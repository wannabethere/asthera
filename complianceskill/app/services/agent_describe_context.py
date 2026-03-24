"""
Agent Describe Context — build prompt + tools description for proxy layer.

Runs at registration: for each agent_id we load prompt file(s) and tool names,
then call an LLM to produce purpose, goal, and use cases. The describe endpoint
returns this so the proxy has the right context.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.agents.prompt_loader import (
    load_prompt,
    PROMPTS_CSOD,
    PROMPTS_MDL,
    PROMPTS_BASE,
    PROMPTS_SHARED,
)

logger = logging.getLogger(__name__)

# Max chars of each prompt to include in summary (avoid huge payloads)
PROMPT_EXCERPT_CHARS = 800


# agent_id -> (list of (prompt_name, prompts_dir), list of tool names)
# prompts_dir is path-like (str or Path); tool names come from CSOD_TOOL_MAP or similar
AGENT_PROMPT_AND_TOOLS: Dict[str, Tuple[List[Tuple[str, str]], List[str]]] = {
    "csod-planner": (
        [
            ("02_csod_planner", str(PROMPTS_CSOD)),
            ("01_analysis_intent_classifier", str(PROMPTS_SHARED)),
            ("01_intent_classifier_domain_addon", str(PROMPTS_CSOD)),
        ],
        ["tavily_search"],
    ),
    "csod-workflow": (
        [
            ("03_metrics_recommender", str(PROMPTS_CSOD)),
            ("04_dashboard_generator", str(PROMPTS_CSOD)),
            ("05_compliance_test_generator", str(PROMPTS_CSOD)),
        ],
        [],  # CSOD_TOOL_MAP has placeholders; list by name for documentation
    ),
    "csod-metric-advisor": (
        [
            ("03_metrics_recommender", str(PROMPTS_CSOD)),
            ("04_dashboard_generator", str(PROMPTS_CSOD)),
            ("05_compliance_test_generator", str(PROMPTS_CSOD)),
        ],
        [],
    ),
    "dt-workflow": (
        [
            ("01_intent_classifier", str(PROMPTS_MDL)),
            ("02_detection_triage_planner", str(PROMPTS_MDL)),
            ("03_detection_engineer", str(PROMPTS_MDL)),
        ],
        [],
    ),
    "compliance-workflow": (
        [("01_intent_classifier", str(PROMPTS_BASE))],
        [],
    ),
    "dashboard-agent": (
        [("04_dashboard_generator", str(PROMPTS_CSOD)), ("26_dashboard_layout", str(PROMPTS_CSOD))],
        [],
    ),
}


def _excerpt(text: str, max_chars: int = PROMPT_EXCERPT_CHARS) -> str:
    """First max_chars, break at last newline if possible."""
    if len(text) <= max_chars:
        return text.strip()
    cut = text[: max_chars + 1]
    last_nl = cut.rfind("\n")
    if last_nl > max_chars // 2:
        return cut[: last_nl + 1].strip()
    return cut.strip() + "\n..."


def _load_prompt_safe(name: str, prompts_dir: str) -> Optional[str]:
    try:
        return load_prompt(name, prompts_dir=prompts_dir)
    except FileNotFoundError as e:
        logger.debug("Prompt not found for describe context: %s", e)
        return None


def _parse_llm_json(content: str) -> Optional[Dict[str, Any]]:
    """Extract JSON object from LLM response (handle markdown code blocks)."""
    content = (content or "").strip()
    # Strip ```json ... ``` or ``` ... ```
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
    if m:
        content = m.group(1).strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None


def _llm_describe_agent(agent_id: str, prompt_summary: str, tools: List[str]) -> Optional[Dict[str, Any]]:
    """
    Call LLM to define purpose, goal, and use cases from the agent's prompts and tools.
    Returns dict with purpose, goal, use_cases (list), or None on failure.
    """
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from app.core.dependencies import get_llm

        system = """You are an expert at summarizing AI agents for a routing/proxy layer.
Given an agent's system prompt excerpts and tool names, output a short JSON object with exactly these keys:
- "purpose": One clear sentence stating what this agent is for.
- "goal": One sentence stating the primary goal or outcome.
- "use_cases": A JSON array of 2-5 short phrases describing what this agent can be used for (e.g. "Answer compliance questions", "Generate dashboards").

Output only valid JSON, no markdown or extra text."""

        tools_str = ", ".join(tools) if tools else "(none listed)"
        user = f"""Agent ID: {agent_id}

System prompt excerpts:
{prompt_summary[:6000]}

Tools: {tools_str}

Return JSON with keys: purpose, goal, use_cases."""

        llm = get_llm(temperature=0)
        resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        raw = getattr(resp, "content", str(resp)) or ""
        parsed = _parse_llm_json(raw)
        if not parsed or not isinstance(parsed, dict):
            return None
        # Normalize use_cases to list of strings
        uc = parsed.get("use_cases")
        if isinstance(uc, list):
            parsed["use_cases"] = [str(x) for x in uc]
        elif isinstance(uc, str):
            parsed["use_cases"] = [uc]
        else:
            parsed["use_cases"] = []
        return parsed
    except Exception as e:
        logger.warning("LLM describe step failed for %s: %s", agent_id, e)
        return None


def build_agent_describe_context(agent_id: str) -> Dict[str, Any]:
    """
    Build context for the proxy layer: prompt excerpts, tools, and an LLM-generated
    description (purpose, goal, use cases). Called at registration or on-demand.
    Returns dict with:
      - purpose: one-sentence purpose (LLM)
      - goal: one-sentence goal (LLM)
      - use_cases: list of short use-case phrases (LLM)
      - description: one-liner for planner (from purpose or fallback)
      - prompt_summary, prompt_excerpts, tools: raw context for proxy
    """
    config = AGENT_PROMPT_AND_TOOLS.get(agent_id)
    prompt_excerpts: List[Dict[str, str]] = []
    prompt_summary_parts: List[str] = []

    if config:
        prompt_specs, tool_names = config
        for prompt_name, prompts_dir in prompt_specs:
            content = _load_prompt_safe(prompt_name, prompts_dir)
            if content:
                excerpt = _excerpt(content)
                prompt_excerpts.append({"prompt_name": prompt_name, "excerpt": excerpt})
                prompt_summary_parts.append(f"## {prompt_name}\n{excerpt}")
        tools = list(tool_names) if tool_names else []
    else:
        tools = []

    prompt_summary = "\n\n".join(prompt_summary_parts).strip() if prompt_summary_parts else ""
    if not prompt_summary:
        prompt_summary = f"Agent {agent_id}: no prompt files configured for describe context."

    # LLM step: define purpose, goal, use cases
    llm_out = _llm_describe_agent(agent_id, prompt_summary, tools)
    if llm_out:
        purpose = llm_out.get("purpose") or ""
        goal = llm_out.get("goal") or ""
        use_cases = llm_out.get("use_cases") or []
        description = purpose or (prompt_summary.split("\n")[0].strip() if prompt_summary else f"Agent {agent_id}.")
    else:
        purpose = ""
        goal = ""
        use_cases = []
        description = prompt_summary.split("\n")[0].strip() if prompt_summary else f"Agent {agent_id}."

    out: Dict[str, Any] = {
        "purpose": purpose,
        "goal": goal,
        "use_cases": use_cases,
        "description": description,
        "prompt_summary": prompt_summary,
        "prompt_excerpts": prompt_excerpts,
        "tools": tools,
    }

    # Same executor catalog the LangGraph planner injects (executor_registry + planned_executors_v5).
    # Lets external proxies / describe consumers align with internal csod_planner_node routing.
    if agent_id in (
        "csod-planner",
        "csod-workflow",
        "csod-metric-advisor",
    ):
        try:
            from app.agents.csod.executor_registry import (
                registry_summary_for_planner,
                INTENT_TO_PRIMARY_EXECUTOR,
            )

            out["executor_catalog"] = registry_summary_for_planner()
            out["intent_to_primary_executor"] = dict(INTENT_TO_PRIMARY_EXECUTOR)
            out["routing_layers"] = (
                "1) AgentRegistry: HTTP agent_id → LangGraph app. "
                "2) Inside csod-workflow: csod_planner_node uses executor_catalog for execution_plan executor_id. "
                "3) executor_registry.py merges _CORE_IMPLEMENTED over executor_registry_planned.planned_executors_v5."
            )
        except Exception as e:
            logger.debug("Executor catalog attach skipped for %s: %s", agent_id, e)

    return out

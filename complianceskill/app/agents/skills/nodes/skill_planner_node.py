"""
Skill Analysis Planner Node — Phase 2 of the skill pipeline.

Runs *after* skill intent identification, *before* the main planner.
Produces a structured data plan that the planner and recommender can consume.

If ``skill_context`` is None (no active skill), this node is a pass-through.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from langchain_core.prompts import ChatPromptTemplate

from app.core.dependencies import get_llm
from app.agents.skills import SkillRegistry
from app.agents.skills.nodes.skill_intent_node import SKILL_CONTEXT_KEY, SKILL_DATA_PLAN_KEY

logger = logging.getLogger(__name__)


def skill_analysis_planner_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase 2: Produce a skill-specific data plan.

    Reads:
        - skill_context (from Phase 1)
        - user_query
        - data_enrichment (from intent classifier)
        - selected_data_sources
        - compliance_profile

    Writes:
        - skill_data_plan: {required_metrics, required_kpis, transformations, mdl_scope, causal_needs}

    The data plan is consumed by:
        - The main planner (csod_planner / dt_planner) — informs step selection
        - The skill recommender (Phase 3) — guides metric framing
        - The skill validator (Phase 4) — provides transformation requirements
    """
    skill_context = state.get(SKILL_CONTEXT_KEY)

    if not skill_context or not skill_context.get("confirmed", False):
        state[SKILL_DATA_PLAN_KEY] = None
        return state

    skill_id = skill_context["skill_id"]
    registry = SkillRegistry.instance()
    skill = registry.get(skill_id)

    if not skill:
        state[SKILL_DATA_PLAN_KEY] = None
        return state

    # Load the skill's analysis_planner prompt
    prompt_text = skill.get_prompt("analysis_planner")

    if prompt_text:
        try:
            data_plan = _invoke_planner_llm(prompt_text, skill, skill_context, state)
        except Exception:
            logger.warning("Skill planner LLM failed for '%s' — using declarative plan", skill_id, exc_info=True)
            data_plan = _declarative_data_plan(skill, skill_context)
    else:
        data_plan = _declarative_data_plan(skill, skill_context)

    state[SKILL_DATA_PLAN_KEY] = data_plan

    _log_skill_step(state, "skill_analysis_planner", skill_id, data_plan)

    return state


def _invoke_planner_llm(
    prompt_text: str,
    skill: Any,
    skill_context: Dict[str, Any],
    state: Dict[str, Any],
) -> Dict[str, Any]:
    """Run the skill's analysis_planner prompt through LLM."""
    llm = get_llm(temperature=0)

    prompt = ChatPromptTemplate.from_messages([
        ("system", prompt_text.replace("{", "{{").replace("}", "}}")),
        ("human", "{input}"),
    ])

    # Build context for the planner
    parts = [f"User query: {state.get('user_query', '')}"]

    # Extracted params from Phase 1
    extracted = skill_context.get("extracted_params", {})
    if extracted:
        parts.append(f"\nExtracted parameters from intent:\n{json.dumps(extracted, indent=2)}")

    # Data enrichment from intent classifier
    enrichment = state.get("data_enrichment", {})
    if enrichment:
        focus = enrichment.get("suggested_focus_areas", [])
        if focus:
            parts.append(f"\nSuggested focus areas: {', '.join(focus)}")

    # Available data sources
    sources = state.get("selected_data_sources") or state.get("csod_data_sources_in_scope", [])
    if sources:
        parts.append(f"\nAvailable data sources: {', '.join(sources)}")

    # Compliance profile filters
    profile = state.get("compliance_profile", {})
    filters = []
    for k in ("time_window", "org_unit", "training_type", "persona", "cost_focus", "skills_domain"):
        v = profile.get(k)
        if v:
            filters.append(f"  {k}: {v}")
    if filters:
        parts.append("\nCompliance profile:\n" + "\n".join(filters))

    human_msg = "\n".join(parts)
    chain = prompt | llm
    response = chain.invoke({"input": human_msg})
    content = response.content if hasattr(response, "content") else str(response)

    parsed = _parse_json(content)
    if parsed and isinstance(parsed, dict):
        parsed["skill_id"] = skill.skill_id
        return parsed

    return _declarative_data_plan(skill, skill_context)


def _declarative_data_plan(skill: Any, skill_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a data plan directly from the skill definition (no LLM).

    This is the fallback and also the path for skills without an
    analysis_planner prompt.
    """
    dp = skill.data_plan
    plan: Dict[str, Any] = {
        "skill_id": skill.skill_id,
        "required_metrics": {
            "primary": list(dp.kpi_focus[:5]) if dp.kpi_focus else [],
            "secondary": list(dp.kpi_focus[5:]) if len(dp.kpi_focus) > 5 else [],
        },
        "required_kpis": [],
        "target_resolution_strategy": "not_applicable",
        "transformations": [
            {"name": t, "formula": t, "per": "metric"}
            for t in dp.transformations
        ],
        "mdl_scope": {
            "required_tables": [],
            "required_columns": list(dp.required_data_elements),
        },
        "causal_needs": {
            "mode": dp.cce_config.mode if dp.cce_config else "disabled",
            "usage": "general",
            "depth": 2,
        },
    }

    # Merge extracted params
    extracted = skill_context.get("extracted_params", {})
    if "target_value" in extracted:
        plan["target_resolution_strategy"] = extracted.get("target_source", "user_specified")

    return plan


def _parse_json(text: str) -> Any:
    import re
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None


def _log_skill_step(state: Dict[str, Any], step_name: str, skill_id: str, plan: Dict) -> None:
    from datetime import datetime
    if "execution_steps" not in state:
        state["execution_steps"] = []
    state["execution_steps"].append({
        "step_name": step_name,
        "agent_name": f"skill:{skill_id}",
        "timestamp": datetime.utcnow().isoformat(),
        "status": "completed",
        "inputs": {"skill_id": skill_id},
        "outputs": {
            "has_plan": plan is not None,
            "metric_count": len(plan.get("required_metrics", {}).get("primary", [])) if plan else 0,
        },
    })

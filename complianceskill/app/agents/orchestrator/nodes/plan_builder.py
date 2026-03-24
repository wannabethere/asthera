"""
Stage 3: Hybrid Plan Builder — breaks the user request into subtasks
dispatched to CSOD (data analysis) and/or DT (detection/triage).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List
from uuid import uuid4

from langchain_core.prompts import ChatPromptTemplate

from app.core.dependencies import get_llm
from app.agents.orchestrator.orchestrator_state import OrchestratorState, Subtask

logger = logging.getLogger(__name__)


def hybrid_plan_builder_node(state: OrchestratorState) -> OrchestratorState:
    """
    Break the user request into concrete subtasks with target workflow assignments.

    Reads: user_query, request_classification, capabilities_needed
    Writes: subtasks, execution_order
    """
    user_query = state.get("user_query", "")
    classification = state.get("request_classification", {})
    capabilities = state.get("capabilities_needed", {})
    request_type = capabilities.get("request_type", "analysis_only")

    try:
        subtasks = _build_plan_via_llm(user_query, classification, capabilities, state)
    except Exception as e:
        logger.warning("Hybrid plan LLM failed, using heuristic: %s", e)
        subtasks = _heuristic_plan(user_query, classification, capabilities)

    # Ensure all subtasks have IDs and status
    for st in subtasks:
        st.setdefault("subtask_id", f"st_{uuid4().hex[:8]}")
        st.setdefault("status", "pending")
        st.setdefault("depends_on", [])
        st.setdefault("focus_areas", [])

    # Build execution order respecting dependencies
    execution_order = _topological_sort(subtasks)

    state["subtasks"] = subtasks
    state["execution_order"] = execution_order

    logger.info(
        "Hybrid plan: %d subtasks (%d analysis, %d detection), order=%s",
        len(subtasks),
        sum(1 for s in subtasks if s["target_workflow"] == "csod"),
        sum(1 for s in subtasks if s["target_workflow"] == "dt"),
        execution_order,
    )

    _log_step(state, "hybrid_plan_builder", {
        "subtask_count": len(subtasks),
        "execution_order": execution_order,
    })
    return state


def _heuristic_plan(
    user_query: str,
    classification: Dict[str, Any],
    capabilities: Dict[str, Any],
) -> List[Subtask]:
    """Build subtasks from classification signals without LLM."""
    subtasks: List[Subtask] = []
    request_type = capabilities.get("request_type", "analysis_only")
    framework_signals = classification.get("framework_signals", [])
    dt_mode = capabilities.get("dt_mode", "no_mdl")

    if capabilities.get("needs_detection_engineering"):
        st: Subtask = {
            "subtask_id": "detection_main",
            "subtask_type": "detection",
            "target_workflow": "dt",
            "description": f"Generate detection rules and playbook for: {user_query[:200]}",
            "priority": 1,
            "depends_on": [],
            "user_query": user_query,
            "intent_hint": "detection_focused" if request_type == "detection_only" else "full_chain",
            "focus_areas": [],
            "framework_id": framework_signals[0] if framework_signals else None,
            "requirement_code": None,
            "status": "pending",
            "result": None,
            "error": None,
        }
        # Pass dt_mode so DT workflow knows whether to skip retrieval
        st["dt_mode"] = dt_mode
        subtasks.append(st)

    if capabilities.get("needs_data_analysis"):
        depends = ["detection_main"] if capabilities.get("needs_detection_engineering") else []
        st: Subtask = {
            "subtask_id": "analysis_main",
            "subtask_type": "analysis",
            "target_workflow": "csod",
            "description": f"Data analysis and metrics for: {user_query[:200]}",
            "priority": 2,
            "depends_on": depends,
            "user_query": user_query,
            "intent_hint": None,
            "focus_areas": [],
            "framework_id": None,
            "requirement_code": None,
            "status": "pending",
            "result": None,
            "error": None,
        }
        subtasks.append(st)

    if capabilities.get("needs_dashboard") and not capabilities.get("needs_data_analysis"):
        st: Subtask = {
            "subtask_id": "dashboard_main",
            "subtask_type": "dashboard",
            "target_workflow": "csod",
            "description": f"Build dashboard for: {user_query[:200]}",
            "priority": 2,
            "depends_on": [],
            "user_query": user_query,
            "intent_hint": "dashboard_generation_for_persona",
            "focus_areas": [],
            "framework_id": None,
            "requirement_code": None,
            "status": "pending",
            "result": None,
            "error": None,
        }
        subtasks.append(st)

    # Fallback — at least one subtask
    if not subtasks:
        subtasks.append({
            "subtask_id": "fallback",
            "subtask_type": "analysis",
            "target_workflow": "csod",
            "description": user_query,
            "priority": 1,
            "depends_on": [],
            "user_query": user_query,
            "intent_hint": None,
            "focus_areas": [],
            "framework_id": None,
            "requirement_code": None,
            "status": "pending",
            "result": None,
            "error": None,
        })

    return subtasks


def _build_plan_via_llm(
    user_query: str,
    classification: Dict[str, Any],
    capabilities: Dict[str, Any],
    state: OrchestratorState,
) -> List[Subtask]:
    """Use LLM to decompose the request into subtasks."""
    llm = get_llm(temperature=0)
    prompt = ChatPromptTemplate.from_messages([
        ("system", _PLAN_BUILDER_PROMPT),
        ("human", "{input}"),
    ])

    human_msg = (
        f"User query: {user_query}\n\n"
        f"Classification: {json.dumps(classification, indent=2)}\n\n"
        f"Capabilities: {json.dumps(capabilities, indent=2)}\n\n"
        f"Data sources connected: {json.dumps(state.get('selected_data_sources', []))}\n\n"
        "Break this into subtasks. Return JSON array."
    )

    chain = prompt | llm
    response = chain.invoke({"input": human_msg})
    content = response.content if hasattr(response, "content") else str(response)

    parsed = _parse_json(content)
    if isinstance(parsed, list) and parsed:
        return parsed
    if isinstance(parsed, dict) and "subtasks" in parsed:
        return parsed["subtasks"]

    # Fallback
    return _heuristic_plan(user_query, classification, capabilities)


def _topological_sort(subtasks: List[Subtask]) -> List[str]:
    """Sort subtask IDs by dependency order."""
    id_set = {s["subtask_id"] for s in subtasks}
    result: List[str] = []
    visited = set()

    def visit(sid: str):
        if sid in visited:
            return
        visited.add(sid)
        st = next((s for s in subtasks if s["subtask_id"] == sid), None)
        if st:
            for dep in st.get("depends_on", []):
                if dep in id_set:
                    visit(dep)
        result.append(sid)

    for s in sorted(subtasks, key=lambda x: x.get("priority", 99)):
        visit(s["subtask_id"])

    return result


def _parse_json(text: str) -> Any:
    import re
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    for pattern in [r"```json\s*(\[.*?\])\s*```", r"```json\s*(\{.*?\})\s*```"]:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
    return None


def _log_step(state: OrchestratorState, step_name: str, outputs: Dict) -> None:
    from datetime import datetime
    state.setdefault("execution_steps", [])
    state["execution_steps"].append({
        "step_name": step_name, "agent_name": "orchestrator",
        "timestamp": datetime.utcnow().isoformat(), "status": "completed",
        "outputs": outputs,
    })


_PLAN_BUILDER_PROMPT = """You are a hybrid plan builder for a security/compliance platform.

Given a user request that may need both detection engineering (SIEM rules, playbooks) AND data analysis (metrics, dashboards, KPIs), break the request into subtasks.

Each subtask must specify:
- subtask_id: unique identifier (e.g., "detection_soc2_access", "analysis_metrics")
- subtask_type: "detection" | "analysis" | "triage" | "dashboard"
- target_workflow: "dt" for detection/triage, "csod" for data analysis/dashboards
- description: what this subtask should accomplish
- priority: 1 = run first
- depends_on: list of subtask_ids that must complete before this one
- user_query: rewritten query scoped to this subtask
- intent_hint: suggested intent for the sub-graph classifier (optional)
- focus_areas: relevant focus areas

Rules:
- Detection subtasks go to "dt" workflow
- Analysis, metrics, dashboard, medallion planning subtasks go to "csod" workflow
- If detection needs data context from analysis, make analysis depend on detection (detection provides metric candidates that analysis can refine)
- Keep subtasks focused — don't combine detection and analysis in one subtask

Return a JSON array of subtasks."""

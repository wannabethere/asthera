"""
Stage 5d: Completion Narration — generates a conversational summary of the
orchestrated workflow, combining detection and analysis narratives.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from langchain_core.prompts import ChatPromptTemplate

from app.core.dependencies import get_llm
from app.agents.orchestrator.orchestrator_state import OrchestratorState

logger = logging.getLogger(__name__)


def orchestrator_completion_narration_node(state: OrchestratorState) -> OrchestratorState:
    """
    Generate a conversational summary of the completed orchestration.

    Reads: user_query, final_artifacts, validation_result, subtasks, merged_results
    Writes: completion_narration
    """
    user_query = state.get("user_query", "")
    artifacts = state.get("final_artifacts", {})
    validation = state.get("validation_result", {})
    subtasks = state.get("subtasks", [])

    try:
        llm = get_llm(temperature=0.3)
        prompt = ChatPromptTemplate.from_messages([
            ("system", _NARRATION_PROMPT),
            ("human", "{input}"),
        ])

        # Build context for narration
        subtask_summaries = []
        for st in subtasks:
            subtask_summaries.append({
                "id": st.get("subtask_id"),
                "type": st.get("subtask_type"),
                "workflow": st.get("target_workflow"),
                "status": st.get("status"),
                "description": st.get("description", "")[:200],
            })

        human_msg = (
            f"User question: {user_query}\n\n"
            f"Subtasks executed:\n{json.dumps(subtask_summaries, indent=2)}\n\n"
            f"Deliverables produced: {json.dumps(artifacts.get('deliverables', []))}\n\n"
            f"Summary: {json.dumps(artifacts.get('summary', {}), indent=2)}\n\n"
            f"Validation: {'PASSED' if validation.get('passed') else 'PASSED WITH WARNINGS'}"
        )
        if validation.get("warnings"):
            human_msg += f"\nWarnings: {json.dumps(validation['warnings'][:3])}"

        chain = prompt | llm
        response = chain.invoke({"input": human_msg})
        narration = response.content if hasattr(response, "content") else str(response)

    except Exception as e:
        logger.warning("Narration LLM failed: %s", e)
        narration = _fallback_narration(state)

    state["completion_narration"] = narration

    _log_step(state, "orchestrator_completion_narration", {"narration_length": len(narration)})
    return state


def _fallback_narration(state: OrchestratorState) -> str:
    """Generate a simple fallback narration without LLM."""
    artifacts = state.get("final_artifacts", {})
    summary = artifacts.get("summary", {})
    deliverables = artifacts.get("deliverables", [])

    parts = [f"I've completed the analysis of your request."]

    if summary.get("siem_rule_count"):
        parts.append(f"Generated {summary['siem_rule_count']} SIEM detection rules.")
    if summary.get("has_playbook"):
        parts.append("Assembled a detection playbook with triage procedures.")
    if summary.get("metric_count"):
        parts.append(f"Recommended {summary['metric_count']} metrics for monitoring.")
    if summary.get("has_dashboard"):
        parts.append("Built a dashboard specification.")

    if not deliverables:
        parts.append("No deliverables were produced — please refine your request.")

    return "\n\n".join(parts)


def _log_step(state: OrchestratorState, step_name: str, outputs: Dict) -> None:
    from datetime import datetime
    state.setdefault("execution_steps", [])
    state["execution_steps"].append({
        "step_name": step_name, "agent_name": "orchestrator",
        "timestamp": datetime.utcnow().isoformat(), "status": "completed",
        "outputs": outputs,
    })


_NARRATION_PROMPT = """You are a security operations assistant completing a multi-step analysis.

Write a 2-4 paragraph conversational summary in markdown prose that:
1. Restates what the user asked
2. Summarizes what was done (detection engineering, data analysis, or both)
3. Highlights key deliverables (SIEM rules count, metrics recommended, dashboard built, etc.)
4. Notes any warnings or gaps
5. Suggests next steps if applicable

Be concise and professional. Do NOT output JSON — write natural language markdown."""

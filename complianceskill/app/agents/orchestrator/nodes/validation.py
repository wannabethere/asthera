"""
Stage 5c: Final Validation — quality gate for assembled artifacts.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from app.agents.orchestrator.orchestrator_state import OrchestratorState

logger = logging.getLogger(__name__)


def final_validation_node(state: OrchestratorState) -> OrchestratorState:
    """
    Validate final artifacts: check completeness, cross-reference rules↔metrics.

    Reads: final_artifacts, subtasks
    Writes: validation_result
    """
    artifacts = state.get("final_artifacts", {})
    subtasks = state.get("subtasks", [])
    deliverables = artifacts.get("deliverables", [])

    issues = []
    warnings = []

    # Check that all completed subtasks produced results
    for st in subtasks:
        if st.get("status") == "completed" and not st.get("result"):
            warnings.append(f"Subtask '{st['subtask_id']}' completed but produced no result")
        if st.get("status") == "failed":
            issues.append(f"Subtask '{st['subtask_id']}' failed: {st.get('error', 'unknown')}")

    # Check detection artifacts
    if "siem_rules" in deliverables:
        rules = artifacts.get("siem_rules", [])
        if not rules:
            warnings.append("SIEM rules deliverable is empty")
        else:
            # Check each rule has required fields
            for i, rule in enumerate(rules):
                if not rule.get("query") and not rule.get("rule_content"):
                    warnings.append(f"SIEM rule {i} has no query/content")

    # Check analysis artifacts
    if "metric_recommendations" in deliverables:
        metrics = artifacts.get("metric_recommendations", [])
        if not metrics:
            warnings.append("Metric recommendations deliverable is empty")

    passed = len(issues) == 0
    state["validation_result"] = {
        "passed": passed,
        "issues": issues,
        "warnings": warnings,
        "deliverable_count": len(deliverables),
        "subtask_completion_rate": (
            sum(1 for s in subtasks if s.get("status") == "completed") / max(len(subtasks), 1)
        ),
    }

    level = "INFO" if passed else "WARNING"
    logger.log(
        logging.INFO if passed else logging.WARNING,
        "Validation %s: %d issues, %d warnings, %d deliverables",
        "PASSED" if passed else "FAILED",
        len(issues), len(warnings), len(deliverables),
    )

    _log_step(state, "final_validation", state["validation_result"])
    return state


def _log_step(state: OrchestratorState, step_name: str, outputs: Dict) -> None:
    from datetime import datetime
    state.setdefault("execution_steps", [])
    state["execution_steps"].append({
        "step_name": step_name, "agent_name": "orchestrator",
        "timestamp": datetime.utcnow().isoformat(), "status": "completed",
        "outputs": {k: v for k, v in outputs.items() if k in ("passed", "deliverable_count")},
    })

"""
State Transformer

Transforms LangGraph internal state to external API state,
providing a clean separation of concerns.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from app.agents.state import EnhancedCompliancePipelineState

logger = logging.getLogger(__name__)


def transform_to_external_state(
    langgraph_state: Dict[str, Any],
    workflow_type: str = "compliance",
) -> Dict[str, Any]:
    """
    Transform LangGraph internal state to external API state.
    
    This function extracts only the relevant information for the caller,
    avoiding exposing internal LangGraph implementation details.
    
    Args:
        langgraph_state: The LangGraph state dictionary
        workflow_type: "compliance" or "detection_triage"
    
    Returns:
        External state dictionary suitable for API responses
    """
    external_state = {
        "intent": langgraph_state.get("intent"),
        "framework_id": langgraph_state.get("framework_id"),
        "requirement_id": langgraph_state.get("requirement_id"),
        "requirement_code": langgraph_state.get("requirement_code"),
        "requirement_name": langgraph_state.get("requirement_name"),
        "session_id": langgraph_state.get("session_id"),
    }
    
    # Artifacts
    external_state["artifacts"] = {
        "siem_rules": langgraph_state.get("siem_rules", []),
        "playbooks": langgraph_state.get("playbooks", []),
        "test_scripts": langgraph_state.get("test_scripts", []),
        "dashboards": langgraph_state.get("dashboards", []),
        "data_pipelines": langgraph_state.get("data_pipelines", []),
        "vulnerability_mappings": langgraph_state.get("vulnerability_mappings", []),
    }
    
    # Planning and execution
    execution_plan = langgraph_state.get("execution_plan")
    if execution_plan:
        external_state["execution_plan"] = [
            {
                "step_id": step.step_id if hasattr(step, "step_id") else step.get("step_id"),
                "description": step.description if hasattr(step, "description") else step.get("description"),
                "status": step.status if hasattr(step, "status") else step.get("status", "pending"),
                "agent": step.agent if hasattr(step, "agent") else step.get("agent"),
            }
            for step in execution_plan
        ]
    else:
        external_state["execution_plan"] = []
    
    external_state["execution_status"] = {
        "current_step_index": langgraph_state.get("current_step_index", 0),
        "iteration_count": langgraph_state.get("iteration_count", 0),
        "max_iterations": langgraph_state.get("max_iterations", 5),
        "plan_completion_status": langgraph_state.get("plan_completion_status", {}),
    }
    
    # Validation results
    validation_results = langgraph_state.get("validation_results", [])
    external_state["validation"] = {
        "validation_passed": langgraph_state.get("validation_passed", False),
        "quality_score": langgraph_state.get("quality_score"),
        "results": [
            {
                "artifact_type": result.artifact_type if hasattr(result, "artifact_type") else result.get("artifact_type"),
                "artifact_id": result.artifact_id if hasattr(result, "artifact_id") else result.get("artifact_id"),
                "passed": result.passed if hasattr(result, "passed") else result.get("passed", False),
                "confidence_score": result.confidence_score if hasattr(result, "confidence_score") else result.get("confidence_score", 0.0),
                "issues": result.issues if hasattr(result, "issues") else result.get("issues", []),
                "suggestions": result.suggestions if hasattr(result, "suggestions") else result.get("suggestions", []),
            }
            for result in validation_results
        ],
    }
    
    # Metrics and data enrichment
    external_state["metrics"] = {
        "resolved_metrics": langgraph_state.get("resolved_metrics", []),
        "metrics_context": langgraph_state.get("metrics_context", []),
    }
    
    data_enrichment = langgraph_state.get("data_enrichment", {})
    external_state["data_enrichment"] = {
        "needs_metrics": data_enrichment.get("needs_metrics", False),
        "needs_mdl": data_enrichment.get("needs_mdl", False),
        "needs_xsoar_dashboard": data_enrichment.get("needs_xsoar_dashboard", False),
        "suggested_focus_areas": data_enrichment.get("suggested_focus_areas", []),
    }
    
    # Framework and controls
    external_state["framework"] = {
        "controls": langgraph_state.get("controls", []),
        "risks": langgraph_state.get("risks", []),
        "scenarios": langgraph_state.get("scenarios", []),
        "test_cases": langgraph_state.get("test_cases", []),
        "gap_analysis_results": langgraph_state.get("gap_analysis_results", []),
        "cross_framework_mappings": langgraph_state.get("cross_framework_mappings", []),
    }
    
    # CSOD specific fields
    if workflow_type == "csod":
        external_state["csod"] = {
            "intent": langgraph_state.get("csod_intent"),
            "persona": langgraph_state.get("csod_persona"),
            "plan_summary": langgraph_state.get("csod_plan_summary"),
            "estimated_complexity": langgraph_state.get("csod_estimated_complexity"),
            "metric_recommendations": langgraph_state.get("csod_metric_recommendations", []),
            "kpi_recommendations": langgraph_state.get("csod_kpi_recommendations", []),
            "table_recommendations": langgraph_state.get("csod_table_recommendations", []),
            "medallion_plan": langgraph_state.get("csod_medallion_plan", {}),
            "generated_gold_model_sql": langgraph_state.get("csod_generated_gold_model_sql", []),
            "dashboard_assembled": langgraph_state.get("csod_dashboard_assembled"),
            "test_cases": langgraph_state.get("csod_test_cases", []),
            "assembled_output": langgraph_state.get("csod_assembled_output"),
            "cubejs_schema_files": langgraph_state.get("cubejs_schema_files", []),
        }
        # CSOD also populates shared artifacts
        external_state["artifacts"]["dashboards"] = langgraph_state.get("dashboards", [])

    # Detection & Triage specific fields
    if workflow_type == "detection_triage":
        external_state["detection_triage"] = {
            "plan_summary": langgraph_state.get("dt_plan_summary"),
            "estimated_complexity": langgraph_state.get("dt_estimated_complexity"),
            "playbook_template": langgraph_state.get("dt_playbook_template"),
            "expected_outputs": langgraph_state.get("dt_expected_outputs", {}),
            "retrieved_controls": langgraph_state.get("dt_retrieved_controls", []),
            "retrieved_risks": langgraph_state.get("dt_retrieved_risks", []),
            "retrieved_scenarios": langgraph_state.get("dt_retrieved_scenarios", []),
            "resolved_schemas": langgraph_state.get("dt_resolved_schemas", []),
            "gold_standard_tables": langgraph_state.get("dt_gold_standard_tables", []),
            "metric_recommendations": langgraph_state.get("dt_metric_recommendations", []),
            "unmeasured_controls": langgraph_state.get("dt_unmeasured_controls", []),
            "siem_validation": {
                "passed": langgraph_state.get("dt_siem_validation_passed", False),
                "failures": langgraph_state.get("dt_siem_validation_failures", []),
            },
            "metric_validation": {
                "passed": langgraph_state.get("dt_metric_validation_passed", False),
                "failures": langgraph_state.get("dt_metric_validation_failures", []),
                "warnings": langgraph_state.get("dt_metric_validation_warnings", []),
            },
            "validation_iteration": langgraph_state.get("dt_validation_iteration", 0),
            "assembled_playbook": langgraph_state.get("dt_assembled_playbook"),
        }
    
    # Calculation plan (if present)
    calculation_plan = langgraph_state.get("calculation_plan")
    if calculation_plan:
        external_state["calculation_plan"] = calculation_plan
    
    # Execution steps (for debugging/logging)
    execution_steps = langgraph_state.get("execution_steps", [])
    external_state["execution_steps"] = [
        {
            "step_id": step.get("step_id"),
            "node": step.get("node"),
            "timestamp": step.get("timestamp"),
            "status": step.get("status"),
        }
        for step in execution_steps[-10:]  # Last 10 steps only
    ]
    
    return external_state


def extract_checkpoint_from_state(
    langgraph_state: Dict[str, Any],
    node_name: str,
) -> Optional[Dict[str, Any]]:
    """
    Extract checkpoint information from LangGraph state.
    
    Args:
        langgraph_state: The LangGraph state dictionary
        node_name: Name of the node that may have created a checkpoint
    
    Returns:
        Checkpoint dictionary if found, None otherwise
    """
    # Check for CSOD planner checkpoint first
    csod_checkpoint = langgraph_state.get("csod_planner_checkpoint")
    if csod_checkpoint and isinstance(csod_checkpoint, dict):
        if csod_checkpoint.get("requires_user_input", False):
            return {
                "checkpoint_id": f"{node_name}_checkpoint",
                "checkpoint_type": csod_checkpoint.get("phase", "unknown"),
                "node": node_name,
                "data": csod_checkpoint,
                "message": csod_checkpoint.get("message", "Waiting for user input"),
                "requires_user_input": True,
            }
    
    # Check for generic checkpoints array
    checkpoints = langgraph_state.get("checkpoints", [])
    if not checkpoints:
        return None
    
    # Find the most recent checkpoint that requires user input
    for checkpoint in reversed(checkpoints):
        if isinstance(checkpoint, dict):
            if checkpoint.get("requires_user_input", False):
                return {
                    "checkpoint_id": checkpoint.get("node", node_name),
                    "checkpoint_type": checkpoint.get("type", "unknown"),
                    "node": checkpoint.get("node", node_name),
                    "data": checkpoint.get("data", {}),
                    "message": checkpoint.get("message", "Waiting for user input"),
                    "requires_user_input": True,
                }
    
    return None

"""
DT Validation Reset Node

A single-purpose node that runs between dt_siem_rule_validator and dt_detection_engineer (on re-try),
and between dt_metric_calculation_validator and the next engineer (on re-try). It increments or resets
dt_validation_iteration and clears dt_validating_detection_metrics. Moves state mutation out of
routing functions where it is unreliable.
"""
import logging
from app.agents.state import EnhancedCompliancePipelineState
from .constants import MAX_REFINEMENT_ITERATIONS

logger = logging.getLogger(__name__)


def dt_validation_reset_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Validation reset node - handles state mutations for refinement loops.
    
    State reads: dt_siem_validation_passed, dt_metric_validation_passed, dt_validating_detection_metrics, dt_validation_iteration
    State writes: dt_validation_iteration (incremented on retry, reset to 0 on phase transition), dt_validating_detection_metrics (reset to False when moving to triage phase)
    
    This node replaces the state mutations currently in _route_after_siem_validator and _route_after_metric_validator.
    Routing functions become pure: they only read state and return a string. No mutations.
    """
    siem_validation_passed = state.get("dt_siem_validation_passed", True)
    metric_validation_passed = state.get("dt_metric_validation_passed", True)
    validating_detection = state.get("dt_validating_detection_metrics", False)
    iteration = state.get("dt_validation_iteration", 0)
    
    # Determine what phase we're in based on context
    # If we just came from SIEM validator and validation failed, increment iteration
    if not siem_validation_passed and iteration < MAX_REFINEMENT_ITERATIONS:
        state["dt_validation_iteration"] = iteration + 1
        logger.info(f"SIEM validation failed, incrementing iteration to {state['dt_validation_iteration']}")
        return state
    
    # If we just came from metric validator and validation passed, reset iteration and clear flag
    if metric_validation_passed and validating_detection:
        state["dt_validating_detection_metrics"] = False
        state["dt_validation_iteration"] = 0
        logger.info("Metric validation passed (detection phase), resetting iteration and clearing flag")
        return state
    
    # If we just came from metric validator (triage phase) and validation passed, reset iteration
    if metric_validation_passed and not validating_detection:
        state["dt_validation_iteration"] = 0
        logger.info("Metric validation passed (triage phase), resetting iteration")
        return state
    
    # If we came from metric validator and validation failed, increment iteration
    if not metric_validation_passed and iteration < MAX_REFINEMENT_ITERATIONS:
        state["dt_validation_iteration"] = iteration + 1
        logger.info(f"Metric validation failed, incrementing iteration to {state['dt_validation_iteration']}")
        return state
    
    return state

"""
LangGraph workflow for the compliance automation pipeline.

This module defines the complete workflow graph with all nodes and edges,
including planning, execution, validation, and iterative refinement.
"""
import logging
from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.agents.state import EnhancedCompliancePipelineState
from app.agents.nodes import (
    intent_classifier_node,
    profile_resolver_node,
    metrics_recommender_node,
    planner_node,
    plan_executor_node,
    mark_step_complete_node,
    framework_analyzer_node,
    detection_engineer_node,
    playbook_writer_node,
    test_generator_node,
    dashboard_generator_node,
    risk_control_mapper_node,
    gap_analysis_node,
    cross_framework_mapper_node,
    siem_rule_validator_node,
    playbook_validator_node,
    test_script_validator_node,
    cross_artifact_validator_node,
    chain_validation_node,
    feedback_analyzer_node,
    artifact_assembler_node,
)
from app.core.telemetry import instrument_langgraph_node

logger = logging.getLogger(__name__)


def build_compliance_workflow() -> StateGraph:
    """
    Build the complete LangGraph workflow for compliance automation.
    
    Returns:
        Compiled StateGraph ready for execution
    """
    # Create the graph
    workflow = StateGraph(EnhancedCompliancePipelineState)
    
    # ============================================================================
    # Add all nodes (with telemetry instrumentation)
    # ============================================================================
    
    # Classification and planning
    workflow.add_node("intent_classifier", instrument_langgraph_node(intent_classifier_node, "intent_classifier", "compliance"))
    workflow.add_node("profile_resolver", instrument_langgraph_node(profile_resolver_node, "profile_resolver", "compliance"))
    workflow.add_node("metrics_recommender", instrument_langgraph_node(metrics_recommender_node, "metrics_recommender", "compliance"))
    workflow.add_node("planner", instrument_langgraph_node(planner_node, "planner", "compliance"))
    workflow.add_node("plan_executor", instrument_langgraph_node(plan_executor_node, "plan_executor", "compliance"))
    workflow.add_node("mark_step_complete", instrument_langgraph_node(mark_step_complete_node, "mark_step_complete", "compliance"))
    
    # Framework analysis and retrieval
    workflow.add_node("framework_analyzer", instrument_langgraph_node(framework_analyzer_node, "framework_analyzer", "compliance"))
    
    # Artifact generation
    workflow.add_node("detection_engineer", instrument_langgraph_node(detection_engineer_node, "detection_engineer", "compliance"))
    workflow.add_node("playbook_writer", instrument_langgraph_node(playbook_writer_node, "playbook_writer", "compliance"))
    workflow.add_node("test_generator", instrument_langgraph_node(test_generator_node, "test_generator", "compliance"))
    workflow.add_node("dashboard_generator", instrument_langgraph_node(dashboard_generator_node, "dashboard_generator", "compliance"))
    workflow.add_node("risk_control_mapper", instrument_langgraph_node(risk_control_mapper_node, "risk_control_mapper", "compliance"))
    workflow.add_node("gap_analysis", instrument_langgraph_node(gap_analysis_node, "gap_analysis", "compliance"))
    workflow.add_node("cross_framework_mapper", instrument_langgraph_node(cross_framework_mapper_node, "cross_framework_mapper", "compliance"))
    
    # Validation nodes
    workflow.add_node("siem_rule_validator", instrument_langgraph_node(siem_rule_validator_node, "siem_rule_validator", "compliance"))
    workflow.add_node("playbook_validator", instrument_langgraph_node(playbook_validator_node, "playbook_validator", "compliance"))
    workflow.add_node("test_script_validator", instrument_langgraph_node(test_script_validator_node, "test_script_validator", "compliance"))
    workflow.add_node("cross_artifact_validator", instrument_langgraph_node(cross_artifact_validator_node, "cross_artifact_validator", "compliance"))
    workflow.add_node("chain_validation", instrument_langgraph_node(chain_validation_node, "chain_validation", "compliance"))
    
    # Feedback and assembly
    workflow.add_node("feedback_analyzer", instrument_langgraph_node(feedback_analyzer_node, "feedback_analyzer", "compliance"))
    workflow.add_node("artifact_assembler", instrument_langgraph_node(artifact_assembler_node, "artifact_assembler", "compliance"))
    
    # ============================================================================
    # Define edges
    # ============================================================================
    
    # Entry → Intent → Profile Resolver → Planner
    workflow.set_entry_point("intent_classifier")
    
    # After intent classification, always go to profile resolver
    workflow.add_edge("intent_classifier", "profile_resolver")
    
    # After profile resolution, route based on intent and data enrichment flags
    def route_from_profile_resolver(state: EnhancedCompliancePipelineState) -> str:
        intent = state.get("intent", "")
        data_enrichment = state.get("data_enrichment", {})
        
        # If needs_metrics is true (for any intent), go to metrics recommender first
        # This ensures metrics are available to all downstream nodes (test_generator, detection_engineer, etc.)
        if data_enrichment.get("needs_metrics", False):
            return "metrics_recommender"
        # Direct routing for simple intents (no planning needed, no metrics)
        elif intent == "dashboard_generation":
            return "dashboard_generator"
        elif intent == "risk_control_mapping":
            return "risk_control_mapper"
        elif intent == "gap_analysis":
            return "gap_analysis"
        elif intent == "cross_framework_mapping":
            return "cross_framework_mapper"
        else:
            # Other intents go through planner
            return "planner"
    
    workflow.add_conditional_edges(
        "profile_resolver",
        route_from_profile_resolver,
        {
            "metrics_recommender": "metrics_recommender",
            "planner": "planner",
            "dashboard_generator": "dashboard_generator",
            "risk_control_mapper": "risk_control_mapper",
            "gap_analysis": "gap_analysis",
            "cross_framework_mapper": "cross_framework_mapper"
        }
    )
    
    # Metrics recommender → dashboard generator, planner, or direct to other agents
    def route_from_metrics_recommender(state: EnhancedCompliancePipelineState) -> str:
        intent = state.get("intent", "")
        data_enrichment = state.get("data_enrichment", {})
        
        # Direct routing for simple intents (metrics now available in state)
        if intent == "dashboard_generation":
            return "dashboard_generator"
        elif intent == "risk_control_mapping":
            return "risk_control_mapper"
        elif intent == "gap_analysis":
            return "gap_analysis"
        elif intent == "cross_framework_mapping":
            return "cross_framework_mapper"
        else:
            # Other intents go through planner (which can now use resolved_metrics)
            return "planner"
    
    workflow.add_conditional_edges(
        "metrics_recommender",
        route_from_metrics_recommender,
        {
            "dashboard_generator": "dashboard_generator",
            "planner": "planner"
        }
    )
    
    workflow.add_edge("planner", "plan_executor")
    
    # Plan executor routes to agents based on plan
    def route_from_plan_executor(state: EnhancedCompliancePipelineState) -> str:
        next_agent = state.get("next_agent")
        intent = state.get("intent", "")
        
        # Direct routing for dashboard and risk_control_mapping intents
        if intent == "dashboard_generation":
            return "dashboard_generator"
        elif intent == "risk_control_mapping":
            return "risk_control_mapper"
        
        if next_agent == "validation_orchestrator":
            return "siem_rule_validator"  # Start validation phase
        elif next_agent in ["framework_analyzer", "detection_engineer", "playbook_writer", 
                             "test_generator", "dashboard_generator", "risk_control_mapper", 
                             "gap_analysis", "cross_framework_mapper"]:
            return next_agent
        else:
            return "siem_rule_validator"  # Default to validation
    
    workflow.add_conditional_edges(
        "plan_executor",
        route_from_plan_executor,
        {
            "framework_analyzer": "framework_analyzer",
            "detection_engineer": "detection_engineer",
            "playbook_writer": "playbook_writer",
            "test_generator": "test_generator",
            "dashboard_generator": "dashboard_generator",
            "risk_control_mapper": "risk_control_mapper",
            "gap_analysis": "gap_analysis",
            "cross_framework_mapper": "cross_framework_mapper",
            "siem_rule_validator": "siem_rule_validator"
        }
    )
    
    # Framework analyzer always goes to mark_step_complete (it's not a generator that needs validation)
    workflow.add_edge("framework_analyzer", "mark_step_complete")
    
    # Simple nodes go directly to artifact_assembler (no validation needed)
    workflow.add_edge("dashboard_generator", "artifact_assembler")
    workflow.add_edge("risk_control_mapper", "artifact_assembler")
    workflow.add_edge("gap_analysis", "artifact_assembler")
    workflow.add_edge("cross_framework_mapper", "artifact_assembler")
    
    # Generators need conditional routing: normal flow → mark_step_complete, refinement → validation
    def route_from_generator(state: EnhancedCompliancePipelineState) -> str:
        # Check if this is a refinement iteration
        iteration = state.get("iteration_count", 0)
        refinement_history = state.get("refinement_history", [])
        
        # If we're in a refinement iteration (iteration > 0 and have refinement history), go to validation
        if iteration > 0 and refinement_history:
            return "siem_rule_validator"
        else:
            # Normal execution flow, continue with plan
            return "mark_step_complete"
    
    workflow.add_conditional_edges(
        "detection_engineer",
        route_from_generator,
        {
            "siem_rule_validator": "siem_rule_validator",
            "mark_step_complete": "mark_step_complete"
        }
    )
    
    workflow.add_conditional_edges(
        "playbook_writer",
        route_from_generator,
        {
            "siem_rule_validator": "siem_rule_validator",
            "mark_step_complete": "mark_step_complete"
        }
    )
    
    workflow.add_conditional_edges(
        "test_generator",
        route_from_generator,
        {
            "siem_rule_validator": "siem_rule_validator",
            "mark_step_complete": "mark_step_complete"
        }
    )
    
    workflow.add_edge("mark_step_complete", "plan_executor")
    
    # Validation chain
    workflow.add_edge("siem_rule_validator", "playbook_validator")
    workflow.add_edge("playbook_validator", "test_script_validator")
    workflow.add_edge("test_script_validator", "cross_artifact_validator")
    workflow.add_edge("cross_artifact_validator", "chain_validation")
    workflow.add_edge("chain_validation", "feedback_analyzer")
    
    # Feedback analyzer routes based on validation results
    def route_from_feedback_analyzer(state: EnhancedCompliancePipelineState) -> str:
        next_agent = state.get("next_agent")
        if next_agent == "FINISH" or next_agent == "artifact_assembler":
            return "artifact_assembler"
        elif next_agent in ["detection_engineer", "playbook_writer", "test_generator"]:
            return next_agent
        else:
            return "artifact_assembler"
    
    workflow.add_conditional_edges(
        "feedback_analyzer",
        route_from_feedback_analyzer,
        {
            "artifact_assembler": "artifact_assembler",
            "detection_engineer": "detection_engineer",
            "playbook_writer": "playbook_writer",
            "test_generator": "test_generator",
        }
    )
    
    
    # Final assembly
    workflow.add_edge("artifact_assembler", END)
    
    return workflow


def create_compliance_app(checkpointer=None):
    """
    Create and compile the compliance automation application.
    
    Args:
        checkpointer: Optional checkpointer for state persistence.
                     If None, uses MemorySaver (in-memory only).
    
    Returns:
        Compiled LangGraph application ready for invocation
    """
    if checkpointer is None:
        checkpointer = MemorySaver()
    
    workflow = build_compliance_workflow()
    app = workflow.compile(checkpointer=checkpointer)
    
    return app


# Convenience function to get a default app instance
def get_compliance_app():
    """
    Get a default compliance automation app instance.
    
    Returns:
        Compiled LangGraph application with in-memory checkpointer
    """
    return create_compliance_app()


if __name__ == "__main__":
    # Example usage
    app = get_compliance_app()
    print("Compliance automation workflow compiled successfully!")
    print(f"Nodes: {list(app.nodes.keys())}")

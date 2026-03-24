"""
Shared workflow-agnostic nodes and utilities.

These nodes are designed to work with standardized state formats
and should not contain workflow-specific logic.
"""
from .calculation_planner import calculation_planner_node
from .state_normalization import normalize_state_for_calculation_planner
from .tool_integration import (
    get_tools_for_agent,
    create_tool_calling_agent,
    should_use_tool_calling_agent,
    intelligent_retrieval,
)
from .gold_model_plan_generator import (
    GoldModelPlanGenerator,
    GoldModelPlanGeneratorInput,
    GoldModelPlan,
    GoldModelSpecification,
    OutputColumn,
    SilverTableInfo,
    SourceTableColumn,
)
from .cubejs_generation import cubejs_schema_generation_node
from .goal_output_routing import (
    ALL_DELIVERABLES,
    apply_goal_output_routing_to_state,
    normalize_deliverables,
)
from .goal_shared_output_tools import (
    apply_goal_shared_pipeline,
    apply_goal_shared_tools_before_csod_assembly,
    apply_goal_shared_tools_before_dt_assembly,
)
from .unified_output_pre_assembly import (
    apply_shared_dashboard_and_metrics_layout,
    apply_unified_output_pre_assembly,
)
from .demo_sql_insight_agent import (
    apply_demo_sql_insight_agent_to_state,
    collect_demo_sql_agent_context,
    synthesize_demo_outputs,
)

__all__ = [
    "calculation_planner_node",
    "normalize_state_for_calculation_planner",
    # Tool integration
    "get_tools_for_agent",
    "create_tool_calling_agent",
    "should_use_tool_calling_agent",
    "intelligent_retrieval",
    # Gold model plan generator
    "GoldModelPlanGenerator",
    "GoldModelPlanGeneratorInput",
    "GoldModelPlan",
    "GoldModelSpecification",
    "OutputColumn",
    "SilverTableInfo",
    "SourceTableColumn",
    "cubejs_schema_generation_node",
    "ALL_DELIVERABLES",
    "apply_goal_output_routing_to_state",
    "normalize_deliverables",
    "apply_goal_shared_pipeline",
    "apply_goal_shared_tools_before_csod_assembly",
    "apply_goal_shared_tools_before_dt_assembly",
    "apply_shared_dashboard_and_metrics_layout",
    "apply_unified_output_pre_assembly",
    "apply_demo_sql_insight_agent_to_state",
    "collect_demo_sql_agent_context",
    "synthesize_demo_outputs",
]

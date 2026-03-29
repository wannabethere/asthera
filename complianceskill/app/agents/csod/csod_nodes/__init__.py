"""
CSOD LangGraph nodes split by function.

- _helpers: shared LLM / logging utilities
- node_intent: classification
- node_planner: planning (with inlined concept_context + spine_precheck)
- node_mdl_retrieval, node_metrics_retrieval: retrieval spine
- node_scoring: unified metric qualification (merged scoring + decision tree)
- node_causal, node_cross_concept: CCE topology
- node_layout: unified layout resolver (merged dashboard + metrics layout)
- node_recommender, node_insights, node_medallion, node_gold_sql: metrics → gold
- node_dashboard, node_compliance: persona & tests
- node_scheduler, node_output: scheduling & assembly
- node_data_intelligence: discovery, quality, lineage, pipeline planner
"""
from app.agents.csod.csod_nodes._helpers import (
    CSOD_State,
    _csod_log_step,
    _llm_invoke,
    _parse_json_response,
)
from app.agents.csod.csod_nodes.node_intent import csod_intent_classifier_node
from app.agents.csod.csod_nodes.node_planner import csod_planner_node
from app.agents.csod.csod_nodes.node_analysis_planner import csod_analysis_planner_node
from app.agents.csod.csod_nodes.node_mdl_retrieval import csod_mdl_schema_retrieval_node
from app.agents.csod.csod_nodes.node_metrics_retrieval import csod_metrics_retrieval_node
from app.agents.csod.csod_nodes.node_scoring import (
    csod_metric_qualification_node,
    csod_scoring_validator_node,       # backward compat alias
    csod_decision_tree_resolver_node,  # backward compat alias
)
from app.agents.csod.csod_nodes.node_causal import csod_causal_graph_node
from app.agents.csod.csod_nodes.node_cross_concept import csod_cross_concept_check_node
from app.agents.csod.csod_nodes.node_layout import (
    csod_layout_resolver_node,
    csod_dashboard_layout_node,  # backward compat
    csod_metrics_layout_node,    # backward compat
)
from app.agents.csod.csod_nodes.node_recommender import csod_metrics_recommender_node
from app.agents.csod.csod_nodes.node_insights import csod_data_science_insights_enricher_node
from app.agents.csod.csod_nodes.node_medallion import csod_medallion_planner_node
from app.agents.csod.csod_nodes.node_gold_sql import csod_gold_model_sql_generator_node
from app.agents.csod.csod_nodes.node_dashboard import csod_dashboard_generator_node
from app.agents.csod.csod_nodes.node_compliance import csod_compliance_test_generator_node
from app.agents.csod.csod_nodes.node_scheduler import csod_scheduler_node, _validate_sql_query
from app.agents.csod.csod_nodes.node_data_intelligence import (
    csod_data_discovery_node,
    csod_data_lineage_tracer_node,
    csod_data_pipeline_planner_node,
    csod_data_quality_inspector_node,
)
from app.agents.csod.csod_nodes.node_output import csod_output_assembler_node
from app.agents.csod.csod_nodes.node_output_format_selector import csod_output_format_selector_node
from app.agents.csod.csod_nodes.node_completion_narration import csod_completion_narration_node
from app.agents.csod.csod_nodes.node_sql_agent import (
    csod_sql_agent_preview_node,
    csod_sql_agent_adhoc_node,
)

# Deprecated imports — kept for backward compat
from app.agents.csod.csod_nodes.node_concept_context import csod_concept_context_node  # now inlined in planner
from app.agents.csod.csod_nodes.node_spine_precheck import csod_spine_precheck_node    # now inlined in planner

__all__ = [
    "CSOD_State",
    "_csod_log_step",
    "_llm_invoke",
    "_parse_json_response",
    "_validate_sql_query",
    "csod_intent_classifier_node",
    "csod_planner_node",
    "csod_analysis_planner_node",
    "csod_mdl_schema_retrieval_node",
    "csod_metrics_retrieval_node",
    "csod_metric_qualification_node",
    "csod_scoring_validator_node",       # backward compat alias
    "csod_decision_tree_resolver_node",  # backward compat alias
    "csod_causal_graph_node",
    "csod_cross_concept_check_node",
    "csod_layout_resolver_node",
    "csod_dashboard_layout_node",        # backward compat alias
    "csod_metrics_layout_node",          # backward compat alias
    "csod_metrics_recommender_node",
    "csod_data_science_insights_enricher_node",
    "csod_medallion_planner_node",
    "csod_gold_model_sql_generator_node",
    "csod_dashboard_generator_node",
    "csod_compliance_test_generator_node",
    "csod_scheduler_node",
    "csod_output_assembler_node",
    "csod_data_discovery_node",
    "csod_data_quality_inspector_node",
    "csod_data_lineage_tracer_node",
    "csod_data_pipeline_planner_node",
    "csod_output_format_selector_node",
    "csod_completion_narration_node",
    "csod_sql_agent_preview_node",
    "csod_sql_agent_adhoc_node",
    "csod_concept_context_node",         # deprecated — now inlined in planner
    "csod_spine_precheck_node",          # deprecated — now inlined in planner
]

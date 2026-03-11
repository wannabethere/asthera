"""
CSOD Workflow State Schema

Extends EnhancedCompliancePipelineState with fields specific to the
CSOD Metrics, Tables, and KPIs Recommender workflow.
"""
from typing import TypedDict, List, Dict, Optional, Any
from app.agents.state import EnhancedCompliancePipelineState  # noqa: F401  (re-export)


# ============================================================================
# CSOD Workflow State Extension
# ============================================================================

class CSODState(TypedDict, total=False):
    """
    State extensions for the CSOD workflow.
    
    Add to EnhancedCompliancePipelineState or use as a mixin.
    All fields optional (total=False) so existing nodes are unaffected.
    """

    # ──────────────── Intent & Planning ────────────────
    csod_intent: Optional[str]  # "metrics_dashboard_plan" | "metrics_recommender_with_gold_plan" | "dashboard_generation_for_persona" | "compliance_test_generator"
    csod_persona: Optional[str]  # Persona for dashboard generation (e.g., "hr_manager", "learning_admin")
    csod_plan_summary: Optional[str]
    csod_estimated_complexity: Optional[str]  # "simple" | "moderate" | "complex"
    csod_execution_plan: List[Dict[str, Any]]
    csod_gap_notes: List[str]
    csod_data_sources_in_scope: List[str]  # Cornerstone/Workday integrations

    # ──────────────── Retrieved context ────────────────
    csod_resolved_schemas: List[Dict[str, Any]]  # MDL schemas
    csod_gold_standard_tables: List[Dict[str, Any]]  # GoldStandardTables from project meta
    csod_retrieved_metrics: List[Dict[str, Any]]  # Metrics from registry
    csod_retrieved_kpis: List[Dict[str, Any]]  # KPIs from registry

    # ──────────────── Scoring & Validation ────────────────
    csod_scored_context: Optional[Dict[str, Any]]  # {metrics, kpis, schemas, tables}
    csod_dropped_items: List[Dict[str, Any]]
    csod_schema_gaps: List[Dict[str, Any]]
    csod_scoring_threshold_applied: float

    # ──────────────── Metrics Recommender outputs ────────────────
    csod_metric_recommendations: List[Dict[str, Any]]
    csod_kpi_recommendations: List[Dict[str, Any]]
    csod_table_recommendations: List[Dict[str, Any]]
    csod_data_science_insights: List[Dict[str, Any]]  # Data science insights using SQL functions
    csod_medallion_plan: Optional[Dict[str, Any]]  # Gold plan for metrics
    csod_unmeasured_requirements: List[Dict[str, Any]]  # Requirements with no metric coverage

    # ──────────────── Dashboard Generation ────────────────
    csod_dashboard_context: Optional[Dict[str, Any]]
    csod_dashboard_available_tables: List[Dict[str, Any]]
    csod_dashboard_reference_patterns: List[Dict[str, Any]]
    csod_dashboard_clarification_request: Optional[Dict[str, Any]]
    csod_dashboard_clarification_response: Optional[Dict[str, Any]]
    csod_dashboard_candidate_questions: List[Dict[str, Any]]
    csod_dashboard_validated_questions: List[Dict[str, Any]]
    csod_dashboard_validation_status: Optional[str]  # "pass" | "fail" | "pass_with_warnings"
    csod_dashboard_validation_report: Optional[Dict[str, Any]]
    csod_dashboard_user_selections: List[str]
    csod_dashboard_assembled: Optional[Dict[str, Any]]
    csod_dashboard_validation_iteration: int

    # ──────────────── Compliance Test Generator ────────────────
    csod_test_cases: List[Dict[str, Any]]  # SQL-based test cases
    csod_test_queries: List[Dict[str, Any]]  # SQL queries for alerts
    csod_test_validation_passed: bool
    csod_test_validation_failures: List[Dict[str, Any]]

    # ──────────────── Scheduling & Planning ────────────────
    csod_schedule_type: Optional[str]  # "adhoc" | "scheduled" | "recurring"
    csod_schedule_config: Optional[Dict[str, Any]]  # Schedule configuration
    csod_execution_frequency: Optional[str]  # "daily" | "weekly" | "monthly" | "on_demand"

    # ──────────────── Validation tracking ────────────────
    csod_validation_iteration: int
    csod_metric_validation_passed: bool
    csod_metric_validation_failures: List[Dict[str, Any]]
    csod_metric_validation_warnings: List[Dict[str, Any]]

    # ──────────────── Causal Graph ────────────────
    csod_causal_graph_enabled: bool  # Feature flag to enable/disable causal graph
    csod_causal_nodes: List[Dict[str, Any]]  # Retrieved causal nodes
    csod_causal_edges: List[Dict[str, Any]]  # Retrieved causal edges
    csod_causal_graph_metadata: Optional[Dict[str, Any]]  # Graph metadata (node_count, edge_count, etc.)
    csod_causal_retrieval_stats: Optional[Dict[str, Any]]  # Retrieval statistics
    csod_causal_metric_registry: List[Dict[str, Any]]  # Metric registry for query enrichment

    # ──────────────── Final assembled output ────────────────
    csod_assembled_output: Optional[Dict[str, Any]]


# ============================================================================
# Unified standalone state for CSOD workflow
# ============================================================================

class CSODWorkflowState(EnhancedCompliancePipelineState, CSODState, total=False):
    """
    Combined state merging base pipeline state with CSOD-specific additions.
    
    Use this if running the CSOD workflow independently.
    """
    pass

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
    csod_intent: Optional[str]  # Canonical pipeline intent (executors / DT / CCE)
    intent_family: Optional[str]  # metrics_dashboard | analysis | data_ops (pipeline UX family)
    csod_intent_registry_id: Optional[str]  # Lexy/catalog label when distinct (e.g. compliance_gap_close → gap_analysis)
    csod_stage_1_intent: Optional[Dict[str, Any]]  # Lexy stage_1_intent shape for UI / API
    # Lexy causal concept mapping (design §11 stage 2) — domain partition + stage_2 payload
    domain_classification: Optional[Dict[str, Any]]
    active_domains: List[str]
    primary_domain: Optional[str]
    domain_scores: Optional[Dict[str, float]]
    lexy_stage_2_concept_mapping: Optional[Dict[str, Any]]
    csod_dt_seed_decisions: Optional[Dict[str, Any]]
    csod_persona: Optional[str]  # Persona for dashboard generation (e.g., "hr_manager", "learning_admin")
    csod_intent_classifier_output: Optional[Dict[str, Any]]  # Full LLM envelope: narrative, detail, intent_signals, analysis_requirements
    csod_plan_summary: Optional[str]
    csod_estimated_complexity: Optional[str]  # "simple" | "moderate" | "complex"
    csod_execution_plan: List[Dict[str, Any]]
    csod_gap_notes: List[str]
    csod_data_sources_in_scope: List[str]  # Cornerstone/Workday integrations

    # ──────────────── Retrieved context ────────────────
    csod_resolved_schemas: List[Dict[str, Any]]  # MDL schemas
    csod_mdl_retrieved_table_descriptions: Optional[List[Dict[str, Any]]]  # index hits from table_descriptions
    # Post–MDL enrichment: L1 focus alignment, L2 table layer, L3 query specs, DDL edges
    csod_mdl_l1_focus_scope: Optional[Dict[str, Any]]
    csod_mdl_l2_capability_tables: Optional[Dict[str, Any]]
    csod_mdl_l3_retrieval_queries: Optional[Dict[str, Any]]
    csod_mdl_relation_edges: Optional[List[Dict[str, Any]]]
    csod_mdl_needs_focus_clarification: Optional[bool]
    csod_mdl_focus_clarification_message: Optional[str]
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

    # ──────────────── Data Intelligence (data_discovery, data_lineage, data_quality, data_planner) ────────────────
    csod_schema_catalog: List[Dict[str, Any]]
    csod_available_metrics_list: List[Dict[str, Any]]
    csod_data_capability_assessment: Optional[Dict[str, Any]]
    csod_coverage_gaps: List[Dict[str, Any]]
    csod_lineage_graph: Optional[Dict[str, Any]]
    csod_column_level_lineage: Optional[Dict[str, Any]]
    csod_transformation_steps: List[Dict[str, Any]]
    csod_impact_analysis: List[Dict[str, Any]]
    csod_quality_scorecard: Optional[Dict[str, Any]]
    csod_issue_list: List[Dict[str, Any]]
    csod_freshness_report: Optional[Dict[str, Any]]
    csod_ingestion_schedule: List[Dict[str, Any]]
    csod_dbt_model_specs: List[Dict[str, Any]]
    csod_dependency_dag: List[Dict[str, Any]]
    csod_build_complexity: Optional[Dict[str, Any]]

    # ──────────────── Causal Graph (topology; Shapley only inside executor outputs) ────────────────
    csod_causal_graph_enabled: bool
    csod_causal_nodes: List[Dict[str, Any]]
    csod_causal_edges: List[Dict[str, Any]]
    csod_causal_graph_metadata: Optional[Dict[str, Any]]
    csod_causal_graph_result: Optional[Dict[str, Any]]  # graph metadata + counts
    csod_causal_centrality: Optional[Dict[str, Any]]  # metric_id -> {in_degree, out_degree}
    csod_causal_mode: Optional[str]  # required | optional | disabled | varies
    csod_causal_retrieval_stats: Optional[Dict[str, Any]]
    csod_causal_metric_registry: List[Dict[str, Any]]
    # CCE attribution (cce_attribution.py) — same dict as attribution_result
    csod_cce_attribution: Optional[Dict[str, Any]]
    attribution_result: Optional[Dict[str, Any]]
    attribution_method_used: Optional[str]
    advisory_mode: bool
    metric_current_values: Optional[Dict[str, Any]]
    metric_observations: List[Dict[str, Any]]
    metric_time_series_available: bool
    requires_audit_evidence: bool
    deadline_days: Optional[int]
    causal_graph: Optional[Dict[str, Any]]
    causal_proposed_nodes: List[Dict[str, Any]]
    causal_graph_metadata: Optional[Dict[str, Any]]

    # ──────────────── Output format selection (post-metrics refinement) ────────────────
    csod_selected_layout: Optional[Dict[str, Any]]  # {template_id, template_name, layout_structure, reasoning}

    # ──────────────── Final assembled output ────────────────
    csod_assembled_output: Optional[Dict[str, Any]]

    # ──────────────── Completion narration (ChatGPT-style summary) ────────────────
    csod_completion_narration: Optional[str]  # Markdown prose summarising the Q&A
    
    # ──────────────── Conversation Planner (Phase 0) ────────────────
    # Datasource selection
    csod_selected_datasource: Optional[str]
    csod_available_datasources: List[Dict[str, str]]
    csod_datasource_confirmed: bool
    
    # Concept resolution
    csod_concept_matches: List[Dict[str, Any]]
    csod_selected_concepts: List[Dict[str, Any]]
    csod_confirmed_concept_ids: List[str]
    csod_resolved_project_ids: List[str]
    csod_resolved_mdl_table_refs: List[str]
    csod_primary_project_id: Optional[str]
    
    # Preliminary area matching (for scoping)
    csod_preliminary_area_matches: List[Dict[str, Any]]
    
    # Scoping
    csod_scoping_answers: Dict[str, Any]  # Maps state_key -> user's answer
    csod_scoping_complete: bool
    
    # Area matching (with scoping context)
    csod_area_matches: List[Dict[str, Any]]
    csod_primary_area: Dict[str, Any]
    csod_confirmed_area_id: Optional[str]
    csod_area_confirmation: Optional[Dict[str, Any]]
    
    # Metric narration
    csod_metric_narration: Optional[str]
    csod_metric_narration_confirmed: bool
    
    # Conversation checkpoint
    csod_conversation_checkpoint: Optional[Dict[str, Any]]  # ConversationCheckpoint as dict
    csod_checkpoint_resolved: bool
    
    # Checkpoint responses - stores user responses to checkpoints by phase
    # Format: {"datasource_select": {...}, "concept_select": {...}, ...}
    # This allows nodes to check if a checkpoint was already responded to
    # without relying on checkpoint state preservation
    csod_checkpoint_responses: Dict[str, Dict[str, Any]]
    
    # Workflow routing (legacy state may still carry csod_metric_advisor_workflow; integration normalizes to csod_workflow)
    csod_target_workflow: Optional[str]
    csod_use_advisor_workflow: bool  # legacy; conversation router no longer branches on this

    # Planner narrator (streaming thinking)
    csod_node_output: Optional[Dict[str, Any]]  # Written by each narrator-aware node. Shape: {node, status, findings, next}. Not persisted across turns.
    csod_reasoning_narrative: List[Dict[str, Any]]  # Accumulated narrator text per node. Each entry: {node: str, text: str}. Persisted across checkpoint turns.
    # UI reasoning timeline: preanalysis S1–S3 + ordered agent_pipeline (see reasoning_trace.py; HITL via apply_hitl_patch)
    csod_reasoning_trace: Optional[Dict[str, Any]]

    # Conversational analysis flows (csod_data_analysis_conversations.md)
    csod_session_turn: int  # 1 = first message; >1 enables follow-up router
    csod_narrative_stream: List[Dict[str, Any]]  # {ts, phase, title, message, meta}
    csod_narrative_preview: Optional[str]  # Planner one-liner before executors
    csod_follow_up_eligible: bool  # After full spine, true if direct follow-up possible
    csod_followup_graph_route: Optional[str]  # set by follow-up router → next node id
    csod_followup_executor_id: Optional[str]
    csod_dt_layout: Optional[Dict[str, Any]]  # dashboard_layout_resolver
    csod_metrics_layout: Optional[Dict[str, Any]]  # metrics_layout_resolver
    csod_followup_analysis_result: Optional[Dict[str, Any]]  # direct analytical executor output
    
    # ──────────────── Skill Pipeline (enhancement layer) ────────────────
    skill_pipeline_enabled: bool  # Feature flag — when False, skill nodes are pass-through
    skill_context: Optional[Dict[str, Any]]  # Phase 1: skill match + extracted params
    skill_data_plan: Optional[Dict[str, Any]]  # Phase 2: data plan (metrics, KPIs, transformations)
    skill_recommender_context: Optional[Dict[str, Any]]  # Phase 3: injected recommender instructions
    skill_validated_metrics: Optional[List[Dict[str, Any]]]  # Phase 4: post-validation filtered metrics
    skill_validation_report: Optional[Dict[str, Any]]  # Phase 4: validation report (kept/dropped/warnings)

    # ──────────────── Interactive Checkpoints (conversation mode) ────────────────
    csod_interactive_checkpoints: bool  # When True, metric_selection and goal_intent emit checkpoints
    csod_selected_metric_ids: Optional[List[str]]  # User-selected metric IDs (from checkpoint)
    csod_metrics_user_confirmed: bool  # True after user confirms metric selection

    # Legacy fields (to be removed)
    csod_planner_checkpoint: Optional[Dict[str, Any]]  # DEPRECATED - use csod_conversation_checkpoint
    csod_generate_area_confirmation: bool  # DEPRECATED - always generate now


# ============================================================================
# Unified standalone state for CSOD workflow
# ============================================================================

class CSODWorkflowState(EnhancedCompliancePipelineState, CSODState, total=False):
    """
    Combined state merging base pipeline state with CSOD-specific additions.
    
    Use this if running the CSOD workflow independently.
    """
    pass

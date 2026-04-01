"""
Enhanced Compliance Pipeline State Schema

Defines the state structure for the LangGraph workflow with planning,
validation, and iterative refinement capabilities.
"""
from typing import TypedDict, List, Dict, Optional, Any, Literal, Annotated
from datetime import datetime
from dataclasses import dataclass, field
from langchain_core.messages import BaseMessage
from operator import add


def merge_csod_scoping_answers(
    left: Optional[Dict[str, Any]],
    right: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Merge scoping answers across turns so partial checkpoint replies accumulate."""
    acc = dict(left) if isinstance(left, dict) else {}
    if right is None:
        return acc
    if isinstance(right, dict):
        acc = {**acc, **right}
    return acc


# ============================================================================
# Plan Step Data Structure
# ============================================================================

@dataclass
class PlanStep:
    """Single atomic step in the execution plan."""
    step_id: str
    description: str
    required_data: List[str]  # What context is needed
    retrieval_queries: List[str]  # Semantic search queries
    agent: str  # Which agent executes this
    dependencies: List[str]  # step_ids that must complete first
    status: Literal["pending", "in_progress", "completed", "failed"] = "pending"
    context: Dict = field(default_factory=dict)  # Retrieved data for this step
    output: Optional[Dict] = None


# ============================================================================
# Validation Result Data Structure
# ============================================================================

@dataclass
class ValidationResult:
    """Result from a validation agent."""
    artifact_type: str  # "siem_rule" | "playbook" | "test_script" | "data_pipeline"
    artifact_id: str
    passed: bool
    confidence_score: float  # 0.0 - 1.0
    issues: List[Dict]  # [{severity: "error|warning", message: str, location: str}]
    suggestions: List[str]  # Specific fixes to apply
    validation_timestamp: datetime


# ============================================================================
# Enhanced Compliance Pipeline State
# ============================================================================

class EnhancedCompliancePipelineState(TypedDict, total=False):
    """Extended state with planning and validation."""
    
    # ========== Original fields ==========
    user_query: str
    intent: Optional[str]
    framework_id: Optional[str]
    requirement_id: Optional[str]
    requirement_code: Optional[str]
    requirement_name: Optional[str]
    requirement_description: Optional[str]
    
    controls: List[Dict]
    risks: List[Dict]
    scenarios: List[Dict]
    test_cases: List[Dict]
    
    siem_rules: List[Dict]
    playbooks: List[Dict]
    test_scripts: List[Dict]
    data_pipelines: List[Dict]
    dashboards: List[Dict]
    vulnerability_mappings: List[Dict]
    gap_analysis_results: List[Dict]
    cross_framework_mappings: List[Dict]
    metrics_context: List[Dict]
    xsoar_indicators: List[Dict]
    
    messages: Annotated[List[BaseMessage], add]
    next_agent: Optional[str]
    session_id: str
    created_at: datetime
    updated_at: datetime
    error: Optional[str]
    
    # ========== Planning fields ==========
    execution_plan: Optional[List[PlanStep]]  # The multi-step plan
    current_step_index: int  # Which step we're executing
    plan_completion_status: Dict[str, str]  # {step_id: "completed|failed"}
    
    # ========== Validation fields ==========
    validation_results: List[ValidationResult]
    validation_passed: bool
    iteration_count: int  # Track refinement loops
    max_iterations: int  # Prevent infinite loops
    
    # ========== Feedback loop ==========
    refinement_history: List[Dict]  # Track what was regenerated and why
    quality_score: Optional[float]  # Overall artifact quality 0-100
    
    # ========== Context cache ==========
    context_cache: Dict[str, Any]  # Cache retrieved data per step
    
    # ========== LLM response tracking (for validation/review) ==========
    llm_response: Optional[str]  # Raw LLM response content
    llm_prompt: Optional[Dict[str, str]]  # Prompt sent to LLM (system + human)
    
    # ========== Step-by-step execution logging (JSON output) ==========
    execution_steps: List[Dict[str, Any]]  # List of all agent execution steps with inputs/outputs
    
    # ========== Data Enrichment fields (from intent classifier) ==========
    data_enrichment: Optional[Dict[str, Any]]  # {
    #   needs_mdl: bool,
    #   needs_metrics: bool,
    #   needs_xsoar_dashboard: bool,
    #   suggested_focus_areas: List[str],
    #   metrics_intent: str  # "current_state" | "trend" | "benchmark" | "gap"
    # }
    
    # ========== Resolved metrics (from metrics recommender) ==========
    resolved_metrics: List[Dict[str, Any]]  # List of resolved metrics with source_schemas, kpis, trends, etc.
    
    # ========== Tenant profile and data source selection ==========
    compliance_profile: Optional[Dict[str, Any]]  # {
    #   framework: "soc2_type2",
    #   vendor_capabilities: ["endpoint_detection", "log_management", "identity"],
    #   data_sources: ["qualys", "snyk", "wiz"],
    #   tenant_field_mappings: {...}
    # }
    selected_data_sources: List[str]  # Data sources selected from tenant profile (e.g., ["qualys", "snyk"])
    resolved_focus_areas: List[Dict[str, Any]]  # Focus areas resolved from static catalog
    focus_area_categories: List[str]  # Category strings for filtering (e.g., ["vulnerabilities", "access_control"])
    
    # ========== Calculation plan (from calculation planner) ==========
    calculation_plan: Optional[Dict[str, Any]]  # {
    #   field_instructions: [...],
    #   metric_instructions: [...],
    #   silver_time_series_suggestion: {...},
    #   reasoning: "..."
    # }
    
    # ========== Detection & Triage workflow fields ==========
    active_project_id: Optional[str]  # ProjectId for GoldStandardTable lookup
    dt_plan_summary: Optional[str]
    dt_estimated_complexity: Optional[str]  # "simple" | "moderate" | "complex"
    dt_playbook_template: Optional[str]  # "A" | "B" | "C"
    dt_playbook_template_sections: List[str]
    dt_expected_outputs: Optional[Dict[str, bool]]  # {"siem_rules": bool, "metric_recommendations": bool, ...}
    dt_gap_notes: List[str]  # sources omitted because not configured
    dt_data_sources_in_scope: List[str]  # confirmed sources used in this plan
    dt_retrieved_controls: List[Dict[str, Any]]  # with relevance_score from vector search
    dt_retrieved_risks: List[Dict[str, Any]]
    dt_retrieved_scenarios: List[Dict[str, Any]]
    dt_resolved_schemas: List[Dict[str, Any]]  # MDL schemas from direct name lookup
    dt_mdl_retrieved_table_descriptions: Optional[List[Dict[str, Any]]]
    dt_mdl_l1_focus_scope: Optional[Dict[str, Any]]
    dt_mdl_l2_capability_tables: Optional[Dict[str, Any]]
    dt_mdl_l3_retrieval_queries: Optional[Dict[str, Any]]
    dt_mdl_relation_edges: Optional[List[Dict[str, Any]]]
    dt_mdl_needs_focus_clarification: Optional[bool]
    dt_mdl_focus_clarification_message: Optional[str]
    dt_gold_standard_tables: List[Dict[str, Any]]  # GoldStandardTables from project meta
    dt_scored_context: Optional[Dict[str, Any]]  # {controls, risks, scenarios, scored_metrics, resolved_schemas}
    dt_dropped_items: List[Dict[str, Any]]  # items dropped with score < 0.5
    dt_schema_gaps: List[Dict[str, Any]]  # metrics with missing schema names
    dt_scoring_threshold_applied: float  # actual threshold used (may lower for fallback)
    dt_rule_gaps: List[Dict[str, Any]]  # scenarios skipped (missing log source)
    dt_coverage_summary: Optional[Dict[str, Any]]  # {scenarios_covered, controls_addressed, ...}
    dt_medallion_plan: Optional[Dict[str, Any]]  # {project_id, entries: [...]}
    dt_metric_recommendations: List[Dict[str, Any]]
    dt_unmeasured_controls: List[Dict[str, Any]]  # controls with no metric coverage
    dt_siem_validation_passed: bool
    dt_siem_validation_failures: List[Dict[str, Any]]
    dt_metric_validation_passed: bool
    dt_metric_validation_failures: List[Dict[str, Any]]  # critical failures from metric validator
    dt_metric_validation_warnings: List[Dict[str, Any]]  # warnings (non-blocking)
    dt_metric_validation_rule_summary: Optional[Dict[str, str]]
    dt_validation_iteration: int  # current refinement iteration (0-indexed)
    dt_assembled_playbook: Optional[Dict[str, Any]]
    # UI reasoning timeline (preanalysis + agent_pipeline; see mdlworkflows/dt_reasoning_trace.py)
    dt_reasoning_trace: Optional[Dict[str, Any]]
    
    # Medallion / SQL pipeline flags
    silver_gold_tables_only: bool  # Set to True to skip source/bronze tables, only use silver and gold
    dt_generate_sql: bool  # Set to True to generate SQL for gold models (dbt-compatible)
    dt_generated_gold_model_sql: List[Dict[str, Any]]  # Generated SQL models (populated if dt_generate_sql=True)
    dt_gold_model_artifact_name: Optional[str]  # Artifact name for generated SQL models
    dt_data_science_insights: List[Dict[str, Any]]
    dt_demo_sql_agent_context: Optional[Dict[str, Any]]
    dt_demo_sql_result_sets: Optional[List[Dict[str, Any]]]
    dt_demo_sql_insights_synthetic: Optional[bool]
    dt_assembler_goal_actions: List[str]
    unified_pre_assembly_actions: List[str]
    shared_per_metric_demo_artifacts: List[Dict[str, Any]]
    shared_per_metric_artifact_stubs: List[Dict[str, Any]]
    goal_metric_definitions: List[Dict[str, Any]]  # Planner format: metric definitions without table mapping
    goal_metrics: List[Dict[str, Any]]  # Planner format: metrics with table mapping
    planner_siem_rules: List[Dict[str, Any]]  # Planner format: SIEM rules
    planner_metric_recommendations: List[Dict[str, Any]]  # Planner format: metric recommendations
    planner_execution_plan: Dict[str, Any]  # Planner format: execution plan
    planner_medallion_plan: Dict[str, Any]  # Planner format: medallion plan

    # ========== CSOD planner (Phase 0) — must be declared for LangGraph channels & checkpointer ==========
    # Cross-turn checkpoint resume (graph_input + restore)
    csod_checkpoint_responses: Optional[Dict[str, Any]]
    # Concept resolution
    csod_concept_matches: Optional[List[Dict[str, Any]]]
    csod_selected_concepts: Optional[List[Dict[str, Any]]]
    csod_confirmed_concept_ids: Optional[List[str]]
    csod_concepts_confirmed: Optional[bool]
    # Datasource
    csod_selected_datasource: Optional[str]
    csod_datasource_confirmed: Optional[bool]
    csod_available_datasources: Optional[List[Dict[str, Any]]]
    # Scoping (merged across invoke turns — required for multi-step scoping checkpoints)
    csod_scoping_answers: Annotated[Optional[Dict[str, Any]], merge_csod_scoping_answers]
    csod_scoping_complete: Optional[bool]
    # Skill identification
    csod_primary_skill: Optional[str]
    csod_identified_skills: Optional[List[str]]
    csod_skill_reasoning: Optional[str]
    # Area matching
    csod_area_matches: Optional[List[Dict[str, Any]]]
    csod_primary_area: Optional[Dict[str, Any]]
    csod_confirmed_area_id: Optional[str]
    csod_area_confirmation: Optional[Dict[str, Any]]
    # LLM-resolved concept→area cache (populated by concept_resolver_node, read by area_matcher_node)
    csod_llm_resolved_areas: Optional[Dict[str, Any]]
    # Conversation interrupt mechanism — MUST be in schema so LangGraph preserves them through state merges
    csod_conversation_checkpoint: Optional[Dict[str, Any]]
    csod_checkpoint_resolved: Optional[bool]
    # Interactive checkpoints flag — when True, metric_selection and goal_intent nodes
    # emit checkpoints for user confirmation instead of auto-confirming.
    # MUST be in EnhancedCompliancePipelineState (not just CSODState) so the Phase 1
    # graph (which uses this state schema) preserves it through LangGraph state merges.
    csod_interactive_checkpoints: Optional[bool]
    csod_selected_metric_ids: Optional[List[str]]
    csod_metrics_user_confirmed: Optional[bool]
    # Metric narration — MUST be declared so LangGraph preserves the confirmed flag through state merges
    csod_metric_narration: Optional[str]
    csod_metric_narration_confirmed: Optional[bool]
    # Preliminary area matching (lightweight pre-scoping pass)
    csod_preliminary_area_matches: Optional[List[Dict[str, Any]]]
    # Cross-concept enrichment — MUST be declared for LangGraph channel preservation
    csod_cross_concept_confirmed: Optional[bool]
    csod_cross_concept_areas: Optional[List[Dict[str, Any]]]
    csod_additional_area_ids: Optional[List[str]]
    # Planner chain flag
    csod_from_planner_chain: Optional[bool]
    # Planner completion → chain trigger (read by _extract_workflow_metadata → invocation service)
    is_planner_output: Optional[bool]
    next_agent_id: Optional[str]
    # Follow-up routing (set by csod_followup_router_node for metric augmentation)
    csod_followup_short_circuit: Optional[bool]
    csod_followup_executor_id: Optional[str]
    csod_followup_graph_route: Optional[str]
    # Metric augmentation mode (follow-up "add X" requests)
    csod_augment_mode: Optional[bool]
    csod_metric_augmentation_request: Optional[str]
    csod_augmented_metrics: Optional[List[Dict[str, Any]]]
    csod_augmented_metric_candidates: Optional[List[Dict[str, Any]]]
    # Project / MDL resolution
    csod_resolved_project_ids: Optional[List[str]]
    csod_resolved_mdl_table_refs: Optional[List[str]]
    csod_primary_project_id: Optional[str]
    # Routing output
    csod_target_workflow: Optional[str]
    csod_intent: Optional[str]
    # Planner checkpoint (in-turn signalling; routing reads this)
    csod_planner_checkpoint: Optional[Dict[str, Any]]
    # Narrator
    csod_node_output: Optional[Dict[str, Any]]
    csod_reasoning_narrative: Optional[List[Dict[str, Any]]]
    # Gold SQL generation flag (CSOD graph; also set from shared goal routing)
    csod_generate_sql: Optional[bool]
    # Demo synthetic SQL/insights (DEMO_FAKE_SQL_AND_INSIGHTS; see demo_sql_insight_agent)
    csod_demo_sql_agent_context: Optional[Dict[str, Any]]
    csod_demo_sql_result_sets: Optional[List[Dict[str, Any]]]
    csod_demo_sql_insights_synthetic: Optional[bool]
    # Conversation → shared pipelines: what the user wants and refined deliverables
    goal_intent: Optional[str]
    goal_output_intents: List[str]
    goal_output_classifier_result: Optional[Dict[str, Any]]

    # ========== CubeJS schema generation (shared by CSOD + DT) ==========
    output_format: Optional[str]  # "cubejs" to enable cube generation; skip node if not cubejs
    cubejs_schema_files: List[Dict[str, Any]]  # [{cube_name, filename, content, source_tables, measures, dimensions}]
    cubejs_generation_errors: List[str]  # Per-file errors captured during generation

    # ========== Schema-grounded analysis plan ==========
    csod_analysis_plan: Optional[Dict[str, Any]]        # Step-by-step analysis plan grounded in resolved schemas
    csod_resolved_schemas_pruned: Optional[List[Dict]]   # Schemas pruned to only plan-referenced columns

    # ========== Post-metrics layout refinement ==========
    csod_selected_layout: Optional[Dict[str, Any]]  # {template_id, template_name, layout_structure, reasoning}

    # ========== Completion narration ==========
    csod_completion_narration: Optional[str]  # Markdown prose summary after output assembly
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
    
    # LEEN integration flags
    is_leen_request: bool  # Set to True when request comes from leen
    silver_gold_tables_only: bool  # Set to True to skip source/bronze tables, only use silver and gold
    dt_generate_sql: bool  # Set to True to generate SQL for gold models (dbt-compatible)
    dt_generated_gold_model_sql: List[Dict[str, Any]]  # Generated SQL models (populated if dt_generate_sql=True)
    dt_gold_model_artifact_name: Optional[str]  # Artifact name for generated SQL models
    goal_metric_definitions: List[Dict[str, Any]]  # Planner format: metric definitions without table mapping
    goal_metrics: List[Dict[str, Any]]  # Planner format: metrics with table mapping
    planner_siem_rules: List[Dict[str, Any]]  # Planner format: SIEM rules
    planner_metric_recommendations: List[Dict[str, Any]]  # Planner format: metric recommendations
    planner_execution_plan: Dict[str, Any]  # Planner format: execution plan
    planner_medallion_plan: Dict[str, Any]  # Planner format: medallion plan
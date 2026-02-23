"""
Detection & Triage Workflow State Schema

Extends EnhancedCompliancePipelineState with fields specific to the
Detection & Triage Engineering workflow.

These additions are designed to be merged into state.py or imported as a
TypedDict extension. All new fields follow the optional pattern (total=False)
so existing workflows are unaffected.
"""
from typing import TypedDict, List, Dict, Optional, Any
from app.agents.state import EnhancedCompliancePipelineState  # noqa: F401  (re-export)


# ============================================================================
# Detection & Triage Workflow State Extension
# ============================================================================

class DetectionTriageState(TypedDict, total=False):
    """
    State extensions for the Detection & Triage workflow.

    Add to EnhancedCompliancePipelineState or use as a mixin.
    All fields optional (total=False) so existing nodes are unaffected.

    MANUAL STEP: Merge these fields into EnhancedCompliancePipelineState in
    app/agents/state.py to enable the unified state object. Alternatively,
    DetectionTriageWorkflowState (below) can be used as a standalone state.
    """

    # ──────────────── Planner outputs ────────────────
    dt_plan_summary: Optional[str]
    dt_estimated_complexity: Optional[str]         # "simple" | "moderate" | "complex"
    dt_playbook_template: Optional[str]            # "A" | "B" | "C"
    dt_playbook_template_sections: List[str]
    dt_expected_outputs: Optional[Dict[str, bool]] # {"siem_rules": bool, "metric_recommendations": bool, ...}
    dt_gap_notes: List[str]                        # sources omitted because not configured
    dt_data_sources_in_scope: List[str]            # confirmed sources used in this plan

    # ──────────────── Retrieved framework context ────────────────
    dt_retrieved_controls: List[Dict[str, Any]]    # with relevance_score from vector search
    dt_retrieved_risks: List[Dict[str, Any]]
    dt_retrieved_scenarios: List[Dict[str, Any]]

    # ──────────────── Retrieved metrics & schemas ────────────────
    # dt_resolved_metrics already exists as resolved_metrics in base state
    dt_resolved_schemas: List[Dict[str, Any]]      # MDL schemas from direct name lookup
    dt_gold_standard_tables: List[Dict[str, Any]]  # GoldStandardTables from project meta

    # ──────────────── Scoring validator outputs ────────────────
    dt_scored_context: Optional[Dict[str, Any]]    # {controls, risks, scenarios, scored_metrics, resolved_schemas}
    dt_dropped_items: List[Dict[str, Any]]         # items dropped with score < 0.5
    dt_schema_gaps: List[Dict[str, Any]]           # metrics with missing schema names
    dt_scoring_threshold_applied: float            # actual threshold used (may lower for fallback)

    # ──────────────── Detection engineer outputs ────────────────
    # dt_siem_rules re-uses existing siem_rules field in base state
    dt_rule_gaps: List[Dict[str, Any]]             # scenarios skipped (missing log source)
    dt_coverage_summary: Optional[Dict[str, Any]]  # {scenarios_covered, controls_addressed, ...}

    # ──────────────── Triage engineer outputs ────────────────
    dt_medallion_plan: Optional[Dict[str, Any]]    # {project_id, entries: [...]}
    dt_metric_recommendations: List[Dict[str, Any]]
    dt_unmeasured_controls: List[Dict[str, Any]]   # controls with no metric coverage

    # ──────────────── Validation tracking ────────────────
    dt_siem_validation_passed: bool
    dt_siem_validation_failures: List[Dict[str, Any]]
    dt_metric_validation_passed: bool
    dt_metric_validation_failures: List[Dict[str, Any]]  # critical failures from metric validator
    dt_metric_validation_warnings: List[Dict[str, Any]]  # warnings (non-blocking)
    dt_metric_validation_rule_summary: Optional[Dict[str, str]]
    dt_validation_iteration: int                   # current refinement iteration (0-indexed)

    # ──────────────── Final assembled playbook ────────────────
    dt_assembled_playbook: Optional[Dict[str, Any]]


# ============================================================================
# Unified standalone state for DT workflow
# ============================================================================

class DetectionTriageWorkflowState(EnhancedCompliancePipelineState, DetectionTriageState, total=False):
    """
    Combined state merging base pipeline state with DT-specific additions.

    Use this if running the DT workflow independently rather than as part of
    the main compliance pipeline.

    Example invocation:
        initial_state: DetectionTriageWorkflowState = {
            "user_query": "Build HIPAA breach detection...",
            "messages": [],
            "session_id": str(uuid.uuid4()),
            "controls": [],
            "risks": [],
            "scenarios": [],
            "siem_rules": [],
            "dt_retrieved_controls": [],
            "dt_retrieved_risks": [],
            "dt_retrieved_scenarios": [],
            "dt_resolved_schemas": [],
            "dt_gold_standard_tables": [],
            "dt_dropped_items": [],
            "dt_schema_gaps": [],
            "dt_gap_notes": [],
            "dt_data_sources_in_scope": [],
            "dt_rule_gaps": [],
            "dt_metric_recommendations": [],
            "dt_unmeasured_controls": [],
            "dt_siem_validation_failures": [],
            "dt_metric_validation_failures": [],
            "dt_metric_validation_warnings": [],
            "dt_playbook_template_sections": [],
            "dt_validation_iteration": 0,
        }
    """
    pass

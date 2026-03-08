"""
CCE Layout Advisor Agent — State Schema
========================================
Position in pipeline:
  Upstream Agents (metrics, KPIs, tables, visuals)
    → THIS AGENT (layout definition via conversation)
      → Downstream Renderer (actual HTML/React generation)

State flows through LangGraph nodes accumulating decisions
until a final layout_spec JSON is produced.
"""

from __future__ import annotations
from typing import TypedDict, Literal, Optional, Annotated
from dataclasses import dataclass, field
from enum import Enum
import operator


# ── Upstream Context (from prior agents in pipeline) ──────────────────

class UpstreamContext(TypedDict, total=False):
    """What the upstream metric/KPI/visual agents have already resolved."""
    use_case: str                     # e.g. "SOC2 monitoring", "training compliance"
    data_sources: list[str]           # e.g. ["siem", "cornerstone", "workday"]
    persona: str                      # e.g. "SOC Analyst", "CISO"
    metrics: list[dict]               # [{name, type, source_table}, ...]
    kpis: list[dict]                  # [{label, value_expr, threshold}, ...]
    tables: list[dict]                # [{name, schema, row_count}, ...]
    visuals: list[dict]               # [{type: "line_chart", metric, ...}, ...]
    has_chat_requirement: bool
    kpi_count: int
    framework: str                    # "SOC2", "HIPAA", "NIST AI RMF"
    use_case_group: str               # if upstream already resolved it
    control_ids: list[str]            # e.g. ["CC7"] for compliance-first entry
    goal_statement: str               # freeform goal from UI
    # Goal-driven pipeline: metrics + gold models from upstream agents
    metric_recommendations: list[dict]  # [{id, name, widget_type, kpi_value_type, ...}, ...]
    gold_model_sql: list[dict]          # [{name, sql_query, expected_columns, ...}, ...]
    output_format: str                 # "echarts" | "powerbi" | "other" — target renderer


# ── Decision Accumulator ─────────────────────────────────────────────

class Decisions(TypedDict, total=False):
    """Accumulated decisions from the conversation."""
    category: list[str]       # ["compliance", "grc"]
    domain: str               # "security" | "cornerstone" | "workday" | "hybrid" | "data_ops"
    theme: str                # "dark" | "light"
    complexity: str           # "low" | "medium" | "high"
    has_chat: bool
    strip_cells: int          # 0, 4, 6, 8
    # Dashboard decision tree (7-question flow from dashboard_decision_tree.md)
    destination_type: str     # "embedded" | "powerbi" | "simple" | "slack_digest" | "api_json"
    interaction_mode: str     # "drill_down" | "read_only" | "real_time" | "scheduled_report"
    metric_profile: str       # "count_heavy" | "trend_heavy" | "rate_percentage" | "mixed" | "scorecard"
    focus_area: str           # e.g. "vulnerability_management", "training_completion"
    audience: str             # e.g. "security_ops", "compliance_team"
    registry_target: str      # "dashboard_registry" | "ld_templates_registry" | "both"


# ── Conversation Message ─────────────────────────────────────────────

class Message(TypedDict):
    role: Literal["agent", "user", "system"]
    content: str
    metadata: dict  # optional: step_id, auto_resolved, decision_applied


# ── Agent Phase Enum ─────────────────────────────────────────────────

class Phase(str, Enum):
    INTAKE = "intake"                      # receive upstream context
    DECISION_INTENT = "decision_intent"    # ask purpose
    DECISION_SYSTEMS = "decision_systems"  # ask systems
    DECISION_AUDIENCE = "decision_audience" # ask audience
    DECISION_CHAT = "decision_chat"        # ask AI chat
    DECISION_KPIS = "decision_kpis"        # ask KPI count
    BIND = "bind"                          # registry join, no user input
    SCORING = "scoring"                    # score templates (legacy, maps to score)
    SCORE = "score"                        # template + chart scoring, no user input
    RECOMMENDATION = "recommendation"      # present top 3 (legacy)
    RECOMMEND = "recommend"                # assemble options for human
    SELECTION = "selection"                # user picks (legacy)
    DATA_TABLES = "data_tables"            # human asks to add data tables (hitl)
    CUSTOMIZATION = "customization"        # optional tweaks (legacy)
    VERIFY = "verify"                      # human approval gate
    VERIFY_ADJUST = "verify_adjust"        # human applied an adjustment handle
    VERIFY_RERUN = "verify_rerun"          # partial pipeline re-run requested
    SPEC_GENERATION = "spec_generation"    # build final spec
    COMPLETE = "complete"                  # done


class ResolutionPayload(TypedDict, total=False):
    """Output of BIND stage — fully joined registry context."""
    resolved_metric_groups: dict          # {required: [...], optional_included: [...]}
    control_anchors: list                # [{id, domain, focus, risk_categories}, ...]
    focus_areas: list[str]
    risk_categories: list[str]
    timeframe: str                        # "daily" | "monthly" | "quarterly"
    audience: str
    complexity: str
    # When upstream provides metric_recommendations + gold_model_sql
    metric_recommendations: list         # from upstream — [{id, name, widget_type, ...}, ...]
    gold_model_sql: list                 # from upstream — [{name, sql_query, expected_columns}, ...]
    metric_to_gold_map: dict              # {metric_id: gold_table_name} — BIND join
    # Dashboard decision tree outputs
    destination_type: str
    interaction_mode: str
    metric_profile: str
    registry_target: str


class ScoredCandidate(TypedDict, total=False):
    """Output of SCORE stage — one ranked template option."""
    template_id: str
    name: str
    score: int
    coverage_gaps: list
    coverage_pct: float
    reasons: list
    chart_candidates: dict
    adjustment_handles: list


class AdjustmentHandle(TypedDict, total=False):
    """A named, pre-computed modification the human can apply at VERIFY."""
    id: str
    label: str
    description: str
    re_triggers: str
    delta: dict


class PipelineAudit(TypedDict, total=False):
    """Immutable audit trail written when spec is committed."""
    resolve_path: str
    bind_control_count: int
    score_candidates_evaluated: int
    recommend_options_presented: int
    verify_adjustments_applied: int
    verify_options_switched: int
    verify_rescore_count: int
    approved_by: str
    approved_at: str


# ── Graph State ──────────────────────────────────────────────────────

class LayoutAdvisorState(TypedDict):
    """Full state for the Layout Advisor LangGraph."""
    
    # Pipeline context
    upstream_context: UpstreamContext
    agent_config: dict                     # LayoutAdvisorConfig.to_dict()
    
    # Conversation
    messages: Annotated[list[Message], operator.add]
    
    # Agent progress
    phase: Phase
    decisions: Decisions
    auto_resolved: dict          # which decisions were auto-filled from upstream
    
    # RESOLVE output
    use_case_group: str
    framework: list
    resolution_confidence: float
    
    # BIND output
    resolution_payload: dict     # ResolutionPayload
    
    # Template scoring
    candidate_templates: list[dict]   # [{template_id, score, reasons}, ...] (legacy)
    scored_candidates: list           # list[ScoredCandidate] — replaces candidate_templates
    recommended_top3: list[dict]      # top 3 from scoring (now ScoredCandidates)
    
    # RECOMMEND output
    adjustment_handles: list          # list[AdjustmentHandle]
    recommend_rationale: list         # [{option_idx, rationale, coverage_map}]
    
    # VERIFY state
    spec_status: str                 # "pending_approval" | "approved" | "rejected"
    verify_decision: str             # "approve" | "adjust" | "switch" | "rescore" | "reject"
    selected_option_idx: int         # which of top-3 is active (0=primary)
    adjustments_applied: list[str]   # handle IDs applied this session
    
    # Selection & customization (legacy)
    selected_template_id: str
    customization_requests: list[str]
    
    # Output
    layout_spec: dict            # final JSON spec for downstream renderer
    output_format: str           # "echarts" | "powerbi" | "other" — target renderer
    metric_gold_model_bindings: list  # [{metric_id, gold_table, chart_type}, ...]
    user_added_tables: list     # tables added via data-tables hitl [{table_id, name, ...}, ...]
    
    # Post-VERIFY
    compliance_context: dict
    pipeline_audit: dict         # PipelineAudit

    # Vector store retrieval outputs (written by retrieve_context_node)
    retrieved_metric_context: list  # RETRIEVAL POINT 2 — metric_catalog collection
    retrieved_past_specs: list      # RETRIEVAL POINT 3 — past_layout_specs collection
    
    # Control
    needs_user_input: bool       # pause graph for human-in-the-loop
    user_response: str           # latest user message
    error: str

"""
CCE Dashboard Enricher — Data Models
======================================
Pydantic models for all enriched entities produced by the enricher pipeline.
Used for validation, serialisation, and as the schema contract between stages.
"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


# ── Enums ─────────────────────────────────────────────────────────────

class DestinationType(str, Enum):
    EMBEDDED   = "embedded"
    POWERBI    = "powerbi"
    SIMPLE     = "simple"
    SLACK      = "slack_digest"
    API_JSON   = "api_json"

class InteractionMode(str, Enum):
    DRILL_DOWN       = "drill_down"
    READ_ONLY        = "read_only"
    REAL_TIME        = "real_time"
    SCHEDULED_REPORT = "scheduled_report"

class MetricProfile(str, Enum):
    COUNT_HEAVY    = "count_heavy"
    TREND_HEAVY    = "trend_heavy"
    RATE_PCT       = "rate_percentage"
    COMPARISON     = "comparison"
    MIXED          = "mixed"
    SCORECARD      = "scorecard"

class DashboardCategory(str, Enum):
    COMPLIANCE_AUDIT    = "compliance_audit"
    SECURITY_OPS        = "security_operations"
    LEARNING_DEV        = "learning_development"
    HR_WORKFORCE        = "hr_workforce"
    RISK_MANAGEMENT     = "risk_management"
    EXECUTIVE           = "executive_reporting"
    DATA_OPS            = "data_operations"
    CROSS_DOMAIN        = "cross_domain"

class AudienceLevel(str, Enum):
    SECURITY_OPS     = "security_ops"
    COMPLIANCE_TEAM  = "compliance_team"
    EXECUTIVE_BOARD  = "executive_board"
    RISK_MANAGEMENT  = "risk_management"
    LEARNING_ADMIN   = "learning_admin"
    DATA_ENGINEER    = "data_engineer"
    SOC_ANALYST      = "soc_analyst"

class ComplexityLevel(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


# ── Decision Tree Dimensions ──────────────────────────────────────────

class DecisionDimension(BaseModel):
    """One resolved dimension in the decision tree output."""
    option_id:  str
    confidence: float = Field(ge=0.0, le=1.0)
    source:     str   # "llm" | "deterministic" | "keyword" | "default"


class ResolvedDecisions(BaseModel):
    """Full output of the decision tree resolver for one dashboard/template."""
    category:         DecisionDimension
    focus_areas:      list[str]
    metric_profile:   DecisionDimension
    audience:         list[str]
    complexity:       DecisionDimension
    destination_type: list[DestinationType]
    interaction_mode: list[InteractionMode]
    registry_source:  str   # "dashboard_registry" | "ld_templates_registry" | "both"
    overall_confidence: float
    reasoning:        str = ""


# ── Enriched Template ─────────────────────────────────────────────────

class DestinationConstraints(BaseModel):
    """What is excluded or transformed for a given destination."""
    excluded_primitives: list[str] = []
    max_panels:          Optional[int] = None
    measure_format:      Optional[str] = None  # "dax" for PowerBI
    max_kpi_cells:       Optional[int] = None


class EnrichedTemplate(BaseModel):
    """
    A dashboard template (from either registry) after enrichment.
    This is the canonical row written to Postgres + embedded in vector store.
    """
    # Identity
    template_id:    str
    registry_source: str   # "dashboard_registry" | "ld_templates_registry"
    name:           str
    description:    str
    source_system:  Optional[str] = None  # e.g. "Elastic Security", "AWS SIEM"
    content_hash:   str = ""              # SHA-256 of source JSON, for change detection

    # Decision tree dimensions (enriched)
    category:            DashboardCategory
    focus_areas:         list[str]
    audience_levels:     list[AudienceLevel]
    complexity:          ComplexityLevel
    metric_profile_fit:  list[MetricProfile]
    supported_destinations: list[DestinationType]
    interaction_modes:   list[InteractionMode]

    # Layout spec
    primitives:          list[str] = []
    panels:              dict      = {}
    layout_grid:         dict      = {}
    strip_cells:         int       = 0
    has_chat:            bool      = False
    has_graph:           bool      = False
    has_filters:         bool      = False
    chart_types:         list[str] = []
    components:          list[dict] = []   # raw component list from source

    # Scoring metadata
    best_for:            list[str] = []
    theme_hint:          str       = "light"
    domains:             list[str] = []

    # Destination constraints
    powerbi_constraints: DestinationConstraints = Field(default_factory=DestinationConstraints)
    simple_constraints:  DestinationConstraints = Field(default_factory=DestinationConstraints)

    # Embedding text (built by enricher, stored for re-indexing)
    embedding_text:      str = ""


# ── Enriched Metric ───────────────────────────────────────────────────

class EnrichedMetric(BaseModel):
    """
    A single metric after enrichment. One Postgres row + one vector store doc.
    """
    metric_id:           str
    dashboard_id:        str
    dashboard_name:      str
    dashboard_category:  str

    name:                str
    metric_type:         str          # count | percentage | trend_line | etc.
    unit:                str
    chart_type:          str
    section:             str = ""

    # Enriched fields
    metric_profile:      MetricProfile
    category:            DashboardCategory
    focus_areas:         list[str]
    source_capabilities: list[str]    # e.g. ["cornerstone.lms"]
    source_schemas:      list[str]    # table names
    kpis:                list[str]    = []

    # Thresholds (populated from catalog if available, else null)
    threshold_warning:   Optional[float] = None
    threshold_critical:  Optional[float] = None
    good_direction:      str = "neutral"   # up | down | neutral

    axis_label:          str = ""
    aggregation:         str = ""
    display_name:        str = ""

    embedding_text:      str = ""
    content_hash:        str = ""


# ── Decision Tree Node ────────────────────────────────────────────────

class DecisionOption(BaseModel):
    option_id:   str
    label:       str
    keywords:    list[str]
    maps_to:     dict                  # {field: value}
    confidence:  float = 0.8
    tags:        list[str] = []


class DecisionQuestion(BaseModel):
    question_id: str
    question:    str
    field:       str
    options:     list[DecisionOption]
    auto_resolve_from: Optional[str] = None   # upstream state field
    resolution_priority: int = 0


class DecisionTree(BaseModel):
    """
    The full decision tree built by the enricher from all three registries.
    Serialised to decision_tree.json and to Postgres decision_tree_config table.
    """
    version:     str
    questions:   list[DecisionQuestion]
    registry_targets:  dict   # category → registry file(s)
    destination_gates: dict   # destination_type → allowed primitives
    defaults:          dict   # destination_type → {category, audience, complexity}
    built_at:    str

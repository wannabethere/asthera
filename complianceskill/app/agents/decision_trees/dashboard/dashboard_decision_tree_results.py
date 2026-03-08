"""
Result types for Dashboard Decision Tree retrieval services.

Mirrors decision_tree_results.py exactly — same dataclass pattern,
same __post_init__ guard pattern.

DashboardTemplateResult  — one enriched template from the vector store
DashboardMetricResult    — one metric from the metric_catalog collection
DashboardDecisionContext — combined retrieval result passed to the decision node
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DashboardTemplateResult:
    """Result from layout_templates vector store search (RETRIEVAL POINT 1)."""
    template_id:     str
    name:            str
    registry_source: Optional[str] = None      # "dashboard_registry" | "ld_templates_registry"
    description:     Optional[str] = None
    source_system:   Optional[str] = None

    # Decision tree dimensions
    category:                str             = ""
    focus_areas:             List[str]       = field(default_factory=list)
    audience_levels:         List[str]       = field(default_factory=list)
    complexity:              str             = "medium"
    metric_profile_fit:      List[str]       = field(default_factory=list)
    supported_destinations:  List[str]       = field(default_factory=list)
    interaction_modes:       List[str]       = field(default_factory=list)

    # Layout spec
    primitives:     List[str]       = field(default_factory=list)
    panels:         Dict[str, Any]  = field(default_factory=dict)
    layout_grid:    Dict[str, Any]  = field(default_factory=dict)
    strip_cells:    int             = 0
    has_chat:       bool            = False
    has_graph:      bool            = False
    has_filters:    bool            = False
    chart_types:    List[str]       = field(default_factory=list)
    best_for:       List[str]       = field(default_factory=list)
    theme_hint:     str             = "light"
    domains:        List[str]       = field(default_factory=list)

    # Destination constraints
    powerbi_constraints: Dict[str, Any] = field(default_factory=dict)
    simple_constraints:  Dict[str, Any] = field(default_factory=dict)

    # Retrieval metadata
    content_hash:   str   = ""
    score:          float = 0.0
    id:             Optional[str] = None
    metadata:       Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict for state storage."""
        return {
            "template_id":              self.template_id,
            "name":                     self.name,
            "registry_source":          self.registry_source,
            "description":              self.description,
            "source_system":            self.source_system,
            "category":                 self.category,
            "focus_areas":              self.focus_areas,
            "audience_levels":          self.audience_levels,
            "complexity":               self.complexity,
            "metric_profile_fit":       self.metric_profile_fit,
            "supported_destinations":   self.supported_destinations,
            "interaction_modes":        self.interaction_modes,
            "primitives":               self.primitives,
            "panels":                   self.panels,
            "layout_grid":              self.layout_grid,
            "strip_cells":              self.strip_cells,
            "has_chat":                 self.has_chat,
            "has_graph":                self.has_graph,
            "has_filters":              self.has_filters,
            "chart_types":              self.chart_types,
            "best_for":                 self.best_for,
            "theme_hint":               self.theme_hint,
            "domains":                  self.domains,
            "powerbi_constraints":      self.powerbi_constraints,
            "simple_constraints":       self.simple_constraints,
            "content_hash":             self.content_hash,
        }


@dataclass
class DashboardMetricResult:
    """
    Result from metric_catalog vector store search (RETRIEVAL POINT 2).
    Used by spec_generation_node to configure per-metric chart settings.
    """
    metric_id:           str
    name:                str
    dashboard_id:        Optional[str]  = None
    dashboard_name:      Optional[str]  = None
    dashboard_category:  Optional[str]  = None

    metric_type:         Optional[str]  = None
    unit:                Optional[str]  = None
    chart_type:          Optional[str]  = None
    section:             Optional[str]  = None
    metric_profile:      Optional[str]  = None
    category:            Optional[str]  = None

    focus_areas:         List[str]      = field(default_factory=list)
    source_capabilities: List[str]      = field(default_factory=list)
    source_schemas:      List[str]      = field(default_factory=list)
    kpis:                List[str]      = field(default_factory=list)

    threshold_warning:   Optional[float] = None
    threshold_critical:  Optional[float] = None
    good_direction:      str            = "neutral"
    axis_label:          Optional[str]  = None
    aggregation:         Optional[str]  = None
    display_name:        Optional[str]  = None

    score:               float          = 0.0
    id:                  Optional[str]  = None
    metadata:            Dict[str, Any] = field(default_factory=dict)


@dataclass
class DashboardDecisionContext:
    """
    Combined retrieval result passed to the dashboard decision node.
    Mirrors DecisionTreeRetrievedContext from decision_tree_results.py.
    """
    query:     str
    templates: List[DashboardTemplateResult]
    metrics:   List[DashboardMetricResult]

    # {template_id: similarity_score} — fed into scoring as vector boost
    template_boosts: Dict[str, float] = field(default_factory=dict)

    total_hits: int = 0
    warnings:   List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.templates is None:
            self.templates = []
        if self.metrics is None:
            self.metrics = []
        if self.template_boosts is None:
            self.template_boosts = {}
        if self.warnings is None:
            self.warnings = []
        if not self.total_hits:
            self.total_hits = len(self.templates) + len(self.metrics)

    def to_state_payload(self) -> Dict[str, Any]:
        """
        Serialise into the two state fields consumed by
        dt_dashboard_decision_node:
            dt_enriched_templates       — list of template dicts
            dt_retrieved_template_boosts — {template_id: score}
        """
        return {
            "dt_enriched_templates":         [t.to_dict() for t in self.templates],
            "dt_retrieved_template_boosts":  self.template_boosts,
            "retrieved_metric_context":      [
                {
                    "metric_id":          m.metric_id,
                    "name":               m.name,
                    "display_name":       m.display_name or m.name,
                    "unit":               m.unit or "",
                    "chart_type":         m.chart_type or "",
                    "threshold_warning":  m.threshold_warning,
                    "threshold_critical": m.threshold_critical,
                    "good_direction":     m.good_direction,
                    "axis_label":         m.axis_label or "",
                    "aggregation":        m.aggregation or "",
                    "focus_areas":        m.focus_areas,
                    "source_capabilities":m.source_capabilities,
                }
                for m in self.metrics
            ],
        }

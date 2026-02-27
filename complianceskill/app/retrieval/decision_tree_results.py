"""
Result types for Decision Tree retrieval services.

Provides typed dataclasses for metrics and control taxonomy search results.
"""
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class MetricResult:
    """Result from metric search."""
    metric_id: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    goals: Optional[List[str]] = None
    focus_areas: Optional[List[str]] = None
    use_cases: Optional[List[str]] = None
    audience_levels: Optional[List[str]] = None
    metric_type: Optional[str] = None
    aggregation_windows: Optional[List[str]] = None
    group_affinity: Optional[List[str]] = None
    source_schemas: Optional[List[str]] = None
    source_capabilities: Optional[List[str]] = None
    kpis: Optional[List[Dict[str, Any]]] = None
    trends: Optional[List[Dict[str, Any]]] = None
    data_filters: Optional[List[str]] = None
    data_groups: Optional[List[str]] = None
    natural_language_question: Optional[str] = None
    mapped_control_codes: Optional[List[str]] = None
    mapped_control_domains: Optional[List[str]] = None
    mapped_risk_categories: Optional[List[str]] = None
    control_evidence_hints: Optional[Dict[str, Any]] = None
    risk_quantification_hints: Optional[Dict[str, Any]] = None
    scenario_detection_hints: Optional[Dict[str, Any]] = None
    enrichment_source: Optional[str] = None
    metadata: Dict[str, Any] = None
    score: float = 0.0
    id: Optional[str] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.goals is None:
            self.goals = []
        if self.focus_areas is None:
            self.focus_areas = []
        if self.use_cases is None:
            self.use_cases = []
        if self.audience_levels is None:
            self.audience_levels = []
        if self.aggregation_windows is None:
            self.aggregation_windows = []
        if self.group_affinity is None:
            self.group_affinity = []
        if self.source_schemas is None:
            self.source_schemas = []
        if self.source_capabilities is None:
            self.source_capabilities = []
        if self.kpis is None:
            self.kpis = []
        if self.trends is None:
            self.trends = []
        if self.data_filters is None:
            self.data_filters = []
        if self.data_groups is None:
            self.data_groups = []
        if self.mapped_control_codes is None:
            self.mapped_control_codes = []
        if self.mapped_control_domains is None:
            self.mapped_control_domains = []
        if self.mapped_risk_categories is None:
            self.mapped_risk_categories = []


@dataclass
class ControlTaxonomyResult:
    """Result from control taxonomy search."""
    control_code: str
    domain: Optional[str] = None
    sub_domain: Optional[str] = None
    measurement_goal: Optional[str] = None
    focus_areas: Optional[List[str]] = None
    risk_categories: Optional[List[str]] = None
    metric_type_preferences: Optional[Dict[str, Any]] = None
    evidence_requirements: Optional[Dict[str, Any]] = None
    affinity_keywords: Optional[List[str]] = None
    control_type_classification: Optional[Dict[str, Any]] = None
    differentiation_note: Optional[str] = None
    metadata: Dict[str, Any] = None
    score: float = 0.0
    id: Optional[str] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.focus_areas is None:
            self.focus_areas = []
        if self.risk_categories is None:
            self.risk_categories = []
        if self.affinity_keywords is None:
            self.affinity_keywords = []
        if self.metric_type_preferences is None:
            self.metric_type_preferences = {}
        if self.evidence_requirements is None:
            self.evidence_requirements = {}
        if self.control_type_classification is None:
            self.control_type_classification = {}


@dataclass
class DecisionTreeRetrievedContext:
    """Combined decision tree retrieval results."""
    query: str
    metrics: List[MetricResult]
    control_taxonomy: List[ControlTaxonomyResult]
    total_hits: int
    warnings: Optional[List[str]] = None

    def __post_init__(self):
        if self.metrics is None:
            self.metrics = []
        if self.control_taxonomy is None:
            self.control_taxonomy = []
        if self.warnings is None:
            self.warnings = []
        if self.total_hits is None:
            self.total_hits = len(self.metrics) + len(self.control_taxonomy)

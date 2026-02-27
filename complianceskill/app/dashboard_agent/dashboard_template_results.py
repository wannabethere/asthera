"""
Result types for Dashboard Template retrieval services.

Provides typed dataclasses for dashboard template search results.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class DashboardTemplateResult:
    """Result from dashboard template search."""
    template_id: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    category_label: Optional[str] = None
    icon: Optional[str] = None
    domains: List[str] = field(default_factory=list)
    complexity: Optional[str] = None
    has_chat: bool = False
    has_graph: bool = False
    has_filters: bool = False
    strip_cells: int = 0
    best_for: List[str] = field(default_factory=list)
    primitives: List[str] = field(default_factory=list)
    theme_hint: Optional[str] = None
    similarity_score: Optional[float] = None
    
    # Extended fields from L&D templates
    chart_types: List[str] = field(default_factory=list)
    activity_types: List[str] = field(default_factory=list)
    table_columns: Optional[Any] = None  # Can be list or dict
    strip_example: List[str] = field(default_factory=list)
    card_anatomy: Optional[Dict[str, Any]] = None
    layout_grid: Optional[Dict[str, Any]] = None
    panels: Optional[Dict[str, Any]] = None
    filter_options: List[str] = field(default_factory=list)
    
    # Full template metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class DashboardTemplateRetrievedContext:
    """Combined dashboard template retrieval results."""
    query: str
    templates: List[DashboardTemplateResult]
    total_hits: int = 0
    decisions: Optional[Dict[str, Any]] = None  # Decision context used for scoring
    warnings: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if self.templates is None:
            self.templates = []
        if self.warnings is None:
            self.warnings = []
        if self.total_hits == 0 and self.templates:
            self.total_hits = len(self.templates)

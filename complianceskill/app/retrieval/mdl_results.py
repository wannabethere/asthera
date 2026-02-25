"""
Result types for MDL retrieval services.

Provides typed dataclasses for MDL collection search results.
"""
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class MDLSchemaResult:
    """Result from leen_db_schema search."""
    table_name: str
    schema_ddl: str
    columns: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    score: float
    id: Optional[str] = None


@dataclass
class MDLTableDescriptionResult:
    """Result from leen_table_description search."""
    table_name: str
    description: str
    relationships: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    score: float
    id: Optional[str] = None


@dataclass
class MDLProjectMetaResult:
    """Result from leen_project_meta search."""
    project_id: str
    project_name: str
    metadata: Dict[str, Any]
    content: str
    score: float
    id: Optional[str] = None


@dataclass
class MDLMetricResult:
    """Result from leen_metrics_registry search."""
    metric_name: str
    metric_definition: str
    kpi_type: Optional[str] = None
    thresholds: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = None
    score: float = 0.0
    id: Optional[str] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.thresholds is None:
            self.thresholds = {}


@dataclass
class MDLDashboardPatternResult:
    """Result from mdl_dashboards search."""
    question: str
    component_type: str  # kpi, metric, table, insight
    data_tables: List[str]
    reasoning: str
    chart_hint: Optional[str] = None
    columns_used: Optional[List[str]] = None
    filters_available: Optional[List[str]] = None
    dashboard_name: Optional[str] = None
    dashboard_description: Optional[str] = None
    dashboard_id: Optional[str] = None
    project_id: Optional[str] = None
    source_id: Optional[str] = None
    component_sequence: Optional[int] = None
    sql_query: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Dict[str, Any] = None
    score: float = 0.0
    id: Optional[str] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.data_tables is None:
            self.data_tables = []
        if self.columns_used is None:
            self.columns_used = []
        if self.filters_available is None:
            self.filters_available = []
        if self.tags is None:
            self.tags = []


@dataclass
class MDLRetrievedContext:
    """Combined MDL retrieval results."""
    query: str
    db_schemas: List[MDLSchemaResult]
    table_descriptions: List[MDLTableDescriptionResult]
    project_meta: List[MDLProjectMetaResult]
    metrics: List[MDLMetricResult]
    total_hits: int

    def __post_init__(self):
        if self.db_schemas is None:
            self.db_schemas = []
        if self.table_descriptions is None:
            self.table_descriptions = []
        if self.project_meta is None:
            self.project_meta = []
        if self.metrics is None:
            self.metrics = []
        if self.total_hits is None:
            self.total_hits = (
                len(self.db_schemas) +
                len(self.table_descriptions) +
                len(self.project_meta) +
                len(self.metrics)
            )

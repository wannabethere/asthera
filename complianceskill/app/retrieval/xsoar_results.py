"""
Result types for XSOAR retrieval services.

Provides typed dataclasses for XSOAR enriched collection search results.
"""
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class XSOARPlaybookResult:
    """Result from XSOAR playbook search."""
    playbook_id: str
    playbook_name: str
    content: str
    tasks: Optional[List[Dict[str, Any]]] = None
    metadata: Dict[str, Any] = None
    score: float = 0.0
    id: Optional[str] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.tasks is None:
            self.tasks = []


@dataclass
class XSOARDashboardResult:
    """Result from XSOAR dashboard search."""
    dashboard_id: str
    dashboard_name: str
    widgets: Optional[List[Dict[str, Any]]] = None
    metadata: Dict[str, Any] = None
    score: float = 0.0
    id: Optional[str] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.widgets is None:
            self.widgets = []


@dataclass
class XSOARScriptResult:
    """Result from XSOAR script search."""
    script_id: str
    script_name: str
    content: str
    script_type: Optional[str] = None
    metadata: Dict[str, Any] = None
    score: float = 0.0
    id: Optional[str] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class XSOARIntegrationResult:
    """Result from XSOAR integration search."""
    integration_id: str
    integration_name: str
    content: str
    commands: Optional[List[Dict[str, Any]]] = None
    metadata: Dict[str, Any] = None
    score: float = 0.0
    id: Optional[str] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.commands is None:
            self.commands = []


@dataclass
class XSOARIndicatorResult:
    """Result from XSOAR indicator search."""
    indicator_id: str
    indicator_name: str
    indicator_type: str
    content: str
    regex: Optional[str] = None
    metadata: Dict[str, Any] = None
    score: float = 0.0
    id: Optional[str] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class XSOARRetrievedContext:
    """Combined XSOAR retrieval results."""
    query: str
    playbooks: List[XSOARPlaybookResult]
    dashboards: List[XSOARDashboardResult]
    scripts: List[XSOARScriptResult]
    integrations: List[XSOARIntegrationResult]
    indicators: List[XSOARIndicatorResult]
    total_hits: int

    def __post_init__(self):
        if self.playbooks is None:
            self.playbooks = []
        if self.dashboards is None:
            self.dashboards = []
        if self.scripts is None:
            self.scripts = []
        if self.integrations is None:
            self.integrations = []
        if self.indicators is None:
            self.indicators = []
        if self.total_hits is None:
            self.total_hits = (
                len(self.playbooks) +
                len(self.dashboards) +
                len(self.scripts) +
                len(self.integrations) +
                len(self.indicators)
            )

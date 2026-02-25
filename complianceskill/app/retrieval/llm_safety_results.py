"""
Result types for LLM Safety retrieval services.

Provides typed dataclasses for LLM Safety collection search results.
"""
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class LLMSafetyTechniqueResult:
    """Result from LLM Safety technique search."""
    technique_id: str
    title: str
    description: str
    content: str
    severity: Optional[str] = None
    category: Optional[str] = None
    tactic: Optional[str] = None
    keywords: Optional[List[str]] = None
    has_detection_rule: bool = False
    detection_rule_title: Optional[str] = None
    detection_rule_level: Optional[str] = None
    metadata: Dict[str, Any] = None
    score: float = 0.0
    id: Optional[str] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.keywords is None:
            self.keywords = []


@dataclass
class LLMSafetyMitigationResult:
    """Result from LLM Safety mitigation search."""
    mitigation_id: str
    title: str
    description: str
    content: str
    category: Optional[str] = None
    effectiveness: Optional[str] = None
    implementation_complexity: Optional[str] = None
    keywords: Optional[List[str]] = None
    metadata: Dict[str, Any] = None
    score: float = 0.0
    id: Optional[str] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.keywords is None:
            self.keywords = []


@dataclass
class LLMSafetyDetectionRuleResult:
    """Result from LLM Safety detection rule search."""
    rule_id: str
    title: str
    description: str
    content: str  # Full YAML content
    technique_id: Optional[str] = None
    technique_title: Optional[str] = None
    status: Optional[str] = None
    level: Optional[str] = None
    tags: Optional[List[str]] = None
    logsource: Optional[Dict[str, Any]] = None
    detection: Optional[Dict[str, Any]] = None
    falsepositives: Optional[List[str]] = None
    metadata: Dict[str, Any] = None
    score: float = 0.0
    id: Optional[str] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.tags is None:
            self.tags = []
        if self.falsepositives is None:
            self.falsepositives = []


@dataclass
class LLMSafetyRetrievedContext:
    """Combined LLM Safety retrieval results."""
    query: str
    techniques: List[LLMSafetyTechniqueResult]
    mitigations: List[LLMSafetyMitigationResult]
    detection_rules: List[LLMSafetyDetectionRuleResult]
    total_hits: int

    def __post_init__(self):
        if self.techniques is None:
            self.techniques = []
        if self.mitigations is None:
            self.mitigations = []
        if self.detection_rules is None:
            self.detection_rules = []
        if self.total_hits is None:
            self.total_hits = (
                len(self.techniques) +
                len(self.mitigations) +
                len(self.detection_rules)
            )

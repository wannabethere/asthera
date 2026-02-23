"""
Result dataclasses for retrieval operations.

These dataclasses provide typed results for agents consuming the knowledge base.
They separate the retrieval layer from the ORM models and Qdrant payloads.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class ControlResult:
    """Result for a control artifact."""
    id: str
    control_code: str
    framework_id: str
    framework_name: str
    name: str
    description: Optional[str] = None
    domain: Optional[str] = None
    control_type: Optional[str] = None
    cis_control_id: Optional[str] = None
    similarity_score: Optional[float] = None
    
    # Relational fields (populated when fetch_context=True)
    mitigated_risks: List["RiskResult"] = field(default_factory=list)
    satisfied_requirements: List["RequirementResult"] = field(default_factory=list)
    related_test_cases: List["TestCaseResult"] = field(default_factory=list)
    cross_framework_mappings: List["CrossFrameworkResult"] = field(default_factory=list)
    
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RequirementResult:
    """Result for a requirement artifact."""
    id: str
    requirement_code: str
    framework_id: str
    framework_name: str
    name: Optional[str] = None
    description: Optional[str] = None
    domain: Optional[str] = None
    compliance_type: Optional[str] = None
    similarity_score: Optional[float] = None
    
    # Relational fields
    satisfying_controls: List[ControlResult] = field(default_factory=list)
    
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskResult:
    """Result for a risk artifact."""
    id: str
    risk_code: str
    framework_id: str
    framework_name: str
    name: str
    description: Optional[str] = None
    asset: Optional[str] = None
    trigger: Optional[str] = None
    loss_outcomes: List[str] = field(default_factory=list)
    similarity_score: Optional[float] = None
    
    # Relational fields
    mitigating_controls: List[ControlResult] = field(default_factory=list)
    test_cases: List["TestCaseResult"] = field(default_factory=list)
    
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TestCaseResult:
    """Result for a test case artifact."""
    id: str
    framework_id: str
    framework_name: str
    name: str
    test_type: Optional[str] = None
    objective: Optional[str] = None
    test_steps: List[str] = field(default_factory=list)
    expected_result: Optional[str] = None
    evidence_required: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    risk_id: Optional[str] = None
    control_id: Optional[str] = None
    similarity_score: Optional[float] = None
    
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScenarioResult:
    """Result for a scenario artifact."""
    id: str
    scenario_code: str
    framework_id: str
    framework_name: str
    name: str
    description: Optional[str] = None
    asset: Optional[str] = None
    trigger: Optional[str] = None
    loss_outcomes: List[str] = field(default_factory=list)
    similarity_score: Optional[float] = None
    
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CrossFrameworkResult:
    """Result for a cross-framework mapping."""
    source_control_id: str
    source_control_code: str
    source_framework_id: str
    target_framework_id: str
    target_control_id: Optional[str] = None
    target_control_code: Optional[str] = None
    target_raw_code: Optional[str] = None
    mapping_type: str = "related"
    confidence_score: Optional[float] = None
    source: str = "yaml_inline"
    
    # Relational field (populated when target is resolved)
    target_control: Optional[ControlResult] = None


@dataclass
class RetrievedContext:
    """
    Typed result envelope returned by all retrieval methods.
    
    Agents consume this structure rather than raw ORM rows or Qdrant payloads.
    """
    query: str
    artifact_type: str  # "control" | "requirement" | "risk" | "test_case" | "scenario" | "cross_framework" | "multi"
    
    # Results by type (only one populated based on artifact_type, except "multi")
    controls: List[ControlResult] = field(default_factory=list)
    requirements: List[RequirementResult] = field(default_factory=list)
    risks: List[RiskResult] = field(default_factory=list)
    test_cases: List[TestCaseResult] = field(default_factory=list)
    scenarios: List[ScenarioResult] = field(default_factory=list)
    cross_framework_mappings: List[CrossFrameworkResult] = field(default_factory=list)
    
    # Metadata
    framework_filter: Optional[List[str]] = None
    total_hits: int = 0
    warnings: List[str] = field(default_factory=list)

"""
Abstract base class for framework YAML adapters.

Each framework (CIS, HIPAA, SOC2, NIST, ISO27001) has one adapter that:
1. Reads that framework's raw YAML file(s) into normalized Python dataclasses
2. Hands the normalized data to the ingestion orchestrator

Adapters never touch the database or Qdrant directly — that's the orchestrator's job.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


# ---------------------------------------------------------------------------
# Normalized dataclasses — canonical schema independent of source format
# ---------------------------------------------------------------------------

@dataclass
class NormalizedFramework:
    id: str               # e.g. "cis_v8_1"
    name: str             # e.g. "CIS Controls"
    version: str          # e.g. "v8.1"
    description: Optional[str] = None
    source_url: Optional[str] = None


@dataclass
class NormalizedControl:
    control_code: str             # raw code from source e.g. "VPM-2"
    name: str
    description: Optional[str] = None
    domain: Optional[str] = None
    control_type: Optional[str] = None   # preventive | detective | corrective
    cis_control_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Cross-framework references parsed from YAML
    # Keys are framework_id (e.g. "soc2"), values are raw code strings (e.g. "CC 2.1, CC 4.1")
    cross_framework_refs: Dict[str, str] = field(default_factory=dict)


@dataclass
class NormalizedRequirement:
    requirement_code: str
    description: Optional[str] = None
    name: Optional[str] = None
    domain: Optional[str] = None
    compliance_type: Optional[str] = None   # required | addressable (HIPAA)
    parent_requirement_code: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedRisk:
    risk_code: str                          # e.g. "CIS-RISK-001"
    name: str
    description: Optional[str] = None
    asset: Optional[str] = None
    trigger: Optional[str] = None
    loss_outcomes: List[str] = field(default_factory=list)
    likelihood: Optional[float] = None
    impact: Optional[float] = None
    # Control codes (within this framework) that mitigate this risk
    mitigating_control_codes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedTestCase:
    test_id: str                            # e.g. "CIS-RISK-001-TEST-01"
    name: str
    risk_code: Optional[str] = None         # links to risk
    control_code: Optional[str] = None      # optionally links to specific control
    test_type: Optional[str] = None
    objective: Optional[str] = None
    test_steps: List[str] = field(default_factory=list)
    expected_result: Optional[str] = None
    evidence_required: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedScenario:
    scenario_code: str                      # e.g. "CIS-RISK-001"
    name: str
    description: Optional[str] = None
    asset: Optional[str] = None
    trigger: Optional[str] = None
    loss_outcomes: List[str] = field(default_factory=list)
    severity: Optional[str] = None
    # Control codes relevant to this scenario
    relevant_control_codes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FrameworkIngestionBundle:
    """
    Everything an adapter produces. The orchestrator processes this atomically.
    """
    framework: NormalizedFramework
    controls: List[NormalizedControl] = field(default_factory=list)
    requirements: List[NormalizedRequirement] = field(default_factory=list)
    risks: List[NormalizedRisk] = field(default_factory=list)
    test_cases: List[NormalizedTestCase] = field(default_factory=list)
    scenarios: List[NormalizedScenario] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Base adapter
# ---------------------------------------------------------------------------

class BaseFrameworkAdapter(ABC):
    """
    Subclass this for each framework. Implement `load()` to return a
    FrameworkIngestionBundle populated from the framework's YAML files.
    """

    @property
    @abstractmethod
    def framework_id(self) -> str:
        """Stable identifier used as the primary key, e.g. 'cis_v8_1'."""
        ...

    @abstractmethod
    def load(self) -> FrameworkIngestionBundle:
        """
        Read the framework's source files, normalize, and return a bundle.
        Should NOT perform any I/O beyond reading source files.
        """
        ...

    # ------------------------------------------------------------------
    # Shared utility methods available to all adapters
    # ------------------------------------------------------------------

    @staticmethod
    def make_control_id(framework_id: str, control_code: str) -> str:
        return f"{framework_id}__{control_code}"

    @staticmethod
    def make_risk_id(risk_code: str) -> str:
        """Risk IDs are globally unique by convention (include framework prefix)."""
        return risk_code

    @staticmethod
    def make_requirement_id(framework_id: str, requirement_code: str) -> str:
        # HIPAA codes contain parens and dots — slugify lightly
        safe = requirement_code.replace("(", "_").replace(")", "_").replace(".", "_")
        return f"{framework_id}__{safe}"

    @staticmethod
    def make_scenario_id(scenario_code: str) -> str:
        return scenario_code

    @staticmethod
    def clean_text(text: Optional[str]) -> Optional[str]:
        """Strip leading/trailing whitespace from text fields."""
        return text.strip() if text else None

    @staticmethod
    def parse_cross_framework_refs(raw: Any) -> Dict[str, str]:
        """
        Parse the `related_frameworks` block that appears in CIS YAML controls.
        Handles dict format: {"soc2": "CC 2.1, CC 4.1", "nist_csf_2_0": "DE.CM-1"}
        Returns empty dict if malformed.
        """
        if not isinstance(raw, dict):
            return {}
        result = {}
        for framework_key, refs in raw.items():
            if refs and isinstance(refs, str):
                result[framework_key] = refs.strip()
        return result

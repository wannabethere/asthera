"""
Compliance Control Universe - Knowledge Model
=============================================

This module defines the knowledge structures for:
1. Control-Requirement-Evidence Model
2. Domain Context Definition
3. Measurable Expectations Framework
4. Risk Matrix Integration

All structures support REASONING ONLY - no execution.
"""

from typing import Dict, List, Optional, Any, Literal
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


# ============================================================================
# RISK MATRIX DEFINITIONS (from images)
# ============================================================================

class LikelihoodLevel(str, Enum):
    """Likelihood levels for risk assessment (5x5 matrix)."""
    HIGHLY_UNLIKELY = "1"  # Highly Unlikely (1)
    UNLIKELY = "2"          # Unlikely (2)
    POSSIBLE = "3"          # Possible (3)
    LIKELY = "4"            # Likely (4)
    HIGHLY_LIKELY = "5"     # Highly Likely (5)


class ImpactLevel(str, Enum):
    """Impact levels for risk assessment (5x5 matrix)."""
    NEGLIGIBLE = "1"        # Negligible Impact (1)
    LOW = "2"               # Low Impact (2)
    MODERATE = "3"          # Moderate Impact (3)
    HIGH = "4"              # High Impact (4)
    CATASTROPHIC = "5"      # Catastrophic Impact (5)


class RiskScore(str, Enum):
    """Combined risk score levels."""
    NEGLIGIBLE = "1"        # Score 1
    LOW = "4"               # Score 4
    MODERATE = "9"          # Score 9
    HIGH = "16"             # Score 16
    MAJOR = "25"            # Score 25


class ProbabilityLevel(str, Enum):
    """Probability levels for 3x3 matrix."""
    LOW = "low"
    AVERAGE = "average"
    HIGH = "high"


class SeverityLevel(str, Enum):
    """Severity/Impact levels for 3x3 matrix."""
    LOW = "low"
    AVERAGE = "average"
    HIGH = "high"


class RiskClassification(str, Enum):
    """Risk classification from 3x3 matrix."""
    INSIGNIFICANT = "insignificant"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class RiskMatrixMapping:
    """
    Mapping for risk matrix calculations.
    Based on 5x5 matrix from image 1 and 3x3 matrix from image 2.
    """
    
    # 5x5 Matrix mapping (likelihood × impact = risk score)
    five_by_five_matrix: Dict[str, Dict[str, int]] = field(default_factory=lambda: {
        "1": {"1": 1, "2": 2, "3": 3, "4": 4, "5": 5},      # Highly Unlikely
        "2": {"1": 2, "2": 4, "3": 6, "4": 8, "5": 10},     # Unlikely
        "3": {"1": 3, "2": 6, "3": 9, "4": 12, "5": 15},    # Possible
        "4": {"1": 4, "2": 8, "3": 12, "4": 16, "5": 20},   # Likely
        "5": {"1": 5, "2": 10, "3": 15, "4": 20, "5": 25}   # Highly Likely
    })
    
    # Risk score to classification mapping
    score_to_classification: Dict[int, str] = field(default_factory=lambda: {
        1: "Negligible Risk",
        2: "Negligible Risk",
        3: "Negligible Risk",
        4: "Low Risk",
        5: "Low Risk",
        6: "Low Risk",
        9: "Moderate Risk",
        10: "Moderate Risk",
        12: "Moderate Risk",
        15: "Moderate Risk",
        16: "High Risk",
        20: "High Risk",
        25: "Major Risk"
    })
    
    # 3x3 Matrix mapping (probability × severity = risk classification)
    three_by_three_matrix: Dict[str, Dict[str, str]] = field(default_factory=lambda: {
        "low": {"low": "insignificant", "average": "low", "high": "medium"},
        "average": {"low": "low", "average": "medium", "high": "high"},
        "high": {"low": "medium", "average": "high", "high": "high"}
    })


# ============================================================================
# CONTROL-REQUIREMENT-EVIDENCE MODEL
# ============================================================================

@dataclass
class Control:
    """
    High-level compliance control (e.g., SOC2 CC2.1, GDPR Article 5).
    """
    
    control_id: str                    # e.g., "SOC2-CC2.1", "GDPR-ART5"
    control_name: str                  # e.g., "Security Monitoring"
    framework: str                     # e.g., "SOC2", "GDPR", "HIPAA"
    category: str                      # e.g., "Security", "Privacy", "Access Control"
    description: str                   # High-level requirement
    control_owner: str                 # Person/team responsible
    
    # Context from documents
    source_document: Optional[str] = None
    document_section: Optional[str] = None
    extracted_text: Optional[str] = None
    
    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SubControl:
    """
    Specific measurable requirement under a control.
    This is where measurable expectations are defined.
    """
    
    subcontrol_id: str                 # e.g., "SOC2-CC2.1.1"
    parent_control_id: str             # Links to Control
    requirement_statement: str         # Specific measurable expectation
    
    # Measurable expectation details
    measurable_criteria: str           # How to measure compliance
    success_criteria: str              # What constitutes compliance
    failure_conditions: List[str]      # What makes it non-compliant
    
    # Testing/validation approach
    testing_approach: str              # How to test compliance
    testing_frequency: str             # How often to test
    
    # Risk context
    likelihood_of_failure: Optional[LikelihoodLevel] = None
    impact_of_failure: Optional[ImpactLevel] = None
    calculated_risk_score: Optional[int] = None
    risk_classification: Optional[str] = None
    
    # Source mapping
    source_document: Optional[str] = None
    extracted_requirement: Optional[str] = None
    
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceType:
    """
    Type of evidence that demonstrates control compliance.
    """
    
    evidence_type_id: str              # e.g., "LOG-001", "METRIC-001"
    evidence_name: str                 # e.g., "Access Logs", "Training Completion"
    evidence_category: str             # e.g., "Logs", "Metrics", "Documents", "Configs"
    
    # What this evidence proves
    applicable_to: List[str]           # List of subcontrol_ids
    what_it_demonstrates: str          # Natural language explanation
    
    # Collection details
    collection_method: str             # How evidence is collected
    collection_frequency: str          # How often collected
    retention_period: str              # How long to keep
    
    # Quality/sufficiency criteria
    sufficiency_criteria: str          # What makes evidence sufficient
    quality_indicators: List[str]      # Indicators of good evidence
    
    # Source
    source_system: Optional[str] = None
    data_location: Optional[str] = None
    
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ControlMapping:
    """
    Mapping between controls, requirements, and evidence.
    Also maps to processes, assets, people, systems.
    """
    
    mapping_id: str
    control_id: str
    subcontrol_ids: List[str]
    evidence_type_ids: List[str]
    
    # Entity mappings
    mapped_processes: List[str] = field(default_factory=list)
    mapped_assets: List[str] = field(default_factory=list)
    mapped_people: List[str] = field(default_factory=list)
    mapped_systems: List[str] = field(default_factory=list)
    
    # Gap analysis
    coverage_assessment: Optional[str] = None
    identified_gaps: List[str] = field(default_factory=list)
    
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# DOMAIN CONTEXT DEFINITION
# ============================================================================

@dataclass
class DomainContext:
    """
    Domain-specific context extracted from compliance documents.
    This defines what the organization does and what needs to be controlled.
    """
    
    domain_name: str                   # e.g., "Healthcare Data Processing"
    industry: str                      # e.g., "Healthcare", "Finance"
    
    # Core domain concepts
    business_processes: List[Dict[str, str]]      # Key processes identified
    data_categories: List[Dict[str, str]]         # Types of data processed
    system_components: List[Dict[str, str]]       # Systems involved
    stakeholders: List[Dict[str, str]]            # People/roles involved
    
    # Compliance context
    applicable_frameworks: List[str]              # Which frameworks apply
    regulatory_requirements: List[str]            # Specific regulations
    
    # Risk context
    inherent_risks: List[Dict[str, str]]         # Risks identified in domain
    risk_appetite: Optional[str] = None          # Organization's risk tolerance
    
    # Source information
    source_documents: List[str] = field(default_factory=list)
    extraction_date: str = field(default_factory=lambda: datetime.now().isoformat())
    
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MeasurableExpectation:
    """
    A measurable expectation derived from compliance requirements.
    This is what reasoning agents produce when analyzing documents.
    """
    
    expectation_id: str
    subcontrol_id: str                 # Links to SubControl
    
    # The expectation in natural language
    expectation_statement: str         # "User access reviews occur quarterly"
    
    # Measurability components
    metric_name: str                   # "Access Review Frequency"
    target_value: str                  # "Quarterly (every 90 days)"
    measurement_method: str            # "Review audit logs for review completion dates"
    data_source: str                   # "Access management system logs"
    
    # Success/failure criteria
    pass_criteria: str                 # "Reviews completed within 90-day window"
    fail_criteria: str                 # "Reviews >90 days apart or missing"
    
    # Testing approach
    how_to_test: str                   # Natural language test plan
    
    # Reasoning context
    reasoning_for_expectation: str     # Why this expectation is appropriate
    
    # Optional fields (must come after required fields)
    sample_size: Optional[str] = None  # If sampling required
    assumptions: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# COMPLIANCE CONTROL UNIVERSE
# ============================================================================

class ComplianceControlUniverse:
    """
    The complete universe of compliance controls for an organization.
    Contains all controls, requirements, evidence, and mappings.
    """
    
    def __init__(self, organization_name: str):
        self.organization_name = organization_name
        self.domain_context: Optional[DomainContext] = None
        
        # Core entities
        self.controls: Dict[str, Control] = {}
        self.sub_controls: Dict[str, SubControl] = {}
        self.evidence_types: Dict[str, EvidenceType] = {}
        self.mappings: Dict[str, ControlMapping] = {}
        self.measurable_expectations: Dict[str, MeasurableExpectation] = {}
        
        # Risk matrix
        self.risk_matrix = RiskMatrixMapping()
        
        # Metadata
        self.created_at = datetime.now().isoformat()
        self.last_updated = datetime.now().isoformat()
    
    def add_control(self, control: Control) -> None:
        """Add a control to the universe."""
        self.controls[control.control_id] = control
        self.last_updated = datetime.now().isoformat()
    
    def add_sub_control(self, sub_control: SubControl) -> None:
        """Add a sub-control with measurable expectations."""
        self.sub_controls[sub_control.subcontrol_id] = sub_control
        self.last_updated = datetime.now().isoformat()
    
    def add_evidence_type(self, evidence: EvidenceType) -> None:
        """Add an evidence type."""
        self.evidence_types[evidence.evidence_type_id] = evidence
        self.last_updated = datetime.now().isoformat()
    
    def add_mapping(self, mapping: ControlMapping) -> None:
        """Add a control mapping."""
        self.mappings[mapping.mapping_id] = mapping
        self.last_updated = datetime.now().isoformat()
    
    def add_measurable_expectation(self, expectation: MeasurableExpectation) -> None:
        """Add a measurable expectation."""
        self.measurable_expectations[expectation.expectation_id] = expectation
        self.last_updated = datetime.now().isoformat()
    
    def set_domain_context(self, context: DomainContext) -> None:
        """Set the domain context."""
        self.domain_context = context
        self.last_updated = datetime.now().isoformat()
    
    def calculate_risk_score(
        self,
        likelihood: LikelihoodLevel,
        impact: ImpactLevel
    ) -> tuple[int, str]:
        """
        Calculate risk score using 5x5 matrix.
        Returns (score, classification).
        """
        score = self.risk_matrix.five_by_five_matrix[likelihood.value][impact.value]
        classification = self.risk_matrix.score_to_classification.get(score, "Unknown")
        return score, classification
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of the control universe."""
        return {
            "organization": self.organization_name,
            "domain": self.domain_context.domain_name if self.domain_context else None,
            "statistics": {
                "total_controls": len(self.controls),
                "total_sub_controls": len(self.sub_controls),
                "total_evidence_types": len(self.evidence_types),
                "total_mappings": len(self.mappings),
                "total_measurable_expectations": len(self.measurable_expectations)
            },
            "frameworks": list(set(c.framework for c in self.controls.values())),
            "last_updated": self.last_updated
        }


# ============================================================================
# KNOWLEDGE BASE FOR REASONING AGENTS
# ============================================================================

@dataclass
class ComplianceKnowledgeBase:
    """
    Knowledge base that reasoning agents read from to understand
    the compliance control universe.
    """
    
    control_universe: ComplianceControlUniverse
    
    # Document sources
    source_documents: List[Dict[str, str]] = field(default_factory=list)
    
    # Extracted knowledge
    control_patterns: List[Dict[str, str]] = field(default_factory=list)
    requirement_patterns: List[Dict[str, str]] = field(default_factory=list)
    evidence_patterns: List[Dict[str, str]] = field(default_factory=list)
    
    # Industry benchmarks
    industry_benchmarks: Dict[str, Any] = field(default_factory=dict)
    
    # Risk context
    risk_assessments: List[Dict[str, Any]] = field(default_factory=list)
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_control_by_framework(self, framework: str) -> List[Control]:
        """Get all controls for a specific framework."""
        return [
            control for control in self.control_universe.controls.values()
            if control.framework == framework
        ]
    
    def get_measurable_expectations_for_control(
        self,
        control_id: str
    ) -> List[MeasurableExpectation]:
        """Get all measurable expectations for a control."""
        # Find sub-controls for this control
        sub_control_ids = [
            sc.subcontrol_id for sc in self.control_universe.sub_controls.values()
            if sc.parent_control_id == control_id
        ]
        
        # Find expectations for these sub-controls
        return [
            exp for exp in self.control_universe.measurable_expectations.values()
            if exp.subcontrol_id in sub_control_ids
        ]
    
    def get_summary_for_agents(self) -> str:
        """Get a natural language summary for reasoning agents."""
        summary = self.control_universe.get_summary()
        
        return f"""
Compliance Control Universe Summary:
====================================

Organization: {summary['organization']}
Domain: {summary['domain']}

Control Statistics:
- Total Controls: {summary['statistics']['total_controls']}
- Total Sub-Controls: {summary['statistics']['total_sub_controls']}
- Total Evidence Types: {summary['statistics']['total_evidence_types']}
- Total Measurable Expectations: {summary['statistics']['total_measurable_expectations']}

Applicable Frameworks: {', '.join(summary['frameworks'])}

Domain Context:
{self.control_universe.domain_context.domain_name if self.control_universe.domain_context else 'Not defined'}

Last Updated: {summary['last_updated']}
"""


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_sample_control_universe() -> ComplianceControlUniverse:
    """Create a sample control universe for demonstration."""
    
    universe = ComplianceControlUniverse("Sample Healthcare Organization")
    
    # Add domain context
    domain = DomainContext(
        domain_name="Healthcare Data Processing",
        industry="Healthcare",
        business_processes=[
            {"process": "Patient Registration", "criticality": "High"},
            {"process": "Clinical Documentation", "criticality": "High"},
            {"process": "Billing and Claims", "criticality": "Medium"}
        ],
        data_categories=[
            {"category": "Protected Health Information (PHI)", "sensitivity": "High"},
            {"category": "Payment Card Data", "sensitivity": "High"},
            {"category": "Administrative Data", "sensitivity": "Low"}
        ],
        applicable_frameworks=["HIPAA", "SOC2", "PCI-DSS"]
    )
    universe.set_domain_context(domain)
    
    # Add a control
    control = Control(
        control_id="HIPAA-SEC-001",
        control_name="Access Control",
        framework="HIPAA",
        category="Security",
        description="Implement technical policies and procedures for electronic information systems that maintain ePHI to allow access only to those persons or software programs that have been granted access rights",
        control_owner="CISO",
        source_document="HIPAA Security Rule",
        document_section="164.312(a)(1)"
    )
    universe.add_control(control)
    
    # Add sub-control with measurable expectation
    sub_control = SubControl(
        subcontrol_id="HIPAA-SEC-001.1",
        parent_control_id="HIPAA-SEC-001",
        requirement_statement="User access reviews must be conducted quarterly to ensure only authorized users have access to ePHI systems",
        measurable_criteria="Documented evidence of quarterly access reviews",
        success_criteria="Access reviews completed within 90 days with documented results",
        failure_conditions=[
            "Reviews not conducted within 90-day period",
            "Reviews lack documentation",
            "Unauthorized users found but not remediated"
        ],
        testing_approach="Sample access review documentation from past 12 months",
        testing_frequency="Quarterly",
        likelihood_of_failure=LikelihoodLevel.POSSIBLE,
        impact_of_failure=ImpactLevel.HIGH
    )
    
    # Calculate risk
    risk_score, risk_class = universe.calculate_risk_score(
        sub_control.likelihood_of_failure,
        sub_control.impact_of_failure
    )
    sub_control.calculated_risk_score = risk_score
    sub_control.risk_classification = risk_class
    
    universe.add_sub_control(sub_control)
    
    # Add measurable expectation
    expectation = MeasurableExpectation(
        expectation_id="EXP-001",
        subcontrol_id="HIPAA-SEC-001.1",
        expectation_statement="Access reviews for all ePHI systems occur every 90 days with documented approval",
        metric_name="Access Review Frequency",
        target_value="90 days maximum interval",
        measurement_method="Review access review logs and approval documentation",
        data_source="Identity Management System access review module",
        pass_criteria="All systems reviewed within 90-day window with documented approvals",
        fail_criteria="Any system exceeds 90 days between reviews OR reviews lack approval documentation",
        how_to_test="Query access review system for all reviews in past 12 months, calculate intervals, verify approvals",
        reasoning_for_expectation="HIPAA requires regular review of access rights. 90-day interval balances security with operational overhead and aligns with industry standards.",
        assumptions=["Access review system accurately logs all reviews", "Approval workflow is enforced"],
        limitations=["Does not verify quality of reviews, only that they occurred"]
    )
    universe.add_measurable_expectation(expectation)
    
    # Add evidence type
    evidence = EvidenceType(
        evidence_type_id="EVD-001",
        evidence_name="Access Review Reports",
        evidence_category="Reports",
        applicable_to=["HIPAA-SEC-001.1"],
        what_it_demonstrates="Demonstrates that periodic access reviews are conducted",
        collection_method="Export from Identity Management System",
        collection_frequency="Quarterly",
        retention_period="7 years",
        sufficiency_criteria="Reports must show: review date, reviewer, systems covered, approvals, remediation actions",
        quality_indicators=[
            "Complete coverage of all ePHI systems",
            "Clear approval chain documented",
            "Remediation actions for identified issues"
        ]
    )
    universe.add_evidence_type(evidence)
    
    return universe

"""
Compliance Control Universe - Knowledge Model
=============================================

This module defines the knowledge structures for:
1. Control-Requirement-Evidence Model
2. Domain Context Definition
3. Measurable Expectations Framework
4. Risk Matrix Integration
5. LLM-based Priority Calculation

All structures support REASONING ONLY - no execution.
"""

from typing import Dict, List, Optional, Any, Literal
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
import re
import logging
from pathlib import Path

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger("lexy-ai-service")


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


class ControlPriority(str, Enum):
    """Control priority levels for compliance prioritization."""
    CRITICAL = "critical"      # Highest priority - immediate attention required
    HIGH = "high"              # High priority - address soon
    MEDIUM = "medium"          # Medium priority - standard attention
    LOW = "low"                # Low priority - can be addressed later
    INFORMATIONAL = "informational"  # Lowest priority - for awareness only


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
class ControlPriorityInfo:
    """
    Priority information for a control, derived from risk, relevance, and quality assessments.
    """
    priority_level: ControlPriority              # Overall priority level
    priority_score: float                        # Numeric priority score (0.0-1.0, higher = more important)
    priority_order: int                          # Rank order (1 = highest priority)
    
    # Priority factors
    risk_score: Optional[int] = None             # Calculated risk score from likelihood × impact
    risk_classification: Optional[str] = None    # Risk classification (e.g., "High Risk")
    relevance_score: Optional[float] = None      # Relevance score from deep research (0.0-1.0)
    quality_score: Optional[float] = None        # Quality assessment score (0.0-1.0)
    coverage_score: Optional[float] = None       # Coverage completeness score (0.0-1.0)
    
    # Deep research insights
    has_coverage_gaps: bool = False             # Whether control has identified coverage gaps
    quality_issues: List[str] = field(default_factory=list)  # Quality issues identified
    improvement_recommendations: List[str] = field(default_factory=list)  # Improvement suggestions
    
    # Reasoning
    priority_reasoning: str = ""                 # Explanation of why this priority was assigned
    last_prioritized: str = field(default_factory=lambda: datetime.now().isoformat())
    
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExternalControlData:
    """
    External data for a control loaded from files or database.
    This data can override or supplement calculated values.
    """
    control_id: str
    
    # Risk data
    risk_score: Optional[int] = None
    risk_classification: Optional[str] = None
    likelihood: Optional[str] = None  # LikelihoodLevel value
    impact: Optional[str] = None      # ImpactLevel value
    
    # Metrics from external sources
    relevance_score: Optional[float] = None
    quality_score: Optional[float] = None
    coverage_score: Optional[float] = None
    
    # Flags and issues
    has_coverage_gaps: Optional[bool] = None
    quality_issues: List[str] = field(default_factory=list)
    improvement_recommendations: List[str] = field(default_factory=list)
    
    # Sub-control risk details
    subcontrol_risk_details: List[Dict[str, Any]] = field(default_factory=list)
    
    # Source information
    data_source: Optional[str] = None  # "file" or "database" or "api"
    source_file: Optional[str] = None
    last_updated: Optional[str] = None
    
    metadata: Dict[str, Any] = field(default_factory=dict)


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
    
    # Priority information
    priority_info: Optional[ControlPriorityInfo] = None
    
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
    
    # Priority information (inherits from parent control but can be overridden)
    priority_info: Optional[ControlPriorityInfo] = None
    
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
        
        # External data storage (loaded from files or database)
        self.external_control_data: Dict[str, ExternalControlData] = {}
        
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
    
    def load_external_control_data_from_file(
        self,
        file_path: str
    ) -> Dict[str, ExternalControlData]:
        """
        Load external control data from a JSON file.
        
        Expected JSON format:
        {
            "controls": [
                {
                    "control_id": "SOC2-CC2.1",
                    "risk_score": 12,
                    "risk_classification": "Moderate Risk",
                    "likelihood": "3",
                    "impact": "4",
                    "relevance_score": 0.85,
                    "quality_score": 0.90,
                    "coverage_score": 0.75,
                    "has_coverage_gaps": false,
                    "quality_issues": ["Issue 1", "Issue 2"],
                    "improvement_recommendations": ["Rec 1"],
                    "subcontrol_risk_details": [
                        {
                            "subcontrol_id": "SOC2-CC2.1.1",
                            "risk_score": 12,
                            "risk_classification": "Moderate Risk",
                            "likelihood": "3",
                            "impact": "4"
                        }
                    ]
                }
            ]
        }
        
        Args:
            file_path: Path to JSON file containing control data
        
        Returns:
            Dict mapping control_id to ExternalControlData
        """
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            logger.warning(f"External control data file not found: {file_path}")
            return {}
        
        try:
            with open(file_path_obj, 'r') as f:
                data = json.load(f)
            
            loaded_data = {}
            controls_data = data.get("controls", [])
            
            for control_data in controls_data:
                control_id = control_data.get("control_id")
                if not control_id:
                    logger.warning(f"Skipping control data entry without control_id")
                    continue
                
                external_data = ExternalControlData(
                    control_id=control_id,
                    risk_score=control_data.get("risk_score"),
                    risk_classification=control_data.get("risk_classification"),
                    likelihood=control_data.get("likelihood"),
                    impact=control_data.get("impact"),
                    relevance_score=control_data.get("relevance_score"),
                    quality_score=control_data.get("quality_score"),
                    coverage_score=control_data.get("coverage_score"),
                    has_coverage_gaps=control_data.get("has_coverage_gaps"),
                    quality_issues=control_data.get("quality_issues", []),
                    improvement_recommendations=control_data.get("improvement_recommendations", []),
                    subcontrol_risk_details=control_data.get("subcontrol_risk_details", []),
                    data_source="file",
                    source_file=str(file_path),
                    last_updated=control_data.get("last_updated", datetime.now().isoformat()),
                    metadata=control_data.get("metadata", {})
                )
                
                loaded_data[control_id] = external_data
                self.external_control_data[control_id] = external_data
            
            logger.info(f"Loaded external data for {len(loaded_data)} controls from {file_path}")
            self.last_updated = datetime.now().isoformat()
            return loaded_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON from {file_path}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error loading external control data from {file_path}: {e}")
            return {}
    
    def get_external_control_data(self, control_id: str) -> Optional[ExternalControlData]:
        """
        Get external data for a control if it exists.
        
        Args:
            control_id: ID of the control
        
        Returns:
            ExternalControlData if found, None otherwise
        """
        return self.external_control_data.get(control_id)
    
    def load_external_control_data_from_database(
        self,
        connection_string: Optional[str] = None
    ) -> Dict[str, ExternalControlData]:
        """
        Load external control data from a database.
        
        This is a placeholder for future database integration.
        Currently returns empty dict.
        
        Args:
            connection_string: Optional database connection string
        
        Returns:
            Dict mapping control_id to ExternalControlData
        """
        # TODO: Implement database loading
        logger.info("Database loading not yet implemented, returning empty data")
        return {}
    
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
    
    def calculate_control_priority(
        self,
        control_id: str,
        deep_research_knowledge: Optional[Dict[str, Any]] = None
    ) -> ControlPriorityInfo:
        """
        Calculate priority for a control using static/rule-based method.
        
        This is a fast, deterministic method based on weighted formulas.
        For more nuanced reasoning that considers downstream processing needs,
        use calculate_control_priority_with_llm() instead.
        
        Priority factors:
        1. Risk scores (likelihood × impact) - 40% weight
        2. Deep research relevance scores - 25% weight
        3. Quality assessments - 20% weight
        4. Coverage gaps - 15% weight
        
        Args:
            control_id: ID of the control to prioritize
            deep_research_knowledge: Optional dict containing:
                - relevance_scores: Dict mapping control_id to relevance score (0.0-1.0)
                - quality_scores: Dict mapping control_id to quality score (0.0-1.0)
                - coverage_gaps: List of control_ids with coverage gaps
                - quality_issues: Dict mapping control_id to list of quality issues
                - improvement_recommendations: Dict mapping control_id to recommendations
        
        Returns:
            ControlPriorityInfo with calculated priority
        
        See also:
            calculate_control_priority_with_llm() for LLM-based reasoning
        """
        control = self.controls.get(control_id)
        if not control:
            raise ValueError(f"Control {control_id} not found")
        
        # Get sub-controls for this control
        sub_controls = [
            sc for sc in self.sub_controls.values()
            if sc.parent_control_id == control_id
        ]
        
        # Check for external data first (from file or database)
        external_data = self.get_external_control_data(control_id)
        
        # Calculate aggregate risk score - use external data if available, otherwise calculate from sub-controls
        max_risk_score = 0
        max_risk_classification = "Unknown"
        if external_data and external_data.risk_score is not None:
            max_risk_score = external_data.risk_score
            max_risk_classification = external_data.risk_classification or "Unknown"
        elif sub_controls:
            risk_scores = [
                sc.calculated_risk_score for sc in sub_controls
                if sc.calculated_risk_score is not None
            ]
            if risk_scores:
                max_risk_score = max(risk_scores)
                # Get classification from highest risk sub-control
                max_sub = max(sub_controls, key=lambda sc: sc.calculated_risk_score or 0)
                max_risk_classification = max_sub.risk_classification or "Unknown"
        
        # Get metrics - prioritize external data, then default config, then deep research
        if external_data:
            relevance_score = external_data.relevance_score
            quality_score = external_data.quality_score
            coverage_score = external_data.coverage_score
            has_coverage_gaps = external_data.has_coverage_gaps if external_data.has_coverage_gaps is not None else False
            quality_issues = external_data.quality_issues or []
            improvement_recommendations = external_data.improvement_recommendations or []
        else:
            # Check for default configuration from domain_config
            try:
                from app.agents.transform.domain_config import get_control_prioritization_config
                default_config = get_control_prioritization_config(control_id)
                if default_config:
                    relevance_score = default_config.default_relevance_score
                    quality_score = default_config.default_quality_score
                    coverage_score = default_config.default_coverage_score
                    has_coverage_gaps = default_config.default_has_coverage_gaps
                    quality_issues = []
                    improvement_recommendations = []
                else:
                    # Fallback to None - will be handled below
                    relevance_score = None
                    quality_score = None
                    coverage_score = None
                    has_coverage_gaps = False
                    quality_issues = []
                    improvement_recommendations = []
            except ImportError:
                # domain_config not available, fall through to deep research
                relevance_score = None
                quality_score = None
                coverage_score = None
                has_coverage_gaps = False
                quality_issues = []
                improvement_recommendations = []
            
            # Fallback to deep research knowledge if default config not available
            if relevance_score is None:
                if deep_research_knowledge:
                    relevance_scores = deep_research_knowledge.get("relevance_scores", {})
                    quality_scores = deep_research_knowledge.get("quality_scores", {})
                    coverage_gaps = deep_research_knowledge.get("coverage_gaps", [])
                    quality_issues_dict = deep_research_knowledge.get("quality_issues", {})
                    improvement_recs = deep_research_knowledge.get("improvement_recommendations", {})
                    
                    relevance_score = relevance_scores.get(control_id)
                    quality_score = quality_scores.get(control_id)
                    has_coverage_gaps = control_id in coverage_gaps or any(
                        control_id in gap for gap in coverage_gaps if isinstance(gap, str)
                    )
                    quality_issues = quality_issues_dict.get(control_id, [])
                    improvement_recommendations = improvement_recs.get(control_id, [])
            
            # Calculate coverage score if not from external data or default config
            if coverage_score is None:
                coverage_score = self._calculate_coverage_score(control_id, sub_controls)
        
        # If coverage_score is None from external data, calculate it
        if coverage_score is None:
            coverage_score = self._calculate_coverage_score(control_id, sub_controls)
        
        # Calculate priority score (weighted combination)
        # Risk: 40%, Relevance: 25%, Quality: 20%, Coverage: 15%
        risk_normalized = min(max_risk_score / 25.0, 1.0) if max_risk_score > 0 else 0.0
        relevance_normalized = relevance_score if relevance_score is not None else 0.5
        quality_normalized = quality_score if quality_score is not None else 0.5
        coverage_normalized = coverage_score
        
        # Penalize controls with coverage gaps
        if has_coverage_gaps:
            coverage_normalized *= 0.7
        
        priority_score = (
            0.40 * risk_normalized +
            0.25 * relevance_normalized +
            0.20 * quality_normalized +
            0.15 * coverage_normalized
        )
        
        # Determine priority level
        if priority_score >= 0.8 or max_risk_score >= 20:
            priority_level = ControlPriority.CRITICAL
        elif priority_score >= 0.6 or max_risk_score >= 12:
            priority_level = ControlPriority.HIGH
        elif priority_score >= 0.4 or max_risk_score >= 6:
            priority_level = ControlPriority.MEDIUM
        elif priority_score >= 0.2:
            priority_level = ControlPriority.LOW
        else:
            priority_level = ControlPriority.INFORMATIONAL
        
        # Build reasoning
        reasoning_parts = []
        if max_risk_score > 0:
            reasoning_parts.append(f"Risk score: {max_risk_score} ({max_risk_classification})")
        if relevance_score is not None:
            reasoning_parts.append(f"Relevance: {relevance_score:.2f}")
        if quality_score is not None:
            reasoning_parts.append(f"Quality: {quality_score:.2f}")
        if has_coverage_gaps:
            reasoning_parts.append("Has coverage gaps")
        if coverage_score < 0.5:
            reasoning_parts.append("Low coverage")
        
        priority_reasoning = "; ".join(reasoning_parts) if reasoning_parts else "Default priority assignment"
        
        return ControlPriorityInfo(
            priority_level=priority_level,
            priority_score=priority_score,
            priority_order=0,  # Will be set when all controls are prioritized
            risk_score=max_risk_score,
            risk_classification=max_risk_classification,
            relevance_score=relevance_score,
            quality_score=quality_score,
            coverage_score=coverage_score,
            has_coverage_gaps=has_coverage_gaps,
            quality_issues=quality_issues,
            improvement_recommendations=improvement_recommendations,
            priority_reasoning=priority_reasoning
        )
    
    def _calculate_coverage_score(self, control_id: str, sub_controls: List[SubControl]) -> float:
        """Calculate coverage score based on sub-controls, evidence, and mappings."""
        if not sub_controls:
            return 0.0
        
        # Check for evidence types
        evidence_count = 0
        for mapping in self.mappings.values():
            if control_id == mapping.control_id:
                evidence_count += len(mapping.evidence_type_ids)
        
        # Check for measurable expectations
        expectation_count = sum(
            1 for exp in self.measurable_expectations.values()
            if exp.subcontrol_id in [sc.subcontrol_id for sc in sub_controls]
        )
        
        # Coverage score: evidence + expectations normalized by sub-control count
        evidence_score = min(evidence_count / max(len(sub_controls), 1), 1.0)
        expectation_score = min(expectation_count / max(len(sub_controls), 1), 1.0)
        
        return (evidence_score * 0.6 + expectation_score * 0.4)
    
    def prioritize_all_controls(
        self,
        deep_research_knowledge: Optional[Dict[str, Any]] = None
    ) -> Dict[str, ControlPriorityInfo]:
        """
        Calculate priorities for all controls using static/rule-based method.
        
        This is a fast, deterministic method. For more nuanced reasoning that
        considers downstream processing needs, use prioritize_all_controls_with_llm() instead.
        
        Args:
            deep_research_knowledge: Optional deep research knowledge dict
        
        Returns:
            Dict mapping control_id to ControlPriorityInfo
        
        See also:
            prioritize_all_controls_with_llm() for LLM-based reasoning
        """
        priority_infos = {}
        
        # Calculate priority for each control
        for control_id in self.controls.keys():
            priority_info = self.calculate_control_priority(control_id, deep_research_knowledge)
            priority_infos[control_id] = priority_info
            # Update control with priority info
            self.controls[control_id].priority_info = priority_info
        
        # Sort by priority score (descending) and assign order
        sorted_controls = sorted(
            priority_infos.items(),
            key=lambda x: x[1].priority_score,
            reverse=True
        )
        
        for order, (control_id, priority_info) in enumerate(sorted_controls, start=1):
            priority_info.priority_order = order
        
        self.last_updated = datetime.now().isoformat()
        return priority_infos
    
    def get_prioritized_controls(
        self,
        priority_level: Optional[ControlPriority] = None,
        limit: Optional[int] = None
    ) -> List[Control]:
        """
        Get controls sorted by priority order.
        
        Args:
            priority_level: Optional filter by priority level
            limit: Optional limit on number of controls to return
        
        Returns:
            List of controls sorted by priority (highest first)
        """
        controls_list = list(self.controls.values())
        
        # Filter by priority level if specified
        if priority_level:
            controls_list = [
                c for c in controls_list
                if c.priority_info and c.priority_info.priority_level == priority_level
            ]
        
        # Sort by priority order
        controls_list.sort(
            key=lambda c: c.priority_info.priority_order if c.priority_info else 999999
        )
        
        # Apply limit
        if limit:
            controls_list = controls_list[:limit]
        
        return controls_list
    
    def get_controls_for_compliance_calculation(
        self,
        include_priority_levels: Optional[List[ControlPriority]] = None,
        exclude_priority_levels: Optional[List[ControlPriority]] = None,
        min_priority_score: Optional[float] = None
    ) -> List[Control]:
        """
        Get controls to use for overall compliance calculation.
        Filters based on priority criteria.
        
        Args:
            include_priority_levels: Only include these priority levels (if None, include all)
            exclude_priority_levels: Exclude these priority levels
            min_priority_score: Minimum priority score to include (0.0-1.0)
        
        Returns:
            List of controls to use for compliance calculation
        """
        controls_list = list(self.controls.values())
        
        # Filter by priority info
        filtered = []
        for control in controls_list:
            if not control.priority_info:
                continue
            
            # Check include list
            if include_priority_levels:
                if control.priority_info.priority_level not in include_priority_levels:
                    continue
            
            # Check exclude list
            if exclude_priority_levels:
                if control.priority_info.priority_level in exclude_priority_levels:
                    continue
            
            # Check minimum score
            if min_priority_score is not None:
                if control.priority_info.priority_score < min_priority_score:
                    continue
            
            filtered.append(control)
        
        # Sort by priority order
        filtered.sort(
            key=lambda c: c.priority_info.priority_order if c.priority_info else 999999
        )
        
        return filtered
    
    async def assess_control_risk_with_llm(
        self,
        control_ids: List[str],
        llm: BaseChatModel,
        state: Optional[Dict[str, Any]] = None,
        domain_context: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Phase 1: Assess overall risk, impact, and likelihood for controls using LLM.
        
        This is the first step in the two-phase prioritization process.
        The LLM analyzes controls and determines:
        - Likelihood of failure
        - Impact of failure
        - Overall risk score
        - Risk classification
        
        Args:
            control_ids: List of control IDs to assess
            llm: LLM instance for reasoning
            state: Optional state dict for tracking LLM calls
            domain_context: Optional domain context description
        
        Returns:
            Dict mapping control_id to risk assessment dict with:
                - likelihood: LikelihoodLevel value
                - impact: ImpactLevel value
                - risk_score: Calculated risk score
                - risk_classification: Risk classification string
                - risk_reasoning: Explanation of risk assessment
        """
        # Build control information for batch assessment
        controls_info = []
        for control_id in control_ids:
            control = self.controls.get(control_id)
            if not control:
                continue
            
            sub_controls = [
                sc for sc in self.sub_controls.values()
                if sc.parent_control_id == control_id
            ]
            
            controls_info.append({
                "control_id": control.control_id,
                "control_name": control.control_name,
                "framework": control.framework,
                "category": control.category,
                "description": control.description,
                "sub_controls_count": len(sub_controls),
                "sub_controls": [
                    {
                        "subcontrol_id": sc.subcontrol_id,
                        "requirement_statement": sc.requirement_statement[:200] if sc.requirement_statement else ""
                    }
                    for sc in sub_controls[:5]  # Limit to first 5 for context
                ]
            })
        
        system_prompt = """You are an expert risk analyst specializing in compliance control risk assessment.

Your task is to assess the risk, impact, and likelihood for compliance controls.

RISK ASSESSMENT CRITERIA:

Likelihood Levels (1-5):
1. Highly Unlikely - Very rare occurrence, strong controls in place
2. Unlikely - Rare occurrence, controls generally effective
3. Possible - Occasional occurrence, some controls may be weak
4. Likely - Frequent occurrence, controls need improvement
5. Highly Likely - Very frequent occurrence, controls are inadequate

Impact Levels (1-5):
1. Negligible - Minimal impact, easily recoverable
2. Low - Minor impact, some disruption
3. Moderate - Significant impact, noticeable disruption
4. High - Major impact, serious disruption or compliance failure
5. Catastrophic - Severe impact, regulatory violations, major breaches

Risk Score Calculation:
- Risk Score = Likelihood × Impact (1-25 scale)
- Risk Classification based on score:
  * 1-3: Negligible Risk
  * 4-6: Low Risk
  * 9-15: Moderate Risk
  * 16-20: High Risk
  * 25: Major Risk

For each control, assess:
1. Likelihood of control failure (1-5)
2. Impact if control fails (1-5)
3. Calculate risk score (likelihood × impact)
4. Determine risk classification
5. Provide reasoning for your assessment

Respond in JSON format with an array of assessments:
[
    {
        "control_id": "CONTROL-ID",
        "likelihood": "1|2|3|4|5",
        "impact": "1|2|3|4|5",
        "risk_score": 1-25,
        "risk_classification": "Negligible Risk|Low Risk|Moderate Risk|High Risk|Major Risk",
        "risk_reasoning": "Detailed explanation of why these values were assigned"
    },
    ...
]"""

        domain_info = ""
        if domain_context:
            domain_info = f"\nDOMAIN CONTEXT:\n{domain_context}\n"
        elif self.domain_context:
            domain_info = f"""
DOMAIN CONTEXT:
- Domain: {self.domain_context.domain_name}
- Industry: {self.domain_context.industry}
- Frameworks: {', '.join(self.domain_context.applicable_frameworks)}
- Risk Appetite: {self.domain_context.risk_appetite or 'Not specified'}
"""

        prompt = f"""Assess the risk, impact, and likelihood for the following compliance controls.

{domain_info}

CONTROLS TO ASSESS ({len(controls_info)}):
{json.dumps(controls_info, indent=2)}

For each control, determine:
1. Likelihood of failure (1-5 scale)
2. Impact of failure (1-5 scale)
3. Risk score (likelihood × impact)
4. Risk classification
5. Reasoning for your assessment

Consider:
- The control's importance to compliance
- The nature of the requirement
- Potential consequences of failure
- Industry standards and best practices
- The organization's risk context

Provide your assessment in JSON format as an array."""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ]
            
            # Try to use track_llm_call if available
            try:
                from app.agents.transform.feature_engineering_types import track_llm_call
                if state is not None:
                    response = await track_llm_call(
                        agent_name="ControlRiskAssessmentAgent",
                        llm=llm,
                        messages=messages,
                        state=state,
                        step_name="control_risk_assessment_phase1"
                    )
                else:
                    response = await llm.ainvoke(messages)
            except ImportError:
                response = await llm.ainvoke(messages)
            
            # Parse response
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Extract JSON array
            json_match = re.search(r'\[[\s\S]*\]', content)
            if json_match:
                assessments = json.loads(json_match.group(0))
            else:
                logger.warning(f"Could not parse JSON array from LLM response, using fallback")
                assessments = []
            
            # Convert to dict keyed by control_id
            risk_assessments = {}
            for assessment in assessments:
                control_id = assessment.get("control_id")
                if not control_id:
                    continue
                
                likelihood_str = str(assessment.get("likelihood", "3"))
                impact_str = str(assessment.get("impact", "3"))
                risk_score = int(assessment.get("risk_score", 9))
                risk_classification = assessment.get("risk_classification", "Moderate Risk")
                risk_reasoning = assessment.get("risk_reasoning", "Risk assessed based on control characteristics")
                
                risk_assessments[control_id] = {
                    "likelihood": likelihood_str,
                    "impact": impact_str,
                    "risk_score": risk_score,
                    "risk_classification": risk_classification,
                    "risk_reasoning": risk_reasoning
                }
            
            logger.info(f"Assessed risk for {len(risk_assessments)} controls")
            return risk_assessments
            
        except Exception as e:
            logger.error(f"Error in LLM risk assessment: {e}")
            # Return empty dict on error
            return {}
    
    async def classify_control_priority_with_llm(
        self,
        control_id: str,
        risk_assessment: Dict[str, Any],
        llm: BaseChatModel,
        deep_research_knowledge: Optional[Dict[str, Any]] = None,
        state: Optional[Dict[str, Any]] = None,
        downstream_processing_context: Optional[str] = None
    ) -> ControlPriorityInfo:
        """
        Phase 2: Classify control priority using LLM based on Phase 1 risk assessment.
        
        This is the second step in the two-phase prioritization process.
        The LLM uses the risk assessment from Phase 1 plus other factors to determine:
        - Priority level (CRITICAL, HIGH, MEDIUM, LOW, INFORMATIONAL)
        - Priority score (0.0-1.0)
        - Relevance assessment
        - Quality assessment
        - Coverage assessment
        - Downstream utility
        
        Args:
            control_id: ID of the control to classify
            risk_assessment: Risk assessment from Phase 1 (likelihood, impact, risk_score, etc.)
            llm: LLM instance for reasoning
            deep_research_knowledge: Optional dict with relevance_scores, quality_scores, etc.
            state: Optional state dict for tracking LLM calls
            downstream_processing_context: Optional context about downstream processing needs
        
        Returns:
            ControlPriorityInfo with LLM-classified priority
        """
        control = self.controls.get(control_id)
        if not control:
            raise ValueError(f"Control {control_id} not found")
        
        # Get sub-controls for this control
        sub_controls = [
            sc for sc in self.sub_controls.values()
            if sc.parent_control_id == control_id
        ]
        
        # Get metrics from external data or deep research
        external_data = self.get_external_control_data(control_id)
        
        if external_data:
            relevance_score = external_data.relevance_score
            quality_score = external_data.quality_score
            coverage_score = external_data.coverage_score
            has_coverage_gaps = external_data.has_coverage_gaps if external_data.has_coverage_gaps is not None else False
            quality_issues = external_data.quality_issues or []
            improvement_recommendations = external_data.improvement_recommendations or []
        else:
            # Check for default configuration from domain_config
            try:
                from app.agents.transform.domain_config import get_control_prioritization_config
                default_config = get_control_prioritization_config(control_id)
                if default_config:
                    relevance_score = default_config.default_relevance_score
                    quality_score = default_config.default_quality_score
                    coverage_score = default_config.default_coverage_score
                    has_coverage_gaps = default_config.default_has_coverage_gaps
                    quality_issues = []
                    improvement_recommendations = []
                else:
                    # Fallback to deep research knowledge
                    relevance_score = deep_research_knowledge.get("relevance_scores", {}).get(control_id) if deep_research_knowledge else None
                    quality_score = deep_research_knowledge.get("quality_scores", {}).get(control_id) if deep_research_knowledge else None
                    has_coverage_gaps = False
                    quality_issues = []
                    improvement_recommendations = []
                    
                    if deep_research_knowledge:
                        coverage_gaps = deep_research_knowledge.get("coverage_gaps", [])
                        has_coverage_gaps = control_id in coverage_gaps or any(
                            control_id in str(gap) for gap in coverage_gaps
                        )
                        quality_issues = deep_research_knowledge.get("quality_issues", {}).get(control_id, [])
                        improvement_recommendations = deep_research_knowledge.get("improvement_recommendations", {}).get(control_id, [])
                    
                    coverage_score = self._calculate_coverage_score(control_id, sub_controls)
            except ImportError:
                # domain_config not available, use deep research knowledge
                relevance_score = deep_research_knowledge.get("relevance_scores", {}).get(control_id) if deep_research_knowledge else None
                quality_score = deep_research_knowledge.get("quality_scores", {}).get(control_id) if deep_research_knowledge else None
                has_coverage_gaps = False
                quality_issues = []
                improvement_recommendations = []
                
                if deep_research_knowledge:
                    coverage_gaps = deep_research_knowledge.get("coverage_gaps", [])
                    has_coverage_gaps = control_id in coverage_gaps or any(
                        control_id in str(gap) for gap in coverage_gaps
                    )
                    quality_issues = deep_research_knowledge.get("quality_issues", {}).get(control_id, [])
                    improvement_recommendations = deep_research_knowledge.get("improvement_recommendations", {}).get(control_id, [])
                
                coverage_score = self._calculate_coverage_score(control_id, sub_controls)
        
        # If coverage_score is None from external data, calculate it
        if coverage_score is None:
            coverage_score = self._calculate_coverage_score(control_id, sub_controls)
        
        if coverage_score is None:
            coverage_score = self._calculate_coverage_score(control_id, sub_controls)
        
        # Get evidence and expectations
        evidence_count = sum(
            len(m.evidence_type_ids) for m in self.mappings.values()
            if m.control_id == control_id
        )
        expectation_count = sum(
            1 for exp in self.measurable_expectations.values()
            if exp.subcontrol_id in [sc.subcontrol_id for sc in sub_controls]
        )
        
        # Build LLM prompt for Phase 2
        system_prompt = """You are an expert compliance analyst specializing in control prioritization and classification.

Your task is to classify the priority level for a compliance control based on:
1. Risk assessment (from Phase 1: likelihood, impact, risk score)
2. Relevance to organizational goals and downstream processing
3. Quality of implementation and evidence
4. Coverage completeness
5. Downstream processing utility

Priority levels:
- CRITICAL: Immediate attention required, high risk, essential for compliance
- HIGH: High priority, address soon, important for risk management
- MEDIUM: Standard priority, normal attention
- LOW: Lower priority, can be addressed later
- INFORMATIONAL: Lowest priority, awareness only

Consider downstream processing needs:
- Controls that feed into risk calculations should be prioritized
- Controls with measurable expectations are more useful
- Controls with complete evidence are more actionable
- Controls that map to multiple frameworks are more valuable

Respond in JSON format with:
{
    "priority_level": "critical|high|medium|low|informational",
    "priority_score": 0.0-1.0,
    "relevance_score": 0.0-1.0,
    "quality_score": 0.0-1.0,
    "coverage_score": 0.0-1.0,
    "priority_reasoning": "Detailed explanation of priority classification",
    "key_factors": ["factor1", "factor2", ...],
    "downstream_utility": "Explanation of how useful this control is for downstream processing"
}"""

        control_info = f"""
CONTROL INFORMATION:
- Control ID: {control.control_id}
- Control Name: {control.control_name}
- Framework: {control.framework}
- Category: {control.category}
- Description: {control.description}
- Owner: {control.control_owner}
"""

        # Use risk assessment from Phase 1
        risk_info = f"""
RISK ASSESSMENT (from Phase 1):
- Likelihood: {risk_assessment.get('likelihood', 'Unknown')} (1-5 scale)
- Impact: {risk_assessment.get('impact', 'Unknown')} (1-5 scale)
- Risk Score: {risk_assessment.get('risk_score', 0)} (out of 25)
- Risk Classification: {risk_assessment.get('risk_classification', 'Unknown')}
- Risk Reasoning: {risk_assessment.get('risk_reasoning', 'Not provided')}
"""

        metrics_info = f"""
CURRENT METRICS:
- Relevance Score: {relevance_score if relevance_score is not None else "To be assessed"}
- Quality Score: {quality_score if quality_score is not None else "To be assessed"}
- Coverage Score: {coverage_score:.2f}
- Evidence Types: {evidence_count}
- Measurable Expectations: {expectation_count}
- Has Coverage Gaps: {has_coverage_gaps}
"""

        issues_info = ""
        if quality_issues:
            issues_info = f"\nQUALITY ISSUES:\n" + "\n".join(f"- {issue}" for issue in quality_issues)
        
        recommendations_info = ""
        if improvement_recommendations:
            recommendations_info = f"\nIMPROVEMENT RECOMMENDATIONS:\n" + "\n".join(f"- {rec}" for rec in improvement_recommendations)
        
        downstream_context = ""
        if downstream_processing_context:
            downstream_context = f"\nDOWNSTREAM PROCESSING CONTEXT:\n{downstream_processing_context}"
        
        prompt = f"""{control_info}

{risk_info}

{metrics_info}
{issues_info}
{recommendations_info}
{downstream_context}

Based on the Phase 1 risk assessment and the metrics above, classify the priority level and assess:
1. Priority level (CRITICAL, HIGH, MEDIUM, LOW, INFORMATIONAL)
2. Priority score (0.0-1.0)
3. Relevance score (0.0-1.0) - how relevant to organizational goals
4. Quality score (0.0-1.0) - quality of implementation
5. Coverage score (0.0-1.0) - completeness of coverage
6. Downstream utility - how useful for risk calculations, monitoring, reporting

Provide your classification in JSON format."""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ]
            
            # Try to use track_llm_call if available
            try:
                from app.agents.transform.feature_engineering_types import track_llm_call
                if state is not None:
                    response = await track_llm_call(
                        agent_name="ControlPriorityClassificationAgent",
                        llm=llm,
                        messages=messages,
                        state=state,
                        step_name="control_priority_classification_phase2"
                    )
                else:
                    response = await llm.ainvoke(messages)
            except ImportError:
                response = await llm.ainvoke(messages)
            
            # Parse response
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                classification_data = json.loads(json_match.group(0))
            else:
                logger.warning(f"Could not parse JSON from LLM response for control {control_id}, using fallback")
                classification_data = self._parse_priority_from_text(content)
            
            # Extract priority information
            priority_level_str = classification_data.get("priority_level", "medium").lower()
            priority_level = ControlPriority.MEDIUM
            try:
                priority_level = ControlPriority(priority_level_str)
            except ValueError:
                logger.warning(f"Invalid priority level '{priority_level_str}', defaulting to MEDIUM")
            
            priority_score = float(classification_data.get("priority_score", 0.5))
            priority_score = max(0.0, min(1.0, priority_score))
            
            # Update scores from LLM assessment if provided
            relevance_score_llm = classification_data.get("relevance_score")
            quality_score_llm = classification_data.get("quality_score")
            coverage_score_llm = classification_data.get("coverage_score")
            
            if relevance_score_llm is not None:
                relevance_score = float(relevance_score_llm)
            if quality_score_llm is not None:
                quality_score = float(quality_score_llm)
            if coverage_score_llm is not None:
                coverage_score = float(coverage_score_llm)
            
            priority_reasoning = classification_data.get("priority_reasoning", "Priority classified based on risk assessment and metrics")
            downstream_utility = classification_data.get("downstream_utility", "Not specified")
            
            # Combine reasoning
            full_reasoning = f"{priority_reasoning}\n\nDownstream Utility: {downstream_utility}"
            
            return ControlPriorityInfo(
                priority_level=priority_level,
                priority_score=priority_score,
                priority_order=0,  # Will be set when all controls are prioritized
                risk_score=risk_assessment.get("risk_score"),
                risk_classification=risk_assessment.get("risk_classification"),
                relevance_score=relevance_score,
                quality_score=quality_score,
                coverage_score=coverage_score,
                has_coverage_gaps=has_coverage_gaps,
                quality_issues=quality_issues,
                improvement_recommendations=improvement_recommendations,
                priority_reasoning=full_reasoning
            )
            
        except Exception as e:
            logger.error(f"Error in LLM priority classification for control {control_id}: {e}")
            # Fallback to static calculation
            return self.calculate_control_priority(control_id, deep_research_knowledge)
    
    async def prioritize_all_controls_two_phase(
        self,
        llm: BaseChatModel,
        deep_research_knowledge: Optional[Dict[str, Any]] = None,
        state: Optional[Dict[str, Any]] = None,
        downstream_processing_context: Optional[str] = None,
        phase1_batch_size: int = 10,
        phase2_batch_size: int = 5
    ) -> Dict[str, ControlPriorityInfo]:
        """
        Prioritize all controls using two-phase LLM approach.
        
        Phase 1: Assess overall risk, impact, and likelihood for all controls
        Phase 2: Classify priority, relevance, quality for each control using Phase 1 results
        
        Args:
            llm: LLM instance for reasoning
            deep_research_knowledge: Optional deep research knowledge dict
            state: Optional state dict for tracking LLM calls
            downstream_processing_context: Optional context about downstream processing
            phase1_batch_size: Number of controls to assess in Phase 1 batch (default: 10)
            phase2_batch_size: Number of controls to classify in Phase 2 batch (default: 5)
        
        Returns:
            Dict mapping control_id to ControlPriorityInfo
        """
        import asyncio
        
        control_ids = list(self.controls.keys())
        if not control_ids:
            logger.warning("No controls to prioritize")
            return {}
        
        logger.info(f"Starting two-phase prioritization for {len(control_ids)} controls")
        
        # Phase 1: Assess risk, impact, likelihood for all controls
        logger.info("Phase 1: Assessing risk, impact, and likelihood")
        
        domain_context_str = None
        if self.domain_context:
            domain_context_str = f"""
Domain: {self.domain_context.domain_name}
Industry: {self.domain_context.industry}
Frameworks: {', '.join(self.domain_context.applicable_frameworks)}
Risk Appetite: {self.domain_context.risk_appetite or 'Not specified'}
"""
        
        # Process Phase 1 in batches
        all_risk_assessments = {}
        for i in range(0, len(control_ids), phase1_batch_size):
            batch = control_ids[i:i + phase1_batch_size]
            logger.info(f"Phase 1 batch {i//phase1_batch_size + 1}: Assessing {len(batch)} controls")
            
            batch_assessments = await self.assess_control_risk_with_llm(
                control_ids=batch,
                llm=llm,
                state=state,
                domain_context=domain_context_str
            )
            all_risk_assessments.update(batch_assessments)
        
        logger.info(f"Phase 1 complete: Assessed {len(all_risk_assessments)} controls")
        
        # Phase 2: Classify priority for each control using Phase 1 results
        logger.info("Phase 2: Classifying priority, relevance, and quality")
        
        priority_infos = {}
        
        # Process Phase 2 in batches
        for i in range(0, len(control_ids), phase2_batch_size):
            batch = control_ids[i:i + phase2_batch_size]
            logger.info(f"Phase 2 batch {i//phase2_batch_size + 1}: Classifying {len(batch)} controls")
            
            # Process batch concurrently
            tasks = []
            for control_id in batch:
                risk_assessment = all_risk_assessments.get(control_id, {
                    "likelihood": "3",
                    "impact": "3",
                    "risk_score": 9,
                    "risk_classification": "Moderate Risk",
                    "risk_reasoning": "Default risk assessment (Phase 1 not available)"
                })
                
                tasks.append(
                    self.classify_control_priority_with_llm(
                        control_id=control_id,
                        risk_assessment=risk_assessment,
                        llm=llm,
                        deep_research_knowledge=deep_research_knowledge,
                        state=state,
                        downstream_processing_context=downstream_processing_context
                    )
                )
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Store results
            for control_id, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Error classifying priority for control {control_id}: {result}")
                    # Fallback to static calculation
                    priority_info = self.calculate_control_priority(control_id, deep_research_knowledge)
                else:
                    priority_info = result
                
                priority_infos[control_id] = priority_info
                # Update control with priority info
                self.controls[control_id].priority_info = priority_info
        
        # Sort by priority score and assign order
        sorted_controls = sorted(
            priority_infos.items(),
            key=lambda x: x[1].priority_score,
            reverse=True
        )
        
        for order, (control_id, priority_info) in enumerate(sorted_controls, start=1):
            priority_info.priority_order = order
        
        self.last_updated = datetime.now().isoformat()
        logger.info(f"Two-phase prioritization complete: {len(priority_infos)} controls prioritized")
        return priority_infos
    
    async def calculate_control_priority_with_llm(
        self,
        control_id: str,
        llm: BaseChatModel,
        deep_research_knowledge: Optional[Dict[str, Any]] = None,
        state: Optional[Dict[str, Any]] = None,
        downstream_processing_context: Optional[str] = None
    ) -> ControlPriorityInfo:
        """
        Calculate priority for a control using LLM reasoning.
        The LLM considers risk, relevance, quality, coverage, and downstream processing needs.
        
        Args:
            control_id: ID of the control to prioritize
            llm: LLM instance for reasoning
            deep_research_knowledge: Optional dict with relevance_scores, quality_scores, etc.
            state: Optional state dict for tracking LLM calls
            downstream_processing_context: Optional context about downstream processing needs
        
        Returns:
            ControlPriorityInfo with LLM-calculated priority
        """
        control = self.controls.get(control_id)
        if not control:
            raise ValueError(f"Control {control_id} not found")
        
        # Get sub-controls for this control
        sub_controls = [
            sc for sc in self.sub_controls.values()
            if sc.parent_control_id == control_id
        ]
        
        # Check for external data first (from file or database)
        external_data = self.get_external_control_data(control_id)
        
        # Calculate aggregate risk metrics - use external data if available, otherwise calculate from sub-controls
        max_risk_score = 0
        max_risk_classification = "Unknown"
        risk_details = []
        
        if external_data and external_data.risk_score is not None:
            # Use external risk data
            max_risk_score = external_data.risk_score
            max_risk_classification = external_data.risk_classification or "Unknown"
            risk_details = external_data.subcontrol_risk_details or []
            
            # If no subcontrol details but we have main risk data, create a summary entry
            if not risk_details and max_risk_score > 0:
                risk_details = [{
                    "subcontrol_id": f"{control_id} (aggregate)",
                    "risk_score": max_risk_score,
                    "risk_classification": max_risk_classification,
                    "likelihood": external_data.likelihood or "Unknown",
                    "impact": external_data.impact or "Unknown"
                }]
        else:
            # Calculate from sub-controls (fallback when external data not available)
            if sub_controls:
                for sc in sub_controls:
                    if sc.calculated_risk_score is not None:
                        risk_details.append({
                            "subcontrol_id": sc.subcontrol_id,
                            "risk_score": sc.calculated_risk_score,
                            "risk_classification": sc.risk_classification or "Unknown",
                            "likelihood": sc.likelihood_of_failure.value if sc.likelihood_of_failure else "Unknown",
                            "impact": sc.impact_of_failure.value if sc.impact_of_failure else "Unknown"
                        })
                        if sc.calculated_risk_score > max_risk_score:
                            max_risk_score = sc.calculated_risk_score
                            max_risk_classification = sc.risk_classification or "Unknown"
        
        # Get metrics - prioritize external data, then deep research, then calculated
        if external_data:
            relevance_score = external_data.relevance_score
            quality_score = external_data.quality_score
            coverage_score = external_data.coverage_score
            has_coverage_gaps = external_data.has_coverage_gaps if external_data.has_coverage_gaps is not None else False
            quality_issues = external_data.quality_issues or []
            improvement_recommendations = external_data.improvement_recommendations or []
        else:
            # Fallback to deep research knowledge
            relevance_score = deep_research_knowledge.get("relevance_scores", {}).get(control_id) if deep_research_knowledge else None
            quality_score = deep_research_knowledge.get("quality_scores", {}).get(control_id) if deep_research_knowledge else None
            has_coverage_gaps = False
            quality_issues = []
            improvement_recommendations = []
            
            if deep_research_knowledge:
                coverage_gaps = deep_research_knowledge.get("coverage_gaps", [])
                has_coverage_gaps = control_id in coverage_gaps or any(
                    control_id in str(gap) for gap in coverage_gaps
                )
                quality_issues = deep_research_knowledge.get("quality_issues", {}).get(control_id, [])
                improvement_recommendations = deep_research_knowledge.get("improvement_recommendations", {}).get(control_id, [])
            
            # Calculate coverage score if not from external data
            coverage_score = self._calculate_coverage_score(control_id, sub_controls)
        
        # If coverage_score is None from external data, calculate it
        if coverage_score is None:
            coverage_score = self._calculate_coverage_score(control_id, sub_controls)
        
        # Get evidence and expectations
        evidence_count = sum(
            len(m.evidence_type_ids) for m in self.mappings.values()
            if m.control_id == control_id
        )
        expectation_count = sum(
            1 for exp in self.measurable_expectations.values()
            if exp.subcontrol_id in [sc.subcontrol_id for sc in sub_controls]
        )
        
        # Build LLM prompt
        system_prompt = """You are an expert compliance analyst specializing in control prioritization for risk estimation, monitoring, and reporting systems.

Your task is to assign a priority level to a compliance control based on:
1. Risk assessment (likelihood × impact)
2. Relevance to organizational goals and downstream processing
3. Quality of implementation and evidence
4. Coverage completeness
5. Downstream processing utility (how useful this control is for risk calculations, monitoring, reporting)

Priority levels:
- CRITICAL: Immediate attention required, high risk, essential for compliance
- HIGH: High priority, address soon, important for risk management
- MEDIUM: Standard priority, normal attention
- LOW: Lower priority, can be addressed later
- INFORMATIONAL: Lowest priority, awareness only

Consider downstream processing needs:
- Controls that feed into risk calculations should be prioritized
- Controls with measurable expectations are more useful
- Controls with complete evidence are more actionable
- Controls that map to multiple frameworks are more valuable

Respond in JSON format with:
{
    "priority_level": "critical|high|medium|low|informational",
    "priority_score": 0.0-1.0,
    "priority_reasoning": "Detailed explanation of why this priority was assigned, considering all factors and downstream utility",
    "key_factors": ["factor1", "factor2", ...],
    "downstream_utility": "Explanation of how useful this control is for downstream processing"
}"""

        control_info = f"""
CONTROL INFORMATION:
- Control ID: {control.control_id}
- Control Name: {control.control_name}
- Framework: {control.framework}
- Category: {control.category}
- Description: {control.description}
- Owner: {control.control_owner}
"""

        risk_info = f"""
RISK ASSESSMENT:
- Maximum Risk Score: {max_risk_score} (out of 25)
- Risk Classification: {max_risk_classification}
- Number of Sub-Controls: {len(sub_controls)}
- Risk Details: {json.dumps(risk_details, indent=2) if risk_details else "No risk data"}
"""

        metrics_info = f"""
METRICS:
- Relevance Score: {relevance_score if relevance_score is not None else "Not available"}
- Quality Score: {quality_score if quality_score is not None else "Not available"}
- Coverage Score: {coverage_score:.2f}
- Evidence Types: {evidence_count}
- Measurable Expectations: {expectation_count}
- Has Coverage Gaps: {has_coverage_gaps}
"""

        issues_info = ""
        if quality_issues:
            issues_info = f"\nQUALITY ISSUES:\n" + "\n".join(f"- {issue}" for issue in quality_issues)
        
        recommendations_info = ""
        if improvement_recommendations:
            recommendations_info = f"\nIMPROVEMENT RECOMMENDATIONS:\n" + "\n".join(f"- {rec}" for rec in improvement_recommendations)
        
        downstream_context = ""
        if downstream_processing_context:
            downstream_context = f"\nDOWNSTREAM PROCESSING CONTEXT:\n{downstream_processing_context}"
        
        prompt = f"""{control_info}

{risk_info}

{metrics_info}
{issues_info}
{recommendations_info}
{downstream_context}

Based on all this information, assign a priority level and score, considering:
1. The risk level and potential impact
2. How relevant this control is to the organization's compliance goals
3. The quality and completeness of evidence and expectations
4. How useful this control will be for downstream risk calculations, monitoring, and reporting
5. Any identified gaps or quality issues

Provide your analysis in JSON format."""

        try:
            # Make LLM call
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ]
            
            # Try to use track_llm_call if available
            try:
                from app.agents.transform.feature_engineering_types import track_llm_call
                if state is not None:
                    response = await track_llm_call(
                        agent_name="ControlPriorityAgent",
                        llm=llm,
                        messages=messages,
                        state=state,
                        step_name="control_priority_calculation"
                    )
                else:
                    response = await llm.ainvoke(messages)
            except ImportError:
                # Fallback to direct call
                response = await llm.ainvoke(messages)
            
            # Parse response
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                priority_data = json.loads(json_match.group(0))
            else:
                # Fallback parsing
                logger.warning(f"Could not parse JSON from LLM response for control {control_id}, using fallback")
                priority_data = self._parse_priority_from_text(content)
            
            # Extract priority information
            priority_level_str = priority_data.get("priority_level", "medium").lower()
            priority_level = ControlPriority.MEDIUM
            try:
                priority_level = ControlPriority(priority_level_str)
            except ValueError:
                logger.warning(f"Invalid priority level '{priority_level_str}', defaulting to MEDIUM")
            
            priority_score = float(priority_data.get("priority_score", 0.5))
            priority_score = max(0.0, min(1.0, priority_score))  # Clamp to 0-1
            
            priority_reasoning = priority_data.get("priority_reasoning", "Priority assigned based on available metrics")
            downstream_utility = priority_data.get("downstream_utility", "Not specified")
            
            # Combine reasoning
            full_reasoning = f"{priority_reasoning}\n\nDownstream Utility: {downstream_utility}"
            
            return ControlPriorityInfo(
                priority_level=priority_level,
                priority_score=priority_score,
                priority_order=0,  # Will be set when all controls are prioritized
                risk_score=max_risk_score if max_risk_score > 0 else None,
                risk_classification=max_risk_classification if max_risk_classification != "Unknown" else None,
                relevance_score=relevance_score,
                quality_score=quality_score,
                coverage_score=coverage_score,
                has_coverage_gaps=has_coverage_gaps,
                quality_issues=quality_issues,
                improvement_recommendations=improvement_recommendations,
                priority_reasoning=full_reasoning
            )
            
        except Exception as e:
            logger.error(f"Error in LLM priority calculation for control {control_id}: {e}")
            # Fallback to static calculation
            return self.calculate_control_priority(control_id, deep_research_knowledge)
    
    def _parse_priority_from_text(self, text: str) -> Dict[str, Any]:
        """Fallback parser to extract priority information from text if JSON parsing fails."""
        priority_data = {
            "priority_level": "medium",
            "priority_score": 0.5,
            "priority_reasoning": text[:500],
            "downstream_utility": "Not specified"
        }
        
        # Try to extract priority level
        for level in ["critical", "high", "medium", "low", "informational"]:
            if level in text.lower():
                priority_data["priority_level"] = level
                break
        
        # Try to extract score
        score_match = re.search(r'(?:score|priority)[:\s]+([0-9.]+)', text, re.IGNORECASE)
        if score_match:
            try:
                score = float(score_match.group(1))
                priority_data["priority_score"] = max(0.0, min(1.0, score / 100.0 if score > 1.0 else score))
            except ValueError:
                pass
        
        return priority_data
    
    async def prioritize_all_controls_with_llm(
        self,
        llm: BaseChatModel,
        deep_research_knowledge: Optional[Dict[str, Any]] = None,
        state: Optional[Dict[str, Any]] = None,
        downstream_processing_context: Optional[str] = None,
        use_two_phase: bool = True,
        batch_size: int = 5
    ) -> Dict[str, ControlPriorityInfo]:
        """
        Calculate priorities for all controls using LLM reasoning.
        
        By default, uses two-phase approach:
        - Phase 1: Assess risk, impact, likelihood for all controls
        - Phase 2: Classify priority, relevance, quality for each control
        
        Args:
            llm: LLM instance for reasoning
            deep_research_knowledge: Optional deep research knowledge dict
            state: Optional state dict for tracking LLM calls
            downstream_processing_context: Optional context about downstream processing
            use_two_phase: If True (default), use two-phase approach. If False, use single-phase.
            batch_size: Number of controls to process in parallel for single-phase (default: 5)
        
        Returns:
            Dict mapping control_id to ControlPriorityInfo
        """
        if use_two_phase:
            # Use two-phase approach
            return await self.prioritize_all_controls_two_phase(
                llm=llm,
                deep_research_knowledge=deep_research_knowledge,
                state=state,
                downstream_processing_context=downstream_processing_context
            )
        else:
            # Use single-phase approach (legacy)
            import asyncio
            
            priority_infos = {}
            control_ids = list(self.controls.keys())
            
            # Process in batches
            for i in range(0, len(control_ids), batch_size):
                batch = control_ids[i:i + batch_size]
                logger.info(f"Processing priority batch {i//batch_size + 1} ({len(batch)} controls)")
                
                # Process batch concurrently
                tasks = [
                    self.calculate_control_priority_with_llm(
                        control_id,
                        llm,
                        deep_research_knowledge,
                        state,
                        downstream_processing_context
                    )
                    for control_id in batch
                ]
                
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Store results
                for control_id, result in zip(batch, batch_results):
                    if isinstance(result, Exception):
                        logger.error(f"Error prioritizing control {control_id}: {result}")
                        # Fallback to static calculation
                        priority_info = self.calculate_control_priority(control_id, deep_research_knowledge)
                    else:
                        priority_info = result
                    
                    priority_infos[control_id] = priority_info
                    # Update control with priority info
                    self.controls[control_id].priority_info = priority_info
            
            # Sort by priority score and assign order
            sorted_controls = sorted(
                priority_infos.items(),
                key=lambda x: x[1].priority_score,
                reverse=True
            )
            
            for order, (control_id, priority_info) in enumerate(sorted_controls, start=1):
                priority_info.priority_order = order
            
            self.last_updated = datetime.now().isoformat()
            logger.info(f"Completed LLM-based prioritization for {len(priority_infos)} controls")
            return priority_infos
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of the control universe."""
        # Count controls by priority
        priority_counts = {}
        for control in self.controls.values():
            if control.priority_info:
                level = control.priority_info.priority_level.value
                priority_counts[level] = priority_counts.get(level, 0) + 1
        
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
            "priority_distribution": priority_counts,
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
    
    def integrate_deep_research_knowledge(
        self,
        deep_research_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract and format deep research knowledge for priority calculation.
        
        Args:
            deep_research_state: State dict from DeepResearchReviewAgent containing:
                - identified_controls: List of control dicts
                - relevance_scores: Dict with feature_scores, overall_score, etc.
                - deep_research_review: Dict with coverage_gaps, quality_issues, etc.
        
        Returns:
            Formatted deep research knowledge dict for use in prioritize_all_controls
        """
        knowledge = {
            "relevance_scores": {},
            "quality_scores": {},
            "coverage_gaps": [],
            "quality_issues": {},
            "improvement_recommendations": {}
        }
        
        # Extract relevance scores from feature scores
        relevance_scores = deep_research_state.get("relevance_scores", {})
        feature_scores = relevance_scores.get("feature_scores", [])
        identified_controls = deep_research_state.get("identified_controls", [])
        
        # Map feature scores to controls (via compliance_reasoning)
        for feature_score in feature_scores:
            score = feature_score.get("score", 0.5)
            feature_name = feature_score.get("feature_name", "")
            compliance_reasoning = feature_score.get("compliance_reasoning", "")
            
            # Try to match to identified controls
            for control in identified_controls:
                control_id = control.get("control_id", "")
                if control_id and (control_id in compliance_reasoning or control.get("control_name", "") in feature_name):
                    # Average scores if multiple features map to same control
                    if control_id in knowledge["relevance_scores"]:
                        knowledge["relevance_scores"][control_id] = (
                            knowledge["relevance_scores"][control_id] + score
                        ) / 2
                    else:
                        knowledge["relevance_scores"][control_id] = score
        
        # Extract coverage gaps
        deep_research_review = deep_research_state.get("deep_research_review", {})
        review_summary = deep_research_review.get("review_summary", {})
        coverage_gaps = review_summary.get("coverage_gaps", [])
        knowledge["coverage_gaps"] = coverage_gaps
        
        # Extract quality issues
        quality_issues = review_summary.get("quality_issues", [])
        for issue in quality_issues:
            # Try to extract control ID from issue text
            for control in identified_controls:
                control_id = control.get("control_id", "")
                if control_id and control_id in issue:
                    if control_id not in knowledge["quality_issues"]:
                        knowledge["quality_issues"][control_id] = []
                    knowledge["quality_issues"][control_id].append(issue)
        
        # Extract improvement recommendations
        improvement_recs = review_summary.get("improvement_recommendations", [])
        for rec in improvement_recs:
            # Try to extract control ID from recommendation text
            for control in identified_controls:
                control_id = control.get("control_id", "")
                if control_id and control_id in rec:
                    if control_id not in knowledge["improvement_recommendations"]:
                        knowledge["improvement_recommendations"][control_id] = []
                    knowledge["improvement_recommendations"][control_id].append(rec)
        
        # Calculate quality scores (inverse of issues)
        for control in identified_controls:
            control_id = control.get("control_id", "")
            if control_id:
                issues = knowledge["quality_issues"].get(control_id, [])
                # Quality score decreases with more issues
                quality_score = max(0.0, 1.0 - (len(issues) * 0.1))
                knowledge["quality_scores"][control_id] = quality_score
        
        return knowledge
    
    def get_summary_for_agents(self) -> str:
        """Get a natural language summary for reasoning agents."""
        summary = self.control_universe.get_summary()
        
        priority_info = ""
        if summary.get("priority_distribution"):
            priority_info = "\nPriority Distribution:\n"
            for level, count in sorted(summary["priority_distribution"].items()):
                priority_info += f"- {level.capitalize()}: {count}\n"
        
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
{priority_info}
Domain Context:
{self.control_universe.domain_context.domain_name if self.control_universe.domain_context else 'Not defined'}

Last Updated: {summary['last_updated']}
"""


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_deep_research_knowledge_from_state(
    deep_research_state: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Helper function to convert deep research state to knowledge format.
    
    This function extracts knowledge from the DeepResearchReviewAgent output
    and formats it for use with ComplianceControlUniverse.prioritize_all_controls().
    
    Args:
        deep_research_state: State dict from DeepResearchReviewAgent containing:
            - identified_controls: List of control dicts with control_id, control_name, etc.
            - relevance_scores: Dict with feature_scores, overall_score, goal_alignment
            - deep_research_review: Dict with review_summary containing coverage_gaps,
              quality_issues, improvement_recommendations
    
    Returns:
        Dict formatted for prioritize_all_controls() with:
            - relevance_scores: Dict[control_id, float]
            - quality_scores: Dict[control_id, float]
            - coverage_gaps: List[str]
            - quality_issues: Dict[control_id, List[str]]
            - improvement_recommendations: Dict[control_id, List[str]]
    """
    knowledge = {
        "relevance_scores": {},
        "quality_scores": {},
        "coverage_gaps": [],
        "quality_issues": {},
        "improvement_recommendations": {}
    }
    
    identified_controls = deep_research_state.get("identified_controls", [])
    relevance_scores = deep_research_state.get("relevance_scores", {})
    deep_research_review = deep_research_state.get("deep_research_review", {})
    
    # Build control ID to name mapping
    control_id_map = {
        c.get("control_id", ""): c for c in identified_controls
        if c.get("control_id")
    }
    
    # Extract relevance scores from feature scores
    feature_scores = relevance_scores.get("feature_scores", [])
    recommended_features = deep_research_state.get("recommended_features", [])
    
    # Map features to controls
    for i, feature in enumerate(recommended_features):
        compliance_reasoning = (
            feature.get("compliance_reasoning", "") or
            feature.get("soc2_compliance_reasoning", "")
        )
        feature_score = feature_scores[i].get("score", 0.5) if i < len(feature_scores) else 0.5
        
        # Match feature to control
        for control_id, control in control_id_map.items():
            if control_id in compliance_reasoning or control.get("control_name", "") in compliance_reasoning:
                # Average if multiple features map to same control
                if control_id in knowledge["relevance_scores"]:
                    knowledge["relevance_scores"][control_id] = (
                        knowledge["relevance_scores"][control_id] + feature_score
                    ) / 2
                else:
                    knowledge["relevance_scores"][control_id] = feature_score
    
    # Extract from deep research review
    review_summary = deep_research_review.get("review_summary", {})
    coverage_gaps = review_summary.get("coverage_gaps", [])
    quality_issues_list = review_summary.get("quality_issues", [])
    improvement_recs_list = review_summary.get("improvement_recommendations", [])
    
    # Process coverage gaps
    for gap in coverage_gaps:
        # Check if gap mentions specific control IDs
        for control_id in control_id_map.keys():
            if control_id in gap:
                knowledge["coverage_gaps"].append(control_id)
                break
    
    # Process quality issues
    for issue in quality_issues_list:
        for control_id in control_id_map.keys():
            if control_id in issue:
                if control_id not in knowledge["quality_issues"]:
                    knowledge["quality_issues"][control_id] = []
                knowledge["quality_issues"][control_id].append(issue)
                break
    
    # Process improvement recommendations
    for rec in improvement_recs_list:
        for control_id in control_id_map.keys():
            if control_id in rec:
                if control_id not in knowledge["improvement_recommendations"]:
                    knowledge["improvement_recommendations"][control_id] = []
                knowledge["improvement_recommendations"][control_id].append(rec)
                break
    
    # Calculate quality scores (inverse relationship with issues)
    for control_id in control_id_map.keys():
        issues = knowledge["quality_issues"].get(control_id, [])
        # More issues = lower quality score
        quality_score = max(0.0, 1.0 - (len(issues) * 0.15))
        knowledge["quality_scores"][control_id] = quality_score
    
    return knowledge


def load_external_control_data(
    control_universe: ComplianceControlUniverse,
    file_path: Optional[str] = None,
    database_connection: Optional[str] = None
) -> Dict[str, ExternalControlData]:
    """
    Helper function to load external control data from files or database.
    
    Args:
        control_universe: ComplianceControlUniverse instance
        file_path: Optional path to JSON file containing control data
        database_connection: Optional database connection string (not yet implemented)
    
    Returns:
        Dict mapping control_id to ExternalControlData
    
    Example:
        ```python
        # Load external data from file
        external_data = load_external_control_data(
            control_universe=universe,
            file_path="data/control_risk_data.json"
        )
        
        # Now when calculating priorities, external data will be used automatically
        priority_infos = await control_universe.prioritize_all_controls_with_llm(
            llm=llm,
            deep_research_knowledge=deep_research_knowledge
        )
        ```
    """
    loaded_data = {}
    
    if file_path:
        loaded_data = control_universe.load_external_control_data_from_file(file_path)
    
    if database_connection:
        db_data = control_universe.load_external_control_data_from_database(database_connection)
        loaded_data.update(db_data)
    
    return loaded_data


async def prioritize_controls_with_llm(
    control_universe: ComplianceControlUniverse,
    llm: BaseChatModel,
    deep_research_state: Optional[Dict[str, Any]] = None,
    state: Optional[Dict[str, Any]] = None,
    downstream_processing_context: Optional[str] = None
) -> Dict[str, ControlPriorityInfo]:
    """
    Convenience function to prioritize controls using LLM reasoning.
    
    This function:
    1. Extracts deep research knowledge from state (if provided)
    2. Calls LLM-based prioritization
    3. Returns prioritized controls
    
    Args:
        control_universe: ComplianceControlUniverse instance
        llm: LLM instance for reasoning
        deep_research_state: Optional deep research state from DeepResearchReviewAgent
        state: Optional state dict for tracking LLM calls
        downstream_processing_context: Optional context about downstream processing needs
            (e.g., "Controls will be used for risk calculation, monitoring dashboards, and compliance reporting")
    
    Returns:
        Dict mapping control_id to ControlPriorityInfo
    
    Example:
        ```python
        # After running DeepResearchReviewAgent
        deep_research_state = state  # from feature engineering workflow
        
        # Prioritize controls with LLM
        priority_infos = await prioritize_controls_with_llm(
            control_universe=universe,
            llm=llm,
            deep_research_state=deep_research_state,
            state=state,
            downstream_processing_context="Controls will be used for real-time risk monitoring and quarterly compliance reports"
        )
        
        # Get high-priority controls for compliance calculation
        critical_controls = control_universe.get_controls_for_compliance_calculation(
            include_priority_levels=[ControlPriority.CRITICAL, ControlPriority.HIGH]
        )
        ```
    """
    # Extract deep research knowledge if provided
    deep_research_knowledge = None
    if deep_research_state:
        deep_research_knowledge = create_deep_research_knowledge_from_state(deep_research_state)
    
    # Prioritize using LLM
    priority_infos = await control_universe.prioritize_all_controls_with_llm(
        llm=llm,
        deep_research_knowledge=deep_research_knowledge,
        state=state,
        downstream_processing_context=downstream_processing_context
    )
    
    return priority_infos


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
    
    # Example: Prioritize controls (with sample deep research knowledge)
    sample_deep_research = {
        "relevance_scores": {
            "HIPAA-SEC-001": 0.85  # High relevance
        },
        "quality_scores": {
            "HIPAA-SEC-001": 0.90  # High quality
        },
        "coverage_gaps": [],
        "quality_issues": {},
        "improvement_recommendations": {}
    }
    
    # Calculate priorities
    universe.prioritize_all_controls(deep_research_knowledge=sample_deep_research)
    
    return universe

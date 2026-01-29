"""
Measurable Signals and Risk Model Inputs - Data Structures
==========================================================

Defines structures for:
1. Measurable signals of compliance health (continuous, not binary)
2. Likelihood model inputs (generic across domains)
3. Impact model inputs (generic across domains)
4. Contextual factors
5. Feature definition library

All structures support REASONING PLANS - no execution.
"""

from typing import Dict, List, Optional, Any, Literal
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


# ============================================================================
# SIGNAL CATEGORIES (Universal across all compliance domains)
# ============================================================================

class SignalCategory(str, Enum):
    """Universal signal categories for compliance health."""
    TIMELINESS = "timeliness"              # Delays, overdue items
    COMPLETENESS = "completeness"          # Missing evidence, tasks
    ADHERENCE = "adherence"                # Rule violations
    DRIFT = "drift"                        # Config drift, training drift
    INCIDENT_FREQUENCY = "incident_frequency"  # Failures, incidents
    EXCEPTIONS = "exceptions"              # Logged exceptions
    RESPONSIVENESS = "responsiveness"      # Owner response time
    MATURITY = "maturity"                  # Control maturity level


class SignalType(str, Enum):
    """Types of signals for measurement."""
    CONTINUOUS = "continuous"      # Numeric value (e.g., days overdue)
    BINARY = "binary"             # Yes/No (e.g., evidence exists)
    CATEGORICAL = "categorical"   # Discrete categories (e.g., low/med/high)
    COUNT = "count"               # Number of occurrences
    PERCENTAGE = "percentage"     # Rate or proportion
    SCORE = "score"              # Composite score (0-100)


# ============================================================================
# MEASURABLE SIGNAL DEFINITION
# ============================================================================

@dataclass
class MeasurableSignal:
    """
    Definition of a measurable signal for compliance health.
    Converts binary (pass/fail) into continuous measurement.
    """
    
    signal_id: str                     # e.g., "SIG-TIMELINESS-001"
    signal_name: str                   # e.g., "Access Review Timeliness"
    signal_category: SignalCategory    # Which universal category
    signal_type: SignalType           # Type of measurement
    
    # What this signal measures
    description: str                   # Natural language description
    what_it_indicates: str            # What it tells us about compliance health
    
    # Measurement specification
    metric_formula: str               # How to calculate (natural language)
    unit_of_measure: str             # e.g., "days", "count", "percentage"
    healthy_range: str               # e.g., "0-5 days", "95-100%"
    warning_threshold: str           # When to be concerned
    critical_threshold: str          # When immediate action needed
    
    # Data requirements
    data_sources: List[str]          # Where data comes from
    data_collection_frequency: str   # How often to measure
    
    # Context
    applicable_controls: List[str]   # Which controls this applies to
    compliance_frameworks: List[str] # Which frameworks (or "universal")
    
    # Reasoning
    why_this_signal: str             # Reasoning for signal selection
    how_it_predicts_failure: str     # Relationship to compliance failure
    
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SignalLibrary:
    """
    Feature definition library of all measurable signals.
    Works across all compliance types.
    """
    
    signals: Dict[str, MeasurableSignal] = field(default_factory=dict)
    
    def add_signal(self, signal: MeasurableSignal) -> None:
        """Add a signal to the library."""
        self.signals[signal.signal_id] = signal
    
    def get_by_category(self, category: SignalCategory) -> List[MeasurableSignal]:
        """Get all signals in a category."""
        return [s for s in self.signals.values() if s.signal_category == category]
    
    def get_by_framework(self, framework: str) -> List[MeasurableSignal]:
        """Get signals applicable to a framework."""
        return [
            s for s in self.signals.values() 
            if framework in s.compliance_frameworks or "universal" in s.compliance_frameworks
        ]


# ============================================================================
# LIKELIHOOD MODEL INPUTS
# ============================================================================

class LikelihoodDriver(str, Enum):
    """Universal drivers of control failure likelihood."""
    HISTORICAL_FAILURE = "historical_failure_rate"
    CONTROL_DRIFT = "control_drift_frequency"
    EVIDENCE_QUALITY = "evidence_quality_score"
    PROCESS_VOLATILITY = "process_volatility"
    HUMAN_DEPENDENCY = "human_dependency"
    OPERATIONAL_LOAD = "operational_load"
    CONTROL_MATURITY = "control_maturity_level"


@dataclass
class LikelihoodInput:
    """
    Input feature for likelihood model.
    Generic across all compliance domains.
    """
    
    input_id: str                      # e.g., "LH-HIST-001"
    input_name: str                   # e.g., "Historical Failure Rate"
    driver_type: LikelihoodDriver     # Which universal driver
    
    # Definition
    description: str                   # What this input measures
    how_it_affects_likelihood: str    # Why it predicts failure
    
    # Measurement specification
    calculation_method: str           # How to calculate (natural language)
    data_sources: List[str]          # Where data comes from
    unit_of_measure: str             # e.g., "failures per quarter"
    
    # Interpretation
    low_likelihood_range: str        # Values indicating low likelihood
    medium_likelihood_range: str     # Values indicating medium likelihood
    high_likelihood_range: str       # Values indicating high likelihood
    
    # Applicability
    applies_to_control_types: List[str]  # Which control types (or "universal")
    domain_specific_adjustments: str     # How to adjust for specific domains
    
    # Reasoning
    why_this_input: str              # Reasoning for input selection
    evidence_of_predictive_power: str  # Why we believe it predicts
    
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LikelihoodModelInputs:
    """
    Complete set of inputs for likelihood modeling.
    Generic across compliance domains.
    """
    
    inputs: Dict[str, LikelihoodInput] = field(default_factory=dict)
    
    # Model design reasoning
    model_architecture: str = ""           # How inputs combine
    weighting_approach: str = ""           # How to weight inputs
    
    def add_input(self, likelihood_input: LikelihoodInput) -> None:
        """Add an input to the model."""
        self.inputs[likelihood_input.input_id] = likelihood_input
    
    def get_by_driver(self, driver: LikelihoodDriver) -> List[LikelihoodInput]:
        """Get all inputs for a driver type."""
        return [i for i in self.inputs.values() if i.driver_type == driver]


# ============================================================================
# IMPACT MODEL INPUTS
# ============================================================================

class ImpactDimension(str, Enum):
    """Universal dimensions of control failure impact."""
    REGULATORY_SEVERITY = "regulatory_severity"
    CUSTOMER_TRUST = "customer_trust_brand"
    FINANCIAL = "financial_impact"
    OPERATIONAL = "operational_disruption"
    DOWNSTREAM_DEPENDENCY = "downstream_dependency"
    CROWN_JEWEL_RELEVANCE = "crown_jewel_relevance"


@dataclass
class ImpactInput:
    """
    Input feature for impact model.
    Generic across all compliance domains.
    """
    
    input_id: str                      # e.g., "IMP-REG-001"
    input_name: str                   # e.g., "Regulatory Severity"
    dimension: ImpactDimension        # Which universal dimension
    
    # Definition
    description: str                   # What this input measures
    how_it_affects_impact: str        # Why it determines consequence
    
    # Measurement specification
    calculation_method: str           # How to calculate (natural language)
    data_sources: List[str]          # Where data comes from
    unit_of_measure: str             # e.g., "severity level", "dollar amount"
    
    # Interpretation
    low_impact_range: str            # Values indicating low impact
    medium_impact_range: str         # Values indicating medium impact
    high_impact_range: str           # Values indicating high impact
    
    # Applicability
    applies_to_control_types: List[str]  # Which control types (or "universal")
    domain_specific_adjustments: str     # How to adjust for specific domains
    
    # Reasoning
    why_this_input: str              # Reasoning for input selection
    impact_quantification_approach: str  # How to quantify this dimension
    
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ImpactModelInputs:
    """
    Complete set of inputs for impact modeling.
    Generic across compliance domains.
    """
    
    inputs: Dict[str, ImpactInput] = field(default_factory=dict)
    
    # Model design reasoning
    model_architecture: str = ""           # How inputs combine
    aggregation_approach: str = ""         # How to aggregate dimensions
    
    def add_input(self, impact_input: ImpactInput) -> None:
        """Add an input to the model."""
        self.inputs[impact_input.input_id] = impact_input
    
    def get_by_dimension(self, dimension: ImpactDimension) -> List[ImpactInput]:
        """Get all inputs for a dimension."""
        return [i for i in self.inputs.values() if i.dimension == dimension]


# ============================================================================
# CONTEXTUAL FACTORS
# ============================================================================

class ContextualFactorType(str, Enum):
    """Types of contextual factors that modify risk."""
    TEMPORAL = "temporal"              # Time-based factors
    ORGANIZATIONAL = "organizational"  # Org structure/capability
    DATA_SENSITIVITY = "data_sensitivity"  # Data classification
    POPULATION = "population"          # Affected population size


@dataclass
class ContextualFactor:
    """
    Cross-domain modifier for risk assessment.
    """
    
    factor_id: str                     # e.g., "CTX-TIME-001"
    factor_name: str                  # e.g., "Time Since Last Review"
    factor_type: ContextualFactorType # Which type
    
    # Definition
    description: str                   # What this factor represents
    how_it_modifies_risk: str         # How it affects risk assessment
    
    # Measurement
    measurement_approach: str         # How to measure
    data_source: str                  # Where data comes from
    
    # Impact on risk
    effect_on_likelihood: str         # How it affects likelihood
    effect_on_impact: str             # How it affects impact
    adjustment_formula: str           # How to apply (natural language)
    
    # Applicability
    applies_to: List[str]             # Which controls/frameworks
    
    # Reasoning
    why_this_factor: str              # Reasoning for inclusion
    
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# COMPLETE RISK MODEL BLUEPRINT
# ============================================================================

@dataclass
class RiskModelBlueprint:
    """
    Complete blueprint for risk modeling across all compliance domains.
    Contains all signals, likelihood inputs, impact inputs, and contextual factors.
    """
    
    # Signal library
    signal_library: SignalLibrary
    
    # Likelihood model
    likelihood_inputs: LikelihoodModelInputs
    
    # Impact model
    impact_inputs: ImpactModelInputs
    
    # Contextual factors
    contextual_factors: Dict[str, ContextualFactor] = field(default_factory=dict)
    
    # Model design reasoning
    overall_model_design: str = ""
    likelihood_impact_combination: str = ""  # How L × I works
    signal_to_risk_mapping: str = ""        # How signals feed into risk
    
    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    applicable_frameworks: List[str] = field(default_factory=list)
    domain_agnostic: bool = True
    
    def add_contextual_factor(self, factor: ContextualFactor) -> None:
        """Add a contextual factor."""
        self.contextual_factors[factor.factor_id] = factor
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of the risk model blueprint."""
        return {
            "total_signals": len(self.signal_library.signals),
            "signal_categories": list(set(s.signal_category for s in self.signal_library.signals.values())),
            "likelihood_inputs": len(self.likelihood_inputs.inputs),
            "likelihood_drivers": list(set(i.driver_type for i in self.likelihood_inputs.inputs.values())),
            "impact_inputs": len(self.impact_inputs.inputs),
            "impact_dimensions": list(set(i.dimension for i in self.impact_inputs.inputs.values())),
            "contextual_factors": len(self.contextual_factors),
            "domain_agnostic": self.domain_agnostic,
            "frameworks": self.applicable_frameworks
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_sample_signal_library() -> SignalLibrary:
    """Create sample signal library with universal signals."""
    
    library = SignalLibrary()
    
    # Example: Timeliness signal
    timeliness_signal = MeasurableSignal(
        signal_id="SIG-TIMELINESS-001",
        signal_name="Task Completion Timeliness",
        signal_category=SignalCategory.TIMELINESS,
        signal_type=SignalType.CONTINUOUS,
        description="Measures days overdue for compliance tasks",
        what_it_indicates="Control process health and execution discipline",
        metric_formula="Current date - Due date for incomplete tasks; 0 for completed on time",
        unit_of_measure="days",
        healthy_range="0 days (on time)",
        warning_threshold="1-5 days overdue",
        critical_threshold=">5 days overdue",
        data_sources=["Task management system", "Workflow logs"],
        data_collection_frequency="Daily",
        applicable_controls=["universal"],
        compliance_frameworks=["universal"],
        why_this_signal="Timeliness indicates process discipline. Delays predict control failures.",
        how_it_predicts_failure="Overdue tasks accumulate, leading to incomplete evidence and audit findings"
    )
    library.add_signal(timeliness_signal)
    
    # Example: Completeness signal
    completeness_signal = MeasurableSignal(
        signal_id="SIG-COMPLETENESS-001",
        signal_name="Evidence Completeness Rate",
        signal_category=SignalCategory.COMPLETENESS,
        signal_type=SignalType.PERCENTAGE,
        description="Percentage of required evidence artifacts present",
        what_it_indicates="Evidence collection effectiveness",
        metric_formula="(Evidence items present / Evidence items required) × 100",
        unit_of_measure="percentage",
        healthy_range="95-100%",
        warning_threshold="85-95%",
        critical_threshold="<85%",
        data_sources=["Evidence repository", "Control requirements database"],
        data_collection_frequency="Weekly",
        applicable_controls=["universal"],
        compliance_frameworks=["universal"],
        why_this_signal="Missing evidence indicates control gaps. Direct predictor of audit failures.",
        how_it_predicts_failure="Incomplete evidence = cannot demonstrate compliance = audit finding"
    )
    library.add_signal(completeness_signal)
    
    return library


def create_sample_likelihood_inputs() -> LikelihoodModelInputs:
    """Create sample likelihood model inputs."""
    
    model = LikelihoodModelInputs()
    
    # Example: Historical failure rate
    historical_input = LikelihoodInput(
        input_id="LH-HIST-001",
        input_name="Historical Failure Rate",
        driver_type=LikelihoodDriver.HISTORICAL_FAILURE,
        description="Frequency of past control failures",
        how_it_affects_likelihood="Past failures predict future failures",
        calculation_method="Count of failures in past 12 months / Total review periods",
        data_sources=["Audit findings database", "Control testing results"],
        unit_of_measure="failures per quarter",
        low_likelihood_range="0 failures/quarter",
        medium_likelihood_range="1-2 failures/quarter",
        high_likelihood_range=">2 failures/quarter",
        applies_to_control_types=["universal"],
        domain_specific_adjustments="Adjust lookback period based on control frequency",
        why_this_input="Historical patterns are strongest predictor of future behavior",
        evidence_of_predictive_power="Industry data shows 70% of failures have prior history"
    )
    model.add_input(historical_input)
    
    # Example: Human dependency
    human_dependency_input = LikelihoodInput(
        input_id="LH-HUMAN-001",
        input_name="Human Dependency Score",
        driver_type=LikelihoodDriver.HUMAN_DEPENDENCY,
        description="Degree to which control relies on manual human actions",
        how_it_affects_likelihood="Manual processes have higher failure rates than automated",
        calculation_method="Score 0-10: 0=fully automated, 10=fully manual",
        data_sources=["Process documentation", "Control design specs"],
        unit_of_measure="score (0-10)",
        low_likelihood_range="0-3 (mostly automated)",
        medium_likelihood_range="4-7 (mixed)",
        high_likelihood_range="8-10 (manual)",
        applies_to_control_types=["universal"],
        domain_specific_adjustments="Weight based on task complexity",
        why_this_input="Human error is leading cause of control failures",
        evidence_of_predictive_power="Automated controls fail at 2% rate vs 15% for manual"
    )
    model.add_input(human_dependency_input)
    
    return model


def create_sample_impact_inputs() -> ImpactModelInputs:
    """Create sample impact model inputs."""
    
    model = ImpactModelInputs()
    
    # Example: Regulatory severity
    regulatory_input = ImpactInput(
        input_id="IMP-REG-001",
        input_name="Regulatory Severity Level",
        dimension=ImpactDimension.REGULATORY_SEVERITY,
        description="Severity of regulatory penalties for this control failure",
        how_it_affects_impact="Higher penalties = higher impact",
        calculation_method="Map control to regulation tier: Tier 1 (low), Tier 2 (high)",
        data_sources=["Regulatory framework mappings", "Legal assessments"],
        unit_of_measure="tier level",
        low_impact_range="Tier 1 / Addressable requirements",
        medium_impact_range="Tier 1 / Required with moderate penalties",
        high_impact_range="Tier 2 / High penalty potential",
        applies_to_control_types=["universal"],
        domain_specific_adjustments="Map to framework-specific penalty structures",
        why_this_input="Regulatory penalties directly quantify financial impact",
        impact_quantification_approach="Use penalty tier as multiplier on base impact"
    )
    model.add_input(regulatory_input)
    
    # Example: Downstream dependency
    dependency_input = ImpactInput(
        input_id="IMP-DEP-001",
        input_name="Downstream Dependency Count",
        dimension=ImpactDimension.DOWNSTREAM_DEPENDENCY,
        description="Number of other controls that depend on this control",
        how_it_affects_impact="More dependencies = cascading failures = higher impact",
        calculation_method="Count controls that reference this control as prerequisite",
        data_sources=["Control dependency mapping", "Control universe graph"],
        unit_of_measure="count of dependent controls",
        low_impact_range="0-2 dependencies",
        medium_impact_range="3-5 dependencies",
        high_impact_range=">5 dependencies",
        applies_to_control_types=["universal"],
        domain_specific_adjustments="Weight by criticality of dependent controls",
        why_this_input="Cascading failures multiply impact exponentially",
        impact_quantification_approach="Impact increases logarithmically with dependency count"
    )
    model.add_input(dependency_input)
    
    return model

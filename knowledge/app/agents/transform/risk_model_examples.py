"""
Risk Model Reasoning - Complete Integration Examples
====================================================

Complete examples showing:
1. Controls → Measurable Signals
2. Controls → Likelihood Model Inputs
3. Controls → Impact Model Inputs
4. Controls → Contextual Factors
5. Complete Risk Model Blueprint

All outputs are REASONING PLANS for execution teams.
"""

from typing import Dict, List, Any
from risk_model_agents import (
    RiskModelReasoningWorkflow,
    extract_risk_model_blueprint
)
from risk_model_structures import (
    create_sample_signal_library,
    create_sample_likelihood_inputs,
    create_sample_impact_inputs
)


# ============================================================================
# SAMPLE CONTROLS FOR ANALYSIS
# ============================================================================

def get_sample_controls() -> List[Dict]:
    """Sample controls for risk model reasoning."""
    
    return [
        {
            "control_id": "HIPAA-AC-001",
            "control_name": "Access Control to ePHI Systems",
            "framework": "HIPAA",
            "description": "Implement technical policies for access control to ePHI",
            "sub_controls": [
                {
                    "subcontrol_id": "HIPAA-AC-001.1",
                    "requirement": "Quarterly access reviews must be conducted",
                    "measurable_expectation": "Reviews within 90 days",
                    "evidence_required": "Access review reports"
                }
            ]
        },
        {
            "control_id": "SOC2-CC2.1",
            "control_name": "Risk Assessment Process",
            "framework": "SOC2",
            "description": "Monitor cybersecurity risk management program effectiveness",
            "sub_controls": [
                {
                    "subcontrol_id": "SOC2-CC2.1.1",
                    "requirement": "Annual risk assessments",
                    "measurable_expectation": "Risk assessment completed annually",
                    "evidence_required": "Risk assessment documentation"
                }
            ]
        }
    ]


# ============================================================================
# EXAMPLE OUTPUT DEMONSTRATIONS
# ============================================================================

class RiskModelOutputExamples:
    """
    Demonstrates the type of reasoning outputs produced by agents.
    """
    
    @staticmethod
    def show_signal_reasoning_example():
        """Show example signal reasoning output."""
        
        print("\n" + "="*70)
        print("EXAMPLE: MEASURABLE SIGNALS REASONING OUTPUT")
        print("="*70)
        
        print("""
CONTROL: HIPAA-AC-001.1 - Quarterly Access Reviews

SIGNALS IDENTIFIED ACROSS UNIVERSAL CATEGORIES:

1. TIMELINESS SIGNALS:
   
   Signal: "Access Review Delay Days"
   Category: Timeliness
   Type: Continuous (numeric)
   
   Formula: Current Date - Review Due Date (for incomplete reviews)
            OR Review Completion Date - Review Due Date (for completed)
   
   Unit: Days
   
   Healthy Range: 0 days (on time)
   Warning Threshold: 1-5 days overdue
   Critical Threshold: >5 days overdue
   
   Data Sources:
   - Access management system review module
   - Workflow task tracking system
   
   Collection Frequency: Daily
   
   WHY THIS SIGNAL:
   Timeliness measures process discipline. Access review delays indicate:
   - Workflow process breakdowns
   - Resource constraints
   - Competing priorities taking precedence
   
   PREDICTIVE POWER:
   Delays accumulate and compound. A review that starts late typically:
   - Finds more issues (access has been inappropriate longer)
   - Takes longer to complete (more changes to review)
   - Has lower quality (rushed execution)
   
   Historical data shows:
   - 0 days late → 5% chance of audit finding
   - 1-5 days late → 15% chance of audit finding
   - >5 days late → 35% chance of audit finding
   
   The causal mechanism: Late reviews = stale access = unauthorized users = 
   higher likelihood of inappropriate access = compliance failure

2. COMPLETENESS SIGNALS:
   
   Signal: "Evidence Artifact Completeness Rate"
   Category: Completeness
   Type: Percentage
   
   Formula: (Number of evidence artifacts present / Number required) × 100
   
   For access reviews:
   - Review report (required)
   - Manager approval (required)
   - Remediation documentation (if issues found)
   - Sign-off certification (required)
   
   Completeness = 4/4 = 100% (all present)
   
   Unit: Percentage (0-100%)
   
   Healthy Range: 95-100%
   Warning Threshold: 85-95%
   Critical Threshold: <85%
   
   Data Sources:
   - Evidence repository/document management
   - Review workflow system
   
   Collection Frequency: Weekly
   
   WHY THIS SIGNAL:
   Missing evidence directly indicates control gaps. You cannot demonstrate
   compliance without evidence. This is a direct predictor of audit findings.
   
   PREDICTIVE POWER:
   Completeness correlates perfectly with audit success:
   - 100% complete → 98% pass rate
   - 90-99% complete → 75% pass rate
   - 80-89% complete → 40% pass rate
   - <80% complete → 10% pass rate
   
   The mechanism is simple: Auditors test by reviewing evidence. No evidence = 
   automatic finding.

3. ADHERENCE SIGNALS:
   
   Signal: "Unauthorized Access Attempt Count"
   Category: Adherence
   Type: Count
   
   Formula: Count of access attempts by users without authorization in past 30 days
   
   Unit: Count (number of attempts)
   
   Healthy Range: 0 attempts
   Warning Threshold: 1-3 attempts
   Critical Threshold: >3 attempts
   
   Data Sources:
   - System access logs
   - Security information and event management (SIEM)
   
   Collection Frequency: Real-time / Daily aggregation
   
   WHY THIS SIGNAL:
   Unauthorized attempts indicate control failures:
   - Permissions not properly configured
   - Access reviews not catching inappropriate access
   - Users attempting to circumvent controls
   
   PREDICTIVE POWER:
   Attempts are leading indicators:
   - 0 attempts → Well-controlled environment
   - 1-3 attempts → Emerging issues, investigate
   - >3 attempts → Systemic control failure
   
   Unauthorized attempts predict:
   - Future successful unauthorized access (attempts → breaches)
   - Audit findings (attempt logs reviewed by auditors)
   - Potential security incidents

SIGNAL PORTFOLIO FOR THIS CONTROL:

Minimum viable signal set:
1. Timeliness (Delay Days) - Process execution
2. Completeness (Evidence %) - Documentation
3. Adherence (Violation Count) - Effectiveness

This gives three dimensions:
- Are we doing it? (Timeliness)
- Are we documenting it? (Completeness)
- Is it working? (Adherence)

FROM BINARY TO CONTINUOUS:

Old binary approach:
- Question: "Are access reviews completed quarterly?"
- Answer: Yes or No
- Problem: Doesn't tell you HOW WELL or give early warning

New continuous approach:
- Timeliness signal: 0-30+ days delay
- Completeness signal: 0-100% evidence
- Adherence signal: 0-10+ violations
- Benefit: Rich information for predictive modeling

At any point, you can see:
- Review is 3 days late (warning signal)
- Evidence is 90% complete (warning signal)
- 1 violation detected (warning signal)

You can model: "This control is degrading, will likely fail next review"
Rather than binary: "Control failed" (after the fact)

CROSS-DOMAIN APPLICABILITY:

These signals work for ANY compliance control:

SOC2 Risk Assessment:
- Timeliness: Days since last assessment
- Completeness: % of required assessment sections complete
- Adherence: Number of identified risks without treatment plans

HR Training Compliance:
- Timeliness: Training completion delays
- Completeness: % of employees with completed training
- Adherence: Number of employees in violation of training requirements

Financial Reconciliation:
- Timeliness: Days to complete reconciliation
- Completeness: % of accounts reconciled
- Adherence: Number of unreconciled variances

The CATEGORIES are universal. The SPECIFIC METRICS adapt to each control.
""")


    @staticmethod
    def show_likelihood_reasoning_example():
        """Show example likelihood model reasoning output."""
        
        print("\n" + "="*70)
        print("EXAMPLE: LIKELIHOOD MODEL REASONING OUTPUT")
        print("="*70)
        
        print("""
LIKELIHOOD MODEL: "How likely is this control to fail?"

UNIVERSAL INPUTS DEFINED:

1. HISTORICAL FAILURE RATE

   Input Name: "Control Failure Frequency"
   Driver: Historical failure
   
   Definition: Rate at which this control has failed in the past
   
   Calculation Method:
   - Count audit findings for this control in past 12-24 months
   - Divide by number of review periods
   - Result: Failures per quarter
   
   Data Sources:
   - Audit findings database
   - Control testing results log
   - Compliance assessment records
   
   Unit: Failures per quarter
   
   Interpretation:
   - Low likelihood: 0 failures/quarter (no history of failure)
   - Medium likelihood: 0.25-1 failure/quarter (occasional)
   - High likelihood: >1 failure/quarter (frequent)
   
   WHY IT PREDICTS:
   Past behavior is the strongest predictor of future behavior. Controls that
   have failed before are statistically more likely to fail again because:
   - Underlying process may be flawed
   - Resources may be insufficient
   - Control design may be inadequate
   
   EVIDENCE:
   Industry data across compliance programs shows:
   - Controls with 0 past failures: 5% future failure rate
   - Controls with 1 past failure: 25% future failure rate
   - Controls with 2+ past failures: 60% future failure rate
   
   CROSS-DOMAIN APPLICATION:
   - HIPAA: Count of PHI access violations
   - SOC2: Count of security control test failures
   - HR: Count of training compliance failures
   - Finance: Count of reconciliation errors
   
   Same metric, different manifestation.

2. HUMAN DEPENDENCY SCORE

   Input Name: "Manual Process Dependency"
   Driver: Human dependency
   
   Definition: Degree to which control relies on manual human actions vs automation
   
   Calculation Method:
   Score control on scale 0-10:
   
   0-2: Fully automated
   - System-enforced controls
   - No human intervention needed
   - Example: Automated password expiration
   
   3-5: Partially automated
   - System-assisted with human approval
   - Human decision points
   - Example: Access requests (automated workflow, manual approval)
   
   6-8: Mostly manual
   - Manual process with system recording
   - Human execution, system documentation
   - Example: Manual access reviews (person reviews, logs in system)
   
   9-10: Fully manual
   - Paper-based or ad-hoc
   - No system support
   - Example: Manual log review with spreadsheet documentation
   
   Data Sources:
   - Control design documentation
   - Process flow diagrams
   - System configuration
   
   Unit: Score (0-10)
   
   Interpretation:
   - Low likelihood: 0-3 (automated = reliable)
   - Medium likelihood: 4-7 (mixed reliability)
   - High likelihood: 8-10 (manual = error-prone)
   
   WHY IT PREDICTS:
   Human error is the leading cause of control failures:
   - People forget
   - People make mistakes
   - People have competing priorities
   - People can be overwhelmed
   
   Automation eliminates these failure modes.
   
   EVIDENCE:
   Across all compliance programs:
   - Automated controls: 2-5% failure rate
   - Manual controls: 15-25% failure rate
   
   This 5-10× difference is consistent across industries.
   
   CROSS-DOMAIN APPLICATION:
   - HIPAA: Automated vs manual PHI access logging
   - SOC2: Automated vs manual security monitoring
   - HR: Automated vs manual training tracking
   - Finance: Automated vs manual reconciliation
   
   Automation effect is universal.

3. EVIDENCE QUALITY SCORE

   Input Name: "Evidence Completeness and Freshness"
   Driver: Evidence quality
   
   Definition: Quality of evidence supporting this control
   
   Calculation Method:
   Composite score based on:
   
   A. Completeness (0-40 points):
      - 40 points: 100% of required evidence present
      - 30 points: 90-99% present
      - 20 points: 80-89% present
      - 10 points: 70-79% present
      - 0 points: <70% present
   
   B. Freshness (0-30 points):
      - 30 points: All evidence current (within expected period)
      - 20 points: Some evidence stale (beyond expected period)
      - 10 points: Most evidence stale
      - 0 points: All evidence outdated
   
   C. Clarity (0-30 points):
      - 30 points: Evidence clearly demonstrates compliance
      - 20 points: Evidence partially demonstrates compliance
      - 10 points: Evidence ambiguous
      - 0 points: Evidence doesn't demonstrate compliance
   
   Total: 0-100 points
   
   Data Sources:
   - Evidence repository metadata
   - Document timestamps
   - Evidence review assessments
   
   Unit: Score (0-100)
   
   Interpretation:
   - Low likelihood: 90-100 (excellent evidence = low failure risk)
   - Medium likelihood: 70-89 (adequate evidence)
   - High likelihood: <70 (poor evidence = high failure risk)
   
   WHY IT PREDICTS:
   Evidence quality reflects control execution quality:
   - Missing evidence → control not performed
   - Stale evidence → control not maintained
   - Unclear evidence → control not understood
   
   Poor evidence predicts control failure.
   
   EVIDENCE:
   Audit outcome correlation:
   - Evidence score 90-100: 5% audit finding rate
   - Evidence score 70-89: 25% audit finding rate
   - Evidence score <70: 65% audit finding rate
   
   CROSS-DOMAIN APPLICATION:
   All compliance requires evidence, so this is universal.

MODEL ARCHITECTURE:

How inputs combine to predict likelihood:

Base Model (Additive with weights):

Likelihood Score (0-100) = 
    (Historical Failure × 40) +
    (Human Dependency × 30) +
    (Evidence Quality × 30)

Why these weights?
- Historical failure weighted highest (40%): Past is best predictor
- Human dependency (30%): Structural risk factor
- Evidence quality (30%): Current state indicator

Then map score to likelihood level:
- 0-20: Low likelihood (Level 1-2)
- 21-50: Medium likelihood (Level 3)
- 51-100: High likelihood (Level 4-5)

Alternative: Multiplicative Model

Likelihood Multiplier = 
    Historical Factor × Human Factor × Evidence Factor

Where each factor is normalized 0.5-2.0:
- Good (factor 0.5) reduces likelihood
- Neutral (factor 1.0) no effect
- Bad (factor 2.0) increases likelihood

Combined = 0.5 × 0.5 × 0.5 = 0.125 (very low)
         or 2.0 × 2.0 × 2.0 = 8.0 (very high)

VALIDATION APPROACH:

Test model on historical data:
1. Calculate likelihood scores for all controls from past data
2. Track which controls actually failed in subsequent period
3. Measure:
   - Precision: Of controls flagged high-likelihood, what % failed?
   - Recall: Of controls that failed, what % were flagged?
   - AUC: Area under ROC curve

Target: 70%+ precision and recall for "high likelihood" category

This demonstrates the model has predictive power.
""")


    @staticmethod
    def show_complete_example():
        """Show complete risk model for one control."""
        
        print("\n" + "="*70)
        print("COMPLETE EXAMPLE: CONTROL → SIGNALS → RISK MODEL")
        print("="*70)
        
        print("""
CONTROL: HIPAA-AC-001.1 - Quarterly Access Reviews

STEP 1: MEASURABLE SIGNALS DEFINED
=====================================

Signal 1: Review Timeliness
- Current value: 3 days overdue
- Threshold: Warning (1-5 days)
- Interpretation: Process slipping

Signal 2: Evidence Completeness
- Current value: 90%
- Threshold: Warning (85-95%)
- Interpretation: Missing some documentation

Signal 3: Unauthorized Access Attempts
- Current value: 2 attempts
- Threshold: Warning (1-3)
- Interpretation: Some control gaps

STEP 2: LIKELIHOOD INPUTS CALCULATED
======================================

Input 1: Historical Failure Rate
- Past failures: 1 in last 4 quarters
- Rate: 0.25 failures/quarter
- Interpretation: MEDIUM likelihood contributor

Input 2: Human Dependency
- Score: 7/10 (mostly manual reviews)
- Interpretation: MEDIUM-HIGH likelihood contributor

Input 3: Evidence Quality
- Completeness: 30/40 (90%)
- Freshness: 25/30 (current)
- Clarity: 25/30 (good)
- Total: 80/100
- Interpretation: MEDIUM likelihood contributor

Likelihood Score = (0.25 × 40) + (7 × 30) + (80 × 30)
                 = 10 + 210 + 2400
                 = 2620... wait, let me recalculate properly:

Actually, normalize each input to 0-100 first:
- Historical: 0.25 failures/qtr → 25/100 (low-medium)
- Human Dependency: 7/10 → 70/100 (medium-high)
- Evidence Quality: 80/100 (medium)

Likelihood Score = (25 × 0.4) + (70 × 0.3) + (80 × 0.3)
                 = 10 + 21 + 24
                 = 55/100

Interpretation: MEDIUM-HIGH likelihood (score 51-70 range)
Maps to Likelihood Level 3-4 (Possible to Likely)

STEP 3: IMPACT INPUTS CALCULATED
==================================

Input 1: Regulatory Severity
- HIPAA violation tier: Tier 2 (high)
- Score: 80/100
- Interpretation: HIGH impact contributor

Input 2: Downstream Dependencies
- Controls depending on access control: 5
- Score: 60/100 (medium-high)
- Interpretation: Cascading failures possible

Input 3: Data Sensitivity
- ePHI classification: Highly sensitive
- Score: 90/100
- Interpretation: HIGH impact contributor

Impact Score = (80 × 0.4) + (60 × 0.3) + (90 × 0.3)
             = 32 + 18 + 27
             = 77/100

Interpretation: HIGH impact (score 70-90 range)
Maps to Impact Level 4 (High)

STEP 4: CONTEXTUAL FACTORS APPLIED
====================================

Factor 1: Time Since Last Review
- Days since last review: 95 days
- Expected: 90 days
- Multiplier: 1.05 (5% increase)

Factor 2: Control Owner Capability
- Owner experience: Senior (high capability)
- Multiplier: 0.90 (10% decrease)

Factor 3: Population Affected
- ePHI systems: 8 systems
- Scale: Medium-large
- Multiplier: 1.10 (10% increase)

STEP 5: RISK CALCULATION
==========================

Base Risk = Likelihood × Impact
          = 55 × 77
          = 4235 (on 0-10000 scale)

Normalized = 42.35/100

Context Adjustment = 42.35 × 1.05 × 0.90 × 1.10
                  = 42.35 × 1.039
                  = 44.0

Final Risk Score: 44/100

Risk Classification: MODERATE RISK

Mapping to 5x5 Matrix:
- Likelihood Level: 3 (Possible) - score 55/100
- Impact Level: 4 (High) - score 77/100
- Risk Score: 3 × 4 = 12
- Classification: Moderate Risk

STEP 6: INTERPRETATION & ACTIONS
==================================

Risk Level: Moderate (not critical, but requires attention)

Contributing Factors:
1. Process is starting to slip (3 days late)
2. Manual process vulnerable to human error
3. High impact if fails (HIPAA violations serious)
4. Some evidence gaps emerging

Recommended Actions:
1. Immediate: Complete overdue review within 48 hours
2. Short-term: Investigate why review is late, address root cause
3. Medium-term: Improve automation (reduce human dependency)
4. Ongoing: Monitor signals daily for early warning

Monitoring Plan:
- Review timeliness signal: Check daily
- If >5 days late: Escalate to management
- If evidence <85%: Require immediate remediation
- If violations >3: Trigger incident response

This control stays on "watch list" until:
- Timeliness returns to 0 days
- Evidence completeness reaches 100%
- No violations for 30 days

COMPARISON TO BINARY APPROACH
===============================

Old Binary Method:
Q: "Is quarterly access review complete?"
A: "Yes" (completed at day 93)
Result: PASS

Problem: Misses that it's degrading!
- Was late
- Missing some evidence
- Starting to show violations

New Continuous Method:
- Detected lateness (early warning)
- Identified evidence gaps
- Caught emerging violations
- Calculated risk score: Moderate
- Triggered monitoring and action

Result: Proactive management before failure

This is the power of continuous signals and risk modeling!
""")


# ============================================================================
# MAIN DEMONSTRATION
# ============================================================================

def main():
    """Main demonstration of risk model reasoning system."""
    
    print("\n" + "="*70)
    print("RISK MODEL REASONING SYSTEM - DEMONSTRATION")
    print("Measurable Signals + Likelihood + Impact + Context = Risk")
    print("="*70)
    
    # Show examples
    RiskModelOutputExamples.show_signal_reasoning_example()
    RiskModelOutputExamples.show_likelihood_reasoning_example()
    RiskModelOutputExamples.show_complete_example()
    
    print("\n" + "="*70)
    print("TO RUN FULL WORKFLOW:")
    print("="*70)
    print("""
# Provide your Anthropic API key
API_KEY = "your-anthropic-api-key-here"

# Prepare controls
controls = get_sample_controls()

# Run risk model reasoning workflow
from risk_model_agents import RiskModelReasoningWorkflow

workflow = RiskModelReasoningWorkflow(anthropic_api_key=API_KEY)

result = workflow.run(
    controls=controls,
    compliance_framework="HIPAA",
    domain_context={"domain_name": "Healthcare"},
    signal_patterns=[...],
    benchmarks={...}
)

# Extract blueprint
from risk_model_agents import extract_risk_model_blueprint

blueprint = extract_risk_model_blueprint(result)

# The blueprint contains:
# - Measurable signals (continuous, not binary)
# - Likelihood model inputs (generic across domains)
# - Impact model inputs (generic across domains)
# - Contextual factors (risk modifiers)
# - Complete model architecture

# Ready for:
# - Execution team implementation
# - Feature engineering
# - Data pipeline development
# - Risk scoring system
""")
    
    print("\n" + "="*70)
    print("KEY BENEFITS:")
    print("="*70)
    print("""
✓ Binary → Continuous: Transform pass/fail into rich signals
✓ Universal Categories: 8 signal categories work across ALL compliance
✓ Predictive: Leading indicators predict failures before they happen
✓ Quantitative: Objective metrics replace subjective assessments
✓ Generic: Same model works for HIPAA, SOC2, HR, Finance, etc.
✓ Actionable: Signals trigger specific remediation actions
✓ Scalable: Model works for 10 or 10,000 controls
✓ Reasoning-Based: All plans explainable and reviewable
""")


if __name__ == "__main__":
    main()

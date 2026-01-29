"""
Data Science Planner Agents - Signal and Risk Model Reasoning
=============================================================

Reasoning agents that convert controls into:
1. Measurable signals (continuous, not binary)
2. Likelihood model inputs (generic across domains)
3. Impact model inputs (generic across domains)
4. Contextual factors

All agents produce REASONING PLANS for execution teams.
"""

from typing import TypedDict, List, Dict, Annotated, Optional
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
import operator

from risk_model_structures import (
    SignalLibrary,
    MeasurableSignal,
    SignalCategory,
    LikelihoodModelInputs,
    ImpactModelInputs,
    RiskModelBlueprint,
    ContextualFactor
)


# ============================================================================
# STATE DEFINITION
# ============================================================================

class RiskModelReasoningState(TypedDict):
    """
    State for risk model reasoning agents.
    """
    
    # Input: Controls from control universe
    controls: List[Dict]                    # Controls to analyze
    compliance_framework: str               # Framework context
    domain_context: Optional[Dict]          # Domain information
    
    # Knowledge bases
    existing_signal_patterns: Optional[List[Dict]]
    industry_benchmarks: Optional[Dict]
    historical_models: Optional[List[Dict]]
    
    # Reasoning outputs (natural language plans)
    signal_identification_reasoning: Optional[str]
    likelihood_modeling_reasoning: Optional[str]
    impact_modeling_reasoning: Optional[str]
    contextual_factors_reasoning: Optional[str]
    
    # Structured reasoning outputs (still plans, not execution)
    proposed_signals: Optional[List[Dict]]
    proposed_likelihood_inputs: Optional[List[Dict]]
    proposed_impact_inputs: Optional[List[Dict]]
    proposed_contextual_factors: Optional[List[Dict]]
    
    # Integrated model blueprint
    risk_model_blueprint: Optional[Dict]
    
    # Workflow tracking
    messages: Annotated[List[BaseMessage], operator.add]
    current_step: str


# ============================================================================
# MEASURABLE SIGNALS REASONING AGENT
# ============================================================================

class MeasurableSignalsReasoningAgent:
    """
    Data scientist reasoning agent that converts controls into measurable signals.
    
    Transforms binary (pass/fail) into continuous health indicators.
    """
    
    def __init__(self, llm: ChatAnthropic):
        self.llm = llm
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a data scientist specializing in creating measurable 
signals for compliance health monitoring.

Your expertise: Feature engineering, signal processing, predictive indicators, 
continuous monitoring systems

Your task is to REASON about converting binary compliance (pass/fail) into 
continuous signals that can be modeled.

Universal Signal Categories:
1. TIMELINESS - Delays, overdue items
2. COMPLETENESS - Missing evidence, tasks
3. ADHERENCE - Rule violations
4. DRIFT - Configuration drift, training drift
5. INCIDENT FREQUENCY - Failures, incidents
6. EXCEPTIONS - Logged exceptions
7. RESPONSIVENESS - Owner response time
8. MATURITY - Control maturity level

For each control, identify measurable signals across these categories.

Think like a data scientist designing a monitoring system - explain your 
reasoning about signal selection, measurement methods, and thresholds.

You do NOT:
- Execute measurements
- Write code
- Collect actual data

Output: Natural language reasoning about signal design."""),
            ("human", "{input}")
        ])
    
    def __call__(self, state: RiskModelReasoningState) -> RiskModelReasoningState:
        """Generate measurable signals reasoning."""
        
        controls = state.get("controls", [])
        framework = state.get("compliance_framework", "")
        domain = state.get("domain_context", {})
        signal_patterns = state.get("existing_signal_patterns", [])
        
        chain = self.prompt | self.llm
        
        response = chain.invoke({
            "input": f"""Analyze controls and reason about measurable signals for compliance health.

CONTROLS TO ANALYZE:
{chr(10).join(f"Control {i+1}: {c.get('control_name', 'Unknown')} - {c.get('description', '')[:200]}..." 
              for i, c in enumerate(controls[:5]))}

FRAMEWORK: {framework}
DOMAIN CONTEXT: {domain.get('domain_name', 'Generic')}

EXISTING SIGNAL PATTERNS (for reference):
{signal_patterns[:2] if signal_patterns else 'No patterns available'}

As a data scientist, provide REASONING about measurable signals:

1. SIGNAL IDENTIFICATION PER CATEGORY:

   For each control, identify signals across these universal categories:
   
   A. TIMELINESS SIGNALS:
      - What delays or overdue items can be measured?
      - How would you quantify timeliness?
      - What data source would provide this?
      Example: "Days overdue for access reviews" - measures process discipline
   
   B. COMPLETENESS SIGNALS:
      - What missing evidence or tasks can be measured?
      - How would you calculate completeness percentage?
      - What constitutes "complete"?
      Example: "Evidence completeness rate" - % of required artifacts present
   
   C. ADHERENCE SIGNALS:
      - What rule violations can be measured?
      - How would you detect non-adherence?
      - What's the measurement unit?
      Example: "Unauthorized access attempts" - count of violations
   
   D. DRIFT SIGNALS:
      - What configuration or training drift can be measured?
      - How would you detect drift from baseline?
      - What comparison method makes sense?
      Example: "Config drift from baseline" - % of changed settings
   
   E. INCIDENT FREQUENCY:
      - What failures or incidents can be counted?
      - How would you normalize frequency?
      - What time period is appropriate?
      Example: "Control failures per quarter" - failure rate
   
   F. EXCEPTIONS:
      - What exceptions can be logged and counted?
      - How do exceptions indicate control health?
      - What patterns matter?
      Example: "Approved exceptions count" - volume of workarounds
   
   G. RESPONSIVENESS:
      - What response times can be measured?
      - Who are the owners to track?
      - What actions trigger measurement?
      Example: "Owner response time to issues" - hours to acknowledge
   
   H. MATURITY:
      - How can control maturity be scored?
      - What dimensions of maturity matter?
      - How does maturity evolve?
      Example: "Control maturity level" - CMM-style 1-5 rating

2. SIGNAL DESIGN REASONING:

   For each proposed signal:
   
   - METRIC FORMULA: How would you calculate this signal?
     Natural language formula, not code
     
   - UNIT OF MEASURE: What's the measurement unit?
     Days, count, percentage, score, etc.
     
   - HEALTHY RANGE: What values indicate good compliance health?
     What's the normal/expected range?
     
   - WARNING THRESHOLD: When should you be concerned?
     At what value does this signal indicate risk?
     
   - CRITICAL THRESHOLD: When is immediate action needed?
     What value indicates imminent failure?
     
   - DATA SOURCES: Where does measurement data come from?
     Specific systems or logs
     
   - COLLECTION FREQUENCY: How often to measure?
     Real-time, daily, weekly, monthly?
     
   - WHY THIS SIGNAL: Why is this signal important?
     What does it tell us about compliance health?
     
   - PREDICTIVE POWER: How does it predict control failure?
     What's the causal relationship?

3. CROSS-DOMAIN APPLICABILITY:

   - Which signals are universal (work for any compliance type)?
   - Which signals need domain-specific adjustments?
   - How would you adapt signals for different frameworks?
   - What patterns are common across domains?

4. SIGNAL PORTFOLIO DESIGN:

   - What's the right number of signals per control?
   - How do signals complement each other?
   - Are there redundant signals?
   - What's the minimum viable signal set?

5. FROM BINARY TO CONTINUOUS:

   For each control:
   - Old binary approach: "Access reviews completed? Yes/No"
   - New continuous approach: "Days overdue: 0-30+; Completeness: 85-100%"
   
   Explain how continuous signals provide richer information for modeling.

Structure your reasoning so it can guide signal implementation."""
        })
        
        state["signal_identification_reasoning"] = response.content
        
        # Create structured signal proposals
        state["proposed_signals"] = [
            {
                "signal_id": "SIG-TIMELINESS-001",
                "signal_name": "Task Completion Timeliness",
                "category": "timeliness",
                "reasoning": "Extracted from agent response..."
            }
        ]
        
        state["messages"].append(
            AIMessage(content="Measurable signals reasoning complete")
        )
        state["current_step"] = "signals_reasoning_complete"
        
        return state


# ============================================================================
# LIKELIHOOD MODEL REASONING AGENT
# ============================================================================

class LikelihoodModelReasoningAgent:
    """
    Data scientist reasoning agent that defines likelihood model inputs.
    
    Creates generic features that predict "How likely is this control to fail?"
    """
    
    def __init__(self, llm: ChatAnthropic):
        self.llm = llm
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a data scientist specializing in predictive modeling 
for compliance risk.

Your expertise: Predictive analytics, machine learning features, probability estimation

Your task is to REASON about inputs for a likelihood model that answers:
"How likely is this control to fail?"

Universal Likelihood Drivers:
1. Historical failure rate
2. Control drift frequency
3. Evidence quality score
4. Process volatility
5. Human dependency
6. Operational load
7. Control maturity level

Define features that work across ALL compliance types (SOC2, HIPAA, HR, finance, etc.)

Think like a data scientist building a predictive model - explain feature 
engineering, data requirements, and how features predict failure.

You do NOT:
- Train actual models
- Write code
- Execute predictions

Output: Natural language reasoning about likelihood modeling."""),
            ("human", "{input}")
        ])
    
    def __call__(self, state: RiskModelReasoningState) -> RiskModelReasoningState:
        """Generate likelihood model reasoning."""
        
        controls = state.get("controls", [])
        signals_reasoning = state.get("signal_identification_reasoning", "")
        benchmarks = state.get("industry_benchmarks", {})
        
        chain = self.prompt | self.llm
        
        response = chain.invoke({
            "input": f"""Design likelihood model inputs that work across all compliance domains.

CONTROLS CONTEXT:
{chr(10).join(f"Control {i+1}: {c.get('control_name', 'Unknown')}" 
              for i, c in enumerate(controls[:5]))}

SIGNALS IDENTIFIED (from previous reasoning):
{signals_reasoning[:1000] if signals_reasoning else 'Not available'}...

INDUSTRY BENCHMARKS:
{benchmarks}

As a data scientist, provide REASONING about likelihood model inputs:

1. UNIVERSAL LIKELIHOOD DRIVERS:

   For each driver, define a feature:
   
   A. HISTORICAL FAILURE RATE:
      - How would you measure past failures?
      - What time window is appropriate?
      - How do you handle controls with no history?
      - Calculation method: e.g., "failures in past 12 months / review periods"
      - Data source: Audit findings, control testing results
      - Interpretation: 0 = low likelihood, >2/quarter = high likelihood
      - Reasoning: Past behavior predicts future behavior
      - Evidence: Industry data shows 70% of failures have prior history
   
   B. CONTROL DRIFT FREQUENCY:
      - What constitutes drift?
      - How do you detect and quantify drift?
      - Why does drift predict failure?
      - Calculation method: Changes from baseline configuration
      - Reasoning: Drift indicates degrading control effectiveness
   
   C. EVIDENCE QUALITY SCORE:
      - What dimensions define quality?
      - How do you score evidence quality?
      - Missing, outdated, incomplete - how to quantify?
      - Reasoning: Poor evidence indicates poor control execution
   
   D. PROCESS VOLATILITY:
      - How do you measure process change frequency?
      - Why does volatility increase failure likelihood?
      - What change events to track?
      - Reasoning: Frequent changes disrupt control stability
   
   E. HUMAN DEPENDENCY:
      - How do you score manual vs automated?
      - What makes a process "human-dependent"?
      - Why does manual increase likelihood?
      - Reasoning: Human error rates exceed automated error rates
   
   F. OPERATIONAL LOAD:
      - How do you measure load (users, transactions, systems)?
      - Why does scale increase failure likelihood?
      - How to normalize across different control types?
      - Reasoning: More operations = more opportunities for failure
   
   G. CONTROL MATURITY LEVEL:
      - What maturity model to use (CMM-style)?
      - How to assess maturity consistently?
      - Why does low maturity predict failure?
      - Reasoning: Immature controls lack robust processes

2. FEATURE ENGINEERING REASONING:

   For each likelihood input:
   
   - INPUT DEFINITION: What exactly does this feature measure?
   - CALCULATION METHOD: How to calculate (natural language)?
   - DATA SOURCES: Where does data come from?
   - UNIT OF MEASURE: What's the measurement unit?
   - RANGES: What values indicate low/medium/high likelihood?
   - CROSS-DOMAIN APPLICABILITY: How does this work for different frameworks?
   - DOMAIN ADJUSTMENTS: What adjustments are needed per domain?
   - WHY IT PREDICTS: Explain the causal relationship
   - EVIDENCE: What evidence supports predictive power?

3. MODEL ARCHITECTURE REASONING:

   - How should these inputs combine?
   - Additive? Multiplicative? Non-linear?
   - Should inputs be weighted? How?
   - What's the baseline likelihood?
   - How do you handle missing data for an input?
   - What transformations are needed?

4. APPLICABILITY ACROSS DOMAINS:

   Show how each input works for different compliance types:
   - SOC2 Security: Historical failure rate = failed penetration tests
   - HIPAA: Historical failure rate = PHI access violations
   - HR Compliance: Historical failure rate = missed training deadlines
   - Financial: Historical failure rate = reconciliation errors
   
   Demonstrate universality.

5. VALIDATION APPROACH:

   - How would you validate that these inputs predict likelihood?
   - What metrics would you use?
   - How would you test the model?
   - What would constitute success?

Structure your reasoning to guide likelihood model implementation."""
        })
        
        state["likelihood_modeling_reasoning"] = response.content
        
        # Create structured likelihood inputs
        state["proposed_likelihood_inputs"] = [
            {
                "input_id": "LH-HIST-001",
                "input_name": "Historical Failure Rate",
                "driver": "historical_failure",
                "reasoning": "From agent response..."
            }
        ]
        
        state["messages"].append(
            AIMessage(content="Likelihood model reasoning complete")
        )
        state["current_step"] = "likelihood_reasoning_complete"
        
        return state


# ============================================================================
# IMPACT MODEL REASONING AGENT
# ============================================================================

class ImpactModelReasoningAgent:
    """
    Data scientist reasoning agent that defines impact model inputs.
    
    Creates generic features that predict "If this fails, what is the consequence?"
    """
    
    def __init__(self, llm: ChatAnthropic):
        self.llm = llm
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a data scientist specializing in impact assessment 
and consequence modeling for compliance.

Your expertise: Multi-dimensional impact analysis, severity scoring, consequence quantification

Your task is to REASON about inputs for an impact model that answers:
"If this control fails, what is the consequence?"

Universal Impact Dimensions:
1. Regulatory severity
2. Customer trust / brand sensitivity
3. Financial impact
4. Operational disruption
5. Downstream dependency
6. Crown jewel relevance

Define features that work across ALL compliance types.

Think like a data scientist building an impact model - explain dimension 
selection, quantification approaches, and aggregation methods.

You do NOT:
- Calculate actual impacts
- Write code
- Perform assessments

Output: Natural language reasoning about impact modeling."""),
            ("human", "{input}")
        ])
    
    def __call__(self, state: RiskModelReasoningState) -> RiskModelReasoningState:
        """Generate impact model reasoning."""
        
        controls = state.get("controls", [])
        domain = state.get("domain_context", {})
        likelihood_reasoning = state.get("likelihood_modeling_reasoning", "")
        
        chain = self.prompt | self.llm
        
        response = chain.invoke({
            "input": f"""Design impact model inputs that work across all compliance domains.

CONTROLS CONTEXT:
{chr(10).join(f"Control {i+1}: {c.get('control_name', 'Unknown')}" 
              for i, c in enumerate(controls[:5]))}

DOMAIN: {domain.get('domain_name', 'Generic')}

LIKELIHOOD MODEL (for context):
{likelihood_reasoning[:500] if likelihood_reasoning else 'Not available'}...

As a data scientist, provide REASONING about impact model inputs:

1. UNIVERSAL IMPACT DIMENSIONS:

   For each dimension, define a feature:
   
   A. REGULATORY SEVERITY:
      - How do you score regulatory severity?
      - How to map controls to penalty tiers?
      - Cross-framework severity comparison?
      - Calculation method: Map to penalty tier (Tier 1 = low, Tier 2 = high)
      - Data source: Regulatory framework mappings, legal assessments
      - Interpretation: Tier 1 = low impact, Tier 2 = high impact
      - Reasoning: Regulatory penalties directly quantify financial impact
      - Quantification: Use penalty tier as multiplier
   
   B. CUSTOMER TRUST / BRAND SENSITIVITY:
      - How do you quantify brand impact?
      - What makes some controls more brand-sensitive?
      - How to measure reputational damage?
      - Reasoning: Some failures damage trust more than others
      - Examples: PHI breach vs internal audit finding
   
   C. FINANCIAL IMPACT:
      - What cost components to include?
      - Fines, remediation, lost revenue, etc.?
      - How to estimate potential costs?
      - Reasoning: Direct monetary consequences
      - Quantification: Sum of potential cost components
   
   D. OPERATIONAL DISRUPTION:
      - How do you measure disruption severity?
      - Process downtime? Recovery time? Staff impact?
      - How to normalize across different operations?
      - Reasoning: Operational impact affects business continuity
   
   E. DOWNSTREAM DEPENDENCY:
      - How do you count dependent controls?
      - How does dependency amplify impact?
      - Network effects and cascades?
      - Calculation: Count of controls that depend on this one
      - Reasoning: Cascading failures multiply impact
      - Quantification: Impact increases logarithmically with dependencies
   
   F. CROWN JEWEL RELEVANCE:
      - What makes a system/process a "crown jewel"?
      - How do you identify critical systems?
      - How does criticality affect impact?
      - Reasoning: Failures affecting critical systems have outsized impact

2. FEATURE ENGINEERING REASONING:

   For each impact input:
   
   - INPUT DEFINITION: What does this feature measure?
   - CALCULATION METHOD: How to calculate?
   - DATA SOURCES: Where does data come from?
   - UNIT OF MEASURE: What's the unit?
   - RANGES: Low/medium/high impact values?
   - CROSS-DOMAIN APPLICABILITY: How does this work universally?
   - DOMAIN ADJUSTMENTS: What adjustments needed per domain?
   - QUANTIFICATION APPROACH: How to make it numeric?
   - WHY IT MATTERS: Explain the consequence mechanism

3. MULTI-DIMENSIONAL AGGREGATION:

   - How should these dimensions combine?
   - Weighted average? Maximum? Multiplicative?
   - What weights for each dimension?
   - How to handle one very high dimension vs all moderate?
   - What's the final impact scale (1-5, 1-100)?

4. IMPACT PORTABILITY ACROSS DOMAINS:

   Show how each dimension works for different compliance types:
   
   - SOC2: Regulatory severity = audit finding level
   - HIPAA: Regulatory severity = OCR penalty tier
   - HR: Regulatory severity = EEOC violation class
   - Finance: Regulatory severity = SEC enforcement level
   
   Demonstrate how same framework applies everywhere.

5. INTERACTION WITH LIKELIHOOD:

   - How does impact combine with likelihood for risk?
   - Risk = Likelihood × Impact (how exactly)?
   - Are some impacts likelihood-dependent?
   - How to normalize the combination?

6. DYNAMIC vs STATIC IMPACT:

   - Which impact factors are static (don't change often)?
   - Which are dynamic (change with conditions)?
   - How often to recalculate impact?
   - What triggers impact reassessment?

Structure your reasoning to guide impact model implementation."""
        })
        
        state["impact_modeling_reasoning"] = response.content
        
        # Create structured impact inputs
        state["proposed_impact_inputs"] = [
            {
                "input_id": "IMP-REG-001",
                "input_name": "Regulatory Severity Level",
                "dimension": "regulatory_severity",
                "reasoning": "From agent response..."
            }
        ]
        
        state["messages"].append(
            AIMessage(content="Impact model reasoning complete")
        )
        state["current_step"] = "impact_reasoning_complete"
        
        return state


# ============================================================================
# CONTEXTUAL FACTORS REASONING AGENT
# ============================================================================

class ContextualFactorsReasoningAgent:
    """
    Data scientist reasoning agent that identifies contextual factors
    that modify risk assessment.
    """
    
    def __init__(self, llm: ChatAnthropic):
        self.llm = llm
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a data scientist specializing in contextual modeling 
for risk assessment.

Your expertise: Context-aware modeling, risk modifiers, temporal factors

Your task is to REASON about contextual factors that modify risk assessment:

Universal Contextual Factors:
1. TEMPORAL: Time since last review, seasonal patterns
2. ORGANIZATIONAL: Control owner capability, team size
3. DATA SENSITIVITY: Classification level, data criticality
4. POPULATION: Affected employees, transactions, systems

These factors adjust base risk (Likelihood × Impact).

Think like a data scientist adding context to a model - explain what factors 
matter, how they modify risk, and how to measure them.

You do NOT:
- Execute adjustments
- Write code
- Calculate modifiers

Output: Natural language reasoning about contextual factors."""),
            ("human", "{input}")
        ])
    
    def __call__(self, state: RiskModelReasoningState) -> RiskModelReasoningState:
        """Generate contextual factors reasoning."""
        
        controls = state.get("controls", [])
        likelihood_reasoning = state.get("likelihood_modeling_reasoning", "")
        impact_reasoning = state.get("impact_modeling_reasoning", "")
        
        chain = self.prompt | self.llm
        
        response = chain.invoke({
            "input": f"""Design contextual factors that modify risk assessment universally.

CONTROLS CONTEXT:
{chr(10).join(f"Control {i+1}: {c.get('control_name', 'Unknown')}" 
              for i, c in enumerate(controls[:5]))}

LIKELIHOOD MODEL (context):
{likelihood_reasoning[:500] if likelihood_reasoning else 'Not available'}...

IMPACT MODEL (context):
{impact_reasoning[:500] if impact_reasoning else 'Not available'}...

As a data scientist, provide REASONING about contextual factors:

1. TEMPORAL FACTORS:

   A. TIME SINCE LAST REVIEW:
      - How does staleness affect risk?
      - What's the decay function?
      - Measurement: Days since last review
      - Effect on likelihood: Increases with time (review drift)
      - Effect on impact: Minimal direct effect
      - Adjustment formula: Likelihood multiplier = 1 + (days/365) × 0.5
      - Reasoning: Older reviews miss current risks
   
   B. SEASONAL PATTERNS:
      - Do certain times have higher risk?
      - Year-end close, audit season, peak business?
      - How to model seasonality?
      - Reasoning: Load patterns affect likelihood

2. ORGANIZATIONAL FACTORS:

   A. CONTROL OWNER CAPABILITY:
      - How to assess owner capability?
      - Experience, certifications, track record?
      - Measurement approach: Capability score (1-5)
      - Effect: Higher capability = lower likelihood
      - Reasoning: Skilled owners execute better
   
   B. TEAM SIZE / RESOURCES:
      - How does team size affect risk?
      - Adequate resources vs understaffed?
      - Reasoning: Under-resourced teams have higher failure rates

3. DATA SENSITIVITY FACTORS:

   A. DATA CLASSIFICATION LEVEL:
      - How does sensitivity affect impact?
      - Public vs Confidential vs Secret?
      - Measurement: Map to sensitivity tier (1-5)
      - Effect on impact: Direct multiplier
      - Reasoning: More sensitive data = higher consequence
   
   B. CROWN JEWEL DATA:
      - What data is most critical?
      - How to identify crown jewels?
      - Reasoning: Crown jewel failures have outsized impact

4. POPULATION FACTORS:

   A. POPULATION AFFECTED:
      - How many employees/transactions/systems affected?
      - Measurement: Count or volume
      - Effect: Larger population = higher likelihood AND impact
      - Reasoning: Scale increases both probability and consequence
   
   B. AFFECTED POPULATION CRITICALITY:
      - Not all populations equal - executives vs general staff?
      - How to weight by criticality?
      - Reasoning: Some populations more impactful

5. CONTEXTUAL ADJUSTMENT FRAMEWORK:

   - How do contextual factors combine?
   - Multiplicative? Additive?
   - What's the adjustment formula?
   - Base Risk = Likelihood × Impact
   - Adjusted Risk = Base Risk × Context Multiplier
   
   Example:
   Base Risk = 12 (Likelihood 3 × Impact 4)
   Context Multipliers:
   - Time factor: 1.2 (review is old)
   - Capability factor: 0.8 (strong owner)
   - Sensitivity factor: 1.5 (high sensitivity)
   
   Adjusted Risk = 12 × 1.2 × 0.8 × 1.5 = 17.28

6. CROSS-DOMAIN APPLICABILITY:

   Show how contextual factors work universally:
   - SOC2: Population = number of systems monitored
   - HIPAA: Population = patient records affected
   - HR: Population = employees covered
   - Finance: Population = transactions processed

7. DYNAMIC CONTEXT:

   - Which factors change frequently? (daily, weekly, monthly)
   - Which are static? (annual review)
   - How to handle real-time context updates?
   - What's the recalculation trigger?

Structure your reasoning to guide contextual modeling."""
        })
        
        state["contextual_factors_reasoning"] = response.content
        
        # Create structured contextual factors
        state["proposed_contextual_factors"] = [
            {
                "factor_id": "CTX-TIME-001",
                "factor_name": "Time Since Last Review",
                "type": "temporal",
                "reasoning": "From agent response..."
            }
        ]
        
        state["messages"].append(
            AIMessage(content="Contextual factors reasoning complete")
        )
        state["current_step"] = "contextual_reasoning_complete"
        
        return state


# ============================================================================
# RISK MODEL INTEGRATION AGENT
# ============================================================================

class RiskModelIntegrationAgent:
    """
    Agent that synthesizes all reasoning into complete risk model blueprint.
    """
    
    def __init__(self, llm: ChatAnthropic):
        self.llm = llm
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a senior data scientist architecting a complete 
risk modeling system for compliance.

Your task is to INTEGRATE all reasoning into a cohesive risk model blueprint:
- Measurable signals
- Likelihood model inputs
- Impact model inputs
- Contextual factors

Create a complete model design that works across ALL compliance domains.

Output: Integrated risk model architecture and implementation blueprint."""),
            ("human", "{input}")
        ])
    
    def __call__(self, state: RiskModelReasoningState) -> RiskModelReasoningState:
        """Integrate all reasoning into risk model blueprint."""
        
        signals_reasoning = state.get("signal_identification_reasoning", "")
        likelihood_reasoning = state.get("likelihood_modeling_reasoning", "")
        impact_reasoning = state.get("impact_modeling_reasoning", "")
        contextual_reasoning = state.get("contextual_factors_reasoning", "")
        
        chain = self.prompt | self.llm
        
        response = chain.invoke({
            "input": f"""Integrate all risk modeling reasoning into complete blueprint.

SIGNALS REASONING:
{signals_reasoning[:800]}...

LIKELIHOOD MODEL REASONING:
{likelihood_reasoning[:800]}...

IMPACT MODEL REASONING:
{impact_reasoning[:800]}...

CONTEXTUAL FACTORS REASONING:
{contextual_reasoning[:800]}...

Provide INTEGRATION REASONING:

1. COMPLETE MODEL ARCHITECTURE:
   
   Show how all components fit together:
   
   SIGNALS (Continuous monitoring)
        ↓
   Feed into
        ↓
   LIKELIHOOD MODEL ← Contextual factors
        ×
   IMPACT MODEL ← Contextual factors
        ↓
   RISK SCORE
   
   Explain the data flow and connections.

2. SIGNAL-TO-RISK MAPPING:
   
   - How do signals inform likelihood?
   - How do signals inform impact?
   - Which signals are leading indicators?
   - How to aggregate signal information?

3. MODEL EXECUTION FLOW:
   
   Step-by-step reasoning:
   1. Collect signals (continuous)
   2. Calculate likelihood inputs
   3. Calculate impact inputs
   4. Apply contextual factors
   5. Compute base risk = L × I
   6. Adjust risk with context
   7. Classify risk level
   8. Trigger actions based on thresholds

4. CROSS-DOMAIN VALIDATION:
   
   Show how this model works for:
   - SOC2 security controls
   - HIPAA privacy controls
   - HR compliance controls
   - Financial controls
   
   Demonstrate universality with examples.

5. IMPLEMENTATION BLUEPRINT:
   
   - What needs to be built?
   - Data collection requirements
   - Calculation pipeline
   - Storage and tracking
   - Monitoring and alerting
   - Reporting and visualization

6. MODEL MAINTENANCE:
   
   - How often to recalibrate?
   - What triggers model updates?
   - How to validate ongoing accuracy?
   - How to handle model drift?

7. SCALABILITY AND PERFORMANCE:
   
   - How does this scale to 1000s of controls?
   - Real-time vs batch processing?
   - Computational requirements?

Provide a complete blueprint ready for execution teams."""
        })
        
        # Create comprehensive blueprint
        blueprint = {
            "integration_reasoning": response.content,
            "signals": state.get("proposed_signals", []),
            "likelihood_inputs": state.get("proposed_likelihood_inputs", []),
            "impact_inputs": state.get("proposed_impact_inputs", []),
            "contextual_factors": state.get("proposed_contextual_factors", []),
            "model_architecture": "Signals → Likelihood × Impact × Context = Risk",
            "domain_agnostic": True,
            "ready_for_implementation": True
        }
        
        state["risk_model_blueprint"] = blueprint
        
        state["messages"].append(
            AIMessage(content="Risk model blueprint integration complete")
        )
        state["current_step"] = "integration_complete"
        
        return state


# ============================================================================
# WORKFLOW ORCHESTRATION
# ============================================================================

class RiskModelReasoningWorkflow:
    """
    LangGraph workflow that orchestrates all data science planner agents.
    """
    
    def __init__(self, anthropic_api_key: str):
        """Initialize the workflow."""
        
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            anthropic_api_key=anthropic_api_key,
            temperature=0.2
        )
        
        # Initialize all agents
        self.signals_agent = MeasurableSignalsReasoningAgent(self.llm)
        self.likelihood_agent = LikelihoodModelReasoningAgent(self.llm)
        self.impact_agent = ImpactModelReasoningAgent(self.llm)
        self.contextual_agent = ContextualFactorsReasoningAgent(self.llm)
        self.integration_agent = RiskModelIntegrationAgent(self.llm)
        
        # Build graph
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        
        workflow = StateGraph(RiskModelReasoningState)
        
        # Add all agent nodes
        workflow.add_node("signals", self.signals_agent)
        workflow.add_node("likelihood", self.likelihood_agent)
        workflow.add_node("impact", self.impact_agent)
        workflow.add_node("contextual", self.contextual_agent)
        workflow.add_node("integration", self.integration_agent)
        
        # Define workflow
        workflow.set_entry_point("signals")
        workflow.add_edge("signals", "likelihood")
        workflow.add_edge("likelihood", "impact")
        workflow.add_edge("impact", "contextual")
        workflow.add_edge("contextual", "integration")
        workflow.add_edge("integration", END)
        
        return workflow.compile()
    
    def run(
        self,
        controls: List[Dict],
        compliance_framework: str,
        domain_context: Optional[Dict] = None,
        signal_patterns: Optional[List[Dict]] = None,
        benchmarks: Optional[Dict] = None,
        historical_models: Optional[List[Dict]] = None
    ) -> RiskModelReasoningState:
        """Execute the risk model reasoning workflow."""
        
        initial_state = RiskModelReasoningState(
            controls=controls,
            compliance_framework=compliance_framework,
            domain_context=domain_context,
            existing_signal_patterns=signal_patterns,
            industry_benchmarks=benchmarks,
            historical_models=historical_models,
            signal_identification_reasoning=None,
            likelihood_modeling_reasoning=None,
            impact_modeling_reasoning=None,
            contextual_factors_reasoning=None,
            proposed_signals=None,
            proposed_likelihood_inputs=None,
            proposed_impact_inputs=None,
            proposed_contextual_factors=None,
            risk_model_blueprint=None,
            messages=[HumanMessage(content="Starting risk model reasoning")],
            current_step="initialized"
        )
        
        final_state = self.graph.invoke(initial_state)
        
        return final_state


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_risk_model_workflow(api_key: str) -> RiskModelReasoningWorkflow:
    """Factory function to create risk model reasoning workflow."""
    return RiskModelReasoningWorkflow(anthropic_api_key=api_key)


def extract_risk_model_blueprint(state: RiskModelReasoningState) -> Dict:
    """Extract the complete risk model blueprint."""
    return {
        "blueprint": state.get("risk_model_blueprint", {}),
        "signals_reasoning": state.get("signal_identification_reasoning", ""),
        "likelihood_reasoning": state.get("likelihood_modeling_reasoning", ""),
        "impact_reasoning": state.get("impact_modeling_reasoning", ""),
        "contextual_reasoning": state.get("contextual_factors_reasoning", "")
    }

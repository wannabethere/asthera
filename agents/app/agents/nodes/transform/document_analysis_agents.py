"""
Document Analysis Reasoning Agents
==================================

Reasoning agents that analyze compliance documents and generate:
1. Domain context definitions
2. Control-requirement-evidence structures
3. Measurable expectations
4. Risk assessments using risk matrices

All agents produce REASONING PLANS only - no execution.
"""

from typing import TypedDict, List, Dict, Annotated, Optional
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
import operator

from control_universe_model import (
    ComplianceControlUniverse,
    Control,
    SubControl,
    EvidenceType,
    MeasurableExpectation,
    DomainContext,
    LikelihoodLevel,
    ImpactLevel
)


# ============================================================================
# STATE DEFINITION
# ============================================================================

class ControlUniverseReasoningState(TypedDict):
    """
    State for document analysis and control universe definition reasoning.
    """
    
    # Input documents
    source_documents: List[Dict[str, str]]  # List of documents to analyze
    compliance_framework: str                # Target framework (HIPAA, SOC2, etc)
    
    # Knowledge bases (read-only)
    existing_control_patterns: Optional[List[Dict]]
    industry_benchmarks: Optional[Dict]
    historical_examples: Optional[List[Dict]]
    
    # Reasoning outputs (natural language plans)
    domain_definition_reasoning: Optional[str]
    control_identification_reasoning: Optional[str]
    measurable_expectations_reasoning: Optional[str]
    evidence_mapping_reasoning: Optional[str]
    risk_assessment_reasoning: Optional[str]
    
    # Structured reasoning outputs (still plans, not execution)
    identified_controls: Optional[List[Dict]]
    identified_requirements: Optional[List[Dict]]
    proposed_measurable_expectations: Optional[List[Dict]]
    proposed_evidence_types: Optional[List[Dict]]
    risk_matrix_reasoning: Optional[Dict]
    
    # Integrated output
    control_universe_blueprint: Optional[Dict]
    
    # Workflow tracking
    messages: Annotated[List[BaseMessage], operator.add]
    current_step: str


# ============================================================================
# DOMAIN CONTEXT REASONING AGENT
# ============================================================================

class DomainContextReasoningAgent:
    """
    Reasoning agent that analyzes documents to define domain context.
    
    Outputs natural language reasoning about:
    - What domain this represents
    - What processes are involved
    - What data categories exist
    - What stakeholders are relevant
    - What compliance frameworks apply
    """
    
    def __init__(self, llm: ChatAnthropic):
        self.llm = llm
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a compliance domain expert who analyzes documents to 
understand organizational context.

Your task is to READ compliance documents and REASON about:
1. What domain/industry this organization operates in
2. What business processes are described
3. What types of data are mentioned
4. What systems and stakeholders are involved
5. What compliance frameworks are applicable

Output REASONING in natural language - explain your thought process about 
how you identified these domain elements.

You do NOT:
- Execute queries
- Write code
- Make definitive determinations (reason about possibilities)"""),
            ("human", "{input}")
        ])
    
    def __call__(self, state: ControlUniverseReasoningState) -> ControlUniverseReasoningState:
        """Generate domain context reasoning from documents."""
        
        documents = state.get("source_documents", [])
        framework = state.get("compliance_framework", "")
        examples = state.get("historical_examples", [])
        
        chain = self.prompt | self.llm
        
        response = chain.invoke({
            "input": f"""Analyze these compliance documents and reason about the domain context:

DOCUMENTS TO ANALYZE:
{chr(10).join(f"Document {i+1}: {doc.get('title', 'Untitled')} - {doc.get('content', '')[:500]}..." 
              for i, doc in enumerate(documents))}

TARGET FRAMEWORK: {framework}

HISTORICAL EXAMPLES (for pattern recognition):
{examples[:2] if examples else 'No examples available'}

Provide REASONING about:

1. DOMAIN IDENTIFICATION:
   - What industry/domain does this represent? Why?
   - What clues in the documents indicate this domain?
   - What similar domains have you seen in examples?

2. BUSINESS PROCESSES:
   - What business processes are described or implied?
   - How do you know these are key processes?
   - What criticality do they have (and why)?

3. DATA CATEGORIES:
   - What types of data are mentioned?
   - How sensitive is each category (reasoning)?
   - What compliance implications exist for each?

4. SYSTEM COMPONENTS:
   - What systems or technologies are referenced?
   - What role do they play in compliance?
   - How do they interact?

5. STAKEHOLDERS:
   - Who are the key people/roles involved?
   - What responsibilities do they have?
   - How did you identify them from the documents?

6. APPLICABLE FRAMEWORKS:
   - Why does {framework} apply?
   - What other frameworks might be relevant?
   - What in the documents suggests this?

Provide your REASONING as structured natural language."""
        })
        
        state["domain_definition_reasoning"] = response.content
        
        state["messages"].append(
            AIMessage(content="Domain context reasoning complete")
        )
        state["current_step"] = "domain_reasoning_complete"
        
        return state


# ============================================================================
# CONTROL IDENTIFICATION REASONING AGENT
# ============================================================================

class ControlIdentificationReasoningAgent:
    """
    Reasoning agent that identifies controls from documents.
    
    Produces reasoning about:
    - What controls are described in documents
    - How to structure the control hierarchy
    - What control objectives exist
    - How controls map to frameworks
    """
    
    def __init__(self, llm: ChatAnthropic):
        self.llm = llm
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a compliance controls expert who identifies and structures 
compliance requirements from documents.

Your task is to READ documents and REASON about:
1. What high-level controls are described
2. What specific sub-controls or requirements exist
3. How to organize the control hierarchy
4. What control objectives are being met

Use the Control-Requirement-Evidence model:
- Controls: High-level requirements (e.g., "Access Control")
- Sub-Controls: Specific measurable requirements (e.g., "Quarterly access reviews")
- Evidence: What proves compliance

Output REASONING in natural language - explain how you identified controls 
and why you structured them this way.

You do NOT:
- Execute analysis
- Write control implementations
- Make definitive classifications (reason about them)"""),
            ("human", "{input}")
        ])
    
    def __call__(self, state: ControlUniverseReasoningState) -> ControlUniverseReasoningState:
        """Generate control identification reasoning."""
        
        documents = state.get("source_documents", [])
        framework = state.get("compliance_framework", "")
        domain_reasoning = state.get("domain_definition_reasoning", "")
        control_patterns = state.get("existing_control_patterns", [])
        
        chain = self.prompt | self.llm
        
        response = chain.invoke({
            "input": f"""Analyze documents and reason about control identification:

DOCUMENTS:
{chr(10).join(f"Document {i+1}: {doc.get('title', 'Untitled')} - {doc.get('content', '')[:500]}..." 
              for i, doc in enumerate(documents))}

FRAMEWORK: {framework}

DOMAIN CONTEXT REASONING (from previous agent):
{domain_reasoning[:1000]}...

KNOWN CONTROL PATTERNS (from knowledge base):
{control_patterns[:3] if control_patterns else 'No patterns available'}

Provide REASONING about:

1. HIGH-LEVEL CONTROL IDENTIFICATION:
   - What major controls are described in the documents?
   - How did you identify them (what keywords/phrases)?
   - How do they map to {framework} control categories?
   - What control IDs would you assign (and why)?

2. CONTROL HIERARCHY:
   - How should these controls be organized?
   - What's the parent-child structure?
   - Why this hierarchy (what's the logic)?

3. SUB-CONTROL/REQUIREMENT IDENTIFICATION:
   - What specific requirements exist under each control?
   - How are they distinct from the parent control?
   - What makes each one measurable?
   - How did you extract them from document text?

4. CONTROL OBJECTIVES:
   - What is each control trying to achieve?
   - How do you know this is the objective?
   - How does it relate to the domain context?

5. CONTROL OWNERSHIP:
   - Who owns each control (based on documents)?
   - How did you determine ownership?
   - What if ownership is unclear?

For each identified control, provide:
- Proposed control ID
- Control name
- Category
- Justification for identification
- Source text that led to identification
- Confidence level in identification

Structure your reasoning clearly so it can guide control definition."""
        })
        
        state["control_identification_reasoning"] = response.content
        
        # Also create structured list of identified controls
        # (This is still reasoning/planning, not execution)
        state["identified_controls"] = [
            {
                "control_id": "IDENTIFIED-001",
                "reasoning": "Extracted from document section X because...",
                "confidence": "high"
            }
            # In real implementation, would parse from LLM response
        ]
        
        state["messages"].append(
            AIMessage(content="Control identification reasoning complete")
        )
        state["current_step"] = "control_identification_complete"
        
        return state


# ============================================================================
# MEASURABLE EXPECTATIONS REASONING AGENT
# ============================================================================

class MeasurableExpectationsReasoningAgent:
    """
    Data scientist reasoning agent that defines measurable expectations.
    
    Creates reasoning plans for:
    - How to make requirements measurable
    - What metrics to use
    - What success/failure criteria should be
    - How to test compliance
    """
    
    def __init__(self, llm: ChatAnthropic):
        self.llm = llm
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a data scientist specializing in creating measurable 
expectations for compliance requirements.

Your expertise: Defining metrics, success criteria, testing approaches, data collection methods

Your task is to REASON about how to make compliance requirements measurable:
1. What metrics would quantify compliance
2. What data sources would provide evidence
3. What constitutes success vs failure
4. How to test compliance objectively

Think like a data scientist designing a measurement system - explain your 
reasoning about metric selection and validation approaches.

You do NOT:
- Execute measurements
- Write testing code
- Collect actual data

Output: Natural language reasoning about measurement design."""),
            ("human", "{input}")
        ])
    
    def __call__(self, state: ControlUniverseReasoningState) -> ControlUniverseReasoningState:
        """Generate measurable expectations reasoning."""
        
        identified_controls = state.get("identified_controls", [])
        control_reasoning = state.get("control_identification_reasoning", "")
        benchmarks = state.get("industry_benchmarks", {})
        
        chain = self.prompt | self.llm
        
        response = chain.invoke({
            "input": f"""Create measurable expectations for identified compliance requirements.

IDENTIFIED CONTROLS (from previous reasoning):
{control_reasoning[:1000]}...

INDUSTRY BENCHMARKS (for reference):
{benchmarks}

As a data scientist, provide REASONING about:

1. MAKING REQUIREMENTS MEASURABLE:
   For each identified requirement, reason about:
   - What metric would quantify this requirement?
   - Why is this metric appropriate?
   - What makes it measurable vs subjective?
   - What data type does it produce?

2. METRIC SELECTION REASONING:
   - What alternative metrics were considered?
   - Why did you choose this metric over others?
   - What are the trade-offs?
   - How does it align with industry practices?

3. DATA SOURCE IDENTIFICATION:
   - Where would this metric data come from?
   - How reliable is this data source?
   - What quality issues might exist?
   - How would you validate data quality?

4. SUCCESS/FAILURE CRITERIA:
   - What constitutes compliance (pass criteria)?
   - What constitutes non-compliance (fail criteria)?
   - Where is the boundary (and why there)?
   - How did you determine these thresholds?

5. TESTING APPROACH:
   - How would you test this requirement?
   - What testing methodology is appropriate?
   - How often should testing occur (and why)?
   - What sample size is needed?
   - How would you handle edge cases?

6. MEASUREMENT VALIDATION:
   - How would you validate the measurement approach?
   - What could go wrong with this measurement?
   - How would you detect measurement errors?
   - What controls should exist on the measurement itself?

For each requirement, provide:
- Proposed metric name
- Measurement method (natural language)
- Target value/threshold
- Pass/fail criteria
- Testing approach
- Data source
- Reasoning for all above choices
- Assumptions made
- Limitations of the approach

Example structure:
"For requirement 'Access reviews must be periodic':
- Metric: 'Days between access reviews'
- Reasoning: This quantifies 'periodic' objectively. Alternative was 'number of reviews per year' but interval-based is more precise.
- Target: Maximum 90 days
- Reasoning: HIPAA guidance suggests quarterly, industry standard is 90 days, balances security with overhead.
- Pass criteria: All reviews within 90-day window
- Fail criteria: Any interval >90 days
- Data source: Access management system review log
- Testing: Query log for all reviews, calculate intervals
- Assumption: Review log is complete and accurate
- Limitation: Doesn't measure review quality, only that it occurred"
""")
        })
        
        state["measurable_expectations_reasoning"] = response.content
        
        # Create structured expectations (still reasoning/planning)
        state["proposed_measurable_expectations"] = [
            {
                "expectation_id": "EXP-001",
                "metric": "Access Review Interval",
                "reasoning": "Extracted from agent response...",
                "confidence": "high"
            }
        ]
        
        state["messages"].append(
            AIMessage(content="Measurable expectations reasoning complete")
        )
        state["current_step"] = "expectations_reasoning_complete"
        
        return state


# ============================================================================
# EVIDENCE MAPPING REASONING AGENT
# ============================================================================

class EvidenceMappingReasoningAgent:
    """
    Reasoning agent that identifies what evidence proves compliance.
    
    Creates reasoning about:
    - What types of evidence are needed
    - How evidence maps to requirements
    - What makes evidence sufficient
    - How to collect and validate evidence
    """
    
    def __init__(self, llm: ChatAnthropic):
        self.llm = llm
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a compliance audit expert who reasons about evidence requirements.

Your task is to REASON about:
1. What evidence proves compliance
2. What types of evidence are most reliable
3. How to map evidence to requirements
4. What makes evidence sufficient

Think like an auditor - explain what evidence you would want to see and why.

You do NOT:
- Collect actual evidence
- Execute audit procedures
- Write audit programs

Output: Natural language reasoning about evidence requirements."""),
            ("human", "{input}")
        ])
    
    def __call__(self, state: ControlUniverseReasoningState) -> ControlUniverseReasoningState:
        """Generate evidence mapping reasoning."""
        
        expectations_reasoning = state.get("measurable_expectations_reasoning", "")
        control_reasoning = state.get("control_identification_reasoning", "")
        
        chain = self.prompt | self.llm
        
        response = chain.invoke({
            "input": f"""Reason about evidence requirements for compliance.

MEASURABLE EXPECTATIONS (from data scientist):
{expectations_reasoning[:1000]}...

IDENTIFIED CONTROLS:
{control_reasoning[:500]}...

As an audit expert, provide REASONING about:

1. EVIDENCE TYPE IDENTIFICATION:
   - What types of evidence would prove each requirement?
   - Why is this evidence type appropriate?
   - What alternatives exist?
   - How reliable is each evidence type?

2. EVIDENCE CATEGORIES:
   Common categories: Logs, Metrics, Documents, Configurations, Reports, Training Records
   - Which category fits each evidence need?
   - Why this categorization?
   - What if evidence spans multiple categories?

3. EVIDENCE SUFFICIENCY:
   - What makes evidence sufficient?
   - How much evidence is needed?
   - What quality indicators matter?
   - How would you know if evidence is insufficient?

4. EVIDENCE-TO-REQUIREMENT MAPPING:
   - Which evidence proves which requirement?
   - Can one piece of evidence prove multiple requirements?
   - Are there gaps where evidence doesn't exist?
   - How would you handle evidence gaps?

5. COLLECTION APPROACH:
   - How should this evidence be collected?
   - How often?
   - From what systems/sources?
   - What could go wrong in collection?

6. RETENTION AND PRESERVATION:
   - How long should evidence be retained?
   - How should it be preserved?
   - What legal/regulatory requirements apply?

For each evidence type, provide:
- Evidence type name
- Category (logs/metrics/docs/etc)
- What it demonstrates
- Which requirements it supports
- Collection method
- Collection frequency
- Retention period
- Sufficiency criteria
- Quality indicators
- Reasoning for all above

Example:
"Evidence Type: Access Review Reports
- Category: Reports
- Demonstrates: That periodic access reviews are conducted
- Supports: Requirements around access review frequency
- Reasoning: Reports provide documented proof of review activity. Alternative would be access logs, but reports are more comprehensive.
- Collection: Export from Identity Management System
- Frequency: Quarterly (matches review frequency)
- Retention: 7 years (HIPAA requirement)
- Sufficient if: Contains review date, reviewer, systems covered, approvals, remediation
- Quality indicators: Complete system coverage, clear approval chain, remediation tracking
- Limitations: Report existence doesn't prove review quality"
""")
        })
        
        state["evidence_mapping_reasoning"] = response.content
        
        # Create structured evidence types
        state["proposed_evidence_types"] = [
            {
                "evidence_type_id": "EVD-001",
                "evidence_name": "Access Review Reports",
                "reasoning": "From agent response...",
                "supports": ["EXP-001"]
            }
        ]
        
        state["messages"].append(
            AIMessage(content="Evidence mapping reasoning complete")
        )
        state["current_step"] = "evidence_reasoning_complete"
        
        return state


# ============================================================================
# RISK ASSESSMENT REASONING AGENT
# ============================================================================

class RiskAssessmentReasoningAgent:
    """
    Data scientist reasoning agent for risk assessment using risk matrices.
    
    Creates reasoning about:
    - Likelihood of control failure
    - Impact if control fails
    - Risk score calculation using 5x5 matrix
    - Risk prioritization
    """
    
    def __init__(self, llm: ChatAnthropic):
        self.llm = llm
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a risk analyst data scientist specializing in compliance risk assessment.

Your expertise: Risk matrices, probability estimation, impact analysis, risk scoring

Your task is to REASON about risk assessment for compliance requirements using 
the 5x5 Risk Matrix:
- Likelihood: 1 (Highly Unlikely) to 5 (Highly Likely)
- Impact: 1 (Negligible) to 5 (Catastrophic)
- Risk Score: Likelihood × Impact (1-25)
- Classifications: Negligible (1-3), Low (4-6), Moderate (9-15), High (16-20), Major (25)

Think like a risk analyst - explain your reasoning about likelihood and impact assessments.

You do NOT:
- Calculate actual risk scores (explain how you would)
- Execute risk models
- Make definitive risk determinations

Output: Natural language reasoning about risk assessment."""),
            ("human", "{input}")
        ])
    
    def __call__(self, state: ControlUniverseReasoningState) -> ControlUniverseReasoningState:
        """Generate risk assessment reasoning."""
        
        control_reasoning = state.get("control_identification_reasoning", "")
        expectations_reasoning = state.get("measurable_expectations_reasoning", "")
        domain_reasoning = state.get("domain_definition_reasoning", "")
        
        chain = self.prompt | self.llm
        
        response = chain.invoke({
            "input": f"""Reason about risk assessment for compliance controls using the 5x5 Risk Matrix.

RISK MATRIX FRAMEWORK:
Likelihood Levels:
1 = Highly Unlikely
2 = Unlikely  
3 = Possible
4 = Likely
5 = Highly Likely

Impact Levels:
1 = Negligible
2 = Low
3 = Moderate
4 = High
5 = Catastrophic

Risk Score = Likelihood × Impact
Classifications:
- Negligible Risk: 1-3
- Low Risk: 4-6
- Moderate Risk: 9-15
- High Risk: 16-20
- Major Risk: 25

IDENTIFIED CONTROLS:
{control_reasoning[:500]}...

DOMAIN CONTEXT:
{domain_reasoning[:500]}...

As a risk analyst, provide REASONING about:

1. LIKELIHOOD ASSESSMENT:
   For each control/requirement:
   - What is the likelihood of this control failing? (1-5)
   - What factors influence this likelihood?
   - What historical data or patterns inform this?
   - What control weaknesses exist?
   - Why this likelihood level vs others?

2. IMPACT ASSESSMENT:
   For each control/requirement:
   - What is the impact if this control fails? (1-5)
   - What dimensions of impact are relevant?
     * Financial (fines, costs)
     * Operational (disruption)
     * Reputational (brand damage)
     * Legal/regulatory
   - Why this impact level?
   - What makes it catastrophic vs moderate?

3. RISK SCORE REASONING:
   - How do likelihood and impact combine?
   - What is the calculated risk score?
   - What risk classification does this fall into?
   - Does this match your intuition?

4. RISK FACTORS:
   - What increases likelihood?
   - What increases impact?
   - What mitigating factors exist?
   - How do domain factors affect risk?

5. RISK PRIORITIZATION:
   - Which controls carry highest risk?
   - Why should they be prioritized?
   - What's the risk ranking?

For each requirement, provide:
- Likelihood level (1-5) with reasoning
- Impact level (1-5) with reasoning
- Calculated risk score
- Risk classification
- Key risk factors
- Mitigation considerations
- Priority ranking

Example:
"Requirement: Quarterly access reviews
- Likelihood: 3 (Possible)
  Reasoning: Manual process prone to delays. Historical data shows 30% of reviews late. 
  Mitigating: Automated reminders exist.
  Aggravating: High workload, competing priorities.
  
- Impact: 4 (High)  
  Reasoning:
  * Financial: HIPAA Tier 2 penalty potential (€20M/4% revenue)
  * Operational: Would require emergency access remediation
  * Reputational: PHI exposure risk = severe brand damage
  * Legal: Regulatory investigation likely
  Not Catastrophic (5) because limited to access issues, not breach.
  
- Risk Score: 3 × 4 = 12
- Classification: Moderate Risk
- Priority: Medium-High (should address but not emergency)

Confidence: Medium (based on industry patterns, limited org-specific data)"

Include reasoning for each assessment."""
        })
        
        state["risk_assessment_reasoning"] = response.content
        
        # Create structured risk assessments
        state["risk_matrix_reasoning"] = {
            "methodology": "5x5 Risk Matrix",
            "assessments": [
                {
                    "requirement_id": "REQ-001",
                    "likelihood": 3,
                    "impact": 4,
                    "risk_score": 12,
                    "classification": "Moderate Risk",
                    "reasoning": "From agent response..."
                }
            ]
        }
        
        state["messages"].append(
            AIMessage(content="Risk assessment reasoning complete")
        )
        state["current_step"] = "risk_assessment_complete"
        
        return state


# ============================================================================
# CONTROL UNIVERSE INTEGRATION AGENT
# ============================================================================

class ControlUniverseIntegrationAgent:
    """
    Agent that synthesizes all reasoning into a complete control universe blueprint.
    
    Integrates:
    - Domain context
    - Controls and sub-controls
    - Measurable expectations
    - Evidence mappings
    - Risk assessments
    """
    
    def __init__(self, llm: ChatAnthropic):
        self.llm = llm
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a compliance program architect who integrates all 
compliance reasoning into a cohesive control universe.

Your task is to SYNTHESIZE reasoning from:
- Domain context analysis
- Control identification
- Measurable expectations
- Evidence mapping
- Risk assessment

Create an integrated blueprint that shows how all pieces fit together.

Output: Natural language integration reasoning and structured blueprint."""),
            ("human", "{input}")
        ])
    
    def __call__(self, state: ControlUniverseReasoningState) -> ControlUniverseReasoningState:
        """Integrate all reasoning into control universe blueprint."""
        
        domain_reasoning = state.get("domain_definition_reasoning", "")
        control_reasoning = state.get("control_identification_reasoning", "")
        expectations_reasoning = state.get("measurable_expectations_reasoning", "")
        evidence_reasoning = state.get("evidence_mapping_reasoning", "")
        risk_reasoning = state.get("risk_assessment_reasoning", "")
        
        chain = self.prompt | self.llm
        
        response = chain.invoke({
            "input": f"""Integrate all compliance reasoning into a complete control universe blueprint.

DOMAIN CONTEXT REASONING:
{domain_reasoning[:800]}...

CONTROL IDENTIFICATION REASONING:
{control_reasoning[:800]}...

MEASURABLE EXPECTATIONS REASONING:
{expectations_reasoning[:800]}...

EVIDENCE MAPPING REASONING:
{evidence_reasoning[:800]}...

RISK ASSESSMENT REASONING:
{risk_reasoning[:800]}...

Provide INTEGRATION REASONING:

1. CONTROL UNIVERSE OVERVIEW:
   - What is the complete picture?
   - How do all pieces fit together?
   - What is the control hierarchy?

2. CONTROL-TO-REQUIREMENT-TO-EVIDENCE FLOW:
   - How do controls flow to requirements?
   - How do requirements connect to expectations?
   - How does evidence prove expectations?
   - Show the complete chain

3. RISK-BASED PRIORITIZATION:
   - Which controls are highest risk?
   - How should implementation be prioritized?
   - What should be addressed first?

4. COVERAGE ASSESSMENT:
   - What is covered by identified controls?
   - What gaps exist?
   - What additional controls might be needed?

5. IMPLEMENTATION GUIDANCE:
   - How should this control universe be built?
   - What's the recommended sequence?
   - What dependencies exist?

6. BLUEPRINT COMPLETENESS:
   - Is this blueprint complete?
   - What additional reasoning is needed?
   - What assumptions underpin this blueprint?

Provide a structured blueprint showing:
- Domain context
- Control hierarchy (controls → sub-controls)
- Measurable expectations for each sub-control
- Evidence types for each expectation
- Risk assessments for each requirement
- Implementation priorities
- Gap analysis

This blueprint should be ready for execution teams to implement."""
        })
        
        # Create comprehensive blueprint
        blueprint = {
            "integration_reasoning": response.content,
            "domain_context": {
                "reasoning": domain_reasoning
            },
            "controls": state.get("identified_controls", []),
            "measurable_expectations": state.get("proposed_measurable_expectations", []),
            "evidence_types": state.get("proposed_evidence_types", []),
            "risk_assessments": state.get("risk_matrix_reasoning", {}),
            "implementation_priority": "Based on risk assessment, high-risk controls first",
            "gaps_identified": [],
            "blueprint_status": "Ready for execution team review"
        }
        
        state["control_universe_blueprint"] = blueprint
        
        state["messages"].append(
            AIMessage(content="Control universe blueprint complete")
        )
        state["current_step"] = "integration_complete"
        
        return state


# ============================================================================
# WORKFLOW ORCHESTRATION
# ============================================================================

class ControlUniverseReasoningWorkflow:
    """
    LangGraph workflow that orchestrates all reasoning agents to create
    a complete control universe definition from documents.
    """
    
    def __init__(self, anthropic_api_key: str):
        """Initialize the workflow with all reasoning agents."""
        
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            anthropic_api_key=anthropic_api_key,
            temperature=0.2
        )
        
        # Initialize all reasoning agents
        self.domain_agent = DomainContextReasoningAgent(self.llm)
        self.control_agent = ControlIdentificationReasoningAgent(self.llm)
        self.expectations_agent = MeasurableExpectationsReasoningAgent(self.llm)
        self.evidence_agent = EvidenceMappingReasoningAgent(self.llm)
        self.risk_agent = RiskAssessmentReasoningAgent(self.llm)
        self.integration_agent = ControlUniverseIntegrationAgent(self.llm)
        
        # Build the graph
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph reasoning workflow."""
        
        workflow = StateGraph(ControlUniverseReasoningState)
        
        # Add all agent nodes
        workflow.add_node("domain_reasoning", self.domain_agent)
        workflow.add_node("control_identification", self.control_agent)
        workflow.add_node("measurable_expectations", self.expectations_agent)
        workflow.add_node("evidence_mapping", self.evidence_agent)
        workflow.add_node("risk_assessment", self.risk_agent)
        workflow.add_node("integration", self.integration_agent)
        
        # Define sequential workflow
        workflow.set_entry_point("domain_reasoning")
        workflow.add_edge("domain_reasoning", "control_identification")
        workflow.add_edge("control_identification", "measurable_expectations")
        workflow.add_edge("measurable_expectations", "evidence_mapping")
        workflow.add_edge("evidence_mapping", "risk_assessment")
        workflow.add_edge("risk_assessment", "integration")
        workflow.add_edge("integration", END)
        
        return workflow.compile()
    
    def run(
        self,
        source_documents: List[Dict[str, str]],
        compliance_framework: str,
        existing_patterns: Optional[List[Dict]] = None,
        benchmarks: Optional[Dict] = None,
        examples: Optional[List[Dict]] = None
    ) -> ControlUniverseReasoningState:
        """
        Execute the control universe reasoning workflow.
        
        Args:
            source_documents: Compliance documents to analyze
            compliance_framework: Target framework (HIPAA, SOC2, etc)
            existing_patterns: Known control patterns
            benchmarks: Industry benchmarks
            examples: Historical examples
            
        Returns:
            State with complete control universe blueprint
        """
        
        initial_state = ControlUniverseReasoningState(
            source_documents=source_documents,
            compliance_framework=compliance_framework,
            existing_control_patterns=existing_patterns,
            industry_benchmarks=benchmarks,
            historical_examples=examples,
            domain_definition_reasoning=None,
            control_identification_reasoning=None,
            measurable_expectations_reasoning=None,
            evidence_mapping_reasoning=None,
            risk_assessment_reasoning=None,
            identified_controls=None,
            identified_requirements=None,
            proposed_measurable_expectations=None,
            proposed_evidence_types=None,
            risk_matrix_reasoning=None,
            control_universe_blueprint=None,
            messages=[HumanMessage(content="Starting control universe reasoning")],
            current_step="initialized"
        )
        
        final_state = self.graph.invoke(initial_state)
        
        return final_state


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_control_universe_workflow(api_key: str) -> ControlUniverseReasoningWorkflow:
    """Factory function to create control universe reasoning workflow."""
    return ControlUniverseReasoningWorkflow(anthropic_api_key=api_key)


def extract_blueprint(state: ControlUniverseReasoningState) -> Dict:
    """Extract the complete control universe blueprint from final state."""
    return {
        "blueprint": state.get("control_universe_blueprint", {}),
        "domain_reasoning": state.get("domain_definition_reasoning", ""),
        "control_reasoning": state.get("control_identification_reasoning", ""),
        "expectations_reasoning": state.get("measurable_expectations_reasoning", ""),
        "evidence_reasoning": state.get("evidence_mapping_reasoning", ""),
        "risk_reasoning": state.get("risk_assessment_reasoning", "")
    }

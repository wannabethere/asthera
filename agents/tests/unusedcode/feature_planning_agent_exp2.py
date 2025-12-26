"""
Compliance Reasoning Agents - Pure Planning and Reasoning System
================================================================

This system contains ONLY reasoning agents that:
1. Generate natural language questions
2. Create reasoning plans
3. Suggest analytical approaches
4. NO execution or calculation

Execution agents are separate and not included here.

Refactored to use AgentPipeline architecture similar to feature_engineering_agent.
"""

import logging
import json
from typing import TypedDict, List, Dict, Annotated, Optional, Sequence, Any
import operator
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.agents.pipelines.base import AgentPipeline
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.engine import Engine
from app.core.provider import DocumentStoreProvider
from app.core.dependencies import get_llm
from app.agents.nodes.transform.knowledge_and_context import (
    DataModelKnowledgeBase,
    ComplianceRulesKnowledgeBase,
    ExamplesLibrary,
    ReasoningContextBuilder,
    HistoricalExample
)

logger = logging.getLogger("lexy-ai-service")


# ============================================================================
# STATE DEFINITION
# ============================================================================

class ComplianceReasoningState(TypedDict, total=False):
    """
    State for reasoning agents - focuses on plans, questions, and reasoning.
    """
    # Inputs
    data_model_schema: Optional[Dict]
    compliance_url: Optional[str]
    user_query: Optional[str]  # Natural language query about compliance needs
    
    # Knowledge bases (read-only reference material)
    data_model_knowledge_base: Optional[Dict]
    compliance_rules_knowledge_base: Optional[Dict]
    historical_analysis_examples: Optional[List[Dict]]
    
    # Reasoning outputs (natural language)
    compliance_questions: Optional[List[str]]  # Questions to ask about the data
    feature_importance_reasoning: Optional[str]  # Why certain features matter
    
    # Data scientist reasoning plans (natural language plans, not code)
    risk_reasoning_plan: Optional[Dict]  # How to think about risk
    impact_reasoning_plan: Optional[Dict]  # How to think about impact
    likelihood_reasoning_plan: Optional[Dict]  # How to think about likelihood
    
    # Aggregated reasoning
    integrated_reasoning: Optional[str]  # Combined reasoning from all agents
    
    # Conversation history and context
    messages: Annotated[Sequence[BaseMessage], operator.add]
    agent_history: Dict[str, List[str]]  # Track each agent's reasoning history
    current_step: str
    next_agent: str  # For conditional routing
    
    # Pipeline support
    project_id: Optional[str]
    retrieval_helper: Optional[RetrievalHelper]


# ============================================================================
# KNOWLEDGE BASE READER
# ============================================================================

class KnowledgeBaseReader:
    """
    Utility for agents to read from knowledge bases.
    Uses ReasoningContextBuilder from knowledge_and_context.py
    """
    
    def __init__(self, context_builder: Optional[ReasoningContextBuilder] = None):
        self.context_builder = context_builder
    
    def read_data_model_kb(
        self,
        kb: Dict,
        query: str
    ) -> str:
        """
        Read relevant information from data model knowledge base.
        In production, this would use semantic search over a vector DB.
        """
        if not kb:
            return "No data model knowledge base available"
        
        return f"""
Data Model Knowledge (relevant to: {query}):
- Tables: {kb.get('tables_summary', 'Not available')}
- Key columns: {json.dumps(kb.get('key_columns', []), indent=2)}
- Relationships: {json.dumps(kb.get('relationships', []), indent=2)}
- Compliance indicators: {json.dumps(kb.get('compliance_indicators', []), indent=2)}
- Data quality notes: {kb.get('data_quality_notes', 'Not available')}
"""
    
    def read_compliance_kb(
        self,
        kb: Dict,
        query: str
    ) -> str:
        """
        Read relevant compliance rules from knowledge base.
        """
        if not kb:
            return "No compliance knowledge base available"
        
        return f"""
Compliance Knowledge (relevant to: {query}):
- Applicable regulations: {json.dumps(kb.get('regulations', []), indent=2)}
- Key requirements: {json.dumps(kb.get('requirements', []), indent=2)}
- Data protection rules: {json.dumps(kb.get('data_protection', []), indent=2)}
- Penalties: {json.dumps(kb.get('penalties', {}), indent=2)}
- Control requirements: {json.dumps(kb.get('control_requirements', []), indent=2)}
"""
    
    def read_examples(
        self,
        examples: List[Dict],
        scenario: str
    ) -> str:
        """
        Read relevant examples from historical analyses.
        """
        if not examples:
            return "No examples available"
        
        # In production, filter examples by similarity to scenario
        example_text = f"\nHistorical Examples (similar to: {scenario}):\n"
        for i, ex in enumerate(examples[:3], 1):  # Limit to 3 examples
            example_text += f"\nExample {i}:\n"
            example_text += f"Scenario: {ex.get('scenario', ex.get('example_id', 'N/A'))}\n"
            if ex.get('compliance_questions'):
                example_text += f"Questions: {chr(10).join(f'  - {q}' for q in ex.get('compliance_questions', []))}\n"
            if ex.get('feature_reasoning'):
                example_text += f"Feature Reasoning: {ex.get('feature_reasoning', 'N/A')[:200]}...\n"
            if ex.get('outcome'):
                example_text += f"Outcome: {ex.get('outcome', 'N/A')}\n"
        
        return example_text


# ============================================================================
# COMPLIANCE REASONING AGENT
# ============================================================================

class ComplianceReasoningAgent:
    """
    Reasoning agent that generates natural language questions about compliance.
    
    This agent:
    - Reads from knowledge bases
    - Uses examples to guide thinking
    - Generates questions that need to be answered
    - Explains reasoning about which features are important
    - Does NOT execute any analysis
    """
    
    def __init__(self, llm: BaseChatModel, context_builder: Optional[ReasoningContextBuilder] = None):
        self.llm = llm
        self.kb_reader = KnowledgeBaseReader(context_builder)
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a compliance reasoning expert who generates thoughtful questions and explanations.

Your role is to REASON and PLAN, not to execute:
- Generate natural language questions about compliance requirements
- Explain which data features are important and why
- Reference knowledge bases to inform your reasoning
- Use historical examples to guide your thinking
- Provide clear, structured reasoning

You do NOT:
- Execute queries or calculations
- Write code
- Perform actual analysis

Output Format:
1. COMPLIANCE QUESTIONS: List of specific questions to investigate
2. FEATURE IMPORTANCE REASONING: Explanation of why certain features matter
3. KNOWLEDGE REFERENCES: What you learned from knowledge bases
4. REASONING PROCESS: Your thought process"""),
            ("human", "{input}")
        ])
    
    async def __call__(self, state: ComplianceReasoningState) -> ComplianceReasoningState:
        """Generate compliance questions and feature importance reasoning."""
        
        # Read from knowledge bases
        data_kb = state.get("data_model_knowledge_base", {})
        compliance_kb = state.get("compliance_rules_knowledge_base", {})
        examples = state.get("historical_analysis_examples", [])
        
        # Get relevant knowledge
        data_knowledge = self.kb_reader.read_data_model_kb(
            data_kb,
            "compliance-relevant fields"
        )
        compliance_knowledge = self.kb_reader.read_compliance_kb(
            compliance_kb,
            "data requirements"
        )
        example_reasoning = self.kb_reader.read_examples(
            examples,
            "compliance feature identification"
        )
        
        # Get conversation history for this agent
        agent_history = state.get("agent_history", {}).get("compliance_reasoning", [])
        history_context = "\n".join(agent_history[-3:]) if agent_history else "No prior history"
        
        # Get user query or data model schema
        user_query = state.get("user_query", "")
        data_schema = state.get("data_model_schema", {})
        
        chain = self.prompt | self.llm
        
        response = await chain.ainvoke({
            "input": f"""Generate compliance questions and reasoning about feature importance.

USER QUERY:
{user_query if user_query else 'No specific query provided'}

DATA MODEL SCHEMA:
{json.dumps(data_schema, indent=2) if data_schema else 'No schema provided'}

KNOWLEDGE BASE - DATA MODEL:
{data_knowledge}

KNOWLEDGE BASE - COMPLIANCE RULES:
{compliance_knowledge}

HISTORICAL EXAMPLES:
{example_reasoning}

YOUR PREVIOUS REASONING (if any):
{history_context}

Based on this information, provide:

1. COMPLIANCE QUESTIONS (natural language questions to investigate):
   - What questions should we ask about this data?
   - What compliance concerns need investigation?
   - What relationships need to be understood?

2. FEATURE IMPORTANCE REASONING:
   - Which columns/fields are most critical for compliance?
   - Why are they important?
   - What compliance rules apply to each?

3. KNOWLEDGE INTEGRATION:
   - What did you learn from the knowledge bases?
   - How do the examples inform your reasoning?

4. REASONING PROCESS:
   - Walk through your thought process
   - What patterns did you notice?
   - What uncertainties exist?

Remember: Generate questions and reasoning, not answers or code."""
        })
        
        # Extract questions and reasoning from response
        reasoning_text = response.content if hasattr(response, 'content') else str(response)
        
        # Try to parse questions from the response (in production, use structured output)
        # For now, extract questions from the reasoning text
        questions = []
        lines = reasoning_text.split('\n')
        in_questions_section = False
        for line in lines:
            if 'COMPLIANCE QUESTIONS' in line.upper() or 'QUESTIONS' in line.upper():
                in_questions_section = True
                continue
            if in_questions_section and (line.strip().startswith('-') or line.strip().startswith('*') or 
                                         (line.strip() and not line.strip().startswith('2.'))):
                question = line.strip().lstrip('-*').strip()
                if question and len(question) > 10:  # Basic validation
                    questions.append(question)
            if in_questions_section and line.strip().startswith('2.'):
                break
        
        # Fallback: if no questions extracted, create default ones
        if not questions:
            questions = [
                "What personal data elements require explicit consent?",
                "Which fields contain data subject to right of erasure?",
                "Are there fields that require data retention policies?",
                "What data crosses international boundaries?",
                "Which fields require audit logging of access?"
            ]
        
        # Update state with reasoning
        state["compliance_questions"] = questions
        state["feature_importance_reasoning"] = reasoning_text
        
        # Update agent history
        if "agent_history" not in state:
            state["agent_history"] = {}
        if "compliance_reasoning" not in state["agent_history"]:
            state["agent_history"]["compliance_reasoning"] = []
        
        state["agent_history"]["compliance_reasoning"].append(
            f"Generated {len(questions)} compliance questions and feature importance reasoning"
        )
        
        state["messages"].append(
            AIMessage(content=f"Compliance reasoning complete: {len(questions)} questions generated")
        )
        state["current_step"] = "compliance_reasoning_complete"
        state["next_agent"] = "risk_scientist_reasoning"  # Start sequential data scientist reasoning
        
        return state


# ============================================================================
# RISK DATA SCIENTIST REASONING AGENT
# ============================================================================

class RiskDataScientistReasoningAgent:
    """
    Data scientist reasoning agent specialized in PLANNING risk calculations.
    
    This agent:
    - Creates a reasoning plan for risk assessment
    - Explains the analytical approach
    - Suggests methodologies without implementing them
    - Does NOT execute calculations
    """
    
    def __init__(self, llm: BaseChatModel, context_builder: Optional[ReasoningContextBuilder] = None):
        self.llm = llm
        self.kb_reader = KnowledgeBaseReader(context_builder)
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a senior data scientist specializing in risk analysis REASONING.

Your expertise: Statistical risk modeling, Bayesian analysis, Monte Carlo methods, risk scoring

Your role is to REASON and PLAN:
- Develop a reasoning plan for risk assessment
- Explain which methodologies would be appropriate and why
- Describe the analytical approach in natural language
- Identify what data points are needed and why
- Explain the logic behind risk calculations

You do NOT:
- Write code or formulas
- Execute calculations
- Perform actual analysis

Think like a data scientist planning an analysis - explain your reasoning process.

Output Format:
1. RISK ASSESSMENT APPROACH: High-level strategy
2. METHODOLOGY REASONING: Why certain methods are appropriate
3. DATA REQUIREMENTS: What data is needed and why
4. ANALYTICAL PLAN: Step-by-step reasoning plan
5. ASSUMPTIONS & CONSIDERATIONS: What to keep in mind"""),
            ("human", "{input}")
        ])
    
    async def __call__(self, state: ComplianceReasoningState) -> ComplianceReasoningState:
        """Generate reasoning plan for risk assessment."""
        
        # Read from knowledge bases
        compliance_kb = state.get("compliance_rules_knowledge_base", {})
        examples = state.get("historical_analysis_examples", [])
        
        compliance_knowledge = self.kb_reader.read_compliance_kb(
            compliance_kb,
            "risk assessment"
        )
        example_reasoning = self.kb_reader.read_examples(
            examples,
            "risk calculation planning"
        )
        
        # Get this agent's history
        agent_history = state.get("agent_history", {}).get("risk_scientist", [])
        history_context = "\n".join(agent_history[-3:]) if agent_history else "No prior history"
        
        # Get compliance questions as input
        compliance_questions = state.get("compliance_questions", [])
        feature_reasoning = state.get("feature_importance_reasoning", "")
        
        chain = self.prompt | self.llm
        
        response = await chain.ainvoke({
            "input": f"""Create a reasoning plan for risk assessment based on compliance needs.

COMPLIANCE QUESTIONS TO ADDRESS:
{chr(10).join(f'- {q}' for q in compliance_questions) if compliance_questions else 'No questions provided yet'}

FEATURE IMPORTANCE REASONING:
{feature_reasoning if feature_reasoning else 'No feature reasoning available yet'}

COMPLIANCE KNOWLEDGE BASE:
{compliance_knowledge}

HISTORICAL EXAMPLES OF RISK REASONING:
{example_reasoning}

YOUR PREVIOUS REASONING:
{history_context}

As a data scientist, develop a REASONING PLAN for risk assessment:

1. RISK ASSESSMENT APPROACH:
   - What is your high-level strategy for assessing compliance risk?
   - How would you think about different types of risk?
   - What framework makes sense for this scenario?

2. METHODOLOGY REASONING:
   - Why would certain risk methodologies be appropriate here?
   - What are the pros/cons of different approaches?
   - How would you handle uncertainty?

3. DATA REQUIREMENTS:
   - What data points would you need to assess risk?
   - Why is each data point important?
   - What derived features might be useful?

4. ANALYTICAL PLAN (step-by-step reasoning):
   - How would you approach the risk calculation logically?
   - What factors would you consider?
   - How would you weight different risk components?
   - How would you validate your risk assessment?

5. ASSUMPTIONS & CONSIDERATIONS:
   - What assumptions would you make?
   - What edge cases need consideration?
   - What are the limitations of this approach?

Remember: Explain your reasoning process, don't write formulas or code."""
        })
        
        # Store the reasoning plan
        reasoning_text = response.content if hasattr(response, 'content') else str(response)
        
        risk_plan = {
            "reasoning": reasoning_text,
            "methodology_considered": ["bayesian_risk", "scoring_matrix", "monte_carlo"],
            "data_needs_identified": True,
            "plan_complete": True
        }
        
        state["risk_reasoning_plan"] = risk_plan
        
        # Update agent history
        if "agent_history" not in state:
            state["agent_history"] = {}
        if "risk_scientist" not in state["agent_history"]:
            state["agent_history"]["risk_scientist"] = []
        
        state["agent_history"]["risk_scientist"].append(
            "Developed risk assessment reasoning plan with methodology considerations"
        )
        
        state["messages"].append(
            AIMessage(content="Risk data scientist reasoning plan complete")
        )
        state["current_step"] = "risk_reasoning_complete"
        state["next_agent"] = "impact_scientist_reasoning"  # Move to next scientist
        
        return state


# ============================================================================
# IMPACT DATA SCIENTIST REASONING AGENT
# ============================================================================

class ImpactDataScientistReasoningAgent:
    """
    Data scientist reasoning agent specialized in PLANNING impact assessment.
    
    This agent creates reasoning plans for impact analysis without execution.
    """
    
    def __init__(self, llm: BaseChatModel, context_builder: Optional[ReasoningContextBuilder] = None):
        self.llm = llm
        self.kb_reader = KnowledgeBaseReader(context_builder)
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a senior data scientist specializing in impact assessment REASONING.

Your expertise: Multi-criteria analysis, consequence modeling, stakeholder impact, financial modeling

Your role is to REASON and PLAN:
- Develop a reasoning plan for impact assessment
- Explain which impact dimensions to consider and why
- Describe how to think about severity and consequences
- Identify impact factors and their relationships
- Explain the logic behind impact evaluation

You do NOT:
- Write code or formulas
- Execute calculations
- Perform actual analysis

Think like a data scientist planning an impact study - explain your reasoning.

Output Format:
1. IMPACT ASSESSMENT APPROACH: Overall strategy
2. IMPACT DIMENSIONS: What types of impact to consider
3. SEVERITY REASONING: How to think about impact severity
4. ANALYTICAL PLAN: Step-by-step reasoning
5. STAKEHOLDER CONSIDERATIONS: Who is affected and how"""),
            ("human", "{input}")
        ])
    
    async def __call__(self, state: ComplianceReasoningState) -> ComplianceReasoningState:
        """Generate reasoning plan for impact assessment."""
        
        compliance_kb = state.get("compliance_rules_knowledge_base", {})
        examples = state.get("historical_analysis_examples", [])
        
        compliance_knowledge = self.kb_reader.read_compliance_kb(
            compliance_kb,
            "impact and penalties"
        )
        example_reasoning = self.kb_reader.read_examples(
            examples,
            "impact assessment planning"
        )
        
        agent_history = state.get("agent_history", {}).get("impact_scientist", [])
        history_context = "\n".join(agent_history[-3:]) if agent_history else "No prior history"
        
        compliance_questions = state.get("compliance_questions", [])
        feature_reasoning = state.get("feature_importance_reasoning", "")
        
        chain = self.prompt | self.llm
        
        response = await chain.ainvoke({
            "input": f"""Create a reasoning plan for impact assessment of compliance violations.

COMPLIANCE QUESTIONS:
{chr(10).join(f'- {q}' for q in compliance_questions) if compliance_questions else 'No questions provided yet'}

FEATURE IMPORTANCE REASONING:
{feature_reasoning if feature_reasoning else 'No feature reasoning available yet'}

COMPLIANCE KNOWLEDGE (penalties and consequences):
{compliance_knowledge}

HISTORICAL IMPACT REASONING EXAMPLES:
{example_reasoning}

YOUR PREVIOUS REASONING:
{history_context}

As a data scientist, develop a REASONING PLAN for impact assessment:

1. IMPACT ASSESSMENT APPROACH:
   - How would you approach assessing compliance violation impact?
   - What framework would you use to think about impact?
   - How would you categorize different types of impact?

2. IMPACT DIMENSIONS TO CONSIDER:
   - Financial impact: fines, legal costs, lost revenue
   - Operational impact: business disruption, remediation effort
   - Reputational impact: brand damage, customer trust
   - Legal impact: regulatory actions, litigation risk
   - For each dimension, explain WHY it matters

3. SEVERITY REASONING:
   - How would you think about severity levels?
   - What makes an impact "critical" vs "moderate" vs "low"?
   - How would you handle cascading impacts?

4. ANALYTICAL PLAN (step-by-step reasoning):
   - How would you approach impact calculation logically?
   - What factors would you consider for each dimension?
   - How would you aggregate multi-dimensional impacts?
   - How would you account for uncertainty?

5. STAKEHOLDER CONSIDERATIONS:
   - Who would be affected by violations?
   - How would impacts vary by stakeholder group?
   - What secondary impacts might occur?

Remember: Explain your reasoning process and approach, not specific formulas."""
        })
        
        reasoning_text = response.content if hasattr(response, 'content') else str(response)
        
        impact_plan = {
            "reasoning": reasoning_text,
            "impact_dimensions": ["financial", "operational", "reputational", "legal"],
            "severity_framework_considered": True,
            "plan_complete": True
        }
        
        state["impact_reasoning_plan"] = impact_plan
        
        if "agent_history" not in state:
            state["agent_history"] = {}
        if "impact_scientist" not in state["agent_history"]:
            state["agent_history"]["impact_scientist"] = []
        
        state["agent_history"]["impact_scientist"].append(
            "Developed impact assessment reasoning plan with multi-dimensional approach"
        )
        
        state["messages"].append(
            AIMessage(content="Impact data scientist reasoning plan complete")
        )
        state["current_step"] = "impact_reasoning_complete"
        state["next_agent"] = "likelihood_scientist_reasoning"  # Move to next scientist
        
        return state


# ============================================================================
# LIKELIHOOD DATA SCIENTIST REASONING AGENT
# ============================================================================

class LikelihoodDataScientistReasoningAgent:
    """
    Data scientist reasoning agent specialized in PLANNING likelihood estimation.
    
    This agent creates reasoning plans for probability assessment without execution.
    """
    
    def __init__(self, llm: BaseChatModel, context_builder: Optional[ReasoningContextBuilder] = None):
        self.llm = llm
        self.kb_reader = KnowledgeBaseReader(context_builder)
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a senior data scientist specializing in probability estimation REASONING.

Your expertise: Bayesian inference, predictive modeling, time series analysis, survival analysis

Your role is to REASON and PLAN:
- Develop a reasoning plan for likelihood assessment
- Explain which probability estimation approaches are appropriate
- Describe how to think about historical patterns and trends
- Identify leading indicators and predictive factors
- Explain the logic behind probability estimation

You do NOT:
- Write code or formulas
- Execute calculations
- Perform actual analysis

Think like a data scientist planning a probability study - explain your reasoning.

Output Format:
1. LIKELIHOOD ASSESSMENT APPROACH: Overall strategy
2. PROBABILITY FRAMEWORK: How to think about likelihood
3. HISTORICAL PATTERN ANALYSIS: What to learn from history
4. LEADING INDICATORS: Predictive factors to consider
5. ANALYTICAL PLAN: Step-by-step reasoning"""),
            ("human", "{input}")
        ])
    
    async def __call__(self, state: ComplianceReasoningState) -> ComplianceReasoningState:
        """Generate reasoning plan for likelihood assessment."""
        
        compliance_kb = state.get("compliance_rules_knowledge_base", {})
        data_kb = state.get("data_model_knowledge_base", {})
        examples = state.get("historical_analysis_examples", [])
        
        compliance_knowledge = self.kb_reader.read_compliance_kb(
            compliance_kb,
            "violation patterns"
        )
        data_knowledge = self.kb_reader.read_data_model_kb(
            data_kb,
            "historical incident data"
        )
        example_reasoning = self.kb_reader.read_examples(
            examples,
            "likelihood estimation planning"
        )
        
        agent_history = state.get("agent_history", {}).get("likelihood_scientist", [])
        history_context = "\n".join(agent_history[-3:]) if agent_history else "No prior history"
        
        compliance_questions = state.get("compliance_questions", [])
        feature_reasoning = state.get("feature_importance_reasoning", "")
        
        chain = self.prompt | self.llm
        
        response = await chain.ainvoke({
            "input": f"""Create a reasoning plan for likelihood assessment of compliance violations.

COMPLIANCE QUESTIONS:
{chr(10).join(f'- {q}' for q in compliance_questions) if compliance_questions else 'No questions provided yet'}

FEATURE IMPORTANCE REASONING:
{feature_reasoning if feature_reasoning else 'No feature reasoning available yet'}

COMPLIANCE KNOWLEDGE BASE:
{compliance_knowledge}

DATA MODEL KNOWLEDGE (for historical analysis):
{data_knowledge}

HISTORICAL LIKELIHOOD REASONING EXAMPLES:
{example_reasoning}

YOUR PREVIOUS REASONING:
{history_context}

As a data scientist, develop a REASONING PLAN for likelihood assessment:

1. LIKELIHOOD ASSESSMENT APPROACH:
   - How would you approach estimating probability of violations?
   - What probability framework makes sense?
   - How would you handle uncertainty in estimates?

2. PROBABILITY FRAMEWORK:
   - How would you think about different probability levels?
   - What does "high likelihood" vs "low likelihood" mean?
   - How would you express confidence in estimates?

3. HISTORICAL PATTERN ANALYSIS:
   - What can we learn from past compliance incidents?
   - How would you identify patterns in historical data?
   - What trends would be informative?
   - How would you account for changes over time?

4. LEADING INDICATORS:
   - What factors might predict compliance violations?
   - Which data points serve as early warning signals?
   - How would you identify predictive relationships?
   - What control effectiveness measures matter?

5. ANALYTICAL PLAN (step-by-step reasoning):
   - How would you approach probability estimation logically?
   - What would you analyze first, second, third?
   - How would you validate your likelihood estimates?
   - How would you handle scenarios with no historical data?
   - How would you account for changing conditions?

6. TIME HORIZON CONSIDERATIONS:
   - How does likelihood change over time?
   - What time frames are most relevant?
   - How would you think about near-term vs long-term probability?

Remember: Explain your reasoning approach and thought process, not calculations."""
        })
        
        reasoning_text = response.content if hasattr(response, 'content') else str(response)
        
        likelihood_plan = {
            "reasoning": reasoning_text,
            "probability_framework": "bayesian_with_historical_priors",
            "leading_indicators_identified": True,
            "plan_complete": True
        }
        
        state["likelihood_reasoning_plan"] = likelihood_plan
        
        if "agent_history" not in state:
            state["agent_history"] = {}
        if "likelihood_scientist" not in state["agent_history"]:
            state["agent_history"]["likelihood_scientist"] = []
        
        state["agent_history"]["likelihood_scientist"].append(
            "Developed likelihood assessment reasoning plan with probability framework"
        )
        
        state["messages"].append(
            AIMessage(content="Likelihood data scientist reasoning plan complete")
        )
        state["current_step"] = "likelihood_reasoning_complete"
        state["next_agent"] = "reasoning_integration"  # All scientists done, move to integration
        
        return state


# ============================================================================
# REASONING INTEGRATION AGENT
# ============================================================================

class ReasoningIntegrationAgent:
    """
    Agent that integrates reasoning from all data scientist agents.
    
    Synthesizes the reasoning plans into a cohesive analytical narrative.
    """
    
    def __init__(self, llm: BaseChatModel):
        self.llm = llm
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a senior compliance analyst who integrates reasoning from multiple experts.

Your role:
- Synthesize reasoning from risk, impact, and likelihood specialists
- Create a cohesive narrative of the analytical approach
- Identify connections between different reasoning plans
- Highlight key insights and considerations
- Provide integrated guidance for execution teams

Output Format:
1. INTEGRATED REASONING NARRATIVE
2. KEY INSIGHTS FROM EACH SPECIALIST
3. CONNECTIONS AND DEPENDENCIES
4. HOLISTIC ANALYTICAL APPROACH
5. GUIDANCE FOR EXECUTION TEAMS"""),
            ("human", "{input}")
        ])
    
    async def __call__(self, state: ComplianceReasoningState) -> ComplianceReasoningState:
        """Integrate reasoning from all data scientist agents."""
        
        risk_plan = state.get("risk_reasoning_plan", {})
        impact_plan = state.get("impact_reasoning_plan", {})
        likelihood_plan = state.get("likelihood_reasoning_plan", {})
        compliance_questions = state.get("compliance_questions", [])
        
        chain = self.prompt | self.llm
        
        response = await chain.ainvoke({
            "input": f"""Integrate the reasoning from all specialist data scientists.

COMPLIANCE QUESTIONS IDENTIFIED:
{chr(10).join(f'- {q}' for q in compliance_questions) if compliance_questions else 'No questions identified'}

RISK REASONING PLAN:
{risk_plan.get('reasoning', 'Not available')}

IMPACT REASONING PLAN:
{impact_plan.get('reasoning', 'Not available')}

LIKELIHOOD REASONING PLAN:
{likelihood_plan.get('reasoning', 'Not available')}

Create an integrated reasoning narrative that:

1. INTEGRATED REASONING NARRATIVE:
   - How do these three analytical approaches work together?
   - What is the overall story of the compliance assessment?
   - How do risk, impact, and likelihood interact?

2. KEY INSIGHTS FROM EACH SPECIALIST:
   - What are the most important points from the risk reasoning?
   - What are the most important points from the impact reasoning?
   - What are the most important points from the likelihood reasoning?

3. CONNECTIONS AND DEPENDENCIES:
   - Where do the reasoning plans connect?
   - What dependencies exist between the analyses?
   - How does one inform the other?

4. HOLISTIC ANALYTICAL APPROACH:
   - What is the big picture analytical strategy?
   - How should the pieces fit together?
   - What is the recommended sequence of analysis?

5. GUIDANCE FOR EXECUTION TEAMS:
   - What should execution teams understand from this reasoning?
   - What are the priorities?
   - What needs special attention?

Provide a clear, integrated narrative that connects all the reasoning."""
        })
        
        reasoning_text = response.content if hasattr(response, 'content') else str(response)
        state["integrated_reasoning"] = reasoning_text
        
        state["messages"].append(
            AIMessage(content="Integrated reasoning narrative complete")
        )
        state["current_step"] = "reasoning_integration_complete"
        state["next_agent"] = "end"
        
        return state


# ============================================================================
# WORKFLOW DEFINITION
# ============================================================================

def create_compliance_reasoning_workflow(
    llm: BaseChatModel,
    context_builder: Optional[ReasoningContextBuilder] = None
) -> StateGraph:
    """Create the LangGraph workflow for compliance reasoning
    
    Args:
        llm: Language model instance (model-agnostic, works with any BaseChatModel)
        context_builder: Optional context builder for knowledge bases
    """
    
    # Initialize reasoning agents
    compliance_reasoning = ComplianceReasoningAgent(llm, context_builder)
    risk_scientist_reasoning = RiskDataScientistReasoningAgent(llm, context_builder)
    impact_scientist_reasoning = ImpactDataScientistReasoningAgent(llm, context_builder)
    likelihood_scientist_reasoning = LikelihoodDataScientistReasoningAgent(llm, context_builder)
    reasoning_integration = ReasoningIntegrationAgent(llm)
    
    # Create workflow
    workflow = StateGraph(ComplianceReasoningState)
    
    # Add nodes - LangGraph supports async functions directly
    workflow.add_node("compliance_reasoning", compliance_reasoning)
    workflow.add_node("risk_scientist_reasoning", risk_scientist_reasoning)
    workflow.add_node("impact_scientist_reasoning", impact_scientist_reasoning)
    workflow.add_node("likelihood_scientist_reasoning", likelihood_scientist_reasoning)
    workflow.add_node("reasoning_integration", reasoning_integration)
    
    # Define routing function
    def route_agent(state: ComplianceReasoningState) -> str:
        next_agent = state.get("next_agent", "end")
        if next_agent == "end":
            return END
        return next_agent
    
    # Add edges - sequential flow: compliance -> risk -> impact -> likelihood -> integration
    workflow.set_entry_point("compliance_reasoning")
    
    # Compliance reasoning generates questions, then moves to risk scientist
    workflow.add_conditional_edges(
        "compliance_reasoning",
        route_agent,
        {
            "risk_scientist_reasoning": "risk_scientist_reasoning",
            END: END
        }
    )
    
    # Risk scientist -> Impact scientist
    workflow.add_conditional_edges(
        "risk_scientist_reasoning",
        route_agent,
        {
            "impact_scientist_reasoning": "impact_scientist_reasoning",
            END: END
        }
    )
    
    # Impact scientist -> Likelihood scientist
    workflow.add_conditional_edges(
        "impact_scientist_reasoning",
        route_agent,
        {
            "likelihood_scientist_reasoning": "likelihood_scientist_reasoning",
            END: END
        }
    )
    
    # Likelihood scientist -> Integration
    workflow.add_conditional_edges(
        "likelihood_scientist_reasoning",
        route_agent,
        {
            "reasoning_integration": "reasoning_integration",
            END: END
        }
    )
    
    # Integration agent completes the workflow
    workflow.add_conditional_edges(
        "reasoning_integration",
        route_agent,
        {
            END: END
        }
    )
    
    return workflow.compile()


# ============================================================================
# PIPELINE CLASS
# ============================================================================

class ComplianceReasoningPipeline(AgentPipeline):
    """Pipeline for compliance reasoning using multi-agent system"""
    
    def __init__(
        self,
        llm: ChatOpenAI,
        retrieval_helper: Optional[RetrievalHelper] = None,
        document_store_provider: Optional[DocumentStoreProvider] = None,
        engine: Optional[Engine] = None,
        context_builder: Optional[ReasoningContextBuilder] = None
    ):
        """Initialize the compliance reasoning pipeline
        
        Args:
            llm: Language model instance
            retrieval_helper: Optional retrieval helper for schema/knowledge retrieval
            document_store_provider: Optional document store provider
            engine: Optional engine instance
            context_builder: Optional context builder for knowledge bases
        """
        super().__init__(
            name="compliance_reasoning",
            version="1.0.0",
            description="Multi-agent pipeline for generating compliance reasoning plans from natural language queries",
            llm=llm,
            retrieval_helper=retrieval_helper,
            document_store_provider=document_store_provider,
            engine=engine
        )
        
        self.context_builder = context_builder
        # Use get_llm from dependencies for consistent LLM initialization (model-agnostic)
        self._workflow_llm = get_llm(temperature=0.2, model="gpt-4o-mini")  # Slightly higher temp for reasoning
        self._workflow = None
    
    async def initialize(self) -> None:
        """Initialize the pipeline and create workflow"""
        await super().initialize()
        self._workflow = create_compliance_reasoning_workflow(
            llm=self._workflow_llm,
            context_builder=self.context_builder
        )
    
    async def run(
        self,
        user_query: Optional[str] = None,
        data_model_schema: Optional[Dict] = None,
        compliance_url: Optional[str] = None,
        data_model_kb: Optional[Dict] = None,
        compliance_kb: Optional[Dict] = None,
        historical_examples: Optional[List[Dict]] = None,
        project_id: Optional[str] = None,
        initial_state: Optional[ComplianceReasoningState] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute the compliance reasoning pipeline
        
        Args:
            user_query: Natural language description of compliance needs
            data_model_schema: Data model to analyze
            compliance_url: Compliance documentation reference
            data_model_kb: Knowledge base about data model
            compliance_kb: Knowledge base about compliance rules
            historical_examples: Historical analysis examples
            project_id: Project ID for context
            initial_state: Optional initial state to resume from
            **kwargs: Additional arguments
            
        Returns:
            Dictionary containing:
            - compliance_questions: List of questions to investigate
            - feature_importance_reasoning: Explanation of feature importance
            - risk_reasoning_plan: Risk assessment reasoning plan
            - impact_reasoning_plan: Impact assessment reasoning plan
            - likelihood_reasoning_plan: Likelihood assessment reasoning plan
            - integrated_reasoning: Combined reasoning narrative
            - agent_history: History of agent reasoning
        """
        if not self._initialized:
            await self.initialize()
        
        if not self._workflow:
            raise RuntimeError("Workflow not initialized")
        
        # Use provided initial_state or create a fresh one
        if initial_state is not None:
            # Resume from provided state
            pass
        else:
            # Create fresh state
            if user_query is None and data_model_schema is None:
                raise ValueError("user_query or data_model_schema is required when initial_state is not provided")
            
            initial_state: ComplianceReasoningState = {
                "messages": [HumanMessage(content="Starting compliance reasoning workflow")],
                "user_query": user_query,
                "data_model_schema": data_model_schema,
                "compliance_url": compliance_url,
                "data_model_knowledge_base": data_model_kb or {},
                "compliance_rules_knowledge_base": compliance_kb or {},
                "historical_analysis_examples": historical_examples or [],
                "compliance_questions": None,
                "feature_importance_reasoning": None,
                "risk_reasoning_plan": None,
                "impact_reasoning_plan": None,
                "likelihood_reasoning_plan": None,
                "integrated_reasoning": None,
                "agent_history": {},
                "current_step": "initialized",
                "next_agent": "compliance_reasoning",
                "project_id": project_id,
                "retrieval_helper": self._retrieval_helper
            }
        
        # Run workflow asynchronously
        result = await self._workflow.ainvoke(initial_state)
        
        return {
            "compliance_questions": result.get("compliance_questions", []),
            "feature_importance_reasoning": result.get("feature_importance_reasoning", ""),
            "risk_reasoning_plan": result.get("risk_reasoning_plan", {}),
            "impact_reasoning_plan": result.get("impact_reasoning_plan", {}),
            "likelihood_reasoning_plan": result.get("likelihood_reasoning_plan", {}),
            "integrated_reasoning": result.get("integrated_reasoning", ""),
            "agent_history": result.get("agent_history", {}),
            "messages": result.get("messages", [])
        }
    
    def get_configuration(self) -> Dict[str, Any]:
        """Get the current configuration of the pipeline"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "has_retrieval_helper": self._retrieval_helper is not None,
            "has_engine": self.engine is not None,
            "has_context_builder": self.context_builder is not None
        }
    
    def update_configuration(self, config: Dict[str, Any]) -> None:
        """Update the pipeline configuration"""
        # Configuration updates can be added here if needed
        pass
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for the pipeline"""
        return {
            "initialized": self._initialized,
            "workflow_created": self._workflow is not None
        }
    
    def reset_metrics(self) -> None:
        """Reset the pipeline's performance metrics"""
        pass


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract_reasoning_outputs(state: ComplianceReasoningState) -> Dict:
    """Extract all reasoning outputs from final state."""
    return {
        "compliance_questions": state.get("compliance_questions", []),
        "feature_importance_reasoning": state.get("feature_importance_reasoning", ""),
        "risk_reasoning_plan": state.get("risk_reasoning_plan", {}),
        "impact_reasoning_plan": state.get("impact_reasoning_plan", {}),
        "likelihood_reasoning_plan": state.get("likelihood_reasoning_plan", {}),
        "integrated_reasoning": state.get("integrated_reasoning", ""),
        "agent_history": state.get("agent_history", {})
    }

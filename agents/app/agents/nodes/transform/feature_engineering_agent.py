"""
Deep Research Feature Engineering Agentic Pipeline using LangGraph

This module implements a deep research agent for compliance risk estimation, monitoring, and reporting
using a MEDALLION ARCHITECTURE (Bronze/Silver/Gold).

Deep Research Workflow (Compliance-First Approach)
===================================================
This workflow generates detailed natural language questions for compliance control monitoring
in a medallion architecture. The process is:

1. COMPLIANCE IDENTIFICATION: Identify most important compliances based on:
   - User query and analytical goal
   - Knowledge documents (compliance frameworks, best practices)
   - Historical examples and patterns
   - Domain-specific compliance requirements

2. CONTROL IDENTIFICATION: For each compliance framework:
   - Identify relevant compliance controls
   - Fetch knowledge documents for each control using retrieval_helper
   - Identify key measures/metrics needed for each control

3. FEATURE GENERATION: For each control, generate:
   - Detailed natural language questions (step-by-step, executable)
   - Medallion architecture classification (SILVER or GOLD):
     * SILVER: Transformations from raw data (bronze). Basic calculations, cleaning, normalization.
     * GOLD: Requires other transformations or aggregations. Complex multi-step calculations.
   - Feature metadata (calculation logic, required schemas, compliance reasoning)

4. DEEP RESEARCH REVIEW: Review recommendations and relevancy scores:
   - Control coverage analysis
   - Natural language question quality
   - Medallion architecture validation
   - Quality improvements

The workflow generates natural language questions like:
- "Calculate raw_risk score for each asset by first calculating raw_impact, then calculating raw_likelihood from breach method likelihoods and asset exposure, then combining them with appropriate weighting"
- "For each vulnerability based on the severity, vulnerability definition, vulnerability remediation availability and attack vector lets calculate the exploitability score, breach likelihood and risk scores"

These questions are designed to be executed by transformation agents in a medallion architecture.
"""

import asyncio
import logging
import re
import json
import time
from typing import TypedDict, Annotated, Sequence, List, Dict, Any, Optional
import operator
from pathlib import Path
from datetime import datetime
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.agents.pipelines.base import AgentPipeline
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.engine import Engine
from app.core.provider import DocumentStoreProvider
from app.core.dependencies import get_llm
from app.agents.nodes.transform.domain_config import (
    DomainConfiguration,
    get_domain_config,
    CYBERSECURITY_DOMAIN_CONFIG
)

# Import shared types, models, and utilities
from app.agents.nodes.transform.feature_engineering_types import (
    FeatureEngineeringState,
    TimeConstraints,
    AnalyticalIntent,
    SchemaMapping,
    FeatureRecommendation,
    ReasoningPlan,
    ClarifyingQuestion,
    FeatureDependency,
    FeatureDependencyGraph,
    RelevanceScore,
    RelevancyScoringResult,
    QueryBreakdown,
    QueryBreakdownStep,
    track_llm_call
)

# Import deep research capabilities
from app.agents.nodes.transform.deep_research import DeepResearchReviewAgent

# Import risk feature engineering agent
from app.agents.nodes.transform.risk_feature_engineering_agent import RiskFeatureEngineeringAgent

# Import control universe model for SOC2 control identification
try:
    from control_universe_model import (
        Control,
        SubControl,
        ComplianceControlUniverse
    )
    CONTROL_UNIVERSE_AVAILABLE = True
except ImportError:
    CONTROL_UNIVERSE_AVAILABLE = False

logger = logging.getLogger("lexy-ai-service")

# Log warning after logger is defined
if not CONTROL_UNIVERSE_AVAILABLE:
    logger.warning("control_universe_model not available, control identification will be limited")


# ============================================================================
# AGENT DEFINITIONS
# ============================================================================

class QueryBreakdownAgent:
    """
    First step agent that breaks down the user query into multiple analytical steps.
    
    This agent uses the domain configuration to understand the domain context and
    breaks down complex compliance report requests into manageable steps that can
    track risk, impact, likelihood trends, and general metrics.
    """
    
    def __init__(self, llm: BaseChatModel, domain_config: DomainConfiguration):
        # Use with_structured_output if available
        if hasattr(llm, 'with_structured_output'):
            self.llm = llm.with_structured_output(QueryBreakdown)
        else:
            self.llm = llm
            logger.warning("LLM does not support with_structured_output, using regular LLM")
        self.domain_config = domain_config
    
    def _get_domain_config_from_state(self, state: FeatureEngineeringState) -> DomainConfiguration:
        """Get domain config from state or use instance config"""
        domain_config_dict = state.get("domain_config")
        if domain_config_dict:
            return DomainConfiguration(**domain_config_dict)
        return self.domain_config
    
    async def __call__(self, state: FeatureEngineeringState) -> FeatureEngineeringState:
        """
        Break down user query into multiple analytical steps using domain context.
        
        The breakdown identifies:
        - Steps for risk trend tracking
        - Steps for impact trend tracking
        - Steps for likelihood trend tracking
        - Steps for general metrics
        - Compliance framework requirements
        - Entity types and focus areas
        """
        # Check if we're resuming to a later step
        next_agent = state.get("next_agent", "")
        if next_agent and next_agent not in ["breakdown_analysis", "query_understanding", "end", ""]:
            logger.info(f"Skipping QueryBreakdownAgent - resuming to {next_agent}")
            return state
        
        # Get domain config from state or use instance config
        domain_config = self._get_domain_config_from_state(state)
        
        user_query = state.get("user_query", "")
        if not user_query:
            logger.warning("No user query provided, skipping query breakdown")
            state["next_agent"] = "query_understanding"
            return state
        
        # Check if breakdown already exists
        if state.get("query_breakdown"):
            logger.info("Query breakdown already exists, skipping")
            state["next_agent"] = "query_understanding"
            return state
        
        logger.info(f"Breaking down query for domain: {domain_config.domain_name}")
        
        # Build prompt with domain context
        domain_context = self._format_domain_context(domain_config)
        
        prompt = f"""You are an expert compliance analyst specializing in {domain_config.domain_name} domain.

Your task is to:
1. Identify the overall analytical intent and goals
2. Identify applicable compliance frameworks
3. Break down the user's compliance report request into multiple analytical steps

DOMAIN CONTEXT:
{domain_context}

USER QUERY:
{user_query}

FIRST, identify:
1. **Overall Goal**: What is the overarching analytical goal of this query? (e.g., "Track vulnerability risk trends for SOC2 compliance", "Monitor training completion for GDPR compliance")
2. **Analytical Intent**: What does the user want to achieve or understand? (e.g., "Understand risk posture", "Monitor compliance status", "Track remediation effectiveness")
3. **Applicable Compliance Frameworks**: Which compliance frameworks are relevant? (e.g., {', '.join(domain_config.compliance_frameworks[:5]) if domain_config.compliance_frameworks else 'SOC2, GDPR, HIPAA, PCI-DSS'})
4. **Primary Goals**: List 2-5 primary goals that need to be accomplished (e.g., ["Track risk trends", "Monitor SLA compliance", "Assess impact of vulnerabilities"])

THEN, break down this query into multiple analytical steps. Each step should:
1. Focus on a specific aspect of the compliance report (risk trends, impact trends, likelihood trends, general metrics, compliance tracking)
2. Identify the relevant compliance frameworks for that step
3. Specify entity types involved (e.g., {', '.join(domain_config.entity_types[:5]) if domain_config.entity_types else 'Asset, Vulnerability, Employee'})
4. Identify required metric types (count, rate, trend, risk_score, etc.)
5. Determine if time series/trending analysis is needed

STEP TYPES:
- 'risk_trend': Steps that track risk scores over time or across dimensions
- 'impact_trend': Steps that track impact/consequence trends
- 'likelihood_trend': Steps that track likelihood/probability trends
- 'general_metrics': Steps for standard operational metrics (counts, rates, percentages)
- 'compliance_tracking': Steps focused on compliance framework requirements
- 'other': Other analytical steps

For each step, provide:
- Step number and name
- Clear description of what this step accomplishes
- Step type (from the list above)
- Focus areas (specific entities, severity levels, etc.)
- Required metrics (count, rate, trend, risk_score, etc.)
- Relevant compliance frameworks
- Entity types involved

Break down the query into 3-8 steps that together cover all aspects of the user's request.
"""
        
        messages = [
            SystemMessage(content="You are an expert compliance analyst who breaks down complex compliance report requests into actionable analytical steps."),
            HumanMessage(content=prompt)
        ]
        
        try:
            # Track LLM call
            response = await track_llm_call(
                agent_name="query_breakdown",
                llm=self.llm,
                messages=messages,
                state=state,
                step_name="query_breakdown"
            )
            
            # Parse response
            if hasattr(self.llm, 'with_structured_output'):
                # Structured output already parsed
                breakdown = response
            else:
                # Parse JSON from response
                content = response.content if hasattr(response, 'content') else str(response)
                breakdown = self._parse_breakdown(content, user_query, domain_config.domain_name)
            
            # Store breakdown in state
            state["query_breakdown"] = breakdown.model_dump() if hasattr(breakdown, 'model_dump') else breakdown.dict() if hasattr(breakdown, 'dict') else breakdown
            
            logger.info(f"Query broken down into {len(breakdown.breakdown_steps)} steps")
            
            # Route to next agent
            state["next_agent"] = "query_understanding"
            
            return state
            
        except Exception as e:
            logger.error(f"Error in QueryBreakdownAgent: {e}")
            import traceback
            traceback.print_exc()
            # Continue without breakdown
            state["next_agent"] = "query_understanding"
            return state
    
    def _format_domain_context(self, domain_config: DomainConfiguration) -> str:
        """Format domain configuration as context for the LLM"""
        context_parts = [
            f"Domain: {domain_config.domain_name}",
            f"Description: {domain_config.domain_description}",
        ]
        
        if domain_config.entity_types:
            context_parts.append(f"Entity Types: {', '.join(domain_config.entity_types)}")
        
        if domain_config.severity_levels:
            context_parts.append(f"Severity Levels: {', '.join(domain_config.severity_levels)}")
        
        if domain_config.compliance_frameworks:
            context_parts.append(f"Compliance Frameworks: {', '.join(domain_config.compliance_frameworks)}")
        
        if domain_config.aggregation_levels:
            context_parts.append(f"Aggregation Levels: {', '.join(domain_config.aggregation_levels)}")
        
        if domain_config.default_context:
            context_parts.append(f"Default Context: {json.dumps(domain_config.default_context, indent=2)}")
        
        return "\n".join(context_parts)
    
    def _parse_breakdown(self, content: str, user_query: str, domain: str) -> QueryBreakdown:
        """Parse breakdown from LLM response text"""
        try:
            # Try to extract JSON
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                data = json.loads(json_match.group(0))
                
                # Extract intent, goals, and compliance frameworks
                overall_goal = data.get('overall_goal', '')
                analytical_intent = data.get('analytical_intent', '')
                applicable_compliance_frameworks = data.get('applicable_compliance_frameworks', [])
                primary_goals = data.get('primary_goals', [])
                
                # If not in top level, try to extract from breakdown_steps
                if not overall_goal and not analytical_intent:
                    # Try to infer from first step or content
                    steps = data.get('breakdown_steps', [])
                    if steps:
                        first_step = steps[0] if isinstance(steps[0], dict) else steps[0].dict() if hasattr(steps[0], 'dict') else {}
                        overall_goal = first_step.get('description', user_query[:200])
                        analytical_intent = f"Analyze {first_step.get('step_name', 'compliance metrics')}"
                
                # Extract compliance frameworks from steps if not at top level
                if not applicable_compliance_frameworks:
                    steps = data.get('breakdown_steps', [])
                    frameworks_set = set()
                    for step in steps:
                        step_dict = step if isinstance(step, dict) else step.dict() if hasattr(step, 'dict') else {}
                        frameworks_set.update(step_dict.get('compliance_frameworks', []))
                    applicable_compliance_frameworks = list(frameworks_set)
                
                # Create QueryBreakdown with all fields
                return QueryBreakdown(
                    original_query=user_query,
                    domain=domain,
                    overall_goal=overall_goal or user_query[:200],
                    analytical_intent=analytical_intent or f"Analyze compliance metrics for {domain}",
                    applicable_compliance_frameworks=applicable_compliance_frameworks,
                    primary_goals=primary_goals or [overall_goal] if overall_goal else [],
                    breakdown_steps=data.get('breakdown_steps', []),
                    time_series_requirements=data.get('time_series_requirements', False)
                )
        except Exception as e:
            logger.warning(f"Error parsing breakdown: {e}")
        
        # Fallback: create a simple breakdown
        return QueryBreakdown(
            original_query=user_query,
            domain=domain,
            overall_goal=user_query[:200],
            analytical_intent=f"Analyze compliance metrics for {domain}",
            applicable_compliance_frameworks=[],
            primary_goals=[user_query[:100]],
            breakdown_steps=[
                QueryBreakdownStep(
                    step_number=1,
                    step_name="General Analysis",
                    description=user_query[:200],
                    step_type="general_metrics",
                    focus_areas=[],
                    required_metrics=["count", "rate"],
                    compliance_frameworks=[],
                    entity_types=[]
                )
            ],
            time_series_requirements=False
        )


class QueryUnderstandingAgent:
    """
    Deep Research Agent: Parses user query and identifies most important compliances based on knowledge, history, and examples
    
    Note: This agent checks if we're resuming to a later step (follow-up scenario) and skips execution
    if next_agent is already set to a later node. This prevents the workflow from re-running initial
    steps when resuming from a previous state.
    """
    
    def __init__(self, llm: BaseChatModel, domain_config: DomainConfiguration, retrieval_helper: Optional[RetrievalHelper] = None):
        # Use with_structured_output if available, otherwise use regular llm
        if hasattr(llm, 'with_structured_output'):
            self.llm = llm.with_structured_output(AnalyticalIntent)
        else:
            self.llm = llm
            logger.warning("LLM does not support with_structured_output, using regular LLM")
        self.domain_config = domain_config
        self.retrieval_helper = retrieval_helper
    
    def _get_domain_config_from_state(self, state: FeatureEngineeringState) -> DomainConfiguration:
        """Get domain config from state or use instance config"""
        domain_config_dict = state.get("domain_config")
        if domain_config_dict:
            return DomainConfiguration(**domain_config_dict)
        return self.domain_config
    
    def _format_breakdown_context(self, query_breakdown: Dict[str, Any]) -> str:
        """Format query breakdown as context for query understanding"""
        if not query_breakdown:
            return ""
        
        context_parts = [
            "=== QUERY BREAKDOWN CONTEXT ===",
            f"Original Query: {query_breakdown.get('original_query', 'N/A')}",
            f"Domain: {query_breakdown.get('domain', 'N/A')}",
            f"Overall Goal: {query_breakdown.get('overall_goal', 'N/A')}",
            f"Analytical Intent: {query_breakdown.get('analytical_intent', 'N/A')}",
            f"Applicable Compliance Frameworks: {', '.join(query_breakdown.get('applicable_compliance_frameworks', [])) or 'N/A'}",
            f"Primary Goals: {', '.join(query_breakdown.get('primary_goals', [])) or 'N/A'}",
            f"Time Series Requirements: {query_breakdown.get('time_series_requirements', False)}"
        ]
        
        # Add breakdown steps
        breakdown_steps = query_breakdown.get("breakdown_steps", [])
        if breakdown_steps:
            context_parts.append(f"\nAnalytical Steps ({len(breakdown_steps)} total):")
            for i, step in enumerate(breakdown_steps, 1):
                step_name = step.get("step_name", "") if isinstance(step, dict) else getattr(step, "step_name", "")
                step_type = step.get("step_type", "") if isinstance(step, dict) else getattr(step, "step_type", "")
                description = step.get("description", "") if isinstance(step, dict) else getattr(step, "description", "")
                focus_areas = step.get("focus_areas", []) if isinstance(step, dict) else getattr(step, "focus_areas", [])
                required_metrics = step.get("required_metrics", []) if isinstance(step, dict) else getattr(step, "required_metrics", [])
                compliance_frameworks = step.get("compliance_frameworks", []) if isinstance(step, dict) else getattr(step, "compliance_frameworks", [])
                entity_types = step.get("entity_types", []) if isinstance(step, dict) else getattr(step, "entity_types", [])
                
                context_parts.append(f"\n  Step {i}: {step_name} ({step_type})")
                context_parts.append(f"    Description: {description[:200]}")
                if focus_areas:
                    context_parts.append(f"    Focus Areas: {', '.join(focus_areas[:5])}")
                if required_metrics:
                    context_parts.append(f"    Required Metrics: {', '.join(required_metrics[:5])}")
                if compliance_frameworks:
                    context_parts.append(f"    Compliance Frameworks: {', '.join(compliance_frameworks[:5])}")
                if entity_types:
                    context_parts.append(f"    Entity Types: {', '.join(entity_types[:5])}")
        
        context_parts.append("\nUse this breakdown to better understand the analytical intent and identify relevant compliance frameworks and controls.")
        
        return "\n".join(context_parts)
        
    async def __call__(self, state: FeatureEngineeringState) -> FeatureEngineeringState:
        """
        Deep Research: Identify most important compliances based on:
        1. User query and analytical goal
        2. Knowledge documents (compliance frameworks, best practices)
        3. Historical examples and patterns
        4. Domain-specific compliance requirements
        
        Goal: Suggest the most relevant compliance controls for risk estimation, monitoring, and reporting
        """
        
        # Check if we're resuming to a later step (follow-up scenario)
        # If next_agent is already set to a later step, skip this node
        # Only skip if next_agent is set to something that comes AFTER this agent
        next_agent = state.get("next_agent", "")
        if next_agent and next_agent not in ["query_understanding", "control_identification", "knowledge_retrieval", "end", ""]:
            # We're resuming to a later step, skip this node
            logger.info(f"Skipping QueryUnderstandingAgent - resuming to {next_agent}")
            return state
        
        # Get domain config from state or use instance config
        domain_config = self._get_domain_config_from_state(state)
        
        user_query = state.get("user_query", "")
        project_id = state.get("project_id")
        histories = state.get("histories", [])
        validation_expectations = state.get("validation_expectations", [])
        
        # Retrieve knowledge documents to identify relevant compliance frameworks
        knowledge_documents = []
        if self.retrieval_helper:
            try:
                knowledge_result = await self.retrieval_helper.get_knowledge_documents(
                    query=user_query,
                    project_id=project_id,
                    top_k=10,  # Get more documents for compliance identification
                    framework=None,  # Don't filter by framework yet
                    category=None
                )
                knowledge_documents = knowledge_result.get("documents", [])
                logger.info(f"Retrieved {len(knowledge_documents)} knowledge documents for compliance identification")
            except Exception as e:
                logger.warning(f"Error retrieving knowledge documents: {e}")
        
        # Format historical examples
        history_context = ""
        if histories:
            history_context = "\n\nHISTORICAL EXAMPLES:\n"
            for i, hist in enumerate(histories[:5], 1):  # Use top 5 historical examples
                history_context += f"{i}. {hist}\n"
        
        # Format validation expectations/examples
        examples_context = ""
        if validation_expectations:
            examples_context = "\n\nPROVIDED EXAMPLES/EXPECTATIONS:\n"
            for i, exp in enumerate(validation_expectations, 1):
                examples_context += f"{i}. {exp}\n"
        
        # Format knowledge documents for compliance identification
        knowledge_context = ""
        if knowledge_documents:
            knowledge_context = "\n\nRELEVANT KNOWLEDGE:\n"
            frameworks_found = set()
            for doc in knowledge_documents[:10]:
                metadata = doc.get("metadata", {})
                framework = metadata.get("framework", "")
                category = metadata.get("category", "")
                if framework:
                    frameworks_found.add(framework)
                if framework or category:
                    knowledge_context += f"- {framework or 'General'} ({category or 'N/A'})\n"
        
        # Use custom prompt if provided, otherwise use default
        if domain_config.query_understanding_prompt:
            system_prompt = domain_config.query_understanding_prompt
        else:
            domain_desc = domain_config.domain_description or domain_config.domain_name
            entity_types = ", ".join(domain_config.entity_types) if domain_config.entity_types else "entities"
            time_terms = ", ".join(domain_config.time_constraint_terms) if domain_config.time_constraint_terms else "time constraints"
            compliance_frameworks = ', '.join(domain_config.compliance_frameworks) if domain_config.compliance_frameworks else 'N/A'
            
            system_prompt = f"""You are a deep research agent specializing in compliance risk estimation, monitoring, and reporting for {domain_desc}.

Your task is to identify the MOST IMPORTANT compliance frameworks and controls based on:
1. User's analytical goal and query
2. Knowledge documents (compliance frameworks, best practices, domain expertise)
3. Historical examples and patterns
4. Domain-specific compliance requirements

COMPLIANCE FRAMEWORKS IN THIS DOMAIN: {compliance_frameworks}

For risk estimation, monitoring, and reporting, identify:
1. Primary analytical goal (what risk/compliance metrics are needed)
2. Most relevant compliance framework(s) - prioritize based on:
   - Explicit mentions in query
   - Knowledge document relevance
   - Historical patterns
   - Domain best practices
3. Key compliance controls that need monitoring (will be identified in next step)
4. Severity/priority levels of interest - Common levels: {', '.join(domain_config.severity_levels) if domain_config.severity_levels else 'N/A'}
5. Time constraints ({time_terms})
6. Required metrics for risk estimation
7. Level of aggregation - Common levels: {', '.join(domain_config.aggregation_levels) if domain_config.aggregation_levels else 'N/A'}
8. Time-series requirements for monitoring

Entity types in this domain: {entity_types}

GOAL TRACKING: Focus on identifying compliance controls that enable:
- Risk estimation (likelihood × impact)
- Compliance monitoring (SLA tracking, control effectiveness)
- Compliance reporting (dashboards, metrics, trends)

Be thorough and prioritize compliance frameworks that are most relevant to the user's goal."""

        # Build user message with breakdown context if available
        query_breakdown = state.get("query_breakdown")
        breakdown_context_text = ""
        if query_breakdown:
            breakdown_context = self._format_breakdown_context(query_breakdown)
            breakdown_context_text = f"\n\n{breakdown_context}\n"

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"""{breakdown_context_text}USER QUERY: {user_query}
{knowledge_context}{history_context}{examples_context}

Identify the most important compliance frameworks and controls for this risk estimation, monitoring, and reporting goal.""")
        ]
        
        # Handle structured output or regular output with tracking
        if hasattr(self.llm, 'with_structured_output'):
            intent = await track_llm_call(
                agent_name="QueryUnderstandingAgent",
                llm=self.llm,
                messages=messages,
                state=state,
                step_name="query_understanding"
            )
            # Convert to dict using model_dump for Pydantic V2 compatibility
            if hasattr(intent, 'model_dump'):
                state["analytical_intent"] = intent.model_dump()
            elif hasattr(intent, 'dict'):  # Fallback for Pydantic V1
                state["analytical_intent"] = intent.dict()
            else:
                state["analytical_intent"] = intent
        else:
            # Fallback: parse from regular LLM response with tracking
            response = await track_llm_call(
                agent_name="QueryUnderstandingAgent",
                llm=self.llm,
                messages=messages,
                state=state,
                step_name="query_understanding"
            )
            content = response.content if hasattr(response, 'content') else str(response)
            # Try to extract structured data from response
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                try:
                    parsed = json.loads(json_match.group(0))
                    state["analytical_intent"] = parsed
                except:
                    # Fallback to basic parsing
                    state["analytical_intent"] = {
                        "primary_goal": content[:200],
                        "compliance_framework": "",
                        "severity_levels": [],
                        "time_constraints": None,
                        "metrics_required": [],
                        "aggregation_level": "",
                        "time_series_requirements": False
                    }
            else:
                state["analytical_intent"] = {
                    "primary_goal": content[:200],
                    "compliance_framework": "",
                    "severity_levels": [],
                    "time_constraints": None,
                    "metrics_required": [],
                    "aggregation_level": "",
                    "time_series_requirements": False
                }
        
        # Store initial knowledge documents for later use
        state["knowledge_documents"] = knowledge_documents
        
        # Store domain config in state for other agents to use
        if "domain_config" not in state or not state.get("domain_config"):
            state["domain_config"] = domain_config.model_dump() if hasattr(domain_config, 'model_dump') else domain_config.dict()
        
        # Get primary goal from stored intent for message
        primary_goal = state.get("analytical_intent", {}).get("primary_goal", "Unknown")
        compliance_framework = state.get("analytical_intent", {}).get("compliance_framework", "").upper()
        
        state["messages"].append(AIMessage(
            content=f"Deep research: Identified goal '{primary_goal}' with compliance framework '{compliance_framework}' based on {len(knowledge_documents)} knowledge documents",
            name="QueryUnderstandingAgent"
        ))
        
        # Always route to control identification (compliance-first approach)
        state["next_agent"] = "control_identification"
        
        return state


class KnowledgeRefiningAgent:
    """Agent that refines the analytical intent using knowledge retrieval and provided instructions/examples"""
    
    def __init__(
        self, 
        llm: BaseChatModel, 
        retrieval_helper: Optional[RetrievalHelper] = None, 
        domain_config: Optional[DomainConfiguration] = None,
        instructions: Optional[str] = None,
        examples: Optional[List[Dict[str, Any]]] = None
    ):
        self.llm = llm
        self.retrieval_helper = retrieval_helper
        self.domain_config = domain_config or CYBERSECURITY_DOMAIN_CONFIG
        self.instructions = instructions or ""  # Placeholder for future instructions
        self.examples = examples or []  # Placeholder for future examples
    
    def _get_domain_config_from_state(self, state: FeatureEngineeringState) -> DomainConfiguration:
        """Get domain config from state or use instance config"""
        domain_config_dict = state.get("domain_config")
        if domain_config_dict:
            # Reconstruct from dict if available
            return DomainConfiguration(**domain_config_dict)
        return self.domain_config
    
    async def __call__(self, state: FeatureEngineeringState) -> FeatureEngineeringState:
        """Refine analytical intent using knowledge retrieval, instructions, and examples"""
        
        # Check if we're resuming to a later step (follow-up scenario)
        # Only skip if next_agent is set to something that comes AFTER this agent
        next_agent = state.get("next_agent", "")
        if next_agent and next_agent not in ["knowledge_retrieval", "schema_analysis", "end", ""]:
            # We're resuming to a later step, skip this node
            logger.info(f"Skipping KnowledgeRefiningAgent - resuming to {next_agent}")
            return state
        
        # Get domain config from state or use instance config
        domain_config = self._get_domain_config_from_state(state)
        
        # Get instructions and examples from state if provided, otherwise use instance values
        instructions = state.get("refining_instructions") or self.instructions
        examples = state.get("refining_examples") or self.examples
        
        intent = state.get("analytical_intent", {})
        user_query = state.get("user_query", "")
        project_id = state.get("project_id")
        
        # Extract framework and category from intent
        framework = intent.get("compliance_framework", "")
        if framework:
            # Normalize framework name
            framework = framework.upper().replace("-", "_")
            # Check if framework is in domain's compliance frameworks
            if framework not in [f.upper().replace("-", "_") for f in domain_config.compliance_frameworks]:
                # Try to match partial names
                for domain_framework in domain_config.compliance_frameworks:
                    if framework in domain_framework.upper() or domain_framework.upper() in framework:
                        framework = domain_framework.upper().replace("-", "_")
                        break
        
        # Determine category based on domain configuration mappings
        category = None
        query_lower = user_query.lower()
        
        # Use domain-specific category mappings
        for mapping in domain_config.category_mappings:
            if any(keyword in query_lower for keyword in mapping.keywords):
                category = mapping.category
                break
        
        knowledge_documents = []
        
        if self.retrieval_helper:
            try:
                # Retrieve knowledge documents
                knowledge_result = await self.retrieval_helper.get_knowledge_documents(
                    query=user_query,
                    project_id=project_id,
                    top_k=5,
                    framework=framework if framework else None,
                    category=category
                )
                
                knowledge_documents = knowledge_result.get("documents", [])
                
                logger.info(f"Retrieved {len(knowledge_documents)} knowledge documents")
                
            except Exception as e:
                logger.warning(f"Error retrieving knowledge documents: {e}")
                knowledge_documents = []
        else:
            logger.warning("RetrievalHelper not available, skipping knowledge retrieval")
        
        state["knowledge_documents"] = knowledge_documents
        state["messages"].append(AIMessage(
            content=f"Refined analytical intent using {len(knowledge_documents)} knowledge documents"
            + (f" and {len(examples)} examples" if examples else ""),
            name="KnowledgeRefiningAgent"
        ))
        state["next_agent"] = "schema_analysis"
        
        return state


class SchemaAnalysisAgent:
    """Agent that maps requirements to available data schemas"""
    
    def __init__(self, llm: BaseChatModel, retrieval_helper: Optional[RetrievalHelper] = None, domain_config: Optional[DomainConfiguration] = None):
        self.llm = llm
        self.retrieval_helper = retrieval_helper
        self._schema_cache: Dict[str, Dict[str, Any]] = {}
        self.domain_config = domain_config or CYBERSECURITY_DOMAIN_CONFIG
        
    async def __call__(self, state: FeatureEngineeringState) -> FeatureEngineeringState:
        """Analyze which schemas are needed for the analytical intent"""
        
        # Check if we're resuming to a later step (follow-up scenario)
        # Only skip if next_agent is set to something that comes AFTER this agent
        next_agent = state.get("next_agent", "")
        if next_agent and next_agent not in ["schema_analysis", "question_generation", "end", ""]:
            # We're resuming to a later step, skip this node
            logger.info(f"Skipping SchemaAnalysisAgent - resuming to {next_agent}")
            return state
        
        intent = state.get("analytical_intent", {})
        if not intent:
            # If no intent, create a minimal one
            intent = {"primary_goal": state.get("user_query", "")[:200]}
        project_id = state.get("project_id")
        user_query = state.get("user_query", "")
        
        # Retrieve schemas using retrieval helper if available
        schema_registry = {}
        if self.retrieval_helper and project_id:
            try:
                schema_result = await self.retrieval_helper.get_database_schemas(
                    project_id=project_id,
                    table_retrieval={
                        "table_retrieval_size": 20,
                        "table_column_retrieval_size": 100,
                        "allow_using_db_schemas_without_pruning": False
                    },
                    query=user_query,
                    histories=state.get("histories"),
                    tables=None
                )
                
                # Build schema registry from retrieved schemas
                for schema in schema_result.get("schemas", []):
                    if isinstance(schema, dict):
                        table_name = schema.get("table_name", "")
                        table_ddl = schema.get("table_ddl", "")
                        relationships = schema.get("relationships", [])
                        
                        if table_name and table_ddl:
                            # Extract key fields from DDL
                            key_fields = self._extract_key_fields_from_ddl(table_ddl)
                            
                            # Extract description from DDL comments
                            description = self._extract_description_from_ddl(table_ddl)
                            
                            schema_registry[table_name] = {
                                "description": description or f"Table: {table_name}",
                                "key_fields": key_fields,
                                "relationships": [str(r) for r in relationships] if relationships else [],
                                "table_ddl": table_ddl
                            }
                
                # Cache for future use
                self._schema_cache[project_id] = schema_registry
                
            except Exception as e:
                logger.warning(f"Error retrieving schemas: {e}, using cached or empty registry")
                # Use cached schemas if available
                schema_registry = self._schema_cache.get(project_id, {})
        else:
            logger.warning("RetrievalHelper or project_id not available, using empty schema registry")
        
        system_prompt = f"""You are a data architecture expert. Given the analytical intent and available schemas,
identify which schemas are most relevant and explain why.

AVAILABLE SCHEMAS:
{self._format_schema_registry(schema_registry)}

ANALYTICAL INTENT:
{intent}

Provide a ranked list of relevant schemas with reasoning."""

        response = await track_llm_call(
            agent_name="SchemaAnalysisAgent",
            llm=self.llm,
            messages=[
                SystemMessage(content=system_prompt),
                HumanMessage(content="Analyze schema relevance")
            ],
            state=state,
            step_name="schema_analysis"
        )
        
        # Parse relevant schemas from response
        relevant_schemas = self._extract_schema_names(response.content, schema_registry)
        
        # Store schema registry in state for later use
        state["schema_registry"] = schema_registry
        state["relevant_schemas"] = relevant_schemas
        state["messages"].append(AIMessage(
            content=f"Identified relevant schemas: {', '.join(relevant_schemas)}",
            name="SchemaAnalysisAgent"
        ))
        state["next_agent"] = "question_generation"
        
        return state
    
    def _format_schema_registry(self, schema_registry: Dict[str, Any]) -> str:
        """Format schema registry for prompt"""
        if not schema_registry:
            return "No schemas available. Please ensure project_id and retrieval_helper are configured."
        
        formatted = []
        for name, info in schema_registry.items():
            desc = info.get("description", "")
            fields = info.get("key_fields", [])
            formatted.append(f"- {name}: {desc}\n  Key fields: {', '.join(fields[:10])}")  # Limit to first 10 fields
        
        return "\n".join(formatted)
    
    def _extract_key_fields_from_ddl(self, ddl: str) -> List[str]:
        """Extract key field names from DDL"""
        fields = []
        # Match column definitions (column_name TYPE)
        pattern = r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s+'
        for line in ddl.split('\n'):
            match = re.match(pattern, line.strip())
            if match:
                field_name = match.group(1)
                # Skip common SQL keywords
                if field_name.upper() not in ['CREATE', 'TABLE', 'PRIMARY', 'FOREIGN', 'KEY', 'CONSTRAINT', 'INDEX']:
                    fields.append(field_name)
        return fields[:20]  # Limit to first 20 fields
    
    def _extract_description_from_ddl(self, ddl: str) -> str:
        """Extract description from DDL comments"""
        lines = ddl.split('\n')
        for line in lines:
            if line.strip().startswith('--'):
                desc = line.strip()[2:].strip()
                if desc:
                    return desc
        return ""
    
    def _extract_schema_names(self, content: str, schema_registry: Dict[str, Any]) -> List[str]:
        """Extract schema names from LLM response"""
        schema_names = []
        content_lower = content.lower()
        
        # Check for mentions of schema names in the response
        for name in schema_registry.keys():
            if name.lower() in content_lower:
                schema_names.append(name)
        
        # If no schemas found, try to extract from the response text
        if not schema_names:
            # Look for patterns like "table_name", "schema_name", etc.
            patterns = [
                r'([a-zA-Z_][a-zA-Z0-9_]*)\s+(?:table|schema)',
                r'table[s]?\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            ]
            for pattern in patterns:
                matches = re.findall(pattern, content_lower)
                for match in matches:
                    if match in schema_registry:
                        schema_names.append(match)
        
        return list(set(schema_names))  # Remove duplicates


class QuestionGenerationAgent:
    """Agent that generates clarifying questions"""
    
    def __init__(self, llm: BaseChatModel, domain_config: DomainConfiguration):
        self.llm = llm
        self.domain_config = domain_config
    
    def _get_domain_config_from_state(self, state: FeatureEngineeringState) -> DomainConfiguration:
        """Get domain config from state or use instance config"""
        domain_config_dict = state.get("domain_config")
        if domain_config_dict:
            return DomainConfiguration(**domain_config_dict)
        return self.domain_config
        
    async def __call__(self, state: FeatureEngineeringState) -> FeatureEngineeringState:
        """Generate clarifying questions based on ambiguities"""
        
        # Check if we're resuming to a later step (follow-up scenario)
        # Only skip if next_agent is set to something that comes AFTER this agent
        next_agent = state.get("next_agent", "")
        if next_agent and next_agent not in ["question_generation", "group_planner", "feature_recommendation", "end", ""]:
            # We're resuming to a later step, skip this node
            logger.info(f"Skipping QuestionGenerationAgent - resuming to {next_agent}")
            return state
        
        # Get domain config from state or use instance config
        domain_config = self._get_domain_config_from_state(state)
        
        intent = state["analytical_intent"]
        knowledge_documents = state.get("knowledge_documents", [])
        
        # Format knowledge documents for context
        knowledge_context = ""
        if knowledge_documents:
            knowledge_context = "\n\nRELEVANT KNOWLEDGE:\n"
            for doc in knowledge_documents[:3]:  # Use top 3 for context
                metadata = doc.get("metadata", {})
                framework = metadata.get("framework", "")
                category = metadata.get("category", "")
                if framework or category:
                    knowledge_context += f"- {framework or 'General'} ({category or 'N/A'})\n"
        
        # Build domain-specific question types
        time_term = domain_config.time_constraint_terms[0] if domain_config.time_constraint_terms else "time constraints"
        entity_term = domain_config.entity_types[0] if domain_config.entity_types else "entities"
        
        system_prompt = f"""You are an expert at identifying ambiguities in analytics requirements.

Generate 3-5 clarifying questions that would help refine the feature engineering plan.
Focus on:
1. {time_term.title()} definitions and time windows
2. Specific metrics and data sources relevant to {domain_config.domain_name}
3. Scope and filters (which {entity_term.lower()}s, which categories)
4. Aggregation methods and grouping
5. Missing metric definitions
6. Compliance framework requirements (if applicable) - Frameworks: {', '.join(domain_config.compliance_frameworks) if domain_config.compliance_frameworks else 'N/A'}

For each question, provide:
- The question itself
- The type ({time_term.lower()}, scope, metric, filter, aggregation, compliance)
- Context explaining why this matters
- A reasonable default assumption

Format as a structured list."""

        response = await track_llm_call(
            agent_name="QuestionGenerationAgent",
            llm=self.llm,
            messages=[
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Analytical Intent:\n{intent}\n\nRelevant Schemas:\n{state['relevant_schemas']}{knowledge_context}")
            ],
            state=state,
            step_name="question_generation"
        )
        
        questions = self._parse_questions(response.content)
        
        state["clarifying_questions"] = questions
        state["messages"].append(AIMessage(
            content=f"Generated {len(questions)} clarifying questions",
            name="QuestionGenerationAgent"
        ))
        state["next_agent"] = "group_planner"  # Route to group planner before feature recommendation
        
        return state
    
    def _parse_questions(self, content: str) -> List[str]:
        """Parse questions from LLM response"""
        lines = content.split("\n")
        questions = [line.strip() for line in lines if "?" in line and len(line.strip()) > 10]
        return questions[:5]  # Limit to 5 questions


# ============================================================================
# GROUP PLANNER AGENT
# ============================================================================

class GroupPlannerAgent:
    """
    LLM Planner agent that creates breakdown groups based on knowledge and goal.
    
    This agent analyzes the user query, knowledge documents, and analytical intent
    to create logical groups for organizing features. These groups will be used to
    generate KPIs, Metrics, and Natural Language SQL questions.
    """
    
    def __init__(self, llm: BaseChatModel, domain_config: DomainConfiguration):
        self.llm = llm
        self.domain_config = domain_config
    
    def _get_domain_config_from_state(self, state: FeatureEngineeringState) -> DomainConfiguration:
        """Get domain config from state or use instance config"""
        domain_config_dict = state.get("domain_config")
        if domain_config_dict:
            return DomainConfiguration(**domain_config_dict)
        return self.domain_config
    
    async def __call__(self, state: FeatureEngineeringState) -> FeatureEngineeringState:
        """Create breakdown groups based on knowledge and goal"""
        
        # Check if we're resuming to a later step
        next_agent = state.get("next_agent", "")
        if next_agent and next_agent not in ["group_planner", "feature_recommendation", "end", ""]:
            logger.info(f"Skipping GroupPlannerAgent - resuming to {next_agent}")
            return state
        
        # Check if groups already exist
        if state.get("planned_groups"):
            logger.info("Planned groups already exist, skipping")
            state["next_agent"] = "feature_recommendation"
            return state
        
        domain_config = self._get_domain_config_from_state(state)
        user_query = state.get("user_query", "")
        analytical_intent = state.get("analytical_intent", {})
        knowledge_documents = state.get("knowledge_documents", [])
        identified_controls = state.get("identified_controls", [])
        relevant_schemas = state.get("relevant_schemas", [])
        
        # Format knowledge documents
        knowledge_context = self._format_knowledge_for_planner(knowledge_documents)
        
        # Format controls if available
        controls_context = ""
        if identified_controls:
            controls_context = "\n\nIDENTIFIED CONTROLS:\n"
            for control in identified_controls[:10]:  # Limit to top 10
                control_id = control.get("control_id", "")
                control_name = control.get("control_name", "")
                category = control.get("category", "")
                controls_context += f"- {control_id}: {control_name} ({category})\n"
        
        system_prompt = f"""You are an expert compliance analyst specializing in {domain_config.domain_name} domain.

Your task is to analyze the user's goal and knowledge documents to create logical breakdown groups.
These groups will be used to organize features, KPIs, Metrics, and Natural Language SQL questions.

Based on the user query, analytical intent, knowledge documents, and identified controls (if any),
create 3-8 logical groups that:
1. Represent distinct analytical dimensions or use cases
2. Are based on compliance frameworks, control categories, or business domains
3. Can be used to organize related features together
4. Make sense from a monitoring and reporting perspective

For each group, provide:
- group_name: A descriptive name (e.g., "Training Completion Metrics", "Certification Management", "Vulnerability Risk Assessment")
- description: What this group represents and why it's important
- related_controls: List of control IDs or categories related to this group (if applicable)
- key_metrics: Types of metrics/KPIs that should be in this group
- schemas: Relevant schemas for this group

Return your analysis as JSON with this structure:
{{
    "groups": [
        {{
            "group_name": "Group Name",
            "description": "Description of what this group represents",
            "related_controls": ["control_id1", "control_id2"],
            "key_metrics": ["metric_type1", "metric_type2"],
            "schemas": ["schema1", "schema2"]
        }}
    ]
}}"""

        prompt = f"""
USER QUERY:
{user_query}

ANALYTICAL INTENT:
{json.dumps(analytical_intent, indent=2)}

RELEVANT SCHEMAS:
{', '.join(relevant_schemas) if relevant_schemas else 'None identified yet'}

{knowledge_context}

{controls_context}

Create logical breakdown groups that will help organize features, KPIs, metrics, and SQL questions.
Focus on creating groups that make sense for monitoring and reporting purposes.
"""

        try:
            response = await track_llm_call(
                agent_name="GroupPlannerAgent",
                llm=self.llm,
                messages=[
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=prompt)
                ],
                state=state,
                step_name="group_planner"
            )
            
            # Parse JSON response
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Extract JSON from response
            planned_groups = None
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                try:
                    planned_groups = json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    # Try to fix common JSON issues
                    json_str = json_match.group(0)
                    json_str = re.sub(r'//.*?$', '', json_str, flags=re.MULTILINE)
                    json_str = re.sub(r',\s*}', '}', json_str)
                    json_str = re.sub(r',\s*]', ']', json_str)
                    try:
                        planned_groups = json.loads(json_str)
                    except json.JSONDecodeError:
                        logger.warning("Could not parse JSON from GroupPlannerAgent response")
            
            # Fallback: Create groups from feature_group tags if available
            if not planned_groups or not planned_groups.get("groups"):
                logger.warning("Creating fallback groups from controls and schemas")
                planned_groups = self._create_fallback_groups(identified_controls, relevant_schemas, analytical_intent)
            
            state["planned_groups"] = planned_groups
            state["messages"].append(AIMessage(
                content=f"Created {len(planned_groups.get('groups', []))} breakdown groups for feature organization",
                name="GroupPlannerAgent"
            ))
            
        except Exception as e:
            logger.error(f"Error in GroupPlannerAgent: {e}")
            # Create fallback groups
            planned_groups = self._create_fallback_groups(identified_controls, relevant_schemas, analytical_intent)
            state["planned_groups"] = planned_groups
        
        state["next_agent"] = "feature_recommendation"
        return state
    
    def _format_knowledge_for_planner(self, knowledge_documents: List[Dict[str, Any]]) -> str:
        """Format knowledge documents for the planner prompt"""
        if not knowledge_documents:
            return ""
        
        formatted = "\n\nRELEVANT KNOWLEDGE:\n"
        for i, doc in enumerate(knowledge_documents[:5], 1):  # Limit to top 5
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})
            framework = metadata.get("framework", "")
            category = metadata.get("category", "")
            
            formatted += f"\n--- Knowledge {i} ---\n"
            if framework:
                formatted += f"Framework: {framework}\n"
            if category:
                formatted += f"Category: {category}\n"
            # Include first 200 chars of content
            content_preview = content[:200] + "..." if len(content) > 200 else content
            formatted += f"Content: {content_preview}\n"
        
        return formatted
    
    def _create_fallback_groups(self, identified_controls: List[Dict[str, Any]], 
                                relevant_schemas: List[str],
                                analytical_intent: Dict[str, Any]) -> Dict[str, Any]:
        """Create fallback groups when LLM parsing fails"""
        groups = []
        
        # Group by control categories if available
        if identified_controls:
            category_map = {}
            for control in identified_controls:
                category = control.get("category", "General")
                if category not in category_map:
                    category_map[category] = {
                        "group_name": f"{category} Metrics",
                        "controls": [],
                        "schemas": []
                    }
                category_map[category]["controls"].append(control.get("control_id", ""))
            
            for category, group_data in category_map.items():
                groups.append({
                    "group_name": group_data["group_name"],
                    "description": f"Metrics related to {category} controls",
                    "related_controls": group_data["controls"],
                    "key_metrics": ["count", "kpi", "metric"],
                    "schemas": relevant_schemas[:3] if relevant_schemas else []
                })
        
        # If no groups created, create a general group
        if not groups:
            primary_goal = analytical_intent.get("primary_goal", "General Analytics")
            groups.append({
                "group_name": "General Metrics",
                "description": f"General metrics for {primary_goal}",
                "related_controls": [],
                "key_metrics": ["count", "kpi", "metric"],
                "schemas": relevant_schemas[:3] if relevant_schemas else []
            })
        
        return {"groups": groups}


# ============================================================================
# EXTERNAL AGENTS FOR GROUP-BASED GENERATION (DUMMY IMPLEMENTATIONS)
# ============================================================================

class GroupKPIGenerationAgent:
    """External agent (dummy) for generating KPIs per group"""
    
    def __init__(self, llm: BaseChatModel, domain_config: DomainConfiguration):
        self.llm = llm
        self.domain_config = domain_config
    
    async def __call__(self, state: FeatureEngineeringState) -> FeatureEngineeringState:
        """Generate KPIs for each planned group (dummy implementation)"""
        planned_groups = state.get("planned_groups", {})
        groups = planned_groups.get("groups", [])
        
        # Dummy implementation - will be fixed later
        group_kpis = {}
        for group in groups:
            group_name = group.get("group_name", "Unknown")
            group_kpis[group_name] = {
                "kpis": [],
                "status": "pending",
                "note": "Dummy implementation - to be fixed later"
            }
        
        state["group_kpis"] = group_kpis
        state["messages"].append(AIMessage(
            content=f"Generated KPIs for {len(groups)} groups (dummy implementation)",
            name="GroupKPIGenerationAgent"
        ))
        return state


class GroupMetricGenerationAgent:
    """External agent (dummy) for generating Metrics per group"""
    
    def __init__(self, llm: BaseChatModel, domain_config: DomainConfiguration):
        self.llm = llm
        self.domain_config = domain_config
    
    async def __call__(self, state: FeatureEngineeringState) -> FeatureEngineeringState:
        """Generate Metrics for each planned group (dummy implementation)"""
        planned_groups = state.get("planned_groups", {})
        groups = planned_groups.get("groups", [])
        
        # Dummy implementation - will be fixed later
        group_metrics = {}
        for group in groups:
            group_name = group.get("group_name", "Unknown")
            group_metrics[group_name] = {
                "metrics": [],
                "status": "pending",
                "note": "Dummy implementation - to be fixed later"
            }
        
        state["group_metrics"] = group_metrics
        state["messages"].append(AIMessage(
            content=f"Generated Metrics for {len(groups)} groups (dummy implementation)",
            name="GroupMetricGenerationAgent"
        ))
        return state


class GroupSQLQuestionGenerationAgent:
    """External agent (dummy) for generating Natural Language SQL questions per group"""
    
    def __init__(self, llm: BaseChatModel, domain_config: DomainConfiguration):
        self.llm = llm
        self.domain_config = domain_config
    
    async def __call__(self, state: FeatureEngineeringState) -> FeatureEngineeringState:
        """Generate Natural Language SQL questions for each planned group (dummy implementation)"""
        planned_groups = state.get("planned_groups", {})
        groups = planned_groups.get("groups", [])
        
        # Dummy implementation - will be fixed later
        group_sql_questions = {}
        for group in groups:
            group_name = group.get("group_name", "Unknown")
            group_sql_questions[group_name] = {
                "sql_questions": [],
                "status": "pending",
                "note": "Dummy implementation - to be fixed later"
            }
        
        state["group_sql_questions"] = group_sql_questions
        state["messages"].append(AIMessage(
            content=f"Generated SQL questions for {len(groups)} groups (dummy implementation)",
            name="GroupSQLQuestionGenerationAgent"
        ))
        return state


# ============================================================================
# RISK QUANTIFICATION PLANNER AGENT
# ============================================================================

class RiskQuantificationPlannerAgent:
    """
    LLM Planner agent that creates breakdown groups for risk quantification goals.
    
    Similar to GroupPlannerAgent, but specifically for risk quantification.
    The user decides the risk quantification goal, and this agent breaks it down
    into groups for risk, impact, and likelihood features.
    """
    
    def __init__(self, llm: BaseChatModel, domain_config: DomainConfiguration):
        self.llm = llm
        self.domain_config = domain_config
    
    def _get_domain_config_from_state(self, state: FeatureEngineeringState) -> DomainConfiguration:
        """Get domain config from state or use instance config"""
        domain_config_dict = state.get("domain_config")
        if domain_config_dict:
            return DomainConfiguration(**domain_config_dict)
        return self.domain_config
    
    async def __call__(self, state: FeatureEngineeringState) -> FeatureEngineeringState:
        """Create breakdown groups for risk quantification"""
        
        # Check if risk quantification is requested
        risk_goal = state.get("risk_quantification_goal")
        if not risk_goal:
            logger.info("No risk quantification goal provided, skipping RiskQuantificationPlannerAgent")
            state["next_agent"] = state.get("next_agent", "end")
            return state
        
        # Check if risk groups already exist
        if state.get("risk_quantification_groups"):
            logger.info("Risk quantification groups already exist, skipping")
            return state
        
        domain_config = self._get_domain_config_from_state(state)
        user_query = state.get("user_query", "")
        analytical_intent = state.get("analytical_intent", {})
        knowledge_documents = state.get("knowledge_documents", [])
        use_case_groups = state.get("use_case_groups", [])
        
        # Format knowledge documents
        knowledge_context = self._format_knowledge_for_planner(knowledge_documents)
        
        # Format use case groups if available
        use_case_context = ""
        if use_case_groups:
            use_case_context = "\n\nUSE CASE GROUPS:\n"
            for group in use_case_groups[:5]:
                group_name = group.get("use_case_name", "Unknown")
                control_ids = group.get("control_ids", [])
                use_case_context += f"- {group_name}: {', '.join(control_ids[:3])}\n"
        
        system_prompt = f"""You are an expert risk analyst specializing in {domain_config.domain_name} domain.

Your task is to analyze the risk quantification goal and break it down into logical groups
for risk, impact, and likelihood features.

Based on the risk quantification goal, user query, analytical intent, knowledge documents,
and existing use case groups (if any), create 2-5 logical groups that:
1. Represent distinct risk dimensions or scenarios
2. Can be used to organize risk, impact, and likelihood features
3. Make sense from a risk assessment and monitoring perspective

For each group, provide:
- group_name: A descriptive name (e.g., "Critical Vulnerability Risk", "Training Compliance Risk")
- description: What this group represents and why it's important for risk quantification
- risk_dimensions: Types of risk factors to consider
- impact_factors: Types of impact factors to consider
- likelihood_factors: Types of likelihood factors to consider
- related_use_cases: Related use case groups (if applicable)

Return your analysis as JSON with this structure:
{{
    "groups": [
        {{
            "group_name": "Group Name",
            "description": "Description of what this group represents",
            "risk_dimensions": ["dimension1", "dimension2"],
            "impact_factors": ["factor1", "factor2"],
            "likelihood_factors": ["factor1", "factor2"],
            "related_use_cases": ["use_case1", "use_case2"]
        }}
    ]
}}"""

        prompt = f"""
RISK QUANTIFICATION GOAL:
{risk_goal}

USER QUERY:
{user_query}

ANALYTICAL INTENT:
{json.dumps(analytical_intent, indent=2)}

{knowledge_context}

{use_case_context}

Create logical breakdown groups for risk quantification that will help organize
risk, impact, and likelihood features.
"""

        try:
            response = await track_llm_call(
                agent_name="RiskQuantificationPlannerAgent",
                llm=self.llm,
                messages=[
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=prompt)
                ],
                state=state,
                step_name="risk_quantification_planner"
            )
            
            # Parse JSON response
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Extract JSON from response
            risk_groups = None
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                try:
                    risk_groups = json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    # Try to fix common JSON issues
                    json_str = json_match.group(0)
                    json_str = re.sub(r'//.*?$', '', json_str, flags=re.MULTILINE)
                    json_str = re.sub(r',\s*}', '}', json_str)
                    json_str = re.sub(r',\s*]', ']', json_str)
                    try:
                        risk_groups = json.loads(json_str)
                    except json.JSONDecodeError:
                        logger.warning("Could not parse JSON from RiskQuantificationPlannerAgent response")
            
            # Fallback: Create groups from use case groups
            if not risk_groups or not risk_groups.get("groups"):
                logger.warning("Creating fallback risk groups from use case groups")
                risk_groups = self._create_fallback_risk_groups(use_case_groups, risk_goal)
            
            state["risk_quantification_groups"] = risk_groups
            state["messages"].append(AIMessage(
                content=f"Created {len(risk_groups.get('groups', []))} risk quantification groups",
                name="RiskQuantificationPlannerAgent"
            ))
            
        except Exception as e:
            logger.error(f"Error in RiskQuantificationPlannerAgent: {e}")
            # Create fallback groups
            risk_groups = self._create_fallback_risk_groups(use_case_groups, risk_goal)
            state["risk_quantification_groups"] = risk_groups
        
        return state
    
    def _format_knowledge_for_planner(self, knowledge_documents: List[Dict[str, Any]]) -> str:
        """Format knowledge documents for the planner prompt"""
        if not knowledge_documents:
            return ""
        
        formatted = "\n\nRELEVANT KNOWLEDGE:\n"
        for i, doc in enumerate(knowledge_documents[:5], 1):
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})
            framework = metadata.get("framework", "")
            category = metadata.get("category", "")
            
            formatted += f"\n--- Knowledge {i} ---\n"
            if framework:
                formatted += f"Framework: {framework}\n"
            if category:
                formatted += f"Category: {category}\n"
            content_preview = content[:200] + "..." if len(content) > 200 else content
            formatted += f"Content: {content_preview}\n"
        
        return formatted
    
    def _create_fallback_risk_groups(self, use_case_groups: List[Dict[str, Any]], 
                                     risk_goal: str) -> Dict[str, Any]:
        """Create fallback risk groups when LLM parsing fails"""
        groups = []
        
        # Use use case groups if available
        if use_case_groups:
            for use_case_group in use_case_groups:
                group_name = use_case_group.get("use_case_name", "Unknown")
                groups.append({
                    "group_name": f"{group_name} Risk",
                    "description": f"Risk quantification for {group_name}",
                    "risk_dimensions": ["severity", "exposure", "compliance"],
                    "impact_factors": ["business_impact", "compliance_impact"],
                    "likelihood_factors": ["exploitability", "exposure"],
                    "related_use_cases": [group_name]
                })
        
        # If no groups created, create a general group
        if not groups:
            groups.append({
                "group_name": "General Risk",
                "description": f"Risk quantification for {risk_goal}",
                "risk_dimensions": ["severity", "exposure"],
                "impact_factors": ["business_impact"],
                "likelihood_factors": ["exploitability"],
                "related_use_cases": []
            })
        
        return {"groups": groups}


# ============================================================================
# CONTROL IDENTIFICATION AGENT
# ============================================================================

class ControlIdentificationAgent:
    """
    Deep Research Agent: Identifies compliance controls and fetches relevant knowledge for each control.
    For each identified control, retrieves knowledge documents to identify key measures that need to be
    calculated for risk estimation, monitoring, and reporting.
    """
    
    def __init__(self, llm: BaseChatModel, domain_config: DomainConfiguration, retrieval_helper: Optional[RetrievalHelper] = None):
        self.llm = llm
        self.domain_config = domain_config
        self.retrieval_helper = retrieval_helper
    
    def _get_domain_config_from_state(self, state: FeatureEngineeringState) -> DomainConfiguration:
        """Get domain config from state or use instance config"""
        domain_config_dict = state.get("domain_config")
        if domain_config_dict:
            return DomainConfiguration(**domain_config_dict)
        return self.domain_config
    
    async def __call__(self, state: FeatureEngineeringState) -> FeatureEngineeringState:
        """
        Deep Research: Identify compliance controls and fetch knowledge for each control.
        For each control, retrieve relevant knowledge documents to identify key measures.
        
        Process:
        1. Identify relevant compliance controls based on analytical intent and knowledge
        2. For each control, fetch knowledge documents using retrieval_helper
        3. Identify key measures/metrics that need to be calculated for each control
        4. Prepare control-specific knowledge for feature generation
        """
        
        # Check if we're resuming to a later step (follow-up scenario)
        # Only skip if next_agent is set to something that comes AFTER this agent
        next_agent = state.get("next_agent", "")
        if next_agent and next_agent not in ["control_identification", "schema_analysis", "knowledge_retrieval", "end", ""]:
            # We're resuming to a later step, skip this node
            logger.info(f"Skipping ControlIdentificationAgent - resuming to {next_agent}")
            return state
        
        domain_config = self._get_domain_config_from_state(state)
        analytical_intent = state.get("analytical_intent", {})
        schema_registry = state.get("schema_registry", {})
        relevant_schemas = state.get("relevant_schemas", [])
        compliance_framework = analytical_intent.get("compliance_framework", "").upper()
        user_query = state.get("user_query", "")
        project_id = state.get("project_id")
        existing_knowledge = state.get("knowledge_documents", [])
        
        # Format schema information
        schema_info = self._format_schema_info(schema_registry, relevant_schemas)
        
        # Build compliance framework context
        frameworks_list = ', '.join(domain_config.compliance_frameworks) if domain_config.compliance_frameworks else 'SOC2, PCI-DSS, HIPAA, GDPR'
        
        system_prompt = f"""You are a deep research compliance expert who identifies relevant compliance controls for risk estimation, monitoring, and reporting.

Your task is to:
1. Identify the most relevant compliance controls based on the analytical intent and available data
2. For each control, identify what key measures/metrics need to be calculated
3. Consider the available data model to determine which controls can be monitored

COMPLIANCE FRAMEWORKS: {frameworks_list}

For each identified control, specify:
1. Control ID (e.g., CC6.1, CC7.2, PCI-DSS 3.4, GDPR Article 32)
2. Control name
3. Control description
4. Key measures/metrics needed for this control (what needs to be calculated)
5. How the available data can support monitoring this control
6. Confidence level (high/medium/low) that this control can be answered with available data

Focus on controls that:
- Are directly relevant to the user's goal
- Can be measured or monitored using available data
- Support risk estimation, monitoring, and reporting

AVAILABLE DATA MODEL:
{schema_info}

ANALYTICAL INTENT:
{analytical_intent}

Provide a structured list of identified controls with key measures for each."""

        response = await track_llm_call(
            agent_name="ControlIdentificationAgent",
            llm=self.llm,
            messages=[
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Identify compliance controls and key measures for: {user_query}")
            ],
            state=state,
            step_name="control_identification"
        )
        
        # Parse identified controls from response
        identified_controls = self._parse_controls(response.content, schema_registry)
        
        # For each identified control, fetch specific knowledge documents
        control_knowledge_map = {}
        if self.retrieval_helper and identified_controls:
            for control in identified_controls:
                control_id = control.get("control_id", "")
                control_name = control.get("control_name", "")
                framework = control.get("framework", compliance_framework)
                
                # Build query for this specific control
                control_query = f"{control_id} {control_name} {framework} compliance monitoring measures"
                
                try:
                    # Fetch knowledge documents specific to this control
                    knowledge_result = await self.retrieval_helper.get_knowledge_documents(
                        query=control_query,
                        project_id=project_id,
                        top_k=5,
                        framework=framework if framework else None,
                        category=None
                    )
                    
                    control_knowledge = knowledge_result.get("documents", [])
                    control_knowledge_map[control_id] = control_knowledge
                    
                    # Add key measures from knowledge to control
                    if control_knowledge:
                        # Extract key measures from knowledge documents
                        measures = self._extract_key_measures_from_knowledge(control_knowledge, control)
                        control["key_measures"] = measures
                        control["knowledge_documents"] = control_knowledge
                    
                    logger.info(f"Fetched {len(control_knowledge)} knowledge documents for control {control_id}")
                    
                except Exception as e:
                    logger.warning(f"Error fetching knowledge for control {control_id}: {e}")
                    control["key_measures"] = []
                    control["knowledge_documents"] = []
        
        # Combine all control-specific knowledge with existing knowledge
        all_knowledge = existing_knowledge.copy()
        for control_id, knowledge_docs in control_knowledge_map.items():
            all_knowledge.extend(knowledge_docs)
        
        state["identified_controls"] = identified_controls
        state["knowledge_documents"] = all_knowledge
        state["control_universe"] = {
            "framework": compliance_framework or "MULTI",
            "controls": identified_controls,
            "total_controls": len(identified_controls),
            "control_knowledge_map": {cid: len(docs) for cid, docs in control_knowledge_map.items()}
        }
        
        state["messages"].append(AIMessage(
            content=f"Deep research: Identified {len(identified_controls)} compliance controls with knowledge documents fetched for each",
            name="ControlIdentificationAgent"
        ))
        
        # Continue to schema analysis (to understand available data)
        state["next_agent"] = "schema_analysis"
        
        return state
    
    def _extract_key_measures_from_knowledge(self, knowledge_documents: List[Dict[str, Any]], control: Dict[str, Any]) -> List[str]:
        """Extract key measures/metrics from knowledge documents for a specific control"""
        measures = []
        
        for doc in knowledge_documents:
            content = doc.get("content", "").lower()
            metadata = doc.get("metadata", {})
            
            # Look for measure-related keywords
            measure_keywords = [
                "measure", "metric", "indicator", "kpi", "score", "rate", "count",
                "percentage", "ratio", "average", "sla", "compliance", "monitoring"
            ]
            
            # Extract sentences that mention measures
            sentences = content.split('.')
            for sentence in sentences:
                if any(keyword in sentence for keyword in measure_keywords):
                    # Clean and extract measure
                    measure = sentence.strip()[:200]  # Limit length
                    if measure and measure not in measures:
                        measures.append(measure)
        
        # If no measures found, use default based on control
        if not measures:
            control_name = control.get("control_name", "").lower()
            if "access" in control_name:
                measures.append("Access control effectiveness metrics")
            elif "monitoring" in control_name:
                measures.append("Monitoring activity metrics")
            elif "risk" in control_name:
                measures.append("Risk assessment metrics")
            else:
                measures.append(f"Compliance metrics for {control.get('control_id', 'control')}")
        
        return measures[:5]  # Limit to 5 key measures
    
    def _format_schema_info(self, schema_registry: Dict[str, Any], relevant_schemas: List[str]) -> str:
        """Format schema information for the prompt"""
        if not schema_registry:
            return ", ".join(relevant_schemas) if relevant_schemas else "No schemas available"
        
        info_parts = []
        for schema_name in relevant_schemas:
            if schema_name in schema_registry:
                schema_info = schema_registry[schema_name]
                desc = schema_info.get("description", "")
                fields = schema_info.get("key_fields", [])
                all_fields = schema_info.get("fields", fields)
                info_parts.append(f"{schema_name}: {desc}\n  Fields: {', '.join(all_fields[:20])}")
            else:
                info_parts.append(schema_name)
        
        return "\n".join(info_parts) if info_parts else ", ".join(relevant_schemas)
    
    def _parse_controls(self, content: str, schema_registry: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse identified controls from LLM response"""
        controls = []
        
        # Try to extract controls using various patterns
        # Pattern 1: Numbered list with control IDs
        control_pattern = re.compile(
            r'(?:^|\n)\s*(?:\d+\.)?\s*(?:Control\s+ID|CC\d+\.\d+)[:\s]+([^\n]+)',
            re.IGNORECASE | re.MULTILINE
        )
        
        # Pattern 2: Look for CC6.1, CC7.2, etc.
        cc_pattern = re.compile(r'CC\d+\.\d+[^\n]*', re.IGNORECASE)
        
        # Extract control IDs
        control_ids = cc_pattern.findall(content)
        
        # Split content by control sections
        sections = re.split(r'(?:^|\n)\s*(?:Control|CC\d+)', content, flags=re.IGNORECASE | re.MULTILINE)
        
        for section in sections:
            if not section.strip():
                continue
            
            control = {}
            
            # Extract control ID
            cc_match = cc_pattern.search(section)
            if cc_match:
                control_id_full = cc_match.group(0).strip()
                # Extract just the ID part (CC6.1)
                id_match = re.search(r'(CC\d+\.\d+)', control_id_full)
                if id_match:
                    control["control_id"] = id_match.group(1)
                else:
                    control["control_id"] = control_id_full.split()[0] if control_id_full.split() else "UNKNOWN"
            else:
                # Try to extract from numbered list
                id_match = re.search(r'(\d+\.)\s*(CC\d+\.\d+)', section)
                if id_match:
                    control["control_id"] = id_match.group(2)
                else:
                    continue  # Skip if no control ID found
            
            # Extract control name
            name_match = re.search(r'(?:Control\s+Name|Name)[:\s]+([^\n]+)', section, re.IGNORECASE)
            if name_match:
                control["control_name"] = name_match.group(1).strip()
            else:
                # Try to extract from first line after control ID
                lines = section.split('\n')
                if len(lines) > 1:
                    control["control_name"] = lines[1].strip()[:100]
                else:
                    control["control_name"] = f"Control {control['control_id']}"
            
            # Extract description
            desc_match = re.search(r'(?:Description|Control\s+Description)[:\s]+([^\n]+(?:\n[^\n]+)*)', section, re.IGNORECASE)
            if desc_match:
                control["description"] = desc_match.group(1).strip()[:500]
            else:
                # Use first few sentences of section
                sentences = section.split('.')[:3]
                control["description"] = '. '.join(sentences).strip()[:500]
            
            # Extract how data can answer this control
            data_match = re.search(r'(?:How\s+Data\s+Can\s+Answer|Data\s+Support|Available\s+Data)[:\s]+([^\n]+(?:\n[^\n]+)*)', section, re.IGNORECASE)
            if data_match:
                control["data_support"] = data_match.group(1).strip()[:500]
            else:
                control["data_support"] = "Data model supports monitoring this control"
            
            # Extract confidence
            conf_match = re.search(r'(?:Confidence|Confidence\s+Level)[:\s]+(high|medium|low)', section, re.IGNORECASE)
            if conf_match:
                control["confidence"] = conf_match.group(1).lower()
            else:
                control["confidence"] = "medium"
            
            # Extract suggested features
            features_match = re.search(r'(?:Suggested\s+Features|Features|Metrics)[:\s]+([^\n]+(?:\n[^\n]+)*)', section, re.IGNORECASE)
            if features_match:
                features_text = features_match.group(1).strip()
                # Extract feature names (bullet points or list items)
                feature_list = re.findall(r'[-•*]\s*([^\n]+)', features_text)
                control["suggested_features"] = [f.strip() for f in feature_list[:5]]
            else:
                control["suggested_features"] = []
            
            # Set framework
            control["framework"] = "SOC2"
            control["category"] = self._get_control_category(control.get("control_id", ""))
            
            controls.append(control)
        
        # If no structured parsing worked, create controls from control IDs found
        if not controls and control_ids:
            for cc_id in control_ids[:10]:  # Limit to 10 controls
                id_match = re.search(r'(CC\d+\.\d+)', cc_id)
                if id_match:
                    controls.append({
                        "control_id": id_match.group(1),
                        "control_name": f"Control {id_match.group(1)}",
                        "description": f"SOC2 control {id_match.group(1)}",
                        "framework": "SOC2",
                        "category": self._get_control_category(id_match.group(1)),
                        "data_support": "Available data can support monitoring this control",
                        "confidence": "medium",
                        "suggested_features": []
                    })
        
        return controls
    
    def _get_control_category(self, control_id: str) -> str:
        """Get control category from control ID"""
        if not control_id:
            return "Unknown"
        
        # Extract the main control number (CC6, CC7, etc.)
        match = re.search(r'CC(\d+)', control_id)
        if match:
            control_num = int(match.group(1))
            categories = {
                1: "Control Environment",
                2: "Communication and Information",
                3: "Risk Assessment",
                4: "Monitoring Activities",
                5: "Control Activities",
                6: "Logical and Physical Access Controls",
                7: "System Operations",
                8: "Change Management",
                9: "Risk Mitigation"
            }
            return categories.get(control_num, "Unknown")
        
        return "Unknown"


class FeatureRecommendationAgent:
    """Agent that recommends specific features to calculate"""
    
    def __init__(
        self, 
        llm: BaseChatModel, 
        domain_config: DomainConfiguration,
        instructions: Optional[str] = None,
        examples: Optional[List[Dict[str, Any]]] = None
    ):
        self.llm = llm
        self.domain_config = domain_config
        self.instructions = instructions or ""  # Placeholder for future instructions
        self.examples = examples or []  # Placeholder for future examples
        # Use feature patterns from domain configuration
        self.feature_patterns = {
            name: {
                "template": pattern.template,
                "logic": pattern.logic,
                "schemas": pattern.schemas
            }
            for name, pattern in domain_config.feature_patterns.items()
        }
    
    def _get_domain_config_from_state(self, state: FeatureEngineeringState) -> DomainConfiguration:
        """Get domain config from state or use instance config"""
        domain_config_dict = state.get("domain_config")
        if domain_config_dict:
            return DomainConfiguration(**domain_config_dict)
        return self.domain_config
        
    async def __call__(self, state: FeatureEngineeringState) -> FeatureEngineeringState:
        """Recommend features based on intent, schemas, instructions, and examples"""
        
        # Check if this is a risk-only follow-up (skip base metrics generation)
        is_risk_only_followup = state.get("risk_only_followup", False)
        if is_risk_only_followup:
            logger.info("Risk-only follow-up detected: skipping base metrics generation, routing to risk feature generation")
            # Ensure use case groups exist from previous run
            if not state.get("use_case_groups"):
                # Try to create use case groups from existing features
                existing_features = state.get("recommended_features", [])
                identified_controls = state.get("identified_controls", [])
                if existing_features:
                    use_case_groups = self._group_features_by_use_case(existing_features, identified_controls or [])
                    state["use_case_groups"] = use_case_groups
            state["next_agent"] = "risk_feature_generation_graph"
            return state
        
        # Get domain config from state or use instance config
        domain_config = self._get_domain_config_from_state(state)
        
        # Get instructions and examples from state if provided, otherwise use instance values
        instructions = state.get("feature_generation_instructions") or self.instructions
        examples = state.get("feature_generation_examples") or self.examples
        
        # Safely get state fields with defaults for resume scenarios
        intent = state.get("analytical_intent", {})
        schemas = state.get("relevant_schemas", [])
        schema_registry = state.get("schema_registry", {})
        knowledge_documents = state.get("knowledge_documents", [])
        identified_controls = state.get("identified_controls", [])
        control_universe = state.get("control_universe", {})
        
        # Ensure we have minimum required fields
        if not intent:
            intent = {"primary_goal": state.get("user_query", "")[:200] or "Feature generation"}
        if not schemas:
            schemas = []
        
        # Format schema information for prompt
        schema_info = self._format_schema_info(schema_registry, schemas)
        
        # Format knowledge documents for prompt
        knowledge_info = self._format_knowledge_documents(knowledge_documents)
        
        # Format identified controls for prompt
        # Handle None case - ensure identified_controls is a list
        if identified_controls is None:
            identified_controls = []
        controls_info = self._format_controls_info(identified_controls, control_universe)
        has_controls = len(identified_controls) > 0
        
        # Use custom prompt if provided, otherwise use default
        if domain_config.feature_recommendation_prompt:
            base_prompt = domain_config.feature_recommendation_prompt
        else:
            domain_desc = domain_config.domain_description or domain_config.domain_name
            base_prompt = f"""You are a feature engineering expert for {domain_desc} analytics."""
        
        # Add instructions and examples to the prompt
        instructions_text = f"\n\nFEATURE GENERATION INSTRUCTIONS:\n{instructions}" if instructions else ""
        
        examples_text = ""
        if examples:
            examples_text = "\n\nEXAMPLE FEATURES:\n"
            for i, example in enumerate(examples, 1):
                example_query = example.get("query", "")
                example_features = example.get("features", [])
                examples_text += f"\nExample {i}:\nQuery: {example_query}\nFeatures: {example_features}\n"
        
        # Build feature generation instructions based on whether controls are identified
        if has_controls:
            control_instruction = """For EACH identified control, generate 1-3 features that:
1. Directly support monitoring or answering that control
2. Use the key measures identified for that control
3. Can be calculated using the available data model"""
        else:
            control_instruction = f"""Since no specific compliance controls have been identified, generate 5-10 general {domain_config.domain_name} compliance features based on:
1. The analytical intent and user query
2. Available domain feature patterns (see FEATURE PATTERN TEMPLATES below)
3. Common compliance metrics for {domain_config.domain_name} domain
4. Available schemas and data model
5. Domain-specific best practices for {domain_config.domain_name}

Focus on generating features that support:
- {domain_config.time_constraint_terms[0].title() if domain_config.time_constraint_terms else 'Time'} compliance and monitoring
- Risk assessment and vulnerability management
- {', '.join(domain_config.entity_types[:3]) if domain_config.entity_types else 'Entity'} monitoring and metrics
- Compliance framework requirements ({', '.join(domain_config.compliance_frameworks[:3]) if domain_config.compliance_frameworks else 'SOC2, PCI-DSS, HIPAA'})"""
        
        system_prompt = f"""{base_prompt}

You are a feature engineering expert generating STANDARD METRICS, KPIs, and COUNTS for daily compliance monitoring and analysis.

GOAL: Generate standard operational metrics, KPIs, and counts that can be calculated daily from raw data. These are foundational metrics that support daily dashboards and operational monitoring.

IMPORTANT: These features are for DAILY ANALYSIS - we expect data to arrive daily. Focus on metrics that can be recalculated each day from the latest data.

MEDALLION ARCHITECTURE CLASSIFICATION:
- SILVER: Transformations from raw data (bronze). Includes: data cleaning, normalization, deduplication, type conversions, basic calculations from raw fields. Example: "Create a calculated column for vulnerability_age based on publish_time and current_date"
- GOLD: Requires aggregations or multi-table joins. Includes: counts, averages, sums, aggregations across tables, grouped metrics. Example: "Count vulnerabilities by severity level grouped by asset"

FEATURE TYPES TO GENERATE:
1. COUNTS: Simple counts of entities, events, or states (e.g., "Count of critical vulnerabilities", "Count of assets by type")
2. METRICS: Aggregated metrics (e.g., "Average remediation time", "Total patch lag days")
3. KPIs: Key performance indicators (e.g., "SLA compliance rate", "Patch deployment rate")
4. RATIOS: Percentage or ratio calculations (e.g., "Percentage of vulnerabilities patched", "Ratio of critical to total vulnerabilities")

NATURAL LANGUAGE QUESTION FORMAT:
Generate clear, executable natural language questions like:
- "Count the number of vulnerabilities where severity is Critical and state is ACTIVE, grouped by asset"
- "Calculate the average number of days between detected_time and remediation_time for vulnerabilities where state is REMEDIATED"
- "Count the number of assets by device_type and platform, filtering for assets where is_cloud_asset is TRUE"

Each question should:
1. Specify what to calculate (count, average, sum, etc.)
2. Specify the entity/level (per asset, per vulnerability, overall, etc.)
3. Include filters (severity, state, time windows, etc.)
4. Reference specific fields from available schemas
5. Be executable by a transformation agent

Given the analytical intent, available schemas, and {'identified compliance controls' if has_controls else 'domain patterns'}, generate STANDARD METRICS, KPIs, and COUNTS.
{instructions_text}
{examples_text}

FEATURE PATTERN TEMPLATES:
{self._format_feature_patterns()}

ANALYTICAL INTENT:
{intent}

AVAILABLE SCHEMAS:
{schema_info}

RELEVANT KNOWLEDGE:
{knowledge_info}

{'IDENTIFIED COMPLIANCE CONTROLS:' if has_controls else 'NOTE: No specific compliance controls have been identified. Generate general compliance features based on domain patterns and analytical intent.'}
{controls_info}

{control_instruction}

For each feature, provide:
1. Feature name (descriptive, following naming conventions - use underscores, no spaces, e.g., critical_vulnerability_count, avg_remediation_time_days)
2. Feature type (count, metric, kpi, ratio, time_series, impact, likelihood, risk)
3. Natural language question (REQUIRED - Clear, executable instruction specifying what to calculate, filters, and grouping. Must be a complete question.)
4. Feature group (Group name for related features that should be calculated together, e.g., 'vulnerability_counts', 'sla_metrics', 'risk_scores', 'remediation_metrics')
5. Required schemas and fields
6. Aggregation method (count, sum, avg, max, min, percentile, ratio, etc.)
7. Filters to apply ({', '.join(domain_config.severity_levels) if domain_config.severity_levels else 'severity/priority levels'}, state, time windows)
8. Business context (why this metric matters for daily monitoring)
9. Compliance reasoning (explain how this metric supports compliance monitoring{' and include the specific control ID if applicable' if has_controls else ''})
10. Transformation layer (MUST be 'silver' or 'gold'):
    - SILVER: Basic transformations from raw data. Simple calculations, cleaning, normalization.
    - GOLD: Aggregations, multi-table joins, grouped calculations.
11. Time series type (if applicable: 'snapshot' for point-in-time, 'cumulative' for running totals, 'rolling_window' for moving averages, 'period_over_period' for comparisons, 'trend' for trends, or None)

IMPORTANT: DO NOT include calculation logic - that will be determined by other agents. Focus on the natural language question, grouping, and metadata.

OUTPUT FORMAT:
Provide features in a numbered list format, grouped by feature_group:
1. **Feature Name**: [feature_name] - **Feature Type**: [count/metric/kpi/ratio] - **Natural Language Question**: [clear, complete question] - **Feature Group**: [group_name] - **Required Schemas**: [schemas] - **Aggregation Method**: [method] - **Filters Applied**: [filters] - **Business Context**: [context] - **Compliance Reasoning**: [reasoning] - **Transformation Layer**: [silver/gold] - **Time Series Type**: [type or None]

Focus on generating:
- Standard operational metrics for daily monitoring
- Counts of entities, events, and states
- KPIs for compliance tracking
- Aggregated metrics (averages, sums, totals)
- Metrics that can be recalculated daily from fresh data
- {domain_config.time_constraint_terms[0].title() if domain_config.time_constraint_terms else 'Time'} compliance metrics
- Domain-specific operational indicators for {domain_config.domain_name}

DO NOT generate risk, impact, or likelihood features here - those will be generated in a separate risk feature engineering step.

{('Follow the provided instructions and use the examples as guidance for feature generation.' if (instructions or examples) else '')}"""

        response = await track_llm_call(
            agent_name="FeatureRecommendationAgent",
            llm=self.llm,
            messages=[
                SystemMessage(content=system_prompt),
                HumanMessage(content="Generate feature recommendations")
            ],
            state=state,
            step_name="feature_recommendation"
        )
        
        recommended_features = self._parse_feature_recommendations(response.content)
        
        # Fallback: If no features were generated, create features from domain patterns
        if not recommended_features:
            logger.warning("No features parsed from LLM response. Generating fallback features from domain patterns.")
            recommended_features = self._create_fallback_features_from_patterns(
                domain_config, 
                intent, 
                schemas,
                schema_registry
            )
            state["messages"].append(AIMessage(
                content=f"Generated {len(recommended_features)} fallback features from domain patterns",
                name="FeatureRecommendationAgent"
            ))
        
        # If there are existing features, append new ones (for follow-up scenarios)
        existing_features = state.get("recommended_features", [])
        if existing_features and instructions:  # If instructions provided, likely a follow-up
            # Append new features to existing ones
            state["recommended_features"] = existing_features + recommended_features
            state["messages"].append(AIMessage(
                content=f"Added {len(recommended_features)} additional features (total: {len(state['recommended_features'])})",
                name="FeatureRecommendationAgent"
            ))
        else:
            # Replace with new features (initial generation)
            state["recommended_features"] = recommended_features
        state["messages"].append(AIMessage(
            content=f"Recommended {len(recommended_features)} standard metrics/KPIs for daily analysis",
            name="FeatureRecommendationAgent"
        ))
        
        # Group features by use case (control groups)
        use_case_groups = self._group_features_by_use_case(recommended_features, identified_controls)
        state["use_case_groups"] = use_case_groups
        
        # Initialize risk configuration if not present
        if "risk_configuration" not in state or state["risk_configuration"] is None:
            state["risk_configuration"] = {}
        
        # Route to risk feature generation graph if configured, otherwise skip
        # Check if this is a follow-up that only adds risk metrics (no new base metrics)
        is_risk_only_followup = state.get("risk_only_followup", False)
        if is_risk_only_followup:
            # Skip base metrics generation, go directly to risk feature generation
            state["next_agent"] = "risk_feature_generation_graph"
        else:
            # After base metrics, check if risk features should be generated
            should_generate_risk = state.get("generate_risk_features", True)
            if should_generate_risk:
                state["next_agent"] = "risk_feature_generation_graph"
            else:
                # Skip risk features, go to feature combination
                state["next_agent"] = "feature_combination"
        
        return state
    
    def _group_features_by_use_case(
        self, 
        features: List[Dict[str, Any]], 
        identified_controls: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Group features by use case using feature_group tags and planned groups"""
        use_case_groups = []
        
        # First, try to use planned_groups from GroupPlannerAgent if available
        # This will be set in state if GroupPlannerAgent has run
        planned_groups = None  # Will be passed from state if available
        
        # Group features by their feature_group tag (primary method)
        feature_group_map = {}
        for feature in features:
            feature_group = feature.get("feature_group", "")
            # Clean feature_group tag (remove "*: " prefix if present)
            if feature_group.startswith("*: "):
                feature_group = feature_group[3:]
            elif feature_group.startswith("*:"):
                feature_group = feature_group[2:].strip()
            
            if not feature_group:
                feature_group = "general_metrics"
            
            if feature_group not in feature_group_map:
                feature_group_map[feature_group] = []
            feature_group_map[feature_group].append(feature)
        
        # Create use case groups from feature_group tags
        for feature_group_name, group_features in feature_group_map.items():
            # Try to find matching control group for this feature_group
            matched_controls = []
            matched_control_ids = []
            
            # Normalize feature_group name for matching
            feature_group_lower = feature_group_name.lower().replace("_", " ").replace("-", " ")
            
            # Try to match with identified controls
            for control in identified_controls:
                control_id = control.get("control_id", "")
                category = control.get("category", "").lower()
                control_name = control.get("control_name", "").lower()
                
                # Check if feature_group name matches control category or name
                if (category and any(word in feature_group_lower for word in category.split()) or
                    any(word in feature_group_lower for word in control_name.split())):
                    matched_controls.append(control)
                    if control_id:
                        matched_control_ids.append(control_id)
            
            # Create a readable use case name from feature_group
            use_case_name = feature_group_name.replace("_", " ").title()
            # Try to improve name based on controls
            if matched_controls:
                category = matched_controls[0].get("category", "")
                if category:
                    use_case_name = f"{category} - {use_case_name}"
            
            use_case_groups.append({
                "use_case_name": use_case_name,
                "control_ids": matched_control_ids,
                "controls": matched_controls,
                "features": group_features,
                "feature_count": len(group_features),
                "feature_group": feature_group_name  # Store original feature_group tag
            })
        
        # Sort groups by feature count (descending)
        use_case_groups.sort(key=lambda x: x["feature_count"], reverse=True)
        
        # If no groups created, create a single general group
        if not use_case_groups:
            use_case_groups.append({
                "use_case_name": "General Metrics",
                "control_ids": [],
                "controls": [],
                "features": features,
                "feature_count": len(features),
                "feature_group": "general_metrics"
            })
        
        logger.info(f"Grouped {len(features)} features into {len(use_case_groups)} use case groups based on feature_group tags")
        return use_case_groups
    
    def _format_knowledge_documents(self, knowledge_documents: List[Dict[str, Any]]) -> str:
        """Format knowledge documents for the prompt"""
        if not knowledge_documents:
            return "No relevant knowledge documents available."
        
        formatted = []
        for i, doc in enumerate(knowledge_documents, 1):
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})
            framework = metadata.get("framework", "")
            category = metadata.get("category", "")
            
            formatted.append(f"\n--- Knowledge Document {i} ---")
            if framework:
                formatted.append(f"Framework: {framework}")
            if category:
                formatted.append(f"Category: {category}")
            formatted.append(f"Content:\n{content}")
        
        return "\n".join(formatted)
    
    def _format_controls_info(self, identified_controls: List[Dict[str, Any]], control_universe: Dict[str, Any]) -> str:
        """Format identified controls for the prompt"""
        if not identified_controls:
            return "No SOC2 controls have been identified yet. Recommend general compliance features."
        
        formatted = []
        formatted.append(f"\n=== IDENTIFIED SOC2 CONTROLS ({len(identified_controls)} controls) ===\n")
        formatted.append("These controls can be answered/monitored using the available data model.\n")
        formatted.append("For each control, recommend 1-2 features that support it.\n")
        
        for i, control in enumerate(identified_controls, 1):
            formatted.append(f"\n--- Control {i}: {control.get('control_id', 'UNKNOWN')} ---")
            formatted.append(f"Control Name: {control.get('control_name', 'N/A')}")
            formatted.append(f"Category: {control.get('category', 'N/A')}")
            formatted.append(f"Description: {control.get('description', 'N/A')[:200]}")
            formatted.append(f"How Data Can Answer: {control.get('data_support', 'N/A')[:200]}")
            formatted.append(f"Confidence: {control.get('confidence', 'medium')}")
            if control.get('suggested_features'):
                formatted.append(f"Suggested Features: {', '.join(control.get('suggested_features', [])[:3])}")
        
        formatted.append("\n=== INSTRUCTIONS ===")
        formatted.append("For each identified control above, recommend 1-2 features that:")
        formatted.append("1. Can be calculated using the available schemas")
        formatted.append("2. Directly support monitoring or answering the control requirement")
        formatted.append("3. Include the specific control ID (e.g., CC6.1) in the SOC2 compliance reasoning")
        formatted.append("4. Explain how the feature supports the control in the SOC2 compliance reasoning field")
        
        return "\n".join(formatted)
    
    def _format_schema_info(self, schema_registry: Dict[str, Any], relevant_schemas: List[str]) -> str:
        """Format schema information for the prompt"""
        if not schema_registry:
            return ", ".join(relevant_schemas) if relevant_schemas else "No schemas available"
        
        info_parts = []
        for schema_name in relevant_schemas:
            if schema_name in schema_registry:
                schema_info = schema_registry[schema_name]
                desc = schema_info.get("description", "")
                fields = schema_info.get("key_fields", [])
                info_parts.append(f"{schema_name}: {desc} (Fields: {', '.join(fields[:10])})")
            else:
                info_parts.append(schema_name)
        
        return "\n".join(info_parts) if info_parts else ", ".join(relevant_schemas)
    
    def _format_feature_patterns(self) -> str:
        """Format feature patterns for prompt"""
        return "\n".join([
            f"- {name}: {pattern['template']}\n  Logic: {pattern['logic']}"
            for name, pattern in self.feature_patterns.items()
        ])
    
    def _create_fallback_features_from_patterns(
        self,
        domain_config: DomainConfiguration,
        intent: Dict[str, Any],
        schemas: List[str],
        schema_registry: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Create fallback features from domain patterns when LLM doesn't generate any"""
        features = []
        
        # Get primary goal from intent
        primary_goal = intent.get("primary_goal", "").lower()
        
        # Generate features based on domain patterns
        for pattern_name, pattern in domain_config.feature_patterns.items():
            # Skip if pattern doesn't match intent (only if we have a primary goal)
            if primary_goal:
                pattern_desc = (pattern.description or "").lower()
                pattern_keywords = pattern_name.split("_") + pattern_desc.split()
                if not any(keyword in primary_goal for keyword in pattern_keywords if keyword):
                    continue
            
            # Create feature from pattern
            try:
                feature_name = pattern.template.format(
                    severity="critical" if domain_config.severity_levels else "",
                    risk_type="effective",
                    sla_days=domain_config.default_context.get("critical_sla_days", 7)
                )
            except (KeyError, ValueError):
                # If format fails, use template as-is and remove placeholders
                feature_name = pattern.template
            
            # Remove empty placeholders
            feature_name = re.sub(r'\{[^}]+\}', '', feature_name).strip('_')
            
            feature = {
                "feature_name": feature_name,
                "feature_type": "metric" if "avg" in feature_name else "count",
                "natural_language_question": f"Calculate {feature_name.replace('_', ' ')}",
                "required_schemas": pattern.schemas if pattern.schemas else schemas[:2],
                "required_fields": [],
                "aggregation_method": "avg" if "avg" in feature_name else "count",
                "filters_applied": [],
                "business_context": pattern.description or f"Feature for {domain_config.domain_name} compliance monitoring",
                "compliance_reasoning": f"Supports {domain_config.domain_name} compliance monitoring and risk assessment",
                "feature_group": "general_metrics",
                "transformation_layer": "gold",
                "time_series_type": None
            }
            features.append(feature)
        
        # If still no features, create basic ones from domain config
        if not features:
            # Create basic features based on domain
            if domain_config.domain_name == "cybersecurity":
                features = [
                    {
                        "feature_name": "critical_vulnerability_sla_breached_count",
                        "feature_type": "count",
                        "natural_language_question": "Count vulnerabilities where severity is Critical and (current_date - detected_time) exceeds the SLA threshold of 7 days",
                        "required_schemas": ["vulnerability_instances", "cve"],
                        "required_fields": ["severity", "detected_time"],
                        "aggregation_method": "count",
                        "filters_applied": ["severity = Critical"],
                        "business_context": "Track critical vulnerabilities that have breached SLA requirements",
                        "compliance_reasoning": "Supports SOC2 CC7.1 and CC7.4 controls for vulnerability monitoring and remediation",
                        "feature_group": "sla_metrics",
                        "transformation_layer": "gold",
                        "time_series_type": "snapshot"
                    },
                    {
                        "feature_name": "high_exploitability_vulnerability_count",
                        "feature_type": "count",
                        "natural_language_question": "Count vulnerabilities where epssScore is greater than 0.5 or cisaExploited is true",
                        "required_schemas": ["vulnerability_instances", "cve"],
                        "required_fields": ["epssScore", "cisaExploited"],
                        "feature_group": "vulnerability_metrics",
                        "aggregation_method": "count",
                        "filters_applied": [],
                        "business_context": "Identify vulnerabilities with high exploitability risk",
                        "compliance_reasoning": "Supports SOC2 CC7.1 control for identifying exploitable vulnerabilities",
                        "transformation_layer": "gold",
                        "time_series_type": "snapshot"
                    },
                    {
                        "feature_name": "avg_patch_lag_days",
                        "feature_type": "metric",
                        "natural_language_question": "Calculate the average number of days between when a patch is available and when it is installed",
                        "required_schemas": ["software_instances"],
                        "required_fields": ["latest_available_patch_release_time", "latest_installed_patch_release_time"],
                        "aggregation_method": "avg",
                        "filters_applied": [],
                        "business_context": "Measure patch deployment efficiency and compliance",
                        "compliance_reasoning": "Supports PCI-DSS REQ-6 control for timely patch deployment",
                        "feature_group": "remediation_metrics",
                        "transformation_layer": "gold",
                        "time_series_type": "snapshot"
                    },
                    {
                        "feature_name": "avg_remediation_time_by_severity",
                        "feature_type": "metric",
                        "natural_language_question": "Calculate the average time from detection to remediation for vulnerabilities, grouped by severity level",
                        "required_schemas": ["vulnerability_instances"],
                        "required_fields": ["remediation_time", "detected_time", "severity", "state"],
                        "aggregation_method": "avg",
                        "filters_applied": ["state = remediated"],
                        "business_context": "Track remediation efficiency by severity to improve SLA compliance",
                        "compliance_reasoning": "Supports SOC2 CC7.4 control for incident response and remediation tracking",
                        "feature_group": "remediation_metrics",
                        "transformation_layer": "gold",
                        "time_series_type": "snapshot"
                    },
                    {
                        "feature_name": "avg_risk_score_by_asset",
                        "feature_type": "metric",
                        "natural_language_question": "Calculate the average risk score for each asset based on associated vulnerabilities and their severity",
                        "required_schemas": ["features", "asset"],
                        "required_fields": ["effective_risk", "asset_id"],
                        "aggregation_method": "avg",
                        "filters_applied": [],
                        "business_context": "Assess overall risk posture at the asset level",
                        "compliance_reasoning": "Supports SOC2 CC6.1 and CC7.1 controls for risk assessment and monitoring",
                        "feature_group": "risk_scores",
                        "transformation_layer": "gold",
                        "time_series_type": "snapshot"
                    }
                ]
        
        return features[:10]  # Limit to 10 features
    
    def _parse_feature_recommendations(self, content: str) -> List[Dict[str, Any]]:
        """Parse feature recommendations from LLM response"""
        features = []
        
        # Split content by numbered items (1., 2., etc.)
        parts = re.split(r'(?=\d+\.)', content)
        
        for part in parts:
            if not part.strip() or not re.match(r'^\d+\.', part.strip()):
                continue
            
            feature = {}
            part_clean = part.strip()
            
            # Pattern to extract fields in format: "**Field Name**: value -" or "Field Name: value -"
            # This handles the format: "1. **Feature Name**: critical_sla_breached_count - **Feature Type**: Count - ..."
            
            # Helper function to extract field value between dashes
            def extract_field(pattern, text):
                """Extract field value that may be between dashes or at end"""
                # Match pattern and capture until next " - **" or end of string
                match = re.search(pattern + r'[:\*]?\s*(?:\*\*)?\s*(.+?)(?:\s*-\s*\*\*|$)', text, re.IGNORECASE | re.DOTALL)
                if match:
                    value = match.group(1).strip()
                    # Remove trailing markdown formatting
                    value = re.sub(r'\*\*$', '', value).strip()
                    return value
                return None
            
            # Extract feature name (first field after the number)
            # Try multiple patterns to handle different formats
            name_match = re.search(r'^\d+\.\s*(?:\*\*)?(?:Feature\s+Name|Feature Name|Name)[:\*]?\s*(?:\*\*)?\s*([^-]+?)(?:\s*-\s*\*\*|$)', part_clean, re.IGNORECASE)
            if name_match:
                feature["feature_name"] = name_match.group(1).strip()
            else:
                # Try pattern: "1. *: feature_name" or "1. feature_name"
                name_match = re.search(r'^\d+\.\s*(?:\*\*)?\s*\*?:\s*([^\s-]+)', part_clean, re.IGNORECASE)
                if name_match:
                    feature["feature_name"] = name_match.group(1).strip()
                else:
                    # Try to extract first meaningful text after number as feature name
                    name_match = re.search(r'^\d+\.\s*(?:[^\w]*)?([a-z_][a-z0-9_]*(?:_[a-z0-9_]+)*)', part_clean, re.IGNORECASE)
                    if name_match:
                        feature["feature_name"] = name_match.group(1).strip()
            
            # Clean up feature name - remove any remaining "*:" prefix or malformed prefixes
            if "feature_name" in feature:
                # Remove "*:", "* :", " *:", or any combination of asterisks and colons at the start
                feature["feature_name"] = re.sub(r'^\s*\*+\s*:?\s*', '', feature["feature_name"]).strip()
                # Also remove any trailing asterisks or colons
                feature["feature_name"] = re.sub(r'[:*]+\s*$', '', feature["feature_name"]).strip()
            
            # Extract feature type
            type_val = extract_field(r'(?:\*\*)?(?:Feature\s+Type|Feature Type|Type)', part_clean)
            if type_val:
                feature["feature_type"] = type_val
            
            # Extract feature group
            group_val = extract_field(r'(?:\*\*)?(?:Feature\s+Group|Feature Group|Group)', part_clean)
            if group_val:
                feature["feature_group"] = group_val.strip()
            
            # Extract natural language question
            question_val = extract_field(r'(?:\*\*)?(?:Natural\s+Language\s+Question|Natural Language Question|Question|NLQ)', part_clean)
            if question_val:
                # Clean up any "*:" prefix in the question
                question_val = re.sub(r'^\s*\*+\s*:?\s*', '', question_val).strip()
                feature["natural_language_question"] = question_val
            else:
                # If not found, generate from feature name and calculation logic
                feature_name = feature.get("feature_name", "")
                calc_logic = feature.get("calculation_logic", "")
                if feature_name:
                    # Ensure feature name is clean before using it
                    clean_name = re.sub(r'^\s*\*+\s*:?\s*', '', feature_name).strip()
                    clean_name = re.sub(r'[:*]+\s*$', '', clean_name).strip()
                    # Generate a simple question from the feature name
                    feature["natural_language_question"] = f"What is the {clean_name.lower().replace('_', ' ')}?"
            
            # Extract required schemas
            schema_val = extract_field(r'(?:\*\*)?(?:Required\s+Schemas|Required Schemas|Schemas)', part_clean)
            if schema_val:
                # Extract schema names from parentheses
                schema_names = re.findall(r'(\w+)\s*\(', schema_val)
                feature["required_schemas"] = schema_names if schema_names else [s.strip() for s in schema_val.split(',')]
            
            # Extract aggregation method
            agg_val = extract_field(r'(?:\*\*)?(?:Aggregation\s+Method|Aggregation Method|Method)', part_clean)
            if agg_val:
                feature["aggregation_method"] = agg_val
            
            # Extract filters
            filter_val = extract_field(r'(?:\*\*)?(?:Filters?)', part_clean)
            if filter_val:
                feature["filters_applied"] = [f.strip() for f in filter_val.split(',')]
            
            # Extract business context
            context_val = extract_field(r'(?:\*\*)?(?:Business\s+Context|Business Context|Context)', part_clean)
            if context_val:
                feature["business_context"] = context_val
            
            # Extract compliance reasoning (SOC2 or general)
            compliance_val = extract_field(r'(?:\*\*)?(?:Compliance\s+Reasoning|Compliance Reasoning|SOC2\s+Compliance\s+Reasoning|SOC2 Compliance Reasoning|SOC2)', part_clean)
            if compliance_val:
                feature["compliance_reasoning"] = compliance_val
            elif "business_context" in feature:
                # Fallback to business context if compliance reasoning not found
                feature["compliance_reasoning"] = feature.get("business_context", "")
            
            # Extract transformation layer
            layer_val = extract_field(r'(?:\*\*)?(?:Transformation\s+Layer|Transformation Layer|Layer)', part_clean)
            if layer_val:
                # Normalize to lowercase and validate
                layer_lower = layer_val.lower().strip()
                if layer_lower in ['bronze', 'silver', 'gold']:
                    feature["transformation_layer"] = layer_lower
                else:
                    # Try to extract from text
                    if 'bronze' in layer_lower or 'raw' in layer_lower:
                        feature["transformation_layer"] = "bronze"
                    elif 'silver' in layer_lower or 'clean' in layer_lower or 'normalized' in layer_lower:
                        feature["transformation_layer"] = "silver"
                    elif 'gold' in layer_lower or 'aggregat' in layer_lower or 'mart' in layer_lower:
                        feature["transformation_layer"] = "gold"
                    else:
                        feature["transformation_layer"] = "gold"  # Default to gold for analytics features
            
            # Extract time series type
            ts_val = extract_field(r'(?:\*\*)?(?:Time\s+Series\s+Type|Time Series Type|Time Series|TS Type)', part_clean)
            if ts_val:
                ts_lower = ts_val.lower().strip()
                # Map to standard values
                if 'snapshot' in ts_lower or 'point-in-time' in ts_lower or 'current' in ts_lower:
                    feature["time_series_type"] = "snapshot"
                elif 'cumulative' in ts_lower or 'running' in ts_lower or 'total' in ts_lower:
                    feature["time_series_type"] = "cumulative"
                elif 'rolling' in ts_lower or 'moving' in ts_lower or 'window' in ts_lower:
                    feature["time_series_type"] = "rolling_window"
                elif 'period' in ts_lower or 'yoy' in ts_lower or 'mom' in ts_lower or 'comparison' in ts_lower:
                    feature["time_series_type"] = "period_over_period"
                elif 'trend' in ts_lower or 'slope' in ts_lower or 'rate' in ts_lower:
                    feature["time_series_type"] = "trend"
                elif 'none' in ts_lower or 'not' in ts_lower or 'n/a' in ts_lower:
                    feature["time_series_type"] = None
                else:
                    # Check if feature_type indicates time series
                    if feature.get("feature_type", "").lower() == "time_series":
                        feature["time_series_type"] = "snapshot"  # Default for time_series type
                    else:
                        feature["time_series_type"] = None
            
            # If we found at least a feature name, add it
            if "feature_name" in feature and feature["feature_name"]:
                # Set defaults for missing fields
                feature.setdefault("feature_type", "metric")
                # Generate natural language question if not found (REQUIRED)
                if "natural_language_question" not in feature or not feature.get("natural_language_question") or feature.get("natural_language_question") == "N/A":
                    feature_name = feature.get("feature_name", "")
                    if feature_name:
                        # Clean up feature name before using it
                        clean_name = re.sub(r'^\s*\*+\s*:?\s*', '', feature_name).strip()
                        clean_name = re.sub(r'[:*]+\s*$', '', clean_name).strip()
                        # Generate a question from the feature name
                        feature["natural_language_question"] = f"What is the {clean_name.lower().replace('_', ' ')}?"
                    else:
                        feature["natural_language_question"] = "What should this feature calculate?"
                
                # Infer feature group from feature name if not provided
                if "feature_group" not in feature or not feature.get("feature_group"):
                    feature_name_lower = feature.get("feature_name", "").lower()
                    if "vulnerability" in feature_name_lower or "vuln" in feature_name_lower:
                        feature["feature_group"] = "vulnerability_metrics"
                    elif "sla" in feature_name_lower or "breach" in feature_name_lower:
                        feature["feature_group"] = "sla_metrics"
                    elif "remediation" in feature_name_lower or "patch" in feature_name_lower:
                        feature["feature_group"] = "remediation_metrics"
                    elif "risk" in feature_name_lower:
                        feature["feature_group"] = "risk_scores"
                    elif "impact" in feature_name_lower:
                        feature["feature_group"] = "impact_scores"
                    elif "likelihood" in feature_name_lower:
                        feature["feature_group"] = "likelihood_scores"
                    elif "count" in feature_name_lower:
                        feature["feature_group"] = "count_metrics"
                    else:
                        feature["feature_group"] = "general_metrics"
                
                feature.setdefault("required_schemas", [])
                feature.setdefault("required_fields", [])
                feature.setdefault("aggregation_method", "count")
                feature.setdefault("filters_applied", [])
                feature.setdefault("business_context", "N/A")
                if "compliance_reasoning" not in feature or not feature["compliance_reasoning"]:
                    feature["compliance_reasoning"] = feature.get("business_context", "")
                
                # Set defaults for transformation layer and time series type
                if "transformation_layer" not in feature:
                    # Infer from feature characteristics
                    if feature.get("aggregation_method", "").lower() not in ["n/a", ""]:
                        feature["transformation_layer"] = "gold"  # Aggregations are typically gold
                    elif feature.get("feature_type", "").lower() in ["time_series", "derived"]:
                        feature["transformation_layer"] = "gold"  # Derived metrics are gold
                    else:
                        feature["transformation_layer"] = "gold"  # Default to gold for analytics features
                
                if "time_series_type" not in feature:
                    # Infer from feature type and name
                    feature_name_lower = feature.get("feature_name", "").lower()
                    if feature.get("feature_type", "").lower() == "time_series":
                        # Check name for hints
                        if any(word in feature_name_lower for word in ["cumulative", "total", "running"]):
                            feature["time_series_type"] = "cumulative"
                        elif any(word in feature_name_lower for word in ["rolling", "moving", "average", "window"]):
                            feature["time_series_type"] = "rolling_window"
                        elif any(word in feature_name_lower for word in ["trend", "growth", "rate", "slope"]):
                            feature["time_series_type"] = "trend"
                        elif any(word in feature_name_lower for word in ["yoy", "mom", "period", "comparison"]):
                            feature["time_series_type"] = "period_over_period"
                        else:
                            feature["time_series_type"] = "snapshot"  # Default for time series
                    else:
                        feature["time_series_type"] = None  # Not a time series feature
                
                # Validate feature before adding - filter out invalid features
                feature_name = feature.get("feature_name", "").strip()
                if feature_name and self._is_valid_feature_name(feature_name):
                    features.append(feature)
                else:
                    logger.warning(f"Skipping invalid feature with name: '{feature_name}'")
        
        # Fallback: if no structured parsing worked, try simple extraction
        if not features:
            # Try to extract features from lines starting with numbers
            lines = content.split("\n")
            current_feature = {}
            current_text = ""
            
            for line in lines:
                line = line.strip()
                if re.match(r'^\d+\.', line):
                    if current_feature:
                        features.append(current_feature)
                    # Try to extract feature name from the line
                    name_match = re.search(r'(?:Feature\s+Name|Name)[:\*]?\s*(?:\*\*)?\s*([^-]+?)(?:\s*-\s*|$)', line, re.IGNORECASE)
                    if name_match:
                        current_feature = {"feature_name": name_match.group(1).strip(), "raw_text": line}
                    else:
                        # Extract first meaningful text as feature name
                        parts = re.split(r'[:\-]', line, 2)
                        if len(parts) > 1:
                            current_feature = {"feature_name": parts[1].strip(), "raw_text": line}
                        else:
                            current_feature = {"feature_name": line[:50], "raw_text": line}
                    current_text = line
                elif current_feature:
                    current_text += " " + line
                    current_feature["raw_text"] = current_text
            
            # Add the last feature if it exists
            if current_feature:
                features.append(current_feature)
        
        # Final cleanup: remove any "*:" prefixes from all features
        for feature in features:
            if "feature_name" in feature and feature["feature_name"]:
                # Remove "*:", "* :", " *:", or any combination at the start
                feature["feature_name"] = re.sub(r'^\s*\*+\s*:?\s*', '', feature["feature_name"]).strip()
                feature["feature_name"] = re.sub(r'[:*]+\s*$', '', feature["feature_name"]).strip()
            if "natural_language_question" in feature and feature["natural_language_question"]:
                # Clean up natural language question too
                feature["natural_language_question"] = re.sub(r'^\s*\*+\s*:?\s*', '', feature["natural_language_question"]).strip()
                feature["natural_language_question"] = re.sub(r'[:*]+\s*$', '', feature["natural_language_question"]).strip()
        
        # Final validation: filter out any remaining invalid features
        validated_features = []
        for feature in features:
            feature_name = feature.get("feature_name", "").strip()
            if feature_name and self._is_valid_feature_name(feature_name):
                validated_features.append(feature)
            else:
                logger.warning(f"Filtering out invalid feature: '{feature_name}'")
        
        return validated_features
    
    def _is_valid_feature_name(self, name: str) -> bool:
        """Validate that a feature name is properly formatted"""
        if not name or len(name) < 3:
            return False
        
        name_lower = name.lower().strip()
        
        # Invalid keywords that shouldn't be feature names
        invalid_keywords = ["transformation", "layer", "type", "method", "context", "reasoning",
                           "schemas", "filters", "applied", "required", "fields", "series", "time",
                           "none", "n/a", "unknown", "feature", "name", "group"]
        
        if name_lower in invalid_keywords:
            return False
        
        # Should not start with asterisks or colons (malformed parsing)
        if re.match(r'^\s*[\*:]+', name):
            return False
        
        # Should be snake_case, alphanumeric, or contain underscores
        if not (re.match(r'^[a-z][a-z0-9_]*$', name_lower) or name_lower.replace('_', '').isalnum()):
            return False
        
        # Should not be a single common word (unless it's a valid metric word)
        if len(name.split('_')) == 1 and len(name) < 8:
            # Single words less than 8 chars are likely invalid (unless they're domain-specific)
            # Allow common metric words
            valid_single_words = ["count", "sum", "avg", "min", "max", "rate", "score"]
            if name_lower not in valid_single_words:
                return False
        
        return True


# ============================================================================
# RISK FEATURE ENGINEERING AGENT
# ============================================================================
# RiskFeatureEngineeringAgent has been moved to risk_feature_engineering_agent.py
# Import it at the top of this file


# ============================================================================
# FEATURE COMBINATION AGENT
# ============================================================================

class FeatureCombinationAgent:
    """Agent that combines standard metrics features with risk features into a unified feature set"""
    
    def __init__(self, llm: BaseChatModel, domain_config: DomainConfiguration):
        self.llm = llm
        self.domain_config = domain_config
    
    def _get_domain_config_from_state(self, state: FeatureEngineeringState) -> DomainConfiguration:
        """Get domain config from state or use instance config"""
        domain_config_dict = state.get("domain_config")
        if domain_config_dict:
            return DomainConfiguration(**domain_config_dict)
        return self.domain_config
    
    async def __call__(self, state: FeatureEngineeringState) -> FeatureEngineeringState:
        """Combine standard features with risk features into unified feature set"""
        
        domain_config = self._get_domain_config_from_state(state)
        
        # Get standard features (from FeatureRecommendationAgent)
        standard_features = state.get("recommended_features", [])
        
        # Get risk features (from RiskFeatureEngineeringAgent)
        impact_features = state.get("impact_features", [])
        likelihood_features = state.get("likelihood_features", [])
        risk_features = state.get("risk_features", [])
        
        # Combine all features
        all_features = standard_features + impact_features + likelihood_features + risk_features
        
        # Add metadata to distinguish feature types (only if not already set)
        for feature in standard_features:
            if "feature_category" not in feature:
                feature["feature_category"] = "standard_metric"
        
        for feature in impact_features:
            if "feature_category" not in feature:
                feature["feature_category"] = "risk_impact"
        
        for feature in likelihood_features:
            if "feature_category" not in feature:
                feature["feature_category"] = "risk_likelihood"
        
        for feature in risk_features:
            if "feature_category" not in feature:
                feature["feature_category"] = "risk_score"
        
        # Update state with combined features
        state["recommended_features"] = all_features
        
        # Create summary
        summary = {
            "total_features": len(all_features),
            "standard_metrics": len(standard_features),
            "impact_features": len(impact_features),
            "likelihood_features": len(likelihood_features),
            "risk_features": len(risk_features)
        }
        
        state["messages"].append(AIMessage(
            content=f"Combined {len(standard_features)} standard metrics with {len(impact_features)} impact, {len(likelihood_features)} likelihood, and {len(risk_features)} risk features (total: {len(all_features)} features)",
            name="FeatureCombinationAgent"
        ))
        
        state["next_agent"] = "feature_dependency"
        
        return state


# ============================================================================
# FEATURE CALCULATION PLAN AGENT
# ============================================================================

class FeatureCalculationPlanAgent:
    """Agent that generates a calculation plan for features based on knowledge documents instead of schema lookup"""
    
    def __init__(self, llm: BaseChatModel, domain_config: DomainConfiguration):
        self.llm = llm
        self.domain_config = domain_config
    
    def _get_domain_config_from_state(self, state: FeatureEngineeringState) -> DomainConfiguration:
        """Get domain config from state or use instance config"""
        domain_config_dict = state.get("domain_config")
        if domain_config_dict:
            return DomainConfiguration(**domain_config_dict)
        return self.domain_config
    
    async def __call__(self, state: FeatureEngineeringState) -> FeatureEngineeringState:
        """Generate a calculation plan for features based on knowledge documents"""
        
        domain_config = self._get_domain_config_from_state(state)
        features = state.get("recommended_features", [])
        knowledge_documents = state.get("knowledge_documents", [])
        user_query = state.get("user_query", "")
        analytical_intent = state.get("analytical_intent", {})
        
        if not features:
            logger.warning("No features to create calculation plan for")
            state["feature_calculation_plan"] = {
                "plan_id": f"plan_{hash(state.get('user_query', '')) % 10000}",
                "features": [],
                "calculation_steps": [],
                "data_requirements": [],
                "knowledge_based": True
            }
            state["next_agent"] = "create_reasoning_plan"
            return state
        
        system_prompt = f"""You are an expert at creating feature calculation plans based on knowledge documents and domain expertise for {domain_config.domain_description or domain_config.domain_name} analytics.

Your task is to generate a detailed calculation plan for each recommended feature. Instead of looking up schemas, use the knowledge documents and domain expertise to determine:
1. What data columns/fields are needed (based on knowledge, not schema lookup)
2. How to calculate each feature (step-by-step logic)
3. What transformations are required
4. What aggregations are needed
5. What filters should be applied

The plan should be:
- Knowledge-based: Use information from knowledge documents to infer data requirements
- Domain-aware: Leverage {domain_config.domain_name} domain expertise
- Feature-specific: Provide detailed calculation steps for each feature
- Executable: Could be translated to SQL/Python code
- Dependency-aware: Consider feature dependencies when ordering calculations

For each feature, provide:
- Required data fields (inferred from knowledge, not from schema)
- Calculation steps (detailed logic)
- Transformations needed
- Aggregations required
- Filters to apply
- Dependencies on other features (if any)"""

        features_text = "\n".join([
            f"{i+1}. {f.get('feature_name', 'Unknown')}: {f.get('calculation_logic', 'N/A')}"
            for i, f in enumerate(features)
        ])
        
        knowledge_text = self._format_knowledge_documents(knowledge_documents)
        
        prompt = f"""
USER QUERY: {user_query}

ANALYTICAL INTENT:
{analytical_intent}

RECOMMENDED FEATURES:
{features_text}

KNOWLEDGE DOCUMENTS:
{knowledge_text}

Based on the knowledge documents and domain expertise, create a detailed calculation plan for each feature.
For each feature, specify:
1. Required data fields (what columns/fields are needed - infer from knowledge, not schema)
2. Calculation steps (how to compute the feature)
3. Transformations (data transformations needed)
4. Aggregations (grouping and summarization)
5. Filters (conditions to apply)
6. Dependencies (which other features this depends on)

Return your plan as JSON:
{{
    "plan_id": "plan_identifier",
    "features": [
        {{
            "feature_name": "feature_name",
            "required_fields": ["field1", "field2"],
            "calculation_steps": [
                {{"step": 1, "description": "step description", "logic": "calculation logic"}},
                {{"step": 2, "description": "step description", "logic": "calculation logic"}}
            ],
            "transformations": ["transformation1", "transformation2"],
            "aggregations": ["aggregation1", "aggregation2"],
            "filters": ["filter1", "filter2"],
            "dependencies": ["dependency_feature1"],
            "knowledge_based_reasoning": "explanation of how knowledge documents informed this plan"
        }}
    ],
    "overall_calculation_sequence": ["feature1", "feature2"],
    "data_requirements_summary": "summary of all data fields needed"
}}
"""
        
        try:
            response = await track_llm_call(
                agent_name="FeatureCalculationPlanAgent",
                llm=self.llm,
                messages=[
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=prompt)
                ],
                state=state,
                step_name="feature_calculation_planning"
            )
            
            # Parse JSON response
            content = response.content if hasattr(response, 'content') else str(response)
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                try:
                    calculation_plan = json.loads(json_match.group(0))
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON parsing failed in FeatureCalculationPlanAgent: {e}")
                    # Try to fix common JSON issues
                    json_str = json_match.group(0)
                    json_str = re.sub(r'//.*?$', '', json_str, flags=re.MULTILINE)
                    json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
                    json_str = re.sub(r',\s*}', '}', json_str)
                    json_str = re.sub(r',\s*]', ']', json_str)
                    try:
                        calculation_plan = json.loads(json_str)
                    except json.JSONDecodeError:
                        calculation_plan = self._create_fallback_plan(features)
            else:
                # Fallback: create basic plan structure
                calculation_plan = self._create_fallback_plan(features)
            
            # Validate plan structure
            validated_plan = self._validate_calculation_plan(calculation_plan, features)
            
            state["feature_calculation_plan"] = validated_plan
            state["messages"].append(AIMessage(
                content=f"Created knowledge-based calculation plan for {len(features)} features",
                name="FeatureCalculationPlanAgent"
            ))
            # Continue to feature dependency analysis
            # Note: Impact, Likelihood, and Risk features are generated in STEP 3 (Deep Research & Risk Modeling)
            state["next_agent"] = "feature_dependency"
            
        except Exception as e:
            logger.error(f"Error in FeatureCalculationPlanAgent: {e}")
            # Fallback to basic structure
            state["feature_calculation_plan"] = self._create_fallback_plan(features)
            # Continue to feature dependency analysis
            state["next_agent"] = "feature_dependency"
        
        return state
    
    def _format_knowledge_documents(self, knowledge_documents: List[Dict[str, Any]]) -> str:
        """Format knowledge documents for the prompt"""
        if not knowledge_documents:
            return "No relevant knowledge documents available."
        
        formatted = []
        for i, doc in enumerate(knowledge_documents, 1):
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})
            framework = metadata.get("framework", "")
            category = metadata.get("category", "")
            
            formatted.append(f"\n--- Knowledge Document {i} ---")
            if framework:
                formatted.append(f"Framework: {framework}")
            if category:
                formatted.append(f"Category: {category}")
            formatted.append(f"Content:\n{content}")
        
        return "\n".join(formatted)
    
    def _create_fallback_plan(self, features: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a basic calculation plan structure when parsing fails"""
        feature_plans = []
        for f in features:
            feature_name = f.get('feature_name', 'unknown')
            feature_plans.append({
                "feature_name": feature_name,
                "required_fields": f.get('required_fields', []),
                "calculation_steps": [
                    {"step": 1, "description": f"Calculate {feature_name}", "logic": f.get('calculation_logic', 'N/A')}
                ],
                "transformations": [],
                "aggregations": [f.get('aggregation_method', 'N/A')],
                "filters": f.get('filters_applied', []),
                "dependencies": [],
                "knowledge_based_reasoning": "Basic plan generated from feature metadata"
            })
        
        return {
            "plan_id": f"plan_{hash(str(features)) % 10000}",
            "features": feature_plans,
            "overall_calculation_sequence": [f.get('feature_name', f'feature_{i}') for i, f in enumerate(features)],
            "data_requirements_summary": "Fields inferred from feature definitions"
        }
    
    def _validate_calculation_plan(self, data: Dict[str, Any], features: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate and fix calculation plan structure"""
        feature_names = {f.get('feature_name', f'feature_{i}') for i, f in enumerate(features)}
        
        # Validate feature plans
        validated_features = []
        for plan in data.get('features', []):
            feat_name = plan.get('feature_name', '')
            if feat_name in feature_names:
                validated_features.append({
                    "feature_name": feat_name,
                    "required_fields": plan.get('required_fields', []),
                    "calculation_steps": plan.get('calculation_steps', []),
                    "transformations": plan.get('transformations', []),
                    "aggregations": plan.get('aggregations', []),
                    "filters": plan.get('filters', []),
                    "dependencies": [d for d in plan.get('dependencies', []) if d in feature_names],
                    "knowledge_based_reasoning": plan.get('knowledge_based_reasoning', '')
                })
        
        return {
            "plan_id": data.get('plan_id', f"plan_{hash(str(features)) % 10000}"),
            "features": validated_features,
            "overall_calculation_sequence": data.get('overall_calculation_sequence', []),
            "data_requirements_summary": data.get('data_requirements_summary', ''),
            "knowledge_based": True
        }


# ============================================================================
# IMPACT, LIKELIHOOD, AND RISK FEATURE GENERATION AGENTS
# ============================================================================
# NOTE: These agents are part of STEP 3 (Deep Research & Risk Modeling)
# They are kept here for backward compatibility and can be called separately.
# The main Feature Engineering workflow (STEP 2) does NOT automatically
# route to these agents. Instead, they should be called as part of the
# Deep Research & Risk Modeling workflow (see risk_model_agents.py).
#
# TODO: Move these agents to a separate deep_research_agents.py module
# or integrate them into risk_model_agents.py for STEP 3.
# ============================================================================

class ImpactFeatureGenerationAgent:
    """Agent that generates impact features as natural language questions based on knowledge and existing features"""
    
    def __init__(self, llm: BaseChatModel, domain_config: DomainConfiguration):
        self.llm = llm
        self.domain_config = domain_config
    
    def _get_domain_config_from_state(self, state: FeatureEngineeringState) -> DomainConfiguration:
        """Get domain config from state or use instance config"""
        domain_config_dict = state.get("domain_config")
        if domain_config_dict:
            return DomainConfiguration(**domain_config_dict)
        return self.domain_config
    
    def _get_impact_sql_function_context(self) -> str:
        """Get SQL function documentation for impact calculations"""
        return """
GENERIC IMPACT CALCULATION SQL FUNCTIONS:

The impact features you generate will be converted to SQL using generic impact calculation functions. 
These functions accept parameters in JSON format and calculate impact scores using configurable methods.

CONTROL PRIORITIZATION CONFIGS:
When controls are identified, you can use DEFAULT_CONTROL_PRIORITIZATION_CONFIGS from domain_config.py which provide:
- default_impact: str (1-5 scale) - Convert to 0-100 scale: (value * 20) - 20, e.g., "4" -> 60, "5" -> 80
- default_relevance_score: float (0.0-1.0) - Can be used directly or scaled to 0-100
- default_quality_score: float (0.0-1.0) - Can be used directly or scaled to 0-100
- default_coverage_score: float (0.0-1.0) - Can be used directly or scaled to 0-100
- priority_notes: str - Contextual information about the control

These defaults should be used when actual impact data is not available. Map control_id to get_control_prioritization_config(control_id).

MAIN FUNCTION: calculate_impact_from_json(p_config JSONB)
- Accepts a JSON configuration with parameters array and aggregation settings
- Returns: overall_impact, direct_impact, indirect_impact, cascading_impact, aggregation_method, impact_by_category, parameter_scores, calculation_summary

PARAMETER STRUCTURE (each parameter in the 'parameters' array):
{
    "param_name": "string",              // Name of the parameter (e.g., 'asset_criticality', 'financial_impact')
    "param_value": decimal,               // Current value of the parameter (0-100 or raw value)
    "param_weight": decimal,              // Weight in final calculation (0-1, typically 0.1-0.5)
    "max_value": decimal,                // Maximum expected value for normalization (default 100.0)
    "impact_category": "string",          // 'direct', 'indirect', 'cascading', 'reputational', 'financial', 'operational', 'compliance'
    "amplification_factor": decimal,      // Multiplier for cascading impacts (default 1.0, use 1.2-2.0 for critical factors)
    "decay_function": "string",          // 'none', 'linear', 'exponential', 'logarithmic', 'step', 'compound', 'inverse_exponential', 'sigmoid', 'square'
    "decay_rate": decimal,               // Decay rate parameter (tau for exponential, etc., default 1.0)
    "time_delta": decimal,                // Time elapsed for decay calculation (days, hours, etc., default 0)
    "inverse": boolean,                   // If true, higher value = lower impact (default false)
    "threshold_critical": decimal,       // Critical threshold (default 90.0)
    "threshold_high": decimal,            // High threshold (default 70.0)
    "threshold_medium": decimal           // Medium threshold (default 50.0)
}

AGGREGATION METHODS:
- 'weighted_sum': Weighted average (default, most common)
- 'max': Maximum impact (worst case scenario)
- 'least': Minimum impact (best case scenario)
- 'geometric_mean': Product root (for multiplicative effects)
- 'cascading': Includes cascade multiplier for compound effects
- 'quadratic_mean': Root mean square

CONFIGURATION STRUCTURE:
{
    "aggregation_method": "weighted_sum",  // Aggregation method (see above)
    "scale_to": 100.0,                    // Scale final result to this value (default 100.0)
    "enable_cascade": false,               // Enable cascading impact calculation (default false)
    "cascade_depth": 3,                   // Depth of cascade (1=primary only, 2=secondary, 3=tertiary)
    "parameters": [                        // Array of parameter objects (see structure above)
        {
            "param_name": "regulatory_severity",
            "param_value": 85.0,
            "param_weight": 0.40,
            "max_value": 100.0,
            "impact_category": "direct",
            "amplification_factor": 1.0,
            "decay_function": "none"
        },
        ...
    ]
}

IMPORTANT FOR NATURAL LANGUAGE QUESTIONS:
When generating impact features, include in the natural_language_question and description:
1. Parameter names and their source data fields (or control prioritization config defaults)
2. Parameter weights (how important each factor is)
3. Aggregation method (how parameters combine)
4. Impact categories (direct, indirect, cascading, etc.)
5. Max values for normalization (what's the scale)
6. Decay functions if time-based (e.g., "exponential decay over 30 days")
7. Amplification factors for critical factors
8. Whether any parameters are inverse (higher value = lower impact)
9. When controls are identified, mention using control prioritization configs (default_impact, default_relevance_score, etc.)

Example natural language question with SQL context:
"What is the overall impact score combining regulatory severity (weight 0.4, max 100, direct category), 
financial impact (weight 0.3, max 100000, financial category, amplification 1.5), and operational 
disruption (weight 0.3, max 100, operational category) using weighted_sum aggregation, scaled to 100?"

Example with control prioritization:
"What is the overall impact score for identified controls using control prioritization config defaults 
(default_impact converted from 1-5 scale to 0-100, weight 0.5, direct category) combined with 
regulatory severity (weight 0.3, max 100, direct category) and financial impact (weight 0.2, max 100000, 
financial category) using weighted_sum aggregation, scaled to 100?"

This provides enough context for another agent to construct the SQL function call.
"""
    
    async def __call__(self, state: FeatureEngineeringState) -> FeatureEngineeringState:
        """Generate impact features as natural language questions using universal impact dimensions"""
        
        domain_config = self._get_domain_config_from_state(state)
        recommended_features = state.get("recommended_features", [])
        knowledge_documents = state.get("knowledge_documents", [])
        identified_controls = state.get("identified_controls", [])
        use_case_groups = state.get("use_case_groups", [])
        current_group_index = state.get("current_risk_group_index", 0)
        user_query = state.get("user_query", "")
        analytical_intent = state.get("analytical_intent", {})
        compliance_framework = analytical_intent.get("compliance_framework", "").upper()
        
        # If use case groups exist, focus on current group
        if use_case_groups and current_group_index < len(use_case_groups):
            current_group = use_case_groups[current_group_index]
            # Filter features and controls for current group
            group_features = current_group.get("features", [])
            group_controls = current_group.get("controls", [])
            # Use group-specific features and controls for this generation
            recommended_features = group_features
            identified_controls = group_controls
        
        # Format identified controls for prompt
        controls_info = self._format_controls_for_impact(identified_controls)
        
        system_prompt = f"""You are a data scientist specializing in impact assessment and consequence modeling for compliance.

Your task is to generate impact features that measure "If this control fails, what is the consequence?" using UNIVERSAL IMPACT DIMENSIONS that work across ALL compliance types (SOC2, HIPAA, HR, Finance, etc.).

{self._get_impact_sql_function_context()}

UNIVERSAL IMPACT DIMENSIONS (use these as the foundation):
1. REGULATORY SEVERITY - Regulatory penalty tiers, enforcement levels
2. CUSTOMER TRUST / BRAND SENSITIVITY - Reputational damage, brand impact
3. FINANCIAL IMPACT - Fines, remediation costs, lost revenue
4. OPERATIONAL DISRUPTION - Process downtime, recovery time, staff impact
5. DOWNSTREAM DEPENDENCY - Cascading failures, dependent controls
6. CROWN JEWEL RELEVANCE - Critical systems/processes affected

DOMAIN CONTEXT:
- Domain: {domain_config.domain_name}
- Entity Types: {', '.join(domain_config.entity_types) if domain_config.entity_types else 'N/A'}
- Severity Levels: {', '.join(domain_config.severity_levels) if domain_config.severity_levels else 'N/A'}
- Compliance Frameworks: {', '.join(domain_config.compliance_frameworks) if domain_config.compliance_frameworks else 'N/A'}
- Target Framework: {compliance_framework}

{controls_info}

For each universal dimension, create impact features that:
- Work across all compliance domains (SOC2, HIPAA, HR, Finance, etc.)
- Can be adapted with domain-specific adjustments
- Quantify consequences in measurable ways
- Map to specific controls when controls are identified
- Include sufficient detail in natural language questions for SQL generation

For each impact feature, provide:
1. Feature name following universal conventions (e.g., "regulatory_severity_impact", "financial_impact", "operational_disruption_impact")
2. Natural language question that includes SQL-relevant context:
   - Parameter names and source data fields (or control prioritization config defaults when controls are identified)
   - Parameter weights (0-1, typically 0.1-0.5)
   - Aggregation method (weighted_sum, max, least, geometric_mean, cascading, quadratic_mean)
   - Impact categories (direct, indirect, cascading, reputational, financial, operational, compliance)
   - Max values for normalization
   - Decay functions if time-based
   - Amplification factors for critical factors
   - Whether any parameters are inverse
   - When controls are identified: mention using DEFAULT_CONTROL_PRIORITIZATION_CONFIGS.default_impact (1-5 scale, convert to 0-100) and default_relevance_score
3. Impact dimension it measures (regulatory_severity, financial, operational, etc.)
4. Calculation method (how to quantify this impact, including SQL function parameters)
5. Data sources (where measurement data comes from, or control prioritization configs when controls are identified)
6. Unit of measure (score, dollars, hours, etc.)
7. Ranges (low/medium/high impact values)
8. Cross-domain applicability (how it works for different frameworks)
9. Domain-specific adjustments (if needed for {domain_config.domain_name})
10. Control mapping (which identified controls this supports, if controls are identified - use get_control_prioritization_config(control_id) to get defaults)
11. SQL function parameters (detailed breakdown of param_name, param_value source, param_weight, max_value, impact_category, etc.)
12. Control prioritization usage (how to use DEFAULT_CONTROL_PRIORITIZATION_CONFIGS when controls are identified)

Generate impact features as JSON array with this structure:
[
    {{
        "feature_name": "raw_impact",
        "natural_language_question": "What is the overall raw impact score for {domain_config.entity_types[0] if domain_config.entity_types else 'entities'} combining regulatory severity (weight 0.4, max 100, direct category), financial impact (weight 0.3, max 100000, financial category, amplification 1.2), and operational disruption (weight 0.3, max 100, operational category) using weighted_sum aggregation, scaled to 100?",
        "description": "Overall raw impact score without considering controls. Combines regulatory severity, financial impact, and operational disruption using weighted sum aggregation.",
        "impact_type": "overall",
        "feature_type": "float",
        "calculation_logic": "Weighted combination of all impact factors using calculate_impact_from_json with weighted_sum aggregation",
        "sql_function": "calculate_impact_from_json",
        "sql_parameters": {{
            "aggregation_method": "weighted_sum",
            "scale_to": 100.0,
            "enable_cascade": false,
            "parameters": [
                {{"param_name": "regulatory_severity", "param_value": "regulatory_severity_score", "param_weight": 0.4, "max_value": 100.0, "impact_category": "direct", "amplification_factor": 1.0, "decay_function": "none"}},
                {{"param_name": "financial_impact", "param_value": "financial_impact_amount", "param_weight": 0.3, "max_value": 100000.0, "impact_category": "financial", "amplification_factor": 1.2, "decay_function": "none"}},
                {{"param_name": "operational_disruption", "param_value": "operational_disruption_score", "param_weight": 0.3, "max_value": 100.0, "impact_category": "operational", "amplification_factor": 1.0, "decay_function": "none"}}
            ]
        }},
        "control_prioritization_usage": "When controls are identified, can use DEFAULT_CONTROL_PRIORITIZATION_CONFIGS.default_impact (1-5 scale, convert to 0-100) and default_relevance_score (0-1 scale) as additional parameters",
        "related_features": [],
        "knowledge_based_reasoning": "Based on domain knowledge about impact assessment"
    }},
    {{
        "feature_name": "effective_impact",
        "natural_language_question": "What is the effective impact score after considering controls and mitigations, combining raw impact (weight 0.7, max 100, direct category) and control effectiveness (weight 0.3, max 100, indirect category, inverse true) using weighted_sum aggregation?",
        "description": "Effective impact after controls are applied. Combines raw impact with control effectiveness adjustment.",
        "impact_type": "effective",
        "feature_type": "float",
        "calculation_logic": "Raw impact adjusted for effectiveness of controls using calculate_impact_from_json",
        "sql_function": "calculate_impact_from_json",
        "sql_parameters": {{
            "aggregation_method": "weighted_sum",
            "scale_to": 100.0,
            "enable_cascade": false,
            "parameters": [
                {{"param_name": "raw_impact", "param_value": "raw_impact_score", "param_weight": 0.7, "max_value": 100.0, "impact_category": "direct", "decay_function": "none"}},
                {{"param_name": "control_effectiveness", "param_value": "control_effectiveness_score", "param_weight": 0.3, "max_value": 100.0, "impact_category": "indirect", "inverse": true, "decay_function": "none"}}
            ]
        }},
        "related_features": ["raw_impact"],
        "knowledge_based_reasoning": "Based on domain knowledge about control effectiveness"
    }}
]

Generate 6-8 impact features covering the universal impact dimensions. Prioritize features that:
- Map to identified controls (if controls are identified)
- Work universally across compliance frameworks
- Can be calculated using available data
- Support risk assessment (Risk = Likelihood × Impact)

Example impact features:
- regulatory_severity_impact: Maps control to regulatory penalty tier
- financial_impact: Estimates potential fines and remediation costs
- operational_disruption_impact: Measures process downtime and recovery time
- brand_sensitivity_impact: Quantifies reputational damage potential
- downstream_dependency_impact: Counts dependent controls affected
- crown_jewel_impact: Identifies critical systems/processes at risk"""

        features_text = "\n".join([
            f"- {f.get('feature_name', 'Unknown')}: {f.get('natural_language_question', f.get('calculation_logic', 'N/A'))}"
            for f in recommended_features[:10]  # Use first 10 features
        ])
        
        knowledge_text = self._format_knowledge_documents(knowledge_documents)
        
        prompt = f"""
USER QUERY: {user_query}

ANALYTICAL INTENT:
{analytical_intent}

EXISTING FEATURES:
{features_text}

KNOWLEDGE DOCUMENTS:
{knowledge_text}

DOMAIN CONTEXT:
- Entity Types: {', '.join(domain_config.entity_types) if domain_config.entity_types else 'N/A'}
- Severity Levels: {', '.join(domain_config.severity_levels) if domain_config.severity_levels else 'N/A'}
- Compliance Frameworks: {', '.join(domain_config.compliance_frameworks) if domain_config.compliance_frameworks else 'N/A'}

Generate impact features that are:
1. Domain-relevant: Appropriate for {domain_config.domain_name} domain
2. Knowledge-based: Derived from the knowledge documents provided
3. Context-aware: Consider the existing features and analytical intent
4. Well-named: Use descriptive names following domain conventions (e.g., "{{impact_type}}_impact", "{{entity_type}}_impact")

Each feature must include: feature_name, natural_language_question, description, impact_type, feature_type (float), calculation_logic, sql_function, sql_parameters, related_features, and knowledge_based_reasoning.

CRITICAL: The natural_language_question must include enough detail for SQL generation:
- Explicitly mention parameter names, weights, max values, impact categories
- Specify aggregation method (weighted_sum, max, least, geometric_mean, cascading, quadratic_mean)
- Include decay functions if time-based
- Mention amplification factors for critical factors
- Note if any parameters are inverse

The sql_parameters field should provide a complete JSON structure that can be used directly with calculate_impact_from_json function, with parameter values referencing source data fields.

Focus on impact dimensions that are relevant to {domain_config.domain_name} based on the knowledge documents.
"""
        
        try:
            response = await track_llm_call(
                agent_name="ImpactFeatureGenerationAgent",
                llm=self.llm,
                messages=[
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=prompt)
                ],
                state=state,
                step_name="impact_feature_generation"
            )
            
            # Parse JSON response
            content = response.content if hasattr(response, 'content') else str(response)
            json_match = re.search(r'\[[\s\S]*\]', content)
            if json_match:
                try:
                    impact_features = json.loads(json_match.group(0))
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON parsing failed in ImpactFeatureGenerationAgent: {e}")
                    # Try to fix common JSON issues
                    json_str = json_match.group(0)
                    json_str = re.sub(r'//.*?$', '', json_str, flags=re.MULTILINE)
                    json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
                    json_str = re.sub(r',\s*}', '}', json_str)
                    json_str = re.sub(r',\s*]', ']', json_str)
                    try:
                        impact_features = json.loads(json_str)
                    except json.JSONDecodeError:
                        impact_features = self._create_fallback_impact_features(domain_config)
            else:
                impact_features = self._create_fallback_impact_features()
            
            state["impact_features"] = impact_features
            state["messages"].append(AIMessage(
                content=f"Generated {len(impact_features)} impact feature questions",
                name="ImpactFeatureGenerationAgent"
            ))
            state["next_agent"] = "likelihood_feature_generation"  # Continue to likelihood features
            
        except Exception as e:
            logger.error(f"Error in ImpactFeatureGenerationAgent: {e}")
            state["impact_features"] = self._create_fallback_impact_features(domain_config)
            state["next_agent"] = "end"  # Stop here even on error
        
        return state
    
    def _format_knowledge_documents(self, knowledge_documents: List[Dict[str, Any]]) -> str:
        """Format knowledge documents for the prompt"""
        if not knowledge_documents:
            return "No relevant knowledge documents available."
        
        formatted = []
        for i, doc in enumerate(knowledge_documents, 1):
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})
            framework = metadata.get("framework", "")
            category = metadata.get("category", "")
            
            formatted.append(f"\n--- Knowledge Document {i} ---")
            if framework:
                formatted.append(f"Framework: {framework}")
            if category:
                formatted.append(f"Category: {category}")
            formatted.append(f"Content:\n{content}")
        
        return "\n".join(formatted)
    
    def _format_controls_for_impact(self, identified_controls: List[Dict[str, Any]]) -> str:
        """Format identified controls for impact feature generation"""
        if not identified_controls:
            return "No controls have been identified yet. Generate universal impact features that work across all compliance types."
        
        formatted = []
        formatted.append(f"\n=== IDENTIFIED CONTROLS ({len(identified_controls)} controls) ===")
        formatted.append("Generate impact features that map to these controls:\n")
        
        for i, control in enumerate(identified_controls[:10], 1):  # Limit to 10 for prompt size
            formatted.append(f"{i}. {control.get('control_id', 'UNKNOWN')}: {control.get('control_name', 'N/A')}")
            formatted.append(f"   Category: {control.get('category', 'N/A')}")
            formatted.append(f"   Description: {control.get('description', 'N/A')[:150]}")
        
        formatted.append("\nFor each control, consider:")
        formatted.append("- Regulatory severity if this control fails")
        formatted.append("- Financial impact (fines, remediation costs)")
        formatted.append("- Operational disruption if control fails")
        formatted.append("- Downstream dependencies (other controls affected)")
        formatted.append("- Crown jewel relevance (critical systems involved)")
        
        return "\n".join(formatted)
    
    def _create_fallback_impact_features(self, domain_config: DomainConfiguration) -> List[Dict[str, Any]]:
        """Create fallback impact features based on universal impact dimensions"""
        entity_type = domain_config.entity_types[0] if domain_config.entity_types else "entity"
        return [
            {
                "feature_name": "regulatory_severity_impact",
                "natural_language_question": f"What is the regulatory severity impact score for {entity_type.lower()}s?",
                "description": "Regulatory penalty tier and enforcement level impact",
                "impact_type": "regulatory_severity",
                "impact_dimension": "regulatory_severity",
                "feature_type": "float",
                "calculation_logic": "Map control to regulatory penalty tier (Tier 1 = low, Tier 2 = high)",
                "related_features": [],
                "knowledge_based_reasoning": f"Universal regulatory severity impact for {domain_config.domain_name} domain"
            },
            {
                "feature_name": "financial_impact",
                "natural_language_question": f"What is the estimated financial impact for {entity_type.lower()}s?",
                "description": "Potential fines, remediation costs, and lost revenue",
                "impact_type": "financial",
                "impact_dimension": "financial",
                "feature_type": "float",
                "calculation_logic": "Sum of potential fines, remediation costs, and lost revenue estimates",
                "related_features": [],
                "knowledge_based_reasoning": f"Universal financial impact for {domain_config.domain_name} domain"
            },
            {
                "feature_name": "operational_disruption_impact",
                "natural_language_question": f"What is the operational disruption impact for {entity_type.lower()}s?",
                "description": "Process downtime, recovery time, and staff impact",
                "impact_type": "operational",
                "impact_dimension": "operational_disruption",
                "feature_type": "float",
                "calculation_logic": "Measure process downtime, recovery time, and staff hours affected",
                "related_features": [],
                "knowledge_based_reasoning": f"Universal operational disruption impact for {domain_config.domain_name} domain"
            }
        ]


class LikelihoodFeatureGenerationAgent:
    """Agent that generates likelihood features as natural language questions based on knowledge and existing features"""
    
    def __init__(self, llm: BaseChatModel, domain_config: DomainConfiguration):
        self.llm = llm
        self.domain_config = domain_config
    
    def _get_domain_config_from_state(self, state: FeatureEngineeringState) -> DomainConfiguration:
        """Get domain config from state or use instance config"""
        domain_config_dict = state.get("domain_config")
        if domain_config_dict:
            return DomainConfiguration(**domain_config_dict)
        return self.domain_config
    
    def _get_likelihood_sql_function_context(self) -> str:
        """Get SQL function documentation for likelihood calculations"""
        return """
GENERIC LIKELIHOOD CALCULATION SQL FUNCTIONS:

The likelihood features you generate will be converted to SQL using generic likelihood calculation functions.
These functions accept parameters in JSON format and calculate likelihood scores using configurable methods.

CONTROL PRIORITIZATION CONFIGS:
When controls are identified, you can use DEFAULT_CONTROL_PRIORITIZATION_CONFIGS from domain_config.py which provide:
- default_likelihood: str (1-5 scale) - Convert to 0-100 scale: (value * 20) - 20, e.g., "3" -> 40, "4" -> 60, "5" -> 80
- default_relevance_score: float (0.0-1.0) - Can be used directly or scaled to 0-100
- default_quality_score: float (0.0-1.0) - Can be used directly or scaled to 0-100
- default_coverage_score: float (0.0-1.0) - Can be used directly or scaled to 0-100
- default_has_coverage_gaps: bool - Can be converted to score (true -> higher likelihood)
- priority_notes: str - Contextual information about the control

These defaults should be used when actual likelihood data is not available. Map control_id to get_control_prioritization_config(control_id).

MAIN FUNCTION: calculate_likelihood_from_json(p_config JSONB)
- Accepts a JSON configuration with parameters array and aggregation settings
- Returns: overall_likelihood, aggregation_method, parameter_scores, calculation_summary

PARAMETER STRUCTURE (each parameter in the 'parameters' array):
{
    "param_name": "string",              // Name of the parameter (e.g., 'critical_vuln_count', 'patch_compliance_rate')
    "param_value": decimal,               // Current value of the parameter (0-100 or raw value)
    "param_weight": decimal,              // Weight in final calculation (0-1, typically 0.1-0.5)
    "max_value": decimal,                // Maximum expected value for normalization (default 100.0)
    "decay_function": "string",          // 'none', 'linear', 'exponential', 'logarithmic', 'step', 'inverse_exponential', 'sigmoid'
    "decay_rate": decimal,               // Decay rate parameter (tau for exponential, etc., default 1.0)
    "time_delta": decimal,                // Time elapsed for decay calculation (days, hours, etc., default 0)
    "inverse": boolean,                   // If true, higher value = lower likelihood (e.g., patch_compliance where high = good)
    "threshold_low": decimal,            // Lower threshold for step function (default 0)
    "threshold_high": decimal            // Upper threshold for step function (default 100.0)
}

AGGREGATION METHODS:
- 'weighted_sum': Weighted average (default, most common)
- 'least': Minimum likelihood (conservative, worst case)
- 'max': Maximum likelihood (optimistic, best case)
- 'geometric_mean': Product root (for multiplicative effects)
- 'harmonic_mean': Harmonic average (for rates)
- 'quadratic_mean': Root mean square

CONFIGURATION STRUCTURE:
{
    "aggregation_method": "weighted_sum",  // Aggregation method (see above)
    "scale_to": 100.0,                    // Scale final result to this value (default 100.0)
    "normalization_method": "none",        // 'none', 'min_max', 'z_score', 'sigmoid' (default 'none')
    "parameters": [                        // Array of parameter objects (see structure above)
        {
            "param_name": "critical_vulns",
            "param_value": 5.0,
            "param_weight": 0.40,
            "max_value": 20.0,
            "decay_function": "exponential",
            "decay_rate": 30.0,
            "time_delta": 45,
            "inverse": false
        },
        {
            "param_name": "patch_compliance",
            "param_value": 75.0,
            "param_weight": 0.30,
            "max_value": 100.0,
            "decay_function": "none",
            "inverse": true
        },
        ...
    ]
}

IMPORTANT FOR NATURAL LANGUAGE QUESTIONS:
When generating likelihood features, include in the natural_language_question and description:
1. Parameter names and their source data fields (or control prioritization config defaults)
2. Parameter weights (how important each factor is)
3. Aggregation method (how parameters combine)
4. Max values for normalization (what's the scale)
5. Decay functions if time-based (e.g., "exponential decay over 30 days with decay_rate 30.0")
6. Whether any parameters are inverse (higher value = lower likelihood, e.g., compliance rates)
7. Time delta if decay is applied (how much time has elapsed)
8. When controls are identified, mention using control prioritization configs (default_likelihood, default_coverage_score, etc.)

Example natural language question with SQL context:
"What is the overall likelihood score combining critical vulnerabilities (weight 0.4, max 20, exponential decay over 30 days), 
patch compliance rate (weight 0.3, max 100, inverse true), and dwell time (weight 0.3, max 90, linear decay) 
using weighted_sum aggregation, scaled to 100?"

Example with control prioritization:
"What is the overall likelihood score for identified controls using control prioritization config defaults 
(default_likelihood converted from 1-5 scale to 0-100, weight 0.4) combined with historical failure rate 
(weight 0.3, max 100) and coverage gaps (default_has_coverage_gaps converted to score, weight 0.3, max 100) 
using weighted_sum aggregation, scaled to 100?"

This provides enough context for another agent to construct the SQL function call.
"""
    
    async def __call__(self, state: FeatureEngineeringState) -> FeatureEngineeringState:
        """Generate likelihood features as natural language questions using universal likelihood drivers"""
        
        domain_config = self._get_domain_config_from_state(state)
        recommended_features = state.get("recommended_features", [])
        knowledge_documents = state.get("knowledge_documents", [])
        impact_features = state.get("impact_features", [])
        identified_controls = state.get("identified_controls", [])
        user_query = state.get("user_query", "")
        analytical_intent = state.get("analytical_intent", {})
        compliance_framework = analytical_intent.get("compliance_framework", "").upper()
        
        # Format identified controls for prompt
        controls_info = self._format_controls_for_likelihood(identified_controls)
        
        system_prompt = f"""You are a data scientist specializing in predictive modeling for compliance risk.

Your task is to generate likelihood features that answer "How likely is this control to fail?" using UNIVERSAL LIKELIHOOD DRIVERS that work across ALL compliance types (SOC2, HIPAA, HR, Finance, etc.).

{self._get_likelihood_sql_function_context()}

UNIVERSAL LIKELIHOOD DRIVERS (use these as the foundation):
1. HISTORICAL FAILURE RATE - Past failures, audit findings, control testing results
2. CONTROL DRIFT FREQUENCY - Configuration changes, baseline deviations
3. EVIDENCE QUALITY SCORE - Missing, outdated, or incomplete evidence
4. PROCESS VOLATILITY - Change frequency, process stability
5. HUMAN DEPENDENCY - Manual vs automated processes, human error rates
6. OPERATIONAL LOAD - Scale (users, transactions, systems), load factors
7. CONTROL MATURITY LEVEL - CMM-style maturity assessment (1-5)

DOMAIN CONTEXT:
- Domain: {domain_config.domain_name}
- Entity Types: {', '.join(domain_config.entity_types) if domain_config.entity_types else 'N/A'}
- Severity Levels: {', '.join(domain_config.severity_levels) if domain_config.severity_levels else 'N/A'}
- Compliance Frameworks: {', '.join(domain_config.compliance_frameworks) if domain_config.compliance_frameworks else 'N/A'}
- Target Framework: {compliance_framework}

{controls_info}

For each universal driver, create likelihood features that:
- Work across all compliance domains (SOC2, HIPAA, HR, Finance, etc.)
- Can be adapted with domain-specific adjustments
- Predict control failure probability
- Map to specific controls when controls are identified
- Include sufficient detail in natural language questions for SQL generation

For each likelihood feature, provide:
1. Feature name following universal conventions (e.g., "historical_failure_rate", "control_drift_frequency", "evidence_quality_score")
2. Natural language question that includes SQL-relevant context:
   - Parameter names and source data fields (or control prioritization config defaults when controls are identified)
   - Parameter weights (0-1, typically 0.1-0.5)
   - Aggregation method (weighted_sum, least, max, geometric_mean, harmonic_mean, quadratic_mean)
   - Max values for normalization
   - Decay functions if time-based (with decay_rate and time_delta)
   - Whether any parameters are inverse (higher value = lower likelihood)
   - When controls are identified: mention using DEFAULT_CONTROL_PRIORITIZATION_CONFIGS.default_likelihood (1-5 scale, convert to 0-100), default_coverage_score, and default_has_coverage_gaps
3. Likelihood driver it measures (historical_failure, drift, evidence_quality, etc.)
4. Calculation method (how to calculate this likelihood input, including SQL function parameters)
5. Data sources (where measurement data comes from, or control prioritization configs when controls are identified)
6. Unit of measure (rate, score, count, percentage, etc.)
7. Ranges (low/medium/high likelihood values)
8. Cross-domain applicability (how it works for different frameworks)
9. Domain-specific adjustments (if needed for {domain_config.domain_name})
10. Control mapping (which identified controls this predicts, if controls are identified - use get_control_prioritization_config(control_id) to get defaults)
11. Predictive power explanation (why this driver predicts failure)
12. SQL function parameters (detailed breakdown of param_name, param_value source, param_weight, max_value, decay_function, inverse, etc.)
13. Control prioritization usage (how to use DEFAULT_CONTROL_PRIORITIZATION_CONFIGS when controls are identified)

For likelihood features, consider generating:
- Base likelihood features (e.g., "{{likelihood_type}}_likelihood")
- Active likelihood variants (with controls): "{{likelihood_type}}_likelihood_active"
- Inherent likelihood variants (without controls): "{{likelihood_type}}_likelihood_inherent"
- Overall likelihood: "raw_likelihood", "likelihood_active", "likelihood_inherent"

Generate likelihood features as JSON array with this structure:
[
    {{
        "feature_name": "raw_likelihood",
        "natural_language_question": "What is the overall raw likelihood score for {domain_config.entity_types[0] if domain_config.entity_types else 'entities'} combining critical vulnerabilities (weight 0.4, max 20, exponential decay over 30 days), patch compliance rate (weight 0.3, max 100, inverse true), and dwell time (weight 0.3, max 90, linear decay) using weighted_sum aggregation, scaled to 100?",
        "description": "Overall raw likelihood score without considering controls. Combines critical vulnerabilities with exponential decay, patch compliance (inverse), and dwell time with linear decay.",
        "likelihood_type": "overall",
        "feature_type": "float",
        "calculation_logic": "Weighted combination of all likelihood factors using calculate_likelihood_from_json with weighted_sum aggregation",
        "sql_function": "calculate_likelihood_from_json",
        "sql_parameters": {{
            "aggregation_method": "weighted_sum",
            "scale_to": 100.0,
            "normalization_method": "none",
            "parameters": [
                {{"param_name": "critical_vulns", "param_value": "critical_vuln_count", "param_weight": 0.4, "max_value": 20.0, "decay_function": "exponential", "decay_rate": 30.0, "time_delta": 45, "inverse": false}},
                {{"param_name": "patch_compliance", "param_value": "patch_compliance_rate", "param_weight": 0.3, "max_value": 100.0, "decay_function": "none", "inverse": true}},
                {{"param_name": "dwell_time", "param_value": "dwell_time_days", "param_weight": 0.3, "max_value": 90.0, "decay_function": "linear", "decay_rate": 90.0, "time_delta": 60, "inverse": false}}
            ]
        }},
        "control_prioritization_usage": "When controls are identified, can use DEFAULT_CONTROL_PRIORITIZATION_CONFIGS.default_likelihood (1-5 scale, convert to 0-100), default_coverage_score (0-1 scale), and default_has_coverage_gaps (bool, convert to score) as additional parameters",
        "related_features": [],
        "knowledge_based_reasoning": "Based on domain knowledge about likelihood assessment"
    }},
    {{
        "feature_name": "likelihood_active",
        "natural_language_question": "What is the active likelihood (with controls) for {domain_config.entity_types[0] if domain_config.entity_types else 'entities'} combining raw likelihood (weight 0.7, max 100) and control effectiveness (weight 0.3, max 100, inverse true) using weighted_sum aggregation?",
        "description": "Active likelihood considering current controls. Combines raw likelihood with control effectiveness adjustment.",
        "likelihood_type": "overall",
        "feature_type": "float",
        "calculation_logic": "Raw likelihood adjusted for active controls using calculate_likelihood_from_json",
        "sql_function": "calculate_likelihood_from_json",
        "sql_parameters": {{
            "aggregation_method": "weighted_sum",
            "scale_to": 100.0,
            "normalization_method": "none",
            "parameters": [
                {{"param_name": "raw_likelihood", "param_value": "raw_likelihood_score", "param_weight": 0.7, "max_value": 100.0, "decay_function": "none", "inverse": false}},
                {{"param_name": "control_effectiveness", "param_value": "control_effectiveness_score", "param_weight": 0.3, "max_value": 100.0, "decay_function": "none", "inverse": true}}
            ]
        }},
        "related_features": ["raw_likelihood"],
        "knowledge_based_reasoning": "Active likelihood with controls applied"
    }},
    {{
        "feature_name": "likelihood_inherent",
        "natural_language_question": "What is the inherent likelihood (without controls) for {domain_config.entity_types[0] if domain_config.entity_types else 'entities'} using historical failure rate (weight 0.5, max 100) and process volatility (weight 0.5, max 100) with weighted_sum aggregation?",
        "description": "Inherent likelihood without controls. Base likelihood baseline.",
        "likelihood_type": "overall",
        "feature_type": "float",
        "calculation_logic": "Base likelihood without considering controls using calculate_likelihood_from_json",
        "sql_function": "calculate_likelihood_from_json",
        "sql_parameters": {{
            "aggregation_method": "weighted_sum",
            "scale_to": 100.0,
            "normalization_method": "none",
            "parameters": [
                {{"param_name": "historical_failure_rate", "param_value": "historical_failure_rate", "param_weight": 0.5, "max_value": 100.0, "decay_function": "none", "inverse": false}},
                {{"param_name": "process_volatility", "param_value": "process_volatility_score", "param_weight": 0.5, "max_value": 100.0, "decay_function": "none", "inverse": false}}
            ]
        }},
        "related_features": ["raw_likelihood"],
        "knowledge_based_reasoning": "Inherent likelihood baseline"
    }}
]

Generate 7-10 likelihood features covering the universal likelihood drivers. Prioritize features that:
- Map to identified controls (if controls are identified)
- Work universally across compliance frameworks
- Can be calculated using available data
- Predict control failure probability

Example likelihood features:
- historical_failure_rate: Past failures per time period
- control_drift_frequency: Configuration changes from baseline
- evidence_quality_score: Completeness and currency of evidence
- process_volatility: Change frequency and stability
- human_dependency_score: Manual vs automated process ratio
- operational_load_factor: Scale and load metrics
- control_maturity_level: CMM-style maturity assessment"""

        features_text = "\n".join([
            f"- {f.get('feature_name', 'Unknown')}: {f.get('natural_language_question', f.get('calculation_logic', 'N/A'))}"
            for f in recommended_features[:10]
        ])
        
        impact_text = "\n".join([
            f"- {f.get('feature_name', f.get('question', 'Unknown'))}: {f.get('natural_language_question', f.get('question', 'N/A'))}"
            for f in impact_features
        ])
        
        knowledge_text = self._format_knowledge_documents(knowledge_documents)
        
        prompt = f"""
USER QUERY: {user_query}

ANALYTICAL INTENT:
{analytical_intent}

EXISTING FEATURES:
{features_text}

IMPACT FEATURES:
{impact_text}

KNOWLEDGE DOCUMENTS:
{knowledge_text}

DOMAIN CONTEXT:
- Entity Types: {', '.join(domain_config.entity_types) if domain_config.entity_types else 'N/A'}
- Severity Levels: {', '.join(domain_config.severity_levels) if domain_config.severity_levels else 'N/A'}
- Compliance Frameworks: {', '.join(domain_config.compliance_frameworks) if domain_config.compliance_frameworks else 'N/A'}

Generate likelihood features that are:
1. Domain-relevant: Appropriate for {domain_config.domain_name} domain
2. Knowledge-based: Derived from the knowledge documents provided
3. Context-aware: Consider the existing features, impact features, and analytical intent
4. Well-named: Use descriptive names following domain conventions (e.g., "{{likelihood_type}}_likelihood", with _active and _inherent variants)

Each feature must include: feature_name, natural_language_question, description, likelihood_type, feature_type (float), calculation_logic, sql_function, sql_parameters, related_features, and knowledge_based_reasoning.

CRITICAL: The natural_language_question must include enough detail for SQL generation:
- Explicitly mention parameter names, weights, max values
- Specify aggregation method (weighted_sum, least, max, geometric_mean, harmonic_mean, quadratic_mean)
- Include decay functions if time-based (with decay_rate and time_delta)
- Note if any parameters are inverse (higher value = lower likelihood)
- Mention normalization method if not 'none'

The sql_parameters field should provide a complete JSON structure that can be used directly with calculate_likelihood_from_json function, with parameter values referencing source data fields.

Focus on universal likelihood drivers that work across all compliance domains. For each driver, explain:
- How it predicts control failure
- Calculation method (including SQL function parameters)
- Data sources
- Cross-domain applicability (SOC2, HIPAA, HR, Finance examples)
- Control mapping (if controls are identified)
"""
        
        try:
            response = await track_llm_call(
                agent_name="LikelihoodFeatureGenerationAgent",
                llm=self.llm,
                messages=[
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=prompt)
                ],
                state=state,
                step_name="likelihood_feature_generation"
            )
            
            # Parse JSON response
            content = response.content if hasattr(response, 'content') else str(response)
            json_match = re.search(r'\[[\s\S]*\]', content)
            if json_match:
                likelihood_features = json.loads(json_match.group(0))
            else:
                likelihood_features = self._create_fallback_likelihood_features(domain_config)
            
            state["likelihood_features"] = likelihood_features
            state["messages"].append(AIMessage(
                content=f"Generated {len(likelihood_features)} likelihood feature questions",
                name="LikelihoodFeatureGenerationAgent"
            ))
            state["next_agent"] = "risk_feature_generation"  # Continue to risk features
            
        except Exception as e:
            logger.error(f"Error in LikelihoodFeatureGenerationAgent: {e}")
            state["likelihood_features"] = self._create_fallback_likelihood_features(domain_config)
            state["next_agent"] = "end"  # Stop here even on error
        
        return state
    
    def _format_knowledge_documents(self, knowledge_documents: List[Dict[str, Any]]) -> str:
        """Format knowledge documents for the prompt"""
        if not knowledge_documents:
            return "No relevant knowledge documents available."
        
        formatted = []
        for i, doc in enumerate(knowledge_documents, 1):
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})
            framework = metadata.get("framework", "")
            category = metadata.get("category", "")
            
            formatted.append(f"\n--- Knowledge Document {i} ---")
            if framework:
                formatted.append(f"Framework: {framework}")
            if category:
                formatted.append(f"Category: {category}")
            formatted.append(f"Content:\n{content}")
        
        return "\n".join(formatted)
    
    def _format_controls_for_likelihood(self, identified_controls: List[Dict[str, Any]]) -> str:
        """Format identified controls for likelihood feature generation"""
        if not identified_controls:
            return "No controls have been identified yet. Generate universal likelihood features that work across all compliance types."
        
        formatted = []
        formatted.append(f"\n=== IDENTIFIED CONTROLS ({len(identified_controls)} controls) ===")
        formatted.append("Generate likelihood features that predict failure for these controls:\n")
        
        for i, control in enumerate(identified_controls[:10], 1):  # Limit to 10 for prompt size
            formatted.append(f"{i}. {control.get('control_id', 'UNKNOWN')}: {control.get('control_name', 'N/A')}")
            formatted.append(f"   Category: {control.get('category', 'N/A')}")
            formatted.append(f"   Description: {control.get('description', 'N/A')[:150]}")
        
        formatted.append("\nFor each control, consider likelihood drivers:")
        formatted.append("- Historical failure rate (past audit findings, test failures)")
        formatted.append("- Control drift frequency (configuration changes)")
        formatted.append("- Evidence quality (missing, outdated evidence)")
        formatted.append("- Process volatility (change frequency)")
        formatted.append("- Human dependency (manual vs automated)")
        formatted.append("- Operational load (scale, volume)")
        formatted.append("- Control maturity (CMM-style assessment)")
        
        return "\n".join(formatted)
    
    def _create_fallback_likelihood_features(self, domain_config: DomainConfiguration) -> List[Dict[str, Any]]:
        """Create fallback likelihood features based on universal likelihood drivers"""
        entity_type = domain_config.entity_types[0] if domain_config.entity_types else "entity"
        return [
            {
                "feature_name": "historical_failure_rate",
                "natural_language_question": f"What is the historical failure rate for {entity_type.lower()}s?",
                "description": "Past failures per time period (failures in past 12 months / review periods)",
                "likelihood_type": "historical_failure",
                "likelihood_driver": "historical_failure",
                "feature_type": "float",
                "calculation_logic": "Count of failures in past 12 months divided by number of review periods",
                "related_features": [],
                "knowledge_based_reasoning": f"Universal historical failure rate for {domain_config.domain_name} domain"
            },
            {
                "feature_name": "control_drift_frequency",
                "natural_language_question": f"What is the control drift frequency for {entity_type.lower()}s?",
                "description": "Configuration changes from baseline",
                "likelihood_type": "drift",
                "likelihood_driver": "control_drift",
                "feature_type": "float",
                "calculation_logic": "Count of configuration changes from baseline per time period",
                "related_features": [],
                "knowledge_based_reasoning": f"Universal control drift frequency for {domain_config.domain_name} domain"
            },
            {
                "feature_name": "evidence_quality_score",
                "natural_language_question": f"What is the evidence quality score for {entity_type.lower()}s?",
                "description": "Completeness and currency of evidence",
                "likelihood_type": "evidence_quality",
                "likelihood_driver": "evidence_quality",
                "feature_type": "float",
                "calculation_logic": "Score based on missing, outdated, or incomplete evidence",
                "related_features": [],
                "knowledge_based_reasoning": f"Universal evidence quality score for {domain_config.domain_name} domain"
            }
        ]


class RiskFeatureGenerationAgent:
    """Agent that generates risk features as natural language questions based on knowledge, impact, and likelihood features"""
    
    def __init__(self, llm: BaseChatModel, domain_config: DomainConfiguration):
        self.llm = llm
        self.domain_config = domain_config
    
    def _get_domain_config_from_state(self, state: FeatureEngineeringState) -> DomainConfiguration:
        """Get domain config from state or use instance config"""
        domain_config_dict = state.get("domain_config")
        if domain_config_dict:
            return DomainConfiguration(**domain_config_dict)
        return self.domain_config
    
    def _get_risk_sql_function_context(self) -> str:
        """Get SQL function documentation for risk calculations"""
        return """
GENERIC RISK CALCULATION SQL FUNCTIONS:

NOTE: A generic risk calculation SQL function (calculate_risk_from_json) will be created to combine impact and likelihood scores.
For now, risk features should reference both impact and likelihood features and specify how they combine.

CONTROL PRIORITIZATION CONFIGS:
When controls are identified, you can use DEFAULT_CONTROL_PRIORITIZATION_CONFIGS from domain_config.py which provide:
- default_impact: str (1-5 scale) - Convert to 0-100 scale: (value * 20) - 20
- default_likelihood: str (1-5 scale) - Convert to 0-100 scale: (value * 20) - 20
- default_relevance_score, default_quality_score, default_coverage_score: floats (0.0-1.0)
- These can be used to calculate base risk when actual data is not available

RISK CALCULATION APPROACH:
Risk is typically calculated as: Risk = f(Impact, Likelihood)
Common formulas:
- Risk = sqrt(Impact × Likelihood)  // Non-linear, geometric mean
- Risk = (Impact × 0.6) + (Likelihood × 0.4)  // Weighted combination
- Risk = Impact × Likelihood  // Simple multiplication
- Risk = max(Impact, Likelihood)  // Worst case
- Risk = (Impact + Likelihood) / 2  // Average

When using control prioritization configs:
- Base Risk = f(default_impact_converted, default_likelihood_converted)
- Can also incorporate relevance_score, quality_score, coverage_score as contextual factors

CONTEXTUAL FACTORS (that modify base risk):
1. TEMPORAL FACTORS: Time since last review, seasonal patterns
2. ORGANIZATIONAL FACTORS: Control owner capability, team size/resources
3. DATA SENSITIVITY FACTORS: Data classification level, crown jewel relevance
4. POPULATION FACTORS: Population affected, population criticality

RISK FEATURE STRUCTURE:
Risk features should reference:
- Related impact features (by feature_name)
- Related likelihood features (by feature_name)
- Risk formula (how impact and likelihood combine)
- Contextual multipliers (if applicable)
- Aggregation method if combining multiple risk factors

IMPORTANT FOR NATURAL LANGUAGE QUESTIONS:
When generating risk features, include in the natural_language_question and description:
1. Which impact and likelihood features are being combined
2. Risk formula (sqrt(impact × likelihood), weighted combination, etc.)
3. Contextual factors if applicable (temporal, organizational, sensitivity, population)
4. Context multipliers and how they modify base risk
5. Final risk score range (typically 0-100)

Example natural language question with SQL context:
"What is the overall risk score combining raw_impact and raw_likelihood using sqrt(impact × likelihood) formula, 
with temporal multiplier (time_since_review factor 1.2), organizational multiplier (control_owner_capability factor 0.9), 
and sensitivity multiplier (data_classification_level factor 1.3), scaled to 100?"

Example with control prioritization:
"What is the overall risk score for identified controls using control prioritization config defaults 
(default_impact and default_likelihood converted from 1-5 scale to 0-100) combined with sqrt(impact × likelihood) formula, 
with relevance score multiplier (default_relevance_score factor), quality score multiplier (default_quality_score factor), 
and coverage gaps multiplier (default_has_coverage_gaps converted to factor), scaled to 100?"

This provides enough context for another agent to construct the SQL calculation once the generic risk function is available.
"""
    
    async def __call__(self, state: FeatureEngineeringState) -> FeatureEngineeringState:
        """Generate risk features incorporating contextual factors and universal risk framework"""
        
        domain_config = self._get_domain_config_from_state(state)
        recommended_features = state.get("recommended_features", [])
        knowledge_documents = state.get("knowledge_documents", [])
        impact_features = state.get("impact_features", [])
        likelihood_features = state.get("likelihood_features", [])
        identified_controls = state.get("identified_controls", [])
        user_query = state.get("user_query", "")
        analytical_intent = state.get("analytical_intent", {})
        compliance_framework = analytical_intent.get("compliance_framework", "").upper()
        
        # Format identified controls for prompt
        controls_info = self._format_controls_for_risk(identified_controls)
        
        system_prompt = f"""You are a data scientist specializing in risk assessment and contextual modeling for compliance.

Your task is to generate risk features that combine Impact × Likelihood with CONTEXTUAL FACTORS that modify risk assessment. Use a UNIVERSAL RISK FRAMEWORK that works across ALL compliance types (SOC2, HIPAA, HR, Finance, etc.).

{self._get_risk_sql_function_context()}

UNIVERSAL RISK CALCULATION:
Base Risk = Likelihood × Impact
Adjusted Risk = Base Risk × Context Multipliers

CONTEXTUAL FACTORS (that modify base risk):
1. TEMPORAL FACTORS:
   - Time since last review (staleness increases likelihood)
   - Seasonal patterns (peak business periods)
   
2. ORGANIZATIONAL FACTORS:
   - Control owner capability (higher capability = lower likelihood)
   - Team size/resources (under-resourced = higher likelihood)
   
3. DATA SENSITIVITY FACTORS:
   - Data classification level (higher sensitivity = higher impact)
   - Crown jewel relevance (critical systems = higher impact)
   
4. POPULATION FACTORS:
   - Population affected (larger = higher likelihood AND impact)
   - Population criticality (executives vs general staff)

DOMAIN CONTEXT:
- Domain: {domain_config.domain_name}
- Entity Types: {', '.join(domain_config.entity_types) if domain_config.entity_types else 'N/A'}
- Severity Levels: {', '.join(domain_config.severity_levels) if domain_config.severity_levels else 'N/A'}
- Compliance Frameworks: {', '.join(domain_config.compliance_frameworks) if domain_config.compliance_frameworks else 'N/A'}
- Target Framework: {compliance_framework}

{controls_info}

For risk features, use this framework:
1. Base Risk = Likelihood × Impact (or √(L × I) for non-linear)
2. Context Multipliers = Temporal × Organizational × Sensitivity × Population
3. Adjusted Risk = Base Risk × Context Multipliers

For each risk feature, provide:
1. Feature name following universal conventions (e.g., "base_risk", "adjusted_risk", "contextual_risk")
2. Natural language question that includes SQL-relevant context:
   - Which impact and likelihood features are being combined (by feature_name, or control prioritization config defaults when controls are identified)
   - Risk formula (sqrt(impact × likelihood), weighted combination, etc.)
   - Contextual factors if applicable (temporal, organizational, sensitivity, population)
   - Context multipliers and how they modify base risk
   - Final risk score range (typically 0-100)
   - When controls are identified: mention using DEFAULT_CONTROL_PRIORITIZATION_CONFIGS.default_impact and default_likelihood (both 1-5 scale, convert to 0-100) and default_relevance_score, default_quality_score, default_coverage_score as contextual multipliers
3. Risk calculation formula (how Impact and Likelihood combine, with explicit formula)
4. Contextual adjustments (which contextual factors apply and how, with multiplier values)
5. Control mapping (which identified controls this risk applies to, if controls are identified - use get_control_prioritization_config(control_id) to get defaults)
6. Cross-domain applicability (how it works for different frameworks)
7. Risk classification (how to interpret the risk score - low/medium/high)
8. SQL calculation context (references to impact_features and likelihood_features, risk formula, contextual multipliers)
9. Control prioritization usage (how to use DEFAULT_CONTROL_PRIORITIZATION_CONFIGS when controls are identified to calculate base risk and contextual multipliers)

Generate risk features as JSON array with this structure:
[
    {{
        "feature_name": "raw_risk",
        "natural_language_question": "What is the raw risk score combining raw_impact and raw_likelihood for {domain_config.entity_types[0] if domain_config.entity_types else 'entities'} using sqrt(impact × likelihood) formula, scaled to 100?",
        "description": "Overall raw risk score combining raw impact and raw likelihood using geometric mean (square root) formula",
        "risk_type": "overall",
        "feature_type": "float",
        "risk_formula": "sqrt(raw_impact * raw_likelihood)",
        "calculation_logic": "Square root of (raw_impact multiplied by raw_likelihood) using sqrt(impact × likelihood) formula",
        "sql_calculation": "sqrt(raw_impact * raw_likelihood) where raw_impact and raw_likelihood are feature names from impact_features and likelihood_features",
        "related_impact_features": ["raw_impact"],
        "related_likelihood_features": ["raw_likelihood"],
        "contextual_factors": [],
        "control_prioritization_usage": "When controls are identified, can use DEFAULT_CONTROL_PRIORITIZATION_CONFIGS.default_impact and default_likelihood (both 1-5 scale, convert to 0-100) to calculate base risk, and default_relevance_score, default_quality_score, default_coverage_score as contextual multipliers",
        "knowledge_based_reasoning": "Based on risk calculation best practices from knowledge documents"
    }},
    {{
        "feature_name": "effective_risk",
        "natural_language_question": "What is the effective risk score combining effective_impact and effective_likelihood for {domain_config.entity_types[0] if domain_config.entity_types else 'entities'} using sqrt(impact × likelihood) formula, with temporal multiplier (time_since_review factor 1.2), scaled to 100?",
        "description": "Effective risk score after controls, combining effective impact and effective likelihood with temporal context multiplier",
        "risk_type": "effective",
        "feature_type": "float",
        "risk_formula": "sqrt(effective_impact * effective_likelihood) * temporal_multiplier",
        "calculation_logic": "Square root of (effective_impact multiplied by effective_likelihood) multiplied by temporal context factor",
        "sql_calculation": "sqrt(effective_impact * effective_likelihood) * (1.0 + (time_since_review_days / 365.0) * 0.2) where effective_impact and effective_likelihood are feature names",
        "related_impact_features": ["effective_impact"],
        "related_likelihood_features": ["effective_likelihood"],
        "contextual_factors": [
            {{"factor_name": "temporal", "factor_source": "time_since_review_days", "multiplier_formula": "1.0 + (time_since_review_days / 365.0) * 0.2", "description": "Temporal multiplier increases risk by 20% per year since last review"}}
        ],
        "knowledge_based_reasoning": "Effective risk considering controls and mitigations with temporal context"
    }},
    {{
        "feature_name": "contextual_risk",
        "natural_language_question": "What is the contextual risk score combining raw_impact and raw_likelihood using sqrt(impact × likelihood) formula, with temporal multiplier (time_since_review factor 1.2), organizational multiplier (control_owner_capability factor 0.9), sensitivity multiplier (data_classification_level factor 1.3), and population multiplier (affected_population_count factor 1.1), scaled to 100?",
        "description": "Context-adjusted risk score with all contextual factors applied",
        "risk_type": "contextual",
        "feature_type": "float",
        "risk_formula": "sqrt(raw_impact * raw_likelihood) * temporal_mult * org_mult * sensitivity_mult * population_mult",
        "calculation_logic": "Base risk multiplied by all contextual multipliers",
        "sql_calculation": "sqrt(raw_impact * raw_likelihood) * temporal_mult * org_mult * sensitivity_mult * population_mult",
        "related_impact_features": ["raw_impact"],
        "related_likelihood_features": ["raw_likelihood"],
        "contextual_factors": [
            {{"factor_name": "temporal", "factor_source": "time_since_review_days", "multiplier_formula": "1.0 + (time_since_review_days / 365.0) * 0.2"}},
            {{"factor_name": "organizational", "factor_source": "control_owner_capability_score", "multiplier_formula": "1.0 - (control_owner_capability_score / 100.0) * 0.1"}},
            {{"factor_name": "sensitivity", "factor_source": "data_classification_level", "multiplier_formula": "1.0 + (data_classification_level / 5.0) * 0.3"}},
            {{"factor_name": "population", "factor_source": "affected_population_count", "multiplier_formula": "1.0 + LEAST(affected_population_count / 1000.0, 0.1)"}}
        ],
        "knowledge_based_reasoning": "Contextual risk with all modifying factors"
    }}
]

Generate 3-5 risk features covering:
1. Base risk (Likelihood × Impact)
2. Context-adjusted risk (with temporal, organizational, sensitivity, population factors)
3. Control-specific risk (if controls are identified, map risk to specific controls)

Prioritize features that:
- Work universally across compliance frameworks
- Incorporate contextual factors appropriately
- Map to identified controls (if controls are identified)
- Can be calculated using available impact and likelihood features

Example risk features:
- base_risk: Base calculation (Likelihood × Impact)
- adjusted_risk: Base risk adjusted for contextual factors
- control_risk: Risk score for specific identified controls"""

        features_text = "\n".join([
            f"- {f.get('feature_name', 'Unknown')}: {f.get('natural_language_question', f.get('calculation_logic', 'N/A'))}"
            for f in recommended_features[:10]
        ])
        
        impact_text = "\n".join([
            f"- {f.get('feature_name', f.get('question', 'Unknown'))}: {f.get('natural_language_question', f.get('question', 'N/A'))}"
            for f in impact_features
        ])
        
        likelihood_text = "\n".join([
            f"- {f.get('feature_name', f.get('question', 'Unknown'))}: {f.get('natural_language_question', f.get('question', 'N/A'))}"
            for f in likelihood_features
        ])
        
        knowledge_text = self._format_knowledge_documents(knowledge_documents)
        
        prompt = f"""
USER QUERY: {user_query}

ANALYTICAL INTENT:
{analytical_intent}

EXISTING FEATURES:
{features_text}

IMPACT FEATURES:
{impact_text}

LIKELIHOOD FEATURES:
{likelihood_text}

KNOWLEDGE DOCUMENTS:
{knowledge_text}

DOMAIN CONTEXT:
- Entity Types: {', '.join(domain_config.entity_types) if domain_config.entity_types else 'N/A'}
- Severity Levels: {', '.join(domain_config.severity_levels) if domain_config.severity_levels else 'N/A'}
- Compliance Frameworks: {', '.join(domain_config.compliance_frameworks) if domain_config.compliance_frameworks else 'N/A'}

Generate risk features that are:
1. Domain-relevant: Appropriate for {domain_config.domain_name} domain
2. Knowledge-based: Derived from the knowledge documents provided
3. Context-aware: Consider the existing features, impact features, likelihood features, and analytical intent
4. Well-named: Use descriptive names following domain conventions (e.g., "raw_risk", "effective_risk", "{{risk_type}}_risk")
5. Properly combined: Combine appropriate impact and likelihood features based on domain knowledge

Each feature must include: feature_name, natural_language_question, description, risk_type, feature_type (float), risk_formula, calculation_logic, sql_calculation, related_impact_features, related_likelihood_features, contextual_factors, and knowledge_based_reasoning.

CRITICAL: The natural_language_question must include enough detail for SQL generation:
- Explicitly mention which impact and likelihood features are being combined (by feature_name)
- Specify risk formula (sqrt(impact × likelihood), weighted combination, etc.)
- Include contextual factors if applicable (temporal, organizational, sensitivity, population)
- Mention context multipliers and their formulas
- Note final risk score range (typically 0-100)

The sql_calculation field should provide SQL expression that references impact_features and likelihood_features by name, includes the risk formula, and applies contextual multipliers.

Focus on universal risk calculations that:
- Combine Impact × Likelihood appropriately
- Incorporate contextual factors (temporal, organizational, sensitivity, population)
- Work across all compliance domains (SOC2, HIPAA, HR, Finance)
- Map to identified controls (if controls are identified)
- Use contextual adjustments: Adjusted Risk = Base Risk × Context Multipliers

For each risk feature, explain:
- How Impact and Likelihood combine (formula with explicit SQL expression)
- Which contextual factors apply
- How context modifies the base risk
- Control mapping (if controls are identified)
- Cross-domain examples (SOC2, HIPAA, HR, Finance)
"""
        
        try:
            response = await track_llm_call(
                agent_name="RiskFeatureGenerationAgent",
                llm=self.llm,
                messages=[
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=prompt)
                ],
                state=state,
                step_name="risk_feature_generation"
            )
            
            # Parse JSON response
            content = response.content if hasattr(response, 'content') else str(response)
            json_match = re.search(r'\[[\s\S]*\]', content)
            if json_match:
                risk_features = json.loads(json_match.group(0))
            else:
                risk_features = self._create_fallback_risk_features(domain_config)
            
            state["risk_features"] = risk_features
            state["messages"].append(AIMessage(
                content=f"Generated {len(risk_features)} risk feature questions",
                name="RiskFeatureGenerationAgent"
            ))
            state["next_agent"] = "create_reasoning_plan"
            
        except Exception as e:
            logger.error(f"Error in RiskFeatureGenerationAgent: {e}")
            state["risk_features"] = self._create_fallback_risk_features(domain_config)
            state["next_agent"] = "create_reasoning_plan"
        
        return state
    
    def _format_knowledge_documents(self, knowledge_documents: List[Dict[str, Any]]) -> str:
        """Format knowledge documents for the prompt"""
        if not knowledge_documents:
            return "No relevant knowledge documents available."
        
        formatted = []
        for i, doc in enumerate(knowledge_documents, 1):
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})
            framework = metadata.get("framework", "")
            category = metadata.get("category", "")
            
            formatted.append(f"\n--- Knowledge Document {i} ---")
            if framework:
                formatted.append(f"Framework: {framework}")
            if category:
                formatted.append(f"Category: {category}")
            formatted.append(f"Content:\n{content}")
        
        return "\n".join(formatted)
    
    def _format_controls_for_risk(self, identified_controls: List[Dict[str, Any]]) -> str:
        """Format identified controls for risk feature generation"""
        if not identified_controls:
            return "No controls have been identified yet. Generate universal risk features that work across all compliance types."
        
        formatted = []
        formatted.append(f"\n=== IDENTIFIED CONTROLS ({len(identified_controls)} controls) ===")
        formatted.append("Generate risk features that calculate risk for these controls:\n")
        
        for i, control in enumerate(identified_controls[:10], 1):  # Limit to 10 for prompt size
            formatted.append(f"{i}. {control.get('control_id', 'UNKNOWN')}: {control.get('control_name', 'N/A')}")
            formatted.append(f"   Category: {control.get('category', 'N/A')}")
            formatted.append(f"   Description: {control.get('description', 'N/A')[:150]}")
        
        formatted.append("\nFor each control, calculate risk using:")
        formatted.append("- Base Risk = Likelihood × Impact")
        formatted.append("- Contextual adjustments (temporal, organizational, sensitivity, population)")
        formatted.append("- Adjusted Risk = Base Risk × Context Multipliers")
        formatted.append("- Risk classification (low/medium/high based on score)")
        
        return "\n".join(formatted)
    
    def _create_fallback_risk_features(self, domain_config: Optional[DomainConfiguration] = None) -> List[Dict[str, Any]]:
        """Create fallback risk features based on universal risk framework"""
        entity_type = domain_config.entity_types[0] if domain_config and domain_config.entity_types else "entity"
        domain_name = domain_config.domain_name if domain_config else "compliance"
        
        return [
            {
                "feature_name": "base_risk",
                "natural_language_question": f"What is the base risk score (Likelihood × Impact) for {entity_type.lower()}s?",
                "description": "Base risk calculation combining likelihood and impact",
                "risk_type": "base",
                "feature_type": "float",
                "risk_formula": "likelihood_score * impact_score",
                "calculation_logic": "Multiply likelihood score by impact score",
                "related_impact_features": ["regulatory_severity_impact", "financial_impact"],
                "related_likelihood_features": ["historical_failure_rate", "control_drift_frequency"],
                "knowledge_based_reasoning": f"Universal base risk calculation for {domain_name} domain"
            },
            {
                "feature_name": "adjusted_risk",
                "natural_language_question": f"What is the context-adjusted risk score for {entity_type.lower()}s?",
                "description": "Risk adjusted for contextual factors (temporal, organizational, sensitivity, population)",
                "risk_type": "adjusted",
                "feature_type": "float",
                "risk_formula": "base_risk * temporal_multiplier * organizational_multiplier * sensitivity_multiplier * population_multiplier",
                "calculation_logic": "Base risk multiplied by contextual factor multipliers",
                "related_impact_features": ["regulatory_severity_impact", "financial_impact"],
                "related_likelihood_features": ["historical_failure_rate", "control_drift_frequency"],
                "contextual_factors": ["temporal", "organizational", "sensitivity", "population"],
                "knowledge_based_reasoning": f"Universal context-adjusted risk for {domain_name} domain"
            }
        ]


class ReasoningPlanAgent:
    """Agent that creates a step-by-step analytical reasoning plan"""
    
    def __init__(self, llm: BaseChatModel, domain_config: DomainConfiguration):
        self.llm = llm
        self.domain_config = domain_config
    
    def _get_domain_config_from_state(self, state: FeatureEngineeringState) -> DomainConfiguration:
        """Get domain config from state or use instance config"""
        domain_config_dict = state.get("domain_config")
        if domain_config_dict:
            return DomainConfiguration(**domain_config_dict)
        return self.domain_config
        
    async def __call__(self, state: FeatureEngineeringState) -> FeatureEngineeringState:
        """Generate comprehensive reasoning plan"""
        
        # Get domain config from state or use instance config
        domain_config = self._get_domain_config_from_state(state)
        
        intent = state["analytical_intent"]
        features = state["recommended_features"]
        schemas = state["relevant_schemas"]
        schema_registry = state.get("schema_registry", {})
        knowledge_documents = state.get("knowledge_documents", [])
        
        system_prompt = """You are an analytics architect creating a detailed reasoning plan.

Create a step-by-step plan that explains:
1. Data extraction steps (which schemas to query, join conditions)
2. Feature calculation steps (in dependency order)
3. Aggregation steps (grouping and summarization)
4. Quality checks and validations
5. Output format

The plan should be:
- Executable (could be translated to SQL/Python)
- Dependency-aware (calculate base features before derived ones)
- Quality-focused (include data validation steps)
- Time-series aware (handle temporal features correctly)
- Compliance-aware (incorporate compliance framework requirements if applicable)

Format as a numbered plan with clear sections."""

        schema_info = self._format_schema_info(schema_registry, schemas)
        knowledge_info = self._format_knowledge_documents(knowledge_documents)
        
        # Build context from domain configuration
        context_items = []
        default_context = domain_config.default_context
        
        # Add domain-specific context
        for key, value in default_context.items():
            if isinstance(value, bool):
                context_items.append(f"- {key.replace('_', ' ').title()}: {value}")
            elif isinstance(value, (int, float)):
                context_items.append(f"- {key.replace('_', ' ').title()}: {value}")
            else:
                context_items.append(f"- {key.replace('_', ' ').title()}: {value}")
        
        # Add default items if not in config
        if not context_items:
            context_items.append(f"- Features are time-series based: {default_context.get('features_are_time_series', True)}")

        context = f"""
ANALYTICAL INTENT:
{intent}

RECOMMENDED FEATURES:
{features}

AVAILABLE SCHEMAS:
{schema_info}

RELEVANT KNOWLEDGE:
{knowledge_info}

KNOWN CONTEXT:
{chr(10).join(context_items)}
"""

        response = await track_llm_call(
            agent_name="ReasoningPlanAgent",
            llm=self.llm,
            messages=[
                SystemMessage(content=system_prompt),
                HumanMessage(content=context)
            ],
            state=state,
            step_name="create_reasoning_plan"
        )
        
        reasoning_plan = {
            "plan_id": f"plan_{hash(state['user_query']) % 10000}",
            "objective": intent.get("primary_goal", ""),
            "steps": self._parse_plan_steps(response.content),
            "raw_plan": response.content
        }
        
        state["reasoning_plan"] = reasoning_plan
        state["messages"].append(AIMessage(
            content=f"Created reasoning plan with {len(reasoning_plan['steps'])} steps",
            name="ReasoningPlanAgent"
        ))
        state["next_agent"] = "end"
        
        return state
    
    def _format_knowledge_documents(self, knowledge_documents: List[Dict[str, Any]]) -> str:
        """Format knowledge documents for the prompt"""
        if not knowledge_documents:
            return "No relevant knowledge documents available."
        
        formatted = []
        for i, doc in enumerate(knowledge_documents, 1):
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})
            framework = metadata.get("framework", "")
            category = metadata.get("category", "")
            
            formatted.append(f"\n--- Knowledge Document {i} ---")
            if framework:
                formatted.append(f"Framework: {framework}")
            if category:
                formatted.append(f"Category: {category}")
            formatted.append(f"Content:\n{content}")
        
        return "\n".join(formatted)
    
    def _format_schema_info(self, schema_registry: Dict[str, Any], relevant_schemas: List[str]) -> str:
        """Format schema information for the prompt"""
        if not schema_registry:
            return ", ".join(relevant_schemas) if relevant_schemas else "No schemas available"
        
        info_parts = []
        for schema_name in relevant_schemas:
            if schema_name in schema_registry:
                schema_info = schema_registry[schema_name]
                desc = schema_info.get("description", "")
                fields = schema_info.get("key_fields", [])
                info_parts.append(f"{schema_name}: {desc} (Fields: {', '.join(fields[:10])})")
            else:
                info_parts.append(schema_name)
        
        return "\n".join(info_parts) if info_parts else ", ".join(relevant_schemas)
    
    def _parse_plan_steps(self, content: str) -> List[Dict[str, Any]]:
        """Parse plan steps from LLM response"""
        steps = []
        lines = content.split("\n")
        
        current_step = None
        for line in lines:
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("Step")):
                if current_step:
                    steps.append(current_step)
                current_step = {"description": line, "details": []}
            elif current_step and line:
                current_step["details"].append(line)
        
        if current_step:
            steps.append(current_step)
        
        return steps


# ============================================================================
# FEATURE DEPENDENCY AGENT
# ============================================================================

class FeatureDependencyAgent:
    """Agent that identifies feature dependencies and calculation order"""
    
    def __init__(self, llm: BaseChatModel, domain_config: DomainConfiguration):
        self.llm = llm
        self.domain_config = domain_config
    
    def _get_domain_config_from_state(self, state: FeatureEngineeringState) -> DomainConfiguration:
        """Get domain config from state or use instance config"""
        domain_config_dict = state.get("domain_config")
        if domain_config_dict:
            return DomainConfiguration(**domain_config_dict)
        return self.domain_config
    
    async def __call__(self, state: FeatureEngineeringState) -> FeatureEngineeringState:
        """Analyze all features and identify dependencies, chains, and calculation order"""
        
        domain_config = self._get_domain_config_from_state(state)
        features = state.get("recommended_features", [])
        user_query = state.get("user_query", "")
        analytical_intent = state.get("analytical_intent", {})
        
        if not features:
            logger.warning("No features to analyze for dependencies")
            state["feature_dependencies"] = {
                "calculation_sequence": [],
                "dependency_chains": [],
                "total_steps": 0
            }
            state["next_agent"] = "relevancy_scoring"
            return state
        
        system_prompt = f"""You are an expert at analyzing feature dependencies and calculation order for {domain_config.domain_description or domain_config.domain_name} analytics.

Your task is to:
1. Analyze all recommended features
2. Identify which features depend on other features (e.g., derived features depend on base features)
3. Create natural language chains of questions/operations that need to be calculated in order
4. Determine the optimal calculation sequence (which features can be calculated in parallel, which must be sequential)
5. Identify base features (those with no dependencies)

For each feature, identify:
- Direct dependencies (other features this feature needs)
- Data dependencies (schemas/tables required)
- Calculation order (when this feature should be calculated)
- Natural language chain (sequence of questions/operations)

Return a structured dependency graph with:
- All features with their dependencies
- Calculation sequence (groups of features that can be calculated together)
- Dependency chains (sequential chains of calculations)
- Total number of calculation steps required"""

        features_text = "\n".join([
            f"{i+1}. {f.get('feature_name', 'Unknown')}: {f.get('calculation_logic', '')} "
            f"(Type: {f.get('feature_type', '')}, Schemas: {f.get('required_schemas', [])})"
            for i, f in enumerate(features)
        ])
        
        prompt = f"""
USER QUERY: {user_query}

ANALYTICAL INTENT:
{analytical_intent}

RECOMMENDED FEATURES:
{features_text}

Analyze the dependencies and create a dependency graph. Consider:
- Base features (counts, aggregations from raw data) should be calculated first
- Derived features (ratios, percentages, time-series features) depend on base features
- Features using the same schemas can often be calculated in parallel
- Time-series features may depend on temporal aggregations

Return your analysis as JSON matching this structure:
{{
    "features": [
        {{
            "feature_name": "feature_name",
            "depends_on": ["dependency1", "dependency2"],
            "calculation_order": 1,
            "natural_language_chain": ["question1", "question2"],
            "data_dependencies": ["schema1", "schema2"],
            "is_base_feature": true/false
        }}
    ],
    "calculation_sequence": [
        ["feature1", "feature2"],  // Can be calculated in parallel
        ["feature3"]  // Must wait for feature1 and feature2
    ],
    "dependency_chains": [
        ["feature1", "feature3", "feature5"]  // Sequential chain
    ],
    "total_steps": 3
}}
"""
        
        try:
            response = await track_llm_call(
                agent_name="FeatureDependencyAgent",
                llm=self.llm,
                messages=[
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=prompt)
                ],
                state=state,
                step_name="feature_dependency"
            )
            
            # Parse JSON response
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Extract JSON from response - try multiple strategies
            dependency_data = None
            
            # Strategy 1: Try to find JSON object in response
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                try:
                    dependency_data = json.loads(json_match.group(0))
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON parsing failed for extracted match: {e}")
                    # Try to fix common JSON issues
                    json_str = json_match.group(0)
                    # Remove comments (// and /* */)
                    json_str = re.sub(r'//.*?$', '', json_str, flags=re.MULTILINE)
                    json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
                    # Fix trailing commas
                    json_str = re.sub(r',\s*}', '}', json_str)
                    json_str = re.sub(r',\s*]', ']', json_str)
                    try:
                        dependency_data = json.loads(json_str)
                    except json.JSONDecodeError as e2:
                        logger.warning(f"JSON parsing failed even after cleaning: {e2}")
                        logger.debug(f"Problematic JSON string (first 500 chars): {json_str[:500]}")
            
            # Strategy 2: Try to find JSON array
            if dependency_data is None:
                json_array_match = re.search(r'\[[\s\S]*\]', content)
                if json_array_match:
                    try:
                        array_data = json.loads(json_array_match.group(0))
                        # Convert array to expected format
                        if isinstance(array_data, list):
                            dependency_data = {
                                "features": array_data,
                                "calculation_sequence": [],
                                "dependency_chains": [],
                                "total_steps": len(array_data)
                            }
                    except json.JSONDecodeError:
                        pass
            
            # Strategy 3: Fallback to basic structure
            if dependency_data is None:
                logger.warning("Could not parse JSON from response, using fallback structure")
                dependency_data = self._create_fallback_dependencies(features)
            
            # Validate and structure the dependency data
            dependency_graph = self._validate_dependency_graph(dependency_data, features)
            
            # Add dependency information directly to recommended_features instead of duplicating
            # Create a map of feature_name -> dependency info
            dependency_map = {feat.get('feature_name'): feat for feat in dependency_graph.get('features', [])}
            
            # Update recommended_features with dependency information
            updated_features = []
            for feature in features:
                feature_name = feature.get('feature_name', '')
                dep_info = dependency_map.get(feature_name, {})
                
                # Add dependency fields directly to the feature
                feature['depends_on'] = dep_info.get('depends_on', [])
                feature['calculation_order'] = dep_info.get('calculation_order', None)
                feature['is_base_feature'] = dep_info.get('is_base_feature', len(dep_info.get('depends_on', [])) == 0)
                
                updated_features.append(feature)
            
            state["recommended_features"] = updated_features
            
            # Store only the calculation sequence and dependency chains (not full feature objects)
            state["feature_dependencies"] = {
                "calculation_sequence": dependency_graph.get('calculation_sequence', []),
                "dependency_chains": dependency_graph.get('dependency_chains', []),
                "total_steps": dependency_graph.get('total_steps', 0)
            }
            
            state["messages"].append(AIMessage(
                content=f"Identified dependencies for {len(features)} features with {dependency_graph.get('total_steps', 0)} calculation steps",
                name="FeatureDependencyAgent"
            ))
            state["next_agent"] = "relevancy_scoring"
            
        except Exception as e:
            logger.error(f"Error in FeatureDependencyAgent: {e}")
            # Fallback to basic structure
            state["feature_dependencies"] = self._create_fallback_dependencies(features)
            # Route to relevancy_scoring (normal flow) even on error
            state["next_agent"] = "relevancy_scoring"
        
        return state
    
    def _create_fallback_dependencies(self, features: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a basic dependency structure when parsing fails"""
        feature_list = []
        for i, f in enumerate(features):
            feature_name = f.get('feature_name', f'feature_{i+1}')
            feature_list.append({
                "feature_name": feature_name,
                "depends_on": [],
                "calculation_order": i + 1,
                "is_base_feature": True
            })
        
        return {
            "features": feature_list,
            "calculation_sequence": [[f.get('feature_name', f'feature_{i+1}')] for i, f in enumerate(features)],
            "dependency_chains": [[f.get('feature_name', f'feature_{i+1}')] for f in features],
            "total_steps": len(features)
        }
    
    def _validate_dependency_graph(self, data: Dict[str, Any], features: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate and fix dependency graph structure"""
        feature_names = {f.get('feature_name', f'feature_{i}') for i, f in enumerate(features)}
        
        # Validate features
        validated_features = []
        for feat in data.get('features', []):
            feat_name = feat.get('feature_name', '')
            if feat_name in feature_names:
                # Validate dependencies exist
                depends_on = [d for d in feat.get('depends_on', []) if d in feature_names]
                validated_features.append({
                    **feat,
                    'depends_on': depends_on
                })
        
        return {
            "features": validated_features,
            "calculation_sequence": data.get('calculation_sequence', []),
            "dependency_chains": data.get('dependency_chains', []),
            "total_steps": data.get('total_steps', len(validated_features))
        }


# ============================================================================
# RELEVANCY SCORING AGENT
# ============================================================================

class RelevancyScoringAgent:
    """Agent that validates outputs against expectations using GROQ/LLM and provides relevance scores"""
    
    def __init__(
        self, 
        llm: BaseChatModel, 
        domain_config: DomainConfiguration,
        validation_llm: Optional[BaseChatModel] = None  # Optional separate LLM for validation (e.g., GROQ)
    ):
        self.llm = llm
        self.validation_llm = validation_llm or llm  # Use separate validation LLM if provided, otherwise use main LLM
        self.domain_config = domain_config
    
    def _get_domain_config_from_state(self, state: FeatureEngineeringState) -> DomainConfiguration:
        """Get domain config from state or use instance config"""
        domain_config_dict = state.get("domain_config")
        if domain_config_dict:
            return DomainConfiguration(**domain_config_dict)
        return self.domain_config
    
    async def __call__(self, state: FeatureEngineeringState) -> FeatureEngineeringState:
        """Score relevance of features and overall output against goals and examples"""
        
        domain_config = self._get_domain_config_from_state(state)
        user_query = state.get("user_query", "")
        analytical_intent = state.get("analytical_intent", {})
        features = state.get("recommended_features", [])
        feature_dependencies = state.get("feature_dependencies", {})
        validation_expectations = state.get("validation_expectations", [])
        
        system_prompt = f"""You are an expert quality evaluator using GRPO (Group Relative Policy Optimization) methodology to assess feature engineering outputs for {domain_config.domain_description or domain_config.domain_name} analytics.

Your task is to:
1. Evaluate how well the recommended features match the user's goal
2. Compare features against provided examples/expectations (if available)
3. Score each feature on multiple dimensions (relevance, completeness, feasibility, clarity, technical accuracy)
4. Calculate overall relevance scores
5. Provide actionable feedback and improvement suggestions

Use GRPO methodology:
- Score each dimension from 0.0 to 1.0
- Apply weighted scoring based on importance
- Compare against reference standards (examples/expectations)
- Provide group-relative scoring (how does this compare to similar features?)

Dimensions to evaluate:
- Relevance: How relevant is this feature to the user's goal?
- Completeness: How complete is the feature definition?
- Feasibility: How feasible is this feature given available data?
- Clarity: How clear and actionable is the feature?
- Technical Accuracy: How technically accurate is the calculation logic?
- Goal Alignment: How well does this align with the analytical intent?
- Example Alignment: How well does this match provided examples (if available)?

Return structured scores for each feature and overall output."""

        features_text = "\n".join([
            f"{i+1}. {f.get('feature_name', 'Unknown')}: {f.get('calculation_logic', '')} "
            f"(Context: {f.get('business_context', '')})"
            for i, f in enumerate(features)
        ])
        
        expectations_text = ""
        if validation_expectations:
            expectations_text = "\n\nVALIDATION EXPECTATIONS/EXAMPLES:\n"
            for i, exp in enumerate(validation_expectations, 1):
                expectations_text += f"{i}. {exp}\n"
        
        prompt = f"""
USER QUERY: {user_query}

ANALYTICAL INTENT:
{analytical_intent}

RECOMMENDED FEATURES:
{features_text}

FEATURE DEPENDENCIES:
{feature_dependencies}
{expectations_text}

Evaluate the relevance and quality of these features. For each feature, provide:
1. Individual dimension scores (relevance, completeness, feasibility, clarity, technical accuracy)
2. Overall feature score (weighted average)
3. Goal alignment score (how well it matches the user's goal)
4. Example alignment score (how well it matches examples, if provided)
5. Confidence in the score
6. Feedback and improvement suggestions

Return your evaluation as JSON matching this structure:
{{
    "overall_score": 0.0-1.0,
    "overall_confidence": 0.0-1.0,
    "feature_scores": [
        {{
            "feature_name": "feature_name",
            "score": 0.0-1.0,
            "confidence": 0.0-1.0,
            "dimensions": {{
                "relevance": 0.0-1.0,
                "completeness": 0.0-1.0,
                "feasibility": 0.0-1.0,
                "clarity": 0.0-1.0,
                "technical_accuracy": 0.0-1.0
            }},
            "matches_goal": true/false,
            "matches_examples": true/false,
            "feedback": "detailed feedback",
            "improvement_suggestions": ["suggestion1", "suggestion2"]
        }}
    ],
    "goal_alignment": 0.0-1.0,
    "example_alignment": 0.0-1.0,
    "quality_metrics": {{
        "average_feature_score": 0.0-1.0,
        "consistency": 0.0-1.0,
        "coverage": 0.0-1.0
    }},
    "recommendations": ["recommendation1", "recommendation2"]
}}
"""
        
        try:
            response = await track_llm_call(
                agent_name="RelevancyScoringAgent",
                llm=self.validation_llm,
                messages=[
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=prompt)
                ],
                state=state,
                step_name="relevancy_scoring"
            )
            
            # Parse JSON response
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                scoring_data = json.loads(json_match.group(0))
            else:
                # Fallback: create basic scoring structure
                scoring_data = self._create_fallback_scores(features)
            
            # Validate scoring data
            scoring_result = self._validate_scoring_result(scoring_data, features)
            
            # Add recommendation scores directly to recommended_features instead of separate structure
            # Create a map of feature_name -> score info
            feature_scores_map = {score.get('feature_name'): score for score in scoring_result.get('feature_scores', [])}
            
            # Update recommended_features with score information
            updated_features = []
            for feature in features:
                feature_name = feature.get('feature_name', '')
                score_info = feature_scores_map.get(feature_name, {})
                
                # Add score fields directly to the feature
                feature['recommendation_score'] = score_info.get('score', None)
                feature['recommendation_confidence'] = score_info.get('confidence', None)
                feature['score_dimensions'] = score_info.get('dimensions', None)
                feature['matches_goal'] = score_info.get('matches_goal', None)
                feature['matches_examples'] = score_info.get('matches_examples', None)
                feature['score_feedback'] = score_info.get('feedback', None)
                feature['improvement_suggestions'] = score_info.get('improvement_suggestions', [])
                
                updated_features.append(feature)
            
            state["recommended_features"] = updated_features
            
            # Store only overall scores and quality metrics (not per-feature scores)
            state["relevance_scores"] = {
                "overall_score": scoring_result.get('overall_score', 0.0),
                "overall_confidence": scoring_result.get('overall_confidence', 0.0),
                "goal_alignment": scoring_result.get('goal_alignment', 0.0),
                "example_alignment": scoring_result.get('example_alignment', 0.0),
                "quality_metrics": scoring_result.get('quality_metrics', {}),
                "recommendations": scoring_result.get('recommendations', [])
            }
            
            state["messages"].append(AIMessage(
                content=f"Calculated relevance scores: Overall={scoring_result.get('overall_score', 0.0):.2f}, "
                       f"Goal Alignment={scoring_result.get('goal_alignment', 0.0):.2f}",
                name="RelevancyScoringAgent"
            ))
            state["next_agent"] = "end"
            
        except Exception as e:
            logger.error(f"Error in RelevancyScoringAgent: {e}")
            # Fallback to basic structure
            fallback_scores = self._create_fallback_scores(features)
            
            # Add fallback scores to features
            updated_features = []
            for feature in features:
                feature['recommendation_score'] = None
                feature['recommendation_confidence'] = None
                feature['score_dimensions'] = None
                feature['matches_goal'] = None
                feature['matches_examples'] = None
                feature['score_feedback'] = None
                feature['improvement_suggestions'] = []
                updated_features.append(feature)
            
            state["recommended_features"] = updated_features
            state["relevance_scores"] = {
                "overall_score": fallback_scores.get('overall_score', 0.0),
                "overall_confidence": fallback_scores.get('overall_confidence', 0.0),
                "goal_alignment": fallback_scores.get('goal_alignment', 0.0),
                "example_alignment": fallback_scores.get('example_alignment', 0.0),
                "quality_metrics": fallback_scores.get('quality_metrics', {}),
                "recommendations": fallback_scores.get('recommendations', [])
            }
            state["next_agent"] = "review_step"
        
        return state
    
    def _create_fallback_scores(self, features: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a basic scoring structure when parsing fails"""
        feature_scores = []
        for f in features:
            feature_name = f.get('feature_name', 'unknown')
            feature_scores.append({
                "feature_name": feature_name,
                "score": 0.7,  # Default moderate score
                "confidence": 0.5,
                "dimensions": {
                    "relevance": 0.7,
                    "completeness": 0.7,
                    "feasibility": 0.7,
                    "clarity": 0.7,
                    "technical_accuracy": 0.7
                },
                "matches_goal": True,
                "matches_examples": False,
                "feedback": "Basic scoring applied due to parsing error",
                "improvement_suggestions": []
            })
        
        avg_score = sum(s['score'] for s in feature_scores) / len(feature_scores) if feature_scores else 0.7
        
        return {
            "overall_score": avg_score,
            "overall_confidence": 0.5,
            "feature_scores": feature_scores,
            "goal_alignment": 0.7,
            "example_alignment": 0.0,
            "quality_metrics": {
                "average_feature_score": avg_score,
                "consistency": 0.7,
                "coverage": 0.7
            },
            "recommendations": []
        }
    
    def _validate_scoring_result(self, data: Dict[str, Any], features: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate and fix scoring result structure"""
        feature_names = {f.get('feature_name', f'feature_{i}') for i, f in enumerate(features)}
        
        # Validate feature scores
        validated_scores = []
        for score in data.get('feature_scores', []):
            feat_name = score.get('feature_name', '')
            if feat_name in feature_names:
                # Ensure all required fields exist
                validated_scores.append({
                    "feature_name": feat_name,
                    "score": max(0.0, min(1.0, score.get('score', 0.7))),
                    "confidence": max(0.0, min(1.0, score.get('confidence', 0.5))),
                    "dimensions": score.get('dimensions', {}),
                    "matches_goal": score.get('matches_goal', True),
                    "matches_examples": score.get('matches_examples', False),
                    "feedback": score.get('feedback', ''),
                    "improvement_suggestions": score.get('improvement_suggestions', [])
                })
        
        overall_score = data.get('overall_score', 0.7)
        overall_score = max(0.0, min(1.0, overall_score))
        
        return {
            "overall_score": overall_score,
            "overall_confidence": max(0.0, min(1.0, data.get('overall_confidence', 0.5))),
            "feature_scores": validated_scores,
            "goal_alignment": max(0.0, min(1.0, data.get('goal_alignment', 0.7))),
            "example_alignment": max(0.0, min(1.0, data.get('example_alignment', 0.0))),
            "quality_metrics": data.get('quality_metrics', {}),
            "recommendations": data.get('recommendations', [])
        }


# ============================================================================
# DEEP RESEARCH REVIEW AGENT
# ============================================================================

# ============================================================================
# DEEP RESEARCH REVIEW AGENT
# ============================================================================
# DeepResearchReviewAgent has been moved to deep_research.py
# Import it at the top of this file


# ============================================================================
# FILE WRITING NODE
# ============================================================================

class FileWritingNode:
    """Node that automatically writes workflow results to a file"""
    
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path("transform/outputs")
    
    async def __call__(self, state: FeatureEngineeringState) -> FeatureEngineeringState:
        """Write results to file asynchronously"""
        try:
            # Get domain name for filename
            domain_config_dict = state.get("domain_config", {})
            domain_name = domain_config_dict.get("domain_name", "compliance") if domain_config_dict else "compliance"
            project_id = state.get("project_id", "unknown")
            
            # Convert state to result format
            result = {
                "analytical_intent": state.get("analytical_intent", {}),
                "identified_controls": state.get("identified_controls", []),
                "recommended_features": state.get("recommended_features", []),
                "feature_dependencies": state.get("feature_dependencies", {}),
                "relevance_scores": state.get("relevance_scores", {}),
                "deep_research_review": state.get("deep_research_review", {}),
                "feature_calculation_plan": state.get("feature_calculation_plan", {}),
                "relevant_schemas": state.get("relevant_schemas", []),
                "knowledge_documents": state.get("knowledge_documents", []),
                "metrics": state.get("metrics", {})  # Include metrics
            }
            
            # Write file asynchronously
            filename_prefix = f"feature_engineering_output_{domain_name.lower().replace(' ', '_')}"
            output_file = await write_results_to_file_async(
                result=result,
                output_dir=self.output_dir,
                filename_prefix=filename_prefix,
                domain_name=domain_name,
                project_id=project_id
            )
            
            state["output_file"] = str(output_file)
            state["messages"].append(AIMessage(
                content=f"Results written to: {output_file}",
                name="FileWritingNode"
            ))
            
        except Exception as e:
            logger.error(f"Error writing results to file: {e}")
            state["output_file"] = None
            state["messages"].append(AIMessage(
                content=f"Error writing results to file: {str(e)}",
                name="FileWritingNode"
            ))
        
        state["next_agent"] = "end"
        return state


# ============================================================================
# RISK FEATURE GENERATION GRAPH
# ============================================================================

def create_risk_feature_generation_graph(
    llm: BaseChatModel,
    domain_config: Optional[DomainConfiguration] = None,
    retrieval_helper: Optional[RetrievalHelper] = None
) -> StateGraph:
    """Create a separate graph for generating risk/impact/likelihood features
    
    This graph is invoked after base metrics generation and generates risk features
    based on use case groups and risk configuration.
    
    Args:
        llm: Language model instance
        domain_config: Domain configuration
        retrieval_helper: Optional retrieval helper
    
    Returns:
        Compiled LangGraph workflow for risk feature generation
    """
    # Use default domain config if not provided
    if domain_config is None:
        domain_config = CYBERSECURITY_DOMAIN_CONFIG
    
    # Initialize risk feature agents
    impact_agent = ImpactFeatureGenerationAgent(llm, domain_config)
    likelihood_agent = LikelihoodFeatureGenerationAgent(llm, domain_config)
    risk_agent = RiskFeatureGenerationAgent(llm, domain_config)
    
    # Create workflow
    workflow = StateGraph(FeatureEngineeringState)
    
    # Add nodes
    workflow.add_node("impact_feature_generation", impact_agent)
    workflow.add_node("likelihood_feature_generation", likelihood_agent)
    workflow.add_node("risk_feature_generation", risk_agent)
    
    # Define routing function
    def route_risk_agent(state: FeatureEngineeringState) -> str:
        """Route based on risk configuration and use case groups"""
        next_agent = state.get("next_agent", "end")
        if next_agent == "end" or next_agent == END:
            return END
        
        # Check risk configuration to determine which features to generate
        risk_config = state.get("risk_configuration", {})
        use_case_groups = state.get("use_case_groups", [])
        
        # If no use case groups, generate all risk features
        if not use_case_groups:
            # Default flow: impact -> likelihood -> risk
            if next_agent == "impact_feature_generation":
                return "likelihood_feature_generation"
            elif next_agent == "likelihood_feature_generation":
                return "risk_feature_generation"
            elif next_agent == "risk_feature_generation":
                return END
            else:
                return "impact_feature_generation"
        
        # Route based on use case group configuration
        # For each use case group, check if risk/impact/likelihood should be generated
        current_group_index = state.get("current_risk_group_index", 0)
        if current_group_index >= len(use_case_groups):
            return END
        
        current_group = use_case_groups[current_group_index]
        group_name = current_group.get("use_case_name", "")
        
        # Check configuration for this group
        group_config = risk_config.get(group_name, {})
        generate_impact = group_config.get("generate_impact", True)
        generate_likelihood = group_config.get("generate_likelihood", True)
        generate_risk = group_config.get("generate_risk", True)
        
        # Route based on what needs to be generated
        if next_agent == "impact_feature_generation":
            if generate_likelihood:
                return "likelihood_feature_generation"
            elif generate_risk:
                return "risk_feature_generation"
            else:
                # Move to next group
                state["current_risk_group_index"] = current_group_index + 1
                if state["current_risk_group_index"] < len(use_case_groups):
                    return "impact_feature_generation"
                else:
                    return END
        elif next_agent == "likelihood_feature_generation":
            if generate_risk:
                return "risk_feature_generation"
            else:
                # Move to next group
                state["current_risk_group_index"] = current_group_index + 1
                if state["current_risk_group_index"] < len(use_case_groups):
                    return "impact_feature_generation"
                else:
                    return END
        elif next_agent == "risk_feature_generation":
            # Move to next group
            state["current_risk_group_index"] = current_group_index + 1
            if state["current_risk_group_index"] < len(use_case_groups):
                return "impact_feature_generation"
            else:
                return END
        else:
            # Start with impact if enabled, otherwise skip to likelihood or risk
            if generate_impact:
                return "impact_feature_generation"
            elif generate_likelihood:
                return "likelihood_feature_generation"
            elif generate_risk:
                return "risk_feature_generation"
            else:
                # Skip this group, move to next
                state["current_risk_group_index"] = current_group_index + 1
                if state["current_risk_group_index"] < len(use_case_groups):
                    return "impact_feature_generation"
                else:
                    return END
    
    # Set entry point
    workflow.set_entry_point("impact_feature_generation")
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "impact_feature_generation",
        route_risk_agent,
        {
            "likelihood_feature_generation": "likelihood_feature_generation",
            "risk_feature_generation": "risk_feature_generation",
            "impact_feature_generation": "impact_feature_generation",  # Next group
            END: END
        }
    )
    workflow.add_conditional_edges(
        "likelihood_feature_generation",
        route_risk_agent,
        {
            "risk_feature_generation": "risk_feature_generation",
            "impact_feature_generation": "impact_feature_generation",  # Next group
            END: END
        }
    )
    workflow.add_conditional_edges(
        "risk_feature_generation",
        route_risk_agent,
        {
            "impact_feature_generation": "impact_feature_generation",  # Next group
            END: END
        }
    )
    
    return workflow.compile()


# ============================================================================
# WORKFLOW DEFINITION
# ============================================================================

def create_feature_engineering_workflow(
    llm: BaseChatModel,
    retrieval_helper: Optional[RetrievalHelper] = None,
    domain_config: Optional[DomainConfiguration] = None,
    output_dir: Optional[Path] = None,
    auto_write_file: bool = True
) -> StateGraph:
    """Create the LangGraph workflow for Deep Research Feature Engineering
    
    This workflow implements a deep research agent for compliance risk estimation, monitoring, and reporting
    using a MEDALLION ARCHITECTURE (Bronze/Silver/Gold).
    
    Process Flow:
    1. Query Understanding: Identify most important compliances based on knowledge, history, examples
    2. Control Identification: Identify controls and fetch knowledge for each control
    3. Schema Analysis: Understand available data model
    4. Feature Recommendation: Generate detailed natural language questions for each control
    5. Feature Dependency: Analyze dependencies and calculation order
    6. Relevancy Scoring: Score features against goals and examples
    7. Deep Research Review: Review recommendations and relevancy scores
    
    The workflow generates detailed natural language questions that can be executed by
    transformation agents in a medallion architecture (silver/gold layers).
    
    Args:
        llm: Language model instance (model-agnostic, works with any BaseChatModel)
        retrieval_helper: Optional retrieval helper for schema/knowledge retrieval
        domain_config: Domain configuration (defaults to cybersecurity if not provided)
    
    Returns:
        Compiled LangGraph workflow for deep research feature engineering
    """
    # Use default domain config if not provided
    if domain_config is None:
        domain_config = CYBERSECURITY_DOMAIN_CONFIG
    
    # Initialize agents with domain configuration
    # Deep Research Workflow agents (compliance-first approach)
    # First step: Query breakdown
    breakdown_agent = QueryBreakdownAgent(llm, domain_config)
    query_agent = QueryUnderstandingAgent(llm, domain_config, retrieval_helper)
    control_agent = ControlIdentificationAgent(llm, domain_config, retrieval_helper)
    knowledge_agent = KnowledgeRefiningAgent(llm, retrieval_helper, domain_config)
    schema_agent = SchemaAnalysisAgent(llm, retrieval_helper, domain_config)
    question_agent = QuestionGenerationAgent(llm, domain_config)
    feature_agent = FeatureRecommendationAgent(llm, domain_config)
    risk_feature_agent = RiskFeatureEngineeringAgent(llm, domain_config, retrieval_helper)
    combination_agent = FeatureCombinationAgent(llm, domain_config)
    calculation_plan_agent = FeatureCalculationPlanAgent(llm, domain_config)
    plan_agent = ReasoningPlanAgent(llm, domain_config)
    dependency_agent = FeatureDependencyAgent(llm, domain_config)
    scoring_agent = RelevancyScoringAgent(llm, domain_config)
    review_agent = DeepResearchReviewAgent(llm, domain_config)
    
    # Group Planner Agent (creates breakdown groups based on knowledge and goal)
    group_planner_agent = GroupPlannerAgent(llm, domain_config)
    
    # External agents for group-based generation (dummy implementations)
    group_kpi_agent = GroupKPIGenerationAgent(llm, domain_config)
    group_metric_agent = GroupMetricGenerationAgent(llm, domain_config)
    group_sql_agent = GroupSQLQuestionGenerationAgent(llm, domain_config)
    
    # Risk Quantification Planner Agent
    risk_quantification_planner_agent = RiskQuantificationPlannerAgent(llm, domain_config)
    
    # File writing node (optional)
    file_writer = FileWritingNode(output_dir=output_dir) if auto_write_file else None
    
    # STEP 3: Deep Research & Risk Modeling agents (kept for backward compatibility)
    # These are called separately, not as part of the main feature engineering flow
    # TODO: Move to separate deep_research_agents.py or integrate into risk_model_agents.py
    impact_agent = ImpactFeatureGenerationAgent(llm, domain_config)
    likelihood_agent = LikelihoodFeatureGenerationAgent(llm, domain_config)
    risk_agent = RiskFeatureGenerationAgent(llm, domain_config)
    
    # Create risk feature generation graph (separate graph for risk/impact/likelihood)
    risk_feature_graph = create_risk_feature_generation_graph(llm, domain_config, retrieval_helper)
    
    # Create workflow
    workflow = StateGraph(FeatureEngineeringState)
    
    # Add nodes - LangGraph supports async functions directly
    # Deep Research Workflow nodes (compliance-first approach)
    # First step: Query breakdown (node name must differ from state key)
    workflow.add_node("breakdown_analysis", breakdown_agent)
    workflow.add_node("query_understanding", query_agent)
    workflow.add_node("control_identification", control_agent)
    workflow.add_node("knowledge_retrieval", knowledge_agent)
    workflow.add_node("schema_analysis", schema_agent)
    workflow.add_node("question_generation", question_agent)
    workflow.add_node("group_planner", group_planner_agent)
    workflow.add_node("feature_recommendation", feature_agent)
    workflow.add_node("risk_feature_engineering", risk_feature_agent)
    
    # External agents for group-based generation (dummy implementations)
    workflow.add_node("group_kpi_generation", group_kpi_agent)
    workflow.add_node("group_metric_generation", group_metric_agent)
    workflow.add_node("group_sql_generation", group_sql_agent)
    
    # Risk Quantification Planner
    workflow.add_node("risk_quantification_planner", risk_quantification_planner_agent)
    
    # Add node to invoke risk feature generation graph
    async def invoke_risk_feature_graph(state: FeatureEngineeringState) -> FeatureEngineeringState:
        """Invoke the separate risk feature generation graph"""
        try:
            # Initialize risk group index if not present
            if "current_risk_group_index" not in state:
                state["current_risk_group_index"] = 0
            
            # Invoke the risk feature generation graph
            result = await risk_feature_graph.ainvoke(state)
            
            # Merge results back into state
            state.update(result)
            
            # After risk features are generated, continue to feature combination
            state["next_agent"] = "feature_combination"
            
        except Exception as e:
            logger.error(f"Error invoking risk feature generation graph: {e}")
            state["next_agent"] = "feature_combination"  # Continue even on error
        
        return state
    
    workflow.add_node("risk_feature_generation_graph", invoke_risk_feature_graph)
    
    workflow.add_node("feature_combination", combination_agent)
    workflow.add_node("feature_calculation_planning", calculation_plan_agent)
    workflow.add_node("create_reasoning_plan", plan_agent)
    workflow.add_node("feature_dependency", dependency_agent)
    workflow.add_node("relevancy_scoring", scoring_agent)
    workflow.add_node("review_step", review_agent)  # Renamed from "deep_research_review" to avoid state key conflict
    
    # File writing node (if enabled)
    if file_writer:
        workflow.add_node("write_output_file", file_writer)
    
    # STEP 3: Deep Research nodes (available for separate calls, not in main flow)
    # These can be called via generate_impact_features(), generate_likelihood_features(), etc.
    workflow.add_node("impact_feature_generation", impact_agent)
    workflow.add_node("likelihood_feature_generation", likelihood_agent)
    workflow.add_node("risk_feature_generation", risk_agent)
    
    # Define routing function
    def route_agent(state: FeatureEngineeringState) -> str:
        next_agent = state.get("next_agent", "end")
        if next_agent == "end" or next_agent == END:
            return END
        # Validate that the next_agent is a valid node
        valid_nodes = {
            "breakdown_analysis", "query_understanding", "control_identification", "knowledge_retrieval", "schema_analysis",
            "question_generation", "group_planner", "feature_recommendation", "risk_feature_engineering", "risk_feature_generation_graph",
            "group_kpi_generation", "group_metric_generation", "group_sql_generation",
            "risk_quantification_planner",
            "feature_combination", "feature_calculation_planning", "create_reasoning_plan", 
            "feature_dependency", "relevancy_scoring", "review_step", "write_output_file", 
            "impact_feature_generation", "likelihood_feature_generation", "risk_feature_generation", "end"
        }
        if next_agent not in valid_nodes:
            logger.warning(f"Invalid next_agent '{next_agent}', defaulting to 'end'")
            return END
        return next_agent
    
    # Add edges
    workflow.set_entry_point("breakdown_analysis")
    
    # Define all possible destinations for routing (including STEP 3 nodes for resume scenarios)
    # This allows initial nodes to route to any destination when resuming
    all_destinations = {
        "breakdown_analysis": "breakdown_analysis",
        "query_understanding": "query_understanding",
        "control_identification": "control_identification",
        "knowledge_retrieval": "knowledge_retrieval",
        "schema_analysis": "schema_analysis",
        "question_generation": "question_generation",
        "group_planner": "group_planner",
        "feature_recommendation": "feature_recommendation",
        "risk_feature_engineering": "risk_feature_engineering",
        "risk_feature_generation_graph": "risk_feature_generation_graph",
        "group_kpi_generation": "group_kpi_generation",
        "group_metric_generation": "group_metric_generation",
        "group_sql_generation": "group_sql_generation",
        "risk_quantification_planner": "risk_quantification_planner",
        "feature_combination": "feature_combination",
        "feature_calculation_planning": "feature_calculation_planning",
        "create_reasoning_plan": "create_reasoning_plan",
        "feature_dependency": "feature_dependency",
        "relevancy_scoring": "relevancy_scoring",
        "review_step": "review_step",
        "impact_feature_generation": "impact_feature_generation",
        "likelihood_feature_generation": "likelihood_feature_generation",
        "risk_feature_generation": "risk_feature_generation",
        END: END
    }
    
    # Add write_output_file only if file_writer is enabled
    if file_writer:
        all_destinations["write_output_file"] = "write_output_file"
    
    # Add conditional edge for breakdown_analysis
    workflow.add_conditional_edges(
        "breakdown_analysis",
        route_agent,
        {
            "query_understanding": "query_understanding",
            END: END
        }
    )
    workflow.add_conditional_edges(
        "query_understanding",
        route_agent,
        all_destinations
    )
    workflow.add_conditional_edges(
        "control_identification",
        route_agent,
        all_destinations
    )
    workflow.add_conditional_edges(
        "knowledge_retrieval",
        route_agent,
        all_destinations
    )
    workflow.add_conditional_edges(
        "schema_analysis",
        route_agent,
        all_destinations
    )
    workflow.add_conditional_edges(
        "question_generation",
        route_agent,
        all_destinations
    )
    workflow.add_conditional_edges(
        "group_planner",
        route_agent,
        {
            "feature_recommendation": "feature_recommendation",
            "group_kpi_generation": "group_kpi_generation",
            "group_metric_generation": "group_metric_generation",
            "group_sql_generation": "group_sql_generation",
            END: END
        }
    )
    workflow.add_conditional_edges(
        "feature_recommendation",
        route_agent,
        {
            "risk_feature_generation_graph": "risk_feature_generation_graph",
            "risk_feature_engineering": "risk_feature_engineering",
            "feature_combination": "feature_combination",
            "feature_calculation_planning": "feature_calculation_planning",
            "create_reasoning_plan": "create_reasoning_plan",
            "feature_dependency": "feature_dependency",
            # Note: Impact/Likelihood/Risk features are generated via risk_feature_generation_graph
            # They can also be called separately via generate_impact_features(), etc.
            END: END
        }
    )
    # Add conditional edge for risk_feature_generation_graph
    workflow.add_conditional_edges(
        "risk_feature_generation_graph",
        route_agent,
        {
            "feature_combination": "feature_combination",
            "feature_calculation_planning": "feature_calculation_planning",
            "create_reasoning_plan": "create_reasoning_plan",
            "feature_dependency": "feature_dependency",
            END: END
        }
    )
    workflow.add_conditional_edges(
        "feature_calculation_planning",
        route_agent,
        {
            "create_reasoning_plan": "create_reasoning_plan",
            "feature_dependency": "feature_dependency",
            # Note: Impact/Likelihood/Risk features are generated in STEP 3 (Deep Research)
            END: END
        }
    )
    # Add conditional edge for risk_feature_engineering
    workflow.add_conditional_edges(
        "risk_feature_engineering",
        route_agent,
        {
            "feature_combination": "feature_combination",
            "feature_dependency": "feature_dependency",
            "feature_calculation_planning": "feature_calculation_planning",
            "create_reasoning_plan": "create_reasoning_plan",
            END: END
        }
    )
    # Add conditional edge for feature_combination
    workflow.add_conditional_edges(
        "feature_combination",
        route_agent,
        {
            "feature_calculation_planning": "feature_calculation_planning",
            "create_reasoning_plan": "create_reasoning_plan",
            "feature_dependency": "feature_dependency",
            END: END
        }
    )
    # STEP 3: Deep Research workflow edges (for separate calls)
    # These are used when calling generate_impact_features(), generate_likelihood_features(), etc.
    workflow.add_conditional_edges(
        "impact_feature_generation",
        route_agent,
        all_destinations
    )
    workflow.add_conditional_edges(
        "likelihood_feature_generation",
        route_agent,
        all_destinations
    )
    workflow.add_conditional_edges(
        "risk_feature_generation",
        route_agent,
        all_destinations
    )
    workflow.add_conditional_edges(
        "create_reasoning_plan",
        route_agent,
        {
            "feature_dependency": "feature_dependency",
            END: END
        }
    )
    workflow.add_conditional_edges(
        "feature_dependency",
        route_agent,
        {
            "relevancy_scoring": "relevancy_scoring",
            "review_step": "review_step",
            END: END
        }
    )
    workflow.add_conditional_edges(
        "relevancy_scoring",
        route_agent,
        {
            "review_step": "review_step",
            END: END
        }
    )
    # Route from review_step
    if file_writer:
        workflow.add_conditional_edges(
            "review_step",
            route_agent,
            {
                "write_output_file": "write_output_file",
                END: END
            }
        )
        workflow.add_conditional_edges(
            "write_output_file",
            route_agent,
            {
                END: END
            }
        )
    else:
        # If file writing is disabled, route directly to END
        workflow.add_conditional_edges(
            "review_step",
            route_agent,
            {
                "write_output_file": END,  # Route write_output_file to END if file_writer is disabled
                END: END
            }
        )
    
    return workflow.compile()


# ============================================================================
# PIPELINE CLASS
# ============================================================================

class FeatureEngineeringPipeline(AgentPipeline):
    """
    Pipeline for STEP 2: Feature Engineering using multi-agent system
    
    This is STEP 2 of the three-phase compliance system:
    - STEP 1: Document Analysis → Control Universe
    - STEP 2: Feature Engineering (this pipeline) → Recommended Features
    - STEP 3: Deep Research & Risk Modeling → Risk Model Blueprint
    
    This pipeline generates compliance features from user queries. It does NOT
    automatically generate impact/likelihood/risk features - those are handled
    in STEP 3 (Deep Research & Risk Modeling workflow).
    
    For the complete sequential flow, see README.md
    """
    
    def __init__(
        self,
        llm: ChatOpenAI,
        retrieval_helper: Optional[RetrievalHelper] = None,
        document_store_provider: Optional[DocumentStoreProvider] = None,
        engine: Optional[Engine] = None,
        domain_config: Optional[DomainConfiguration] = None,
        output_dir: Optional[Path] = None,
        auto_write_file: bool = True
    ):
        """Initialize the feature engineering pipeline (STEP 2)
        
        Args:
            llm: Language model instance
            retrieval_helper: Optional retrieval helper for schema/knowledge retrieval
            document_store_provider: Optional document store provider
            engine: Optional engine instance
            domain_config: Domain configuration (defaults to cybersecurity if not provided)
        
        Note: This pipeline is STEP 2 of the three-phase system. For impact/likelihood/risk
        features, use STEP 3 (Deep Research & Risk Modeling workflow).
        """
        super().__init__(
            name="feature_engineering",
            version="1.0.0",
            description="Multi-agent pipeline for generating feature engineering plans from natural language queries",
            llm=llm,
            retrieval_helper=retrieval_helper,
            document_store_provider=document_store_provider,
            engine=engine
        )
        
        # Use default domain config if not provided
        self.domain_config = domain_config or CYBERSECURITY_DOMAIN_CONFIG
        
        # Use get_llm from dependencies for consistent LLM initialization (model-agnostic)
        # Default to gpt-4o-mini, but can be overridden via settings
        self._workflow_llm = get_llm(temperature=0, model="gpt-4o-mini")
        self._workflow = None
        self._output_dir = output_dir
        self._auto_write_file = auto_write_file
    
    async def initialize(self) -> None:
        """Initialize the pipeline and create workflow"""
        await super().initialize()
        self._workflow = create_feature_engineering_workflow(
            llm=self._workflow_llm,
            retrieval_helper=self._retrieval_helper,
            domain_config=self.domain_config,
            output_dir=self._output_dir,
            auto_write_file=self._auto_write_file
        )
    
    async def run(
        self,
        user_query: Optional[str] = None,
        project_id: Optional[str] = None,
        histories: Optional[List[Any]] = None,
        validation_expectations: Optional[List[Dict[str, Any]]] = None,
        refining_instructions: Optional[str] = None,
        refining_examples: Optional[List[Dict[str, Any]]] = None,
        feature_generation_instructions: Optional[str] = None,
        feature_generation_examples: Optional[List[Dict[str, Any]]] = None,
        initial_state: Optional[FeatureEngineeringState] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute STEP 2: Feature Engineering pipeline
        
        This is STEP 2 of the three-phase compliance system. It generates compliance
        features from user queries but does NOT generate impact/likelihood/risk features.
        Those are generated in STEP 3 (Deep Research & Risk Modeling).
        
        Args:
            user_query: Natural language description of analytics needs (required if initial_state is None)
            project_id: Project ID for schema retrieval (required if initial_state is None)
            histories: Optional list of historical queries for context
            validation_expectations: Optional list of expectations/examples for validation scoring
            refining_instructions: Optional instructions for knowledge refining agent (placeholder for future)
            refining_examples: Optional examples for knowledge refining agent (placeholder for future)
            feature_generation_instructions: Optional instructions for feature generation agent (placeholder for future)
            feature_generation_examples: Optional examples for feature generation agent (placeholder for future)
            initial_state: Optional initial state to resume from. If provided, user_query and project_id can be None.
                          If None, a fresh state will be created from user_query and project_id.
            **kwargs: Additional arguments
            
        Returns:
            Dictionary containing:
            - clarifying_questions: List of questions to refine requirements
            - reasoning_plan: Step-by-step analytical plan
            - recommended_features: List of compliance features to calculate
            - feature_dependencies: Dependency graph and calculation order
            - relevance_scores: Relevance scores for features and overall output
            - analytical_intent: Parsed intent from query
            - relevant_schemas: List of relevant schema names
            - identified_controls: Controls identified from data model
            - knowledge_documents: Retrieved knowledge documents
            
        Note: Impact, Likelihood, and Risk features are NOT generated by this pipeline.
        Use STEP 3 (Deep Research & Risk Modeling workflow) for those.
        """
        if not self._initialized:
            await self.initialize()
        
        if not self._workflow:
            raise RuntimeError("Workflow not initialized")
        
        # Use provided initial_state or create a fresh one
        if initial_state is not None:
            # Resume from provided state
            # Ensure domain_config is set if not present
            if "domain_config" not in initial_state or not initial_state.get("domain_config"):
                initial_state["domain_config"] = self.domain_config.model_dump() if hasattr(self.domain_config, 'model_dump') else self.domain_config.dict()
            
            # Update any provided parameters that override state
            if refining_instructions is not None:
                initial_state["refining_instructions"] = refining_instructions
            if refining_examples is not None:
                initial_state["refining_examples"] = refining_examples
            if feature_generation_instructions is not None:
                initial_state["feature_generation_instructions"] = feature_generation_instructions
            if feature_generation_examples is not None:
                initial_state["feature_generation_examples"] = feature_generation_examples
            if validation_expectations is not None:
                initial_state["validation_expectations"] = validation_expectations
        else:
            # Create fresh state
            if user_query is None or project_id is None:
                raise ValueError("user_query and project_id are required when initial_state is not provided")
            
            initial_state: FeatureEngineeringState = {
        "messages": [],
        "user_query": user_query,
        "analytical_intent": {},
        "relevant_schemas": [],
        "available_features": [],
        "clarifying_questions": [],
        "reasoning_plan": {},
        "recommended_features": [],
                "feature_dependencies": {},
                "relevance_scores": {},
                "feature_calculation_plan": {},
                "impact_features": [],
                "likelihood_features": [],
                "risk_features": [],
                "next_agent": "breakdown_analysis",
                "project_id": project_id,
                "histories": histories or [],
                "schema_registry": {},
                "knowledge_documents": [],
                "domain_config": self.domain_config.model_dump() if hasattr(self.domain_config, 'model_dump') else self.domain_config.dict(),
                "identified_controls": None,
                "control_universe": None,
                "validation_expectations": validation_expectations or [],
                "refining_instructions": refining_instructions,
                "refining_examples": refining_examples or [],
                "feature_generation_instructions": feature_generation_instructions,
                "feature_generation_examples": feature_generation_examples or []
            }
        
        # Run workflow asynchronously
        result = await self._workflow.ainvoke(initial_state)
        
        return {
            "clarifying_questions": result.get("clarifying_questions", []),
            "reasoning_plan": result.get("reasoning_plan", {}),
            "recommended_features": result.get("recommended_features", []),
            "feature_dependencies": result.get("feature_dependencies", {}),
            "relevance_scores": result.get("relevance_scores", {}),
            "feature_calculation_plan": result.get("feature_calculation_plan", {}),
            "impact_features": result.get("impact_features", []),
            "likelihood_features": result.get("likelihood_features", []),
            "risk_features": result.get("risk_features", []),
            "analytical_intent": result.get("analytical_intent", {}),
            "relevant_schemas": result.get("relevant_schemas", []),
            "schema_registry": result.get("schema_registry", {}),
            "knowledge_documents": result.get("knowledge_documents", []),
            "identified_controls": result.get("identified_controls", []),
            "control_universe": result.get("control_universe", {}),
            "deep_research_review": result.get("deep_research_review", {}),
            "metrics": result.get("metrics", {}),  # Include metrics
            "_full_state": dict(result)  # Full state for resuming
        }
    
    def get_configuration(self) -> Dict[str, Any]:
        """Get the current configuration of the pipeline"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "has_retrieval_helper": self._retrieval_helper is not None,
            "has_engine": self.engine is not None
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
# ASYNC FILE WRITING AND BACKGROUND EXECUTION
# ============================================================================

async def write_results_to_file_async(
    result: Dict[str, Any],
    output_dir: Optional[Path] = None,
    filename_prefix: str = "feature_engineering_output",
    domain_name: Optional[str] = None,
    project_id: Optional[str] = None
) -> Path:
    """
    Asynchronously write pipeline results to a markdown file.
    
    Args:
        result: Pipeline result dictionary
        output_dir: Output directory (defaults to "transform/outputs")
        filename_prefix: Prefix for output filename
        domain_name: Domain name for metadata
        project_id: Project ID for metadata
    
    Returns:
        Path to the written file
    """
    if output_dir is None:
        output_dir = Path("transform/outputs")
    else:
        output_dir = Path(output_dir)
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{filename_prefix}_{timestamp}.md"
    output_file = output_dir / filename
    
    # Write file asynchronously using aiofiles or thread pool
    # Since aiofiles might not be available, use asyncio.to_thread for file I/O
    def write_file():
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# Deep Research Feature Engineering Pipeline Output\n\n")
            f.write(f"**Generated at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            if domain_name:
                f.write(f"**Domain:** {domain_name}\n")
            if project_id:
                f.write(f"**Project ID:** {project_id}\n")
            f.write("\n")
            
            # Write analytical intent
            analytical_intent = result.get("analytical_intent", {})
            if analytical_intent:
                f.write("## Analytical Intent\n\n")
                f.write(f"**Primary Goal:** {analytical_intent.get('primary_goal', 'N/A')}\n")
                f.write(f"**Compliance Framework:** {analytical_intent.get('compliance_framework', 'N/A')}\n")
                f.write(f"**Aggregation Level:** {analytical_intent.get('aggregation_level', 'N/A')}\n")
                f.write("\n")
            
            # Write identified controls
            identified_controls = result.get("identified_controls", [])
            if identified_controls:
                f.write(f"## Identified Compliance Controls ({len(identified_controls)} controls)\n\n")
                for i, control in enumerate(identified_controls, 1):
                    f.write(f"### {i}. {control.get('control_id', 'UNKNOWN')}: {control.get('control_name', 'N/A')}\n")
                    f.write(f"**Category:** {control.get('category', 'N/A')}\n")
                    f.write(f"**Description:** {control.get('description', 'N/A')[:200]}\n")
                    key_measures = control.get('key_measures', [])
                    if key_measures:
                        f.write(f"**Key Measures:** {', '.join(key_measures[:5])}\n")
                    f.write("\n")
            
            # Write recommended features grouped by feature_group
            recommended_features = result.get("recommended_features", [])
            if recommended_features:
                # Group features by feature_group
                grouped_features = {}
                ungrouped_features = []
                for feature in recommended_features:
                    feature_group = feature.get('feature_group', 'ungrouped')
                    if feature_group and feature_group != 'ungrouped':
                        if feature_group not in grouped_features:
                            grouped_features[feature_group] = []
                        grouped_features[feature_group].append(feature)
                    else:
                        ungrouped_features.append(feature)
                
                f.write(f"## Recommended Features ({len(recommended_features)} total)\n\n")
                
                # Write grouped features
                for group_name, group_features in sorted(grouped_features.items()):
                    f.write(f"### Feature Group: {group_name.replace('_', ' ').title()} ({len(group_features)} features)\n\n")
                    for i, feature in enumerate(group_features, 1):
                        f.write(f"#### {i}. {feature.get('feature_name', 'Unknown')}\n")
                        f.write(f"**Natural Language Question:** {feature.get('natural_language_question', 'N/A')}\n")
                        f.write(f"**Type:** {feature.get('feature_type', 'Unknown')}\n")
                        f.write(f"**Aggregation Method:** {feature.get('aggregation_method', 'N/A')}\n")
                        if feature.get('filters_applied'):
                            f.write(f"**Filters Applied:** {', '.join(feature.get('filters_applied', []))}\n")
                        f.write(f"**Business Context:** {feature.get('business_context', 'N/A')}\n")
                        compliance_reasoning = feature.get('compliance_reasoning') or feature.get('soc2_compliance_reasoning', 'N/A')
                        f.write(f"**Compliance Reasoning:** {compliance_reasoning}\n")
                        f.write(f"**Transformation Layer:** {feature.get('transformation_layer', 'gold')}\n")
                        f.write(f"**Time Series Type:** {feature.get('time_series_type', 'None')}\n")
                        if feature.get('required_schemas'):
                            f.write(f"**Required Schemas:** {', '.join(feature.get('required_schemas', []))}\n")
                        f.write("\n")
                
                # Write ungrouped features if any
                if ungrouped_features:
                    f.write(f"### Ungrouped Features ({len(ungrouped_features)} features)\n\n")
                    for i, feature in enumerate(ungrouped_features, 1):
                        f.write(f"#### {i}. {feature.get('feature_name', 'Unknown')}\n")
                        f.write(f"**Natural Language Question:** {feature.get('natural_language_question', 'N/A')}\n")
                        f.write(f"**Type:** {feature.get('feature_type', 'Unknown')}\n")
                        f.write(f"**Aggregation Method:** {feature.get('aggregation_method', 'N/A')}\n")
                        if feature.get('filters_applied'):
                            f.write(f"**Filters Applied:** {', '.join(feature.get('filters_applied', []))}\n")
                        f.write(f"**Business Context:** {feature.get('business_context', 'N/A')}\n")
                        compliance_reasoning = feature.get('compliance_reasoning') or feature.get('soc2_compliance_reasoning', 'N/A')
                        f.write(f"**Compliance Reasoning:** {compliance_reasoning}\n")
                        f.write(f"**Transformation Layer:** {feature.get('transformation_layer', 'gold')}\n")
                        f.write(f"**Time Series Type:** {feature.get('time_series_type', 'None')}\n")
                        if feature.get('required_schemas'):
                            f.write(f"**Required Schemas:** {', '.join(feature.get('required_schemas', []))}\n")
                        f.write("\n")
            
            # Write deep research review
            deep_research_review = result.get("deep_research_review", {})
            if deep_research_review:
                f.write("## Deep Research Review\n\n")
                review_summary = deep_research_review.get("review_summary", {})
                f.write(f"**Overall Assessment:** {review_summary.get('overall_assessment', 'N/A')[:500]}\n\n")
                
                coverage_gaps = review_summary.get("coverage_gaps", [])
                if coverage_gaps:
                    f.write("### Coverage Gaps\n\n")
                    for gap in coverage_gaps:
                        f.write(f"- {gap}\n")
                    f.write("\n")
                
                quality_issues = review_summary.get("quality_issues", [])
                if quality_issues:
                    f.write("### Quality Issues\n\n")
                    for issue in quality_issues:
                        f.write(f"- {issue}\n")
                    f.write("\n")
                
                improvements = review_summary.get("improvement_recommendations", [])
                if improvements:
                    f.write("### Improvement Recommendations\n\n")
                    for rec in improvements:
                        f.write(f"- {rec}\n")
                    f.write("\n")
            
            # Write relevance scores
            relevance_scores = result.get("relevance_scores", {})
            if relevance_scores:
                f.write("## Relevance Scores\n\n")
                f.write(f"**Overall Score:** {relevance_scores.get('overall_score', 'N/A')}\n")
                f.write(f"**Goal Alignment:** {relevance_scores.get('goal_alignment', 'N/A')}\n")
                f.write(f"**Overall Confidence:** {relevance_scores.get('overall_confidence', 'N/A')}\n")
                f.write("\n")
            
            # Write metrics (token usage and response times)
            metrics = result.get("metrics", {})
            if metrics:
                f.write("## Performance Metrics\n\n")
                f.write(f"**Total Steps:** {metrics.get('step_count', 0)}\n")
                f.write(f"**Total Response Time:** {metrics.get('total_response_time', 0):.3f} seconds\n")
                f.write(f"**Average Response Time per Step:** {metrics.get('total_response_time', 0) / max(metrics.get('step_count', 1), 1):.3f} seconds\n")
                f.write(f"**Total Tokens:** {metrics.get('total_tokens', 0)}\n")
                f.write(f"**Total Prompt Tokens:** {metrics.get('total_prompt_tokens', 0)}\n")
                f.write(f"**Total Completion Tokens:** {metrics.get('total_completion_tokens', 0)}\n")
                f.write("\n")
                
                # Write per-step metrics
                steps = metrics.get("steps", [])
                if steps:
                    f.write("### Per-Step Metrics\n\n")
                    f.write("| Step | Agent | Response Time (s) | Prompt Tokens | Completion Tokens | Total Tokens |\n")
                    f.write("|------|-------|-------------------|---------------|-------------------|-------------|\n")
                    for step in steps:
                        step_name = step.get("step_name", "N/A")
                        agent_name = step.get("agent_name", "N/A")
                        response_time = step.get("response_time_seconds", 0)
                        prompt_tokens = step.get("prompt_tokens", 0)
                        completion_tokens = step.get("completion_tokens", 0)
                        total_tokens = step.get("total_tokens", 0)
                        f.write(f"| {step_name} | {agent_name} | {response_time:.3f} | {prompt_tokens} | {completion_tokens} | {total_tokens} |\n")
                    f.write("\n")
                
                # Write errors if any
                errors = metrics.get("errors", [])
                if errors:
                    f.write("### Errors\n\n")
                    for error in errors:
                        f.write(f"- **{error.get('step', 'Unknown')}:** {error.get('error', 'N/A')}\n")
                    f.write("\n")
            
            # Write feature dependencies
            feature_dependencies = result.get("feature_dependencies", {})
            if feature_dependencies:
                f.write("## Feature Dependencies\n\n")
                f.write(f"**Total Calculation Steps:** {feature_dependencies.get('total_steps', 'N/A')}\n")
                f.write(f"**Calculation Sequence Groups:** {len(feature_dependencies.get('calculation_sequence', []))}\n")
                f.write("\n")
        
        return output_file
    
    # Run file writing in a thread pool to avoid blocking
    output_path = await asyncio.to_thread(write_file)
    logger.info(f"Results written to: {output_path}")
    return output_path


async def run_pipeline_async_with_file_output(
    user_query: str,
    project_id: str,
    retrieval_helper: Optional[RetrievalHelper] = None,
    domain_config: Optional[DomainConfiguration] = None,
    output_dir: Optional[Path] = None,
    filename_prefix: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Run the feature engineering pipeline asynchronously and automatically write results to file.
    This function runs in the background and doesn't block.
    
    Args:
        user_query: Natural language description of analytics needs
        project_id: Project ID for schema retrieval
        retrieval_helper: Optional retrieval helper instance
        domain_config: Domain configuration (defaults to cybersecurity if not provided)
        output_dir: Output directory for results file (defaults to "transform/outputs")
        filename_prefix: Prefix for output filename (defaults to "feature_engineering_output")
        **kwargs: Additional arguments passed to run_feature_engineering_pipeline
    
    Returns:
        Dictionary containing pipeline results and output file path
    """
    # Run pipeline
    result = await run_feature_engineering_pipeline(
        user_query=user_query,
        project_id=project_id,
        retrieval_helper=retrieval_helper,
        domain_config=domain_config,
        **kwargs
    )
    
    # Determine domain name and filename prefix
    domain_name = None
    if domain_config:
        domain_name = domain_config.domain_name
    
    if filename_prefix is None:
        filename_prefix = f"feature_engineering_output_{domain_name.lower().replace(' ', '_')}" if domain_name else "feature_engineering_output"
    
    # Write results to file asynchronously
    output_file = await write_results_to_file_async(
        result=result,
        output_dir=output_dir,
        filename_prefix=filename_prefix,
        domain_name=domain_name,
        project_id=project_id
    )
    
    result["output_file"] = str(output_file)
    return result


def run_pipeline_in_background(
    user_query: str,
    project_id: str,
    retrieval_helper: Optional[RetrievalHelper] = None,
    domain_config: Optional[DomainConfiguration] = None,
    output_dir: Optional[Path] = None,
    filename_prefix: Optional[str] = None,
    **kwargs
) -> asyncio.Task:
    """
    Run the feature engineering pipeline in the background (non-blocking).
    Results are automatically written to a file when complete.
    
    Args:
        user_query: Natural language description of analytics needs
        project_id: Project ID for schema retrieval
        retrieval_helper: Optional retrieval helper instance
        domain_config: Domain configuration (defaults to cybersecurity if not provided)
        output_dir: Output directory for results file (defaults to "transform/outputs")
        filename_prefix: Prefix for output filename (defaults to "feature_engineering_output")
        **kwargs: Additional arguments passed to run_feature_engineering_pipeline
    
    Returns:
        asyncio.Task that can be awaited or checked for completion
    """
    task = asyncio.create_task(
        run_pipeline_async_with_file_output(
            user_query=user_query,
            project_id=project_id,
            retrieval_helper=retrieval_helper,
            domain_config=domain_config,
            output_dir=output_dir,
            filename_prefix=filename_prefix,
            **kwargs
        )
    )
    return task


# ============================================================================
# MAIN EXECUTION (for backward compatibility)
# ============================================================================

async def run_feature_engineering_pipeline(
    user_query: Optional[str] = None,
    project_id: Optional[str] = None,
    retrieval_helper: Optional[RetrievalHelper] = None,
    histories: Optional[List[Any]] = None,
    domain_config: Optional[DomainConfiguration] = None,
    initial_state: Optional[FeatureEngineeringState] = None,
    validation_expectations: Optional[List[Dict[str, Any]]] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Execute the feature engineering pipeline (async version)
    
    Args:
        user_query: Natural language description of analytics needs (required if initial_state is None)
        project_id: Project ID for schema retrieval (required if initial_state is None)
        retrieval_helper: Optional retrieval helper instance
        histories: Optional list of historical queries
        domain_config: Domain configuration (defaults to cybersecurity if not provided)
        initial_state: Optional initial state to resume from. If provided, user_query and project_id can be None.
                      If None, a fresh state will be created from user_query and project_id.
        validation_expectations: Optional list of validation examples/expectations
        **kwargs: Additional state fields
        
    Returns:
        Dictionary containing:
        - clarifying_questions: List of questions to refine requirements
        - reasoning_plan: Step-by-step analytical plan
        - recommended_features: List of features to calculate (exactly 10)
        - feature_dependencies: Dependency graph and calculation order
        - relevance_scores: Relevance scores for features and overall output
        - analytical_intent: Parsed intent from query
        - relevant_schemas: List of relevant schema names
    """
    
    # Use default domain config if not provided
    if domain_config is None:
        domain_config = CYBERSECURITY_DOMAIN_CONFIG
    
    # Use get_llm from dependencies for consistent LLM initialization (model-agnostic)
    llm = get_llm(temperature=0, model="gpt-4o-mini")
    workflow = create_feature_engineering_workflow(llm, retrieval_helper, domain_config)
    
    # Use provided initial_state or create a fresh one
    if initial_state is not None:
        # Resume from provided state
        # Ensure domain_config is set if not present
        if "domain_config" not in initial_state or not initial_state.get("domain_config"):
            initial_state["domain_config"] = domain_config.model_dump() if hasattr(domain_config, 'model_dump') else domain_config.dict()
    else:
        # Create fresh state
        if user_query is None or project_id is None:
            raise ValueError("user_query and project_id are required when initial_state is not provided")
        
        initial_state: FeatureEngineeringState = {
            "messages": [],
            "user_query": user_query,
            "analytical_intent": {},
            "relevant_schemas": [],
            "available_features": [],
            "clarifying_questions": [],
            "reasoning_plan": {},
            "recommended_features": [],
            "feature_dependencies": {},
            "relevance_scores": {},
            "next_agent": "breakdown_analysis",
            "project_id": project_id,
            "histories": histories or [],
            "schema_registry": {},
            "knowledge_documents": [],
            "domain_config": domain_config.model_dump() if hasattr(domain_config, 'model_dump') else domain_config.dict(),
            "validation_expectations": validation_expectations or [],
            "refining_instructions": None,
            "refining_examples": [],
            "feature_generation_instructions": None,
            "feature_generation_examples": [],
            "identified_controls": None,
            "control_universe": None,
            "metrics": None,  # Initialize metrics tracking
            **kwargs  # Include any additional kwargs
        }
    
    result = await workflow.ainvoke(initial_state)
    
        # Return both the summary and full state for follow-up capability
    return {
        "clarifying_questions": result.get("clarifying_questions", []),
        "reasoning_plan": result.get("reasoning_plan", {}),
        "recommended_features": result.get("recommended_features", []),
        "feature_dependencies": result.get("feature_dependencies", {}),
        "relevance_scores": result.get("relevance_scores", {}),
        "feature_calculation_plan": result.get("feature_calculation_plan", {}),
        "impact_features": result.get("impact_features", []),
        "likelihood_features": result.get("likelihood_features", []),
        "risk_features": result.get("risk_features", []),
            "analytical_intent": result.get("analytical_intent", {}),
            "relevant_schemas": result.get("relevant_schemas", []),
            "knowledge_documents": result.get("knowledge_documents", []),
            "identified_controls": result.get("identified_controls", []),
            "control_universe": result.get("control_universe", {}),
            "deep_research_review": result.get("deep_research_review", {}),
            "metrics": result.get("metrics", {}),  # Include metrics
            # Include full state for follow-up/resume capability
            "_full_state": dict(result)  # Full state for resuming
        }


# ============================================================================
# STEP 3: DEEP RESEARCH & RISK MODELING - PLACEHOLDER
# ============================================================================
# 
# NOTE: The deep research phase that builds comprehensive likelihood, impact,
# and risk models is defined separately. This phase performs:
#
# 1. Deep analysis of features from STEP 2 (Feature Engineering)
# 2. Domain-specific analysis and research
# 3. Building likelihood models using universal likelihood drivers
# 4. Building impact models using universal impact dimensions
# 5. Identifying contextual factors
# 6. Creating comprehensive risk calculations
#
# The main implementation is in: risk_model_agents.py
# 
# The functions below are kept for backward compatibility and can be used
# for simpler impact/likelihood/risk feature generation, but the full deep
# research workflow should use RiskModelReasoningWorkflow from risk_model_agents.py
#
# TODO: Create deep_research_workflow() that integrates:
#   - Features from Feature Engineering (STEP 2)
#   - Control Universe from Document Analysis (STEP 1)
#   - Domain analysis
#   - RiskModelReasoningWorkflow
# ============================================================================

async def deep_research_and_risk_modeling_workflow(
    features: List[Dict[str, Any]],
    control_universe: Optional[Dict[str, Any]] = None,
    domain_context: Optional[Dict[str, Any]] = None,
    compliance_framework: Optional[str] = None,
    retrieval_helper: Optional[RetrievalHelper] = None,
    domain_config: Optional[DomainConfiguration] = None
) -> Dict[str, Any]:
    """
    PLACEHOLDER: Deep Research & Risk Modeling Workflow (STEP 3)
    
    This function will be implemented to perform deep research that:
    1. Analyzes features from STEP 2 (Feature Engineering)
    2. Performs domain-specific analysis
    3. Builds comprehensive likelihood models
    4. Builds comprehensive impact models
    5. Identifies contextual factors
    6. Creates risk calculations
    
    The implementation will integrate:
    - RiskModelReasoningWorkflow from risk_model_agents.py
    - Features from Feature Engineering (STEP 2)
    - Control Universe from Document Analysis (STEP 1)
    - Domain analysis and research
    
    Args:
        features: Recommended features from STEP 2 (Feature Engineering)
        control_universe: Control Universe from STEP 1 (Document Analysis)
        domain_context: Domain-specific context and analysis
        compliance_framework: Compliance framework (e.g., 'SOC2', 'GDPR')
        retrieval_helper: Optional retrieval helper instance
        domain_config: Domain configuration
    
    Returns:
        Dictionary containing:
        - measurable_signals: List of measurable signals
        - likelihood_inputs: Likelihood model inputs
        - impact_inputs: Impact model inputs
        - contextual_factors: Contextual factors
        - risk_model_blueprint: Complete risk model blueprint
    
    TODO: Implement this function to integrate:
        - RiskModelReasoningWorkflow from risk_model_agents.py
        - Deep analysis of features
        - Domain research
        - Comprehensive risk modeling
    """
    # Placeholder implementation
    logger.info("Deep Research & Risk Modeling workflow - PLACEHOLDER")
    logger.info("This will be implemented to perform deep research using:")
    logger.info(f"  - {len(features)} features from STEP 2")
    logger.info(f"  - Control Universe: {control_universe is not None}")
    logger.info(f"  - Domain Context: {domain_context is not None}")
    logger.info(f"  - Framework: {compliance_framework}")
    
    # TODO: Implement deep research workflow
    # This should:
    # 1. Use RiskModelReasoningWorkflow from risk_model_agents.py
    # 2. Analyze features deeply
    # 3. Perform domain-specific research
    # 4. Build comprehensive risk models
    
    return {
        "measurable_signals": [],
        "likelihood_inputs": [],
        "impact_inputs": [],
        "contextual_factors": [],
        "risk_model_blueprint": {},
        "status": "placeholder",
        "message": "Deep Research & Risk Modeling workflow will be implemented separately"
    }

# ============================================================================
# SEPARATE FEATURE GENERATION FUNCTIONS (Backward Compatibility)
# ============================================================================
# These functions are kept for backward compatibility but are part of STEP 3.
# For the full deep research workflow, use RiskModelReasoningWorkflow from
# risk_model_agents.py instead.
# ============================================================================

async def generate_impact_features(
    initial_state: FeatureEngineeringState,
    retrieval_helper: Optional[RetrievalHelper] = None,
    domain_config: Optional[DomainConfiguration] = None
) -> Dict[str, Any]:
    """
    Generate impact features separately. Part of STEP 3 (Deep Research & Risk Modeling).
    
    NOTE: This is a simpler version. For comprehensive deep research, use
    RiskModelReasoningWorkflow from risk_model_agents.py which performs:
    - Deep analysis of features from STEP 2
    - Domain-specific research
    - Comprehensive impact modeling using universal impact dimensions
    
    Args:
        initial_state: State containing previously generated features, knowledge documents, schemas, etc.
        retrieval_helper: Optional retrieval helper instance
        domain_config: Domain configuration (defaults to cybersecurity if not provided)
    
    Returns:
        Dictionary containing impact_features and updated state
    """
    if domain_config is None:
        domain_config = CYBERSECURITY_DOMAIN_CONFIG
    
    # Ensure domain_config is in state
    if "domain_config" not in initial_state or not initial_state.get("domain_config"):
        initial_state["domain_config"] = domain_config.model_dump() if hasattr(domain_config, 'model_dump') else domain_config.dict()
    
    # Set next_agent to impact_feature_generation
    initial_state["next_agent"] = "impact_feature_generation"
    
    # Use get_llm from dependencies
    llm = get_llm(temperature=0, model="gpt-4o-mini")
    workflow = create_feature_engineering_workflow(llm, retrieval_helper, domain_config)
    
    result = await workflow.ainvoke(initial_state)
    
    return {
        "impact_features": result.get("impact_features", []),
        "_full_state": dict(result)
    }


async def generate_likelihood_features(
    initial_state: FeatureEngineeringState,
    retrieval_helper: Optional[RetrievalHelper] = None,
    domain_config: Optional[DomainConfiguration] = None
) -> Dict[str, Any]:
    """
    Generate likelihood features separately. Part of STEP 3 (Deep Research & Risk Modeling).
    
    NOTE: This is a simpler version. For comprehensive deep research, use
    RiskModelReasoningWorkflow from risk_model_agents.py which performs:
    - Deep analysis of features from STEP 2
    - Domain-specific research
    - Comprehensive likelihood modeling using universal likelihood drivers
    
    Args:
        initial_state: State containing previously generated features (recommended_features, impact_features),
                      knowledge documents, schemas, etc.
        retrieval_helper: Optional retrieval helper instance
        domain_config: Domain configuration (defaults to cybersecurity if not provided)
    
    Returns:
        Dictionary containing likelihood_features and updated state
    """
    if domain_config is None:
        domain_config = CYBERSECURITY_DOMAIN_CONFIG
    
    # Ensure domain_config is in state
    if "domain_config" not in initial_state or not initial_state.get("domain_config"):
        initial_state["domain_config"] = domain_config.model_dump() if hasattr(domain_config, 'model_dump') else domain_config.dict()
    
    # Set next_agent to likelihood_feature_generation
    initial_state["next_agent"] = "likelihood_feature_generation"
    
    # Use get_llm from dependencies
    llm = get_llm(temperature=0, model="gpt-4o-mini")
    workflow = create_feature_engineering_workflow(llm, retrieval_helper, domain_config)
    
    result = await workflow.ainvoke(initial_state)
    
    return {
        "likelihood_features": result.get("likelihood_features", []),
        "_full_state": dict(result)
    }


async def generate_risk_features(
    initial_state: FeatureEngineeringState,
    retrieval_helper: Optional[RetrievalHelper] = None,
    domain_config: Optional[DomainConfiguration] = None
) -> Dict[str, Any]:
    """
    Generate risk features separately. Part of STEP 3 (Deep Research & Risk Modeling).
    
    NOTE: This is a simpler version. For comprehensive deep research, use
    RiskModelReasoningWorkflow from risk_model_agents.py which performs:
    - Deep analysis of features from STEP 2
    - Domain-specific research
    - Comprehensive risk modeling combining likelihood × impact with contextual factors
    
    Args:
        initial_state: State containing previously generated features (recommended_features, impact_features,
                      likelihood_features), knowledge documents, schemas, etc.
        retrieval_helper: Optional retrieval helper instance
        domain_config: Domain configuration (defaults to cybersecurity if not provided)
    
    Returns:
        Dictionary containing risk_features and updated state
    """
    if domain_config is None:
        domain_config = CYBERSECURITY_DOMAIN_CONFIG
    
    # Ensure domain_config is in state
    if "domain_config" not in initial_state or not initial_state.get("domain_config"):
        initial_state["domain_config"] = domain_config.model_dump() if hasattr(domain_config, 'model_dump') else domain_config.dict()
    
    # Set next_agent to risk_feature_generation
    initial_state["next_agent"] = "risk_feature_generation"
    
    # Use get_llm from dependencies
    llm = get_llm(temperature=0, model="gpt-4o-mini")
    workflow = create_feature_engineering_workflow(llm, retrieval_helper, domain_config)
    
    result = await workflow.ainvoke(initial_state)
    
    return {
        "risk_features": result.get("risk_features", []),
        "_full_state": dict(result)
    }


# ============================================================================
# STANDALONE AGENT EXECUTION FUNCTIONS
# ============================================================================

async def generate_standard_features(
    user_query: str,
    project_id: str,
    retrieval_helper: Optional[RetrievalHelper] = None,
    domain_config: Optional[DomainConfiguration] = None,
    initial_state: Optional[FeatureEngineeringState] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Generate standard metrics, KPIs, and counts features independently.
    
    This function runs only the FeatureRecommendationAgent to generate
    standard operational metrics for daily analysis.
    
    Args:
        user_query: User's query/question
        project_id: Project identifier
        retrieval_helper: Optional retrieval helper for knowledge/schema retrieval
        domain_config: Domain configuration (defaults to cybersecurity if not provided)
        initial_state: Optional initial state (if resuming from previous step)
        **kwargs: Additional state fields
    
    Returns:
        Dictionary containing recommended_features (standard metrics) and updated state
    """
    if domain_config is None:
        domain_config = CYBERSECURITY_DOMAIN_CONFIG
    
    llm = get_llm(temperature=0, model="gpt-4o-mini")
    
    # Create minimal workflow or run agent directly
    if initial_state is None:
        initial_state: FeatureEngineeringState = {
            "messages": [],
            "user_query": user_query,
            "analytical_intent": {},
            "relevant_schemas": [],
            "available_features": [],
            "clarifying_questions": [],
            "reasoning_plan": {},
            "recommended_features": [],
            "feature_dependencies": {},
            "relevance_scores": {},
            "next_agent": "feature_recommendation",
            "project_id": project_id,
            "histories": [],
            "schema_registry": {},
            "knowledge_documents": [],
            "domain_config": domain_config.model_dump() if hasattr(domain_config, 'model_dump') else domain_config.dict(),
            "identified_controls": None,
            "control_universe": None,
            **kwargs
        }
    else:
        initial_state = initial_state.copy()
        initial_state["next_agent"] = "feature_recommendation"
        initial_state["next_agent_after_features"] = "feature_combination"  # Skip risk, go to combination
    
    # Run through workflow up to feature recommendation
    workflow = create_feature_engineering_workflow(llm, retrieval_helper, domain_config)
    result = await workflow.ainvoke(initial_state)
    
    return {
        "recommended_features": result.get("recommended_features", []),
        "analytical_intent": result.get("analytical_intent", {}),
        "relevant_schemas": result.get("relevant_schemas", []),
        "knowledge_documents": result.get("knowledge_documents", []),
        "_full_state": dict(result)
    }


async def generate_risk_features_from_standard(
    standard_features: List[Dict[str, Any]],
    user_query: str,
    project_id: str,
    retrieval_helper: Optional[RetrievalHelper] = None,
    domain_config: Optional[DomainConfiguration] = None,
    knowledge_documents: Optional[List[Dict[str, Any]]] = None,
    schema_registry: Optional[Dict[str, Any]] = None,
    relevant_schemas: Optional[List[str]] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Generate risk, impact, and likelihood features from standard metrics independently.
    
    This function runs only the RiskFeatureEngineeringAgent to generate
    risk features using the standard metrics as building blocks.
    
    Args:
        standard_features: List of standard metrics/KPIs from FeatureRecommendationAgent
        user_query: Original user query
        project_id: Project identifier
        retrieval_helper: Optional retrieval helper for risk knowledge retrieval
        domain_config: Domain configuration (defaults to cybersecurity if not provided)
        knowledge_documents: Optional knowledge documents (will retrieve if not provided)
        schema_registry: Optional schema registry
        relevant_schemas: Optional list of relevant schema names
        **kwargs: Additional state fields
    
    Returns:
        Dictionary containing impact_features, likelihood_features, risk_features and updated state
    """
    if domain_config is None:
        domain_config = CYBERSECURITY_DOMAIN_CONFIG
    
    llm = get_llm(temperature=0, model="gpt-4o-mini")
    
    # Create initial state with standard features
    initial_state: FeatureEngineeringState = {
        "messages": [],
        "user_query": user_query,
        "analytical_intent": {},
        "relevant_schemas": relevant_schemas or [],
        "available_features": [],
        "clarifying_questions": [],
        "reasoning_plan": {},
        "recommended_features": standard_features,  # Standard features as input
        "feature_dependencies": {},
        "relevance_scores": {},
        "next_agent": "risk_feature_engineering",
        "project_id": project_id,
        "histories": [],
        "schema_registry": schema_registry or {},
        "knowledge_documents": knowledge_documents or [],
        "domain_config": domain_config.model_dump() if hasattr(domain_config, 'model_dump') else domain_config.dict(),
        "identified_controls": None,
        "control_universe": None,
        "impact_features": [],
        "likelihood_features": [],
        "risk_features": [],
        **kwargs
    }
    
    # Run through workflow starting at risk feature engineering
    workflow = create_feature_engineering_workflow(llm, retrieval_helper, domain_config)
    result = await workflow.ainvoke(initial_state)
    
    return {
        "impact_features": result.get("impact_features", []),
        "likelihood_features": result.get("likelihood_features", []),
        "risk_features": result.get("risk_features", []),
        "recommended_features": result.get("recommended_features", []),  # Standard features preserved
        "_full_state": dict(result)
    }


async def combine_features(
    standard_features: List[Dict[str, Any]],
    impact_features: Optional[List[Dict[str, Any]]] = None,
    likelihood_features: Optional[List[Dict[str, Any]]] = None,
    risk_features: Optional[List[Dict[str, Any]]] = None,
    domain_config: Optional[DomainConfiguration] = None
) -> Dict[str, Any]:
    """
    Combine standard features with risk features into a unified feature set.
    
    This function runs the FeatureCombinationAgent to merge all features
    and add metadata distinguishing feature categories.
    
    Args:
        standard_features: List of standard metrics/KPIs
        impact_features: Optional list of impact features
        likelihood_features: Optional list of likelihood features
        risk_features: Optional list of risk features
        domain_config: Domain configuration (defaults to cybersecurity if not provided)
    
    Returns:
        Dictionary containing combined recommended_features with feature_category metadata
    """
    if domain_config is None:
        domain_config = CYBERSECURITY_DOMAIN_CONFIG
    
    llm = get_llm(temperature=0, model="gpt-4o-mini")
    combination_agent = FeatureCombinationAgent(llm, domain_config)
    
    # Create minimal state
    state: FeatureEngineeringState = {
        "messages": [],
        "user_query": "",
        "analytical_intent": {},
        "relevant_schemas": [],
        "available_features": [],
        "clarifying_questions": [],
        "reasoning_plan": {},
        "recommended_features": standard_features,
        "feature_dependencies": {},
        "relevance_scores": {},
        "next_agent": "feature_combination",
        "project_id": "",
        "histories": [],
        "schema_registry": {},
        "knowledge_documents": [],
        "domain_config": domain_config.model_dump() if hasattr(domain_config, 'model_dump') else domain_config.dict(),
        "identified_controls": None,
        "control_universe": None,
        "impact_features": impact_features or [],
        "likelihood_features": likelihood_features or [],
        "risk_features": risk_features or []
    }
    
    # Run combination agent
    result = await combination_agent(state)
    
    return {
        "recommended_features": result.get("recommended_features", []),
        "summary": {
            "total_features": len(result.get("recommended_features", [])),
            "standard_metrics": len(standard_features),
            "impact_features": len(impact_features or []),
            "likelihood_features": len(likelihood_features or []),
            "risk_features": len(risk_features or [])
        },
        "_full_state": dict(result)
    }


if __name__ == "__main__":
    # Example usage
    import asyncio
    import json
    from datetime import datetime
    from pathlib import Path
    from app.agents.nodes.transform.domain_config import (
        get_domain_config,
        HR_COMPLIANCE_DOMAIN_CONFIG,
        RISK_MANAGEMENT_DOMAIN_CONFIG
    )
    
    async def main():
        # Create output directory
        output_dir = Path("transform/outputs")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Example 1: Cybersecurity domain (default)
        query_cybersecurity = """
        Create a report for Snyk that looks at the Critical and High vulnerabilities 
        for SOC2 compliance and provides risk, impact and likelihood metrics. I need to know SLAs, Repos, and Exploitability of the 
        vulnerabilities. Critical = 7 Days, High = 30 days since created and open and their risks.
        Yes use reachability. I want to understand the risk, impact and likelihood metrics for the report as well.
        Generate more than 20 features. 
        """
        
        # Example 2: HR Compliance domain
        query_hr = """
        Create a report for HR compliance that tracks training completion rates 
        for GDPR compliance across cornerstone and talent. I need to know completion rates, certification expiry,
        and compliance gaps by department. Critical deadline = 7 days, High = 30 days.
        """
        
        # Initialize retrieval helper if needed
        retrieval_helper = RetrievalHelper() if RetrievalHelper else None
        
        # Run with cybersecurity domain (default)
        print("=" * 80)
        print("CYBERSECURITY DOMAIN EXAMPLE")
        print("=" * 80)
        # Generate all features (regular compliance, impact, likelihood, and risk) in one run
        print("\n" + "=" * 80)
        print("GENERATING ALL FEATURES (Compliance, Impact, Likelihood, Risk)")
        print("=" * 80)
        result_cyber = await run_feature_engineering_pipeline(
            user_query=query_cybersecurity,
            project_id="cve_data",
            retrieval_helper=retrieval_helper,
            domain_config=get_domain_config("cybersecurity")
        )
        
        # Write all features to a file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"feature_engineering_output_{timestamp}.md"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# Feature Engineering Pipeline Output\n\n")
            f.write(f"**Generated at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Domain:** Cybersecurity\n")
            f.write(f"**Project ID:** cve_data\n\n")
            
            # Write recommended features
            all_features = result_cyber.get("recommended_features", [])
            f.write(f"## Recommended Features ({len(all_features)} total)\n\n")
            for i, feature in enumerate(all_features, 1):
                f.write(f"### {i}. {feature.get('feature_name', 'Unknown')}\n")
                f.write(f"**Natural Language Question:** {feature.get('natural_language_question', 'N/A')}\n")
                f.write(f"**Type:** {feature.get('feature_type', 'Unknown')}\n")
                f.write(f"**Calculation Logic:** {feature.get('calculation_logic', 'N/A')}\n")
                f.write(f"**Business Context:** {feature.get('business_context', 'N/A')}\n")
                f.write(f"**SOC2 Compliance Reasoning:** {feature.get('soc2_compliance_reasoning', 'N/A')}\n")
                f.write(f"**Transformation Layer:** {feature.get('transformation_layer', 'gold')}\n")
                f.write(f"**Time Series Type:** {feature.get('time_series_type', 'None')}\n")
                f.write(f"**Required Fields:** {', '.join(feature.get('required_fields', []))}\n")
                f.write(f"**Required Schemas:** {', '.join(feature.get('required_schemas', []))}\n")
                f.write("\n")
            
            # Write impact features
            impact_features = result_cyber.get("impact_features", [])
            f.write(f"\n## Impact Features ({len(impact_features)} total)\n\n")
            for i, feature in enumerate(impact_features, 1):
                f.write(f"### {i}. {feature.get('feature_name', 'Unknown')}\n")
                f.write(f"**Natural Language Question:** {feature.get('natural_language_question', 'N/A')}\n")
                f.write(f"**Description:** {feature.get('description', 'N/A')}\n")
                f.write(f"**Impact Type:** {feature.get('impact_type', 'N/A')}\n")
                f.write(f"**Feature Type:** {feature.get('feature_type', 'N/A')}\n")
                f.write(f"**Calculation Logic:** {feature.get('calculation_logic', 'N/A')}\n")
                f.write(f"**Related Features:** {', '.join(feature.get('related_features', []))}\n")
                f.write(f"**Knowledge Based Reasoning:** {feature.get('knowledge_based_reasoning', 'N/A')}\n")
                f.write("\n")
            
            # Write likelihood features
            likelihood_features = result_cyber.get("likelihood_features", [])
            f.write(f"\n## Likelihood Features ({len(likelihood_features)} total)\n\n")
            for i, feature in enumerate(likelihood_features, 1):
                f.write(f"### {i}. {feature.get('feature_name', 'Unknown')}\n")
                f.write(f"**Natural Language Question:** {feature.get('natural_language_question', 'N/A')}\n")
                f.write(f"**Description:** {feature.get('description', 'N/A')}\n")
                f.write(f"**Likelihood Type:** {feature.get('likelihood_type', 'N/A')}\n")
                f.write(f"**Feature Type:** {feature.get('feature_type', 'N/A')}\n")
                f.write(f"**Calculation Logic:** {feature.get('calculation_logic', 'N/A')}\n")
                f.write(f"**Related Features:** {', '.join(feature.get('related_features', []))}\n")
                f.write(f"**Knowledge Based Reasoning:** {feature.get('knowledge_based_reasoning', 'N/A')}\n")
                f.write("\n")
            
            # Write risk features
            risk_features = result_cyber.get("risk_features", [])
            f.write(f"\n## Risk Features ({len(risk_features)} total)\n\n")
            for i, feature in enumerate(risk_features, 1):
                f.write(f"### {i}. {feature.get('feature_name', 'Unknown')}\n")
                f.write(f"**Natural Language Question:** {feature.get('natural_language_question', 'N/A')}\n")
                f.write(f"**Description:** {feature.get('description', 'N/A')}\n")
                f.write(f"**Risk Type:** {feature.get('risk_type', 'N/A')}\n")
                f.write(f"**Feature Type:** {feature.get('feature_type', 'N/A')}\n")
                f.write(f"**Risk Formula:** {feature.get('risk_formula', 'N/A')}\n")
                f.write(f"**Calculation Logic:** {feature.get('calculation_logic', 'N/A')}\n")
                f.write(f"**Related Impact Features:** {', '.join(feature.get('related_impact_features', []))}\n")
                f.write(f"**Related Likelihood Features:** {', '.join(feature.get('related_likelihood_features', []))}\n")
                f.write(f"**Knowledge Based Reasoning:** {feature.get('knowledge_based_reasoning', 'N/A')}\n")
                f.write("\n")
            
            # Write feature calculation plan
            calculation_plan = result_cyber.get("feature_calculation_plan", {})
            if calculation_plan:
                f.write(f"\n## Feature Calculation Plan\n\n")
                f.write(f"**Plan ID:** {calculation_plan.get('plan_id', 'N/A')}\n")
                f.write(f"**Data Requirements Summary:** {calculation_plan.get('data_requirements_summary', 'N/A')}\n")
                f.write(f"**Overall Calculation Sequence:** {', '.join(calculation_plan.get('overall_calculation_sequence', []))}\n\n")
                f.write("### Feature Plans\n\n")
                for plan in calculation_plan.get('features', []):
                    f.write(f"#### {plan.get('feature_name', 'Unknown')}\n")
                    f.write(f"**Required Fields:** {', '.join(plan.get('required_fields', []))}\n")
                    f.write(f"**Aggregations:** {', '.join(plan.get('aggregations', []))}\n")
                    f.write(f"**Filters:** {', '.join(plan.get('filters', []))}\n")
                    f.write(f"**Dependencies:** {', '.join(plan.get('dependencies', []))}\n")
                    f.write(f"**Knowledge Based Reasoning:** {plan.get('knowledge_based_reasoning', 'N/A')}\n")
                    f.write("\n")
            
            # Write feature dependencies
            feature_dependencies = result_cyber.get("feature_dependencies", {})
            if feature_dependencies:
                f.write(f"\n## Feature Dependencies\n\n")
                f.write(f"```json\n{json.dumps(feature_dependencies, indent=2)}\n```\n\n")
            
            # Write relevance scores
            relevance_scores = result_cyber.get("relevance_scores", {})
            if relevance_scores:
                f.write(f"\n## Relevance Scores\n\n")
                f.write(f"```json\n{json.dumps(relevance_scores, indent=2)}\n```\n\n")
        
        print(f"\n✅ All features written to: {output_file.absolute()}")
        
        print("\nCLARIFYING QUESTIONS:")
        for i, q in enumerate(result_cyber["clarifying_questions"], 1):
            print(f"{i}. {q}")
        
        # Combine and display all features in markdown format
        all_features = result_cyber.get("recommended_features", [])
        
        print("\n" + "=" * 80)
        print("ALL RECOMMENDED FEATURES WITH SOC2 COMPLIANCE REASONING")
        print("=" * 80)
        print(f"\n## Total Features: {len(all_features)}\n")
        
        for i, feature in enumerate(all_features, 1):
            # Extract feature name - clean it up if it contains extra text
            feature_name = feature.get('feature_name', '')
            if not feature_name or feature_name == 'Unknown':
                # Try to extract from raw_text if available
                raw_text = feature.get('raw_text', '')
                if raw_text:
                    # Extract just the feature name part
                    name_match = re.search(r'(?:Feature\s+Name|Name)[:\*]?\s*(?:\*\*)?\s*([^-]+?)(?:\s*-\s*|$)', raw_text, re.IGNORECASE)
                    if name_match:
                        feature_name = name_match.group(1).strip()
                    else:
                        # Fallback: use first part before dash or colon
                        parts = re.split(r'[:\-]', raw_text, 2)
                        feature_name = parts[1].strip() if len(parts) > 1 else raw_text[:50].strip()
                else:
                    feature_name = f"Feature {i}"
            
            # Clean feature name - remove numbering and extra formatting
            feature_name = re.sub(r'^\d+\.\s*', '', feature_name)  # Remove leading number
            feature_name = re.sub(r'\*\*', '', feature_name)  # Remove markdown bold
            feature_name = feature_name.strip()
            
            feature_type = feature.get('feature_type', 'Unknown')
            calculation_logic = feature.get('calculation_logic', 'N/A')
            business_context = feature.get('business_context', 'N/A')
            soc2_reasoning = feature.get('soc2_compliance_reasoning', feature.get('business_context', 'N/A'))
            
            # Clean up values - remove markdown formatting
            if feature_type != 'Unknown':
                feature_type = re.sub(r'\*\*', '', feature_type).strip()
            if calculation_logic != 'N/A':
                calculation_logic = re.sub(r'`', '', calculation_logic).strip()
            if business_context != 'N/A':
                business_context = business_context.strip()
            if soc2_reasoning and soc2_reasoning != 'N/A':
                soc2_reasoning = soc2_reasoning.strip()
            
            # Extract natural language question
            natural_language_question = feature.get('natural_language_question', '')
            if not natural_language_question or natural_language_question == 'N/A':
                # Generate from feature name if not found
                natural_language_question = f"What is the {feature_name.lower().replace('_', ' ')}?"
            
            # Only print if we have a valid feature name (not the full raw text)
            if len(feature_name) < 200:  # Reasonable feature name length
                print(f"### {i}. {feature_name}")
                if natural_language_question and natural_language_question != 'N/A':
                    print(f"**Natural Language Question:** {natural_language_question}")
                if feature_type != 'Unknown':
                    print(f"**Type:** {feature_type}")
                if calculation_logic != 'N/A':
                    print(f"**Calculation Logic:** {calculation_logic}")
                if business_context != 'N/A':
                    print(f"**Business Context:** {business_context}")
                if soc2_reasoning and soc2_reasoning != 'N/A':
                    print(f"**SOC2 Compliance Reasoning:** {soc2_reasoning}")
                print()  # Empty line between features
        
        # Follow-up: Add more features
        print("\n" + "=" * 80)
        print("FOLLOW-UP: ADDING MORE FEATURES")
        print("=" * 80)
        
        # Create a follow-up state from the previous result
        # Use the full state if available, otherwise reconstruct from returned fields
        if "_full_state" in result_cyber:
            follow_up_state: FeatureEngineeringState = result_cyber["_full_state"].copy()
        else:
            # Reconstruct state from returned fields
            follow_up_state: FeatureEngineeringState = {
                "messages": [],
                "user_query": query_cybersecurity,
                "analytical_intent": result_cyber.get("analytical_intent", {}),
                "relevant_schemas": result_cyber.get("relevant_schemas", []),
                "available_features": [],
                "clarifying_questions": result_cyber.get("clarifying_questions", []),
                "reasoning_plan": result_cyber.get("reasoning_plan", {}),
                "recommended_features": result_cyber.get("recommended_features", []),
                "feature_dependencies": result_cyber.get("feature_dependencies", {}),
                "relevance_scores": result_cyber.get("relevance_scores", {}),
                "next_agent": "feature_recommendation",
                "project_id": "cve_data",
                "histories": [],
                "schema_registry": {},
                "knowledge_documents": result_cyber.get("knowledge_documents", []),
                "domain_config": {},
                "validation_expectations": [],
                "refining_instructions": None,
                "refining_examples": [],
                "feature_generation_instructions": None,
                "feature_generation_examples": []
            }
        
        # Modify state for follow-up
        follow_up_state["next_agent"] = "feature_recommendation"  # Go back to feature recommendation
        follow_up_state["feature_generation_instructions"] = "Generate 5 additional features that complement the existing 10 features. Focus on cyber risk quantification metrics for Compliance based on assets, softwares and vulnerabilities. For each feature, provide detailed SOC2 compliance reasoning explaining which SOC2 control domains it addresses (e.g., CC6.1, CC7.1, CC7.2, etc.) and how it supports compliance monitoring."
        follow_up_state["feature_generation_examples"] = []
        
        # Run follow-up to add more features
        result_followup = await run_feature_engineering_pipeline(
            initial_state=follow_up_state,
            retrieval_helper=retrieval_helper,
            domain_config=get_domain_config("cybersecurity")
        )
        
        # Write follow-up features to file
        followup_output_file = output_dir / f"feature_engineering_followup_{timestamp}.md"
        with open(followup_output_file, 'w', encoding='utf-8') as f:
            f.write("# Feature Engineering Pipeline Output (Follow-up)\n\n")
            f.write(f"**Generated at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Domain:** Cybersecurity\n")
            f.write(f"**Project ID:** cve_data\n\n")
            
            # Combine and display all features (initial + follow-up) in markdown format
            all_features_combined = result_followup.get("recommended_features", [])
            
            f.write(f"## Recommended Features (Combined - {len(all_features_combined)} total)\n\n")
            for i, feature in enumerate(all_features_combined, 1):
                feature_name = feature.get('feature_name', feature.get('raw_text', 'Unknown'))
                feature_type = feature.get('feature_type', 'Unknown')
                calculation_logic = feature.get('calculation_logic', 'N/A')
                natural_language_question = feature.get('natural_language_question', '')
                business_context = feature.get('business_context', 'N/A')
                soc2_reasoning = feature.get('soc2_compliance_reasoning', feature.get('business_context', 'N/A'))
                
                # Generate natural language question if not found
                if not natural_language_question or natural_language_question == 'N/A':
                    natural_language_question = f"What is the {feature_name.lower().replace('_', ' ')}?"
                
                f.write(f"### {i}. {feature_name}\n")
                if natural_language_question and natural_language_question != 'N/A':
                    f.write(f"**Natural Language Question:** {natural_language_question}\n")
                f.write(f"**Type:** {feature_type}\n")
                f.write(f"**Calculation Logic:** {calculation_logic}\n")
                f.write(f"**Business Context:** {business_context}\n")
                f.write(f"**SOC2 Compliance Reasoning:** {soc2_reasoning}\n")
                f.write(f"**Transformation Layer:** {feature.get('transformation_layer', 'gold')}\n")
                f.write(f"**Time Series Type:** {feature.get('time_series_type', 'None')}\n")
                f.write("\n")
            
            # Write impact, likelihood, and risk features from follow-up
            impact_features_followup = result_followup.get("impact_features", [])
            likelihood_features_followup = result_followup.get("likelihood_features", [])
            risk_features_followup = result_followup.get("risk_features", [])
            
            if impact_features_followup:
                f.write(f"\n## Impact Features (Follow-up - {len(impact_features_followup)} total)\n\n")
                for i, feature in enumerate(impact_features_followup, 1):
                    f.write(f"### {i}. {feature.get('feature_name', 'Unknown')}\n")
                    f.write(f"**Natural Language Question:** {feature.get('natural_language_question', 'N/A')}\n")
                    f.write(f"**Description:** {feature.get('description', 'N/A')}\n")
                    f.write(f"**Impact Type:** {feature.get('impact_type', 'N/A')}\n")
                    f.write(f"**Calculation Logic:** {feature.get('calculation_logic', 'N/A')}\n")
                    f.write("\n")
            
            if likelihood_features_followup:
                f.write(f"\n## Likelihood Features (Follow-up - {len(likelihood_features_followup)} total)\n\n")
                for i, feature in enumerate(likelihood_features_followup, 1):
                    f.write(f"### {i}. {feature.get('feature_name', 'Unknown')}\n")
                    f.write(f"**Natural Language Question:** {feature.get('natural_language_question', 'N/A')}\n")
                    f.write(f"**Description:** {feature.get('description', 'N/A')}\n")
                    f.write(f"**Likelihood Type:** {feature.get('likelihood_type', 'N/A')}\n")
                    f.write(f"**Calculation Logic:** {feature.get('calculation_logic', 'N/A')}\n")
                    f.write("\n")
            
            if risk_features_followup:
                f.write(f"\n## Risk Features (Follow-up - {len(risk_features_followup)} total)\n\n")
                for i, feature in enumerate(risk_features_followup, 1):
                    f.write(f"### {i}. {feature.get('feature_name', 'Unknown')}\n")
                    f.write(f"**Natural Language Question:** {feature.get('natural_language_question', 'N/A')}\n")
                    f.write(f"**Description:** {feature.get('description', 'N/A')}\n")
                    f.write(f"**Risk Type:** {feature.get('risk_type', 'N/A')}\n")
                    f.write(f"**Risk Formula:** {feature.get('risk_formula', 'N/A')}\n")
                    f.write(f"**Calculation Logic:** {feature.get('calculation_logic', 'N/A')}\n")
                    f.write("\n")
        
        print(f"\n✅ Follow-up features written to: {followup_output_file.absolute()}")
        
        print("\n" + "=" * 80)
        print("ALL RECOMMENDED FEATURES WITH SOC2 COMPLIANCE REASONING (COMBINED)")
        print("=" * 80)
        print(f"\n## Total Features: {len(all_features_combined)}\n")
        
        for i, feature in enumerate(all_features_combined, 1):
            feature_name = feature.get('feature_name', feature.get('raw_text', 'Unknown'))
            feature_type = feature.get('feature_type', 'Unknown')
            calculation_logic = feature.get('calculation_logic', 'N/A')
            natural_language_question = feature.get('natural_language_question', '')
            business_context = feature.get('business_context', 'N/A')
            soc2_reasoning = feature.get('soc2_compliance_reasoning', feature.get('business_context', 'N/A'))
            
            # Generate natural language question if not found
            if not natural_language_question or natural_language_question == 'N/A':
                natural_language_question = f"What is the {feature_name.lower().replace('_', ' ')}?"
            
            print(f"### {i}. {feature_name}")
            if natural_language_question and natural_language_question != 'N/A':
                print(f"**Natural Language Question:** {natural_language_question}")
            print(f"**Type:** {feature_type}")
            print(f"**Calculation Logic:** {calculation_logic}")
            print(f"**Business Context:** {business_context}")
            print(f"**SOC2 Compliance Reasoning:** {soc2_reasoning}")
            print()  # Empty line between features
        
        # Print impact, likelihood, and risk features summary
        print("\n" + "=" * 80)
        print("IMPACT, LIKELIHOOD, AND RISK FEATURES SUMMARY")
        print("=" * 80)
        
        impact_features = result_cyber.get("impact_features", [])
        likelihood_features = result_cyber.get("likelihood_features", [])
        risk_features = result_cyber.get("risk_features", [])
        
        print(f"\n### Impact Features: {len(impact_features)}")
        for i, feature in enumerate(impact_features, 1):
            print(f"  {i}. {feature.get('feature_name', 'Unknown')}: {feature.get('natural_language_question', 'N/A')}")
        
        print(f"\n### Likelihood Features: {len(likelihood_features)}")
        for i, feature in enumerate(likelihood_features, 1):
            print(f"  {i}. {feature.get('feature_name', 'Unknown')}: {feature.get('natural_language_question', 'N/A')}")
        
        print(f"\n### Risk Features: {len(risk_features)}")
        for i, feature in enumerate(risk_features, 1):
            print(f"  {i}. {feature.get('feature_name', 'Unknown')}: {feature.get('natural_language_question', 'N/A')}")
        
        # Run with HR compliance domain - COMMENTED OUT
        """
        
        print("\n" + "=" * 80)
        print("HR COMPLIANCE DOMAIN EXAMPLE")
        print("=" * 80)
        
        # Step 1: Generate regular compliance features
        print("\n" + "=" * 80)
        print("STEP 1: GENERATING REGULAR COMPLIANCE FEATURES")
        print("=" * 80)
        result_hr = await run_feature_engineering_pipeline(
            user_query=query_hr,
            project_id="cornerstone_learning",
            retrieval_helper=retrieval_helper,
            domain_config=HR_COMPLIANCE_DOMAIN_CONFIG
        )
        
        # Step 2: Generate impact features
        print("\n" + "=" * 80)
        print("STEP 2: GENERATING IMPACT FEATURES")
        print("=" * 80)
        impact_result_hr = await generate_impact_features(
            initial_state=result_hr["_full_state"],
            retrieval_helper=retrieval_helper,
            domain_config=HR_COMPLIANCE_DOMAIN_CONFIG
        )
        result_hr["impact_features"] = impact_result_hr["impact_features"]
        result_hr["_full_state"] = impact_result_hr["_full_state"]
        
        # Step 3: Generate likelihood features
        print("\n" + "=" * 80)
        print("STEP 3: GENERATING LIKELIHOOD FEATURES")
        print("=" * 80)
        likelihood_result_hr = await generate_likelihood_features(
            initial_state=impact_result_hr["_full_state"],
            retrieval_helper=retrieval_helper,
            domain_config=HR_COMPLIANCE_DOMAIN_CONFIG
        )
        result_hr["likelihood_features"] = likelihood_result_hr["likelihood_features"]
        result_hr["_full_state"] = likelihood_result_hr["_full_state"]
        
        # Step 4: Generate risk features
        print("\n" + "=" * 80)
        print("STEP 4: GENERATING RISK FEATURES")
        print("=" * 80)
        risk_result_hr = await generate_risk_features(
            initial_state=likelihood_result_hr["_full_state"],
            retrieval_helper=retrieval_helper,
            domain_config=HR_COMPLIANCE_DOMAIN_CONFIG
        )
        result_hr["risk_features"] = risk_result_hr["risk_features"]
        result_hr["_full_state"] = risk_result_hr["_full_state"]
        
        # Write all features to a file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file_hr = output_dir / f"feature_engineering_output_hr_{timestamp}.md"
        
        with open(output_file_hr, 'w', encoding='utf-8') as f:
            f.write("# Feature Engineering Pipeline Output (HR Compliance)\n\n")
            f.write(f"**Generated at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Domain:** HR Compliance\n")
            f.write(f"**Project ID:** cornerstone_learning\n\n")
            
            # Write recommended features
            all_features_hr = result_hr.get("recommended_features", [])
            f.write(f"## Recommended Features ({len(all_features_hr)} total)\n\n")
            for i, feature in enumerate(all_features_hr, 1):
                f.write(f"### {i}. {feature.get('feature_name', 'Unknown')}\n")
                f.write(f"**Natural Language Question:** {feature.get('natural_language_question', 'N/A')}\n")
                f.write(f"**Type:** {feature.get('feature_type', 'Unknown')}\n")
                f.write(f"**Calculation Logic:** {feature.get('calculation_logic', 'N/A')}\n")
                f.write(f"**Business Context:** {feature.get('business_context', 'N/A')}\n")
                f.write(f"**Compliance Reasoning:** {feature.get('soc2_compliance_reasoning', 'N/A')}\n")
                f.write(f"**Transformation Layer:** {feature.get('transformation_layer', 'gold')}\n")
                f.write(f"**Time Series Type:** {feature.get('time_series_type', 'None')}\n")
                f.write(f"**Required Fields:** {', '.join(feature.get('required_fields', []))}\n")
                f.write(f"**Required Schemas:** {', '.join(feature.get('required_schemas', []))}\n")
                f.write("\n")
            
            # Write impact features
            impact_features_hr = result_hr.get("impact_features", [])
            f.write(f"\n## Impact Features ({len(impact_features_hr)} total)\n\n")
            for i, feature in enumerate(impact_features_hr, 1):
                f.write(f"### {i}. {feature.get('feature_name', 'Unknown')}\n")
                f.write(f"**Natural Language Question:** {feature.get('natural_language_question', 'N/A')}\n")
                f.write(f"**Description:** {feature.get('description', 'N/A')}\n")
                f.write(f"**Impact Type:** {feature.get('impact_type', 'N/A')}\n")
                f.write(f"**Feature Type:** {feature.get('feature_type', 'N/A')}\n")
                f.write(f"**Calculation Logic:** {feature.get('calculation_logic', 'N/A')}\n")
                f.write(f"**Related Features:** {', '.join(feature.get('related_features', []))}\n")
                f.write(f"**Knowledge Based Reasoning:** {feature.get('knowledge_based_reasoning', 'N/A')}\n")
                f.write("\n")
            
            # Write likelihood features
            likelihood_features_hr = result_hr.get("likelihood_features", [])
            f.write(f"\n## Likelihood Features ({len(likelihood_features_hr)} total)\n\n")
            for i, feature in enumerate(likelihood_features_hr, 1):
                f.write(f"### {i}. {feature.get('feature_name', 'Unknown')}\n")
                f.write(f"**Natural Language Question:** {feature.get('natural_language_question', 'N/A')}\n")
                f.write(f"**Description:** {feature.get('description', 'N/A')}\n")
                f.write(f"**Likelihood Type:** {feature.get('likelihood_type', 'N/A')}\n")
                f.write(f"**Feature Type:** {feature.get('feature_type', 'N/A')}\n")
                f.write(f"**Calculation Logic:** {feature.get('calculation_logic', 'N/A')}\n")
                f.write(f"**Related Features:** {', '.join(feature.get('related_features', []))}\n")
                f.write(f"**Knowledge Based Reasoning:** {feature.get('knowledge_based_reasoning', 'N/A')}\n")
                f.write("\n")
            
            # Write risk features
            risk_features_hr = result_hr.get("risk_features", [])
            f.write(f"\n## Risk Features ({len(risk_features_hr)} total)\n\n")
            for i, feature in enumerate(risk_features_hr, 1):
                f.write(f"### {i}. {feature.get('feature_name', 'Unknown')}\n")
                f.write(f"**Natural Language Question:** {feature.get('natural_language_question', 'N/A')}\n")
                f.write(f"**Description:** {feature.get('description', 'N/A')}\n")
                f.write(f"**Risk Type:** {feature.get('risk_type', 'N/A')}\n")
                f.write(f"**Feature Type:** {feature.get('feature_type', 'N/A')}\n")
                f.write(f"**Risk Formula:** {feature.get('risk_formula', 'N/A')}\n")
                f.write(f"**Calculation Logic:** {feature.get('calculation_logic', 'N/A')}\n")
                f.write(f"**Related Impact Features:** {', '.join(feature.get('related_impact_features', []))}\n")
                f.write(f"**Related Likelihood Features:** {', '.join(feature.get('related_likelihood_features', []))}\n")
                f.write(f"**Knowledge Based Reasoning:** {feature.get('knowledge_based_reasoning', 'N/A')}\n")
                f.write("\n")
        
        print(f"\n✅ All HR compliance features written to: {output_file_hr.absolute()}")
        
        print("\nCLARIFYING QUESTIONS:")
        for i, q in enumerate(result_hr["clarifying_questions"], 1):
            print(f"{i}. {q}")
        
        print("\n" + "=" * 80)
        print("RECOMMENDED FEATURES (HR Domain)")
        print("=" * 80)
        for i, feature in enumerate(result_hr["recommended_features"], 1):
            print(f"{i}. {feature.get('feature_name', feature.get('raw_text', 'Unknown'))}")
        
        # Print impact, likelihood, and risk features summary
        print("\n" + "=" * 80)
        print("IMPACT, LIKELIHOOD, AND RISK FEATURES SUMMARY (HR Domain)")
        print("=" * 80)
        
        impact_features_hr = result_hr.get("impact_features", [])
        likelihood_features_hr = result_hr.get("likelihood_features", [])
        risk_features_hr = result_hr.get("risk_features", [])
        
        print(f"\n### Impact Features: {len(impact_features_hr)}")
        for i, feature in enumerate(impact_features_hr, 1):
            print(f"  {i}. {feature.get('feature_name', 'Unknown')}: {feature.get('natural_language_question', 'N/A')}")
        
        print(f"\n### Likelihood Features: {len(likelihood_features_hr)}")
        for i, feature in enumerate(likelihood_features_hr, 1):
            print(f"  {i}. {feature.get('feature_name', 'Unknown')}: {feature.get('natural_language_question', 'N/A')}")
        
        print(f"\n### Risk Features: {len(risk_features_hr)}")
        for i, feature in enumerate(risk_features_hr, 1):
            print(f"  {i}. {feature.get('feature_name', 'Unknown')}: {feature.get('natural_language_question', 'N/A')}")
        
        # Follow-up: Add more HR compliance features
        print("\n" + "=" * 80)
        print("FOLLOW-UP: ADDING MORE HR COMPLIANCE FEATURES")
        print("=" * 80)
        
        # Create a follow-up state from the previous result
        # Use the full state if available, otherwise reconstruct from returned fields
        if "_full_state" in result_hr:
            follow_up_state_hr: FeatureEngineeringState = result_hr["_full_state"].copy()
        else:
            # Reconstruct state from returned fields
            follow_up_state_hr: FeatureEngineeringState = {
                "messages": [],
                "user_query": query_hr,
                "analytical_intent": result_hr.get("analytical_intent", {}),
                "relevant_schemas": result_hr.get("relevant_schemas", []),
                "available_features": [],
                "clarifying_questions": result_hr.get("clarifying_questions", []),
                "reasoning_plan": result_hr.get("reasoning_plan", {}),
                "recommended_features": result_hr.get("recommended_features", []),
                "feature_dependencies": result_hr.get("feature_dependencies", {}),
                "relevance_scores": result_hr.get("relevance_scores", {}),
                "next_agent": "feature_recommendation",
                "project_id": "cornerstone_learning",
                "histories": [],
                "schema_registry": {},
                "knowledge_documents": result_hr.get("knowledge_documents", []),
                "domain_config": {},
                "validation_expectations": [],
                "refining_instructions": None,
                "refining_examples": [],
                "feature_generation_instructions": None,
                "feature_generation_examples": []
            }
        
        # Modify state for follow-up
        follow_up_state_hr["next_agent"] = "feature_recommendation"  # Go back to feature recommendation
        follow_up_state_hr["feature_generation_instructions"] = "Generate 5 additional features that complement the existing features. Focus on HR compliance metrics for GDPR compliance based on training completion, certification expiry, and compliance gaps. For each feature, provide detailed GDPR compliance reasoning explaining which GDPR articles it addresses and how it supports compliance monitoring."
        follow_up_state_hr["feature_generation_examples"] = []
        
        # Run follow-up to add more features
        result_followup_hr = await run_feature_engineering_pipeline(
            initial_state=follow_up_state_hr,
            retrieval_helper=retrieval_helper,
            domain_config=HR_COMPLIANCE_DOMAIN_CONFIG
        )
        
        # Write follow-up features to file
        followup_output_file_hr = output_dir / f"feature_engineering_followup_hr_{timestamp}.md"
        with open(followup_output_file_hr, 'w', encoding='utf-8') as f:
            f.write("# Feature Engineering Pipeline Output (HR Compliance - Follow-up)\n\n")
            f.write(f"**Generated at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Domain:** HR Compliance\n")
            f.write(f"**Project ID:** cornerstone_learning\n\n")
            
            # Combine and display all features (initial + follow-up) in markdown format
            all_features_combined_hr = result_followup_hr.get("recommended_features", [])
            
            f.write(f"## Recommended Features (Combined - {len(all_features_combined_hr)} total)\n\n")
            for i, feature in enumerate(all_features_combined_hr, 1):
                feature_name = feature.get('feature_name', feature.get('raw_text', 'Unknown'))
                feature_type = feature.get('feature_type', 'Unknown')
                calculation_logic = feature.get('calculation_logic', 'N/A')
                natural_language_question = feature.get('natural_language_question', '')
                business_context = feature.get('business_context', 'N/A')
                compliance_reasoning = feature.get('soc2_compliance_reasoning', feature.get('business_context', 'N/A'))
                
                # Generate natural language question if not found
                if not natural_language_question or natural_language_question == 'N/A':
                    natural_language_question = f"What is the {feature_name.lower().replace('_', ' ')}?"
                
                f.write(f"### {i}. {feature_name}\n")
                if natural_language_question and natural_language_question != 'N/A':
                    f.write(f"**Natural Language Question:** {natural_language_question}\n")
                f.write(f"**Type:** {feature_type}\n")
                f.write(f"**Calculation Logic:** {calculation_logic}\n")
                f.write(f"**Business Context:** {business_context}\n")
                f.write(f"**Compliance Reasoning:** {compliance_reasoning}\n")
                f.write(f"**Transformation Layer:** {feature.get('transformation_layer', 'gold')}\n")
                f.write(f"**Time Series Type:** {feature.get('time_series_type', 'None')}\n")
                f.write("\n")
            
            # Write impact, likelihood, and risk features from follow-up
            impact_features_followup_hr = result_followup_hr.get("impact_features", [])
            likelihood_features_followup_hr = result_followup_hr.get("likelihood_features", [])
            risk_features_followup_hr = result_followup_hr.get("risk_features", [])
            
            if impact_features_followup_hr:
                f.write(f"\n## Impact Features (Follow-up - {len(impact_features_followup_hr)} total)\n\n")
                for i, feature in enumerate(impact_features_followup_hr, 1):
                    f.write(f"### {i}. {feature.get('feature_name', 'Unknown')}\n")
                    f.write(f"**Natural Language Question:** {feature.get('natural_language_question', 'N/A')}\n")
                    f.write(f"**Description:** {feature.get('description', 'N/A')}\n")
                    f.write(f"**Impact Type:** {feature.get('impact_type', 'N/A')}\n")
                    f.write(f"**Calculation Logic:** {feature.get('calculation_logic', 'N/A')}\n")
                    f.write("\n")
            
            if likelihood_features_followup_hr:
                f.write(f"\n## Likelihood Features (Follow-up - {len(likelihood_features_followup_hr)} total)\n\n")
                for i, feature in enumerate(likelihood_features_followup_hr, 1):
                    f.write(f"### {i}. {feature.get('feature_name', 'Unknown')}\n")
                    f.write(f"**Natural Language Question:** {feature.get('natural_language_question', 'N/A')}\n")
                    f.write(f"**Description:** {feature.get('description', 'N/A')}\n")
                    f.write(f"**Likelihood Type:** {feature.get('likelihood_type', 'N/A')}\n")
                    f.write(f"**Calculation Logic:** {feature.get('calculation_logic', 'N/A')}\n")
                    f.write("\n")
            
            if risk_features_followup_hr:
                f.write(f"\n## Risk Features (Follow-up - {len(risk_features_followup_hr)} total)\n\n")
                for i, feature in enumerate(risk_features_followup_hr, 1):
                    f.write(f"### {i}. {feature.get('feature_name', 'Unknown')}\n")
                    f.write(f"**Natural Language Question:** {feature.get('natural_language_question', 'N/A')}\n")
                    f.write(f"**Description:** {feature.get('description', 'N/A')}\n")
                    f.write(f"**Risk Type:** {feature.get('risk_type', 'N/A')}\n")
                    f.write(f"**Risk Formula:** {feature.get('risk_formula', 'N/A')}\n")
                    f.write(f"**Calculation Logic:** {feature.get('calculation_logic', 'N/A')}\n")
                    f.write("\n")
        
        print(f"\n✅ Follow-up HR compliance features written to: {followup_output_file_hr.absolute()}")
        
        print("\n" + "=" * 80)
        print("ALL RECOMMENDED FEATURES WITH COMPLIANCE REASONING (COMBINED - HR Domain)")
        print("=" * 80)
        print(f"\n## Total Features: {len(all_features_combined_hr)}\n")
        
        for i, feature in enumerate(all_features_combined_hr, 1):
            feature_name = feature.get('feature_name', feature.get('raw_text', 'Unknown'))
            feature_type = feature.get('feature_type', 'Unknown')
            calculation_logic = feature.get('calculation_logic', 'N/A')
            natural_language_question = feature.get('natural_language_question', '')
            business_context = feature.get('business_context', 'N/A')
            compliance_reasoning = feature.get('soc2_compliance_reasoning', feature.get('business_context', 'N/A'))
            
            # Generate natural language question if not found
            if not natural_language_question or natural_language_question == 'N/A':
                natural_language_question = f"What is the {feature_name.lower().replace('_', ' ')}?"
            
            print(f"### {i}. {feature_name}")
            if natural_language_question and natural_language_question != 'N/A':
                print(f"**Natural Language Question:** {natural_language_question}")
            print(f"**Type:** {feature_type}")
            print(f"**Calculation Logic:** {calculation_logic}")
            print(f"**Business Context:** {business_context}")
            print(f"**Compliance Reasoning:** {compliance_reasoning}")
            print()  # Empty line between features
        """
        
    asyncio.run(main())
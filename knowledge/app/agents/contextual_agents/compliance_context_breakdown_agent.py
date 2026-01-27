"""
Compliance Context Breakdown Agent
Specialized agent for breaking down compliance/risk management queries.

Handles:
- Frameworks (SOC2, HIPAA, ISO 27001, GDPR, etc.)
- Actors (Compliance Officer, Auditor, CISO, etc.)
- Compliance controls, evidences, requirements
- Features for compliance
- Keywords, topics, patterns
"""
import logging
from typing import Dict, List, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI
import json

from .base_context_breakdown_agent import BaseContextBreakdownAgent, ContextBreakdown

logger = logging.getLogger(__name__)


class ComplianceContextBreakdownAgent(BaseContextBreakdownAgent):
    """
    Agent that breaks down compliance and risk management queries using LLM.
    
    Specializes in:
    - Compliance framework queries (SOC2, HIPAA, etc.)
    - Control and requirement queries
    - Evidence and policy queries
    - Risk assessment queries
    - Actor-specific queries
    """
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini",
        prompts_file: Optional[str] = None
    ):
        """
        Initialize the compliance context breakdown agent.
        
        Args:
            llm: Optional LLM instance
            model_name: Model name if llm not provided
            prompts_file: Path to vector_store_prompts.json
        """
        super().__init__(llm, model_name, prompts_file)
    
    async def _detect_query_type(self, user_question: str) -> Dict[str, Any]:
        """
        Detect the type of compliance query from user question.
        
        Returns:
            Dictionary with query_type and detected entities
        """
        question_lower = user_question.lower()
        
        query_type = {
            "is_framework_query": any(keyword in question_lower for keyword in [
                "soc2", "hipaa", "iso 27001", "gdpr", "nist", "pci-dss", "framework"
            ]),
            "is_control_query": any(keyword in question_lower for keyword in [
                "control", "requirement", "mandate"
            ]),
            "is_evidence_query": any(keyword in question_lower for keyword in [
                "evidence", "proof", "documentation", "artifact"
            ]),
            "is_risk_query": any(keyword in question_lower for keyword in [
                "risk", "vulnerability", "threat", "assessment"
            ]),
            "is_policy_query": any(keyword in question_lower for keyword in [
                "policy", "procedure", "guideline", "standard"
            ]),
            "is_actor_query": any(keyword in question_lower for keyword in [
                "compliance officer", "auditor", "ciso", "analyst", "who"
            ])
        }
        
        # Detect frameworks mentioned
        detected_frameworks = []
        framework_keywords = {
            "SOC2": ["soc2", "soc 2"],
            "HIPAA": ["hipaa"],
            "ISO 27001": ["iso 27001", "iso27001"],
            "GDPR": ["gdpr"],
            "NIST": ["nist"],
            "PCI-DSS": ["pci-dss", "pci dss", "pcidss"]
        }
        for framework, keywords in framework_keywords.items():
            if any(kw in question_lower for kw in keywords):
                detected_frameworks.append(framework)
        
        # Detect actors mentioned
        detected_actors = []
        actor_keywords = {
            "Compliance Officer": ["compliance officer"],
            "Auditor": ["auditor"],
            "CISO": ["ciso", "chief information security officer"],
            "Security Analyst": ["security analyst"],
            "Data Analyst": ["data analyst"],
            "Risk Manager": ["risk manager"]
        }
        for actor, keywords in actor_keywords.items():
            if any(kw in question_lower for kw in keywords):
                detected_actors.append(actor)
        
        return {
            "query_type": query_type,
            "detected_frameworks": detected_frameworks,
            "detected_actors": detected_actors
        }
    
    async def breakdown_question(
        self,
        user_question: str,
        available_frameworks: Optional[List[str]] = None,
        available_products: Optional[List[str]] = None,
        available_actors: Optional[List[str]] = None,
        available_domains: Optional[List[str]] = None,
        **kwargs
    ) -> ContextBreakdown:
        """
        Break down a compliance/risk management query using LLM.
        
        Args:
            user_question: User's question about compliance/risk
            available_frameworks: Optional list of available frameworks
            available_products: Optional list of available products
            available_actors: Optional list of available actor types
            available_domains: Optional list of available domains
            **kwargs: Additional parameters
            
        Returns:
            ContextBreakdown object with compliance-aware context information
        """
        try:
            # Detect compliance query type
            compliance_detection = await self._detect_query_type(user_question)
            
            # Build context for prompt
            frameworks_context = ""
            if available_frameworks:
                frameworks_context = f"\n\nAvailable frameworks: {', '.join(available_frameworks)}"
            
            products_context = ""
            if available_products:
                products_context = f"\n\nAvailable products: {', '.join(available_products)}"
            
            actors_context = ""
            if available_actors:
                actors_context = f"\n\nAvailable actor types: {', '.join(available_actors)}"
            
            domains_context = ""
            if available_domains:
                domains_context = f"\n\nAvailable domains: {', '.join(available_domains)}"
            
            # Get prompts from vector_store_prompts.json
            planning_instructions = self._get_planning_instructions()
            question_decomposition = self._get_question_decomposition()
            entity_definitions = self._get_entity_definitions()
            
            # Build entity list for prompt
            entity_list = "\n".join([
                f"- {name}: {info.get('description', '')[:100]}"
                for name, info in list(entity_definitions.items())[:20]
            ])
            
            # Add compliance detection results
            compliance_context = f"""
Compliance Query Detection:
- Is framework query: {compliance_detection['query_type']['is_framework_query']}
- Is control query: {compliance_detection['query_type']['is_control_query']}
- Is evidence query: {compliance_detection['query_type']['is_evidence_query']}
- Is risk query: {compliance_detection['query_type']['is_risk_query']}
- Is policy query: {compliance_detection['query_type']['is_policy_query']}
- Is actor query: {compliance_detection['query_type']['is_actor_query']}
- Detected frameworks: {', '.join(compliance_detection['detected_frameworks']) if compliance_detection['detected_frameworks'] else 'None'}
- Detected actors: {', '.join(compliance_detection['detected_actors']) if compliance_detection['detected_actors'] else 'None'}
"""
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", f"""You are an expert at analyzing compliance and risk management questions to extract context information.

{planning_instructions}

{question_decomposition}

Available Entities:
{entity_list}

Break down the user question into:
1. Compliance context: Which compliance framework(s) are mentioned or implied?
2. Action context: What action is the user trying to perform?
3. Product context: Which product(s) are mentioned?
4. User intent: What is the user trying to accomplish?
5. Identified entities: Which entities from the available entities list are relevant?
6. Entity sub-types: Specific sub-types for identified entities
7. Edge types: Which edge types might be relevant?
8. Query keywords: Key terms that should be used for vector search

Return a JSON object with:
- query_type: Type of query (compliance, risk, policy, etc.)
- compliance_context: String describing compliance framework/context
- action_context: String describing the action
- product_context: String describing product context (if any)
- user_intent: String describing user intent
- frameworks: List of framework names mentioned
- identified_entities: List of entity names from available entities
- entity_sub_types: List of specific sub-types
- entity_types: List of entity types that might be relevant
- edge_types: List of edge types that might be relevant
- query_keywords: List of key terms for search
- search_questions: List of search question objects for entity retrieval

If a context is not present, set it to null."""),
                ("human", """Analyze this compliance query:

{user_question}
{compliance_context}
{frameworks_context}
{products_context}
{actors_context}
{domains_context}

Provide the context breakdown as JSON.""")
            ])
            
            chain = prompt | self.llm | self.json_parser
            
            result = await chain.ainvoke({
                "user_question": user_question,
                "compliance_context": compliance_context,
                "frameworks_context": frameworks_context,
                "products_context": products_context,
                "actors_context": actors_context,
                "domains_context": domains_context
            })
            
            # Log result
            logger.info(f"Compliance context breakdown result: {json.dumps(result, indent=2)[:500]}")
            
            # Build ContextBreakdown from result
            breakdown = ContextBreakdown(
                user_question=user_question,
                query_type=result.get("query_type", "compliance"),
                compliance_context=result.get("compliance_context"),
                action_context=result.get("action_context"),
                product_context=result.get("product_context"),
                user_intent=result.get("user_intent"),
                frameworks=result.get("frameworks", []),
                entity_types=result.get("entity_types", []),
                edge_types=result.get("edge_types", []),
                query_keywords=result.get("query_keywords", []),
                identified_entities=result.get("identified_entities", []),
                entity_sub_types=result.get("entity_sub_types", [])
            )
            
            # Store compliance-specific data in metadata
            breakdown.metadata["compliance_detection"] = compliance_detection
            breakdown.search_questions = result.get("search_questions", [])
            
            logger.info(f"Compliance context breakdown: {len(breakdown.identified_entities)} entities, "
                       f"{len(breakdown.search_questions)} search questions")
            
            return breakdown
            
        except Exception as e:
            logger.error(f"Error breaking down compliance question: {str(e)}", exc_info=True)
            # Return minimal breakdown on error
            breakdown = ContextBreakdown(
                user_question=user_question,
                query_type="compliance",
                identified_entities=[]
            )
            breakdown.search_questions = []
            return breakdown

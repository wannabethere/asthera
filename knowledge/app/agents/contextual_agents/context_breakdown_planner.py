"""
Context Breakdown Planner
Decides which context breakdown agent(s) to use based on user question.

This planner analyzes the user's question and determines whether to:
1. Use only the MDL agent (for pure MDL/schema queries)
2. Use only the Compliance agent (for pure compliance/risk queries)
3. Use both agents (for hybrid queries involving both MDL and compliance)
"""
import logging
from typing import Dict, List, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from .base_context_breakdown_agent import ContextBreakdown
from .mdl_context_breakdown_agent import MDLContextBreakdownAgent
from .compliance_context_breakdown_agent import ComplianceContextBreakdownAgent

logger = logging.getLogger(__name__)


class ContextBreakdownPlanner:
    """
    Planner that decides which context breakdown agent(s) to use.
    
    Uses LLM to analyze user question and determine:
    - Is it an MDL query? (tables, relationships, columns, schemas)
    - Is it a compliance query? (controls, requirements, evidence, frameworks)
    - Is it a hybrid query? (requires both MDL and compliance context)
    """
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini",
        prompts_file: Optional[str] = None
    ):
        """
        Initialize the context breakdown planner.
        
        Args:
            llm: Optional LLM instance
            model_name: Model name if llm not provided
            prompts_file: Path to vector_store_prompts.json
        """
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.json_parser = JsonOutputParser()
        
        # Initialize both agents
        self.mdl_agent = MDLContextBreakdownAgent(llm=self.llm, prompts_file=prompts_file)
        self.compliance_agent = ComplianceContextBreakdownAgent(llm=self.llm, prompts_file=prompts_file)
    
    async def plan_breakdown(
        self,
        user_question: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Analyze user question and decide which agent(s) to use.
        
        Args:
            user_question: User's question
            **kwargs: Additional context parameters
            
        Returns:
            Dictionary with:
            - use_mdl: Whether to use MDL agent
            - use_compliance: Whether to use compliance agent
            - reasoning: Explanation of the decision
            - mdl_context: Context for MDL agent (if applicable)
            - compliance_context: Context for compliance agent (if applicable)
        """
        try:
            # Use LLM to analyze the question
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an expert at analyzing user questions to determine which type of knowledge is needed.

Determine if the question requires:
1. MDL knowledge (tables, relationships, columns, schemas, metrics, features, semantic layer)
2. Compliance knowledge (frameworks, controls, requirements, evidence, policies, actors)
3. Both types of knowledge (hybrid query)

MDL indicators:
- Questions about database tables, schemas, models, entities
- Questions about relationships between tables (joins, references, belongs_to, has_many)
- Questions about columns, fields, attributes, properties
- Questions about data categories, groups, types
- Questions about metrics, KPIs, calculations, aggregations
- Questions about semantic layer, data definitions

Compliance indicators:
- Questions about compliance frameworks (SOC2, HIPAA, ISO 27001, GDPR, etc.)
- Questions about controls, requirements, mandates
- Questions about evidence, proof, documentation, artifacts
- Questions about risk, vulnerability, threat, assessment
- Questions about policies, procedures, guidelines, standards
- Questions about actors (Compliance Officer, Auditor, CISO, etc.)

Hybrid indicators:
- Questions that combine MDL and compliance (e.g., "What tables are needed for SOC2 access control?")
- Questions about compliance controls that require database evidence
- Questions about data analysis for compliance purposes

Return a JSON object with:
- use_mdl: Boolean indicating if MDL agent is needed
- use_compliance: Boolean indicating if compliance agent is needed
- reasoning: String explaining the decision
- query_type: String describing the primary query type (mdl, compliance, hybrid, general)
"""),
                ("human", """Analyze this question and determine which agent(s) to use:

User Question: {user_question}

Return your analysis as JSON.""")
            ])
            
            chain = prompt | self.llm | self.json_parser
            
            result = await chain.ainvoke({
                "user_question": user_question
            })
            
            use_mdl = result.get("use_mdl", False)
            use_compliance = result.get("use_compliance", False)
            reasoning = result.get("reasoning", "")
            query_type = result.get("query_type", "general")
            
            logger.info(f"Context breakdown planner decision: use_mdl={use_mdl}, "
                       f"use_compliance={use_compliance}, query_type={query_type}")
            logger.info(f"Reasoning: {reasoning}")
            
            return {
                "use_mdl": use_mdl,
                "use_compliance": use_compliance,
                "reasoning": reasoning,
                "query_type": query_type
            }
            
        except Exception as e:
            logger.error(f"Error in context breakdown planner: {str(e)}", exc_info=True)
            # Fallback: use both agents
            return {
                "use_mdl": True,
                "use_compliance": True,
                "reasoning": "Error in planning, using both agents as fallback",
                "query_type": "general"
            }
    
    async def breakdown_question(
        self,
        user_question: str,
        product_name: Optional[str] = None,
        available_frameworks: Optional[List[str]] = None,
        available_products: Optional[List[str]] = None,
        available_actors: Optional[List[str]] = None,
        available_domains: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Main method that plans and executes context breakdown.
        
        Args:
            user_question: User's question
            product_name: Optional product name
            available_frameworks: Optional list of available frameworks
            available_products: Optional list of available products
            available_actors: Optional list of available actor types
            available_domains: Optional list of available domains
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with:
            - plan: Planning decision
            - mdl_breakdown: MDL context breakdown (if applicable)
            - compliance_breakdown: Compliance context breakdown (if applicable)
            - combined_breakdown: Merged breakdown (if both agents used)
        """
        try:
            # Plan which agent(s) to use
            plan = await self.plan_breakdown(user_question, **kwargs)
            
            result = {
                "plan": plan,
                "mdl_breakdown": None,
                "compliance_breakdown": None,
                "combined_breakdown": None
            }
            
            # Execute MDL breakdown if needed
            if plan["use_mdl"]:
                logger.info("Executing MDL context breakdown")
                mdl_breakdown = await self.mdl_agent.breakdown_question(
                    user_question=user_question,
                    product_name=product_name,
                    available_frameworks=available_frameworks,
                    available_products=available_products,
                    **kwargs
                )
                result["mdl_breakdown"] = mdl_breakdown
            
            # Execute compliance breakdown if needed
            if plan["use_compliance"]:
                logger.info("Executing Compliance context breakdown")
                compliance_breakdown = await self.compliance_agent.breakdown_question(
                    user_question=user_question,
                    available_frameworks=available_frameworks,
                    available_products=available_products,
                    available_actors=available_actors,
                    available_domains=available_domains,
                    **kwargs
                )
                result["compliance_breakdown"] = compliance_breakdown
            
            # Combine breakdowns if both were used
            if result["mdl_breakdown"] and result["compliance_breakdown"]:
                logger.info("Combining MDL and Compliance breakdowns")
                result["combined_breakdown"] = self._combine_breakdowns(
                    mdl_breakdown=result["mdl_breakdown"],
                    compliance_breakdown=result["compliance_breakdown"]
                )
            elif result["mdl_breakdown"]:
                result["combined_breakdown"] = result["mdl_breakdown"]
            elif result["compliance_breakdown"]:
                result["combined_breakdown"] = result["compliance_breakdown"]
            
            return result
            
        except Exception as e:
            logger.error(f"Error in breakdown_question: {str(e)}", exc_info=True)
            # Return minimal result
            return {
                "plan": {
                    "use_mdl": False,
                    "use_compliance": False,
                    "reasoning": f"Error: {str(e)}",
                    "query_type": "error"
                },
                "mdl_breakdown": None,
                "compliance_breakdown": None,
                "combined_breakdown": ContextBreakdown(
                    user_question=user_question,
                    query_type="error"
                )
            }
    
    def _combine_breakdowns(
        self,
        mdl_breakdown: ContextBreakdown,
        compliance_breakdown: ContextBreakdown
    ) -> ContextBreakdown:
        """
        Combine MDL and compliance breakdowns into a single breakdown.
        
        Args:
            mdl_breakdown: MDL context breakdown
            compliance_breakdown: Compliance context breakdown
            
        Returns:
            Combined ContextBreakdown
        """
        # Merge identified entities (remove duplicates)
        identified_entities = list(set(
            mdl_breakdown.identified_entities + compliance_breakdown.identified_entities
        ))
        
        # Merge entity types (remove duplicates)
        entity_types = list(set(
            mdl_breakdown.entity_types + compliance_breakdown.entity_types
        ))
        
        # Merge entity sub-types (remove duplicates)
        entity_sub_types = list(set(
            mdl_breakdown.entity_sub_types + compliance_breakdown.entity_sub_types
        ))
        
        # Merge search questions
        search_questions = mdl_breakdown.search_questions + compliance_breakdown.search_questions
        
        # Merge edge types (remove duplicates)
        edge_types = list(set(
            mdl_breakdown.edge_types + compliance_breakdown.edge_types
        ))
        
        # Merge query keywords (remove duplicates)
        query_keywords = list(set(
            mdl_breakdown.query_keywords + compliance_breakdown.query_keywords
        ))
        
        # Merge frameworks (remove duplicates)
        frameworks = list(set(
            mdl_breakdown.frameworks + compliance_breakdown.frameworks
        ))
        
        # Merge evidence gathering requirements
        evidence_gathering_required = (
            mdl_breakdown.evidence_gathering_required or 
            compliance_breakdown.evidence_gathering_required
        )
        evidence_types_needed = list(set(
            mdl_breakdown.evidence_types_needed + compliance_breakdown.evidence_types_needed
        ))
        data_retrieval_plan = mdl_breakdown.data_retrieval_plan + compliance_breakdown.data_retrieval_plan
        metrics_kpis_needed = mdl_breakdown.metrics_kpis_needed + compliance_breakdown.metrics_kpis_needed
        
        # Merge metadata
        merged_metadata = {
            **mdl_breakdown.metadata,
            **compliance_breakdown.metadata,
            "mdl_detection": mdl_breakdown.metadata.get("mdl_detection"),
            "compliance_detection": compliance_breakdown.metadata.get("compliance_detection")
        }
        
        # Create combined breakdown
        combined = ContextBreakdown(
            user_question=mdl_breakdown.user_question,
            query_type="hybrid",
            compliance_context=compliance_breakdown.compliance_context,
            action_context=compliance_breakdown.action_context or mdl_breakdown.action_context,
            product_context=mdl_breakdown.product_context or compliance_breakdown.product_context,
            user_intent=compliance_breakdown.user_intent or mdl_breakdown.user_intent,
            frameworks=frameworks,
            entity_types=entity_types,
            edge_types=edge_types,
            query_keywords=query_keywords,
            identified_entities=identified_entities,
            entity_sub_types=entity_sub_types,
            evidence_gathering_required=evidence_gathering_required,
            evidence_types_needed=evidence_types_needed,
            data_retrieval_plan=data_retrieval_plan,
            metrics_kpis_needed=metrics_kpis_needed,
            metadata=merged_metadata
        )
        
        combined.search_questions = search_questions
        
        logger.info(f"Combined breakdown: {len(combined.identified_entities)} entities, "
                   f"{len(combined.search_questions)} search questions")
        
        return combined

"""
Context Breakdown Service
Analyzes user questions to extract context information for edge discovery
Uses vector_store_prompts.json for entity identification and planning
"""
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import json

logger = logging.getLogger(__name__)


@dataclass
class ContextBreakdown:
    """Represents a breakdown of user question into context components"""
    user_question: str
    compliance_context: Optional[str] = None
    action_context: Optional[str] = None
    product_context: Optional[str] = None
    user_intent: Optional[str] = None
    frameworks: List[str] = None
    entity_types: List[str] = None
    edge_types: List[str] = None
    query_keywords: List[str] = None
    identified_entities: List[str] = None  # Entity names from vector_store_prompts.json
    entity_sub_types: List[str] = None  # Sub-types for identified entities
    
    # Evidence gathering planning (for deep research integration)
    evidence_gathering_required: bool = False
    evidence_types_needed: List[str] = None
    data_retrieval_plan: List[Dict[str, Any]] = None
    metrics_kpis_needed: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.frameworks is None:
            self.frameworks = []
        if self.entity_types is None:
            self.entity_types = []
        if self.edge_types is None:
            self.edge_types = []
        if self.query_keywords is None:
            self.query_keywords = []
        if self.identified_entities is None:
            self.identified_entities = []
        if self.entity_sub_types is None:
            self.entity_sub_types = []
        if self.evidence_types_needed is None:
            self.evidence_types_needed = []
        if self.data_retrieval_plan is None:
            self.data_retrieval_plan = []
        if self.metrics_kpis_needed is None:
            self.metrics_kpis_needed = []
    
    def to_search_query(self) -> str:
        """Convert breakdown to a search query for edge discovery"""
        parts = []
        if self.compliance_context:
            parts.append(self.compliance_context)
        if self.action_context:
            parts.append(self.action_context)
        if self.product_context:
            parts.append(self.product_context)
        if self.user_intent:
            parts.append(self.user_intent)
        parts.extend(self.query_keywords)
        return " ".join(parts)
    
    def to_metadata_filters(self) -> Dict[str, Any]:
        """Convert breakdown to metadata filters for edge search"""
        filters = {}
        if self.frameworks:
            filters["framework"] = self.frameworks[0]  # Use first framework for now
        if self.entity_types:
            filters["source_entity_type"] = self.entity_types[0]  # Can be expanded
        if self.edge_types:
            filters["edge_type"] = self.edge_types[0]  # Can be expanded
        return filters
    
    def get_entity_queries(self, prompts_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate entity queries based on identified entities and vector_store_prompts.json.
        
        Args:
            prompts_data: Loaded vector_store_prompts.json data
            
        Returns:
            List of entity query dictionaries with store_name, metadata_filters, and query
        """
        entity_queries = []
        entities = prompts_data.get("entities", {})
        
        for entity_name in self.identified_entities:
            if entity_name in entities:
                entity_info = entities[entity_name]
                store_name = entity_info.get("store_name", "")
                
                # Get sub-type if specified
                sub_type = None
                for sub_type_name in self.entity_sub_types:
                    if sub_type_name in entity_info.get("sub_types", {}):
                        sub_type = entity_info["sub_types"][sub_type_name]
                        break
                
                # Build metadata filters
                metadata_filters = {}
                if sub_type:
                    metadata_filters.update(sub_type.get("metadata_filter", {}))
                else:
                    # Use default metadata filters from entity
                    metadata_filters_info = entity_info.get("metadata_filters", {})
                    # Apply framework filter if available
                    if self.frameworks:
                        if "framework" in metadata_filters_info:
                            metadata_filters["framework"] = self.frameworks[0]
                
                # Build query from keywords and context
                query_parts = []
                if self.compliance_context:
                    query_parts.append(self.compliance_context)
                if self.action_context:
                    query_parts.append(self.action_context)
                query_parts.extend(self.query_keywords)
                query = " ".join(query_parts) if query_parts else self.user_question
                
                entity_queries.append({
                    "entity_name": entity_name,
                    "store_name": store_name,
                    "metadata_filters": metadata_filters,
                    "query": query,
                    "sub_type": sub_type.get("description", "") if sub_type else None
                })
        
        return entity_queries


class ContextBreakdownService:
    """
    Service that breaks down user questions into context components for edge discovery.
    Uses vector_store_prompts.json for entity identification and planning instructions.
    
    Extracts:
    - Compliance context (SOC2, HIPAA, etc.)
    - Action context (for compliance/product)
    - Product context (Snyk, etc.)
    - User intent
    - Entity types and edge types from vector_store_prompts.json
    """
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini",
        prompts_file: Optional[str] = None
    ):
        """
        Initialize the context breakdown service.
        
        Args:
            llm: Optional LLM instance
            model_name: Model name if llm not provided
            prompts_file: Path to vector_store_prompts.json (defaults to app/indexing/vector_store_prompts.json)
        """
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.json_parser = JsonOutputParser()
        
        # Load vector_store_prompts.json
        if prompts_file is None:
            # Default path relative to this file
            base_path = Path(__file__).parent.parent
            prompts_file = base_path / "indexing" / "vector_store_prompts.json"
        
        self.prompts_file = Path(prompts_file)
        self.prompts_data = self._load_prompts()
    
    def _load_prompts(self) -> Dict[str, Any]:
        """Load vector_store_prompts.json"""
        try:
            if self.prompts_file.exists():
                with open(self.prompts_file, 'r') as f:
                    return json.load(f)
            else:
                logger.warning(f"Prompts file not found: {self.prompts_file}")
                return {}
        except Exception as e:
            logger.error(f"Error loading prompts file: {str(e)}")
            return {}
    
    def _get_planning_instructions(self) -> str:
        """Get planning instructions from prompts"""
        planning = self.prompts_data.get("planning_instructions", {})
        steps = planning.get("steps", [])
        entity_identification = planning.get("entity_identification", "")
        parallel_fetching = planning.get("parallel_fetching", "")
        result_combination = planning.get("result_combination", "")
        
        return f"""
Planning Instructions:
{chr(10).join(steps)}

Entity Identification: {entity_identification}
Parallel Fetching: {parallel_fetching}
Result Combination: {result_combination}
"""
    
    def _get_question_decomposition(self) -> str:
        """Get question decomposition strategy from prompts"""
        decomposition = self.prompts_data.get("instructions", {}).get("question_decomposition", {})
        return decomposition.get("content", "")
    
    def _get_entity_definitions(self) -> Dict[str, Any]:
        """Get entity definitions from prompts"""
        return self.prompts_data.get("entities", {})
    
    def _get_contextual_edges_info(self) -> Dict[str, Any]:
        """Get contextual edges information from prompts"""
        entities = self._get_entity_definitions()
        return entities.get("contextual_edges", {})
    
    async def breakdown_question(
        self,
        user_question: str,
        available_frameworks: Optional[List[str]] = None,
        available_products: Optional[List[str]] = None,
        available_actors: Optional[List[str]] = None,
        available_domains: Optional[List[str]] = None
    ) -> ContextBreakdown:
        """
        Break down a user question into context components.
        
        Args:
            user_question: User's question or query
            available_frameworks: Optional list of available frameworks (for validation)
            available_products: Optional list of available products (for validation)
            available_actors: Optional list of available actor types (e.g., ["Compliance Officer", "Data Analyst"])
            available_domains: Optional list of available domains (e.g., ["compliance", "security", "risk"])
            
        Returns:
            ContextBreakdown object with extracted context information
        """
        try:
            # Build prompt with available frameworks/products/actors/domains if provided
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
            contextual_edges_info = self._get_contextual_edges_info()
            
            # Build entity list for prompt
            entity_list = "\n".join([
                f"- {name}: {info.get('description', '')[:100]}"
                for name, info in list(entity_definitions.items())[:20]  # Limit to first 20
            ])
            
            # Get connected entity types from contextual_edges
            connected_types = []
            if contextual_edges_info:
                stores_and_types = contextual_edges_info.get("connected_entity_types", {}).get("stores_and_types", [])
                connected_types = [f"- {st['extraction_type']} from {st['store_name']}" for st in stores_and_types]
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", f"""You are an expert at analyzing user questions to extract context information for knowledge graph queries.

{planning_instructions}

{question_decomposition}

Available Entities:
{entity_list}

Contextual Edges connect these entity types:
{chr(10).join(connected_types) if connected_types else "- entities, evidence, fields, control, context, schema"}

Break down the user question into:
1. Compliance context: Which compliance framework(s) are mentioned or implied? (SOC2, HIPAA, ISO 27001, GDPR, NIST, PCI-DSS, etc.)
2. Action context: What action is the user trying to perform? (e.g., "find controls", "check compliance", "assess risk", "get evidence")
3. Product context: Which product(s) are mentioned? (e.g., Snyk, Okta, Splunk)
4. User intent: What is the user trying to accomplish? (e.g., "understand access control requirements", "find evidence for audit")
5. Identified entities: Which entities from the available entities list are relevant? (e.g., compliance_controls, policy_evidence, risk_controls)
6. Entity sub-types: Specific sub-types for identified entities (e.g., soc2_controls, hipaa_controls)
7. Edge types: Which edge types might be relevant? (e.g., HAS_REQUIREMENT_IN_CONTEXT, PROVED_BY, RELATED_TO_IN_CONTEXT)
8. Query keywords: Key terms that should be used for vector search

Return a JSON object with:
- compliance_context: String describing compliance framework/context
- action_context: String describing the action
- product_context: String describing product context (if any)
- user_intent: String describing user intent
- frameworks: List of framework names mentioned
- identified_entities: List of entity names from available entities (e.g., ["compliance_controls", "policy_evidence"])
- entity_sub_types: List of specific sub-types (e.g., ["soc2_controls", "policy_evidence_types"])
- entity_types: List of entity types that might be relevant (control, requirement, evidence, entity, field, schema)
- edge_types: List of edge types that might be relevant (HAS_REQUIREMENT_IN_CONTEXT, PROVED_BY, etc.)
- query_keywords: List of key terms for search

If a context is not present, set it to null."""),
                ("human", """Analyze this user question:

{user_question}
{frameworks_context}
{products_context}
{actors_context}
{domains_context}

Provide the context breakdown as JSON.""")
            ])
            
            chain = prompt | self.llm | self.json_parser
            
            result = await chain.ainvoke({
                "user_question": user_question,
                "frameworks_context": frameworks_context,
                "products_context": products_context,
                "actors_context": actors_context,
                "domains_context": domains_context
            })
            
            # Create ContextBreakdown from result
            breakdown = ContextBreakdown(
                user_question=user_question,
                compliance_context=result.get("compliance_context"),
                action_context=result.get("action_context"),
                product_context=result.get("product_context"),
                user_intent=result.get("user_intent"),
                frameworks=result.get("frameworks", []),
                entity_types=result.get("entity_types", []),
                edge_types=result.get("edge_types", []),
                query_keywords=result.get("query_keywords", [])
            )
            
            # Add identified entities and sub-types from prompts-based breakdown
            breakdown.identified_entities = result.get("identified_entities", [])
            breakdown.entity_sub_types = result.get("entity_sub_types", [])
            
            logger.info(f"Broke down question into: compliance={breakdown.compliance_context}, "
                       f"action={breakdown.action_context}, product={breakdown.product_context}, "
                       f"intent={breakdown.user_intent}")
            
            return breakdown
            
        except Exception as e:
            logger.error(f"Error breaking down question: {str(e)}", exc_info=True)
            # Return minimal breakdown on error
            return ContextBreakdown(
                user_question=user_question,
                query_keywords=user_question.split()[:10]  # Use first 10 words as keywords
            )
    
    async def get_default_prompt(
        self,
        user_question: str
    ) -> ContextBreakdown:
        """
        Get default prompt breakdown when no specific context is available.
        
        Args:
            user_question: User's question
            
        Returns:
            ContextBreakdown with default values
        """
        return ContextBreakdown(
            user_question=user_question,
            user_intent="general_query",
            query_keywords=user_question.split()[:10]
        )


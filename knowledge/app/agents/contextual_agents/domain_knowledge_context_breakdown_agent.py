"""
Domain Knowledge Context Breakdown Agent
Specialized agent for breaking down domain knowledge queries.

Handles:
- Domain-specific concepts (Security, Privacy, Compliance, Cloud, etc.)
- Industry terminology and best practices
- Technical concepts and patterns
- Keywords, topics, and domain-specific language
- Cross-domain relationships and dependencies
"""
import logging
from typing import Dict, List, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI
import json

from app.agents.contextual_agents.base_context_breakdown_agent import BaseContextBreakdownAgent, ContextBreakdown

logger = logging.getLogger(__name__)


class DomainKnowledgeContextBreakdownAgent(BaseContextBreakdownAgent):
    """
    Agent that breaks down domain knowledge queries using LLM.
    
    Specializes in:
    - Domain concept queries (What is X? How does Y work?)
    - Best practice queries (What are best practices for X?)
    - Technical pattern queries (What patterns are used for Y?)
    - Cross-domain relationship queries (How does X relate to Y?)
    - Industry terminology queries
    """
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini",
        prompts_file: Optional[str] = None
    ):
        """
        Initialize the domain knowledge context breakdown agent.
        
        Args:
            llm: Optional LLM instance
            model_name: Model name if llm not provided
            prompts_file: Path to vector_store_prompts.json
        """
        super().__init__(llm, model_name, prompts_file)
    
    async def _detect_query_type(self, user_question: str) -> Dict[str, Any]:
        """
        Detect the type of domain knowledge query from user question.
        
        Returns:
            Dictionary with query_type and detected entities
        """
        question_lower = user_question.lower()
        
        query_type = {
            "is_concept_query": any(keyword in question_lower for keyword in [
                "what is", "what are", "define", "definition", "explain", "describe"
            ]),
            "is_best_practice_query": any(keyword in question_lower for keyword in [
                "best practice", "recommended", "should", "guideline", "standard approach"
            ]),
            "is_how_to_query": any(keyword in question_lower for keyword in [
                "how to", "how do", "how does", "how can", "process for", "steps to"
            ]),
            "is_comparison_query": any(keyword in question_lower for keyword in [
                "versus", "vs", "compare", "difference", "better", "alternative"
            ]),
            "is_relationship_query": any(keyword in question_lower for keyword in [
                "relate", "relationship", "connection", "depends on", "linked to"
            ]),
            "is_terminology_query": any(keyword in question_lower for keyword in [
                "term", "terminology", "mean", "means", "refers to", "called"
            ])
        }
        
        # Detect domains mentioned
        detected_domains = []
        domain_keywords = {
            "Security": ["security", "secure", "encryption", "authentication", "authorization"],
            "Privacy": ["privacy", "data protection", "gdpr", "personal data", "pii"],
            "Compliance": ["compliance", "regulatory", "audit", "control", "requirement"],
            "Cloud": ["cloud", "aws", "azure", "gcp", "kubernetes", "container"],
            "DevOps": ["devops", "ci/cd", "pipeline", "deployment", "automation"],
            "Data": ["data", "database", "analytics", "reporting", "metrics"],
            "Network": ["network", "networking", "vpn", "firewall", "dns"],
            "Identity": ["identity", "iam", "access", "user management", "sso"],
            "Risk": ["risk", "vulnerability", "threat", "assessment", "mitigation"]
        }
        for domain, keywords in domain_keywords.items():
            if any(kw in question_lower for kw in keywords):
                detected_domains.append(domain)
        
        # Detect concepts mentioned (high-level categorization)
        detected_concepts = []
        concept_keywords = {
            "Authentication": ["authentication", "auth", "login", "identity verification"],
            "Authorization": ["authorization", "permissions", "access control", "rbac"],
            "Encryption": ["encryption", "encrypt", "crypto", "cipher"],
            "Monitoring": ["monitoring", "observability", "logging", "alerting"],
            "Vulnerability": ["vulnerability", "cve", "exploit", "weakness"],
            "Compliance Framework": ["framework", "standard", "regulation", "mandate"],
            "API": ["api", "rest", "graphql", "endpoint"],
            "Integration": ["integration", "connector", "webhook", "sync"]
        }
        for concept, keywords in concept_keywords.items():
            if any(kw in question_lower for kw in keywords):
                detected_concepts.append(concept)
        
        return {
            "query_type": query_type,
            "detected_domains": detected_domains,
            "detected_concepts": detected_concepts
        }
    
    async def breakdown_question(
        self,
        user_question: str,
        available_domains: Optional[List[str]] = None,
        available_concepts: Optional[List[str]] = None,
        available_products: Optional[List[str]] = None,
        available_frameworks: Optional[List[str]] = None,
        web_search_enabled: bool = True,
        **kwargs
    ) -> ContextBreakdown:
        """
        Break down a domain knowledge query using LLM.
        
        Args:
            user_question: User's question about domain knowledge
            available_domains: Optional list of available domains
            available_concepts: Optional list of available concepts
            available_products: Optional list of available products (for cross-reference)
            available_frameworks: Optional list of available frameworks (for cross-reference)
            web_search_enabled: Whether web search is enabled for this query
            **kwargs: Additional parameters
            
        Returns:
            ContextBreakdown object with domain-aware context information
        """
        try:
            # Detect domain query type
            domain_detection = await self._detect_query_type(user_question)
            
            # Build context for prompt
            domains_context = ""
            if available_domains:
                domains_context = f"\n\nAvailable domains: {', '.join(available_domains)}"
            
            concepts_context = ""
            if available_concepts:
                concepts_context = f"\n\nAvailable concepts: {', '.join(available_concepts)}"
            
            products_context = ""
            if available_products:
                products_context = f"\n\nAvailable products (for reference): {', '.join(available_products)}"
            
            frameworks_context = ""
            if available_frameworks:
                frameworks_context = f"\n\nAvailable frameworks (for reference): {', '.join(available_frameworks)}"
            
            # Get prompts from vector_store_prompts.json
            planning_instructions = self._get_planning_instructions()
            question_decomposition = self._get_question_decomposition()
            entity_definitions = self._get_entity_definitions()
            
            # Build entity list for prompt
            entity_list = "\n".join([
                f"- {name}: {info.get('description', '')[:100]}"
                for name, info in list(entity_definitions.items())[:20]
            ])
            
            # Add domain detection results
            domain_context_info = f"""
Domain Knowledge Query Detection:
- Is concept query: {domain_detection['query_type']['is_concept_query']}
- Is best practice query: {domain_detection['query_type']['is_best_practice_query']}
- Is how-to query: {domain_detection['query_type']['is_how_to_query']}
- Is comparison query: {domain_detection['query_type']['is_comparison_query']}
- Is relationship query: {domain_detection['query_type']['is_relationship_query']}
- Is terminology query: {domain_detection['query_type']['is_terminology_query']}
- Detected domains: {', '.join(domain_detection['detected_domains']) if domain_detection['detected_domains'] else 'None'}
- Detected concepts: {', '.join(domain_detection['detected_concepts']) if domain_detection['detected_concepts'] else 'None'}
- Web search enabled: {web_search_enabled}
"""
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", f"""You are an expert at analyzing domain knowledge questions to extract context information.

{planning_instructions}

{question_decomposition}

Available Entities:
{entity_list}

Break down the user question into:
1. Domain context: Which domain(s) are mentioned or implied?
2. Concept context: Which concepts are being asked about?
3. Action context: What action is the user trying to perform (learn, compare, implement, etc.)?
4. User intent: What is the user trying to accomplish?
5. Identified entities: Which entities from the available entities list are relevant?
6. Entity sub-types: Specific sub-types for identified entities
7. Edge types: Which edge types might be relevant?
8. Query keywords: Key terms that should be used for vector search
9. Web search queries: Suggested web search queries if web search is enabled

Return a JSON object with:
- query_type: Type of query (concept, best_practice, how_to, comparison, relationship, terminology)
- domain_context: String describing domain context
- concept_context: String describing concept context
- action_context: String describing the action
- user_intent: String describing user intent
- domains: List of domain names mentioned
- concepts: List of concept names mentioned
- identified_entities: List of entity names from available entities
- entity_sub_types: List of specific sub-types
- entity_types: List of entity types that might be relevant
- edge_types: List of edge types that might be relevant
- query_keywords: List of key terms for search
- search_questions: List of search question objects for entity retrieval
- web_search_queries: List of suggested web search queries (if web_search_enabled)
- related_products: List of products that might be related to this domain question
- related_frameworks: List of frameworks that might be related to this domain question

If a context is not present, set it to null."""),
                ("human", """Analyze this domain knowledge query:

{user_question}
{domain_context_info}
{domains_context}
{concepts_context}
{products_context}
{frameworks_context}

Provide the context breakdown as JSON.""")
            ])
            
            chain = prompt | self.llm | self.json_parser
            
            result = await chain.ainvoke({
                "user_question": user_question,
                "domain_context_info": domain_context_info,
                "domains_context": domains_context,
                "concepts_context": concepts_context,
                "products_context": products_context,
                "frameworks_context": frameworks_context
            })
            
            # Log result
            logger.info(f"Domain knowledge context breakdown result: {json.dumps(result, indent=2)[:500]}")
            
            # Build ContextBreakdown from result
            breakdown = ContextBreakdown(
                user_question=user_question,
                query_type=result.get("query_type", "domain_knowledge"),
                action_context=result.get("action_context"),
                user_intent=result.get("user_intent"),
                entity_types=result.get("entity_types", []),
                edge_types=result.get("edge_types", []),
                query_keywords=result.get("query_keywords", []),
                identified_entities=result.get("identified_entities", []),
                entity_sub_types=result.get("entity_sub_types", [])
            )
            
            # Store domain-specific data in metadata
            breakdown.metadata["domain_detection"] = domain_detection
            breakdown.metadata["domain_context"] = result.get("domain_context")
            breakdown.metadata["concept_context"] = result.get("concept_context")
            breakdown.metadata["domains"] = result.get("domains", [])
            breakdown.metadata["concepts"] = result.get("concepts", [])
            breakdown.metadata["related_products"] = result.get("related_products", [])
            breakdown.metadata["related_frameworks"] = result.get("related_frameworks", [])
            breakdown.metadata["web_search_queries"] = result.get("web_search_queries", [])
            breakdown.metadata["web_search_enabled"] = web_search_enabled
            breakdown.search_questions = result.get("search_questions", [])
            
            logger.info(f"Domain knowledge context breakdown: {len(breakdown.identified_entities)} entities, "
                       f"{len(breakdown.search_questions)} search questions, "
                       f"{len(breakdown.metadata.get('web_search_queries', []))} web search queries, "
                       f"domains: {breakdown.metadata.get('domains', [])}")
            
            return breakdown
            
        except Exception as e:
            logger.error(f"Error breaking down domain knowledge question: {str(e)}", exc_info=True)
            # Return minimal breakdown on error
            breakdown = ContextBreakdown(
                user_question=user_question,
                query_type="domain_knowledge",
                identified_entities=[]
            )
            breakdown.search_questions = []
            breakdown.metadata["web_search_enabled"] = web_search_enabled
            breakdown.metadata["web_search_queries"] = []
            return breakdown

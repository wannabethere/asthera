"""
MDL Reasoning Integration Node for Data Assistance

This node integrates MDL reasoning graph into the data assistance workflow.
It runs the MDL reasoning graph as a sub-graph and maps the results to the
data assistance state.
"""
import logging
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI

from app.assistants.state import ContextualAssistantState
from app.agents.mdl_reasoning_state import MDLReasoningState
from app.agents.mdl_reasoning_nodes import create_mdl_reasoning_graph
from app.services.contextual_graph_storage import ContextualGraphStorage
from app.storage.query.collection_factory import CollectionFactory

logger = logging.getLogger(__name__)


class MDLReasoningIntegrationNode:
    """Node that integrates MDL reasoning graph into data assistance workflow"""
    
    def __init__(
        self,
        contextual_graph_storage: ContextualGraphStorage,
        collection_factory: CollectionFactory,
        retrieval_helper: Any = None,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini",
        assistant_type: Optional[str] = None
    ):
        """
        Initialize MDL reasoning integration node
        
        Args:
            contextual_graph_storage: ContextualGraphStorage instance
            collection_factory: CollectionFactory instance
            retrieval_helper: Optional RetrievalHelper for metrics retrieval
            llm: Optional LLM instance
            model_name: Model name if llm not provided
            assistant_type: Optional assistant ID for playbook-first breakdown prompt (e.g. data_assistance_assistant)
        """
        self.contextual_graph_storage = contextual_graph_storage
        self.collection_factory = collection_factory
        self.retrieval_helper = retrieval_helper
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.model_name = model_name
        
        # Create MDL reasoning graph (assistant_type drives playbook-first and assistant-specific prompt)
        self.mdl_reasoning_graph = create_mdl_reasoning_graph(
            contextual_graph_storage=contextual_graph_storage,
            collection_factory=collection_factory,
            llm=self.llm,
            model_name=model_name,
            use_checkpointing=False,
            retrieval_helper=retrieval_helper,
            assistant_type=assistant_type
        )
    
    async def __call__(self, state: ContextualAssistantState) -> ContextualAssistantState:
        """
        Run MDL reasoning graph and map results to data assistance state
        
        This node:
        1. Maps ContextualAssistantState to MDLReasoningState
        2. Runs MDL reasoning graph
        3. Maps MDLReasoningState results back to ContextualAssistantState
        4. Stores MDL summary and context in state for writer to use
        """
        query = state.get("query", "")
        project_id = state.get("project_id")
        user_context = state.get("user_context", {})
        actor_type = state.get("actor_type", "consultant")
        
        # Extract actor from user_context or use actor_type
        actor = user_context.get("actor") or actor_type
        
        # Extract product(s) - user always passes product or products for table retrieval
        product_name = user_context.get("product_name") or user_context.get("product") or project_id or "Snyk"
        products = user_context.get("products") or user_context.get("available_products")
        if not products and user_context.get("product"):
            products = [user_context.get("product")]
        if not products and product_name:
            products = [product_name]
        if not products:
            products = ["Snyk"]
        if not isinstance(products, list):
            products = [products] if products else []
        products = [str(p).strip() for p in products if p] or [product_name or "Snyk"]
        
        if not query:
            logger.warning("MDLReasoningIntegrationNode: No query provided, skipping MDL reasoning")
            return state
        
        try:
            logger.info(f"MDLReasoningIntegrationNode: Starting MDL reasoning for query: {query[:100]}")
            logger.info(f"MDLReasoningIntegrationNode: Product: {product_name}, Actor: {actor}, Project ID: {project_id}")
            
            # Map ContextualAssistantState to MDLReasoningState
            mdl_state: MDLReasoningState = {
                "user_question": query,
                "product_name": product_name,
                "products": products,
                "project_id": project_id,
                "actor": actor,
                "identified_entities": [],
                "search_questions": [],
                "tables_found": [],
                "entities_found": [],
                "entity_questions": [],
                "contexts_retrieved": [],
                "edges_discovered": [],
                "related_entities": [],
                "natural_language_questions": [],
                "reasoning_plan": None,
                "plan_components": {},
                "current_step": "start",
                "status": "processing",
                "messages": []
            }
            
            # Run MDL reasoning graph
            logger.info("MDLReasoningIntegrationNode: Invoking MDL reasoning graph...")
            mdl_result = await self.mdl_reasoning_graph.ainvoke(mdl_state)
            
            logger.info(f"MDLReasoningIntegrationNode: MDL reasoning completed with status: {mdl_result.get('status')}")
            
            # Extract MDL results
            mdl_summary = mdl_result.get("summary", {})
            mdl_final_result = mdl_result.get("final_result", {})
            curated_tables = mdl_result.get("tables_found", [])
            contexts_retrieved = mdl_result.get("contexts_retrieved", [])
            edges_discovered = mdl_result.get("edges_discovered", [])
            contextual_plan = mdl_result.get("contextual_plan", {})
            generic_breakdown = mdl_result.get("generic_breakdown", {})  # Extract generic breakdown
            
            # Map MDL results to ContextualAssistantState
            # Store MDL summary and context for writer to use
            state["mdl_summary"] = mdl_summary
            state["mdl_final_result"] = mdl_final_result
            state["mdl_curated_tables"] = curated_tables
            state["mdl_contexts_retrieved"] = contexts_retrieved
            state["mdl_edges_discovered"] = edges_discovered
            state["mdl_contextual_plan"] = contextual_plan
            
            # Store generic breakdown in ContextualAssistantState for deep research node
            if generic_breakdown:
                state["generic_breakdown"] = generic_breakdown
                logger.info(f"MDLReasoningIntegrationNode: Stored generic_breakdown with evidence_gathering_required={generic_breakdown.get('evidence_gathering_required', False)}")
            else:
                logger.warning("MDLReasoningIntegrationNode: No generic_breakdown found in MDL result")
            
            # Extract suggested tables from MDL for data knowledge retrieval
            suggested_tables = []
            if curated_tables:
                for table_info in curated_tables:
                    if isinstance(table_info, dict):
                        suggested_tables.append({
                            "table_name": table_info.get("table_name", ""),
                            "relevance_score": table_info.get("relevance_score", 0.0),
                            "description": table_info.get("description", "")
                        })
            
            state["suggested_tables"] = suggested_tables
            
            # Extract table suggestion strategy from MDL contextual plan
            table_suggestion_strategy = ""
            if contextual_plan:
                reasoning = contextual_plan.get("reasoning", "")
                if reasoning:
                    table_suggestion_strategy = reasoning
            
            state["table_suggestion_strategy"] = table_suggestion_strategy
            
            # Extract context IDs from MDL contexts for framework context retrieval
            context_ids = []
            if contexts_retrieved:
                for context in contexts_retrieved:
                    if isinstance(context, dict):
                        context_id = context.get("context_id")
                        if context_id:
                            context_ids.append(context_id)
            
            # Merge with existing context_ids if any
            existing_context_ids = state.get("context_ids", [])
            all_context_ids = list(set(existing_context_ids + context_ids))
            state["context_ids"] = all_context_ids
            
            # Store reasoning path from MDL for data assistance nodes
            reasoning_path = []
            if mdl_final_result:
                # Build reasoning path from MDL results
                reasoning_path.append({
                    "step": "mdl_reasoning",
                    "summary": mdl_summary,
                    "curated_tables": curated_tables,
                    "contexts": contexts_retrieved,
                    "edges": edges_discovered
                })
            
            state["reasoning_path"] = reasoning_path
            
            # Set next node to continue with data assistance workflow
            state["next_node"] = "data_knowledge_retrieval"
            state["current_node"] = "mdl_reasoning_integration"
            
            logger.info(f"MDLReasoningIntegrationNode: MDL reasoning completed. "
                       f"Found {len(curated_tables)} tables, {len(contexts_retrieved)} contexts, "
                       f"{len(edges_discovered)} edges")
            
            # Log generic breakdown details if available
            if generic_breakdown:
                query_type = generic_breakdown.get("query_type", "unknown")
                evidence_required = generic_breakdown.get("evidence_gathering_required", False)
                logger.info(f"MDLReasoningIntegrationNode: Generic breakdown - query_type={query_type}, "
                           f"evidence_gathering_required={evidence_required}")
                if evidence_required:
                    data_plan_count = len(generic_breakdown.get("data_retrieval_plan", []))
                    metrics_count = len(generic_breakdown.get("metrics_kpis_needed", []))
                    logger.info(f"MDLReasoningIntegrationNode: Evidence gathering plan - "
                               f"{data_plan_count} data retrieval items, {metrics_count} metrics/KPIs needed")
            
        except Exception as e:
            logger.error(f"MDLReasoningIntegrationNode: Error running MDL reasoning: {str(e)}", exc_info=True)
            # Continue anyway - don't fail the entire workflow
            state["mdl_summary"] = {}
            state["mdl_final_result"] = {}
            state["suggested_tables"] = []
            state["next_node"] = "data_knowledge_retrieval"  # Continue with workflow
        
        return state

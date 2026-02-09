"""
Contextual Graph Retrieval Pipeline
Orchestrates context retrieval and reasoning plan creation
"""
import logging
from typing import Dict, Any, Optional, Callable
from langchain_openai import ChatOpenAI

from app.pipelines.base import ExtractionPipeline
from app.agents.contextual_graph_retrieval_agent import ContextualGraphRetrievalAgent

logger = logging.getLogger(__name__)


class ContextualGraphRetrievalPipeline(ExtractionPipeline):
    """Pipeline for retrieving contexts and creating reasoning plans"""
    
    def __init__(
        self,
        contextual_graph_service: Any,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        **kwargs
    ):
        """
        Initialize contextual graph retrieval pipeline
        
        Args:
            contextual_graph_service: ContextualGraphService instance
            llm: Optional LLM instance
            model_name: Model name if llm not provided
        """
        super().__init__(
            name="contextual_graph_retrieval",
            version="1.0.0",
            description="Retrieve relevant contexts and create reasoning plans",
            llm=llm,
            model_name=model_name,
            **kwargs
        )
        self.contextual_graph_service = contextual_graph_service
        # Get collection_factory from query_engine to ensure we use the same stores
        collection_factory = None
        if hasattr(contextual_graph_service, 'query_engine') and hasattr(contextual_graph_service.query_engine, 'collection_factory'):
            collection_factory = contextual_graph_service.query_engine.collection_factory
            logger.info("Using CollectionFactory from ContextualGraphService.query_engine")
        
        self.agent = ContextualGraphRetrievalAgent(
            contextual_graph_service=contextual_graph_service,
            llm=llm,
            model_name=model_name,
            collection_factory=collection_factory  # Pass collection_factory to use same stores
        )
    
    async def initialize(self, **kwargs) -> None:
        """Initialize the pipeline"""
        await super().initialize(**kwargs)
        logger.info("ContextualGraphRetrievalPipeline initialized")
    
    async def run(
        self,
        inputs: Dict[str, Any],
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Retrieve contexts and create reasoning plan
        
        Args:
            inputs: Dictionary with keys:
                - query: User query or action description
                - context_ids: Optional list of specific context IDs
                - include_all_contexts: Whether to search all contexts (default: True)
                - target_domain: Optional target domain
                - top_k: Number of contexts to retrieve (default: 5)
                - filters: Optional metadata filters
            status_callback: Optional callback for status updates
            configuration: Optional configuration overrides
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with retrieved contexts and reasoning plan
        """
        if status_callback:
            status_callback("retrieving", {"stage": "context_retrieval_start"})
        
        query = inputs.get("query", "")
        context_ids = inputs.get("context_ids")
        include_all_contexts = inputs.get("include_all_contexts", True)
        target_domain = inputs.get("target_domain")
        top_k = inputs.get("top_k", 5)
        filters = inputs.get("filters")
        
        try:
            # Step 1: Retrieve contexts
            if status_callback:
                status_callback("processing", {"stage": "retrieving_contexts"})
            
            # Extract actor, domain, and product information from inputs for context breakdown
            available_actors = inputs.get("available_actors")
            available_domains = inputs.get("available_domains")
            available_products = inputs.get("available_products")
            available_frameworks = inputs.get("available_frameworks")
            
            retrieval_result = await self.agent.retrieve_contexts(
                query=query,
                context_ids=context_ids,
                include_all_contexts=include_all_contexts,
                top_k=top_k,
                filters=filters,
                available_actors=available_actors,
                available_domains=available_domains,
                available_products=available_products,
                available_frameworks=available_frameworks
            )
            
            if not retrieval_result.get("success"):
                logger.error(f"Context retrieval failed: {retrieval_result.get('error')}")
                return {
                    "success": False,
                    "error": retrieval_result.get("error", "Context retrieval failed"),
                    "contexts": [],
                    "reasoning_plan": {}
                }
            
            contexts = retrieval_result.get("contexts", [])
            
            # Step 2: Prioritize contexts
            if status_callback:
                status_callback("processing", {"stage": "prioritizing_contexts"})
            
            action_type = inputs.get("action_type")
            prioritized_contexts = await self.agent.prioritize_contexts(
                contexts=contexts,
                query=query,
                action_type=action_type
            )
            
            # Step 3: Create reasoning plan
            if status_callback:
                status_callback("processing", {"stage": "creating_reasoning_plan"})
            
            # Extract schema_info from inputs if available
            schema_info = inputs.get("schema_info")
            
            plan_result = await self.agent.create_reasoning_plan(
                user_action=query,
                retrieved_contexts=prioritized_contexts,
                target_domain=target_domain,
                schema_info=schema_info,
                available_actors=available_actors,
                available_domains=available_domains,
                available_products=available_products,
                available_frameworks=available_frameworks
            )
            
            if not plan_result.get("success"):
                logger.warning(f"Reasoning plan creation failed: {plan_result.get('error')}")
                # Continue with contexts even if plan creation fails
                reasoning_plan = {}
            else:
                reasoning_plan = plan_result.get("reasoning_plan", {})
            
            if status_callback:
                status_callback("completed", {"stage": "retrieval_complete"})
            
            # Include context_breakdown in result if available
            result_data = {
                "contexts": prioritized_contexts,
                "reasoning_plan": reasoning_plan,
                "context_count": len(prioritized_contexts),
                "query": query,
                "target_domain": target_domain
            }
            
            # Add context_breakdown from retrieval_result if available
            if "context_breakdown" in retrieval_result:
                result_data["context_breakdown"] = retrieval_result["context_breakdown"]
            
            return {
                "success": True,
                "data": result_data,
                "contexts": prioritized_contexts,
                "reasoning_plan": reasoning_plan
            }
            
        except Exception as e:
            logger.error(f"Error in contextual graph retrieval: {str(e)}", exc_info=True)
            if status_callback:
                status_callback("error", {"stage": "retrieval_failed", "error": str(e)})
            
            return {
                "success": False,
                "error": str(e),
                "data": {
                    "contexts": [],
                    "reasoning_plan": {}
                }
            }
    
    async def cleanup(self) -> None:
        """Clean up pipeline resources"""
        await super().cleanup()
        logger.info("ContextualGraphRetrievalPipeline cleaned up")


"""
Contextual Graph Reasoning Pipeline
Orchestrates context-aware reasoning using retrieved contexts
"""
import logging
from typing import Dict, Any, Optional, Callable, List
from langchain_openai import ChatOpenAI

from .base import ExtractionPipeline
from ..contextual_graph_reasoning_agent import ContextualGraphReasoningAgent

logger = logging.getLogger(__name__)


class ContextualGraphReasoningPipeline(ExtractionPipeline):
    """Pipeline for performing context-aware reasoning"""
    
    def __init__(
        self,
        contextual_graph_service: Any,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        **kwargs
    ):
        """
        Initialize contextual graph reasoning pipeline
        
        Args:
            contextual_graph_service: ContextualGraphService instance
            llm: Optional LLM instance
            model_name: Model name if llm not provided
        """
        super().__init__(
            name="contextual_graph_reasoning",
            version="1.0.0",
            description="Perform context-aware reasoning using contextual graphs",
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
        
        self.agent = ContextualGraphReasoningAgent(
            contextual_graph_service=contextual_graph_service,
            llm=llm,
            model_name=model_name,
            collection_factory=collection_factory  # Pass collection_factory to use same stores
        )
    
    async def initialize(self, **kwargs) -> None:
        """Initialize the pipeline"""
        await super().initialize(**kwargs)
        logger.info("ContextualGraphReasoningPipeline initialized")
    
    async def run(
        self,
        inputs: Dict[str, Any],
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Perform context-aware reasoning
        
        Args:
            inputs: Dictionary with keys:
                - query: User query or question
                - context_id: Single context ID for reasoning
                - contexts: Optional list of context dictionaries for multi-context reasoning
                - reasoning_plan: Optional pre-computed reasoning plan
                - max_hops: Maximum reasoning hops (default: 3)
                - reasoning_type: Type of reasoning ('multi_hop', 'priority_controls', 'synthesis', 'infer_properties')
            status_callback: Optional callback for status updates
            configuration: Optional configuration overrides
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with reasoning results
        """
        if status_callback:
            status_callback("reasoning", {"stage": "reasoning_start"})
        
        query = inputs.get("query", "")
        context_id = inputs.get("context_id")
        contexts = inputs.get("contexts", [])
        reasoning_plan = inputs.get("reasoning_plan")
        max_hops = inputs.get("max_hops", 3)
        reasoning_type = inputs.get("reasoning_type", "multi_hop")
        
        try:
            # Determine reasoning type and execute
            if reasoning_type == "multi_hop":
                if not context_id:
                    return {
                        "success": False,
                        "error": "context_id required for multi_hop reasoning",
                        "data": {}
                    }
                
                if status_callback:
                    status_callback("processing", {"stage": "multi_hop_reasoning"})
                
                result = await self.agent.reason_with_context(
                    query=query,
                    context_id=context_id,
                    max_hops=max_hops,
                    reasoning_plan=reasoning_plan
                )
                
            elif reasoning_type == "priority_controls":
                if not context_id:
                    return {
                        "success": False,
                        "error": "context_id required for priority_controls reasoning",
                        "data": {}
                    }
                
                if status_callback:
                    status_callback("processing", {"stage": "priority_controls_reasoning"})
                
                filters = inputs.get("filters")
                top_k = inputs.get("top_k", 10)
                
                result = await self.agent.get_priority_controls(
                    context_id=context_id,
                    query=query,
                    filters=filters,
                    top_k=top_k
                )
                
            elif reasoning_type == "synthesis":
                if not contexts:
                    return {
                        "success": False,
                        "error": "contexts list required for synthesis reasoning",
                        "data": {}
                    }
                
                if status_callback:
                    status_callback("processing", {"stage": "multi_context_synthesis"})
                
                # Perform reasoning for each context first
                reasoning_results = []
                for ctx in contexts:
                    ctx_id = ctx.get("context_id")
                    if ctx_id:
                        reasoning_result = await self.agent.reason_with_context(
                            query=query,
                            context_id=ctx_id,
                            max_hops=max_hops
                        )
                        reasoning_results.append(reasoning_result)
                
                # Synthesize results
                result = await self.agent.synthesize_multi_context(
                    query=query,
                    contexts=contexts,
                    reasoning_results=reasoning_results
                )
                
            elif reasoning_type == "infer_properties":
                if not context_id:
                    return {
                        "success": False,
                        "error": "context_id required for infer_properties reasoning",
                        "data": {}
                    }
                
                if status_callback:
                    status_callback("processing", {"stage": "inferring_properties"})
                
                entity_id = inputs.get("entity_id")
                entity_type = inputs.get("entity_type", "control")
                
                if not entity_id:
                    return {
                        "success": False,
                        "error": "entity_id required for infer_properties reasoning",
                        "data": {}
                    }
                
                result = await self.agent.infer_context_properties(
                    entity_id=entity_id,
                    entity_type=entity_type,
                    context_id=context_id
                )
                
            else:
                return {
                    "success": False,
                    "error": f"Unknown reasoning_type: {reasoning_type}",
                    "data": {}
                }
            
            if status_callback:
                status_callback("completed", {"stage": "reasoning_complete"})
            
            return {
                "success": result.get("success", True),
                "data": result,
                "reasoning_type": reasoning_type,
                "query": query
            }
            
        except Exception as e:
            logger.error(f"Error in contextual graph reasoning: {str(e)}", exc_info=True)
            if status_callback:
                status_callback("error", {"stage": "reasoning_failed", "error": str(e)})
            
            return {
                "success": False,
                "error": str(e),
                "data": {}
            }
    
    async def run_multi_context(
        self,
        query: str,
        contexts: List[Dict[str, Any]],
        max_hops: int = 3,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Convenience method for multi-context reasoning
        
        Args:
            query: User query
            contexts: List of context dictionaries
            max_hops: Maximum reasoning hops
            status_callback: Optional status callback
            
        Returns:
            Dictionary with synthesized reasoning results
        """
        return await self.run(
            inputs={
                "query": query,
                "contexts": contexts,
                "reasoning_type": "synthesis",
                "max_hops": max_hops
            },
            status_callback=status_callback
        )
    
    async def cleanup(self) -> None:
        """Clean up pipeline resources"""
        await super().cleanup()
        logger.info("ContextualGraphReasoningPipeline cleaned up")


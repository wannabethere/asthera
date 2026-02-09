"""
Factory for creating and registering contextual assistants

This factory creates contextual assistant graphs and registers them
with the graph registry for use with the streaming service.
"""
import logging
from typing import Optional, Dict, Any
from langchain_openai import ChatOpenAI

from app.streams.graph_registry import GraphRegistry, get_registry
from app.assistants.graph_builder import create_contextual_assistant_graph

logger = logging.getLogger(__name__)


class ContextualAssistantFactory:
    """Factory for creating and registering contextual assistants"""
    
    def __init__(
        self,
        contextual_graph_service: Any,
        retrieval_pipeline: Any,
        reasoning_pipeline: Any,
        graph_registry: Optional[GraphRegistry] = None,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o"
    ):
        """
        Initialize the factory
        
        Args:
            contextual_graph_service: ContextualGraphService instance
            retrieval_pipeline: ContextualGraphRetrievalPipeline instance
            reasoning_pipeline: ContextualGraphReasoningPipeline instance
            graph_registry: Optional GraphRegistry (uses global if not provided)
            llm: Optional LLM instance
            model_name: Model name if llm not provided
        """
        self.contextual_graph_service = contextual_graph_service
        self.retrieval_pipeline = retrieval_pipeline
        self.reasoning_pipeline = reasoning_pipeline
        self.graph_registry = graph_registry or get_registry()
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.3)
        self.model_name = model_name
    
    def create_and_register_assistant(
        self,
        assistant_id: str,
        name: str,
        description: Optional[str] = None,
        graph_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        use_checkpointing: bool = True,
        set_as_default: bool = True
    ) -> Any:
        """
        Create a contextual assistant graph and register it
        
        Args:
            assistant_id: Unique ID for the assistant
            name: Display name for the assistant
            description: Optional description
            graph_id: Optional graph ID (defaults to assistant_id)
            metadata: Optional metadata
            use_checkpointing: Whether to use checkpointing
            set_as_default: Whether to set as default graph
            
        Returns:
            GraphConfig object
        """
        try:
            # Register assistant first
            assistant = self.graph_registry.register_assistant(
                assistant_id=assistant_id,
                name=name,
                description=description or f"Contextual assistant: {name}",
                metadata=metadata or {}
            )
            
            # Create graph
            graph_id = graph_id or f"{assistant_id}_graph"
            graph = create_contextual_assistant_graph(
                contextual_graph_service=self.contextual_graph_service,
                retrieval_pipeline=self.retrieval_pipeline,
                reasoning_pipeline=self.reasoning_pipeline,
                graph_registry=self.graph_registry,
                llm=self.llm,
                model_name=self.model_name,
                use_checkpointing=use_checkpointing
            )
            
            # Register graph
            graph_config = self.graph_registry.register_graph(
                assistant_id=assistant_id,
                graph_id=graph_id,
                graph=graph,
                name=name,
                description=description or f"Contextual assistant graph for {name}",
                metadata={
                    "type": "contextual_assistant",
                    "model": self.model_name,
                    "use_checkpointing": use_checkpointing,
                    **(metadata or {})
                },
                set_as_default=set_as_default
            )
            
            logger.info(f"Created and registered assistant: {assistant_id} with graph: {graph_id}")
            return graph_config
            
        except Exception as e:
            logger.error(f"Error creating assistant {assistant_id}: {str(e)}", exc_info=True)
            raise
    
    def create_default_assistant(
        self,
        assistant_id: str = "contextual_assistant",
        use_checkpointing: bool = True
    ) -> Any:
        """
        Create a default contextual assistant
        
        Args:
            assistant_id: ID for the assistant
            use_checkpointing: Whether to use checkpointing
            
        Returns:
            GraphConfig object
        """
        return self.create_and_register_assistant(
            assistant_id=assistant_id,
            name="Contextual Assistant",
            description="Default contextual assistant with context-aware reasoning capabilities",
            use_checkpointing=use_checkpointing,
            set_as_default=True
        )


def create_contextual_assistant_factory(
    contextual_graph_service: Any,
    retrieval_pipeline: Any,
    reasoning_pipeline: Any,
    graph_registry: Optional[GraphRegistry] = None,
    llm: Optional[ChatOpenAI] = None,
    model_name: str = "gpt-4o"
) -> ContextualAssistantFactory:
    """
    Factory function to create a ContextualAssistantFactory
    
    Args:
        contextual_graph_service: ContextualGraphService instance
        retrieval_pipeline: ContextualGraphRetrievalPipeline instance
        reasoning_pipeline: ContextualGraphReasoningPipeline instance
        graph_registry: Optional GraphRegistry
        llm: Optional LLM instance
        model_name: Model name if llm not provided
        
    Returns:
        ContextualAssistantFactory instance
    """
    return ContextualAssistantFactory(
        contextual_graph_service=contextual_graph_service,
        retrieval_pipeline=retrieval_pipeline,
        reasoning_pipeline=reasoning_pipeline,
        graph_registry=graph_registry,
        llm=llm,
        model_name=model_name
    )


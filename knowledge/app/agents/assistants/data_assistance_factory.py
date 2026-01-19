"""
Factory for creating and registering Data Assistance Assistants

This factory creates data assistance assistant graphs using the framework
and registers them with the graph registry for use with the streaming service.

IMPORTANT: Collection Prefix Configuration
------------------------------------------
The data assistance assistant uses the same ChromaDB collections and contextual graph
as the ingestion scripts (ingest_mdl_contextual_graph.py, ingest_preview_files.py).

Both use empty collection_prefix ("") to match collection_factory.py collections:
- Context definitions: "context_definitions" (unprefixed)
- Contextual edges: "contextual_edges" (unprefixed)
- Control profiles: "control_context_profiles" (unprefixed)
- Compliance controls: "compliance_controls" (unprefixed)
- Fields: "fields" (unprefixed)
- Other collections as defined in collection_factory.py

When initializing ContextualGraphService for the data assistance assistant,
ensure collection_prefix="" is passed to match the ingestion scripts.
See app/core/startup.py:_initialize_data_assistance_assistant() for the initialization.
"""
import logging
from typing import Optional, Dict, Any
from langchain_openai import ChatOpenAI

from app.streams.graph_registry import GraphRegistry, get_registry
from .data_assistance_graph_builder import create_data_assistance_graph

logger = logging.getLogger(__name__)


class DataAssistanceFactory:
    """Factory for creating and registering data assistance assistants using the framework"""
    
    def __init__(
        self,
        retrieval_helper: Any,
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
            retrieval_helper: RetrievalHelper instance for schema/metric retrieval
            contextual_graph_service: ContextualGraphService for control retrieval (framework requirement)
            retrieval_pipeline: ContextualGraphRetrievalPipeline instance (framework requirement)
            reasoning_pipeline: ContextualGraphReasoningPipeline instance (framework requirement)
            graph_registry: Optional GraphRegistry (uses global if not provided)
            llm: Optional LLM instance
            model_name: Model name if llm not provided
        """
        self.retrieval_helper = retrieval_helper
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
        Create a data assistance assistant graph and register it
        
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
                description=description or f"Data assistance assistant: {name}",
                metadata=metadata or {}
            )
            
            # Create graph using framework
            graph_id = graph_id or f"{assistant_id}_graph"
            graph = create_data_assistance_graph(
                retrieval_helper=self.retrieval_helper,
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
                description=description or f"Data assistance assistant graph for {name}",
                metadata={
                    "type": "data_assistance",
                    "model": self.model_name,
                    "use_checkpointing": use_checkpointing,
                    **(metadata or {})
                },
                set_as_default=set_as_default
            )
            
            logger.info(f"Created and registered data assistance assistant: {assistant_id} with graph: {graph_id}")
            return graph_config
            
        except Exception as e:
            logger.error(f"Error creating data assistance assistant {assistant_id}: {str(e)}", exc_info=True)
            raise
    
    def create_default_assistant(
        self,
        assistant_id: str = "data_assistance_assistant",
        use_checkpointing: bool = True
    ) -> Any:
        """
        Create a default data assistance assistant
        
        Args:
            assistant_id: ID for the assistant
            use_checkpointing: Whether to use checkpointing
            
        Returns:
            GraphConfig object
        """
        return self.create_and_register_assistant(
            assistant_id=assistant_id,
            name="Data Assistance Assistant",
            description="Data assistance assistant that retrieves schemas, metrics, and controls, and helps answer questions about metrics for compliance controls",
            use_checkpointing=use_checkpointing,
            set_as_default=True
        )


def create_data_assistance_factory(
    retrieval_helper: Any,
    contextual_graph_service: Any,
    retrieval_pipeline: Any,
    reasoning_pipeline: Any,
    graph_registry: Optional[GraphRegistry] = None,
    llm: Optional[ChatOpenAI] = None,
    model_name: str = "gpt-4o"
) -> DataAssistanceFactory:
    """
    Factory function to create a DataAssistanceFactory using the framework
    
    Args:
        retrieval_helper: RetrievalHelper instance for schema/metric retrieval
        contextual_graph_service: ContextualGraphService for control retrieval (framework requirement)
        retrieval_pipeline: ContextualGraphRetrievalPipeline instance (framework requirement)
        reasoning_pipeline: ContextualGraphReasoningPipeline instance (framework requirement)
        graph_registry: Optional GraphRegistry
        llm: Optional LLM instance
        model_name: Model name if llm not provided
        
    Returns:
        DataAssistanceFactory instance
    """
    return DataAssistanceFactory(
        retrieval_helper=retrieval_helper,
        contextual_graph_service=contextual_graph_service,
        retrieval_pipeline=retrieval_pipeline,
        reasoning_pipeline=reasoning_pipeline,
        graph_registry=graph_registry,
        llm=llm,
        model_name=model_name
    )


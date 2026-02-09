"""
Factory for creating and registering Data Assistance Assistants

This factory creates data assistance assistant graphs using the framework
and registers them with the graph registry for use with the streaming service.

Data retrieval (when contextual data path is used):
- Table/data retrieval is done via ContextualDataRetrievalAgent, using RetrievalHelper.
- For this path, pass RetrievalHelper(vector_store_client, collection_factory=...) so that
  retrieve_from_mdl_stores is available. No contextual edge retrieval is performed; the
  assistant returns data and the QA node summarizes based on user action.
- When retrieval_helper has no collection_factory, the graph falls back to legacy
  retrieval (query_plan -> retrieve_context -> mdl_reasoning or contextual_reasoning -> data_knowledge_retrieval).

Collection prefix and contextual graph (legacy path): same as ingest scripts; see startup.
"""
import logging
from typing import Optional, Dict, Any
from langchain_openai import ChatOpenAI

from app.streams.graph_registry import GraphRegistry, get_registry
from .data_assistance_graph_builder import create_data_assistance_graph
from app.utils.deep_research_utility import DeepResearchConfig
from app.services.contextual_graph_storage import ContextualGraphStorage
from app.storage.query.collection_factory import CollectionFactory
from app.core.dependencies import get_llm

logger = logging.getLogger(__name__)


class DataAssistanceFactory:
    """Factory for creating and registering data assistance assistants using the framework"""
    
    def __init__(
        self,
        retrieval_helper: Any,
        contextual_graph_service: Any,
        retrieval_pipeline: Any,
        reasoning_pipeline: Any,
        contextual_graph_storage: Optional[ContextualGraphStorage] = None,
        collection_factory: Optional[CollectionFactory] = None,
        graph_registry: Optional[GraphRegistry] = None,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        deep_research_config: Optional[DeepResearchConfig] = None
    ):
        """
        Initialize the factory
        
        Args:
            retrieval_helper: RetrievalHelper instance for schema/metric retrieval
            contextual_graph_service: ContextualGraphService for control retrieval (framework requirement)
            retrieval_pipeline: ContextualGraphRetrievalPipeline instance (framework requirement)
            reasoning_pipeline: ContextualGraphReasoningPipeline instance (framework requirement)
            contextual_graph_storage: Optional ContextualGraphStorage for MDL reasoning
            collection_factory: Optional CollectionFactory for MDL reasoning
            graph_registry: Optional GraphRegistry (uses global if not provided)
            llm: Optional LLM instance
            model_name: Model name if llm not provided
            deep_research_config: Optional config for URL-based deep research (e.g. default_snyk_config())
        """
        self.retrieval_helper = retrieval_helper
        self.contextual_graph_service = contextual_graph_service
        self.retrieval_pipeline = retrieval_pipeline
        self.reasoning_pipeline = reasoning_pipeline
        self.contextual_graph_storage = contextual_graph_storage
        self.collection_factory = collection_factory
        self.graph_registry = graph_registry or get_registry()
        self.llm = llm or get_llm(model=model_name)
        self.model_name = model_name
        self.deep_research_config = deep_research_config
    
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
                contextual_graph_storage=self.contextual_graph_storage,
                collection_factory=self.collection_factory,
                graph_registry=self.graph_registry,
                llm=self.llm,
                model_name=self.model_name,
                use_checkpointing=use_checkpointing,
                deep_research_config=self.deep_research_config
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
    contextual_graph_storage: Optional[ContextualGraphStorage] = None,
    collection_factory: Optional[CollectionFactory] = None,
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
        contextual_graph_storage: Optional ContextualGraphStorage for MDL reasoning
        collection_factory: Optional CollectionFactory for MDL reasoning
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
        contextual_graph_storage=contextual_graph_storage,
        collection_factory=collection_factory,
        graph_registry=graph_registry,
        llm=llm,
        model_name=model_name
    )


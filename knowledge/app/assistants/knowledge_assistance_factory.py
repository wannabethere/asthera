"""
Factory for creating and registering Knowledge Assistance Assistants

This factory creates knowledge assistance assistant graphs using the framework
and registers them with the graph registry for use with the streaming service.

The knowledge assistance assistant focuses on:
- SOC2 Compliance controls
- Risks associated with controls
- Measures/effectiveness for controls
- Presenting knowledge as markdown without aggregation or consolidation

IMPORTANT: Collection Prefix Configuration
------------------------------------------
The knowledge assistance assistant uses the same ChromaDB collections and contextual graph
as the ingestion scripts (ingest_mdl_contextual_graph.py, ingest_preview_files.py).

Both use empty collection_prefix ("") to match collection_factory.py collections:
- Context definitions: "context_definitions" (unprefixed)
- Contextual edges: "contextual_edges" (unprefixed)
- Control profiles: "control_context_profiles" (unprefixed)
- Compliance controls: "compliance_controls" (unprefixed)
- Other collections as defined in collection_factory.py

When initializing ContextualGraphService for the knowledge assistance assistant,
ensure collection_prefix="" is passed to match the ingestion scripts.
"""
import logging
from typing import Optional, Dict, Any
from langchain_openai import ChatOpenAI

from app.streams.graph_registry import GraphRegistry, get_registry
from .knowledge_assistance_graph_builder import create_knowledge_assistance_graph

logger = logging.getLogger(__name__)


class KnowledgeAssistanceFactory:
    """Factory for creating and registering knowledge assistance assistants using the framework"""
    
    def __init__(
        self,
        contextual_graph_service: Any,
        retrieval_pipeline: Any,
        reasoning_pipeline: Any,
        graph_registry: Optional[GraphRegistry] = None,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        framework: str = "SOC2"
    ):
        """
        Initialize the factory
        
        Args:
            contextual_graph_service: ContextualGraphService for control retrieval (framework requirement)
            retrieval_pipeline: ContextualGraphRetrievalPipeline instance (framework requirement)
            reasoning_pipeline: ContextualGraphReasoningPipeline instance (framework requirement)
            graph_registry: Optional GraphRegistry (uses global if not provided)
            llm: Optional LLM instance
            model_name: Model name if llm not provided
            framework: Compliance framework (default: SOC2)
        """
        self.contextual_graph_service = contextual_graph_service
        self.retrieval_pipeline = retrieval_pipeline
        self.reasoning_pipeline = reasoning_pipeline
        self.graph_registry = graph_registry or get_registry()
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.3)
        self.model_name = model_name
        self.framework = framework
    
    def create_and_register_assistant(
        self,
        assistant_id: str,
        name: str,
        description: Optional[str] = None,
        graph_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        use_checkpointing: bool = True,
        set_as_default: bool = True,
        framework: Optional[str] = None
    ) -> Any:
        """
        Create a knowledge assistance assistant graph and register it
        
        Args:
            assistant_id: Unique ID for the assistant
            name: Display name for the assistant
            description: Optional description
            graph_id: Optional graph ID (defaults to assistant_id)
            metadata: Optional metadata
            use_checkpointing: Whether to use checkpointing
            set_as_default: Whether to set as default graph
            framework: Compliance framework (defaults to factory default)
            
        Returns:
            GraphConfig object
        """
        try:
            # Register assistant first
            assistant = self.graph_registry.register_assistant(
                assistant_id=assistant_id,
                name=name,
                description=description or f"Knowledge assistance assistant: {name}",
                metadata=metadata or {}
            )
            
            # Create graph using framework
            graph_id = graph_id or f"{assistant_id}_graph"
            framework_to_use = framework or self.framework
            graph = create_knowledge_assistance_graph(
                contextual_graph_service=self.contextual_graph_service,
                retrieval_pipeline=self.retrieval_pipeline,
                reasoning_pipeline=self.reasoning_pipeline,
                graph_registry=self.graph_registry,
                llm=self.llm,
                model_name=self.model_name,
                use_checkpointing=use_checkpointing,
                framework=framework_to_use
            )
            
            # Register graph
            graph_config = self.graph_registry.register_graph(
                assistant_id=assistant_id,
                graph_id=graph_id,
                graph=graph,
                name=name,
                description=description or f"Knowledge assistance assistant graph for {name}",
                metadata={
                    "type": "knowledge_assistance",
                    "model": self.model_name,
                    "use_checkpointing": use_checkpointing,
                    "framework": framework_to_use,
                    **(metadata or {})
                },
                set_as_default=set_as_default
            )
            
            logger.info(f"Created and registered knowledge assistance assistant: {assistant_id} with graph: {graph_id}")
            return graph_config
            
        except Exception as e:
            logger.error(f"Error creating knowledge assistance assistant {assistant_id}: {str(e)}", exc_info=True)
            raise
    
    def create_default_assistant(
        self,
        assistant_id: str = "knowledge_assistance_assistant",
        use_checkpointing: bool = True,
        framework: str = "SOC2"
    ) -> Any:
        """
        Create a default knowledge assistance assistant
        
        Args:
            assistant_id: ID for the assistant
            use_checkpointing: Whether to use checkpointing
            framework: Compliance framework (default: SOC2)
            
        Returns:
            GraphConfig object
        """
        return self.create_and_register_assistant(
            assistant_id=assistant_id,
            name="Knowledge Assistance Assistant",
            description="Knowledge assistance assistant that retrieves SOC2 compliance controls, risks, and measures/effectiveness. Presents knowledge as markdown without aggregation or consolidation.",
            use_checkpointing=use_checkpointing,
            set_as_default=True,
            framework=framework
        )


def create_knowledge_assistance_factory(
    contextual_graph_service: Any,
    retrieval_pipeline: Any,
    reasoning_pipeline: Any,
    graph_registry: Optional[GraphRegistry] = None,
    llm: Optional[ChatOpenAI] = None,
    model_name: str = "gpt-4o",
    framework: str = "SOC2"
) -> KnowledgeAssistanceFactory:
    """
    Factory function to create a KnowledgeAssistanceFactory using the framework
    
    Args:
        contextual_graph_service: ContextualGraphService for control retrieval (framework requirement)
        retrieval_pipeline: ContextualGraphRetrievalPipeline instance (framework requirement)
        reasoning_pipeline: ContextualGraphReasoningPipeline instance (framework requirement)
        graph_registry: Optional GraphRegistry
        llm: Optional LLM instance
        model_name: Model name if llm not provided
        framework: Compliance framework (default: SOC2)
        
    Returns:
        KnowledgeAssistanceFactory instance
    """
    return KnowledgeAssistanceFactory(
        contextual_graph_service=contextual_graph_service,
        retrieval_pipeline=retrieval_pipeline,
        reasoning_pipeline=reasoning_pipeline,
        graph_registry=graph_registry,
        llm=llm,
        model_name=model_name,
        framework=framework
    )


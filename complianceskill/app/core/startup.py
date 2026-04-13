"""
Startup initialization for Knowledge App

This module handles:
- Graph compilation and registration
- Assistant creation and configuration
- Initial setup of the graph registry
- Indexing service initialization and collection verification
"""
import logging
import traceback
from typing import Dict, Any, Optional, List

from app.core.dependencies import get_dependencies
from app.streams.graph_registry import GraphRegistry, get_registry
from app.streams.streaming_service import GraphStreamingService

logger = logging.getLogger(__name__)


async def initialize_graphs_and_assistants(
    dependencies: Dict[str, Any],
    registry: Optional[GraphRegistry] = None,
    config_path: Optional[str] = None
) -> GraphRegistry:
    """
    Initialize graphs and assistants at startup.
    
    This function:
    1. Tries to load from config file if provided
    2. Otherwise creates example assistants (compliance, data science, etc.)
    3. Compiles and registers graphs for each assistant
    4. Sets up default graphs
    
    Args:
        dependencies: Dictionary of dependencies from get_dependencies()
        registry: Optional registry instance (uses global if not provided)
        config_path: Optional path to YAML config file
    
    Returns:
        GraphRegistry instance with all graphs and assistants registered
    """
    if registry is None:
        registry = get_registry()
    
    llm = dependencies.get("llm")
    settings = dependencies.get("settings")
    
    logger.info("Initializing graph registry (assistants archived)...")
    # Assistants have been moved to complianceskill/archived/assistants
    return registry


async def _initialize_knowledge_assistance_assistant(
    registry: GraphRegistry,
    llm: Any,
    settings: Any,
    dependencies: Dict[str, Any]
) -> None:
    """Initialize Knowledge Assistance Assistant for SOC2 compliance knowledge
    
    This assistant retrieves and presents SOC2 compliance controls, risks, and measures
    without aggregation or consolidation.
    """
    logger.info("Initializing Knowledge Assistance Assistant...")
    
    try:
        # Import required components
        from app.services.contextual_graph_service import ContextualGraphService
        from app.pipelines import (
            ContextualGraphRetrievalPipeline,
            ContextualGraphReasoningPipeline
        )
        from app.assistants import create_knowledge_assistance_factory
        
        # Get dependencies
        db_pool = dependencies.get("db_pool")
        vector_store_client = dependencies.get("vector_store_client")
        embeddings = dependencies.get("embeddings")
        vector_store_type = dependencies.get("vector_store_type", "chroma")
        
        logger.info(f"Vector store type: {vector_store_type}")
        
        # Validate required dependencies
        if not db_pool or not vector_store_client or not embeddings:
            logger.warning("Could not create Knowledge Assistance Assistant: missing db_pool, vector_store_client, or embeddings")
            registry.register_assistant(
                assistant_id="knowledge_assistance_assistant",
                name="Knowledge Assistance Assistant",
                description="Retrieves and presents SOC2 compliance knowledge: controls, risks, and measures/effectiveness",
                metadata={
                    "category": "compliance",
                    "use_cases": ["soc2_compliance", "compliance_controls", "risk_analysis", "effectiveness_measures"]
                }
            )
            logger.warning("Knowledge Assistance Assistant registered without graphs")
            return
        
        # Create ContextualGraphService
        # Use empty collection_prefix to match ingestion scripts
        collection_prefix = getattr(settings, 'KNOWLEDGE_ASSISTANCE_COLLECTION_PREFIX', "")
        contextual_graph_service = ContextualGraphService(
            db_pool=db_pool,
            vector_store_client=vector_store_client,
            embeddings_model=embeddings,
            llm=llm,
            collection_prefix=collection_prefix
        )
        logger.info(f"Created ContextualGraphService for Knowledge Assistance Assistant (collection_prefix: '{collection_prefix or 'none'}')")
        
        # Create pipelines
        retrieval_pipeline = ContextualGraphRetrievalPipeline(
            contextual_graph_service=contextual_graph_service,
            llm=llm,
            model_name=settings.LLM_MODEL
        )
        await retrieval_pipeline.initialize()
        logger.info("Created ContextualGraphRetrievalPipeline for Knowledge Assistance Assistant")
        
        reasoning_pipeline = ContextualGraphReasoningPipeline(
            contextual_graph_service=contextual_graph_service,
            llm=llm,
            model_name=settings.LLM_MODEL
        )
        await reasoning_pipeline.initialize()
        logger.info("Created ContextualGraphReasoningPipeline for Knowledge Assistance Assistant")
        
        # Create factory and register assistant
        factory = create_knowledge_assistance_factory(
            contextual_graph_service=contextual_graph_service,
            retrieval_pipeline=retrieval_pipeline,
            reasoning_pipeline=reasoning_pipeline,
            graph_registry=registry,
            llm=llm,
            model_name=settings.LLM_MODEL,
            framework="SOC2"  # Default to SOC2
        )
        
        graph_config = factory.create_and_register_assistant(
            assistant_id="knowledge_assistance_assistant",
            name="Knowledge Assistance Assistant",
            description="Retrieves and presents SOC2 compliance knowledge: controls, risks, and measures/effectiveness. Presents knowledge as markdown without aggregation or consolidation.",
            use_checkpointing=True,
            set_as_default=True,
            framework="SOC2",
            metadata={
                "category": "compliance",
                "use_cases": ["soc2_compliance", "compliance_controls", "risk_analysis", "effectiveness_measures"],
                "vector_store_type": vector_store_type,
                "no_aggregation": True,
                "output_format": "markdown"
            }
        )
        logger.info(f"Registered knowledge_assistance_assistant with graph: {graph_config.graph_id}")
            
    except Exception as e:
        logger.error(f"Error initializing Knowledge Assistance Assistant: {e}", exc_info=True)
        logger.warning("Knowledge Assistance Assistant not initialized")
        # Register assistant without graph as fallback
        try:
            registry.register_assistant(
                assistant_id="knowledge_assistance_assistant",
                name="Knowledge Assistance Assistant",
                description="Retrieves and presents SOC2 compliance knowledge: controls, risks, and measures/effectiveness",
                metadata={
                    "category": "compliance",
                    "use_cases": ["soc2_compliance", "compliance_controls", "risk_analysis", "effectiveness_measures"]
                }
            )
            logger.warning("Knowledge Assistance Assistant registered without graphs")
        except Exception as reg_error:
            logger.error(f"Failed to register Knowledge Assistance Assistant: {reg_error}")


async def _initialize_data_assistance_assistant(
    registry: GraphRegistry,
    llm: Any,
    settings: Any,
    dependencies: Dict[str, Any]
) -> None:
    """Initialize Data Assistance Assistant with data assistance capabilities
    
    Uses dependencies from get_dependencies() which supports both ChromaDB and Qdrant.
    ContextualGraphService now uses vector_store_client which supports both backends.
    """
    logger.info("Initializing Data Assistance Assistant...")
    
    try:
        # Import required components
        from app.agents.data.retrieval_helper import RetrievalHelper
        from app.services.contextual_graph_service import ContextualGraphService
        from app.pipelines import (
            ContextualGraphRetrievalPipeline,
            ContextualGraphReasoningPipeline
        )
        from app.assistants import create_data_assistance_factory
        
        # Get dependencies (works with both ChromaDB and Qdrant)
        db_pool = dependencies.get("db_pool")
        vector_store_client = dependencies.get("vector_store_client")
        embeddings = dependencies.get("embeddings")
        vector_store_type = dependencies.get("vector_store_type", "chroma")
        
        # Log which vector store is being used
        logger.info(f"Vector store type: {vector_store_type}")
        
        # Validate required dependencies
        if not db_pool or not vector_store_client or not embeddings:
            logger.warning("Could not create Data Assistance Assistant: missing db_pool, vector_store_client, or embeddings")
            registry.register_assistant(
                assistant_id="data_assistance_assistant",
                name="Data Assistance Assistant",
                description="Helps answer questions about metrics, schemas, and compliance controls",
                metadata={
                    "category": "data_assistance",
                    "use_cases": ["schema_queries", "metric_generation", "compliance_metrics", "data_analysis"]
                }
            )
            logger.warning("Data Assistance Assistant registered without graphs")
            return
        
        # Create ContextualGraphService using dependencies
        # ContextualGraphService now uses vector_store_client (supports both ChromaDB and Qdrant)
        # Use empty collection_prefix to match ingestion scripts (ingest_mdl_contextual_graph.py, ingest_preview_files.py)
        # which use unprefixed collections to match collection_factory.py
        collection_prefix = getattr(settings, 'DATA_ASSISTANCE_COLLECTION_PREFIX', "")
        contextual_graph_service = ContextualGraphService(
            db_pool=db_pool,
            vector_store_client=vector_store_client,
            embeddings_model=embeddings,
            llm=llm,
            collection_prefix=collection_prefix
        )
        logger.info(f"Created ContextualGraphService for Data Assistance Assistant (collection_prefix: '{collection_prefix or 'none'}')")
        
        # Create pipelines
        retrieval_pipeline = ContextualGraphRetrievalPipeline(
            contextual_graph_service=contextual_graph_service,
            llm=llm,
            model_name=settings.LLM_MODEL
        )
        await retrieval_pipeline.initialize()
        logger.info("Created ContextualGraphRetrievalPipeline for Data Assistance Assistant")
        
        reasoning_pipeline = ContextualGraphReasoningPipeline(
            contextual_graph_service=contextual_graph_service,
            llm=llm,
            model_name=settings.LLM_MODEL
        )
        await reasoning_pipeline.initialize()
        logger.info("Created ContextualGraphReasoningPipeline for Data Assistance Assistant")
        
        # Create RetrievalHelper
        # RetrievalHelper uses document stores which can work with either ChromaDB or Qdrant
        # via the DocumentStoreProvider abstraction
        retrieval_helper = RetrievalHelper()
        
        # Create factory and register assistant
        factory = create_data_assistance_factory(
            retrieval_helper=retrieval_helper,
            contextual_graph_service=contextual_graph_service,
            retrieval_pipeline=retrieval_pipeline,
            reasoning_pipeline=reasoning_pipeline,
            graph_registry=registry,
            llm=llm,
            model_name=settings.LLM_MODEL
        )
        
        graph_config = factory.create_and_register_assistant(
            assistant_id="data_assistance_assistant",
            name="Data Assistance Assistant",
            description="Helps answer questions about metrics, schemas, and compliance controls. Retrieves knowledge from contextual retrieval for schemas, metrics, and controls.",
            use_checkpointing=True,
            set_as_default=True,
            metadata={
                "category": "data_assistance",
                "use_cases": ["schema_queries", "metric_generation", "compliance_metrics", "data_analysis"],
                "vector_store_type": vector_store_type
            }
        )
        logger.info(f"Registered data_assistance_assistant with graph: {graph_config.graph_id}")
            
    except Exception as e:
        logger.error(f"Error initializing Data Assistance Assistant: {e}", exc_info=True)
        logger.warning("Data Assistance Assistant not initialized")
        # Register assistant without graph as fallback
        try:
            registry.register_assistant(
                assistant_id="data_assistance_assistant",
                name="Data Assistance Assistant",
                description="Helps answer questions about metrics, schemas, and compliance controls",
                metadata={
                    "category": "data_assistance",
                    "use_cases": ["schema_queries", "metric_generation", "compliance_metrics", "data_analysis"]
                }
            )
        except Exception as reg_error:
            logger.error(f"Could not register assistant: {reg_error}")


async def _initialize_compliance_assistant(
    registry: GraphRegistry,
    llm: Any,
    settings: Any,
    dependencies: Dict[str, Any] = None
) -> None:
    """Initialize Compliance Assistant using policy retrieval agent (no contextual/hybrid search)."""
    logger.info("Initializing Compliance Assistant (policy retrieval agent)...")

    try:
        from app.storage.query.collection_factory import CollectionFactory
        from app.agents.data.retrieval_helper import RetrievalHelper
        from app.agents.policy_retrieval_agent import PolicyRetrievalAgent
        from app.assistants import create_compliance_assistance_factory
        from app.utils.deep_research_utility import default_compliance_config

        vector_store_client = dependencies.get("vector_store_client")
        embeddings = dependencies.get("embeddings")

        if not vector_store_client or not embeddings:
            logger.warning("Could not create Compliance Assistant: missing vector_store_client or embeddings")
            registry.register_assistant(
                assistant_id="compliance_assistant",
                name="Compliance Assistant",
                description="Helps with compliance, risk analysis, and regulatory requirements",
                metadata={
                    "category": "compliance",
                    "use_cases": ["risk_analysis", "regulatory_compliance", "audit_support"]
                }
            )
            return

        collection_prefix = getattr(settings, "KNOWLEDGE_ASSISTANCE_COLLECTION_PREFIX", "comprehensive_index")
        collection_factory = CollectionFactory(
            vector_store_client=vector_store_client,
            embeddings_model=embeddings,
            collection_prefix=collection_prefix,
        )
        core_collection_prefix = getattr(settings, "CORE_COLLECTION_PREFIX", None)
        retrieval_helper = RetrievalHelper(
            vector_store_client=vector_store_client,
            collection_factory=collection_factory,
            core_collection_prefix=core_collection_prefix,
        )
        policy_retrieval_agent = PolicyRetrievalAgent(retrieval_helper=retrieval_helper)

        contextual_data_retrieval_agent = None
        if getattr(retrieval_helper, "collection_factory", None):
            from app.agents.mdlworkflows.contextual_data_retrieval_agent import ContextualDataRetrievalAgent
            contextual_data_retrieval_agent = ContextualDataRetrievalAgent(
                retrieval_helper=retrieval_helper,
                model_name="gpt-4o-mini",
                top_k_per_store=10,
                max_tables=10,
                max_metrics=5,
            )

        factory = create_compliance_assistance_factory(
            policy_retrieval_agent=policy_retrieval_agent,
            graph_registry=registry,
            llm=llm,
            model_name=settings.LLM_MODEL,
            framework="SOC2",
            deep_research_config=default_compliance_config(),
            retrieval_helper=retrieval_helper,
            contextual_data_retrieval_agent=contextual_data_retrieval_agent,
        )
        factory.create_and_register_assistant(
            assistant_id="compliance_assistant",
            name="Compliance Assistant",
            description="Compliance assistant: policy retrieval (controls, risks, frameworks, edges).",
            graph_id="compliance_rag",
            use_checkpointing=True,
            set_as_default=True,
            framework="SOC2",
            metadata={
                "category": "compliance",
                "use_cases": ["risk_analysis", "regulatory_compliance", "audit_support"],
                "output_format": "policy_retrieval",
            }
        )
        logger.info("Registered compliance_rag graph (policy retrieval agent)")
    except Exception as e:
        logger.error(f"Could not create Compliance Assistant: {e}", exc_info=True)
        try:
            registry.register_assistant(
                assistant_id="compliance_assistant",
                name="Compliance Assistant",
                description="Helps with compliance, risk analysis, and regulatory requirements",
                metadata={"category": "compliance", "use_cases": ["risk_analysis", "regulatory_compliance", "audit_support"]}
            )
        except Exception:
            pass


async def _initialize_data_science_assistant(
    registry: GraphRegistry,
    llm: Any,
    settings: Any,
    dependencies: Dict[str, Any] = None
) -> None:
    """Initialize Data Science Assistant with data science-focused graphs"""
    logger.info("Initializing Data Science Assistant...")
    
    # Register the assistant
    assistant = registry.register_assistant(
        assistant_id="data_science_assistant",
        name="Data Science Assistant",
        description="Helps with data analysis, modeling, and statistical questions",
        metadata={
            "category": "data_science",
            "use_cases": ["data_analysis", "statistical_modeling", "ml_guidance"]
        }
    )
    
    # Create a simple data science graph
    try:
        ds_graph = _create_simple_data_science_graph(llm, settings)
        if ds_graph:
            registry.register_graph(
                assistant_id="data_science_assistant",
                graph_id="data_science_rag",
                graph=ds_graph,
                name="Data Science RAG",
                description="Self-correcting RAG for data science queries",
                set_as_default=True
            )
            logger.info("Registered data_science_rag graph")
    except Exception as e:
        logger.warning(f"Could not create data science graph: {e}")
        logger.warning("Data science assistant registered without graphs")


async def _initialize_knowledge_assistant(
    registry: GraphRegistry,
    llm: Any,
    settings: Any,
    dependencies: Dict[str, Any] = None
) -> None:
    """Initialize Knowledge Assistant (general purpose)"""
    logger.info("Initializing Knowledge Assistant...")
    
    # Register the assistant
    assistant = registry.register_assistant(
        assistant_id="knowledge_assistant",
        name="Knowledge Assistant",
        description="General purpose knowledge assistant for document queries and information retrieval",
        metadata={
            "category": "general",
            "use_cases": ["document_qa", "information_retrieval", "knowledge_base_queries"]
        }
    )
    
    # Create a simple knowledge graph
    try:
        knowledge_graph = _create_simple_knowledge_graph(llm, settings)
        if knowledge_graph:
            registry.register_graph(
                assistant_id="knowledge_assistant",
                graph_id="knowledge_rag",
                graph=knowledge_graph,
                name="Knowledge RAG",
                description="Self-correcting RAG for general knowledge queries",
                set_as_default=True
            )
            logger.info("Registered knowledge_rag graph")
    except Exception as e:
        logger.warning(f"Could not create knowledge graph: {e}")
        logger.warning("Knowledge assistant registered without graphs")


def _create_simple_compliance_graph(llm: Any, settings: Any) -> Optional[Any]:
    """
    Create a simple compliance-focused graph.
    
    Tries to use dynamic langraph framework if available, otherwise creates a minimal graph.
    """
    try:
        # Try to use dynamic langraph framework
        try:
            # This would be in a separate module if you implement the framework
            # For now, we'll create a simple graph
            pass
        except ImportError:
            logger.debug("Dynamic langraph framework not available, using simple graph")
        
        # Fallback: Create a simple graph
        from langgraph.graph import StateGraph, END
        from app.core.checkpointer_provider import get_checkpointer
        from typing import TypedDict

        # Simple state for compliance queries
        class ComplianceState(TypedDict):
            query: str
            answer: str
            context: str
            confidence: float
        
        # Simple node that answers compliance questions
        def compliance_node(state: ComplianceState) -> ComplianceState:
            """Process compliance query"""
            # In production, this would use RAG, retrieval, etc.
            state["answer"] = f"Compliance analysis for: {state['query']}. This is a placeholder implementation."
            state["context"] = "compliance_domain"
            state["confidence"] = 0.8
            return state
        
        # Build graph
        graph = StateGraph(ComplianceState)
        graph.add_node("compliance_processor", compliance_node)
        graph.set_entry_point("compliance_processor")
        graph.add_edge("compliance_processor", END)
        
        # Compile with checkpointer
        checkpointer = get_checkpointer()
        return graph.compile(checkpointer=checkpointer)

    except Exception as e:
        logger.error(f"Error creating compliance graph: {e}")
        logger.error(traceback.format_exc())
        return None


def _create_simple_data_science_graph(llm: Any, settings: Any) -> Optional[Any]:
    """
    Create a simple data science-focused graph.
    
    Tries to use dynamic langraph framework if available, otherwise creates a minimal graph.
    """
    try:
        from langgraph.graph import StateGraph, END
        from app.core.checkpointer_provider import get_checkpointer
        from typing import TypedDict

        # Simple state for data science queries
        class DataScienceState(TypedDict):
            query: str
            answer: str
            analysis_type: str
            confidence: float
        
        # Simple node that answers data science questions
        def data_science_node(state: DataScienceState) -> DataScienceState:
            """Process data science query"""
            # In production, this would use RAG, retrieval, etc.
            state["answer"] = f"Data science analysis for: {state['query']}. This is a placeholder implementation."
            state["analysis_type"] = "statistical"
            state["confidence"] = 0.8
            return state
        
        # Build graph
        graph = StateGraph(DataScienceState)
        graph.add_node("data_science_processor", data_science_node)
        graph.set_entry_point("data_science_processor")
        graph.add_edge("data_science_processor", END)
        
        # Compile with checkpointer
        checkpointer = get_checkpointer()
        return graph.compile(checkpointer=checkpointer)

    except Exception as e:
        logger.error(f"Error creating data science graph: {e}")
        logger.error(traceback.format_exc())
        return None


def _create_simple_knowledge_graph(llm: Any, settings: Any) -> Optional[Any]:
    """
    Create a simple knowledge-focused graph.
    
    Tries to use dynamic langraph framework if available, otherwise creates a minimal graph.
    """
    try:
        from langgraph.graph import StateGraph, END
        from app.core.checkpointer_provider import get_checkpointer
        from typing import TypedDict

        # Simple state for knowledge queries
        class KnowledgeState(TypedDict):
            query: str
            answer: str
            sources: list
            confidence: float
        
        # Simple node that answers knowledge questions
        def knowledge_node(state: KnowledgeState) -> KnowledgeState:
            """Process knowledge query"""
            # In production, this would use RAG, retrieval, etc.
            state["answer"] = f"Knowledge base response for: {state['query']}. This is a placeholder implementation."
            state["sources"] = []
            state["confidence"] = 0.8
            return state
        
        # Build graph
        graph = StateGraph(KnowledgeState)
        graph.add_node("knowledge_processor", knowledge_node)
        graph.set_entry_point("knowledge_processor")
        graph.add_edge("knowledge_processor", END)
        
        # Compile with checkpointer
        checkpointer = get_checkpointer()
        return graph.compile(checkpointer=checkpointer)

    except Exception as e:
        logger.error(f"Error creating knowledge graph: {e}")
        logger.error(traceback.format_exc())
        return None


async def initialize_from_config(
    dependencies: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
    registry: Optional[GraphRegistry] = None
) -> GraphRegistry:
    """
    Initialize graphs and assistants from configuration.
    
    This allows loading graph definitions from a config file or dictionary.
    
    Args:
        dependencies: Dictionary of dependencies from get_dependencies()
        config: Optional configuration dictionary with graph/assistant definitions
        registry: Optional registry instance
    
    Returns:
        GraphRegistry instance
    """
    if registry is None:
        registry = get_registry()
    
    if config is None:
        # Use default initialization
        return await initialize_graphs_and_assistants(dependencies, registry)
    
    logger.info("Initializing from configuration...")
    
    # Process config to create assistants and graphs
    assistants_config = config.get("assistants", [])
    
    for assistant_config in assistants_config:
        assistant_id = assistant_config.get("assistant_id")
        name = assistant_config.get("name")
        description = assistant_config.get("description", "")
        metadata = assistant_config.get("metadata", {})
        
        # Register assistant
        registry.register_assistant(
            assistant_id=assistant_id,
            name=name,
            description=description,
            metadata=metadata
        )
        
        # Register graphs for this assistant
        graphs_config = assistant_config.get("graphs", [])
        for graph_config in graphs_config:
            graph_id = graph_config.get("graph_id")
            graph_name = graph_config.get("name", graph_id)
            graph_description = graph_config.get("description", "")
            graph_metadata = graph_config.get("metadata", {})
            set_as_default = graph_config.get("set_as_default", False)
            
            # Build graph from config
            # In production, you'd parse the graph definition and compile it
            # For now, we'll create a placeholder
            try:
                graph = _build_graph_from_config(graph_config, dependencies)
                if graph:
                    registry.register_graph(
                        assistant_id=assistant_id,
                        graph_id=graph_id,
                        graph=graph,
                        name=graph_name,
                        description=graph_description,
                        metadata=graph_metadata,
                        set_as_default=set_as_default
                    )
                    logger.info(f"Registered graph {graph_id} for assistant {assistant_id}")
            except Exception as e:
                logger.warning(f"Could not create graph {graph_id}: {e}")
    
    return registry


def _build_graph_from_config(
    graph_config: Dict[str, Any],
    dependencies: Dict[str, Any]
) -> Optional[Any]:
    """
    Build a graph from configuration.
    
    This is a placeholder. In production, you would:
    1. Parse the graph definition (nodes, edges, etc.)
    2. Use the dynamic langraph framework to build it
    3. Compile and return it
    
    Args:
        graph_config: Graph configuration dictionary
        dependencies: Dependencies dictionary
    
    Returns:
        Compiled LangGraph instance or None
    """
    # Placeholder implementation
    # In production, use the GraphBuilder and GraphSpec from dynamic_langraph.md
    logger.warning("Graph building from config not fully implemented")
    return None


async def initialize_indexing_services(
    dependencies: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Initialize all indexing services and verify collections are available.
    
    This function:
    1. Initializes ComprehensiveIndexingService for each collection prefix:
       - compliance_baseline (from index_compliance.py)
       - connector_index (from index_connectors.py)
       - mdl_index (from index_mdl.py)
       - comprehensive_index (from ingest_preview_files.py)
    2. Verifies that collections exist and have data
    3. Makes services available for use by the application
    
    Args:
        dependencies: Dictionary of dependencies from get_dependencies()
    
    Returns:
        Dictionary mapping collection_prefix to ComprehensiveIndexingService instance
    """
    logger.info("=" * 80)
    logger.info("Initializing Indexing Services")
    logger.info("=" * 80)
    
    from app.indexing.comprehensive_indexing_service import ComprehensiveIndexingService
    from app.core.dependencies import get_chromadb_client, get_embeddings_model, get_llm
    
    # Get required dependencies
    persistent_client = get_chromadb_client()
    embeddings = get_embeddings_model()
    llm = get_llm(temperature=0.2)
    vector_store_type = dependencies.get("vector_store_type", "chroma")
    
    # Collection prefixes used by different indexing scripts
    collection_prefixes = {
        "compliance_baseline": {
            "description": "Compliance documents (SOC2, policies, risk controls)",
            "source": "index_compliance.py"
        },
        "connector_index": {
            "description": "Connector/product configurations",
            "source": "index_connectors.py"
        },
        "mdl_index": {
            "description": "MDL schema files",
            "source": "index_mdl.py"
        },
        "comprehensive_index": {
            "description": "Comprehensive indexed data (preview files)",
            "source": "ingest_preview_files.py"
        }
    }
    
    indexing_services = {}
    collection_status = {}
    
    # Initialize each indexing service
    for collection_prefix, info in collection_prefixes.items():
        try:
            logger.info(f"\nInitializing indexing service: {collection_prefix}")
            logger.info(f"  Description: {info['description']}")
            logger.info(f"  Source: {info['source']}")
            
            service = ComprehensiveIndexingService(
                vector_store_type=vector_store_type,
                persistent_client=persistent_client if vector_store_type == "chroma" else None,
                embeddings_model=embeddings,
                llm=llm,
                collection_prefix=collection_prefix,
                preview_mode=False,  # Not in preview mode - will access existing collections
                enable_pipeline_processing=False,  # Skip pipelines - just verify access
                pipeline_batch_size=50
            )
            
            indexing_services[collection_prefix] = service
            
            # Verify collections exist and have data
            status = await _verify_collections_for_prefix(
                persistent_client=persistent_client,
                collection_prefix=collection_prefix,
                stores=service.stores,
                vector_store_type=vector_store_type
            )
            
            collection_status[collection_prefix] = status
            
            logger.info(f"  ✓ Service initialized")
            logger.info(f"  Collections: {status['total_collections']} found, {status['collections_with_data']} with data")
            
        except Exception as e:
            logger.error(f"  ✗ Error initializing service for {collection_prefix}: {e}")
            logger.debug(f"  Error details: {traceback.format_exc()}")
            collection_status[collection_prefix] = {
                "error": str(e),
                "total_collections": 0,
                "collections_with_data": 0,
                "collections": {}
            }
    
    # Summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("Indexing Services Summary")
    logger.info("=" * 80)
    
    total_collections = sum(s.get("total_collections", 0) for s in collection_status.values())
    total_with_data = sum(s.get("collections_with_data", 0) for s in collection_status.values())
    
    logger.info(f"Total indexing services: {len(indexing_services)}")
    logger.info(f"Total collections found: {total_collections}")
    logger.info(f"Collections with data: {total_with_data}")
    logger.info("")
    
    for prefix, status in collection_status.items():
        if status.get("error"):
            logger.warning(f"  {prefix}: ✗ Error - {status['error']}")
        else:
            collections_count = status.get("total_collections", 0)
            with_data = status.get("collections_with_data", 0)
            status_icon = "✓" if with_data > 0 else "⚠"
            logger.info(f"  {status_icon} {prefix}: {collections_count} collections, {with_data} with data")
    
    logger.info("=" * 80)
    logger.info("")
    
    return {
        "services": indexing_services,
        "status": collection_status,
        "summary": {
            "total_services": len(indexing_services),
            "total_collections": total_collections,
            "collections_with_data": total_with_data
        }
    }


async def _verify_collections_for_prefix(
    persistent_client: Any,
    collection_prefix: str,
    stores: Dict[str, Any],
    vector_store_type: str = "chroma"
) -> Dict[str, Any]:
    """
    Verify that collections exist for a given prefix and check if they have data.
    
    Args:
        persistent_client: ChromaDB persistent client
        collection_prefix: Collection prefix to check
        stores: Dictionary of stores from ComprehensiveIndexingService
        vector_store_type: Vector store type ("chroma" or "qdrant")
    
    Returns:
        Dictionary with collection status information
    """
    status = {
        "total_collections": 0,
        "collections_with_data": 0,
        "collections": {}
    }
    
    if vector_store_type != "chroma":
        # For Qdrant, we'd need different verification logic
        logger.debug(f"Skipping collection verification for {vector_store_type} (only ChromaDB supported)")
        return status
    
    try:
        # List all collections
        all_collections = persistent_client.list_collections()
        collection_names = {c.name for c in all_collections}
        
        # Check each store's collection
        for store_name, store in stores.items():
            collection_name = f"{collection_prefix}_{store_name}"
            
            try:
                if collection_name in collection_names:
                    # Collection exists, get count
                    collection = persistent_client.get_collection(name=collection_name)
                    count = collection.count()
                    
                    status["total_collections"] += 1
                    if count > 0:
                        status["collections_with_data"] += 1
                    
                    status["collections"][store_name] = {
                        "collection_name": collection_name,
                        "exists": True,
                        "document_count": count,
                        "has_data": count > 0
                    }
                else:
                    # Collection doesn't exist
                    status["collections"][store_name] = {
                        "collection_name": collection_name,
                        "exists": False,
                        "document_count": 0,
                        "has_data": False
                    }
            except Exception as e:
                logger.debug(f"Error checking collection {collection_name}: {e}")
                status["collections"][store_name] = {
                    "collection_name": collection_name,
                    "exists": False,
                    "document_count": 0,
                    "has_data": False,
                    "error": str(e)
                }
    except Exception as e:
        logger.warning(f"Error verifying collections for prefix {collection_prefix}: {e}")
        status["error"] = str(e)
    
    return status


# ============================================================================
# WORKFORCE ASSISTANTS INITIALIZATION
# ============================================================================

async def _initialize_product_assistant(
    registry: GraphRegistry,
    llm: Any,
    settings: Any,
    dependencies: Dict[str, Any]
) -> None:
    """Initialize Product Assistant using same graph style as Knowledge: real data from product docs, framework, MDL."""
    logger.info("Initializing Product Assistant (knowledge-style graph)...")
    
    try:
        from app.services.contextual_graph_service import ContextualGraphService
        from app.pipelines import (
            ContextualGraphRetrievalPipeline,
            ContextualGraphReasoningPipeline
        )
        from app.storage.query.collection_factory import CollectionFactory
        from app.assistants.product_assistance_graph_builder import create_product_assistance_graph
        
        db_pool = dependencies.get("db_pool")
        vector_store_client = dependencies.get("vector_store_client")
        embeddings = dependencies.get("embeddings")
        
        registry.register_assistant(
            assistant_id="product_assistant",
            name="Product Assistant",
            description="Product documentation, APIs, features, and MDL/schema (same style as Knowledge assistant)",
            metadata={
                "category": "workforce",
                "type": "product",
                "use_cases": ["product_features", "api_documentation", "user_actions", "integrations"]
            }
        )
        
        if not db_pool or not vector_store_client or not embeddings:
            missing = [k for k, v in [("db_pool", db_pool), ("vector_store_client", vector_store_client), ("embeddings", embeddings)] if not v]
            logger.warning(
                "Product Assistant registered without graphs (missing dependencies: %s). "
                "Streaming invoke will return 400 until DB/vector store/embeddings are available.",
                missing,
            )
            return
        
        collection_prefix = getattr(settings, "KNOWLEDGE_ASSISTANCE_COLLECTION_PREFIX", "")
        contextual_graph_service = ContextualGraphService(
            db_pool=db_pool,
            vector_store_client=vector_store_client,
            embeddings_model=embeddings,
            llm=llm,
            collection_prefix=collection_prefix
        )
        retrieval_pipeline = ContextualGraphRetrievalPipeline(
            contextual_graph_service=contextual_graph_service,
            llm=llm,
            model_name=settings.LLM_MODEL
        )
        await retrieval_pipeline.initialize()
        reasoning_pipeline = ContextualGraphReasoningPipeline(
            contextual_graph_service=contextual_graph_service,
            llm=llm,
            model_name=settings.LLM_MODEL
        )
        await reasoning_pipeline.initialize()
        collection_factory = CollectionFactory(
            vector_store_client=vector_store_client,
            embeddings_model=embeddings,
        )
        
        graph = create_product_assistance_graph(
            contextual_graph_service=contextual_graph_service,
            retrieval_pipeline=retrieval_pipeline,
            reasoning_pipeline=reasoning_pipeline,
            collection_factory=collection_factory,
            graph_registry=registry,
            llm=llm,
            model_name=settings.LLM_MODEL,
            use_checkpointing=True,
        )
        registry.register_graph(
            assistant_id="product_assistant",
            graph_id="product_workflow",
            graph=graph,
            name="Product Workflow",
            description="Product queries using product docs, framework, and MDL tables (same style as Knowledge)",
            set_as_default=True,
            metadata={"type": "workforce", "assistant_type": "product"}
        )
        logger.info("Product Assistant initialized (knowledge-style graph)")
    except Exception as e:
        logger.error(f"Error initializing Product Assistant: {e}", exc_info=True)
        try:
            registry.register_assistant(
                assistant_id="product_assistant",
                name="Product Assistant",
                description="Product documentation, APIs, features, and MDL/schema (same style as Knowledge assistant)",
                metadata={
                    "category": "workforce",
                    "type": "product",
                    "use_cases": ["product_features", "api_documentation", "user_actions", "integrations"]
                }
            )
        except Exception:
            pass


async def _initialize_domain_knowledge_assistant(
    registry: GraphRegistry,
    llm: Any,
    settings: Any,
    dependencies: Dict[str, Any]
) -> None:
    """Initialize Domain Knowledge Assistant (plan then execute, same pattern as product/compliance)."""
    logger.info("Initializing Domain Knowledge Assistant (plan then execute)...")
    
    try:
        from app.services.contextual_graph_service import ContextualGraphService
        from app.pipelines import (
            ContextualGraphRetrievalPipeline,
            ContextualGraphReasoningPipeline
        )
        from app.storage.query.collection_factory import CollectionFactory
        from app.assistants.domain_knowledge_assistance_graph_builder import create_domain_knowledge_assistance_graph
        
        db_pool = dependencies.get("db_pool")
        vector_store_client = dependencies.get("vector_store_client")
        embeddings = dependencies.get("embeddings")
        
        registry.register_assistant(
            assistant_id="domain_knowledge_assistant",
            name="Domain Knowledge Assistant",
            description="Domain concepts, best practices, technical patterns (plan then execute, same as other assistants)",
            metadata={
                "category": "workforce",
                "type": "domain_knowledge",
                "use_cases": ["domain_concepts", "best_practices", "technical_patterns", "industry_knowledge"]
            }
        )
        
        if not db_pool or not vector_store_client or not embeddings:
            logger.warning("Domain Knowledge Assistant registered without graphs (missing dependencies)")
            return
        
        collection_prefix = getattr(settings, "KNOWLEDGE_ASSISTANCE_COLLECTION_PREFIX", "")
        contextual_graph_service = ContextualGraphService(
            db_pool=db_pool,
            vector_store_client=vector_store_client,
            embeddings_model=embeddings,
            llm=llm,
            collection_prefix=collection_prefix
        )
        retrieval_pipeline = ContextualGraphRetrievalPipeline(
            contextual_graph_service=contextual_graph_service,
            llm=llm,
            model_name=settings.LLM_MODEL
        )
        await retrieval_pipeline.initialize()
        reasoning_pipeline = ContextualGraphReasoningPipeline(
            contextual_graph_service=contextual_graph_service,
            llm=llm,
            model_name=settings.LLM_MODEL
        )
        await reasoning_pipeline.initialize()
        collection_factory = CollectionFactory(
            vector_store_client=vector_store_client,
            embeddings_model=embeddings,
        )
        
        graph = create_domain_knowledge_assistance_graph(
            contextual_graph_service=contextual_graph_service,
            retrieval_pipeline=retrieval_pipeline,
            reasoning_pipeline=reasoning_pipeline,
            collection_factory=collection_factory,
            graph_registry=registry,
            llm=llm,
            model_name=settings.LLM_MODEL,
            use_checkpointing=True,
        )
        registry.register_graph(
            assistant_id="domain_knowledge_assistant",
            graph_id="domain_knowledge_workflow",
            graph=graph,
            name="Domain Knowledge Workflow",
            description="Domain knowledge: plan (general_prompts) then retrieve domain_knowledge, entities, compliance_controls",
            set_as_default=True,
            metadata={"type": "workforce", "assistant_type": "domain_knowledge"}
        )
        logger.info("Domain Knowledge Assistant initialized (plan then execute)")
    except Exception as e:
        logger.error(f"Error initializing Domain Knowledge Assistant: {e}", exc_info=True)
        try:
            registry.register_assistant(
                assistant_id="domain_knowledge_assistant",
                name="Domain Knowledge Assistant",
                description="Domain concepts, best practices, technical patterns",
                metadata={
                    "category": "workforce",
                    "type": "domain_knowledge",
                    "use_cases": ["domain_concepts", "best_practices", "technical_patterns", "industry_knowledge"]
                }
            )
        except Exception:
            pass


async def _initialize_feature_engineering_assistant(
    registry: GraphRegistry,
    llm: Any,
    settings: Any,
    dependencies: Dict[str, Any]
) -> None:
    """Initialize Feature Engineering Assistant (streaming-only, excluded from chat assistant list)."""
    logger.info("Initializing Feature Engineering Assistant (API-only, not in assistant list)...")
    try:
        from app.agents.data.retrieval_helper import RetrievalHelper
        from app.agents.transform.domain_config import get_domain_config
        from app.agents.transform.feature_engineering_agent import create_feature_engineering_workflow

        vector_store_client = dependencies.get("vector_store_client")
        # Use core_* collections (core_table_descriptions, core_db_schema) for schema retrieval when available
        core_collection_prefix = getattr(settings, "CORE_COLLECTION_PREFIX", None)
        if core_collection_prefix is None:
            core_collection_prefix = "core_"
        retrieval_helper = RetrievalHelper(
            vector_store_client=vector_store_client,
            core_collection_prefix=core_collection_prefix,
        )
        domain = getattr(settings, "FEATURE_ENGINEERING_DOMAIN", "cybersecurity")
        domain_config = get_domain_config(domain)

        workflow = create_feature_engineering_workflow(
            llm=llm,
            retrieval_helper=retrieval_helper,
            domain_config=domain_config,
            output_dir=None,
            auto_write_file=False,
        )

        registry.register_assistant(
            assistant_id="feature_engineering_assistant",
            name="Feature Engineering",
            description="Streaming feature engineering for compliance reports, risk metrics, and natural language feature generation. Not shown in chat assistant list.",
            metadata={
                "exclude_from_list": True,
                "category": "feature_engineering",
                "use_cases": ["compliance_features", "risk_metrics", "nl_feature_generation"],
            },
        )
        registry.register_graph(
            assistant_id="feature_engineering_assistant",
            graph_id="feature_engineering_graph",
            graph=workflow,
            name="Feature Engineering Graph",
            description="Deep research feature engineering workflow (breakdown, schema, controls, features, scoring)",
            set_as_default=True,
            metadata={"input_requires": ["query", "project_id"]},
        )
        logger.info("Feature Engineering Assistant initialized (excluded from list, use POST /api/streams/invoke with assistant_id=feature_engineering_assistant)")
    except Exception as e:
        logger.error(f"Error initializing Feature Engineering Assistant: {e}", exc_info=True)
        try:
            registry.register_assistant(
                assistant_id="feature_engineering_assistant",
                name="Feature Engineering",
                description="Streaming feature engineering (graph not loaded)",
                metadata={"exclude_from_list": True, "category": "feature_engineering"},
            )
        except Exception:
            pass


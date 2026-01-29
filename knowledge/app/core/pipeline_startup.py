"""
Pipeline Registry Startup Initialization

Initialize and register async pipelines that will be available throughout
the application lifecycle for handling user queries and data retrieval.
"""
import logging
from typing import Dict, Any, Optional

from app.pipelines import (
    AsyncQueryPipeline,
    AsyncDataRetrievalPipeline,
    ContextualGraphRetrievalPipeline,
    ContextualGraphReasoningPipeline,
    get_pipeline_registry
)

logger = logging.getLogger(__name__)


async def initialize_pipeline_registry(
    dependencies: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Initialize pipeline registry with async pipelines at startup
    
    This function:
    1. Creates the pipeline registry
    2. Registers standard async pipelines for user queries
    3. Registers specialized pipelines (data retrieval, contextual, etc.)
    4. Initializes all registered pipelines
    
    Args:
        dependencies: Dictionary of dependencies from get_dependencies()
        
    Returns:
        Dictionary with initialization results
    """
    logger.info("=" * 80)
    logger.info("Initializing Pipeline Registry")
    logger.info("=" * 80)
    
    registry = get_pipeline_registry()
    
    # Get dependencies
    llm = dependencies.get("llm")
    settings = dependencies.get("settings")
    db_pool = dependencies.get("db_pool")
    vector_store_client = dependencies.get("vector_store_client")
    embeddings = dependencies.get("embeddings")
    
    results = {
        "total_pipelines": 0,
        "registered": [],
        "failed": [],
        "categories": []
    }
    
    # Register pipeline categories
    _register_pipeline_categories(registry, results)
    
    # Initialize standard query pipelines
    await _initialize_query_pipelines(registry, llm, settings, results)
    
    # Initialize data retrieval pipelines
    if db_pool and vector_store_client and embeddings:
        await _initialize_data_pipelines(
            registry, llm, settings, db_pool, 
            vector_store_client, embeddings, results
        )
    else:
        logger.warning("Skipping data pipelines - missing db_pool, vector_store_client, or embeddings")
    
    # Initialize contextual pipelines
    if vector_store_client and embeddings and db_pool:
        await _initialize_contextual_pipelines(
            registry, llm, settings, db_pool,
            vector_store_client, embeddings, results
        )
    else:
        logger.warning("Skipping contextual pipelines - missing dependencies")
    
    # Initialize all registered pipelines
    logger.info("\nInitializing all registered pipelines...")
    init_results = await registry.initialize_all()
    
    # Summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("Pipeline Registry Initialization Summary")
    logger.info("=" * 80)
    logger.info(f"Total pipelines registered: {results['total_pipelines']}")
    logger.info(f"Successfully registered: {len(results['registered'])}")
    logger.info(f"Failed to register: {len(results['failed'])}")
    logger.info(f"Categories: {len(results['categories'])}")
    logger.info(f"Initialized: {init_results['initialized']}")
    logger.info(f"Failed initialization: {init_results['failed']}")
    logger.info(f"Skipped: {init_results['skipped']}")
    logger.info("")
    
    # List registered pipelines by category
    for category in results['categories']:
        category_pipelines = registry.list_pipelines(category=category)
        if category_pipelines:
            logger.info(f"  {category.upper()} ({len(category_pipelines)} pipelines):")
            for p in category_pipelines:
                logger.info(f"    - {p['pipeline_id']}: {p['name']}")
    
    logger.info("=" * 80)
    logger.info("")
    
    return {
        "registry": registry,
        "registration_results": results,
        "initialization_results": init_results
    }


def _register_pipeline_categories(registry, results: Dict[str, Any]) -> None:
    """Register standard pipeline categories"""
    categories = [
        ("query", "Query Pipelines", "Pipelines for processing user queries"),
        ("data", "Data Pipelines", "Pipelines for data retrieval and analysis"),
        ("contextual", "Contextual Pipelines", "Pipelines for contextual graph operations"),
        ("analysis", "Analysis Pipelines", "Pipelines for data analysis and insights"),
        ("integration", "Integration Pipelines", "Pipelines for integration workflows")
    ]
    
    for cat_id, name, description in categories:
        registry.register_category(
            category_id=cat_id,
            name=name,
            description=description
        )
        results['categories'].append(cat_id)
    
    logger.info(f"Registered {len(categories)} pipeline categories")


async def _initialize_query_pipelines(
    registry,
    llm: Any,
    settings: Any,
    results: Dict[str, Any]
) -> None:
    """Initialize standard query pipelines"""
    logger.info("\nInitializing Query Pipelines...")
    
    try:
        # General-purpose query pipeline
        general_query_pipeline = AsyncQueryPipeline(
            name="general_query_pipeline",
            description="General-purpose async pipeline for user queries",
            llm=llm,
            model_name=settings.LLM_MODEL if settings else "gpt-4o"
        )
        
        await general_query_pipeline.initialize()
        
        registry.register_pipeline(
            pipeline_id="general_query",
            pipeline=general_query_pipeline,
            name="General Query Pipeline",
            description="Handles general user queries asynchronously",
            category="query",
            set_as_default=True
        )
        
        results['registered'].append("general_query")
        results['total_pipelines'] += 1
        logger.info("  ✓ Registered general_query pipeline")
        
    except Exception as e:
        logger.error(f"  ✗ Failed to register general query pipeline: {str(e)}")
        results['failed'].append({"pipeline_id": "general_query", "error": str(e)})


async def _initialize_data_pipelines(
    registry,
    llm: Any,
    settings: Any,
    db_pool: Any,
    vector_store_client: Any,
    embeddings: Any,
    results: Dict[str, Any]
) -> None:
    """Initialize data retrieval pipelines"""
    logger.info("\nInitializing Data Retrieval Pipelines...")
    
    try:
        from app.agents.data.retrieval_helper import RetrievalHelper
        from app.services.contextual_graph_service import ContextualGraphService
        
        # Create retrieval helper
        retrieval_helper = RetrievalHelper()
        
        # Create contextual graph service
        contextual_graph_service = ContextualGraphService(
            db_pool=db_pool,
            vector_store_client=vector_store_client,
            embeddings_model=embeddings,
            llm=llm
        )
        
        # Data retrieval pipeline
        data_retrieval_pipeline = AsyncDataRetrievalPipeline(
            name="data_retrieval_pipeline",
            description="Async pipeline for data retrieval with schema awareness",
            llm=llm,
            model_name=settings.LLM_MODEL if settings else "gpt-4o",
            data_source=db_pool,
            retrieval_helper=retrieval_helper,
            contextual_graph_service=contextual_graph_service
        )
        
        await data_retrieval_pipeline.initialize()
        
        registry.register_pipeline(
            pipeline_id="data_retrieval",
            pipeline=data_retrieval_pipeline,
            name="Data Retrieval Pipeline",
            description="Retrieves data with schema awareness and contextual information",
            category="data",
            set_as_default=True
        )
        
        results['registered'].append("data_retrieval")
        results['total_pipelines'] += 1
        logger.info("  ✓ Registered data_retrieval pipeline")
        
    except Exception as e:
        logger.error(f"  ✗ Failed to register data retrieval pipeline: {str(e)}")
        results['failed'].append({"pipeline_id": "data_retrieval", "error": str(e)})


async def _initialize_contextual_pipelines(
    registry,
    llm: Any,
    settings: Any,
    db_pool: Any,
    vector_store_client: Any,
    embeddings: Any,
    results: Dict[str, Any]
) -> None:
    """Initialize contextual graph pipelines"""
    logger.info("\nInitializing Contextual Graph Pipelines...")
    
    try:
        from app.services.contextual_graph_service import ContextualGraphService
        
        # Create contextual graph service
        contextual_graph_service = ContextualGraphService(
            db_pool=db_pool,
            vector_store_client=vector_store_client,
            embeddings_model=embeddings,
            llm=llm
        )
        
        # Contextual retrieval pipeline
        contextual_retrieval_pipeline = ContextualGraphRetrievalPipeline(
            contextual_graph_service=contextual_graph_service,
            llm=llm,
            model_name=settings.LLM_MODEL if settings else "gpt-4o"
        )
        
        await contextual_retrieval_pipeline.initialize()
        
        registry.register_pipeline(
            pipeline_id="contextual_retrieval",
            pipeline=contextual_retrieval_pipeline,
            name="Contextual Retrieval Pipeline",
            description="Retrieves relevant contexts and creates reasoning plans",
            category="contextual"
        )
        
        results['registered'].append("contextual_retrieval")
        results['total_pipelines'] += 1
        logger.info("  ✓ Registered contextual_retrieval pipeline")
        
        # Contextual reasoning pipeline
        contextual_reasoning_pipeline = ContextualGraphReasoningPipeline(
            contextual_graph_service=contextual_graph_service,
            llm=llm,
            model_name=settings.LLM_MODEL if settings else "gpt-4o"
        )
        
        await contextual_reasoning_pipeline.initialize()
        
        registry.register_pipeline(
            pipeline_id="contextual_reasoning",
            pipeline=contextual_reasoning_pipeline,
            name="Contextual Reasoning Pipeline",
            description="Performs context-aware reasoning using contextual graphs",
            category="contextual",
            set_as_default=True
        )
        
        results['registered'].append("contextual_reasoning")
        results['total_pipelines'] += 1
        logger.info("  ✓ Registered contextual_reasoning pipeline")
        
    except Exception as e:
        logger.error(f"  ✗ Failed to register contextual pipelines: {str(e)}")
        results['failed'].append({"pipeline_id": "contextual_pipelines", "error": str(e)})


async def cleanup_pipeline_registry() -> Dict[str, Any]:
    """
    Clean up all pipelines in the registry
    
    Should be called on application shutdown
    
    Returns:
        Dictionary with cleanup results
    """
    logger.info("Cleaning up pipeline registry...")
    
    registry = get_pipeline_registry()
    cleanup_results = await registry.cleanup_all()
    
    logger.info(f"Pipeline registry cleanup complete: {cleanup_results['cleaned_up']} cleaned up, "
               f"{cleanup_results['failed']} failed")
    
    return cleanup_results


def get_pipeline_from_registry(
    pipeline_id: str,
    category: Optional[str] = None
) -> Optional[Any]:
    """
    Convenience function to get a pipeline from the registry
    
    Args:
        pipeline_id: Pipeline ID
        category: Optional category (if provided, uses category-based lookup)
        
    Returns:
        Pipeline instance or None
    """
    registry = get_pipeline_registry()
    
    if category:
        return registry.get_category_pipeline(category, pipeline_id)
    else:
        return registry.get_pipeline(pipeline_id)

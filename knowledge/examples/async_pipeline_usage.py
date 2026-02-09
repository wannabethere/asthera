"""
Example Usage of Async Query Pipelines

Demonstrates how to use the async pipeline registry and query pipelines
"""
import asyncio
import logging
from typing import Dict, Any

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_general_query():
    """Example: Using general query pipeline"""
    from app.pipelines import get_pipeline_registry
    
    logger.info("=" * 80)
    logger.info("Example 1: General Query Pipeline")
    logger.info("=" * 80)
    
    # Get pipeline from registry
    registry = get_pipeline_registry()
    pipeline = registry.get_pipeline("general_query")
    
    if not pipeline:
        logger.error("General query pipeline not found - ensure registry is initialized")
        return
    
    # Run query
    result = await pipeline.run(
        inputs={
            "query": "What are the key compliance requirements for SOC2?",
            "context": {
                "domain": "compliance",
                "framework": "SOC2"
            },
            "options": {
                "include_details": True,
                "max_results": 10
            }
        }
    )
    
    logger.info(f"Query successful: {result.get('success')}")
    logger.info(f"Processing time: {result.get('metadata', {}).get('processing_time', 0):.2f}s")
    logger.info(f"Result data: {result.get('data', {})}")
    logger.info("")


async def example_data_retrieval():
    """Example: Using data retrieval pipeline"""
    from app.pipelines import get_pipeline_registry
    
    logger.info("=" * 80)
    logger.info("Example 2: Data Retrieval Pipeline")
    logger.info("=" * 80)
    
    # Get pipeline from registry
    registry = get_pipeline_registry()
    pipeline = registry.get_category_pipeline("data")  # Get default data pipeline
    
    if not pipeline:
        logger.error("Data retrieval pipeline not found - ensure registry is initialized")
        return
    
    # Run data retrieval query
    result = await pipeline.run(
        inputs={
            "query": "Get all high-severity vulnerabilities",
            "context": {
                "project_id": "my_project_123",
                "domain": "security"
            },
            "options": {
                "schema_limit": 5,
                "column_limit": 50,
                "context_limit": 3,
                "include_metadata": True
            },
            "filters": {
                "severity": "high",
                "status": "open"
            }
        }
    )
    
    logger.info(f"Query successful: {result.get('success')}")
    logger.info(f"Processing time: {result.get('metadata', {}).get('processing_time', 0):.2f}s")
    
    data = result.get('data', {})
    logger.info(f"Schemas found: {data.get('metadata', {}).get('schema_count', 0)}")
    logger.info(f"Contexts found: {data.get('metadata', {}).get('context_count', 0)}")
    logger.info(f"Retrieved records: {data.get('metadata', {}).get('retrieved_count', 0)}")
    logger.info("")


async def example_contextual_reasoning():
    """Example: Using contextual reasoning pipeline"""
    from app.pipelines import get_pipeline_registry
    
    logger.info("=" * 80)
    logger.info("Example 3: Contextual Reasoning Pipeline")
    logger.info("=" * 80)
    
    # Get pipeline from registry
    registry = get_pipeline_registry()
    pipeline = registry.get_pipeline("contextual_reasoning")
    
    if not pipeline:
        logger.error("Contextual reasoning pipeline not found - ensure registry is initialized")
        return
    
    # First, get contexts using retrieval pipeline
    retrieval_pipeline = registry.get_pipeline("contextual_retrieval")
    if not retrieval_pipeline:
        logger.error("Contextual retrieval pipeline not found")
        return
    
    # Step 1: Retrieve contexts
    retrieval_result = await retrieval_pipeline.run(
        inputs={
            "query": "What controls are needed for data encryption?",
            "context": {
                "framework": "SOC2",
                "domain": "security"
            },
            "top_k": 5
        }
    )
    
    if not retrieval_result.get("success"):
        logger.error(f"Context retrieval failed: {retrieval_result.get('error')}")
        return
    
    contexts = retrieval_result.get("data", {}).get("contexts", [])
    reasoning_plan = retrieval_result.get("data", {}).get("reasoning_plan", {})
    
    logger.info(f"Retrieved {len(contexts)} contexts")
    
    if not contexts:
        logger.info("No contexts found - skipping reasoning")
        return
    
    # Step 2: Perform reasoning
    reasoning_result = await pipeline.run(
        inputs={
            "query": "What controls are needed for data encryption?",
            "context_id": contexts[0].get("context_id") if contexts else None,
            "reasoning_plan": reasoning_plan,
            "max_hops": 3,
            "reasoning_type": "multi_hop"
        }
    )
    
    logger.info(f"Reasoning successful: {reasoning_result.get('success')}")
    
    data = reasoning_result.get('data', {})
    logger.info(f"Reasoning path length: {len(data.get('reasoning_path', []))}")
    logger.info(f"Final answer: {data.get('final_answer', 'N/A')[:200]}...")
    logger.info("")


async def example_custom_query_pipeline():
    """Example: Creating and registering a custom query pipeline"""
    from app.pipelines import AsyncQueryPipeline, get_pipeline_registry
    from langchain_openai import ChatOpenAI
    
    logger.info("=" * 80)
    logger.info("Example 4: Custom Query Pipeline")
    logger.info("=" * 80)
    
    # Define custom query processor
    async def custom_processor(query: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Custom query processor that transforms queries"""
        context = params.get("context", {})
        options = params.get("options", {})
        
        # Custom processing logic
        transformed_query = f"[CUSTOM] {query.upper()}"
        
        return {
            "query": query,
            "transformed_query": transformed_query,
            "context": context,
            "options": options,
            "custom_processing": True,
            "message": "This is a custom query processor"
        }
    
    # Create custom pipeline
    custom_pipeline = AsyncQueryPipeline(
        name="custom_query_pipeline",
        description="Custom async pipeline with custom processor",
        llm=ChatOpenAI(model="gpt-4o", temperature=0.2),
        query_processor=custom_processor
    )
    
    await custom_pipeline.initialize()
    
    # Register in registry
    registry = get_pipeline_registry()
    registry.register_pipeline(
        pipeline_id="my_custom_query",
        pipeline=custom_pipeline,
        name="My Custom Query Pipeline",
        description="Demonstrates custom query processing",
        category="query"
    )
    
    logger.info("Registered custom pipeline")
    
    # Use custom pipeline
    result = await custom_pipeline.run(
        inputs={
            "query": "test query",
            "context": {"test": True},
            "options": {"custom_option": "value"}
        }
    )
    
    logger.info(f"Custom pipeline result: {result.get('data', {})}")
    logger.info("")


async def example_list_pipelines():
    """Example: List all available pipelines"""
    from app.pipelines import get_pipeline_registry
    
    logger.info("=" * 80)
    logger.info("Example 5: List Available Pipelines")
    logger.info("=" * 80)
    
    registry = get_pipeline_registry()
    
    # List all categories
    categories = registry.list_categories()
    logger.info(f"\nAvailable Categories ({len(categories)}):")
    for cat in categories:
        logger.info(f"  - {cat['category_id']}: {cat['name']} ({cat['pipeline_count']} pipelines)")
    
    # List pipelines by category
    for cat in categories:
        pipelines = registry.list_pipelines(category=cat['category_id'])
        if pipelines:
            logger.info(f"\n{cat['name']} Pipelines:")
            for p in pipelines:
                status = "✓ Active" if p['is_active'] else "✗ Inactive"
                logger.info(f"  {status} {p['pipeline_id']}: {p['name']}")
                logger.info(f"      {p['description']}")
    
    logger.info("")


async def example_pipeline_assembly():
    """Example: Using pipeline assembly to combine pipelines"""
    from app.pipelines import (
        PipelineAssembly,
        PipelineStep,
        PipelineAssemblyConfig,
        PipelineExecutionMode,
        get_pipeline_registry
    )
    
    logger.info("=" * 80)
    logger.info("Example 6: Pipeline Assembly")
    logger.info("=" * 80)
    
    registry = get_pipeline_registry()
    
    # Get pipelines
    retrieval_pipeline = registry.get_pipeline("contextual_retrieval")
    reasoning_pipeline = registry.get_pipeline("contextual_reasoning")
    
    if not retrieval_pipeline or not reasoning_pipeline:
        logger.error("Required pipelines not found")
        return
    
    # Create assembly
    config = PipelineAssemblyConfig(
        assembly_id="contextual_qa_assembly",
        assembly_name="Contextual Q&A Assembly",
        description="Retrieves contexts and performs reasoning",
        execution_mode=PipelineExecutionMode.SEQUENTIAL
    )
    
    assembly = PipelineAssembly(config=config)
    
    # Add retrieval step
    assembly.add_step(
        PipelineStep(
            pipeline=retrieval_pipeline,
            step_id="retrieve",
            step_name="Context Retrieval",
            input_mapper=lambda state: {
                "query": state.get("query"),
                "top_k": 5
            }
        )
    )
    
    # Add reasoning step
    assembly.add_step(
        PipelineStep(
            pipeline=reasoning_pipeline,
            step_id="reason",
            step_name="Contextual Reasoning",
            input_mapper=lambda state: {
                "query": state.get("query"),
                "context_id": state.get("contexts", [{}])[0].get("context_id"),
                "reasoning_plan": state.get("reasoning_plan"),
                "reasoning_type": "multi_hop"
            },
            condition=lambda state: bool(state.get("contexts"))
        )
    )
    
    # Initialize and run assembly
    await assembly.initialize()
    
    result = await assembly.run(
        inputs={
            "query": "What are the access control requirements?"
        }
    )
    
    logger.info(f"Assembly successful: {result.get('success')}")
    logger.info(f"Steps executed: {result.get('data', {}).get('steps_executed', 0)}")
    logger.info("")


async def main():
    """
    Main function to run all examples
    
    NOTE: These examples assume the pipeline registry has been initialized
    at application startup. In a real application, this would be done in
    app/core/startup.py
    """
    from app.core.dependencies import get_dependencies
    from app.core.pipeline_startup import initialize_pipeline_registry
    
    logger.info("Initializing dependencies and pipeline registry...")
    
    # Get dependencies
    dependencies = get_dependencies()
    
    # Initialize pipeline registry
    init_result = await initialize_pipeline_registry(dependencies)
    
    logger.info(f"Pipeline registry initialized: {init_result['registration_results']['total_pipelines']} pipelines")
    logger.info("")
    
    # Run examples
    try:
        await example_list_pipelines()
        await example_general_query()
        await example_data_retrieval()
        await example_contextual_reasoning()
        await example_custom_query_pipeline()
        await example_pipeline_assembly()
        
    except Exception as e:
        logger.error(f"Error running examples: {str(e)}", exc_info=True)
    
    finally:
        # Cleanup
        from app.core.pipeline_startup import cleanup_pipeline_registry
        logger.info("Cleaning up pipeline registry...")
        await cleanup_pipeline_registry()


if __name__ == "__main__":
    asyncio.run(main())

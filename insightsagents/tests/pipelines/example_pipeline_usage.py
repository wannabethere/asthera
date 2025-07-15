#!/usr/bin/env python3
"""
Example usage of the registered pipelines in PipelineContainer

This script demonstrates how to:
1. Initialize the PipelineContainer
2. Use the Analysis Intent Classification Pipeline
3. Use the Self-Correcting Pipeline Code Generation Pipeline
"""

import asyncio
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_analysis_intent_classification():
    """Example of using the Analysis Intent Classification Pipeline"""
    
    from app.pipelines.pipeline_container import PipelineContainer, PipelineType
    
    try:
        # Initialize the pipeline container
        logger.info("Initializing PipelineContainer...")
        container = await PipelineContainer.initialize_async()
        
        # Get the analysis intent pipeline
        analysis_pipeline = container.get_analysis_intent_pipeline()
        
        # Example question for classification
        question = "How does the 5-day rolling variance of flux change over time for each group of projects, cost centers, and departments?"
        
        logger.info(f"Classifying intent for question: {question}")
        
        # Run the classification
        result = await analysis_pipeline.run(
            question=question,
            dataframe_description="Financial metrics dataset with project performance data",
            dataframe_summary="Contains 10,000 rows with daily metrics from 2023-2024",
            available_columns=["flux", "timestamp", "projects", "cost_centers", "departments"],
            enable_quick_check=True,
            enable_llm_feasibility=True
        )
        
        # Display results
        logger.info("Classification Results:")
        logger.info(f"Status: {result['status']}")
        logger.info(f"Intent Type: {result['classification']['intent_type']}")
        logger.info(f"Confidence Score: {result['classification']['confidence_score']}")
        logger.info(f"Can be answered: {result['classification']['can_be_answered']}")
        logger.info(f"Feasibility Score: {result['classification']['feasibility_score']}")
        logger.info(f"Suggested Functions: {result['classification']['suggested_functions']}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in analysis intent classification: {e}")
        raise


async def example_self_correcting_pipeline_codegen():
    """Example of using the Self-Correcting Pipeline Code Generation Pipeline"""
    
    from app.pipelines.pipeline_container import PipelineContainer, PipelineType
    
    try:
        # Initialize the pipeline container
        logger.info("Initializing PipelineContainer...")
        container = await PipelineContainer.initialize_async()
        
        # Get the self-correcting pipeline codegen
        codegen_pipeline = container.get_self_correcting_pipeline_codegen()
        
        # Example context and function for code generation
        context = "Calculate the variance of sales data over time with rolling windows"
        function_name = "variance_analysis"
        
        logger.info(f"Generating pipeline code for: {context}")
        logger.info(f"Function: {function_name}")
        
        # Run the code generation
        result = await codegen_pipeline.run(
            context=context,
            function_name=function_name,
            function_inputs={
                "columns": ["sales"],
                "method": "rolling",
                "window": 5
            },
            dataframe_name="df",
            classification={
                "intent_type": "time_series_analysis",
                "confidence_score": 0.95,
                "suggested_functions": ["variance_analysis"]
            },
            dataset_description="Sales dataset with daily metrics",
            columns_description={
                "sales": "Daily sales amount",
                "timestamp": "Date of the sale"
            }
        )
        
        # Display results
        logger.info("Code Generation Results:")
        logger.info(f"Status: {result['status']}")
        if result['status'] == 'success':
            logger.info("Generated Code:")
            logger.info(result['result'])
        else:
            logger.error(f"Error: {result.get('error', {}).get('message', 'Unknown error')}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in self-correcting pipeline codegen: {e}")
        raise


async def example_batch_processing():
    """Example of batch processing with the Analysis Intent Pipeline"""
    
    from app.pipelines.pipeline_container import PipelineContainer, PipelineType
    
    try:
        # Initialize the pipeline container
        logger.info("Initializing PipelineContainer...")
        container = await PipelineContainer.initialize_async()
        
        # Get the analysis intent pipeline
        analysis_pipeline = container.get_analysis_intent_pipeline()
        
        # Multiple questions for batch processing
        questions = [
            {
                "question": "What is the variance of my data?",
                "dataframe_description": "Test dataset",
                "available_columns": ["value", "timestamp"]
            },
            {
                "question": "Show me user retention over time",
                "dataframe_description": "User dataset",
                "available_columns": ["user_id", "timestamp"]
            },
            {
                "question": "Calculate the mean of sales by region",
                "dataframe_description": "Sales dataset",
                "available_columns": ["sales", "region", "date"]
            }
        ]
        
        logger.info(f"Processing {len(questions)} questions in batch...")
        
        # Run batch classification
        results = await analysis_pipeline.batch_classify_intents(questions, batch_size=2)
        
        # Display results
        logger.info("Batch Processing Results:")
        for i, result in enumerate(results):
            logger.info(f"Question {i+1}: {questions[i]['question']}")
            logger.info(f"  Status: {result['status']}")
            if result['status'] == 'success':
                logger.info(f"  Intent: {result['classification']['intent_type']}")
                logger.info(f"  Confidence: {result['classification']['confidence_score']}")
            else:
                logger.error(f"  Error: {result.get('error', {}).get('message', 'Unknown error')}")
            logger.info("")
        
        return results
        
    except Exception as e:
        logger.error(f"Error in batch processing: {e}")
        raise


async def example_pipeline_metrics():
    """Example of getting pipeline metrics and information"""
    
    from app.pipelines.pipeline_container import PipelineContainer, PipelineType
    
    try:
        # Initialize the pipeline container
        logger.info("Initializing PipelineContainer...")
        container = await PipelineContainer.initialize_async()
        
        # Get pipeline information
        pipeline_info = container.get_pipeline_info()
        
        logger.info("Pipeline Information:")
        for name, info in pipeline_info.items():
            logger.info(f"Pipeline: {name}")
            logger.info(f"  Name: {info['name']}")
            logger.info(f"  Version: {info['version']}")
            logger.info(f"  Description: {info['description']}")
            logger.info(f"  Initialized: {info['is_initialized']}")
            
            # Display metrics if available
            if info['metrics']:
                logger.info("  Metrics:")
                for metric_name, metric_value in info['metrics'].items():
                    logger.info(f"    {metric_name}: {metric_value}")
            logger.info("")
        
        # Get available pipeline names
        pipeline_names = container.get_pipeline_names()
        logger.info(f"Available pipelines: {pipeline_names}")
        
        return pipeline_info
        
    except Exception as e:
        logger.error(f"Error getting pipeline metrics: {e}")
        raise


async def main():
    """Main function to run all examples"""
    
    logger.info("Starting Pipeline Examples...")
    from app.pipelines.pipeline_container import PipelineContainer, PipelineType
    try:
        # Example 1: Analysis Intent Classification
        logger.info("\n" + "="*50)
        logger.info("EXAMPLE 1: Analysis Intent Classification")
        logger.info("="*50)
        await example_analysis_intent_classification()
        
        # Example 2: Self-Correcting Pipeline Code Generation
        logger.info("\n" + "="*50)
        logger.info("EXAMPLE 2: Self-Correcting Pipeline Code Generation")
        logger.info("="*50)
        await example_self_correcting_pipeline_codegen()
        
        # Example 3: Batch Processing
        logger.info("\n" + "="*50)
        logger.info("EXAMPLE 3: Batch Processing")
        logger.info("="*50)
        await example_batch_processing()
        
        # Example 4: Pipeline Metrics
        logger.info("\n" + "="*50)
        logger.info("EXAMPLE 4: Pipeline Metrics")
        logger.info("="*50)
        await example_pipeline_metrics()
        
        logger.info("\n" + "="*50)
        logger.info("All examples completed successfully!")
        logger.info("="*50)
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise
    finally:
        # Cleanup
        try:
            container = PipelineContainer.get_instance()
            await container.cleanup_all_pipelines()
            logger.info("Cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


if __name__ == "__main__":
    # Run the examples
    asyncio.run(main()) 
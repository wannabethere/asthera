#!/usr/bin/env python3
"""
Example usage of the AnalysisIntentClassificationPipeline

This script demonstrates how to use the pipeline for various analysis scenarios.
"""

import asyncio
import logging
from typing import Dict, Any
import chromadb
from langchain_openai import ChatOpenAI

from app.pipelines.mlpipelines.stats_pipelines import (
    AnalysisIntentClassificationPipeline,
    create_analysis_intent_pipeline
)
from app.storage.documents import DocumentChromaStore
from app.core.settings import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()


async def setup_chroma_collections() -> tuple:
    """
    Set up ChromaDB collections for function definitions, examples, and insights
    
    Returns:
        Tuple of (function_collection, example_collection, insights_collection)
    """
    try:
        # Initialize ChromaDB client
        client = chromadb.PersistentClient(path=settings.CHROMA_STORE_PATH)
        
        # Create collections
        function_collection = DocumentChromaStore(
            persistent_client=client,
            collection_name="function_definitions"
        )
        
        example_collection = DocumentChromaStore(
            persistent_client=client,
            collection_name="function_examples"
        )
        
        insights_collection = DocumentChromaStore(
            persistent_client=client,
            collection_name="function_insights"
        )
        
        logger.info("ChromaDB collections initialized successfully")
        return function_collection, example_collection, insights_collection
        
    except Exception as e:
        logger.error(f"Failed to setup ChromaDB collections: {e}")
        # Return None collections if setup fails
        return None, None, None


async def setup_llm() -> ChatOpenAI:
    """
    Set up the language model
    
    Returns:
        Configured ChatOpenAI instance
    """
    try:
        llm = ChatOpenAI(
            model="gpt-4",
            temperature=0.1,
            openai_api_key=settings.OPENAI_API_KEY
        )
        logger.info("Language model initialized successfully")
        return llm
    except Exception as e:
        logger.error(f"Failed to setup language model: {e}")
        raise


async def example_single_classification(pipeline: AnalysisIntentClassificationPipeline):
    """
    Example of single question classification
    
    Args:
        pipeline: Initialized pipeline instance
    """
    print("\n" + "="*60)
    print("EXAMPLE 1: Single Question Classification")
    print("="*60)
    
    # Test question about time series analysis
    result = await pipeline.run(
        question="How does the 5-day rolling variance of flux change over time for each group of projects, cost centers, and departments?",
        dataframe_description="Financial metrics dataset with project performance data",
        dataframe_summary="Contains 10,000 rows with daily metrics from 2023-2024, covering flux measurements across different organizational units",
        available_columns=["flux", "timestamp", "projects", "cost_centers", "departments", "revenue", "employee_count"]
    )
    
    print(f"Question: {result['input']['question']}")
    print(f"Status: {result['status']}")
    
    if result['status'] == 'success':
        classification = result['classification']
        print(f"Intent Type: {classification['intent_type']}")
        print(f"Confidence Score: {classification['confidence_score']:.2f}")
        print(f"Can be answered: {classification['can_be_answered']}")
        print(f"Feasibility Score: {classification['feasibility_score']:.2f}")
        print(f"Suggested Functions: {classification['suggested_functions']}")
        print(f"Required Columns: {classification['required_data_columns']}")
        print(f"Missing Columns: {classification['missing_columns']}")
        print(f"Rephrased Question: {classification['rephrased_question']}")
        print(f"Reasoning: {classification['reasoning']}")
        
        if classification['data_suggestions']:
            print(f"Data Suggestions: {classification['data_suggestions']}")
    else:
        print(f"Error: {result.get('error', {}).get('message', 'Unknown error')}")


async def example_batch_classification(pipeline: AnalysisIntentClassificationPipeline):
    """
    Example of batch question classification
    
    Args:
        pipeline: Initialized pipeline instance
    """
    print("\n" + "="*60)
    print("EXAMPLE 2: Batch Question Classification")
    print("="*60)
    
    # Multiple questions to classify
    questions = [
        {
            "question": "What is the variance of my data?",
            "dataframe_description": "Simple metrics dataset",
            "dataframe_summary": "Contains basic statistical measurements",
            "available_columns": ["value", "timestamp", "category"]
        },
        {
            "question": "Show me user retention over the last 6 months",
            "dataframe_description": "User activity dataset",
            "dataframe_summary": "Contains user signup and activity data",
            "available_columns": ["user_id", "signup_date", "last_activity", "subscription_type"]
        },
        {
            "question": "I want to segment my customers based on their behavior",
            "dataframe_description": "Customer behavior dataset",
            "dataframe_summary": "Contains customer purchase and interaction data",
            "available_columns": ["customer_id", "purchase_amount", "visit_frequency", "avg_order_value", "lifetime_value"]
        },
        {
            "question": "Detect anomalies in our sales data",
            "dataframe_description": "Sales dataset",
            "dataframe_summary": "Daily sales data across different regions",
            "available_columns": ["date", "region", "sales_amount", "product_category", "customer_count"]
        }
    ]
    
    print(f"Processing {len(questions)} questions in batch...")
    results = await pipeline.batch_classify_intents(questions, batch_size=2)
    
    for i, result in enumerate(results):
        print(f"\n--- Question {i+1} ---")
        print(f"Question: {result['input']['question']}")
        print(f"Status: {result['status']}")
        
        if result['status'] == 'success':
            classification = result['classification']
            print(f"Intent: {classification['intent_type']}")
            print(f"Confidence: {classification['confidence_score']:.2f}")
            print(f"Can answer: {classification['can_be_answered']}")
            print(f"Functions: {classification['suggested_functions']}")
        else:
            print(f"Error: {result.get('error', {}).get('message', 'Unknown error')}")


async def example_with_retry_logic(pipeline: AnalysisIntentClassificationPipeline):
    """
    Example of classification with retry logic
    
    Args:
        pipeline: Initialized pipeline instance
    """
    print("\n" + "="*60)
    print("EXAMPLE 3: Classification with Retry Logic")
    print("="*60)
    
    # Test with retry logic
    result = await pipeline.classify_with_retry(
        max_retries=2,
        retry_delay=0.5,
        question="Calculate the correlation between revenue and customer satisfaction scores",
        dataframe_description="Business metrics dataset",
        dataframe_summary="Contains revenue and customer satisfaction data",
        available_columns=["revenue", "satisfaction_score", "date", "region"]
    )
    
    print(f"Question: {result['input']['question']}")
    print(f"Status: {result['status']}")
    
    if result['status'] == 'success':
        classification = result['classification']
        print(f"Intent: {classification['intent_type']}")
        print(f"Confidence: {classification['confidence_score']:.2f}")
        print(f"Functions: {classification['suggested_functions']}")
    else:
        print(f"Error after retries: {result.get('error', {}).get('message', 'Unknown error')}")


async def example_pipeline_metrics(pipeline: AnalysisIntentClassificationPipeline):
    """
    Example of accessing pipeline metrics
    
    Args:
        pipeline: Initialized pipeline instance
    """
    print("\n" + "="*60)
    print("EXAMPLE 4: Pipeline Metrics and Configuration")
    print("="*60)
    
    # Get pipeline metrics
    metrics = pipeline.get_metrics()
    print("Pipeline Metrics:")
    print(f"  Total Requests: {metrics['total_requests']}")
    print(f"  Successful Classifications: {metrics['successful_classifications']}")
    print(f"  Failed Classifications: {metrics['failed_classifications']}")
    print(f"  Success Rate: {metrics['success_rate']:.2%}")
    print(f"  Average Processing Time: {metrics['average_processing_time']:.2f}s")
    print(f"  Total Processing Time: {metrics['total_processing_time']:.2f}s")
    
    # Get pipeline configuration
    config = pipeline.get_configuration()
    print("\nPipeline Configuration:")
    print(f"  Name: {config['pipeline_name']}")
    print(f"  Version: {config['pipeline_version']}")
    print(f"  Max Functions to Retrieve: {config['max_functions_to_retrieve']}")
    print(f"  Initialized: {config['is_initialized']}")
    
    # Get available analysis types
    analyses = pipeline.get_available_analyses()
    print("\nAvailable Analysis Types:")
    for analysis_type, description in analyses.items():
        print(f"  {analysis_type}: {description}")


async def example_input_validation(pipeline: AnalysisIntentClassificationPipeline):
    """
    Example of input validation
    
    Args:
        pipeline: Initialized pipeline instance
    """
    print("\n" + "="*60)
    print("EXAMPLE 5: Input Validation")
    print("="*60)
    
    # Test valid input
    valid_input = {
        "question": "What is the trend in our sales data?",
        "dataframe_description": "Sales dataset",
        "available_columns": ["date", "sales", "region"]
    }
    
    validation_result = await pipeline.validate_input(**valid_input)
    print("Valid Input Test:")
    print(f"  Is Valid: {validation_result['is_valid']}")
    print(f"  Errors: {validation_result['errors']}")
    print(f"  Warnings: {validation_result['warnings']}")
    
    # Test invalid input
    invalid_input = {
        "question": "",  # Empty question
        "available_columns": "not_a_list"  # Wrong type
    }
    
    validation_result = await pipeline.validate_input(**invalid_input)
    print("\nInvalid Input Test:")
    print(f"  Is Valid: {validation_result['is_valid']}")
    print(f"  Errors: {validation_result['errors']}")
    print(f"  Warnings: {validation_result['warnings']}")


async def main():
    """
    Main function to run all examples
    """
    print("Analysis Intent Classification Pipeline Examples")
    print("="*60)
    
    try:
        # Setup components
        print("Setting up components...")
        llm = await setup_llm()
        function_collection, example_collection, insights_collection = await setup_chroma_collections()
        
        # Create pipeline
        pipeline = create_analysis_intent_pipeline(
            llm=llm,
            function_collection=function_collection,
            example_collection=example_collection,
            insights_collection=insights_collection,
            pipeline_config={
                "enable_quick_check": True,
                "enable_llm_feasibility": True,
                "max_functions_to_retrieve": 10
            }
        )
        
        # Initialize pipeline
        await pipeline.initialize()
        print("Pipeline initialized successfully!")
        
        # Run examples
        await example_single_classification(pipeline)
        await example_batch_classification(pipeline)
        await example_with_retry_logic(pipeline)
        await example_pipeline_metrics(pipeline)
        await example_input_validation(pipeline)
        
        # Cleanup
        await pipeline.cleanup()
        print("\nPipeline cleaned up successfully!")
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        print(f"Error: {e}")


if __name__ == "__main__":
    # Run the examples
    asyncio.run(main()) 
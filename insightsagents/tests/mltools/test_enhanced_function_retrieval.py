#!/usr/bin/env python3
"""
Test Enhanced Function Retrieval Service

This script demonstrates how to use the enhanced function retrieval service
with retrieval helper and input extractor using comprehensive definitions.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.tools.mltools.registry.enhanced_comprehensive_registry import (
    initialize_enhanced_comprehensive_registry,
    EnhancedComprehensiveRegistry
)
from app.core.dependencies import get_llm
from app.core.dependencies import get_doc_store_provider

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test-enhanced-function-retrieval")

def print_section(title: str, content: str = ""):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f"📋 {title}")
    print(f"{'='*60}")
    if content:
        print(content)

def print_success(message: str):
    """Print a success message with emoji."""
    print(f"✅ {message}")

def print_warning(message: str):
    """Print a warning message with emoji."""
    print(f"⚠️  {message}")

def print_error(message: str):
    """Print an error message with emoji."""
    print(f"❌ {message}")

def print_info(message: str):
    """Print an info message with emoji."""
    print(f"ℹ️  {message}")

def pretty_print_json(data: Dict[str, Any], title: str = "Data"):
    """Pretty print JSON data with formatting."""
    print(f"\n📊 {title}:")
    print("-" * 40)
    try:
        formatted_json = json.dumps(data, indent=2, default=str)
        print(formatted_json)
    except Exception as e:
        print(f"Error formatting JSON: {e}")
        print(data)

def print_function_match_info(match: Dict[str, Any], index: int = 1):
    """Pretty print function match information."""
    print(f"\n🔧 Function Match #{index}:")
    print("-" * 40)
    
    # Basic info
    name = match.get('function_name', 'Unknown')
    pipe = match.get('pipe_name', 'Unknown')
    category = match.get('category', 'Unknown')
    relevance_score = match.get('relevance_score', 0.0)
    reasoning = match.get('reasoning', 'No reasoning provided')
    
    print(f"📝 Name: {name}")
    print(f"🔗 Pipeline: {pipe}")
    print(f"🏷️  Category: {category}")
    print(f"🎯 Relevance Score: {relevance_score:.2f}")
    print(f"💭 Reasoning: {reasoning}")
    
    # Description
    description = match.get('description', 'No description available')
    if description:
        print(f"\n📋 Description:")
        print(f"   {description}")
    
    # Usage description
    usage = match.get('usage_description', '')
    if usage:
        print(f"\n🔧 Usage:")
        print(f"   {usage}")
    
    # Extracted parameters
    extracted_params = match.get('extracted_parameters', {})
    if extracted_params:
        print(f"\n⚙️  Extracted Parameters:")
        for key, value in extracted_params.items():
            print(f"   • {key}: {value}")
    
    # Examples count
    examples = match.get('examples', [])
    instructions = match.get('instructions', [])
    historical_rules = match.get('historical_rules', [])
    
    print(f"\n📊 Context:")
    print(f"   Examples: {len(examples)}")
    print(f"   Instructions: {len(instructions)}")
    print(f"   Historical Rules: {len(historical_rules)}")

def print_step_matches(step_matches: Dict[int, List[Dict[str, Any]]]):
    """Pretty print step matches."""
    print_section("Step-Function Matches")
    
    if not step_matches:
        print_warning("No step matches found")
        return
    
    for step_num, functions in step_matches.items():
        print(f"\n📋 Step {step_num}:")
        print("-" * 30)
        
        if not functions:
            print_warning("No functions matched to this step")
            continue
        
        print_success(f"Matched {len(functions)} function(s)")
        
        for i, func in enumerate(functions, 1):
            print_function_match_info(func, i)

async def test_enhanced_function_retrieval():
    """Test the enhanced function retrieval service."""
    print_section("Enhanced Function Retrieval Test", 
                 "This test demonstrates the enhanced function retrieval service with comprehensive definitions.")
    
    try:
        # Initialize components
        print_section("Initializing Components")
        
        # Get LLM
        print_info("Getting LLM instance...")
        llm = get_llm()
        print_success("LLM initialized")
        
        # Initialize retrieval helper
        print_info("Initializing RetrievalHelper...")
        retrieval_helper = RetrievalHelper()
        print_success("RetrievalHelper initialized")
        
        # Initialize comprehensive registry
        print_info("Initializing Enhanced Comprehensive Registry...")
        comprehensive_registry = initialize_enhanced_comprehensive_registry(
            collection_name="comprehensive_ml_functions_test",
            force_recreate=False,  # Set to True if you want to recreate the collection
            enable_separate_collections=True
        )
        print_success("Enhanced Comprehensive Registry initialized")
        
        # Get document stores for input extraction
        print_info("Getting document stores...")
        doc_store_provider = get_doc_store_provider()
        document_stores = doc_store_provider.stores
        
        example_collection = document_stores.get("usage_examples")
        function_collection = document_stores.get("function_spec")
        insights_collection = document_stores.get("insights_store")
        
        print_success("Document stores retrieved")
        
        # Test data
        print_section("Test Data Setup")
        
        # Sample reasoning plan
        reasoning_plan = [
            {
                "step_number": 1,
                "step_title": "Data Preparation",
                "step_description": "Clean and prepare the dataset for analysis",
                "data_requirements": ["date_column", "value_column"]
            },
            {
                "step_number": 2,
                "step_title": "Time Series Analysis",
                "step_description": "Perform rolling variance analysis on the time series data",
                "data_requirements": ["date_column", "value_column", "window_size"]
            },
            {
                "step_number": 3,
                "step_title": "Anomaly Detection",
                "step_description": "Identify outliers and anomalies in the data",
                "data_requirements": ["value_column", "threshold"]
            }
        ]
        
        question = "Analyze the rolling variance of stock prices and detect anomalies"
        rephrased_question = "Calculate rolling variance for stock price data and identify outliers"
        dataframe_description = "Stock price dataset with date, price, and volume columns"
        dataframe_summary = "Daily stock prices from 2020-2024 with 1000+ records"
        available_columns = ["date", "price", "volume", "ticker"]
        project_id = "test_project"
        
        print_success("Test data prepared")
        pretty_print_json({
            "reasoning_plan": reasoning_plan,
            "question": question,
            "available_columns": available_columns
        }, "Test Configuration")
        
        # Test enhanced function retrieval
        print_section("Testing Enhanced Function Retrieval")
        
        print_info("Calling enhanced function retrieval...")
        result = await retrieval_helper.get_enhanced_function_retrieval(
            reasoning_plan=reasoning_plan,
            question=question,
            rephrased_question=rephrased_question,
            dataframe_description=dataframe_description,
            dataframe_summary=dataframe_summary,
            available_columns=available_columns,
            project_id=project_id,
            llm=llm,
            comprehensive_registry=comprehensive_registry,
            example_collection=example_collection,
            function_collection=function_collection,
            insights_collection=insights_collection
        )
        
        # Display results
        print_section("Retrieval Results")
        
        if "error" in result:
            print_error(f"Retrieval failed: {result['error']}")
            return
        
        print_success("Function retrieval completed successfully")
        
        # Display metrics
        print_info(f"Total functions retrieved: {result['total_functions_retrieved']}")
        print_info(f"Steps covered: {result['total_steps_covered']}")
        print_info(f"Average relevance score: {result['average_relevance_score']:.2f}")
        print_info(f"Confidence score: {result['confidence_score']:.2f}")
        print_info(f"Fallback used: {result['fallback_used']}")
        print_info(f"Reasoning: {result['reasoning']}")
        
        # Display step matches
        step_matches = result.get('step_matches', {})
        print_step_matches(step_matches)
        
        # Test with different query
        print_section("Testing with Different Query")
        
        different_question = "Perform cohort analysis on user retention data"
        different_reasoning_plan = [
            {
                "step_number": 1,
                "step_title": "Cohort Definition",
                "step_description": "Define user cohorts based on acquisition date",
                "data_requirements": ["user_id", "acquisition_date"]
            },
            {
                "step_number": 2,
                "step_title": "Retention Calculation",
                "step_description": "Calculate retention rates for each cohort",
                "data_requirements": ["user_id", "activity_date", "cohort_period"]
            }
        ]
        
        print_info(f"Testing with query: {different_question}")
        
        result2 = await retrieval_helper.get_enhanced_function_retrieval(
            reasoning_plan=different_reasoning_plan,
            question=different_question,
            rephrased_question=different_question,
            dataframe_description="User activity dataset with user_id, acquisition_date, and activity_date",
            dataframe_summary="User activity data with 10,000+ users and 50,000+ activity records",
            available_columns=["user_id", "acquisition_date", "activity_date", "activity_type"],
            project_id=project_id,
            llm=llm,
            comprehensive_registry=comprehensive_registry,
            example_collection=example_collection,
            function_collection=function_collection,
            insights_collection=insights_collection
        )
        
        if "error" not in result2:
            print_success("Second retrieval completed successfully")
            print_info(f"Total functions retrieved: {result2['total_functions_retrieved']}")
            print_info(f"Steps covered: {result2['total_steps_covered']}")
            print_info(f"Average relevance score: {result2['average_relevance_score']:.2f}")
            
            # Display step matches for second query
            step_matches2 = result2.get('step_matches', {})
            print_step_matches(step_matches2)
        else:
            print_error(f"Second retrieval failed: {result2['error']}")
        
        print_success("Enhanced function retrieval test completed successfully!")
        
    except Exception as e:
        print_error(f"Test failed: {e}")
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Main function to run the test."""
    await test_enhanced_function_retrieval()

if __name__ == "__main__":
    asyncio.run(main())

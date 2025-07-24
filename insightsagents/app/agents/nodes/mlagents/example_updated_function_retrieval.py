#!/usr/bin/env python3
"""
Example script demonstrating how to use the updated FunctionRetrieval class
with ChromaDB integration for retrieving function definitions.
"""

import asyncio
import json
from typing import Optional
from unittest.mock import Mock

# Import the FunctionRetrieval class
from function_retrieval import FunctionRetrieval, FunctionRetrievalResult


async def example_with_chromadb():
    """
    Example usage of the FunctionRetrieval class with ChromaDB integration
    """
    
    # Mock LLM for demonstration (replace with your actual LLM)
    mock_llm = Mock()
    
    # Create a realistic mock response with rephrased questions for each function
    mock_response = Mock()
    mock_response.content = '''
    {
        "top_functions": [
            {
                "function_name": "variance_analysis",
                "pipe_name": "MovingAggrPipe",
                "description": "Calculate moving variance and standard deviation for specified columns",
                "usage_description": "Measures volatility and variability over time. Useful for detecting changes in data variability, analyzing risk in financial data, and identifying periods of unusual activity in sensor data, financial transactions, or business metrics.",
                "relevance_score": 0.95,
                "reasoning": "The user specifically asks for rolling variance analysis, which directly matches this function's purpose of calculating moving variance over time.",
                "rephrased_question": "Calculate 5-day rolling variance of flux metric grouped by projects, cost centers, and departments over time"
            },
            {
                "function_name": "moving_variance",
                "pipe_name": "MovingAggrPipe",
                "description": "Calculate moving variance and standard deviation for specified columns",
                "usage_description": "Measures volatility and variability over time. Useful for detecting changes in data variability, analyzing risk in financial data, and identifying periods of unusual activity in sensor data, financial transactions, or business metrics.",
                "relevance_score": 0.9,
                "reasoning": "This function provides moving variance calculations which are essential for the user's rolling variance analysis request.",
                "rephrased_question": "Calculate moving variance for time series data with grouping by organizational units"
            },
            {
                "function_name": "aggregate_by_time",
                "pipe_name": "TrendPipe",
                "description": "Aggregate data by time periods",
                "usage_description": "Groups and summarizes data by time periods (daily, weekly, monthly, etc.). Essential for trend analysis, reducing noise in time series data, and creating time-based summaries for analysis.",
                "relevance_score": 0.8,
                "reasoning": "The user wants to analyze variance over time, so time-based aggregation would be useful for grouping data by time periods.",
                "rephrased_question": "Aggregate financial metrics by time periods for trend analysis"
            }
        ],
        "confidence_score": 0.9,
        "reasoning": "The user's question clearly indicates a need for rolling variance analysis, which is well-supported by the MovingAggrPipe functions. The question is specific enough to identify relevant functions and can be further refined for function definition lookup.",
        "suggested_pipes": ["MovingAggrPipe", "TrendPipe"],
        "total_functions_analyzed": 150
    }
    '''
    mock_llm.ainvoke = Mock(return_value=mock_response)
    
    # Mock ChromaDB collection for function definitions
    mock_function_collection = Mock()
    
    # Mock ChromaDB response for function definitions
    mock_chroma_response = {
        "documents": [[
            json.dumps({
                "function_name": "variance_analysis",
                "description": "Calculate moving variance and standard deviation for specified columns",
                "usage_description": "Measures volatility and variability over time. Useful for detecting changes in data variability, analyzing risk in financial data, and identifying periods of unusual activity in sensor data, financial transactions, or business metrics.",
                "parameters": {
                    "window_size": "int",
                    "columns": "list",
                    "group_by": "list"
                },
                "required_params": ["window_size", "columns"],
                "optional_params": ["group_by"],
                "category": "Time Series Analysis",
                "type_of_operation": "Moving Window"
            })
        ]],
        "distances": [[0.1]]  # Low distance = high relevance
    }
    mock_function_collection.semantic_searches = Mock(return_value=mock_chroma_response)
    
    # Initialize the FunctionRetrieval system with ChromaDB collection
    retrieval = FunctionRetrieval(
        llm=mock_llm,
        function_collection=mock_function_collection
    )
    
    # Example user question
    question = "How does the 5-day rolling variance of flux change over time for each group of projects, cost centers, and departments?"
    
    # Dataframe context
    dataframe_description = "Financial metrics dataset with project performance data"
    dataframe_summary = "Contains 10,000 rows with daily metrics from 2023-2024, covering flux measurements across different organizational units"
    available_columns = ["flux", "timestamp", "projects", "cost_centers", "departments", "revenue", "employee_count"]
    
    print("=== Updated Function Retrieval Example with ChromaDB ===\n")
    print(f"User Question: {question}")
    print(f"Dataframe Description: {dataframe_description}")
    print(f"Available Columns: {available_columns}")
    print("\n" + "="*80 + "\n")
    
    # Retrieve relevant functions with ChromaDB integration
    result = await retrieval.retrieve_relevant_functions(
        question=question,
        dataframe_description=dataframe_description,
        dataframe_summary=dataframe_summary,
        available_columns=available_columns
    )
    
    # Display results
    print("=== RETRIEVAL RESULTS ===\n")
    print(f"Confidence Score: {result.confidence_score:.2f}")
    print(f"Overall Reasoning: {result.reasoning}")
    print(f"Suggested Pipes: {', '.join(result.suggested_pipes)}")
    print(f"Total Functions Analyzed: {result.total_functions_analyzed}")
    
    print(f"\n=== TOP {len(result.top_functions)} RELEVANT FUNCTIONS WITH DEFINITIONS ===\n")
    
    for i, func in enumerate(result.top_functions, 1):
        print(f"{i}. {func.function_name} ({func.pipe_name})")
        print(f"   Relevance Score: {func.relevance_score:.2f}")
        print(f"   Description: {func.description}")
        print(f"   Usage: {func.usage_description[:100]}...")
        print(f"   Reasoning: {func.reasoning}")
        print(f"   Rephrased Question: {func.rephrased_question}")
        
        if func.function_definition:
            print(f"   ✅ Function Definition Retrieved:")
            definition = func.function_definition
            if isinstance(definition, dict):
                print(f"      - Parameters: {definition.get('parameters', 'N/A')}")
                print(f"      - Required: {definition.get('required_params', 'N/A')}")
                print(f"      - Optional: {definition.get('optional_params', 'N/A')}")
                print(f"      - Category: {definition.get('category', 'N/A')}")
                print(f"      - Type: {definition.get('type_of_operation', 'N/A')}")
        else:
            print(f"   ❌ No function definition retrieved")
        print()
    
    # Example of how to use the retrieved function definitions
    print("=== USING RETRIEVED FUNCTION DEFINITIONS ===\n")
    
    for func in result.top_functions:
        if func.function_definition:
            print(f"Function: {func.function_name}")
            print(f"Rephrased Question: {func.rephrased_question}")
            print(f"Definition: {json.dumps(func.function_definition, indent=2)}")
            print("-" * 50)
    
    return result


async def example_without_chromadb():
    """
    Example usage without ChromaDB (fallback to JSON library)
    """
    
    # Mock LLM
    mock_llm = Mock()
    mock_response = Mock()
    mock_response.content = '''
    {
        "top_functions": [
            {
                "function_name": "variance_analysis",
                "pipe_name": "MovingAggrPipe",
                "description": "Calculate moving variance",
                "usage_description": "Measures volatility over time",
                "relevance_score": 0.95,
                "reasoning": "Direct match for variance analysis",
                "rephrased_question": "Calculate variance analysis for time series data"
            }
        ],
        "confidence_score": 0.9,
        "reasoning": "Clear variance analysis request",
        "suggested_pipes": ["MovingAggrPipe"],
        "total_functions_analyzed": 150
    }
    '''
    mock_llm.ainvoke = Mock(return_value=mock_response)
    
    # Initialize without ChromaDB collection
    retrieval = FunctionRetrieval(llm=mock_llm)
    
    question = "What is the variance of my data?"
    
    print("=== Example Without ChromaDB ===\n")
    print(f"Question: {question}")
    
    result = await retrieval.retrieve_relevant_functions(
        question=question,
        dataframe_description="Sample dataset",
        dataframe_summary="Contains various metrics",
        available_columns=["value", "timestamp"]
    )
    
    print(f"Top Function: {result.top_functions[0].function_name if result.top_functions else 'None'}")
    print(f"Rephrased Question: {result.top_functions[0].rephrased_question if result.top_functions else 'None'}")
    print(f"Function Definition: {'Retrieved from JSON library' if result.top_functions[0].function_definition else 'Not retrieved'}")
    
    # Show the function definition details
    if result.top_functions and result.top_functions[0].function_definition:
        definition = result.top_functions[0].function_definition
        print(f"  - Description: {definition.get('description', 'N/A')}")
        print(f"  - Usage: {definition.get('usage_description', 'N/A')[:100]}...")
    
    return result


async def demonstrate_utility_methods():
    """
    Demonstrate the utility methods
    """
    print("\n=== UTILITY METHODS DEMONSTRATION ===\n")
    
    # Create a FunctionRetrieval instance (without LLM for utility methods)
    retrieval = FunctionRetrieval(llm=None)
    
    # Get all available pipes
    pipes = retrieval.get_all_pipes()
    print(f"Available Pipes: {', '.join(pipes)}")
    
    # Get functions from a specific pipe
    if "MovingAggrPipe" in pipes:
        functions = retrieval.get_pipe_functions("MovingAggrPipe")
        print(f"\nMovingAggrPipe Functions: {', '.join(functions[:5])}...")
    
    # Get function details
    if "MovingAggrPipe" in pipes:
        details = retrieval.get_function_details("variance_analysis", "MovingAggrPipe")
        if details:
            print(f"\nFunction Details for variance_analysis:")
            print(f"  Description: {details.get('description', 'N/A')}")
            print(f"  Usage: {details.get('usage_description', 'N/A')[:100]}...")
    
    # Search functions by keyword
    variance_functions = retrieval.search_functions_by_keyword("variance")
    print(f"\nFunctions containing 'variance': {len(variance_functions)} found")
    for pipe_name, func_name, _ in variance_functions[:3]:
        print(f"  - {func_name} ({pipe_name})")
    
    print("\n=== UTILITY METHODS COMPLETED ===")


async def main():
    """
    Main function to run all examples
    """
    print("Updated Function Retrieval System - Examples and Tests\n")
    print("=" * 80)
    
    # Run the main example with ChromaDB
    await example_with_chromadb()
    
    print("\n" + "=" * 80)
    
    # Run example without ChromaDB
    await example_without_chromadb()
    
    print("\n" + "=" * 80)
    
    # Demonstrate utility methods
    await demonstrate_utility_methods()
    
    print("\n" + "=" * 80)
    print("All examples completed successfully!")


if __name__ == "__main__":
    asyncio.run(main()) 
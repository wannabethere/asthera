#!/usr/bin/env python3
"""
Example script demonstrating how to use the FunctionRetrieval class
to identify the most relevant functions for user questions.
"""

import asyncio
import json
from typing import Optional
from unittest.mock import Mock

# Import the FunctionRetrieval class
from function_retrieval import FunctionRetrieval, FunctionRetrievalResult


async def example_usage():
    """
    Example usage of the FunctionRetrieval class
    """
    
    # Mock LLM for demonstration (replace with your actual LLM)
    mock_llm = Mock()
    
    # Create a realistic mock response
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
                "reasoning": "The user specifically asks for rolling variance analysis, which directly matches this function's purpose of calculating moving variance over time."
            },
            {
                "function_name": "moving_variance",
                "pipe_name": "MovingAggrPipe",
                "description": "Calculate moving variance and standard deviation for specified columns",
                "usage_description": "Measures volatility and variability over time. Useful for detecting changes in data variability, analyzing risk in financial data, and identifying periods of unusual activity in sensor data, financial transactions, or business metrics.",
                "relevance_score": 0.9,
                "reasoning": "This function provides moving variance calculations which are essential for the user's rolling variance analysis request."
            },
            {
                "function_name": "aggregate_by_time",
                "pipe_name": "TrendPipe",
                "description": "Aggregate data by time periods",
                "usage_description": "Groups and summarizes data by time periods (daily, weekly, monthly, etc.). Essential for trend analysis, reducing noise in time series data, and creating time-based summaries for analysis.",
                "relevance_score": 0.8,
                "reasoning": "The user wants to analyze variance over time, so time-based aggregation would be useful for grouping data by time periods."
            },
            {
                "function_name": "detect_statistical_outliers",
                "pipe_name": "AnomalyPipe",
                "description": "Detect outliers using statistical methods",
                "usage_description": "Identifies unusual values using statistical methods like z-score, IQR, and modified z-score. Essential for data quality control, fraud detection, and identifying unusual patterns in sensor data, financial transactions, or business metrics.",
                "relevance_score": 0.7,
                "reasoning": "Variance analysis often leads to outlier detection, so this function could be useful for identifying unusual variance patterns."
            },
            {
                "function_name": "calculate_moving_average",
                "pipe_name": "TrendPipe",
                "description": "Calculate moving averages for aggregated metrics",
                "usage_description": "Smooths time series data to identify underlying trends. Essential for trend analysis, reducing seasonal noise, and understanding long-term patterns in business metrics.",
                "relevance_score": 0.6,
                "reasoning": "Moving averages can complement variance analysis by providing trend context for the variance calculations."
            }
        ],
        "rephrased_question": "Calculate 5-day rolling variance of flux metric grouped by projects, cost centers, and departments over time",
        "confidence_score": 0.9,
        "reasoning": "The user's question clearly indicates a need for rolling variance analysis, which is well-supported by the MovingAggrPipe functions. The question is specific enough to identify relevant functions and can be further refined for function definition lookup.",
        "suggested_pipes": ["MovingAggrPipe", "TrendPipe", "AnomalyPipe"],
        "total_functions_analyzed": 150
    }
    '''
    mock_llm.ainvoke = Mock(return_value=mock_response)
    
    # Initialize the FunctionRetrieval system
    retrieval = FunctionRetrieval(llm=mock_llm)
    
    # Example user question
    question = "How does the 5-day rolling variance of flux change over time for each group of projects, cost centers, and departments?"
    
    # Dataframe context
    dataframe_description = "Financial metrics dataset with project performance data"
    dataframe_summary = "Contains 10,000 rows with daily metrics from 2023-2024, covering flux measurements across different organizational units"
    available_columns = ["flux", "timestamp", "projects", "cost_centers", "departments", "revenue", "employee_count"]
    
    print("=== Function Retrieval Example ===\n")
    print(f"User Question: {question}")
    print(f"Dataframe Description: {dataframe_description}")
    print(f"Available Columns: {available_columns}")
    print("\n" + "="*80 + "\n")
    
    # Retrieve relevant functions
    result = await retrieval.retrieve_relevant_functions(
        question=question,
        dataframe_description=dataframe_description,
        dataframe_summary=dataframe_summary,
        available_columns=available_columns
    )
    
    # Display results
    print("=== RETRIEVAL RESULTS ===\n")
    print(f"Rephrased Question: {result.rephrased_question}")
    print(f"Confidence Score: {result.confidence_score:.2f}")
    print(f"Overall Reasoning: {result.reasoning}")
    print(f"Suggested Pipes: {', '.join(result.suggested_pipes)}")
    print(f"Total Functions Analyzed: {result.total_functions_analyzed}")
    
    print(f"\n=== TOP {len(result.top_functions)} RELEVANT FUNCTIONS ===\n")
    
    for i, func in enumerate(result.top_functions, 1):
        print(f"{i}. {func.function_name} ({func.pipe_name})")
        print(f"   Relevance Score: {func.relevance_score:.2f}")
        print(f"   Description: {func.description}")
        print(f"   Usage: {func.usage_description[:100]}...")
        print(f"   Reasoning: {func.reasoning}")
        print()
    
    # Example of how to use the rephrased question for ChromaDB querying
    print("=== CHROMADB QUERY EXAMPLE ===\n")
    print("You can now use the rephrased question to query ChromaDB for function definitions:")
    print(f"Query: '{result.rephrased_question}'")
    print("\nThis rephrased question is optimized for semantic search in ChromaDB.")
    
    return result


async def test_different_questions():
    """
    Test the FunctionRetrieval with different types of questions
    """
    
    # Mock LLM responses for different scenarios
    mock_responses = {
        "variance": '''
        {
            "top_functions": [
                {
                    "function_name": "variance_analysis",
                    "pipe_name": "MovingAggrPipe",
                    "description": "Calculate moving variance and standard deviation",
                    "usage_description": "Measures volatility and variability over time",
                    "relevance_score": 0.95,
                    "reasoning": "Direct match for variance analysis"
                }
            ],
            "rephrased_question": "Calculate variance analysis for time series data",
            "confidence_score": 0.9,
            "reasoning": "Clear variance analysis request",
            "suggested_pipes": ["MovingAggrPipe"],
            "total_functions_analyzed": 150
        }
        ''',
        "anomaly": '''
        {
            "top_functions": [
                {
                    "function_name": "detect_statistical_outliers",
                    "pipe_name": "AnomalyPipe",
                    "description": "Detect outliers using statistical methods",
                    "usage_description": "Identifies unusual values using z-score, IQR methods",
                    "relevance_score": 0.95,
                    "reasoning": "Direct match for anomaly detection"
                }
            ],
            "rephrased_question": "Detect statistical outliers in the dataset",
            "confidence_score": 0.9,
            "reasoning": "Clear anomaly detection request",
            "suggested_pipes": ["AnomalyPipe"],
            "total_functions_analyzed": 150
        }
        ''',
        "cohort": '''
        {
            "top_functions": [
                {
                    "function_name": "calculate_retention",
                    "pipe_name": "CohortPipe",
                    "description": "Calculate retention metrics for cohorts",
                    "usage_description": "Measures how many users from each cohort return over time",
                    "relevance_score": 0.95,
                    "reasoning": "Direct match for retention analysis"
                }
            ],
            "rephrased_question": "Calculate user retention rates for different cohorts",
            "confidence_score": 0.9,
            "reasoning": "Clear cohort retention request",
            "suggested_pipes": ["CohortPipe"],
            "total_functions_analyzed": 150
        }
        '''
    }
    
    test_questions = [
        ("variance", "What is the variance of my data?"),
        ("anomaly", "Detect anomalies in my dataset"),
        ("cohort", "Show me user retention over time")
    ]
    
    print("=== TESTING DIFFERENT QUESTION TYPES ===\n")
    
    for scenario, question in test_questions:
        print(f"Question Type: {scenario.upper()}")
        print(f"Question: {question}")
        
        # Create mock LLM with specific response
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = mock_responses[scenario]
        mock_llm.ainvoke = Mock(return_value=mock_response)
        
        # Initialize retrieval
        retrieval = FunctionRetrieval(llm=mock_llm)
        
        # Get results
        result = await retrieval.retrieve_relevant_functions(
            question=question,
            dataframe_description="Sample dataset",
            dataframe_summary="Contains various metrics",
            available_columns=["value", "timestamp", "user_id"]
        )
        
        print(f"Rephrased: {result.rephrased_question}")
        print(f"Top Function: {result.top_functions[0].function_name if result.top_functions else 'None'}")
        print(f"Confidence: {result.confidence_score:.2f}")
        print("-" * 50)
    
    print("\n=== TESTING COMPLETED ===")


def demonstrate_utility_methods():
    """
    Demonstrate the utility methods of FunctionRetrieval
    """
    print("=== UTILITY METHODS DEMONSTRATION ===\n")
    
    # Create a FunctionRetrieval instance (without LLM for utility methods)
    retrieval = FunctionRetrieval(llm=None)
    
    # Get all available pipes
    pipes = retrieval.get_all_pipes()
    print(f"Available Pipes: {', '.join(pipes)}")
    
    # Get functions from a specific pipe
    if "MovingAggrPipe" in pipes:
        functions = retrieval.get_pipe_functions("MovingAggrPipe")
        print(f"\nMovingAggrPipe Functions: {', '.join(functions[:5])}...")
    
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
    print("Function Retrieval System - Examples and Tests\n")
    print("=" * 80)
    
    # Run the main example
    await example_usage()
    
    print("\n" + "=" * 80)
    
    # Test different question types
    await test_different_questions()
    
    print("\n" + "=" * 80)
    
    # Demonstrate utility methods
    demonstrate_utility_methods()
    
    print("\n" + "=" * 80)
    print("All examples completed successfully!")


if __name__ == "__main__":
    asyncio.run(main()) 
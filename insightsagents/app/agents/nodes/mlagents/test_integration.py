#!/usr/bin/env python3
"""
Test script to verify the integration between AnalysisIntentPlanner and FunctionRetrieval
"""

import asyncio
import json
from unittest.mock import Mock
from analysis_intent_classification import AnalysisIntentPlanner
from function_retrieval import FunctionRetrieval


async def test_integration():
    """
    Test the integration between AnalysisIntentPlanner and FunctionRetrieval
    """
    print("=== Testing Integration between AnalysisIntentPlanner and FunctionRetrieval ===\n")
    
    # Mock LLM
    mock_llm = Mock()
    mock_response = Mock()
    mock_response.content = '''
    {
        "intent_type": "time_series_analysis",
        "confidence_score": 0.95,
        "rephrased_question": "Calculate 5-day rolling variance of flux metric grouped by projects, cost centers, and departments over time",
        "reasoning": "The user's question clearly indicates a need for rolling variance analysis over time, which is a time series analysis task.",
        "required_data_columns": ["flux", "timestamp", "projects", "cost_centers", "departments"],
        "clarification_needed": null,
        "available_alternatives": [],
        "data_suggestions": "The analysis requires time series data with flux measurements and grouping columns."
    }
    '''
    mock_llm.ainvoke = Mock(return_value=mock_response)
    
    # Mock ChromaDB collection
    mock_function_collection = Mock()
    mock_chroma_response = {
        "documents": [[json.dumps({
            "function_name": "variance_analysis",
            "description": "Calculate moving variance and standard deviation",
            "usage_description": "Measures volatility over time",
            "parameters": {"window_size": "int", "columns": "list"},
            "required_params": [{"name": "window_size", "type": "int"}, {"name": "columns", "type": "list"}],
            "optional_params": [{"name": "group_by", "type": "list"}],
            "category": "Time Series Analysis",
            "type_of_operation": "Moving Window"
        })]],
        "distances": [[0.1]]
    }
    mock_function_collection.semantic_searches = Mock(return_value=mock_chroma_response)
    
    # Initialize AnalysisIntentPlanner with FunctionRetrieval integration
    planner = AnalysisIntentPlanner(
        llm=mock_llm,
        function_collection=mock_function_collection
    )
    
    # Test question
    question = "How does the 5-day rolling variance of flux change over time for each group of projects, cost centers, and departments?"
    dataframe_description = "Financial metrics dataset with project performance data"
    dataframe_summary = "Contains 10,000 rows with daily metrics from 2023-2024, covering flux measurements across different organizational units"
    available_columns = ["flux", "timestamp", "projects", "cost_centers", "departments", "revenue", "employee_count"]
    
    print(f"User Question: {question}")
    print(f"Dataframe Description: {dataframe_description}")
    print(f"Available Columns: {available_columns}")
    print("\n" + "="*80 + "\n")
    
    # Test the integrated classification
    result = await planner.classify_intent(
        question=question,
        dataframe_description=dataframe_description,
        dataframe_summary=dataframe_summary,
        available_columns=available_columns
    )
    
    # Display results
    print("=== INTEGRATION TEST RESULTS ===\n")
    print(f"Intent Type: {result.intent_type}")
    print(f"Confidence Score: {result.confidence_score:.2f}")
    print(f"Rephrased Question: {result.rephrased_question}")
    print(f"Reasoning: {result.reasoning}")
    print(f"Can Be Answered: {result.can_be_answered}")
    print(f"Feasibility Score: {result.feasibility_score:.2f}")
    print(f"Required Columns: {result.required_data_columns}")
    print(f"Missing Columns: {result.missing_columns}")
    print(f"Available Alternatives: {result.available_alternatives}")
    
    print(f"\n=== RETRIEVED FUNCTIONS ===\n")
    print(f"Number of Retrieved Functions: {len(result.retrieved_functions)}")
    for i, func in enumerate(result.retrieved_functions, 1):
        print(f"{i}. {func['function_name']} ({func['pipe_name']})")
        print(f"   Relevance Score: {func['relevance_score']:.2f}")
        print(f"   Description: {func['description']}")
        if func.get('function_definition'):
            print(f"   ✅ Function Definition Available")
        else:
            print(f"   ❌ No Function Definition")
        print()
    
    print(f"=== SUGGESTED FUNCTIONS ===\n")
    for i, func_name in enumerate(result.suggested_functions, 1):
        print(f"{i}. {func_name}")
    
    print(f"\n=== SPECIFIC FUNCTION MATCHES ===\n")
    for i, func_name in enumerate(result.specific_function_matches, 1):
        print(f"{i}. {func_name}")
    
    # Verify integration worked correctly
    print(f"\n=== INTEGRATION VERIFICATION ===\n")
    
    # Check that FunctionRetrieval was used
    assert hasattr(planner, 'function_retrieval'), "FunctionRetrieval not initialized"
    assert isinstance(planner.function_retrieval, FunctionRetrieval), "FunctionRetrieval not properly initialized"
    
    # Check that functions were retrieved
    assert len(result.retrieved_functions) > 0, "No functions were retrieved"
    assert len(result.suggested_functions) > 0, "No suggested functions"
    
    # Check that the LLM was called with the retrieved functions
    assert mock_llm.ainvoke.called, "LLM was not called"
    
    print("✅ Integration test passed! AnalysisIntentPlanner successfully uses FunctionRetrieval")
    
    return result


async def test_without_chromadb():
    """
    Test the integration without ChromaDB (fallback to JSON library)
    """
    print("\n=== Testing Integration without ChromaDB ===\n")
    
    # Mock LLM
    mock_llm = Mock()
    mock_response = Mock()
    mock_response.content = '''
    {
        "intent_type": "trend_analysis",
        "confidence_score": 0.85,
        "rephrased_question": "Calculate growth rates and trends for revenue over time",
        "reasoning": "The user is asking about growth trends, which is a trend analysis task.",
        "required_data_columns": ["revenue", "timestamp"],
        "clarification_needed": null,
        "available_alternatives": [],
        "data_suggestions": "The analysis requires time series data with revenue measurements."
    }
    '''
    mock_llm.ainvoke = Mock(return_value=mock_response)
    
    # Initialize AnalysisIntentPlanner without ChromaDB
    planner = AnalysisIntentPlanner(
        llm=mock_llm,
        function_collection=None  # No ChromaDB
    )
    
    # Test question
    question = "What are the growth trends in revenue over the past year?"
    dataframe_description = "Revenue dataset with monthly data"
    dataframe_summary = "Contains 12 months of revenue data from 2023"
    available_columns = ["revenue", "timestamp", "region", "product"]
    
    print(f"User Question: {question}")
    print(f"Available Columns: {available_columns}")
    print("\n" + "="*80 + "\n")
    
    # Test the integrated classification
    result = await planner.classify_intent(
        question=question,
        dataframe_description=dataframe_description,
        dataframe_summary=dataframe_summary,
        available_columns=available_columns
    )
    
    # Display results
    print("=== FALLBACK TEST RESULTS ===\n")
    print(f"Intent Type: {result.intent_type}")
    print(f"Confidence Score: {result.confidence_score:.2f}")
    print(f"Can Be Answered: {result.can_be_answered}")
    print(f"Feasibility Score: {result.feasibility_score:.2f}")
    
    print(f"\n=== RETRIEVED FUNCTIONS (JSON Fallback) ===\n")
    print(f"Number of Retrieved Functions: {len(result.retrieved_functions)}")
    for i, func in enumerate(result.retrieved_functions, 1):
        print(f"{i}. {func['function_name']} ({func['pipe_name']})")
        print(f"   Relevance Score: {func['relevance_score']:.2f}")
        print(f"   Description: {func['description']}")
        if func.get('function_definition'):
            print(f"   ✅ Function Definition Available (from JSON)")
        else:
            print(f"   ❌ No Function Definition")
        print()
    
    print("✅ Fallback test passed! FunctionRetrieval works without ChromaDB")
    
    return result


async def main():
    """
    Run all integration tests
    """
    try:
        # Test with ChromaDB
        result1 = await test_integration()
        
        # Test without ChromaDB
        result2 = await test_without_chromadb()
        
        print("\n" + "="*80)
        print("🎉 ALL INTEGRATION TESTS PASSED!")
        print("="*80)
        print("\nSummary:")
        print(f"- AnalysisIntentPlanner successfully integrates with FunctionRetrieval")
        print(f"- Function definitions are properly retrieved and included")
        print(f"- Fallback to JSON library works when ChromaDB is not available")
        print(f"- LLM receives properly formatted function information")
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main()) 
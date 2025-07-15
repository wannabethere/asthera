#!/usr/bin/env python3
"""
Test script for function definition retrieval in SelfCorrectingPipelineCodeGenerator
"""

import json
import asyncio
from typing import Dict, Any, List
from unittest.mock import Mock, AsyncMock

# Import the class we're testing
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.agents.nodes.mlagents.self_correcting_pipeline_generator import SelfCorrectingPipelineCodeGenerator

class MockDocumentChromaStore:
    """Mock DocumentChromaStore for testing"""
    
    def __init__(self, mock_data: Dict[str, List[Dict[str, Any]]]):
        self.mock_data = mock_data
    
    def semantic_searches(self, queries: List[str], n_results: int = 3) -> Dict[str, Any]:
        """Mock semantic search that returns predefined data"""
        results = {"documents": [[]], "distances": [[]]}
        
        for query in queries:
            query_results = []
            query_distances = []
            
            # Find matching data for the query
            for function_name, docs in self.mock_data.items():
                if function_name.lower() in query.lower() or query.lower() in function_name.lower():
                    for i, doc in enumerate(docs[:n_results]):
                        query_results.append(doc)
                        query_distances.append(0.1 + i * 0.1)  # Mock distances
            
            if query_results:
                results["documents"][0].extend(query_results)
                results["distances"][0].extend(query_distances)
        
        return results

def create_mock_function_definitions():
    """Create mock function definitions for testing"""
    return {
        "Mean": [
            {
                "name": "Mean",
                "description": "Calculate the arithmetic mean of a numeric column",
                "parameters": ["variable"],
                "returns": "DataFrame with mean value",
                "examples": ["Mean(variable='sales')", "Mean(variable='revenue')"],
                "pipeline_type": "MetricsPipe"
            }
        ],
        "Variance": [
            {
                "name": "Variance",
                "description": "Calculate the variance of a numeric column",
                "parameters": ["variable"],
                "returns": "DataFrame with variance value",
                "examples": ["Variance(variable='sales')"],
                "pipeline_type": "MetricsPipe"
            }
        ],
        "PercentChange": [
            {
                "name": "PercentChange",
                "description": "Calculate percent change compared to a baseline",
                "parameters": ["condition_column", "baseline"],
                "returns": "DataFrame with percent change values",
                "examples": ["PercentChange(condition_column='period', baseline='Q1')"],
                "pipeline_type": "OperationsPipe"
            }
        ],
        "detect_statistical_outliers": [
            {
                "name": "detect_statistical_outliers",
                "description": "Detect statistical outliers using z-score or IQR methods",
                "parameters": ["columns", "method", "threshold"],
                "returns": "DataFrame with outlier flags",
                "examples": ["detect_statistical_outliers(columns='value', method='zscore', threshold=3.0)"],
                "pipeline_type": "AnomalyPipe"
            }
        ]
    }

class MockLLM:
    """Mock LLM for testing"""
    
    def __init__(self):
        self.invoke_count = 0
    
    async def ainvoke(self, inputs: Dict[str, Any]) -> str:
        """Mock async invoke that returns predefined responses"""
        self.invoke_count += 1
        
        # Simulate different responses based on the input
        context = inputs.get("context", "").lower()
        function_names = inputs.get("suggested_functions", "")
        
        if "mean" in context and "Mean" in function_names:
            return json.dumps({
                "selected_function": "Mean",
                "confidence": 0.95,
                "reasoning": "Mean is the most appropriate function for calculating average values",
                "alternative_functions": ["Sum", "Count"]
            })
        elif "variance" in context and "Variance" in function_names:
            return json.dumps({
                "selected_function": "Variance",
                "confidence": 0.90,
                "reasoning": "Variance is the most appropriate function for measuring spread",
                "alternative_functions": ["StandardDeviation"]
            })
        elif "percent change" in context and "PercentChange" in function_names:
            return json.dumps({
                "selected_function": "PercentChange",
                "confidence": 0.88,
                "reasoning": "PercentChange is the most appropriate function for comparing changes",
                "alternative_functions": ["AbsoluteChange"]
            })
        else:
            # Default response
            return json.dumps({
                "selected_function": "Mean",
                "confidence": 0.7,
                "reasoning": "Default selection based on available functions",
                "alternative_functions": []
            })

async def test_function_definition_retrieval():
    """Test the function definition retrieval functionality"""
    
    print("Testing Function Definition Retrieval")
    print("=" * 60)
    
    # Create mock data
    mock_function_definitions = create_mock_function_definitions()
    
    # Create mock stores
    mock_function_store = MockDocumentChromaStore(mock_function_definitions)
    mock_usage_store = MockDocumentChromaStore({})
    mock_code_store = MockDocumentChromaStore({})
    
    # Create mock LLM
    mock_llm = MockLLM()
    
    # Create the generator instance
    generator = SelfCorrectingPipelineCodeGenerator(
        llm=mock_llm,
        usage_examples_store=mock_usage_store,
        code_examples_store=mock_code_store,
        function_definition_store=mock_function_store
    )
    
    # Test cases
    test_cases = [
        {
            "name": "Mean function selection",
            "context": "Calculate the mean of sales data",
            "suggested_functions": ["Mean", "Sum", "Count"],
            "expected_function": "Mean",
            "expected_confidence": 0.9
        },
        {
            "name": "Variance function selection",
            "context": "Calculate the variance of revenue",
            "suggested_functions": ["Variance", "StandardDeviation", "Mean"],
            "expected_function": "Variance",
            "expected_confidence": 0.8
        },
        {
            "name": "PercentChange function selection",
            "context": "Calculate percent change in sales compared to baseline",
            "suggested_functions": ["PercentChange", "AbsoluteChange", "Mean"],
            "expected_function": "PercentChange",
            "expected_confidence": 0.8
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test_case['name']}")
        print(f"Context: {test_case['context']}")
        print(f"Suggested Functions: {test_case['suggested_functions']}")
        
        try:
            # Test function definition retrieval
            function_definitions = await generator._retrieve_function_definitions(
                test_case['suggested_functions']
            )
            
            print(f"Retrieved Function Definitions:")
            print(function_definitions)
            
            # Test function selection with definitions
            result = await generator._detect_best_function(
                context=test_case['context'],
                suggested_functions=test_case['suggested_functions'],
                classification=None,
                dataset_description=None,
                columns_description=None
            )
            
            print(f"\nFunction Selection Result:")
            print(f"  Selected Function: {result.get('selected_function', 'N/A')}")
            print(f"  Confidence: {result.get('confidence', 0.0):.2f}")
            print(f"  Reasoning: {result.get('reasoning', 'N/A')}")
            print(f"  Alternative Functions: {result.get('alternative_functions', [])}")
            
            # Validate results
            selected_function = result.get('selected_function', '')
            confidence = result.get('confidence', 0.0)
            
            if selected_function == test_case['expected_function']:
                print(f"  ✅ PASS: Expected function '{test_case['expected_function']}', got '{selected_function}'")
            else:
                print(f"  ❌ FAIL: Expected function '{test_case['expected_function']}', got '{selected_function}'")
            
            if confidence >= test_case['expected_confidence']:
                print(f"  ✅ PASS: Confidence {confidence:.2f} >= {test_case['expected_confidence']:.2f}")
            else:
                print(f"  ❌ FAIL: Confidence {confidence:.2f} < {test_case['expected_confidence']:.2f}")
            
        except Exception as e:
            print(f"  ❌ ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
    
    print(f"\nTotal LLM invocations: {mock_llm.invoke_count}")
    print("\n" + "=" * 60)
    print("Test completed!")

async def test_function_input_detection_with_definitions():
    """Test function input detection with function definitions"""
    
    print("\nTesting Function Input Detection with Definitions")
    print("=" * 60)
    
    # Create mock data
    mock_function_definitions = create_mock_function_definitions()
    
    # Create mock stores
    mock_function_store = MockDocumentChromaStore(mock_function_definitions)
    mock_usage_store = MockDocumentChromaStore({})
    mock_code_store = MockDocumentChromaStore({})
    
    # Create mock LLM
    mock_llm = MockLLM()
    
    # Create the generator instance
    generator = SelfCorrectingPipelineCodeGenerator(
        llm=mock_llm,
        usage_examples_store=mock_usage_store,
        code_examples_store=mock_code_store,
        function_definition_store=mock_function_store
    )
    
    # Test cases for function input detection
    test_cases = [
        {
            "name": "Mean function inputs",
            "context": "Calculate the mean of sales column",
            "function_name": "Mean",
            "expected_inputs": {"variable": "sales"}
        },
        {
            "name": "PercentChange function inputs",
            "context": "Calculate percent change in revenue compared to Q1 baseline",
            "function_name": "PercentChange",
            "expected_inputs": {"condition_column": "quarter", "baseline": "Q1"}
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test_case['name']}")
        print(f"Context: {test_case['context']}")
        print(f"Function: {test_case['function_name']}")
        
        try:
            # Test function input detection with definitions
            result = await generator._detect_function_inputs(
                context=test_case['context'],
                function_name=test_case['function_name'],
                classification=None,
                dataset_description=None,
                columns_description=None
            )
            
            print(f"Detected Inputs:")
            print(f"  Primary Function Inputs: {result.get('primary_function_inputs', {})}")
            print(f"  Additional Computations: {len(result.get('additional_computations', []))}")
            print(f"  Pipeline Sequence: {result.get('pipeline_sequence', [])}")
            print(f"  Reasoning: {result.get('reasoning', 'N/A')}")
            
            # Basic validation
            primary_inputs = result.get('primary_function_inputs', {})
            if primary_inputs:
                print(f"  ✅ PASS: Function inputs detected successfully")
            else:
                print(f"  ⚠️  WARNING: No function inputs detected")
            
        except Exception as e:
            print(f"  ❌ ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("Function Input Detection Test completed!")

async def main():
    """Run all tests"""
    await test_function_definition_retrieval()
    await test_function_input_detection_with_definitions()

if __name__ == "__main__":
    asyncio.run(main()) 
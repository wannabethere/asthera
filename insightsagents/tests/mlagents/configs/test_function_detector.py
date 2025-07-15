#!/usr/bin/env python3
"""
Test script for the function detector in SelfCorrectingPipelineCodeGenerator
"""

import asyncio
import json
from typing import List, Dict, Any
from unittest.mock import Mock, AsyncMock

# Mock the LLM for testing
class MockLLM:
    def __init__(self):
        self.responses = {
            "function_detection": {
                "selected_function": "Mean",
                "confidence": 0.95,
                "reasoning": "Mean is the most appropriate function for calculating average values",
                "alternative_functions": ["Sum", "Count"]
            },
            "function_inputs": {
                "primary_function_inputs": {"variable": "sales"},
                "additional_computations": [],
                "pipeline_sequence": ["Calculate mean of sales"],
                "reasoning": "Direct mean calculation using metrics_tools Mean function"
            }
        }
    
    async def ainvoke(self, inputs: Dict[str, Any]) -> str:
        """Mock LLM response"""
        # Determine which type of request this is based on the inputs
        if "suggested_functions" in inputs:
            # Function detection request
            return json.dumps(self.responses["function_detection"])
        else:
            # Function inputs detection request
            return json.dumps(self.responses["function_inputs"])

# Mock the document stores
class MockDocumentStore:
    def semantic_searches(self, queries: List[str], n_results: int = 5) -> Dict[str, Any]:
        return {
            "documents": [["Mock document content"]],
            "distances": [[0.1]]
        }

async def test_function_detector():
    """Test the function detector with a list of suggested functions"""
    
    # Import the class (you'll need to adjust the import path based on your project structure)
    try:
        from app.agents.nodes.mlagents.self_correcting_pipeline_generator import SelfCorrectingPipelineCodeGenerator
    except ImportError:
        print("Could not import SelfCorrectingPipelineCodeGenerator. Please check the import path.")
        return
    
    # Create mock instances
    mock_llm = MockLLM()
    mock_usage_store = MockDocumentStore()
    mock_code_store = MockDocumentStore()
    mock_function_store = MockDocumentStore()
    
    # Create the generator instance
    generator = SelfCorrectingPipelineCodeGenerator(
        llm=mock_llm,
        usage_examples_store=mock_usage_store,
        code_examples_store=mock_code_store,
        function_definition_store=mock_function_store
    )
    
    # Test case 1: List of suggested functions
    print("=== Test Case 1: List of Suggested Functions ===")
    context = "Calculate the average sales value"
    suggested_functions = ["Mean", "Sum", "Count", "Median"]
    function_inputs = {}
    
    try:
        result = await generator.generate_pipeline_code(
            context=context,
            function_name=suggested_functions,  # List of functions
            function_inputs=function_inputs,
            dataframe_name="df"
        )
        
        print("Result:")
        print(json.dumps(result, indent=2))
        
        # Verify function detection metadata
        if "function_detection_metadata" in result:
            metadata = result["function_detection_metadata"]
            print(f"\nSelected function: {metadata.get('selected_function')}")
            print(f"Confidence: {metadata.get('confidence')}")
            print(f"Reasoning: {metadata.get('reasoning')}")
            print(f"Alternative functions: {metadata.get('alternative_functions')}")
        
    except Exception as e:
        print(f"Error in test case 1: {e}")
    
    # Test case 2: Single function (existing behavior)
    print("\n=== Test Case 2: Single Function ===")
    context = "Calculate the sum of revenue"
    single_function = "Sum"
    function_inputs = {"variable": "revenue"}
    
    try:
        result = await generator.generate_pipeline_code(
            context=context,
            function_name=single_function,  # Single function
            function_inputs=function_inputs,
            dataframe_name="df"
        )
        
        print("Result:")
        print(json.dumps(result, indent=2))
        
        # Verify function detection metadata
        if "function_detection_metadata" in result:
            metadata = result["function_detection_metadata"]
            print(f"\nSelected function: {metadata.get('selected_function')}")
            print(f"Confidence: {metadata.get('confidence')}")
            print(f"Reasoning: {metadata.get('reasoning')}")
        
    except Exception as e:
        print(f"Error in test case 2: {e}")

if __name__ == "__main__":
    asyncio.run(test_function_detector()) 
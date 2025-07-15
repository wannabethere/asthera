#!/usr/bin/env python3
"""
Example usage of the enhanced SelfCorrectingPipelineCodeGenerator with function detection
"""

import asyncio
import json
from typing import List, Dict, Any

# Example usage scenarios
async def example_usage():
    """
    Example usage of the SelfCorrectingPipelineCodeGenerator with function detection
    """
    
    print("=== Enhanced SelfCorrectingPipelineCodeGenerator Example ===\n")
    
    # Example 1: Using a list of suggested functions
    print("Example 1: List of Suggested Functions")
    print("Context: 'Calculate the average sales value'")
    print("Suggested Functions: ['Mean', 'Sum', 'Count', 'Median']")
    print("Expected: Function detector will select 'Mean' as the best function\n")
    
    # Example 2: Using a single function (existing behavior)
    print("Example 2: Single Function")
    print("Context: 'Calculate the sum of revenue'")
    print("Function: 'Sum'")
    print("Expected: Direct use of the provided function\n")
    
    # Example 3: Complex analysis with multiple suggested functions
    print("Example 3: Complex Analysis")
    print("Context: 'Analyze customer retention patterns over time'")
    print("Suggested Functions: ['calculate_retention', 'form_time_cohorts', 'variance_analysis', 'Mean']")
    print("Expected: Function detector will select the most appropriate function based on context\n")
    
    # Example 4: Risk analysis with suggested functions
    print("Example 4: Risk Analysis")
    print("Context: 'Calculate the Value at Risk for portfolio returns'")
    print("Suggested Functions: ['calculate_var', 'calculate_cvar', 'Variance', 'StandardDeviation']")
    print("Expected: Function detector will select 'calculate_var' for VaR calculation\n")

def show_code_example():
    """
    Show code example of how to use the enhanced generator
    """
    
    print("=== Code Example ===\n")
    
    code_example = '''
# Import the generator
from app.agents.nodes.mlagents.self_correcting_pipeline_generator import SelfCorrectingPipelineCodeGenerator

# Initialize the generator with your LLM and document stores
generator = SelfCorrectingPipelineCodeGenerator(
    llm=your_llm_instance,
    usage_examples_store=your_usage_store,
    code_examples_store=your_code_store,
    function_definition_store=your_function_store
)

# Example 1: Using a list of suggested functions
context = "Calculate the average sales value"
suggested_functions = ["Mean", "Sum", "Count", "Median"]
function_inputs = {}

result = await generator.generate_pipeline_code(
    context=context,
    function_name=suggested_functions,  # List of functions
    function_inputs=function_inputs,
    dataframe_name="df"
)

# Access the function detection metadata
function_metadata = result["function_detection_metadata"]
print(f"Selected function: {function_metadata['selected_function']}")
print(f"Confidence: {function_metadata['confidence']}")
print(f"Reasoning: {function_metadata['reasoning']}")
print(f"Alternative functions: {function_metadata['alternative_functions']}")

# Example 2: Using a single function (existing behavior)
context = "Calculate the sum of revenue"
single_function = "Sum"
function_inputs = {"variable": "revenue"}

result = await generator.generate_pipeline_code(
    context=context,
    function_name=single_function,  # Single function
    function_inputs=function_inputs,
    dataframe_name="df"
)

# The function detection metadata will show it was a direct selection
function_metadata = result["function_detection_metadata"]
print(f"Selected function: {function_metadata['selected_function']}")
print(f"Confidence: {function_metadata['confidence']}")  # Should be 1.0
'''
    
    print(code_example)

def show_return_structure():
    """
    Show the structure of the returned result
    """
    
    print("=== Return Structure ===\n")
    
    return_structure = {
        "status": "success",
        "generated_code": "result = (MetricsPipe.from_dataframe(df) | Mean(variable='sales') | ShowDataFrame())",
        "iterations": 1,
        "attempts": ["result = (MetricsPipe.from_dataframe(df) | Mean(variable='sales') | ShowDataFrame())"],
        "reasoning": [],
        "function_name": "Mean",
        "pipeline_type": "MetricsPipe",
        "detected_inputs": {
            "primary_function_inputs": {"variable": "sales"},
            "additional_computations": [],
            "pipeline_sequence": ["Calculate mean of sales"],
            "reasoning": "Direct mean calculation using metrics_tools Mean function"
        },
        "enhanced_function_inputs": {"variable": "sales"},
        "function_detection_metadata": {
            "selected_function": "Mean",
            "confidence": 0.95,
            "reasoning": "Mean is the most appropriate function for calculating average values",
            "alternative_functions": ["Sum", "Count"]
        },
        "classification": None,
        "dataset_description": None,
        "columns_description": None,
        "enhanced_context": "Calculate the average sales value"
    }
    
    print("The enhanced generator now returns a result with 'function_detection_metadata':")
    print(json.dumps(return_structure, indent=2))

if __name__ == "__main__":
    # Show examples
    asyncio.run(example_usage())
    
    # Show code example
    show_code_example()
    
    # Show return structure
    show_return_structure() 
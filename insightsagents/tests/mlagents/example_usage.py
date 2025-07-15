#!/usr/bin/env python3
"""
Example usage of the updated SelfCorrectingPipelineCodeGenerator
with classification input for time series analysis.
"""

from typing import Dict, Any
from app.agents.nodes.mlagents.self_correcting_pipeline_generator import SelfCorrectingPipelineCodeGenerator

def main():
    # Example classification input (as provided by user)
    classification = {
        'intent_type': 'time_series_analysis',
        'confidence_score': 0.9,
        'rephrased_question': 'What is the 5-day rolling variance of flux over time for each project, cost center, and department?',
        'suggested_functions': ['variance_analysis', 'calculate_var'],
        'reasoning': 'The question specifically asks for rolling variance, matching the variance_analysis function. The available data supports this analysis.',
        'required_data_columns': ['Date', 'Project', 'Cost center', 'Department', 'Transactional value'],
        'clarification_needed': None,
        'retrieved_functions': [],
        'specific_function_matches': ['variance_analysis', 'calculate_var'],
        'can_be_answered': True,
        'feasibility_score': 0.8,
        'missing_columns': ['Department'],
        'available_alternatives': [],
        'data_suggestions': ''
    }
    
    # Example dataset description
    dataset_description = "Financial transaction data with project, cost center, and department information over time"
    
    # Example columns description
    columns_description = {
        'Date': 'Transaction date in YYYY-MM-DD format',
        'Project': 'Project identifier or name',
        'Cost center': 'Cost center code or name',
        'Transactional value': 'Monetary value of the transaction (flux)',
        'Department': 'Department name (may be missing in some records)'
    }
    
    # Example function inputs
    function_inputs = {
        'window': 5,
        'value_column': 'Transactional value',
        'group_by': ['Project', 'Cost center', 'Department'],
        'date_column': 'Date'
    }
    
    # Initialize the generator (you would need to provide actual stores and LLM)
    # generator = SelfCorrectingPipelineCodeGenerator(
    #     llm=your_llm_instance,
    #     usage_examples_store=your_usage_store,
    #     code_examples_store=your_code_store,
    #     function_definition_store=your_function_store
    # )
    
    # Example usage (commented out since we don't have the actual dependencies)
    """
    result = generator.generate_pipeline_code(
        context="Calculate 5-day rolling variance of transactional values",
        function_name="variance_analysis",
        function_inputs=function_inputs,
        dataframe_name="df",
        classification=classification,
        dataset_description=dataset_description,
        columns_description=columns_description
    )
    
    print("Generated Pipeline Code:")
    print(result["generated_code"])
    print("\nPipeline Type:", result["pipeline_type"])
    print("Iterations:", result["iterations"])
    print("Status:", result["status"])
    """
    
    # Print the expected structure
    print("Expected Classification Input Structure:")
    print("=" * 50)
    for key, value in classification.items():
        print(f"{key}: {value}")
    
    print("\nExpected Dataset Description:")
    print("=" * 50)
    print(dataset_description)
    
    print("\nExpected Columns Description:")
    print("=" * 50)
    for col, desc in columns_description.items():
        print(f"{col}: {desc}")
    
    print("\nExpected Function Inputs:")
    print("=" * 50)
    for key, value in function_inputs.items():
        print(f"{key}: {value}")
    
    print("\nExpected Output Structure:")
    print("=" * 50)
    expected_output = {
        "status": "success",
        "generated_code": "result = (TimeSeriesPipe.from_dataframe(df) | variance_analysis(window=5, value_column='Transactional value', group_by=['Project', 'Cost center', 'Department'], date_column='Date') | ShowDataFrame())",
        "iterations": 1,
        "attempts": ["generated_code_here"],
        "reasoning": [],
        "function_name": "variance_analysis",
        "pipeline_type": "TimeSeriesPipe",
        "classification": classification,
        "dataset_description": dataset_description,
        "columns_description": columns_description,
        "enhanced_context": "Enhanced context with classification info..."
    }
    
    for key, value in expected_output.items():
        if key == "generated_code":
            print(f"{key}:")
            print(f"  {value}")
        elif key == "enhanced_context":
            print(f"{key}: [Enhanced context with classification information]")
        else:
            print(f"{key}: {value}")

if __name__ == "__main__":
    main() 
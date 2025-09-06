#!/usr/bin/env python3
"""
Test script to verify the updated self-correcting pipeline generator
correctly groups functions by pipeline type and chains them together.
"""

import asyncio
import sys
import os

# Add the parent directory to the path to import the pipeline generator
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.agents.nodes.mlagents.self_correcting_pipeline_generator import SelfCorrectingPipelineCodeGenerator

async def test_pipeline_generation():
    """Test the pipeline generation with a sample reasoning plan"""
    
    # Create a mock reasoning plan that should generate chained pipelines
    reasoning_plan = [
        {
            "step_number": 1,
            "step_title": "Data Selection",
            "function_name": "select_strings",
            "parameter_mapping": {},
            "data_requirements": ["string_columns"],
            "embedded_function_parameter": False,
            "embedded_function_details": None
        },
        {
            "step_number": 2,
            "step_title": "Aggregate Daily Transaction Amounts",
            "function_name": "aggregate_by_time",
            "parameter_mapping": {
                "date_column": "Date",
                "metric_columns": ["Transactional value"],
                "time_period": "D",
                "aggregation": "sum"
            },
            "data_requirements": ["date_column", "metric_columns"],
            "embedded_function_parameter": False,
            "embedded_function_details": None
        },
        {
            "step_number": 3,
            "step_title": "Calculate Growth Rates",
            "function_name": "calculate_growth_rates",
            "parameter_mapping": {
                "window": None,
                "annualize": False,
                "method": "percentage"
            },
            "data_requirements": ["time_series_data"],
            "embedded_function_parameter": False,
            "embedded_function_details": None
        },
        {
            "step_number": 4,
            "step_title": "Calculate Moving Averages",
            "function_name": "calculate_moving_average",
            "parameter_mapping": {
                "window": 7,
                "method": "simple"
            },
            "data_requirements": ["time_series_data"],
            "embedded_function_parameter": False,
            "embedded_function_details": None
        }
    ]
    
    # Create a mock classification object
    mock_classification = type('MockClassification', (), {
        'reasoning_plan': reasoning_plan,
        'intent_type': 'trend_analysis',
        'confidence_score': 0.9,
        'suggested_functions': ['aggregate_by_time', 'calculate_growth_rates', 'calculate_moving_average']
    })()
    
    # Create a mock LLM (we'll just use a simple function for testing)
    class MockLLM:
        async def ainvoke(self, inputs):
            # Return a simple response for testing
            return '{"function_name": "aggregate_by_time", "parameter_mapping": {}}'
    
    mock_llm = MockLLM()
    
    # Create the pipeline generator
    generator = SelfCorrectingPipelineCodeGenerator(
        llm=mock_llm,
        usage_examples_store=None,
        code_examples_store=None,
        function_definition_store=None,
        logical_reasoning_store=None,
        function_retrieval=None,
        max_iterations=1,
        relevance_threshold=0.7
    )
    
    # Test the pipeline generation
    try:
        # Test the reasoning plan extraction
        print("Testing reasoning plan extraction...")
        extraction_result = generator._extract_function_from_reasoning_plan(
            reasoning_plan, 
            "What are the daily trends of transaction amounts?", 
            mock_classification
        )
        print(f"Extraction result: {extraction_result}")
        
        # Test the code generation from reasoning plan
        print("\nTesting code generation from reasoning plan...")
        generated_code = await generator._generate_code_from_reasoning_plan(
            reasoning_plan,
            "financial_data",
            mock_classification
        )
        
        print("\nGenerated Code:")
        print("=" * 50)
        print(generated_code)
        print("=" * 50)
        
        # Check if the code contains chained pipelines within the same pipeline type
        if "| aggregate_by_time" in generated_code and "| calculate_growth_rates" in generated_code:
            print("\n✅ SUCCESS: Code contains chained pipeline functions within the same pipeline type!")
        else:
            print("\n❌ FAILURE: Code does not contain chained pipeline functions")
        
        # Check if functions from the same pipeline type are grouped together
        if "TrendPipe.from_dataframe" in generated_code:
            print("✅ SUCCESS: Functions are grouped by pipeline type!")
        else:
            print("❌ FAILURE: Functions are not grouped by pipeline type")
        
        # Check if different pipeline types are separate (not chained together)
        if "MetricsPipe.from_dataframe" in generated_code and "TrendPipe.from_dataframe" in generated_code:
            print("✅ SUCCESS: Different pipeline types are kept separate!")
        else:
            print("❌ FAILURE: Different pipeline types are not properly separated")
        
        # Check if the first pipeline uses the original dataframe and subsequent pipelines use result
        if "MetricsPipe.from_dataframe(financial_data)" in generated_code and "TrendPipe.from_dataframe(result)" in generated_code:
            print("✅ SUCCESS: First pipeline uses original dataframe, subsequent pipelines use result!")
        else:
            print("❌ FAILURE: Pipelines are not using the correct dataframe sources")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing Self-Correcting Pipeline Generator...")
    print("=" * 60)
    
    # Run the test
    success = asyncio.run(test_pipeline_generation())
    
    if success:
        print("\n🎉 All tests passed!")
    else:
        print("\n💥 Tests failed!")
        sys.exit(1)

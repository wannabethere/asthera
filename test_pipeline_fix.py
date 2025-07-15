#!/usr/bin/env python3
"""
Test script to demonstrate the pipeline type consistency fix
"""

import sys
import os

# Add the genieml path to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'genieml'))

from insightsagents.app.agents.nodes.mlagents.self_correcting_pipeline_generator import (
    SelfCorrectingPipelineCodeGenerator, PipelineType
)

def test_pipeline_type_detection():
    """Test that pipeline types are correctly detected"""
    generator = SelfCorrectingPipelineCodeGenerator(
        llm=None,  # We don't need LLM for this test
        usage_examples_store=None,
        code_examples_store=None,
        function_definition_store=None
    )
    
    # Test cases
    test_cases = [
        ("variance_analysis", PipelineType.TIMESERIES),
        ("Variance", PipelineType.METRICS),
        ("Mean", PipelineType.METRICS),
        ("PercentChange", PipelineType.OPERATIONS),
        ("calculate_retention", PipelineType.COHORT),
        ("calculate_var", PipelineType.RISK),
        ("analyze_funnel", PipelineType.FUNNEL),
    ]
    
    print("Testing pipeline type detection:")
    for function_name, expected_type in test_cases:
        detected_type = generator._detect_pipeline_type(function_name, "")
        status = "✓" if detected_type == expected_type else "✗"
        print(f"  {status} {function_name} -> {detected_type.value} (expected: {expected_type.value})")

def test_additional_computations_filtering():
    """Test that additional computations are filtered correctly"""
    generator = SelfCorrectingPipelineCodeGenerator(
        llm=None,
        usage_examples_store=None,
        code_examples_store=None,
        function_definition_store=None
    )
    
    # Test case: variance_analysis (TimeSeriesPipe) with Variance (MetricsPipe)
    detected_inputs = {
        "primary_function_inputs": {"columns": ["Transactional value"]},
        "additional_computations": [
            {
                "function": "Variance",
                "inputs": {"variable": "5-day rolling transactional value"},
                "tool": "metrics_tools"
            }
        ],
        "pipeline_sequence": ["variance_analysis", "Variance"],
        "reasoning": "Test case"
    }
    
    filtered_inputs = generator._filter_additional_computations(detected_inputs, "variance_analysis")
    
    print("\nTesting additional computations filtering:")
    print(f"  Original additional_computations: {len(detected_inputs['additional_computations'])}")
    print(f"  Filtered additional_computations: {len(filtered_inputs['additional_computations'])}")
    print(f"  Should be filtered out: {len(filtered_inputs['additional_computations']) == 0}")

def test_pipeline_type_mixing_detection():
    """Test that pipeline type mixing is detected correctly"""
    generator = SelfCorrectingPipelineCodeGenerator(
        llm=None,
        usage_examples_store=None,
        code_examples_store=None,
        function_definition_store=None
    )
    
    # Test case: TimeSeriesPipe with MetricsPipe function
    problematic_code = """
    result = (
        TimeSeriesPipe.from_dataframe("Purchase Orders Data")
        | variance_analysis(
            columns=['Transactional value'],
            method='rolling',
            window=5
        )
        | Variance(variable='5-day rolling transactional value')
        | ShowDataFrame()
    )
    """
    
    mixing_detected = generator._check_pipeline_type_mixing(problematic_code, PipelineType.TIMESERIES)
    
    print("\nTesting pipeline type mixing detection:")
    print(f"  Mixing detected: {mixing_detected is not None}")
    if mixing_detected:
        print(f"  Error: {mixing_detected}")

def test_correct_pipeline_generation():
    """Test that correct pipeline code would be generated"""
    print("\nExpected correct pipeline code for variance_analysis:")
    print("""
    result = (
        TimeSeriesPipe.from_dataframe("Purchase Orders Data")
        | variance_analysis(
            columns=['Transactional value'],
            method='rolling',
            window=5,
            time_column='Date',
            group_columns=['Project', 'Event Type'],
            suffix='_rolling'
        )
        | ShowDataFrame()
    )
    """)
    
    print("\nExpected correct pipeline code for Variance (MetricsPipe):")
    print("""
    result = (
        MetricsPipe.from_dataframe("Purchase Orders Data")
        | Variance(variable='Transactional value')
        | ShowDataFrame()
    )
    """)

if __name__ == "__main__":
    print("Testing Pipeline Type Consistency Fix")
    print("=" * 50)
    
    test_pipeline_type_detection()
    test_additional_computations_filtering()
    test_pipeline_type_mixing_detection()
    test_correct_pipeline_generation()
    
    print("\n" + "=" * 50)
    print("Test completed!") 
#!/usr/bin/env python3
"""
Test script to demonstrate the multi-pipeline approach
"""

import sys
import os

# Add the genieml path to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'genieml'))

from insightsagents.app.agents.nodes.mlagents.self_correcting_pipeline_generator import (
    SelfCorrectingPipelineCodeGenerator, PipelineType
)

def test_multi_pipeline_detection():
    """Test that multi-pipeline scenarios are correctly detected"""
    generator = SelfCorrectingPipelineCodeGenerator(
        llm=None,  # We don't need LLM for this test
        usage_examples_store=None,
        code_examples_store=None,
        function_definition_store=None
    )
    
    # Test case: variance_analysis (TimeSeriesPipe) with Mean (MetricsPipe)
    detected_inputs = {
        "primary_function_inputs": {"columns": ["mean_Transactional value"], "method": "rolling", "window": 5},
        "additional_computations": [
            {
                "function": "Mean",
                "inputs": {"variable": "Transactional value"},
                "tool": "metrics_tools"
            }
        ],
        "pipeline_sequence": ["Calculate mean of transactional value", "Analyze variance over time"],
        "reasoning": "Test case"
    }
    
    filtered_inputs = generator._filter_additional_computations(detected_inputs, "variance_analysis")
    
    print("Testing multi-pipeline detection:")
    print(f"  Multi-pipeline: {filtered_inputs.get('multi_pipeline', False)}")
    print(f"  First pipeline type: {filtered_inputs.get('first_pipeline_type')}")
    print(f"  Second pipeline type: {filtered_inputs.get('second_pipeline_type')}")
    print(f"  Additional computations: {len(filtered_inputs.get('additional_computations', []))}")

def test_multi_pipeline_validation():
    """Test that multi-pipeline code is correctly validated"""
    generator = SelfCorrectingPipelineCodeGenerator(
        llm=None,
        usage_examples_store=None,
        code_examples_store=None,
        function_definition_store=None
    )
    
    # Test case: Proper multi-pipeline code
    proper_multi_pipeline_code = """
    result = (
        MetricsPipe.from_dataframe("Purchase Orders Data")
        | Mean(variable='Transactional value')
        | TimeSeriesPipe.from_dataframe()
        | variance_analysis(
            columns=['mean_Transactional value'],
            method='rolling',
            window=5
        )
        | ShowDataFrame()
    )
    """
    
    # Test case: Improper mixing (should be detected as error)
    improper_mixing_code = """
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
    
    print("\nTesting multi-pipeline validation:")
    
    # Test proper multi-pipeline
    mixing_detected = generator._check_pipeline_type_mixing(proper_multi_pipeline_code, PipelineType.TIMESERIES)
    print(f"  Proper multi-pipeline - mixing detected: {mixing_detected is not None}")
    
    # Test improper mixing
    mixing_detected = generator._check_pipeline_type_mixing(improper_mixing_code, PipelineType.TIMESERIES)
    print(f"  Improper mixing - mixing detected: {mixing_detected is not None}")
    if mixing_detected:
        print(f"  Error: {mixing_detected}")

def show_correct_pipeline_examples():
    """Show examples of correct pipeline generation"""
    print("\nCorrect Pipeline Examples:")
    print("=" * 50)
    
    print("\n1. Single Pipeline (MetricsPipe):")
    print("""
    result = (
        MetricsPipe.from_dataframe("Purchase Orders Data")
        | Mean(variable='Transactional value')
        | Variance(variable='Transactional value')
        | ShowDataFrame()
    )
    """)
    
    print("\n2. Multi-Pipeline (MetricsPipe -> TimeSeriesPipe):")
    print("""
    result = (
        MetricsPipe.from_dataframe("Purchase Orders Data")
        | Mean(variable='Transactional value')
        | TimeSeriesPipe.from_dataframe()
        | variance_analysis(
            columns=['mean_Transactional value'],
            method='rolling',
            window=5,
            time_column='Date',
            group_columns=['Project', 'Event Type'],
            suffix='_rolling'
        )
        | ShowDataFrame()
    )
    """)
    
    print("\n3. Multi-Pipeline (OperationsPipe -> TimeSeriesPipe):")
    print("""
    result = (
        OperationsPipe.from_dataframe("Purchase Orders Data")
        | PercentChange(condition_column='period', baseline='Q1')
        | TimeSeriesPipe.from_dataframe()
        | variance_analysis(
            columns=['percent_change'],
            method='rolling',
            window=5
        )
        | ShowDataFrame()
    )
    """)
    
    print("\n4. Single Pipeline (TimeSeriesPipe only):")
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

def show_incorrect_examples():
    """Show examples of incorrect pipeline generation"""
    print("\nIncorrect Pipeline Examples (What NOT to do):")
    print("=" * 50)
    
    print("\n1. Mixing TimeSeriesPipe with MetricsPipe functions:")
    print("""
    # WRONG - This will cause 'Variance does not exist' error
    result = (
        TimeSeriesPipe.from_dataframe("Purchase Orders Data")
        | variance_analysis(
            columns=['Transactional value'],
            method='rolling',
            window=5
        )
        | Variance(variable='5-day rolling transactional value')  # WRONG!
        | ShowDataFrame()
    )
    """)
    
    print("\n2. Mixing MetricsPipe with OperationsPipe functions:")
    print("""
    # WRONG - This will cause errors
    result = (
        MetricsPipe.from_dataframe("Purchase Orders Data")
        | Mean(variable='Transactional value')
        | PercentChange(condition_column='period', baseline='Q1')  # WRONG!
        | ShowDataFrame()
    )
    """)

if __name__ == "__main__":
    print("Testing Multi-Pipeline Approach")
    print("=" * 50)
    
    test_multi_pipeline_detection()
    test_multi_pipeline_validation()
    show_correct_pipeline_examples()
    show_incorrect_examples()
    
    print("\n" + "=" * 50)
    print("Test completed!")
    print("\nKey Points:")
    print("1. MetricsPipe and OperationsPipe should be executed FIRST")
    print("2. TimeSeriesPipe, CohortPipe, RiskPipe, FunnelPipe should be executed SECOND")
    print("3. Use proper chaining: MetricsPipe.from_dataframe() | ... | TimeSeriesPipe.from_dataframe()")
    print("4. Never mix functions from different pipeline types in the same pipeline") 
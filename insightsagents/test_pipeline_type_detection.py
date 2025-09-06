#!/usr/bin/env python3
"""
Test script to verify pipeline type detection for moving_apply_by_group
"""

import asyncio
import sys
import os
import json

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.agents.nodes.mlagents.self_correcting_pipeline_generator import (
    SelfCorrectingPipelineCodeGenerator,
    PipelineType
)
from app.agents.retrieval.retrieval_helper import RetrievalHelper


async def test_pipeline_type_detection():
    """Test that moving_apply_by_group is correctly detected as MovingAggrPipe"""
    
    # Create a mock LLM
    class MockLLM:
        async def ainvoke(self, inputs):
            return "MovingAggrPipe"  # Mock response
    
    # Create pipeline generator
    pipeline_generator = SelfCorrectingPipelineCodeGenerator(
        llm=MockLLM(),
        usage_examples_store=None,
        code_examples_store=None,
        function_definition_store=None,
        function_retrieval=None
    )
    
    # Test pipeline type detection for moving_apply_by_group
    function_name = "moving_apply_by_group"
    context = "Calculate moving variance analysis for flux data"
    
    print(f"Testing pipeline type detection for: {function_name}")
    
    # Test the detection
    pipeline_type = await pipeline_generator._detect_pipeline_type(
        function_name, context, None
    )
    
    print(f"Detected pipeline type: {pipeline_type}")
    print(f"Expected pipeline type: {PipelineType.MOVINGAGGR}")
    
    if pipeline_type == PipelineType.MOVINGAGGR:
        print("✅ SUCCESS: moving_apply_by_group correctly detected as MovingAggrPipe")
    else:
        print(f"❌ FAILURE: Expected MovingAggrPipe, but got {pipeline_type}")
    
    # Test with function definitions from JSON
    print("\nTesting with function definitions from JSON...")
    
    # Load function definitions
    with open("data/meta/all_pipes_functions.json", "r") as f:
        function_definitions = json.load(f)
    
    # Check if moving_apply_by_group is in MovingAggrPipe
    moving_aggr_functions = function_definitions.get("MovingAggrPipe", {}).get("functions", {})
    
    if "moving_apply_by_group" in moving_aggr_functions:
        print("✅ SUCCESS: moving_apply_by_group found in MovingAggrPipe functions")
        print(f"Description: {moving_aggr_functions['moving_apply_by_group']['description']}")
    else:
        print("❌ FAILURE: moving_apply_by_group not found in MovingAggrPipe functions")
    
    # Check if it's incorrectly in TimeSeriesPipe
    timeseries_functions = function_definitions.get("TimeSeriesPipe", {}).get("functions", {})
    
    if "moving_apply_by_group" in timeseries_functions:
        print("❌ FAILURE: moving_apply_by_group incorrectly found in TimeSeriesPipe functions")
    else:
        print("✅ SUCCESS: moving_apply_by_group correctly NOT found in TimeSeriesPipe functions")
    
    # Test the map_pipe_name_to_pipeline_type method
    print("\nTesting map_pipe_name_to_pipeline_type...")
    
    # Test with MovingAggrPipe
    result = pipeline_generator._map_pipe_name_to_pipeline_type("MovingAggrPipe")
    print(f"MovingAggrPipe -> {result}")
    
    if result == PipelineType.MOVINGAGGR:
        print("✅ SUCCESS: MovingAggrPipe correctly mapped")
    else:
        print(f"❌ FAILURE: Expected MovingAggrPipe, but got {result}")
    
    # Test with TimeSeriesPipe
    result = pipeline_generator._map_pipe_name_to_pipeline_type("TimeSeriesPipe")
    print(f"TimeSeriesPipe -> {result}")
    
    if result == PipelineType.TIMESERIES:
        print("✅ SUCCESS: TimeSeriesPipe correctly mapped")
    else:
        print(f"❌ FAILURE: Expected TimeSeriesPipe, but got {result}")


if __name__ == "__main__":
    asyncio.run(test_pipeline_type_detection())

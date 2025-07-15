#!/usr/bin/env python3
"""
Test script to demonstrate the async pipeline generation functionality
"""

import asyncio
import sys
import os
import time

# Add the genieml path to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'genieml'))

from insightsagents.app.agents.nodes.mlagents.self_correcting_pipeline_generator import (
    SelfCorrectingPipelineCodeGenerator, PipelineType
)

# Mock LLM for testing
class MockLLM:
    """Mock LLM for testing async functionality"""
    
    async def ainvoke(self, inputs):
        """Simulate async LLM call with delay"""
        await asyncio.sleep(0.1)  # Simulate network delay
        
        # Return mock responses based on the input
        if "detect" in str(inputs):
            return '''{
                "primary_function_inputs": {"columns": ["Transactional value"], "method": "rolling", "window": 5},
                "additional_computations": [
                    {
                        "function": "Mean",
                        "inputs": {"variable": "Transactional value"},
                        "tool": "metrics_tools"
                    }
                ],
                "pipeline_sequence": ["Calculate mean", "Analyze variance"],
                "multi_pipeline": true,
                "first_pipeline_type": "MetricsPipe",
                "second_pipeline_type": "TimeSeriesPipe",
                "reasoning": "Need to calculate mean first, then analyze variance"
            }'''
        elif "grade" in str(inputs):
            return "RELEVANT"
        elif "generate" in str(inputs):
            return '''
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
            '''
        else:
            return "Mock response"

async def test_async_pipeline_generation():
    """Test async pipeline generation"""
    print("Testing Async Pipeline Generation")
    print("=" * 50)
    
    # Create generator with mock LLM
    generator = SelfCorrectingPipelineCodeGenerator(
        llm=MockLLM(),
        usage_examples_store=None,
        code_examples_store=None,
        function_definition_store=None
    )
    
    # Test parameters
    context = "Calculate the mean of transactional value and then analyze its variance over time"
    function_name = "variance_analysis"
    function_inputs = {
        "columns": ["Transactional value"],
        "method": "rolling",
        "window": 5
    }
    dataframe_name = "Purchase Orders Data"
    
    print(f"Context: {context}")
    print(f"Function: {function_name}")
    print(f"Dataframe: {dataframe_name}")
    print()
    
    # Measure execution time
    start_time = time.time()
    
    try:
        # Generate pipeline code asynchronously
        result = await generator.generate_pipeline_code(
            context=context,
            function_name=function_name,
            function_inputs=function_inputs,
            dataframe_name=dataframe_name
        )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        print(f"✅ Pipeline generation completed in {execution_time:.2f} seconds")
        print(f"Status: {result.get('status', 'unknown')}")
        print(f"Iterations: {result.get('iterations', 0)}")
        print(f"Pipeline Type: {result.get('pipeline_type', 'unknown')}")
        print()
        
        if result.get('generated_code'):
            print("Generated Code:")
            print("-" * 30)
            print(result['generated_code'])
            print("-" * 30)
        else:
            print("❌ No code generated")
        
        if result.get('reasoning'):
            print(f"\nReasoning: {result['reasoning']}")
        
    except Exception as e:
        end_time = time.time()
        execution_time = end_time - start_time
        print(f"❌ Error after {execution_time:.2f} seconds: {str(e)}")

async def test_concurrent_pipeline_generation():
    """Test concurrent pipeline generation"""
    print("\nTesting Concurrent Pipeline Generation")
    print("=" * 50)
    
    # Create generator with mock LLM
    generator = SelfCorrectingPipelineCodeGenerator(
        llm=MockLLM(),
        usage_examples_store=None,
        code_examples_store=None,
        function_definition_store=None
    )
    
    # Test cases
    test_cases = [
        {
            "context": "Calculate mean and variance of sales",
            "function_name": "Mean",
            "function_inputs": {"variable": "sales"},
            "dataframe_name": "Sales Data"
        },
        {
            "context": "Analyze variance over time for revenue",
            "function_name": "variance_analysis",
            "function_inputs": {"columns": ["revenue"], "method": "rolling", "window": 7},
            "dataframe_name": "Revenue Data"
        },
        {
            "context": "Calculate percent change and absolute change",
            "function_name": "PercentChange",
            "function_inputs": {"condition_column": "period", "baseline": "Q1"},
            "dataframe_name": "Quarterly Data"
        }
    ]
    
    print(f"Running {len(test_cases)} concurrent pipeline generations...")
    
    # Measure execution time
    start_time = time.time()
    
    try:
        # Run all pipeline generations concurrently
        tasks = []
        for i, test_case in enumerate(test_cases):
            task = generator.generate_pipeline_code(
                context=test_case["context"],
                function_name=test_case["function_name"],
                function_inputs=test_case["function_inputs"],
                dataframe_name=test_case["dataframe_name"]
            )
            tasks.append((i, task))
        
        # Wait for all tasks to complete
        results = []
        for i, task in tasks:
            try:
                result = await task
                results.append((i, result))
                print(f"✅ Task {i+1} completed successfully")
            except Exception as e:
                print(f"❌ Task {i+1} failed: {str(e)}")
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        print(f"\n🎉 All tasks completed in {execution_time:.2f} seconds")
        print(f"Average time per task: {execution_time/len(test_cases):.2f} seconds")
        
        # Show results summary
        for i, result in results:
            print(f"Task {i+1}: {result.get('status', 'unknown')} - {result.get('pipeline_type', 'unknown')}")
        
    except Exception as e:
        end_time = time.time()
        execution_time = end_time - start_time
        print(f"❌ Error after {execution_time:.2f} seconds: {str(e)}")

def test_sync_vs_async_comparison():
    """Compare sync vs async performance"""
    print("\nSync vs Async Performance Comparison")
    print("=" * 50)
    
    print("Note: This is a theoretical comparison since we're using mock LLM")
    print("In real scenarios with actual LLM calls:")
    print("- Sync: Each LLM call blocks until completion")
    print("- Async: Multiple LLM calls can run concurrently")
    print("- Document retrieval: Currently sync (could be made async)")
    print("- Code generation: Async LLM calls for better performance")
    print()
    print("Benefits of async approach:")
    print("1. Non-blocking LLM calls")
    print("2. Better resource utilization")
    print("3. Improved responsiveness for web applications")
    print("4. Ability to handle multiple requests concurrently")
    print("5. Timeout handling and cancellation support")

async def main():
    """Main test function"""
    print("Async Pipeline Generator Test Suite")
    print("=" * 60)
    
    await test_async_pipeline_generation()
    await test_concurrent_pipeline_generation()
    test_sync_vs_async_comparison()
    
    print("\n" + "=" * 60)
    print("Test completed!")

if __name__ == "__main__":
    asyncio.run(main()) 
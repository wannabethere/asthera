#!/usr/bin/env python3
"""
Test script for function input detection using LLMs
"""

import json
from typing import Dict, Any, Optional
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers.string import StrOutputParser

def test_function_input_detection():
    """
    Test the function input detection logic
    """
    
    # Mock LLM for testing (you would replace this with your actual LLM)
    class MockLLM:
        def invoke(self, inputs: Dict[str, Any]) -> str:
            # Simulate LLM response based on the context
            context = inputs.get("context", "").lower()
            function_name = inputs.get("function_name", "")
            
            if "mean" in context and function_name == "Mean":
                return json.dumps({
                    "primary_function_inputs": {"variable": "sales"},
                    "additional_computations": [],
                    "pipeline_sequence": ["Calculate mean of sales"],
                    "reasoning": "Direct mean calculation using metrics_tools Mean function"
                })
            elif "percent change" in context and function_name == "PercentChange":
                return json.dumps({
                    "primary_function_inputs": {"condition_column": "customer_type", "baseline": "standard"},
                    "additional_computations": [
                        {
                            "function": "Mean",
                            "inputs": {"variable": "revenue"},
                            "tool": "metrics_tools"
                        }
                    ],
                    "pipeline_sequence": ["Calculate mean revenue", "Calculate percent change vs baseline"],
                    "reasoning": "First need to calculate average revenue using Mean, then apply PercentChange"
                })
            else:
                return json.dumps({
                    "primary_function_inputs": {},
                    "additional_computations": [],
                    "pipeline_sequence": ["Basic analysis"],
                    "reasoning": "Basic analysis without additional computations"
                })
    
    # Create mock LLM instance
    mock_llm = MockLLM()
    
    # Available functions
    metrics_functions = [
        "Count", "Sum", "Max", "Min", "Ratio", "Dot", "Nth", "Variance", 
        "StandardDeviation", "CV", "Correlation", "Cov", "Mean", "Median", 
        "Percentile", "PivotTable", "GroupBy", "Filter", "CumulativeSum", 
        "RollingMetric", "Execute", "ShowPivot", "ShowDataFrame"
    ]
    
    operations_functions = [
        "PercentChange", "AbsoluteChange", "MH", "CUPED", "PrePostChange",
        "FilterConditions", "PowerAnalysis", "StratifiedSummary", "BootstrapCI",
        "MultiComparisonAdjustment", "ExecuteOperations", "ShowOperation", "ShowComparison"
    ]
    
    # Test cases
    test_cases = [
        {
            "context": "Calculate the mean of sales column",
            "function_name": "Mean",
            "expected_computations": 0
        },
        {
            "context": "Calculate the average revenue per customer and then find the percent change compared to baseline",
            "function_name": "PercentChange",
            "expected_computations": 1
        },
        {
            "context": "Find the sum of transactions, calculate correlation with time, and show percent change",
            "function_name": "PercentChange",
            "expected_computations": 2
        }
    ]
    
    # Detection prompt (same as in the main class)
    detection_prompt = PromptTemplate(
        input_variables=[
            "context", "function_name", "classification_context", "dataset_context",
            "metrics_functions", "operations_functions"
        ],
        template="""
        You are an expert function input detector for data analysis pipelines.
        
        TASK: Analyze the given context and function name to detect the required function inputs,
        including any additional computations needed (like mean, average, etc.) or whether to use
        functions from metrics_tools.py or operations_tools.py.
        
        CONTEXT: {context}
        FUNCTION NAME: {function_name}
        
        CLASSIFICATION ANALYSIS:
        {classification_context}
        
        DATASET INFORMATION:
        {dataset_context}
        
        AVAILABLE METRICS FUNCTIONS (from metrics_tools.py):
        {metrics_functions}
        
        AVAILABLE OPERATIONS FUNCTIONS (from operations_tools.py):
        {operations_functions}
        
        INSTRUCTIONS:
        1. Analyze the context to understand what data analysis is being requested
        2. Determine the required function inputs for the primary function
        3. Identify if any additional computations are needed (e.g., mean, average, sum, etc.)
        4. Decide if any metrics_tools.py or operations_tools.py functions should be used
        5. Consider the classification analysis for additional context
        6. Return a JSON object with the detected inputs
        
        OUTPUT FORMAT:
        Return ONLY a valid JSON object with the following structure:
        {{
            "primary_function_inputs": {{
                "param1": "value1",
                "param2": "value2"
            }},
            "additional_computations": [
                {{
                    "function": "function_name",
                    "inputs": {{
                        "param1": "value1",
                        "param2": "value2"
                    }},
                    "tool": "metrics_tools" | "operations_tools" | "builtin"
                }}
            ],
            "pipeline_sequence": [
                "step1_description",
                "step2_description"
            ],
            "reasoning": "explanation of why these inputs were chosen"
        }}
        
        Now analyze the given context and return the appropriate JSON response.
        """
    )
    
    # Create detection chain
    detection_chain = detection_prompt | mock_llm | StrOutputParser()
    
    print("Testing Function Input Detection")
    print("=" * 50)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}:")
        print(f"Context: {test_case['context']}")
        print(f"Function: {test_case['function_name']}")
        
        try:
            # Invoke the detection
            result = detection_chain.invoke({
                "context": test_case["context"],
                "function_name": test_case["function_name"],
                "classification_context": "No classification available",
                "dataset_context": "No dataset information available",
                "metrics_functions": ", ".join(metrics_functions),
                "operations_functions": ", ".join(operations_functions)
            })
            
            # Parse the JSON result
            detected_inputs = json.loads(result.strip())
            
            print(f"Detected Inputs:")
            print(f"  Primary Function Inputs: {detected_inputs.get('primary_function_inputs', {})}")
            print(f"  Additional Computations: {len(detected_inputs.get('additional_computations', []))}")
            print(f"  Pipeline Sequence: {detected_inputs.get('pipeline_sequence', [])}")
            print(f"  Reasoning: {detected_inputs.get('reasoning', '')}")
            
            # Validate expected number of computations
            actual_computations = len(detected_inputs.get('additional_computations', []))
            expected_computations = test_case['expected_computations']
            
            if actual_computations == expected_computations:
                print(f"  ✅ PASS: Expected {expected_computations} computations, got {actual_computations}")
            else:
                print(f"  ❌ FAIL: Expected {expected_computations} computations, got {actual_computations}")
            
        except Exception as e:
            print(f"  ❌ ERROR: {str(e)}")
    
    print("\n" + "=" * 50)
    print("Test completed!")

if __name__ == "__main__":
    test_function_input_detection() 
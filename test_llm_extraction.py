#!/usr/bin/env python3
"""
Test script for LLM-based data selection step extraction
"""

import asyncio
import json
from typing import List, Dict, Any

# Mock LLM for testing
class MockLLM:
    async def ainvoke(self, inputs: Dict[str, Any]) -> str:
        """Mock LLM response for testing"""
        reasoning_plan = inputs.get("reasoning_plan", "[]")
        
        # Simulate LLM response based on the reasoning plan
        if "data selection" in reasoning_plan.lower() or "select columns" in reasoning_plan.lower():
            return json.dumps([
                {
                    "step_number": 1,
                    "step_title": "Data Selection and Preparation",
                    "step_description": "Select relevant columns for analysis based on requirements",
                    "data_requirements": ["customer_id", "order_date", "amount"],
                    "expected_outcome": "Dataset with selected columns ready for analysis",
                    "considerations": "Ensure all required columns are available and properly formatted"
                }
            ])
        else:
            return json.dumps([
                {
                    "step_number": 1,
                    "step_title": "Default Data Selection",
                    "step_description": "Select columns based on analysis requirements",
                    "data_requirements": ["id", "date", "value"],
                    "expected_outcome": "Prepared dataset for analysis",
                    "considerations": "Standard data preparation step"
                }
            ])

async def test_llm_extraction():
    """Test the LLM-based extraction functionality"""
    
    # Sample reasoning plan
    reasoning_plan = [
        {
            "step_number": 1,
            "step_title": "Data Selection",
            "step_description": "Select relevant columns for customer analysis",
            "data_requirements": ["customer_id", "order_date", "amount"],
            "expected_outcome": "Filtered dataset",
            "considerations": "Ensure data quality"
        },
        {
            "step_number": 2,
            "step_title": "Calculate Metrics",
            "step_description": "Calculate average order value",
            "data_requirements": ["amount"],
            "expected_outcome": "Average order value",
            "considerations": "Handle missing values"
        }
    ]
    
    # Create mock LLM
    mock_llm = MockLLM()
    
    # Test the extraction logic
    try:
        # Simulate the LLM call
        llm_response = await mock_llm.ainvoke({
            "reasoning_plan": json.dumps(reasoning_plan, indent=2)
        })
        
        print("LLM Response:")
        print(llm_response)
        print()
        
        # Parse the response
        extracted_steps = json.loads(llm_response)
        
        print("Extracted Steps:")
        for step in extracted_steps:
            print(f"Step {step['step_number']}: {step['step_title']}")
            print(f"  Description: {step['step_description']}")
            print(f"  Requirements: {step['data_requirements']}")
            print(f"  Outcome: {step['expected_outcome']}")
            print(f"  Considerations: {step['considerations']}")
            print()
        
        print("✅ Test completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_llm_extraction()) 
#!/usr/bin/env python3
"""
Test script to debug chart generation issues
"""

import asyncio
import os
import sys
import logging

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'genieml'))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set environment variable for testing
os.environ["OPENAI_API_KEY"] = "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"

async def test_chart_generation():
    """Test the chart generation pipeline"""
    try:
        from app.agents.nodes.sql.chart_generation import create_vega_lite_chart_generation_pipeline
        
        # Sample data for testing
        sample_data = {
            "columns": ["Division", "On_Time_Count", "Late_Count"],
            "data": [
                ["Engineering", 45, 5],
                ["Sales", 38, 12],
                ["Marketing", 42, 8],
                ["HR", 35, 15]
            ]
        }
        
        # Create pipeline
        pipeline = create_vega_lite_chart_generation_pipeline()
        
        # Test chart generation
        result = await pipeline.run(
            query="Show me the number of employees who have completed training on time or late per division",
            sql="SELECT Division, On_Time_Count, Late_Count FROM training_completion",
            data=sample_data,
            language="English",
            remove_data_from_chart_schema=True
        )
        
        print("Chart Generation Result:")
        print(f"Success: {result.get('success', False)}")
        print(f"Chart Type: {result.get('chart_type', '')}")
        print(f"Reasoning: {result.get('reasoning', '')[:200]}...")
        print(f"Chart Schema: {result.get('chart_schema', {})}")
        
        if result.get('error'):
            print(f"Error: {result.get('error')}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in test: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    asyncio.run(test_chart_generation()) 
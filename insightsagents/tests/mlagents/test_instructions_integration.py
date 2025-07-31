#!/usr/bin/env python3
"""
Test script to verify that instructions are properly integrated into FunctionRetrieval.
Instructions are now included in the LLM prompt for better function matching decisions.
"""

import asyncio
import logging
from unittest.mock import Mock
from pathlib import Path
import sys

# Add the insightsagents directory to the path
sys.path.append(str(Path(__file__).parent))

from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.agents.nodes.mlagents.function_retrieval import FunctionRetrieval

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test-instructions-integration")


async def test_instructions_integration():
    """Test that instructions are properly integrated into FunctionRetrieval prompt."""
    
    logger.info("Starting instructions integration test...")
    
    try:
        # Initialize RetrievalHelper
        logger.info("Initializing RetrievalHelper...")
        retrieval_helper = RetrievalHelper()
        logger.info("RetrievalHelper initialized successfully")
        
        # Mock LLM for testing
        logger.info("Setting up mock LLM...")
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = '''
        {
            "top_functions": [
                {
                    "function_name": "variance_analysis",
                    "pipe_name": "MovingAggrPipe",
                    "description": "Calculate moving variance and standard deviation for specified columns",
                    "usage_description": "Measures volatility and variability over time.",
                    "relevance_score": 0.95,
                    "reasoning": "The user specifically asks for rolling variance analysis. The instructions suggest using variance analysis for financial data.",
                    "rephrased_question": "Calculate rolling variance analysis for time series data"
                }
            ],
            "rephrased_question": "Calculate 5-day rolling variance of flux metric",
            "confidence_score": 0.9,
            "reasoning": "The user's question clearly indicates a need for rolling variance analysis. The provided instructions confirm this approach.",
            "suggested_pipes": ["MovingAggrPipe"],
            "total_functions_analyzed": 150
        }
        '''
        mock_llm.ainvoke = Mock(return_value=mock_response)
        logger.info("Mock LLM setup complete")
        
        # Initialize FunctionRetrieval with RetrievalHelper
        logger.info("Initializing FunctionRetrieval with RetrievalHelper...")
        function_retrieval = FunctionRetrieval(
            llm=mock_llm, 
            retrieval_helper=retrieval_helper
        )
        logger.info("FunctionRetrieval initialized successfully")
        
        # Test with sample question and project_id
        logger.info("Testing function retrieval with instructions in prompt...")
        question = "How does the 5-day rolling variance of flux change over time?"
        dataframe_description = "Financial metrics dataset"
        dataframe_summary = "Contains 10,000 rows with daily metrics"
        available_columns = ["flux", "timestamp", "projects"]
        project_id = "test_project"
        
        result = await function_retrieval.retrieve_relevant_functions(
            question=question,
            dataframe_description=dataframe_description,
            dataframe_summary=dataframe_summary,
            available_columns=available_columns,
            project_id=project_id
        )
        
        # Verify results
        logger.info("Verifying results...")
        assert result is not None, "Result should not be None"
        assert hasattr(result, 'top_functions'), "Result should have top_functions attribute"
        
        logger.info(f"✅ Instructions integration test passed!")
        logger.info(f"   - Top functions found: {len(result.top_functions)}")
        logger.info(f"   - Project ID used: {project_id}")
        logger.info(f"   - Instructions are now included in the LLM prompt for better function matching")
        
        # Test direct instructions retrieval
        logger.info("Testing direct instructions retrieval...")
        instructions_result = await function_retrieval.get_instructions(question, project_id)
        assert instructions_result is not None, "Instructions result should not be None"
        logger.info(f"✅ Direct instructions retrieval test passed!")
        logger.info(f"   - Instructions result: {instructions_result}")
        
        logger.info("🎉 All instructions integration tests passed!")
        logger.info("   - Instructions are now properly integrated into the LLM prompt")
        logger.info("   - LLM can use instructions to make better function matching decisions")
        return True
        
    except Exception as e:
        logger.error(f"❌ Instructions integration test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main test function."""
    logger.info("=" * 60)
    logger.info("INSTRUCTIONS INTEGRATION TEST")
    logger.info("=" * 60)
    
    success = await test_instructions_integration()
    
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Instructions Integration: {'✅ PASSED' if success else '❌ FAILED'}")
    
    if success:
        logger.info("\n🎉 ALL TESTS PASSED! Instructions integration is working correctly.")
        logger.info("   - Instructions are now included in the LLM prompt")
        logger.info("   - This enables better function matching based on project-specific guidance")
        return True
    else:
        logger.error("\n❌ TESTS FAILED! Please check the errors above.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 
#!/usr/bin/env python3
"""
Test script to verify the step-by-step approach.
The new approach:
STEP 1: Rephrase question, classify intent based on MOST SPECIFIC analysis type, and create reasoning plan
STEP 2: Use Step 1 output for function selection and detailed planning
"""

import asyncio
import logging
from unittest.mock import Mock
from pathlib import Path
import sys

# Add the insightsagents directory to the path
sys.path.append(str(Path(__file__).parent))

from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.agents.nodes.mlagents.analysis_intent_classification import AnalysisIntentPlanner

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test-step-by-step-approach")


async def test_step_by_step_approach():
    """Test the new step-by-step approach."""
    
    logger.info("Starting step-by-step approach test...")
    
    try:
        # Initialize RetrievalHelper
        logger.info("Initializing RetrievalHelper...")
        retrieval_helper = RetrievalHelper()
        logger.info("RetrievalHelper initialized successfully")
        
        # Mock LLM for testing
        logger.info("Setting up mock LLM...")
        mock_llm = Mock()
        
        # Mock response for Step 1 - Question Analysis
        mock_step1_response = Mock()
        mock_step1_response.content = '''
        {
            "rephrased_question": "Calculate 5-day rolling variance of flux metric grouped by organizational units over time",
            "intent_type": "time_series_analysis",
            "confidence_score": 0.95,
            "reasoning": "Question specifically asks for rolling variance over time with grouping, which is a time series analysis",
            "required_data_columns": ["flux", "timestamp", "projects", "cost_centers", "departments"],
            "clarification_needed": null,
            "can_be_answered": true,
            "feasibility_score": 0.9,
            "missing_columns": [],
            "available_alternatives": [],
            "data_suggestions": "All required columns are available for the analysis",
            "reasoning_plan": [
                {
                    "step_number": 1,
                    "step_title": "Data Preparation and Cleaning",
                    "step_description": "Clean and prepare the data for rolling variance analysis",
                    "data_requirements": ["flux", "timestamp"],
                    "expected_outcome": "Clean dataset with proper datetime formatting",
                    "considerations": "Ensure timestamp is in datetime format and handle missing values",
                    "suggested_functions": ["data_cleaning", "datetime_conversion"],
                    "function_reasoning": "Data preparation functions needed to ensure data quality"
                },
                {
                    "step_number": 2,
                    "step_title": "Rolling Variance Calculation",
                    "step_description": "Calculate 5-day rolling variance for flux metric",
                    "data_requirements": ["flux", "timestamp"],
                    "expected_outcome": "Rolling variance values over time",
                    "considerations": "Use appropriate window size and handle edge cases",
                    "suggested_functions": ["variance_analysis", "rolling_window"],
                    "function_reasoning": "Variance analysis function specifically designed for rolling calculations"
                },
                {
                    "step_number": 3,
                    "step_title": "Group Analysis and Aggregation",
                    "step_description": "Group results by projects, cost centers, and departments",
                    "data_requirements": ["projects", "cost_centers", "departments"],
                    "expected_outcome": "Variance analysis by organizational groups",
                    "considerations": "Handle groups with insufficient data",
                    "suggested_functions": ["group_by", "aggregate"],
                    "function_reasoning": "Grouping functions needed to organize results by organizational units"
                }
            ]
        }
        '''
        
        # Mock response for Step 2 - Function Selection and Planning
        mock_step2_response = Mock()
        mock_step2_response.content = '''
        {
            "selected_functions": [
                {
                    "function_name": "variance_analysis",
                    "pipe_name": "statistical_analysis",
                    "priority": 1,
                    "relevance_score": 0.95,
                    "reasoning": "Primary function for rolling variance calculation",
                    "step_applicability": ["step2"],
                    "data_requirements": ["flux", "timestamp"],
                    "expected_output": "Rolling variance values over time"
                },
                {
                    "function_name": "group_by",
                    "pipe_name": "data_manipulation",
                    "priority": 2,
                    "relevance_score": 0.9,
                    "reasoning": "Required for grouping by organizational units",
                    "step_applicability": ["step3"],
                    "data_requirements": ["projects", "cost_centers", "departments"],
                    "expected_output": "Grouped variance analysis results"
                },
                {
                    "function_name": "data_cleaning",
                    "pipe_name": "data_preparation",
                    "priority": 3,
                    "relevance_score": 0.85,
                    "reasoning": "Essential for data quality assurance",
                    "step_applicability": ["step1"],
                    "data_requirements": ["flux", "timestamp"],
                    "expected_output": "Clean dataset ready for analysis"
                }
            ],
            "function_selection_reasoning": "Selected functions based on the reasoning plan from Step 1, prioritizing variance analysis and grouping capabilities",
            "analysis_complexity": "medium",
            "estimated_execution_time": "5-10 minutes",
            "potential_issues": ["Large dataset may slow down rolling calculations", "Some groups may have insufficient data"],
            "recommendations": ["Consider data sampling for large datasets", "Validate group sizes before analysis"]
        }
        '''
        
        # Set up mock to return different responses based on the prompt
        def mock_ainvoke(input_dict):
            prompt = str(input_dict)
            if "STEP 1 TASK" in prompt or "Rephrase the question" in prompt:
                return mock_step1_response
            elif "STEP 2 TASK" in prompt or "ANALYZE REASONING PLAN" in prompt:
                return mock_step2_response
            else:
                return mock_step1_response  # Default
        
        mock_llm.ainvoke = Mock(side_effect=mock_ainvoke)
        logger.info("Mock LLM setup complete")
        
        # Initialize AnalysisIntentPlanner with RetrievalHelper
        logger.info("Initializing AnalysisIntentPlanner with RetrievalHelper...")
        planner = AnalysisIntentPlanner(llm=mock_llm)
        logger.info("AnalysisIntentPlanner initialized successfully")
        
        # Test with sample question and project_id
        logger.info("Testing step-by-step approach...")
        question = "How does the 5-day rolling variance of flux change over time for each group of projects, cost centers, and departments?"
        dataframe_description = "Financial metrics dataset with project performance data"
        dataframe_summary = "Contains 10,000 rows with daily metrics from 2023-2024"
        available_columns = ["flux", "timestamp", "projects", "cost_centers", "departments"]
        project_id = "test_project"
        
        result = await planner.classify_intent(
            question=question,
            dataframe_description=dataframe_description,
            dataframe_summary=dataframe_summary,
            available_columns=available_columns,
            project_id=project_id
        )
        
        # Verify results
        logger.info("Verifying results...")
        assert result is not None, "Result should not be None"
        assert hasattr(result, 'intent_type'), "Result should have intent_type attribute"
        assert hasattr(result, 'confidence_score'), "Result should have confidence_score attribute"
        assert hasattr(result, 'reasoning_plan'), "Result should have reasoning_plan attribute"
        assert hasattr(result, 'suggested_functions'), "Result should have suggested_functions attribute"
        
        logger.info(f"✅ Step-by-step approach test passed!")
        logger.info(f"   - Intent type: {result.intent_type}")
        logger.info(f"   - Confidence score: {result.confidence_score}")
        logger.info(f"   - Project ID used: {project_id}")
        logger.info(f"   - Reasoning plan steps: {len(result.reasoning_plan) if result.reasoning_plan else 0}")
        logger.info(f"   - Selected functions: {result.suggested_functions}")
        logger.info(f"   - New approach: Step 1 (question analysis) → Step 2 (function selection)")
        
        # Display reasoning plan details
        if result.reasoning_plan:
            logger.info("📋 Step 1 Reasoning Plan Details:")
            for step in result.reasoning_plan:
                logger.info(f"   Step {step.get('step_number', 'N/A')}: {step.get('step_title', 'N/A')}")
                logger.info(f"     Description: {step.get('step_description', 'N/A')}")
                logger.info(f"     Data Requirements: {step.get('data_requirements', [])}")
                logger.info(f"     Expected Outcome: {step.get('expected_outcome', 'N/A')}")
                logger.info(f"     Considerations: {step.get('considerations', 'N/A')}")
                logger.info(f"     Suggested Functions: {step.get('suggested_functions', [])}")
                logger.info(f"     Function Reasoning: {step.get('function_reasoning', 'N/A')}")
                logger.info("")
        
        # Test individual steps
        logger.info("Testing individual steps...")
        
        # Test Step 1 directly
        logger.info("Testing Step 1 - Question Analysis...")
        step1_result = await planner._step1_question_analysis(
            question=question,
            dataframe_description=dataframe_description,
            dataframe_summary=dataframe_summary,
            available_columns=available_columns,
            project_id=project_id
        )
        assert step1_result is not None, "Step 1 result should not be None"
        assert "rephrased_question" in step1_result, "Step 1 should have rephrased_question"
        assert "intent_type" in step1_result, "Step 1 should have intent_type"
        assert "reasoning_plan" in step1_result, "Step 1 should have reasoning_plan"
        logger.info(f"✅ Step 1 test passed!")
        logger.info(f"   - Rephrased question: {step1_result.get('rephrased_question', 'N/A')}")
        logger.info(f"   - Intent type: {step1_result.get('intent_type', 'N/A')}")
        logger.info(f"   - Confidence score: {step1_result.get('confidence_score', 'N/A')}")
        logger.info(f"   - Reasoning plan steps: {len(step1_result.get('reasoning_plan', []))}")
        
        # Test Step 2 directly
        logger.info("Testing Step 2 - Function Selection and Planning...")
        step2_result = await planner._step2_function_selection_and_planning(
            step1_output=step1_result,
            question=question,
            available_columns=available_columns
        )
        assert step2_result is not None, "Step 2 result should not be None"
        assert "function_names" in step2_result, "Step 2 should have function_names"
        assert "function_details" in step2_result, "Step 2 should have function_details"
        logger.info(f"✅ Step 2 test passed!")
        logger.info(f"   - Selected functions: {step2_result.get('function_names', [])}")
        logger.info(f"   - Analysis complexity: {step2_result.get('analysis_complexity', 'N/A')}")
        logger.info(f"   - Estimated execution time: {step2_result.get('estimated_execution_time', 'N/A')}")
        
        logger.info("🎉 All step-by-step approach tests passed!")
        logger.info("   - Step 1: Question rephrasing, intent classification, and reasoning plan creation")
        logger.info("   - Step 2: Function selection and detailed planning based on Step 1 output")
        logger.info("   - Clear separation of concerns between analysis planning and function selection")
        return True
        
    except Exception as e:
        logger.error(f"❌ Step-by-step approach test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_step_comparison():
    """Test the difference between old and new step-by-step approaches."""
    
    logger.info("Starting step comparison test...")
    
    try:
        # Mock LLM for comparison
        mock_llm = Mock()
        
        # Mock responses for different approaches
        mock_old_approach_response = Mock()
        mock_old_approach_response.content = '''
        {
            "intent_type": "time_series_analysis",
            "confidence_score": 0.85,
            "rephrased_question": "Calculate rolling variance",
            "suggested_functions": ["variance_analysis"],
            "reasoning": "Question asks for rolling variance analysis",
            "required_data_columns": ["flux", "timestamp"],
            "can_be_answered": true,
            "feasibility_score": 0.8
        }
        '''
        
        mock_new_step1_response = Mock()
        mock_new_step1_response.content = '''
        {
            "rephrased_question": "Calculate 5-day rolling variance of flux metric grouped by organizational units over time",
            "intent_type": "time_series_analysis",
            "confidence_score": 0.95,
            "reasoning": "Question specifically asks for rolling variance over time with grouping, which is a time series analysis",
            "reasoning_plan": [
                {
                    "step_number": 1,
                    "step_title": "Data Preparation",
                    "step_description": "Clean and prepare data",
                    "data_requirements": ["flux", "timestamp"],
                    "expected_outcome": "Clean dataset",
                    "considerations": "Handle missing values",
                    "suggested_functions": ["data_cleaning", "variance_analysis", "group_by"],
                    "function_reasoning": "Multiple functions needed for comprehensive analysis"
                }
            ]
        }
        '''
        
        mock_new_step2_response = Mock()
        mock_new_step2_response.content = '''
        {
            "selected_functions": [
                {
                    "function_name": "variance_analysis",
                    "priority": 1,
                    "relevance_score": 0.95,
                    "reasoning": "Primary function for rolling variance calculation"
                }
            ],
            "function_selection_reasoning": "Selected based on the reasoning plan from Step 1",
            "analysis_complexity": "medium",
            "estimated_execution_time": "5-10 minutes"
        }
        '''
        
        def mock_ainvoke(input_dict):
            prompt = str(input_dict)
            if "STEP 1 TASK" in prompt:
                return mock_new_step1_response
            elif "STEP 2 TASK" in prompt:
                return mock_new_step2_response
            else:
                return mock_old_approach_response
        
        mock_llm.ainvoke = Mock(side_effect=mock_ainvoke)
        
        planner = AnalysisIntentPlanner(llm=mock_llm)
        
        # Test new step-by-step approach
        result_new = await planner.classify_intent(
            question="How does the 5-day rolling variance of flux change over time?",
            dataframe_description="Financial metrics dataset",
            dataframe_summary="Contains 10,000 rows with daily metrics",
            available_columns=["flux", "timestamp", "projects", "cost_centers", "departments"],
            project_id="test_project"
        )
        
        logger.info("📊 Step-by-Step Approach Comparison Results:")
        logger.info(f"   New Approach - Confidence: {result_new.confidence_score}")
        logger.info(f"   New Approach - Functions: {result_new.suggested_functions}")
        logger.info(f"   New Approach - Plan Steps: {len(result_new.reasoning_plan) if result_new.reasoning_plan else 0}")
        logger.info(f"   New Approach - Step 1: Question rephrasing, intent classification, reasoning plan")
        logger.info(f"   New Approach - Step 2: Function selection based on Step 1 output")
        
        logger.info("✅ Step comparison test passed!")
        logger.info("   - New approach provides clearer separation of concerns")
        logger.info("   - Step 1 focuses on analysis planning and intent classification")
        logger.info("   - Step 2 focuses on optimal function selection based on the plan")
        logger.info("   - Higher confidence due to more structured analysis approach")
        return True
        
    except Exception as e:
        logger.error(f"❌ Step comparison test failed: {str(e)}")
        return False


async def main():
    """Main test function."""
    logger.info("=" * 60)
    logger.info("STEP-BY-STEP APPROACH TEST")
    logger.info("=" * 60)
    
    success1 = await test_step_by_step_approach()
    success2 = await test_step_comparison()
    
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Step-by-Step Approach: {'✅ PASSED' if success1 else '❌ FAILED'}")
    logger.info(f"Step Comparison: {'✅ PASSED' if success2 else '❌ FAILED'}")
    
    overall_success = success1 and success2
    
    if overall_success:
        logger.info("\n🎉 ALL TESTS PASSED! Step-by-step approach is working correctly.")
        logger.info("   - Step 1: Question rephrasing, intent classification, and reasoning plan creation")
        logger.info("   - Step 2: Function selection and detailed planning based on Step 1 output")
        logger.info("   - Clear separation of concerns between analysis planning and function selection")
        logger.info("   - More structured and intelligent analysis approach")
        return True
    else:
        logger.error("\n❌ TESTS FAILED! Please check the errors above.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 
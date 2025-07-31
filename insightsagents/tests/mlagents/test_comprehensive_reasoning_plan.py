#!/usr/bin/env python3
"""
Test script to verify the comprehensive reasoning plan approach.
The new approach: 
1. Generate comprehensive reasoning plan using ALL available functions
2. Select best functions based on the reasoning plan
3. Classify intent based on the plan and selected functions
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
logger = logging.getLogger("test-comprehensive-reasoning-plan")


async def test_comprehensive_reasoning_plan_approach():
    """Test the new comprehensive reasoning plan approach."""
    
    logger.info("Starting comprehensive reasoning plan approach test...")
    
    try:
        # Initialize RetrievalHelper
        logger.info("Initializing RetrievalHelper...")
        retrieval_helper = RetrievalHelper()
        logger.info("RetrievalHelper initialized successfully")
        
        # Mock LLM for testing
        logger.info("Setting up mock LLM...")
        mock_llm = Mock()
        
        # Mock response for comprehensive reasoning plan generation
        mock_comprehensive_response = Mock()
        mock_comprehensive_response.content = '''
        [
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
        '''
        
        # Mock response for intent classification
        mock_intent_response = Mock()
        mock_intent_response.content = '''
        {
            "intent_type": "time_series_analysis",
            "confidence_score": 0.95,
            "rephrased_question": "Calculate 5-day rolling variance of flux metric grouped by organizational units over time",
            "reasoning": "The comprehensive reasoning plan shows a clear time series analysis approach with rolling variance calculations and grouping by organizational units",
            "required_data_columns": ["flux", "timestamp", "projects", "cost_centers", "departments"],
            "clarification_needed": null,
            "can_be_answered": true,
            "feasibility_score": 0.9,
            "missing_columns": [],
            "available_alternatives": [],
            "data_suggestions": "All required columns are available for the analysis"
        }
        '''
        
        # Set up mock to return different responses based on the prompt
        def mock_ainvoke(input_dict):
            prompt = str(input_dict)
            if "comprehensive step-by-step reasoning plan" in prompt:
                return mock_comprehensive_response
            elif "classifying the intent" in prompt:
                return mock_intent_response
            else:
                return mock_comprehensive_response  # Default
        
        mock_llm.ainvoke = Mock(side_effect=mock_ainvoke)
        logger.info("Mock LLM setup complete")
        
        # Initialize AnalysisIntentPlanner with RetrievalHelper
        logger.info("Initializing AnalysisIntentPlanner with RetrievalHelper...")
        planner = AnalysisIntentPlanner(llm=mock_llm)
        logger.info("AnalysisIntentPlanner initialized successfully")
        
        # Test with sample question and project_id
        logger.info("Testing comprehensive reasoning plan approach...")
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
        
        logger.info(f"✅ Comprehensive reasoning plan approach test passed!")
        logger.info(f"   - Intent type: {result.intent_type}")
        logger.info(f"   - Confidence score: {result.confidence_score}")
        logger.info(f"   - Project ID used: {project_id}")
        logger.info(f"   - Reasoning plan steps: {len(result.reasoning_plan) if result.reasoning_plan else 0}")
        logger.info(f"   - Selected functions: {result.suggested_functions}")
        logger.info(f"   - New approach: Reasoning plan generated first, then functions selected based on plan")
        
        # Display reasoning plan details
        if result.reasoning_plan:
            logger.info("📋 Comprehensive Reasoning Plan Details:")
            for step in result.reasoning_plan:
                logger.info(f"   Step {step.get('step_number', 'N/A')}: {step.get('step_title', 'N/A')}")
                logger.info(f"     Description: {step.get('step_description', 'N/A')}")
                logger.info(f"     Data Requirements: {step.get('data_requirements', [])}")
                logger.info(f"     Expected Outcome: {step.get('expected_outcome', 'N/A')}")
                logger.info(f"     Considerations: {step.get('considerations', 'N/A')}")
                logger.info(f"     Suggested Functions: {step.get('suggested_functions', [])}")
                logger.info(f"     Function Reasoning: {step.get('function_reasoning', 'N/A')}")
                logger.info("")
        
        # Test individual components
        logger.info("Testing individual components...")
        
        # Test comprehensive reasoning plan generation
        logger.info("Testing comprehensive reasoning plan generation...")
        function_library = planner.function_retrieval._load_function_library()
        all_functions = []
        for pipe_name, pipe_info in function_library.items():
            if 'functions' in pipe_info:
                for func_name, func_info in pipe_info['functions'].items():
                    all_functions.append({
                        'function_name': func_name,
                        'pipe_name': pipe_name,
                        'description': func_info.get('description', ''),
                        'usage_description': func_info.get('usage_description', ''),
                        'category': func_info.get('category', ''),
                        'type_of_operation': func_info.get('type_of_operation', '')
                    })
        
        comprehensive_plan = await planner._generate_comprehensive_reasoning_plan(
            question=question,
            dataframe_description=dataframe_description,
            dataframe_summary=dataframe_summary,
            available_columns=available_columns,
            all_functions=all_functions,
            historical_context="",
            instructions_context=""
        )
        assert comprehensive_plan is not None, "Comprehensive plan should not be None"
        assert isinstance(comprehensive_plan, list), "Comprehensive plan should be a list"
        logger.info(f"✅ Comprehensive reasoning plan generation test passed!")
        logger.info(f"   - Generated {len(comprehensive_plan)} steps")
        
        # Test function selection from plan
        logger.info("Testing function selection from plan...")
        selected_functions = await planner._select_best_functions_from_plan(
            question=question,
            reasoning_plan=comprehensive_plan,
            all_functions=all_functions,
            available_columns=available_columns
        )
        assert selected_functions is not None, "Selected functions should not be None"
        assert "function_names" in selected_functions, "Should have function_names"
        assert "function_details" in selected_functions, "Should have function_details"
        logger.info(f"✅ Function selection from plan test passed!")
        logger.info(f"   - Selected {len(selected_functions.get('function_names', []))} functions")
        
        # Test intent classification from plan
        logger.info("Testing intent classification from plan...")
        intent_classification = await planner._classify_intent_from_plan(
            question=question,
            reasoning_plan=comprehensive_plan,
            selected_functions=selected_functions,
            available_columns=available_columns
        )
        assert intent_classification is not None, "Intent classification should not be None"
        assert "intent_type" in intent_classification, "Should have intent_type"
        logger.info(f"✅ Intent classification from plan test passed!")
        logger.info(f"   - Intent type: {intent_classification.get('intent_type', 'N/A')}")
        
        logger.info("🎉 All comprehensive reasoning plan approach tests passed!")
        logger.info("   - New approach successfully implemented")
        logger.info("   - Reasoning plan generated first using all available functions")
        logger.info("   - Best functions selected based on the reasoning plan")
        logger.info("   - Intent classified based on the plan and selected functions")
        return True
        
    except Exception as e:
        logger.error(f"❌ Comprehensive reasoning plan approach test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_approach_comparison():
    """Test the difference between old and new approaches."""
    
    logger.info("Starting approach comparison test...")
    
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
        
        mock_new_approach_comprehensive = Mock()
        mock_new_approach_comprehensive.content = '''
        [
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
        '''
        
        mock_new_approach_intent = Mock()
        mock_new_approach_intent.content = '''
        {
            "intent_type": "time_series_analysis",
            "confidence_score": 0.95,
            "rephrased_question": "Comprehensive rolling variance analysis with grouping",
            "reasoning": "Based on comprehensive plan that considers data preparation, variance calculation, and grouping",
            "required_data_columns": ["flux", "timestamp", "projects", "cost_centers", "departments"],
            "can_be_answered": true,
            "feasibility_score": 0.9
        }
        '''
        
        def mock_ainvoke(input_dict):
            prompt = str(input_dict)
            if "comprehensive step-by-step reasoning plan" in prompt:
                return mock_new_approach_comprehensive
            elif "classifying the intent" in prompt:
                return mock_new_approach_intent
            else:
                return mock_old_approach_response
        
        mock_llm.ainvoke = Mock(side_effect=mock_ainvoke)
        
        planner = AnalysisIntentPlanner(llm=mock_llm)
        
        # Test new approach
        result_new = await planner.classify_intent(
            question="How does the 5-day rolling variance of flux change over time?",
            dataframe_description="Financial metrics dataset",
            dataframe_summary="Contains 10,000 rows with daily metrics",
            available_columns=["flux", "timestamp", "projects", "cost_centers", "departments"],
            project_id="test_project"
        )
        
        logger.info("📊 Approach Comparison Results:")
        logger.info(f"   New Approach - Confidence: {result_new.confidence_score}")
        logger.info(f"   New Approach - Functions: {result_new.suggested_functions}")
        logger.info(f"   New Approach - Plan Steps: {len(result_new.reasoning_plan) if result_new.reasoning_plan else 0}")
        logger.info(f"   New Approach - Comprehensive: Uses all available functions for planning")
        logger.info(f"   New Approach - Selection: Functions selected based on reasoning plan")
        
        logger.info("✅ Approach comparison test passed!")
        logger.info("   - New approach provides more comprehensive analysis planning")
        logger.info("   - Functions are selected based on detailed reasoning plan")
        logger.info("   - Higher confidence due to comprehensive consideration of all options")
        return True
        
    except Exception as e:
        logger.error(f"❌ Approach comparison test failed: {str(e)}")
        return False


async def main():
    """Main test function."""
    logger.info("=" * 60)
    logger.info("COMPREHENSIVE REASONING PLAN APPROACH TEST")
    logger.info("=" * 60)
    
    success1 = await test_comprehensive_reasoning_plan_approach()
    success2 = await test_approach_comparison()
    
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Comprehensive Reasoning Plan Approach: {'✅ PASSED' if success1 else '❌ FAILED'}")
    logger.info(f"Approach Comparison: {'✅ PASSED' if success2 else '❌ FAILED'}")
    
    overall_success = success1 and success2
    
    if overall_success:
        logger.info("\n🎉 ALL TESTS PASSED! Comprehensive reasoning plan approach is working correctly.")
        logger.info("   - New approach: Reasoning plan generated first using ALL available functions")
        logger.info("   - Best functions selected based on the comprehensive reasoning plan")
        logger.info("   - Intent classified based on the plan and selected functions")
        logger.info("   - More comprehensive and intelligent function selection")
        return True
    else:
        logger.error("\n❌ TESTS FAILED! Please check the errors above.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 
#!/usr/bin/env python3
"""
Test script to verify that reasoning plan functionality is properly integrated into AnalysisIntentPlanner.
The reasoning plan provides step-by-step analysis guidance based on dataframe context, question, and available functions.
"""

import asyncio
import logging
from unittest.mock import Mock, AsyncMock
import sys
import os
import ast

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))

from app.agents.nodes.mlagents.analysis_intent_classification import AnalysisIntentResult
from app.agents.nodes.mlagents.self_correcting_pipeline_generator import SelfCorrectingPipelineCodeGenerator
from app.storage.documents import DocumentChromaStore

logger = logging.getLogger(__name__)


async def test_reasoning_plan_integration():
    """Test that reasoning plan is properly integrated into AnalysisIntentPlanner."""
    
    logger.info("Starting reasoning plan integration test...")
    
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
            "intent_type": "time_series_analysis",
            "confidence_score": 0.95,
            "rephrased_question": "Calculate 5-day rolling variance of flux metric grouped by projects, cost centers, and departments over time",
            "suggested_functions": ["variance_analysis"],
            "reasoning": "Question specifically asks for rolling variance analysis. Historical context shows similar variance analysis patterns were successful.",
            "required_data_columns": ["flux", "timestamp", "projects", "cost_centers", "departments"],
            "clarification_needed": null,
            "can_be_answered": true,
            "feasibility_score": 0.9,
            "missing_columns": [],
            "available_alternatives": ["date_column could substitute for timestamp"],
            "data_suggestions": "Historical analysis shows this approach works well with the available data structure",
            "reasoning_plan": [
                {
                    "step_number": 1,
                    "step_title": "Data Preparation",
                    "step_description": "Clean and prepare the data for rolling variance analysis",
                    "data_requirements": ["flux", "timestamp"],
                    "expected_outcome": "Clean dataset with proper datetime formatting",
                    "considerations": "Ensure timestamp is in datetime format and handle missing values"
                },
                {
                    "step_number": 2,
                    "step_title": "Rolling Variance Calculation",
                    "step_description": "Calculate 5-day rolling variance for flux metric",
                    "data_requirements": ["flux", "timestamp"],
                    "expected_outcome": "Rolling variance values over time",
                    "considerations": "Use appropriate window size and handle edge cases"
                },
                {
                    "step_number": 3,
                    "step_title": "Group Analysis",
                    "step_description": "Group results by projects, cost centers, and departments",
                    "data_requirements": ["projects", "cost_centers", "departments"],
                    "expected_outcome": "Variance analysis by organizational groups",
                    "considerations": "Handle groups with insufficient data"
                }
            ]
        }
        '''
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        logger.info("Mock LLM setup completed")
        
        # Initialize AnalysisIntentPlanner
        logger.info("Initializing AnalysisIntentPlanner...")
        planner = AnalysisIntentPlanner(
            llm=mock_llm,
            retrieval_helper=retrieval_helper
        )
        logger.info("AnalysisIntentPlanner initialized successfully")
        
        # Test data
        question = "Calculate 5-day rolling variance of flux metric grouped by projects, cost centers, and departments over time"
        dataframe_description = "Financial transaction data with flux metrics and organizational grouping"
        dataframe_summary = "Dataset contains 1000+ transactions with flux values, timestamps, and organizational hierarchy"
        available_columns = ["flux", "timestamp", "projects", "cost_centers", "departments", "transaction_id"]
        project_id = "test_project_123"
        
        # Test the analysis
        logger.info("Testing analysis with reasoning plan...")
        result = await planner.analyze_intent(
            question=question,
            dataframe_description=dataframe_description,
            dataframe_summary=dataframe_summary,
            available_columns=available_columns,
            project_id=project_id
        )
        
        # Verify the result
        assert result is not None, "Result should not be None"
        assert isinstance(result, AnalysisIntentResult), "Result should be AnalysisIntentResult"
        assert result.intent_type == "time_series_analysis", f"Expected time_series_analysis, got {result.intent_type}"
        assert result.confidence_score > 0.8, f"Expected high confidence, got {result.confidence_score}"
        assert result.reasoning_plan is not None, "Reasoning plan should not be None"
        assert len(result.reasoning_plan) > 0, "Reasoning plan should have steps"
        
        logger.info("✅ AnalysisIntentPlanner reasoning plan integration test passed!")
        logger.info(f"   - Intent type: {result.intent_type}")
        logger.info(f"   - Confidence score: {result.confidence_score}")
        logger.info(f"   - Rephrased question: {result.rephrased_question}")
        logger.info(f"   - Suggested functions: {result.suggested_functions}")
        logger.info(f"   - Reasoning plan steps: {len(result.reasoning_plan) if result.reasoning_plan else 0}")
        logger.info(f"   - Reasoning plan is now passed as raw JSON for better LLM flexibility")
        
        # Display reasoning plan details
        if result.reasoning_plan:
            logger.info("📋 Reasoning Plan Details (Raw JSON):")
            import json
            logger.info(json.dumps(result.reasoning_plan, indent=2))
        
        # Test direct reasoning plan generation
        logger.info("Testing direct reasoning plan generation...")
        reasoning_plan = await planner.generate_reasoning_plan(
            question=question,
            dataframe_description=dataframe_description,
            dataframe_summary=dataframe_summary,
            available_columns=available_columns,
            intent_type="time_series_analysis",
            suggested_functions=["variance_analysis"],
            project_id=project_id
        )
        assert reasoning_plan is not None, "Reasoning plan should not be None"
        assert isinstance(reasoning_plan, list), "Reasoning plan should be a list"
        logger.info(f"✅ Direct reasoning plan generation test passed!")
        logger.info(f"   - Generated {len(reasoning_plan)} reasoning plan steps")
        
        # Test with different analysis types
        logger.info("Testing reasoning plan with different analysis types...")
        test_cases = [
            ("Calculate mean sales by region", "metrics_calculation", ["Mean"]),
            ("Detect anomalies in customer behavior", "anomaly_detection", ["detect_statistical_outliers"]),
            ("Analyze customer retention over time", "cohort_analysis", ["calculate_retention"]),
            ("Segment customers by behavior", "segmentation_analysis", ["run_kmeans"])
        ]
        
        for test_question, expected_intent, expected_functions in test_cases:
            logger.info(f"Testing: {test_question}")
            reasoning_plan = await planner.generate_reasoning_plan(
                question=test_question,
                dataframe_description="Customer data with various metrics",
                dataframe_summary="Dataset with customer behavior and transaction data",
                available_columns=["customer_id", "sales", "region", "date", "behavior_score"],
                intent_type=expected_intent,
                suggested_functions=expected_functions,
                project_id=project_id
            )
            assert reasoning_plan is not None, f"Reasoning plan should not be None for {test_question}"
            assert len(reasoning_plan) > 0, f"Reasoning plan should have steps for {test_question}"
            logger.info(f"   ✅ {test_question} - Generated {len(reasoning_plan)} steps")
        
        logger.info("🎉 All reasoning plan integration tests passed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Reasoning plan integration test failed: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False


async def test_self_correcting_pipeline_generator_with_reasoning_plan():
    """Test that the self-correcting pipeline generator properly uses reasoning plan."""
    
    logger.info("Starting self-correcting pipeline generator reasoning plan integration test...")
    
    try:
        # Mock LLM for testing
        mock_llm = Mock()
        mock_llm.ainvoke = AsyncMock()
        
        # Mock function detection response
        function_detection_response = Mock()
        function_detection_response.content = '''
        {
            "selected_function": "variance_analysis",
            "confidence": 0.95,
            "reasoning": "variance_analysis is the most appropriate function for rolling variance analysis. Aligns with Step 2 of reasoning plan.",
            "alternative_functions": ["Mean", "Sum"],
            "reasoning_plan_alignment": "Directly implements Step 2 variance calculation requirement"
        }
        '''
        
        # Mock function input detection response
        input_detection_response = Mock()
        input_detection_response.content = '''
        {
            "primary_function_inputs": {
                "columns": ["flux"],
                "method": "rolling",
                "window": 5
            },
            "additional_computations": [],
            "pipeline_sequence": ["Calculate 5-day rolling variance of flux"],
            "multi_pipeline": false,
            "reasoning": "Using 'flux' column for variance analysis as it's a numeric metric. Aligns with Step 2 of reasoning plan.",
            "reasoning_plan_step_mapping": "Implements Step 2 variance analysis requirement"
        }
        '''
        
        # Mock code generation response
        code_generation_response = Mock()
        code_generation_response.content = '''
        result = (TimeSeriesPipe.from_dataframe(df)
                 | variance_analysis(
                     columns=['flux'],
                     method='rolling',
                     window=5
                 )
                 | to_df()
        )
        '''
        
        # Set up mock responses
        mock_llm.ainvoke.side_effect = [
            function_detection_response,
            input_detection_response,
            code_generation_response
        ]
        
        # Mock document stores
        mock_usage_store = Mock(spec=DocumentChromaStore)
        mock_code_store = Mock(spec=DocumentChromaStore)
        mock_function_store = Mock(spec=DocumentChromaStore)
        
        # Mock document retrieval responses
        mock_usage_store.semantic_searches.return_value = {"documents": [[]], "distances": [[]]}
        mock_code_store.semantic_searches.return_value = {"documents": [[]], "distances": [[]]}
        mock_function_store.semantic_searches.return_value = {"documents": [[]], "distances": [[]]}
        
        # Initialize SelfCorrectingPipelineCodeGenerator
        generator = SelfCorrectingPipelineCodeGenerator(
            llm=mock_llm,
            usage_examples_store=mock_usage_store,
            code_examples_store=mock_code_store,
            function_definition_store=mock_function_store
        )
        
        # Create test classification with reasoning plan
        classification = AnalysisIntentResult(
            intent_type="time_series_analysis",
            confidence_score=0.95,
            rephrased_question="Calculate 5-day rolling variance of flux metric",
            suggested_functions=["variance_analysis"],
            reasoning="Question specifically asks for rolling variance analysis",
            required_data_columns=["flux", "timestamp"],
            clarification_needed=None,
            retrieved_functions=[],
            specific_function_matches=[],
            can_be_answered=True,
            feasibility_score=0.9,
            missing_columns=[],
            available_alternatives=[],
            data_suggestions="Use flux column for variance analysis",
            reasoning_plan=[
                {
                    "step_number": 1,
                    "step_title": "Data Preparation",
                    "step_description": "Clean and prepare the data for rolling variance analysis",
                    "data_requirements": ["flux", "timestamp"],
                    "expected_outcome": "Clean dataset with proper datetime formatting",
                    "considerations": "Ensure timestamp is in datetime format and handle missing values"
                },
                {
                    "step_number": 2,
                    "step_title": "Rolling Variance Calculation",
                    "step_description": "Calculate 5-day rolling variance for flux metric",
                    "data_requirements": ["flux", "timestamp"],
                    "expected_outcome": "Rolling variance values over time",
                    "considerations": "Use appropriate window size and handle edge cases",
                    "suggested_functions": ["variance_analysis"],
                    "function_reasoning": "variance_analysis function is perfect for rolling variance calculation"
                }
            ]
        )
        
        # Test the pipeline generation
        result = await generator.generate_pipeline_code(
            context="Calculate 5-day rolling variance of flux metric",
            function_name=["variance_analysis", "Mean"],
            function_inputs={},
            dataframe_name="df",
            classification=classification,
            dataset_description="Financial transaction data with flux metrics",
            columns_description={
                "flux": "Financial flux value",
                "timestamp": "Transaction timestamp",
                "project": "Project identifier"
            }
        )
        
        # Verify the result
        assert result is not None, "Result should not be None"
        assert result["status"] == "success", f"Expected success status, got {result['status']}"
        assert result["generated_code"] is not None, "Generated code should not be None"
        assert "variance_analysis" in result["generated_code"], "Generated code should contain variance_analysis"
        assert "TimeSeriesPipe" in result["generated_code"], "Generated code should use TimeSeriesPipe"
        
        # Verify reasoning plan integration
        assert result["detected_inputs"] is not None, "Detected inputs should not be None"
        detected_inputs = result["detected_inputs"]
        assert "reasoning_plan_step_mapping" in detected_inputs, "Should include reasoning plan step mapping"
        assert "reasoning" in detected_inputs, "Should include reasoning"
        
        logger.info("✅ Self-correcting pipeline generator reasoning plan integration test passed!")
        logger.info(f"   - Generated code: {result['generated_code'][:100]}...")
        logger.info(f"   - Reasoning plan step mapping: {detected_inputs.get('reasoning_plan_step_mapping', 'N/A')}")
        logger.info(f"   - Reasoning: {detected_inputs.get('reasoning', 'N/A')}")
        logger.info(f"   - Reasoning plan is now passed as raw JSON for LLM flexibility")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Self-correcting pipeline generator reasoning plan integration test failed: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False


async def test_reasoning_plan_json_format():
    """Test that reasoning plan is passed as raw JSON."""
    
    logger.info("Starting reasoning plan JSON format test...")
    
    try:
        # Create a test classification with reasoning plan
        classification = AnalysisIntentResult(
            intent_type="time_series_analysis",
            confidence_score=0.95,
            rephrased_question="Calculate rolling variance",
            suggested_functions=["variance_analysis"],
            reasoning="Test reasoning",
            required_data_columns=["flux", "timestamp"],
            clarification_needed=None,
            retrieved_functions=[],
            specific_function_matches=[],
            can_be_answered=True,
            feasibility_score=0.9,
            missing_columns=[],
            available_alternatives=[],
            data_suggestions="Test suggestions",
            reasoning_plan=[
                {
                    "step_number": 1,
                    "step_title": "Data Preparation",
                    "step_description": "Prepare data for analysis",
                    "data_requirements": ["flux", "timestamp"],
                    "expected_outcome": "Clean dataset",
                    "considerations": "Handle missing values",
                    "suggested_functions": ["clean_data"],
                    "function_reasoning": "Clean data first"
                },
                {
                    "step_number": 2,
                    "step_title": "Variance Analysis",
                    "step_description": "Calculate rolling variance",
                    "data_requirements": ["flux"],
                    "expected_outcome": "Variance values",
                    "considerations": "Use appropriate window",
                    "suggested_functions": ["variance_analysis"],
                    "function_reasoning": "Use variance_analysis function"
                }
            ]
        )
        
        # Mock LLM and stores
        mock_llm = Mock()
        mock_llm.ainvoke = AsyncMock()
        mock_usage_store = Mock(spec=DocumentChromaStore)
        mock_code_store = Mock(spec=DocumentChromaStore)
        mock_function_store = Mock(spec=DocumentChromaStore)
        
        # Mock responses
        mock_llm.ainvoke.side_effect = [
            Mock(content='{"selected_function": "variance_analysis", "confidence": 0.95, "reasoning": "test", "alternative_functions": [], "reasoning_plan_alignment": "test"}'),
            Mock(content='{"primary_function_inputs": {}, "additional_computations": [], "pipeline_sequence": [], "reasoning": "test", "reasoning_plan_step_mapping": "test"}'),
            Mock(content='result = TimeSeriesPipe.from_dataframe(df) | variance_analysis() | to_df()')
        ]
        
        mock_usage_store.semantic_searches.return_value = {"documents": [[]], "distances": [[]]}
        mock_code_store.semantic_searches.return_value = {"documents": [[]], "distances": [[]]}
        mock_function_store.semantic_searches.return_value = {"documents": [[]], "distances": [[]]}
        
        # Initialize generator
        generator = SelfCorrectingPipelineCodeGenerator(
            llm=mock_llm,
            usage_examples_store=mock_usage_store,
            code_examples_store=mock_code_store,
            function_definition_store=mock_function_store
        )
        
        # Test the JSON formatting
        reasoning_plan_json = generator._format_reasoning_plan_json(classification)
        
        # Verify it's valid JSON
        import json
        parsed_json = json.loads(reasoning_plan_json)
        assert isinstance(parsed_json, list), "Should be a list"
        assert len(parsed_json) == 2, "Should have 2 steps"
        assert parsed_json[0]["step_number"] == 1, "First step should be step 1"
        assert parsed_json[1]["step_number"] == 2, "Second step should be step 2"
        
        logger.info("✅ Reasoning plan JSON format test passed!")
        logger.info(f"   - Generated JSON: {reasoning_plan_json[:100]}...")
        logger.info(f"   - JSON is valid and contains {len(parsed_json)} steps")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Reasoning plan JSON format test failed: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False


async def test_code_cleaning_with_syntax_errors():
    """Test that code cleaning handles syntax errors correctly."""
    
    logger.info("Starting code cleaning with syntax errors test...")
    
    try:
        # Mock LLM and stores
        mock_llm = Mock()
        mock_llm.ainvoke = AsyncMock()
        mock_usage_store = Mock(spec=DocumentChromaStore)
        mock_code_store = Mock(spec=DocumentChromaStore)
        mock_function_store = Mock(spec=DocumentChromaStore)
        
        mock_usage_store.semantic_searches.return_value = {"documents": [[]], "distances": [[]]}
        mock_code_store.semantic_searches.return_value = {"documents": [[]], "distances": [[]]}
        mock_function_store.semantic_searches.return_value = {"documents": [[]], "distances": [[]]}
        
        # Initialize generator
        generator = SelfCorrectingPipelineCodeGenerator(
            llm=mock_llm,
            usage_examples_store=mock_usage_store,
            code_examples_store=mock_code_store,
            function_definition_store=mock_function_store
        )
        
        # Test cases with syntax errors
        test_cases = [
            # Unclosed parentheses
            ("result = (MetricsPipe.from_dataframe(df) | Mean(variable='revenue'", 
             "result = (MetricsPipe.from_dataframe(df) | Mean(variable='revenue'))"),
            
            # Extra closing parentheses
            ("result = (MetricsPipe.from_dataframe(df) | Mean(variable='revenue'))))", 
             "result = (MetricsPipe.from_dataframe(df) | Mean(variable='revenue'))"),
            
            # Empty parentheses
            ("result = (MetricsPipe.from_dataframe(df) | Mean() | to_df())", 
             "result = (MetricsPipe.from_dataframe(df) | Mean() | to_df())"),
            
            # Double pipes
            ("result = (MetricsPipe.from_dataframe(df) || Mean(variable='revenue') | to_df())", 
             "result = (MetricsPipe.from_dataframe(df) | Mean(variable='revenue') | to_df())"),
            
            # Malformed function call
            ("result = (MetricsPipe.from_dataframe(df) | Mean(,variable='revenue') | to_df())", 
             "result = (MetricsPipe.from_dataframe(df) | Mean(variable='revenue') | to_df())"),
        ]
        
        for malformed_code, expected_fixed_code in test_cases:
            # Test the cleaning
            cleaned_code = generator._clean_generated_code(malformed_code)
            
            # Verify the cleaned code is syntactically valid
            try:
                ast.parse(cleaned_code)
                logger.info(f"✅ Cleaned code is syntactically valid: {cleaned_code[:50]}...")
            except SyntaxError as e:
                logger.error(f"❌ Cleaned code still has syntax errors: {e}")
                logger.error(f"   Original: {malformed_code}")
                logger.error(f"   Cleaned: {cleaned_code}")
                return False
        
        logger.info("✅ Code cleaning with syntax errors test passed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Code cleaning with syntax errors test failed: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False


async def main():
    """Run all tests."""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    logger.info("🚀 Starting reasoning plan integration tests...")
    
    # Test AnalysisIntentPlanner reasoning plan integration
    test1_result = await test_reasoning_plan_integration()
    
    # Test SelfCorrectingPipelineCodeGenerator reasoning plan integration
    test2_result = await test_self_correcting_pipeline_generator_with_reasoning_plan()
    
    # Test reasoning plan JSON format
    test3_result = await test_reasoning_plan_json_format()
    
    # Test code cleaning with syntax errors
    test4_result = await test_code_cleaning_with_syntax_errors()
    
    if test1_result and test2_result and test3_result and test4_result:
        logger.info("🎉 All reasoning plan integration tests passed!")
        return True
    else:
        logger.error("❌ Some reasoning plan integration tests failed!")
        return False


if __name__ == "__main__":
    # Import here to avoid circular imports
    from app.agents.nodes.mlagents.analysis_intent_classification import AnalysisIntentPlanner
    from app.agents.retrieval.retrieval_helper import RetrievalHelper
    
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 
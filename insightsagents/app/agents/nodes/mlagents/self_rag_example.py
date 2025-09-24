"""
Self-RAG Enhanced Analysis Intent Classification - Example Usage

This example demonstrates how to use the SelfRAGAnalysisIntentPlanner
with self-reflection and self-correction capabilities.
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser

# Import the self-RAG enhanced planner
from analysis_intent_classification_self_rag import SelfRAGAnalysisIntentPlanner

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockRetrievalHelper:
    """
    Mock retrieval helper for demonstration purposes.
    In production, this would be your actual retrieval helper.
    """
    
    def __init__(self):
        self.function_database = {
            "rolling_variance": {
                "function_name": "rolling_variance",
                "pipe_name": "TimeSeriesPipe",
                "description": "Calculate rolling variance over a specified window",
                "parameters": ["data_column", "window_size", "group_columns"],
                "category": "time_series_analysis"
            },
            "group_by": {
                "function_name": "group_by",
                "pipe_name": "MetricsPipe", 
                "description": "Group data by specified columns and calculate aggregations",
                "parameters": ["group_columns", "aggregation_functions"],
                "category": "aggregation"
            },
            "anomaly_detection": {
                "function_name": "anomaly_detection",
                "pipe_name": "AnomalyPipe",
                "description": "Detect anomalies using statistical methods",
                "parameters": ["data_column", "method", "threshold"],
                "category": "anomaly_detection"
            },
            "trend_analysis": {
                "function_name": "trend_analysis",
                "pipe_name": "TrendPipe",
                "description": "Analyze trends in time series data",
                "parameters": ["data_column", "time_column", "trend_type"],
                "category": "trend_analysis"
            }
        }
    
    async def get_function_definition_by_query(
        self, 
        query: str, 
        similarity_threshold: float = 0.3, 
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Mock function retrieval based on query similarity.
        """
        query_lower = query.lower()
        matching_functions = []
        
        for func_name, func_def in self.function_database.items():
            # Simple keyword matching for demonstration
            if any(keyword in query_lower for keyword in func_name.split('_')):
                matching_functions.append(func_def)
            elif any(keyword in query_lower for keyword in func_def['description'].lower().split()):
                matching_functions.append(func_def)
        
        return {
            "function_definitions": matching_functions[:top_k],
            "query": query,
            "similarity_threshold": similarity_threshold,
            "total_matches": len(matching_functions)
        }

async def demonstrate_self_rag_analysis():
    """
    Demonstrate the self-RAG enhanced analysis intent classification.
    """
    try:
        # Initialize the LLM
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1,
            max_tokens=2000
        )
        
        # Initialize the mock retrieval helper
        retrieval_helper = MockRetrievalHelper()
        
        # Initialize the self-RAG enhanced planner
        planner = SelfRAGAnalysisIntentPlanner(
            llm=llm,
            retrieval_helper=retrieval_helper,
            max_retries=3
        )
        
        # Example questions for testing
        test_questions = [
            "How does the 5-day rolling variance of flux change over time for each group?",
            "What are the trends in user engagement over the past 6 months?",
            "Identify any anomalies in the transaction data",
            "Calculate the average revenue per user by segment"
        ]
        
        # Sample dataframe context
        dataframe_context = {
            "dataframe_description": "Financial transaction data with user segments and time series metrics",
            "dataframe_summary": "Contains 100k+ transactions with columns: date, user_id, segment, flux, revenue, transaction_type",
            "available_columns": ["date", "user_id", "segment", "flux", "revenue", "transaction_type", "amount", "status"]
        }
        
        print("=" * 80)
        print("SELF-RAG ENHANCED ANALYSIS INTENT CLASSIFICATION DEMONSTRATION")
        print("=" * 80)
        
        for i, question in enumerate(test_questions, 1):
            print(f"\n{'='*20} TEST CASE {i} {'='*20}")
            print(f"Question: {question}")
            print("-" * 60)
            
            # Run the self-RAG enhanced analysis
            result = await planner.classify_intent_with_self_rag(
                question=question,
                dataframe_description=dataframe_context["dataframe_description"],
                dataframe_summary=dataframe_context["dataframe_summary"],
                available_columns=dataframe_context["available_columns"]
            )
            
            # Display results
            print(f"Rephrased Question: {result.get('rephrased_question', 'N/A')}")
            print(f"Intent Type: {result.get('intent_type', 'N/A')}")
            print(f"Confidence Score: {result.get('confidence_score', 0.0):.2f}")
            print(f"Can Be Answered: {result.get('can_be_answered', False)}")
            print(f"Feasibility Score: {result.get('feasibility_score', 0.0):.2f}")
            
            # Display reasoning plan
            reasoning_plan = result.get('reasoning_plan', [])
            if reasoning_plan:
                print(f"\nReasoning Plan ({len(reasoning_plan)} steps):")
                for step in reasoning_plan:
                    print(f"  {step.get('step_number', '?')}. {step.get('step_title', 'Unknown')}")
                    print(f"     {step.get('step_description', 'No description')}")
            
            # Display suggested functions
            suggested_functions = result.get('suggested_functions', [])
            if suggested_functions:
                print(f"\nSuggested Functions ({len(suggested_functions)}):")
                for func in suggested_functions:
                    print(f"  - {func}")
            
            # Display self-RAG metadata
            self_rag_metadata = result.get('self_rag_metadata', {})
            if self_rag_metadata:
                print(f"\nSelf-RAG Metadata:")
                print(f"  Total Assessments: {self_rag_metadata.get('total_assessments', 0)}")
                print(f"  Corrections Applied: {self_rag_metadata.get('corrections_applied', 0)}")
                
                # Step 1 metadata
                step1_metadata = self_rag_metadata.get('step1_metadata', {})
                if step1_metadata:
                    usefulness_assessment = step1_metadata.get('usefulness_assessment', {})
                    print(f"  Step 1 Usefulness: {usefulness_assessment.get('usefulness_score', 'N/A')}")
                    print(f"  Step 1 Correction Applied: {step1_metadata.get('correction_applied', False)}")
                
                # Step 2 metadata
                step2_metadata = self_rag_metadata.get('step2_metadata', {})
                if step2_metadata:
                    print(f"  Step 2 Total Assessments: {step2_metadata.get('total_assessments', 0)}")
                    print(f"  Step 2 Corrections Applied: {step2_metadata.get('corrections_applied', 0)}")
            
            # Display GRPO evaluation results
            evaluation = result.get('evaluation', {})
            if evaluation:
                print(f"\nGRPO Evaluation Results:")
                print(f"  Methodology: {evaluation.get('grpo_methodology', 'N/A')}")
                print(f"  Overall GRPO Score: {evaluation.get('overall_grpo_score', 0.0):.3f}")
                print(f"  GRPO Rank: {evaluation.get('grpo_rank', 'N/A')}")
                
                # Step metrics
                step_metrics = evaluation.get('step_metrics', {})
                if step_metrics:
                    print(f"  Total Steps: {step_metrics.get('total_steps', 0)}")
                    print(f"  Average Step Score: {step_metrics.get('average_step_score', 0.0):.3f}")
                    print(f"  Best Step Score: {step_metrics.get('best_step_score', 0.0):.3f}")
                    print(f"  Worst Step Score: {step_metrics.get('worst_step_score', 0.0):.3f}")
                
                # Quality dimensions
                quality_dimensions = evaluation.get('quality_dimensions', {})
                if quality_dimensions:
                    print(f"  Quality Dimensions:")
                    for dim, score in quality_dimensions.items():
                        print(f"    {dim.replace('_', ' ').title()}: {score:.3f}")
                
                # Self-RAG metrics
                self_rag_metrics = evaluation.get('self_rag_metrics', {})
                if self_rag_metrics:
                    print(f"  Self-RAG Metrics:")
                    print(f"    Total Assessments: {self_rag_metrics.get('total_assessments', 0)}")
                    print(f"    Corrections Applied: {self_rag_metrics.get('corrections_applied', 0)}")
                    print(f"    Correction Rate: {self_rag_metrics.get('correction_rate', 0.0):.3f}")
                    print(f"    Self-Reflection Effectiveness: {self_rag_metrics.get('self_reflection_effectiveness', 0.0):.3f}")
                
                # GRPO insights
                grpo_insights = evaluation.get('grpo_insights', {})
                if grpo_insights:
                    print(f"  GRPO Insights:")
                    strengths = grpo_insights.get('strengths', [])
                    if strengths:
                        print(f"    Strengths: {', '.join(strengths[:3])}")
                    
                    weaknesses = grpo_insights.get('weaknesses', [])
                    if weaknesses:
                        print(f"    Weaknesses: {', '.join(weaknesses[:3])}")
                    
                    recommendations = grpo_insights.get('recommendations', [])
                    if recommendations:
                        print(f"    Recommendations: {', '.join(recommendations[:2])}")
            
            print("\n" + "="*60)
        
        print("\n" + "="*80)
        print("DEMONSTRATION COMPLETED")
        print("="*80)
        
    except Exception as e:
        logger.error(f"Error in demonstration: {e}")
        print(f"Error: {e}")

async def demonstrate_self_correction():
    """
    Demonstrate the self-correction capabilities specifically.
    """
    try:
        print("\n" + "="*80)
        print("SELF-CORRECTION CAPABILITIES DEMONSTRATION")
        print("="*80)
        
        # Initialize components
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1)
        retrieval_helper = MockRetrievalHelper()
        planner = SelfRAGAnalysisIntentPlanner(llm=llm, retrieval_helper=retrieval_helper)
        
        # Test with a question that might need correction
        question = "What is the meaning of life?"  # This should trigger correction
        
        print(f"Testing with question: {question}")
        print("This question should trigger self-correction as it's not data analysis related.")
        
        result = await planner.classify_intent_with_self_rag(
            question=question,
            dataframe_description="Sample financial data",
            dataframe_summary="Contains transaction records",
            available_columns=["date", "amount", "category"]
        )
        
        # Check if correction was applied
        self_rag_metadata = result.get('self_rag_metadata', {})
        step1_metadata = self_rag_metadata.get('step1_metadata', {})
        
        print(f"\nCorrection Applied: {step1_metadata.get('correction_applied', False)}")
        print(f"Confidence Improvement: {step1_metadata.get('confidence_improvement', 0.0):.2f}")
        
        if step1_metadata.get('correction_applied', False):
            print("✓ Self-correction was successfully applied!")
        else:
            print("ℹ No correction was needed or applied.")
        
        print("="*80)
        
    except Exception as e:
        logger.error(f"Error in self-correction demonstration: {e}")
        print(f"Error: {e}")

async def demonstrate_grpo_evaluation():
    """
    Demonstrate the GRPO evaluation capabilities specifically.
    """
    try:
        print("\n" + "="*80)
        print("GRPO EVALUATION CAPABILITIES DEMONSTRATION")
        print("="*80)
        
        # Initialize components
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1)
        retrieval_helper = MockRetrievalHelper()
        planner = SelfRAGAnalysisIntentPlanner(llm=llm, retrieval_helper=retrieval_helper)
        
        # Test with a complex question that will generate multiple steps
        question = "Analyze the rolling variance trends and identify anomalies in the flux data over time"
        
        print(f"Testing GRPO evaluation with question: {question}")
        print("This will demonstrate step-by-step GRPO evaluation and overall scoring.")
        
        result = await planner.classify_intent_with_self_rag(
            question=question,
            dataframe_description="Financial transaction data with time series metrics",
            dataframe_summary="Contains 100k+ transactions with flux measurements over time",
            available_columns=["date", "flux", "group", "revenue", "transaction_type"]
        )
        
        # Display GRPO evaluation results
        evaluation = result.get('evaluation', {})
        if evaluation:
            print(f"\nGRPO Evaluation Results:")
            print(f"  Methodology: {evaluation.get('grpo_methodology', 'N/A')}")
            print(f"  Overall GRPO Score: {evaluation.get('overall_grpo_score', 0.0):.3f}")
            print(f"  GRPO Rank: {evaluation.get('grpo_rank', 'N/A')}")
            
            # Step-by-step evaluation
            step_evaluations = evaluation.get('step_evaluations', [])
            if step_evaluations:
                print(f"\nStep-by-Step GRPO Evaluation:")
                for i, step_eval in enumerate(step_evaluations, 1):
                    print(f"  Step {i}: {step_eval.get('step_title', 'Unknown')}")
                    print(f"    Overall Score: {step_eval.get('overall_step_score', 0.0):.3f}")
                    print(f"    GRPO Rank: {step_eval.get('grpo_rank', 'N/A')}")
                    
                    # Dimension scores
                    dimension_scores = step_eval.get('dimension_scores', {})
                    if dimension_scores:
                        print(f"    Dimension Scores:")
                        for dim, score in dimension_scores.items():
                            print(f"      {dim.replace('_', ' ').title()}: {score:.3f}")
                    
                    # Strengths and weaknesses
                    strengths = step_eval.get('strengths', [])
                    if strengths:
                        print(f"    Strengths: {', '.join(strengths[:2])}")
                    
                    weaknesses = step_eval.get('weaknesses', [])
                    if weaknesses:
                        print(f"    Weaknesses: {', '.join(weaknesses[:2])}")
            
            # Quality dimensions summary
            quality_dimensions = evaluation.get('quality_dimensions', {})
            if quality_dimensions:
                print(f"\nOverall Quality Dimensions:")
                for dim, score in quality_dimensions.items():
                    print(f"  {dim.replace('_', ' ').title()}: {score:.3f}")
            
            # GRPO insights
            grpo_insights = evaluation.get('grpo_insights', {})
            if grpo_insights:
                print(f"\nGRPO Insights:")
                recommendations = grpo_insights.get('recommendations', [])
                if recommendations:
                    print(f"  Recommendations:")
                    for rec in recommendations[:3]:
                        print(f"    - {rec}")
                
                improvement_priorities = grpo_insights.get('improvement_priorities', [])
                if improvement_priorities:
                    print(f"  Improvement Priorities:")
                    for priority in improvement_priorities[:3]:
                        print(f"    - {priority}")
        
        print("\n" + "="*80)
        print("GRPO EVALUATION DEMONSTRATION COMPLETED")
        print("="*80)
        
    except Exception as e:
        logger.error(f"Error in GRPO evaluation demonstration: {e}")
        print(f"Error: {e}")

if __name__ == "__main__":
    # Run the demonstrations
    asyncio.run(demonstrate_self_rag_analysis())
    asyncio.run(demonstrate_self_correction())
    asyncio.run(demonstrate_grpo_evaluation())

import logging
from typing import Dict, List, Any, Optional, Union, Tuple
from app.storage.documents import DocumentChromaStore
from app.agents.nodes.mlagents.analysis_intent_classification import AnalysisIntentPlanner, AnalysisIntentResult
from app.agents.nodes.mlagents.select_correcting_pipeline_generator import SelfCorrectingSelectPipeGenerator
import asyncio

logger = logging.getLogger("select-pipe-integration")

class AnalysisIntentWithSelectPipe:
    """
    Integration class that combines Analysis Intent Classification with SelectPipe generation.
    This class orchestrates the complete flow from intent classification to data selection.
    """
    
    def __init__(self, 
                 llm,
                 # Stores for intent classification
                 function_collection: DocumentChromaStore = None,
                 example_collection: DocumentChromaStore = None,
                 insights_collection: DocumentChromaStore = None,
                 # Stores for SelectPipe generation (can be the same or different)
                 select_usage_examples_store: DocumentChromaStore = None,
                 select_code_examples_store: DocumentChromaStore = None,
                 select_function_definition_store: DocumentChromaStore = None,
                 # Configuration
                 max_functions_to_retrieve: int = 10,
                 max_select_iterations: int = 3):
        """
        Initialize the integrated analysis intent and SelectPipe system
        
        Args:
            llm: Language model instance
            function_collection: ChromaDB collection for function definitions (intent classification)
            example_collection: ChromaDB collection for function examples (intent classification)
            insights_collection: ChromaDB collection for function insights (intent classification)
            select_usage_examples_store: ChromaDB store for SelectPipe usage examples
            select_code_examples_store: ChromaDB store for SelectPipe code examples
            select_function_definition_store: ChromaDB store for SelectPipe function definitions
            max_functions_to_retrieve: Maximum functions to retrieve for intent classification
            max_select_iterations: Maximum iterations for SelectPipe generation
        """
        self.llm = llm
        
        # Initialize Analysis Intent Planner
        self.intent_planner = AnalysisIntentPlanner(
            llm=llm,
            function_collection=function_collection,
            example_collection=example_collection,
            insights_collection=insights_collection,
            max_functions_to_retrieve=max_functions_to_retrieve
        )
        
        # Initialize SelectPipe Generator
        # Use the same stores if SelectPipe-specific stores are not provided
        self.select_generator = SelfCorrectingSelectPipeGenerator(
            llm=llm,
            usage_examples_store=select_usage_examples_store or example_collection,
            code_examples_store=select_code_examples_store or example_collection,
            function_definition_store=select_function_definition_store or function_collection,
            max_iterations=max_select_iterations
        )
    
    async def analyze_and_generate_select_code(self,
                                             question: str,
                                             dataframe_description: str,
                                             dataframe_summary: str,
                                             available_columns: List[str],
                                             engine_name: str = "engine",
                                             table_name: str = "df",
                                             project_id: Optional[str] = None,
                                             columns_description: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Complete analysis workflow: classify intent and generate SelectPipe code
        
        Args:
            question: User's natural language question
            dataframe_description: Description of the dataframe
            dataframe_summary: Summary of the dataframe
            available_columns: List of available columns in the dataframe
            engine_name: Name of the engine variable for SelectPipe
            table_name: Name of the table/dataframe for SelectPipe
            project_id: Optional project ID for retrieving historical questions and instructions
            columns_description: Optional dictionary mapping column names to descriptions
            
        Returns:
            Dictionary containing both intent classification and SelectPipe generation results
        """
        try:
            logger.info("Starting integrated analysis intent classification and SelectPipe generation")
            
            # STEP 1: Run Analysis Intent Classification
            logger.info("=== STEP 1: Analysis Intent Classification ===")
            intent_result = await self.intent_planner.classify_intent(
                question=question,
                dataframe_description=dataframe_description,
                dataframe_summary=dataframe_summary,
                available_columns=available_columns,
                project_id=project_id
            )
            
            logger.info(f"Intent classification completed:")
            logger.info(f"  - Intent Type: {intent_result.intent_type}")
            logger.info(f"  - Confidence: {intent_result.confidence_score}")
            logger.info(f"  - Can Be Answered: {intent_result.can_be_answered}")
            logger.info(f"  - Feasibility Score: {intent_result.feasibility_score}")
            logger.info(f"  - Reasoning Plan Steps: {len(intent_result.reasoning_plan) if intent_result.reasoning_plan else 0}")
            
            # STEP 2: Generate SelectPipe Code
            logger.info("=== STEP 2: SelectPipe Code Generation ===")
            select_result = await self.select_generator.generate_select_pipe_code(
                context=question,
                classification=intent_result,
                available_columns=available_columns,
                engine_name=engine_name,
                table_name=table_name,
                dataset_description=dataframe_description,
                columns_description=columns_description
            )
            
            logger.info(f"SelectPipe generation completed:")
            logger.info(f"  - Status: {select_result['status']}")
            logger.info(f"  - Iterations: {select_result['iterations']}")
            logger.info(f"  - Selection Strategy: {select_result['selection_strategy']}")
            
            # STEP 3: Combine Results
            logger.info("=== STEP 3: Combining Results ===")
            combined_result = self._combine_results(intent_result, select_result, question, available_columns)
            
            logger.info("Integrated analysis completed successfully")
            return combined_result
            
        except Exception as e:
            logger.error(f"Error in integrated analysis: {e}")
            return {
                "status": "error",
                "error": str(e),
                "intent_classification": None,
                "select_pipe_generation": None,
                "combined_analysis": None
            }
    
    def _combine_results(self, intent_result: AnalysisIntentResult, 
                        select_result: Dict[str, Any],
                        question: str,
                        available_columns: List[str]) -> Dict[str, Any]:
        """
        Combine intent classification and SelectPipe generation results
        
        Args:
            intent_result: Results from intent classification
            select_result: Results from SelectPipe generation
            question: Original user question
            available_columns: Available columns list
            
        Returns:
            Combined results dictionary
        """
        # Extract key information
        can_proceed = intent_result.can_be_answered and select_result["status"] == "success"
        
        # Create analysis summary
        analysis_summary = {
            "question": question,
            "can_be_analyzed": can_proceed,
            "intent_confidence": intent_result.confidence_score,
            "data_feasibility": intent_result.feasibility_score,
            "total_columns_available": len(available_columns),
            "columns_selected": len(select_result.get("required_columns", [])),
            "analysis_complexity": self._assess_analysis_complexity(intent_result, select_result)
        }
        
        # Create recommendations
        recommendations = self._generate_recommendations(intent_result, select_result)
        
        # Create next steps
        next_steps = self._generate_next_steps(intent_result, select_result, can_proceed)
        
        return {
            "status": "success" if can_proceed else "partial_success",
            "analysis_summary": analysis_summary,
            "intent_classification": {
                "intent_type": intent_result.intent_type,
                "confidence_score": intent_result.confidence_score,
                "rephrased_question": intent_result.rephrased_question,
                "suggested_functions": intent_result.suggested_functions,
                "required_data_columns": intent_result.required_data_columns,
                "can_be_answered": intent_result.can_be_answered,
                "feasibility_score": intent_result.feasibility_score,
                "missing_columns": intent_result.missing_columns,
                "available_alternatives": intent_result.available_alternatives,
                "reasoning_plan": intent_result.reasoning_plan,
                "reasoning": getattr(intent_result, 'reasoning', 'No reasoning available')
            },
            "select_pipe_generation": {
                "status": select_result["status"],
                "generated_code": select_result["generated_code"],
                "selection_strategy": select_result["selection_strategy"],
                "data_selection_steps": select_result["data_selection_steps"],
                "iterations": select_result["iterations"],
                "reasoning": select_result["reasoning"]
            },
            "recommendations": recommendations,
            "next_steps": next_steps,
            "combined_code": self._generate_combined_code_example(intent_result, select_result),
            "metadata": {
                "intent_iterations": 1,  # Intent classification typically runs once
                "select_iterations": select_result["iterations"],
                "total_processing_steps": 2,
                "analysis_timestamp": self._get_timestamp()
            }
        }
    
    def _assess_analysis_complexity(self, intent_result: AnalysisIntentResult, 
                                  select_result: Dict[str, Any]) -> str:
        """Assess the overall complexity of the analysis"""
        factors = 0
        
        # Intent complexity factors
        if intent_result.intent_type in ["cohort_analysis", "funnel_analysis", "risk_analysis"]:
            factors += 2
        elif intent_result.intent_type in ["segmentation_analysis", "anomaly_detection"]:
            factors += 1
        
        # Reasoning plan complexity
        if intent_result.reasoning_plan and len(intent_result.reasoning_plan) > 3:
            factors += 1
        
        # Data selection complexity
        if len(select_result.get("data_selection_steps", [])) > 2:
            factors += 1
        
        # Column complexity
        if len(select_result.get("required_columns", [])) > 10:
            factors += 1
        
        if factors >= 4:
            return "high"
        elif factors >= 2:
            return "medium"
        else:
            return "low"
    
    def _generate_recommendations(self, intent_result: AnalysisIntentResult, 
                                select_result: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on the analysis results"""
        recommendations = []
        
        # Intent-based recommendations
        if intent_result.confidence_score < 0.7:
            recommendations.append("Low confidence in intent classification. Consider rephrasing the question for better accuracy.")
        
        if intent_result.feasibility_score < 0.6:
            recommendations.append("Data feasibility is low. Review missing columns and consider data enrichment.")
        
        if intent_result.missing_columns:
            recommendations.append(f"Missing columns detected: {', '.join(intent_result.missing_columns)}. Consider data sources that include these columns.")
        
        # SelectPipe-based recommendations
        if select_result["status"] != "success":
            recommendations.append("SelectPipe generation was not fully successful. Review the generated code and make manual adjustments if needed.")
        
        if select_result["iterations"] > 2:
            recommendations.append("SelectPipe generation required multiple iterations. The generated code may need validation.")
        
        # Combined recommendations
        complexity = self._assess_analysis_complexity(intent_result, select_result)
        if complexity == "high":
            recommendations.append("This is a complex analysis. Consider breaking it down into smaller, focused analyses.")
        
        # Data quality recommendations
        if len(select_result.get("required_columns", [])) < 3:
            recommendations.append("Limited number of columns selected. Consider if additional columns might enhance the analysis.")
        
        return recommendations
    
    def _generate_next_steps(self, intent_result: AnalysisIntentResult, 
                           select_result: Dict[str, Any], 
                           can_proceed: bool) -> List[str]:
        """Generate next steps based on the analysis results"""
        next_steps = []
        
        if can_proceed:
            next_steps.append("Execute the generated SelectPipe code to prepare the data subset.")
            next_steps.append("Run the analysis pipeline using the suggested functions from intent classification.")
            
            if intent_result.reasoning_plan:
                next_steps.append(f"Follow the {len(intent_result.reasoning_plan)}-step reasoning plan for comprehensive analysis.")
            
            next_steps.append("Validate results and iterate if necessary.")
            
        else:
            if not intent_result.can_be_answered:
                next_steps.append("Address data feasibility issues before proceeding with analysis.")
                if intent_result.missing_columns:
                    next_steps.append("Obtain or derive the missing columns needed for analysis.")
            
            if select_result["status"] != "success":
                next_steps.append("Fix SelectPipe code generation issues or create manual column selection.")
            
            next_steps.append("Re-run the analysis workflow after addressing the identified issues.")
        
        next_steps.append("Consider data quality assessment and validation of selected columns.")
        next_steps.append("Document the analysis approach and results for future reference.")
        
        return next_steps
    
    def _generate_combined_code_example(self, intent_result: AnalysisIntentResult, 
                                      select_result: Dict[str, Any]) -> Optional[str]:
        """Generate a combined code example showing SelectPipe + Analysis pipeline"""
        if select_result["status"] != "success" or not select_result.get("generated_code"):
            return None
        
        try:
            select_code = select_result["generated_code"]
            
            # Extract variable name from SelectPipe code (usually 'result')
            import re
            var_match = re.search(r'^(\w+)\s*=', select_code.strip())
            data_var = var_match.group(1) if var_match else "selected_data"
            
            # Generate analysis pipeline code based on intent
            analysis_code = self._generate_analysis_pipeline_code(intent_result, data_var)
            
            combined_code = f"""# Step 1: Data Selection using SelectPipe
{select_code}

# Step 2: Analysis Pipeline based on Intent Classification
{analysis_code}"""
            
            return combined_code
            
        except Exception as e:
            logger.warning(f"Error generating combined code example: {e}")
            return None
    
    def _generate_analysis_pipeline_code(self, intent_result: AnalysisIntentResult, 
                                       data_var: str) -> str:
        """Generate analysis pipeline code based on intent classification"""
        intent_type = intent_result.intent_type
        suggested_functions = intent_result.suggested_functions[:2]  # Take first 2 functions
        
        if not suggested_functions:
            return f"# Analysis pipeline code would be generated here based on {intent_type}"
        
        # Generate pipeline based on intent type and suggested functions
        pipeline_templates = {
            "metrics_calculation": "MetricsPipe",
            "time_series_analysis": "TimeSeriesPipe", 
            "trend_analysis": "TrendsPipe",
            "cohort_analysis": "CohortPipe",
            "segmentation_analysis": "SegmentPipe",
            "funnel_analysis": "CohortPipe",
            "risk_analysis": "RiskPipe",
            "anomaly_detection": "AnomalyPipe",
            "operations_analysis": "OperationsPipe"
        }
        
        pipe_type = pipeline_templates.get(intent_type, "MetricsPipe")
        
        # Generate sample pipeline code
        if len(suggested_functions) >= 2:
            analysis_code = f"""analysis_result = (
    {pipe_type}.from_dataframe({data_var})
    | {suggested_functions[0]}()  # Primary analysis function
    | {suggested_functions[1]}()  # Secondary analysis function
    ).to_df()"""
        else:
            analysis_code = f"""analysis_result = (
    {pipe_type}.from_dataframe({data_var})
    | {suggested_functions[0]}()  # Primary analysis function
    ).to_df()"""
        
        return analysis_code
    
    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().isoformat()

# Convenience function for easy usage
async def analyze_intent_and_generate_select_pipe(
    question: str,
    dataframe_description: str,
    dataframe_summary: str,
    available_columns: List[str],
    llm,
    # ChromaDB stores
    function_collection: DocumentChromaStore = None,
    example_collection: DocumentChromaStore = None,
    insights_collection: DocumentChromaStore = None,
    # Optional parameters
    engine_name: str = "engine",
    table_name: str = "df",
    project_id: Optional[str] = None,
    columns_description: Optional[Dict[str, str]] = None,
    # SelectPipe specific stores (optional)
    select_usage_examples_store: DocumentChromaStore = None,
    select_code_examples_store: DocumentChromaStore = None,
    select_function_definition_store: DocumentChromaStore = None
) -> Dict[str, Any]:
    """
    Convenience function to run the complete analysis workflow
    
    Args:
        question: User's natural language question
        dataframe_description: Description of the dataframe
        dataframe_summary: Summary of the dataframe  
        available_columns: List of available columns
        llm: Language model instance
        function_collection: ChromaDB collection for function definitions
        example_collection: ChromaDB collection for examples
        insights_collection: ChromaDB collection for insights
        engine_name: Engine variable name for SelectPipe
        table_name: Table name for SelectPipe
        project_id: Optional project ID
        columns_description: Optional column descriptions
        select_usage_examples_store: Optional SelectPipe usage examples store
        select_code_examples_store: Optional SelectPipe code examples store
        select_function_definition_store: Optional SelectPipe function definitions store
        
    Returns:
        Combined analysis results
    """
    analyzer = AnalysisIntentWithSelectPipe(
        llm=llm,
        function_collection=function_collection,
        example_collection=example_collection,
        insights_collection=insights_collection,
        select_usage_examples_store=select_usage_examples_store,
        select_code_examples_store=select_code_examples_store,
        select_function_definition_store=select_function_definition_store
    )
    
    return await analyzer.analyze_and_generate_select_code(
        question=question,
        dataframe_description=dataframe_description,
        dataframe_summary=dataframe_summary,
        available_columns=available_columns,
        engine_name=engine_name,
        table_name=table_name,
        project_id=project_id,
        columns_description=columns_description
    )

# Example usage
if __name__ == "__main__":
    import asyncio
    from unittest.mock import Mock
    
    async def test_integration():
        # Mock LLM and stores
        mock_llm = Mock()
        mock_store = Mock()
        mock_store.semantic_searches = Mock(return_value={"documents": [[]], "distances": [[]]})
        
        # Sample data
        question = "Analyze customer purchase patterns by region over time"
        dataframe_description = "Customer transaction data with demographics and purchase history"
        dataframe_summary = "Contains 100,000 customer transactions from 2023-2024"
        available_columns = [
            "customer_id", "customer_name", "customer_age", "region", "country",
            "purchase_date", "product_id", "product_name", "product_category",
            "purchase_amount", "quantity", "discount_applied", "payment_method",
            "customer_segment", "lifetime_value", "last_purchase_date"
        ]
        columns_description = {
            "customer_id": "Unique customer identifier",
            "purchase_amount": "Total purchase amount in USD", 
            "region": "Customer's geographical region",
            "purchase_date": "Date of purchase transaction"
        }
        
        # Run integrated analysis
        result = await analyze_intent_and_generate_select_pipe(
            question=question,
            dataframe_description=dataframe_description,
            dataframe_summary=dataframe_summary,
            available_columns=available_columns,
            llm=mock_llm,
            function_collection=mock_store,
            example_collection=mock_store,
            insights_collection=mock_store,
            engine_name="engine",
            table_name="customers",
            columns_description=columns_description
        )
        
        print("=== INTEGRATION TEST RESULTS ===")
        print(f"Status: {result['status']}")
        print(f"Can be analyzed: {result['analysis_summary']['can_be_analyzed']}")
        print(f"Intent type: {result['intent_classification']['intent_type']}")
        print(f"Selection strategy: {result['select_pipe_generation']['selection_strategy']}")
        print(f"Analysis complexity: {result['analysis_summary']['analysis_complexity']}")
        print(f"Recommendations: {len(result['recommendations'])}")
        print(f"Next steps: {len(result['next_steps'])}")
        
        if result['select_pipe_generation']['generated_code']:
            print("\n=== GENERATED SELECTPIPE CODE ===")
            print(result['select_pipe_generation']['generated_code'])
        
        if result['combined_code']:
            print("\n=== COMBINED CODE EXAMPLE ===")
            print(result['combined_code'])
        
        return "Integration test completed successfully!"
    
    # Run the test
    test_result = asyncio.run(test_integration())
    print(f"\nOverall result: {test_result}")
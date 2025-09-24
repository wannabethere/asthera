"""
Enhanced Function Retrieval Service

This module provides an enhanced function retrieval system that efficiently matches
analysis functions to specific steps in reasoning plans using ChromaDB and LLM-based matching.

Key improvements:
1. Uses RetrievalHelper for comprehensive function retrieval
2. Uses InputExtractor for intelligent parameter extraction
3. Uses comprehensive definitions for LLM calls
4. Stores initialized outside of retrieval helper
"""

import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from langchain.prompts import PromptTemplate
from langchain_core.output_parsers.string import StrOutputParser
from langfuse.decorators import observe
from pydantic import BaseModel

from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.agents.nodes.mlagents.function_input_extractor import (
    BaseInputExtractor,
    create_input_extractor
)

logger = logging.getLogger("enhanced-function-retrieval-service")


class FunctionMatch(BaseModel):
    """Model for function match results"""
    function_name: str
    pipe_name: str
    description: str
    usage_description: str
    relevance_score: float
    reasoning: str
    category: str = "unknown"
    function_definition: Optional[Dict[str, Any]] = None
    examples: Optional[List[Dict[str, Any]]] = None
    instructions: Optional[List[Dict[str, Any]]] = None
    examples_store: Optional[List[Dict[str, Any]]] = None
    historical_rules: Optional[List[Dict[str, Any]]] = None
    extracted_parameters: Optional[Dict[str, Any]] = None


class StepFunctionMatch(BaseModel):
    """Model for step-function matching results"""
    step_number: int
    step_title: str
    matched_functions: List[FunctionMatch]
    total_relevance_score: float


class EnhancedFunctionRetrievalResult(BaseModel):
    """Result model for enhanced function retrieval"""
    step_matches: Dict[int, List[Dict[str, Any]]]
    total_functions_retrieved: int
    total_steps_covered: int
    average_relevance_score: float
    confidence_score: float
    reasoning: str
    fallback_used: bool = False


class EnhancedFunctionRetrievalService:
    """
    Enhanced function retrieval service that efficiently matches functions to analysis steps
    using RetrievalHelper, InputExtractor, and comprehensive definitions.
    """
    
    def __init__(
        self,
        llm, 
        retrieval_helper: RetrievalHelper,
        comprehensive_registry=None,
        example_collection=None,
        function_collection=None,
        insights_collection=None
    ):
        """
        Initialize the Enhanced Function Retrieval Service
        
        Args:
            llm: LangChain LLM instance
            retrieval_helper: RetrievalHelper instance for accessing function definitions
            comprehensive_registry: Enhanced comprehensive registry for function search
            example_collection: Examples collection for input extraction
            function_collection: Function collection for input extraction
            insights_collection: Insights collection for input extraction
        """
        self.llm = llm
        self.retrieval_helper = retrieval_helper
        self.comprehensive_registry = comprehensive_registry
        self.example_collection = example_collection
        self.function_collection = function_collection
        self.insights_collection = insights_collection
        
        # Initialize input extractor
        self.input_extractor = create_input_extractor(
            analysis_type="general_analysis",
            llm=llm,
            example_collection=example_collection,
            function_collection=function_collection,
            insights_collection=insights_collection
            )
    
    async def retrieve_and_match_functions(
        self,
        reasoning_plan: List[Dict[str, Any]],
        question: str,
        rephrased_question: str,
        dataframe_description: str,
        dataframe_summary: str,
        available_columns: List[str],
        project_id: Optional[str] = None
    ) -> EnhancedFunctionRetrievalResult:
        """
        Main method to retrieve and match functions to analysis steps
        
        Args:
            reasoning_plan: The reasoning plan from Step 1
            question: Original user question
            rephrased_question: Rephrased question from Step 1
            dataframe_description: Description of the dataframe
            dataframe_summary: Summary of the dataframe
            available_columns: List of available columns
            project_id: Optional project ID
            
        Returns:
            EnhancedFunctionRetrievalResult with step-function matches
        """
        try:
            logger.info("Starting enhanced function retrieval and matching...")
            
            # Step 1: Fetch relevant functions using comprehensive registry
            relevant_functions = await self._fetch_relevant_functions_comprehensive(
                reasoning_plan=reasoning_plan,
                question=question,
                rephrased_question=rephrased_question,
                dataframe_description=dataframe_description,
                dataframe_summary=dataframe_summary,
                available_columns=available_columns,
                project_id=project_id
            )
            
            if not relevant_functions:
                logger.warning("No relevant functions found")
                return self._create_empty_result("No relevant functions found")
            
            # Step 2: Enrich functions with comprehensive context
            enriched_functions = []
            for func in relevant_functions:
                enriched_func = await self._enrich_function_with_comprehensive_context(
                    function_data=func,
                    question=question,
                    dataframe_description=dataframe_description,
                    available_columns=available_columns,
                    project_id=project_id
                )
                enriched_functions.append(enriched_func)
            
            # Step 3: Match functions to steps using LLM with comprehensive definitions
            step_function_matches = await self._match_functions_to_steps_with_comprehensive_llm(
                reasoning_plan=reasoning_plan,
                relevant_functions=enriched_functions,
                question=question,
                dataframe_description=dataframe_description,
                available_columns=available_columns
            )
            
            # Step 4: Calculate metrics and create result
            result = self._create_result_from_matches(
                step_function_matches=step_function_matches,
                total_functions=len(enriched_functions),
                reasoning_plan=reasoning_plan,
                fallback_used=False
            )
            
            logger.info(f"Enhanced function retrieval completed successfully")
            logger.info(f"  - Retrieved {len(relevant_functions)} functions")
            logger.info(f"  - Matched to {len(step_function_matches)} steps")
            logger.info(f"  - Average relevance score: {result.average_relevance_score:.2f}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in enhanced function retrieval: {e}")
            return self._create_empty_result(f"Error: {str(e)}", fallback_used=True)
    
    async def _fetch_relevant_functions_comprehensive(
        self,
        reasoning_plan: List[Dict[str, Any]],
        question: str,
        rephrased_question: str,
        dataframe_description: str,
        dataframe_summary: str,
        available_columns: List[str],
        project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch relevant functions using comprehensive registry and retrieval helper.
        
        Args:
            reasoning_plan: The reasoning plan from Step 1
            question: Original user question
            rephrased_question: Rephrased question from Step 1
            dataframe_description: Description of the dataframe
            dataframe_summary: Summary of the dataframe
            available_columns: List of available columns
            project_id: Optional project ID
            
        Returns:
            List of relevant function definitions
        """
        try:
            relevant_functions = []
            
            # Create a comprehensive query that includes the reasoning plan
            plan_context = "\n".join([
                f"Step {step.get('step_number', i+1)}: {step.get('step_title', '')} - {step.get('step_description', '')}"
                for i, step in enumerate(reasoning_plan)
            ])
            
            # Combine all context for a comprehensive search
            comprehensive_query = f"""
            User Question: {question}
            Rephrased Question: {rephrased_question}
            Dataframe Description: {dataframe_description}
            Available Columns: {', '.join(available_columns)}
            
            Analysis Plan:
            {plan_context}
            """
            
            logger.info(f"Fetching functions with comprehensive query")
            
            # Try comprehensive registry first if available
            if self.comprehensive_registry:
                try:
                    # Use comprehensive registry for enhanced search
                    search_results = self.comprehensive_registry.search_functions(
                        query=comprehensive_query,
                        n_results=10,
                        has_examples=True,
                        has_instructions=True
                    )
                    
                    if search_results:
                        for result in search_results:
                            if isinstance(result, dict):
                                # Get comprehensive function data by name
                                function_name = result.get('function_name', '')
                                if function_name:
                                    comprehensive_data = self.comprehensive_registry.get_function_by_name(function_name)
                                    if comprehensive_data:
                                        # Try to get actual source code from the actual Python files
                                        try:
                                            actual_source_code = self._get_actual_source_code(function_name)
                                            if actual_source_code:
                                                comprehensive_data['source_code'] = actual_source_code
                                                logger.info(f"Retrieved actual source code for {function_name}")
                                        except Exception as e:
                                            logger.warning(f"Failed to get source code for {function_name}: {e}")
                                        
                                        # Parse and format function definition properly
                                        merged_result = {**result, **comprehensive_data}
                                        
                                        # Fix function definition formatting
                                        if 'function_definition' in merged_result:
                                            merged_result['function_definition'] = self._format_function_definition(merged_result['function_definition'])
                                        
                                        relevant_functions.append(merged_result)
                                        logger.info(f"Found comprehensive function: {function_name}")
                                    else:
                                        relevant_functions.append(result)
                                        logger.info(f"Found function from comprehensive registry: {function_name}")
                    
                except Exception as e:
                    logger.warning(f"Comprehensive registry search failed: {e}")
            
            # Fallback to retrieval helper if comprehensive registry fails or returns no results
            if not relevant_functions and self.retrieval_helper:
                search_queries = [
                    comprehensive_query,
                    rephrased_question,
                    plan_context,
                    question
                ]
                for query in search_queries:
                    try:
                        # Use the retrieval helper to get function definitions
                        function_result = await self.retrieval_helper.get_function_definition_by_query(
                            query=query,
                                    similarity_threshold=0.6,  # Lower threshold to get more candidates
                                    top_k=5
                        )
                        
                        if function_result and function_result.get("function_definition"):
                            relevant_functions.append(function_result["function_definition"])
                            logger.info(f"Found function from retrieval helper: {function_result['function_definition'].get('function_name', 'unknown')}")
                        
                    except Exception as e:
                        logger.warning(f"Failed to fetch functions with query '{query[:50]}...': {e}")
                        continue
            
            # Remove duplicates based on function name
            unique_functions = {}
            for func in relevant_functions:
                func_name = func.get("function_name", "")
                if func_name and func_name not in unique_functions:
                    unique_functions[func_name] = func
            
                    logger.info(f"Retrieved {len(unique_functions)} unique functions")
            return list(unique_functions.values())
            
        except Exception as e:
                    logger.error(f"Retrieval helper search failed: {e}")
            
        except Exception as e:
            logger.error(f"Error fetching functions: {e}")
            return []
    
    async def _enrich_function_with_comprehensive_context(
        self,
        function_data: Dict[str, Any],
        question: str,
        dataframe_description: str,
        available_columns: List[str],
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enrich function data with comprehensive context using retrieval helper and input extractor.
        
        Args:
            function_data: Function data dictionary
            question: Original user question
            dataframe_description: Description of the dataframe
            available_columns: List of available columns
            project_id: Optional project ID for instructions
            
        Returns:
            Enriched function data
        """
        function_name = function_data.get("function_name", "")
        if not function_name:
            return function_data
        
        try:
            # Check if we already have comprehensive data from the registry
            has_comprehensive_data = any(key in function_data for key in [
                'examples', 'instructions', 'code_snippets', 'source_code', 
                'function_definition', 'required_params', 'optional_params'
            ])
            
            if has_comprehensive_data:
                logger.info(f"Function {function_name} already has comprehensive data, skipping enrichment")
                # Still extract parameters if not present
                if not function_data.get('extracted_parameters') and self.input_extractor:
                    try:
                        context = f"Question: {question}\nDataframe: {dataframe_description}"
                        extracted_parameters = self.input_extractor.extract_inputs(
                            context=context,
                            function_name=function_name,
                            columns=available_columns,
                            dataframe_description={"schema": dataframe_description} if isinstance(dataframe_description, str) else dataframe_description
                        )
                        function_data['extracted_parameters'] = extracted_parameters
                    except Exception as e:
                        logger.warning(f"Failed to extract parameters for {function_name}: {e}")
                
                return function_data
            
            # If we don't have comprehensive data, try to get it from retrieval helper
            if not self.retrieval_helper:
                return function_data
            
            # Retrieve examples, instructions, and insights in parallel
            examples_task = self.retrieval_helper.get_function_examples(
                function_name=function_name,
                similarity_threshold=0.6,
                top_k=5
            )
            
            insights_task = self.retrieval_helper.get_function_insights(
                function_name=function_name,
                similarity_threshold=0.6,
                top_k=3
            )
            
            instructions_task = None
            if project_id:
                instructions_task = self.retrieval_helper.get_instructions(
                    query=question,
                    project_id=project_id,
                    similarity_threshold=0.7,
                    top_k=5
                )
            
            # Wait for all tasks to complete
            examples_result = await examples_task
            insights_result = await insights_task
            instructions_result = await instructions_task if instructions_task else {"instructions": []}
            
            # Extract examples
            examples = []
            if examples_result and not examples_result.get("error"):
                examples = examples_result.get("examples", [])
            
            # Extract insights (used as examples store for historical patterns)
            examples_store = []
            if insights_result and not insights_result.get("error"):
                examples_store = insights_result.get("insights", [])
            
            # Extract instructions
            instructions = []
            if instructions_result and not instructions_result.get("error"):
                instructions = instructions_result.get("instructions", [])
            
            # Get historical rules
            historical_rules = await self._get_historical_rules(function_name, question)
            
            # Extract parameters using input extractor
            extracted_parameters = None
            if self.input_extractor:
                try:
                    context = f"Question: {question}\nDataframe: {dataframe_description}"
                    extracted_parameters = self.input_extractor.extract_inputs(
                        context=context,
                        function_name=function_name,
                        columns=available_columns,
                        dataframe_description={"schema": dataframe_description} if isinstance(dataframe_description, str) else dataframe_description
                    )
                except Exception as e:
                    logger.warning(f"Failed to extract parameters for {function_name}: {e}")
            
            # Update function data
            function_data.update({
                "examples": examples,
                "instructions": instructions,
                "examples_store": examples_store,
                "historical_rules": historical_rules,
                "extracted_parameters": extracted_parameters
            })
            
            logger.info(f"Enriched {function_name} with {len(examples)} examples, {len(instructions)} instructions, {len(examples_store)} insights, {len(historical_rules)} historical rules")
            
        except Exception as e:
            logger.error(f"Error enriching function {function_name}: {e}")
            # Return original data if enrichment fails
            function_data.update({
                "examples": [],
                "instructions": [],
                "examples_store": [],
                "historical_rules": [],
                "extracted_parameters": None
            })
    
        return function_data
    
    def _format_function_definition(self, function_definition: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format function definition to ensure parameters are properly structured as JSON objects.
        
        Args:
            function_definition: Raw function definition dictionary
            
        Returns:
            Properly formatted function definition
        """
        if not function_definition:
            return {}
        
        formatted_definition = {}
        
        # Handle parameters
        if 'parameters' in function_definition:
            parameters = function_definition['parameters']
            if isinstance(parameters, dict):
                formatted_params = {}
                for param_name, param_info in parameters.items():
                    if isinstance(param_info, str):
                        # Parse string parameter info
                        formatted_params[param_name] = {
                            "type": "Any",
                            "description": param_info,
                            "required": True
                        }
                    elif isinstance(param_info, dict):
                        # Already properly formatted
                        formatted_params[param_name] = param_info
                    else:
                        # Convert to string and create basic structure
                        formatted_params[param_name] = {
                            "type": "Any",
                            "description": str(param_info),
                            "required": True
                        }
                formatted_definition['parameters'] = formatted_params
            else:
                formatted_definition['parameters'] = parameters
        
        # Handle other fields
        for key, value in function_definition.items():
            if key != 'parameters':
                formatted_definition[key] = value
        
        return formatted_definition
    
    def _get_actual_source_code(self, function_name: str) -> Optional[str]:
        """
        Get actual source code from Python files for a given function name.
        
        Args:
            function_name: Name of the function to get source code for
            
        Returns:
            Source code string if found, None otherwise
        """
        try:
            import inspect
            import sys
            from pathlib import Path
            
            # Map function names to their modules
            function_module_map = {
                'calculate_retention': 'insightsagents.app.tools.mltools.cohortanalysistools',
                'form_time_cohorts': 'insightsagents.app.tools.mltools.cohortanalysistools',
                'form_behavioral_cohorts': 'insightsagents.app.tools.mltools.cohortanalysistools',
                'calculate_lifetime_value': 'insightsagents.app.tools.mltools.cohortanalysistools',
                'calculate_cohort_size': 'insightsagents.app.tools.mltools.cohortanalysistools',
                'variance_analysis': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_variance': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'anomaly_detection': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'outlier_detection': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'z_score_analysis': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'iqr_analysis': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'isolation_forest': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'one_class_svm': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'dbscan_clustering': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'kmeans_clustering': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'hierarchical_clustering': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'pca_analysis': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'tsne_analysis': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'umap_analysis': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'distribution_analysis': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'statistical_summary': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'correlation_analysis': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'trend_analysis': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'seasonality_analysis': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'stationarity_test': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'arima_forecasting': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'exponential_smoothing': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'prophet_forecasting': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'lstm_forecasting': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'moving_average': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'exponential_moving_average': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'weighted_moving_average': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'bollinger_bands': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rsi_analysis': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'macd_analysis': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'stochastic_oscillator': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'williams_r': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'cci_analysis': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'atr_analysis': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'adx_analysis': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'parabolic_sar': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'ichimoku_analysis': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'fibonacci_retracement': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'pivot_points': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'support_resistance': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'trend_lines': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'chart_patterns': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'candlestick_patterns': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'volume_analysis': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'price_action': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'market_profile': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'order_flow': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'liquidity_analysis': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'volatility_analysis': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'risk_metrics': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'var_calculation': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'cvar_calculation': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'stress_testing': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'monte_carlo_simulation': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'scenario_analysis': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'sensitivity_analysis': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'backtesting': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'performance_attribution': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'risk_adjusted_returns': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'sharpe_ratio': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'sortino_ratio': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'calmar_ratio': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'max_drawdown': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'recovery_factor': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'ulcer_index': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'sterling_ratio': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'burke_ratio': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'kappa_ratio': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'omega_ratio': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'gain_to_pain_ratio': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'profit_factor': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'expectancy': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'win_rate': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'average_win': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'average_loss': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'largest_win': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'largest_loss': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'consecutive_wins': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'consecutive_losses': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'recovery_time': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'time_underwater': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'equity_curve': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'drawdown_curve': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_returns': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_volatility': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_sharpe': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_max_drawdown': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_calmar': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_sortino': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_sterling': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_burke': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_kappa': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_omega': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_gain_to_pain': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_profit_factor': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_expectancy': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_win_rate': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_average_win': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_average_loss': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_largest_win': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_largest_loss': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_consecutive_wins': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_consecutive_losses': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_recovery_time': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_time_underwater': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_equity_curve': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_drawdown_curve': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_rolling_returns': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_rolling_volatility': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_rolling_sharpe': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_rolling_max_drawdown': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_rolling_calmar': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_rolling_sortino': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_rolling_sterling': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_rolling_burke': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_rolling_kappa': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_rolling_omega': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_rolling_gain_to_pain': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_rolling_profit_factor': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_rolling_expectancy': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_rolling_win_rate': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_rolling_average_win': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_rolling_average_loss': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_rolling_largest_win': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_rolling_largest_loss': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_rolling_consecutive_wins': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_rolling_consecutive_losses': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_rolling_recovery_time': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_rolling_time_underwater': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_rolling_equity_curve': 'insightsagents.app.tools.mltools.anomalydetectiontools',
                'rolling_rolling_drawdown_curve': 'insightsagents.app.tools.mltools.anomalydetectiontools'
            }
            
            # Get the module for the function
            module_name = function_module_map.get(function_name)
            if not module_name:
                logger.warning(f"No module mapping found for function: {function_name}")
                return None
            
            # Import the module
            try:
                module = __import__(module_name, fromlist=[function_name])
            except ImportError as e:
                logger.warning(f"Failed to import module {module_name}: {e}")
                return None
            
            # Get the function object
            if hasattr(module, function_name):
                func_obj = getattr(module, function_name)
                
                # Get source code using inspect
                try:
                    source_code = inspect.getsource(func_obj)
                    return source_code
                except OSError as e:
                    logger.warning(f"Failed to get source code for {function_name}: {e}")
                    return None
            else:
                logger.warning(f"Function {function_name} not found in module {module_name}")
                return None
                
        except Exception as e:
            logger.warning(f"Error getting source code for {function_name}: {e}")
            return None
    
    async def _match_functions_to_steps_with_comprehensive_llm(
        self,
        reasoning_plan: List[Dict[str, Any]],
        relevant_functions: List[Dict[str, Any]],
        question: str,
        dataframe_description: str,
        available_columns: List[str]
    ) -> Dict[int, List[Dict[str, Any]]]:
        """
        Use LLM to match functions to specific steps using comprehensive definitions.
        
        Args:
            reasoning_plan: The reasoning plan from Step 1
            relevant_functions: List of relevant functions from comprehensive search
            question: Original user question
            dataframe_description: Description of the dataframe
            available_columns: List of available columns
            
        Returns:
            Dictionary mapping step numbers to matched functions
        """
        try:
            # Format functions for LLM prompt with comprehensive context
            function_descriptions = []
            for func in relevant_functions:
                desc = f"""
                Function: {func.get('function_name', 'unknown')}
                Pipeline: {func.get('pipe_name', 'unknown')}
                Description: {func.get('description', 'No description')}
                Usage: {func.get('usage_description', 'No usage info')}
                Category: {func.get('category', 'unknown')}
                """
                
                # Add comprehensive function definition if available
                function_definition = func.get('function_definition', {})
                if function_definition:
                    desc += f"\nFunction Definition: {json.dumps(function_definition, indent=2)}"
                
                # Add required and optional parameters if available
                required_params = func.get('required_params', [])
                optional_params = func.get('optional_params', [])
                if required_params or optional_params:
                    desc += f"\nParameters:"
                    if required_params:
                        desc += f"\n  Required: {json.dumps(required_params, indent=2)}"
                    if optional_params:
                        desc += f"\n  Optional: {json.dumps(optional_params, indent=2)}"
                
                # Add examples if available
                examples = func.get('examples', [])
                if examples:
                    desc += f"\nExamples ({len(examples)} available):\n"
                    for i, example in enumerate(examples[:3], 1):  # Show top 3 examples
                        if isinstance(example, dict):
                            # Handle comprehensive examples with variations
                            if 'variations' in example:
                                desc += f"  {i}. Variations ({len(example['variations'])}):\n"
                                for j, variation in enumerate(example['variations'][:2], 1):  # Show first 2 variations
                                    desc += f"    {j}. {variation.get('name', 'Variation')}: {variation.get('example', '')[:150]}...\n"
                            else:
                                desc += f"  {i}. {str(example)[:200]}...\n"
                        else:
                            desc += f"  {i}. {str(example)[:200]}...\n"
                
                # Add instructions if available
                instructions = func.get('instructions', [])
                if instructions:
                    desc += f"\nInstructions ({len(instructions)} available):\n"
                    for i, instruction in enumerate(instructions[:2], 1):  # Show top 2 instructions
                        desc += f"  {i}. {instruction.get('instruction', str(instruction))[:150]}...\n"
                
                # Add extracted parameters if available
                extracted_params = func.get('extracted_parameters', {})
                if extracted_params:
                    desc += f"\nExtracted Parameters: {json.dumps(extracted_params, indent=2)}"
                
                # Add historical rules if available
                historical_rules = func.get('historical_rules', [])
                if historical_rules:
                    desc += f"\nHistorical Rules ({len(historical_rules)} available):\n"
                    for i, rule in enumerate(historical_rules[:2], 1):  # Show top 2 rules
                        content = rule.get('content', str(rule))
                        if isinstance(content, str):
                            desc += f"  {i}. {content[:150]}...\n"
                        else:
                            desc += f"  {i}. {str(content)[:150]}...\n"
                
                # Add source code if available
                source_code = func.get('source_code', '')
                if source_code:
                    desc += f"\nSource Code:\n{source_code[:500]}{'...' if len(source_code) > 500 else ''}\n"
                
                # Add function signature if available
                function_signature = func.get('function_signature', '')
                if function_signature:
                    desc += f"\nFunction Signature: {function_signature}\n"
                
                # Add docstring if available
                docstring = func.get('docstring', '')
                if docstring:
                    desc += f"\nDocstring: {docstring[:200]}{'...' if len(docstring) > 200 else ''}\n"
                
                function_descriptions.append(desc)
            
            # Format reasoning plan for LLM prompt
            plan_description = "\n".join([
                f"Step {step.get('step_number', i+1)}: {step.get('step_title', '')}\n"
                f"Description: {step.get('step_description', '')}\n"
                f"Data Requirements: {', '.join(step.get('data_requirements', []))}\n"
                for i, step in enumerate(reasoning_plan)
            ])
            
            # Create comprehensive LLM prompt for function matching
            prompt = f"""
            You are an expert data analyst who matches analysis functions to specific analysis steps using comprehensive function definitions.
            
            USER QUESTION: {question}
            DATAFRAME DESCRIPTION: {dataframe_description}
            AVAILABLE COLUMNS: {', '.join(available_columns)}
            
            ANALYSIS PLAN:
            {plan_description}
            
            AVAILABLE FUNCTIONS WITH COMPREHENSIVE DEFINITIONS:
            {chr(10).join(function_descriptions)}
            
            TASK: For each step in the analysis plan, identify which functions are most relevant and appropriate using the comprehensive function definitions, examples, instructions, and extracted parameters.
            
            INSTRUCTIONS:
            1. Analyze each step's requirements and data needs
            2. Match functions that can fulfill those requirements using their comprehensive definitions
            3. Consider examples, instructions, and extracted parameters for better matching
            4. Score each function's relevance (0.0 to 1.0) for each step
            5. Provide detailed reasoning for each match
            6. Return results as JSON
            
            OUTPUT FORMAT:
            CRITICAL: You must return ONLY a valid JSON object without any markdown formatting, code blocks, or extra text.
            
            CORRECT FORMAT:
            {{
                "step_matches": {{
                    "1": [
                        {{
                            "function_name": "function_name",
                            "pipe_name": "pipe_name", 
                            "relevance_score": 0.95,
                            "reasoning": "Why this function is relevant for this step based on comprehensive definition",
                            "description": "function description",
                            "usage_description": "usage description",
                            "category": "category",
                            "function_definition": {{...}},
                            "extracted_parameters": {{...}},
                            "examples": [...],
                            "instructions": [...]
                        }}
                    ],
                    "2": [...],
                    ...
                }}
            }}
            
            Focus on functions that directly address each step's specific requirements using their comprehensive definitions.
            Return ONLY the JSON object, nothing else.
            """
            
            # Log comprehensive information before LLM call
            logger.info("=" * 80)
            logger.info("🚀 STARTING LLM CALL FOR FUNCTION MATCHING")
            logger.info("=" * 80)
            logger.info(f"📊 Input Summary:")
            logger.info(f"  • Reasoning Plan Steps: {len(reasoning_plan)}")
            logger.info(f"  • Relevant Functions: {len(relevant_functions)}")
            logger.info(f"  • Question: {question[:100]}...")
            logger.info(f"  • Dataframe Description: {dataframe_description[:100]}...")
            logger.info(f"  • Available Columns: {available_columns}")
            logger.info(f"  • Prompt Length: {len(prompt)} characters")
            logger.info(f"  • LLM Model: {type(self.llm).__name__}")
            
            # Log function details
            logger.info(f"📋 Function Details:")
            for i, func in enumerate(relevant_functions, 1):
                logger.info(f"  {i}. {func.get('function_name', 'unknown')} ({func.get('pipe_name', 'unknown')})")
                logger.info(f"     Description: {func.get('description', 'No description')[:100]}...")
                logger.info(f"     Has Source Code: {bool(func.get('source_code'))}")
                logger.info(f"     Has Examples: {len(func.get('examples', []))}")
                logger.info(f"     Has Instructions: {len(func.get('instructions', []))}")
            
            # Log prompt preview and structure
            logger.info(f"📝 Prompt Structure:")
            logger.info(f"  • Total Length: {len(prompt)} characters")
            logger.info(f"  • Lines: {len(prompt.splitlines())}")
            logger.info(f"  • Contains JSON: {'JSON' in prompt}")
            logger.info(f"  • Contains Functions: {'Function:' in prompt}")
            logger.info(f"  • Contains Steps: {'Step' in prompt}")
            
            # Log prompt preview (first 500 chars)
            logger.info(f"📝 Prompt Preview (first 500 chars):")
            logger.info(f"{prompt[:500]}...")
            
            # Log prompt ending (last 200 chars)
            logger.info(f"📝 Prompt Ending (last 200 chars):")
            logger.info(f"...{prompt[-200:]}")
            logger.info("=" * 80)
            
            # Get LLM response
            logger.info("⏳ Calling LLM...")
            llm_response = await self._classify_with_llm(prompt)
            
            # Log the response type for debugging
            logger.debug(f"LLM response type: {type(llm_response)}")
            logger.debug(f"LLM response: {llm_response[:500]}...")  # Log first 500 chars
            
            # Clean and parse the response
            try:
                # Clean the response - remove markdown formatting and empty content
                cleaned_response = llm_response.strip()
                
                # Remove markdown code blocks
                import re
                cleaned_response = re.sub(r'```json\s*', '', cleaned_response)
                cleaned_response = re.sub(r'```\s*', '', cleaned_response)
                cleaned_response = cleaned_response.strip()
                
                # Check if response is empty or just whitespace
                if not cleaned_response or cleaned_response.isspace():
                    logger.warning("LLM returned empty response, using fallback")
                    return self._fallback_function_step_matching(reasoning_plan, relevant_functions)
                
                # Try to parse JSON
                response_data = json.loads(cleaned_response)
                step_matches = response_data.get("step_matches", {})
                
                # Convert string keys to integers and validate
                validated_matches = {}
                for step_key, functions in step_matches.items():
                    try:
                        step_num = int(step_key)
                        if step_num > 0:
                            validated_matches[step_num] = functions
                    except ValueError:
                        continue
                
                logger.info(f"LLM matched functions to {len(validated_matches)} steps")
                return validated_matches
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse LLM response as JSON: {e}")
                logger.warning(f"Original response: {llm_response[:200]}...")
                logger.warning(f"Cleaned response: {cleaned_response[:200]}...")
                # Fallback: assign functions to steps based on simple matching
                return self._fallback_function_step_matching(reasoning_plan, relevant_functions)
                
        except Exception as e:
            logger.error(f"Error in LLM function matching: {e}")
            # Fallback: assign functions to steps based on simple matching
            return self._fallback_function_step_matching(reasoning_plan, relevant_functions)
    
    def _fallback_function_step_matching(
        self,
        reasoning_plan: List[Dict[str, Any]],
        relevant_functions: List[Dict[str, Any]]
    ) -> Dict[int, List[Dict[str, Any]]]:
        """
        Fallback function matching when LLM matching fails.
        
        Args:
            reasoning_plan: The reasoning plan from Step 1
            relevant_functions: List of relevant functions from comprehensive search
            
        Returns:
            Dictionary mapping step numbers to matched functions
        """
        step_matches = {}
        
        for step in reasoning_plan:
            step_num = step.get("step_number", 0)
            step_title = step.get("step_title", "").lower()
            step_desc = step.get("step_description", "").lower()
            
            matched_functions = []
            
            for func in relevant_functions:
                func_name = func.get("function_name", "").lower()
                func_desc = func.get("description", "").lower()
                func_usage = func.get("usage_description", "").lower()
                
                # Simple keyword matching
                relevance_score = 0.0
                reasoning = ""
                
                # Check for keyword matches
                keywords = step_title.split() + step_desc.split()
                for keyword in keywords:
                    if keyword in func_name or keyword in func_desc or keyword in func_usage:
                        relevance_score += 0.2
                
                # Normalize score
                relevance_score = min(1.0, relevance_score)
                
                if relevance_score > 0.3:  # Only include if reasonably relevant
                    matched_functions.append({
                        "function_name": func.get("function_name", ""),
                        "pipe_name": func.get("pipe_name", ""),
                        "relevance_score": relevance_score,
                        "reasoning": f"Keyword match with step: {step_title}",
                        "description": func.get("description", ""),
                        "usage_description": func.get("usage_description", ""),
                        "category": func.get("category", ""),
                        "function_definition": func.get("function_definition", {}),
                        "examples": func.get("examples", []),
                        "instructions": func.get("instructions", []),
                        "examples_store": func.get("examples_store", []),
                        "historical_rules": func.get("historical_rules", []),
                        "extracted_parameters": func.get("extracted_parameters", {})
                    })
            
            if matched_functions:
                step_matches[step_num] = matched_functions
        
        logger.info(f"Fallback matching assigned functions to {len(step_matches)} steps")
        return step_matches
    
    async def _classify_with_llm(self, prompt: str) -> str:
        """
        Classify using LLM with error handling
        
        Args:
            prompt: The prompt to send to the LLM
            
        Returns:
            LLM response as string
        """
        try:
            # Log LLM call details
            logger.info("🔧 LLM Call Details:")
            logger.info(f"  • Prompt Length: {len(prompt)} characters")
            logger.info(f"  • LLM Type: {type(self.llm).__name__}")
            logger.info(f"  • LLM Config: {getattr(self.llm, 'model_name', 'unknown')}")
            logger.info(f"  • Timeout: 30 seconds")
            
            # Create the chain with StrOutputParser
            chain = PromptTemplate.from_template("{prompt}") | self.llm | StrOutputParser()
            
            # Generate response with timeout
            import asyncio
            try:
                logger.info("⏳ Starting LLM inference...")
                start_time = asyncio.get_event_loop().time()
                
                response = await asyncio.wait_for(
                    chain.ainvoke({"prompt": prompt}),
                    timeout=30.0  # 30 second timeout
                )
                
                end_time = asyncio.get_event_loop().time()
                duration = end_time - start_time
                logger.info(f"✅ LLM call completed in {duration:.2f} seconds")
                
                # Validate response
                if not response or not isinstance(response, str):
                    logger.warning(f"LLM returned invalid response type: {type(response)}")
                    return ""
                
                return response
                
            except asyncio.TimeoutError:
                end_time = asyncio.get_event_loop().time()
                duration = end_time - start_time
                logger.error("=" * 80)
                logger.error("❌ LLM CALL TIMEOUT ERROR")
                logger.error("=" * 80)
                logger.error(f"⏰ Timeout Details:")
                logger.error(f"  • Timeout Duration: 30 seconds")
                logger.error(f"  • Actual Duration: {duration:.2f} seconds")
                logger.error(f"  • Prompt Length: {len(prompt)} characters")
                logger.error(f"  • LLM Type: {type(self.llm).__name__}")
                logger.error(f"  • LLM Config: {getattr(self.llm, 'model_name', 'unknown')}")
                logger.error(f"  • Prompt Preview: {prompt[:200]}...")
                logger.error("=" * 80)
                return ""
                
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            return ""
    
    def _create_result_from_matches(
        self,
        step_function_matches: Dict[int, List[Dict[str, Any]]],
        total_functions: int,
        reasoning_plan: List[Dict[str, Any]],
        fallback_used: bool = False
    ) -> EnhancedFunctionRetrievalResult:
        """
        Create result object from step-function matches
        
        Args:
            step_function_matches: Dictionary mapping step numbers to matched functions
            total_functions: Total number of functions retrieved
            reasoning_plan: The reasoning plan from Step 1
            fallback_used: Whether fallback matching was used
            
        Returns:
            EnhancedFunctionRetrievalResult
        """
        # Calculate metrics
        total_steps_covered = len(step_function_matches)
        total_steps = len(reasoning_plan)
        
        # Calculate average relevance score
        all_scores = []
        for functions in step_function_matches.values():
            for func in functions:
                all_scores.append(func.get("relevance_score", 0.0))
        
        average_relevance_score = sum(all_scores) / len(all_scores) if all_scores else 0.0
        
        # Calculate confidence score
        coverage_ratio = total_steps_covered / total_steps if total_steps > 0 else 0.0
        confidence_score = (coverage_ratio + average_relevance_score) / 2
        
        reasoning = f"Matched {total_functions} functions to {total_steps_covered}/{total_steps} steps with average relevance {average_relevance_score:.2f}"
        if fallback_used:
            reasoning += " (using fallback matching)"
        
        return EnhancedFunctionRetrievalResult(
            step_matches=step_function_matches,
            total_functions_retrieved=total_functions,
            total_steps_covered=total_steps_covered,
            average_relevance_score=average_relevance_score,
            confidence_score=confidence_score,
            reasoning=reasoning,
            fallback_used=fallback_used
        )
    
    def _create_empty_result(self, reasoning: str, fallback_used: bool = True) -> EnhancedFunctionRetrievalResult:
        """
        Create empty result when no functions are found
        
        Args:
            reasoning: Reason for empty result
            fallback_used: Whether fallback was used
            
        Returns:
            EnhancedFunctionRetrievalResult
        """
        return EnhancedFunctionRetrievalResult(
            step_matches={},
            total_functions_retrieved=0,
            total_steps_covered=0,
            average_relevance_score=0.0,
            confidence_score=0.0,
            reasoning=reasoning,
            fallback_used=fallback_used
        )
    
    async def _get_historical_rules(
        self,
        function_name: str,
        question: str
    ) -> List[Dict[str, Any]]:
        """
        Get historical rules and patterns for the function
        
        Args:
            function_name: Name of the function
            question: User question for context
            
        Returns:
            List of historical rules and patterns
        """
        if not self.retrieval_helper:
            return []
        
        try:
            # Get examples store for historical patterns
            examples_store_result = await self.retrieval_helper.get_function_examples(
                function_name=function_name,
                similarity_threshold=0.5,
                top_k=10
            )
            
            historical_rules = []
            if examples_store_result and not examples_store_result.get("error"):
                examples = examples_store_result.get("examples", [])
                
                # Filter for historical patterns and rules
                for example in examples:
                    if isinstance(example, dict):
                        # Look for rule-like patterns in the example
                        if any(keyword in str(example).lower() for keyword in ["rule", "pattern", "best_practice", "guideline", "convention"]):
                            historical_rules.append({
                                "type": "historical_pattern",
                                "content": example,
                                "source": "examples_store"
                            })
            
            # Add hardcoded rules based on function type
            hardcoded_rules = self._get_hardcoded_rules(function_name)
            historical_rules.extend(hardcoded_rules)
            
            return historical_rules
            
        except Exception as e:
            logger.error(f"Error getting historical rules for {function_name}: {e}")
            return []
    
    def _get_hardcoded_rules(self, function_name: str) -> List[Dict[str, Any]]:
        """
        Get hardcoded rules based on function type and name
        
        Args:
            function_name: Name of the function
            
        Returns:
            List of hardcoded rules
        """
        rules = []
        function_lower = function_name.lower()
        
        # Time series analysis rules
        if any(keyword in function_lower for keyword in ["variance", "rolling", "moving", "time_series"]):
            rules.extend([
                {
                    "type": "hardcoded_rule",
                    "content": "For time series analysis, always ensure data is sorted by time column before applying rolling functions",
                    "source": "hardcoded"
                },
                {
                    "type": "hardcoded_rule", 
                    "content": "Use appropriate window sizes based on data frequency - daily data: 7-30 days, hourly data: 24-168 hours",
                    "source": "hardcoded"
                }
            ])
        
        # Cohort analysis rules
        if any(keyword in function_lower for keyword in ["cohort", "retention", "churn"]):
            rules.extend([
                {
                    "type": "hardcoded_rule",
                    "content": "For cohort analysis, ensure user_id and date columns are properly formatted and contain no null values",
                    "source": "hardcoded"
                },
                {
                    "type": "hardcoded_rule",
                    "content": "Use consistent time periods (monthly, weekly) for cohort calculations to ensure comparability",
                    "source": "hardcoded"
                }
            ])
        
        # Risk analysis rules
        if any(keyword in function_lower for keyword in ["var", "risk", "monte_carlo", "stress_test"]):
            rules.extend([
                {
                    "type": "hardcoded_rule",
                    "content": "For risk analysis, use appropriate confidence levels (95% for VaR, 99% for stress testing)",
                    "source": "hardcoded"
                },
                {
                    "type": "hardcoded_rule",
                    "content": "Ensure sufficient historical data (minimum 1 year) for reliable risk calculations",
                    "source": "hardcoded"
                }
            ])
        
        # Segmentation rules
        if any(keyword in function_lower for keyword in ["cluster", "segment", "dbscan", "kmeans"]):
            rules.extend([
                {
                    "type": "hardcoded_rule",
                    "content": "For clustering, normalize numerical features before applying clustering algorithms",
                    "source": "hardcoded"
                },
                {
                    "type": "hardcoded_rule",
                    "content": "Use appropriate distance metrics - Euclidean for continuous variables, Jaccard for categorical",
                    "source": "hardcoded"
                }
            ])
        
        # Funnel analysis rules
        if any(keyword in function_lower for keyword in ["funnel", "conversion", "step"]):
            rules.extend([
                {
                    "type": "hardcoded_rule",
                    "content": "For funnel analysis, ensure event sequences are properly ordered by timestamp",
                    "source": "hardcoded"
                },
                {
                    "type": "hardcoded_rule",
                    "content": "Handle duplicate events by keeping only the first occurrence in each funnel step",
                    "source": "hardcoded"
                }
            ])
        
        return rules
    

def create_enhanced_function_retrieval_service(
    llm,
    retrieval_helper: RetrievalHelper,
    comprehensive_registry=None,
    example_collection=None,
    function_collection=None,
    insights_collection=None
) -> EnhancedFunctionRetrievalService:
    """
    Factory function to create an enhanced function retrieval service.
    
    Args:
        llm: LangChain LLM instance
        retrieval_helper: RetrievalHelper instance
        comprehensive_registry: Enhanced comprehensive registry
        example_collection: Examples collection
        function_collection: Function collection
        insights_collection: Insights collection
        
    Returns:
        EnhancedFunctionRetrievalService instance
    """
    return EnhancedFunctionRetrievalService(
        llm=llm,
        retrieval_helper=retrieval_helper,
        comprehensive_registry=comprehensive_registry,
        example_collection=example_collection,
        function_collection=function_collection,
        insights_collection=insights_collection
    )
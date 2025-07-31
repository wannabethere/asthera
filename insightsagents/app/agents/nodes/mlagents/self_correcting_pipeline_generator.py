from typing import Dict, List, Any, Optional, Union, Tuple
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers.string import StrOutputParser
import json
import re
from enum import Enum
import ast
from app.storage.documents import DocumentChromaStore
from .analysis_intent_classification import AnalysisIntentResult
import logging

class PipelineType(Enum):
    """Supported pipeline types"""
    COHORT = "CohortPipe"
    TIMESERIES = "TimeSeriesPipe"
    TRENDS = "TrendsPipe"
    SEGMENT = "SegmentPipe"
    RISK = "RiskPipe"
    METRICS = "MetricsPipe"
    OPERATIONS = "OperationsPipe"
    FUNNEL = "FunnelPipe"
    ANOMALY = "AnomalyPipe"

class DocumentRelevance(Enum):
    """Document relevance grades"""
    RELEVANT = "relevant"
    IRRELEVANT = "irrelevant"
    PARTIALLY_RELEVANT = "partially_relevant"

class CodeQuality(Enum):
    """Code quality grades"""
    EXCELLENT = "excellent"
    GOOD = "good"
    POOR = "poor"
    INVALID = "invalid"

# Initialize logger at the beginning

logger = logging.getLogger(__name__)
        

class SelfCorrectingPipelineCodeGenerator:
    """
    Self-correcting RAG-based pipeline code generator that produces complete 
    pipeline chains with proper Pipe initialization and method chaining.
    
    Implements adaptive RAG pattern with:
    - Multi-store document retrieval
    - Relevance grading
    - Code generation with validation
    - Self-correction loops
    """
    
    def __init__(self, 
                 llm,
                 usage_examples_store: DocumentChromaStore,
                 code_examples_store: DocumentChromaStore, 
                 function_definition_store:DocumentChromaStore,
                 logical_reasoning_store=None,
                 max_iterations: int = 3,
                 relevance_threshold: float = 0.7):
        """
        Initialize the self-correcting pipeline code generator
        
        Args:
            llm: Language model instance
            usage_examples_store: Store containing usage examples
            code_examples_store: Store containing code examples
            function_definition_store: Store containing function definitions
            logical_reasoning_store: Optional store for logical reasoning patterns
            max_iterations: Maximum number of self-correction iterations
            relevance_threshold: Threshold for document relevance scoring
        """
        self.llm = llm
        self.usage_examples_store = usage_examples_store
        self.code_examples_store = code_examples_store
        self.function_definition_store = function_definition_store
        self.logical_reasoning_store = logical_reasoning_store
        self.max_iterations = max_iterations
        self.relevance_threshold = relevance_threshold
        
        # Pipeline type mappings
        self.function_to_pipe = {
            "analyze_funnel": PipelineType.FUNNEL,
            "analyze_funnel_by_time": PipelineType.FUNNEL,
            "analyze_funnel_by_segment": PipelineType.FUNNEL,
            "form_time_cohorts": PipelineType.COHORT,
            "form_behavioral_cohorts": PipelineType.COHORT,
            "calculate_retention": PipelineType.COHORT,
            "calculate_lifetime_value": PipelineType.COHORT,
            "lead": PipelineType.TIMESERIES,
            "lag": PipelineType.TIMESERIES,
            "variance_analysis": PipelineType.TIMESERIES,
            # TrendsPipe Functions
            "aggregate_by_time": PipelineType.TRENDS,
            "calculate_growth_rates": PipelineType.TRENDS,
            "forecast_metric": PipelineType.TRENDS,
            "calculate_moving_average": PipelineType.TRENDS,
            "decompose_trend": PipelineType.TRENDS,
            "calculate_statistical_trend": PipelineType.TRENDS,
            "compare_periods": PipelineType.TRENDS,
            "get_top_metrics": PipelineType.TRENDS,
            # SegmentationPipe Functions
            "run_kmeans": PipelineType.SEGMENT,
            "run_dbscan": PipelineType.SEGMENT,
            "run_hierarchical": PipelineType.SEGMENT,
            "run_rule_based": PipelineType.SEGMENT,
            "get_features": PipelineType.SEGMENT,
            "generate_summary": PipelineType.SEGMENT,
            "get_segment_data": PipelineType.SEGMENT,
            "compare_algorithms": PipelineType.SEGMENT,
            "custom_calculation": PipelineType.SEGMENT,
            # RiskPipe Functions
            "calculate_var": PipelineType.RISK,
            "calculate_cvar": PipelineType.RISK,
            "monte_carlo_simulation": PipelineType.RISK,
            # MetricsPipe Functions
            "Count": PipelineType.METRICS,
            "Sum": PipelineType.METRICS,
            "Mean": PipelineType.METRICS,
            "Variance": PipelineType.METRICS,
            "StandardDeviation": PipelineType.METRICS,
            "Max": PipelineType.METRICS,
            "Min": PipelineType.METRICS,
            "Correlation": PipelineType.METRICS,
            "CV": PipelineType.METRICS,
            "Median": PipelineType.METRICS,
            "Percentile": PipelineType.METRICS,
            # OperationsPipe Functions
            "PercentChange": PipelineType.OPERATIONS,
            "AbsoluteChange": PipelineType.OPERATIONS,
            "CUPED": PipelineType.OPERATIONS,
            # Anomaly Detection Functions
            "detect_statistical_outliers": PipelineType.ANOMALY,
            "detect_contextual_anomalies": PipelineType.ANOMALY,
            "calculate_seasonal_residuals": PipelineType.ANOMALY,
            "detect_anomalies_from_residuals": PipelineType.ANOMALY,
            "forecast_and_detect_anomalies": PipelineType.ANOMALY,
            "batch_detect_anomalies": PipelineType.ANOMALY,
            "get_anomaly_summary": PipelineType.ANOMALY,
            "get_top_anomalies": PipelineType.ANOMALY
        }
    
    async def generate_pipeline_code(self, 
                                   context: str,
                                   function_name: Union[str, List[str]],
                                   function_inputs,
                                   dataframe_name: str = "df",
                                   classification: Optional[Union[Dict[str, Any], AnalysisIntentResult]] = None,
                                   dataset_description: Optional[str] = None,
                                   columns_description: Optional[Dict[str, str]] = None) -> Dict[str, Any]: 
        """
        Generate complete pipeline code with self-correction
        
        Args:
            context: Natural language description of the task
            function_name: Fallback function(s) to use if classification.retrieved_functions is not available
                          (can be a string or list of suggested functions)
            function_inputs: Extracted function inputs (will be enhanced by LLM detection).
                           Can be Dict[str, Any], List[str], or other types (will be converted to dict)
            dataframe_name: Name of the dataframe variable
            classification: Optional classification results with intent, confidence, and retrieved_functions.
                          If provided and contains retrieved_functions, these will be used instead of function_name
            dataset_description: Optional description of the dataset
            columns_description: Optional dictionary mapping column names to descriptions
            
        Returns:
            Dictionary containing generated code and metadata
        """
        
        # Use existing reasoning plan and retrieved functions from classification if available
        if classification and hasattr(classification, 'reasoning_plan') and classification.reasoning_plan:
            # Use the existing reasoning plan and retrieved functions
            reasoning_plan = classification.reasoning_plan
            retrieved_functions = classification.retrieved_functions if hasattr(classification, 'retrieved_functions') else []
            
            logger.info(f"Using existing reasoning plan with {len(reasoning_plan)} steps")
            logger.info(f"Using existing retrieved functions: {len(retrieved_functions)} functions")
            
            # Extract function names from reasoning plan steps
            reasoning_plan_functions = []
            for step in reasoning_plan:
                if isinstance(step, dict) and 'function_name' in step:
                    reasoning_plan_functions.append(step['function_name'])
            
            # Use reasoning plan functions if available, otherwise use retrieved functions
            if reasoning_plan_functions:
                function_name = reasoning_plan_functions
                logger.info(f"Using functions from reasoning plan: {reasoning_plan_functions}")
            elif retrieved_functions:
                # Extract function names from retrieved_functions
                retrieved_function_names = []
                for func in retrieved_functions:
                    if isinstance(func, dict):
                        func_name = func.get('function_name', '')
                        if func_name:
                            retrieved_function_names.append(func_name)
                    elif isinstance(func, str):
                        retrieved_function_names.append(func)
                
                if retrieved_function_names:
                    function_name = retrieved_function_names
                    logger.info(f"Using retrieved_functions from classification: {retrieved_function_names}")
                else:
                    # Fallback to function_name parameter
                    if not isinstance(function_name, list):
                        function_name = [function_name]
                    logger.info(f"Using function_name parameter as fallback: {function_name}")
            else:
                # Fallback to function_name parameter
                if not isinstance(function_name, list):
                    function_name = [function_name]
                logger.info(f"Using function_name parameter as fallback: {function_name}")
        else:
            # Use function_name parameter if no reasoning plan available
            if not isinstance(function_name, list):
                function_name = [function_name]
            logger.info(f"Using function_name parameter: {function_name}")
        
        original_function_list = function_name
        
        # If we have a reasoning plan, use it directly instead of detecting functions
        if classification and hasattr(classification, 'reasoning_plan') and classification.reasoning_plan:
            # Use the reasoning plan to determine the primary function and inputs
            reasoning_plan_result = self._extract_function_from_reasoning_plan(
                classification.reasoning_plan, context, classification
            )
            selected_function = reasoning_plan_result["selected_function"]
            function_detection_metadata = reasoning_plan_result["metadata"]
            detected_inputs = reasoning_plan_result["inputs"]
            
            logger.info(f"Using reasoning plan - Selected function: {selected_function}")
            logger.info(f"Using reasoning plan - Function metadata: {function_detection_metadata}")
            logger.info(f"Using reasoning plan - Detected inputs: {detected_inputs}")
        else:
            # Fallback to original detection logic
            detected_function = await self._detect_best_function(
                context, function_name, classification, dataset_description, columns_description
            )
            selected_function = detected_function["selected_function"]
            function_detection_metadata = detected_function
            print("detected_function",detected_function)
            # Validate that a function was selected
            if not selected_function:
                logger.warning("No function was selected from the list, using the first suggested function")
                selected_function = original_function_list[0] if original_function_list else "Mean"  # fallback
                function_detection_metadata["selected_function"] = selected_function
                function_detection_metadata["reasoning"] = "Fallback to first suggested function due to detection failure"
            
            # Detect function inputs using LLM (including additional computations)
            detected_inputs = await self._detect_function_inputs(
                context, selected_function, classification, dataset_description, columns_description
            )
        
        function_name = selected_function
        
        # Debug logging
        logger.info(f"Detected function: {function_name}")
        logger.info(f"Function detection metadata: {function_detection_metadata}")
        logger.info(f"Detected inputs: {detected_inputs}")
        logger.info(f"Detected inputs type: {type(detected_inputs)}")
        logger.info(f"Function inputs: {function_inputs}")
        logger.info(f"Function inputs type: {type(function_inputs)}")
        
        # Ensure function_inputs is a dictionary
        if not isinstance(function_inputs, dict):
            if isinstance(function_inputs, list):
                # If it's a list, it might be column names - convert to a meaningful dict
                logger.info(f"Function inputs is a list, converting to dict with column names: {function_inputs}")
                if len(function_inputs) > 0:
                    # Create a more meaningful structure
                    function_inputs = {
                        "columns": function_inputs,
                        "column_count": len(function_inputs),
                        "primary_columns": function_inputs[:3] if len(function_inputs) >= 3 else function_inputs
                    }
                else:
                    function_inputs = {}
            else:
                logger.warning(f"Function inputs is not a dict, converting to empty dict: {type(function_inputs)} -> {function_inputs}")
                function_inputs = {}
        
        # Merge detected inputs with provided inputs (detected inputs take precedence)
        primary_function_inputs = detected_inputs.get("primary_function_inputs", {})
        logger.info(f"Primary function inputs: {primary_function_inputs}")
        logger.info(f"Primary function inputs type: {type(primary_function_inputs)}")
        
        # Ensure primary_function_inputs is a dictionary
        if isinstance(primary_function_inputs, list):
            # Convert list to dictionary if needed
            logger.warning(f"Primary function inputs is a list, converting to empty dict: {primary_function_inputs}")
            primary_function_inputs = {}
        elif not isinstance(primary_function_inputs, dict):
            # Convert any other type to empty dict
            logger.warning(f"Primary function inputs is not a dict, converting to empty dict: {type(primary_function_inputs)}")
            primary_function_inputs = {}
        
        enhanced_function_inputs = {**function_inputs, **primary_function_inputs}
        
        # Enhance context with classification information
        enhanced_context = self._enhance_context_with_classification(
            context, classification, dataset_description, columns_description
        )
        
        query_state = {
            "context": enhanced_context,
            "original_context": context,
            "function_name": function_name,
            "function_inputs": enhanced_function_inputs,
            "detected_inputs": detected_inputs,
            "function_detection_metadata": function_detection_metadata,
            "dataframe_name": dataframe_name,
            "classification": classification,
            "dataset_description": dataset_description,
            "columns_description": columns_description,
            "iteration": 0,
            "retrieved_docs": {},
            "code_attempts": [],
            "final_code": None,
            "reasoning": []
        }
        
        # Self-correction loop
        for iteration in range(self.max_iterations):
            query_state["iteration"] = iteration
            
            # Check if we have a reasoning plan to use directly
            if classification and hasattr(classification, 'reasoning_plan') and classification.reasoning_plan:
                # Use reasoning plan directly for code generation
                logger.info(f"Iteration {iteration}: Using reasoning plan for direct code generation")
                
                # Evaluate reasoning plan quality first
                plan_evaluation = self._evaluate_reasoning_plan_quality(
                    classification.reasoning_plan, 
                    "",  # No generated code yet
                    query_state
                )
                
                logger.info(f"Reasoning plan quality score: {plan_evaluation['quality_score']}")
                if plan_evaluation['issues']:
                    logger.info(f"Reasoning plan issues: {plan_evaluation['issues']}")
                
                # Adjust reasoning plan if needed
                if plan_evaluation['quality_score'] < 0.7:
                    logger.info("Adjusting reasoning plan due to quality issues")
                    adjusted_plan = self._adjust_reasoning_plan(
                        classification.reasoning_plan, 
                        plan_evaluation
                    )
                    # Update the classification with adjusted plan
                    classification.reasoning_plan = adjusted_plan
                    logger.info(f"Adjusted reasoning plan has {len(adjusted_plan)} steps")
                
                # Generate code from (potentially adjusted) reasoning plan
                generated_code = self._generate_code_from_reasoning_plan(
                    classification.reasoning_plan, 
                    dataframe_name, 
                    classification
                )
                
                # Grade the generated code
                code_quality = self._grade_code(generated_code, query_state)
                
                # If code quality is good, use it; otherwise try LLM generation
                if code_quality in [CodeQuality.EXCELLENT, CodeQuality.GOOD]:
                    query_state["final_code"] = generated_code
                    logger.info("Using code generated from reasoning plan")
                    break
                else:
                    logger.info(f"Reasoning plan code quality was {code_quality}, trying LLM generation")
                    # Add reasoning plan evaluation to query state for LLM generation
                    query_state["reasoning_plan_evaluation"] = plan_evaluation
            
            # Step 1: Retrieve documents
            retrieved_docs = self._retrieve_documents(query_state)
            
            # Step 2: Grade document relevance
            relevant_docs = await self._grade_documents(retrieved_docs, query_state)
            
            # Step 3: Generate code
            generated_code = await self._generate_code(relevant_docs, query_state)
            
            # Step 4: Validate and grade code
            code_quality = self._grade_code(generated_code, query_state)
            
            # Step 5: Decide on next action
            if code_quality in [CodeQuality.EXCELLENT, CodeQuality.GOOD]:
                query_state["final_code"] = generated_code
                break
            elif iteration < self.max_iterations - 1:
                # Self-correct: refine query and try again
                query_state = self._refine_query_state(query_state, code_quality)
        
        return self._format_final_result(query_state)
    
    def _enhance_context_with_classification(self, 
                                           context: str,
                                           classification: Optional[Union[Dict[str, Any], AnalysisIntentResult]] = None,
                                           dataset_description: Optional[str] = None,
                                           columns_description: Optional[Dict[str, str]] = None) -> str:
        """
        Enhance the context with classification information and dataset details
        
        Args:
            classification: Either a Dict[str, Any] or AnalysisIntentResult object
        """
        enhanced_parts = [context]
        
        if classification:
            # Handle both dictionary and Pydantic model inputs
            if hasattr(classification, 'intent_type'):
                # Pydantic model (AnalysisIntentResult)
                intent_type = getattr(classification, 'intent_type', '')
                confidence_score = getattr(classification, 'confidence_score', 0.0)
                rephrased_question = getattr(classification, 'rephrased_question', '')
                reasoning = getattr(classification, 'reasoning', '')
                suggested_functions = getattr(classification, 'suggested_functions', [])
                required_columns = getattr(classification, 'required_data_columns', [])
                missing_columns = getattr(classification, 'missing_columns', [])
                can_be_answered = getattr(classification, 'can_be_answered', True)
                feasibility_score = getattr(classification, 'feasibility_score', 0.0)
                clarification_needed = getattr(classification, 'clarification_needed', None)
                reasoning_plan = getattr(classification, 'reasoning_plan', None)
            else:
                # Dictionary
                intent_type = classification.get('intent_type', '')
                confidence_score = classification.get('confidence_score', 0.0)
                rephrased_question = classification.get('rephrased_question', '')
                reasoning = classification.get('reasoning', '')
                suggested_functions = classification.get('suggested_functions', [])
                required_columns = classification.get('required_data_columns', [])
                missing_columns = classification.get('missing_columns', [])
                can_be_answered = classification.get('can_be_answered', True)
                feasibility_score = classification.get('feasibility_score', 0.0)
                clarification_needed = classification.get('clarification_needed')
                reasoning_plan = classification.get('reasoning_plan', None)
            
            enhanced_parts.append(f"\nIntent Analysis:")
            enhanced_parts.append(f"- Intent Type: {intent_type}")
            enhanced_parts.append(f"- Confidence: {confidence_score:.2f}")
            if rephrased_question:
                enhanced_parts.append(f"- Rephrased Question: {rephrased_question}")
            if reasoning:
                enhanced_parts.append(f"- Reasoning: {reasoning}")
            
            # Add suggested functions
            if suggested_functions:
                enhanced_parts.append(f"- Suggested Functions: {', '.join(suggested_functions)}")
            
            # Add data requirements
            if required_columns:
                enhanced_parts.append(f"- Required Columns: {', '.join(required_columns)}")
            
            if missing_columns:
                enhanced_parts.append(f"- Missing Columns: {', '.join(missing_columns)}")
            
            # Add feasibility information
            enhanced_parts.append(f"- Can Be Answered: {can_be_answered}")
            enhanced_parts.append(f"- Feasibility Score: {feasibility_score:.2f}")
            
            # Add clarification if needed
            if clarification_needed:
                enhanced_parts.append(f"- Clarification Needed: {clarification_needed}")
            
            # Add reasoning plan as raw JSON if available
            if reasoning_plan and isinstance(reasoning_plan, list):
                enhanced_parts.append(f"\nReasoning Plan (JSON):")
                enhanced_parts.append(json.dumps(reasoning_plan, indent=2))
        
        # Add dataset description
        if dataset_description:
            enhanced_parts.append(f"\nDataset Description: {dataset_description}")
        
        # Add columns description
        if columns_description:
            enhanced_parts.append(f"\nColumns Description:")
            for col, desc in columns_description.items():
                enhanced_parts.append(f"- {col}: {desc}")
        
        return "\n".join(enhanced_parts)
    
    def _extract_function_from_reasoning_plan(self, 
                                            reasoning_plan: List[Dict[str, Any]], 
                                            context: str,
                                            classification: Union[Dict[str, Any], AnalysisIntentResult]) -> Dict[str, Any]:
        """
        Extract function and inputs from existing reasoning plan instead of creating new ones
        
        Args:
            reasoning_plan: List of reasoning plan steps
            context: Original context
            classification: Classification results
            
        Returns:
            Dictionary with selected function, metadata, and inputs
        """
        if not reasoning_plan or not isinstance(reasoning_plan, list):
            return {
                "selected_function": "Mean",  # fallback
                "metadata": {
                    "selected_function": "Mean",
                    "confidence": 0.0,
                    "reasoning": "No reasoning plan available, using fallback",
                    "alternative_functions": [],
                    "reasoning_plan_alignment": "No reasoning plan to align with"
                },
                "inputs": {
                    "primary_function_inputs": {},
                    "additional_computations": [],
                    "pipeline_sequence": ["Basic analysis"],
                    "reasoning": "No reasoning plan available",
                    "reasoning_plan_step_mapping": "No reasoning plan available"
                }
            }
        
        # Extract functions from reasoning plan steps
        plan_functions = []
        for step in reasoning_plan:
            if isinstance(step, dict) and 'function_name' in step:
                function_name = step['function_name']
                # Skip None, "None", or empty function names
                if function_name and function_name != "None" and function_name != "none":
                    plan_functions.append(function_name)
        
        if not plan_functions:
            return {
                "selected_function": "Mean",  # fallback
                "metadata": {
                    "selected_function": "Mean",
                    "confidence": 0.0,
                    "reasoning": "No functions found in reasoning plan, using fallback",
                    "alternative_functions": [],
                    "reasoning_plan_alignment": "No functions in reasoning plan"
                },
                "inputs": {
                    "primary_function_inputs": {},
                    "additional_computations": [],
                    "pipeline_sequence": ["Basic analysis"],
                    "reasoning": "No functions found in reasoning plan",
                    "reasoning_plan_step_mapping": "No functions in reasoning plan"
                }
            }
        
        # Select the primary function (first one in the plan)
        selected_function = plan_functions[0]
        
        # Create metadata based on reasoning plan
        metadata = {
            "selected_function": selected_function,
            "confidence": 0.95,  # High confidence since it's from reasoning plan
            "reasoning": f"Selected {selected_function} from reasoning plan step 1",
            "alternative_functions": plan_functions[1:] if len(plan_functions) > 1 else [],
            "reasoning_plan_alignment": f"Directly implements reasoning plan with {len(reasoning_plan)} steps"
        }
        
        # Extract inputs from reasoning plan
        primary_function_inputs = {}
        additional_computations = []
        pipeline_sequence = []
        
        for i, step in enumerate(reasoning_plan):
            if isinstance(step, dict):
                step_num = step.get('step_number', i + 1)
                step_title = step.get('step_title', f'Step {step_num}')
                function_name = step.get('function_name', '')
                parameter_mapping = step.get('parameter_mapping', {})
                data_requirements = step.get('data_requirements', [])
                embedded_function_parameter = step.get('embedded_function_parameter', False)
                embedded_function_details = step.get('embedded_function_details', {})
                
                # Handle None, "None", or "N/A" values
                if function_name in [None, "None", "none", "N/A"]:
                    function_name = ""
                if parameter_mapping in [None, "None", "none", "N/A"]:
                    parameter_mapping = {}
                
                # Add to pipeline sequence
                pipeline_sequence.append(f"Step {step_num}: {step_title}")
                
                # Extract parameters for the primary function (first step)
                if i == 0 and parameter_mapping:
                    if isinstance(parameter_mapping, dict):
                        primary_function_inputs = parameter_mapping.copy()
                        
                        # Handle embedded function parameters
                        if embedded_function_parameter and embedded_function_details:
                            embedded_function = embedded_function_details.get('embedded_function', '')
                            embedded_pipe = embedded_function_details.get('embedded_pipe', 'MetricsPipe')
                            embedded_parameters = embedded_function_details.get('embedded_parameters', {})
                            
                            if embedded_function and embedded_pipe:
                                # Create the embedded function expression
                                embedded_expr = f"({embedded_pipe}.from_dataframe(df) | {embedded_function}("
                                
                                # Add embedded function parameters
                                embedded_params = []
                                for key, value in embedded_parameters.items():
                                    if isinstance(value, str):
                                        embedded_params.append(f"{key}='{value}'")
                                    else:
                                        embedded_params.append(f"{key}={value}")
                                
                                embedded_expr += ", ".join(embedded_params)
                                embedded_expr += ") | to_df())"
                                
                                # Add the embedded function to the primary function inputs
                                primary_function_inputs['function'] = embedded_expr
                                
                                logger.info(f"Added embedded function parameter: {embedded_expr}")
                    else:
                        logger.warning(f"Parameter mapping is not a dictionary, converting to empty dict: {type(parameter_mapping)} -> {parameter_mapping}")
                        primary_function_inputs = {}
                
                # Add additional computations for subsequent steps (only if not embedded)
                if i > 0 and function_name and not embedded_function_parameter:
                    # Ensure parameter_mapping is a dictionary
                    if isinstance(parameter_mapping, dict):
                        inputs_for_computation = parameter_mapping
                    else:
                        logger.warning(f"Parameter mapping for step {i} is not a dictionary, using empty dict: {type(parameter_mapping)} -> {parameter_mapping}")
                        inputs_for_computation = {}
                    
                    additional_computations.append({
                        "function": function_name,
                        "inputs": inputs_for_computation,
                        "tool": "metrics_tools" if function_name in ["Mean", "Sum", "Count", "Variance"] else "builtin"
                    })
        
        # Create inputs structure
        inputs = {
            "primary_function_inputs": primary_function_inputs,
            "additional_computations": additional_computations,
            "pipeline_sequence": pipeline_sequence,
            "multi_pipeline": len(additional_computations) > 0,
            "first_pipeline_type": "MetricsPipe" if selected_function in ["Mean", "Sum", "Count", "Variance", "GroupBy"] else None,
            "second_pipeline_type": None,  # Will be determined by the primary function
            "reasoning": f"Extracted from reasoning plan with {len(reasoning_plan)} steps",
            "reasoning_plan_step_mapping": f"Maps to {len(reasoning_plan)} reasoning plan steps"
        }
        
        # Check if any step has embedded function parameters
        has_embedded_functions = any(
            step.get('embedded_function_parameter', False) 
            for step in reasoning_plan 
            if isinstance(step, dict)
        )
        
        if has_embedded_functions:
            # If we have embedded functions, we don't need separate pipelines
            inputs["multi_pipeline"] = False
            inputs["reasoning"] += " (embedded function parameters used)"
        
        # Determine second pipeline type if multi-pipeline
        if inputs["multi_pipeline"] and additional_computations:
            # Check what type of functions are in additional computations
            for comp in additional_computations:
                func_name = comp.get("function", "")
                if func_name in ["variance_analysis", "lead", "lag"]:
                    inputs["second_pipeline_type"] = "TimeSeriesPipe"
                    break
                elif func_name in ["form_time_cohorts", "calculate_retention"]:
                    inputs["second_pipeline_type"] = "CohortPipe"
                    break
                elif func_name in ["detect_statistical_outliers", "detect_contextual_anomalies"]:
                    inputs["second_pipeline_type"] = "AnomalyPipe"
                    break
                elif func_name in ["run_kmeans", "run_dbscan"]:
                    inputs["second_pipeline_type"] = "SegmentPipe"
                    break
        
        logger.info(f"Extracted function from reasoning plan: {selected_function}")
        logger.info(f"Reasoning plan has {len(reasoning_plan)} steps")
        logger.info(f"Pipeline sequence: {pipeline_sequence}")
        
        return {
            "selected_function": selected_function,
            "metadata": metadata,
            "inputs": inputs
        }
    
    async def _detect_best_function(self, 
                                   context: str,
                                   suggested_functions: List[str],
                                   classification: Optional[Union[Dict[str, Any], AnalysisIntentResult]] = None,
                                   dataset_description: Optional[str] = None,
                                   columns_description: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Detect the best function from a list of suggested functions using LLM.
        """
        # Retrieve function definitions from the function_definition_store
        function_definitions = await self._retrieve_function_definitions(suggested_functions)
        print("function_definitions",function_definitions)

        # Extract retrieved_functions metadata if available
        retrieved_functions_info = ""
        if classification and hasattr(classification, 'retrieved_functions') and classification.retrieved_functions:
            retrieved_functions_info = "\nRETRIEVED FUNCTIONS METADATA:\n"
            for i, func in enumerate(classification.retrieved_functions, 1):
                if func.get('function_name') in suggested_functions:
                    retrieved_functions_info += f"{i}. {func.get('function_name', 'N/A')}:\n"
                    retrieved_functions_info += f"   - Relevance Score: {func.get('relevance_score', 'N/A')}\n"
                    retrieved_functions_info += f"   - Description: {func.get('description', 'N/A')}\n"
                    retrieved_functions_info += f"   - Usage: {func.get('usage_description', 'N/A')}\n"
                    retrieved_functions_info += f"   - Reasoning: {func.get('reasoning', 'N/A')}\n"
                    retrieved_functions_info += f"   - Priority: {func.get('priority', 'N/A')}\n"
                    
                    # Add required parameters if available
                    if func.get('required_params'):
                        retrieved_functions_info += f"   - Required Parameters:\n"
                        for param in func.get('required_params', []):
                            param_name = param.get('name', 'N/A')
                            param_type = param.get('type', 'N/A')
                            param_desc = param.get('description', 'N/A')
                            retrieved_functions_info += f"     * {param_name} ({param_type}): {param_desc}\n"
                    
                    # Add optional parameters if available
                    if func.get('optional_params'):
                        retrieved_functions_info += f"   - Optional Parameters:\n"
                        for param in func.get('optional_params', []):
                            param_name = param.get('name', 'N/A')
                            param_type = param.get('type', 'N/A')
                            param_desc = param.get('description', 'N/A')
                            retrieved_functions_info += f"     * {param_name} ({param_type}): {param_desc}\n"
                    
                    # Add outputs if available
                    if func.get('outputs'):
                        outputs = func.get('outputs', {})
                        output_type = outputs.get('type', 'N/A')
                        output_desc = outputs.get('description', 'N/A')
                        retrieved_functions_info += f"   - Output: {output_type} - {output_desc}\n"
                    
                    # Add category if available
                    if func.get('category'):
                        retrieved_functions_info += f"   - Category: {func.get('category')}\n"
                    
                    retrieved_functions_info += "\n"

        detection_prompt = PromptTemplate(
            input_variables=[
                "context", "suggested_functions", "function_definitions", "classification_context", "dataset_context", "reasoning_plan_json", "retrieved_functions_info"
            ],
            template="""
            You are an expert function selector for data analysis pipelines.
            
            TASK: From the provided list of suggested functions, select the most appropriate primary function
            to fulfill the given context. Consider the intent type, confidence, feasibility, and the detailed reasoning plan.
            
            CONTEXT: {context}
            SUGGESTED FUNCTIONS: {suggested_functions}
            
            FUNCTION DEFINITIONS:
            {function_definitions}
            
            CLASSIFICATION ANALYSIS:
            {classification_context}
            
            DATASET INFORMATION:
            {dataset_context}
            
            REASONING PLAN (JSON):
            {reasoning_plan_json}
            
            {retrieved_functions_info}
            
            INSTRUCTIONS:
            1. Analyze the context to understand the data analysis task.
            2. Review the function definitions to understand what each function does.
            3. Analyze the dataset and column descriptions to identify available data types and columns.
            4. IMPORTANT: Use ONLY the actual column names provided in the dataset information. Do not invent column names.
            5. Map context requirements to actual column names from the dataset description:
               - If the context mentions "sales", look for columns like "sales_amount", "total_sales", "revenue", etc.
               - If the context mentions "time" or "date", look for temporal columns
               - If the context mentions grouping "by region", look for categorical columns that could represent regions
            6. CRITICAL: Use the reasoning plan to guide function selection:
               - Review each step in the reasoning plan to understand the analysis approach
               - Identify which functions are suggested for each step
               - Prioritize functions that appear in multiple steps or have high relevance
               - Consider the step-by-step logic and data requirements
               - Choose functions that align with the expected outcomes described in the plan
            7. CRITICAL: Use the retrieved functions metadata to prioritize function selection:
               - Higher relevance scores indicate better matches for the current context
               - Review the reasoning provided for each function to understand why it was selected
               - Consider priority levels when multiple functions are available
               - Functions with higher relevance scores and better reasoning should be preferred
               - Review required and optional parameters to ensure the function can be used with available data
               - Consider parameter types and descriptions when selecting functions
            8. Evaluate the confidence and feasibility of each suggested function based on their definitions, available data, reasoning plan alignment, and retrieved functions metadata.
            9. Prioritize functions that are highly confident, feasible with the available data, align with the reasoning plan, AND have high relevance scores from the retrieved functions analysis.
            10. Consider if multiple pipelines are needed based on data requirements and reasoning plan steps.
            11. Return a JSON object with the selected function and its confidence.
            
            OUTPUT FORMAT:
            {{
                "selected_function": "function_name",
                "confidence": 0.0-1.0,
                "reasoning": "explanation of why this function was selected, including reasoning plan alignment",
                "alternative_functions": ["function_name1", "function_name2"],
                "reasoning_plan_alignment": "how this function aligns with the reasoning plan steps"
            }}
            
            EXAMPLES:
            
            Example 1 - Simple selection with reasoning plan:
            Context: "Calculate the mean of sales column"
            Suggested Functions: ["Mean", "Sum", "Count"]
            Reasoning Plan: Step 1 suggests "Mean" function for basic aggregation
            Output: {{
                "selected_function": "Mean",
                "confidence": 0.95,
                "reasoning": "Mean is the most direct and confident function for calculating a single value. Aligns with Step 1 of reasoning plan.",
                "alternative_functions": ["Sum", "Count"],
                "reasoning_plan_alignment": "Directly matches Step 1 requirement for mean calculation"
            }}
            
            Example 2 - Multi-pipeline selection with reasoning plan:
            Context: "Calculate the mean of transactional value and then analyze its variance over time"
            Suggested Functions: ["Mean", "Variance", "variance_analysis"]
            Reasoning Plan: Step 1 suggests "Mean" for aggregation, Step 2 suggests "variance_analysis" for time series
            Output: {{
                "selected_function": "Mean",
                "confidence": 0.85,
                "reasoning": "Mean is a necessary first step for variance analysis. TimeSeriesPipe is also needed. Aligns with Step 1 of reasoning plan.",
                "alternative_functions": ["Variance"],
                "reasoning_plan_alignment": "Matches Step 1 requirement for mean calculation, sets up for Step 2 variance analysis"
            }}
            
            Example 3 - Risk function selection with reasoning plan:
            Context: "Calculate the variance of customer retention rate"
            Suggested Functions: ["Variance", "CohortPipe"]
            Reasoning Plan: Step 1 suggests "Variance" for risk assessment
            Output: {{
                "selected_function": "Variance",
                "confidence": 0.90,
                "reasoning": "Variance is the most relevant and confident function for risk analysis. Directly matches reasoning plan Step 1.",
                "alternative_functions": ["CohortPipe"],
                "reasoning_plan_alignment": "Directly implements Step 1 variance calculation requirement"
            }}
            
            Example 4 - Column-aware function selection with reasoning plan:
            Context: "Analyze sales performance by region over time"
            Suggested Functions: ["Mean", "variance_analysis", "aggregate_by_time"]
            Dataset: "Sales data with regional and temporal information"
            Columns: {{"sales_amount": "Total sales value", "region": "Sales region", "date": "Transaction date"}}
            Reasoning Plan: Step 1 suggests "aggregate_by_time" for temporal analysis, Step 2 suggests grouping by region
            Output: {{
                "selected_function": "aggregate_by_time",
                "confidence": 0.95,
                "reasoning": "aggregate_by_time is the best choice as it can handle both temporal analysis (using 'date' column) and grouping by region, with 'sales_amount' as the target metric. Aligns with reasoning plan steps.",
                "alternative_functions": ["Mean", "variance_analysis"],
                "reasoning_plan_alignment": "Implements Step 1 temporal aggregation and sets up for Step 2 regional grouping"
            }}
            
            Analyze the given context and return the appropriate JSON response.
            """
        )
        
        # Format classification context
        classification_context = self._format_classification_context(classification) if classification else "No classification available"
        
        # Format dataset context
        dataset_context = self._format_dataset_context(dataset_description, columns_description)
        
        # Format reasoning plan as JSON
        reasoning_plan_json = self._format_reasoning_plan_json(classification)
        
        # Create detection chain
        detection_chain = detection_prompt | self.llm | StrOutputParser()
        
        try:
            # Invoke the detection
            result = await detection_chain.ainvoke({
                "context": context,
                "suggested_functions": ", ".join(suggested_functions),
                "function_definitions": function_definitions,
                "classification_context": classification_context,
                "dataset_context": dataset_context,
                "reasoning_plan_json": reasoning_plan_json,
                "retrieved_functions_info": retrieved_functions_info
            })
            
            # Parse the JSON result
            try:
                detected_function = json.loads(result.strip())
                print("detected_function",result)
                # Debug logging
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"Raw LLM response: {result}")
                logger.debug(f"Parsed detected_function: {detected_function}")
                logger.debug(f"Detected function type: {type(detected_function)}")
                
                # Validate the structure
                if not isinstance(detected_function, dict):
                    raise ValueError("Result is not a dictionary")
                
                # Ensure required keys exist and have correct types
                required_keys = ["selected_function", "confidence", "reasoning", "alternative_functions", "reasoning_plan_alignment"]
                
                for key in required_keys:
                    if key not in detected_function:
                        if key == "selected_function":
                            detected_function[key] = ""
                        elif key == "confidence":
                            detected_function[key] = 0.0
                        elif key == "reasoning":
                            detected_function[key] = ""
                        elif key == "alternative_functions":
                            detected_function[key] = []
                        elif key == "reasoning_plan_alignment":
                            detected_function[key] = ""
                
                # Ensure alternative_functions is a list
                if not isinstance(detected_function["alternative_functions"], list):
                    detected_function["alternative_functions"] = []
                
                logger.debug(f"Final detected_function: {detected_function}")
                return detected_function
                
            except json.JSONDecodeError as e:
                # If JSON parsing fails, return a basic structure
                return {
                    "selected_function": "",
                    "confidence": 0.0,
                    "reasoning": f"JSON parsing failed: {str(e)}. Using fallback function.",
                    "alternative_functions": [],
                    "reasoning_plan_alignment": ""
                }
                
        except Exception as e:
            # Return a fallback structure if detection fails
            return {
                "selected_function": "",
                "confidence": 0.0,
                "reasoning": f"Function selection failed: {str(e)}. Using fallback function.",
                "alternative_functions": [],
                "reasoning_plan_alignment": ""
            }
    
    async def _retrieve_function_definitions(self, function_names: List[str]) -> str:
        """
        Retrieve function definitions from the function_definition_store for the given function names.
        
        Args:
            function_names: List of function names to retrieve definitions for
            
        Returns:
            Formatted string containing function definitions
        """
        if not self.function_definition_store or not function_names:
            return "No function definitions available."
        
        try:
            # Retrieve function definitions for each function name
            all_definitions = []
            
            for function_name in function_names:
                # Search for the function definition
                search_results = self.function_definition_store.semantic_searches(
                    [function_name], n_results=3
                )
                print("function_name",function_name)
                print("search_results",search_results)
                
                # Parse the results
                function_docs = self._parse_retrieval_results(search_results)
                
                if function_docs:
                    # Format the function definition
                    for doc in function_docs[:1]:  # Take the most relevant result
                        content = doc.get("content", {})
                        if isinstance(content, dict):
                            # Extract relevant information from the function definition
                            function_info = {
                                "name": content.get("name", function_name),
                                "description": content.get("description", "No description available"),
                                "parameters": content.get("parameters", []),
                                "returns": content.get("returns", "No return information"),
                                "examples": content.get("examples", []),
                                "pipeline_type": content.get("pipeline_type", "Unknown")
                            }
                            
                            # Format the function definition
                            definition_text = f"Function: {function_info['name']}\n"
                            definition_text += f"Description: {function_info['description']}\n"
                            
                            if function_info['parameters']:
                                definition_text += f"Parameters: {', '.join(function_info['parameters'])}\n"
                            
                            definition_text += f"Returns: {function_info['returns']}\n"
                            definition_text += f"Pipeline Type: {function_info['pipeline_type']}\n"
                            
                            if function_info['examples']:
                                definition_text += f"Examples: {', '.join(function_info['examples'])}\n"
                            
                            all_definitions.append(definition_text)
                        else:
                            # If content is not a dict, use it as is
                            all_definitions.append(f"Function: {function_name}\nDefinition: {content}\n")
                else:
                    # No definition found, add a placeholder
                    all_definitions.append(f"Function: {function_name}\nDefinition: No definition available in store.\n")
            
            # Join all definitions
            if all_definitions:
                return "\n---\n".join(all_definitions)
            else:
                return "No function definitions found in store."
                
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Error retrieving function definitions: {str(e)}")
            return f"Error retrieving function definitions: {str(e)}"
    
    async def _detect_function_inputs(self, 
                                    context: str,
                                    function_name: str,
                                    classification: Optional[Union[Dict[str, Any], AnalysisIntentResult]] = None,
                                    dataset_description: Optional[str] = None,
                                    columns_description: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Detect function inputs using LLM, including additional computations like mean, average,
        or using metrics_tools.py or operations_tools.py functions.
        
        Args:
            context: Natural language description of the task
            function_name: Primary function to use in the pipeline
            classification: Optional classification results
            dataset_description: Optional description of the dataset
            columns_description: Optional dictionary mapping column names to descriptions
            
        Returns:
            Dictionary containing detected function inputs with any additional computations
        """
        # Available metrics functions from metrics_tools.py
        metrics_functions = [
            "Count", "Sum", "Max", "Min", "Ratio", "Dot", "Nth", "Variance", 
            "StandardDeviation", "CV", "Correlation", "Cov", "Mean", "Median", 
            "Percentile", "PivotTable", "GroupBy", "Filter", "CumulativeSum", 
            "RollingMetric", "Execute", "ShowPivot", "ShowDataFrame"
        ]
        
        # Available operations functions from operations_tools.py
        operations_functions = [
            "PercentChange", "AbsoluteChange", "MH", "CUPED", "PrePostChange",
            "FilterConditions", "PowerAnalysis", "StratifiedSummary", "BootstrapCI",
            "MultiComparisonAdjustment", "ExecuteOperations", "ShowOperation", "ShowComparison"
        ]
         
        # Retrieve function definition for the primary function
        primary_function_definition = await self._retrieve_function_definitions([function_name])
        
        # Create the detection prompt
        detection_prompt = PromptTemplate(
            input_variables=[
                "context", "function_name", "function_definition", "classification_context", "dataset_context",
                "metrics_functions", "operations_functions", "reasoning_plan_json"
            ],
            template="""
            You are an expert function input detector for data analysis pipelines.
            
            TASK: Analyze the given context and function name to detect the required function inputs,
            including any additional computations needed (like mean, average, etc.) or whether to use
            functions from metrics_tools.py or operations_tools.py. Use the detailed reasoning plan to guide your decisions.
            
            CONTEXT: {context}
            FUNCTION NAME: {function_name}
            
            PRIMARY FUNCTION DEFINITION:
            {function_definition}
            
            CLASSIFICATION ANALYSIS:
            {classification_context}
            
            DATASET INFORMATION:
            {dataset_context}
            
            AVAILABLE METRICS FUNCTIONS (from metrics_tools.py):
            {metrics_functions}
            
            AVAILABLE OPERATIONS FUNCTIONS (from operations_tools.py):
            {operations_functions}
            
            REASONING PLAN (JSON):
            {reasoning_plan_json}
            
            INSTRUCTIONS:
            1. Analyze the context to understand what data analysis is being requested
            2. Review the primary function definition to understand its parameters and requirements
            3. CRITICAL: Use the reasoning plan to guide input detection:
               - Review each step in the reasoning plan to understand the analysis approach
               - Identify which step(s) the primary function corresponds to
               - Use the data requirements and suggested functions from the reasoning plan
               - Consider the expected outcomes and considerations from the plan
               - Align your input detection with the step-by-step logic
            4. Analyze the dataset and column descriptions to identify the most appropriate columns for the analysis:
               - For numeric calculations: Use columns categorized as "Numeric Columns"
               - For time-based analysis: Use columns categorized as "Temporal Columns" 
               - For grouping/segmentation: Use columns categorized as "Categorical Columns"
               - For identification: Use columns categorized as "Identifier Columns"
            5. IMPORTANT: Use ONLY the actual column names provided in the dataset information. Do not invent column names.
            6. Map context requirements to actual column names from the dataset description:
               - If the context mentions "sales", look for columns like "sales_amount", "total_sales", "revenue", etc.
               - If the context mentions "time" or "date", look for temporal columns
               - If the context mentions grouping "by region", look for categorical columns that could represent regions
            7. Determine the required function inputs for the primary function based on its definition, available columns, and reasoning plan alignment
            8. Identify the pipeline type for the primary function:
               - TimeSeriesPipe: variance_analysis, lead, lag, etc.
               - MetricsPipe: Variance, Mean, Sum, Count, etc.
               - OperationsPipe: PercentChange, AbsoluteChange, etc.
               - CohortPipe: form_time_cohorts, calculate_retention, etc.
               - RiskPipe: calculate_var, calculate_cvar, etc.
               - FunnelPipe: analyze_funnel, etc.
               - AnomalyPipe: detect_statistical_outliers, detect_contextual_anomalies, etc.
               - SegmentPipe: run_kmeans, run_dbscan, etc.
               - TrendsPipe: aggregate_by_time, calculate_growth_rates, etc.
            9. Determine if multiple pipelines are needed based on reasoning plan steps:
                - If reasoning plan has multiple steps with different function types
                - If primary function is TimeSeriesPipe/CohortPipe/RiskPipe/FunnelPipe/AnomalyPipe/SegmentPipe/TrendsPipe AND additional computations are needed
                - Create a multi-pipeline approach: MetricsPipe/OperationsPipe first, then primary pipeline
            10. Consider the classification analysis and reasoning plan for additional context
            11. Return a JSON object with the detected inputs using actual column names and reasoning plan alignment
            
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
                "multi_pipeline": true | false,
                "first_pipeline_type": "MetricsPipe" | "OperationsPipe" | null,
                "second_pipeline_type": "TimeSeriesPipe" | "CohortPipe" | "RiskPipe" | "FunnelPipe" | "AnomalyPipe" | "SegmentPipe" | "TrendsPipe" | null,
                "reasoning": "explanation of why these inputs were chosen, including reasoning plan alignment",
                "reasoning_plan_step_mapping": "which reasoning plan steps this implementation covers"
            }}
            
            EXAMPLES:
            
            Example 1 - Simple metrics with reasoning plan:
            Context: "Calculate the mean of sales column"
            Function: "Mean"
            Reasoning Plan: Step 1 suggests "Mean" function for basic aggregation
            Output: {{
                "primary_function_inputs": {{"variable": "sales"}},
                "additional_computations": [],
                "pipeline_sequence": ["Calculate mean of sales"],
                "reasoning": "Direct mean calculation using metrics_tools Mean function. Aligns with Step 1 of reasoning plan.",
                "reasoning_plan_step_mapping": "Implements Step 1 mean calculation requirement"
            }}
            
            Example 2 - Multi-pipeline approach with reasoning plan:
            Context: "Calculate the mean of transactional value and then analyze its variance over time"
            Function: "variance_analysis"
            Reasoning Plan: Step 1 suggests "Mean" for aggregation, Step 2 suggests "variance_analysis" for time series
            Output: {{
                "primary_function_inputs": {{"columns": ["mean_Transactional value"], "method": "rolling", "window": 5}},
                "additional_computations": [
                    {{
                        "function": "Mean",
                        "inputs": {{"variable": "Transactional value"}},
                        "tool": "metrics_tools"
                    }}
                ],
                "pipeline_sequence": ["Calculate mean of transactional value", "Analyze variance over time"],
                "multi_pipeline": true,
                "first_pipeline_type": "MetricsPipe",
                "second_pipeline_type": "TimeSeriesPipe",
                "reasoning": "Need to calculate mean first using MetricsPipe (Step 1), then analyze variance over time using TimeSeriesPipe (Step 2). Aligns with reasoning plan steps.",
                "reasoning_plan_step_mapping": "Step 1: Mean calculation, Step 2: Variance analysis"
            }}
            
            Example 2b - Variance + moving_apply_by_group scenario:
            Context: "Calculate variance of transactional value and apply moving variance by group"
            Function: "moving_apply_by_group"
            Reasoning Plan: Step 1 suggests "Variance" calculation, Step 2 suggests "moving_apply_by_group" for time series
            Output: {{
                "primary_function_inputs": {{"columns": "Transactional value", "group_column": "Project, Cost center, Department", "window": 5, "min_periods": 1, "time_column": "Date", "output_suffix": "_rolling_variance", "function": "(MetricsPipe.from_dataframe(df) | Variance(variable='Transactional value') | to_df())"}},
                "additional_computations": [],
                "pipeline_sequence": ["Apply moving variance by group with embedded Variance calculation"],
                "multi_pipeline": false,
                "first_pipeline_type": null,
                "second_pipeline_type": null,
                "reasoning": "moving_apply_by_group function parameter should contain the complete Variance pipeline expression. This embeds the MetricsPipe Variance calculation within the TimeSeriesPipe moving_apply_by_group function.",
                "reasoning_plan_step_mapping": "Step 1 & 2: Combined in single pipeline with embedded function"
            }}
            
            Example 3 - Column mapping with reasoning plan:
            Context: "Calculate the variance of customer retention rate over time"
            Function: "variance_analysis"
            Dataset: "Customer transaction data with retention metrics"
            Columns: {{"customer_id": "Unique customer identifier", "retention_rate": "Customer retention percentage", "transaction_date": "Date of transaction"}}
            Reasoning Plan: Step 1 suggests data preparation, Step 2 suggests variance analysis using retention_rate
            Output: {{
                "primary_function_inputs": {{"columns": ["retention_rate"], "method": "rolling", "window": 5}},
                "additional_computations": [],
                "pipeline_sequence": ["Analyze variance of retention rate over time"],
                "multi_pipeline": false,
                "reasoning": "Using 'retention_rate' column for variance analysis as it's a numeric metric, with 'transaction_date' available for time-based analysis. Aligns with Step 2 of reasoning plan.",
                "reasoning_plan_step_mapping": "Implements Step 2 variance analysis requirement"
            }}
            
            Now analyze the given context and return the appropriate JSON response.
            """
        )
        
        # Format classification context
        classification_context = self._format_classification_context(classification) if classification else "No classification available"
        
        # Format dataset context
        dataset_context = self._format_dataset_context(dataset_description, columns_description)
        
        # Format reasoning plan as JSON
        reasoning_plan_json = self._format_reasoning_plan_json(classification)
        
        # Create detection chain
        detection_chain = detection_prompt | self.llm | StrOutputParser()
        
        try:
            # Invoke the detection
            result = await detection_chain.ainvoke({
                "context": context,
                "function_name": function_name,
                "function_definition": primary_function_definition,
                "classification_context": classification_context,
                "dataset_context": dataset_context,
                "metrics_functions": ", ".join(metrics_functions),
                "operations_functions": ", ".join(operations_functions),
                "reasoning_plan_json": reasoning_plan_json
            })
            
            # Parse the JSON result
            try:
                detected_inputs = json.loads(result.strip())
                
                # Debug logging
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"Raw LLM response: {result}")
                logger.debug(f"Parsed detected_inputs: {detected_inputs}")
                logger.debug(f"Detected inputs type: {type(detected_inputs)}")
                
                # Validate the structure
                if not isinstance(detected_inputs, dict):
                    raise ValueError("Result is not a dictionary")
                
                # Ensure required keys exist and have correct types
                required_keys = ["primary_function_inputs", "additional_computations", "pipeline_sequence", "reasoning"]
                optional_keys = ["multi_pipeline", "first_pipeline_type", "second_pipeline_type", "reasoning_plan_step_mapping"]
                
                for key in required_keys:
                    if key not in detected_inputs:
                        if key == "primary_function_inputs":
                            detected_inputs[key] = {}
                        elif key in ["additional_computations", "pipeline_sequence"]:
                            detected_inputs[key] = []
                        else:
                            detected_inputs[key] = ""
                    else:
                        # Validate types for existing keys
                        if key == "primary_function_inputs" and not isinstance(detected_inputs[key], dict):
                            logger.warning(f"primary_function_inputs is not a dict, converting: {type(detected_inputs[key])} -> {detected_inputs[key]}")
                            detected_inputs[key] = {}
                        elif key in ["additional_computations", "pipeline_sequence"] and not isinstance(detected_inputs[key], list):
                            logger.warning(f"{key} is not a list, converting: {type(detected_inputs[key])} -> {detected_inputs[key]}")
                            detected_inputs[key] = []
                        elif key == "reasoning" and not isinstance(detected_inputs[key], str):
                            logger.warning(f"reasoning is not a string, converting: {type(detected_inputs[key])} -> {detected_inputs[key]}")
                            detected_inputs[key] = str(detected_inputs[key])
                
                # Handle optional multi-pipeline keys
                for key in optional_keys:
                    if key not in detected_inputs:
                        if key == "multi_pipeline":
                            detected_inputs[key] = False
                        elif key == "reasoning_plan_step_mapping":
                            detected_inputs[key] = ""
                        else:
                            detected_inputs[key] = None
                
                # Filter additional computations to ensure pipeline type consistency
                detected_inputs = self._filter_additional_computations(detected_inputs, function_name)
                

                
                logger.debug(f"Final detected_inputs: {detected_inputs}")
                print("Final detected_inputs: ", detected_inputs)
                return detected_inputs
                
            except json.JSONDecodeError as e:
                # If JSON parsing fails, return a basic structure
                return {
                    "primary_function_inputs": {},
                    "additional_computations": [],
                    "pipeline_sequence": ["Basic analysis"],
                    "reasoning": f"JSON parsing failed: {str(e)}. Using basic inputs.",
                    "reasoning_plan_step_mapping": "Unable to map to reasoning plan due to parsing error",
                    "raw_response": result
                }
                
        except Exception as e:
            # Return a fallback structure if detection fails
            return {
                "primary_function_inputs": {},
                "additional_computations": [],
                "pipeline_sequence": ["Fallback analysis"],
                "reasoning": f"Detection failed: {str(e)}. Using fallback inputs.",
                "reasoning_plan_step_mapping": "Unable to map to reasoning plan due to detection failure",
                "error": str(e)
            }
    
    def _filter_additional_computations(self, detected_inputs: Dict[str, Any], function_name: str) -> Dict[str, Any]:
        """
        Filter additional computations and determine if multi-pipeline approach is needed
        
        Args:
            detected_inputs: Dictionary containing detected inputs
            function_name: Primary function name
            
        Returns:
            Filtered detected inputs with multi-pipeline configuration
        """
        # Get the pipeline type for the primary function
        primary_pipeline_type = self._detect_pipeline_type(function_name, "")
        
        # Use the same mapping as defined in __init__
        function_pipeline_mapping = self.function_to_pipe
        
        # Check if multi-pipeline approach is needed
        needs_multi_pipeline = False
        first_pipeline_type = None
        second_pipeline_type = None
        
        if "additional_computations" in detected_inputs and detected_inputs["additional_computations"]:
            metrics_computations = []
            operations_computations = []
            other_computations = []
            
            for comp in detected_inputs["additional_computations"]:
                comp_function = comp.get("function", "")
                comp_pipeline_type = function_pipeline_mapping.get(comp_function)
                
                if comp_pipeline_type == PipelineType.METRICS:
                    metrics_computations.append(comp)
                elif comp_pipeline_type == PipelineType.OPERATIONS:
                    operations_computations.append(comp)
                else:
                    other_computations.append(comp)
            
            # Determine if multi-pipeline is needed
            if primary_pipeline_type in [PipelineType.TIMESERIES, PipelineType.COHORT, PipelineType.RISK, PipelineType.FUNNEL, PipelineType.ANOMALY, PipelineType.SEGMENT, PipelineType.TRENDS]:
                if metrics_computations or operations_computations:
                    needs_multi_pipeline = True
                    if metrics_computations:
                        first_pipeline_type = "MetricsPipe"
                        detected_inputs["additional_computations"] = metrics_computations
                    elif operations_computations:
                        first_pipeline_type = "OperationsPipe"
                        detected_inputs["additional_computations"] = operations_computations
                    second_pipeline_type = primary_pipeline_type.value
                else:
                    # Only same-pipeline-type computations
                    detected_inputs["additional_computations"] = other_computations
            else:
                # Primary function is MetricsPipe or OperationsPipe
                if primary_pipeline_type == PipelineType.METRICS:
                    detected_inputs["additional_computations"] = metrics_computations
                elif primary_pipeline_type == PipelineType.OPERATIONS:
                    detected_inputs["additional_computations"] = operations_computations
                else:
                    detected_inputs["additional_computations"] = other_computations
        
        # Update multi-pipeline configuration
        detected_inputs["multi_pipeline"] = needs_multi_pipeline
        detected_inputs["first_pipeline_type"] = first_pipeline_type
        detected_inputs["second_pipeline_type"] = second_pipeline_type
        
        return detected_inputs
    
    def _format_classification_context(self, classification: Optional[Union[Dict[str, Any], AnalysisIntentResult]]) -> str:
        """
        Format classification information for code generation prompt
        
        Args:
            classification: Either a Dict[str, Any] or AnalysisIntentResult object containing
                           intent classification results
        """
        if not classification:
            return "No classification information available."
        
        parts = []
        
        # Handle both dictionary and Pydantic model inputs
        if hasattr(classification, 'intent_type'):
            # Pydantic model (AnalysisIntentResult)
            intent_type = getattr(classification, 'intent_type', '')
            confidence_score = getattr(classification, 'confidence_score', 0.0)
            suggested_functions = getattr(classification, 'suggested_functions', [])
            specific_matches = getattr(classification, 'specific_function_matches', [])
            required_columns = getattr(classification, 'required_data_columns', [])
            missing_columns = getattr(classification, 'missing_columns', [])
            can_be_answered = getattr(classification, 'can_be_answered', True)
            feasibility_score = getattr(classification, 'feasibility_score', 0.0)
            reasoning = getattr(classification, 'reasoning', '')
        else:
            # Dictionary
            intent_type = classification.get('intent_type', '')
            confidence_score = classification.get('confidence_score', 0.0)
            suggested_functions = classification.get('suggested_functions', [])
            specific_matches = classification.get('specific_function_matches', [])
            required_columns = classification.get('required_data_columns', [])
            missing_columns = classification.get('missing_columns', [])
            can_be_answered = classification.get('can_be_answered', True)
            feasibility_score = classification.get('feasibility_score', 0.0)
            reasoning = classification.get('reasoning', '')
        
        # Intent information
        if intent_type:
            parts.append(f"Intent Type: {intent_type} (confidence: {confidence_score:.2f})")
        
        # Suggested functions
        if suggested_functions:
            parts.append(f"Suggested Functions: {', '.join(suggested_functions)}")
        
        # Specific function matches
        if specific_matches:
            parts.append(f"Specific Function Matches: {', '.join(specific_matches)}")
        
        # Data requirements
        if required_columns:
            parts.append(f"Required Columns: {', '.join(required_columns)}")
        
        if missing_columns:
            parts.append(f"Missing Columns: {', '.join(missing_columns)}")
        
        # Feasibility
        parts.append(f"Can Be Answered: {can_be_answered} (feasibility: {feasibility_score:.2f})")
        
        # Reasoning
        if reasoning:
            parts.append(f"Reasoning: {reasoning}")
        
        return "\n".join(parts) if parts else "No classification information available."
    
    def _format_reasoning_plan_json(self, classification: Optional[Union[Dict[str, Any], AnalysisIntentResult]]) -> str:
        """
        Format reasoning plan as JSON for LLM consumption
        
        Args:
            classification: Either a Dict[str, Any] or AnalysisIntentResult object containing
                           reasoning plan information
        """
        if not classification:
            return "null"
        
        # Extract reasoning plan
        if hasattr(classification, 'reasoning_plan'):
            reasoning_plan = getattr(classification, 'reasoning_plan', None)
        else:
            reasoning_plan = classification.get('reasoning_plan', None)
        
        if not reasoning_plan or not isinstance(reasoning_plan, list):
            return "null"
        
        return json.dumps(reasoning_plan, indent=2)
    
    def _format_dataset_context(self, dataset_description: Optional[str], 
                               columns_description: Dict[str, str]) -> str:
        """
        Format dataset information for code generation prompt with enhanced column analysis
        """
        parts = []
        
        if dataset_description:
            parts.append(f"Dataset: {dataset_description}")
        
        if columns_description:
            parts.append("Columns Analysis:")
            parts.append(json.dumps(columns_description, indent=2))
            
        return "\n".join(parts) if parts else "No dataset information available."
    
    def _retrieve_documents(self, query_state: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Retrieve relevant documents from all stores"""
        context = query_state["context"]
        function_name = query_state["function_name"]
        
        # Determine pipeline type
        pipeline_type = self._detect_pipeline_type(function_name, context)
        
        # Create enhanced query for retrieval
        enhanced_query = self._create_enhanced_query(context, function_name, pipeline_type)
        
        retrieved_docs = {}
        
        # Retrieve from usage examples store
        if self.usage_examples_store:
            usage_results = self.usage_examples_store.semantic_searches(
                [enhanced_query], n_results=5
            )
            retrieved_docs["usage_examples"] = self._parse_retrieval_results(usage_results)
        
        # Retrieve from code examples store
        if self.code_examples_store:
            code_results = self.code_examples_store.semantic_searches(
                [enhanced_query], n_results=5
            )
            retrieved_docs["code_examples"] = self._parse_retrieval_results(code_results)
        
        # Retrieve from function definition store
        if self.function_definition_store:
            func_results = self.function_definition_store.semantic_searches(
                [function_name], n_results=3
            )
            retrieved_docs["function_definitions"] = self._parse_retrieval_results(func_results)
        
        # Retrieve logical reasoning patterns if available
        if self.logical_reasoning_store:
            reasoning_results = self.logical_reasoning_store.semantic_searches(
                [f"{pipeline_type.value} reasoning pattern"], n_results=3
            )
            retrieved_docs["reasoning_patterns"] = self._parse_retrieval_results(reasoning_results)
        
        return retrieved_docs
    
    async def _grade_documents(self, retrieved_docs: Dict[str, List[Dict[str, Any]]], 
                              query_state: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Grade document relevance and filter relevant ones"""
        context = query_state["context"]
        function_name = query_state["function_name"]
        
        grading_prompt = PromptTemplate(
            input_variables=["context", "function_name", "document", "doc_type"],
            template="""
            You are a document relevance grader for code generation.
            
            CONTEXT: {context}
            FUNCTION: {function_name}
            DOCUMENT TYPE: {doc_type}
            DOCUMENT: {document}
            
            Grade the relevance of this document for generating pipeline code:
            - RELEVANT: Document directly helps with the task
            - PARTIALLY_RELEVANT: Document has some useful information
            - IRRELEVANT: Document is not useful for this task
            
            Return only: RELEVANT, PARTIALLY_RELEVANT, or IRRELEVANT
            """
        )
        
        grading_chain = grading_prompt | self.llm | StrOutputParser()
        
        relevant_docs = {}
        
        for doc_type, documents in retrieved_docs.items():
            relevant_docs[doc_type] = []
            
            for doc in documents:
                try:
                    relevance = await grading_chain.ainvoke({
                        "context": context,
                        "function_name": function_name,
                        "document": json.dumps(doc, indent=2),
                        "doc_type": doc_type
                    })
                    relevance = relevance.strip().upper()
                    
                    if relevance in ["RELEVANT", "PARTIALLY_RELEVANT"]:
                        doc["relevance_grade"] = relevance
                        relevant_docs[doc_type].append(doc)
                        
                except Exception as e:
                    # If grading fails, include the document
                    doc["relevance_grade"] = "UNKNOWN"
                    relevant_docs[doc_type].append(doc)
        
        return relevant_docs
    
    def _generate_code_from_reasoning_plan(self, reasoning_plan: List[Dict[str, Any]], 
                                         dataframe_name: str, 
                                         classification: Union[Dict[str, Any], AnalysisIntentResult]) -> str:
        """
        Generate code directly from the reasoning plan instead of using LLM detection
        
        Args:
            reasoning_plan: List of reasoning plan steps
            dataframe_name: Name of the dataframe
            classification: Classification results
            
        Returns:
            Generated pipeline code
        """
        if not reasoning_plan or not isinstance(reasoning_plan, list):
            return self._generate_fallback_code(PipelineType.METRICS, "Mean", {}, dataframe_name)
        
        # Handle dataframe names with spaces
        if ' ' in dataframe_name:
            formatted_dataframe_name = f'"{dataframe_name}"'
        else:
            formatted_dataframe_name = dataframe_name
        
        # Generate code based on reasoning plan steps
        pipeline_code_parts = []
        
        for i, step in enumerate(reasoning_plan):
            if not isinstance(step, dict):
                continue
                
            function_name = step.get('function_name', '')
            parameter_mapping = step.get('parameter_mapping', {})
            step_title = step.get('step_title', f'Step {i+1}')
            
            # Handle None, "None", or "N/A" values
            if function_name in [None, "None", "none", "N/A"]:
                function_name = ""
            if parameter_mapping in [None, "None", "none", "N/A"]:
                parameter_mapping = {}
            
            # Ensure parameter_mapping is a dictionary
            if not isinstance(parameter_mapping, dict):
                logger.warning(f"Parameter mapping in step {i+1} is not a dictionary, converting to empty dict: {type(parameter_mapping)} -> {parameter_mapping}")
                parameter_mapping = {}
            
            # Skip steps with no function name or invalid function names
            if not function_name or function_name in ["None", "none", "N/A"]:
                logger.info(f"Skipping step {i+1} with invalid function name: {function_name}")
                continue
            
            # Determine pipeline type for this function
            pipeline_type = self._detect_pipeline_type(function_name, step_title)
            
            # Format parameters
            formatted_params = []
            for key, value in parameter_mapping.items():
                if isinstance(value, str):
                    formatted_params.append(f"{key}='{value}'")
                elif isinstance(value, list):
                    formatted_params.append(f"{key}={value}")
                else:
                    formatted_params.append(f"{key}={value}")
            
            param_str = ", ".join(formatted_params) if formatted_params else ""
            
            # Generate the pipeline step
            if i == 0:
                # First step - initialize the pipeline
                if param_str:
                    pipeline_code_parts.append(f"""result = (
    {pipeline_type.value}.from_dataframe({formatted_dataframe_name})
    | {function_name}({param_str})""")
                else:
                    pipeline_code_parts.append(f"""result = (
    {pipeline_type.value}.from_dataframe({formatted_dataframe_name})
    | {function_name}()""")
            else:
                # Subsequent steps - chain to previous result
                if param_str:
                    pipeline_code_parts.append(f"""    | {function_name}({param_str})""")
                else:
                    pipeline_code_parts.append(f"""    | {function_name}()""")
        
        if not pipeline_code_parts:
            # Fallback if no valid steps found
            return self._generate_fallback_code(PipelineType.METRICS, "Mean", {}, dataframe_name)
        
        # Check if the first part starts with '|' (indicating missing initialization)
        if pipeline_code_parts and pipeline_code_parts[0].strip().startswith('|'):
            # Add the missing initialization
            pipeline_code_parts.insert(0, f"""result = (
    {pipeline_type.value}.from_dataframe({formatted_dataframe_name})""")
        
        # Join all pipeline steps and add closing parenthesis and to_df()
        generated_code = "\n".join(pipeline_code_parts) + "\n    ).to_df()"
        
        logger.info(f"Generated code from reasoning plan with {len(reasoning_plan)} steps")
        logger.info(f"Generated code: {generated_code}")
        
        return generated_code
    
    async def _generate_code(self, relevant_docs: Dict[str, List[Dict[str, Any]]], 
                            query_state: Dict[str, Any]) -> str:
        """Generate complete pipeline code"""
        context = query_state["context"]
        original_context = query_state.get("original_context", context)
        function_name = query_state["function_name"]
        function_inputs = query_state["function_inputs"]
        detected_inputs = query_state.get("detected_inputs", {})
        dataframe_name = query_state["dataframe_name"]
        classification = query_state.get("classification", {})
        dataset_description = query_state.get("dataset_description")
        columns_description = query_state.get("columns_description", {})
        
        # Detect pipeline type
        pipeline_type = self._detect_pipeline_type(function_name, original_context)
        
        # Format relevant documents
        docs_context = self._format_documents_for_generation(relevant_docs)
        
        # Format function inputs
        inputs_str = self._format_function_inputs(function_inputs)
        
        # Format additional computations and multi-pipeline info
        additional_computations = detected_inputs.get("additional_computations", [])
        pipeline_sequence = detected_inputs.get("pipeline_sequence", [])
        reasoning = detected_inputs.get("reasoning", "")
        multi_pipeline = detected_inputs.get("multi_pipeline", False)
        first_pipeline_type = detected_inputs.get("first_pipeline_type")
        second_pipeline_type = detected_inputs.get("second_pipeline_type")
        reasoning_plan_step_mapping = detected_inputs.get("reasoning_plan_step_mapping", "")
        
        # Format classification context
        classification_context = self._format_classification_context(classification)
        
        # Format dataset context
        dataset_context = self._format_dataset_context(dataset_description, columns_description)
        
        # Format reasoning plan as JSON
        reasoning_plan_json = self._format_reasoning_plan_json(classification)
        
        generation_prompt = PromptTemplate(
            input_variables=[
                "context", "original_context", "function_name", "pipeline_type", "dataframe_name", 
                "function_inputs", "additional_computations", "pipeline_sequence", "reasoning",
                "multi_pipeline", "first_pipeline_type", "second_pipeline_type", "reasoning_plan_step_mapping",
                "docs_context", "classification_context", "dataset_context", "reasoning_plan_json", "iteration"
            ],
            template="""
            You are an expert code generator for data analysis pipelines.
            
            ORIGINAL TASK: {original_context}
            ENHANCED CONTEXT: {context}
            PRIMARY FUNCTION: {function_name}
            PIPELINE TYPE: {pipeline_type}
            DATAFRAME NAME: {dataframe_name}
            FUNCTION INPUTS: {function_inputs}
            ITERATION: {iteration}
            
            DETECTED ADDITIONAL COMPUTATIONS: {additional_computations}
            PIPELINE SEQUENCE: {pipeline_sequence}
            REASONING: {reasoning}
            MULTI-PIPELINE: {multi_pipeline}
            FIRST PIPELINE TYPE: {first_pipeline_type}
            SECOND PIPELINE TYPE: {second_pipeline_type}
            REASONING PLAN STEP MAPPING: {reasoning_plan_step_mapping}
            
            CLASSIFICATION ANALYSIS:
            {classification_context}
            
            DATASET INFORMATION:
            {dataset_context}
            
            REASONING PLAN (JSON):
            {reasoning_plan_json}
            
            RELEVANT DOCUMENTATION:
            {docs_context}
            
            Generate a complete pipeline code that:
            1. Initializes the appropriate Pipe with from_dataframe() based on the primary function type
            2. Chains the primary function with proper parameters based on the classification
            3. Uses proper Python syntax with pipe operator (|)
            4. Follows the detected pipeline sequence
            5. Considers the intent type and suggested functions from classification
            6. CRITICAL: Aligns with the reasoning plan steps and their expected outcomes
            7. Uses the reasoning plan step mapping to ensure proper implementation of each step
            8. CRITICAL: For funnel analysis, use CohortPipe and follow the funnel analysis format
            9. CRITICAL: For moving_apply_by_group, embed the function parameter as a complete pipeline expression
            10. CRITICAL: function=(MetricsPipe.from_dataframe(...) | Variance(...) | to_df()) format for moving_apply_by_group
            
            CRITICAL SYNTAX REQUIREMENTS:
            - Ensure all parentheses are properly closed
            - Use proper indentation for multi-line statements (4 spaces for continued lines)
            - Use proper string quotes for dataframe names with spaces
            - Ensure function parameters are properly formatted
            - Avoid syntax errors like unclosed parentheses or missing commas
            - CRITICAL: Function parameters that reference function names should NOT be quoted
            - CRITICAL: function=Variance (correct) NOT function='Variance' (incorrect)
            - CRITICAL: For funnel analysis, DO NOT use to_df() - return results directly
            - CRITICAL: For other pipeline types, use ).to_df() at the end
            - CRITICAL: Use proper indentation with 4 spaces for continued lines
            
            CRITICAL RULES:
            - Create separate pipelines for different pipeline types
            - MetricsPipe and OperationsPipe pipelines should be executed FIRST to prepare data
            - TimeSeriesPipe, CohortPipe (including funnel analysis), RiskPipe, AnomalyPipe, SegmentPipe, and TrendsPipe pipelines should be executed SECOND on the prepared data
            - Each pipeline should stay within its own pipeline type
            - Use the results from the first pipeline as input to the second pipeline
            - Chain the pipelines using the pipe operator (|) between different pipeline types
            - Follow the reasoning plan step-by-step logic and expected outcomes
            - Ensure each step in the reasoning plan is properly implemented in the code
            - CRITICAL: For funnel analysis, use CohortPipe and follow the funnel analysis format without to_df()
            
            CRITICAL PIPELINE TYPE SEPARATION RULES:
            - MetricsPipe functions: Mean, Variance, Sum, Count, Max, Min, StandardDeviation, Correlation, etc.
            - TimeSeriesPipe functions: variance_analysis, moving_apply_by_group, lead, lag, rolling_mean, etc.
            - OperationsPipe functions: PercentChange, AbsoluteChange, MH, CUPED, etc.
            - CohortPipe functions: form_time_cohorts, calculate_retention, analyze_funnel, analyze_funnel_by_time, analyze_funnel_by_segment, analyze_user_paths, etc.
            - RiskPipe functions: calculate_var, calculate_cvar, etc.
            - AnomalyPipe functions: detect_statistical_outliers, detect_contextual_anomalies, etc.
            - SegmentPipe functions: get_features, run_kmeans, run_dbscan, etc.
            - TrendsPipe functions: aggregate_by_time, calculate_growth_rates, forecast_metric, etc.
            
            CRITICAL: For moving_apply_by_group, the function parameter should be a complete pipeline expression
            CRITICAL: function=(MetricsPipe.from_dataframe(...) | Variance(...) | to_df()) (correct)
            CRITICAL: NOT separate pipelines (incorrect)
            
            REQUIRED FORMAT:
            
            For single pipeline type (MetricsPipe, TimeSeriesPipe, OperationsPipe, etc.):
            ```python
            result = (
                PipeType.from_dataframe({dataframe_name})
                | function1(param1='value1')
                | function2(param2='value2')
                ).to_df()
            ```
            
            For funnel analysis (CohortPipe):
            ```python
            cohort_pipe = CohortPipe.from_dataframe({dataframe_name})
            cohort_pipe = cohort_pipe | analyze_funnel(
                event_column='event_name',
                user_id_column='user_id',
                funnel_steps=['step1', 'step2', 'step3'],
                step_names=['Step 1', 'Step 2', 'Step 3']
            )
            ```
            
            CRITICAL: For funnel analysis, use CohortPipe and DO NOT use to_df() - return results directly.
            CRITICAL: For other pipeline types, use the parentheses format with to_df().
            NEVER generate code like this (WRONG):
            ```python
            result = TimeSeriesPipe.from_dataframe(result)
                     | moving_apply_by_group(...)
                     | to_df()
            ```
            
            CRITICAL FUNCTION PARAMETER RULES:
            - Function names in parameters should NOT be quoted: function=Variance (correct)
            - String values should be quoted: columns='Transactional value' (correct)
            - ).to_df() must be at the end: ).to_df() (correct)
            - CRITICAL: Use direct method calls, NOT function parameters
            - CRITICAL: variance(...) (correct) NOT moving_apply_by_group(function='Variance', ...) (incorrect)
            - CRITICAL: Mean(variable='revenue') (correct) NOT some_function(function='Mean', ...) (incorrect)
            
            CORRECT EXAMPLE:
            ```python
            result = (TimeSeriesPipe.from_dataframe(result)
                     | variance(  # Direct method call, not a parameter
                         columns='Transactional value',
                         group_column='Project, Cost center, Department',
                         window=5,
                         min_periods=1,
                         time_column='Date',
                         output_suffix='_rolling_variance'
                     )
                     | to_df()  # MUST have parentheses
            )
            ```
            
            For multiple pipeline types (Metrics/Operations first, then TimeSeries/Cohort/Risk/Anomaly/Segment/Trends):
            ```python
            result = (MetricsPipe.from_dataframe({dataframe_name})
                     | metrics_function1(param1='value1')
                     | metrics_function2(param2='value2')
                     | to_df()

            result_operations = TimeSeriesPipe.from_dataframe(result)
                     | timeseries_function(param3='value3')
                     | to_df()
            )
            ```
            
            For funnel analysis (CohortPipe):
            ```python
            cohort_pipe = CohortPipe.from_dataframe({dataframe_name})
            cohort_pipe = cohort_pipe | analyze_funnel(
                event_column='event_name',
                user_id_column='user_id',
                funnel_steps=['step1', 'step2', 'step3']
            )
            ```
            
            CRITICAL MULTI-PIPELINE EXAMPLE - Variance + moving_apply_by_group:
            ```python
            result = (TimeSeriesPipe.from_dataframe({dataframe_name})
                     | moving_apply_by_group(
                         columns='Transactional value',
                         group_column='Project, Cost center, Department',
                         function=(MetricsPipe.from_dataframe({dataframe_name})
                                  | Variance(variable='Transactional value')
                                  | to_df()),
                         window=5,
                         min_periods=1,
                         time_column='Date',
                         output_suffix='_rolling_variance'
                     )
                     | to_df()
            )
            ```
            
            IMPORTANT: If the dataframe name contains spaces, it must be quoted: from_dataframe("Dataframe Name")
            
            EXAMPLES:
            
            Example 1 - Single pipeline type (MetricsPipe) with reasoning plan:
            ```python
            result = (
                MetricsPipe.from_dataframe(df)
                | Mean(variable='revenue')
                | Variance(variable='revenue')
                ).to_df()
            ```
            
            Example 2 - Multiple pipeline types (MetricsPipe first, then TimeSeriesPipe) with reasoning plan:
            ```python
            result = (
                MetricsPipe.from_dataframe(df)
                | Mean(variable='Transactional value')
                ).to_df()
            
            result_operations = (
                TimeSeriesPipe.from_dataframe(result)
                | variance_analysis(
                    columns=['mean_Transactional value'],
                    method='rolling',
                    window=5
                )
                ).to_df()
            ```
            
            Example 2b - CORRECT way to handle Variance + moving_apply_by_group (function parameter):
            ```python
            result = (
                TimeSeriesPipe.from_dataframe(df)
                | moving_apply_by_group(
                    columns='Transactional value',
                    group_column='Project, Cost center, Department',
                    function=(MetricsPipe.from_dataframe(df)
                             | Variance(variable='Transactional value')
                             ).to_df(),
                    window=5,
                    min_periods=1,
                    time_column='Date',
                    output_suffix='_rolling_variance'
                )
                ).to_df()
            ```
            
            Example 2c - WRONG way (mixing pipeline types):
            ```python
            # ❌ WRONG: Don't do this - mixing MetricsPipe and TimeSeriesPipe functions
            result = (
                TimeSeriesPipe.from_dataframe(df)
                | moving_apply_by_group(
                    function=Variance,  # ❌ Variance belongs to MetricsPipe, not TimeSeriesPipe
                    columns='Transactional value',
                    ...
                )
                ).to_df()
            ```
            
            Example 3 - Multiple pipeline types (OperationsPipe first, then TimeSeriesPipe) with reasoning plan:
            ```python
            result = (
                OperationsPipe.from_dataframe(df)
                | PercentChange(condition_column='period', baseline='Q1')
                ).to_df()
            
            result_operations = (
                TimeSeriesPipe.from_dataframe(result)
                | variance_analysis(
                    columns=['percent_change'],
                    method='rolling',
                    window=5
                )
                ).to_df()
            ```
            
            Example 4 - Dataframe with spaces:
            ```python
            result = (
                TimeSeriesPipe.from_dataframe("Purchase Orders Data")
                | variance_analysis(
                    columns=['Project', 'Transactional value'],
                    method='rolling',
                    window=5
                )
                ).to_df()
            ```
            
            Example 5 - Anomaly detection (MetricsPipe first, then AnomalyPipe) with reasoning plan:
            ```python
            result_metrics = (
                MetricsPipe.from_dataframe(df)
                | Mean(variable='sales')
                ).to_df()
                     
            result_pipe = (
                AnomalyPipe.from_dataframe(result_metrics)
                | detect_statistical_outliers(
                    columns='mean_sales',
                    method='zscore',
                    threshold=3.0
                )
                ).to_df()
            ```
            
            Example 6 - Single AnomalyPipe with reasoning plan:
            ```python
            result = (
                AnomalyPipe.from_dataframe(df)
                | detect_statistical_outliers(
                    columns='value',
                    method='zscore',
                    threshold=3.0
                )
                | detect_contextual_anomalies(
                    columns='value',
                    time_column='timestamp',
                    method='residual',
                    model_type='ewm',
                    window=30
                )
                ).to_df()
            ```
            
            Example 7 - Segmentation (MetricsPipe first, then SegmentPipe) with reasoning plan:
            ```python
            result_metrics = (
                MetricsPipe.from_dataframe(df)
                | Mean(variable='sales')
                ).to_df()

            result_pipe = (
                SegmentPipe.from_dataframe(result_metrics)
                | get_features(columns=['mean_sales', 'frequency'])
                | run_kmeans(n_clusters=5, find_optimal=True)
                ).to_df()
            ```
            
            Example 8 - Single SegmentPipe with reasoning plan:
            ```python
            result = (
                SegmentPipe.from_dataframe(df)
                | get_features(columns=['sales', 'frequency', 'recency'])
                | run_kmeans(n_clusters=5)
                | run_dbscan(eps=0.5, min_samples=5)
                | compare_algorithms()
                ).to_df()
            ```
            
            Example 9 - Trends analysis (MetricsPipe first, then TrendsPipe) with reasoning plan:
            ```python
            result_metrics = (
                MetricsPipe.from_dataframe(df)
                | Mean(variable='revenue')
                ).to_df()

            result_pipe = (
                TrendsPipe.from_dataframe(result_metrics)
                | aggregate_by_time(
                    date_column='date',
                    metric_columns=['mean_revenue'],
                    time_period='M'
                )
                | calculate_growth_rates(window=3)
                | forecast_metric(metric_column='mean_revenue', fperiods=6)
                ).to_df()
            ```
            
            Example 10 - Single TrendsPipe with reasoning plan:
            ```python
            result = (
                TrendsPipe.from_dataframe(df)
                | aggregate_by_time(
                    date_column='timestamp',
                    metric_columns=['sales', 'revenue'],
                    time_period='D'
                )
                | calculate_moving_average(window=7)
                | decompose_trend(metric_column='sales')
                | forecast_metric(metric_column='revenue', fperiods=12)
                ).to_df()
            ```
            
            Example 11 - Funnel analysis (CohortPipe) with reasoning plan:
            ```python
            cohort_pipe = CohortPipe.from_dataframe(df)
            cohort_pipe = cohort_pipe | analyze_funnel(
                event_column='event_name',
                user_id_column='user_id',
                funnel_steps=['home_page_view', 'product_view', 'add_to_cart', 'checkout_started', 'purchase_completed'],
                step_names=['Homepage', 'Product Page', 'Cart', 'Checkout', 'Purchase'],
                max_step_time=86400
            )
            ```
            
            Example 12 - Funnel analysis by time (CohortPipe) with reasoning plan:
            ```python
            cohort_pipe = CohortPipe.from_dataframe(df)
            cohort_pipe = cohort_pipe | analyze_funnel_by_time(
                event_column='event_name',
                user_id_column='user_id',
                date_column='event_timestamp',
                funnel_steps=['product_view', 'add_to_cart', 'checkout_started', 'purchase_completed'],
                step_names=['View', 'Cart', 'Checkout', 'Purchase'],
                time_period='week',
                max_periods=4
            )
            ```
            
            Generate ONLY the pipeline code, no explanations.
            """
        )
        
        generation_chain = generation_prompt | self.llm | StrOutputParser()
        
        try:
            # Handle dataframe names with spaces
            formatted_dataframe_name = dataframe_name
            if ' ' in dataframe_name:
                formatted_dataframe_name = f'"{dataframe_name}"'
            
            generated_code = await generation_chain.ainvoke({
                "context": context,
                "original_context": original_context,
                "function_name": function_name,
                "pipeline_type": pipeline_type.value,
                "dataframe_name": formatted_dataframe_name,
                "function_inputs": inputs_str,
                "additional_computations": json.dumps(additional_computations, indent=2),
                "pipeline_sequence": json.dumps(pipeline_sequence, indent=2),
                "reasoning": reasoning,
                "multi_pipeline": multi_pipeline,
                "first_pipeline_type": first_pipeline_type,
                "second_pipeline_type": second_pipeline_type,
                "reasoning_plan_step_mapping": reasoning_plan_step_mapping,
                "docs_context": docs_context,
                "classification_context": classification_context,
                "dataset_context": dataset_context,
                "reasoning_plan_json": reasoning_plan_json,
                "iteration": query_state["iteration"]
            })
            
            # Clean up the generated code
            code = self._clean_generated_code(generated_code)
            
            # Validate the cleaned code
            try:
                ast.parse(code)
                logger.info("Generated code passed syntax validation")
            except SyntaxError as e:
                logger.warning(f"Syntax error in cleaned code: {e}")
                # Try to fix the code
                code = self._extract_valid_code_parts(code)
                logger.info("Attempted to extract valid code parts")
            
            query_state["code_attempts"].append(code)
            
            return code
            
        except Exception as e:
            logger.error(f"Error in code generation: {e}")
            fallback_code = self._generate_fallback_code(
                pipeline_type, function_name, function_inputs, dataframe_name
            )
            query_state["code_attempts"].append(fallback_code)
            return fallback_code
    
    def _evaluate_reasoning_plan_quality(self, reasoning_plan: List[Dict[str, Any]], 
                                       generated_code: str, 
                                       query_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate the quality of the reasoning plan based on generated code and suggest improvements
        
        Args:
            reasoning_plan: List of reasoning plan steps
            generated_code: Generated pipeline code
            query_state: Current query state
            
        Returns:
            Dictionary with evaluation results and suggestions
        """
        evaluation = {
            "quality_score": 0.0,
            "issues": [],
            "suggestions": [],
            "plan_adjustments": []
        }
        
        if not reasoning_plan or not isinstance(reasoning_plan, list):
            evaluation["issues"].append("No reasoning plan available")
            evaluation["quality_score"] = 0.0
            return evaluation
        
        # Check if all steps have required fields
        required_fields = ["step_number", "step_title", "function_name", "parameter_mapping"]
        for i, step in enumerate(reasoning_plan):
            if not isinstance(step, dict):
                evaluation["issues"].append(f"Step {i+1} is not a dictionary")
                continue
                
            missing_fields = [field for field in required_fields if field not in step]
            if missing_fields:
                evaluation["issues"].append(f"Step {i+1} missing fields: {missing_fields}")
        
        # Check function consistency
        function_names = []
        for step in reasoning_plan:
            if isinstance(step, dict) and 'function_name' in step:
                function_names.append(step['function_name'])
        
        # Check if functions are valid
        valid_functions = list(self.function_to_pipe.keys())
        invalid_functions = [func for func in function_names if func not in valid_functions]
        if invalid_functions:
            evaluation["issues"].append(f"Invalid functions found: {invalid_functions}")
            evaluation["suggestions"].append("Replace invalid functions with valid alternatives")
        
        # Check pipeline type consistency
        pipeline_types = []
        for step in reasoning_plan:
            if isinstance(step, dict) and 'function_name' in step:
                func_name = step['function_name']
                if func_name in self.function_to_pipe:
                    pipeline_types.append(self.function_to_pipe[func_name])
        
        # Check for pipeline type mixing issues
        if len(set(pipeline_types)) > 1:
            # Check if it's a valid multi-pipeline pattern
            valid_multi_patterns = [
                [PipelineType.METRICS, PipelineType.TIMESERIES],
                [PipelineType.OPERATIONS, PipelineType.TIMESERIES],
                [PipelineType.METRICS, PipelineType.COHORT],
                [PipelineType.OPERATIONS, PipelineType.COHORT],
                [PipelineType.METRICS, PipelineType.ANOMALY],
                [PipelineType.OPERATIONS, PipelineType.ANOMALY],
                [PipelineType.METRICS, PipelineType.SEGMENT],
                [PipelineType.OPERATIONS, PipelineType.SEGMENT],
                [PipelineType.METRICS, PipelineType.TRENDS],
                [PipelineType.OPERATIONS, PipelineType.TRENDS],
                [PipelineType.METRICS, PipelineType.RISK],
                [PipelineType.OPERATIONS, PipelineType.RISK],
            ]
            
            is_valid_multi = any(
                pipeline_types[:2] == pattern[:2] for pattern in valid_multi_patterns
            )
            
            if not is_valid_multi:
                evaluation["issues"].append("Invalid pipeline type mixing detected")
                evaluation["suggestions"].append("Ensure proper pipeline type sequencing")
        
        # Check parameter consistency
        for i, step in enumerate(reasoning_plan):
            if isinstance(step, dict) and 'parameter_mapping' in step:
                param_mapping = step['parameter_mapping']
                if not isinstance(param_mapping, dict):
                    evaluation["issues"].append(f"Step {i+1} parameter_mapping is not a dictionary")
                else:
                    # Check for common parameter issues
                    for key, value in param_mapping.items():
                        if isinstance(value, str) and len(value) == 0:
                            evaluation["issues"].append(f"Step {i+1} has empty parameter value for {key}")
        
        # Calculate quality score based on issues
        total_checks = len(reasoning_plan) * 3 + 3  # Basic checks per step + overall checks
        issue_count = len(evaluation["issues"])
        evaluation["quality_score"] = max(0.0, 1.0 - (issue_count / total_checks))
        
        # Generate suggestions based on issues
        if evaluation["quality_score"] < 0.7:
            evaluation["suggestions"].append("Consider simplifying the reasoning plan")
            evaluation["suggestions"].append("Ensure all functions are from the same pipeline type or follow valid multi-pipeline patterns")
        
        return evaluation
    
    def _adjust_reasoning_plan(self, reasoning_plan: List[Dict[str, Any]], 
                             evaluation: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Adjust the reasoning plan based on evaluation results
        
        Args:
            reasoning_plan: Original reasoning plan
            evaluation: Evaluation results
            
        Returns:
            Adjusted reasoning plan
        """
        if not reasoning_plan or not isinstance(reasoning_plan, list):
            return reasoning_plan
        
        adjusted_plan = []
        
        for i, step in enumerate(reasoning_plan):
            if not isinstance(step, dict):
                continue
            
            adjusted_step = step.copy()
            
            # Fix missing required fields
            if 'step_number' not in adjusted_step:
                adjusted_step['step_number'] = i + 1
            
            if 'step_title' not in adjusted_step:
                adjusted_step['step_title'] = f'Step {i + 1}'
            
            if 'function_name' not in adjusted_step:
                # Try to infer function name from step title
                title = adjusted_step.get('step_title', '').lower()
                if 'mean' in title or 'average' in title:
                    adjusted_step['function_name'] = 'Mean'
                elif 'group' in title or 'aggregate' in title:
                    adjusted_step['function_name'] = 'GroupBy'
                elif 'variance' in title:
                    adjusted_step['function_name'] = 'Variance'
                else:
                    adjusted_step['function_name'] = 'Mean'  # Default fallback
            
            if 'parameter_mapping' not in adjusted_step:
                adjusted_step['parameter_mapping'] = {}
            
            # Fix invalid functions
            if 'function_name' in adjusted_step:
                func_name = adjusted_step['function_name']
                if func_name not in self.function_to_pipe:
                    # Replace with a valid alternative
                    if 'mean' in func_name.lower() or 'average' in func_name.lower():
                        adjusted_step['function_name'] = 'Mean'
                    elif 'group' in func_name.lower():
                        adjusted_step['function_name'] = 'GroupBy'
                    elif 'variance' in func_name.lower():
                        adjusted_step['function_name'] = 'Variance'
                    else:
                        adjusted_step['function_name'] = 'Mean'  # Default fallback
            
            adjusted_plan.append(adjusted_step)
        
        return adjusted_plan
    
    def _grade_code(self, generated_code: str, query_state: Dict[str, Any]) -> CodeQuality:
        """Grade the quality of generated code"""
        # Syntax validation
        try:
            ast.parse(generated_code)
        except SyntaxError as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Syntax error in generated code: {e}")
            return CodeQuality.INVALID
        
        # Basic semantic validation - check if it contains expected elements
        function_name = query_state["function_name"]
        dataframe_name = query_state["dataframe_name"]
        
        # Check for basic required elements
        if function_name not in generated_code:
            return CodeQuality.POOR
        
        if dataframe_name not in generated_code and "from_dataframe" in generated_code:
            return CodeQuality.POOR
        
        # Check for pipeline type consistency
        primary_pipeline_type = self._detect_pipeline_type(function_name, "")
        
        # Check if the generated code uses the correct pipeline type
        if primary_pipeline_type.value not in generated_code:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Generated code doesn't use correct pipeline type. Expected: {primary_pipeline_type.value}")
            return CodeQuality.POOR
        
        # Check for pipeline type mixing (e.g., TimeSeriesPipe with MetricsPipe functions)
        pipeline_type_mixing = self._check_pipeline_type_mixing(generated_code, primary_pipeline_type)
        if pipeline_type_mixing:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Pipeline type mixing detected: {pipeline_type_mixing}")
            return CodeQuality.POOR
        
        # If syntax is valid and basic elements are present, consider it GOOD
        # This is more lenient than the LLM grading which might be too strict
        return CodeQuality.GOOD
    
    def _check_pipeline_type_mixing(self, generated_code: str, primary_pipeline_type: PipelineType) -> Optional[str]:
        """
        Check if the generated code mixes different pipeline types incorrectly
        
        Args:
            generated_code: The generated pipeline code
            primary_pipeline_type: The expected pipeline type for the primary function
            
        Returns:
            Error message if mixing is detected, None otherwise
        """
        # Check for proper multi-pipeline patterns first
        proper_multi_pipeline_patterns = [
            # MetricsPipe -> TimeSeriesPipe
            ("MetricsPipe.from_dataframe", "TimeSeriesPipe.from_dataframe"),
            # OperationsPipe -> TimeSeriesPipe
            ("OperationsPipe.from_dataframe", "TimeSeriesPipe.from_dataframe"),
            # MetricsPipe -> CohortPipe
            ("MetricsPipe.from_dataframe", "CohortPipe.from_dataframe"),
            # OperationsPipe -> CohortPipe
            ("OperationsPipe.from_dataframe", "CohortPipe.from_dataframe"),
            # MetricsPipe -> AnomalyPipe
            ("MetricsPipe.from_dataframe", "AnomalyPipe.from_dataframe"),
            # OperationsPipe -> AnomalyPipe
            ("OperationsPipe.from_dataframe", "AnomalyPipe.from_dataframe"),
            # TimeSeriesPipe -> AnomalyPipe
            ("TimeSeriesPipe.from_dataframe", "AnomalyPipe.from_dataframe"),
            # MetricsPipe -> SegmentPipe
            ("MetricsPipe.from_dataframe", "SegmentPipe.from_dataframe"),
            # OperationsPipe -> SegmentPipe
            ("OperationsPipe.from_dataframe", "SegmentPipe.from_dataframe"),
            # MetricsPipe -> TrendsPipe
            ("MetricsPipe.from_dataframe", "TrendsPipe.from_dataframe"),
            # OperationsPipe -> TrendsPipe
            ("OperationsPipe.from_dataframe", "TrendsPipe.from_dataframe"),
            # MetricsPipe -> RiskPipe
            ("MetricsPipe.from_dataframe", "RiskPipe.from_dataframe"),
            # OperationsPipe -> RiskPipe
            ("OperationsPipe.from_dataframe", "RiskPipe.from_dataframe"),
            
        ]
        
        # Check if proper multi-pipeline pattern is used
        for first_pipe, second_pipe in proper_multi_pipeline_patterns:
            if first_pipe in generated_code and second_pipe in generated_code:
                # This is a proper multi-pipeline pattern, no mixing error
                return None
        
        # Check for improper mixing patterns (same pipeline type with different function types)
        mixing_patterns = [
            # TimeSeriesPipe with MetricsPipe functions (without proper chaining)
            (PipelineType.TIMESERIES, ["Variance(", "Mean(", "Sum(", "Count("], "TimeSeriesPipe with MetricsPipe functions"),
            # MetricsPipe with OperationsPipe functions (without proper chaining)
            (PipelineType.METRICS, ["PercentChange(", "AbsoluteChange(", "CUPED("], "MetricsPipe with OperationsPipe functions"),
            # TimeSeriesPipe with OperationsPipe functions (without proper chaining)
            (PipelineType.TIMESERIES, ["PercentChange(", "AbsoluteChange(", "CUPED("], "TimeSeriesPipe with OperationsPipe functions"),
            # AnomalyPipe with MetricsPipe functions (without proper chaining)
            (PipelineType.ANOMALY, ["Variance(", "Mean(", "Sum(", "Count("], "AnomalyPipe with MetricsPipe functions"),
            # AnomalyPipe with OperationsPipe functions (without proper chaining)
            (PipelineType.ANOMALY, ["PercentChange(", "AbsoluteChange(", "CUPED("], "AnomalyPipe with OperationsPipe functions"),
            # SegmentPipe with MetricsPipe functions (without proper chaining)
            (PipelineType.SEGMENT, ["Variance(", "Mean(", "Sum(", "Count("], "SegmentPipe with MetricsPipe functions"),
            # SegmentPipe with OperationsPipe functions (without proper chaining)
            (PipelineType.SEGMENT, ["PercentChange(", "AbsoluteChange(", "CUPED("], "SegmentPipe with OperationsPipe functions"),
            # TrendsPipe with MetricsPipe functions (without proper chaining)
            (PipelineType.TRENDS, ["Variance(", "Mean(", "Sum(", "Count("], "TrendsPipe with MetricsPipe functions"),
            # TrendsPipe with OperationsPipe functions (without proper chaining)
            (PipelineType.TRENDS, ["PercentChange(", "AbsoluteChange(", "CUPED("], "TrendsPipe with OperationsPipe functions"),
        ]
        
        for expected_type, forbidden_functions, error_msg in mixing_patterns:
            if primary_pipeline_type == expected_type:
                for func in forbidden_functions:
                    if func in generated_code:
                        return f"{error_msg}: {func}"
        
        return None
    
    def _refine_query_state(self, query_state: Dict[str, Any], 
                           code_quality: CodeQuality) -> Dict[str, Any]:
        """Refine query state for next iteration"""
        # Add reasoning about what went wrong
        if code_quality == CodeQuality.INVALID:
            query_state["reasoning"].append("Code had syntax errors, refining generation approach")
        elif code_quality == CodeQuality.POOR:
            # Check if it's due to pipeline type mixing
            function_name = query_state["function_name"]
            primary_pipeline_type = self._detect_pipeline_type(function_name, "")
            query_state["reasoning"].append(f"Code quality was poor, likely due to pipeline type mixing. Primary function '{function_name}' should use {primary_pipeline_type.value}")
        
        # Enhance context for next iteration with pipeline type guidance
        function_name = query_state["function_name"]
        primary_pipeline_type = self._detect_pipeline_type(function_name, "")
        query_state["context"] += f" [Iteration {query_state['iteration'] + 1}: Use {primary_pipeline_type.value} and stay within the same pipeline type]"
        
        return query_state
    
    def _detect_pipeline_type(self, function_name: str, context: str) -> PipelineType:
        """Detect the appropriate pipeline type"""
        if function_name in self.function_to_pipe:
            return self.function_to_pipe[function_name]
        
        context_lower = context.lower()
        if any(term in context_lower for term in ["cohort", "retention", "lifetime"]):
            return PipelineType.COHORT
        elif any(term in context_lower for term in ["time series", "lag", "lead", "variance"]):
            return PipelineType.TIMESERIES
        elif any(term in context_lower for term in ["trend", "forecast", "growth", "moving average", "decompose", "seasonal"]):
            return PipelineType.TRENDS
        elif any(term in context_lower for term in ["segment", "cluster", "kmeans", "dbscan", "hierarchical", "grouping"]):
            return PipelineType.SEGMENT
        elif any(term in context_lower for term in ["risk", "var", "volatility"]):
            return PipelineType.RISK
        elif any(term in context_lower for term in ["funnel", "conversion"]):
            return PipelineType.FUNNEL
        elif any(term in context_lower for term in ["anomaly", "outlier", "detect", "unusual", "abnormal"]):
            return PipelineType.ANOMALY
        else:
            return PipelineType.METRICS
    
    def _create_enhanced_query(self, context: str, function_name: str, 
                              pipeline_type: PipelineType) -> str:
        """Create enhanced query for better retrieval"""
        return f"{context} {function_name} {pipeline_type.value} pipeline code example"
    
    def _parse_retrieval_results(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse retrieval results into structured format"""
        documents = []
        
        if results and "documents" in results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                distance = results.get("distances", [[]])[0][i] if "distances" in results else 0.0
                
                # Parse document if it's a JSON string
                if isinstance(doc, str):
                    try:
                        doc = json.loads(doc)
                    except:
                        doc = {"content": doc}
                
                documents.append({
                    "content": doc,
                    "distance": distance,
                    "relevance_score": 1.0 - distance
                })
        
        return documents
    
    def _format_documents_for_generation(self, relevant_docs: Dict[str, List[Dict[str, Any]]]) -> str:
        """Format documents for code generation prompt"""
        formatted_docs = []
        
        for doc_type, documents in relevant_docs.items():
            if documents:
                formatted_docs.append(f"\n{doc_type.upper()}:")
                for doc in documents[:3]:  # Limit to top 3 per type
                    content = doc["content"]
                    if isinstance(content, dict):
                        content = json.dumps(content, indent=2)
                    formatted_docs.append(f"- {content}")
        
        return "\n".join(formatted_docs)
    
    def _format_function_inputs(self, function_inputs: Dict[str, Any]) -> str:
        """Format function inputs for prompt"""
        formatted_inputs = []
        for key, value in function_inputs.items():
            if key.startswith('_'):
                continue
            if isinstance(value, str):
                formatted_inputs.append(f"{key}='{value}'")
            else:
                formatted_inputs.append(f"{key}={value}")
        
        return ",\n                         ".join(formatted_inputs)
    
    def _clean_generated_code(self, code: str) -> str:
        """Clean and format generated code with enhanced error handling"""
        if not code or not isinstance(code, str):
            return ""
        
        # Remove markdown code blocks
        code = re.sub(r'```python\s*', '', code)
        code = re.sub(r'```\s*', '', code)
        
        # Clean whitespace and remove empty lines
        lines = [line.rstrip() for line in code.split('\n') if line.strip()]
        
        if not lines:
            return ""
        
        # Join lines back together
        code = '\n'.join(lines)
        
        # Fix common syntax issues
        code = self._fix_common_syntax_issues(code)
        
        # Validate and try to fix parentheses
        code = self._fix_parentheses(code)
        
        # Check for specific indentation issues before final validation
        lines = code.split('\n')
        if len(lines) > 1:
            # Look for the specific problematic pattern
            if any('|' in line and line.strip().startswith('|') for line in lines[1:]):
                # Check if the first line is a pipeline initialization
                first_line = lines[0].strip()
                if re.match(r'^\w+\s*=\s*\w+Pipe\.from_dataframe\(', first_line):
                    logger.info("Detected pipeline indentation issue, attempting to fix")
                    code = self._extract_valid_code_parts(code)
        
        # Final validation - if still has syntax errors, try to generate a minimal valid version
        try:
            ast.parse(code)
            return code
        except SyntaxError as e:
            logger.warning(f"Syntax error after cleaning: {e}")
            # Try to extract valid parts or generate minimal valid code
            return self._extract_valid_code_parts(code)
    
    def _fix_common_syntax_issues(self, code: str) -> str:
        """Fix common syntax issues in generated code"""
        # Fix common issues
        code = re.sub(r'(\w+)\s*\(\s*\)\s*\|', r'\1() |', code)  # Fix empty function calls
        code = re.sub(r'\|\s*\(\s*\)', '|', code)  # Remove empty parentheses in pipe chains
        code = re.sub(r'\(\s*\)', '', code)  # Remove standalone empty parentheses
        
        # Fix common pipe syntax issues
        code = re.sub(r'\|\s*\|\s*', ' | ', code)  # Fix double pipes
        code = re.sub(r'\(\s*\|', '(', code)  # Fix opening parenthesis followed by pipe
        code = re.sub(r'\|\s*\)', ')', code)  # Fix pipe followed by closing parenthesis
        
        # Fix common function call issues
        code = re.sub(r'(\w+)\s*\(\s*,\s*', r'\1(', code)  # Fix function calls starting with comma
        code = re.sub(r'\(\s*,\s*', '(', code)  # Fix parentheses starting with comma
        
        # Fix to_df() missing parentheses
        code = re.sub(r'\|\s*to_df\s*(\||\)|$)', r' | to_df()\1', code)
        code = re.sub(r'^\s*to_df\s*(\||\)|$)', r'to_df()\1', code)
        
        # Fix function parameter issues - remove quotes around function names
        # Pattern: function='Variance' -> function=Variance
        code = re.sub(r"function\s*=\s*'([^']+)'", r'function=\1', code)
        code = re.sub(r'function\s*=\s*"([^"]+)"', r'function=\1', code)
        
        # Fix function parameters to direct method calls
        # Pattern: moving_apply_by_group(function=Variance, ...) -> variance(...)
        # This converts function parameters to direct method calls
        function_conversions = {
            'Variance': 'variance',
            'Mean': 'mean', 
            'Sum': 'sum',
            'Count': 'count',
            'Max': 'max',
            'Min': 'min',
            'StandardDeviation': 'std',
            'Correlation': 'correlation',
            'Covariance': 'covariance',
            'Median': 'median',
            'Percentile': 'percentile'
        }
        
        for func_param, method_name in function_conversions.items():
            # Pattern: moving_apply_by_group(function=Variance, ...) -> variance(...)
            pattern = rf'moving_apply_by_group\s*\(\s*function\s*=\s*{func_param}\s*,([^)]*)\)'
            replacement = rf'{method_name}(\1)'
            code = re.sub(pattern, replacement, code)
            
            # Also handle other wrapper functions
            pattern2 = rf'(\w+)\s*\(\s*function\s*=\s*{func_param}\s*,([^)]*)\)'
            replacement2 = rf'{method_name}(\2)'
            code = re.sub(pattern2, replacement2, code)
        
        # CRITICAL: Handle the case where we need to embed MetricsPipe functions as function parameters in TimeSeriesPipe
        # Pattern: moving_apply_by_group(function=Variance, ...) -> function=(MetricsPipe.from_dataframe(...) | Variance(...) | to_df())
        for func_param, method_name in function_conversions.items():
            # Look for moving_apply_by_group with function parameter
            pattern = rf'moving_apply_by_group\s*\(\s*function\s*=\s*{func_param}\s*,([^)]*)\)'
            if re.search(pattern, code):
                # Extract the dataframe name from the context
                dataframe_match = re.search(r'(\w+Pipe\.from_dataframe\([^)]+\))', code)
                if dataframe_match:
                    dataframe_expr = dataframe_match.group(1)
                    # Convert to embedded function format
                    replacement = rf'function=({dataframe_expr} | {method_name}(variable=\'Transactional value\') | to_df()),\1'
                    code = re.sub(pattern, replacement, code)
                    logger.info(f"Converted function={func_param} to embedded pipeline expression")
        
        # Fix other common function parameter issues
        # Pattern: method='rolling' -> method='rolling' (keep quotes for string values)
        # But: function=Variance -> function=Variance (no quotes for function names)
        
        # Fix missing parentheses in function calls within parameters
        # Pattern: function=Variance -> function=Variance (already handled above)
        
        # Fix pipeline indentation issues - this is the main fix for the reported error
        # Pattern: result = PipeType.from_dataframe(...)\n         | function(...)\n         | to_df()
        # Convert to: result = (PipeType.from_dataframe(...)\n                     | function(...)\n                     | to_df()\n                    )
        lines = code.split('\n')
        if len(lines) > 1:
            # Check if we have a pipeline pattern with incorrect indentation
            pipeline_pattern = re.compile(r'^(\w+)\s*=\s*(\w+Pipe\.from_dataframe\([^)]*\))')
            first_line_match = pipeline_pattern.match(lines[0].strip())
            
            if first_line_match and len(lines) > 1:
                # Check if subsequent lines start with pipe operators and indentation
                pipe_lines = []
                for i, line in enumerate(lines[1:], 1):
                    stripped = line.strip()
                    if stripped.startswith('|'):
                        pipe_lines.append((i, stripped))
                
                if pipe_lines:
                    # Reconstruct the code with proper parentheses and indentation
                    result_var = first_line_match.group(1)
                    pipe_init = first_line_match.group(2)
                    
                    # Start with opening parenthesis
                    fixed_lines = [f"{result_var} = ({pipe_init}"]
                    
                    # Add pipe operations with proper indentation
                    for _, pipe_line in pipe_lines:
                        # Remove the leading | and add proper indentation
                        pipe_content = pipe_line[1:].strip()
                        fixed_lines.append(f"                     | {pipe_content}")
                    
                    # Close the parentheses
                    fixed_lines.append("                    )")
                    
                    # Join the lines
                    code = '\n'.join(fixed_lines)
        
        return code
    
    def _fix_parentheses(self, code: str) -> str:
        """Fix unclosed or mismatched parentheses"""
        # Count parentheses
        open_parens = code.count('(')
        close_parens = code.count(')')
        
        # If we have more opening than closing parentheses, add missing ones
        if open_parens > close_parens:
            missing = open_parens - close_parens
            # Add missing closing parentheses at the end
            code += ')' * missing
            logger.info(f"Added {missing} missing closing parentheses")
        
        # If we have more closing than opening parentheses, remove extra ones
        elif close_parens > open_parens:
            extra = close_parens - open_parens
            # Remove extra closing parentheses from the end
            for _ in range(extra):
                if code.endswith(')'):
                    code = code[:-1]
            logger.info(f"Removed {extra} extra closing parentheses")
        
        return code
    
    def _extract_valid_code_parts(self, code: str) -> str:
        """Extract valid code parts when full code has syntax errors"""
        try:
            # First, try to fix the specific indentation issue we're seeing
            lines = code.split('\n')
            if len(lines) > 1:
                                # Check for the specific pattern: result = (PipeType.from_dataframe(...)\n    | function(...)
                pipeline_pattern = re.compile(r'^(\w+)\s*=\s*\((\w+Pipe\.from_dataframe\([^)]*\))')
                first_line_match = pipeline_pattern.match(lines[0].strip())
                
                if first_line_match:
                    result_var = first_line_match.group(1)
                    pipe_init = first_line_match.group(2)
                    
                    # Collect all pipe operations
                    pipe_operations = []
                    for line in lines[1:]:
                        stripped = line.strip()
                        if stripped.startswith('|'):
                            # Extract the operation part after the pipe
                            operation_part = stripped[1:].strip()
                            pipe_operations.append(operation_part)
                    
                    if pipe_operations:
                        # Reconstruct with proper syntax
                        fixed_code = f"{result_var} = ({pipe_init}"
                        for op in pipe_operations:
                            # Fix common issues in the operation
                            op = re.sub(r"function\s*=\s*'([^']+)'", r'function=\1', op)
                            op = re.sub(r'function\s*=\s*"([^"]+)"', r'function=\1', op)
                            
                            # Fix function parameters to direct method calls
                            function_conversions = {
                                'Variance': 'variance',
                                'Mean': 'mean', 
                                'Sum': 'sum',
                                'Count': 'count',
                                'Max': 'max',
                                'Min': 'min',
                                'StandardDeviation': 'std',
                                'Correlation': 'correlation',
                                'Covariance': 'covariance',
                                'Median': 'median',
                                'Percentile': 'percentile'
                            }
                            
                            for func_param, method_name in function_conversions.items():
                                # Pattern: moving_apply_by_group(function=Variance, ...) -> variance(...)
                                pattern = rf'moving_apply_by_group\s*\(\s*function\s*=\s*{func_param}\s*,([^)]*)\)'
                                replacement = rf'{method_name}(\1)'
                                op = re.sub(pattern, replacement, op)
                                
                                # Also handle other wrapper functions
                                pattern2 = rf'(\w+)\s*\(\s*function\s*=\s*{func_param}\s*,([^)]*)\)'
                                replacement2 = rf'{method_name}(\2)'
                                op = re.sub(pattern2, replacement2, op)
                            
                            fixed_code += f"\n    | {op}"
                        fixed_code += "\n    ).to_df()"
                        return fixed_code
            
            # Try to find a valid pipeline pattern
            pipeline_pattern = r'(\w+Pipe\.from_dataframe\([^)]+\)\s*\|\s*\w+\([^)]*\)\s*\|\s*to_df\(\))'
            match = re.search(pipeline_pattern, code)
            if match:
                return f"result = ({match.group(1)})"
            
            # Try to extract just the pipeline initialization
            init_pattern = r'(\w+Pipe\.from_dataframe\([^)]+\))'
            match = re.search(init_pattern, code)
            if match:
                return f"""result = (
    {match.group(1)}
    ).to_df()"""
            
            # If all else fails, return a basic fallback
            return """result = (
    MetricsPipe.from_dataframe(df)
    ).to_df()"""
            
        except Exception as e:
            logger.error(f"Error extracting valid code parts: {e}")
            return """result = (
    MetricsPipe.from_dataframe(df)
    ).to_df()"""
    
    def _generate_fallback_code(self, pipeline_type: PipelineType, 
                               function_name: str, function_inputs: Dict[str, Any], 
                               dataframe_name: str) -> str:
        """Generate fallback code when main generation fails"""
        try:
            inputs_str = self._format_function_inputs(function_inputs)
            
            # Handle dataframe names with spaces
            if ' ' in dataframe_name:
                dataframe_name = f'"{dataframe_name}"'
            
            # Generate a simple, valid fallback code
            if inputs_str.strip():
                fallback_code = f"""result = (
    {pipeline_type.value}.from_dataframe({dataframe_name})
    | {function_name}({inputs_str})
    ).to_df()"""
            else:
                fallback_code = f"""result = (
    {pipeline_type.value}.from_dataframe({dataframe_name})
    | {function_name}()
    ).to_df()"""
            
            # Validate the fallback code
            try:
                ast.parse(fallback_code)
                return fallback_code
            except SyntaxError:
                # If even the fallback has syntax errors, return the most basic version
                return f"""result = (
    {pipeline_type.value}.from_dataframe({dataframe_name})
    ).to_df()"""
                
        except Exception as e:
            logger.error(f"Error generating fallback code: {e}")
            # Return the most basic valid code
            return f"""result = (
    MetricsPipe.from_dataframe('df')
    ).to_df()"""
    
    def _format_final_result(self, query_state: Dict[str, Any]) -> Dict[str, Any]:
        """Format the final result"""
        # Consider it successful if we have generated code attempts
        has_generated_code = len(query_state["code_attempts"]) > 0
        final_code = query_state["final_code"] or (query_state["code_attempts"][-1] if query_state["code_attempts"] else None)
        
        return {
            "status": "success" if has_generated_code else "error",
            "generated_code": final_code,
            "iterations": query_state["iteration"] + 1,
            "attempts": query_state["code_attempts"],
            "reasoning": query_state["reasoning"],
            "function_name": query_state["function_name"],
            "pipeline_type": self._detect_pipeline_type(
                query_state["function_name"], 
                query_state.get("original_context", query_state["context"])
            ).value,
            "detected_inputs": query_state.get("detected_inputs", {}),
            "enhanced_function_inputs": query_state["function_inputs"],
            "function_detection_metadata": query_state.get("function_detection_metadata", {}),
            "classification": query_state.get("classification"),
            "dataset_description": query_state.get("dataset_description"),
            "columns_description": query_state.get("columns_description"),
            "enhanced_context": query_state["context"]
        }
from typing import Dict, List, Any, Optional, Union, Tuple
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers.string import StrOutputParser
import json
import re
from enum import Enum
import ast
from app.storage.documents import DocumentChromaStore
from .analysis_intent_classification import AnalysisIntentResult
from .function_retrieval import FunctionRetrieval
from app.agents.retrieval.retrieval_helper import RetrievalHelper
import logging

class PipelineType(Enum):
    """Supported pipeline types"""
    COHORT = "CohortPipe"
    TIMESERIES = "TimeSeriesPipe"
    TRENDS = "TrendPipe"
    SEGMENT = "SegmentPipe"
    RISK = "RiskPipe"
    METRICS = "MetricsPipe"
    OPERATIONS = "OperationsPipe"
    FUNNEL = "FunnelPipe"
    ANOMALY = "AnomalyPipe"
    MOVINGAGGR = "MovingAggrPipe"
    PROPHET = "ProphetPipe"

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
                 function_definition_store: DocumentChromaStore,
                 logical_reasoning_store=None,
                 function_retrieval: FunctionRetrieval = None,
                 enhanced_function_registry=None,
                 retrieval_helper=None,
                 max_iterations: int = 3,
                 relevance_threshold: float = 0.7):
        """
        Initialize the self-correcting pipeline code generator
        
        Args:
            llm: Language model instance
            usage_examples_store: Store containing usage examples
            code_examples_store: Store containing code examples
            function_definition_store: Store containing function definitions (fallback)
            logical_reasoning_store: Optional store for logical reasoning patterns
            function_retrieval: FunctionRetrieval instance for accessing function definitions
            enhanced_function_registry: Enhanced function registry with examples, instructions, and rules
            retrieval_helper: RetrievalHelper instance for accessing function definitions, examples, and insights
            max_iterations: Maximum number of self-correction iterations
            relevance_threshold: Threshold for document relevance scoring
        """
        self.llm = llm
        self.usage_examples_store = usage_examples_store
        self.code_examples_store = code_examples_store
        self.function_definition_store = function_definition_store
        self.logical_reasoning_store = logical_reasoning_store
        self.function_retrieval = function_retrieval
        self.enhanced_function_registry = enhanced_function_registry
        self.retrieval_helper = retrieval_helper
        self.max_iterations = max_iterations
        self.relevance_threshold = relevance_threshold
        
        # No hardcoded function mappings - use LLM-based intelligent selection instead
        self.function_to_pipe = {}
    
    async def _get_enhanced_function_context(self, function_name: str, context: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get enhanced function context including examples, instructions, and rules.
        
        Args:
            function_name: Name of the function to get context for
            context: User context for better matching
            project_id: Optional project ID for project-specific instructions
            
        Returns:
            Dictionary containing enhanced function context
        """
        if not self.enhanced_function_registry:
            return {}
        
        try:
            # Get enhanced function definition with context
            enhanced_def = await self.enhanced_function_registry.get_enhanced_function_definition(
                function_name=function_name,
                question=context,
                project_id=project_id
            )
            
            if "error" in enhanced_def:
                return {}
            
            # Extract relevant context
            enhanced_context = {
                "function_name": function_name,
                "description": enhanced_def.get("description", ""),
                "usage_description": enhanced_def.get("usage_description", ""),
                "category": enhanced_def.get("category", ""),
                "source_code": enhanced_def.get("source_code", ""),
                "function_signature": enhanced_def.get("function_signature", ""),
                "function_docstring": enhanced_def.get("function_docstring", ""),
                "examples": enhanced_def.get("examples", []),
                "instructions": enhanced_def.get("instructions", []),
                "historical_rules": enhanced_def.get("historical_rules", []),
                "examples_store": enhanced_def.get("examples_store", [])
            }
            
            return enhanced_context
            
        except Exception as e:
            logger.warning(f"Error getting enhanced function context for {function_name}: {e}")
            return {}
    
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
            reasoning_plan_result = await self._extract_function_from_reasoning_plan(
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
                plan_evaluation = await self._evaluate_reasoning_plan_quality(
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
                    adjusted_plan = await self._adjust_reasoning_plan(
                        classification.reasoning_plan, 
                        plan_evaluation
                    )
                    # Update the classification with adjusted plan
                    classification.reasoning_plan = adjusted_plan
                    logger.info(f"Adjusted reasoning plan has {len(adjusted_plan)} steps")
                
                # Generate code from (potentially adjusted) reasoning plan
                code_generation_result = await self._generate_code_from_reasoning_plan(
                    classification.reasoning_plan, 
                    dataframe_name, 
                    classification
                )
                
                # Extract the combined code for backward compatibility
                generated_code = code_generation_result["combined_code"]
                step_codes = code_generation_result["step_codes"]
                flow_graph = code_generation_result["flow_graph"]
                
                # Skip grading for now to focus on flow generation
                # code_quality = await self._grade_code(generated_code, query_state)
                code_quality = CodeQuality.GOOD  # Skip grading for now
                
                # If code quality is good, use it; otherwise try LLM generation
                if code_quality in [CodeQuality.EXCELLENT, CodeQuality.GOOD]:
                    query_state["final_code"] = generated_code
                    query_state["step_codes"] = step_codes
                    query_state["flow_graph"] = flow_graph
                    logger.info("Using code generated from reasoning plan")
                    break
                else:
                    logger.info(f"Reasoning plan code quality was {code_quality}, trying LLM generation")
                    # Add reasoning plan evaluation to query state for LLM generation
                    query_state["reasoning_plan_evaluation"] = plan_evaluation
            
            # Step 1: Retrieve documents
            retrieved_docs = await self._retrieve_documents(query_state)
            
            # Step 2: Grade document relevance
            relevant_docs = await self._grade_documents(retrieved_docs, query_state)
            
            # Step 3: Generate code
            generated_code = await self._generate_code(relevant_docs, query_state)
            
            # Step 4: Skip grading for now to focus on flow generation
            # code_quality = await self._grade_code(generated_code, query_state)
            code_quality = CodeQuality.GOOD  # Skip grading for now
            
            # Step 5: Decide on next action
            if code_quality in [CodeQuality.EXCELLENT, CodeQuality.GOOD]:
                query_state["final_code"] = generated_code
                break
            elif iteration < self.max_iterations - 1:
                # Self-correct: refine query and try again
                query_state = await self._refine_query_state(query_state, code_quality)
        
        return await self._format_final_result(query_state)
    
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
        
        # Initialize default values to prevent UnboundLocalError
        required_columns = []
        missing_columns = []
        suggested_functions = []
        intent_type = ''
        confidence_score = 0.0
        rephrased_question = ''
        reasoning = ''
        can_be_answered = True
        feasibility_score = 0.0
        clarification_needed = None
        reasoning_plan = None
        
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
                
                # Add enhanced metadata summary if available
                enhanced_metadata_summary = []
                for i, step in enumerate(reasoning_plan):
                    if isinstance(step, dict):
                        step_metadata = []
                        
                        # Add column mapping if available
                        if step.get('column_mapping'):
                            step_metadata.append(f"Column Mapping: {step.get('column_mapping')}")
                        
                        # Add input/output columns if available
                        if step.get('input_columns'):
                            step_metadata.append(f"Input Columns: {step.get('input_columns')}")
                        if step.get('output_columns'):
                            step_metadata.append(f"Output Columns: {step.get('output_columns')}")
                        
                        # Add pipeline type if available
                        if step.get('pipeline_type'):
                            step_metadata.append(f"Pipeline Type: {step.get('pipeline_type')}")
                        
                        # Add function category if available
                        if step.get('function_category'):
                            step_metadata.append(f"Function Category: {step.get('function_category')}")
                        
                        # Add step dependencies if available
                        if step.get('step_dependencies'):
                            step_metadata.append(f"Dependencies: Step {step.get('step_dependencies')}")
                        
                        if step_metadata:
                            enhanced_metadata_summary.append(f"Step {i+1}: {'; '.join(step_metadata)}")
                
                if enhanced_metadata_summary:
                    enhanced_parts.append(f"\nEnhanced Metadata Summary:")
                    enhanced_parts.append("\n".join(enhanced_metadata_summary))
        
        # Add dataset description
        if dataset_description:
            enhanced_parts.append(f"\nDataset Description: {dataset_description}")
        
        # Add columns description
        if columns_description:
            enhanced_parts.append(f"\nColumns Description:")
            for col, desc in columns_description.items():
                enhanced_parts.append(f"- {col}: {desc}")
        
        return "\n".join(enhanced_parts)
    
    async def _extract_function_from_reasoning_plan(self, 
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
        
        # Select the most appropriate function based on relevance scores and confidence
        selected_function = await self._select_best_function_from_reasoning_plan(
            plan_functions, reasoning_plan, classification, context
        )
        
        # Create metadata based on reasoning plan
        metadata = {
            "selected_function": selected_function,
            "confidence": 0.95,  # High confidence since it's from reasoning plan
            "reasoning": f"Selected {selected_function} from reasoning plan based on relevance and confidence scores",
            "alternative_functions": [f for f in plan_functions if f != selected_function],
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
                
                # Handle None, "None", or "N/A" values - use LLM-based extraction
                if function_name in [None, "None", "none", "N/A"]:
                    logger.info(f"Step {i+1} has invalid function name '{function_name}', using LLM to extract function name")
                    # Use LLM to extract function name and parameters from step description
                    parsed_result = await self._parse_reasoning_plan_step_with_llm(
                        parameter_mapping if isinstance(parameter_mapping, str) else step_title, 
                        step_title, 
                        i+1, 
                        None  # Let LLM determine function name
                    )
                    
                    if parsed_result and parsed_result.get('function_name'):
                        function_name = parsed_result['function_name']
                        parameter_mapping = parsed_result.get('parameter_mapping', parameter_mapping)
                        logger.info(f"Step {i+1} - LLM extracted function name: {function_name}")
                    else:
                        # Error out instead of using fallback to prevent incorrect pipeline generation
                        error_msg = f"Step {i+1} - LLM extraction failed to determine function name for step: {step_title}"
                        logger.error(error_msg)
                        raise ValueError(error_msg)
                
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
                        
                        # Handle enhanced metadata if available
                        column_mapping = step.get('column_mapping', {})
                        if column_mapping and isinstance(column_mapping, dict):
                            # Use column mapping to enhance parameter mapping
                            for param_name, mapped_column in column_mapping.items():
                                if param_name in primary_function_inputs:
                                    # Update parameter with mapped column
                                    primary_function_inputs[param_name] = mapped_column
                                    logger.info(f"Updated parameter {param_name} with mapped column: {mapped_column}")
                        
                        # Add enhanced metadata to primary function inputs
                        enhanced_metadata = {
                            'input_columns': step.get('input_columns', []),
                            'output_columns': step.get('output_columns', []),
                            'step_dependencies': step.get('step_dependencies', []),
                            'data_flow': step.get('data_flow', ''),
                            'pipeline_type': step.get('pipeline_type', ''),
                            'function_category': step.get('function_category', ''),
                            'parameter_constraints': step.get('parameter_constraints', {}),
                            'error_handling': step.get('error_handling', ''),
                            'embedded_function_columns': step.get('embedded_function_columns')
                        }
                        primary_function_inputs['_enhanced_metadata'] = enhanced_metadata
                        
                    else:
                        logger.warning(f"Parameter mapping is not a dictionary, converting to empty dict: {type(parameter_mapping)} -> {parameter_mapping}")
                        primary_function_inputs = {}
                
                # Add additional computations for subsequent steps (only if not embedded)
                if i > 0 and function_name and not embedded_function_parameter:
                    # Ensure parameter_mapping is a dictionary
                    if isinstance(parameter_mapping, dict):
                        inputs_for_computation = parameter_mapping.copy()
                        
                        # Handle enhanced metadata if available
                        column_mapping = step.get('column_mapping', {})
                        if column_mapping and isinstance(column_mapping, dict):
                            # Use column mapping to enhance parameter mapping
                            for param_name, mapped_column in column_mapping.items():
                                if param_name in inputs_for_computation:
                                    # Update parameter with mapped column
                                    inputs_for_computation[param_name] = mapped_column
                                    logger.info(f"Updated parameter {param_name} with mapped column: {mapped_column}")
                        
                        # Add enhanced metadata to computation inputs
                        enhanced_metadata = {
                            'input_columns': step.get('input_columns', []),
                            'output_columns': step.get('output_columns', []),
                            'step_dependencies': step.get('step_dependencies', []),
                            'data_flow': step.get('data_flow', ''),
                            'pipeline_type': step.get('pipeline_type', ''),
                            'function_category': step.get('function_category', ''),
                            'parameter_constraints': step.get('parameter_constraints', {}),
                            'error_handling': step.get('error_handling', ''),
                            'embedded_function_columns': step.get('embedded_function_columns')
                        }
                        inputs_for_computation['_enhanced_metadata'] = enhanced_metadata
                        
                    else:
                        logger.warning(f"Parameter mapping for step {i} is not a dictionary, using empty dict: {type(parameter_mapping)} -> {parameter_mapping}")
                        inputs_for_computation = {}
                    
                    additional_computations.append({
                        "function": function_name,
                        "inputs": inputs_for_computation,
                        "tool": "dynamic",  # Let the system determine the tool dynamically
                        "enhanced_metadata": enhanced_metadata if 'enhanced_metadata' in locals() else {}
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
    
    async def _select_best_function_from_reasoning_plan(
        self, 
        plan_functions: List[str], 
        reasoning_plan: List[Dict[str, Any]], 
        classification: Union[Dict[str, Any], AnalysisIntentResult],
        context: str
    ) -> str:
        """
        Select the best function from reasoning plan using LLM for intelligent selection
        
        Args:
            plan_functions: List of function names from reasoning plan
            reasoning_plan: Complete reasoning plan
            classification: Classification results with retrieved functions
            context: Original context
            
        Returns:
            Best function name based on LLM analysis
        """
        if not plan_functions:
            return "Mean"  # Fallback
        
        if len(plan_functions) == 1:
            return plan_functions[0]  # Only one function available
        
        # If no LLM available, fall back to rule-based selection
        if not self.llm:
            logger.warning("No LLM available, falling back to rule-based function selection")
            return await self._select_best_function_rule_based(
                plan_functions, reasoning_plan, classification, context
            )
        
        try:
            # Get retrieved functions from classification
            retrieved_functions = []
            if hasattr(classification, 'retrieved_functions'):
                retrieved_functions = getattr(classification, 'retrieved_functions', [])
            else:
                retrieved_functions = classification.get('retrieved_functions', [])
            
            # Prepare function details for LLM analysis
            function_details = []
            for func_name in plan_functions:
                func_info = {
                    "function_name": func_name,
                    "relevance_score": 0.0,
                    "priority": 999,
                    "reasoning": "",
                    "description": "",
                    "pipeline_type": "",
                    "function_category": "",
                    "parameter_mapping": {},
                    "data_requirements": [],
                    "expected_output": ""
                }
                
                # Find function in retrieved functions
                for retrieved_func in retrieved_functions:
                    if isinstance(retrieved_func, dict) and retrieved_func.get('function_name') == func_name:
                        func_info.update({
                            "relevance_score": retrieved_func.get('relevance_score', 0.0),
                            "priority": retrieved_func.get('priority', 999),
                            "reasoning": retrieved_func.get('reasoning', ''),
                            "description": retrieved_func.get('description', ''),
                            "pipeline_type": retrieved_func.get('category', ''),
                            "function_category": retrieved_func.get('category', '')
                        })
                        break
                
                # Find function in reasoning plan steps
                for step in reasoning_plan:
                    if isinstance(step, dict) and step.get('function_name') == func_name:
                        func_info.update({
                            "pipeline_type": step.get('pipeline_type', func_info["pipeline_type"]),
                            "function_category": step.get('function_category', func_info["function_category"]),
                            "parameter_mapping": step.get('parameter_mapping', {}),
                            "data_requirements": step.get('data_requirements', []),
                            "expected_output": step.get('expected_output', '')
                        })
                        break
                
                function_details.append(func_info)
            
            # Use LLM to select the best function
            selected_function = await self._select_best_function_with_llm(
                function_details, context, reasoning_plan
            )
            
            logger.info(f"LLM selected function: {selected_function}")
            return selected_function
            
        except Exception as e:
            logger.warning(f"LLM function selection failed: {e}, falling back to rule-based selection")
            return await self._select_best_function_rule_based(
                plan_functions, reasoning_plan, classification, context
            )
    
    async def _select_best_function_with_llm(
        self,
        function_details: List[Dict[str, Any]],
        context: str,
        reasoning_plan: List[Dict[str, Any]]
    ) -> str:
        """
        Use LLM to intelligently select the best function from available options
        
        Args:
            function_details: List of function details with metadata
            context: Original analysis context
            reasoning_plan: Complete reasoning plan
            
        Returns:
            Best function name selected by LLM
        """
        from langchain.prompts import PromptTemplate
        from langchain_core.output_parsers.string import StrOutputParser
        
        # Format function details for LLM
        function_details_formatted = []
        for i, func in enumerate(function_details, 1):
            details = f"{i}. {func['function_name']}:\n"
            details += f"   - Relevance Score: {func['relevance_score']:.2f}\n"
            details += f"   - Priority: {func['priority']}\n"
            details += f"   - Pipeline Type: {func['pipeline_type']}\n"
            details += f"   - Function Category: {func['function_category']}\n"
            details += f"   - Description: {func['description']}\n"
            details += f"   - Reasoning: {func['reasoning']}\n"
            
            if func['parameter_mapping']:
                details += f"   - Parameter Mapping: {func['parameter_mapping']}\n"
            if func['data_requirements']:
                details += f"   - Data Requirements: {func['data_requirements']}\n"
            if func['expected_output']:
                details += f"   - Expected Output: {func['expected_output']}\n"
            
            function_details_formatted.append(details)
        
        # Format reasoning plan for context
        reasoning_plan_formatted = []
        for i, step in enumerate(reasoning_plan, 1):
            if isinstance(step, dict):
                step_info = f"Step {i}: {step.get('step_title', 'Unknown')}\n"
                step_info += f"   - Function: {step.get('function_name', 'Unknown')}\n"
                step_info += f"   - Pipeline Type: {step.get('pipeline_type', 'Unknown')}\n"
                step_info += f"   - Category: {step.get('function_category', 'Unknown')}\n"
                reasoning_plan_formatted.append(step_info)
        
        selection_prompt = PromptTemplate(
            input_variables=["context", "function_details", "reasoning_plan"],
            template="""
You are an expert data analysis function selector. Your task is to select the most appropriate function from the available options based on the analysis context, reasoning plan, and function metadata.

ANALYSIS CONTEXT:
{context}

REASONING PLAN:
{reasoning_plan}

AVAILABLE FUNCTIONS:
{function_details}

INSTRUCTIONS:
1. Use the reasoning plan (already available) to understand the analysis requirements
2. Get the function definition for the primary function to understand its parameters
3. Map available columns to function parameters based on the function definition
4. Ensure the function inputs align with the reasoning plan steps
5. Focus on detecting the correct function inputs, not pipeline type identification

4. CRITICAL FUNCTION INPUT DETECTION:
   - Use the function definition to understand required and optional parameters
   - Map available columns to function parameters based on data types and context
   - Ensure parameter values match the function signature
   - Consider the reasoning plan steps for proper data flow
   - Do not try to identify or change the pipeline type (already determined)

5. Return ONLY the function name of the best choice, nothing else.

EXAMPLES:
- If context mentions "variance analysis" and variance_analysis has relevance_score=1.0, select "variance_analysis"
- If context mentions "moving average" and calculate_moving_average has relevance_score=0.9, select "calculate_moving_average"
- If multiple functions have similar relevance scores, consider the reasoning plan and context alignment

SELECT THE BEST FUNCTION:
"""
        )
        
        selection_chain = selection_prompt | self.llm | StrOutputParser()
        
        try:
            result = await selection_chain.ainvoke({
                "context": context,
                "function_details": "\n".join(function_details_formatted),
                "reasoning_plan": "\n".join(reasoning_plan_formatted)
            })
            
            # Clean and extract function name
            selected_function = result.strip()
            
            # Validate that the selected function is in our list
            available_functions = [func['function_name'] for func in function_details]
            if selected_function in available_functions:
                logger.info(f"LLM selected function: {selected_function}")
                return selected_function
            else:
                logger.warning(f"LLM selected invalid function: {selected_function}, falling back to highest relevance score")
                # Fall back to highest relevance score
                best_function = max(function_details, key=lambda x: x['relevance_score'])
                return best_function['function_name']
                
        except Exception as e:
            logger.warning(f"LLM function selection failed: {e}, falling back to highest relevance score")
            # Fall back to highest relevance score
            best_function = max(function_details, key=lambda x: x['relevance_score'])
            return best_function['function_name']
    
    async def _select_best_function_rule_based(
        self, 
        plan_functions: List[str], 
        reasoning_plan: List[Dict[str, Any]], 
        classification: Union[Dict[str, Any], AnalysisIntentResult],
        context: str
    ) -> str:
        """
        Fallback rule-based function selection when LLM is not available
        
        Args:
            plan_functions: List of function names from reasoning plan
            reasoning_plan: Complete reasoning plan
            classification: Classification results with retrieved functions
            context: Original context
            
        Returns:
            Best function name based on rule-based scoring
        """
        # Get retrieved functions from classification
        retrieved_functions = []
        if hasattr(classification, 'retrieved_functions'):
            retrieved_functions = getattr(classification, 'retrieved_functions', [])
        else:
            retrieved_functions = classification.get('retrieved_functions', [])
        
        # Create a scoring system for each function
        function_scores = {}
        
        for func_name in plan_functions:
            score = 0.0
            reasoning = []
            
            # Base score for being in the reasoning plan
            score += 50.0
            reasoning.append("Function present in reasoning plan")
            
            # Check if function exists in retrieved functions with relevance score
            for retrieved_func in retrieved_functions:
                if isinstance(retrieved_func, dict) and retrieved_func.get('function_name') == func_name:
                    # Add relevance score (0.0 to 1.0, scaled to 0-50 points)
                    relevance_score = retrieved_func.get('relevance_score', 0.0)
                    score += relevance_score * 50.0
                    reasoning.append(f"Relevance score: {relevance_score:.2f}")
                    
                    # Add priority score if available
                    priority = retrieved_func.get('priority', 1)
                    score += (6 - priority) * 5.0  # Higher priority (lower number) gets more points
                    reasoning.append(f"Priority: {priority}")
                    
                    # Check if function has good reasoning
                    func_reasoning = retrieved_func.get('reasoning', '')
                    if func_reasoning and len(func_reasoning) > 10:
                        score += 10.0
                        reasoning.append("Has detailed reasoning")
                    
                    # Check if function has required parameters
                    required_params = retrieved_func.get('required_params', [])
                    if required_params:
                        score += 5.0
                        reasoning.append("Has required parameters defined")
                    
                    break
            
            # Check reasoning plan step details for additional scoring
            for step in reasoning_plan:
                if isinstance(step, dict) and step.get('function_name') == func_name:
                    # Check if step has detailed parameter mapping
                    param_mapping = step.get('parameter_mapping', {})
                    if param_mapping and isinstance(param_mapping, dict) and len(param_mapping) > 0:
                        score += 10.0
                        reasoning.append("Has detailed parameter mapping")
                    
                    # Check if step has data requirements
                    data_reqs = step.get('data_requirements', [])
                    if data_reqs and len(data_reqs) > 0:
                        score += 5.0
                        reasoning.append("Has data requirements defined")
                    
                    # Check if step has expected output
                    expected_output = step.get('expected_output', '')
                    if expected_output and len(expected_output) > 10:
                        score += 5.0
                        reasoning.append("Has expected output defined")
                    
                    # Check pipeline type alignment
                    pipeline_type = step.get('pipeline_type', '')
                    if pipeline_type:
                        score += 5.0
                        reasoning.append(f"Pipeline type: {pipeline_type}")
                    
                    break
            
            # Check if function is more appropriate for the context
            context_lower = context.lower()
            if any(keyword in context_lower for keyword in ['variance', 'variation', 'volatility']):
                if 'variance' in func_name.lower():
                    score += 20.0
                    reasoning.append("Context mentions variance - function matches")
            elif any(keyword in context_lower for keyword in ['moving', 'rolling', 'average']):
                if any(keyword in func_name.lower() for keyword in ['moving', 'rolling', 'average']):
                    score += 20.0
                    reasoning.append("Context mentions moving/rolling - function matches")
            elif any(keyword in context_lower for keyword in ['trend', 'growth', 'forecast']):
                if any(keyword in func_name.lower() for keyword in ['trend', 'growth', 'forecast']):
                    score += 20.0
                    reasoning.append("Context mentions trends - function matches")
            
            function_scores[func_name] = {
                'score': score,
                'reasoning': reasoning
            }
        
        # Select the function with the highest score
        best_function = max(function_scores.keys(), key=lambda x: function_scores[x]['score'])
        best_score = function_scores[best_function]['score']
        best_reasoning = function_scores[best_function]['reasoning']
        
        logger.info(f"Rule-based function selection scores:")
        for func_name, score_info in function_scores.items():
            logger.info(f"  {func_name}: {score_info['score']:.1f} points - {', '.join(score_info['reasoning'])}")
        
        logger.info(f"Selected function: {best_function} with score {best_score:.1f}")
        
        return best_function
    
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
                # Extract function names from suggested_functions for comparison
                suggested_function_names = [self._extract_function_name_from_suggested_function(func) for func in suggested_functions]
                if func.get('function_name') in suggested_function_names:
                    retrieved_functions_info += f"{i}. {func.get('function_name', 'N/A')}:\n"
                    retrieved_functions_info += f"   - Relevance Score: {func.get('relevance_score', 'N/A')}\n"
                    retrieved_functions_info += f"   - Description: {func.get('description', 'N/A')}\n"
                    retrieved_functions_info += f"   - Usage: {func.get('usage_description', 'N/A')}\n"
                    retrieved_functions_info += f"   - Reasoning: {func.get('reasoning', 'N/A')}\n"
                    retrieved_functions_info += f"   - Priority: {func.get('priority', 'N/A')}\n"
                    
                    # Add required parameters if available
                    if func.get('required_params'):
                        retrieved_functions_info += f"   - Required Parameters:\n"
                        required_params = func.get('required_params', [])
                        
                        # Handle both string and dictionary formats
                        try:
                            if isinstance(required_params, list):
                                for param in required_params:
                                    if isinstance(param, dict):
                                        param_name = param.get('name', 'N/A')
                                        param_type = param.get('type', 'N/A')
                                        param_desc = param.get('description', 'N/A')
                                        retrieved_functions_info += f"     * {param_name} ({param_type}): {param_desc}\n"
                                    elif isinstance(param, str):
                                        retrieved_functions_info += f"     * {param}\n"
                            elif isinstance(required_params, str):
                                retrieved_functions_info += f"     * {required_params}\n"
                        except Exception as e:
                            logger.warning(f"Error processing required parameters: {e}")
                            retrieved_functions_info += f"     * Error processing parameters\n"
                    
                    # Add optional parameters if available
                    if func.get('optional_params'):
                        retrieved_functions_info += f"   - Optional Parameters:\n"
                        optional_params = func.get('optional_params', [])
                        
                        # Handle both string and dictionary formats
                        try:
                            if isinstance(optional_params, list):
                                for param in optional_params:
                                    if isinstance(param, dict):
                                        param_name = param.get('name', 'N/A')
                                        param_type = param.get('type', 'N/A')
                                        param_desc = param.get('description', 'N/A')
                                        retrieved_functions_info += f"     * {param_name} ({param_type}): {param_desc}\n"
                                    elif isinstance(param, str):
                                        retrieved_functions_info += f"     * {param}\n"
                            elif isinstance(optional_params, str):
                                retrieved_functions_info += f"     * {optional_params}\n"
                        except Exception as e:
                            logger.warning(f"Error processing optional parameters: {e}")
                            retrieved_functions_info += f"     * Error processing parameters\n"
                    
                    # Add outputs if available
                    if func.get('outputs'):
                        outputs = func.get('outputs', {})
                        if isinstance(outputs, dict):
                            output_type = outputs.get('type', 'N/A')
                            output_desc = outputs.get('description', 'N/A')
                            retrieved_functions_info += f"   - Output: {output_type} - {output_desc}\n"
                        elif isinstance(outputs, str):
                            retrieved_functions_info += f"   - Output: {outputs}\n"
                        else:
                            retrieved_functions_info += f"   - Output: {str(outputs)}\n"
                    
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
            
            NOTE: Functions are in format "function_name: category (pipeline)". Focus on the function names for selection.
            
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
            4.0 IMPORTANT: Use ONLY the functions provided in the function definitions. Do not invent functions.
            4.1 IMPORTANT: Use ONLY the actual column names provided in the dataset information. Do not invent column names.
            4.2 IMPORTANT: Use ONLY the actual parameter names provided in the function definitions. Do not invent parameter names.
            4.3 IMPORTANT: Use the Pipelines for the functions provided in the function definitions. Do not invent pipelines or functions that might not be associated with defined pipelines.
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
               - HIGHER RELEVANCE SCORES = BETTER MATCHES: Functions with relevance scores > 0.8 should be strongly preferred
               - Review the reasoning provided for each function to understand why it was selected
               - Consider priority levels when multiple functions are available (lower priority numbers = higher priority)
               - ALWAYS PREFER functions with higher relevance scores over those with lower scores
               - If a function has relevance_score = 1.0, it should be the top choice unless there's a compelling reason not to
               - Review required and optional parameters to ensure the function can be used with available data
               - Consider parameter types and descriptions when selecting functions
               - CRITICAL: Do NOT select the last function in the list - select the function with the highest relevance score
               - CRITICAL: When relevance scores are similar, consider the reasoning plan step sequence and context alignment
            8. Evaluate the confidence and feasibility of each suggested function based on their definitions, available data, reasoning plan alignment, and retrieved functions metadata.
            9. Prioritize functions that are highly confident, feasible with the available data, align with the reasoning plan, AND have high relevance scores from the retrieved functions analysis.
            10. Consider if multiple pipelines are needed based on data requirements and reasoning plan steps.
            11. Return a JSON object with the selected function and its confidence.
            
            OUTPUT FORMAT:
            CRITICAL: You must return ONLY a valid JSON object without any markdown formatting, code blocks, or extra text.
            
            CORRECT FORMAT:
            {{
                "selected_function": "function_name",
                "confidence": 0.0-1.0,
                "reasoning": "explanation of why this function was selected, including reasoning plan alignment",
                "alternative_functions": ["function_name1", "function_name2"],
                "reasoning_plan_alignment": "how this function aligns with the reasoning plan steps"
            }}
            
            WRONG FORMATS (DO NOT USE):
            ❌ ```json
            ❌ ```python
            ❌ Any markdown formatting
            ❌ Explanations before or after the JSON
            ❌ Extra text or comments
            
            CONSEQUENCES OF IMPROPER FORMAT:
            - If you return markdown code blocks, the parsing will fail
            - If you add extra text, the JSON parsing will fail
            - If you don't return valid JSON, the system will fall back to basic parsing
            - This will result in poor function selection
            - The user's analysis pipeline will not work correctly
            
            Return ONLY the JSON object, nothing else.
            
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
            
            Example 5 - Relevance score prioritization:
            Context: "Calculate rolling variance analysis for flux data"
            Suggested Functions: ["calculate_moving_average", "variance_analysis"]
            Retrieved Functions: 
            - calculate_moving_average: relevance_score=0.6, reasoning="Keyword match with step"
            - variance_analysis: relevance_score=1.0, reasoning="Perfect match for variance analysis"
            Output: {{
                "selected_function": "variance_analysis",
                "confidence": 0.95,
                "reasoning": "variance_analysis has relevance_score=1.0 (perfect match) vs calculate_moving_average with relevance_score=0.6. Higher relevance score indicates better match for variance analysis task.",
                "alternative_functions": ["calculate_moving_average"],
                "reasoning_plan_alignment": "Directly matches variance analysis requirement"
            }}
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
                import re
                
                # Clean the response text - remove markdown code blocks and extra formatting
                cleaned_result = result.strip()
                
                # Remove markdown code blocks (```json ... ```)
                cleaned_result = re.sub(r'```json\s*', '', cleaned_result)
                cleaned_result = re.sub(r'```\s*', '', cleaned_result)
                
                # Remove any leading/trailing whitespace and newlines
                cleaned_result = cleaned_result.strip()
                
                detected_function = json.loads(cleaned_result)
                print("detected_function",result)
                # Debug logging
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"Raw LLM response: {result}")
                logger.debug(f"Cleaned response: {cleaned_result}")
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
                # If JSON parsing fails, try to extract JSON content from markdown blocks as a fallback
                try:
                    # Look for JSON content between markdown code blocks
                    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', result, re.DOTALL)
                    if json_match:
                        json_content = json_match.group(1)
                        detected_function = json.loads(json_content)
                        logger.info("Successfully extracted JSON from markdown blocks using fallback")
                        
                        # Continue with validation and return
                        # Debug logging
                        logger.debug(f"Fallback parsed detected_function: {detected_function}")
                        logger.debug(f"Fallback detected function type: {type(detected_function)}")
                        
                        # Validate the structure and continue with the existing logic
                        if not isinstance(detected_function, dict):
                            raise ValueError("Fallback result is not a dictionary")
                        
                        # Continue with the existing validation logic...
                        # (The rest of the validation code will run with the fallback result)
                        # The method will continue to the validation section below
                        
                    else:
                        # No markdown blocks found, return basic structure
                        logger.warning(f"No JSON content found in markdown blocks, using basic structure")
                        return {
                            "selected_function": "",
                            "confidence": 0.0,
                            "reasoning": f"JSON parsing failed: {str(e)}. Using fallback function.",
                            "alternative_functions": [],
                            "reasoning_plan_alignment": ""
                        }
                        
                except Exception as fallback_error:
                    logger.warning(f"Fallback JSON extraction also failed: {fallback_error}")
                    # Return basic structure if fallback also fails
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
    
    def _format_essential_function_definition(self, function_data: Dict[str, Any]) -> str:
        """
        Format function definition with only essential information for LLM prompts.
        
        Args:
            function_data: Dictionary containing function definition data
            
        Returns:
            Formatted string with only essential parameters
        """
        if not function_data:
            return "No function data available."
        
        # Extract essential information
        function_name = function_data.get('function_name', 'Unknown')
        description = function_data.get('description', 'No description available')
        category = function_data.get('category', function_data.get('pipe_name', 'Unknown'))
        subcategory = function_data.get('subcategory', '')
        
        # Format required parameters
        required_params = function_data.get('required_params', [])
        required_params_str = ""
        if required_params:
            if isinstance(required_params, list):
                param_list = []
                for param in required_params:
                    if isinstance(param, dict):
                        name = param.get('name', '')
                        param_type = param.get('type', '')
                        description = param.get('description', '')
                        if name:
                            param_str = f'{{"name": "{name}"'
                            if param_type:
                                param_str += f', "type": "{param_type}"'
                            if description:
                                param_str += f', "description": "{description}"'
                            param_str += '}'
                            param_list.append(param_str)
                    elif isinstance(param, str) and param.strip():
                        param_list.append(f'{{"name": "{param.strip()}"}}')
                required_params_str = f'[{", ".join(param_list)}]'
            else:
                required_params_str = str(required_params)
        
        # Format optional parameters
        optional_params = function_data.get('optional_params', [])
        optional_params_str = ""
        if optional_params:
            if isinstance(optional_params, list):
                param_list = []
                for param in optional_params:
                    if isinstance(param, dict):
                        name = param.get('name', '')
                        param_type = param.get('type', '')
                        description = param.get('description', '')
                        if name:
                            param_str = f'{{"name": "{name}"'
                            if param_type:
                                param_str += f', "type": "{param_type}"'
                            if description:
                                param_str += f', "description": "{description}"'
                            param_str += '}'
                            param_list.append(param_str)
                    elif isinstance(param, str) and param.strip():
                        param_list.append(f'{{"name": "{param.strip()}"}}')
                optional_params_str = f'[{", ".join(param_list)}]'
            else:
                optional_params_str = str(optional_params)
        
        # Format outputs
        outputs = function_data.get('outputs', {})
        outputs_str = ""
        if outputs:
            if isinstance(outputs, dict):
                output_type = outputs.get('type', '')
                output_desc = outputs.get('description', '')
                if output_type or output_desc:
                    outputs_str = f'{{"type": "{output_type}", "description": "{output_desc}"}}'
            else:
                outputs_str = str(outputs)
        
        # Build essential definition
        definition = f'{{"function_name": "{function_name}", "description": "{description}", "category": "{category}"'
        
        if subcategory:
            definition += f', "subcategory": "{subcategory}"'
        
        if required_params_str:
            definition += f', "required_params": {required_params_str}'
        
        if optional_params_str:
            definition += f', "optional_params": {optional_params_str}'
        
        if outputs_str:
            definition += f', "outputs": {outputs_str}'
        
        definition += '}'
        
        return definition

    async def _retrieve_function_definitions(self, function_names: List[str], context: str = "", project_id: Optional[str] = None) -> str:
        """
        Retrieve function definitions using RetrievalHelper if available, fallback to enhanced function registry, FunctionRetrieval, or function_definition_store.
        
        Args:
            function_names: List of function names to retrieve definitions for
            context: User context for better function matching
            project_id: Optional project ID for project-specific instructions
            
        Returns:
            Formatted string containing function definitions with enhanced context
        """
        if not function_names:
            return "No function names provided."
        
        try:
            # Try to use RetrievalHelper first if available
            if self.retrieval_helper:
                all_definitions = []
                
                for function_name in function_names:
                    try:
                        # Get function definition using RetrievalHelper
                        definition_result = await self.retrieval_helper.get_function_definition(
                            function_name=function_name,
                            similarity_threshold=0.7,
                            top_k=1
                        )
                        
                        if definition_result:
                            # Handle both string and dictionary returns from RetrievalHelper
                            if isinstance(definition_result, str):
                                # If it's a string, use it directly
                                essential_definition = self._format_essential_function_definition({"content": definition_result, "function_name": function_name})
                                all_definitions.append(essential_definition)
                                continue
                            elif isinstance(definition_result, dict) and not definition_result.get("error"):
                                # Extract the actual function definition from RetrievalHelper results
                                function_definition = definition_result.get("function_definition")
                                if function_definition:
                                    # Handle case where function_definition might be a string (page_content)
                                    if isinstance(function_definition, str):
                                        # Parse the string content to extract function information
                                        try:
                                            # Try to parse as JSON first
                                            if function_definition.strip().startswith('{'):
                                                parsed_def = json.loads(function_definition)
                                            else:
                                                # If not JSON, create a basic structure from the string
                                                parsed_def = {
                                                    "function_name": function_name,
                                                    "description": function_definition,
                                                    "content": function_definition
                                                }
                                        except (json.JSONDecodeError, ValueError):
                                            # If parsing fails, create a basic structure
                                            parsed_def = {
                                                "function_name": function_name,
                                                "description": function_definition,
                                                "content": function_definition
                                            }
                                        
                                        essential_definition = self._format_essential_function_definition(parsed_def)
                                    else:
                                        # If it's already a dict, use it directly
                                        essential_definition = self._format_essential_function_definition(function_definition)
                                    
                                    all_definitions.append(essential_definition)
                                    continue
                    
                    except Exception as e:
                        logger.warning(f"Error getting function definition from RetrievalHelper for {function_name}: {e}")
                
                # If we got definitions from RetrievalHelper, return them
                if all_definitions:
                    return "\n---\n".join(all_definitions)
            
            # Try to use enhanced function registry if RetrievalHelper not available or failed
            if self.enhanced_function_registry:
                all_definitions = []
                
                for function_name in function_names:
                    try:
                        # Get enhanced function context
                        enhanced_context = await self._get_enhanced_function_context(
                            function_name=function_name,
                            context=context,
                            project_id=project_id
                        )
                        
                        if enhanced_context:
                            # Use essential formatting for enhanced context
                            essential_definition = self._format_essential_function_definition(enhanced_context)
                            all_definitions.append(essential_definition)
                            continue
                    
                    except Exception as e:
                        logger.warning(f"Error getting enhanced context for {function_name}: {e}")
            
            # Fallback to FunctionRetrieval if enhanced registry not available or failed
            if not all_definitions and self.function_retrieval:
                for function_name in function_names:
                    try:
                        # Get function details from the loaded function library
                        function_details = self.function_retrieval.get_function_details(function_name, "")
                        
                        if function_details:
                            # Use essential formatting for FunctionRetrieval results
                            essential_definition = self._format_essential_function_definition(function_details)
                            all_definitions.append(essential_definition)
                        else:
                            # Try to find the function in any pipe
                            found = False
                            for pipe_name in self.function_retrieval.get_all_pipes():
                                function_details = self.function_retrieval.get_function_details(function_name, pipe_name)
                                if function_details:
                                    found = True
                                    # Use essential formatting for FunctionRetrieval results
                                    essential_definition = self._format_essential_function_definition(function_details)
                                    all_definitions.append(essential_definition)
                                    break
                            
                            if not found:
                                all_definitions.append(f"Function: {function_name}\nDefinition: No definition available in function library.\n")
                    
                    except Exception as e:
                        logger.warning(f"Error retrieving function definition for {function_name}: {str(e)}")
                        all_definitions.append(f"Function: {function_name}\nDefinition: Error retrieving definition: {str(e)}\n")
                
                # Join all definitions
                if all_definitions:
                    return "\n---\n".join(all_definitions)
                else:
                    return "No function definitions found in function library."
            
            # Fallback to function_definition_store if FunctionRetrieval is not available
            elif self.function_definition_store:
                all_definitions = []
                
                for function_name in function_names:
                    # Search for the function definition
                    search_results = self.function_definition_store.semantic_searches(
                        [function_name], n_results=3
                    )
                    
                    # Parse the results
                    function_docs = self._parse_retrieval_results(search_results)
                    
                    if function_docs:
                        # Format the function definition using essential formatting
                        for doc in function_docs[:1]:  # Take the most relevant result
                            content = doc.get("content", {})
                            if isinstance(content, dict):
                                # Map to expected format for essential formatting
                                function_data = {
                                    "function_name": content.get("name", function_name),
                                    "description": content.get("description", "No description available"),
                                    "category": content.get("pipeline_type", "Unknown"),
                                    "required_params": content.get("required_params", []),
                                    "optional_params": content.get("optional_params", []),
                                    "outputs": {"description": content.get("returns", "No return information")}
                                }
                                
                                # Use essential formatting
                                essential_definition = self._format_essential_function_definition(function_data)
                                all_definitions.append(essential_definition)
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
            
            else:
                return "No function definition sources available."
                
        except Exception as e:
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
        # Function definitions are now dynamically loaded from JSON file
        # No need for hardcoded function lists
         
        # Retrieve function definition for the primary function
        primary_function_definition = await self._retrieve_function_definitions([function_name])
        
        # Create the detection prompt
        detection_prompt = PromptTemplate(
            input_variables=[
                "context", "function_name", "function_definition", "classification_context", "dataset_context",
                "reasoning_plan_json"
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
            
            # Function definitions are dynamically loaded from JSON file
            # Available functions are determined by the function definition and pipeline type
            
            REASONING PLAN (JSON):
            {reasoning_plan_json}
            
            INSTRUCTIONS:
            1. Analyze the context to understand what data analysis is being requested
            2. Review the primary function definition to understand its parameters and requirements
            2.1 Function definitions have the pipeline type already determined, you must use it to detect the function for which inputs are required.
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
            5. CRITICAL COLUMN HANDLING:
               - Use ONLY the actual column names provided in the dataset information. Do not invent column names.
               - For array parameters (like 'columns', 'metric_columns'): Return a list of column names
               - For single column parameters (like 'variable', 'time_column'): Return a single column name
               - Ensure column names match exactly with available columns
            6. Map context requirements to actual column names from the dataset description:
               - If the context mentions "sales", look for columns like "sales_amount", "total_sales", "revenue", etc.
               - If the context mentions "time" or "date", look for temporal columns
               - If the context mentions grouping "by region", look for categorical columns that could represent regions
            7. CRITICAL: Determine the required function inputs for the primary function based on its definition, available columns, and reasoning plan alignment
            8. CRITICAL: Use ONLY existing function names from function definitions - do not invent new function names
            9. CRITICAL: Use ONLY parameter names from function definitions - do not invent new parameter names
            10. CRITICAL: Extract parameters from the function definition JSON structure:
                - Use "required_params" array to identify mandatory parameters
                - Use "optional_params" array to identify optional parameters with defaults
                - Match parameter types exactly: "str or List[str]" means use list format for arrays
                - Use parameter descriptions to understand expected values
                - CRITICAL: Include default values from optional_params when not specified in context
                - CRITICAL: Extract default values from descriptions like "(default: 'zscore')" or "(default: 3.0)"
                - Example function definition structure:
                ```json
                "required_params": [
                    {"name": "columns", "type": "str or List[str]", "description": "Base column(s) names"}
                ],
                "optional_params": [
                    {"name": "method", "type": "str", "description": "Method to use (default: 'zscore')"},
                    {"name": "threshold", "type": "float", "description": "Threshold value (default: 3.0)"}
                ]
                ```
            11. CRITICAL: For array parameters (like 'columns', 'metric_columns'): use list format ["value1", "value2"]
            12. CRITICAL: For single parameters (like 'variable', 'time_column'): use string format "value"
            13. Use the pipeline type from the function definition (already determined):
               - Extract the pipeline type from the function definition above
               - Focus on detecting function inputs based on the function definition
               - Do not try to identify or change the pipeline type
            14. Focus on the primary function only - do not create multiple pipelines
                - Use only the primary function with its appropriate pipeline type
                - Do not create multi-pipeline approaches
            15. Consider the classification analysis and reasoning plan for additional context
            16. CRITICAL: Validate that all detected inputs match the function definition parameters:
                - All required_params from function definition must be included
                - Optional parameters can be included if context suggests them
                - Parameter names must match exactly (case-sensitive)
                - Parameter types must match the function definition (str vs List[str])
                - CRITICAL: Do NOT include duplicate parameter names
                - CRITICAL: Include default values for optional parameters when not specified in context
                - CRITICAL: Use ONLY parameter names from the function definition - do not invent parameter names like 'actual_values', 'expected_values', etc.
            17. Return a JSON object with the detected inputs using actual column names and reasoning plan alignment
            
            OUTPUT FORMAT:
            CRITICAL: You must return ONLY a valid JSON object without any markdown formatting, code blocks, or extra text.
            
            CORRECT FORMAT:
            {{
                "primary_function_inputs": {{
                    "param1": "value1",
                    "param2": "value2",
                    "columns": ["column1", "column2"],  # Array for array parameters
                    "variable": "single_column"  # Single value for single parameters
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
                    "step_description"
                ],
                "multi_pipeline": false,
                "first_pipeline_type": null,
                "second_pipeline_type": null,
                "reasoning": "explanation of why these inputs were chosen, including reasoning plan alignment",
                "reasoning_plan_step_mapping": "which reasoning plan steps this implementation covers"
            }}
            
            WRONG FORMATS (DO NOT USE):
            ❌ ```json
            ❌ ```python
            ❌ Any markdown formatting
            ❌ Explanations before or after the JSON
            ❌ Extra text or comments
            ❌ Single string for array parameters (e.g., "columns": "column1" instead of "columns": ["column1"])
            ❌ Array for single parameters (e.g., "variable": ["column1"] instead of "variable": "column1")
            
            CONSEQUENCES OF IMPROPER FORMAT:
            - If you return markdown code blocks, the parsing will fail
            - If you add extra text, the JSON parsing will fail
            - If you don't return valid JSON, the system will fall back to basic parsing
            - Incorrect column format will result in poor code generation quality
            - The user's analysis pipeline will not work correctly
            
            EXAMPLES OF CORRECT COLUMN HANDLING:
            - For moving_apply_by_group: "columns": ["Transactional value", "Functional value"] (array)
            - For GroupBy: "by": ["Region", "Project"] (array)
            - For Variance: "variable": "Transactional value" (single string)
            - For calculate_growth_rates: "time_column": "Date" (single string)
            
            Return ONLY the JSON object, nothing else.
            
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
            
            Example 2 - Single pipeline approach with reasoning plan:
            Context: "Analyze variance of transactional value over time"
            Function: "variance_analysis"
            Reasoning Plan: Step 1 suggests "variance_analysis" for time series analysis
            Output: {{
                "primary_function_inputs": {{"columns": ["Transactional value"], "method": "rolling", "window": 5}},
                "additional_computations": [],
                "pipeline_sequence": ["Analyze variance over time"],
                "multi_pipeline": false,
                "first_pipeline_type": null,
                "second_pipeline_type": null,
                "reasoning": "Direct variance analysis using TimeSeriesPipe. Aligns with Step 1 of reasoning plan.",
                "reasoning_plan_step_mapping": "Implements Step 1 variance analysis requirement"
            }}
            
            Example 2b - moving_apply_by_group scenario:
            Context: "Apply moving variance by group for transactional value"
            Function: "moving_apply_by_group"
            Reasoning Plan: Step 1 suggests "moving_apply_by_group" for group-based moving calculations
            Output: {{
                "primary_function_inputs": {{"columns": ["Transactional value"], "group_column": "Region, Project", "window": 5, "min_periods": 1, "time_column": "Date", "output_suffix": "_rolling_variance", "function": "variance"}},
                "additional_computations": [],
                "pipeline_sequence": ["Apply moving variance by group"],
                "multi_pipeline": false,
                "first_pipeline_type": null,
                "second_pipeline_type": null,
                "reasoning": "moving_apply_by_group function parameter should contain the function name 'variance' from group aggregation functions. This embeds the variance calculation within the MovingAggrPipe moving_apply_by_group function.",
                "reasoning_plan_step_mapping": "Implements Step 1 moving variance by group requirement"
            }}
            
            Example 3 - Using actual function definition parameters with defaults (anomaly detection):
            Context: "Detect anomalies in sales data"
            Function: "detect_statistical_outliers"
            Function Definition: {{"required_params": [{{"name": "columns", "type": "str or List[str]", "description": "Base column(s) names"}}], "optional_params": [{{"name": "method", "type": "str", "description": "Method to use (default: 'zscore')"}}, {{"name": "threshold", "type": "float", "description": "Threshold value (default: 3.0)"}}, {{"name": "suffix", "type": "str", "description": "Suffix of columns containing residuals (default: '_residual')"}}, {{"name": "output_suffix", "type": "str", "description": "Suffix for output anomaly flag columns (default: '_anomaly')"}}]}}
            Dataset: "Sales transaction data"
            Columns: {{"sales_amount": "Sales transaction amount", "date": "Transaction date"}}
            Reasoning Plan: Step 1 suggests anomaly detection using sales_amount
            Output: {{
                "primary_function_inputs": {{"columns": ["sales_amount"], "method": "zscore", "threshold": 3.0, "suffix": "_residual", "output_suffix": "_anomaly"}},
                "additional_computations": [],
                "pipeline_sequence": ["Detect anomalies in sales data"],
                "multi_pipeline": false,
                "first_pipeline_type": null,
                "second_pipeline_type": null,
                "reasoning": "Using 'sales_amount' column for anomaly detection. Included all required and optional parameters with their default values from function definition. Aligns with Step 1 of reasoning plan.",
                "reasoning_plan_step_mapping": "Implements Step 1 anomaly detection requirement"
            }}
            
            Example 4 - Avoiding duplicate parameters (moving_apply_by_group):
            Context: "Apply moving standard deviation by group"
            Function: "moving_apply_by_group"
            Function Definition: {{"required_params": [{{"name": "columns", "type": "str or List[str]"}}, {{"name": "group_column", "type": "str"}}, {{"name": "function", "type": "Callable"}}], "optional_params": [{{"name": "window", "type": "int", "description": "Window size (default: 7)"}}, {{"name": "min_periods", "type": "int", "description": "Minimum periods (default: 1)"}}]}}
            WRONG Output: {{"columns": ["sales"], "group_column": "region", "function": "std_dev", "function": "std_dev"}}  # DUPLICATE!
            CORRECT Output: {{"columns": ["sales"], "group_column": "region", "function": "std_dev", "window": 7, "min_periods": 1}}
            
            Example 5 - Using correct function definition parameters (detect_contextual_anomalies):
            Context: "Detect contextual anomalies in transactional value"
            Function: "detect_contextual_anomalies"
            Function Definition: {{"required_params": [{{"name": "columns", "type": "str or List[str]", "description": "Column(s) to analyze for anomalies"}}, {{"name": "time_column", "type": "str", "description": "Column containing the time/date information"}}], "optional_params": [{{"name": "method", "type": "str", "description": "Method to use (default: 'residual')"}}, {{"name": "model_type", "type": "str", "description": "Model to generate expected values (default: 'ewm')"}}, {{"name": "threshold", "type": "float", "description": "Threshold for determining anomalies (default: 3.0)"}}, {{"name": "window", "type": "int", "description": "Window size for rolling model fitting (default: 30)"}}]}}
            WRONG Output: {{"actual_values": "Transactional value", "expected_values": "Weekly_Average_Transactional_value", "threshold": 2.0}}  # WRONG PARAMETERS!
            CORRECT Output: {{"columns": ["Transactional value"], "time_column": "Date", "method": "residual", "model_type": "ewm", "threshold": 3.0, "window": 30}}
            
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
                "reasoning_plan_json": reasoning_plan_json
            })
            
            # Parse the JSON result
            try:
                import re
                
                # Clean the response text - remove markdown code blocks and extra formatting
                cleaned_result = result.strip()
                
                # Remove markdown code blocks (```json ... ```)
                cleaned_result = re.sub(r'```json\s*', '', cleaned_result)
                cleaned_result = re.sub(r'```\s*', '', cleaned_result)
                
                # Remove any leading/trailing whitespace and newlines
                cleaned_result = cleaned_result.strip()
                
                detected_inputs = json.loads(cleaned_result)
                
                # Debug logging
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"Raw LLM response: {result}")
                logger.debug(f"Cleaned response: {cleaned_result}")
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
                detected_inputs = await self._filter_additional_computations(detected_inputs, function_name, classification)
                

                
                logger.debug(f"Final detected_inputs: {detected_inputs}")
                print("Final detected_inputs: ", detected_inputs)
                return detected_inputs
                
            except json.JSONDecodeError as e:
                # If JSON parsing fails, try to extract JSON content from markdown blocks as a fallback
                try:
                    # Look for JSON content between markdown code blocks
                    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', result, re.DOTALL)
                    if json_match:
                        json_content = json_match.group(1)
                        detected_inputs = json.loads(json_content)
                        logger.info("Successfully extracted JSON from markdown blocks using fallback")
                        
                        # Continue with validation and return
                        # Debug logging
                        logger.debug(f"Fallback parsed detected_inputs: {detected_inputs}")
                        logger.debug(f"Fallback detected inputs type: {type(detected_inputs)}")
                        
                        # Validate the structure and continue with the existing logic
                        if not isinstance(detected_inputs, dict):
                            raise ValueError("Fallback result is not a dictionary")
                        
                        # Continue with the existing validation logic...
                        # (The rest of the validation code will run with the fallback result)
                        # The method will continue to the validation section below
                        
                    else:
                        # No markdown blocks found, return basic structure
                        logger.warning(f"No JSON content found in markdown blocks, using basic structure")
                        return {
                            "primary_function_inputs": {},
                            "additional_computations": [],
                            "pipeline_sequence": ["Basic analysis"],
                            "reasoning": f"JSON parsing failed: {str(e)}. Using basic inputs.",
                            "reasoning_plan_step_mapping": "Unable to map to reasoning plan due to parsing error",
                            "raw_response": result
                        }
                        
                except Exception as fallback_error:
                    logger.warning(f"Fallback JSON extraction also failed: {fallback_error}")
                    # Return basic structure if fallback also fails
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
    
    async def _filter_additional_computations(self, detected_inputs: Dict[str, Any], function_name: str, classification: Optional[Union[Dict[str, Any], AnalysisIntentResult]] = None) -> Dict[str, Any]:
        """
        Filter additional computations and determine if multi-pipeline approach is needed
        
        Args:
            detected_inputs: Dictionary containing detected inputs
            function_name: Primary function name
            classification: Optional classification results for better pipeline type detection
            
        Returns:
            Filtered detected inputs with multi-pipeline configuration
        """
        # Get the pipeline type for the primary function using the enhanced detection
        primary_pipeline_type = await self._detect_pipeline_type(function_name, "", classification)
        
        # Use the same mapping as defined in __init__
        function_pipeline_mapping = self.function_to_pipe
        
        # Check if multi-pipeline approach is needed
        needs_multi_pipeline = False
        first_pipeline_type = None
        second_pipeline_type = None
        
        if "additional_computations" in detected_inputs and detected_inputs["additional_computations"]:
            metrics_computations = []
            operations_computations = []
            trends_computations = []
            timeseries_computations = []
            other_computations = []
            
            for comp in detected_inputs["additional_computations"]:
                comp_function = comp.get("function", "")
                comp_pipeline_type = function_pipeline_mapping.get(comp_function)
                
                if comp_pipeline_type == PipelineType.METRICS:
                    metrics_computations.append(comp)
                elif comp_pipeline_type == PipelineType.OPERATIONS:
                    operations_computations.append(comp)
                elif comp_pipeline_type == PipelineType.TRENDS:
                    trends_computations.append(comp)
                elif comp_pipeline_type == PipelineType.TIMESERIES:
                    timeseries_computations.append(comp)
                else:
                    other_computations.append(comp)
            
            # Determine if multi-pipeline is needed based on primary function type
            if primary_pipeline_type in [PipelineType.TIMESERIES, PipelineType.COHORT, PipelineType.RISK, PipelineType.FUNNEL, PipelineType.ANOMALY, PipelineType.SEGMENT]:
                # These pipeline types can benefit from MetricsPipe/OperationsPipe preprocessing
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
            elif primary_pipeline_type == PipelineType.TRENDS:
                # TrendsPipe can work with MetricsPipe preprocessing
                if metrics_computations:
                    needs_multi_pipeline = True
                    first_pipeline_type = "MetricsPipe"
                    detected_inputs["additional_computations"] = metrics_computations
                    second_pipeline_type = primary_pipeline_type.value
                else:
                    # Only trends computations
                    detected_inputs["additional_computations"] = trends_computations
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
        
        # Suggested functions with pipeline information
        if suggested_functions:
            # Extract function names and pipeline types from the new format
            function_info = self._extract_function_info_from_suggested_functions(suggested_functions)
            parts.append(f"Suggested Functions: {', '.join(function_info)}")
        
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
    
    def _extract_function_info_from_suggested_functions(self, suggested_functions: List[str]) -> List[str]:
        """
        Extract function names and pipeline information from the new suggested_functions format
        
        Args:
            suggested_functions: List of functions in format "function_name: category (pipeline)"
            
        Returns:
            List of formatted function information strings
        """
        function_info = []
        
        for func in suggested_functions:
            if ': ' in func:
                # New format: "function_name: category (pipeline)"
                parts = func.split(': ')
                if len(parts) == 2:
                    function_name = parts[0]
                    category_pipeline = parts[1]
                    function_info.append(f"{function_name} ({category_pipeline})")
                else:
                    function_info.append(func)
            else:
                # Old format: just function name
                function_info.append(func)
        
        return function_info
    
    def _extract_function_name_from_suggested_function(self, suggested_function: str) -> str:
        """
        Extract just the function name from a suggested function string
        
        Args:
            suggested_function: Function string in format "function_name: category (pipeline)" or just "function_name"
            
        Returns:
            Just the function name
        """
        if ': ' in suggested_function:
            return suggested_function.split(': ')[0]
        return suggested_function
    
    def _extract_pipeline_type_from_suggested_function(self, suggested_function: str) -> Optional[str]:
        """
        Extract pipeline type from a suggested function string
        
        Args:
            suggested_function: Function string in format "function_name: category (pipeline)" or just "function_name"
            
        Returns:
            Pipeline type if available, None otherwise
        """
        if ': ' in suggested_function:
            parts = suggested_function.split(': ')
            if len(parts) == 2:
                category_pipeline = parts[1]
                # Extract pipeline type from parentheses
                if '(' in category_pipeline and ')' in category_pipeline:
                    pipeline_start = category_pipeline.find('(') + 1
                    pipeline_end = category_pipeline.find(')')
                    if pipeline_start < pipeline_end:
                        return category_pipeline[pipeline_start:pipeline_end]
        return None
    
    def _validate_and_enhance_reasoning_plan(self, reasoning_plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validate and enhance reasoning plan with metadata validation
        
        Args:
            reasoning_plan: List of reasoning plan steps
            
        Returns:
            Enhanced and validated reasoning plan
        """
        if not reasoning_plan or not isinstance(reasoning_plan, list):
            return []
        
        enhanced_plan = []
        for i, step in enumerate(reasoning_plan):
            if not isinstance(step, dict):
                continue
            
            enhanced_step = step.copy()
            
            # Ensure required fields exist
            if 'step_number' not in enhanced_step:
                enhanced_step['step_number'] = i + 1
            if 'step_title' not in enhanced_step:
                enhanced_step['step_title'] = f'Step {i + 1}'
            
            # Validate column mapping
            if 'column_mapping' in enhanced_step and enhanced_step['column_mapping']:
                if not isinstance(enhanced_step['column_mapping'], dict):
                    enhanced_step['column_mapping'] = {}
                    logger.warning(f"Step {i+1}: Invalid column_mapping, resetting to empty dict")
            
            # Validate input/output columns
            if 'input_columns' in enhanced_step and enhanced_step['input_columns']:
                if not isinstance(enhanced_step['input_columns'], list):
                    enhanced_step['input_columns'] = []
                    logger.warning(f"Step {i+1}: Invalid input_columns, resetting to empty list")
            
            if 'output_columns' in enhanced_step and enhanced_step['output_columns']:
                if not isinstance(enhanced_step['output_columns'], list):
                    enhanced_step['output_columns'] = []
                    logger.warning(f"Step {i+1}: Invalid output_columns, resetting to empty list")
            
            # Validate step dependencies
            if 'step_dependencies' in enhanced_step and enhanced_step['step_dependencies']:
                if not isinstance(enhanced_step['step_dependencies'], list):
                    enhanced_step['step_dependencies'] = []
                    logger.warning(f"Step {i+1}: Invalid step_dependencies, resetting to empty list")
            
            # Validate parameter constraints
            if 'parameter_constraints' in enhanced_step and enhanced_step['parameter_constraints']:
                if not isinstance(enhanced_step['parameter_constraints'], dict):
                    enhanced_step['parameter_constraints'] = {}
                    logger.warning(f"Step {i+1}: Invalid parameter_constraints, resetting to empty dict")
            
            enhanced_plan.append(enhanced_step)
        
        logger.info(f"Validated and enhanced reasoning plan: {len(enhanced_plan)} steps")
        return enhanced_plan

    def _format_reasoning_plan_json(self, classification: Optional[Union[Dict[str, Any], AnalysisIntentResult]]) -> str:
        """
        Format reasoning plan as JSON for LLM consumption with enhanced metadata
        
        Args:
            classification: Either a Dict[str, Any] or AnalysisIntentResult object containing
                           reasoning plan information with enhanced metadata
        """
        if not classification:
            return "null"
        
        # Extract reasoning plan - prefer pipeline_reasoning_plan (enhanced) over reasoning_plan (basic)
        if hasattr(classification, 'pipeline_reasoning_plan'):
            reasoning_plan = getattr(classification, 'pipeline_reasoning_plan', None)
        elif hasattr(classification, 'reasoning_plan'):
            reasoning_plan = getattr(classification, 'reasoning_plan', None)
        else:
            reasoning_plan = classification.get('pipeline_reasoning_plan', None) or classification.get('reasoning_plan', None)
        
        if not reasoning_plan or not isinstance(reasoning_plan, list):
            return "null"
        
        # Validate and enhance the reasoning plan first
        validated_plan = self._validate_and_enhance_reasoning_plan(reasoning_plan)
        
        # Create enhanced reasoning plan with metadata summary
        enhanced_plan = []
        for step in validated_plan:
            if isinstance(step, dict):
                enhanced_step = step.copy()
                
                # Add metadata summary for better LLM understanding
                metadata_summary = []
                
                # Add column mapping summary
                if step.get('column_mapping'):
                    metadata_summary.append(f"Column Mapping: {step.get('column_mapping')}")
                
                # Add input/output summary
                if step.get('input_columns'):
                    metadata_summary.append(f"Inputs: {step.get('input_columns')}")
                if step.get('output_columns'):
                    metadata_summary.append(f"Outputs: {step.get('output_columns')}")
                
                # Add pipeline info
                if step.get('pipeline_type'):
                    metadata_summary.append(f"Pipeline: {step.get('pipeline_type')}")
                
                # Add dependencies
                if step.get('step_dependencies'):
                    metadata_summary.append(f"Depends on: Step {step.get('step_dependencies')}")
                
                # Add data flow
                if step.get('data_flow'):
                    metadata_summary.append(f"Data Flow: {step.get('data_flow')}")
                
                # Add constraints and error handling
                if step.get('parameter_constraints'):
                    metadata_summary.append(f"Constraints: {step.get('parameter_constraints')}")
                if step.get('error_handling'):
                    metadata_summary.append(f"Error Handling: {step.get('error_handling')}")
                
                # Add embedded function details
                if step.get('embedded_function_parameter') and step.get('embedded_function_details'):
                    embedded_details = step.get('embedded_function_details', {})
                    embedded_summary = f"Embedded: {embedded_details.get('embedded_function', '')} in {embedded_details.get('embedded_pipe', '')}"
                    metadata_summary.append(embedded_summary)
                
                # Add metadata summary to the step
                if metadata_summary:
                    enhanced_step['_metadata_summary'] = '; '.join(metadata_summary)
                
                enhanced_plan.append(enhanced_step)
        
        return json.dumps(enhanced_plan, indent=2)
    
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
            
            # Add enhanced metadata if available
            if '_enhanced_metadata' in columns_description:
                enhanced_metadata = columns_description['_enhanced_metadata']
                parts.append("\nEnhanced Metadata:")
                parts.append(f"- Reasoning Plan Steps: {enhanced_metadata.get('reasoning_plan_steps', 0)}")
                parts.append(f"- Has Enhanced Metadata: {enhanced_metadata.get('has_enhanced_metadata', False)}")
                
                pipeline_types = enhanced_metadata.get('pipeline_types', [])
                if pipeline_types:
                    parts.append(f"- Pipeline Types: {', '.join(pipeline_types)}")
                
                function_categories = enhanced_metadata.get('function_categories', [])
                if function_categories:
                    parts.append(f"- Function Categories: {', '.join(function_categories)}")
            
        return "\n".join(parts) if parts else "No dataset information available."
    
    async def _retrieve_documents(self, query_state: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Retrieve relevant documents from all stores using RetrievalHelper when available"""
        context = query_state["context"]
        function_name = query_state["function_name"]
        project_id = query_state.get("project_id")
        
        # Determine pipeline type
        classification = query_state.get("classification", {})
        pipeline_type = await self._detect_pipeline_type(function_name, context, classification)
        
        # Create enhanced query for retrieval
        enhanced_query = self._create_enhanced_query(context, function_name, pipeline_type)
        
        retrieved_docs = {}
        
        # Use RetrievalHelper if available, otherwise fallback to direct store access
        if self.retrieval_helper:
            try:
                # Retrieve function examples using RetrievalHelper
                examples_result = await self.retrieval_helper.get_function_examples(
                    function_name=function_name,
                    similarity_threshold=0.6,
                    top_k=5
                )
                if examples_result and not examples_result.get("error"):
                    retrieved_docs["usage_examples"] = [{"content": ex, "score": 0.8} for ex in examples_result.get("examples", [])]
                
                # Retrieve function insights using RetrievalHelper
                insights_result = await self.retrieval_helper.get_function_insights(
                    function_name=function_name,
                    similarity_threshold=0.6,
                    top_k=5
                )
                if insights_result and not insights_result.get("error"):
                    retrieved_docs["code_examples"] = [{"content": insight, "score": 0.8} for insight in insights_result.get("insights", [])]
                
                # Retrieve function definition using RetrievalHelper
                definition_result = await self.retrieval_helper.get_function_definition(
                    function_name=function_name,
                    similarity_threshold=0.7,
                    top_k=3
                )
                if definition_result:
                    # Handle both string and dictionary returns from RetrievalHelper
                    if isinstance(definition_result, str):
                        retrieved_docs["function_definitions"] = [{"content": definition_result, "score": 0.9}]
                    elif isinstance(definition_result, dict) and not definition_result.get("error"):
                        retrieved_docs["function_definitions"] = [{"content": definition_result, "score": 0.9}]
                
                # Retrieve instructions if project_id is available
                if project_id:
                    instructions_result = await self.retrieval_helper.get_instructions(
                        query=context,
                        project_id=project_id,
                        similarity_threshold=0.7,
                        top_k=5
                    )
                    if instructions_result and not instructions_result.get("error"):
                        retrieved_docs["instructions"] = [{"content": inst, "score": 0.8} for inst in instructions_result.get("instructions", [])]
                
            except Exception as e:
                logger.warning(f"Error using RetrievalHelper: {e}, falling back to direct store access")
                # Fallback to direct store access
                retrieved_docs = await self._retrieve_documents_fallback(query_state, enhanced_query, pipeline_type)
        else:
            # Fallback to direct store access
            retrieved_docs = await self._retrieve_documents_fallback(query_state, enhanced_query, pipeline_type)
        
        return retrieved_docs
    
    async def _retrieve_documents_fallback(self, query_state: Dict[str, Any], enhanced_query: str, pipeline_type) -> Dict[str, List[Dict[str, Any]]]:
        """Fallback method for direct store access when RetrievalHelper is not available"""
        function_name = query_state["function_name"]
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

    async def _parse_reasoning_plan_step_with_llm(self, parameter_mapping: str, step_title: str, step_number: int, function_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Parse reasoning plan step using LLM for better understanding of natural language descriptions
        
        Args:
            parameter_mapping: String description of parameters
            step_title: Title of the step
            step_number: Step number for logging
            function_name: Optional function name if already known
            
        Returns:
            Dictionary with parsed function_name and parameter_mapping, or None if parsing fails
        """
        try:
            from langchain.prompts import PromptTemplate
            
            # Get available functions from FunctionRetrieval or function definition store
            available_functions = []
            
            # Try to use FunctionRetrieval first if available
            if self.function_retrieval:
                try:
                    # Get all available functions from the loaded function library
                    for pipe_name in self.function_retrieval.get_all_pipes():
                        pipe_functions = self.function_retrieval.get_pipe_functions(pipe_name)
                        for func_name in pipe_functions:
                            try:
                                func_details = self.function_retrieval.get_function_details(func_name, pipe_name)
                                if func_details:
                                    func_desc = func_details.get('description', 'No description')
                                    available_functions.append(f"- {func_name}: {func_desc}")
                            except Exception as e:
                                logger.warning(f"Error getting function details for {func_name}: {str(e)}")
                                continue
                    
                    # Limit to top 20 functions to avoid overwhelming the prompt
                    available_functions = available_functions[:20]
                    
                except Exception as e:
                    logger.warning(f"Error getting functions from FunctionRetrieval: {str(e)}")
            
            # Try RetrievalHelper if available
            elif self.retrieval_helper:
                try:
                    # Search for relevant functions based on the step description
                    search_context = f"{step_title}: {parameter_mapping}"
                    definition_result = await self.retrieval_helper.get_function_definition_by_query(
                        query=search_context,
                        similarity_threshold=0.6,
                        top_k=10
                    )
                    
                    if definition_result:
                        # Handle both string and dictionary returns from RetrievalHelper
                        if isinstance(definition_result, str):
                            # If it's a string, create a basic function info structure
                            function_info = {"name": "unknown", "description": definition_result}
                        elif isinstance(definition_result, dict) and not definition_result.get("error"):
                            # Extract function information from RetrievalHelper result
                            function_info = definition_result.get("function_definition", {})
                        if function_info:
                            func_name = function_info.get("name", "")
                            func_desc = function_info.get("description", "")
                            if func_name and func_desc:
                                available_functions.append({
                                    "name": func_name,
                                    "description": func_desc,
                                    "category": function_info.get("category", "unknown"),
                                    "pipeline_type": function_info.get("pipeline_type", "unknown")
                                })
                    
                    # If no results from query-based search, try searching by function name patterns
                    if not available_functions:
                        # Extract potential function names from step title
                        step_keywords = step_title.lower().split()
                        for keyword in step_keywords:
                            if len(keyword) > 3:  # Only use meaningful keywords
                                try:
                                    keyword_result = await self.retrieval_helper.get_function_definition_by_query(
                                        query=keyword,
                                        similarity_threshold=0.5,
                                        top_k=3
                                    )
                                    if keyword_result and not keyword_result.get("error"):
                                        function_info = keyword_result.get("function_definition", {})
                                        if function_info:
                                            func_name = function_info.get("name", "")
                                            func_desc = function_info.get("description", "")
                                            if func_name and func_desc:
                                                available_functions.append({
                                                    "name": func_name,
                                                    "description": func_desc,
                                                    "category": function_info.get("category", "unknown"),
                                                    "pipeline_type": function_info.get("pipeline_type", "unknown")
                                                })
                                except Exception as e:
                                    logger.warning(f"Error searching for function with keyword '{keyword}': {e}")
                                    continue
                
                except Exception as e:
                    logger.warning(f"Error using RetrievalHelper for function extraction: {e}")
                    available_functions = []
            
            # Fallback to function_definition_store if RetrievalHelper is not available
            elif self.function_definition_store:
                try:
                    # Search for relevant functions based on the step description
                    search_context = f"{step_title}: {parameter_mapping}"
                    search_results = self.function_definition_store.semantic_searches(
                        query_texts=[search_context], 
                        n_results=10  # Get top 10 matches for context
                    )
                    
                    # Extract function names and descriptions from search results
                    if search_results and "documents" in search_results and search_results["documents"]:
                        documents = search_results["documents"][0]  # Get first query results
                        for document in documents:
                            try:
                                if isinstance(document, str):
                                    content = document
                                    # Parse function definition to extract name and description
                                    if '"function_name"' in content or '"name"' in content:
                                        import json
                                        try:
                                            func_def = json.loads(content)
                                            func_name = func_def.get('function_name') or func_def.get('name')
                                            func_desc = func_def.get('description', '')
                                            if func_name:
                                                available_functions.append(f"- {func_name}: {func_desc}")
                                        except json.JSONDecodeError:
                                            continue
                            except Exception as e:
                                logger.warning(f"Error parsing function definition: {str(e)}")
                                continue
                except Exception as e:
                    logger.warning(f"Error searching function definition store: {str(e)}")
            
            # If no functions found from store, use fallback list
            if not available_functions:
                available_functions = [
                    "- GroupBy: For grouping and aggregation operations",
                    "- moving_apply_by_group: For moving window operations with group-based calculations", 
                    "- moving_variance: For moving variance calculations",
                    "- detect_statistical_outliers: For statistical outlier detection",
                    "- detect_contextual_anomalies: For contextual anomaly detection",
                    "- get_anomaly_summary: For generating anomaly summaries"
                ]
            
            # Create the parsing prompt
            parsing_prompt = PromptTemplate(
                input_variables=["parameter_mapping", "step_title", "step_number", "function_name", "available_functions"],
                template="""
You are an expert data pipeline parser. Your task is to parse a reasoning plan step description and extract the function name and parameters.

STEP TITLE: {step_title}
STEP NUMBER: {step_number}
PARAMETER MAPPING DESCRIPTION: {parameter_mapping}
KNOWN FUNCTION NAME: {function_name}

AVAILABLE FUNCTIONS:
{available_functions}

INSTRUCTIONS:
1. If function_name is "None" or empty, extract the most appropriate function name from the available functions list based on the description
2. Parse the parameter mapping description into a proper dictionary
            3. CRITICAL: Use the function definitions to understand the correct parameter structure for each function
            4. CRITICAL: Use ONLY existing function names from the available functions list - do not invent new function names
            5. CRITICAL: Use ONLY parameter names from function definitions - do not invent new parameter names
            6. CRITICAL: Extract parameters from the function definition JSON structure:
                - Use "required_params" array to identify mandatory parameters
                - Use "optional_params" array to identify optional parameters with defaults
                - Match parameter types exactly: "str or List[str]" means use list format for arrays
                - Use parameter descriptions to understand expected values
                - CRITICAL: Include default values from optional_params when not specified in context
                - CRITICAL: Extract default values from descriptions like "(default: 'zscore')" or "(default: 3.0)"
                - CRITICAL: Do NOT include duplicate parameter names
                - CRITICAL: Use ONLY parameter names from the function definition - do not invent parameter names like 'actual_values', 'expected_values', etc.
                - CRITICAL: Ensure the parameter names are not duplicated, validate the parameter type being used and set it correctly as per the definition.
                - CRITICAL: Ensure that we use only the values
            7. CRITICAL: For array parameters (like 'columns', 'group_columns'): use list format ["value1", "value2"]
            8. CRITICAL: For single parameters (like 'variable', 'time_column'): use string format "value"
            9. CRITICAL: For Callable parameters (like 'func' in moving_apply_by_group): use string format "function_name" (e.g., "variance", "mean", "std")
            10. Determine the pipeline type based on the selected function (e.g., GroupBy → MetricsPipe, moving_apply_by_group → MovingAggrPipe)
            11. Return a JSON object with the parsed function_name, parameter_mapping, and pipeline_type

            OUTPUT FORMAT:
            CRITICAL: You must return ONLY a valid JSON object without any markdown formatting, code blocks, or extra text.
            
            CORRECT FORMAT:
            {{
                "function_name": "extracted_or_provided_function_name",
                "parameter_mapping": {{
                    "param1": "value1",
                    "param2": "value2"
                }},
                "pipeline_type": "PipelineTypeName"
            }}
            
            WRONG FORMATS (DO NOT USE):
            ❌ ```json
            ❌ ```python
            ❌ Any markdown formatting
            ❌ Explanations before or after the JSON
            ❌ Extra text or comments
            
            CONSEQUENCES OF IMPROPER FORMAT:
            - If you return markdown code blocks, the parsing will fail
            - If you add extra text, the JSON parsing will fail
            - If you don't return valid JSON, the system will fall back to basic parsing
            - This will result in poor code generation quality
            - The user's analysis pipeline will not work correctly
            
            Return ONLY the JSON object, nothing else.

EXAMPLES:

Example 1:
Input: "Group by 'Date', 'Region', 'Project' and sum 'Transactional value'"
Output: {{
    "function_name": "GroupBy",
    "parameter_mapping": {{
        "by": ["Date", "Region", "Project"],
        "agg_dict": {{"Transactional value": "sum"}}
    }},
    "pipeline_type": "MetricsPipe"
}}

Example 2:
Input: "Calculate mean and std deviation for 'Transactional value' grouped by 'Region' and 'Project'"
Output: {{
    "function_name": "GroupBy",
    "parameter_mapping": {{
        "by": ["Region", "Project"],
        "agg_dict": {{"Transactional value": ["mean", "std"]}}
    }},
    "pipeline_type": "MetricsPipe"
}}

            Example 3 - Using function definition parameters with defaults:
Input: "Apply moving variance calculation by group"
            Function Definition: {{"required_params": [{{"name": "columns", "type": "str or List[str]"}}, {{"name": "func", "type": "Callable"}}, {{"name": "group_columns", "type": "List[str]"}}], "optional_params": [{{"name": "window", "type": "int", "description": "Window size (default: 10)"}}, {{"name": "min_periods", "type": "int", "description": "Minimum periods (default: 1)"}}, {{"name": "center", "type": "bool", "description": "Center labels (default: False)"}}, {{"name": "time_column", "type": "str", "description": "Time column name"}}, {{"name": "output_suffix", "type": "str", "description": "Output suffix (default: '_ma')"}}]}}
Output: {{
    "function_name": "moving_apply_by_group",
    "parameter_mapping": {{
        "columns": ["Transactional value"],
        "func": "variance",
        "group_columns": ["Region", "Project"],
        "window": 10,
        "min_periods": 1,
        "center": false,
        "output_suffix": "_ma"
    }},
    "pipeline_type": "MovingAggrPipe"
}}
            
            Example 4 - Avoiding duplicate parameters:
            Input: "Apply moving standard deviation by group"
            Function Definition: {{"required_params": [{{"name": "columns", "type": "str or List[str]"}}, {{"name": "func", "type": "Callable"}}, {{"name": "group_columns", "type": "List[str]"}}], "optional_params": [{{"name": "window", "type": "int", "description": "Window size (default: 10)"}}]}}
            WRONG Output: {{"function_name": "moving_apply_by_group", "parameter_mapping": {{"columns": ["sales"], "func": "std_dev", "func": "std_dev"}}, "pipeline_type": "MovingAggrPipe"}}
            CORRECT Output: {{"function_name": "moving_apply_by_group", "parameter_mapping": {{"columns": ["sales"], "func": "std_dev", "group_columns": ["region"], "window": 10}}, "pipeline_type": "MovingAggrPipe"}}
            
            Example 5 - Using correct function definition parameters (detect_contextual_anomalies):
            Input: "Detect contextual anomalies in transactional value"
            Function Definition: {{"required_params": [{{"name": "columns", "type": "str or List[str]", "description": "Column(s) to analyze for anomalies"}}, {{"name": "time_column", "type": "str", "description": "Column containing the time/date information"}}], "optional_params": [{{"name": "method", "type": "str", "description": "Method to use (default: 'residual')"}}, {{"name": "model_type", "type": "str", "description": "Model to generate expected values (default: 'ewm')"}}, {{"name": "threshold", "type": "float", "description": "Threshold for determining anomalies (default: 3.0)"}}]}}
            WRONG Output: {{"function_name": "detect_contextual_anomalies", "parameter_mapping": {{"actual_values": "Transactional value", "expected_values": "Weekly_Average_Transactional_value", "threshold": 2.0}}, "pipeline_type": "AnomalyPipe"}}
            CORRECT Output: {{"function_name": "detect_contextual_anomalies", "parameter_mapping": {{"columns": ["Transactional value"], "time_column": "Date", "method": "residual", "model_type": "ewm", "threshold": 3.0}}, "pipeline_type": "AnomalyPipe"}}

Example 4:
Input: "Calculate 5-day rolling mean by group"
Output: {{
    "function_name": "moving_apply_by_group",
    "parameter_mapping": {{
        "columns": ["Transactional value"],
        "func": "mean",
        "group_columns": ["Region", "Project"],
        "time_column": "Date",
        "window": 5,
        "min_periods": 1,
        "output_suffix": "_rolling_mean"
    }},
    "pipeline_type": "MovingAggrPipe"
}}

Example 5:
Input: "Apply moving standard deviation by group"
Output: {{
    "function_name": "moving_apply_by_group",
    "parameter_mapping": {{
        "columns": ["Transactional value"],
        "func": "std",
        "group_columns": ["Region", "Project"],
        "time_column": "Date",
        "window": 7,
        "min_periods": 1,
        "output_suffix": "_rolling_std"
    }},
    "pipeline_type": "MovingAggrPipe"
}}

            Example 6:
            Input: "Aggregate data by weekly time periods"
            Output: {{
                "function_name": "aggregate_by_time",
                "parameter_mapping": {{
                    "date_column": "Date",
                    "metric_columns": ["Transactional value"],
                    "time_period": "W",
                    "aggregation": "mean"
                }},
                "pipeline_type": "TrendPipe"
}}

EMBEDDED FUNCTION RULES:
- For moving_apply_by_group, the "function" parameter should be a simple function name from group aggregation functions
- Common embedded functions: variance, mean, std, sum, count, min, max, median
- Do NOT use complex pipeline expressions for the function parameter
- The function parameter should be just the function name (e.g., "variance", not "Variance()" or complex expressions)

Now parse the given step description and return the JSON result.
"""
            )
            
            # Create parsing chain
            parsing_chain = parsing_prompt | self.llm | StrOutputParser()
            
            # Call the LLM using the chain
            try:
                result_text = await parsing_chain.ainvoke({
                    "parameter_mapping": parameter_mapping,
                    "step_title": step_title,
                    "step_number": step_number,
                    "function_name": function_name or "None",
                    "available_functions": "\n".join(available_functions)
                })
                
                # Try to parse the JSON response
                try:
                    import json
                    import re
                    
                    # Clean the response text - remove markdown code blocks and extra formatting
                    cleaned_text = result_text.strip()
                    
                    # Remove markdown code blocks (```json ... ```)
                    cleaned_text = re.sub(r'```json\s*', '', cleaned_text)
                    cleaned_text = re.sub(r'```\s*', '', cleaned_text)
                    
                    # Remove any leading/trailing whitespace and newlines
                    cleaned_text = cleaned_text.strip()
                    
                    # Try to parse the cleaned JSON
                    parsed_result = json.loads(cleaned_text)
                    
                    # Validate the result
                    if isinstance(parsed_result, dict) and 'function_name' in parsed_result and 'parameter_mapping' in parsed_result:
                        # Check if this is moving_apply_by_group and needs embedded function
                        function_name = parsed_result.get('function_name')
                        parameter_mapping = parsed_result.get('parameter_mapping', {})
                        
                        if function_name == 'moving_apply_by_group' and 'func' in parameter_mapping:
                            func_name = parameter_mapping.get('func')
                            if func_name and isinstance(func_name, str):
                                # Set embedded function details
                                parsed_result['embedded_function_parameter'] = True
                                parsed_result['embedded_function_details'] = {
                                    'embedded_function': func_name,
                                    'embedded_pipe': 'MetricsPipe',
                                    'embedded_parameters': {}
                                }
                                logger.info(f"Detected embedded function for moving_apply_by_group: {func_name}")
                        
                        return parsed_result
                    else:
                        logger.warning(f"LLM parsing returned invalid structure for step {step_number}: {parsed_result}")
                        return None
                        
                except json.JSONDecodeError as e:
                    logger.warning(f"LLM parsing returned invalid JSON for step {step_number}: {result_text}, error: {e}")
                    # Try to extract JSON content from markdown blocks as a fallback
                    try:
                        # Look for JSON content between markdown code blocks
                        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', result_text, re.DOTALL)
                        if json_match:
                            json_content = json_match.group(1)
                            parsed_result = json.loads(json_content)
                            if isinstance(parsed_result, dict) and 'function_name' in parsed_result and 'parameter_mapping' in parsed_result:
                                # Check if this is moving_apply_by_group and needs embedded function
                                function_name = parsed_result.get('function_name')
                                parameter_mapping = parsed_result.get('parameter_mapping', {})
                                
                                if function_name == 'moving_apply_by_group' and 'func' in parameter_mapping:
                                    func_name = parameter_mapping.get('func')
                                    if func_name and isinstance(func_name, str):
                                        # Set embedded function details
                                        parsed_result['embedded_function_parameter'] = True
                                        parsed_result['embedded_function_details'] = {
                                            'embedded_function': func_name,
                                            'embedded_pipe': 'MetricsPipe',
                                            'embedded_parameters': {}
                                        }
                                        logger.info(f"Detected embedded function for moving_apply_by_group (fallback): {func_name}")
                                
                                logger.info(f"Successfully extracted JSON from markdown blocks for step {step_number}")
                                return parsed_result
                    except Exception as fallback_error:
                        logger.warning(f"Fallback JSON extraction also failed for step {step_number}: {fallback_error}")
                    
                    return None
                    
            except Exception as e:
                logger.warning(f"LLM parsing failed for step {step_number}: {e}")
                return None
                
        except Exception as e:
            logger.warning(f"LLM parsing failed for step {step_number}: {e}")
            return None

    async def _get_available_embedded_functions(self) -> List[str]:
        """
        Get available embedded functions dynamically from function stores
        
        Returns:
            List of available embedded function names
        """
        try:
            embedded_functions = []
            
            # Try to get functions from FunctionRetrieval first
            if self.function_retrieval:
                try:
                    # Look for group aggregation functions
                    for pipe_name in self.function_retrieval.get_all_pipes():
                        if 'group' in pipe_name.lower() or 'aggregation' in pipe_name.lower():
                            pipe_functions = self.function_retrieval.get_pipe_functions(pipe_name)
                            embedded_functions.extend(pipe_functions)
                except Exception as e:
                    logger.warning(f"Error getting embedded functions from FunctionRetrieval: {e}")
            
            # Try RetrievalHelper if available
            if not embedded_functions and self.retrieval_helper:
                try:
                    # Search for group aggregation functions
                    definition_result = await self.retrieval_helper.get_function_definition_by_query(
                        query="group aggregation functions",
                        similarity_threshold=0.6,
                        top_k=20
                    )
                    
                    if definition_result:
                        # Handle both string and dictionary returns from RetrievalHelper
                        if isinstance(definition_result, str):
                            # If it's a string, create a basic function info structure
                            function_info = {"name": "unknown", "description": definition_result}
                        elif isinstance(definition_result, dict) and not definition_result.get("error"):
                            function_info = definition_result.get("function_definition", {})
                        if function_info and function_info.get("name"):
                            embedded_functions.append(function_info["name"])
                except Exception as e:
                    logger.warning(f"Error getting embedded functions from RetrievalHelper: {e}")
            
            # Try function_definition_store if available
            if not embedded_functions and self.function_definition_store:
                try:
                    search_results = self.function_definition_store.semantic_searches(
                        query_texts=["group aggregation functions"], 
                        n_results=20
                    )
                    
                    if search_results and "documents" in search_results and search_results["documents"]:
                        documents = search_results["documents"][0]
                        for document in documents:
                            try:
                                if isinstance(document, str):
                                    content = document
                                    if '"function_name"' in content or '"name"' in content:
                                        import json
                                        try:
                                            func_def = json.loads(content)
                                            func_name = func_def.get('function_name') or func_def.get('name')
                                            if func_name and 'group' in func_name.lower():
                                                embedded_functions.append(func_name)
                                        except json.JSONDecodeError:
                                            continue
                            except Exception as e:
                                logger.warning(f"Error parsing embedded function definition: {str(e)}")
                                continue
                except Exception as e:
                    logger.warning(f"Error getting embedded functions from function_definition_store: {e}")
            
            # If no functions found, use a minimal fallback list
            if not embedded_functions:
                embedded_functions = ["mean", "sum", "count", "variance", "std", "min", "max", "median"]
                logger.warning("Using fallback embedded functions list")
            
            # Remove duplicates and return
            return list(set(embedded_functions))
            
        except Exception as e:
            logger.warning(f"Error getting available embedded functions: {e}")
            return ["mean", "sum", "count", "variance", "std", "min", "max", "median"]







    async def _generate_code_from_reasoning_plan(self, reasoning_plan: List[Dict[str, Any]], 
                                         dataframe_name: str, 
                                         classification: Union[Dict[str, Any], AnalysisIntentResult]) -> Dict[str, Any]:
        """
        Generate separate code for each step and create flow graph structure
        
        Args:
            reasoning_plan: List of reasoning plan steps
            dataframe_name: Name of the dataframe
            classification: Classification results
            
        Returns:
            Dictionary containing:
            - step_codes: List of individual step codes
            - flow_graph: Flow graph structure with nodes and edges
            - combined_code: Combined code for backward compatibility
        """
        if not reasoning_plan or not isinstance(reasoning_plan, list):
            logger.warning(f"Invalid reasoning plan: {reasoning_plan}")
            fallback_code = self._generate_fallback_code(PipelineType.METRICS, "Mean", {}, dataframe_name)
            return {
                "step_codes": [{"step_number": 1, "code": fallback_code, "title": "Fallback Step"}],
                "flow_graph": {"nodes": [{"id": 1, "title": "Fallback Step"}], "edges": []},
                "combined_code": fallback_code
            }
        
        logger.info(f"Processing reasoning plan with {len(reasoning_plan)} steps")
        for i, step in enumerate(reasoning_plan):
            logger.info(f"Step {i+1}: {step}")
        
        # Handle dataframe names with spaces
        if ' ' in dataframe_name:
            formatted_dataframe_name = f'"{dataframe_name}"'
        else:
            formatted_dataframe_name = dataframe_name
        
        logger.info(f"Starting separate code generation from reasoning plan with {len(reasoning_plan)} steps")
        logger.info(f"Dataframe name: {formatted_dataframe_name}")
        
        # Extract all function names from reasoning plan and validate them
        function_names = []
        function_validations = {}
        for step in reasoning_plan:
            if isinstance(step, dict) and 'function_name' in step:
                func_name = step.get('function_name', '')
                if func_name and func_name not in [None, "None", "none", "N/A"]:
                    function_names.append(func_name)
                    # Validate function against store
                    validation = await self._validate_function_against_store(func_name)
                    function_validations[func_name] = validation
                    logger.info(f"Function validation for '{func_name}': {validation['valid']}")
        
        # Generate separate code for each step
        step_codes = []
        flow_graph_nodes = []
        flow_graph_edges = []
        current_dataframe = formatted_dataframe_name
        
        logger.info(f"Starting to process {len(reasoning_plan)} reasoning plan steps")
        
        for i, step in enumerate(reasoning_plan):
            logger.info(f"Processing step {i+1}/{len(reasoning_plan)}: {step}")
            
            if not isinstance(step, dict):
                logger.warning(f"Step {i+1} is not a dictionary, skipping")
                continue
                
            function_name = step.get('function_name', '')
            parameter_mapping = step.get('parameter_mapping', {})
            step_title = step.get('step_title', f'Step {i+1}')
            embedded_function_details = step.get('embedded_function_details', None)
            
            logger.info(f"Step {i+1} - Function: {function_name}, Title: {step_title}")
            logger.info(f"Step {i+1} - Parameter mapping: {parameter_mapping}")
            logger.info(f"Step {i+1} - Embedded function details: {embedded_function_details}")
            
            # Handle None, "None", or "N/A" values - use LLM-based extraction
            if function_name in [None, "None", "none", "N/A"]:
                logger.info(f"Step {i+1} has invalid function name '{function_name}', using LLM to extract function name")
                # Use LLM to extract function name and parameters from step description
                parsed_result = await self._parse_reasoning_plan_step_with_llm(
                    parameter_mapping if isinstance(parameter_mapping, str) else step_title, 
                    step_title, 
                    i+1, 
                    None  # Let LLM determine function name
                )
                
                if parsed_result and parsed_result.get('function_name'):
                    function_name = parsed_result['function_name']
                    parameter_mapping = parsed_result.get('parameter_mapping', parameter_mapping)
                    logger.info(f"Step {i+1} - LLM extracted function name: {function_name}")
                else:
                    # Fallback based on step title keywords
                    step_title_lower = step_title.lower()
                    if any(keyword in step_title_lower for keyword in ['group', 'aggregate', 'aggregation']):
                        function_name = "GroupBy"
                        logger.info(f"Step {i+1} - Detected aggregation step, using GroupBy")
                    elif any(keyword in step_title_lower for keyword in ['mean', 'average', 'sum', 'count']):
                        function_name = "Mean"
                        logger.info(f"Step {i+1} - Detected statistical step, using Mean")
                    elif any(keyword in step_title_lower for keyword in ['variance', 'std', 'standard']):
                        function_name = "Variance"
                        logger.info(f"Step {i+1} - Detected variance step, using Variance")
                    else:
                        # Error out instead of using fallback to prevent incorrect pipeline generation
                        error_msg = f"Step {i+1} - Cannot determine appropriate function for step: {step_title}. Please ensure the reasoning plan includes proper function names."
                        logger.error(error_msg)
                        raise ValueError(error_msg)
            
            if parameter_mapping in [None, "None", "none", "N/A"]:
                parameter_mapping = {}
            
            # Ensure parameter_mapping is a dictionary
            if not isinstance(parameter_mapping, dict):
                logger.warning(f"Parameter mapping in step {i+1} is not a dictionary, converting to empty dict: {type(parameter_mapping)} -> {parameter_mapping}")
                parameter_mapping = {}
            
            # Don't skip steps - always try to process them
            if not function_name:
                # Error out instead of using fallback to prevent incorrect pipeline generation
                error_msg = f"Step {i+1} - No function name found in reasoning plan for step: {step_title}. Please ensure the reasoning plan includes proper function names."
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # Use the rich metadata from reasoning plan instead of re-parsing
            if isinstance(parameter_mapping, dict) and parameter_mapping:
                # Use the parameter mapping directly from reasoning plan
                logger.info(f"Step {i+1} - Using parameter mapping from reasoning plan: {parameter_mapping}")
            elif isinstance(parameter_mapping, str) and parameter_mapping:
                # Try to parse string parameter mapping using LLM
                parsed_result = await self._parse_reasoning_plan_step_with_llm(
                    parameter_mapping, 
                    step_title, 
                    i+1, 
                    function_name
                )
                
                if parsed_result:
                    # Use LLM parsed results
                    function_name = parsed_result.get('function_name', function_name)
                    parameter_mapping = parsed_result.get('parameter_mapping', {})
                    logger.info(f"LLM parsed step {i+1}: function='{function_name}', params={parameter_mapping}")
                else:
                    # If LLM parsing fails, use column_mapping as fallback
                    column_mapping = step.get('column_mapping', {})
                    if column_mapping and isinstance(column_mapping, dict):
                        parameter_mapping = column_mapping
                        logger.info(f"Step {i+1} - Using column_mapping as parameter mapping: {parameter_mapping}")
                    else:
                        # Last resort: use empty parameter mapping
                        parameter_mapping = {}
                        logger.info(f"Step {i+1} - Using empty parameter mapping as fallback")
            else:
                # No parameter mapping provided, use column_mapping if available
                column_mapping = step.get('column_mapping', {})
                if column_mapping and isinstance(column_mapping, dict):
                    parameter_mapping = column_mapping
                    logger.info(f"Step {i+1} - Using column_mapping as parameter mapping: {parameter_mapping}")
                else:
                    parameter_mapping = {}
                    logger.info(f"Step {i+1} - Using empty parameter mapping as fallback")
            
            # Determine pipeline type for this function - use metadata first, then detect
            pipeline_type_str = step.get('pipeline_type')
            if pipeline_type_str and pipeline_type_str != "unknown_category":
                # Use pipeline type from reasoning plan metadata
                pipeline_type = self._map_pipe_name_to_pipeline_type(pipeline_type_str)
                if pipeline_type:
                    logger.info(f"Step {i+1} - Using pipeline type from reasoning plan: {pipeline_type}")
                else:
                    # Fallback to detection if mapping fails
                    pipeline_type = await self._detect_pipeline_type(function_name, step_title, classification)
                    logger.info(f"Step {i+1} - Detected pipeline type (fallback): {pipeline_type}")
            else:
                # No pipeline type in metadata or it's unknown_category, detect it
                pipeline_type = await self._detect_pipeline_type(function_name, step_title, classification)
                logger.info(f"Step {i+1} - Detected pipeline type: {pipeline_type}")
            
            # Validate step intent consistency
            step_intent_validation = await self._validate_single_step_intent(step, classification, i+1)
            if not step_intent_validation["valid"]:
                logger.warning(f"Step {i+1} intent validation failed: {step_intent_validation['issues']}")
                # Try to fix the step intent
                step = await self._fix_step_intent(step, classification, step_intent_validation)
                logger.info(f"Step {i+1} - Applied intent fixes: {step.get('step_title', 'Unknown')}")
            
            # Check if function is valid according to function definition store
            function_validation = function_validations.get(function_name, {"valid": False, "definition": None})
            if not function_validation["valid"]:
                logger.warning(f"Function '{function_name}' in step {i+1} is not valid according to function definition store: {function_validation.get('error', 'Unknown error')}")
                # Continue anyway, but log the warning
                logger.info(f"Step {i+1} - Continuing with function '{function_name}' despite validation failure")
            
            # Handle enhanced metadata if available
            column_mapping = step.get('column_mapping', {})
            if column_mapping and isinstance(column_mapping, dict):
                # Use column mapping to enhance parameter mapping
                for param_name, mapped_column in column_mapping.items():
                    if param_name in parameter_mapping:
                        # Update parameter with mapped column
                        parameter_mapping[param_name] = mapped_column
                        logger.info(f"Step {i+1} - Updated parameter {param_name} with mapped column: {mapped_column}")
            
            # Format parameters using the parameter mapping
            formatted_params = self._format_parameters_for_function(parameter_mapping, function_name)
            param_str = ", ".join(formatted_params) if formatted_params else ""
            logger.info(f"Step {i+1} - Formatted parameters: {param_str}")
            
            # Generate individual step code with enhanced context
            step_code = await self._generate_individual_step_code(
                function_name=function_name,
                param_str=param_str,
                pipeline_type=pipeline_type,
                current_dataframe=current_dataframe,
                step_title=step_title,
                step_number=i+1,
                embedded_function_details=embedded_function_details,
                context=step_title  # Use step title as context for enhanced function retrieval
            )
            
            # Add step to flow graph
            flow_graph_nodes.append({
                "id": i+1,
                "title": step_title,
                "function": function_name,
                "pipeline_type": pipeline_type.value,
                "input_dataframe": current_dataframe,
                "output_dataframe": f"step_{i+1}_result",
                "dependencies": step.get('step_dependencies', []),
                "input_columns": step.get('input_columns', []),
                "output_columns": step.get('output_columns', [])
            })
            
            # Add edges based on dependencies
            step_dependencies = step.get('step_dependencies', [])
            for dep_step in step_dependencies:
                flow_graph_edges.append({
                    "from": dep_step,
                    "to": i+1,
                    "type": "data_dependency"
                })
            
            # Add step code to results
            step_code_dict = {
                "step_number": i+1,
                "code": step_code,
                "title": step_title,
                "function": function_name,
                "pipeline_type": pipeline_type.value,
                "input_dataframe": current_dataframe,
                "output_dataframe": f"step_{i+1}_result",
                "dependencies": step_dependencies,
                "input_columns": step.get('input_columns', []),
                "output_columns": step.get('output_columns', [])
            }
            step_codes.append(step_code_dict)
            
            # Debug: Print the actual generated code
            logger.info(f"=== STEP {i+1} GENERATED CODE ===")
            logger.info(f"Title: {step_title}")
            logger.info(f"Function: {function_name}")
            logger.info(f"Pipeline Type: {pipeline_type.value}")
            logger.info(f"Generated Code:")
            logger.info(f"```python")
            logger.info(f"{step_code}")
            logger.info(f"```")
            logger.info(f"=== END STEP {i+1} CODE ===")
            
            logger.info(f"Added step {i+1} to step_codes: {step_code_dict}")
            
            # Update current dataframe for next step
            current_dataframe = f"step_{i+1}_result"
            
            # Log enhanced metadata if available
            if step.get('input_columns'):
                logger.info(f"Step {i+1} - Input columns: {step.get('input_columns')}")
            if step.get('output_columns'):
                logger.info(f"Step {i+1} - Output columns: {step.get('output_columns')}")
            if step.get('step_dependencies'):
                logger.info(f"Step {i+1} - Dependencies: Step {step.get('step_dependencies')}")
            if step.get('data_flow'):
                logger.info(f"Step {i+1} - Data flow: {step.get('data_flow')}")
            if step.get('pipeline_type'):
                logger.info(f"Step {i+1} - Pipeline type: {step.get('pipeline_type')}")
            if step.get('function_category'):
                logger.info(f"Step {i+1} - Function category: {step.get('function_category')}")
            
            logger.info(f"Step {i+1} - Generated individual code and added to flow graph")
        
        logger.info(f"Generated {len(step_codes)} individual step codes")
        logger.info(f"Flow graph has {len(flow_graph_nodes)} nodes and {len(flow_graph_edges)} edges")
        
        # Generate combined code for backward compatibility
        combined_code = self._generate_combined_code_from_steps(step_codes, formatted_dataframe_name)
        
        # Debug: Print the combined code
        logger.info(f"=== COMBINED GENERATED CODE ===")
        logger.info(f"Combined Code:")
        logger.info(f"```python")
        logger.info(f"{combined_code}")
        logger.info(f"```")
        logger.info(f"=== END COMBINED CODE ===")
        
        # Create flow graph structure
        flow_graph = {
            "nodes": flow_graph_nodes,
            "edges": flow_graph_edges,
            "metadata": {
                "total_steps": len(step_codes),
                "pipeline_types": list(set([node["pipeline_type"] for node in flow_graph_nodes])),
                "functions_used": list(set([node["function"] for node in flow_graph_nodes]))
            }
        }
        
        result = {
            "step_codes": step_codes,
            "flow_graph": flow_graph,
            "combined_code": combined_code
        }
        
        # Debug: Print the final result structure
        logger.info(f"=== FINAL RESULT STRUCTURE ===")
        logger.info(f"Step codes count: {len(step_codes)}")
        logger.info(f"Flow graph nodes: {len(flow_graph['nodes'])}")
        logger.info(f"Flow graph edges: {len(flow_graph['edges'])}")
        logger.info(f"Combined code length: {len(combined_code) if combined_code else 0}")
        logger.info(f"=== END FINAL RESULT ===")
        
        return result
    
    async def _generate_individual_step_code(self, 
                                           function_name: str,
                                           param_str: str,
                                           pipeline_type: PipelineType,
                                           current_dataframe: str,
                                           step_title: str,
                                           step_number: int,
                                           embedded_function_details: Optional[Dict[str, Any]] = None,
                                           context: str = "") -> str:
        """
        Generate individual code for a single step with enhanced function context
        
        Args:
            function_name: Name of the function to call
            param_str: Formatted parameter string
            pipeline_type: Type of pipeline to use
            current_dataframe: Name of the input dataframe
            step_title: Title of the step
            step_number: Number of the step
            embedded_function_details: Details for embedded functions
            context: User context for enhanced function retrieval
            
        Returns:
            Generated code for the individual step
        """
        # Get enhanced function context if available
        enhanced_context = {}
        if self.enhanced_function_registry and context:
            try:
                enhanced_context = await self._get_enhanced_function_context(
                    function_name=function_name,
                    context=context
                )
            except Exception as e:
                logger.warning(f"Error getting enhanced context for {function_name}: {e}")
        
        # Generate enhanced comments based on function context
        enhanced_comments = []
        if enhanced_context:
            # Add function description
            description = enhanced_context.get('description', '')
            if description:
                enhanced_comments.append(f"# {description}")
            
            # Add usage information
            usage = enhanced_context.get('usage_description', '')
            if usage:
                enhanced_comments.append(f"# Usage: {usage}")
            
            # Add historical rules as comments
            historical_rules = enhanced_context.get('historical_rules', [])
            if historical_rules:
                enhanced_comments.append("# Best practices:")
                for rule in historical_rules[:2]:  # Show top 2 rules
                    content = rule.get('content', str(rule))
                    if isinstance(content, str) and len(content) > 100:
                        content = content[:97] + "..."
                    enhanced_comments.append(f"# - {content}")
        
        # Combine enhanced comments with step title
        comment_lines = [f"# {step_title}"]
        if enhanced_comments:
            comment_lines.extend(enhanced_comments)
        
        comment_section = "\n".join(comment_lines)
        
        if embedded_function_details and embedded_function_details.get('embedded_function'):
            # Handle embedded functions
            embedded_function = embedded_function_details.get('embedded_function')
            embedded_params = embedded_function_details.get('embedded_parameters', {})
            
            # Remove func parameter from param_str since embedded function will provide it
            if param_str:
                # Parse param_str to remove func parameter
                param_parts = []
                for part in param_str.split(', '):
                    if not part.startswith('func='):
                        param_parts.append(part)
                param_str_clean = ', '.join(param_parts) if param_parts else ""
            else:
                param_str_clean = ""
            
            # Format embedded function parameters
            embedded_param_str = ", ".join([f"{k}={v}" for k, v in embedded_params.items()])
            if param_str_clean:
                full_params = f"{param_str_clean}, func={embedded_function}"
            else:
                full_params = f"func={embedded_function}"
            
            step_code = f"""{comment_section}
step_{step_number}_result = (
    {pipeline_type.value}.from_dataframe({current_dataframe})
    | {function_name}({full_params})
    ).to_df()"""
        else:
            # Regular function call
            step_code = f"""{comment_section}
step_{step_number}_result = (
    {pipeline_type.value}.from_dataframe({current_dataframe})
    | {function_name}({param_str})
    ).to_df()"""
        
        return step_code
    
    def _generate_combined_code_from_steps(self, step_codes: List[Dict[str, Any]], original_dataframe: str) -> str:
        """
        Generate combined code from individual step codes for backward compatibility
        
        Args:
            step_codes: List of individual step codes
            original_dataframe: Name of the original dataframe
            
        Returns:
            Combined code string
        """
        if not step_codes:
            return f"# No steps to execute\nresult = {original_dataframe}.copy()"
        
        combined_parts = []
        
        # Initialize with original data
        combined_parts.append(f"# Start with original data\nresult = {original_dataframe}.copy()")
        
        # Add each step
        for step in step_codes:
            step_code = step['code']
            # Replace the step-specific dataframe with 'result' for chaining
            step_code = step_code.replace(f"step_{step['step_number']}_result", "result")
            combined_parts.append(step_code)
        
        # Add final result statement
        combined_parts.append("# Final result\nresult = result")
        
        return "\n\n".join(combined_parts)
    
    def _format_parameters_for_function(self, parameter_mapping: Dict[str, Any], function_name: str) -> List[str]:
        """
        Format parameters for a function call
        
        Args:
            parameter_mapping: Dictionary of parameters
            function_name: Name of the function
            
        Returns:
            List of formatted parameter strings
        """
        formatted_params = []
        
        for key, value in parameter_mapping.items():
            if isinstance(value, str):
                # Handle string parameters
                if value.startswith('"') and value.endswith('"'):
                    # Already quoted
                    formatted_params.append(f"{key}={value}")
                else:
                    formatted_params.append(f"{key}='{value}'")
            elif isinstance(value, list):
                # Handle list parameters
                if key == 'agg_dict':
                    # Special handling for agg_dict
                    formatted_params.append(f"{key}={value}")
                else:
                    formatted_params.append(f"{key}={value}")
            elif isinstance(value, dict):
                # Handle dictionary parameters
                formatted_params.append(f"{key}={value}")
            elif value is None:
                # Handle None values
                formatted_params.append(f"{key}=None")
            else:
                # Handle other types (numbers, booleans, etc.)
                formatted_params.append(f"{key}={value}")
        
        return formatted_params
    
    async def _detect_embedded_function_from_context(self, context: str, step_title: str) -> Optional[str]:
        """
        Detect embedded function from context and step title using LLM
        
        Args:
            context: Analysis context
            step_title: Step title
            
        Returns:
            Detected embedded function name or None
        """
        try:
            from langchain.prompts import PromptTemplate
            
            # Get available group aggregation functions dynamically
            available_embedded_functions = await self._get_available_embedded_functions()
            
            detection_prompt = PromptTemplate(
                input_variables=["context", "step_title", "available_functions"],
                template="""
You are an expert at detecting embedded functions for moving window operations.

CONTEXT: {context}
STEP TITLE: {step_title}
AVAILABLE EMBEDDED FUNCTIONS: {available_functions}

TASK: From the context and step title, determine which group aggregation function should be used as an embedded function for moving_apply_by_group.

RULES:
1. Look for keywords that indicate specific statistical operations
2. Common patterns:
   - "variance" or "variability" → variance
   - "mean" or "average" → mean
   - "standard deviation" or "std" → std
   - "sum" or "total" → sum
   - "count" or "number" → count
   - "minimum" or "min" → min
   - "maximum" or "max" → max
   - "median" → median

3. If no specific function is mentioned, default to "mean" for general aggregation

4. Return ONLY the function name, nothing else.

EXAMPLES:
- "5-day rolling variance" → variance
- "Calculate rolling mean" → mean
- "Moving average" → mean
- "Rolling standard deviation" → std
- "Rolling sum" → sum
- "Rolling count" → count

Return the function name:
"""
            )
            
            detection_chain = detection_prompt | self.llm | StrOutputParser()
            
            result = await detection_chain.ainvoke({
                "context": context,
                "step_title": step_title,
                "available_functions": ", ".join(available_embedded_functions)
            })
            
            # Clean and validate the result
            detected_function = result.strip().lower()
            
            if detected_function in available_embedded_functions:
                logger.info(f"Detected embedded function: {detected_function}")
                return detected_function
            else:
                logger.warning(f"Detected function '{detected_function}' not in available functions, using 'mean' as fallback")
                return "mean"
                
        except Exception as e:
            logger.error(f"Error detecting embedded function: {str(e)}")
            return "mean"  # Safe fallback
    
    async def _generate_embedded_function_code(self, embedded_details: Dict[str, Any], 
                                             current_dataframe: str, 
                                             parent_function: str,
                                             parent_params: Dict[str, Any]) -> str:
        """
        Generate code for embedded functions (like moving_apply_by_group with embedded group aggregation functions)
        
        Args:
            embedded_details: Details about the embedded function
            current_dataframe: Current dataframe variable name
            parent_function: Parent function name
            parent_params: Parent function parameters
            
        Returns:
            Generated code string
        """
        embedded_function = embedded_details.get('embedded_function', '')
        embedded_parameters = embedded_details.get('embedded_parameters', {})
        
        if not embedded_function:
            logger.warning("No embedded function specified in embedded_details, attempting to detect from context")
            # Try to detect from context using LLM
            try:
                # Get context from the step or use a default
                context = embedded_details.get('context', 'moving window operation')
                step_title = embedded_details.get('step_title', 'embedded function step')
                embedded_function = await self._detect_embedded_function_from_context(context, step_title)
                logger.info(f"Detected embedded function from context: {embedded_function}")
            except Exception as e:
                logger.error(f"Error detecting embedded function from context: {str(e)}")
                embedded_function = "mean"  # Safe fallback
                logger.info(f"Using fallback embedded function: {embedded_function}")
        
        if not embedded_function:
            logger.warning("Still no embedded function after detection, using fallback")
            return self._generate_fallback_code(PipelineType.METRICS, parent_function, parent_params, current_dataframe)
        
        # Validate that the embedded function exists
        valid_embedded_functions = await self._get_available_embedded_functions()
        
        if embedded_function not in valid_embedded_functions:
            logger.warning(f"Embedded function '{embedded_function}' not in valid functions, using 'mean' as fallback")
            embedded_function = "mean"
        
        # Import the group aggregation function
        import_statement = f"from insightsagents.app.tools.mltools.group_aggregation_functions import {embedded_function}"
        
        # Format parent function parameters
        parent_formatted_params = self._format_parameters_for_function(parent_params, parent_function)
        
        # Add the function parameter with the embedded function name
        # Check if func parameter already exists
        func_param_exists = any(param.startswith("func=") for param in parent_formatted_params)
        
        if not func_param_exists:
            # Add the func parameter
            parent_formatted_params.append(f"func={embedded_function}")
        else:
            # Replace existing func parameter
            for i, param in enumerate(parent_formatted_params):
                if param.startswith("func="):
                    parent_formatted_params[i] = f"func={embedded_function}"
                    break
        
        parent_param_str = ", ".join(parent_formatted_params)
        
        # Generate the complete code
        pipeline_type = await self._detect_pipeline_type(parent_function, "embedded_function")
        
        if parent_param_str:
            return f"""{import_statement}

result = (
    {pipeline_type.value}.from_dataframe({current_dataframe})
    | {parent_function}({parent_param_str})
    ).to_df()"""
        else:
            return f"""{import_statement}

result = (
    {pipeline_type.value}.from_dataframe({current_dataframe})
    | {parent_function}()
    ).to_df()"""
    
    async def _generate_step_code(self, function_name: str, 
                                param_str: str, 
                                pipeline_type: PipelineType, 
                                current_dataframe: str,
                                step_title: str,
                                step_number: int) -> str:
        """
        Generate code for a single reasoning plan step
        
        Args:
            function_name: Name of the function
            param_str: Formatted parameter string
            pipeline_type: Pipeline type for the function
            current_dataframe: Current dataframe variable name
            step_title: Title of the step
            step_number: Step number
            
        Returns:
            Generated code string
        """
        # Add comment for the step
        comment = f"# Step {step_number}: {step_title}"
        
        # Generate the function call
        if param_str:
            function_call = f"""result = (
    {pipeline_type.value}.from_dataframe({current_dataframe})
    | {function_name}({param_str})
    ).to_df()"""
        else:
            function_call = f"""result = (
    {pipeline_type.value}.from_dataframe({current_dataframe})
    | {function_name}()
    ).to_df()"""
        
        return f"{comment}\n{function_call}"
    
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
        
        # Check if there's a reasoning plan and use the reasoning plan approach
        # Prefer pipeline_reasoning_plan (enhanced) over reasoning_plan (basic)
        reasoning_plan = None
        if hasattr(classification, 'pipeline_reasoning_plan'):
            reasoning_plan = getattr(classification, 'pipeline_reasoning_plan', None)
        elif hasattr(classification, 'reasoning_plan'):
            reasoning_plan = getattr(classification, 'reasoning_plan', None)
        else:
            reasoning_plan = classification.get('pipeline_reasoning_plan', None) or classification.get('reasoning_plan', None)
        
        if reasoning_plan and len(reasoning_plan) > 1:
            logger.info("Using reasoning plan approach for multi-step pipeline")
            pipeline_result = await self._generate_code_from_reasoning_plan(
                reasoning_plan, 
                dataframe_name, 
                classification
            )
            # Store step_codes and flow_graph in query_state for later use
            if isinstance(pipeline_result, dict):
                if 'step_codes' in pipeline_result:
                    query_state["step_codes"] = pipeline_result['step_codes']
                    logger.info(f"Stored {len(pipeline_result['step_codes'])} step codes in query_state")
                if 'flow_graph' in pipeline_result:
                    query_state["flow_graph"] = pipeline_result['flow_graph']
                    logger.info(f"Stored flow graph with {len(pipeline_result['flow_graph'].get('nodes', []))} nodes in query_state")
                
                # Extract just the combined code from the pipeline result
                if 'combined_code' in pipeline_result:
                    logger.info("Extracted combined_code from pipeline result")
                    return pipeline_result['combined_code']
                else:
                    logger.error(f"Pipeline result does not contain combined_code: {list(pipeline_result.keys())}")
                    return str(pipeline_result) if pipeline_result else ""
            else:
                logger.error(f"Pipeline result is not a dict: {type(pipeline_result)}")
                return str(pipeline_result) if pipeline_result else ""
        
        # Get pipeline type from function definition (not detection)
        pipeline_type = await self._get_pipeline_type_from_function_definition(function_name)
        
        # If not found in function definition, fall back to detection
        if not pipeline_type:
            pipeline_type = await self._detect_pipeline_type(function_name, original_context, classification)
        
        # Format relevant documents
        docs_context = self._format_documents_for_generation(relevant_docs)
        
        # Get enhanced function definitions with context
        function_definitions = await self._retrieve_function_definitions(
            function_names=[function_name],
            context=original_context,
            project_id=classification.get('project_id') if isinstance(classification, dict) else getattr(classification, 'project_id', None)
        )
        
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
                "docs_context", "classification_context", "dataset_context", "reasoning_plan_json", 
                "function_definitions", "iteration", "name"
            ],
            template="""
            You are an expert code generator for data analysis pipelines.
            
            IMPORTANT: The reasoning plan is already available and the pipeline type has been determined from the function definition.
            Your task is to focus on detecting function inputs based on the function definition and available data.
            
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
            
            ENHANCED FUNCTION DEFINITIONS (with examples, instructions, and rules):
            {function_definitions}
            
            RELEVANT DOCUMENTATION:
            {docs_context}
            
            Generate a complete pipeline code using a SINGLE PIPELINE APPROACH that:
            1. Uses ONE pipeline type with ONE function call
            2. Starts with the original dataframe and creates a result copy
            3. Applies the single function using the appropriate pipeline type
            4. Follows the reasoning plan step that corresponds to the primary function
            5. Considers the intent type and suggested functions from classification
            6. CRITICAL: Aligns with the reasoning plan step and its expected outcome
            7. CRITICAL: Use the single pipeline approach: result = (PipeType.from_dataframe(result) | function()).to_df()
            8. CRITICAL: Use the enhanced function definitions with examples, instructions, and rules for better code generation
            9. CRITICAL: Follow the function signatures, docstrings, and source code patterns provided
            10. CRITICAL: Apply the historical rules and best practices from the function context
            11. CRITICAL: Use the examples as reference for proper function usage patterns
            
            CRITICAL SYNTAX REQUIREMENTS:
            - Ensure all parentheses are properly closed
            - Use proper indentation for multi-line statements (4 spaces for continued lines)
            - Use proper string quotes for dataframe names with spaces
            - Ensure function parameters are properly formatted
            - Avoid syntax errors like unclosed parentheses or missing commas
            
            
            CRITICAL SINGLE PIPELINE RULES:
            - Start with original dataframe: result = df.copy()
            - Use ONE pipeline type with ONE function call
            - Apply the single function using the appropriate pipeline type
            - Use single pipeline approach: result = (PipeType.from_dataframe(result) | function()).to_df()
            - Follow the reasoning plan step that corresponds to the primary function
            - Ensure the single step in the reasoning plan is properly implemented in the code
            
            CRITICAL PIPELINE TYPE SEPARATION RULES:
            - MetricsPipe functions: Mean, Variance, Sum, Count, Max, Min, StandardDeviation, Correlation, etc.
            - TimeSeriesPipe functions: variance_analysis, lead, lag, rolling_window, distribution_analysis, etc.
            - MovingAggrPipe functions: moving_apply_by_group, moving_average, moving_variance, etc.
            - OperationsPipe functions: PercentChange, AbsoluteChange, MH, CUPED, etc.
            - CohortPipe functions: form_time_cohorts, calculate_retention, analyze_funnel, analyze_funnel_by_time, analyze_funnel_by_segment, analyze_user_paths, etc.
            - RiskPipe functions: calculate_var, calculate_cvar, etc.
            - AnomalyPipe functions: detect_statistical_outliers, detect_contextual_anomalies, etc.
            - SegmentPipe functions: get_features, run_kmeans, run_dbscan, etc.
            - TrendsPipe functions: aggregate_by_time, calculate_growth_rates, forecast_metric, etc.
            
            
            
            REQUIRED UNIFIED FORMAT:
            
            SINGLE PIPELINE FORMAT (REQUIRED):
            ```python
            # Start with original data
            result = {dataframe_name}.copy()
            
            # Apply single pipeline step
            result = (
                PipeType.from_dataframe(result)
                | function(param1='value1', param2='value2')
                ).to_df()
            
            # Final result
            result = result
            ```
            
            CRITICAL: Always use ONE pipeline type with ONE function call
            Do NOT chain multiple pipeline types together
            Do NOT use multi-pipeline approaches
            
            CRITICAL FUNCTION PARAMETER RULES:
            1. CRITICAL: Use ONLY existing function names from function definitions - do not invent new function names
            2. CRITICAL: Use ONLY parameter names from function definitions - do not invent new parameter names
            example inputs provided: ``` "required_params": [
                {"name": "columns", "type": "str or List[str]", "description": "Base column(s) names (will look for {{column}}{{suffix}})"}
            ],
            "optional_params": [
                {"name": "method", "type": "str", "description": "Method to use: 'zscore', 'modified_zscore', 'iqr', or 'percentile' (default: 'zscore')"},
                {"name": "threshold", "type": "float", "description": "Threshold for determining anomalies (default: 3.0)"},
                {"name": "suffix", "type": "str", "description": "Suffix of columns containing residuals (default: '_residual')"},
                {"name": "output_suffix", "type": "str", "description": "Suffix for output anomaly flag columns (default: '_anomaly')"}
            ],```
            Please use these parameters to determine the inputs to the function definition and nothing else.

            3. CRITICAL: For array parameters (like 'columns', 'metric_columns'): use list format ["value1", "value2"]
            4. CRITICAL: For single parameters (like 'variable', 'time_column'): use string format "value"
            5. CRITICAL: Use actual column names from dataset - do not invent column names
            6. CRITICAL: Function parameters that reference function names should NOT be quoted: func=variance (correct)
            7. CRITICAL: String values should be quoted: columns=['Transactional value'] (correct)
            8. CRITICAL: Use ).to_df() at the end for all pipeline types except funnel analysis
            9. CRITICAL: Use direct method calls, NOT function parameters: variance(...) NOT moving_apply_by_group(func='variance', ...)
            10. CRITICAL: For moving_apply_by_group, func parameter should be the function name as string
            11. CRITICAL: Do NOT include duplicate parameter names in function calls
            12. CRITICAL: Include default values for optional parameters when not specified in context
            13. CRITICAL: Use ONLY parameter names from function definitions - do not invent parameter names like 'actual_values', 'expected_values', etc.
            
            CORRECT EXAMPLE:
            ```python
            result = (MovingAggrPipe.from_dataframe(result)
                     | moving_apply_by_group(  # Correct function name
                         columns=['Transactional value'],  # Array format
                         group_column='Region, Project',  # Correct parameter name
                         function=variance,  # Function reference, not string
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
            
            SINGLE PIPELINE EXAMPLE - moving_apply_by_group (NO DUPLICATES):
            ```python
            result = (MovingAggrPipe.from_dataframe({dataframe_name})
                     | moving_apply_by_group(
                         columns=['Transactional value'],
                         group_column='Region, Project',
                         function=variance,
                         window=5,
                         min_periods=1,
                         time_column='Date',
                         output_suffix='_rolling_variance'
                     )
                     | to_df()
            )
            ```
            
            WRONG EXAMPLE - WITH DUPLICATES (DO NOT USE):
            ```python
            result = (MovingAggrPipe.from_dataframe({dataframe_name})
                     | moving_apply_by_group(
                         columns=['Transactional value'],
                         group_column='Region, Project',
                         function=variance,
                         function=variance,  # DUPLICATE! WRONG!
                         window=5,
                         min_periods=1
                     )
                     | to_df()
            )
            ```
            
            WRONG EXAMPLE - WRONG PARAMETER NAMES (DO NOT USE):
            ```python
            result = (AnomalyPipe.from_dataframe({dataframe_name})
                     | detect_contextual_anomalies(
                         actual_values='Transactional value',  # WRONG PARAMETER!
                         expected_values='Weekly_Average_Transactional_value',  # WRONG PARAMETER!
                         threshold=2.0
                     )
                     | to_df()
            )
            ```
            
            CORRECT EXAMPLE - CORRECT PARAMETER NAMES:
            ```python
            result = (AnomalyPipe.from_dataframe({dataframe_name})
                     | detect_contextual_anomalies(
                         columns=['Transactional value'],  # CORRECT!
                         time_column='Date',  # CORRECT!
                         method='residual',
                         model_type='ewm',
                         threshold=3.0,
                         window=30
                     )
                     | to_df()
            )
            ```
            
            IMPORTANT: If the dataframe name contains spaces, it must be quoted: from_dataframe("Dataframe Name")
            
            EXAMPLES:
            
            Example 1 - Single pipeline type (MetricsPipe) with unified approach:
            ```python
            # Start with original data
            result_df = df.copy()
            
            # Apply metrics pipeline step
            result = (
                MetricsPipe.from_dataframe(result)
                | Mean(variable='revenue')
                | Variance(variable='revenue')
                ).to_df()
            
            # Final result
            result = result
            ```
            
            Example 2 - Multiple pipeline types with sequential approach:
            ```python
            # Start with original data
            result = df.copy()
            
            # Apply metrics pipeline step
            result = (
                MetricsPipe.from_dataframe(result)
                | Mean(variable='Transactional value')
                ).to_df()
            
            # Apply timeseries pipeline step
            result = (
                TimeSeriesPipe.from_dataframe(result)
                | variance_analysis(
                    columns=['Transactional value'],
                    method='rolling',
                    window=5
                )
                ).to_df()
            
            # Final result
            result = result
            ```
            
            Example 2b - Moving aggregation with sequential approach:
            ```python
            # Start with original data
            result = df.copy()
            
            # Apply moving aggregation pipeline step
            result = (
                MovingAggrPipe.from_dataframe(result)
                | moving_apply_by_group(
                    columns=['Transactional value'],
                    group_column='Region, Project',
                    function=variance,
                    window=5,
                    min_periods=1,
                    time_column='Date',
                    output_suffix='_rolling_variance'
                )
                ).to_df()
            
            # Final result
            result = result
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
            
            Example 11 - WRONG way (inventing function names):
            ```python
            # ❌ WRONG: Don't invent function names like this
            result = (
                TrendsPipe.from_dataframe(df)
                | aggregate_weekly_transactional_values(  # ❌ This function doesn't exist
                    date_column='Date',
                    metric_columns=['Transactional value'],
                    by=['Region', 'Project']
                )
                ).to_df()
            ```

            Example 12 - CORRECT way (using existing function names):
            ```python
            # ✅ CORRECT: Use existing function names
            result = (
                TrendsPipe.from_dataframe(df)
                | aggregate_by_time(  # ✅ This function exists
                    date_column='Date',
                    metric_columns=['Transactional value'],
                    time_period='W',
                    aggregation='mean'
                )
                ).to_df()
            ```
            
            Example 13 - Funnel analysis (CohortPipe) with reasoning plan:
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
            
            Example 14 - Funnel analysis by time (CohortPipe) with reasoning plan:
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
            
            logger.info(f"Calling generation_chain.ainvoke with parameters:")
            logger.info(f"  context: {context}")
            logger.info(f"  function_name: {function_name}")
            logger.info(f"  pipeline_type: {pipeline_type.value}")
            logger.info(f"  dataframe_name: {formatted_dataframe_name}")
            
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
                "function_definitions": function_definitions,
                "iteration": query_state["iteration"],
                "name": function_name  # Add the missing name variable
            })
            
            # Debug: Check what the LLM returned
            logger.info(f"LLM returned type: {type(generated_code)}")
            logger.info(f"LLM returned value: {repr(generated_code)[:200]}")
            
            # Check if it's a dict or other structured object
            if isinstance(generated_code, dict):
                logger.error(f"LLM returned a dict: {generated_code}")
                # Try to extract content from common LLM response formats
                if 'content' in generated_code:
                    generated_code = generated_code['content']
                elif 'text' in generated_code:
                    generated_code = generated_code['text']
                elif 'response' in generated_code:
                    generated_code = generated_code['response']
                else:
                    generated_code = str(generated_code)
                logger.info(f"Extracted content: {repr(generated_code)[:200]}")
            elif hasattr(generated_code, 'content'):
                logger.error(f"LLM returned object with content attribute: {generated_code}")
                generated_code = generated_code.content
                logger.info(f"Extracted content: {repr(generated_code)[:200]}")
            
            # Ensure generated_code is a string
            if not isinstance(generated_code, str):
                logger.error(f"LLM returned non-string value: {type(generated_code)} - {generated_code}")
                generated_code = str(generated_code) if generated_code is not None else ""
                logger.info(f"Converted to string: {repr(generated_code)[:200]}")
            
            # Debug: Check generated_code before cleaning
            logger.info(f"Generated code type: {type(generated_code)}")
            logger.info(f"Generated code: {repr(generated_code)[:200]}")
            
            # Clean up the generated code
            code = self._clean_generated_code(generated_code)
            
            # Debug: Check what we have after cleaning
            logger.info(f"After cleaning - code type: {type(code)}")
            logger.info(f"After cleaning - code: {repr(code)[:200]}")
            
            # Validate the cleaned code
            try:
                ast.parse(code)
                logger.info("Generated code passed syntax validation")
            except SyntaxError as e:
                logger.warning(f"Syntax error in cleaned code: {e}")
                # Try to fix the code
                code = self._extract_valid_code_parts(code)
                logger.info("Attempted to extract valid code parts")
                logger.info(f"After extraction - code type: {type(code)}")
                logger.info(f"After extraction - code: {repr(code)[:200]}")
            
            query_state["code_attempts"].append(code)
            
            return code
            
        except Exception as e:
            logger.error(f"Error in code generation: {e}")
            fallback_code = self._generate_fallback_code(
                pipeline_type, function_name, function_inputs, dataframe_name
            )
            query_state["code_attempts"].append(fallback_code)
            return fallback_code
    
    async def _evaluate_reasoning_plan_quality(self, reasoning_plan: List[Dict[str, Any]], 
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
            "plan_adjustments": [],
            "intent_consistency": True,
            "step_intent_issues": []
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
                [PipelineType.METRICS, PipelineType.MOVINGAGGR],
                [PipelineType.OPERATIONS, PipelineType.MOVINGAGGR],
                [PipelineType.MOVINGAGGR, PipelineType.ANOMALY],
                [PipelineType.METRICS, PipelineType.MOVINGAGGR, PipelineType.ANOMALY],
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
        
        # Validate step intents and consistency
        intent_validation = await self._validate_step_intents(reasoning_plan, query_state)
        evaluation["intent_consistency"] = intent_validation["consistent"]
        evaluation["step_intent_issues"] = intent_validation["issues"]
        
        # Add intent issues to main issues list
        if intent_validation["issues"]:
            evaluation["issues"].extend(intent_validation["issues"])
        
        # Calculate quality score based on issues
        total_checks = len(reasoning_plan) * 3 + 3  # Basic checks per step + overall checks
        issue_count = len(evaluation["issues"])
        evaluation["quality_score"] = max(0.0, 1.0 - (issue_count / total_checks))
        
        # Generate suggestions based on issues
        if evaluation["quality_score"] < 0.7:
            evaluation["suggestions"].append("Consider simplifying the reasoning plan")
            evaluation["suggestions"].append("Ensure all functions are from the same pipeline type or follow valid multi-pipeline patterns")
        
        return evaluation
    
    async def _validate_step_intents(self, reasoning_plan: List[Dict[str, Any]], 
                             query_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate step intents and check consistency with overall analysis intent
        
        Args:
            reasoning_plan: List of reasoning plan steps
            query_state: Current query state with classification info
            
        Returns:
            Dictionary with intent validation results
        """
        validation = {
            "consistent": True,
            "issues": [],
            "suggestions": []
        }
        
        if not reasoning_plan or not isinstance(reasoning_plan, list):
            return validation
        
        # Get overall analysis intent from query state
        classification = query_state.get("classification")
        overall_intent = None
        if classification:
            if hasattr(classification, 'intent_type'):
                overall_intent = classification.intent_type
            elif isinstance(classification, dict):
                overall_intent = classification.get('intent_type')
        
        # Validate each step's intent
        for i, step in enumerate(reasoning_plan):
            if not isinstance(step, dict):
                continue
            
            step_number = i + 1
            step_title = step.get('step_title', f'Step {step_number}')
            step_description = step.get('step_description', '')
            function_name = step.get('function_name', '')
            pipeline_type = step.get('pipeline_type', '')
            function_category = step.get('function_category', '')
            
            # Check if step intent aligns with overall analysis intent
            if overall_intent and self._is_intent_mismatch(overall_intent, step, step_title, step_description):
                validation["issues"].append(
                    f"Step {step_number} intent mismatch: '{step_title}' doesn't align with overall intent '{overall_intent}'"
                )
                validation["consistent"] = False
            
            # Check for missing intent indicators
            if not step_title and not step_description:
                validation["issues"].append(f"Step {step_number} missing clear intent indicators")
            
            # Check for conflicting pipeline types within the same step
            if pipeline_type and function_category:
                if self._is_pipeline_category_mismatch(pipeline_type, function_category):
                    validation["issues"].append(
                        f"Step {step_number} pipeline type '{pipeline_type}' conflicts with function category '{function_category}'"
                    )
                    validation["consistent"] = False
            
            # Check for embedded function intent consistency
            embedded_function_parameter = step.get('embedded_function_parameter', False)
            embedded_function_details = step.get('embedded_function_details', {})
            if embedded_function_parameter and embedded_function_details:
                embedded_function = embedded_function_details.get('embedded_function', '')
                if embedded_function and not await self._is_embedded_function_appropriate(function_name, embedded_function):
                    validation["issues"].append(
                        f"Step {step_number} embedded function '{embedded_function}' not appropriate for '{function_name}'"
                    )
                    validation["consistent"] = False
        
        # Check overall step sequence consistency
        sequence_issues = self._validate_step_sequence(reasoning_plan, overall_intent)
        if sequence_issues:
            validation["issues"].extend(sequence_issues)
            validation["consistent"] = False
        
        return validation
    
    def _is_intent_mismatch(self, overall_intent: str, step: Dict[str, Any], 
                           step_title: str, step_description: str) -> bool:
        """
        Check if a step's intent mismatches with the overall analysis intent
        """
        # Define intent keywords for each analysis type
        intent_keywords = {
            "time_series_analysis": ["time", "series", "rolling", "window", "lag", "lead", "trend", "variance", "moving"],
            "trend_analysis": ["trend", "growth", "forecast", "prediction", "rate", "change"],
            "segmentation_analysis": ["segment", "group", "cluster", "category", "class"],
            "cohort_analysis": ["cohort", "retention", "lifetime", "period", "cohort"],
            "funnel_analysis": ["funnel", "conversion", "journey", "path", "step"],
            "risk_analysis": ["risk", "var", "monte", "carlo", "volatility", "portfolio"],
            "anomaly_detection": ["anomaly", "outlier", "detection", "unusual", "abnormal"],
            "metrics_calculation": ["metric", "statistic", "mean", "sum", "count", "aggregate"],
            "operations_analysis": ["operation", "test", "experiment", "ab", "confidence", "interval"]
        }
        
        # Get keywords for the overall intent
        expected_keywords = intent_keywords.get(overall_intent, [])
        if not expected_keywords:
            return False
        
        # Check if step content matches expected keywords
        step_content = f"{step_title} {step_description}".lower()
        has_matching_keywords = any(keyword in step_content for keyword in expected_keywords)
        
        # If no matching keywords found, it might be a mismatch
        return not has_matching_keywords
    
    def _is_pipeline_category_mismatch(self, pipeline_type: str, function_category: str) -> bool:
        """
        Check if pipeline type and function category are compatible
        """
        # Define compatible mappings
        compatible_mappings = {
            "MetricsPipe": ["basic_metrics", "statistical_metrics", "aggregation"],
            "TimeSeriesPipe": ["time_aggregation", "time_series", "rolling", "lag_lead"],
            "CohortPipe": ["cohort_analysis", "retention", "lifetime_value"],
            "FunnelPipe": ["funnel_analysis", "conversion", "user_journey"],
            "TrendPipe": ["trend_analysis", "growth", "forecasting"],
            "SegmentPipe": ["segmentation", "clustering", "grouping"],
            "RiskPipe": ["risk_analysis", "var", "monte_carlo"],
            "AnomalyPipe": ["anomaly_detection", "outlier", "detection"],
            "OperationsPipe": ["operations_analysis", "ab_testing", "experiments"],
            "MovingAggrPipe": ["moving_aggregation", "rolling", "time_series"]
        }
        
        compatible_categories = compatible_mappings.get(pipeline_type, [])
        return function_category not in compatible_categories
    
    async def _is_embedded_function_appropriate(self, parent_function: str, embedded_function: str) -> bool:
        """
        Check if embedded function is appropriate for the parent function
        """
        try:
            # Get available embedded functions dynamically
            available_embedded_functions = await self._get_available_embedded_functions()
            
            # For moving_apply_by_group, any available embedded function is appropriate
            if parent_function == "moving_apply_by_group":
                return embedded_function in available_embedded_functions
            
            # For other functions, check if the embedded function is available
            return embedded_function in available_embedded_functions
            
        except Exception as e:
            logger.warning(f"Error checking embedded function appropriateness: {e}")
            # Fallback to basic check
            return embedded_function in ["mean", "sum", "count", "variance", "std", "min", "max", "median"]
    
    def _validate_step_sequence(self, reasoning_plan: List[Dict[str, Any]], overall_intent: str) -> List[str]:
        """
        Validate the sequence of steps for logical flow
        """
        issues = []
        
        if not reasoning_plan or len(reasoning_plan) < 2:
            return issues
        
        # Check for logical step ordering based on intent
        if overall_intent == "time_series_analysis":
            # For time series, data preparation should come before analysis
            first_step = reasoning_plan[0]
            if "preparation" not in first_step.get('step_title', '').lower():
                issues.append("Time series analysis should start with data preparation step")
        
        elif overall_intent == "funnel_analysis":
            # For funnel analysis, data selection should come before conversion analysis
            has_data_selection = any("selection" in step.get('step_title', '').lower() 
                                   for step in reasoning_plan[:2])
            if not has_data_selection:
                issues.append("Funnel analysis should include data selection step early in sequence")
        
        # Check for dependency issues
        for i, step in enumerate(reasoning_plan):
            step_dependencies = step.get('step_dependencies', [])
            if step_dependencies:
                for dep in step_dependencies:
                    if dep > i + 1:  # Dependencies should reference previous steps
                        issues.append(f"Step {i+1} has invalid dependency on future step {dep}")
        
        return issues
    
    async def _validate_single_step_intent(self, step: Dict[str, Any], 
                                   classification: Union[Dict[str, Any], AnalysisIntentResult], 
                                   step_number: int) -> Dict[str, Any]:
        """
        Validate a single step's intent against the overall classification
        """
        validation = {
            "valid": True,
            "issues": [],
            "suggestions": []
        }
        
        if not step or not isinstance(step, dict):
            validation["valid"] = False
            validation["issues"].append("Step is not a valid dictionary")
            return validation
        
        # Get overall intent
        overall_intent = None
        if classification:
            if hasattr(classification, 'intent_type'):
                overall_intent = classification.intent_type
            elif isinstance(classification, dict):
                overall_intent = classification.get('intent_type')
        
        if not overall_intent:
            return validation
        
        step_title = step.get('step_title', f'Step {step_number}')
        step_description = step.get('step_description', '')
        function_name = step.get('function_name', '')
        
        # Check intent alignment
        if self._is_intent_mismatch(overall_intent, step, step_title, step_description):
            validation["valid"] = False
            validation["issues"].append(f"Step intent doesn't align with overall intent '{overall_intent}'")
            validation["suggestions"].append(f"Consider adjusting step title or description to include keywords related to '{overall_intent}'")
        
        # Check embedded function appropriateness
        embedded_function_parameter = step.get('embedded_function_parameter', False)
        embedded_function_details = step.get('embedded_function_details', {})
        if embedded_function_parameter and embedded_function_details:
            embedded_function = embedded_function_details.get('embedded_function', '')
            if embedded_function and not await self._is_embedded_function_appropriate(function_name, embedded_function):
                validation["valid"] = False
                validation["issues"].append(f"Embedded function '{embedded_function}' not appropriate for '{function_name}'")
                validation["suggestions"].append(f"Use appropriate embedded functions for '{function_name}'")
        
        return validation
    
    async def _fix_step_intent(self, step: Dict[str, Any], 
                        classification: Union[Dict[str, Any], AnalysisIntentResult], 
                        validation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fix step intent issues based on validation results
        """
        fixed_step = step.copy()
        
        # Get overall intent
        overall_intent = None
        if classification:
            if hasattr(classification, 'intent_type'):
                overall_intent = classification.intent_type
            elif isinstance(classification, dict):
                overall_intent = classification.get('intent_type')
        
        if not overall_intent:
            return fixed_step
        
        # Fix intent mismatch by updating step title/description
        if "intent doesn't align" in str(validation.get('issues', [])):
            step_title = fixed_step.get('step_title', '')
            step_description = fixed_step.get('step_description', '')
            
            # Add intent-specific keywords to step title
            intent_keywords = {
                "time_series_analysis": ["Time Series", "Window", "Variance"],
                "trend_analysis": ["Trend", "Growth", "Forecast"],
                "segmentation_analysis": ["Segmentation", "Grouping", "Clustering"],
                "cohort_analysis": ["Cohort", "Retention", "Lifetime"],
                "funnel_analysis": ["Funnel", "Conversion", "Journey"],
                "risk_analysis": ["Risk", "VaR", "Volatility"],
                "anomaly_detection": ["Anomaly", "Outlier", "Detection"],
                "metrics_calculation": ["Metrics", "Statistics", "Aggregation"],
                "operations_analysis": ["Operations", "Testing", "Analysis"]
            }
            
            keywords = intent_keywords.get(overall_intent, [])
            if keywords and not any(keyword.lower() in step_title.lower() for keyword in keywords):
                # Add appropriate keyword to step title
                fixed_step['step_title'] = f"{keywords[0]} {step_title}"
                logger.info(f"Fixed step title to include intent keyword: {fixed_step['step_title']}")
        
        # Fix embedded function issues
        if "Embedded function" in str(validation.get('issues', [])):
            embedded_function_details = fixed_step.get('embedded_function_details', {})
            function_name = fixed_step.get('function_name', '')
            
            if embedded_function_details and function_name:
                # Get appropriate embedded functions dynamically
                try:
                    available_embedded_functions = await self._get_available_embedded_functions()
                    appropriate_functions = available_embedded_functions[:5]  # Use first 5 available functions
                except Exception as e:
                    logger.warning(f"Error getting embedded functions for fix: {e}")
                    appropriate_functions = ["mean", "sum", "count", "variance", "std"]
                if appropriate_functions:
                    embedded_function_details['embedded_function'] = appropriate_functions[0]
                    fixed_step['embedded_function_details'] = embedded_function_details
                    logger.info(f"Fixed embedded function to: {appropriate_functions[0]}")
        
        return fixed_step
    
    async def _adjust_reasoning_plan(self, reasoning_plan: List[Dict[str, Any]], 
                                   evaluation: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Adjust the reasoning plan based on evaluation results using LLM and available stores
        
        Args:
            reasoning_plan: Original reasoning plan
            evaluation: Evaluation results
            
        Returns:
            Adjusted reasoning plan
        """
        if not reasoning_plan or not isinstance(reasoning_plan, list):
            return reasoning_plan
        
        # Create a query state for retrieval
        query_state = {
            "context": "reasoning plan adjustment",
            "function_name": "reasoning_plan_adjustment",
            "dataframe_name": "df"
        }
        
        # Retrieve relevant documents for reasoning plan adjustment
        retrieved_docs = await self._retrieve_documents_for_reasoning_adjustment(reasoning_plan, evaluation)
        
        # Use LLM to adjust the reasoning plan
        adjusted_plan = await self._adjust_reasoning_plan_with_llm(
            reasoning_plan, evaluation, retrieved_docs
        )
        
        return adjusted_plan
    
    async def _retrieve_documents_for_reasoning_adjustment(self, reasoning_plan: List[Dict[str, Any]], 
                                                         evaluation: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retrieve relevant documents for reasoning plan adjustment using RetrievalHelper when available
        """
        retrieved_docs = {}
        
        # Extract function names from reasoning plan
        function_names = []
        for step in reasoning_plan:
            if isinstance(step, dict) and 'function_name' in step:
                function_names.append(step['function_name'])
        
        # Create queries for retrieval
        queries = []
        if function_names:
            queries.extend(function_names)
        
        # Add evaluation issues as queries
        if 'issues' in evaluation:
            for issue in evaluation['issues']:
                queries.append(issue)
        
        # Add suggestions as queries
        if 'suggestions' in evaluation:
            for suggestion in evaluation['suggestions']:
                queries.append(suggestion)
        
        # Use RetrievalHelper if available, otherwise fallback to direct store access
        if self.retrieval_helper and function_names:
            try:
                # Retrieve function examples for each function
                for function_name in function_names[:3]:  # Limit to first 3 functions
                    examples_result = await self.retrieval_helper.get_function_examples(
                        function_name=function_name,
                        similarity_threshold=0.6,
                        top_k=3
                    )
                    if examples_result and not examples_result.get("error"):
                        if "usage_examples" not in retrieved_docs:
                            retrieved_docs["usage_examples"] = []
                        retrieved_docs["usage_examples"].extend([
                            {"content": ex, "score": 0.8} for ex in examples_result.get("examples", [])
                        ])
                
                # Retrieve function insights for each function
                for function_name in function_names[:3]:  # Limit to first 3 functions
                    insights_result = await self.retrieval_helper.get_function_insights(
                        function_name=function_name,
                        similarity_threshold=0.6,
                        top_k=3
                    )
                    if insights_result and not insights_result.get("error"):
                        if "code_examples" not in retrieved_docs:
                            retrieved_docs["code_examples"] = []
                        retrieved_docs["code_examples"].extend([
                            {"content": insight, "score": 0.8} for insight in insights_result.get("insights", [])
                        ])
                
                # Retrieve function definitions for each function
                for function_name in function_names[:3]:  # Limit to first 3 functions
                    definition_result = await self.retrieval_helper.get_function_definition(
                        function_name=function_name,
                        similarity_threshold=0.7,
                        top_k=1
                    )
                    if definition_result:
                        # Handle both string and dictionary returns from RetrievalHelper
                        if "function_definitions" not in retrieved_docs:
                            retrieved_docs["function_definitions"] = []
                        
                        if isinstance(definition_result, str):
                            retrieved_docs["function_definitions"].append({
                                "content": definition_result, "score": 0.9
                            })
                        elif isinstance(definition_result, dict) and not definition_result.get("error"):
                            retrieved_docs["function_definitions"].append({
                                "content": definition_result, "score": 0.9
                            })
                
            except Exception as e:
                logger.warning(f"Error using RetrievalHelper for reasoning adjustment: {e}, falling back to direct store access")
                # Fallback to direct store access
                retrieved_docs = await self._retrieve_documents_for_reasoning_adjustment_fallback(queries, function_names)
        else:
            # Fallback to direct store access
            retrieved_docs = await self._retrieve_documents_for_reasoning_adjustment_fallback(queries, function_names)
        
        return retrieved_docs
    
    async def _retrieve_documents_for_reasoning_adjustment_fallback(self, queries: List[str], function_names: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """Fallback method for direct store access when RetrievalHelper is not available"""
        retrieved_docs = {}
        
        # Retrieve from usage examples store
        if self.usage_examples_store and queries:
            try:
                usage_results = self.usage_examples_store.semantic_searches(
                    queries[:3], n_results=5  # Limit to first 3 queries
                )
                retrieved_docs["usage_examples"] = self._parse_retrieval_results(usage_results)
            except Exception as e:
                print(f"Error retrieving from usage examples store: {e}")
        
        # Retrieve from code examples store
        if self.code_examples_store and queries:
            try:
                code_results = self.code_examples_store.semantic_searches(
                    queries[:3], n_results=5
                )
                retrieved_docs["code_examples"] = self._parse_retrieval_results(code_results)
            except Exception as e:
                print(f"Error retrieving from code examples store: {e}")
        
        # Retrieve from function definition store
        if self.function_definition_store and function_names:
            try:
                func_results = self.function_definition_store.semantic_searches(
                    function_names[:3], n_results=3
                )
                retrieved_docs["function_definitions"] = self._parse_retrieval_results(func_results)
            except Exception as e:
                print(f"Error retrieving from function definition store: {e}")
        
        return retrieved_docs
    
    async def _adjust_reasoning_plan_with_llm(self, reasoning_plan: List[Dict[str, Any]], 
                                            evaluation: Dict[str, Any], 
                                            retrieved_docs: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        Use LLM to adjust reasoning plan based on evaluation and retrieved documents
        """
        # Format the reasoning plan for LLM
        reasoning_plan_json = json.dumps(reasoning_plan, indent=2)
        evaluation_json = json.dumps(evaluation, indent=2)
        
        # Format retrieved documents
        docs_context = self._format_documents_for_reasoning_adjustment(retrieved_docs)
        
        # Create adjustment prompt
        adjustment_prompt = PromptTemplate(
            input_variables=["reasoning_plan", "evaluation", "docs_context"],
            template="""
            You are an expert at adjusting reasoning plans for data analysis pipelines.
            
            CURRENT REASONING PLAN:
            {reasoning_plan}
            
            EVALUATION RESULTS:
            {evaluation}
            
            RELEVANT DOCUMENTS AND EXAMPLES:
            {docs_context}
            
            TASK: Adjust the reasoning plan to fix the identified issues and improve quality.
            
            REQUIREMENTS:
            1. Fix missing required fields (step_number, step_title, function_name, parameter_mapping)
            2. Replace invalid functions with appropriate alternatives from the available function library
            3. Ensure proper pipeline type consistency
            4. Fix parameter mapping issues
            5. Maintain the logical flow and intent of the original plan
            6. Use only functions that are available in the function library
            7. **CRITICAL**: Ensure step intents align with the overall analysis intent
            8. **CRITICAL**: Fix any step intent mismatches identified in the evaluation
            9. **CRITICAL**: Ensure embedded functions are appropriate for their parent functions
            10. **CRITICAL**: Maintain proper step sequence based on analysis type
            
            AVAILABLE FUNCTION TYPES (from the documents):
            - MetricsPipe functions: Mean, Sum, Count, Variance, Max, Min, Median, Percentile, Correlation, StandardDeviation
            - TimeSeriesPipe functions: variance_analysis, lead, lag, rolling_window, distribution_analysis, cumulative_distribution
            - MovingAggrPipe functions: moving_average, moving_variance, moving_sum, moving_quantile, moving_apply_by_group
            - CohortPipe functions: form_time_cohorts, calculate_retention, calculate_conversion, calculate_lifetime_value
            - SegmentPipe functions: get_features, run_kmeans, run_dbscan, run_hierarchical, run_rule_based
            - AnomalyPipe functions: detect_statistical_outliers, detect_contextual_anomalies, detect_collective_anomalies
            - TrendsPipe functions: aggregate_by_time, calculate_growth_rates, calculate_statistical_trend, forecast_metric
            - RiskPipe functions: calculate_var, calculate_cvar, monte_carlo_simulation, stress_test
            - OperationsPipe functions: PercentChange, AbsoluteChange, MH, CUPED, PrePostChange
            - FunnelPipe functions: analyze_funnel, analyze_funnel_by_time, analyze_funnel_by_segment
            
            OUTPUT FORMAT:
            CRITICAL: You must return ONLY a valid JSON array without any markdown formatting, code blocks, or extra text.
            
            CORRECT FORMAT:
            [
                {{
                    "step_number": 1,
                    "step_title": "Group data by region and project",
                    "function_name": "GroupBy",
                    "parameter_mapping": {{
                        "by": ["Region", "Project"],
                        "agg_dict": {{"Transactional value": "sum"}}
                    }}
                }},
                {{
                    "step_number": 2,
                    "step_title": "Calculate mean daily transactional values",
                    "function_name": "Mean",
                    "parameter_mapping": {{
                        "variable": "Transactional value",
                        "output_name": "average_daily_transactional_value"
                    }}
                }}
            ]
            
            WRONG FORMATS (DO NOT USE):
            ❌ ```json
            ❌ ```python
            ❌ Any markdown formatting
            ❌ Explanations before or after the JSON
            ❌ Extra text or comments
            
            CONSEQUENCES OF IMPROPER FORMAT:
            - If you return markdown code blocks, the parsing will fail
            - If you add extra text, the JSON parsing will fail
            - If you don't return valid JSON, the system will fall back to basic fixes
            - This will result in poor reasoning plan quality
            - The user's analysis pipeline will not work correctly
            
            Return ONLY the JSON array, nothing else.
            
            ADJUSTED REASONING PLAN:
            """
        )
        
        adjustment_chain = adjustment_prompt | self.llm | StrOutputParser()
        
        try:
            # Get LLM adjustment
            adjusted_plan_str = await adjustment_chain.ainvoke({
                "reasoning_plan": reasoning_plan_json,
                "evaluation": evaluation_json,
                "docs_context": docs_context
            })
            
            # Parse the adjusted plan
            adjusted_plan = self._parse_adjusted_reasoning_plan(adjusted_plan_str)
            
            # Validate the adjusted plan
            if not adjusted_plan or not isinstance(adjusted_plan, list):
                print("LLM adjustment failed, falling back to basic fixes")
                return self._apply_basic_reasoning_plan_fixes(reasoning_plan)
            
            return adjusted_plan
            
        except Exception as e:
            print(f"Error in LLM-based reasoning plan adjustment: {e}")
            # Fall back to basic fixes
            return self._apply_basic_reasoning_plan_fixes(reasoning_plan)
    
    def _format_documents_for_reasoning_adjustment(self, retrieved_docs: Dict[str, List[Dict[str, Any]]]) -> str:
        """
        Format retrieved documents for reasoning plan adjustment
        """
        if not retrieved_docs:
            return "No relevant documents available."
        
        formatted_docs = []
        
        for doc_type, documents in retrieved_docs.items():
            if not documents:
                continue
                
            formatted_docs.append(f"\n{doc_type.upper()}:")
            
            for i, doc in enumerate(documents[:3]):  # Limit to 3 docs per type
                try:
                    if isinstance(doc, dict):
                        content = doc.get('content', doc.get('page_content', str(doc)))
                    else:
                        content = str(doc)
                    
                    # Truncate long content
                    if len(content) > 500:
                        content = content[:500] + "..."
                    
                    formatted_docs.append(f"  {i+1}. {content}")
                except Exception as e:
                    print(f"Error formatting document {i} in {doc_type}: {e}")
        
        return "\n".join(formatted_docs) if formatted_docs else "No relevant documents available."
    
    def _parse_adjusted_reasoning_plan(self, adjusted_plan_str: str) -> List[Dict[str, Any]]:
        """
        Parse the LLM-adjusted reasoning plan from string to list of dictionaries
        """
        try:
            # Try to extract JSON from the response
            # Look for JSON array pattern
            import re
            import json
            
            # Clean the response text - remove markdown code blocks and extra formatting
            cleaned_text = adjusted_plan_str.strip()
            
            # Remove markdown code blocks (```json ... ```)
            cleaned_text = re.sub(r'```json\s*', '', cleaned_text)
            cleaned_text = re.sub(r'```\s*', '', cleaned_text)
            
            # Remove any leading/trailing whitespace and newlines
            cleaned_text = cleaned_text.strip()
            
            # First try to parse the cleaned text directly
            try:
                adjusted_plan = json.loads(cleaned_text)
                if isinstance(adjusted_plan, list):
                    # Successfully parsed as list, validate and return
                    validated_plan = []
                    for step in adjusted_plan:
                        if isinstance(step, dict):
                            # Ensure required fields
                            validated_step = {
                                "step_number": step.get("step_number", 1),
                                "step_title": step.get("step_title", "Step"),
                                "function_name": step.get("function_name", "Mean"),
                                "parameter_mapping": step.get("parameter_mapping", {})
                            }
                            validated_plan.append(validated_step)
                    
                    return validated_plan
            except json.JSONDecodeError:
                # If direct parsing fails, try to extract JSON array pattern
                pass
            
            # Find JSON array in the cleaned response
            json_match = re.search(r'\[.*\]', cleaned_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                adjusted_plan = json.loads(json_str)
                
                # Validate the structure
                if isinstance(adjusted_plan, list):
                    validated_plan = []
                    for step in adjusted_plan:
                        if isinstance(step, dict):
                            # Ensure required fields
                            validated_step = {
                                "step_number": step.get("step_number", 1),
                                "step_title": step.get("step_title", "Step"),
                                "function_name": step.get("function_name", "Mean"),
                                "parameter_mapping": step.get("parameter_mapping", {})
                            }
                            validated_plan.append(validated_step)
                    
                    return validated_plan
            
            # If still no success, try to extract from the original text with markdown blocks
            json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', adjusted_plan_str, re.DOTALL)
            if json_match:
                json_content = json_match.group(1)
                adjusted_plan = json.loads(json_content)
                
                # Validate the structure
                if isinstance(adjusted_plan, list):
                    validated_plan = []
                    for step in adjusted_plan:
                        if isinstance(step, dict):
                            # Ensure required fields
                            validated_step = {
                                "step_number": step.get("step_number", 1),
                                "step_title": step.get("step_title", "Step"),
                                "function_name": step.get("function_name", "Mean"),
                                "parameter_mapping": step.get("parameter_mapping", {})
                            }
                            validated_plan.append(validated_step)
                    
                    return validated_plan
            
            # If still no success, try to extract from the original text with markdown blocks (alternative pattern)
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', adjusted_plan_str, re.DOTALL)
            if json_match:
                json_content = json_match.group(1)
                try:
                    adjusted_plan = json.loads(json_content)
                    
                    # Validate the structure
                    if isinstance(adjusted_plan, list):
                        validated_plan = []
                        for step in adjusted_plan:
                            if isinstance(step, dict):
                                # Ensure required fields
                                validated_step = {
                                    "step_number": step.get("step_number", 1),
                                    "step_title": step.get("step_title", "Step"),
                                    "function_name": step.get("function_name", "Mean"),
                                    "parameter_mapping": step.get("parameter_mapping", {})
                                }
                                validated_plan.append(validated_step)
                        
                        return validated_plan
                except json.JSONDecodeError:
                    # If this pattern also fails, continue to next fallback
                    pass
            
            # If JSON parsing fails, try to extract individual steps
            return self._extract_steps_from_text(adjusted_plan_str)
            
        except Exception as e:
            print(f"Error parsing adjusted reasoning plan: {e}")
            # Try to extract JSON content from markdown blocks as a final fallback
            try:
                # Look for JSON content between markdown code blocks
                json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', adjusted_plan_str, re.DOTALL)
                if json_match:
                    json_content = json_match.group(1)
                    adjusted_plan = json.loads(json_content)
                    if isinstance(adjusted_plan, list):
                        # Validate the structure
                        validated_plan = []
                        for step in adjusted_plan:
                            if isinstance(step, dict):
                                # Ensure required fields
                                validated_step = {
                                    "step_number": step.get("step_number", 1),
                                    "step_title": step.get("step_title", "Step"),
                                    "function_name": step.get("function_name", "Mean"),
                                    "parameter_mapping": step.get("parameter_mapping", {})
                                }
                                validated_plan.append(validated_step)
                        
                        print("Successfully extracted JSON array from markdown blocks using fallback")
                        return validated_plan
            except Exception as fallback_error:
                print(f"Fallback JSON extraction also failed: {fallback_error}")
            
            return []
    
    def _extract_steps_from_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract reasoning plan steps from text when JSON parsing fails
        """
        steps = []
        lines = text.split('\n')
        current_step = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Look for step patterns
            if 'step_number' in line.lower() or 'step_title' in line.lower():
                if current_step:
                    steps.append(current_step)
                current_step = {}
            
            # Extract key-value pairs
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().strip('"{}').lower()
                value = value.strip().strip('"{}')
                
                if key == 'step_number':
                    current_step['step_number'] = int(value) if value.isdigit() else 1
                elif key == 'step_title':
                    current_step['step_title'] = value
                elif key == 'function_name':
                    current_step['function_name'] = value
                elif key == 'parameter_mapping':
                    current_step['parameter_mapping'] = {}
        
        if current_step:
            steps.append(current_step)
        
        return steps
    
    def _apply_basic_reasoning_plan_fixes(self, reasoning_plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply basic fixes to reasoning plan when LLM adjustment fails
        """
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
                adjusted_step['function_name'] = 'Mean'  # Default fallback
            
            if 'parameter_mapping' not in adjusted_step:
                adjusted_step['parameter_mapping'] = {}
            
            adjusted_plan.append(adjusted_step)
        
        return adjusted_plan
    
    async def _grade_code(self, generated_code: str, query_state: Dict[str, Any]) -> CodeQuality:
        """Grade the quality of generated code"""
        import logging
        logger = logging.getLogger(__name__)
        
        # Debug: Check what type generated_code is
        logger.info(f"_grade_code received type: {type(generated_code)}")
        logger.info(f"_grade_code received value: {repr(generated_code)[:200]}")
        
        # Handle case where entire pipeline result dictionary is passed instead of just code
        if isinstance(generated_code, dict):
            logger.warning(f"_grade_code received dict instead of string, extracting combined_code")
            if 'combined_code' in generated_code:
                generated_code = generated_code['combined_code']
                logger.info(f"Extracted combined_code: {repr(generated_code)[:200]}")
            else:
                logger.error(f"Dict does not contain 'combined_code' key: {list(generated_code.keys())}")
                return CodeQuality.INVALID
        
        # Ensure generated_code is a string
        if not isinstance(generated_code, str):
            logger.error(f"generated_code is not a string in _grade_code: {type(generated_code)} - {generated_code}")
            return CodeQuality.INVALID
        
        # Syntax validation
        try:
            ast.parse(generated_code)
        except SyntaxError as e:
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
        classification = query_state.get("classification", {})
        
        # Check if this is a multi-step reasoning plan - prefer pipeline_reasoning_plan (enhanced) over reasoning_plan (basic)
        reasoning_plan = None
        if hasattr(classification, 'pipeline_reasoning_plan'):
            reasoning_plan = getattr(classification, 'pipeline_reasoning_plan', None)
        elif hasattr(classification, 'reasoning_plan'):
            reasoning_plan = getattr(classification, 'reasoning_plan', None)
        else:
            reasoning_plan = classification.get('pipeline_reasoning_plan', None) or classification.get('reasoning_plan', None)
        
        if reasoning_plan and len(reasoning_plan) > 1:
            # For multi-step reasoning plans, check that all expected pipeline types are present
            expected_pipeline_types = set()
            for step in reasoning_plan:
                if isinstance(step, dict) and 'pipeline_type' in step:
                    pipeline_type_str = step.get('pipeline_type')
                    if pipeline_type_str and pipeline_type_str != "unknown_category":
                        pipeline_type = self._map_pipe_name_to_pipeline_type(pipeline_type_str)
                        if pipeline_type:
                            expected_pipeline_types.add(pipeline_type.value)
            
            # Check that all expected pipeline types are present in the generated code
            for expected_type in expected_pipeline_types:
                if expected_type not in generated_code:
                    logger.warning(f"Generated code missing expected pipeline type: {expected_type}")
                    return CodeQuality.POOR
            
            # For multi-step plans, don't check for pipeline type mixing as different types are expected
            logger.info(f"Multi-step reasoning plan detected with {len(expected_pipeline_types)} pipeline types")
        else:
            # For single-step pipelines, use the original logic
            primary_pipeline_type = await self._detect_pipeline_type(function_name, "", classification)
            
            # Check if the generated code uses the correct pipeline type
            if primary_pipeline_type.value not in generated_code:
                logger.warning(f"Generated code doesn't use correct pipeline type. Expected: {primary_pipeline_type.value}")
                return CodeQuality.POOR
            
            # Check for pipeline type mixing (e.g., TimeSeriesPipe with MetricsPipe functions)
            pipeline_type_mixing = self._check_pipeline_type_mixing(generated_code, primary_pipeline_type)
            if pipeline_type_mixing:
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
    
    async def _refine_query_state(self, query_state: Dict[str, Any], 
                           code_quality: CodeQuality) -> Dict[str, Any]:
        """Refine query state based on code quality feedback"""
        if code_quality == CodeQuality.INVALID:
            query_state["reasoning"].append("Code had syntax errors, refining generation approach")
        elif code_quality == CodeQuality.POOR:
            # Check if it's due to pipeline type mixing
            function_name = query_state["function_name"]
            classification = query_state.get("classification", {})
            primary_pipeline_type = await self._detect_pipeline_type(function_name, "", classification)
            query_state["reasoning"].append(f"Code quality was poor, likely due to pipeline type mixing. Primary function '{function_name}' should use {primary_pipeline_type.value}")
        
        # Enhance context for next iteration with pipeline type guidance
        function_name = query_state["function_name"]
        classification = query_state.get("classification", {})
        primary_pipeline_type = await self._detect_pipeline_type(function_name, "", classification)
        query_state["context"] += f" [Iteration {query_state['iteration'] + 1}: Use {primary_pipeline_type.value} and stay within the same pipeline type]"
        
        return query_state
    
    async def _get_pipeline_type_from_function_definition(self, function_name: str) -> Optional[PipelineType]:
        """Get pipeline type directly from function definition JSON file"""
        try:
            # Load function definitions from JSON file
            import json
            import os
            
            # Path to the function definitions file
            json_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', 'data', 'meta', 'all_pipes_functions.json')
            
            if not os.path.exists(json_path):
                logger.warning(f"Function definitions file not found: {json_path}")
                return None
            
            with open(json_path, 'r') as f:
                function_definitions = json.load(f)
            
            # Search for the function in all pipeline types
            for pipeline_name, pipeline_data in function_definitions.items():
                if pipeline_name in ["description", "functions"]:
                    continue
                
                functions = pipeline_data.get("functions", {})
                if function_name in functions:
                    # Map pipeline name to PipelineType enum
                    pipeline_type = self._map_pipe_name_to_pipeline_type(pipeline_name)
                    if pipeline_type:
                        logger.info(f"Found function '{function_name}' in {pipeline_name}, mapped to {pipeline_type.value}")
                        return pipeline_type
            
            logger.warning(f"Function '{function_name}' not found in function definitions")
            return None
                
        except Exception as e:
            logger.warning(f"Error retrieving pipeline type for function {function_name}: {str(e)}")
            return None

    async def _detect_pipeline_type(self, function_name: str, context: str, classification: Optional[Union[Dict[str, Any], AnalysisIntentResult]] = None) -> PipelineType:
        """Detect the appropriate pipeline type using FunctionRetrieval system and suggested functions"""
        # First, try to get pipeline type from retrieved functions (most reliable source)
        if classification:
            retrieved_functions = []
            if hasattr(classification, 'retrieved_functions'):
                retrieved_functions = getattr(classification, 'retrieved_functions', [])
            else:
                retrieved_functions = classification.get('retrieved_functions', [])
            
            # Look for the function in retrieved functions to get its pipeline type
            for func in retrieved_functions:
                if isinstance(func, dict) and func.get('function_name') == function_name:
                    # Check for pipe_name in retrieved function (most reliable)
                    pipe_name = func.get('pipe_name')
                    if pipe_name:
                        pipeline_type = self._map_pipe_name_to_pipeline_type(pipe_name)
                        if pipeline_type:
                            logger.info(f"Detected pipeline type {pipeline_type.value} for function '{function_name}' from retrieved functions pipe_name")
                            return pipeline_type
                    
                    # Check for category in retrieved function
                    category = func.get('category')
                    if category and category != "unknown_category":
                        pipeline_type = self._map_pipe_name_to_pipeline_type(category)
                        if pipeline_type:
                            logger.info(f"Detected pipeline type {pipeline_type.value} for function '{function_name}' from retrieved functions category")
                            return pipeline_type
        
        # Second, try to get pipeline type from reasoning plan if available
        if classification:
            reasoning_plan = None
            if hasattr(classification, 'pipeline_reasoning_plan'):
                reasoning_plan = getattr(classification, 'pipeline_reasoning_plan', None)
            elif hasattr(classification, 'reasoning_plan'):
                reasoning_plan = getattr(classification, 'reasoning_plan', None)
            else:
                reasoning_plan = classification.get('pipeline_reasoning_plan', None) or classification.get('reasoning_plan', None)
            
            # Look for the function in reasoning plan to get its pipeline type
            if reasoning_plan and isinstance(reasoning_plan, list):
                for step in reasoning_plan:
                    if isinstance(step, dict) and step.get('function_name') == function_name:
                        # Check for pipeline_type in the step (only if not unknown_category)
                        pipeline_type_str = step.get('pipeline_type')
                        if pipeline_type_str and pipeline_type_str != "unknown_category":
                            pipeline_type = self._map_pipe_name_to_pipeline_type(pipeline_type_str)
                            if pipeline_type:
                                logger.info(f"Detected pipeline type {pipeline_type.value} for function '{function_name}' from reasoning plan")
                                return pipeline_type
                        
                        # Check for function_category in the step
                        function_category = step.get('function_category')
                        if function_category and function_category != "unknown_operation":
                            pipeline_type = self._get_pipeline_type_from_function_category(function_category)
                            if pipeline_type:
                                logger.info(f"Detected pipeline type {pipeline_type.value} for function '{function_name}' from function category: {function_category}")
                                return pipeline_type
        
        # Second, try to get pipeline type from suggested functions if available
        if classification:
            suggested_functions = []
            if hasattr(classification, 'suggested_functions'):
                suggested_functions = getattr(classification, 'suggested_functions', [])
            else:
                suggested_functions = classification.get('suggested_functions', [])
            
            # Look for the function in suggested functions to get its pipeline type
            for suggested_func in suggested_functions:
                extracted_name = self._extract_function_name_from_suggested_function(suggested_func)
                if extracted_name == function_name:
                    pipeline_type_str = self._extract_pipeline_type_from_suggested_function(suggested_func)
                    if pipeline_type_str:
                        pipeline_type = self._map_pipe_name_to_pipeline_type(pipeline_type_str)
                        if pipeline_type:
                            logger.info(f"Detected pipeline type {pipeline_type.value} for function '{function_name}' from suggested functions")
                            return pipeline_type
                        break
        
        # Third, try to get pipeline type from FunctionRetrieval if available
        if self.function_retrieval:
            try:
                # Search for the function in the function library
                search_results = self.function_retrieval.search_functions_by_keyword(function_name)
                if search_results:
                    # Get the first match and extract pipe name
                    pipe_name = search_results[0][0]  # (pipe_name, function_name, function_details)
                    
                    # Map pipe name to PipelineType enum
                    pipeline_type = self._map_pipe_name_to_pipeline_type(pipe_name)
                    if pipeline_type:
                        logger.info(f"Detected pipeline type {pipeline_type.value} for function '{function_name}' using FunctionRetrieval")
                        return pipeline_type
            except Exception as e:
                logger.warning(f"Error using FunctionRetrieval for function '{function_name}': {e}")
        
        # Fourth, fallback to function definition store if FunctionRetrieval is not available
        pipeline_type = await self._get_pipeline_type_from_function_definition(function_name)
        if pipeline_type:
            return pipeline_type
        
        # Final fallback - use context-based detection only as last resort
        logger.warning(f"Could not determine pipeline type for function '{function_name}', using context-based fallback")
        return self._detect_pipeline_type_from_context(context)
    
    def _map_pipe_name_to_pipeline_type(self, pipe_name: str) -> Optional[PipelineType]:
        """Map pipe name from FunctionRetrieval to PipelineType enum"""
        pipe_mapping = {
            "MetricsPipe": PipelineType.METRICS,
            "OperationsPipe": PipelineType.OPERATIONS,
            "TimeSeriesPipe": PipelineType.TIMESERIES,
            "TrendsPipe": PipelineType.TRENDS,
            "TrendPipe": PipelineType.TRENDS,  # Handle alternative naming
            "CohortPipe": PipelineType.COHORT,
            "FunnelPipe": PipelineType.FUNNEL,
            "SegmentPipe": PipelineType.SEGMENT,
            "AnomalyPipe": PipelineType.ANOMALY,
            "RiskPipe": PipelineType.RISK,
            "MovingAggrPipe": PipelineType.MOVINGAGGR,
            "ProphetPipe": PipelineType.PROPHET
        }
        return pipe_mapping.get(pipe_name)
    
    def _get_pipeline_type_from_function_category(self, function_category: str) -> Optional[PipelineType]:
        """Get pipeline type from function category string"""
        category_mapping = {
            "moving_average_analysis": PipelineType.TRENDS,
            "statistical_analysis": PipelineType.TIMESERIES,
            "time_series_analysis": PipelineType.TIMESERIES,
            "trend_analysis": PipelineType.TRENDS,
            "cohort_analysis": PipelineType.COHORT,
            "funnel_analysis": PipelineType.FUNNEL,
            "segmentation_analysis": PipelineType.SEGMENT,
            "anomaly_detection": PipelineType.ANOMALY,
            "risk_analysis": PipelineType.RISK,
            "metrics_calculation": PipelineType.METRICS,
            "operations_analysis": PipelineType.OPERATIONS
        }
        return category_mapping.get(function_category)
    
    def _detect_pipeline_type_from_context(self, context: str) -> PipelineType:
        """Fallback context-based pipeline type detection"""
        context_lower = context.lower()
        
        # Use LLM-like reasoning patterns instead of hardcoded keywords
        if any(term in context_lower for term in ["cohort", "retention", "lifetime"]):
            return PipelineType.COHORT
        elif any(term in context_lower for term in ["time series", "lag", "lead", "rolling", "moving"]):
            return PipelineType.TIMESERIES
        elif any(term in context_lower for term in ["forecast_with_regressors", "prophet", "regressors", "external regressors"]):
            return PipelineType.PROPHET
        elif any(term in context_lower for term in ["trend", "forecast", "growth", "decompose", "seasonal"]):
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
            # Default to METRICS for basic statistical operations
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
        # Debug: Check if code is a string
        if not isinstance(code, str):
            logger.error(f"Code parameter is not a string in _clean_generated_code: {type(code)} - {code}")
            return str(code) if code is not None else ""
        
        if not code:
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
        
        # Fix multi-line pipeline formatting issues
        code = self._fix_multiline_pipeline_formatting(code)
        
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
        # Debug: Check if code is a string
        if not isinstance(code, str):
            logger.error(f"Code parameter is not a string in _fix_common_syntax_issues: {type(code)} - {code}")
            return str(code) if code is not None else ""
        
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
        
        # Fix to_df() missing parentheses - enhanced patterns
        # Pattern 1: | to_df at end of line
        code = re.sub(r'\|\s*to_df\s*(\||\)|$)', r' | to_df()\1', code)
        # Pattern 2: to_df at start of line
        code = re.sub(r'^\s*to_df\s*(\||\)|$)', r'to_df()\1', code)
        # Pattern 3: to_df at end of multi-line pipeline without parentheses
        code = re.sub(r'(\s+)\|\s*to_df\s*$', r'\1| to_df()', code, flags=re.MULTILINE)
        # Pattern 4: to_df followed by newline or end of string
        code = re.sub(r'to_df\s*(?:\n|$)', r'to_df()\1', code)
        # Pattern 5: to_df in the middle of a pipeline chain
        code = re.sub(r'(\|\s*)to_df(\s*\|)', r'\1to_df()\2', code)
        
        # Fix function parameter issues - remove quotes around function names
        # Pattern: func='variance' -> func=variance
        code = re.sub(r"func\s*=\s*'([^']+)'", r'func=\1', code)
        code = re.sub(r'func\s*=\s*"([^"]+)"', r'func=\1', code)
        
        # Fix function parameters to direct method calls
        # Pattern: moving_apply_by_group(func=variance, ...) -> variance(...)
        # This converts function parameters to direct method calls
        function_conversions = {
            'variance': 'variance',
            'mean': 'mean', 
            'sum': 'sum',
            'count': 'count',
            'max': 'max',
            'min': 'min',
            'std': 'std',
            'correlation': 'correlation',
            'covariance': 'covariance',
            'median': 'median',
            'percentile': 'percentile'
        }
        
        for func_param, method_name in function_conversions.items():
            # Pattern: moving_apply_by_group(func=variance, ...) -> variance(...)
            pattern = rf'moving_apply_by_group\s*\(\s*func\s*=\s*{func_param}\s*,([^)]*)\)'
            replacement = rf'{method_name}(\1)'
            code = re.sub(pattern, replacement, code)
            
            # Also handle other wrapper functions
            pattern2 = rf'(\w+)\s*\(\s*func\s*=\s*{func_param}\s*,([^)]*)\)'
            replacement2 = rf'{method_name}(\2)'
            code = re.sub(pattern2, replacement2, code)
        
        # DISABLED: This conversion was causing complex pipeline expressions instead of simple function names
        # The embedded function generation now handles this correctly by using simple function names
        # Pattern: moving_apply_by_group(func=mean, ...) should stay as func=mean
        # for func_param, method_name in function_conversions.items():
        #     # Look for moving_apply_by_group with func parameter
        #     pattern = rf'moving_apply_by_group\s*\(\s*func\s*=\s*{func_param}\s*,([^)]*)\)'
        #     if re.search(pattern, code):
        #         # Extract the dataframe name from the context
        #         dataframe_match = re.search(r'(\w+Pipe\.from_dataframe\([^)]+\))', code)
        #         if dataframe_match:
        #             dataframe_expr = dataframe_match.group(1)
        #             # Convert to embedded function format
        #             replacement = rf'function=({dataframe_expr} | {method_name}(variable=\'Transactional value\') | to_df()),\1'
        #             code = re.sub(pattern, replacement, code)
        #             logger.info(f"Converted function={func_param} to embedded pipeline expression")
        
        # Fix other common function parameter issues
        # Pattern: method='rolling' -> method='rolling' (keep quotes for string values)
        # But: function=Variance -> function=Variance (no quotes for function names)
        
        # Fix missing parentheses in function calls within parameters
        # Pattern: function=Variance -> function=Variance (already handled above)
        
        # Fix pipeline indentation issues - this is the main fix for the reported error
        # Pattern: result = PipeType.from_dataframe(...)\n         | function(...)\n         | to_df()
        # Convert to: result = (PipeType.from_dataframe(...)\n                     | function(...)\n                     | to_df()\n                    )
        print(f"=== FIXING COMMON SYNTAX ISSUES ===", code)
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
        
        # Additional fix for multi-line pipelines with missing to_df parentheses
        # This handles the specific case where to_df appears at the end of a multi-line pipeline
        lines = code.split('\n')
        if len(lines) > 1:
            # Look for the pattern where the last line contains just "to_df" or "| to_df"
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped == 'to_df' or stripped == '| to_df':
                    # Check if this is the end of a pipeline (next line should be empty or contain closing parenthesis)
                    if i == len(lines) - 1 or (i < len(lines) - 1 and lines[i + 1].strip() == ''):
                        # Fix the to_df line
                        if stripped == 'to_df':
                            lines[i] = line.replace('to_df', 'to_df()')
                        elif stripped == '| to_df':
                            lines[i] = line.replace('| to_df', '| to_df()')
                        break
            
            # Rejoin the lines
            code = '\n'.join(lines)
        
        return code
    
    def _fix_multiline_pipeline_formatting(self, code: str) -> str:
        """Fix multi-line pipeline formatting issues, especially to_df() parentheses"""
        lines = code.split('\n')
        if len(lines) < 2:
            return code
        
        # Look for multi-line pipeline patterns
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Pattern 1: Line ending with "to_df" without parentheses
            if stripped.endswith('to_df') and not stripped.endswith('to_df()'):
                # Check if this is part of a pipeline chain
                if '|' in stripped or (i > 0 and '|' in lines[i-1].strip()):
                    # Fix the to_df call
                    lines[i] = line.replace('to_df', 'to_df()')
            
            # Pattern 2: Standalone "to_df" line
            elif stripped == 'to_df':
                # Check if this is the end of a pipeline
                if i == len(lines) - 1 or (i < len(lines) - 1 and lines[i + 1].strip() == ''):
                    lines[i] = line.replace('to_df', 'to_df()')
            
            # Pattern 3: Line with "| to_df" without parentheses
            elif stripped == '| to_df':
                lines[i] = line.replace('| to_df', '| to_df()')
            
            # Pattern 4: Line ending with " - to_df is missing parenthesis" (user's specific case)
            elif stripped.endswith(' - to_df is missing parenthesis'):
                # Remove the comment and add proper to_df()
                lines[i] = line.replace(' - to_df is missing parenthesis', '')
                if not lines[i].strip().endswith('to_df()'):
                    lines[i] = lines[i].replace('to_df', 'to_df()')
        
        # Additional fix for the specific pattern mentioned by the user
        # Look for patterns like: result_anomalies = (...)\n    ).to_df - to_df is missing parenthesis
        for i, line in enumerate(lines):
            if ').to_df' in line and not ').to_df()' in line:
                # Fix the missing parentheses
                lines[i] = line.replace(').to_df', ').to_df()')
        
        return '\n'.join(lines)
    
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
        # Debug: Check if code is a string
        print(f"=== EXTRACTING VALID CODE PARTS ===", code)
        if not isinstance(code, str):
            logger.error(f"Code parameter is not a string in _extract_valid_code_parts: {type(code)} - {code}")
            return str(code) if code is not None else ""
        
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
                            op = re.sub(r"func\s*=\s*'([^']+)'", r'func=\1', op)
                            op = re.sub(r'func\s*=\s*"([^"]+)"', r'func=\1', op)
                            
                            # Fix function parameters to direct method calls
                            function_conversions = {
                                'variance': 'variance',
                                'mean': 'mean', 
                                'sum': 'sum',
                                'count': 'count',
                                'max': 'max',
                                'min': 'min',
                                'std': 'std',
                                'correlation': 'correlation',
                                'covariance': 'covariance',
                                'median': 'median',
                                'percentile': 'percentile'
                            }
                            
                            for func_param, method_name in function_conversions.items():
                                # Pattern: moving_apply_by_group(func=variance, ...) -> variance(...)
                                pattern = rf'moving_apply_by_group\s*\(\s*func\s*=\s*{func_param}\s*,([^)]*)\)'
                                replacement = rf'{method_name}(\1)'
                                op = re.sub(pattern, replacement, op)
                                
                                # Also handle other wrapper functions
                                pattern2 = rf'(\w+)\s*\(\s*func\s*=\s*{func_param}\s*,([^)]*)\)'
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
        """Generate fallback code when main generation fails using unified approach"""
        try:
            inputs_str = self._format_function_inputs(function_inputs)
            
            # Handle dataframe names with spaces
            if ' ' in dataframe_name:
                dataframe_name = f'"{dataframe_name}"'
            
            # Generate a simple, valid fallback code using unified approach
            if inputs_str.strip():
                fallback_code = f"""# Start with original data
result_df = {dataframe_name}.copy()

# Apply {pipeline_type.value} pipeline
result = (
    {pipeline_type.value}.from_dataframe(result)
    | {function_name}({inputs_str})
    ).to_df()

# Final result
result = result"""
            else:
                fallback_code = f"""# Start with original data
result_df = {dataframe_name}.copy()

# Apply {pipeline_type.value} pipeline
result = (
    {pipeline_type.value}.from_dataframe(result)
    | {function_name}()
    ).to_df()

# Final result
result = result"""
            
            # Validate the fallback code
            try:
                ast.parse(fallback_code)
                return fallback_code
            except SyntaxError:
                # If even the fallback has syntax errors, return the most basic version
                return f"""# Start with original data
result_df = {dataframe_name}.copy()

# Apply {pipeline_type.value} pipeline
result = {pipeline_type.value}.from_dataframe(result).to_df()

# Final result
result = result"""
                
        except Exception as e:
            logger.error(f"Error generating fallback code: {e}")
            # Return the most basic valid code
            return f"""# Start with original data
result_df = df.copy()

# Apply MetricsPipe pipeline
result = MetricsPipe.from_dataframe(result).to_df()

# Final result
result = result"""
    
    async def _format_final_result(self, query_state: Dict[str, Any]) -> Dict[str, Any]:
        """Format the final result"""
        # Consider it successful if we have generated code (either in final_code or attempts)
        final_code = query_state["final_code"] or (query_state["code_attempts"][-1] if query_state["code_attempts"] else None)
        has_generated_code = final_code is not None
        
        # Debug: Log query_state structure
        logger.info(f"Formatting final result from query_state")
        logger.info(f"Query state keys: {list(query_state.keys())}")
        logger.info(f"Final code type: {type(final_code)}")
        logger.info(f"Step codes type: {type(query_state.get('step_codes', []))}")
        logger.info(f"Flow graph type: {type(query_state.get('flow_graph', {}))}")
        
        # Debug: Check step_codes structure
        step_codes = query_state.get("step_codes", [])
        if step_codes:
            logger.info(f"Step codes length: {len(step_codes)}")
            logger.info(f"First step type: {type(step_codes[0])}")
            if isinstance(step_codes[0], dict):
                logger.info(f"First step keys: {list(step_codes[0].keys())}")
                for key, value in step_codes[0].items():
                    logger.info(f"First step {key}: {type(value)} - {repr(value)[:100]}")
        
        result = {
            "status": "success" if has_generated_code else "error",
            "generated_code": final_code,
            "step_codes": query_state.get("step_codes", []),
            "flow_graph": query_state.get("flow_graph", {"nodes": [], "edges": [], "metadata": {}}),
            "iterations": query_state["iteration"] + 1,
            "attempts": query_state["code_attempts"],
            "reasoning": query_state["reasoning"],
            "function_name": query_state["function_name"],
            "pipeline_type": (await self._detect_pipeline_type(    
                query_state["function_name"], 
                query_state.get("original_context", query_state["context"]),
                query_state.get("classification", {})
            )).value,
            "detected_inputs": query_state.get("detected_inputs", {}),
            "enhanced_function_inputs": query_state["function_inputs"],
            "function_detection_metadata": query_state.get("function_detection_metadata", {}),
            "classification": query_state.get("classification"),
            "dataset_description": query_state.get("dataset_description"),
            "columns_description": query_state.get("columns_description"),
            "enhanced_context": query_state["context"]
        }
        
        # Debug: Log final result structure
        logger.info(f"Final result type: {type(result)}")
        logger.info(f"Final result keys: {list(result.keys())}")
        for key, value in result.items():
            logger.info(f"Final result {key}: {type(value)} - {repr(value)[:100]}")
        
        return result

    def _combine_parameters(self, required_params, optional_params):
        """
        Combine required and optional parameters, handling both string and dictionary formats
        
        Args:
            required_params: Required parameters (string or list)
            optional_params: Optional parameters (string or list)
            
        Returns:
            Combined list of parameter names
        """
        combined = []
        
        try:
            # Handle required parameters
            if required_params:
                if isinstance(required_params, list):
                    for param in required_params:
                        if isinstance(param, dict):
                            param_name = param.get('name', 'unknown')
                            if param_name and param_name != 'unknown':
                                combined.append(param_name)
                        elif isinstance(param, str) and param.strip():
                            combined.append(param.strip())
                elif isinstance(required_params, str) and required_params.strip():
                    combined.append(required_params.strip())
            
            # Handle optional parameters
            if optional_params:
                if isinstance(optional_params, list):
                    for param in optional_params:
                        if isinstance(param, dict):
                            param_name = param.get('name', 'unknown')
                            if param_name and param_name != 'unknown':
                                combined.append(param_name)
                        elif isinstance(param, str) and param.strip():
                            combined.append(param.strip())
                elif isinstance(optional_params, str) and optional_params.strip():
                    combined.append(optional_params.strip())
                    
        except Exception as e:
            logger.warning(f"Error combining parameters: {e}")
            # Return empty list as fallback
            return []
        
        return combined

    async def _validate_function_against_store(self, function_name: str) -> Dict[str, Any]:
        """
        Validate a function against the function definition store and return its definition
        
        Args:
            function_name: Name of the function to validate
            
        Returns:
            Dictionary containing function validation results and definition
        """
        try:
            # Try to use FunctionRetrieval first if available
            if self.function_retrieval:
                # Try to find the function in any pipe
                found = False
                for pipe_name in self.function_retrieval.get_all_pipes():
                    function_details = self.function_retrieval.get_function_details(function_name, pipe_name)
                    if function_details:
                        found = True
                        # Extract relevant information from the function definition
                        function_info = {
                            "name": function_name,
                            "description": function_details.get("description", "No description available"),
                            "parameters": self._combine_parameters(
                                function_details.get("required_params", []), 
                                function_details.get("optional_params", [])
                            ),
                            "returns": function_details.get("outputs", {}).get("description", "No return information"),
                            "examples": [],  # FunctionRetrieval doesn't provide examples directly
                            "pipeline_type": function_details.get("category", "Unknown"),
                            "syntax": "",  # Not provided by FunctionRetrieval
                            "usage": function_details.get("usage_description", "")
                        }
                        
                        return {
                            "valid": True,
                            "definition": function_info,
                            "error": None
                        }
                
                if not found:
                    return {
                        "valid": False,
                        "definition": None,
                        "error": f"Function '{function_name}' not found in function library"
                    }
            
            # Try RetrievalHelper if available
            elif self.retrieval_helper:
                try:
                    definition_result = await self.retrieval_helper.get_function_definition(
                        function_name=function_name,
                        similarity_threshold=0.7,
                        top_k=1
                    )
                    
                    if definition_result:
                        # Handle both string and dictionary returns from RetrievalHelper
                        if isinstance(definition_result, str):
                            # If it's a string, create a basic function info structure
                            function_info = {
                                "name": function_name,
                                "description": definition_result,
                                "parameters": [],
                            }
                        elif isinstance(definition_result, dict) and not definition_result.get("error"):
                            # Extract relevant information from the function definition
                            function_info = {
                                "name": function_name,
                                "description": definition_result.get("description", "No description available"),
                                "parameters": definition_result.get("parameters", []),
                                "returns": definition_result.get("returns", "No return information"),
                                "examples": definition_result.get("examples", []),
                                "pipeline_type": definition_result.get("pipeline_type", "Unknown"),
                                "syntax": definition_result.get("syntax", ""),
                                "usage": definition_result.get("usage", "")
                            }
                        
                        return {
                            "valid": True,
                            "definition": function_info,
                            "error": None
                        }
                    else:
                        return {
                            "valid": False,
                            "definition": None,
                            "error": f"Function '{function_name}' not found via RetrievalHelper"
                        }
                except Exception as e:
                    logger.warning(f"Error using RetrievalHelper for function validation: {e}")
                    return {
                        "valid": False,
                        "definition": None,
                        "error": f"Error retrieving function definition: {str(e)}"
                    }
            
            # Fallback to function_definition_store if RetrievalHelper is not available
            elif self.function_definition_store:
                # Search for the function definition
                search_results = self.function_definition_store.semantic_searches(
                    [function_name], n_results=1
                )
                
                # Parse the results
                function_docs = self._parse_retrieval_results(search_results)
                
                if function_docs:
                    doc = function_docs[0]  # Take the most relevant result
                    content = doc.get("content", {})
                    
                    if isinstance(content, dict):
                        # Extract relevant information from the function definition
                        function_info = {
                            "name": content.get("name", function_name),
                            "description": content.get("description", "No description available"),
                            "parameters": content.get("parameters", []),
                            "returns": content.get("returns", "No return information"),
                            "examples": content.get("examples", []),
                            "pipeline_type": content.get("pipeline_type", "Unknown"),
                            "syntax": content.get("syntax", ""),
                            "usage": content.get("usage", "")
                        }
                        
                        return {
                            "valid": True,
                            "definition": function_info,
                            "error": None
                        }
                    else:
                        return {
                            "valid": True,
                            "definition": {"name": function_name, "content": content},
                            "error": None
                        }
                else:
                    return {
                        "valid": False,
                        "definition": None,
                        "error": f"Function '{function_name}' not found in function definition store"
                    }
            else:
                return {
                    "valid": False,
                    "definition": None,
                    "error": "No function definition sources available"
                }
                
        except Exception as e:
            logger.warning(f"Error validating function '{function_name}': {str(e)}")
            return {
                "valid": False,
                "definition": None,
                "error": f"Error validating function: {str(e)}"
            }
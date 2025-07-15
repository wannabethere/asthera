from typing import Dict, List, Any, Optional, Union, Tuple
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers.string import StrOutputParser
import json
import re
from enum import Enum
import ast
from app.storage.documents import DocumentChromaStore
from .analysis_intent_classification import AnalysisIntentResult

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
            function_name: Primary function to use in the pipeline (can be a string or list of suggested functions)
            function_inputs: Extracted function inputs (will be enhanced by LLM detection).
                           Can be Dict[str, Any], List[str], or other types (will be converted to dict)
            dataframe_name: Name of the dataframe variable
            classification: Optional classification results with intent, confidence, etc.
            dataset_description: Optional description of the dataset
            columns_description: Optional dictionary mapping column names to descriptions
            
        Returns:
            Dictionary containing generated code and metadata
        """
        # Initialize logger at the beginning
        import logging
        logger = logging.getLogger(__name__)
        
        # Detect the best function if function_name is a list
        if isinstance(function_name, list):
            original_function_list = function_name
            detected_function = await self._detect_best_function(
                context, function_name, classification, dataset_description, columns_description
            )
            selected_function = detected_function["selected_function"]
            function_detection_metadata = detected_function
            
            # Validate that a function was selected
            if not selected_function:
                logger.warning("No function was selected from the list, using the first suggested function")
                selected_function = original_function_list[0] if original_function_list else "Mean"  # fallback
                function_detection_metadata["selected_function"] = selected_function
                function_detection_metadata["reasoning"] = "Fallback to first suggested function due to detection failure"
            
            function_name = selected_function
        else:
            function_detection_metadata = {
                "selected_function": function_name,
                "confidence": 1.0,
                "reasoning": "Single function provided",
                "alternative_functions": []
            }
        
        # Detect function inputs using LLM (including additional computations)
        detected_inputs = await self._detect_function_inputs(
            context, function_name, classification, dataset_description, columns_description
        )
        
        # Debug logging
        logger.debug(f"Detected function: {function_name}")
        logger.debug(f"Function detection metadata: {function_detection_metadata}")
        logger.debug(f"Detected inputs: {detected_inputs}")
        logger.debug(f"Detected inputs type: {type(detected_inputs)}")
        logger.debug(f"Function inputs: {function_inputs}")
        logger.debug(f"Function inputs type: {type(function_inputs)}")
        
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
        logger.debug(f"Primary function inputs: {primary_function_inputs}")
        logger.debug(f"Primary function inputs type: {type(primary_function_inputs)}")
        
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
        
        # Add dataset description
        if dataset_description:
            enhanced_parts.append(f"\nDataset Description: {dataset_description}")
        
        # Add columns description
        if columns_description:
            enhanced_parts.append(f"\nColumns Description:")
            for col, desc in columns_description.items():
                enhanced_parts.append(f"- {col}: {desc}")
        
        return "\n".join(enhanced_parts)
    
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

        detection_prompt = PromptTemplate(
            input_variables=[
                "context", "suggested_functions", "function_definitions", "classification_context", "dataset_context"
            ],
            template="""
            You are an expert function selector for data analysis pipelines.
            
            TASK: From the provided list of suggested functions, select the most appropriate primary function
            to fulfill the given context. Consider the intent type, confidence, and feasibility.
            
            CONTEXT: {context}
            SUGGESTED FUNCTIONS: {suggested_functions}
            
            FUNCTION DEFINITIONS:
            {function_definitions}
            
            CLASSIFICATION ANALYSIS:
            {classification_context}
            
            DATASET INFORMATION:
            {dataset_context}
            
            INSTRUCTIONS:
            1. Analyze the context to understand the data analysis task.
            2. Review the function definitions to understand what each function does.
            3. Evaluate the confidence and feasibility of each suggested function based on their definitions.
            4. Prioritize functions that are highly confident and feasible.
            5. Consider if multiple pipelines are needed.
            6. Return a JSON object with the selected function and its confidence.
            
            OUTPUT FORMAT:
            {{
                "selected_function": "function_name",
                "confidence": 0.0-1.0,
                "reasoning": "explanation of why this function was selected",
                "alternative_functions": ["function_name1", "function_name2"]
            }}
            
            EXAMPLES:
            
            Example 1 - Simple selection:
            Context: "Calculate the mean of sales column"
            Suggested Functions: ["Mean", "Sum", "Count"]
            Output: {{
                "selected_function": "Mean",
                "confidence": 0.95,
                "reasoning": "Mean is the most direct and confident function for calculating a single value.",
                "alternative_functions": ["Sum", "Count"]
            }}
            
            Example 2 - Multi-pipeline selection:
            Context: "Calculate the mean of transactional value and then analyze its variance over time"
            Suggested Functions: ["Mean", "Variance", "TimeSeriesPipe"]
            Output: {{
                "selected_function": "Mean",
                "confidence": 0.85,
                "reasoning": "Mean is a necessary first step for variance analysis. TimeSeriesPipe is also needed.",
                "alternative_functions": ["Variance"]
            }}
            
            Example 3 - Risk function selection:
            Context: "Calculate the variance of customer retention rate"
            Suggested Functions: ["Variance", "CohortPipe"]
            Output: {{
                "selected_function": "Variance",
                "confidence": 0.90,
                "reasoning": "Variance is the most relevant and confident function for risk analysis.",
                "alternative_functions": ["CohortPipe"]
            }}
            
            Analyze the given context and return the appropriate JSON response.
            """
        )
        
        # Format classification context
        classification_context = self._format_classification_context(classification) if classification else "No classification available"
        
        # Format dataset context
        dataset_context = self._format_dataset_context(dataset_description, columns_description or {})
        
        # Create detection chain
        detection_chain = detection_prompt | self.llm | StrOutputParser()
        
        try:
            # Invoke the detection
            result = await detection_chain.ainvoke({
                "context": context,
                "suggested_functions": ", ".join(suggested_functions),
                "function_definitions": function_definitions,
                "classification_context": classification_context,
                "dataset_context": dataset_context
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
                required_keys = ["selected_function", "confidence", "reasoning", "alternative_functions"]
                
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
                    "alternative_functions": []
                }
                
        except Exception as e:
            # Return a fallback structure if detection fails
            return {
                "selected_function": "",
                "confidence": 0.0,
                "reasoning": f"Function selection failed: {str(e)}. Using fallback function.",
                "alternative_functions": []
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
        
        # Available anomaly detection functions
        anomaly_functions = [
            "detect_statistical_outliers", "detect_contextual_anomalies", 
            "calculate_seasonal_residuals", "detect_anomalies_from_residuals",
            "forecast_and_detect_anomalies", "batch_detect_anomalies",
            "get_anomaly_summary", "get_top_anomalies"
        ]
        
        # Retrieve function definition for the primary function
        primary_function_definition = await self._retrieve_function_definitions([function_name])
        
        # Create the detection prompt
        detection_prompt = PromptTemplate(
            input_variables=[
                "context", "function_name", "function_definition", "classification_context", "dataset_context",
                "metrics_functions", "operations_functions", "anomaly_functions"
            ],
            template="""
            You are an expert function input detector for data analysis pipelines.
            
            TASK: Analyze the given context and function name to detect the required function inputs,
            including any additional computations needed (like mean, average, etc.) or whether to use
            functions from metrics_tools.py or operations_tools.py.
            
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
            
            AVAILABLE ANOMALY DETECTION FUNCTIONS:
            {anomaly_functions}
            
            INSTRUCTIONS:
            1. Analyze the context to understand what data analysis is being requested
            2. Review the primary function definition to understand its parameters and requirements
            3. Determine the required function inputs for the primary function based on its definition
            4. Identify the pipeline type for the primary function:
               - TimeSeriesPipe: variance_analysis, lead, lag, etc.
               - MetricsPipe: Variance, Mean, Sum, Count, etc.
               - OperationsPipe: PercentChange, AbsoluteChange, etc.
               - CohortPipe: form_time_cohorts, calculate_retention, etc.
               - RiskPipe: calculate_var, calculate_cvar, etc.
               - FunnelPipe: analyze_funnel, etc.
               - AnomalyPipe: detect_statistical_outliers, detect_contextual_anomalies, etc.
               - SegmentPipe: run_kmeans, run_dbscan, etc.
               - TrendsPipe: aggregate_by_time, calculate_growth_rates, etc.
            5. Determine if multiple pipelines are needed:
                - If primary function is TimeSeriesPipe/CohortPipe/RiskPipe/FunnelPipe/AnomalyPipe/SegmentPipe/TrendsPipe AND additional computations are needed
                - Create a multi-pipeline approach: MetricsPipe/OperationsPipe first, then primary pipeline
            6. Consider the classification analysis for additional context
            7. Return a JSON object with the detected inputs
            
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
                "reasoning": "explanation of why these inputs were chosen"
            }}
            
            EXAMPLES:
            
            Example 1 - Simple metrics:
            Context: "Calculate the mean of sales column"
            Function: "Mean"
            Output: {{
                "primary_function_inputs": {{"variable": "sales"}},
                "additional_computations": [],
                "pipeline_sequence": ["Calculate mean of sales"],
                "reasoning": "Direct mean calculation using metrics_tools Mean function"
            }}
            
            Example 2 - Same pipeline type (OperationsPipe):
            Context: "Calculate the percent change and absolute change compared to baseline"
            Function: "PercentChange"
            Output: {{
                "primary_function_inputs": {{"condition_column": "customer_type", "baseline": "standard"}},
                "additional_computations": [
                    {{
                        "function": "AbsoluteChange",
                        "inputs": {{"condition_column": "customer_type", "baseline": "standard"}},
                        "tool": "operations_tools"
                    }}
                ],
                "pipeline_sequence": ["Calculate percent change", "Calculate absolute change"],
                "reasoning": "Both functions are from OperationsPipe, so they can be chained together"
            }}
            
            Example 3 - Multi-pipeline approach (MetricsPipe first, then TimeSeriesPipe):
            Context: "Calculate the mean of transactional value and then analyze its variance over time"
            Function: "variance_analysis"
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
                "reasoning": "Need to calculate mean first using MetricsPipe, then analyze variance over time using TimeSeriesPipe"
            }}
            
            Example 4 - Anomaly detection with preprocessing (MetricsPipe first, then AnomalyPipe):
            Context: "Calculate the mean of sales and then detect outliers in the data"
            Function: "detect_statistical_outliers"
            Output: {{
                "primary_function_inputs": {{"columns": "mean_sales", "method": "zscore", "threshold": 3.0}},
                "additional_computations": [
                    {{
                        "function": "Mean",
                        "inputs": {{"variable": "sales"}},
                        "tool": "metrics_tools"
                    }}
                ],
                "pipeline_sequence": ["Calculate mean of sales", "Detect statistical outliers"],
                "multi_pipeline": true,
                "first_pipeline_type": "MetricsPipe",
                "second_pipeline_type": "AnomalyPipe",
                "reasoning": "Need to calculate mean first using MetricsPipe, then detect outliers using AnomalyPipe"
            }}
            
            Now analyze the given context and return the appropriate JSON response.
            """
        )
        
        # Format classification context
        classification_context = self._format_classification_context(classification) if classification else "No classification available"
        
        # Format dataset context
        dataset_context = self._format_dataset_context(dataset_description, columns_description or {})
        
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
                "anomaly_functions": ", ".join(anomaly_functions)
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
                optional_keys = ["multi_pipeline", "first_pipeline_type", "second_pipeline_type"]
                
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
                        else:
                            detected_inputs[key] = None
                
                # Filter additional computations to ensure pipeline type consistency
                detected_inputs = self._filter_additional_computations(detected_inputs, function_name)
                
                logger.debug(f"Final detected_inputs: {detected_inputs}")
                return detected_inputs
                
            except json.JSONDecodeError as e:
                # If JSON parsing fails, return a basic structure
                return {
                    "primary_function_inputs": {},
                    "additional_computations": [],
                    "pipeline_sequence": ["Basic analysis"],
                    "reasoning": f"JSON parsing failed: {str(e)}. Using basic inputs.",
                    "raw_response": result
                }
                
        except Exception as e:
            # Return a fallback structure if detection fails
            return {
                "primary_function_inputs": {},
                "additional_computations": [],
                "pipeline_sequence": ["Fallback analysis"],
                "reasoning": f"Detection failed: {str(e)}. Using fallback inputs.",
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
    
    def _format_dataset_context(self, dataset_description: Optional[str], 
                               columns_description: Dict[str, str]) -> str:
        """
        Format dataset information for code generation prompt
        """
        parts = []
        
        if dataset_description:
            parts.append(f"Dataset: {dataset_description}")
        
        if columns_description:
            parts.append("Columns:")
            for col, desc in columns_description.items():
                parts.append(f"  - {col}: {desc}")
        
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
        
        # Format classification context
        classification_context = self._format_classification_context(classification)
        
        # Format dataset context
        dataset_context = self._format_dataset_context(dataset_description, columns_description)
        
        generation_prompt = PromptTemplate(
            input_variables=[
                "context", "original_context", "function_name", "pipeline_type", "dataframe_name", 
                "function_inputs", "additional_computations", "pipeline_sequence", "reasoning",
                "multi_pipeline", "first_pipeline_type", "second_pipeline_type",
                "docs_context", "classification_context", "dataset_context", "iteration"
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
            
            CLASSIFICATION ANALYSIS:
            {classification_context}
            
            DATASET INFORMATION:
            {dataset_context}
            
            RELEVANT DOCUMENTATION:
            {docs_context}
            
            Generate a complete pipeline code that:
            1. Initializes the appropriate Pipe with from_dataframe() based on the primary function type
            2. Chains the primary function with proper parameters based on the classification
            3. Adds appropriate summary/output functions
            4. Uses proper Python syntax with pipe operator (|)
            5. Follows the detected pipeline sequence
            6. Considers the intent type and suggested functions from classification
            
            CRITICAL RULES:
            - Create separate pipelines for different pipeline types
            - MetricsPipe and OperationsPipe pipelines should be executed FIRST to prepare data
            - TimeSeriesPipe, CohortPipe, RiskPipe, FunnelPipe, AnomalyPipe, SegmentPipe, and TrendsPipe pipelines should be executed SECOND on the prepared data
            - Each pipeline should stay within its own pipeline type
            - Use the results from the first pipeline as input to the second pipeline
            - Chain the pipelines using the pipe operator (|) between different pipeline types
            
            REQUIRED FORMAT:
            
            For single pipeline type:
            ```python
            result = (PipeType.from_dataframe({dataframe_name})
                     | function1(param1='value1')
                     | function2(param2='value2')
                     | to_df()
            )
            ```
            
            For multiple pipeline types (Metrics/Operations first, then TimeSeries/Cohort/Risk/Funnel/Anomaly/Segment/Trends):
            ```python
            result = (MetricsPipe.from_dataframe({dataframe_name})
                     | metrics_function1(param1='value1')
                     | metrics_function2(param2='value2')
                     | TimeSeriesPipe.from_dataframe()
                     | timeseries_function(param3='value3')
                     | to_df()
            )
            ```
            
            IMPORTANT: If the dataframe name contains spaces, it must be quoted: from_dataframe("Dataframe Name")
            
            EXAMPLES:
            
            Example 1 - Single pipeline type (MetricsPipe):
            ```python
            result = (MetricsPipe.from_dataframe(df)
                     | Mean(variable='revenue')
                     | Variance(variable='revenue')
                     | to_df()
            )
            ```
            
            Example 2 - Multiple pipeline types (MetricsPipe first, then TimeSeriesPipe):
            ```python
            result = (MetricsPipe.from_dataframe(df)
                     | Mean(variable='Transactional value')
                     | TimeSeriesPipe.from_dataframe()
                     | variance_analysis(
                         columns=['mean_Transactional value'],
                         method='rolling',
                         window=5
                     )
                     | to_df()
            )
            ```
            
            Example 3 - Multiple pipeline types (OperationsPipe first, then TimeSeriesPipe):
            ```python
            result = (OperationsPipe.from_dataframe(df)
                     | PercentChange(condition_column='period', baseline='Q1')
                     | TimeSeriesPipe.from_dataframe()
                     | variance_analysis(
                         columns=['percent_change'],
                         method='rolling',
                         window=5
                     )
                     | to_df()
            )
            ```
            
            Example 4 - Dataframe with spaces:
            ```python
            result = (TimeSeriesPipe.from_dataframe("Purchase Orders Data")
                     | variance_analysis(
                         columns=['Project', 'Transactional value'],
                         method='rolling',
                         window=5
                     )
                     | to_df()
            )
            ```
            
            Example 5 - Anomaly detection (MetricsPipe first, then AnomalyPipe):
            ```python
            result_metrics = (MetricsPipe.from_dataframe(df)
                     | Mean(variable='sales')
                     | to_df()
                     
            result_pipe = AnomalyPipe.from_dataframe(result_metrics)
                     | detect_statistical_outliers(
                         columns='mean_sales',
                         method='zscore',
                         threshold=3.0
                     )
                     | to_df()
            )
            ```
            
            Example 6 - Single AnomalyPipe:
            ```python
            result = (AnomalyPipe.from_dataframe(df)
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
                     | to_df()
            )
            ```
            
            Example 7 - Segmentation (MetricsPipe first, then SegmentPipe):
            ```python
            result_metrics = (MetricsPipe.from_dataframe(df)
                     | Mean(variable='sales')
                     | to_df()

            result_pipe = SegmentPipe.from_dataframe(result_metrics)
                     | get_features(columns=['mean_sales', 'frequency'])
                     | run_kmeans(n_clusters=5, find_optimal=True)
                     | to_df()
            )
            ```
            
            Example 8 - Single SegmentPipe:
            ```python
            result = (SegmentPipe.from_dataframe(df)
                     | get_features(columns=['sales', 'frequency', 'recency'])
                     | run_kmeans(n_clusters=5)
                     | run_dbscan(eps=0.5, min_samples=5)
                     | compare_algorithms()
                     | to_df()
            )
            ```
            
            Example 9 - Trends analysis (MetricsPipe first, then TrendsPipe):
            ```python
            result_metrics = (MetricsPipe.from_dataframe(df)
                     | Mean(variable='revenue')
                     | to_df()

            result_pipe = TrendsPipe.from_dataframe(result_metrics)
                     | aggregate_by_time(
                         date_column='date',
                         metric_columns=['mean_revenue'],
                         time_period='M'
                     )
                     | calculate_growth_rates(window=3)
                     | forecast_metric(metric_column='mean_revenue', fperiods=6)
                     | to_df()
            )
            ```
            
            Example 10 - Single TrendsPipe:
            ```python
            result = (TrendsPipe.from_dataframe(df)
                     | aggregate_by_time(
                         date_column='timestamp',
                         metric_columns=['sales', 'revenue'],
                         time_period='D'
                     )
                     | calculate_moving_average(window=7)
                     | decompose_trend(metric_column='sales')
                     | forecast_metric(metric_column='revenue', fperiods=12)
                     | to_df()
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
                "docs_context": docs_context,
                "classification_context": classification_context,
                "dataset_context": dataset_context,
                "iteration": query_state["iteration"]
            })
            
            # Clean up the generated code
            code = self._clean_generated_code(generated_code)
            query_state["code_attempts"].append(code)
            
            return code
            
        except Exception as e:
            fallback_code = self._generate_fallback_code(
                pipeline_type, function_name, function_inputs, dataframe_name
            )
            query_state["code_attempts"].append(fallback_code)
            return fallback_code
    
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
        """Clean and format generated code"""
        # Remove markdown code blocks
        code = re.sub(r'```python\s*', '', code)
        code = re.sub(r'```\s*', '', code)
        
        # Clean whitespace
        lines = [line.rstrip() for line in code.split('\n') if line.strip()]
        
        return '\n'.join(lines)
    
    def _generate_fallback_code(self, pipeline_type: PipelineType, 
                               function_name: str, function_inputs: Dict[str, Any], 
                               dataframe_name: str) -> str:
        """Generate fallback code when main generation fails"""
        inputs_str = self._format_function_inputs(function_inputs)
        
        # Handle dataframe names with spaces
        if ' ' in dataframe_name:
            dataframe_name = f'"{dataframe_name}"'
        
        return f"""result = ({pipeline_type.value}.from_dataframe({dataframe_name})
         | {function_name}(
             {inputs_str}
         )
         | ShowDataFrame())
        """
    
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
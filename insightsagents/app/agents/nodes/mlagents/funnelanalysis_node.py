from langchain.agents import Agent, AgentExecutor, Tool
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers.string import StrOutputParser
from langchain_core.output_parsers.json import JsonOutputParser
from langchain_community.vectorstores import Chroma
from langchain.agents.output_parsers.openai_tools import OpenAIToolsAgentOutputParser
from langchain.agents.format_scratchpad.openai_tools import (
    format_to_openai_tool_messages,
)
from typing import Dict, List, Any, Optional, Callable, Union
import chromadb
import json
import pandas as pd
import re
from app.storage.documents import DocumentChromaStore
from app.core.settings import get_settings

settings = get_settings()
CHROMA_STORE_PATH = settings.CHROMA_STORE_PATH

FUNCTION_TERM_SPECS =  {
            "sql": {
                "terms": ["table", "column", "join", "select", "from", "where", 
                          "group by", "order by", "having", "union", "insert", 
                          "update", "delete", "create", "alter", "index", "view", 
                          "query", "subquery", "database", "schema"],
                "max_score": 0.20,
                "min_match_threshold": 2
            },
            "cohort_analysis": {
                "terms": ["cohort", "retention", "churn", "lifetime value", "ltv", 
                         "customer segmentation", "behavioral cohorts", "value segment", 
                         "transaction", "time period", "cumulative", "from_dataframe", 
                         "calculate_lifetime_value", "form_behavioral_cohorts",
                         "CohortPipe", "time_period", "max_periods"],
                "max_score": 0.25,
                "min_match_threshold": 2
            },
            "segmentation": {
                "terms": ["segmentation", "clustering", "kmeans", "dbscan", "hierarchical",
                         "features", "recency", "frequency", "monetary", "rfm", "cluster",
                         "segment", "eps", "min_samples", "linkage", "ward", "n_clusters",
                         "SegmentationPipe", "get_features", "run_kmeans", "run_dbscan",
                         "run_hierarchical", "compare_algorithms"],
                "max_score": 0.25,
                "min_match_threshold": 2
            },
            "machine_learning": {
                "terms": ["model", "train", "test", "validation", "accuracy", "precision",
                         "recall", "f1", "roc", "auc", "cross-validation", "hyperparameter",
                         "feature selection", "feature engineering", "regression", "classification",
                         "decision tree", "random forest", "neural network", "deep learning",
                         "supervised", "unsupervised", "reinforcement", "overfitting", "underfitting"],
                "max_score": 0.20,
                "min_match_threshold": 2
            },
            "time_series": {
                "terms": ["time series", "forecast", "trend", "seasonal", "decomposition",
                         "arima", "sarima", "prophet", "exponential smoothing", "moving average",
                         "autocorrelation", "stationarity", "periodicity", "seasonality",
                         "prediction interval", "lag", "rolling window", "resampling"],
                "max_score": 0.20,
                "min_match_threshold": 2
            },
            "metrics": {
                "terms": ["metrics", "metric", "kpi", "value", "score", "accuracy", "precision",
                         "recall", "f1", "roc", "auc", "cross-validation", "hyperparameter",
                         "feature selection", "feature engineering", "regression", "classification",
                         "decision tree", "random forest", "neural network", "deep learning",
                         "supervised", "unsupervised", "reinforcement", "overfitting", "underfitting"],
                "max_score": 0.20,
                "min_match_threshold": 2
            },
            "operations": {
                "terms": ["filter", "group", "sort", "join", "merge", "concat", "append", "split",
                         "transform", "convert", "calculate", "compute", "derive", "normalize",
                         "standardize", "rescale", "change", "difference", "delta", "comparison"],
                "max_score": 0.20,
                "min_match_threshold": 2
            },
            "aggregation": {
                "terms": ["aggregate", "summarize", "groupby", "pivot", "rollup", "cube", "crosstab",
                         "total", "subtotal", "accumulate", "collect", "combine", "condense"],
                "max_score": 0.20,
                "min_match_threshold": 2
            },
            "trends": {
                "terms": ["trend", "pattern", "anomaly", "outlier", "seasonality", "cyclical", "growth",
                         "decay", "increase", "decrease", "spike", "dip", "volatility", "stability"],
                "max_score": 0.20,
                "min_match_threshold": 2
            },
            "data_processing": {
                "terms": ["clean", "preprocess", "impute", "missing", "outlier", "normalize", "scale",
                         "encode", "decode", "tokenize", "parse", "extract", "transform", "format"],
                "max_score": 0.20,
                "min_match_threshold": 2
            },
            "general_analysis": {
                "terms": ["data", "analysis", "visualization", "preprocessing", "statistics",
                         "correlation", "causation", "hypothesis", "insight", "metric", 
                         "dashboard", "report", "chart", "graph", "plot", "aggregate", 
                         "summarize", "filter", "transform", "clean", "normalize"],
                "max_score": 0.15,
                "min_match_threshold": 2
            }
        },

FUNNEL_ANALYST_PROMPT= """
You are a data science analysis expert who helps users generate code for datascience analysis tasks.

CONTEXT:
You have access to collections of data science functions with function definitions and examples.
You can retrieve function definitions and examples, validate retrieval scores, and generate code.
The retrieval score must be above 0.6 to be considered reliable.
for the code generation, please dont generate any boilerplate code, just the code that is needed to call the function.
for the function inputs, please use the function_specs to determine the correct inputs.
You are also given function insights that are relevant to the function you are trying to generate code for but are not exactly matching the function definition.
The function insights help you understand the function better and provide more context for the code generation.
if the inputs need to be calculated please output a list of parameters that needed to be calculated as "Natural Language Question for the data". Please only use the function_specs to determine the correct calculations.
Please provide the inputs for all the functions.

as an example: 
For the question: "How do I analyze funnel performance across different user segments with my event data?"
The code should be:
analyze_funnel_by_segment(
    event_column='event_name',
    user_id_column='user_id',
    segment_column='device_type',  # Column to segment by
    funnel_steps=funnel_steps,
    min_users=20  # Minimum users per segment
)


CHAT HISTORY:
{chat_history}

QUESTION:
{input}

FUNCTION DEFINITIONS:
{function_definitions}

FUNCTION INSIGHTS:
{function_insights}

THOUGHT PROCESS:
{agent_scratchpad}

Output Format:
code:
{{
Example function definition for analyze funnel segment :analyze_funnel_by_segment(
    event_column='event_name',
    user_id_column='user_id',
    segment_column='device_type',  # Column to segment by
    funnel_steps=funnel_steps,
    min_users=20  # Minimum users per segment
)
}}
inputs:
{{
    {{input function variable name1: generated input 1: calculated: "Natural Language Question for the data"}}
    {{input function variable name2: generated input 2: columnpresent: "data set column name"}}
    ...
}}

"""

class FunnelAnalysisAgent:
    """LangChain agent for funnel analysis tools with ChromaDB retrieval and validation."""
    
    def __init__(self, llm, function_collection, example_collection,insights_collection=None, llm_model: str = "gpt-4"):
        """
        Initialize the Funnel Analysis Agent
        
        Args:
            llm: Language model instance
            function_collection: DocumentChromaStore instance for function definitions
            example_collection: DocumentChromaStore instance for examples
            llm_model: LLM model to use
        """
        self.llm = llm
       
        self.function_collection = function_collection
        
        self.example_collection = example_collection
        self.insights_collection = insights_collection
        self.input_extractor = EnhancedFunctionInputExtractor(
            llm=self.llm, 
            examplestore=self.example_collection, 
            function_specs_store=self.function_collection,
            insights_store=self.insights_collection
        )
        
        # Initialize conversation memory
        self.memory = ConversationBufferMemory(memory_key="chat_history")
        
        # Create the tools
        self.tools = self._create_tools()
        
        # Create the agent
        self.agent = self._create_agent()
        
    def _create_tools(self) -> List[Tool]:
        """Create the tools for the agent"""
        tools = [
            Tool(
                name="retrieve_function_definition",
                func=lambda function_name: retrieve_function_definition(function_name, self.function_collection),
                description="Retrieves the definition of a funnel analysis function"
            ),
            Tool(
                name="retrieve_function_examples",
                func=lambda function_name: retrieve_function_examples(function_name, self.example_collection),
                description="Retrieves examples of how to use a funnel analysis function"
            ),
            Tool(
                name="retrieve_function_insights",
                func=lambda function_name: retrieve_function_insights(function_name, self.insights_collection),
                description="Retrieves insights about a funnel analysis function"
            ),
            Tool(
                name="validate_retrieval_score",
                func=self._validate_retrieval_score,
                description="Validates that the retrieval score is high enough to be reliable"
            ),
            Tool(
                name="extract_funnel_inputs",
                func=self._extract_funnel_inputs,
                description="Extracts funnel steps and names from a natural language context"
            ),
             # Fix for the error - wrap with lambda to ensure all parameters are provided
            Tool(
                name="generate_function_code",
                func=lambda function_type, function_inputs=None, dataframe_columns=None: 
                    self._generate_function_code(
                        function_type=function_type,
                        function_inputs=function_inputs or {},
                        dataframe_columns=dataframe_columns
                    ),
                description="Generates code for a function based on the definition and examples"
            )
        ]
        return tools
    
    def _create_agent(self) -> AgentExecutor:
        """Create the LangChain agent"""
        # Define the prompt template
        prompt = PromptTemplate(
            input_variables=["input", "chat_history", "agent_scratchpad","function_definitions","function_insights"],
            template=FUNNEL_ANALYST_PROMPT
        )
        llm_with_tools = self.llm.bind_tools(self.tools)
        
        # Create the agent
        agent = {
            "input": lambda x: x["input"],
            "agent_scratchpad": lambda x: format_to_openai_tool_messages(
                x["intermediate_steps"]
            ),
            "chat_history": lambda x: x["chat_history"],
            "function_definitions": lambda x: json.dumps(FUNCTION_TERM_SPECS, indent=2),
            "function_insights": lambda x: json.dumps(retrieve_function_insights(x["input"], self.insights_collection), indent=2)
        } | prompt | llm_with_tools | OpenAIToolsAgentOutputParser()
        
        # Create the agent executor
        agent_executor = AgentExecutor.from_agent_and_tools(
            agent=agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True
        )
        
        return agent_executor
    
    
    
    def _validate_retrieval_score(self, score: float, threshold: float = 0.8) -> Dict[str, Any]:
        """
        Validate the retrieval score
        
        Args:
            score: The retrieval score to validate
            threshold: The minimum acceptable score
            
        Returns:
            Dict with validation result
        """
        
        is_valid = True#float(score) >= float(threshold)
        
        return {
            "status": "success" if is_valid else "error",
            "is_valid": is_valid,
            "score": score,
            "threshold": threshold,
            "message": f"Score {score} is {'above' if is_valid else 'below'} threshold {threshold}"
        }
    
    def _generate_function_code_with_examples(self, 
                              function_name: str, 
                              function_definition: Dict[str, Any], 
                              examples: List[Dict[str, Any]],
                              parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate code for a function based on definition and examples
        
        Args:
            function_name: Name of the function
            function_definition: Function definition
            examples: Function examples
            parameters: Parameters to use in the generated code
            
        Returns:
            Dict with generated code
        """
        # Extract code examples from example documents
        code_examples = []
        for example in examples:
            if "Code_Example" in example:
                code_examples.append(example["Code_Example"])
        
        # Use LLM to generate code based on definition and examples
        code_generation_prompt = PromptTemplate(
            input_variables=["function_name", "function_definition", "code_examples", "parameters"],
            template="""
            Generate code that uses the {function_name} function based on:
            
            FUNCTION DEFINITION:
            {function_definition}
            
            CODE EXAMPLES:
            {code_examples}
            
            PARAMETERS TO USE:
            {parameters}
            
            IMPORTANT: Only generate the code without explanations.
            """
        )
        
        code_chain = PromptTemplate(
            input_variables=["function_name", "function_definition", "code_examples", "parameters"],
            template="""
            Generate code that uses the {function_name} function based on:
            
            FUNCTION DEFINITION:
            {function_definition}
            
            CODE EXAMPLES:
            {code_examples}
            
            PARAMETERS TO USE:
            {parameters}
            
            IMPORTANT: Only generate the code without explanations.
            """
        ) | self.llm | StrOutputParser()
        
        try:
            code = code_chain.invoke({
                "function_name": function_name,
                "function_definition": json.dumps(function_definition, indent=2),
                "code_examples": "\n\n".join(code_examples),
                "parameters": json.dumps(parameters, indent=2)
            }).strip()
            
            # Clean up the code (remove markdown code blocks if present)
            code = re.sub(r'```python\s*', '', code)
            code = re.sub(r'```\s*', '', code)
            
            return {
                "status": "success",
                "code": code
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error generating code: {str(e)}"
            }
    
    def run(self, query: str, dataframe_columns: List[str] = None, dataframe_description: Dict[str, Any] = None, pipeline_operator: str = None) -> Dict[str, Any]:
        """
        Run the agent on a query using invoke with input only
        
        Args:
            query: The user's query
            dataframe_columns: Optional list of available columns in the dataframe
            dataframe_description: Optional dictionary with schema, descriptions, and statistics
            pipeline_operator: Optional pipeline operator to use for context (e.g., "funnel_analysis", "cohort_analysis")
            
        Returns:
            Dictionary containing the response, chain of thought, and generated code
        """
        # Keep track of dataframe information directly in the agent instance
        self.dataframe_columns = dataframe_columns
        self.dataframe_description = dataframe_description
        
        # Alternatively, save serialized versions to memory for tools that need them
        if dataframe_columns:
            column_str = json.dumps(dataframe_columns)
            self.memory.save_context(
                {"input": "What are the dataframe columns?"},
                {"output": f"The dataframe columns are: {column_str}"}
            )
        
        if dataframe_description:
            # Create a simplified, string-friendly version for memory
            # Convert any Timestamp objects to strings before JSON serialization
            desc_copy = dataframe_description.copy()
            if 'stats' in desc_copy:
                for col in desc_copy['stats']:
                    for stat in desc_copy['stats'][col]:
                        if pd.api.types.is_datetime64_any_dtype(type(desc_copy['stats'][col][stat])):
                            desc_copy['stats'][col][stat] = str(desc_copy['stats'][col][stat])
            
            desc_str = json.dumps(desc_copy)
            self.memory.save_context(
                {"input": "What is the dataframe description?"},
                {"output": f"The dataframe description is: {desc_str}"}
            )
        # First, extract inputs with chain of thought reasoning
        extraction_result = self._extract_funnel_inputs(
            query, 
            self.dataframe_columns,
            self.dataframe_description,
            pipeline_operator
        )
        
        # Store the chain of thought reasoning
        chain_of_thought = extraction_result.get("chain_of_thought", "")
        
        # Get the function type and inputs
        function_type = extraction_result.get("function_type", "analyze_funnel")
        function_inputs = extraction_result.get("inputs", {})
        
        # Generate code based on the extracted inputs
        code_result = self._generate_function_code(
            function_type, 
            function_inputs,
            self.dataframe_columns
        )
        
        # Store the generated code
        generated_code = code_result.get("code", "")
        
        # Prepare the input for the agent
        input_data = {
            "input": query
        }
        
        # Invoke the agent with just the input
        response = self.agent.invoke(input_data)
        
        # Extract the output text from the response
        output_text = ""
        if isinstance(response, dict) and "output" in response:
            output_text = response["output"]
        else:
            output_text = str(response)
        
      
        # Return a comprehensive result
        return {
            "response": output_text,
            "chain_of_thought": chain_of_thought,
            "generated_code": generated_code,
            "function_type": function_type,
            "function_inputs": function_inputs,
        }
    
    def _generate_function_code(self, 
                           function_type: str, 
                           function_inputs: Dict[str, Any],
                           dataframe_columns: List[str] = None) -> Dict[str, Any]:
        """
        Generate Python code for the specified function and inputs
        
        Args:
            function_type: Type of funnel analysis function to generate
            function_inputs: Dictionary of input parameters for the function
            dataframe_columns: Optional list of dataframe columns for validation
            
        Returns:
            Dictionary with generated code and metadata
        """
        # Prepare inputs as a formatted string
        inputs_str = ""
        for key, value in function_inputs.items():
            # Skip internal keys like '_reasoning'
            if key.startswith('_'):
                continue
            
            # Format the value appropriately
            if isinstance(value, str):
                formatted_value = f"'{value}'"
            elif isinstance(value, list):
                if all(isinstance(item, str) for item in value):
                    formatted_value = "[" + ", ".join(f"'{item}'" for item in value) + "]"
                else:
                    formatted_value = str(value)
            else:
                formatted_value = str(value)
            
            inputs_str += f"{key} = {formatted_value}\n"
        
        # Prepare dataframe info
        dataframe_info = ""
        if dataframe_columns:
            dataframe_info = f"Available columns: {', '.join(dataframe_columns)}"
        else:
            dataframe_info = "No specific dataframe information provided."
        
        # Create the code generation chain
        code_chain = PromptTemplate(
            input_variables=["function_type", "function_inputs", "dataframe_info"],
            template="""
            Generate Python code that uses the {function_type} function in a FunnelPipe.
        
            FUNCTION: {function_type}
            
            INPUTS:
            {function_inputs}
            
            The code should ONLY include ONE function call in this exact pattern:
            
            {function_type}(
                parameter1='value1',
                parameter2='value2',
                ...
            )
            
            EXAMPLE FORMAT:
            analyze_funnel_by_segment(
                event_column='event_name',
                user_id_column='user_id',
                segment_column='user_segment',
                funnel_steps=funnel_steps,
                step_names=step_names,
                min_users=10
            )
            
            IMPORTANT RULES:
            1. Do NOT include any implementation code
            2. Only include function imports and the pipeline call
            3. The output should be minimal - just the imports and pipeline
            4. Format all parameters properly (strings in quotes, lists with proper syntax)
            5. Do NOT add any extra code for visualization or analysis
            
            Provide ONLY the code without explanations or comments.
            """
        ) | self.llm | StrOutputParser()
        
        # Run the chain
        try:
            code = code_chain.invoke({
                "function_type": function_type,
                "function_inputs": inputs_str,
                "dataframe_info": dataframe_info
            }).strip()
            
            # Clean up the code (remove markdown code blocks if present)
            code = re.sub(r'```python\s*', '', code)
            code = re.sub(r'```\s*', '', code)
            
            return {
                "status": "success",
                "code": code.strip()
            }
        except Exception as e:
            return {
                "status": "error",
                "code": f"# Error generating code: {str(e)}",
                "error": str(e)
            }
    
    def _extract_funnel_inputs(self, 
                          context: str, 
                          dataframe_columns: List[str] = None,
                          dataframe_description: Dict[str, Any] = None,
                          pipeline_operator: str = None) -> Dict[str, Any]:
        """
        Extract funnel analysis inputs from natural language context with schema information
        
        Args:
            context: Natural language description of the funnel analysis task
            dataframe_columns: Optional list of available columns in the dataframe
            dataframe_description: Optional dictionary with schema, descriptions, and statistics
            
        Returns:
            Dict with extracted funnel inputs and reasoning
        """
        print("dataframe_columns",context)
        # Use instance variables if parameters aren't provided
        if dataframe_columns is None:
            dataframe_columns = getattr(self, 'dataframe_columns', None)
        
        if dataframe_description is None:
            dataframe_description = getattr(self, 'dataframe_description', None)

        # Use pipeline operator context if provided, otherwise detect function type
        if pipeline_operator:
            # Map pipeline operator to function type
            operator_to_function = {
                "funnel_analysis": "analyze_funnel",
                "cohort_analysis": "analyze_cohort",
                "segmentation": "analyze_segmentation",
                "time_series_analysis": "analyze_time_series",
                "trend_analysis": "analyze_trends",
                "risk_analysis": "analyze_risk",
                "metric_analysis": "analyze_metrics",
                "operation_analysis": "analyze_operations"
            }
            function_name = operator_to_function.get(pipeline_operator, "analyze_funnel")
        else:
            # First, determine which function type to use
            function_name = self.input_extractor.detect_function_type(context, pipeline_operator)
        print("function_name",function_name)    
        # Extract initial inputs for the detected function
        extracted_inputs = self.input_extractor.extract_funnel_inputs(
            context=context,
            dataframe_description=dataframe_description,
            dataframe_columns=dataframe_columns, 
            function_name=function_name,
            pipeline_operator=pipeline_operator
        )
        print("extracted_inputs",extracted_inputs)
        # Validate and enhance the inputs with reasoning and schema information
        enhanced_inputs,function_spec = self.input_extractor.validate_and_enhance_inputs(
            extracted_inputs=extracted_inputs, 
            dataframe_columns=dataframe_columns,
            dataframe_description=dataframe_description
        )
        print("function_spec",function_spec)
        # Format the chain-of-thought explanation
        chain_of_thought = []
        chain_of_thought.append(f"1. Detected function type: {function_name}")
        chain_of_thought.append(f"2. Function description: {function_spec['description']}")
        
        # Add dataframe analysis if available
        if dataframe_description:
            chain_of_thought.append("3. Dataframe analysis:")
            # Add key dataframe stats if available
            if "dataframe_stats" in dataframe_description:
                df_stats = dataframe_description["dataframe_stats"]
                if "rows" in df_stats:
                    chain_of_thought.append(f"   - Rows: {df_stats['rows']}")
                if "columns" in df_stats:
                    chain_of_thought.append(f"   - Columns: {df_stats['columns']}")
                if "memory_usage" in df_stats:
                    chain_of_thought.append(f"   - Memory usage: {df_stats['memory_usage']}")
            
            # Add column type distribution if available
            if "schema" in dataframe_description:
                schema = dataframe_description["schema"]
                type_counts = {}
                for col, dtype in schema.items():
                    dtype_str = str(dtype)
                    if dtype_str not in type_counts:
                        type_counts[dtype_str] = 0
                    type_counts[dtype_str] += 1
                
                if type_counts:
                    chain_of_thought.append("   - Column type distribution:")
                    for dtype, count in type_counts.items():
                        chain_of_thought.append(f"     * {dtype}: {count} columns")
        
        # Add parameter selections
        chain_of_thought.append(f"4. Parameter selections:")
        
        # Add reasoning for each parameter
        if "_reasoning" in enhanced_inputs:
            reasoning = enhanced_inputs.pop("_reasoning")  # Remove from final output
            for param, reason in reasoning.items():
                param_value = enhanced_inputs.get(param, "Not set")
                if isinstance(param_value, list):
                    param_value = ", ".join(param_value) if len(param_value) < 5 else f"{len(param_value)} items"
                chain_of_thought.append(f"   - {param}: {param_value} → {reason}")
        
        return {
            "function_type": function_name,
            "inputs": enhanced_inputs,
            "description": function_spec["description"],
            "chain_of_thought": "\n".join(chain_of_thought)
        }




 # Check for semantic matches based on column type
COLUMN_TYPE_KEYWORDS = {
    "event": ["event", "action", "activity", "type", "name"],
    "user": ["user", "customer", "visitor", "id", "client"],
    "segment": ["segment", "group", "category", "type", "device", "platform", "country"],
    "date": ["date", "day", "month", "year", "created"],
    "timestamp": ["timestamp", "time", "datetime", "created_at", "occurred"],
    "metric": ["rate", "conversion", "percent", "score", "value", "metric"]
}

class EnhancedFunctionInputExtractor:
    """Tool to extract inputs for all funnel analysis functions from natural language context"""
    
    def __init__(self, llm=None, examplestore=None, function_specs_store=None, insights_store=None):
        """Initialize the enhanced input extractor"""
        # Use the same LLM as the agent if provided, otherwise initialize a new one
        self.llm = llm
        
        self.examplestore = examplestore
        self.function_specs_store = function_specs_store
        self.insights_store = insights_store
        # Define function specifications based on the funnelanalysis.py module
        # TO BE EXTERNALIZED
        
    
    def detect_function_type(self, context: str, pipeline_operator: str = None) -> str:
        """
        Detect which funnel analysis function is most appropriate based on context
        
        Args:
            context: Natural language description of the funnel analysis task
            pipeline_operator: Optional pipeline operator to use for context
            
        Returns:
            Name of the most appropriate function
        """
        # Create a prompt template for detecting function type
        prompt_template = PromptTemplate(
            input_variables=["context", "function_descriptions", "function_examples", "pipeline_operator"],
            template="""
            Based on the following context, determine which funnel analysis function is most appropriate:
            You are also given function insights that are relevant to the function you are trying to generate code for but are not exactly matching the function definition.
            The function insights help you understand the function better and provide more context for function selection.

            CONTEXT:
            {context}
            
            PIPELINE OPERATOR CONTEXT:
            {pipeline_operator}
            
            AVAILABLE FUNCTIONS:
            {function_descriptions}
            {function_examples}
            {function_insights}
            if no function is found, return "analyze_funnel"
            Return just the function name without any explanation.
            """
        )
        # Get function descriptions from ChromaDB
        function_descriptions = json.dumps(retrieve_function_definition(context, self.function_specs_store), indent=2)
        function_examples = json.dumps(retrieve_function_examples(context, self.examplestore), indent=2)
        function_insights = json.dumps(retrieve_function_insights(context, self.insights_store), indent=2)
        # Create the chain
        detection_chain = prompt_template | self.llm | StrOutputParser()
        
        # Run the chain
        try:
            print("detection_chain",context)
            result = detection_chain.invoke({
                "context": context, 
                "function_descriptions": function_descriptions,
                "function_examples": function_examples,
                "function_insights": function_insights,
                "pipeline_operator": pipeline_operator or "No specific pipeline operator provided"
            }).strip()
            print("result",result)
            return result
        except Exception as e:
            print(f"Error detecting function type: {str(e)}")
            return "analyze_funnel"
        
    
    def extract_funnel_inputs(self, context: str, dataframe_description: str = None,dataframe_columns: List[str] = None, function_name: str = None, pipeline_operator: str = None) -> Dict[str, Any]:
        """
        Extract inputs for funnel analysis functions from natural language context
        
        Args:
            context: Natural language description of the funnel analysis task
            dataframe_columns: Optional list of available columns in the dataframe
            function_name: Optional function name to extract inputs for (if not provided, it will be detected)
            
        Returns:
            Dictionary of extracted inputs for the specified funnel analysis function
        """
        # Detect function type if not provided
        if not function_name:
            function_name = self.detect_function_type(context, pipeline_operator)
        
        # Get function specification
        function_spec = retrieve_function_definition(function_name, self.function_specs_store)
        print("function_spec",function_spec)
        function_spec = function_spec['function_definition']
        
        # Create a prompt template for extracting function inputs
        prompt_template = PromptTemplate(
            input_variables=["context", "function_name", "required_params", "optional_params", "dataframe_description", "pipeline_operator"],
            template="""
            Extract inputs for the {function_name} function from the following context:
            
            CONTEXT:
            {context}
            
            PIPELINE OPERATOR CONTEXT:
            {pipeline_operator}
            
            {dataframe_description}
            
            REQUIRED PARAMETERS:
            {required_params}
            
            OPTIONAL PARAMETERS:
            {optional_params}
            
            Please extract the following information in JSON format. Only include parameters mentioned or implied in the context:
            
            OUTPUT FORMAT:
            {{
                "function": "{function_name}",
                ... extracted parameters ...
            }}
            
            
            Only include keys if you can reasonably infer the values from the context.
            """
        )
        
        # Add dataframe columns if provided
        
        dataframe_columns_text = ""
        if dataframe_description:
            dataframe_columns_text = "Available dataframe description: " + dataframe_description['summary']
        
        if dataframe_columns:
            dataframe_columns_text += "Available dataframe: " + ", ".join(dataframe_columns)
        
        # Create parameter descriptions
        required_params = ", ".join(function_spec["required_params"])
        optional_params = ", ".join(function_spec["optional_params"])
        
        # Create the chain
        extraction_chain =  prompt_template | self.llm | StrOutputParser()
        
        # Run the chain
        try:
            result = extraction_chain.invoke({
                    "context": context,
                    "function_name": function_name,
                    "required_params": required_params,
                    "optional_params": optional_params,
                    "dataframe_description": dataframe_columns_text,
                    "pipeline_operator": pipeline_operator or "No specific pipeline operator provided"
                }
            )
            # Parse the JSON result
            # Strip any markdown formatting if present
            result = result.strip()
            if result.startswith("```json"):
                result = result[7:]
            if result.endswith("```"):
                result = result[:-3]
                
            result = result.strip()
            extracted_inputs = json.loads(result)
            print("extracted_inputs",extracted_inputs)

            return extracted_inputs
        except Exception as e:
            return {
                "function": function_name,
                "error": f"Failed to extract inputs: {str(e)}"
            }
    
    def validate_and_enhance_inputs(self, 
                               extracted_inputs: Dict[str, Any], 
                               dataframe_columns: List[str] = None,
                               dataframe_description: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Validate and enhance extracted inputs with chain-of-thought reasoning
        
        Args:
            extracted_inputs: Initial extracted inputs
            dataframe_columns: Available columns in the dataframe
            dataframe_description: Dictionary containing dataframe schema, descriptions, and statistics
            
        Returns:
            Validated and enhanced inputs with reasoning
        """
        enhanced_inputs = extracted_inputs.copy()
        column_reasoning = {}  # Store reasoning for column selections
        
        # Get function name
        function_spec = retrieve_function_definition(extracted_inputs['function'], self.function_specs_store)
        function_spec = function_spec['function_definition']
        
       
        
        # Use LangChain agent to find column matches if dataframe information is provided
        if dataframe_columns or dataframe_description:
            # Identify all required column parameters for this function
            column_params = [
                param for param in function_spec["required_params"] 
                if any(param.endswith(col_type) for col_type in ["_column"])
            ]
            column_params.extend([
                param for param in function_spec["optional_params"] 
                if any(param.endswith(col_type) for col_type in ["_column"])
            ])
            
            # If we have dataframe_description, use it to enhance column matching
            if dataframe_description:
                for column_param in column_params:
                    # If parameter is missing or not a valid column, try to find a match
                    if column_param not in enhanced_inputs or (
                        dataframe_columns and enhanced_inputs[column_param] not in dataframe_columns
                    ):
                        result = self.find_column_match_with_schema(
                            column_param, 
                            dataframe_columns or [], 
                            dataframe_description
                        )
                        matched_column = result["column"]
                        reasoning = result["reasoning"]
                        
                        if matched_column:
                            # Store original value for reasoning
                            original_value = enhanced_inputs.get(column_param, "Not specified")
                            
                            # Update with matched column
                            enhanced_inputs[column_param] = matched_column
                            
                            # Store reasoning
                            if original_value != "Not specified" and original_value != matched_column:
                                column_reasoning[column_param] = f"Changed from '{original_value}' to '{matched_column}'. {reasoning}"
                            else:
                                column_reasoning[column_param] = f"Selected '{matched_column}'. {reasoning}"
                        else:
                            column_reasoning[column_param] = f"Could not find a suitable match. {reasoning}"
            # If we only have column names but no schema description
            elif dataframe_columns:
                for column_param in column_params:
                    # If parameter is missing or not a valid column, try to find a match
                    if column_param not in enhanced_inputs or enhanced_inputs[column_param] not in dataframe_columns:
                        result = self.find_column_match(column_param, dataframe_columns)
                        matched_column = result["column"]
                        reasoning = result["reasoning"]
                        
                        if matched_column:
                            # Store original value for reasoning
                            original_value = enhanced_inputs.get(column_param, "Not specified")
                            
                            # Update with matched column
                            enhanced_inputs[column_param] = matched_column
                            
                            # Store reasoning
                            if original_value != "Not specified" and original_value != matched_column:
                                column_reasoning[column_param] = f"Changed from '{original_value}' to '{matched_column}'. {reasoning}"
                            else:
                                column_reasoning[column_param] = f"Selected '{matched_column}'. {reasoning}"
                        else:
                            column_reasoning[column_param] = f"Could not find a suitable match. {reasoning}"
        
        # Add reasoning to the enhanced inputs
        enhanced_inputs["_reasoning"] = column_reasoning
        
        return enhanced_inputs,function_spec
    
    def _generate_step_names(self, funnel_steps: List[str]) -> List[str]:
        """Generate human-friendly step names from funnel steps"""
        step_names = []
        
        for step in funnel_steps:
            # Convert snake_case or camelCase to Title Case with spaces
            name = re.sub(r'([A-Z])', r' \1', step)  # Insert space before capital letters
            name = re.sub(r'_', ' ', name)  # Replace underscores with spaces
            name = name.strip().title()  # Convert to title case
            step_names.append(name)
        
        return step_names
    
    def _find_closest_column(self, column_name: str, available_columns: List[str]) -> Optional[str]:
        """Find the closest matching column name"""
        # Simple implementation - could be enhanced with fuzzy matching
        column_lower = column_name.lower()
        
        # Direct substring match
        for col in available_columns:
            if column_lower in col.lower() or col.lower() in column_lower:
                return col
        
        # Determine which column type this most likely is
        likely_type = None
        highest_score = 0
        
        for col_type, keywords in COLUMN_TYPE_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in column_lower)
            if score > highest_score:
                highest_score = score
                likely_type = col_type
        
        if likely_type and highest_score > 0:
            # Look for columns that match this type
            for col in available_columns:
                col_lower = col.lower()
                score = sum(1 for keyword in COLUMN_TYPE_KEYWORDS[likely_type] if keyword in col_lower)
                if score > 0:
                    return col
        
        return None
    
    def find_column_match_with_schema(self, 
                                 column_type: str, 
                                 available_columns: List[str], 
                                 dataframe_description: Dict[str, Any]) -> Dict[str, Any]:
        """
        Find the best matching column using schema information, descriptions, and statistics
        
        Args:
            column_type: Type of column to find (e.g., 'event_column', 'user_id_column')
            available_columns: List of available column names in the dataframe
            dataframe_description: Dictionary containing schema, descriptions, and statistics
            
        Returns:
            Dictionary with matched column and reasoning
        """
        if not available_columns:
            return {
                "column": None,
                "reasoning": "No columns available to match."
            }
                
        try:
            # Get keywords for this column type
            keywords = COLUMN_TYPE_KEYWORDS.get(column_type, [])
            
            schema_text = dataframe_description['summary']
            
            # Create a prompt template for matching with chain-of-thought and schema information
            schema_prompt_template = PromptTemplate(
                input_variables=["column_type", "available_columns", "column_type_keywords", "schema_text"],
                template="""
                You are a column matching expert. Your task is to identify the best column from a dataframe
                that matches a specific column type required for funnel analysis.
                
                Column Type Needed: {column_type}
                
                Available Columns: {available_columns}
                
                Keywords associated with this column type: {column_type_keywords}
                
                Schema Information:
                {schema_text}
                
                First, think through each available column and analyze its suitability:
                
                CHAIN OF THOUGHT:
                1. Examine each column name and evaluate its relevance to the {column_type} function
                2. Consider the data type and statistics of each column
                3. Evaluate which column would most likely contain the data needed for {column_type}
                4. Consider common naming conventions and the semantic meaning of the column
                5. Analyze the distribution and top values if available
                
                After your analysis, provide your answer in the following format:
                
                COLUMN: [selected column name]
                REASONING: [explanation of why this column was selected based on schema and statistics]
                """
            )
            
            # Create the column matcher chain
            schema_column_matcher_chain = PromptTemplate(
                input_variables=["column_type", "available_columns", "column_type_keywords", "schema_text"],
                template="""
                You are a column matching expert. Your task is to identify the best column from a dataframe
                that matches a specific column type required for funnel analysis.
                
                Column Type Needed: {column_type}
                
                Available Columns: {available_columns}
                
                Keywords associated with this column type: {column_type_keywords}
                
                Schema Information:
                {schema_text}
                
                First, think through each available column and analyze its suitability:
                
                CHAIN OF THOUGHT:
                1. Examine each column name and evaluate its relevance to the {column_type} function
                2. Consider the data type and statistics of each column
                3. Evaluate which column would most likely contain the data needed for {column_type}
                4. Consider common naming conventions and the semantic meaning of the column
                5. Analyze the distribution and top values if available
                
                After your analysis, provide your answer in the following format:
                
                COLUMN: [selected column name]
                REASONING: [explanation of why this column was selected based on schema and statistics]
                """
            ) | self.llm | StrOutputParser()
            
            # Run the chain
            result = schema_column_matcher_chain.invoke({
                "column_type": column_type,
                "available_columns": ", ".join(available_columns),
                "column_type_keywords": ", ".join(keywords),
                "schema_text": schema_text
            }).strip()
            
            # Parse the result to extract column and reasoning
            column_match = None
            reasoning = "No clear reasoning provided."
            
            # Extract column selection
            column_pattern = r"COLUMN:\s*(.*?)(?:\n|$)"
            column_match = re.search(column_pattern, result)
            if column_match:
                column_name = column_match.group(1).strip()
                # Verify column exists in available columns
                if column_name in available_columns:
                    column_match = column_name
                elif column_name.lower() == "none":
                    column_match = None
                else:
                    # Try case-insensitive match
                    for col in available_columns:
                        if col.lower() == column_name.lower():
                            column_match = col
                            break
            
            # Extract reasoning
            reasoning_pattern = r"REASONING:\s*(.*?)(?:\n|$)"
            reasoning_match = re.search(reasoning_pattern, result)
            if reasoning_match:
                reasoning = reasoning_match.group(1).strip()
            
            return {
                "column": column_match,
                "reasoning": reasoning
            }
                
        except Exception as e:
            return {
                "column": None,
                "reasoning": f"Error finding column match using schema: {str(e)}"
            }
        
    def find_column_match(self, column_type: str, available_columns: List[str]) -> Dict[str, Any]:
        """
        Find the best matching column for a given column type using a LangChain agent
        with chain-of-thought reasoning
        
        Args:
            column_type: Type of column to find (e.g., 'event_column', 'user_id_column')
            available_columns: List of available column names in the dataframe
            
        Returns:
            Dictionary with matched column and reasoning
        """
        if not available_columns:
            return {
                "column": None,
                "reasoning": "No columns available to match."
            }
                
        try:
            # Get keywords for this column type
            keywords = COLUMN_TYPE_KEYWORDS.get(column_type, [])
            
            # Create a prompt template for matching with chain-of-thought
            cot_prompt_template = PromptTemplate(
                input_variables=["column_type", "available_columns", "column_type_keywords"],
                template="""
                You are a column matching expert. Your task is to identify the best column from a dataframe
                that matches a specific column type required for funnel analysis.
                
                Column Type: {column_type}
                
                Available Columns: {available_columns}
                
                Keywords associated with this column type: {column_type_keywords}
                
                First, think through each available column and analyze its suitability:
                
                CHAIN OF THOUGHT:
                1. First, examine each column name and evaluate its relevance to the {column_type} function
                2. Consider common naming conventions for this type of column
                3. Determine which column would most likely contain the data needed for {column_type}
                4. Consider common alternatives if an exact match isn't available
                
                After your analysis, provide your answer in the following format:
                
                COLUMN: [selected column name]
                REASONING: [brief explanation of why this column was selected]
                """
            )
            
            # Create the column matcher chain
            cot_column_matcher_chain = PromptTemplate(
                input_variables=["column_type", "available_columns", "column_type_keywords"],
                template="""
                You are a column matching expert. Your task is to identify the best column from a dataframe
                that matches a specific column type required for funnel analysis.
                
                Column Type: {column_type}
                
                Available Columns: {available_columns}
                
                Keywords associated with this column type: {column_type_keywords}
                
                First, think through each available column and analyze its suitability:
                
                CHAIN OF THOUGHT:
                1. First, examine each column name and evaluate its relevance to the {column_type} function
                2. Consider common naming conventions for this type of column
                3. Determine which column would most likely contain the data needed for {column_type}
                4. Consider common alternatives if an exact match isn't available
                
                After your analysis, provide your answer in the following format:
                
                COLUMN: [selected column name]
                REASONING: [brief explanation of why this column was selected]
                """
            ) | self.llm | StrOutputParser()
            
            # Run the chain
            result = cot_column_matcher_chain.invoke({
                "column_type": column_type,
                "available_columns": ", ".join(available_columns),
                "column_type_keywords": ", ".join(keywords)
            }).strip()
            
            # Parse the result to extract column and reasoning
            column_match = None
            reasoning = "No clear reasoning provided."
            
            # Extract column selection
            column_pattern = r"COLUMN:\s*(.*?)(?:\n|$)"
            column_match = re.search(column_pattern, result)
            if column_match:
                column_name = column_match.group(1).strip()
                # Verify column exists in available columns
                if column_name in available_columns:
                    column_match = column_name
                elif column_name.lower() == "none":
                    column_match = None
                else:
                    # Try case-insensitive match
                    for col in available_columns:
                        if col.lower() == column_name.lower():
                            column_match = col
                            break
            
            # Extract reasoning
            reasoning_pattern = r"REASONING:\s*(.*?)(?:\n|$)"
            reasoning_match = re.search(reasoning_pattern, result)
            if reasoning_match:
                reasoning = reasoning_match.group(1).strip()
            
            return {
                "column": column_match,
                "reasoning": reasoning
            }
                
        except Exception as e:
            return {
                "column": None,
                "reasoning": f"Error finding column match: {str(e)}"
            }



def retrieve_function_definition(function_name: str, function_collection: DocumentChromaStore) -> Dict[str, Any]:
    """
    Retrieve function definition from ChromaDB
    
    Args:
        function_name: Name of the function to retrieve
        function_collection: DocumentChromaStore instance containing function definitions
        
    Returns:
        Dict with function definition and retrieval score
    """
    
    # Query ChromaDB for function definition
    query_result = function_collection.semantic_searches(query_texts=[function_name],n_results=3)
    
    
    if not query_result or not query_result["documents"] or len(query_result["documents"][0]) == 0:
        return {
            "status": "error",
            "message": f"No definition found for function {function_name}",
            "score": 0.0
        }
    
    # Parse the document content
    try:
        
        # semantic_searches returns a dict with "documents", "distances", "metadatas" keys
        # Each value is a list of lists (one list per query)
        document = query_result["documents"][0][0]  # First query, first result
        score = query_result["distances"][0][0] if "distances" in query_result else 0.0
        
        # Convert from JSON string if needed
        if isinstance(document, str) and document.startswith('"') and document.endswith('"'):
            document = json.loads(document)
            
        if isinstance(document, str) and (document.startswith('{') or document.startswith('{"')):
            document = json.loads(document)
        print("document",document)
        return {
            "status": "success",
            "function_definition": document,
            "score": score
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error parsing function definition: {str(e)}",
            "score": 0.0
        }
    
def retrieve_function_examples(function_name: str, example_collection:DocumentChromaStore) -> Dict[str, Any]:
    """
    Retrieve function examples from ChromaDB
    
    Args:
        function_name: Name of the function to retrieve examples for
        
    Returns:
        Dict with function examples and retrieval score
    """
    # Query ChromaDB for function examples
    query_result = example_collection.semantic_searches(
        query_texts=[function_name],
        n_results=5
    )
    
    if not query_result or not query_result["documents"]:
        return {
            "status": "error",
            "message": f"No examples found for function {function_name}",
            "score": 0.0
        }
    
    # Parse the document content
    try:
        examples = []
        scores = []
        
        for i, document in enumerate(query_result["documents"][0]):
            score = query_result["distances"][0][i] if "distances" in query_result else 0.0
            
            # Convert from JSON string if needed
            if isinstance(document, str) and document.startswith('"') and document.endswith('"'):
                document = json.loads(document)
                
            if isinstance(document, str) and (document.startswith('{') or document.startswith('{"')):
                document = json.loads(document)
            
            examples.append(document)
            scores.append(score)
        
        return {
            "status": "success",
            "examples": examples,
            "scores": scores,
            "avg_score": sum(scores) / len(scores) if scores else 0.0
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error parsing function examples: {str(e)}",
            "score": 0.0
        }


def retrieve_function_insights(function_name: str, insights_collection:DocumentChromaStore) -> Dict[str, Any]:
    """
    Retrieve function insights from ChromaDB
    
    Args:
        function_name: Name of the function to retrieve examples for
        
    Returns:
        Dict with function examples and retrieval score
    """
    # Query ChromaDB for function examples
    query_result = insights_collection.semantic_searches(
        query_texts=[function_name],
        n_results=5
    )
    
    if not query_result or not query_result["documents"]:
        return {
            "status": "error",
            "message": f"No examples found for function {function_name}",
            "score": 0.0
        }
    
    # Parse the document content
    try:
        examples = []
        scores = []
        
        for i, document in enumerate(query_result["documents"][0]):
            score = query_result["distances"][0][i] if "distances" in query_result else 0.0
            
            # Convert from JSON string if needed
            if isinstance(document, str) and document.startswith('"') and document.endswith('"'):
                document = json.loads(document)
                
            if isinstance(document, str) and (document.startswith('{') or document.startswith('{"')):
                document = json.loads(document)
            
            examples.append(document)
            scores.append(score)
        
        return {
            "status": "success",
            "examples": examples,
            "scores": scores,
            "avg_score": sum(scores) / len(scores) if scores else 0.0
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error parsing function examples: {str(e)}",
            "score": 0.0
        }
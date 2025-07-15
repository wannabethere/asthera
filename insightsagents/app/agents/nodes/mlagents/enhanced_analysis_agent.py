import json
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers.string import StrOutputParser

@dataclass
class PipelineStep:
    """Represents a single step in the analysis pipeline"""
    step_number: int
    description: str
    operation_type: str
    function_name: Optional[str]
    columns: List[str]
    sql_operation: str
    generated_code: str = ""
    function_inputs: Dict[str, Any] = None
    validation_score: float = 0.0
    function_spec: Dict[str, Any] = None  # Store retrieved function spec


class EnhancedGeneralizedAnalysisAgent:
    """Enhanced agent with improved ChromaDB function retrieval"""
    
    def __init__(self, llm, function_collection, example_collection, insights_collection=None):
        """
        Initialize the Enhanced Generalized Analysis Agent
        
        Args:
            llm: Language model instance
            function_collection: ChromaDB collection for function definitions
            example_collection: ChromaDB collection for examples
            insights_collection: ChromaDB collection for insights
        """
        self.llm = llm
        self.function_collection = function_collection
        self.example_collection = example_collection
        self.insights_collection = insights_collection
        
        # Cache for function specifications to avoid repeated ChromaDB queries
        self.function_spec_cache = {}
        
        # Debug mode for troubleshooting
        self.debug_mode = False

    def enable_debug_mode(self):
        """Enable debug mode for detailed logging"""
        self.debug_mode = True

    def disable_debug_mode(self):
        """Disable debug mode"""
        self.debug_mode = False

    def retrieve_function_spec_from_chromadb(self, function_name: str, retries: int = 3) -> Dict[str, Any]:
        """
        Retrieve function specification from ChromaDB with multiple retrieval strategies
        
        Args:
            function_name: Name of the function to retrieve
            retries: Number of retry attempts with different strategies
            
        Returns:
            Dictionary containing function specification
        """
        # Check cache first
        if function_name in self.function_spec_cache:
            if self.debug_mode:
                print(f"📦 Retrieved {function_name} from cache")
            return self.function_spec_cache[function_name]
        
        function_spec = {}
        retrieval_successful = False
        
        # Strategy 1: Direct semantic search
        if not retrieval_successful and hasattr(self.function_collection, 'query'):
            try:
                if self.debug_mode:
                    print(f"🔍 Strategy 1: ChromaDB query for '{function_name}'")
                
                results = self.function_collection.query(
                    query_texts=[function_name],
                    n_results=1
                )
                
                if results and 'documents' in results and results['documents'][0]:
                    doc_content = results['documents'][0][0]
                    if self.debug_mode:
                        print(f"📄 Raw document content: {doc_content[:200]}...")
                    
                    # Try to parse as JSON
                    function_spec = self._parse_function_spec_document(doc_content, function_name)
                    if function_spec:
                        retrieval_successful = True
                        if self.debug_mode:
                            print(f"✅ Strategy 1 successful for {function_name}")
                
            except Exception as e:
                if self.debug_mode:
                    print(f"❌ Strategy 1 failed: {str(e)}")

        # Strategy 2: Semantic search with alternatives
        if not retrieval_successful and hasattr(self.function_collection, 'semantic_search'):
            try:
                if self.debug_mode:
                    print(f"🔍 Strategy 2: Semantic search for '{function_name}'")
                
                results = self.function_collection.semantic_search(function_name, k=3)
                
                for result in results:
                    if 'content' in result or 'document' in result:
                        content = result.get('content', result.get('document', ''))
                        function_spec = self._parse_function_spec_document(content, function_name)
                        if function_spec:
                            retrieval_successful = True
                            if self.debug_mode:
                                print(f"✅ Strategy 2 successful for {function_name}")
                            break
                
            except Exception as e:
                if self.debug_mode:
                    print(f"❌ Strategy 2 failed: {str(e)}")

        # Strategy 3: Search by category + function name
        if not retrieval_successful:
            try:
                if self.debug_mode:
                    print(f"🔍 Strategy 3: Category-based search for '{function_name}'")
                
                # Try common categories
                categories = ["time_series_analysis", "timeseriesanalysis", "variance", "rolling"]
                
                for category in categories:
                    search_query = f"{category} {function_name}"
                    
                    if hasattr(self.function_collection, 'query'):
                        results = self.function_collection.query(
                            query_texts=[search_query],
                            n_results=2
                        )
                        
                        if results and 'documents' in results and results['documents'][0]:
                            for doc in results['documents'][0]:
                                function_spec = self._parse_function_spec_document(doc, function_name)
                                if function_spec:
                                    retrieval_successful = True
                                    if self.debug_mode:
                                        print(f"✅ Strategy 3 successful with category '{category}'")
                                    break
                    
                    if retrieval_successful:
                        break
                        
            except Exception as e:
                if self.debug_mode:
                    print(f"❌ Strategy 3 failed: {str(e)}")

        # Strategy 4: Fallback to hardcoded specs for known functions
        if not retrieval_successful:
            if self.debug_mode:
                print(f"🔍 Strategy 4: Fallback to hardcoded specs for '{function_name}'")
            
            function_spec = self._get_fallback_function_spec(function_name)
            if function_spec:
                retrieval_successful = True
                if self.debug_mode:
                    print(f"✅ Strategy 4 successful - using fallback spec")

        # Cache successful results
        if retrieval_successful and function_spec:
            self.function_spec_cache[function_name] = function_spec
            if self.debug_mode:
                print(f"💾 Cached function spec for {function_name}")
        
        # Log final result
        if self.debug_mode:
            if retrieval_successful:
                print(f"🎯 Final result for {function_name}: {json.dumps(function_spec, indent=2)}")
            else:
                print(f"❌ Failed to retrieve spec for {function_name}")

        return function_spec if retrieval_successful else {}

    def _parse_function_spec_document(self, content: str, function_name: str) -> Dict[str, Any]:
        """
        Parse function specification from document content
        
        Args:
            content: Raw document content from ChromaDB
            function_name: Name of the function being searched
            
        Returns:
            Parsed function specification or empty dict
        """
        try:
            # Strategy 1: Try direct JSON parsing
            if content.strip().startswith('{'):
                spec = json.loads(content)
                
                # Check if this document contains our function
                if 'functions' in spec and function_name in spec['functions']:
                    return spec['functions'][function_name]
                elif function_name in spec:
                    return spec[function_name]
                elif isinstance(spec, dict) and 'name' in spec and spec['name'] == function_name:
                    return spec
            
            # Strategy 2: Extract JSON from mixed content
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_content = json_match.group(0)
                spec = json.loads(json_content)
                
                if 'functions' in spec and function_name in spec['functions']:
                    return spec['functions'][function_name]
                elif function_name in spec:
                    return spec[function_name]
            
            # Strategy 3: Look for function definitions in text
            if function_name in content:
                # Try to extract structured information using regex
                spec = self._extract_spec_from_text(content, function_name)
                if spec:
                    return spec
                    
        except json.JSONDecodeError as e:
            if self.debug_mode:
                print(f"JSON parsing error: {e}")
        except Exception as e:
            if self.debug_mode:
                print(f"Error parsing document: {e}")
        
        return {}

    def _extract_spec_from_text(self, content: str, function_name: str) -> Dict[str, Any]:
        """
        Extract function specification from unstructured text
        
        Args:
            content: Text content containing function information
            function_name: Name of the function to extract
            
        Returns:
            Extracted function specification
        """
        spec = {"name": function_name}
        
        # Look for parameter information
        param_patterns = [
            r'required_params["\s]*:["\s]*\[(.*?)\]',
            r'optional_params["\s]*:["\s]*\[(.*?)\]',
            r'parameters["\s]*:["\s]*\[(.*?)\]'
        ]
        
        for pattern in param_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                params_str = match.group(1)
                params = [p.strip().strip('"\'') for p in params_str.split(',') if p.strip()]
                
                if 'required' in pattern:
                    spec['required_params'] = params
                elif 'optional' in pattern:
                    spec['optional_params'] = params
                else:
                    spec['parameters'] = params
        
        # Look for description
        desc_patterns = [
            r'description["\s]*:["\s]*"([^"]+)"',
            r'description["\s]*:["\s]*\'([^\']+)\'',
            fr'{function_name}["\s]*:["\s]*"([^"]+)"'
        ]
        
        for pattern in desc_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                spec['description'] = match.group(1)
                break
        
        return spec if len(spec) > 1 else {}

    def _get_fallback_function_spec(self, function_name: str) -> Dict[str, Any]:
        """
        Get fallback function specifications for known functions
        
        Args:
            function_name: Name of the function
            
        Returns:
            Fallback function specification
        """
        fallback_specs = {
            "variance_analysis": {
                "name": "variance_analysis",
                "description": "Calculate variance and standard deviation for time series data",
                "required_params": ["columns"],
                "optional_params": ["method", "window", "time_column", "group_columns", "suffix"],
                "default_values": {
                    "method": "rolling",
                    "window": 30,
                    "suffix": None
                },
                "outputs": {
                    "type": "Callable",
                    "description": "Function that calculates variance in a TimeSeriesPipe"
                }
            },
            "rolling_window": {
                "name": "rolling_window", 
                "description": "Apply rolling window operations to time series data",
                "required_params": ["columns"],
                "optional_params": ["window", "unit", "aggregation", "time_column", "group_columns", "suffix"],
                "default_values": {
                    "window": 5,
                    "unit": "daily",
                    "aggregation": "mean"
                }
            },
            "lag": {
                "name": "lag",
                "description": "Create lag (past) values for specified columns",
                "required_params": ["columns"],
                "optional_params": ["periods", "time_column", "group_columns", "suffix"],
                "default_values": {
                    "periods": 1,
                    "suffix": "_lag"
                }
            },
            "lead": {
                "name": "lead", 
                "description": "Create lead (future) values for specified columns",
                "required_params": ["columns"],
                "optional_params": ["periods", "time_column", "group_columns", "suffix"],
                "default_values": {
                    "periods": 1,
                    "suffix": "_lead"
                }
            }
        }
        
        return fallback_specs.get(function_name, {})

    def generate_function_call_with_spec(self, step: PipelineStep, function_spec: Dict[str, Any], 
                                        dataframe_description: Dict[str, Any] = None) -> str:
        """
        Generate function call code using retrieved function specification
        
        Args:
            step: Pipeline step to generate code for
            function_spec: Retrieved function specification
            dataframe_description: Optional dataframe description
            
        Returns:
            Generated function call code
        """
        if not function_spec:
            return f"# Error: No specification found for function {step.function_name}"
        
        function_name = step.function_name or function_spec.get('name', 'unknown_function')
        
        # Extract parameter information
        required_params = function_spec.get('required_params', [])
        optional_params = function_spec.get('optional_params', [])
        default_values = function_spec.get('default_values', {})
        
        # Generate parameter values using LLM
        param_values = self._generate_parameter_values_with_llm(
            step, function_spec, dataframe_description
        )
        
        # Build the function call
        params = []
        
        # Add required parameters
        for param in required_params:
            if param in param_values:
                value = param_values[param]
                if isinstance(value, str) and not value.startswith('['):
                    params.append(f"{param}='{value}'")
                else:
                    params.append(f"{param}={value}")
            elif param == 'columns' and step.columns:
                # Special handling for columns parameter
                if len(step.columns) == 1:
                    params.append(f"columns='{step.columns[0]}'")
                else:
                    params.append(f"columns={step.columns}")
        
        # Add optional parameters with non-default values
        for param in optional_params:
            if param in param_values and param_values[param] is not None:
                value = param_values[param]
                default_val = default_values.get(param)
                
                # Only include if different from default
                if value != default_val:
                    if isinstance(value, str) and not value.startswith('['):
                        params.append(f"{param}='{value}'")
                    else:
                        params.append(f"{param}={value}")
        
        # Generate the complete function call
        params_str = ",\n    ".join(params)
        
        if params_str:
            function_call = f".{function_name}(\n    {params_str}\n)"
        else:
            function_call = f".{function_name}()"
        
        return function_call

    def _generate_parameter_values_with_llm(self, step: PipelineStep, function_spec: Dict[str, Any],
                                          dataframe_description: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Use LLM to generate appropriate parameter values based on step context and function spec
        
        Args:
            step: Pipeline step
            function_spec: Function specification 
            dataframe_description: Optional dataframe description
            
        Returns:
            Dictionary of parameter values
        """
        # Create prompt for parameter generation
        param_prompt = PromptTemplate(
            input_variables=["step_description", "function_spec", "columns", "operation_type", "dataframe_info"],
            template="""
            You are a data science expert generating parameter values for a function call.
            
            STEP DESCRIPTION: {step_description}
            OPERATION TYPE: {operation_type}
            COLUMNS: {columns}
            
            FUNCTION SPECIFICATION:
            {function_spec}
            
            DATAFRAME INFO:
            {dataframe_info}
            
            Generate appropriate parameter values for this function call based on:
            1. The step description and what it's trying to accomplish
            2. The function specification and its parameters
            3. Common data science best practices
            4. The available columns and data types
            
            SPECIFIC GUIDANCE:
            - For variance_analysis with rolling volatility: use method='rolling', window=30 (or extract window from description)
            - For time series operations: look for time column references
            - For window parameters: extract window size from description (e.g., "30 days" -> window=30)
            - For method parameters: choose based on description context
            
            OUTPUT FORMAT:
            PARAMETERS:
            parameter_name: parameter_value
            parameter_name: parameter_value
            ...
            
            REASONING:
            [Explain why these parameter values were chosen]
            
            IMPORTANT: Only suggest parameters that are in the function specification.
            """
        )
        
        try:
            # Create the parameter generation chain
            param_chain = param_prompt | self.llm | StrOutputParser()
            
            result = param_chain.invoke({
                "step_description": step.description,
                "operation_type": step.operation_type,
                "columns": step.columns,
                "function_spec": json.dumps(function_spec, indent=2),
                "dataframe_info": json.dumps(dataframe_description, indent=2) if dataframe_description else "No dataframe info available"
            })
            
            # Parse the LLM response
            return self._parse_parameter_response(result, function_spec)
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error generating parameters with LLM: {e}")
            return self._generate_default_parameters(step, function_spec)

    def _parse_parameter_response(self, response: str, function_spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse LLM response to extract parameter values
        
        Args:
            response: LLM response text
            function_spec: Function specification for validation
            
        Returns:
            Dictionary of parsed parameter values
        """
        params = {}
        
        try:
            # Look for PARAMETERS section
            param_section = re.search(r'PARAMETERS:\s*(.*?)(?:\n\n|\nREASONING|$)', response, re.DOTALL | re.IGNORECASE)
            
            if param_section:
                param_text = param_section.group(1)
                
                # Parse parameter lines
                for line in param_text.split('\n'):
                    line = line.strip()
                    if ':' in line:
                        param_name, param_value = line.split(':', 1)
                        param_name = param_name.strip()
                        param_value = param_value.strip()
                        
                        # Validate parameter exists in spec
                        all_params = function_spec.get('required_params', []) + function_spec.get('optional_params', [])
                        if param_name in all_params:
                            # Parse the value
                            parsed_value = self._parse_parameter_value(param_value)
                            params[param_name] = parsed_value
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error parsing parameter response: {e}")
        
        return params

    def _parse_parameter_value(self, value_str: str) -> Any:
        """
        Parse a parameter value string into appropriate Python type
        
        Args:
            value_str: String representation of parameter value
            
        Returns:
            Parsed parameter value
        """
        value_str = value_str.strip().strip("'\"")
        
        # Handle different types
        if value_str.lower() in ['true', 'false']:
            return value_str.lower() == 'true'
        elif value_str.lower() == 'none':
            return None
        elif value_str.isdigit():
            return int(value_str)
        elif re.match(r'^\d+\.\d+$', value_str):
            return float(value_str)
        elif value_str.startswith('[') and value_str.endswith(']'):
            # List handling
            try:
                return eval(value_str)  # Use eval carefully for lists
            except:
                return value_str
        else:
            return value_str

    def _generate_default_parameters(self, step: PipelineStep, function_spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate default parameter values as fallback
        
        Args:
            step: Pipeline step
            function_spec: Function specification
            
        Returns:
            Dictionary of default parameter values
        """
        params = {}
        default_values = function_spec.get('default_values', {})
        
        # Apply defaults and make intelligent guesses
        if step.function_name == "variance_analysis":
            params.update({
                "method": "rolling",
                "window": 30,  # Common for volatility calculations
                "suffix": None
            })
            
            # Extract window from description if mentioned
            window_match = re.search(r'(\d+)[\s-]*day', step.description, re.IGNORECASE)
            if window_match:
                params["window"] = int(window_match.group(1))
        
        # Apply function defaults
        params.update(default_values)
        
        return params

    def process_logical_plan_step_enhanced(self, step_text: str, dataframe_description: Dict[str, Any] = None) -> PipelineStep:
        """
        Enhanced processing of a single logical plan step with ChromaDB function retrieval
        
        Args:
            step_text: Single step text from logical planner
            dataframe_description: Optional dataframe description
            
        Returns:
            Enhanced PipelineStep object with function specification
        """
        # Parse the basic step information
        step = self._parse_logical_plan_step(step_text)
        
        # If we have a function name, retrieve its specification from ChromaDB
        if step.function_name and step.function_name != "None":
            if self.debug_mode:
                print(f"\n🔍 Retrieving function spec for: {step.function_name}")
            
            function_spec = self.retrieve_function_spec_from_chromadb(step.function_name)
            step.function_spec = function_spec
            
            if function_spec:
                # Generate enhanced code using the retrieved specification
                enhanced_code = self.generate_function_call_with_spec(step, function_spec, dataframe_description)
                step.generated_code = enhanced_code
                
                if self.debug_mode:
                    print(f"✅ Generated enhanced code for {step.function_name}:")
                    print(f"   {enhanced_code}")
            else:
                if self.debug_mode:
                    print(f"❌ No function spec found for {step.function_name}")
                step.generated_code = f"# Error: Function specification not found for {step.function_name}"
        
        return step

    def _parse_logical_plan_step(self, step_text: str) -> PipelineStep:
        """
        Parse a single step from the logical planner output
        
        Args:
            step_text: Single step text from logical planner
            
        Returns:
            PipelineStep object
        """
        # Parse the format: (step_number. description: operation_type : function : columns : sql_operation)
        step_pattern = r'\((\d+)\.\s*(.*?):\s*(.*?):\s*(.*?):\s*(.*?):\s*(.*?)\)'
        match = re.search(step_pattern, step_text)
        
        if match:
            step_number = int(match.group(1))
            description = match.group(2).strip()
            operation_type = match.group(3).strip()
            function_name = match.group(4).strip() if match.group(4).strip() != 'None' else None
            columns_str = match.group(5).strip()
            sql_operation = match.group(6).strip()
            
            # Parse columns list
            columns = []
            if columns_str and columns_str != 'None':
                # Remove brackets and split by comma
                columns_clean = columns_str.strip('[]\'\"')
                columns = [col.strip().strip("'\"") for col in columns_clean.split(',') if col.strip()]
            
            return PipelineStep(
                step_number=step_number,
                description=description,
                operation_type=operation_type,
                function_name=function_name,
                columns=columns,
                sql_operation=sql_operation
            )
        else:
            # Fallback parsing for simpler formats
            return PipelineStep(
                step_number=1,
                description=step_text,
                operation_type="general_analysis",
                function_name=None,
                columns=[],
                sql_operation=step_text
            )

    def run_enhanced(self, logical_plan_output: str, dataframe_columns: List[str] = None, 
                    dataframe_description: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Enhanced run method with improved ChromaDB function retrieval
        
        Args:
            logical_plan_output: Raw plan output from the logical planner
            dataframe_columns: Optional list of available columns
            dataframe_description: Optional dataframe description
            
        Returns:
            Dictionary containing the complete analysis pipeline with enhanced function specs
        """
        if self.debug_mode:
            print("🚀 Starting Enhanced Logical Plan Processing")
            print("=" * 60)
        
        # Split the plan into individual steps
        step_texts = logical_plan_output.split(' | ')
        
        # Process each step with enhanced ChromaDB retrieval
        enhanced_steps = []
        for step_text in step_texts:
            step = self.process_logical_plan_step_enhanced(step_text.strip(), dataframe_description)
            enhanced_steps.append(step)
        
        # Generate complete pipeline code
        pipeline_code = self._assemble_enhanced_pipeline(enhanced_steps)
        
        # Return enhanced results
        result = {
            "original_plan": logical_plan_output,
            "enhanced_steps": [
                {
                    "step_number": step.step_number,
                    "description": step.description,
                    "operation_type": step.operation_type,
                    "function_name": step.function_name,
                    "columns": step.columns,
                    "sql_operation": step.sql_operation,
                    "generated_code": step.generated_code,
                    "function_spec": step.function_spec
                }
                for step in enhanced_steps
            ],
            "pipeline_code": pipeline_code,
            "chromadb_retrievals": len([s for s in enhanced_steps if s.function_spec]),
            "analysis_summary": {
                "total_steps": len(enhanced_steps),
                "functions_with_specs": len([s for s in enhanced_steps if s.function_spec]),
                "operation_types": list(set([step.operation_type for step in enhanced_steps])),
                "functions_used": [step.function_name for step in enhanced_steps if step.function_name],
                "columns_involved": list(set([col for step in enhanced_steps for col in step.columns]))
            }
        }
        
        if self.debug_mode:
            print(f"\n✅ Enhanced Processing Complete!")
            print(f"   📊 Total steps: {len(enhanced_steps)}")
            print(f"   🔍 ChromaDB retrievals: {result['chromadb_retrievals']}")
            print(f"   ⚙️ Functions with specs: {result['analysis_summary']['functions_with_specs']}")
        
        return result

    def _assemble_enhanced_pipeline(self, steps: List[PipelineStep]) -> str:
        """
        Assemble pipeline with enhanced function calls
        
        Args:
            steps: List of enhanced pipeline steps
            
        Returns:
            Complete pipeline code
        """
        # Determine the primary pipe class
        primary_type = self._determine_primary_pipe_class(steps)
        
        # Build the pipeline
        pipeline_lines = [
            "# Import necessary libraries",
            "import pandas as pd",
            "import numpy as np",
            f"from analysis_pipes import {primary_type}",
            "",
            "# Initialize and execute the analysis pipeline",
            "result = (",
            f"    {primary_type}.from_dataframe(df)"
        ]
        
        # Add each step
        for step in steps:
            if step.generated_code and not step.generated_code.startswith("# Error"):
                # Clean up the generated code
                code_line = step.generated_code.strip()
                if code_line.startswith('.'):
                    pipeline_lines.append(f"    | {code_line}")
                else:
                    pipeline_lines.append(f"    | .{code_line}")
        
        pipeline_lines.extend([
            ")",
            "",
            "# Display results",
            "print(result.summary())"
        ])
        
        return "\n".join(pipeline_lines)

    def _determine_primary_pipe_class(self, steps: List[PipelineStep]) -> str:
        """Determine the primary pipe class based on steps"""
        pipe_class_map = {
            "time_series_analysis": "TimeSeriesPipe",
            "time series operation": "TimeSeriesPipe", 
            "risk_analysis": "RiskPipe",
            "risk analysis operation": "RiskPipe",
            "general_analysis": "DataFramePipe",
            "general analysis operation": "DataFramePipe"
        }
        
        # Count operation types
        type_counts = {}
        for step in steps:
            op_type = step.operation_type
            type_counts[op_type] = type_counts.get(op_type, 0) + 1
        
        # Choose the most common type
        if type_counts:
            primary_type = max(type_counts.items(), key=lambda x: x[1])[0]
            return pipe_class_map.get(primary_type, "DataFramePipe")
        
        return "DataFramePipe"


# Test function for the enhanced agent
def test_enhanced_agent_with_variance_analysis():
    """Test the enhanced agent with the variance analysis example"""
    
    print("🧪 TESTING ENHANCED AGENT WITH VARIANCE ANALYSIS")
    print("=" * 70)
    
    # Mock ChromaDB collection that returns the time series specs
    class MockChromaDBCollection:
        def query(self, query_texts, n_results=1):
            # Return the variance_analysis specification
            if "variance_analysis" in query_texts[0]:
                return {
                    "documents": [[json.dumps({
                        "functions": {
                            "variance_analysis": {
                                "required_params": ["columns"],
                                "optional_params": ["method", "window", "time_column", "group_columns", "suffix"],
                                "outputs": {
                                    "type": "Callable",
                                    "description": "Function that calculates variance in a TimeSeriesPipe"
                                },
                                "description": "Calculate variance and standard deviation for time series data",
                                "default_values": {
                                    "method": "rolling",
                                    "window": 30
                                }
                            }
                        }
                    })]]
                }
            return {"documents": [[]]}
    
    # Mock LLM for parameter generation
    class MockLLM:
        def invoke(self, args):
            if "parameter values" in str(args).lower():
                return """
                PARAMETERS:
                method: rolling
                window: 30
                suffix: _volatility
                
                REASONING:
                For rolling volatility calculation over 30 days as mentioned in the description,
                using rolling method with 30-day window is appropriate for financial risk analysis.
                """
            return "Mock response"
    
    # Create enhanced agent
    llm = MockLLM()
    function_collection = MockChromaDBCollection()
    
    agent = EnhancedGeneralizedAnalysisAgent(
        llm=llm,
        function_collection=function_collection,
        example_collection=None,
        insights_collection=None
    )
    
    agent.enable_debug_mode()
    
    # Test the problematic logical plan step
    logical_plan = """(1. Data Preprocessing: general analysis operation : None : ['date', 'asset_id', 'returns', 'price', 'volume', 'portfolio_weight'] : Filter the dataset to ensure it contains only relevant columns and remove any rows with missing values.) | (2. Calculate Rolling Volatility: time series operation : variance_analysis : ['returns'] : Calculate the rolling standard deviation of returns over a specified window (e.g., 30 days) to assess volatility.)"""
    
    # Sample dataframe description
    dataframe_description = {
        'schema': {
            'date': 'datetime64[ns]',
            'asset_id': 'object',
            'returns': 'float64',
            'price': 'float64', 
            'volume': 'int64',
            'portfolio_weight': 'float64'
        },
        'stats': {
            'returns': {'mean': 0.001, 'std': 0.02, 'min': -0.1, 'max': 0.08},
            'price': {'mean': 150.25, 'std': 25.67}
        }
    }
    
    print("📊 Testing with logical plan:")
    print(logical_plan)
    print("\n🔄 Processing with Enhanced Agent...")
    
    # Run the enhanced agent
    result = agent.run_enhanced(
        logical_plan_output=logical_plan,
        dataframe_description=dataframe_description
    )
    
    print("\n" + "="*70)
    print("📋 ENHANCED PROCESSING RESULTS:")
    print("="*70)
    
    # Display results
    for step in result["enhanced_steps"]:
        print(f"\n📝 Step {step['step_number']}: {step['description']}")
        print(f"   Function: {step['function_name']}")
        print(f"   Generated Code: {step['generated_code']}")
        if step['function_spec']:
            print(f"   ✅ Function spec retrieved from ChromaDB")
        else:
            print(f"   ❌ No function spec found")
    
    print(f"\n🎯 Final Pipeline Code:")
    print(result["pipeline_code"])
    
    return result

if __name__ == "__main__":
    test_enhanced_agent_with_variance_analysis()
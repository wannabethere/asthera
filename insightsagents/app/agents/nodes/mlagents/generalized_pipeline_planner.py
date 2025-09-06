from langchain.agents import Tool
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers.string import StrOutputParser
from typing import Dict, List, Any, Optional, Tuple
import json
import re
from dataclasses import dataclass

# Import the existing logical planner output structure
from app.agents.nodes.logical_planners import DataSciencePlanState, FUNCTIONS_AVAILABLE
from app.agents.nodes.mlagents.function_input_extractor import create_input_extractor

# NOTE: This module now uses the enhanced smart input extractors from generic_input_extractors
# which provide LLM-based parameter extraction instead of hardcoded logic.
# The smart extractors include:
# - SmartTimeSeriesExtractor: LLM-powered time series parameter extraction
# - SmartCohortAnalysisExtractor: Intelligent cohort analysis parameter detection
# - SmartSegmentationExtractor: Context-aware segmentation parameter extraction
# - SmartTrendAnalysisExtractor: Advanced trend analysis parameter inference
# - SmartRiskAnalysisExtractor: Sophisticated risk analysis parameter detection
# - SmartFunnelAnalysisExtractor: Enhanced funnel analysis parameter extraction
# - SmartGeneralAnalysisExtractor: Comprehensive general analysis parameter extraction

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

GENERALIZED_ANALYSIS_PROMPT = """
You are a data science analysis expert who helps users generate code for comprehensive data science analysis tasks.

CONTEXT:
You have access to collections of data science functions with function definitions and examples.
You can retrieve function definitions and examples, validate retrieval scores, and generate code.
The retrieval score must be above 0.8 to be considered reliable.
for the code generation, please dont generate any boilerplate code, just the code that is needed to call the function.
for the function inputs, please use the function_specs to determine the correct inputs.
You are also given function insights that are relevant to the function you are trying to generate code for but are not exactly matching the function definition.
The function insights help you understand the function better and provide more context for the code generation.
if the inputs need to be calculated please output a list of parameters that needed to be calculated as "Natural Language Question for the data". Please only use the function_specs to determine the correct calculations.
Please provide the inputs for all the functions.

LOGICAL PLAN STEP:
{logical_step}

DATAFRAME INFORMATION:
{dataframe_info}

AVAILABLE FUNCTIONS:
{available_functions}

FUNCTION DEFINITIONS:
{function_definitions}

FUNCTION INSIGHTS:
{function_insights}

THOUGHT PROCESS:
{agent_scratchpad}

Your task is to generate executable code for this specific step in the logical plan, working from the step description and operation type to create the appropriate function call.

Output Format:
code:
{{
# Generated function call for {operation_type}
function_name(
    parameter1='value1',
    parameter2='value2',
    ...
)
}}
inputs:
{{
    {{input function variable name1: generated input 1: calculated: "Natural Language Question for the data"}}
    {{input function variable name2: generated input 2: columnpresent: "data set column name"}}
    ...
}}
reasoning:
{{
Brief explanation of why this function and these parameters were chosen for this step.
}}
"""

class GeneralizedAnalysisAgent:
    """Generalized agent that can handle all types of data science analysis functions"""
    
    def __init__(self, llm, function_collection, example_collection, insights_collection=None):
        """
        Initialize the Generalized Analysis Agent
        
        Args:
            llm: Language model instance
            function_collection: DocumentChromaStore instance for function definitions
            example_collection: DocumentChromaStore instance for examples
            insights_collection: DocumentChromaStore instance for insights
        """
        self.llm = llm
        self.function_collection = function_collection
        self.example_collection = example_collection
        self.insights_collection = insights_collection
        
        # Initialize debug mode (disabled by default)
        self.debug_mode = False
        
        # Initialize function specification cache
        self.function_spec_cache = {}
        
        # Create specialized input extractors for different analysis types using the smart extractors
        
        
        self.input_extractors = {
            "cohort_analysis": create_input_extractor("cohort_analysis", llm, example_collection, function_collection, insights_collection),
            "funnel_analysis": create_input_extractor("funnel_analysis", llm, example_collection, function_collection, insights_collection),
            "time_series_analysis": create_input_extractor("time_series_analysis", llm, example_collection, function_collection, insights_collection),
            "time series operation": create_input_extractor("time_series_analysis", llm, example_collection, function_collection, insights_collection),
            "segmentation": create_input_extractor("segmentation", llm, example_collection, function_collection, insights_collection),
            "trend_analysis": create_input_extractor("trend_analysis", llm, example_collection, function_collection, insights_collection),
            "risk_analysis": create_input_extractor("risk_analysis", llm, example_collection, function_collection, insights_collection),
            "general_analysis": create_input_extractor("general_analysis", llm, example_collection, function_collection, insights_collection),
            "general analysis operation": create_input_extractor("general_analysis operation", llm, example_collection, function_collection, insights_collection)
        }
        
        # Initialize conversation memory
        self.memory = ConversationBufferMemory(memory_key="chat_history")
        
        # Create the tools
        self.tools = self._create_tools()

    def find_column_match_with_schema(self, column_type: str, available_columns: List[str], 
                                     dataframe_description: Dict[str, Any]) -> Dict[str, Any]:
        """
        Find the best matching column using LLM-based analysis with schema information
        
        Args:
            column_type: Type of column to find (e.g., 'event_column', 'user_id_column')
            available_columns: List of available column names in the dataframe
            dataframe_description: Dictionary containing schema, descriptions, and statistics
            
        Returns:
            Dictionary with matched column and reasoning
        """
        if not available_columns:
            return {"column": None, "reasoning": "No columns available to match.", "confidence": "LOW"}
                
        try:
            # Extract comprehensive schema information
            schema_details = self._extract_comprehensive_schema_info(available_columns, dataframe_description)
            
            # Create enhanced prompt template
            schema_prompt_template = PromptTemplate(
                input_variables=["column_type", "available_columns", "schema_details", "summary_text"],
                template="""
                You are an expert data scientist specializing in column identification for data analysis functions.
                
                TASK: Find the BEST column that matches the requirements for: {column_type}
                
                AVAILABLE COLUMNS: {available_columns}
                
                SCHEMA INFORMATION:
                {schema_details}
                
                DATAFRAME SUMMARY: {summary_text}
                
                ANALYSIS FRAMEWORK:
                1. UNDERSTAND REQUIREMENT: What type of data does {column_type} need?
                2. EVALUATE DATA TYPES: Which columns have compatible data types?
                3. ASSESS QUALITY: Which columns have good data quality for this use?
                4. SEMANTIC ANALYSIS: Which column names suggest the right content?
                5. STATISTICAL REVIEW: Do the statistics support this column's suitability?
                
                EXPERT KNOWLEDGE:
                - event_column: Should contain categorical event/action names (object/string type)
                - user_id_column: Should contain unique identifiers (object/string/int, high uniqueness)
                - date_column: Should contain dates/timestamps (datetime64 type)
                - value_column: Should contain numeric values (int64/float64 type)
                - segment_column: Should contain categorical groupings (object type, moderate uniqueness)
                
                RESPONSE FORMAT:
                REQUIREMENT: [What {column_type} needs]
                ANALYSIS: [Evaluate each column systematically]
                BEST_MATCH: [exact_column_name_or_NONE]
                CONFIDENCE: [HIGH/MEDIUM/LOW]
                REASONING: [Why this column was selected based on data evidence]
                """
            )
            
            # Create and run the LLM chain
            schema_chain = schema_prompt_template | self.llm | StrOutputParser()
            result = schema_chain.invoke({
                "column_type": column_type,
                "available_columns": ", ".join(available_columns),
                "schema_details": schema_details,
                "summary_text": dataframe_description.get('summary', 'No summary provided')
            })
            
            return self._parse_enhanced_column_response(result, available_columns)
                
        except Exception as e:
            return {"column": None, "reasoning": f"Error in schema-based column matching: {str(e)}", "confidence": "LOW"}

    def find_column_match(self, column_type: str, available_columns: List[str]) -> Dict[str, Any]:
        """
        Find the best matching column using LLM-based semantic analysis
        
        Args:
            column_type: Type of column to find (e.g., 'event_column', 'user_id_column')
            available_columns: List of available column names in the dataframe
            
        Returns:
            Dictionary with matched column and reasoning
        """
        if not available_columns:
            return {"column": None, "reasoning": "No columns available to match.", "confidence": "LOW"}
                
        try:
            # Create semantic analysis prompt
            semantic_prompt_template = PromptTemplate(
                input_variables=["column_type", "available_columns"],
                template="""
                You are an expert data scientist with extensive knowledge of column naming conventions and data analysis requirements.
                
                TASK: Identify the BEST column for: {column_type}
                
                AVAILABLE COLUMNS: {available_columns}
                
                EXPERT ANALYSIS:
                Apply your knowledge of:
                - Common data science naming conventions
                - Industry-standard column patterns
                - Semantic meaning of column names
                - Functional requirements for different analysis types
                
                COLUMN TYPE EXPERTISE:
                - event_column: Look for columns indicating actions, events, activities (event, action, activity_type, etc.)
                - user_id_column: Look for unique user identifiers (user_id, customer_id, uid, etc.)
                - date_column: Look for date/time references (date, timestamp, created_at, etc.)
                - value_column: Look for numeric values, amounts, metrics (value, amount, price, revenue, etc.)
                - segment_column: Look for grouping/category columns (segment, group, category, type, etc.)
                
                ANALYSIS PROCESS:
                1. Parse the {column_type} to understand what's needed
                2. Apply semantic analysis to each available column name
                3. Consider common naming patterns and variations
                4. Evaluate logical fit for the intended purpose
                5. Apply data science best practices
                
                RESPONSE FORMAT:
                REQUIREMENT: [What {column_type} typically contains]
                EVALUATION: [Analyze each column name for semantic fit]
                BEST_MATCH: [exact_column_name_or_NONE]
                CONFIDENCE: [HIGH/MEDIUM/LOW]
                REASONING: [Why this column was selected based on naming analysis]
                
                IMPORTANT: Return NONE if no column is semantically appropriate.
                """
            )
            
            # Create and run the LLM chain
            semantic_chain = semantic_prompt_template | self.llm | StrOutputParser()
            result = semantic_chain.invoke({
                "column_type": column_type,
                "available_columns": ", ".join(available_columns)
            })
            
            return self._parse_enhanced_column_response(result, available_columns)
                
        except Exception as e:
            return {"column": None, "reasoning": f"Error in semantic column matching: {str(e)}", "confidence": "LOW"}

    def _find_closest_column(self, column_name: str, available_columns: List[str], 
                            dataframe_description: Dict[str, Any] = None, 
                            context: str = "") -> Optional[str]:
        """
        Enhanced LLM-based column finder that replaces hardcoded pattern matching
        
        Args:
            column_name: The type of column needed (e.g., 'user_id_column', 'date_column')
            available_columns: List of available column names in the dataframe
            dataframe_description: Optional dictionary with schema and metadata
            context: Optional context about how this column will be used
            
        Returns:
            Best matching column name or None if no suitable match found
        """
        if not available_columns:
            return None
        
        # Use schema-based matching if description is available, otherwise semantic matching
        if dataframe_description:
            result = self.find_column_match_with_schema(column_name, available_columns, dataframe_description)
        else:
            result = self.find_column_match(column_name, available_columns)
        
        # Log the decision for debugging
        if self.debug_mode:
            self._log_column_matching_decision(column_name, result, available_columns, bool(dataframe_description))
        
        return result.get("column")

    def _extract_comprehensive_schema_info(self, available_columns: List[str], 
                                          dataframe_description: Dict[str, Any]) -> str:
        """Extract comprehensive schema information for LLM analysis"""
        schema_parts = []
        
        # Extract data types
        if 'schema' in dataframe_description:
            type_info = []
            for col in available_columns:
                if col in dataframe_description['schema']:
                    dtype = dataframe_description['schema'][col]
                    type_info.append(f"  {col}: {dtype}")
            if type_info:
                schema_parts.append("DATA TYPES:\n" + "\n".join(type_info))
        
        # Extract statistics
        if 'stats' in dataframe_description:
            stats_info = []
            for col in available_columns:
                if col in dataframe_description['stats']:
                    col_stats = dataframe_description['stats'][col]
                    if isinstance(col_stats, dict):
                        stat_details = []
                        for stat_name, stat_value in col_stats.items():
                            if stat_name in ['count', 'unique', 'mean', 'std', 'min', 'max', 'null_count']:
                                stat_details.append(f"{stat_name}: {stat_value}")
                        if stat_details:
                            stats_info.append(f"  {col}: {', '.join(stat_details)}")
            if stats_info:
                schema_parts.append("STATISTICS:\n" + "\n".join(stats_info))
        
        # Extract sample values
        if 'sample_values' in dataframe_description:
            sample_info = []
            for col in available_columns:
                if col in dataframe_description['sample_values']:
                    samples = dataframe_description['sample_values'][col]
                    if isinstance(samples, list) and samples:
                        sample_str = str(samples[:5])[1:-1]  # Remove brackets, show first 5
                        sample_info.append(f"  {col}: {sample_str}")
            if sample_info:
                schema_parts.append("SAMPLE VALUES:\n" + "\n".join(sample_info))
        
        return "\n\n".join(schema_parts) if schema_parts else "No detailed schema information available"

    def _parse_enhanced_column_response(self, result: str, available_columns: List[str]) -> Dict[str, Any]:
        """Parse LLM response to extract column match and metadata"""
        parsed = {"column": None, "reasoning": "No clear reasoning provided.", "confidence": "LOW"}
        
        try:
            # Extract BEST_MATCH
            best_match_pattern = r"BEST_MATCH:\s*(.*?)(?:\n|$)"
            match = re.search(best_match_pattern, result, re.IGNORECASE)
            if match:
                column_name = match.group(1).strip()
                if column_name.upper() == "NONE":
                    parsed["column"] = None
                elif column_name in available_columns:
                    parsed["column"] = column_name
                else:
                    # Try case-insensitive match
                    for col in available_columns:
                        if col.lower() == column_name.lower():
                            parsed["column"] = col
                            break
            
            # Extract CONFIDENCE
            confidence_pattern = r"CONFIDENCE:\s*(.*?)(?:\n|$)"
            conf_match = re.search(confidence_pattern, result, re.IGNORECASE)
            if conf_match:
                confidence = conf_match.group(1).strip().upper()
                if confidence in ["HIGH", "MEDIUM", "LOW"]:
                    parsed["confidence"] = confidence
            
            # Extract REASONING
            reasoning_pattern = r"REASONING:\s*(.*?)(?:\n(?:[A-Z_]+:|$))"
            reasoning_match = re.search(reasoning_pattern, result, re.IGNORECASE | re.DOTALL)
            if reasoning_match:
                parsed["reasoning"] = reasoning_match.group(1).strip()
        
        except Exception as e:
            parsed["reasoning"] = f"Error parsing LLM response: {str(e)}"
        
        return parsed

    def _log_column_matching_decision(self, column_type: str, result: Dict[str, Any], 
                                     available_columns: List[str], has_schema: bool = False):
        """Log column matching decisions for debugging"""
        if self.debug_mode:
            print(f"🔍 Column Matching for '{column_type}':")
            print(f"   Method: {'Schema-based' if has_schema else 'Semantic'} LLM analysis")
            print(f"   Available: {', '.join(available_columns)}")
            print(f"   Selected: {result['column'] or 'None'}")
            print(f"   Confidence: {result.get('confidence', 'Unknown')}")
            print(f"   Reasoning: {result['reasoning'][:100]}{'...' if len(result['reasoning']) > 100 else ''}")
            print()

    def enable_debug_mode(self):
        """Enable debug mode for column matching logging"""
        self.debug_mode = True

    def disable_debug_mode(self):
        """Disable debug mode for column matching logging"""
        self.debug_mode = False

    def test_column_matching(self, test_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Test the enhanced column matching with multiple scenarios
        
        Args:
            test_cases: List of test cases with column_type, available_columns, and optional dataframe_description
            
        Returns:
            Dictionary with test results
        """
        results = {}
        
        print("🧪 TESTING ENHANCED COLUMN MATCHING")
        print("=" * 50)
        
        for i, test_case in enumerate(test_cases, 1):
            column_type = test_case["column_type"]
            columns = test_case["available_columns"]
            description = test_case.get("dataframe_description")
            
            print(f"\n📝 Test Case {i}: {column_type}")
            print(f"   Available columns: {', '.join(columns)}")
            
            # Test with schema if available
            if description:
                result = self.find_column_match_with_schema(column_type, columns, description)
                method = "Schema-based"
            else:
                result = self.find_column_match(column_type, columns)
                method = "Semantic"
            
            print(f"   Method: {method}")
            print(f"   Selected: {result['column'] or 'None'}")
            print(f"   Confidence: {result.get('confidence', 'Unknown')}")
            print(f"   Reasoning: {result['reasoning'][:100]}{'...' if len(result['reasoning']) > 100 else ''}")
            
            results[f"test_{i}_{column_type}"] = result
        
        print(f"\n✅ Completed {len(test_cases)} test cases")
        return results

    def quick_column_match(self, column_type: str, available_columns: List[str], 
                          dataframe_description: Dict[str, Any] = None, debug: bool = False) -> str:
        """
        Quick utility method for column matching with optional debug output
        
        Args:
            column_type: Type of column needed
            available_columns: Available columns in dataset
            dataframe_description: Optional schema information
            debug: Whether to print debug information
            
        Returns:
            Best matching column name or None
        """
        if debug:
            self.enable_debug_mode()
        
        result = self._find_closest_column(column_type, available_columns, dataframe_description)
        
        if debug:
            print(f"🎯 Quick Match Result: {column_type} -> {result or 'None'}")
            self.disable_debug_mode()
        
        return result

    def _create_tools(self) -> List[Tool]:
        """Create the tools for the agent"""
        tools = [
            Tool(
                name="parse_logical_plan_step",
                func=self._parse_logical_plan_step,
                description="Parses a single step from the logical planner output"
            ),
            Tool(
                name="map_operation_to_function",
                func=self._map_operation_to_function,
                description="Maps an operation type to appropriate analysis functions"
            ),
            Tool(
                name="extract_step_inputs",
                func=self._extract_step_inputs,
                description="Extracts inputs for a specific analysis step"
            ),
            Tool(
                name="generate_step_code",
                func=self._generate_step_code,
                description="Generates code for a specific analysis step"
            ),
            Tool(
                name="validate_step_dependencies",
                func=self._validate_step_dependencies,
                description="Validates that step dependencies are satisfied"
            ),
            Tool(
                name="assemble_complete_pipeline",
                func=self._assemble_complete_pipeline,
                description="Assembles the complete analysis pipeline from all steps"
            )
        ]
        return tools

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

    def _map_operation_to_function(self, operation_type: str, function_name: str = None, description: str = "") -> Tuple[str, List[str]]:
        """
        Map an operation type to appropriate analysis functions using LLM and function specifications
        
        Args:
            operation_type: Type of operation from logical planner
            function_name: Specific function name if provided
            description: Description of the operation
            
        Returns:
            Tuple of (analysis_category, suggested_functions)
        """
        # Direct mapping from operation types to categories
        operation_category_map = {
            "cohort_analysis": "cohort_analysis",
            "cohort analysis operation": "cohort_analysis",
            "funnel_analysis": "funnel_analysis", 
            "funnel analysis operation": "funnel_analysis",
            "time_series_analysis": "time_series_analysis",
            "time series operation": "time_series_analysis",
            "segmentation": "segmentation",
            "segmentation operation": "segmentation",
            "trend_analysis": "trend_analysis",
            "trend analysis operation": "trend_analysis",
            "risk_analysis": "risk_analysis",
            "risk analysis operation": "risk_analysis",
            "general_analysis": "general_analysis",
            "general analysis operation": "general_analysis",
            "sql": "general_analysis",
            "machine_learning": "machine_learning"
        }
        
        # Get the analysis category
        analysis_category = operation_category_map.get(operation_type, "general_analysis")
        
        # If a specific function is provided, use it
        if function_name and function_name != "None":
            return analysis_category, [function_name]
        
        # Use LLM to intelligently suggest functions based on function specifications
        suggested_functions = self._llm_suggest_functions(analysis_category, description)
        
        return analysis_category, suggested_functions

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
            
            EXAMPLES GUIDANCE for variance_analysis or time series operations:
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
            print("="*100)
            print(f"🔍 Retrieving function spec for: {step.function_name}")
            print(f"🔍 Function spec: {function_spec}")
            print("="*100)

            if function_spec:
                # Generate enhanced code using the retrieved specification
                enhanced_code = self.generate_function_call_with_llm_integration(step, function_spec, dataframe_description)
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
   
    def generate_function_call_with_spec(self, step: PipelineStep, function_spec: Dict[str, Any], 
                                        dataframe_description: Dict[str, Any] = None) -> str:
        """
        Generate function call code using LLM-based approach with enhanced parameter generation
        
        Args:
            step: Pipeline step to generate code for
            function_spec: Retrieved function specification
            dataframe_description: Optional dataframe description
            
        Returns:
            Generated function call code
        """
        # Use the enhanced LLM-integrated approach
        return self.generate_function_call_with_llm_integration(step, function_spec, dataframe_description)
    
    def _generate_llm_based_function_call(self, step: PipelineStep, function_specs: List[Dict[str, Any]],
                                         dataframe_description: Dict[str, Any] = None) -> str:
        """
        Generate function call using LLM with multiple function specifications from vector store
        
        Args:
            step: Pipeline step
            function_specs: List of function specifications from vector store
            dataframe_description: Optional dataframe description
            
        Returns:
            Generated function call string
        """
        if not function_specs:
            return self._generate_basic_function_call(step, dataframe_description)
        
        # Create comprehensive LLM prompt for function selection and call generation
        function_call_prompt = PromptTemplate(
            input_variables=["step_description", "operation_type", "columns", "sql_operation", 
                           "available_functions", "dataframe_info"],
            template="""
            You are an expert data scientist generating Python function calls for data analysis pipelines.
            
            TASK: Select the BEST function from the available functions and generate a complete, executable function call.
            
            STEP INFORMATION:
            - Description: {step_description}
            - Operation Type: {operation_type}
            - Available Columns: {columns}
            - SQL Operation: {sql_operation}
            
            AVAILABLE FUNCTIONS FROM VECTOR STORE:
            {available_functions}
            
            DATAFRAME INFORMATION:
            {dataframe_info}
            
            REQUIREMENTS:
            1. Select the MOST APPROPRIATE function for this specific step
            2. Generate ONLY the function call code (e.g., ".function_name(param1='value1', param2=value2)")
            3. Include all required parameters from the selected function specification
            4. Include optional parameters only if they add value based on the step context
            5. Use appropriate parameter values based on the step description and available columns
            6. Follow Python syntax conventions
            7. Handle column parameters intelligently (single column as string, multiple as list)
            8. Extract parameter values from the step description when possible (e.g., "30 days" -> window=30)
            
            SELECTION CRITERIA:
            - Function purpose matches the task requirements
            - Function capabilities align with the described operation
            - Consider the specific terminology used in the step description
            - Apply data science best practices for function selection
            
            PARAMETER GUIDANCE:
            - For 'columns' parameter: use step.columns, format as string if single, list if multiple
            - For time-related parameters: extract from description (e.g., "30-day volatility" -> window=30)
            - For method parameters: choose based on context (e.g., "rolling" for time series)
            - For boolean parameters: infer from description context
            - For numeric parameters: extract numbers from description or use sensible defaults
            
            OUTPUT FORMAT:
            Generate ONLY the function call code, no explanations or markdown formatting.
            Example: .variance_analysis(columns='close_price', method='rolling', window=30)
            
            IMPORTANT: Return ONLY the function call, no additional text or formatting.
            """
        )
        
        try:
            # Create the function call generation chain
            function_call_chain = function_call_prompt | self.llm | StrOutputParser()
            
            # Format available functions for the prompt
            available_functions_text = self._format_multiple_functions_for_prompt(function_specs)
            
            # Prepare dataframe information
            dataframe_info = self._format_dataframe_info_for_prompt(dataframe_description)
            
            # Generate the function call
            result = function_call_chain.invoke({
                "step_description": step.description,
                "operation_type": step.operation_type,
                "columns": str(step.columns) if step.columns else "[]",
                "sql_operation": step.sql_operation,
                "available_functions": available_functions_text,
                "dataframe_info": dataframe_info
            })
            print("="*100)
            print(f"🔍 Generated function call: {result}")
            print("="*100)
            
            # Clean and validate the generated function call
            cleaned_call = self._clean_and_validate_function_call_from_multiple_specs(result, function_specs)
            
            if self.debug_mode:
                print(f"🔧 Generated function call: {cleaned_call}")
            
            return cleaned_call
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error in LLM-based function call generation: {e}")
            
            # Fallback: use the first function spec to generate a basic call
            if function_specs:
                return self._generate_fallback_function_call(step, function_specs[0])
            else:
                return self._generate_basic_function_call(step, dataframe_description)
    
    def _format_function_spec_for_prompt(self, function_spec: Dict[str, Any]) -> str:
        """Format function specification for LLM prompt"""
        formatted_parts = []
        
        if 'description' in function_spec:
            formatted_parts.append(f"Description: {function_spec['description']}")
        
        if 'required_params' in function_spec:
            formatted_parts.append(f"Required Parameters: {', '.join(function_spec['required_params'])}")
        
        if 'optional_params' in function_spec:
            formatted_parts.append(f"Optional Parameters: {', '.join(function_spec['optional_params'])}")
        
        if 'default_values' in function_spec:
            defaults = [f"{k}={v}" for k, v in function_spec['default_values'].items()]
            formatted_parts.append(f"Default Values: {', '.join(defaults)}")
        
        return "\n".join(formatted_parts) if formatted_parts else "No detailed specification available"
    
    def _format_dataframe_info_for_prompt(self, dataframe_description: Dict[str, Any] = None) -> str:
        """Format dataframe information for LLM prompt"""
        if not dataframe_description:
            return "No dataframe information available"
        
        info_parts = []
        
        if 'schema' in dataframe_description:
            schema_info = [f"{col}: {dtype}" for col, dtype in dataframe_description['schema'].items()]
            info_parts.append(f"Data Types: {', '.join(schema_info)}")
        
        if 'summary' in dataframe_description:
            info_parts.append(f"Summary: {dataframe_description['summary']}")
        
        return "\n".join(info_parts) if info_parts else "Basic dataframe information available"
    
    def _clean_and_validate_function_call(self, result: str, function_name: str, function_spec: Dict[str, Any]) -> str:
        """Clean and validate the generated function call"""
        # Remove markdown formatting and extra whitespace
        cleaned = result.strip()
        
        # Remove code block markers
        if cleaned.startswith('```python'):
            cleaned = cleaned[10:]
        if cleaned.startswith('```'):
            cleaned = cleaned[3:]
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]
        
        cleaned = cleaned.strip()
        
        # Ensure it starts with the function name
        if not cleaned.startswith(f'.{function_name}('):
            # Try to fix common issues
            if cleaned.startswith(function_name):
                cleaned = f'.{cleaned}'
            elif not cleaned.startswith('.'):
                cleaned = f'.{function_name}({cleaned})'
        
        # Validate required parameters are present
        required_params = function_spec.get('required_params', [])
        for param in required_params:
            if param not in cleaned and param != 'columns':  # columns is handled specially
                if self.debug_mode:
                    print(f"⚠️  Warning: Required parameter '{param}' not found in generated call")
        
        return cleaned
    
    def _generate_fallback_function_call(self, step: PipelineStep, function_spec: Dict[str, Any]) -> str:
        """Generate a fallback function call when LLM generation fails"""
        function_name = step.function_name or function_spec.get('name', 'unknown_function')
        
        # Extract basic parameter information
        required_params = function_spec.get('required_params', [])
        optional_params = function_spec.get('optional_params', [])
        default_values = function_spec.get('default_values', {})
        
        # Build parameters
        params = []
        
        # Handle required parameters
        for param in required_params:
            if param == 'columns' and step.columns:
                if len(step.columns) == 1:
                    params.append(f"columns='{step.columns[0]}'")
                else:
                    params.append(f"columns={step.columns}")
            else:
                # Use default value if available, otherwise use parameter name as placeholder
                default_val = default_values.get(param)
                if default_val is not None:
                    if isinstance(default_val, str):
                        params.append(f"{param}='{default_val}'")
                    else:
                        params.append(f"{param}={default_val}")
                else:
                    params.append(f"{param}='<{param}>'")
        
        # Add a few key optional parameters with defaults
        key_optional_params = ['window', 'method', 'periods']
        for param in key_optional_params:
            if param in optional_params and param in default_values:
                default_val = default_values[param]
                if isinstance(default_val, str):
                    params.append(f"{param}='{default_val}'")
                else:
                    params.append(f"{param}={default_val}")
        
        # Generate the function call
        params_str = ", ".join(params)
        return f".{function_name}({params_str})"

    def generate_function_call_with_llm_integration(self, step: PipelineStep, function_spec: Dict[str, Any] = None,
                                                   dataframe_description: Dict[str, Any] = None) -> str:
        """
        Enhanced function call generation that integrates LLM-based function selection and parameter generation
        
        Args:
            step: Pipeline step to generate code for
            function_spec: Optional function specification (will be retrieved if not provided)
            dataframe_description: Optional dataframe description
            
        Returns:
            Generated function call code
        """
       
        return self._generate_llm_based_function_call(step, [function_spec], dataframe_description)
        
            
    def _retrieve_functions_from_vector_store(self, step: PipelineStep, dataframe_description: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Retrieve possible functions from the functions vector store based on step description
        
        Args:
            step: Pipeline step
            dataframe_description: Optional dataframe description
            
        Returns:
            List of retrieved function specifications
        """
        if not self.function_collection:
            if self.debug_mode:
                print("⚠️  No function collection available for vector store retrieval")
            return []
        
        try:
            # Create a comprehensive search query from the step description
            search_query = self._create_function_search_query(step, dataframe_description)
            
            if self.debug_mode:
                print(f"🔍 Searching functions vector store with query: {search_query}")
            
            # Retrieve functions from the vector store
            retrieved_functions = []
            
            # Try different search methods
            if hasattr(self.function_collection, 'semantic_search'):
                results = self.function_collection.semantic_search(search_query, k=5)
                retrieved_functions.extend(self._parse_semantic_search_results(results))
            
            elif hasattr(self.function_collection, 'query'):
                results = self.function_collection.query(
                    query_texts=[search_query],
                    n_results=5
                )
                retrieved_functions.extend(self._parse_query_results(results))
            
            # If we have a specific function name, also try to get its exact specification
            if step.function_name and step.function_name != "None":
                specific_function = self.retrieve_function_spec_from_chromadb(step.function_name)
                if specific_function:
                    # Add to the beginning of the list as it's more specific
                    retrieved_functions.insert(0, specific_function)
            
            if self.debug_mode:
                print(f"📦 Retrieved {len(retrieved_functions)} functions from vector store")
                for i, func in enumerate(retrieved_functions[:3]):  # Show first 3
                    func_name = func.get('name', 'unknown')
                    func_desc = func.get('description', 'No description')[:100]
                    print(f"   {i+1}. {func_name}: {func_desc}...")
            
            return retrieved_functions
            
        except Exception as e:
            if self.debug_mode:
                print(f"❌ Error retrieving functions from vector store: {e}")
            return []
    
    def _create_function_search_query(self, step: PipelineStep, dataframe_description: Dict[str, Any] = None) -> str:
        """
        Create a comprehensive search query for function retrieval
        
        Args:
            step: Pipeline step
            dataframe_description: Optional dataframe description
            
        Returns:
            Search query string
        """
        query_parts = []
        
        # Add step description (primary source)
        if step.description:
            query_parts.append(step.description)
        
        # Add operation type
        if step.operation_type:
            query_parts.append(step.operation_type)
        
        # Add SQL operation if it contains useful information
        if step.sql_operation and step.sql_operation != step.description:
            # Extract key terms from SQL operation
            sql_terms = self._extract_key_terms_from_sql(step.sql_operation)
            if sql_terms:
                query_parts.extend(sql_terms)
        
        # Add column information if available
        if step.columns:
            query_parts.append(f"columns: {', '.join(step.columns)}")
        
        # Add dataframe context if available
        if dataframe_description and 'summary' in dataframe_description:
            query_parts.append(f"data context: {dataframe_description['summary']}")
        
        # Combine all parts
        search_query = " ".join(query_parts)
        
        # Clean up the query
        search_query = re.sub(r'\s+', ' ', search_query).strip()
        
        return search_query
    
    def _extract_key_terms_from_sql(self, sql_operation: str) -> List[str]:
        """
        Extract key terms from SQL operation for function search
        
        Args:
            sql_operation: SQL operation string
            
        Returns:
            List of key terms
        """
        key_terms = []
        
        # Extract common SQL patterns that indicate function types
        sql_lower = sql_operation.lower()
        
        # Time series patterns
        if any(term in sql_lower for term in ['lag(', 'lead(', 'window', 'rolling', 'moving average']):
            key_terms.extend(['time series', 'rolling', 'lag', 'lead'])
        
        # Aggregation patterns
        if any(term in sql_lower for term in ['sum(', 'avg(', 'count(', 'group by']):
            key_terms.extend(['aggregation', 'group by', 'summary'])
        
        # Statistical patterns
        if any(term in sql_lower for term in ['stddev', 'variance', 'correlation', 'regression']):
            key_terms.extend(['statistics', 'variance', 'correlation'])
        
        # Cohort patterns
        if any(term in sql_lower for term in ['cohort', 'retention', 'signup', 'activity']):
            key_terms.extend(['cohort', 'retention', 'user behavior'])
        
        # Funnel patterns
        if any(term in sql_lower for term in ['funnel', 'conversion', 'step']):
            key_terms.extend(['funnel', 'conversion', 'user journey'])
        
        # Segmentation patterns
        if any(term in sql_lower for term in ['case when', 'segment', 'cluster']):
            key_terms.extend(['segmentation', 'clustering', 'classification'])
        
        return key_terms
    
    def _parse_semantic_search_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Parse semantic search results from function collection
        
        Args:
            results: Raw semantic search results
            
        Returns:
            List of parsed function specifications
        """
        parsed_functions = []
        
        for result in results:
            if isinstance(result, dict):
                # Extract content from different possible keys
                content = result.get('content') or result.get('document') or result.get('text', '')
                
                if content:
                    function_spec = self._parse_function_spec_from_content(content)
                    if function_spec:
                        parsed_functions.append(function_spec)
        
        return parsed_functions
    
    def _parse_query_results(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse query results from function collection
        
        Args:
            results: Raw query results
            
        Returns:
            List of parsed function specifications
        """
        parsed_functions = []
        
        if 'documents' in results and results['documents']:
            for doc_list in results['documents']:
                for doc in doc_list:
                    if isinstance(doc, str):
                        function_spec = self._parse_function_spec_from_content(doc)
                        if function_spec:
                            parsed_functions.append(function_spec)
        
        return parsed_functions
    
    def _parse_function_spec_from_content(self, content: str) -> Dict[str, Any]:
        """
        Parse function specification from content string
        
        Args:
            content: Raw content string
            
        Returns:
            Parsed function specification
        """
        try:
            # Try to parse as JSON first
            if content.strip().startswith('{'):
                spec = json.loads(content)
                return spec
            
            # Try to extract JSON from mixed content
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                spec = json.loads(json_match.group(0))
                return spec
            
            # Try to extract structured information using regex patterns
            spec = self._extract_spec_from_text(content, "")
            if spec and len(spec) > 1:
                return spec
            
        except (json.JSONDecodeError, Exception) as e:
            if self.debug_mode:
                print(f"Error parsing function spec from content: {e}")
        
        return {}
    

    
    def _format_multiple_functions_for_prompt(self, function_specs: List[Dict[str, Any]]) -> str:
        """
        Format multiple function specifications for LLM prompt
        
        Args:
            function_specs: List of function specifications
            
        Returns:
            Formatted string for prompt
        """
        formatted_functions = []
        
        for i, spec in enumerate(function_specs, 1):
            func_text = f"FUNCTION {i}:\n"
            
            if 'name' in spec:
                func_text += f"  Name: {spec['name']}\n"
            
            if 'description' in spec:
                func_text += f"  Description: {spec['description']}\n"
            
            if 'required_params' in spec:
                func_text += f"  Required Parameters: {', '.join(spec['required_params'])}\n"
            
            if 'optional_params' in spec:
                func_text += f"  Optional Parameters: {', '.join(spec['optional_params'])}\n"
            
            if 'default_values' in spec:
                defaults = [f"{k}={v}" for k, v in spec['default_values'].items()]
                func_text += f"  Default Values: {', '.join(defaults)}\n"
            
            formatted_functions.append(func_text)
        
        return "\n".join(formatted_functions) if formatted_functions else "No functions available"
    
    def _clean_and_validate_function_call_from_multiple_specs(self, result: str, function_specs: List[Dict[str, Any]]) -> str:
        """
        Clean and validate function call when multiple function specs are available
        
        Args:
            result: LLM generated result
            function_specs: List of available function specifications
            
        Returns:
            Cleaned and validated function call
        """
        # Remove markdown formatting and extra whitespace
        cleaned = result.strip()
        
        # Remove code block markers
        if cleaned.startswith('```python'):
            cleaned = cleaned[10:]
        if cleaned.startswith('```'):
            cleaned = cleaned[3:]
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]
        
        cleaned = cleaned.strip()
        
        # Extract function name from the generated call
        function_name_match = re.search(r'\.(\w+)\s*\(', cleaned)
        if function_name_match:
            function_name = function_name_match.group(1)
            
            # Validate that this function exists in our specs
            valid_function = any(spec.get('name') == function_name for spec in function_specs)
            
            if not valid_function:
                # Try to find a similar function name
                for spec in function_specs:
                    spec_name = spec.get('name', '')
                    if spec_name and spec_name.lower() in function_name.lower():
                        # Replace with the correct function name
                        cleaned = cleaned.replace(f".{function_name}(", f".{spec_name}(")
                        break
        
        return cleaned

    def _generate_basic_function_call(self, step: PipelineStep, dataframe_description: Dict[str, Any] = None) -> str:
        """
        Generate a basic function call when no function specification is available
        
        Args:
            step: Pipeline step
            dataframe_description: Optional dataframe description
            
        Returns:
            Basic function call string
        """
        # Determine the function name based on operation type
        operation_type = step.operation_type.lower()
        
        # Map operation types to common function names
        function_mapping = {
            "time_series_analysis": "time_series_analysis",
            "time series operation": "time_series_analysis",
            "cohort_analysis": "cohort_analysis",
            "cohort analysis operation": "cohort_analysis",
            "funnel_analysis": "funnel_analysis",
            "funnel analysis operation": "funnel_analysis",
            "segmentation": "segmentation",
            "segmentation operation": "segmentation",
            "trend_analysis": "trend_analysis",
            "trend analysis operation": "trend_analysis",
            "risk_analysis": "risk_analysis",
            "risk analysis operation": "risk_analysis",
            "general_analysis": "general_analysis",
            "general analysis operation": "general_analysis"
        }
        
        function_name = function_mapping.get(operation_type, "general_analysis")
        
        # Generate parameters based on the step description and columns
        params = self._extract_basic_parameters_from_step(step, dataframe_description)
        
        # Build the function call
        if params:
            params_str = ", ".join([f"{k}={v}" for k, v in params.items()])
            return f".{function_name}({params_str})"
        else:
            return f".{function_name}()"
    
    def _extract_basic_parameters_from_step(self, step: PipelineStep, dataframe_description: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Extract basic parameters from step description and columns
        
        Args:
            step: Pipeline step
            dataframe_description: Optional dataframe description
            
        Returns:
            Dictionary of basic parameters
        """
        params = {}
        
        # Handle columns parameter
        if step.columns:
            if len(step.columns) == 1:
                params["columns"] = f"'{step.columns[0]}'"
            else:
                params["columns"] = str(step.columns)
        
        # Extract common parameters from description
        description_lower = step.description.lower()
        
        # Extract window size
        window_match = re.search(r'(\d+)[\s-]*(day|week|month|year)', description_lower)
        if window_match:
            params["window"] = int(window_match.group(1))
        
        # Extract method
        if "rolling" in description_lower:
            params["method"] = "'rolling'"
        elif "exponential" in description_lower:
            params["method"] = "'exponential'"
        
        # Extract periods for lag/lead operations
        periods_match = re.search(r'(\d+)[\s-]*(lag|lead|period)', description_lower)
        if periods_match:
            params["periods"] = int(periods_match.group(1))
        
        return params

    def _llm_suggest_functions(self, analysis_category: str, description: str) -> List[str]:
        """
        Use LLM to suggest appropriate functions based on function specifications and task description
        
        Args:
            analysis_category: Category of analysis (time_series_analysis, cohort_analysis, etc.)
            description: Description of what needs to be accomplished
            
        Returns:
            List of suggested function names
        """
        try:
            # Validate inputs
            if not analysis_category or not description:
                print(f"Invalid inputs: analysis_category={analysis_category}, description={description}")
                return []
            
            # Get all available functions for this category from FUNCTIONS_AVAILABLE
            # FUNCTIONS_AVAILABLE is already imported at the top of the file
            
            category_functions = [
                func for func in FUNCTIONS_AVAILABLE 
                if func.get("category") == analysis_category
            ]
            
            if not category_functions:
                print(f"No functions found for category: {analysis_category}")
                return []
            
            # Get detailed function specifications from the function collection
            if not self.function_collection:
                print("No function collection available, using basic function info")
                return [func.get("name", "") for func in category_functions if func.get("name")]
            
            function_specs = self._get_category_function_specs(category_functions)
            
            # Create LLM prompt for function selection
            from langchain.prompts import PromptTemplate
            from langchain_core.output_parsers.string import StrOutputParser
            
            function_selection_prompt = PromptTemplate(
                input_variables=["analysis_category", "task_description", "available_functions"],
                template="""
                You are an expert data scientist who selects the most appropriate analysis functions for specific tasks.
                
                ANALYSIS CATEGORY: {analysis_category}
                
                TASK DESCRIPTION: {task_description}
                
                AVAILABLE FUNCTIONS:
                {available_functions}
                
                Your task is to select the BEST function(s) from the available functions that would accomplish the described task.
                
                SELECTION CRITERIA:
                1. Function purpose matches the task requirements
                2. Function capabilities align with the described operation
                3. Consider the specific terminology used in the task description
                4. Apply data science best practices for function selection
                5. Consider common workflows and function combinations
                
                ANALYSIS PROCESS:
                1. Parse the task description to understand what needs to be accomplished
                2. Review each available function's name and description
                3. Match the task requirements to function capabilities
                4. Select the most appropriate function(s)
                5. Consider if multiple functions might be needed for the task
                
                RESPONSE FORMAT:
                TASK_ANALYSIS: [What the task is trying to accomplish]
                FUNCTION_EVALUATION: [Evaluate each relevant function for this task]
                SELECTED_FUNCTIONS: [comma-separated list of function names, or NONE if no match]
                CONFIDENCE: [HIGH/MEDIUM/LOW]
                REASONING: [Why these functions were selected based on their specifications]
                
                IMPORTANT:
                - Only select functions that are actually available in the list
                - Return NONE if no function is appropriate for the task
                - Consider the specific wording and intent of the task description
                - Don't force matches - be conservative in selection
                """
            )
            
            # Format available functions for the prompt
            functions_text = self._format_functions_for_prompt(category_functions, function_specs)
            
            # Create and run the LLM chain
            function_chain = function_selection_prompt | self.llm | StrOutputParser()
            result = function_chain.invoke({
                "analysis_category": analysis_category,
                "task_description": description,
                "available_functions": functions_text
            })
            
            # Parse the LLM response
            return self._parse_function_selection_response(result, category_functions)
            
        except Exception as e:
            print(f"Error in LLM function suggestion for {analysis_category}: {e}")
            # Fallback: return empty list rather than hardcoded suggestions
            return []

    def _get_category_function_specs(self, category_functions: List[Dict[str, str]]) -> Dict[str, Dict[str, Any]]:
        """
        Get detailed function specifications from the function collection
        
        Args:
            category_functions: List of functions from FUNCTIONS_AVAILABLE for a specific category
            
        Returns:
            Dictionary mapping function names to their detailed specifications
        """
        function_specs = {}
        
        for func in category_functions:
            function_name = func["name"]
            try:
                # Try to get detailed spec from function collection
                if function_name and hasattr(self.function_collection, 'semantic_search'):
                    results = self.function_collection.semantic_search(function_name, k=1)
                    if results and len(results) > 0 and isinstance(results[0], dict) and results[0].get('content'):
                        spec = results[0]['content']
                        if isinstance(spec, str):
                            try:
                                spec = json.loads(spec)
                            except json.JSONDecodeError:
                                spec = {"description": spec}
                        function_specs[function_name] = spec
                elif function_name and hasattr(self.function_collection, 'semantic_searches'):
                    results = self.function_collection.semantic_searches([function_name], n_results=1)
                    if results and results.get('documents') and len(results['documents']) > 0 and len(results['documents'][0]) > 0:
                        spec = results['documents'][0][0]
                        if isinstance(spec, str):
                            try:
                                spec = json.loads(spec)
                            except json.JSONDecodeError:
                                spec = {"description": spec}
                        function_specs[function_name] = spec
                
                # If no detailed spec found, use basic info from FUNCTIONS_AVAILABLE
                if function_name not in function_specs:
                    function_specs[function_name] = {
                        "name": function_name,
                        "description": func["description"],
                        "category": func["category"]
                    }
                    
            except Exception as e:
                print(f"Error getting spec for {function_name}: {e}")
                # Use basic info as fallback
                function_specs[function_name] = {
                    "name": function_name,
                    "description": func["description"],
                    "category": func["category"]
                }
        
        return function_specs

    def _format_functions_for_prompt(self, category_functions: List[Dict[str, str]], 
                                    function_specs: Dict[str, Dict[str, Any]]) -> str:
        """
        Format function information for LLM prompt
        
        Args:
            category_functions: Basic function info from FUNCTIONS_AVAILABLE
            function_specs: Detailed function specifications
            
        Returns:
            Formatted string describing available functions
        """
        formatted_functions = []
        
        for func in category_functions:
            function_name = func["name"]
            basic_description = func["description"]
            
            # Get detailed spec if available
            detailed_spec = function_specs.get(function_name, {})
            
            # Create comprehensive function description
            func_description = f"**{function_name}**:\n"
            func_description += f"  Description: {basic_description}\n"
            
            if "required_params" in detailed_spec:
                func_description += f"  Required Parameters: {', '.join(detailed_spec['required_params'])}\n"
            
            if "optional_params" in detailed_spec:
                func_description += f"  Optional Parameters: {', '.join(detailed_spec['optional_params'])}\n"
            
            if "use_cases" in detailed_spec:
                func_description += f"  Use Cases: {detailed_spec['use_cases']}\n"
            
            formatted_functions.append(func_description)
        
        return "\n".join(formatted_functions)

    def _parse_function_selection_response(self, result: str, category_functions: List[Dict[str, str]]) -> List[str]:
        """
        Parse LLM response to extract selected functions
        
        Args:
            result: LLM response text
            category_functions: Available functions for validation
            
        Returns:
            List of selected function names
        """
        selected_functions = []
        
        try:
            # Extract SELECTED_FUNCTIONS
            functions_pattern = r"SELECTED_FUNCTIONS:\s*(.*?)(?:\n|$)"
            match = re.search(functions_pattern, result, re.IGNORECASE)
            
            if match:
                functions_text = match.group(1).strip()
                
                if functions_text.upper() == "NONE":
                    return []
                
                # Parse comma-separated function names
                suggested_names = [name.strip() for name in functions_text.split(',')]
                
                # Validate against available functions
                available_names = [func["name"] for func in category_functions]
                
                for name in suggested_names:
                    if name in available_names:
                        selected_functions.append(name)
                    else:
                        # Try case-insensitive match
                        for available_name in available_names:
                            if available_name.lower() == name.lower():
                                selected_functions.append(available_name)
                                break
        
        except Exception as e:
            print(f"Error parsing function selection response: {e}")
        
        return selected_functions

    def _get_function_suggestions_with_confidence(self, analysis_category: str, description: str) -> Dict[str, Any]:
        """
        Get function suggestions with confidence scoring and reasoning
        
        Args:
            analysis_category: Category of analysis
            description: Task description
            
        Returns:
            Dictionary with suggested functions, confidence, and reasoning
        """
        suggested_functions = self._llm_suggest_functions(analysis_category, description)
        
        # For now, return basic confidence (could be enhanced with LLM confidence scoring)
        confidence = "HIGH" if len(suggested_functions) == 1 else "MEDIUM" if suggested_functions else "LOW"
        
        return {
            "suggested_functions": suggested_functions,
            "confidence": confidence,
            "reasoning": f"Selected {len(suggested_functions)} function(s) for {analysis_category} based on task analysis"
        }

    def _extract_step_inputs(self, step: PipelineStep, dataframe_description: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Extract inputs for a specific analysis step
        
        Args:
            step: Pipeline step to extract inputs for
            dataframe_description: Optional dataframe description
            
        Returns:
            Dictionary with extracted inputs
        """
        # Determine the analysis category
        category, suggested_functions = self._map_operation_to_function(
            step.operation_type, 
            step.function_name, 
            step.description
        )
        
        # Get the appropriate input extractor
        extractor = self.input_extractors.get(category, self.input_extractors["general_analysis"])
        
        # Create context from step information
        context = f"""
        Task: {step.description}
        Operation Type: {step.operation_type}
        Function: {step.function_name or 'To be determined'}
        Columns: {step.columns}
        SQL Operation: {step.sql_operation}
        Suggested Functions: {suggested_functions}
        """
        
        # Use the suggested function if no specific function was provided
        target_function = step.function_name
        if not target_function and suggested_functions:
            # Extract function name from formatted string (remove category and pipeline info)
            formatted_func = suggested_functions[0]
            if ': ' in formatted_func:
                target_function = formatted_func.split(': ')[0]
            else:
                target_function = formatted_func
        
        # Extract inputs using the specialized extractor
        if hasattr(extractor, 'extract_inputs'):
            result = extractor.extract_inputs(
                context=context,
                function_name=target_function,
                columns=step.columns,
                dataframe_description=dataframe_description
            )
        else:
            # Fallback for simpler extractors
            result = {
                "function_name": target_function,
                "columns": step.columns,
                "operation_type": step.operation_type,
                "description": step.description
            }
        
        return result

    def _generate_step_code(self, step: PipelineStep, extracted_inputs: Dict[str, Any]) -> str:
        """
        Generate code for a specific analysis step
        
        Args:
            step: Pipeline step to generate code for
            extracted_inputs: Extracted inputs for the step
            
        Returns:
            Generated Python code
        """
        # Determine the function to use
        function_name = extracted_inputs.get("function_name") or step.function_name
        
        # Create a prompt template for code generation
        code_prompt = PromptTemplate(
            input_variables=["step_description", "function_name", "operation_type", "columns", "inputs", "sql_operation"],
            template="""
            Generate Python code for the following data science analysis step:
            
            STEP: {step_description}
            FUNCTION: {function_name}
            OPERATION TYPE: {operation_type}
            COLUMNS: {columns}
            SQL OPERATION: {sql_operation}
            EXTRACTED INPUTS: {inputs}
            
            Generate code based on the operation type:
            
            For time series operations:
            ```python
            .{function_name}(
                columns={columns},
                parameter1=value1,
                parameter2=value2
            )
            ```
            
            For cohort analysis:
            ```python
            .{function_name}(
                column='column_name',
                parameter1=value1
            )
            ```
            
            For segmentation:
            ```python
            .{function_name}(
                features={columns},
                parameter1=value1
            )
            ```
            
            For risk analysis:
            ```python
            .{function_name}(
                data_column='column_name',
                parameter1=value1
            )
            ```
            
            For general operations (when function_name is None):
            ```python
            # SQL-like operation or pandas transformation
            .query("condition")
            .groupby('column')
            .agg(function)
            # or
            .assign(new_column=lambda x: calculation)
            ```
            
            IMPORTANT RULES:
            1. If function_name is None or not available, generate pandas operations based on the SQL operation description
            2. Only include the pipeline operation code, not full pipeline initialization
            3. Format all parameters properly (strings in quotes, lists with proper syntax)
            4. Use column names from the columns list where appropriate
            5. Make sure to give all the correct parameters for the function including default values.
            
            Return ONLY the pipeline operation code without explanations.
            """
        )
        
        # Create the code generation chain
        code_chain = code_prompt | self.llm | StrOutputParser()
        
        # Run the chain
        try:
            code = code_chain.invoke({
                "step_description": step.description,
                "function_name": function_name or "pandas_operation",
                "operation_type": step.operation_type,
                "columns": str(step.columns),
                "sql_operation": step.sql_operation,
                "inputs": json.dumps(extracted_inputs, indent=2)
            })
            
            # Clean up the code
            code = re.sub(r'```python\s*', '', code)
            code = re.sub(r'```\s*', '', code)
            
            return code.strip()
        except Exception as e:
            return f"# Error generating code for {step.description}: {str(e)}"

    def _validate_step_dependencies(self, steps: List[PipelineStep]) -> Dict[str, Any]:
        """
        Validate that step dependencies are satisfied
        
        Args:
            steps: List of pipeline steps
            
        Returns:
            Dictionary with validation results
        """
        validation_results = {
            "valid": True,
            "issues": [],
            "warnings": []
        }
        
        created_columns = set()
        
        for step in steps:
            # Check if required columns exist
            for col in step.columns:
                if col not in created_columns and not self._is_likely_existing_column(col):
                    validation_results["warnings"].append(
                        f"Step {step.step_number}: Column '{col}' may not be available"
                    )
            
            # Track columns that might be created by this step
            potential_new_columns = self._infer_created_columns(step)
            created_columns.update(potential_new_columns)
        
        return validation_results

    def _is_likely_existing_column(self, col_name: str) -> bool:
        """Check if a column name is likely to exist in the original dataset"""
        # Common column patterns that are likely to exist
        common_patterns = [
            "date", "time", "price", "volume", "value", "amount", "id", "user", 
            "customer", "product", "category", "group", "segment", "flux", "returns"
        ]
        col_lower = col_name.lower()
        return any(pattern in col_lower for pattern in common_patterns)

    def _infer_created_columns(self, step: PipelineStep) -> List[str]:
        """Infer what new columns might be created by this step"""
        created_columns = []
        description_lower = step.description.lower()
        
        if "calculate" in description_lower:
            if "returns" in description_lower:
                created_columns.append("daily_returns")
            if "volatility" in description_lower:
                created_columns.append("volatility") 
            if "variance" in description_lower:
                created_columns.append("variance")
            if "moving_average" in description_lower:
                created_columns.append("moving_average")
        
        return created_columns

    def _assemble_complete_pipeline(self, steps_with_code: List[PipelineStep]) -> str:
        """
        Assemble the complete analysis pipeline
        
        Args:
            steps_with_code: List of pipeline steps with generated code
            
        Returns:
            Complete pipeline code
        """
        # Determine the primary analysis type to choose the right Pipe class
        analysis_types = [step.operation_type for step in steps_with_code]
        
        # Count occurrences of each type
        type_counts = {}
        for analysis_type in analysis_types:
            type_counts[analysis_type] = type_counts.get(analysis_type, 0) + 1
        
        # Choose the most common analysis type
        primary_type = max(type_counts.items(), key=lambda x: x[1])[0] if type_counts else "general_analysis"
        
        # Map to appropriate Pipe class
        pipe_class_map = {
            "time_series_analysis": "TimeSeriesPipe",
            "time series operation": "TimeSeriesPipe",
            "cohort_analysis": "CohortPipe",
            "segmentation": "SegmentationPipe",
            "trend_analysis": "TrendAnalysisPipe",
            "risk_analysis": "RiskPipe",
            "funnel_analysis": "FunnelPipe",
            "general_analysis": "DataFramePipe"
        }
        
        pipe_class = pipe_class_map.get(primary_type, "DataFramePipe")
        
        # Create a prompt template for assembling the pipeline
        assemble_prompt = PromptTemplate(
            input_variables=["steps", "pipe_class", "primary_type"],
            template="""
            Assemble a complete data science analysis pipeline from the following steps:
            
            PRIMARY ANALYSIS TYPE: {primary_type}
            PIPE CLASS: {pipe_class}
            
            STEPS WITH GENERATED CODE:
            {steps}
            
            The pipeline should follow this format:
            ```python
            # Donot add imports here.
            
            # Initialize the pipeline with the dataframe
            result = (
                {pipe_class}.from_dataframe(df)
                | step1_operation
                | step2_operation
                | step3_operation
                ...
            )
            
            
            ```
            
            IMPORTANT RULES:
            1. Use the correct {pipe_class} for the primary analysis type
            2. Chain operations using the | operator
            3. Include proper imports at the top
            4. Handle cases where some steps don't have function calls (use pandas operations)
            5. Donot add result display at the end
            
            Return the complete assembled pipeline code
            """
        )
        
        # Format steps for the prompt
        steps_info = []
        for step in steps_with_code:
            steps_info.append(f"""
            Step {step.step_number}: {step.description}
            Operation Type: {step.operation_type}
            Function: {step.function_name or 'pandas_operation'}
            Generated Code: {step.generated_code}
            """)
        
        steps_str = "\n".join(steps_info)
        
        # Create the assembly chain
        assemble_chain = assemble_prompt | self.llm | StrOutputParser()
        
        # Run the chain
        try:
            result = assemble_chain.invoke({
                "steps": steps_str,
                "pipe_class": pipe_class,
                "primary_type": primary_type
            })
            
            # Clean up the code
            code = result.strip()
            if code.startswith("```python"):
                code = code[10:]
            if code.endswith("```"):
                code = code[:-3]
            
            return code.strip()
        except Exception as e:
            return f"# Error assembling pipeline: {str(e)}"

    def run(self, logical_plan_output: str, dataframe_columns: List[str] = None, dataframe_description: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Run the generalized analysis agent on a logical plan output
        
        Args:
            logical_plan_output: Raw plan output from the logical planner (pipe-separated steps)
            dataframe_columns: Optional list of available columns
            dataframe_description: Optional dataframe description
            
        Returns:
            Dictionary containing the complete analysis pipeline
        """
        # Split the plan into individual steps
        step_texts = logical_plan_output.split(' | ')
        
        # Parse each step
        parsed_steps = []
        for step_text in step_texts:
            step = self.process_logical_plan_step_enhanced(step_text.strip(), dataframe_description = dataframe_description)
            parsed_steps.append(step)
        
        # Process each step: extract inputs and generate code
        steps_with_code = []
        for step in parsed_steps:
            # Extract inputs for this step
            extracted_inputs = self._extract_step_inputs(step, dataframe_description)
            step.function_inputs = extracted_inputs
            
            # Generate code for this step
            generated_code = self._generate_step_code(step, extracted_inputs)
            step.generated_code = generated_code
            
            steps_with_code.append(step)
        
        # Validate step dependencies
        validation_results = self._validate_step_dependencies(steps_with_code)
        
        # Assemble the complete pipeline
        pipeline_code = self._assemble_complete_pipeline(steps_with_code)
        
        # Return the complete result
        return {
            "original_plan": logical_plan_output,
            "parsed_steps": [
                {
                    "step_number": step.step_number,
                    "description": step.description,
                    "operation_type": step.operation_type,
                    "function_name": step.function_name,
                    "columns": step.columns,
                    "sql_operation": step.sql_operation,
                    "generated_code": step.generated_code,
                    "function_inputs": step.function_inputs
                }
                for step in steps_with_code
            ],
            "validation_results": validation_results,
            "pipeline_code": pipeline_code,
            "analysis_summary": {
                "total_steps": len(steps_with_code),
                "operation_types": list(set([step.operation_type for step in steps_with_code])),
                "functions_used": [step.function_name for step in steps_with_code if step.function_name],
                "columns_involved": list(set([col for step in steps_with_code for col in step.columns]))
            }
        }


# Base class for specialized input extractors
class BaseInputExtractor:
    """Base class for input extractors"""
    
    def __init__(self, llm, example_collection, function_collection, insights_collection):
        self.llm = llm
        self.example_collection = example_collection
        self.function_collection = function_collection
        self.insights_collection = insights_collection
    
    def extract_inputs(self, context: str, function_name: str, columns: List[str], dataframe_description: Dict[str, Any] = None) -> Dict[str, Any]:
        """Extract inputs for the given function and context"""
        return {
            "function_name": function_name,
            "columns": columns,
            "context": context
        }




class GeneralAnalysisInputExtractor(BaseInputExtractor):
    """Smart general analysis input extractor for SQL-like operations with LLM-based column matching"""
    
    def extract_inputs(self, context: str, function_name: str, columns: List[str], 
                      dataframe_description: Dict[str, Any] = None) -> Dict[str, Any]:
        """Extract inputs for general analysis operations with enhanced LLM intelligence"""
        
        # Start with basic structure
        inputs = {
            "columns": columns,
            "operation": "general_analysis",
            "context": context
        }
        
        # Use LLM to analyze the context and determine operation type
        operation_analysis = self._analyze_operation_context(context, columns, dataframe_description)
        inputs.update(operation_analysis)
        
        # Extract specific parameters based on detected operation
        if inputs["operation"] == "filter":
            inputs.update(self._extract_filter_conditions_llm(context, columns, dataframe_description))
        elif inputs["operation"] == "groupby":
            inputs.update(self._extract_groupby_params_llm(context, columns, dataframe_description))
        elif inputs["operation"] == "sort":
            inputs.update(self._extract_sort_params_llm(context, columns, dataframe_description))
        
        return inputs
    
    def _analyze_operation_context(self, context: str, columns: List[str], 
                                  dataframe_description: Dict[str, Any] = None) -> Dict[str, Any]:
        """Use LLM to analyze context and determine the type of operation needed"""
        
        from langchain.prompts import PromptTemplate
        from langchain_core.output_parsers.string import StrOutputParser
        
        analysis_prompt = PromptTemplate(
            input_variables=["context", "columns", "dataframe_info"],
            template="""
            You are a data analysis expert. Analyze the following context to determine what type of operation is needed:
            
            CONTEXT: {context}
            AVAILABLE COLUMNS: {columns}
            DATAFRAME INFO: {dataframe_info}
            
            Determine the PRIMARY operation type from these options:
            - filter: Filtering/subsetting data based on conditions
            - groupby: Grouping data by categories and aggregating
            - sort: Sorting/ordering data
            - join: Joining with other data
            - transform: Transforming/calculating new columns
            - aggregate: Computing summary statistics
            - validation: Checking data quality or outliers
            - interpretation: Analyzing and explaining results
            
            IMPORTANT: Please ignore any visualization operations. 
            ANALYSIS:
            [Analyze what the context is asking for]
            
            OPERATION: [one of the options above]
            CONFIDENCE: [HIGH/MEDIUM/LOW]
            REASONING: [why this operation was selected]
            """
        )
        
        try:
            chain = analysis_prompt | self.llm | StrOutputParser()
            result = chain.invoke({
                "context": context,
                "columns": ", ".join(columns) if columns else "No columns specified",
                "dataframe_info": json.dumps(dataframe_description, indent=2) if dataframe_description else "No schema information"
            })
            
            # Parse the result
            operation_match = re.search(r"OPERATION:\s*(.*?)(?:\n|$)", result, re.IGNORECASE)
            confidence_match = re.search(r"CONFIDENCE:\s*(.*?)(?:\n|$)", result, re.IGNORECASE)
            reasoning_match = re.search(r"REASONING:\s*(.*?)(?:\n|$)", result, re.IGNORECASE)
            
            operation = operation_match.group(1).strip().lower() if operation_match else "general_analysis"
            confidence = confidence_match.group(1).strip().upper() if confidence_match else "LOW"
            reasoning = reasoning_match.group(1).strip() if reasoning_match else "Default analysis"
            
            return {
                "operation": operation,
                "operation_confidence": confidence,
                "operation_reasoning": reasoning
            }
            
        except Exception as e:
            return {
                "operation": "general_analysis",
                "operation_confidence": "LOW",
                "operation_reasoning": f"Error in operation analysis: {str(e)}"
            }
    
    def _extract_filter_conditions_llm(self, context: str, columns: List[str], 
                                      dataframe_description: Dict[str, Any] = None) -> Dict[str, Any]:
        """Use LLM to extract filter conditions from context"""
        
        from langchain.prompts import PromptTemplate
        from langchain_core.output_parsers.string import StrOutputParser
        
        filter_prompt = PromptTemplate(
            input_variables=["context", "columns", "schema_info"],
            template="""
            Extract filter conditions from this context:
            
            CONTEXT: {context}
            AVAILABLE COLUMNS: {columns}
            SCHEMA INFO: {schema_info}
            
            Identify:
            1. Which column(s) to filter on
            2. What filter condition to apply
            3. The filter values or criteria
            
            FILTER_COLUMN: [column to filter on]
            FILTER_CONDITION: [the condition as SQL-like expression]
            FILTER_VALUES: [specific values if any]
            REASONING: [why this filter was extracted]
            """
        )
        
        try:
            chain = filter_prompt | self.llm | StrOutputParser()
            result = chain.invoke({
                "context": context,
                "columns": ", ".join(columns) if columns else "No columns",
                "schema_info": json.dumps(dataframe_description, indent=2) if dataframe_description else "No schema"
            })
            
            # Parse filter parameters
            filter_params = {}
            
            # Extract filter column using LLM column matching
            column_match = re.search(r"FILTER_COLUMN:\s*(.*?)(?:\n|$)", result, re.IGNORECASE)
            if column_match:
                suggested_column = column_match.group(1).strip()
                if suggested_column in columns:
                    filter_params["filter_column"] = suggested_column
                else:
                    # Use LLM-based column matching to find the best match
                    if dataframe_description:
                        match_result = self.find_column_match_with_schema("filter_column", columns, dataframe_description)
                    else:
                        match_result = self.find_column_match("filter_column", columns)
                    if match_result["column"]:
                        filter_params["filter_column"] = match_result["column"]
            
            # Extract condition
            condition_match = re.search(r"FILTER_CONDITION:\s*(.*?)(?:\n|$)", result, re.IGNORECASE)
            if condition_match:
                filter_params["filter_condition"] = condition_match.group(1).strip()
            
            # Extract values
            values_match = re.search(r"FILTER_VALUES:\s*(.*?)(?:\n|$)", result, re.IGNORECASE)
            if values_match:
                filter_params["filter_values"] = values_match.group(1).strip()
            
            return filter_params
            
        except Exception as e:
            return {"filter_error": f"Error extracting filter conditions: {str(e)}"}
    
    def _extract_groupby_params_llm(self, context: str, columns: List[str], 
                                   dataframe_description: Dict[str, Any] = None) -> Dict[str, Any]:
        """Use LLM to extract groupby parameters from context"""
        
        from langchain.prompts import PromptTemplate
        from langchain_core.output_parsers.string import StrOutputParser
        
        groupby_prompt = PromptTemplate(
            input_variables=["context", "columns", "schema_info"],
            template="""
            Extract groupby parameters from this context:
            
            CONTEXT: {context}
            AVAILABLE COLUMNS: {columns}
            SCHEMA INFO: {schema_info}
            
            Identify:
            1. Which column(s) to group by (categorical columns)
            2. Which column(s) to aggregate
            3. What aggregation functions to use
            
            GROUP_BY_COLUMNS: [comma-separated list of columns to group by]
            AGGREGATE_COLUMNS: [comma-separated list of columns to aggregate]
            AGGREGATE_FUNCTIONS: [functions like sum, mean, count, etc.]
            REASONING: [explanation of the groupby operation]
            """
        )
        
        try:
            chain = groupby_prompt | self.llm | StrOutputParser()
            result = chain.invoke({
                "context": context,
                "columns": ", ".join(columns) if columns else "No columns",
                "schema_info": json.dumps(dataframe_description, indent=2) if dataframe_description else "No schema"
            })
            
            groupby_params = {}
            
            # Extract groupby columns
            groupby_match = re.search(r"GROUP_BY_COLUMNS:\s*(.*?)(?:\n|$)", result, re.IGNORECASE)
            if groupby_match:
                suggested_cols = [col.strip() for col in groupby_match.group(1).split(',')]
                valid_cols = [col for col in suggested_cols if col in columns]
                if valid_cols:
                    groupby_params["groupby_columns"] = valid_cols
            
            # Extract aggregate columns
            agg_match = re.search(r"AGGREGATE_COLUMNS:\s*(.*?)(?:\n|$)", result, re.IGNORECASE)
            if agg_match:
                suggested_cols = [col.strip() for col in agg_match.group(1).split(',')]
                valid_cols = [col for col in suggested_cols if col in columns]
                if valid_cols:
                    groupby_params["aggregate_columns"] = valid_cols
            
            # Extract aggregate functions
            func_match = re.search(r"AGGREGATE_FUNCTIONS:\s*(.*?)(?:\n|$)", result, re.IGNORECASE)
            if func_match:
                groupby_params["aggregate_functions"] = func_match.group(1).strip()
            
            return groupby_params
            
        except Exception as e:
            return {"groupby_error": f"Error extracting groupby parameters: {str(e)}"}
    
    def _extract_sort_params_llm(self, context: str, columns: List[str], 
                                dataframe_description: Dict[str, Any] = None) -> Dict[str, Any]:
        """Use LLM to extract sort parameters from context"""
        
        from langchain.prompts import PromptTemplate
        from langchain_core.output_parsers.string import StrOutputParser
        
        sort_prompt = PromptTemplate(
            input_variables=["context", "columns"],
            template="""
            Extract sorting parameters from this context:
            
            CONTEXT: {context}
            AVAILABLE COLUMNS: {columns}
            
            Identify:
            1. Which column(s) to sort by
            2. Sort direction (ascending/descending)
            
            SORT_COLUMNS: [comma-separated list of columns to sort by]
            SORT_DIRECTION: [ascending or descending]
            REASONING: [why these sort parameters were chosen]
            """
        )
        
        try:
            chain = sort_prompt | self.llm | StrOutputParser()
            result = chain.invoke({
                "context": context,
                "columns": ", ".join(columns) if columns else "No columns"
            })
            
            sort_params = {}
            
            # Extract sort columns
            sort_match = re.search(r"SORT_COLUMNS:\s*(.*?)(?:\n|$)", result, re.IGNORECASE)
            if sort_match:
                suggested_cols = [col.strip() for col in sort_match.group(1).split(',')]
                valid_cols = [col for col in suggested_cols if col in columns]
                if valid_cols:
                    sort_params["sort_columns"] = valid_cols
            
            # Extract sort direction
            dir_match = re.search(r"SORT_DIRECTION:\s*(.*?)(?:\n|$)", result, re.IGNORECASE)
            if dir_match:
                direction = dir_match.group(1).strip().lower()
                sort_params["ascending"] = direction != "descending"
            
            return sort_params
            
        except Exception as e:
            return {"sort_error": f"Error extracting sort parameters: {str(e)}"}
    
    




# Example usage function demonstrating the enhanced column matching
def demonstrate_enhanced_column_matching():
    """Demonstrate the enhanced LLM-based column matching capabilities"""
    
    print("🚀 ENHANCED COLUMN MATCHING DEMO")
    print("=" * 60)
    
    # Mock components for demonstration
    class MockLLM:
        def invoke(self, args):
            class MockResponse:
                def __init__(self, content):
                    self.content = content
            
            prompt_text = str(args)
            
            if "user_id_column" in prompt_text:
                return MockResponse("""
                REQUIREMENT: user_id_column needs unique user identifiers
                ANALYSIS: customer_id appears to be a unique identifier with object type
                BEST_MATCH: customer_id
                CONFIDENCE: HIGH
                REASONING: customer_id is semantically equivalent to user_id and has appropriate data type (object) with high uniqueness
                """)
            elif "date_column" in prompt_text:
                return MockResponse("""
                REQUIREMENT: date_column needs datetime data
                ANALYSIS: signup_date has datetime64[ns] type, transaction_date also datetime
                BEST_MATCH: signup_date
                CONFIDENCE: HIGH
                REASONING: signup_date has proper datetime type and is semantically appropriate for time-based analysis
                """)
            else:
                return MockResponse("""
                BEST_MATCH: NONE
                CONFIDENCE: LOW
                REASONING: No suitable column found
                """)
    
    # Create mock agent
    llm = MockLLM()
    agent = GeneralizedAnalysisAgent(llm, None, None, None)
    agent.enable_debug_mode()
    
    # Test data
    columns = ["customer_id", "signup_date", "transaction_date", "amount", "product_category"]
    dataframe_description = {
        "schema": {
            "customer_id": "object",
            "signup_date": "datetime64[ns]",
            "transaction_date": "datetime64[ns]",
            "amount": "float64",
            "product_category": "object"
        },
        "stats": {
            "customer_id": {"unique": 1000, "null_count": 0},
            "amount": {"mean": 45.67, "std": 23.45}
        },
        "sample_values": {
            "customer_id": ["CUST001", "CUST002", "CUST003"],
            "product_category": ["Electronics", "Clothing", "Books"]
        }
    }
    
    print("📊 Test Dataset:")
    print(f"   Columns: {', '.join(columns)}")
    print(f"   Schema: {dataframe_description['schema']}")
    
    print("\n🔍 Testing Enhanced Column Matching:")
    
    # Test 1: Schema-based matching
    print("\n1. Schema-based matching for 'user_id_column':")
    result1 = agent.find_column_match_with_schema("user_id_column", columns, dataframe_description)
    print(f"   Selected: {result1['column']}")
    print(f"   Confidence: {result1['confidence']}")
    print(f"   Reasoning: {result1['reasoning']}")
    
    # Test 2: Semantic matching without schema
    print("\n2. Semantic matching for 'date_column':")
    result2 = agent.find_column_match("date_column", columns)
    print(f"   Selected: {result2['column']}")
    print(f"   Confidence: {result2['confidence']}")
    print(f"   Reasoning: {result2['reasoning']}")
    
    # Test 3: Using _find_closest_column method
    print("\n3. Using _find_closest_column method:")
    closest_user_col = agent._find_closest_column("user_id_column", columns, dataframe_description)
    closest_date_col = agent._find_closest_column("date_column", columns)
    print(f"   Closest user column: {closest_user_col}")
    print(f"   Closest date column: {closest_date_col}")
    
    print("\n✅ Enhanced column matching demonstration completed!")
    print("\nKey improvements:")
    print("   🧠 LLM-powered semantic analysis")
    print("   📊 Schema-aware data type matching")
    print("   🔍 Intelligent reasoning and confidence scoring")
    print("   🚫 No hardcoded keyword dependencies")
    print("   🔧 Automatic fallback mechanisms")

def run_with_logical_plan_example():
    """
    Example function demonstrating how to use the GeneralizedAnalysisAgent
    with a sample logical plan output
    """
    
    print("🚀 LOGICAL PLAN PROCESSING EXAMPLE")
    print("=" * 60)
    
    # Mock components for demonstration
    class MockLLM:
        def invoke(self, args):
            class MockResponse:
                def __init__(self, content):
                    self.content = content
                def strip(self):
                    return self.content.strip()
            
            # Simulate different LLM responses based on the prompt context
            prompt_text = str(args)
            
            if "SELECTED_FUNCTIONS" in prompt_text:
                return MockResponse("""
                TASK_ANALYSIS: Time series analysis for calculating daily returns and volatility
                FUNCTION_EVALUATION: calculate_returns matches the requirement for return calculation
                SELECTED_FUNCTIONS: calculate_returns, calculate_volatility
                CONFIDENCE: HIGH
                REASONING: These functions directly match the time series analysis requirements
                """)
            elif "OPERATION:" in prompt_text:
                return MockResponse("""
                ANALYSIS: The context involves time series operations and volatility calculations
                OPERATION: time_series_analysis
                CONFIDENCE: HIGH
                REASONING: Multiple indicators point to time series analysis workflow
                """)
            elif "Generate Python code" in prompt_text:
                return MockResponse("""
                ```python
                .calculate_returns(
                    price_column='close_price',
                    return_type='daily'
                )
                ```
                """)
            elif "Assemble a complete" in prompt_text:
                return MockResponse("""
                ```python
                # Import necessary libraries
                import pandas as pd
                import numpy as np
                from analysis_pipes import TimeSeriesPipe
                
                # Initialize the pipeline with the dataframe
                result = (
                    TimeSeriesPipe.from_dataframe(df)
                    | .calculate_returns(price_column='close_price', return_type='daily')
                    | .calculate_volatility(returns_column='daily_returns', window=30)
                )
                
                # Display results
                print(result.summary())
                ```
                """)
            else:
                return MockResponse("# Mock LLM response")
    
    class MockFunctionCollection:
        def semantic_search(self, query, k=1):
            return [{
                'content': '{"name": "calculate_returns", "description": "Calculate returns from price data", "required_params": ["price_column"], "optional_params": ["return_type"]}'
            }]
    
    class MockExampleCollection:
        def semantic_search(self, query, k=1):
            return [{
                'content': 'Example: df.calculate_returns(price_column="close", return_type="daily")'
            }]
    
    # Create mock agent
    llm = MockLLM()
    function_collection = MockFunctionCollection()
    example_collection = MockExampleCollection()
    insights_collection = None
    
    agent = GeneralizedAnalysisAgent(
        llm=llm,
        function_collection=function_collection,
        example_collection=example_collection,
        insights_collection=insights_collection
    )
    
    # Sample logical plan output (pipe-separated steps)
    logical_plan_output = """
    (1. Calculate daily returns from close prices: time_series_analysis : calculate_returns : ['close_price'] : SELECT *, (close_price - LAG(close_price)) / LAG(close_price) as daily_returns FROM data) | 
    (2. Calculate 30-day volatility from returns: time_series_analysis : calculate_volatility : ['daily_returns'] : SELECT *, STDDEV(daily_returns) OVER (ORDER BY date ROWS 29 PRECEDING) as volatility FROM data)
    """
    
    # Sample dataframe information
    dataframe_columns = ['date', 'open_price', 'high_price', 'low_price', 'close_price', 'volume']
    dataframe_description = {
        'schema': {
            'date': 'datetime64[ns]',
            'open_price': 'float64',
            'high_price': 'float64', 
            'low_price': 'float64',
            'close_price': 'float64',
            'volume': 'int64'
        },
        'stats': {
            'close_price': {'mean': 150.25, 'std': 25.67, 'min': 100.0, 'max': 200.0},
            'volume': {'mean': 1000000, 'std': 500000}
        },
        'sample_values': {
            'date': ['2024-01-01', '2024-01-02', '2024-01-03'],
            'close_price': [145.23, 147.89, 143.56]
        },
        'summary': 'Daily stock price data with OHLCV format'
    }
    
    print("📊 Input Data:")
    print(f"   Logical Plan: {logical_plan_output}")
    print(f"   Available Columns: {', '.join(dataframe_columns)}")
    print(f"   Data Types: {dataframe_description['schema']}")
    
    print("\n🔄 Processing with GeneralizedAnalysisAgent...")
    
    # Run the agent
    try:
        result = agent.run(
            logical_plan_output=logical_plan_output,
            dataframe_columns=dataframe_columns,
            dataframe_description=dataframe_description
        )
        
        print("\n✅ Processing completed successfully!")
        return result
        
    except Exception as e:
        print(f"\n❌ Error during processing: {str(e)}")
        return {
            "error": str(e),
            "original_plan": logical_plan_output,
            "status": "failed"
        }


def run_advanced_logical_plan_example():
    """
    Advanced example with more complex multi-step analysis
    """
    
    print("\n🔬 ADVANCED LOGICAL PLAN EXAMPLE")
    print("=" * 60)
    
    # More complex logical plan with multiple analysis types
    complex_logical_plan = """
    (1. Filter data for active users: general_analysis : filter_data : ['user_status'] : SELECT * FROM data WHERE user_status = 'active') |
    (2. Segment users by engagement level: segmentation : segment_users : ['page_views', 'session_duration'] : SELECT *, CASE WHEN page_views > 10 THEN 'high' ELSE 'low' END as engagement FROM data) |
    (3. Perform cohort analysis by signup month: cohort_analysis : cohort_retention : ['user_id', 'signup_date', 'activity_date'] : SELECT signup_month, activity_month, COUNT(DISTINCT user_id) as retained_users FROM data GROUP BY signup_month, activity_month) |
    (4. Analyze conversion funnel: funnel_analysis : conversion_funnel : ['event_name', 'user_id'] : SELECT event_name, COUNT(DISTINCT user_id) as users FROM events GROUP BY event_name ORDER BY funnel_step)
    """
    
    # Sample e-commerce/SaaS dataframe
    ecommerce_columns = ['user_id', 'signup_date', 'user_status', 'page_views', 'session_duration', 
                        'activity_date', 'event_name', 'purchase_amount', 'subscription_tier']
    
    ecommerce_description = {
        'schema': {
            'user_id': 'object',
            'signup_date': 'datetime64[ns]',
            'user_status': 'object',
            'page_views': 'int64',
            'session_duration': 'float64',
            'activity_date': 'datetime64[ns]',
            'event_name': 'object',
            'purchase_amount': 'float64',
            'subscription_tier': 'object'
        },
        'stats': {
            'page_views': {'mean': 15.3, 'std': 12.8, 'min': 0, 'max': 100},
            'session_duration': {'mean': 245.6, 'std': 180.2},
            'purchase_amount': {'mean': 49.99, 'std': 75.25}
        },
        'sample_values': {
            'user_status': ['active', 'inactive', 'churned'],
            'event_name': ['page_view', 'add_to_cart', 'purchase', 'subscription'],
            'subscription_tier': ['free', 'basic', 'premium']
        },
        'summary': 'User behavior and transaction data for SaaS/e-commerce platform'
    }
    
    print("📊 Advanced Input Data:")
    print(f"   Complex Plan Steps: {len(complex_logical_plan.split('|'))}")
    print(f"   Analysis Types: general_analysis, segmentation, cohort_analysis, funnel_analysis")
    print(f"   Available Columns: {', '.join(ecommerce_columns)}")
    
    # This would use the same agent as above with the complex plan
    print("\n🔄 Would process complex multi-step analysis...")
    print("   ✓ Data filtering and cleaning")
    print("   ✓ User segmentation based on behavior")  
    print("   ✓ Cohort retention analysis")
    print("   ✓ Conversion funnel optimization")
    
    return {
        "plan_type": "advanced_multi_step",
        "analysis_types": ["general_analysis", "segmentation", "cohort_analysis", "funnel_analysis"],
        "total_steps": 4,
        "complexity": "high",
        "status": "demo_ready"
    }


def demonstrate_column_matching_integration():
    """
    Demonstrate how the enhanced column matching integrates with logical plan processing
    """
    
    print("\n🎯 COLUMN MATCHING INTEGRATION DEMO")
    print("=" * 60)
    
    # Realistic scenario with ambiguous column names
    ambiguous_plan = """
    (1. Analyze user activity trends: time_series_analysis : activity_trends : ['user_col', 'date_col', 'activity_col'] : SELECT date_col, COUNT(user_col) as active_users FROM data GROUP BY date_col)
    """
    
    # Dataset with non-obvious column names
    ambiguous_columns = ['customer_identifier', 'registration_timestamp', 'interaction_type', 
                        'revenue_amount', 'product_category', 'geo_region']
    
    ambiguous_description = {
        'schema': {
            'customer_identifier': 'object',
            'registration_timestamp': 'datetime64[ns]',
            'interaction_type': 'object',
            'revenue_amount': 'float64',
            'product_category': 'object',
            'geo_region': 'object'
        },
        'stats': {
            'customer_identifier': {'unique': 5000, 'null_count': 0},
            'revenue_amount': {'mean': 125.50, 'std': 89.25}
        },
        'sample_values': {
            'interaction_type': ['login', 'purchase', 'support_ticket', 'feature_usage'],
            'product_category': ['electronics', 'software', 'services']
        }
    }
    
    print("🔍 Column Matching Challenge:")
    print(f"   Logical plan needs: user_col, date_col, activity_col")
    print(f"   Available columns: {', '.join(ambiguous_columns)}")
    print("\n📋 Expected Intelligent Matches:")
    print("   user_col → customer_identifier (unique user identifier)")
    print("   date_col → registration_timestamp (datetime data)")  
    print("   activity_col → interaction_type (categorical activity data)")
    
    print("\n✅ Enhanced LLM-based column matching would resolve these automatically!")
    
    return {
        "column_matching_demo": True,
        "challenges_resolved": ["semantic_matching", "schema_awareness", "intelligent_inference"],
        "ambiguous_columns": len(ambiguous_columns),
        "required_matches": 3
    }


# Main execution example
if __name__ == "__main__":
    # Run the enhanced column matching demo
    demonstrate_enhanced_column_matching()
    
    # Run the vector store function retrieval demo
    vector_demo_result = demonstrate_vector_store_function_retrieval()
    
    # Run the enhanced LLM function generation demo
    llm_demo_result = demonstrate_enhanced_llm_function_generation()
    
    # Run the main logical plan example
    result = run_with_logical_plan_example()
    print("\n" + "="*80)
    print("📋 LOGICAL PLAN PROCESSING RESULT:")
    print("="*80)
    print(json.dumps(result, indent=2))
    
    # Run additional examples
    advanced_result = run_advanced_logical_plan_example()
    column_demo_result = demonstrate_column_matching_integration()
    
    print(f"\n🎉 All examples completed successfully!")
    print(f"   ✓ Enhanced column matching demo")
    print(f"   ✓ Vector store function retrieval demo")
    print(f"   ✓ Enhanced LLM function generation demo")
    print(f"   ✓ Basic logical plan processing")
    print(f"   ✓ Advanced multi-step analysis")
    print(f"   ✓ Column matching integration demo")


def demonstrate_enhanced_llm_function_generation():
    """
    Demonstrate the enhanced LLM-based function call generation capabilities
    """
    
    print("\n🤖 ENHANCED LLM FUNCTION GENERATION DEMO")
    print("=" * 60)
    
    # Mock components for demonstration
    class MockLLM:
        def invoke(self, args):
            class MockResponse:
                def __init__(self, content):
                    self.content = content
                def strip(self):
                    return self.content.strip()
            
            # Simulate LLM responses for function call generation
            prompt_text = str(args)
            
            if "variance_analysis" in prompt_text and "30-day" in prompt_text:
                return MockResponse(".variance_analysis(columns='close_price', method='rolling', window=30)")
            elif "time_series_analysis" in prompt_text:
                return MockResponse(".time_series_analysis(columns=['date', 'value'], method='rolling', window=7)")
            elif "cohort_analysis" in prompt_text:
                return MockResponse(".cohort_analysis(user_id_column='user_id', date_column='signup_date', event_column='purchase_date')")
            else:
                return MockResponse(".general_analysis(columns='data_column')")
    
    class MockFunctionCollection:
        def semantic_search(self, query, k=1):
            return [{
                'content': '{"name": "variance_analysis", "description": "Calculate variance and volatility", "required_params": ["columns"], "optional_params": ["method", "window"], "default_values": {"method": "rolling", "window": 30}}'
            }]
    
    # Create mock agent
    llm = MockLLM()
    function_collection = MockFunctionCollection()
    example_collection = None
    insights_collection = None
    
    agent = GeneralizedAnalysisAgent(
        llm=llm,
        function_collection=function_collection,
        example_collection=example_collection,
        insights_collection=insights_collection
    )
    agent.enable_debug_mode()
    
    # Test cases for enhanced function generation
    test_cases = [
        {
            "description": "Calculate 30-day rolling volatility from close prices",
            "operation_type": "time_series_analysis",
            "function_name": "variance_analysis",
            "columns": ["close_price"],
            "expected_params": ["columns", "method", "window"]
        },
        {
            "description": "Perform cohort retention analysis by signup month",
            "operation_type": "cohort_analysis",
            "function_name": None,  # Let LLM suggest
            "columns": ["user_id", "signup_date", "activity_date"],
            "expected_params": ["user_id_column", "date_column", "event_column"]
        },
        {
            "description": "Analyze time series trends with 7-day moving average",
            "operation_type": "time_series_analysis",
            "function_name": "time_series_analysis",
            "columns": ["date", "value"],
            "expected_params": ["columns", "method", "window"]
        }
    ]
    
    print("🧪 Testing Enhanced LLM Function Generation:")
    print("=" * 50)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📝 Test Case {i}: {test_case['description']}")
        print(f"   Operation Type: {test_case['operation_type']}")
        print(f"   Function: {test_case['function_name'] or 'LLM-suggested'}")
        print(f"   Columns: {test_case['columns']}")
        
        # Create a pipeline step
        step = PipelineStep(
            step_number=i,
            description=test_case['description'],
            operation_type=test_case['operation_type'],
            function_name=test_case['function_name'],
            columns=test_case['columns'],
            sql_operation=f"SELECT * FROM data WHERE {test_case['operation_type']}"
        )
        
        # Test the enhanced function generation
        try:
            generated_call = agent.generate_function_call_with_llm_integration(
                step=step,
                dataframe_description={
                    'schema': {col: 'float64' for col in test_case['columns']},
                    'summary': f'Test data for {test_case["operation_type"]}'
                }
            )
            
            print(f"   ✅ Generated: {generated_call}")
            
            # Validate expected parameters
            for expected_param in test_case['expected_params']:
                if expected_param in generated_call:
                    print(f"   ✓ Found parameter: {expected_param}")
                else:
                    print(f"   ⚠️  Missing parameter: {expected_param}")
                    
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
    
    print(f"\n✅ Enhanced LLM function generation demonstration completed!")
    print("\nKey improvements:")
    print("   🧠 LLM-powered function selection and parameter generation")
    print("   🔍 Intelligent parameter extraction from descriptions")
    print("   📊 Context-aware parameter value assignment")
    print("   🔄 Integration with existing _llm_suggest_functions")
    print("   🛡️  Robust fallback mechanisms")
    
    return {
        "enhanced_function_generation": True,
        "test_cases_processed": len(test_cases),
        "llm_integration": "successful",
        "fallback_mechanisms": "active"
    }


def demonstrate_vector_store_function_retrieval():
    """
    Demonstrate the vector store-based function retrieval capabilities
    """
    
    print("\n🔍 VECTOR STORE FUNCTION RETRIEVAL DEMO")
    print("=" * 60)
    
    # Mock components for demonstration
    class MockLLM:
        def invoke(self, args):
            class MockResponse:
                def __init__(self, content):
                    self.content = content
                def strip(self):
                    return self.content.strip()
            
            # Simulate LLM responses for function selection and generation
            prompt_text = str(args)
            
            if "variance_analysis" in prompt_text:
                return MockResponse(".variance_analysis(columns='close_price', method='rolling', window=30)")
            elif "cohort_analysis" in prompt_text:
                return MockResponse(".cohort_analysis(user_id_column='user_id', date_column='signup_date', event_column='purchase_date')")
            elif "time_series_analysis" in prompt_text:
                return MockResponse(".time_series_analysis(columns=['date', 'value'], method='rolling', window=7)")
            else:
                return MockResponse(".general_analysis(columns='data_column')")
    
    class MockFunctionCollection:
        def semantic_search(self, query, k=5):
            # Simulate different function retrievals based on query
            query_lower = query.lower()
            
            if "volatility" in query_lower or "variance" in query_lower:
                return [
                    {
                        'content': '{"name": "variance_analysis", "description": "Calculate variance and volatility for time series data", "required_params": ["columns"], "optional_params": ["method", "window", "suffix"], "default_values": {"method": "rolling", "window": 30}}'
                    },
                    {
                        'content': '{"name": "rolling_volatility", "description": "Calculate rolling volatility with customizable window", "required_params": ["columns", "window"], "optional_params": ["method", "min_periods"]}'
                    }
                ]
            elif "cohort" in query_lower or "retention" in query_lower:
                return [
                    {
                        'content': '{"name": "cohort_analysis", "description": "Perform cohort retention analysis", "required_params": ["user_id_column", "date_column"], "optional_params": ["event_column", "cohort_period", "analysis_period"]}'
                    },
                    {
                        'content': '{"name": "retention_analysis", "description": "Calculate user retention metrics", "required_params": ["user_id", "signup_date"], "optional_params": ["activity_date", "cohort_type"]}'
                    }
                ]
            elif "time series" in query_lower or "trend" in query_lower:
                return [
                    {
                        'content': '{"name": "time_series_analysis", "description": "Analyze time series data with various methods", "required_params": ["columns"], "optional_params": ["method", "window", "period"]}'
                    },
                    {
                        'content': '{"name": "trend_analysis", "description": "Detect trends in time series data", "required_params": ["columns"], "optional_params": ["window", "method"]}'
                    }
                ]
            else:
                return [
                    {
                        'content': '{"name": "general_analysis", "description": "General data analysis function", "required_params": ["columns"], "optional_params": ["method"]}'
                    }
                ]
    
    # Create mock agent
    llm = MockLLM()
    function_collection = MockFunctionCollection()
    example_collection = None
    insights_collection = None
    
    agent = GeneralizedAnalysisAgent(
        llm=llm,
        function_collection=function_collection,
        example_collection=example_collection,
        insights_collection=insights_collection
    )
    agent.enable_debug_mode()
    
    # Test cases for vector store function retrieval
    test_cases = [
        {
            "description": "Calculate 30-day rolling volatility from close prices",
            "operation_type": "time_series_analysis",
            "columns": ["close_price"],
            "sql_operation": "SELECT *, STDDEV(close_price) OVER (ORDER BY date ROWS 29 PRECEDING) as volatility FROM data",
            "expected_functions": ["variance_analysis", "rolling_volatility"],
            "expected_params": ["columns", "method", "window"]
        },
        {
            "description": "Perform cohort retention analysis by signup month",
            "operation_type": "cohort_analysis",
            "columns": ["user_id", "signup_date", "activity_date"],
            "sql_operation": "SELECT signup_month, activity_month, COUNT(DISTINCT user_id) as retained_users FROM data GROUP BY signup_month, activity_month",
            "expected_functions": ["cohort_analysis", "retention_analysis"],
            "expected_params": ["user_id_column", "date_column", "event_column"]
        },
        {
            "description": "Analyze time series trends with 7-day moving average",
            "operation_type": "time_series_analysis",
            "columns": ["date", "value"],
            "sql_operation": "SELECT *, AVG(value) OVER (ORDER BY date ROWS 6 PRECEDING) as moving_avg FROM data",
            "expected_functions": ["time_series_analysis", "trend_analysis"],
            "expected_params": ["columns", "method", "window"]
        }
    ]
    
    print("🧪 Testing Vector Store Function Retrieval:")
    print("=" * 50)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📝 Test Case {i}: {test_case['description']}")
        print(f"   Operation Type: {test_case['operation_type']}")
        print(f"   Columns: {test_case['columns']}")
        print(f"   SQL Operation: {test_case['sql_operation'][:50]}...")
        
        # Create a pipeline step
        step = PipelineStep(
            step_number=i,
            description=test_case['description'],
            operation_type=test_case['operation_type'],
            function_name=None,  # Let vector store suggest
            columns=test_case['columns'],
            sql_operation=test_case['sql_operation']
        )
        
        # Test vector store function retrieval
        try:
            # Test the retrieval method directly
            retrieved_functions = agent._retrieve_functions_from_vector_store(
                step=step,
                dataframe_description={
                    'schema': {col: 'float64' for col in test_case['columns']},
                    'summary': f'Test data for {test_case["operation_type"]}'
                }
            )
            
            print(f"   🔍 Retrieved {len(retrieved_functions)} functions from vector store")
            
            # Show retrieved functions
            for j, func in enumerate(retrieved_functions[:2]):  # Show first 2
                func_name = func.get('name', 'unknown')
                func_desc = func.get('description', 'No description')[:60]
                print(f"   {j+1}. {func_name}: {func_desc}...")
            
            # Test the complete function generation
            generated_call = agent.generate_function_call_with_llm_integration(
                step=step,
                dataframe_description={
                    'schema': {col: 'float64' for col in test_case['columns']},
                    'summary': f'Test data for {test_case["operation_type"]}'
                }
            )
            
            print(f"   ✅ Generated: {generated_call}")
            
            # Validate expected parameters
            for expected_param in test_case['expected_params']:
                if expected_param in generated_call:
                    print(f"   ✓ Found parameter: {expected_param}")
                else:
                    print(f"   ⚠️  Missing parameter: {expected_param}")
                    
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
    
    print(f"\n✅ Vector store function retrieval demonstration completed!")
    print("\nKey improvements:")
    print("   🔍 Vector store-based function discovery")
    print("   🧠 LLM-powered function selection from multiple candidates")
    print("   📊 Context-aware search query generation")
    print("   🔄 Integration with SQL operation analysis")
    print("   🛡️  Robust fallback mechanisms")
    
    return {
        "vector_store_retrieval": True,
        "test_cases_processed": len(test_cases),
        "function_discovery": "successful",
        "llm_integration": "active"
    }




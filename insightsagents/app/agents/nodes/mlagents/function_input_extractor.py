from typing import Dict, List, Any, Optional, Union
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers.string import StrOutputParser
import json
import re
from abc import ABC, abstractmethod

class BaseInputExtractor(ABC):
    """Enhanced base class for input extractors with intelligent parameter extraction"""
    
    def __init__(self, llm, example_collection, function_collection, insights_collection):
        self.llm = llm
        self.example_collection = example_collection
        self.function_collection = function_collection
        self.insights_collection = insights_collection
        
        # Common parameter patterns for different data types
        self.column_type_patterns = {
            "date": ["date", "time", "timestamp", "created", "updated", "day", "month", "year"],
            "user_id": ["user", "customer", "client", "id", "identifier", "uid"],
            "value": ["value", "amount", "price", "cost", "revenue", "sales", "metric"],
            "category": ["category", "type", "group", "segment", "class", "label"],
            "event": ["event", "action", "activity", "step", "stage"],
            "numeric": ["count", "quantity", "number", "rate", "percent", "ratio"]
        }
    
    def extract_inputs(self, context: str, function_name: str, columns: List[str], dataframe_description: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generic input extraction using LLM reasoning and function definitions
        
        Args:
            context: Natural language context describing the task
            function_name: Name of the function to extract inputs for
            columns: Available columns in the dataset
            dataframe_description: Optional schema and metadata about the dataframe
            
        Returns:
            Dictionary of extracted inputs for the function
        """
        # Get function definition
        function_spec = self._get_function_specification(function_name)
        
        # Get function examples
        function_examples = self._get_function_examples(function_name)
        
        # Use LLM to intelligently extract parameters
        extracted_params = self._llm_extract_parameters(
            context=context,
            function_name=function_name,
            function_spec=function_spec,
            function_examples=function_examples,
            columns=columns,
            dataframe_description=dataframe_description
        )
        
        # Enhance with intelligent column mapping
        enhanced_params = self._enhance_with_column_mapping(
            extracted_params, columns, dataframe_description
        )
        
        # Validate and set defaults
        final_params = self._validate_and_set_defaults(
            enhanced_params, function_spec
        )
        
        return final_params
    
    def _get_function_specification(self, function_name: str) -> Dict[str, Any]:
        """Retrieve function specification from the function collection"""
        try:
            if function_name and hasattr(self.function_collection, 'semantic_search'):
                results = self.function_collection.semantic_search(function_name, k=1)
                if results and len(results) > 0:
                    result = results[0]
                    if isinstance(result, dict):
                        spec = result.get('content', {})
                        if isinstance(spec, str):
                            try:
                                spec = json.loads(spec)
                            except json.JSONDecodeError:
                                spec = {"description": spec}
                        return spec
            elif function_name and hasattr(self.function_collection, 'semantic_searches'):
                results = self.function_collection.semantic_searches([function_name], n_results=1)
                if results and results.get('documents') and len(results['documents']) > 0 and len(results['documents'][0]) > 0:
                    spec = results['documents'][0][0]
                    if isinstance(spec, str):
                        try:
                            spec = json.loads(spec)
                        except json.JSONDecodeError:
                            spec = {"description": spec}
                    return spec
        except Exception as e:
            print(f"Error retrieving function spec for {function_name}: {e}")
        
        # Fallback to basic spec
        return {
            "function_name": function_name,
            "required_params": [],
            "optional_params": [],
            "description": f"Function: {function_name}"
        }
    
    def _get_function_examples(self, function_name: str) -> List[Dict[str, Any]]:
        """Retrieve function examples from the example collection"""
        try:
            if function_name and hasattr(self.example_collection, 'semantic_search'):
                results = self.example_collection.semantic_search(function_name, k=3)
                if results:
                    return [result.get('content', {}) for result in results if isinstance(result, dict)]
            elif function_name and hasattr(self.example_collection, 'semantic_searches'):
                results = self.example_collection.semantic_searches([function_name], n_results=3)
                if results and results.get('documents') and len(results['documents']) > 0:
                    return results['documents'][0]
        except Exception as e:
            print(f"Error retrieving examples for {function_name}: {e}")
        
        return []
    
    def _llm_extract_parameters(self, context: str, function_name: str, function_spec: Dict[str, Any], 
                               function_examples: List[Dict[str, Any]], columns: List[str], 
                               dataframe_description: Dict[str, Any] = None) -> Dict[str, Any]:
        """Use LLM to intelligently extract parameters from context"""
        
        # Create a comprehensive prompt for parameter extraction
        extraction_prompt = PromptTemplate(
            input_variables=[
                "context", "function_name", "function_spec", "function_examples", 
                "columns", "dataframe_description"
            ],
            template="""
            You are an expert data scientist who extracts function parameters from natural language descriptions.
            
            TASK CONTEXT:
            {context}
            
            FUNCTION TO USE:
            {function_name}
            
            FUNCTION SPECIFICATION:
            {function_spec}
            
            FUNCTION EXAMPLES:
            {function_examples}
            
            AVAILABLE COLUMNS:
            {columns}
            
            DATAFRAME DESCRIPTION:
            {dataframe_description}
            
            Your task is to extract the appropriate parameters for the {function_name} function based on:
            1. The task context and what needs to be accomplished
            2. The function specification (required and optional parameters)
            3. Examples of how this function has been used before
            4. The available columns in the dataset
            5. The dataframe schema and description
            
            EXTRACTION RULES:
            1. Map context requirements to function parameters intelligently
            2. Choose appropriate columns based on their names and types
            3. Set reasonable default values for optional parameters
            4. Infer parameter values from the context description
            5. Use examples to understand typical parameter patterns
            
            OUTPUT FORMAT:
            Return a JSON object with the extracted parameters:
            {{
                "parameter_name": "extracted_value",
                "column_parameter": "best_matching_column",
                "numeric_parameter": numeric_value,
                "list_parameter": ["item1", "item2"],
                "_reasoning": {{
                    "parameter_name": "Why this value was chosen",
                    "column_parameter": "Why this column was selected"
                }}
            }}
            
            Only include parameters that can be reasonably inferred from the context.
            Include a _reasoning section explaining your parameter choices.
            """
        )
        
        # Create the extraction chain
        extraction_chain = extraction_prompt | self.llm | StrOutputParser()
        
        # Format inputs for the prompt
        columns_str = ", ".join(columns) if columns else "No columns specified"
        dataframe_desc_str = json.dumps(dataframe_description, indent=2) if dataframe_description else "No description provided"
        function_spec_str = json.dumps(function_spec, indent=2)
        examples_str = json.dumps(function_examples[:2], indent=2) if function_examples else "No examples available"
        
        try:
            # Run the extraction
            result = extraction_chain.invoke({
                "context": context,
                "function_name": function_name,
                "function_spec": function_spec_str,
                "function_examples": examples_str,
                "columns": columns_str,
                "dataframe_description": dataframe_desc_str
            })
            
            # Parse the JSON result
            result = result.strip()
            if result.startswith("```json"):
                result = result[7:]
            if result.endswith("```"):
                result = result[:-3]
            
            extracted_params = json.loads(result.strip())
            return extracted_params
            
        except Exception as e:
            print(f"Error in LLM parameter extraction: {e}")
            # Fallback to basic extraction
            return self._fallback_parameter_extraction(context, function_name, columns)
    
    def _fallback_parameter_extraction(self, context: str, function_name: str, columns: List[str]) -> Dict[str, Any]:
        """Fallback parameter extraction using pattern matching"""
        params = {"function_name": function_name}
        
        # Basic column mapping based on common patterns
        if columns:
            context_lower = context.lower()
            
            # Look for date columns
            date_cols = [col for col in columns if any(pattern in col.lower() for pattern in self.column_type_patterns["date"])]
            if date_cols and ("time" in context_lower or "date" in context_lower):
                params["date_column"] = date_cols[0]
            
            # Look for ID columns
            id_cols = [col for col in columns if any(pattern in col.lower() for pattern in self.column_type_patterns["user_id"])]
            if id_cols and ("user" in context_lower or "customer" in context_lower):
                params["user_id_column"] = id_cols[0]
            
            # Look for value columns
            value_cols = [col for col in columns if any(pattern in col.lower() for pattern in self.column_type_patterns["value"])]
            if value_cols and ("value" in context_lower or "amount" in context_lower):
                params["value_column"] = value_cols[0]
            
            # Default to using provided columns
            if len(columns) > 0:
                params["columns"] = columns
        
        return params
    
    def _enhance_with_column_mapping(self, params: Dict[str, Any], columns: List[str], 
                                   dataframe_description: Dict[str, Any] = None) -> Dict[str, Any]:
        """Enhance parameters with intelligent column mapping"""
        enhanced_params = params.copy()
        
        if not columns:
            return enhanced_params
        
        # Use LLM for intelligent column mapping if we have column parameters
        column_params = [key for key in params.keys() if key.endswith('_column') or key == 'columns']
        
        if column_params and dataframe_description:
            enhanced_mapping = self._llm_column_mapping(params, columns, dataframe_description)
            enhanced_params.update(enhanced_mapping)
        
        return enhanced_params
    
    def _llm_column_mapping(self, params: Dict[str, Any], columns: List[str], 
                           dataframe_description: Dict[str, Any]) -> Dict[str, Any]:
        """Use LLM for intelligent column mapping"""
        
        mapping_prompt = PromptTemplate(
            input_variables=["params", "columns", "dataframe_description"],
            template="""
            You are a data scientist who maps function parameters to the best matching columns in a dataset.
            
            CURRENT PARAMETERS:
            {params}
            
            AVAILABLE COLUMNS:
            {columns}
            
            DATAFRAME DESCRIPTION:
            {dataframe_description}
            
            Your task is to map any column-related parameters to the best matching columns from the available columns.
            Consider:
            1. Column names and their semantic meaning
            2. Data types from the schema
            3. Column descriptions if available
            4. Common naming conventions
            
            Return ONLY the column parameter mappings that need to be updated in JSON format:
            {{
                "parameter_name": "best_matching_column",
                "another_column_param": "another_best_match"
            }}
            
            Only include parameters that need to be updated or corrected.
            """
        )
        
        mapping_chain = mapping_prompt | self.llm | StrOutputParser()
        
        try:
            result = mapping_chain.invoke({
                "params": json.dumps(params, indent=2),
                "columns": ", ".join(columns),
                "dataframe_description": json.dumps(dataframe_description, indent=2)
            })
            
            # Parse result
            result = result.strip()
            if result.startswith("```json"):
                result = result[7:]
            if result.endswith("```"):
                result = result[:-3]
            
            return json.loads(result.strip())
            
        except Exception as e:
            print(f"Error in column mapping: {e}")
            return {}
    
    def _validate_and_set_defaults(self, params: Dict[str, Any], function_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Validate parameters and set intelligent defaults"""
        validated_params = params.copy()
        
        # Remove reasoning section if present
        if "_reasoning" in validated_params:
            del validated_params["_reasoning"]
        
        # Set intelligent defaults based on function type and common patterns
        defaults = self._get_intelligent_defaults(params.get("function_name", ""), function_spec)
        
        # Apply defaults for missing required parameters
        for param, default_value in defaults.items():
            if param not in validated_params:
                validated_params[param] = default_value
        
        return validated_params
    
    def _get_intelligent_defaults(self, function_name: str, function_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Get intelligent defaults based on function type and common patterns"""
        defaults = {}
        
        # Time series defaults
        if "variance" in function_name or "rolling" in function_name:
            defaults.update({
                "window_size": 5,
                "method": "rolling"
            })
        
        if "lag" in function_name or "lead" in function_name:
            defaults.update({
                "periods": 1
            })
        
        # Cohort analysis defaults
        if "cohort" in function_name:
            defaults.update({
                "time_period": "month",
                "max_periods": 12
            })
        
        # Segmentation defaults
        if "dbscan" in function_name:
            defaults.update({
                "eps": 0.5,
                "min_samples": 5
            })
        
        if "hierarchical" in function_name:
            defaults.update({
                "n_clusters": 3,
                "linkage": "ward"
            })
        
        # Risk analysis defaults
        if "var" in function_name:
            defaults.update({
                "confidence_level": 0.05,
                "method": "historical"
            })
        
        if "distribution" in function_name:
            defaults.update({
                "distributions": ["normal", "t", "skewnorm"]
            })
        
        # Moving average defaults
        if "moving_average" in function_name:
            defaults.update({
                "window_size": 30
            })
        
        return defaults

class SmartTimeSeriesExtractor(BaseInputExtractor):
    """Smart time series input extractor with context awareness"""
    
    def _get_intelligent_defaults(self, function_name: str, function_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Time series specific intelligent defaults"""
        defaults = super()._get_intelligent_defaults(function_name, function_spec)
        
        # Add time series specific defaults
        if "custom_calculation" in function_name:
            defaults.update({
                "calculation": "pct_change"  # Common for returns calculation
            })
        
        if "cumulative" in function_name:
            defaults.update({
                "normalize": True
            })
        
        return defaults

class SmartCohortAnalysisExtractor(BaseInputExtractor):
    """Smart cohort analysis input extractor"""
    
    def _get_intelligent_defaults(self, function_name: str, function_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Cohort analysis specific intelligent defaults"""
        defaults = super()._get_intelligent_defaults(function_name, function_spec)
        
        # Add cohort specific defaults
        if "retention" in function_name:
            defaults.update({
                "user_id_column": "user_id",
                "date_column": "date"
            })
        
        if "lifetime_value" in function_name:
            defaults.update({
                "user_id_column": "user_id",
                "value_column": "value",
                "date_column": "date"
            })
        
        return defaults

class SmartSegmentationExtractor(BaseInputExtractor):
    """Smart segmentation input extractor"""
    
    def _get_intelligent_defaults(self, function_name: str, function_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Segmentation specific intelligent defaults"""
        defaults = super()._get_intelligent_defaults(function_name, function_spec)
        
        # Add segmentation specific logic
        if "rule_based" in function_name:
            defaults.update({
                "rules": []  # Will be populated by LLM extraction
            })
        
        return defaults

class SmartTrendAnalysisExtractor(BaseInputExtractor):
    """Smart trend analysis input extractor"""
    
    def _get_intelligent_defaults(self, function_name: str, function_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Trend analysis specific intelligent defaults"""
        defaults = super()._get_intelligent_defaults(function_name, function_spec)
        
        # Add trend analysis defaults
        if "aggregate" in function_name:
            defaults.update({
                "time_period": "day",
                "date_column": "date"
            })
        
        if "growth" in function_name:
            defaults.update({
                "periods": 1
            })
        
        return defaults

class SmartRiskAnalysisExtractor(BaseInputExtractor):
    """Smart risk analysis input extractor"""
    
    def _get_intelligent_defaults(self, function_name: str, function_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Risk analysis specific intelligent defaults"""
        defaults = super()._get_intelligent_defaults(function_name, function_spec)
        
        # Add risk analysis defaults
        if "monte_carlo" in function_name:
            defaults.update({
                "n_simulations": 10000,
                "random_seed": 42
            })
        
        if "stress_test" in function_name:
            defaults.update({
                "scenarios": ["market_crash", "volatility_spike"]
            })
        
        return defaults

class SmartFunnelAnalysisExtractor(BaseInputExtractor):
    """Smart funnel analysis input extractor"""
    
    def _get_intelligent_defaults(self, function_name: str, function_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Funnel analysis specific intelligent defaults"""
        defaults = super()._get_intelligent_defaults(function_name, function_spec)
        
        # Add funnel analysis defaults
        if "funnel" in function_name:
            defaults.update({
                "event_column": "event",
                "user_id_column": "user_id",
                "timestamp_column": "timestamp"
            })
        
        if "segment" in function_name:
            defaults.update({
                "min_users": 10
            })
        
        return defaults

class SmartGeneralAnalysisExtractor(BaseInputExtractor):
    """Smart general analysis input extractor for SQL-like operations"""
    
    def extract_inputs(self, context: str, function_name: str, columns: List[str], 
                      dataframe_description: Dict[str, Any] = None) -> Dict[str, Any]:
        """Extract inputs for general analysis operations with SQL-like intelligence"""
        
        # For general operations, use pattern matching combined with LLM
        context_lower = context.lower()
        inputs = {
            "columns": columns,
            "operation": "general_analysis"
        }
        
        # Detect operation type from context
        if "filter" in context_lower:
            inputs["operation"] = "filter"
            inputs.update(self._extract_filter_conditions(context, columns))
        elif "group" in context_lower or "aggregate" in context_lower:
            inputs["operation"] = "groupby"
            inputs.update(self._extract_groupby_params(context, columns))
        elif "sort" in context_lower:
            inputs["operation"] = "sort"
            inputs.update(self._extract_sort_params(context, columns))
        elif "visualize" in context_lower or "plot" in context_lower:
            inputs["operation"] = "visualization"
            inputs.update(self._extract_viz_params(context, columns))
        elif "validate" in context_lower:
            inputs["operation"] = "validation"
        elif "interpret" in context_lower:
            inputs["operation"] = "interpretation"
        
        return inputs
    
    def _extract_filter_conditions(self, context: str, columns: List[str]) -> Dict[str, Any]:
        """Extract filter conditions from context"""
        conditions = {}
        
        # Common filter patterns
        if "12 months" in context or "1 year" in context:
            conditions["filter_condition"] = "date >= (current_date - interval '12 months')"
        elif "last" in context and "days" in context:
            # Extract number of days
            days_match = re.search(r'(\d+)\s*days?', context)
            if days_match:
                days = days_match.group(1)
                conditions["filter_condition"] = f"date >= (current_date - interval '{days} days')"
        
        return conditions
    
    def _extract_groupby_params(self, context: str, columns: List[str]) -> Dict[str, Any]:
        """Extract groupby parameters from context"""
        params = {}
        
        # Look for grouping columns
        group_cols = []
        for col in columns:
            if col.lower() in context.lower() and any(term in col.lower() for term in ["group", "category", "type", "segment"]):
                group_cols.append(col)
        
        if group_cols:
            params["groupby_columns"] = group_cols
        
        return params
    
    def _extract_sort_params(self, context: str, columns: List[str]) -> Dict[str, Any]:
        """Extract sort parameters from context"""
        params = {}
        
        # Detect sort direction
        if "descending" in context.lower() or "desc" in context.lower():
            params["ascending"] = False
        else:
            params["ascending"] = True
        
        return params
    
    def _extract_viz_params(self, context: str, columns: List[str]) -> Dict[str, Any]:
        """Extract visualization parameters from context"""
        params = {}
        
        # Detect chart type
        if "line" in context.lower():
            params["chart_type"] = "line"
        elif "bar" in context.lower():
            params["chart_type"] = "bar"
        elif "histogram" in context.lower():
            params["chart_type"] = "histogram"
        elif "scatter" in context.lower():
            params["chart_type"] = "scatter"
        else:
            params["chart_type"] = "auto"
        
        return params

# Factory function to create the appropriate extractor
def create_input_extractor(analysis_type: str, llm, example_collection, function_collection, insights_collection) -> BaseInputExtractor:
    """
    Factory function to create the appropriate input extractor based on analysis type
    
    Args:
        analysis_type: Type of analysis (time_series, cohort_analysis, etc.)
        llm: Language model instance
        example_collection: Examples collection
        function_collection: Functions collection  
        insights_collection: Insights collection
        
    Returns:
        Appropriate input extractor instance
    """
    extractor_map = {
        "time_series_analysis": SmartTimeSeriesExtractor,
        "time series operation": SmartTimeSeriesExtractor,
        "cohort_analysis": SmartCohortAnalysisExtractor,
        "cohort analysis operation": SmartCohortAnalysisExtractor,
        "segmentation": SmartSegmentationExtractor,
        "segmentation operation": SmartSegmentationExtractor,
        "trend_analysis": SmartTrendAnalysisExtractor,
        "trend analysis operation": SmartTrendAnalysisExtractor,
        "risk_analysis": SmartRiskAnalysisExtractor,
        "risk analysis operation": SmartRiskAnalysisExtractor,
        "funnel_analysis": SmartFunnelAnalysisExtractor,
        "funnel analysis operation": SmartFunnelAnalysisExtractor,
        "general_analysis": SmartGeneralAnalysisExtractor,
        "general analysis operation": SmartGeneralAnalysisExtractor
    }
    
    extractor_class = extractor_map.get(analysis_type, SmartGeneralAnalysisExtractor)
    return extractor_class(llm, example_collection, function_collection, insights_collection)

# Example usage
if __name__ == "__main__":
    # Mock components for demonstration
    class MockLLM:
        def __call__(self, prompt):
            return '{"columns": ["price"], "window_size": 5, "method": "rolling"}'
    
    class MockCollection:
        def semantic_search(self, query, k=5):
            return [{"content": {"function_name": "variance_analysis", "required_params": ["columns"]}}]
    
    # Create extractor
    llm = MockLLM()
    collections = MockCollection()
    
    extractor = create_input_extractor(
        "time_series_analysis", 
        llm, collections, collections, collections
    )
    
    # Extract inputs
    result = extractor.extract_inputs(
        context="Calculate 5-day rolling variance of stock prices",
        function_name="variance_analysis",
        columns=["date", "price", "volume"],
        dataframe_description={"schema": {"price": "float64"}}
    )
    
    print("Extracted inputs:", result)
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import json
from pydantic import BaseModel, Field
from langgraph.graph import END, StateGraph
from enum import Enum
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.core.dependencies import get_llm
# State modeling for LangGraph
class DataFrameAnalysisState(BaseModel):
    """State for the dataframe analysis pipeline."""
    dataframe_info: Dict[str, Any] = Field(..., description="Basic information about the dataframe")
    schema: Dict[str, Any] = Field(default_factory=dict, description="Schema of the dataframe")
    sample_rows: List[Dict[str, Any]] = Field(default_factory=list, description="Sample rows from the dataframe")
    statistics: Dict[str, Any] = Field(default_factory=dict, description="Statistical summary of the dataframe")
    time_series_column: Optional[str] = Field(None, description="Detected time series column, if any")
    groupby_columns: List[str] = Field(default_factory=list, description="Suggested groupby columns")
    aggregation_functions: Dict[str, List[str]] = Field(default_factory=dict, description="Suggested aggregation functions by column")
    data_types: Dict[str, str] = Field(default_factory=dict, description="Data types of columns")
    data_patterns: Dict[str, Any] = Field(default_factory=dict, description="Detected patterns in the data")
    outliers_info: Dict[str, Any] = Field(default_factory=dict, description="Information about outliers")
    missing_data_info: Dict[str, Any] = Field(default_factory=dict, description="Information about missing data")
    correlations: Dict[str, Dict[str, float]] = Field(default_factory=dict, description="Correlation matrix")
    suggested_functions: List[Dict[str, Any]] = Field(default_factory=list, description="Suggested functions for analysis")
    context: Optional[str] = Field(None, description="Additional context about the dataframe")
    errors: List[str] = Field(default_factory=list, description="Errors encountered during the process")


class AnalysisNodeType(str, Enum):
    """Types of nodes in the dataframe analysis pipeline."""
    SCHEMA_ANALYZER = "schema_analyzer"
    STATISTICS_CALCULATOR = "statistics_calculator"
    TIME_SERIES_DETECTOR = "time_series_detector"
    GROUPBY_SUGGESTER = "groupby_suggester"
    AGGREGATION_SUGGESTER = "aggregation_suggester"
    CORRELATION_ANALYZER = "correlation_analyzer"
    MISSING_DATA_ANALYZER = "missing_data_analyzer"
    FUNCTION_SUGGESTER = "function_suggester"
    CONTEXT_GENERATOR = "context_generator"




# Node implementations
def schema_analyzer(state: DataFrameAnalysisState) -> Dict:
    """Analyze the schema of the dataframe."""
    try:
        # Extract dataframe from state
        df = state.dataframe_info["dataframe"]
        
        schema = {}
        data_types = {}
        
        for col in df.columns:
            col_type = str(df[col].dtype)
            data_types[col] = col_type
            
            # Determine if categorical
            is_categorical = False
            if col_type == 'object' or col_type == 'category':
                unique_vals = df[col].nunique()
                total_vals = len(df[col])
                if unique_vals / total_vals < 0.2:  # If less than 20% unique values
                    is_categorical = True
            
            # Get example values
            example_values = []
            non_null_values = df[col].dropna()
            if not non_null_values.empty:
                example_values = non_null_values.sample(min(3, len(non_null_values))).tolist()
            
            schema[col] = {
                'type': col_type,
                'nullable': df[col].isna().any(),
                'unique_count': df[col].nunique(),
                'is_categorical': is_categorical,
                'example_values': example_values
            }
        
        # Get sample rows
        sample_rows = []
        sample_df = df.sample(min(5, len(df)))
        
        for _, row in sample_df.iterrows():
            # Convert numpy and pandas types to Python types
            row_dict = {}
            for k, v in row.items():
                if isinstance(v, (np.integer, np.floating)):
                    row_dict[k] = float(v) if np.isfinite(v) else None
                elif isinstance(v, (pd.Timestamp, pd.Period)):
                    row_dict[k] = str(v)
                elif isinstance(v, np.ndarray):
                    row_dict[k] = v.tolist()
                else:
                    row_dict[k] = v
            
            sample_rows.append(row_dict)
        
        return {
            "schema": schema,
            "sample_rows": sample_rows,
            "data_types": data_types
        }
    
    except Exception as e:
        return {"errors": state.errors + [f"Error in schema analyzer: {str(e)}"]}


def statistics_calculator(state: DataFrameAnalysisState) -> Dict:
    """Calculate statistics for the dataframe."""
    try:
        # Extract dataframe from state
        df = state.dataframe_info["dataframe"]
        
        stats = {}
        
        # Overall dataframe stats
        stats['dataframe'] = {
            'row_count': len(df),
            'column_count': len(df.columns),
            'memory_usage': df.memory_usage(deep=True).sum(),
            'missing_values_count': df.isna().sum().sum()
        }
        
        # Column-specific stats
        stats['columns'] = {}
        
        for col in df.columns:
            col_stats = {}
            
            # Basic stats for all column types
            col_stats['count'] = df[col].count()
            col_stats['missing'] = df[col].isna().sum()
            col_stats['unique'] = df[col].nunique()
            
            # Type-specific stats
            dtype = df[col].dtype
            if pd.api.types.is_numeric_dtype(dtype):
                # Numeric column stats
                col_stats['min'] = float(df[col].min()) if not df[col].empty else None
                col_stats['max'] = float(df[col].max()) if not df[col].empty else None
                col_stats['mean'] = float(df[col].mean()) if not df[col].empty else None
                col_stats['median'] = float(df[col].median()) if not df[col].empty else None
                col_stats['std'] = float(df[col].std()) if not df[col].empty else None
                
                # Distribution info
                percentiles = [0.25, 0.5, 0.75]
                quartiles = df[col].quantile(percentiles).tolist()
                col_stats['quartiles'] = dict(zip([f"{p*100}%" for p in percentiles], quartiles))
                
                # Detect outliers
                q1 = df[col].quantile(0.25)
                q3 = df[col].quantile(0.75)
                iqr = q3 - q1
                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr
                outliers = df[(df[col] < lower_bound) | (df[col] > upper_bound)][col]
                col_stats['outliers_count'] = len(outliers)
                col_stats['outliers_percentage'] = (len(outliers) / df[col].count()) * 100 if df[col].count() > 0 else 0
                
            elif pd.api.types.is_string_dtype(dtype):
                # String column stats
                if not df[col].empty:
                    col_stats['min_length'] = df[col].str.len().min()
                    col_stats['max_length'] = df[col].str.len().max()
                    col_stats['avg_length'] = df[col].str.len().mean()
                
                # Most common values
                value_counts = df[col].value_counts(normalize=True).head(5)
                col_stats['top_values'] = {str(k): float(v) for k, v in value_counts.items()}
                
            elif pd.api.types.is_datetime64_dtype(dtype):
                # Datetime column stats
                if not df[col].empty:
                    col_stats['min'] = str(df[col].min())
                    col_stats['max'] = str(df[col].max())
                    col_stats['range_days'] = (df[col].max() - df[col].min()).days
            
            stats['columns'][col] = col_stats
        
        return {"statistics": stats}
    
    except Exception as e:
        return {"errors": state.errors + [f"Error in statistics calculator: {str(e)}"]}


def time_series_detector(state: DataFrameAnalysisState) -> Dict:
    """Detect if the dataframe contains time series data."""
    try:
        # Extract dataframe from state
        df = state.dataframe_info["dataframe"]
        
        # Check for datetime columns
        datetime_cols = df.select_dtypes(include=['datetime64']).columns.tolist()
        
        if datetime_cols:
            # If multiple datetime columns, try to identify the primary one
            if len(datetime_cols) > 1:
                # Prefer columns with names like 'date', 'time', 'timestamp'
                time_keywords = ['date', 'time', 'timestamp', 'dt', 'period']
                for keyword in time_keywords:
                    matching_cols = [col for col in datetime_cols if keyword.lower() in col.lower()]
                    if matching_cols:
                        return {"time_series_column": matching_cols[0]}
            
            # Return the first datetime column if no obvious choice
            return {"time_series_column": datetime_cols[0]}
        
        # Check for string columns that might contain dates
        for col in df.select_dtypes(include=['object']).columns:
            # Sample the column and check if values look like dates
            sample = df[col].dropna().sample(min(100, len(df[col].dropna())))
            if sample.empty:
                continue
                
            # Try to convert to datetime
            try:
                pd.to_datetime(sample, errors='raise')
                return {"time_series_column": col}  # Return the column name if conversion succeeds
            except:
                continue
        
        return {"time_series_column": None}
    
    except Exception as e:
        return {"errors": state.errors + [f"Error in time series detector: {str(e)}"]}


def groupby_suggester(state: DataFrameAnalysisState) -> Dict:
    """Suggest columns that might be good for grouping."""
    try:
        # Extract dataframe from state
        df = state.dataframe_info["dataframe"]
        
        groupby_candidates = []
        
        for col in df.columns:
            unique_count = df[col].nunique()
            unique_pct = unique_count / len(df)
            
            # Good groupby candidates have a moderate number of unique values
            if 1 < unique_count < 1000 and unique_pct < 0.2:
                groupby_candidates.append(col)
            
            # Also check column name for typical groupby column names
            groupby_keywords = ['id', 'category', 'type', 'group', 'class', 'segment', 'region', 'country', 'state', 'city', 'month', 'year', 'quarter']
            if any(keyword in col.lower() for keyword in groupby_keywords):
                if col not in groupby_candidates:
                    groupby_candidates.append(col)
        
        return {"groupby_columns": groupby_candidates}
    
    except Exception as e:
        return {"errors": state.errors + [f"Error in groupby suggester: {str(e)}"]}


def aggregation_suggester(state: DataFrameAnalysisState) -> Dict:
    """Suggest aggregation methods for each column."""
    try:
        # Extract dataframe from state
        df = state.dataframe_info["dataframe"]
        
        aggregations = {}
        
        for col in df.columns:
            aggs = []
            dtype = df[col].dtype
            
            if pd.api.types.is_numeric_dtype(dtype):
                # For numeric columns
                aggs = ['sum', 'mean', 'median', 'min', 'max', 'count', 'std']
                
                # Check if the column might be a count/quantity
                if col.lower().find('count') >= 0 or col.lower().find('qty') >= 0 or col.lower().find('quantity') >= 0:
                    aggs = ['sum', 'mean', 'count'] + aggs[3:]
                
                # Check if the column might be a ratio/percentage
                if col.lower().find('ratio') >= 0 or col.lower().find('pct') >= 0 or col.lower().find('percent') >= 0:
                    aggs = ['mean', 'median', 'min', 'max', 'std', 'count']
                
            elif pd.api.types.is_string_dtype(dtype) or pd.api.types.is_categorical_dtype(dtype):
                # For categorical columns
                unique_pct = df[col].nunique() / len(df)
                
                if unique_pct < 0.1:  # If fewer than 10% unique values, likely categorical
                    aggs = ['count', 'nunique', 'mode']
                else:
                    aggs = ['count', 'nunique']
                
            elif pd.api.types.is_datetime64_dtype(dtype):
                # For datetime columns
                aggs = ['min', 'max', 'nunique', 'count']
                
            aggregations[col] = aggs
        
        return {"aggregation_functions": aggregations}
    
    except Exception as e:
        return {"errors": state.errors + [f"Error in aggregation suggester: {str(e)}"]}


def correlation_analyzer(state: DataFrameAnalysisState) -> Dict:
    """Analyze correlations between numeric columns."""
    try:
        # Extract dataframe from state
        df = state.dataframe_info["dataframe"]
        
        # Get numeric columns
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        
        # Initialize correlations
        correlations = {}
        
        # Calculate correlation matrix if there are at least 2 numeric columns
        if len(numeric_cols) > 1:
            corr_matrix = df[numeric_cols].corr().round(2)
            
            # Convert to dictionary format
            for col1 in corr_matrix.columns:
                correlations[col1] = {}
                for col2 in corr_matrix.columns:
                    correlations[col1][col2] = float(corr_matrix.loc[col1, col2])
        
        return {"correlations": correlations}
    
    except Exception as e:
        return {"errors": state.errors + [f"Error in correlation analyzer: {str(e)}"]}


def missing_data_analyzer(state: DataFrameAnalysisState) -> Dict:
    """Analyze missing data patterns."""
    try:
        # Extract dataframe from state
        df = state.dataframe_info["dataframe"]
        
        missing_data_info = {
            "total_missing": df.isna().sum().sum(),
            "missing_percentage": (df.isna().sum().sum() / (df.shape[0] * df.shape[1])) * 100,
            "columns_with_missing": {}
        }
        
        # Analyze missing data by column
        for col in df.columns:
            missing_count = df[col].isna().sum()
            if missing_count > 0:
                missing_data_info["columns_with_missing"][col] = {
                    "count": int(missing_count),
                    "percentage": float((missing_count / len(df)) * 100)
                }
        
        # Check for patterns in missing data
        missing_patterns = df.isna().sum(axis=1).value_counts().sort_index()
        missing_data_info["rows_with_n_missing"] = {str(k): int(v) for k, v in missing_patterns.items()}
        
        return {"missing_data_info": missing_data_info}
    
    except Exception as e:
        return {"errors": state.errors + [f"Error in missing data analyzer: {str(e)}"]}


def function_suggester(state: DataFrameAnalysisState) -> Dict:
    """Suggest functions for data analysis based on the dataset characteristics."""
    try:
        llm = get_llm()
        
        # Create prompt for function suggestions
        function_prompt = ChatPromptTemplate.from_template("""
        You are a data scientist specializing in exploratory data analysis and feature engineering.
        Based on the characteristics of the dataset, suggest Python functions that would be useful for analyzing this data.
        
        Dataset Information:
        - Rows: {row_count}
        - Columns: {column_count}
        - Missing Values: {missing_values_count} ({missing_values_percentage}% of all cells)
        
        Schema:
        {schema_summary}
        
        Time Series Information:
        {time_series_info}
        
        Groupby Columns:
        {groupby_columns}
        
        Correlation Information:
        {correlation_info}
        
        Missing Data Information:
        {missing_data_info}
        
        For each suggested function, provide:
        1. Function name
        2. Brief description of what the function does
        3. Sample code showing how to use it with this dataset
        4. What insights this function might reveal
        
        Return a JSON array of function suggestions:
        [
          {{
            "name": "function_name",
            "description": "What this function does",
            "code": "Python code sample",
            "insights": "Potential insights this function could reveal",
            "relevant_columns": ["col1", "col2"],
            "category": "one of: cleaning, exploration, visualization, statistical_analysis, feature_engineering, predictive_modeling"
          }},
          ...
        ]
        
        Focus on functions that are relevant to this specific dataset and its characteristics.
        """)
        
        # Prepare inputs for the prompt
        schema_summary = []
        for col, info in state.schema.items():
            schema_summary.append(f"- {col}: {info['type']}, {info['unique_count']} unique values, {'categorical' if info.get('is_categorical') else 'continuous'}")
        
        # Time series info
        if state.time_series_column:
            time_series_info = f"Dataset contains time series data with column '{state.time_series_column}'"
        else:
            time_series_info = "No time series data detected"
        
        # Correlation info
        correlation_info = []
        if state.correlations:
            high_corr_pairs = []
            for col1, corrs in state.correlations.items():
                for col2, corr_val in corrs.items():
                    if col1 != col2 and abs(corr_val) > 0.7:
                        high_corr_pairs.append((col1, col2, corr_val))
            
            if high_corr_pairs:
                high_corr_pairs.sort(key=lambda x: abs(x[2]), reverse=True)
                for pair in high_corr_pairs[:5]:
                    correlation_info.append(f"- {pair[0]} and {pair[1]}: {pair[2]:.2f}")
            else:
                correlation_info.append("No strong correlations detected")
        else:
            correlation_info.append("No correlation data available")
        
        # Missing data info
        missing_data_info = []
        if state.missing_data_info and state.missing_data_info.get("columns_with_missing"):
            for col, info in state.missing_data_info.get("columns_with_missing", {}).items():
                missing_data_info.append(f"- {col}: {info['count']} missing values ({info['percentage']:.2f}%)")
        else:
            missing_data_info.append("No missing data detected")
        
        # Prepare the inputs
        inputs = {
            "row_count": state.dataframe_info["row_count"],
            "column_count": state.dataframe_info["column_count"],
            "missing_values_count": state.statistics.get("dataframe", {}).get("missing_values_count", 0),
            "missing_values_percentage": (state.statistics.get("dataframe", {}).get("missing_values_count", 0) / 
                                          (state.dataframe_info["row_count"] * state.dataframe_info["column_count"]) * 100 
                                          if state.dataframe_info["row_count"] * state.dataframe_info["column_count"] > 0 else 0),
            "schema_summary": "\n".join(schema_summary),
            "time_series_info": time_series_info,
            "groupby_columns": ", ".join(state.groupby_columns) if state.groupby_columns else "No obvious groupby columns detected",
            "correlation_info": "\n".join(correlation_info),
            "missing_data_info": "\n".join(missing_data_info)
        }
        
        llm = get_llm()
        # Generate function suggestions
        chain = function_prompt | llm | StrOutputParser()
        result = chain.invoke(inputs)
        
        # Parse the suggestions
        try:
            suggestions = json.loads(result)
            if not isinstance(suggestions, list):
                suggestions = []
        except:
            # Try to extract JSON using regex if direct parsing fails
            import re
            json_match = re.search(r'\[(.*?)\]', result, re.DOTALL)
            if json_match:
                try:
                    suggestions = json.loads("[" + json_match.group(1) + "]")
                except:
                    suggestions = []
            else:
                suggestions = []
        
        return {"suggested_functions": suggestions}
    
    except Exception as e:
        return {"errors": state.errors + [f"Error in function suggester: {str(e)}"]}


def context_generator(state: DataFrameAnalysisState) -> Dict:
    """Generate context about the dataframe."""
    try:
        # Create a context string
        context = []
        
        # Dataset size info
        context.append(f"Dataset contains {state.dataframe_info['row_count']} rows and {state.dataframe_info['column_count']} columns.")
        
        # Missing data info
        missing_values_count = state.statistics.get("dataframe", {}).get("missing_values_count", 0)
        if missing_values_count > 0:
            missing_pct = missing_values_count / (state.dataframe_info["row_count"] * state.dataframe_info["column_count"]) * 100
            context.append(f"Dataset contains {missing_pct:.2f}% missing values.")
        
        # Time series info
        if state.time_series_column:
            context.append(f"Dataset appears to contain time series data with date/time column '{state.time_series_column}'.")
        
        # Column type breakdown
        numeric_cols = [col for col, info in state.schema.items() if 'float' in info['type'] or 'int' in info['type']]
        categorical_cols = [col for col, info in state.schema.items() if info['is_categorical']]
        
        context.append(f"Dataset contains {len(numeric_cols)} numeric columns and {len(categorical_cols)} categorical columns.")
        
        # Groupby suggestion
        if state.groupby_columns:
            context.append(f"Potential grouping columns: {', '.join(state.groupby_columns[:5])}" + 
                          (f" and {len(state.groupby_columns) - 5} more" if len(state.groupby_columns) > 5 else ""))
        
        # High correlation pairs
        if state.correlations:
            high_corr_pairs = []
            for col1, corrs in state.correlations.items():
                for col2, corr_val in corrs.items():
                    if col1 != col2 and abs(corr_val) > 0.7:
                        high_corr_pairs.append((col1, col2, corr_val))
            
            if high_corr_pairs:
                high_corr_pairs.sort(key=lambda x: abs(x[2]), reverse=True)
                top_pairs = high_corr_pairs[:3]
                pairs_text = [f"'{p[0]}' and '{p[1]}' ({p[2]:.2f})" for p in top_pairs]
                context.append(f"Strong correlations detected between: {'; '.join(pairs_text)}" +
                              (f" and {len(high_corr_pairs) - 3} more pairs" if len(high_corr_pairs) > 3 else ""))
        
        # Function suggestions summary
        if state.suggested_functions:
            functions_by_category = {}
            for func in state.suggested_functions:
                category = func.get("category", "other")
                if category not in functions_by_category:
                    functions_by_category[category] = []
                functions_by_category[category].append(func["name"])
            
            for category, funcs in functions_by_category.items():
                context.append(f"Suggested {category.replace('_', ' ')} functions: {', '.join(funcs[:3])}" +
                              (f" and {len(funcs) - 3} more" if len(funcs) > 3 else ""))
        
        return {"context": "\n".join(context)}
    
    except Exception as e:
        return {"errors": state.errors + [f"Error in context generator: {str(e)}"]}


# Graph builder
def build_dataframe_analysis_graph():
    """Build the LangGraph for dataframe analysis."""
    # Define the graph
    workflow = StateGraph(DataFrameAnalysisState)
    
    # Add nodes
    workflow.add_node(AnalysisNodeType.SCHEMA_ANALYZER, schema_analyzer)
    workflow.add_node(AnalysisNodeType.STATISTICS_CALCULATOR, statistics_calculator)
    workflow.add_node(AnalysisNodeType.TIME_SERIES_DETECTOR, time_series_detector)
    workflow.add_node(AnalysisNodeType.GROUPBY_SUGGESTER, groupby_suggester)
    workflow.add_node(AnalysisNodeType.AGGREGATION_SUGGESTER, aggregation_suggester)
    workflow.add_node(AnalysisNodeType.CORRELATION_ANALYZER, correlation_analyzer)
    workflow.add_node(AnalysisNodeType.MISSING_DATA_ANALYZER, missing_data_analyzer)
    workflow.add_node(AnalysisNodeType.FUNCTION_SUGGESTER, function_suggester)
    workflow.add_node(AnalysisNodeType.CONTEXT_GENERATOR, context_generator)
    
    # Define the edges
    workflow.add_edge(AnalysisNodeType.SCHEMA_ANALYZER, AnalysisNodeType.STATISTICS_CALCULATOR)
    workflow.add_edge(AnalysisNodeType.STATISTICS_CALCULATOR, AnalysisNodeType.TIME_SERIES_DETECTOR)
    workflow.add_edge(AnalysisNodeType.TIME_SERIES_DETECTOR, AnalysisNodeType.GROUPBY_SUGGESTER)
    workflow.add_edge(AnalysisNodeType.GROUPBY_SUGGESTER, AnalysisNodeType.AGGREGATION_SUGGESTER)
    workflow.add_edge(AnalysisNodeType.AGGREGATION_SUGGESTER, AnalysisNodeType.CORRELATION_ANALYZER)
    workflow.add_edge(AnalysisNodeType.CORRELATION_ANALYZER, AnalysisNodeType.MISSING_DATA_ANALYZER)
    workflow.add_edge(AnalysisNodeType.MISSING_DATA_ANALYZER, AnalysisNodeType.FUNCTION_SUGGESTER)
    workflow.add_edge(AnalysisNodeType.FUNCTION_SUGGESTER, AnalysisNodeType.CONTEXT_GENERATOR)
    workflow.add_edge(AnalysisNodeType.CONTEXT_GENERATOR, END)
    
    # Set the entry point
    workflow.set_entry_point(AnalysisNodeType.SCHEMA_ANALYZER)
    
    # Compile the graph
    return workflow.compile()


class DataFrameAnalyzer:
    """Utility class for analyzing dataframes and preparing them for the KPI recommendation pipeline."""
    
    def __init__(self, df: pd.DataFrame):
        """Initialize the analyzer with a dataframe.
        
        Args:
            df: Pandas DataFrame to analyze
        """
        self.df = df
        self.graph = build_dataframe_analysis_graph()
        
    def analyze_with_langgraph(self):
        """Analyze the dataframe using LangGraph.
        
        Returns:
            Full analysis results with function suggestions
        """
        # Initialize the state
        initial_state = DataFrameAnalysisState(
            dataframe_info={
                "dataframe": self.df,
                "row_count": len(self.df),
                "column_count": len(self.df.columns)
            }
        )
        
        # Execute the graph
        result = self.graph.invoke(initial_state)
        
        # Remove the dataframe from the result to make it serializable
        if "dataframe" in result.dataframe_info:
            del result.dataframe_info["dataframe"]
            
        return result
        
    def get_schema(self) -> Dict[str, Any]:
        """Get the schema of the dataframe.
        
        Returns:
            Dictionary with column names, types, and basic information
        """
        schema = {}
        
        for col in self.df.columns:
            col_type = str(self.df[col].dtype)
            
            # Determine if categorical
            is_categorical = False
            if col_type == 'object' or col_type == 'category':
                unique_vals = self.df[col].nunique()
                total_vals = len(self.df[col])
                if unique_vals / total_vals < 0.2:  # If less than 20% unique values
                    is_categorical = True
            
            # Get example values
            example_values = []
            non_null_values = self.df[col].dropna()
            if not non_null_values.empty:
                example_values = non_null_values.sample(min(3, len(non_null_values))).tolist()
            
            schema[col] = {
                'type': col_type,
                'nullable': self.df[col].isna().any(),
                'unique_count': self.df[col].nunique(),
                'is_categorical': is_categorical,
                'example_values': example_values
            }
        
        return schema
    
    def get_sample_rows(self, n: int = 5) -> List[Dict[str, Any]]:
        """Get sample rows from the dataframe.
        
        Args:
            n: Number of sample rows to return
            
        Returns:
            List of dictionaries representing sample rows
        """
        # Use sample to get random rows
        sample_df = self.df.sample(min(n, len(self.df)))
        
        # Convert to list of dictionaries
        sample_rows = []
        for _, row in sample_df.iterrows():
            # Convert numpy and pandas types to Python types
            row_dict = {}
            for k, v in row.items():
                if isinstance(v, (np.integer, np.floating)):
                    row_dict[k] = float(v) if np.isfinite(v) else None
                elif isinstance(v, (pd.Timestamp, pd.Period)):
                    row_dict[k] = str(v)
                elif isinstance(v, np.ndarray):
                    row_dict[k] = v.tolist()
                else:
                    row_dict[k] = v
            
            sample_rows.append(row_dict)
        
        return sample_rows
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistical summary of the dataframe.
        
        Returns:
            Dictionary with statistical summaries for each column
        """
        stats = {}
        
        # Overall dataframe stats
        stats['dataframe'] = {
            'row_count': len(self.df),
            'column_count': len(self.df.columns),
            'memory_usage': self.df.memory_usage(deep=True).sum(),
            'missing_values_count': self.df.isna().sum().sum()
        }
        
        # Column-specific stats
        stats['columns'] = {}
        
        for col in self.df.columns:
            col_stats = {}
            
            # Basic stats for all column types
            col_stats['count'] = self.df[col].count()
            col_stats['missing'] = self.df[col].isna().sum()
            col_stats['unique'] = self.df[col].nunique()
            
            # Type-specific stats
            dtype = self.df[col].dtype
            if pd.api.types.is_numeric_dtype(dtype):
                # Numeric column stats
                col_stats['min'] = float(self.df[col].min()) if not self.df[col].empty else None
                col_stats['max'] = float(self.df[col].max()) if not self.df[col].empty else None
                col_stats['mean'] = float(self.df[col].mean()) if not self.df[col].empty else None
                col_stats['median'] = float(self.df[col].median()) if not self.df[col].empty else None
                col_stats['std'] = float(self.df[col].std()) if not self.df[col].empty else None
                
                # Distribution info
                percentiles = [0.25, 0.5, 0.75]
                quartiles = self.df[col].quantile(percentiles).tolist()
                col_stats['quartiles'] = dict(zip([f"{p*100}%" for p in percentiles], quartiles))
                
            elif pd.api.types.is_string_dtype(dtype):
                # String column stats
                if not self.df[col].empty:
                    col_stats['min_length'] = self.df[col].str.len().min()
                    col_stats['max_length'] = self.df[col].str.len().max()
                    col_stats['avg_length'] = self.df[col].str.len().mean()
                
                # Most common values
                value_counts = self.df[col].value_counts(normalize=True).head(5)
                col_stats['top_values'] = {str(k): float(v) for k, v in value_counts.items()}
                
            elif pd.api.types.is_datetime64_dtype(dtype):
                # Datetime column stats
                if not self.df[col].empty:
                    col_stats['min'] = str(self.df[col].min())
                    col_stats['max'] = str(self.df[col].max())
                    col_stats['range_days'] = (self.df[col].max() - self.df[col].min()).days
            
            stats['columns'][col] = col_stats
        
        # Add correlation matrix for numeric columns
        numeric_cols = self.df.select_dtypes(include=['number']).columns.tolist()
        if len(numeric_cols) > 1:
            corr_matrix = self.df[numeric_cols].corr().round(2)
            
            # Convert to dictionary format
            corr_dict = {}
            for col1 in corr_matrix.columns:
                corr_dict[col1] = {}
                for col2 in corr_matrix.columns:
                    corr_dict[col1][col2] = float(corr_matrix.loc[col1, col2])
            
            stats['correlations'] = corr_dict
        
        return stats
    
    def detect_time_series(self) -> Optional[str]:
        """Detect if the dataframe contains time series data.
        
        Returns:
            Name of the datetime column if found, None otherwise
        """
        # Check for datetime columns
        datetime_cols = self.df.select_dtypes(include=['datetime64']).columns.tolist()
        
        if datetime_cols:
            # If multiple datetime columns, try to identify the primary one
            if len(datetime_cols) > 1:
                # Prefer columns with names like 'date', 'time', 'timestamp'
                time_keywords = ['date', 'time', 'timestamp', 'dt', 'period']
                for keyword in time_keywords:
                    matching_cols = [col for col in datetime_cols if keyword.lower() in col.lower()]
                    if matching_cols:
                        return matching_cols[0]
            
            # Return the first datetime column if no obvious choice
            return datetime_cols[0]
        
        # Check for string columns that might contain dates
        for col in self.df.select_dtypes(include=['object']).columns:
            # Sample the column and check if values look like dates
            sample = self.df[col].dropna().sample(min(100, len(self.df[col].dropna())))
            if sample.empty:
                continue
                
            # Try to convert to datetime
            try:
                pd.to_datetime(sample, errors='raise')
                return col  # Return the column name if conversion succeeds
            except:
                continue
        
        return None
    
    def suggest_aggregations(self) -> Dict[str, List[str]]:
        """Suggest aggregation methods for each column.
        
        Returns:
            Dictionary mapping column names to suggested aggregation methods
        """
        aggregations = {}
        
        for col in self.df.columns:
            aggs = []
            dtype = self.df[col].dtype
            
            if pd.api.types.is_numeric_dtype(dtype):
                # For numeric columns
                aggs = ['sum', 'mean', 'median', 'min', 'max', 'count', 'std']
                
                # Check if the column might be a count/quantity
                if col.lower().find('count') >= 0 or col.lower().find('qty') >= 0 or col.lower().find('quantity') >= 0:
                    aggs = ['sum', 'mean', 'count'] + aggs[3:]
                
                # Check if the column might be a ratio/percentage
                if col.lower().find('ratio') >= 0 or col.lower().find('pct') >= 0 or col.lower().find('percent') >= 0:
                    aggs = ['mean', 'median', 'min', 'max', 'std', 'count']
                
            elif pd.api.types.is_string_dtype(dtype) or pd.api.types.is_categorical_dtype(dtype):
                # For categorical columns
                unique_pct = self.df[col].nunique() / len(self.df)
                
                if unique_pct < 0.1:  # If fewer than 10% unique values, likely categorical
                    aggs = ['count', 'nunique', 'mode']
                else:
                    aggs = ['count', 'nunique']
                
            elif pd.api.types.is_datetime64_dtype(dtype):
                # For datetime columns
                aggs = ['min', 'max', 'nunique', 'count']
                
            aggregations[col] = aggs
        
        return aggregations
    
    def suggest_groupby_columns(self) -> List[str]:
        """Suggest columns that might be good for grouping.
        
        Returns:
            List of column names that are good candidates for GROUP BY operations
        """
        groupby_candidates = []
        
        for col in self.df.columns:
            unique_count = self.df[col].nunique()
            unique_pct = unique_count / len(self.df)
            
            # Good groupby candidates have a moderate number of unique values
            if 1 < unique_count < 1000 and unique_pct < 0.2:
                groupby_candidates.append(col)
            
            # Also check column name for typical groupby column names
            groupby_keywords = ['id', 'category', 'type', 'group', 'class', 'segment', 'region', 'country', 'state', 'city', 'month', 'year', 'quarter']
            if any(keyword in col.lower() for keyword in groupby_keywords):
                if col not in groupby_candidates:
                    groupby_candidates.append(col)
        
        return groupby_candidates
    
    def prepare_for_kpi_pipeline(self) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any], str]:
        """Prepare the dataframe for the KPI recommendation pipeline.
        
        Returns:
            Tuple of (schema, sample_rows, statistics, context)
        """
        # Use LangGraph for analysis with function suggestions
        analysis_result = self.analyze_with_langgraph()
        
        return (
            analysis_result.schema,
            analysis_result.sample_rows,
            analysis_result.statistics,
            analysis_result.context or ""
        )
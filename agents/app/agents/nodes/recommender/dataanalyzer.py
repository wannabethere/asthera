from typing import Dict, List, Any, Optional, Union
import json
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from enum import Enum
from langgraph.graph import END, StateGraph


# State for the QA system
class DataFrameQAState(BaseModel):
    """State for the dataframe question answering system."""
    query: str = Field(..., description="User query about the dataframe")
    analysis_result: Dict[str, Any] = Field(..., description="Result from dataframe analysis")
    kpi_context: Optional[Dict[str, Any]] = Field(None, description="Additional KPI context information")
    query_type: Optional[str] = Field(None, description="Classified type of the query")
    focused_data: Optional[Dict[str, Any]] = Field(None, description="Focused subset of data for answering the query")
    query_plan: Optional[str] = Field(None, description="Plan for answering the query")
    generated_kpis: Optional[List[Dict[str, Any]]] = Field(None, description="Generated KPI suggestions")
    answer: Optional[str] = Field(None, description="Generated answer to the query")
    code_examples: Optional[List[Dict[str, Any]]] = Field(None, description="Code examples for implementing the answer")
    errors: List[str] = Field(default_factory=list, description="Errors encountered during the process")


class QueryType(str, Enum):
    """Types of queries that can be handled."""
    TIMESERIES_KPI = "timeseries_kpi"
    CATEGORICAL_KPI = "categorical_kpi"
    CORRELATION_KPI = "correlation_kpi"
    ANOMALY_KPI = "anomaly_kpi"
    GENERAL_KPI = "general_kpi"
    DATA_QUALITY = "data_quality"
    EXPLORATION = "exploration"
    VISUALIZATION = "visualization"
    UNKNOWN = "unknown"


class QANodeType(str, Enum):
    """Types of nodes in the QA pipeline."""
    QUERY_CLASSIFIER = "query_classifier"
    DATA_FOCUSER = "data_focuser"
    QUERY_PLANNER = "query_planner"
    KPI_GENERATOR = "kpi_generator"
    ANSWER_GENERATOR = "answer_generator"
    CODE_GENERATOR = "code_generator"


def get_llm(temperature: float = 0.0, model: str = "gpt-4o-mini"):
    """Get the LLM with specified temperature and model."""
    return ChatOpenAI(
        model=model,
        temperature=temperature
    )
# Node implementations
def query_classifier(state: DataFrameQAState) -> Dict:
    """Classify the type of query being asked."""
    try:
        # Define the classification prompt
        prompt = ChatPromptTemplate.from_template("""
        You are an expert data analyst specializing in understanding queries about dataframes and KPIs.
        Classify the following query into one of these categories:
        
        - TIMESERIES_KPI: Queries about time-based metrics or KPIs
        - CATEGORICAL_KPI: Queries about category-based or segmentation KPIs
        - CORRELATION_KPI: Queries about relationships between metrics
        - ANOMALY_KPI: Queries about detecting unusual patterns or outliers
        - GENERAL_KPI: General questions about KPIs for the dataset
        - DATA_QUALITY: Questions about data completeness, accuracy, or quality
        - EXPLORATION: General exploration questions about the dataset
        - VISUALIZATION: Questions about how to visualize the data
        - UNKNOWN: Cannot classify the query into any of the above
        
        User Query: {query}
        
        Dataset Information:
        {dataset_info}
        
        Return only the category name as a single word.
        """)
        
        # Prepare dataset info summary
        dataset_info = []
        if "dataframe_info" in state.analysis_result:
            info = state.analysis_result["dataframe_info"]
            dataset_info.append(f"Rows: {info.get('row_count', 'unknown')}")
            dataset_info.append(f"Columns: {info.get('column_count', 'unknown')}")
        
        if "schema" in state.analysis_result:
            dataset_info.append("Columns:")
            for col, details in state.analysis_result["schema"].items():
                col_type = details.get("type", "unknown")
                dataset_info.append(f"- {col}: {col_type}")
        
        if "time_series_column" in state.analysis_result:
            time_col = state.analysis_result["time_series_column"]
            if time_col:
                dataset_info.append(f"Time Series Column: {time_col}")
        
        # Get the LLM
        llm = get_llm()
        
        # Create the chain
        chain = prompt | llm | StrOutputParser()
        
        # Invoke the chain
        result = chain.invoke({
            "query": state.query,
            "dataset_info": "\n".join(dataset_info)
        })
        
        # Clean up the result (in case it returns more than just the category)
        result = result.strip().upper()
        
        # Extract the query type
        for query_type in QueryType:
            if query_type.name in result:
                return {"query_type": query_type.value}
        
        # Default to unknown if no match found
        return {"query_type": QueryType.UNKNOWN.value}
    
    except Exception as e:
        return {"errors": state.errors + [f"Error in query classifier: {str(e)}"]}


def data_focuser(state: DataFrameQAState) -> Dict:
    """Focus on relevant parts of the data for the query."""
    try:
        # Define what data to focus on based on query type
        focused_data = {}
        
        # Pull relevant data based on query type
        if state.query_type == QueryType.TIMESERIES_KPI.value:
            # Focus on time series data
            time_col = state.analysis_result.get("time_series_column")
            if time_col:
                focused_data["time_column"] = time_col
                
                # Get schema info for the time column
                if "schema" in state.analysis_result and time_col in state.analysis_result["schema"]:
                    focused_data["time_column_schema"] = state.analysis_result["schema"][time_col]
                
                # Get statistics for the time column
                if "statistics" in state.analysis_result and "columns" in state.analysis_result["statistics"]:
                    if time_col in state.analysis_result["statistics"]["columns"]:
                        focused_data["time_column_stats"] = state.analysis_result["statistics"]["columns"][time_col]
            
            # Get numeric columns (potential metrics for time series KPIs)
            numeric_cols = []
            if "schema" in state.analysis_result:
                for col, details in state.analysis_result["schema"].items():
                    col_type = details.get("type", "")
                    if "float" in col_type or "int" in col_type:
                        numeric_cols.append(col)
            
            focused_data["numeric_columns"] = numeric_cols
            
            # Get time-based suggested functions
            if "suggested_functions" in state.analysis_result:
                time_functions = []
                for func in state.analysis_result["suggested_functions"]:
                    if any(keyword in func.get("name", "").lower() for keyword in ["time", "trend", "seasonal", "period", "forecast", "rolling", "moving"]):
                        time_functions.append(func)
                focused_data["time_related_functions"] = time_functions
        
        elif state.query_type == QueryType.CATEGORICAL_KPI.value:
            # Focus on categorical data
            categorical_cols = []
            if "schema" in state.analysis_result:
                for col, details in state.analysis_result["schema"].items():
                    if details.get("is_categorical", False):
                        categorical_cols.append(col)
            
            focused_data["categorical_columns"] = categorical_cols
            
            # Get potential groupby columns
            if "groupby_columns" in state.analysis_result:
                focused_data["groupby_columns"] = state.analysis_result["groupby_columns"]
            
            # Get numeric columns (potential metrics for categorical KPIs)
            numeric_cols = []
            if "schema" in state.analysis_result:
                for col, details in state.analysis_result["schema"].items():
                    col_type = details.get("type", "")
                    if "float" in col_type or "int" in col_type:
                        numeric_cols.append(col)
            
            focused_data["numeric_columns"] = numeric_cols
        
        elif state.query_type == QueryType.CORRELATION_KPI.value:
            # Focus on correlations
            if "correlations" in state.analysis_result:
                focused_data["correlations"] = state.analysis_result["correlations"]
            
            # Get numeric columns
            numeric_cols = []
            if "schema" in state.analysis_result:
                for col, details in state.analysis_result["schema"].items():
                    col_type = details.get("type", "")
                    if "float" in col_type or "int" in col_type:
                        numeric_cols.append(col)
            
            focused_data["numeric_columns"] = numeric_cols
            
            # Get high correlation pairs
            high_corr_pairs = []
            if "correlations" in state.analysis_result:
                for col1, corrs in state.analysis_result["correlations"].items():
                    for col2, corr_val in corrs.items():
                        if col1 != col2 and abs(corr_val) > 0.6:
                            high_corr_pairs.append((col1, col2, corr_val))
            
            if high_corr_pairs:
                high_corr_pairs.sort(key=lambda x: abs(x[2]), reverse=True)
                focused_data["high_correlation_pairs"] = high_corr_pairs
        
        # Add generic focused data for all query types
        if "schema" in state.analysis_result:
            focused_data["schema"] = state.analysis_result["schema"]
        
        if "suggested_functions" in state.analysis_result:
            focused_data["suggested_functions"] = state.analysis_result["suggested_functions"]
        
        return {"focused_data": focused_data}
    
    except Exception as e:
        return {"errors": state.errors + [f"Error in data focuser: {str(e)}"]}


def query_planner(state: DataFrameQAState) -> Dict:
    """Plan how to answer the query."""
    try:
        query_type = state.query_type
        
        if query_type == QueryType.TIMESERIES_KPI.value:
            plan = f"""
            To answer a query about time series KPIs, I will:
            1. Identify the time series column: {state.focused_data.get('time_column', 'None found')}
            2. Identify numeric columns that could serve as metrics: {", ".join(state.focused_data.get('numeric_columns', [])[:5])}{"..." if len(state.focused_data.get('numeric_columns', [])) > 5 else ""}
            3. Generate time-based KPI definitions and formulas
            4. Provide example code for calculating and visualizing these KPIs
            5. Suggest dashboard layouts for monitoring these KPIs over time
            """
        
        elif query_type == QueryType.CATEGORICAL_KPI.value:
            plan = f"""
            To answer a query about categorical KPIs, I will:
            1. Identify categorical columns for segmentation: {", ".join(state.focused_data.get('categorical_columns', [])[:5])}{"..." if len(state.focused_data.get('categorical_columns', [])) > 5 else ""}
            2. Identify numeric columns that could serve as metrics: {", ".join(state.focused_data.get('numeric_columns', [])[:5])}{"..." if len(state.focused_data.get('numeric_columns', [])) > 5 else ""}
            3. Generate segmentation-based KPI definitions and formulas
            4. Provide example code for calculating and visualizing these KPIs
            5. Suggest comparative analyses between different categories
            """
        
        elif query_type == QueryType.CORRELATION_KPI.value:
            plan = f"""
            To answer a query about correlation KPIs, I will:
            1. Identify highly correlated pairs of metrics
            2. Generate KPIs that capture these relationships
            3. Provide formulas for calculating correlation-based KPIs
            4. Suggest visualizations to monitor these relationships
            5. Provide code examples for implementation
            """
        
        elif query_type == QueryType.ANOMALY_KPI.value:
            plan = f"""
            To answer a query about anomaly detection KPIs, I will:
            1. Identify metrics that should be monitored for anomalies
            2. Define KPIs based on statistical deviation from normal patterns
            3. Provide formulas for anomaly detection
            4. Suggest visualization and alerting mechanisms
            5. Provide code examples for implementation
            """
        
        else:
            # General approach for other query types
            plan = f"""
            To answer this {query_type} query, I will:
            1. Analyze the available dataset information and schema
            2. Generate appropriate KPI definitions based on the data
            3. Provide formulas and calculation methods
            4. Suggest visualizations and monitoring approaches
            5. Provide code examples for implementation
            """
        
        return {"query_plan": plan}
    
    except Exception as e:
        return {"errors": state.errors + [f"Error in query planner: {str(e)}"]}


def kpi_generator(state: DataFrameQAState) -> Dict:
    """Generate KPI suggestions based on the query and data."""
    try:
        # Define the KPI generation prompt based on query type
        if state.query_type == QueryType.TIMESERIES_KPI.value:
            prompt = ChatPromptTemplate.from_template("""
            You are a KPI and performance management expert with a focus on time series analysis.
            Generate relevant time series KPIs for the dataset described below.
            
            Dataset Information:
            {dataset_info}
            
            Time Column: {time_column}
            Numeric Columns (potential metrics): {numeric_columns}
            
            User Query: {query}
            
            Generate a comprehensive set of time series KPIs that:
            1. Utilize the time dimension in the dataset
            2. Provide actionable insights from the numeric metrics
            3. Include trend, seasonality, and comparative analyses
            4. Cover different time intervals (daily, weekly, monthly, etc. as appropriate)
            5. Include rate-of-change metrics
            
            For each KPI, provide:
            - Name: Clear and concise name
            - Description: What this KPI measures and why it's valuable
            - Formula: How to calculate this KPI
            - Interpretation: How to interpret different values
            - Visualization: Suggested visualization approach
            
            Format your response as a JSON array of KPI objects:
            [
              {{
                "name": "KPI Name",
                "description": "Detailed description",
                "formula": "Calculation formula",
                "interpretation": "How to interpret values",
                "visualization": "Visualization approach",
                "relevant_columns": ["col1", "col2"],
                "time_granularity": "Suggested time granularity (daily, weekly, etc.)"
              }},
              ...
            ]
            """)
            
            # Prepare input data
            time_column = state.focused_data.get("time_column", "None identified")
            numeric_columns = state.focused_data.get("numeric_columns", [])
            numeric_columns_str = ", ".join(numeric_columns[:10]) + ("..." if len(numeric_columns) > 10 else "")
            
        elif state.query_type == QueryType.CATEGORICAL_KPI.value:
            prompt = ChatPromptTemplate.from_template("""
            You are a KPI and performance management expert with a focus on segmentation analysis.
            Generate relevant categorical/segmentation KPIs for the dataset described below.
            
            Dataset Information:
            {dataset_info}
            
            Categorical Columns: {categorical_columns}
            Numeric Columns (potential metrics): {numeric_columns}
            
            User Query: {query}
            
            Generate a comprehensive set of categorical KPIs that:
            1. Utilize the categorical dimensions for segmentation
            2. Provide actionable insights about different segments
            3. Include comparative analyses between segments
            4. Highlight performance variations across categories
            
            For each KPI, provide:
            - Name: Clear and concise name
            - Description: What this KPI measures and why it's valuable
            - Formula: How to calculate this KPI
            - Interpretation: How to interpret different values
            - Visualization: Suggested visualization approach
            
            Format your response as a JSON array of KPI objects:
            [
              {{
                "name": "KPI Name",
                "description": "Detailed description",
                "formula": "Calculation formula",
                "interpretation": "How to interpret values",
                "visualization": "Visualization approach",
                "relevant_columns": ["col1", "col2"],
                "segment_column": "Main column used for segmentation"
              }},
              ...
            ]
            """)
            
            # Prepare input data
            categorical_columns = state.focused_data.get("categorical_columns", [])
            categorical_columns_str = ", ".join(categorical_columns[:10]) + ("..." if len(categorical_columns) > 10 else "")
            
            numeric_columns = state.focused_data.get("numeric_columns", [])
            numeric_columns_str = ", ".join(numeric_columns[:10]) + ("..." if len(numeric_columns) > 10 else "")
            
        elif state.query_type == QueryType.CORRELATION_KPI.value:
            prompt = ChatPromptTemplate.from_template("""
            You are a KPI and performance management expert with a focus on correlation analysis.
            Generate relevant correlation-based KPIs for the dataset described below.
            
            Dataset Information:
            {dataset_info}
            
            Highly Correlated Column Pairs:
            {correlation_pairs}
            
            User Query: {query}
            
            Generate a comprehensive set of correlation-based KPIs that:
            1. Leverage the relationships between metrics
            2. Provide actionable insights based on these relationships
            3. Include ratio metrics and relationship indicators
            4. Help track how changes in one metric affect another
            
            For each KPI, provide:
            - Name: Clear and concise name
            - Description: What this KPI measures and why it's valuable
            - Formula: How to calculate this KPI
            - Interpretation: How to interpret different values
            - Visualization: Suggested visualization approach
            
            Format your response as a JSON array of KPI objects:
            [
              {{
                "name": "KPI Name",
                "description": "Detailed description",
                "formula": "Calculation formula",
                "interpretation": "How to interpret values",
                "visualization": "Visualization approach",
                "relevant_columns": ["col1", "col2"],
                "correlation_type": "positive/negative/complex"
              }},
              ...
            ]
            """)
            
            # Prepare input data
            correlation_pairs = []
            if "high_correlation_pairs" in state.focused_data:
                for col1, col2, corr_val in state.focused_data["high_correlation_pairs"][:5]:
                    correlation_pairs.append(f"- {col1} and {col2}: {corr_val:.2f} correlation")
            
            correlation_pairs_str = "\n".join(correlation_pairs) or "No strong correlations identified"
            
        else:
            # General KPI prompt for other query types
            prompt = ChatPromptTemplate.from_template("""
            You are a KPI and performance management expert.
            Generate relevant KPIs for the dataset described below based on the user's query.
            
            Dataset Information:
            {dataset_info}
            
            User Query: {query}
            Query Type: {query_type}
            
            Generate a comprehensive set of KPIs that:
            1. Address the user's specific query
            2. Provide actionable insights from the available data
            3. Are clear, measurable, and business-relevant
            
            For each KPI, provide:
            - Name: Clear and concise name
            - Description: What this KPI measures and why it's valuable
            - Formula: How to calculate this KPI
            - Interpretation: How to interpret different values
            - Visualization: Suggested visualization approach
            
            Format your response as a JSON array of KPI objects:
            [
              {{
                "name": "KPI Name",
                "description": "Detailed description",
                "formula": "Calculation formula",
                "interpretation": "How to interpret values",
                "visualization": "Visualization approach",
                "relevant_columns": ["col1", "col2"]
              }},
              ...
            ]
            """)
        
        # Prepare general dataset info
        dataset_info = []
        if "dataframe_info" in state.analysis_result:
            info = state.analysis_result["dataframe_info"]
            dataset_info.append(f"Rows: {info.get('row_count', 'unknown')}")
            dataset_info.append(f"Columns: {info.get('column_count', 'unknown')}")
        
        # Add schema information
        if "schema" in state.analysis_result:
            dataset_info.append("\nColumns:")
            cols_added = 0
            for col, details in state.analysis_result["schema"].items():
                if cols_added < 10:  # Limit to 10 columns to keep it concise
                    col_type = details.get("type", "unknown")
                    is_cat = " (categorical)" if details.get("is_categorical", False) else ""
                    dataset_info.append(f"- {col}: {col_type}{is_cat}")
                    cols_added += 1
                else:
                    dataset_info.append(f"- ... and {len(state.analysis_result['schema']) - 10} more columns")
                    break
        
        dataset_info_str = "\n".join(dataset_info)
        
        # Get the LLM
        llm = get_llm()
          # Slightly higher temperature for creativity
        
        # Create the chain
        chain = prompt | llm | StrOutputParser()
        
        # Invoke the chain with input based on query type
        if state.query_type == QueryType.TIMESERIES_KPI.value:
            result = chain.invoke({
                "dataset_info": dataset_info_str,
                "time_column": time_column,
                "numeric_columns": numeric_columns_str,
                "query": state.query
            })
        elif state.query_type == QueryType.CATEGORICAL_KPI.value:
            result = chain.invoke({
                "dataset_info": dataset_info_str,
                "categorical_columns": categorical_columns_str,
                "numeric_columns": numeric_columns_str,
                "query": state.query
            })
        elif state.query_type == QueryType.CORRELATION_KPI.value:
            result = chain.invoke({
                "dataset_info": dataset_info_str,
                "correlation_pairs": correlation_pairs_str,
                "query": state.query
            })
        else:
            # For general or other query types
            result = chain.invoke({
                "dataset_info": dataset_info_str,
                "query": state.query,
                "query_type": state.query_type
            })
        
        # Parse the KPIs from the result
        try:
            kpis = json.loads(result)
            if not isinstance(kpis, list):
                kpis = []
        except:
            # Try to extract JSON using regex if direct parsing fails
            import re
            json_match = re.search(r'\[(.*?)\]', result, re.DOTALL)
            if json_match:
                try:
                    kpis = json.loads("[" + json_match.group(1) + "]")
                except:
                    kpis = []
            else:
                kpis = []
        
        return {"generated_kpis": kpis}
    
    except Exception as e:
        return {"errors": state.errors + [f"Error in KPI generator: {str(e)}"]}


def answer_generator(state: DataFrameQAState) -> Dict:
    """Generate a natural language answer to the query."""
    try:
        # Define the answer generation prompt
        prompt = ChatPromptTemplate.from_template("""
        You are an expert data analyst explaining KPIs to a business user.
        Craft a clear, thorough response to the user's query about KPIs for their dataset.
        
        User Query: {query}
        Query Type: {query_type}
        
        Generated KPIs:
        {kpis_summary}
        
        Your response should:
        1. Directly address the user's query
        2. Explain the recommended KPIs in business-friendly language
        3. Highlight why these KPIs are relevant and valuable
        4. Explain how they can be implemented at a high level
        5. Include any important caveats or considerations
        
        Avoid technical jargon when possible, but be precise about the KPI definitions.
        Be concise but thorough, organizing your response with clear sections.
        """)
        
        # Prepare KPI summary
        kpis_summary = []
        if state.generated_kpis:
            for i, kpi in enumerate(state.generated_kpis):
                kpis_summary.append(f"{i+1}. {kpi.get('name', 'Unnamed KPI')}:")
                kpis_summary.append(f"   Description: {kpi.get('description', 'No description')}")
                kpis_summary.append(f"   Formula: {kpi.get('formula', 'No formula provided')}")
                kpis_summary.append(f"   Columns: {', '.join(kpi.get('relevant_columns', []))}")
                kpis_summary.append("")
        else:
            kpis_summary = ["No KPIs were generated."]
        
       # Slightly higher temperature for natural language
        llm = get_llm()
        # Create the chain
        chain = prompt | llm | StrOutputParser()
        
        # Invoke the chain
        result = chain.invoke({
            "query": state.query,
            "query_type": state.query_type,
            "kpis_summary": "\n".join(kpis_summary)
        })
        
        return {"answer": result}
    
    except Exception as e:
        return {"errors": state.errors + [f"Error in answer generator: {str(e)}"]}





# Build QA graph
def build_dataframe_qa_graph():
    """Build the LangGraph for dataframe question answering."""
    # Define the graph
    workflow = StateGraph(DataFrameQAState)
    
    # Add nodes
    workflow.add_node(QANodeType.QUERY_CLASSIFIER, query_classifier)
    workflow.add_node(QANodeType.DATA_FOCUSER, data_focuser)
    workflow.add_node(QANodeType.QUERY_PLANNER, query_planner)
    workflow.add_node(QANodeType.KPI_GENERATOR, kpi_generator)
    workflow.add_node(QANodeType.ANSWER_GENERATOR, answer_generator)
    
    # Define the edges
    workflow.add_edge(QANodeType.QUERY_CLASSIFIER, QANodeType.DATA_FOCUSER)
    workflow.add_edge(QANodeType.DATA_FOCUSER, QANodeType.QUERY_PLANNER)
    workflow.add_edge(QANodeType.QUERY_PLANNER, QANodeType.KPI_GENERATOR)
    workflow.add_edge(QANodeType.KPI_GENERATOR, QANodeType.ANSWER_GENERATOR)
    workflow.add_edge(QANodeType.ANSWER_GENERATOR, END)
   
    
    # Set the entry point
    workflow.set_entry_point(QANodeType.QUERY_CLASSIFIER)
    
    # Compile the graph
    return workflow.compile()


class DataFrameQAGenerator:
    """Class for generating answers to questions about dataframes."""
    
    def __init__(self):
        """Initialize the QA generator."""
        self.graph = build_dataframe_qa_graph()
    
    def answer_question(
        self, 
        query: str, 
        analysis_result: Dict[str, Any], 
        kpi_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Answer a question about a dataframe.
        
        Args:
            query: User query about the dataframe
            analysis_result: Result from dataframe analysis
            kpi_context: Additional KPI context information
            
        Returns:
            Dictionary with answer and supporting information
        """
        # Initialize the state
        initial_state = DataFrameQAState(
            query=query,
            analysis_result=analysis_result,
            kpi_context=kpi_context
        )
        
        # Execute the graph
        result = self.graph.invoke(initial_state)
        
       
        # Convert to dict - safely handling the dataframe reference
        # Remove the dataframe from the result to make it serializable
        # Convert to dict - safely handling the dataframe reference
        try:
            # First check if it's a Pydantic model with dict() method
            if hasattr(result, 'dict'):
                # Try to remove dataframe reference before converting to dict
                if hasattr(result, 'dataframe_info'):
                    # If dataframe_info is an object with dataframe attribute
                    if hasattr(result.dataframe_info, 'dataframe'):
                        delattr(result.dataframe_info, 'dataframe')
                result_dict = result.dict()
            else:
                # If it's already a dict-like object
                result_dict = dict(result)
                if 'dataframe_info' in result_dict and isinstance(result_dict['dataframe_info'], dict):
                    if 'dataframe' in result_dict['dataframe_info']:
                        del result_dict['dataframe_info']['dataframe']

                print(result_dict)
        except Exception as e:
            print(f"Warning: Error handling dataframe reference: {e}")
            # If all else fails, create a basic result dict with what we can extract
            result_dict = {
                "schema": getattr(result, 'schema', {}),
                "suggested_functions": getattr(result, 'suggested_functions', []),
                "context": getattr(result, 'context', ""),
                "dataframe_info": {
                    "row_count": len(self.df),
                    "column_count": len(self.df.columns)
                }
            }
        print(f"Query processed. Response type: {result_dict.get('query_type', 'unknown')}")
        
        return result_dict
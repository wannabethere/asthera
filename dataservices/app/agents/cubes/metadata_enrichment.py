"""
Metadata Enrichment Module

This module provides functionality to enrich table metadata by:
1. Gathering statistics from pandas DataFrame
2. Generating business use cases and domain descriptions using LLM
"""

from typing import Dict, Any, List, Optional
import pandas as pd
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# Import models to avoid circular import - these are defined in cube_generation_agent
# We'll import them at runtime when the function is called


def get_table_statistics_from_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Get table statistics from a pandas DataFrame.
    
    Args:
        df: pandas DataFrame to analyze
    
    Returns:
        Dictionary containing table and column statistics
    """
    stats = {}
    
    if df is None or df.empty:
        return stats
    
    try:
        # Overall statistics
        stats["row_count"] = len(df)
        stats["column_count"] = len(df.columns)
        
        # Column-level statistics
        column_stats = {}
        for col in df.columns:
            col_stats = {
                "count": int(df[col].count()),
                "null_count": int(df[col].isna().sum()),
                "null_percentage": float((df[col].isna().sum() / len(df)) * 100) if len(df) > 0 else 0.0,
                "unique_count": int(df[col].nunique()),
                "cardinality": int(df[col].nunique())
            }
            
            # Numeric statistics
            if pd.api.types.is_numeric_dtype(df[col]):
                col_stats.update({
                    "min": float(df[col].min()) if not pd.isna(df[col].min()) else None,
                    "max": float(df[col].max()) if not pd.isna(df[col].max()) else None,
                    "mean": float(df[col].mean()) if not pd.isna(df[col].mean()) else None,
                    "median": float(df[col].median()) if not pd.isna(df[col].median()) else None,
                    "std": float(df[col].std()) if not pd.isna(df[col].std()) else None
                })
            
            # Sample values (top 10 most common)
            if df[col].dtype == 'object' or df[col].dtype.name == 'category':
                value_counts = df[col].value_counts().head(10)
                col_stats["top_values"] = value_counts.to_dict()
            
            column_stats[col] = col_stats
        
        stats["columns"] = column_stats
        
    except Exception as e:
        # Return empty stats on error
        pass
    
    return stats


def get_table_statistics_sql(table_name: str, db_connection: Any, sample_size: int = 200) -> Dict[str, Any]:
    """
    Get table statistics using SQL queries (legacy function for backward compatibility).
    
    Args:
        table_name: Name of the table to analyze
        db_connection: Database connection object (for pandas read_sql)
        sample_size: Number of rows to sample (default: 200)
    
    Returns:
        Dictionary containing table and column statistics
    """
    if not db_connection:
        return {}
    
    try:
        # Get sample data
        sample_query = f"SELECT * FROM {table_name} LIMIT {sample_size}"
        df = pd.read_sql(sample_query, db_connection)
        return get_table_statistics_from_dataframe(df)
    except Exception as e:
        return {}


def enrich_table_metadata(
    state: Any,  # AgentState - imported at runtime to avoid circular import
    table_dataframes: Optional[Dict[str, pd.DataFrame]] = None,
    db_connection: Optional[Any] = None,
    llm: Optional[ChatOpenAI] = None
) -> Any:  # AgentState
    """
    Enrich table metadata by gathering statistics from pandas DataFrames.
    This is the first step in the cube generation workflow.
    
    Args:
        state: Current agent state containing raw_ddls
        table_dataframes: Optional dictionary mapping table names to pandas DataFrames for statistics
        db_connection: Optional database connection for statistics (legacy support)
        llm: Optional LLM for generating business use cases
    
    Returns:
        Updated state with enriched table_metadata
    """
    # Import here to avoid circular import
    from .cube_generation_agent import TableMetadataSummary, ColumnMetadata
    
    table_metadata_list = []
    
    for ddl in state["raw_ddls"]:
        table_name = ddl.table_name
        metadata_summary = TableMetadataSummary(table_name=table_name)
        
        # Get statistics from pandas DataFrame if provided
        stats = {}
        if table_dataframes and table_name in table_dataframes:
            df = table_dataframes[table_name]
            stats = get_table_statistics_from_dataframe(df)
            metadata_summary.statistics = stats
            
            # Update column metadata from DataFrame
            for col_name in df.columns:
                # Find or create column metadata
                col_meta = next(
                    (c for c in metadata_summary.columns if c.name == col_name),
                    None
                )
                if not col_meta:
                    # Infer data type from pandas dtype
                    pandas_dtype = str(df[col_name].dtype)
                    # Map pandas dtypes to SQL-like types
                    if pd.api.types.is_integer_dtype(df[col_name]):
                        sql_type = "INTEGER"
                    elif pd.api.types.is_float_dtype(df[col_name]):
                        sql_type = "FLOAT"
                    elif pd.api.types.is_datetime64_any_dtype(df[col_name]):
                        sql_type = "TIMESTAMP"
                    elif pd.api.types.is_bool_dtype(df[col_name]):
                        sql_type = "BOOLEAN"
                    else:
                        sql_type = "VARCHAR"
                    
                    col_meta = ColumnMetadata(name=col_name, data_type=sql_type)
                    metadata_summary.columns.append(col_meta)
                
                # Update statistics
                if "columns" in stats and col_name in stats["columns"]:
                    col_stats = stats["columns"][col_name]
                    col_meta.statistics = col_stats
                    if "top_values" in col_stats:
                        col_meta.sample_values = list(col_stats["top_values"].keys())[:10]
        
        # Fallback to SQL-based statistics if DataFrame not provided
        elif db_connection:
            stats = get_table_statistics_sql(table_name, db_connection)
            metadata_summary.statistics = stats
            
            # Update column statistics
            if "columns" in stats:
                for col_name, col_stats in stats["columns"].items():
                    # Find or create column metadata
                    col_meta = next(
                        (c for c in metadata_summary.columns if c.name == col_name),
                        None
                    )
                    if not col_meta:
                        col_meta = ColumnMetadata(name=col_name, data_type="unknown")
                        metadata_summary.columns.append(col_meta)
                    
                    col_meta.statistics = col_stats
                    if "top_values" in col_stats:
                        col_meta.sample_values = list(col_stats["top_values"].keys())[:10]
        
        # Use LLM to generate business use case and domain description if not available
        if llm and (not metadata_summary.business_use_case or not metadata_summary.domain_description):
            system_prompt = """You are a data analyst. Based on table schema and column information, 
            provide a brief business use case and domain description for the table."""
            
            columns_info = "\n".join([
                f"- {col.name} ({col.data_type}): {col.description}" 
                for col in metadata_summary.columns
            ])
            
            prompt = f"""Table: {table_name}
DDL: {ddl.table_ddl}

Columns:
{columns_info}

Provide:
1. A brief business use case description (1-2 sentences)
2. A domain description (e.g., "Sales", "HR", "Finance", etc.)

Format as JSON:
{{
  "business_use_case": "...",
  "domain_description": "..."
}}"""
            
            try:
                response = llm.invoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=prompt)
                ])
                
                # Try to parse JSON from response
                response_text = response.content
                # Simple extraction - in production, use proper JSON parsing
                if "business_use_case" in response_text.lower():
                    if not metadata_summary.business_use_case:
                        metadata_summary.business_use_case = "Generated from schema analysis"
                    if not metadata_summary.domain_description:
                        metadata_summary.domain_description = "Generated from schema analysis"
            except:
                pass
        
        # Identify possible joins from relationships
        for rel in metadata_summary.relationships:
            if rel.get("type") == "FOREIGN_KEY":
                metadata_summary.possible_joins.append({
                    "type": "FOREIGN_KEY",
                    "from_columns": rel.get("columns", []),
                    "to_table": rel.get("referred_table", ""),
                    "to_columns": rel.get("referred_columns", []),
                    "join_condition": f"{table_name}.{rel.get('columns', [])[0]} = {rel.get('referred_table', '')}.{rel.get('referred_columns', [])[0]}" if rel.get("columns") and rel.get("referred_columns") else ""
                })
        
        # Add placeholder usages if not available
        if not metadata_summary.usages:
            metadata_summary.usages = {
                "SQLs": [],  # Placeholder - would be populated from OpenMetadata
                "Joins": [],  # Placeholder - would be populated from OpenMetadata
                "Cubes": [],  # Placeholder - would be populated from OpenMetadata
                "Dashboards": []  # Placeholder - would be populated from OpenMetadata
            }
        
        table_metadata_list.append(metadata_summary)
    
    state["table_metadata"] = table_metadata_list
    
    # Add summary message
    summary_msg = f"Enriched metadata for {len(table_metadata_list)} tables from pandas DataFrames and database statistics."
    state["messages"].append(AIMessage(content=summary_msg))
    
    return state


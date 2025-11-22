"""
Schema Analysis Agent
Analyzes DDL schemas to extract dimensions, measures, and relationships
"""

from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
import re


class ColumnAnalysis(BaseModel):
    """Analysis of a single column"""
    name: str
    data_type: str
    is_dimension: bool
    is_measure: bool
    is_temporal: bool
    is_identifier: bool
    description: str
    suggested_cube_type: str  # dimension, measure, time_dimension
    aggregation_type: str = "none"  # sum, count, avg, min, max, countDistinct


class TableAnalysis(BaseModel):
    """Complete analysis of a table"""
    table_name: str
    description: str
    columns: List[ColumnAnalysis]
    primary_keys: List[str]
    foreign_keys: List[Dict[str, str]]
    potential_joins: List[Dict[str, Any]]
    grain: str  # Level of detail description
    data_quality_concerns: List[str]
    recommended_transformations: List[str]


class SchemaAnalysisAgent:
    """Analyzes database schemas and provides insights for cube generation"""
    
    def __init__(self, model_name: str = "gpt-4o"):
        from app.core.dependencies import get_llm
        self.llm = get_llm(temperature=0, model=model_name)
        self.parser = JsonOutputParser()
    
    def analyze_ddl(self, table_name: str, ddl: str, relationships: List[Dict]) -> TableAnalysis:
        """
        Perform deep analysis of a DDL statement.
        
        Args:
            table_name: Name of the table
            ddl: DDL CREATE TABLE statement
            relationships: List of relationship definitions
            
        Returns:
            TableAnalysis object with comprehensive insights
        """
        system_prompt = """You are an expert database schema analyst specializing in dimensional modeling and Cube.js.

Your task is to analyze DDL statements and identify:
1. **Dimensions**: Categorical, textual, or date columns used for slicing/filtering
2. **Measures**: Numeric columns suitable for aggregation (sum, avg, count, etc.)
3. **Time Dimensions**: Date/timestamp columns for time-series analysis
4. **Identifiers**: Primary keys, unique identifiers
5. **Grain**: The level of detail the table represents
6. **Data Quality Concerns**: Potential issues (nullability, duplicates, etc.)
7. **Recommended Transformations**: Cleaning/enrichment suggestions

Classification Rules:
- **Dimensions**: VARCHAR, BOOLEAN, ENUM types; categorical data
- **Measures**: NUMERIC, INTEGER, FLOAT, DOUBLE types; aggregatable data
- **Time Dimensions**: DATE, TIMESTAMP, DATETIME types
- **Identifiers**: Columns with "id", "_id", or marked as PRIMARY KEY

For each column, suggest:
- Cube.js dimension/measure type
- Appropriate aggregation (for measures)
- Any transformations needed

Output your analysis as structured JSON."""
        
        user_prompt = f"""Analyze this table schema:

**Table Name**: {table_name}

**DDL**:
```sql
{ddl}
```

**Relationships**:
```json
{relationships}
```

Provide a comprehensive analysis including:
1. Column-by-column classification
2. Identified grain/level of detail
3. Primary and foreign key detection
4. Potential join paths to other tables
5. Data quality concerns
6. Transformation recommendations

Return as JSON matching this structure:
{{
  "table_name": "...",
  "description": "...",
  "columns": [
    {{
      "name": "...",
      "data_type": "...",
      "is_dimension": true/false,
      "is_measure": true/false,
      "is_temporal": true/false,
      "is_identifier": true/false,
      "description": "...",
      "suggested_cube_type": "dimension|measure|time_dimension",
      "aggregation_type": "sum|avg|count|min|max|countDistinct|none"
    }}
  ],
  "primary_keys": ["col1", "col2"],
  "foreign_keys": [{{"column": "col", "references_table": "table", "references_column": "id"}}],
  "potential_joins": [{{"target_table": "...", "join_type": "...", "condition": "..."}}],
  "grain": "Description of what one row represents",
  "data_quality_concerns": ["concern1", "concern2"],
  "recommended_transformations": ["transformation1", "transformation2"]
}}"""
        
        response = self.llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        
        # Parse JSON response
        try:
            analysis_dict = self.parser.parse(response.content)
            return TableAnalysis(**analysis_dict)
        except Exception as e:
            # Fallback: basic parsing from DDL
            return self._fallback_analysis(table_name, ddl, relationships)
    
    def _fallback_analysis(self, table_name: str, ddl: str, relationships: List[Dict]) -> TableAnalysis:
        """Fallback analysis using regex parsing if LLM fails"""
        
        # Extract columns using regex
        column_pattern = r'(\w+)\s+(VARCHAR|INTEGER|BIGINT|BOOLEAN|TIMESTAMP|FLOAT|DOUBLE|NUMERIC)'
        matches = re.findall(column_pattern, ddl, re.IGNORECASE)
        
        columns = []
        for col_name, col_type in matches:
            # Determine column classification
            is_numeric = col_type.upper() in ['INTEGER', 'BIGINT', 'FLOAT', 'DOUBLE', 'NUMERIC']
            is_temporal = col_type.upper() in ['TIMESTAMP', 'DATE', 'DATETIME']
            is_identifier = 'id' in col_name.lower()
            
            column = ColumnAnalysis(
                name=col_name,
                data_type=col_type,
                is_dimension=not is_numeric and not is_temporal,
                is_measure=is_numeric and not is_identifier,
                is_temporal=is_temporal,
                is_identifier=is_identifier,
                description=f"{col_name} column",
                suggested_cube_type="measure" if is_numeric else "dimension",
                aggregation_type="sum" if is_numeric else "none"
            )
            columns.append(column)
        
        return TableAnalysis(
            table_name=table_name,
            description=f"Analysis of {table_name}",
            columns=columns,
            primary_keys=[],
            foreign_keys=[],
            potential_joins=[],
            grain="Row-level detail",
            data_quality_concerns=[],
            recommended_transformations=[]
        )
    
    def infer_grain(self, analysis: TableAnalysis) -> str:
        """
        Infer the grain (level of detail) of the table.
        
        Args:
            analysis: TableAnalysis object
            
        Returns:
            Human-readable description of the grain
        """
        system_prompt = """You are a data modeling expert. Determine the "grain" or level of detail for a table.

The grain describes what one row in the table represents. Examples:
- "One row per customer"
- "One row per order line item"
- "One row per device per day"
- "One row per network event"

Consider:
- Identifier columns
- Temporal columns
- Dimensional attributes"""
        
        columns_summary = "\n".join([
            f"- {col.name} ({col.data_type}): {'ID' if col.is_identifier else ''} {'TEMPORAL' if col.is_temporal else ''}"
            for col in analysis.columns
        ])
        
        prompt = f"""What is the grain of this table?

Table: {analysis.table_name}
Columns:
{columns_summary}

Provide a concise description like "One row per ..."."""
        
        response = self.llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ])
        
        return response.content.strip()
    
    def suggest_deduplication_strategy(self, analysis: TableAnalysis) -> Dict[str, Any]:
        """
        Suggest deduplication strategy based on table analysis.
        
        Args:
            analysis: TableAnalysis object
            
        Returns:
            Dictionary with deduplication recommendations
        """
        system_prompt = """You are a data quality expert. Suggest a deduplication strategy.

Consider:
1. What makes a record unique? (Primary keys, natural keys)
2. What dimensions define uniqueness? (LOD approach)
3. Which column to use for choosing the "best" record? (latest timestamp, highest priority)
4. Should duplicates be removed or aggregated?

Provide specific SQL logic for deduplication."""
        
        identifiers = [col.name for col in analysis.columns if col.is_identifier]
        temporal = [col.name for col in analysis.columns if col.is_temporal]
        
        prompt = f"""Suggest deduplication strategy for: {analysis.table_name}

Grain: {analysis.grain}
Identifiers: {identifiers}
Temporal columns: {temporal}

Provide:
1. LOD dimensions for uniqueness
2. Tie-breaker column (which record to keep)
3. SQL deduplication logic
4. Rationale

Return as JSON:
{{
  "lod_dimensions": ["col1", "col2"],
  "tie_breaker_column": "updated_at",
  "tie_breaker_order": "DESC",
  "sql_logic": "ROW_NUMBER() OVER ...",
  "rationale": "..."
}}"""
        
        response = self.llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ])
        
        try:
            return self.parser.parse(response.content)
        except:
            return {
                "lod_dimensions": identifiers,
                "tie_breaker_column": temporal[0] if temporal else "id",
                "tie_breaker_order": "DESC",
                "sql_logic": "",
                "rationale": "Basic deduplication strategy"
            }
    
    def compare_schemas(self, analyses: List[TableAnalysis]) -> Dict[str, Any]:
        """
        Compare multiple table schemas to find relationships and join opportunities.
        
        Args:
            analyses: List of TableAnalysis objects
            
        Returns:
            Dictionary with relationship insights
        """
        system_prompt = """You are a data modeling expert. Analyze relationships between tables.

Identify:
1. Foreign key relationships
2. Potential join columns (even without explicit FKs)
3. Dimension vs. fact table patterns
4. Recommended join strategies for silver layer
5. Potential for snowflake or star schema

Output relationship recommendations."""
        
        table_summaries = []
        for analysis in analyses:
            summary = f"""Table: {analysis.table_name}
Grain: {analysis.grain}
Keys: {', '.join(analysis.primary_keys)}
Columns: {', '.join([c.name for c in analysis.columns[:5]])}..."""
            table_summaries.append(summary)
        
        prompt = f"""Analyze relationships between these tables:

{chr(10).join(table_summaries)}

Provide:
1. Detected relationships
2. Recommended join order for silver layer
3. Dimension vs. fact classification
4. Suggested denormalization strategies

Return as JSON."""
        
        response = self.llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ])
        
        try:
            return self.parser.parse(response.content)
        except:
            return {"relationships": [], "recommendations": []}


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    agent = SchemaAnalysisAgent()
    
    # Example DDL
    ddl = """-- Network device inventory
CREATE TABLE dev_network_devices (
  id BIGINT NOT NULL,
  ip VARCHAR,
  subnet VARCHAR,
  mac VARCHAR,
  manufacturer VARCHAR,
  updated_at TIMESTAMP,
  is_stale BOOLEAN NOT NULL,
  days_since_last_seen INTEGER
);"""
    
    # Analyze
    analysis = agent.analyze_ddl("dev_network_devices", ddl, [])
    print("Table Analysis:")
    print(f"  Grain: {analysis.grain}")
    print(f"  Dimensions: {[c.name for c in analysis.columns if c.is_dimension]}")
    print(f"  Measures: {[c.name for c in analysis.columns if c.is_measure]}")
    print(f"  Quality Concerns: {analysis.data_quality_concerns}")
    
    # Suggest deduplication
    dedup = agent.suggest_deduplication_strategy(analysis)
    print(f"\nDeduplication Strategy:")
    print(f"  LOD Dimensions: {dedup.get('lod_dimensions')}")
    print(f"  Tie Breaker: {dedup.get('tie_breaker_column')}")

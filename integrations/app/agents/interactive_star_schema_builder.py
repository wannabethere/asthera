"""
Interactive Star Schema Builder with Human-in-the-Loop

This module provides an interactive workflow for building star schema materialized views:
1. Fetch all tables, schemas, and relationships from ChromaDB
2. Allow user to add/select metrics
3. Allow user to add/select time dimension
4. Allow user to configure LOD expressions for deduplication
5. Generate optimized star schema views

Uses RetrievalHelper2 for ChromaDB retrieval and implements its own agents for view generation.
"""

import asyncio
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.schema import HumanMessage, SystemMessage

from app.retrieval.retrieval_helper2 import RetrievalHelper2

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("genieml-agents")


# ============================================================================
# SQL Generation Rules
# ============================================================================

TEXT_TO_SQL_RULES = """
#### SQL RULES ####
- ONLY USE SELECT statements, NO DELETE, UPDATE OR INSERT etc. statements that might change the data in the database.
- Strictly Support POSTGRES SQL Syntax.
- **CRITICAL**: ONLY USE the tables and columns mentioned in the database schema. **CRITICAL**: Only use columns that exist in the provided schema for a table. Don't create columns that don't exist in the schema.
- ONLY USE "*" if the user query asks for all the columns of a table.
- **CRITICAL**: ONLY CHOOSE columns belong to the tables mentioned in the database schema and make sure alias is used correctly from the table definition.
- **CRITICAL**: Only use columns that exist in the provided schema for a table. Don't mixup columns from different tables.
- YOU MUST USE "JOIN" if you choose columns from multiple tables!
- ALWAYS QUALIFY column names with their table name or table alias to avoid ambiguity (e.g., orders.OrderId, o.OrderId)
- **IMPORTANT: Use column names exactly as they appear in the database schema (case-sensitive).**
- YOU MUST USE "lower(<table_name>.<column_name>) like lower(<value>)" function or "lower(<table_name>.<column_name>) = lower(<value>)" function for case-insensitive comparison!
- ALWAYS CAST the date/time related field to "TIMESTAMP WITH TIME ZONE" type when using them in the query
- DON'T USE "FILTER(WHERE <expression>)" clause in the generated SQL query.
- DONT USE HAVING CLAUSE WITHOUT GROUP BY CLAUSE.
- **RELATIONSHIP HANDLING**: When table relationships are provided, use them to create proper JOINs between tables.
- **FOR MATERIALIZED VIEWS**: Use proper aggregation functions (SUM, COUNT, AVG, MIN, MAX) and GROUP BY clauses
- **FOR MATERIALIZED VIEWS**: Include appropriate indexing considerations for frequently queried dimensions
"""

CALCULATED_FIELD_INSTRUCTIONS = """
#### Instructions for Calculated Fields ####

Calculated Fields are special columns whose values are derived through calculations on related data.
These fields are defined within a model and marked as "calculated: true" with an expression.

When you encounter Calculated Fields in the schema:
1. Recognize them by the "calculated: true" indicator
2. Understand their computation logic from the "expression" field
3. Use them directly in SQL queries as if they were regular columns
4. Do NOT try to replicate their calculation logic - the system handles this automatically
"""

METRIC_INSTRUCTIONS = """
#### Instructions for Metric ####

Metrics in a data model simplify complex data analysis by structuring data through predefined dimensions and measures.

The metric typically consists of:
1. Base Object: The primary data source or table
2. Dimensions: Categorical fields for data segmentation (e.g., time, location, category)
3. Measures: Numerical statistics calculated from data (e.g., SUM, COUNT, AVG)
4. Time Grain: Granularity of time-based aggregation (daily, monthly, yearly)

When the schema contains structures marked as 'metric', interpret them and use appropriately in SQL queries.
"""


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class MetricSpec:
    """Specification for a metric definition"""
    name: str
    display_name: str
    description: str
    metric_sql: str
    metric_type: str  # count, sum, avg, custom
    aggregation_type: Optional[str] = None
    table_name: Optional[str] = None
    columns: List[str] = field(default_factory=list)


@dataclass
class TimeDimensionSpec:
    """Specification for time dimension"""
    table_name: str
    column_name: str
    display_name: str
    description: str
    granularity: str = "day"  # day, week, month, quarter, year
    time_grain: Optional[str] = None


@dataclass
class LODConfig:
    """Level of Detail configuration for a view"""
    view_name: str
    lod_type: str  # FIXED, INCLUDE, EXCLUDE, or None
    dimensions: List[str] = field(default_factory=list)


@dataclass
class ReasoningPlan:
    """Structure for reasoning plan output"""
    reasoning: str
    query_groups: List[Dict[str, Any]]
    patterns: List[str]
    dimensions: List[str]
    measures: List[str]


@dataclass
class ViewSpec:
    """Specification for a materialized view in star schema format"""
    view_name: str
    reasoning: str
    source_queries: List[str]
    sql_definition: str
    dimensions: List[str]
    measures: List[str]
    refresh_strategy: str
    view_type: str = "fact"  # "source", "fact", "dimension"
    source_tables: List[str] = field(default_factory=list)
    fact_key_columns: List[str] = field(default_factory=list)
    dimension_key_columns: List[str] = field(default_factory=list)
    level_of_details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RegeneratedSQL:
    """Regenerated SQL for a view with validation and optimization details"""
    view_name: str
    original_sql: str
    regenerated_sql: str
    improvements: List[str]
    schema_alignment: Dict[str, Any]
    suggested_indexes: List[str] = field(default_factory=list)
    column_corrections: List[Dict[str, str]] = field(default_factory=list)


# ============================================================================
# Internal Agents
# ============================================================================

class StarSchemaReasoningAgent:
    """Agent for analyzing metrics and creating a reasoning plan for star schema views."""
    
    def __init__(self, llm: ChatAnthropic):
        self.llm = llm
    
    async def create_reasoning_plan(
        self,
        tables: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
        metrics: List[MetricSpec],
        time_dimension: Optional[TimeDimensionSpec],
        schema_context: str
    ) -> ReasoningPlan:
        """Create a reasoning plan for star schema generation."""
        
        # Build metrics context
        metrics_context = "=== METRICS ===\n"
        for metric in metrics:
            metrics_context += f"- {metric.name}: {metric.metric_sql} ({metric.metric_type})\n"
            metrics_context += f"  Description: {metric.description}\n"
            metrics_context += f"  Table: {metric.table_name}\n"
        
        # Build time dimension context
        time_context = ""
        if time_dimension:
            time_context = f"\n=== TIME DIMENSION ===\n"
            time_context += f"- Table: {time_dimension.table_name}\n"
            time_context += f"- Column: {time_dimension.column_name}\n"
            time_context += f"- Granularity: {time_dimension.granularity}\n"
        
        # Build relationships context
        rel_context = "\n=== RELATIONSHIPS ===\n"
        for rel in relationships[:10]:  # Show first 10
            rel_context += f"- {rel.get('from_table', '')}.{rel.get('from_column', '')} -> {rel.get('to_table', '')}.{rel.get('to_column', '')} [{rel.get('relationship_type', '')}]\n"
        
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are an expert database architect specializing in star schema design.
Your task is to analyze metrics, time dimensions, and relationships to create a reasoning plan for star schema materialized views.

Focus on:
1. Identifying fact tables (transaction-level data with measures)
2. Identifying dimension tables (descriptive attributes)
3. Understanding relationships between tables
4. Determining optimal view structure for the metrics provided
5. Planning how time dimension will be used across views

Respond in JSON format with:
{
  "reasoning": "detailed analysis of how to organize the star schema",
  "query_groups": [
    {
      "group_name": "descriptive name",
      "common_pattern": "description",
      "shared_elements": ["list of shared columns/logic"],
      "intended_views": ["view_name1", "view_name2"]
    }
  ],
  "patterns": ["pattern1", "pattern2"],
  "dimensions": ["dim1", "dim2"],
  "measures": ["measure1", "measure2"]
}"""),
            HumanMessage(content=f"""{schema_context}

{metrics_context}

{time_context}

{rel_context}

Analyze this information and create a reasoning plan for building a star schema.
Identify which tables should be fact tables, which should be dimensions, and how they relate.
Provide your reasoning plan in JSON format.""")
        ])
        
        chain = prompt | self.llm | StrOutputParser()
        response_text = chain.invoke({})
        
        try:
            result = json.loads(response_text)
            return ReasoningPlan(
                reasoning=result.get("reasoning", ""),
                query_groups=result.get("query_groups", []),
                patterns=result.get("patterns", []),
                dimensions=result.get("dimensions", []),
                measures=result.get("measures", [])
            )
        except json.JSONDecodeError:
            return ReasoningPlan(
                reasoning=response_text,
                query_groups=[],
                patterns=["general"],
                dimensions=[],
                measures=[]
            )


class StarSchemaViewCreationAgent:
    """Agent for creating star schema view definitions."""
    
    def __init__(self, llm: ChatAnthropic):
        self.llm = llm
    
    def _ast_for_sql(self, sql: str) -> Dict[str, Any]:
        """Parse SQL into AST and return JSON plus normalized SQL."""
        try:
            from sqlglot import parse_one as sqlglot_parse_one
            expr = sqlglot_parse_one(sql, read="postgres")
            ast_json = expr.to_json() if hasattr(expr, "to_json") else expr.dump()
            normalized_sql = expr.sql(dialect="postgres")
            return {"ast_json": ast_json, "normalized_sql": normalized_sql}
        except Exception:
            return {"ast_json": "", "normalized_sql": sql}
    
    async def create_views(
        self,
        reasoning_plan: ReasoningPlan,
        tables: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
        metrics: List[MetricSpec],
        time_dimension: Optional[TimeDimensionSpec],
        lod_configs: Dict[str, LODConfig],
        schema_context: str,
        instructions: Optional[str] = None,
        examples: Optional[List[Dict[str, Any]]] = None
    ) -> List[ViewSpec]:
        """Create star schema view definitions."""
        
        # Build star schema instructions
        star_schema_instructions = instructions or """
Create optimized materialized views in STAR SCHEMA format:

1. **SOURCE TABLE VIEWS**: Base views that represent source tables from the schema
   - Use 'mv_source_' prefix (e.g., mv_source_orders)
   - Preserve all columns from source tables
   - These are logical representations that can be replaced by external views
   
2. **FACT TABLE VIEWS**: Fact tables containing business metrics at the LOWEST GRANULARITY
   - **CRITICAL**: Create fact tables at the transaction/event level (lowest granularity)
   - Each row represents a single transaction, event, or measurable occurrence
   - Do NOT pre-aggregate in fact tables - preserve one row per transaction/event
   - Use 'mv_fact_' prefix with descriptive names (e.g., mv_fact_sales_transactions)
   - Include foreign keys to dimension tables for drill-down capability
   - Include raw measures at the transaction level
   - Avoid GROUP BY in fact tables unless LOD requires it
   
   **DEDUPLICATION (Level of Details / LOD) - Tableau-style**:
   - **FIXED LOD**: Use DISTINCT ON or GROUP BY with specified dimensions
   - **INCLUDE LOD**: Preserves fine granularity, allows reaggregation
   - **EXCLUDE LOD**: Remove dimensions from granularity
   - If NO LOD, keep all transaction rows (no deduplication)
   
3. **DIMENSION TABLE VIEWS**: Dimension tables with descriptive attributes
   - Use 'mv_dim_' prefix (e.g., mv_dim_customer, mv_dim_date)
   - Include dimension keys (primary keys or surrogate keys)
   - Include descriptive attributes (names, categories, hierarchies)
   
**CRITICAL: COLUMN COMMENTS AND METADATA**:
- **MUST include column comments** with business attributes:
  - Format: `column_name data_type -- Description: ... | DataType: ... | DisplayName: ... | Usage: ...`
  - Include ALL available column metadata from schema
  - These comments enable natural language queries on dashboards
"""
        
        # Build metrics and time context for LLM
        metrics_text = "\n=== METRICS TO INCLUDE ===\n"
        for metric in metrics:
            metrics_text += f"- {metric.name}: {metric.metric_sql} (Type: {metric.metric_type})\n"
        
        time_text = ""
        if time_dimension:
            time_text = f"\n=== TIME DIMENSION ===\n"
            time_text += f"- Table: {time_dimension.table_name}, Column: {time_dimension.column_name}\n"
            time_text += f"- Granularity: {time_dimension.granularity}\n"
        
        # Build LOD context
        lod_text = "\n=== LEVEL OF DETAIL CONFIGURATIONS ===\n"
        for view_name, lod_config in lod_configs.items():
            if lod_config.lod_type and lod_config.lod_type != "NONE":
                lod_text += f"- {view_name}: {lod_config.lod_type} LOD with dimensions {lod_config.dimensions}\n"
            else:
                lod_text += f"- {view_name}: No LOD (full transaction granularity)\n"
        
        # Default examples
        if not examples:
            examples = self._get_default_examples()
        
        examples_text = "=== STAR SCHEMA VIEW CREATION EXAMPLES ===\n\n"
        for idx, ex in enumerate(examples, 1):
            examples_text += f"Example {idx} ({ex.get('view_type', 'fact')}):\n"
            examples_text += f"View Type: {ex.get('view_type', 'fact')}\n"
            examples_text += f"Reasoning: {ex['reasoning']}\n"
            examples_text += f"View Name: {ex['view_name']}\n"
            examples_text += f"SQL: {ex['sql']}\n\n"
        
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=f"""You are an expert database architect specializing in PostgreSQL star schema and materialized view design.
Your task is to create optimal materialized view definitions in STAR SCHEMA format.

{star_schema_instructions}

{TEXT_TO_SQL_RULES}

{CALCULATED_FIELD_INSTRUCTIONS}

{METRIC_INSTRUCTIONS}

**CRITICAL REQUIREMENTS**:
1. Use CREATE MATERIALIZED VIEW syntax for PostgreSQL
2. Organize views into three types: source, fact, and dimension
3. **FACT VIEWS** MUST be at the LOWEST GRANULARITY (transaction/event level)
4. Include column comments with metadata for each column
5. Apply LOD configurations where specified
6. Validate all columns exist in the schema
7. Use proper JOIN conditions based on relationships

Respond in JSON format with an array of views:
[
  {{
    "view_type": "source|fact|dimension",
    "view_name": "mv_source_|mv_fact_|mv_dim_descriptive_name",
    "reasoning": "why this view is needed",
    "source_queries": [],
    "source_tables": ["table1", "mv_source_table1"],
    "sql_definition": "CREATE MATERIALIZED VIEW mv_name AS SELECT column1 -- Description: ... | DataType: ... | DisplayName: ... | Usage: ..., column2 FROM ...",
    "fact_key_columns": ["key1"],
    "dimension_key_columns": ["key1"],
    "dimensions": ["table.dim1"],
    "measures": ["raw_measure1"],
    "refresh_strategy": "incremental|full",
    "level_of_details": {{"type": "FIXED|INCLUDE|EXCLUDE", "dimensions": ["col1"]}} or {{}} for no LOD
  }}
]"""),
            HumanMessage(content=f"""{examples_text}

{schema_context}

{metrics_text}

{time_text}

{lod_text}

=== REASONING PLAN ===

Reasoning: {reasoning_plan.reasoning}
Patterns: {', '.join(reasoning_plan.patterns)}
Dimensions: {', '.join(reasoning_plan.dimensions)}
Measures: {', '.join(reasoning_plan.measures)}

Create materialized view definitions in STAR SCHEMA format following the examples and instructions.
Organize views into source, fact, and dimension types.
Respond with JSON array of view specifications.""")
        ])
        
        chain = prompt | self.llm | StrOutputParser()
        response_text = chain.invoke({})
        
        try:
            views_data = json.loads(response_text)
            views = []
            for v in views_data:
                lod_expr = {}
                view_name = v.get("view_name", "mv_unnamed")
                
                # Get LOD for this view
                if view_name in lod_configs:
                    lod_config = lod_configs[view_name]
                    if lod_config.lod_type and lod_config.lod_type != "NONE":
                        lod_expr = {
                            "type": lod_config.lod_type,
                            "dimensions": lod_config.dimensions
                        }
                elif v.get("level_of_details"):
                    lod_expr = v.get("level_of_details", {})
                
                views.append(ViewSpec(
                    view_name=view_name,
                    reasoning=v.get("reasoning", ""),
                    source_queries=v.get("source_queries", []),
                    sql_definition=v.get("sql_definition", ""),
                    dimensions=v.get("dimensions", []),
                    measures=v.get("measures", []),
                    refresh_strategy=v.get("refresh_strategy", "incremental"),
                    view_type=v.get("view_type", "fact"),
                    source_tables=v.get("source_tables", []),
                    fact_key_columns=v.get("fact_key_columns", []),
                    dimension_key_columns=v.get("dimension_key_columns", []),
                    level_of_details=lod_expr
                ))
            return views
        except json.JSONDecodeError:
            # Fallback: create one view
            return [ViewSpec(
                view_name="mv_unified",
                reasoning=response_text,
                source_queries=[],
                sql_definition=response_text,
                dimensions=reasoning_plan.dimensions,
                measures=reasoning_plan.measures,
                refresh_strategy="incremental",
                view_type="fact",
                source_tables=[],
                fact_key_columns=[],
                dimension_key_columns=[],
                level_of_details={}
            )]
    
    def _get_default_examples(self) -> List[Dict[str, Any]]:
        """Get default star schema examples."""
        return [
            {
                "view_type": "source",
                "reasoning": "Base source table for orders data",
                "view_name": "mv_source_orders",
                "sql": "CREATE MATERIALIZED VIEW mv_source_orders AS SELECT order_id -- Description: Unique order identifier | DataType: INT | DisplayName: Order ID | Usage: dimension, customer_id -- Description: Customer who placed the order | DataType: INT | DisplayName: Customer ID | Usage: dimension, CAST(order_date AS TIMESTAMP WITH TIME ZONE) as order_date -- Description: Date when order was placed | DataType: TIMESTAMP WITH TIME ZONE | DisplayName: Order Date | Usage: dimension, amount -- Description: Total order amount | DataType: DECIMAL | DisplayName: Order Amount | Usage: measure FROM orders"
            },
            {
                "view_type": "fact",
                "reasoning": "Fact table for sales transactions at transaction level",
                "view_name": "mv_fact_sales_transactions",
                "sql": "CREATE MATERIALIZED VIEW mv_fact_sales_transactions AS SELECT order_id -- Description: Unique order identifier | DataType: INT | DisplayName: Order ID | Usage: dimension, customer_id -- Description: Customer ID | DataType: INT | DisplayName: Customer ID | Usage: dimension, CAST(order_date AS TIMESTAMP WITH TIME ZONE) as order_date -- Description: Order date | DataType: TIMESTAMP WITH TIME ZONE | DisplayName: Order Date | Usage: dimension, amount as order_amount -- Description: Order amount | DataType: DECIMAL | DisplayName: Order Amount | Usage: measure FROM mv_source_orders"
            },
            {
                "view_type": "dimension",
                "reasoning": "Dimension table for customer attributes",
                "view_name": "mv_dim_customer",
                "sql": "CREATE MATERIALIZED VIEW mv_dim_customer AS SELECT DISTINCT customer_id -- Description: Customer ID | DataType: INT | DisplayName: Customer ID | Usage: dimension, customer_name -- Description: Customer name | DataType: VARCHAR | DisplayName: Customer Name | Usage: attribute FROM customers"
            }
        ]


class StarSchemaSQLOptimizationAgent:
    """Agent for optimizing and regenerating SQL for views."""
    
    def __init__(self, llm: ChatAnthropic):
        self.llm = llm
    
    async def regenerate_sql(
        self,
        view_spec: ViewSpec,
        tables: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
        schema_context: str
    ) -> RegeneratedSQL:
        """Regenerate and optimize SQL for a view using schema context."""
        
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=f"""You are an expert SQL optimizer.
Your task is to regenerate and optimize PostgreSQL materialized view definitions using retrieved schema context.

{TEXT_TO_SQL_RULES}

{CALCULATED_FIELD_INSTRUCTIONS}

{METRIC_INSTRUCTIONS}

**CRITICAL VALIDATION REQUIREMENTS**:
1. Verify ALL columns exist in the schema
2. Verify ALL tables exist in the schema
3. Use exact column names (case-sensitive) as they appear in schema
4. Apply proper table relationships and JOIN conditions
5. Use proper CAST for date/time fields to TIMESTAMP WITH TIME ZONE
6. Qualify all columns with table names or aliases
7. **MUST preserve and include column comments** with business attributes
8. Follow PostgreSQL syntax strictly

**OPTIMIZATION FOCUS**:
1. Schema alignment - ensure columns exist and have correct types
2. Join optimization - use proper foreign key relationships
3. Index hints - suggest useful indexes
4. Query efficiency - remove redundant operations
5. Maintainability - clear aliasing and formatting

Respond in JSON format:
{{
  "regenerated_sql": "Complete CREATE MATERIALIZED VIEW statement with optimizations",
  "improvements": ["Specific improvement 1", "Specific improvement 2"],
  "schema_alignment": {{
    "tables_used": ["table1"],
    "columns_validated": ["table1.col1"],
    "relationships_applied": ["table1.fk_col = table2.pk_col"]
  }},
  "suggested_indexes": ["CREATE INDEX idx_name ON view_name(column1)"]
}}"""),
            HumanMessage(content=f"""=== RETRIEVED SCHEMA CONTEXT ===

{schema_context}

=== VIEW SPECIFICATION ===

View Name: {view_spec.view_name}
View Type: {view_spec.view_type}
Original SQL Definition:
{view_spec.sql_definition}

Reasoning: {view_spec.reasoning}
Dimensions: {', '.join(view_spec.dimensions)}
Measures: {', '.join(view_spec.measures)}

Using the retrieved schema context, regenerate an optimized SQL definition for this view.
Ensure all columns exist, relationships are correct, and the SQL is efficient.
Respond in JSON format.""")
        ])
        
        chain = prompt | self.llm | StrOutputParser()
        response_text = chain.invoke({})
        
        try:
            result = json.loads(response_text)
            return RegeneratedSQL(
                view_name=view_spec.view_name,
                original_sql=view_spec.sql_definition,
                regenerated_sql=result.get("regenerated_sql", view_spec.sql_definition),
                improvements=result.get("improvements", []),
                schema_alignment=result.get("schema_alignment", {}),
                suggested_indexes=result.get("suggested_indexes", []),
                column_corrections=result.get("schema_alignment", {}).get("column_corrections", [])
            )
        except json.JSONDecodeError:
            return RegeneratedSQL(
                view_name=view_spec.view_name,
                original_sql=view_spec.sql_definition,
                regenerated_sql=response_text,
                improvements=["Regenerated with LLM"],
                schema_alignment={},
                suggested_indexes=[],
                column_corrections=[]
            )


# ============================================================================
# Main Interactive Star Schema Builder
# ============================================================================

class InteractiveStarSchemaBuilder:
    """
    Interactive star schema builder with human-in-the-loop workflow.
    
    Workflow:
    1. Fetch all tables from ChromaDB using RetrievalHelper2
    2. Display tables and relationships to user
    3. Prompt user to add/select metrics
    4. Prompt user to add/select time dimension
    5. Prompt user to configure LOD expressions
    6. Generate star schema views using internal agents
    """
    
    def __init__(
        self,
        project_id: str,
        retrieval_helper: Optional[RetrievalHelper2] = None,
        llm: Optional[ChatAnthropic] = None,
        interactive_mode: bool = True
    ):
        """Initialize the interactive star schema builder."""
        self.project_id = project_id
        self.interactive_mode = interactive_mode
        
        # Initialize retrieval helper
        self.retrieval_helper = retrieval_helper or RetrievalHelper2()
        
        # Initialize LLM
        self.llm = llm or ChatAnthropic(
            model="claude-sonnet-4-5-20250929",
            temperature=0
        )
        
        # Initialize internal agents
        self.reasoning_agent = StarSchemaReasoningAgent(self.llm)
        self.view_agent = StarSchemaViewCreationAgent(self.llm)
        self.optimization_agent = StarSchemaSQLOptimizationAgent(self.llm)
        
        # Store fetched data
        self.tables: List[Dict[str, Any]] = []
        self.relationships: List[Dict[str, Any]] = []
        self.schema_context: str = ""
        
        # Store user configurations
        self.metrics: List[MetricSpec] = []
        self.time_dimension: Optional[TimeDimensionSpec] = None
        self.lod_configs: Dict[str, LODConfig] = {}
        
        logger.info(f"Initialized InteractiveStarSchemaBuilder for project: {project_id}")
    
    async def fetch_all_tables(self, query: str = "") -> Dict[str, Any]:
        """Fetch all tables, schemas, and relationships from ChromaDB."""
        logger.info(f"Fetching all tables for project: {self.project_id}")
        
        schema_result = await self.retrieval_helper.get_database_schemas(
            project_id=self.project_id,
            table_retrieval={"table_retrieval_size": 100},
            query=query,
            histories=None,
            tables=None
        )
        
        if schema_result.get("error"):
            logger.error(f"Error fetching schemas: {schema_result['error']}")
            return {
                "success": False,
                "error": schema_result["error"],
                "tables": [],
                "relationships": []
            }
        
        schemas = schema_result.get("schemas", [])
        self.tables = []
        all_relationships = []
        
        for schema in schemas:
            table_info = {
                "name": schema.get("table_name", ""),
                "display_name": schema.get("table_ddl", "").split()[2] if schema.get("table_ddl") else "",
                "description": schema.get("table_ddl", ""),
                "columns": schema.get("column_metadata", []),
                "relationships": schema.get("relationships", []),
                "ddl": schema.get("table_ddl", "")
            }
            
            # Extract column details
            columns = []
            for col_meta in schema.get("column_metadata", []):
                if isinstance(col_meta, dict):
                    col = {
                        "name": col_meta.get("name", ""),
                        "data_type": col_meta.get("data_type", ""),
                        "description": col_meta.get("description", ""),
                        "display_name": col_meta.get("display_name", ""),
                        "usage_type": col_meta.get("usage_type", ""),
                        "is_calculated": col_meta.get("is_calculated", False),
                        "calculation_expression": col_meta.get("calculation_expression", ""),
                        "comment": col_meta.get("comment", "")
                    }
                    columns.append(col)
            
            table_info["columns"] = columns
            
            # Collect relationships
            table_rels = schema.get("relationships", [])
            if table_rels:
                all_relationships.extend(table_rels)
            
            self.tables.append(table_info)
        
        # Deduplicate relationships
        seen_relationships = set()
        for rel in all_relationships:
            rel_key = (
                rel.get("from_table", ""),
                rel.get("from_column", ""),
                rel.get("to_table", ""),
                rel.get("to_column", "")
            )
            if rel_key not in seen_relationships:
                self.relationships.append(rel)
                seen_relationships.add(rel_key)
        
        # Build schema context string
        self.schema_context = self._build_schema_context()
        
        result = {
            "success": True,
            "tables": self.tables,
            "relationships": self.relationships,
            "total_tables": len(self.tables),
            "total_relationships": len(self.relationships),
            "has_calculated_fields": schema_result.get("has_calculated_field", False),
            "has_metrics": schema_result.get("has_metric", False)
        }
        
        logger.info(f"Fetched {len(self.tables)} tables and {len(self.relationships)} relationships")
        return result
    
    def _build_schema_context(self) -> str:
        """Build a formatted schema context string from tables."""
        context_parts = []
        context_parts.append("=== DATABASE SCHEMA ===\n")
        
        for table in self.tables:
            context_parts.append(f"\nTable: {table['name']}")
            if table.get('description'):
                context_parts.append(f"Description: {table['description']}")
            
            context_parts.append("Columns:")
            for col in table.get('columns', []):
                col_info = f"  - {col['name']} ({col.get('data_type', 'VARCHAR')})"
                if col.get('description'):
                    col_info += f" -- {col['description']}"
                if col.get('usage_type'):
                    col_info += f" [Usage: {col['usage_type']}]"
                if col.get('is_calculated'):
                    col_info += f" [Calculated: {col.get('calculation_expression', '')}]"
                context_parts.append(col_info)
        
        if self.relationships:
            context_parts.append("\n=== RELATIONSHIPS ===")
            for rel in self.relationships:
                rel_info = f"{rel.get('from_table', '')}.{rel.get('from_column', '')} -> {rel.get('to_table', '')}.{rel.get('to_column', '')}"
                if rel.get('relationship_type'):
                    rel_info += f" [{rel.get('relationship_type')}]"
                context_parts.append(rel_info)
        
        return "\n".join(context_parts)
    
    def display_tables_and_relationships(self) -> str:
        """Display tables and relationships in a formatted way."""
        output = []
        output.append("\n" + "="*80)
        output.append("TABLES AND RELATIONSHIPS")
        output.append("="*80)
        
        output.append(f"\nTotal Tables: {len(self.tables)}")
        output.append(f"Total Relationships: {len(self.relationships)}\n")
        
        for idx, table in enumerate(self.tables, 1):
            output.append(f"\n[{idx}] {table['name']}")
            if table.get('display_name'):
                output.append(f"    Display Name: {table['display_name']}")
            
            columns = table.get('columns', [])
            measure_cols = [c for c in columns if c.get('usage_type') == 'measure']
            dim_cols = [c for c in columns if c.get('usage_type') == 'dimension']
            
            if measure_cols:
                output.append(f"    Measures: {', '.join([c['name'] for c in measure_cols[:5]])}")
            if dim_cols:
                output.append(f"    Dimensions: {', '.join([c['name'] for c in dim_cols[:5]])}")
            
            if len(columns) > 10:
                output.append(f"    ... and {len(columns) - 10} more columns")
        
        if self.relationships:
            output.append("\n\n=== RELATIONSHIPS ===")
            for rel in self.relationships[:10]:
                output.append(
                    f"{rel.get('from_table', '')}.{rel.get('from_column', '')} -> "
                    f"{rel.get('to_table', '')}.{rel.get('to_column', '')} "
                    f"[{rel.get('relationship_type', 'UNKNOWN')}]"
                )
            if len(self.relationships) > 10:
                output.append(f"... and {len(self.relationships) - 10} more relationships")
        
        return "\n".join(output)
    
    def prompt_for_metrics(self, input_data: Optional[Dict[str, Any]] = None) -> List[MetricSpec]:
        """Prompt user to add or select metrics."""
        if input_data and not self.interactive_mode:
            # API mode
            metrics_data = input_data.get("metrics", [])
            self.metrics = []
            
            for metric_data in metrics_data:
                metric = MetricSpec(
                    name=metric_data.get("name", ""),
                    display_name=metric_data.get("display_name", ""),
                    description=metric_data.get("description", ""),
                    metric_sql=metric_data.get("metric_sql", ""),
                    metric_type=metric_data.get("metric_type", "custom"),
                    aggregation_type=metric_data.get("aggregation_type"),
                    table_name=metric_data.get("table_name"),
                    columns=metric_data.get("columns", [])
                )
                self.metrics.append(metric)
            
            return self.metrics
        
        # Interactive mode - same as before
        print("\n" + "="*80)
        print("STEP 2: ADD METRICS")
        print("="*80)
        print("\nA metric is a business measure that you want to track (e.g., total sales, order count).")
        print("You can:")
        print("  1. Select existing columns as metrics")
        print("  2. Define new calculated metrics")
        print("  3. Skip metrics (press Enter)")
        
        measure_columns = []
        for table in self.tables:
            for col in table.get('columns', []):
                if col.get('usage_type') == 'measure':
                    measure_columns.append({
                        "table": table['name'],
                        "column": col['name'],
                        "description": col.get('description', ''),
                        "data_type": col.get('data_type', '')
                    })
        
        if measure_columns:
            print(f"\nFound {len(measure_columns)} measure columns:")
            for idx, mc in enumerate(measure_columns[:10], 1):
                print(f"  {idx}. {mc['table']}.{mc['column']} ({mc['data_type']}) - {mc['description']}")
            if len(measure_columns) > 10:
                print(f"  ... and {len(measure_columns) - 10} more")
        
        print("\nEnter metrics (press Enter twice when done):")
        print("Format: table_name.column_name as metric_name | description")
        
        metrics_input = []
        while True:
            try:
                user_input = input("\nMetric (or press Enter to finish): ").strip()
                if not user_input:
                    break
                
                parts = user_input.split("|")
                metric_def = parts[0].strip()
                description = parts[1].strip() if len(parts) > 1 else ""
                
                if " as " in metric_def:
                    table_col, metric_name = metric_def.split(" as ", 1)
                    table_name, col_name = table_col.split(".", 1) if "." in table_col else ("", table_col)
                else:
                    table_col = metric_def
                    table_name, col_name = table_col.split(".", 1) if "." in table_col else ("", table_col)
                    metric_name = col_name
                
                col_info = next(
                    (c for t in self.tables 
                     for c in t.get('columns', []) 
                     if t['name'] == table_name and c['name'] == col_name),
                    None
                )
                
                metric = MetricSpec(
                    name=metric_name.strip(),
                    display_name=metric_name.strip().replace("_", " ").title(),
                    description=description,
                    metric_sql=f"SUM({table_name}.{col_name})" if col_info else f"{metric_name}",
                    metric_type="sum" if col_info and col_info.get('data_type', '').lower() in ['decimal', 'numeric', 'float', 'double', 'int'] else "count",
                    aggregation_type="SUM",
                    table_name=table_name,
                    columns=[col_name]
                )
                
                metrics_input.append(metric)
                print(f"  ✓ Added metric: {metric_name}")
                
            except Exception as e:
                print(f"  ✗ Error parsing metric: {e}")
                continue
        
        self.metrics = metrics_input
        print(f"\n✓ Added {len(self.metrics)} metrics")
        return self.metrics
    
    def prompt_for_time_dimension(self, input_data: Optional[Dict[str, Any]] = None) -> Optional[TimeDimensionSpec]:
        """Prompt user to select or add time dimension."""
        if input_data and not self.interactive_mode:
            time_dim_data = input_data.get("time_dimension")
            if time_dim_data:
                self.time_dimension = TimeDimensionSpec(
                    table_name=time_dim_data.get("table_name", ""),
                    column_name=time_dim_data.get("column_name", ""),
                    display_name=time_dim_data.get("display_name", ""),
                    description=time_dim_data.get("description", ""),
                    granularity=time_dim_data.get("granularity", "day"),
                    time_grain=time_dim_data.get("time_grain")
                )
            return self.time_dimension
        
        # Interactive mode - same as before
        print("\n" + "="*80)
        print("STEP 3: SELECT TIME DIMENSION")
        print("="*80)
        print("\nSelect a time column to use as the time dimension.")
        
        time_columns = []
        for table in self.tables:
            for col in table.get('columns', []):
                col_type = col.get('data_type', '').lower()
                col_name = col.get('name', '').lower()
                if any(time_term in col_type for time_term in ['date', 'timestamp', 'time']) or \
                   any(time_term in col_name for time_term in ['date', 'time', 'timestamp', 'created', 'updated']):
                    time_columns.append({
                        "table": table['name'],
                        "column": col['name'],
                        "data_type": col.get('data_type', ''),
                        "description": col.get('description', '')
                    })
        
        if not time_columns:
            print("\n⚠ No time/date columns found. You can manually specify one.")
            user_input = input("Enter time dimension (format: table.column): ").strip()
            if user_input:
                table_name, col_name = user_input.split(".", 1) if "." in user_input else ("", user_input)
                self.time_dimension = TimeDimensionSpec(
                    table_name=table_name,
                    column_name=col_name,
                    display_name=col_name.replace("_", " ").title(),
                    description="Time dimension column",
                    granularity="day"
                )
            return self.time_dimension
        
        print(f"\nFound {len(time_columns)} time/date columns:")
        for idx, tc in enumerate(time_columns, 1):
            print(f"  {idx}. {tc['table']}.{tc['column']} ({tc['data_type']}) - {tc['description']}")
        
        try:
            choice = input("\nSelect time dimension (enter number, or press Enter to skip): ").strip()
            if not choice:
                return None
            
            idx = int(choice) - 1
            if 0 <= idx < len(time_columns):
                tc = time_columns[idx]
                granularity = input("Enter granularity (day/week/month/quarter/year, default: day): ").strip() or "day"
                
                self.time_dimension = TimeDimensionSpec(
                    table_name=tc['table'],
                    column_name=tc['column'],
                    display_name=tc['column'].replace("_", " ").title(),
                    description=tc['description'],
                    granularity=granularity
                )
                print(f"\n✓ Selected time dimension: {tc['table']}.{tc['column']} ({granularity})")
                return self.time_dimension
            else:
                print("Invalid selection")
                return None
        except (ValueError, KeyboardInterrupt):
            return None
    
    def prompt_for_lod_expressions(self, view_names: List[str], input_data: Optional[Dict[str, Any]] = None) -> Dict[str, LODConfig]:
        """Prompt user to configure LOD expressions for fact views."""
        if input_data and not self.interactive_mode:
            lod_configs_data = input_data.get("lod_configs", {})
            self.lod_configs = {}
            
            for view_name, lod_data in lod_configs_data.items():
                if view_name in view_names:
                    self.lod_configs[view_name] = LODConfig(
                        view_name=view_name,
                        lod_type=lod_data.get("type", ""),
                        dimensions=lod_data.get("dimensions", [])
                    )
            
            return self.lod_configs
        
        # Interactive mode
        print("\n" + "="*80)
        print("STEP 4: CONFIGURE LEVEL OF DETAIL (LOD) EXPRESSIONS")
        print("="*80)
        print("\nLOD expressions control deduplication and aggregation levels for fact views.")
        print("Types:")
        print("  - FIXED: Compute at specified granularity only")
        print("  - INCLUDE: Compute at fine granularity, allows reaggregation")
        print("  - EXCLUDE: Remove dimensions from granularity")
        print("  - None: No deduplication (full transaction granularity)")
        
        fact_views = [vn for vn in view_names if "fact" in vn.lower()]
        
        if not fact_views:
            print("\nNo fact views found. Skipping LOD configuration.")
            return {}
        
        print(f"\nConfigure LOD for {len(fact_views)} fact view(s):")
        
        for view_name in fact_views:
            print(f"\n  View: {view_name}")
            lod_type = input("    LOD Type (FIXED/INCLUDE/EXCLUDE/None, default: None): ").strip().upper() or "NONE"
            
            if lod_type in ["FIXED", "INCLUDE", "EXCLUDE"]:
                dimensions_input = input("    Enter dimensions (comma-separated, e.g., date,region): ").strip()
                dimensions = [d.strip() for d in dimensions_input.split(",") if d.strip()]
                
                self.lod_configs[view_name] = LODConfig(
                    view_name=view_name,
                    lod_type=lod_type,
                    dimensions=dimensions
                )
                print(f"    ✓ Configured {lod_type} LOD with dimensions: {', '.join(dimensions)}")
            else:
                print(f"    ✓ No LOD (full transaction granularity)")
        
        return self.lod_configs
    
    async def generate_star_schema(self) -> Dict[str, Any]:
        """Generate star schema views using internal agents."""
        logger.info("Generating star schema views")
        
        # Step 1: Create reasoning plan
        reasoning_plan = await self.reasoning_agent.create_reasoning_plan(
            tables=self.tables,
            relationships=self.relationships,
            metrics=self.metrics,
            time_dimension=self.time_dimension,
            schema_context=self.schema_context
        )
        
        # Step 2: Create view specifications
        view_specs = await self.view_agent.create_views(
            reasoning_plan=reasoning_plan,
            tables=self.tables,
            relationships=self.relationships,
            metrics=self.metrics,
            time_dimension=self.time_dimension,
            lod_configs=self.lod_configs,
            schema_context=self.schema_context
        )
        
        # Step 3: Regenerate and optimize SQL
        regenerated_sql = []
        for view_spec in view_specs:
            optimized = await self.optimization_agent.regenerate_sql(
                view_spec=view_spec,
                tables=self.tables,
                relationships=self.relationships,
                schema_context=self.schema_context
            )
            regenerated_sql.append(optimized)
        
        return {
            "reasoning_plan": reasoning_plan,
            "view_specs": view_specs,
            "regenerated_sql": regenerated_sql
        }
    
    async def run_interactive_workflow(self, input_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run the complete interactive workflow."""
        print("\n" + "="*80)
        print("INTERACTIVE STAR SCHEMA BUILDER")
        print("="*80)
        
        # Step 1: Fetch all tables
        print("\nSTEP 1: Fetching tables from ChromaDB...")
        fetch_result = await self.fetch_all_tables()
        
        if not fetch_result.get("success"):
            return {"error": fetch_result.get("error"), "success": False}
        
        # Display tables
        if self.interactive_mode:
            print(self.display_tables_and_relationships())
        else:
            logger.info(f"Fetched {len(self.tables)} tables and {len(self.relationships)} relationships")
        
        # Step 2: Prompt for metrics
        self.prompt_for_metrics(input_data)
        
        # Step 3: Prompt for time dimension
        self.prompt_for_time_dimension(input_data)
        
        # Step 4: Generate views (LOD will be prompted after views are created)
        print("\nSTEP 4: Generating star schema views...")
        results = await self.generate_star_schema()
        
        # Step 5: Prompt for LOD expressions
        view_names = [vs.view_name for vs in results['view_specs']]
        self.prompt_for_lod_expressions(view_names, input_data)
        
        # Re-generate with LOD if configured
        if self.lod_configs:
            # Regenerate views with LOD configuration
            view_specs = await self.view_agent.create_views(
                reasoning_plan=results['reasoning_plan'],
                tables=self.tables,
                relationships=self.relationships,
                metrics=self.metrics,
                time_dimension=self.time_dimension,
                lod_configs=self.lod_configs,
                schema_context=self.schema_context
            )
            
            regenerated_sql = []
            for view_spec in view_specs:
                optimized = await self.optimization_agent.regenerate_sql(
                    view_spec=view_spec,
                    tables=self.tables,
                    relationships=self.relationships,
                    schema_context=self.schema_context
                )
                regenerated_sql.append(optimized)
            
            results['view_specs'] = view_specs
            results['regenerated_sql'] = regenerated_sql
        
        # Display results
        if self.interactive_mode:
            self._display_results(results)
        
        return {
            "success": True,
            "tables": self.tables,
            "relationships": self.relationships,
            "metrics": [m.__dict__ for m in self.metrics],
            "time_dimension": self.time_dimension.__dict__ if self.time_dimension else None,
            "lod_configs": {k: {"type": v.lod_type, "dimensions": v.dimensions} for k, v in self.lod_configs.items()},
            "view_specs": [vs.__dict__ for vs in results['view_specs']],
            "regenerated_sql": [rs.__dict__ for rs in results['regenerated_sql']]
        }
    
    def _display_results(self, results: Dict[str, Any]):
        """Display final results in a formatted way."""
        print("\n" + "="*80)
        print("STAR SCHEMA GENERATION COMPLETE")
        print("="*80)
        
        print(f"\n✓ Generated {len(results['view_specs'])} views")
        print(f"✓ Configured {len(self.metrics)} metrics")
        if self.time_dimension:
            print(f"✓ Time dimension: {self.time_dimension.table_name}.{self.time_dimension.column_name}")
        print(f"✓ LOD configurations: {len(self.lod_configs)}")
        
        print("\n=== VIEW SPECIFICATIONS ===")
        for vs in results['view_specs']:
            print(f"\n{vs.view_name} ({vs.view_type})")
            print(f"  Dimensions: {', '.join(vs.dimensions[:5])}")
            print(f"  Measures: {', '.join(vs.measures)}")
            if vs.level_of_details:
                lod = vs.level_of_details
                print(f"  LOD: {lod.get('type', 'None')} {lod.get('dimensions', [])}")


# Example usage
async def main():
    """Example usage of InteractiveStarSchemaBuilder."""
    import sys
    
    project_id = sys.argv[1] if len(sys.argv) > 1 else "sumtotal_learn"
    
    builder = InteractiveStarSchemaBuilder(
        project_id=project_id,
        interactive_mode=True
    )
    
    results = await builder.run_interactive_workflow()
    
    if results.get("success"):
        print("\n✓ Star schema generation completed successfully!")
    else:
        print(f"\n✗ Error: {results.get('error')}")


if __name__ == "__main__":
    asyncio.run(main())

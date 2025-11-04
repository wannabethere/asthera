"""
Unified SQL View Agent with three-stage processing:
1. Query Analysis & Reasoning Plan
2. View Creation
3. SQL Regeneration (RAG-based)

Uses comprehensive SQL rules for PostgreSQL-compliant view and query generation.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.schema import HumanMessage, SystemMessage
import chromadb
import json
import sqlglot
from sqlglot import parse_one as sqlglot_parse_one


# ============================================================================
# SQL Generation Rules (from sql_prompts.py)
# ============================================================================

TEXT_TO_SQL_RULES = """
#### SQL RULES ####
- ONLY USE SELECT statements, NO DELETE, UPDATE OR INSERT etc. statements that might change the data in the database.
- Strictly Support POSTGRES SQL Syntax.
- **CRITICAL**: ONLY USE the tables and columns mentioned in the database schema. **CRITICAL**: Only use columns that exist in the provided schema for a table. Don't create columns that don't exist in the schema.
- ONLY USE "*" if the user query asks for all the columns of a table.
- **CRITICAL**: ONLY CHOOSE columns belong to the tables mentioned in the database schema and make sure alias is used correctly from the table definition.
- **CRITICAL**: Only use columns that exist in the provided schema for a table. Don't mixup columns from different tables.
- DON'T INCLUDE comments in the generated SQL query.
- YOU MUST USE "JOIN" if you choose columns from multiple tables!
- ALWAYS QUALIFY column names with their table name or table alias to avoid ambiguity (e.g., orders.OrderId, o.OrderId)
- **IMPORTANT: Use column names exactly as they appear in the database schema (case-sensitive). If the schema shows 'division' (lowercase), use 'division', not 'Division'.**
- YOU MUST USE "lower(<table_name>.<column_name>) like lower(<value>)" function or "lower(<table_name>.<column_name>) = lower(<value>)" function for case-insensitive comparison!
    - Use "lower(<table_name>.<column_name>) LIKE lower(<value>)" when:
        - The user requests a pattern or partial match.
        - The value is not specific enough to be a single, exact value.
        - Wildcards (%) are needed to capture the pattern.
    - Use "lower(<table_name>.<column_name>) = lower(<value>)" when:
        - The user requests an exact, specific value.
        - There is no ambiguity or pattern in the value.
- ALWAYS CAST the date/time related field to "TIMESTAMP WITH TIME ZONE" type when using them in the query
    - example 1: CAST(properties_closedate AS TIMESTAMP WITH TIME ZONE)
    - example 2: CAST('2024-11-09 00:00:00' AS TIMESTAMP WITH TIME ZONE)
    - example 3: CAST(DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month') AS TIMESTAMP WITH TIME ZONE)
- If the user asks for a specific date, please give the date range in SQL query
    - example: "What is the total revenue for the month of 2024-11-01?"
    - answer: "SELECT SUM(r.PriceSum) FROM Revenue r WHERE CAST(r.PurchaseTimestamp AS TIMESTAMP WITH TIME ZONE) >= CAST('2024-11-01 00:00:00' AS TIMESTAMP WITH TIME ZONE) AND CAST(r.PurchaseTimestamp AS TIMESTAMP WITH TIME ZONE) < CAST('2024-11-02 00:00:00' AS TIMESTAMP WITH TIME ZONE)"
- USE THE VIEW TO SIMPLIFY THE QUERY.
- DON'T MISUSE THE VIEW NAME. THE ACTUAL NAME IS FOLLOWING THE CREATE VIEW STATEMENT.
- MUST USE the value of alias from the comment section of the corresponding table or column in the DATABASE SCHEMA section for the column/table alias.
- DON'T USE '.' in column/table alias, replace '.' with '_' in column/table alias.
- DON'T USE "FILTER(WHERE <expression>)" clause in the generated SQL query.
- DON'T USE "EXTRACT(EPOCH FROM <expression>)" clause in the generated SQL query.
- DON'T USE INTERVAL or generate INTERVAL-like expression in the generated SQL query.
- DONT USE HAVING CLAUSE WITHOUT GROUP BY CLAUSE.
- WHEN THRESHOLD OR CONDITIONS are found, use CTE Expressions to evaluate the conditions or thresholds.
- ONLY USE JSON_QUERY for querying fields if "json_type":"JSON" is identified in the columns comment, NOT the deprecated JSON_EXTRACT_SCALAR function.
- ONLY USE JSON_QUERY_ARRAY for querying "json_type":"JSON_ARRAY" is identified in the comment of the column.
- DON'T USE JSON_QUERY and JSON_QUERY_ARRAY when "json_type":"".
- DONT CREATE COLUMNS WHICH ARE NOT PRESENT IN THE DATABASE SCHEMA. CHECK FOR SPELLING ERRORS IN COLUMN NAMES TO AVOID ERRORS.
- DON'T USE LAX_BOOL, LAX_FLOAT64, LAX_INT64, LAX_STRING when "json_type":"".
- **RELATIONSHIP HANDLING**: When table relationships are provided, use them to create proper JOINs between tables. Pay attention to:
  - Join types (ONE_TO_ONE, ONE_TO_MANY, MANY_TO_ONE) to determine the appropriate JOIN syntax
  - Join conditions to ensure correct column matching between tables
  - Use the exact column names specified in the relationship conditions
  - Consider the relationship direction when writing JOIN clauses
- **FOR MATERIALIZED VIEWS**: Use proper aggregation functions (SUM, COUNT, AVG, MIN, MAX) and GROUP BY clauses
- **FOR MATERIALIZED VIEWS**: Include appropriate indexing considerations for frequently queried dimensions
- **FOR MATERIALIZED VIEWS**: Consider refresh strategies (INCREMENTAL vs FULL) based on data update patterns
"""

CALCULATED_FIELD_INSTRUCTIONS = """
#### Instructions for Calculated Fields ####

First, you will understand how to use Calculated Fields in a table schema when generating SQL queries.
Calculated Fields are special columns whose values are derived through calculations on related data, rather than being directly stored.
These fields are defined within a model and marked as "calculated: true" with an expression that defines how they should be computed.

When you encounter Calculated Fields in the schema:
1. Recognize them by the "calculated: true" indicator in the column definition
2. Understand their computation logic from the "expression" field
3. Use them directly in SQL queries as if they were regular columns
4. Do NOT try to replicate their calculation logic - the system handles this automatically

EXAMPLE:
If a schema contains:
/* {"displayName":"orders"} */
CREATE TABLE orders (
  OrderId VARCHAR,
  CustomerId VARCHAR,
  -- {"calculated":true,"expression":"avg(reviews.Score)"}
  Rating DOUBLE,
  -- {"calculated":true,"expression":"count(reviews.ReviewId)"}
  ReviewCount BIGINT,
  -- {"calculated":true,"expression":"count(order_items.ItemNumber)"}
  Size BIGINT,
  -- {"calculated":true,"expression":"count(order_items.ItemNumber) > 1"}
  Large BOOLEAN
)

For queries like "How many large orders have been placed by customer with ID 'C1234'?":
- Use: SELECT COUNT(*) FROM orders WHERE CustomerId = 'C1234' AND Large = true
- Don't manually calculate: SELECT COUNT(*) FROM orders o JOIN order_items oi ON o.OrderId = oi.OrderId WHERE o.CustomerId = 'C1234' GROUP BY o.OrderId HAVING COUNT(oi.ItemNumber) > 1
"""

METRIC_INSTRUCTIONS = """
#### Instructions for Metric ####

You will learn how to effectively utilize the special "metric" structure in SQL generation tasks.
Metrics in a data model simplify complex data analysis by structuring data through predefined dimensions and measures.

The metric typically consists of the following components:
1. Base Object: The primary data source or table that provides the raw data
2. Dimensions: Categorical fields for data segmentation (e.g., time, location, category)
3. Measures: Numerical statistics calculated from data (e.g., SUM, COUNT, AVG)
4. Time Grain: Granularity of time-based aggregation (daily, monthly, yearly)

When the schema contains structures marked as 'metric', interpret them based on this definition and use them appropriately in SQL queries.

EXAMPLE:
/* This table is a metric */
/* Metric Base Object: orders */
CREATE TABLE Revenue (
  -- This column is a dimension
  PurchaseTimestamp TIMESTAMP,
  -- This column is a dimension
  CustomerId VARCHAR,
  -- This column is a dimension
  Status VARCHAR,
  -- This column is a measure
  -- expression: sum(order_items.Price)
  PriceSum DOUBLE,
  -- This column is a measure
  -- expression: count(OrderId)
  NumberOfOrders BIGINT
)

For queries about revenue metrics, use the Revenue metric directly rather than computing from base tables.
Query: "What is the total revenue for customer 'C1234'?"
Use: SELECT SUM(PriceSum) FROM Revenue WHERE CustomerId = 'C1234'
Don't: SELECT SUM(oi.Price) FROM orders o JOIN order_items oi ON o.OrderId = oi.OrderId WHERE o.CustomerId = 'C1234'
"""


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
    source_tables: List[str] = None
    fact_key_columns: List[str] = None
    dimension_key_columns: List[str] = None
    level_of_details: Dict[str, Any] = None  # LOD expression in Tableau format: {"type": "FIXED|INCLUDE|EXCLUDE", "dimensions": [...]}
    
    def __post_init__(self):
        if self.source_tables is None:
            self.source_tables = []
        if self.fact_key_columns is None:
            self.fact_key_columns = []
        if self.dimension_key_columns is None:
            self.dimension_key_columns = []
        if self.level_of_details is None:
            self.level_of_details = {}


@dataclass
class RegeneratedSQL:
    """Regenerated SQL for a view with validation and optimization details"""
    view_name: str
    original_sql: str
    regenerated_sql: str
    improvements: List[str]
    schema_alignment: Dict[str, Any]
    suggested_indexes: List[str] = None
    column_corrections: List[Dict[str, str]] = None
    
    def __post_init__(self):
        if self.suggested_indexes is None:
            self.suggested_indexes = []
        if self.column_corrections is None:
            self.column_corrections = []


@dataclass
class Configuration:
    """Configuration for SQL generation context"""
    fiscal_year_start: Optional[str] = None  # e.g., "01-04" for April 1st
    fiscal_year_end: Optional[str] = None    # e.g., "03-31" for March 31st
    timezone: str = "UTC"
    language: str = "English"
    has_calculated_fields: bool = False
    has_metrics: bool = False
    
    def get_instructions(self) -> str:
        """Build custom instructions based on configuration"""
        instructions = ""
        
        if self.fiscal_year_start and self.fiscal_year_end:
            instructions += f"\n- For fiscal year related computation, it should start from {self.fiscal_year_start} to {self.fiscal_year_end}\n"
        
        if self.has_calculated_fields:
            instructions += f"\n{CALCULATED_FIELD_INSTRUCTIONS}\n"
        
        if self.has_metrics:
            instructions += f"\n{METRIC_INSTRUCTIONS}\n"
        
        return instructions


class UnifiedSQLViewAgent:
    """
    Three-stage agent system for SQL query analysis, view creation, and SQL regeneration.
    Uses ChromaDB for schema context and LangChain for LLM orchestration.
    """
    
    def __init__(
        self,
        llm: ChatAnthropic,
        chroma_client: chromadb.Client,
        collection_name: str = "sql_schema",
        configuration: Optional[Configuration] = None
    ):
        self.llm = llm
        self.chroma_client = chroma_client
        self.collection_name = collection_name
        self.schema_collection = None
        self.configuration = configuration or Configuration()
        self._initialize_schema_collection()
    
    def _initialize_schema_collection(self):
        """Initialize or get existing ChromaDB collection for schema"""
        try:
            self.schema_collection = self.chroma_client.get_collection(
                name=self.collection_name
            )
        except:
            self.schema_collection = self.chroma_client.create_collection(
                name=self.collection_name,
                metadata={"description": "Database schema metadata"}
            )
    
    def add_schema_metadata(
        self,
        tables: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]]
    ):
        """Add table and relationship metadata to ChromaDB"""
        documents = []
        metadatas = []
        ids = []
        
        # Add table metadata
        for idx, table in enumerate(tables):
            table_name = table.get("name", f"table_{idx}")
            columns = table.get("columns", [])
            table_description = table.get("description", "")
            table_display_name = table.get("display_name", "")
            
            doc = f"Table: {table_name}\n"
            if table_display_name:
                doc += f"Display Name: {table_display_name}\n"
            if table_description:
                doc += f"Description: {table_description}\n"
            doc += f"Columns: {', '.join([c.get('name', '') for c in columns])}\n"
            doc += f"Column Details:\n"
            for col in columns:
                col_name = col.get("name", "")
                # Try data_type first, fallback to type
                col_type = col.get("data_type") or col.get("type", "")
                col_description = col.get("description") or col.get("business_description", "")
                col_display_name = col.get("display_name", "")
                col_comment = col.get("comment", "")
                col_usage_type = col.get("usage_type", "")  # dimension, measure, attribute
                col_properties = col.get("properties", {})
                
                doc += f"  - {col_name} ({col_type})"
                if col_display_name:
                    doc += f" | Display: {col_display_name}"
                if col_description:
                    doc += f" | Description: {col_description}"
                if col_comment:
                    doc += f" | Comment: {col_comment}"
                if col_usage_type:
                    doc += f" | Usage: {col_usage_type}"
                if col_properties and isinstance(col_properties, dict):
                    # Include relevant business attributes from properties
                    business_attrs = []
                    if col_properties.get("displayName"):
                        business_attrs.append(f"displayName: {col_properties['displayName']}")
                    if col_properties.get("alias"):
                        business_attrs.append(f"alias: {col_properties['alias']}")
                    if business_attrs:
                        doc += f" | Business: {', '.join(business_attrs)}"
                doc += "\n"
            
            documents.append(doc)
            metadatas.append({
                "type": "table",
                "name": table_name,
                "column_count": len(columns)
            })
            ids.append(f"table_{idx}_{table_name}")
        
        # Add relationship metadata
        for idx, rel in enumerate(relationships):
            from_table = rel.get("from_table", "")
            to_table = rel.get("to_table", "")
            from_col = rel.get("from_column", "")
            to_col = rel.get("to_column", "")
            
            doc = f"Relationship: {from_table}.{from_col} -> {to_table}.{to_col}\n"
            doc += f"Type: {rel.get('relationship_type', 'foreign_key')}"
            
            documents.append(doc)
            metadatas.append({
                "type": "relationship",
                "from_table": from_table,
                "to_table": to_table
            })
            ids.append(f"rel_{idx}_{from_table}_{to_table}")
        
        if documents:
            self.schema_collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
    
    def _retrieve_schema_context(self, queries: List[str], n_results: int = 10) -> str:
        """Retrieve relevant schema context from ChromaDB based on queries"""
        # Combine queries for context retrieval
        query_text = "\n".join(queries)
        
        results = self.schema_collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        
        context = "=== RELEVANT SCHEMA CONTEXT ===\n\n"
        if results and results.get("documents"):
            for doc in results["documents"][0]:
                context += doc + "\n\n"
        
        return context

    def _ast_for_sql(self, sql: str) -> Dict[str, Any]:
        """Parse SQL into AST and return JSON plus normalized SQL. Falls back gracefully on errors."""
        try:
            expr = sqlglot_parse_one(sql, read="postgres")
            ast_json = None
            if hasattr(expr, "to_json"):
                try:
                    ast_json = expr.to_json()
                except Exception:
                    ast_json = expr.dump()
            else:
                ast_json = expr.dump()
            normalized_sql = expr.sql(dialect="postgres")
            return {"ast_json": ast_json, "normalized_sql": normalized_sql}
        except Exception:
            return {"ast_json": "", "normalized_sql": sql}

    def _parse_queries_ast(self, queries: List[str]) -> List[Dict[str, Any]]:
        """Return per-query AST and normalized SQL for prompt conditioning."""
        results: List[Dict[str, Any]] = []
        for q in queries:
            parsed = self._ast_for_sql(q)
            results.append({
                "original_sql": q,
                "normalized_sql": parsed.get("normalized_sql", q),
                "ast_json": parsed.get("ast_json", "")
            })
        return results
    
    # ============================================================================
    # AGENT 1: Query Analysis & Reasoning Plan
    # ============================================================================
    
    def agent_1_create_reasoning_plan(
        self,
        queries: List[str],
        chain_of_thought_examples: Optional[List[Dict[str, Any]]] = None
    ) -> ReasoningPlan:
        """
        First agent: Analyze queries and create a reasoning plan.
        Uses chain-of-thought examples to guide reasoning.
        """
        schema_context = self._retrieve_schema_context(queries)
        ast_entries = self._parse_queries_ast(queries)
        
        # Default chain-of-thought examples if none provided
        if not chain_of_thought_examples:
            chain_of_thought_examples = [
                {
                    "queries": ["SELECT customer_id, SUM(amount) FROM orders GROUP BY customer_id"],
                    "reasoning": "This query aggregates order amounts by customer. Pattern: GROUP BY aggregation on numeric measure.",
                    "dimensions": ["customer_id"],
                    "measures": ["SUM(amount)"],
                    "patterns": ["customer_aggregation", "financial_metric"]
                },
                {
                    "queries": [
                        "SELECT date, COUNT(*) FROM events WHERE type='click' GROUP BY date",
                        "SELECT date, COUNT(*) FROM events WHERE type='view' GROUP BY date"
                    ],
                    "reasoning": "Both queries follow time-series pattern filtering by event type. Can be unified into a single view with type as dimension.",
                    "dimensions": ["date", "type"],
                    "measures": ["COUNT(*)"],
                    "patterns": ["time_series", "event_tracking", "categorical_filter"]
                }
            ]
        
        # Format examples for prompt
        examples_text = "=== CHAIN-OF-THOUGHT EXAMPLES ===\n\n"
        for idx, ex in enumerate(chain_of_thought_examples, 1):
            examples_text += f"Example {idx}:\n"
            examples_text += f"Queries:\n"
            for q in ex["queries"]:
                examples_text += f"  - {q}\n"
            examples_text += f"Reasoning: {ex['reasoning']}\n"
            examples_text += f"Dimensions: {', '.join(ex['dimensions'])}\n"
            examples_text += f"Measures: {', '.join(ex['measures'])}\n"
            examples_text += f"Patterns: {', '.join(ex['patterns'])}\n\n"
        
        ast_context = "=== SQL AST CONTEXT ===\n\n"
        for i, entry in enumerate(ast_entries, 1):
            ast_context += f"Query {i} (normalized):\n{entry['normalized_sql']}\nAST JSON:\n{entry['ast_json']}\n\n"

        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are an expert SQL analyst specializing in query pattern recognition and optimization.
Your task is to analyze a collection of SQL queries and create a comprehensive reasoning plan.

Focus on:
1. Identifying common patterns (GROUP BY aggregations, time-series, joins, filters)
2. Extracting dimensions (columns used for grouping or filtering)
3. Extracting measures (aggregated columns like SUM, COUNT, AVG)
4. Grouping similar queries that can share common views
5. Understanding the analytical intent behind queries

Respond in JSON format with:
{
  "reasoning": "detailed analysis of query patterns and intent",
  "query_groups": [
    {
      "group_name": "descriptive name",
      "queries": ["query1", "query2"],
      "common_pattern": "description",
      "shared_elements": ["list of shared columns/logic"]
    }
  ],
  "patterns": ["pattern1", "pattern2"],
  "dimensions": ["dim1", "dim2"],
  "measures": ["measure1", "measure2"]
}"""),
            HumanMessage(content=f"""{examples_text}

{schema_context}

=== QUERIES TO ANALYZE ===

{chr(10).join([f"{idx+1}. {q}" for idx, q in enumerate(queries)])}

{ast_context}

Analyze these queries following the chain-of-thought approach shown in the examples.
Provide your reasoning plan in JSON format.""")
        ])
        
        chain = prompt | self.llm | StrOutputParser()
        response_text = chain.invoke({})
        
        # Parse response
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
            # Fallback parsing
            return ReasoningPlan(
                reasoning=response_text,
                query_groups=[{"group_name": "all_queries", "queries": queries}],
                patterns=["general"],
                dimensions=[],
                measures=[]
            )
    
    # ============================================================================
    # AGENT 2: View Creation
    # ============================================================================
    
    def agent_2_create_views(
        self,
        reasoning_plan: ReasoningPlan,
        queries: List[str],
        instructions: Optional[str] = None,
        examples: Optional[List[Dict[str, Any]]] = None,
        level_of_details_config: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> List[ViewSpec]:
        """
        Second agent: Create materialized view definitions in star schema format.
        Creates three types of views:
        1. Source table views - base tables from the schema
        2. Fact table views - fact tables with measures/metrics
        3. Dimension table views - dimension tables with descriptive attributes
        
        This logical representation allows replacing views with external views if they already exist.
        Uses custom instructions and examples.
        
        Args:
            reasoning_plan: The reasoning plan from agent 1
            queries: Original SQL queries
            instructions: Optional custom instructions
            examples: Optional custom examples
            level_of_details_config: Optional dict mapping view names to LOD expressions in Tableau format.
                                     Format: {
                                       "mv_fact_sales": {
                                         "type": "FIXED",  // or "INCLUDE" or "EXCLUDE"
                                         "dimensions": ["order_date", "region"]
                                       },
                                       ...
                                     }
                                     Supports FIXED, INCLUDE, EXCLUDE LOD types like Tableau.
                                     If not provided or empty for a view, no deduplication is applied.
        """
        schema_context = self._retrieve_schema_context(queries)
        ast_entries = self._parse_queries_ast(queries)
        
        # Default instructions - combine with configuration
        if not instructions:
            instructions = """
Create optimized materialized views in STAR SCHEMA format:
1. **SOURCE TABLE VIEWS**: Base views that represent source tables from the schema
   - Use table name as view name (e.g., mv_source_orders)
   - Preserve all columns from source tables
   - These are logical representations of base tables that can be replaced by external views
   
2. **FACT TABLE VIEWS**: Fact tables containing business metrics and measures at the LOWEST GRANULARITY
   - **CRITICAL**: Create fact tables at the transaction/event level (lowest granularity)
   - Each row represents a single transaction, event, or measurable occurrence
   - Do NOT pre-aggregate in fact tables - preserve one row per transaction/event
   - Use descriptive names (e.g., mv_fact_sales_transactions, mv_fact_order_items)
   - Include foreign keys to dimension tables for drill-down capability
   - Include raw measures at the transaction level (amount, quantity, price, etc.)
   - Avoid GROUP BY in fact tables - aggregations should happen in queries, not in fact tables
   - This granularity enables maximum flexibility for ad-hoc analysis and drill-down
   
   **DEDUPLICATION (Level of Details / LOD) - Tableau-style expressions**:
   - LOD expressions follow Tableau's format: { FIXED | INCLUDE | EXCLUDE [dimensions] : aggregate }
   - **FIXED LOD**: Compute at specified granularity, ignoring view dimensions
     * Example: { FIXED [order_date, region] : SUM(amount) } - aggregates at date+region level
     * Use DISTINCT ON or GROUP BY with specified dimensions
   - **INCLUDE LOD**: Compute using specified dimensions PLUS any dimensions in queries/view
     * Example: { INCLUDE [customer_id] : SUM(amount) } - aggregates at customer level, then reaggregates in view
     * Preserves granularity but allows reaggregation
   - **EXCLUDE LOD**: Remove specified dimensions from view granularity
     * Example: { EXCLUDE [region] : SUM(amount) } - aggregates excluding region dimension
     * Useful for "percent of total" scenarios
   - If NO LOD is specified for a view, NO deduplication should be applied - keep all rows at transaction level
   - Format: {"type": "FIXED|INCLUDE|EXCLUDE", "dimensions": ["col1", "col2"]}
   
3. **DIMENSION TABLE VIEWS**: Dimension tables with descriptive attributes
   - Use descriptive names (e.g., mv_dim_customer, mv_dim_date, mv_dim_product)
   - Include dimension keys (primary keys or surrogate keys)
   - Include descriptive attributes (names, categories, hierarchies)
   - Support filtering and grouping in analytical queries

Design principles:
- Fact tables MUST be at the LOWEST GRANULARITY (transaction/event level) - this is the most important principle
- Fact tables can include additional columns that are not present in the queries - these columns are not used for deduplication and are used for additional analysis.
- Dimension tables can include additional tables/columns from source tables that can be related to other dimensions present- For example: sales, orders, inventory, etc.
- Time Dimension table should be created but can also imported from external sources like a data warehouse or data lake.
- Preserve one row per transaction/event in fact tables - do NOT pre-aggregate
- Aggregations happen in analytical queries, not in fact tables
- Support drill-down analysis (time, location, category dimensions) through dimension foreign keys
- Maximize flexibility for ad-hoc analysis by keeping granular data in fact tables
- Use incremental refresh where possible
- Include proper indexing considerations (especially on fact primary keys and dimension foreign keys)
- Enable replacement with external views if data already exists
"""
        
        # Add configuration-specific instructions
        config_instructions = self.configuration.get_instructions()
        if config_instructions:
            instructions = instructions + "\n" + config_instructions
        
        # Default examples in star schema format
        if not examples:
            examples = [
                {
                    "view_type": "source",
                    "reasoning": "Base source table for orders data",
                    "view_name": "mv_source_orders",
                    "sql": "CREATE MATERIALIZED VIEW mv_source_orders AS SELECT order_id -- Description: Unique order identifier | DataType: INT | DisplayName: Order ID | Usage: dimension, customer_id -- Description: Customer who placed the order | DataType: INT | DisplayName: Customer ID | Usage: dimension, CAST(order_date AS TIMESTAMP WITH TIME ZONE) as order_date -- Description: Date and time when order was placed | DataType: TIMESTAMP WITH TIME ZONE | DisplayName: Order Date | Usage: dimension, amount -- Description: Total order amount | DataType: DECIMAL | DisplayName: Order Amount | Usage: measure, region -- Description: Geographic region of order | DataType: VARCHAR | DisplayName: Region | Usage: dimension, status -- Description: Current status of the order | DataType: VARCHAR | DisplayName: Status | Usage: dimension FROM orders",
                    "source_tables": ["orders"],
                    "dimensions": [],
                    "measures": [],
                    "refresh_strategy": "full"
                },
                {
                    "view_type": "fact",
                    "reasoning": "Fact table for sales transactions at the lowest granularity - one row per order (no deduplication)",
                    "view_name": "mv_fact_sales_transactions",
                    "sql": "CREATE MATERIALIZED VIEW mv_fact_sales_transactions AS SELECT order_id -- Description: Unique order identifier | DataType: INT | DisplayName: Order ID | Usage: dimension, customer_id -- Description: Customer who placed the order | DataType: INT | DisplayName: Customer ID | Usage: dimension, CAST(order_date AS TIMESTAMP WITH TIME ZONE) as order_date -- Description: Date and time when order was placed | DataType: TIMESTAMP WITH TIME ZONE | DisplayName: Order Date | Usage: dimension, region -- Description: Geographic region of order | DataType: VARCHAR | DisplayName: Region | Usage: dimension, status -- Description: Current status of the order | DataType: VARCHAR | DisplayName: Status | Usage: dimension, amount as order_amount -- Description: Total order amount | DataType: DECIMAL | DisplayName: Order Amount | Usage: measure FROM mv_source_orders",
                    "source_tables": ["mv_source_orders"],
                    "fact_key_columns": ["order_id"],
                    "dimensions": ["customer_id", "order_date", "region", "status"],
                    "measures": ["order_amount"],
                    "refresh_strategy": "incremental",
                    "level_of_details": {}
                },
                {
                    "view_type": "fact",
                    "reasoning": "Fact table for sales transactions with FIXED LOD at order_date and region granularity",
                    "view_name": "mv_fact_sales_fixed_date_region",
                    "sql": "CREATE MATERIALIZED VIEW mv_fact_sales_by_date_region AS SELECT DISTINCT ON (CAST(order_date AS TIMESTAMP WITH TIME ZONE), region) CAST(order_date AS TIMESTAMP WITH TIME ZONE) as order_date -- Description: Date and time when order was placed | DataType: TIMESTAMP WITH TIME ZONE | DisplayName: Order Date | Usage: dimension, region -- Description: Geographic region of order | DataType: VARCHAR | DisplayName: Region | Usage: dimension, order_id -- Description: Unique order identifier | DataType: INT | DisplayName: Order ID | Usage: dimension, customer_id -- Description: Customer who placed the order | DataType: INT | DisplayName: Customer ID | Usage: dimension, status -- Description: Current status of the order | DataType: VARCHAR | DisplayName: Status | Usage: dimension, amount as order_amount -- Description: Total order amount | DataType: DECIMAL | DisplayName: Order Amount | Usage: measure FROM mv_source_orders ORDER BY CAST(order_date AS TIMESTAMP WITH TIME ZONE), region, order_id",
                    "source_tables": ["mv_source_orders"],
                    "fact_key_columns": ["order_date", "region"],
                    "dimensions": ["customer_id", "order_date", "region", "status"],
                    "measures": ["order_amount"],
                    "refresh_strategy": "incremental",
                    "level_of_details": {"type": "FIXED", "dimensions": ["order_date", "region"]}
                },
                {
                    "view_type": "fact",
                    "reasoning": "Fact table for sales with INCLUDE LOD - computes at customer level, allows reaggregation",
                    "view_name": "mv_fact_sales_include_customer",
                    "sql": "CREATE MATERIALIZED VIEW mv_fact_sales_include_customer AS SELECT customer_id -- Description: Customer who placed the order | DataType: INT | DisplayName: Customer ID | Usage: dimension, CAST(order_date AS TIMESTAMP WITH TIME ZONE) as order_date -- Description: Date and time when order was placed | DataType: TIMESTAMP WITH TIME ZONE | DisplayName: Order Date | Usage: dimension, region -- Description: Geographic region of order | DataType: VARCHAR | DisplayName: Region | Usage: dimension, order_id -- Description: Unique order identifier | DataType: INT | DisplayName: Order ID | Usage: dimension, status -- Description: Current status of the order | DataType: VARCHAR | DisplayName: Status | Usage: dimension, amount as order_amount -- Description: Total order amount | DataType: DECIMAL | DisplayName: Order Amount | Usage: measure FROM mv_source_orders",
                    "source_tables": ["mv_source_orders"],
                    "fact_key_columns": ["customer_id"],
                    "dimensions": ["customer_id", "order_date", "region", "status"],
                    "measures": ["order_amount"],
                    "refresh_strategy": "incremental",
                    "level_of_details": {"type": "INCLUDE", "dimensions": ["customer_id"]}
                },
                {
                    "view_type": "dimension",
                    "reasoning": "Dimension table for customer attributes",
                    "view_name": "mv_dim_customer",
                    "sql": "CREATE MATERIALIZED VIEW mv_dim_customer AS SELECT DISTINCT customer_id -- Description: Unique customer identifier | DataType: INT | DisplayName: Customer ID | Usage: dimension, customer_name -- Description: Full name of the customer | DataType: VARCHAR | DisplayName: Customer Name | Usage: attribute, region -- Description: Customer's region | DataType: VARCHAR | DisplayName: Region | Usage: dimension, signup_date -- Description: Date when customer signed up | DataType: DATE | DisplayName: Signup Date | Usage: dimension FROM customers",
                    "source_tables": ["customers"],
                    "dimension_key_columns": ["customer_id"],
                    "dimensions": ["customer_id", "customer_name", "region", "signup_date"],
                    "measures": [],
                    "refresh_strategy": "full"
                }
            ]
        
        # Format examples
        examples_text = "=== STAR SCHEMA VIEW CREATION EXAMPLES ===\n\n"
        for idx, ex in enumerate(examples, 1):
            examples_text += f"Example {idx} ({ex.get('view_type', 'fact')}):\n"
            examples_text += f"View Type: {ex.get('view_type', 'fact')}\n"
            examples_text += f"Reasoning: {ex['reasoning']}\n"
            examples_text += f"View Name: {ex['view_name']}\n"
            examples_text += f"SQL: {ex['sql']}\n"
            examples_text += f"Source Tables: {', '.join(ex.get('source_tables', []))}\n"
            if ex.get('fact_key_columns'):
                examples_text += f"Fact Key Columns: {', '.join(ex.get('fact_key_columns', []))}\n"
            if ex.get('dimension_key_columns'):
                examples_text += f"Dimension Key Columns: {', '.join(ex.get('dimension_key_columns', []))}\n"
            if ex.get('level_of_details') and isinstance(ex.get('level_of_details'), dict) and ex.get('level_of_details').get('type'):
                lod = ex.get('level_of_details')
                examples_text += f"Level of Details (LOD): {lod.get('type')} {lod.get('dimensions', [])} - Tableau-style LOD expression\n"
            elif ex.get('level_of_details'):
                examples_text += f"Level of Details (LOD): {ex.get('level_of_details')} - Deduplication applied\n"
            else:
                examples_text += f"Level of Details (LOD): None - No deduplication (full transaction granularity)\n"
            examples_text += f"Dimensions: {', '.join(ex.get('dimensions', []))}\n"
            examples_text += f"Measures: {', '.join(ex.get('measures', []))}\n"
            examples_text += f"Refresh: {ex['refresh_strategy']}\n\n"
        
        ast_context = "=== SQL AST CONTEXT ===\n\n"
        for i, entry in enumerate(ast_entries, 1):
            ast_context += f"Query {i} (normalized):\n{entry['normalized_sql']}\nAST JSON:\n{entry['ast_json']}\n\n"

        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=f"""You are an expert database architect specializing in PostgreSQL star schema and materialized view design.
Your task is to create optimal materialized view definitions in STAR SCHEMA format based on a reasoning plan.

{instructions}

{TEXT_TO_SQL_RULES}

{CALCULATED_FIELD_INSTRUCTIONS}

{METRIC_INSTRUCTIONS}

**CRITICAL STAR SCHEMA MATERIALIZED VIEW REQUIREMENTS**:
1. Use CREATE MATERIALIZED VIEW syntax for PostgreSQL
2. Organize views into three types: source, fact, and dimension
3. **SOURCE VIEWS**: Represent base tables, use 'mv_source_' prefix
4. **FACT VIEWS** (MOST IMPORTANT): 
   - MUST be created at the LOWEST GRANULARITY (transaction/event level)
   - Each row = one transaction, event, or measurable occurrence
   - DO NOT use GROUP BY in fact tables - preserve one row per transaction
   - Include all dimension foreign keys for drill-down capability
   - Include raw measures at transaction level (amounts, quantities, etc.)
   - Use 'mv_fact_' prefix with descriptive names (e.g., mv_fact_sales_transactions)
   - Aggregations should be done in queries, NOT in fact tables
   
   **FACT VIEW DEDUPLICATION (Level of Details / LOD) - Tableau-style**:
   - LOD expressions use Tableau format with FIXED, INCLUDE, or EXCLUDE types
   - LOD config format: {"view_name": {"type": "FIXED|INCLUDE|EXCLUDE", "dimensions": ["col1", "col2"]}}
   - **FIXED**: Use DISTINCT ON (dimensions) or GROUP BY (dimensions) - computes at specified granularity only
   - **INCLUDE**: Computes at fine granularity (dimensions + transaction), allows reaggregation in queries
   - **EXCLUDE**: Removes specified dimensions from granularity - useful for percentage/total calculations
   - If NO LOD is specified for a view, apply NO deduplication - keep all transaction rows
   - Reference: Tableau LOD expressions (https://help.tableau.com/current/pro/desktop/en-us/calculations_calculatedfields_lod.htm)
5. **DIMENSION VIEWS**: Contain descriptive attributes, use 'mv_dim_' prefix, include dimension keys
6. Qualify all column names with table aliases
7. Use proper CAST for date/time fields to TIMESTAMP WITH TIME ZONE
8. Follow all JOIN requirements from the SQL rules above
9. Validate all columns exist in the schema (retrieved from ChromaDB)
10. Enable logical replacement - views can reference other views (source -> fact/dimension)
11. Consider indexing on frequently filtered dimensions and fact key columns (primary keys)

**CRITICAL: COLUMN COMMENTS AND METADATA**:
12. **MUST include column comments** with business attributes for natural language query support:
    - For each column in the SELECT statement, add inline comments with:
      * Column description/business description
      * Data type
      * Display name (if available)
      * Usage type (dimension, measure, attribute)
      * Any business attributes from properties (displayName, alias, etc.)
    - Use PostgreSQL COMMENT syntax: `column_name data_type -- Description: ... | DataType: ... | DisplayName: ... | Usage: ...`
    - Example: `order_amount DECIMAL -- Description: Total order amount | DataType: DECIMAL | DisplayName: Order Amount | Usage: measure`
    - Include ALL available column metadata from the schema context
    - These comments enable natural language queries on dashboards built from these views

Respond in JSON format with an array of views organized by type:
[
  {{
    "view_type": "source|fact|dimension",
    "view_name": "mv_source_|mv_fact_|mv_dim_descriptive_name",
    "reasoning": "why this view is needed and what queries it serves",
    "source_queries": ["query1", "query2"],
    "source_tables": ["table1", "mv_source_table1"],
    "sql_definition": "CREATE MATERIALIZED VIEW mv_name AS SELECT column1 -- Description: ... | DataType: ... | DisplayName: ... | Usage: ..., column2 -- Description: ... FROM ...",  // NO GROUP BY for fact tables - use lowest granularity, INCLUDE COLUMN COMMENTS
    "fact_key_columns": ["key1", "key2"],  // For fact views: columns that join to dimensions
    "dimension_key_columns": ["key1"],  // For dimension views: primary key columns
    "dimensions": ["table.dim1", "table.dim2"],
    "measures": ["raw_measure1", "raw_measure2"],  // Raw measures at transaction level (NO aggregations like SUM/COUNT/AVG)
    "refresh_strategy": "incremental|full|on-demand",
    "level_of_details": {{"type": "FIXED|INCLUDE|EXCLUDE", "dimensions": ["col1", "col2"]}}  // Optional: LOD expression in Tableau format. If empty/null, no deduplication
  }}
]

Organize the views logically:
- First create source table views (base tables)
- Then create dimension views (descriptive attributes)
- Finally create fact views (transaction-level data with raw measures)

**REMEMBER**: Fact tables MUST be at the LOWEST GRANULARITY - one row per transaction/event.
DO NOT aggregate in fact tables. Aggregations happen in analytical queries that JOIN fact and dimension tables.
"""),
            HumanMessage(content=f"""{examples_text}

{schema_context}

=== REASONING PLAN ===

Reasoning: {reasoning_plan.reasoning}

Query Groups:
{json.dumps(reasoning_plan.query_groups, indent=2)}

Patterns: {', '.join(reasoning_plan.patterns)}
Dimensions: {', '.join(reasoning_plan.dimensions)}
Measures: {', '.join(reasoning_plan.measures)}

=== ORIGINAL QUERIES ===

{chr(10).join([f"{idx+1}. {q}" for idx, q in enumerate(queries)])}

{ast_context}

{f"=== LEVEL OF DETAILS (LOD) CONFIGURATION (Tableau-style) ===\n\n" + json.dumps(level_of_details_config, indent=2) + "\n\n" if level_of_details_config else ""}Apply deduplication to fact views based on LOD configuration above. LOD expressions follow Tableau format:
- FIXED: Compute at specified granularity only (use DISTINCT ON or GROUP BY)
- INCLUDE: Compute at fine granularity (dimensions + transaction), allows reaggregation
- EXCLUDE: Remove dimensions from granularity (for percentage/total calculations)
If no LOD is specified for a view, do NOT apply deduplication - keep all transaction rows.

Create materialized view definitions in STAR SCHEMA format following the examples and instructions.
Organize views into source, fact, and dimension types.
This logical representation allows replacing views with external views if they already exist.
Respond with JSON array of view specifications.""")
        ])
        
        chain = prompt | self.llm | StrOutputParser()
        response_text = chain.invoke({})
        
        # Parse response
        try:
            views_data = json.loads(response_text)
            views = []
            for v in views_data:
                view_name = v.get("view_name", "mv_unnamed")
                # Get LOD for this view from config, or from response, or empty dict
                lod_expr = {}
                if level_of_details_config and view_name in level_of_details_config:
                    lod_expr = level_of_details_config[view_name]
                    # Ensure it's a dict with type and dimensions
                    if not isinstance(lod_expr, dict):
                        # Legacy format: convert list to FIXED LOD
                        lod_expr = {"type": "FIXED", "dimensions": lod_expr if isinstance(lod_expr, list) else []}
                elif v.get("level_of_details"):
                    lod_expr = v.get("level_of_details", {})
                    if isinstance(lod_expr, list):
                        # Legacy format: convert list to FIXED LOD
                        lod_expr = {"type": "FIXED", "dimensions": lod_expr}
                
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
            # Get LOD for default view if specified
            lod_expr = {}
            if level_of_details_config and "mv_unified" in level_of_details_config:
                lod_expr = level_of_details_config["mv_unified"]
                # Ensure it's a dict with type and dimensions
                if not isinstance(lod_expr, dict):
                    lod_expr = {"type": "FIXED", "dimensions": lod_expr if isinstance(lod_expr, list) else []}
            
            return [ViewSpec(
                view_name="mv_unified",
                reasoning=response_text,
                source_queries=queries,
                sql_definition=response_text,
                dimensions=reasoning_plan.dimensions,
                measures=reasoning_plan.measures,
                refresh_strategy="incremental",
                view_type="fact",
                source_tables=[],
                fact_key_columns=[],
                dimension_key_columns=[],
                level_of_details=lod_expr
            )]
    
    # ============================================================================
    # AGENT 3: SQL Regeneration (RAG-based)
    # ============================================================================
    
    def agent_3_regenerate_sql(
        self,
        view_specs: List[ViewSpec],
        original_queries: List[str]
    ) -> List[RegeneratedSQL]:
        """
        Third agent: Regenerate SQL for views using RAG architecture.
        Retrieves schema context and optimizes view definitions.
        """
        regenerated = []
        
        for view_spec in view_specs:
            # Retrieve relevant schema for this specific view
            schema_context = self._retrieve_schema_context(
                [view_spec.sql_definition] + view_spec.source_queries,
                n_results=15
            )
            
            # AST context for current view and its source queries
            view_ast = self._ast_for_sql(view_spec.sql_definition or "")
            src_ast_entries = self._parse_queries_ast(view_spec.source_queries)
            ast_context = "=== SQL AST CONTEXT ===\n\n"
            ast_context += f"Current View (normalized):\n{view_ast.get('normalized_sql', '')}\nAST JSON:\n{view_ast.get('ast_json', '')}\n\n"
            for i, entry in enumerate(src_ast_entries, 1):
                ast_context += f"Source Query {i} (normalized):\n{entry['normalized_sql']}\nAST JSON:\n{entry['ast_json']}\n\n"

            prompt = ChatPromptTemplate.from_messages([
                SystemMessage(content=f"""You are an expert SQL optimizer using RAG (Retrieval-Augmented Generation) approach.
Your task is to regenerate and optimize PostgreSQL materialized view definitions using retrieved schema context.

{TEXT_TO_SQL_RULES}

{CALCULATED_FIELD_INSTRUCTIONS}

{METRIC_INSTRUCTIONS}

**CRITICAL VALIDATION REQUIREMENTS**:
1. Verify ALL columns exist in the retrieved schema context
2. Verify ALL tables exist in the retrieved schema context
3. Use exact column names (case-sensitive) as they appear in schema
4. Apply proper table relationships and JOIN conditions
5. Use proper CAST for date/time fields to TIMESTAMP WITH TIME ZONE
6. Qualify all columns with table names or aliases
7. Follow PostgreSQL syntax strictly
8. **MUST preserve and include column comments** with business attributes:
   - For each column in SELECT, include inline comments with description, data type, display name, and usage type
   - Format: `column_name data_type -- Description: ... | DataType: ... | DisplayName: ... | Usage: ...`
   - Extract metadata from the retrieved schema context
   - These comments are critical for natural language query support on dashboards
9. Add comments explaining complex logic

**OPTIMIZATION FOCUS**:
1. Schema alignment - ensure columns exist and have correct types
2. Join optimization - use proper foreign key relationships from schema
3. Index hints - suggest useful indexes based on WHERE/GROUP BY clauses
4. Query efficiency - remove redundant operations, optimize aggregations
5. Maintainability - clear aliasing, formatting, and documentation

Respond in JSON format:
{{
  "regenerated_sql": "Complete CREATE MATERIALIZED VIEW statement with all optimizations",
  "improvements": ["Specific improvement 1", "Specific improvement 2"],
  "schema_alignment": {{
    "tables_used": ["table1", "table2"],
    "columns_validated": ["table1.col1", "table2.col2"],
    "relationships_applied": ["table1.fk_col = table2.pk_col (ONE_TO_MANY)"],
    "missing_columns": [],
    "column_corrections": [{{"from": "wrong_name", "to": "correct_name"}}]
  }},
  "suggested_indexes": ["CREATE INDEX idx_name ON view_name(column1, column2)"]
}}"""),
                HumanMessage(content=f"""=== RETRIEVED SCHEMA CONTEXT ===

{schema_context}

=== VIEW SPECIFICATION ===

View Name: {view_spec.view_name}
Original SQL Definition:
{view_spec.sql_definition}

Reasoning: {view_spec.reasoning}
Dimensions: {', '.join(view_spec.dimensions)}
Measures: {', '.join(view_spec.measures)}
Refresh Strategy: {view_spec.refresh_strategy}

=== SOURCE QUERIES ===

{chr(10).join([f"{idx+1}. {q}" for idx, q in enumerate(view_spec.source_queries)])}

Using the retrieved schema context, regenerate an optimized SQL definition for this view.
Ensure all columns exist, relationships are correct, and the SQL is efficient.
{ast_context}

Respond in JSON format.""")
            ])
            
            chain = prompt | self.llm | StrOutputParser()
            response_text = chain.invoke({})
            
            # Parse response
            try:
                result = json.loads(response_text)
                regenerated.append(RegeneratedSQL(
                    view_name=view_spec.view_name,
                    original_sql=view_spec.sql_definition,
                    regenerated_sql=result.get("regenerated_sql", view_spec.sql_definition),
                    improvements=result.get("improvements", []),
                    schema_alignment=result.get("schema_alignment", {}),
                    suggested_indexes=result.get("suggested_indexes", []),
                    column_corrections=result.get("schema_alignment", {}).get("column_corrections", [])
                ))
            except json.JSONDecodeError:
                # Fallback
                regenerated.append(RegeneratedSQL(
                    view_name=view_spec.view_name,
                    original_sql=view_spec.sql_definition,
                    regenerated_sql=response_text,
                    improvements=["Regenerated with LLM"],
                    schema_alignment={},
                    suggested_indexes=[],
                    column_corrections=[]
                ))
        
        return regenerated
    
    def validate_sql(self, sql: str) -> Dict[str, Any]:
        """
        Validate generated SQL against the comprehensive rules.
        Returns validation results with warnings and errors.
        """
        warnings = []
        errors = []
        info = []
        
        # Check for prohibited statements
        prohibited_keywords = ['DELETE', 'UPDATE', 'INSERT', 'DROP', 'ALTER', 'TRUNCATE']
        for keyword in prohibited_keywords:
            if keyword in sql.upper():
                errors.append(f"Prohibited keyword found: {keyword}")
        
        # Check for unqualified column names (basic check)
        if 'SELECT' in sql.upper() and 'FROM' in sql.upper():
            # Look for common patterns that might indicate unqualified columns
            if ',' in sql and not any(x in sql for x in ['.', ' AS ']):
                warnings.append("Possible unqualified column names detected")
        
        # Check for proper date casting
        if any(date_term in sql.lower() for date_term in ['date', 'timestamp', 'time']):
            if 'CAST' not in sql.upper() and 'TIMESTAMP WITH TIME ZONE' not in sql.upper():
                warnings.append("Date/time fields should be CAST to TIMESTAMP WITH TIME ZONE")
        
        # Check for case-insensitive comparison
        if 'WHERE' in sql.upper() or 'LIKE' in sql.upper():
            if 'LIKE' in sql.upper() and 'lower(' not in sql.lower():
                warnings.append("Consider using lower() for case-insensitive LIKE comparisons")
        
        # Check for HAVING without GROUP BY
        if 'HAVING' in sql.upper() and 'GROUP BY' not in sql.upper():
            errors.append("HAVING clause used without GROUP BY")
        
        # Check for proper view naming
        if 'CREATE MATERIALIZED VIEW' in sql.upper():
            if 'mv_' not in sql.lower():
                info.append("View name should start with 'mv_' prefix")
        
        # Check for JSON functions
        deprecated_json = ['JSON_EXTRACT_SCALAR', 'JSON_EXTRACT_ARRAY']
        for func in deprecated_json:
            if func in sql.upper():
                errors.append(f"Deprecated JSON function found: {func}. Use JSON_QUERY or JSON_QUERY_ARRAY instead")
        
        # Check for INTERVAL usage
        if 'INTERVAL' in sql.upper():
            warnings.append("INTERVAL usage detected - verify if needed or can be avoided")
        
        # Check for FILTER clause
        if 'FILTER(WHERE' in sql.upper():
            errors.append("FILTER(WHERE ...) clause should not be used")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "info": info,
            "score": max(0, 100 - (len(errors) * 25) - (len(warnings) * 10))
        }
    
    # ============================================================================
    # Main Pipeline
    # ============================================================================
    
    def process_queries(
        self,
        queries: List[str],
        chain_of_thought_examples: Optional[List[Dict[str, Any]]] = None,
        view_instructions: Optional[str] = None,
        view_examples: Optional[List[Dict[str, Any]]] = None,
        validate_output: bool = True,
        level_of_details_config: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Run the complete three-stage pipeline:
        1. Create reasoning plan
        2. Generate view specifications
        3. Regenerate optimized SQL
        
        Returns complete results from all three agents with optional validation.
        """
        print("🔍 Stage 1: Creating reasoning plan...")
        reasoning_plan = self.agent_1_create_reasoning_plan(
            queries=queries,
            chain_of_thought_examples=chain_of_thought_examples
        )
        
        print("🏗️  Stage 2: Creating view specifications...")
        view_specs = self.agent_2_create_views(
            reasoning_plan=reasoning_plan,
            queries=queries,
            instructions=view_instructions,
            examples=view_examples
        )
        
        print("♻️  Stage 3: Regenerating optimized SQL...")
        regenerated_sql = self.agent_3_regenerate_sql(
            view_specs=view_specs,
            original_queries=queries
        )
        
        # Validate generated SQL
        validation_results = []
        if validate_output:
            print("✅ Validating generated SQL...")
            for regen in regenerated_sql:
                validation = self.validate_sql(regen.regenerated_sql)
                validation_results.append({
                    "view_name": regen.view_name,
                    "validation": validation
                })
        
        return {
            "reasoning_plan": reasoning_plan,
            "view_specs": view_specs,
            "regenerated_sql": regenerated_sql,
            "validation_results": validation_results,
            "summary": {
                "total_queries": len(queries),
                "query_groups": len(reasoning_plan.query_groups),
                "views_created": len(view_specs),
                "patterns_identified": reasoning_plan.patterns,
                "validation_passed": sum(1 for v in validation_results if v["validation"]["is_valid"]),
                "total_errors": sum(len(v["validation"]["errors"]) for v in validation_results),
                "total_warnings": sum(len(v["validation"]["warnings"]) for v in validation_results)
            }
        }


# ============================================================================
# Usage Example
# ============================================================================

def load_payload_and_extract_queries(payload_path: str) -> tuple[List[str], Dict[str, Any]]:
    """
    Load render-report payload and extract SQL queries from thread_components.
    
    Args:
        payload_path: Path to the JSON payload file
        
    Returns:
        Tuple of (list of SQL queries, payload metadata)
    """
    import os
    
    # Try to read the payload file
    if not os.path.exists(payload_path):
        raise FileNotFoundError(f"Payload file not found: {payload_path}")
    
    with open(payload_path, 'r', encoding='utf-8') as f:
        payload = json.load(f)
    
    # Extract SQL queries from thread_components
    queries = []
    for component in payload.get("thread_components", []):
        # Check for sql_query field
        sql_query = component.get("sql_query") or component.get("sql", "")
        if sql_query and sql_query.strip():
            queries.append(sql_query.strip())
        
        # Also check in nested execution_info
        execution_info = component.get("execution_info", {})
        if isinstance(execution_info, dict):
            exec_sql = execution_info.get("sql_query") or execution_info.get("sql", "")
            if exec_sql and exec_sql.strip() and exec_sql not in queries:
                queries.append(exec_sql.strip())
    
    # Extract metadata for schema setup
    project_id = payload.get("project_id", "default")
    workflow_metadata = payload.get("workflow_metadata", {})
    
    return queries, {
        "project_id": project_id,
        "workflow_id": payload.get("workflow_id"),
        "workflow_metadata": workflow_metadata,
        "total_components": len(payload.get("thread_components", []))
    }

from langchain_openai import OpenAIEmbeddings
from app.settings import get_settings
import logging
import os
from pathlib import Path
import chromadb
from app.storage.documents import DocumentChromaStore
from app.settings import get_settings
from app.dependencies import get_chromadb_client
from typing import List, Dict, Any, Optional
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("genieml-agents")
settings = get_settings()


class UnifiedStores:
    
    def __init__(
        self,
        base_path: str = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/sql_meta",
        persistent_client: chromadb.PersistentClient = None,
        embeddings: OpenAIEmbeddings = None,
        use_local_storage: bool = True
    ):
        """Initialize ProjectReader2 with unified storage.
        
        Args:
            base_path: Base path to the project directory
            persistent_client: Optional ChromaDB persistent client
            embeddings: Optional embeddings model
            use_local_storage: If True, use local ChromaDB storage (default: True)
        """
        logger.info(f"Initializing ProjectReader2 with base path: {base_path}")
        self.base_path = Path(base_path)
        
        # Initialize ChromaDB client
        if persistent_client is not None:
            self.persistent_client = persistent_client
        elif use_local_storage:
            # Force local storage
            local_path = os.environ.get("CHROMA_STORE_PATH", "./chroma_db")
            logger.info(f"Using local ChromaDB storage at: {local_path}")
            self.persistent_client = chromadb.PersistentClient(path=local_path)
        else:
            # Use remote client from dependencies
            self.persistent_client = get_chromadb_client()
        
        # Get settings for embeddings
        settings = get_settings()
        self.embeddings = embeddings or OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.OPENAI_API_KEY
        )
        
        # Initialize document stores
        logger.info("Initializing document stores")
        self._init_document_stores()
        
        # Initialize components with unified storage
        logger.info("Initializing unified storage components")
        self._init_components()
        
        logger.info("ProjectReader2 initialization complete")
    
    def _init_document_stores(self):
        """Initialize document stores for unified storage."""
        logger.info("Setting up document stores")
        
        # Create unified document store
        self.unified_doc_store = DocumentChromaStore(
            persistent_client=self.persistent_client,
            collection_name="unified_storage",
            embeddings_model=self.embeddings
        )
        
        # Create store for SQL pairs
        self.sql_pairs_store = DocumentChromaStore(
            persistent_client=self.persistent_client,
            collection_name="sql_pairs",
            embeddings_model=self.embeddings
        )
        
        # Create store for historical questions
        self.historical_question_store = DocumentChromaStore(
            persistent_client=self.persistent_client,
            collection_name="historical_question",
            embeddings_model=self.embeddings
        )
        
        # Create store for instructions
        self.instructions_store = DocumentChromaStore(
            persistent_client=self.persistent_client,
            collection_name="instructions",
            embeddings_model=self.embeddings
        )
        
        logger.info("Document stores initialized successfully")


if __name__ == "__main__":
    import sys
    import os
    
    # Check if payload file path is provided as argument
    payload_path = None
    if len(sys.argv) > 1:
        payload_path = sys.argv[1]
    
    # Initialize with configuration
    llm = ChatAnthropic(model="claude-sonnet-4-5-20250929", temperature=0)
    chroma_client = chromadb.Client()
    
    # Configure with fiscal year and schema metadata
    config = Configuration(
        fiscal_year_start="04-01",  # April 1st
        fiscal_year_end="03-31",    # March 31st
        timezone="America/New_York",
        has_calculated_fields=True,
        has_metrics=True
    )
    
    # Determine collection name and queries based on payload or default
    schema_loaded = False  # Track if schema was loaded from payload
    if payload_path and os.path.exists(payload_path):
        print(f"📥 Loading payload from: {payload_path}")
        queries, payload_meta = load_payload_and_extract_queries(payload_path)
        collection_name = f"{payload_meta['project_id']}_schema"
        
        print(f"✅ Loaded {len(queries)} SQL queries from payload")
        print(f"   Project ID: {payload_meta['project_id']}")
        print(f"   Workflow ID: {payload_meta['workflow_id']}")
        print(f"   Total Components: {payload_meta['total_components']}")
        
        agent = UnifiedSQLViewAgent(
            llm=llm,
            chroma_client=chroma_client,
            collection_name=collection_name,
            configuration=config
        )
        
        # Try to load schema from common location if exists
        schema_path = f"data/sql_meta/{payload_meta['project_id']}/mdl.json"
        if os.path.exists(schema_path):
            print(f"📊 Loading schema from: {schema_path}")
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema_data = json.load(f)
            
            # Extract tables and relationships from schema
            # This is a simplified extraction - adjust based on your schema format
            tables = schema_data.get("tables", [])
            relationships = schema_data.get("relationships", [])
            
            if tables or relationships:
                agent.add_schema_metadata(tables, relationships)
                print(f"✅ Added {len(tables)} tables and {len(relationships)} relationships to schema")
                schema_loaded = True
        else:
            print(f"⚠️  Schema file not found at {schema_path}, continuing without explicit schema")
    else:
        # Default example queries
        print("📝 Using default example queries")
        collection_name = "sales_schema"
        queries = [
            "SELECT CAST(order_date AS TIMESTAMP WITH TIME ZONE) as order_date, region, SUM(amount) as total_amount FROM orders GROUP BY order_date, region",
            "SELECT CAST(order_date AS TIMESTAMP WITH TIME ZONE) as order_date, COUNT(*) as order_count FROM orders GROUP BY order_date",
            "SELECT region, AVG(amount) as avg_amount, COUNT(*) as order_count FROM orders GROUP BY region",
            "SELECT o.customer_id, c.customer_name, SUM(oi.price * oi.quantity) as total_spent FROM orders o JOIN customers c ON o.customer_id = c.customer_id JOIN order_items oi ON o.order_id = oi.order_id GROUP BY o.customer_id, c.customer_name"
        ]
        
        agent = UnifiedSQLViewAgent(
            llm=llm,
            chroma_client=chroma_client,
            collection_name=collection_name,
            configuration=config
        )
    
    # Add comprehensive schema metadata with descriptions, datatypes, and comments
    tables = [
        {
            "name": "orders",
            "display_name": "Orders",
            "description": "Table containing order transactions and details",
            "columns": [
                {
                    "name": "order_id",
                    "data_type": "INT",
                    "type": "INT",
                    "description": "Unique order identifier",
                    "display_name": "Order ID",
                    "comment": "Primary key for orders table",
                    "usage_type": "dimension",
                    "properties": {"displayName": "Order ID", "alias": "order_id"}
                },
                {
                    "name": "customer_id",
                    "data_type": "INT",
                    "type": "INT",
                    "description": "Customer who placed the order",
                    "display_name": "Customer ID",
                    "comment": "Foreign key to customers table",
                    "usage_type": "dimension",
                    "properties": {"displayName": "Customer ID", "alias": "customer_id"}
                },
                {
                    "name": "order_date",
                    "data_type": "TIMESTAMP",
                    "type": "TIMESTAMP",
                    "description": "Date and time when order was placed",
                    "display_name": "Order Date",
                    "comment": "Timestamp of order creation",
                    "usage_type": "dimension",
                    "properties": {"displayName": "Order Date", "alias": "order_date"}
                },
                {
                    "name": "amount",
                    "data_type": "DECIMAL",
                    "type": "DECIMAL",
                    "description": "Total order amount",
                    "display_name": "Order Amount",
                    "comment": "Monetary value of the order",
                    "usage_type": "measure",
                    "properties": {"displayName": "Order Amount", "alias": "amount"}
                },
                {
                    "name": "region",
                    "data_type": "VARCHAR",
                    "type": "VARCHAR",
                    "description": "Geographic region of order",
                    "display_name": "Region",
                    "comment": "Sales region where order was placed",
                    "usage_type": "dimension",
                    "properties": {"displayName": "Region", "alias": "region"}
                },
                {
                    "name": "status",
                    "data_type": "VARCHAR",
                    "type": "VARCHAR",
                    "description": "Current status of the order",
                    "display_name": "Status",
                    "comment": "Order status: pending, completed, cancelled",
                    "usage_type": "dimension",
                    "properties": {"displayName": "Status", "alias": "status"}
                }
            ]
        },
        {
            "name": "customers",
            "display_name": "Customers",
            "description": "Table containing customer information",
            "columns": [
                {
                    "name": "customer_id",
                    "data_type": "INT",
                    "type": "INT",
                    "description": "Unique customer identifier",
                    "display_name": "Customer ID",
                    "comment": "Primary key for customers table",
                    "usage_type": "dimension",
                    "properties": {"displayName": "Customer ID", "alias": "customer_id"}
                },
                {
                    "name": "customer_name",
                    "data_type": "VARCHAR",
                    "type": "VARCHAR",
                    "description": "Full name of the customer",
                    "display_name": "Customer Name",
                    "comment": "Customer's full name",
                    "usage_type": "attribute",
                    "properties": {"displayName": "Customer Name", "alias": "customer_name"}
                },
                {
                    "name": "signup_date",
                    "data_type": "DATE",
                    "type": "DATE",
                    "description": "Date when customer signed up",
                    "display_name": "Signup Date",
                    "comment": "Customer registration date",
                    "usage_type": "dimension",
                    "properties": {"displayName": "Signup Date", "alias": "signup_date"}
                },
                {
                    "name": "email",
                    "data_type": "VARCHAR",
                    "type": "VARCHAR",
                    "description": "Customer email address",
                    "display_name": "Email",
                    "comment": "Customer contact email",
                    "usage_type": "attribute",
                    "properties": {"displayName": "Email", "alias": "email"}
                }
            ]
        },
        {
            "name": "order_items",
            "display_name": "Order Items",
            "description": "Table containing individual items within orders",
            "columns": [
                {
                    "name": "item_id",
                    "data_type": "INT",
                    "type": "INT",
                    "description": "Unique item identifier",
                    "display_name": "Item ID",
                    "comment": "Primary key for order items",
                    "usage_type": "dimension",
                    "properties": {"displayName": "Item ID", "alias": "item_id"}
                },
                {
                    "name": "order_id",
                    "data_type": "INT",
                    "type": "INT",
                    "description": "Order this item belongs to",
                    "display_name": "Order ID",
                    "comment": "Foreign key to orders table",
                    "usage_type": "dimension",
                    "properties": {"displayName": "Order ID", "alias": "order_id"}
                },
                {
                    "name": "product_id",
                    "data_type": "INT",
                    "type": "INT",
                    "description": "Product identifier",
                    "display_name": "Product ID",
                    "comment": "Foreign key to products table",
                    "usage_type": "dimension",
                    "properties": {"displayName": "Product ID", "alias": "product_id"}
                },
                {
                    "name": "quantity",
                    "data_type": "INT",
                    "type": "INT",
                    "description": "Quantity of items ordered",
                    "display_name": "Quantity",
                    "comment": "Number of units in this order item",
                    "usage_type": "measure",
                    "properties": {"displayName": "Quantity", "alias": "quantity"}
                },
                {
                    "name": "price",
                    "data_type": "DECIMAL",
                    "type": "DECIMAL",
                    "description": "Price per unit",
                    "display_name": "Unit Price",
                    "comment": "Price for a single unit of the product",
                    "usage_type": "measure",
                    "properties": {"displayName": "Unit Price", "alias": "price"}
                }
            ]
        }
    ]
    
    relationships = [
        {
            "from_table": "orders",
            "from_column": "customer_id",
            "to_table": "customers",
            "to_column": "customer_id",
            "relationship_type": "MANY_TO_ONE"
        },
        {
            "from_table": "order_items",
            "from_column": "order_id",
            "to_table": "orders",
            "to_column": "order_id",
            "relationship_type": "MANY_TO_ONE"
        }
    ]
    
    # Add comprehensive schema metadata for default example (only if not loaded from payload)
    # Only add default schema if we're using default queries OR if payload schema wasn't found
    if not payload_path or not os.path.exists(payload_path):
        agent.add_schema_metadata(tables, relationships)
    else:
        # Check if schema was loaded in the if branch above
        if not schema_loaded:
            # Fallback to default schema if payload schema not found
            print(f"⚠️  Using default schema metadata (payload schema not found)")
            agent.add_schema_metadata(tables, relationships)
    
    # Provide chain-of-thought examples
    cot_examples = [
        {
            "queries": [
                "SELECT date, region, SUM(sales) FROM orders GROUP BY date, region",
                "SELECT date, COUNT(*) FROM orders GROUP BY date"
            ],
            "reasoning": "Both queries aggregate by date. First adds region dimension. Pattern: Time-series with optional geographic breakdown.",
            "dimensions": ["date", "region"],
            "measures": ["SUM(sales)", "COUNT(*)"],
            "patterns": ["time_series", "geographic_analysis", "aggregation"]
        }
    ]
    
    # Provide view examples in star schema format
    view_examples = [
        {
            "view_type": "source",
            "reasoning": "Base source table for orders data",
            "view_name": "mv_source_orders",
            "sql": "CREATE MATERIALIZED VIEW mv_source_orders AS SELECT order_id -- Description: Unique order identifier | DataType: INT | DisplayName: Order ID | Usage: dimension, customer_id -- Description: Customer who placed the order | DataType: INT | DisplayName: Customer ID | Usage: dimension, CAST(order_date AS TIMESTAMP WITH TIME ZONE) as order_date -- Description: Date and time when order was placed | DataType: TIMESTAMP WITH TIME ZONE | DisplayName: Order Date | Usage: dimension, amount -- Description: Total order amount | DataType: DECIMAL | DisplayName: Order Amount | Usage: measure, region -- Description: Geographic region of order | DataType: VARCHAR | DisplayName: Region | Usage: dimension, status -- Description: Current status of the order | DataType: VARCHAR | DisplayName: Status | Usage: dimension FROM orders",
            "source_tables": ["orders"],
            "dimensions": [],
            "measures": [],
            "refresh_strategy": "full"
        },
        {
            "view_type": "fact",
            "reasoning": "Fact table for sales transactions at the lowest granularity - one row per order",
            "view_name": "mv_fact_sales_transactions",
            "sql": "CREATE MATERIALIZED VIEW mv_fact_sales_transactions AS SELECT order_id -- Description: Unique order identifier | DataType: INT | DisplayName: Order ID | Usage: dimension, customer_id -- Description: Customer who placed the order | DataType: INT | DisplayName: Customer ID | Usage: dimension, CAST(order_date AS TIMESTAMP WITH TIME ZONE) as order_date -- Description: Date and time when order was placed | DataType: TIMESTAMP WITH TIME ZONE | DisplayName: Order Date | Usage: dimension, region -- Description: Geographic region of order | DataType: VARCHAR | DisplayName: Region | Usage: dimension, status -- Description: Current status of the order | DataType: VARCHAR | DisplayName: Status | Usage: dimension, amount as order_amount -- Description: Total order amount | DataType: DECIMAL | DisplayName: Order Amount | Usage: measure FROM mv_source_orders",
            "source_tables": ["mv_source_orders"],
            "fact_key_columns": ["order_id"],
            "dimensions": ["customer_id", "order_date", "region", "status"],
            "measures": ["order_amount"],
            "refresh_strategy": "incremental"
        },
        {
            "view_type": "dimension",
            "reasoning": "Dimension table for customer attributes",
            "view_name": "mv_dim_customer",
            "sql": "CREATE MATERIALIZED VIEW mv_dim_customer AS SELECT DISTINCT customer_id -- Description: Unique customer identifier | DataType: INT | DisplayName: Customer ID | Usage: dimension, customer_name -- Description: Full name of the customer | DataType: VARCHAR | DisplayName: Customer Name | Usage: attribute, region -- Description: Customer's region | DataType: VARCHAR | DisplayName: Region | Usage: dimension, signup_date -- Description: Date when customer signed up | DataType: DATE | DisplayName: Signup Date | Usage: dimension FROM customers",
            "source_tables": ["customers"],
            "dimension_key_columns": ["customer_id"],
            "dimensions": ["customer_id", "customer_name", "region", "signup_date"],
            "measures": [],
            "refresh_strategy": "full"
        }
    ]
    
    results = agent.process_queries(
        queries=queries,
        chain_of_thought_examples=cot_examples,
        view_examples=view_examples
    )
    
    print("\n" + "="*80)
    print("UNIFIED SQL VIEW AGENT - RESULTS")
    print("="*80)
    
    print("\n📊 STAGE 1: REASONING PLAN")
    print("-" * 80)
    print(f"Reasoning: {results['reasoning_plan'].reasoning}")
    print(f"\nPatterns Identified: {', '.join(results['reasoning_plan'].patterns)}")
    print(f"Dimensions: {', '.join(results['reasoning_plan'].dimensions)}")
    print(f"Measures: {', '.join(results['reasoning_plan'].measures)}")
    print(f"\nQuery Groups: {len(results['reasoning_plan'].query_groups)}")
    for i, group in enumerate(results['reasoning_plan'].query_groups, 1):
        print(f"  {i}. {group.get('group_name', 'Unnamed')}: {len(group.get('queries', []))} queries")
    
    print("\n🏗️  STAGE 2: VIEW SPECIFICATIONS (STAR SCHEMA)")
    print("-" * 80)
    print(f"Views Created: {len(results['view_specs'])}\n")
    
    # Group views by type
    source_views = [v for v in results['view_specs'] if v.view_type == "source"]
    fact_views = [v for v in results['view_specs'] if v.view_type == "fact"]
    dimension_views = [v for v in results['view_specs'] if v.view_type == "dimension"]
    
    if source_views:
        print("📊 SOURCE TABLE VIEWS:")
        for i, view in enumerate(source_views, 1):
            print(f"   {i}. {view.view_name}")
            print(f"      Reasoning: {view.reasoning[:80]}...")
            print(f"      Source Tables: {', '.join(view.source_tables) if view.source_tables else 'N/A'}")
            print(f"      Refresh: {view.refresh_strategy}")
            print(f"      SQL Preview: {view.sql_definition[:120]}...")
            print()
    
    if dimension_views:
        print("📐 DIMENSION TABLE VIEWS:")
        for i, view in enumerate(dimension_views, 1):
            print(f"   {i}. {view.view_name}")
            print(f"      Reasoning: {view.reasoning[:80]}...")
            print(f"      Source Tables: {', '.join(view.source_tables) if view.source_tables else 'N/A'}")
            print(f"      Dimension Keys: {', '.join(view.dimension_key_columns) if view.dimension_key_columns else 'N/A'}")
            print(f"      Dimensions: {', '.join(view.dimensions) if view.dimensions else 'N/A'}")
            print(f"      Refresh: {view.refresh_strategy}")
            print(f"      SQL Preview: {view.sql_definition[:120]}...")
            print()
    
    if fact_views:
        print("⭐ FACT TABLE VIEWS:")
        for i, view in enumerate(fact_views, 1):
            print(f"   {i}. {view.view_name}")
            print(f"      Reasoning: {view.reasoning[:80]}...")
            print(f"      Source Tables: {', '.join(view.source_tables) if view.source_tables else 'N/A'}")
            print(f"      Fact Keys: {', '.join(view.fact_key_columns) if view.fact_key_columns else 'N/A'}")
            print(f"      Dimensions: {', '.join(view.dimensions) if view.dimensions else 'N/A'}")
            print(f"      Measures: {', '.join(view.measures) if view.measures else 'N/A'}")
            print(f"      Refresh: {view.refresh_strategy}")
            print(f"      SQL Preview: {view.sql_definition[:120]}...")
            print()
    
    # Display any views that don't match the above types
    other_views = [v for v in results['view_specs'] if v.view_type not in ["source", "fact", "dimension"]]
    if other_views:
        print("📋 OTHER VIEWS:")
        for i, view in enumerate(other_views, 1):
            print(f"   {i}. {view.view_name} (Type: {view.view_type})")
            print(f"      Reasoning: {view.reasoning[:80]}...")
            print(f"      Dimensions: {', '.join(view.dimensions)}")
            print(f"      Measures: {', '.join(view.measures)}")
            print(f"      Refresh: {view.refresh_strategy}")
            print(f"      SQL Preview: {view.sql_definition[:120]}...")
            print()
    
    print("\n♻️  STAGE 3: REGENERATED SQL")
    print("-" * 80)
    for i, regen in enumerate(results['regenerated_sql'], 1):
        print(f"{i}. {regen.view_name}")
        print(f"   Improvements:")
        for improvement in regen.improvements[:3]:
            print(f"      - {improvement}")
        print(f"   Tables Used: {', '.join(regen.schema_alignment.get('tables_used', []))}")
        print(f"   Columns Validated: {len(regen.schema_alignment.get('columns_validated', []))}")
        if regen.suggested_indexes:
            print(f"   Suggested Indexes: {len(regen.suggested_indexes)}")
        if regen.column_corrections:
            print(f"   Column Corrections: {len(regen.column_corrections)}")
        print(f"   SQL Preview: {regen.regenerated_sql[:150]}...")
        print()
    
    print("\n📈 SUMMARY")
    print("-" * 80)
    print(f"Total Queries Processed: {results['summary']['total_queries']}")
    print(f"Query Groups: {results['summary']['query_groups']}")
    print(f"Views Created: {results['summary']['views_created']}")
    print(f"Patterns: {', '.join(results['summary']['patterns_identified'])}")
    
    if results.get('validation_results'):
        print(f"\n✅ Validation Results:")
        print(f"   Passed: {results['summary']['validation_passed']}/{len(results['validation_results'])}")
        print(f"   Total Errors: {results['summary']['total_errors']}")
        print(f"   Total Warnings: {results['summary']['total_warnings']}")
        
        # Show details for any views with errors
        for val_result in results['validation_results']:
            if val_result['validation']['errors']:
                print(f"\n   ⚠️  {val_result['view_name']}:")
                for error in val_result['validation']['errors']:
                    print(f"      ERROR: {error}")
            elif val_result['validation']['warnings']:
                print(f"\n   ⚡ {val_result['view_name']}:")
                for warning in val_result['validation']['warnings'][:2]:
                    print(f"      WARNING: {warning}")
    
    print("\n" + "="*80)

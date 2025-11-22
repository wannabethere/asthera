"""
Cube.js Data Model Generation Agent using LangGraph
Medallion Architecture: Raw → Silver → Gold

This agent workflow orchestrates the creation of Cube.js data models
from DDL schemas following data quality and transformation best practices.
"""

from typing import TypedDict, List, Dict, Any, Optional, Annotated
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from pydantic import BaseModel, Field
import json
import operator
import pandas as pd
import asyncio
import logging

# Import metadata enrichment functionality
from app.agents.cubes.metadata_enrichment import enrich_table_metadata as enrich_metadata
# Note: SilverHumanInLoopAgent imported lazily to avoid circular dependency
from app.core.dependencies import get_llm

logger = logging.getLogger("genieml-agents")


def log_llm_call(stage: str, messages: List, response: Any, max_response_length: int = 500):
    """
    Log LLM request and response for debugging.
    
    Args:
        stage: Name of the stage/operation
        messages: List of messages sent to LLM
        response: LLM response object
        max_response_length: Maximum length of response to log (truncate if longer)
    """
    system_msg = next((msg.content for msg in messages if isinstance(msg, SystemMessage)), None)
    user_msg = next((msg.content for msg in messages if isinstance(msg, HumanMessage)), None)
    
    logger.info(f"\n{'='*80}")
    logger.info(f"🤖 LLM CALL: {stage}")
    logger.info(f"{'='*80}")
    
    if system_msg:
        logger.debug(f"System Message: {system_msg[:200]}...")
    
    if user_msg:
        user_preview = user_msg[:300] + "..." if len(user_msg) > 300 else user_msg
        logger.info(f"User Prompt Preview: {user_preview}")
    
    if hasattr(response, 'content'):
        response_content = response.content
        if len(response_content) > max_response_length:
            logger.info(f"LLM Response ({len(response_content)} chars, truncated):\n{response_content[:max_response_length]}...")
            logger.debug(f"Full Response:\n{response_content}")
        else:
            logger.info(f"LLM Response ({len(response_content)} chars):\n{response_content}")
    else:
        logger.info(f"LLM Response: {response}")
    
    logger.info(f"{'='*80}\n")


# ============================================================================
# SCHEMA ANALYSIS RULES - STAR SCHEMA DATA MODELING
# ============================================================================

SCHEMA_ANALYSIS_RULES = """
#### STAR SCHEMA DATA MODELING RULES ####

## OVERVIEW
- Analyze database schemas using Star Schema principles: Facts (measures) and Dimensions
- Identify Time Dimensions for temporal analysis
- Classify columns as Dimensions, Measures, or Time Filters
- Analyze sample data (100-200 rows per table) to validate classifications
- Detect relationships and hierarchies

## DIMENSION IDENTIFICATION RULES

### **CRITICAL**: Dimension Column Characteristics
- **STRING/VARCHAR/TEXT columns**: Typically dimensions (names, descriptions, categories, codes)
  - Examples: customer_name, product_category, region, status, country_code
  - EXCEPTION: If string represents a unique identifier (UUID, hash) and has high cardinality (>1000 distinct values), it may be a key, not a dimension
- **BOOLEAN columns**: Always dimensions (yes/no, true/false attributes)
  - Examples: is_active, is_premium, has_discount
- **ENUM/CATEGORICAL columns**: Always dimensions (limited set of values)
  - Examples: order_status, priority_level, account_type
- **LOW CARDINALITY NUMERIC columns**: May be dimensions if they represent categories
  - Examples: status_code (0,1,2,3), priority (1-5), rating_level (1-5)
  - Rule: If distinct count < 20 and represents categories, treat as dimension
- **FOREIGN KEY columns**: Always dimensions (link to dimension tables)
  - Examples: customer_id, product_id, region_id
  - These create relationships to other tables

### Dimension Naming Patterns
- Columns ending in: _id, _code, _name, _type, _status, _category, _level, _group
- Columns starting with: is_, has_, can_, should_
- Descriptive attributes: color, size, brand, model, version

### Dimension Hierarchies
- Identify natural hierarchies: Country → Region → City, Year → Quarter → Month → Day
- Look for parent-child relationships in dimension columns
- Detect time hierarchies: date → year/month/day/week

## TIME DIMENSION IDENTIFICATION RULES

### **CRITICAL**: Time Column Characteristics
- **TIMESTAMP/DATETIME columns**: Always time dimensions
  - Examples: created_at, updated_at, order_date, transaction_time
  - Use for time-based filtering and grouping
- **DATE columns**: Always time dimensions
  - Examples: birth_date, start_date, end_date, effective_date
- **TIME columns**: Time dimensions (for time-of-day analysis)
  - Examples: event_time, scheduled_time
- **YEAR/MONTH/DAY columns**: Time dimensions (pre-aggregated time)
  - Examples: order_year, transaction_month, report_day

### Time Dimension Types
1. **Event Time**: When something happened (transaction_date, created_at)
2. **Effective Time**: When something becomes valid (effective_date, start_date)
3. **Expiry Time**: When something expires (end_date, expiry_date)
4. **Audit Time**: When record was created/updated (created_at, updated_at)

### Time Filter Rules
- **CRITICAL**: Identify the PRIMARY time dimension for each fact table
  - Usually the event/transaction timestamp
  - Used for time-based filtering in queries
- **CRITICAL**: For each time column, identify:
  - Granularity: Year, Quarter, Month, Week, Day, Hour, Minute, Second
  - Timezone: UTC, local, or timezone-aware
  - Format: ISO 8601, Unix timestamp, custom format
- **CRITICAL**: Detect time ranges (start_date + end_date pairs)
  - Examples: subscription_start + subscription_end, valid_from + valid_to

## FACT/MEASURE IDENTIFICATION RULES

### **CRITICAL**: Measure Column Characteristics
- **NUMERIC columns that are AGGREGATABLE**: Always measures
  - INTEGER/BIGINT: Counts, quantities, IDs (if not FK)
  - DECIMAL/NUMERIC/FLOAT/DOUBLE: Amounts, prices, rates, percentages
  - Examples: revenue, quantity, price, discount_amount, tax_rate, total_cost
- **HIGH CARDINALITY NUMERIC columns**: Usually measures
  - If distinct count > 100 and represents continuous values, it's a measure
  - Examples: transaction_amount, order_total, customer_lifetime_value
- **CALCULATED/COMPUTED columns**: May be measures if numeric
  - Examples: profit (revenue - cost), margin_percentage, growth_rate

### Measure Types
1. **Additive Measures**: Can be summed across all dimensions
   - Examples: revenue, quantity, cost, count
2. **Semi-Additive Measures**: Can be summed across some dimensions, not others
   - Examples: account_balance (sum across accounts, not across time)
3. **Non-Additive Measures**: Cannot be summed
   - Examples: ratios, percentages, averages (store as components, calculate on-the-fly)

### Measure Aggregation Rules
- **CRITICAL**: For each measure, identify appropriate aggregations:
  - SUM: For additive measures (revenue, quantity, cost)
  - AVG: For averages (average_price, average_rating)
  - MIN/MAX: For ranges (min_temperature, max_score)
  - COUNT/COUNT_DISTINCT: For counts (order_count, unique_customers)
  - PERCENTILE: For distributions (median, p95, p99)

## SAMPLE DATA ANALYSIS RULES

### **CRITICAL**: Analyze 100-200 Sample Rows Per Table
- **Cardinality Analysis**: Count distinct values for each column
  - High cardinality (>1000): Likely measure or key
  - Medium cardinality (10-1000): Likely dimension
  - Low cardinality (<10): Definitely dimension
- **Null Analysis**: Check null percentage
  - High null rate (>50%): May indicate optional dimension or data quality issue
  - Low null rate (<5%): Likely required dimension or measure
- **Value Distribution**: Analyze value patterns
  - Uniform distribution: Likely dimension
  - Skewed distribution: May indicate measure or categorical dimension
  - Constant values: May indicate deprecated column or default value
- **Data Type Validation**: Verify actual data matches declared type
  - String columns with numeric patterns: May need parsing
  - Numeric columns with text: Data quality issue
- **Pattern Detection**: Identify common patterns
  - UUIDs: 8-4-4-4-12 format
  - Dates: ISO 8601, Unix timestamp, custom formats
  - Codes: Alphanumeric patterns, prefixes/suffixes

### Sample Data Analysis Checklist
For each column in sample data:
1. Count distinct values (cardinality)
2. Count null values (completeness)
3. Identify min/max for numeric columns
4. Identify most common values (mode)
5. Check for patterns (format, structure)
6. Validate against declared data type
7. Detect outliers or anomalies

## RELATIONSHIP IDENTIFICATION RULES

### **CRITICAL**: Primary and Foreign Key Detection
- **Primary Keys**: Unique identifiers for each row
  - Usually: id, {table_name}_id, pk_{table_name}
  - May be composite (multiple columns)
- **Foreign Keys**: References to other tables
  - Pattern: {referenced_table}_id, fk_{referenced_table}
  - Creates relationships: ONE_TO_ONE, ONE_TO_MANY, MANY_TO_ONE, MANY_TO_MANY

### Relationship Types
1. **Fact-to-Dimension**: Fact table → Dimension table (most common)
   - Example: orders.customer_id → customers.id
2. **Dimension-to-Dimension**: Dimension table → Dimension table (hierarchies)
   - Example: cities.region_id → regions.id
3. **Fact-to-Fact**: Fact table → Fact table (rare, usually via bridge table)
   - Example: order_items.order_id → orders.id

### Join Condition Rules
- **CRITICAL**: Identify join columns from relationships
  - Use exact column names from schema
  - Match data types between join columns
  - Consider NULL handling (INNER vs LEFT JOIN)

## DATA QUALITY RULES

### **CRITICAL**: Data Quality Checks
- **Completeness**: Check for high null rates (>20% may indicate issue)
- **Consistency**: Check for inconsistent formats (dates, codes, names)
- **Validity**: Check for invalid values (negative quantities, future dates in past events)
- **Uniqueness**: Check for duplicate keys (violates primary key constraint)
- **Accuracy**: Check for outliers (unusually high/low values)

### Data Quality Recommendations
- Identify columns requiring cleaning/transformation
- Flag potential data quality issues
- Suggest standardization rules (case, format, encoding)
- Recommend validation rules for silver layer

## STAR SCHEMA CLASSIFICATION RULES

### **CRITICAL**: Table Type Classification
1. **Fact Tables**: Contain measures and foreign keys to dimensions
   - High row count (millions/billions)
   - Mostly numeric columns (measures)
   - Multiple foreign keys
   - Time dimension present
   - Examples: orders, transactions, events, sales

2. **Dimension Tables**: Contain descriptive attributes
   - Lower row count (thousands to millions)
   - Mostly string/categorical columns
   - Primary key present
   - Descriptive attributes
   - Examples: customers, products, regions, time

3. **Bridge Tables**: Resolve many-to-many relationships
   - Two or more foreign keys
   - May contain measures (quantities, weights)
   - Examples: order_items, product_categories

### **CRITICAL**: Grain Identification
- Identify the grain (level of detail) for each fact table
  - Example: "One row per order" vs "One row per order item"
  - Critical for correct aggregation
- Document the grain clearly in analysis

## TRANSFORMATION RECOMMENDATIONS

### Silver Layer Transformations
- **Data Cleaning**: Handle nulls, standardize formats, fix data types
- **Deduplication**: Identify duplicate rows, apply LOD logic
- **Conforming**: Standardize naming, apply business rules
- **Enrichment**: Add calculated columns, derive dimensions
- **Validation**: Add data quality checks, flag issues

### Dimension Conforming Rules
- Standardize dimension values (case, format, encoding)
- Create conformed dimensions (shared across facts)
- Handle slowly changing dimensions (SCD Type 1, 2, 3)
- Create dimension hierarchies

### Measure Conforming Rules
- Standardize units (currency, weight, distance)
- Handle currency conversion if needed
- Normalize measures to common scale if needed
- Calculate derived measures (profit, margin, growth)

## OUTPUT FORMAT REQUIREMENTS

### **CRITICAL**: Analysis Output Must Include
For each table:
1. **Table Classification**: Fact, Dimension, or Bridge
2. **Grain**: Level of detail (one row per what?)
3. **Dimensions**: List with cardinality, null rate, sample values
4. **Time Dimensions**: List with granularity, timezone, format
5. **Measures**: List with aggregation type, data type, null rate
6. **Relationships**: List with join type, join condition
7. **Data Quality Issues**: List of concerns and recommendations
8. **Transformation Recommendations**: Specific steps for silver layer

### Sample Data Summary
For each table, include:
- Total row count (from sample)
- Column statistics (cardinality, nulls, min/max for numeric)
- Sample values (top 5-10 most common)
- Data quality score (0-100)
"""


# ============================================================================
# STATE DEFINITIONS
# ============================================================================

class TableDDL(BaseModel):
    """Represents a table DDL with metadata"""
    table_name: str
    table_ddl: str
    relationships: List[Dict[str, Any]] = Field(default_factory=list)
    layer: str = "raw"  # raw, silver, or gold


class LODConfig(BaseModel):
    """Level of Detail configuration for deduplication"""
    table_name: str
    lod_type: str  # "FIXED", "INCLUDE", "EXCLUDE"
    dimensions: List[str]
    description: str = ""


class RelationshipMapping(BaseModel):
    """Parent-child relationship for silver/gold table building"""
    child_table: str
    parent_table: str
    join_type: str  # "ONE_TO_ONE", "ONE_TO_MANY", "MANY_TO_ONE"
    join_condition: str
    layer: str  # silver or gold


class CubeDefinition(BaseModel):
    """Cube.js cube definition"""
    name: str
    sql: str
    dimensions: List[Dict[str, Any]]
    measures: List[Dict[str, Any]]
    pre_aggregations: List[Dict[str, Any]] = Field(default_factory=list)
    joins: List[Dict[str, Any]] = Field(default_factory=list)
    description: str = ""
    layer: str = "raw"


class ViewDefinition(BaseModel):
    """Cube.js view definition"""
    name: str
    cubes: List[Dict[str, Any]]
    description: str = ""


class TransformationStep(BaseModel):
    """Data transformation step"""
    step_name: str
    step_type: str  # "clean", "transform", "aggregate", "deduplicate"
    sql_logic: str
    description: str
    input_tables: List[str]
    output_table: str
    layer: str


class ColumnMetadata(BaseModel):
    """Metadata for a single column"""
    name: str
    data_type: str
    description: Optional[str] = ""
    domain_description: Optional[str] = ""
    business_use_case: Optional[str] = ""
    statistics: Optional[Dict[str, Any]] = Field(default_factory=dict)
    sample_values: Optional[List[Any]] = Field(default_factory=list)


class TableMetadataSummary(BaseModel):
    """Comprehensive metadata summary for a table"""
    table_name: str
    description: Optional[str] = ""
    domain_description: Optional[str] = ""
    business_use_case: Optional[str] = ""
    columns: List[ColumnMetadata] = Field(default_factory=list)
    statistics: Dict[str, Any] = Field(default_factory=dict)
    relationships: List[Dict[str, Any]] = Field(default_factory=list)
    possible_joins: List[Dict[str, Any]] = Field(default_factory=list)
    usages: Dict[str, List[str]] = Field(default_factory=dict)  # SQLs, Joins, Cubes, Dashboards


class AgentState(TypedDict):
    """State maintained throughout the agent workflow"""
    # Input
    raw_ddls: List[TableDDL]
    user_query: str
    
    # Configuration
    lod_configs: List[LODConfig]
    relationship_mappings: List[RelationshipMapping]
    
    # Processing stages
    messages: Annotated[List[Any], operator.add]
    current_layer: str  # raw, silver, gold
    table_metadata: List[TableMetadataSummary]  # Enriched metadata from pandas DataFrames
    table_analysis_configs: List[Dict[str, Any]]  # Human-in-the-loop collected requirements
    
    # Generated artifacts
    raw_cubes: List[CubeDefinition]
    silver_cubes: List[CubeDefinition]
    gold_cubes: List[CubeDefinition]
    views: List[ViewDefinition]
    
    # Transformation workflows
    raw_to_silver_steps: List[TransformationStep]
    silver_to_gold_steps: List[TransformationStep]
    
    # Final output
    generation_complete: bool
    error: Optional[str]


# ============================================================================
# AGENT NODES
# ============================================================================

class CubeGenerationAgent:
    """Main orchestrator for Cube.js model generation"""
    
    def __init__(
        self, 
        model_name: str = "gpt-4o",
        table_dataframes: Optional[Dict[str, pd.DataFrame]] = None,
        db_connection: Optional[Any] = None,
        user_input_handler: Optional[Any] = None,
        llm: Optional[ChatOpenAI] = None
    ):
        # Use provided LLM or get from dependencies
        self.llm = llm or get_llm()
        self.table_dataframes = table_dataframes  # Dictionary mapping table names to DataFrames
        self.db_connection = db_connection  # For SQL statistics (legacy support)
        self.user_input_handler = user_input_handler  # For human-in-the-loop
        
        # Initialize human-in-the-loop agent (lazy import to avoid circular dependency)
        from app.agents.cubes.silver_human_in_loop import SilverHumanInLoopAgent
        self.human_in_loop_agent = SilverHumanInLoopAgent(
            llm=self.llm,
            user_input_handler=user_input_handler
        )
        
        # Build separate workflows
        self.silver_workflow = self._build_silver_workflow()
        self.gold_workflow = self._build_gold_workflow()
        # Keep full workflow for backward compatibility
        self.graph = self._build_full_workflow()
    
    def _build_silver_workflow(self) -> StateGraph:
        """Build the Silver table generator workflow"""
        workflow = StateGraph(AgentState)
        
        # Add nodes for silver workflow
        workflow.add_node("enrich_table_metadata", self.enrich_table_metadata)
        workflow.add_node("human_in_loop_collection", self.human_in_loop_collection)
        workflow.add_node("collect_requirements", self.collect_requirements)
        workflow.add_node("analyze_schema", self.analyze_schema)
        workflow.add_node("generate_raw_cubes", self.generate_raw_cubes)
        workflow.add_node("plan_silver_transformations", self.plan_silver_transformations)
        workflow.add_node("generate_silver_cubes", self.generate_silver_cubes)
        
        # Define edges for silver workflow
        workflow.set_entry_point("enrich_table_metadata")
        workflow.add_edge("enrich_table_metadata", "human_in_loop_collection")
        workflow.add_edge("human_in_loop_collection", "collect_requirements")
        workflow.add_edge("collect_requirements", "analyze_schema")
        workflow.add_edge("analyze_schema", "generate_raw_cubes")
        workflow.add_edge("generate_raw_cubes", "plan_silver_transformations")
        workflow.add_edge("plan_silver_transformations", "generate_silver_cubes")
        workflow.add_edge("generate_silver_cubes", END)
        
        return workflow.compile()
    
    def _build_gold_workflow(self) -> StateGraph:
        """Build the Gold table generator workflow"""
        workflow = StateGraph(AgentState)
        
        # Add nodes for gold workflow
        workflow.add_node("plan_gold_aggregations", self.plan_gold_aggregations)
        workflow.add_node("generate_gold_cubes", self.generate_gold_cubes)
        workflow.add_node("generate_views", self.generate_views)
        workflow.add_node("generate_pre_aggregations", self.generate_pre_aggregations)
        workflow.add_node("validate_output", self.validate_output)
        
        # Define edges for gold workflow
        workflow.set_entry_point("plan_gold_aggregations")
        workflow.add_edge("plan_gold_aggregations", "generate_gold_cubes")
        workflow.add_edge("generate_gold_cubes", "generate_views")
        workflow.add_edge("generate_views", "generate_pre_aggregations")
        workflow.add_edge("generate_pre_aggregations", "validate_output")
        workflow.add_edge("validate_output", END)
        
        return workflow.compile()
    
    def _build_full_workflow(self) -> StateGraph:
        """Build the complete workflow (silver + gold) for backward compatibility"""
        workflow = StateGraph(AgentState)
        
        # Add all nodes
        workflow.add_node("enrich_table_metadata", self.enrich_table_metadata)
        workflow.add_node("collect_requirements", self.collect_requirements)
        workflow.add_node("analyze_schema", self.analyze_schema)
        workflow.add_node("generate_raw_cubes", self.generate_raw_cubes)
        workflow.add_node("plan_silver_transformations", self.plan_silver_transformations)
        workflow.add_node("generate_silver_cubes", self.generate_silver_cubes)
        workflow.add_node("plan_gold_aggregations", self.plan_gold_aggregations)
        workflow.add_node("generate_gold_cubes", self.generate_gold_cubes)
        workflow.add_node("generate_views", self.generate_views)
        workflow.add_node("generate_pre_aggregations", self.generate_pre_aggregations)
        workflow.add_node("validate_output", self.validate_output)
        
        # Define edges
        workflow.set_entry_point("enrich_table_metadata")
        workflow.add_edge("enrich_table_metadata", "collect_requirements")
        workflow.add_edge("collect_requirements", "analyze_schema")
        workflow.add_edge("analyze_schema", "generate_raw_cubes")
        workflow.add_edge("generate_raw_cubes", "plan_silver_transformations")
        workflow.add_edge("plan_silver_transformations", "generate_silver_cubes")
        workflow.add_edge("generate_silver_cubes", "plan_gold_aggregations")
        workflow.add_edge("plan_gold_aggregations", "generate_gold_cubes")
        workflow.add_edge("generate_gold_cubes", "generate_views")
        workflow.add_edge("generate_views", "generate_pre_aggregations")
        workflow.add_edge("generate_pre_aggregations", "validate_output")
        workflow.add_edge("validate_output", END)
        
        return workflow.compile()
    
    # ========================================================================
    # NODE IMPLEMENTATIONS
    # ========================================================================
    
    def enrich_table_metadata(self, state: AgentState) -> AgentState:
        """
        Enrich table metadata by gathering statistics from pandas DataFrames.
        This is the first step in the workflow.
        Delegates to the metadata_enrichment module.
        """
        return enrich_metadata(
            state=state,
            table_dataframes=self.table_dataframes,
            db_connection=self.db_connection,
            llm=self.llm
        )
    
    def human_in_loop_collection(self, state: AgentState) -> AgentState:
        """
        Human-in-the-loop collection of requirements for each table.
        This step enriches the workflow with user input, domain knowledge, and business goals.
        
        Note: If enrichment has already been done (indicated by table_analysis_configs in state),
        this method will skip the enrichment to avoid duplicate processing.
        """
        # Check if enrichment has already been done
        if state.get("table_analysis_configs") and len(state.get("table_analysis_configs", [])) > 0:
            logger.info("Human-in-the-loop enrichment already completed, skipping duplicate call")
            state["messages"].append(
                AIMessage(content="Human-in-the-loop enrichment already completed, skipping duplicate processing.")
            )
            return state
        
        # Use async function to collect requirements (handle async in sync context)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, use nest_asyncio
                try:
                    import nest_asyncio
                    nest_asyncio.apply()
                    from app.agents.cubes.silver_human_in_loop import enrich_silver_workflow_with_human_in_loop
                    return asyncio.run(enrich_silver_workflow_with_human_in_loop(
                        state=state,
                        human_in_loop_agent=self.human_in_loop_agent
                    ))
                except:
                    # Fallback: return state without enrichment
                    return state
            else:
                from app.agents.cubes.silver_human_in_loop import enrich_silver_workflow_with_human_in_loop
                return asyncio.run(enrich_silver_workflow_with_human_in_loop(
                    state=state,
                    human_in_loop_agent=self.human_in_loop_agent
                ))
        except RuntimeError:
            # No event loop, create new one
            from app.agents.cubes.silver_human_in_loop import enrich_silver_workflow_with_human_in_loop
            return asyncio.run(enrich_silver_workflow_with_human_in_loop(
                state=state,
                human_in_loop_agent=self.human_in_loop_agent
            ))
    
    def collect_requirements(self, state: AgentState) -> AgentState:
        """
        Collect LOD configurations and relationship mappings from user.
        This node prompts the user to define deduplication logic and table relationships.
        """
        system_prompt = """You are a data modeling expert. Help the user define:
        1. Level of Detail (LOD) configurations for deduplication
        2. Parent-child relationships between tables for silver/gold layers
        
        Ask clarifying questions to understand their business requirements."""
        
        # Check if configurations already exist
        if state.get("lod_configs") and state.get("relationship_mappings"):
            state["messages"].append(
                AIMessage(content="Using existing LOD and relationship configurations.")
            )
            return state
        
        # Analyze available tables
        table_names = [ddl.table_name for ddl in state["raw_ddls"]]
        
        prompt = f"""Based on the user query: "{state['user_query']}"
        
Available tables: {', '.join(table_names)}

Please define:
1. **LOD Configurations** - Which dimensions should be used for deduplication at each layer?
2. **Relationship Mappings** - How should tables be joined to create silver and gold layers?

Provide your response in a structured format."""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        response = self.llm.invoke(messages)
        log_llm_call("Requirements Collection", messages, response)
        
        state["messages"].append(response)
        
        # In a real implementation, this would interactively collect user input
        # For now, we'll add default configurations
        state["lod_configs"] = state.get("lod_configs", [])
        state["relationship_mappings"] = state.get("relationship_mappings", [])
        
        return state
    
    def analyze_schema(self, state: AgentState) -> AgentState:
        """
        Analyze the raw DDLs to understand:
        - Data types and constraints
        - Existing relationships
        - Potential dimensions and measures
        - Data quality issues
        - Sample data analysis (100-200 rows per table)
        """
        system_prompt = f"""You are a database schema analyst specializing in Star Schema Data Modeling. 
Analyze the provided DDLs and sample data following these comprehensive rules:

{SCHEMA_ANALYSIS_RULES}

Your analysis must:
1. Classify each table as Fact, Dimension, or Bridge
2. Identify all dimensions with cardinality, null rates, and sample values
3. Identify all time dimensions with granularity, timezone, and format
4. Identify all measures with aggregation types and data types
5. Detect primary keys, foreign keys, and relationships
6. Analyze sample data (100-200 rows) to validate classifications
7. Identify data quality issues and recommend transformations
8. Provide specific recommendations for silver layer transformations"""
        
        ddl_summaries = []
        for ddl in state["raw_ddls"]:
            ddl_summaries.append(f"Table: {ddl.table_name}\n{ddl.table_ddl}\nRelationships: {json.dumps(ddl.relationships, indent=2)}")
        
        prompt = f"""Analyze these database schemas using Star Schema Data Modeling principles:

{chr(10).join(ddl_summaries)}

**IMPORTANT**: For each table, assume you have access to 100-200 sample rows. Use this sample data to:
- Calculate cardinality (distinct value counts) for each column
- Identify null rates and completeness
- Detect value patterns and distributions
- Validate data types against actual values
- Identify outliers and anomalies

Provide a comprehensive analysis following the Star Schema rules, including:

**For each table:**
1. **Table Classification**: Fact, Dimension, or Bridge table
2. **Grain**: Level of detail (e.g., "One row per order", "One row per customer")
3. **Dimensions**: 
   - List each dimension column
   - Cardinality (from sample data analysis)
   - Null rate percentage
   - Top 5-10 sample values
   - Dimension type (categorical, boolean, foreign key, etc.)
4. **Time Dimensions**:
   - List each time dimension column
   - Granularity (Year, Quarter, Month, Week, Day, Hour, etc.)
   - Timezone information
   - Format (ISO 8601, Unix timestamp, etc.)
   - Primary time dimension for fact tables
   - Time range pairs (start_date + end_date) if applicable
5. **Measures**:
   - List each measure column
   - Aggregation type (SUM, AVG, MIN, MAX, COUNT, COUNT_DISTINCT)
   - Measure type (Additive, Semi-Additive, Non-Additive)
   - Data type and null rate
   - Min/max values from sample data
6. **Relationships**:
   - Primary keys identified
   - Foreign keys and their referenced tables
   - Join types (ONE_TO_ONE, ONE_TO_MANY, MANY_TO_ONE, MANY_TO_MANY)
   - Join conditions
7. **Data Quality Issues**:
   - Completeness issues (high null rates)
   - Consistency issues (format inconsistencies)
   - Validity issues (invalid values, outliers)
   - Uniqueness issues (duplicate keys)
   - Accuracy concerns
8. **Transformation Recommendations**:
   - Specific cleaning steps needed
   - Deduplication logic
   - Standardization requirements
   - Calculated columns to add
   - Data quality validations

**Sample Data Analysis Summary**:
For each table, provide:
- Total row count analyzed (100-200 rows)
- Column-level statistics (cardinality, nulls, min/max for numeric)
- Most common values per column
- Data quality score (0-100) with justification

Format your response as structured JSON or markdown for easy parsing."""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        response = self.llm.invoke(messages)
        log_llm_call("Schema Analysis", messages, response, max_response_length=1000)
        
        state["messages"].append(response)
        state["current_layer"] = "raw"
        
        return state
    
    def generate_raw_cubes(self, state: AgentState) -> AgentState:
        """
        Generate Cube.js definitions for raw layer.
        Raw layer = minimal transformations, mostly pass-through with type casting.
        """
        system_prompt = """You are a Cube.js expert. Generate cube definitions for the RAW layer.

RAW Layer Principles:
- Minimal transformations
- Preserve all source columns
- Basic type casting where needed
- Simple dimensions and measures
- No complex joins or aggregations yet

Output Format: Valid Cube.js JSON cube definitions."""
        
        raw_cubes = []
        
        for ddl in state["raw_ddls"]:
            prompt = f"""Generate a Cube.js cube definition for RAW layer:

Table: {ddl.table_name}
DDL: {ddl.table_ddl}

Requirements:
1. Extract all dimensions (non-numeric, categorical, temporal)
2. Extract all measures (numeric, aggregatable)
3. Define proper SQL for the cube
4. Include descriptions from DDL comments
5. Use Cube.js best practices

Output as JSON matching this structure:
{{
  "cube": "{{name}}",
  "sql": "SELECT * FROM {{table_name}}",
  "dimensions": [...],
  "measures": [...]
}}"""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ]
            response = self.llm.invoke(messages)
            log_llm_call(f"Raw Cube Generation ({ddl.table_name})", messages, response, max_response_length=1000)
            
            # Parse the response and create CubeDefinition
            # In production, use proper JSON parsing
            cube_def = CubeDefinition(
                name=f"raw_{ddl.table_name}",
                sql=f"SELECT * FROM {ddl.table_name}",
                dimensions=[],
                measures=[],
                layer="raw",
                description=f"Raw layer cube for {ddl.table_name}"
            )
            
            raw_cubes.append(cube_def)
            state["messages"].append(response)
        
        state["raw_cubes"] = raw_cubes
        return state
    
    def plan_silver_transformations(self, state: AgentState) -> AgentState:
        """
        Plan transformation steps from raw to silver layer.
        Silver layer = cleaned, deduplicated, conformed data.
        """
        system_prompt = """You are a data engineering expert. Plan transformation steps for the SILVER layer.

SILVER Layer Transformations:
1. Data Cleaning: Handle nulls, fix data types, standardize formats
2. Deduplication: Apply LOD-based deduplication logic
3. Conforming: Standardize naming, apply business rules
4. Joining: Create denormalized views using relationship mappings
5. Validation: Add data quality checks

For each transformation, specify:
- SQL logic
- Input tables
- Output table
- Business rationale"""
        
        # Get LOD configs and relationships
        lod_configs = state.get("lod_configs", [])
        relationships = state.get("relationship_mappings", [])
        
        prompt = f"""Plan silver layer transformations:

Raw Tables: {[cube.name for cube in state['raw_cubes']]}
LOD Configurations: {json.dumps([lod.dict() for lod in lod_configs], indent=2)}
Relationships: {json.dumps([rel.dict() for rel in relationships], indent=2)}

Create transformation steps covering:
1. Cleaning transformations
2. Deduplication using LOD
3. Joining related tables
4. Business logic applications

Output as structured JSON array of transformation steps."""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        response = self.llm.invoke(messages)
        log_llm_call("Silver Transformation Planning", messages, response, max_response_length=1000)
        
        # Parse transformation steps
        # In production, properly parse the JSON response
        transformation_steps = []
        
        state["raw_to_silver_steps"] = transformation_steps
        state["messages"].append(response)
        state["current_layer"] = "silver"
        
        return state
    
    def generate_silver_cubes(self, state: AgentState) -> AgentState:
        """
        Generate Cube.js definitions for silver layer.
        Silver layer = cleaned, conformed, business-ready data.
        """
        system_prompt = """You are a Cube.js expert. Generate cube definitions for the SILVER layer.

SILVER Layer Principles:
- Cleaned and validated data
- Deduplicated using LOD logic
- Conformed dimensions
- Business-friendly naming
- Relationships defined through joins
- Ready for analysis

Include proper join definitions using the relationship mappings."""
        
        silver_cubes = []
        relationships = state.get("relationship_mappings", [])
        
        for step in state.get("raw_to_silver_steps", []):
            prompt = f"""Generate a Cube.js cube definition for SILVER layer:

Transformation: {step.step_name}
Description: {step.description}
SQL Logic: {step.sql_logic}
Output Table: {step.output_table}

Available Relationships: {json.dumps([r.dict() for r in relationships if r.layer == 'silver'], indent=2)}

Requirements:
1. Use transformed/cleaned data
2. Include all relevant dimensions and measures
3. Define joins based on relationships
4. Add calculated fields where appropriate
5. Include proper aggregations

Output as valid Cube.js JSON."""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ]
            response = self.llm.invoke(messages)
            log_llm_call(f"Silver Cube Generation ({step.output_table})", messages, response, max_response_length=1000)
            
            # Create cube definition
            cube_def = CubeDefinition(
                name=f"silver_{step.output_table}",
                sql=step.sql_logic,
                dimensions=[],
                measures=[],
                joins=[],
                layer="silver",
                description=step.description
            )
            
            silver_cubes.append(cube_def)
            state["messages"].append(response)
        
        state["silver_cubes"] = silver_cubes
        return state
    
    def plan_gold_aggregations(self, state: AgentState) -> AgentState:
        """
        Plan aggregation steps from silver to gold layer.
        Gold layer = business-level aggregations and metrics.
        """
        system_prompt = """You are a business intelligence expert. Plan aggregations for the GOLD layer.

GOLD Layer Aggregations:
1. Business Metrics: KPIs, trends, ratios
2. Time-based Rollups: Daily, weekly, monthly aggregations
3. Dimensional Aggregations: By region, product, customer segment
4. Composite Metrics: Derived business calculations

For each aggregation:
- Define the business metric
- Specify aggregation logic
- Identify grain/level of detail
- Note any special calculations"""
        
        silver_cubes = state.get("silver_cubes", [])
        
        prompt = f"""Plan gold layer aggregations:

Silver Cubes: {[cube.name for cube in silver_cubes]}
User Query Context: {state['user_query']}

Create aggregation steps for business metrics that would answer the user's needs.
Consider:
1. Time-based rollups
2. Dimensional aggregations
3. Calculated metrics
4. Business KPIs

Output as structured JSON array of transformation steps."""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        response = self.llm.invoke(messages)
        log_llm_call("Gold Transformation Planning", messages, response, max_response_length=1000)
        
        # Parse aggregation steps
        aggregation_steps = []
        
        state["silver_to_gold_steps"] = aggregation_steps
        state["messages"].append(response)
        state["current_layer"] = "gold"
        
        return state
    
    def generate_gold_cubes(self, state: AgentState) -> AgentState:
        """
        Generate Cube.js definitions for gold layer.
        Gold layer = business metrics and aggregated views.
        """
        system_prompt = """You are a Cube.js expert. Generate cube definitions for the GOLD layer.

GOLD Layer Principles:
- Business-level aggregations
- Pre-calculated metrics
- Optimized for reporting/dashboards
- Minimal real-time computation
- May include rollup tables

Focus on performance and business value."""
        
        gold_cubes = []
        
        for step in state.get("silver_to_gold_steps", []):
            prompt = f"""Generate a Cube.js cube definition for GOLD layer:

Aggregation: {step.step_name}
Description: {step.description}
SQL Logic: {step.sql_logic}
Output Table: {step.output_table}

Requirements:
1. Define business-friendly metrics
2. Include time dimensions for trending
3. Add calculated measures
4. Optimize for query performance
5. Consider pre-aggregations

Output as valid Cube.js JSON."""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ]
            response = self.llm.invoke(messages)
            log_llm_call(f"Gold Cube Generation ({step.output_table})", messages, response, max_response_length=1000)
            
            # Create cube definition
            cube_def = CubeDefinition(
                name=f"gold_{step.output_table}",
                sql=step.sql_logic,
                dimensions=[],
                measures=[],
                layer="gold",
                description=step.description
            )
            
            gold_cubes.append(cube_def)
            state["messages"].append(response)
        
        state["gold_cubes"] = gold_cubes
        return state
    
    def generate_views(self, state: AgentState) -> AgentState:
        """
        Generate Cube.js view definitions that combine multiple cubes.
        Views provide simplified access to complex data models.
        """
        system_prompt = """You are a Cube.js expert. Generate view definitions.

Views in Cube.js:
- Combine multiple cubes
- Simplify complex models
- Provide business-friendly interfaces
- Enable cross-cube analysis

Best Practices:
- Group related cubes
- Hide implementation complexity
- Use clear naming conventions
- Document business purpose"""
        
        all_cubes = state["raw_cubes"] + state["silver_cubes"] + state["gold_cubes"]
        
        prompt = f"""Generate Cube.js views:

Available Cubes:
{chr(10).join([f"- {cube.name} ({cube.layer}): {cube.description}" for cube in all_cubes])}

User Query: {state['user_query']}

Create views that:
1. Group related cubes logically
2. Provide simplified access patterns
3. Support the user's analytical needs
4. Follow naming conventions

Output as valid Cube.js view JSON definitions."""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        response = self.llm.invoke(messages)
        log_llm_call("View Generation", messages, response, max_response_length=1000)
        
        # Parse view definitions
        views = []
        
        state["views"] = views
        state["messages"].append(response)
        
        return state
    
    def generate_pre_aggregations(self, state: AgentState) -> AgentState:
        """
        Generate pre-aggregation definitions for performance optimization.
        Pre-aggregations are materialized rollups for faster queries.
        """
        system_prompt = """You are a Cube.js performance expert. Generate pre-aggregation definitions.

Pre-aggregations:
- Materialized rollup tables
- Speed up common queries
- Balance storage vs. compute
- Consider refresh frequency

Types:
1. rollup: Aggregate measures
2. originalSql: Cache full results
3. rollupJoin: Pre-join tables
4. rollupLambda: Serverless rollups

Focus on the most impactful aggregations based on likely query patterns."""
        
        all_cubes = state["silver_cubes"] + state["gold_cubes"]
        
        for cube in all_cubes:
            prompt = f"""Generate pre-aggregations for cube: {cube.name}

Cube Description: {cube.description}
Layer: {cube.layer}

Dimensions: {json.dumps([d.get('name') for d in cube.dimensions], indent=2)}
Measures: {json.dumps([m.get('name') for m in cube.measures], indent=2)}

Consider:
1. Common query patterns
2. Time-based rollups
3. Frequently accessed dimension combinations
4. Query performance bottlenecks

Output as pre-aggregation definitions array."""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ]
            response = self.llm.invoke(messages)
            cube_name = cube.get("name", "unknown")
            log_llm_call(f"Pre-aggregation Planning ({cube_name})", messages, response, max_response_length=1000)
            
            state["messages"].append(response)
        
        return state
    
    def validate_output(self, state: AgentState) -> AgentState:
        """
        Validate all generated artifacts for correctness and completeness.
        """
        system_prompt = """You are a data quality validator. Check the generated Cube.js models for:
        1. Valid JSON syntax
        2. Complete dimension and measure definitions
        3. Proper relationship mappings
        4. Logical data flow (raw → silver → gold)
        5. Business logic correctness
        6. Performance considerations"""
        
        validation_summary = f"""Validation Summary:
- Raw Cubes: {len(state.get('raw_cubes', []))}
- Silver Cubes: {len(state.get('silver_cubes', []))}
- Gold Cubes: {len(state.get('gold_cubes', []))}
- Views: {len(state.get('views', []))}
- Raw→Silver Steps: {len(state.get('raw_to_silver_steps', []))}
- Silver→Gold Steps: {len(state.get('silver_to_gold_steps', []))}"""
        
        prompt = f"""{validation_summary}

Perform validation and provide:
1. Any errors or warnings
2. Recommendations for improvement
3. Missing elements
4. Overall quality assessment"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        response = self.llm.invoke(messages)
        log_llm_call("Quality Assessment", messages, response, max_response_length=1000)
        
        state["messages"].append(response)
        state["generation_complete"] = True
        
        return state
    
    # ========================================================================
    # PUBLIC INTERFACE
    # ========================================================================
    
    def _create_initial_state(
        self,
        raw_ddls: List[TableDDL],
        user_query: str,
        lod_configs: Optional[List[LODConfig]] = None,
        relationship_mappings: Optional[List[RelationshipMapping]] = None
    ) -> AgentState:
        """Create initial state for workflows"""
        return {
            "raw_ddls": raw_ddls,
            "user_query": user_query,
            "lod_configs": lod_configs or [],
            "relationship_mappings": relationship_mappings or [],
            "messages": [],
            "current_layer": "raw",
            "table_metadata": [],
            "table_analysis_configs": [],
            "raw_cubes": [],
            "silver_cubes": [],
            "gold_cubes": [],
            "views": [],
            "raw_to_silver_steps": [],
            "silver_to_gold_steps": [],
            "generation_complete": False,
            "error": None
        }
    
    def generate_silver(
        self,
        raw_ddls: List[TableDDL],
        user_query: str,
        lod_configs: Optional[List[LODConfig]] = None,
        relationship_mappings: Optional[List[RelationshipMapping]] = None
    ) -> Dict[str, Any]:
        """
        Generate Silver layer cubes only.
        
        Args:
            raw_ddls: List of table DDLs to process
            user_query: User's analytical question or requirement
            lod_configs: Optional LOD configurations for deduplication
            relationship_mappings: Optional parent-child relationships
            
        Returns:
            Dictionary containing silver layer artifacts
        """
        initial_state = self._create_initial_state(
            raw_ddls=raw_ddls,
            user_query=user_query,
            lod_configs=lod_configs,
            relationship_mappings=relationship_mappings
        )
        
        # Execute silver workflow
        final_state = self.silver_workflow.invoke(initial_state)
        
        return {
            "table_metadata": [meta.dict() for meta in final_state.get("table_metadata", [])],
            "raw_cubes": [cube.dict() for cube in final_state["raw_cubes"]],
            "silver_cubes": [cube.dict() for cube in final_state["silver_cubes"]],
            "raw_to_silver_transformations": [step.dict() for step in final_state["raw_to_silver_steps"]],
            "messages": final_state["messages"],
            "state": final_state  # Return state for potential gold workflow continuation
        }
    
    def generate_gold(
        self,
        state: Optional[AgentState] = None,
        silver_cubes: Optional[List[CubeDefinition]] = None,
        user_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate Gold layer cubes from Silver layer.
        
        Args:
            state: Optional state from silver workflow (if continuing from silver)
            silver_cubes: Optional list of silver cubes (if starting fresh)
            user_query: Optional user query (required if state not provided)
            
        Returns:
            Dictionary containing gold layer artifacts
        """
        if state:
            # Use provided state (continuing from silver workflow)
            initial_state = state
        elif silver_cubes:
            # Create minimal state from silver cubes
            initial_state = self._create_initial_state(
                raw_ddls=[],
                user_query=user_query or "Generate gold layer aggregations",
                lod_configs=[],
                relationship_mappings=[]
            )
            initial_state["silver_cubes"] = silver_cubes
        else:
            raise ValueError("Either 'state' or 'silver_cubes' must be provided")
        
        # Execute gold workflow
        final_state = self.gold_workflow.invoke(initial_state)
        
        return {
            "gold_cubes": [cube.dict() for cube in final_state["gold_cubes"]],
            "views": [view.dict() for view in final_state["views"]],
            "silver_to_gold_transformations": [step.dict() for step in final_state["silver_to_gold_steps"]],
            "messages": final_state["messages"],
            "generation_complete": final_state["generation_complete"]
        }
    
    def generate(
        self,
        raw_ddls: List[TableDDL],
        user_query: str,
        lod_configs: Optional[List[LODConfig]] = None,
        relationship_mappings: Optional[List[RelationshipMapping]] = None
    ) -> Dict[str, Any]:
        """
        Main entry point for complete cube generation (silver + gold).
        This method runs both workflows sequentially.
        
        Args:
            raw_ddls: List of table DDLs to process
            user_query: User's analytical question or requirement
            lod_configs: Optional LOD configurations for deduplication
            relationship_mappings: Optional parent-child relationships
            
        Returns:
            Dictionary containing all generated artifacts
        """
        # First generate silver
        silver_result = self.generate_silver(
            raw_ddls=raw_ddls,
            user_query=user_query,
            lod_configs=lod_configs,
            relationship_mappings=relationship_mappings
        )
        
        # Then generate gold from silver state
        gold_result = self.generate_gold(state=silver_result["state"])
        
        # Combine results
        return {
            "table_metadata": silver_result["table_metadata"],
            "raw_cubes": silver_result["raw_cubes"],
            "silver_cubes": silver_result["silver_cubes"],
            "gold_cubes": gold_result["gold_cubes"],
            "views": gold_result["views"],
            "raw_to_silver_transformations": silver_result["raw_to_silver_transformations"],
            "silver_to_gold_transformations": gold_result["silver_to_gold_transformations"],
            "messages": silver_result["messages"] + gold_result["messages"],
            "generation_complete": gold_result["generation_complete"]
        }


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Example: Load DDL from the provided network devices table
    example_ddl = TableDDL(
        table_name="dev_network_devices",
        table_ddl="""-- Network device inventory and management system
CREATE TABLE dev_network_devices (
  id BIGINT NOT NULL,
  ip VARCHAR,
  subnet VARCHAR,
  site VARCHAR,
  mac VARCHAR,
  manufacturer VARCHAR,
  updated_at TIMESTAMP,
  is_stale BOOLEAN NOT NULL,
  is_cloud_device BOOLEAN,
  is_virtual_machine BOOLEAN,
  days_since_last_seen INTEGER
);""",
        relationships=[],
        layer="raw"
    )
    
    # Example LOD configuration
    lod_config = LODConfig(
        table_name="dev_network_devices",
        lod_type="FIXED",
        dimensions=["ip", "mac"],
        description="Deduplicate devices by IP and MAC address"
    )
    
    # Initialize agent
    agent = CubeGenerationAgent()
    
    # Option 1: Generate only Silver layer
    print("=== Generating Silver Layer ===")
    silver_result = agent.generate_silver(
        raw_ddls=[example_ddl],
        user_query="Create analytics dashboard for network device monitoring",
        lod_configs=[lod_config],
        relationship_mappings=[]
    )
    print(f"Generated {len(silver_result['silver_cubes'])} silver cubes")
    
    # Option 2: Generate Gold layer from Silver (continuing workflow)
    print("\n=== Generating Gold Layer from Silver ===")
    gold_result = agent.generate_gold(state=silver_result["state"])
    print(f"Generated {len(gold_result['gold_cubes'])} gold cubes")
    
    # Option 3: Generate complete workflow (Silver + Gold) - backward compatible
    print("\n=== Generating Complete Workflow ===")
    complete_result = agent.generate(
        raw_ddls=[example_ddl],
        user_query="Create analytics dashboard for network device monitoring",
        lod_configs=[lod_config],
        relationship_mappings=[]
    )
    print(f"Complete: {len(complete_result['silver_cubes'])} silver + {len(complete_result['gold_cubes'])} gold cubes")
    
    print(json.dumps(complete_result, indent=2))

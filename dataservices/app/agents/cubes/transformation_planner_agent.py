"""
Transformation Planner Agent
Plans and generates SQL transformations for medallion architecture layers
"""

from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from enum import Enum
import logging
import json
from app.core.dependencies import get_llm
from app.agents.cubes.sql_generator_agent import SQLGeneratorAgent, SQLType, SQLDialect

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


class TransformationType(str, Enum):
    """Types of transformations"""
    CLEANING = "cleaning"
    DEDUPLICATION = "deduplication"
    TYPE_CASTING = "type_casting"
    STANDARDIZATION = "standardization"
    ENRICHMENT = "enrichment"
    AGGREGATION = "aggregation"
    JOIN = "join"
    CALCULATION = "calculation"
    METRIC = "metric"  # Metric calculation transformation


class TransformationStep(BaseModel):
    """A single transformation step"""
    step_id: str
    step_name: str
    transformation_type: TransformationType
    input_tables: List[str]
    output_table: str
    sql_logic: str
    description: str
    dependencies: List[str] = Field(default_factory=list)
    business_rules: List[str] = Field(default_factory=list)
    data_quality_checks: List[str] = Field(default_factory=list)


class LODDeduplication(BaseModel):
    """Level of Detail deduplication configuration"""
    lod_type: str  # FIXED, INCLUDE, EXCLUDE
    dimensions: List[str]
    tie_breaker: str
    tie_breaker_order: str = "DESC"


class MetricConfig(BaseModel):
    """Configuration for a metric to be created in gold layer"""
    metric_name: str
    metric_type: str  # count, sum, avg, ratio, percentage, growth_rate, trend, etc.
    description: str
    formula: str  # SQL expression or formula description
    source_tables: List[str] = Field(default_factory=list)
    dimensions: List[str] = Field(default_factory=list)  # Dimensions to group by
    time_granularity: Optional[str] = None  # day, week, month, quarter, year
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)  # Optional filters
    business_rules: List[str] = Field(default_factory=list)
    target_mart: Optional[str] = None  # Target data mart name


class TransformationPlan(BaseModel):
    """Complete transformation plan for a layer"""
    source_layer: str
    target_layer: str
    steps: List[TransformationStep]
    execution_order: List[str]  # Step IDs in order
    estimated_complexity: str


class TransformationPlannerAgent:
    """Plans transformations between medallion architecture layers"""
    
    def __init__(
        self,
        model_name: str = "gpt-4o-mini",
        sql_generator: Optional[SQLGeneratorAgent] = None
    ):
        self.llm = get_llm()
        self.parser = JsonOutputParser()
        self.sql_generator = sql_generator or SQLGeneratorAgent(llm=self.llm, model_name=model_name)
    
    def plan_raw_to_silver(
        self,
        table_name: str,
        schema_analysis: Dict[str, Any],
        lod_config: Optional[LODDeduplication] = None
    ) -> List[TransformationStep]:
        """
        Plan transformations from RAW to SILVER layer.
        
        Silver Layer Goals:
        - Data cleaning and validation
        - Type casting and standardization
        - Deduplication using LOD
        - Handle nulls and missing values
        - Apply business rules
        - Create conformed dimensions
        
        Args:
            table_name: Name of the table
            schema_analysis: Analysis from SchemaAnalysisAgent
            lod_config: Optional LOD deduplication configuration
            
        Returns:
            List of transformation steps
        """
        system_prompt = """You are a data engineering expert specializing in data quality and the medallion architecture.

Plan SILVER layer transformations following these principles:

**Silver Layer Goals:**
1. **Data Cleaning**: Remove/fix invalid values, handle nulls
2. **Type Casting**: Ensure correct data types
3. **Standardization**: Consistent formatting (dates, strings, etc.)
4. **Deduplication**: Use LOD (Level of Detail) approach
5. **Validation**: Apply business rules and constraints
6. **Conforming**: Create standardized dimensions

**Transformation Patterns:**
- Clean nulls: `COALESCE(column, default_value)`
- Standardize strings: `TRIM(UPPER(column))`
- Parse dates: `CAST(column AS TIMESTAMP)`
- Deduplicate: `ROW_NUMBER() OVER (PARTITION BY lod_dimensions ORDER BY tie_breaker DESC) = 1`
- Handle boolean: `CASE WHEN column IS NULL THEN FALSE ELSE column END`

Generate SQL that is:
- Readable and well-commented
- Efficient (minimize operations)
- Idempotent (can run multiple times safely)
- Testable (clear logic)"""
        
        lod_info = ""
        if lod_config:
            lod_info = f"""
**LOD Configuration:**
- Type: {lod_config.lod_type}
- Dimensions: {', '.join(lod_config.dimensions)}
- Tie Breaker: {lod_config.tie_breaker} {lod_config.tie_breaker_order}
"""
        
        user_prompt = f"""Plan SILVER transformations for: {table_name}

**Schema Analysis:**
```json
{schema_analysis}
```
{lod_info}

Generate transformation steps covering:
1. **Cleaning Step**: Handle nulls, invalid values
2. **Type Casting Step**: Ensure proper data types
3. **Standardization Step**: Format consistency
4. **Deduplication Step**: Apply LOD logic (if configured)
5. **Validation Step**: Business rule checks

For each step, provide:
- Step name and type
- Complete SQL logic (CREATE TABLE AS SELECT ...)
- Description of what it does
- Data quality checks to run after

Return as JSON array of transformation steps."""
        
        response = self.llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        
        try:
            steps_data = self.parser.parse(response.content)
            if isinstance(steps_data, dict) and "steps" in steps_data:
                steps_data = steps_data["steps"]
            return [TransformationStep(**step) for step in steps_data]
        except Exception as e:
            # Return basic transformation steps as fallback
            return self._create_basic_silver_steps(table_name, schema_analysis, lod_config)
    
    def _create_basic_silver_steps(
        self,
        table_name: str,
        schema_analysis: Dict[str, Any],
        lod_config: Optional[LODDeduplication]
    ) -> List[TransformationStep]:
        """Create basic silver transformation steps as fallback"""
        
        steps = []
        
        # Step 1: Cleaning
        cleaning_sql = f"""
CREATE TABLE silver_{table_name}_cleaned AS
SELECT 
    *,
    CASE 
        WHEN id IS NULL THEN FALSE 
        ELSE TRUE 
    END AS is_valid_record
FROM raw_{table_name}
WHERE id IS NOT NULL;
"""
        
        steps.append(TransformationStep(
            step_id="clean_001",
            step_name=f"Clean {table_name}",
            transformation_type=TransformationType.CLEANING,
            input_tables=[f"raw_{table_name}"],
            output_table=f"silver_{table_name}_cleaned",
            sql_logic=cleaning_sql,
            description="Remove invalid records and handle nulls",
            data_quality_checks=["Check for null IDs", "Validate record count"]
        ))
        
        # Step 2: Deduplication (if LOD configured)
        if lod_config:
            lod_dims = ", ".join(lod_config.dimensions)
            dedup_sql = f"""
CREATE TABLE silver_{table_name}_deduped AS
SELECT *
FROM (
    SELECT 
        *,
        ROW_NUMBER() OVER (
            PARTITION BY {lod_dims}
            ORDER BY {lod_config.tie_breaker} {lod_config.tie_breaker_order}
        ) as row_num
    FROM silver_{table_name}_cleaned
) ranked
WHERE row_num = 1;
"""
            
            steps.append(TransformationStep(
                step_id="dedup_001",
                step_name=f"Deduplicate {table_name}",
                transformation_type=TransformationType.DEDUPLICATION,
                input_tables=[f"silver_{table_name}_cleaned"],
                output_table=f"silver_{table_name}_deduped",
                sql_logic=dedup_sql,
                description=f"Deduplicate using LOD dimensions: {lod_dims}",
                dependencies=["clean_001"],
                data_quality_checks=["Verify uniqueness on LOD dimensions"]
            ))
        
        return steps
    
    def plan_silver_to_gold(
        self,
        table_name: str,
        schema_analysis: Dict[str, Any],
        aggregation_requirements: Dict[str, Any]
    ) -> List[TransformationStep]:
        """
        Plan transformations from SILVER to GOLD layer.
        
        Gold Layer Goals:
        - Business-level aggregations
        - Pre-calculated metrics
        - Time-based rollups
        - Dimensional aggregations
        - Optimized for reporting
        
        Args:
            table_name: Name of the table
            schema_analysis: Analysis from SchemaAnalysisAgent
            aggregation_requirements: User requirements for aggregations
            
        Returns:
            List of transformation steps
        """
        system_prompt = """You are a business intelligence expert specializing in data aggregation and the medallion architecture.

Plan GOLD layer transformations following these principles:

**Gold Layer Goals:**
1. **Business Metrics**: Calculate KPIs and business measures
2. **Time Rollups**: Daily, weekly, monthly aggregations
3. **Dimensional Aggregations**: By region, product, customer, etc.
4. **Derived Metrics**: Ratios, percentages, growth rates
5. **Performance**: Pre-aggregate for fast queries

**Aggregation Patterns:**
- Time-based: `GROUP BY DATE_TRUNC('day', timestamp_column)`
- Dimensional: `GROUP BY dimension1, dimension2`
- Metrics: `SUM(amount), AVG(value), COUNT(DISTINCT id)`
- Running totals: `SUM(amount) OVER (ORDER BY date)`
- Period-over-period: `LAG(metric) OVER (PARTITION BY dimension ORDER BY date)`

Generate SQL that:
- Creates materialized aggregate tables
- Includes useful business metrics
- Optimizes for query performance
- Maintains grain documentation"""
        
        user_prompt = f"""Plan GOLD aggregations for: {table_name}

**Schema Analysis:**
```json
{schema_analysis}
```

**Aggregation Requirements:**
```json
{aggregation_requirements}
```

Generate aggregation steps for:
1. **Time-based rollups**: Daily, weekly, monthly summaries
2. **Dimensional aggregations**: Group by key dimensions
3. **Business metrics**: KPIs and calculated measures
4. **Trend analysis**: Period-over-period comparisons

For each step, provide:
- Aggregation name and type
- Complete SQL with GROUP BY and aggregations
- Description of business value
- Grain of the result

Return as JSON array of transformation steps."""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        response = self.llm.invoke(messages)
        log_llm_call(f"Silver to Gold Transformation Planning ({table_name})", messages, response, max_response_length=1000)
        
        try:
            steps_data = self.parser.parse(response.content)
            if isinstance(steps_data, dict) and "steps" in steps_data:
                steps_data = steps_data["steps"]
            return [TransformationStep(**step) for step in steps_data]
        except Exception as e:
            return self._create_basic_gold_steps(table_name, schema_analysis)
    
    def _create_basic_gold_steps(
        self,
        table_name: str,
        schema_analysis: Dict[str, Any]
    ) -> List[TransformationStep]:
        """Create basic gold aggregation steps as fallback"""
        
        steps = []
        
        # Daily aggregation
        daily_sql = f"""
CREATE TABLE gold_{table_name}_daily AS
SELECT 
    DATE_TRUNC('day', updated_at) as date,
    COUNT(*) as total_records,
    COUNT(DISTINCT id) as unique_devices,
    SUM(CASE WHEN is_stale THEN 1 ELSE 0 END) as stale_count
FROM silver_{table_name}
GROUP BY DATE_TRUNC('day', updated_at);
"""
        
        steps.append(TransformationStep(
            step_id="agg_daily_001",
            step_name=f"Daily Aggregation - {table_name}",
            transformation_type=TransformationType.AGGREGATION,
            input_tables=[f"silver_{table_name}"],
            output_table=f"gold_{table_name}_daily",
            sql_logic=daily_sql,
            description="Daily aggregated metrics",
            business_rules=["One row per day"]
        ))
        
        return steps
    
    def plan_metric_transformations(
        self,
        metrics_config: List[MetricConfig],
        source_tables: List[str],
        schema_analyses: Optional[Dict[str, Any]] = None
    ) -> List[TransformationStep]:
        """
        Plan transformations to create metrics in gold layer based on metric configurations.
        
        Args:
            metrics_config: List of metric configurations
            source_tables: List of available source tables (silver layer)
            schema_analyses: Optional schema analyses for context
            
        Returns:
            List of transformation steps for creating metrics
        """
        system_prompt = """You are a business intelligence expert specializing in metric calculation and transformation.

Your task is to generate SQL transformations that create business metrics in the gold layer.

**Metric Types and SQL Patterns:**

1. **Count Metrics**:
   - Simple count: `COUNT(*)`
   - Distinct count: `COUNT(DISTINCT column)`
   - Conditional count: `COUNT(CASE WHEN condition THEN 1 END)`

2. **Sum Metrics**:
   - Total sum: `SUM(column)`
   - Conditional sum: `SUM(CASE WHEN condition THEN column ELSE 0 END)`

3. **Average Metrics**:
   - Simple average: `AVG(column)`
   - Weighted average: `SUM(column * weight) / SUM(weight)`

4. **Ratio Metrics**:
   - Percentage: `(numerator / denominator) * 100`
   - Ratio: `numerator / NULLIF(denominator, 0)`

5. **Growth Rate Metrics**:
   - Period-over-period: `(current_value - previous_value) / previous_value * 100`
   - Year-over-year: Use LAG with PARTITION BY

6. **Trend Metrics**:
   - Moving average: `AVG(metric) OVER (ORDER BY date ROWS BETWEEN N PRECEDING AND CURRENT ROW)`
   - Cumulative sum: `SUM(metric) OVER (ORDER BY date)`

7. **Rate Metrics**:
   - Conversion rate: `(converted_count / total_count) * 100`
   - Completion rate: `(completed_count / started_count) * 100`

**Best Practices:**
- Use proper NULL handling (NULLIF, COALESCE)
- Include time dimensions for time-series metrics
- Group by relevant dimensions
- Add appropriate filters
- Document business rules
- Handle edge cases (division by zero, null values)

Generate production-ready SQL that creates materialized metric tables."""
        
        steps = []
        
        for metric_config in metrics_config:
            # Build context from schema analyses
            schema_context = ""
            if schema_analyses:
                for table_name in metric_config.source_tables:
                    if table_name in schema_analyses:
                        analysis = schema_analyses[table_name]
                        schema_context += f"\n**Table: {table_name}**\n"
                        schema_context += f"Columns: {json.dumps([col.get('name') for col in analysis.get('columns', [])], indent=2)}\n"
            
            # Build dimensions and grouping
            group_by_clause = ""
            if metric_config.dimensions:
                group_by_clause = f"GROUP BY {', '.join(metric_config.dimensions)}"
            
            # Build time dimension handling
            time_dimension_sql = ""
            if metric_config.time_granularity:
                time_dimension_sql = f"""
    DATE_TRUNC('{metric_config.time_granularity}', time_column) as metric_date,"""
            
            # Build filters
            filter_clause = ""
            if metric_config.filters:
                filter_conditions = []
                for key, value in metric_config.filters.items():
                    if isinstance(value, list):
                        # Format values for IN clause - handle strings and non-strings separately
                        formatted_values = []
                        for v in value:
                            if isinstance(v, str):
                                formatted_values.append(f"'{v}'")
                            else:
                                formatted_values.append(str(v))
                        filter_conditions.append(f"{key} IN ({', '.join(formatted_values)})")
                    else:
                        # Format single value for equality check
                        formatted_value = f"'{value}'" if isinstance(value, str) else str(value)
                        filter_conditions.append(f"{key} = {formatted_value}")
                if filter_conditions:
                    filter_clause = f"WHERE {' AND '.join(filter_conditions)}"
            
            user_prompt = f"""Generate SQL transformation for metric: {metric_config.metric_name}

**Metric Configuration:**
- Type: {metric_config.metric_type}
- Description: {metric_config.description}
- Formula: {metric_config.formula}
- Source Tables: {', '.join(metric_config.source_tables)}
- Dimensions: {', '.join(metric_config.dimensions) if metric_config.dimensions else 'None'}
- Time Granularity: {metric_config.time_granularity or 'None'}
- Filters: {json.dumps(metric_config.filters) if metric_config.filters else 'None'}
- Business Rules: {', '.join(metric_config.business_rules) if metric_config.business_rules else 'None'}
- Target Mart: {metric_config.target_mart or 'gold_metrics'}

{schema_context}

**Requirements:**
1. Create a CREATE TABLE statement for the metric
2. Use appropriate SQL for metric type: {metric_config.metric_type}
3. Implement the formula: {metric_config.formula}
4. Include time dimension if granularity specified: {metric_config.time_granularity or 'N/A'}
5. Group by dimensions: {', '.join(metric_config.dimensions) if metric_config.dimensions else 'All records'}
6. Apply filters: {filter_clause or 'None'}
7. Handle NULL values and edge cases
8. Add proper data types and constraints

**Output Format:**
Return JSON with:
{{
    "step_id": "metric_001",
    "step_name": "Metric: {metric_config.metric_name}",
    "transformation_type": "metric",
    "input_tables": {metric_config.source_tables},
    "output_table": "gold_{metric_config.metric_name.lower().replace(' ', '_')}",
    "sql_logic": "CREATE TABLE ... AS SELECT ...",
    "description": "{metric_config.description}",
    "business_rules": {metric_config.business_rules},
    "data_quality_checks": ["Check for null values", "Verify metric calculation"]
}}"""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            try:
                # Use SQL generator agent for metric SQL
                table_schemas = {}
                if schema_analyses:
                    for table_name in metric_config.source_tables:
                        if table_name in schema_analyses:
                            analysis = schema_analyses[table_name]
                            table_schemas[table_name] = analysis.get("columns", [])
                
                sql = self.sql_generator.generate_metric_sql(
                    metric_name=metric_config.metric_name,
                    metric_description=metric_config.description,
                    metric_type=metric_config.metric_type,
                    source_tables=metric_config.source_tables,
                    formula=metric_config.formula,
                    dimensions=metric_config.dimensions,
                    time_granularity=metric_config.time_granularity,
                    filters=metric_config.filters,
                    table_schemas=table_schemas if table_schemas else None,
                    business_rules=metric_config.business_rules,
                    target_dialect=SQLDialect.POSTGRESQL  # Will be converted to target dialect if needed
                )
                
                # Create TransformationStep
                step = TransformationStep(
                    step_id=f"metric_{len(steps) + 1:03d}",
                    step_name=f"Metric: {metric_config.metric_name}",
                    transformation_type=TransformationType.METRIC,
                    input_tables=metric_config.source_tables,
                    output_table=f"gold_{metric_config.metric_name.lower().replace(' ', '_')}",
                    sql_logic=sql,
                    description=metric_config.description,
                    business_rules=metric_config.business_rules,
                    data_quality_checks=["Verify metric calculation", "Check for null values"]
                )
                steps.append(step)
                
            except Exception as e:
                logger.error(f"Error planning metric transformation for {metric_config.metric_name}: {str(e)}")
                # Create fallback step
                fallback_sql = self._create_fallback_metric_sql(metric_config)
                step = TransformationStep(
                    step_id=f"metric_{len(steps) + 1:03d}",
                    step_name=f"Metric: {metric_config.metric_name}",
                    transformation_type=TransformationType.METRIC,
                    input_tables=metric_config.source_tables,
                    output_table=f"gold_{metric_config.metric_name.lower().replace(' ', '_')}",
                    sql_logic=fallback_sql,
                    description=metric_config.description,
                    business_rules=metric_config.business_rules,
                    data_quality_checks=["Verify metric calculation", "Check for null values"]
                )
                steps.append(step)
        
        return steps
    
    def _create_fallback_metric_sql(self, metric_config: MetricConfig) -> str:
        """Create a basic fallback SQL for a metric"""
        source_table = metric_config.source_tables[0] if metric_config.source_tables else "silver_table"
        
        # Basic metric SQL based on type
        if metric_config.metric_type == "count":
            metric_sql = "COUNT(*)"
        elif metric_config.metric_type == "sum":
            metric_sql = "SUM(value)"  # Assumes a 'value' column
        elif metric_config.metric_type == "avg":
            metric_sql = "AVG(value)"
        elif metric_config.metric_type in ["ratio", "percentage"]:
            metric_sql = "(SUM(numerator) / NULLIF(SUM(denominator), 0)) * 100"
        else:
            metric_sql = "COUNT(*)"
        
        group_by = ""
        if metric_config.dimensions:
            group_by = f"GROUP BY {', '.join(metric_config.dimensions)}"
        
        return f"""
CREATE TABLE {metric_config.metric_name.lower().replace(' ', '_')} AS
SELECT
    {', '.join(metric_config.dimensions) if metric_config.dimensions else ''}
    {metric_sql} as {metric_config.metric_name}
FROM {source_table}
{group_by};
"""
    
    def plan_join_transformation(
        self,
        parent_table: str,
        child_table: str,
        join_condition: str,
        join_type: str = "LEFT"
    ) -> TransformationStep:
        """
        Plan a join transformation between two tables.
        
        Args:
            parent_table: Parent table name
            child_table: Child table name
            join_condition: SQL join condition
            join_type: Type of join (LEFT, INNER, etc.)
            
        Returns:
            TransformationStep for the join
        """
        system_prompt = """You are a SQL expert. Generate efficient join logic.

Best practices:
- Use explicit column selection (avoid SELECT *)
- Add comments explaining the join
- Consider NULL handling
- Optimize join conditions
- Document the resulting grain"""
        
        user_prompt = f"""Generate SQL to join:

Parent Table: {parent_table}
Child Table: {child_table}
Join Type: {join_type} JOIN
Join Condition: {join_condition}

Create a new table with:
- All columns from parent
- Selected columns from child
- Handle NULL values appropriately
- Document the grain

Return complete SQL as JSON."""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        response = self.llm.invoke(messages)
        log_llm_call(f"Join Transformation Planning ({parent_table} + {child_table})", messages, response)
        
        # For simplicity, create basic join SQL
        join_sql = f"""
CREATE TABLE silver_{parent_table}_{child_table} AS
SELECT 
    p.*,
    c.* -- TODO: Select specific columns
FROM {parent_table} p
{join_type} JOIN {child_table} c
    ON {join_condition};
"""
        
        return TransformationStep(
            step_id=f"join_{parent_table}_{child_table}",
            step_name=f"Join {parent_table} with {child_table}",
            transformation_type=TransformationType.JOIN,
            input_tables=[parent_table, child_table],
            output_table=f"silver_{parent_table}_{child_table}",
            sql_logic=join_sql,
            description=f"{join_type} join between {parent_table} and {child_table}"
        )
    
    def create_execution_plan(self, steps: List[TransformationStep]) -> List[str]:
        """
        Create execution order for transformation steps based on dependencies.
        
        Args:
            steps: List of transformation steps
            
        Returns:
            List of step IDs in execution order
        """
        # Simple topological sort
        executed = set()
        execution_order = []
        
        max_iterations = len(steps) * 2
        iteration = 0
        
        while len(execution_order) < len(steps) and iteration < max_iterations:
            iteration += 1
            
            for step in steps:
                if step.step_id in executed:
                    continue
                
                # Check if all dependencies are executed
                deps_met = all(dep in executed for dep in step.dependencies)
                
                if deps_met:
                    execution_order.append(step.step_id)
                    executed.add(step.step_id)
        
        return execution_order
    
    def generate_data_quality_checks(self, step: TransformationStep) -> List[str]:
        """
        Generate data quality check SQL for a transformation step.
        
        Args:
            step: TransformationStep to generate checks for
            
        Returns:
            List of SQL check statements
        """
        checks = []
        
        # Row count check
        checks.append(f"""
-- Check: Row count
SELECT 
    'Row Count Check' as check_name,
    COUNT(*) as row_count,
    CASE 
        WHEN COUNT(*) = 0 THEN 'FAIL'
        ELSE 'PASS'
    END as status
FROM {step.output_table};
""")
        
        # Null check for key columns
        checks.append(f"""
-- Check: Null values in key columns
SELECT 
    'Null Check' as check_name,
    COUNT(*) as null_count,
    CASE 
        WHEN COUNT(*) > 0 THEN 'FAIL'
        ELSE 'PASS'
    END as status
FROM {step.output_table}
WHERE id IS NULL;
""")
        
        # Deduplication check (if applicable)
        if step.transformation_type == TransformationType.DEDUPLICATION:
            checks.append(f"""
-- Check: Duplicate records
SELECT 
    'Duplicate Check' as check_name,
    COUNT(*) - COUNT(DISTINCT id) as duplicate_count,
    CASE 
        WHEN COUNT(*) - COUNT(DISTINCT id) > 0 THEN 'FAIL'
        ELSE 'PASS'
    END as status
FROM {step.output_table};
""")
        
        return checks


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    agent = TransformationPlannerAgent()
    
    # Example schema analysis
    schema_analysis = {
        "table_name": "dev_network_devices",
        "grain": "One row per device",
        "columns": [
            {"name": "id", "data_type": "BIGINT", "is_identifier": True},
            {"name": "ip", "data_type": "VARCHAR", "is_dimension": True},
            {"name": "updated_at", "data_type": "TIMESTAMP", "is_temporal": True},
            {"name": "is_stale", "data_type": "BOOLEAN", "is_dimension": True}
        ]
    }
    
    # LOD configuration
    lod_config = LODDeduplication(
        lod_type="FIXED",
        dimensions=["ip", "mac"],
        tie_breaker="updated_at",
        tie_breaker_order="DESC"
    )
    
    # Plan silver transformations
    print("Planning RAW → SILVER transformations...")
    silver_steps = agent.plan_raw_to_silver(
        "dev_network_devices",
        schema_analysis,
        lod_config
    )
    
    for step in silver_steps:
        print(f"\nStep: {step.step_name}")
        print(f"Type: {step.transformation_type}")
        print(f"SQL:\n{step.sql_logic}")
    
    # Create execution order
    execution_order = agent.create_execution_plan(silver_steps)
    print(f"\nExecution Order: {execution_order}")
    
    # Generate data quality checks
    for step in silver_steps:
        checks = agent.generate_data_quality_checks(step)
        print(f"\nQuality Checks for {step.step_name}:")
        for check in checks:
            print(check)

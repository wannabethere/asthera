"""
SQL Generator Agent
Centralized, robust SQL generation for all use cases across the codebase.
Always generates PostgreSQL SQL, then uses sqlglot to convert to target dialect.
Supports transformations, metrics, data marts, aggregations, and more.
"""

from typing import Dict, List, Any, Optional, Union
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from enum import Enum
import json
import re
import logging

from app.core.dependencies import get_llm

# Import sqlglot for SQL dialect conversion
try:
    import sqlglot
    from sqlglot import transpile
    SQLGLOT_AVAILABLE = True
except ImportError:
    SQLGLOT_AVAILABLE = False
    logger.warning("sqlglot not available - SQL dialect conversion will be disabled. Install with: pip install sqlglot")

logger = logging.getLogger("genieml-agents")


# ============================================================================
# SQL GENERATION MODELS
# ============================================================================

class SQLType(str, Enum):
    """Types of SQL to generate"""
    CREATE_TABLE = "create_table"
    CREATE_TABLE_AS_SELECT = "create_table_as_select"
    SELECT = "select"
    TRANSFORMATION = "transformation"
    METRIC = "metric"
    DATA_MART = "data_mart"
    AGGREGATION = "aggregation"
    VIEW = "view"
    DBT_MODEL = "dbt_model"


class SQLDialect(str, Enum):
    """SQL dialect support - target dialects for conversion"""
    POSTGRESQL = "postgresql"  # Base dialect (always generated)
    SNOWFLAKE = "snowflake"
    BIGQUERY = "bigquery"
    REDSHIFT = "redshift"
    SPARK = "spark"
    TRINO = "trino"
    DUCKDB = "duckdb"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    ORACLE = "oracle"
    MSSQL = "mssql"
    TERADATA = "teradata"


class SQLGenerationRequest(BaseModel):
    """Request for SQL generation"""
    sql_type: SQLType
    description: str
    source_tables: List[str] = Field(default_factory=list)
    target_table: Optional[str] = None
    columns: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    aggregations: Optional[Dict[str, str]] = Field(default_factory=dict)  # column -> aggregation_type
    group_by: Optional[List[str]] = Field(default_factory=list)
    joins: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    time_granularity: Optional[str] = None  # day, week, month, quarter, year
    business_rules: List[str] = Field(default_factory=list)
    formula: Optional[str] = None  # For metrics
    target_dialect: SQLDialect = SQLDialect.POSTGRESQL  # Target dialect for conversion (default: postgresql)
    table_schemas: Optional[Dict[str, List[Dict[str, Any]]]] = None  # table_name -> columns
    additional_context: Optional[Dict[str, Any]] = Field(default_factory=dict)


class SQLGenerationResult(BaseModel):
    """Result from SQL generation"""
    sql: str  # Final SQL in target dialect
    postgresql_sql: Optional[str] = None  # Original PostgreSQL SQL before conversion
    target_dialect: SQLDialect = SQLDialect.POSTGRESQL
    validated: bool = False
    validation_errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    estimated_complexity: str = "medium"  # low, medium, high
    conversion_applied: bool = False  # Whether sqlglot conversion was applied


# ============================================================================
# SQL GENERATOR AGENT
# ============================================================================

class SQLGeneratorAgent:
    """Centralized SQL generator for all use cases"""
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        default_target_dialect: SQLDialect = SQLDialect.POSTGRESQL
    ):
        """
        Initialize SQL generator agent.
        
        Args:
            llm: Optional LLM instance
            model_name: LLM model name
            default_target_dialect: Default target dialect for conversion (always generates PostgreSQL first)
        """
        self.llm = llm or get_llm(model=model_name)
        self.default_target_dialect = default_target_dialect
        self.base_dialect = SQLDialect.POSTGRESQL  # Always generate PostgreSQL SQL
    
    def generate_sql(
        self,
        request: Union[SQLGenerationRequest, Dict[str, Any]]
    ) -> SQLGenerationResult:
        """
        Generate SQL based on request.
        
        Args:
            request: SQLGenerationRequest or dictionary with request parameters
            
        Returns:
            SQLGenerationResult with generated SQL and metadata
        """
        # Convert dict to request if needed
        if isinstance(request, dict):
            request = SQLGenerationRequest(**request)
        
        # Build system prompt based on SQL type
        system_prompt = self._build_system_prompt(request)
        
        # Build user prompt with all context
        user_prompt = self._build_user_prompt(request)
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        try:
            response = self.llm.invoke(messages)
            postgresql_sql = self._extract_sql_from_response(response.content)
            
            # Validate PostgreSQL SQL
            validation_result = self._validate_sql(postgresql_sql, request)
            
            # Convert to target dialect if needed
            target_sql = postgresql_sql
            conversion_applied = False
            if request.target_dialect != SQLDialect.POSTGRESQL and SQLGLOT_AVAILABLE:
                try:
                    target_sql = self._convert_sql_dialect(
                        postgresql_sql,
                        source_dialect="postgresql",
                        target_dialect=request.target_dialect.value
                    )
                    conversion_applied = True
                    logger.info(f"Converted SQL from PostgreSQL to {request.target_dialect.value}")
                except Exception as e:
                    logger.warning(f"Error converting SQL to {request.target_dialect.value}, using PostgreSQL: {e}")
                    target_sql = postgresql_sql
                    validation_result["warnings"].append(f"Dialect conversion failed: {str(e)}")
            
            # Estimate complexity
            complexity = self._estimate_complexity(postgresql_sql, request)
            
            result = SQLGenerationResult(
                sql=target_sql,
                postgresql_sql=postgresql_sql,
                target_dialect=request.target_dialect,
                validated=validation_result["valid"],
                validation_errors=validation_result["errors"],
                warnings=validation_result["warnings"],
                estimated_complexity=complexity,
                conversion_applied=conversion_applied
            )
            
            logger.info(f"Generated SQL for {request.sql_type.value} (complexity: {complexity}, dialect: {request.target_dialect.value})")
            if result.warnings:
                logger.warning(f"SQL generation warnings: {result.warnings}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating SQL: {e}")
            # Return fallback SQL
            fallback_sql = self._generate_fallback_sql(request)
            # Convert fallback SQL if needed
            target_fallback_sql = fallback_sql
            if request.target_dialect != SQLDialect.POSTGRESQL and SQLGLOT_AVAILABLE:
                try:
                    target_fallback_sql = self._convert_sql_dialect(
                        fallback_sql,
                        source_dialect="postgresql",
                        target_dialect=request.target_dialect.value
                    )
                except:
                    pass  # Use PostgreSQL fallback if conversion fails
            
            return SQLGenerationResult(
                sql=target_fallback_sql,
                postgresql_sql=fallback_sql,
                target_dialect=request.target_dialect,
                validated=False,
                validation_errors=[f"Error during generation: {str(e)}"],
                warnings=["Used fallback SQL due to generation error"],
                estimated_complexity="low",
                conversion_applied=(target_fallback_sql != fallback_sql)
            )
    
    def _build_system_prompt(self, request: SQLGenerationRequest) -> str:
        """Build system prompt - always generates PostgreSQL SQL"""
        
        # Always generate PostgreSQL SQL
        base_dialect_guideline = """Use PostgreSQL syntax. Key PostgreSQL features:
- Use DATE_TRUNC('day', timestamp) for time functions
- Use INTERVAL for date arithmetic: CURRENT_DATE - INTERVAL '30 days'
- Use COALESCE and NULLIF for NULL handling
- Use CASE WHEN for conditional logic
- Use proper PostgreSQL data types (BIGINT, VARCHAR, TIMESTAMP, BOOLEAN, etc.)
- Use double quotes for identifiers if needed, single quotes for strings
- Use PostgreSQL array functions if needed
- Use window functions: OVER (PARTITION BY ... ORDER BY ...)
"""
        
        sql_type_guidelines = {
            SQLType.CREATE_TABLE: """
**CREATE TABLE Guidelines:**
- Include proper column definitions with data types
- Add NOT NULL constraints where appropriate
- Include primary keys if applicable
- Add indexes for performance (as comments)
- Document columns with comments
""",
            SQLType.CREATE_TABLE_AS_SELECT: """
**CREATE TABLE AS SELECT Guidelines:**
- Use CREATE TABLE ... AS SELECT syntax
- Include all necessary columns
- Add proper WHERE clauses for filtering
- Use appropriate JOINs when needed
- Handle NULL values properly
""",
            SQLType.TRANSFORMATION: """
**Transformation SQL Guidelines:**
- Clean and standardize data
- Handle NULL values with COALESCE or NULLIF
- Apply data type conversions
- Implement deduplication logic if needed
- Add data quality checks
- Use CASE statements for conditional logic
""",
            SQLType.METRIC: """
**Metric SQL Guidelines:**
- Calculate business metrics accurately
- Handle division by zero with NULLIF
- Use appropriate aggregations (COUNT, SUM, AVG, etc.)
- Include time dimensions for time-series metrics
- Group by relevant dimensions
- Apply filters correctly
- Use window functions for trends and comparisons
""",
            SQLType.DATA_MART: """
**Data Mart SQL Guidelines:**
- Create denormalized, business-friendly tables
- Include calculated fields and KPIs
- Optimize for reporting and dashboards
- Add proper indexes (as comments)
- Include time dimensions
- Support common analytical queries
""",
            SQLType.AGGREGATION: """
**Aggregation SQL Guidelines:**
- Use appropriate GROUP BY clauses
- Apply correct aggregation functions
- Handle time granularity with DATE_TRUNC
- Include all necessary dimensions
- Use HAVING for post-aggregation filters
""",
            SQLType.DBT_MODEL: """
**dbt Model SQL Guidelines:**
- Use {{ config() }} for materialization
- Use {{ ref() }} for table references
- Use {{ source() }} for source references
- Follow dbt best practices
- Include proper documentation
"""
        }
        
        base_prompt = f"""You are an expert PostgreSQL SQL engineer.

{base_dialect_guideline}

**Note:** Always generate PostgreSQL-compliant SQL. The SQL will be automatically converted to the target dialect ({request.target_dialect.value}) if needed.

**Core SQL Best Practices:**
1. **NULL Handling**: Always use COALESCE or NULLIF to handle NULL values
2. **Division by Zero**: Use NULLIF(denominator, 0) to prevent division errors
3. **Performance**: Use appropriate indexes, avoid unnecessary subqueries
4. **Readability**: Format SQL clearly with proper indentation
5. **Security**: Use parameterized queries (show as placeholders)
6. **Data Types**: Use PostgreSQL data types (BIGINT, VARCHAR, TIMESTAMP, BOOLEAN, DECIMAL, etc.)
7. **Constraints**: Add appropriate constraints (NOT NULL, CHECK, etc.)
8. **Comments**: Add comments for complex logic

{sql_type_guidelines.get(request.sql_type, "")}

**Critical PostgreSQL Rules:**
- Always validate column names exist in source tables
- Use proper JOIN syntax (INNER, LEFT, RIGHT, FULL OUTER)
- Handle time zones correctly for TIMESTAMP columns
- Use DATE_TRUNC('granularity', timestamp) for time-based aggregations
- Use INTERVAL for date arithmetic: CURRENT_DATE - INTERVAL '30 days'
- Use PostgreSQL-specific functions when appropriate
- Include proper error handling for edge cases
- Document complex calculations

Generate production-ready, optimized PostgreSQL SQL that follows all best practices."""
        
        return base_prompt
    
    def _build_user_prompt(self, request: SQLGenerationRequest) -> str:
        """Build detailed user prompt with all context"""
        
        # Build table schema information
        schema_info = ""
        if request.table_schemas:
            for table_name, columns in request.table_schemas.items():
                schema_info += f"\n**Table: {table_name}**\n"
                for col in columns[:30]:  # Limit to first 30 columns
                    col_name = col.get("name", "")
                    col_type = col.get("data_type", col.get("type", ""))
                    col_desc = col.get("description", "")
                    schema_info += f"  - {col_name} ({col_type}): {col_desc}\n"
        elif request.source_tables:
            schema_info = f"\n**Source Tables:** {', '.join(request.source_tables)}\n"
            schema_info += "(Table schemas not provided - use standard column names)"
        
        # Build filters information
        filters_info = ""
        if request.filters:
            filters_info = "\n**Filters to Apply:**\n"
            for key, value in request.filters.items():
                if isinstance(value, list):
                    filters_info += f"  - {key} IN {value}\n"
                else:
                    filters_info += f"  - {key} = {value}\n"
        
        # Build aggregations information
        aggregations_info = ""
        if request.aggregations:
            aggregations_info = "\n**Aggregations:**\n"
            for col, agg_type in request.aggregations.items():
                aggregations_info += f"  - {col}: {agg_type}\n"
        
        # Build joins information
        joins_info = ""
        if request.joins:
            joins_info = "\n**Joins:**\n"
            for join in request.joins:
                join_type = join.get("type", "INNER")
                join_condition = join.get("condition", "")
                joins_info += f"  - {join_type} JOIN on {join_condition}\n"
        
        # Build time granularity information
        time_info = ""
        if request.time_granularity:
            time_info = f"\n**Time Granularity:** {request.time_granularity}\n"
            time_info += "Use DATE_TRUNC to group by this granularity.\n"
        
        # Build business rules
        rules_info = ""
        if request.business_rules:
            rules_info = "\n**Business Rules:**\n"
            for rule in request.business_rules:
                rules_info += f"  - {rule}\n"
        
        # Build formula information
        formula_info = ""
        if request.formula:
            formula_info = f"\n**Formula to Implement:** {request.formula}\n"
        
        prompt = f"""Generate {request.sql_type.value.replace('_', ' ').title()} SQL:

**Description:** {request.description}

**SQL Type:** {request.sql_type.value}
**Base Dialect:** PostgreSQL (will be converted to {request.target_dialect.value} if needed)
**Target Table:** {request.target_table or 'Not specified'}

{schema_info}
{filters_info}
{aggregations_info}
{joins_info}
{time_info}
{formula_info}
{rules_info}

**Group By:** {', '.join(request.group_by) if request.group_by else 'None'}

**Additional Context:**
{json.dumps(request.additional_context, indent=2) if request.additional_context else 'None'}

**Requirements:**
1. Generate complete, production-ready PostgreSQL SQL
2. Follow all PostgreSQL best practices
3. Handle NULL values and edge cases
4. Include proper error handling
5. Add comments for complex logic
6. Optimize for performance where possible
7. Use PostgreSQL-specific features when beneficial

Return only the PostgreSQL SQL statement, no explanations or markdown formatting."""
        
        return prompt
    
    def _extract_sql_from_response(self, response_content: str) -> str:
        """Extract SQL from LLM response, handling markdown code blocks"""
        sql = response_content.strip()
        
        # Remove markdown code blocks
        if sql.startswith("```sql"):
            sql = re.sub(r'^```sql\s*', '', sql, flags=re.MULTILINE)
            sql = re.sub(r'\s*```$', '', sql, flags=re.MULTILINE)
        elif sql.startswith("```"):
            sql = re.sub(r'^```\s*', '', sql, flags=re.MULTILINE)
            sql = re.sub(r'\s*```$', '', sql, flags=re.MULTILINE)
        
        # Remove leading/trailing whitespace
        sql = sql.strip()
        
        return sql
    
    def _validate_sql(self, sql: str, request: SQLGenerationRequest) -> Dict[str, Any]:
        """Basic SQL validation"""
        errors = []
        warnings = []
        
        # Check for basic SQL structure
        sql_upper = sql.upper()
        
        # Check for required keywords based on type
        if request.sql_type == SQLType.CREATE_TABLE_AS_SELECT:
            if "CREATE TABLE" not in sql_upper:
                errors.append("Missing CREATE TABLE statement")
            if "SELECT" not in sql_upper:
                errors.append("Missing SELECT statement")
        elif request.sql_type == SQLType.SELECT:
            if "SELECT" not in sql_upper:
                errors.append("Missing SELECT statement")
        
        # Check for common issues
        if "SELECT *" in sql_upper and request.sql_type in [SQLType.METRIC, SQLType.AGGREGATION]:
            warnings.append("Using SELECT * in metric/aggregation - consider specifying columns")
        
        if "DIVISION BY ZERO" in sql_upper or "/ 0" in sql:
            warnings.append("Potential division by zero - ensure NULLIF is used")
        
        # Check for proper NULL handling in aggregations
        if any(agg in sql_upper for agg in ["SUM(", "AVG(", "COUNT("]):
            if "NULLIF" not in sql_upper and "COALESCE" not in sql_upper:
                warnings.append("Consider NULL handling in aggregations")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def _estimate_complexity(self, sql: str, request: SQLGenerationRequest) -> str:
        """Estimate SQL complexity"""
        sql_upper = sql.upper()
        
        complexity_score = 0
        
        # Count joins
        join_count = sql_upper.count("JOIN")
        complexity_score += join_count * 2
        
        # Count subqueries
        subquery_count = sql_upper.count("SELECT") - 1
        complexity_score += subquery_count * 3
        
        # Count window functions
        window_count = sql_upper.count("OVER (")
        complexity_score += window_count * 2
        
        # Count CASE statements
        case_count = sql_upper.count("CASE")
        complexity_score += case_count
        
        # Count aggregations
        agg_count = sum(1 for agg in ["SUM(", "AVG(", "COUNT(", "MAX(", "MIN("] if agg in sql_upper)
        complexity_score += agg_count
        
        if complexity_score < 5:
            return "low"
        elif complexity_score < 15:
            return "medium"
        else:
            return "high"
    
    def _convert_sql_dialect(
        self,
        sql: str,
        source_dialect: str = "postgresql",
        target_dialect: str = "postgresql"
    ) -> str:
        """
        Convert SQL from source dialect to target dialect using sqlglot.
        
        Args:
            sql: SQL statement to convert
            source_dialect: Source dialect (default: postgresql)
            target_dialect: Target dialect
            
        Returns:
            Converted SQL statement
        """
        if not SQLGLOT_AVAILABLE:
            logger.warning("sqlglot not available, returning original SQL")
            return sql
        
        if source_dialect == target_dialect:
            return sql
        
        try:
            # Parse and transpile SQL
            # sqlglot uses lowercase dialect names
            source_dialect_lower = source_dialect.lower()
            target_dialect_lower = target_dialect.lower()
            
            # Map our enum values to sqlglot dialect names
            dialect_map = {
                "postgresql": "postgres",
                "mssql": "tsql",
                "mysql": "mysql",
                "sqlite": "sqlite",
                "snowflake": "snowflake",
                "bigquery": "bigquery",
                "redshift": "redshift",
                "spark": "spark",
                "duckdb": "duckdb",
                "oracle": "oracle",
                "teradata": "teradata"
            }
            
            sqlglot_source = dialect_map.get(source_dialect_lower, source_dialect_lower)
            sqlglot_target = dialect_map.get(target_dialect_lower, target_dialect_lower)
            
            # Transpile SQL
            converted_sql = transpile(
                sql,
                read=sqlglot_source,
                write=sqlglot_target,
                pretty=True
            )
            
            # transpile returns a list, get first element
            if isinstance(converted_sql, list) and len(converted_sql) > 0:
                return converted_sql[0]
            elif isinstance(converted_sql, str):
                return converted_sql
            else:
                logger.warning(f"Unexpected sqlglot output format, returning original SQL")
                return sql
                
        except Exception as e:
            logger.error(f"Error converting SQL from {source_dialect} to {target_dialect}: {e}")
            logger.debug(f"Original SQL: {sql[:200]}...")
            # Return original SQL if conversion fails
            return sql
    
    def _generate_fallback_sql(self, request: SQLGenerationRequest) -> str:
        """Generate basic fallback SQL when generation fails"""
        source_table = request.source_tables[0] if request.source_tables else "source_table"
        target_table = request.target_table or f"target_{request.sql_type.value}"
        
        if request.sql_type == SQLType.CREATE_TABLE_AS_SELECT:
            group_by = ""
            if request.group_by:
                group_by = f"\nGROUP BY {', '.join(request.group_by)}"
            
            return f"""CREATE TABLE {target_table} AS
SELECT *
FROM {source_table}
{group_by};"""
        elif request.sql_type == SQLType.SELECT:
            return f"SELECT * FROM {source_table};"
        else:
            return f"-- Fallback SQL for {request.sql_type.value}\nSELECT * FROM {source_table};"
    
    # ========================================================================
    # CONVENIENCE METHODS
    # ========================================================================
    
    def generate_transformation_sql(
        self,
        description: str,
        source_tables: List[str],
        target_table: str,
        table_schemas: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        filters: Optional[Dict[str, Any]] = None,
        business_rules: Optional[List[str]] = None,
        target_dialect: SQLDialect = None
    ) -> str:
        """Generate transformation SQL"""
        request = SQLGenerationRequest(
            sql_type=SQLType.TRANSFORMATION,
            description=description,
            source_tables=source_tables,
            target_table=target_table,
            table_schemas=table_schemas,
            filters=filters or {},
            business_rules=business_rules or [],
            target_dialect=target_dialect or self.default_target_dialect
        )
        result = self.generate_sql(request)
        return result.sql
    
    def generate_metric_sql(
        self,
        metric_name: str,
        metric_description: str,
        metric_type: str,
        source_tables: List[str],
        formula: str,
        dimensions: Optional[List[str]] = None,
        time_granularity: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        table_schemas: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        business_rules: Optional[List[str]] = None,
        target_dialect: SQLDialect = None
    ) -> str:
        """Generate metric SQL"""
        target_table = f"gold_{metric_name.lower().replace(' ', '_')}"
        
        request = SQLGenerationRequest(
            sql_type=SQLType.METRIC,
            description=metric_description,
            source_tables=source_tables,
            target_table=target_table,
            formula=formula,
            group_by=dimensions or [],
            time_granularity=time_granularity,
            filters=filters or {},
            table_schemas=table_schemas,
            business_rules=business_rules or [],
            target_dialect=target_dialect or self.default_target_dialect
        )
        result = self.generate_sql(request)
        return result.sql
    
    def generate_data_mart_sql(
        self,
        mart_name: str,
        description: str,
        source_tables: List[str],
        columns: Optional[List[Dict[str, Any]]] = None,
        joins: Optional[List[Dict[str, Any]]] = None,
        filters: Optional[Dict[str, Any]] = None,
        aggregations: Optional[Dict[str, str]] = None,
        group_by: Optional[List[str]] = None,
        table_schemas: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        business_rules: Optional[List[str]] = None,
        target_dialect: SQLDialect = None
    ) -> str:
        """Generate data mart SQL"""
        request = SQLGenerationRequest(
            sql_type=SQLType.DATA_MART,
            description=description,
            source_tables=source_tables,
            target_table=mart_name,
            columns=columns or [],
            joins=joins or [],
            filters=filters or {},
            aggregations=aggregations or {},
            group_by=group_by or [],
            table_schemas=table_schemas,
            business_rules=business_rules or [],
            target_dialect=target_dialect or self.default_target_dialect
        )
        result = self.generate_sql(request)
        return result.sql
    
    def generate_aggregation_sql(
        self,
        description: str,
        source_table: str,
        aggregations: Dict[str, str],
        group_by: List[str],
        time_granularity: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        table_schema: Optional[List[Dict[str, Any]]] = None,
        target_dialect: SQLDialect = None
    ) -> str:
        """Generate aggregation SQL"""
        request = SQLGenerationRequest(
            sql_type=SQLType.AGGREGATION,
            description=description,
            source_tables=[source_table],
            aggregations=aggregations,
            group_by=group_by,
            time_granularity=time_granularity,
            filters=filters or {},
            table_schemas={source_table: table_schema} if table_schema else None,
            target_dialect=target_dialect or self.default_target_dialect
        )
        result = self.generate_sql(request)
        return result.sql


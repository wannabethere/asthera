import logging
import re
from abc import ABCMeta, abstractmethod
from typing import Any, Dict, Optional, Tuple

import aiohttp
import sqlglot
from pydantic import BaseModel

logger = logging.getLogger("wren-ai-service")


class EngineConfig(BaseModel):
    provider: str = "wren_ui"
    config: dict = {}


class Engine(metaclass=ABCMeta):
    @abstractmethod
    async def execute_sql(
        self,
        sql: str,
        session: aiohttp.ClientSession,
        dry_run: bool = True,
        **kwargs,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        ...

    @abstractmethod
    async def execute_sql_in_batches(
        self,
        sql: str,
        session: aiohttp.ClientSession,
        batch_size: int = 1000,
        batch_num: Optional[int] = None,
        max_batches: Optional[int] = None,
        dry_run: bool = True,
        **kwargs,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Execute SQL query in batches to handle large result sets efficiently
        
        Args:
            sql: SQL query to execute
            session: aiohttp ClientSession
            batch_size: Number of rows to fetch in each batch
            batch_num: Specific batch number to retrieve (None for all batches)
            max_batches: Maximum number of batches to process (None for unlimited)
            dry_run: If True, validates SQL without executing
            **kwargs: Additional arguments
            
        Returns:
            Tuple of (success: bool, result: Dict)
        """
        ...

def clean_generation_result(result: str) -> str:
    def _normalize_whitespace(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip()

    # First, try to extract SQL from wrapped format
    # Look for patterns like "SQL Query: SELECT ..." or "SELECT * FROM (Alert Request: ... SQL Query: ...)"
    sql_patterns = [
        r"SQL Query:\s*(SELECT.*?)(?:\s*LIMIT\s+\d+)?$",  # SQL Query: SELECT ... LIMIT 10
        r"SELECT\s+\*\s+FROM\s+\([^)]*SQL Query:\s*(SELECT.*?)\)",  # SELECT * FROM (Alert Request: ... SQL Query: ...)
        r"```sql\s*(SELECT.*?)\s*```",  # ```sql SELECT ... ```
        r"```\s*(SELECT.*?)\s*```",  # ``` SELECT ... ```
    ]
    
    for pattern in sql_patterns:
        match = re.search(pattern, result, re.DOTALL | re.IGNORECASE)
        if match:
            result = match.group(1).strip()
            break
    
    return (
        _normalize_whitespace(result)
        .replace("\\n", " ")
        .replace("```sql", "")
        .replace("```json", "")
        .replace('"""', "")
        .replace("'''", "")
        .replace("```", "")
        .replace(";", "")
    )


def remove_limit_statement(sql: str) -> str:
    pattern = r"\s*LIMIT\s+\d+(\s*;?\s*--.*|\s*;?\s*)$"
    modified_sql = re.sub(pattern, "", sql, flags=re.IGNORECASE)

    return modified_sql


def add_quotes(sql: str) -> Tuple[str, str]:
    try:
        # Clean the SQL first to remove any wrapping text
        cleaned_sql = clean_generation_result(sql)
        
        # Disable automatic quoting to prevent issues with PostgreSQL case sensitivity
        # The original code used identify=True which caused problems with column names
        quoted_sql = sqlglot.transpile(
            cleaned_sql, read="trino", identify=False, error_level=sqlglot.ErrorLevel.RAISE
        )[0]
    except Exception as e:
        logger.exception(f"Error in sqlglot.transpile for SQL: {sql[:100]}... Error: {e}")
        
        # Try to extract just the SELECT statement if the error is due to wrapping
        try:
            # Look for SELECT statement in the original SQL
            select_match = re.search(r'(SELECT\s+.*?)(?:\s*LIMIT\s+\d+)?$', sql, re.DOTALL | re.IGNORECASE)
            if select_match:
                select_sql = select_match.group(1).strip()
                quoted_sql = sqlglot.transpile(
                    select_sql, read="trino", identify=False, error_level=sqlglot.ErrorLevel.RAISE
                )[0]
                logger.info(f"Successfully extracted and processed SQL: {select_sql[:100]}...")
                return quoted_sql, ""
        except Exception as extract_error:
            logger.warning(f"Failed to extract SELECT statement: {extract_error}")

        return "", str(e)

    return quoted_sql, ""


def validate_and_fix_column_names(sql: str, schema_context: Dict[str, Any] = None) -> Tuple[str, str]:
    """
    Validate and fix column names in SQL to match actual database schema case.
    
    Args:
        sql: The SQL query to validate
        schema_context: Optional schema context containing actual column names
        
    Returns:
        Tuple of (fixed_sql, error_message)
    """
    try:
        if not schema_context:
            # If no schema context, just return the SQL as-is
            return sql, ""
        
        # Extract actual column names from schema context
        actual_columns = {}
        for table_info in schema_context.get("schemas", []):
            if isinstance(table_info, dict):
                table_name = table_info.get("table_name", "")
                table_ddl = table_info.get("table_ddl", "")
                
                # Parse DDL to extract column names
                if table_ddl:
                    # Simple regex to extract column names from CREATE TABLE
                    import re
                    column_matches = re.findall(r'^\s*(\w+)\s+[A-Z]+', table_ddl, re.MULTILINE)
                    for col in column_matches:
                        actual_columns[f"{table_name}.{col}"] = col
                        actual_columns[col] = col  # Also store just column name
        
        # If we have actual column information, try to fix case issues
        if actual_columns:
            # Simple case correction for common patterns
            fixed_sql = sql
            
            # Replace common case mismatches
            for actual_col, correct_case in actual_columns.items():
                # Handle table.column format
                if "." in actual_col:
                    table_name, col_name = actual_col.split(".", 1)
                    # Look for patterns like table.Column and replace with table.column
                    pattern = rf'\b{re.escape(table_name)}\.{re.escape(col_name)}\b'
                    replacement = f"{table_name}.{correct_case}"
                    fixed_sql = re.sub(pattern, replacement, fixed_sql, flags=re.IGNORECASE)
            
            return fixed_sql, ""
        
        return sql, ""
        
    except Exception as e:
        logger.exception(f"Error validating column names: {e}")
        return sql, str(e)

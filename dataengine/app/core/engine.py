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
        quoted_sql = sqlglot.transpile(
            sql, read="trino", identify=True, error_level=sqlglot.ErrorLevel.RAISE
        )[0]
    except Exception as e:
        logger.exception(f"Error in sqlglot.transpile to {sql}: {e}")

        return "", str(e)

    return quoted_sql, ""

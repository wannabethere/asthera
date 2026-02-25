"""
SQL validator against the PostgreSQL connection from app.settings.

Uses the cornerstone table (csod_training_records) and validates generated SQL
from the DS RAG pipeline. Supports:
- Single SQL execution (for step_1 or full combined SQL)
- Step-by-step pipeline validation (builds CTE chain, validates each step)
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.settings import get_settings

logger = logging.getLogger("lexy-ai-service")

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import SQLAlchemyError
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False


@dataclass
class ValidationResult:
    """Result of a SQL validation."""
    success: bool
    error: Optional[str] = None
    row_count: Optional[int] = None
    sql_executed: Optional[str] = None


def _get_postgres_url() -> str:
    """Build PostgreSQL connection URL from settings."""
    settings = get_settings()
    host = getattr(settings, "POSTGRES_HOST", "localhost")
    port = getattr(settings, "POSTGRES_PORT", 5432)
    database = getattr(settings, "POSTGRES_DB", "postgres")
    user = getattr(settings, "POSTGRES_USER", "postgres")
    password = getattr(settings, "POSTGRES_PASSWORD", "")
    engine_config = getattr(settings, "ENGINE_POSTGRES_CONFIG", None) or {}
    sslmode = engine_config.get("sslmode", "require")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}?sslmode={sslmode}"


def _clean_sql(sql: str) -> str:
    """Normalize SQL for execution."""
    if not sql or not sql.strip():
        return ""
    sql = sql.strip().rstrip(";")
    sql = re.sub(r"\s+", " ", sql)
    return sql


def validate_sql(sql: str, limit: Optional[int] = None) -> ValidationResult:
    """
    Execute SQL against the configured PostgreSQL connection.

    Args:
        sql: SQL to validate (SELECT only; no writes).
        limit: Optional row limit; appends LIMIT if provided.

    Returns:
        ValidationResult with success, error, row_count.
    """
    if not SQLALCHEMY_AVAILABLE:
        return ValidationResult(
            success=False,
            error="sqlalchemy/psycopg2 not installed",
        )

    sql = _clean_sql(sql)
    if not sql:
        return ValidationResult(success=False, error="Empty SQL")

    if limit is not None and "LIMIT" not in sql.upper():
        sql = f"{sql} LIMIT {limit}"

    try:
        url = _get_postgres_url()
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = result.fetchall()
            row_count = len(rows)
        return ValidationResult(
            success=True,
            row_count=row_count,
            sql_executed=sql,
        )
    except SQLAlchemyError as e:
        return ValidationResult(
            success=False,
            error=str(e),
            sql_executed=sql,
        )
    except Exception as e:
        return ValidationResult(
            success=False,
            error=str(e),
            sql_executed=sql,
        )


def validate_step_pipeline(
    step_sqls: Dict[str, str],
) -> Dict[str, ValidationResult]:
    """
    Validate a multi-step pipeline by building a CTE chain and executing each step.

    step_sqls: {"step_1": "SELECT ...", "step_2": "SELECT ... FROM step_1_output", ...}
    Each step N's SQL references step_{N-1}_output etc. We build:
      WITH step_1_output AS (step_1_sql),
           step_2_output AS (step_2_sql),
           ...
      SELECT * FROM step_N_output LIMIT 10

    Returns:
        Dict mapping step_key -> ValidationResult.
    """
    if not step_sqls:
        return {}

    step_keys = sorted(
        step_sqls.keys(),
        key=lambda k: int(k.split("_")[1]) if "_" in k and k.split("_")[1].isdigit() else 999,
    )
    results: Dict[str, ValidationResult] = {}

    for i, step_key in enumerate(step_keys):
        sql = step_sqls.get(step_key, "").strip()
        if not sql:
            results[step_key] = ValidationResult(success=False, error="Empty SQL")
            continue

        # Build CTE chain for steps 1..i
        ctes = []
        for j in range(i + 1):
            sk = step_keys[j]
            step_sql = step_sqls.get(sk, "").strip().rstrip(";")
            if step_sql:
                ctes.append(f"{sk}_output AS (\n{step_sql}\n)")

        full_sql = "WITH\n" + ",\n".join(ctes) + "\nSELECT * FROM " + step_key + "_output LIMIT 10"
        full_sql = _clean_sql(full_sql)

        res = validate_sql(full_sql, limit=None)  # LIMIT already in full_sql
        res.sql_executed = full_sql
        results[step_key] = res

        if not res.success:
            # Stop at first failure — later steps depend on this one
            break

    return results


def validate_combined_sql(combined_sql: str) -> ValidationResult:
    """
    Validate the full combined SQL (WITH ... SELECT ...) from the pipeline assembler.
    """
    sql = _clean_sql(combined_sql)
    if not sql:
        return ValidationResult(success=False, error="Empty SQL")
    if "LIMIT" not in sql.upper():
        sql = f"{sql} LIMIT 10"
    return validate_sql(sql, limit=None)

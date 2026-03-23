"""
DB schema for CWE/CAPEC/ATT&CK/KEV threat intelligence.
Creates tables used by the CVE enrichment pipeline.
Checks PostgreSQL for existing tables and column schemas before creating to avoid conflicts.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Set, Tuple

from sqlalchemy import text

logger = logging.getLogger(__name__)

# Expected columns per table: (column_name, type_hint) for schema compatibility check.
# type_hint is normalized: varchar, text, jsonb, integer, timestamptz
EXPECTED_COLUMNS: Dict[str, List[Tuple[str, str]]] = {
    "cwe_entries": [
        ("cwe_id", "varchar"),
        ("raw_data", "jsonb"),
        ("name", "text"),
        ("description", "text"),
        ("updated_at", "timestamptz"),
    ],
    "capec": [
        ("capec_id", "varchar"),
        ("name", "text"),
        ("description", "text"),
        ("related_cwes", "jsonb"),
        ("raw_data", "jsonb"),
        ("updated_at", "timestamptz"),
    ],
    "cwe_to_capec": [
        ("cwe_id", "varchar"),
        ("capec_id", "varchar"),
    ],
    "nvd_cves_by_cwe": [
        ("cwe_id", "varchar"),
        ("cve_id", "varchar"),
        ("normalized_data", "jsonb"),
    ],
    "attack_enterprise_techniques": [
        ("technique_id", "varchar"),
        ("name", "text"),
        ("description", "text"),
        ("raw_data", "jsonb"),
        ("updated_at", "timestamptz"),
    ],
    "cisa_kev": [
        ("cve_id", "varchar"),
        ("catalog_date", "text"),
        ("raw_data", "jsonb"),
        ("updated_at", "timestamptz"),
    ],
    "cwe_capec_attack_mappings": [
        ("id", "integer"),
        ("cwe_id", "varchar"),
        ("capec_id", "varchar"),
        ("attack_id", "varchar"),
        ("tactic", "varchar"),
        ("mapping_basis", "varchar"),
        ("confidence", "varchar"),
        ("example_cves", "jsonb"),
        ("created_at", "timestamptz"),
    ],
    "cwe_technique_mappings": [
        ("cwe_id", "varchar"),
        ("technique_id", "varchar"),
        ("tactic", "varchar"),
        ("confidence", "varchar"),
        ("mapping_source", "varchar"),
    ],
}


def _normalize_pg_type(data_type: str) -> str:
    """Normalize PostgreSQL data_type to our type hints for comparison."""
    if not data_type:
        return "unknown"
    t = data_type.lower()
    if "character varying" in t or "varchar" in t:
        return "varchar"
    if t == "text":
        return "text"
    if t == "jsonb" or t == "json":
        return "jsonb"
    if "timestamp" in t:
        return "timestamptz"
    if t in ("integer", "int4", "serial", "bigint", "int8"):
        return "integer"
    return t


def get_existing_tables(session) -> Set[str]:
    """
    Query PostgreSQL for existing tables in user schemas.
    Use before creating tables to avoid conflicts with cve_enrich_pipeline.
    """
    try:
        result = session.execute(text("""
            SELECT schemaname, tablename
            FROM pg_tables
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
        """))
        return {row[1].lower() for row in result.fetchall() if row[1]}
    except Exception as e:
        logger.warning(f"Could not query existing tables: {e}")
        return set()


def get_existing_table_columns(session) -> Dict[str, List[Tuple[str, str]]]:
    """
    Query PostgreSQL for existing table columns (name, normalized_type).
    Returns {table_name: [(col_name, type), ...]} for user schemas.
    """
    try:
        result = session.execute(text("""
            SELECT table_schema, table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY table_schema, table_name, ordinal_position
        """))
        out: Dict[str, List[Tuple[str, str]]] = {}
        for row in result.fetchall():
            schema, tbl, col, dtype = row[0], row[1], row[2], row[3]
            key = tbl.lower()
            if key not in out:
                out[key] = []
            out[key].append((col.lower(), _normalize_pg_type(dtype or "")))
        return out
    except Exception as e:
        logger.warning(f"Could not query existing columns: {e}")
        return {}


def _types_compatible(expected: str, actual: str) -> bool:
    """Check if PostgreSQL types are compatible (varchar/text interchangeable, etc.)."""
    if expected == actual:
        return True
    compatible_pairs = {
        ("varchar", "text"),
        ("text", "varchar"),
        ("integer", "integer"),
    }
    return (expected, actual) in compatible_pairs or (actual, expected) in compatible_pairs


def _schema_compatible(
    table_name: str,
    existing_cols: List[Tuple[str, str]],
    expected_cols: List[Tuple[str, str]],
) -> bool:
    """
    Check if existing table has all expected columns with compatible types.
    Extra columns in existing table are ok (superset). Missing or type-mismatch = incompatible.
    """
    existing_map = {c[0]: c[1] for c in existing_cols}
    for col_name, expected_type in expected_cols:
        if col_name not in existing_map:
            logger.warning(f"Table {table_name}: missing expected column '{col_name}'")
            return False
        actual = existing_map[col_name]
        if not _types_compatible(expected_type, actual):
            logger.warning(f"Table {table_name} column '{col_name}': expected {expected_type}, got {actual}")
            return False
    return True


def _get_existing_tables(session) -> Set[str]:
    """Alias for get_existing_tables (internal use)."""
    return get_existing_tables(session)


def _drop_fk_version() -> List[Tuple[str, str]]:
    """Return (table_name, ddl) for each table. DDL without FK constraints."""
    stmts = [
        ("cwe_entries", "CREATE TABLE IF NOT EXISTS cwe_entries (cwe_id VARCHAR(32) PRIMARY KEY, raw_data JSONB, name TEXT, description TEXT, updated_at TIMESTAMPTZ DEFAULT NOW())"),
        ("capec", "CREATE TABLE IF NOT EXISTS capec (capec_id VARCHAR(32) PRIMARY KEY, name TEXT, description TEXT, related_cwes JSONB, raw_data JSONB, updated_at TIMESTAMPTZ DEFAULT NOW())"),
        ("cwe_to_capec", "CREATE TABLE IF NOT EXISTS cwe_to_capec (cwe_id VARCHAR(32) NOT NULL, capec_id VARCHAR(32) NOT NULL, PRIMARY KEY (cwe_id, capec_id))"),
        ("nvd_cves_by_cwe", "CREATE TABLE IF NOT EXISTS nvd_cves_by_cwe (cwe_id VARCHAR(32) NOT NULL, cve_id VARCHAR(32) NOT NULL, normalized_data JSONB, PRIMARY KEY (cwe_id, cve_id))"),
        ("attack_enterprise_techniques", "CREATE TABLE IF NOT EXISTS attack_enterprise_techniques (technique_id VARCHAR(32) PRIMARY KEY, name TEXT, description TEXT, raw_data JSONB, updated_at TIMESTAMPTZ DEFAULT NOW())"),
        ("cisa_kev", "CREATE TABLE IF NOT EXISTS cisa_kev (cve_id VARCHAR(32) PRIMARY KEY, catalog_date TEXT, raw_data JSONB, updated_at TIMESTAMPTZ DEFAULT NOW())"),
        ("cwe_capec_attack_mappings", """CREATE TABLE IF NOT EXISTS cwe_capec_attack_mappings (
            id SERIAL PRIMARY KEY,
            cwe_id VARCHAR(32) NOT NULL,
            capec_id VARCHAR(32),
            attack_id VARCHAR(32) NOT NULL,
            tactic VARCHAR(64) NOT NULL,
            mapping_basis VARCHAR(32) NOT NULL,
            confidence VARCHAR(16) DEFAULT 'medium',
            example_cves JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (cwe_id, attack_id, tactic)
        )"""),
        ("cwe_technique_mappings", """CREATE TABLE IF NOT EXISTS cwe_technique_mappings (
            cwe_id VARCHAR(32) NOT NULL,
            technique_id VARCHAR(32) NOT NULL,
            tactic VARCHAR(64) NOT NULL,
            confidence VARCHAR(16) DEFAULT 'high',
            mapping_source VARCHAR(64) DEFAULT 'cwe_lookup',
            PRIMARY KEY (cwe_id, technique_id, tactic)
        )"""),
    ]
    return stmts


def create_cwe_threat_intel_tables(session) -> None:
    """
    Create CWE threat intel tables. Idempotent.
    Queries PostgreSQL for existing tables and column schemas first.
    Skips CREATE only when table exists AND has compatible columns (from cve_enrich_pipeline).
    Creates table if missing or schema incompatible (CREATE TABLE IF NOT EXISTS).
    """
    existing_tables = _get_existing_tables(session)
    existing_columns = get_existing_table_columns(session)
    table_ddls = _drop_fk_version()

    for table_name, stmt in table_ddls:
        key = table_name.lower()
        if key not in existing_tables:
            try:
                session.execute(text(stmt))
                logger.info(f"Created table: {table_name}")
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.debug(f"Table {table_name} already exists: {e}")
                else:
                    logger.warning(f"Schema statement failed for {table_name}: {e}")
            continue

        expected = EXPECTED_COLUMNS.get(key)
        existing_cols = existing_columns.get(key, [])
        if expected and existing_cols:
            if _schema_compatible(table_name, existing_cols, expected):
                logger.info(f"Table {table_name} already exists with compatible schema, skipping CREATE")
            else:
                logger.warning(
                    f"Table {table_name} exists but schema differs from expected. "
                    "Using existing table. If inserts fail, check column types."
                )
        else:
            logger.info(f"Table {table_name} already exists, skipping CREATE")

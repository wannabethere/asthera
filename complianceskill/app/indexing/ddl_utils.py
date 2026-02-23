"""
DDL generation and validation for table schemas from MDL.
Mirrors agents/app/indexing/project_reader._build_table_ddl, _build_column_defs, _validate_ddl_syntax
so the same logs appear when indexing in knowledge (project_reader_qdrant).
"""
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def build_column_defs(columns: List[Any], default_type: str = "VARCHAR") -> List[str]:
    """Build column definitions for DDL generation. Same logic and logging as agents _build_column_defs."""
    col_defs = []
    if not columns:
        return []

    logger.debug("_build_column_defs called with %s columns, default_type=%s", len(columns), default_type)
    for i, col in enumerate(columns):
        try:
            logger.debug("Processing column %s: %s", i, col)
            if isinstance(col, dict):
                name = col.get("name", "")
                dtype = col.get("type", default_type)
                comment = col.get("comment", "")
                description = col.get("description", "")
                if "properties" in col and isinstance(col["properties"], dict):
                    if not comment:
                        comment = col["properties"].get("displayName", "")
                    if not description:
                        description = col["properties"].get("description", "")
                    logger.debug(
                        "Column %s properties: comment='%s', description='%s'",
                        col.get("name", ""),
                        (comment[:50] + "..." if len(comment or "") > 50 else (comment or "None")),
                        (description[:50] + "..." if len(description or "") > 50 else (description or "None")),
                    )
                if not comment:
                    comment = (name or "").replace("_", " ").title()
                    logger.debug("Generated comment for column %s: '%s'", name, comment)
                not_null = col.get("notNull", False)
                if not_null and (dtype or "").upper() != "PRIMARY KEY":
                    dtype = (dtype or default_type) + " NOT NULL"
            else:
                name = str(col) if col is not None else ""
                dtype = default_type
                comment = ""

            if not name or not name.strip():
                logger.warning("Skipping column with empty name")
                continue
            if any(c in name for c in ["(", ")", ";", "\n", "\r"]):
                logger.warning("Column name contains problematic characters, skipping: %s", name)
                continue

            col_def = f"{name} {dtype}"
            comment_parts = []
            if comment:
                clean = comment.strip().replace("\n", " ").replace("\r", " ")
                if clean and not clean.startswith("--"):
                    comment_parts.append(clean)
            if description:
                clean = description.strip().replace("\n", " ").replace("\r", " ")
                if clean and not clean.startswith("--"):
                    comment_parts.append(clean)
            if comment_parts:
                col_def += " -- " + " -- ".join(comment_parts)
            logger.debug("Generated column definition: %s", col_def)
            col_defs.append(col_def)
        except Exception as e:
            logger.warning("Error processing column %s (%s): %s", i, col, e)
    return col_defs


def build_table_ddl(table_name: str, description: str, columns: List[Any]) -> str:
    """Build DDL for a single table. Same logic and logging as agents _build_table_ddl."""
    try:
        logger.debug("Building DDL for table %s", table_name)
        logger.debug("Description: %s...", (description[:100] if description else "None"))
        logger.debug("Columns type: %s, length: %s", type(columns), len(columns) if columns else 0)
        logger.debug("Columns sample: %s", (columns[:2] if columns else "None"))

        col_defs = build_column_defs(columns)
        logger.debug("Generated column definitions: %s", col_defs)

        if description:
            clean_description = description.replace("\n", " ").replace("\r", " ").strip()
            clean_description = clean_description.replace("(", "[").replace(")", "]")
            if len(clean_description) > 200:
                clean_description = clean_description[:200] + "..."
            table_comment = f"-- {clean_description}\n"
        else:
            table_comment = ""

        if not table_name:
            logger.warning("No table name provided, skipping DDL generation")
            return ""
        if not col_defs:
            logger.warning("No column definitions for table %s, skipping DDL generation", table_name)
            return ""

        ddl = f"{table_comment}CREATE TABLE {table_name} (\n  " + ",\n  ".join(col_defs) + "\n);"
        logger.info("Generated DDL for %s: %s", table_name, ddl)

        if not validate_ddl_syntax(ddl):
            logger.error("Generated DDL failed syntax validation for table %s", table_name)
            logger.error("Problematic DDL: %s", repr(ddl))
            logger.error("DDL length: %s", len(ddl))
            logger.error("DDL first 200 chars: %s", ddl[:200])
            return ""
        return ddl
    except Exception as e:
        logger.error("Error building table DDL for %s: %s", table_name, e)
        logger.error("Columns that caused error: %s", columns)
        return ""


def validate_ddl_syntax(ddl: str) -> bool:
    """Validate DDL syntax. Same logic as agents _validate_ddl_syntax."""
    try:
        if not ddl or not ddl.strip():
            return False
        if ddl.count("(") != ddl.count(")"):
            logger.error("Unbalanced parentheses in DDL")
            return False
        lines = ddl.split("\n")
        create_table_found = False
        for line in lines:
            line = line.strip()
            if line and not line.startswith("--"):
                if line.upper().startswith("CREATE TABLE"):
                    create_table_found = True
                    break
                break
        if not create_table_found:
            logger.error("DDL does not contain CREATE TABLE statement")
            return False
        if not ddl.strip().endswith(";"):
            logger.error("DDL does not end with semicolon")
            return False
        if "()" in ddl:
            logger.error("DDL contains empty column list")
            return False
        return True
    except Exception as e:
        logger.error("Error validating DDL syntax: %s", e)
        return False


def generate_and_log_table_ddl(mdl_dict: Dict[str, Any], project_id: str = "") -> Dict[str, str]:
    """
    Generate DDL for each model in the MDL and log the same way as agents _generate_table_ddl.
    Returns dict table_name -> ddl. Call from project_reader_qdrant.index_project after parsing MDL.
    """
    logger.info("Starting DDL generation for project: %s", project_id or "unknown")
    table_ddl_map = {}
    try:
        for model in mdl_dict.get("models", []):
            table_name = model.get("name", "")
            if not table_name:
                continue
            logger.info("Generating DDL for table: %s", table_name)

            table_description = model.get("description", "") or (model.get("properties") or {}).get("description", "")
            columns = model.get("columns", [])
            processed_columns = []
            for column in columns:
                column_name = column.get("name", "")
                if not column_name:
                    continue
                properties = column.get("properties", {})
                processed_columns.append({
                    "name": column_name,
                    "type": column.get("type", "VARCHAR"),
                    "comment": properties.get("displayName", ""),
                    "description": properties.get("description", ""),
                    "notNull": column.get("notNull", False),
                    "properties": properties,
                })
                desc = properties.get("description") or ""
                logger.info(
                    "  Column %s: type=%s, display_name='%s', description='%s'",
                    column_name,
                    column.get("type", "VARCHAR"),
                    properties.get("displayName", ""),
                    desc[:50] + "..." if len(desc) > 50 else (desc or "None"),
                )

            ddl = build_table_ddl(table_name=table_name, description=table_description, columns=processed_columns)
            if ddl:
                table_ddl_map[table_name] = ddl
                logger.info("Generated DDL for %s: %s characters", table_name, len(ddl))
                logger.info("DDL preview: %s...", ddl[:200])
            else:
                logger.warning("Failed to generate DDL for table %s", table_name)

        logger.info("DDL generation completed: %s tables processed", len(table_ddl_map))
    except Exception as e:
        logger.exception("Error generating table DDL: %s", e)
    return table_ddl_map

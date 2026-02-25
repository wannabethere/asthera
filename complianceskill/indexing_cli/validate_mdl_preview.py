"""
Validate MDL contextual preview files (mdl_docs).

Checks:
- Required keys in each document (page_content, metadata with source_content_type)
- category in allowed list (cybersecurity categories)
- table_name/column_name reference existing schema when schema is provided
- edge content_types reference valid mdl/schema types

Usage:
    python -m indexing_cli.validate_mdl_preview \
        --preview-dir indexing_preview \
        --mdl-docs-dir mdl_docs

    # With schema reference validation (optional: pass path to table_definitions or MDL)
    python -m indexing_cli.validate_mdl_preview \
        --preview-dir indexing_preview \
        --mdl-file path/to/snyk_mdl.json
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

ALLOWED_CATEGORIES = [
    "access requests",
    "application data",
    "assets",
    "projects",
    "vulnerabilities",
    "integrations",
    "configuration",
    "audit logs",
    "risk management",
    "deployment",
    "groups",
    "organizations",
    "memberships and roles",
    "issues",
    "artifacts",
    "other",
]

VALID_EDGE_CONTENT_TYPES = {
    "table_descriptions",
    "column_definitions",
    "schema_descriptions",
    "mdl_key_concepts",
    "mdl_patterns",
    "mdl_evidences",
    "mdl_fields",
    "mdl_metrics",
    "mdl_edges_table",
    "mdl_edges_column",
}


def load_mdl_tables_columns(mdl_path: Path) -> Tuple[Set[str], Dict[str, Set[str]]]:
    """Load table names and table -> column names from MDL JSON."""
    with open(mdl_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    tables = set()
    table_columns: Dict[str, Set[str]] = {}
    for model in data.get("models", []):
        name = model.get("name", "")
        if not name:
            continue
        tables.add(name)
        table_columns[name] = {c.get("name", "") for c in model.get("columns", []) if c.get("name")}
    return tables, table_columns


def validate_doc(
    doc: Dict[str, Any],
    content_type: str,
    allowed_tables: Optional[Set[str]] = None,
    table_columns: Optional[Dict[str, Set[str]]] = None,
) -> List[str]:
    """Validate one document; return list of error messages."""
    errors = []
    if not isinstance(doc, dict):
        errors.append("document is not a dict")
        return errors
    if not doc.get("page_content"):
        errors.append("missing page_content")
    meta = doc.get("metadata") or {}
    if meta.get("source_content_type") != content_type:
        errors.append(f"metadata.source_content_type should be '{content_type}'")
    category = meta.get("category")
    if category is not None and category not in ALLOWED_CATEGORIES:
        errors.append(f"category '{category}' not in ALLOWED_CATEGORIES")
    if allowed_tables is not None:
        table_name = meta.get("table_name")
        if table_name and table_name not in allowed_tables:
            errors.append(f"table_name '{table_name}' not in MDL")
        if table_columns and table_name:
            col = meta.get("column_name")
            if col and table_name in table_columns and col not in table_columns[table_name]:
                errors.append(f"column_name '{col}' not in table '{table_name}' in MDL")
    if content_type in ("mdl_edges_table", "mdl_edges_column"):
        for ct in meta.get("content_types", []):
            if ct not in VALID_EDGE_CONTENT_TYPES:
                errors.append(f"content_types entry '{ct}' not in VALID_EDGE_CONTENT_TYPES")
    return errors


def validate_file(
    filepath: Path,
    allowed_tables: Optional[Set[str]] = None,
    table_columns: Optional[Dict[str, Set[str]]] = None,
) -> Tuple[int, int, List[str]]:
    """Validate one preview JSON file. Returns (ok_count, error_count, list of error messages)."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return 0, 0, [f"Failed to load file: {e}"]
    if not isinstance(data, dict):
        return 0, 0, ["Top-level value is not a dict"]
    docs = data.get("documents", [])
    if not isinstance(docs, list):
        return 0, 0, ["'documents' is not a list"]
    content_type = data.get("metadata", {}).get("content_type", "")
    if not content_type:
        content_type = filepath.stem
        if content_type.startswith("mdl_"):
            parts = content_type.split("_")
            for i, p in enumerate(parts):
                if len(p) == 8 and p.isdigit():
                    content_type = "_".join(parts[:i])
                    break
    ok, err_count = 0, 0
    all_errors = []
    for i, doc in enumerate(docs):
        errs = validate_doc(doc, content_type, allowed_tables, table_columns)
        if errs:
            err_count += 1
            for e in errs:
                all_errors.append(f"doc[{i}]: {e}")
        else:
            ok += 1
    return ok, err_count, all_errors


def run(
    preview_dir: str,
    mdl_docs_dir: str = "mdl_docs",
    mdl_file: Optional[str] = None,
) -> bool:
    """Run validation. Returns True if all files pass."""
    preview_path = Path(preview_dir)
    mdl_docs_path = preview_path / mdl_docs_dir
    if not mdl_docs_path.exists():
        logger.warning("mdl_docs directory not found: %s", mdl_docs_path)
        return True
    allowed_tables, table_columns = None, None
    if mdl_file and Path(mdl_file).exists():
        allowed_tables, table_columns = load_mdl_tables_columns(Path(mdl_file))
        logger.info("Loaded %s tables from MDL for reference validation", len(allowed_tables))
    total_ok, total_err = 0, 0
    any_fail = False
    for json_file in mdl_docs_path.glob("*.json"):
        if "summary" in json_file.name:
            continue
        ok, err, msgs = validate_file(json_file, allowed_tables, table_columns)
        total_ok += ok
        total_err += err
        if msgs:
            any_fail = True
            logger.error("%s: %s errors", json_file.name, len(msgs))
            for m in msgs[:10]:
                logger.error("  %s", m)
            if len(msgs) > 10:
                logger.error("  ... and %s more", len(msgs) - 10)
        else:
            logger.info("%s: %s documents OK", json_file.name, ok)
    logger.info("Total: %s OK, %s errors", total_ok, total_err)
    return not any_fail


def main():
    parser = argparse.ArgumentParser(description="Validate MDL contextual preview (mdl_docs) files")
    parser.add_argument("--preview-dir", default="indexing_preview", help="Preview root directory")
    parser.add_argument("--mdl-docs-dir", default="mdl_docs", help="Subdirectory name for mdl_docs")
    parser.add_argument("--mdl-file", help="Path to MDL JSON for table/column reference validation")
    args = parser.parse_args()
    ok = run(
        preview_dir=args.preview_dir,
        mdl_docs_dir=args.mdl_docs_dir,
        mdl_file=args.mdl_file,
    )
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()

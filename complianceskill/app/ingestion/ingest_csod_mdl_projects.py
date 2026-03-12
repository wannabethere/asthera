"""
Ingest CSOD MDL project folders into a unified csod_project_metadata.json.

Scans a root directory for folders containing project_metadata.json (e.g. from
CSOD_Learn_mdl_files structure: Assessment & Q&A, Learning & Training subfolders,
Users & HR Management, etc.), loads each project, validates MDL references,
and produces a unified metadata file for Lexy/CCE consumption.

Usage:
    python -m app.ingestion.ingest_csod_mdl_projects --input-dir /path/to/CSOD_Learn_mdl_files
    python app/ingestion/ingest_csod_mdl_projects.py --input-dir /path/to/mdl --output data/csod_project_metadata.json
    python app/ingestion/ingest_csod_mdl_projects.py --input-dir /path/to/mdl --dry-run
"""

from pathlib import Path as _Path
import sys
_script_dir = _Path(__file__).resolve().parent
_project_root = _script_dir.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _slugify(name: str) -> str:
    """Convert folder name to slug for project_id (e.g. 'Assessment & Q&A' -> 'assessment_qa')."""
    s = re.sub(r"[^a-zA-Z0-9\s]", "", name)
    s = re.sub(r"\s+", "_", s.strip().lower())
    return s or "unknown"


def discover_mdl_project_folders(root: Path) -> List[Path]:
    """
    Find all folders containing project_metadata.json.

    Returns list of folder paths (parent of project_metadata.json).
    """
    folders = []
    for p in root.rglob("project_metadata.json"):
        if p.is_file():
            folders.append(p.parent)
    return sorted(set(folders))


def load_project_metadata(metadata_path: Path) -> Optional[Dict[str, Any]]:
    """Load and validate project_metadata.json."""
    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {metadata_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error reading {metadata_path}: {e}")
        return None

    if not isinstance(data, dict):
        logger.error(f"project_metadata.json must be a dict: {metadata_path}")
        return None

    project_id = data.get("project_id")
    if not project_id:
        logger.warning(f"Missing project_id in {metadata_path}, will infer from path")
        # Infer from path: e.g. "Assessment & Q&A/Assessment & Q&A" -> csod_assessment_qa
        parts = metadata_path.parent.parts
        if len(parts) >= 2:
            project_id = f"csod_{_slugify(parts[-1])}"
        else:
            project_id = f"csod_{_slugify(parts[-1]) if parts else 'unknown'}"
        data["project_id"] = project_id

    tables = data.get("tables", [])
    if not tables:
        logger.warning(f"No tables in {metadata_path}")

    return data


def validate_mdl_refs(project: Dict[str, Any], folder: Path) -> Dict[str, Any]:
    """
    Validate that referenced MDL files exist and optionally parse them.
    Returns project with validation info (mdl_files_valid, missing_mdl).
    """
    tables = project.get("tables", [])
    missing = []
    for t in tables:
        if not isinstance(t, dict):
            continue
        mdl_file = t.get("mdl_file")
        if mdl_file:
            mdl_path = folder / mdl_file
            if not mdl_path.exists():
                missing.append(mdl_file)
    project["_validation"] = {
        "mdl_files_valid": len(missing) == 0,
        "missing_mdl": missing,
    }
    return project


def extract_table_schemas(project: Dict[str, Any], folder: Path) -> tuple[Dict[str, Dict[str, str]], str, str]:
    """
    Extract table_schemas (catalog, schema) from MDL files.
    Returns (table_schemas, db_catalog, db_schema).
    db_catalog/db_schema are from first MDL (project-level defaults).
    Aligns with lexy_metadata_registry_design table_schemas / db_schemas.
    """
    table_schemas: Dict[str, Dict[str, str]] = {}
    db_catalog, db_schema = "", ""
    tables = project.get("tables", [])
    for t in tables:
        if not isinstance(t, dict):
            continue
        name = t.get("name", "")
        if not name:
            continue
        mdl_file = t.get("mdl_file", f"{name}.mdl.json")
        mdl_path = folder / mdl_file
        if not mdl_path.exists():
            continue
        try:
            with open(mdl_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        catalog = data.get("catalog")
        schema = data.get("schema")
        models = data.get("models", [])
        if models:
            tr = models[0].get("tableReference") or {}
            catalog = catalog or tr.get("catalog")
            schema = schema or tr.get("schema")
        if catalog or schema:
            table_schemas[name] = {"catalog": catalog or "", "schema": schema or ""}
            if not db_catalog and not db_schema:
                db_catalog = catalog or ""
                db_schema = schema or ""
    return table_schemas, db_catalog, db_schema


def infer_category_path(folder: Path, root: Path) -> tuple[str, str]:
    """
    Infer category and subcategory from folder path relative to root.
    E.g. root/Learning & Training/Transcript & Statuses -> ("Learning & Training", "Transcript & Statuses")
    """
    try:
        rel = folder.relative_to(root)
        parts = rel.parts
        if len(parts) >= 2:
            return parts[0], parts[1]
        if len(parts) == 1:
            return parts[0], parts[0]
    except ValueError:
        pass
    return "unknown", "unknown"


def ingest_projects(
    input_dir: Path,
    validate_mdl: bool = True,
) -> Dict[str, Any]:
    """
    Ingest all CSOD MDL projects from input_dir.

    Returns unified structure:
    {
        "projects": [...],
        "meta": {"source_dir": "...", "project_count": N, "ingested_at": "..."}
    }
    """
    from datetime import datetime

    input_dir = input_dir.resolve()
    if not input_dir.exists() or not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    folders = discover_mdl_project_folders(input_dir)
    if not folders:
        logger.warning(f"No project_metadata.json files found under {input_dir}")
        return {"projects": [], "meta": {"source_dir": str(input_dir), "project_count": 0}}

    projects = []
    for folder in folders:
        metadata_path = folder / "project_metadata.json"
        project = load_project_metadata(metadata_path)
        if not project:
            continue

        category, subcategory = infer_category_path(folder, input_dir)
        project["_source"] = {
            "folder_path": str(folder),
            "category": category,
            "subcategory": subcategory,
        }

        if validate_mdl:
            project = validate_mdl_refs(project, folder)
            if project.get("_validation", {}).get("missing_mdl"):
                logger.warning(
                    f"[{project['project_id']}] Missing MDL files: {project['_validation']['missing_mdl']}"
                )

        table_schemas, db_catalog, db_schema = extract_table_schemas(project, folder)
        if table_schemas:
            project["_source"]["table_schemas"] = table_schemas
            project["_source"]["db_catalog"] = db_catalog
            project["_source"]["db_schema"] = db_schema

        projects.append(project)
        logger.info(f"Ingested: {project['project_id']} ({len(project.get('tables', []))} tables)")

    return {
        "projects": projects,
        "meta": {
            "source_dir": str(input_dir),
            "project_count": len(projects),
            "ingested_at": datetime.utcnow().isoformat() + "Z",
        },
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Ingest CSOD MDL project folders into unified csod_project_metadata.json"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        required=True,
        help="Root directory containing MDL project folders (e.g. CSOD_Learn_mdl_files)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON path (default: data/csod_project_metadata.json relative to complianceskill)",
    )
    parser.add_argument(
        "--no-validate-mdl",
        action="store_true",
        help="Skip validation of MDL file existence",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover and report projects without writing output",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir).resolve()
    if not input_dir.exists():
        logger.error(f"Input directory not found: {input_dir}")
        return 1

    result = ingest_projects(input_dir, validate_mdl=not args.no_validate_mdl)

    if args.dry_run:
        logger.info(f"\n[DRY RUN] Would write {len(result['projects'])} projects")
        for p in result["projects"]:
            logger.info(f"  - {p['project_id']}: {p['_source']['category']}/{p['_source']['subcategory']}")
        return 0

    # Default output: complianceskill/data/csod_project_metadata.json
    if args.output:
        output_path = Path(args.output).resolve()
    else:
        complianceskill_root = Path(__file__).resolve().parent.parent.parent
        output_path = complianceskill_root / "data" / "csod_project_metadata.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Keep folder_path, table_schemas, db_catalog, db_schema for downstream; strip _validation
    output_projects = []
    for p in result["projects"]:
        clean = {k: v for k, v in p.items() if k != "_validation"}
        if "_source" in clean:
            src = clean.pop("_source", {})
            clean["folder_path"] = src.get("folder_path", "")
            clean["category"] = src.get("category", "")
            clean["subcategory"] = src.get("subcategory", "")
            if src.get("table_schemas"):
                clean["table_schemas"] = src["table_schemas"]
            if src.get("db_catalog"):
                clean["db_catalog"] = src["db_catalog"]
            if src.get("db_schema"):
                clean["db_schema"] = src["db_schema"]
        output_projects.append(clean)

    output_data = {
        "projects": output_projects,
        "meta": result["meta"],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    logger.info(f"\nWrote {len(output_projects)} projects to {output_path}")

    # Hook A: push raw L3 table docs (concept_ids=[]; establishes table structure)
    try:
        import importlib.util
        _store_path = _Path(__file__).resolve().parent / "registry_vector_store.py"
        _spec = importlib.util.spec_from_file_location("registry_vector_store", _store_path)
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        _mod.push_mdl_tables_to_store(
            project_metadata=output_data,
            stage="raw",
            dry_run=getattr(args, "dry_run", False),
        )
        logger.info("L3 vector store seeded with raw table structure")
    except Exception as e:
        logger.warning(f"Vector store hook failed (non-blocking): {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

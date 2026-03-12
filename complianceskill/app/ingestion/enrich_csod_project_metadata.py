"""
Enrich csod_project_metadata.json with mdl_tables, table_to_category,
key_columns, and concept_ids using LLM-driven enrichment.

No hardcoded mappings — the MDL Enrichment Engine reads MDL files and
project_metadata.json, then uses LLM to infer all enrichment fields.
Handles new MDLs as they arrive without code changes.

Usage:
    python app/ingestion/enrich_csod_project_metadata.py --input data/csod_project_metadata.json
    python app/ingestion/enrich_csod_project_metadata.py --input in.json --output out.json --method llm
    python app/ingestion/enrich_csod_project_metadata.py --input in.json --method rule-based  # fallback, minimal
"""

import importlib.util
import json
import sys
from pathlib import Path as _Path

# Ensure project root in path when run directly
_script_dir = _Path(__file__).resolve().parent
_project_root = _script_dir.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _ensure_table_schemas(project: Dict[str, Any], folder_path: Path) -> Dict[str, Any]:
    """Ensure table_schemas, db_catalog, db_schema from MDL files if missing."""
    if project.get("table_schemas"):
        return project
    try:
        _engine_path = _Path(__file__).resolve().parent / "mdl_enrichment_engine.py"
        _spec = importlib.util.spec_from_file_location("mdl_enrichment_engine", _engine_path)
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        table_schemas = _mod.extract_table_schemas_from_folder(project, folder_path)
        if table_schemas:
            project["table_schemas"] = table_schemas
            first = next(iter(table_schemas.values()), {})
            project["db_catalog"] = first.get("catalog", "")
            project["db_schema"] = first.get("schema", "")
    except Exception as e:
        logger.debug(f"Could not extract table_schemas: {e}")
    return project


def _rule_based_fallback(project: Dict[str, Any], folder_path: Path) -> Dict[str, Any]:
    """
    Minimal rule-based fallback when LLM is unavailable.
    Infers from MDL structure only — primaryKey, column names.
    """
    enriched = dict(project)
    tables = project.get("tables", [])
    table_names = [t.get("name", "") for t in tables if isinstance(t, dict) and t.get("name")]

    key_columns = {}
    table_to_category = {}
    for t in tables:
        name = t.get("name", "")
        if not name:
            continue
        mdl_file = t.get("mdl_file", f"{name}.mdl.json")
        mdl_path = folder_path / mdl_file
        if mdl_path.exists():
            try:
                with open(mdl_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            models = data.get("models", [])
            if models:
                m = models[0]
                pk = m.get("primaryKey")
                cols = [c.get("name") for c in m.get("columns", []) if isinstance(c, dict) and c.get("name")]
                result = [pk] if pk else []
                for p in ["user_id", "object_id", "reg_num", "completed_date", "due_date", "status"]:
                    if p in cols and p not in result:
                        result.append(p)
                for c in cols[:8]:
                    if c and c not in result:
                        result.append(c)
                key_columns[name] = result[:12]

        # Heuristic categories from table name
        if "_local_core" in name or "type_core" in name:
            table_to_category[name] = []
        elif "transcript" in name or "assignment" in name:
            table_to_category[name] = ["training_completion", "compliance_training"]
        elif "assessment" in name or "qna" in name:
            table_to_category[name] = ["learning_effectiveness", "certification_tracking"]
        elif "scorm" in name:
            table_to_category[name] = ["learning_effectiveness"]
        elif "ilt" in name or "attendance" in name or "instructor" in name:
            table_to_category[name] = ["training_roi"]
        elif "purchase" in name or "finance" in name:
            table_to_category[name] = ["training_roi"]
        elif "user" in name or "ou_core" in name or "user_ou" in name:
            table_to_category[name] = ["user_context"]
        elif "timezone" in name or "currency" in name or "language" in name:
            table_to_category[name] = ["localization"]
        else:
            table_to_category[name] = ["training_completion"]

    primary = [n for n in table_names if not any(x in n for x in ["_local_core", "type_core", "enum"]) and "user_context" not in str(table_to_category.get(n, []))]
    supporting = [n for n in table_names if n not in primary]
    if not primary:
        primary = table_names[:5]
        supporting = table_names[5:]

    enriched["concept_ids"] = ["compliance_training", "learning_effectiveness"]
    enriched["table_to_category"] = table_to_category
    enriched["mdl_tables"] = {"primary": primary, "supporting": supporting, "optional": []}
    enriched["key_columns"] = key_columns
    return enriched


def enrich_project(
    project: Dict[str, Any],
    engine,
    method: str = "llm",
) -> Dict[str, Any]:
    """Enrich a single project using engine (LLM) or rule-based fallback."""
    folder = project.get("folder_path") or project.get("_source", {}).get("folder_path")
    folder_path = Path(folder).resolve() if folder else None

    if method == "llm" and engine:
        result = engine.enrich_project(project, folder_path=folder_path)
    elif folder_path and folder_path.exists():
        result = _rule_based_fallback(project, folder_path)
    else:
        logger.warning(f"No folder_path for {project.get('project_id')}, cannot run rule-based enrichment")
        return dict(project)

    result = _ensure_table_schemas(result, folder_path) if folder_path and folder_path.exists() else result
    result.setdefault("source_id", "cornerstone")
    return result


def enrich_registry(
    input_path: Path,
    output_path: Path,
    method: str = "llm",
) -> Dict[str, Any]:
    """Enrich full csod_project_metadata.json."""
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    projects = data.get("projects", [])
    if not projects:
        logger.warning("No projects in input")
        return data

    engine = None
    if method == "llm":
        try:
            # Import directly to avoid app.ingestion.__init__ (pulls frameworks, yaml, etc.)
            import importlib.util
            _engine_path = _Path(__file__).resolve().parent / "mdl_enrichment_engine.py"
            _spec = importlib.util.spec_from_file_location("mdl_enrichment_engine", _engine_path)
            _mod = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            engine = _mod.MDLEnrichmentEngine()
            logger.info("Using LLM-driven enrichment")
        except Exception as e:
            logger.warning(f"LLM engine unavailable ({e}), falling back to rule-based")
            method = "rule-based"

    enriched_projects = []
    for p in projects:
        ep = enrich_project(p, engine=engine, method=method)
        enriched_projects.append(ep)
        logger.info(f"Enriched: {ep['project_id']} -> concepts={ep.get('concept_ids', [])}")

    result = {
        **data,
        "projects": enriched_projects,
        "meta": {
            **data.get("meta", {}),
            "enriched": True,
            "enrichment_source": "enrich_csod_project_metadata",
            "enrichment_method": method,
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    logger.info(f"Wrote enriched metadata to {output_path}")

    # Hook B: push L1 source concepts to vector store (Option A: never write to source_concept_registry)
    try:
        import importlib.util
        _store_path = _Path(__file__).resolve().parent / "registry_vector_store.py"
        _spec = importlib.util.spec_from_file_location("registry_vector_store", _store_path)
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        src_reg = _mod._load_json(_mod.SOURCE_CONCEPT_REGISTRY_PATH)
        _mod.push_source_concepts_to_store(
            enriched_metadata=result,
            source_concept_registry=src_reg,
            source_id="cornerstone",
        )
        logger.info("L1 vector store updated with enriched concept bindings")
    except Exception as e:
        logger.warning(f"Vector store hook failed (non-blocking): {e}")

    return result


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Enrich csod_project_metadata.json with LLM-driven enrichment"
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to csod_project_metadata.json",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output path (default: input path with _enriched suffix)",
    )
    parser.add_argument(
        "--method",
        type=str,
        choices=["llm", "rule-based"],
        default="llm",
        help="Enrichment method: llm (default) or rule-based fallback",
    )
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        logger.error(f"Input not found: {input_path}")
        return 1

    if args.output:
        output_path = Path(args.output).resolve()
    else:
        output_path = input_path.parent / f"{input_path.stem}_enriched.json"

    enrich_registry(input_path, output_path, method=args.method)
    return 0


if __name__ == "__main__":
    sys.exit(main())

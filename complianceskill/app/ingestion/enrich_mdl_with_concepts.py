"""
Enrich CSOD MDL files with concept_ids and recommendation_area_ids.

Uses the MDL Enrichment Engine to infer concept_ids from MDL content and
project_metadata.json — no hardcoded table mappings. When project_metadata_enriched
is provided, uses its LLM-derived concept_ids. Otherwise, calls the engine
per-project to infer concepts, then annotates MDL files.

Adds to each model in .mdl.json files:
- properties.concept_ids: [concept_id]
- properties.recommendation_area_ids: [area_id] (if concept_recommendation_registry provided)
- columns: concept_id virtual column (if not present)

Usage:
    python app/ingestion/enrich_mdl_with_concepts.py --input-dir /path/to/CSOD_Learn_mdl_files
    python app/ingestion/enrich_mdl_with_concepts.py --input-dir /path/to/mdl --project-metadata data/csod_project_metadata_enriched.json
    python app/ingestion/enrich_mdl_with_concepts.py --input-dir /path/to/mdl  # engine infers concepts
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

CONCEPT_ID_COLUMN = {
    "name": "concept_id",
    "type": "VARCHAR",
    "notNull": False,
    "properties": {
        "description": "Key concept this table row belongs to (semantic routing)",
        "displayName": "Concept ID",
    },
}


def load_json(path: Path) -> Optional[Dict]:
    if not path or not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load {path}: {e}")
        return None


def get_recommendation_areas_for_concepts(
    concept_ids: List[str],
    concept_rec_registry: Dict,
) -> List[str]:
    """Return recommendation area_ids for all given concept_ids."""
    area_ids = []
    recommendations = concept_rec_registry.get("concept_recommendations", {})
    for concept_id in concept_ids:
        areas = recommendations.get(concept_id, {}).get("recommendation_areas", [])
        area_ids.extend(a.get("area_id", "") for a in areas if a.get("area_id"))
    return list(dict.fromkeys(area_ids))


def build_project_id_to_concepts(project_metadata: Dict) -> Dict[str, List[str]]:
    """Build mapping project_id -> concept_ids from enriched project metadata."""
    result = {}
    for p in project_metadata.get("projects", []):
        project_id = p.get("project_id", "")
        concepts = p.get("concept_ids", [])
        if project_id and concepts:
            result[project_id] = concepts
    return result


def has_concept_column(columns: List[Dict]) -> bool:
    for c in columns:
        if isinstance(c, dict) and c.get("name") == "concept_id":
            return True
    return False


def enrich_model(
    model: Dict[str, Any],
    concept_ids: List[str],
    recommendation_area_ids: List[str],
) -> Dict[str, Any]:
    """Add concept annotations to a single MDL model."""
    enriched = dict(model)
    props = dict(enriched.get("properties", {}))
    props["concept_ids"] = concept_ids
    props["recommendation_area_ids"] = recommendation_area_ids
    enriched["properties"] = props

    columns = list(enriched.get("columns", []))
    if not has_concept_column(columns):
        columns.append(CONCEPT_ID_COLUMN)
        enriched["columns"] = columns

    return enriched


def enrich_mdl_file(
    mdl_path: Path,
    concept_ids: List[str],
    recommendation_area_ids: List[str],
    dry_run: bool = False,
) -> bool:
    """Enrich a single MDL file. Returns True if modified."""
    try:
        with open(mdl_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Could not read {mdl_path}: {e}")
        return False

    models = data.get("models", [])
    if not models:
        return False

    modified = False
    for i, model in enumerate(models):
        if not isinstance(model, dict):
            continue
        enriched = enrich_model(model, concept_ids, recommendation_area_ids)
        if enriched != model:
            models[i] = enriched
            modified = True

    if modified and not dry_run:
        with open(mdl_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Enriched: {mdl_path.name} -> concepts={concept_ids}")
    elif modified and dry_run:
        logger.info(f"[dry-run] Would enrich: {mdl_path.name} -> concepts={concept_ids}")

    return modified


def discover_project_folders(root: Path) -> List[Path]:
    """Find all folders containing project_metadata.json."""
    folders = []
    for p in root.rglob("project_metadata.json"):
        if p.is_file():
            folders.append(p.parent)
    return sorted(set(folders))


def _infer_concepts_with_engine(project: Dict, folder: Path) -> List[str]:
    """Use MDL Enrichment Engine to infer concept_ids for a project."""
    try:
        _engine_path = _Path(__file__).resolve().parent / "mdl_enrichment_engine.py"
        _spec = importlib.util.spec_from_file_location("mdl_enrichment_engine", _engine_path)
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        engine = _mod.MDLEnrichmentEngine()
        enriched = engine.enrich_project(project, folder_path=folder)
        return enriched.get("concept_ids", [])
    except Exception as e:
        logger.warning(f"Engine inference failed for {folder}: {e}")
        return []


def enrich_mdl_files(
    input_dir: Path,
    project_metadata: Optional[Dict] = None,
    concept_rec_registry: Optional[Dict] = None,
    use_engine_when_no_metadata: bool = True,
    dry_run: bool = False,
) -> Dict[str, int]:
    """
    Enrich all MDL files under input_dir.

    - If project_metadata provided: uses concept_ids from enriched metadata.
    - Else if use_engine_when_no_metadata: calls MDL Enrichment Engine per project.
    - Else: skips (no concept source).
    """
    input_dir = input_dir.resolve()
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    project_id_to_concepts = build_project_id_to_concepts(project_metadata) if project_metadata else {}
    folders = discover_project_folders(input_dir)
    if not folders:
        logger.warning(f"No project_metadata.json found under {input_dir}")
        return {"enriched_count": 0, "skipped_count": 0, "error_count": 0}

    enriched_count = 0
    skipped_count = 0
    error_count = 0

    for folder in folders:
        proj_meta_path = folder / "project_metadata.json"
        proj_meta = load_json(proj_meta_path)
        if not proj_meta:
            skipped_count += 1
            continue

        project_id = proj_meta.get("project_id", "")
        concept_ids = project_id_to_concepts.get(project_id, [])

        if not concept_ids and use_engine_when_no_metadata:
            # Infer via engine from MDL content + project metadata
            project_with_path = dict(proj_meta, folder_path=str(folder))
            concept_ids = _infer_concepts_with_engine(project_with_path, folder)

        if not concept_ids:
            logger.debug(f"No concepts for {folder}, skipping")
            skipped_count += 1
            continue

        recommendation_area_ids = []
        if concept_rec_registry:
            recommendation_area_ids = get_recommendation_areas_for_concepts(
                concept_ids, concept_rec_registry
            )

        mdl_files = list(folder.glob("*.mdl.json"))
        for mdl_path in mdl_files:
            try:
                if enrich_mdl_file(
                    mdl_path,
                    concept_ids,
                    recommendation_area_ids,
                    dry_run=dry_run,
                ):
                    enriched_count += 1
            except Exception as e:
                logger.error(f"Error enriching {mdl_path}: {e}")
                error_count += 1

    # Hook C: push enriched L3 table docs (concept_ids now populated)
    try:
        from app.ingestion.registry_vector_store import push_mdl_tables_to_store
        push_mdl_tables_to_store(
            project_metadata=project_metadata,
            input_dir=input_dir,
            stage="enriched",
            dry_run=dry_run,
            concept_rec_registry=concept_rec_registry,
        )
        logger.info("L3 vector store updated with concept annotations")
    except Exception as e:
        logger.warning(f"Vector store hook failed (non-blocking): {e}")

    return {
        "enriched_count": enriched_count,
        "skipped_count": skipped_count,
        "error_count": error_count,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Enrich CSOD MDL files with concept_ids (LLM-driven or from enriched metadata)"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        required=True,
        help="Root directory containing MDL project folders",
    )
    parser.add_argument(
        "--project-metadata",
        type=str,
        default=None,
        help="Path to csod_project_metadata_enriched.json (optional; engine infers if omitted)",
    )
    parser.add_argument(
        "--concept-rec-registry",
        type=str,
        default=None,
        help="Path to concept_recommendation_registry.json (for recommendation_area_ids)",
    )
    parser.add_argument(
        "--no-engine-fallback",
        action="store_true",
        help="Do not use engine when project-metadata not provided",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be done without modifying files",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir).resolve()
    if not input_dir.exists():
        logger.error(f"Input directory not found: {input_dir}")
        return 1

    project_metadata = load_json(Path(args.project_metadata)) if args.project_metadata else None
    concept_rec_registry = (
        load_json(Path(args.concept_rec_registry)) if args.concept_rec_registry else None
    )

    if not project_metadata and args.no_engine_fallback:
        logger.warning("No project-metadata and --no-engine-fallback: no concept source")

    stats = enrich_mdl_files(
        input_dir,
        project_metadata=project_metadata,
        concept_rec_registry=concept_rec_registry,
        use_engine_when_no_metadata=not args.no_engine_fallback,
        dry_run=args.dry_run,
    )

    logger.info(
        f"\nEnrichment complete: {stats['enriched_count']} enriched, "
        f"{stats['skipped_count']} skipped, {stats['error_count']} errors"
    )
    return 0 if stats["error_count"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

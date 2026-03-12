"""
Single script to ingest all CSOD registry data into the vector store collections.

Orchestrates the full pipeline (ingest → enrich → enrich MDL → enrich registries)
and pushes L1, L2, L3 to Qdrant. Can also run in push-only mode using existing files.

Collections written:
    csod_l1_source_concepts       — concept → project_ids, mdl_table_refs (from enriched metadata)
    csod_l2_recommendation_areas  — concept → recommendation areas (from concept_recommendation_registry)
    csod_l3_mdl_tables           — MDL table models per project (from enriched metadata + .mdl.json)
    csod_metrics_registry        — metrics from preview_out/metrics/ (with --all or --preview-dir)

Usage:
    # Push from existing files (default paths)
    python app/ingestion/ingest_registry_vector_store.py

    # Push with custom paths
    python app/ingestion/ingest_registry_vector_store.py \
      --enriched data/csod_project_metadata_enriched.json \
      --source-registry registries/source_concept_registry.json \
      --concept-rec-registry registries/concept_recommendation_registry.json

    # Full pipeline: ingest → enrich → enrich MDL → push
    python app/ingestion/ingest_registry_vector_store.py \
      --input-dir /path/to/CSOD_Learn_mdl_files \
      --run-full-pipeline

    # Dry run (no Qdrant writes)
    python app/ingestion/ingest_registry_vector_store.py --dry-run

    # From preview output folder
    python app/ingestion/ingest_registry_vector_store.py \
      --enriched preview_out/data/csod_project_metadata_enriched.json \
      --source-registry preview_out/registries/source_concept_registry.json \
      --concept-rec-registry preview_out/registries/concept_recommendation_registry.json

    # Ingest ALL from preview_out (L1, L2, L3 + metrics)
    python app/ingestion/ingest_registry_vector_store.py --all
    python app/ingestion/ingest_registry_vector_store.py --preview-dir preview_out
"""

from pathlib import Path as _Path
import sys

_script_dir = _Path(__file__).resolve().parent
_project_root = _script_dir.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

REPO_ROOT = _Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data"
REGISTRIES_DIR = REPO_ROOT / "registries"
DEFAULT_METADATA = DATA_DIR / "csod_project_metadata.json"
DEFAULT_ENRICHED = DATA_DIR / "csod_project_metadata_enriched.json"
DEFAULT_SOURCE_REGISTRY = REGISTRIES_DIR / "source_concept_registry.json"
DEFAULT_CONCEPT_REC_REGISTRY = REGISTRIES_DIR / "concept_recommendation_registry.json"


def _load_store():
    """Load registry_vector_store via importlib to avoid app.ingestion deps."""
    import importlib.util
    _store_path = _Path(__file__).resolve().parent / "registry_vector_store.py"
    _spec = importlib.util.spec_from_file_location("registry_vector_store", _store_path)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    return _mod


def _load_json(path: Path) -> Dict:
    if not path or not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_ingest(input_dir: Path, output_path: Path) -> Dict[str, Any]:
    """Step 1: Ingest MDL projects."""
    import importlib.util
    _ingest_path = _Path(__file__).resolve().parent / "ingest_csod_mdl_projects.py"
    _spec = importlib.util.spec_from_file_location("ingest_csod_mdl_projects", _ingest_path)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    result = _mod.ingest_projects(input_dir, validate_mdl=True)
    projects = []
    for p in result.get("projects", []):
        src = p.get("_source", p)
        clean = {k: v for k, v in p.items() if k != "_validation"}
        if "_source" in clean:
            clean.pop("_source", None)
        clean["folder_path"] = src.get("folder_path", "")
        clean["category"] = src.get("category", "")
        clean["subcategory"] = src.get("subcategory", "")
        if src.get("table_schemas"):
            clean["table_schemas"] = src["table_schemas"]
        if src.get("db_catalog"):
            clean["db_catalog"] = src["db_catalog"]
        if src.get("db_schema"):
            clean["db_schema"] = src["db_schema"]
        projects.append(clean)
    out = {"projects": projects, "meta": result.get("meta", {})}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    logger.info(f"Ingested {len(projects)} projects -> {output_path}")
    return out


def run_enrich_metadata(input_path: Path, output_path: Path) -> Dict[str, Any]:
    """Step 2: Enrich metadata with concepts, mdl_tables, etc."""
    import importlib.util
    _enrich_path = _Path(__file__).resolve().parent / "enrich_csod_project_metadata.py"
    _spec = importlib.util.spec_from_file_location("enrich_csod_project_metadata", _enrich_path)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    return _mod.enrich_registry(input_path, output_path, method="llm")


def run_enrich_mdl(
    input_dir: Path,
    project_metadata: Dict,
    concept_rec_registry: Optional[Dict],
) -> Dict[str, int]:
    """Step 3: Enrich MDL files with concept_ids."""
    import importlib.util
    _enrich_mdl_path = _Path(__file__).resolve().parent / "enrich_mdl_with_concepts.py"
    _spec = importlib.util.spec_from_file_location("enrich_mdl_with_concepts", _enrich_mdl_path)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    return _mod.enrich_mdl_files(
        input_dir,
        project_metadata=project_metadata,
        concept_rec_registry=concept_rec_registry,
        use_engine_when_no_metadata=False,
        dry_run=False,
    )


def run_enrich_registries(enriched_path: Path, enrich_source_map: bool = True) -> None:
    """Step 4 (optional): Enrich concept_recommendation_registry and source_concept_map."""
    import importlib.util
    _enrich_reg_path = _Path(__file__).resolve().parent / "enrich_registries_with_llm.py"
    _spec = importlib.util.spec_from_file_location("enrich_registries_with_llm", _enrich_reg_path)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    _mod.enrich_concept_recommendation_registry(
        enriched_path,
        _mod.SOURCE_CONCEPT_REGISTRY_PATH,
        _mod.CONCEPT_REC_REGISTRY_PATH,
        dry_run=False,
    )
    if enrich_source_map:
        enriched = _load_json(enriched_path)
        src_reg = _load_json(_mod.SOURCE_CONCEPT_REGISTRY_PATH)
        src_reg = _mod.enrich_source_concept_map(enriched, src_reg)
        with open(_mod.SOURCE_CONCEPT_REGISTRY_PATH, "w", encoding="utf-8") as f:
            json.dump(src_reg, f, indent=2, ensure_ascii=False)
        logger.info("Updated source_concept_map in source_concept_registry.json")


def push_to_store(
    enriched_metadata: Dict,
    source_registry: Dict,
    concept_rec_registry: Dict,
    dry_run: bool = False,
) -> Dict[str, int]:
    """Push L1, L2, L3 to vector store."""
    store = _load_store()
    counts = {}

    # L1
    texts, payloads = store._build_l1_from_enriched_metadata(
        enriched_metadata, source_registry, "cornerstone"
    )
    if texts:
        client = None if dry_run else store._get_qdrant_client()
        n = store._upsert_batch(client, store.L1_COLLECTION, texts, payloads, dry_run)
        counts["l1"] = len(texts) if dry_run else n
    else:
        logger.warning("No L1 docs — enriched_metadata may lack concept_ids")
        counts["l1"] = 0

    # L2
    texts, payloads = store._build_l2_from_registry(concept_rec_registry, source_registry)
    if texts:
        client = None if dry_run else store._get_qdrant_client()
        n = store._upsert_batch(client, store.L2_COLLECTION, texts, payloads, dry_run)
        counts["l2"] = len(texts) if dry_run else n
    else:
        logger.warning("No L2 docs — concept_recommendation_registry may lack recommendation_areas")
        counts["l2"] = 0

    # L3 (enriched stage: read .mdl.json for concept_ids)
    texts, payloads = store._build_l3_from_metadata(
        enriched_metadata, "cornerstone", read_mdl_files=True
    )
    if texts:
        client = None if dry_run else store._get_qdrant_client()
        n = store._upsert_batch(client, store.L3_COLLECTION, texts, payloads, dry_run)
        counts["l3"] = len(texts) if dry_run else n
    else:
        logger.warning("No L3 docs — enriched_metadata may lack projects with mdl_tables")
        counts["l3"] = 0

    return counts


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Ingest all CSOD registry data into vector store (L1, L2, L3)"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default=None,
        help="Root directory containing MDL project folders (for --run-full-pipeline)",
    )
    parser.add_argument(
        "--run-full-pipeline",
        action="store_true",
        help="Run ingest → enrich metadata → enrich MDL → push (requires --input-dir)",
    )
    parser.add_argument(
        "--enrich-registries",
        action="store_true",
        help="Run LLM enrich on concept_recommendation_registry before push (requires API key)",
    )
    parser.add_argument(
        "--metadata",
        type=str,
        default=None,
        help=f"Path to csod_project_metadata.json (default: {DEFAULT_METADATA})",
    )
    parser.add_argument(
        "--enriched",
        type=str,
        default=None,
        help=f"Path to csod_project_metadata_enriched.json (default: {DEFAULT_ENRICHED})",
    )
    parser.add_argument(
        "--source-registry",
        type=str,
        default=None,
        help=f"Path to source_concept_registry.json (default: {DEFAULT_SOURCE_REGISTRY})",
    )
    parser.add_argument(
        "--concept-rec-registry",
        type=str,
        default=None,
        help=f"Path to concept_recommendation_registry.json (default: {DEFAULT_CONCEPT_REC_REGISTRY})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would be written without calling Qdrant",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Ingest all from preview_out: L1, L2, L3 + metrics registry",
    )
    parser.add_argument(
        "--preview-dir",
        type=str,
        default=None,
        help="Preview output directory (ingests data/, registries/, metrics/). Default with --all: preview_out",
    )
    args = parser.parse_args()

    # --all or --preview-dir: ingest everything from preview folder
    preview_dir = None
    if args.all or args.preview_dir:
        preview_dir = Path(args.preview_dir or "preview_out").resolve()
        if not preview_dir.exists():
            logger.error(f"Preview directory not found: {preview_dir}")
            return 1
        enriched_path = preview_dir / "data" / "csod_project_metadata_enriched.json"
        source_reg_path = preview_dir / "registries" / "source_concept_registry.json"
        concept_rec_path = preview_dir / "registries" / "concept_recommendation_registry.json"
        metadata_path = preview_dir / "data" / "csod_project_metadata.json"
    else:
        metadata_path = Path(args.metadata or str(DEFAULT_METADATA)).resolve()
        enriched_path = Path(args.enriched or str(DEFAULT_ENRICHED)).resolve()
        source_reg_path = Path(args.source_registry or str(DEFAULT_SOURCE_REGISTRY)).resolve()
        concept_rec_path = Path(args.concept_rec_registry or str(DEFAULT_CONCEPT_REC_REGISTRY)).resolve()

    if args.run_full_pipeline:
        input_dir = Path(args.input_dir).resolve() if args.input_dir else None
        if not input_dir or not input_dir.exists():
            logger.error("--run-full-pipeline requires --input-dir pointing to MDL project root")
            return 1
        logger.info("Running full pipeline: ingest → enrich → enrich MDL → push")
        run_ingest(input_dir, metadata_path)
        run_enrich_metadata(metadata_path, enriched_path)
        if args.enrich_registries:
            run_enrich_registries(enriched_path, enrich_source_map=True)
        enriched_metadata = _load_json(enriched_path)
        run_enrich_mdl(
            input_dir,
            enriched_metadata,
            _load_json(concept_rec_path) if concept_rec_path.exists() else None,
        )
    else:
        if not enriched_path.exists():
            logger.error(f"Enriched metadata not found: {enriched_path}")
            logger.info("Run with --run-full-pipeline --input-dir /path/to/mdl to generate")
            return 1
        enriched_metadata = _load_json(enriched_path)

    if not source_reg_path.exists():
        logger.error(f"Source concept registry not found: {source_reg_path}")
        return 1
    source_registry = _load_json(source_reg_path)

    concept_rec_registry = _load_json(concept_rec_path) if concept_rec_path.exists() else {}
    if not concept_rec_registry.get("concept_recommendations") and not args.dry_run:
        logger.warning(
            "concept_recommendation_registry has no concept_recommendations — L2 will be empty. "
            "Run enrich_registries_with_llm.py to populate."
        )

    counts = push_to_store(
        enriched_metadata,
        source_registry,
        concept_rec_registry,
        dry_run=args.dry_run,
    )

    # Metrics ingestion from preview_dir/metrics/
    if preview_dir and not args.dry_run:
        metrics_dir = preview_dir / "metrics"
        if metrics_dir.exists():
            logger.info(f"Ingesting metrics from {metrics_dir}")
            try:
                try:
                    from app.storage.collections import MDLCollections
                    metrics_coll = MDLCollections.CSOD_METRICS_REGISTRY
                except ImportError:
                    metrics_coll = "csod_metrics_registry"
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "app.ingestion.ingest_metrics_registry",
                        "--metrics-dir",
                        str(metrics_dir),
                        "--collection-name",
                        metrics_coll,
                    ],
                    cwd=str(REPO_ROOT),
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    logger.info("Metrics ingestion complete")
                else:
                    logger.warning(f"Metrics ingestion failed: {result.stderr or result.stdout}")
            except Exception as e:
                logger.warning(f"Metrics ingestion failed (non-blocking): {e}")

    logger.info(
        f"Vector store ingest complete — L1: {counts['l1']}  L2: {counts['l2']}  L3: {counts['l3']}"
        + (" (dry-run)" if args.dry_run else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

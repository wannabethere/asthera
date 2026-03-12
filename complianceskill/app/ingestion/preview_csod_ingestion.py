"""
Preview CSOD ingestion into vector store and registry structure.

Runs ingest + enrich (or loads from files) filtered by category, then shows
what would be written to registries/, data/, and L1/L2/L3 collections —
without calling Qdrant or modifying files.

Usage:
    python app/ingestion/preview_csod_ingestion.py --input-dir /path/to/CSOD_Learn_mdl_files
    python app/ingestion/preview_csod_ingestion.py --input-dir /path/to/mdl --categories "Assessment & Q&A" "Custom Fields (CF)" "Learning & Training" "Localization & Metadata"
    python app/ingestion/preview_csod_ingestion.py --metadata data/csod_project_metadata.json --enriched data/csod_project_metadata_enriched.json --categories "Assessment & Q&A"
    python app/ingestion/preview_csod_ingestion.py --input-dir /path/to/mdl --output preview_out  # creates output folder structure
"""

from pathlib import Path as _Path
import sys
_script_dir = _Path(__file__).resolve().parent
_project_root = _script_dir.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Categories to include (matches design doc structure)
DEFAULT_CATEGORIES = {
    "Assessment & Q&A",
    "Custom Fields (CF)",
    "Learning & Training",
    "Localization & Metadata",
}


def load_or_ingest(
    input_dir: Optional[Path],
    metadata_path: Optional[Path],
    categories: Set[str],
) -> Dict[str, Any]:
    """Load from metadata file or run ingest, then filter by category."""
    if metadata_path and metadata_path.exists():
        with open(metadata_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    elif input_dir and input_dir.exists():
        import importlib.util
        _ingest_path = _Path(__file__).resolve().parent / "ingest_csod_mdl_projects.py"
        _spec = importlib.util.spec_from_file_location("ingest_csod_mdl_projects", _ingest_path)
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        result = _mod.ingest_projects(input_dir, validate_mdl=True)
        projects = []
        for p in result.get("projects", []):
            src = p.get("_source", p)
            cat = src.get("category", p.get("category", ""))
            proj = {k: v for k, v in p.items() if k != "_validation"}
            proj["folder_path"] = src.get("folder_path", "")
            proj["category"] = cat
            proj["subcategory"] = src.get("subcategory", cat)
            if src.get("table_schemas"):
                proj["table_schemas"] = src["table_schemas"]
            if src.get("db_catalog"):
                proj["db_catalog"] = src["db_catalog"]
            if src.get("db_schema"):
                proj["db_schema"] = src["db_schema"]
            projects.append(proj)
        data = {"projects": projects, "meta": result.get("meta", {})}
    else:
        raise FileNotFoundError("Provide --input-dir or --metadata")

    # Filter by category
    filtered = [p for p in data.get("projects", []) if p.get("category") in categories]
    return {
        **data,
        "projects": filtered,
        "meta": {**data.get("meta", {}), "project_count": len(filtered), "categories": list(categories)},
    }


def load_or_enrich(
    project_metadata: Dict[str, Any],
    enriched_path: Optional[Path],
    input_dir: Optional[Path],
    categories: Set[str],
) -> Dict[str, Any]:
    """Load enriched from file or run enrich on project metadata."""
    if enriched_path and enriched_path.exists():
        with open(enriched_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Filter to same categories as project_metadata
        filtered = [p for p in data.get("projects", []) if p.get("category") in categories]
        return {**data, "projects": filtered}
    # Run enrich (rule-based to avoid LLM)
    import importlib.util
    _engine_path = _Path(__file__).resolve().parent / "enrich_csod_project_metadata.py"
    _spec = importlib.util.spec_from_file_location("enrich_csod_project_metadata", _engine_path)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    # Build temp input for enrich_registry
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
        json.dump(project_metadata, tf, indent=2)
        tmp_in = Path(tf.name)
    try:
        out = tmp_in.parent / "preview_enriched.json"
        result = _mod.enrich_registry(tmp_in, out, method="rule-based")
        return result
    finally:
        tmp_in.unlink(missing_ok=True)
        (tmp_in.parent / "preview_enriched.json").unlink(missing_ok=True)


def build_preview(
    enriched_metadata: Dict[str, Any],
    input_dir: Optional[Path],
) -> Dict[str, Any]:
    """Build L1/L2/L3 payload counts and structure preview."""
    import importlib.util
    _store_path = _Path(__file__).resolve().parent / "registry_vector_store.py"
    _spec = importlib.util.spec_from_file_location("registry_vector_store", _store_path)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)

    src_reg = _mod._load_json(_mod.SOURCE_CONCEPT_REGISTRY_PATH)
    rec_reg = _mod._load_json(_mod.CONCEPT_REC_REGISTRY_PATH)

    l1_texts, l1_payloads = _mod._build_l1_from_enriched_metadata(
        enriched_metadata, src_reg, "cornerstone"
    )
    l2_texts, l2_payloads = _mod._build_l2_from_registry(rec_reg, src_reg)
    l3_texts, l3_payloads = _mod._build_l3_from_metadata(
        enriched_metadata, "cornerstone", read_mdl_files=bool(input_dir and Path(input_dir).exists())
    )

    # Build mdl_schemas structure (CSOD projects by category)
    mdl_schemas: Dict[str, List[str]] = {}
    for p in enriched_metadata.get("projects", []):
        cat = p.get("category", "unknown")
        pid = p.get("project_id", "")
        if cat not in mdl_schemas:
            mdl_schemas[cat] = []
        mdl_schemas[cat].append(pid)

    return {
        "l1_count": len(l1_payloads),
        "l1_sample": [{"concept_id": p.get("concept_id"), "project_ids": p.get("project_ids", [])} for p in l1_payloads[:5]],
        "l2_count": len(l2_payloads),
        "l2_sample": [{"concept_id": p.get("concept_id"), "area_id": p.get("area_id")} for p in l2_payloads[:5]],
        "l3_count": len(l3_payloads),
        "l3_sample": [
            {
                "table_name": p.get("table_name"),
                "qualified_table_name": p.get("qualified_table_name"),
                "project_id": p.get("project_id"),
                "concept_ids": p.get("concept_ids", []),
            }
            for p in l3_payloads[:8]
        ],
        "mdl_schemas": mdl_schemas,
        "projects": [
            {
                "project_id": p.get("project_id"),
                "category": p.get("category"),
                "subcategory": p.get("subcategory"),
                "table_count": len(
                    (p.get("mdl_tables") or {}).get("primary", [])
                    + (p.get("mdl_tables") or {}).get("supporting", [])
                    + (p.get("mdl_tables") or {}).get("optional", [])
                ) or len(p.get("tables", [])),
            }
            for p in enriched_metadata.get("projects", [])
        ],
    }


def _enrich_source_concept_map(enriched_metadata: Dict, source_concept_registry: Dict) -> Dict:
    """Build source_concept_map from enriched metadata (concept -> mdl_table_refs, project_ids)."""
    cornerstone = source_concept_registry.setdefault("source_concept_map", {}).setdefault("cornerstone", {})
    for project in enriched_metadata.get("projects", []):
        pid = project.get("project_id", "")
        concept_ids = project.get("concept_ids", [])
        mdl_tables = project.get("mdl_tables", {})
        table_refs = (
            mdl_tables.get("primary", [])
            + mdl_tables.get("supporting", [])
            + mdl_tables.get("optional", [])
        )
        for cid in concept_ids:
            entry = cornerstone.get(cid) or {
                "api_categories": [],
                "mdl_table_refs": [],
                "project_ids": [],
                "coverage_confidence": 0.85,
                "coverage_notes": "",
            }
            entry["mdl_table_refs"] = list(set(entry.get("mdl_table_refs", [])) | set(table_refs))
            entry["project_ids"] = list(set(entry.get("project_ids", [])) | {pid})
            cornerstone[cid] = entry
    return source_concept_registry


def write_output_folder(
    output_dir: Path,
    project_metadata: Dict[str, Any],
    enriched_metadata: Dict[str, Any],
    preview: Dict[str, Any],
    copy_mdl: bool = False,
    enrich_registries: bool = False,
) -> None:
    """Create output folder structure: registries/, data/, mdl_schemas/."""
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # data/
    data_dir = output_dir / "data"
    data_dir.mkdir(exist_ok=True)
    with open(data_dir / "csod_project_metadata.json", "w", encoding="utf-8") as f:
        json.dump(project_metadata, f, indent=2, ensure_ascii=False)
    with open(data_dir / "csod_project_metadata_enriched.json", "w", encoding="utf-8") as f:
        json.dump(enriched_metadata, f, indent=2, ensure_ascii=False)

    # registries/
    reg_dir = output_dir / "registries"
    reg_dir.mkdir(exist_ok=True)
    import importlib.util
    _store_path = _Path(__file__).resolve().parent / "registry_vector_store.py"
    _spec = importlib.util.spec_from_file_location("registry_vector_store", _store_path)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    for name, path in [
        ("source_concept_registry.json", _mod.SOURCE_CONCEPT_REGISTRY_PATH),
        ("concept_recommendation_registry.json", _mod.CONCEPT_REC_REGISTRY_PATH),
    ]:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                reg_data = json.load(f)
            if enrich_registries and name == "source_concept_registry.json":
                reg_data = _enrich_source_concept_map(enriched_metadata, reg_data)
            with open(reg_dir / name, "w", encoding="utf-8") as f:
                json.dump(reg_data, f, indent=2, ensure_ascii=False)
        else:
            with open(reg_dir / name, "w", encoding="utf-8") as f:
                json.dump({"_meta": {"preview": True, "source": str(path)}}, f, indent=2)

    # mdl_schemas/<category>/<project_id>/
    mdl_dir = output_dir / "mdl_schemas"
    mdl_dir.mkdir(exist_ok=True)
    project_by_id = {p["project_id"]: p for p in enriched_metadata.get("projects", [])}

    for cat, pids in sorted(preview.get("mdl_schemas", {}).items()):
        cat_dir = mdl_dir / cat.replace("/", "_")
        cat_dir.mkdir(exist_ok=True)
        for pid in sorted(pids):
            proj_dir = cat_dir / pid
            proj_dir.mkdir(exist_ok=True)
            if copy_mdl:
                proj = project_by_id.get(pid, {})
                folder = Path(proj.get("folder_path", ""))
                if folder.exists():
                    import shutil
                    for f in folder.glob("*.mdl.json"):
                        shutil.copy(f, proj_dir / f.name)
                    if not list(proj_dir.glob("*.mdl.json")):
                        (proj_dir / ".gitkeep").touch()
                else:
                    (proj_dir / ".gitkeep").touch()
            else:
                (proj_dir / ".gitkeep").touch()

    logger.info(f"Created output folder: {output_dir}" + (" (with MDL files)" if copy_mdl else ""))


def print_preview(preview: Dict[str, Any], project_root: Path) -> None:
    """Print preview in design doc format."""
    print("\n" + "=" * 60)
    print("CSOD Ingestion Preview — Registry & Vector Store Structure")
    print("=" * 60)
    print("""
registries/
  source_concept_registry.json          ← key_concepts seed
  concept_recommendation_registry.json  ← concept → recommendation_areas

data/
  csod_project_metadata.json
  csod_project_metadata_enriched.json

mdl_schemas/  (CSOD projects by category)
""")
    for cat, pids in sorted(preview.get("mdl_schemas", {}).items()):
        print(f"  {cat}/")
        for pid in sorted(pids):
            print(f"    {pid}/")
            print(f"      *.mdl.json")
        print()

    print("Vector store (would be written):")
    print(f"  L1 (csod_l1_source_concepts):     {preview['l1_count']} docs")
    if preview.get("l1_sample"):
        for s in preview["l1_sample"]:
            print(f"    - {s['concept_id']} → project_ids: {s['project_ids'][:5]}{'...' if len(s.get('project_ids', [])) > 5 else ''}")
    print(f"  L2 (csod_l2_recommendation_areas): {preview['l2_count']} docs")
    if preview.get("l2_sample"):
        for s in preview["l2_sample"]:
            print(f"    - {s['concept_id']} / {s['area_id']}")
    print(f"  L3 (csod_l3_mdl_tables):         {preview['l3_count']} docs")
    if preview.get("l3_sample"):
        for s in preview["l3_sample"]:
            print(f"    - {s['qualified_table_name'] or s['table_name']} ({s['project_id']}) concepts: {s['concept_ids'][:3]}")

    print("\nProjects included:")
    for p in preview.get("projects", []):
        print(f"  - {p['project_id']}: {p['category']}/{p['subcategory']} ({p['table_count']} tables)")

    print("\n" + "=" * 60)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Preview CSOD ingestion into vector store (no writes)"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default=None,
        help="Root directory containing MDL project folders",
    )
    parser.add_argument(
        "--metadata",
        type=str,
        default=None,
        help="Path to csod_project_metadata.json (skip ingest)",
    )
    parser.add_argument(
        "--enriched",
        type=str,
        default=None,
        help="Path to csod_project_metadata_enriched.json (skip enrich)",
    )
    parser.add_argument(
        "--categories",
        type=str,
        nargs="*",
        default=None,
        help="Categories to include (default: Assessment & Q&A, Custom Fields (CF), Learning & Training, Localization & Metadata)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Create output folder with registries/, data/, mdl_schemas/ and write preview files",
    )
    parser.add_argument(
        "--copy-mdl",
        action="store_true",
        help="Copy enriched .mdl.json files into output/mdl_schemas/ (requires folder_path in metadata)",
    )
    parser.add_argument(
        "--enrich-registries",
        action="store_true",
        help="Enrich source_concept_map (mdl_table_refs, project_ids) in output registries from metadata",
    )
    args = parser.parse_args()

    categories = set(args.categories) if args.categories else DEFAULT_CATEGORIES
    input_dir = Path(args.input_dir).resolve() if args.input_dir else None
    metadata_path = Path(args.metadata).resolve() if args.metadata else None
    enriched_path = Path(args.enriched).resolve() if args.enriched else None

    if not input_dir and not metadata_path:
        logger.error("Provide --input-dir or --metadata")
        return 1

    try:
        project_meta = load_or_ingest(input_dir, metadata_path, categories)
        if not project_meta.get("projects"):
            logger.warning(f"No projects found for categories: {categories}")
            return 0

        enriched = load_or_enrich(project_meta, enriched_path, input_dir, categories)
        preview = build_preview(enriched, input_dir)
        print_preview(preview, _project_root)

        if args.output:
            write_output_folder(
                Path(args.output).resolve(),
                project_meta,
                enriched,
                preview,
                copy_mdl=args.copy_mdl,
                enrich_registries=args.enrich_registries,
            )

        return 0
    except Exception as e:
        logger.exception(f"Preview failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

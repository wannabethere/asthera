"""
registry_vector_store.py

Write/index side of the Lexy registry vector store.

Collections:
    lexy_l1_source_concepts       — (source_id × concept_id) pairs
    lexy_l2_recommendation_areas  — (concept_id × area_id) pairs
    lexy_l3_mdl_tables            — MDL table models per project

Hook functions called by the three ingestion scripts:
    push_mdl_tables_to_store()           <- ingest_csod_mdl_projects.py (stage=raw)
                                         <- enrich_mdl_with_concepts.py  (stage=enriched)
    push_source_concepts_to_store()      <- enrich_csod_project_metadata.py
    push_recommendation_areas_to_store() <- build_concept_recommendation_registry.py

All writes use deterministic point IDs (MD5 of doc_id). Safe to re-run as upsert.
Aligns with lexy_metadata_registry_design table_schemas, db_schemas, concepts registry.
"""

import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Paths (complianceskill project root) ───────────────────────────────────────
REPO_ROOT                    = Path(__file__).resolve().parent.parent.parent
REGISTRIES_DIR               = REPO_ROOT / "registries"
DATA_DIR                     = REPO_ROOT / "data"
SOURCE_CONCEPT_REGISTRY_PATH = REGISTRIES_DIR / "source_concept_registry.json"
CONCEPT_REC_REGISTRY_PATH    = REGISTRIES_DIR / "concept_recommendation_registry.json"
ENRICHED_METADATA_PATH       = DATA_DIR / "csod_project_metadata_enriched.json"

# ── Collection names (from app.storage.collections.MDLCollections) ──────────────
try:
    from app.storage.collections import MDLCollections
    L1_COLLECTION = MDLCollections.CSOD_L1_SOURCE_CONCEPTS
    L2_COLLECTION = MDLCollections.CSOD_L2_RECOMMENDATION_AREAS
    L3_COLLECTION = MDLCollections.CSOD_L3_MDL_TABLES
except ImportError:
    L1_COLLECTION = "csod_l1_source_concepts"
    L2_COLLECTION = "csod_l2_recommendation_areas"
    L3_COLLECTION = "csod_l3_mdl_tables"

EMBEDDING_DIM = 1536
EMBED_MODEL   = "text-embedding-3-small"

SOURCE_DISPLAY_NAMES = {
    "cornerstone": "Cornerstone OnDemand",
    "workday":     "Workday",
    "qualys":      "Qualys VMDR",
    "snyk":        "Snyk",
    "sentinel":    "Microsoft Sentinel",
    "wiz":         "Wiz Cloud Security",
}


# ── Low-level utilities ────────────────────────────────────────────────────────

def _load_json(path: Path) -> Dict:
    if not path or not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)

def _point_id(doc_id: str) -> int:
    """Stable uint63 from doc_id string — truncated MD5."""
    return int(hashlib.md5(doc_id.encode()).hexdigest()[:16], 16) % (2 ** 63)

def _embed_texts(texts: List[str]) -> List[List[float]]:
    """Batch embed texts via OpenAI. Uses app.core.settings when available."""
    api_key = None
    try:
        from app.core.settings import get_settings
        api_key = get_settings().OPENAI_API_KEY
    except ImportError:
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        api_key = os.getenv("OPENAI_API_KEY")
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    all_vectors: List[List[float]] = []
    for i in range(0, len(texts), 100):
        resp = client.embeddings.create(input=texts[i : i + 100], model=EMBED_MODEL)
        all_vectors.extend(item.embedding for item in resp.data)
    return all_vectors

def _get_qdrant_client():
    """Get QdrantClient using app.core.settings (loads .env). Fallback to os.getenv if app unavailable."""
    try:
        from app.core.settings import get_settings
        settings = get_settings()
        url = settings.QDRANT_URL
        if not url:
            host = settings.QDRANT_HOST or "localhost"
            port = settings.QDRANT_PORT
            url = f"http://{host}:{port}"
        api_key = settings.QDRANT_API_KEY
    except ImportError:
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        url = os.getenv("QDRANT_URL")
        if not url:
            host = os.getenv("QDRANT_HOST", "localhost")
            port = os.getenv("QDRANT_PORT", "6333")
            url = f"http://{host}:{port}"
        api_key = os.getenv("QDRANT_API_KEY")
    from qdrant_client import QdrantClient
    return QdrantClient(url=url, api_key=api_key)

def _ensure_collection(client, name: str):
    """Create collection + payload indexes if absent."""
    from qdrant_client.models import Distance, VectorParams, PayloadSchemaType
    existing = {c.name for c in client.get_collections().collections}
    if name not in existing:
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )
        logger.info(f"Created collection: {name}")
    for field in {
        L1_COLLECTION: ["source_id", "concept_id", "domain"],
        L2_COLLECTION: ["concept_id", "domain"],
        L3_COLLECTION: ["project_id", "source_id", "table_tier", "concept_ids"],
    }.get(name, []):
        try:
            client.create_payload_index(
                collection_name=name,
                field_name=field,
                field_schema=PayloadSchemaType.KEYWORD,
            )
        except Exception:
            pass  # already exists

def _upsert_batch(
    client,
    collection: str,
    texts: List[str],
    payloads: List[Dict],
    dry_run: bool = False,
) -> int:
    if not texts:
        logger.info(f"  No documents for {collection}")
        return 0
    if dry_run:
        logger.info(f"  [dry-run] {len(texts)} docs -> {collection}")
        for p in payloads[:3]:
            logger.info(f"    {p['doc_id']}")
        return 0

    logger.info(f"  Embedding {len(texts)} texts for {collection}...")
    vectors = _embed_texts(texts)

    from qdrant_client.models import PointStruct
    _ensure_collection(client, collection)
    points = [
        PointStruct(id=_point_id(payloads[i]["doc_id"]), vector=vectors[i], payload=payloads[i])
        for i in range(len(texts))
    ]
    for i in range(0, len(points), 50):
        client.upsert(collection_name=collection, points=points[i : i + 50])

    logger.info(f"  Upserted {len(points)} points -> {collection}")
    return len(points)


# ── L1 builders ───────────────────────────────────────────────────────────────

def _l1_embedding_text(source_display: str, concept: Dict, entry: Dict) -> str:
    """
    Written to match how a user describes their problem, not how an engineer names a concept.
    business_questions[] is the highest-signal content — authored to mirror real user phrasings.
    """
    return " ".join(filter(None, [
        f"{concept.get('display_name', '')}.",
        concept.get("description", ""),
        f"Keywords: {', '.join(concept.get('trigger_keywords', []))}.",
        f"Business questions: {' '.join(concept.get('business_questions', []))}.",
        f"Data source: {source_display}.",
        f"Coverage: {entry.get('coverage_notes', '')}." if entry.get("coverage_notes") else "",
        f"API areas: {', '.join(entry.get('api_categories', []))}." if entry.get("api_categories") else "",
    ]))

def _l1_payload(
    source_id: str, concept_id: str, concept: Dict, entry: Dict, project_ids: List[str],
) -> Dict:
    return {
        "doc_id":              f"l1_{source_id}_{concept_id}",
        "doc_type":            "l1_source_concept",
        "source_id":           source_id,
        "concept_id":          concept_id,
        "domain":              concept.get("domain", ""),
        "display_name":        concept.get("display_name", ""),
        "description":         concept.get("description", ""),
        "coverage_confidence": float(entry.get("coverage_confidence", 0.8)),
        "api_categories":      entry.get("api_categories", []),
        "mdl_table_refs":      entry.get("mdl_table_refs", []),
        "primary_schemas":     entry.get("primary_schemas", []),
        "data_capabilities":   entry.get("data_capabilities", {}),
        "trigger_keywords":    concept.get("trigger_keywords", []),
        "requires_sources":    concept.get("requires_sources", [source_id]),
        "project_ids":         project_ids,
    }

def _build_l1_from_enriched_metadata(
    enriched_metadata: Dict,
    source_concept_registry: Dict,
    source_id: str = "cornerstone",
) -> Tuple[List[str], List[Dict]]:
    """
    Build L1 docs from csod_project_metadata_enriched.json.

    Concept -> project_ids is 1:many (one concept spans multiple project folders).
    Entry (mdl_table_refs, etc.) built from enriched metadata — no registry write.
    """
    key_concepts = {
        c["concept_id"]: c
        for c in source_concept_registry.get("key_concepts", [])
    }
    source_map = source_concept_registry.get("source_concept_map", {})
    source_entry = source_map.get(source_id, {})

    # concept_id -> project_ids (all projects serving this concept)
    concept_to_projects: Dict[str, List[str]] = {}
    # concept_id -> entry (mdl_table_refs, coverage) built from enriched projects
    concept_to_entry: Dict[str, Dict] = {}
    for project in enriched_metadata.get("projects", []):
        pid = project.get("project_id", "")
        mdl_tables = project.get("mdl_tables", {})
        table_refs = list(
            mdl_tables.get("primary", [])
            + mdl_tables.get("supporting", [])
            + mdl_tables.get("optional", [])
        )
        for cid in project.get("concept_ids", []):
            concept_to_projects.setdefault(cid, []).append(pid)
            entry = concept_to_entry.setdefault(cid, {
                "api_categories": [],
                "mdl_table_refs": [],
                "coverage_confidence": 0.85,
                "coverage_notes": "",
            })
            existing = set(entry.get("mdl_table_refs", []))
            entry["mdl_table_refs"] = list(existing | set(table_refs))
            if not entry.get("coverage_notes"):
                entry["coverage_notes"] = f"CSOD MDL projects: {pid}"

    source_display = SOURCE_DISPLAY_NAMES.get(source_id, source_id)
    texts, payloads = [], []

    for concept_id, project_ids in concept_to_projects.items():
        concept = key_concepts.get(concept_id)
        if not concept:
            logger.warning(f"L1: '{concept_id}' not in key_concepts, skipping")
            continue
        entry = concept_to_entry.get(concept_id) or source_entry.get(concept_id) or {
            "api_categories": [],
            "mdl_table_refs": [],
            "coverage_confidence": 0.8,
            "coverage_notes": f"Static LMS mapping for {concept_id}",
        }
        texts.append(_l1_embedding_text(source_display, concept, entry))
        payloads.append(_l1_payload(source_id, concept_id, concept, entry, project_ids))

    return texts, payloads


# ── L2 builders ───────────────────────────────────────────────────────────────

def _l2_embedding_text(concept_display: str, area: Dict) -> str:
    """
    natural_language_questions[] is the highest-signal content.
    A user saying 'empty classroom waste' will match 'How much is no-show waste costing us?'
    even though none of those words appear in the area_id or display_name.
    """
    return " ".join(filter(None, [
        f"{area.get('display_name', '')}.",
        area.get("description", ""),
        f"Questions: {' '.join(area.get('natural_language_questions', []))}.",
        f"KPIs: {', '.join(area.get('kpis', []))}.",
        f"Causal drivers: {' | '.join(area.get('causal_paths', []))}." if area.get("causal_paths") else "",
        f"Dashboard: {', '.join(area.get('dashboard_axes', []))}." if area.get("dashboard_axes") else "",
        f"Concept: {concept_display}.",
    ]))

def _l2_payload(concept_id: str, domain: str, area: Dict) -> Dict:
    return {
        "doc_id":           f"l2_{concept_id}_{area['area_id']}",
        "doc_type":         "l2_recommendation_area",
        "concept_id":       concept_id,
        "area_id":          area["area_id"],
        "domain":           domain,
        "display_name":     area.get("display_name", ""),
        "description":      area.get("description", ""),
        "metrics":          area.get("metrics", []),
        "kpis":             area.get("kpis", []),
        "filters":          area.get("filters", []),
        "dashboard_axes":   area.get("dashboard_axes", []),
        "causal_paths":     area.get("causal_paths", []),
        "data_requirements":area.get("data_requirements", []),
        "natural_language_questions": area.get("natural_language_questions", []),
    }

def _build_l2_from_registry(
    concept_rec_registry: Dict,
    source_concept_registry: Dict,
) -> Tuple[List[str], List[Dict]]:
    key_concepts   = {c["concept_id"]: c for c in source_concept_registry.get("key_concepts", [])}
    recommendations = concept_rec_registry.get("concept_recommendations", {})
    texts, payloads = [], []
    for concept_id, concept_data in recommendations.items():
        concept = key_concepts.get(concept_id, {})
        display = concept.get("display_name", concept_id)
        domain  = concept.get("domain", "")
        for area in concept_data.get("recommendation_areas", []):
            if not area.get("area_id"):
                continue
            texts.append(_l2_embedding_text(display, area))
            payloads.append(_l2_payload(concept_id, domain, area))
    return texts, payloads


# ── L3 builders ───────────────────────────────────────────────────────────────

def _l3_embedding_text(
    display_name: str, description: str,
    concept_ids: List[str], key_columns: List[str], categories: List[str],
) -> str:
    """
    Includes concept names as words in the embedding text so a query about
    'compliance SLA' has elevated similarity to tables tagged compliance_training.
    """
    return " ".join(filter(None, [
        f"{display_name}.",
        description,
        f"Concepts: {', '.join(concept_ids)}." if concept_ids else "",
        f"Key columns: {', '.join(key_columns[:15])}." if key_columns else "",
        f"Categories: {', '.join(categories)}." if categories else "",
    ]))

def _l3_payload(
    project: Dict,
    table_name: str,
    tier: str,
    model: Optional[Dict],
    source_id: str,
    mdl_data: Optional[Dict] = None,
) -> Dict:
    project_id  = project.get("project_id", "")
    key_cols    = project.get("key_columns", {}).get(table_name, [])
    categories  = project.get("table_to_category", {}).get(table_name, [])
    concept_ids = project.get("concept_ids", [])
    area_ids: List[str] = []

    if model:
        # Per-model annotations set by enrich_mdl_with_concepts take priority
        concept_ids = model.get("properties", {}).get("concept_ids", concept_ids)
        area_ids    = model.get("properties", {}).get("recommendation_area_ids", [])
        if not key_cols:
            key_cols = [
                c["name"] for c in model.get("columns", [])
                if isinstance(c, dict) and c.get("name") and c["name"] != "concept_id"
            ][:12]

    display = (model or {}).get("properties", {}).get("displayName", table_name.replace("_", " ").title())
    desc    = ((model or {}).get("properties", {}).get("description", "") or "")[:512]

    # db_catalog, db_schema from table_schemas, project, or MDL file (preserve table_schemas/db_schemas flow)
    table_schemas = project.get("table_schemas", {}).get(table_name, {})
    db_catalog = table_schemas.get("catalog") or project.get("db_catalog", "")
    db_schema = table_schemas.get("schema") or project.get("db_schema", "dbo")
    if not db_catalog and mdl_data:
        db_catalog = mdl_data.get("catalog", "")
    if not db_schema and mdl_data:
        db_schema = mdl_data.get("schema", "dbo")
    if not db_catalog and model:
        tr = model.get("tableReference") or {}
        db_catalog = db_catalog or tr.get("catalog", "")
        db_schema = db_schema or tr.get("schema", "dbo")
    db_schema = db_schema or "dbo"
    qualified_table_name = f"{db_catalog}.{db_schema}.{table_name}" if (db_catalog and db_schema) else table_name

    return {
        "doc_id":                  f"l3_{project_id}_{table_name}",
        "doc_type":                "l3_mdl_table",
        "project_id":              project_id,
        "source_id":               source_id or project.get("source_id", "cornerstone"),
        "table_name":              table_name,
        "display_name":            display,
        "description":             desc,
        "primary_key":             (model or {}).get("primaryKey", key_cols[0] if key_cols else ""),
        "concept_ids":             concept_ids,
        "recommendation_area_ids": area_ids,
        "key_columns":             key_cols,
        "data_capabilities":       (model or {}).get("properties", {}).get("data_capabilities", []),
        "table_tier":              tier,
        "mdl_file":                f"{table_name}.mdl.json",
        "category_path":           f"{project.get('category','')}/{project.get('subcategory','')}",
        "source_schema":           (model or {}).get("properties", {}).get("source_schema", table_name),
        "db_catalog":              db_catalog,
        "db_schema":               db_schema,
        "qualified_table_name":    qualified_table_name,
    }

def _build_l3_from_metadata(
    project_metadata: Dict,
    source_id: str = "cornerstone",
    read_mdl_files: bool = True,
) -> Tuple[List[str], List[Dict]]:
    """
    Build L3 docs from project metadata dict.
    read_mdl_files=False (stage=raw): uses project record only, no MDL file reads.
    read_mdl_files=True  (stage=enriched): reads .mdl.json for per-model concept annotations.
    """
    texts, payloads = [], []

    for project in project_metadata.get("projects", []):
        folder_path = Path(project.get("folder_path", ""))
        mdl_tables  = project.get("mdl_tables", {})
        proj_source_id = project.get("source_id", source_id)

        # Build tier map
        tier_map: Dict[str, str] = {}
        if mdl_tables:
            for tier in ("primary", "supporting", "optional"):
                for t in mdl_tables.get(tier, []):
                    tier_map[t] = tier
        else:
            for t in project.get("tables", []):
                if isinstance(t, dict) and t.get("name"):
                    tier_map[t["name"]] = "supporting"

        for table_name, tier in tier_map.items():
            model = None
            mdl_data = None
            if read_mdl_files and folder_path.exists():
                mdl_path = folder_path / f"{table_name}.mdl.json"
                if mdl_path.exists():
                    try:
                        with open(mdl_path) as f:
                            mdl_data = json.load(f)
                        models = mdl_data.get("models", [])
                        model = models[0] if models else None
                    except Exception:
                        pass

            payload = _l3_payload(project, table_name, tier, model, proj_source_id, mdl_data)
            text    = _l3_embedding_text(
                payload["display_name"], payload["description"],
                payload["concept_ids"],  payload["key_columns"],
                project.get("table_to_category", {}).get(table_name, []),
            )
            texts.append(text)
            payloads.append(payload)

    return texts, payloads


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC HOOK FUNCTIONS — called by the three ingestion scripts
# ══════════════════════════════════════════════════════════════════════════════

def push_source_concepts_to_store(
    enriched_metadata: Dict,
    source_concept_registry: Optional[Dict] = None,
    source_id: str = "cornerstone",
    dry_run: bool = False,
) -> int:
    """
    HOOK B — called by enrich_csod_project_metadata.py -> enrich_registry()

    Args:
        enriched_metadata:       return value of enrich_registry() — full enriched structure
        source_concept_registry: loaded source_concept_registry.json; auto-loaded if None
        source_id:               data source identifier (default 'cornerstone')
        dry_run:                 log without calling Qdrant
    """
    src_reg = source_concept_registry or _load_json(SOURCE_CONCEPT_REGISTRY_PATH)
    texts, payloads = _build_l1_from_enriched_metadata(enriched_metadata, src_reg, source_id)
    if not texts:
        logger.warning("push_source_concepts_to_store: no L1 docs built — enriched_metadata may lack concept_ids or source_concept_registry.key_concepts")
        return 0
    client = None if dry_run else _get_qdrant_client()
    return _upsert_batch(client, L1_COLLECTION, texts, payloads, dry_run)


def push_recommendation_areas_to_store(
    concept_rec_registry: Optional[Dict] = None,
    source_concept_registry: Optional[Dict] = None,
    dry_run: bool = False,
) -> int:
    """
    HOOK D — called by build_concept_recommendation_registry.py

    Args:
        concept_rec_registry:    loaded concept_recommendation_registry.json; auto-loaded if None
        source_concept_registry: for concept display_name/domain; auto-loaded if None
        dry_run:                 log without calling Qdrant
    """
    rec_reg = concept_rec_registry or _load_json(CONCEPT_REC_REGISTRY_PATH)
    src_reg = source_concept_registry or _load_json(SOURCE_CONCEPT_REGISTRY_PATH)
    texts, payloads = _build_l2_from_registry(rec_reg, src_reg)
    client = None if dry_run else _get_qdrant_client()
    return _upsert_batch(client, L2_COLLECTION, texts, payloads, dry_run)


def push_mdl_tables_to_store(
    project_metadata: Optional[Dict] = None,
    input_dir: Optional[Path] = None,
    source_id: str = "cornerstone",
    stage: str = "enriched",
    dry_run: bool = False,
    concept_rec_registry: Optional[Dict] = None,
) -> int:
    """
    HOOK A — called by ingest_csod_mdl_projects.py  (stage='raw')
    HOOK C — called by enrich_mdl_with_concepts.py  (stage='enriched')

    stage='raw':      concept_ids=[] in embedding text; establishes table docs before enrichment
    stage='enriched': reads .mdl.json for per-model concept_ids written by enrich_mdl_with_concepts
                      Deterministic point IDs -> Hook C safely upserts/overwrites Hook A docs
    """
    if project_metadata is None and input_dir is not None:
        # Reconstruct minimal metadata from MDL directory structure
        projects = []
        for mp in input_dir.rglob("project_metadata.json"):
            try:
                with open(mp) as f:
                    p = json.load(f)
                p["folder_path"] = str(mp.parent)
                projects.append(p)
            except Exception:
                pass
        project_metadata = {"projects": projects}

    if not project_metadata:
        logger.warning("push_mdl_tables_to_store: no project_metadata, nothing to upsert")
        return 0

    # stage=raw -> don't read MDL files (concept_ids not yet written into them)
    read_mdl = (stage == "enriched")
    texts, payloads = _build_l3_from_metadata(project_metadata, source_id, read_mdl)
    client = None if dry_run else _get_qdrant_client()
    return _upsert_batch(client, L3_COLLECTION, texts, payloads, dry_run)


# ══════════════════════════════════════════════════════════════════════════════
# STANDALONE CLI — full rebuild
# ══════════════════════════════════════════════════════════════════════════════

def build_all(
    project_metadata_path: Optional[Path] = None,
    dry_run: bool = False,
) -> Dict[str, int]:
    src_reg  = _load_json(SOURCE_CONCEPT_REGISTRY_PATH)
    rec_reg  = _load_json(CONCEPT_REC_REGISTRY_PATH)
    meta_p   = project_metadata_path or ENRICHED_METADATA_PATH
    meta     = _load_json(meta_p) if meta_p.exists() else {}
    client   = None if dry_run else _get_qdrant_client()

    texts, payloads = _build_l1_from_enriched_metadata(meta, src_reg)
    l1 = _upsert_batch(client, L1_COLLECTION, texts, payloads, dry_run)

    texts, payloads = _build_l2_from_registry(rec_reg, src_reg)
    l2 = _upsert_batch(client, L2_COLLECTION, texts, payloads, dry_run)

    texts, payloads = _build_l3_from_metadata(meta, read_mdl_files=True)
    l3 = _upsert_batch(client, L3_COLLECTION, texts, payloads, dry_run)

    logger.info(f"Vector store build complete — L1:{l1}  L2:{l2}  L3:{l3}")
    return {"l1": l1, "l2": l2, "l3": l3}


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-all",  action="store_true")
    ap.add_argument("--collection", choices=["l1", "l2", "l3"])
    ap.add_argument("--metadata",   type=Path, default=None)
    ap.add_argument("--dry-run",    action="store_true")
    args = ap.parse_args()

    if args.build_all:
        build_all(project_metadata_path=args.metadata, dry_run=args.dry_run)
    elif args.collection == "l1":
        meta = _load_json(args.metadata or ENRICHED_METADATA_PATH)
        push_source_concepts_to_store(meta, dry_run=args.dry_run)
    elif args.collection == "l2":
        push_recommendation_areas_to_store(dry_run=args.dry_run)
    elif args.collection == "l3":
        meta = _load_json(args.metadata or ENRICHED_METADATA_PATH)
        push_mdl_tables_to_store(meta, stage="enriched", dry_run=args.dry_run)
    else:
        print("Specify --build-all or --collection {l1|l2|l3}")
        sys.exit(1)

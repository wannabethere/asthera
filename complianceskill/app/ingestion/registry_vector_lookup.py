"""
registry_vector_lookup.py

Read/query side of the Lexy registry vector store.

Three public query functions — one per collection, one per runtime problem:

    resolve_intent_to_concept()      <- Lexy Phase 1 (user query -> concept_id, project_ids)
    resolve_scoping_to_areas()       <- Lexy Phase 3 (scoping answers -> recommendation areas)
    resolve_metric_to_tables()       <- CCE planner (metric intent -> MDL tables with qualified_table_name)

Concept -> project_ids is 1:many. L3 filter uses project_id IN active_project_ids.
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# ── Collection names (from app.storage.collections.MDLCollections) ────────────
try:
    from app.storage.collections import MDLCollections
    L1_COLLECTION = MDLCollections.CSOD_L1_SOURCE_CONCEPTS
    L2_COLLECTION = MDLCollections.CSOD_L2_RECOMMENDATION_AREAS
    L3_COLLECTION = MDLCollections.CSOD_L3_MDL_TABLES
except ImportError:
    L1_COLLECTION = "csod_l1_source_concepts"
    L2_COLLECTION = "csod_l2_recommendation_areas"
    L3_COLLECTION = "csod_l3_mdl_tables"

EMBED_MODEL = "text-embedding-3-small"

# Score thresholds — below these, fallback is triggered
L1_THRESHOLD = 0.65
L2_THRESHOLD = 0.60
L3_THRESHOLD = 0.60

# Coverage confidence reranking weight for L1
CONFIDENCE_WEIGHT = 0.30

# Paths (complianceskill project root)
REPO_ROOT                    = Path(__file__).resolve().parent.parent.parent
REGISTRIES_DIR               = REPO_ROOT / "registries"
DATA_DIR                     = REPO_ROOT / "data"
SOURCE_CONCEPT_REGISTRY_PATH = REGISTRIES_DIR / "source_concept_registry.json"
CONCEPT_REC_REGISTRY_PATH    = REGISTRIES_DIR / "concept_recommendation_registry.json"
ENRICHED_METADATA_PATH       = DATA_DIR / "csod_project_metadata_enriched.json"


# ── Result dataclasses ─────────────────────────────────────────────────────────

@dataclass
class ConceptMatch:
    """Result of resolve_intent_to_concept() — one candidate concept per result."""
    concept_id:          str
    source_id:           str
    project_ids:         List[str]   # 1:many — concept spans multiple project folders
    display_name:        str
    domain:              str
    score:               float
    raw_score:           float
    coverage_confidence: float
    mdl_table_refs:      List[str]
    api_categories:      List[str]
    trigger_keywords:    List[str]
    via_fallback:        bool = False

    @property
    def project_id(self) -> str:
        """Backward compat: first project_id."""
        return self.project_ids[0] if self.project_ids else ""


@dataclass
class RecommendationAreaMatch:
    """Result of resolve_scoping_to_areas() — one recommendation area per result."""
    area_id:          str
    concept_id:       str
    display_name:     str
    score:            float
    metrics:          List[str]
    kpis:             List[str]
    filters:          List[str]
    dashboard_axes:   List[str]
    causal_paths:     List[str]
    natural_language_questions: List[str]
    data_requirements: List[str]
    via_fallback:     bool = False


@dataclass
class TableMatch:
    """Result of resolve_metric_to_tables() — one MDL table per result."""
    table_name:           str
    project_id:           str
    source_id:            str
    display_name:         str
    primary_key:          str
    score:                float
    key_columns:          List[str]
    concept_ids:          List[str]
    data_capabilities:    List[str]
    table_tier:           str
    mdl_file:             str
    category_path:        str
    db_catalog:           str = ""
    db_schema:            str = ""
    qualified_table_name: str = ""   # e.g. csod_dE.dbo.transcript_core — planner uses directly
    via_fallback:         bool = False


# ── Infrastructure ─────────────────────────────────────────────────────────────

def _load_json(path: Path) -> Dict:
    if not path or not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)

def _embed(text: str) -> List[float]:
    """Embed text via OpenAI. Uses app.core.settings when available."""
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
    resp = client.embeddings.create(input=[text], model=EMBED_MODEL)
    return resp.data[0].embedding

def _get_qdrant():
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

def _qdrant_search(collection: str, vector: List[float], filters: Dict, top_k: int) -> List[Any]:
    from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny

    must = []
    for field_name, value in filters.items():
        if isinstance(value, list):
            must.append(FieldCondition(key=field_name, match=MatchAny(any=value)))
        elif value is not None:
            must.append(FieldCondition(key=field_name, match=MatchValue(value=value)))

    qdrant_filter = Filter(must=must) if must else None

    try:
        client = _get_qdrant()
        return client.search(
            collection_name=collection,
            query_vector=vector,
            query_filter=qdrant_filter,
            limit=top_k,
            with_payload=True,
        )
    except Exception as e:
        logger.warning(f"Qdrant search failed ({collection}): {e}")
        return []


# ── 1. Phase 1: Intent → Concept ──────────────────────────────────────────────

def resolve_intent_to_concept(
    user_query: str,
    connected_source_ids: List[str],
    domain_filter: Optional[str] = None,
    top_k: int = 5,
    source_concept_registry: Optional[Dict] = None,
) -> List[ConceptMatch]:
    """
    Lexy Phase 1 — resolve user query to concept(s). Returns project_ids (1:many).
    
    Note: source_id filtering is disabled - queries all concepts in the collection.
    Future: When multiple source collections exist, filtering can be re-enabled.
    """
    qdrant_filters: Dict[str, Any] = {}
    # Source ID filtering disabled - collection is already scoped to a single source
    # if connected_source_ids:
    #     qdrant_filters["source_id"] = connected_source_ids
    if domain_filter:
        qdrant_filters["domain"] = domain_filter

    vector  = _embed(user_query)
    results = _qdrant_search(L1_COLLECTION, vector, qdrant_filters, top_k)

    matches: List[ConceptMatch] = []
    for r in results:
        p = r.payload
        raw_score  = float(r.score)
        confidence = float(p.get("coverage_confidence", 0.5))
        reranked   = raw_score * (1 - CONFIDENCE_WEIGHT + CONFIDENCE_WEIGHT * confidence)

        matches.append(ConceptMatch(
            concept_id=          p.get("concept_id", ""),
            source_id=           p.get("source_id", ""),
            project_ids=         p.get("project_ids", []),
            display_name=        p.get("display_name", ""),
            domain=              p.get("domain", ""),
            score=               round(reranked, 4),
            raw_score=           round(raw_score, 4),
            coverage_confidence= confidence,
            mdl_table_refs=      p.get("mdl_table_refs", []),
            api_categories=      p.get("api_categories", []),
            trigger_keywords=    p.get("trigger_keywords", []),
        ))

    matches.sort(key=lambda m: m.score, reverse=True)

    if not matches or matches[0].score < L1_THRESHOLD:
        fallback = _l1_keyword_fallback(user_query, connected_source_ids, source_concept_registry)
        if fallback:
            return fallback
        return matches

    return matches


def _l1_keyword_fallback(
    user_query: str,
    connected_source_ids: List[str],
    source_concept_registry: Optional[Dict] = None,
) -> List[ConceptMatch]:
    """Keyword fallback — build project_ids and mdl_table_refs from enriched metadata (1:many)."""
    reg = source_concept_registry or _load_json(SOURCE_CONCEPT_REGISTRY_PATH)
    key_concepts = {c["concept_id"]: c for c in reg.get("key_concepts", [])}
    source_map   = reg.get("source_concept_map", {})
    query_lower  = user_query.lower()

    meta = _load_json(ENRICHED_METADATA_PATH)
    concept_to_projects: Dict[str, List[str]] = {}
    concept_to_refs: Dict[str, List[str]] = {}
    for project in meta.get("projects", []):
        pid = project.get("project_id", "")
        mdl_tables = project.get("mdl_tables", {})
        refs = mdl_tables.get("primary", []) + mdl_tables.get("supporting", []) + mdl_tables.get("optional", [])
        for cid in project.get("concept_ids", []):
            concept_to_projects.setdefault(cid, []).append(pid)
            concept_to_refs.setdefault(cid, []).extend(refs)

    matches: List[ConceptMatch] = []
    seen_concepts: set = set()

    for source_id in connected_source_ids:
        source_entries = source_map.get(source_id, {})
        for concept_id in set(concept_to_projects.keys()) | set(source_entries.keys()):
            if concept_id in seen_concepts:
                continue
            concept = key_concepts.get(concept_id, {})
            keywords = concept.get("trigger_keywords", [])
            hits = sum(1 for kw in keywords if kw.lower() in query_lower)
            if hits == 0:
                continue
            seen_concepts.add(concept_id)

            entry = source_entries.get(concept_id) if isinstance(source_entries.get(concept_id), dict) else {}
            project_ids = concept_to_projects.get(concept_id, [])
            mdl_refs = concept_to_refs.get(concept_id, []) or entry.get("mdl_table_refs", [])
            if not project_ids:
                project_ids = [""]

            score = min(0.64, 0.40 + 0.06 * hits)
            matches.append(ConceptMatch(
                concept_id=          concept_id,
                source_id=           source_id,
                project_ids=         project_ids,
                display_name=        concept.get("display_name", ""),
                domain=              concept.get("domain", ""),
                score=               score,
                raw_score=           score,
                coverage_confidence= float(entry.get("coverage_confidence", 0.5)),
                mdl_table_refs=      list(dict.fromkeys(mdl_refs)),
                api_categories=      entry.get("api_categories", []),
                trigger_keywords=    keywords,
                via_fallback=        True,
            ))

    matches.sort(key=lambda m: m.score, reverse=True)
    return matches[:5]


# ── 2. Phase 3: Scoping → Recommendation Areas ────────────────────────────────

def resolve_scoping_to_areas(
    scoping_answers: Dict[str, str],
    confirmed_concept_id: str,
    top_k: int = 3,
    concept_rec_registry: Optional[Dict] = None,
) -> List[RecommendationAreaMatch]:
    """Lexy Phase 3 — map scoping answers to recommendation areas."""
    scoping_text = " ".join(v for v in scoping_answers.values() if v and isinstance(v, str))
    if not scoping_text.strip():
        return _l2_all_areas_fallback(confirmed_concept_id, concept_rec_registry)

    qdrant_filters = {"concept_id": confirmed_concept_id}
    vector  = _embed(scoping_text)
    results = _qdrant_search(L2_COLLECTION, vector, qdrant_filters, top_k)

    matches: List[RecommendationAreaMatch] = []
    for r in results:
        p = r.payload
        matches.append(RecommendationAreaMatch(
            area_id=          p.get("area_id", ""),
            concept_id=       p.get("concept_id", ""),
            display_name=     p.get("display_name", ""),
            score=            round(float(r.score), 4),
            metrics=          p.get("metrics", []),
            kpis=             p.get("kpis", []),
            filters=          p.get("filters", []),
            dashboard_axes=   p.get("dashboard_axes", []),
            causal_paths=     p.get("causal_paths", []),
            natural_language_questions= p.get("natural_language_questions", []),
            data_requirements= p.get("data_requirements", []),
        ))

    if not matches or matches[0].score < L2_THRESHOLD:
        return _l2_all_areas_fallback(confirmed_concept_id, concept_rec_registry)

    return matches


def _l2_all_areas_fallback(
    concept_id: str,
    concept_rec_registry: Optional[Dict] = None,
) -> List[RecommendationAreaMatch]:
    reg  = concept_rec_registry or _load_json(CONCEPT_REC_REGISTRY_PATH)
    data = reg.get("concept_recommendations", {}).get(concept_id, {})
    areas = data.get("recommendation_areas", [])

    return [
        RecommendationAreaMatch(
            area_id=          a.get("area_id", ""),
            concept_id=       concept_id,
            display_name=     a.get("display_name", ""),
            score=            0.0,
            metrics=          a.get("metrics", []),
            kpis=             a.get("kpis", []),
            filters=          a.get("filters", []),
            dashboard_axes=   a.get("dashboard_axes", []),
            causal_paths=     a.get("causal_paths", []),
            natural_language_questions= a.get("natural_language_questions", []),
            data_requirements= a.get("data_requirements", []),
            via_fallback=     True,
        )
        for a in areas if a.get("area_id")
    ]


# ── 3. CCE Planner: Metric Intent → MDL Tables ────────────────────────────────

def resolve_metric_to_tables(
    metric_intent: str,
    active_project_ids: Union[str, List[str]],
    confirmed_concept_id: str,
    tier_filter: Optional[List[str]] = None,
    top_k: int = 5,
    project_metadata: Optional[Dict] = None,
) -> List[TableMatch]:
    """
    CCE planner — map metric intent to MDL tables. Returns qualified_table_name.

    Args:
        active_project_ids:  project_ids for the concept (1:many). Single str accepted for backward compat.
        confirmed_concept_id: concept confirmed at Phase 1
    """
    if isinstance(active_project_ids, str):
        active_project_ids = [active_project_ids]
    active_project_ids = [p for p in active_project_ids if p]

    tiers = tier_filter or ["primary", "supporting"]

    # project_id IN active_project_ids — never miss sibling project tables
    qdrant_filters: Dict[str, Any] = {
        "project_id":  active_project_ids,
        "table_tier":  tiers,
        "concept_ids": confirmed_concept_id,
    }

    vector  = _embed(metric_intent)
    results = _qdrant_search(L3_COLLECTION, vector, qdrant_filters, top_k)

    matches: List[TableMatch] = []
    for r in results:
        p = r.payload
        matches.append(TableMatch(
            table_name=           p.get("table_name", ""),
            project_id=           p.get("project_id", ""),
            source_id=            p.get("source_id", ""),
            display_name=         p.get("display_name", ""),
            primary_key=          p.get("primary_key", ""),
            score=                round(float(r.score), 4),
            key_columns=          p.get("key_columns", []),
            concept_ids=          p.get("concept_ids", []),
            data_capabilities=    p.get("data_capabilities", []),
            table_tier=           p.get("table_tier", ""),
            mdl_file=             p.get("mdl_file", ""),
            category_path=        p.get("category_path", ""),
            db_catalog=           p.get("db_catalog", ""),
            db_schema=            p.get("db_schema", ""),
            qualified_table_name= p.get("qualified_table_name", ""),
        ))

    if not matches or matches[0].score < L3_THRESHOLD:
        return _l3_primary_tables_fallback(active_project_ids, confirmed_concept_id, project_metadata)

    return matches


def _l3_primary_tables_fallback(
    project_ids: List[str],
    concept_id: str,
    project_metadata: Optional[Dict] = None,
) -> List[TableMatch]:
    """Return primary tables for all project_ids (concept spans multiple projects)."""
    meta = project_metadata or _load_json(ENRICHED_METADATA_PATH)
    matches: List[TableMatch] = []

    for project in meta.get("projects", []):
        pid = project.get("project_id", "")
        if pid not in project_ids:
            continue

        primary_tables = project.get("mdl_tables", {}).get("primary", [])
        key_columns   = project.get("key_columns", {})
        table_schemas = project.get("table_schemas", {})
        db_catalog    = project.get("db_catalog", "")
        db_schema     = project.get("db_schema", "dbo")

        for t in primary_tables:
            ts = table_schemas.get(t, {})
            cat = ts.get("catalog") or db_catalog
            sch = ts.get("schema") or db_schema
            qtn = f"{cat}.{sch}.{t}" if (cat and sch) else t

            matches.append(TableMatch(
                table_name=           t,
                project_id=           pid,
                source_id=            project.get("source_id", "cornerstone"),
                display_name=         t.replace("_", " ").title(),
                primary_key=          key_columns.get(t, [""])[0] if key_columns.get(t) else "",
                score=                0.0,
                key_columns=          key_columns.get(t, []),
                concept_ids=          project.get("concept_ids", []),
                data_capabilities=    [],
                table_tier=           "primary",
                mdl_file=             f"{t}.mdl.json",
                category_path=        f"{project.get('category','')}/{project.get('subcategory','')}",
                db_catalog=           cat,
                db_schema=            sch,
                qualified_table_name= qtn,
                via_fallback=         True,
            ))

    return matches


def build_scoping_query_text(
    onset_pattern: Optional[str] = None,
    org_unit: Optional[str] = None,
    org_unit_value: Optional[str] = None,
    training_type: Optional[str] = None,
    time_window: Optional[str] = None,
    persona: Optional[str] = None,
    **extra_answers,
) -> str:
    """Build scoping query text for resolve_scoping_to_areas()."""
    parts = []
    if onset_pattern:
        parts.append(f"Problem pattern: {onset_pattern}.")
    if org_unit and org_unit_value:
        parts.append(f"Scope: {org_unit_value} {org_unit}.")
    elif org_unit:
        parts.append(f"Scope: by {org_unit}.")
    if training_type:
        parts.append(f"Training type: {training_type}.")
    if time_window:
        parts.append(f"Time window: {time_window}.")
    if persona:
        parts.append(f"Viewer: {persona}.")
    for k, v in extra_answers.items():
        if v:
            parts.append(f"{k}: {v}.")
    return " ".join(parts)

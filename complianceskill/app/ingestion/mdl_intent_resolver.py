"""
mdl_intent_resolver.py

MDL-aware intent-to-project-and-area resolution.

Uses ONLY:
  • preview_out/data/csod_project_metadata_enriched.json
      — area_registry (project areas with tables + key_columns)
      — concept_registry (concept → area mappings, signal columns, sample questions)
  • preview_out/data/csod_project_metadata.json
      — projects (richer table_schemas, knowledge_base, examples per project)

No pruning: the entire file content is sent to the LLM.
If the combined payload exceeds BATCH_CHAR_LIMIT, area_registry items are sent
in batches of BATCH_SIZE and results are merged/de-duplicated.

Public API
----------
resolve_intents_to_projects_and_areas(intents, datasource_id) -> List[dict]
    Each dict (IntentResolution): {
        intent_id, description, analytical_goal,
        concept_id, concept_display_name,
        matched_project_ids, project_display_names, project_rationale,
        area_ids, areas, project_tables
    }
"""

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── File paths ────────────────────────────────────────────────────────────────

_HERE = Path(__file__).resolve()
# Walk up to repo root: .../genieml/complianceskill/
_SKILL_ROOT = _HERE.parent.parent.parent
_DATA_DIR = _SKILL_ROOT / "preview_out" / "data"

ENRICHED_METADATA_PATH = _DATA_DIR / "csod_project_metadata_enriched.json"
BASE_METADATA_PATH = _DATA_DIR / "csod_project_metadata.json"

# Batching: when area payload exceeds this, split into BATCH_SIZE chunks
BATCH_CHAR_LIMIT = 80_000   # ~20K tokens — safe for all supported LLMs
BATCH_SIZE = 3               # areas per LLM call when batching


# ── File loading (cached) ─────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _load_enriched() -> dict:
    if ENRICHED_METADATA_PATH.exists():
        with open(ENRICHED_METADATA_PATH) as f:
            return json.load(f)
    logger.warning("Enriched metadata not found at %s", ENRICHED_METADATA_PATH)
    return {}


@lru_cache(maxsize=1)
def _load_base() -> dict:
    if BASE_METADATA_PATH.exists():
        with open(BASE_METADATA_PATH) as f:
            return json.load(f)
    logger.warning("Base metadata not found at %s", BASE_METADATA_PATH)
    return {}


# Keep the public helpers that csod_intent_confirm._apply_selections calls
# as a fallback (it reads area_registry directly via _load_area_registry).
def _load_area_registry() -> dict:
    """Compatibility shim: return enriched file as an area-registry-shaped dict."""
    enriched = _load_enriched()
    # Build concept_recommendations map from concept_registry for backward compat
    concept_registry = enriched.get("concept_registry", [])
    area_registry = enriched.get("area_registry", [])
    area_index = {a["area_id"]: a for a in area_registry}

    concept_recommendations = {}
    for c in concept_registry:
        cid = c["concept_id"]
        rec_areas = []
        for aid in c.get("area_ids", []):
            area = area_index.get(aid, {})
            rec_areas.append({
                "area_id": aid,
                "display_name": area.get("label", aid),
                "description": area.get("description", ""),
                "metrics": [],
                "kpis": [],
                "filters": [],
                "causal_paths": [],
                "dashboard_axes": [],
                "natural_language_questions": c.get("sample_questions", [])[:3],
                "data_requirements": [t["name"] for t in area.get("tables", []) if t.get("role") == "primary"],
            })
        concept_recommendations[cid] = {"recommendation_areas": rec_areas}

    return {"concept_recommendations": concept_recommendations}


def _load_project_metadata() -> dict:
    """Compatibility shim: return enriched area_registry as a projects list."""
    enriched = _load_enriched()
    area_registry = enriched.get("area_registry", [])
    projects = []
    for a in area_registry:
        primary = [t["name"] for t in a.get("tables", []) if t.get("role") == "primary"]
        supporting = [t["name"] for t in a.get("tables", []) if t.get("role") != "primary"]
        key_columns = {t["name"]: t.get("key_columns", []) for t in a.get("tables", [])}
        projects.append({
            "project_id": a["area_id"],
            "title": a.get("label", a["area_id"]),
            "description": a.get("description", ""),
            "data_sources": ["cornerstone"],
            "tables": a.get("tables", []),
            "mdl_tables": {"primary": primary, "supporting": supporting},
            "key_columns": key_columns,
            "table_to_category": {},
            "concept_ids": [],
        })
    return {"projects": projects}


# Keep _load_concept_registry for anything that imports it from here
def _load_concept_registry() -> dict:
    """Compatibility shim: return concept_registry as source_concept_registry format."""
    enriched = _load_enriched()
    concept_registry = enriched.get("concept_registry", [])
    key_concepts = []
    for c in concept_registry:
        key_concepts.append({
            "concept_id": c["concept_id"],
            "display_name": c.get("label", c["concept_id"]),
            "description": c.get("description", ""),
        })
    return {"key_concepts": key_concepts, "source_concept_map": {}}


# ── Data preparation ──────────────────────────────────────────────────────────

def _build_merged_areas() -> List[dict]:
    """
    Merge area_registry (enriched) with projects (base) into a single list.
    No pruning — all fields from both files are included.
    """
    enriched = _load_enriched()
    base = _load_base()

    area_registry: List[dict] = enriched.get("area_registry", [])
    base_projects: Dict[str, dict] = {p["project_id"]: p for p in base.get("projects", [])}

    merged = []
    for area in area_registry:
        aid = area["area_id"]
        entry = dict(area)  # full area object, no pruning
        base_p = base_projects.get(aid, {})
        # Attach richer fields from base file
        if base_p:
            entry["knowledge_base"] = base_p.get("knowledge_base", "")
            entry["examples"] = base_p.get("examples", [])
            entry["table_schemas"] = base_p.get("table_schemas", [])
        merged.append(entry)

    return merged


def _get_concept_registry() -> List[dict]:
    return _load_enriched().get("concept_registry", [])


# ── LLM prompt / call ─────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are an LMS analytics routing specialist for Cornerstone OnDemand (CSOD).

You are given:
  1. concept_registry — analytical concepts with their IDs, descriptions, and the area_ids they cover
  2. area_registry — CSOD project areas with full table definitions, key columns, and enriched metadata
  3. intents — 1–3 analytical intents extracted from the user's question

Your task: for EACH intent, return:
  - concept_id: the best-matching concept from concept_registry (copy the exact concept_id string)
  - matched_project_ids: 2–4 area_ids from area_registry whose tables/columns can directly answer this intent
  - project_rationale: 1–2 sentences naming the specific tables/columns that drove your choice
  - area_ids: same list as matched_project_ids (areas and projects are the same in this schema)

HOW TO SELECT:
- Reason from the actual table names and key_columns in area_registry, not just labels
- Match column names to what the intent is measuring:
    • completion / transcript status  → completion_dt, status, reg_num → csod_transcript_statuses
    • mandatory / assignment tracking → assignment_id, due_date       → csod_assignments_lat
    • assessment scores / quiz        → score, attempt_score           → csod_assessment_qa
    • ILT / instructor-led training   → session_id, event_id           → csod_ilt_event_session
    • SCORM / e-learning              → scorm_activity_id              → csod_scorm
    • training catalog / LO           → lo_id, object_id, title        → csod_training_catalog_lo
    • curriculum / learning path      → curriculum_object_id           → csod_curriculum_bundles
    • certifications / cost           → cost, certification_id         → csod_training_finance_ecommerce

⚠ CRITICAL — copy ID strings EXACTLY as they appear in the JSON you receive. Do NOT invent or abbreviate.

Return ONLY a valid JSON array — no markdown fences, no explanation outside the array.
"""

_USER_PROMPT_TEMPLATE = """\
## concept_registry
{concept_registry_json}

## area_registry (batch {batch_num} of {batch_total})
{area_registry_json}

## intents to resolve
{intents_json}

Return a JSON array — one object per intent:
[
  {{
    "intent_id": "<same intent_id from input>",
    "concept_id": "<exact concept_id from concept_registry>",
    "matched_project_ids": ["<exact area_id from area_registry>", ...],
    "project_rationale": "<tables/columns that drove selection>",
    "area_ids": ["<same as matched_project_ids>"]
  }}
]
Rules:
- matched_project_ids and area_ids must be exact area_id strings from the area_registry shown above
- concept_id must be an exact concept_id from concept_registry
- matched_project_ids: 2–4 entries; area_ids: 1–3 entries (subset of matched_project_ids)
- Every intent_id in input must appear in output
"""


def _call_llm(system_prompt: str, user_prompt: str) -> str:
    from app.core.provider import get_llm_for_type, LlmType
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = get_llm_for_type(LlmType.EXECUTOR, temperature=0.0)
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ])
    return response.content if hasattr(response, "content") else str(response)


def _parse_resolution_list(raw: str) -> list:
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    start = cleaned.find("[")
    end = cleaned.rfind("]") + 1
    if start >= 0 and end > start:
        cleaned = cleaned[start:end]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        fixed = re.sub(r",\s*([}\]])", r"\1", cleaned)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            logger.warning("MDL intent resolver: unparseable JSON (%d chars)", len(raw))
            return []


def _call_resolution_for_batch(
    concept_registry: List[dict],
    area_batch: List[dict],
    intents: List[dict],
    batch_num: int,
    batch_total: int,
) -> List[dict]:
    """Single LLM call for one batch of areas."""
    intents_json = json.dumps(
        [{"intent_id": i["intent_id"], "description": i["description"],
          "analytical_goal": i.get("analytical_goal", ""),
          "key_entities": i.get("key_entities", [])} for i in intents],
        indent=2,
    )
    prompt = _USER_PROMPT_TEMPLATE.format(
        concept_registry_json=json.dumps(concept_registry, indent=2),
        area_registry_json=json.dumps(area_batch, indent=2),
        intents_json=intents_json,
        batch_num=batch_num,
        batch_total=batch_total,
    )
    logger.info(
        "[MDL resolver] LLM call: batch %d/%d (%d areas, prompt ~%d chars)",
        batch_num, batch_total, len(area_batch), len(prompt),
    )
    raw = _call_llm(_SYSTEM_PROMPT, prompt)
    logger.debug("[MDL resolver] raw LLM response (batch %d):\n%s", batch_num, raw)
    return _parse_resolution_list(raw)


def _merge_batch_results(
    all_batch_results: List[List[dict]],
    intents: List[dict],
) -> List[dict]:
    """
    Merge results from multiple batches.
    For each intent, merge matched_project_ids / area_ids across all batches.
    When a batch has no entry for an intent, that's fine — just skip it.
    """
    merged: Dict[str, dict] = {}
    for batch_results in all_batch_results:
        for res in batch_results:
            iid = res.get("intent_id", "")
            if not iid:
                continue
            if iid not in merged:
                merged[iid] = dict(res)
            else:
                # Accumulate project/area IDs from later batches
                existing = merged[iid]
                for pid in res.get("matched_project_ids", []):
                    if pid not in existing.get("matched_project_ids", []):
                        existing.setdefault("matched_project_ids", []).append(pid)
                for aid in res.get("area_ids", []):
                    if aid not in existing.get("area_ids", []):
                        existing.setdefault("area_ids", []).append(aid)

    # Ensure every intent has at least an empty entry
    result = []
    for intent in intents:
        iid = intent.get("intent_id", "i1")
        result.append(merged.get(iid, {
            "intent_id": iid, "concept_id": "",
            "matched_project_ids": [], "area_ids": [],
        }))
    return result


# ── Hydration ─────────────────────────────────────────────────────────────────

def _hydrate_resolution(raw_res: dict, intent: dict) -> dict:
    """
    Enrich a raw LLM resolution using the enriched + base files as ground truth.
    Falls back to fuzzy matching then registry defaults on any ID mismatch.
    """
    enriched = _load_enriched()
    area_registry: List[dict] = enriched.get("area_registry", [])
    concept_registry: List[dict] = enriched.get("concept_registry", [])

    area_index: Dict[str, dict] = {a["area_id"]: a for a in area_registry}
    concept_index: Dict[str, dict] = {c["concept_id"]: c for c in concept_registry}
    known_area_ids = set(area_index.keys())
    known_concept_ids = set(concept_index.keys())

    # ── Concept ID ───────────────────────────────────────────────────────────
    concept_id = raw_res.get("concept_id", "")
    if concept_id not in known_concept_ids:
        # Fuzzy match
        match = next(
            (kid for kid in known_concept_ids
             if concept_id.lower() in kid.lower() or kid.lower() in concept_id.lower()),
            None,
        )
        if match:
            logger.warning("[MDL hydrate] fuzzy concept_id '%s' → '%s'", concept_id, match)
            concept_id = match
        elif known_concept_ids:
            concept_id = next(iter(known_concept_ids))  # last resort: first concept
            logger.warning("[MDL hydrate] unknown concept_id '%s' — defaulting to '%s'",
                           raw_res.get("concept_id"), concept_id)

    concept_meta = concept_index.get(concept_id, {})
    concept_display_name = concept_meta.get("label", concept_id)

    logger.info(
        "[MDL hydrate] intent='%s' | LLM raw: concept_id='%s', project_ids=%s, area_ids=%s",
        intent.get("intent_id", "?"),
        raw_res.get("concept_id", ""),
        raw_res.get("matched_project_ids", []),
        raw_res.get("area_ids", []),
    )

    # ── Project IDs ──────────────────────────────────────────────────────────
    raw_pids: List[str] = raw_res.get("matched_project_ids") or []
    exact_pids = [pid for pid in raw_pids if pid in known_area_ids]
    fuzzy_pids: List[str] = []
    for pid in raw_pids:
        if pid in known_area_ids:
            continue
        match = next(
            (kaid for kaid in known_area_ids
             if pid.lower() in kaid.lower() or kaid.lower() in pid.lower()),
            None,
        )
        if match and match not in exact_pids and match not in fuzzy_pids:
            fuzzy_pids.append(match)
            logger.warning("[MDL hydrate] fuzzy project_id '%s' → '%s'", pid, match)

    matched_project_ids = exact_pids + fuzzy_pids

    # Fallback: use concept's own area_ids if LLM returned nothing valid
    if not matched_project_ids:
        matched_project_ids = [
            aid for aid in concept_meta.get("area_ids", [])
            if aid in known_area_ids
        ][:4]
        logger.warning(
            "[MDL hydrate] no valid project_ids from LLM for intent '%s'/concept '%s' "
            "— using concept area_ids fallback: %s",
            intent.get("intent_id"), concept_id, matched_project_ids,
        )

    project_display_names = [area_index[pid].get("label", pid) for pid in matched_project_ids]

    # ── Area objects ─────────────────────────────────────────────────────────
    # In this schema areas = projects. Build area dicts from area_registry entries.
    raw_area_ids: List[str] = raw_res.get("area_ids") or matched_project_ids
    area_obj_ids: List[str] = []
    for aid in raw_area_ids:
        resolved = aid if aid in area_index else next(
            (kaid for kaid in area_index
             if aid.lower() in kaid.lower() or kaid.lower() in aid.lower()),
            None,
        )
        if resolved and resolved not in area_obj_ids:
            area_obj_ids.append(resolved)

    # If still empty, use matched_project_ids as areas
    if not area_obj_ids:
        area_obj_ids = matched_project_ids[:3]

    areas = []
    for aid in area_obj_ids:
        area = area_index.get(aid, {})
        primary_tables = [t["name"] for t in area.get("tables", []) if t.get("role") == "primary"]
        areas.append({
            "area_id": aid,
            "display_name": area.get("label", aid),
            "description": area.get("description", ""),
            "metrics": [],
            "kpis": [],
            "filters": [],
            "causal_paths": [],
            "dashboard_axes": [],
            "natural_language_questions": concept_meta.get("sample_questions", [])[:3],
            "data_requirements": primary_tables,
        })

    # ── Project tables metadata (for schema retrieval + area confirm) ─────────
    base_projects: Dict[str, dict] = {
        p["project_id"]: p for p in _load_base().get("projects", [])
    }
    project_tables: Dict[str, dict] = {}
    for pid in matched_project_ids:
        area = area_index.get(pid, {})
        base_p = base_projects.get(pid, {})
        primary = [t for t in area.get("tables", []) if t.get("role") == "primary"]
        supporting = [t["name"] for t in area.get("tables", []) if t.get("role") != "primary"]
        project_tables[pid] = {
            "project_id": pid,
            "title": area.get("label", pid),
            "description": area.get("description", ""),
            "concept_ids": [concept_id],
            "data_categories": [],
            "primary_tables": [
                {
                    "name": t["name"],
                    "display_name": t.get("display_name", t["name"]),
                    "description": t.get("description", ""),
                    "key_columns": t.get("key_columns", []),
                }
                for t in primary
            ],
            "supporting_table_names": supporting,
            # Richer schema info from base file if available
            "table_schemas": base_p.get("table_schemas", []),
            "knowledge_base": base_p.get("knowledge_base", ""),
        }

    return {
        "intent_id": intent.get("intent_id", raw_res.get("intent_id", "i1")),
        "description": intent.get("description", ""),
        "analytical_goal": intent.get("analytical_goal", ""),
        "key_entities": intent.get("key_entities", []),
        "concept_id": concept_id,
        "concept_display_name": concept_display_name,
        "matched_project_ids": matched_project_ids,
        "project_display_names": project_display_names,
        "project_rationale": raw_res.get("project_rationale", ""),
        "area_ids": [a["area_id"] for a in areas],
        "areas": areas,
        "project_tables": project_tables,
    }


# ── Public function ────────────────────────────────────────────────────────────

def resolve_intents_to_projects_and_areas(
    intents: List[dict],
    datasource_id: str = "",
) -> List[dict]:
    """
    For each intent, use the enriched + base metadata files (no pruning) to
    identify specific projects and areas via LLM.

    Batches area_registry if the combined payload exceeds BATCH_CHAR_LIMIT.
    Returns hydrated IntentResolution dicts compatible with the downstream graph.
    """
    if not intents:
        return []

    concept_registry = _get_concept_registry()
    merged_areas = _build_merged_areas()

    concept_json = json.dumps(concept_registry, indent=2)
    areas_json = json.dumps(merged_areas, indent=2)
    total_chars = len(concept_json) + len(areas_json)

    logger.info(
        "[MDL resolver] payload: %d concepts, %d areas, ~%d chars total — %s",
        len(concept_registry), len(merged_areas), total_chars,
        "single call" if total_chars <= BATCH_CHAR_LIMIT else f"batching by {BATCH_SIZE}",
    )

    # ── LLM call(s) ──────────────────────────────────────────────────────────
    if total_chars <= BATCH_CHAR_LIMIT:
        raw_resolutions = _call_resolution_for_batch(
            concept_registry, merged_areas, intents, batch_num=1, batch_total=1,
        )
    else:
        batches = [
            merged_areas[i:i + BATCH_SIZE]
            for i in range(0, len(merged_areas), BATCH_SIZE)
        ]
        all_batch_results = []
        for i, batch in enumerate(batches, start=1):
            try:
                batch_raw = _call_resolution_for_batch(
                    concept_registry, batch, intents,
                    batch_num=i, batch_total=len(batches),
                )
                all_batch_results.append(batch_raw)
            except Exception as exc:
                logger.error("[MDL resolver] batch %d/%d failed: %s", i, len(batches), exc)
                all_batch_results.append([])

        raw_resolutions = _merge_batch_results(all_batch_results, intents)

    # Index by intent_id for safe lookup
    raw_by_intent: Dict[str, dict] = {
        r.get("intent_id", ""): r for r in raw_resolutions if isinstance(r, dict)
    }

    # ── Hydrate ──────────────────────────────────────────────────────────────
    result = []
    for intent in intents:
        iid = intent.get("intent_id", "i1")
        raw_res = raw_by_intent.get(
            iid,
            {"intent_id": iid, "concept_id": "", "matched_project_ids": [], "area_ids": []},
        )
        hydrated = _hydrate_resolution(raw_res, intent)
        result.append(hydrated)

        logger.info(
            "[MDL resolver] intent '%s' → concept='%s' (%s) | projects=%s | areas=%s",
            iid,
            hydrated.get("concept_id", ""),
            hydrated.get("concept_display_name", ""),
            hydrated.get("matched_project_ids", []),
            [f"{a.get('area_id','')} ({a.get('display_name','')})" for a in hydrated.get("areas", [])],
        )
        for pid, tdata in hydrated.get("project_tables", {}).items():
            logger.info(
                "[MDL resolver]   project '%s' (%s): primary_tables=%s",
                pid, tdata.get("title", pid),
                [t.get("name", "") for t in tdata.get("primary_tables", [])],
            )

    logger.info(
        "[MDL resolver] resolved %d intent(s); projects per intent: %s",
        len(result),
        [len(r["matched_project_ids"]) for r in result],
    )
    return result

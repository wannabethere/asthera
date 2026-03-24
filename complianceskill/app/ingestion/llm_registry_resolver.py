"""
llm_registry_resolver.py

LLM-based concept and area resolution.

The full catalog is small (10 concepts × ~3 areas = ~30 items), so we pass it all
to the LLM and let it rank the best matches for the user's question.
No Qdrant collections needed, no keyword fallbacks.

Public API
----------
resolve_all_via_llm(user_query, datasource_id, top_k_concepts) ->
    (List[ConceptMatch], Dict[concept_id, List[RecommendationAreaMatch]])
"""

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.ingestion.registry_vector_lookup import (
    CONCEPT_REC_REGISTRY_PATH,
    SOURCE_CONCEPT_REGISTRY_PATH,
    ConceptMatch,
    RecommendationAreaMatch,
)

logger = logging.getLogger(__name__)


# ── Registry loading (cached) ──────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _load_concept_registry() -> dict:
    if SOURCE_CONCEPT_REGISTRY_PATH.exists():
        with open(SOURCE_CONCEPT_REGISTRY_PATH) as f:
            return json.load(f)
    return {}


@lru_cache(maxsize=1)
def _load_area_registry() -> dict:
    if CONCEPT_REC_REGISTRY_PATH.exists():
        with open(CONCEPT_REC_REGISTRY_PATH) as f:
            return json.load(f)
    return {}


# ── Catalog builder ────────────────────────────────────────────────────────────

def _build_catalog_for_prompt(datasource_id: Optional[str] = None) -> str:
    """Build a compact text catalog of all concepts and their areas for the LLM prompt."""
    concept_reg = _load_concept_registry()
    area_reg = _load_area_registry()

    key_concepts = concept_reg.get("key_concepts", [])
    source_map = concept_reg.get("source_concept_map", {})
    rec_map = area_reg.get("concept_recommendations", {})

    lines = []
    for c in key_concepts:
        cid = c["concept_id"]
        lines.append(f"\n## Concept: {cid}")
        lines.append(f"Name: {c['display_name']}")
        lines.append(f"Description: {c.get('description', '')}")
        bqs = c.get("business_questions", [])
        if bqs:
            lines.append("Example questions: " + " | ".join(bqs))

        # Areas for this concept
        areas = rec_map.get(cid, {}).get("recommendation_areas", [])
        for a in areas:
            lines.append(f"  - Area [{a['area_id']}]: {a['display_name']}")
            lines.append(f"    {a.get('description', '')}")
            nqs = a.get("natural_language_questions", [])
            if nqs:
                lines.append(f"    Sample questions: " + " | ".join(nqs[:2]))

    return "\n".join(lines)


# ── LLM call ───────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are an analytics routing specialist for an LMS (Learning Management System) analytics platform.
Your task: given a user's analytics question, identify their UNDERLYING ANALYTICAL GOAL, then find which
concepts and areas in the catalog best provide the CAPABILITY to achieve that goal.

CRITICAL — do NOT do keyword matching. Instead, reason as follows:
1. What decision, insight, or measurement does the user actually need?
2. Which concept/area provides the ANALYTICAL CAPABILITY to answer that need?
3. Is the vocabulary in the user's question masking a deeper analytical capability match?
4. Are there cross-concept situations where 2+ concepts together give a fuller picture?

Example of correct reasoning:
  User question: "skill compliance training gaps over the last year"
  Goal: measure the GAP between expected and actual compliance training completion, broken down by skill
  Capability needed: gap analysis between required skills and actual completion — that is "skill_gap_analysis" under "workforce_capability", potentially enriched by "compliance_training/completion_trends" for the compliance angle.
  Wrong answer: routing only to "compliance_training" because the phrase "compliance training" appears literally.

Return ONLY valid JSON — no markdown, no explanation outside the JSON object.
"""

_USER_PROMPT_TEMPLATE = """\
Available analytics catalog:
{catalog}

User question: "{user_query}"

Reason step by step:
Step 1 — What is the user's analytical GOAL? (what decision/insight/measurement do they need?)
Step 2 — For each concept and area: what ANALYTICAL CAPABILITY does it provide?
Step 3 — Which concept(s) and area(s) best provide the capability to meet the goal?
Step 4 — Are there cross-concept combinations that together answer the goal more completely?

Return JSON with this exact shape:
{{
  "goal_reasoning": "<1-2 sentences: what is the user's analytical goal and what capability is needed?>",
  "concepts": [
    {{"concept_id": "<id>", "score": <0.0-1.0>, "reasoning": "<why this concept's capability matches the goal, NOT keyword overlap>"}}
  ],
  "areas": [
    {{"concept_id": "<id>", "area_id": "<id>", "score": <0.0-1.0>, "capability_match": "<what analytical capability this area provides for the goal>"}}
  ],
  "cross_concept_note": "<if multiple concepts together answer the goal better, explain; otherwise empty string>"
}}

Rules:
- Include up to {top_k} concepts ranked by CAPABILITY match (score >= 0.3 to include).
- For each included concept, include its best 1-3 matching areas.
- Scores must be floats between 0.0 and 1.0.
- Use ONLY concept_ids and area_ids from the catalog above.
- If the goal requires cross-concept analysis, include ALL relevant concepts.
- Score the area that directly provides the needed analytical capability HIGHEST, even if vocabulary doesn't overlap with the user's question.
- A specialized area that directly answers the goal should score higher than a general area with keyword overlap.
"""


def _call_llm(prompt: str) -> str:
    """Call the configured LLM and return the text response."""
    from app.core.provider import get_llm_for_type, LlmType
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = get_llm_for_type(LlmType.EXECUTOR, temperature=0.0)
    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]
    response = llm.invoke(messages)
    return response.content if hasattr(response, "content") else str(response)


def _parse_llm_response(raw: str) -> dict:
    """Extract JSON from LLM response, stripping any markdown fences."""
    # Strip ```json ... ``` if present
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    # Find first { ... } block
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start >= 0 and end > start:
        cleaned = cleaned[start:end]
    return json.loads(cleaned)


# ── Public function ────────────────────────────────────────────────────────────

def resolve_all_via_llm(
    user_query: str,
    datasource_id: Optional[str] = None,
    top_k_concepts: int = 3,
) -> Tuple[List[ConceptMatch], Dict[str, List[RecommendationAreaMatch]]]:
    """
    Use LLM to match user query against the full concept + area catalog.

    Returns:
        concepts: ranked list of ConceptMatch (same type used by the rest of the planner)
        areas_by_concept: dict mapping concept_id -> list of RecommendationAreaMatch
    """
    concept_reg = _load_concept_registry()
    area_reg = _load_area_registry()
    source_map = concept_reg.get("source_concept_map", {})
    key_concepts_list = concept_reg.get("key_concepts", [])
    key_concepts_by_id = {c["concept_id"]: c for c in key_concepts_list}
    rec_map = area_reg.get("concept_recommendations", {})

    catalog = _build_catalog_for_prompt(datasource_id)
    prompt = _USER_PROMPT_TEMPLATE.format(
        catalog=catalog,
        user_query=user_query,
        top_k=top_k_concepts,
    )

    raw = _call_llm(prompt)
    logger.debug(f"LLM registry resolver raw response:\n{raw}")

    data = _parse_llm_response(raw)

    if data.get("goal_reasoning"):
        logger.info(f"LLM goal reasoning: {data['goal_reasoning']}")
    if data.get("cross_concept_note"):
        logger.info(f"LLM cross-concept note: {data['cross_concept_note']}")

    # ── Build ConceptMatch list ────────────────────────────────────────────────
    concepts: List[ConceptMatch] = []
    for item in data.get("concepts", [])[:top_k_concepts]:
        cid = item.get("concept_id", "")
        score = float(item.get("score", 0.5))
        c_meta = key_concepts_by_id.get(cid, {})
        if not c_meta:
            logger.warning(f"LLM returned unknown concept_id '{cid}' — skipping")
            continue

        # Pull project_ids from source_concept_map if available
        # mdl_table_refs intentionally left empty — L3 table resolution happens later
        # in the downstream workflow once the specific metric/query is known.
        ds_key = datasource_id or next(iter(source_map), None)
        ds_concepts = source_map.get(ds_key, {}) if ds_key else {}
        ds_entry = ds_concepts.get(cid, {})

        concepts.append(ConceptMatch(
            concept_id=cid,
            source_id=ds_key or "",
            project_ids=ds_entry.get("project_ids", []),
            display_name=c_meta.get("display_name", cid),
            domain=c_meta.get("domain", "lms"),
            score=score,
            raw_score=score,
            coverage_confidence=ds_entry.get("coverage_confidence", score),
            mdl_table_refs=[],
            api_categories=ds_entry.get("api_categories", []),
            trigger_keywords=c_meta.get("trigger_keywords", []),
            via_fallback=False,
        ))

    # ── Build areas_by_concept dict ────────────────────────────────────────────
    areas_by_concept: Dict[str, List[RecommendationAreaMatch]] = {}
    area_items = data.get("areas", [])

    # Index areas from registry for fast lookup
    def _area_from_registry(concept_id: str, area_id: str) -> Optional[dict]:
        for a in rec_map.get(concept_id, {}).get("recommendation_areas", []):
            if a["area_id"] == area_id:
                return a
        return None

    for item in area_items:
        cid = item.get("concept_id", "")
        aid = item.get("area_id", "")
        score = float(item.get("score", 0.5))
        area_data = _area_from_registry(cid, aid)
        if not area_data:
            logger.warning(f"LLM returned unknown area '{cid}/{aid}' — skipping")
            continue

        match = RecommendationAreaMatch(
            area_id=aid,
            concept_id=cid,
            display_name=area_data.get("display_name", aid),
            description=area_data.get("description", ""),
            score=score,
            metrics=area_data.get("metrics", []),
            kpis=area_data.get("kpis", []),
            filters=area_data.get("filters", []),
            dashboard_axes=area_data.get("dashboard_axes", []),
            causal_paths=area_data.get("causal_paths", []),
            natural_language_questions=area_data.get("natural_language_questions", []),
            data_requirements=area_data.get("data_requirements", []),
            via_fallback=False,
        )
        areas_by_concept.setdefault(cid, []).append(match)

    logger.info(
        f"LLM resolver: {len(concepts)} concepts, "
        f"{sum(len(v) for v in areas_by_concept.values())} areas "
        f"for query: {user_query[:80]!r}"
    )
    return concepts, areas_by_concept

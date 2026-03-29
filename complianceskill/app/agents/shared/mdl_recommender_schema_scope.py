"""Focus-area + concept-scoped MDL retrieval for metrics recommenders and schema nodes."""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _walk_concept_strings(obj: Any, out: List[str], depth: int = 0) -> None:
    if depth > 8 or len(out) > 60:
        return
    if isinstance(obj, str):
        s = obj.strip()
        if len(s) > 1:
            out.append(s)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() not in ("confidence", "score", "id"):
                sk = k.replace("_", " ").strip()
                if len(sk) > 1:
                    out.append(sk)
            _walk_concept_strings(v, out, depth + 1)
    elif isinstance(obj, (list, tuple)):
        for item in obj[:40]:
            _walk_concept_strings(item, out, depth + 1)


def build_area_scoped_mdl_fallback_query(state: Dict[str, Any]) -> str:
    """
    Build a single semantic query from focus areas, concept mapping, domains, and user text.
    Used as MDL vector / rephrase input so retrieved schemas align with the conversation scope.
    """
    parts: List[str] = []

    for x in state.get("focus_area_categories") or []:
        if x:
            parts.append(str(x).replace("_", " "))

    de = state.get("data_enrichment") or {}
    for fa in de.get("suggested_focus_areas") or []:
        parts.append(str(fa).replace("_", " "))

    for fa in state.get("resolved_focus_areas") or []:
        if isinstance(fa, dict):
            for c in fa.get("categories") or []:
                parts.append(str(c).replace("_", " "))
            if fa.get("name"):
                parts.append(str(fa["name"]))
        elif fa:
            parts.append(str(fa).replace("_", " "))

    for x in state.get("causal_graph_boost_focus_areas") or []:
        parts.append(str(x).replace("_", " "))

    sig = (state.get("causal_signals") or {}).get("derived_focus_area")
    if sig:
        parts.append(str(sig).replace("_", " "))

    cap_hints = (state.get("capability_retrieval_hints") or "").strip()
    if cap_hints:
        parts.append(cap_hints)

    _walk_concept_strings(state.get("lexy_stage_2_concept_mapping"), parts)

    dc = state.get("domain_classification")
    if isinstance(dc, dict):
        for k in dc.keys():
            parts.append(str(k).replace("_", " "))

    for d in state.get("active_domains") or []:
        parts.append(str(d).replace("_", " "))

    uq = (state.get("user_query") or "").strip()
    if uq:
        parts.append(uq)

    seen: set[str] = set()
    deduped: List[str] = []
    for p in parts:
        s = str(p).strip()
        if len(s) < 2:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(s)

    return " ".join(deduped).strip()


def merge_mdl_fallback_query(existing_fallback: str, state: Dict[str, Any]) -> str:
    """Prepend area/concept terms to an existing fallback (e.g. focus_area_categories + user_query)."""
    area = build_area_scoped_mdl_fallback_query(state)
    chunks = [c.strip() for c in (area, existing_fallback or "") if c and str(c).strip()]
    return " ".join(chunks).strip()


def collect_schema_name_hints_from_state(
    state: Dict[str, Any],
    metrics: Optional[List[Dict[str, Any]]] = None,
) -> List[str]:
    names: List[str] = []
    mets = metrics if metrics is not None else (state.get("resolved_metrics") or [])
    for m in mets:
        for sn in m.get("source_schemas") or []:
            if sn and sn not in names:
                names.append(str(sn))
    cp = state.get("compliance_profile") or {}
    for t in (cp.get("data_requirements") or []) + (cp.get("active_mdl_tables") or [])[:20]:
        if t and t not in names:
            names.append(str(t))
    return names


def refresh_csod_scored_context_schemas(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return scored_context with resolved_schemas.

    If csod_resolved_schemas already exists in state (populated by the upstream
    csod_mdl_schema_retrieval node), reuse it instead of making a duplicate
    Qdrant round-trip.  Only re-fetch when schemas are missing.
    """
    from app.agents.csod.csod_tool_integration import csod_retrieve_mdl_schemas

    raw = state.get("csod_scored_context") or {}
    scored: Dict[str, Any] = copy.deepcopy(raw) if raw else {
        "scored_metrics": [],
        "resolved_schemas": [],
        "gold_standard_tables": [],
    }
    for k in ("scored_metrics", "resolved_schemas", "gold_standard_tables"):
        scored.setdefault(k, raw.get(k) if isinstance(raw, dict) else [])

    # ── Fast path: reuse schemas already resolved by csod_mdl_schema_retrieval ──
    existing_schemas = state.get("csod_resolved_schemas") or scored.get("resolved_schemas") or []
    if existing_schemas:
        logger.info(
            "refresh_csod_scored_context_schemas: reusing %d schemas already in state (skipping MDL re-fetch)",
            len(existing_schemas),
        )
        scored["resolved_schemas"] = existing_schemas
        return scored

    # ── Slow path: no schemas in state — fetch from MDL ──────────────────────
    logger.info("refresh_csod_scored_context_schemas: no schemas in state, fetching from MDL")

    fq = build_area_scoped_mdl_fallback_query(state)
    if not fq.strip():
        fq = (state.get("user_query") or "").strip()

    metrics_for_hints = scored.get("scored_metrics") or state.get("resolved_metrics") or []
    schema_names = collect_schema_name_hints_from_state(state, metrics_for_hints)
    selected = state.get("csod_data_sources_in_scope") or state.get("selected_data_sources") or []

    try:
        data = csod_retrieve_mdl_schemas(
            schema_names=schema_names,
            fallback_query=fq,
            limit=15,
            selected_data_sources=selected,
            silver_gold_tables_only=state.get("silver_gold_tables_only", False),
            planner_output=state.get("calculation_plan"),
            original_query=state.get("user_query", ""),
        )
        fresh = data.get("schemas") or []
    except Exception as e:
        logger.warning("refresh_csod_scored_context_schemas: retrieval failed: %s", e)
        fresh = []

    if fresh:
        scored["resolved_schemas"] = fresh
        state.setdefault("csod_scored_context", {})
        if not isinstance(state["csod_scored_context"], dict):
            state["csod_scored_context"] = {}
        state["csod_scored_context"]["resolved_schemas"] = fresh
        state["csod_resolved_schemas"] = fresh

    return scored


def retrieve_area_scoped_dt_schemas(state: Dict[str, Any], limit: int = 15) -> List[Dict[str, Any]]:
    """DT / base-pipeline MDL retrieval using the same focus + concept query."""
    from app.agents.mdlworkflows.dt_tool_integration import dt_retrieve_mdl_schemas

    fq = build_area_scoped_mdl_fallback_query(state)
    if not fq.strip():
        fq = (state.get("user_query") or "").strip()

    schema_names = collect_schema_name_hints_from_state(state, state.get("resolved_metrics") or [])
    selected = state.get("dt_data_sources_in_scope") or state.get("selected_data_sources") or []

    try:
        data = dt_retrieve_mdl_schemas(
            schema_names=schema_names,
            fallback_query=fq,
            limit=limit,
            selected_data_sources=selected,
            silver_gold_tables_only=state.get("silver_gold_tables_only", False),
            planner_output=state.get("calculation_plan") or state.get("dt_planner_reasoning"),
            original_query=state.get("user_query", ""),
            workflow_type="dt",
            focus_area_queries=None,
            focus_area_categories=state.get("focus_area_categories") or None,
        )
        return data.get("schemas") or []
    except Exception as e:
        logger.warning("retrieve_area_scoped_dt_schemas failed: %s", e)
        return []

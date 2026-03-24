"""Backfill Lexy / MDL anchors from L1 concepts when planner chain skipped resolution."""

from __future__ import annotations

from typing import Any, Dict, List

from langchain_core.messages import AIMessage

from app.agents.csod.csod_nodes._helpers import CSOD_State, _csod_log_step, logger
from app.agents.csod.csod_query_utils import effective_user_query
from app.ingestion.registry_vector_lookup import resolve_intent_to_concept


def _has_mdl_anchors(state: CSOD_State) -> bool:
    """Skip L1 resolve when we already have table/requirement hints or planner concept rows."""
    if state.get("csod_resolved_mdl_table_refs"):
        return True
    profile = state.get("compliance_profile") or {}
    if profile.get("active_mdl_tables") or profile.get("data_requirements"):
        return True
    if state.get("csod_concept_matches") and (
        state.get("csod_primary_project_id") or state.get("active_project_id")
    ):
        return True
    return False


def csod_concept_context_node(state: CSOD_State) -> CSOD_State:
    """
    After intent classification, ensure we have project / MDL table hints for the spine.

    Conversation Phase 0 normally fills this; direct or partial invokes may not. Uses the same
    L1 resolver as the planner's concept_resolver_node (no user interrupt here).
    """
    if _has_mdl_anchors(state):
        return state

    uq = effective_user_query(state)
    if not uq:
        logger.warning("csod_concept_context: no user question in state or messages; skipping L1 resolve")
        return state

    state["user_query"] = uq

    ds = state.get("csod_selected_datasource") or ""
    if not ds:
        sds = state.get("selected_data_sources") or []
        if isinstance(sds, list) and sds:
            ds = str(sds[0])

    connected = [ds] if ds else []

    try:
        matches = resolve_intent_to_concept(
            user_query=uq,
            connected_source_ids=connected,
            top_k=5,
        )
    except Exception as e:
        logger.warning("csod_concept_context: resolve_intent_to_concept failed: %s", e, exc_info=True)
        return state

    if not matches:
        logger.info("csod_concept_context: no L1 concept matches for query")
        return state

    all_pids: List[str] = []
    all_refs: List[str] = []
    selected_rows: List[Dict[str, Any]] = []
    for m in matches[:3]:
        selected_rows.append(
            {
                "concept_id": m.concept_id,
                "display_name": m.display_name,
                "score": m.score,
                "coverage_confidence": m.coverage_confidence,
            }
        )
        all_pids.extend(m.project_ids or [])
        all_refs.extend(m.mdl_table_refs or [])

    all_pids = list(dict.fromkeys(all_pids))
    all_refs = list(dict.fromkeys(all_refs))

    state["csod_selected_concepts"] = selected_rows
    state["csod_concept_matches"] = [
        {
            "concept_id": m.concept_id,
            "display_name": m.display_name,
            "score": m.score,
            "coverage_confidence": m.coverage_confidence,
            "project_ids": m.project_ids,
            "mdl_table_refs": m.mdl_table_refs,
        }
        for m in matches
    ]
    state["csod_resolved_project_ids"] = all_pids
    state["csod_resolved_mdl_table_refs"] = all_refs
    if all_pids:
        state["csod_primary_project_id"] = all_pids[0]
        if not state.get("active_project_id"):
            state["active_project_id"] = all_pids[0]

    profile = dict(state.get("compliance_profile") or {})
    if all_refs:
        existing = list(profile.get("active_mdl_tables") or [])
        profile["active_mdl_tables"] = list(dict.fromkeys([*existing, *all_refs]))
    prof_sel = [str(x) for x in (profile.get("selected_concepts") or [])]
    new_cids = [str(r["concept_id"]) for r in selected_rows if r.get("concept_id")]
    profile["selected_concepts"] = list(dict.fromkeys([*prof_sel, *new_cids]))
    state["compliance_profile"] = profile

    _csod_log_step(
        state,
        "csod_concept_context",
        "csod_concept_context",
        inputs={"user_query_len": len(uq), "datasource": ds or "(any)"},
        outputs={
            "concepts": len(selected_rows),
            "project_ids": len(all_pids),
            "mdl_refs": len(all_refs),
        },
    )
    state["messages"].append(
        AIMessage(
            content=(
                f"Concept context: {len(selected_rows)} topic(s), "
                f"{len(all_pids)} project id(s), {len(all_refs)} MDL ref(s)"
            )
        )
    )
    return state

"""
CSOD Intent + Project Selection Node

Replaces the (concept_resolver → concept_confirm) pair in the CSOD planner graph.

Shows the user an INTENT_SELECTION checkpoint that presents each analytical
intent alongside:
  - Its matched concept, specific projects, and top recommendation areas
  - A SIGNAL EXTRACTION panel with dynamic key/value signals extracted by the
    intent splitter (e.g. terminal_metric, urgency, analysis_type, implicit…)
    — label names and values are fully LLM-generated per query, not hardcoded.

On resume the node populates backward-compatible state keys so that the remainder
of the graph (preliminary_area_matcher → scoping → area_matcher → area_confirm →
metric_narration → workflow_router) works without modification.
"""
import logging
from typing import Any, Dict, List

from app.agents.state import EnhancedCompliancePipelineState
from app.conversation.config import VerticalConversationConfig
from app.conversation.turn import (
    ConversationCheckpoint,
    ConversationTurn,
    TurnOutputType,
)

logger = logging.getLogger(__name__)


def csod_intent_confirm_node(
    state: EnhancedCompliancePipelineState,
    config: VerticalConversationConfig,
) -> EnhancedCompliancePipelineState:
    """
    Intent + project selection checkpoint for the CSOD planner.

    State reads:  csod_intent_resolutions, csod_selected_intent_ids
    State writes: csod_conversation_checkpoint            (first pass)
                  csod_confirmed_concept_ids,
                  csod_selected_concepts, csod_concept_matches,
                  csod_resolved_project_ids, csod_primary_project_id,
                  csod_llm_resolved_areas, csod_concepts_confirmed  (resume)
    resume_with_field: csod_selected_intent_ids
    """
    resolutions: List[Dict[str, Any]] = state.get("csod_intent_resolutions") or []

    # ── Direct mode auto-confirm: skip intent_selection checkpoint ──
    # In Direct (planner_only) mode, the user just wants scope narrowing + a
    # rephrased query. Auto-pick all resolved intents so the UI only shows
    # concept/area selection downstream.
    if state.get("csod_planner_only") and resolutions and not _get_selected_intent_ids(state):
        all_intent_ids = [r["intent_id"] for r in resolutions if r.get("intent_id")]
        if all_intent_ids:
            logger.info("csod_intent_confirm: planner_only mode — auto-selecting all intents %s", all_intent_ids)
            state["csod_selected_intent_ids"] = all_intent_ids
            return _apply_selections(state, resolutions, all_intent_ids)

    # ── Resume path ───────────────────────────────────────────────────────────
    selected_intent_ids = _get_selected_intent_ids(state)

    if selected_intent_ids:
        return _apply_selections(state, resolutions, selected_intent_ids)

    # ── First pass — build checkpoint ─────────────────────────────────────────
    if not resolutions:
        checkpoint = ConversationCheckpoint(
            phase="intent_selection",
            turn=ConversationTurn(
                phase="intent_selection",
                turn_type=TurnOutputType.INTENT_SELECTION,
                message=(
                    "I couldn't identify a clear analysis area for your question. "
                    "Could you rephrase it or add more context about what you're trying to understand?"
                ),
                options=[{"id": "rephrase", "label": "Let me rephrase", "action": "rephrase"}],
            ),
            resume_with_field="user_query",
        )
        state["csod_conversation_checkpoint"] = checkpoint.to_dict()
        state["csod_checkpoint_resolved"] = False
        return state

    # Merge signals from csod_intent_splits onto the matching resolution
    intent_splits: List[Dict[str, Any]] = state.get("csod_intent_splits") or []
    splits_by_id: Dict[str, Dict[str, Any]] = {s["intent_id"]: s for s in intent_splits}
    resolutions = _attach_signals(resolutions, splits_by_id)

    options = _build_options(resolutions)
    n = len(resolutions)
    message = (
        "Based on your question, here's the analysis area I found. "
        "Confirm to proceed or rephrase if this isn't what you meant:"
        if n == 1
        else (
            f"I found {n} distinct analytical angles in your question. "
            "Select the one(s) you'd like to explore:"
        )
    )

    # Build a flat signal_map keyed by intent_id for quick frontend access
    signal_map = {
        r["intent_id"]: r.get("extracted_signals", [])
        for r in resolutions
    }

    checkpoint = ConversationCheckpoint(
        phase="intent_selection",
        turn=ConversationTurn(
            phase="intent_selection",
            turn_type=TurnOutputType.INTENT_SELECTION,
            message=message,
            options=options,
            metadata={
                "intent_resolutions": resolutions,
                "signal_map": signal_map,          # {intent_id: [{label, value}, ...]}
            },
        ),
        resume_with_field="csod_selected_intent_ids",
    )
    state["csod_conversation_checkpoint"] = checkpoint.to_dict()
    state["csod_checkpoint_resolved"] = False

    logger.info(
        "csod_intent_confirm: checkpoint created with %d option(s); signals per intent: %s",
        len(options) - 1,  # subtract rephrase
        {iid: [s["label"] for s in sigs] for iid, sigs in signal_map.items()},
    )
    return state


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_selected_intent_ids(state: EnhancedCompliancePipelineState) -> List[str]:
    """Extract selected intent IDs from multiple possible resume paths."""
    ids = state.get("csod_selected_intent_ids")
    if ids and isinstance(ids, list):
        return [str(x) for x in ids if x]

    cr = (state.get("csod_checkpoint_responses") or {}).get("intent_confirm")
    if isinstance(cr, dict):
        ids = cr.get("csod_selected_intent_ids")
        if ids and isinstance(ids, list):
            return [str(x) for x in ids if x]

    # Already confirmed downstream — derive from existing resolutions so we don't recreate the checkpoint
    if state.get("csod_concepts_confirmed") and state.get("csod_intent_resolutions"):
        confirmed = state.get("csod_confirmed_concept_ids") or []
        if confirmed:
            confirmed_set = set(str(c) for c in confirmed)
            resolutions = state.get("csod_intent_resolutions") or []
            return [r["intent_id"] for r in resolutions if r.get("concept_id") in confirmed_set]

    return []


def _attach_signals(
    resolutions: List[Dict[str, Any]],
    splits_by_id: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Attach extracted_signals from intent_splits onto each resolution.
    Signals live on the split (intent_splitter output), not on the resolution
    (mdl_intent_resolver output), so we merge them here by intent_id.
    """
    for r in resolutions:
        iid = r.get("intent_id", "")
        split = splits_by_id.get(iid, {})
        r.setdefault("extracted_signals", split.get("extracted_signals") or [])
    return resolutions


def _build_options(resolutions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build the options list for the INTENT_SELECTION checkpoint.

    Each option carries:
    - Standard resolution fields (concept, projects, areas, metrics)
    - extracted_signals: [{label, value}] — dynamic per-intent signals
      for the frontend's Signal Extraction panel
    """
    options = []
    for r in resolutions:
        first_area = r.get("areas", [{}])[0] if r.get("areas") else {}
        top_metrics = (first_area.get("metrics") or [])[:3]

        options.append({
            "option_id": r["intent_id"],
            "id": r["intent_id"],
            "label": r.get("concept_display_name", r.get("concept_id", r["intent_id"])),
            "description": r.get("description", ""),
            "analytical_goal": r.get("analytical_goal", ""),
            "concept_id": r.get("concept_id", ""),
            "concept_display_name": r.get("concept_display_name", ""),
            "project_ids": r.get("matched_project_ids", []),
            "project_display_names": r.get("project_display_names", []),
            "project_rationale": r.get("project_rationale", ""),
            "area_ids": r.get("area_ids", []),
            "area_display_names": [a.get("display_name", "") for a in r.get("areas", [])],
            "top_metrics": top_metrics,
            # Full MDL table details for the matched projects: {project_id: {title, primary_tables, ...}}
            "project_tables": r.get("project_tables", {}),
            # Signal Extraction panel data — dynamic labels/values from LLM
            "extracted_signals": r.get("extracted_signals", []),
            "action": "select",
        })

    options.append({"id": "rephrase", "label": "Let me rephrase", "action": "rephrase"})
    return options


def _apply_selections(
    state: EnhancedCompliancePipelineState,
    resolutions: List[Dict[str, Any]],
    selected_intent_ids: List[str],
) -> EnhancedCompliancePipelineState:
    """
    After user selects intent(s): populate backward-compatible state keys so that
    preliminary_area_matcher, area_matcher, and the rest of the graph work unchanged.
    """
    selected_ids_set = set(selected_intent_ids)
    selected = [r for r in resolutions if r.get("intent_id") in selected_ids_set]

    if not selected and resolutions:
        selected = [resolutions[0]]
        logger.warning(
            "csod_intent_confirm resume: selected_intent_ids %s not found in resolutions — using first",
            selected_intent_ids,
        )

    # ── Concept keys ──────────────────────────────────────────────────────────
    seen_concepts: Dict[str, bool] = {}
    concept_matches = []
    selected_concepts = []
    for r in selected:
        cid = r.get("concept_id", "")
        if not cid or cid in seen_concepts:
            continue
        seen_concepts[cid] = True
        concept_matches.append({
            "concept_id": cid,
            "display_name": r.get("concept_display_name", cid),
            "score": 1.0,
            "coverage_confidence": 0.9,
            "project_ids": r.get("matched_project_ids", []),
            "mdl_table_refs": [],
        })
        selected_concepts.append({
            "concept_id": cid,
            "display_name": r.get("concept_display_name", cid),
            "score": 1.0,
            "coverage_confidence": 0.9,
        })

    confirmed_concept_ids = list(seen_concepts.keys())

    # ── Project keys + MDL table metadata ────────────────────────────────────
    all_project_ids: List[str] = []
    merged_project_tables: Dict[str, dict] = {}
    for r in selected:
        for pid in r.get("matched_project_ids", []):
            if pid not in all_project_ids:
                all_project_ids.append(pid)
        # Merge project_tables from each selected resolution (keyed by project_id)
        for pid, tdata in (r.get("project_tables") or {}).items():
            if pid not in merged_project_tables:
                merged_project_tables[pid] = tdata

    # ── LLM-resolved areas (keyed by concept_id for area_matcher_node) ────────
    llm_resolved_areas: Dict[str, List[dict]] = {}
    for r in selected:
        cid = r.get("concept_id", "")
        if not cid:
            continue
        if cid not in llm_resolved_areas:
            llm_resolved_areas[cid] = []
        for a in r.get("areas", []):
            area_id = a.get("area_id", "")
            if not area_id:
                continue  # skip area objects with empty area_id — they cause silent misses downstream
            llm_resolved_areas[cid].append({
                "area_id": area_id,
                "concept_id": cid,
                "display_name": a.get("display_name", ""),
                "description": a.get("description", ""),
                "score": 1.0,
                "metrics": a.get("metrics", []),
                "kpis": a.get("kpis", []),
                "filters": a.get("filters", []),
                "causal_paths": a.get("causal_paths", []),
                "dashboard_axes": a.get("dashboard_axes", []),
                "natural_language_questions": a.get("natural_language_questions", []),
                "data_requirements": a.get("data_requirements", []),
            })

    # ── Registry fallback: if resolutions carried no usable areas, go to registry directly ──
    # This covers: LLM returned wrong area_ids, hydration produced empty lists, or areas
    # field was absent from old checkpoint state.
    from app.ingestion.mdl_intent_resolver import _load_area_registry
    area_reg = _load_area_registry()
    rec_map = area_reg.get("concept_recommendations", {})

    for cid in confirmed_concept_ids:
        if llm_resolved_areas.get(cid):
            continue  # already have valid areas for this concept
        concept_areas = rec_map.get(cid, {}).get("recommendation_areas", [])
        if concept_areas:
            llm_resolved_areas[cid] = [
                {
                    "area_id": a["area_id"],
                    "concept_id": cid,
                    "display_name": a.get("display_name", ""),
                    "description": a.get("description", ""),
                    "score": 1.0,
                    "metrics": a.get("metrics", []),
                    "kpis": a.get("kpis", []),
                    "filters": a.get("filters", []),
                    "causal_paths": a.get("causal_paths", []),
                    "dashboard_axes": a.get("dashboard_axes", []),
                    "natural_language_questions": a.get("natural_language_questions", []),
                    "data_requirements": a.get("data_requirements", []),
                }
                for a in concept_areas[:3]
                if a.get("area_id")
            ]
            logger.warning(
                "csod_intent_confirm: resolutions had no usable areas for concept '%s' "
                "— populated %d area(s) directly from registry",
                cid, len(llm_resolved_areas[cid]),
            )
        else:
            logger.error(
                "csod_intent_confirm: concept '%s' has no areas in registry either — "
                "area_confirm will hit fallback. Check concept_id validity.",
                cid,
            )

    # ── Signals — merge from intent splits ────────────────────────────────────
    intent_splits: List[Dict[str, Any]] = state.get("csod_intent_splits") or []
    splits_by_id: Dict[str, Dict[str, Any]] = {s["intent_id"]: s for s in intent_splits}
    selected_signals: List[dict] = []
    for iid in selected_intent_ids:
        split = splits_by_id.get(iid, {})
        selected_signals.extend(split.get("extracted_signals") or [])

    # ── Write state ───────────────────────────────────────────────────────────
    state["csod_selected_intent_ids"] = selected_intent_ids
    state["csod_concept_matches"] = concept_matches
    state["csod_selected_concepts"] = selected_concepts
    state["csod_confirmed_concept_ids"] = confirmed_concept_ids
    state["csod_resolved_project_ids"] = all_project_ids
    if all_project_ids:
        state["csod_primary_project_id"] = all_project_ids[0]
    state["csod_llm_resolved_areas"] = llm_resolved_areas
    state["csod_concepts_confirmed"] = True
    # MDL table details for all resolved projects — used by schema retrieval and area confirm
    if merged_project_tables:
        state["csod_resolved_project_tables"] = merged_project_tables
    state["csod_extracted_signals"] = selected_signals   # [{label, value}] for selected intents
    state["csod_conversation_checkpoint"] = None
    state["csod_checkpoint_resolved"] = True

    logger.info(
        "csod_intent_confirm resume: intents=%s concepts=%s projects=%s signals=%s",
        selected_intent_ids,
        confirmed_concept_ids,
        all_project_ids,
        [s["label"] for s in selected_signals],
    )
    return state

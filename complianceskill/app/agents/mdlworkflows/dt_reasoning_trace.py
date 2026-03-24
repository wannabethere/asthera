"""
Reasoning timeline for Detection & Triage (DT) workflow — same shape as CSOD
``csod_reasoning_trace`` for shared UI: preanalysis S1–S3 + ``agent_pipeline``.

HITL: ``apply_dt_hitl_patch`` or pass ``dt_reasoning_hitl_patch`` via
``DTWorkflowService.create_initial_state`` / workflow ``initial_state_data``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

TRACE_VERSION = 1

STEP_INTENT_CLASSIFIER = "dt_intent_classifier"
STEP_PLANNER = "dt_planner"
STEP_METRICS_RETRIEVAL = "dt_metrics_retrieval"
STEP_MDL_SCHEMA = "dt_mdl_schema_retrieval"


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def ensure_dt_reasoning_trace(state: Dict[str, Any]) -> Dict[str, Any]:
    existing = state.get("dt_reasoning_trace")
    if isinstance(existing, dict) and existing.get("version") == TRACE_VERSION:
        return existing
    trace = {
        "version": TRACE_VERSION,
        "workflow": "detection_triage",
        "updated_at": _now_iso(),
        "preanalysis": {"stages": {}},
        "agent_pipeline": [],
    }
    state["dt_reasoning_trace"] = trace
    return trace


def merge_preanalysis_stage(
    state: Dict[str, Any],
    stage_id: str,
    payload: Dict[str, Any],
    *,
    source: str = "agent",
) -> None:
    rt = ensure_dt_reasoning_trace(state)
    stages: Dict[str, Any] = rt["preanalysis"].setdefault("stages", {})
    cur = stages.get(stage_id) if isinstance(stages.get(stage_id), dict) else {}
    merged = {**cur, **payload}
    merged["updated_at"] = _now_iso()
    merged["last_writer"] = source
    merged["status"] = "human_edited" if source == "human" else payload.get("status", "complete")
    stages[stage_id] = merged
    rt["updated_at"] = _now_iso()


def upsert_pipeline_step(
    state: Dict[str, Any],
    *,
    step_id: str,
    order: int,
    title: str,
    summary: str,
    metadata: Optional[Dict[str, Any]] = None,
    source: str = "agent",
    status: str = "ok",
) -> None:
    rt = ensure_dt_reasoning_trace(state)
    steps: List[Dict[str, Any]] = rt["agent_pipeline"]
    meta = dict(metadata or {})
    ts = _now_iso()

    for i, s in enumerate(steps):
        if s.get("step_id") != step_id:
            continue
        prev = dict(s)
        rev = int(prev.get("revision", 1))
        last_writer = prev.get("last_writer", "agent")
        new_meta = {**(prev.get("metadata") or {}), **meta}
        entry: Dict[str, Any] = {
            **prev,
            "title": title,
            "order": order,
            "metadata": new_meta,
            "revision": rev + 1,
            "updated_at": ts,
            "status": status,
        }
        if source == "human":
            entry["summary"] = summary
            entry["last_writer"] = "human"
        elif last_writer == "human":
            entry["agent_summary"] = summary
            entry["agent_metadata"] = meta
            entry["last_writer"] = "human"
        else:
            entry["summary"] = summary
            entry["last_writer"] = "agent"
        steps[i] = entry
        rt["updated_at"] = ts
        steps.sort(key=lambda x: int(x.get("order", 0)))
        return

    steps.append(
        {
            "step_id": step_id,
            "order": order,
            "title": title,
            "summary": summary,
            "metadata": meta,
            "revision": 1,
            "updated_at": ts,
            "last_writer": source,
            "status": status,
        }
    )
    steps.sort(key=lambda x: int(x.get("order", 0)))
    rt["updated_at"] = ts


def apply_dt_hitl_patch(state: Dict[str, Any], patch: Dict[str, Any]) -> None:
    pre = patch.get("preanalysis")
    if isinstance(pre, dict):
        for sid, body in pre.items():
            if isinstance(body, dict) and sid in ("S1", "S2", "S3"):
                merge_preanalysis_stage(state, sid, body, source="human")

    raw_steps = patch.get("agent_pipeline")
    if not isinstance(raw_steps, list):
        return
    for step in raw_steps:
        if not isinstance(step, dict) or not step.get("step_id"):
            continue
        upsert_pipeline_step(
            state,
            step_id=str(step["step_id"]),
            order=int(step.get("order", 0)),
            title=str(step.get("title") or step["step_id"]),
            summary=str(step.get("summary") or ""),
            metadata=step.get("metadata") if isinstance(step.get("metadata"), dict) else None,
            source="human",
            status=str(step.get("status") or "ok"),
        )


def _s1_payload_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    de = state.get("data_enrichment") or {}
    if not isinstance(de, dict):
        de = {}
    blocks: List[Dict[str, str]] = []
    for key in ("needs_mdl", "needs_metrics", "metrics_intent", "playbook_template_hint"):
        if de.get(key) is not None:
            blocks.append({"key": key, "text": str(de.get(key))})
    return {
        "label": "S1 Intent Classification (DT)",
        "primary_intent": state.get("intent"),
        "framework_id": state.get("framework_id"),
        "requirement_code": state.get("requirement_code"),
        "reasoning_blocks": blocks,
        "data_enrichment": de,
    }


def _s2_payload_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    de = state.get("data_enrichment") or {}
    focus = de.get("suggested_focus_areas") or [] if isinstance(de, dict) else []
    if not isinstance(focus, list):
        focus = []
    cards: List[Dict[str, Any]] = []
    for fa in focus:
        cards.append(
            {
                "concept_id": str(fa),
                "display_name": str(fa).replace("_", " ").title(),
                "tags": ["focus_area"],
                "rationale": "Suggested focus area from DT intent / planner context.",
            }
        )
    resolved = state.get("resolved_focus_areas") or []
    if isinstance(resolved, list):
        for item in resolved:
            if isinstance(item, dict):
                cards.append(
                    {
                        "concept_id": item.get("id") or item.get("focus_area_id"),
                        "display_name": item.get("name") or item.get("label"),
                        "score": item.get("score"),
                        "tags": item.get("tags") or ["resolved_focus"],
                        "rationale": item.get("rationale") or "",
                    }
                )
    return {
        "label": "S2 Focus / Scope Mapping (DT)",
        "active_concepts": cards,
        "excluded_concepts": [],
        "data_sources_in_scope": state.get("dt_data_sources_in_scope")
        or state.get("selected_data_sources")
        or [],
    }


def _s3_payload_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    schemas = state.get("dt_resolved_schemas") or []
    groups: List[Dict[str, Any]] = []
    for s in schemas[:24]:
        if not isinstance(s, dict):
            continue
        name = (
            s.get("schema_name")
            or s.get("name")
            or s.get("table_name")
            or s.get("id")
            or "schema"
        )
        tables = s.get("tables") or s.get("table_names") or []
        if not tables and s.get("table_name"):
            tables = [s["table_name"]]
        if not isinstance(tables, list):
            tables = [str(tables)]
        groups.append(
            {
                "label": str(name),
                "reasoning": (s.get("description") or s.get("rationale") or "")[:500],
                "status": "ok",
                "tables": [str(t) for t in tables[:24]],
            }
        )
    return {
        "label": "S3 Schema Retrieval (DT)",
        "schema_groups": groups,
        "schema_count": len(schemas),
        "gold_tables_count": len(state.get("dt_gold_standard_tables") or []),
    }


def refresh_dt_reasoning_trace_after_intent(state: Dict[str, Any]) -> None:
    merge_preanalysis_stage(state, "S1", _s1_payload_from_state(state), source="agent")
    merge_preanalysis_stage(state, "S2", _s2_payload_from_state(state), source="agent")
    de = state.get("data_enrichment") or {}
    summary = (
        f"DT intent `{state.get('intent')}` | framework `{state.get('framework_id')}` | "
        f"needs_metrics={de.get('needs_metrics') if isinstance(de, dict) else None} | "
        f"needs_mdl={de.get('needs_mdl') if isinstance(de, dict) else None}"
    )
    upsert_pipeline_step(
        state,
        step_id=STEP_INTENT_CLASSIFIER,
        order=0,
        title="INTENT CLASSIFIER",
        summary=summary[:2000],
        metadata={
            "intent": state.get("intent"),
            "framework_id": state.get("framework_id"),
            "needs_metrics": isinstance(de, dict) and bool(de.get("needs_metrics")),
            "needs_mdl": isinstance(de, dict) and bool(de.get("needs_mdl")),
            "playbook_template": state.get("dt_playbook_template"),
        },
        source="agent",
    )


def refresh_dt_reasoning_trace_after_planner(state: Dict[str, Any]) -> None:
    merge_preanalysis_stage(state, "S2", _s2_payload_from_state(state), source="agent")
    summary = (state.get("dt_plan_summary") or "").strip() or "DT execution plan recorded."
    exec_plan = (state.get("planner_execution_plan") or {}).get("execution_plan") or []
    upsert_pipeline_step(
        state,
        step_id=STEP_PLANNER,
        order=1,
        title="PLANNER",
        summary=summary[:2000],
        metadata={
            "playbook_template": state.get("dt_playbook_template"),
            "complexity": state.get("dt_estimated_complexity"),
            "plan_step_count": len(exec_plan) if isinstance(exec_plan, list) else 0,
            "data_sources_in_scope": state.get("dt_data_sources_in_scope"),
        },
        source="agent",
    )


def refresh_dt_reasoning_trace_after_metrics(state: Dict[str, Any]) -> None:
    metrics = state.get("resolved_metrics") or []
    n = len(metrics)
    summary = (
        f"Resolved {n} metric candidate(s) from registry"
        + (
            f"; {len(state.get('dt_metric_groups') or [])} decision-tree groups"
            if state.get("dt_metric_groups")
            else ""
        )
        + "."
    )
    upsert_pipeline_step(
        state,
        step_id=STEP_METRICS_RETRIEVAL,
        order=3,
        title="METRICS RETRIEVAL",
        summary=summary,
        metadata={
            "metric_candidates": n,
            "dt_scored_metrics": len(state.get("dt_scored_metrics") or []),
            "dt_metric_groups": len(state.get("dt_metric_groups") or []),
            "gap_notes": len(state.get("dt_gap_notes") or []),
        },
        source="agent",
    )


def refresh_dt_reasoning_trace_after_mdl(state: Dict[str, Any]) -> None:
    merge_preanalysis_stage(state, "S3", _s3_payload_from_state(state), source="agent")
    schemas = state.get("dt_resolved_schemas") or []
    metrics = state.get("resolved_metrics") or []
    summary = (
        f"Retrieved {len(schemas)} schema bundle(s) and {len(metrics)} metric candidate(s) "
        f"for scoring and playbook engineering."
    )
    l2 = state.get("dt_mdl_l2_capability_tables") or {}
    l2_n = len(l2) if isinstance(l2, dict) else 0
    l3 = state.get("dt_mdl_l3_retrieval_queries") or {}
    l3_n = len(l3) if isinstance(l3, dict) else 0
    rel_n = len(state.get("dt_mdl_relation_edges") or [])
    upsert_pipeline_step(
        state,
        step_id=STEP_MDL_SCHEMA,
        order=2,
        title="MDL SCHEMA RETRIEVAL",
        summary=summary,
        metadata={
            "schemas": len(schemas),
            "metric_candidates": len(metrics),
            "gold_tables": len(state.get("dt_gold_standard_tables") or []),
            "mdl_l2_tables": l2_n,
            "mdl_l3_query_specs": l3_n,
            "mdl_relation_edges": rel_n,
            "mdl_needs_focus_clarification": bool(state.get("dt_mdl_needs_focus_clarification")),
        },
        source="agent",
    )

"""
Structured reasoning + pipeline steps for CSOD UI (Lexy pre-analysis + agent timeline).

- ``preanalysis.stages.S1|S2|S3`` mirror the S1/S2/S3 panels (intent, concepts, schemas).
- ``agent_pipeline`` is an ordered list of steps (intent → planner → MDL → …).

Human-in-the-loop: use ``apply_hitl_patch`` (or pass the same shape as
``initial_state_data["csod_reasoning_hitl_patch"]`` into CSOD workflow startup so
``CSODWorkflowService.create_initial_state`` merges before the graph runs) or call
``merge_preanalysis_stage`` / ``upsert_pipeline_step`` with ``source="human"``.
When ``last_writer`` is ``human``, agent upserts keep the human-facing ``summary``
and store new agent text in ``agent_summary`` / ``agent_metadata`` so UIs can
show both until reset.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

TRACE_VERSION = 1

STEP_INTENT_CLASSIFIER = "intent_classifier"
STEP_PLANNER = "planner"
STEP_MDL_METRICS = "mdl_metrics_retrieval"


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def ensure_csod_reasoning_trace(state: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize ``state['csod_reasoning_trace']`` if missing; return the trace dict."""
    existing = state.get("csod_reasoning_trace")
    if isinstance(existing, dict) and existing.get("version") == TRACE_VERSION:
        return existing
    trace = {
        "version": TRACE_VERSION,
        "updated_at": _now_iso(),
        "preanalysis": {"stages": {}},
        "agent_pipeline": [],
    }
    state["csod_reasoning_trace"] = trace
    return trace


def merge_preanalysis_stage(
    state: Dict[str, Any],
    stage_id: str,
    payload: Dict[str, Any],
    *,
    source: str = "agent",
) -> None:
    """Merge one pre-analysis stage (S1, S2, or S3). ``stage_id`` is 'S1'|'S2'|'S3'."""
    rt = ensure_csod_reasoning_trace(state)
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
    """Insert or update a pipeline step by stable ``step_id``."""
    rt = ensure_csod_reasoning_trace(state)
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


def apply_hitl_patch(state: Dict[str, Any], patch: Dict[str, Any]) -> None:
    """
    Merge UI / human edits into the trace.

    ``patch`` shape::
        {
          "preanalysis": {"S1": {...}, "S2": {...}, "S3": {...}},
          "agent_pipeline": [
            {"step_id": "planner", "summary": "...", "metadata": {...}, "title": "..."}
          ],
        }
    Omitted keys on a pipeline step are left unchanged.
    """
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
    s1 = state.get("csod_stage_1_intent") or {}
    env = state.get("csod_intent_classifier_output") or {}
    blocks: List[Dict[str, str]] = []
    detail = env.get("detail")
    if isinstance(detail, str) and detail.strip():
        blocks.append({"key": "detail", "text": detail.strip()})
    ar = env.get("analysis_requirements")
    if isinstance(ar, dict) and ar:
        blocks.append({"key": "analysis_requirements", "text": str(ar)})
    for sig in env.get("intent_signals") or []:
        if isinstance(sig, dict):
            k = str(sig.get("key") or sig.get("name") or "signal")
            v = sig.get("value") or sig.get("text") or sig
            blocks.append({"key": k, "text": str(v)})
        elif isinstance(sig, str):
            blocks.append({"key": "signal", "text": sig})

    return {
        "label": "S1 Intent Classification",
        "primary_intent": s1.get("intent") or state.get("csod_intent_registry_id"),
        "pipeline_intent": state.get("csod_intent"),
        "confidence": s1.get("confidence"),
        "mode": s1.get("routing"),
        "tags": s1.get("tags") or [],
        "reasoning_blocks": blocks,
        "signals": s1.get("signals") or [],
        "implicit_questions": s1.get("implicit_questions") or [],
        "quadrant": s1.get("quadrant"),
    }


def _s2_payload_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    lx2 = state.get("lexy_stage_2_concept_mapping")
    if isinstance(lx2, dict):
        active = lx2.get("concepts") or lx2.get("active_concepts") or lx2.get("cards")
        excluded = lx2.get("excluded_concepts") or lx2.get("excluded") or []
        return {
            "label": "S2 Concept Mapping",
            "active_concepts": active if isinstance(active, list) else [],
            "excluded_concepts": excluded if isinstance(excluded, list) else [],
            "raw_stage_2": lx2,
        }

    profile = state.get("compliance_profile") or {}
    selected = profile.get("selected_concepts") or []
    cards: List[Dict[str, Any]] = []
    for cid in selected:
        if isinstance(cid, dict):
            cards.append(
                {
                    "concept_id": cid.get("concept_id") or cid.get("id"),
                    "display_name": cid.get("display_name") or cid.get("label"),
                    "score": cid.get("score"),
                    "tags": cid.get("tags") or [],
                    "rationale": cid.get("rationale") or "Selected during conversation.",
                }
            )
        else:
            cards.append(
                {
                    "concept_id": str(cid),
                    "rationale": "Selected during conversation.",
                    "tags": [],
                }
            )

    domains = state.get("active_domains") or []
    scores = state.get("domain_scores") or {}
    if domains or scores:
        cards.append(
            {
                "concept_id": "domain_partition",
                "display_name": "Domain partition",
                "score": max(scores.values()) if scores else None,
                "tags": ["domain"],
                "rationale": f"active_domains={domains}, primary={state.get('primary_domain')}",
            }
        )

    return {
        "label": "S2 Concept Mapping",
        "active_concepts": cards,
        "excluded_concepts": [],
    }


def _s3_payload_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    schemas = state.get("csod_resolved_schemas") or []
    groups: List[Dict[str, Any]] = []
    for s in schemas[:20]:
        if not isinstance(s, dict):
            continue
        name = s.get("schema_name") or s.get("name") or s.get("id") or "schema"
        tables = s.get("tables") or s.get("table_names") or []
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
        "label": "S3 Schema Retrieval",
        "schema_groups": groups,
        "schema_count": len(schemas),
    }


def refresh_reasoning_trace_after_intent(state: Dict[str, Any]) -> None:
    """Call at end of intent classification (after domain classification)."""
    merge_preanalysis_stage(state, "S1", _s1_payload_from_state(state), source="agent")
    merge_preanalysis_stage(state, "S2", _s2_payload_from_state(state), source="agent")

    env = state.get("csod_intent_classifier_output") or {}
    narrative = env.get("narrative")
    if not isinstance(narrative, str) or not narrative.strip():
        s1 = state.get("csod_stage_1_intent") or {}
        narrative = (
            f"Intent `{s1.get('intent')}` → pipeline `{state.get('csod_intent')}` "
            f"(confidence {s1.get('confidence')}, routing {s1.get('routing')})."
        )
    upsert_pipeline_step(
        state,
        step_id=STEP_INTENT_CLASSIFIER,
        order=0,
        title="INTENT CLASSIFIER",
        summary=narrative.strip()[:2000],
        metadata={
            "intent": state.get("csod_intent_registry_id") or (state.get("csod_stage_1_intent") or {}).get("intent"),
            "pipeline_intent": state.get("csod_intent"),
            "requires_deadline_dim": bool(state.get("deadline_days")),
            "cce_enabled": bool(state.get("csod_causal_graph_enabled")),
            "active_domains": state.get("active_domains"),
        },
        source="agent",
    )


def refresh_reasoning_trace_after_planner(state: Dict[str, Any]) -> None:
    plan = state.get("csod_execution_plan") or []
    executor_ids = [str(p.get("executor_id", "")) for p in plan if isinstance(p, dict)]
    summary = (state.get("csod_plan_summary") or "").strip() or f"{len(plan)}-step execution plan."
    upsert_pipeline_step(
        state,
        step_id=STEP_PLANNER,
        order=1,
        title="PLANNER",
        summary=summary[:2000],
        metadata={
            "step_count": len(plan),
            "executors": executor_ids,
            "complexity": state.get("csod_estimated_complexity"),
            "follow_up_eligible": bool(state.get("csod_follow_up_eligible")),
            "data_sources_in_scope": state.get("csod_data_sources_in_scope"),
        },
        source="agent",
    )


def refresh_reasoning_trace_after_mdl(state: Dict[str, Any]) -> None:
    merge_preanalysis_stage(state, "S3", _s3_payload_from_state(state), source="agent")
    schemas = state.get("csod_resolved_schemas") or []
    metrics = state.get("resolved_metrics") or state.get("csod_retrieved_metrics") or []
    summary = (
        f"Retrieved {len(schemas)} schema bundle(s) and {len(metrics)} metric candidate(s) "
        f"for downstream scoring and DT resolution."
    )
    l2 = state.get("csod_mdl_l2_capability_tables") or {}
    l2_n = len(l2) if isinstance(l2, dict) else 0
    l3 = state.get("csod_mdl_l3_retrieval_queries") or {}
    l3_n = len(l3) if isinstance(l3, dict) else 0
    rel_n = len(state.get("csod_mdl_relation_edges") or [])
    upsert_pipeline_step(
        state,
        step_id=STEP_MDL_METRICS,
        order=2,
        title="MDL + METRICS RETRIEVAL",
        summary=summary,
        metadata={
            "schemas": len(schemas),
            "metric_candidates": len(metrics),
            "mdl_l2_tables": l2_n,
            "mdl_l3_query_specs": l3_n,
            "mdl_relation_edges": rel_n,
            "mdl_needs_focus_clarification": bool(state.get("csod_mdl_needs_focus_clarification")),
        },
        source="agent",
    )

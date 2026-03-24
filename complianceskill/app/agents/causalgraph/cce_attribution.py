"""
CCE attribution layer — single response shape for LLM path vs Shapley-on-data.

Upgrade points (do not change signatures of choose_attribution_method / run_attribution):
  Phase 2 — replace body of llm_attribution_and_ordering() only.
  Phase 3 — replace body of shapley_on_observations() only.

Pre-wire state (before Phase 2/3):
  metric_current_values: { metric_id: { "current": ..., "target": ... } }
  metric_observations:     [ { "date", "metric_id", "value", ... }, ... ]
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Keys every implementation must populate (UI / assembler / tools key on these only).
ATTRIBUTION_RESULT_KEYS = frozenset({
    "method",
    "method_detail",
    "contributions",
    "intervention_order",
    "blocked_metrics",
    "diagnosis",
    "confidence",
    "is_placeholder",
})


def build_stub_metric_current_values(metrics: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Best-effort map from spine metrics until capability resolver feeds real values."""
    out: Dict[str, Dict[str, Any]] = {}
    for m in metrics or []:
        mid = m.get("metric_id") or m.get("id")
        if not mid:
            continue
        out[str(mid)] = {
            "current": m.get("current_value"),
            "target": m.get("target_value") if m.get("target_value") is not None else m.get("target"),
        }
    return out


def _attribution_result(
    *,
    method: str,
    method_detail: str,
    diagnosis: str,
    confidence: float = 0.0,
    is_placeholder: bool = True,
) -> Dict[str, Any]:
    return {
        "method": method,
        "method_detail": method_detail,
        "contributions": [],
        "intervention_order": [],
        "blocked_metrics": [],
        "diagnosis": diagnosis,
        "confidence": confidence,
        "is_placeholder": is_placeholder,
    }


def advisory_skip_attribution_result() -> Dict[str, Any]:
    """Same schema as live paths; UI treats is_placeholder=False as 'no pending ϕ bars'."""
    return _attribution_result(
        method="advisory_skip",
        method_detail="advisory_mode",
        diagnosis="Advisory mode — quantitative attribution was not run.",
        confidence=0.0,
        is_placeholder=False,
    )


def placeholder_attribution_result(method_detail: str, *, diagnosis: Optional[str] = None) -> Dict[str, Any]:
    return _attribution_result(
        method="placeholder",
        method_detail=method_detail,
        diagnosis=diagnosis or "Attribution analysis coming soon.",
        confidence=0.0,
        is_placeholder=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Decision function — stable across Phase 2 / Phase 3 (do not edit when upgrading stubs)
# ─────────────────────────────────────────────────────────────────────────────


def choose_attribution_method(state: Dict[str, Any]) -> str:
    """
    Returns 'shapley_on_data' or 'llm_attribution'.
    Uses: audit context, time-series availability, metric count.
    """
    has_time_series = bool(state.get("metric_time_series_available", False))
    proposed = state.get("causal_proposed_nodes", [])
    n_metrics = len(proposed) if isinstance(proposed, list) else 0
    audit_required = bool(state.get("requires_audit_evidence", False))

    if audit_required and has_time_series:
        return "shapley_on_data"

    if has_time_series and n_metrics <= 7:
        return "shapley_on_data"

    return "llm_attribution"


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 UPGRADE: replace function body only — keep signature
# ─────────────────────────────────────────────────────────────────────────────


def llm_attribution_and_ordering(
    causal_graph: Dict[str, Any],
    metric_values: Dict[str, Any],
    deadline_days: int,
    llm: Any,
) -> Dict[str, Any]:
    # UPGRADE_PHASE_2: prompt → path contributions → lag filter → rank → parse JSON
    _ = (causal_graph, metric_values, deadline_days, llm)
    logger.info("llm_attribution_and_ordering: placeholder (Phase 2)")
    return placeholder_attribution_result(
        "LLM attribution not yet implemented (Phase 2).",
        diagnosis="Attribution analysis coming soon.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 3 UPGRADE: replace function body only — keep signature
# ─────────────────────────────────────────────────────────────────────────────


def shapley_on_observations(
    causal_graph: Dict[str, Any],
    observations: List[Dict[str, Any]],
    terminal_metric: str,
    deadline_days: int,
) -> Dict[str, Any]:
    # UPGRADE_PHASE_3: pivot → coalitions → marginal ϕ → lag filter → rank
    _ = (causal_graph, deadline_days)
    logger.info(
        "shapley_on_observations: placeholder (Phase 3); rows=%s terminal=%s",
        len(observations or []),
        terminal_metric,
    )
    return placeholder_attribution_result(
        "Shapley-on-data not yet implemented (Phase 3).",
        diagnosis="Attribution analysis coming soon.",
    )


def _terminal_metric_id(state: Dict[str, Any]) -> str:
    meta = state.get("causal_graph_metadata") or {}
    tids = meta.get("terminal_node_ids") or []
    if tids:
        return str(tids[0])
    for n in state.get("causal_proposed_nodes") or []:
        if n.get("node_type") == "terminal" or n.get("is_outcome"):
            return str(n.get("metric_ref") or n.get("node_id") or "")
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Dispatch — stable entry point
# ─────────────────────────────────────────────────────────────────────────────


def run_attribution(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sets attribution_result, attribution_method_used, csod_cce_attribution (alias).
    Advisory mode: returns immediately — does not call choose_attribution_method or stubs.
    """
    if state.get("advisory_mode"):
        result = advisory_skip_attribution_result()
        state["attribution_method_used"] = "advisory_skip"
        state["attribution_result"] = result
        state["csod_cce_attribution"] = result
        logger.debug("run_attribution: advisory_mode skip")
        return state

    method = choose_attribution_method(state)
    state["attribution_method_used"] = method

    causal_graph = state.get("causal_graph") or {}
    deadline_days = int(state.get("deadline_days", 999) or 999)

    if method == "shapley_on_data":
        observations = state.get("metric_observations") or []
        terminal_metric = _terminal_metric_id(state)
        result = shapley_on_observations(
            causal_graph=causal_graph,
            observations=list(observations),
            terminal_metric=terminal_metric,
            deadline_days=deadline_days,
        )
    else:
        metric_values = state.get("metric_current_values") or {}
        llm = state.get("_llm_instance") or state.get("_llm_instance_for_cce_attribution")
        result = llm_attribution_and_ordering(
            causal_graph=causal_graph,
            metric_values=dict(metric_values),
            deadline_days=deadline_days,
            llm=llm,
        )

    state["attribution_result"] = result
    state["csod_cce_attribution"] = result
    logger.info(
        "run_attribution: method=%s placeholder=%s contributions=%s",
        method,
        result.get("is_placeholder"),
        len(result.get("contributions") or []),
    )
    return state


def merge_attribution_into_causal_graph_result(state: Dict[str, Any]) -> None:
    """Attach attribution blob to csod_causal_graph_result for assembler / API."""
    base = state.get("csod_causal_graph_result")
    if not isinstance(base, dict):
        base = {}
    ar = state.get("attribution_result")
    if isinstance(ar, dict):
        base = {**base, "cce_attribution": ar}
    state["csod_causal_graph_result"] = base


def prepare_cce_attribution_context(
    state: Dict[str, Any],
    *,
    proposed_nodes: List[Dict[str, Any]],
    proposed_edges: List[Dict[str, Any]],
    graph_metadata: Dict[str, Any],
    spine_metrics: List[Dict[str, Any]],
) -> None:
    """Populate attribution inputs on state (idempotent where noted)."""
    state.setdefault("metric_observations", state.get("metric_observations") or [])
    if not state.get("metric_current_values"):
        state["metric_current_values"] = build_stub_metric_current_values(spine_metrics)
    state["metric_time_series_available"] = bool(state.get("metric_observations"))
    state["causal_proposed_nodes"] = proposed_nodes
    state["causal_graph_metadata"] = graph_metadata if isinstance(graph_metadata, dict) else {}
    state["causal_graph"] = {
        "nodes": proposed_nodes,
        "edges": proposed_edges or [],
    }
    profile = state.get("compliance_profile") or {}
    if "requires_audit_evidence" not in state:
        fw = str(profile.get("framework") or profile.get("audit_framework") or "").lower()
        state["requires_audit_evidence"] = (
            "soc" in fw or profile.get("requires_audit_evidence") is True
        )
    if state.get("deadline_days") is None:
        state["deadline_days"] = (
            profile.get("deadline_days")
            or profile.get("certification_deadline_days")
            or 999
        )

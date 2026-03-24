"""
Spine pre-step: decision-tree axis seeds + capability resolution before MDL retrieval.

Order: DT seeds + capability resolver (this module) → MDL schema retrieval (+ L2/L3 enrichment)
→ metrics registry retrieval.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Set

logger = logging.getLogger(__name__)

# ── Domain-aware capability + focus hints (loaded from DomainConfig) ───────────
# Falls back to inline dicts if DomainConfig is unavailable.

def _get_cap_source_hints() -> Dict[str, Sequence[str]]:
    """Capability ID substring → source tokens, merged from all loaded domains."""
    try:
        from app.agents.domain_config import DomainRegistry
        return DomainRegistry.instance().all_capability_source_hints()
    except Exception:
        pass
    # Inline fallback
    return {
        "lms.": ("csod", "cornerstone", "workday", "lms", "saba"),
        "completion": ("csod", "cornerstone", "workday", "lms"),
        "deadline": ("csod", "cornerstone", "workday", "lms"),
        "assessment": ("csod", "cornerstone", "workday", "lms"),
        "cert": ("csod", "cornerstone", "workday", "lms"),
        "training": ("csod", "cornerstone", "workday", "lms"),
        "siem": ("splunk", "sentinel", "elastic", "qradar", "sumo", "chronicle"),
        "log": ("splunk", "sentinel", "elastic", "qradar", "sumo"),
        "edr": ("crowdstrike", "sentinel", "defender", "carbonblack", "cortex"),
        "endpoint": ("crowdstrike", "sentinel", "defender", "carbonblack"),
        "vuln": ("tenable", "qualys", "rapid7", "wiz", "snyk"),
        "cloud": ("aws", "azure", "gcp", "wiz", "prisma"),
    }


def _get_dt_focus_hints() -> Dict[str, List[str]]:
    """DT focus area → keyword hints, merged from all loaded domains."""
    try:
        from app.agents.domain_config import DomainRegistry
        return DomainRegistry.instance().all_dt_focus_hints()
    except Exception:
        pass
    # Inline fallback
    return {
        "vulnerability_management": ["vulnerability", "cve", "exposure", "patch"],
        "incident_detection": ["incident", "detection", "alert", "mttr"],
        "log_management_siem": ["siem", "log", "audit", "event"],
        "audit_logging_compliance": ["audit", "logging", "compliance"],
        "endpoint_detection": ["endpoint", "edr", "malware"],
        "network_detection": ["network", "traffic", "anomaly"],
        "cloud_security_posture": ["cloud", "cspm", "misconfig"],
        "patch_management": ["patch", "remediation"],
        "identity_access_management": ["identity", "access", "iam"],
        "authentication_mfa": ["mfa", "authentication"],
        "data_classification": ["classification", "dlp", "data"],
    }


# Backward compat aliases — code that referenced these directly still works
_CAP_SOURCE_HINTS = _get_cap_source_hints()
_DT_FOCUS_HINTS = _get_dt_focus_hints()


def normalize_connected_sources(raw: Optional[Sequence[Any]]) -> List[str]:
    if not raw:
        return []
    out: List[str] = []
    for item in raw:
        if item is None:
            continue
        s = str(item).strip().lower()
        if not s:
            continue
        base = s.split(".")[0].split("/")[-1]
        if base and base not in out:
            out.append(base)
    return out


def _cap_fulfilled(cap_id: str, sources: List[str]) -> bool:
    cap_l = cap_id.lower()
    for needle, provs in _CAP_SOURCE_HINTS.items():
        if needle in cap_l:
            return any(
                (p in sources) or any(s.startswith(p) for s in sources)
                for p in provs
            )
    return True


def _hints_from_capabilities(required: List[str]) -> List[str]:
    tokens: Set[str] = set()
    for cap in required:
        for part in cap.replace("_", ".").split("."):
            p = part.strip().lower()
            if len(p) > 2:
                tokens.add(p)
        tokens.add(cap.lower().replace("_", " "))
    return sorted(tokens)


def compute_capability_resolution(
    *,
    use_case: Optional[str],
    connected_sources: List[str],
    uc_group: Dict[str, Any],
    extra_hint_tokens: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    required = list(uc_group.get("required_capabilities") or [])
    if not isinstance(required, list):
        required = []
    fulfilled = [c for c in required if _cap_fulfilled(c, connected_sources)]
    missing = [c for c in required if c not in fulfilled]
    hints = _hints_from_capabilities(required)
    if extra_hint_tokens:
        hints.extend(str(t).lower() for t in extra_hint_tokens if t)
    retrieval_query = " ".join(sorted(set(hints)))
    ratio = (len(fulfilled) / len(required)) if required else 1.0
    return {
        "use_case": use_case,
        "required_capability_ids": required,
        "fulfilled_capability_ids": fulfilled,
        "missing_capability_ids": missing,
        "connected_sources_normalized": connected_sources,
        "capability_coverage_ratio": round(ratio, 4),
        "capability_retrieval_hints": retrieval_query,
    }


def seed_csod_decision_tree_axis_state(state: Dict[str, Any]) -> Optional[str]:
    """
    Populate csod_dt_seed_decisions / dt_group_by_hint / csod_dt_config when DT applies.
    Returns resolved use_case key (or None) for capability lookup.
    """
    from app.agents.csod.intent_config import (
        get_dt_config_for_intent,
        get_lms_use_case_group,
        should_skip_dt_for_intent,
    )

    intent = state.get("csod_intent", "")
    if should_skip_dt_for_intent(intent):
        state.setdefault("csod_dt_seed_decisions", {})
        return None

    dt_config = get_dt_config_for_intent(intent)
    state["csod_dt_config"] = dt_config
    uc = dt_config.get("use_case")
    uc_group = get_lms_use_case_group(uc) if uc else {}
    primary_fa = (uc_group.get("primary_focus_areas") or [])[:1]
    enrich_fa = state.get("data_enrichment", {}).get("suggested_focus_areas", [])[:1]
    focus_pick = primary_fa[0] if primary_fa else (enrich_fa[0] if enrich_fa else None)
    override = dt_config.get("focus_area_override")
    if override:
        focus_pick = override

    state["csod_dt_seed_decisions"] = {
        k: v
        for k, v in {
            "use_case": uc,
            "goal": dt_config.get("goal"),
            "focus_area": focus_pick,
            "metric_type": dt_config.get("metric_type"),
            "audience": dt_config.get("audience"),
            "timeframe": dt_config.get("timeframe"),
        }.items()
        if v
    }
    state["dt_group_by_hint"] = dt_config.get("dt_group_by")
    return uc if isinstance(uc, str) else None


def precheck_csod_dt_and_capabilities(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run after goal planner, before MDL schema retrieval: DT axis seeds + capability resolution.
    """
    from app.agents.csod.intent_config import get_lms_use_case_group

    use_case = seed_csod_decision_tree_axis_state(state)
    raw_sources = state.get("csod_data_sources_in_scope") or state.get("selected_data_sources") or []
    connected = normalize_connected_sources(raw_sources)
    uc_group: Dict[str, Any] = get_lms_use_case_group(use_case) if use_case else {}

    extra: List[str] = []
    de = state.get("data_enrichment") or {}
    for fa in de.get("suggested_focus_areas") or []:
        extra.extend(_DT_FOCUS_HINTS.get(str(fa), [str(fa)]))

    cap = compute_capability_resolution(
        use_case=use_case,
        connected_sources=connected,
        uc_group=uc_group,
        extra_hint_tokens=extra,
    )
    state["capability_resolution"] = cap
    state["capability_retrieval_hints"] = cap.get("capability_retrieval_hints") or ""
    logger.info(
        "precheck_csod: use_case=%s required_caps=%s fulfilled=%s",
        use_case,
        cap.get("required_capability_ids"),
        cap.get("fulfilled_capability_ids"),
    )
    return state


def precheck_dt_capabilities(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detection & triage path: capability resolution before MDL retrieval and metrics registry.
    Uses optional data_enrichment.lms_use_case when present; otherwise focus-area hints only.
    """
    from app.agents.csod.intent_config import get_lms_use_case_group

    de = state.get("data_enrichment") or {}
    use_case = de.get("lms_use_case")
    if not use_case:
        use_case = None

    raw_sources = state.get("dt_data_sources_in_scope") or state.get("selected_data_sources") or []
    connected = normalize_connected_sources(raw_sources)
    uc_group: Dict[str, Any] = get_lms_use_case_group(use_case) if use_case else {}

    extra: List[str] = []
    for fa in de.get("suggested_focus_areas") or []:
        extra.extend(_DT_FOCUS_HINTS.get(str(fa), [str(fa)]))

    cap = compute_capability_resolution(
        use_case=use_case,
        connected_sources=connected,
        uc_group=uc_group,
        extra_hint_tokens=extra,
    )
    state["capability_resolution"] = cap
    state["capability_retrieval_hints"] = cap.get("capability_retrieval_hints") or ""
    # Light DT seeds so early enrich_metrics_with_decision_tree respects Lexy/use_case when set
    if use_case:
        state.setdefault("csod_dt_seed_decisions", {})
        state["csod_dt_seed_decisions"] = {**state["csod_dt_seed_decisions"], "use_case": use_case}
    logger.info(
        "precheck_dt: use_case=%s hints_len=%s",
        use_case,
        len(cap.get("capability_retrieval_hints") or ""),
    )
    return state


def capability_boost_for_metric(
    metric_text: str,
    source_caps: List[str],
    required_caps: List[str],
) -> float:
    """Extra score bump when metric content aligns with required capabilities."""
    if not required_caps:
        return 0.0
    blob = " ".join(
        [metric_text.lower()]
        + [str(c).lower() for c in source_caps]
    )
    hit = 0
    for cap in required_caps:
        for part in cap.lower().replace("_", ".").split("."):
            if len(part) > 2 and part in blob:
                hit += 1
                break
    return min(0.15, 0.03 * hit)

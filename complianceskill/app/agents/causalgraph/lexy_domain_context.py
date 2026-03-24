"""
Lexy / causal pipeline — domain partition helpers (lexy_causal_concept_mapping_design §4).

Resolves active_domains for vector retrieval and keeps causal_vertical / vertical as
compat aliases for primary_domain.

Domain keywords and intent prefixes are loaded from DomainConfig (config/domains/*.json)
when available, with inline fallbacks for backward compatibility.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


# ── Domain keyword + prefix loading (DomainConfig-aware) ──────────────────────

def _load_domain_signals() -> Tuple[
    Dict[str, List[str]],  # domain_id → keywords
    Dict[str, List[str]],  # domain_id → intent_prefixes
]:
    """Load keyword/prefix signals from DomainConfig; fall back to inline dicts."""
    try:
        from app.agents.domain_config import DomainRegistry
        reg = DomainRegistry.instance()
        return reg.all_domain_keywords(), reg.all_intent_prefixes()
    except Exception:
        pass
    # Inline fallback
    keywords = {
        "lms": [
            "completion", "training", "compliance", "certification", "cornerstone",
            "csod", "learner", "enrollment", "lms", "course", "mandatory",
            "overdue", "assignment",
        ],
        "security": [
            "cve", "vulnerability", "patch", "incident", "mitre", "att&ck",
            "control", "siem", "exposure", "threat",
        ],
    }
    prefixes = {
        "lms": [
            "compliance_gap", "training_plan", "learner_", "funnel_",
            "skill_gap", "benchmark_", "metrics_dashboard", "metric_kpi",
        ],
        "security": [
            "gap_analysis", "vulnerability", "incident_", "risk_",
        ],
    }
    return keywords, prefixes


# Keyword weight per hit (can differ per domain for tuning)
_KEYWORD_WEIGHT: Dict[str, float] = {"lms": 0.08, "security": 0.09}
_PREFIX_WEIGHT = 0.25


def classify_domains_for_query(
    user_query: str,
    intent: str = "",
    feature_vector: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Multi-label domain scores (design §4.1).

    Dynamically scores against all domains loaded from DomainConfig.
    Returns active_domains, primary_domain, domain_scores.
    """
    all_keywords, all_prefixes = _load_domain_signals()
    text = f"{user_query or ''} {intent or ''}".lower()
    intent_l = (intent or "").lower()

    scores: Dict[str, float] = {did: 0.0 for did in all_keywords}

    # Keyword scoring
    for did, kws in all_keywords.items():
        weight = _KEYWORD_WEIGHT.get(did, 0.08)
        for kw in kws:
            if kw in text:
                scores[did] += weight

    # Intent prefix scoring
    for did, prefixes in all_prefixes.items():
        for p in prefixes:
            if intent_l.startswith(p):
                scores[did] += _PREFIX_WEIGHT

    # Feature vector hints
    if feature_vector:
        hints = feature_vector.get("domain_hints") or []
        for d in hints:
            if d in scores:
                scores[d] = min(scores[d] + 0.25, 1.0)

    scores = {k: round(min(v, 1.0), 3) for k, v in scores.items()}
    threshold = 0.35
    active = [d for d, s in scores.items() if s >= threshold]
    if not active:
        active = [max(scores, key=scores.get)] if scores else ["lms"]
    primary = max(scores, key=scores.get) if scores else "lms"

    return {
        "domain_scores": scores,
        "active_domains": active,
        "primary_domain": primary,
    }


def apply_domain_classification_to_state(state: Dict[str, Any]) -> None:
    """
    Mutates state: domain_classification, active_domains, primary_domain,
    vertical, causal_vertical (compat).
    """
    if state.get("domain_classification") and state.get("active_domains"):
        primary = state.get("primary_domain") or (state["active_domains"][0] if state["active_domains"] else "lms")
        state.setdefault("primary_domain", primary)
        state["vertical"] = primary
        state["causal_vertical"] = primary
        return

    q = state.get("user_query", "") or ""
    intent = state.get("csod_intent") or state.get("intent") or ""
    stage1 = state.get("csod_stage_1_intent") or {}
    tags = [str(t).lower() for t in (stage1.get("tags") or [])]
    if any(t in ("soc2", "compliance", "lms", "training", "cornerstone", "csod") for t in tags):
        intent = f"{intent} {' '.join(tags)}"
    fv = state.get("feature_vector") if isinstance(state.get("feature_vector"), dict) else None
    dc = classify_domains_for_query(q, intent, fv)
    state["domain_classification"] = dc
    state["active_domains"] = dc["active_domains"]
    state["primary_domain"] = dc["primary_domain"]
    state["domain_scores"] = dc["domain_scores"]
    state["vertical"] = dc["primary_domain"]
    state["causal_vertical"] = dc["primary_domain"]


def retrieval_domain_ids(state: Dict[str, Any]) -> List[str]:
    """Domains for causal vector filter: active + _shared."""
    raw = state.get("active_domains")
    if not raw:
        v = state.get("causal_vertical") or state.get("vertical") or "lms"
        raw = [v]
    out: List[str] = []
    for d in raw:
        if d and d not in out:
            out.append(str(d))
    if "_shared" not in out:
        out.append("_shared")
    return out

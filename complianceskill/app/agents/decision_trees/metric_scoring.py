"""
Metric Decision Tree — Scoring Engine

Weighted multi-dimension scoring that ranks metrics from the registry
against resolved decision tree values.

Mirrors the scoring pattern in registry_unified.py's score_all_templates()
but operates on metric attributes instead of template attributes.
"""
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
# Scoring weight configuration
# ============================================================================

SCORING_WEIGHTS = {
    "use_case":        30,   # metric.use_cases ∩ decisions.use_case
    "goal":            25,   # metric.goals ∩ decisions.goal tags
    "focus_area":      20,   # metric.focus_areas ∩ decisions.focus_area
    "control_domain":  15,   # metric.mapped_control_domains ∩ scored controls
    "risk_category":   15,   # metric.mapped_risk_categories ∩ scored risks
    "metric_type":     10,   # metric.metric_type == decisions.metric_type
    "data_source":     10,   # metric.source_capabilities ∩ data_sources_in_scope
    "timeframe":       10,   # decisions.timeframe ∈ metric.aggregation_windows
    "audience":         5,   # decisions.audience ∈ metric.audience_levels
    "vector_boost":    10,   # existing Qdrant similarity score
}

MAX_SCORE = sum(SCORING_WEIGHTS.values())  # 150


# ============================================================================
# Scoring dimensions
# ============================================================================

def _score_use_case(metric: Dict, decisions: Dict, tags: Dict) -> float:
    """D1: Does metric explicitly support this use case?"""
    metric_use_cases = _ensure_list(metric.get("use_cases", []))
    decision_use_case = decisions.get("use_case", "")
    if not metric_use_cases:
        return 0.4  # neutral if not tagged
    if decision_use_case in metric_use_cases:
        return 1.0
    # Partial: check if metric's goals overlap with use_case's goal_filter
    goal_filter = tags.get("goal_filter", [])
    metric_goals = _ensure_list(metric.get("goals", []))
    if goal_filter and metric_goals:
        overlap = len(set(goal_filter) & set(metric_goals))
        if overlap > 0:
            return 0.6 + (0.3 * min(overlap / len(goal_filter), 1.0))
    return 0.2


def _score_goal(metric: Dict, decisions: Dict, tags: Dict) -> float:
    """D2: Does metric align with the measurement goal?"""
    metric_goals = _ensure_list(metric.get("goals", []))
    decision_goal = decisions.get("goal", "")
    goal_categories = tags.get("metric_categories", [])

    if not metric_goals and not metric.get("category"):
        return 0.3

    score = 0.0
    if decision_goal in metric_goals:
        score = 1.0
    elif metric.get("category") in goal_categories:
        score = 0.8
    elif metric_goals:
        # Partial match via category overlap
        metric_category = metric.get("category", "")
        if metric_category and any(metric_category in g or g in metric_category for g in goal_categories):
            score = 0.5
        else:
            score = 0.15
    else:
        score = 0.2

    return score


def _score_focus_area(metric: Dict, decisions: Dict, tags: Dict) -> float:
    """D3: Does metric cover the target compliance domain?"""
    metric_focus = _ensure_list(metric.get("focus_areas", []))
    decision_focus = decisions.get("focus_area", "")

    if not metric_focus:
        # Infer from category
        category = metric.get("category", "")
        CATEGORY_FOCUS_MAP = {
            "vulnerabilities": "vulnerability_management",
            "patch_compliance": "vulnerability_management",
            "cve_exposure": "vulnerability_management",
            "access_control": "access_control",
            "authentication": "access_control",
            "mfa_adoption": "access_control",
            "audit_logging": "audit_logging",
            "siem_events": "audit_logging",
            "compliance_events": "audit_logging",
            "incidents": "incident_response",
            "mttr": "incident_response",
            "alert_volume": "incident_response",
            "cloud_findings": "vulnerability_management",
            "misconfigs": "vulnerability_management",
            "endpoint_events": "incident_response",
            "edr_alerts": "incident_response",
            "training_compliance": "training_compliance",
            "certification": "training_compliance",
        }
        inferred = CATEGORY_FOCUS_MAP.get(category, "")
        if inferred == decision_focus:
            return 0.8
        return 0.3

    if decision_focus in metric_focus:
        return 1.0

    # Check control domain overlap from tags
    control_domains = tags.get("control_domains", [])
    metric_domains = _ensure_list(metric.get("mapped_control_domains", []))
    if control_domains and metric_domains:
        if set(control_domains) & set(metric_domains):
            return 0.7

    return 0.15


def _score_control_domain(
    metric: Dict,
    scored_controls: List[Dict],
) -> float:
    """D4: Does metric map to controls found in scored_context?"""
    # Check for LLM-generated control evidence hints first (fast path)
    control_hints = metric.get("control_evidence_hints", {})
    best_controls = control_hints.get("best_controls", [])
    if best_controls:
        # Check if any of the best_controls are in scored_controls
        scored_codes = {
            (c.get("code") or c.get("control_code") or "").upper()
            for c in scored_controls
        }
        if any(c.upper() in scored_codes for c in best_controls):
            return 0.95  # Near-certain match from LLM pre-validation
    
    metric_domains = _ensure_list(metric.get("mapped_control_domains", []))
    if not metric_domains and not metric.get("mapped_control_codes"):
        return 0.3  # untagged neutral

    # Build set of active control codes and domains
    active_codes: Set[str] = set()
    for ctrl in scored_controls:
        code = (ctrl.get("code") or ctrl.get("control_code") or "").upper()
        if code:
            active_codes.add(code)
            # Extract domain prefix (e.g., "CC6" from "CC6.1")
            prefix = re.match(r'^([A-Z]+\d+)', code)
            if prefix:
                active_codes.add(prefix.group(1))
        
        # Check LLM taxonomy if available (more precise matching)
        llm_taxonomy = ctrl.get("llm_taxonomy", {})
        if llm_taxonomy:
            # Check if metric's focus_areas match control's focus_areas from taxonomy
            taxonomy_focus = llm_taxonomy.get("focus_areas", [])
            metric_focus = _ensure_list(metric.get("focus_areas", []))
            if taxonomy_focus and metric_focus:
                if set(taxonomy_focus) & set(metric_focus):
                    return 0.9  # Strong match via LLM taxonomy
            
            # Check keyword overlap
            taxonomy_keywords = llm_taxonomy.get("affinity_keywords", [])
            if taxonomy_keywords:
                metric_text = " ".join([
                    metric.get("name", ""),
                    metric.get("description", ""),
                    metric.get("natural_language_question", ""),
                ]).lower()
                matches = sum(1 for kw in taxonomy_keywords if kw.lower() in metric_text)
                if matches > 0:
                    return 0.7 + 0.2 * (matches / max(len(taxonomy_keywords), 1))

    if not active_codes:
        return 0.4

    mapped_codes = _ensure_list(metric.get("mapped_control_codes", []))
    all_metric_refs = set(d.upper() for d in metric_domains) | set(c.upper() for c in mapped_codes)

    overlap = all_metric_refs & active_codes
    if overlap:
        return min(1.0, 0.5 + 0.5 * (len(overlap) / max(len(all_metric_refs), 1)))

    return 0.1


def _score_risk_category(
    metric: Dict,
    scored_risks: List[Dict],
) -> float:
    """D5: Does metric map to risks found in scored_context?"""
    metric_risk_cats = _ensure_list(metric.get("mapped_risk_categories", []))
    if not metric_risk_cats:
        return 0.3

    active_risk_cats: Set[str] = set()
    for risk in scored_risks:
        cat = risk.get("category", "") or risk.get("risk_category", "")
        if cat:
            active_risk_cats.add(cat.lower())
        # Also extract from risk name keywords
        name = (risk.get("name") or risk.get("risk_name") or "").lower()
        for token in name.replace("_", " ").split():
            if len(token) > 4:
                active_risk_cats.add(token)

    if not active_risk_cats:
        return 0.4

    overlap = set(c.lower() for c in metric_risk_cats) & active_risk_cats
    if overlap:
        return min(1.0, 0.5 + 0.5 * (len(overlap) / max(len(metric_risk_cats), 1)))

    return 0.1


def _score_metric_type(metric: Dict, decisions: Dict, tags: Dict) -> float:
    """D6: Does metric type match the requested insight type?"""
    metric_type = metric.get("metric_type", "")
    filter_type = tags.get("metric_type_filter", "") or decisions.get("metric_type", "")

    if not metric_type or not filter_type:
        return 0.5  # neutral

    if metric_type == filter_type:
        return 1.0

    # Fuzzy: "count" matches "counts", "percentage" matches "percentages"
    if metric_type.rstrip("s") == filter_type.rstrip("s"):
        return 0.9

    # Type affinity groups
    AFFINITIES = {
        "count": {"rate", "trend"},
        "rate": {"count", "percentage", "trend"},
        "percentage": {"score", "rate"},
        "score": {"percentage"},
        "trend": {"count", "rate"},
        "distribution": {"count"},
        "comparison": {"percentage", "score"},
    }
    if filter_type in AFFINITIES.get(metric_type, set()):
        return 0.5

    return 0.2


def _score_data_source(
    metric: Dict,
    data_sources_in_scope: List[str],
) -> float:
    """D7: Are the metric's required data sources available?"""
    source_caps = _ensure_list(metric.get("source_capabilities", []))
    if not source_caps:
        return 0.5  # untagged neutral

    if not data_sources_in_scope:
        return 0.5  # no constraint

    # Build prefix set from data_sources_in_scope
    prefixes = [ds.split(".")[0].lower() for ds in data_sources_in_scope]

    matched = 0
    for cap in source_caps:
        cap_prefix = cap.split(".")[0].lower() if isinstance(cap, str) else ""
        if cap_prefix and any(cap_prefix.startswith(p) or p.startswith(cap_prefix) for p in prefixes):
            matched += 1

    if matched > 0:
        return min(1.0, 0.5 + 0.5 * (matched / len(source_caps)))

    return 0.1  # no data source match — still usable but penalized


def _score_timeframe(metric: Dict, decisions: Dict, tags: Dict) -> float:
    """D8: Does metric support the requested aggregation window?"""
    windows = _ensure_list(metric.get("aggregation_windows", []))
    requested = tags.get("aggregation_window") or decisions.get("timeframe", "")

    if not windows or not requested:
        return 0.5

    if requested in windows:
        return 1.0

    # Adjacency bonus
    ORDER = ["realtime", "hourly", "daily", "weekly", "monthly", "quarterly"]
    if requested in ORDER:
        req_idx = ORDER.index(requested)
        for w in windows:
            if w in ORDER:
                dist = abs(ORDER.index(w) - req_idx)
                if dist == 1:
                    return 0.7
                if dist == 2:
                    return 0.4

    return 0.2


def _score_audience(metric: Dict, decisions: Dict, tags: Dict) -> float:
    """D9: Is metric appropriate for the target audience?"""
    metric_audiences = _ensure_list(metric.get("audience_levels", []))
    decision_audience = decisions.get("audience", "")

    if not metric_audiences:
        return 0.5

    if decision_audience in metric_audiences:
        return 1.0

    # Audience compatibility — compliance_team and auditor overlap
    COMPAT = {
        "compliance_team": {"auditor", "risk_management"},
        "auditor": {"compliance_team", "executive_board"},
        "executive_board": {"risk_management", "auditor"},
        "security_ops": {"compliance_team"},
        "risk_management": {"executive_board", "compliance_team"},
        "learning_admin": {"compliance_team"},
    }
    compat_set = COMPAT.get(decision_audience, set())
    if compat_set & set(metric_audiences):
        return 0.7

    return 0.3


def _score_vector_boost(metric: Dict) -> float:
    """D10: Qdrant vector similarity score (already computed during retrieval)."""
    score = metric.get("score", 0.0)
    if isinstance(score, (int, float)):
        return min(1.0, max(0.0, score))
    return 0.0


# ============================================================================
# Helpers
# ============================================================================

def _ensure_list(val: Any) -> List[str]:
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        return [val] if val else []
    return []


# ============================================================================
# Public API
# ============================================================================

def score_all_metrics(
    metrics: List[Dict[str, Any]],
    decisions: Dict[str, Any],
    scored_context: Optional[Dict[str, Any]] = None,
    data_sources_in_scope: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Score every metric against the resolved decisions.

    Args:
        metrics: List of metric dicts from metrics_registry (resolved_metrics)
        decisions: Output of resolve_decisions()
        scored_context: The dt_scored_context from state (controls, risks, etc.)
        data_sources_in_scope: dt_data_sources_in_scope from state

    Returns:
        List of metrics with added fields:
            composite_score (float 0-1), dimension_scores (dict), low_confidence (bool)
        Sorted by composite_score descending.
    """
    tags = decisions.get("all_tags", {})
    scored_controls = (scored_context or {}).get("controls", [])
    scored_risks = (scored_context or {}).get("risks", [])
    ds_in_scope = data_sources_in_scope or []

    scored_metrics: List[Dict[str, Any]] = []

    for metric in metrics:
        dim_scores = {
            "use_case":       _score_use_case(metric, decisions, tags),
            "goal":           _score_goal(metric, decisions, tags),
            "focus_area":     _score_focus_area(metric, decisions, tags),
            "control_domain": _score_control_domain(metric, scored_controls),
            "risk_category":  _score_risk_category(metric, scored_risks),
            "metric_type":    _score_metric_type(metric, decisions, tags),
            "data_source":    _score_data_source(metric, ds_in_scope),
            "timeframe":      _score_timeframe(metric, decisions, tags),
            "audience":       _score_audience(metric, decisions, tags),
            "vector_boost":   _score_vector_boost(metric),
        }

        raw_score = sum(
            dim_scores[dim] * SCORING_WEIGHTS[dim]
            for dim in dim_scores
        )
        composite = round(raw_score / MAX_SCORE, 4)

        scored_metric = {
            **metric,
            "composite_score": composite,
            "dimension_scores": {k: round(v, 3) for k, v in dim_scores.items()},
            "low_confidence": 0.50 <= composite < 0.65,
        }
        scored_metrics.append(scored_metric)

    scored_metrics.sort(key=lambda m: m["composite_score"], reverse=True)
    return scored_metrics


def apply_thresholds(
    scored_metrics: List[Dict[str, Any]],
    include_threshold: float = 0.50,
    candidate_threshold: float = 0.35,
    required_groups: Optional[List[str]] = None,
    min_metrics_per_group: int = 3,
    min_total_metrics: int = 5,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Apply score thresholds and minimum coverage rules.

    Returns:
        (included, candidates, dropped)
        - included: metrics above include_threshold
        - candidates: metrics between candidate_threshold and include_threshold
                      (pulled in if minimum coverage not met)
        - dropped: metrics below candidate_threshold
    """
    included = []
    candidates = []
    dropped = []

    for m in scored_metrics:
        score = m.get("composite_score", 0)
        if score >= include_threshold:
            included.append(m)
        elif score >= candidate_threshold:
            candidates.append(m)
        else:
            dropped.append(m)

    # Minimum coverage: pull from candidates if needed
    if required_groups and len(included) < min_total_metrics:
        needed = min_total_metrics - len(included)
        promoted = candidates[:needed]
        for p in promoted:
            p["promoted_from_candidate"] = True
            p["low_confidence"] = True
        included.extend(promoted)
        candidates = candidates[needed:]

    # Per-group minimum check
    if required_groups:
        for group_id in required_groups:
            group_metrics = [
                m for m in included
                if group_id in _ensure_list(m.get("group_affinity", []))
            ]
            if len(group_metrics) < min_metrics_per_group:
                # Pull candidates with this group affinity
                group_candidates = [
                    c for c in candidates
                    if group_id in _ensure_list(c.get("group_affinity", []))
                ]
                needed = min_metrics_per_group - len(group_metrics)
                promoted = group_candidates[:needed]
                for p in promoted:
                    p["promoted_from_candidate"] = True
                    p["low_confidence"] = True
                included.extend(promoted)
                candidates = [c for c in candidates if c not in promoted]

    return included, candidates, dropped

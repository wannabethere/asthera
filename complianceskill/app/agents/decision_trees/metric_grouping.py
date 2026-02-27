"""
Metric Decision Tree — Goal-Based Grouping

Assigns scored metrics into goal-aligned insight groups with typed slots
(KPIs, metrics, trends). Each group maps to a medallion plan section and
dashboard panel.

Groups are selected based on the use_case decision and populated from
the scored metric pool using a slot-filling algorithm.
"""
import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
# Group definitions
# ============================================================================

METRIC_GROUPS: Dict[str, Dict[str, Any]] = {
    "compliance_posture": {
        "group_id": "compliance_posture",
        "group_name": "Compliance Posture Overview",
        "goal": "Monitor overall compliance status against framework controls",
        "slots": {
            "kpis":    {"min": 2, "max": 5, "prefer_types": ["percentage", "score"]},
            "metrics": {"min": 3, "max": 8, "prefer_types": ["count", "rate", "percentage"]},
            "trends":  {"min": 1, "max": 3, "prefer_types": ["trend", "rate"]},
        },
        "visualization_suggestions": ["gauge", "scorecard", "trend_line"],
        "audience": ["compliance_team", "executive_board", "auditor"],
        "priority": "high",
        "affinity_categories": [
            "compliance_events", "audit_logging", "access_control",
            "authentication", "vulnerabilities",
        ],
    },
    "control_effectiveness": {
        "group_id": "control_effectiveness",
        "group_name": "Control Effectiveness",
        "goal": "Measure how well individual controls mitigate their target risks",
        "slots": {
            "kpis":    {"min": 2, "max": 4, "prefer_types": ["percentage", "rate"]},
            "metrics": {"min": 3, "max": 10, "prefer_types": ["count", "percentage", "rate"]},
            "trends":  {"min": 1, "max": 3, "prefer_types": ["trend"]},
        },
        "visualization_suggestions": ["heatmap", "bar_chart", "status_matrix"],
        "audience": ["security_ops", "compliance_team"],
        "priority": "high",
        "affinity_categories": [
            "detection_engineering", "access_control", "authentication",
            "mfa_adoption", "compliance_events",
        ],
    },
    "risk_exposure": {
        "group_id": "risk_exposure",
        "group_name": "Risk Exposure Dashboard",
        "goal": "Quantify and track risk exposure across the environment",
        "slots": {
            "kpis":    {"min": 2, "max": 4, "prefer_types": ["score", "count"]},
            "metrics": {"min": 3, "max": 8, "prefer_types": ["count", "percentage", "distribution"]},
            "trends":  {"min": 2, "max": 4, "prefer_types": ["trend", "rate"]},
        },
        "visualization_suggestions": ["risk_matrix", "trend_line", "gauge"],
        "audience": ["risk_management", "executive_board"],
        "priority": "high",
        "affinity_categories": [
            "vulnerabilities", "cve_exposure", "misconfigs",
            "cloud_findings", "patch_compliance",
        ],
    },
    "operational_security": {
        "group_id": "operational_security",
        "group_name": "Operational Security Metrics",
        "goal": "Track day-to-day security operations efficiency",
        "slots": {
            "kpis":    {"min": 2, "max": 5, "prefer_types": ["rate", "count"]},
            "metrics": {"min": 4, "max": 12, "prefer_types": ["count", "rate", "distribution"]},
            "trends":  {"min": 2, "max": 4, "prefer_types": ["trend", "rate"]},
        },
        "visualization_suggestions": ["time_series", "bar_chart", "table"],
        "audience": ["security_ops"],
        "priority": "medium",
        "affinity_categories": [
            "incidents", "mttr", "alert_volume", "siem_events",
            "endpoint_events", "edr_alerts", "network_events",
        ],
    },
    "training_completion": {
        "group_id": "training_completion",
        "group_name": "Training & Learning Targets",
        "goal": "Track LMS training completion rates against compliance targets",
        "slots": {
            "kpis":    {"min": 2, "max": 4, "prefer_types": ["percentage", "count"]},
            "metrics": {"min": 3, "max": 6, "prefer_types": ["count", "percentage", "rate"]},
            "trends":  {"min": 1, "max": 2, "prefer_types": ["trend"]},
        },
        "visualization_suggestions": ["progress_bar", "scorecard", "table"],
        "audience": ["learning_admin", "compliance_team"],
        "priority": "medium",
        "affinity_categories": [
            "training_compliance", "certification",
        ],
    },
    "remediation_velocity": {
        "group_id": "remediation_velocity",
        "group_name": "Remediation Velocity",
        "goal": "Measure speed and completeness of vulnerability and finding remediation",
        "slots": {
            "kpis":    {"min": 2, "max": 4, "prefer_types": ["rate", "count"]},
            "metrics": {"min": 3, "max": 8, "prefer_types": ["count", "rate", "trend"]},
            "trends":  {"min": 2, "max": 3, "prefer_types": ["trend", "rate"]},
        },
        "visualization_suggestions": ["funnel", "trend_line", "bar_chart"],
        "audience": ["security_ops", "compliance_team"],
        "priority": "medium",
        "affinity_categories": [
            "patch_compliance", "mttr", "vulnerabilities", "cve_exposure",
        ],
    },
}


# ============================================================================
# Use case → group mapping
# ============================================================================

USE_CASE_GROUP_CONFIG: Dict[str, Dict[str, Any]] = {
    "soc2_audit": {
        "required_groups": ["compliance_posture", "control_effectiveness", "risk_exposure"],
        "optional_groups": ["operational_security", "remediation_velocity"],
        "default_audience": "auditor",
        "default_timeframe": "monthly",
    },
    "lms_learning_target": {
        "required_groups": ["training_completion", "compliance_posture"],
        "optional_groups": ["control_effectiveness"],
        "default_audience": "learning_admin",
        "default_timeframe": "quarterly",
    },
    "risk_posture_report": {
        "required_groups": ["risk_exposure", "compliance_posture"],
        "optional_groups": ["remediation_velocity"],
        "default_audience": "executive_board",
        "default_timeframe": "monthly",
    },
    "executive_dashboard": {
        "required_groups": ["compliance_posture", "risk_exposure"],
        "optional_groups": ["operational_security"],
        "default_audience": "executive_board",
        "default_timeframe": "monthly",
    },
    "operational_monitoring": {
        "required_groups": ["operational_security", "remediation_velocity"],
        "optional_groups": ["control_effectiveness", "risk_exposure"],
        "default_audience": "security_ops",
        "default_timeframe": "daily",
    },
}


# ============================================================================
# Slot assignment logic
# ============================================================================

def _metric_affinity_score(metric: Dict, group_def: Dict) -> float:
    """
    How well a metric fits a group, based on:
    1. Explicit group_affinity field on the metric
    2. Category match against group's affinity_categories
    3. Control code match (if LLM-generated groups)
    4. Risk code match (if LLM-generated groups)
    5. Keyword match (if LLM-generated groups)
    6. Composite score (tiebreaker)
    """
    group_id = group_def["group_id"]
    score = 0.0

    # Explicit affinity
    affinities = metric.get("group_affinity", [])
    if isinstance(affinities, str):
        affinities = [affinities]
    if group_id in affinities:
        score += 3.0

    # Control code match (LLM-generated groups)
    evidenced_controls = group_def.get("evidences_controls", [])
    if evidenced_controls:
        metric_controls = metric.get("control_evidence_hints", {}).get("best_controls", [])
        if not metric_controls:
            metric_controls = metric.get("mapped_control_codes", []) or metric.get("mapped_control_domains", [])
        overlap = set(evidenced_controls) & set(metric_controls)
        if overlap:
            score += 2.5 * (len(overlap) / max(len(evidenced_controls), 1))

    # Risk code match (LLM-generated groups)
    quantified_risks = group_def.get("quantifies_risks", [])
    if quantified_risks:
        metric_risks = metric.get("risk_quantification_hints", {}).get("best_risks", [])
        if not metric_risks:
            metric_risks = metric.get("mapped_risk_categories", [])
        overlap = set(quantified_risks) & set(metric_risks)
        if overlap:
            score += 2.0 * (len(overlap) / max(len(quantified_risks), 1))

    # Category match
    category = metric.get("category", "")
    affinity_cats = group_def.get("affinity_categories", [])
    if category and category in affinity_cats:
        score += 2.0
    elif category:
        # Partial: check substring match
        for ac in affinity_cats:
            if ac in category or category in ac:
                score += 1.0
                break

    # Keyword match (LLM-generated groups)
    affinity_keywords = group_def.get("affinity_criteria", {}).get("keywords", [])
    if affinity_keywords:
        metric_text = " ".join([
            metric.get("name", ""),
            metric.get("description", ""),
            metric.get("natural_language_question", ""),
        ]).lower()
        matches = sum(1 for kw in affinity_keywords if kw.lower() in metric_text)
        if matches > 0:
            score += 1.0 * (matches / max(len(affinity_keywords), 1))

    # Composite score as tiebreaker
    score += metric.get("composite_score", 0) * 0.5

    return score


def _determine_slot(
    metric: Dict,
    slot_config: Dict[str, Dict],
    filled: Dict[str, int],
) -> Optional[str]:
    """
    Determine which slot (kpis, metrics, trends) a metric should fill.

    Priority: kpis first (if type matches), then trends (if has trend capability),
    then metrics (general pool).
    """
    metric_type = metric.get("metric_type", "")
    has_trends = bool(metric.get("trends", []))
    kpi_eligible = bool(metric.get("kpis", []))

    # Try KPI slot
    kpi_config = slot_config.get("kpis", {})
    kpi_max = kpi_config.get("max", 5)
    kpi_prefer = kpi_config.get("prefer_types", [])
    if filled.get("kpis", 0) < kpi_max:
        if kpi_eligible or metric_type in kpi_prefer:
            return "kpis"

    # Try trend slot
    trend_config = slot_config.get("trends", {})
    trend_max = trend_config.get("max", 3)
    trend_prefer = trend_config.get("prefer_types", [])
    if filled.get("trends", 0) < trend_max:
        if has_trends or metric_type in trend_prefer or metric_type == "trend":
            return "trends"

    # Default: metric slot
    metric_config = slot_config.get("metrics", {})
    metric_max = metric_config.get("max", 10)
    if filled.get("metrics", 0) < metric_max:
        return "metrics"

    return None  # all slots full


def _build_metric_entry(metric: Dict, slot: str, group_id: str) -> Dict[str, Any]:
    """Build a clean metric entry for a group slot."""
    return {
        "metric_id": metric.get("metric_id") or metric.get("id", ""),
        "name": metric.get("name", ""),
        "description": metric.get("description", ""),
        "category": metric.get("category", ""),
        "composite_score": metric.get("composite_score", 0),
        "role": slot.rstrip("s"),  # "kpis" → "kpi"
        "group_id": group_id,
        "metric_type": metric.get("metric_type", ""),
        "mapped_controls": metric.get("mapped_control_codes", []) or metric.get("mapped_control_domains", []),
        "mapped_risks": metric.get("mapped_risk_categories", []),
        "source_schemas": metric.get("source_schemas", []),
        "source_capabilities": metric.get("source_capabilities", []),
        "kpis": metric.get("kpis", []),
        "trends": metric.get("trends", []),
        "natural_language_question": metric.get("natural_language_question", ""),
        "data_filters": metric.get("data_filters", []),
        "data_groups": metric.get("data_groups", []),
        "low_confidence": metric.get("low_confidence", False),
        "promoted_from_candidate": metric.get("promoted_from_candidate", False),
    }


# ============================================================================
# Public API
# ============================================================================

def group_metrics(
    scored_metrics: List[Dict[str, Any]],
    decisions: Dict[str, Any],
    llm_generated_groups: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Group scored metrics into goal-aligned insight groups with typed slots.

    Args:
        scored_metrics: Output of score_all_metrics() after threshold filtering (included list)
        decisions: Output of resolve_decisions()

    Returns:
        {
            "decision_summary": {...},
            "groups": [
                {
                    "group_id": str,
                    "group_name": str,
                    "goal": str,
                    "priority": str,
                    "audience": [...],
                    "visualization_suggestions": [...],
                    "kpis": [...],
                    "metrics": [...],
                    "trends": [...],
                    "slot_coverage": {"kpis": "2/4", ...},
                }
            ],
            "overflow_metrics": [...],
            "coverage_report": {...},
        }
    """
    use_case = decisions.get("use_case", "soc2_audit")
    
    # Use LLM-generated groups if available, else fall back to static config
    if llm_generated_groups and len(llm_generated_groups) > 0:
        # Build group map from LLM-generated groups
        llm_group_map = {g.get("group_id", ""): g for g in llm_generated_groups}
        # Extract required/optional from LLM groups (priority field indicates required)
        required_group_ids = [g.get("group_id") for g in llm_generated_groups if g.get("priority") == "high"]
        optional_group_ids = [g.get("group_id") for g in llm_generated_groups if g.get("priority") != "high"]
        # Use LLM groups as the source of truth
        active_groups = llm_generated_groups
    else:
        # Fall back to static config
        use_case_config = USE_CASE_GROUP_CONFIG.get(use_case, USE_CASE_GROUP_CONFIG["soc2_audit"])
        required_group_ids = use_case_config["required_groups"]
        optional_group_ids = use_case_config.get("optional_groups", [])
        active_groups = None  # Will use METRIC_GROUPS

    # Track which metrics have been assigned
    assigned_metric_ids: Set[str] = set()
    groups: List[Dict[str, Any]] = []
    overflow: List[Dict[str, Any]] = []

    # Process required groups first, then optional
    all_group_ids = required_group_ids + [
        g for g in optional_group_ids
    ]

    for group_id in all_group_ids:
        # Get group definition from LLM-generated or static
        if active_groups:
            group_def = next((g for g in active_groups if g.get("group_id") == group_id), None)
            if not group_def:
                logger.warning(f"Group '{group_id}' not found in LLM-generated groups, skipping")
                continue
            # Convert LLM group format to expected format
            group_def = {
                "group_id": group_def.get("group_id", group_id),
                "group_name": group_def.get("group_name", group_id),
                "goal": group_def.get("goal", ""),
                "slots": group_def.get("slots", {}),
                "visualization_suggestions": group_def.get("visualization_suggestions", []),
                "audience": group_def.get("audience", []),
                "priority": group_def.get("priority", "medium"),
                "affinity_categories": group_def.get("affinity_criteria", {}).get("categories", []),
                "evidences_controls": group_def.get("evidences_controls", []),
                "quantifies_risks": group_def.get("quantifies_risks", []),
            }
        else:
            group_def = METRIC_GROUPS.get(group_id)
            if not group_def:
                logger.warning(f"Group '{group_id}' not found in METRIC_GROUPS, skipping")
                continue

        # Score and sort candidates for this group
        candidates = []
        for m in scored_metrics:
            mid = m.get("metric_id") or m.get("id", "")
            if mid in assigned_metric_ids:
                continue
            affinity = _metric_affinity_score(m, group_def)
            if affinity > 0:
                candidates.append((affinity, m))

        candidates.sort(key=lambda x: x[0], reverse=True)

        # Fill slots
        slot_config = group_def["slots"]
        filled: Dict[str, int] = {"kpis": 0, "metrics": 0, "trends": 0}
        group_kpis: List[Dict] = []
        group_metrics_list: List[Dict] = []
        group_trends: List[Dict] = []
        slot_lists = {"kpis": group_kpis, "metrics": group_metrics_list, "trends": group_trends}

        for _affinity, metric in candidates:
            slot = _determine_slot(metric, slot_config, filled)
            if slot is None:
                continue  # all slots full for this group

            mid = metric.get("metric_id") or metric.get("id", "")
            entry = _build_metric_entry(metric, slot, group_id)
            slot_lists[slot].append(entry)
            filled[slot] += 1
            if mid:
                assigned_metric_ids.add(mid)

        # Build slot coverage strings
        slot_coverage = {}
        for slot_name, slot_def in slot_config.items():
            slot_coverage[slot_name] = f"{filled[slot_name]}/{slot_def['max']}"

        is_required = group_id in required_group_ids

        # Only include group if it has at least one metric OR is required
        if any(filled.values()) or is_required:
            groups.append({
                "group_id": group_id,
                "group_name": group_def["group_name"],
                "goal": group_def["goal"],
                "priority": group_def["priority"] if is_required else "optional",
                "audience": group_def["audience"],
                "visualization_suggestions": group_def["visualization_suggestions"],
                "kpis": group_kpis,
                "metrics": group_metrics_list,
                "trends": group_trends,
                "slot_coverage": slot_coverage,
                "total_assigned": sum(filled.values()),
                "is_required": is_required,
            })

    # Collect overflow (scored but unassigned metrics)
    for m in scored_metrics:
        mid = m.get("metric_id") or m.get("id", "")
        if mid and mid not in assigned_metric_ids:
            overflow.append(_build_metric_entry(m, "metrics", "overflow"))

    # Coverage report
    total_assigned = sum(g["total_assigned"] for g in groups)
    groups_full_coverage = sum(
        1 for g in groups
        if all(
            int(g["slot_coverage"][s].split("/")[0]) >= METRIC_GROUPS[g["group_id"]]["slots"][s]["min"]
            for s in METRIC_GROUPS[g["group_id"]]["slots"]
        )
    )
    groups_partial = len([g for g in groups if g["total_assigned"] > 0]) - groups_full_coverage
    unserved = [
        gid for gid in required_group_ids
        if not any(g["group_id"] == gid and g["total_assigned"] > 0 for g in groups)
    ]

    coverage_report = {
        "total_metrics_scored": len(scored_metrics),
        "total_metrics_selected": total_assigned,
        "overflow_count": len(overflow),
        "groups_with_full_coverage": groups_full_coverage,
        "groups_with_partial_coverage": groups_partial,
        "unserved_groups": unserved,
        "dropped_metrics_count": len(scored_metrics) - total_assigned - len(overflow),
    }

    # Decision summary
    decision_summary = {
        "use_case": use_case,
        "goal": decisions.get("goal", ""),
        "focus_area": decisions.get("focus_area", ""),
        "audience": decisions.get("audience", ""),
        "timeframe": decisions.get("timeframe", ""),
        "metric_type": decisions.get("metric_type", ""),
        "auto_resolve_confidence": decisions.get("auto_resolve_confidence", 0),
        "resolved_from": decisions.get("resolved_from", []),
        "unresolved": decisions.get("unresolved", []),
    }

    return {
        "decision_summary": decision_summary,
        "groups": groups,
        "overflow_metrics": overflow,
        "coverage_report": coverage_report,
    }


def get_required_groups(use_case: str) -> List[str]:
    """Return the list of required group IDs for a given use case."""
    config = USE_CASE_GROUP_CONFIG.get(use_case, USE_CASE_GROUP_CONFIG.get("soc2_audit", {}))
    return config.get("required_groups", [])

"""
CSOD Intent Config — DT + CCE per-intent (prompts_updates v2.2)

DT_INTENT_CONFIG: Decision Tree resolver parameters per intent.
CCE_INTENT_CONFIG: Causal graph (CCE) enabled/mode per intent.
Data intelligence intents skip DT and CCE (short-circuit or no CCE).
"""

from typing import Any, Dict, List, Optional

# ─── Data intents that skip DT resolver (no qualification step) ─────────────
# data_planner runs DT (spec: 5-6 +1 DT, 0 CCE → 6-7 total)
SKIP_DT_INTENTS = frozenset({
    "data_discovery",
    "data_quality_analysis",
    "data_lineage",
})

# ─── DT resolution map (per intent) ────────────────────────────────────────
DT_INTENT_CONFIG: Dict[str, Dict[str, Any]] = {
    "crown_jewel_analysis": {
        "use_case": "lms_learning_target",
        "goal": ["training_completion", "compliance_posture_unification"],
        "metric_type": ["current_state", "trend"],
        "audience": None,
        "timeframe": "ytd",
        "dt_group_by": "goal",
        "min_composite": 0.60,
    },
    "gap_analysis": {
        "use_case": "lms_learning_target",
        "goal": None,
        "metric_type": "current_state",
        "audience": None,
        "timeframe": None,
        "dt_group_by": "goal",
        "min_composite": 0.55,
        "requires_target_value": True,
    },
    "anomaly_detection": {
        "use_case": "lms_learning_target",
        "goal": None,
        "metric_type": "trend",
        "audience": None,
        "timeframe": None,
        "dt_group_by": "focus_area",
        "min_composite": 0.55,
        "enforce_trend_only": True,
    },
    "funnel_analysis": {
        "use_case": "lms_learning_target",
        "goal": "training_completion",
        "metric_type": "current_state",
        "audience": None,
        "timeframe": None,
        "dt_group_by": "goal",
        "min_composite": 0.55,
        "requires_funnel_stages": True,
    },
    "cohort_analysis": {
        "use_case": "lms_learning_target",
        "goal": None,
        "metric_type": ["current_state", "trend"],
        "audience": None,
        "timeframe": None,
        "dt_group_by": "focus_area",
        "min_composite": 0.55,
        "requires_segment_dimension": True,
    },
    "benchmark_analysis": {
        "use_case": "lms_learning_target",
        "goal": None,
        "metric_type": "current_state",
        "audience": None,
        "timeframe": None,
        "dt_group_by": "goal",
        "min_composite": 0.50,
        "requires_comparable_value": True,
    },
    "skill_gap_analysis": {
        "use_case": "lms_learning_target",
        "goal": "competency_tracking",
        "metric_type": "current_state",
        "audience": None,
        "timeframe": None,
        "dt_group_by": "goal",
        "min_composite": 0.55,
        "focus_area_override": "talent_management",
    },
    "metrics_recommender_with_gold_plan": {
        "use_case": None,
        "goal": None,
        "metric_type": None,
        "audience": None,
        "timeframe": None,
        "dt_group_by": "goal",
        "min_composite": 0.55,
    },
    "metrics_dashboard_plan": {
        "use_case": None,
        "goal": None,
        "metric_type": None,
        "audience": None,
        "timeframe": None,
        "dt_group_by": "goal",
        "min_composite": 0.55,
    },
    "predictive_risk_analysis": {
        "use_case": "lms_learning_target",
        "goal": "compliance_posture_unification",
        "metric_type": ["current_state", "trend"],
        "audience": None,
        "timeframe": None,
        "dt_group_by": "goal",
        "min_composite": 0.60,
        "requires_deadline_dimension": True,
    },
    "training_roi_analysis": {
        "use_case": "lms_learning_target",
        "goal": "enterprise_learning_measurement",
        "metric_type": "current_state",
        "audience": None,
        "timeframe": None,
        "dt_group_by": "goal",
        "min_composite": 0.55,
        "requires_cost_and_outcome_pair": True,
    },
    "metric_kpi_advisor": {
        "use_case": None,
        "goal": None,
        "metric_type": None,
        "audience": None,
        "timeframe": None,
        "dt_group_by": "focus_area",
        "min_composite": 0.55,
    },
    "dashboard_generation_for_persona": {
        "use_case": None,
        "goal": None,
        "metric_type": ["current_state", "trend"],
        "audience": None,
        "timeframe": None,
        "dt_group_by": "goal",
        "min_composite": 0.50,
    },
    "compliance_test_generator": {
        "use_case": "soc2_audit",
        "goal": "compliance_posture_unification",
        "metric_type": "current_state",
        "audience": None,
        "timeframe": None,
        "dt_group_by": "goal",
        "min_composite": 0.55,
    },
    "data_planner": {
        "use_case": None,
        "goal": None,
        "metric_type": None,
        "audience": None,
        "timeframe": None,
        "dt_group_by": "goal",
        "min_composite": 0.55,
    },
}

# ─── CCE enable/disable per intent ──────────────────────────────────────────
CCE_INTENT_CONFIG: Dict[str, Dict[str, Any]] = {
    "crown_jewel_analysis": {"enabled": True, "mode": "required"},
    "gap_analysis": {"enabled": True, "mode": "required"},
    "anomaly_detection": {"enabled": True, "mode": "required"},
    "predictive_risk_analysis": {"enabled": True, "mode": "required"},
    "training_roi_analysis": {"enabled": True, "mode": "required"},
    "metric_kpi_advisor": {"enabled": True, "mode": "required"},
    "funnel_analysis": {"enabled": True, "mode": "optional"},
    "cohort_analysis": {"enabled": True, "mode": "optional"},
    "skill_gap_analysis": {"enabled": True, "mode": "optional"},
    "metrics_recommender_with_gold_plan": {"enabled": True, "mode": "optional"},
    "metrics_dashboard_plan": {"enabled": True, "mode": "optional"},
    "dashboard_generation_for_persona": {"enabled": True, "mode": "optional"},
    "compliance_test_generator": {"enabled": True, "mode": "optional"},
    "benchmark_analysis": {"enabled": False, "mode": "disabled"},
    "data_discovery": {"enabled": False, "mode": "disabled"},
    "data_lineage": {"enabled": False, "mode": "disabled"},
    "data_quality_analysis": {"enabled": False, "mode": "disabled"},
    "data_planner": {"enabled": False, "mode": "disabled"},
}


def get_dt_config_for_intent(intent: Optional[str]) -> Dict[str, Any]:
    """Return DT config for intent; empty dict if intent skips DT or unknown."""
    if not intent or intent in SKIP_DT_INTENTS:
        return {}
    return DT_INTENT_CONFIG.get(intent, {}).copy()


def get_cce_enabled_for_intent(intent: Optional[str]) -> bool:
    """Return whether CCE (causal graph) is enabled for this intent."""
    if not intent:
        return False
    return CCE_INTENT_CONFIG.get(intent, {}).get("enabled", False)


def get_cce_mode_for_intent(intent: Optional[str]) -> str:
    """Return CCE mode: required | optional | disabled."""
    if not intent:
        return "disabled"
    return CCE_INTENT_CONFIG.get(intent, {}).get("mode", "disabled")


def should_skip_dt_for_intent(intent: Optional[str]) -> bool:
    """True if decision_tree_resolver should be skipped (data intents)."""
    return intent in SKIP_DT_INTENTS

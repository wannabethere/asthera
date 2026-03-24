"""
CSOD Intent Config — DT + CCE per-intent (prompts_updates v2.2)

DT_INTENT_CONFIG: Decision Tree resolver parameters per intent.
CCE_INTENT_CONFIG: Causal graph (CCE) enabled/mode per intent.
Data intelligence intents skip DT and CCE (short-circuit or no CCE).
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Lexy / classifier stage_1 fixtures (editable JSON)
_APP_DIR = Path(__file__).resolve().parents[2]
STAGE_1_INTENT_EXAMPLES_PATH = _APP_DIR / "config" / "stage_1_intent_examples.json"
_SKILL_ROOT = Path(__file__).resolve().parents[3]
LMS_USE_CASE_GROUPS_PATH = _SKILL_ROOT / "config" / "lms_metric_use_case_groups_v2.json"

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
    "behavioral_analysis": {
        "use_case": "lms_learning_target",
        "goal": None,
        "metric_type": ["current_state", "trend"],
        "audience": None,
        "timeframe": None,
        "dt_group_by": "focus_area",
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
    "crown_jewel_analysis": {
        "enabled": True,
        "mode": "required",
        "causal_graph_provides": "csod_causal_centrality (topology)",
        "executor_uses": "unified tail: metrics_recommender uses centrality for impact / prioritization framing",
    },
    "gap_analysis": {
        "enabled": True,
        "mode": "required",
        "causal_graph_provides": "csod_causal_edges",
        "executor_uses": "unified tail: metrics_recommender + graph context (no separate gap_analyzer node)",
    },
    "anomaly_detection": {
        "enabled": True,
        "mode": "required",
        "causal_graph_provides": "csod_causal_edges (graph walk)",
        "executor_uses": "unified tail: metrics_recommender + graph walk context",
    },
    "predictive_risk_analysis": {
        "enabled": True,
        "mode": "required",
        "causal_graph_provides": "csod_causal_edges",
        "executor_uses": "unified tail: metrics_recommender + risk framing from graph edges",
    },
    "training_roi_analysis": {
        "enabled": True,
        "mode": "required",
        "causal_graph_provides": "csod_causal_edges",
        "executor_uses": "unified tail: metrics_recommender + ROI-oriented recommendations",
    },
    "metric_kpi_advisor": {
        "enabled": True,
        "mode": "required",
        "causal_graph_provides": "full graph (nodes, edges, centrality)",
        "executor_uses": "graph-as-answer for reasoning; no spine Shapley",
    },
    "funnel_analysis": {
        "enabled": True,
        "mode": "optional",
        "causal_graph_provides": "csod_causal_edges",
        "executor_uses": "unified tail: metrics_recommender + funnel-oriented framing",
    },
    "cohort_analysis": {
        "enabled": True,
        "mode": "optional",
        "causal_graph_provides": "csod_causal_edges",
        "executor_uses": "unified tail: metrics_recommender + segment/cohort framing",
    },
    "skill_gap_analysis": {
        "enabled": True,
        "mode": "optional",
        "causal_graph_provides": "csod_causal_edges",
        "executor_uses": "unified tail: metrics_recommender + competency-gap framing",
    },
    "metrics_recommender_with_gold_plan": {
        "enabled": True,
        "mode": "optional",
        "causal_graph_provides": "csod_causal_centrality",
        "executor_uses": "metrics_recommender leading/lagging tags",
    },
    "metrics_dashboard_plan": {
        "enabled": True,
        "mode": "optional",
        "causal_graph_provides": "csod_causal_centrality",
        "executor_uses": "optional annotation on recommendations",
    },
    "dashboard_generation_for_persona": {
        "enabled": True,
        "mode": "optional",
        "causal_graph_provides": "csod_causal_centrality",
        "executor_uses": "layout/dashboard ordering — topology only",
    },
    "compliance_test_generator": {
        "enabled": True,
        "mode": "optional",
        "causal_graph_provides": "csod_causal_edges",
        "executor_uses": "internal Shapley → test_case.severity_weight",
    },
    "behavioral_analysis": {
        "enabled": True,
        "mode": "required",
        "causal_graph_provides": "csod_causal_edges",
        "executor_uses": "unified tail: metrics_recommender + engagement/behavior framing",
    },
    "benchmark_analysis": {
        "enabled": False,
        "mode": "disabled",
        "rationale": "Relative comparison — no causal structure",
    },
    "data_discovery": {"enabled": False, "mode": "disabled"},
    "data_lineage": {"enabled": False, "mode": "disabled"},
    "data_quality_analysis": {"enabled": False, "mode": "disabled"},
    "data_planner": {"enabled": False, "mode": "disabled"},
}

# Lexy UI / lexy_conversation_flows.json registry labels → pipeline intent for DT, CCE, executors.
INTENT_PIPELINE_ALIASES: Dict[str, str] = {
    "compliance_gap_close": "gap_analysis",
    "current_state_metric_lookup": "metrics_dashboard_plan",
    "training_plan_dashboard": "dashboard_generation_for_persona",
}

# Pipeline-intent families (final_design_flow / Lexy): shapes output assembler + advisory_mode defaults.
_DATA_OPS_PIPELINE_INTENTS: frozenset = frozenset({
    "compliance_test_generator",
    "data_lineage",
    "data_quality_analysis",
    "data_planner",
})
_METRICS_DASHBOARD_FAMILY_PIPELINE_INTENTS: frozenset = frozenset({
    "metrics_dashboard_plan",
    "metrics_recommender_with_gold_plan",
    "metric_kpi_advisor",
    "crown_jewel_analysis",
    "data_discovery",
    "dashboard_generation_for_persona",
})


def get_intent_family_for_pipeline_intent(pipeline_intent: Optional[str]) -> str:
    """Broad UX family: metrics_dashboard | analysis | data_ops (canonical pipeline intent)."""
    if not pipeline_intent:
        return "analysis"
    if pipeline_intent in _DATA_OPS_PIPELINE_INTENTS:
        return "data_ops"
    if pipeline_intent in _METRICS_DASHBOARD_FAMILY_PIPELINE_INTENTS:
        return "metrics_dashboard"
    return "analysis"


def get_default_advisory_mode_for_pipeline_intent(pipeline_intent: Optional[str]) -> bool:
    """Advisory tone default: True for metrics_dashboard family, False for analysis and data_ops."""
    return get_intent_family_for_pipeline_intent(pipeline_intent) == "metrics_dashboard"

# Default quadrant for stage_1_intent when the model omits it (Lexy pipeline viewer).
DEFAULT_QUADRANT_BY_REGISTRY_INTENT: Dict[str, str] = {
    "compliance_gap_close": "Diagnostic",
    "gap_analysis": "Diagnostic",
    "anomaly_detection": "Diagnostic",
    "cohort_analysis": "Exploratory",
    "current_state_metric_lookup": "Exploratory",
    "predictive_risk_analysis": "Predictive",
    "dashboard_generation_for_persona": "Operational",
    "training_plan_dashboard": "Operational",
    "metrics_dashboard_plan": "Operational",
    "metrics_recommender_with_gold_plan": "Exploratory",
    "metric_kpi_advisor": "Exploratory",
    "data_discovery": "Exploratory",
    "data_lineage": "Exploratory",
    "data_quality_analysis": "Diagnostic",
    "data_planner": "Operational",
    "compliance_test_generator": "Operational",
    "crown_jewel_analysis": "Exploratory",
    "funnel_analysis": "Exploratory",
    "benchmark_analysis": "Exploratory",
    "skill_gap_analysis": "Diagnostic",
    "training_roi_analysis": "Exploratory",
    "behavioral_analysis": "Exploratory",
}


def resolve_pipeline_intent(intent_id: Optional[str]) -> Optional[str]:
    """Map Lexy/registry label to canonical pipeline intent (DT + executor routing)."""
    if not intent_id:
        return None
    return INTENT_PIPELINE_ALIASES.get(intent_id, intent_id)


def default_quadrant_for_intent(registry_intent: Optional[str]) -> str:
    if not registry_intent:
        return "Exploratory"
    if registry_intent in DEFAULT_QUADRANT_BY_REGISTRY_INTENT:
        return DEFAULT_QUADRANT_BY_REGISTRY_INTENT[registry_intent]
    canon = resolve_pipeline_intent(registry_intent) or registry_intent
    return DEFAULT_QUADRANT_BY_REGISTRY_INTENT.get(canon, "Exploratory")


def _signals_from_classifier_result(result: Dict[str, Any]) -> List[Dict[str, str]]:
    """Normalize intent_signals to Lexy stage_1 signal rows {key, value}."""
    out: List[Dict[str, str]] = []
    raw = result.get("intent_signals") or []
    for i, item in enumerate(raw):
        if isinstance(item, dict) and "key" in item and "value" in item:
            out.append({"key": str(item["key"]), "value": str(item["value"])})
        elif isinstance(item, str):
            out.append({"key": f"signal_{i + 1}", "value": item})
    return out


def build_stage_1_intent_from_classifier(
    result: Dict[str, Any],
    registry_intent: str,
) -> Dict[str, Any]:
    """
    Shape aligned with examples/lexy_conversation_flows.json ``stage_1_intent``
    for pipeline viewers and SSE/API consumers.
    """
    conf = result.get("confidence_score")
    s1 = result.get("stage_1_intent")
    if isinstance(s1, dict):
        merged = dict(s1)
        merged["intent"] = registry_intent
        if conf is not None and merged.get("confidence") is None:
            merged["confidence"] = conf
        merged.setdefault("spine_steps_skipped", [])
        merged.setdefault("tags", [])
        merged.setdefault("routing", "full_spine")
        merged.setdefault("quadrant", default_quadrant_for_intent(registry_intent))
        if not merged.get("signals"):
            merged["signals"] = _signals_from_classifier_result(result)
        merged.setdefault("implicit_questions", [])
        return merged

    tags = result.get("lexy_tags")
    if not isinstance(tags, list):
        tags = []
    implicit = result.get("implicit_questions")
    if not isinstance(implicit, list):
        implicit = []
    routing = result.get("lexy_routing")
    if not isinstance(routing, str) or not routing:
        routing = "full_spine"

    return {
        "intent": registry_intent,
        "confidence": conf,
        "quadrant": default_quadrant_for_intent(registry_intent),
        "routing": routing,
        "spine_steps_skipped": [],
        "tags": [str(t) for t in tags],
        "signals": _signals_from_classifier_result(result),
        "implicit_questions": [str(x) for x in implicit],
    }


# Keys in DT_INTENT_CONFIG that become hints in the LLM catalog (typical_analysis_flags)
_DT_HINT_KEYS: Tuple[str, ...] = (
    "requires_target_value",
    "enforce_trend_only",
    "requires_funnel_stages",
    "requires_segment_dimension",
    "requires_comparable_value",
    "requires_deadline_dimension",
    "requires_cost_and_outcome_pair",
)

# Human-oriented catalog for the shared analysis intent classifier (injected as JSON).
INTENT_CATALOG_ENTRIES: Dict[str, Dict[str, Any]] = {
    "data_discovery": {
        "description": "User wants an inventory of data assets, schemas, tables, or capabilities available for analysis.",
        "examples": [
            "What tables do we have for learning completion?",
            "What can I analyze with my current CSOD connection?",
        ],
        "use_cases": ["Onboarding analysts", "Scoping a new dashboard", "Pre-flight before metrics work"],
    },
    "data_lineage": {
        "description": "User wants to trace where a metric or field is sourced from, or downstream dependencies.",
        "examples": [
            "Where does this completion rate in the dashboard come from?",
            "What raw feeds feed the gold compliance course table?",
        ],
        "use_cases": ["Explainability", "Debugging metric drift", "Impact analysis before schema change"],
    },
    "data_quality_analysis": {
        "description": "User wants to assess trustworthiness of data: freshness, completeness, duplicates, integrity.",
        "examples": [
            "Can we trust last month’s assignment data?",
            "Are there nulls or stale rows in compliance training facts?",
        ],
        "use_cases": ["Pre-analysis validation", "Audit support", "SLA monitoring"],
    },
    "data_planner": {
        "description": "User wants a data-engineering plan: ingestion, medallion layers, dbt models, DAG, schedules.",
        "examples": [
            "Design bronze→silver→gold for course completions and certifications.",
            "What dbt models do we need to support compliance training KPIs?",
        ],
        "use_cases": ["Greenfield pipelines", "Refactoring lakehouse", "Adding a new source"],
    },
    "metrics_dashboard_plan": {
        "description": "User wants a structured plan for which metrics/widgets belong on a dashboard without full persona-specific layout polish.",
        "examples": [
            "Plan a dashboard for training operations leadership.",
            "What should we track for compliance training at a glance?",
        ],
        "use_cases": ["MVP dashboard spec", "Workshop with stakeholders", "Prioritizing KPIs"],
    },
    "metrics_recommender_with_gold_plan": {
        "description": "User wants recommended KPIs/metrics plus how they land in curated (gold) data models.",
        "examples": [
            "Recommend metrics for program utilization with a gold-layer plan.",
            "What should we measure for ILT spend and how do we model it?",
        ],
        "use_cases": ["Metric catalog expansion", "Aligning analytics to medallion design"],
    },
    "dashboard_generation_for_persona": {
        "description": "User wants a concrete dashboard specification tailored to a named audience/persona.",
        "examples": [
            "Build an executive dashboard for compliance training risk.",
            "Learning admin view: overdue assignments and certifications.",
        ],
        "use_cases": ["Role-based reporting", "Exec readouts", "Operational consoles"],
    },
    "compliance_test_generator": {
        "description": "User wants automated checks: SQL-based tests, alert rules, or validation logic for compliance training data.",
        "examples": [
            "SQL checks that flag learners out of compliance with policy X.",
            "Tests that catch missing certifications for regulated roles.",
        ],
        "use_cases": ["Continuous controls", "Audit evidence", "Monitoring"],
    },
    "metric_kpi_advisor": {
        "description": "User wants advice on metric choice, relationships, drivers, or causal-style reasoning between KPIs.",
        "examples": [
            "How does engagement relate to completion and audit findings?",
            "Which leading indicators should we watch for compliance risk?",
        ],
        "use_cases": ["Metric rationalization", "Causal storytelling", "Advisor-style planning"],
    },
    "crown_jewel_analysis": {
        "description": "Identify the highest-impact metrics/programs/nodes in the learning graph (centrality / impact framing).",
        "examples": [
            "What are the crown-jewel metrics for our compliance program?",
            "Which training metrics matter most if we can only watch five?",
        ],
        "use_cases": ["Executive prioritization", "Resource allocation", "Risk concentration"],
    },
    "gap_analysis": {
        "description": "Compare current state to a target, threshold, SLA, or policy requirement and quantify the gap.",
        "examples": [
            "Gap between required and actual certification coverage by role.",
            "How far are we from 95% compliance training completion?",
        ],
        "use_cases": ["Remediation planning", "OKR tracking", "Policy adherence"],
    },
    "anomaly_detection": {
        "description": "Detect unusual spikes/drops or outliers in learning or compliance metrics over time.",
        "examples": [
            "Sudden drop in course completions last week — what looks off?",
            "Unusual pattern in overdue training by org unit.",
        ],
        "use_cases": ["Operations monitoring", "Early warning", "Investigation triage"],
    },
    "funnel_analysis": {
        "description": "Analyze multi-stage processes (assign → start → complete → certify) with conversion between stages.",
        "examples": [
            "Funnel from assignment to certification for safety training.",
            "Where do learners drop off between launch and completion?",
        ],
        "use_cases": ["Program redesign", "Content effectiveness", "Process bottlenecking"],
    },
    "cohort_analysis": {
        "description": "Compare segments (cohorts) such as role, region, hire cohort, or business unit.",
        "examples": [
            "New hires vs tenured employees on compliance completion.",
            "Compare EMEA vs AMER certification rates.",
        ],
        "use_cases": ["Equity analysis", "Localization insights", "Segmented interventions"],
    },
    "benchmark_analysis": {
        "description": "Compare against external or internal benchmarks, peer groups, or industry references.",
        "examples": [
            "How do we stack up against last year’s Q4 benchmark?",
            "Compare our completion rates to the industry pack we bought.",
        ],
        "use_cases": ["Board reporting", "Competitive posture", "Normalization"],
    },
    "skill_gap_analysis": {
        "description": "Assess competency or skill coverage vs role needs; training priorities for closing gaps.",
        "examples": [
            "Skill gaps for cyber roles vs completed security curricula.",
            "Which teams are missing required competencies?",
        ],
        "use_cases": ["Workforce planning", "Curriculum investment", "Role readiness"],
    },
    "predictive_risk_analysis": {
        "description": "Forward-looking risk: who is likely to miss deadlines, fall out of compliance, or breach policy if trends continue.",
        "examples": [
            "Who is going to miss compliance training before next Friday?",
            "Predict certification lapses in the next 30 days.",
        ],
        "use_cases": ["Proactive nudges", "Risk dashboards", "Capacity planning"],
    },
    "training_roi_analysis": {
        "description": "Relate training cost or effort to outcomes (performance, compliance, retention, productivity).",
        "examples": [
            "ROI of leadership training on promotion rates.",
            "Did compliance training spend correlate with fewer audit findings?",
        ],
        "use_cases": ["Budget justification", "Program rationalization", "Executive storytelling"],
    },
    "behavioral_analysis": {
        "description": "Study engagement behaviors (logins, time on platform, patterns) and link to outcomes.",
        "examples": [
            "Do frequent LMS users complete compliance training faster?",
            "Engagement patterns before certification success.",
        ],
        "use_cases": ["Adoption programs", "Intervention design", "Hypothesis testing"],
    },
    # ─── Lexy conversation registry ids (lexy_conversation_flows.json) ─────────
    "compliance_gap_close": {
        "description": "Lexy registry: audit- or deadline-driven compliance rate gap (current vs target) with remediation framing — routes as gap_analysis in the pipeline.",
        "examples": [
            "We have a SOC2 audit in 30 days. Our security compliance training rate is at 71%. We need to get to 90%. What's the gap and how do we close it?",
        ],
        "use_cases": ["SOC2 / audit countdown", "Policy target catch-up", "Gap close playbooks"],
    },
    "current_state_metric_lookup": {
        "description": "Lexy registry: single headline metric at a point in time or simple weekly rollup — minimal causal work; routes as metrics_dashboard_plan.",
        "examples": [
            "What's our overall training completion rate this week across all active learners?",
        ],
        "use_cases": ["Weekly ops pulse", "Exec one-number questions", "Before drilling into cohorts"],
    },
    "training_plan_dashboard": {
        "description": "Lexy registry: training plan administration view (goals, activities, assign status by division) — routes as dashboard_generation_for_persona.",
        "examples": [
            "Show me the training plan management view for the Procurement division.",
        ],
        "use_cases": ["HR BP plan review", "Division-scoped plan status", "Assign-level tables"],
    },
}


def get_analysis_intent_catalog_for_llm() -> List[Dict[str, Any]]:
    """Rows for JSON injection into the shared analysis intent classifier prompt."""
    rows: List[Dict[str, Any]] = []
    for intent_id in sorted(INTENT_CATALOG_ENTRIES.keys()):
        entry = dict(INTENT_CATALOG_ENTRIES[intent_id])
        row: Dict[str, Any] = {"id": intent_id, **entry}
        pipeline_id = resolve_pipeline_intent(intent_id) or intent_id
        if pipeline_id != intent_id:
            row["maps_to_pipeline_intent"] = pipeline_id
        dt = DT_INTENT_CONFIG.get(pipeline_id, {})
        hints = {k: True for k in _DT_HINT_KEYS if dt.get(k)}
        if hints:
            row["typical_analysis_flags"] = hints
        rows.append(row)
    return rows


def get_csod_intent_classifier_catalog_json(*, indent: int = 2) -> str:
    """Serialized catalog for CSOD (and any consumer sharing the same intent ids)."""
    return json.dumps(get_analysis_intent_catalog_for_llm(), indent=indent)


def load_stage_1_intent_examples() -> Dict[str, Any]:
    """Load static stage_1 intent exemplars from app/config/stage_1_intent_examples.json."""
    with STAGE_1_INTENT_EXAMPLES_PATH.open(encoding="utf-8") as f:
        return json.load(f)


ALLOWED_CSOD_ANALYSIS_INTENTS: frozenset = frozenset(INTENT_CATALOG_ENTRIES.keys())


@lru_cache(maxsize=1)
def _load_lms_use_case_groups_file() -> Dict[str, Any]:
    """LMS use-case groups (lms_metric_use_case_groups_v2.json) for DT + Lexy stage 2 alignment."""
    if not LMS_USE_CASE_GROUPS_PATH.is_file():
        return {}
    with LMS_USE_CASE_GROUPS_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def get_lms_use_case_group(use_case: Optional[str]) -> Dict[str, Any]:
    """Return one use_case_groups entry or {}."""
    data = _load_lms_use_case_groups_file()
    groups = data.get("use_case_groups") or {}
    return dict(groups.get(use_case or "", {}) or {})


def _try_skill_registry() -> Optional[Any]:
    """Lazy-load SkillRegistry — returns None if skills module unavailable."""
    try:
        from app.agents.skills import SkillRegistry
        return SkillRegistry.instance()
    except Exception:
        return None


def _try_domain_config(state: Optional[Dict[str, Any]] = None) -> Optional[Any]:
    """Lazy-load DomainConfig for the active domain."""
    try:
        from app.agents.domain_config import DomainRegistry
        reg = DomainRegistry.instance()
        if state:
            return reg.get_for_state(state)
        return reg.default()
    except Exception:
        return None


def get_dt_config_for_intent(intent: Optional[str], state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Return DT config for intent; empty dict if intent skips DT or unknown.

    Resolution order:
      1. SkillRegistry (skill definition's dt_config)
      2. DT_INTENT_CONFIG (hardcoded fallback)
      3. Overlay use_case from DomainConfig if the static value matches the
         LMS default ("lms_learning_target") and a different domain is active.
    """
    resolved = resolve_pipeline_intent(intent) if intent else None
    key = resolved or intent
    if not key or key in SKIP_DT_INTENTS:
        return {}
    # 1. Skill-based lookup (preferred)
    registry = _try_skill_registry()
    if registry:
        skill = registry.get(key)
        if skill:
            cfg = skill.to_dt_intent_config()
            if cfg:
                return cfg
    # 2. Hardcoded fallback
    cfg = DT_INTENT_CONFIG.get(key, {}).copy()
    # 3. Overlay use_case from DomainConfig when available
    if cfg and cfg.get("use_case") == "lms_learning_target":
        domain_cfg = _try_domain_config(state)
        if domain_cfg and domain_cfg.default_use_case != "lms_learning_target":
            cfg["use_case"] = domain_cfg.default_use_case
    return cfg


def get_cce_enabled_for_intent(intent: Optional[str]) -> bool:
    """Return whether CCE (causal graph) is enabled for this intent."""
    if not intent:
        return False
    key = resolve_pipeline_intent(intent) or intent
    # Skill-based lookup
    registry = _try_skill_registry()
    if registry:
        skill = registry.get(key)
        if skill and skill.data_plan.cce_config:
            return skill.data_plan.cce_config.enabled
    return CCE_INTENT_CONFIG.get(key, {}).get("enabled", False)


def get_cce_mode_for_intent(intent: Optional[str]) -> str:
    """Return CCE mode: required | optional | disabled."""
    if not intent:
        return "disabled"
    key = resolve_pipeline_intent(intent) or intent
    # Skill-based lookup
    registry = _try_skill_registry()
    if registry:
        skill = registry.get(key)
        if skill and skill.data_plan.cce_config:
            return skill.data_plan.cce_config.mode
    return CCE_INTENT_CONFIG.get(key, {}).get("mode", "disabled")


def should_skip_dt_for_intent(intent: Optional[str]) -> bool:
    """True if decision_tree_resolver should be skipped (data intents)."""
    key = resolve_pipeline_intent(intent) if intent else None
    return (key or intent) in SKIP_DT_INTENTS

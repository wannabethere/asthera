"""
Dashboard Decision Tree — Structure & Auto-Resolution

Defines the decision tree questions, option→attribute mappings, keyword-based
auto-resolve hints, and state-field resolution logic for dashboard/template
selection.

Pattern mirrors metric_decision_tree.py exactly. Seven questions instead of
six — destination_type is resolved first (gates all template filtering) and
interaction_mode is added as Q7.

LLM resolution uses prompt: 18_resolve_dashboard_decisions.md
Fallback uses keyword matching from VALID_OPTIONS.
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
# Data structures  (identical to metric_decision_tree.py)
# ============================================================================

@dataclass
class DecisionOption:
    """Single selectable option within a decision question."""
    option_id: str
    label: str
    description: str = ""
    tags: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionQuestion:
    """One axis of the decision tree."""
    key: str
    question: str
    options: List[DecisionOption] = field(default_factory=list)
    required: bool = True
    default: Optional[str] = None

    def option_ids(self) -> List[str]:
        return [o.option_id for o in self.options]

    def get_option(self, option_id: str) -> Optional[DecisionOption]:
        for o in self.options:
            if o.option_id == option_id:
                return o
        return None


# ============================================================================
# Minimal decision tree structure
#
# The full structure (labels, keywords, tags) lives in the LLM prompt
# (18_resolve_dashboard_decisions.md).  This minimal structure is used for:
#   - Validating LLM responses
#   - Building clarification questions
#   - Tag merging after resolution
# ============================================================================

# Q6 (destination_type) is listed first: it is the gate — resolved before
# any template scoring begins.  Its resolution_priority=0.
DECISION_QUESTIONS: List[DecisionQuestion] = [
    DecisionQuestion(
        key="destination_type",
        question="Where will the dashboard be rendered or delivered?",
        required=True,
        default="embedded",
        options=[],
    ),
    DecisionQuestion(
        key="category",
        question="What is the primary domain or purpose of this dashboard?",
        required=True,
        default="security_operations",
        options=[],
    ),
    DecisionQuestion(
        key="focus_area",
        question="What is the primary focus area within that domain?",
        required=True,
        default="vulnerability_management",
        options=[],
    ),
    DecisionQuestion(
        key="metric_profile",
        question="What types of metrics dominate this dataset?",
        required=False,
        default="mixed",
        options=[],
    ),
    DecisionQuestion(
        key="audience",
        question="Who is the primary audience for this dashboard?",
        required=False,
        default="security_ops",
        options=[],
    ),
    DecisionQuestion(
        key="complexity",
        question="How much detail is required?",
        required=False,
        default="medium",
        options=[],
    ),
    DecisionQuestion(
        key="interaction_mode",
        question="How will users interact with the dashboard?",
        required=False,
        default="drill_down",
        options=[],
    ),
]

QUESTION_MAP: Dict[str, DecisionQuestion] = {q.key: q for q in DECISION_QUESTIONS}

# Valid option IDs — used for LLM response validation and clarification
VALID_OPTIONS: Dict[str, List[str]] = {
    "destination_type": [
        "embedded", "powerbi", "simple", "slack_digest", "api_json",
    ],
    "category": [
        "compliance_audit", "security_operations", "learning_development",
        "hr_workforce", "risk_management", "executive_reporting",
        "data_operations", "cross_domain",
    ],
    "focus_area": [
        "vulnerability_management", "incident_response", "threat_detection",
        "asset_inventory", "access_control", "audit_logging", "change_management",
        "data_protection", "training_completion", "learner_engagement",
        "content_effectiveness", "compliance_posture", "pipeline_health",
        "data_quality", "vendor_risk", "risk_exposure",
    ],
    "metric_profile": [
        "count_heavy", "trend_heavy", "rate_percentage",
        "comparison", "mixed", "scorecard",
    ],
    "audience": [
        "security_ops", "soc_analyst", "compliance_team", "executive_board",
        "risk_management", "learning_admin", "data_engineer",
    ],
    "complexity": ["low", "medium", "high"],
    "interaction_mode": [
        "drill_down", "read_only", "real_time", "scheduled_report",
    ],
}

# ── Destination gates ─────────────────────────────────────────────────────
# These control which layout primitives are allowed for each destination.
# Applied as a hard filter before any template scoring.
DESTINATION_GATES: Dict[str, Dict[str, Any]] = {
    "embedded": {
        "allowed_all": True,
    },
    "powerbi": {
        "excluded_primitives": [
            "chat_panel", "causal_graph", "heatmap_calendar", "sankey", "treemap",
        ],
    },
    "simple": {
        "allowed_primitives": ["kpi_strip", "bar", "line", "table"],
        "max_panels": 2,
    },
    "slack_digest": {
        "allowed_primitives": ["kpi_strip"],
        "max_kpi_cells": 6,
    },
    "api_json": {
        "emit_metric_spec_only": True,
    },
}

# ── Option tags ────────────────────────────────────────────────────────────
# Used when LLM doesn't return tags, or as a fallback after resolution.
# Mirrors OPTION_TAGS structure in metric_decision_tree.py.
OPTION_TAGS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "destination_type": {
        "embedded": {
            "allowed_primitives": "__all__",
            "supports_chat": True,
            "supports_causal_graph": True,
            "output_format": "eps_json",
        },
        "powerbi": {
            "excluded_primitives": ["chat_panel", "causal_graph"],
            "measure_format": "dax",
            "output_format": "pbix_manifest",
        },
        "simple": {
            "max_panels": 2,
            "excluded_primitives": ["chat_panel", "causal_graph", "filters"],
            "output_format": "html",
        },
        "slack_digest": {
            "max_kpi_cells": 6,
            "output_format": "slack_blocks",
        },
        "api_json": {
            "emit_metric_spec_only": True,
            "output_format": "metric_spec_json",
        },
    },
    "category": {
        "compliance_audit": {
            "registry_target": "dashboard_registry",
            "focus_areas_default": ["access_control", "audit_logging", "training_compliance"],
            "theme": "light",
        },
        "security_operations": {
            "registry_target": "dashboard_registry",
            "focus_areas_default": ["vulnerability_management", "incident_response", "threat_detection"],
            "theme": "dark",
        },
        "learning_development": {
            "registry_target": "ld_templates_registry",
            "focus_areas_default": ["training_completion", "learner_engagement", "content_effectiveness"],
            "theme": "light",
        },
        "hr_workforce": {
            "registry_target": "ld_templates_registry",
            "focus_areas_default": ["onboarding_offboarding", "headcount_planning"],
            "theme": "light",
        },
        "risk_management": {
            "registry_target": "dashboard_registry",
            "focus_areas_default": ["vendor_risk", "risk_exposure", "control_effectiveness"],
            "theme": "light",
        },
        "executive_reporting": {
            "registry_target": "dashboard_registry",
            "focus_areas_default": ["compliance_posture", "risk_exposure"],
            "theme": "light",
            "complexity_override": "low",
        },
        "data_operations": {
            "registry_target": "dashboard_registry",
            "focus_areas_default": ["pipeline_health", "data_quality"],
            "theme": "dark",
        },
        "cross_domain": {
            "registry_target": "both",
            "focus_areas_default": ["training_compliance", "access_control"],
            "theme": "light",
        },
    },
    "focus_area": {
        "vulnerability_management": {
            "control_domains": ["CC7", "CC8", "CC3", "164.308(a)(1)"],
            "risk_categories": ["unpatched_systems", "cve_exposure"],
            "chart_type_hints": ["bar_grouped", "line_trend", "gauge"],
        },
        "incident_response": {
            "control_domains": ["CC7", "CC4", "164.308(a)(6)"],
            "risk_categories": ["delayed_response", "uncontained_breach"],
            "chart_type_hints": ["histogram", "line_trend", "stat_card"],
        },
        "threat_detection": {
            "control_domains": ["CC7", "CC4"],
            "risk_categories": ["undetected_breach", "monitoring_gap"],
            "chart_type_hints": ["histogram", "geo_map", "heatmap"],
        },
        "access_control": {
            "control_domains": ["CC6", "CC5", "164.312(a)", "164.308(a)(3)"],
            "risk_categories": ["unauthorized_access", "privilege_escalation"],
            "chart_type_hints": ["bar_grouped", "donut", "stat_card"],
        },
        "audit_logging": {
            "control_domains": ["CC4", "CC7", "164.312(b)"],
            "risk_categories": ["undetected_breach", "log_tampering"],
            "chart_type_hints": ["histogram", "line_trend", "table"],
        },
        "training_completion": {
            "control_domains": ["CC1", "CC2", "164.308(a)(5)"],
            "risk_categories": ["untrained_staff", "compliance_gap"],
            "chart_type_hints": ["donut", "bar_grouped", "kpi_card"],
        },
        "learner_engagement": {
            "control_domains": ["CC1"],
            "risk_categories": ["compliance_gap"],
            "chart_type_hints": ["line_chart", "area_chart", "kpi_card"],
        },
        "compliance_posture": {
            "control_domains": ["CC1", "CC2", "CC3"],
            "risk_categories": ["governance_failure", "compliance_gap"],
            "chart_type_hints": ["gauge", "stat_card", "bar_grouped"],
        },
        "data_protection": {
            "control_domains": ["CC6", "CC9", "164.312(c)", "164.312(e)"],
            "risk_categories": ["data_leak", "classification_gap"],
            "chart_type_hints": ["donut", "bar_grouped", "heatmap"],
        },
    },
    "audience": {
        "security_ops": {
            "complexity_default": "high",
            "theme": "dark",
            "show_chat": True,
            "interaction_modes": ["drill_down", "real_time"],
        },
        "soc_analyst": {
            "complexity_default": "high",
            "theme": "dark",
            "show_chat": True,
            "interaction_modes": ["drill_down", "real_time"],
        },
        "compliance_team": {
            "complexity_default": "medium",
            "theme": "light",
            "show_chat": False,
            "interaction_modes": ["drill_down", "read_only"],
        },
        "executive_board": {
            "complexity_default": "low",
            "theme": "light",
            "show_chat": False,
            "interaction_modes": ["read_only", "scheduled_report"],
        },
        "risk_management": {
            "complexity_default": "medium",
            "theme": "light",
            "show_chat": False,
            "interaction_modes": ["drill_down", "read_only"],
        },
        "learning_admin": {
            "complexity_default": "medium",
            "theme": "light",
            "show_chat": False,
            "interaction_modes": ["drill_down", "read_only"],
        },
        "data_engineer": {
            "complexity_default": "high",
            "theme": "dark",
            "show_chat": True,
            "interaction_modes": ["drill_down", "real_time"],
        },
    },
    "complexity": {
        "low":    {"max_panels": 2, "max_strip_cells": 4},
        "medium": {"max_panels": 4, "max_strip_cells": 6},
        "high":   {"max_panels": 6, "max_strip_cells": 8, "show_causal_graph": True},
    },
    "interaction_mode": {
        "drill_down":       {"has_filters": True,  "n8n_trigger": None},
        "read_only":        {"has_filters": False, "n8n_trigger": None},
        "real_time":        {"has_filters": True,  "n8n_trigger": "interval_5min"},
        "scheduled_report": {"has_filters": False, "n8n_trigger": "cron"},
    },
}

# ── Taxonomy merge ─────────────────────────────────────────────────────────
# Load dashboard_domain_taxonomy.json and merge goals, focus_areas, audience_levels
# into OPTION_TAGS (mirrors metric_decision_tree use of taxonomy).
try:
    from .dashboard_taxonomy import get_merged_opt_tags
    OPTION_TAGS = get_merged_opt_tags(OPTION_TAGS)
except Exception as e:
    logger.debug("dashboard_decision_tree: taxonomy merge skipped (%s)", e)

# ── Registry routing ───────────────────────────────────────────────────────
REGISTRY_TARGETS: Dict[str, str] = {
    "compliance_audit":     "dashboard_registry",
    "security_operations":  "dashboard_registry",
    "learning_development": "ld_templates_registry",
    "hr_workforce":         "ld_templates_registry",
    "risk_management":      "dashboard_registry",
    "executive_reporting":  "dashboard_registry",
    "data_operations":      "dashboard_registry",
    "cross_domain":         "both",
}

# ── Destination-aware defaults ─────────────────────────────────────────────
_DESTINATION_DEFAULTS: Dict[str, Dict[str, str]] = {
    "embedded":     {"category": "security_operations", "audience": "security_ops",   "complexity": "medium"},
    "powerbi":      {"category": "executive_reporting",  "audience": "executive_board","complexity": "low"},
    "simple":       {"category": "compliance_audit",     "audience": "compliance_team","complexity": "low"},
    "slack_digest": {"category": "executive_reporting",  "audience": "executive_board","complexity": "low"},
    "api_json":     {"category": "security_operations",  "audience": "security_ops",   "complexity": "low"},
}


# ============================================================================
# Metric profile — always deterministic, never LLM
# ============================================================================

def compute_metric_profile(metrics: List[Dict[str, Any]]) -> Tuple[str, float]:
    """
    Deterministically derive metric_profile from the type distribution of
    the metrics list in state.  Returns (option_id, confidence=1.0).

    Called before the LLM resolution so the result can be injected as a
    pre-resolved field in the prompt payload.
    """
    if not metrics:
        return "mixed", 0.5

    _TYPE_PROFILE = {
        "count":              "count_heavy",
        "currency":           "count_heavy",
        "percentage":         "rate_percentage",
        "rate":               "rate_percentage",
        "trend_line":         "trend_heavy",
        "trend":              "trend_heavy",
        "duration":           "trend_heavy",
        "status_distribution":"comparison",
        "distribution":       "comparison",
        "score":              "scorecard",
        "kpi_card":           "scorecard",
    }
    counts: Dict[str, int] = {}
    for m in metrics:
        t = m.get("type") or m.get("metric_type") or m.get("chart_type") or ""
        profile = _TYPE_PROFILE.get(t, "mixed")
        counts[profile] = counts.get(profile, 0) + 1

    dominant = max(counts, key=counts.get)
    ratio = counts[dominant] / len(metrics)
    if ratio >= 0.5:
        return dominant, 1.0
    return "mixed", 1.0


# ============================================================================
# Fallback resolution  (used only if LLM call fails)
# ============================================================================

def _resolve_from_state_fallback(state: Dict[str, Any]) -> Dict[str, Tuple[str, float]]:
    """
    Fallback: simple keyword matching against state fields.
    Only called when the LLM resolution attempt raises an exception.
    """
    resolved: Dict[str, Tuple[str, float]] = {}

    user_query     = state.get("user_query", "").lower()
    intent         = state.get("intent", "").lower()
    framework_id   = (state.get("framework_id") or "").lower()
    output_format  = (state.get("output_format") or
                      state.get("agent_config", {}).get("default_output_format") or "").lower()
    persona        = (state.get("persona") or "").lower()
    timeframe      = (state.get("timeframe") or "").lower()
    data_sources   = state.get("selected_data_sources", [])
    data_enrichment= state.get("data_enrichment", {})
    focus_areas    = data_enrichment.get("suggested_focus_areas", [])

    # ── destination_type ─────────────────────────────────────────────
    if "powerbi" in output_format or "power bi" in user_query:
        resolved["destination_type"] = ("powerbi", 0.95)
    elif "slack" in output_format or "email" in output_format or "digest" in output_format:
        resolved["destination_type"] = ("slack_digest", 0.9)
    elif "simple" in output_format or "html" in output_format or "static" in output_format:
        resolved["destination_type"] = ("simple", 0.9)
    elif "api" in output_format or "json" in output_format or "export" in output_format:
        resolved["destination_type"] = ("api_json", 0.9)
    else:
        resolved["destination_type"] = ("embedded", 0.7)

    # ── category from framework / data sources / keywords ────────────
    if framework_id in ("soc2", "hipaa", "nist_ai_rmf"):
        resolved["category"] = ("compliance_audit", 0.9)
    elif any("cornerstone" in ds or "lms" in ds for ds in data_sources):
        resolved["category"] = ("learning_development", 0.85)
    elif "executive" in intent or "board" in user_query:
        resolved["category"] = ("executive_reporting", 0.8)
    elif any(kw in user_query for kw in ("siem", "incident", "threat", "vulnerability", "edr")):
        resolved["category"] = ("security_operations", 0.75)

    # ── focus_area from suggested_focus_areas ────────────────────────
    if focus_areas:
        fa = focus_areas[0].lower()
        valid_fas = VALID_OPTIONS["focus_area"]
        alias_map = {
            "identity_access_management": "access_control",
            "authentication_mfa":         "access_control",
            "log_management_siem":        "audit_logging",
            "incident_detection":         "incident_response",
            "cloud_security_posture":     "vulnerability_management",
            "patch_management":           "vulnerability_management",
        }
        mapped = alias_map.get(fa, fa)
        if mapped in valid_fas:
            resolved["focus_area"] = (mapped, 0.85)

    # ── audience ──────────────────────────────────────────────────────
    if "executive" in persona or "board" in persona or "ciso" in persona:
        resolved["audience"] = ("executive_board", 0.85)
    elif "compliance" in persona or "auditor" in persona:
        resolved["audience"] = ("compliance_team", 0.85)
    elif "learning" in persona or "training" in persona or "lms" in persona:
        resolved["audience"] = ("learning_admin", 0.85)
    elif "soc" in persona or "analyst" in persona:
        resolved["audience"] = ("soc_analyst", 0.8)

    # ── interaction_mode from timeframe ──────────────────────────────
    if timeframe in ("realtime", "real_time"):
        resolved["interaction_mode"] = ("real_time", 0.9)
    elif any(w in user_query for w in ("scheduled", "daily report", "weekly report")):
        resolved["interaction_mode"] = ("scheduled_report", 0.85)

    return resolved


# ============================================================================
# Primary LLM resolution
# ============================================================================

def _resolve_from_state(
    state: Dict[str, Any],
    preresolved_metric_profile: Optional[str] = None,
) -> Dict[str, Tuple[str, float]]:
    """
    Resolve decisions from state using an LLM call.
    Falls back to _resolve_from_state_fallback() if the LLM call fails.

    preresolved_metric_profile is injected so the LLM does not waste tokens
    reasoning about metric type distributions (it is always deterministic).
    """
    try:
        from app.agents.prompt_loader import load_prompt, PROMPTS_DECISION_TREES
        from app.core.dependencies import get_llm
        from langchain_core.prompts import ChatPromptTemplate
        import json

        prompt_template = load_prompt(
            "18_resolve_dashboard_decisions",
            prompts_dir=str(PROMPTS_DECISION_TREES),
        )

        input_data = {
            "user_query":        state.get("user_query", ""),
            "intent":            state.get("intent", ""),
            "framework_id":      state.get("framework_id"),
            "output_format":     state.get("output_format") or state.get("agent_config", {}).get("default_output_format"),
            "persona":           state.get("persona"),
            "timeframe":         state.get("timeframe"),
            "selected_data_sources": state.get("selected_data_sources", []),
            "data_enrichment":   state.get("data_enrichment", {}),
            "metric_profile_preresolved": preresolved_metric_profile,
        }

        llm = get_llm(temperature=0)
        import json as _json
        system_prompt = prompt_template.replace("{", "{{").replace("}", "}}")
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
        ])
        chain = prompt | llm
        response = chain.invoke({"input": _json.dumps(input_data, indent=2)})
        response_content = response.content if hasattr(response, "content") else str(response)

        # Strip markdown fences
        for fence in ("```json", "```"):
            if fence in response_content:
                start = response_content.find(fence) + len(fence)
                end = response_content.find("```", start)
                if end > start:
                    response_content = response_content[start:end].strip()
                    break

        result = _json.loads(response_content)
        resolved_decisions = result.get("resolved_decisions", {})

        resolved: Dict[str, Tuple[str, float]] = {}
        for q_key, info in resolved_decisions.items():
            if isinstance(info, dict):
                opt_id = info.get("option_id")
                conf   = float(info.get("confidence", 0.5))
                if opt_id and opt_id in VALID_OPTIONS.get(q_key, []):
                    resolved[q_key] = (opt_id, conf)
                elif opt_id:
                    logger.warning(
                        f"_resolve_from_state: Invalid option '{opt_id}' "
                        f"for question '{q_key}' — skipping"
                    )

        # Pass LLM tags downstream via special key (stripped in resolve_decisions)
        if "all_tags" in result:
            resolved["_llm_tags"] = result["all_tags"]

        logger.info(
            f"_resolve_from_state: LLM resolved {len(resolved)} dashboard decisions "
            f"(confidence: {result.get('overall_confidence', 0):.2f})"
        )
        return resolved

    except Exception as exc:
        logger.warning(
            f"_resolve_from_state: LLM resolution failed ({exc}), "
            "falling back to keyword matching",
            exc_info=True,
        )
        return _resolve_from_state_fallback(state)


# ============================================================================
# Keyword auto-resolve  (priority 2)
# ============================================================================

def _resolve_from_keywords(
    user_query: str,
    already_resolved: Dict[str, Tuple[str, float]],
) -> Dict[str, Tuple[str, float]]:
    """
    Score unresolved questions against user_query keywords.
    Fallback only — primary resolution is LLM-based.
    """
    resolved: Dict[str, Tuple[str, float]] = {}
    q = user_query.lower()

    keyword_patterns: Dict[str, Dict[str, List[str]]] = {
        "destination_type": {
            "powerbi":      ["powerbi", "power bi", "pbix", "dax"],
            "embedded":     ["embedded", "echarts", "react", "web"],
            "simple":       ["simple", "static", "html", "pdf"],
            "slack_digest": ["slack", "email", "digest", "notification"],
            "api_json":     ["api", "json", "headless", "export"],
        },
        "category": {
            "compliance_audit":    ["soc2", "hipaa", "nist", "audit", "compliance", "iam"],
            "security_operations": ["incident", "threat", "vulnerability", "siem", "detection", "edr"],
            "learning_development":["training", "lms", "course", "learner", "completion", "csod"],
            "executive_reporting": ["executive", "board", "ciso", "summary", "kpi rollup"],
            "data_operations":     ["pipeline", "dbt", "etl", "data quality", "schema"],
        },
        "focus_area": {
            "vulnerability_management": ["vulnerability", "vuln", "cve", "patch", "cvss"],
            "incident_response":        ["incident", "alert", "triage", "case", "mttr"],
            "access_control":           ["access", "identity", "mfa", "sso", "iam"],
            "training_completion":      ["training", "completion", "assignment", "overdue"],
            "audit_logging":            ["audit", "logging", "siem", "event log"],
        },
        "audience": {
            "executive_board":  ["executive", "board", "ciso"],
            "soc_analyst":      ["analyst", "soc", "tier 1", "tier 2"],
            "compliance_team":  ["compliance", "auditor", "grc"],
            "learning_admin":   ["training admin", "l&d", "lms admin"],
        },
        "interaction_mode": {
            "real_time":        ["real time", "live", "streaming", "realtime"],
            "scheduled_report": ["scheduled", "daily report", "weekly report", "digest"],
            "drill_down":       ["drill", "interactive", "click", "explore"],
        },
    }

    for q_key, patterns in keyword_patterns.items():
        if q_key in already_resolved:
            continue
        best_opt, best_n = None, 0
        for opt_id, keywords in patterns.items():
            n = sum(1 for kw in keywords if kw in q)
            if n > best_n:
                best_n, best_opt = n, opt_id
        if best_opt and best_n > 0:
            resolved[q_key] = (best_opt, min(0.7, 0.5 + best_n * 0.1))

    return resolved


# ============================================================================
# Context-signal resolution  (priority 3)
# ============================================================================

def _resolve_from_context(
    state: Dict[str, Any],
    already_resolved: Dict[str, Tuple[str, float]],
) -> Dict[str, Tuple[str, float]]:
    """
    Infer decisions from presence of controls, framework_id, and data_sources.
    Lowest priority — only fills gaps after state + keyword passes.
    """
    resolved: Dict[str, Tuple[str, float]] = {}
    framework_id = (state.get("framework_id") or "").lower()

    # category from control taxonomy
    if "category" not in already_resolved and framework_id:
        if framework_id in ("soc2", "hipaa", "nist_ai_rmf"):
            resolved["category"] = ("compliance_audit", 0.65)

    # focus_area from control codes in state
    if "focus_area" not in already_resolved:
        controls = state.get("controls", [])
        domain_counts: Dict[str, int] = {}
        for ctrl in controls:
            code = (ctrl.get("code") or ctrl.get("control_code") or "").upper()
            if code.startswith("CC6"):
                domain_counts["access_control"] = domain_counts.get("access_control", 0) + 1
            elif code.startswith("CC7"):
                domain_counts["vulnerability_management"] = domain_counts.get("vulnerability_management", 0) + 1
            elif code.startswith("CC8"):
                domain_counts["change_management"] = domain_counts.get("change_management", 0) + 1
            elif "164.308(a)(5)" in code:
                domain_counts["training_completion"] = domain_counts.get("training_completion", 0) + 1
        if domain_counts:
            top = max(domain_counts, key=domain_counts.get)
            if top in VALID_OPTIONS["focus_area"]:
                resolved["focus_area"] = (top, 0.6)

    return resolved


# ============================================================================
# Public API
# ============================================================================

def resolve_decisions(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point: resolve all seven dashboard decision tree questions.

    Order of resolution:
      Phase 0 — metric_profile (deterministic, from metrics list)
      Phase 1 — LLM or keyword fallback (destination_type resolved FIRST)
      Phase 2 — keyword hints for remaining gaps
      Phase 3 — context signals for remaining gaps
      Phase 4 — defaults for anything still unresolved

    Returns a dict with:
        - For each question key: the resolved option_id
        - "registry_target"          : "dashboard_registry" | "ld_templates_registry" | "both"
        - "destination_gate"         : dict of allowed/excluded primitives
        - "auto_resolve_confidence"  : mean confidence across required questions
        - "resolved_from"            : list of signal sources used
        - "unresolved"               : list of question keys that fell back to defaults
        - "all_tags"                 : merged tag bundle from all resolved options
    """
    user_query = state.get("user_query", "")

    # Phase 0: metric_profile — always deterministic
    metrics = state.get("resolved_metrics", []) or state.get("metrics", [])
    metric_profile_id, mp_conf = compute_metric_profile(metrics)

    # Phase 1: LLM (or keyword fallback)
    state_resolved = _resolve_from_state(state, preresolved_metric_profile=metric_profile_id)

    # Phase 2: Keyword hints
    keyword_resolved = _resolve_from_keywords(user_query, state_resolved)

    # Phase 3: Context signals
    combined = {**state_resolved, **keyword_resolved}
    context_resolved = _resolve_from_context(state, combined)

    # Merge (earlier phases win)
    all_resolved = {**context_resolved, **keyword_resolved, **state_resolved}

    # Strip internal tag key before iterating questions
    llm_tags = None
    if "_llm_tags" in all_resolved:
        llm_tags = all_resolved.pop("_llm_tags")

    # Phase 4: Build final decisions
    decisions: Dict[str, str] = {}
    confidences: Dict[str, float] = {}
    unresolved: List[str] = []
    resolved_from: List[str] = []

    # Always inject deterministic metric_profile
    decisions["metric_profile"]    = metric_profile_id
    confidences["metric_profile"]  = mp_conf
    resolved_from.append("deterministic:metric_profile")

    for q in DECISION_QUESTIONS:
        if q.key == "metric_profile":
            continue  # already set above

        if q.key in all_resolved:
            opt_id, conf = all_resolved[q.key]
            decisions[q.key]    = opt_id
            confidences[q.key]  = conf
            if q.key in state_resolved:
                resolved_from.append(f"state:{q.key}")
            elif q.key in keyword_resolved:
                resolved_from.append(f"keyword:{q.key}")
            else:
                resolved_from.append(f"context:{q.key}")
        else:
            # Apply destination-aware defaults
            dest = decisions.get("destination_type", "embedded")
            dest_defaults = _DESTINATION_DEFAULTS.get(dest, {})

            default_val = dest_defaults.get(q.key) or q.default or ""
            decisions[q.key]   = default_val
            confidences[q.key] = 0.3
            unresolved.append(q.key)

    # Derive registry_target and destination_gate from resolved values
    cat  = decisions.get("category", "security_operations")
    dest = decisions.get("destination_type", "embedded")
    decisions["registry_target"] = REGISTRY_TARGETS.get(cat, "dashboard_registry")
    decisions["destination_gate"] = DESTINATION_GATES.get(dest, {})

    # Merge tags
    all_tags: Dict[str, Any] = {}
    if llm_tags:
        all_tags = llm_tags
    else:
        for q_key, opt_id in decisions.items():
            if q_key in ("registry_target", "destination_gate"):
                continue
            option_tags = OPTION_TAGS.get(q_key, {}).get(opt_id, {})
            for tag_key, tag_val in option_tags.items():
                if tag_key in all_tags and isinstance(all_tags[tag_key], list) and isinstance(tag_val, list):
                    for v in tag_val:
                        if v not in all_tags[tag_key]:
                            all_tags[tag_key].append(v)
                else:
                    all_tags[tag_key] = tag_val

    required_confs = [
        confidences[q.key]
        for q in DECISION_QUESTIONS
        if q.required and q.key in confidences
    ]
    overall_confidence = (
        sum(required_confs) / len(required_confs) if required_confs else 0.0
    )

    return {
        **decisions,
        "auto_resolve_confidence": round(overall_confidence, 3),
        "confidences":   confidences,
        "resolved_from": resolved_from,
        "unresolved":    unresolved,
        "all_tags":      all_tags,
    }


def get_clarification_questions(decisions: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Return questions that should be asked interactively when confidence < 0.6.
    Returns list of {key, question, options: [{id, label}], current_value, current_confidence}.
    """
    option_labels: Dict[str, Dict[str, str]] = {
        "destination_type": {
            "embedded":     "Embedded (ECharts / React)",
            "powerbi":      "Power BI",
            "simple":       "Simple / Static HTML",
            "slack_digest": "Slack / Email Digest",
            "api_json":     "API / JSON Export",
        },
        "category": {
            "compliance_audit":     "Compliance & Audit",
            "security_operations":  "Security Operations",
            "learning_development": "Learning & Development",
            "hr_workforce":         "HR & Workforce",
            "risk_management":      "Risk Management",
            "executive_reporting":  "Executive / Board",
            "data_operations":      "Data Operations",
            "cross_domain":         "Cross-Domain",
        },
        "focus_area": {
            "vulnerability_management": "Vulnerability Management",
            "incident_response":        "Incident Response",
            "threat_detection":         "Threat Detection",
            "asset_inventory":          "Asset Inventory",
            "access_control":           "Access Control",
            "audit_logging":            "Audit Logging",
            "change_management":        "Change Management",
            "data_protection":          "Data Protection",
            "training_completion":      "Training Completion",
            "learner_engagement":       "Learner Engagement",
            "content_effectiveness":    "Content Effectiveness",
            "compliance_posture":       "Compliance Posture",
            "pipeline_health":          "Pipeline Health",
            "data_quality":             "Data Quality",
            "vendor_risk":              "Vendor Risk",
            "risk_exposure":            "Risk Exposure",
        },
        "audience": {
            "security_ops":    "Security Operations Team",
            "soc_analyst":     "SOC Analyst",
            "compliance_team": "Compliance / GRC Team",
            "executive_board": "Executive / Board",
            "risk_management": "Risk Management",
            "learning_admin":  "L&D Administrator",
            "data_engineer":   "Data / Ops Engineer",
        },
        "complexity": {
            "low":    "Summary / Overview",
            "medium": "Standard",
            "high":   "Full Detail",
        },
        "interaction_mode": {
            "drill_down":       "Interactive Drill-Down",
            "read_only":        "Read-Only View",
            "real_time":        "Real-Time / Live",
            "scheduled_report": "Scheduled Report",
        },
    }

    clarifications = []
    confidences = decisions.get("confidences", {})
    unresolved   = decisions.get("unresolved", [])

    for q in DECISION_QUESTIONS:
        conf = confidences.get(q.key, 0.0)
        if conf < 0.6 or q.key in unresolved:
            labels = option_labels.get(q.key, {})
            clarifications.append({
                "key":               q.key,
                "question":          q.question,
                "options":           [
                    {"id": opt_id, "label": labels.get(opt_id, opt_id)}
                    for opt_id in VALID_OPTIONS.get(q.key, [])
                ],
                "current_value":     decisions.get(q.key),
                "current_confidence": round(conf, 2),
            })

    return clarifications

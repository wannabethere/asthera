"""
Metric Decision Tree — Structure & Auto-Resolution

Defines the decision tree questions, option→attribute mappings, keyword-based
auto-resolve hints, and state-field resolution logic.

Pattern mirrors registry_unified.py's decision tree but scoped to metric/KPI
selection for SOC2 compliance audits and LMS learning targets.
"""
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
# Data structures
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
# Minimal decision tree structure (for validation and clarification only)
# 
# NOTE: The full decision tree structure with all options, tags, and keywords
# is now in the LLM prompt (17_resolve_decisions.md). This minimal structure
# is only used for:
# - Validation of LLM responses
# - Building clarification questions
# - Tag merging after resolution
# ============================================================================

# Minimal question definitions (just keys, defaults, and required flags)
DECISION_QUESTIONS: List[DecisionQuestion] = [
    DecisionQuestion(key="use_case", question="What is the compliance use case?", required=True, default="soc2_audit", options=[]),
    DecisionQuestion(key="goal", question="What is the primary measurement goal?", required=True, default="compliance_posture", options=[]),
    DecisionQuestion(key="focus_area", question="Which compliance domain is the priority?", required=True, default="vulnerability_management", options=[]),
    DecisionQuestion(key="audience", question="Who will consume these metrics?", required=False, default="compliance_team", options=[]),
    DecisionQuestion(key="timeframe", question="What time granularity is needed?", required=False, default="monthly", options=[]),
    DecisionQuestion(key="metric_type", question="What type of insights are needed?", required=False, default="percentages", options=[]),
]

# Build lookup for fast access
QUESTION_MAP: Dict[str, DecisionQuestion] = {q.key: q for q in DECISION_QUESTIONS}

# Valid option IDs for validation (extracted from prompt, kept here for quick validation)
VALID_OPTIONS: Dict[str, List[str]] = {
    "use_case": ["soc2_audit", "lms_learning_target", "risk_posture_report", "executive_dashboard", "operational_monitoring"],
    "goal": ["compliance_posture", "incident_triage", "control_effectiveness", "risk_exposure", "training_completion", "remediation_velocity"],
    "focus_area": ["access_control", "audit_logging", "vulnerability_management", "incident_response", "change_management", "data_protection", "training_compliance"],
    "audience": ["security_ops", "compliance_team", "executive_board", "risk_management", "learning_admin", "auditor"],
    "timeframe": ["realtime", "hourly", "daily", "weekly", "monthly", "quarterly"],
    "metric_type": ["counts", "rates", "percentages", "scores", "distributions", "comparisons", "trends"],
}

# Tag mappings (for merging tags after LLM resolution)
# These are loaded from the LLM response's all_tags, but kept here as fallback
OPTION_TAGS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "use_case": {
        "soc2_audit": {
            "goal_filter": ["compliance_posture", "control_effectiveness", "risk_exposure"],
            "audience": ["compliance_team", "auditor", "executive_board"],
            "required_groups": ["compliance_posture", "control_effectiveness", "risk_exposure"],
        },
        "lms_learning_target": {
            "goal_filter": ["training_completion", "compliance_posture"],
            "required_groups": ["training_completion", "compliance_posture"],
        },
        "risk_posture_report": {
            "goal_filter": ["risk_exposure", "compliance_posture"],
            "required_groups": ["risk_exposure", "compliance_posture"],
        },
        "executive_dashboard": {
            "goal_filter": ["compliance_posture", "risk_exposure"],
            "required_groups": ["compliance_posture", "risk_exposure"],
        },
        "operational_monitoring": {
            "goal_filter": ["incident_triage", "control_effectiveness", "remediation_velocity"],
            "required_groups": ["operational_security", "remediation_velocity"],
        },
    },
    "goal": {
        "compliance_posture": {"metric_categories": ["compliance_events", "audit_logging", "access_control"], "kpi_types": ["percentage", "score"]},
        "incident_triage": {"metric_categories": ["incidents", "mttr", "alert_volume", "siem_events"], "kpi_types": ["count", "rate"]},
        "control_effectiveness": {"metric_categories": ["detection_engineering", "access_control", "authentication"], "kpi_types": ["percentage", "rate"]},
        "risk_exposure": {"metric_categories": ["vulnerabilities", "cve_exposure", "misconfigs"], "kpi_types": ["score", "count"]},
        "training_completion": {"metric_categories": ["training_compliance", "certification"], "kpi_types": ["percentage", "count"]},
        "remediation_velocity": {"metric_categories": ["patch_compliance", "mttr", "vulnerabilities"], "kpi_types": ["rate", "trend"]},
    },
    "focus_area": {
        "access_control": {"control_domains": ["CC6", "164.312(a)"], "risk_categories": ["unauthorized_access", "privilege_escalation"]},
        "audit_logging": {"control_domains": ["CC7", "164.312(b)"], "risk_categories": ["undetected_breach", "log_tampering"]},
        "vulnerability_management": {"control_domains": ["CC7", "CC8"], "risk_categories": ["unpatched_systems", "cve_exposure"]},
        "incident_response": {"control_domains": ["CC7"], "risk_categories": ["delayed_response", "uncontained_breach"]},
        "change_management": {"control_domains": ["CC8"], "risk_categories": ["unauthorized_changes", "configuration_drift"]},
        "data_protection": {"control_domains": ["CC6", "CC9"], "risk_categories": ["data_leak", "classification_gap"]},
        "training_compliance": {"control_domains": ["CC1", "CC2"], "risk_categories": ["untrained_staff", "compliance_gap"]},
    },
}


# ============================================================================
# State-field resolution (priority 1: explicit state signals)
# ============================================================================

# ============================================================================
# Fallback resolution (used only if LLM call fails)
# ============================================================================

def _resolve_from_state_fallback(state: Dict[str, Any]) -> Dict[str, Tuple[str, float]]:
    """
    Fallback resolution using simple keyword matching.
    Only used if LLM-based resolution fails.
    """
    resolved: Dict[str, Tuple[str, float]] = {}
    user_query = state.get("user_query", "").lower()
    intent = state.get("intent", "").lower()
    framework_id = (state.get("framework_id") or "").lower()
    data_enrichment = state.get("data_enrichment", {})
    metrics_intent = data_enrichment.get("metrics_intent", "").lower()
    focus_areas = data_enrichment.get("suggested_focus_areas", [])

    # ── use_case from intent + framework ──
    if framework_id in ("soc2", "soc_2", "soc 2"):
        resolved["use_case"] = ("soc2_audit", 0.9)
    elif "dashboard" in intent:
        if "executive" in intent or "board" in user_query:
            resolved["use_case"] = ("executive_dashboard", 0.8)
        else:
            resolved["use_case"] = ("operational_monitoring", 0.7)

    # ── goal from metrics_intent ──
    if metrics_intent:
        # Simple keyword matching
        if "risk" in metrics_intent:
            resolved["goal"] = ("risk_exposure", 0.7)
        elif "incident" in metrics_intent:
            resolved["goal"] = ("incident_triage", 0.7)
        elif "control" in metrics_intent:
            resolved["goal"] = ("control_effectiveness", 0.7)
        elif "training" in metrics_intent:
            resolved["goal"] = ("training_completion", 0.7)
        elif "remediation" in metrics_intent:
            resolved["goal"] = ("remediation_velocity", 0.7)
        else:
            resolved["goal"] = ("compliance_posture", 0.6)

    # ── focus_area from suggested_focus_areas ──
    if focus_areas:
        focus_area_value = focus_areas[0].lower()
        valid_focus_areas = VALID_OPTIONS.get("focus_area", [])
        # Check if it's already a valid option_id
        if focus_area_value in valid_focus_areas:
            resolved["focus_area"] = (focus_area_value, 0.9)
        else:
            # Simple alias mapping
            alias_map = {
                "identity_access_management": "access_control",
                "authentication_mfa": "access_control",
                "log_management_siem": "audit_logging",
                "incident_detection": "incident_response",
                "cloud_security_posture": "vulnerability_management",
                "patch_management": "vulnerability_management",
                "endpoint_detection": "incident_response",
                "network_detection": "incident_response",
                "data_classification": "data_protection",
                "audit_logging_compliance": "audit_logging",
            }
            mapped = alias_map.get(focus_area_value, focus_area_value)
            if mapped in valid_focus_areas:
                resolved["focus_area"] = (mapped, 0.75)

    # ── audience from intent ──
    if "executive" in intent or "board" in user_query:
        resolved["audience"] = ("executive_board", 0.8)
    elif "audit" in intent or "audit" in user_query:
        resolved["audience"] = ("auditor", 0.8)

    return resolved


def _resolve_from_state(state: Dict[str, Any]) -> Dict[str, Tuple[str, float]]:
    """
    Extract decision values from explicit state fields using LLM-based resolution.
    
    Uses an LLM prompt that includes all decision tree structure and examples.
    Falls back to simple keyword matching if LLM call fails.

    Returns dict of {question_key: (option_id, confidence)} for questions
    that can be resolved from state.
    """
    try:
        # Try LLM-based resolution first
        from app.agents.prompt_loader import load_prompt
        from app.core.dependencies import get_llm
        from langchain_core.prompts import ChatPromptTemplate
        import json
        from pathlib import Path
        
        # Resolve prompts directory relative to this file's location
        prompts_dir = Path(__file__).parent / "prompts"
        prompt_template = load_prompt("17_resolve_decisions", 
                                     prompts_dir=str(prompts_dir))
        
        # Prepare input for LLM
        input_data = {
            "user_query": state.get("user_query", ""),
            "intent": state.get("intent", ""),
            "framework_id": state.get("framework_id"),
            "data_enrichment": state.get("data_enrichment", {}),
        }
        
        human_message = json.dumps(input_data, indent=2)
        
        llm = get_llm(temperature=0)
        system_prompt = prompt_template.replace("{", "{{").replace("}", "}}")
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
        ])
        chain = prompt | llm
        response = chain.invoke({"input": human_message})
        response_content = response.content if hasattr(response, "content") else str(response)
        
        # Parse JSON response
        if "```json" in response_content:
            start = response_content.find("```json") + 7
            end = response_content.find("```", start)
            if end > start:
                response_content = response_content[start:end].strip()
        elif "```" in response_content:
            start = response_content.find("```") + 3
            end = response_content.find("```", start)
            if end > start:
                response_content = response_content[start:end].strip()
        
        result = json.loads(response_content)
        resolved_decisions = result.get("resolved_decisions", {})
        
        # Convert LLM output format to expected format
        resolved: Dict[str, Tuple[str, float]] = {}
        llm_tags = {}  # Extract tags if LLM provided them
        
        for question_key, decision_info in resolved_decisions.items():
            if isinstance(decision_info, dict):
                option_id = decision_info.get("option_id")
                confidence = decision_info.get("confidence", 0.5)
                if option_id:
                    # Validate option_id
                    valid_opts = VALID_OPTIONS.get(question_key, [])
                    if option_id in valid_opts:
                        resolved[question_key] = (option_id, float(confidence))
                    else:
                        logger.warning(f"_resolve_from_state: Invalid option_id '{option_id}' for '{question_key}', skipping")
        
        # Store tags from LLM response if available (for later merging)
        if "all_tags" in result:
            llm_tags = result["all_tags"]
            resolved["_llm_tags"] = llm_tags
        
        logger.info(
            f"_resolve_from_state: LLM resolved {len(resolved)} decisions "
            f"(confidence: {result.get('overall_confidence', 0):.2f})"
        )
        
        return resolved
        
    except Exception as e:
        logger.warning(f"_resolve_from_state: LLM resolution failed: {e}, falling back to keyword matching", exc_info=True)
        # Fallback to simple keyword matching
        return _resolve_from_state_fallback(state)


# ============================================================================
# Keyword auto-resolve (priority 2: user query matching)
# ============================================================================

def _resolve_from_keywords(
    user_query: str,
    already_resolved: Dict[str, Tuple[str, float]],
) -> Dict[str, Tuple[str, float]]:
    """
    Score each unresolved question's options against user_query keywords.
    
    NOTE: This is a fallback for Phase 2 resolution. The primary resolution
    is now LLM-based (see _resolve_from_state). This function uses simple
    keyword matching as a fallback.

    Returns {question_key: (best_option_id, confidence)} for questions
    not already in already_resolved.
    """
    resolved: Dict[str, Tuple[str, float]] = {}
    query_lower = user_query.lower()

    # Simple keyword matching (fallback only)
    # Full keyword hints are in the LLM prompt
    keyword_patterns = {
        "use_case": {
            "soc2_audit": ["soc2", "soc 2", "audit", "type ii"],
            "executive_dashboard": ["executive", "board", "ciso"],
            "operational_monitoring": ["soc", "operations", "monitoring"],
        },
        "goal": {
            "risk_exposure": ["risk", "exposure", "vulnerability"],
            "incident_triage": ["triage", "incident", "mttr"],
            "control_effectiveness": ["control", "effectiveness"],
            "remediation_velocity": ["remediation", "velocity", "patch"],
        },
        "focus_area": {
            "vulnerability_management": ["vulnerability", "vuln", "cve", "patch"],
            "access_control": ["access", "authentication", "mfa", "sso"],
            "audit_logging": ["audit", "logging", "siem"],
            "incident_response": ["incident", "response"],
        },
        "audience": {
            "executive_board": ["executive", "board", "ciso"],
            "auditor": ["auditor", "audit"],
            "security_ops": ["soc", "operations"],
        },
    }

    for question_key, patterns in keyword_patterns.items():
        if question_key in already_resolved:
            continue

        best_option = None
        best_matches = 0

        for option_id, keywords in patterns.items():
            matches = sum(1 for kw in keywords if kw in query_lower)
            if matches > best_matches:
                best_matches = matches
                best_option = option_id

        if best_option and best_matches > 0:
            confidence = min(0.7, 0.5 + (best_matches * 0.1))
            resolved[question_key] = (best_option, confidence)

    return resolved


# ============================================================================
# Context-signal resolution (priority 3: scored_context inference)
# ============================================================================

def _resolve_from_context(
    state: Dict[str, Any],
    already_resolved: Dict[str, Tuple[str, float]],
) -> Dict[str, Tuple[str, float]]:
    """
    Infer decisions from the presence of controls, risks, schemas in state.
    Lowest priority — only fills gaps not covered by state fields or keywords.
    """
    resolved: Dict[str, Tuple[str, float]] = {}
    scored_context = state.get("dt_scored_context", {})

    # Infer focus_area from control domains
    if "focus_area" not in already_resolved:
        controls = scored_context.get("controls", []) or state.get("controls", [])
        domain_counts: Dict[str, int] = {}
        for ctrl in controls:
            code = (ctrl.get("code") or ctrl.get("control_code") or "").upper()
            if code.startswith("CC6"):
                domain_counts["access_control"] = domain_counts.get("access_control", 0) + 1
            elif code.startswith("CC7"):
                domain_counts["vulnerability_management"] = domain_counts.get("vulnerability_management", 0) + 1
            elif code.startswith("CC8"):
                domain_counts["change_management"] = domain_counts.get("change_management", 0) + 1

        if domain_counts:
            top_domain = max(domain_counts, key=domain_counts.get)
            if top_domain in VALID_OPTIONS.get("focus_area", []):
                resolved["focus_area"] = (top_domain, 0.6)

    # Infer goal from risk categories
    if "goal" not in already_resolved:
        risks = scored_context.get("risks", []) or state.get("risks", [])
        if len(risks) > 3:
            resolved["goal"] = ("risk_exposure", 0.5)

    return resolved


# ============================================================================
# Public API
# ============================================================================

def resolve_decisions(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point: resolve all decision tree questions from state + query.

    Returns a dict with:
        - For each question key: the resolved option_id
        - "auto_resolve_confidence": overall confidence (min across questions)
        - "resolved_from": list of signal sources used
        - "unresolved": list of question keys that fell back to defaults
        - "all_tags": merged tag bundle from all resolved options
    """
    user_query = state.get("user_query", "")

    # Phase 1: State fields (highest confidence)
    state_resolved = _resolve_from_state(state)

    # Phase 2: Keyword hints
    keyword_resolved = _resolve_from_keywords(user_query, state_resolved)

    # Phase 3: Context signals
    combined = {**state_resolved, **keyword_resolved}
    context_resolved = _resolve_from_context(state, combined)

    # Merge all (earlier phases take priority)
    all_resolved = {**context_resolved, **keyword_resolved, **state_resolved}

    # Build final decisions with defaults for unresolved questions
    decisions: Dict[str, str] = {}
    confidences: Dict[str, float] = {}
    unresolved: List[str] = []
    resolved_from: List[str] = []

    for q in DECISION_QUESTIONS:
        if q.key in all_resolved:
            option_id, conf = all_resolved[q.key]
            decisions[q.key] = option_id
            confidences[q.key] = conf
            if q.key in state_resolved:
                resolved_from.append(f"state:{q.key}")
            elif q.key in keyword_resolved:
                resolved_from.append(f"keyword:{q.key}")
            else:
                resolved_from.append(f"context:{q.key}")
        elif q.default:
            decisions[q.key] = q.default
            confidences[q.key] = 0.3  # low confidence for defaults
            unresolved.append(q.key)
        else:
            decisions[q.key] = q.options[0].option_id if q.options else ""
            confidences[q.key] = 0.1
            unresolved.append(q.key)

    # Merge all tags from resolved options
    # Tags come from LLM response if available, otherwise use OPTION_TAGS fallback
    all_tags: Dict[str, Any] = {}
    
    # Check if LLM provided tags (stored in state_resolved as special key)
    llm_tags = None
    if isinstance(state_resolved, dict) and "_llm_tags" in state_resolved:
        llm_tags = state_resolved.pop("_llm_tags")  # Remove special key after extracting
    
    if llm_tags:
        all_tags = llm_tags
    else:
        # Fallback: use OPTION_TAGS
        for q_key, option_id in decisions.items():
            option_tags = OPTION_TAGS.get(q_key, {}).get(option_id, {})
            if option_tags:
                for tag_key, tag_val in option_tags.items():
                    if tag_key in all_tags and isinstance(all_tags[tag_key], list) and isinstance(tag_val, list):
                        # Merge lists, deduplicate
                        for v in tag_val:
                            if v not in all_tags[tag_key]:
                                all_tags[tag_key].append(v)
                    else:
                        all_tags[tag_key] = tag_val

    overall_confidence = min(confidences.values()) if confidences else 0.0
    # Weight: required questions matter more
    required_confs = [confidences[q.key] for q in DECISION_QUESTIONS if q.required and q.key in confidences]
    if required_confs:
        overall_confidence = sum(required_confs) / len(required_confs)

    return {
        **decisions,
        "auto_resolve_confidence": round(overall_confidence, 3),
        "confidences": confidences,
        "resolved_from": resolved_from,
        "unresolved": unresolved,
        "all_tags": all_tags,
    }


def get_clarification_questions(decisions: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Return questions that should be asked interactively because
    auto-resolve confidence was too low.

    Returns list of {key, question, options: [{id, label}], current_value}
    
    NOTE: Full option details (labels, descriptions) are in the LLM prompt.
    This function returns minimal structure for clarification.
    """
    clarifications = []
    confidences = decisions.get("confidences", {})
    unresolved = decisions.get("unresolved", [])

    # Option labels for clarification (minimal set)
    option_labels = {
        "use_case": {
            "soc2_audit": "SOC2 Compliance Audit",
            "lms_learning_target": "LMS Learning Target",
            "risk_posture_report": "Risk Posture Report",
            "executive_dashboard": "Executive Dashboard",
            "operational_monitoring": "Operational Security Monitoring",
        },
        "goal": {
            "compliance_posture": "Monitor Compliance Posture",
            "incident_triage": "Triage Security Incidents",
            "control_effectiveness": "Track Control Effectiveness",
            "risk_exposure": "Measure Risk Exposure",
            "training_completion": "Training Completion",
            "remediation_velocity": "Remediation Velocity",
        },
        "focus_area": {
            "access_control": "Access Control",
            "audit_logging": "Audit Logging & Monitoring",
            "vulnerability_management": "Vulnerability Management",
            "incident_response": "Incident Response",
            "change_management": "Change Management",
            "data_protection": "Data Protection & Classification",
            "training_compliance": "Training & Awareness",
        },
        "audience": {
            "security_ops": "Security Operations",
            "compliance_team": "Compliance Team",
            "executive_board": "Executive / Board",
            "risk_management": "Risk Management",
            "learning_admin": "Learning Administrator",
            "auditor": "External Auditor",
        },
        "timeframe": {
            "realtime": "Real-time",
            "hourly": "Hourly",
            "daily": "Daily",
            "weekly": "Weekly",
            "monthly": "Monthly",
            "quarterly": "Quarterly",
        },
        "metric_type": {
            "counts": "Counts / Totals",
            "rates": "Rates / Velocity",
            "percentages": "Percentages / Scores",
            "scores": "Composite Scores",
            "distributions": "Distributions",
            "comparisons": "Comparisons / Benchmarks",
            "trends": "Trend Analysis",
        },
    }

    for q in DECISION_QUESTIONS:
        conf = confidences.get(q.key, 0.0)
        if conf < 0.6 or q.key in unresolved:
            valid_options = VALID_OPTIONS.get(q.key, [])
            labels = option_labels.get(q.key, {})
            clarifications.append({
                "key": q.key,
                "question": q.question,
                "options": [
                    {"id": opt_id, "label": labels.get(opt_id, opt_id)}
                    for opt_id in valid_options
                ],
                "current_value": decisions.get(q.key),
                "current_confidence": round(conf, 2),
            })

    return clarifications

"""
Dashboard Decision Tree — Taxonomy Loader

Loads dashboard_domain_taxonomy.json and provides:
  - OPTION_TAGS for category, focus_area, audience (mirrors metric_decision_tree pattern)
  - Taxonomy-aware focus_area and audience mappings for scoring
  - Fuzzy match aliases (taxonomy focus_areas → canonical focus_area)

Mirrors how dt_metric_decision_nodes uses taxonomy:
  - metric_decision_tree: OPTION_TAGS with control_domains, risk_categories per focus_area
  - metric_scoring: scores against mapped_control_domains, mapped_risk_categories
  - dt_generated_taxonomy: LLM-generated taxonomy merged into scored_context

For dashboard: taxonomy provides goals, focus_areas, use_cases, audience_levels per domain.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Taxonomy domain → VALID_OPTIONS category mapping
TAXONOMY_DOMAIN_TO_CATEGORY: Dict[str, str] = {
    "ld_training": "learning_development",
    "ld_operations": "learning_development",
    "ld_engagement": "learning_development",
    "lms_training": "learning_development",
    "hr_workforce": "hr_workforce",
    "security_operations": "security_operations",
    "compliance_posture": "compliance_audit",
    "hybrid_compliance": "cross_domain",
    "iam_access_certification": "compliance_audit",
    "data_migration": "data_operations",
    "executive_reporting": "executive_reporting",
}

# Canonical focus_area → taxonomy focus_areas (for fuzzy matching in scoring)
FOCUS_AREA_TAXONOMY_ALIASES: Dict[str, List[str]] = {
    "vulnerability_management": [
        "patch_and_vulnerability_sla_tracking",
        "CVE/KEV correlation and blast radius",
    ],
    "incident_response": [
        "incident_alert_lists_and_triage",
        "investigation_detail_and timelines",
    ],
    "access_control": [
        "access_review_campaigns",
        "privilege_creep_and_role_analysis",
        "orphaned_and_inactive_accounts",
        "termination_to_access_workflow",
    ],
    "training_completion": [
        "assignment_status_and_completion",
        "individual_learner_profiles",
        "team_level_compliance",
        "training_plan_metrics",
    ],
    "learner_engagement": [
        "login_volume_and_uniques",
        "temporal_engagement_trends (daily/week/month)",
        "job-role and org adoption",
        "recent_activity_audit_trail",
    ],
    "compliance_posture": [
        "control_level_status_and_evidence",
        "audit_readiness (SOC2, HIPAA, etc.)",
        "remediation_pipeline",
        "cross-functional_control_dependencies",
    ],
}

# Canonical audience → taxonomy audience_levels (for fuzzy matching)
AUDIENCE_TAXONOMY_ALIASES: Dict[str, List[str]] = {
    "security_ops": ["security_ops_analyst", "incident_response_lead", "vulnerability_manager", "soc_manager"],
    "soc_analyst": ["security_ops_analyst", "incident_response_lead"],
    "compliance_team": ["compliance_lead", "internal_auditor", "g_r_c_manager", "security_lead"],
    "executive_board": ["c_level_executive", "board_member", "vp_of_l&d", "chief_compliance_officer"],
    "learning_admin": ["learning_admin", "training_coordinator", "lms_admin", "learning_operations"],
}


def _get_taxonomy_path() -> Path:
    try:
        from app.config.dashboard_paths import get_dashboard_domain_taxonomy_enriched_path
        path = get_dashboard_domain_taxonomy_enriched_path()
    except Exception:
        try:
            from app.config.dashboard_paths import get_dashboard_domain_taxonomy_path
            path = get_dashboard_domain_taxonomy_path()
        except Exception:
            path = Path(__file__).resolve().parent.parent.parent.parent / "config" / "dashboard" / "dashboard_domain_taxonomy.json"
    return path


def load_dashboard_taxonomy() -> Dict[str, Any]:
    """Load dashboard_domain_taxonomy.json. Returns empty dict on failure."""
    path = _get_taxonomy_path()
    if not path.exists():
        logger.warning(f"dashboard_taxonomy: taxonomy file not found: {path}")
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("domains", data)
    except Exception as exc:
        logger.warning(f"dashboard_taxonomy: failed to load {path}: {exc}")
        return {}


def build_category_opt_tags_from_taxonomy(
    taxonomy: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """
    Build OPTION_TAGS for category from taxonomy.
    Each taxonomy domain maps to a category; merge focus_areas, goals, audience_levels.
    """
    tags: Dict[str, Dict[str, Any]] = {}
    for domain_id, domain in taxonomy.items():
        cat = TAXONOMY_DOMAIN_TO_CATEGORY.get(domain_id)
        if not cat:
            continue
        if cat not in tags:
            tags[cat] = {
                "focus_areas_default": [],
                "goals": [],
                "use_cases": [],
                "audience_levels": [],
                "theme": domain.get("theme_preference", "light"),
                "complexity_default": domain.get("complexity", "medium"),
            }
        t = tags[cat]
        t["focus_areas_default"] = list(set(
            (t.get("focus_areas_default") or []) + (domain.get("focus_areas") or [])
        ))
        t["goals"] = list(set((t.get("goals") or []) + (domain.get("goals") or [])))
        t["use_cases"] = list(set((t.get("use_cases") or []) + (domain.get("use_cases") or [])))
        t["audience_levels"] = list(set(
            (t.get("audience_levels") or []) + (domain.get("audience_levels") or [])
        ))
    return tags


def build_focus_area_aliases_from_taxonomy(
    taxonomy: Dict[str, Any],
) -> Dict[str, List[str]]:
    """
    Build focus_area → taxonomy focus_areas for fuzzy matching.
    Merges FOCUS_AREA_TAXONOMY_ALIASES with taxonomy-derived mappings.
    """
    aliases = dict(FOCUS_AREA_TAXONOMY_ALIASES)
    for domain in taxonomy.values():
        fas = domain.get("focus_areas") or []
        for fa in fas:
            # Normalize: use first word or key part as canonical hint
            key = fa.lower().replace(" ", "_").replace("-", "_").split("(")[0].strip("_")
            if key and key not in aliases:
                # Map taxonomy focus_area to itself for exact match
                aliases.setdefault(key, []).append(fa)
    return aliases


def get_focus_areas_for_scoring(decision_focus_area: str) -> Set[str]:
    """
    Return all focus_area strings that should match the given decision.
    Includes the decision value and taxonomy aliases.
    """
    result: Set[str] = {decision_focus_area}
    aliases = FOCUS_AREA_TAXONOMY_ALIASES.get(decision_focus_area, [])
    result.update(aliases)
    return result


def get_audiences_for_scoring(decision_audience: str) -> Set[str]:
    """
    Return all audience strings that should match the given decision.
    Includes the decision value and taxonomy aliases.
    """
    result: Set[str] = {decision_audience}
    aliases = AUDIENCE_TAXONOMY_ALIASES.get(decision_audience, [])
    result.update(aliases)
    return result


def get_merged_opt_tags(
    base_opt_tags: Dict[str, Dict[str, Dict[str, Any]]],
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """
    Merge taxonomy-derived OPTION_TAGS with base (hardcoded) OPTION_TAGS.
    Taxonomy augments category tags with goals, use_cases, audience_levels.
    """
    taxonomy = load_dashboard_taxonomy()
    if not taxonomy:
        return base_opt_tags

    tax_category_tags = build_category_opt_tags_from_taxonomy(taxonomy)
    merged = dict(base_opt_tags)

    if "category" not in merged:
        merged["category"] = {}
    for cat, tax_tags in tax_category_tags.items():
        existing = merged["category"].get(cat, {})
        # Merge: taxonomy adds goals, use_cases, audience_levels; preserve focus_areas_default if not in taxonomy
        merged["category"][cat] = {
            **existing,
            "goals": tax_tags.get("goals") or existing.get("goals", []),
            "use_cases": tax_tags.get("use_cases") or existing.get("use_cases", []),
            "audience_levels": tax_tags.get("audience_levels") or existing.get("audience_levels", []),
            "focus_areas_taxonomy": tax_tags.get("focus_areas_default", []),
        }
        if tax_tags.get("focus_areas_default") and not existing.get("focus_areas_default"):
            merged["category"][cat]["focus_areas_default"] = tax_tags["focus_areas_default"]

    return merged

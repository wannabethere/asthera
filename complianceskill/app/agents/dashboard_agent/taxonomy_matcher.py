"""
Dashboard Taxonomy Matcher
==========================
Matches metrics, KPIs, and use cases to dashboard domains using the enriched taxonomy.
Uses keyword lookup to narrow candidate domains before scoring, reducing taxonomy size
for prompt inclusion and faster matching.
"""

from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Set

# Load taxonomy - try app/config/dashboard first, then legacy locations
try:
    from app.config.dashboard_paths import (
        get_dashboard_domain_taxonomy_enriched_path,
        get_dashboard_domain_taxonomy_path,
        get_taxonomy_keyword_index_path,
    )
    _TAXONOMY_PATHS = [
        get_dashboard_domain_taxonomy_enriched_path(),
        get_dashboard_domain_taxonomy_path(),
    ]
except ImportError:
    _TAXONOMY_PATHS = [
        Path(__file__).parent.parent / "decision_trees" / "dashboard_domain_taxonomy_enriched.json",
        Path(__file__).parent.parent / "decision_trees" / "dashboard_domain_taxonomy.json",
    ]
    get_taxonomy_keyword_index_path = lambda: Path(__file__).parent.parent / "decision_trees" / "taxonomy_keyword_index.json"

_TAXONOMY_CACHE: Optional[Dict[str, Any]] = None
_KEYWORD_INDEX_CACHE: Optional[Dict[str, List[str]]] = None

# Minimum token length for keyword index (skip "ld", "hr", etc.)
_MIN_KEYWORD_LEN = 3


def _extract_keywords_from_text(text: str) -> List[str]:
    """Extract lowercase tokens from text (split on non-alphanumeric)."""
    if not text:
        return []
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if len(t) >= _MIN_KEYWORD_LEN]


def _build_keyword_index(domains: Dict[str, Any]) -> Dict[str, List[str]]:
    """Build keyword -> [domain_ids] index from taxonomy domains."""
    index: Dict[str, List[str]] = {}
    domain_keys = [k for k in domains.keys() if not k.startswith("_") and k != "meta"]

    for domain_id in domain_keys:
        d = domains.get(domain_id)
        if not isinstance(d, dict):
            continue
        # Collect all indexable text
        parts = []
        parts.append(d.get("display_name", ""))
        parts.append(d.get("domain", ""))
        parts.extend(d.get("goals", []))
        parts.extend(d.get("focus_areas", []))
        parts.extend(d.get("use_cases", []))
        text = " ".join(str(p) for p in parts).replace("_", " ")
        keywords = set(_extract_keywords_from_text(text))

        for kw in keywords:
            if kw not in index:
                index[kw] = []
            if domain_id not in index[kw]:
                index[kw].append(domain_id)

    return index


def _load_keyword_index() -> Dict[str, List[str]]:
    """Load keyword index from file or build from taxonomy."""
    global _KEYWORD_INDEX_CACHE
    if _KEYWORD_INDEX_CACHE is not None:
        return _KEYWORD_INDEX_CACHE

    path = get_taxonomy_keyword_index_path()
    if path.exists():
        try:
            with open(path, "r") as f:
                _KEYWORD_INDEX_CACHE = json.load(f)
                return _KEYWORD_INDEX_CACHE
        except (json.JSONDecodeError, OSError):
            pass

    taxonomy = load_taxonomy()
    # Prefer top-level domain entries (enriched); fallback to taxonomy["domains"]
    domains = taxonomy.get("domains", {})
    domain_dict = {k: v for k, v in taxonomy.items() if isinstance(v, dict) and not k.startswith("_") and k not in ("meta", "domains")}
    if not domain_dict and domains:
        domain_dict = {k: v for k, v in domains.items() if isinstance(v, dict)}
    _KEYWORD_INDEX_CACHE = _build_keyword_index(domain_dict)
    return _KEYWORD_INDEX_CACHE


def get_candidate_domains_from_keywords(keywords: List[str]) -> Set[str]:
    """
    Look up candidate domain IDs from keywords. Returns domains that match any keyword.
    Use this to narrow taxonomy before scoring or prompt inclusion.
    """
    index = _load_keyword_index()
    candidates: Set[str] = set()
    for kw in keywords:
        if kw in index:
            candidates.update(index[kw])
    return candidates


def load_taxonomy() -> Dict[str, Any]:
    """Load the enriched dashboard taxonomy."""
    global _TAXONOMY_CACHE
    if _TAXONOMY_CACHE is not None:
        return _TAXONOMY_CACHE
    
    # Try each path in order
    for taxonomy_path in _TAXONOMY_PATHS:
        if taxonomy_path.exists():
            try:
                with open(taxonomy_path, 'r') as f:
                    _TAXONOMY_CACHE = json.load(f)
                    return _TAXONOMY_CACHE
            except Exception as e:
                continue
    
    # Return empty dict if no taxonomy found
    return {}


def match_domain_from_metrics(
    metrics: List[Dict[str, Any]],
    kpis: List[Dict[str, Any]],
    use_case: Optional[str] = None,
    data_sources: Optional[List[str]] = None,
) -> List[Tuple[str, float, Dict[str, Any]]]:
    """
    Match metrics and KPIs to dashboard domains using taxonomy.
    Uses keyword lookup to narrow candidate domains before scoring (reduces taxonomy slice).
    
    Args:
        metrics: List of metric dicts with 'name', 'type', 'source_table', etc.
        kpis: List of KPI dicts with 'label', 'value_expr', etc.
        use_case: Optional use case string (e.g., "SOC2 monitoring", "training compliance")
        data_sources: Optional list of data sources (e.g., ["siem", "cornerstone"])
    
    Returns:
        List of (domain_id, confidence_score, match_reasons) tuples, sorted by confidence.
    """
    taxonomy = load_taxonomy()
    # Merge domains from taxonomy["domains"] and top-level domain keys (enriched)
    domains = dict(taxonomy.get("domains", {}))
    for k, v in taxonomy.items():
        if isinstance(v, dict) and not k.startswith("_") and k not in ("meta", "domains"):
            domains[k] = v
    
    if not domains:
        return []
    
    # Extract text from metrics and KPIs for matching
    metric_texts = []
    for m in metrics:
        name = m.get("name", "")
        metric_type = m.get("type", "")
        source = m.get("source_table", "")
        metric_texts.append(f"{name} {metric_type} {source}".lower())
    
    kpi_texts = []
    for k in kpis:
        label = k.get("label", "")
        kpi_texts.append(label.lower())
    
    all_text = " ".join(metric_texts + kpi_texts).lower()
    use_case_lower = (use_case or "").lower()
    
    # Keyword lookup: narrow to candidate domains (reduces taxonomy size for scoring)
    keywords = _extract_keywords_from_text(all_text + " " + use_case_lower)
    if data_sources:
        keywords.extend(ds.lower() for ds in data_sources if len(ds) >= _MIN_KEYWORD_LEN)
    candidates = get_candidate_domains_from_keywords(keywords)
    domains_to_score = {k: v for k, v in domains.items() if k in candidates} if candidates else domains
    
    # Score each domain (only candidates, or all if no keyword matches)
    domain_scores = []
    
    for domain_id, domain_data in domains_to_score.items():
        if not isinstance(domain_data, dict):
            continue
        score = 0.0
        reasons = []
        
        # Match against goals
        goals = domain_data.get("goals", [])
        for goal in goals:
            goal_lower = goal.lower()
            # Check if goal appears in metrics/KPIs
            if any(goal_lower in text for text in metric_texts + kpi_texts):
                score += 15.0
                reasons.append(f"goal_match: {goal}")
            # Check if goal appears in use case
            if use_case_lower and goal_lower in use_case_lower:
                score += 10.0
                reasons.append(f"use_case_goal_match: {goal}")
        
        # Match against focus areas
        focus_areas = domain_data.get("focus_areas", [])
        for focus in focus_areas:
            focus_lower = focus.lower()
            if any(focus_lower in text for text in metric_texts + kpi_texts):
                score += 12.0
                reasons.append(f"focus_match: {focus}")
            if use_case_lower and focus_lower in use_case_lower:
                score += 8.0
                reasons.append(f"use_case_focus_match: {focus}")
        
        # Match against use cases
        domain_use_cases = domain_data.get("use_cases", [])
        for uc in domain_use_cases:
            uc_lower = uc.lower()
            if use_case_lower and uc_lower in use_case_lower:
                score += 20.0
                reasons.append(f"use_case_match: {uc}")
        
        # Match data sources to domain
        if data_sources:
            # Map data sources to likely domains
            source_domain_map = {
                "cornerstone": ["ld_training", "ld_operations", "ld_engagement"],
                "lms": ["ld_training", "ld_operations", "ld_engagement"],
                "workday": ["hr_workforce", "hr_learning"],
                "siem": ["security_operations", "compliance"],
                "qualys": ["security_operations", "vulnerability_management"],
                "snyk": ["security_operations", "vulnerability_management"],
            }
            for source in data_sources:
                source_lower = source.lower()
                if domain_id in source_domain_map.get(source_lower, []):
                    score += 15.0
                    reasons.append(f"data_source_match: {source}")
        
        # Keyword matching in metric/KPI names
        domain_keywords = [
            domain_data.get("display_name", "").lower(),
            domain_id.replace("_", " "),
        ]
        domain_keywords.extend([g.lower() for g in goals[:3]])
        domain_keywords.extend([f.lower() for f in focus_areas[:3]])
        
        for keyword in domain_keywords:
            if keyword and len(keyword) > 3:
                if any(keyword in text for text in metric_texts + kpi_texts):
                    score += 5.0
                    reasons.append(f"keyword_match: {keyword}")
        
        if score > 0:
            domain_scores.append((domain_id, score, {
                "domain": domain_id,
                "display_name": domain_data.get("display_name", domain_id),
                "score": score,
                "reasons": reasons,
                "goals": goals,
                "focus_areas": focus_areas,
                "use_cases": domain_use_cases,
                "complexity": domain_data.get("complexity", "medium"),
                "theme_preference": domain_data.get("theme_preference", "light"),
            }))
    
    # Sort by score descending
    domain_scores.sort(key=lambda x: x[1], reverse=True)
    
    return domain_scores


def get_taxonomy_slice_for_prompt(
    metrics: Optional[List[Dict[str, Any]]] = None,
    kpis: Optional[List[Dict[str, Any]]] = None,
    use_case: Optional[str] = None,
    domain_ids: Optional[List[str]] = None,
    max_domains: int = 5,
) -> Dict[str, Any]:
    """
    Return a compact taxonomy slice for prompt inclusion. Uses keyword lookup to
    select only relevant domains, reducing size from ~28KB to a few KB.
    
    Args:
        metrics: Optional metrics to extract keywords from
        kpis: Optional KPIs to extract keywords from
        use_case: Optional use case string
        domain_ids: Explicit domain IDs to include (overrides keyword lookup)
        max_domains: Max domains to include (default 5)
    
    Returns:
        Compact dict with only selected domains: {domain_id: {goals, focus_areas, ...}}
    """
    taxonomy = load_taxonomy()
    domains = dict(taxonomy.get("domains", {}))
    for k, v in taxonomy.items():
        if isinstance(v, dict) and not k.startswith("_") and k not in ("meta", "domains"):
            domains[k] = v

    if domain_ids:
        selected = [d for d in domain_ids if d in domains][:max_domains]
    else:
        keywords = []
        if metrics:
            for m in metrics:
                keywords.extend(_extract_keywords_from_text(
                    f"{m.get('name','')} {m.get('type','')} {m.get('source_table','')}"
                ))
        if kpis:
            for k in kpis:
                keywords.extend(_extract_keywords_from_text(k.get("label", "")))
        if use_case:
            keywords.extend(_extract_keywords_from_text(use_case))
        candidates = list(get_candidate_domains_from_keywords(keywords))[:max_domains]
        selected = candidates if candidates else list(domains.keys())[:max_domains]

    slice_data = {}
    for did in selected:
        d = domains.get(did)
        if isinstance(d, dict):
            slice_data[did] = {
                "display_name": d.get("display_name", did),
                "goals": d.get("goals", [])[:5],
                "focus_areas": d.get("focus_areas", [])[:5],
                "use_cases": d.get("use_cases", [])[:3],
                "complexity": d.get("complexity", "medium"),
                "theme_preference": d.get("theme_preference", "light"),
            }
    return slice_data


def get_domain_recommendations(
    metrics: List[Dict[str, Any]],
    kpis: List[Dict[str, Any]],
    use_case: Optional[str] = None,
    data_sources: Optional[List[str]] = None,
    top_k: int = 3,
) -> Dict[str, Any]:
    """
    Get top domain recommendations with detailed match information.
    
    Returns:
        Dict with top domains and recommendations for decisions.
    """
    matches = match_domain_from_metrics(metrics, kpis, use_case, data_sources)
    
    top_domains = matches[:top_k]
    
    # Build recommendations
    recommendations = {
        "top_domains": [match[2] for match in top_domains],
        "recommended_domain": top_domains[0][0] if top_domains else None,
        "recommended_decisions": {},
    }
    
    if top_domains:
        top_domain_data = top_domains[0][2]
        recommendations["recommended_decisions"] = {
            "domain": top_domain_data["domain"],
            "category": _domain_to_category(top_domain_data["domain"]),
            "complexity": top_domain_data.get("complexity", "medium"),
            "theme": top_domain_data.get("theme_preference", "light"),
        }
    
    return recommendations


def match_use_case_group(
    goal_text: str,
    data_sources: Optional[List[str]] = None,
    framework: Optional[str] = None,
) -> Tuple[str, float]:
    """
    Rule-based keyword match of freeform goal text to a use_case_group.
    Returns (use_case_group_id, confidence_score).
    Falls back to "operational_monitoring" with low confidence if no match.
    """
    _USE_CASE_KEYWORDS = {
        "soc2_audit": ["audit", "compliance evidence", "control testing", "soc2", "auditor"],
        "lms_learning_target": ["training", "learning", "lms", "completion", "cornerstone", "sumtotal"],
        "risk_posture_report": ["risk report", "risk posture", "risk summary", "board", "executive"],
        "executive_dashboard": ["executive", "board", "leadership", "kpi summary"],
        "operational_monitoring": ["monitoring", "alerts", "operations", "soc", "incident", "live"],
    }
    goal_lower = (goal_text or "").lower()
    best_match = "operational_monitoring"
    best_score = 0.3

    for use_case, keywords in _USE_CASE_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in goal_lower)
        if hits > 0:
            score = min(0.3 + hits * 0.2, 0.95)
            if score > best_score:
                best_match = use_case
                best_score = score

    return (best_match, best_score)


def expand_use_case_group(
    use_case_group: str,
    complexity: str,
) -> Dict[str, Any]:
    """
    Load metric_use_case_groups.json and return expanded group with
    complexity-gated optional groups.
    """
    from app.config.dashboard_paths import get_metric_use_case_groups_path
    path = get_metric_use_case_groups_path()
    try:
        with open(path, "r") as f:
            groups = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "required_groups": [],
            "optional_included": [],
            "default_audience": "security_ops",
            "default_timeframe": "monthly",
            "framework_overrides": {},
        }

    cfg = groups.get(use_case_group, groups.get("operational_monitoring", {}))
    required = cfg.get("required_groups", [])
    optional_all = cfg.get("optional_groups", [])
    # Complexity gating: high gets more optional groups
    optional_included = (
        optional_all[:2] if complexity == "high" else
        optional_all[:1] if complexity == "medium" else
        []
    )
    return {
        "required_groups": required,
        "optional_included": optional_included,
        "default_audience": cfg.get("default_audience", "security_ops"),
        "default_timeframe": cfg.get("default_timeframe", "monthly"),
        "framework_overrides": cfg.get("framework_overrides", {}),
    }


def join_control_anchors(
    focus_areas: List[str],
    framework: str,
) -> List[Dict[str, Any]]:
    """
    Join focus_areas against control_domain_taxonomy for a given framework.
    Returns list of anchor dicts: [{id, domain, display_name, focus, risk_categories}]
    """
    from app.config.dashboard_paths import get_control_domain_taxonomy_path
    path = get_control_domain_taxonomy_path()
    try:
        with open(path, "r") as f:
            taxonomy = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    framework_data = taxonomy.get(framework, taxonomy.get("soc2", {}))
    focus_set = set((fa or "").lower() for fa in focus_areas)

    anchors = []
    for ctrl_id, ctrl_data in framework_data.items():
        ctrl_focus = set((f or "").lower() for f in ctrl_data.get("focus_areas", []))
        if focus_set & ctrl_focus:
            anchors.append({
                "id": ctrl_id,
                "domain": ctrl_data.get("domain", ""),
                "display_name": ctrl_data.get("display_name", ctrl_id),
                "focus": list(ctrl_focus),
                "risk_categories": ctrl_data.get("risk_categories", []),
            })
    return anchors


def reverse_map_control_to_use_case(
    control_id: str,
    framework: str,
) -> Tuple[str, List[str]]:
    """
    Compliance-first entry point.
    Given a control ID, find the best use_case_group and resolve focus_areas.
    Returns (use_case_group_id, focus_areas_list)
    """
    from app.config.dashboard_paths import get_control_domain_taxonomy_path
    path = get_control_domain_taxonomy_path()
    try:
        with open(path, "r") as f:
            taxonomy = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return ("operational_monitoring", [])

    fw_data = taxonomy.get(framework, taxonomy.get("soc2", {}))
    ctrl = fw_data.get(control_id)
    if not ctrl:
        return ("operational_monitoring", [])

    focus_areas = ctrl.get("focus_areas", [])
    # Map focus to use case: training_compliance -> lms_learning_target, etc.
    focus_to_use_case = {
        "training_compliance": "lms_learning_target",
        "vulnerability_management": "operational_monitoring",
        "audit_logging": "soc2_audit",
        "access_control": "soc2_audit",
        "risk_exposure": "risk_posture_report",
    }
    for fa in focus_areas:
        if fa in focus_to_use_case:
            return (focus_to_use_case[fa], focus_areas)
    return ("soc2_audit", focus_areas)


def build_and_save_keyword_index() -> Path:
    """
    Build keyword index from taxonomy and save to taxonomy_keyword_index.json.
    Call after taxonomy generation/enrichment. Returns path to saved file.
    """
    taxonomy = load_taxonomy()
    domains = dict(taxonomy.get("domains", {}))
    for k, v in taxonomy.items():
        if isinstance(v, dict) and not k.startswith("_") and k not in ("meta", "domains"):
            domains[k] = v
    index = _build_keyword_index(domains)
    path = get_taxonomy_keyword_index_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(index, f, indent=0, sort_keys=True)
    global _KEYWORD_INDEX_CACHE
    _KEYWORD_INDEX_CACHE = index
    return path


# ═══════════════════════════════════════════════════════════════════════
# METRIC WIDGET → CHART TYPE MAPPING (for goal-driven dashboard generation)
# ═══════════════════════════════════════════════════════════════════════

WIDGET_TO_CHART_MAP: Dict[str, List[str]] = {
    "trend_line": ["line_basic", "area_stacked"],
    "line": ["line_basic", "area_stacked"],
    "line_multi": ["line_multi"],
    "area": ["area_stacked"],
    "bar": ["bar_vertical", "bar_grouped", "bar_stacked", "bar_horizontal"],
    "bar_horizontal": ["bar_horizontal"],
    "bar_compare": ["bar_grouped", "bar_vertical"],
    "gauge": ["gauge"],
    "kpi_card": ["kpi_card"],
    "pie": ["pie", "donut"],
    "donut": ["donut"],
    "treemap": ["treemap"],
    "scatter": ["scatter_basic"],
    "heatmap": ["heatmap"],
    "radar": ["radar"],
    "waterfall": ["bar_waterfall"],
    "funnel": ["funnel"],
    "list_card": ["kpi_card"],
    "signal_meter": ["gauge"],
}


def map_metric_widget_to_chart(
    widget_type: str,
    kpi_value_type: Optional[str] = None,
    metrics_intent: Optional[str] = None,
) -> str:
    """
    Map a metric's widget_type (from metric_recommendations) to a chart catalog ID.
    Used by BIND/SCORE when generating layout from metrics + gold models.

    Args:
        widget_type: e.g. "trend_line", "gauge", "bar_compare"
        kpi_value_type: "count" | "percentage" | "currency" — influences chart choice
        metrics_intent: "trend" | "distribution" | "comparison" — from metric

    Returns:
        Chart catalog ID (e.g. "line_basic", "gauge", "bar_grouped")
    """
    wt = (widget_type or "trend_line").lower().replace("-", "_")
    candidates = WIDGET_TO_CHART_MAP.get(wt, WIDGET_TO_CHART_MAP["trend_line"])

    # Prefer first candidate; refine by kpi_value_type / metrics_intent if needed
    if kpi_value_type in ("count", "percentage") and wt in ("kpi_card", "list_card"):
        return "stat_tile"
    if kpi_value_type == "percentage" and "gauge" in candidates:
        return "gauge"
    if metrics_intent == "trend" and "line_basic" in candidates:
        return "line_basic"
    if metrics_intent == "comparison" and "line_multi" in candidates:
        return "line_multi"
    if metrics_intent == "distribution" and "bar_horizontal" in candidates:
        return "bar_horizontal"
    if metrics_intent == "distribution" and "treemap" in candidates:
        return "treemap"
    if metrics_intent == "comparison" and "bar_grouped" in candidates:
        return "bar_grouped"
    if metrics_intent == "comparison" and "bar_vertical" in candidates:
        return "bar_vertical"

    return candidates[0] if candidates else "line_basic"


def match_metric_to_gold_table(
    metric: Dict[str, Any],
    gold_models: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Match a metric to a gold table by implementation_note, calculation_plan, or name hints.
    Returns gold table name or None if no match.
    """
    impl_note = (metric.get("implementation_note") or "").lower()
    calc_steps = " ".join(metric.get("calculation_plan_steps", [])).lower()
    metric_name = (metric.get("name") or "").lower()
    data_source = (metric.get("data_source_required") or "").lower()

    best_match: Optional[str] = None
    best_score = 0

    for gm in gold_models:
        gname = (gm.get("name") or "").lower()
        gdesc = (gm.get("description") or "").lower()

        score = 0
        if gname in impl_note or gname in calc_steps:
            score += 20
        if gname in impl_note:
            score += 15
        if any(part in gname for part in metric_name.split() if len(part) > 3):
            score += 5
        if data_source and data_source in gname:
            score += 10

        if score > best_score:
            best_score = score
            best_match = gm.get("name")

    return best_match


def _domain_to_category(domain_id: str) -> List[str]:
    """Map domain ID to template categories."""
    domain_category_map = {
        "ld_training": ["hr_learning"],
        "ld_operations": ["hr_learning"],
        "ld_engagement": ["hr_learning"],
        "security_operations": ["operations"],
        "compliance": ["compliance", "grc"],
        "executive": ["executive"],
        "grc": ["grc"],
        "iam": ["iam"],
        "data_ops": ["data_ops"],
        "hr_workforce": ["hr_learning"],
        "cross_domain": ["cross_domain"],
    }
    return domain_category_map.get(domain_id, ["operations"])

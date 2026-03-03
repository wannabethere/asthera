"""
Dashboard Taxonomy Matcher
==========================
Matches metrics, KPIs, and use cases to dashboard domains using the enriched taxonomy.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# Load taxonomy - try multiple possible locations
_TAXONOMY_PATHS = [
    # Enriched version in decision_trees
    Path(__file__).parent.parent / "agents" / "decision_trees" / "dashboard_domain_taxonomy_enriched.json",
    # Enriched version in registry_config
    Path(__file__).parent / "registry_config" / "dashboard_domain_taxonomy_enriched.json",
    # Non-enriched version in decision_trees
    Path(__file__).parent.parent / "agents" / "decision_trees" / "dashboard_domain_taxonomy.json",
    # Non-enriched version in registry_config
    Path(__file__).parent / "registry_config" / "dashboard_domain_taxonomy.json",
]
_TAXONOMY_CACHE: Optional[Dict[str, Any]] = None


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
    
    Args:
        metrics: List of metric dicts with 'name', 'type', 'source_table', etc.
        kpis: List of KPI dicts with 'label', 'value_expr', etc.
        use_case: Optional use case string (e.g., "SOC2 monitoring", "training compliance")
        data_sources: Optional list of data sources (e.g., ["siem", "cornerstone"])
    
    Returns:
        List of (domain_id, confidence_score, match_reasons) tuples, sorted by confidence.
    """
    taxonomy = load_taxonomy()
    domains = taxonomy.get("domains", {})
    
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
    
    # Score each domain
    domain_scores = []
    
    for domain_id, domain_data in domains.items():
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

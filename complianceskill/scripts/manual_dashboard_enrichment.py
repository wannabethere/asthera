#!/usr/bin/env python3
"""
Standalone manual enrichment — no pydantic or app deps.

Reads from data/dashboard/:
  - dashboard_registry.json
  - ld_templates_registry.json
  - lms_dashboard_metrics.json

Writes to app/ingestion/dashboard/:
  - enriched_templates.json
  - enriched_metrics.json
  - decision_tree.json
  - embedding_texts.json

Usage: python scripts/manual_dashboard_enrichment.py
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "dashboard"
OUTPUT_DIR = PROJECT_ROOT / "app" / "ingestion" / "dashboard"

_CATEGORY_MAP = {
    "Executive / SOC": "executive_reporting",
    "SOC Operations": "security_operations",
    "SOC Operations / Engineering": "security_operations",
    "Vulnerability Management": "security_operations",
    "Threat Detection": "security_operations",
    "UEBA / Threat Analytics": "security_operations",
    "Endpoint Security": "security_operations",
    "Network Security": "security_operations",
    "Network / Application": "security_operations",
    "Network Access": "security_operations",
    "DNS Security": "security_operations",
    "CDN / Web Traffic": "security_operations",
    "Web Application Security": "security_operations",
    "Application Security": "security_operations",
    "Database Security": "security_operations",
    "Data Security": "security_operations",
    "Cloud Security": "security_operations",
    "Cloud Security / Container": "security_operations",
    "Cloud Audit / IAM": "compliance_audit",
    "SIEM Operations": "data_operations",
    "Operations / Data Engineering": "data_operations",
    "End User Computing": "security_operations",
    "Compliance / Aggregation": "compliance_audit",
    "Compliance / Configuration": "compliance_audit",
    "ld_training": "learning_development",
    "ld_operations": "learning_development",
    "ld_engagement": "learning_development",
    "hr_workforce": "hr_workforce",
    "cross_domain": "cross_domain",
}

_AUDIENCE_MAP = {
    "SOC Analyst": "soc_analyst",
    "SOC Manager": "security_ops",
    "CISO": "executive_board",
    "Security Analyst": "soc_analyst",
    "Security Engineer": "security_ops",
    "Incident Responder": "soc_analyst",
    "Network Engineer": "security_ops",
    "Cloud Security Team": "security_ops",
    "Threat Intel Analyst": "soc_analyst",
    "Vulnerability Team": "security_ops",
    "Data Engineer": "data_engineer",
    "Compliance Team": "compliance_team",
    "Auditor": "compliance_team",
    "Risk Manager": "risk_management",
    "Executive": "executive_board",
    "Board": "executive_board",
    "HR Admin": "learning_admin",
    "L&D Admin": "learning_admin",
    "Training Admin": "learning_admin",
    "Learning Admin": "learning_admin",
    "LMS Admin": "learning_admin",
}

_FOCUS_KEYWORD_MAP = {
    "vulnerability": "vulnerability_management",
    "vuln": "vulnerability_management",
    "cve": "vulnerability_management",
    "incident": "incident_response",
    "alert": "incident_response",
    "threat": "threat_detection",
    "detection": "threat_detection",
    "network": "asset_inventory",
    "endpoint": "asset_inventory",
    "cloud": "asset_inventory",
    "compliance": "compliance_posture",
    "audit": "audit_logging",
    "iam": "access_control",
    "identity": "access_control",
    "access": "access_control",
    "training": "training_completion",
    "completion": "training_completion",
    "learner": "learner_engagement",
    "engagement": "learner_engagement",
    "login": "learner_engagement",
    "course": "content_effectiveness",
    "curriculum": "content_effectiveness",
    "pipeline": "pipeline_health",
    "data quality": "data_quality",
    "schema": "schema_drift",
    "vendor": "vendor_risk",
    "risk": "risk_exposure",
}

_FOCUS_AREA_DEFAULTS = {
    "security_operations": ["vulnerability_management", "incident_response", "threat_detection", "asset_inventory"],
    "compliance_audit": ["access_control", "audit_logging", "change_management", "data_protection", "training_compliance"],
    "learning_development": ["training_completion", "learner_engagement", "content_effectiveness", "compliance_training"],
    "hr_workforce": ["onboarding_offboarding", "headcount_planning", "performance_tracking", "attrition_risk"],
    "risk_management": ["vendor_risk", "control_effectiveness", "risk_exposure", "regulatory_change"],
    "executive_reporting": ["risk_exposure", "compliance_posture", "training_compliance"],
    "data_operations": ["pipeline_health", "data_quality", "schema_drift"],
    "cross_domain": ["training_compliance", "access_control", "compliance_posture"],
}

_SOURCE_CAPABILITY_MAP = {
    "Cornerstone LMS": "cornerstone.lms",
    "HRIS": "workday.hris",
    "Workday": "workday.hris",
    "Cornerstone": "cornerstone.lms",
    "LMS": "cornerstone.lms",
    "Finance ERP": "finance.erp",
}


def _sha256(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _map_audience(raw_list):
    out = []
    for a in raw_list:
        mapped = _AUDIENCE_MAP.get(a)
        if mapped and mapped not in out:
            out.append(mapped)
    return out or ["security_ops"]


def _infer_focus_areas(text, category):
    text_lower = text.lower()
    found = []
    for keyword, focus in _FOCUS_KEYWORD_MAP.items():
        if keyword in text_lower and focus not in found:
            found.append(focus)
    if not found:
        found = _FOCUS_AREA_DEFAULTS.get(category, ["vulnerability_management"])[:2]
    return found


def _map_source_capabilities(sources):
    caps = []
    for s in sources:
        mapped = _SOURCE_CAPABILITY_MAP.get(s, s.lower().replace(" ", "."))
        if mapped not in caps:
            caps.append(mapped)
    return caps


def enrich_dashboard_registry(path):
    with open(path) as f:
        raw = json.load(f)
    templates = []
    for db in raw.get("dashboards", []):
        category = _CATEGORY_MAP.get(db.get("category", ""), "security_operations")
        raw_audience = db.get("audience", [])
        audience_levels = _map_audience(raw_audience)
        description = db.get("description", "")
        name = db.get("name", db["id"])
        components = db.get("components", [])
        focus_areas = _infer_focus_areas(
            description + " " + " ".join(db.get("layout", {}).get("sections", [])),
            category,
        )
        chart_types = list({c.get("type", "") for c in components if c.get("type")})
        has_filters = bool(db.get("filters"))
        complexity = "high" if len(components) >= 6 else ("medium" if len(components) >= 3 else "low")
        destinations = ["embedded", "simple"]
        if category == "executive_reporting":
            destinations.append("powerbi")
        metric_profile_fit = ["count_heavy", "trend_heavy"]
        if category in ("compliance_audit", "executive_reporting"):
            metric_profile_fit = ["rate_percentage", "mixed"]
        sections = db.get("layout", {}).get("sections", [])
        best_for = [s.replace("_", " ").title() for s in sections[:4]]
        embedding_parts = [
            name, description,
            f"Category: {category}",
            f"Focus areas: {', '.join(focus_areas)}",
            f"Audience: {', '.join(audience_levels)}",
            f"Complexity: {complexity}",
            f"Metric profiles: {', '.join(metric_profile_fit)}",
            f"Destinations: embedded, simple" + (" powerbi" if "powerbi" in destinations else ""),
            f"Chart types: {', '.join(chart_types)}",
            f"Best for: {', '.join(best_for)}",
        ]
        if db.get("source"):
            embedding_parts.append(f"Source: {db['source']}")
        t = {
            "template_id": db["id"],
            "registry_source": "dashboard_registry",
            "name": name,
            "description": description,
            "source_system": db.get("source"),
            "content_hash": _sha256(db),
            "category": category,
            "focus_areas": focus_areas,
            "audience_levels": audience_levels,
            "complexity": complexity,
            "metric_profile_fit": metric_profile_fit,
            "supported_destinations": destinations,
            "interaction_modes": ["drill_down", "read_only"],
            "primitives": [],
            "panels": {},
            "layout_grid": db.get("layout", {}),
            "strip_cells": 0,
            "has_chat": False,
            "has_graph": False,
            "has_filters": has_filters,
            "chart_types": chart_types,
            "components": components,
            "best_for": best_for,
            "theme_hint": "dark",
            "domains": [category],
            "embedding_text": "\n".join(embedding_parts),
        }
        templates.append(t)
    return templates


def enrich_ld_templates_registry(path):
    with open(path) as f:
        raw = json.load(f)
    templates = []
    for tpl in raw.get("templates", []):
        category = _CATEGORY_MAP.get(tpl.get("category", ""), "learning_development")
        description = tpl.get("description", "")
        focus_areas = _infer_focus_areas(
            description + " " + " ".join(tpl.get("best_for", [])),
            category,
        )
        audience_levels = ["learning_admin"]
        complexity = tpl.get("complexity", "medium")
        destinations = ["embedded", "simple"]
        if tpl.get("category") in ("ld_operations", "hr_workforce"):
            destinations.append("powerbi")
        chart_types = tpl.get("chart_types", [])
        profile_fit = []
        if any("kpi" in c or "card" in c for c in chart_types):
            profile_fit.append("scorecard")
        if any("line" in c or "area" in c for c in chart_types):
            profile_fit.append("trend_heavy")
        if any("bar" in c for c in chart_types):
            profile_fit.append("comparison")
        if not profile_fit:
            profile_fit = ["mixed"]
        embedding_parts = [
            tpl.get("name", tpl["id"]),
            description,
            f"Category: {category}",
            f"Focus areas: {', '.join(focus_areas)}",
            f"Audience: {', '.join(audience_levels)}",
            f"Complexity: {complexity}",
            f"Metric profiles: {', '.join(profile_fit)}",
            f"Destinations: embedded, simple" + (" powerbi" if "powerbi" in destinations else ""),
            f"Chart types: {', '.join(chart_types)}",
            f"Best for: {', '.join(tpl.get('best_for', []))}",
            "Source: CCE L&D",
        ]
        t = {
            "template_id": tpl["id"],
            "registry_source": "ld_templates_registry",
            "name": tpl.get("name", tpl["id"]),
            "description": description,
            "source_system": "CCE L&D",
            "content_hash": _sha256(tpl),
            "category": category,
            "focus_areas": focus_areas,
            "audience_levels": audience_levels,
            "complexity": complexity,
            "metric_profile_fit": profile_fit,
            "supported_destinations": destinations,
            "interaction_modes": ["drill_down"],
            "primitives": tpl.get("primitives", []),
            "panels": tpl.get("panels", {}),
            "layout_grid": tpl.get("layout_grid", {}),
            "strip_cells": tpl.get("strip_cells", 0),
            "has_chat": tpl.get("has_chat", False),
            "has_graph": tpl.get("has_graph", False),
            "has_filters": tpl.get("has_filters", False),
            "chart_types": chart_types,
            "components": [],
            "best_for": tpl.get("best_for", []),
            "theme_hint": tpl.get("theme_hint", "light"),
            "domains": tpl.get("domains", []),
            "embedding_text": "\n".join(embedding_parts),
        }
        templates.append(t)
    return templates


def enrich_lms_metrics(path):
    with open(path) as f:
        raw = json.load(f)
    metrics = []
    type_to_profile = {
        "count": "count_heavy", "percentage": "rate_percentage", "rate": "rate_percentage",
        "trend_line": "trend_heavy", "trend": "trend_heavy", "status_distribution": "comparison",
        "distribution": "comparison", "score": "scorecard", "kpi_card": "scorecard",
        "currency": "count_heavy", "duration": "trend_heavy",
    }
    for db in raw.get("dashboards", []):
        db_id = db["dashboard_id"]
        db_name = db.get("dashboard_name", db_id)
        db_category = db.get("dashboard_category", "ld_operations")
        category = _CATEGORY_MAP.get(db_category, "learning_development")
        for m in db.get("metrics", []):
            metric_type = m.get("type", "count")
            chart_type = m.get("chart_type", "kpi_card")
            sources = m.get("sources", [])
            focus_areas = _infer_focus_areas(m.get("name", "") + " " + m.get("section", ""), category)
            profile = type_to_profile.get(metric_type, "mixed")
            name_lower = m.get("name", "").lower()
            good_dir = "down" if any(w in name_lower for w in ("overdue", "failed", "error", "breach", "incident")) else "up"
            if any(w in name_lower for w in ("completion", "coverage", "compliance")):
                good_dir = "up"
            embedding_parts = [
                m.get("name", m["id"]),
                f"Dashboard: {db_name}",
                f"Category: {category}",
                f"Type: {metric_type}",
                f"Unit: {m.get('unit', '')}",
                f"Focus areas: {', '.join(focus_areas)}",
                f"Source capabilities: {', '.join(_map_source_capabilities(sources))}",
                f"Chart type: {chart_type}",
                f"Section: {m.get('section', '')}",
            ]
            em = {
                "metric_id": f"{db_id}:{m['id']}",
                "dashboard_id": db_id,
                "dashboard_name": db_name,
                "dashboard_category": db_category,
                "name": m.get("name", m["id"]),
                "metric_type": metric_type,
                "unit": m.get("unit") or "",
                "chart_type": chart_type,
                "section": m.get("section") or "",
                "metric_profile": profile,
                "category": category,
                "focus_areas": focus_areas,
                "source_capabilities": _map_source_capabilities(sources),
                "source_schemas": [],
                "kpis": [],
                "threshold_warning": None,
                "threshold_critical": None,
                "good_direction": good_dir,
                "axis_label": m.get("unit") or "",
                "aggregation": "sum" if metric_type == "count" else "avg",
                "display_name": m.get("name", m["id"]),
                "content_hash": _sha256(m),
                "embedding_text": "\n".join(embedding_parts),
            }
            metrics.append(em)
    return metrics


def build_decision_tree(templates, metrics):
    category_counts = {}
    for t in templates:
        c = t["category"]
        category_counts[c] = category_counts.get(c, 0) + 1
    category_keywords = {
        "compliance_audit": ["soc2", "hipaa", "nist", "audit", "controls", "compliance", "iam", "cloud audit"],
        "security_operations": ["incident", "threat", "vulnerability", "siem", "detection", "alert", "endpoint", "network", "dns"],
        "learning_development": ["training", "completion", "lms", "course", "learner", "cornerstone", "csod", "l&d"],
        "hr_workforce": ["onboarding", "headcount", "attrition", "workforce", "employee", "workday"],
        "risk_management": ["risk", "exposure", "vendor", "third-party", "grc", "posture"],
        "executive_reporting": ["board", "executive", "summary", "leadership", "ciso", "kpi rollup"],
        "data_operations": ["pipeline", "etl", "dbt", "data quality", "freshness", "schema", "siem ops"],
        "cross_domain": ["hybrid", "unified", "multi-framework", "integrated"],
    }
    registry_for = {"learning_development": "ld_templates_registry", "hr_workforce": "ld_templates_registry", "cross_domain": "both"}
    q1_options = []
    for cat_val, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        q1_options.append({
            "option_id": cat_val,
            "label": cat_val.replace("_", " ").title(),
            "keywords": category_keywords.get(cat_val, [cat_val]),
            "maps_to": {"category": cat_val, "registry_source": registry_for.get(cat_val, "dashboard_registry")},
            "confidence": 0.9,
            "tags": ["primary"],
        })
    all_focus = {}
    for t in templates:
        for fa in t["focus_areas"]:
            all_focus[fa] = all_focus.get(fa, 0) + 1
    focus_keywords = {
        "vulnerability_management": ["vulnerability", "vuln", "cve", "patch", "cvss"],
        "incident_response": ["incident", "alert", "case", "response", "triage"],
        "threat_detection": ["threat", "detection", "malware", "rule", "signal"],
        "asset_inventory": ["endpoint", "host", "network", "cloud", "asset"],
        "access_control": ["iam", "identity", "access", "privilege", "certification"],
        "audit_logging": ["audit", "log", "event", "siem", "trail"],
        "training_completion": ["training", "completion", "assignment", "overdue"],
        "learner_engagement": ["learner", "engagement", "login", "active user"],
        "content_effectiveness": ["course", "content", "curriculum", "effectiveness"],
        "pipeline_health": ["pipeline", "etl", "data quality", "freshness"],
        "vendor_risk": ["vendor", "third-party", "supplier", "partner"],
        "risk_exposure": ["risk", "exposure", "posture", "score"],
    }
    q2_options = []
    for fa, count in sorted(all_focus.items(), key=lambda x: -x[1]):
        q2_options.append({
            "option_id": fa,
            "label": fa.replace("_", " ").title(),
            "keywords": focus_keywords.get(fa, [fa.replace("_", " ")]),
            "maps_to": {"focus_area": fa},
            "confidence": 0.85,
        })
    all_audience = {}
    for t in templates:
        for a in t["audience_levels"]:
            all_audience[a] = all_audience.get(a, 0) + 1
    audience_keywords = {
        "security_ops": ["security team", "analyst", "soc", "engineer"],
        "soc_analyst": ["soc analyst", "tier 1", "tier 2", "incident responder"],
        "compliance_team": ["compliance", "auditor", "grc", "controls"],
        "executive_board": ["ciso", "board", "vp", "leadership", "executive"],
        "learning_admin": ["l&d", "training admin", "lms admin", "hr"],
        "data_engineer": ["data engineer", "pipeline", "etl"],
    }
    q4_options = []
    for aud_val, count in sorted(all_audience.items(), key=lambda x: -x[1]):
        q4_options.append({
            "option_id": aud_val,
            "label": aud_val.replace("_", " ").title(),
            "keywords": audience_keywords.get(aud_val, [aud_val]),
            "maps_to": {"audience": aud_val},
            "confidence": 0.8,
        })
    dest_options = [
        {"option_id": "embedded", "label": "Embedded (ECharts / React)", "keywords": ["embedded", "echarts", "react", "web app", "platform"], "maps_to": {"destination_type": "embedded"}, "confidence": 1.0, "tags": []},
        {"option_id": "powerbi", "label": "Power BI", "keywords": ["powerbi", "power bi", "pbix", "dax"], "maps_to": {"destination_type": "powerbi"}, "confidence": 1.0, "tags": []},
        {"option_id": "simple", "label": "Simple / Static HTML", "keywords": ["simple", "static", "html", "pdf", "email"], "maps_to": {"destination_type": "simple"}, "confidence": 1.0, "tags": []},
        {"option_id": "slack_digest", "label": "Slack / Email Digest", "keywords": ["slack", "email", "digest", "notification", "message"], "maps_to": {"destination_type": "slack_digest"}, "confidence": 1.0, "tags": []},
        {"option_id": "api_json", "label": "API / JSON Export", "keywords": ["api", "json", "headless", "export", "integration"], "maps_to": {"destination_type": "api_json"}, "confidence": 1.0, "tags": []},
    ]
    metric_profile_options = [
        {"option_id": "count_heavy", "label": "Count Heavy", "keywords": ["count", "total", "number of", "quantity"], "maps_to": {"metric_profile": "count_heavy"}, "confidence": 1.0, "tags": ["deterministic"]},
        {"option_id": "trend_heavy", "label": "Trend Heavy", "keywords": ["trend", "over time", "time series", "historical"], "maps_to": {"metric_profile": "trend_heavy"}, "confidence": 1.0, "tags": ["deterministic"]},
        {"option_id": "rate_percentage", "label": "Rate Percentage", "keywords": ["percentage", "rate", "ratio", "compliance %"], "maps_to": {"metric_profile": "rate_percentage"}, "confidence": 1.0, "tags": ["deterministic"]},
        {"option_id": "comparison", "label": "Comparison", "keywords": ["comparison", "distribution", "ranking", "breakdown"], "maps_to": {"metric_profile": "comparison"}, "confidence": 1.0, "tags": ["deterministic"]},
        {"option_id": "mixed", "label": "Mixed", "keywords": ["mixed", "varied", "multiple types"], "maps_to": {"metric_profile": "mixed"}, "confidence": 1.0, "tags": ["deterministic"]},
        {"option_id": "scorecard", "label": "Scorecard", "keywords": ["scorecard", "kpi", "summary card", "single value"], "maps_to": {"metric_profile": "scorecard"}, "confidence": 1.0, "tags": ["deterministic"]},
    ]
    complexity_options = [
        {"option_id": "low", "label": "Summary / Overview", "keywords": ["summary", "overview", "exec", "kpi only"], "maps_to": {"complexity": "low", "max_panels": 2}, "confidence": 0.9},
        {"option_id": "medium", "label": "Standard", "keywords": ["standard", "operational", "regular"], "maps_to": {"complexity": "medium", "max_panels": 4}, "confidence": 0.9},
        {"option_id": "high", "label": "Full Detail", "keywords": ["detailed", "full", "analyst", "deep dive", "all metrics"], "maps_to": {"complexity": "high", "max_panels": 6}, "confidence": 0.9},
    ]
    interaction_options = [
        {"option_id": "drill_down", "label": "Interactive Drill-Down", "keywords": ["drill", "click", "filter", "explore", "interactive"], "maps_to": {"interaction_mode": "drill_down"}, "confidence": 0.85},
        {"option_id": "read_only", "label": "Read-Only View", "keywords": ["read only", "view only", "no interaction", "static"], "maps_to": {"interaction_mode": "read_only"}, "confidence": 0.85},
        {"option_id": "real_time", "label": "Real-Time / Live", "keywords": ["real time", "live", "streaming", "realtime"], "maps_to": {"interaction_mode": "real_time"}, "confidence": 0.9},
        {"option_id": "scheduled_report", "label": "Scheduled Report", "keywords": ["scheduled", "daily report", "weekly report", "digest"], "maps_to": {"interaction_mode": "scheduled_report"}, "confidence": 0.9},
    ]
    return {
        "version": "1.0.0",
        "questions": [
            {"question_id": "destination_type", "question": "Where will the dashboard be rendered or delivered?", "field": "destination_type", "options": dest_options, "auto_resolve_from": "output_format", "resolution_priority": 0},
            {"question_id": "category", "question": "What is the primary domain or purpose of this dashboard?", "field": "category", "options": q1_options, "auto_resolve_from": "goal_statement", "resolution_priority": 1},
            {"question_id": "focus_area", "question": "What is the primary focus area within that domain?", "field": "focus_area", "options": q2_options, "auto_resolve_from": "suggested_focus_areas", "resolution_priority": 2},
            {"question_id": "metric_profile", "question": "What types of metrics dominate this dataset?", "field": "metric_profile", "options": metric_profile_options, "auto_resolve_from": "metrics", "resolution_priority": 3},
            {"question_id": "audience", "question": "Who is the primary audience for this dashboard?", "field": "audience", "options": q4_options, "auto_resolve_from": "persona", "resolution_priority": 4},
            {"question_id": "complexity", "question": "How much detail is required?", "field": "complexity", "options": complexity_options, "auto_resolve_from": "audience", "resolution_priority": 5},
            {"question_id": "interaction_mode", "question": "How will users interact with the dashboard?", "field": "interaction_mode", "options": interaction_options, "auto_resolve_from": "timeframe", "resolution_priority": 6},
        ],
        "registry_targets": {
            "compliance_audit": "dashboard_registry",
            "security_operations": "dashboard_registry",
            "learning_development": "ld_templates_registry",
            "hr_workforce": "ld_templates_registry",
            "risk_management": "dashboard_registry",
            "executive_reporting": "dashboard_registry",
            "data_operations": "dashboard_registry",
            "cross_domain": "both",
        },
        "destination_gates": {
            "embedded": {"allowed_all": True},
            "powerbi": {"excluded_primitives": ["chat_panel", "causal_graph", "heatmap_calendar", "sankey", "treemap"]},
            "simple": {"allowed_primitives": ["kpi_strip", "bar", "line", "table"], "max_panels": 2},
            "slack_digest": {"allowed_primitives": ["kpi_strip"], "max_kpi_cells": 6},
            "api_json": {"emit_metric_spec_only": True},
        },
        "defaults": {
            "embedded": {"category": "security_operations", "audience": "security_ops", "complexity": "medium"},
            "powerbi": {"category": "executive_reporting", "audience": "executive_board", "complexity": "low"},
            "simple": {"category": "compliance_audit", "audience": "compliance_team", "complexity": "low"},
            "slack_digest": {"category": "executive_reporting", "audience": "executive_board", "complexity": "low"},
            "api_json": {},
        },
        "built_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    start = datetime.now(timezone.utc)
    print("=" * 60)
    print("Dashboard Enrichment — manual (standalone, no deps)")
    print("=" * 60)
    dr_path = DATA_DIR / "dashboard_registry.json"
    ld_path = DATA_DIR / "ld_templates_registry.json"
    lms_path = DATA_DIR / "lms_dashboard_metrics.json"
    for name, p in [("dashboard_registry", dr_path), ("ld_templates", ld_path), ("lms_metrics", lms_path)]:
        if not p.exists():
            print(f"ERROR: {p} not found")
            return 1
        print(f"  Source: {p}")
    dr_templates = enrich_dashboard_registry(dr_path)
    ld_templates = enrich_ld_templates_registry(ld_path)
    all_templates = dr_templates + ld_templates
    metrics = enrich_lms_metrics(lms_path)
    tree = build_decision_tree(all_templates, metrics)
    print(f"\n  Templates: {len(all_templates)} ({len(dr_templates)} security + {len(ld_templates)} L&D)")
    print(f"  Metrics: {len(metrics)}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def write_json(path, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    write_json(OUTPUT_DIR / "enriched_templates.json", {
        "meta": {"total": len(all_templates), "from_dashboard_registry": len(dr_templates), "from_ld_templates": len(ld_templates), "generated_at": start.isoformat()},
        "templates": all_templates,
    })
    write_json(OUTPUT_DIR / "enriched_metrics.json", {
        "meta": {"total": len(metrics), "generated_at": start.isoformat()},
        "metrics": metrics,
    })
    write_json(OUTPUT_DIR / "decision_tree.json", tree)
    write_json(OUTPUT_DIR / "embedding_texts.json", {
        "templates": {t["template_id"]: t["embedding_text"] for t in all_templates},
        "metrics": {m["metric_id"]: m["embedding_text"] for m in metrics},
    })
    print(f"  Wrote enriched_templates.json, enriched_metrics.json, decision_tree.json, embedding_texts.json")
    print(f"  Done in {(datetime.now(timezone.utc) - start).total_seconds():.1f}s")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    exit(main())

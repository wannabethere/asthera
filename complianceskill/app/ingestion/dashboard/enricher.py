"""
CCE Dashboard Enricher — Core Enrichment Engine
=================================================
Reads the three source files and produces:
  - EnrichedTemplate[]  (from dashboard_registry + ld_templates_registry)
  - EnrichedMetric[]    (from lms_dashboard_metrics)
  - DecisionTree        (synthesised from all three)

No external API calls — all enrichment is deterministic.
LLM enrichment hooks are clearly marked for optional activation.
"""

from __future__ import annotations

import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from models import (
    EnrichedTemplate, EnrichedMetric, DecisionTree,
    DecisionQuestion, DecisionOption, DestinationConstraints,
    DashboardCategory, AudienceLevel, ComplexityLevel,
    MetricProfile, DestinationType, InteractionMode,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# CATEGORY MAPPINGS — raw registry values → canonical DashboardCategory
# ═══════════════════════════════════════════════════════════════════════

_CATEGORY_MAP: dict[str, DashboardCategory] = {
    # dashboard_registry categories
    "Executive / SOC":              DashboardCategory.EXECUTIVE,
    "SOC Operations":               DashboardCategory.SECURITY_OPS,
    "SOC Operations / Engineering": DashboardCategory.SECURITY_OPS,
    "Vulnerability Management":     DashboardCategory.SECURITY_OPS,
    "Threat Detection":             DashboardCategory.SECURITY_OPS,
    "UEBA / Threat Analytics":      DashboardCategory.SECURITY_OPS,
    "Endpoint Security":            DashboardCategory.SECURITY_OPS,
    "Network Security":             DashboardCategory.SECURITY_OPS,
    "Network / Application":        DashboardCategory.SECURITY_OPS,
    "Network Access":               DashboardCategory.SECURITY_OPS,
    "DNS Security":                 DashboardCategory.SECURITY_OPS,
    "CDN / Web Traffic":            DashboardCategory.SECURITY_OPS,
    "Web Application Security":     DashboardCategory.SECURITY_OPS,
    "Application Security":         DashboardCategory.SECURITY_OPS,
    "Database Security":            DashboardCategory.SECURITY_OPS,
    "Data Security":                DashboardCategory.SECURITY_OPS,
    "Cloud Security":               DashboardCategory.SECURITY_OPS,
    "Cloud Security / Container":   DashboardCategory.SECURITY_OPS,
    "Cloud Audit / IAM":            DashboardCategory.COMPLIANCE_AUDIT,
    "SIEM Operations":              DashboardCategory.DATA_OPS,
    "Operations / Data Engineering":DashboardCategory.DATA_OPS,
    "End User Computing":           DashboardCategory.SECURITY_OPS,
    "Compliance / Aggregation":     DashboardCategory.COMPLIANCE_AUDIT,
    "Compliance / Configuration":   DashboardCategory.COMPLIANCE_AUDIT,
    # ld_templates_registry categories
    "ld_training":                  DashboardCategory.LEARNING_DEV,
    "ld_operations":                DashboardCategory.LEARNING_DEV,
    "ld_engagement":                DashboardCategory.LEARNING_DEV,
    "hr_workforce":                 DashboardCategory.HR_WORKFORCE,
    "cross_domain":                 DashboardCategory.CROSS_DOMAIN,
    # lms_dashboard_metrics dashboard_category
    "ld_operations":                DashboardCategory.LEARNING_DEV,
}

_AUDIENCE_MAP: dict[str, AudienceLevel] = {
    "SOC Analyst":          AudienceLevel.SOC_ANALYST,
    "SOC Manager":          AudienceLevel.SECURITY_OPS,
    "CISO":                 AudienceLevel.EXECUTIVE_BOARD,
    "Security Analyst":     AudienceLevel.SOC_ANALYST,
    "Security Engineer":    AudienceLevel.SECURITY_OPS,
    "Incident Responder":   AudienceLevel.SOC_ANALYST,
    "Network Engineer":     AudienceLevel.SECURITY_OPS,
    "Cloud Security Team":  AudienceLevel.SECURITY_OPS,
    "Threat Intel Analyst": AudienceLevel.SOC_ANALYST,
    "Vulnerability Team":   AudienceLevel.SECURITY_OPS,
    "Data Engineer":        AudienceLevel.DATA_ENGINEER,
    "Compliance Team":      AudienceLevel.COMPLIANCE_TEAM,
    "Auditor":              AudienceLevel.COMPLIANCE_TEAM,
    "Risk Manager":         AudienceLevel.RISK_MANAGEMENT,
    "Executive":            AudienceLevel.EXECUTIVE_BOARD,
    "Board":                AudienceLevel.EXECUTIVE_BOARD,
    "HR Admin":             AudienceLevel.LEARNING_ADMIN,
    "L&D Admin":            AudienceLevel.LEARNING_ADMIN,
    "Training Admin":       AudienceLevel.LEARNING_ADMIN,
    "Learning Admin":       AudienceLevel.LEARNING_ADMIN,
    "LMS Admin":            AudienceLevel.LEARNING_ADMIN,
}

_FOCUS_AREA_MAP: dict[str, list[str]] = {
    DashboardCategory.SECURITY_OPS:     ["vulnerability_management", "incident_response", "threat_detection", "asset_inventory"],
    DashboardCategory.COMPLIANCE_AUDIT: ["access_control", "audit_logging", "change_management", "data_protection", "training_compliance"],
    DashboardCategory.LEARNING_DEV:     ["training_completion", "learner_engagement", "content_effectiveness", "compliance_training"],
    DashboardCategory.HR_WORKFORCE:     ["onboarding_offboarding", "headcount_planning", "performance_tracking", "attrition_risk"],
    DashboardCategory.RISK_MANAGEMENT:  ["vendor_risk", "control_effectiveness", "risk_exposure", "regulatory_change"],
    DashboardCategory.EXECUTIVE:        ["risk_exposure", "compliance_posture", "training_compliance"],
    DashboardCategory.DATA_OPS:         ["pipeline_health", "data_quality", "schema_drift"],
    DashboardCategory.CROSS_DOMAIN:     ["training_compliance", "access_control", "compliance_posture"],
}

# Keyword → focus_area for fine-grained matching
_FOCUS_KEYWORD_MAP: dict[str, str] = {
    "vulnerability": "vulnerability_management",
    "vuln":          "vulnerability_management",
    "cve":           "vulnerability_management",
    "incident":      "incident_response",
    "alert":         "incident_response",
    "threat":        "threat_detection",
    "detection":     "threat_detection",
    "network":       "asset_inventory",
    "endpoint":      "asset_inventory",
    "cloud":         "asset_inventory",
    "compliance":    "compliance_posture",
    "audit":         "audit_logging",
    "iam":           "access_control",
    "identity":      "access_control",
    "access":        "access_control",
    "training":      "training_completion",
    "completion":    "training_completion",
    "learner":       "learner_engagement",
    "engagement":    "learner_engagement",
    "login":         "learner_engagement",
    "course":        "content_effectiveness",
    "curriculum":    "content_effectiveness",
    "pipeline":      "pipeline_health",
    "data quality":  "data_quality",
    "schema":        "schema_drift",
    "vendor":        "vendor_risk",
    "risk":          "risk_exposure",
}

_SOURCE_CAPABILITY_MAP: dict[str, str] = {
    "Cornerstone LMS":   "cornerstone.lms",
    "HRIS":              "workday.hris",
    "Workday":           "workday.hris",
    "Cornerstone":       "cornerstone.lms",
    "LMS":               "cornerstone.lms",
}

_METRIC_TYPE_TO_PROFILE: dict[str, MetricProfile] = {
    "count":               MetricProfile.COUNT_HEAVY,
    "percentage":          MetricProfile.RATE_PCT,
    "rate":                MetricProfile.RATE_PCT,
    "trend_line":          MetricProfile.TREND_HEAVY,
    "trend":               MetricProfile.TREND_HEAVY,
    "status_distribution": MetricProfile.COMPARISON,
    "distribution":        MetricProfile.COMPARISON,
    "score":               MetricProfile.SCORECARD,
    "kpi_card":            MetricProfile.SCORECARD,
    "currency":            MetricProfile.COUNT_HEAVY,
    "duration":            MetricProfile.TREND_HEAVY,
}


# ═══════════════════════════════════════════════════════════════════════
# HELPER UTILITIES
# ═══════════════════════════════════════════════════════════════════════

def _sha256(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]


def _map_audience(raw_list: list[str]) -> list[AudienceLevel]:
    out = []
    for a in raw_list:
        mapped = _AUDIENCE_MAP.get(a)
        if mapped and mapped not in out:
            out.append(mapped)
    return out or [AudienceLevel.SECURITY_OPS]


def _infer_focus_areas(text: str, category: DashboardCategory) -> list[str]:
    """Extract focus areas by scanning text for keywords, then fall back to category default."""
    text_lower = text.lower()
    found = []
    for keyword, focus in _FOCUS_KEYWORD_MAP.items():
        if keyword in text_lower and focus not in found:
            found.append(focus)
    if not found:
        found = _FOCUS_AREA_MAP.get(category, ["vulnerability_management"])[:2]
    return found


def _infer_metric_profile(metrics: list[dict]) -> MetricProfile:
    """Deterministically derive metric profile from type distribution."""
    if not metrics:
        return MetricProfile.MIXED
    counts: dict[MetricProfile, int] = {}
    for m in metrics:
        t = m.get("type", "") or m.get("chart_type", "")
        profile = _METRIC_TYPE_TO_PROFILE.get(t, MetricProfile.MIXED)
        counts[profile] = counts.get(profile, 0) + 1
    dominant = max(counts, key=counts.get)
    top_count = counts[dominant]
    if top_count / len(metrics) >= 0.5:
        return dominant
    return MetricProfile.MIXED


def _infer_complexity_from_components(count: int, has_chat: bool, has_graph: bool) -> ComplexityLevel:
    if count >= 6 or has_graph:
        return ComplexityLevel.HIGH
    if count >= 3 or has_chat:
        return ComplexityLevel.MEDIUM
    return ComplexityLevel.LOW


def _map_source_capabilities(sources: list[str]) -> list[str]:
    caps = []
    for s in sources:
        mapped = _SOURCE_CAPABILITY_MAP.get(s, s.lower().replace(" ", "."))
        if mapped not in caps:
            caps.append(mapped)
    return caps


def _build_embedding_text_template(t: EnrichedTemplate) -> str:
    parts = [
        t.name,
        t.description,
        f"Category: {t.category.value}",
        f"Focus areas: {', '.join(t.focus_areas)}",
        f"Audience: {', '.join(a.value for a in t.audience_levels)}",
        f"Complexity: {t.complexity.value}",
        f"Metric profiles: {', '.join(p.value for p in t.metric_profile_fit)}",
        f"Destinations: {', '.join(d.value for d in t.supported_destinations)}",
        f"Chart types: {', '.join(t.chart_types)}",
        f"Best for: {', '.join(t.best_for)}",
    ]
    if t.source_system:
        parts.append(f"Source: {t.source_system}")
    return "\n".join(parts)


def _build_embedding_text_metric(m: EnrichedMetric) -> str:
    parts = [
        m.name,
        f"Dashboard: {m.dashboard_name}",
        f"Category: {m.category.value}",
        f"Type: {m.metric_type}",
        f"Unit: {m.unit}",
        f"Focus areas: {', '.join(m.focus_areas)}",
        f"Source capabilities: {', '.join(m.source_capabilities)}",
        f"Chart type: {m.chart_type}",
        f"Section: {m.section}",
    ]
    if m.kpis:
        parts.append(f"KPIs: {', '.join(m.kpis)}")
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════
# ENRICHER: dashboard_registry.json → EnrichedTemplate[]
# ═══════════════════════════════════════════════════════════════════════

def enrich_dashboard_registry(path: Path) -> list[EnrichedTemplate]:
    """Parse dashboard_registry.json and produce EnrichedTemplate records."""
    with open(path) as f:
        raw = json.load(f)

    templates = []
    for db in raw.get("dashboards", []):
        category = _CATEGORY_MAP.get(db.get("category", ""), DashboardCategory.SECURITY_OPS)

        raw_audience = db.get("audience", [])
        audience_levels = _map_audience(raw_audience)

        description = db.get("description", "")
        name = db.get("name", db["id"])
        components = db.get("components", [])

        focus_areas = _infer_focus_areas(
            description + " " + " ".join(db.get("layout", {}).get("sections", [])),
            category,
        )

        # Component-level chart types
        chart_types = list({
            c.get("type", "") for c in components if c.get("type")
        })

        has_filters  = bool(db.get("filters"))
        has_chat     = False   # security dashboards don't have AI chat
        has_graph    = False

        complexity = _infer_complexity_from_components(
            len(components), has_chat, has_graph
        )

        # Security dashboards: embedded + simple always; powerbi if executive
        destinations = [DestinationType.EMBEDDED, DestinationType.SIMPLE]
        if category == DashboardCategory.EXECUTIVE:
            destinations.append(DestinationType.POWERBI)

        metric_profile_fit = [MetricProfile.COUNT_HEAVY, MetricProfile.TREND_HEAVY]
        if category in (DashboardCategory.COMPLIANCE_AUDIT, DashboardCategory.EXECUTIVE):
            metric_profile_fit = [MetricProfile.RATE_PCT, MetricProfile.MIXED]

        # Build best_for from layout sections
        sections = db.get("layout", {}).get("sections", [])
        best_for = [s.replace("_", " ").title() for s in sections[:4]]

        t = EnrichedTemplate(
            template_id=db["id"],
            registry_source="dashboard_registry",
            name=name,
            description=description,
            source_system=db.get("source"),
            content_hash=_sha256(db),
            category=category,
            focus_areas=focus_areas,
            audience_levels=audience_levels,
            complexity=complexity,
            metric_profile_fit=metric_profile_fit,
            supported_destinations=destinations,
            interaction_modes=[InteractionMode.DRILL_DOWN, InteractionMode.READ_ONLY],
            primitives=[],
            panels={},
            layout_grid=db.get("layout", {}),
            strip_cells=0,
            has_chat=has_chat,
            has_graph=has_graph,
            has_filters=has_filters,
            chart_types=chart_types,
            components=components,
            best_for=best_for,
            theme_hint="dark",
            domains=[category.value],
            powerbi_constraints=DestinationConstraints(
                excluded_primitives=["chat_panel", "causal_graph"],
                measure_format="dax",
            ),
            simple_constraints=DestinationConstraints(
                excluded_primitives=["chat_panel", "causal_graph", "filters"],
                max_panels=2,
            ),
        )
        t.embedding_text = _build_embedding_text_template(t)
        templates.append(t)
        logger.info(f"  [dashboard_registry] enriched: {t.template_id}")

    logger.info(f"dashboard_registry: {len(templates)} templates enriched")
    return templates


# ═══════════════════════════════════════════════════════════════════════
# ENRICHER: ld_templates_registry.json → EnrichedTemplate[]
# ═══════════════════════════════════════════════════════════════════════

def enrich_ld_templates_registry(path: Path) -> list[EnrichedTemplate]:
    """Parse ld_templates_registry.json and produce EnrichedTemplate records."""
    with open(path) as f:
        raw = json.load(f)

    templates = []
    for tpl in raw.get("templates", []):
        category = _CATEGORY_MAP.get(tpl.get("category", ""), DashboardCategory.LEARNING_DEV)

        description = tpl.get("description", "")
        focus_areas = _infer_focus_areas(
            description + " " + " ".join(tpl.get("best_for", [])),
            category,
        )

        # L&D templates: audience derived from category
        audience_map = {
            DashboardCategory.LEARNING_DEV: [AudienceLevel.LEARNING_ADMIN],
            DashboardCategory.HR_WORKFORCE: [AudienceLevel.LEARNING_ADMIN],
            DashboardCategory.CROSS_DOMAIN: [AudienceLevel.COMPLIANCE_TEAM, AudienceLevel.LEARNING_ADMIN],
        }
        audience_levels = audience_map.get(category, [AudienceLevel.LEARNING_ADMIN])

        complexity_map = {
            "low":    ComplexityLevel.LOW,
            "medium": ComplexityLevel.MEDIUM,
            "high":   ComplexityLevel.HIGH,
        }
        complexity = complexity_map.get(tpl.get("complexity", "medium"), ComplexityLevel.MEDIUM)

        # L&D templates support embedded + simple; powerbi for operations dashboards
        destinations = [DestinationType.EMBEDDED, DestinationType.SIMPLE]
        if tpl.get("category") in ("ld_operations", "hr_workforce"):
            destinations.append(DestinationType.POWERBI)

        has_chat  = tpl.get("has_chat", False)
        has_graph = tpl.get("has_graph", False)

        interaction_modes = [InteractionMode.DRILL_DOWN]
        if has_chat:
            interaction_modes.append(InteractionMode.REAL_TIME)

        # Infer metric profile fit from chart_types
        chart_types = tpl.get("chart_types", [])
        profile_fit = []
        if any("kpi" in c or "card" in c for c in chart_types):
            profile_fit.append(MetricProfile.SCORECARD)
        if any("line" in c or "area" in c for c in chart_types):
            profile_fit.append(MetricProfile.TREND_HEAVY)
        if any("bar" in c for c in chart_types):
            profile_fit.append(MetricProfile.COMPARISON)
        if not profile_fit:
            profile_fit = [MetricProfile.MIXED]

        t = EnrichedTemplate(
            template_id=tpl["id"],
            registry_source="ld_templates_registry",
            name=tpl.get("name", tpl["id"]),
            description=description,
            source_system="CCE L&D",
            content_hash=_sha256(tpl),
            category=category,
            focus_areas=focus_areas,
            audience_levels=audience_levels,
            complexity=complexity,
            metric_profile_fit=profile_fit,
            supported_destinations=destinations,
            interaction_modes=interaction_modes,
            primitives=tpl.get("primitives", []),
            panels=tpl.get("panels", {}),
            layout_grid=tpl.get("layout_grid", {}),
            strip_cells=tpl.get("strip_cells", 0),
            has_chat=has_chat,
            has_graph=has_graph,
            has_filters=tpl.get("has_filters", False),
            chart_types=chart_types,
            components=[],
            best_for=tpl.get("best_for", []),
            theme_hint=tpl.get("theme_hint", "light"),
            domains=tpl.get("domains", []),
            powerbi_constraints=DestinationConstraints(
                excluded_primitives=["chat_panel", "causal_graph"],
                measure_format="dax",
            ),
            simple_constraints=DestinationConstraints(
                excluded_primitives=["chat_panel", "causal_graph", "filters"],
                max_panels=2,
            ),
        )
        t.embedding_text = _build_embedding_text_template(t)
        templates.append(t)
        logger.info(f"  [ld_templates] enriched: {t.template_id}")

    logger.info(f"ld_templates_registry: {len(templates)} templates enriched")
    return templates


# ═══════════════════════════════════════════════════════════════════════
# ENRICHER: lms_dashboard_metrics.json → EnrichedMetric[]
# ═══════════════════════════════════════════════════════════════════════

def enrich_lms_metrics(path: Path) -> list[EnrichedMetric]:
    """Parse lms_dashboard_metrics.json and produce EnrichedMetric records."""
    with open(path) as f:
        raw = json.load(f)

    metrics = []
    for db in raw.get("dashboards", []):
        db_id       = db["dashboard_id"]
        db_name     = db.get("dashboard_name", db_id)
        db_category = db.get("dashboard_category", "ld_operations")
        category    = _CATEGORY_MAP.get(db_category, DashboardCategory.LEARNING_DEV)

        for m in db.get("metrics", []):
            metric_type = m.get("type", "count")
            chart_type  = m.get("chart_type", "kpi_card")
            sources     = m.get("sources", [])

            focus_areas = _infer_focus_areas(
                m.get("name", "") + " " + m.get("section", ""),
                category,
            )

            # Derive metric_profile from individual metric type
            profile_raw = _METRIC_TYPE_TO_PROFILE.get(metric_type, MetricProfile.MIXED)

            # Good direction heuristic
            name_lower = m.get("name", "").lower()
            good_dir = "up"
            if any(w in name_lower for w in ("overdue", "failed", "error", "breach", "incident")):
                good_dir = "down"
            elif any(w in name_lower for w in ("completion", "coverage", "compliance")):
                good_dir = "up"

            em = EnrichedMetric(
                metric_id=f"{db_id}:{m['id']}",
                dashboard_id=db_id,
                dashboard_name=db_name,
                dashboard_category=db_category,
                name=m.get("name", m["id"]),
                metric_type=metric_type,
                unit=m.get("unit") or "",
                chart_type=chart_type,
                section=m.get("section") or "",
                metric_profile=profile_raw,
                category=category,
                focus_areas=focus_areas,
                source_capabilities=_map_source_capabilities(sources),
                source_schemas=[],   # not present in source; populated by schema ETL
                kpis=[],
                threshold_warning=None,
                threshold_critical=None,
                good_direction=good_dir,
                axis_label=m.get("unit") or "",
                aggregation="sum" if metric_type == "count" else "avg",
                display_name=m.get("name", m["id"]),
                content_hash=_sha256(m),
            )
            em.embedding_text = _build_embedding_text_metric(em)
            metrics.append(em)

    logger.info(f"lms_metrics: {len(metrics)} metrics enriched")
    return metrics


# ═══════════════════════════════════════════════════════════════════════
# DECISION TREE BUILDER — synthesised from all enriched templates
# ═══════════════════════════════════════════════════════════════════════

def build_decision_tree(
    templates: list[EnrichedTemplate],
    metrics:   list[EnrichedMetric],
) -> DecisionTree:
    """
    Build the generic decision tree from the enriched corpus.
    Derives option sets dynamically from actual registry data.
    """

    # ── Q1: Category — derived from actual categories in registry ─────
    category_counts: dict[str, int] = {}
    for t in templates:
        category_counts[t.category.value] = category_counts.get(t.category.value, 0) + 1

    category_keywords = {
        "compliance_audit":   ["soc2", "hipaa", "nist", "audit", "controls", "compliance", "iam", "cloud audit"],
        "security_operations":["incident", "threat", "vulnerability", "siem", "detection", "alert", "endpoint", "network", "dns"],
        "learning_development":["training", "completion", "lms", "course", "learner", "cornerstone", "csod", "l&d"],
        "hr_workforce":       ["onboarding", "headcount", "attrition", "workforce", "employee", "workday"],
        "risk_management":    ["risk", "exposure", "vendor", "third-party", "grc", "posture"],
        "executive_reporting":["board", "executive", "summary", "leadership", "ciso", "kpi rollup"],
        "data_operations":    ["pipeline", "etl", "dbt", "data quality", "freshness", "schema", "siem ops"],
        "cross_domain":       ["hybrid", "unified", "multi-framework", "integrated"],
    }
    q1_options = []
    for cat_val, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        q1_options.append(DecisionOption(
            option_id=cat_val,
            label=cat_val.replace("_", " ").title(),
            keywords=category_keywords.get(cat_val, [cat_val]),
            maps_to={"category": cat_val, "registry_source": _registry_for_category(cat_val)},
            confidence=0.9,
            tags=["primary"],
        ))

    q1 = DecisionQuestion(
        question_id="category",
        question="What is the primary domain or purpose of this dashboard?",
        field="category",
        options=q1_options,
        auto_resolve_from="goal_statement",
        resolution_priority=1,
    )

    # ── Q2: Focus Area — from enriched template focus_areas corpus ────
    all_focus = {}
    for t in templates:
        for fa in t.focus_areas:
            all_focus[fa] = all_focus.get(fa, 0) + 1
    focus_keywords = {
        "vulnerability_management": ["vulnerability", "vuln", "cve", "patch", "cvss"],
        "incident_response":        ["incident", "alert", "case", "response", "triage"],
        "threat_detection":         ["threat", "detection", "malware", "rule", "signal"],
        "asset_inventory":          ["endpoint", "host", "network", "cloud", "asset"],
        "access_control":           ["iam", "identity", "access", "privilege", "certification"],
        "audit_logging":            ["audit", "log", "event", "siem", "trail"],
        "change_management":        ["change", "configuration", "drift", "policy"],
        "data_protection":          ["data", "dlp", "encryption", "privacy"],
        "training_completion":      ["training", "completion", "assignment", "overdue"],
        "learner_engagement":       ["learner", "engagement", "login", "active user"],
        "content_effectiveness":    ["course", "content", "curriculum", "effectiveness"],
        "pipeline_health":          ["pipeline", "etl", "data quality", "freshness"],
        "vendor_risk":              ["vendor", "third-party", "supplier", "partner"],
        "risk_exposure":            ["risk", "exposure", "posture", "score"],
    }
    q2_options = []
    for fa, count in sorted(all_focus.items(), key=lambda x: -x[1]):
        q2_options.append(DecisionOption(
            option_id=fa,
            label=fa.replace("_", " ").title(),
            keywords=focus_keywords.get(fa, [fa.replace("_", " ")]),
            maps_to={"focus_area": fa},
            confidence=0.85,
        ))
    q2 = DecisionQuestion(
        question_id="focus_area",
        question="What is the primary focus area within that domain?",
        field="focus_area",
        options=q2_options,
        auto_resolve_from="suggested_focus_areas",
        resolution_priority=2,
    )

    # ── Q3: Metric Profile — deterministic, all options always present ─
    q3_options = [
        DecisionOption(option_id=p.value, label=p.value.replace("_", " ").title(),
                       keywords=_metric_profile_keywords(p),
                       maps_to={"metric_profile": p.value}, confidence=1.0, tags=["deterministic"])
        for p in MetricProfile
    ]
    q3 = DecisionQuestion(
        question_id="metric_profile",
        question="What types of metrics dominate this dataset?",
        field="metric_profile",
        options=q3_options,
        auto_resolve_from="metrics",
        resolution_priority=3,
    )

    # ── Q4: Audience ──────────────────────────────────────────────────
    all_audience: dict[str, int] = {}
    for t in templates:
        for a in t.audience_levels:
            all_audience[a.value] = all_audience.get(a.value, 0) + 1
    audience_keywords = {
        "security_ops":    ["security team", "analyst", "soc", "engineer"],
        "soc_analyst":     ["soc analyst", "tier 1", "tier 2", "incident responder"],
        "compliance_team": ["compliance", "auditor", "grc", "controls"],
        "executive_board": ["ciso", "board", "vp", "leadership", "executive"],
        "risk_management": ["risk", "vendor", "third-party"],
        "learning_admin":  ["l&d", "training admin", "lms admin", "hr"],
        "data_engineer":   ["data engineer", "pipeline", "etl"],
    }
    q4_options = []
    for aud_val, count in sorted(all_audience.items(), key=lambda x: -x[1]):
        q4_options.append(DecisionOption(
            option_id=aud_val,
            label=aud_val.replace("_", " ").title(),
            keywords=audience_keywords.get(aud_val, [aud_val]),
            maps_to={"audience": aud_val},
            confidence=0.8,
        ))
    q4 = DecisionQuestion(
        question_id="audience",
        question="Who is the primary audience for this dashboard?",
        field="audience",
        options=q4_options,
        auto_resolve_from="persona",
        resolution_priority=4,
    )

    # ── Q5: Complexity ────────────────────────────────────────────────
    q5_options = [
        DecisionOption(option_id="low",    label="Summary / Overview",
                       keywords=["summary", "overview", "exec", "kpi only"],
                       maps_to={"complexity": "low", "max_panels": 2}, confidence=0.9),
        DecisionOption(option_id="medium", label="Standard",
                       keywords=["standard", "operational", "regular"],
                       maps_to={"complexity": "medium", "max_panels": 4}, confidence=0.9),
        DecisionOption(option_id="high",   label="Full Detail",
                       keywords=["detailed", "full", "analyst", "deep dive", "all metrics"],
                       maps_to={"complexity": "high", "max_panels": 6}, confidence=0.9),
    ]
    q5 = DecisionQuestion(
        question_id="complexity",
        question="How much detail is required?",
        field="complexity",
        options=q5_options,
        auto_resolve_from="audience",
        resolution_priority=5,
    )

    # ── Q6: Destination Type ──────────────────────────────────────────
    q6_options = [
        DecisionOption(option_id="embedded",    label="Embedded (ECharts / React)",
                       keywords=["embedded", "echarts", "react", "web app", "platform"],
                       maps_to={"destination_type": "embedded"}, confidence=1.0),
        DecisionOption(option_id="powerbi",     label="Power BI",
                       keywords=["powerbi", "power bi", "pbix", "dax"],
                       maps_to={"destination_type": "powerbi"}, confidence=1.0),
        DecisionOption(option_id="simple",      label="Simple / Static HTML",
                       keywords=["simple", "static", "html", "pdf", "email"],
                       maps_to={"destination_type": "simple"}, confidence=1.0),
        DecisionOption(option_id="slack_digest",label="Slack / Email Digest",
                       keywords=["slack", "email", "digest", "notification", "message"],
                       maps_to={"destination_type": "slack_digest"}, confidence=1.0),
        DecisionOption(option_id="api_json",    label="API / JSON Export",
                       keywords=["api", "json", "headless", "export", "integration"],
                       maps_to={"destination_type": "api_json"}, confidence=1.0),
    ]
    q6 = DecisionQuestion(
        question_id="destination_type",
        question="Where will the dashboard be rendered or delivered?",
        field="destination_type",
        options=q6_options,
        auto_resolve_from="output_format",
        resolution_priority=0,   # resolved first — gates all template filtering
    )

    # ── Q7: Interaction Mode ──────────────────────────────────────────
    q7_options = [
        DecisionOption(option_id="drill_down",       label="Interactive Drill-Down",
                       keywords=["drill", "click", "filter", "explore", "interactive"],
                       maps_to={"interaction_mode": "drill_down"}, confidence=0.85),
        DecisionOption(option_id="read_only",        label="Read-Only View",
                       keywords=["read only", "view only", "no interaction", "static"],
                       maps_to={"interaction_mode": "read_only"}, confidence=0.85),
        DecisionOption(option_id="real_time",        label="Real-Time / Live",
                       keywords=["real time", "live", "streaming", "< 5 min", "realtime"],
                       maps_to={"interaction_mode": "real_time"}, confidence=0.9),
        DecisionOption(option_id="scheduled_report", label="Scheduled Report",
                       keywords=["scheduled", "daily report", "weekly report", "digest"],
                       maps_to={"interaction_mode": "scheduled_report"}, confidence=0.9),
    ]
    q7 = DecisionQuestion(
        question_id="interaction_mode",
        question="How will users interact with the dashboard?",
        field="interaction_mode",
        options=q7_options,
        auto_resolve_from="timeframe",
        resolution_priority=6,
    )

    # ── Registry targets ──────────────────────────────────────────────
    registry_targets = {
        "compliance_audit":    "dashboard_registry",
        "security_operations": "dashboard_registry",
        "learning_development":"ld_templates_registry",
        "hr_workforce":        "ld_templates_registry",
        "risk_management":     "dashboard_registry",
        "executive_reporting": "dashboard_registry",
        "data_operations":     "dashboard_registry",
        "cross_domain":        "both",
    }

    # ── Destination gates ─────────────────────────────────────────────
    destination_gates = {
        "embedded":    {"allowed_all": True},
        "powerbi":     {"excluded_primitives": ["chat_panel", "causal_graph", "heatmap_calendar", "sankey", "treemap"]},
        "simple":      {"allowed_primitives":  ["kpi_strip", "bar", "line", "table"], "max_panels": 2},
        "slack_digest":{"allowed_primitives":  ["kpi_strip"], "max_kpi_cells": 6},
        "api_json":    {"emit_metric_spec_only": True},
    }

    # ── Destination defaults ──────────────────────────────────────────
    defaults = {
        "embedded":    {"category": "security_operations", "audience": "security_ops",   "complexity": "medium"},
        "powerbi":     {"category": "executive_reporting",  "audience": "executive_board","complexity": "low"},
        "simple":      {"category": "compliance_audit",     "audience": "compliance_team","complexity": "low"},
        "slack_digest":{"category": "executive_reporting",  "audience": "executive_board","complexity": "low"},
        "api_json":    {},
    }

    return DecisionTree(
        version="1.0.0",
        questions=[q6, q1, q2, q3, q4, q5, q7],  # Q6 first — destination gate
        registry_targets=registry_targets,
        destination_gates=destination_gates,
        defaults=defaults,
        built_at=datetime.now(timezone.utc).isoformat(),
    )


def _registry_for_category(cat: str) -> str:
    return {
        "learning_development": "ld_templates_registry",
        "hr_workforce":         "ld_templates_registry",
        "cross_domain":         "both",
    }.get(cat, "dashboard_registry")


def _metric_profile_keywords(p: MetricProfile) -> list[str]:
    return {
        MetricProfile.COUNT_HEAVY:  ["count", "total", "number of", "quantity"],
        MetricProfile.TREND_HEAVY:  ["trend", "over time", "time series", "historical"],
        MetricProfile.RATE_PCT:     ["percentage", "rate", "ratio", "compliance %"],
        MetricProfile.COMPARISON:   ["comparison", "distribution", "ranking", "breakdown"],
        MetricProfile.MIXED:        ["mixed", "varied", "multiple types"],
        MetricProfile.SCORECARD:    ["scorecard", "kpi", "summary card", "single value"],
    }.get(p, [p.value])

"""
CCE Layout Advisor — LangGraph Tools
=====================================
Tools callable by the LLM agent during the layout conversation.
These are bound to the agent node so the LLM can:
  1. Search templates by semantic similarity
  2. Score templates against accumulated decisions
  3. Get template details
  4. Generate the final layout spec
  5. Apply customizations to an existing spec
"""

from __future__ import annotations
import json
from typing import Optional

from langchain_core.tools import tool

from .templates import TEMPLATES, CATEGORIES, DECISION_TREE
from app.services.dashboard_template_vector_store import score_templates_hybrid, ALL_TEMPLATES
from .taxonomy_matcher import (
    get_domain_recommendations,
    match_domain_from_metrics,
    expand_use_case_group,
    join_control_anchors,
    match_use_case_group,
    map_metric_widget_to_chart,
    match_metric_to_gold_table,
    get_taxonomy_slice_for_prompt,
)


# ═══════════════════════════════════════════════════════════════════════
# TOOL 1: Search Templates (semantic — requires vector store in state)
# ═══════════════════════════════════════════════════════════════════════

@tool
def search_templates(query: str, k: int = 5) -> str:
    """
    Semantic search across the template registry via DashboardTemplateRetrievalService.
    Use when the user describes what they need in natural language.
    
    Args:
        query: Natural language description of the dashboard need
        k: Number of results to return (default 5)
    
    Returns:
        JSON array of matching templates with scores.
    """
    from .retrieval import retrieve_similar_templates

    boosts = retrieve_similar_templates(query, k=k)
    if not boosts:
        results = []
        query_lower = query.lower()
        for tid, tpl in ALL_TEMPLATES.items():
            name_match = query_lower in (tpl.get("name") or "").lower()
            desc_match = query_lower in (tpl.get("description") or "").lower()
            if name_match or desc_match:
                results.append({
                    "template_id": tid,
                    "name": tpl.get("name"),
                    "score": 10 if name_match else 5,
                    "similarity": None,
                    "description": tpl.get("description"),
                    "category": tpl.get("category"),
                    "domains": tpl.get("domains", []),
                    "complexity": tpl.get("complexity"),
                    "source": "keyword_fallback",
                })
        return json.dumps(results[:k], indent=2)

    results = []
    for boost in boosts:
        tid = boost["template_id"]
        tpl = ALL_TEMPLATES.get(tid) or TEMPLATES.get(tid)
        if not tpl:
            continue
        results.append({
            "template_id": tid,
            "name": tpl.get("name"),
            "score": boost["boost"],
            "similarity": boost["similarity"],
            "description": tpl.get("description"),
            "category": tpl.get("category"),
            "domains": tpl.get("domains", []),
            "complexity": tpl.get("complexity"),
            "has_chat": tpl.get("has_chat"),
            "strip_cells": tpl.get("strip_cells"),
            "best_for": tpl.get("best_for", []),
            "source": "vector_store",
        })
    return json.dumps(results, indent=2)


# ═══════════════════════════════════════════════════════════════════════
# TOOL 2: Score Templates (rule-based + optional vector boost)
# ═══════════════════════════════════════════════════════════════════════

@tool
def score_templates(
    decisions: dict,
    resolution_payload: Optional[dict] = None,
    goal_statement: Optional[str] = None,
    output_format: Optional[str] = None,
    metrics: Optional[list] = None,
) -> str:
    """
    Score templates against user decisions. Prefers the 7-question dashboard
    decision tree (destination gate + vector-store templates) when possible.
    Falls back to hybrid scoring.
    
    Args:
        decisions: Dict with category, domain, theme, complexity, has_chat, strip_cells,
                   destination_type, interaction_mode, metric_profile (decision tree)
        resolution_payload: Optional BIND output with control_anchors, focus_areas
        goal_statement: Optional query for vector-store retrieval
        output_format: Optional target (echarts->embedded, powerbi, simple, etc.)
        metrics: Optional list for metric_profile resolution
    
    Returns:
        JSON array of top 5 templates with scores and match reasons.
    """
    # Try dashboard decision tree flow when we have enough context
    try:
        from app.agents.decision_trees.dashboard.dashboard_decision_tree_service import (
            DashboardDecisionTreeService,
        )
        from app.agents.decision_trees.dashboard.dashboard_decision_tree import resolve_decisions
        from app.agents.decision_trees.dashboard.dt_dashboard_decision_nodes import (
            enrich_dashboard_with_decision_tree,
        )
    except ImportError:
        pass
    else:
        query = goal_statement or decisions.get("domain", "") or "dashboard"
        dest = output_format or decisions.get("output_format", "echarts")
        dest_map = {"echarts": "embedded", "powerbi": "powerbi", "html": "simple"}
        dest = dest_map.get((dest or "").lower(), "embedded")

        dt_state = {
            "user_query": query,
            "intent": query,
            "output_format": dest,
            "persona": decisions.get("audience", ""),
            "framework_id": (decisions.get("framework") or "").lower(),
            "timeframe": "monthly",
            "selected_data_sources": resolution_payload.get("data_sources", []) if resolution_payload else [],
            "data_enrichment": {},
            "resolved_metrics": metrics or [],
            "metrics": metrics or [],
        }
        try:
            service = DashboardDecisionTreeService()
            ctx = service.search_all(query=query, templates_limit=15, destination_filter=dest)
            dt_state.update(ctx.to_state_payload())
            if dt_state.get("dt_enriched_templates"):
                enrich_dashboard_with_decision_tree(dt_state)
                candidates = dt_state.get("dt_template_candidates", [])[:5]
                results = [
                    {
                        "template_id": c.get("template_id", ""),
                        "name": c.get("name", ""),
                        "score": int((c.get("composite_score", 0) or 0) * 100),
                        "reasons": ["decision_tree_match"],
                        "description": c.get("description", ""),
                        "category": c.get("category", ""),
                        "complexity": c.get("complexity", "medium"),
                        "has_chat": c.get("has_chat", False),
                        "strip_cells": c.get("strip_cells", 0),
                    }
                    for c in candidates
                ]
                return json.dumps(results, indent=2)
        except Exception:
            pass

    # Legacy: score_templates_hybrid
    ranked = score_templates_hybrid(decisions)
    top5 = ranked[:5]
    results = []
    for tid, score, reasons in top5:
        tpl = ALL_TEMPLATES.get(tid) or TEMPLATES.get(tid, {})
        results.append({
            "template_id": tid,
            "name": tpl.get("name", tid),
            "score": score,
            "reasons": reasons,
            "description": tpl.get("description", ""),
            "category": tpl.get("category"),
            "complexity": tpl.get("complexity"),
            "has_chat": tpl.get("has_chat"),
            "strip_cells": tpl.get("strip_cells"),
        })
    return json.dumps(results, indent=2)


# ═══════════════════════════════════════════════════════════════════════
# TOOL 3: Get Template Detail
# ═══════════════════════════════════════════════════════════════════════

@tool
def get_template_detail(template_id: str) -> str:
    """
    Get the full specification of a specific template by ID.
    Use after scoring to present detailed information about 
    a recommended template.
    
    Args:
        template_id: The template ID (e.g. "command-center", "risk-register")
    
    Returns:
        Full template JSON or error message.
    """
    tpl = ALL_TEMPLATES.get(template_id) or TEMPLATES.get(template_id)
    if not tpl:
        return json.dumps({"error": f"Template '{template_id}' not found. Available: {list(ALL_TEMPLATES.keys())}"})
    return json.dumps(tpl, indent=2, default=str)


# ═══════════════════════════════════════════════════════════════════════
# TOOL 4: Generate Layout Spec
# ═══════════════════════════════════════════════════════════════════════

@tool
def generate_layout_spec(
    template_id: str,
    decisions: dict,
    customizations: Optional[dict] = None,
) -> str:
    """
    Generate the final layout_spec JSON from a selected template + decisions.
    This is the output that the downstream renderer consumes.
    
    Args:
        template_id: Selected template ID
        decisions: All accumulated decisions from the conversation
        customizations: Optional overrides (strip_kpis, filters, theme, etc.)
    
    Returns:
        Complete layout_spec JSON ready for the renderer.
    """
    tpl = ALL_TEMPLATES.get(template_id) or TEMPLATES.get(template_id)
    if not tpl:
        return json.dumps({"error": f"Template '{template_id}' not found"})

    # Build base spec
    spec = {
        "template_id": template_id,
        "template_name": tpl["name"],
        "template_icon": tpl.get("icon", ""),
        "category": tpl["category"],
        "category_label": CATEGORIES.get(tpl["category"], {}).get("label", ""),

        # Structure
        "primitives": tpl["primitives"],
        "panels": tpl["panels"],

        # Theme
        "theme": decisions.get("theme") or (
            "dark" if "dark" in tpl.get("theme_hint", "") else "light"
        ),

        # KPI Strip
        "strip_cells": tpl["strip_cells"],
        "strip_kpis": tpl.get("strip_example", []),

        # Features
        "has_chat": tpl["has_chat"],
        "has_causal_graph": tpl.get("has_graph", False),
        "has_filters": tpl.get("has_filters", False),

        # Card anatomy
        "card_anatomy": tpl.get("card_anatomy", {}),

        # Filters
        "filters": _default_filters(tpl, decisions),

        # Detail sections (parsed from center panel config)
        "detail_sections": tpl["panels"].get("center", "").split(" + "),

        # Domain & complexity
        "domain": decisions.get("domain", tpl["domains"][0] if tpl["domains"] else "security"),
        "complexity": tpl["complexity"],

        # Metadata
        "decisions_applied": decisions,
        "best_for": tpl["best_for"],
        "domains": tpl["domains"],
    }

    # Apply customizations
    if customizations:
        if "strip_kpis" in customizations:
            spec["strip_kpis"] = customizations["strip_kpis"]
            spec["strip_cells"] = len(customizations["strip_kpis"])
        if "filters" in customizations:
            spec["filters"] = customizations["filters"]
        if "theme" in customizations:
            spec["theme"] = customizations["theme"]
        if "panels" in customizations:
            spec["panels"] = {**spec["panels"], **customizations["panels"]}
        if "has_chat" in customizations:
            spec["has_chat"] = customizations["has_chat"]
        if "detail_sections" in customizations:
            spec["detail_sections"] = customizations["detail_sections"]
        if "card_anatomy" in customizations:
            spec["card_anatomy"] = {**spec["card_anatomy"], **customizations["card_anatomy"]}

    return json.dumps(spec, indent=2, default=str)


def _default_filters(tpl: dict, decisions: dict) -> list[str]:
    """Pick default filter chips based on domain."""
    domain = decisions.get("domain", "security")
    domain_filters = {
        "security":     ["All", "Critical", "High", "Medium", "Low"],
        "cornerstone":  ["All", "Overdue", "In Progress", "Completed", "Not Started"],
        "workday":      ["All", "Open", "In Review", "Approved", "Closed"],
        "hybrid":       ["All", "Failing", "Degraded", "Passing", "Not Evaluated"],
        "data_ops":     ["All", "Failed", "Running", "Succeeded", "Scheduled"],
    }
    if tpl.get("has_filters"):
        return domain_filters.get(domain, domain_filters["security"])
    return []


# ═══════════════════════════════════════════════════════════════════════
# TOOL 5: Bind Metric Groups (BIND stage)
# ═══════════════════════════════════════════════════════════════════════

@tool
def bind_metric_groups(use_case_group: str, complexity: str) -> str:
    """
    Expand a use_case_group into required/optional metric groups.
    Loads from metric_use_case_groups.json and applies complexity gating.
    
    Args:
        use_case_group: e.g. "soc2_audit", "lms_learning_target"
        complexity: "low" | "medium" | "high"
    
    Returns:
        JSON with required_groups, optional_included, timeframe, audience.
    """
    result = expand_use_case_group(use_case_group, complexity)
    return json.dumps(result, indent=2)


# ═══════════════════════════════════════════════════════════════════════
# TOOL 6: Bind Control Anchors (BIND stage)
# ═══════════════════════════════════════════════════════════════════════

@tool
def bind_control_anchors(focus_areas: list[str], framework: str) -> str:
    """
    Join focus_areas against control_domain_taxonomy for a given framework.
    Returns the matched control anchors with their risk_categories.
    
    Args:
        focus_areas: e.g. ["training_compliance", "access_control"]
        framework: "soc2" | "hipaa" | "nist_ai_rmf"
    
    Returns:
        JSON array of matched control_anchor dicts.
    """
    anchors = join_control_anchors(focus_areas, framework)
    return json.dumps(anchors, indent=2)


# ═══════════════════════════════════════════════════════════════════════
# TOOL 7: Apply Adjustment Handle (VERIFY stage — replaces apply_customization)
# ═══════════════════════════════════════════════════════════════════════

@tool
def apply_adjustment_handle(
    current_spec: dict,
    handle: dict,
    resolution_payload: Optional[dict] = None,
) -> str:
    """
    Apply a pre-computed adjustment handle to a pending spec.
    Returns the updated spec AND a human-readable diff summary.
    
    Args:
        current_spec: The current pending spec dict
        handle: AdjustmentHandle dict (id, delta, re_triggers)
        resolution_payload: For context when re_triggers != "none"
    
    Returns:
        JSON with {updated_spec, diff_summary, re_triggers}.
    """
    delta = handle.get("delta", {})
    updated = {**current_spec}
    for key, value in delta.items():
        if isinstance(value, dict) and isinstance(updated.get(key), dict):
            updated[key] = {**updated.get(key, {}), **value}
        else:
            updated[key] = value
    diff_summary = f"Applied handle: {handle.get('label', handle.get('id', 'unknown'))}"
    return json.dumps({
        "updated_spec": updated,
        "diff_summary": diff_summary,
        "re_triggers": handle.get("re_triggers", "none"),
    }, indent=2, default=str)


# ═══════════════════════════════════════════════════════════════════════
# TOOL 8: List Available Templates
# ═══════════════════════════════════════════════════════════════════════

@tool
def list_templates(category: Optional[str] = None) -> str:
    """
    List all available templates, optionally filtered by category.
    
    Args:
        category: Optional category filter (operations, executive, 
                  hr_learning, cross_domain, data_ops, grc, iam, compliance)
    
    Returns:
        JSON array of template summaries.
    """
    results = []
    for tid, tpl in ALL_TEMPLATES.items():
        if category and tpl["category"] != category:
            continue
        results.append({
            "id": tid,
            "name": tpl["name"],
            "icon": tpl.get("icon", ""),
            "category": tpl["category"],
            "description": tpl["description"][:120] + "…",
            "complexity": tpl["complexity"],
            "domains": tpl["domains"],
        })
    return json.dumps(results, indent=2)


# ═══════════════════════════════════════════════════════════════════════
# TOOL 9: Match Domain from Metrics (Taxonomy-Based)
# ═══════════════════════════════════════════════════════════════════════

@tool
def match_domain_from_metrics_tool(
    metrics: list[dict],
    kpis: list[dict],
    use_case: Optional[str] = None,
    data_sources: Optional[list[str]] = None,
) -> str:
    """
    Match metrics and KPIs to dashboard domains using the enriched taxonomy.
    This helps identify which dashboard domain best fits the provided metrics.
    
    Use this tool when you have metrics/KPIs from upstream context and want
    to determine the appropriate dashboard domain before scoring templates.
    
    Args:
        metrics: List of metric dicts with 'name', 'type', 'source_table', etc.
        kpis: List of KPI dicts with 'label', 'value_expr', etc.
        use_case: Optional use case string (e.g., "SOC2 monitoring", "training compliance")
        data_sources: Optional list of data sources (e.g., ["siem", "cornerstone", "lms"])
    
    Returns:
        JSON with top domain matches, recommended domain, and suggested decisions.
    """
    recommendations = get_domain_recommendations(
        metrics=metrics,
        kpis=kpis,
        use_case=use_case,
        data_sources=data_sources,
        top_k=3,
    )
    return json.dumps(recommendations, indent=2)


# ═══════════════════════════════════════════════════════════════════════
# TOOL 10: Bind Metrics to Layout (BIND stage — goal-driven path)
# ═══════════════════════════════════════════════════════════════════════

@tool
def bind_metrics_to_layout(
    metric_recommendations: list,
    gold_model_sql: list,
    goal_statement: str = "",
    output_format: str = "echarts",
) -> str:
    """
    Map metric recommendations to gold tables and chart types for layout generation.
    Use when upstream provides metric_recommendations and gold_model_sql.
    Returns metric_gold_model_bindings and recommended layout for VERIFY.

    Args:
        metric_recommendations: List of metric dicts (id, name, widget_type, kpi_value_type, ...)
        gold_model_sql: List of gold table dicts (name, sql_query, expected_columns)
        goal_statement: User goal that drove the metrics
        output_format: "echarts" | "powerbi" | "other"

    Returns:
        JSON with metric_gold_model_bindings, recommended_template_id, strip_cells, panel_layout, rationale.
    """
    bindings = []
    for m in metric_recommendations:
        gold_table = match_metric_to_gold_table(m, gold_model_sql)
        chart_type = map_metric_widget_to_chart(
            m.get("widget_type", "trend_line"),
            m.get("kpi_value_type"),
            m.get("metrics_intent"),
        )
        bindings.append({
            "metric_id": m.get("id", ""),
            "metric_name": m.get("name", ""),
            "gold_table_name": gold_table or "",
            "chart_type": chart_type,
            "strip_cell": m.get("kpi_value_type") in ("count", "percentage") and not m.get("parent_metric_id"),
        })
    # Default template when metrics suggest operational/vuln domain
    recommended = "command-center"
    strip_cells = [b["metric_id"] for b in bindings[:8] if b.get("strip_cell")]
    return json.dumps({
        "metric_gold_model_bindings": bindings,
        "recommended_template_id": recommended,
        "strip_cells": strip_cells[:8],
        "panel_layout": {"left": [], "center": [b["metric_id"] for b in bindings], "right": []},
        "rationale": f"Layout for {len(metric_recommendations)} metrics from goal: {goal_statement}. Output: {output_format}.",
    }, indent=2)


# ═══════════════════════════════════════════════════════════════════════
# TOOL 11: Fetch Data Tables (human-in-the-loop — dummy implementation)
# ═══════════════════════════════════════════════════════════════════════
# Replace with real data-fetching tool in production.

_DUMMY_TABLES = [
    {
        "table_id": "dummy_vulnerability_snapshot",
        "name": "Vulnerability Snapshot (dummy)",
        "description": "Daily snapshot of open vulnerabilities by host and severity",
        "columns": ["host_id", "severity", "count", "snapshot_date"],
        "suggested_chart_type": "line_basic",
        "source": "qualys",
    },
    {
        "table_id": "dummy_agent_coverage",
        "name": "Agent Coverage (dummy)",
        "description": "Weekly agent/detection coverage percentage by organization",
        "columns": ["organization_id", "coverage_pct", "week_start"],
        "suggested_chart_type": "gauge",
        "source": "qualys",
    },
    {
        "table_id": "dummy_backlog_trend",
        "name": "Backlog Trend (dummy)",
        "description": "90-day open vulnerability backlog trend",
        "columns": ["snapshot_date", "open_count", "avg_days_open"],
        "suggested_chart_type": "line_basic",
        "source": "qualys",
    },
    {
        "table_id": "dummy_snyk_issues",
        "name": "Snyk Issues (dummy)",
        "description": "High-CVSS Snyk issues by language and package",
        "columns": ["issue_language", "issue_package", "count_high_cvss_week", "week_start"],
        "suggested_chart_type": "bar_grouped",
        "source": "snyk",
    },
]


@tool
def fetch_data_tables(user_question: str, context: Optional[str] = None) -> str:
    """
    Fetch data tables matching a user's natural language question.
    Human-in-the-loop: user asks "add vulnerability data" or "include agent coverage"
    and this tool returns matching table descriptions to add to the dashboard.

    DUMMY IMPLEMENTATION: Returns static table descriptions. Replace with real
    data catalog / schema discovery tool in production.

    Args:
        user_question: Natural language question, e.g. "add vulnerability metrics",
                       "include agent coverage", "show me backlog trend"
        context: Optional context (goal, domain) to narrow results

    Returns:
        JSON array of table dicts: [{table_id, name, description, columns, suggested_chart_type}]
    """
    q = (user_question or "").lower()
    matches = []
    keywords_map = {
        "vulnerability": ["dummy_vulnerability_snapshot"],
        "vuln": ["dummy_vulnerability_snapshot"],
        "agent": ["dummy_agent_coverage"],
        "coverage": ["dummy_agent_coverage"],
        "backlog": ["dummy_backlog_trend"],
        "trend": ["dummy_backlog_trend"],
        "snyk": ["dummy_snyk_issues"],
        "cvss": ["dummy_snyk_issues"],
        "issue": ["dummy_snyk_issues"],
    }
    seen = set()
    for kw, table_ids in keywords_map.items():
        if kw in q:
            for tid in table_ids:
                if tid not in seen:
                    seen.add(tid)
                    t = next((x for x in _DUMMY_TABLES if x["table_id"] == tid), None)
                    if t:
                        matches.append(t)
    if not matches:
        matches = _DUMMY_TABLES[:2]
    return json.dumps(matches, indent=2)


# ── Collect all tools for binding to agent ────────────────────────────

LAYOUT_TOOLS = [
    search_templates,
    score_templates,
    get_template_detail,
    generate_layout_spec,
    bind_metric_groups,
    bind_control_anchors,
    apply_adjustment_handle,
    list_templates,
    match_domain_from_metrics_tool,
    bind_metrics_to_layout,
    fetch_data_tables,
]

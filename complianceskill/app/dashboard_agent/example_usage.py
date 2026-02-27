"""
CCE Layout Advisor — Example Usage
====================================
Demonstrates the full conversation flow for both:
1. Rule-based graph (deterministic, fast)
2. LLM-powered graph (natural language, flexible)

Run: python example_usage.py
"""

import json
from .runner import LayoutAdvisorSession


def demo_rule_based():
    """
    Demo: Rule-based layout advisor conversation.
    Shows the full flow from intake → spec generation.
    """
    print("=" * 72)
    print("  CCE LAYOUT ADVISOR — Rule-Based Demo")
    print("=" * 72)

    # ── 1. Create session ─────────────────────────────────────────────
    session = LayoutAdvisorSession()

    # ── 2. Start with upstream context ────────────────────────────────
    # This simulates what the upstream metric/KPI agents would provide
    upstream = {
        "use_case": "SOC2 compliance monitoring",
        "data_sources": ["siem", "cornerstone"],
        "persona": "Compliance Analyst",
        "metrics": [
            {"name": "control_pass_rate", "type": "percentage", "source_table": "controls"},
            {"name": "evidence_completeness", "type": "percentage", "source_table": "evidence"},
            {"name": "days_to_audit", "type": "integer", "source_table": "audits"},
        ],
        "kpis": [
            {"label": "Overall Posture", "value_expr": "AVG(control_pass_rate)", "threshold": 80},
            {"label": "CC Families", "value_expr": "COUNT(DISTINCT family)", "threshold": None},
            {"label": "Controls Degraded", "value_expr": "COUNT(*) WHERE status='degraded'", "threshold": 5},
            {"label": "Evidence Complete", "value_expr": "AVG(evidence_completeness)", "threshold": 90},
            {"label": "Days to Audit", "value_expr": "MIN(days_to_audit)", "threshold": 30},
            {"label": "Critical Findings", "value_expr": "COUNT(*) WHERE severity='critical'", "threshold": 0},
        ],
        "tables": [
            {"name": "controls", "schema": "id, name, family, status, score", "row_count": 120},
            {"name": "evidence", "schema": "id, control_id, type, status, collected_at", "row_count": 450},
        ],
        "visuals": [
            {"type": "posture_strip", "metric": "overall_posture"},
            {"type": "list_cards", "metric": "controls"},
            {"type": "detail_sections", "metric": "control_detail"},
        ],
        "kpi_count": 6,
        "framework": "SOC2",
    }

    print("\n▶ Starting session with upstream context...")
    response = session.start(upstream)
    _print_response(response)

    # ── 3. Walk through decisions ─────────────────────────────────────
    # Some may be auto-resolved from upstream context

    responses = [
        "Monitor compliance posture",          # intent
        "Security tools",                       # systems (if not auto-resolved)
        "Compliance Analyst",                   # audience (if not auto-resolved)
        "Yes — contextual AI investigation",    # AI chat
        "5-6 KPIs",                             # KPI bar
    ]

    for user_msg in responses:
        if not response.needs_input:
            break
        if response.is_complete:
            break

        print(f"\n▶ User: {user_msg}")
        response = session.respond(user_msg)
        _print_response(response)

    # ── 4. Select template ────────────────────────────────────────────
    if response.recommended and not response.is_complete:
        selection = "1"  # Pick the top recommendation
        print(f"\n▶ User: {selection}")
        response = session.respond(selection)
        _print_response(response)

    # ── 5. Finalize ───────────────────────────────────────────────────
    if not response.is_complete:
        print("\n▶ User: looks good")
        response = session.respond("looks good")
        _print_response(response)

    # ── 6. Get final spec ─────────────────────────────────────────────
    if response.is_complete and response.layout_spec:
        print("\n" + "=" * 72)
        print("  FINAL LAYOUT SPEC")
        print("=" * 72)
        print(json.dumps(response.layout_spec, indent=2))


def demo_with_auto_resolve():
    """
    Demo: When upstream provides enough context to auto-resolve decisions.
    """
    print("\n\n" + "=" * 72)
    print("  CCE LAYOUT ADVISOR — Auto-Resolve Demo")
    print("=" * 72)

    session = LayoutAdvisorSession()

    # Rich upstream context that can auto-resolve everything
    upstream = {
        "use_case": "alert triage incident response",
        "data_sources": ["siem", "edr", "vuln_scanner"],
        "persona": "SOC Analyst",
        "has_chat_requirement": True,
        "kpi_count": 0,  # No KPI strip — maximize space
    }

    print("\n▶ Starting with fully resolvable context...")
    response = session.start(upstream)
    _print_response(response)

    # If all decisions auto-resolved, we skip to scoring
    if response.phase == "recommendation":
        print("\n✓ All decisions auto-resolved! Directly at recommendations.")

        # Select
        if response.recommended:
            print(f"\n▶ User: 1 (selecting: {response.recommended[0]['name']})")
            response = session.respond("1")
            _print_response(response)

        # Finalize
        if not response.is_complete:
            print("\n▶ User: looks good")
            response = session.respond("looks good")
            _print_response(response)

    if response.layout_spec:
        print("\n✓ Spec generated!")
        print(f"  Template: {response.layout_spec.get('template_name')}")
        print(f"  Theme: {response.layout_spec.get('theme')}")
        print(f"  Panels: {list(response.layout_spec.get('panels', {}).keys())}")


def demo_pipeline_integration():
    """
    Demo: How this fits into the larger CCE pipeline.
    Shows the data flowing from upstream agents → layout advisor → downstream.
    """
    print("\n\n" + "=" * 72)
    print("  CCE PIPELINE INTEGRATION DEMO")
    print("=" * 72)

    # ── Step 1: Simulate upstream agent outputs ────────────────────────
    print("\n[1] Upstream Agents Output:")

    metric_agent_output = {
        "metrics": [
            {"name": "control_pass_rate", "type": "pct", "source": "controls_table"},
            {"name": "evidence_count", "type": "int", "source": "evidence_table"},
            {"name": "risk_score", "type": "float", "source": "risk_register"},
        ]
    }
    print(f"    Metric Agent: {len(metric_agent_output['metrics'])} metrics identified")

    kpi_agent_output = {
        "kpis": [
            {"label": "Overall Posture", "expr": "AVG(control_pass_rate)"},
            {"label": "Open Risks", "expr": "COUNT(*) WHERE status='open'"},
            {"label": "Evidence %", "expr": "collected/total * 100"},
            {"label": "Days to Audit", "expr": "MIN(audit_date - NOW())"},
            {"label": "Critical Gaps", "expr": "COUNT(*) WHERE severity='critical'"},
        ]
    }
    print(f"    KPI Agent: {len(kpi_agent_output['kpis'])} KPIs defined")

    visual_agent_output = {
        "visuals": [
            {"type": "posture_strip"},
            {"type": "list_cards"},
            {"type": "causal_graph"},
            {"type": "detail_sections"},
        ]
    }
    print(f"    Visual Agent: {len(visual_agent_output['visuals'])} visual types")

    # ── Step 2: Compose upstream context ───────────────────────────────
    upstream_context = {
        **metric_agent_output,
        **kpi_agent_output,
        **visual_agent_output,
        "use_case": "SOC2 monitoring",
        "data_sources": ["siem"],
        "persona": "Compliance Analyst",
        "kpi_count": len(kpi_agent_output["kpis"]),
        "framework": "SOC2",
    }

    # ── Step 3: Run layout advisor ─────────────────────────────────────
    print("\n[2] Layout Advisor Agent:")
    session = LayoutAdvisorSession()
    response = session.start(upstream_context)
    print(f"    Phase: {response.phase}")
    print(f"    Auto-resolved decisions: {response.decisions_so_far}")

    # Quick run through remaining decisions
    auto_responses = ["compliance posture", "security", "compliance analyst", "yes", "5-6"]
    for msg in auto_responses:
        if not response.needs_input or response.is_complete:
            break
        response = session.respond(msg)

    if response.recommended:
        response = session.respond("1")
    if not response.is_complete:
        response = session.respond("looks good")

    print(f"    Selected: {response.selected_template}")
    print(f"    Spec generated: {response.is_complete}")

    # ── Step 4: Show what downstream renderer receives ─────────────────
    if response.layout_spec:
        spec = response.layout_spec
        print("\n[3] Downstream Renderer Receives:")
        print(f"    Template: {spec.get('template_name')}")
        print(f"    Primitives: {' → '.join(spec.get('primitives', []))}")
        print(f"    Theme: {spec.get('theme')}")
        print(f"    Panels: {list(spec.get('panels', {}).keys())}")
        print(f"    KPI Strip: {spec.get('strip_cells')} cells → {spec.get('strip_kpis', [])[:3]}")
        print(f"    Filters: {spec.get('filters', [])}")
        print(f"    Chat: {spec.get('has_chat')}")
        print(f"    Graph: {spec.get('has_causal_graph')}")


def _print_response(response):
    """Pretty-print an AdvisorResponse."""
    print(f"\n  Agent: {response.agent_message[:200]}{'...' if len(response.agent_message) > 200 else ''}")
    print(f"  Phase: {response.phase} | Complete: {response.is_complete} | Needs input: {response.needs_input}")
    if response.options:
        print(f"  Options: {response.options[:4]}{'...' if len(response.options) > 4 else ''}")
    if response.recommended:
        print(f"  Recommended: {[t['name'] for t in response.recommended]}")
    if response.decisions_so_far:
        print(f"  Decisions: {response.decisions_so_far}")


if __name__ == "__main__":
    demo_rule_based()
    demo_with_auto_resolve()
    demo_pipeline_integration()

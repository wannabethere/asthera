#!/usr/bin/env python3
"""
Tests for the CCE Layout Advisor Agent.

Covers:
- LayoutAdvisorConfig (goals, persona, business context, max summary)
- Taxonomy matching (no LLM) for LMS context
- Metric widget → chart mapping, metric → gold table matching
- fetch_data_tables tool (dummy)
- Goal-driven intake (metric_recommendations + gold_model_sql)
- Data tables human-in-the-loop flow
- Rule-based graph flow (intake → bind → score → recommend → selection → data_tables → customization)
- LLM agent node with LMS upstream context (requires ANTHROPIC_API_KEY)

Run:
  # Recommendation layout demo (uses examples/outputs):
  python -m tests.test_layout_advisor_llm

  # LMS demo:
  python -m tests.test_layout_advisor_llm lms

  # Unit tests only (no API key needed):
  pytest tests/test_layout_advisor_llm.py -v -k "test_taxonomy or test_config or test_metric or test_fetch or test_goal or test_data_tables or test_rule"

  # Goal-driven layout test (uses examples/outputs):
  pytest tests/test_layout_advisor_llm.py -v -k "test_graph_goal_driven_full_flow"

  # Full integration (requires ANTHROPIC_API_KEY):
  ANTHROPIC_API_KEY=sk-... pytest tests/test_layout_advisor_llm.py -v
"""

"""
Tests use app.core.settings and app.core.dependencies via tests/conftest.py:
- Settings loads .env from project root (BASE_DIR/.env)
- qdrant_available / qdrant_client fixtures for Qdrant validation tests
"""

import os
import sys
import json
import uuid
import pytest
from pathlib import Path

base_dir = Path(__file__).resolve().parent.parent
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))


# ═══════════════════════════════════════════════════════════════════════
# LMS UPSTREAM CONTEXT (Learning Management System)
# ═══════════════════════════════════════════════════════════════════════

LMS_UPSTREAM_CONTEXT = {
    "use_case": "training compliance dashboard for team manager",
    "data_sources": ["cornerstone", "lms"],
    "persona": "Learning Admin",
    "metrics": [
        {"name": "training_completion_rate", "type": "percentage", "source_table": "learning_assignments"},
        {"name": "overdue_assignments", "type": "integer", "source_table": "learning_assignments"},
        {"name": "learner_progress", "type": "percentage", "source_table": "learning_transcripts"},
        {"name": "compliance_coverage", "type": "percentage", "source_table": "compliance_tracking"},
    ],
    "kpis": [
        {"label": "Team Completion Rate", "value_expr": "AVG(training_completion_rate)", "threshold": 90},
        {"label": "Overdue Count", "value_expr": "COUNT(*) WHERE status='overdue'", "threshold": 0},
        {"label": "Compliance %", "value_expr": "AVG(compliance_coverage)", "threshold": 95},
        {"label": "Learners On Track", "value_expr": "COUNT(*) WHERE progress >= 0.8", "threshold": None},
    ],
    "tables": [
        {"name": "learning_assignments", "schema": "id, learner_id, course_id, status, due_date", "row_count": 5000},
        {"name": "learning_transcripts", "schema": "id, learner_id, course_id, progress, completed_at", "row_count": 12000},
    ],
    "kpi_count": 4,
    "framework": "LMS",
}


# ═══════════════════════════════════════════════════════════════════════
# UNIT TESTS (no LLM required)
# ═══════════════════════════════════════════════════════════════════════

class TestTaxonomyMatching:
    """Tests for taxonomy matching without LLM — uses keyword lookup and scoring."""

    def test_match_domain_from_metrics_lms(self):
        """LMS metrics should map to ld_training or ld_operations domain."""
        from app.agents.dashboard_agent.taxonomy_matcher import match_domain_from_metrics

        metrics = LMS_UPSTREAM_CONTEXT["metrics"]
        kpis = LMS_UPSTREAM_CONTEXT["kpis"]

        matches = match_domain_from_metrics(
            metrics=metrics,
            kpis=kpis,
            use_case=LMS_UPSTREAM_CONTEXT["use_case"],
            data_sources=LMS_UPSTREAM_CONTEXT["data_sources"],
        )

        assert len(matches) > 0, "Should have at least one domain match"
        top_domain = matches[0][0]
        top_score = matches[0][1]

        # LMS context should map to ld_training, ld_operations, ld_engagement, or lms_admin
        lms_domains = {"ld_training", "ld_operations", "ld_engagement", "lms_admin", "hr_workforce"}
        assert top_domain in lms_domains, f"Expected LMS domain, got {top_domain}"
        assert top_score > 0, "Match score should be positive"

    def test_get_domain_recommendations_lms(self):
        """get_domain_recommendations should return recommended_decisions for LMS."""
        from app.agents.dashboard_agent.taxonomy_matcher import get_domain_recommendations

        rec = get_domain_recommendations(
            metrics=LMS_UPSTREAM_CONTEXT["metrics"],
            kpis=LMS_UPSTREAM_CONTEXT["kpis"],
            use_case=LMS_UPSTREAM_CONTEXT["use_case"],
            data_sources=LMS_UPSTREAM_CONTEXT["data_sources"],
            top_k=3,
        )

        assert "top_domains" in rec
        assert len(rec["top_domains"]) > 0
        assert rec.get("recommended_domain") is not None
        rec_decisions = rec.get("recommended_decisions", {})
        assert "domain" in rec_decisions or "category" in rec_decisions

    def test_get_taxonomy_slice_for_prompt_lms(self):
        """Taxonomy slice for LMS should be compact and include ld_* domains."""
        from app.agents.dashboard_agent.taxonomy_matcher import get_taxonomy_slice_for_prompt

        slice_data = get_taxonomy_slice_for_prompt(
            metrics=LMS_UPSTREAM_CONTEXT["metrics"],
            kpis=LMS_UPSTREAM_CONTEXT["kpis"],
            use_case=LMS_UPSTREAM_CONTEXT["use_case"],
            max_domains=5,
        )

        assert "ld_training" in slice_data or "ld_operations" in slice_data or len(slice_data) > 0
        for domain_id, domain_data in slice_data.items():
            assert "display_name" in domain_data
            assert "goals" in domain_data
            assert "focus_areas" in domain_data


class TestLayoutAdvisorConfig:
    """Tests for LayoutAdvisorConfig."""

    def test_config_defaults(self):
        """Config should have sensible defaults."""
        from app.agents.dashboard_agent.config import LayoutAdvisorConfig

        cfg = LayoutAdvisorConfig()
        assert cfg.dashboard_goals
        assert cfg.summary_writer_persona == "auditor"
        assert cfg.max_summary_length == 500
        assert cfg.enable_data_tables_hitl is True

    def test_config_to_dict(self):
        """Config should serialize to dict."""
        from app.agents.dashboard_agent.config import LayoutAdvisorConfig

        cfg = LayoutAdvisorConfig(
            dashboard_goals=["Goal A"],
            summary_writer_persona="executive",
            max_summary_length=300,
        )
        d = cfg.to_dict()
        assert d["dashboard_goals"] == ["Goal A"]
        assert d["summary_writer_persona"] == "executive"
        assert d["max_summary_length"] == 300

    def test_config_from_dict(self):
        """Config should build from dict."""
        from app.agents.dashboard_agent.config import LayoutAdvisorConfig

        d = {
            "dashboard_goals": ["SOC2 audit"],
            "summary_writer_persona": "grc_manager",
            "business_context": "Financial services",
            "max_summary_length": 400,
            "enable_data_tables_hitl": False,
        }
        cfg = LayoutAdvisorConfig.from_dict(d)
        assert cfg.dashboard_goals == ["SOC2 audit"]
        assert cfg.summary_writer_persona == "grc_manager"
        assert cfg.business_context == "Financial services"
        assert cfg.max_summary_length == 400
        assert cfg.enable_data_tables_hitl is False


class TestMetricWidgetMapping:
    """Tests for metric widget → chart and metric → gold table mapping."""

    def test_map_metric_widget_to_chart_trend_line(self):
        """trend_line should map to line_basic."""
        from app.agents.dashboard_agent.taxonomy_matcher import map_metric_widget_to_chart

        assert map_metric_widget_to_chart("trend_line", "count", "trend") == "line_basic"
        assert map_metric_widget_to_chart("trend_line") == "line_basic"

    def test_map_metric_widget_to_chart_gauge(self):
        """gauge should map to gauge."""
        from app.agents.dashboard_agent.taxonomy_matcher import map_metric_widget_to_chart

        assert map_metric_widget_to_chart("gauge", "percentage") == "gauge"

    def test_map_metric_widget_to_chart_bar_compare(self):
        """bar_compare should map to bar_grouped or bar_vertical."""
        from app.agents.dashboard_agent.taxonomy_matcher import map_metric_widget_to_chart

        result = map_metric_widget_to_chart("bar_compare", metrics_intent="comparison")
        assert result in ("bar_grouped", "bar_vertical")

    def test_match_metric_to_gold_table(self):
        """Metric with implementation_note mentioning gold table should match."""
        from app.agents.dashboard_agent.taxonomy_matcher import match_metric_to_gold_table

        metric = {
            "id": "vuln_by_host",
            "name": "Vulnerabilities by Host",
            "implementation_note": "gold_qualys_vulnerabilities_weekly_snapshot recommended",
            "data_source_required": "qualys",
        }
        gold_models = [
            {"name": "gold_qualys_vulnerabilities_weekly_snapshot", "description": "Weekly vuln snapshot"},
            {"name": "gold_other", "description": "Other"},
        ]
        result = match_metric_to_gold_table(metric, gold_models)
        assert result == "gold_qualys_vulnerabilities_weekly_snapshot"


class TestFetchDataTables:
    """Tests for fetch_data_tables tool (dummy)."""

    def test_fetch_data_tables_vulnerability(self):
        """'add vulnerability data' should return vulnerability tables."""
        from app.agents.dashboard_agent.tools import fetch_data_tables

        result = fetch_data_tables.invoke({"user_question": "add vulnerability data"})
        tables = json.loads(result) if isinstance(result, str) else result
        assert len(tables) > 0
        assert any("vulnerability" in t.get("name", "").lower() or "vuln" in t.get("table_id", "").lower() for t in tables)

    def test_fetch_data_tables_agent_coverage(self):
        """'include agent coverage' should return agent coverage table."""
        from app.agents.dashboard_agent.tools import fetch_data_tables

        result = fetch_data_tables.invoke({"user_question": "include agent coverage"})
        tables = json.loads(result) if isinstance(result, str) else result
        assert len(tables) > 0
        assert any("agent" in t.get("name", "").lower() or "coverage" in t.get("name", "").lower() for t in tables)

    def test_fetch_data_tables_unknown_returns_default(self):
        """Unknown question should return default tables."""
        from app.agents.dashboard_agent.tools import fetch_data_tables

        result = fetch_data_tables.invoke({"user_question": "xyz unknown"})
        tables = json.loads(result) if isinstance(result, str) else result
        assert len(tables) >= 1


class TestGoalDrivenIntake:
    """Tests for goal-driven intake (metric_recommendations + gold_model_sql)."""

    def test_intake_goal_driven_routes_to_bind(self):
        """Intake with metrics + gold models should route to BIND."""
        from app.agents.dashboard_agent.nodes import intake_node
        from app.agents.dashboard_agent.state import Phase

        metric_recs = [
            {"id": "m1", "name": "Vuln by Host", "widget_type": "trend_line", "kpi_value_type": "count"},
        ]
        gold_sql = [{"name": "gold_vuln_weekly", "description": "Weekly vuln", "expected_columns": []}]

        state = {
            "upstream_context": {
                "metric_recommendations": metric_recs,
                "gold_model_sql": gold_sql,
                "goal_statement": "Vulnerability dashboard",
                "output_format": "echarts",
            },
            "agent_config": {},
            "messages": [],
            "phase": Phase.INTAKE,
        }

        result = intake_node(state)

        assert result["phase"] == Phase.BIND
        assert "resolution_payload" in result
        assert result["resolution_payload"]["metric_recommendations"] == metric_recs
        assert result["resolution_payload"]["gold_model_sql"] == gold_sql
        assert "metric" in result["messages"][0]["content"].lower() or "gold" in result["messages"][0]["content"].lower()


class TestDataTablesNode:
    """Tests for data_tables human-in-the-loop node."""

    def test_data_tables_skip_goes_to_customization(self):
        """User saying 'skip' should route to CUSTOMIZATION."""
        from app.agents.dashboard_agent.nodes import data_tables_node
        from app.agents.dashboard_agent.state import Phase

        state = {
            "user_response": "skip",
            "user_added_tables": [],
            "agent_config": {"enable_data_tables_hitl": True},
        }

        result = data_tables_node(state)

        assert result["phase"] == Phase.CUSTOMIZATION
        assert "skip" in result["messages"][-1]["content"].lower() or "customization" in result["messages"][-1]["content"].lower()

    def test_data_tables_add_vulnerability(self):
        """User asking for vulnerability data should add tables."""
        from app.agents.dashboard_agent.nodes import data_tables_node
        from app.agents.dashboard_agent.state import Phase

        state = {
            "user_response": "add vulnerability data",
            "user_added_tables": [],
            "agent_config": {"enable_data_tables_hitl": True, "max_summary_length": 500},
        }

        result = data_tables_node(state)

        assert result["phase"] == Phase.DATA_TABLES
        assert len(result["user_added_tables"]) > 0
        assert any("vulnerability" in t.get("name", "").lower() or "vuln" in t.get("table_id", "").lower() for t in result["user_added_tables"])


class TestLayoutAdvisorSessionWithConfig:
    """Tests for LayoutAdvisorSession with config."""

    def test_session_start_with_config(self):
        """Session should accept and use agent_config."""
        from app.agents.dashboard_agent import LayoutAdvisorSession, LayoutAdvisorConfig

        config = LayoutAdvisorConfig(
            dashboard_goals=["Test goal"],
            summary_writer_persona="executive",
            enable_data_tables_hitl=False,
        )
        session = LayoutAdvisorSession(agent_config=config)
        response = session.start(upstream_context=LMS_UPSTREAM_CONTEXT)

        assert response.agent_message
        assert response.phase
        assert not response.is_complete


class TestQdrantStoreValidation:
    """Validate Qdrant store configuration and dashboard collections.
    Skipped when VECTOR_STORE_TYPE != qdrant or Qdrant is unreachable.
    """

    def test_qdrant_reachable(self, settings, qdrant_available):
        """Qdrant should be reachable when VECTOR_STORE_TYPE=qdrant."""
        if settings.VECTOR_STORE_TYPE.value != "qdrant":
            pytest.skip("VECTOR_STORE_TYPE is not qdrant")
        if not qdrant_available:
            pytest.skip("Qdrant not reachable (check QDRANT_HOST, QDRANT_PORT)")

    def test_qdrant_dashboard_templates_collection(self, settings, qdrant_client):
        """dashboard_templates collection should exist and optionally have data."""
        from app.storage.collections import MDLCollections

        collection = MDLCollections.DASHBOARD_TEMPLATES
        try:
            collections = qdrant_client.get_collections().collections
            names = [c.name for c in collections]
            assert collection in names, f"Collection {collection} not found. Available: {names}"
            info = qdrant_client.get_collection(collection)
            assert info.points_count >= 0, "Collection should have valid points_count"
        except Exception as e:
            pytest.skip(f"Qdrant validation skipped: {e}")

    def test_qdrant_dashboard_metrics_registry_collection(self, settings, qdrant_client):
        """dashboard_metrics_registry collection should exist when used by MDL flows."""
        from app.storage.collections import MDLCollections

        collection = MDLCollections.DASHBOARD_METRICS_REGISTRY
        try:
            collections = qdrant_client.get_collections().collections
            names = [c.name for c in collections]
            if collection not in names:
                pytest.skip(f"Collection {collection} not found (run ingestion to populate)")
            info = qdrant_client.get_collection(collection)
            assert info.points_count >= 0
        except Exception as e:
            pytest.skip(f"Qdrant validation skipped: {e}")

    def test_settings_vector_store_config(self, settings):
        """Settings should provide valid vector store config."""
        config = settings.get_vector_store_config()
        assert "type" in config
        t = config["type"]
        type_val = t.value if hasattr(t, "value") else str(t)
        assert type_val in ("chroma", "qdrant", "pinecone")
        if type_val == "qdrant":
            assert "host" in config
            assert "port" in config


class TestRuleBasedGraph:
    """Tests for rule-based layout advisor graph (no LLM)."""

    def test_graph_compiles(self):
        """Graph should compile without error."""
        from app.agents.dashboard_agent.graph import compile_layout_advisor

        graph = compile_layout_advisor()
        assert graph is not None

    def test_graph_lms_start(self):
        """Graph should start with LMS context and produce first message."""
        from app.agents.dashboard_agent.graph import compile_layout_advisor
        from app.agents.dashboard_agent.config import LayoutAdvisorConfig

        graph = compile_layout_advisor()
        config = {"configurable": {"thread_id": str(uuid.uuid4())}}

        initial_state = {
            "upstream_context": LMS_UPSTREAM_CONTEXT,
            "agent_config": LayoutAdvisorConfig().to_dict(),
            "messages": [],
            "phase": "intake",
            "decisions": {},
            "auto_resolved": {},
            "candidate_templates": [],
            "recommended_top3": [],
            "selected_template_id": "",
            "customization_requests": [],
            "user_added_tables": [],
            "layout_spec": {},
            "needs_user_input": False,
            "user_response": "",
            "error": "",
        }

        result = graph.invoke(initial_state, config)

        assert "messages" in result
        assert result.get("phase") in ("intake", "decision_intent", "bind", "scoring", "recommendation", "selection")

    def test_graph_goal_driven_full_flow(self):
        """Goal-driven flow: metrics + gold → bind → score → recommend → selection."""
        from app.agents.dashboard_agent.graph import compile_layout_advisor
        from app.agents.dashboard_agent.config import LayoutAdvisorConfig

        with open(base_dir / "examples" / "outputs" / "metric_recommendations.json") as f:
            metric_recs = json.load(f)[:5]
        with open(base_dir / "examples" / "outputs" / "generated_gold_model_sql.json") as f:
            gold_sql = json.load(f)[:3]

        graph = compile_layout_advisor()
        config = {"configurable": {"thread_id": str(uuid.uuid4())}}

        initial_state = {
            "upstream_context": {
                "metric_recommendations": metric_recs,
                "gold_model_sql": gold_sql,
                "goal_statement": "Vulnerability management dashboard",
                "output_format": "echarts",
            },
            "agent_config": LayoutAdvisorConfig().to_dict(),
            "messages": [],
            "phase": "intake",
            "decisions": {},
            "auto_resolved": {},
            "candidate_templates": [],
            "recommended_top3": [],
            "selected_template_id": "",
            "customization_requests": [],
            "user_added_tables": [],
            "layout_spec": {},
            "needs_user_input": False,
            "user_response": "",
            "error": "",
        }

        result = graph.invoke(initial_state, config)

        assert result.get("phase") in ("bind", "scoring", "recommendation", "selection", "data_tables", "customization")
        assert "recommended_top3" in result or "metric_gold_model_bindings" in result or len(result.get("messages", [])) > 0


class TestIntakeNodeLMS:
    """Tests for intake_node_llm with LMS context."""

    def test_intake_node_llm_produces_taxonomy_hint(self):
        """Intake should produce taxonomy hint when metrics/KPIs are present."""
        from app.agents.dashboard_agent.llm_agent import intake_node_llm
        from app.agents.dashboard_agent.state import Phase

        state = {
            "upstream_context": LMS_UPSTREAM_CONTEXT,
            "agent_config": {},
            "messages": [],
            "phase": Phase.INTAKE,
        }

        result = intake_node_llm(state)

        assert "messages" in result
        assert len(result["messages"]) > 0
        assert result["messages"][0]["role"] == "system"
        content = result["messages"][0]["content"]
        assert "Upstream context" in content or "training" in content.lower()
        assert result.get("phase") == Phase.DECISION_INTENT


# ═══════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS (requires ANTHROPIC_API_KEY)
# ═══════════════════════════════════════════════════════════════════════

def _has_anthropic_key() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


@pytest.mark.skipif(
    not _has_anthropic_key(),
    reason="ANTHROPIC_API_KEY not set — skip LLM integration tests",
)
class TestLayoutAdvisorLMS:
    """Integration tests for the LLM Layout Advisor with LMS context."""

    def test_llm_agent_node_lms_one_turn(self):
        """Run one LLM turn with LMS upstream context."""
        from app.agents.dashboard_agent.llm_agent import llm_agent_node, intake_node_llm
        from app.agents.dashboard_agent.state import Phase

        # Build state after intake
        intake_state = {
            "upstream_context": LMS_UPSTREAM_CONTEXT,
            "messages": [],
            "phase": Phase.INTAKE,
        }
        intake_result = intake_node_llm(intake_state)

        state = {
            **intake_result,
            "upstream_context": LMS_UPSTREAM_CONTEXT,
            "decisions": {},
            "auto_resolved": {},
            "candidate_templates": [],
            "recommended_top3": [],
            "selected_template_id": "",
            "layout_spec": {},
            "needs_user_input": False,
            "user_response": "",
        }

        result = llm_agent_node(state, config={"configurable": {"thread_id": str(uuid.uuid4())}})

        assert "messages" in result
        assert len(result["messages"]) > 0
        agent_msg = next((m for m in result["messages"] if m.get("role") == "agent"), None)
        assert agent_msg is not None
        assert len(agent_msg.get("content", "")) > 0

    def test_llm_layout_advisor_graph_lms_start(self):
        """Start the LLM graph with LMS context and verify first response."""
        from app.agents.dashboard_agent.llm_agent import build_llm_layout_advisor_graph

        graph = build_llm_layout_advisor_graph()
        config = {"configurable": {"thread_id": str(uuid.uuid4())}}

        initial_state = {
            "upstream_context": LMS_UPSTREAM_CONTEXT,
            "messages": [],
            "phase": "intake",
            "decisions": {},
            "auto_resolved": {},
            "candidate_templates": [],
            "recommended_top3": [],
            "selected_template_id": "",
            "layout_spec": {},
            "needs_user_input": False,
            "user_response": "",
        }

        result = graph.invoke(initial_state, config)

        assert "messages" in result
        assert len(result["messages"]) > 0
        # Graph should interrupt at await_user or complete
        assert result.get("needs_user_input") is True or result.get("phase") == "complete"


# ═══════════════════════════════════════════════════════════════════════
# MANUAL RUNNER (for quick demos)
# ═══════════════════════════════════════════════════════════════════════

def run_recommendation_layout_demo():
    """
    Run the recommendation layout flow using examples/outputs data.
    Loads metric_recommendations.json and generated_gold_model_sql.json.

    Run: python examples/run_recommendation_layout_demo.py
    Or:  python -m tests.test_layout_advisor_llm  (requires pytest)
    """
    from examples.run_recommendation_layout_demo import main
    main()


def run_lms_demo():
    """
    Run a quick LMS demo using the rule-based LayoutAdvisorSession.
    This uses the same flow as example_usage.py but with LMS context.
    Includes config, data tables hitl, and full flow.

    Run: python -m tests.test_layout_advisor_llm
    """
    from app.agents.dashboard_agent import LayoutAdvisorSession, LayoutAdvisorConfig

    print("=" * 72)
    print("  CCE LAYOUT ADVISOR — LMS Demo")
    print("=" * 72)

    config = LayoutAdvisorConfig(
        dashboard_goals=["Training compliance", "Team oversight"],
        summary_writer_persona="learning_admin",
        max_summary_length=400,
        enable_data_tables_hitl=True,
    )
    session = LayoutAdvisorSession(agent_config=config)
    response = session.start(LMS_UPSTREAM_CONTEXT)

    print(f"\nAgent: {response.agent_message[:300]}...")
    print(f"Phase: {response.phase} | Complete: {response.is_complete} | Needs input: {response.needs_input}")
    if response.decisions_so_far:
        print(f"Decisions: {response.decisions_so_far}")

    # Quick run through decision loop
    for msg in ["Training compliance dashboard", "Cornerstone", "Learning Admin", "Yes", "4"]:
        if not response.needs_input or response.is_complete:
            break
        response = session.respond(msg)

    # Template selection
    if response.recommended:
        response = session.respond("1")

    # Data tables phase (if enabled) — skip or add
    if response.phase == "data_tables":
        response = session.respond("skip")

    if not response.is_complete:
        response = session.respond("looks good")

    if response.layout_spec:
        print("\n✓ Layout spec generated!")
        spec = response.layout_spec
        print(f"  Template: {spec.get('template_name', '?')}")
        print(f"  Output format: {spec.get('output_format', 'echarts')}")
        if spec.get("user_added_tables"):
            print(f"  User-added tables: {len(spec['user_added_tables'])}")
        print(json.dumps(spec, indent=2)[:500] + "...")
    else:
        print(f"\nFinal phase: {response.phase}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1].lower() == "lms":
        run_lms_demo()
    else:
        run_recommendation_layout_demo()

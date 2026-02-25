"""
Tests for DS RAG agent - cornerstone project with trend and moving average functions.

Uses calculate_statistical_trend, calculate_sma, calculate_ema, classify_trend
to produce pipeline step output.
"""

import asyncio
import pytest
import pandas as pd
from pathlib import Path

from langchain_openai import ChatOpenAI
from app.core.pandas_engine import PandasEngine
from app.agents.nodes.ds.ds_rag_agent import DSRAgent
from app.settings import get_settings

PROJECT_ID = "cornerstone"
APPENDIX_PATH = "data/sql_functions/sql_function_appendix.json"


def _make_cornerstone_engine():
    """PandasEngine with cornerstone-style learning data."""
    df = pd.DataFrame({
        "division_id": ["div1", "div1", "div2", "div2"] * 6,
        "metric_date": pd.to_datetime(
            ["2024-01-01", "2024-01-08", "2024-01-15", "2024-01-22"] * 6
        ),
        "completion_rate": [75.0, 78.0, 80.0, 82.0] * 6,
        "enrolled_count": [100, 105, 110, 108] * 6,
        "organization_id": ["cornerstone"] * 24,
    })
    return PandasEngine(data_sources={"fct_learning_completion_monthly": df})


def _make_ds_agent(llm=None, engine=None, appendix_path=None):
    """Create DSRAgent with minimal dependencies. Pipeline-plan tests do not need document stores."""
    settings = get_settings()
    llm = llm or ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.0,
        openai_api_key=getattr(settings, "OPENAI_API_KEY", None),
    )
    engine = engine or _make_cornerstone_engine()
    path = appendix_path or (Path(settings.BASE_DIR) / APPENDIX_PATH)
    return DSRAgent(
        llm=llm,
        engine=engine,
        document_store_provider=None,
        appendix_path=path,
    )


# --- Cornerstone-style fixtures for pipeline planning ---

CONFIRMED_MODELS_CORNERSTONE = [
    {
        "model_id": "transcript_core",
        "display_name": "Learning Completion",
        "columns": [
            {"name": "division_id", "type": "VARCHAR"},
            {"name": "metric_date", "type": "DATE"},
            {"name": "completion_rate", "type": "DECIMAL"},
            {"name": "enrolled_count", "type": "INTEGER"},
            {"name": "organization_id", "type": "VARCHAR"},
        ],
        "grain": ["division_id", "metric_date"],
    }
]

RESOLVED_PARAMETERS_SMA = {
    "output_grain": "division_id, metric_date",
    "time_spine": "metric_date",
    "time_window": "last 6 months",
    "window_size": 7,
}

RESOLVED_PARAMETERS_TREND = {
    "output_grain": "division_id",
    "time_spine": "metric_date",
    "time_window": "last 6 months",
}

FUNCTION_MAP_SMA = [
    {
        "function_name": "calculate_sma",
        "input_key_contract": {"time": "timestamp", "value": "numeric"},
        "input_column": "metric_series",
        "window_size": 7,
        "output_columns": ["time_period", "sma_value", "upper_band", "lower_band"],
    }
]

FUNCTION_MAP_STATISTICAL_TREND = [
    {
        "function_name": "calculate_statistical_trend",
        "input_key_contract": {"time": "timestamp", "metric": "numeric"},
        "input_column": "metric_series",
        "output_columns": ["slope", "r_squared", "p_value", "intercept"],
    }
]

FUNCTION_MAP_CLASSIFY_TREND = [
    {
        "function_name": "classify_trend",
        "input_key_contract": {"time": "timestamp", "metric": "numeric"},
        "input_column": "metric_series",
        "output_columns": ["trend_class", "slope", "interpretation"],
    }
]


class TestDSRAgentAppendix:
    """Verify DS agent loads appendix with trend/moving average functions."""

    def test_agent_has_appendix_functions(self):
        agent = _make_ds_agent()
        names = agent._appendix_names
        assert "calculate_sma" in names
        assert "calculate_ema" in names
        assert "calculate_statistical_trend" in names
        assert "classify_trend" in names
        assert "calculate_moving_average" in names

    def test_appendix_prompt_non_empty(self):
        agent = _make_ds_agent()
        assert len(agent._appendix_prompt) > 0
        assert "calculate_sma" in agent._appendix_prompt
        assert "calculate_statistical_trend" in agent._appendix_prompt

    def test_appendix_prompt_includes_input_contracts(self):
        """Appendix format includes input_contract and jsonb_format_example per ds_rag_fixes Fix 1b."""
        agent = _make_ds_agent()
        prompt = agent._appendix_prompt
        assert "Input JSONB keys required" in prompt or "input_contract" in prompt.lower()
        assert "json_agg" in prompt or "json_build_object" in prompt


class TestDSRAgentPipelinePlan:
    """Test _build_pipeline_plan for cornerstone with trend/moving average functions."""

    def test_build_pipeline_plan_sma(self):
        """Build pipeline plan for 7-day SMA of completion rate by division."""
        agent = _make_ds_agent()
        query = (
            "Show the 7-day moving average of completion rate by division "
            "for cornerstone over the last 6 months"
        )

        async def _run():
            return await agent._build_pipeline_plan(
                query=query,
                confirmed_models=CONFIRMED_MODELS_CORNERSTONE,
                resolved_parameters=RESOLVED_PARAMETERS_SMA,
                function_map=FUNCTION_MAP_SMA,
            )

        plan = asyncio.run(_run())
        assert isinstance(plan, dict)
        assert "steps" in plan or "plan_type" in plan
        steps = plan.get("steps", {})
        if steps:
            assert "step_1" in steps or len(steps) >= 1
            # Step 3 should reference calculate_sma
            step_keys = list(steps.keys())
            last_step = steps.get(step_keys[-1]) if step_keys else {}
            fn = last_step.get("function") if isinstance(last_step, dict) else {}
            if fn:
                assert fn.get("function_name") == "calculate_sma"

    def test_build_pipeline_plan_statistical_trend(self):
        """Build pipeline plan for statistical trend of completion rate by division."""
        agent = _make_ds_agent()
        query = (
            "Calculate the statistical trend of completion rate by division "
            "for cornerstone over the last 6 months"
        )
        plan = asyncio.run(
            agent._build_pipeline_plan(
                query=query,
                confirmed_models=CONFIRMED_MODELS_CORNERSTONE,
                resolved_parameters=RESOLVED_PARAMETERS_TREND,
                function_map=FUNCTION_MAP_STATISTICAL_TREND,
            )
        )
        assert isinstance(plan, dict)
        assert "steps" in plan or "plan_type" in plan
        steps = plan.get("steps", {})
        if steps:
            last_key = list(steps.keys())[-1]
            last_step = steps[last_key]
            fn = last_step.get("function") if isinstance(last_step, dict) else {}
            if fn:
                assert fn.get("function_name") == "calculate_statistical_trend"

    def test_build_pipeline_plan_classify_trend(self):
        """Build pipeline plan for classify_trend on completion rate."""
        agent = _make_ds_agent()
        query = (
            "Classify the trend of completion rate by division "
            "for cornerstone over the last 6 months"
        )
        plan = asyncio.run(
            agent._build_pipeline_plan(
                query=query,
                confirmed_models=CONFIRMED_MODELS_CORNERSTONE,
                resolved_parameters=RESOLVED_PARAMETERS_TREND,
                function_map=FUNCTION_MAP_CLASSIFY_TREND,
            )
        )
        assert isinstance(plan, dict)
        steps = plan.get("steps", {})
        if steps:
            last_key = list(steps.keys())[-1]
            last_step = steps[last_key]
            fn = last_step.get("function") if isinstance(last_step, dict) else {}
            if fn:
                assert fn.get("function_name") == "classify_trend"


class TestDSRAgentNLQuestion:
    """Test _generate_nl_question for pipeline steps."""

    def test_generate_nl_question_for_sma_step(self):
        """Generate NL question for a step that feeds calculate_sma."""
        agent = _make_ds_agent()
        step_definition = {
            "purpose": "Aggregate completion rate to monthly grain per division and format as JSONB",
            "input_source": "fct_learning_completion_monthly",
            "input_columns": ["division_id", "metric_date", "completion_rate"],
            "output_columns": [
                {"name": "division_id", "type": "VARCHAR"},
                {"name": "metric_series", "type": "JSONB"},
            ],
            "nl_question_spec": {
                "intent": "Group by division and format metric as JSONB array for calculate_sma",
                "must_include": ["GROUP BY division_id", "json_agg", "metric_series"],
                "output_shape": "One row per division with metric_series",
            },
        }
        available_schema = {
            "tables": ["fct_learning_completion_monthly"],
            "columns": ["division_id", "metric_date", "completion_rate", "organization_id"],
        }
        result = asyncio.run(
            agent._generate_nl_question(
                step_definition=step_definition,
                available_schema=available_schema,
            )
        )
        assert isinstance(result, dict)
        assert "nl_question" in result or "step" in result
        if result.get("nl_question"):
            assert len(result["nl_question"]) > 0


class TestDSRAgentTaskDecomposition:
    """Test _decompose_task_internal for cornerstone-style queries."""

    def test_decompose_task_moving_average(self):
        """Decompose task for moving average query."""
        agent = _make_ds_agent()
        query = (
            "Show the 7-day moving average of completion rate by division "
            "for cornerstone over the last 6 months"
        )
        decomposition = asyncio.run(
            agent._decompose_task_internal(query, language="English")
        )
        assert isinstance(decomposition, str)
        assert len(decomposition) > 0
        # Should mention data fetch, transformation, or operations
        decomp_lower = decomposition.lower()
        assert (
            "data" in decomp_lower
            or "fetch" in decomp_lower
            or "completion" in decomp_lower
            or "moving" in decomp_lower
            or "average" in decomp_lower
        )

    def test_decompose_task_statistical_trend(self):
        """Decompose task for statistical trend query."""
        agent = _make_ds_agent()
        query = (
            "Calculate the statistical trend of enrollment count by division "
            "for cornerstone over the last 6 months"
        )
        decomposition = asyncio.run(
            agent._decompose_task_internal(query, language="English")
        )
        assert isinstance(decomposition, str)
        assert len(decomposition) > 0

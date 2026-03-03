"""Tests for GoldModelPlanGenerator (compliance skill version)."""

import pytest
from app.agents.gold_model_plan_generator import (
    GoldModelPlanGenerator,
    GoldModelPlanGeneratorInput,
    SilverTableInfo,
)


@pytest.fixture
def sample_silver_table_info() -> list[SilverTableInfo]:
    """Create sample silver table info for testing."""
    schema_info = {
        "table_name": "snyk_issue",
        "description": "Snyk vulnerability issues table",
        "table_ddl": "CREATE TABLE snyk_issue (id STRING, severity STRING, created_at TIMESTAMP, fixed_at TIMESTAMP, connection_id STRING)",
        "column_metadata": [
            {"column_name": "id", "type": "string", "description": "Issue ID"},
            {"column_name": "severity", "type": "string", "description": "Severity level"},
            {"column_name": "created_at", "type": "timestamp", "description": "Creation time"},
            {"column_name": "fixed_at", "type": "timestamp", "description": "Fix time"},
            {"column_name": "connection_id", "type": "string", "description": "Connection ID"},
        ],
    }

    return [
        SilverTableInfo(
            table_name="snyk_issue",
            reason="Snyk vulnerability issues table",
            schema_info=schema_info,
            relevant_columns=["id", "severity", "created_at", "fixed_at"],
            relevant_columns_reasoning="Columns needed for MTTR calculation",
        )
    ]


@pytest.fixture
def sample_metrics() -> list[dict]:
    """Create sample metrics for testing."""
    return [
        {
            "name": "mean_time_to_remediate",
            "description": "Average time to fix vulnerabilities",
            "base_table": "snyk_issue",
            "dimensions": ["severity"],
            "measure": "AVG(EXTRACT(EPOCH FROM (fixed_at - created_at))/86400) as days_to_fix",
            "source_schemas": ["snyk_issue"],
        },
        {
            "name": "open_issues_count",
            "description": "Count of open vulnerabilities",
            "base_table": "snyk_issue",
            "dimensions": ["severity"],
            "measure": "COUNT(*) WHERE fixed_at IS NULL",
            "source_schemas": ["snyk_issue"],
        },
    ]


@pytest.mark.asyncio
async def test_generate_gold_model_plan(sample_metrics, sample_silver_table_info):
    """Test generating a gold model plan from metrics."""
    generator = GoldModelPlanGenerator()

    input_data = GoldModelPlanGeneratorInput(
        metrics=sample_metrics,
        silver_tables_info=sample_silver_table_info,
        user_request="Show me vulnerability remediation metrics",
    )

    plan = await generator.generate(input_data)

    assert plan is not None
    assert isinstance(plan.requires_gold_model, bool)
    assert plan.reasoning is not None

    if plan.requires_gold_model:
        assert plan.specifications is not None
        assert len(plan.specifications) > 0

        for spec in plan.specifications:
            assert spec.name.startswith("gold_")
            assert spec.description is not None
            assert spec.materialization in ["incremental", "table", "view"]
            assert len(spec.expected_columns) > 0

            # Ensure connection_id is present
            column_names = {col.name for col in spec.expected_columns}
            assert "connection_id" in column_names


@pytest.mark.asyncio
async def test_generate_with_kpis(sample_metrics, sample_silver_table_info):
    """Test generating plan with KPIs."""
    generator = GoldModelPlanGenerator()

    kpis = [
        {
            "kpi_name": "MTTR",
            "calculation_method": "Average days to fix vulnerabilities",
        }
    ]

    input_data = GoldModelPlanGeneratorInput(
        metrics=sample_metrics,
        silver_tables_info=sample_silver_table_info,
        kpis=kpis,
        user_request="Generate MTTR dashboard",
    )

    plan = await generator.generate(input_data)

    assert plan is not None
    # Plan should account for KPIs in reasoning or specifications


@pytest.mark.asyncio
async def test_silver_table_info_render_schema(sample_silver_table_info):
    """Test SilverTableInfo.render_schema() method."""
    table_info = sample_silver_table_info[0]
    schema_text = table_info.render_schema()
    
    assert "Table: snyk_issue" in schema_text
    assert "Description:" in schema_text or "DDL:" in schema_text
    assert "Columns:" in schema_text
    assert "id" in schema_text
    assert "severity" in schema_text

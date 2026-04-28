"""
dbt Model Generation Service.

Generates three artifacts for every dashboard publish event:
  1. dbt SQL       — LLM-generated via GoldModelSQLGenerator (rich business logic)
  2. schema.yml    — template-rendered (structural, deterministic)
  3. cube_yaml     — template-rendered (semantic layer definition)

The key difference from the existing gold model workflow:
- Existing flow: GoldModelPlanGenerator discovers WHAT models are needed from vague metrics
- This flow:     The dashboard already defines exactly WHAT is needed (grain, dimensions,
                 metrics). We skip plan discovery and feed a pre-built GoldModelPlan
                 straight into GoldModelSQLGenerator so the LLM focuses entirely on
                 generating rich, context-aware SQL — joins, window functions, complex
                 aggregations — for a better dashboard experience.
"""
import logging
from typing import Any

from app.agents.shared.dbt_generation import (
    DbtGenerateRequest,
    DbtGenerateResponse,
    build_cube_yaml,
    build_schema_yml,
)
from app.agents.shared.gold_model_generation import (
    GoldModelPlan,
    GoldModelSQLGenerator,
    GoldModelSpecification,
    OutputColumn,
    SourceTableColumn,
    SilverTableInfo,
    load_examples_for_model,
)

logger = logging.getLogger(__name__)


def _build_gold_model_plan(req: DbtGenerateRequest) -> GoldModelPlan:
    """
    Convert a DbtGenerateRequest into a GoldModelPlan with a single specification.

    We already know grain, dimensions, metrics, and source tables from the dashboard
    definition so no LLM plan discovery is needed — build it deterministically.
    """
    # Every gold cube always includes these fixed columns
    fixed_columns = [
        OutputColumn(name="connection_id", description="Multi-tenant isolation key"),
        OutputColumn(name="tenant_id", description="Tenant identifier"),
        OutputColumn(
            name="period",
            description=f"Aggregation period truncated to {req.grain.value}",
        ),
    ]

    dimension_columns = [
        OutputColumn(
            name=dim.name,
            description=dim.description or dim.name.replace("_", " ").title(),
        )
        for dim in req.dimensions
    ]

    metric_columns = [
        OutputColumn(
            name=m.name,
            description=m.description or f"{m.aggregation.value} of {m.column}",
        )
        for m in req.metrics
    ]

    source_columns = [
        SourceTableColumn(
            table_name=req.source_tables[0] if req.source_tables else "silver_source",
            column_name=dim.name,
            usage="dimension / GROUP BY",
        )
        for dim in req.dimensions
    ] + [
        SourceTableColumn(
            table_name=req.source_tables[0] if req.source_tables else "silver_source",
            column_name=m.column,
            usage=f"{m.aggregation.value} aggregation → {m.name}",
        )
        for m in req.metrics
    ]

    description = (
        req.description
        or (
            f"Gold cube for dashboard {req.dashboard_id}. "
            f"Aggregates {', '.join(req.source_tables)} at {req.grain.value} grain "
            f"across dimensions: {', '.join(d.name for d in req.dimensions)}. "
            f"Metrics: {', '.join(m.name for m in req.metrics)}."
        )
    )

    spec = GoldModelSpecification(
        name=req.model_name,
        description=description,
        materialization="incremental",
        source_tables=req.source_tables,
        source_columns=source_columns,
        expected_columns=fixed_columns + dimension_columns + metric_columns,
    )

    return GoldModelPlan(
        requires_gold_model=True,
        reasoning=(
            f"Dashboard {req.dashboard_id} published with explicit grain={req.grain.value}, "
            f"{len(req.dimensions)} dimensions, {len(req.metrics)} metrics "
            f"from source tables: {', '.join(req.source_tables)}."
        ),
        specifications=[spec],
    )


def _build_silver_tables_info(req: DbtGenerateRequest) -> list[dict[str, Any]]:
    """
    Build minimal silver table info for the SQL generator prompt.
    Includes all dimension and metric columns the LLM needs to reference.
    """
    columns = (
        [{"column_name": "connection_id", "type": "VARCHAR", "description": "Multi-tenant key"}]
        + [{"column_name": "tenant_id", "type": "VARCHAR", "description": "Tenant identifier"}]
        + [{"column_name": req.event_date_column, "type": "TIMESTAMP", "description": "Event timestamp"}]
        + [{"column_name": dim.name, "type": dim.type, "description": dim.description} for dim in req.dimensions]
        + [{"column_name": m.column, "type": "NUMERIC", "description": m.description or m.name} for m in req.metrics]
    )

    return [
        {
            "table_name": table,
            "column_metadata": columns,
        }
        for table in req.source_tables
    ]


class DbtModelGenerationService:

    def __init__(self, temperature: float = 0.0, max_tokens: int = 16384):
        self._sql_generator = GoldModelSQLGenerator(
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def generate(self, req: DbtGenerateRequest) -> DbtGenerateResponse:
        """
        Generate all three dbt artifacts from a dashboard publish payload.

        - SQL:        LLM via GoldModelSQLGenerator (rich, context-aware)
        - schema.yml: Jinja2 template (deterministic, structural)
        - cube_yaml:  Jinja2 template (deterministic, semantic layer)
        """
        logger.info(
            "Generating dbt artifacts model=%s dashboard=%s grain=%s "
            "dimensions=%d metrics=%d destination=%s",
            req.model_name,
            req.dashboard_id,
            req.grain.value,
            len(req.dimensions),
            len(req.metrics),
            req.destination_type.value,
        )

        plan = _build_gold_model_plan(req)
        silver_tables_info = _build_silver_tables_info(req)
        examples = load_examples_for_model(req.model_name, max_examples=2)

        sql_response = await self._sql_generator.generate(
            gold_model_plan=plan,
            silver_tables_info=silver_tables_info,
            examples=examples,
        )

        if not sql_response.models:
            raise RuntimeError(
                f"LLM returned no SQL for model {req.model_name}. "
                "Check silver table info and model specification."
            )

        sql = sql_response.models[0].sql_query
        schema_yml = build_schema_yml(req)
        cube_yaml = build_cube_yaml(req)

        logger.info("dbt artifacts generated for model=%s", req.model_name)

        return DbtGenerateResponse(
            model_name=req.model_name,
            sql=sql,
            schema_yml=schema_yml,
            cube_yaml=cube_yaml,
        )


_service: DbtModelGenerationService | None = None


def get_dbt_model_generation_service() -> DbtModelGenerationService:
    global _service
    if _service is None:
        _service = DbtModelGenerationService()
    return _service

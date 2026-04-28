"""
dbt Generation Route — POST /api/v1/dbt/generate

Called by Airflow (task T1: generate_dbt_model_sql) during the
dashboard_dbt_pipeline DAG. Returns three artifacts for the published dashboard:
  - sql        LLM-generated dbt-spark SQL (rich business logic via GoldModelSQLGenerator)
  - schema_yml template-rendered dbt schema with column tests
  - cube_yaml  template-rendered semantic layer cube definition
"""
from fastapi import APIRouter, HTTPException, status

from app.agents.shared.dbt_generation import DbtGenerateRequest, DbtGenerateResponse
from app.services.dbt_model_generation_service import get_dbt_model_generation_service

router = APIRouter(prefix="/api/v1/dbt", tags=["dbt"])


@router.post(
    "/generate",
    response_model=DbtGenerateResponse,
    summary="Generate dbt gold cube artifacts for a published dashboard",
)
async def generate_dbt_model(req: DbtGenerateRequest) -> DbtGenerateResponse:
    """
    Generates three dbt artifacts from a dashboard publish payload:

    - **sql**: LLM-generated via `GoldModelSQLGenerator` — same pipeline as the
      existing gold model workflow, but with a pre-built plan (grain, dimensions,
      metrics already known from the dashboard definition). The LLM focuses on
      rich business logic: window functions, complex joins, incremental strategy.
    - **schema_yml**: Jinja2 template — column definitions + dbt tests.
    - **cube_yaml**: Jinja2 template — semantic layer definition for integration
      adapters (Asthera UX, PowerBI, Tableau).
    """
    if not req.source_tables:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="source_tables must contain at least one silver table name",
        )
    if not req.dimensions and not req.metrics:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one dimension or metric is required",
        )

    svc = get_dbt_model_generation_service()

    try:
        return await svc.generate(req)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

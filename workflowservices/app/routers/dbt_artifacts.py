"""
dbt Artifacts Router.

Endpoints:
  GET  /{workflow_id}/dbt-artifact              artifact + all versions
  GET  /{workflow_id}/dbt-artifact/current      active version only
  POST /dbt-artifacts/callback                  Airflow posts result here
  GET  /dbt-artifacts/{artifact_id}/versions    full version history
  POST /destinations/                           register a gold destination
  GET  /destinations/                           list tenant destinations
  PATCH /destinations/{id}/set-default          set as tenant default
  POST /destinations/{id}/test                  test connection
"""
import logging
import os
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_async_db_session
from app.models.dbt_artifact import ArtifactType, DbtArtifact, DbtArtifactVersion
from app.models.gold_destination import GoldDestinationConfig, GoldDestinationType
from app.services.dbt_artifact_service import DbtArtifactService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dbt-artifacts"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class DbtCallbackPayload(BaseModel):
    dag_run_id:            str
    status:                str          # passed | failed
    model_sql:             str | None = None
    schema_yml:            str | None = None
    cube_yaml:             str | None = None
    destination_table_uri: str | None = None
    table_snapshot_id:     str | None = None
    table_version_number:  int | None = None
    run_log:               str | None = None


class GoldDestinationCreate(BaseModel):
    name:             str
    destination_type: GoldDestinationType
    connection_config: dict[str, Any]
    is_default:       bool = False


# ---------------------------------------------------------------------------
# Artifact read routes
# ---------------------------------------------------------------------------

@router.get("/{workflow_id}/dbt-artifact")
async def get_artifact(
    workflow_id: str,
    artifact_type: str = "dashboard",
    db: AsyncSession = Depends(get_async_db_session),
):
    svc   = DbtArtifactService(db)
    atype = ArtifactType(artifact_type)
    artifact = await svc.get_artifact(workflow_id, atype)
    if not artifact:
        raise HTTPException(status_code=404, detail="No dbt artifact found for this workflow")
    return {
        "artifact_id":   artifact.id,
        "model_name":    artifact.model_name,
        "status":        artifact.status.value,
        "current_version_id": artifact.current_version_id,
        "versions": [
            {
                "id":             v.id,
                "version_number": v.version_number,
                "run_status":     v.run_status.value,
                "is_current":     v.is_current,
                "destination_table_uri": v.destination_table_uri,
                "created_at":     v.created_at.isoformat(),
            }
            for v in (artifact.versions or [])
        ],
    }


@router.get("/{workflow_id}/dbt-artifact/current")
async def get_current_version(
    workflow_id: str,
    artifact_type: str = "dashboard",
    db: AsyncSession = Depends(get_async_db_session),
):
    svc      = DbtArtifactService(db)
    atype    = ArtifactType(artifact_type)
    artifact = await svc.get_artifact(workflow_id, atype)
    if not artifact or not artifact.current_version_id:
        raise HTTPException(status_code=404, detail="No active dbt version found")

    stmt   = select(DbtArtifactVersion).where(DbtArtifactVersion.id == artifact.current_version_id)
    result = await db.execute(stmt)
    version = result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Current version record not found")

    return {
        "artifact_id":          artifact.id,
        "model_name":           artifact.model_name,
        "status":               artifact.status.value,
        "version_number":       version.version_number,
        "run_status":           version.run_status.value,
        "destination_table_uri": version.destination_table_uri,
        "destination_type":     version.destination_type,
        "cube_yaml":            version.cube_yaml,
        "grain":                version.grain,
        "dimensions":           version.dimensions,
        "measures":             version.metrics,
        "s3_artifact_path":     version.s3_artifact_path,
        "created_at":           version.created_at.isoformat(),
    }


@router.get("/dbt-artifacts/{artifact_id}/versions")
async def list_versions(
    artifact_id: str,
    db: AsyncSession = Depends(get_async_db_session),
):
    stmt   = select(DbtArtifactVersion).where(
        DbtArtifactVersion.artifact_id == artifact_id
    ).order_by(DbtArtifactVersion.version_number.desc())
    result = await db.execute(stmt)
    versions = result.scalars().all()
    return [
        {
            "id":             v.id,
            "version_number": v.version_number,
            "run_status":     v.run_status.value,
            "is_current":     v.is_current,
            "dag_run_id":     v.dag_run_id,
            "destination_table_uri": v.destination_table_uri,
            "grain":          v.grain,
            "dimensions":     v.dimensions,
            "metrics":        v.metrics,
            "source_tables":  v.source_tables,
            "created_at":     v.created_at.isoformat(),
        }
        for v in versions
    ]


# ---------------------------------------------------------------------------
# Airflow callback
# ---------------------------------------------------------------------------

@router.post("/dbt-artifacts/callback", status_code=status.HTTP_204_NO_CONTENT)
async def airflow_callback(
    body: DbtCallbackPayload,
    db: AsyncSession = Depends(get_async_db_session),
):
    """Airflow posts here after DAG completion (success or failure)."""
    svc = DbtArtifactService(db)
    try:
        await svc.receive_callback(body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Gold destination management
# ---------------------------------------------------------------------------

@router.post("/destinations/", status_code=status.HTTP_201_CREATED)
async def create_destination(
    body: GoldDestinationCreate,
    tenant_id: str,                    # passed as query param from gateway JWT
    db: AsyncSession = Depends(get_async_db_session),
):
    if body.is_default:
        # Clear existing default for tenant
        stmt   = select(GoldDestinationConfig).where(
            GoldDestinationConfig.tenant_id == tenant_id,
            GoldDestinationConfig.is_default == True,   # noqa: E712
        )
        result = await db.execute(stmt)
        for existing in result.scalars().all():
            existing.is_default = False

    dest = GoldDestinationConfig(
        tenant_id        = tenant_id,
        name             = body.name,
        destination_type = body.destination_type,
        connection_config = body.connection_config,
        is_default       = body.is_default,
    )
    db.add(dest)
    await db.commit()
    await db.refresh(dest)
    return {"id": dest.id, "name": dest.name, "destination_type": dest.destination_type.value}


@router.get("/destinations/")
async def list_destinations(
    tenant_id: str,
    db: AsyncSession = Depends(get_async_db_session),
):
    stmt   = select(GoldDestinationConfig).where(
        GoldDestinationConfig.tenant_id == tenant_id,
        GoldDestinationConfig.is_active == True,    # noqa: E712
    )
    result = await db.execute(stmt)
    dests  = result.scalars().all()
    return [
        {
            "id":             d.id,
            "name":           d.name,
            "destination_type": d.destination_type.value,
            "is_default":     d.is_default,
        }
        for d in dests
    ]


@router.patch("/destinations/{dest_id}/set-default", status_code=status.HTTP_204_NO_CONTENT)
async def set_default_destination(
    dest_id: str,
    tenant_id: str,
    db: AsyncSession = Depends(get_async_db_session),
):
    # Clear existing default
    stmt   = select(GoldDestinationConfig).where(
        GoldDestinationConfig.tenant_id == tenant_id,
        GoldDestinationConfig.is_default == True,   # noqa: E712
    )
    result = await db.execute(stmt)
    for existing in result.scalars().all():
        existing.is_default = False

    stmt   = select(GoldDestinationConfig).where(GoldDestinationConfig.id == dest_id)
    result = await db.execute(stmt)
    dest   = result.scalar_one_or_none()
    if not dest:
        raise HTTPException(status_code=404, detail="Destination not found")
    dest.is_default = True
    await db.commit()


@router.post("/destinations/{dest_id}/test")
async def test_destination(
    dest_id: str,
    db: AsyncSession = Depends(get_async_db_session),
):
    """Validate credentials by performing a lightweight connection test."""
    stmt   = select(GoldDestinationConfig).where(GoldDestinationConfig.id == dest_id)
    result = await db.execute(stmt)
    dest   = result.scalar_one_or_none()
    if not dest:
        raise HTTPException(status_code=404, detail="Destination not found")

    # Lightweight test per destination type — just validate config keys are present
    required: dict[str, list[str]] = {
        "customer_s3":  ["bucket", "region", "access_key_id", "secret_access_key"],
        "snowflake":    ["account", "database", "schema", "warehouse", "user"],
        "bigquery":     ["project", "dataset", "service_account_json"],
        "databricks":   ["host", "http_path", "token", "catalog", "schema"],
        "redshift":     ["host", "database", "user", "password"],
        "azure_adls":   ["account_name", "container", "tenant_id", "client_id", "client_secret"],
        "postgres":     ["host", "database", "user", "password"],
    }
    cfg     = dest.connection_config or {}
    missing = [k for k in required.get(dest.destination_type.value, []) if k not in cfg]
    if missing:
        return {"success": False, "missing_fields": missing}
    return {"success": True, "destination_type": dest.destination_type.value}

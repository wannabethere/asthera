"""
Generic RLS/CLS configuration API (data services).

Provides:
  - Org-level CRUD  (existing)
  - Connection-level policy generation, CRUD, and effective-policy preview (new)

Optional service auth: set DATA_SERVICES_PROTECTION_API_KEY and send X-DS-API-Key.
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.data_protection_agent import DataProtectionAgent
from app.core.dependencies import get_async_db_session
from app.schemas.data_protection_api import (
    ColumnClassificationResponse,
    ConnectionPolicyConfig,
    DataProtectionConfig,
    DataProtectionStatusResponse,
    EffectivePolicyPreview,
    PolicyGenerationRequest,
    PolicyGenerationResponse,
    PredicateValidationRequest,
    PredicateValidationResponse,
)
from app.service.data_protection_service import (
    activate_connection_policies,
    clear_organization,
    get_effective_policies,
    list_connections_with_policies,
    load_config,
    load_connection_policies,
    reload_config,
    save_config,
    save_connection_policies,
)
from app.service.ERDextraction_service import ERDExtractor

logger = logging.getLogger(__name__)
router = APIRouter()

# Singleton agent (stateless except TTL cache)
_agent = DataProtectionAgent()
_erd = ERDExtractor()


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

async def verify_protection_service_key(x_ds_api_key: str | None = Header(None, alias="X-DS-API-Key")) -> None:
    expected = os.getenv("DATA_SERVICES_PROTECTION_API_KEY", "").strip()
    if not expected:
        return
    if not x_ds_api_key or x_ds_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-DS-API-Key",
        )


# ---------------------------------------------------------------------------
# Org-level endpoints (unchanged)
# ---------------------------------------------------------------------------

@router.get("/status", response_model=DataProtectionStatusResponse)
async def protection_status(_: None = Depends(verify_protection_service_key)) -> DataProtectionStatusResponse:
    return DataProtectionStatusResponse(
        api_key_configured=bool(os.getenv("DATA_SERVICES_PROTECTION_API_KEY", "").strip()),
    )


@router.get("/orgs/{organization_id}/config", response_model=DataProtectionConfig)
async def get_org_config(
    organization_id: UUID,
    db: AsyncSession = Depends(get_async_db_session),
    _: None = Depends(verify_protection_service_key),
) -> DataProtectionConfig:
    return await load_config(db, organization_id)


@router.put("/orgs/{organization_id}/config", response_model=DataProtectionConfig)
async def put_org_config(
    organization_id: UUID,
    body: DataProtectionConfig,
    db: AsyncSession = Depends(get_async_db_session),
    _: None = Depends(verify_protection_service_key),
) -> DataProtectionConfig:
    try:
        await save_config(db, organization_id, body)
        await db.commit()
        return body
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.post("/orgs/{organization_id}/config/reload", response_model=DataProtectionConfig)
async def post_org_config_reload(
    organization_id: UUID,
    db: AsyncSession = Depends(get_async_db_session),
    _: None = Depends(verify_protection_service_key),
) -> DataProtectionConfig:
    """Load DATA_PROTECTION_SEED_PATH JSON into this org, or clear to empty if unset."""
    try:
        return await reload_config(db, organization_id)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.delete("/orgs/{organization_id}/config", response_model=DataProtectionConfig)
async def delete_org_config(
    organization_id: UUID,
    db: AsyncSession = Depends(get_async_db_session),
    _: None = Depends(verify_protection_service_key),
) -> DataProtectionConfig:
    try:
        await clear_organization(db, organization_id)
        await db.commit()
        return DataProtectionConfig()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


# ---------------------------------------------------------------------------
# Connection-level: policy generation (agent)
# ---------------------------------------------------------------------------

async def _get_connection_schema(connection_id: UUID, db: AsyncSession):
    """Fetch the ERD schema for a connection."""
    from app.schemas.dbmodels import ConnectionDetails

    conn = await db.get(ConnectionDetails, connection_id)
    if conn is None:
        raise HTTPException(status_code=404, detail=f"Connection {connection_id} not found")

    # ERDExtractor expects connectionDetails with .data_source and .connection_details
    try:
        schema = await _erd.get_RDBMS_Extractor(conn)
        # get_RDBMS_Extractor returns ReactFlow JSON; we need raw schema for the agent
        # Re-extract raw schema for the agent prompt
        raw_schema = await _extract_raw_schema(conn)
        return raw_schema
    except Exception as e:
        logger.warning("ERD extraction failed, falling back to raw schema: %s", e)
        return await _extract_raw_schema(conn)


async def _extract_raw_schema(conn) -> dict:
    """Extract raw table/column schema directly for the agent."""
    db_type = conn.data_source.database_type.lower() if conn.data_source else "unknown"
    details = conn.connection_details or {}

    if db_type == "postgresql":
        import asyncpg

        connection = await asyncpg.connect(
            host=details.get("host"),
            port=details.get("port", 5432),
            user=details.get("username"),
            password=details.get("password"),
            database=details.get("database"),
        )
        try:
            tables_query = """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """
            tables = await connection.fetch(tables_query)
            schema = {"tables": []}
            for row in tables:
                cols_query = """
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = $1 AND table_schema = 'public'
                    ORDER BY ordinal_position
                """
                cols = await connection.fetch(cols_query, row["table_name"])
                pk_query = """
                    SELECT kcu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name
                    WHERE tc.table_name = $1 AND tc.constraint_type = 'PRIMARY KEY'
                """
                pks = await connection.fetch(pk_query, row["table_name"])
                schema["tables"].append({
                    "table_name": row["table_name"],
                    "columns": [
                        {"fieldName": c["column_name"], "dataType": c["data_type"]}
                        for c in cols
                    ],
                    "primary_key": [p["column_name"] for p in pks],
                })
            return schema
        finally:
            await connection.close()

    # Fallback: return empty schema for unsupported types (agent will still work with limited data)
    logger.warning("Raw schema extraction not implemented for %s, returning empty", db_type)
    return {"tables": []}


@router.post(
    "/connections/{connection_id}/generate",
    response_model=PolicyGenerationResponse,
)
async def generate_connection_policies(
    connection_id: UUID,
    body: PolicyGenerationRequest,
    db: AsyncSession = Depends(get_async_db_session),
    _: None = Depends(verify_protection_service_key),
) -> PolicyGenerationResponse:
    """Use the LLM agent to generate RLS/CLS policy recommendations from the connection schema."""
    try:
        schema = await _get_connection_schema(connection_id, db)
        tables_data = schema.get("tables", [])

        config = await _agent.generate_policies(
            connection_id=connection_id,
            tables_data=tables_data,
            business_context=body.business_context,
            existing_roles=body.existing_roles or [],
            generate_rls=body.generate_rls,
            generate_cls=body.generate_cls,
        )

        metadata = {
            "tables_analyzed": len(tables_data),
            "columns_classified": sum(len(t.get("columns", [])) for t in tables_data),
            "model": "gpt-4o-mini",
        }

        # Persist as draft
        await save_connection_policies(
            db,
            connection_id=connection_id,
            organization_id=body.organization_id,
            config=config,
            status="draft",
            generated_by="agent",
            generation_metadata=metadata,
        )
        await db.commit()

        return PolicyGenerationResponse(
            connection_id=connection_id,
            status="draft",
            config=config,
            tables_analyzed=metadata["tables_analyzed"],
            columns_classified=metadata["columns_classified"],
            generation_metadata=metadata,
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.exception("Policy generation failed for connection %s", connection_id)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ---------------------------------------------------------------------------
# Connection-level: CRUD
# ---------------------------------------------------------------------------

@router.get(
    "/connections/{connection_id}/policies",
    response_model=ConnectionPolicyConfig,
)
async def get_connection_policies(
    connection_id: UUID,
    db: AsyncSession = Depends(get_async_db_session),
    _: None = Depends(verify_protection_service_key),
) -> ConnectionPolicyConfig:
    cfg = await load_connection_policies(db, connection_id)
    if cfg is None:
        raise HTTPException(status_code=404, detail="No policies found for this connection")
    return cfg


@router.put(
    "/connections/{connection_id}/policies",
    response_model=ConnectionPolicyConfig,
)
async def put_connection_policies(
    connection_id: UUID,
    body: ConnectionPolicyConfig,
    db: AsyncSession = Depends(get_async_db_session),
    _: None = Depends(verify_protection_service_key),
) -> ConnectionPolicyConfig:
    try:
        await save_connection_policies(
            db,
            connection_id=connection_id,
            organization_id=body.organization_id,
            config=body.config,
            status=body.status,
            inheritance_mode=body.inheritance_mode,
            rls_overrides=body.rls_overrides,
            cls_overrides=body.cls_overrides,
            excluded_policy_ids=body.excluded_policy_ids,
            generated_by=body.generated_by,
            generation_metadata=body.generation_metadata,
        )
        await db.commit()
        return body
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/connections/{connection_id}/activate")
async def activate_policies(
    connection_id: UUID,
    db: AsyncSession = Depends(get_async_db_session),
    _: None = Depends(verify_protection_service_key),
):
    updated = await activate_connection_policies(db, connection_id)
    if not updated:
        raise HTTPException(status_code=404, detail="No draft policies found to activate")
    await db.commit()
    return {"status": "active", "connection_id": str(connection_id)}


@router.get(
    "/connections/{connection_id}/effective",
    response_model=EffectivePolicyPreview,
)
async def effective_policies(
    connection_id: UUID,
    organization_id: UUID,
    role: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_db_session),
    _: None = Depends(verify_protection_service_key),
) -> EffectivePolicyPreview:
    return await get_effective_policies(db, connection_id, organization_id, role)


@router.get(
    "/orgs/{organization_id}/connections",
    response_model=List[ConnectionPolicyConfig],
)
async def list_org_connection_policies(
    organization_id: UUID,
    db: AsyncSession = Depends(get_async_db_session),
    _: None = Depends(verify_protection_service_key),
) -> List[ConnectionPolicyConfig]:
    return await list_connections_with_policies(db, organization_id)


# ---------------------------------------------------------------------------
# Column classification & predicate validation
# ---------------------------------------------------------------------------

@router.post(
    "/connections/{connection_id}/classify-columns",
    response_model=ColumnClassificationResponse,
)
async def classify_columns(
    connection_id: UUID,
    db: AsyncSession = Depends(get_async_db_session),
    _: None = Depends(verify_protection_service_key),
) -> ColumnClassificationResponse:
    schema = await _get_connection_schema(connection_id, db)
    tables_data = schema.get("tables", [])
    classifications = await _agent.classify_columns(tables_data)
    return ColumnClassificationResponse(
        connection_id=connection_id,
        classifications=classifications,
    )


@router.post("/validate-predicate", response_model=PredicateValidationResponse)
async def validate_predicate(
    body: PredicateValidationRequest,
    _: None = Depends(verify_protection_service_key),
) -> PredicateValidationResponse:
    return await _agent.validate_predicate(body.predicate_template, body.session_properties)

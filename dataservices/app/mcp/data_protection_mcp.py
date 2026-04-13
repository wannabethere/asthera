"""
Custom JSON-RPC over SSE — MCP server for data-protection tools.

Exposes tools that wrap the DataProtectionAgent and persistence service so that
external clients (Asthera gateway, IDE extensions, etc.) can generate, manage,
and preview RLS/CLS policies via standard MCP tool calls.

Wire-up: mounted on the FastAPI app at ``/mcp/data-protection``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid as _uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.data_protection_agent import DataProtectionAgent
from app.core.dependencies import get_async_db_session
from app.schemas.data_protection_api import (
    DataProtectionConfig,
    RLSPolicyDefinition,
    CLSPolicyDefinition,
    RoleDefinition,
)
from app.service.data_protection_service import (
    activate_connection_policies,
    get_effective_policies,
    list_connections_with_policies,
    load_config,
    load_connection_policies,
    save_connection_policies,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Shared agent singleton
_agent = DataProtectionAgent()

# ---------------------------------------------------------------------------
# Tool definitions (returned by tools/list)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "generate_data_protection_policies",
        "description": "Auto-generate RLS and CLS policies for a database connection by analysing its schema with an LLM.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "connection_id": {"type": "string", "description": "UUID of the connection"},
                "organization_id": {"type": "string", "description": "UUID of the organisation"},
                "business_context": {"type": "string", "description": "Free-text business context"},
                "generate_rls": {"type": "boolean", "default": True},
                "generate_cls": {"type": "boolean", "default": True},
            },
            "required": ["connection_id", "organization_id"],
        },
    },
    {
        "name": "generate_rls_policies",
        "description": "Generate Row-Level Security policies only for given tables.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "connection_id": {"type": "string"},
                "organization_id": {"type": "string"},
                "business_context": {"type": "string", "default": ""},
            },
            "required": ["connection_id", "organization_id"],
        },
    },
    {
        "name": "generate_cls_policies",
        "description": "Generate Column-Level Security policies only for given tables.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "connection_id": {"type": "string"},
                "organization_id": {"type": "string"},
                "business_context": {"type": "string", "default": ""},
            },
            "required": ["connection_id", "organization_id"],
        },
    },
    {
        "name": "classify_columns",
        "description": "Classify database columns by sensitivity level (PII, financial, health, confidential, public).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "connection_id": {"type": "string"},
            },
            "required": ["connection_id"],
        },
    },
    {
        "name": "list_connection_policies",
        "description": "Retrieve the current policy configuration for a connection.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "connection_id": {"type": "string"},
            },
            "required": ["connection_id"],
        },
    },
    {
        "name": "save_connection_policies",
        "description": "Persist a data-protection configuration for a connection (draft status).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "connection_id": {"type": "string"},
                "organization_id": {"type": "string"},
                "config": {"type": "object", "description": "DataProtectionConfig JSON"},
            },
            "required": ["connection_id", "organization_id", "config"],
        },
    },
    {
        "name": "activate_connection_policies",
        "description": "Transition connection policies from draft to active.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "connection_id": {"type": "string"},
            },
            "required": ["connection_id"],
        },
    },
    {
        "name": "validate_rls_predicate",
        "description": "Validate an RLS predicate template for syntax and injection safety.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "predicate_template": {"type": "string"},
                "session_properties": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["predicate_template"],
        },
    },
    {
        "name": "preview_effective_policies",
        "description": "Preview the merged (org + connection) effective policies, optionally filtered by role.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "connection_id": {"type": "string"},
                "organization_id": {"type": "string"},
                "role": {"type": "string", "description": "Optional role slug to filter by"},
            },
            "required": ["connection_id", "organization_id"],
        },
    },
    {
        "name": "get_policy_inheritance",
        "description": "Show which org-level policies a connection inherits and which are overridden.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "connection_id": {"type": "string"},
                "organization_id": {"type": "string"},
            },
            "required": ["connection_id", "organization_id"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

async def _get_schema_for_connection(connection_id: str, db: AsyncSession) -> dict:
    """Re-use the router helper to fetch raw schema."""
    from app.routers.data_protection_router import _get_connection_schema
    return await _get_connection_schema(_uuid.UUID(connection_id), db)


async def _handle_generate_data_protection_policies(args: dict, db: AsyncSession) -> dict:
    conn_id = _uuid.UUID(args["connection_id"])
    org_id = _uuid.UUID(args["organization_id"])
    schema = await _get_schema_for_connection(args["connection_id"], db)
    tables = schema.get("tables", [])

    config = await _agent.generate_policies(
        connection_id=conn_id,
        tables_data=tables,
        business_context=args.get("business_context", ""),
        generate_rls=args.get("generate_rls", True),
        generate_cls=args.get("generate_cls", True),
    )

    metadata = {"tables_analyzed": len(tables), "columns_classified": sum(len(t.get("columns", [])) for t in tables)}
    await save_connection_policies(db, conn_id, org_id, config, status="draft", generated_by="agent", generation_metadata=metadata)
    await db.commit()

    return {"status": "draft", "config": config.model_dump(), **metadata}


async def _handle_generate_rls_policies(args: dict, db: AsyncSession) -> dict:
    schema = await _get_schema_for_connection(args["connection_id"], db)
    result = await _agent.generate_rls_policies(schema.get("tables", []), args.get("business_context", ""))
    return result


async def _handle_generate_cls_policies(args: dict, db: AsyncSession) -> dict:
    schema = await _get_schema_for_connection(args["connection_id"], db)
    result = await _agent.generate_cls_policies(schema.get("tables", []), args.get("business_context", ""))
    return result


async def _handle_classify_columns(args: dict, db: AsyncSession) -> dict:
    schema = await _get_schema_for_connection(args["connection_id"], db)
    classifications = await _agent.classify_columns(schema.get("tables", []))
    return {"classifications": [c.model_dump() for c in classifications]}


async def _handle_list_connection_policies(args: dict, db: AsyncSession) -> dict:
    conn_id = _uuid.UUID(args["connection_id"])
    cfg = await load_connection_policies(db, conn_id)
    if cfg is None:
        return {"error": "No policies found for this connection"}
    return cfg.model_dump()


async def _handle_save_connection_policies(args: dict, db: AsyncSession) -> dict:
    conn_id = _uuid.UUID(args["connection_id"])
    org_id = _uuid.UUID(args["organization_id"])
    config = DataProtectionConfig(**args["config"])
    await save_connection_policies(db, conn_id, org_id, config, status="draft", generated_by="manual")
    await db.commit()
    return {"status": "saved", "connection_id": args["connection_id"]}


async def _handle_activate_connection_policies(args: dict, db: AsyncSession) -> dict:
    conn_id = _uuid.UUID(args["connection_id"])
    updated = await activate_connection_policies(db, conn_id)
    await db.commit()
    return {"activated": updated, "connection_id": args["connection_id"]}


async def _handle_validate_rls_predicate(args: dict, _db: AsyncSession) -> dict:
    result = await _agent.validate_predicate(
        args["predicate_template"],
        args.get("session_properties", []),
    )
    return result.model_dump()


async def _handle_preview_effective_policies(args: dict, db: AsyncSession) -> dict:
    conn_id = _uuid.UUID(args["connection_id"])
    org_id = _uuid.UUID(args["organization_id"])
    preview = await get_effective_policies(db, conn_id, org_id, args.get("role"))
    return preview.model_dump()


async def _handle_get_policy_inheritance(args: dict, db: AsyncSession) -> dict:
    conn_id = _uuid.UUID(args["connection_id"])
    org_id = _uuid.UUID(args["organization_id"])

    org_config = await load_config(db, org_id)
    conn_cfg = await load_connection_policies(db, conn_id)

    inherited_rls = [p.model_dump() for p in org_config.rls_policies]
    inherited_cls = [p.model_dump() for p in org_config.cls_policies]
    overridden_rls = []
    overridden_cls = []
    excluded = []

    if conn_cfg:
        overridden_rls = [p.model_dump() for p in conn_cfg.rls_overrides]
        overridden_cls = [p.model_dump() for p in conn_cfg.cls_overrides]
        excluded = list(conn_cfg.excluded_policy_ids)

    return {
        "inherited_rls_policies": inherited_rls,
        "inherited_cls_policies": inherited_cls,
        "overridden_rls_policies": overridden_rls,
        "overridden_cls_policies": overridden_cls,
        "excluded_policy_ids": excluded,
        "inheritance_mode": conn_cfg.inheritance_mode if conn_cfg else "inherit_override",
    }


# Map tool name → handler
_HANDLERS = {
    "generate_data_protection_policies": _handle_generate_data_protection_policies,
    "generate_rls_policies": _handle_generate_rls_policies,
    "generate_cls_policies": _handle_generate_cls_policies,
    "classify_columns": _handle_classify_columns,
    "list_connection_policies": _handle_list_connection_policies,
    "save_connection_policies": _handle_save_connection_policies,
    "activate_connection_policies": _handle_activate_connection_policies,
    "validate_rls_predicate": _handle_validate_rls_predicate,
    "preview_effective_policies": _handle_preview_effective_policies,
    "get_policy_inheritance": _handle_get_policy_inheritance,
}


# ---------------------------------------------------------------------------
# JSON-RPC dispatcher
# ---------------------------------------------------------------------------

def _jsonrpc_error(id_: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def _jsonrpc_result(id_: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


async def _dispatch(payload: dict, db: AsyncSession) -> dict:
    req_id = payload.get("id")
    method = payload.get("method", "")
    params = payload.get("params", {})

    if method == "tools/list":
        return _jsonrpc_result(req_id, {"tools": TOOL_DEFINITIONS})

    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        handler = _HANDLERS.get(tool_name)
        if handler is None:
            return _jsonrpc_error(req_id, -32601, f"Unknown tool: {tool_name}")
        try:
            result = await handler(arguments, db)
            return _jsonrpc_result(req_id, {"content": [{"type": "text", "text": json.dumps(result, default=str)}]})
        except Exception as e:
            logger.exception("MCP tool %s failed", tool_name)
            return _jsonrpc_error(req_id, -32000, str(e))

    if method == "initialize":
        return _jsonrpc_result(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "data-protection-mcp", "version": "1.0.0"},
        })

    return _jsonrpc_error(req_id, -32601, f"Method not found: {method}")


# ---------------------------------------------------------------------------
# SSE endpoint
# ---------------------------------------------------------------------------

@router.post("/sse")
async def mcp_sse(request: Request, db: AsyncSession = Depends(get_async_db_session)):
    """JSON-RPC over SSE transport for MCP tool calls."""
    body = await request.json()

    # Support batch requests
    if isinstance(body, list):
        results = [await _dispatch(item, db) for item in body]
    else:
        results = [await _dispatch(body, db)]

    async def event_stream():
        for r in results:
            yield f"data: {json.dumps(r, default=str)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/rpc")
async def mcp_rpc(request: Request, db: AsyncSession = Depends(get_async_db_session)):
    """Standard JSON-RPC endpoint (non-SSE) for simpler integrations."""
    body = await request.json()

    if isinstance(body, list):
        results = [await _dispatch(item, db) for item in body]
        return results
    else:
        return await _dispatch(body, db)

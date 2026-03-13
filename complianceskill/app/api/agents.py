"""
Agent Gateway API Endpoints

HTTP endpoints for agent invocation following the agent_adapter.md design.
These endpoints are called by the orchestration layer.
"""

import logging
from typing import Dict, Any, Optional
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.agent_invocation_service import get_agent_invocation_service, AgentInvocationService
from app.adapters.registry import get_agent_registry, AgentRegistry
from app.adapters.base import AgentEvent, EventType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/agents", tags=["agents"])


# ============================================================================
# Request/Response Models
# ============================================================================

class InvokeRequest(BaseModel):
    """Agent invocation request"""
    agent_id: str = Field(..., description="Agent identifier")
    input: str = Field(..., description="User query or agent-specific input")
    thread_id: str = Field(..., description="Thread identifier")
    run_id: Optional[str] = Field(None, description="Run identifier (auto-generated if not provided)")
    step_id: Optional[str] = Field("step_1", description="Plan step identifier")
    step_index: Optional[int] = Field(0, description="Step index in multi-agent plan")
    timeout_seconds: Optional[int] = Field(60, description="Execution timeout")
    use_context_token: Optional[bool] = Field(True, description="Use context token instead of inline context")
    data_scope: Optional[Dict[str, Any]] = Field(None, description="Data scoping filters")
    claims: Optional[Dict[str, Any]] = Field(None, description="Optional JWT claims override (for testing)")


class ContextTokenRequest(BaseModel):
    """Context token resolution request (for agent-side fetching)"""
    token: str = Field(..., description="Context token")


class ClaimsDependency:
    """
    Dependency for extracting JWT claims from request.
    
    JWT is OPTIONAL for testing. If not provided, returns default permissive claims.
    In production, this would verify JWT and extract claims.
    """
    
    @staticmethod
    def get_default_claims() -> Dict[str, Any]:
        """
        Get default permissive claims for testing when JWT is not provided.
        
        Returns:
            Default claims that allow access to all agents
        """
        return {
            "sub": "test_user",
            "tenant_id": "test_tenant",
            "roles": ["compliance_analyst", "vuln_reader", "admin"],
            "agent_access": [],  # Empty list means access to all agents
            "feature_flags": {
                "multi_agent": True,
                "max_parallel_agents": 10,
                "long_term_memory": True,
            },
            "data_scope": {
                "asset_groups": [],
                "frameworks": [],
            },
            "context_tier": "full",
        }
    
    @staticmethod
    async def get_claims(request: Request) -> Dict[str, Any]:
        """
        Extract and verify JWT claims from request.
        
        JWT is OPTIONAL for testing:
        - If Authorization header present: try to verify JWT (not implemented yet)
        - If no JWT: return default permissive claims
        
        In production, this would:
        1. Extract JWT from Authorization header or cookie
        2. Verify signature and expiry
        3. Extract claims
        4. Resolve tenant_id, roles, agent_access, etc.
        
        Returns:
            Claims dict (either from JWT or default)
        """
        # Try to extract JWT from Authorization header
        auth_header = request.headers.get("Authorization", "")
        
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
            
            # TODO: Implement actual JWT verification
            # For now, if token is provided but verification not implemented,
            # we could parse it or return default claims
            # For testing, we'll just log and use default
            logger.debug(f"JWT token provided but verification not implemented yet, using default claims")
            return ClaimsDependency.get_default_claims()
        
        # No JWT provided - use default permissive claims for testing
        logger.debug("No JWT token provided, using default permissive claims for testing")
        return ClaimsDependency.get_default_claims()


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/invoke")
async def invoke_agent(
    request: InvokeRequest,
    claims_from_header: Dict[str, Any] = Depends(ClaimsDependency.get_claims),
    invocation_service = Depends(get_agent_invocation_service),
):
    """
    Invoke an agent and stream events.
    
    This is the main endpoint called by the orchestration layer.
    Returns Server-Sent Events (SSE) stream of AgentEvent objects.
    
    JWT is OPTIONAL for testing:
    - If Authorization header present: will attempt to extract claims (verification not implemented yet)
    - If claims provided in request body: will use those (overrides header)
    - If neither: uses default permissive claims for testing
    """
    # Use claims from request body if provided, otherwise use from header/dependency
    claims = request.claims if request.claims is not None else claims_from_header
    
    # Generate run_id if not provided
    run_id = request.run_id or str(uuid4())
    
    # Build payload
    payload = {
        "input": request.input,
        "thread_id": request.thread_id,
        "run_id": run_id,
        "step_id": request.step_id,
        "step_index": request.step_index,
        "timeout_seconds": request.timeout_seconds,
        "data_scope": request.data_scope or {},
    }
    
    # Stream agent events
    async def event_stream():
        try:
            async for event in invocation_service.invoke_agent(
                agent_id=request.agent_id,
                payload=payload,
                claims=claims,
                use_context_token=request.use_context_token,
            ):
                yield event.to_sse()
        except Exception as e:
            logger.error(f"Agent invocation error: {e}", exc_info=True)
            error_event = AgentEvent(
                type=EventType.ERROR,
                agent_id=request.agent_id,
                run_id=run_id,
                step_id=request.step_id,
                tenant_id=claims.get("tenant_id", "default"),
                data={"error": str(e)},
                metadata={},
            )
            yield error_event.to_sse()
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get("/internal/ctx/{token}")
async def resolve_context(
    token: str,
    invocation_service = Depends(get_agent_invocation_service),
):
    """
    Internal endpoint for agents to fetch context by token.
    
    This is called by agents when they receive a ctx_token in the payload.
    The gateway mints the token, agents fetch the context here.
    """
    try:
        context = await invocation_service.resolve_context_token(token)
        return context.model_dump()
    except Exception as e:
        logger.error(f"Context resolution error: {e}", exc_info=True)
        raise HTTPException(status_code=404, detail=f"Context not found: {e}")


@router.get("/registry")
async def list_agents(
    claims: Dict[str, Any] = Depends(ClaimsDependency.get_claims),
    registry = Depends(get_agent_registry),
):
    """
    List available agents filtered by JWT claims.
    
    Returns catalog of agents the user has access to.
    """
    accessible = registry.agents_for_claims(claims)
    return {
        "agents": [meta.to_catalog_entry() for meta in accessible],
        "count": len(accessible),
    }


@router.get("/registry/{agent_id}")
async def get_agent_meta(
    agent_id: str,
    claims: Dict[str, Any] = Depends(ClaimsDependency.get_claims),
    registry = Depends(get_agent_registry),
):
    """
    Get metadata for a specific agent.
    
    Returns full AgentMeta if user has access.
    """
    try:
        meta = registry.get_meta(agent_id)
        
        # Check access (only if agent_access list is non-empty)
        # Empty list means access to all agents (permissive for testing)
        agent_access = claims.get("agent_access", [])
        if agent_access and len(agent_access) > 0 and agent_id not in agent_access:
            raise HTTPException(status_code=403, detail="Agent access denied")
        
        return {
            "agent_id": meta.agent_id,
            "display_name": meta.display_name,
            "framework": meta.framework,
            "capabilities": meta.capabilities,
            "context_window_tokens": meta.context_window_tokens,
            "routing_tags": meta.routing_tags,
        }
    except Exception as e:
        logger.error(f"Failed to get agent metadata: {e}", exc_info=True)
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

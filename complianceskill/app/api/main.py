"""
Compliance Skill API Service

FastAPI service that exposes the compliance workflow as HTTP endpoints.
This allows the compliance skill to run as a separate service.

Uses the existing settings and dependency injection system from app.core.
"""
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import Dict, Any, Optional, Literal
import logging
import json
import asyncio
from datetime import datetime

from app.core.settings import get_settings, Settings
from app.core.dependencies import get_dependencies
from app.core.telemetry import (
    setup_telemetry,
    instrument_workflow_invocation,
    instrument_workflow_stream,
    instrument_workflow_stream_events,
)
from app.agents.detectiontriageworkflows.workflow import create_compliance_app
from app.agents.mdlworkflows.dt_workflow import create_detection_triage_app, create_dt_initial_state
from app.agents.state import EnhancedCompliancePipelineState
from app.api.session_manager import (
    SessionManager,
    get_session_manager,
    WorkflowType,
    SessionStatus,
    Checkpoint,
)
from app.api.state_transformer import (
    transform_to_external_state,
    extract_checkpoint_from_state,
)
from app.services.dt_workflow_service import get_dt_workflow_service
from app.services.compliance_workflow_service import get_compliance_workflow_service

# Configure logging before importing other modules
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get settings early to configure the app
settings = get_settings()

# Create FastAPI app with settings
app = FastAPI(
    title="Compliance Skill API",
    description="API service for compliance automation workflow",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Configure CORS from settings
cors_origins = ["*"] if settings.DEBUG else []  # Configure appropriately for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize dependencies and services on startup."""
    logger.info("Starting Compliance Skill API Service...")
    logger.info(f"Environment: {settings.ENV}, Debug: {settings.DEBUG}")
    logger.info(f"API Host: {settings.API_HOST}, Port: {settings.API_PORT}")
    logger.info(f"Vector Store: {settings.VECTOR_STORE_TYPE}, Cache: {settings.CACHE_TYPE}")
    
    # Setup OpenTelemetry telemetry (if enabled in settings)
    if settings.OPENTELEMETRY_ENABLED:
        try:
            setup_telemetry()  # Uses settings from .env
            logger.info("OpenTelemetry telemetry initialized")
        except Exception as e:
            logger.warning(f"Failed to setup telemetry: {e}", exc_info=True)
            # Don't fail startup if telemetry setup fails
    else:
        logger.info("OpenTelemetry telemetry is disabled (OPENTELEMETRY_ENABLED=false)")
    
    # Initialize dependencies (this sets up database, vector store, cache, etc.)
    # get_dependencies is async, so we initialize it here
    try:
        dependencies = await get_dependencies()
        logger.info("Dependencies initialized successfully")
        
        # Store dependencies in app state for access in endpoints
        app.state.dependencies = dependencies
        app.state.settings = settings
        
    except Exception as e:
        logger.error(f"Failed to initialize dependencies: {e}", exc_info=True)
        # Don't fail startup, but log the error
        # Dependencies will be initialized lazily when needed
        app.state.dependencies = None
        app.state.settings = settings
        logger.warning("Service will continue without pre-initialized dependencies")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    logger.info("Shutting down Compliance Skill API Service...")
    # Cleanup would go here (close database connections, etc.)


# Global workflow app instances
_compliance_app = None
_dt_app = None


def get_workflow_app(
    workflow_type: WorkflowType = WorkflowType.COMPLIANCE,
    dependencies: Optional[Dict[str, Any]] = None,
):
    """
    Get or create workflow app instance.
    
    Args:
        workflow_type: Type of workflow (compliance or detection_triage)
        dependencies: Optional dependencies dict from get_dependencies()
                     If not provided, will try to get from app state
    
    Returns:
        Compiled LangGraph application
    """
    global _compliance_app, _dt_app
    
    # Use dependencies if available (for proper initialization)
    if dependencies is None:
        # Try to get from app state if available
        if hasattr(app, 'state') and hasattr(app.state, 'dependencies'):
            dependencies = app.state.dependencies
    
    if workflow_type == WorkflowType.COMPLIANCE:
        if _compliance_app is None:
            _compliance_app = create_compliance_app()
            logger.info("Compliance workflow app created successfully")
        return _compliance_app
    elif workflow_type == WorkflowType.DETECTION_TRIAGE:
        if _dt_app is None:
            _dt_app = create_detection_triage_app()
            logger.info("Detection & Triage workflow app created successfully")
        return _dt_app
    else:
        raise ValueError(f"Unknown workflow type: {workflow_type}")


def format_sse_event(event_type: str, data: dict) -> str:
    """Format a Server-Sent Event."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    health_status = {
        "status": "healthy",
        "service": "compliance-skill-api",
        "version": "1.0.0",
        "environment": settings.ENV
    }
    
    # Check if dependencies are initialized
    if hasattr(app, 'state') and hasattr(app.state, 'dependencies'):
        dependencies = app.state.dependencies
        if dependencies:
            health_status["dependencies"] = "initialized"
        else:
            health_status["dependencies"] = "not_initialized"
            health_status["status"] = "degraded"
    else:
        health_status["dependencies"] = "unknown"
    
    return health_status


@app.post("/workflow/execute")
async def execute_workflow(request: Dict[str, Any]):
    """
    Execute workflow with streaming (supports both compliance and detection_triage).
    
    Request body:
    {
        "user_query": str,
        "session_id": str,
        "workflow_type": "compliance" | "detection_triage" (default: "compliance"),
        "initial_state": Optional[Dict]  # Additional state fields
    }
    
    Returns: SSE stream with workflow execution events and external state updates
    """
    try:
        user_query = request.get("user_query")
        if not user_query:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_query is required"
            )
        
        session_id = request.get("session_id", f"session-{datetime.now().isoformat()}")
        workflow_type_str = request.get("workflow_type", "compliance")
        workflow_type = WorkflowType(workflow_type_str)
        initial_state_data = request.get("initial_state", {})
        
        # Get dependencies for service
        dependencies = getattr(app.state, 'dependencies', None) if hasattr(app, 'state') else None
        
        # Route to appropriate service based on workflow type
        if workflow_type == WorkflowType.DETECTION_TRIAGE:
            service = get_dt_workflow_service()
        else:
            service = get_compliance_workflow_service()
        
        async def generate():
            """Generate streaming response using service layer."""
            async for event in service.execute_workflow_stream(
                user_query=user_query,
                session_id=session_id,
                initial_state_data=initial_state_data,
                dependencies=dependencies,
            ):
                yield format_sse_event(event["event"], event["data"])
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    
    except Exception as e:
        logger.error(f"Error in execute_workflow: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/workflow/invoke")
async def invoke_workflow(request: Dict[str, Any]):
    """
    Execute workflow synchronously (non-streaming) - supports both compliance and detection_triage.
    
    Request body:
    {
        "user_query": str,
        "session_id": str,
        "workflow_type": "compliance" | "detection_triage" (default: "compliance"),
        "initial_state": Optional[Dict]
    }
    
    Returns: Complete workflow state and session information
    """
    try:
        user_query = request.get("user_query")
        if not user_query:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_query is required"
            )
        
        session_id = request.get("session_id", f"session-{datetime.now().isoformat()}")
        workflow_type_str = request.get("workflow_type", "compliance")
        workflow_type = WorkflowType(workflow_type_str)
        initial_state_data = request.get("initial_state", {})
        
        # Get dependencies for service
        dependencies = getattr(app.state, 'dependencies', None) if hasattr(app, 'state') else None
        
        # Route to appropriate service based on workflow type
        if workflow_type == WorkflowType.DETECTION_TRIAGE:
            service = get_dt_workflow_service()
        else:
            service = get_compliance_workflow_service()
        
        # Execute workflow
        result = await service.execute_workflow_invoke(
                user_query=user_query,
                session_id=session_id,
            initial_state_data=initial_state_data,
            dependencies=dependencies,
        )
        
        return result
    
    except Exception as e:
        logger.error(f"Error in invoke_workflow: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/workflow/resume")
async def resume_workflow(request: Dict[str, Any]):
    """
    Resume workflow execution from a checkpoint - supports both compliance and detection_triage.
    
    Request body:
    {
        "session_id": str,
        "checkpoint_id": str,  # ID of the checkpoint to resolve
        "user_input": Dict,     # User input for checkpoint
        "approved": bool       # Whether checkpoint is approved (default: True)
    }
    
    Returns: SSE stream continuing from checkpoint
    """
    try:
        session_id = request.get("session_id")
        if not session_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="session_id is required"
            )
        
        checkpoint_id = request.get("checkpoint_id")
        if not checkpoint_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="checkpoint_id is required"
            )
        
        user_input = request.get("user_input", {})
        approved = request.get("approved", True)
        
        # Get session to determine workflow type
        session_manager = get_session_manager()
        session = session_manager.get_session(session_id)
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )
        
        if session.status != SessionStatus.CHECKPOINT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Session {session_id} is not at a checkpoint (current status: {session.status.value})"
            )
        
        # Get dependencies for service
        dependencies = getattr(app.state, 'dependencies', None) if hasattr(app, 'state') else None
        
        # Route to appropriate service based on workflow type
        if session.workflow_type == WorkflowType.DETECTION_TRIAGE:
            service = get_dt_workflow_service()
        else:
            service = get_compliance_workflow_service()
        
        async def generate():
            """Generate streaming response continuing from checkpoint."""
            async for event in service.resume_workflow_stream(
                session_id=session_id,
                checkpoint_id=checkpoint_id,
                user_input=user_input,
                approved=approved,
                dependencies=dependencies,
            ):
                yield format_sse_event(event["event"], event["data"])
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Validation error in resume_workflow: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error in resume_workflow: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/workflow/session/{session_id}")
async def get_session_status(session_id: str):
    """
    Get current session status and state.
    
    Returns: Session information including status, nodes, checkpoints, and external state
    """
    session_manager = get_session_manager()
    session = session_manager.get_session(session_id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )
    
    return {
        "session": session.to_dict(),
    }


@app.get("/workflow/sessions")
async def list_sessions(
    workflow_type: Optional[str] = None,
    status_filter: Optional[str] = None,
):
    """
    List all workflow sessions.
    
    Query parameters:
    - workflow_type: Filter by workflow type ("compliance" or "detection_triage")
    - status_filter: Filter by status ("pending", "running", "checkpoint", "completed", "failed")
    
    Returns: List of sessions
    """
    session_manager = get_session_manager()
    
    workflow_type_enum = None
    if workflow_type:
        try:
            workflow_type_enum = WorkflowType(workflow_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid workflow_type: {workflow_type}"
            )
    
    sessions = session_manager.list_sessions(workflow_type=workflow_type_enum)
    
    # Filter by status if provided
    if status_filter:
        try:
            status_enum = SessionStatus(status_filter)
            sessions = [s for s in sessions if s.status == status_enum]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status_filter: {status_filter}"
            )
    
    return {
        "sessions": [session.to_dict() for session in sessions],
        "count": len(sessions),
    }


# ============================================================================
# Detection & Triage (DT) Workflow API Routes
# ============================================================================

@app.post("/dt/execute")
async def execute_dt_workflow(request: Dict[str, Any]):
    """
    Execute Detection & Triage workflow with streaming.
    
    Request body:
    {
        "user_query": str,
        "session_id": str,
        "initial_state": Optional[Dict]  # Additional state fields
    }
    
    Returns: SSE stream with workflow execution events and external state updates
    """
    try:
        user_query = request.get("user_query")
        if not user_query:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_query is required"
            )
        
        session_id = request.get("session_id", f"dt-session-{datetime.now().isoformat()}")
        initial_state_data = request.get("initial_state", {})
        
        # Get DT workflow service
        dt_service = get_dt_workflow_service()
        
        async def generate():
            """Generate streaming response using DT service."""
            async for event in dt_service.execute_workflow_stream(
                user_query=user_query,
                session_id=session_id,
                initial_state_data=initial_state_data,
            ):
                yield format_sse_event(event["event"], event["data"])
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    
    except Exception as e:
        logger.error(f"Error in execute_dt_workflow: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/dt/invoke")
async def invoke_dt_workflow(request: Dict[str, Any]):
    """
    Execute Detection & Triage workflow synchronously (non-streaming).
    
    Request body:
    {
        "user_query": str,
        "session_id": str,
        "initial_state": Optional[Dict]
    }
    
    Returns: Complete workflow state and session information
    """
    try:
        user_query = request.get("user_query")
        if not user_query:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_query is required"
            )
        
        session_id = request.get("session_id", f"dt-session-{datetime.now().isoformat()}")
        initial_state_data = request.get("initial_state", {})
        
        # Get DT workflow service
        dt_service = get_dt_workflow_service()
        
        # Execute workflow
        result = await dt_service.execute_workflow_invoke(
            user_query=user_query,
            session_id=session_id,
            initial_state_data=initial_state_data,
        )
        
        return result
    
    except Exception as e:
        logger.error(f"Error in invoke_dt_workflow: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/dt/resume")
async def resume_dt_workflow(request: Dict[str, Any]):
    """
    Resume Detection & Triage workflow execution from a checkpoint.
    
    Request body:
    {
        "session_id": str,
        "checkpoint_id": str,  # ID of the checkpoint to resolve
        "user_input": Dict,     # User input for checkpoint
        "approved": bool       # Whether checkpoint is approved (default: True)
    }
    
    Returns: SSE stream continuing from checkpoint
    """
    try:
        session_id = request.get("session_id")
        if not session_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="session_id is required"
            )
        
        checkpoint_id = request.get("checkpoint_id")
        if not checkpoint_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="checkpoint_id is required"
            )
        
        user_input = request.get("user_input", {})
        approved = request.get("approved", True)
        
        # Get DT workflow service
        dt_service = get_dt_workflow_service()
        
        async def generate():
            """Generate streaming response continuing from checkpoint."""
            async for event in dt_service.resume_workflow_stream(
                session_id=session_id,
                checkpoint_id=checkpoint_id,
                user_input=user_input,
                approved=approved,
            ):
                yield format_sse_event(event["event"], event["data"])
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    
    except ValueError as e:
        logger.warning(f"Validation error in resume_dt_workflow: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error in resume_dt_workflow: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/dt/session/{session_id}")
async def get_dt_session_status(session_id: str):
    """
    Get current Detection & Triage session status and state.
    
    Returns: Session information including status, nodes, checkpoints, and external state
    """
    session_manager = get_session_manager()
    session = session_manager.get_session(session_id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )
    
    if session.workflow_type != WorkflowType.DETECTION_TRIAGE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session {session_id} is not a Detection & Triage session"
        )
    
    return {
        "session": session.to_dict(),
    }


@app.get("/dt/sessions")
async def list_dt_sessions(
    status_filter: Optional[str] = None,
):
    """
    List all Detection & Triage workflow sessions.
    
    Query parameters:
    - status_filter: Filter by status ("pending", "running", "checkpoint", "completed", "failed")
    
    Returns: List of DT sessions
    """
    session_manager = get_session_manager()
    sessions = session_manager.list_sessions(workflow_type=WorkflowType.DETECTION_TRIAGE)
    
    # Filter by status if provided
    if status_filter:
        try:
            status_enum = SessionStatus(status_filter)
            sessions = [s for s in sessions if s.status == status_enum]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status_filter: {status_filter}"
            )
    
    return {
        "sessions": [session.to_dict() for session in sessions],
        "count": len(sessions),
    }


if __name__ == "__main__":
    import uvicorn
    
    # Use settings for configuration (with environment variable overrides)
    import os
    host = os.getenv("HOST", settings.API_HOST)
    port = int(os.getenv("PORT", str(settings.API_PORT)))
    reload = os.getenv("DEBUG", str(settings.DEBUG)).lower() == "true"
    log_level = settings.LOG_LEVEL.lower()
    
    logger.info(f"Starting Compliance Skill API on {host}:{port}")
    logger.info(f"Debug mode: {reload}, Log level: {log_level}")
    
    uvicorn.run(
        "app.api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level
    )

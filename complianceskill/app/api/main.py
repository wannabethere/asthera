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
from app.services.csod_workflow_service import get_csod_workflow_service
from app.services.dashboard_agent_service import get_dashboard_agent_service
from app.api.agents import router as agents_router
from app.api.routes.conversation import router as conversation_router
from app.api.routes.workflow_integration import router as workflow_integration_router

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
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
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

# Include routers
app.include_router(agents_router)
app.include_router(conversation_router)
app.include_router(workflow_integration_router)


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
    
    # Validate document stores BEFORE registering agents
    # This ensures all collections are accessible before agents try to use them
    try:
        from app.core.dependencies import get_doc_store_provider, validate_document_stores
        
        logger.info("Validating document stores before agent registration...")
        doc_store_provider = get_doc_store_provider()
        validation_results = validate_document_stores(doc_store_provider)
        
        if not validation_results["valid"]:
            logger.warning(
                f"Document store validation found issues: {len(validation_results['stores_failed'])} stores failed. "
                f"Errors: {validation_results['errors']}"
            )
            logger.warning("Agent registration will continue, but some agents may not work correctly.")
        else:
            logger.info(
                f"✓ Document store validation passed: {validation_results['stores_validated']} stores validated, "
                f"{len(validation_results['collections'])} collections available"
            )
    except Exception as e:
        logger.error(f"Document store validation failed: {e}", exc_info=True)
        logger.warning("Agent registration will continue, but document stores may not be available.")

    # Initialize workflow and agent services (warm up singletons and compile workflow apps)
    deps = getattr(app.state, "dependencies", None)
    try:
        svc = get_compliance_workflow_service()
        svc.get_workflow_app(dependencies=deps)
        logger.info("Compliance workflow service started")
    except Exception as e:
        logger.warning(f"Compliance workflow service init failed: {e}", exc_info=True)

    try:
        svc = get_dt_workflow_service()
        svc.get_workflow_app()
        logger.info("Detection & Triage workflow service started")
    except Exception as e:
        logger.warning(f"DT workflow service init failed: {e}", exc_info=True)

    try:
        svc = get_csod_workflow_service()
        svc.get_workflow_app(dependencies=deps)
        logger.info("CSOD workflow service started")
    except Exception as e:
        logger.warning(f"CSOD workflow service init failed: {e}", exc_info=True)

    try:
        get_dashboard_agent_service()
        logger.info("Dashboard agent service started")
    except Exception as e:
        logger.warning(f"Dashboard agent service init failed: {e}", exc_info=True)
    
    # Initialize LangGraph checkpointer (must be before agent registration)
    try:
        from app.core.checkpointer_provider import init_checkpointer
        cp = await init_checkpointer()
        logger.info(f"✓ Checkpointer initialized: {type(cp).__name__}")
    except Exception as e:
        logger.warning(f"Checkpointer init failed (will use MemorySaver fallback): {e}")

    # Register agents with adapter system
    # This happens AFTER document store validation to ensure stores are ready
    try:
        from app.services.agent_registration import register_all_agents
        logger.info("Registering agents with adapter system...")
        register_all_agents()
        logger.info("✓ Agent adapter system initialized successfully")
    except Exception as e:
        logger.error(f"Agent registration failed: {e}", exc_info=True)
        logger.warning("Some agents may not be available. Check logs for details.")

    # Start memory watchdog (monitors RSS, warns at 2GB, forces GC at 4GB)
    try:
        from app.core.memory_watchdog import start_memory_watchdog
        start_memory_watchdog()
    except Exception as e:
        logger.warning(f"Memory watchdog failed to start: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    logger.info("Shutting down Compliance Skill API Service...")
    try:
        from app.core.memory_watchdog import stop_memory_watchdog
        stop_memory_watchdog()
    except Exception:
        pass


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
        "workflow_type": "compliance" | "detection_triage" | "csod" (default: "compliance"),
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
        elif workflow_type == WorkflowType.CSOD:
            service = get_csod_workflow_service()
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


@app.post("/workflow/preview_generator")
async def preview_generator(request: Dict[str, Any]):
    """
    Generate metric/KPI/table previews from Phase 1 output.

    Called by the frontend after Phase 1 completes.  Accepts the
    recommendations, NL queries, or data-intelligence outputs produced
    by Phase 1 and returns preview cards with Vega-Lite specs, dummy data,
    summaries, and insights.

    Request body:
    {
        "session_id": str,
        "csod_intent": str,
        "csod_primary_area": str,
        "csod_resolved_schemas": list,
        "csod_metric_recommendations": list,   # metrics path
        "csod_kpi_recommendations": list,
        "csod_table_recommendations": list,
        "csod_adhoc_nl_queries": list,          # adhoc/RCA path (optional)
        "csod_data_discovery_results": list,    # data intel (optional)
        "csod_test_cases": list,                # data intel (optional)
        "csod_data_lineage_results": list,      # data intel (optional)
        "csod_data_quality_results": list,      # data intel (optional)
    }

    Returns: SSE stream with preview_start, state_update (metric_previews), preview_complete
    """
    try:
        session_id = request.get("session_id", f"preview-{datetime.now().isoformat()}")
        service = get_csod_workflow_service()

        async def generate():
            async for event in service.execute_preview_generator_stream(
                session_id=session_id,
                preview_input=request,
            ):
                yield format_sse_event(event["event"], event["data"])

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as e:
        logger.error(f"Error in preview_generator: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@app.post("/workflow/preview_item")
async def preview_item(request: Dict[str, Any]):
    """
    Generate a single preview card (one metric, KPI, or table).

    Called by the frontend per-card after rendering placeholder containers.
    Each call is isolated — one LLM call, one preview returned.

    Request body:
    {
        "name": str,                    # required
        "item_type": "metric"|"kpi"|"table",  # required
        "description": str,
        "nl_question": str,
        "focus_area": str,
        "intent": str,
        "source_tables": [str],
        "columns": [dict|str],          # for tables
        "reasoning": str,               # LLM reasoning context
        "plan_context": str,            # analysis plan context
        "project_id": str,
        "index": int                    # for deterministic dummy data seed
    }

    Returns: JSON preview dict
    """
    try:
        from app.agents.csod.csod_nodes.preview_generator import generate_single_preview

        name = request.get("name") or request.get("metric_name") or "Unnamed"
        item_type = request.get("item_type", "metric")

        preview = await generate_single_preview(
            name=name,
            item_type=item_type,
            description=request.get("description", ""),
            nl_question=request.get("nl_question") or request.get("natural_language_question", ""),
            focus_area=request.get("focus_area", ""),
            intent=request.get("intent", ""),
            source_tables=request.get("source_tables") or request.get("source_schemas", []),
            columns=request.get("columns") or request.get("column_metadata", []),
            reasoning=request.get("reasoning", ""),
            plan_context=request.get("plan_context", ""),
            project_id=request.get("project_id", ""),
            project_ids=request.get("project_ids"),
            index=request.get("index", 0),
        )

        return preview

    except Exception as e:
        logger.error(f"Error in preview_item: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@app.post("/workflow/global_filter/recommend")
async def global_filter_recommend(request: Dict[str, Any]):
    """
    Standalone endpoint — recommend a global filter configuration after metrics
    and the gold model are known.  Callers may pass state fields directly without
    needing a full workflow session.

    Request body (mirrors CSODState fields that the node reads):
    {
        "csod_resolved_schemas": [...],
        "csod_metric_recommendations": [...],
        "csod_kpi_recommendations": [...],
        "csod_generated_gold_model_sql": [...],
        "csod_intent": str,
        "user_query": str
    }

    Returns GlobalFilterConfig dict:
    {
        "filters": [{id, label, filter_type, column, table, sql_fragment,
                     operator, default_value, applies_to, is_global, reasoning}],
        "primary_date_field": str,
        "primary_date_table": str,
        "reasoning": str,
        "refinement_suggestions": [str],
        "source": "global_filter_recommender"
    }
    """
    try:
        from app.agents.shared.global_filter_recommender import GlobalFilterRecommender

        config = await GlobalFilterRecommender().recommend(
            resolved_schemas=request.get("csod_resolved_schemas") or [],
            metric_recommendations=request.get("csod_metric_recommendations") or [],
            kpi_recommendations=request.get("csod_kpi_recommendations") or [],
            gold_model_sql=request.get("csod_generated_gold_model_sql") or [],
            intent=request.get("csod_intent", ""),
            user_query=request.get("user_query", ""),
        )
        return config.model_dump()

    except Exception as e:
        logger.error("Error in global_filter_recommend: %s", e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.post("/workflow/global_filter/refine")
async def global_filter_refine(request: Dict[str, Any]):
    """
    Follow-up Q&A endpoint — refine the global filter configuration based on
    user feedback.  Preserves a conversation history so multiple turns are
    supported without losing prior context.

    Request body:
    {
        "global_filter_config": { ...GlobalFilterConfig dict... },
        "user_message": str,
        "history": [{"role": "user"|"assistant", "content": str}]   // optional
    }

    Returns updated GlobalFilterConfig dict (same shape as /recommend).
    """
    try:
        from app.agents.shared.global_filter_recommender import (
            GlobalFilterConfig,
            GlobalFilterRecommender,
        )

        raw_config = request.get("global_filter_config")
        if not raw_config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="global_filter_config is required",
            )
        user_message = request.get("user_message", "").strip()
        if not user_message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_message is required",
            )

        current_config = GlobalFilterConfig(**raw_config)
        history = request.get("history") or []

        updated = await GlobalFilterRecommender().refine(
            current_config=current_config,
            user_message=user_message,
            history=history,
        )
        return updated.model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in global_filter_refine: %s", e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.post("/workflow/preview/chart_adjust")
async def preview_chart_adjust(request: Dict[str, Any]):
    """
    Adjust the chart type / axes for an existing preview card.

    In demo mode (DEMO_FAKE_SQL_AND_INSIGHTS=False) handled entirely in-process.
    Request mirrors ChartAdjustmentRequest from /chart-adjustment/adjust so
    astherabackend can use the same payload for both fake and live paths.

    Request body:
    {
        "query": str,                        # original NL question
        "sql": str,                          # generated SQL (empty in demo)
        "chart_schema": dict,                # current vega-lite spec
        "adjustment_option": {
            "chart_type": "bar|line|pie|...",
            "x_axis": str,
            "y_axis": str
        },
        "result_data": dict,                 # {columns, rows} from the preview card
        "project_id": str,
        "project_ids": [str]
    }

    Returns ChartAdjustmentResultResponse shape:
    {
        "status": "finished",
        "response": {"reasoning": str, "chart_type": str, "chart_schema": dict}
    }
    """
    try:
        from app.agents.csod.csod_nodes.preview_generator import fake_chart_adjust

        result = await fake_chart_adjust(
            query=request.get("query", ""),
            sql=request.get("sql", ""),
            chart_schema=request.get("chart_schema", {}),
            adjustment_option=request.get("adjustment_option", {}),
            result_data=request.get("result_data"),
            project_id=request.get("project_id", ""),
            project_ids=request.get("project_ids"),
        )
        return result
    except Exception as e:
        logger.error(f"Error in preview_chart_adjust: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.post("/workflow/preview/drill_down")
async def preview_drill_down(request: Dict[str, Any]):
    """
    Drill into an existing preview card to get a sub-level view.

    In demo mode handled in-process.  Request mirrors SQLExpansionRequest
    from /sql-helper/sql-expansion so astherabackend can use the same
    payload for both fake and live paths.

    Request body:
    {
        "name": str,                         # parent card name
        "item_type": "metric|kpi|table",
        "nl_question": str,                  # parent NL question
        "query": str,                        # drill NL question (alias for nl_question)
        "sql": str,                          # parent SQL (empty in demo)
        "drill_dimension": str,              # column/field to drill into
        "drill_value": str,                  # value to filter on
        "parent_result_data": dict,          # {columns, rows} from parent card
        "source_tables": [str],
        "project_id": str,
        "project_ids": [str],
        "index": int
    }

    Returns a full preview card dict (same shape as /workflow/preview_item).
    """
    try:
        from app.agents.csod.csod_nodes.preview_generator import fake_drill_down

        name = request.get("name", "Drill-down")
        result = await fake_drill_down(
            name=name,
            item_type=request.get("item_type", "metric"),
            nl_question=request.get("nl_question") or request.get("query", ""),
            drill_dimension=request.get("drill_dimension", ""),
            drill_value=request.get("drill_value", ""),
            parent_result_data=request.get("parent_result_data"),
            source_tables=request.get("source_tables"),
            project_id=request.get("project_id", ""),
            project_ids=request.get("project_ids"),
            index=request.get("index", 0),
        )
        return result
    except Exception as e:
        logger.error(f"Error in preview_drill_down: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.post("/workflow/preview/annotate")
async def preview_annotate(request: Dict[str, Any]):
    """
    Inject an annotation into an existing preview card's vega-lite spec.

    Annotations are handled locally (vega-lite layer injection).
    The real path will send the spec + instruction to an LLM; the fake
    path produces a deterministic annotation layer.

    Request body:
    {
        "vega_lite_spec": dict,              # current chart spec to annotate
        "annotation_text": str,              # label / note to add
        "annotation_type": "text|rule|point",
        "x_value": any,                      # data-space x coord (optional)
        "y_value": any,                      # data-space y coord (optional)
        "color": str                         # hex color (default #ff9800)
    }

    Returns:
    {
        "vega_lite_spec": dict,              # updated spec with annotation layer
        "annotations": [{"text", "x_value", "y_value", "type", "color"}]
    }
    """
    try:
        from app.agents.csod.csod_nodes.preview_generator import fake_annotate

        result = fake_annotate(
            vega_lite_spec=request.get("vega_lite_spec", {}),
            annotation_text=request.get("annotation_text", ""),
            annotation_type=request.get("annotation_type", "text"),
            x_value=request.get("x_value"),
            y_value=request.get("y_value"),
            color=request.get("color", "#ff9800"),
        )
        return result
    except Exception as e:
        logger.error(f"Error in preview_annotate: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.post("/workflow/dashboard/recommend")
async def recommend_dashboard_templates(request: Dict[str, Any]):
    """
    Recommend dashboard templates based on user goals, tone, and purpose.

    Called from AstheraBackend after the user confirms metric selection and
    wants to create a dashboard.  Uses the DashboardDecisionTreeService
    (vector-store retrieval) — no LLM call, fully synchronous.

    Request body:
    {
        "goals": str,               # free-text description of dashboard goals
        "tone": "executive" | "operational" | "technical",
        "purpose": "monitoring" | "compliance" | "analysis" | "reporting",
        "selected_metrics": [str],  # metric/KPI names from the pipeline run
        "top_k": int                # max templates to return (default 3)
    }

    Returns:
    {
        "templates": [...],   # top-k DashboardTemplateResult dicts
        "metrics": [...],     # related metric catalog entries
        "warnings": [str]
    }
    """
    try:
        from app.services.dashboard_recommend_service import get_dashboard_recommend_service

        goals            = str(request.get("goals") or "")
        tone             = str(request.get("tone") or "operational")
        purpose          = str(request.get("purpose") or "monitoring")
        selected_metrics = list(request.get("selected_metrics") or [])
        top_k            = int(request.get("top_k") or 3)
        # Pipeline context — forwarded from the live pipeline state
        primary_area  = request.get("primary_area") or None
        area_concepts = list(request.get("area_concepts") or [])
        intent        = request.get("intent") or None
        persona       = request.get("persona") or None
        output_format = request.get("output_format") or None

        svc = get_dashboard_recommend_service()
        result = svc.recommend(
            goals=goals,
            tone=tone,
            purpose=purpose,
            selected_metrics=selected_metrics,
            top_k=top_k,
            primary_area=primary_area,
            area_concepts=area_concepts or None,
            intent=intent,
            persona=persona,
            output_format=output_format,
        )
        return result

    except Exception as e:
        logger.error("Error in recommend_dashboard_templates: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@app.post("/workflow/invoke")
async def invoke_workflow(request: Dict[str, Any]):
    """
    Execute workflow synchronously (non-streaming) - supports both compliance and detection_triage.
    
    Request body:
    {
        "user_query": str,
        "session_id": str,
        "workflow_type": "compliance" | "detection_triage" | "csod" (default: "compliance"),
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
        elif workflow_type == WorkflowType.CSOD:
            service = get_csod_workflow_service()
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

        # checkpoint_id is optional — fall back to the session's active checkpoint
        checkpoint_id = request.get("checkpoint_id") or session.active_checkpoint_id
        if not checkpoint_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="checkpoint_id is required (and no active checkpoint found for this session)"
            )
        
        # Get dependencies for service
        dependencies = getattr(app.state, 'dependencies', None) if hasattr(app, 'state') else None
        
        # Route to appropriate service based on workflow type
        if session.workflow_type == WorkflowType.DETECTION_TRIAGE:
            service = get_dt_workflow_service()
        elif session.workflow_type == WorkflowType.CSOD:
            service = get_csod_workflow_service()
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


# ============================================================================
# CSOD Workflow API Routes
# ============================================================================

@app.post("/csod/execute")
async def execute_csod_workflow(request: Dict[str, Any]):
    """
    Execute CSOD workflow with streaming.

    Request body:
    {
        "user_query": str,
        "session_id": str,
        "initial_state": Optional[Dict]  # active_project_id, selected_data_sources, etc.
    }

    Returns: SSE stream with workflow execution events
    """
    try:
        user_query = request.get("user_query")
        if not user_query:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_query is required"
            )
        session_id = request.get("session_id", f"csod-session-{datetime.now().isoformat()}")
        initial_state_data = request.get("initial_state", {})
        dependencies = getattr(app.state, "dependencies", None) if hasattr(app, "state") else None

        csod_service = get_csod_workflow_service()

        async def generate():
            async for event in csod_service.execute_workflow_stream(
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
            },
        )
    except Exception as e:
        logger.error(f"Error in execute_csod_workflow: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@app.post("/csod/invoke")
async def invoke_csod_workflow(request: Dict[str, Any]):
    """
    Execute CSOD workflow synchronously (non-streaming).
    """
    try:
        user_query = request.get("user_query")
        if not user_query:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_query is required"
            )
        session_id = request.get("session_id", f"csod-session-{datetime.now().isoformat()}")
        initial_state_data = request.get("initial_state", {})
        dependencies = getattr(app.state, "dependencies", None) if hasattr(app, "state") else None

        csod_service = get_csod_workflow_service()
        result = await csod_service.execute_workflow_invoke(
            user_query=user_query,
            session_id=session_id,
            initial_state_data=initial_state_data,
            dependencies=dependencies,
        )
        return result
    except Exception as e:
        logger.error(f"Error in invoke_csod_workflow: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@app.post("/csod/resume")
async def resume_csod_workflow(request: Dict[str, Any]):
    """
    Resume CSOD workflow from a checkpoint.
    """
    try:
        session_id = request.get("session_id")
        if not session_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="session_id is required")
        user_input = request.get("user_input", {})
        approved = request.get("approved", True)
        dependencies = getattr(app.state, "dependencies", None) if hasattr(app, "state") else None

        session_manager = get_session_manager()
        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session {session_id} not found")
        if session.workflow_type != WorkflowType.CSOD:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Session {session_id} is not a CSOD session",
            )
        if session.status != SessionStatus.CHECKPOINT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Session {session_id} is not at a checkpoint",
            )

        # checkpoint_id is optional — fall back to the session's active checkpoint
        checkpoint_id = request.get("checkpoint_id") or session.active_checkpoint_id
        if not checkpoint_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="checkpoint_id is required (and no active checkpoint found)")

        csod_service = get_csod_workflow_service()

        async def generate():
            async for event in csod_service.resume_workflow_stream(
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
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in resume_csod_workflow: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@app.get("/csod/session/{session_id}")
async def get_csod_session_status(session_id: str):
    """Get CSOD session status and state."""
    session_manager = get_session_manager()
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session {session_id} not found")
    if session.workflow_type != WorkflowType.CSOD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session {session_id} is not a CSOD session",
        )
    return {"session": session.to_dict()}


@app.get("/csod/sessions")
async def list_csod_sessions(status_filter: Optional[str] = None):
    """List all CSOD workflow sessions."""
    session_manager = get_session_manager()
    sessions = session_manager.list_sessions(workflow_type=WorkflowType.CSOD)
    if status_filter:
        try:
            status_enum = SessionStatus(status_filter)
            sessions = [s for s in sessions if s.status == status_enum]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status_filter: {status_filter}",
            )
    return {"sessions": [s.to_dict() for s in sessions], "count": len(sessions)}


# ============================================================================
# Dashboard Agent (Layout Advisor) API Routes
# ============================================================================

@app.post("/dashboard-agent/session")
async def create_dashboard_agent_session(request: Dict[str, Any]):
    """
    Create a new layout advisor session.

    Request body:
    {
        "session_id": Optional[str],
        "agent_config": Optional[Dict]
    }
    """
    try:
        session_id = request.get("session_id")
        agent_config = request.get("agent_config")
        service = get_dashboard_agent_service()
        sid = service.create_session(session_id=session_id, agent_config=agent_config)
        return {"session_id": sid}
    except Exception as e:
        logger.error(f"Error creating dashboard agent session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@app.post("/dashboard-agent/session/{session_id}/start")
async def start_dashboard_agent_session(session_id: str, request: Dict[str, Any]):
    """
    Start a layout advisor conversation with upstream context.

    Request body:
    {
        "upstream_context": Optional[Dict]  # use_case, data_sources, kpis, etc.
    }
    """
    try:
        upstream_context = request.get("upstream_context", {})
        service = get_dashboard_agent_service()
        result = service.start_session(session_id=session_id, upstream_context=upstream_context)
        return result
    except Exception as e:
        logger.error(f"Error starting dashboard agent session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@app.post("/dashboard-agent/session/{session_id}/respond")
async def respond_dashboard_agent_session(session_id: str, request: Dict[str, Any]):
    """
    Send a user message to an existing layout advisor session.

    Request body:
    {
        "user_message": str
    }
    """
    try:
        user_message = request.get("user_message", "")
        if not user_message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_message is required",
            )
        service = get_dashboard_agent_service()
        result = service.respond(session_id=session_id, user_message=user_message)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in dashboard agent respond: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@app.post("/dashboard-agent/session/{session_id}/start/stream")
async def start_dashboard_agent_session_stream(session_id: str, request: Dict[str, Any]):
    """
    Start layout advisor with streaming SSE events (node_start, llm_chunk, response).
    """
    try:
        upstream_context = request.get("upstream_context", {})
        service = get_dashboard_agent_service()

        async def generate():
            async for ev in service.start_session_stream(
                session_id=session_id,
                upstream_context=upstream_context,
            ):
                yield format_sse_event(ev["event"], ev["data"])

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as e:
        logger.error(f"Error in dashboard agent start stream: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@app.post("/dashboard-agent/session/{session_id}/respond/stream")
async def respond_dashboard_agent_session_stream(session_id: str, request: Dict[str, Any]):
    """
    Send user message and stream SSE events until next response.
    """
    try:
        user_message = request.get("user_message", "")
        if not user_message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_message is required",
            )
        service = get_dashboard_agent_service()

        async def generate():
            async for ev in service.respond_stream(
                session_id=session_id,
                user_message=user_message,
            ):
                yield format_sse_event(ev["event"], ev["data"])

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in dashboard agent respond stream: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@app.get("/dashboard-agent/session/{session_id}")
async def get_dashboard_agent_session(session_id: str):
    """Get layout advisor session state."""
    service = get_dashboard_agent_service()
    state = service.get_state(session_id)
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session {session_id} not found")
    return {"session_id": session_id, "state": state}


@app.get("/dashboard-agent/session/{session_id}/layout-spec")
async def get_dashboard_agent_layout_spec(session_id: str):
    """Get the final layout spec if the session is complete."""
    service = get_dashboard_agent_service()
    spec = service.get_layout_spec(session_id)
    if spec is None:
        session = service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session {session_id} not found")
        return {"session_id": session_id, "layout_spec": None, "complete": False}
    return {"session_id": session_id, "layout_spec": spec, "complete": True}


@app.delete("/dashboard-agent/session/{session_id}")
async def delete_dashboard_agent_session(session_id: str):
    """Delete a layout advisor session."""
    service = get_dashboard_agent_service()
    deleted = service.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session {session_id} not found")
    return {"session_id": session_id, "deleted": True}


@app.get("/dashboard-agent/sessions")
async def list_dashboard_agent_sessions():
    """List all layout advisor session IDs."""
    service = get_dashboard_agent_service()
    session_ids = service.list_sessions()
    return {"sessions": session_ids, "count": len(session_ids)}


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

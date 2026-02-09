"""
Main FastAPI application for Knowledge App

This is the entry point for the Knowledge API, providing endpoints for:
- Graph streaming with SSE
- Knowledge base management
- Document processing
- Contextual graph operations
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import sys
import traceback
import datetime

# Import routers
from app.routers import streaming_router, context_breakdown_router
from app.routers.pipelines import router as pipelines_router
# Add other routers as they are created:
# from app.routers import knowledge_router, documents_router, etc.

# Import core components
from app.core.settings import get_settings
from app.core.dependencies import get_dependencies, clear_all_caches
from app.core.startup import initialize_graphs_and_assistants, initialize_indexing_services

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Initialize settings early
try:
    settings = get_settings()
    logger.info("Settings initialized successfully")
except Exception as e:
    logger.error(f"Settings initialization failed: {str(e)}")
    logger.error(traceback.format_exc())
    print(f"CRITICAL ERROR: Failed to initialize settings: {str(e)}")
    sys.exit(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI app.
    Handles startup and shutdown logic.
    """
    try:
        # Setup OpenTelemetry (before anything else)
        from app.core.telemetry import setup_telemetry
        telemetry_enabled = setup_telemetry(
            service_name="knowledge-service",
            enable_console_exporter=False,  # Set True for debugging
            instrument_fastapi=True,
            instrument_asyncpg=True
        )
        
        if telemetry_enabled:
            logger.info("✓ OpenTelemetry tracing enabled")
        else:
            logger.warning("⚠ OpenTelemetry tracing not available - using logging only")
        
        # Initialize dependencies
        logger.info("Initializing dependencies...")
        dependencies = await get_dependencies()
        
        # Store dependencies in app state
        app.state.dependencies = dependencies
        
        # For convenience, also store individual dependencies in app state
        for key, value in dependencies.items():
            setattr(app.state, key, value)
        
        logger.info("API initialized successfully with all dependencies")
        logger.info(f"Vector Store: {settings.VECTOR_STORE_TYPE.value}")
        logger.info(f"Database: {settings.DATABASE_TYPE.value}")
        logger.info(f"Cache: {settings.CACHE_TYPE.value}")
        logger.info(f"LLM Model: {settings.LLM_MODEL}")
        
        # Initialize indexing services and verify collections
        logger.info("Initializing indexing services and verifying collections...")
        try:
            indexing_info = await initialize_indexing_services(dependencies)
            app.state.indexing_services = indexing_info["services"]
            app.state.indexing_status = indexing_info["status"]
            app.state.indexing_summary = indexing_info["summary"]
            logger.info("Indexing services initialized and collections verified")
        except Exception as e:
            logger.error(f"Failed to initialize indexing services: {str(e)}")
            logger.error(traceback.format_exc())
            # Continue without indexing services - API will still work but may have limited functionality
            app.state.indexing_services = {}
            app.state.indexing_status = {}
            app.state.indexing_summary = {}
        
        # Initialize graphs and assistants
        logger.info("Initializing graphs and assistants...")
        try:
            # Try to load from config file (knowledge/config/), fallback to defaults
            config_path = getattr(settings, "GRAPH_CONFIG_PATH", None)
            if not config_path:
                default_path = settings.CONFIG_DIR / "assistants_configuration.yaml"
                config_path = str(default_path) if default_path.exists() else None

            registry = await initialize_graphs_and_assistants(
                dependencies,
                config_path=str(config_path) if config_path else None
            )
            app.state.graph_registry = registry
            
            # Log summary and validate assistants
            assistants = registry.list_assistants()
            total_graphs = sum(len(registry.list_assistant_graphs(a["assistant_id"])) for a in assistants)
            logger.info(f"Graphs and assistants initialized successfully:")
            logger.info(f"  - {len(assistants)} assistants")
            logger.info(f"  - {total_graphs} graphs total")
            
            # Validate each assistant has at least one graph
            assistants_status = {}
            for assistant in assistants:
                assistant_id = assistant["assistant_id"]
                graph_count = assistant["graph_count"]
                default_graph_id = assistant.get("default_graph_id")
                
                # Verify assistant has graphs
                if graph_count == 0:
                    logger.warning(f"  ⚠ {assistant['name']} ({assistant_id}): No graphs registered")
                    assistants_status[assistant_id] = {
                        "status": "no_graphs",
                        "message": "Assistant registered but has no graphs"
                    }
                else:
                    # Verify default graph exists and is accessible
                    if default_graph_id:
                        graph_config = registry.get_assistant_graph(assistant_id, default_graph_id)
                        if graph_config and graph_config.graph:
                            logger.info(f"  ✓ {assistant['name']} ({assistant_id}): {graph_count} graphs, default: {default_graph_id}")
                            assistants_status[assistant_id] = {
                                "status": "operational",
                                "graph_count": graph_count,
                                "default_graph_id": default_graph_id
                            }
                        else:
                            logger.warning(f"  ⚠ {assistant['name']} ({assistant_id}): Default graph {default_graph_id} not found")
                            assistants_status[assistant_id] = {
                                "status": "invalid_default_graph",
                                "message": f"Default graph {default_graph_id} not found"
                            }
                    else:
                        logger.warning(f"  ⚠ {assistant['name']} ({assistant_id}): {graph_count} graphs but no default set")
                        assistants_status[assistant_id] = {
                            "status": "no_default_graph",
                            "message": "Assistant has graphs but no default graph set"
                        }
            
            # Store assistants status for health check
            app.state.assistants_status = assistants_status
            
            # Verify streaming router dependencies
            logger.info("Verifying streaming router dependencies...")
            from app.streams.streaming_service import GraphStreamingService
            streaming_service = GraphStreamingService(registry=registry)
            app.state.streaming_service = streaming_service
            logger.info("  ✓ Streaming service initialized")
            logger.info("  ✓ Streaming router operational at /api/streams/*")
            
        except Exception as e:
            logger.error(f"Failed to initialize graphs and assistants: {str(e)}")
            logger.error(traceback.format_exc())
            # Continue without graphs - API will still work but streaming won't
            app.state.assistants_status = {}
            app.state.streaming_service = None
        
        # Initialize pipeline registry
        logger.info("Initializing pipeline registry...")
        try:
            from app.core.pipeline_startup import initialize_pipeline_registry
            
            pipeline_init_result = await initialize_pipeline_registry(dependencies)
            
            app.state.pipeline_registry = pipeline_init_result["registry"]
            app.state.pipeline_registration_results = pipeline_init_result["registration_results"]
            app.state.pipeline_initialization_results = pipeline_init_result["initialization_results"]
            
            # Log summary
            reg_results = pipeline_init_result["registration_results"]
            init_results = pipeline_init_result["initialization_results"]
            
            logger.info(f"Pipeline registry initialized successfully:")
            logger.info(f"  - {reg_results['total_pipelines']} pipelines registered")
            logger.info(f"  - {init_results['initialized']} pipelines initialized")
            logger.info(f"  - {len(reg_results['categories'])} categories")
            
            if reg_results['failed']:
                logger.warning(f"  - {len(reg_results['failed'])} pipelines failed to register")
            
            if init_results['failed'] > 0:
                logger.warning(f"  - {init_results['failed']} pipelines failed to initialize")
            
            logger.info("  ✓ Pipeline registry operational")
            
        except Exception as e:
            logger.error(f"Failed to initialize pipeline registry: {str(e)}")
            logger.error(traceback.format_exc())
            # Continue without pipeline registry - API will still work but pipelines won't be available
            app.state.pipeline_registry = None
            app.state.pipeline_registration_results = {}
            app.state.pipeline_initialization_results = {}
        
    except Exception as e:
        logger.error(f"Failed to initialize API dependencies: {str(e)}")
        logger.error(traceback.format_exc())
        print(f"CRITICAL ERROR: Failed to initialize API: {str(e)}")
        # We'll continue anyway but with limited functionality
    
    yield
    
    # Cleanup
    logger.info("Shutting down API")
    try:
        # Cleanup pipeline registry
        if hasattr(app.state, "pipeline_registry") and app.state.pipeline_registry:
            try:
                from app.core.pipeline_startup import cleanup_pipeline_registry
                await cleanup_pipeline_registry()
                logger.info("Pipeline registry cleaned up")
            except Exception as e:
                logger.error(f"Error cleaning up pipeline registry: {str(e)}")
        
        # Close database pool if it exists
        if hasattr(app.state, "db_pool") and app.state.db_pool:
            await app.state.db_pool.close()
            logger.info("Database pool closed")
        
        # Clear all caches
        clear_all_caches()
        logger.info("Caches cleared")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")


# Create FastAPI app
app = FastAPI(
    title="Knowledge API",
    description="""
    API for knowledge management, document processing, and graph execution.
    
    ## Features
    * **Graph Streaming**: Real-time SSE streaming for LangGraph execution
    * **Knowledge Base Management**: Vector store operations and document management
    * **Contextual Graph Operations**: Multi-hop reasoning and context management
    * **Document Processing**: Extraction, metadata generation, and analysis
    * **Hybrid Search**: Combined vector and keyword search
    * **Metadata Services**: Automatic metadata generation and extraction
    
    ## Graph Streaming
    Stream LangGraph execution with real-time updates:
    - Node execution events
    - State updates
    - Progress tracking
    - Final results
    
    ## Authentication
    Most endpoints require authentication. Configure authentication middleware as needed.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(streaming_router)
app.include_router(context_breakdown_router)
app.include_router(pipelines_router)
# Add other routers as they are created:
# app.include_router(knowledge_router)
# app.include_router(documents_router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Knowledge API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health"
    }


@app.get("/api/health")
async def health_check():
    """
    Health check endpoint that verifies:
    - API status
    - Database connectivity
    - Vector store connectivity
    - Settings availability
    """
    try:
        health_status = {
            "status": "ok",
            "timestamp": str(datetime.datetime.now()),
            "environment": settings.ENV,
            "services": {}
        }
        
        # Check database
        if hasattr(app.state, "db_pool") and app.state.db_pool:
            try:
                async with app.state.db_pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                health_status["services"]["database"] = "connected"
            except Exception as e:
                health_status["services"]["database"] = f"error: {str(e)}"
                health_status["status"] = "degraded"
        else:
            health_status["services"]["database"] = "not_initialized"
        
        # Check vector store
        if hasattr(app.state, "chroma_client") and app.state.chroma_client:
            try:
                # Try to list collections (lightweight operation)
                app.state.chroma_client.list_collections()
                health_status["services"]["vector_store"] = "connected"
            except Exception as e:
                health_status["services"]["vector_store"] = f"error: {str(e)}"
                health_status["status"] = "degraded"
        else:
            health_status["services"]["vector_store"] = "not_initialized"
        
        # Check cache
        if hasattr(app.state, "cache_client") and app.state.cache_client:
            health_status["services"]["cache"] = "available"
        else:
            health_status["services"]["cache"] = "not_initialized"
        
        # Check LLM
        if hasattr(app.state, "llm") and app.state.llm:
            health_status["services"]["llm"] = "available"
        else:
            health_status["services"]["llm"] = "not_initialized"
        
        # Check graph registry
        if hasattr(app.state, "graph_registry") and app.state.graph_registry:
            assistants = app.state.graph_registry.list_assistants()
            assistants_status = getattr(app.state, "assistants_status", {})
            
            # Count operational assistants
            operational_count = sum(
                1 for status in assistants_status.values() 
                if status.get("status") == "operational"
            )
            
            health_status["services"]["graph_registry"] = {
                "status": "available",
                "assistants_count": len(assistants),
                "operational_assistants": operational_count,
                "assistants": [a["assistant_id"] for a in assistants],
                "assistants_status": assistants_status
            }
        else:
            health_status["services"]["graph_registry"] = "not_initialized"
        
        # Check streaming service
        if hasattr(app.state, "streaming_service") and app.state.streaming_service:
            health_status["services"]["streaming_service"] = "operational"
        else:
            health_status["services"]["streaming_service"] = "not_initialized"
            health_status["status"] = "degraded"
        
        # Check indexing services
        if hasattr(app.state, "indexing_services") and app.state.indexing_services:
            summary = getattr(app.state, "indexing_summary", {})
            health_status["services"]["indexing_services"] = {
                "status": "available",
                "total_services": summary.get("total_services", 0),
                "total_collections": summary.get("total_collections", 0),
                "collections_with_data": summary.get("collections_with_data", 0)
            }
        else:
            health_status["services"]["indexing_services"] = "not_initialized"
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "error",
            "timestamp": str(datetime.datetime.now()),
            "error": str(e),
            "environment": getattr(settings, "ENV", "unknown"),
            "settings_available": hasattr(app, "state") and hasattr(app.state, "settings")
        }


@app.get("/api/assistants/status")
async def assistants_status():
    """
    Get status of all assistants and their availability for graph interaction
    
    Returns detailed status for each assistant including:
    - Whether the assistant is operational
    - Number of graphs available
    - Default graph ID
    - Any issues preventing the assistant from being used
    """
    try:
        if not hasattr(app.state, "graph_registry") or not app.state.graph_registry:
            raise HTTPException(
                status_code=503,
                detail="Graph registry not initialized"
            )
        
        registry = app.state.graph_registry
        assistants = registry.list_assistants()
        assistants_status = getattr(app.state, "assistants_status", {})
        
        result = {
            "total_assistants": len(assistants),
            "operational_assistants": sum(
                1 for status in assistants_status.values() 
                if status.get("status") == "operational"
            ),
            "assistants": []
        }
        
        for assistant in assistants:
            assistant_id = assistant["assistant_id"]
            status_info = assistants_status.get(assistant_id, {"status": "unknown"})
            
            # Get graph details
            graphs_data = registry.list_assistant_graphs(assistant_id) or []
            graphs = []
            for graph_data in graphs_data:
                graph_config = registry.get_assistant_graph(assistant_id, graph_data["graph_id"])
                graphs.append({
                    "graph_id": graph_data["graph_id"],
                    "name": graph_data.get("name", graph_data["graph_id"]),
                    "is_default": graph_data.get("is_default", False),
                    "is_operational": graph_config is not None and graph_config.graph is not None
                })
            
            result["assistants"].append({
                "assistant_id": assistant_id,
                "name": assistant["name"],
                "description": assistant.get("description", ""),
                "status": status_info.get("status", "unknown"),
                "graph_count": assistant["graph_count"],
                "default_graph_id": assistant.get("default_graph_id"),
                "graphs": graphs,
                "metadata": assistant.get("metadata", {}),
                "can_accept_requests": status_info.get("status") == "operational"
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting assistants status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving assistants status: {str(e)}"
        )


@app.get("/api/env")
async def environment_debug():
    """
    Debug endpoint to verify environment variables (safe version).
    Only available in development environment.
    """
    try:
        # Only show in development environment
        if settings.ENV != "development":
            raise HTTPException(status_code=403, detail="Not available in production")
        
        # Get safe subset of environment variables (no secrets)
        safe_vars = {
            "VECTOR_STORE_TYPE": settings.VECTOR_STORE_TYPE.value,
            "DATABASE_TYPE": settings.DATABASE_TYPE.value,
            "CACHE_TYPE": settings.CACHE_TYPE.value,
            "POSTGRES_HOST": settings.POSTGRES_HOST,
            "POSTGRES_PORT": settings.POSTGRES_PORT,
            "POSTGRES_DB": settings.POSTGRES_DB,
            "CHROMA_HOST": settings.CHROMA_HOST,
            "CHROMA_PORT": settings.CHROMA_PORT,
            "CHROMA_USE_LOCAL": settings.CHROMA_USE_LOCAL,
            "EMBEDDING_MODEL": settings.EMBEDDING_MODEL,
            "LLM_MODEL": settings.LLM_MODEL,
            "LLM_TEMPERATURE": settings.LLM_TEMPERATURE,
            "ENV": settings.ENV,
            "DEBUG": settings.DEBUG,
            "LOG_LEVEL": settings.LOG_LEVEL
        }
        
        return {
            "environment": settings.ENV,
            "variables": safe_vars,
            "settings_loaded": True
        }
    except Exception as e:
        logger.error(f"Environment debug endpoint failed: {str(e)}")
        return {
            "error": str(e),
            "settings_loaded": False
        }


@app.get("/api/indexing/status")
async def indexing_status():
    """
    Get status of all indexing services and collections.
    
    Returns detailed status for each collection prefix including:
    - Whether collections exist
    - Document counts per collection
    - Overall summary
    """
    try:
        if not hasattr(app.state, "indexing_services") or not app.state.indexing_services:
            raise HTTPException(
                status_code=503,
                detail="Indexing services not initialized"
            )
        
        indexing_status = getattr(app.state, "indexing_status", {})
        indexing_summary = getattr(app.state, "indexing_summary", {})
        indexing_services = app.state.indexing_services
        
        result = {
            "summary": indexing_summary,
            "services": {}
        }
        
        # Collection prefix descriptions
        prefix_descriptions = {
            "compliance_baseline": {
                "description": "Compliance documents (SOC2, policies, risk controls)",
                "source": "index_compliance.py"
            },
            "connector_index": {
                "description": "Connector/product configurations",
                "source": "index_connectors.py"
            },
            "mdl_index": {
                "description": "MDL schema files",
                "source": "index_mdl.py"
            },
            "comprehensive_index": {
                "description": "Comprehensive indexed data (preview files)",
                "source": "ingest_preview_files.py"
            }
        }
        
        for prefix, service in indexing_services.items():
            status_info = indexing_status.get(prefix, {})
            prefix_info = prefix_descriptions.get(prefix, {})
            
            result["services"][prefix] = {
                "description": prefix_info.get("description", ""),
                "source": prefix_info.get("source", ""),
                "status": "available" if not status_info.get("error") else "error",
                "error": status_info.get("error"),
                "total_collections": status_info.get("total_collections", 0),
                "collections_with_data": status_info.get("collections_with_data", 0),
                "collections": status_info.get("collections", {})
            }
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting indexing status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving indexing status: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    
    # Log startup information
    logger.info(f"Starting Knowledge API server")
    logger.info(f"Environment: {settings.ENV}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"Vector Store: {settings.VECTOR_STORE_TYPE.value}")
    logger.info(f"Database: {settings.DATABASE_TYPE.value}")
    
    # Determine host and port
    host = getattr(settings, "API_HOST", "0.0.0.0")
    port = getattr(settings, "API_PORT", 8000)
    
    logger.info(f"Server will start on {host}:{port}")
    
    # Start the server
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )


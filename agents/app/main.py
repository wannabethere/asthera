from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
import sys
from contextlib import asynccontextmanager
import datetime
import traceback
from app.routers import  documents,  recommendation, planner,pipeline_generator

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Try to initialize environment
try:
    from app.settings import init_environment, get_settings
    settings = init_environment()
    logger.info("Environment initialized successfully")
except Exception as e:
    logger.error(f"Environment initialization failed: {str(e)}")
    logger.error(traceback.format_exc())
    print(f"CRITICAL ERROR: Failed to initialize environment: {str(e)}")
    sys.exit(1)

# Import core components
try:
    from app.core.dependencies import get_dependencies
except Exception as e:
    logger.error(f"Failed to import dependencies: {str(e)}")
    logger.error(traceback.format_exc())
    print(f"CRITICAL ERROR: Failed to import dependencies: {str(e)}")
    sys.exit(1)

# Initialize LLM and agents during startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Initialize dependencies
        logger.info("Initializing dependencies...")
        dependencies = get_dependencies()
        
        # Store dependencies in app state
        app.state.dependencies = dependencies
        
        # For convenience, also store individual dependencies in app state
        for key, value in dependencies.items():
            setattr(app.state, key, value)
        
        logger.info("API initialized successfully with all dependencies")
    except Exception as e:
        logger.error(f"Failed to initialize API dependencies: {str(e)}")
        logger.error(traceback.format_exc())
        print(f"CRITICAL ERROR: Failed to initialize API: {str(e)}")
        # We'll continue anyway but with limited functionality
    
    yield
    
    # Cleanup
    logger.info("Shutting down API")

# Create FastAPI app
app = FastAPI(
    title="Analysis Flow API",
    description="""
    API for generating and following up on data analysis questions.
    
    ## Features
    * User Management
    * Role-based Access Control
    * Team Collaboration
    * Session Management
    * OAuth Integration
    * Recommendations
    * Data Pipeline Generation
    * Document Management
    
    ## Authentication
    Most endpoints require authentication. Use the OAuth endpoints to authenticate.
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
    allow_origins=["*"],  # Adjust in production to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)





app.include_router(
    recommendation.router,
    prefix="/api/recommendations",
    tags=["recommendations"]
)

app.include_router(
    planner.router,
    prefix="/api/planner",
    tags=["planner"]
)

app.include_router(
    pipeline_generator.router,
    prefix="/api/pipelines",
    tags=["pipelines"]
)

app.include_router(
    documents.router,
    prefix="/api/documents",
    tags=["documents"]
)

@app.get("/api/health")
async def health_check():
    """Health check endpoint that also verifies database connectivity"""
    try:
        # Access session manager if available
        if hasattr(app.state, "session_manager"):
            with app.state.session_manager.get_session() as session:
                # Try a simple query to verify database connectivity
                session.execute("SELECT 1")
                db_status = "connected"
        else:
            db_status = "unavailable"
        
        return {
            "status": "ok",
            "timestamp": str(datetime.datetime.now()),
            "environment": settings.ENV,
            "database": db_status,
            "settings_available": True
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "degraded",
            "timestamp": str(datetime.datetime.now()),
            "error": str(e),
            "environment": getattr(settings, "ENV", "unknown"),
            "database": "error",
            "settings_available": hasattr(app, "settings")
        }

@app.get("/api/env")
async def environment_debug():
    """Debug endpoint to verify environment variables (safe version)"""
    try:
        # Only show in development environment
        if settings.ENV != "development":
            raise HTTPException(status_code=403, detail="Not available in production")
        
        # Get safe subset of environment variables
        safe_vars = {
            "POSTGRES_HOST": settings.POSTGRES_HOST,
            "POSTGRES_PORT": settings.POSTGRES_PORT,
            "POSTGRES_DB": settings.POSTGRES_DB,
            "POSTGRES_USER": settings.POSTGRES_USER,
            "CHROMA_HOST": settings.CHROMA_HOST,
            "CHROMA_PORT": settings.CHROMA_PORT,
            "MODEL_NAME": settings.MODEL_NAME,
            "ENV": settings.ENV,
            "API_VERSION": settings.API_VERSION
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

if __name__ == "__main__":
    import uvicorn
    
    # Log startup information
    logger.info(f"Starting API server on {settings.API_HOST}:{settings.API_PORT}")
    logger.info(f"Environment: {settings.ENV}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    
    # Start the server
    uvicorn.run(
        "main:app", 
        host=settings.API_HOST, 
        port=settings.API_PORT, 
        reload=settings.DEBUG
    )
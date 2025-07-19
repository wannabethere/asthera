from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
import sys
from datetime import datetime

from app.routers import documents, threads, agents
from app.utils.postgres_manager import postgres_manager
from app.connections import dbservice

# Configure logging for the entire application
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_file = os.path.join(log_dir, f"app_{datetime.now().strftime('%Y%m%d')}.log")

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        # Output to console
        logging.StreamHandler(sys.stdout),
        # Also log to a file for persistent records
        logging.FileHandler(log_file)
    ]
)

# Get logger for this module
logger = logging.getLogger(__name__)

app = FastAPI(title="Document Processing API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database tables
@app.on_event("startup")
async def startup_event():
    logger.info("Application starting up - initializing database")
    postgres_manager.init_db()
    logger.info("Database initialization complete")

# Include routers
app.include_router(documents.router, prefix="/api")
app.include_router(threads.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(dbservice.router, prefix="/api")

@app.get("/")
async def root():
    logger.info("Root endpoint accessed")
    return {"message": "Welcome to the Document Processing API"}
#!/usr/bin/env python3
"""
Run script for Compliance Skill API Service.

Uses settings from app.core.settings for configuration.
Environment variables can override settings.

Usage:
    python run_api.py
    
Or with uvicorn directly:
    uvicorn app.api.main:app --host 0.0.0.0 --port 8002 --reload
    
Or run the main.py file directly:
    python -m app.api.main
"""
import uvicorn
import os
import sys

# Add current directory to path to ensure imports work
sys.path.insert(0, os.path.dirname(__file__))

# Import settings after path is set
from app.core.settings import get_settings

if __name__ == "__main__":
    # Get settings (loads from .env file automatically)
    settings = get_settings()
    
    # Allow environment variable overrides
    host = os.getenv("HOST", settings.API_HOST)
    port = int(os.getenv("PORT", str(settings.API_PORT)))
    reload = os.getenv("DEBUG", str(settings.DEBUG)).lower() == "true"
    log_level = os.getenv("LOG_LEVEL", settings.LOG_LEVEL).lower()
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║              Compliance Skill API Service                    ║
╠══════════════════════════════════════════════════════════════╣
║  API Docs: http://{host}:{port}/docs
║  Health:   http://{host}:{port}/health
║  Host:     {host}
║  Port:     {port}
║  Reload:   {reload}
║  Log Level: {log_level}
║  Environment: {settings.ENV}
╚══════════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        "app.api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level
    )

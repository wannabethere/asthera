"""
FastAPI Routers Module

This module contains all API route definitions organized by service/feature.
Each router should be focused on a specific domain or service.

To add a new router:
1. Create a new file (e.g., `your_service.py`)
2. Define your router using `APIRouter`
3. Import and export it here
4. Include it in your main FastAPI app
"""

from app.routers.streaming import router as streaming_router
from app.routers.context_breakdown import router as context_breakdown_router

__all__ = [
    "streaming_router",
    "context_breakdown_router",
]


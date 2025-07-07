"""
Configuration and Setup for LLM Definition Service
Provides practical setup examples and integration patterns
"""

import os
import asyncio
import logging
from typing import Dict, List, Any
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import json
from app.config import ServiceConfig
from genieml.dataservices.tests.unusedcode.columnservice import LLMDefinitionService
from app.service.database import SessionLocal, create_db_tables

# Import our services
from app.schemas.dbmodels import Base, Project
from app.service.models import DefinitionType, UserExample, GeneratedDefinition

# ============================================================================
# SERVICE FACTORY
# ============================================================================

class ServiceFactory:
    """Factory for creating service instances"""
    
    def __init__(self, config: ServiceConfig): # No longer needs db_manager
        self.config = config
        self._services: Dict[str, LLMDefinitionService] = {}
        # We can also remove the db_manager attribute
    
    async def get_service(self, project_id: str) -> LLMDefinitionService:
        """Get or create service instance for project"""
        # Create a new session directly from the factory
        session = SessionLocal()
        if project_id not in self._services:
                
            service = LLMDefinitionService(
                session=session,
                openai_api_key=self.config.openai_api_key,
                mcp_server_url=self.config.mcp_server_url,
                project_id=project_id
            )
            
            self._services[project_id] = service
        
        return self._services[project_id]
    
    def cleanup_service(self, project_id: str):
        """Cleanup service instance"""
        if project_id in self._services:
            service = self._services.pop(project_id)
            # The service itself now holds the session, so we can close it from there
            service.session.close()




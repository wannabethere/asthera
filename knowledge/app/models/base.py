"""
Base models for requests and responses
"""
import uuid
from typing import Optional, Dict, Any
from pydantic import BaseModel


class ServiceRequest(BaseModel):
    """Base request model for all services"""
    request_id: Optional[str] = None
    
    def __init__(self, **data):
        if 'request_id' not in data or not data.get('request_id'):
            data['request_id'] = str(uuid.uuid4())
        super().__init__(**data)


class ServiceResponse(BaseModel):
    """Base response model for all services"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None

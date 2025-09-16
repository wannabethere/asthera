"""
Request and Response models for Document Persistence Service
"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class DocumentSearchRequest(BaseModel):
    """Request model for document search"""
    query: Optional[str] = Field(None, description="Search query text")
    document_type: Optional[str] = Field(None, description="Filter by document type")
    source_type: Optional[str] = Field(None, description="Filter by source type")
    domain_id: Optional[str] = Field(None, description="Filter by domain ID")
    created_by: Optional[str] = Field(None, description="Filter by creator")
    limit: int = Field(10, description="Maximum number of results to return")


class DocumentGetRequest(BaseModel):
    """Request model for getting a single document"""
    document_id: str = Field(..., description="Document ID to retrieve")


class DocumentInsightsRequest(BaseModel):
    """Request model for getting document insights"""
    document_id: str = Field(..., description="Document ID to get insights for")


class DocumentDeleteRequest(BaseModel):
    """Request model for deleting a document"""
    document_id: str = Field(..., description="Document ID to delete")


class DocumentResponse(BaseModel):
    """Response model for document operations"""
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    data: Optional[Any] = Field(None, description="Response data")
    error: Optional[str] = Field(None, description="Error message if any")


class DocumentSearchResponse(BaseModel):
    """Response model for document search"""
    success: bool = Field(..., description="Whether the search was successful")
    documents: List[Dict[str, Any]] = Field(default_factory=list, description="List of found documents")
    total_count: int = Field(0, description="Total number of documents found")
    error: Optional[str] = Field(None, description="Error message if any")


class DocumentInsightsResponse(BaseModel):
    """Response model for document insights"""
    success: bool = Field(..., description="Whether the operation was successful")
    insights: List[Dict[str, Any]] = Field(default_factory=list, description="List of document insights")
    total_count: int = Field(0, description="Total number of insights found")
    error: Optional[str] = Field(None, description="Error message if any")

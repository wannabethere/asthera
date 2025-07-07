"""
Pydantic schemas for project JSON storage operations
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class ProjectJSONResponse(BaseModel):
    """Response model for project JSON storage operations"""
    project_id: str = Field(..., description="Project ID")
    json_type: str = Field(..., description="Type of JSON data (tables, metrics, views, calculated_columns, project_summary)")
    chroma_document_id: str = Field(..., description="ChromaDB document ID")
    message: str = Field(..., description="Success message")


class ProjectJSONSearchRequest(BaseModel):
    """Request model for searching project JSON data"""
    search_query: str = Field(..., description="Search query text")
    json_type: Optional[str] = Field(None, description="Optional JSON type filter")
    n_results: int = Field(10, description="Number of results to return", ge=1, le=100)


class ProjectJSONSearchResponse(BaseModel):
    """Response model for project JSON search results"""
    project_id: str = Field(..., description="Project ID")
    search_query: str = Field(..., description="Original search query")
    json_type: Optional[str] = Field(None, description="JSON type filter used")
    results: List[Dict[str, Any]] = Field(..., description="Search results with documents and distances")
    total_results: int = Field(..., description="Total number of results found")


class ProjectJSONUpdateRequest(BaseModel):
    """Request model for updating project JSON on entity changes"""
    entity_type: str = Field(..., description="Type of entity that changed (table, column, metric, view, calculated_column)")
    entity_id: str = Field(..., description="ID of the entity that changed")
    updated_by: str = Field('system', description="User who made the change")


class ProjectJSONStatus(BaseModel):
    """Response model for project JSON storage status"""
    project_id: str = Field(..., description="Project ID")
    json_stores: Dict[str, Dict[str, Any]] = Field(..., description="Status of each JSON store type")


class ProjectTablesJSON(BaseModel):
    """Schema for project tables JSON structure"""
    project_id: str
    project_name: str
    tables: List[Dict[str, Any]]


class ProjectMetricsJSON(BaseModel):
    """Schema for project metrics JSON structure"""
    project_id: str
    project_name: str
    metrics: List[Dict[str, Any]]


class ProjectViewsJSON(BaseModel):
    """Schema for project views JSON structure"""
    project_id: str
    project_name: str
    views: List[Dict[str, Any]]


class ProjectCalculatedColumnsJSON(BaseModel):
    """Schema for project calculated columns JSON structure"""
    project_id: str
    project_name: str
    calculated_columns: List[Dict[str, Any]]


class ProjectSummaryJSON(BaseModel):
    """Schema for project summary JSON structure"""
    project_id: str
    project_name: str
    description: Optional[str]
    status: str
    version: str
    summary: Dict[str, Any]
    tables: List[Dict[str, Any]]
    metrics: List[Dict[str, Any]]
    views: List[Dict[str, Any]]
    calculated_columns: List[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]] 
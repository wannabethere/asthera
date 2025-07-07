from typing import Optional, Any, List, Dict
from pydantic import BaseModel, Field
import uuid
from datetime import datetime


class SQLFunctionBase(BaseModel):
    name: str = Field(..., description="Function name")
    display_name: Optional[str] = Field(None, description="Display name for the function")
    description: Optional[str] = Field(None, description="Function description")
    function_sql: str = Field(..., description="SQL function definition")
    return_type: Optional[str] = Field(None, description="Return type of the function")
    parameters: Optional[List[Dict[str, Any]]] = Field(None, description="Function parameters")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class SQLFunctionCreate(SQLFunctionBase):
    project_id: Optional[str] = Field(None, description="Project ID (optional for global functions)")


class SQLFunctionUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Function name")
    display_name: Optional[str] = Field(None, description="Display name for the function")
    description: Optional[str] = Field(None, description="Function description")
    function_sql: Optional[str] = Field(None, description="SQL function definition")
    return_type: Optional[str] = Field(None, description="Return type of the function")
    parameters: Optional[List[Dict[str, Any]]] = Field(None, description="Function parameters")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class SQLFunctionRead(SQLFunctionBase):
    function_id: str = Field(..., description="Function ID")
    project_id: Optional[str] = Field(None, description="Project ID (null for global functions)")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    modified_by: Optional[str] = Field(None, description="User who last modified the function")
    entity_version: int = Field(..., description="Entity version number")

    class Config:
        from_attributes = True


class SQLFunctionSummary(BaseModel):
    total_functions: int = Field(..., description="Total number of functions")
    project_id: Optional[str] = Field(None, description="Project ID (null for global summary)")
    return_types: Dict[str, int] = Field(..., description="Count by return type")
    recent_functions: List[Dict[str, Any]] = Field(..., description="Recent functions")
    total_parameters: int = Field(..., description="Total number of parameters")


class SQLFunctionSearchRequest(BaseModel):
    search_term: str = Field(..., description="Search term")
    project_id: Optional[str] = Field(None, description="Project ID to filter by")
    return_type: Optional[str] = Field(None, description="Filter by return type")
    limit: Optional[int] = Field(100, description="Maximum number of results")


class SQLFunctionBatchCreate(BaseModel):
    functions: List[SQLFunctionCreate] = Field(..., description="List of functions to create")
    project_id: Optional[str] = Field(None, description="Project ID (optional, can be overridden by individual functions)")


class SQLFunctionCopyRequest(BaseModel):
    target_project_id: str = Field(..., description="Target project ID")
    function_id: str = Field(..., description="Source function ID")


class SQLFunctionListResponse(BaseModel):
    functions: List[SQLFunctionRead] = Field(..., description="List of SQL functions")
    total_count: int = Field(..., description="Total number of functions")
    project_id: Optional[str] = Field(None, description="Project ID filter applied")


class SQLFunctionParameter(BaseModel):
    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Parameter type")
    description: Optional[str] = Field(None, description="Parameter description")
    default: Optional[Any] = Field(None, description="Default value")
    required: bool = Field(True, description="Whether parameter is required")


class SQLFunctionMetadata(BaseModel):
    category: Optional[str] = Field(None, description="Function category")
    tags: Optional[List[str]] = Field(None, description="Function tags")
    complexity: Optional[str] = Field(None, description="Function complexity level")
    usage_count: Optional[int] = Field(0, description="Usage count")
    last_used: Optional[datetime] = Field(None, description="Last usage timestamp")
    documentation_url: Optional[str] = Field(None, description="Documentation URL")
    examples: Optional[List[str]] = Field(None, description="Usage examples") 
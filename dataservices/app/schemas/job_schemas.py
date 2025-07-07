"""
Pydantic schemas for job queue operations
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

from app.services.job_queue_service import JobType, JobStatus


class JobSubmitRequest(BaseModel):
    """Request model for submitting a job"""
    job_type: JobType = Field(..., description="Type of job to submit")
    project_id: str = Field(..., description="Project ID")
    entity_type: Optional[str] = Field(None, description="Type of entity being updated")
    entity_id: Optional[str] = Field(None, description="ID of entity being updated")
    user_id: Optional[str] = Field(None, description="User ID who triggered the update")
    session_id: Optional[str] = Field(None, description="Session ID")
    priority: int = Field(0, description="Job priority (lower = higher priority)", ge=0, le=10)
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class JobResponse(BaseModel):
    """Response model for job operations"""
    job_id: str = Field(..., description="Job ID")
    job_type: Optional[JobType] = Field(None, description="Job type")
    project_id: Optional[str] = Field(None, description="Project ID")
    status: JobStatus = Field(..., description="Job status")
    message: str = Field(..., description="Response message")


class JobStatusResponse(BaseModel):
    """Response model for job status"""
    job_id: str = Field(..., description="Job ID")
    job_type: JobType = Field(..., description="Job type")
    project_id: str = Field(..., description="Project ID")
    status: JobStatus = Field(..., description="Job status")
    created_at: Optional[datetime] = Field(None, description="Job creation timestamp")
    started_at: Optional[datetime] = Field(None, description="Job start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")
    result: Optional[Dict[str, Any]] = Field(None, description="Job result")
    error: Optional[str] = Field(None, description="Job error message")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Job metadata")


class JobListItem(BaseModel):
    """Model for job list items"""
    job_id: str = Field(..., description="Job ID")
    job_type: JobType = Field(..., description="Job type")
    project_id: str = Field(..., description="Project ID")
    status: JobStatus = Field(..., description="Job status")
    created_at: Optional[datetime] = Field(None, description="Job creation timestamp")
    priority: int = Field(..., description="Job priority")


class JobListResponse(BaseModel):
    """Response model for job list"""
    jobs: List[JobListItem] = Field(..., description="List of jobs")
    total: int = Field(..., description="Total number of jobs")
    limit: int = Field(..., description="Limit applied to the query")


class QueueStatsResponse(BaseModel):
    """Response model for queue statistics"""
    queue_length: int = Field(..., description="Number of jobs in queue")
    status_counts: Dict[str, int] = Field(..., description="Job counts by status")
    worker_running: bool = Field(..., description="Whether worker is running")
    timestamp: datetime = Field(..., description="Timestamp of stats")


class EntityUpdateRequest(BaseModel):
    """Request model for entity updates"""
    project_id: str = Field(..., description="Project ID")
    entity_type: str = Field(..., description="Type of entity")
    entity_id: str = Field(..., description="Entity ID")
    user_id: Optional[str] = Field(None, description="User ID")
    session_id: Optional[str] = Field(None, description="Session ID")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class EntityUpdateResponse(BaseModel):
    """Response model for entity updates"""
    message: str = Field(..., description="Update message")
    job_ids: Dict[str, str] = Field(..., description="Submitted job IDs")


class BulkUpdateRequest(BaseModel):
    """Request model for bulk entity updates"""
    project_id: str = Field(..., description="Project ID")
    entity_updates: List[EntityUpdateRequest] = Field(..., description="List of entity updates")
    user_id: Optional[str] = Field(None, description="User ID")
    session_id: Optional[str] = Field(None, description="Session ID")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class BulkUpdateResponse(BaseModel):
    """Response model for bulk entity updates"""
    message: str = Field(..., description="Update message")
    job_ids: List[str] = Field(..., description="List of submitted job IDs")
    total_jobs: int = Field(..., description="Total number of jobs submitted") 
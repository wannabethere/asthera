"""
Router for job queue management and monitoring
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.services.job_queue_service import job_queue_service, JobType, JobStatus
from app.services.entity_update_service import entity_update_service
from app.schemas.job_schemas import (
    JobSubmitRequest,
    JobResponse,
    JobStatusResponse,
    QueueStatsResponse,
    JobListResponse
)

router = APIRouter()


@router.post(
    "/jobs/submit",
    response_model=JobResponse,
    summary="Submit a new job to the queue"
)
async def submit_job(
    request: JobSubmitRequest,
    background_tasks: BackgroundTasks
):
    """Submit a new job to the queue"""
    try:
        job_id = await job_queue_service.submit_job(
            job_type=request.job_type,
            project_id=request.project_id,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            user_id=request.user_id,
            session_id=request.session_id,
            priority=request.priority,
            metadata=request.metadata
        )
        
        return JobResponse(
            job_id=job_id,
            job_type=request.job_type,
            project_id=request.project_id,
            status=JobStatus.PENDING,
            message="Job submitted successfully"
        )
        
    except Exception as e:
        raise HTTPException(400, f"Failed to submit job: {str(e)}")


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job status and details"
)
async def get_job_status(job_id: str):
    """Get the status and details of a specific job"""
    try:
        job_data = await job_queue_service.get_job_status(job_id)
        if not job_data:
            raise HTTPException(404, f"Job {job_id} not found")
        
        return JobStatusResponse(
            job_id=job_data.job_id,
            job_type=job_data.job_type,
            project_id=job_data.project_id,
            status=job_data.status,
            created_at=job_data.created_at,
            started_at=job_data.started_at,
            completed_at=job_data.completed_at,
            result=job_data.result,
            error=job_data.error,
            metadata=job_data.metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to get job status: {str(e)}")


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=JobResponse,
    summary="Cancel a pending job"
)
async def cancel_job(job_id: str):
    """Cancel a pending job"""
    try:
        success = await job_queue_service.cancel_job(job_id)
        if not success:
            raise HTTPException(404, f"Job {job_id} not found or not cancellable")
        
        return JobResponse(
            job_id=job_id,
            status=JobStatus.CANCELLED,
            message="Job cancelled successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to cancel job: {str(e)}")


@router.post(
    "/jobs/{job_id}/retry",
    response_model=JobResponse,
    summary="Retry a failed job"
)
async def retry_job(job_id: str):
    """Retry a failed job"""
    try:
        success = await job_queue_service.retry_job(job_id)
        if not success:
            raise HTTPException(404, f"Job {job_id} not found or not retryable")
        
        return JobResponse(
            job_id=job_id,
            status=JobStatus.PENDING,
            message="Job queued for retry"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to retry job: {str(e)}")


@router.get(
    "/jobs",
    response_model=JobListResponse,
    summary="List jobs with optional filtering"
)
async def list_jobs(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    job_type: Optional[JobType] = Query(None, description="Filter by job type"),
    status: Optional[JobStatus] = Query(None, description="Filter by job status"),
    limit: int = Query(50, description="Maximum number of jobs to return", ge=1, le=100)
):
    """List jobs with optional filtering"""
    try:
        # This would need to be implemented in the job queue service
        # For now, return a placeholder response
        return JobListResponse(
            jobs=[],
            total=0,
            limit=limit
        )
        
    except Exception as e:
        raise HTTPException(500, f"Failed to list jobs: {str(e)}")


@router.get(
    "/queue/stats",
    response_model=QueueStatsResponse,
    summary="Get queue statistics"
)
async def get_queue_stats():
    """Get current queue statistics"""
    try:
        stats = await job_queue_service.get_queue_stats()
        
        return QueueStatsResponse(
            queue_length=stats["queue_length"],
            status_counts=stats["status_counts"],
            worker_running=stats["worker_running"],
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        raise HTTPException(500, f"Failed to get queue stats: {str(e)}")


@router.post(
    "/queue/start",
    summary="Start the job queue worker"
)
async def start_worker():
    """Start the job queue worker"""
    try:
        await job_queue_service.start_worker()
        return {"message": "Job queue worker started successfully"}
        
    except Exception as e:
        raise HTTPException(500, f"Failed to start worker: {str(e)}")


@router.post(
    "/queue/stop",
    summary="Stop the job queue worker"
)
async def stop_worker():
    """Stop the job queue worker"""
    try:
        await job_queue_service.stop_worker()
        return {"message": "Job queue worker stopped successfully"}
        
    except Exception as e:
        raise HTTPException(500, f"Failed to stop worker: {str(e)}")


@router.post(
    "/queue/cleanup",
    summary="Clean up old completed jobs"
)
async def cleanup_old_jobs(
    days: int = Query(7, description="Number of days to keep jobs", ge=1, le=365)
):
    """Clean up old completed/failed jobs"""
    try:
        await job_queue_service.cleanup_old_jobs(days)
        return {"message": f"Cleaned up jobs older than {days} days"}
        
    except Exception as e:
        raise HTTPException(500, f"Failed to cleanup jobs: {str(e)}")


# Entity update endpoints
@router.post(
    "/entity-updates/table",
    summary="Handle table update"
)
async def handle_table_update(
    project_id: str,
    table_id: str,
    user_id: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None)
):
    """Handle table update and submit jobs"""
    try:
        result = await entity_update_service.on_table_updated(
            project_id=project_id,
            table_id=table_id,
            user_id=user_id,
            session_id=session_id
        )
        
        return {
            "message": "Table update handled successfully",
            "job_ids": result
        }
        
    except Exception as e:
        raise HTTPException(500, f"Failed to handle table update: {str(e)}")


@router.post(
    "/entity-updates/column",
    summary="Handle column update"
)
async def handle_column_update(
    project_id: str,
    table_id: str,
    column_id: str,
    user_id: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None)
):
    """Handle column update and submit jobs"""
    try:
        result = await entity_update_service.on_column_updated(
            project_id=project_id,
            table_id=table_id,
            column_id=column_id,
            user_id=user_id,
            session_id=session_id
        )
        
        return {
            "message": "Column update handled successfully",
            "job_ids": result
        }
        
    except Exception as e:
        raise HTTPException(500, f"Failed to handle column update: {str(e)}")


@router.post(
    "/entity-updates/metric",
    summary="Handle metric update"
)
async def handle_metric_update(
    project_id: str,
    metric_id: str,
    user_id: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None)
):
    """Handle metric update and submit jobs"""
    try:
        result = await entity_update_service.on_metric_updated(
            project_id=project_id,
            metric_id=metric_id,
            user_id=user_id,
            session_id=session_id
        )
        
        return {
            "message": "Metric update handled successfully",
            "job_ids": result
        }
        
    except Exception as e:
        raise HTTPException(500, f"Failed to handle metric update: {str(e)}")


@router.post(
    "/entity-updates/view",
    summary="Handle view update"
)
async def handle_view_update(
    project_id: str,
    view_id: str,
    user_id: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None)
):
    """Handle view update and submit jobs"""
    try:
        result = await entity_update_service.on_view_updated(
            project_id=project_id,
            view_id=view_id,
            user_id=user_id,
            session_id=session_id
        )
        
        return {
            "message": "View update handled successfully",
            "job_ids": result
        }
        
    except Exception as e:
        raise HTTPException(500, f"Failed to handle view update: {str(e)}")


@router.post(
    "/entity-updates/calculated-column",
    summary="Handle calculated column update"
)
async def handle_calculated_column_update(
    project_id: str,
    calculated_column_id: str,
    user_id: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None)
):
    """Handle calculated column update and submit jobs"""
    try:
        result = await entity_update_service.on_calculated_column_updated(
            project_id=project_id,
            calculated_column_id=calculated_column_id,
            user_id=user_id,
            session_id=session_id
        )
        
        return {
            "message": "Calculated column update handled successfully",
            "job_ids": result
        }
        
    except Exception as e:
        raise HTTPException(500, f"Failed to handle calculated column update: {str(e)}")


@router.post(
    "/entity-updates/project-commit",
    summary="Handle project commit"
)
async def handle_project_commit(
    project_id: str,
    user_id: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None)
):
    """Handle project commit and submit post-commit workflow and ChromaDB indexing"""
    try:
        result = await entity_update_service.on_project_committed(
            project_id=project_id,
            user_id=user_id,
            session_id=session_id
        )
        
        return {
            "message": "Project commit handled successfully",
            "job_ids": result
        }
        
    except Exception as e:
        raise HTTPException(500, f"Failed to handle project commit: {str(e)}")


@router.post(
    "/chromadb-indexing/{project_id}",
    summary="Trigger ChromaDB indexing for a project"
)
async def trigger_chromadb_indexing(
    project_id: str,
    user_id: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None)
):
    """Manually trigger ChromaDB indexing for a project"""
    try:
        job_id = await job_queue_service.submit_job(
            job_type=JobType.CHROMADB_INDEXING,
            project_id=project_id,
            entity_type="project",
            entity_id=project_id,
            user_id=user_id,
            session_id=session_id,
            priority=1,
            metadata={
                "update_type": "manual_indexing",
                "triggered_at": datetime.utcnow().isoformat()
            }
        )
        
        return {
            "message": "ChromaDB indexing job submitted successfully",
            "job_id": job_id,
            "project_id": project_id
        }
        
    except Exception as e:
        raise HTTPException(500, f"Failed to submit ChromaDB indexing job: {str(e)}") 
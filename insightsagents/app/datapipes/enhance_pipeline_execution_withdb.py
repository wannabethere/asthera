"""
Enhanced Pipeline Execution REST API with Database Integration
=============================================================
FastAPI service with database storage, versioning, and Chroma integration
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import asyncio
import json
import os
from datetime import datetime
import uuid

# Import the integrated pipeline execution service
from integrated_pipeline_service import IntegratedPipelineExecutionService, EnhancedExecutionResult

# Enhanced Pydantic models for API
class PipelineExecutionRequest(BaseModel):
    code: str = Field(..., description="Python pipeline code to execute")
    execution_id: Optional[str] = Field(None, description="Optional execution ID")
    additional_env_vars: Optional[Dict[str, str]] = Field(None, description="Additional environment variables")
    additional_python_paths: Optional[List[str]] = Field(None, description="Additional Python paths")
    timeout_seconds: Optional[int] = Field(300, description="Timeout in seconds")
    user_id: Optional[str] = Field(None, description="User ID for tracking")
    session_id: Optional[str] = Field(None, description="Session ID for tracking")
    save_to_database: Optional[bool] = Field(True, description="Whether to save pipeline to database")

class GeneratedPipelineRequest(BaseModel):
    analysis_results: Dict[str, Any] = Field(..., description="Analysis results from code generation")
    data_file_path: Optional[str] = Field(None, description="Path to data file")
    user_id: Optional[str] = Field(None, description="User ID for tracking")
    session_id: Optional[str] = Field(None, description="Session ID for tracking")

class EnhancedExecutionResponse(BaseModel):
    execution_id: str
    status: str
    start_time: datetime
    end_time: Optional[datetime]
    output: str
    error: str
    exit_code: Optional[int]
    file_path: str
    duration: Optional[float]
    pipeline_code_id: Optional[str]
    database_stored: bool
    chroma_stored: bool
    similar_pipelines: Optional[List[Dict[str, Any]]]
    version_info: Optional[Dict[str, Any]]

class PipelineSearchRequest(BaseModel):
    question: str = Field(..., description="Question to search for")
    analysis_type: Optional[str] = Field(None, description="Analysis type filter")
    use_chroma: bool = Field(True, description="Whether to use Chroma search")
    limit: int = Field(5, description="Maximum number of results")

class AnalyticsResponse(BaseModel):
    period: Dict[str, Any]
    pipeline_stats: Dict[str, Any]
    top_analysis_types: List[Dict[str, Any]]
    top_pipeline_types: List[Dict[str, Any]]
    execution_stats: Dict[str, Any]

# Initialize FastAPI app
app = FastAPI(
    title="Enhanced Pipeline Execution Service",
    description="Execute generated ML pipeline code with database storage, versioning, and similarity search",
    version="2.0.0"
)

# Initialize the integrated pipeline execution service
integrated_service = IntegratedPipelineExecutionService(
    base_directory=os.getenv("PIPELINE_BASE_DIR", "/tmp/pipeline_executions"),
    python_path_additions=os.getenv("ADDITIONAL_PYTHON_PATHS", "").split(":") if os.getenv("ADDITIONAL_PYTHON_PATHS") else [],
    timeout_seconds=int(os.getenv("DEFAULT_TIMEOUT", "300")),
    cleanup_after_execution=os.getenv("CLEANUP_AFTER_EXECUTION", "false").lower() == "true",
    database_url=os.getenv("DATABASE_URL", "sqlite:///pipeline_codes.db"),
    enable_chroma=os.getenv("ENABLE_CHROMA", "true").lower() == "true",
    auto_save_pipelines=os.getenv("AUTO_SAVE_PIPELINES", "true").lower() == "true"
)

# Store execution tasks for monitoring
execution_tasks: Dict[str, asyncio.Task] = {}


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    print("Enhanced Pipeline Execution Service starting up...")
    print(f"Base directory: {integrated_service.base_directory}")
    print(f"Database URL: {integrated_service.db_service.database_url}")
    print(f"Chroma enabled: {integrated_service.db_service.enable_chroma}")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    print("Enhanced Pipeline Execution Service shutting down...")
    # Cancel any running tasks
    for task in execution_tasks.values():
        if not task.done():
            task.cancel()


# Enhanced API endpoints

@app.post("/execute", response_model=EnhancedExecutionResponse)
async def execute_pipeline(request: PipelineExecutionRequest):
    """Execute a pipeline code with database integration"""
    try:
        result = await integrated_service.execute_pipeline(
            code=request.code,
            execution_id=request.execution_id,
            additional_env_vars=request.additional_env_vars,
            additional_python_paths=request.additional_python_paths,
            user_id=request.user_id,
            session_id=request.session_id,
            save_to_database=request.save_to_database
        )
        
        return EnhancedExecutionResponse(
            execution_id=result.execution_id,
            status=result.status.value,
            start_time=result.start_time,
            end_time=result.end_time,
            output=result.output,
            error=result.error,
            exit_code=result.exit_code,
            file_path=result.file_path,
            duration=result.duration,
            pipeline_code_id=result.pipeline_code_id,
            database_stored=result.database_stored,
            chroma_stored=result.chroma_stored,
            similar_pipelines=result.similar_pipelines,
            version_info=result.version_info
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/execute-async", response_model=Dict[str, str])
async def execute_pipeline_async(request: PipelineExecutionRequest):
    """Execute a pipeline code asynchronously with database integration"""
    try:
        execution_id = request.execution_id or str(uuid.uuid4())
        
        # Create async task
        task = asyncio.create_task(
            integrated_service.execute_pipeline(
                code=request.code,
                execution_id=execution_id,
                additional_env_vars=request.additional_env_vars,
                additional_python_paths=request.additional_python_paths,
                user_id=request.user_id,
                session_id=request.session_id,
                save_to_database=request.save_to_database
            )
        )
        
        # Store task for monitoring
        execution_tasks[execution_id] = task
        
        return {"execution_id": execution_id, "status": "started"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/execute-generated", response_model=EnhancedExecutionResponse)
async def execute_generated_pipeline(request: GeneratedPipelineRequest):
    """Execute a pipeline from generated analysis results"""
    try:
        result = await integrated_service.execute_generated_pipeline(
            analysis_results=request.analysis_results,
            data_file_path=request.data_file_path,
            user_id=request.user_id,
            session_id=request.session_id
        )
        
        return EnhancedExecutionResponse(
            execution_id=result.execution_id,
            status=result.status.value,
            start_time=result.start_time,
            end_time=result.end_time,
            output=result.output,
            error=result.error,
            exit_code=result.exit_code,
            file_path=result.file_path,
            duration=result.duration,
            pipeline_code_id=result.pipeline_code_id,
            database_stored=result.database_stored,
            chroma_stored=result.chroma_stored,
            similar_pipelines=result.similar_pipelines,
            version_info=result.version_info
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# New database-related endpoints

@app.post("/search", response_model=List[Dict[str, Any]])
async def search_similar_pipelines(request: PipelineSearchRequest):
    """Search for similar pipelines using database and Chroma"""
    try:
        results = await integrated_service.find_similar_pipelines(
            question=request.question,
            analysis_type=request.analysis_type,
            use_chroma=request.use_chroma
        )
        
        return results[:request.limit]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(days: int = 30):
    """Get pipeline usage analytics"""
    try:
        analytics = integrated_service.get_pipeline_analytics(days=days)
        
        return AnalyticsResponse(
            period=analytics['period'],
            pipeline_stats=analytics['pipeline_stats'],
            top_analysis_types=analytics['top_analysis_types'],
            top_pipeline_types=analytics['top_pipeline_types'],
            execution_stats=analytics['execution_stats']
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/pipeline/{pipeline_id}/history")
async def get_pipeline_history(pipeline_id: str):
    """Get version history of a pipeline"""
    try:
        history = integrated_service.get_pipeline_history(pipeline_id)
        
        if not history:
            raise HTTPException(status_code=404, detail="Pipeline not found")
        
        return {"pipeline_id": pipeline_id, "history": history}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/pipeline/{pipeline_id}")
async def get_pipeline_details(pipeline_id: str):
    """Get detailed information about a specific pipeline"""
    try:
        session = integrated_service.db_service.get_session()
        
        try:
            from database_models import PipelineCode, PipelineExecution
            
            pipeline = session.query(PipelineCode).filter(
                PipelineCode.id == pipeline_id
            ).first()
            
            if not pipeline:
                raise HTTPException(status_code=404, detail="Pipeline not found")
            
            # Get executions for this pipeline
            executions = session.query(PipelineExecution).filter(
                PipelineExecution.pipeline_code_id == pipeline_id
            ).order_by(PipelineExecution.started_at.desc()).all()
            
            return {
                "id": pipeline.id,
                "question": pipeline.question,
                "analysis_type": pipeline.analysis_type,
                "pipeline_type": pipeline.pipeline_type,
                "function_name": pipeline.function_name,
                "status": pipeline.status,
                "version": pipeline.version,
                "is_latest": pipeline.is_latest,
                "generated_on": pipeline.generated_on.isoformat(),
                "code": pipeline.generated_code,
                "metadata": pipeline.metadata,
                "tags": pipeline.tags,
                "executions": [
                    {
                        "execution_id": exec.execution_id,
                        "status": exec.status,
                        "started_at": exec.started_at.isoformat() if exec.started_at else None,
                        "completed_at": exec.completed_at.isoformat() if exec.completed_at else None,
                        "duration_seconds": exec.duration_seconds,
                        "exit_code": exec.exit_code
                    }
                    for exec in executions
                ]
            }
            
        finally:
            session.close()
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/pipeline/{pipeline_id}/code")
async def get_pipeline_code(pipeline_id: str):
    """Get the raw code for a specific pipeline"""
    try:
        session = integrated_service.db_service.get_session()
        
        try:
            from database_models import PipelineCode
            
            pipeline = session.query(PipelineCode).filter(
                PipelineCode.id == pipeline_id
            ).first()
            
            if not pipeline:
                raise HTTPException(status_code=404, detail="Pipeline not found")
            
            return {
                "pipeline_id": pipeline.id,
                "code": pipeline.generated_code,
                "metadata": {
                    "question": pipeline.question,
                    "analysis_type": pipeline.analysis_type,
                    "pipeline_type": pipeline.pipeline_type,
                    "function_name": pipeline.function_name,
                    "version": pipeline.version,
                    "generated_on": pipeline.generated_on.isoformat()
                }
            }
            
        finally:
            session.close()
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/pipelines")
async def list_pipelines(
    limit: int = 50,
    offset: int = 0,
    analysis_type: Optional[str] = None,
    pipeline_type: Optional[str] = None,
    user_id: Optional[str] = None,
    latest_only: bool = True
):
    """List pipelines with filtering options"""
    try:
        session = integrated_service.db_service.get_session()
        
        try:
            from database_models import PipelineCode
            from sqlalchemy import and_, desc
            
            query = session.query(PipelineCode)
            
            # Apply filters
            filters = []
            
            if latest_only:
                filters.append(PipelineCode.is_latest == True)
            
            if analysis_type:
                filters.append(PipelineCode.analysis_type == analysis_type)
            
            if pipeline_type:
                filters.append(PipelineCode.pipeline_type == pipeline_type)
            
            if user_id:
                filters.append(PipelineCode.user_id == user_id)
            
            if filters:
                query = query.filter(and_(*filters))
            
            # Apply ordering and pagination
            pipelines = query.order_by(desc(PipelineCode.generated_on)).offset(offset).limit(limit).all()
            
            # Get total count
            total_count = query.count()
            
            return {
                "pipelines": [
                    {
                        "id": p.id,
                        "question": p.question,
                        "analysis_type": p.analysis_type,
                        "pipeline_type": p.pipeline_type,
                        "function_name": p.function_name,
                        "status": p.status,
                        "version": p.version,
                        "is_latest": p.is_latest,
                        "generated_on": p.generated_on.isoformat(),
                        "user_id": p.user_id,
                        "tags": p.tags
                    }
                    for p in pipelines
                ],
                "total_count": total_count,
                "limit": limit,
                "offset": offset
            }
            
        finally:
            session.close()
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Keep existing endpoints from original API

@app.get("/status/{execution_id}")
async def get_execution_status(execution_id: str):
    """Get the status of a specific execution"""
    try:
        # Check if it's in our async tasks
        if execution_id in execution_tasks:
            task = execution_tasks[execution_id]
            if task.done():
                try:
                    result = await task
                    return {
                        "execution_id": execution_id,
                        "status": result.status.value,
                        "is_running": False,
                        "database_stored": result.database_stored,
                        "pipeline_code_id": result.pipeline_code_id
                    }
                except Exception:
                    return {
                        "execution_id": execution_id,
                        "status": "failed",
                        "is_running": False
                    }
            else:
                return {
                    "execution_id": execution_id,
                    "status": "running",
                    "is_running": True
                }
        
        # Check database for completed executions
        session = integrated_service.db_service.get_session()
        try:
            from database_models import PipelineExecution
            
            execution = session.query(PipelineExecution).filter(
                PipelineExecution.execution_id == execution_id
            ).first()
            
            if execution:
                return {
                    "execution_id": execution_id,
                    "status": execution.status,
                    "is_running": False,
                    "pipeline_code_id": execution.pipeline_code_id
                }
        finally:
            session.close()
        
        raise HTTPException(status_code=404, detail="Execution not found")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/result/{execution_id}")
async def get_execution_result(execution_id: str):
    """Get the result of a completed execution"""
    try:
        # Check if it's in our async tasks and completed
        if execution_id in execution_tasks:
            task = execution_tasks[execution_id]
            if task.done():
                try:
                    result = await task
                    return EnhancedExecutionResponse(
                        execution_id=result.execution_id,
                        status=result.status.value,
                        start_time=result.start_time,
                        end_time=result.end_time,
                        output=result.output,
                        error=result.error,
                        exit_code=result.exit_code,
                        file_path=result.file_path,
                        duration=result.duration,
                        pipeline_code_id=result.pipeline_code_id,
                        database_stored=result.database_stored,
                        chroma_stored=result.chroma_stored,
                        similar_pipelines=result.similar_pipelines,
                        version_info=result.version_info
                    )
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Error retrieving result: {str(e)}")
            else:
                raise HTTPException(status_code=400, detail="Execution is still running")
        
        raise HTTPException(status_code=404, detail="Execution not found in active tasks")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/cancel/{execution_id}")
async def cancel_execution(execution_id: str):
    """Cancel a running execution"""
    try:
        # Try to cancel async task first
        if execution_id in execution_tasks:
            task = execution_tasks[execution_id]
            if not task.done():
                task.cancel()
                del execution_tasks[execution_id]
                return {"message": f"Execution {execution_id} cancelled"}
        
        # Try to cancel through service
        success = integrated_service.cancel_execution(execution_id)
        if success:
            return {"message": f"Execution {execution_id} cancelled"}
        else:
            raise HTTPException(status_code=404, detail="Execution not found or already completed")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/executions")
async def list_executions():
    """List all executions"""
    try:
        running_executions = list(execution_tasks.keys())
        
        # Get recent executions from database
        session = integrated_service.db_service.get_session()
        try:
            from database_models import PipelineExecution
            from sqlalchemy import desc
            
            recent_executions = session.query(PipelineExecution).order_by(
                desc(PipelineExecution.started_at)
            ).limit(50).all()
            
            completed_executions = [
                {
                    "execution_id": exec.execution_id,
                    "status": exec.status,
                    "pipeline_code_id": exec.pipeline_code_id,
                    "started_at": exec.started_at.isoformat() if exec.started_at else None,
                    "completed_at": exec.completed_at.isoformat() if exec.completed_at else None,
                    "duration_seconds": exec.duration_seconds
                }
                for exec in recent_executions
            ]
            
        finally:
            session.close()
        
        return {
            "running_executions": running_executions,
            "recent_executions": completed_executions,
            "total_running": len(running_executions),
            "total_recent": len(completed_executions)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload-data")
async def upload_data_file(file: UploadFile = File(...)):
    """Upload a data file for pipeline execution"""
    try:
        # Save uploaded file
        upload_dir = integrated_service.base_directory / "uploads"
        upload_dir.mkdir(exist_ok=True)
        
        file_path = upload_dir / f"{uuid.uuid4()}_{file.filename}"
        
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        return {
            "filename": file.filename,
            "file_path": str(file_path),
            "size": len(content),
            "message": "File uploaded successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint with database status"""
    try:
        # Check database connection
        session = integrated_service.db_service.get_session()
        try:
            from database_models import PipelineCode
            pipeline_count = session.query(PipelineCode).count()
            db_status = "healthy"
        except Exception as e:
            db_status = f"error: {str(e)}"
            pipeline_count = None
        finally:
            session.close()
        
        return {
            "status": "healthy",
            "service": "Enhanced Pipeline Execution Service",
            "timestamp": datetime.now().isoformat(),
            "running_executions": len(execution_tasks),
            "base_directory": str(integrated_service.base_directory),
            "database": {
                "status": db_status,
                "url": integrated_service.db_service.database_url,
                "pipeline_count": pipeline_count,
                "chroma_enabled": integrated_service.db_service.enable_chroma
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=int(os.getenv("PORT", "8000")),
        log_level="info"
    )
"""
Pipeline Execution REST API
===========================
FastAPI service for executing generated pipeline code
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import asyncio
import json
import os
from datetime import datetime
import uuid

# Import your pipeline execution service
from pipeline_execution_service import PipelineExecutionService, ExecutionResult, ExecutionStatus

# Pydantic models for API
class PipelineExecutionRequest(BaseModel):
    code: str = Field(..., description="Python pipeline code to execute")
    execution_id: Optional[str] = Field(None, description="Optional execution ID")
    additional_env_vars: Optional[Dict[str, str]] = Field(None, description="Additional environment variables")
    additional_python_paths: Optional[List[str]] = Field(None, description="Additional Python paths")
    timeout_seconds: Optional[int] = Field(300, description="Timeout in seconds")

class GeneratedPipelineRequest(BaseModel):
    analysis_results: Dict[str, Any] = Field(..., description="Analysis results from code generation")
    data_file_path: Optional[str] = Field(None, description="Path to data file")

class ExecutionResponse(BaseModel):
    execution_id: str
    status: str
    start_time: datetime
    end_time: Optional[datetime]
    output: str
    error: str
    exit_code: Optional[int]
    file_path: str
    duration: Optional[float]

class ExecutionStatusResponse(BaseModel):
    execution_id: str
    status: str
    is_running: bool

# Initialize FastAPI app
app = FastAPI(
    title="Pipeline Execution Service",
    description="Execute generated ML pipeline code safely and efficiently",
    version="1.0.0"
)

# Initialize the pipeline execution service
pipeline_service = PipelineExecutionService(
    base_directory=os.getenv("PIPELINE_BASE_DIR", "/tmp/pipeline_executions"),
    python_path_additions=os.getenv("ADDITIONAL_PYTHON_PATHS", "").split(":") if os.getenv("ADDITIONAL_PYTHON_PATHS") else [],
    timeout_seconds=int(os.getenv("DEFAULT_TIMEOUT", "300")),
    cleanup_after_execution=os.getenv("CLEANUP_AFTER_EXECUTION", "false").lower() == "true"
)

# Store execution tasks for monitoring
execution_tasks: Dict[str, asyncio.Task] = {}


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    print("Pipeline Execution Service starting up...")
    print(f"Base directory: {pipeline_service.base_directory}")
    print(f"Python path additions: {pipeline_service.python_path_additions}")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    print("Pipeline Execution Service shutting down...")
    # Cancel any running tasks
    for task in execution_tasks.values():
        if not task.done():
            task.cancel()


@app.post("/execute", response_model=ExecutionResponse)
async def execute_pipeline(request: PipelineExecutionRequest, background_tasks: BackgroundTasks):
    """
    Execute a pipeline code
    """
    try:
        execution_id = request.execution_id or str(uuid.uuid4())
        
        # Execute the pipeline
        result = await pipeline_service.execute_pipeline(
            code=request.code,
            execution_id=execution_id,
            additional_env_vars=request.additional_env_vars,
            additional_python_paths=request.additional_python_paths
        )
        
        return ExecutionResponse(
            execution_id=result.execution_id,
            status=result.status.value,
            start_time=result.start_time,
            end_time=result.end_time,
            output=result.output,
            error=result.error,
            exit_code=result.exit_code,
            file_path=result.file_path,
            duration=result.duration
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/execute-async", response_model=Dict[str, str])
async def execute_pipeline_async(request: PipelineExecutionRequest):
    """
    Execute a pipeline code asynchronously and return execution ID immediately
    """
    try:
        execution_id = request.execution_id or str(uuid.uuid4())
        
        # Create async task
        task = asyncio.create_task(
            pipeline_service.execute_pipeline(
                code=request.code,
                execution_id=execution_id,
                additional_env_vars=request.additional_env_vars,
                additional_python_paths=request.additional_python_paths
            )
        )
        
        # Store task for monitoring
        execution_tasks[execution_id] = task
        
        return {"execution_id": execution_id, "status": "started"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/execute-generated", response_model=ExecutionResponse)
async def execute_generated_pipeline(request: GeneratedPipelineRequest):
    """
    Execute a pipeline from generated analysis results
    """
    try:
        if "generated_code" not in request.analysis_results:
            raise HTTPException(status_code=400, detail="No generated code found in analysis results")
        
        result = await pipeline_service.execute_pipeline(
            code=request.analysis_results["generated_code"],
            data_file_path=request.data_file_path,
            additional_env_vars={
                "PIPELINE_ANALYSIS_TYPE": request.analysis_results.get("analysis_type", "unknown"),
                "PIPELINE_GENERATION_TIME": str(datetime.now().isoformat())
            }
        )
        
        return ExecutionResponse(
            execution_id=result.execution_id,
            status=result.status.value,
            start_time=result.start_time,
            end_time=result.end_time,
            output=result.output,
            error=result.error,
            exit_code=result.exit_code,
            file_path=result.file_path,
            duration=result.duration
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status/{execution_id}", response_model=ExecutionStatusResponse)
async def get_execution_status(execution_id: str):
    """
    Get the status of a specific execution
    """
    try:
        # Check if it's in our async tasks
        if execution_id in execution_tasks:
            task = execution_tasks[execution_id]
            if task.done():
                try:
                    result = await task
                    return ExecutionStatusResponse(
                        execution_id=execution_id,
                        status=result.status.value,
                        is_running=False
                    )
                except Exception:
                    return ExecutionStatusResponse(
                        execution_id=execution_id,
                        status="failed",
                        is_running=False
                    )
            else:
                return ExecutionStatusResponse(
                    execution_id=execution_id,
                    status="running",
                    is_running=True
                )
        
        # Check if it's a completed execution
        execution_dir = pipeline_service.base_directory / execution_id
        if execution_dir.exists():
            return ExecutionStatusResponse(
                execution_id=execution_id,
                status="completed",
                is_running=False
            )
        
        raise HTTPException(status_code=404, detail="Execution not found")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/result/{execution_id}")
async def get_execution_result(execution_id: str):
    """
    Get the result of a completed execution
    """
    try:
        # Check if it's in our async tasks and completed
        if execution_id in execution_tasks:
            task = execution_tasks[execution_id]
            if task.done():
                try:
                    result = await task
                    return ExecutionResponse(
                        execution_id=result.execution_id,
                        status=result.status.value,
                        start_time=result.start_time,
                        end_time=result.end_time,
                        output=result.output,
                        error=result.error,
                        exit_code=result.exit_code,
                        file_path=result.file_path,
                        duration=result.duration
                    )
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Error retrieving result: {str(e)}")
            else:
                raise HTTPException(status_code=400, detail="Execution is still running")
        
        raise HTTPException(status_code=404, detail="Execution not found")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/cancel/{execution_id}")
async def cancel_execution(execution_id: str):
    """
    Cancel a running execution
    """
    try:
        # Try to cancel async task first
        if execution_id in execution_tasks:
            task = execution_tasks[execution_id]
            if not task.done():
                task.cancel()
                del execution_tasks[execution_id]
                return {"message": f"Execution {execution_id} cancelled"}
        
        # Try to cancel through service
        success = pipeline_service.cancel_execution(execution_id)
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
    """
    List all executions
    """
    try:
        completed_executions = pipeline_service.list_executions()
        running_executions = list(execution_tasks.keys())
        
        return {
            "completed_executions": completed_executions,
            "running_executions": running_executions,
            "total": len(completed_executions) + len(running_executions)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload-data")
async def upload_data_file(file: UploadFile = File(...)):
    """
    Upload a data file for pipeline execution
    """
    try:
        # Save uploaded file
        upload_dir = pipeline_service.base_directory / "uploads"
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
    """
    Health check endpoint
    """
    return {
        "status": "healthy",
        "service": "Pipeline Execution Service",
        "timestamp": datetime.now().isoformat(),
        "running_executions": len(execution_tasks),
        "base_directory": str(pipeline_service.base_directory)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=int(os.getenv("PORT", "8000")),
        log_level="info"
    )
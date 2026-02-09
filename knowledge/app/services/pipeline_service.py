"""
Pipeline Service

Orchestrates pipeline execution with streaming support.
Provides business logic layer between routers and pipelines.
"""
import logging
import time
from typing import Dict, Any, Optional, AsyncGenerator, Callable
from pydantic import BaseModel, Field

from app.services.base import BaseService, ServiceRequest, ServiceResponse

logger = logging.getLogger(__name__)


class PipelineExecutionRequest(ServiceRequest):
    """Request for pipeline execution"""
    pipeline_id: str = Field(..., description="Pipeline ID to execute")
    inputs: Dict[str, Any] = Field(..., description="Pipeline inputs")
    configuration: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Pipeline configuration")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Request metadata")
    stream: bool = Field(default=False, description="Enable streaming execution")


class PipelineExecutionResponse(ServiceResponse):
    """Response from pipeline execution"""
    pipeline_id: Optional[str] = None
    duration_seconds: Optional[float] = None
    steps: Optional[int] = None


class PipelineServiceError(Exception):
    """Pipeline service error"""
    pass


class PipelineService(BaseService[PipelineExecutionRequest, PipelineExecutionResponse]):
    """
    Service for executing pipelines with streaming support
    
    Responsibilities:
    - Pipeline lookup and validation
    - Execution orchestration
    - Result formatting
    - Streaming event generation
    - Error handling
    """
    
    def __init__(
        self,
        maxsize: int = 1_000_000,
        ttl: int = 120
    ):
        """
        Initialize pipeline service
        
        Args:
            maxsize: Cache size
            ttl: Cache TTL in seconds
        """
        super().__init__(maxsize=maxsize, ttl=ttl)
        # Deferred import to avoid circular import: app.pipelines -> app.services -> pipeline_service -> app.pipelines
        from app.pipelines import get_pipeline_registry
        self.registry = get_pipeline_registry()
    
    async def _process_request_impl(
        self,
        request: PipelineExecutionRequest
    ) -> PipelineExecutionResponse:
        """
        Execute pipeline
        
        Args:
            request: Pipeline execution request
            
        Returns:
            Pipeline execution response
        """
        start_time = time.time()
        
        try:
            # Get pipeline
            pipeline = self.registry.get_pipeline(request.pipeline_id)
            if not pipeline:
                raise PipelineServiceError(f"Pipeline not found: {request.pipeline_id}")
            
            logger.info(f"Executing pipeline: {request.pipeline_id}")
            
            # Execute pipeline
            result = await pipeline.run(
                inputs=request.inputs,
                configuration=request.configuration
            )
            
            duration = time.time() - start_time
            
            logger.info(f"Pipeline execution completed: {request.pipeline_id} in {duration:.3f}s")
            
            return PipelineExecutionResponse(
                success=True,
                data=result.get("data"),
                metadata={
                    **(result.get("metadata", {})),
                    **(request.metadata or {})
                },
                request_id=request.request_id,
                pipeline_id=request.pipeline_id,
                duration_seconds=duration
            )
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Pipeline execution failed: {request.pipeline_id} - {str(e)}", exc_info=True)
            
            return PipelineExecutionResponse(
                success=False,
                error=str(e),
                request_id=request.request_id,
                pipeline_id=request.pipeline_id,
                duration_seconds=duration
            )
    
    async def stream_pipeline_execution(
        self,
        pipeline_id: str,
        inputs: Dict[str, Any],
        configuration: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream pipeline execution with real-time events
        
        Args:
            pipeline_id: Pipeline ID
            inputs: Pipeline inputs
            configuration: Pipeline configuration
            metadata: Request metadata
            status_callback: Optional status callback
            
        Yields:
            Event dictionaries
        """
        start_time = time.time()
        
        try:
            # Get pipeline
            pipeline = self.registry.get_pipeline(pipeline_id)
            if not pipeline:
                yield {
                    "event": "error",
                    "pipeline_id": pipeline_id,
                    "error": f"Pipeline not found: {pipeline_id}",
                    "error_type": "PipelineNotFoundError"
                }
                return
            
            # Yield start event
            yield {
                "event": "pipeline_started",
                "pipeline_id": pipeline_id,
                "timestamp": time.time(),
                "inputs": inputs,
                "metadata": metadata
            }
            
            # Create status callback wrapper
            async def streaming_callback(status: str, data: Dict[str, Any]):
                """Wrap status callback to yield events"""
                yield {
                    "event": "pipeline_progress",
                    "pipeline_id": pipeline_id,
                    "status": status,
                    "data": data,
                    "timestamp": time.time()
                }
                
                if status_callback:
                    await status_callback(status, data)
            
            # Execute pipeline
            logger.info(f"Streaming pipeline execution: {pipeline_id}")
            
            result = await pipeline.run(
                inputs=inputs,
                status_callback=streaming_callback,
                configuration=configuration
            )
            
            duration = time.time() - start_time
            
            # Yield completion event
            yield {
                "event": "pipeline_completed",
                "pipeline_id": pipeline_id,
                "success": result.get("success", True),
                "data": result.get("data"),
                "metadata": result.get("metadata"),
                "duration_seconds": duration,
                "timestamp": time.time()
            }
            
            logger.info(f"Pipeline streaming completed: {pipeline_id} in {duration:.3f}s")
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Pipeline streaming failed: {pipeline_id} - {str(e)}", exc_info=True)
            
            yield {
                "event": "pipeline_error",
                "pipeline_id": pipeline_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "duration_seconds": duration,
                "timestamp": time.time()
            }
    
    async def execute_pipeline_category(
        self,
        category: str,
        inputs: Dict[str, Any],
        pipeline_id: Optional[str] = None,
        configuration: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PipelineExecutionResponse:
        """
        Execute pipeline from category (uses default if pipeline_id not specified)
        
        Args:
            category: Pipeline category
            inputs: Pipeline inputs
            pipeline_id: Optional specific pipeline ID
            configuration: Pipeline configuration
            metadata: Request metadata
            
        Returns:
            Pipeline execution response
        """
        start_time = time.time()
        
        try:
            # Get pipeline from category
            pipeline = self.registry.get_category_pipeline(category, pipeline_id)
            if not pipeline:
                raise PipelineServiceError(f"No pipeline found for category: {category}")
            
            # Get pipeline config for ID
            pipeline_config = None
            for pid, config in self.registry._pipelines.items():
                if config.pipeline == pipeline:
                    pipeline_config = config
                    break
            
            actual_pipeline_id = pipeline_config.pipeline_id if pipeline_config else category
            
            logger.info(f"Executing category pipeline: {category} -> {actual_pipeline_id}")
            
            # Execute
            result = await pipeline.run(
                inputs=inputs,
                configuration=configuration
            )
            
            duration = time.time() - start_time
            
            return PipelineExecutionResponse(
                success=True,
                data=result.get("data"),
                metadata={
                    **(result.get("metadata", {})),
                    **(metadata or {}),
                    "category": category
                },
                pipeline_id=actual_pipeline_id,
                duration_seconds=duration
            )
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Category pipeline execution failed: {category} - {str(e)}", exc_info=True)
            
            return PipelineExecutionResponse(
                success=False,
                error=str(e),
                pipeline_id=category,
                duration_seconds=duration
            )
    
    def list_pipelines(
        self,
        category: Optional[str] = None,
        active_only: bool = True
    ) -> Dict[str, Any]:
        """
        List available pipelines
        
        Args:
            category: Optional category filter
            active_only: Only return active pipelines
            
        Returns:
            Dictionary with pipeline list
        """
        pipelines = self.registry.list_pipelines(category=category, active_only=active_only)
        
        return {
            "pipelines": pipelines,
            "count": len(pipelines),
            "category": category
        }
    
    def list_categories(self) -> Dict[str, Any]:
        """
        List pipeline categories
        
        Returns:
            Dictionary with category list
        """
        categories = self.registry.list_categories()
        
        return {
            "categories": categories,
            "count": len(categories)
        }
    
    def get_pipeline_info(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        """
        Get pipeline information
        
        Args:
            pipeline_id: Pipeline ID
            
        Returns:
            Pipeline info or None
        """
        config = self.registry._pipelines.get(pipeline_id)
        if not config:
            return None
        
        return {
            "pipeline_id": config.pipeline_id,
            "name": config.name,
            "description": config.description,
            "category": config.category,
            "version": config.version,
            "is_active": config.is_active,
            "metadata": config.metadata,
            "created_at": config.created_at.isoformat() if config.created_at else None,
            "updated_at": config.updated_at.isoformat() if config.updated_at else None
        }
    
    async def get_pipeline_health(self, pipeline_id: str) -> Dict[str, Any]:
        """
        Check pipeline health
        
        Args:
            pipeline_id: Pipeline ID
            
        Returns:
            Health check result
        """
        pipeline = self.registry.get_pipeline(pipeline_id)
        if not pipeline:
            return {
                "pipeline_id": pipeline_id,
                "healthy": False,
                "error": "Pipeline not found"
            }
        
        # Check if pipeline is initialized
        is_initialized = hasattr(pipeline, '_initialized') and pipeline._initialized
        
        return {
            "pipeline_id": pipeline_id,
            "healthy": True,
            "initialized": is_initialized,
            "name": pipeline.name if hasattr(pipeline, 'name') else None,
            "version": pipeline.version if hasattr(pipeline, 'version') else None
        }


# Global service instance
_global_pipeline_service = None


def get_pipeline_service() -> PipelineService:
    """Get global pipeline service instance"""
    global _global_pipeline_service
    if _global_pipeline_service is None:
        _global_pipeline_service = PipelineService()
    return _global_pipeline_service

from typing import Dict, Any, Optional, TypeVar, Generic
from cachetools import TTLCache
import uuid
import logging
import json
from datetime import datetime
from pydantic import BaseModel

from app.agents.pipelines.base import Pipeline
from app.core.session_manager import SessionManager
from app.core.provider import DocumentStoreProvider
from app.core.dependencies import get_doc_store_provider

logger = logging.getLogger("lexy-ai-service")

T = TypeVar('T', bound=BaseModel)
R = TypeVar('R', bound=BaseModel)

class BaseService(Generic[T, R]):
    """Base service class that handles pipeline creation, request caching, and async service calls."""
    
    def __init__(
        self,
        pipelines: Dict[str, Pipeline],
        maxsize: int = 1_000_000,
        ttl: int = 120,
    ):
        """Initialize the base service.
        
        Args:
            pipelines: Dictionary of pipeline instances
            maxsize: Maximum size of the cache
            ttl: Time to live for cache entries in seconds
        """
        self._pipelines = pipelines
        self._results_cache: Dict[str, Any] = TTLCache(maxsize=maxsize, ttl=ttl)
        self._session_manager: Optional[SessionManager] = None
        self._doc_store_provider: Optional[DocumentStoreProvider] = get_doc_store_provider()

    @property
    def session_manager(self) -> Optional[SessionManager]:
        """Get the session manager instance."""
        return self._session_manager

    @session_manager.setter
    def session_manager(self, value: Optional[SessionManager]) -> None:
        """Set the session manager instance."""
        self._session_manager = value

    @property
    def doc_store_provider(self) -> Optional[DocumentStoreProvider]:
        """Get the document store provider instance."""
        return self._doc_store_provider

    @doc_store_provider.setter
    def doc_store_provider(self, value: Optional[DocumentStoreProvider]) -> None:
        """Set the document store provider instance."""
        self._doc_store_provider = value

    def _serialize_for_cache(self, obj: Any) -> Any:
        """Serialize an object for caching.
        
        Args:
            obj: Object to serialize
            
        Returns:
            Serializable object
        """
        if isinstance(obj, BaseModel):
            return obj.dict()
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: self._serialize_for_cache(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._serialize_for_cache(item) for item in obj]
        return obj
        
    def _generate_event_id(self) -> str:
        """Generate a unique event ID."""
        return str(uuid.uuid4())
        
    def _cache_request(self, event_id: str, request: T) -> None:
        """Cache the request with the given event ID.
        
        Args:
            event_id: Unique identifier for the request
            request: Request object to cache
        """
        self._results_cache[event_id] = {
            "request": self._serialize_for_cache(request),
            "status": "processing",
            "result": None
        }
        
    def _get_cached_request(self, event_id: str) -> Optional[T]:
        """Get a cached request by event ID.
        
        Args:
            event_id: Unique identifier for the request
            
        Returns:
            Cached request object if found, None otherwise
        """
        if cached := self._results_cache.get(event_id):
            return cached.get("request")
        return None
        
    def _update_cache_status(self, event_id: str, status: str, result: Optional[Any] = None) -> None:
        """Update the status and result of a cached request.
        
        Args:
            event_id: Unique identifier for the request
            status: New status to set
            result: Optional result to cache
        """
        if event_id in self._results_cache:
            self._results_cache[event_id].update({
                "status": status,
                "result": self._serialize_for_cache(result) if result is not None else None
            })
            
    def _is_stopped(self, event_id: str) -> bool:
        """Check if a request has been stopped.
        
        Args:
            event_id: Unique identifier for the request
            
        Returns:
            True if the request has been stopped, False otherwise
        """
        if cached := self._results_cache.get(event_id):
            return cached.get("status") == "stopped"
        return False
        
    async def _execute_pipeline(
        self,
        pipeline_name: str,
        **kwargs
    ) -> Any:
        """Execute a pipeline with the given parameters.
        
        Args:
            pipeline_name: Name of the pipeline to execute
            **kwargs: Additional parameters to pass to the pipeline
            
        Returns:
            Result from the pipeline execution
        """
        if pipeline := self._pipelines.get(pipeline_name):
            return await pipeline.run(**kwargs)
        raise ValueError(f"Pipeline {pipeline_name} not found")
        
    async def process_request(self, request: T) -> R:
        """Process a request asynchronously.
        
        Args:
            request: Request object to process
            
        Returns:
            Response object
        """
        event_id = self._generate_event_id()
        self._cache_request(event_id, request)
        
        try:
            # Execute the request processing logic
            result = await self._process_request_impl(request)
            
            # Update cache with success
            self._update_cache_status(event_id, "finished", result)
            
            # Create and return response
            return self._create_response(event_id, result)
            
        except Exception as e:
            logger.exception(f"Error processing request: {e}")
            self._update_cache_status(event_id, "failed", str(e))
            raise
            
    async def _process_request_impl(self, request: T) -> Any:
        """Implementation of request processing logic.
        To be overridden by subclasses.
        
        Args:
            request: Request object to process
            
        Returns:
            Processing result
        """
        raise NotImplementedError("Subclasses must implement _process_request_impl")
        
    def _create_response(self, event_id: str, result: Any) -> R:
        """Create a response object from the processing result.
        To be overridden by subclasses.
        
        Args:
            event_id: Unique identifier for the request
            result: Processing result
            
        Returns:
            Response object
        """
        raise NotImplementedError("Subclasses must implement _create_response")
        
    def stop_request(self, event_id: str) -> None:
        """Stop processing of a request.
        
        Args:
            event_id: Unique identifier for the request
        """
        self._update_cache_status(event_id, "stopped")
        
    def get_request_status(self, event_id: str) -> Dict[str, Any]:
        """Get the status of a request.
        
        Args:
            event_id: Unique identifier for the request
            
        Returns:
            Dictionary containing request status and result
        """
        cached_data = self._results_cache.get(event_id, {})
        if isinstance(cached_data, dict):
            return cached_data
        return {"status": "unknown", "result": None} 
"""
Base service class for Knowledge App services
Follows the pipeline architecture pattern from agents/docs/pipeline.md
"""
import logging
from typing import Dict, Any, Optional, TypeVar, Generic, List
from cachetools import TTLCache
import asyncio
from pydantic import BaseModel
from abc import ABC, abstractmethod

from app.models.base import ServiceRequest, ServiceResponse

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)
R = TypeVar('R', bound=BaseModel)


class BaseService(Generic[T, R], ABC):
    """
    Base service class that handles async service calls, caching, and request management.
    Follows the pattern from agents/app/services/servicebase.py
    """
    
    def __init__(
        self,
        maxsize: int = 1_000_000,
        ttl: int = 120,
    ):
        """Initialize the base service.
        
        Args:
            maxsize: Maximum size of the cache
            ttl: Time to live for cache entries in seconds
        """
        self._results_cache: Dict[str, Any] = TTLCache(maxsize=maxsize, ttl=ttl)
        self._active_requests: Dict[str, asyncio.Task] = {}
    
    def _generate_request_id(self) -> str:
        """Generate a unique request ID"""
        return str(uuid.uuid4())
    
    def _get_cache_key(self, request: T) -> str:
        """Generate cache key from request"""
        return getattr(request, 'request_id', None) or self._generate_request_id()
    
    async def process_request(self, request: T) -> R:
        """
        Process a request asynchronously.
        
        Args:
            request: Service request
            
        Returns:
            Service response
        """
        request_id = getattr(request, 'request_id', None) or self._generate_request_id()
        
        # Check cache
        cache_key = self._get_cache_key(request)
        cached_result = self._results_cache.get(cache_key)
        if cached_result:
            logger.debug(f"Cache hit for request {request_id}")
            return cached_result
        
        # Process request
        try:
            result = await self._process_request_impl(request)
            
            # Cache result
            self._results_cache[cache_key] = result
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing request {request_id}: {str(e)}", exc_info=True)
            return self._create_error_response(request_id, str(e))
    
    @abstractmethod
    async def _process_request_impl(self, request: T) -> R:
        """
        Implementation of request processing.
        Subclasses must implement this method.
        
        Args:
            request: Service request
            
        Returns:
            Service response
        """
        pass
    
    def _create_error_response(self, request_id: str, error: str) -> R:
        """Create an error response"""
        return ServiceResponse(
            success=False,
            error=error,
            request_id=request_id
        )
    
    def _create_success_response(
        self,
        data: Dict[str, Any],
        request_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> R:
        """Create a success response"""
        return ServiceResponse(
            success=True,
            data=data,
            metadata=metadata,
            request_id=request_id
        )
    
    async def process_request_async(self, request: T) -> str:
        """
        Process a request asynchronously and return request ID.
        The result can be retrieved later using get_request_status.
        
        Args:
            request: Service request
            
        Returns:
            Request ID for tracking
        """
        request_id = getattr(request, 'request_id', None) or self._generate_request_id()
        
        # Create task
        task = asyncio.create_task(self._process_async_impl(request, request_id))
        self._active_requests[request_id] = task
        
        # Store initial status
        self._results_cache[request_id] = {
            "status": "processing",
            "request_id": request_id
        }
        
        return request_id
    
    async def _process_async_impl(self, request: T, request_id: str):
        """Process request asynchronously"""
        try:
            result = await self._process_request_impl(request)
            
            # Update cache with result
            self._results_cache[request_id] = {
                "status": "completed",
                "result": result.dict() if hasattr(result, 'dict') else result,
                "request_id": request_id
            }
            
        except Exception as e:
            logger.error(f"Error in async processing {request_id}: {str(e)}", exc_info=True)
            self._results_cache[request_id] = {
                "status": "error",
                "error": str(e),
                "request_id": request_id
            }
        finally:
            # Clean up active request
            if request_id in self._active_requests:
                del self._active_requests[request_id]
    
    def get_request_status(self, request_id: str) -> Dict[str, Any]:
        """Get the status of an async request"""
        cached_data = self._results_cache.get(request_id, {})
        if isinstance(cached_data, dict):
            return cached_data
        return {"status": "unknown", "request_id": request_id}
    
    async def cancel_request(self, request_id: str) -> bool:
        """Cancel an active request"""
        if request_id in self._active_requests:
            task = self._active_requests[request_id]
            task.cancel()
            del self._active_requests[request_id]
            
            self._results_cache[request_id] = {
                "status": "cancelled",
                "request_id": request_id
            }
            return True
        return False


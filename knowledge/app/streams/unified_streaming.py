"""
Unified Streaming Service

Provides SSE streaming for graphs, pipelines, and services.
Common architecture for all streaming operations.
"""
import asyncio
import json
import time
import logging
from typing import AsyncGenerator, Dict, Any, Optional, Union
from datetime import datetime

from app.streams.events import format_sse_event, KeepAliveEvent

logger = logging.getLogger(__name__)


class UnifiedStreamingService:
    """
    Unified service for streaming execution of graphs, pipelines, and services
    
    Provides:
    - SSE event formatting
    - Keep-alive management
    - Error handling
    - Stream lifecycle management
    """
    
    def __init__(
        self,
        keepalive_interval: float = 15.0,
        timeout: float = 300.0
    ):
        """
        Initialize unified streaming service
        
        Args:
            keepalive_interval: Interval for keep-alive events (seconds)
            timeout: Maximum stream duration (seconds)
        """
        self.keepalive_interval = keepalive_interval
        self.timeout = timeout
        self._active_streams: Dict[str, asyncio.Task] = {}
    
    async def stream_with_keepalive(
        self,
        generator: AsyncGenerator[Dict[str, Any], None],
        stream_id: str
    ) -> AsyncGenerator[str, None]:
        """
        Wrap a generator with keep-alive and SSE formatting
        
        Args:
            generator: Source event generator
            stream_id: Unique stream identifier
            
        Yields:
            SSE-formatted event strings
        """
        last_event_time = time.time()
        stream_start = time.time()
        event_count = 0
        
        try:
            logger.info(f"Starting stream: {stream_id}")
            
            async for event in generator:
                current_time = time.time()
                
                # Check timeout
                if current_time - stream_start > self.timeout:
                    logger.warning(f"Stream timeout: {stream_id}")
                    yield format_sse_event({
                        "event": "stream_timeout",
                        "stream_id": stream_id,
                        "duration": current_time - stream_start,
                        "events_sent": event_count
                    })
                    break
                
                # Send event
                yield format_sse_event(event)
                event_count += 1
                last_event_time = current_time
                
                # Send keep-alive if needed
                if current_time - last_event_time > self.keepalive_interval:
                    yield format_sse_event(KeepAliveEvent(
                        timestamp=current_time,
                        stream_id=stream_id
                    ))
                    last_event_time = current_time
            
            logger.info(f"Stream completed: {stream_id}, events={event_count}, duration={time.time() - stream_start:.2f}s")
            
        except asyncio.CancelledError:
            logger.info(f"Stream cancelled: {stream_id}")
            yield format_sse_event({
                "event": "stream_cancelled",
                "stream_id": stream_id,
                "events_sent": event_count,
                "duration": time.time() - stream_start
            })
            
        except Exception as e:
            logger.error(f"Stream error: {stream_id} - {str(e)}", exc_info=True)
            yield format_sse_event({
                "event": "stream_error",
                "stream_id": stream_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "events_sent": event_count,
                "duration": time.time() - stream_start
            })
        
        finally:
            # Cleanup
            if stream_id in self._active_streams:
                del self._active_streams[stream_id]
    
    async def stream_pipeline_execution(
        self,
        pipeline_service: Any,
        pipeline_id: str,
        inputs: Dict[str, Any],
        configuration: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        stream_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream pipeline execution
        
        Args:
            pipeline_service: PipelineService instance
            pipeline_id: Pipeline ID
            inputs: Pipeline inputs
            configuration: Pipeline configuration
            metadata: Request metadata
            stream_id: Optional stream ID
            
        Yields:
            SSE-formatted events
        """
        stream_id = stream_id or f"pipeline_{pipeline_id}_{int(time.time())}"
        
        async def event_generator():
            """Generate events from pipeline execution"""
            async for event in pipeline_service.stream_pipeline_execution(
                pipeline_id=pipeline_id,
                inputs=inputs,
                configuration=configuration,
                metadata=metadata
            ):
                yield event
        
        async for sse_event in self.stream_with_keepalive(event_generator(), stream_id):
            yield sse_event
    
    async def stream_graph_execution(
        self,
        graph_streaming_service: Any,
        assistant_id: str,
        graph_id: Optional[str],
        input_data: Dict[str, Any],
        session_id: str,
        config: Optional[Dict[str, Any]] = None,
        stream_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream graph execution
        
        Args:
            graph_streaming_service: GraphStreamingService instance
            assistant_id: Assistant ID
            graph_id: Graph ID
            input_data: Input data
            session_id: Session ID
            config: Graph configuration
            stream_id: Optional stream ID
            
        Yields:
            SSE-formatted events
        """
        stream_id = stream_id or f"graph_{assistant_id}_{session_id}_{int(time.time())}"
        
        # Graph streaming service already formats SSE, just wrap with keep-alive
        async for sse_event in graph_streaming_service.stream_graph_execution(
            assistant_id=assistant_id,
            graph_id=graph_id,
            input_data=input_data,
            session_id=session_id,
            config=config
        ):
            yield sse_event
    
    async def stream_service_execution(
        self,
        service: Any,
        method_name: str,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Stream any service method that returns AsyncGenerator
        
        Args:
            service: Service instance
            method_name: Method name to call
            **kwargs: Method arguments
            
        Yields:
            SSE-formatted events
        """
        stream_id = f"service_{service.__class__.__name__}_{method_name}_{int(time.time())}"
        
        try:
            method = getattr(service, method_name)
            if not callable(method):
                yield format_sse_event({
                    "event": "error",
                    "error": f"Method not callable: {method_name}",
                    "error_type": "InvalidMethodError"
                })
                return
            
            # Call method
            result = method(**kwargs)
            
            # Check if it's an async generator
            if hasattr(result, '__aiter__'):
                async for sse_event in self.stream_with_keepalive(result, stream_id):
                    yield sse_event
            else:
                yield format_sse_event({
                    "event": "error",
                    "error": f"Method does not return async generator: {method_name}",
                    "error_type": "InvalidReturnTypeError"
                })
                
        except Exception as e:
            logger.error(f"Service streaming error: {method_name} - {str(e)}", exc_info=True)
            yield format_sse_event({
                "event": "stream_error",
                "error": str(e),
                "error_type": type(e).__name__,
                "method": method_name
            })
    
    def register_stream(self, stream_id: str, task: asyncio.Task):
        """Register an active stream"""
        self._active_streams[stream_id] = task
    
    async def cancel_stream(self, stream_id: str) -> bool:
        """Cancel an active stream"""
        if stream_id in self._active_streams:
            task = self._active_streams[stream_id]
            task.cancel()
            del self._active_streams[stream_id]
            return True
        return False
    
    def get_active_streams(self) -> Dict[str, Any]:
        """Get information about active streams"""
        return {
            stream_id: {
                "stream_id": stream_id,
                "done": task.done(),
                "cancelled": task.cancelled()
            }
            for stream_id, task in self._active_streams.items()
        }


# Global instance
_global_streaming_service = None


def get_streaming_service() -> UnifiedStreamingService:
    """Get global streaming service instance"""
    global _global_streaming_service
    if _global_streaming_service is None:
        _global_streaming_service = UnifiedStreamingService()
    return _global_streaming_service

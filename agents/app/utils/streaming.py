import asyncio
from typing import Callable, Dict, Any, List, Optional
import json

class StreamingManager:
    """
    Shared streaming manager for all services. Manages a queue for each request and supports callbacks.
    """
    def __init__(self):
        # Each request_id maps to a dict with 'queue' and 'callbacks'
        self._streams: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def register(self, request_id: str, callback: Optional[Callable[[Any], None]] = None):
        print(f"[DEBUG][StreamingManager.register] request_id={request_id}")
        async with self._lock:
            if request_id not in self._streams:
                self._streams[request_id] = {
                    'queue': asyncio.Queue(),
                    'callbacks': []
                }
            if callback:
                self._streams[request_id]['callbacks'].append(callback)

    async def unregister(self, request_id: str, callback: Optional[Callable[[Any], None]] = None):
        print(f"[DEBUG][StreamingManager.unregister] request_id={request_id}")
        async with self._lock:
            if request_id in self._streams:
                if callback and callback in self._streams[request_id]['callbacks']:
                    self._streams[request_id]['callbacks'].remove(callback)
                if not self._streams[request_id]['callbacks']:
                    # No more listeners, clean up
                    del self._streams[request_id]

    async def put(self, request_id: str, message: Any):
        print(f"[DEBUG][StreamingManager.put] request_id={request_id}, message={message}")
        async with self._lock:
            if request_id in self._streams:
                await self._streams[request_id]['queue'].put(message)
                for cb in self._streams[request_id]['callbacks']:
                    # Callbacks can be async or sync
                    if asyncio.iscoroutinefunction(cb):
                        asyncio.create_task(cb(message))
                    else:
                        cb(message)
            else:
                print(f"[DEBUG][StreamingManager.put] request_id={request_id} not found in streams!")

    async def get(self, request_id: str, timeout: Optional[float] = None) -> Any:
        print(f"[DEBUG][StreamingManager.get] request_id={request_id}, timeout={timeout}")
        async with self._lock:
            if request_id in self._streams:
                queue = self._streams[request_id]['queue']
            else:
                print(f"[DEBUG][StreamingManager.get] request_id={request_id} not found in streams!")
                raise KeyError(f"No stream for request_id {request_id}")
        if timeout:
            return await asyncio.wait_for(queue.get(), timeout)
        else:
            return await queue.get()

    async def close(self, request_id: str):
        print(f"[DEBUG][StreamingManager.close] request_id={request_id}")
        async with self._lock:
            if request_id in self._streams:
                del self._streams[request_id]
            else:
                print(f"[DEBUG][StreamingManager.close] request_id={request_id} not found in streams!")

# Create a singleton instance of StreamingManager
streaming_manager = StreamingManager() 


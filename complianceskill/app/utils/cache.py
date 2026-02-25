from abc import ABC, abstractmethod
from typing import Any, Optional, Dict
import time
from threading import Lock

class Cache(ABC):
    """Abstract base class for cache implementations"""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache"""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a value in the cache with optional TTL in seconds"""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a value from the cache"""
        pass
    
    @abstractmethod
    async def clear(self) -> None:
        """Clear all values from the cache"""
        pass

class InMemoryCache(Cache):
    """In-memory cache implementation with TTL support"""
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache if it exists and hasn't expired"""
        with self._lock:
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            if entry.get("ttl") and time.time() > entry["expires_at"]:
                del self._cache[key]
                return None
            
            return entry["value"]
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a value in the cache with optional TTL in seconds"""
        with self._lock:
            entry = {
                "value": value,
                "ttl": ttl,
                "expires_at": time.time() + ttl if ttl else None
            }
            self._cache[key] = entry
    
    async def delete(self, key: str) -> None:
        """Delete a value from the cache"""
        with self._lock:
            self._cache.pop(key, None)
    
    async def clear(self) -> None:
        """Clear all values from the cache"""
        with self._lock:
            self._cache.clear()
    
    def _cleanup_expired(self) -> None:
        """Remove expired entries from the cache"""
        current_time = time.time()
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.get("ttl") and current_time > entry["expires_at"]
            ]
            for key in expired_keys:
                del self._cache[key]


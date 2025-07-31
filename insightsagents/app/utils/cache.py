from abc import ABC, abstractmethod
from typing import Any, Optional, Dict
import time
from threading import Lock

# Optional: import redis only if needed
try:
    import redis
except ImportError:
    redis = None

_cache_provider_instance = None

def set_cache_provider(instance: 'AbstractCache'):
    global _cache_provider_instance
    _cache_provider_instance = instance

def get_cache_provider() -> 'AbstractCache':
    if _cache_provider_instance is None:
        raise RuntimeError("Cache provider not initialized. Call set_cache_provider() at startup.")
    return _cache_provider_instance

class AbstractCache(ABC):
    """Abstract base class for cache providers."""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ex: Optional[int] = None) -> None:
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        pass

    @abstractmethod
    def clear(self) -> None:
        pass

class InMemoryCacheProvider(AbstractCache):
    def __init__(self, settings: Optional[dict] = None):
        self._store = {}
        # settings can be used for future extensions

    def get(self, key: str) -> Optional[Any]:
        return self._store.get(key)

    def set(self, key: str, value: Any, ex: Optional[int] = None) -> None:
        self._store[key] = value
        # 'ex' (expiry) is ignored for in-memory cache

    def delete(self, key: str) -> None:
        if key in self._store:
            del self._store[key]

    def clear(self) -> None:
        self._store.clear()

class RedisCacheProvider(AbstractCache):
    def __init__(self, settings: dict):
        if redis is None:
            raise ImportError("redis-py is not installed. Please install it to use RedisCacheProvider.")
        host = settings.get('host', 'localhost')
        port = settings.get('port', 6379)
        db = settings.get('db', 0)
        self._client = redis.StrictRedis(host=host, port=port, db=db, decode_responses=True)

    def get(self, key: str) -> Optional[Any]:
        return self._client.get(key)

    def set(self, key: str, value: Any, ex: Optional[int] = None) -> None:
        self._client.set(key, value, ex=ex)

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def clear(self) -> None:
        self._client.flushdb() 

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
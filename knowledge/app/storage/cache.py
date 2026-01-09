"""
Cache Abstraction
Supports in-memory (TTLCache) and Redis backends
"""
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional
from cachetools import TTLCache
import json

from app.core.settings import get_settings, CacheType

logger = logging.getLogger(__name__)


class CacheClient(ABC):
    """Abstract base class for cache clients"""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache"""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in cache"""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a value from cache"""
        pass
    
    @abstractmethod
    async def clear(self) -> bool:
        """Clear all cache"""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache"""
        pass


class MemoryCacheClient(CacheClient):
    """In-memory cache implementation using TTLCache"""
    
    def __init__(self, config: dict):
        """Initialize in-memory cache"""
        self.cache: TTLCache = TTLCache(
            maxsize=config.get("maxsize", 1_000_000),
            ttl=config.get("ttl", 120)
        )
        self._default_ttl = config.get("ttl", 120)
    
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache"""
        return self.cache.get(key)
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in cache"""
        try:
            self.cache[key] = value
            return True
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {str(e)}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete a value from cache"""
        try:
            if key in self.cache:
                del self.cache[key]
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {str(e)}")
            return False
    
    async def clear(self) -> bool:
        """Clear all cache"""
        try:
            self.cache.clear()
            return True
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache"""
        return key in self.cache


class RedisCacheClient(CacheClient):
    """Redis implementation of cache client"""
    
    def __init__(self, config: dict):
        """Initialize Redis client"""
        try:
            import redis.asyncio as redis
        except ImportError:
            raise ImportError("redis package is required for Redis cache. Install with: pip install redis")
        
        self.config = config
        self._client: Optional[redis.Redis] = None
        self._default_ttl = config.get("ttl", 120)
    
    async def _get_client(self):
        """Get or create Redis client"""
        if self._client is None:
            import redis.asyncio as redis
            
            self._client = redis.Redis(
                host=self.config.get("host", "localhost"),
                port=self.config.get("port", 6379),
                db=self.config.get("db", 0),
                password=self.config.get("password"),
                ssl=self.config.get("ssl", False),
                decode_responses=True
            )
        return self._client
    
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache"""
        try:
            client = await self._get_client()
            value = await client.get(key)
            if value is None:
                return None
            return json.loads(value)
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {str(e)}")
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in cache"""
        try:
            client = await self._get_client()
            ttl = ttl or self._default_ttl
            serialized = json.dumps(value)
            await client.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {str(e)}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete a value from cache"""
        try:
            client = await self._get_client()
            result = await client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {str(e)}")
            return False
    
    async def clear(self) -> bool:
        """Clear all cache"""
        try:
            client = await self._get_client()
            await client.flushdb()
            return True
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache"""
        try:
            client = await self._get_client()
            result = await client.exists(key)
            return result > 0
        except Exception as e:
            logger.error(f"Error checking cache key {key}: {str(e)}")
            return False
    
    async def close(self):
        """Close Redis connection"""
        if self._client:
            await self._client.close()
            self._client = None


def get_cache_client(config: Optional[dict] = None) -> CacheClient:
    """
    Factory function to get a cache client based on settings
    
    Args:
        config: Optional configuration override
        
    Returns:
        CacheClient instance
    """
    settings = get_settings()
    config = config or settings.get_cache_config()
    
    cache_type = config.get("type", CacheType.MEMORY)
    
    if cache_type == CacheType.MEMORY:
        return MemoryCacheClient(config)
    elif cache_type == CacheType.REDIS:
        return RedisCacheClient(config)
    else:
        raise ValueError(f"Unsupported cache type: {cache_type}")


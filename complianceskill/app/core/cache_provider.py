"""
Cache Provider for Knowledge App
Provides caching functionality with support for multiple cache backends
Similar to genieml/agents/app/core/dependencies.py caching pattern
"""
from typing import Dict, Any, Optional, Callable
from enum import Enum
import logging
from functools import lru_cache, wraps
import hashlib
import json

from app.core.settings import get_settings, CacheType
from app.storage.cache import get_cache_client as _get_cache_client, CacheClient

logger = logging.getLogger(__name__)


class CacheProvider:
    """Provider for cache operations with multiple backends"""
    
    def __init__(self, cache_client: Optional[CacheClient] = None):
        """
        Initialize cache provider.
        
        Args:
            cache_client: Optional cache client instance. If None, will be created from settings.
        """
        self._cache_client: Optional[CacheClient] = None
        self._cache_client_provided = cache_client is not None
        
        if cache_client is not None:
            self._cache_client = cache_client
        else:
            # Will be lazily initialized
            pass
    
    @property
    async def cache_client(self) -> CacheClient:
        """Get or create cache client."""
        if self._cache_client is None:
            settings = get_settings()
            config = settings.get_cache_config()
            self._cache_client = _get_cache_client(config)
            logger.info(f"Initialized cache client: {settings.CACHE_TYPE}")
        
        return self._cache_client
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get a value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        client = await self.cache_client
        return await client.get(key)
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set a value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (optional)
            
        Returns:
            True if successful, False otherwise
        """
        client = await self.cache_client
        return await client.set(key, value, ttl=ttl)
    
    async def delete(self, key: str) -> bool:
        """
        Delete a value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if deleted, False otherwise
        """
        client = await self.cache_client
        return await client.delete(key)
    
    async def clear(self) -> bool:
        """
        Clear all cache.
        
        Returns:
            True if successful, False otherwise
        """
        client = await self.cache_client
        return await client.clear()
    
    async def exists(self, key: str) -> bool:
        """
        Check if a key exists in cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists, False otherwise
        """
        client = await self.cache_client
        return await client.exists(key)
    
    def _generate_cache_key(
        self,
        prefix: str,
        *args,
        **kwargs
    ) -> str:
        """
        Generate a cache key from function arguments.
        
        Args:
            prefix: Key prefix
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Cache key string
        """
        # Create a hash of the arguments
        key_data = {
            "args": args,
            "kwargs": kwargs
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        key_hash = hashlib.md5(key_str.encode()).hexdigest()
        return f"{prefix}:{key_hash}"
    
    def cached(
        self,
        ttl: Optional[int] = None,
        key_prefix: Optional[str] = None
    ):
        """
        Decorator to cache function results.
        
        Args:
            ttl: Time to live in seconds (optional)
            key_prefix: Optional prefix for cache keys
            
        Returns:
            Decorated function
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Generate cache key
                prefix = key_prefix or f"{func.__module__}.{func.__name__}"
                cache_key = self._generate_cache_key(prefix, *args, **kwargs)
                
                # Try to get from cache
                cached_value = await self.get(cache_key)
                if cached_value is not None:
                    logger.debug(f"Cache hit for key: {cache_key}")
                    return cached_value
                
                # Cache miss - execute function
                logger.debug(f"Cache miss for key: {cache_key}")
                result = await func(*args, **kwargs)
                
                # Store in cache
                await self.set(cache_key, result, ttl=ttl)
                
                return result
            
            return wrapper
        return decorator


# Global cache provider instance
_cache_provider: Optional[CacheProvider] = None


def get_cache_provider(cache_client: Optional[CacheClient] = None) -> CacheProvider:
    """
    Get or create global cache provider instance.
    
    Args:
        cache_client: Optional cache client instance
        
    Returns:
        CacheProvider instance
    """
    global _cache_provider
    
    if _cache_provider is None:
        _cache_provider = CacheProvider(cache_client=cache_client)
        logger.info("Created new CacheProvider instance")
    elif cache_client is not None and not _cache_provider._cache_client_provided:
        # Update with provided client
        _cache_provider._cache_client = cache_client
        _cache_provider._cache_client_provided = True
    
    return _cache_provider


def clear_cache_provider():
    """Clear the global cache provider instance."""
    global _cache_provider
    _cache_provider = None
    logger.info("Cleared cache provider instance")


# Convenience functions for common cache operations
async def cache_get(key: str) -> Optional[Any]:
    """Get a value from cache."""
    provider = get_cache_provider()
    return await provider.get(key)


async def cache_set(
    key: str,
    value: Any,
    ttl: Optional[int] = None
) -> bool:
    """Set a value in cache."""
    provider = get_cache_provider()
    return await provider.set(key, value, ttl=ttl)


async def cache_delete(key: str) -> bool:
    """Delete a value from cache."""
    provider = get_cache_provider()
    return await provider.delete(key)


async def cache_clear() -> bool:
    """Clear all cache."""
    provider = get_cache_provider()
    return await provider.clear()


def cached_function(
    ttl: Optional[int] = None,
    key_prefix: Optional[str] = None
):
    """
    Decorator to cache async function results.
    
    Usage:
        @cached_function(ttl=300, key_prefix="my_function")
        async def my_function(arg1, arg2):
            # ... function implementation
            return result
    """
    provider = get_cache_provider()
    return provider.cached(ttl=ttl, key_prefix=key_prefix)


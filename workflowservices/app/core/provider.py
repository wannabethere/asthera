from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from app.storage.documents import DocumentChromaStore
from langchain_openai import OpenAIEmbeddings
from app.utils.cache import AbstractCache as Cache, InMemoryCacheProvider, RedisCacheProvider
from app.core.settings import get_settings

settings = get_settings()

@dataclass
class DocumentStoreProvider:
    """Provider for managing multiple document stores"""
    
    stores: Dict[str, DocumentChromaStore]
    default_store: str = "default"
    _store_metrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize store metrics after creation"""
        for store_name in self.stores:
            self._store_metrics[store_name] = {
                "total_documents": 0,
                "last_updated": None,
                "query_count": 0,
                "embedding_count": 0
            }
    
    def get_store(self, store_name: Optional[str] = None) -> DocumentChromaStore:
        """
        Get a specific document store by name
        
        Args:
            store_name: Name of the store to retrieve. If None, returns default store
            
        Returns:
            DocumentChromaStore instance
            
        Raises:
            KeyError: If store_name is not found
        """
        store_name = store_name or self.default_store
        if store_name not in self.stores:
            raise KeyError(f"Document store '{store_name}' not found")
        return self.stores[store_name]
    
    def add_store(self, name: str, store: DocumentChromaStore) -> None:
        """
        Add a new document store
        
        Args:
            name: Name for the new store
            store: DocumentChromaStore instance
        """
        self.stores[name] = store
        self._store_metrics[name] = {
            "total_documents": 0,
            "last_updated": None,
            "query_count": 0,
            "embedding_count": 0
        }
    
    def remove_store(self, name: str) -> None:
        """
        Remove a document store
        
        Args:
            name: Name of the store to remove
            
        Raises:
            KeyError: If store_name is not found
        """
        if name not in self.stores:
            raise KeyError(f"Document store '{name}' not found")
        del self.stores[name]
        del self._store_metrics[name]
    
    def list_stores(self) -> List[str]:
        """Get list of all available store names"""
        return list(self.stores.keys())
    
    def update_metrics(self, store_name: str, operation: str, count: int = 1) -> None:
        """
        Update metrics for a specific store
        
        Args:
            store_name: Name of the store to update
            operation: Type of operation ('query', 'embedding', 'document')
            count: Number to increment the metric by
        """
        if store_name not in self._store_metrics:
            return
            
        metrics = self._store_metrics[store_name]
        if operation == "query":
            metrics["query_count"] += count
        elif operation == "embedding":
            metrics["embedding_count"] += count
        elif operation == "document":
            metrics["total_documents"] += count
            metrics["last_updated"] = None  # Will be set by the store
    
    def get_metrics(self, store_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get metrics for a specific store or all stores
        
        Args:
            store_name: Name of the store to get metrics for. If None, returns all metrics
            
        Returns:
            Dictionary containing store metrics
        """
        if store_name:
            return self._store_metrics.get(store_name, {})
        return self._store_metrics
    
    def reset_metrics(self, store_name: Optional[str] = None) -> None:
        """
        Reset metrics for a specific store or all stores
        
        Args:
            store_name: Name of the store to reset metrics for. If None, resets all metrics
        """
        if store_name:
            if store_name in self._store_metrics:
                self._store_metrics[store_name] = {
                    "total_documents": 0,
                    "last_updated": None,
                    "query_count": 0,
                    "embedding_count": 0
                }
        else:
            for name in self._store_metrics:
                self._store_metrics[name] = {
                    "total_documents": 0,
                    "last_updated": None,
                    "query_count": 0,
                    "embedding_count": 0
                }
    
    def get_store_info(self, store_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get detailed information about a specific store or all stores
        
        Args:
            store_name: Name of the store to get info for. If None, returns info for all stores
            
        Returns:
            Dictionary containing store information
        """
        if store_name:
            if store_name not in self.stores:
                return {}
            store = self.stores[store_name]
            return {
                "name": store_name,
                "collection_name": store.collection_name,
                "metrics": self._store_metrics[store_name],
                "is_persistent": store.is_persistent
            }
        
        return {
            name: {
                "name": name,
                "collection_name": store.collection_name,
                "metrics": self._store_metrics[name],
                "is_persistent": store.is_persistent
            }
            for name, store in self.stores.items()
        }

class EmbedderProvider:
    """Provider for managing embedding models (currently only OpenAIEmbeddings)"""
    def __init__(self, model: str = "text-embedding-3-small", openai_api_key: str = None):
        self.model = model
        self.openai_api_key = openai_api_key
        self._embedder = OpenAIEmbeddings(model=self.model, openai_api_key=self.openai_api_key)

    def get_embedder(self):
        return self._embedder

# Convenience function for global usage
_embedder_provider = None

def get_embedder():
    global _embedder_provider
    if _embedder_provider is None:
        # You may want to fetch the API key from settings here
        _embedder_provider = EmbedderProvider(settings.OPENAI_API_KEY)
    return _embedder_provider.get_embedder()

class CacheProvider:
    """Provider for managing cache instances"""
    
    def __init__(self, cache_type: Optional[str] = None):
        self._caches: Dict[str, Cache] = {}
        self._default_cache = "default"
        self._cache_type = cache_type or self._get_default_cache_type()
        self._initialize_default_cache()
    
    def _get_default_cache_type(self) -> str:
        """Determine default cache type based on settings"""
        # Check if Redis is configured and available
        if hasattr(settings, 'REDIS_HOST') and settings.REDIS_HOST:
            try:
                # Try to import redis to check if it's available
                import redis
                return "redis"
            except ImportError:
                pass
        return "memory"
    
    def _initialize_default_cache(self) -> None:
        """Initialize the default cache based on configuration"""
        if self._cache_type == "redis":
            redis_config = {
                'host': getattr(settings, 'REDIS_HOST', 'localhost'),
                'port': getattr(settings, 'REDIS_PORT', 6379),
                'db': getattr(settings, 'REDIS_DB', 0)
            }
            self.add_cache(self._default_cache, RedisCacheProvider(redis_config))
        else:
            self.add_cache(self._default_cache, InMemoryCacheProvider())
    
    def get_cache(self, cache_name: Optional[str] = None) -> Cache:
        """
        Get a specific cache instance by name
        
        Args:
            cache_name: Name of the cache to retrieve. If None, returns default cache
            
        Returns:
            Cache instance
            
        Raises:
            KeyError: If cache_name is not found
        """
        cache_name = cache_name or self._default_cache
        if cache_name not in self._caches:
            raise KeyError(f"Cache '{cache_name}' not found")
        return self._caches[cache_name]
    
    def add_cache(self, name: str, cache: Cache) -> None:
        """
        Add a new cache instance
        
        Args:
            name: Name for the new cache
            cache: Cache instance
        """
        self._caches[name] = cache
    
    def add_redis_cache(self, name: str, redis_config: Dict[str, Any]) -> None:
        """
        Add a new Redis cache instance
        
        Args:
            name: Name for the new cache
            redis_config: Redis configuration dictionary
        """
        self.add_cache(name, RedisCacheProvider(redis_config))
    
    def add_memory_cache(self, name: str) -> None:
        """
        Add a new in-memory cache instance
        
        Args:
            name: Name for the new cache
        """
        self.add_cache(name, InMemoryCacheProvider())
    
    def remove_cache(self, name: str) -> None:
        """
        Remove a cache instance
        
        Args:
            name: Name of the cache to remove
            
        Raises:
            KeyError: If cache_name is not found
        """
        if name == self._default_cache:
            raise ValueError("Cannot remove default cache")
        if name not in self._caches:
            raise KeyError(f"Cache '{name}' not found")
        del self._caches[name]
    
    def list_caches(self) -> List[str]:
        """Get list of all available cache names"""
        return list(self._caches.keys())
    
    def get_cache_info(self, cache_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get information about a specific cache or all caches
        
        Args:
            cache_name: Name of the cache to get info for. If None, returns info for all caches
            
        Returns:
            Dictionary containing cache information
        """
        if cache_name:
            if cache_name not in self._caches:
                return {}
            cache = self._caches[cache_name]
            return {
                "name": cache_name,
                "type": type(cache).__name__,
                "is_default": cache_name == self._default_cache
            }
        
        return {
            name: {
                "name": name,
                "type": type(cache).__name__,
                "is_default": name == self._default_cache
            }
            for name, cache in self._caches.items()
        }

# Convenience function for global usage
_cache_provider = None

def get_cache_provider() -> CacheProvider:
    global _cache_provider
    if _cache_provider is None:
        _cache_provider = CacheProvider()
    return _cache_provider 
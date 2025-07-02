# PandasEngine Caching Functionality

## Overview

The PandasEngine now includes comprehensive caching functionality to improve performance for repeated SQL queries. This is particularly useful when multiple calls request the same dataset, as it eliminates redundant database operations.

## Features

- **Automatic Caching**: Query results are automatically cached with configurable TTL
- **Smart Cache Keys**: Unique cache keys based on SQL, parameters, and data source state
- **Cache Invalidation**: Automatic cache clearing when data sources change
- **Flexible Cache Providers**: Support for any cache implementation that follows the Cache interface
- **Batch Query Caching**: Support for caching batch query results
- **Cache Statistics**: Built-in cache monitoring capabilities

## Usage

### Basic Usage with Default Cache

```python
from pandas_engine import PandasEngine, PandasEngineConfig
import pandas as pd

# Create engine with default InMemoryCache
engine = PandasEngineConfig.from_dataframes({
    'users': pd.DataFrame({'id': [1, 2], 'name': ['Alice', 'Bob']})
})

# Execute query (will be cached automatically)
success, result = await engine.execute_sql("SELECT * FROM users", session)
```

### Custom Cache Configuration

```python
from app.utils.cache import InMemoryCache

# Create custom cache with specific TTL
custom_cache = InMemoryCache()
engine = PandasEngineConfig.from_dataframes(
    dataframes=dataframes,
    cache_provider=custom_cache,
    cache_ttl=1800  # 30 minutes
)
```

### Disable Caching for Specific Queries

```python
# Execute query without caching
success, result = await engine.execute_sql(
    "SELECT * FROM users", 
    session, 
    use_cache=False
)
```

### Batch Query Caching

```python
# Batch queries are also cached
success, result = await engine.execute_sql_in_batches(
    "SELECT * FROM large_table",
    session,
    batch_size=1000,
    use_cache=True  # Default is True
)
```

## Cache Key Generation

Cache keys are generated based on:
- SQL query string
- Limit parameter
- Engine type
- Data source information (table names and row counts)
- Additional keyword arguments
- Batch parameters (for batch queries)

This ensures that different queries with different parameters get separate cache entries.

## Cache Management

### Clear All Cache

```python
await engine.clear_cache()
```

### Invalidate Cache for Specific Table

```python
await engine.invalidate_cache_for_table('users')
```

### Get Cache Statistics

```python
stats = engine.get_cache_stats()
print(f"Cache type: {stats['cache_type']}")
print(f"Cache size: {stats['cache_size']}")
print(f"Cache TTL: {stats['cache_ttl']}")
```

## Automatic Cache Invalidation

The cache is automatically cleared when:
- New data sources are added via `add_data_source()`
- The engine is reconfigured

## Configuration Options

### PandasEngine Constructor Parameters

- `cache_provider`: Optional cache provider (defaults to InMemoryCache)
- `cache_ttl`: Cache TTL in seconds (default: 3600)

### PandasEngineConfig Methods

All configuration methods now support cache parameters:
- `from_dataframes()`
- `from_csv_files()`
- `from_excel_file()`
- `from_postgres()`
- `from_mixed_sources()`

## Performance Benefits

- **Reduced Database Load**: Repeated queries return cached results
- **Faster Response Times**: Cache hits are significantly faster than database queries
- **Scalability**: Reduces resource usage under high query load
- **Cost Savings**: Fewer database operations mean lower costs

## Cache Providers

The system supports any cache implementation that follows the Cache interface:

```python
class CustomCache(Cache):
    async def get(self, key: str) -> Optional[Any]:
        # Implementation
        pass
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        # Implementation
        pass
    
    async def delete(self, key: str) -> None:
        # Implementation
        pass
    
    async def clear(self) -> None:
        # Implementation
        pass
```

## Example Use Cases

1. **Dashboard Applications**: Cache frequently accessed dashboard data
2. **API Services**: Cache common API query results
3. **Batch Processing**: Cache intermediate results in data pipelines
4. **Development/Testing**: Speed up repeated queries during development

## Best Practices

1. **Set Appropriate TTL**: Balance freshness with performance
2. **Monitor Cache Size**: Large caches can consume significant memory
3. **Use Cache Statistics**: Monitor cache hit rates and performance
4. **Consider Data Freshness**: Clear cache when data is updated
5. **Test Cache Behavior**: Verify cache invalidation works as expected

## Troubleshooting

### Cache Not Working
- Check if `use_cache=True` (default)
- Verify cache provider is properly configured
- Check cache statistics for hit/miss rates

### Memory Issues
- Reduce cache TTL
- Use a different cache provider (e.g., Redis)
- Monitor cache size with `get_cache_stats()`

### Stale Data
- Clear cache manually with `clear_cache()`
- Reduce cache TTL
- Ensure data source changes trigger cache invalidation 
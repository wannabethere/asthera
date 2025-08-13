# Metadata Cache for SQL RAG Agent

## Overview

The SQL RAG Agent has been enhanced with a comprehensive metadata cache system that improves reasoning capabilities and eliminates duplicate API calls. This enhancement provides better context for SQL generation and reasoning by incorporating additional metadata sources.

## New Features

### 1. Enhanced Metadata Retrieval
The agent now retrieves and caches four types of metadata for each query:
- **SQL Pairs**: Similar questions and their corresponding SQL queries
- **Instructions**: Relevant instructions for SQL generation
- **Metrics**: Available metrics and their descriptions
- **Views**: Available database views and their descriptions

### 2. Intelligent Caching System
- **Automatic Caching**: Metadata is automatically cached after first retrieval
- **Cache Key Generation**: Uses MD5 hash of query + project_id for consistent caching
- **Cache Expiration**: Automatic cleanup of expired cache entries (default: 24 hours)
- **Memory Efficient**: Prevents memory leaks through automatic cleanup

### 3. Enhanced Reasoning
The reasoning plan generator now includes:
- Similar questions and SQL examples
- Relevant instructions for the specific query
- Available metrics and their descriptions
- Available views and their descriptions

## Implementation Details

### Cache Structure
```python
{
    "sql_pairs": [{"question": "...", "sql": "..."}],
    "instructions": ["instruction1", "instruction2"],
    "metrics": [{"name": "...", "description": "..."}],
    "views": [{"name": "...", "description": "..."}],
    "timestamp": "2024-01-01T00:00:00",
    "query": "original query",
    "project_id": "project_id"
}
```

### Key Methods

#### `_retrieve_and_cache_metadata(query, project_id, **kwargs)`
Retrieves all metadata types in parallel and caches the results.

#### `_format_metadata_for_reasoning(metadata)`
Formats metadata into a readable string for reasoning prompts.

#### `clear_metadata_cache()`
Clears all cached metadata.

#### `get_cache_stats()`
Returns cache statistics and current keys.

#### `add_metadata_to_cache(query, project_id, metadata)`
Manually adds metadata to the cache for testing or external use.

#### `get_cached_metadata(query, project_id)`
Retrieves cached metadata for a specific query and project.

## Usage Examples

### Basic Usage
```python
# The cache is automatically used when calling reasoning or SQL generation
agent = SQLRAGAgent(llm, engine, retrieval_helper)

# First call - retrieves and caches metadata
result1 = await agent.process(
    SQLOperationType.REASONING,
    "Show me sales data",
    project_id="my_project"
)

# Second call - uses cached metadata
result2 = await agent.process(
    SQLOperationType.REASONING,
    "Show me sales data",
    project_id="my_project"
)
```

### Manual Cache Management
```python
# Clear the cache
agent.clear_metadata_cache()

# Get cache statistics
stats = agent.get_cache_stats()
print(f"Cache size: {stats['cache_size']}")

# Manually add metadata
custom_metadata = {
    "sql_pairs": [{"question": "Custom", "sql": "SELECT 1"}],
    "instructions": ["Custom instruction"],
    "metrics": [{"name": "Custom", "description": "..."}],
    "views": [{"name": "custom_view", "description": "..."}]
}

agent.add_metadata_to_cache("Custom query", "project_id", custom_metadata)
```

## Benefits

### 1. Performance Improvement
- **Eliminates Duplicate Calls**: Metadata is retrieved once and reused
- **Parallel Retrieval**: All metadata types are fetched simultaneously
- **Reduced Latency**: Subsequent calls use cached data

### 2. Better Reasoning Quality
- **Richer Context**: Reasoning includes examples, instructions, metrics, and views
- **Consistent Information**: Same metadata used across reasoning and SQL generation
- **Enhanced Prompts**: More comprehensive prompts lead to better SQL generation

### 3. Resource Efficiency
- **Memory Management**: Automatic cleanup prevents memory leaks
- **Network Optimization**: Reduces API calls to external services
- **Scalable**: Cache grows with usage but maintains performance

## Configuration

### Cache Parameters
- **Default Expiration**: 24 hours
- **Similarity Threshold**: 0.3 (configurable)
- **Max Retrieval Size**: 3 (configurable)
- **Top K Instructions**: 3 (configurable)

### Customization
```python
# Custom cache expiration
agent._cleanup_expired_cache(max_age_hours=48)

# Custom metadata retrieval parameters
metadata = await agent._retrieve_and_cache_metadata(
    query="query",
    project_id="project",
    similarity_threshold=0.5,
    max_retrieval_size=5,
    top_k=5
)
```

## Integration Points

### 1. SQL Generation
The `_generate_sql_internal` method now uses cached metadata instead of making duplicate calls.

### 2. SQL Reasoning
The `_reason_sql_internal` method includes enhanced metadata in reasoning prompts.

### 3. SQL Expansion
The `_handle_sql_expansion` method combines metadata from both original and new queries.

### 4. SQL Correction
The `_handle_sql_correction` method uses cached metadata for better context.

## Testing

Run the test script to verify functionality:
```bash
python test_metadata_cache.py
```

The test script demonstrates:
- Metadata retrieval and caching
- Cache hit/miss scenarios
- Manual cache management
- Cache statistics and cleanup

## Migration Notes

### Existing Code Compatibility
- All existing functionality remains unchanged
- New metadata is automatically included in reasoning
- Cache is transparent to existing API consumers

### Performance Impact
- **First Call**: Slightly slower due to metadata retrieval
- **Subsequent Calls**: Faster due to cache usage
- **Overall**: Net performance improvement for repeated queries

## Future Enhancements

### Potential Improvements
1. **Persistent Cache**: Save cache to disk for persistence across restarts
2. **Cache Invalidation**: Smart invalidation based on data freshness
3. **Distributed Cache**: Share cache across multiple agent instances
4. **Cache Analytics**: Track cache hit rates and performance metrics
5. **Adaptive Caching**: Adjust cache parameters based on usage patterns

## Troubleshooting

### Common Issues
1. **Cache Not Working**: Check if project_id is consistent
2. **Memory Issues**: Verify cache cleanup is working
3. **Stale Data**: Check cache expiration settings

### Debug Information
```python
# Enable debug logging
import logging
logging.getLogger("lexy-ai-service").setLevel(logging.DEBUG)

# Check cache status
stats = agent.get_cache_stats()
print(f"Cache keys: {stats['cache_keys']}")
```

## Conclusion

The metadata cache system significantly improves the SQL RAG Agent's reasoning capabilities while maintaining performance and resource efficiency. The enhanced context leads to better SQL generation and reasoning, while the caching system eliminates redundant API calls and improves overall system performance. 
# Job Queue Storage Configuration

This document describes the configurable job queue storage system that supports both in-memory and Redis backends based on cache provider configuration.

## Overview

The job queue service has been refactored to use a configurable storage backend that automatically selects between in-memory and Redis storage based on the cache provider configuration. This provides flexibility for different deployment scenarios:

- **In-memory storage**: Lightweight, suitable for development and single-instance deployments
- **Redis storage**: Persistent, scalable, suitable for production and multi-instance deployments

## Architecture

### Storage Backends

The system implements an abstract `JobQueueStorage` interface with two concrete implementations:

1. **InMemoryJobQueueStorage**: Uses Python dictionaries and lists for storage
2. **RedisJobQueueStorage**: Uses Redis for persistent storage

### Configuration Detection

The job queue service automatically detects the appropriate storage backend by:

1. Checking the cache provider configuration
2. Looking for Redis cache instances
3. Falling back to in-memory storage if Redis is not available

## Usage

### Basic Usage

```python
from app.services.job_queue_service import JobQueueService, JobType, JobStatus
from app.core.provider import get_cache_provider

# The job queue service automatically selects the appropriate storage backend
job_queue = JobQueueService()

# Register job handlers
async def my_handler(job_data):
    # Process the job
    return {"result": "success"}

job_queue.register_handler(JobType.CHROMADB_INDEXING, my_handler)

# Submit jobs
job_id = await job_queue.submit_job(
    job_type=JobType.CHROMADB_INDEXING,
    project_id="project_123",
    user_id="user_456"
)

# Start the worker
await job_queue.start_worker()
```

### Cache Provider Configuration

The storage backend selection is based on the cache provider configuration:

```python
from app.core.provider import CacheProvider

# For in-memory storage (default if Redis not available)
cache_provider = CacheProvider(cache_type="memory")

# For Redis storage (requires Redis configuration)
cache_provider = CacheProvider(cache_type="redis")
```

### Environment Configuration

To use Redis storage, ensure the following environment variables are set:

```bash
# Redis configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your_password  # Optional
```

## Storage Backend Comparison

| Feature | In-Memory | Redis |
|---------|-----------|-------|
| **Persistence** | No | Yes |
| **Scalability** | Single instance | Multi-instance |
| **Performance** | Very fast | Fast |
| **Memory Usage** | Application memory | Redis memory |
| **Setup Complexity** | None | Redis server |
| **Dependencies** | None | redis-py |

## Implementation Details

### JobQueueStorage Interface

```python
class JobQueueStorage(ABC):
    @abstractmethod
    async def connect(self):
        pass
    
    @abstractmethod
    async def store_job(self, job_data: JobData) -> None:
        pass
    
    @abstractmethod
    async def get_job(self) -> Optional[JobData]:
        pass
    
    # ... other methods
```

### In-Memory Implementation

- Uses Python dictionaries for job data storage
- Uses sorted lists for priority queue management
- All data is lost on application restart
- Suitable for development and testing

### Redis Implementation

- Uses Redis hashes for job data storage
- Uses Redis sorted sets for priority queue management
- Data persists across application restarts
- Supports distributed job processing

## Testing

Run the test script to verify both storage backends:

```bash
cd unstructured/genieml/dataservices
python test_job_queue_storage.py
```

The test script will:
1. Test cache provider information
2. Test in-memory storage functionality
3. Test Redis storage functionality (if Redis is available)

## Migration from Previous Version

### For Existing Code

The public API of `JobQueueService` remains the same, so existing code should work without changes:

```python
# This code continues to work unchanged
job_queue = JobQueueService()
await job_queue.submit_job(...)
await job_queue.start_worker()
```

### For New Deployments

1. **Development**: No configuration needed, uses in-memory storage by default
2. **Production**: Set Redis environment variables to enable Redis storage

## Monitoring and Debugging

### Storage Backend Detection

Check which storage backend is being used:

```python
from app.core.provider import get_cache_provider

cache_provider = get_cache_provider()
cache_info = cache_provider.get_cache_info()
print(f"Cache types: {[info['type'] for info in cache_info.values()]}")
```

### Queue Statistics

Get queue statistics regardless of storage backend:

```python
stats = await job_queue.get_queue_stats()
print(f"Queue length: {stats['queue_length']}")
print(f"Status counts: {stats['status_counts']}")
print(f"Worker running: {stats['worker_running']}")
```

## Error Handling

### Graceful Fallback

If Redis is configured but unavailable, the system automatically falls back to in-memory storage:

```
WARNING: Failed to initialize Redis storage, falling back to in-memory: Connection refused
INFO: Initialized in-memory job queue storage as fallback
```

### Storage-Specific Errors

- **In-memory**: No external dependencies, minimal error scenarios
- **Redis**: Connection errors, authentication failures, etc.

## Performance Considerations

### In-Memory Storage

- **Pros**: Very fast, no network latency
- **Cons**: Memory usage grows with job count, data lost on restart

### Redis Storage

- **Pros**: Persistent, scalable, supports multiple workers
- **Cons**: Network latency, requires Redis server

### Recommendations

- **Development**: Use in-memory storage for simplicity
- **Testing**: Use in-memory storage for isolated tests
- **Production**: Use Redis storage for reliability and scalability

## Future Enhancements

### Planned Features

1. **Database Storage**: PostgreSQL-based job queue storage
2. **Hybrid Storage**: In-memory for active jobs, persistent for completed jobs
3. **Storage Migration**: Tools to migrate between storage backends
4. **Advanced Monitoring**: Storage-specific metrics and alerts

### Configuration Options

1. **Storage Selection**: Explicit storage backend selection
2. **Connection Pooling**: Configurable Redis connection pools
3. **Retry Policies**: Storage-specific retry mechanisms
4. **Cleanup Policies**: Configurable job cleanup strategies

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   - Check Redis server is running
   - Verify connection credentials
   - Check network connectivity

2. **Memory Usage High**
   - Consider switching to Redis storage
   - Implement job cleanup policies
   - Monitor job queue length

3. **Jobs Not Processing**
   - Check worker is started
   - Verify job handlers are registered
   - Check storage backend connectivity

### Debug Commands

```python
# Check storage backend
print(f"Storage type: {type(job_queue.storage).__name__}")

# Check cache provider
cache_info = get_cache_provider().get_cache_info()
print(f"Cache info: {cache_info}")

# Check queue stats
stats = await job_queue.get_queue_stats()
print(f"Queue stats: {stats}")
```

## Conclusion

The configurable job queue storage system provides flexibility for different deployment scenarios while maintaining a consistent API. The automatic backend selection ensures optimal performance and reliability based on the available infrastructure. 
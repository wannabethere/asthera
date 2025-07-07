# Async Job Queue System

## Overview

The Async Job Queue System provides a robust, scalable solution for processing project JSON schemas updates in the background. It uses Redis as the queue backend and supports priority-based job processing, retry mechanisms, and comprehensive monitoring.

## Architecture

### Components

1. **JobQueueService** - Core queue management using Redis
2. **EntityUpdateService** - Automatic job submission on entity updates
3. **JobHandlers** - Processing logic for different job types
4. **Job Queue Router** - REST API for queue management
5. **Redis Backend** - Persistent queue storage

### Job Types

The system supports the following job types:

- `PROJECT_JSON_TABLES` - Process table JSON schemas
- `PROJECT_JSON_METRICS` - Process metric JSON schemas
- `PROJECT_JSON_VIEWS` - Process view JSON schemas
- `PROJECT_JSON_CALCULATED_COLUMNS` - Process calculated column JSON schemas
- `PROJECT_JSON_SUMMARY` - Process project summary JSON
- `PROJECT_JSON_ALL` - Process all JSON types
- `CHROMADB_INDEXING` - Index project data into ChromaDB using MDL files
- `POST_COMMIT_WORKFLOW` - Execute post-commit workflows

## Features

### Priority Queue
- Jobs are processed based on priority (lower number = higher priority)
- Project commits have highest priority (0)
- Entity updates have medium priority (1)
- Summary updates have lower priority (2)

### Retry Mechanism
- Failed jobs are automatically retried up to 3 times
- Retry attempts get higher priority
- Exponential backoff between retries

### Job Status Tracking
- `PENDING` - Job is queued and waiting
- `RUNNING` - Job is currently being processed
- `COMPLETED` - Job completed successfully
- `FAILED` - Job failed after all retries
- `CANCELLED` - Job was cancelled
- `RETRY` - Job is being retried

### Monitoring and Statistics
- Real-time queue statistics
- Job status tracking
- Performance metrics
- Error reporting

## Usage

### Automatic Job Submission

The system automatically submits jobs when entities are updated:

```python
from app.services.entity_update_service import entity_update_service

# Table update
await entity_update_service.on_table_updated(
    project_id="project_123",
    table_id="table_456",
    user_id="user_789"
)

# Column update
await entity_update_service.on_column_updated(
    project_id="project_123",
    table_id="table_456",
    column_id="column_789",
    user_id="user_789"
)

# Metric update
await entity_update_service.on_metric_updated(
    project_id="project_123",
    metric_id="metric_456",
    user_id="user_789"
)

# Project commit
await entity_update_service.on_project_committed(
    project_id="project_123",
    user_id="user_789"
)
```

### Manual Job Submission

You can also submit jobs manually:

```python
from app.services.job_queue_service import job_queue_service, JobType

job_id = await job_queue_service.submit_job(
    job_type=JobType.PROJECT_JSON_TABLES,
    project_id="project_123",
    entity_type="table",
    entity_id="table_456",
    user_id="user_789",
    priority=1
)
```

### Job Monitoring

```python
# Get job status
job_data = await job_queue_service.get_job_status(job_id)

# Get queue statistics
stats = await job_queue_service.get_queue_stats()

# Cancel a job
success = await job_queue_service.cancel_job(job_id)

# Retry a failed job
success = await job_queue_service.retry_job(job_id)
```

## API Endpoints

### Job Management

- `POST /jobs/submit` - Submit a new job
- `GET /jobs/{job_id}` - Get job status
- `POST /jobs/{job_id}/cancel` - Cancel a job
- `POST /jobs/{job_id}/retry` - Retry a failed job
- `GET /jobs` - List jobs with filtering

### Queue Management

- `GET /queue/stats` - Get queue statistics
- `POST /queue/start` - Start the worker
- `POST /queue/stop` - Stop the worker
- `POST /queue/cleanup` - Clean up old jobs

### Entity Updates

- `POST /entity-updates/table` - Handle table update
- `POST /entity-updates/column` - Handle column update
- `POST /entity-updates/metric` - Handle metric update
- `POST /entity-updates/view` - Handle view update
- `POST /entity-updates/calculated-column` - Handle calculated column update
- `POST /entity-updates/project-commit` - Handle project commit
- `POST /chromadb-indexing/{project_id}` - Trigger ChromaDB indexing for a project

## Configuration

### Redis Configuration

The system uses Redis for queue storage. Configure in your environment:

```bash
REDIS_HOST=redis-service
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your_password
```

### Worker Configuration

```python
# Start the worker
await job_queue_service.start_worker()

# Stop the worker
await job_queue_service.stop_worker()
```

## Integration with Database Operations

### Automatic Triggers

The system integrates with database operations to automatically submit jobs:

1. **Table Updates** - Triggers tables and summary jobs
2. **Column Updates** - Triggers tables and summary jobs
3. **Metric Updates** - Triggers metrics and summary jobs
4. **View Updates** - Triggers views and summary jobs
5. **Calculated Column Updates** - Triggers calculated columns and summary jobs
6. **Project Commits** - Triggers post-commit workflow and ChromaDB indexing

### Bulk Operations

For bulk updates, use the bulk operation method:

```python
entity_updates = [
    {"entity_type": "table", "entity_id": "table_1"},
    {"entity_type": "metric", "entity_id": "metric_1"},
    {"entity_type": "view", "entity_id": "view_1"}
]

result = await entity_update_service.on_bulk_update(
    project_id="project_123",
    entity_updates=entity_updates,
    user_id="user_789"
)
```

## Error Handling

### Job Failures

- Jobs that fail are automatically retried up to 3 times
- Failed jobs are logged with detailed error information
- Manual retry is available for failed jobs

### Queue Failures

- Redis connection failures are handled gracefully
- Worker restarts automatically on connection loss
- Jobs are preserved during service restarts

### Monitoring

- All job operations are logged
- Error details are captured and stored
- Queue statistics provide real-time monitoring

## Performance Considerations

### Queue Performance

- Redis provides fast job enqueueing and dequeuing
- Priority queue ensures important jobs are processed first
- Worker processes jobs asynchronously

### Scalability

- Multiple workers can be run for horizontal scaling
- Jobs are distributed across workers automatically
- Redis clustering supports high availability

### Resource Management

- Jobs are cleaned up automatically after 7 days
- Memory usage is controlled through job limits
- Database connections are managed efficiently

## Testing

### Running Tests

```bash
cd genieml/dataservices/tests
python test_async_job_queue.py
```

### Test Coverage

The test suite covers:

1. **Basic Operations** - Job submission, status checking, cancellation
2. **Entity Updates** - All entity update scenarios
3. **Job Handlers** - Processing logic for each job type
4. **Worker Functionality** - Worker start/stop and job processing
5. **Bulk Operations** - Multiple job submissions
6. **Error Handling** - Failure scenarios and retry logic

## Monitoring and Alerting

### Queue Monitoring

- Queue length monitoring
- Job processing rate
- Error rate tracking
- Worker health checks

### Alerting

- Queue overflow alerts
- High error rate alerts
- Worker failure alerts
- Job timeout alerts

## Troubleshooting

### Common Issues

1. **Redis Connection Failures**
   - Check Redis service availability
   - Verify connection credentials
   - Check network connectivity

2. **Job Processing Failures**
   - Check job logs for error details
   - Verify project and entity existence
   - Check database connectivity

3. **Worker Not Processing Jobs**
   - Ensure worker is started
   - Check Redis connection
   - Verify job handlers are registered

### Debug Steps

1. Check application logs for error messages
2. Verify Redis connection and queue state
3. Check job status and error details
4. Validate entity existence in database
5. Test job handlers individually

## Future Enhancements

### Planned Features

1. **Job Scheduling** - Schedule jobs for future execution
2. **Job Dependencies** - Define job execution order
3. **Job Timeouts** - Automatic job cancellation on timeout
4. **Job Progress Tracking** - Real-time job progress updates
5. **Job Result Caching** - Cache job results for reuse

### Integration Opportunities

1. **Webhook Notifications** - Notify external systems on job completion
2. **Metrics Integration** - Export metrics to monitoring systems
3. **Dashboard Integration** - Real-time queue monitoring dashboard
4. **API Rate Limiting** - Prevent queue overload
5. **Job Templates** - Predefined job configurations

## Conclusion

The Async Job Queue System provides a robust, scalable solution for background processing of project JSON schemas updates. It ensures reliable job processing, comprehensive monitoring, and seamless integration with the existing database operations. 
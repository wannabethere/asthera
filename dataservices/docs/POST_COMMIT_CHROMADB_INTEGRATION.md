# Post-Commit ChromaDB Integration

## Overview

The Post-Commit ChromaDB Integration system has been updated to use asynchronous job processing for ChromaDB indexing. The system now separates the immediate post-commit workflows from the ChromaDB indexing, which is handled asynchronously via the job queue system.

## Architecture

### Updated Workflow

1. **Project Commit** → Triggers entity update service
2. **Entity Update Service** → Submits two jobs:
   - `POST_COMMIT_WORKFLOW` (highest priority)
   - `CHROMADB_INDEXING` (medium priority)
3. **Post-Commit Workflow** → Generates LLM definitions and creates MDL file
4. **ChromaDB Indexing Job** → Processes MDL file and indexes into ChromaDB

### Components

#### Post-Commit Service
- Generates LLM definitions for tables
- Creates MDL file using MDL Builder Service
- Updates project metadata with LLM definitions
- **No longer submits ChromaDB indexing job directly**

#### Entity Update Service
- Automatically submits jobs when projects are committed
- Submits both post-commit workflow and ChromaDB indexing jobs
- Handles job priority and metadata

#### ChromaDB Indexing Job Handler
- Reads MDL file from project metadata
- Uses existing indexing components (ProjectMeta, TableDescription, DBSchema)
- Updates project metadata with indexing results

#### MDL Builder Service
- Builds complete MDL definitions from PostgreSQL objects
- Integrates LLM-generated business context
- Provides read-only API endpoints

## Key Changes

### 1. Asynchronous ChromaDB Indexing
- ChromaDB indexing is now handled asynchronously via job queue
- No longer blocks the post-commit workflow
- Provides better scalability and error handling

### 2. MDL File Creation
- Post-commit service creates MDL file using MDL Builder Service
- MDL file contains both database schema and LLM-generated definitions
- File path is stored in project metadata for ChromaDB indexing job

### 3. Read-Only MDL API
- MDL Builder API endpoints are now read-only (GET only)
- No file creation or modification via API
- Provides data retrieval for external tools

### 4. Job Queue Integration
- ChromaDB indexing job is automatically submitted on project commit
- Job includes project metadata and user context
- Supports retry mechanisms and error handling

## Workflow Details

### Step 1: Project Commit
```python
# Entity update service automatically submits jobs
await entity_update_service.on_project_committed(
    project_id="project_123",
    user_id="user_456"
)
```

### Step 2: Post-Commit Workflow Job
```python
# Post-commit service generates LLM definitions and MDL file
results = await post_commit_service.execute_post_commit_workflows(
    project_id="project_123",
    db=db_session
)
```

### Step 3: ChromaDB Indexing Job
```python
# ChromaDB indexing job processes MDL file
result = await job_handlers.handle_chromadb_indexing(job_data)
```

## API Endpoints

### Post-Commit Workflow
```http
POST /api/job-queue/entity-updates/project-commit?project_id=project_123
```

### Manual ChromaDB Indexing
```http
POST /api/job-queue/chromadb-indexing/project_123
```

### MDL Builder (Read-Only)
```http
GET /api/mdl-builder/projects/{project_id}/mdl
GET /api/mdl-builder/tables/{table_id}/mdl
GET /api/mdl-builder/projects/{project_id}/mdl/summary
GET /api/mdl-builder/projects/{project_id}/mdl/validate
GET /api/mdl-builder/projects/{project_id}/mdl/export
```

## Configuration

### Required Settings
```python
# OpenAI API Key for embeddings
OPENAI_API_KEY = "your_openai_api_key"

# ChromaDB settings
CHROMA_STORE_PATH = "/path/to/chromadb"

# Redis settings for job queue
REDIS_HOST = "redis-service"
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_PASSWORD = "your_password"
```

## Error Handling

### Post-Commit Workflow Errors
- LLM definition generation failures are logged
- MDL file creation errors are captured
- Project metadata is updated with error information

### ChromaDB Indexing Errors
- Job automatically retries on failure
- Error details are stored in job metadata
- Project metadata is updated with error information

### Job Queue Errors
- Redis connection failures are handled gracefully
- Worker restarts automatically on connection loss
- Jobs are preserved during service restarts

## Monitoring

### Job Status Tracking
- Real-time job status updates via API
- Detailed error messages and stack traces
- Performance metrics and timing information

### Project Metadata Updates
```json
{
  "llm_definitions": {
    "generated_at": "2024-01-15T10:30:00Z",
    "mdl_file_path": "/path/to/mdl/file.json",
    "definitions_count": 5,
    "tables_processed": 3,
    "status": "pending_indexing"
  },
  "chromadb_indexing": {
    "indexed_at": "2024-01-15T10:35:00Z",
    "indexed_by": "user_123",
    "results": {
      "project_meta": {"documents_written": 1},
      "table_description": {"documents_written": 3},
      "db_schema": {"documents_written": 3}
    }
  }
}
```

## Benefits

### 1. Improved Performance
- Post-commit workflow completes faster
- ChromaDB indexing doesn't block user operations
- Better resource utilization

### 2. Enhanced Reliability
- Automatic retry mechanisms for failed jobs
- Graceful error handling and recovery
- Job persistence during service restarts

### 3. Better Scalability
- Horizontal scaling with multiple workers
- Priority-based job processing
- Configurable worker concurrency

### 4. Improved Monitoring
- Real-time job status tracking
- Detailed error reporting
- Performance metrics and analytics

## Migration Notes

### For Existing Implementations
1. Update post-commit service calls to expect asynchronous ChromaDB indexing
2. Use job status API to monitor indexing progress
3. Update error handling to account for job queue failures
4. Consider implementing job status notifications

### For New Implementations
1. Ensure Redis is configured for job queue
2. Set up worker processes for job processing
3. Configure ChromaDB and OpenAI API keys
4. Implement proper error handling and monitoring

## Troubleshooting

### Common Issues

#### ChromaDB Indexing Job Fails
- Check if MDL file exists and is valid
- Verify ChromaDB connectivity and configuration
- Review OpenAI API key and rate limits
- Check job logs for specific error details

#### Post-Commit Workflow Fails
- Verify LLM service connectivity
- Check MDL Builder Service configuration
- Review database permissions and connectivity
- Ensure proper file system permissions for MDL files

#### Job Queue Issues
- Verify Redis connectivity and configuration
- Check if worker processes are running
- Review job queue configuration and settings
- Monitor Redis memory usage and performance

### Debug Mode
Enable debug logging for detailed troubleshooting:
```python
import logging
logging.getLogger("genieml-agents").setLevel(logging.DEBUG)
logging.getLogger("app.services.job_queue_service").setLevel(logging.DEBUG)
```

## Support

For issues and questions:
1. Check job status and error logs
2. Review configuration settings
3. Verify dependencies and connectivity
4. Consult this documentation
5. Contact the development team

---

*This documentation covers the updated Post-Commit ChromaDB Integration system with asynchronous job processing. For more information about the underlying components, see the individual component documentation.* 
# Project JSON Schemas Integration with Post-Commit Workflow

## Overview

This document describes the integration of project JSON schemas processing into the post-commit workflow for ChromaDB + PostgreSQL integration. The integration allows automatic processing and storage of project metadata in both ChromaDB (for vector search) and PostgreSQL (for structured storage) when a project is committed.

## Architecture

### Components

1. **PostCommitService** - Main orchestrator for post-commit workflows
2. **ProjectJSONService** - Handles JSON schema processing and storage
3. **ChromaDB** - Vector database for semantic search
4. **PostgreSQL** - Structured storage for project metadata

### Workflow Integration

The post-commit workflow now includes two main processes:

1. **ChromaDB Integration** - LLM definition generation and MDL file creation
2. **Project JSON Schemas** - Processing and storage of project metadata

## JSON Schema Types

The integration processes the following JSON schema types:

### 1. Tables JSON
- Table definitions with columns
- Column metadata and relationships
- Calculated column information

### 2. Metrics JSON
- Metric definitions and SQL
- Aggregation types and formats
- Table associations

### 3. Views JSON
- View definitions and SQL
- View types and purposes
- Table associations

### 4. Calculated Columns JSON
- Calculated column definitions
- SQL calculations and dependencies
- Function associations

### 5. Project Summary JSON
- Complete project overview
- All entities combined
- Metadata and context

## Implementation Details

### PostCommitService Updates

The `PostCommitService` class has been enhanced with:

```python
async def _process_project_json_schemas(self, project: Project, db: AsyncSession) -> Dict[str, Any]:
    """Process project JSON schemas and store in ChromaDB + PostgreSQL"""
```

### Workflow Execution

The main workflow execution now includes:

```python
workflows = [
    ("chromadb_integration", self._setup_chromadb_integration),
    ("project_json_schemas", self._process_project_json_schemas)
]
```

### Results Tracking

The integration tracks:

- JSON types processed
- ChromaDB document IDs
- Entity counts (tables, metrics, views, calculated columns)
- Processing timestamps
- Error handling

## Usage

### Automatic Execution

The project JSON schemas processing is automatically executed when:

1. A project is committed (status changes to 'committed')
2. The post-commit workflow is triggered
3. The project has associated entities (tables, metrics, views, calculated columns)

### Manual Execution

You can also trigger the processing manually via the API:

```bash
# Update all project JSON stores
POST /projects/{project_id}/json/update-all

# Update specific JSON type
POST /projects/{project_id}/json/tables
POST /projects/{project_id}/json/metrics
POST /projects/{project_id}/json/views
POST /projects/{project_id}/json/calculated-columns
POST /projects/{project_id}/json/summary
```

## API Endpoints

### Project JSON Storage

- `POST /projects/{project_id}/json/tables` - Store tables JSON
- `POST /projects/{project_id}/json/metrics` - Store metrics JSON
- `POST /projects/{project_id}/json/views` - Store views JSON
- `POST /projects/{project_id}/json/calculated-columns` - Store calculated columns JSON
- `POST /projects/{project_id}/json/summary` - Store project summary JSON
- `POST /projects/{project_id}/json/update-all` - Update all JSON stores

### Search and Retrieval

- `GET /projects/{project_id}/json/{json_type}` - Get JSON data by type
- `POST /projects/{project_id}/json/search` - Search JSON data using ChromaDB
- `GET /projects/{project_id}/json/status` - Get JSON storage status

## Testing

### Test Files

- `test_post_commit.py` - Main post-commit workflow tests
- `test_project_json_schemas_workflow()` - Specific JSON schemas workflow test

### Running Tests

```bash
cd genieml/dataservices/tests
python test_post_commit.py
```

### Test Coverage

The tests cover:

1. Complete post-commit workflow execution
2. Individual JSON schema processing
3. Error handling and recovery
4. Metadata updates
5. ChromaDB document creation
6. PostgreSQL reference storage

## Configuration

### Required Dependencies

- `ProjectJSONService` - For JSON processing
- `SessionManager` - For database sessions
- `ProjectManager` - For project management
- `ChromaDB` - For vector storage

### Environment Variables

- Database connection strings
- ChromaDB configuration
- Logging levels

## Error Handling

### Error Types

1. **Project not found** - Invalid project ID
2. **Database errors** - Connection or transaction issues
3. **ChromaDB errors** - Vector storage issues
4. **JSON processing errors** - Schema validation or parsing issues

### Error Recovery

- Individual workflow failures don't stop other workflows
- Errors are logged and reported in results
- Failed workflows can be retried manually
- Partial success is supported

## Monitoring and Logging

### Log Levels

- `INFO` - Workflow execution and completion
- `ERROR` - Error conditions and failures
- `DEBUG` - Detailed processing information

### Metrics Tracked

- Processing time per JSON type
- Success/failure rates
- Entity counts processed
- ChromaDB document creation success

## Future Enhancements

### Planned Features

1. **Incremental updates** - Only process changed entities
2. **Batch processing** - Handle multiple projects
3. **Real-time updates** - Trigger on entity changes
4. **Advanced search** - Enhanced vector search capabilities
5. **Performance optimization** - Parallel processing

### Integration Opportunities

1. **Notification system** - Alert on processing completion
2. **Dashboard integration** - Real-time status monitoring
3. **API rate limiting** - Prevent overload
4. **Caching layer** - Improve performance

## Troubleshooting

### Common Issues

1. **Missing dependencies** - Ensure all services are available
2. **Database connection** - Check connection strings
3. **ChromaDB availability** - Verify vector database is running
4. **Permission issues** - Check file and database permissions

### Debug Steps

1. Check application logs for error messages
2. Verify project exists and has entities
3. Test individual JSON processing endpoints
4. Validate ChromaDB connection
5. Check PostgreSQL database state

## Conclusion

The project JSON schemas integration provides a comprehensive solution for automatically processing and storing project metadata in both ChromaDB and PostgreSQL. This enables efficient vector search capabilities while maintaining structured data storage for analytics and reporting. 
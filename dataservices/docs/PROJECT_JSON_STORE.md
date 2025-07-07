# Project JSON Store with ChromaDB Integration

This system provides persistent storage for project JSON data with ChromaDB integration for vector search capabilities. It stores project tables, metrics, views, calculated columns, and project summaries as JSON documents that can be efficiently searched and retrieved.

## Architecture

The system consists of:

1. **PostgreSQL Table**: `project_json_store` - Stores metadata and references to ChromaDB documents
2. **ChromaDB Collection**: `project_json_store` - Stores the actual JSON content with vector embeddings
3. **Service Layer**: `ProjectJSONService` - Handles all operations
4. **API Layer**: REST endpoints for CRUD operations

## Database Schema

### project_json_store Table

```sql
CREATE TABLE project_json_store (
    store_id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(50) NOT NULL REFERENCES projects(project_id),
    chroma_document_id VARCHAR(100) NOT NULL UNIQUE,
    json_type VARCHAR(50) NOT NULL,  -- 'tables', 'metrics', 'views', 'calculated_columns', 'project_summary'
    json_content JSONB NOT NULL,
    version VARCHAR(20) DEFAULT '1.0.0',
    is_active BOOLEAN DEFAULT TRUE,
    last_updated_by VARCHAR(100),
    update_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## JSON Types

The system supports the following JSON types:

### 1. Tables JSON
Contains all project tables with their columns and calculated columns:
```json
{
  "project_id": "project_123",
  "project_name": "Sales Analytics",
  "tables": [
    {
      "table_id": "table_456",
      "name": "sales",
      "display_name": "Sales Data",
      "description": "Main sales table",
      "columns": [
        {
          "column_id": "col_789",
          "name": "amount",
          "data_type": "DECIMAL",
          "calculated_column": {
            "calculation_sql": "amount * 1.1",
            "function_id": "func_123"
          }
        }
      ]
    }
  ]
}
```

### 2. Metrics JSON
Contains all project metrics:
```json
{
  "project_id": "project_123",
  "project_name": "Sales Analytics",
  "metrics": [
    {
      "metric_id": "metric_456",
      "name": "total_sales",
      "metric_sql": "SUM(amount)",
      "metric_type": "aggregation",
      "table_name": "sales"
    }
  ]
}
```

### 3. Views JSON
Contains all project views:
```json
{
  "project_id": "project_123",
  "project_name": "Sales Analytics",
  "views": [
    {
      "view_id": "view_456",
      "name": "monthly_sales",
      "view_sql": "SELECT DATE_TRUNC('month', date) as month, SUM(amount) as total FROM sales GROUP BY 1",
      "view_type": "aggregation"
    }
  ]
}
```

### 4. Calculated Columns JSON
Contains all calculated columns:
```json
{
  "project_id": "project_123",
  "project_name": "Sales Analytics",
  "calculated_columns": [
    {
      "calculated_column_id": "calc_456",
      "column_name": "amount_with_tax",
      "calculation_sql": "amount * 1.1",
      "dependencies": ["amount"]
    }
  ]
}
```

### 5. Project Summary JSON
Contains a comprehensive project overview:
```json
{
  "project_id": "project_123",
  "project_name": "Sales Analytics",
  "description": "Sales analytics project",
  "status": "active",
  "version": "1.0.0",
  "summary": {
    "table_count": 5,
    "metric_count": 10,
    "view_count": 3,
    "calculated_column_count": 8
  },
  "tables": [...],
  "metrics": [...],
  "views": [...],
  "calculated_columns": [...]
}
```

## API Endpoints

### Store JSON Data

#### Store Tables JSON
```http
POST /projects/{project_id}/json/tables?updated_by=user123
```

#### Store Metrics JSON
```http
POST /projects/{project_id}/json/metrics?updated_by=user123
```

#### Store Views JSON
```http
POST /projects/{project_id}/json/views?updated_by=user123
```

#### Store Calculated Columns JSON
```http
POST /projects/{project_id}/json/calculated-columns?updated_by=user123
```

#### Store Project Summary JSON
```http
POST /projects/{project_id}/json/summary?updated_by=user123
```

#### Update All JSON Stores
```http
POST /projects/{project_id}/json/update-all?updated_by=user123
```

### Retrieve JSON Data

#### Get JSON by Type
```http
GET /projects/{project_id}/json/{json_type}
```

#### Search JSON Data
```http
POST /projects/{project_id}/json/search
Content-Type: application/json

{
  "search_query": "sales amount calculation",
  "json_type": "tables",
  "n_results": 10
}
```

#### Get JSON Storage Status
```http
GET /projects/{project_id}/json/status
```

### Update on Entity Changes

#### Update JSON on Entity Change
```http
POST /projects/{project_id}/json/update-on-change
Content-Type: application/json

{
  "entity_type": "metric",
  "entity_id": "metric_456",
  "updated_by": "user123"
}
```

## Usage Examples

### Python Service Usage

```python
from app.service.project_json_service import ProjectJSONService
from app.core.session_manager import SessionManager
from app.utils.history import ProjectManager

# Initialize service
session_manager = SessionManager.get_instance()
project_manager = ProjectManager(None)
json_service = ProjectJSONService(session_manager, project_manager)

# Store tables JSON
chroma_doc_id = await json_service.store_project_tables_json("project_123", "user123")

# Get tables JSON
tables_json = await json_service.get_project_json("project_123", "tables")

# Search JSON data
search_results = await json_service.search_project_json(
    project_id="project_123",
    search_query="sales calculation",
    json_type="tables"
)

# Update JSON when entity changes
updated_doc_ids = await json_service.update_project_json_on_change(
    project_id="project_123",
    entity_type="metric",
    entity_id="metric_456",
    updated_by="user123"
)
```

### Automatic Updates

The system automatically updates relevant JSON stores when project entities change:

- **Table/Column changes**: Updates `tables` and `project_summary` JSON
- **Metric changes**: Updates `metrics` and `project_summary` JSON
- **View changes**: Updates `views` and `project_summary` JSON
- **Calculated column changes**: Updates `calculated_columns`, `tables`, and `project_summary` JSON

## Benefits

1. **Vector Search**: ChromaDB provides semantic search capabilities for JSON content
2. **Performance**: JSONB storage in PostgreSQL for efficient querying
3. **Versioning**: Automatic versioning with active/inactive records
4. **Consistency**: Ensures JSON data stays in sync with database entities
5. **Scalability**: ChromaDB handles large-scale vector operations
6. **Flexibility**: Easy to extend with new JSON types

## Setup

1. **Run the SQL script**:
   ```bash
   psql -d your_database -f sql/create_project_json_store_table.sql
   ```

2. **Configure ChromaDB**:
   Ensure ChromaDB is running and accessible via the configuration in `app/core/settings.py`

3. **Add router to main app**:
   ```python
   from app.routers.project_json_routers import router as project_json_router
   app.include_router(project_json_router, prefix="/api/v1", tags=["project-json"])
   ```

## Monitoring

Monitor the system using:

- **Status endpoint**: Check which JSON types exist for each project
- **Database queries**: Monitor the `project_json_store` table
- **ChromaDB metrics**: Monitor ChromaDB collection performance
- **Application logs**: Check service logs for errors and performance

## Best Practices

1. **Regular Updates**: Update JSON stores when entities change
2. **Batch Operations**: Use `update-all` endpoint for bulk updates
3. **Search Optimization**: Use specific JSON types for targeted searches
4. **Error Handling**: Implement proper error handling for ChromaDB operations
5. **Monitoring**: Monitor storage usage and search performance 
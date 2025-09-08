# Workflow Dashboard Integration

This document describes the integration between the dashboard service and workflow database models, enabling the rendering of dashboards based on workflow configurations stored in the database.

## Overview

The workflow dashboard integration allows the agents project to:
1. Fetch workflow data from the workflow services database
2. Extract dashboard queries and configuration from workflow thread components
3. Render dashboards using the agents based on workflow configuration
4. Provide API endpoints for workflow-driven dashboard rendering

## Architecture

```
┌─────────────────────┐    ┌──────────────────────┐    ┌─────────────────────┐
│   Workflow Services │    │   Agents Project     │    │   Dashboard UI      │
│   (Database)        │◄───┤   (API Layer)        │◄───┤   (Frontend)       │
│                     │    │                      │    │                     │
│ - DashboardWorkflow │    │ - DashboardService   │    │ - Dashboard Views   │
│ - ThreadComponent   │    │ - WorkflowIntegration│    │ - Chart Components  │
│ - WorkflowMetadata  │    │ - Dashboard Routes   │    │ - Interactive UI    │
└─────────────────────┘    └──────────────────────┘    └─────────────────────┘
```

## Components

### 1. WorkflowIntegrationService

**File**: `agents/app/services/workflow_integration.py`

Handles communication with the workflow services database:

- `fetch_workflow_from_db(workflow_id)`: Fetches workflow data from database
- `fetch_workflow_components(workflow_id)`: Gets workflow thread components
- `get_workflow_status(workflow_id)`: Retrieves workflow status and metadata
- `transform_workflow_to_dashboard_data(workflow_data)`: Converts workflow data to dashboard format
- `render_dashboard_from_workflow(...)`: Complete workflow-to-dashboard rendering

### 2. Enhanced DashboardService

**File**: `agents/app/services/writers/dashboard_service.py`

Extended with workflow integration methods:

- `render_dashboard_from_workflow_db(...)`: Main method for rendering dashboards from workflow DB
- `get_workflow_components(workflow_id)`: Get workflow components via API
- `get_workflow_status(workflow_id)`: Get workflow status via API
- `preview_dashboard_from_workflow(...)`: Preview dashboard without full rendering

### 3. Dashboard API Routes

**File**: `agents/app/routers/dashboard.py`

New endpoints for workflow integration:

- `POST /dashboard/render-from-workflow`: Render dashboard from workflow database model
- `GET /dashboard/workflow/{workflow_id}/components`: Get workflow components
- `GET /dashboard/workflow/{workflow_id}/status`: Get workflow status
- `POST /dashboard/workflow/{workflow_id}/preview`: Preview dashboard from workflow

## API Usage

### 1. Render Dashboard from Workflow

```http
POST /dashboard/render-from-workflow
Content-Type: application/json

{
  "workflow_id": "123e4567-e89b-12d3-a456-426614174000",
  "project_id": "my_project",
  "natural_language_query": "Highlight high-performing regions in green",
  "additional_context": {
    "user_id": "user123",
    "session_id": "session456"
  },
  "time_filters": {
    "period": "last_quarter"
  },
  "render_options": {
    "mode": "full",
    "enable_caching": true
  }
}
```

**Response:**
```json
{
  "success": true,
  "dashboard_data": {
    "results": {
      "chart_1": {
        "data": [...],
        "metadata": {...}
      }
    }
  },
  "workflow_metadata": {
    "workflow_id": "123e4567-e89b-12d3-a456-426614174000",
    "workflow_state": "ACTIVE",
    "workflow_type": "dashboard_workflow",
    "dashboard_template": "operational_dashboard",
    "workflow_source": "database"
  },
  "metadata": {
    "project_id": "my_project",
    "total_queries": 3,
    "conditional_formatting_applied": true,
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### 2. Get Workflow Components

```http
GET /dashboard/workflow/123e4567-e89b-12d3-a456-426614174000/components
```

**Response:**
```json
{
  "workflow_id": "123e4567-e89b-12d3-a456-426614174000",
  "components": [
    {
      "id": "component_1",
      "component_type": "chart",
      "question": "Show sales by region",
      "description": "Sales analysis by geographic region",
      "sequence_order": 1,
      "configuration": {
        "chart_type": "bar",
        "enable_pagination": true,
        "page_size": 1000
      },
      "chart_config": {
        "type": "bar",
        "x_axis": "region",
        "y_axis": "sales"
      },
      "sql": "SELECT region, SUM(sales) FROM sales_data GROUP BY region",
      "query": "Show sales by region",
      "data_description": "Sales data by region"
    }
  ],
  "total_components": 1
}
```

### 3. Get Workflow Status

```http
GET /dashboard/workflow/123e4567-e89b-12d3-a456-426614174000/status
```

**Response:**
```json
{
  "workflow_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "found",
  "state": "ACTIVE",
  "workflow_metadata": {
    "dashboard_template": "operational_dashboard",
    "dashboard_layout": "grid_2x2",
    "refresh_rate": 300
  },
  "total_components": 3,
  "dashboard_template": "operational_dashboard",
  "last_updated": "2024-01-15T10:30:00Z",
  "created_at": "2024-01-15T09:00:00Z"
}
```

### 4. Preview Dashboard

```http
POST /dashboard/workflow/123e4567-e89b-12d3-a456-426614174000/preview
Content-Type: application/json

{
  "preview_options": {
    "max_queries": 2,
    "enable_caching": true
  }
}
```

## Workflow Data Structure

### DashboardWorkflow Model

```python
class DashboardWorkflow:
    id: UUID
    dashboard_id: UUID
    user_id: UUID
    state: WorkflowState
    current_step: int
    workflow_metadata: Dict[str, Any]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    thread_components: List[ThreadComponent]
```

### ThreadComponent Model

```python
class ThreadComponent:
    id: UUID
    workflow_id: UUID
    component_type: ComponentType  # chart, table, metric, etc.
    question: str
    description: str
    sequence_order: int
    configuration: Dict[str, Any]
    chart_config: Optional[Dict[str, Any]]
    table_config: Optional[Dict[str, Any]]
    alert_config: Optional[Dict[str, Any]]
    sql: Optional[str]
    query: Optional[str]
    data_description: Optional[str]
```

## Configuration

### Environment Variables

```bash
# Workflow Services URL
WORKFLOW_SERVICE_URL=http://workflowservices:8000

# Database connection (for workflow services)
WORKFLOW_DB_HOST=localhost
WORKFLOW_DB_PORT=5432
WORKFLOW_DB_NAME=workflow_services
WORKFLOW_DB_USER=workflow_user
WORKFLOW_DB_PASSWORD=workflow_password
```

### Service Configuration

The `WorkflowIntegrationService` can be configured with:

```python
workflow_integration = WorkflowIntegrationService(
    workflow_service_url="http://workflowservices:8000"
)
```

## Error Handling

### Common Error Scenarios

1. **Workflow Not Found**
   ```json
   {
     "success": false,
     "error": "Workflow 123e4567-e89b-12d3-a456-426614174000 not found",
     "workflow_id": "123e4567-e89b-12d3-a456-426614174000"
   }
   ```

2. **No Dashboard Queries**
   ```json
   {
     "success": false,
     "error": "No dashboard queries found in workflow 123e4567-e89b-12d3-a456-426614174000",
     "workflow_id": "123e4567-e89b-12d3-a456-426614174000"
   }
   ```

3. **Network Error**
   ```json
   {
     "success": false,
     "error": "Network error: Connection refused",
     "workflow_id": "123e4567-e89b-12d3-a456-426614174000"
   }
   ```

## Testing

### Running Integration Tests

```bash
# Run workflow dashboard integration examples
python agents/tests/workflow_dashboard_integration.py

# Run existing dashboard examples
python agents/tests/dashboard_stream.py
python agents/tests/dashboard_examples.py
```

### Test Scenarios

1. **Valid Workflow Rendering**: Test with existing workflow ID
2. **Invalid Workflow ID**: Test error handling with non-existent workflow
3. **Empty Workflow Components**: Test with workflow having no components
4. **Network Failures**: Test with workflow service unavailable
5. **Preview Mode**: Test dashboard preview functionality

## Deployment

### Docker Configuration

```yaml
# docker-compose.yml
services:
  agents:
    build: ./agents
    environment:
      - WORKFLOW_SERVICE_URL=http://workflowservices:8000
    depends_on:
      - workflowservices
  
  workflowservices:
    build: ./workflowservices
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/workflow_services
```

### Service Dependencies

The agents service depends on:
- Workflow services API (for fetching workflow data)
- PostgreSQL database (for workflow data storage)
- Redis (for caching, optional)

## Monitoring

### Health Checks

```http
GET /dashboard/health
```

### Service Status

```http
GET /dashboard/service-status
```

### Execution History

```http
GET /dashboard/execution-history?limit=50
```

## Performance Considerations

1. **Caching**: Workflow data can be cached to reduce database calls
2. **Pagination**: Large workflows can be paginated for components
3. **Async Processing**: Dashboard rendering is fully asynchronous
4. **Connection Pooling**: HTTP client uses connection pooling for workflow service calls

## Security

1. **Authentication**: Workflow access should be authenticated
2. **Authorization**: Users should only access their own workflows
3. **Input Validation**: All workflow IDs and parameters are validated
4. **SQL Injection**: SQL queries from workflows are parameterized

## Troubleshooting

### Common Issues

1. **Workflow Service Unavailable**
   - Check if workflow services are running
   - Verify network connectivity
   - Check service URLs in configuration

2. **Database Connection Issues**
   - Verify database credentials
   - Check database connectivity
   - Ensure database schema is up to date

3. **Dashboard Rendering Failures**
   - Check agent pipeline availability
   - Verify SQL query syntax
   - Check data source connectivity

### Debugging

Enable debug logging:

```python
import logging
logging.getLogger("lexy-ai-service").setLevel(logging.DEBUG)
```

### Logs to Monitor

- Workflow data fetching logs
- Dashboard rendering logs
- Agent pipeline execution logs
- Error logs for failed operations

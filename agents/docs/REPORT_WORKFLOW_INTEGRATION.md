# Report Workflow Integration

This document describes the integration between the report service and workflow database models, enabling the rendering of reports based on workflow configurations stored in the database.

## Overview

The report workflow integration allows the agents project to:
1. Fetch workflow data from the workflow services database
2. Extract report queries and configuration from workflow thread components
3. Render reports using the agents based on workflow configuration
4. Provide API endpoints for workflow-driven report rendering

## Architecture

```
┌─────────────────────┐    ┌──────────────────────┐    ┌─────────────────────┐
│   Workflow Services │    │   Agents Project     │    │   Report UI         │
│   (Database)        │◄───┤   (API Layer)        │◄───┤   (Frontend)       │
│                     │    │                      │    │                     │
│ - ReportWorkflow    │    │ - ReportService      │    │ - Report Views      │
│ - ThreadComponent   │    │ - WorkflowIntegration│    │ - Report Components │
│ - WorkflowMetadata  │    │ - Report Routes      │    │ - Interactive UI    │
└─────────────────────┘    └──────────────────────┘    └─────────────────────┘
```

## Components

### 1. WorkflowIntegrationService

**File**: `agents/app/services/workflow_integration.py`

Handles communication with the workflow services database (shared with dashboard integration):

- `fetch_workflow_from_db(workflow_id)`: Fetches workflow data from database
- `fetch_workflow_components(workflow_id)`: Gets workflow thread components
- `get_workflow_status(workflow_id)`: Retrieves workflow status and metadata
- `transform_workflow_to_dashboard_data(workflow_data)`: Converts workflow data to report format
- `render_dashboard_from_workflow(...)`: Complete workflow-to-report rendering

### 2. Enhanced ReportService

**File**: `agents/app/services/writers/report_service.py`

Extended with workflow integration methods:

- `render_report_from_workflow_db(...)`: Main method for rendering reports from workflow DB
- `get_workflow_components(workflow_id)`: Get workflow components via API
- `get_workflow_status(workflow_id)`: Get workflow status via API
- `preview_report_from_workflow(...)`: Preview report without full rendering
- `_convert_dashboard_to_report_context(...)`: Convert dashboard context to report format
- `_parse_writer_actor(...)`: Parse writer actor configuration
- `_parse_business_goal(...)`: Parse business goal configuration

### 3. Report API Routes

**File**: `agents/app/routers/report.py`

New endpoints for workflow integration:

- `POST /report/render-from-workflow`: Render report from workflow database model
- `GET /report/workflow/{workflow_id}/components`: Get workflow components
- `GET /report/workflow/{workflow_id}/status`: Get workflow status
- `POST /report/workflow/{workflow_id}/preview`: Preview report from workflow

## API Usage

### 1. Render Report from Workflow

```http
POST /report/render-from-workflow
Content-Type: application/json

{
  "workflow_id": "123e4567-e89b-12d3-a456-426614174000",
  "project_id": "my_project",
  "natural_language_query": "Create an executive summary highlighting key performance indicators",
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
  },
  "report_template": "executive_summary",
  "writer_actor": "EXECUTIVE",
  "business_goal": "strategic"
}
```

**Response:**
```json
{
  "success": true,
  "report_data": {
    "orchestration_metadata": {
      "comprehensive_report_generated": true,
      "conditional_formatting_applied": true
    },
    "report_sections": {
      "executive_summary": "...",
      "analysis": "...",
      "conclusions": "..."
    }
  },
  "workflow_metadata": {
    "workflow_id": "123e4567-e89b-12d3-a456-426614174000",
    "workflow_state": "ACTIVE",
    "workflow_type": "report_workflow",
    "report_template": "executive_summary",
    "workflow_source": "database"
  },
  "metadata": {
    "project_id": "my_project",
    "workflow_id": "123e4567-e89b-12d3-a456-426614174000",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### 2. Get Workflow Components

```http
GET /report/workflow/123e4567-e89b-12d3-a456-426614174000/components
```

**Response:**
```json
{
  "workflow_id": "123e4567-e89b-12d3-a456-426614174000",
  "components": [
    {
      "component_id": "component_1",
      "component_type": "chart",
      "question": "Show sales performance by region",
      "description": "Regional sales analysis for Q4",
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
      "query": "Show sales performance by region",
      "data_description": "Sales data aggregated by region"
    }
  ],
  "total_components": 1
}
```

### 3. Get Workflow Status

```http
GET /report/workflow/123e4567-e89b-12d3-a456-426614174000/status
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

### 4. Preview Report

```http
POST /report/workflow/123e4567-e89b-12d3-a456-426614174000/preview
Content-Type: application/json

{
  "preview_options": {
    "max_queries": 2,
    "enable_caching": true
  }
}
```

## Report Templates

### Available Templates

1. **Executive Summary Report**
   - Writer Actor: `EXECUTIVE`
   - Business Goal: Strategic decision making
   - Components: executive_overview, key_metrics, trends_analysis, recommendations

2. **Detailed Analysis Report**
   - Writer Actor: `ANALYST`
   - Business Goal: Operational insights
   - Components: executive_summary, methodology, detailed_findings, data_analysis, conclusions, appendix

3. **Performance Review Report**
   - Writer Actor: `ANALYST`
   - Business Goal: Performance optimization
   - Components: performance_overview, kpi_analysis, trends, benchmarks, action_items

4. **Trend Analysis Report**
   - Writer Actor: `DATA_SCIENTIST`
   - Business Goal: Trend analysis
   - Components: trend_overview, seasonal_patterns, forecasting, drivers_analysis, future_outlook

### Writer Actors

- `EXECUTIVE`: High-level strategic reports for executives
- `ANALYST`: Detailed operational reports for analysts
- `DATA_SCIENTIST`: Technical reports with advanced analytics

### Business Goals

- `strategic`: Strategic decision making focus
- `operational`: Day-to-day operational insights
- `performance`: Performance optimization focus

## Workflow Data Structure

### ReportWorkflow Model

```python
class ReportWorkflow:
    id: UUID
    report_id: UUID
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
    component_type: ComponentType  # chart, table, metric, text, etc.
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

2. **No Report Queries**
   ```json
   {
     "success": false,
     "error": "No report queries found in workflow 123e4567-e89b-12d3-a456-426614174000",
     "workflow_id": "123e4567-e89b-12d3-a456-426614174000"
   }
   ```

3. **Invalid Writer Actor**
   ```json
   {
     "success": false,
     "error": "Invalid writer actor: INVALID_ACTOR",
     "workflow_id": "123e4567-e89b-12d3-a456-426614174000"
   }
   ```

4. **Network Error**
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
# Run report workflow integration examples
python agents/tests/report_workflow_integration.py

# Run existing report examples
python agents/tests/dashboard_examples.py
```

### Test Scenarios

1. **Valid Workflow Rendering**: Test with existing workflow ID
2. **Invalid Workflow ID**: Test error handling with non-existent workflow
3. **Empty Workflow Components**: Test with workflow having no components
4. **Network Failures**: Test with workflow service unavailable
5. **Preview Mode**: Test report preview functionality
6. **Template Validation**: Test different report templates
7. **Writer Actor Validation**: Test different writer actors
8. **Business Goal Validation**: Test different business goals

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
GET /report/health
```

### Service Status

```http
GET /report/service-status
```

### Execution History

```http
GET /report/execution-history?limit=50
```

## Performance Considerations

1. **Caching**: Workflow data can be cached to reduce database calls
2. **Pagination**: Large workflows can be paginated for components
3. **Async Processing**: Report rendering is fully asynchronous
4. **Connection Pooling**: HTTP client uses connection pooling for workflow service calls
5. **Template Caching**: Report templates are cached in memory

## Security

1. **Authentication**: Workflow access should be authenticated
2. **Authorization**: Users should only access their own workflows
3. **Input Validation**: All workflow IDs and parameters are validated
4. **SQL Injection**: SQL queries from workflows are parameterized
5. **Data Sanitization**: Report content is sanitized before rendering

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

3. **Report Rendering Failures**
   - Check agent pipeline availability
   - Verify SQL query syntax
   - Check data source connectivity

4. **Template Issues**
   - Verify template configuration
   - Check writer actor and business goal settings
   - Validate component mappings

### Debugging

Enable debug logging:

```python
import logging
logging.getLogger("lexy-ai-service").setLevel(logging.DEBUG)
```

### Logs to Monitor

- Workflow data fetching logs
- Report rendering logs
- Agent pipeline execution logs
- Error logs for failed operations
- Template processing logs

## Best Practices

1. **Workflow Design**: Design workflows with clear component structure
2. **Template Selection**: Choose appropriate templates for use cases
3. **Writer Actor Selection**: Match writer actor to target audience
4. **Business Goal Alignment**: Align business goals with report objectives
5. **Error Handling**: Implement comprehensive error handling
6. **Caching Strategy**: Use appropriate caching for performance
7. **Monitoring**: Monitor report generation performance and errors
8. **Testing**: Test with various workflow configurations

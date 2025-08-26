# Dashboard Service Workflow Integration

The `DashboardService` now includes comprehensive workflow integration capabilities, allowing you to process dashboards using workflow data from various sources including API calls, JSON files, and direct workflow model objects.

## 🚀 Dashboard Workflow Integration Features

- **Multiple Input Formats**: Support for dictionaries, JSON strings, JSON files, and workflow model objects
- **Dashboard Workflow Model Integration**: Direct integration with SQLAlchemy dashboard workflow models
- **Component Extraction**: Automatic extraction of thread components from workflows
- **Smart Configuration**: Intelligent determination of dashboard templates and layouts
- **Enhanced Context**: Automatic creation of comprehensive dashboard context from workflow metadata
- **Error Handling**: Comprehensive error handling for all input types
- **Status Monitoring**: Real-time progress tracking with workflow-specific status updates

## 📥 Supported Input Formats

### 1. Dictionary Input
```python
workflow_data = {
    "id": "dashboard-workflow-123",
    "state": "active",
    "workflow_metadata": {
        "dashboard_title": "Q4 Sales Dashboard",
        "dashboard_template": "executive_dashboard",
        "dashboard_layout": "grid_2x2"
    },
    "thread_components": [...]
}

result = await dashboard_service.process_dashboard_from_workflow(
    workflow_data=workflow_data,
    dashboard_queries=your_queries,
    project_id="your_project"
)
```

### 2. JSON File Input
```python
# From JSON file
result = await dashboard_service.process_dashboard_from_workflow(
    workflow_data="/path/to/dashboard_workflow.json",
    dashboard_queries=your_queries,
    project_id="your_project"
)
```

### 3. JSON String Input
```python
# From JSON string
workflow_json = '{"id": "dashboard-workflow-123", "state": "active", ...}'
result = await dashboard_service.process_dashboard_from_workflow(
    workflow_data=workflow_json,
    dashboard_queries=your_queries,
    project_id="your_project"
)
```

### 4. Workflow Model Object
```python
# From SQLAlchemy model (if available)
from workflowservices.app.models.workflowmodels import DashboardWorkflow

workflow_obj = session.query(DashboardWorkflow).filter_by(id=workflow_id).first()
result = await dashboard_service.process_dashboard_from_workflow(
    workflow_data=workflow_obj,
    dashboard_queries=your_queries,
    project_id="your_project"
)
```

## 🔧 Dashboard Workflow Data Structure

The service expects dashboard workflow data with the following structure:

```json
{
    "id": "dashboard-workflow-123",
    "dashboard_id": "dashboard-456",
    "user_id": "user-789",
    "state": "active",
    "current_step": 2,
    "workflow_metadata": {
        "dashboard_title": "Q4 Sales Performance Dashboard",
        "dashboard_description": "Real-time dashboard for Q4 sales performance monitoring",
        "dashboard_template": "executive_dashboard",
        "dashboard_layout": "grid_2x2",
        "refresh_rate": 300,
        "auto_refresh": true,
        "responsive": true,
        "theme": "corporate",
        "custom_styling": {
            "primary_color": "#1f77b4",
            "secondary_color": "#ff7f0e",
            "font_family": "Arial, sans-serif"
        },
        "interactive_features": ["drill_down", "hover_tooltips", "zoom_pan"],
        "export_options": ["pdf", "png", "csv", "excel"],
        "sharing_config": {
            "allow_sharing": true,
            "permissions": ["view", "export"],
            "public_access": false
        },
        "alert_config": {
            "enable_alerts": true,
            "alert_thresholds": {
                "sales_target": 0.8,
                "performance_score": 75
            }
        },
        "performance_config": {
            "lazy_loading": true,
            "data_caching": true,
            "query_optimization": true
        }
    },
    "thread_components": [
        {
            "id": "comp-1",
            "component_type": "overview",
            "sequence_order": 1,
            "question": "Sales Overview",
            "description": "High-level sales performance summary",
            "configuration": {"style": "card", "size": "large"},
            "chart_config": null,
            "table_config": null
        },
        {
            "id": "comp-2",
            "component_type": "chart",
            "sequence_order": 2,
            "question": "Regional Sales Chart",
            "description": "Sales performance by region with interactive chart",
            "configuration": {"interactive": true, "chart_type": "bar"},
            "chart_config": {
                "type": "bar",
                "x_axis": "region",
                "y_axis": "sales_amount",
                "colors": ["#1f77b4", "#ff7f0e", "#2ca02c"],
                "animation": true
            },
            "table_config": null
        }
    ]
}
```

## 🧩 Thread Component Types

The service supports various component types for dashboard construction:

| Component Type | Description | Configuration Options |
|----------------|-------------|----------------------|
| `overview` | High-level summary cards | style, size, layout |
| `chart` | Interactive visualizations | type, axes, colors, animation |
| `metric` | Key performance indicators | display_mode, highlight_thresholds |
| `table` | Detailed data tables | columns, sorting, pagination, search |
| `alert` | Real-time notifications | alert_level, auto_dismiss, conditions |

## 🎨 Dashboard Templates

The service comes with several predefined dashboard templates:

### Executive Dashboard
- **Purpose**: High-level dashboard for executives and stakeholders
- **Components**: Overview metrics, KPI summary, trend charts, alert summary
- **Layout**: Grid 2x2
- **Refresh Rate**: 300 seconds

### Operational Dashboard
- **Purpose**: Detailed operational metrics and real-time data
- **Components**: Real-time metrics, performance charts, status indicators, detailed tables
- **Layout**: Grid 3x3
- **Refresh Rate**: 60 seconds

### Analytical Dashboard
- **Purpose**: Deep analytical insights with interactive visualizations
- **Components**: Interactive charts, drill-down tables, correlation analysis, forecasting charts
- **Layout**: Flexible
- **Refresh Rate**: 600 seconds

### Monitoring Dashboard
- **Purpose**: System and performance monitoring with alerts
- **Components**: System metrics, performance monitors, alert panels, log summaries
- **Layout**: Grid 2x3
- **Refresh Rate**: 30 seconds

## ⚙️ Dashboard Configuration Extraction

The service automatically extracts comprehensive dashboard configuration:

```python
dashboard_config = {
    "template": "executive_dashboard",
    "layout": "grid_2x2",
    "refresh_rate": 300,
    "auto_refresh": True,
    "responsive": True,
    "theme": "corporate",
    "custom_styling": {...},
    "interactive_features": [...],
    "export_options": [...],
    "sharing_config": {...},
    "alert_config": {...},
    "performance_config": {...}
}
```

## 🔄 Dashboard Processing Pipeline

The complete dashboard workflow processing pipeline:

1. **Input Parsing**: Parse workflow data from various formats
2. **Configuration Extraction**: Extract dashboard configuration from workflow metadata
3. **Component Processing**: Process thread components and their configurations
4. **Context Creation**: Generate enhanced dashboard context
5. **Dashboard Processing**: Execute the dashboard processing pipeline
6. **Metadata Addition**: Add workflow metadata to results

## 📊 Status Callbacks

Dashboard workflow-specific status updates are provided:

```python
def status_callback(status: str, details: Dict[str, Any] = None):
    print(f"Status: {status} - {details}")

# Dashboard workflow-specific statuses:
# - workflow_dashboard_processing_started
# - workflow_dashboard_processing_completed
# - workflow_dashboard_processing_failed
```

## 🧪 Testing Dashboard Workflow Integration

Run the comprehensive dashboard workflow integration test suite:

```bash
cd agents/app/services/writers
python test_dashboard_workflow_integration.py
```

The test suite covers:
- Dictionary input processing
- JSON file loading
- JSON string parsing
- Configuration extraction
- Component extraction
- Context generation
- Validation
- Error handling
- End-to-end integration

## 🔌 API Integration Examples

### FastAPI Integration
```python
from fastapi import FastAPI, HTTPException
from app.services.writers.dashboard_service import create_dashboard_service

app = FastAPI()
dashboard_service = create_dashboard_service()

@app.post("/process-dashboard-from-workflow")
async def process_dashboard_from_workflow(request: DashboardWorkflowRequest):
    try:
        result = await dashboard_service.process_dashboard_from_workflow(
            workflow_data=request.workflow_data,
            dashboard_queries=request.dashboard_queries,
            project_id=request.project_id,
            natural_language_query=request.natural_language_query
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class DashboardWorkflowRequest(BaseModel):
    workflow_data: Union[Dict[str, Any], str]  # Dict or JSON string
    dashboard_queries: List[Dict[str, Any]]
    project_id: str
    natural_language_query: Optional[str] = None
```

### Celery Integration
```python
from celery import Celery
from app.services.writers.dashboard_service import create_dashboard_service

celery_app = Celery('dashboards')

@celery_app.task
def process_dashboard_workflow_task(workflow_data, queries, project_id):
    dashboard_service = create_dashboard_service()
    return dashboard_service.process_dashboard_from_workflow(
        workflow_data=workflow_data,
        dashboard_queries=queries,
        project_id=project_id
    )
```

## 📁 File-Based Dashboard Workflow Management

### Loading from JSON Files
```python
# Load dashboard workflow from file
workflow_file = "workflows/q4_sales_dashboard_workflow.json"
result = await dashboard_service.process_dashboard_from_workflow(
    workflow_data=workflow_file,
    dashboard_queries=your_queries,
    project_id="q4_sales_dashboard"
)
```

### Dashboard Workflow File Structure
```json
{
    "id": "q4_sales_dashboard_workflow",
    "state": "active",
    "workflow_metadata": {
        "dashboard_title": "Q4 Sales Performance Dashboard",
        "dashboard_template": "executive_dashboard",
        "dashboard_layout": "grid_2x2"
    },
    "thread_components": [...]
}
```

## 🚨 Error Handling

The service includes comprehensive error handling:

```python
try:
    result = await dashboard_service.process_dashboard_from_workflow(
        workflow_data=workflow_data,
        dashboard_queries=queries,
        project_id="project_id"
    )
except ValueError as e:
    print(f"Invalid workflow data: {e}")
except FileNotFoundError as e:
    print(f"Workflow file not found: {e}")
except json.JSONDecodeError as e:
    print(f"Invalid JSON format: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## 🔧 Advanced Configuration

### Custom Dashboard Processing
```python
# Override automatic configuration
result = await dashboard_service.process_dashboard_from_workflow(
    workflow_data=workflow_data,
    dashboard_queries=queries,
    project_id="project_id",
    additional_context={
        "force_template": "custom_dashboard",
        "force_layout": "flexible",
        "custom_refresh_rate": 120
    }
)
```

### Dashboard Workflow Caching
```python
# The service automatically caches workflow data for performance
# Access cached workflows
cached_workflows = dashboard_service._workflow_cache
```

## 📈 Performance Considerations

- **Lazy Loading**: Workflow models are only imported when needed
- **Caching**: Workflow data is cached for repeated use
- **Async Processing**: All operations are asynchronous for better performance
- **Memory Management**: Automatic cleanup of temporary data
- **Query Optimization**: Built-in query optimization for dashboard performance

## 🔍 Debugging and Monitoring

### Enable Debug Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Monitor Dashboard Processing
```python
def detailed_status_callback(status: str, details: Dict[str, Any] = None):
    print(f"[{datetime.now()}] {status}: {details}")
    # Log to file, database, or monitoring system

result = await dashboard_service.process_dashboard_from_workflow(
    workflow_data=workflow_data,
    dashboard_queries=queries,
    project_id="project_id",
    status_callback=detailed_status_callback
)
```

## 🚀 Production Deployment

### Environment Configuration
```bash
# Set environment variables for production
export WORKFLOW_MODELS_PATH="/path/to/workflowservices"
export DASHBOARD_SERVICE_LOG_LEVEL="INFO"
export DASHBOARD_SERVICE_CACHE_SIZE="1000"
export DASHBOARD_SERVICE_REFRESH_RATE="300"
```

### Health Checks
```python
# Check service health
status = dashboard_service.get_service_status()
workflow_status = status.get("workflow_integration", {})
print(f"Dashboard Workflow Integration: {workflow_status.get('available', False)}")
```

## 🔄 Migration from Legacy Usage

If you're migrating from the previous dashboard service:

```python
# Old way
result = await dashboard_service.process_dashboard_with_conditional_formatting(
    natural_language_query=query,
    dashboard_queries=queries,
    project_id="project_id",
    dashboard_context=context
)

# New way with workflow
result = await dashboard_service.process_dashboard_from_workflow(
    workflow_data=workflow_data,
    dashboard_queries=queries,
    project_id="project_id",
    natural_language_query=query
)
```

## 📊 Dashboard Analytics and Metrics

The service provides comprehensive analytics:

```python
# Get execution history
history = dashboard_service.get_execution_history(limit=10)

for entry in history:
    print(f"Project: {entry['project_id']}")
    print(f"Workflow ID: {entry.get('workflow_id')}")
    print(f"Dashboard Template: {entry.get('dashboard_template')}")
    print(f"Success: {entry['success']}")
    print(f"Total Charts: {entry['total_charts']}")
    print(f"Timestamp: {entry['timestamp']}")
```

## 🎨 Custom Dashboard Styling

### Theme Configuration
```python
workflow_metadata = {
    "theme": "corporate",
    "custom_styling": {
        "primary_color": "#1f77b4",
        "secondary_color": "#ff7f0e",
        "accent_color": "#2ca02c",
        "font_family": "Arial, sans-serif",
        "border_radius": "8px",
        "shadow": "0 2px 4px rgba(0,0,0,0.1)"
    }
}
```

### Layout Options
- **Grid 2x2**: 2x2 grid layout for executive dashboards
- **Grid 3x3**: 3x3 grid for detailed operational dashboards
- **Grid 2x3**: 2x3 grid for monitoring dashboards
- **Flexible**: Dynamic layout for analytical dashboards

## 🔔 Alert and Notification System

### Alert Configuration
```python
alert_config = {
    "enable_alerts": True,
    "alert_thresholds": {
        "sales_target": 0.8,
        "performance_score": 75,
        "response_time": 2000
    },
    "notification_channels": ["email", "slack", "webhook"],
    "escalation_rules": {
        "critical": "immediate",
        "high": "within_1_hour",
        "medium": "within_4_hours"
    }
}
```

## 📚 Additional Resources

- [Dashboard Service Documentation](README_DASHBOARD_SERVICE.md)
- [Workflow Models Reference](../workflowservices/app/models/workflowmodels.py)
- [Test Suite Examples](test_dashboard_workflow_integration.py)
- [API Integration Guide](../docs/api_integration.md)

## 🤝 Contributing

When extending dashboard workflow integration:

1. Follow the existing pattern for new input formats
2. Add comprehensive error handling
3. Include status callbacks for new operations
4. Update the test suite
5. Document new features in this README

## 📄 License

This dashboard workflow integration is part of the GenieML platform and follows the project's licensing terms.

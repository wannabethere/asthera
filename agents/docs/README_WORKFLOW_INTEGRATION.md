# Report Service Workflow Integration

The `ReportService` now includes comprehensive workflow integration capabilities, allowing you to generate reports using workflow data from various sources including API calls, JSON files, and direct workflow model objects.

## 🚀 Workflow Integration Features

- **Multiple Input Formats**: Support for dictionaries, JSON strings, JSON files, and workflow model objects
- **Workflow Model Integration**: Direct integration with SQLAlchemy workflow models
- **Component Extraction**: Automatic extraction of thread components from workflows
- **Smart Configuration**: Intelligent determination of writer actors and business goals
- **Context Generation**: Automatic creation of report context from workflow metadata
- **Error Handling**: Comprehensive error handling for all input types
- **Status Monitoring**: Real-time progress tracking with workflow-specific status updates

## 📥 Supported Input Formats

### 1. Dictionary Input
```python
workflow_data = {
    "id": "workflow-123",
    "state": "active",
    "workflow_metadata": {
        "report_title": "Q4 Sales Report",
        "writer_actor": "EXECUTIVE_ANALYST",
        "business_goal": "STRATEGIC_DECISION_MAKING"
    },
    "thread_components": [...]
}

result = await report_service.generate_report_from_workflow(
    workflow_data=workflow_data,
    report_queries=your_queries,
    project_id="your_project"
)
```

### 2. JSON File Input
```python
# From JSON file
result = await report_service.generate_report_from_workflow(
    workflow_data="/path/to/workflow.json",
    report_queries=your_queries,
    project_id="your_project"
)
```

### 3. JSON String Input
```python
# From JSON string
workflow_json = '{"id": "workflow-123", "state": "active", ...}'
result = await report_service.generate_report_from_workflow(
    workflow_data=workflow_json,
    report_queries=your_queries,
    project_id="your_project"
)
```

### 4. Workflow Model Object
```python
# From SQLAlchemy model (if available)
from workflowservices.app.models.workflowmodels import ReportWorkflow

workflow_obj = session.query(ReportWorkflow).filter_by(id=workflow_id).first()
result = await report_service.generate_report_from_workflow(
    workflow_data=workflow_obj,
    report_queries=your_queries,
    project_id="your_project"
)
```

## 🔧 Workflow Data Structure

The service expects workflow data with the following structure:

```json
{
    "id": "workflow-123",
    "report_id": "report-456",
    "user_id": "user-789",
    "state": "active",
    "current_step": 2,
    "workflow_metadata": {
        "report_title": "Q4 Sales Performance Report",
        "report_description": "Comprehensive analysis of Q4 sales performance",
        "report_sections": ["executive_summary", "regional_analysis", "recommendations"],
        "writer_actor": "EXECUTIVE_ANALYST",
        "business_goal": "STRATEGIC_DECISION_MAKING",
        "report_period": "Q4 2024",
        "target_audience": "executives"
    },
    "thread_components": [
        {
            "id": "comp-1",
            "component_type": "overview",
            "sequence_order": 1,
            "question": "Executive Overview",
            "description": "High-level summary of Q4 performance",
            "configuration": {"style": "executive", "length": "concise"}
        },
        {
            "id": "comp-2",
            "component_type": "chart",
            "sequence_order": 2,
            "question": "Regional Sales Analysis",
            "description": "Sales performance by region with visualizations",
            "chart_config": {"type": "bar", "metrics": ["sales", "growth"]},
            "configuration": {"interactive": True}
        }
    ]
}
```

## 🧩 Thread Component Types

The service supports various component types that map to report components:

| Workflow Type | Report Component | Description |
|---------------|------------------|-------------|
| `overview` | TEXT | Executive overview and summaries |
| `description` | TEXT | Detailed descriptions |
| `chart` | CHART | Chart visualizations |
| `table` | TABLE | Tabular data displays |
| `metric` | METRIC | Key performance indicators |
| `insight` | TEXT | Analytical insights |
| `narrative` | TEXT | Storytelling content |
| `alert` | ALERT | Alert notifications |

## 🎯 Automatic Configuration Detection

### Writer Actor Detection
The service automatically determines the appropriate writer actor based on:

1. **Explicit Configuration**: If `writer_actor` is specified in workflow metadata
2. **Workflow State**: Analysis of workflow state and type
3. **Default Fallback**: DATA_ANALYST if no other determination is possible

```python
# Examples of automatic detection:
# - "executive" in state → EXECUTIVE_ANALYST
# - "performance" in state → PERFORMANCE_ANALYST  
# - "trend" in state → TREND_ANALYST
# - Default → DATA_ANALYST
```

### Business Goal Detection
Similarly, business goals are automatically determined:

1. **Explicit Configuration**: If `business_goal` is specified in workflow metadata
2. **Workflow Analysis**: Based on workflow state and purpose
3. **Default Fallback**: OPERATIONAL_INSIGHTS if no other determination is possible

```python
# Examples of automatic detection:
# - "executive" in state → STRATEGIC_DECISION_MAKING
# - "performance" in state → PERFORMANCE_OPTIMIZATION
# - "trend" in state → TREND_ANALYSIS
# - Default → OPERATIONAL_INSIGHTS
```

## 📋 Report Context Generation

The service automatically creates comprehensive report context from workflow data:

```python
report_context = {
    "title": "Q4 Sales Performance Report",  # From workflow metadata
    "description": "Comprehensive analysis of Q4 sales performance",
    "sections": ["executive_summary", "regional_analysis", "recommendations"],
    "available_columns": ["region", "sales", "date", "performance_score"],  # Extracted from queries
    "data_types": {
        "region": "categorical",
        "sales": "numeric", 
        "date": "datetime",
        "performance_score": "numeric"
    },
    "workflow_id": "workflow-123",
    "workflow_state": "active",
    "workflow_metadata": {...}  # Full workflow metadata
}
```

## 🔄 Workflow Processing Pipeline

The complete workflow processing pipeline:

1. **Input Parsing**: Parse workflow data from various formats
2. **Component Extraction**: Extract and convert thread components
3. **Configuration Detection**: Determine writer actor and business goal
4. **Context Creation**: Generate report context from workflow data
5. **Report Generation**: Execute the report orchestrator pipeline
6. **Metadata Addition**: Add workflow metadata to results

## 📊 Status Callbacks

Workflow-specific status updates are provided:

```python
def status_callback(status: str, details: Dict[str, Any] = None):
    print(f"Status: {status} - {details}")

# Workflow-specific statuses:
# - workflow_report_generation_started
# - workflow_report_generation_completed
# - workflow_report_generation_failed
```

## 🧪 Testing Workflow Integration

Run the comprehensive workflow integration test suite:

```bash
cd agents/app/services/writers
python test_workflow_integration.py
```

The test suite covers:
- Dictionary input processing
- JSON file loading
- JSON string parsing
- Component extraction
- Context generation
- Validation
- Error handling
- End-to-end integration

## 🔌 API Integration Examples

### FastAPI Integration
```python
from fastapi import FastAPI, HTTPException
from app.services.writers.report_service import create_report_service

app = FastAPI()
report_service = create_report_service()

@app.post("/generate-report-from-workflow")
async def generate_report_from_workflow(request: WorkflowReportRequest):
    try:
        result = await report_service.generate_report_from_workflow(
            workflow_data=request.workflow_data,
            report_queries=request.report_queries,
            project_id=request.project_id,
            natural_language_query=request.natural_language_query
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class WorkflowReportRequest(BaseModel):
    workflow_data: Union[Dict[str, Any], str]  # Dict or JSON string
    report_queries: List[Dict[str, Any]]
    project_id: str
    natural_language_query: Optional[str] = None
```

### Celery Integration
```python
from celery import Celery
from app.services.writers.report_service import create_report_service

celery_app = Celery('reports')

@celery_app.task
def generate_workflow_report_task(workflow_data, queries, project_id):
    report_service = create_report_service()
    return report_service.generate_report_from_workflow(
        workflow_data=workflow_data,
        report_queries=queries,
        project_id=project_id
    )
```

## 📁 File-Based Workflow Management

### Loading from JSON Files
```python
# Load workflow from file
workflow_file = "workflows/q4_sales_workflow.json"
result = await report_service.generate_report_from_workflow(
    workflow_data=workflow_file,
    report_queries=your_queries,
    project_id="q4_sales_report"
)
```

### Workflow File Structure
```json
{
    "id": "q4_sales_workflow",
    "state": "active",
    "workflow_metadata": {
        "report_title": "Q4 Sales Performance Report",
        "writer_actor": "EXECUTIVE_ANALYST",
        "business_goal": "STRATEGIC_DECISION_MAKING"
    },
    "thread_components": [...]
}
```

## 🚨 Error Handling

The service includes comprehensive error handling:

```python
try:
    result = await report_service.generate_report_from_workflow(
        workflow_data=workflow_data,
        report_queries=queries,
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

### Custom Workflow Processing
```python
# Override automatic detection
result = await report_service.generate_report_from_workflow(
    workflow_data=workflow_data,
    report_queries=queries,
    project_id="project_id",
    additional_context={
        "force_writer_actor": "PERFORMANCE_ANALYST",
        "force_business_goal": "PERFORMANCE_OPTIMIZATION"
    }
)
```

### Workflow Caching
```python
# The service automatically caches workflow data for performance
# Access cached workflows
cached_workflows = report_service._workflow_cache
```

## 📈 Performance Considerations

- **Lazy Loading**: Workflow models are only imported when needed
- **Caching**: Workflow data is cached for repeated use
- **Async Processing**: All operations are asynchronous for better performance
- **Memory Management**: Automatic cleanup of temporary data

## 🔍 Debugging and Monitoring

### Enable Debug Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Monitor Workflow Processing
```python
def detailed_status_callback(status: str, details: Dict[str, Any] = None):
    print(f"[{datetime.now()}] {status}: {details}")
    # Log to file, database, or monitoring system

result = await report_service.generate_report_from_workflow(
    workflow_data=workflow_data,
    report_queries=queries,
    project_id="project_id",
    status_callback=detailed_status_callback
)
```

## 🚀 Production Deployment

### Environment Configuration
```bash
# Set environment variables for production
export WORKFLOW_MODELS_PATH="/path/to/workflowservices"
export REPORT_SERVICE_LOG_LEVEL="INFO"
export REPORT_SERVICE_CACHE_SIZE="1000"
```

### Health Checks
```python
# Check service health
status = report_service.get_service_status()
workflow_status = status.get("workflow_integration", {})
print(f"Workflow Integration: {workflow_status.get('available', False)}")
```

## 🔄 Migration from Legacy Usage

If you're migrating from the previous report service:

```python
# Old way
result = await report_service.generate_comprehensive_report(
    report_queries=queries,
    project_id="project_id",
    report_context=context,
    report_template="executive_summary"
)

# New way with workflow
result = await report_service.generate_report_from_workflow(
    workflow_data=workflow_data,
    report_queries=queries,
    project_id="project_id"
)
```

## 📚 Additional Resources

- [Report Service Documentation](README_REPORT_SERVICE.md)
- [Workflow Models Reference](../workflowservices/app/models/workflowmodels.py)
- [Test Suite Examples](test_workflow_integration.py)
- [API Integration Guide](../docs/api_integration.md)

## 🤝 Contributing

When extending workflow integration:

1. Follow the existing pattern for new input formats
2. Add comprehensive error handling
3. Include status callbacks for new operations
4. Update the test suite
5. Document new features in this README

## 📄 License

This workflow integration is part of the GenieML platform and follows the project's licensing terms.

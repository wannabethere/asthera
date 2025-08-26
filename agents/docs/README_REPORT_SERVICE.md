# Report Service

The `ReportService` is a comprehensive service for generating reports using the `ReportOrchestratorPipeline`. It provides a clean interface for creating both simple and comprehensive reports with conditional formatting capabilities.

## Features

- **Comprehensive Report Generation**: Full-featured reports using the ReportOrchestratorPipeline
- **Simple Report Generation**: Basic reports without comprehensive components
- **Conditional Formatting**: Natural language-based formatting rules
- **Report Templates**: Predefined templates for common report types
- **Custom Components**: Support for custom report components
- **Status Callbacks**: Real-time progress monitoring
- **Validation**: Input validation and error handling
- **Execution History**: Track and analyze report generation history

## Architecture

The ReportService integrates with several key components:

- **ReportOrchestratorPipeline**: Main orchestration pipeline
- **ReportWritingAgent**: AI-powered report writing
- **PipelineContainer**: Access to other pipelines (conditional formatting, simple reports)
- **BaseService**: Common service functionality

## Quick Start

### Basic Usage

```python
from app.services.writers.report_service import create_report_service

# Create report service
report_service = create_report_service()

# Generate a comprehensive report
result = await report_service.generate_comprehensive_report(
    report_queries=your_queries,
    project_id="your_project",
    report_context=your_context,
    report_template="executive_summary"
)
```

### Simple Report

```python
# Generate a simple report
result = await report_service.generate_simple_report(
    report_queries=your_queries,
    project_id="your_project",
    report_context=your_context
)
```

### Conditional Formatting Only

```python
# Generate conditional formatting without executing queries
result = await report_service.generate_conditional_formatting_only(
    natural_language_query="Highlight sales above $100,000 in green",
    report_context=your_context,
    project_id="your_project"
)
```

## Report Templates

The service comes with several predefined templates:

### Executive Summary
- **Purpose**: High-level summary for executives and stakeholders
- **Components**: Executive overview, key metrics, trends analysis, recommendations
- **Writer Actor**: Executive Analyst
- **Business Goal**: Strategic Decision Making

### Detailed Analysis
- **Purpose**: Comprehensive analysis with detailed insights
- **Components**: Executive summary, methodology, detailed findings, data analysis, conclusions, appendix
- **Writer Actor**: Data Analyst
- **Business Goal**: Operational Insights

### Performance Review
- **Purpose**: Performance metrics and analysis report
- **Components**: Performance overview, KPI analysis, trends, benchmarks, action items
- **Writer Actor**: Performance Analyst
- **Business Goal**: Performance Optimization

### Trend Analysis
- **Purpose**: Analysis of trends and patterns over time
- **Components**: Trend overview, seasonal patterns, forecasting, drivers analysis, future outlook
- **Writer Actor**: Trend Analyst
- **Business Goal**: Trend Analysis

## Custom Templates

You can create custom report templates:

```python
custom_template = {
    "name": "Custom Sales Report",
    "description": "Custom template for sales analysis",
    "components": ["overview", "sales_analysis", "insights"],
    "writer_actor": "DATA_ANALYST",
    "business_goal": "OPERATIONAL_INSIGHTS"
}

# Add custom template
report_service.add_custom_template("custom_sales", custom_template)

# Use custom template
result = await report_service.generate_comprehensive_report(
    report_queries=your_queries,
    project_id="your_project",
    report_context=your_context,
    report_template="custom_sales"
)
```

## Input Data Structure

### Report Queries

```python
report_queries = [
    {
        "sql": "SELECT region, SUM(sales) as total_sales FROM sales_data GROUP BY region;",
        "query": "Show sales by region",
        "data_description": "Sales data aggregated by region"
    }
]
```

### Report Context

```python
report_context = {
    "title": "Q4 Sales Performance Report",
    "description": "Comprehensive analysis of Q4 sales performance",
    "sections": ["executive_summary", "regional_analysis", "recommendations"],
    "available_columns": ["date", "region", "sales", "profit"],
    "data_types": {
        "date": "datetime",
        "region": "categorical",
        "sales": "numeric",
        "profit": "numeric"
    }
}
```

### Natural Language Query

```python
natural_language_query = """
Highlight regions with sales above $100,000 in green and below $50,000 in red.
Filter performance data to show only scores above 75.
Emphasize categories with profit margins above 20%.
"""
```

## Status Callbacks

Monitor progress with status callbacks:

```python
def status_callback(status: str, details: Dict[str, Any] = None):
    print(f"Status: {status} - {details}")

result = await report_service.generate_comprehensive_report(
    report_queries=your_queries,
    project_id="your_project",
    report_context=your_context,
    status_callback=status_callback
)
```

Common status updates:
- `report_generation_started`
- `conditional_formatting_started`
- `conditional_formatting_completed`
- `simple_report_generation_started`
- `simple_report_generation_completed`
- `report_generation_completed`

## Validation

Validate your configuration before generating reports:

```python
validation = report_service.validate_report_configuration(
    report_queries=your_queries,
    report_context=your_context,
    natural_language_query=your_query
)

if validation["valid"]:
    print("Configuration is valid!")
else:
    print(f"Issues found: {validation['issues']}")
    print(f"Warnings: {validation['warnings']}")
```

## Service Status

Check the status of all components:

```python
status = report_service.get_service_status()
print(f"Report Orchestrator: {status['report_orchestrator']['available']}")
print(f"Available Templates: {status['report_templates']['available_templates']}")
print(f"Pipeline Count: {status['pipeline_container']['pipeline_count']}")
```

## Execution History

Track report generation history:

```python
# Get recent history
history = report_service.get_execution_history(limit=10)

for entry in history:
    print(f"Project: {entry['project_id']}")
    print(f"Template: {entry['report_template']}")
    print(f"Success: {entry['success']}")
    print(f"Timestamp: {entry['timestamp']}")
```

## Error Handling

The service includes comprehensive error handling:

```python
try:
    result = await report_service.generate_comprehensive_report(
        report_queries=your_queries,
        project_id="your_project",
        report_context=your_context
    )
except RuntimeError as e:
    print(f"Service not available: {e}")
except ValueError as e:
    print(f"Invalid input: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Configuration

### Pipeline Configuration

```python
configuration = {
    "enable_conditional_formatting": True,
    "enable_report_generation": True,
    "enable_validation": True,
    "max_report_iterations": 3,
    "quality_threshold": 0.8
}

result = await report_service.generate_comprehensive_report(
    report_queries=your_queries,
    project_id="your_project",
    report_context=your_context,
    configuration=configuration
)
```

### Time Filters

```python
time_filters = {
    "period": "last_quarter",
    "start_date": "2024-01-01",
    "end_date": "2024-03-31"
}
```

## Integration Examples

### With FastAPI

```python
from fastapi import FastAPI, HTTPException
from app.services.writers.report_service import create_report_service

app = FastAPI()
report_service = create_report_service()

@app.post("/generate-report")
async def generate_report(request: ReportRequest):
    try:
        result = await report_service.generate_comprehensive_report(
            report_queries=request.queries,
            project_id=request.project_id,
            report_context=request.context,
            report_template=request.template
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### With Celery

```python
from celery import Celery
from app.services.writers.report_service import create_report_service

celery_app = Celery('reports')

@celery_app.task
def generate_report_task(queries, project_id, context, template):
    report_service = create_report_service()
    return report_service.generate_comprehensive_report(
        report_queries=queries,
        project_id=project_id,
        report_context=context,
        report_template=template
    )
```

## Testing

Run the test suite to verify functionality:

```bash
cd agents/app/services/writers
python test_report_service.py
```

The test suite covers:
- Basic functionality
- Report templates
- Simple report generation
- Conditional formatting
- Comprehensive report generation
- Execution history

## Performance Considerations

- **Concurrent Execution**: The service supports concurrent query execution
- **Caching**: Configuration and results are cached for performance
- **Streaming**: Intermediate results can be streamed for large reports
- **Resource Management**: Automatic cleanup of execution history

## Troubleshooting

### Common Issues

1. **Service Not Available**: Check if all required pipelines are initialized
2. **Template Not Found**: Verify template name exists in available templates
3. **Validation Errors**: Check input data structure and required fields
4. **Pipeline Errors**: Review pipeline container initialization

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Service Status Check

```python
status = report_service.get_service_status()
print(status)
```

## Dependencies

- `ReportOrchestratorPipeline`: Main orchestration
- `ReportWritingAgent`: AI report writing
- `PipelineContainer`: Pipeline management
- `BaseService`: Common service functionality
- `Engine`: Database engine (optional)

## Contributing

When extending the ReportService:

1. Follow the existing pattern for new methods
2. Add comprehensive error handling
3. Include status callbacks for new operations
4. Update the test suite
5. Document new features in this README

## License

This service is part of the GenieML platform and follows the project's licensing terms.

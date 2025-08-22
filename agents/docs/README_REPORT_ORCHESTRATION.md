# Report Orchestrator Pipeline

This module provides a comprehensive report generation system that orchestrates between conditional formatting generation and report writing, similar to the dashboard orchestrator but focused on report generation.

## Overview

The Report Orchestrator Pipeline coordinates three main components:

1. **Conditional Formatting Generation** - Applies intelligent formatting rules to report data
2. **Simple Report Generation** - Executes SQL queries and generates basic reports with insights
3. **Comprehensive Report Writing** - Uses the Report Writing Agent for advanced report generation

## Architecture

```
Report Orchestrator Pipeline
├── Conditional Formatting Generation Pipeline
├── Simple Report Generation Pipeline
└── Report Writing Agent
    ├── Self-Correcting RAG System
    ├── Content Quality Evaluator
    └── Business Goal Integration
```

## Components

### 1. Report Orchestrator Pipeline (`report_orchestrator_pipeline.py`)

The main orchestrator that coordinates all report generation activities.

**Key Features:**
- Conditional formatting generation
- Simple report generation
- Comprehensive report writing
- Status tracking and metrics
- Configurable execution flow

**Configuration Options:**
```python
{
    "enable_conditional_formatting": True,
    "enable_report_generation": True,
    "enable_validation": True,
    "enable_metrics": True,
    "max_report_iterations": 3,
    "quality_threshold": 0.8
}
```

### 2. Simple Report Generation Pipeline (`simple_report_generation_pipeline.py`)

A streamlined pipeline for basic report generation from SQL queries.

**Key Features:**
- SQL query execution
- Conditional formatting application
- Data insights generation
- Recommendations generation
- Report compilation

**Configuration Options:**
```python
{
    "max_retry_attempts": 3,
    "timeout_seconds": 60,
    "enable_caching": True,
    "cache_ttl_seconds": 3600,
    "enable_validation": True,
    "enable_optimization": True,
    "max_rows_per_query": 10000,
    "enable_data_summarization": True,
    "enable_insight_generation": True,
    "enable_recommendations": True
}
```

## Usage

### Basic Setup

```python
from app.agents.pipelines.writers.report_orchestrator_pipeline import create_report_orchestrator_pipeline
from app.core.engine import Engine
from app.core.dependencies import get_llm

# Create the pipeline
pipeline = create_report_orchestrator_pipeline(
    engine=engine,
    llm=get_llm()
)
```

### Basic Report Generation

```python
# Sample report queries
report_queries = [
    {
        "id": "query_1",
        "name": "Sales Performance",
        "sql": "SELECT department, SUM(sales) as total FROM sales GROUP BY department"
    }
]

# Report context
report_context = {
    "title": "Sales Report",
    "description": "Department sales performance analysis"
}

# Execute pipeline
result = await pipeline.run(
    report_queries=report_queries,
    natural_language_query=None,  # No conditional formatting
    report_context=report_context,
    project_id="project_001"
)
```

### Enhanced Report Generation with Conditional Formatting

```python
# Natural language query for conditional formatting
conditional_formatting_query = """
Apply conditional formatting to the sales data:
- Highlight sales above $100,000 in green
- Format currency values with 2 decimal places
- Apply bold formatting to department names
"""

result = await pipeline.run(
    report_queries=report_queries,
    natural_language_query=conditional_formatting_query,
    report_context=report_context,
    project_id="project_002"
)
```

### Comprehensive Report Generation

```python
from app.agents.nodes.writers.report_writing_agent import (
    ThreadComponentData, 
    WriterActorType, 
    BusinessGoal,
    ComponentType
)

# Thread components for comprehensive report
thread_components = [
    ThreadComponentData(
        id="comp_1",
        component_type=ComponentType.QUESTION,
        sequence_order=1,
        question="What are the key performance indicators?",
        description="Analysis of performance metrics"
    )
]

# Business goal
business_goal = BusinessGoal(
    primary_objective="Improve sales performance",
    target_audience=["Executives", "Managers"],
    decision_context="Q4 planning",
    success_metrics=["Sales growth", "Performance improvement"],
    timeframe="Q4 2024"
)

result = await pipeline.run(
    report_queries=report_queries,
    natural_language_query=conditional_formatting_query,
    report_context=report_context,
    project_id="project_003",
    thread_components=thread_components,
    writer_actor=WriterActorType.EXECUTIVE,
    business_goal=business_goal
)
```

## Configuration

### Pipeline Configuration

```python
# Update configuration
pipeline.update_configuration({
    "quality_threshold": 0.9,
    "max_report_iterations": 5
})

# Enable/disable features
pipeline.enable_conditional_formatting(False)
pipeline.enable_report_generation(True)
pipeline.set_quality_threshold(0.85)
```

### Status Callbacks

```python
def status_callback(status: str, details: Dict[str, Any]):
    print(f"Status: {status}")
    print(f"Details: {details}")

result = await pipeline.run(
    # ... other parameters ...
    status_callback=status_callback
)
```

## Output Structure

### Basic Response

```python
{
    "post_process": {
        "success": True,
        "report": {
            "report_id": "report_project_001_20241201_143022",
            "project_id": "project_001",
            "summary": {
                "total_queries": 1,
                "successful_queries": 1,
                "total_rows_processed": 150,
                "insights_generated": 2,
                "recommendations_generated": 1
            },
            "query_results": {...},
            "insights": [...],
            "recommendations": [...]
        },
        "enhanced_context": {...},
        "orchestration_metadata": {...}
    },
    "metadata": {...}
}
```

### Enhanced Response with Conditional Formatting

```python
{
    "post_process": {
        "success": True,
        "report": {...},
        "enhanced_context": {
            "conditional_formatting_rules": {
                "sales_amount": {
                    "type": "conditional_color",
                    "conditions": [
                        {"operator": "greater_than", "threshold": 100000, "color": "green"},
                        {"operator": "less_than", "threshold": 50000, "color": "red"}
                    ]
                }
            }
        },
        "orchestration_metadata": {
            "conditional_formatting_applied": True
        }
    }
}
```

### Comprehensive Response

```python
{
    "post_process": {
        "success": True,
        "report": {...},
        "enhanced_context": {...},
        "comprehensive_report": {
            "report_outline": {...},
            "final_content": {...},
            "quality_assessment": {...},
            "correction_history": [...]
        },
        "orchestration_metadata": {
            "conditional_formatting_applied": True,
            "comprehensive_report_generated": True
        }
    }
}
```

## Metrics and Monitoring

### Execution Statistics

```python
stats = pipeline.get_execution_statistics()
print(f"Total executions: {stats['pipeline_metrics']['total_executions']}")
print(f"Average execution time: {stats['pipeline_metrics']['average_execution_time']}")
```

### Pipeline Metrics

```python
metrics = pipeline.get_metrics()
print(f"Last execution: {metrics['last_execution']}")
print(f"Total queries processed: {metrics['total_queries_processed']}")
```

## Error Handling

The pipeline includes comprehensive error handling:

- Input validation
- SQL execution error handling
- Conditional formatting error handling
- Report generation error handling
- Status callback error handling
- Metrics tracking for errors

## Example Usage

See `example_report_orchestration.py` for a complete demonstration of:

1. Basic report generation
2. Enhanced report generation with conditional formatting
3. Comprehensive report generation with all features
4. Pipeline configuration demonstration

## Dependencies

- `app.agents.pipelines.base.AgentPipeline`
- `app.agents.retrieval.retrieval_helper.RetrievalHelper`
- `app.core.engine.Engine`
- `app.core.dependencies.get_llm`
- `app.agents.nodes.writers.report_writing_agent.*`
- `app.agents.pipelines.writers.conditional_formatting_generation_pipeline.ConditionalFormattingGenerationPipeline`

## Best Practices

1. **Always provide a project_id** for tracking and debugging
2. **Use status callbacks** for monitoring long-running operations
3. **Configure quality thresholds** based on your requirements
4. **Handle errors gracefully** and check success flags in responses
5. **Monitor metrics** for performance optimization
6. **Use appropriate writer actors** for different report types
7. **Define clear business goals** for comprehensive reports

## Troubleshooting

### Common Issues

1. **Pipeline not initialized**: Ensure the pipeline is properly initialized before running
2. **Missing dependencies**: Check that all required components are available
3. **SQL execution errors**: Verify SQL syntax and database connectivity
4. **Conditional formatting failures**: Ensure natural language queries are clear and specific
5. **Report generation timeouts**: Adjust timeout settings for large datasets

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Future Enhancements

- **Caching**: Implement result caching for improved performance
- **Parallel Processing**: Add support for parallel query execution
- **Advanced Formatting**: Support for more complex conditional formatting rules
- **Report Templates**: Pre-defined report templates for common use cases
- **Export Formats**: Support for PDF, Excel, and other export formats

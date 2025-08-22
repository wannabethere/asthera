# Dashboard Conditional Formatting Service

A comprehensive service for translating natural language queries into dashboard conditional formatting configurations using LangChain agents with RAG capabilities.

## Overview

This service enables users to apply conditional formatting and control filters to dashboard charts through natural language queries. It integrates seamlessly with your existing SQL and chart generation pipelines, providing intelligent configuration generation with self-evaluation and historical learning capabilities.

## Key Features

- **Natural Language Processing**: Convert plain English queries into structured conditional formatting rules
- **RAG-Based Learning**: Learn from historical configurations and improve suggestions over time
- **Self-Evaluation**: Built-in validation and improvement of generated configurations
- **Multi-Chart Support**: Apply formatting across multiple charts in a dashboard
- **Pipeline Integration**: Seamless integration with existing SQL expansion and chart adjustment pipelines
- **Multiple Filter Types**: Support for column filters, time filters, conditional formatting, and aggregation filters
- **Action Tags**: Generate configuration tags that specify which pipelines to execute

## Architecture

### Core Components

1. **ConditionalFormattingAgent**: LangChain agent that processes natural language queries
2. **DashboardConditionalFormattingService**: Main service coordinating all components
3. **ConditionalFormattingRetriever**: RAG component for historical configuration retrieval
4. **ConditionalFormattingPipeline**: Pipeline integration for existing architecture
5. **EnhancedDashboardService**: Extended dashboard service with conditional formatting

### Data Models

- **ControlFilter**: Individual filter configuration
- **ConditionalFormat**: Chart-specific formatting rules
- **DashboardConfiguration**: Complete dashboard configuration
- **FilterOperator**: Enumeration of supported operators
- **FilterType**: Types of filters (column, time, conditional, etc.)
- **ActionType**: Pipeline actions (SQL expansion, chart adjustment, both)

## Installation and Setup

### Dependencies

```python
# Core dependencies
from langchain.agents import Tool, AgentExecutor, create_openai_functions_agent
from langchain.prompts import PromptTemplate, ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langfuse.decorators import observe

# Your existing pipeline dependencies
from app.agents.pipelines.base import AgentPipeline
from app.agents.retrieval.retrieval_helper import RetrievalHelper
from app.core.dependencies import get_llm, get_doc_store_provider
```

### Basic Setup

```python
from dashboard_conditional_formatting import create_conditional_formatting_service
from dashboard_integration import EnhancedDashboardService, add_conditional_formatting_to_pipeline_container

# Initialize the service
service = create_conditional_formatting_service()

# Add to existing pipeline container
container = PipelineContainer.initialize()
add_conditional_formatting_to_pipeline_container(container)

# Create enhanced dashboard service
enhanced_service = EnhancedDashboardService(
    pipeline_container=container,
    conditional_formatting_service=service
)
```

## Usage Examples

### Basic Conditional Formatting

```python
# Dashboard context describing your charts and data
dashboard_context = {
    "charts": [
        {
            "chart_id": "sales_chart",
            "type": "bar",
            "columns": ["region", "sales_amount", "date"],
            "query": "Show sales by region"
        }
    ],
    "available_columns": ["region", "sales_amount", "date", "status"],
    "data_types": {
        "sales_amount": "numeric",
        "date": "datetime",
        "region": "categorical",
        "status": "categorical"
    }
}

# Natural language query
query = "Highlight sales amounts greater than $100,000 in green and filter to show only active status"

# Process the request
result = await service.process_conditional_formatting_request(
    query=query,
    dashboard_context=dashboard_context,
    project_id="my_project"
)

# Result contains:
# - configuration: Complete DashboardConfiguration object
# - chart_configurations: Dict with SQL expansion and chart adjustment configs
# - success: Boolean indicating success/failure
# - metadata: Processing metadata
```

### Time-Based Filtering

```python
query = "Show only data from the last 30 days and highlight current month values"

time_filters = {
    "period": "last_30_days",
    "highlight_current": True
}

result = await service.process_conditional_formatting_request(
    query=query,
    dashboard_context=dashboard_context,
    project_id="my_project",
    time_filters=time_filters
)
```

### Complex Multi-Condition Formatting

```python
query = """
For the sales dashboard:
1. Highlight sales > $200K in dark green with bold font
2. Highlight sales between $100K-200K in light green
3. Filter to show only top 5 regions by performance
4. Show only data from Q4 2024
5. Highlight achievement rates above 120% in blue
"""

additional_context = {
    "performance_thresholds": {
        "excellent": 200000,
        "good": 100000,
        "achievement_target": 120
    },
    "formatting_preferences": {
        "high_performance_color": "dark_green",
        "medium_performance_color": "light_green"
    }
}

result = await service.process_conditional_formatting_request(
    query=query,
    dashboard_context=dashboard_context,
    project_id="my_project",
    additional_context=additional_context
)
```

### Integration with Dashboard Streaming

```python
# Dashboard queries for execution
dashboard_queries = [
    {
        "chart_id": "sales_chart",
        "sql": "SELECT region, SUM(sales_amount) as sales FROM sales_data GROUP BY region",
        "query": "Show sales by region",
        "data_description": "Sales data by region"
    },
    {
        "chart_id": "performance_chart",
        "sql": "SELECT date, performance_score FROM performance_data ORDER BY date",
        "query": "Show performance over time", 
        "data_description": "Performance trends"
    }
]

# Natural language formatting query
formatting_query = "Highlight high performance values and filter recent data"

# Process complete dashboard with conditional formatting
result = await enhanced_service.process_dashboard_with_conditional_formatting(
    natural_language_query=formatting_query,
    dashboard_queries=dashboard_queries,
    project_id="my_project",
    dashboard_context=dashboard_context,
    status_callback=lambda status, details: print(f"Status: {status}")
)
```

## Configuration Output Format

The service generates configurations that specify exactly which pipelines should be executed and how:

```json
{
    "success": true,
    "configuration": {
        "dashboard_id": "dashboard_123",
        "filters": [
            {
                "filter_id": "filter_1",
                "filter_type": "column_filter",
                "column_name": "status",
                "operator": "equals",
                "value": "active"
            }
        ],
        "conditional_formats": [
            {
                "format_id": "format_1",
                "chart_id": "sales_chart",
                "condition": {
                    "column_name": "sales_amount",
                    "operator": "greater_than",
                    "value": 100000
                },
                "formatting_rules": {
                    "color": "green",
                    "font_weight": "bold"
                }
            }
        ]
    },
    "chart_configurations": {
        "sales_chart": {
            "chart_id": "sales_chart",
            "sql_expansion": {
                "where_conditions": ["status = 'active'"],
                "time_filters": {"period": "last_30_days"}
            },
            "chart_adjustment": {
                "adjustment_type": "conditional_format",
                "formatting": {"color": "green", "font_weight": "bold"}
            },
            "actions": ["sql_expansion", "chart_adjustment"]
        }
    }
}
```

## Supported Filter Operators

- **equals, not_equals**: Exact matching
- **greater_than, less_than, greater_equal, less_equal**: Numeric comparisons
- **contains, not_contains**: Text substring matching
- **starts_with, ends_with**: Text prefix/suffix matching
- **in, not_in**: List membership
- **between**: Range queries
- **is_null, is_not_null**: Null value handling
- **regex**: Regular expression matching

## Filter Types

- **column_filter**: Standard column-based filtering
- **time_filter**: Date/time-based filtering
- **conditional_format**: Visual formatting based on conditions
- **aggregation_filter**: Filtering on aggregated values
- **custom_filter**: Custom SQL conditions

## Action Types

The service generates action tags that specify which pipelines to execute:

- **sql_expansion**: Modify SQL queries to include filter conditions
- **chart_adjustment**: Modify chart appearance and formatting
- **both**: Execute both SQL expansion and chart adjustment

## RAG and Self-Evaluation

### Historical Learning

The service learns from previous configurations through RAG:

```python
# Configurations are automatically stored for future retrieval
await service.process_conditional_formatting_request(query, context, project_id)

# Similar configurations are retrieved for reference
similar_configs = await retriever.retrieve_similar_configurations(
    query="highlight sales performance",
    project_id=project_id
)
```

### Self-Evaluation Tools

The LangChain agent includes tools for self-evaluation:

1. **get_filter_examples**: Retrieve examples of specific filter types
2. **get_similar_configurations**: Find similar historical configurations
3. **validate_configuration**: Validate generated configurations

## Testing and Benchmarking

### Running Test Cases

```python
from conditional_formatting_examples import ConditionalFormattingBenchmarks

# Initialize benchmarks
benchmarks = ConditionalFormattingBenchmarks()

# Run all test cases
results = await benchmarks.run_all_test_cases()

# Generate performance report
report = benchmarks.generate_performance_report(results)
print(report)
```

### Available Test Cases

1. **basic_highlighting**: Simple value-based highlighting
2. **time_based_filtering**: Time range and period filtering
3. **performance_thresholds**: Multi-tier performance highlighting
4. **financial_variance**: Financial variance analysis formatting
5. **categorical_filtering**: Category-based filtering and highlighting
6. **complex_multi_condition**: Complex multi-condition scenarios

## Integration with Existing Pipelines

### Pipeline Container Integration

```python
# Add conditional formatting to existing pipeline container
container = PipelineContainer.initialize()
service = add_conditional_formatting_to_pipeline_container(container)

# Access conditional formatting pipeline
cf_pipeline = container.get_pipeline("conditional_formatting")
```

### Direct Pipeline Usage

```python
# Create conditional formatting pipeline directly
cf_pipeline = ConditionalFormattingPipeline(
    llm=get_llm(),
    retrieval_helper=RetrievalHelper(),
    document_store_provider=get_doc_store_provider()
)

# Run the pipeline
result = await cf_pipeline.run(
    query=natural_language_query,
    dashboard_context=dashboard_context,
    project_id=project_id
)
```

## Status Callbacks and Monitoring

The service provides detailed status updates throughout processing:

```python
def status_callback(status: str, details: Dict[str, Any]):
    print(f"Status: {status}")
    print(f"Details: {details}")

# Status events include:
# - processing_started
# - conditional_formatting_started
# - conditional_formatting_completed
# - dashboard_execution_started
# - chart_adjustments_started
# - processing_completed
# - Various error states

result = await enhanced_service.process_dashboard_with_conditional_formatting(
    natural_language_query=query,
    dashboard_queries=queries,
    project_id=project_id,
    dashboard_context=context,
    status_callback=status_callback
)
```

## Performance Considerations

### Optimization Tips

1. **Cache Configurations**: Use the built-in configuration cache for repeated queries
2. **Batch Processing**: Process multiple charts in parallel when possible
3. **Context Reuse**: Reuse dashboard context across similar queries
4. **Filter Scope**: Be specific about which charts need formatting to reduce processing

### Monitoring Metrics

```python
# Get service metrics
history = service.get_configuration_history(limit=10)
cache_stats = service._configuration_cache.keys()

# Clear cache when needed
service.clear_cache()
```

## Error Handling

The service provides comprehensive error handling:

```python
try:
    result = await service.process_conditional_formatting_request(...)
    
    if not result["success"]:
        error = result.get("error", "Unknown error")
        print(f"Configuration failed: {error}")
    
except Exception as e:
    print(f"Service error: {e}")
```

## Extending the Service

### Adding Custom Filter Operators

```python
class CustomFilterOperator(Enum):
    CUSTOM_OPERATOR = "custom_operator"

# Extend ControlFilter.to_sql_condition() method
def custom_to_sql_condition(self) -> str:
    if self.operator == CustomFilterOperator.CUSTOM_OPERATOR:
        return f"CUSTOM_FUNCTION({self.column_name}, '{self.value}')"
    return original_to_sql_condition(self)
```

### Adding Custom Tools

```python
class CustomTool(BaseTool):
    name = "custom_validation"
    description = "Custom validation logic"
    
    def _run(self, config: str) -> str:
        # Custom validation logic
        return "validation_result"

# Add to agent tools
agent.tools.append(CustomTool())
```

## Best Practices

1. **Clear Context**: Provide comprehensive dashboard context with column types
2. **Specific Queries**: Be specific in natural language queries for better results
3. **Incremental Testing**: Start with simple cases and build complexity
4. **Monitor Performance**: Use benchmarking to track service performance
5. **Cache Management**: Regularly clean cache for optimal performance

## Troubleshooting

### Common Issues

1. **Invalid Configuration**: Check dashboard context structure and column names
2. **SQL Generation Errors**: Verify column names and data types in context
3. **Agent Timeout**: Increase timeout for complex queries
4. **Memory Issues**: Clear cache and history for long-running services

### Debug Mode

Enable detailed logging for troubleshooting:

```python
import logging
logging.getLogger("lexy-ai-service").setLevel(logging.DEBUG)
```

## API Reference

### Main Service Methods

- `process_conditional_formatting_request()`: Main processing method
- `get_configuration_history()`: Retrieve processing history
- `clear_cache()`: Clear configuration cache

### Pipeline Integration

- `ConditionalFormattingPipeline.run()`: Execute pipeline directly
- `EnhancedDashboardService.process_dashboard_with_conditional_formatting()`: Full dashboard processing

### Utility Functions

- `ConditionalFormattingUtils.validate_dashboard_context()`: Validate context structure
- `ConditionalFormattingUtils.generate_sample_dashboard_context()`: Create test context
- `create_conditional_formatting_service()`: Factory function for service creation

---

For more examples and advanced usage, see the test cases in `conditional_formatting_examples.py`.
# Enhanced Dashboard System

A comprehensive dashboard system that combines streaming SQL execution with intelligent conditional formatting capabilities.

## 🏗️ Architecture Overview

The enhanced dashboard system is built with a clean separation of concerns, following these principles:

- **Services**: Handle business logic and data processing
- **Pipelines**: Manage execution flow and orchestration
- **Models**: Define data structures and configurations
- **Orchestrators**: Coordinate between different components

## 📁 File Structure

```
writers/
├── __init__.py                           # Module exports
├── dashboard_models.py                   # Data models and enums
├── dashboard_retriever.py                # Retrieval service for historical data
├── dashboard_agent.py                    # LangChain agent for conditional formatting
├── dashboard_service.py                  # Core conditional formatting service
├── dashboard_pipeline.py                 # Basic conditional formatting pipeline
├── dashboard_factory.py                  # Factory functions for creating instances
├── enhanced_dashboard_pipeline.py        # Combined streaming + conditional formatting pipeline
├── dashboard_orchestrator.py             # High-level orchestration service
├── dashboard_examples.py                 # Comprehensive usage examples
└── README_ENHANCED_DASHBOARD.md         # This file
```

## 🚀 Key Components

### 1. Enhanced Dashboard Pipeline (`enhanced_dashboard_pipeline.py`)

**Purpose**: Combines streaming SQL execution with conditional formatting in a single pipeline.

**Features**:
- Concurrent SQL query execution
- Real-time streaming of results
- Conditional formatting integration
- SQL query expansion based on natural language
- Chart adjustment capabilities
- Configurable execution options

**Usage**:
```python
from .enhanced_dashboard_pipeline import create_enhanced_dashboard_pipeline

pipeline = create_enhanced_dashboard_pipeline(engine)
result = await pipeline.run(
    queries=dashboard_queries,
    natural_language_query="Highlight sales > $1000 in green",
    dashboard_context=dashboard_context,
    project_id="my_project"
)
```

### 2. Dashboard Orchestrator (`dashboard_orchestrator.py`)

**Purpose**: High-level service that coordinates all dashboard operations.

**Features**:
- Unified interface for all dashboard operations
- Configuration validation
- Execution history tracking
- Service status monitoring
- Flexible execution modes

**Usage**:
```python
from .dashboard_orchestrator import create_dashboard_orchestrator

orchestrator = create_dashboard_orchestrator()

# Execute with conditional formatting
result = await orchestrator.execute_dashboard_with_conditional_formatting(
    dashboard_queries=queries,
    natural_language_query=formatting_query,
    dashboard_context=context,
    project_id="my_project"
)

# Execute without conditional formatting
result = await orchestrator.execute_dashboard_only(
    dashboard_queries=queries,
    project_id="my_project"
)
```

### 3. Conditional Formatting Service (`dashboard_service.py`)

**Purpose**: Processes natural language queries into structured formatting configurations.

**Features**:
- Natural language to configuration translation
- Historical configuration retrieval
- Configuration caching
- Chart-specific formatting rules

**Usage**:
```python
from .dashboard_service import DashboardConditionalFormattingService

service = DashboardConditionalFormattingService(llm, retrieval_helper, doc_store)
result = await service.process_conditional_formatting_request(
    query="Highlight high sales in green",
    dashboard_context=context,
    project_id="my_project"
)
```

### 4. Data Models (`dashboard_models.py`)

**Purpose**: Define the structure for filters, formatting rules, and configurations.

**Key Classes**:
- `FilterOperator`: Enum for filter operations (equals, greater_than, contains, etc.)
- `FilterType`: Enum for filter types (column_filter, time_filter, etc.)
- `ControlFilter`: Individual filter configuration
- `ConditionalFormat`: Chart formatting rules
- `DashboardConfiguration`: Complete dashboard configuration

## 🔧 Configuration Options

### Enhanced Dashboard Pipeline Configuration

```python
pipeline_config = {
    "concurrent_execution": True,           # Enable concurrent query execution
    "max_concurrent_queries": 5,           # Maximum concurrent queries
    "timeout_per_query": 30,               # Timeout per query in seconds
    "stream_intermediate_results": True,    # Stream results as they complete
    "continue_on_error": True,             # Continue execution on query failure
    "enable_conditional_formatting": True,  # Enable conditional formatting
    "enable_chart_adjustments": True,      # Enable chart adjustments
    "max_retries": 3,                      # Maximum retry attempts
    "retry_delay": 1.0                     # Delay between retries
}
```

### Conditional Formatting Configuration

```python
time_filters = {
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "period": "current_year"  # or "last_30_days", "last_quarter"
}

additional_context = {
    "user_preferences": {
        "highlight_color": "green",
        "default_period": "last_30_days"
    },
    "user_id": "user123"
}
```

## 📊 Usage Examples

### Example 1: Basic Dashboard Execution

```python
from .dashboard_orchestrator import create_dashboard_orchestrator

orchestrator = create_dashboard_orchestrator()

# Execute dashboard queries
result = await orchestrator.execute_dashboard_only(
    dashboard_queries=[
        {
            "chart_id": "sales_chart",
            "sql": "SELECT region, SUM(sales) FROM sales_data GROUP BY region;",
            "query": "Show sales by region",
            "project_id": "my_project"
        }
    ],
    project_id="my_project"
)
```

### Example 2: Dashboard with Conditional Formatting

```python
# Execute with conditional formatting
result = await orchestrator.execute_dashboard_with_conditional_formatting(
    dashboard_queries=dashboard_queries,
    natural_language_query="""
        Highlight all sales amounts greater than $50,000 in green.
        Filter to show only data from the last quarter.
        Make the performance chart show only scores above 80.
    """,
    dashboard_context=dashboard_context,
    project_id="my_project",
    time_filters={"period": "last_quarter"}
)
```

### Example 3: Status Callback for Streaming

```python
def status_callback(status: str, details: Dict[str, Any]):
    print(f"Status: {status} - {details}")

result = await orchestrator.execute_dashboard_with_conditional_formatting(
    dashboard_queries=dashboard_queries,
    natural_language_query=formatting_query,
    dashboard_context=dashboard_context,
    project_id="my_project",
    status_callback=status_callback
)
```

## 🔍 Status Updates

The system provides comprehensive status updates through callbacks:

- `enhanced_dashboard_started`: Pipeline execution started
- `conditional_formatting_started`: Conditional formatting processing started
- `conditional_formatting_completed`: Conditional formatting completed
- `sql_expansion_applied`: SQL query expansion applied
- `dashboard_execution_started`: Dashboard queries execution started
- `query_execution_started`: Individual query execution started
- `query_execution_completed`: Individual query completed
- `query_result_available`: Query result available for streaming
- `chart_adjustments_started`: Chart adjustments started
- `chart_adjustments_completed`: Chart adjustments completed
- `enhanced_dashboard_completed`: Complete pipeline execution finished

## 🧪 Testing and Examples

Run the comprehensive examples:

```python
from .dashboard_examples import run_all_examples

# Run all examples
results = await run_all_examples()

# Run specific examples
from .dashboard_examples import example_basic_conditional_formatting
result = await example_basic_conditional_formatting()
```

## 🔧 Integration with Existing Systems

### Pipeline Container Integration

```python
from app.agents.pipelines.pipeline_container import PipelineContainer
from .dashboard_orchestrator import create_dashboard_orchestrator

# Initialize pipeline container
container = PipelineContainer.initialize()

# Create orchestrator with existing container
orchestrator = create_dashboard_orchestrator(
    pipeline_container=container
)
```

### Engine Provider Integration

```python
from app.core.engine_provider import EngineProvider
from .enhanced_dashboard_pipeline import create_enhanced_dashboard_pipeline

# Get engine from provider
engine = EngineProvider.get_engine()

# Create pipeline with engine
pipeline = create_enhanced_dashboard_pipeline(engine=engine)
```

## 📈 Performance Features

- **Concurrent Execution**: Execute multiple queries simultaneously
- **Streaming Results**: Get results as they complete
- **Caching**: Cache conditional formatting configurations
- **Retry Logic**: Automatic retry for failed queries
- **Timeout Management**: Configurable timeouts per query
- **Error Handling**: Graceful error handling with continue-on-error option

## 🔒 Error Handling

The system provides comprehensive error handling:

- **Query-level Errors**: Individual query failures don't stop the entire pipeline
- **Configuration Validation**: Pre-execution validation of all inputs
- **Graceful Degradation**: Fallback to basic execution if conditional formatting fails
- **Detailed Error Reporting**: Comprehensive error information in results
- **Status Callbacks**: Real-time error notifications through callbacks

## 📚 Advanced Features

### SQL Query Expansion

The system can automatically expand SQL queries based on natural language instructions:

```python
# Original SQL
"SELECT region, sales FROM sales_data"

# After expansion with "Show only active status records"
"SELECT region, sales FROM sales_data WHERE status = 'active'"
```

### Time-based Filtering

Automatic time filter application:

```python
time_filters = {"period": "last_30_days"}

# Automatically adds to SQL:
# WHERE date >= CURRENT_DATE - INTERVAL '30 days'
```

### Chart Adjustments

Apply visual formatting to charts:

```python
# Natural language: "Highlight high sales in green"
chart_adjustment = {
    "adjustment_type": "conditional_format",
    "condition": {"column": "sales", "operator": "greater_than", "value": 1000},
    "formatting": {"color": "green", "font_weight": "bold"}
}
```

## 🚀 Getting Started

1. **Import the components**:
   ```python
   from agents.app.agents.nodes.writers import (
       create_dashboard_orchestrator,
       DashboardExamples
   )
   ```

2. **Create an orchestrator**:
   ```python
   orchestrator = create_dashboard_orchestrator()
   ```

3. **Prepare your data**:
   ```python
   dashboard_queries = DashboardExamples.generate_sample_dashboard_queries()
   dashboard_context = DashboardExamples.generate_sample_dashboard_context()
   ```

4. **Execute with conditional formatting**:
   ```python
   result = await orchestrator.execute_dashboard_with_conditional_formatting(
       dashboard_queries=dashboard_queries,
       natural_language_query="Highlight high sales in green",
       dashboard_context=dashboard_context,
       project_id="my_project"
   )
   ```

## 🔮 Future Enhancements

- **AI-powered Query Optimization**: Automatic SQL query optimization
- **Advanced Chart Types**: Support for more chart types and visualizations
- **Real-time Data Streaming**: Live data updates and streaming
- **Collaborative Dashboards**: Multi-user dashboard editing
- **Advanced Analytics**: Built-in statistical analysis and insights
- **Mobile Optimization**: Responsive dashboard design for mobile devices

## 📞 Support

For questions or issues with the enhanced dashboard system:

1. Check the examples in `dashboard_examples.py`
2. Review the configuration options
3. Check the status callbacks for execution progress
4. Validate your inputs using the validation methods

The system is designed to be robust and provide clear feedback on any issues encountered.

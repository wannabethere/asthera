# SQL Summary Thread Component Integration

This document describes the integration between SQL summary functionality and thread components, ensuring comprehensive data flow from SQL queries to thread components.

## Overview

The SQL summary functionality has been enhanced to provide comprehensive data that can be stored in thread components. This includes executive summaries, data overviews, visualizations, and metadata.

## Updated Components

### 1. SQLSummaryRequest Model

The `SQLSummaryRequest` model now includes additional fields for comprehensive SQL summary generation:

```python
class SQLSummaryRequest(BaseModel):
    """Request model for SQL summary and visualization generation."""
    sql: str
    query: str
    project_id: str
    data_description: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None
    # Additional fields for comprehensive SQL summary
    schema_context: Optional[Dict[str, Any]] = None  # Database schema context
    chart_config: Optional[Dict[str, Any]] = None  # Chart configuration preferences
    summary_type: Optional[str] = "comprehensive"  # Type of summary: basic, comprehensive, detailed
    include_metadata: Optional[bool] = True  # Whether to include metadata in response
    include_sample_data: Optional[bool] = True  # Whether to include sample data
    visualization_format: Optional[str] = "vega_lite"  # Preferred visualization format
    streaming: Optional[bool] = False  # Whether to stream the results
```

### 2. ThreadComponent Model

The `ThreadComponent` model has been enhanced with SQL summary specific fields:

```python
# SQL Summary specific fields
sql_query = Column(String, nullable=True)  # The SQL query executed
executive_summary = Column(String, nullable=True)  # Executive summary text
data_overview = Column(JSON, nullable=True)  # Data overview statistics
visualization_data = Column(JSON, nullable=True)  # Visualization configuration and data
sample_data = Column(JSON, nullable=True)  # Sample data for preview
metadata = Column(JSON, nullable=True)  # Query execution metadata
chart_schema = Column(JSON, nullable=True)  # Chart schema (vega_lite, plotly, etc.)
reasoning = Column(String, nullable=True)  # Reasoning behind the analysis
data_count = Column(Integer, nullable=True)  # Number of records processed
validation_results = Column(JSON, nullable=True)  # Data validation results
```

### 3. New ComponentType

Added a new component type for SQL summaries:

```python
class ComponentType(str, Enum):
    # ... existing types ...
    SQL_SUMMARY = "sql_summary"  # SQL query summary and visualization component
```

### 4. Enhanced Response Structure

The SQL summary response now includes comprehensive data:

```python
{
    "success": True,
    "data": {
        "executive_summary": "Generated summary text",
        "data_overview": {...},  # Data statistics and overview
        "visualization": {...},  # Visualization configuration
        "metadata": {...},  # Query execution metadata
        "sql_query": "SELECT * FROM table",  # Original SQL query
        "query": "Show me sales data",  # Original user query
        "project_id": "project_123",
        "chart_schema": {...},  # Chart schema
        "reasoning": "Analysis reasoning",
        "data_count": 1000,  # Number of records
        "validation_results": {...},  # Data validation
        "sample_data": {...},  # Sample data for preview
        "execution_config": {...},  # Execution configuration
        "plotly_schema": {...},  # Plotly chart schema
        "powerbi_schema": {...},  # PowerBI chart schema
        "vega_lite_schema": {...}  # Vega-Lite chart schema
    },
    "error": None
}
```

## Usage Examples

### 1. Creating a SQL Summary Request

```python
from agents.app.routers.sql_helper import SQLSummaryRequest

# Basic request
request = SQLSummaryRequest(
    sql="SELECT COUNT(*) as total_sales, SUM(amount) as revenue FROM sales WHERE date >= '2024-01-01'",
    query="Show me sales summary for 2024",
    project_id="project_123",
    data_description="Sales data for Q1 2024",
    summary_type="comprehensive",
    include_metadata=True,
    include_sample_data=True,
    visualization_format="vega_lite"
)

# Advanced request with schema context
request = SQLSummaryRequest(
    sql="SELECT * FROM sales s JOIN products p ON s.product_id = p.id",
    query="Show me sales with product details",
    project_id="project_123",
    schema_context={
        "tables": {
            "sales": ["id", "product_id", "amount", "date"],
            "products": ["id", "name", "category", "price"]
        }
    },
    chart_config={
        "chart_type": "bar",
        "x_axis": "category",
        "y_axis": "revenue"
    },
    summary_type="detailed"
)
```

### 2. Creating a ThreadComponent from SQL Summary

```python
from workflowservices.app.models.workflowmodels import ThreadComponent

# After getting SQL summary response
sql_summary_response = {
    "success": True,
    "data": {
        "executive_summary": "Sales increased by 15% in Q1 2024...",
        "data_overview": {"total_records": 1000, "total_revenue": 50000},
        "visualization": {...},
        "sql_query": "SELECT COUNT(*) as total_sales...",
        # ... other fields
    }
}

# Create thread component
component = ThreadComponent.create_sql_summary_component(
    workflow_id="workflow_123",
    thread_message_id="message_456",
    sequence_order=1,
    sql_summary_data=sql_summary_response["data"],
    question="Show me sales summary for 2024",
    description="Q1 2024 sales analysis with visualization"
)
```

### 3. API Usage

```python
import requests

# Make SQL summary request
response = requests.post(
    "http://localhost:8000/sql-helper/summary",
    json={
        "sql": "SELECT COUNT(*) as total_sales FROM sales",
        "query": "Show me total sales count",
        "project_id": "project_123",
        "summary_type": "comprehensive",
        "include_metadata": True,
        "visualization_format": "vega_lite"
    }
)

# Process response
if response.json()["success"]:
    data = response.json()["data"]
    # Use data to create thread component
    component = ThreadComponent.create_sql_summary_component(
        sql_summary_data=data,
        question="Show me total sales count"
    )
```

## Data Flow

1. **Request**: Client sends `SQLSummaryRequest` with SQL query and configuration
2. **Processing**: Service processes the request and generates comprehensive summary data
3. **Response**: Service returns structured data including summary, visualization, and metadata
4. **Storage**: Thread component stores all relevant data in appropriate fields
5. **Retrieval**: Data can be retrieved and displayed in the UI

## Key Benefits

1. **Comprehensive Data**: All SQL summary data is captured and stored
2. **Flexible Configuration**: Multiple visualization formats and summary types
3. **Rich Metadata**: Includes execution details, validation results, and reasoning
4. **Easy Integration**: Simple helper method to create thread components
5. **Extensible**: Easy to add new fields as needed

## Migration Notes

- Existing thread components will continue to work
- New SQL summary fields are optional and nullable
- The `create_sql_summary_component` method is backward compatible
- No breaking changes to existing APIs

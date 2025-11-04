# Interactive Star Schema Builder

An interactive, human-in-the-loop tool for building star schema materialized views from ChromaDB-stored metadata.

## Overview

The `InteractiveStarSchemaBuilder` provides a guided workflow for creating optimized star schema views:

1. **Fetch Tables**: Automatically retrieves all tables, schemas, and relationships from ChromaDB
2. **Add Metrics**: Interactive prompts to define business metrics
3. **Select Time Dimension**: Choose time/date columns for time-series analysis
4. **Configure LOD**: Define Level of Detail expressions for deduplication
5. **Generate Views**: Creates optimized star schema materialized views

## Features

- **ChromaDB Integration**: Uses `RetrievalHelper2` to fetch all project tables and relationships
- **Human-in-the-Loop**: Interactive prompts guide you through configuration
- **Metrics Support**: Define custom metrics with SQL expressions
- **Time Dimension**: Automatic detection and selection of time/date columns
- **LOD Expressions**: Tableau-style Level of Detail expressions (FIXED, INCLUDE, EXCLUDE)
- **Star Schema**: Automatically generates source, fact, and dimension views

## Usage

### Interactive Mode (CLI)

```python
import asyncio
from app.agents.interactive_star_schema_builder import InteractiveStarSchemaBuilder

async def main():
    builder = InteractiveStarSchemaBuilder(
        project_id="sumtotal_learn",
        interactive_mode=True
    )
    
    results = await builder.run_interactive_workflow()

if __name__ == "__main__":
    asyncio.run(main())
```

### API Mode (Programmatic)

```python
import asyncio
from app.agents.interactive_star_schema_builder import InteractiveStarSchemaBuilder

async def main():
    builder = InteractiveStarSchemaBuilder(
        project_id="sumtotal_learn",
        interactive_mode=False  # API mode
    )
    
    input_data = {
        "metrics": [
            {
                "name": "total_sales",
                "display_name": "Total Sales",
                "description": "Sum of all sales amounts",
                "metric_sql": "SUM(orders.amount)",
                "metric_type": "sum",
                "aggregation_type": "SUM",
                "table_name": "orders",
                "columns": ["amount"]
            }
        ],
        "time_dimension": {
            "table_name": "orders",
            "column_name": "order_date",
            "display_name": "Order Date",
            "description": "Date when order was placed",
            "granularity": "day"
        },
        "lod_configs": {
            "mv_fact_sales_transactions": {
                "type": "FIXED",
                "dimensions": ["order_date", "region"]
            }
        }
    }
    
    results = await builder.run_interactive_workflow(input_data=input_data)

if __name__ == "__main__":
    asyncio.run(main())
```

## Workflow Steps

### Step 1: Fetch Tables from ChromaDB

Automatically fetches all tables, columns, and relationships stored in ChromaDB for the specified project.

```python
fetch_result = await builder.fetch_all_tables()
```

### Step 2: Add Metrics

Define business metrics that will be included in fact tables. Metrics can be:
- Simple column aggregations (SUM, COUNT, AVG)
- Custom SQL expressions
- Calculated fields

**Interactive Prompt Example:**
```
Enter metrics (press Enter twice when done):
Format: table_name.column_name as metric_name | description
Example: orders.amount as total_sales | Total sales amount

Metric: orders.amount as total_sales | Total sales amount
```

### Step 3: Select Time Dimension

Choose a time/date column to use as the time dimension. The builder automatically detects time-related columns.

**Interactive Prompt Example:**
```
Found 3 time/date columns:
  1. orders.order_date (TIMESTAMP) - Date when order was placed
  2. customers.signup_date (DATE) - Customer registration date
  3. orders.created_at (TIMESTAMP) - Order creation timestamp

Select time dimension (enter number): 1
Enter granularity (day/week/month/quarter/year, default: day): day
```

### Step 4: Configure LOD Expressions

Define Level of Detail (LOD) expressions for fact views. LOD expressions control deduplication and aggregation levels:

- **FIXED**: Compute at specified granularity only
  - Example: `{FIXED [order_date, region] : SUM(amount)}`
  - Uses `DISTINCT ON` or `GROUP BY` in SQL

- **INCLUDE**: Compute at fine granularity, allows reaggregation
  - Example: `{INCLUDE [customer_id] : SUM(amount)}`
  - Preserves transaction-level granularity

- **EXCLUDE**: Remove dimensions from granularity
  - Example: `{EXCLUDE [region] : SUM(amount)}`
  - Useful for percentage/total calculations

- **None**: No deduplication (full transaction granularity)
  - Keeps all rows at transaction/event level

**Interactive Prompt Example:**
```
Configure LOD for 2 fact view(s):

  View: mv_fact_sales_transactions
    LOD Type (FIXED/INCLUDE/EXCLUDE/None, default: None): FIXED
    Enter dimensions (comma-separated, e.g., date,region): order_date,region
```

## Output

The builder returns a dictionary with:

```python
{
    "success": True,
    "tables": [...],  # List of fetched tables
    "relationships": [...],  # List of relationships
    "metrics": [...],  # List of configured metrics
    "time_dimension": {...},  # Time dimension configuration
    "lod_configs": {...},  # LOD configurations
    "view_specs": [...],  # Generated view specifications
    "regenerated_sql": [...]  # Optimized SQL definitions
}
```

### View Specifications

Each view specification includes:

- `view_name`: Name of the materialized view
- `view_type`: Type (source, fact, dimension)
- `sql_definition`: SQL CREATE statement
- `dimensions`: List of dimension columns
- `measures`: List of measure columns
- `refresh_strategy`: Refresh strategy (incremental, full, on-demand)
- `level_of_details`: LOD configuration

### SQL Definitions

Optimized SQL with:
- Proper column comments with metadata
- Business descriptions and display names
- Data type information
- Usage types (dimension, measure, attribute)
- LOD deduplication logic (if configured)

## Integration with UnifiedSQLViewAgent

The builder uses `UnifiedSQLViewAgent` internally for:
- Query analysis and reasoning plans
- Star schema view generation
- SQL regeneration and optimization
- Schema validation

## Examples

### Example 1: Sales Analytics Star Schema

```python
# Fetch tables for sales project
builder = InteractiveStarSchemaBuilder(project_id="sales_db")

# Add metrics
# Interactive: "orders.total_amount as total_revenue | Total revenue"

# Select time dimension
# Interactive: Select orders.order_date with day granularity

# Configure LOD
# Interactive: FIXED LOD on [order_date, region] for mv_fact_sales

# Generate views
results = await builder.run_interactive_workflow()
```

This will generate:
- `mv_source_orders`: Base orders table
- `mv_dim_customer`: Customer dimension
- `mv_dim_date`: Date dimension
- `mv_fact_sales_transactions`: Sales fact table with FIXED LOD

### Example 2: E-commerce Analytics

```python
# API mode example
input_data = {
    "metrics": [
        {"name": "total_revenue", "metric_sql": "SUM(orders.amount)", ...},
        {"name": "order_count", "metric_sql": "COUNT(orders.order_id)", ...}
    ],
    "time_dimension": {
        "table_name": "orders",
        "column_name": "order_date",
        "granularity": "day"
    },
    "lod_configs": {
        "mv_fact_orders": {
            "type": "FIXED",
            "dimensions": ["order_date", "customer_id"]
        }
    }
}

results = await builder.run_interactive_workflow(input_data=input_data)
```

## Best Practices

1. **Start with All Tables**: The builder fetches all tables automatically - review them before proceeding
2. **Define Clear Metrics**: Use descriptive names and include business descriptions
3. **Choose Appropriate Granularity**: Match time granularity to your analysis needs
4. **Use LOD Sparingly**: Only apply LOD when deduplication is needed - default is transaction-level
5. **Review Generated SQL**: Always review the generated SQL before executing
6. **Validate Relationships**: Ensure relationships are correctly identified

## Configuration

### Project ID

The `project_id` parameter must match the project ID used in ChromaDB storage. This is typically the directory name in `data/sql_meta/`.

### Retrieval Helper

By default, uses `RetrievalHelper2` with standard configuration. You can provide a custom instance:

```python
from app.retrieval.retrieval_helper2 import RetrievalHelper2

custom_retrieval = RetrievalHelper2(
    similarity_threshold=0.8
)

builder = InteractiveStarSchemaBuilder(
    project_id="my_project",
    retrieval_helper=custom_retrieval
)
```

### LLM Configuration

Uses Claude Sonnet 4.5 by default. You can provide a custom LLM:

```python
from langchain_anthropic import ChatAnthropic

custom_llm = ChatAnthropic(
    model="claude-opus-3",
    temperature=0.1
)

builder = InteractiveStarSchemaBuilder(
    project_id="my_project",
    llm=custom_llm
)
```

## Troubleshooting

### No Tables Found

- Verify `project_id` matches ChromaDB collection name
- Check that tables were indexed in ChromaDB
- Verify ChromaDB connection

### Missing Metrics

- Ensure you've added metrics before generating views
- Check that metric columns exist in fetched tables
- Verify SQL syntax in metric expressions

### Time Dimension Not Found

- Check that date/timestamp columns exist in tables
- Verify column data types include 'date', 'timestamp', or 'time'
- You can manually specify time dimension if auto-detection fails

### LOD Not Applied

- Verify LOD configuration is in correct format
- Check that dimensions exist in fact view
- Ensure view name matches exactly

## See Also

- `UnifiedSQLViewAgent`: Core view generation engine
- `RetrievalHelper2`: ChromaDB retrieval helper
- `unified_sql_view_agent.py`: Detailed view generation documentation


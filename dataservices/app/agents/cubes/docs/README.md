# Cube.js Data Model Generation Agent - Medallion Architecture

A LangGraph-based agent workflow for automatically generating Cube.js data models following the medallion architecture (Raw → Silver → Gold layers). This system transforms database DDLs into production-ready Cube.js definitions with pre-aggregations, views, and transformation workflows.

## 🎯 Overview

This agent workflow automates the creation of:
- **Cube.js Cube Definitions** (JSON/JavaScript)
- **Cube.js View Definitions** 
- **Pre-Aggregation Configurations**
- **Data Transformation SQL** (Raw → Silver → Gold)
- **Parent-Child Relationship Mappings**
- **Level of Detail (LOD) Deduplication Logic**

### Medallion Architecture Layers

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   RAW       │────▶│   SILVER    │────▶│   GOLD      │
│             │     │             │     │             │
│ - Raw data  │     │ - Cleaned   │     │ - Aggregated│
│ - Minimal   │     │ - Deduped   │     │ - Business  │
│   transforms│     │ - Conformed │     │   metrics   │
│ - Type cast │     │ - Validated │     │ - Optimized │
└─────────────┘     └─────────────┘     └─────────────┘
```

## 📁 Project Structure

```
.
├── cube_generation_agent.py          # Main LangGraph workflow orchestrator
├── schema_analysis_agent.py          # DDL analysis and dimension/measure extraction
├── transformation_planner_agent.py   # SQL transformation planning
├── cubejs_generator_agent.py         # Cube.js JSON/JS generation
└── README.md                          # This file
```

## 🚀 Quick Start

### Prerequisites

```bash
pip install langgraph langchain langchain-openai pydantic
export OPENAI_API_KEY="your-api-key"
```

### Basic Usage

```python
from cube_generation_agent import CubeGenerationAgent, TableDDL, LODConfig

# 1. Define your raw table DDL
raw_ddl = TableDDL(
    table_name="dev_network_devices",
    table_ddl="""
    CREATE TABLE dev_network_devices (
      id BIGINT NOT NULL,
      ip VARCHAR,
      mac VARCHAR,
      manufacturer VARCHAR,
      updated_at TIMESTAMP,
      is_stale BOOLEAN
    );
    """,
    relationships=[],
    layer="raw"
)

# 2. Configure Level of Detail for deduplication
lod_config = LODConfig(
    table_name="dev_network_devices",
    lod_type="FIXED",
    dimensions=["ip", "mac"],
    description="Deduplicate devices by IP and MAC address"
)

# 3. Initialize agent and generate
agent = CubeGenerationAgent()
result = agent.generate(
    raw_ddls=[raw_ddl],
    user_query="Create analytics dashboard for network device monitoring",
    lod_configs=[lod_config]
)

# 4. Access generated artifacts
print("Raw Cubes:", result['raw_cubes'])
print("Silver Cubes:", result['silver_cubes'])
print("Gold Cubes:", result['gold_cubes'])
print("Views:", result['views'])
print("Transformations:", result['raw_to_silver_transformations'])
```

## 🔧 Agent Workflow

### 1. Schema Analysis Agent

**Purpose**: Analyze DDL schemas to extract semantic information

**Capabilities**:
- Identify dimensions (categorical/text columns)
- Identify measures (numeric/aggregatable columns)
- Detect time dimensions
- Find primary/foreign keys
- Infer table grain
- Suggest data quality improvements
- Recommend deduplication strategies

**Example**:
```python
from schema_analysis_agent import SchemaAnalysisAgent

agent = SchemaAnalysisAgent()
analysis = agent.analyze_ddl(
    table_name="dev_network_devices",
    ddl=your_ddl_string,
    relationships=[]
)

print(f"Grain: {analysis.grain}")
print(f"Dimensions: {[c.name for c in analysis.columns if c.is_dimension]}")
print(f"Measures: {[c.name for c in analysis.columns if c.is_measure]}")
```

### 2. Transformation Planner Agent

**Purpose**: Plan and generate SQL transformations between layers

**Transformation Types**:
- **Cleaning**: Handle nulls, fix invalid data
- **Type Casting**: Ensure proper data types
- **Standardization**: Consistent formatting
- **Deduplication**: Apply LOD-based logic
- **Aggregation**: Business-level rollups
- **Joins**: Create denormalized views

**Example**:
```python
from transformation_planner_agent import TransformationPlannerAgent, LODDeduplication

agent = TransformationPlannerAgent()

# Plan raw → silver transformations
lod = LODDeduplication(
    lod_type="FIXED",
    dimensions=["ip", "mac"],
    tie_breaker="updated_at"
)

steps = agent.plan_raw_to_silver(
    table_name="dev_network_devices",
    schema_analysis=analysis.dict(),
    lod_config=lod
)

for step in steps:
    print(f"{step.step_name}:\n{step.sql_logic}")
```

### 3. Cube.js Generator Agent

**Purpose**: Generate valid Cube.js definitions

**Outputs**:
- Cube definitions (JSON/JavaScript)
- View definitions
- Pre-aggregation configurations
- Dimension specifications
- Measure specifications
- Join definitions

**Example**:
```python
from cubejs_generator_agent import CubeJsGeneratorAgent

agent = CubeJsGeneratorAgent()

# Generate cube definition
cube = agent.generate_cube(
    table_name="silver_network_devices",
    schema_analysis=analysis.dict(),
    layer="silver"
)

# Export as JavaScript
js_code = agent.export_to_javascript(cube)
print(js_code)

# Generate pre-aggregations
pre_aggs = agent.generate_pre_aggregations(
    cube_name="silver_network_devices",
    dimensions=["ip", "site", "manufacturer"],
    measures=["count", "avg_days_since_last_seen"],
    time_dimensions=["updated_at"]
)
```

## 📊 Level of Detail (LOD) Configuration

LOD defines the uniqueness criteria for deduplication, inspired by [Tableau's LOD expressions](https://help.tableau.com/current/pro/desktop/en-us/calculations_calculatedfields_lod.htm).

### LOD Types

1. **FIXED**: Specific dimensions define uniqueness
   ```python
   LODConfig(
       table_name="devices",
       lod_type="FIXED",
       dimensions=["ip", "mac"],  # One record per IP+MAC combination
       description="Unique devices by network address"
   )
   ```

2. **INCLUDE**: Base grain + additional dimensions
   ```python
   LODConfig(
       table_name="events",
       lod_type="INCLUDE",
       dimensions=["event_date"],  # Add date to base grain
       description="Daily aggregated events"
   )
   ```

3. **EXCLUDE**: Remove dimensions from grain
   ```python
   LODConfig(
       table_name="sales",
       lod_type="EXCLUDE",
       dimensions=["transaction_id"],  # Aggregate above transaction level
       description="Order-level totals"
   )
   ```

### Deduplication SQL Example

For FIXED LOD on `["ip", "mac"]`:

```sql
CREATE TABLE silver_devices_deduped AS
SELECT *
FROM (
    SELECT 
        *,
        ROW_NUMBER() OVER (
            PARTITION BY ip, mac
            ORDER BY updated_at DESC
        ) as row_num
    FROM silver_devices_cleaned
) ranked
WHERE row_num = 1;
```

## 🔗 Relationship Mappings

Define parent-child relationships for building silver and gold layers through joins.

### Example

```python
from cube_generation_agent import RelationshipMapping

relationships = [
    RelationshipMapping(
        child_table="device_events",
        parent_table="devices",
        join_type="MANY_TO_ONE",
        join_condition="device_events.device_id = devices.id",
        layer="silver"
    ),
    RelationshipMapping(
        child_table="devices",
        parent_table="sites",
        join_type="MANY_TO_ONE",
        join_condition="devices.site_id = sites.id",
        layer="silver"
    )
]

result = agent.generate(
    raw_ddls=[...],
    user_query="...",
    relationship_mappings=relationships
)
```

### Join Types

- **ONE_TO_ONE**: Each record in child matches one in parent
- **ONE_TO_MANY**: Each parent has multiple children
- **MANY_TO_ONE**: Many children map to one parent
- **MANY_TO_MANY**: Requires junction table

## 🎨 Cube.js Output Examples

### Raw Layer Cube

```javascript
cube(`raw_network_devices`, {
  sql: `SELECT * FROM dev_network_devices`,
  
  title: "Raw Network Devices",
  description: "Raw layer - minimal transformations",
  
  dimensions: {
    id: {
      sql: `${CUBE}.id`,
      type: `number`,
      primaryKey: true,
    },
    ip: {
      sql: `${CUBE}.ip`,
      type: `string`,
      title: `IP Address`,
    },
    updated_at: {
      sql: `${CUBE}.updated_at`,
      type: `time`,
    },
  },
  
  measures: {
    count: {
      type: `count`,
      drillMembers: [id, ip],
    },
  },
});
```

### Silver Layer Cube with Pre-Aggregations

```javascript
cube(`silver_network_devices`, {
  sql: `SELECT * FROM silver_devices_deduped`,
  
  dimensions: {
    // ... dimensions
  },
  
  measures: {
    // ... measures
  },
  
  preAggregations: {
    dailyRollup: {
      type: `rollup`,
      measures: [count, avg_days_since_last_seen],
      dimensions: [site, manufacturer],
      timeDimension: updated_at,
      granularity: `day`,
      partitionGranularity: `month`,
      refreshKey: {
        every: `1 day`,
      },
    },
  },
});
```

### Gold Layer Cube

```javascript
cube(`gold_device_metrics`, {
  sql: `
    SELECT 
      DATE_TRUNC('day', updated_at) as date,
      site,
      COUNT(*) as total_devices,
      COUNT(DISTINCT ip) as unique_ips,
      AVG(days_since_last_seen) as avg_days_inactive
    FROM silver_devices_deduped
    GROUP BY 1, 2
  `,
  
  dimensions: {
    date: {
      sql: `${CUBE}.date`,
      type: `time`,
    },
    site: {
      sql: `${CUBE}.site`,
      type: `string`,
    },
  },
  
  measures: {
    total_devices: {
      sql: `${CUBE}.total_devices`,
      type: `sum`,
      title: `Total Devices`,
    },
    unique_ips: {
      sql: `${CUBE}.unique_ips`,
      type: `sum`,
      title: `Unique IP Addresses`,
    },
    avg_days_inactive: {
      sql: `${CUBE}.avg_days_inactive`,
      type: `avg`,
      title: `Average Days Inactive`,
      format: `percent`,
    },
  },
});
```

## 🔄 Complete Workflow Example

```python
from cube_generation_agent import (
    CubeGenerationAgent,
    TableDDL,
    LODConfig,
    RelationshipMapping
)

# Step 1: Define your raw schemas
device_ddl = TableDDL(
    table_name="dev_network_devices",
    table_ddl="""-- Network device inventory
    CREATE TABLE dev_network_devices (
      id BIGINT NOT NULL,
      ip VARCHAR,
      mac VARCHAR,
      site VARCHAR,
      manufacturer VARCHAR,
      updated_at TIMESTAMP,
      is_stale BOOLEAN,
      days_since_last_seen INTEGER
    );""",
    relationships=[],
    layer="raw"
)

event_ddl = TableDDL(
    table_name="device_events",
    table_ddl="""-- Device network events
    CREATE TABLE device_events (
      event_id BIGINT,
      device_id BIGINT,
      event_type VARCHAR,
      event_timestamp TIMESTAMP,
      bytes_transferred BIGINT
    );""",
    relationships=[],
    layer="raw"
)

# Step 2: Configure LOD for deduplication
device_lod = LODConfig(
    table_name="dev_network_devices",
    lod_type="FIXED",
    dimensions=["ip", "mac"],
    description="One device per IP+MAC combination"
)

# Step 3: Define relationships
relationships = [
    RelationshipMapping(
        child_table="device_events",
        parent_table="dev_network_devices",
        join_type="MANY_TO_ONE",
        join_condition="device_events.device_id = dev_network_devices.id",
        layer="silver"
    )
]

# Step 4: Generate complete data model
agent = CubeGenerationAgent()
result = agent.generate(
    raw_ddls=[device_ddl, event_ddl],
    user_query="""
    Create a network analytics platform that shows:
    - Daily active devices by site
    - Network traffic patterns
    - Device lifecycle metrics
    - Stale device identification
    """,
    lod_configs=[device_lod],
    relationship_mappings=relationships
)

# Step 5: Save outputs
import json

# Save cube definitions
with open('cubes/raw_network_devices.json', 'w') as f:
    json.dump(result['raw_cubes'][0], f, indent=2)

with open('cubes/silver_network_devices.json', 'w') as f:
    json.dump(result['silver_cubes'][0], f, indent=2)

with open('cubes/gold_device_metrics.json', 'w') as f:
    json.dump(result['gold_cubes'][0], f, indent=2)

# Save transformation SQL
with open('transformations/raw_to_silver.sql', 'w') as f:
    for step in result['raw_to_silver_transformations']:
        f.write(f"-- {step['step_name']}\n")
        f.write(f"-- {step['description']}\n\n")
        f.write(step['sql_logic'])
        f.write("\n\n")

# Save views
with open('views/network_analytics_view.json', 'w') as f:
    json.dump(result['views'], f, indent=2)
```

## 📚 Key Concepts

### 1. Medallion Architecture

- **Raw Layer**: Source data with minimal transformation
  - Preserve original structure
  - Basic type casting
  - No business logic
  - Append-only history

- **Silver Layer**: Cleaned and conformed data
  - Data quality rules applied
  - Deduplication completed
  - Standardized formats
  - Business-ready dimensions

- **Gold Layer**: Business-level aggregations
  - Pre-calculated metrics
  - Time-series rollups
  - Performance-optimized
  - Dashboard-ready

### 2. Cube.js Data Modeling

- **Cubes**: Define measures and dimensions
- **Dimensions**: Attributes for filtering/grouping
- **Measures**: Numeric calculations (sum, avg, count)
- **Joins**: Relationships between cubes
- **Pre-Aggregations**: Materialized rollups for performance
- **Views**: Combine multiple cubes

### 3. Transformation Best Practices

- **Idempotent**: Can run multiple times safely
- **Incremental**: Process only changed data
- **Auditable**: Track data lineage
- **Testable**: Include data quality checks
- **Documented**: Clear business logic

## 🎯 Use Cases

### 1. Network Device Monitoring
- Track device inventory across sites
- Monitor device health and lifecycle
- Analyze network traffic patterns
- Identify stale or inactive devices

### 2. Learning Management Systems
- Student enrollment analytics
- Course completion metrics
- Learning path analysis
- Instructor effectiveness

### 3. E-commerce Analytics
- Customer behavior analysis
- Product performance metrics
- Sales trend analysis
- Inventory optimization

### 4. IoT Data Analysis
- Sensor data aggregation
- Device telemetry monitoring
- Predictive maintenance
- Real-time alerting

## 🔍 Advanced Features

### Custom Dimensions

```python
# Add calculated dimension in schema analysis
{
    "name": "device_age_category",
    "sql": """
        CASE 
            WHEN days_since_last_seen <= 7 THEN 'Active'
            WHEN days_since_last_seen <= 30 THEN 'Recent'
            WHEN days_since_last_seen <= 90 THEN 'Inactive'
            ELSE 'Stale'
        END
    """,
    "type": "string",
    "is_calculated": True
}
```

### Custom Measures

```python
# Add calculated measure
{
    "name": "active_device_percentage",
    "sql": """
        100.0 * SUM(CASE WHEN is_stale = FALSE THEN 1 ELSE 0 END) / COUNT(*)
    """,
    "type": "number",
    "format": "percent"
}
```

### Rolling Window Calculations

```python
CubeMeasure(
    name="rolling_7day_average",
    sql="${CUBE}.daily_count",
    type="number",
    rollingWindow={
        "trailing": "7 day",
        "offset": "start"
    }
)
```

## 🐛 Troubleshooting

### Common Issues

1. **Invalid JSON output**
   - Check LLM response parsing
   - Validate Pydantic models
   - Use fallback cube generation

2. **SQL syntax errors**
   - Verify column names match DDL
   - Check join conditions
   - Test SQL independently

3. **Missing dimensions/measures**
   - Review schema analysis output
   - Check column type detection
   - Adjust classification rules

### Debug Mode

```python
import logging
logging.basicConfig(level=logging.DEBUG)

agent = CubeGenerationAgent(model_name="gpt-4o")
result = agent.generate(...)
```

## 📖 References

- [Cube.js Documentation](https://cube.dev/docs)
- [Cube.js Data Modeling Reference](https://cube.dev/docs/product/data-modeling/reference/cube)
- [Cube.js View Reference](https://cube.dev/docs/product/data-modeling/reference/view)
- [Tableau LOD Expressions](https://help.tableau.com/current/pro/desktop/en-us/calculations_calculatedfields_lod.htm)
- [Medallion Architecture](https://www.databricks.com/glossary/medallion-architecture)
- [LangGraph Documentation](https://python.langchain.com/docs/langgraph)

## 🤝 Contributing

This is a focused agent workflow for Cube.js generation. To extend:

1. Add new transformation types in `transformation_planner_agent.py`
2. Enhance schema analysis logic in `schema_analysis_agent.py`
3. Add Cube.js features in `cubejs_generator_agent.py`
4. Improve workflow orchestration in `cube_generation_agent.py`

## 📄 License

MIT License - Use freely for your data modeling needs!

---

**Note**: This agent workflow generates automation workflows (JSON/SQL definitions) that will be executed by a separate system. It does NOT execute transformations or create actual database tables.

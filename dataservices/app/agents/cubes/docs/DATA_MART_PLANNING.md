# Data Mart Planning Agent

## Overview

The Data Mart Planning Agent is a new component in the silver workflow that:
1. **Retrieves relevant silver tables** based on business goals using semantic search
2. **Plans data marts** by generating SQL CREATE TABLE statements
3. **Generates natural language questions** for each SQL query
4. **Integrates with the silver human-in-the-loop workflow**

## Architecture

### Components

1. **SilverTableRetrieval** (`silver_table_retrieval.py`)
   - Similar to `retrieval.py` but specifically for silver tables
   - Uses semantic search to find relevant tables
   - Can work with document stores or in-memory table metadata

2. **DataMartPlannerAgent** (`data_mart_planner_agent.py`)
   - Plans data marts from business goals
   - Generates SQL and natural language questions
   - Integrates with the silver workflow

3. **SilverHumanInLoopAgent** (updated)
   - Now includes data mart planning capability
   - Can plan data marts from goals after collecting table requirements

## Usage

### Basic Usage

```python
from app.agents.cubes.silver_human_in_loop import SilverHumanInLoopAgent
from app.agents.cubes.cube_generation_agent import AgentState

# Initialize the agent with data mart planning enabled
agent = SilverHumanInLoopAgent(
    llm=llm,
    enable_data_mart_planning=True
)

# Plan a data mart from a goal
goal = "Show me daily sales summary by customer and product"
plan = await agent.plan_data_marts_from_goal(
    goal=goal,
    state=agent_state,
    project_id="my_project"
)

# Access the generated SQL and questions
for mart in plan.marts:
    print(f"Mart: {mart.mart_name}")
    print(f"SQL: {mart.sql}")
    print(f"Question: {mart.natural_language_question}")
```

### Integration with Silver Workflow

```python
from app.agents.cubes.silver_human_in_loop import enrich_silver_workflow_with_human_in_loop

# Define data mart goals
data_mart_goals = [
    "Create a customer lifetime value analysis",
    "Show monthly revenue trends by region"
]

# Enrich workflow with data mart planning
state = await enrich_silver_workflow_with_human_in_loop(
    state=agent_state,
    human_in_loop_agent=agent,
    data_mart_goals=data_mart_goals
)

# Access planned data marts from state
data_mart_plans = state.get("data_mart_plans", [])
```

## Data Structures

### DataMartSQL

```python
class DataMartSQL:
    mart_name: str                    # Name of the data mart
    sql: str                          # CREATE TABLE SQL statement
    description: str                   # What this mart contains
    natural_language_question: str    # Question this SQL answers
    source_tables: List[str]          # Source silver tables
    target_columns: List[str]          # Columns in the result
    business_value: str               # Why this mart is valuable
    grain: str                        # Level of detail (e.g., "One row per customer per day")
```

### DataMartPlan

```python
class DataMartPlan:
    goal: str                         # Original business goal
    marts: List[DataMartSQL]          # Generated data marts
    reasoning: str                    # Explanation of the plan
    estimated_complexity: str          # "low", "medium", or "high"
```

## Workflow Integration

The data mart planner integrates into the silver workflow as follows:

1. **Table Requirements Collection** - Collects requirements for each silver table
2. **Data Mart Planning** (NEW) - Plans data marts from business goals
3. **SQL Generation** - Generates CREATE TABLE statements
4. **Question Generation** - Creates natural language questions for each SQL

## Natural Language to SQL

The generated natural language questions can be used by other agents (e.g., text-to-SQL agents) to:
- Validate the generated SQL
- Generate alternative SQL queries
- Create user-facing documentation
- Enable conversational querying

## Example Output

```python
# Goal: "Show me daily sales summary by customer and product"

DataMartPlan(
    goal="Show me daily sales summary by customer and product",
    marts=[
        DataMartSQL(
            mart_name="daily_sales_summary",
            sql="""
            CREATE TABLE daily_sales_summary AS
            SELECT 
                DATE_TRUNC('day', order_date) as sale_date,
                customer_id,
                product_id,
                SUM(amount) as total_sales,
                COUNT(*) as order_count
            FROM silver_orders o
            JOIN silver_customers c ON o.customer_id = c.id
            JOIN silver_products p ON o.product_id = p.id
            GROUP BY DATE_TRUNC('day', order_date), customer_id, product_id;
            """,
            natural_language_question="What are the daily sales totals by customer and product?",
            source_tables=["silver_orders", "silver_customers", "silver_products"],
            target_columns=["sale_date", "customer_id", "product_id", "total_sales", "order_count"],
            business_value="Enables daily sales analysis by customer and product dimensions",
            grain="One row per customer per product per day"
        )
    ],
    reasoning="Selected sales, customer, and product tables to create daily aggregated summary...",
    estimated_complexity="medium"
)
```

## Configuration

Data mart planning can be enabled/disabled when initializing the agent:

```python
# Enable data mart planning (default)
agent = SilverHumanInLoopAgent(enable_data_mart_planning=True)

# Disable data mart planning
agent = SilverHumanInLoopAgent(enable_data_mart_planning=False)
```

## Future Enhancements

- Support for incremental data mart updates
- Automatic optimization of SQL queries
- Integration with query performance monitoring
- Support for materialized views
- Automatic indexing recommendations


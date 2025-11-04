# Quick Start Guide

## 🚀 Get Up and Running in 5 Minutes

### Step 1: Install Dependencies (1 minute)

```bash
pip install langgraph langchain langchain-anthropic anthropic sqlglot pydantic
```

Or use the requirements file:
```bash
pip install -r requirements.txt
```

### Step 2: Set Your API Key (30 seconds)

```bash
export ANTHROPIC_API_KEY='your-api-key-here'
```

Or in Python:
```python
import os
os.environ['ANTHROPIC_API_KEY'] = 'your-api-key-here'
```

### Step 3: Run the Example (30 seconds)

```bash
python comprehensive_example.py
```

This will show you all capabilities of the system!

### Step 4: Transform Your First Dashboard (3 minutes)

```python
import json
from dashboard_agent_system import transform_dashboard

# Load your dashboard
with open('your_dashboard.json', 'r') as f:
    dashboard = json.load(f)

# Transform it!
result = transform_dashboard(
    source_dashboard=dashboard,
    target_platform="powerbi"  # or "tableau"
)

# Get the results
print(f"✅ Transformed {len(result['components'])} components")
print(f"✅ Created {len(result['materialized_views'])} materialized views")
print(f"✅ Generated {len(result['insights'])} insights")

# Save the output
with open('transformed_dashboard.json', 'w') as f:
    json.dump(result['final_dashboard'], f, indent=2)
```

## 🎯 Common Use Cases

### Use Case 1: Convert SQL to DAX

```python
from sql_to_dax_converter import SQLToDAXConverter

converter = SQLToDAXConverter()

sql = """
SELECT 
    department,
    COUNT(*) as employee_count,
    AVG(salary) as avg_salary
FROM employees
WHERE hire_date >= '2024-01-01'
GROUP BY department
"""

# Convert!
dax_table = converter.convert(sql)

# Print the DAX measures
for measure in dax_table.measures:
    print(f"{measure.name} = {measure.expression}")
```

Output:
```
employee_count = COUNTROWS(employees)
avg_salary = AVERAGE(employees[salary])
```

### Use Case 2: Create Materialized Views

```python
from materialized_view_optimizer import MaterializedViewOptimizer

optimizer = MaterializedViewOptimizer()

queries = [
    "SELECT dept, COUNT(*) FROM employees GROUP BY dept",
    "SELECT dept, SUM(salary) FROM employees GROUP BY dept",
    "SELECT dept, AVG(salary) FROM employees GROUP BY dept"
]

# Create optimized views
mv_specs = optimizer.create_materialized_views(queries)

# Print the SQL
for mv in mv_specs:
    print(mv.create_statement)
```

### Use Case 3: Generate Insights & Answer Questions

```python
from conversational_insights_agent import ConversationalInsightsAgent

agent = ConversationalInsightsAgent()

dashboard_data = {
    # Your dashboard data here
}

# Generate insights automatically
insights = agent.generate_insights(dashboard_data, components)

print(f"Found {len(insights)} insights:")
for insight in insights:
    print(f"- [{insight.severity}] {insight.title}")

# Ask questions in natural language
answer = agent.answer_question(
    "What's the current completion rate?",
    dashboard_data
)

print(answer['answer'])
```

## 📊 Input Format

Your dashboard JSON should look like this:

```json
{
  "dashboard_id": "unique-id",
  "dashboard_name": "My Dashboard",
  "content": {
    "components": [
      {
        "id": "component-1",
        "type": "question",
        "question": "What is the average revenue?",
        "sql_query": "SELECT AVG(revenue) FROM sales",
        "chart_schema": {
          "mark": {"type": "bar"},
          "encoding": {...}
        },
        "sample_data": {
          "data": [...],
          "columns": [...]
        }
      }
    ]
  }
}
```

## 🎨 Output Examples

### PowerBI Output
```python
{
  "platform": "powerbi",
  "components": [
    {
      "transformed_query": "AVERAGE(Sales[revenue])",
      "visualization": {
        "visual_type": "clusteredColumnChart",
        "config": {...}
      }
    }
  ],
  "materialized_views": [...]
}
```

### Tableau Output
```python
{
  "platform": "tableau",
  "components": [
    {
      "transformed_query": "AVG([Revenue])",
      "visualization": {
        "worksheet_type": "bar",
        "shelves": {...}
      }
    }
  ],
  "materialized_views": [...]
}
```

## 🔧 Configuration Options

### Basic Configuration
```python
# Transform with options
result = transform_dashboard(
    source_dashboard=dashboard,
    target_platform="powerbi",
    table_metadata=[
        {
            "table": "employees",
            "columns": ["id", "name", "dept", "salary"],
            "primary_key": "id"
        }
    ]
)
```

### Advanced Configuration
```python
from langchain_anthropic import ChatAnthropic

# Use custom LLM settings
llm = ChatAnthropic(
    model="claude-sonnet-4-5-20250929",
    temperature=0,
    max_tokens=4096
)

# Initialize agents with custom LLM
from dashboard_agent_system import PowerBITransformAgent
powerbi_agent = PowerBITransformAgent(llm)
```

## 📝 Examples by Platform

### For PowerBI Users
```python
# Transform dashboard to PowerBI
result = transform_dashboard(dashboard, "powerbi")

# Get DAX measures
for component in result['components']:
    print(component['transformed_query'])  # DAX code

# Get Power Query M code
from sql_to_dax_converter import SQLToDAXConverter
converter = SQLToDAXConverter()
m_code = converter.generate_power_query_m(sql_query)
print(m_code)
```

### For Tableau Users
```python
# Transform dashboard to Tableau
result = transform_dashboard(dashboard, "tableau")

# Get calculated fields
for component in result['components']:
    print(component['transformed_query'])  # Tableau calc

# Get worksheet configuration
for viz in result['transformed_visualizations']:
    print(viz['shelves'])  # Rows, columns, marks
```

## ⚠️ Troubleshooting

### Issue: API Key Error
```
Solution: Set your Anthropic API key
export ANTHROPIC_API_KEY='your-key-here'
```

### Issue: Import Errors
```
Solution: Install missing packages
pip install langgraph langchain-anthropic sqlglot
```

### Issue: SQL Parsing Fails
```
Solution: The system will use LLM fallback automatically
Or provide more context in table_metadata
```

## 🎓 Learning Path

1. **Start Here**: Run `comprehensive_example.py`
2. **Learn Basics**: Read `README.md`
3. **Deep Dive**: Study `dashboard_agent_system_architecture.md`
4. **Customize**: Modify agents for your needs
5. **Deploy**: Deploy to production

## 📚 Key Files to Know

- `dashboard_agent_system.py` - Main system
- `sql_to_dax_converter.py` - SQL conversion
- `materialized_view_optimizer.py` - Performance optimization
- `conversational_insights_agent.py` - AI insights

## 💡 Pro Tips

1. **Use Table Metadata**: Provide table schemas for better conversions
2. **Test Incrementally**: Start with one component, then scale
3. **Monitor LLM Calls**: Keep track of API usage
4. **Cache Results**: Cache common query conversions
5. **Version Control**: Track changes to your transformations

## 🚀 Next Steps

1. ✅ Run the comprehensive example
2. ✅ Try with your own dashboard
3. ✅ Customize for your platform
4. ✅ Add custom insights
5. ✅ Deploy to production

## 📞 Need Help?

- Check `README.md` for detailed documentation
- Review `PROJECT_STRUCTURE.md` for architecture
- Run examples in `comprehensive_example.py`
- Review code comments for API details

---

**Ready to Transform Dashboards?** 

Start with:
```bash
python comprehensive_example.py
```

Then customize for your needs! 🎉

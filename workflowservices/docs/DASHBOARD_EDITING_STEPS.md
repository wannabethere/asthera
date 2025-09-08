# Dashboard Editing Steps in Workflow Orchestrator

This document describes the new dashboard editing steps available in the Workflow Orchestrator for editing dashboards and managing components with proper version control and draft management.

## Draft-Based Editing Workflow

The new editing system implements a **draft-based approach** where:
- **Editing creates draft versions** that don't affect the published dashboard
- **Changes are stored in workflow metadata** until explicitly published
- **Publishing replaces the published dashboard** with draft changes
- **Version control is maintained** throughout the process
- **Users can preview changes** before publishing
- **Draft changes can be discarded** to revert to published state

## New Steps Available

### 1. Edit Dashboard (`edit_dashboard`)
Update basic dashboard information like name, description, content, and metadata. Creates draft version.

### 2. Add Component (`add_component`)
Add a new thread component to the dashboard workflow. Creates draft version if dashboard is published.

### 3. Add Alert Component (`add_alert_component`)
Add a new alert component to the dashboard workflow. Creates draft version if dashboard is published.

### 4. Update Component (`update_component`)
Update an existing thread component in the dashboard workflow. Creates draft version if dashboard is published.

### 5. Remove Component (`remove_component`)
Remove a thread component from the dashboard workflow. Creates draft version if dashboard is published.

### 6. Get Draft Changes (`get_draft_changes`)
Check if there are pending draft changes and get draft information.

### 7. Get Dashboard Preview (`get_dashboard_preview`)
Get a preview of the dashboard with draft changes applied.

### 8. Discard Draft Changes (`discard_draft_changes`)
Discard all draft changes and revert to the published state.

### 9. Publish (`publish`)
Publish draft changes to replace the published dashboard.

## Component Attributes

Each component includes comprehensive metadata for better documentation and functionality:

### Core Attributes
- **`component_type`**: Type of component (chart, table, metric, insight, alert, etc.)
- **`question`**: The business question the component answers
- **`description`**: Detailed description of the component's purpose
- **`overview`**: High-level overview of the component's content

### Data & Query Attributes
- **`sql_query`**: The SQL query used to fetch data for the component
- **`data_count`**: Number of data points/records in the component
- **`sample_data`**: Sample data for preview and testing
- **`data_overview`**: Description of the data structure and content

### Reasoning & Analysis
- **`reasoning`**: Chain of thought explaining why this visualization/component was chosen
- **`summary`**: Concise summary of the component's key findings and insights
- **`executive_summary`**: High-level summary for executive consumption

### Visualization Schema
- **`chart_schema`**: Dictionary object defining the visualization structure:
  - `x_field`, `y_field`: Data fields for axes
  - `title`: Chart title
  - `x_axis_label`, `y_axis_label`: Axis labels
  - `color_scheme`: Color palette for the visualization
  - `show_grid`, `show_legend`: Display options
  - `animation`: Animation settings
  - `sort_order`: Data sorting preference

### Configuration & Metadata
- **`chart_config`** / **`table_config`**: Component-specific configuration
- **`configuration`**: General component settings
- **`metadata`**: Additional metadata and tags
- **`validation_results`**: Data quality and validation results

## Usage Examples

### Example 1: Edit Dashboard Basic Information (Draft Mode)

```python
from uuid import UUID
from workflowservices.app.services.workflow_orchestrator import WorkflowOrchestrator

# Initialize orchestrator
orchestrator = WorkflowOrchestrator(db_session, chroma_client)

# Edit dashboard information - creates draft version
result = await orchestrator.execute_workflow_step(
    user_id=UUID("user-id-here"),
    workflow_id=UUID("workflow-id-here"),
    step_name="edit_dashboard",
    step_data={
        "name": "Updated Dashboard Name",
        "description": "Updated dashboard description",
        "content": {
            "layout": "grid",
            "theme": "dark",
            "custom_settings": {"auto_refresh": True}
        },
        "metadata": {
            "category": "analytics",
            "tags": ["sales", "revenue"]
        }
    }
)

print(f"Dashboard draft updated: {result['dashboard_id']}")
print(f"Name: {result['name']}")
print(f"Description: {result['description']}")
print("Note: Changes are in draft mode and won't affect published dashboard until published")
```

### Example 2: Check Draft Changes

```python
# Check if there are pending draft changes
draft_info = await orchestrator.execute_workflow_step(
    user_id=UUID("user-id-here"),
    workflow_id=UUID("workflow-id-here"),
    step_name="get_draft_changes",
    step_data={}
)

print(f"Has draft changes: {draft_info['has_draft_changes']}")
if draft_info['has_draft_changes']:
    print(f"Last edited: {draft_info['last_edited_at']}")
    print(f"Edited by: {draft_info['edited_by']}")
    print(f"Changes: {draft_info['changes']}")
```

### Example 3: Preview Dashboard with Draft Changes

```python
# Get preview of dashboard with draft changes applied
preview = await orchestrator.execute_workflow_step(
    user_id=UUID("user-id-here"),
    workflow_id=UUID("workflow-id-here"),
    step_name="get_dashboard_preview",
    step_data={}
)

print(f"Dashboard Preview:")
print(f"Name: {preview['name']}")
print(f"Description: {preview['description']}")
print(f"Has draft changes: {preview['has_draft_changes']}")
print(f"Current version: {preview['version']}")
print(f"Draft info: {preview['draft_info']}")
```

### Example 2: Add a Thread Component

```python
# Add a chart component
result = await orchestrator.execute_workflow_step(
    user_id=UUID("user-id-here"),
    workflow_id=UUID("workflow-id-here"),
    step_name="add_component",
    step_data={
        "component_type": "chart",
        "question": "What is the sales trend over time?",
        "description": "Line chart showing monthly sales data",
        "overview": "Sales have been increasing steadily over the past 6 months",
        "chart_config": {
            "type": "line",
            "x_axis": "month",
            "y_axis": "sales_amount",
            "color": "#3498db"
        },
        "sql_query": "SELECT month, SUM(amount) as sales_amount FROM sales GROUP BY month ORDER BY month",
        "reasoning": "Line chart is the most effective visualization for time series data as it clearly shows trends, patterns, and changes over time. The continuous line helps identify seasonal patterns and growth trajectories in sales performance.",
        "summary": "Monthly sales data showing consistent upward trend with 15% average growth month-over-month, peaking in December at $2.1M.",
        "executive_summary": "Strong upward trend in sales performance",
        "data_overview": "12 months of data showing consistent growth",
        "visualization_data": {
            "chart_type": "line",
            "data_points": 12
        },
        "sample_data": [
            {"month": "2024-01", "sales_amount": 150000},
            {"month": "2024-02", "sales_amount": 165000}
        ],
        "metadata": {
            "source": "sales_database",
            "last_updated": "2024-01-15"
        },
        "chart_schema": {
            "x_field": "month",
            "y_field": "sales_amount",
            "title": "Monthly Sales Trend",
            "x_axis_label": "Month",
            "y_axis_label": "Sales Amount ($)",
            "color_scheme": "blue_gradient",
            "show_grid": True,
            "show_legend": False,
            "animation": "fade_in"
        },
        "data_count": 12,
        "validation_results": {
            "sql_valid": True,
            "data_quality": "high"
        },
        "thread_message_id": UUID("thread-message-id-here")  # Optional
    }
)

print(f"Component added: {result['component_id']}")
```

### Example 3: Add an Alert Component

```python
# Add an alert component
result = await orchestrator.execute_workflow_step(
    user_id=UUID("user-id-here"),
    workflow_id=UUID("workflow-id-here"),
    step_name="add_alert_component",
    step_data={
        "alert_type": "threshold",
        "severity": "high",
        "question": "Alert when sales drop below threshold",
        "description": "Monitor sales performance and alert when below expected levels",
        "condition_config": {
            "metric": "daily_sales",
            "operator": "less_than",
            "threshold": 10000
        },
        "threshold_config": {
            "value": 10000,
            "time_window": "daily",
            "comparison_period": "previous_week"
        },
        "notification_channels": ["email", "slack"],
        "escalation_config": {
            "levels": [
                {"delay_minutes": 15, "channels": ["email"]},
                {"delay_minutes": 60, "channels": ["slack", "email"]}
            ]
        },
        "cooldown_period": 3600,  # 1 hour in seconds
        "sql_query": "SELECT DATE(created_at) as date, SUM(amount) as daily_sales FROM sales GROUP BY DATE(created_at)",
        "reasoning": "Threshold-based alerting is essential for proactive sales monitoring. By setting a daily sales threshold of $10,000, we can quickly identify and respond to performance drops before they impact monthly targets. The alert triggers when sales fall below this threshold, allowing immediate investigation and corrective action.",
        "summary": "Daily sales monitoring alert that triggers when sales drop below $10,000 threshold, providing early warning for performance issues and enabling rapid response.",
        "executive_summary": "Critical alert for sales performance monitoring",
        "data_overview": "Daily sales monitoring with threshold-based alerts",
        "visualization_data": {
            "chart_type": "threshold_line",
            "threshold_line": 10000
        },
        "sample_data": [
            {"date": "2024-01-15", "daily_sales": 12000},
            {"date": "2024-01-16", "daily_sales": 8500}
        ],
        "metadata": {
            "alert_category": "performance",
            "business_impact": "high"
        },
        "chart_schema": {
            "x_field": "date",
            "y_field": "daily_sales",
            "threshold_field": "threshold_value",
            "title": "Daily Sales vs Threshold",
            "x_axis_label": "Date",
            "y_axis_label": "Daily Sales ($)",
            "threshold_color": "#ff6b6b",
            "data_color": "#4ecdc4",
            "show_threshold_line": True,
            "alert_zone_color": "#ffebee"
        },
        "data_count": 30,
        "validation_results": {
            "sql_valid": True,
            "threshold_reasonable": True
        },
        "thread_message_id": UUID("thread-message-id-here")  # Optional
    }
)

print(f"Alert component added: {result['component_id']}")
```

### Example 4: Update an Existing Component

```python
# Update a component
result = await orchestrator.execute_workflow_step(
    user_id=UUID("user-id-here"),
    workflow_id=UUID("workflow-id-here"),
    step_name="update_component",
    step_data={
        "component_id": UUID("component-id-here"),
        "update_data": {
            "question": "Updated question about sales performance",
            "description": "Updated description with more details",
            "chart_config": {
                "type": "bar",
                "x_axis": "quarter",
                "y_axis": "sales_amount",
                "color": "#e74c3c"
            },
            "configuration": {
                "auto_refresh": True,
                "refresh_interval": 300
            }
        }
    }
)

print(f"Component updated: {result['component_id']}")
```

### Example 5: Remove a Component

```python
# Remove a component
result = await orchestrator.execute_workflow_step(
    user_id=UUID("user-id-here"),
    workflow_id=UUID("workflow-id-here"),
    step_name="remove_component",
    step_data={
        "component_id": UUID("component-id-here")
    }
)

print(f"Component removed: {result['removed']}")
```

### Example 6: Complete Draft Workflow

```python
# Complete workflow: Edit -> Preview -> Publish or Discard

# Step 1: Make multiple edits (all create draft versions)
await orchestrator.execute_workflow_step(
    user_id=UUID("user-id-here"),
    workflow_id=UUID("workflow-id-here"),
    step_name="edit_dashboard",
    step_data={
        "name": "Updated Sales Dashboard",
        "description": "Comprehensive sales analytics dashboard"
    }
)

await orchestrator.execute_workflow_step(
    user_id=UUID("user-id-here"),
    workflow_id=UUID("workflow-id-here"),
    step_name="add_component",
    step_data={
        "component_type": "chart",
        "question": "What are the top products by sales?",
        "description": "Bar chart showing product performance",
        "chart_config": {
            "type": "bar",
            "x_axis": "product_name",
            "y_axis": "total_sales"
        }
    }
)

# Step 2: Check draft status
draft_info = await orchestrator.execute_workflow_step(
    user_id=UUID("user-id-here"),
    workflow_id=UUID("workflow-id-here"),
    step_name="get_draft_changes",
    step_data={}
)

print(f"Has draft changes: {draft_info['has_draft_changes']}")

# Step 3: Preview changes
preview = await orchestrator.execute_workflow_step(
    user_id=UUID("user-id-here"),
    workflow_id=UUID("workflow-id-here"),
    step_name="get_dashboard_preview",
    step_data={}
)

print(f"Preview name: {preview['name']}")
print(f"Preview has {len(preview['content'].get('components', []))} components")

# Step 4: Either publish or discard
# Option A: Publish changes (replaces published dashboard)
publish_result = await orchestrator.execute_workflow_step(
    user_id=UUID("user-id-here"),
    workflow_id=UUID("workflow-id-here"),
    step_name="publish",
    step_data={}
)

print(f"Published successfully: {publish_result}")

# Option B: Discard changes (revert to published state)
# discard_result = await orchestrator.execute_workflow_step(
#     user_id=UUID("user-id-here"),
#     workflow_id=UUID("workflow-id-here"),
#     step_name="discard_draft_changes",
#     step_data={}
# )
# print(f"Discarded successfully: {discard_result['discarded']}")
```

### Example 7: Batch Operations with Draft Management

```python
# Execute multiple steps in sequence with draft management
steps = [
    {
        "name": "edit_dashboard",
        "data": {
            "name": "Updated Sales Dashboard",
            "description": "Comprehensive sales analytics dashboard"
        }
    },
    {
        "name": "add_component",
        "data": {
            "component_type": "chart",
            "question": "What are the top products by sales?",
            "description": "Bar chart showing product performance",
            "chart_config": {
                "type": "bar",
                "x_axis": "product_name",
                "y_axis": "total_sales"
            },
            "sql_query": "SELECT product_name, SUM(total_sales) as total_sales FROM sales GROUP BY product_name ORDER BY total_sales DESC LIMIT 10",
            "reasoning": "Bar chart is the most effective visualization for comparing categorical data across different products. The horizontal bar layout allows for easy reading of product names while clearly showing the sales performance hierarchy.",
            "summary": "Top 10 products by sales volume, showing clear performance hierarchy with Product A leading at $2.5M in sales.",
            "chart_schema": {
                "x_field": "product_name",
                "y_field": "total_sales",
                "title": "Top Products by Sales",
                "x_axis_label": "Product Name",
                "y_axis_label": "Total Sales ($)",
                "color_scheme": "blue_gradient",
                "show_values": True,
                "sort_order": "desc"
            }
        }
    },
    {
        "name": "add_alert_component",
        "data": {
            "alert_type": "threshold",
            "severity": "medium",
            "question": "Alert for low inventory products",
            "condition_config": {
                "metric": "inventory_level",
                "operator": "less_than",
                "threshold": 10
            }
        }
    },
    {
        "name": "get_draft_changes",
        "data": {}
    }
]

results = await orchestrator.execute_workflow_batch(
    user_id=UUID("user-id-here"),
    workflow_id=UUID("workflow-id-here"),
    steps=steps
)

for result in results:
    print(f"Step {result['step']}: {'Success' if result['success'] else 'Failed'}")
    if result['success']:
        print(f"  Result: {result['result']}")
        if result['step'] == "get_draft_changes":
            print(f"  Has draft changes: {result['result']['has_draft_changes']}")
    else:
        print(f"  Error: {result['error']}")
```

## Error Handling

All steps include proper error handling and will return appropriate error messages if:

- The workflow doesn't exist
- The user doesn't have permission
- The component doesn't exist (for update/remove operations)
- Invalid data is provided
- The workflow is in an invalid state for the operation

## Version Control and State Management

### Draft vs Published States

The system maintains a clear separation between draft and published states:

- **Published Dashboard**: The live, active dashboard that users see
- **Draft Changes**: Stored in workflow metadata, not affecting the published dashboard
- **Version Control**: Each change creates a new workflow version for audit trails
- **Dashboard Versions**: Published changes create new dashboard versions

### State Transitions

```
DRAFT → CONFIGURING → CONFIGURED → SHARING → SHARED → SCHEDULING → SCHEDULED → PUBLISHING → PUBLISHED/ACTIVE
  ↓                                                                                                    ↑
  └─────────────────── EDITING (Draft Changes) ←─────────────────────────────────────────────────────┘
```

### Workflow States

- **DRAFT/CONFIGURING**: Normal editing workflow, changes apply directly
- **PUBLISHED/ACTIVE**: Draft editing mode, changes stored in metadata until published
- **Other States**: Editing may be restricted based on workflow requirements

### Version Management

- **Workflow Versions**: Track all changes and state transitions
- **Dashboard Versions**: Track published dashboard content changes
- **Draft Tracking**: Metadata tracks draft changes with timestamps and user info
- **Audit Trail**: Complete history of all modifications

## Integration with Existing Workflow

These new steps integrate seamlessly with the existing workflow steps:

- `configure_component` - Configure existing components
- `share` - Configure sharing settings  
- `schedule` - Set up scheduling
- `add_integrations` - Add external integrations
- `publish` - Publish the dashboard (now handles draft changes)

### Key Benefits

1. **Non-Destructive Editing**: Published dashboards remain stable during editing
2. **Preview Before Publish**: Users can review changes before making them live
3. **Rollback Capability**: Draft changes can be discarded to revert to published state
4. **Version Control**: Complete audit trail of all changes
5. **Collaborative Editing**: Multiple users can work on drafts without conflicts
6. **State Management**: Clear separation between draft and published states

The new editing steps provide a complete solution for managing dashboard content and components throughout the workflow lifecycle with proper version control and draft management.

## Related Documentation

- [Report Editing Steps](REPORT_EDITING_STEPS.md) - Similar draft-based editing workflow for reports
- [Workflow Orchestrator API](../app/services/workflow_orchestrator.py) - Complete API reference
- [Dashboard Workflow Service](../app/services/dashboard_workflow.py) - Service implementation details

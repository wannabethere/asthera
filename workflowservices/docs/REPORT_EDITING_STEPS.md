# Report Editing Steps in Workflow Orchestrator

This document describes the new report editing steps available in the Workflow Orchestrator for editing reports and managing sections with proper version control and draft management.

## Draft-Based Editing Workflow

The new editing system implements a **draft-based approach** for reports where:
- **Editing creates draft versions** that don't affect the published report
- **Changes are stored in workflow metadata** until explicitly published
- **Publishing replaces the published report** with draft changes
- **Version control is maintained** throughout the process
- **Users can preview changes** before publishing
- **Draft changes can be discarded** to revert to published state

## New Steps Available

### 1. Edit Report (`edit_report`)
Update basic report information like name, description, content, and metadata. Creates draft version.

### 2. Add Section (`add_section`)
Add a new section to the report workflow. Creates draft version if report is published.

### 3. Update Section (`update_section`)
Update an existing report section. Creates draft version if report is published.

### 4. Remove Section (`remove_section`)
Remove a report section from the workflow. Creates draft version if report is published.

### 5. Get Draft Changes (`get_draft_changes`)
Check if there are pending draft changes and get draft information.

### 6. Get Report Preview (`get_report_preview`)
Get a preview of the report with draft changes applied.

### 7. Discard Draft Changes (`discard_draft_changes`)
Discard all draft changes and revert to the published state.

### 8. Publish (`publish`)
Publish draft changes to replace the published report.

## Section Attributes

Each report section includes comprehensive metadata for better documentation and functionality:

### Core Attributes
- **`section_type`**: Type of section (executive_summary, data_analysis, charts, tables, insights, etc.)
- **`title`**: Section title/heading
- **`content`**: Main content/description of the section
- **`order`**: Display order within the report

### Data & Query Attributes
- **`sql_query`**: The SQL query used to fetch data for the section
- **`data_sources`**: List of data sources used in the section
- **`sample_data`**: Sample data for preview and testing
- **`data_overview`**: Description of the data structure and content

### Reasoning & Analysis
- **`reasoning`**: Chain of thought explaining why this section was included and how it contributes to the report
- **`summary`**: Concise summary of the section's key findings and insights
- **`executive_summary`**: High-level summary for executive consumption

### Visualization Schema
- **`chart_schema`**: Dictionary object defining visualization structure for charts in the section:
  - `x_field`, `y_field`: Data fields for axes
  - `title`: Chart title
  - `x_axis_label`, `y_axis_label`: Axis labels
  - `color_scheme`: Color palette for visualizations
  - `show_grid`, `show_legend`: Display options
  - `animation`: Animation settings
  - `sort_order`: Data sorting preference

### Configuration & Formatting
- **`formatting`**: Section-specific formatting options (font, colors, layout)
- **`charts`**: Array of chart configurations within the section
- **`tables`**: Table configurations and styling
- **`metadata`**: Additional metadata and tags

## Usage Examples

### Example 1: Edit Report Basic Information (Draft Mode)

```python
from uuid import UUID
from workflowservices.app.services.workflow_orchestrator import WorkflowOrchestrator

# Initialize orchestrator
orchestrator = WorkflowOrchestrator(db_session, chroma_client)

# Edit report information - creates draft version
result = await orchestrator.execute_workflow_step(
    user_id=UUID("user-id-here"),
    workflow_id=UUID("workflow-id-here"),
    step_name="edit_report",
    step_data={
        "name": "Updated Sales Report",
        "description": "Comprehensive sales analytics report",
        "content": {
            "template": "executive",
            "theme": "corporate",
            "custom_settings": {"auto_refresh": True}
        },
        "metadata": {
            "category": "analytics",
            "tags": ["sales", "revenue", "quarterly"]
        }
    }
)

print(f"Report draft updated: {result['report_id']}")
print(f"Name: {result['name']}")
print(f"Description: {result['description']}")
print("Note: Changes are in draft mode and won't affect published report until published")
```

### Example 2: Add Report Section

```python
# Add a new section to the report
result = await orchestrator.execute_workflow_step(
    user_id=UUID("user-id-here"),
    workflow_id=UUID("workflow-id-here"),
    step_name="add_section",
    step_data={
        "section_type": "executive_summary",
        "section_config": {
            "title": "Executive Summary",
            "content": "This report provides a comprehensive analysis of sales performance...",
            "sql_query": "SELECT month, SUM(amount) as total_sales, COUNT(*) as transaction_count FROM sales GROUP BY month ORDER BY month",
            "reasoning": "Executive summary section provides high-level insights for decision makers. Including sales trend visualization helps stakeholders quickly understand performance patterns and make informed decisions about resource allocation and strategy adjustments.",
            "summary": "Sales performance shows consistent growth with 15% average increase month-over-month, driven primarily by new customer acquisition and product expansion initiatives.",
            "formatting": {
                "font_size": 12,
                "font_weight": "bold",
                "alignment": "left"
            },
            "data_sources": ["sales_database", "customer_analytics"],
            "charts": [
                {
                    "type": "line",
                    "title": "Sales Trend",
                    "data_query": "SELECT month, SUM(amount) FROM sales GROUP BY month",
                    "chart_schema": {
                        "x_field": "month",
                        "y_field": "total_sales",
                        "title": "Monthly Sales Trend",
                        "x_axis_label": "Month",
                        "y_axis_label": "Sales Amount ($)",
                        "color_scheme": "corporate_blue",
                        "show_grid": True,
                        "show_legend": False
                    }
                }
            ]
        }
    }
)

print(f"Section added: {result['section_id']}")
```

### Example 3: Update Report Section

```python
# Update an existing section
result = await orchestrator.execute_workflow_step(
    user_id=UUID("user-id-here"),
    workflow_id=UUID("workflow-id-here"),
    step_name="update_section",
    step_data={
        "section_id": "section-id-here",
        "section_config": {
            "title": "Updated Executive Summary",
            "content": "Updated content with new insights...",
            "sql_query": "SELECT product, SUM(amount) as total_sales, AVG(amount) as avg_sale FROM sales GROUP BY product ORDER BY total_sales DESC",
            "reasoning": "Updated to include product-level analysis as it provides more granular insights for strategic decision making. Bar chart visualization allows for easy comparison across product categories and identification of top performers.",
            "summary": "Product analysis reveals Product A as the top performer with $2.5M in sales, followed by Product B at $1.8M. Average sale value varies significantly across products, indicating different market positioning strategies.",
            "formatting": {
                "font_size": 14,
                "font_weight": "bold",
                "alignment": "center"
            },
            "charts": [
                {
                    "type": "bar",
                    "title": "Updated Sales Chart",
                    "data_query": "SELECT product, SUM(amount) FROM sales GROUP BY product",
                    "chart_schema": {
                        "x_field": "product",
                        "y_field": "total_sales",
                        "title": "Sales by Product",
                        "x_axis_label": "Product",
                        "y_axis_label": "Total Sales ($)",
                        "color_scheme": "gradient_green",
                        "show_values": True,
                        "sort_order": "desc"
                    }
                }
            ]
        }
    }
)

print(f"Section updated: {result['section_id']}")
```

### Example 4: Remove Report Section

```python
# Remove a section
result = await orchestrator.execute_workflow_step(
    user_id=UUID("user-id-here"),
    workflow_id=UUID("workflow-id-here"),
    step_name="remove_section",
    step_data={
        "section_id": "section-id-here"
    }
)

print(f"Section removed: {result['removed']}")
```

### Example 5: Check Draft Changes

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

### Example 6: Preview Report with Draft Changes

```python
# Get preview of report with draft changes applied
preview = await orchestrator.execute_workflow_step(
    user_id=UUID("user-id-here"),
    workflow_id=UUID("workflow-id-here"),
    step_name="get_report_preview",
    step_data={}
)

print(f"Report Preview:")
print(f"Name: {preview['name']}")
print(f"Description: {preview['description']}")
print(f"Has draft changes: {preview['has_draft_changes']}")
print(f"Current version: {preview['version']}")
print(f"Sections: {len(preview['sections'])}")
print(f"Data sources: {len(preview['data_sources'])}")
print(f"Draft info: {preview['draft_info']}")
```

### Example 7: Complete Draft Workflow

```python
# Complete workflow: Edit -> Preview -> Publish or Discard

# Step 1: Make multiple edits (all create draft versions)
await orchestrator.execute_workflow_step(
    user_id=UUID("user-id-here"),
    workflow_id=UUID("workflow-id-here"),
    step_name="edit_report",
    step_data={
        "name": "Updated Sales Report",
        "description": "Comprehensive sales analytics report"
    }
)

await orchestrator.execute_workflow_step(
    user_id=UUID("user-id-here"),
    workflow_id=UUID("workflow-id-here"),
    step_name="add_section",
    step_data={
        "section_type": "data_analysis",
        "section_config": {
            "title": "Data Analysis",
            "content": "Detailed analysis of sales data...",
            "charts": [{"type": "pie", "title": "Sales by Region"}]
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
    step_name="get_report_preview",
    step_data={}
)

print(f"Preview name: {preview['name']}")
print(f"Preview has {len(preview['sections'])} sections")

# Step 4: Either publish or discard
# Option A: Publish changes (replaces published report)
publish_result = await orchestrator.execute_workflow_step(
    user_id=UUID("user-id-here"),
    workflow_id=UUID("workflow-id-here"),
    step_name="publish",
    step_data={
        "formats": ["pdf", "html"],
        "send_email": True,
        "upload_to_sharepoint": False
    }
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

### Example 8: Batch Operations with Draft Management

```python
# Execute multiple steps in sequence with draft management
steps = [
    {
        "name": "edit_report",
        "data": {
            "name": "Updated Sales Report",
            "description": "Comprehensive sales analytics report"
        }
    },
    {
        "name": "add_section",
        "data": {
            "section_type": "executive_summary",
            "section_config": {
                "title": "Executive Summary",
                "content": "Key findings and recommendations..."
            }
        }
    },
    {
        "name": "add_section",
        "data": {
            "section_type": "data_analysis",
            "section_config": {
                "title": "Data Analysis",
                "content": "Detailed analysis of sales performance...",
                "charts": [{"type": "line", "title": "Sales Trend"}]
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
- The section doesn't exist (for update/remove operations)
- Invalid data is provided
- The workflow is in an invalid state for the operation

## Version Control and State Management

### Draft vs Published States

The system maintains a clear separation between draft and published states:

- **Published Report**: The live, active report that users see
- **Draft Changes**: Stored in workflow metadata, not affecting the published report
- **Version Control**: Each change creates a new workflow version for audit trails
- **Report Versions**: Published changes create new report versions

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
- **Report Versions**: Track published report content changes
- **Draft Tracking**: Metadata tracks draft changes with timestamps and user info
- **Audit Trail**: Complete history of all modifications

## Integration with Existing Workflow

These new steps integrate seamlessly with the existing workflow steps:

- `configure_data_sources` - Configure data sources
- `configure_formatting` - Configure report formatting
- `preview` - Generate report preview
- `schedule` - Set up scheduling
- `publish` - Publish the report (now handles draft changes)

### Key Benefits

1. **Non-Destructive Editing**: Published reports remain stable during editing
2. **Preview Before Publish**: Users can review changes before making them live
3. **Rollback Capability**: Draft changes can be discarded to revert to published state
4. **Version Control**: Complete audit trail of all changes
5. **Collaborative Editing**: Multiple users can work on drafts without conflicts
6. **State Management**: Clear separation between draft and published states
7. **Section Management**: Full CRUD operations for report sections
8. **Content Preview**: See how the report will look with all changes applied

The new editing steps provide a complete solution for managing report content and sections throughout the workflow lifecycle with proper version control and draft management.

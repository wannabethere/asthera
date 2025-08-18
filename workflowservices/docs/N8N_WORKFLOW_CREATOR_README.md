# N8N Workflow Creator

The N8N Workflow Creator automatically generates n8n workflows for active dashboards, enabling automated data processing, sharing, and integration workflows.

## Overview

When a dashboard workflow is published and becomes active, the system automatically creates a corresponding n8n workflow JSON file. This workflow includes:

- **Trigger nodes** based on schedule configuration (cron, daily, weekly, etc.)
- **Data processing nodes** for each dashboard component (charts, tables, metrics)
- **Sharing nodes** for notifications and distribution
- **Integration nodes** for external services (Tableau, Power BI, Slack, etc.)

## Features

### Automatic Workflow Generation
- ✅ Automatically creates n8n workflows when dashboards become active
- ✅ Generates workflows based on dashboard components and configuration
- ✅ Includes all sharing, scheduling, and integration settings

### Flexible Trigger Options
- **Manual Trigger**: For on-demand execution
- **Cron Trigger**: Custom cron expressions for complex schedules
- **Daily Trigger**: Daily execution at specified time
- **Weekly Trigger**: Weekly execution on specified day
- **Real-time Trigger**: Immediate execution

### Component Support
- **Chart Components**: Data visualization and chart processing
- **Table Components**: Tabular data processing and analysis
- **Metric Components**: Key performance indicator calculations
- **Generic Components**: Custom data processing logic

### Integration Support
- **Tableau**: Dashboard publishing and data sync
- **Power BI**: Workspace integration and dataset updates
- **Slack**: Channel notifications and updates
- **Email**: Automated email distribution
- **S3**: Data export and storage
- **Webhooks**: Custom HTTP endpoint integration

## How It Works

### 1. Dashboard Workflow Creation
```python
# Create a dashboard workflow
workflow, dashboard = dashboard_service.create_workflow(
    user_id=user_id,
    dashboard_name="Sales Dashboard",
    dashboard_description="Q4 2024 sales analytics"
)
```

### 2. Component Configuration
```python
# Add components to the workflow
component = dashboard_service.add_thread_component(
    user_id=user_id,
    workflow_id=workflow.id,
    component_data=ThreadComponentCreate(
        component_type=ComponentType.CHART,
        question="Sales Trend Analysis",
        chart_config={
            "type": "line",
            "data_source": "sales_db",
            "x_axis": "month",
            "y_axis": "revenue"
        }
    )
)
```

### 3. Sharing and Integration Setup
```python
# Configure sharing
share_configs = dashboard_service.configure_sharing(
    user_id=user_id,
    workflow_id=workflow.id,
    share_config=ShareConfigCreate(
        share_type=ShareType.TEAM,
        target_ids=["sales-team"],
        permissions={"view": True, "edit": False}
    )
)

# Configure integrations
integrations = dashboard_service.configure_integrations(
    user_id=user_id,
    workflow_id=workflow.id,
    integration_configs=[
        IntegrationConfigCreate(
            integration_type=IntegrationType.SLACK,
            connection_config={"webhook_url": "..."},
            mapping_config={"channel": "#sales-updates"}
        )
    ]
)
```

### 4. Automatic n8n Workflow Generation
When the dashboard is published, the n8n workflow is automatically created:

```python
# Publish dashboard (triggers n8n workflow creation)
result = dashboard_service.publish_dashboard(
    user_id=user_id,
    workflow_id=workflow.id
)

# The result includes n8n workflow information
print(result["publish_results"]["n8n_workflow"])
# Output: {
#   "success": True,
#   "file_path": "/path/to/dashboard_123_456.json",
#   "filename": "dashboard_123_456.json"
# }
```

## Generated n8n Workflow Structure

### Example Workflow JSON
```json
{
  "name": "Dashboard Workflow - Sales Dashboard",
  "nodes": [
    {
      "id": "trigger_weekly",
      "name": "Weekly Trigger",
      "type": "n8n-nodes-base.cron",
      "typeVersion": 1,
      "position": [240, 300],
      "parameters": {
        "rule": {
          "hour": "9",
          "minute": "0",
          "dayOfMonth": "*",
          "month": "*",
          "dayOfWeek": "1"
        }
      }
    },
    {
      "id": "chart_sales_trend",
      "name": "Chart: Sales Trend Analysis",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [480, 300],
      "parameters": {
        "jsCode": "// Chart processing logic..."
      }
    },
    {
      "id": "slack_share",
      "name": "Slack Share: #sales-updates",
      "type": "n8n-nodes-base.slack",
      "typeVersion": 1,
      "position": [1200, 200],
      "parameters": {
        "channel": "#sales-updates",
        "text": "Dashboard update notification"
      }
    }
  ],
  "connections": {
    "trigger_weekly": {
      "main": [[{"node": "chart_sales_trend", "type": "main", "index": 0}]]
    },
    "chart_sales_trend": {
      "main": [[{"node": "slack_share", "type": "main", "index": 0}]]
    }
  }
}
```

## API Endpoints

### N8N Workflow Management

#### Create n8n Workflow
```http
POST /api/v1/workflows/{workflow_id}/n8n/create
```
Manually create n8n workflow for an existing active dashboard.

#### Get n8n Workflow Status
```http
GET /api/v1/workflows/{workflow_id}/n8n/status
```
Get the status of n8n workflow for a dashboard.

#### List All n8n Workflows
```http
GET /api/v1/workflows/n8n/workflows
```
List all generated n8n workflow files.

#### Delete n8n Workflow
```http
DELETE /api/v1/workflows/{workflow_id}/n8n/delete
```
Delete n8n workflow file for a dashboard.

## File Management

### Output Directory
Workflows are saved to the `n8n_workflows` directory by default. You can customize this:

```python
creator = N8nWorkflowCreator(output_dir="custom_workflow_directory")
```

### File Naming Convention
Files follow the pattern: `dashboard_{dashboard_id}_{workflow_id}.json`

### File Operations
```python
# List all workflow files
workflow_files = creator.list_workflow_files()

# Get specific workflow file path
file_path = creator.get_workflow_file_path(dashboard_id, workflow_id)

# Delete workflow file
deleted = creator.delete_workflow_file(dashboard_id, workflow_id)
```

## Configuration Options

### Schedule Types
- **ONCE**: Single execution at specified date/time
- **HOURLY**: Every hour
- **DAILY**: Daily at specified time
- **WEEKLY**: Weekly on specified day
- **MONTHLY**: Monthly execution
- **CRON**: Custom cron expressions
- **REALTIME**: Immediate execution

### Component Types
- **QUESTION**: Text-based questions and descriptions
- **CHART**: Data visualization components
- **TABLE**: Tabular data components
- **METRIC**: Key performance indicators
- **OVERVIEW**: Summary and overview components
- **INSIGHT**: Data insights and analysis
- **NARRATIVE**: Text-based narratives

### Share Types
- **USER**: Individual user sharing
- **TEAM**: Team-based sharing
- **PROJECT**: Project-level sharing
- **WORKSPACE**: Workspace-wide sharing
- **EMAIL**: Email-based sharing
- **PUBLIC_LINK**: Public link sharing

### Integration Types
- **TABLEAU**: Tableau Server/Online integration
- **POWERBI**: Power BI integration
- **SLACK**: Slack notifications
- **TEAMS**: Microsoft Teams integration
- **EMAIL**: Email distribution
- **WEBHOOK**: Custom webhook endpoints
- **GOOGLE_SHEETS**: Google Sheets integration
- **SNOWFLAKE**: Snowflake data warehouse
- **S3**: Amazon S3 storage
- **AZURE_BLOB**: Azure Blob storage

## Error Handling

The system includes comprehensive error handling:

- **Graceful Degradation**: n8n workflow creation errors don't fail dashboard publishing
- **Error Logging**: All errors are logged with context
- **Retry Mechanisms**: Failed workflows can be regenerated
- **Status Tracking**: Track workflow generation success/failure

## Best Practices

### 1. Workflow Design
- Keep workflows simple and focused
- Use meaningful node names and descriptions
- Test workflows in n8n before production use

### 2. Security
- Encrypt sensitive connection configurations
- Use environment variables for API keys
- Implement proper authentication for integrations

### 3. Monitoring
- Monitor workflow execution status
- Set up alerts for failed workflows
- Track workflow performance metrics

### 4. Maintenance
- Regularly review and update workflows
- Clean up unused workflow files
- Version control workflow configurations

## Troubleshooting

### Common Issues

#### Workflow Not Generated
- Check if dashboard is active
- Verify workflow state is ACTIVE
- Check error logs for generation failures

#### Integration Failures
- Verify connection configurations
- Check API credentials and permissions
- Test integration endpoints manually

#### Schedule Issues
- Verify cron expressions
- Check timezone settings
- Ensure schedule is active

### Debug Mode
Enable debug logging to troubleshoot issues:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Examples

### Complete Dashboard Workflow
See `examples/n8n_workflow_example.py` for a complete example of:
- Creating a dashboard workflow
- Adding components
- Configuring sharing and integrations
- Publishing and generating n8n workflow

### Custom n8n Workflows
You can extend the system to support custom n8n workflow templates:

```python
class CustomN8nWorkflowCreator(N8nWorkflowCreator):
    def _generate_custom_workflow(self, dashboard, workflow):
        # Custom workflow generation logic
        pass
```

## Future Enhancements

- **Workflow Templates**: Pre-built workflow templates for common use cases
- **Visual Editor**: Web-based workflow builder interface
- **Workflow Versioning**: Track changes and rollback workflows
- **Advanced Scheduling**: More sophisticated scheduling options
- **Workflow Analytics**: Monitor and analyze workflow performance
- **Integration Marketplace**: Community-contributed integrations

## Support

For questions and support:
- Check the troubleshooting section
- Review error logs and status endpoints
- Test with the example scripts
- Consult the API documentation

## License

This project is part of the ComplianceSpark platform. Please refer to the main project license for terms and conditions.

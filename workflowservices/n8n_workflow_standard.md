# N8N Workflow Standard Structure

This document describes the standardized n8n workflow structure implemented for all dashboard and report workflows.

## Standard Workflow Pattern

All n8n workflows follow this consistent pattern:

```
Trigger/Scheduled Trigger → Start → Call render/alert (API Call) → Check alert condition (API Call) → If yes → Send to integration
```

## Workflow Components

### 1. Trigger Node
- **Manual Trigger**: For on-demand execution
- **Cron Trigger**: For scheduled execution based on schedule configuration
- **Webhook Trigger**: For external system triggers

### 2. Start Node
- Initializes workflow variables
- Sets workflow type (dashboard/report)
- Records execution timestamp
- Prepares data for downstream processing

### 3. Render/Alert API Call Node
- **Dashboard Workflows**: Calls `/api/workflows/{workflow_id}/render`
- **Report Workflows**: Calls `/api/workflows/{workflow_id}/render-report`
- Processes dashboard/report components
- Generates rendered content
- Evaluates alert conditions

### 4. Alert Condition Check Node
- **With Alerts**: Calls `/api/workflows/{workflow_id}/check-alerts`
- **Without Alerts**: Pass-through node that sets `alert_triggered: false`
- Determines if alert conditions are met
- Sets `alert_triggered` and `alert_conditions_met` flags

### 5. Integration Nodes (Conditional)
- Only execute if `alert_triggered: true`
- Each integration has:
  - **IF Condition Node**: Checks if alerts are triggered
  - **Action Node**: Performs the actual integration action

## Supported Integrations

### Microsoft Teams
- **Condition**: `alert_triggered == true`
- **Action**: Posts adaptive card to specified Teams channel
- **Configuration**: Channel ID, team ID, message content

### Cornerstone OnDemand
- **Condition**: `alert_triggered == true`
- **Action**: Publishes content to specified course/module
- **Configuration**: Course ID, module ID, content type

### Slack
- **Condition**: `alert_triggered == true`
- **Action**: Posts message to specified Slack channel
- **Configuration**: Channel ID, message content

### Other Integrations
- Tableau, PowerBI, S3, etc.
- All follow the same conditional pattern

## Workflow Execution Flow

1. **Trigger**: Workflow is initiated (manual, scheduled, or webhook)
2. **Start**: Initialize workflow context and variables
3. **Render**: Generate dashboard/report content and evaluate alerts
4. **Check Alerts**: Determine if any alert conditions are met
5. **Conditional Integration**: If alerts triggered, send to configured integrations

## API Endpoints

### Dashboard Workflows
- `POST /api/workflows/{workflow_id}/render`
- `POST /api/workflows/{workflow_id}/check-alerts`

### Report Workflows
- `POST /api/workflows/{workflow_id}/render-report`
- `POST /api/workflows/{workflow_id}/check-alerts`

## Configuration

### Environment Variables
- `BASE_URL`: Base URL for API calls
- Authentication credentials for integrations

### Workflow Parameters
- `workflow_type`: "dashboard" or "report"
- `dashboard_id`/`report_id`: Target resource ID
- `workflow_id`: Workflow instance ID
- `components`: Array of component configurations
- `alert_triggered`: Boolean flag for alert status
- `alert_conditions_met`: Boolean flag for condition status

## Benefits of Standardization

1. **Consistency**: All workflows follow the same pattern
2. **Maintainability**: Easy to understand and modify
3. **Reliability**: Proven execution flow
4. **Scalability**: Easy to add new integrations
5. **Debugging**: Clear execution path for troubleshooting

## Example Workflow JSON Structure

```json
{
  "name": "Dashboard Workflow - Sales Dashboard",
  "nodes": [
    {
      "id": "trigger_cron",
      "name": "Cron Trigger",
      "type": "n8n-nodes-base.cron"
    },
    {
      "id": "start_node",
      "name": "Start",
      "type": "n8n-nodes-base.set"
    },
    {
      "id": "render_api_node",
      "name": "Render Dashboard/Alert",
      "type": "n8n-nodes-base.httpRequest"
    },
    {
      "id": "alert_check_node",
      "name": "Check Alert Conditions",
      "type": "n8n-nodes-base.httpRequest"
    },
    {
      "id": "teams_123",
      "name": "Microsoft Teams Integration",
      "type": "n8n-nodes-base.if"
    },
    {
      "id": "teams_action_123",
      "name": "Send to Teams",
      "type": "n8n-nodes-base.microsoftTeams"
    }
  ],
  "connections": {
    "trigger_cron": {
      "main": [["start_node"]]
    },
    "start_node": {
      "main": [["render_api_node"]]
    },
    "render_api_node": {
      "main": [["alert_check_node"]]
    },
    "alert_check_node": {
      "main": [["teams_123"]]
    },
    "teams_123": {
      "main": [["teams_action_123"]]
    }
  }
}
```

This standardized structure ensures that all workflows are predictable, maintainable, and follow the same execution pattern regardless of the specific dashboard or report being processed.

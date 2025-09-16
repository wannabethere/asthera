# Integration Examples: Teams and Cornerstone

This document provides examples of how to use the newly added Microsoft Teams and Cornerstone OnDemand integrations in the workflow system.

## Microsoft Teams Integration

### Dashboard Integration

```python
# Example: Configure Teams integration for dashboard
integration_config = IntegrationConfigCreate(
    integration_type=IntegrationType.TEAMS,
    connection_config={
        "tenant_id": "your-tenant-id",
        "client_id": "your-client-id",
        "client_secret": "your-client-secret"
    },
    mapping_config={
        "channel_id": "19:channel-id@thread.tacv2",
        "team_id": "team-id",
        "channel": "General"
    }
)
```

### Report Integration

```python
# Example: Publish report to Teams
publish_options = {
    "formats": ["pdf", "html"],
    "send_to_teams": True,
    "teams_config": {
        "channel_id": "19:channel-id@thread.tacv2",
        "team_id": "team-id"
    }
}
```

## Cornerstone OnDemand Integration

### Dashboard Integration

```python
# Example: Configure Cornerstone integration for dashboard
integration_config = IntegrationConfigCreate(
    integration_type=IntegrationType.CORNERSTONE,
    connection_config={
        "api_key": "your-api-key",
        "base_url": "https://your-tenant.cornerstoneondemand.com",
        "username": "your-username",
        "password": "your-password"
    },
    mapping_config={
        "course_id": "course-123",
        "module_id": "module-456"
    }
)
```

### Report Integration

```python
# Example: Publish report to Cornerstone
publish_options = {
    "formats": ["pdf", "html"],
    "publish_to_cornerstone": True,
    "cornerstone_config": {
        "course_id": "course-123",
        "module_id": "module-456"
    }
}
```

## N8N Workflow Integration

The system automatically generates N8N workflows that include:

1. **Teams Integration Node**: Uses the Microsoft Teams node to post adaptive cards with dashboard/report information
2. **Cornerstone Integration Node**: Uses HTTP requests to post content to Cornerstone courses/modules

## Configuration Parameters

### Teams Integration
- `channel_id`: The Teams channel ID where content will be posted
- `team_id`: The Teams team ID
- `channel`: Human-readable channel name

### Cornerstone Integration
- `course_id`: The Cornerstone course ID where content will be published
- `module_id`: The specific module within the course
- `content_type`: Type of content (dashboard/report)

## Authentication

Both integrations support various authentication methods:
- OAuth 2.0 (recommended for production)
- API Key authentication
- Basic authentication

## Error Handling

The integrations include comprehensive error handling and will return detailed status information in the publish results, including:
- Success/failure status
- Generated URLs
- Error messages (if any)
- Integration-specific IDs

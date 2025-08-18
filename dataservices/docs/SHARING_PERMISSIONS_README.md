# Sharing Permissions Integration

This document describes the sharing permissions functionality that automatically generates dummy data for teams, workspaces, and projects and stores it as part of the project metadata.

## Overview

The sharing permissions system integrates with the dataset creation workflow to automatically generate and store sharing permissions. It creates realistic dummy data for testing purposes and stores it in the domain/project metadata for future use.

## Architecture

### Components

1. **SharingPermissionsService** - Core service for generating and managing permissions
2. **Dummy Data Generation** - Creates realistic test data for teams, workspaces, and projects
3. **Workflow Integration** - Automatically called during dataset creation
4. **Fallback Data Generation** - Provides fallback data if generation fails

### Data Flow

```
Dataset Creation → Table Addition → Permissions Generation → Storage → Workflow Commit
                     ↓
              Dummy Data Generation
                     ↓
              Users, Teams, Workspaces, Projects
                     ↓
              Store in Domain Metadata
```

## Data Generation

### Generated Data Types

- **Users** - Team members with various roles (admin, member, viewer)
- **Teams** - Different functional teams (Data Science, Engineering, Product, Analytics)
- **Workspaces** - Team-specific workspaces for collaboration
- **Projects** - Various project types (Customer Analytics, Sales Dashboard, ML Models, etc.)
- **Organizations** - Company information with industry and size details

### Data Structure

The service generates realistic data with:
- Proper relationships between entities
- Varied project counts per workspace
- Different team sizes and member counts
- Industry-specific organization details
- Consistent naming conventions

## Integration Points

### 1. Dataset Creation

Permissions are automatically generated after creating a dataset:

```python
# After dataset creation
await workflow_service.fetch_and_store_sharing_permissions(domain_id)
```

### 2. Table Addition

Permissions are refreshed after adding each table:

```python
# After table creation
await workflow_service.fetch_and_store_sharing_permissions(dataset.domain_id)
```

### 3. Workflow Commit

Final permissions are generated before committing the workflow:

```python
# Before workflow commit
await workflow_service.fetch_and_store_sharing_permissions(domain.domain_id)
```

## Data Structure

### Permissions Data

```json
{
  "users": [
    {
      "id": "user-123",
      "name": "John Doe",
      "email": "john@example.com",
      "role": "admin",
      "is_active": true
    }
  ],
  "teams": [
    {
      "id": "team-456",
      "name": "Data Science Team",
      "description": "Team focused on data analysis and machine learning",
      "is_active": true,
      "created_by": "user-123",
      "owner_id": "user-123",
      "member_count": 5
    }
  ],
  "workspaces": [
    {
      "id": "workspace-789",
      "name": "Data Science Team Workspace 1",
      "description": "Workspace for Data Science Team projects and collaboration",
      "team_id": "team-456",
      "created_by": "user-123",
      "project_count": 3,
      "is_active": true
    }
  ],
  "projects": [
    {
      "id": "project-101",
      "name": "Customer Analytics - Data Science Team Workspace 1",
      "description": "Customer behavior analysis and insights for Data Science Team Workspace 1",
      "workspace_id": "workspace-789",
      "team_id": "team-456",
      "status": "active",
      "created_at": "2024-01-01T12:00:00Z",
      "member_count": 4
    }
  ],
  "organizations": [
    {
      "id": "org-202",
      "name": "Acme Corporation",
      "domain": "acme.com",
      "industry": "Technology",
      "size": "1000-5000 employees",
      "location": "San Francisco, CA"
    }
  ],
  "fetched_at": "2024-01-01T12:00:00Z",
  "user_id": "user-123",
  "source": "dummy_generated"
}
```

### Stored Permissions Metadata

```json
{
  "project_id": "domain-123",
  "permissions": { /* permissions data */ },
  "stored_at": "2024-01-01T12:00:00Z",
  "version": "1.0",
  "metadata": {
    "total_users": 5,
    "total_teams": 4,
    "total_workspaces": 8,
    "total_projects": 24,
    "total_organizations": 3
  }
}
```

## Configuration

### Service Initialization

```python
from app.service.sharing_permissions_service import SharingPermissionsService

# Initialize service (no configuration needed)
service = SharingPermissionsService()
```

### No External Dependencies

The service is completely self-contained:
- No external API calls
- No network dependencies
- No configuration files required
- Works offline

## Error Handling

### Generation Failures

If data generation fails, the service falls back to minimal data:

```python
try:
    permissions = await service.fetch_sharing_permissions(user_id)
except Exception as e:
    # Fallback to minimal data
    permissions = service._generate_fallback_permissions(user_id)
```

### Non-Blocking Integration

Permissions generation is non-blocking - if it fails, the workflow continues:

```python
# Generate permissions (non-blocking)
try:
    await workflow_service.fetch_and_store_sharing_permissions(domain_id)
except Exception as e:
    logger.warning(f"Failed to generate sharing permissions: {str(e)}")
    # Continue with workflow
```

## Usage Examples

### Manual Permissions Generation

```python
from app.service.sharing_permissions_service import SharingPermissionsService

service = SharingPermissionsService()

# Generate permissions for a user
permissions = await service.fetch_sharing_permissions("user-123")

# Store in a project
stored = await service.store_permissions_in_project("project-456", permissions)

# Update permissions
updated = await service.update_project_permissions("project-456", "user-123")
```

### Workflow Integration

```python
from app.service.project_workflow_service import DomainWorkflowService

workflow_service = DomainWorkflowService(user_id, session_id)

# Permissions are automatically generated during workflow steps
await workflow_service.add_dataset(dataset_data)
await workflow_service.add_table(table_request, domain_context)
await workflow_service.commit_workflow(db)
```

## Testing

### Test Script

Run the test script to verify functionality:

```bash
cd dataservices
python test_sharing_permissions.py
```

### Test Coverage

The test script covers:
- Permissions generation
- Fallback data generation
- Permissions storage
- Workflow integration
- Error handling

## Benefits

1. **Automatic Generation** - No manual permission configuration needed
2. **Realistic Data** - Generated data mimics real-world scenarios
3. **Self-Contained** - No external dependencies or API calls
4. **Integrated** - Seamlessly part of the dataset creation workflow
5. **Extensible** - Easy to customize data generation logic

## Future Enhancements

1. **Custom Data Templates** - User-defined data generation patterns
2. **Data Variation** - More diverse and realistic data generation
3. **Permission Rules** - Configurable permission hierarchies
4. **Data Export** - Export generated data for external use
5. **Real-time Updates** - Dynamic data generation based on context

## Troubleshooting

### Common Issues

1. **Data Generation Failures**
   - Check Python environment
   - Verify UUID generation works
   - Check logging for error details

2. **Storage Issues**
   - Check database connectivity
   - Verify domain exists
   - Check user permissions

3. **Workflow Integration Issues**
   - Verify service initialization
   - Check error handling
   - Review workflow logs

### Debug Logging

Enable debug logging to troubleshoot issues:

```python
import logging
logging.getLogger("app.service.sharing_permissions_service").setLevel(logging.DEBUG)
```

## Support

For issues or questions about the sharing permissions functionality:

1. Check the logs for error messages
2. Run the test script to verify functionality
3. Review this documentation
4. Check workflow integration points
5. Contact the development team

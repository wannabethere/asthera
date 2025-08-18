# Data Setup Workflow

This document describes the new data setup workflow endpoints that provide explicit control over the sharing permissions and domain setup process.

## Overview

The data setup workflow provides a structured approach to setting up domains for data creation. It includes dedicated endpoints for:
- Setting up sharing permissions explicitly
- Checking setup status
- Executing complete data setup workflows
- Monitoring workflow progress

## API Endpoints

### 1. Setup Sharing Permissions

**Endpoint:** `POST /workflow/{domain_id}/setup-sharing-permissions`

**Purpose:** Explicitly set up sharing permissions for a domain as part of the data setup workflow.

**Request:**
```http
POST /workflow/{domain_id}/setup-sharing-permissions
X-User-Id: {user_id}
X-Session-Id: {session_id}
```

**Response:**
```json
{
  "status": "success",
  "message": "Sharing permissions setup completed successfully",
  "domain_id": "domain-123",
  "setup_completed_at": "2024-01-01T12:00:00Z",
  "setup_by": "user-456",
  "permissions": {
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
  },
  "workflow_step": "data_setup",
  "next_steps": [
    "Continue with dataset creation",
    "Add tables to datasets",
    "Configure relationships between tables",
    "Commit workflow when ready"
  ]
}
```

### 2. Check Sharing Permissions Status

**Endpoint:** `GET /workflow/{domain_id}/sharing-permissions-status`

**Purpose:** Check the current status of sharing permissions setup for a domain.

**Request:**
```http
GET /workflow/{domain_id}/sharing-permissions-status
X-User-Id: {user_id}
X-Session-Id: {session_id}
```

**Response (Setup Completed):**
```json
{
  "domain_id": "domain-123",
  "status": "setup_completed",
  "setup_completed_at": "2024-01-01T12:00:00Z",
  "setup_by": "user-456",
  "workflow_step": "data_setup",
  "permissions_summary": {
    "total_users": 5,
    "total_teams": 4,
    "total_workspaces": 8,
    "total_projects": 24,
    "total_organizations": 3
  },
  "can_proceed": true,
  "message": "Sharing permissions are already set up for this domain"
}
```

**Response (Not Setup):**
```json
{
  "domain_id": "domain-123",
  "status": "not_setup",
  "setup_completed_at": null,
  "setup_by": null,
  "workflow_step": null,
  "permissions_summary": {
    "total_users": 0,
    "total_teams": 0,
    "total_workspaces": 0,
    "total_projects": 0,
    "total_organizations": 0
  },
  "can_proceed": false,
  "message": "Sharing permissions need to be set up before proceeding",
  "next_action": "Call POST /{domain_id}/setup-sharing-permissions to set up permissions"
}
```

### 3. Execute Complete Data Setup Workflow

**Endpoint:** `POST /workflow/{domain_id}/data-setup-workflow`

**Purpose:** Execute the complete data setup workflow for a domain, orchestrating all setup steps.

**Request:**
```http
POST /workflow/{domain_id}/data-setup-workflow
X-User-Id: {user_id}
X-Session-Id: {session_id}
Content-Type: application/json

{
  "setup_steps": [
    "sharing_permissions",
    "domain_validation",
    "workflow_initialization",
    "ready_for_datasets"
  ]
}
```

**Response:**
```json
{
  "domain_id": "domain-123",
  "workflow_started_at": "2024-01-01T12:00:00Z",
  "executed_by": "user-456",
  "steps": {
    "sharing_permissions": {
      "status": "completed",
      "result": { /* permissions result */ },
      "completed_at": "2024-01-01T12:00:01Z"
    },
    "domain_validation": {
      "status": "completed",
      "result": {
        "domain_exists": true,
        "status_valid": true,
        "has_required_fields": true,
        "can_proceed": true
      },
      "completed_at": "2024-01-01T12:00:02Z"
    },
    "workflow_initialization": {
      "status": "completed",
      "result": {"workflow_state_initialized": true},
      "completed_at": "2024-01-01T12:00:03Z"
    },
    "ready_for_datasets": {
      "status": "completed",
      "result": {"ready_for_datasets": true},
      "completed_at": "2024-01-01T12:00:04Z"
    }
  },
  "overall_status": "completed",
  "message": "Data setup workflow completed successfully",
  "completed_at": "2024-01-01T12:00:04Z"
}
```

## Workflow Steps

### Default Steps

The complete data setup workflow includes these default steps:

1. **sharing_permissions** - Generate and store sharing permissions
2. **domain_validation** - Validate domain configuration and status
3. **workflow_initialization** - Initialize workflow state
4. **ready_for_datasets** - Mark domain as ready for dataset creation

### Custom Steps

You can customize the workflow by specifying only the steps you need:

```json
{
  "setup_steps": ["sharing_permissions", "domain_validation"]
}
```

## Usage Examples

### Basic Setup Flow

```python
import httpx

async def setup_domain_for_data_creation(domain_id: str, user_id: str, session_id: str):
    """Set up a domain for data creation"""
    
    base_url = "http://localhost:8000/workflow"
    headers = {
        "X-User-Id": user_id,
        "X-Session-Id": session_id,
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        # Step 1: Check current status
        status_response = await client.get(
            f"{base_url}/{domain_id}/sharing-permissions-status",
            headers=headers
        )
        status = status_response.json()
        
        if status["status"] == "not_setup":
            # Step 2: Setup sharing permissions
            setup_response = await client.post(
                f"{base_url}/{domain_id}/setup-sharing-permissions",
                headers=headers
            )
            setup_result = setup_response.json()
            print(f"Permissions setup completed: {setup_result['message']}")
        
        # Step 3: Execute complete workflow
        workflow_response = await client.post(
            f"{base_url}/{domain_id}/data-setup-workflow",
            headers=headers
        )
        workflow_result = workflow_response.json()
        
        if workflow_result["overall_status"] == "completed":
            print("Domain is ready for data creation!")
            return True
        else:
            print(f"Workflow failed: {workflow_result['message']}")
            return False
```

### Step-by-Step Setup

```python
async def step_by_step_setup(domain_id: str, user_id: str, session_id: str):
    """Set up domain step by step"""
    
    base_url = "http://localhost:8000/workflow"
    headers = {
        "X-User-Id": user_id,
        "X-Session-Id": session_id,
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        # Step 1: Setup sharing permissions only
        permissions_response = await client.post(
            f"{base_url}/{domain_id}/data-setup-workflow",
            headers=headers,
            json={"setup_steps": ["sharing_permissions"]}
        )
        
        # Step 2: Setup workflow initialization
        workflow_response = await client.post(
            f"{base_url}/{domain_id}/data-setup-workflow",
            headers=headers,
            json={"setup_steps": ["workflow_initialization"]}
        )
        
        # Step 3: Mark as ready for datasets
        ready_response = await client.post(
            f"{base_url}/{domain_id}/data-setup-workflow",
            headers=headers,
            json={"setup_steps": ["ready_for_datasets"]}
        )
        
        return {
            "permissions": permissions_response.json(),
            "workflow": workflow_response.json(),
            "ready": ready_response.json()
        }
```

## Integration with Existing Workflow

### Automatic vs. Explicit Setup

The system supports both approaches:

1. **Automatic Setup** (existing):
   - Permissions are generated automatically during dataset/table creation
   - Integrated into the natural workflow
   - Non-blocking

2. **Explicit Setup** (new):
   - Dedicated endpoints for setup control
   - Can be called before data creation
   - Provides setup status and validation

### Workflow States

```
Domain Created (draft)
        ↓
[Optional] Setup Sharing Permissions
        ↓
[Optional] Execute Data Setup Workflow
        ↓
Ready for Dataset Creation
        ↓
Add Datasets & Tables
        ↓
Commit Workflow (draft_ready)
```

## Error Handling

### Setup Failures

If any step fails, the workflow continues but marks that step as failed:

```json
{
  "steps": {
    "sharing_permissions": {
      "status": "failed",
      "error": "Service unavailable",
      "failed_at": "2024-01-01T12:00:01Z"
    }
  },
  "overall_status": "failed",
  "failed_steps": ["sharing_permissions"]
}
```

### Validation Errors

The endpoints include comprehensive validation:

- Domain existence check
- Status validation (draft/draft_ready only)
- Required field validation
- User permission checks

## Testing

### Test Script

Run the comprehensive test script:

```bash
cd dataservices
python test_data_setup_workflow.py
```

### Test Coverage

The test script covers:
- Sharing permissions setup
- Status checking
- Complete workflow execution
- Custom step execution
- Error handling

## Benefits

1. **Explicit Control** - Dedicated endpoints for setup control
2. **Status Tracking** - Clear visibility into setup progress
3. **Flexible Workflow** - Customizable setup steps
4. **Integration Ready** - Works with existing automatic setup
5. **Error Handling** - Comprehensive error reporting and recovery

## Best Practices

1. **Check Status First** - Always check current status before setup
2. **Use Complete Workflow** - Use the complete workflow for full setup
3. **Handle Failures** - Check overall status and handle failed steps
4. **Monitor Progress** - Use the status endpoints to track progress
5. **Customize as Needed** - Use custom steps for specific requirements

## Future Enhancements

1. **Workflow Templates** - Predefined workflow configurations
2. **Rollback Support** - Ability to undo setup steps
3. **Progress Callbacks** - Real-time progress updates
4. **Batch Operations** - Setup multiple domains at once
5. **Audit Trail** - Complete setup history tracking

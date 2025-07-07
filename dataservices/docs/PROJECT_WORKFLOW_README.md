# Project Workflow System

This document describes the project workflow system that manages the creation and management of data projects with tables, datasets, and enhanced documentation.

## Overview

The project workflow system provides a structured approach to creating data projects with the following workflow:

1. **Create Project** - Initialize a new project in draft status
2. **Add Datasets** - Add datasets to organize tables within the project
3. **Add Tables** - Add tables to datasets with enhanced AI-generated documentation
4. **Commit Workflow** - Finalize the project and transition to draft_ready status

## Architecture

### Components

- **Session Manager** (`app/core/session_manager.py`) - Manages database sessions and user sessions
- **Project Workflow Router** (`app/routers/project_workflow.py`) - API endpoints for workflow operations
- **Project Workflow Service** (`app/service/project_workflow_service.py`) - Business logic for workflow operations
- **Database Models** (`app/schemas/dbmodels.py`) - SQLAlchemy models for projects, datasets, and tables

### Workflow States

Projects progress through the following states:

- `draft` - Initial state, can add datasets and tables
- `draft_ready` - Tables completed, ready for metrics/views
- `review` - Under review before publishing
- `active` - Published and live
- `inactive` - Temporarily disabled
- `archived` - Permanently archived

## API Endpoints

### 1. Create Project

```http
POST /workflow/project
Content-Type: application/json
X-Session-Id: your-session-id
X-User-Id: your-user-id

{
  "project_id": "my_project_001",
  "display_name": "My Project",
  "description": "A data project for analytics",
  "created_by": "user123",
  "context": {
    "project_id": "my_project_001",
    "project_name": "My Project",
    "business_domain": "E-commerce",
    "purpose": "Customer analytics",
    "target_users": ["Data Analysts"],
    "key_business_concepts": ["Customer", "Order"]
  }
}
```

**Response:**
```json
{
  "project_id": "my_project_001",
  "display_name": "My Project",
  "description": "A data project for analytics",
  "created_by": "user123",
  "status": "draft",
  "version_string": "1.0.0",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### 2. Add Dataset

```http
POST /workflow/dataset
Content-Type: application/json
X-Session-Id: your-session-id
X-User-Id: your-user-id

{
  "project_id": "my_project_001",
  "name": "customer_data",
  "display_name": "Customer Data",
  "description": "Customer information and transactions",
  "metadata": {
    "source": "CRM",
    "update_frequency": "daily"
  }
}
```

**Response:**
```json
{
  "dataset_id": "uuid-here",
  "name": "customer_data",
  "display_name": "Customer Data",
  "description": "Customer information and transactions",
  "project_id": "my_project_001"
}
```

### 3. Add Table

```http
POST /workflow/table
Content-Type: application/json
X-Session-Id: your-session-id
X-User-Id: your-user-id

{
  "dataset_id": "dataset-uuid",
  "schema": {
    "table_name": "customers",
    "table_description": "Customer master data table",
    "columns": [
      {
        "name": "customer_id",
        "display_name": "Customer ID",
        "description": "Unique customer identifier",
        "data_type": "VARCHAR(50)",
        "is_primary_key": true,
        "is_nullable": false,
        "usage_type": "identifier"
      },
      {
        "name": "customer_name",
        "display_name": "Customer Name",
        "description": "Full name of the customer",
        "data_type": "VARCHAR(100)",
        "is_nullable": false,
        "usage_type": "attribute"
      }
    ]
  }
}
```

**Response:**
```json
{
  "table_id": "uuid-here",
  "name": "customers",
  "display_name": "customers",
  "description": "Enhanced table description with AI-generated insights",
  "table_type": "table",
  "semantic_description": "AI-generated semantic description",
  "column_count": 2
}
```

### 4. Commit Workflow

```http
POST /workflow/commit
X-Session-Id: your-session-id
X-User-Id: your-user-id
```

**Response:**
```json
{
  "message": "Workflow committed successfully",
  "project_id": "my_project_001",
  "status": "draft_ready",
  "state": {
    "project": {...},
    "datasets": [...],
    "tables": [...]
  }
}
```

### 5. Get Project Status

```http
GET /workflow/project/{project_id}/status
```

**Response:**
```json
{
  "project_id": "my_project_001",
  "display_name": "My Project",
  "workflow_status": {
    "status": "draft_ready",
    "is_draft": false,
    "is_published": false,
    "can_add_tables": false,
    "can_add_metrics": true,
    "table_count": 2,
    "version": "1.0.0"
  },
  "datasets": [
    {
      "dataset_id": "uuid",
      "name": "customer_data",
      "display_name": "Customer Data",
      "description": "Customer information",
      "table_count": 1,
      "tables": [...]
    }
  ],
  "total_datasets": 1,
  "total_tables": 2
}
```

### 6. Stream Updates

```http
GET /workflow/stream/{user_id}?session_id=your-session-id
```

Returns Server-Sent Events (SSE) stream with real-time workflow updates.

### 7. Post-Commit Workflow Status

```http
GET /workflow/project/{project_id}/post-commit-status
```

Get the status of post-commit workflows for a project.

**Response:**
```json
{
  "project_id": "my_project_001",
  "post_commit_status": "completed",
  "workflows_completed": [
    "generate_semantic_descriptions",
    "create_relationship_mappings",
    "generate_data_quality_rules"
  ],
  "last_updated": "2024-01-01T12:00:00Z",
  "errors": []
}
```

### 8. Trigger Post-Commit Workflows

```http
POST /workflow/project/{project_id}/trigger-post-commit
X-Session-Id: your-session-id
X-User-Id: your-user-id
```

Manually trigger post-commit workflows for a project.

**Response:**
```json
{
  "message": "Post-commit workflows triggered successfully",
  "project_id": "my_project_001",
  "status": "initiated"
}
```

## Enhanced Features

### AI-Generated Documentation

When adding tables, the system automatically generates:

1. **Semantic Descriptions** - Business-friendly descriptions of table purpose
2. **Relationship Recommendations** - Suggested relationships between tables
3. **Optimization Recommendations** - Performance and structure improvements
4. **Data Quality Recommendations** - Constraints and validation rules

### Post-Commit Workflows

When a project is committed, the system automatically executes the following workflow:

**LLM Definition Generation & MDL File Creation** - Generates comprehensive LLM definitions for all tables and stores them in a temporary MDL JSON file for future ChromaDB integration.

This workflow:
1. **Processes all tables** in the project using the LLM definition generation service
2. **Creates enhanced table definitions** with business context, column descriptions, and usage patterns
3. **Generates MDL JSON file** containing all definitions in a structured format
4. **Stores file path** in project metadata for future ChromaDB integration

The MDL file is stored in `mdl_files/{project_id}/` directory with timestamp for versioning.

This workflow runs asynchronously in the background and provides real-time updates via SSE.

### Workflow State Management

The system maintains workflow state in cache during the draft phase, allowing users to:

- Add multiple datasets and tables incrementally
- Preview changes before committing
- Receive real-time updates via SSE
- Rollback changes if needed

### Session Management

- **User Sessions** - Track user-specific workflow state
- **Database Sessions** - Async database operations with proper connection management
- **Session Timeout** - Automatic cleanup of expired sessions

## Usage Examples

### Complete Workflow Example

```python
import asyncio
from app.service.models import CreateProjectRequest, ProjectContext, AddTableRequest, SchemaInput

async def create_complete_project():
    # 1. Create project
    project_data = CreateProjectRequest(
        project_id="ecommerce_analytics",
        display_name="E-commerce Analytics",
        description="Customer and order analytics",
        created_by="analyst_user",
        context=ProjectContext(
            project_id="ecommerce_analytics",
            project_name="E-commerce Analytics",
            business_domain="E-commerce",
            purpose="Customer behavior analysis",
            target_users=["Data Analysts", "Business Users"],
            key_business_concepts=["Customer", "Order", "Product", "Revenue"]
        )
    )
    
    # 2. Add dataset
    dataset_data = {
        "project_id": "ecommerce_analytics",
        "name": "customer_data",
        "display_name": "Customer Data",
        "description": "Customer master data and transactions"
    }
    
    # 3. Add table
    table_schema = SchemaInput(
        table_name="customers",
        table_description="Customer master data",
        columns=[
            {
                "name": "customer_id",
                "data_type": "VARCHAR(50)",
                "is_primary_key": True,
                "usage_type": "identifier"
            },
            {
                "name": "customer_name",
                "data_type": "VARCHAR(100)",
                "usage_type": "attribute"
            }
        ]
    )
    
    add_table_request = AddTableRequest(
        dataset_id="dataset_uuid",
        schema=table_schema
    )
    
    # 4. Commit workflow
    # This transitions the project to draft_ready status
```

## Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dbname

# OpenAI API (for AI features)
OPENAI_API_KEY=your-openai-api-key

# Logging
LOG_LEVEL=INFO
```

### Session Configuration

```python
from app.core.session_manager import SessionManager
from app.core.settings import ServiceConfig

config = ServiceConfig(
    database_url="your-database-url",
    log_level="INFO"
)

session_manager = SessionManager(config, session_timeout=3600)
```

## Error Handling

The system provides comprehensive error handling:

- **Validation Errors** - Invalid input data
- **Business Logic Errors** - Workflow state violations
- **Database Errors** - Connection and transaction issues
- **AI Service Errors** - Fallback responses when AI services fail

## Testing

Run the test script to verify functionality:

```bash
cd unstructured/genieml/dataservices
python test_workflow.py
```

## Dependencies

- FastAPI - Web framework
- SQLAlchemy - Database ORM
- LangChain - AI/LLM integration
- Redis - Caching (optional)
- PostgreSQL - Database

## Future Enhancements

1. **Version Control** - Track changes and rollback capabilities
2. **Collaboration** - Multi-user editing with conflict resolution
3. **Templates** - Pre-built project templates
4. **Validation** - Enhanced data validation and quality checks
5. **Integration** - Connect with external data sources 
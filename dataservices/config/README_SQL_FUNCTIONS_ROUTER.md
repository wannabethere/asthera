# SQL Functions Router - Updated with Persistence Service

This document describes the updated SQL Functions Router that now uses the enhanced `SQLFunctionPersistenceService` for storing, managing, and retrieving SQL functions.

## Overview

The SQL Functions Router has been completely refactored to use the persistence service, providing:

- **Optional Project Association**: Functions can be global or project-specific
- **Enhanced CRUD Operations**: Full create, read, update, delete functionality
- **Batch Operations**: Create multiple functions at once
- **Advanced Search**: Search by name, description, and filters
- **Function Copying**: Copy functions between projects
- **Comprehensive Error Handling**: Proper HTTP status codes and error messages

## API Endpoints

### 1. Create SQL Function

**POST** `/api/v1/sql-functions/`

Create a new SQL function with optional project association.

**Request Body:**
```json
{
  "name": "safe_divide",
  "display_name": "Safe Division",
  "description": "Perform division with null check",
  "function_sql": "CREATE OR REPLACE FUNCTION safe_divide(numerator DECIMAL, denominator DECIMAL)...",
  "return_type": "DECIMAL",
  "parameters": [
    {"name": "numerator", "type": "DECIMAL", "description": "Numerator"},
    {"name": "denominator", "type": "DECIMAL", "description": "Denominator"}
  ],
  "project_id": "project_123",  // Optional - null for global functions
  "metadata": {
    "category": "math_utils",
    "tags": ["division", "safe"]
  }
}
```

**Response:**
```json
{
  "function_id": "uuid-here",
  "name": "safe_divide",
  "display_name": "Safe Division",
  "description": "Perform division with null check",
  "function_sql": "...",
  "return_type": "DECIMAL",
  "parameters": [...],
  "project_id": "project_123",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "modified_by": "api_user",
  "entity_version": 1
}
```

### 2. Create Multiple Functions (Batch)

**POST** `/api/v1/sql-functions/batch`

Create multiple SQL functions in batch.

**Request Body:**
```json
{
  "functions": [
    {
      "name": "format_currency",
      "function_sql": "...",
      "return_type": "VARCHAR"
    },
    {
      "name": "get_month_name",
      "function_sql": "...",
      "return_type": "VARCHAR"
    }
  ],
  "project_id": "project_123"  // Optional - applies to all functions
}
```

### 3. List Functions

**GET** `/api/v1/sql-functions/`

List SQL functions with optional filtering.

**Query Parameters:**
- `project_id` (optional): Filter by project ID
- `name` (optional): Filter by function name
- `return_type` (optional): Filter by return type

**Example:**
```
GET /api/v1/sql-functions/?project_id=project_123&return_type=DECIMAL
```

**Response:**
```json
{
  "functions": [...],
  "total_count": 5,
  "project_id": "project_123"
}
```

### 4. List Global Functions

**GET** `/api/v1/sql-functions/global`

List all global SQL functions (not associated with any project).

### 5. Search Functions

**POST** `/api/v1/sql-functions/search`

Search SQL functions by name or description.

**Request Body:**
```json
{
  "search_term": "calculate",
  "project_id": "project_123",  // Optional
  "return_type": "DECIMAL",     // Optional
  "limit": 100                  // Optional
}
```

### 6. Get Function by ID

**GET** `/api/v1/sql-functions/{function_id}`

Retrieve a specific SQL function by its ID.

### 7. Get Summary

**GET** `/api/v1/sql-functions/summary`

Get summary statistics for SQL functions.

**Query Parameters:**
- `project_id` (optional): Project ID for project-specific summary

**Response:**
```json
{
  "total_functions": 10,
  "project_id": "project_123",
  "return_types": {
    "INTEGER": 3,
    "VARCHAR": 4,
    "DECIMAL": 2,
    "BOOLEAN": 1
  },
  "recent_functions": [...],
  "total_parameters": 25
}
```

### 8. Update Function

**PATCH** `/api/v1/sql-functions/{function_id}`

Update a SQL function.

**Request Body:**
```json
{
  "description": "Updated description",
  "metadata": {
    "category": "updated_category",
    "tags": ["updated", "tags"]
  }
}
```

### 9. Copy Function

**POST** `/api/v1/sql-functions/{function_id}/copy`

Copy a SQL function to another project.

**Request Body:**
```json
{
  "target_project_id": "target_project_456"
}
```

### 10. Delete Function

**DELETE** `/api/v1/sql-functions/{function_id}`

Delete a SQL function.

**Response:**
```json
{
  "message": "SQL function deleted successfully"
}
```

## Usage Examples

### Python Client Example

```python
import requests

# Create a global function
global_function = {
    "name": "safe_divide",
    "display_name": "Safe Division",
    "description": "Perform division with null check",
    "function_sql": "CREATE OR REPLACE FUNCTION safe_divide(numerator DECIMAL, denominator DECIMAL)...",
    "return_type": "DECIMAL",
    "parameters": [
        {"name": "numerator", "type": "DECIMAL"},
        {"name": "denominator", "type": "DECIMAL"}
    ]
}

response = requests.post("http://localhost:8000/api/v1/sql-functions/", json=global_function)
function_id = response.json()["function_id"]

# Create a project-specific function
project_function = {
    "name": "calculate_revenue",
    "function_sql": "CREATE OR REPLACE FUNCTION calculate_revenue(project_id UUID)...",
    "return_type": "DECIMAL",
    "project_id": "project_123"
}

response = requests.post("http://localhost:8000/api/v1/sql-functions/", json=project_function)

# List global functions
response = requests.get("http://localhost:8000/api/v1/sql-functions/global")
global_functions = response.json()

# Search functions
search_data = {
    "search_term": "calculate",
    "return_type": "DECIMAL"
}
response = requests.post("http://localhost:8000/api/v1/sql-functions/search", json=search_data)
search_results = response.json()

# Update function
updates = {
    "description": "Updated description",
    "metadata": {"category": "updated"}
}
response = requests.patch(f"http://localhost:8000/api/v1/sql-functions/{function_id}", json=updates)

# Copy function
copy_data = {"target_project_id": "target_project_456"}
response = requests.post(f"http://localhost:8000/api/v1/sql-functions/{function_id}/copy", json=copy_data)

# Delete function
response = requests.delete(f"http://localhost:8000/api/v1/sql-functions/{function_id}")
```

### cURL Examples

```bash
# Create global function
curl -X POST "http://localhost:8000/api/v1/sql-functions/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "safe_divide",
    "function_sql": "CREATE OR REPLACE FUNCTION safe_divide(numerator DECIMAL, denominator DECIMAL)...",
    "return_type": "DECIMAL"
  }'

# Create project function
curl -X POST "http://localhost:8000/api/v1/sql-functions/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "calculate_revenue",
    "function_sql": "CREATE OR REPLACE FUNCTION calculate_revenue(project_id UUID)...",
    "return_type": "DECIMAL",
    "project_id": "project_123"
  }'

# List functions
curl "http://localhost:8000/api/v1/sql-functions/?project_id=project_123"

# Search functions
curl -X POST "http://localhost:8000/api/v1/sql-functions/search" \
  -H "Content-Type: application/json" \
  -d '{"search_term": "calculate"}'

# Get function by ID
curl "http://localhost:8000/api/v1/sql-functions/{function_id}"

# Update function
curl -X PATCH "http://localhost:8000/api/v1/sql-functions/{function_id}" \
  -H "Content-Type: application/json" \
  -d '{"description": "Updated description"}'

# Delete function
curl -X DELETE "http://localhost:8000/api/v1/sql-functions/{function_id}"
```

## Error Handling

The router provides comprehensive error handling:

- **400 Bad Request**: Invalid input data or validation errors
- **404 Not Found**: Function not found
- **500 Internal Server Error**: Database or service errors

All errors include descriptive messages:

```json
{
  "detail": "Failed to create SQL function: Invalid function name"
}
```

## Testing

Use the provided test script to verify the API functionality:

```bash
python test_sql_functions_router.py
```

The test script includes examples for all endpoints and demonstrates both global and project-specific function management.

## Integration Notes

- **Authentication**: Currently uses placeholder `'api_user'` - integrate with your auth system
- **Project Validation**: Ensure projects exist before creating project-specific functions
- **Database Migration**: Run the migration script to make `project_id` nullable
- **Version Control**: Project-specific functions trigger version updates automatically

## Schema Validation

The router uses Pydantic models for request/response validation:

- `SQLFunctionCreate`: For creating functions
- `SQLFunctionUpdate`: For updating functions
- `SQLFunctionRead`: For function responses
- `SQLFunctionSummary`: For summary responses
- `SQLFunctionSearchRequest`: For search requests
- `SQLFunctionBatchCreate`: For batch creation
- `SQLFunctionCopyRequest`: For copying functions

All schemas support optional project association and comprehensive metadata. 
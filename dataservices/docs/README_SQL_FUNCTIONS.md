# SQL Function Persistence Service

This document describes the enhanced SQL Function Persistence Service that supports storing SQL functions with optional project association.

## Overview

The `SQLFunctionPersistenceService` provides comprehensive functionality for managing SQL functions in the database. It supports both global functions (not associated with any project) and project-specific functions.

## Key Features

- **Optional Project Association**: Functions can be stored globally or associated with specific projects
- **Batch Operations**: Support for creating multiple functions at once
- **Search and Filtering**: Advanced search capabilities by name, description, and project
- **Function Copying**: Copy functions between projects
- **Comprehensive Metadata**: Support for parameters, return types, and custom metadata
- **Version Control**: Integration with project versioning system

## Database Model Changes

### SQLFunction Model Updates

The `SQLFunction` model has been updated to support optional project association:

```python
class SQLFunction(Base, TimestampMixin, EntityVersionMixin):
    """Project-level reusable functions with optional project association"""
    __tablename__ = 'sql_functions'
    
    function_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(50), ForeignKey('projects.project_id', ondelete='CASCADE'), nullable=True)  # Now nullable
    name = Column(String(100), nullable=False)
    display_name = Column(String(200))
    description = Column(Text)
    function_sql = Column(Text, nullable=False)
    return_type = Column(String(50))
    parameters = Column(JSONB)  # Array of parameter definitions
    
    # Relationships
    project = relationship("Project", back_populates="sql_functions")
    calculated_columns = relationship("CalculatedColumn", back_populates="function")
    
    __table_args__ = (
        # Partial unique constraint - only enforce uniqueness when project_id is not null
        UniqueConstraint('project_id', 'name', name='uq_sql_functions_project_name', deferrable=True),
        Index('idx_sql_functions_project_id', 'project_id'),
        Index('idx_sql_functions_name', 'name'),
    )
```

## Service Methods

### Core CRUD Operations

#### `persist_sql_function(function_data, created_by, project_id=None)`
Create a new SQL function.

**Parameters:**
- `function_data` (Dict[str, Any]): Function data including name, SQL, etc.
- `created_by` (str): User creating the function
- `project_id` (Optional[str]): Project ID (None for global functions)

**Returns:** Function ID as string

**Example:**
```python
function_data = {
    'name': 'calculate_age',
    'display_name': 'Calculate Age',
    'description': 'Calculate age from birth date',
    'function_sql': 'CREATE OR REPLACE FUNCTION calculate_age(birth_date DATE)...',
    'return_type': 'INTEGER',
    'parameters': [{'name': 'birth_date', 'type': 'DATE'}]
}

# Global function
function_id = service.persist_sql_function(function_data, 'admin')

# Project-specific function
function_id = service.persist_sql_function(function_data, 'admin', 'project_123')
```

#### `persist_sql_functions_batch(functions_data, created_by, project_id=None)`
Create multiple SQL functions in batch.

**Parameters:**
- `functions_data` (List[Dict[str, Any]]): List of function data
- `created_by` (str): User creating the functions
- `project_id` (Optional[str]): Project ID (None for global functions)

**Returns:** List of function IDs

#### `get_sql_function(function_id)`
Get a SQL function by ID.

**Parameters:**
- `function_id` (str): Function ID

**Returns:** SQLFunction object or None

#### `update_sql_function(function_id, updates, modified_by)`
Update a SQL function.

**Parameters:**
- `function_id` (str): Function ID
- `updates` (Dict[str, Any]): Fields to update
- `modified_by` (str): User making the changes

**Returns:** Updated SQLFunction object

#### `delete_sql_function(function_id)`
Delete a SQL function.

**Parameters:**
- `function_id` (str): Function ID

**Returns:** True if deleted, False otherwise

### Query and Search Operations

#### `get_sql_functions(project_id=None)`
Get SQL functions, optionally filtered by project.

**Parameters:**
- `project_id` (Optional[str]): Project ID (None for all functions)

**Returns:** List of SQLFunction objects

#### `get_global_sql_functions()`
Get all global SQL functions (not associated with any project).

**Returns:** List of SQLFunction objects

#### `get_sql_functions_by_name(name, project_id=None)`
Get SQL functions by name, optionally filtered by project.

**Parameters:**
- `name` (str): Function name
- `project_id` (Optional[str]): Project ID (None for all projects)

**Returns:** List of SQLFunction objects

#### `search_sql_functions(search_term, project_id=None)`
Search SQL functions by name or description.

**Parameters:**
- `search_term` (str): Search term
- `project_id` (Optional[str]): Project ID (None for all projects)

**Returns:** List of SQLFunction objects

### Utility Operations

#### `get_sql_function_summary(project_id=None)`
Get summary statistics for SQL functions.

**Parameters:**
- `project_id` (Optional[str]): Project ID (None for global summary)

**Returns:** Dictionary with summary information

**Example Response:**
```python
{
    'total_functions': 10,
    'project_id': 'project_123',
    'return_types': {
        'INTEGER': 3,
        'VARCHAR': 4,
        'DECIMAL': 2,
        'BOOLEAN': 1
    },
    'recent_functions': [...],
    'total_parameters': 25
}
```

#### `copy_sql_function_to_project(function_id, target_project_id, created_by)`
Copy a SQL function to another project.

**Parameters:**
- `function_id` (str): Source function ID
- `target_project_id` (str): Target project ID
- `created_by` (str): User performing the copy

**Returns:** New function ID

## Usage Examples

### Basic Usage

```python
from app.service.persistence_service import SQLFunctionPersistenceService
from app.utils.history import ProjectManager

# Initialize service
project_manager = ProjectManager(session)
sql_function_service = SQLFunctionPersistenceService(session, project_manager)

# Create a global function
global_function_data = {
    'name': 'safe_divide',
    'display_name': 'Safe Division',
    'description': 'Perform division with null check',
    'function_sql': 'CREATE OR REPLACE FUNCTION safe_divide(numerator DECIMAL, denominator DECIMAL)...',
    'return_type': 'DECIMAL',
    'parameters': [
        {'name': 'numerator', 'type': 'DECIMAL'},
        {'name': 'denominator', 'type': 'DECIMAL'}
    ]
}

function_id = sql_function_service.persist_sql_function(
    function_data=global_function_data,
    created_by='admin'
)

# Create a project-specific function
project_function_data = {
    'name': 'calculate_revenue',
    'display_name': 'Calculate Revenue',
    'description': 'Calculate revenue for project',
    'function_sql': 'CREATE OR REPLACE FUNCTION calculate_revenue(project_id UUID)...',
    'return_type': 'DECIMAL'
}

project_function_id = sql_function_service.persist_sql_function(
    function_data=project_function_data,
    created_by='admin',
    project_id='project_123'
)
```

### Advanced Usage

```python
# Search for functions
search_results = sql_function_service.search_sql_functions('calculate')

# Get project summary
summary = sql_function_service.get_sql_function_summary('project_123')

# Copy function to another project
copied_id = sql_function_service.copy_sql_function_to_project(
    function_id='source_function_id',
    target_project_id='target_project_456',
    created_by='admin'
)

# Batch create functions
batch_data = [
    {
        'name': 'format_currency',
        'function_sql': 'CREATE OR REPLACE FUNCTION format_currency(amount DECIMAL)...',
        'return_type': 'VARCHAR'
    },
    {
        'name': 'get_month_name',
        'function_sql': 'CREATE OR REPLACE FUNCTION get_month_name(input_date DATE)...',
        'return_type': 'VARCHAR'
    }
]

function_ids = sql_function_service.persist_sql_functions_batch(
    functions_data=batch_data,
    created_by='admin'
)
```

## Database Migration

If you have existing SQL functions in your database, you'll need to run a migration to make the `project_id` column nullable:

```sql
-- Make project_id nullable
ALTER TABLE sql_functions ALTER COLUMN project_id DROP NOT NULL;

-- Update unique constraint to handle null values
ALTER TABLE sql_functions DROP CONSTRAINT IF EXISTS uq_sql_functions_project_name;
ALTER TABLE sql_functions ADD CONSTRAINT uq_sql_functions_project_name 
    UNIQUE (project_id, name) DEFERRABLE;

-- Add indexes for better performance
CREATE INDEX IF NOT EXISTS idx_sql_functions_project_id ON sql_functions(project_id);
CREATE INDEX IF NOT EXISTS idx_sql_functions_name ON sql_functions(name);
```

## Integration with Project Versioning

The service integrates with the project versioning system:

- **Global functions** (project_id = null) do not trigger project version updates
- **Project-specific functions** trigger version updates when modified
- Version changes follow semantic versioning rules:
  - **Major**: Function deletion or breaking changes
  - **Minor**: New function creation
  - **Patch**: Function updates

## Error Handling

The service includes comprehensive error handling:

- **Validation errors**: Invalid function data
- **Database errors**: Connection issues, constraint violations
- **Not found errors**: Attempting to access non-existent functions
- **Version lock errors**: Attempting to modify locked projects

All errors include descriptive messages and proper rollback handling.

## Best Practices

1. **Use meaningful names**: Choose descriptive function names
2. **Include documentation**: Provide clear descriptions and parameter documentation
3. **Use metadata**: Leverage the metadata field for categorization and tagging
4. **Test functions**: Validate SQL syntax before storing
5. **Version control**: Use project versioning for tracking changes
6. **Global vs Project**: Use global functions for reusable utilities, project-specific for business logic

## Testing

See `sql_functions_example.py` for comprehensive usage examples and testing scenarios. 
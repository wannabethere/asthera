# MDL Builder System

## Overview

The MDL (Model Definition Language) Builder System is a comprehensive solution for automatically generating MDL definitions from PostgreSQL objects stored in the database. It leverages the existing database models to build rich, structured MDL files that include tables, columns, metrics, views, calculated columns, functions, relationships, and enums.

## Architecture

### Core Components

1. **MDLBuilderService** (`mdl_builder_service.py`)
   - Main service for building MDL definitions
   - Processes PostgreSQL objects from database models
   - Supports both project-level and table-level MDL generation
   - Integrates with LLM-generated definitions

2. **MDL Builder Router** (`mdl_builder_router.py`)
   - REST API endpoints for MDL generation
   - Supports validation, export, and summary operations
   - Provides both synchronous and file-based operations

3. **Integration Points**
   - **Post-Commit Workflow**: Automatically generates MDL during project commits
   - **ChromaDB Indexing**: Uses generated MDL for indexing
   - **Manual Generation**: API endpoints for on-demand MDL generation

## Features

### Comprehensive Object Coverage
- **Tables**: Complete table definitions with metadata
- **Columns**: Regular and calculated columns with business context
- **Metrics**: Business metrics with SQL definitions
- **Views**: Database views with business purpose
- **Functions**: SQL functions with parameters and return types
- **Relationships**: Table and column relationships
- **Enums**: Enumeration values (future support)

### LLM Integration
- Incorporates LLM-generated business context
- Preserves existing LLM definitions in metadata
- Supports building MDL with or without LLM definitions
- Maintains business context and semantic information

### Flexible Generation
- **Project-level MDL**: Complete project definition
- **Table-level MDL**: Individual table definitions
- **Customizable output**: Include/exclude LLM definitions
- **File export**: Save MDL to JSON files

## Database Models Used

### Core Models
```python
from app.schemas.dbmodels import (
    Project, Dataset, Table, SQLColumn, Metric, View, 
    CalculatedColumn, SQLFunction, Relationship
)
```

### Model Relationships
- **Project** → **Dataset** → **Table** → **SQLColumn**
- **Table** → **Metric** (table-level metrics)
- **Table** → **View** (table-level views)
- **SQLColumn** → **CalculatedColumn** (calculated columns)
- **Project** → **SQLFunction** (project-level functions)
- **Project** → **Relationship** (table relationships)

## MDL Structure

### Project-Level MDL
```json
{
  "project_id": "project_123",
  "project_name": "E-commerce Analytics",
  "description": "Comprehensive e-commerce data model",
  "version": "1.2.3",
  "status": "active",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T15:45:00Z",
  "created_by": "user_123",
  "last_modified_by": "user_456",
  "generated_at": "2024-01-15T16:00:00Z",
  "mdl_version": "1.0",
  "metadata": {
    "business_domain": "E-commerce",
    "target_users": ["Data Analysts", "Business Users"],
    "key_concepts": ["Customer", "Order", "Product"],
    "project_type": "data_project",
    "total_tables": 5,
    "total_metrics": 12,
    "total_views": 3,
    "total_calculated_columns": 8,
    "total_functions": 4,
    "total_relationships": 6,
    "total_enums": 2
  },
  "tables": [...],
  "metrics": [...],
  "views": [...],
  "calculated_columns": [...],
  "functions": [...],
  "relationships": [...],
  "enums": [...],
  "llm_definitions": {...}
}
```

### Table MDL Structure
```json
{
  "table_id": "table_123",
  "name": "customers",
  "display_name": "Customers",
  "description": "Customer master data table",
  "table_type": "table",
  "dataset_id": "dataset_456",
  "dataset_name": "core_data",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T15:45:00Z",
  "entity_version": 3,
  "business_purpose": "Store and manage customer information",
  "primary_use_cases": ["Customer analytics", "Sales reporting"],
  "key_relationships": ["Orders", "Payments"],
  "data_lineage": "Extracted from CRM system",
  "update_frequency": "Daily",
  "data_retention": "7 years",
  "access_patterns": ["Read-heavy", "Batch updates"],
  "performance_considerations": ["Indexed on customer_id"],
  "columns": [...],
  "metrics": [...],
  "views": [...],
  "metadata": {...}
}
```

### Column MDL Structure
```json
{
  "column_id": "column_123",
  "name": "customer_id",
  "display_name": "Customer ID",
  "description": "Unique customer identifier",
  "column_type": "column",
  "data_type": "VARCHAR(50)",
  "usage_type": "identifier",
  "is_nullable": false,
  "is_primary_key": true,
  "is_foreign_key": false,
  "default_value": null,
  "ordinal_position": 1,
  "business_description": "Primary key for customer records",
  "example_values": ["CUST001", "CUST002"],
  "business_rules": ["Must be unique", "Cannot be null"],
  "data_quality_checks": ["Uniqueness", "Format validation"],
  "related_concepts": ["Customer", "Account"],
  "privacy_classification": "PII",
  "aggregation_suggestions": ["Count", "Distinct count"],
  "filtering_suggestions": ["Exact match", "Pattern matching"],
  "calculated_column": {
    "calculated_column_id": "calc_123",
    "calculation_sql": "UPPER(customer_name)",
    "function_id": "func_456",
    "dependencies": ["customer_name"]
  },
  "metadata": {...}
}
```

## API Endpoints

### Build Project MDL
```http
POST /mdl-builder/projects/{project_id}/mdl
```

**Parameters:**
- `project_id` (path): ID of the project
- `include_llm_definitions` (query): Include LLM-generated definitions (default: true)
- `save_to_file` (query): Save MDL to file (default: false)

**Response:**
```json
{
  "success": true,
  "project_id": "project_123",
  "mdl_data": {...},
  "file_info": {
    "file_path": "/path/to/mdl/file.json",
    "file_size": 15420
  },
  "message": "MDL built successfully"
}
```

### Build Table MDL
```http
POST /mdl-builder/tables/{table_id}/mdl
```

**Parameters:**
- `table_id` (path): ID of the table
- `include_llm_definitions` (query): Include LLM-generated definitions (default: true)
- `save_to_file` (query): Save MDL to file (default: false)

### Get MDL Summary
```http
GET /mdl-builder/projects/{project_id}/mdl/summary
```

**Response:**
```json
{
  "success": true,
  "project_id": "project_123",
  "summary": {
    "project_id": "project_123",
    "project_name": "E-commerce Analytics",
    "version": "1.2.3",
    "status": "active",
    "generated_at": "2024-01-15T16:00:00Z",
    "statistics": {
      "total_tables": 5,
      "total_columns": 45,
      "total_metrics": 12,
      "total_views": 3,
      "total_calculated_columns": 8,
      "total_functions": 4,
      "total_relationships": 6,
      "total_enums": 2
    },
    "tables": [...]
  },
  "message": "MDL summary retrieved successfully"
}
```

### Validate MDL Structure
```http
POST /mdl-builder/projects/{project_id}/mdl/validate
```

**Response:**
```json
{
  "success": true,
  "project_id": "project_123",
  "validation": {
    "project_id": "project_123",
    "is_valid": true,
    "errors": [],
    "warnings": [
      "Table 'temp_table' has no description",
      "Column 'customers.status' has no description"
    ],
    "statistics": {
      "tables_without_description": 1,
      "columns_without_description": 3,
      "tables_without_columns": 0,
      "metrics_without_sql": 0,
      "views_without_sql": 0
    }
  },
  "message": "MDL validation completed"
}
```

### Export MDL to File
```http
POST /mdl-builder/projects/{project_id}/mdl/export
```

**Parameters:**
- `project_id` (path): ID of the project
- `include_llm_definitions` (query): Include LLM-generated definitions (default: true)
- `filename` (query): Custom filename without extension (optional)

## Usage Examples

### Programmatic Usage
```python
from app.services.mdl_builder_service import mdl_builder_service

# Build project MDL
mdl_data = await mdl_builder_service.build_project_mdl(
    project_id="project_123",
    db=db_session,
    include_llm_definitions=True
)

# Build table MDL
table_mdl = await mdl_builder_service.build_table_mdl(
    table_id="table_456",
    db=db_session,
    include_llm_definitions=True
)

# Save MDL to file
save_result = await mdl_builder_service.save_mdl_to_file(
    mdl_data=mdl_data,
    file_path="mdl_files/project_123_mdl.json"
)
```

### API Usage
```bash
# Build project MDL
curl -X POST "http://localhost:8000/mdl-builder/projects/project_123/mdl?include_llm_definitions=true&save_to_file=true"

# Get MDL summary
curl "http://localhost:8000/mdl-builder/projects/project_123/mdl/summary"

# Validate MDL structure
curl -X POST "http://localhost:8000/mdl-builder/projects/project_123/mdl/validate"

# Export MDL to file
curl -X POST "http://localhost:8000/mdl-builder/projects/project_123/mdl/export?filename=custom_mdl"
```

## Integration with Post-Commit Workflow

The MDL builder is automatically integrated into the post-commit workflow:

1. **Project Commit**: When a project is committed
2. **LLM Definition Generation**: LLM generates business context
3. **MDL Generation**: MDL builder creates comprehensive MDL file
4. **ChromaDB Indexing**: Generated MDL is used for indexing
5. **File Storage**: MDL file is saved for future reference

### Workflow Integration
```python
# In post_commit_service.py
async def _create_mdl_json_file(self, project: Project, table_definitions: List[Dict[str, Any]], db: AsyncSession):
    """Create MDL JSON file using MDL Builder Service"""
    from app.services.mdl_builder_service import mdl_builder_service
    
    # Build complete MDL using the MDL Builder Service
    mdl_content = await mdl_builder_service.build_project_mdl(
        project_id=project.project_id,
        db=db,
        include_llm_definitions=True
    )
    
    # Save MDL to file
    save_result = await mdl_builder_service.save_mdl_to_file(
        mdl_data=mdl_content,
        file_path=str(mdl_file_path)
    )
```

## Configuration

### Required Dependencies
```python
# Database models
from app.schemas.dbmodels import Project, Dataset, Table, SQLColumn, Metric, View, CalculatedColumn, SQLFunction, Relationship

# Session management
from app.core.session_manager import SessionManager

# File operations
from pathlib import Path
import json
```

### File Storage Configuration
```python
# MDL files are stored in:
mdl_files/
├── project_123/
│   ├── project_123_mdl_20240115_160000.json
│   ├── tables/
│   │   ├── table_456_mdl_20240115_160000.json
│   │   └── table_789_mdl_20240115_160000.json
│   └── exports/
│       └── custom_mdl_20240115_160000.json
└── project_456/
    └── ...
```

## Error Handling

### Common Issues
1. **Project Not Found**: Verify project exists in database
2. **Table Not Found**: Check table ID and project association
3. **Database Connection**: Ensure database session is valid
4. **File Permissions**: Check write permissions for MDL file directory

### Error Recovery
- Graceful handling of missing LLM definitions
- Fallback to basic MDL structure if LLM data unavailable
- Detailed error messages for debugging
- Validation warnings for incomplete data

## Performance Considerations

### Optimization
- Efficient database queries with proper joins
- Lazy loading of related objects
- Optional LLM definition inclusion
- Batch processing for large projects

### Scalability
- Async/await for non-blocking operations
- Configurable file storage locations
- Support for large MDL files
- Memory-efficient processing

## Testing

### Test Coverage
- Unit tests for MDL builder service
- Integration tests with database models
- API endpoint testing
- File export validation
- MDL structure validation

### Test Data
- Comprehensive test project with all object types
- LLM definitions for business context
- Various data types and relationships
- Edge cases and error conditions

## Future Enhancements

### Planned Features
1. **Incremental MDL Updates**: Only update changed objects
2. **MDL Versioning**: Track MDL file versions
3. **Custom MDL Templates**: User-defined MDL structures
4. **MDL Comparison**: Compare different MDL versions
5. **MDL Import**: Import MDL from external sources

### Integration Opportunities
1. **Schema Registry**: Centralized MDL storage and management
2. **Data Lineage**: Enhanced data lineage tracking
3. **Impact Analysis**: Analyze impact of schema changes
4. **Documentation Generation**: Auto-generate documentation from MDL
5. **Code Generation**: Generate code from MDL definitions

## Troubleshooting

### Common Problems

#### MDL Generation Fails
- Check database connectivity
- Verify project and table existence
- Review error logs for specific issues
- Ensure proper database permissions

#### Missing LLM Definitions
- Verify LLM definition generation completed
- Check project metadata structure
- Review LLM service configuration
- Regenerate LLM definitions if needed

#### File Export Issues
- Check file system permissions
- Verify directory exists and is writable
- Review file path configuration
- Check available disk space

### Debug Mode
Enable debug logging for detailed troubleshooting:
```python
import logging
logging.getLogger("app.services.mdl_builder_service").setLevel(logging.DEBUG)
```

## Support

For issues and questions:
1. Check error logs and validation results
2. Review database model relationships
3. Verify LLM definition availability
4. Test with sample data
5. Consult this documentation
6. Contact the development team

---

*This documentation covers the MDL Builder System for generating comprehensive MDL definitions from PostgreSQL objects. For more information about the underlying database models, see the individual model documentation.* 
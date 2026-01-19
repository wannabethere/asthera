# API to MDL Converter

Convert OpenAPI 3.x specifications to AsteraMDL (Model Definition Language) schema format.

## Overview

This utility helps build a knowledge base of API schemas by converting OpenAPI specifications into AsteraMDL format. It's designed to work with any OpenAPI 3.x compliant API documentation, including Snyk API.

## Features

- ✅ Parse OpenAPI 3.x specifications (JSON)
- ✅ Convert schemas to AsteraMDL models
- ✅ Generate views for API endpoints
- ✅ Infer relationships between models based on foreign key patterns
- ✅ Support for filtering schemas and endpoints by tags
- ✅ Batch conversion of multiple API specs
- ✅ Template for LLM-based enrichment of descriptions
- ✅ Extensible architecture for custom transformations

## Files

### Core Classes

- **`openapi_parser.py`** - Parse OpenAPI specs and extract schema information
  - `OpenAPIParser` - Main parser class
  - `SchemaDefinition` - Represents an OpenAPI schema
  - `PropertySchema` - Represents schema properties
  - `EndpointDefinition` - Represents API endpoints

- **`mdl_builder.py`** - Build AsteraMDL schemas from parsed data
  - `MDLSchemaBuilder` - Main builder class
  - `MDLModel` - Represents an MDL model
  - `MDLColumn` - Represents model columns
  - `MDLRelationship` - Represents relationships
  - `MDLView` - Represents views

- **`api_to_mdl_converter.py`** - Main conversion orchestrator
  - `APIToMDLConverter` - Main converter class
  - `BatchConverter` - Batch process multiple APIs

### Test & Example Scripts

- **`test_converter.py`** - Comprehensive test suite with examples
  - Basic conversion
  - Filtered conversion
  - Endpoint views
  - Relationship inference
  - Batch conversion
  - LLM enrichment pattern

- **`real_api_converter.py`** - Real-world API conversion examples
  - Snyk API conversion
  - Generic API conversion
  - Local file conversion
  - Manual schema template

## Installation

```bash
# Install dependencies
pip install requests --break-system-packages
```

## Quick Start

### 1. Basic Usage

```python
from api_to_mdl_converter import APIToMDLConverter

# Load from OpenAPI spec file
converter = APIToMDLConverter.from_file(
    'openapi_spec.json',
    catalog='my_api',
    schema='v1'
)

# Convert
mdl = converter.convert()

# Save to file
converter.save('output_mdl.json')
```

### 2. Convert from URL

```python
from real_api_converter import RealAPIConverter

converter = RealAPIConverter()

# Convert Snyk API
mdl = converter.convert_snyk_api(
    version="2024-10-15",
    output_file="snyk_mdl.json"
)
```

### 3. Filter Specific Schemas

```python
# Only convert specific schemas
mdl = converter.convert(
    filter_schemas=['User', 'Organization'],
    filter_tags=['users', 'orgs']
)
```

### 4. Batch Conversion

```python
from api_to_mdl_converter import BatchConverter

batch = BatchConverter(catalog="multi_api")
batch.add_from_file("users_api", "users_openapi.json", schema="users")
batch.add_from_file("projects_api", "projects_openapi.json", schema="projects")

results = batch.convert_all()
batch.save_all(output_dir="mdl_schemas")
```

## Running Tests

```bash
# Run all tests
python test_converter.py

# Run specific test
python test_converter.py basic
python test_converter.py relationships
python test_converter.py enrichment
```

Available tests:
- `basic` - Basic conversion
- `filtered` - Filtered conversion
- `views` - Endpoint views
- `relationships` - Relationship inference
- `file` - Load from file
- `batch` - Batch conversion
- `custom` - Custom configuration
- `enrichment` - LLM enrichment pattern

## Real API Examples

```bash
# Convert Snyk API
python real_api_converter.py snyk

# Convert generic API
python real_api_converter.py generic

# Convert from local file
python real_api_converter.py local

# Create manual template
python real_api_converter.py template
```

## LLM Enrichment Pattern

The converter includes a pattern for enriching MDL schemas using LLMs:

```python
from test_converter import demonstrate_llm_enrichment_pattern

# Generate enrichment template
enrichment_data = demonstrate_llm_enrichment_pattern()

# The template includes:
# - Model names
# - Column names and types
# - Current descriptions
# - Flags for columns needing enrichment
```

You can then:
1. Load the enrichment template
2. Use an LLM to generate better descriptions
3. Add business context, data quality rules, metrics
4. Update the MDL schema with enriched information

## Configuration Options

### APIToMDLConverter Options

```python
converter = APIToMDLConverter(
    openapi_spec,
    catalog="api",              # MDL catalog name
    schema="public",            # MDL schema name
    create_endpoint_views=True, # Create views for endpoints
    infer_relationships=True    # Infer FK relationships
)
```

### Conversion Options

```python
mdl = converter.convert(
    filter_schemas=['Schema1', 'Schema2'],  # Only convert these schemas
    filter_tags=['tag1', 'tag2']           # Only create views for these tags
)
```

## Output Format

The converter generates AsteraMDL JSON with:

### Models
```json
{
  "name": "User",
  "refSql": "SELECT * FROM public.User",
  "columns": [
    {
      "name": "id",
      "type": "varchar",
      "notNull": true,
      "properties": {
        "format": "uuid",
        "description": "Unique user identifier"
      }
    }
  ],
  "primaryKey": "id",
  "properties": {
    "description": "A user in the system"
  }
}
```

### Relationships
```json
{
  "name": "User_Organization",
  "models": ["User", "Organization"],
  "joinType": "MANY_TO_ONE",
  "condition": "User.org_id = Organization.id",
  "properties": {
    "foreign_key": "org_id",
    "inferred": "true"
  }
}
```

### Views (for API endpoints)
```json
{
  "name": "GET_users",
  "statement": "SELECT * FROM public.User",
  "properties": {
    "endpoint_path": "/users",
    "http_method": "GET",
    "operation_id": "listUsers"
  }
}
```

## Type Mapping

OpenAPI types are mapped to MDL types:

| OpenAPI Type | Format | MDL Type |
|--------------|--------|----------|
| string | - | varchar |
| string | uuid | varchar |
| string | email | varchar |
| string | date | date |
| string | date-time | timestamp |
| integer | int32 | integer |
| integer | int64 | bigint |
| number | float | float |
| number | double | double |
| boolean | - | boolean |
| array | - | array |
| object | - | json |

## Advanced Usage

### Custom Column Addition

```python
from mdl_builder import MDLColumn

# Add custom ETL columns
for model in builder.models:
    model.columns.append(
        MDLColumn(
            name="_etl_timestamp",
            type="timestamp",
            description="ETL processing timestamp",
            properties={"etl": "true"}
        )
    )
```

### Manual Relationship Creation

```python
# Create custom relationship
builder.infer_relationship(
    from_model="User",
    to_model="Organization",
    foreign_key="org_id",
    join_type="MANY_TO_ONE"
)
```

### Custom View Creation

```python
from mdl_builder import MDLView

view = MDLView(
    name="active_users",
    statement="SELECT * FROM public.User WHERE status = 'active'",
    properties={"description": "All active users"}
)
builder.views.append(view)
```

## Working with Snyk API

To convert the Snyk API:

### Option 1: Direct URL (may require auth)
```python
from real_api_converter import RealAPIConverter

converter = RealAPIConverter(api_token="your_snyk_token")
mdl = converter.convert_snyk_api(version="2024-10-15")
```

### Option 2: Manual download
1. Visit https://apidocs.snyk.io/?version=2024-10-15
2. Open browser dev tools (F12) → Network tab
3. Refresh page and look for requests to OpenAPI spec
4. Save the JSON response as `snyk_openapi.json`
5. Convert:
```python
from api_to_mdl_converter import APIToMDLConverter

converter = APIToMDLConverter.from_file('snyk_openapi.json')
mdl = converter.convert()
converter.save('snyk_mdl.json')
```

## Troubleshooting

### "File not found" errors
Make sure you're running scripts from the correct directory with all files present.

### Import errors
Ensure all three core files are in the same directory:
- `openapi_parser.py`
- `mdl_builder.py`
- `api_to_mdl_converter.py`

### API spec fetch errors
Some API specs require authentication. Download manually if needed.

## Architecture

```
┌─────────────────────┐
│  OpenAPI Spec       │
│  (JSON)             │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  OpenAPIParser      │
│  - Parse schemas    │
│  - Extract endpoints│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ APIToMDLConverter   │
│ - Coordinate        │
│ - Filter & transform│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  MDLSchemaBuilder   │
│  - Build models     │
│  - Create relations │
│  - Generate views   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  AsteraMDL Schema     │
│  (JSON)             │
└─────────────────────┘
```

## Extension Points

The converter is designed to be extended:

1. **Custom Type Mapping**: Override `PropertySchema.to_mdl_type()`
2. **Custom Parsers**: Extend `OpenAPIParser` for specific API patterns
3. **Custom Builders**: Extend `MDLSchemaBuilder` for custom MDL features
4. **Post-processing**: Use the enrichment pattern for LLM enhancement

## License

This is a utility script provided as-is for converting API specifications to AsteraMDL format.

## Support

For issues with:
- AsteraMDL schema: Refer to Astera documentation
- OpenAPI specs: Refer to specific API documentation
- This converter: Review the source code and examples

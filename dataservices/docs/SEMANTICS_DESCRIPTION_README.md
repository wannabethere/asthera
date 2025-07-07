# Semantics Description Service

## Overview

The Semantics Description Service has been updated to work with table JSON data instead of MDL (Model Definition Language) input. This service analyzes table structures and generates comprehensive semantic descriptions including business context, key columns, and suggested relationships.

## Changes Made

### 1. Updated Semantics Description Service (`app/agents/semantics_description.py`)

- **Input Change**: Changed from `mdl` (string) to `table_data` (Dict[str, Any])
- **Enhanced Prompts**: Updated system and user prompts to focus on table structure analysis
- **Improved Output**: Now provides structured JSON response with:
  - Table description and purpose
  - Key columns with business significance
  - Business context and domain description
  - Data patterns
  - Suggested relationships with reasoning

### 2. Updated Project Management Service (`app/service/project_management_service.py`)

- **Integration**: Now uses the actual semantics description service instead of placeholder
- **Table Data Conversion**: Converts database Table objects to the format expected by the semantics service
- **Enhanced Storage**: Stores both the description and full semantic analysis in table metadata
- **Error Handling**: Includes fallback responses when the service fails

### 3. New API Endpoints

#### Semantics Description (`app/routers/semantics.py`)
- **POST `/semantics/describe-table`**: Generate semantic descriptions for table structures
- **GET `/semantics/health`**: Health check endpoint
- **Structured Request/Response**: Uses Pydantic models for type safety

#### Relationship Recommendations (`app/routers/relationships.py`)
- **POST `/relationships/recommend`**: Generate relationship recommendations for table structures
- **GET `/relationships/health`**: Health check endpoint
- **Structured Request/Response**: Uses Pydantic models for type safety

### 4. Updated Project Workflow Service (`app/service/project_workflow_service.py`)

- **Integration**: Now uses the semantics description service in workflow operations
- **Enhanced Table Addition**: Automatically generates semantic descriptions when adding tables
- **Metadata Storage**: Stores semantic descriptions in table metadata for later use
- **Error Handling**: Includes fallback responses when the service fails

### 5. Updated Relationship Recommendation Service (`app/agents/relationship_recommendation.py`)

- **Input Change**: Changed from `mdl` (string) to `table_data` (Dict[str, Any])
- **Enhanced Prompts**: Updated system and user prompts to focus on table structure analysis
- **Improved Output**: Now provides structured JSON response with:
  - Detailed relationship specifications (source/target tables, columns, types)
  - Business value explanations
  - Confidence scores
  - Summary and recommendations
- **Better Error Handling**: Improved response parsing with fallback responses

## Usage

### Direct Service Usage

```python
from app.agents.semantics_description import SemanticsDescription

# Create service instance
semantics_service = SemanticsDescription()

# Prepare table data
table_data = {
    "name": "customers",
    "display_name": "Customer Information",
    "description": "Stores customer master data",
    "columns": [
        {
            "name": "customer_id",
            "display_name": "Customer ID",
            "description": "Unique identifier",
            "data_type": "UUID",
            "is_primary_key": True,
            "is_nullable": False
        },
        # ... more columns
    ]
}

# Generate description
result = await semantics_service.describe(
    SemanticsDescription.Input(
        id="table_customers",
        table_data=table_data,
        project_id="my_project"
    )
)

if result.status == "finished":
    description = result.response
    print(description["description"])
    print(description["table_purpose"])
    # ... access other fields
```

### API Usage

#### Semantic Description
```bash
# Generate semantic description via API
curl -X POST "http://localhost:8000/semantics/describe-table" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "customers",
    "display_name": "Customer Information",
    "description": "Stores customer master data",
    "columns": [
      {
        "name": "customer_id",
        "display_name": "Customer ID",
        "description": "Unique identifier",
        "data_type": "UUID",
        "is_primary_key": true,
        "is_nullable": false
      }
    ]
  }'
```

#### Relationship Recommendations
```bash
# Generate relationship recommendations via API
curl -X POST "http://localhost:8000/relationships/recommend" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "orders",
    "display_name": "Customer Orders",
    "description": "Stores customer order information",
    "columns": [
      {
        "name": "order_id",
        "display_name": "Order ID",
        "description": "Unique identifier",
        "data_type": "UUID",
        "is_primary_key": true,
        "is_nullable": false
      },
      {
        "name": "customer_id",
        "display_name": "Customer ID",
        "description": "Reference to customer",
        "data_type": "UUID",
        "is_foreign_key": true,
        "is_nullable": false
      }
    ]
  }'
```

### Project Management Integration

```python
# Generate descriptions for all tables in a project
from app.service.project_management_service import ProjectService

service = ProjectService(db_session)
descriptions = await service.generate_semantic_descriptions("project_id")

# Each table will have its semantic description stored in json_metadata
for table_id, description in descriptions.items():
    print(f"Table {table_id}: {description['description']}")
```

### Project Workflow Integration

```python
# Use semantics description and relationship recommendations in workflow operations
from app.service.project_workflow_service import ProjectWorkflowService
from app.service.models import AddTableRequest, SchemaInput, ProjectContext

# Create workflow service
workflow_service = ProjectWorkflowService(user_id="user123", session_id="session456")

# Generate semantic description for a table
semantic_description = await workflow_service.get_semantic_description_for_table(
    add_table_request, project_context
)

# Generate relationship recommendations for a table
relationship_recommendations = await workflow_service.get_relationship_recommendation_for_table(
    add_table_request, project_context
)

# Add table with automatic semantic description and relationship recommendation generation
documented_table = await workflow_service.add_table(add_table_request, project_context)

# Access semantic description
if documented_table.semantic_description:
    print(f"Description: {documented_table.semantic_description['description']}")
    print(f"Purpose: {documented_table.semantic_description['table_purpose']}")

# Access relationship recommendations
if documented_table.relationship_recommendations:
    relationships = documented_table.relationship_recommendations.get('relationships', [])
    print(f"Found {len(relationships)} relationship recommendations")
    for rel in relationships:
        print(f"• {rel['source_table']} → {rel['target_table']} ({rel['relationship_type']})")
```

## Response Format

### Semantic Description Response

The semantics description service returns a structured JSON response:

```json
{
  "description": "Overall description of the table and its purpose",
  "table_purpose": "Specific business purpose of this table",
  "key_columns": [
    {
      "name": "column_name",
      "description": "Column description",
      "business_significance": "Why this column is important",
      "data_type": "Data type"
    }
  ],
  "business_context": "Business context and domain description",
  "data_patterns": ["pattern1", "pattern2"],
  "suggested_relationships": [
    {
      "related_entity": "potential_related_table",
      "relationship_type": "relationship_type",
      "reasoning": "Why this relationship makes sense"
    }
  ]
}
```

### Relationship Recommendation Response

The relationship recommendation service returns a structured JSON response:

```json
{
  "relationships": [
    {
      "source_table": "orders",
      "target_table": "customers",
      "relationship_type": "Many-to-One",
      "source_column": "customer_id",
      "target_column": "customer_id",
      "explanation": "Each order belongs to one customer, but a customer can have multiple orders",
      "business_value": "Enables customer order history analysis and customer segmentation",
      "confidence_score": 0.95
    }
  ],
  "summary": {
    "total_relationships": 1,
    "primary_relationships": ["orders-customers"],
    "recommendations": [
      "Consider adding indexes on foreign key columns for better query performance",
      "Implement referential integrity constraints to maintain data quality"
    ]
  }
}
```

## Testing

Run the test scripts to verify the services work:

```bash
cd unstructured/genieml/dataservices

# Test the semantics description service
python test_semantics_service.py

# Test the relationship recommendation service
python test_relationship_recommendation.py

# Test the project workflow service integration
python test_workflow_semantics.py

# Test the project workflow service with relationship recommendations
python test_workflow_relationships.py
```

## Configuration

The service supports configuration options:

```python
from app.agents.semantics_description import Configuration

config = Configuration(language="Spanish")  # Default: "English"
```

## Error Handling

The service includes comprehensive error handling:

- **TABLE_PARSE_ERROR**: When table data cannot be parsed
- **RESOURCE_NOT_FOUND**: When a cached result is not found
- **OTHERS**: For general errors

All errors include detailed error messages and are logged for debugging.

## Dependencies

- `langchain_openai`: For LLM integration
- `orjson`: For fast JSON processing
- `cachetools`: For result caching
- `langfuse`: For observability
- `pydantic`: For data validation 
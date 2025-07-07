# Schema Documentation Utilities

This document explains how to use the schema documentation utilities to generate comprehensive table documentation and store it in ChromaDB for vector search.

## Overview

The schema documentation system provides three main components:

1. **LLMSchemaDocumentationGenerator**: Generates comprehensive table documentation using LLM
2. **SchemaDocumentationUtils**: Utility methods to convert documentation to various formats
3. **Integration with DBSchema**: Store documentation in ChromaDB for vector search

## Quick Start

### 1. Basic Schema Documentation Generation

```python
from app.agents.schema_manager import LLMSchemaDocumentationGenerator
from app.service.models import SchemaInput, ProjectContext

# Create schema input
schema_input = SchemaInput(
    table_name="users",
    table_description="User account information",
    columns=[
        {"name": "user_id", "type": "INTEGER", "nullable": False, "primary_key": True},
        {"name": "email", "type": "VARCHAR(255)", "nullable": False},
        {"name": "created_at", "type": "TIMESTAMP", "nullable": False}
    ],
    sample_data=[{"user_id": 1, "email": "user@example.com", "created_at": "2024-01-01"}]
)

# Create project context
project_context = ProjectContext(
    project_id="my_project",
    project_name="My Application",
    business_domain="user_management",
    purpose="Track user accounts and authentication",
    target_users=["Developers", "Analysts"],
    key_business_concepts=["user_authentication", "account_management"]
)

# Generate documentation
schema_manager = LLMSchemaDocumentationGenerator()
documented_table = await schema_manager.document_table_schema(schema_input, project_context)
```

### 2. Convert to MDL Format

```python
from app.agents.schema_manager import SchemaDocumentationUtils

# Convert to MDL format for DBSchema processing
mdl_json = SchemaDocumentationUtils.documented_table_to_mdl(
    documented_table, 
    project_context.project_id
)
```

### 3. Convert to ChromaDB Documents

```python
# Convert to ChromaDB document format
chroma_documents = SchemaDocumentationUtils.documented_table_to_chroma_documents(
    documented_table, 
    project_context.project_id
)
```

### 4. Complete Workflow

```python
from app.storage.documents import DocumentChromaStore, AsyncDocumentWriter, DuplicatePolicy

# Complete workflow: generate and store
result = await SchemaDocumentationUtils.process_and_store_schema(
    schema_input=schema_input,
    project_context=project_context,
    document_store=document_store,
    embedder=embeddings
)
```

## Utility Methods

### `documented_table_to_mdl()`

Converts a `DocumentedTable` to MDL (Model Definition Language) format that can be processed by the `DBSchema` class.

**Parameters:**
- `documented_table`: The documented table object
- `project_id`: The project identifier

**Returns:**
- JSON string in MDL format

**Example:**
```python
mdl_json = SchemaDocumentationUtils.documented_table_to_mdl(documented_table, "my_project")
print(mdl_json)
# Output: {"models": [{"name": "users", "properties": {...}, "columns": [...]}], ...}
```

### `documented_table_to_chroma_documents()`

Converts a `DocumentedTable` to ChromaDB document format for direct storage.

**Parameters:**
- `documented_table`: The documented table object
- `project_id`: The project identifier

**Returns:**
- List of `LangchainDocument` objects ready for ChromaDB storage

**Document Structure:**
- **Table Document**: Contains table-level information
- **Column Documents**: One document per column with detailed information

**Example:**
```python
documents = SchemaDocumentationUtils.documented_table_to_chroma_documents(
    documented_table, 
    "my_project"
)
print(f"Generated {len(documents)} documents")
# Output: Generated 11 documents (1 table + 10 columns)
```

### `process_and_store_schema()`

Complete workflow that generates schema documentation and stores it in ChromaDB.

**Parameters:**
- `schema_input`: The schema input data
- `project_context`: The project context
- `document_store`: ChromaDB document store instance
- `embedder`: Optional embedder for generating embeddings

**Returns:**
- Dictionary with processing results

**Example:**
```python
result = await SchemaDocumentationUtils.process_and_store_schema(
    schema_input=schema_input,
    project_context=project_context,
    document_store=doc_store
)

if result["success"]:
    print(f"Stored {result['documents_written']} documents")
else:
    print(f"Error: {result['error']}")
```

## Integration with DBSchema

The utilities are designed to work seamlessly with the existing `DBSchema` class:

### Option 1: Use MDL Format

```python
from app.agents.indexing.db_schema import DBSchema

# Convert to MDL and process with DBSchema
mdl_json = SchemaDocumentationUtils.documented_table_to_mdl(documented_table, project_id)
db_schema = DBSchema(document_store=doc_store, embedder=embeddings)
result = await db_schema.run(mdl_json, project_id=project_id)
```

### Option 2: Direct ChromaDB Storage

```python
from app.storage.documents import AsyncDocumentWriter, DuplicatePolicy

# Convert to ChromaDB documents and store directly
documents = SchemaDocumentationUtils.documented_table_to_chroma_documents(
    documented_table, 
    project_id
)

writer = AsyncDocumentWriter(
    document_store=doc_store,
    policy=DuplicatePolicy.OVERWRITE,
)
write_result = await writer.run(documents=documents)
```

## Document Structure

### Table Document
```json
{
  "metadata": {
    "type": "TABLE_SCHEMA",
    "name": "users",
    "project_id": "my_project",
    "documentation_type": "table_overview"
  },
  "page_content": {
    "type": "TABLE",
    "name": "users",
    "display_name": "User Accounts",
    "description": "Stores user account information...",
    "business_purpose": "Track user accounts and authentication...",
    "primary_use_cases": ["User registration", "Authentication"],
    "key_relationships": ["Relates to user_sessions", "Relates to user_profiles"],
    "data_lineage": "Populated from registration forms and API calls",
    "update_frequency": "real-time",
    "data_retention": "Indefinite",
    "access_patterns": ["Read by authentication service", "Updated by user management"],
    "performance_considerations": ["Index on email field", "Partition by created_date"]
  }
}
```

### Column Document
```json
{
  "metadata": {
    "type": "TABLE_SCHEMA",
    "name": "users.user_id",
    "project_id": "my_project",
    "table_name": "users",
    "column_name": "user_id",
    "documentation_type": "column_detail"
  },
  "page_content": {
    "type": "COLUMN",
    "table_name": "users",
    "name": "user_id",
    "display_name": "User ID",
    "data_type": "INTEGER",
    "description": "Unique identifier for users",
    "business_description": "Primary key for user accounts",
    "usage_type": "identifier",
    "example_values": ["1", "2", "3"],
    "business_rules": ["Must be unique", "Cannot be null"],
    "data_quality_checks": ["Check for duplicates", "Validate positive integers"],
    "related_concepts": ["User", "Account"],
    "privacy_classification": "internal",
    "aggregation_suggestions": ["COUNT"],
    "filtering_suggestions": ["Filter by user_id", "Filter by range"],
    "metadata": {
      "is_primary_key": true,
      "typical_cardinality": "high"
    }
  }
}
```

## Example Usage

See the complete example in `examples/schema_to_chroma_example.py` for a full workflow demonstration.

## Configuration

### Required Dependencies
```python
# For basic functionality
from app.agents.schema_manager import LLMSchemaDocumentationGenerator, SchemaDocumentationUtils

# For ChromaDB storage
from app.storage.documents import DocumentChromaStore, AsyncDocumentWriter, DuplicatePolicy
import chromadb

# For embeddings (optional)
from langchain_openai import OpenAIEmbeddings
```

### Environment Variables
```bash
# Required for LLM functionality
OPENAI_API_KEY=your_openai_api_key

# Optional for ChromaDB
CHROMA_STORE_PATH=./chroma_db
```

## Best Practices

1. **Project Context**: Always provide comprehensive project context for better documentation quality
2. **Sample Data**: Include sample data when available for more accurate column analysis
3. **Error Handling**: Wrap utility calls in try-catch blocks for production use
4. **Batch Processing**: For multiple tables, process them in batches to avoid rate limits
5. **Documentation Updates**: Use `DuplicatePolicy.OVERWRITE` to update existing documentation

## Troubleshooting

### Common Issues

1. **LLM Timeout**: Increase timeout settings for large schemas
2. **JSON Parsing Errors**: Check LLM response format and add error handling
3. **ChromaDB Connection**: Ensure ChromaDB is properly initialized
4. **Memory Issues**: Process large schemas in smaller batches

### Debug Mode

Enable debug output by setting logging level:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## API Reference

For detailed API documentation, see the docstrings in the source code:
- `app/agents/schema_manager.py`
- `app/service/models.py`
- `app/storage/documents.py` 
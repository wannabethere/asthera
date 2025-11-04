# Document Types Migration Guide

## 🎯 Problem Solved
This migration eliminates the duplication between `TABLE` and `TABLE_SCHEMA` document types by introducing a unified architecture that separates technical structure from business descriptions.

## 📋 New Architecture

### Before (Duplicated)
```
TABLE_SCHEMA (metadata.type) containing:
├── TABLE (content.type) - Table metadata
├── TABLE_COLUMNS (content.type) - Batched columns
└── FOREIGN_KEY (content.type) - Relationships

TABLE_DESCRIPTION (metadata.type) containing:
└── TABLE (content.type) - Table descriptions (DUPLICATE!)
```

### After (Unified)
```
SCHEMA_DOCUMENT (metadata.type) containing:
├── TABLE_DEFINITION (content.type) - Technical table structure
├── TABLE_COLUMNS (content.type) - Technical column definitions
└── FOREIGN_KEY (content.type) - Technical relationships

DESCRIPTION_DOCUMENT (metadata.type) containing:
├── TABLE_DESCRIPTION (content.type) - Business table descriptions
└── COLUMN_DESCRIPTION (content.type) - Business column descriptions
```

## 🔄 Migration Steps

### Step 1: Update Document Creation

#### In `db_schema.py`:
```python
# OLD
metadata = {"type": "TABLE_SCHEMA", "name": "users"}
content = {"type": "TABLE", "name": "users", "comment": "..."}

# NEW
metadata = {"type": "SCHEMA_DOCUMENT", "name": "users"}
content = {"type": "TABLE_DEFINITION", "name": "users", "primary_key": "user_id"}
```

#### In `table_description.py`:
```python
# OLD
metadata = {"type": "TABLE_DESCRIPTION", "name": "users"}
content = {"type": "TABLE", "name": "users", "description": "..."}

# NEW
metadata = {"type": "DESCRIPTION_DOCUMENT", "name": "users"}
content = {"type": "TABLE_DESCRIPTION", "name": "users", "display_name": "User Accounts"}
```

### Step 2: Update Retrieval Queries

#### In `retrieval.py`:
```python
# OLD
where = {"type": "TABLE_SCHEMA", "name": {"$in": table_names}}

# NEW
where = {"type": "SCHEMA_DOCUMENT", "name": {"$in": table_names}}
```

### Step 3: Update Content Type Checks

```python
# OLD
if content.get("type") == "TABLE":
    # Handle table content

# NEW
if content.get("type") == "TABLE_DEFINITION":
    # Handle technical table structure
elif content.get("type") == "TABLE_DESCRIPTION":
    # Handle business table description
```

## 📊 Migration Mapping

| Old Type | New Type | Purpose |
|----------|----------|---------|
| `TABLE_SCHEMA` (metadata) | `SCHEMA_DOCUMENT` (metadata) | Technical structure documents |
| `TABLE_DESCRIPTION` (metadata) | `DESCRIPTION_DOCUMENT` (metadata) | Business description documents |
| `TABLE` (content) | `TABLE_DEFINITION` (content) | Technical table structure |
| `TABLE` (content) | `TABLE_DESCRIPTION` (content) | Business table description |
| `COLUMN` (content) | `COLUMN` (content) | Technical column structure |
| `COLUMN` (content) | `COLUMN_DESCRIPTION` (content) | Business column description |

## 🎯 Benefits

1. **Eliminates Duplication** - No more overlapping `TABLE` content types
2. **Clear Separation** - Technical vs. business information
3. **Efficient Retrieval** - Query by purpose, not by overlapping types
4. **Maintainable** - Clear responsibility boundaries
5. **Scalable** - Easy to add new technical or business types

## 🔧 Implementation Checklist

- [ ] Update `db_schema.py` to use `SCHEMA_DOCUMENT` and `TABLE_DEFINITION`
- [ ] Update `table_description.py` to use `DESCRIPTION_DOCUMENT` and `TABLE_DESCRIPTION`
- [ ] Update `retrieval.py` queries to use new metadata types
- [ ] Update content type checks throughout the codebase
- [ ] Test retrieval functionality with new document structure
- [ ] Update any existing documents in ChromaDB (if needed)

## 🚀 Usage Examples

### Creating Documents
```python
from agents.app.indexing.document_types import DocumentType

# Technical schema document
schema_doc = {
    "metadata": {
        "type": DocumentType.SCHEMA_DOCUMENT.value,
        "name": "users",
        "project_id": "my_project"
    },
    "page_content": str({
        "type": DocumentType.TABLE_DEFINITION.value,
        "name": "users",
        "primary_key": "user_id",
        "constraints": [...]
    })
}

# Business description document
description_doc = {
    "metadata": {
        "type": DocumentType.DESCRIPTION_DOCUMENT.value,
        "name": "users",
        "project_id": "my_project"
    },
    "page_content": str({
        "type": DocumentType.TABLE_DESCRIPTION.value,
        "name": "users",
        "display_name": "User Accounts",
        "description": "Stores user account information"
    })
}
```

### Querying Documents
```python
# Get technical schema for tables
schema_where = {
    "type": DocumentType.SCHEMA_DOCUMENT.value,
    "name": {"$in": ["users", "orders"]}
}

# Get business descriptions for tables
description_where = {
    "type": DocumentType.DESCRIPTION_DOCUMENT.value,
    "name": "users"
}
```

This migration will eliminate the duplication you identified and provide a cleaner, more maintainable architecture for your ChromaDB indexing system.

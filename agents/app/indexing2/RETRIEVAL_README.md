# Retrieval v2 for Indexing2

This document describes the new retrieval helper and retrieval classes that use the unified storage system from `indexing2/`.

## Overview

The new retrieval system (`retrieval_helper2.py` and `retrieval2.py`) provides enhanced document retrieval capabilities using the unified storage components from `indexing2/`. These classes maintain backward compatibility with the original retrieval system while offering improved functionality.

## Key Differences from v1

### Original Retrieval System (v1)
- Located in `agents/app/agents/retrieval/`
- Uses separate document stores for each type
- Direct ChromaDB queries
- Manual schema construction

### New Retrieval System (v2)
- Located in `agents/app/indexing2/`
- Uses unified storage with `StorageManager`
- Natural language search via `NaturalLanguageSearch`
- Enhanced document building with business context
- TF-IDF support for quick lookups

## Components

### RetrievalHelper2

The `RetrievalHelper2` class provides high-level retrieval methods similar to the original `RetrievalHelper`.

**Key Methods:**
- `get_database_schemas()` - Fetch database schemas using natural language search
- `get_sql_pairs()` - Retrieve SQL pairs for similar queries
- `get_instructions()` - Fetch instructions matching queries
- `get_historical_questions()` - Retrieve historical question patterns
- `get_table_names_and_schema_contexts()` - Extract table info and DDL

**Features:**
- Unified storage access via `StorageManager`
- Natural language search capabilities
- Business context in schema descriptions
- Enhanced column metadata
- Caching support

### TableRetrieval2

The `TableRetrieval2` class handles table retrieval with enhanced business context.

**Key Features:**
- Natural language search for table discovery
- Automatic schema construction from unified documents
- Enhanced DDL generation with business purpose
- Support for calculated fields and metrics
- Relationship tracking

## Usage Examples

### Using RetrievalHelper2

```python
from app.indexing2.retrieval_helper2 import RetrievalHelper2
from langchain_openai import OpenAIEmbeddings

# Initialize the retrieval helper
retrieval_helper = RetrievalHelper2(
    embedder=OpenAIEmbeddings(model="text-embedding-3-small")
)

# Get database schemas
schemas = await retrieval_helper.get_database_schemas(
    project_id="my_project",
    table_retrieval={"table_retrieval_size": 10},
    query="sales data for last month"
)

# Get SQL pairs
sql_pairs = await retrieval_helper.get_sql_pairs(
    query="average sales by region",
    project_id="my_project"
)
```

### Using TableRetrieval2

```python
from app.indexing2.retrieval2 import TableRetrieval2

# Initialize table retrieval
retrieval = TableRetrieval2(
    embedder=embeddings,
    table_retrieval_size=10
)

# Retrieve tables
results = await retrieval.run(
    query="customer orders",
    project_id="my_project"
)

# Get specific tables
results = await retrieval.run(
    tables=["customers", "orders", "products"],
    project_id="my_project"
)
```

## Integration with Indexing2

The new retrieval system integrates with the following indexing2 components:

1. **StorageManager** - Unified storage orchestration
2. **NaturalLanguageSearch** - Enhanced search capabilities
3. **DocumentBuilder** - Document structure creation
4. **TFIDFGenerator** - Quick reference lookups
5. **UnifiedStorage** - Consolidated document storage

## Migration Guide

### From RetrievalHelper to RetrievalHelper2

```python
# Old way
from app.agents.retrieval.retrieval_helper import RetrievalHelper
helper = RetrievalHelper()

# New way
from app.indexing2.retrieval_helper2 import RetrievalHelper2
helper = RetrievalHelper2()
```

The API is the same, so existing code should work with minimal changes.

### From TableRetrieval to TableRetrieval2

```python
# Old way
from app.agents.retrieval.retrieval import TableRetrieval
retrieval = TableRetrieval(document_store, embedder)

# New way
from app.indexing2.retrieval2 import TableRetrieval2
retrieval = TableRetrieval2(document_store, embedder)
```

## Benefits

1. **Enhanced Business Context**
   - Schemas include business purpose, display names, and descriptions
   - Better understanding of table usage and meaning

2. **Natural Language Search**
   - More intuitive table discovery
   - Relevance scoring based on query context

3. **Unified Storage**
   - Single source of truth for all documents
   - Reduced duplication and inconsistency

4. **Better Performance**
   - TF-IDF support for quick lookups
   - Caching at multiple levels
   - Optimized retrieval strategies

5. **Maintainability**
   - Consistent with indexing2 architecture
   - Easier to extend and customize

## Architecture

```
RetrievalHelper2
├── StorageManager
│   ├── UnifiedStorage
│   ├── NaturalLanguageSearch
│   ├── DocumentBuilder
│   └── TFIDFGenerator
└── Cache (InMemoryCache)

TableRetrieval2
├── StorageManager
│   └── NaturalLanguageSearch
└── DocumentBuilder
```

## Future Enhancements

- [ ] LLM-based query optimization
- [ ] Field classification support
- [ ] Enhanced relationship detection
- [ ] Multi-project search
- [ ] Advanced filtering capabilities


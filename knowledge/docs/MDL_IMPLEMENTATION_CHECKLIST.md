# MDL Knowledge Graph - Implementation Checklist

## Overview

This checklist shows **what's already available** vs. **what needs to be created** for the simplified MDL Knowledge Graph architecture.

---

## ✅ Already Available (Use As-Is)

### 1. Table Indexing & Retrieval
- ✅ **Indexing**: `indexing_cli/index_mdl_standalone.py` (Lines 102-131)
  - Indexes to `db_schema` collection
  - Already processes MDL JSON files
  - Handles tables and columns

- ✅ **Collection**: `table_descriptions`
  - Already indexed by `index_mdl_standalone.py`
  - Contains semantic descriptions
  - Has product_name, project_id metadata

- ✅ **Retrieval**: `app/agents/data/retrieval.py`
  - Class: `Retrieval`
  - Already has semantic search
  - Works with table_descriptions

**Usage (Already Works):**
```python
from app.agents.data.retrieval import Retrieval

store = doc_store_provider.get_store("table_description")
retrieval = Retrieval(store, embeddings)
results = await retrieval.run(
    query="tables with vulnerability data",
    project_id="Snyk",
    top_k=5
)
```

### 2. Column Indexing & Retrieval
- ✅ **Indexing**: `indexing_cli/index_mdl_standalone.py` (Lines 165-280)
  - Indexes to `column_metadata` collection
  - Handles nested properties
  - Includes data types, PII markers

- ✅ **Collection**: `column_metadata`
  - Already indexed
  - Contains column metadata
  - Has table_name, is_pii metadata

- ✅ **Retrieval**: `app/agents/data/retrieval.py`
  - Same `Retrieval` class
  - Works with column_metadata

**Usage (Already Works):**
```python
store = doc_store_provider.get_store("column_metadata")
retrieval = Retrieval(store, embeddings)
results = await retrieval.run(
    query="columns with PII data",
    project_id="Snyk",
    top_k=10
)
```

### 3. SQL Examples (Pairs) Retrieval
- ✅ **Collection**: `sql_pairs`
  - Already exists
  - Contains SQL query examples

- ✅ **Retrieval**: `app/agents/data/sql_pairs_retrieval.py`
  - Class: `SqlPairsRetrieval`
  - Has semantic search with similarity threshold
  - Returns formatted SQL pairs

**Usage (Already Works):**
```python
from app.agents.data.sql_pairs_retrieval import SqlPairsRetrieval

store = doc_store_provider.get_store("sql_pairs")
sql_retrieval = SqlPairsRetrieval(store, embeddings)
results = await sql_retrieval.run(
    query="how to query high severity vulnerabilities",
    project_id="Snyk"
)
```

### 4. Instructions Retrieval
- ✅ **Collection**: `instructions`
  - Already exists
  - Contains product instructions

- ✅ **Retrieval**: `app/agents/data/instructions.py`
  - Class: `Instructions`
  - Has semantic search
  - Returns formatted instructions

**Usage (Already Works):**
```python
from app.agents.data.instructions import Instructions

store = doc_store_provider.get_store("instructions")
instructions_retrieval = Instructions(store, embeddings)
results = await instructions_retrieval.run(
    query="best practices for vulnerability scanning",
    project_id="Snyk"
)
```

### 5. Contextual Edges
- ✅ **Collection**: `contextual_edges`
  - Already exists
  - Stores relationships between entities

- ✅ **Service**: `app/services/contextual_graph_storage.py`
  - Class: `ContextualGraphStorageService`
  - Can store and retrieve edges
  - Has edge pruning capabilities

**Usage (Already Works):**
```python
from app.services.contextual_graph_storage import ContextualGraphStorageService

service = ContextualGraphStorageService(vector_store_client)
edges = await service.discover_edges(
    source_entity_id="table_123",
    edge_type="TABLE_RELATES_TO_TABLE",
    max_results=10
)
```

### 6. Existing Extractors (From Background Task)
- ✅ **7 MDL Extractors Created**:
  - `app/agents/extractors/mdl_table_extractor.py` ✅
  - `app/agents/extractors/mdl_relationship_extractor.py` ✅
  - `app/agents/extractors/mdl_category_extractor.py` ✅
  - `app/agents/extractors/mdl_feature_extractor.py` ✅
  - `app/agents/extractors/mdl_metric_extractor.py` ✅
  - `app/agents/extractors/mdl_example_extractor.py` ✅
  - `app/agents/extractors/mdl_instruction_extractor.py` ✅

### 7. Contextual Indexing CLI
- ✅ **File**: `indexing_cli/index_mdl_contextual.py`
  - Created by background task
  - Uses all 7 extractors
  - Creates documents and edges
  - Supports preview mode

---

## ❌ What Needs to Be Created/Updated

### 1. Update Contextual Indexing to Use Existing Collections

**File to Update**: `indexing_cli/index_mdl_contextual.py`

**Changes Needed**:
```python
# Instead of indexing to 16 separate collections:
# - mdl_products, mdl_categories, mdl_features, mdl_metrics...

# Use existing collections with discriminators:

# For products, categories, features, metrics → entities collection
async def index_to_entities_collection(
    documents: List[Document],
    entity_type: str  # "product", "category", "feature", "metric"
):
    entities_store = doc_store_provider.get_store("entities")
    
    # Add discriminator to metadata
    for doc in documents:
        doc.metadata["entity_type"] = "mdl"
        doc.metadata["mdl_entity_type"] = entity_type
    
    entities_store.add_documents(documents)

# For tables → table_descriptions (ALREADY DONE by index_mdl_standalone)
# For columns → column_metadata (ALREADY DONE by index_mdl_standalone)
# For examples → sql_pairs collection
# For instructions → instructions collection
# For relationships → contextual_edges
```

### 2. Create Generic Entity Retrieval Helper

**File to Create**: `app/agents/data/mdl_entity_retrieval.py`

```python
"""
Generic retrieval for MDL entities in the entities collection
"""
from typing import Any, Dict, List, Optional
from app.storage.documents import DocumentChromaStore

class MDLEntityRetrieval:
    """Retrieves MDL entities with type discriminators"""
    
    def __init__(
        self,
        document_store: DocumentChromaStore,
        embedder: Any,
        similarity_threshold: float = 0.7,
        top_k: int = 10,
    ):
        self._document_store = document_store
        self._embedder = embedder
        self._similarity_threshold = similarity_threshold
        self._top_k = top_k
    
    async def run(
        self,
        query: str,
        mdl_entity_type: str,  # "product", "category", "feature", "metric"
        product_name: Optional[str] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Retrieve MDL entities by type"""
        
        # Build filter
        where = {
            "entity_type": "mdl",
            "mdl_entity_type": mdl_entity_type
        }
        
        if product_name:
            where["product_name"] = product_name
        
        # Add any additional filters
        where.update(kwargs)
        
        # Search
        results = self._document_store.semantic_search(
            query=query,
            where=where,
            k=self._top_k
        )
        
        return results
```

### 3. Update Context Breakdown Agent

**File to Update**: `app/agents/contextual_agents/mdl_context_breakdown_agent.py`

**Changes Needed**:
```python
# Update collection mapping to use existing collections

def get_collection_for_entity_type(entity_type: str) -> str:
    """Map entity type to actual collection"""
    mapping = {
        "table": "table_descriptions",      # ALREADY INDEXED
        "column": "column_metadata",        # ALREADY INDEXED
        "example": "sql_pairs",             # ALREADY EXISTS
        "instruction": "instructions",      # ALREADY EXISTS
        "product": "entities",              # Use with discriminator
        "category": "entities",             # Use with discriminator
        "feature": "entities",              # Use with discriminator
        "metric": "entities",               # Use with discriminator
        "relationship": "contextual_edges", # ALREADY EXISTS
    }
    return mapping.get(entity_type, "entities")
```

### 4. Merge Time Concepts into Column Metadata

**File to Update**: `app/indexing/processors/db_schema_processor.py`

**Changes Needed**:
```python
# When processing columns, add time concept fields:

column_metadata = {
    "column_name": column["name"],
    "data_type": column["type"],
    # ... existing fields ...
    
    # Add time concept fields:
    "is_time_dimension": False,  # Detect from column name/type
    "time_granularity": None,    # "day", "hour", "month", etc.
    "is_event_time": False,      # created_at, event_timestamp, etc.
    "is_process_time": False,    # updated_at, processed_at, etc.
}

# Auto-detect time dimensions
if column["name"] in ["created_at", "updated_at", "event_time", "timestamp"]:
    column_metadata["is_time_dimension"] = True
    column_metadata["time_granularity"] = "second"
    
    if column["name"] in ["created_at", "event_time", "event_timestamp"]:
        column_metadata["is_event_time"] = True
    elif column["name"] in ["updated_at", "processed_at"]:
        column_metadata["is_process_time"] = True
```

### 5. Add Category Tagging to Table Indexing

**File to Update**: `app/indexing/processors/table_description_processor.py`

**Changes Needed**:
```python
from indexing_cli.index_mdl_contextual import categorize_table

# When processing tables, add category:

table_metadata = {
    "table_name": table["name"],
    "product_name": product_name,
    # ... existing fields ...
    
    # Add category:
    "category_name": categorize_table(table["name"]),  # Returns one of 15 categories
}
```

---

## Implementation Priority

### Phase 1: Use What's Already Available (Immediate)
1. ✅ Use `index_mdl_standalone.py` for tables and columns
2. ✅ Use existing retrieval for tables (`retrieval.py`)
3. ✅ Use existing retrieval for SQL pairs (`sql_pairs_retrieval.py`)
4. ✅ Use existing retrieval for instructions (`instructions.py`)
5. ✅ Use `contextual_edges` for relationships

**Result**: ~70% of functionality already works!

### Phase 2: Small Updates (Quick Wins)
1. ❌ Add category tagging to table indexing (1 hour)
2. ❌ Merge time concepts into column metadata (2 hours)
3. ❌ Update `index_mdl_contextual.py` to use existing collections (2 hours)

**Result**: ~90% of functionality works!

### Phase 3: New Entity Types (If Needed)
1. ❌ Create `MDLEntityRetrieval` for products/categories/features/metrics (4 hours)
2. ❌ Index products/categories to `entities` collection (2 hours)
3. ❌ Index features/metrics to `entities` collection (2 hours)

**Result**: 100% of functionality works!

---

## Quick Start (Using What's Already Available)

### Step 1: Index Tables and Columns (Already Works!)
```bash
cd knowledge

# Index Snyk MDL
python -m indexing_cli.index_mdl_standalone \
    --mdl-file ../data/cvedata/snyk_mdl1.json \
    --project-id "Snyk" \
    --product-name "Snyk" \
    --collections db_schema table_descriptions column_metadata
```

### Step 2: Query Tables (Already Works!)
```python
from app.agents.data.retrieval import Retrieval
from app.core.dependencies import get_doc_store_provider, get_embeddings_model

# Get stores
doc_store_provider = get_doc_store_provider()
embeddings = get_embeddings_model()

# Query tables
table_store = doc_store_provider.get_store("table_description")
retrieval = Retrieval(table_store, embeddings)
results = await retrieval.run(
    query="tables with vulnerability data",
    project_id="Snyk",
    top_k=5
)

for doc in results["documents"]:
    print(f"Table: {doc['table_name']}")
    print(f"Description: {doc['description']}")
```

### Step 3: Query Columns (Already Works!)
```python
# Query columns
column_store = doc_store_provider.get_store("column_metadata")
retrieval = Retrieval(column_store, embeddings)
results = await retrieval.run(
    query="columns with PII data",
    project_id="Snyk",
    top_k=10
)
```

### Step 4: Get SQL Examples (Already Works!)
```python
from app.agents.data.sql_pairs_retrieval import SqlPairsRetrieval

# Query SQL pairs
sql_pairs_store = doc_store_provider.get_store("sql_pairs")
sql_retrieval = SqlPairsRetrieval(sql_pairs_store, embeddings)
results = await sql_retrieval.run(
    query="how to query vulnerabilities",
    project_id="Snyk"
)
```

---

## Summary

| Component | Status | Collection | Retrieval Code | Notes |
|-----------|--------|-----------|----------------|-------|
| **Tables** | ✅ Done | `table_descriptions` | `retrieval.py` | Indexed by `index_mdl_standalone` |
| **Columns** | ✅ Done | `column_metadata` | `retrieval.py` | Indexed by `index_mdl_standalone` |
| **SQL Examples** | ✅ Done | `sql_pairs` | `sql_pairs_retrieval.py` | Already exists |
| **Instructions** | ✅ Done | `instructions` | `instructions.py` | Already exists |
| **Relationships** | ✅ Done | `contextual_edges` | `contextual_graph_storage.py` | Already exists |
| **Categories** | ❌ Need | `entities` | Need to create | Use discriminator |
| **Features** | ❌ Need | `entities` | Need to create | Use discriminator |
| **Metrics** | ❌ Need | `entities` | Need to create | Use discriminator |
| **Products** | ❌ Need | `entities` | Need to create | Use discriminator |

**Bottom Line**: ~70% already works! Just need small updates to leverage existing infrastructure fully.

---

## Files Reference

### Already Available
- ✅ `indexing_cli/index_mdl_standalone.py` - Table/column indexing
- ✅ `app/agents/data/retrieval.py` - Generic retrieval
- ✅ `app/agents/data/sql_pairs_retrieval.py` - SQL examples
- ✅ `app/agents/data/instructions.py` - Instructions
- ✅ `app/services/contextual_graph_storage.py` - Edge storage
- ✅ `indexing_cli/index_mdl_contextual.py` - Contextual indexing (created by background task)
- ✅ `app/agents/extractors/mdl_*.py` - 7 extractors (created by background task)

### Need to Create/Update
- ❌ `app/agents/data/mdl_entity_retrieval.py` - Generic entity retrieval
- ❌ Update `indexing_cli/index_mdl_contextual.py` - Use existing collections
- ❌ Update `app/indexing/processors/table_description_processor.py` - Add categories
- ❌ Update `app/indexing/processors/db_schema_processor.py` - Merge time concepts

---

**Next Action**: Start with Phase 1 - use what's already available! 🚀

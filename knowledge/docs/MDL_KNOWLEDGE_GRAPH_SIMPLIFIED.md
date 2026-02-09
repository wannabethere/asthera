# MDL Knowledge Graph - Simplified Architecture (Using Existing Collections)

## Overview

This document describes the **simplified and realistic** MDL Knowledge Graph architecture that leverages your **existing collections and infrastructure** instead of creating 16 new collections.

## Key Principle

**Reuse existing collections with type discriminators** rather than creating new collections for each entity type.

---

## Existing Infrastructure (Already Available)

### ✅ Already Indexed Collections

| Collection | Purpose | Indexed By | Retrieval Available |
|------------|---------|------------|---------------------|
| `db_schema` | Tables and columns | `index_mdl_standalone.py` | ✅ Yes (`retrieval.py`) |
| `table_descriptions` | Table descriptions | `index_mdl_standalone.py` | ✅ Yes (`retrieval.py`) |
| `column_metadata` | Column metadata | `index_mdl_standalone.py` | ✅ Yes (`retrieval.py`) |
| `sql_pairs` | SQL examples | (existing) | ✅ Yes (`sql_pairs_retrieval.py`) |
| `instructions` | Product instructions | (existing) | ✅ Yes (`instructions.py`) |
| `contextual_edges` | All relationships | (existing) | ✅ Yes |

### ✅ Generic Collections (Use with Type Discriminators)

| Collection | Purpose | Type Discriminator | Notes |
|------------|---------|-------------------|-------|
| `entities` | Generic entities | `entity_type="mdl"`, `mdl_entity_type="product|category|feature|metric"` | For new MDL entity types |
| `evidence` | Generic evidence | `evidence_type="mdl"`, `mdl_entity_type="category|table|column"` | For MDL evidence |

---

## Simplified MDL Entity Mapping

### Core MDL Entities → Existing Collections

| MDL Entity | ChromaDB Collection | Already Indexed? | Retrieval Code |
|------------|---------------------|------------------|----------------|
| **Product** | `entities` (with `entity_type="mdl"`, `mdl_entity_type="product"`) | ❌ No | Need to create |
| **Category** | `entities` (with `entity_type="mdl"`, `mdl_entity_type="category"`) | ❌ No | Need to create |
| **Table** | `table_descriptions` | ✅ **YES** | ✅ `retrieval.py` |
| **Column** | `column_metadata` | ✅ **YES** | ✅ `retrieval.py` |
| **Relationship** | `contextual_edges` | Partial | ✅ Existing |
| **Feature** | `entities` (with `entity_type="mdl"`, `mdl_entity_type="feature"`) | ❌ No | Need to create |
| **Metric** | `entities` (with `entity_type="mdl"`, `mdl_entity_type="metric"`) | ❌ No | Need to create |
| **Example** | `sql_pairs` | ✅ **YES** | ✅ `sql_pairs_retrieval.py` |
| **Instruction** | `instructions` | ✅ **YES** | ✅ `instructions.py` |
| **Edge** | `contextual_edges` | Partial | ✅ Existing |

### Special Cases

**Time Concepts:** Merge into `column_metadata` collection
- Add fields: `is_time_dimension`, `time_granularity`, `is_event_time`
- Store as column metadata properties

**Calculated Columns:** Already supported in `db_schema`
- MDL already has calculated column support
- No separate collection needed

---

## Hierarchical Structure (Simplified)

```
Product (Snyk)
  ↓ [stored in: entities collection, entity_type="mdl", mdl_entity_type="product"]
  
15 Categories (assets, vulnerabilities, etc.)
  ↓ [stored in: entities collection, entity_type="mdl", mdl_entity_type="category"]
  
Tables (AccessRequest, AssetAttributes, etc.)
  ↓ [stored in: table_descriptions collection - ALREADY INDEXED]
  
Columns (id, status, attributes, etc.)
  ↓ [stored in: column_metadata collection - ALREADY INDEXED]
  │   └─ Time Concepts (merged into column metadata)
  
Features (Vulnerability Scanning, Access Control, etc.)
  ↓ [stored in: entities collection, entity_type="mdl", mdl_entity_type="feature"]
  
Metrics & KPIs (Total Vulnerabilities, MTTR, etc.)
  ↓ [stored in: entities collection, entity_type="mdl", mdl_entity_type="metric"]
  
Examples (SQL queries and natural questions)
  ↓ [stored in: sql_pairs collection - ALREADY HAS RETRIEVAL]
  
Instructions (Best practices, constraints, etc.)
  ↓ [stored in: instructions collection - ALREADY HAS RETRIEVAL]
  
Relationships (All edges between entities)
  ↓ [stored in: contextual_edges collection]
```

---

## Query Patterns

### 1. Table Discovery (Already Works!)

```python
from app.agents.data.retrieval import Retrieval
from app.core.dependencies import get_doc_store_provider, get_embeddings_model

# Get table descriptions store (ALREADY INDEXED)
doc_store_provider = get_doc_store_provider()
table_store = doc_store_provider.get_store("table_description")
embeddings = get_embeddings_model()

# Use existing retrieval
retrieval = Retrieval(table_store, embeddings)
results = await retrieval.run(
    query="tables with vulnerability data",
    project_id="Snyk",
    top_k=5
)
```

### 2. Column Lookup (Already Works!)

```python
# Get column metadata store (ALREADY INDEXED)
column_store = doc_store_provider.get_store("column_metadata")

retrieval = Retrieval(column_store, embeddings)
results = await retrieval.run(
    query="columns with PII data",
    project_id="Snyk",
    top_k=10
)
```

### 3. SQL Examples (Already Works!)

```python
from app.agents.data.sql_pairs_retrieval import SqlPairsRetrieval

# Use EXISTING retrieval (app/agents/data/sql_pairs_retrieval.py)
sql_pairs_store = doc_store_provider.get_store("sql_pairs")
sql_retrieval = SqlPairsRetrieval(sql_pairs_store, embeddings)

results = await sql_retrieval.run(
    query="how to query high severity vulnerabilities",
    project_id="Snyk"
)
```

### 4. Instructions (Already Works!)

```python
from app.agents.data.instructions import Instructions

# Use EXISTING retrieval (app/agents/data/instructions.py)
instructions_store = doc_store_provider.get_store("instructions")
instructions_retrieval = Instructions(instructions_store, embeddings)

results = await instructions_retrieval.run(
    query="best practices for vulnerability scanning",
    project_id="Snyk"
)
```

### 5. Category Exploration (New - Use entities collection)

```python
from app.config.mdl_store_mapping_simplified import build_entity_filter, MDLEntityType

# Query entities collection with discriminator
entities_store = doc_store_provider.get_store("entities")

# Build filter for MDL categories
filters = build_entity_filter(
    MDLEntityType.CATEGORY,
    product_name="Snyk"
)
# filters = {"entity_type": "mdl", "mdl_entity_type": "category", "product_name": "Snyk"}

# Query with filters
results = await entities_store.semantic_search(
    query="asset and vulnerability categories",
    where=filters,
    k=10
)
```

### 6. Feature Mapping (New - Use entities collection)

```python
# Build filter for MDL features
filters = build_entity_filter(
    MDLEntityType.FEATURE,
    product_name="Snyk"
)
# filters = {"entity_type": "mdl", "mdl_entity_type": "feature", "product_name": "Snyk"}

results = await entities_store.semantic_search(
    query="vulnerability scanning features",
    where=filters,
    k=5
)
```

### 7. Metric Discovery (New - Use entities collection)

```python
# Build filter for MDL metrics
filters = build_entity_filter(
    MDLEntityType.METRIC,
    product_name="Snyk"
)

results = await entities_store.semantic_search(
    query="vulnerability remediation metrics",
    where=filters,
    k=5
)
```

### 8. Relationship Traversal (Use contextual_edges)

```python
# Query contextual_edges collection
edges_store = doc_store_provider.get_store("contextual_edges")

# Find relationships
filters = {
    "source_entity_type": "table",
    "edge_type": "TABLE_RELATES_TO_TABLE",
    "product_name": "Snyk"
}

results = await edges_store.semantic_search(
    query="relationships between asset and vulnerability tables",
    where=filters,
    k=10
)
```

---

## Integration with Existing Agents

### MDL Context Breakdown Agent

The agent identifies which collection to query based on entity type:

```python
from app.agents.contextual_agents.mdl_context_breakdown_agent import MDLContextBreakdownAgent
from app.config.mdl_store_mapping_simplified import get_chroma_collection, MDLEntityType

agent = MDLContextBreakdownAgent()
breakdown = await agent.breakdown_question(
    user_question="Show me tables with vulnerability data",
    product_name="Snyk"
)

# Breakdown identifies:
# - Entity type: TABLE
# - Collection: "table_descriptions" (ALREADY INDEXED)
# - Filters: {"product_name": "Snyk", "category_name": "vulnerabilities"}

collection = get_chroma_collection(MDLEntityType.TABLE)
# Returns: "table_descriptions"
```

### MDL Edge Pruning Agent

Prunes edges from `contextual_edges` collection:

```python
from app.agents.contextual_agents.mdl_edge_pruning_agent import MDLEdgePruningAgent

agent = MDLEdgePruningAgent()
pruned_edges = await agent.prune_edges(
    user_question="How are assets related to vulnerabilities?",
    discovered_edges=discovered_edges,
    max_edges=10
)
```

---

## 15 Business Categories

The 15 categories are stored in the `entities` collection with:
- `entity_type = "mdl"`
- `mdl_entity_type = "category"`
- `category_name = "assets" | "vulnerabilities" | ...`

| # | Category | Pattern | Example Tables |
|---|----------|---------|----------------|
| 1 | access requests | `^AccessRequest` | AccessRequest, AccessRequestAttributes |
| 2 | application data | `^App[A-Z]` (not AppRisk) | AppBot, AppData, AppInstance |
| 3 | assets | `^Asset[A-Z]` | AssetAttributes, AssetClass |
| 4 | projects | `^Project[A-Z]` | ProjectAttributes, ProjectMeta |
| 5 | vulnerabilities | `^Vulnerability` | Vulnerability-related tables |
| 6 | integrations | `.*Integration` | IntegrationResource |
| 7 | configuration | `^Config` | Config-related tables |
| 8 | audit logs | `^Audit` | AuditLogSearch |
| 9 | risk management | `.*Risk` | AppRiskAttributes, Risk |
| 10 | deployment | `^Deploy` | Deploy-related tables |
| 11 | groups | `^Group` | Group, GroupAttributes |
| 12 | organizations | `^Org` | Org, OrgAttributes |
| 13 | memberships and roles | `.*Membership|.*Role` | OrgMembership, OrgRole |
| 14 | issues | `^Issue` | Issue, IssueAttributes |
| 15 | artifacts | `.*Artifact` | ArtifactoryAttributes |

---

## Edge Types with Priorities

### Critical Priority
- `COLUMN_BELONGS_TO_TABLE` - Core schema
- `TABLE_BELONGS_TO_CATEGORY` - Organization
- `TABLE_RELATES_TO_TABLE` - Foreign keys

### High Priority
- `TABLE_HAS_FEATURE` - Feature mapping
- `FEATURE_SUPPORTS_CONTROL` - Compliance
- `METRIC_FROM_TABLE` - Business metrics
- `EXAMPLE_USES_TABLE` - Usage patterns

### Medium Priority
- `TABLE_FOLLOWS_INSTRUCTION` - Best practices
- `COLUMN_HAS_TIME_CONCEPT` - Time dimensions
- `COLUMN_SUPPORTS_METRIC` - KPI definitions

### Low Priority
- `PRODUCT_HAS_CATEGORY` - Product structure

---

## What Needs to Be Done

### ✅ Already Available (Use As-Is)
1. Table indexing → `index_mdl_standalone.py` ✅
2. Column indexing → `index_mdl_standalone.py` ✅
3. Table retrieval → `retrieval.py` ✅
4. Column retrieval → `retrieval.py` ✅
5. SQL examples → `sql_pairs_retrieval.py` ✅
6. Instructions → `instructions.py` ✅
7. Contextual edges → Existing ✅

### ❌ Needs to Be Created
1. Product entities indexing (to `entities` collection)
2. Category entities indexing (to `entities` collection)
3. Feature entities indexing (to `entities` collection)
4. Metric entities indexing (to `entities` collection)
5. Retrieval helpers for products, categories, features, metrics

---

## Simplified PostgreSQL Schema

Instead of 16 tables, we only need a few:

```sql
-- Use existing tables for core MDL
-- db_schema, table_descriptions, column_metadata (ALREADY EXIST)

-- Generic entities table (for products, categories, features, metrics)
CREATE TABLE IF NOT EXISTS entities (
    entity_id VARCHAR(255) PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,  -- "mdl", "compliance", etc.
    mdl_entity_type VARCHAR(50),       -- "product", "category", "feature", "metric"
    entity_name VARCHAR(255) NOT NULL,
    entity_description TEXT,
    product_name VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type, mdl_entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_product ON entities(product_name);

-- Use existing contextual_relationships table for edges
-- (ALREADY EXISTS)
```

---

## Benefits of Simplified Approach

1. ✅ **Reuses existing infrastructure** - No need to create 16 new collections
2. ✅ **Leverage existing retrieval code** - Tables, columns, SQL pairs, instructions already work
3. ✅ **Simpler to maintain** - Fewer collections to manage
4. ✅ **Type discriminators** - Flexible for adding new entity types
5. ✅ **Already indexed data** - Tables and columns are ready to use
6. ✅ **Existing test coverage** - Retrieval code is already tested

---

## Usage Example: End-to-End Query

```python
from app.config.mdl_store_mapping_simplified import (
    MDLEntityType, 
    get_chroma_collection,
    build_entity_filter,
    has_existing_retrieval
)
from app.agents.data.retrieval import Retrieval
from app.core.dependencies import get_doc_store_provider, get_embeddings_model

async def search_mdl_entity(
    entity_type: MDLEntityType,
    query: str,
    product_name: str = "Snyk",
    project_id: str = "Snyk",
    top_k: int = 5
):
    """Search for MDL entity using appropriate collection"""
    
    # Get collection name
    collection = get_chroma_collection(entity_type)
    
    # Check if existing retrieval is available
    if has_existing_retrieval(entity_type):
        # Use existing retrieval code
        if entity_type == MDLEntityType.TABLE:
            store = doc_store_provider.get_store("table_description")
            retrieval = Retrieval(store, get_embeddings_model())
            return await retrieval.run(query=query, project_id=project_id, top_k=top_k)
        
        elif entity_type == MDLEntityType.EXAMPLE:
            from app.agents.data.sql_pairs_retrieval import SqlPairsRetrieval
            store = doc_store_provider.get_store("sql_pairs")
            retrieval = SqlPairsRetrieval(store, get_embeddings_model())
            return await retrieval.run(query=query, project_id=project_id)
        
        # ... other existing retrievals
    
    else:
        # Use generic query with filters
        store = doc_store_provider.get_store(collection)
        filters = build_entity_filter(entity_type, product_name, project_id)
        
        return await store.semantic_search(
            query=query,
            where=filters,
            k=top_k
        )

# Example usage
results = await search_mdl_entity(
    MDLEntityType.TABLE,
    query="tables with vulnerability data",
    product_name="Snyk"
)
```

---

## Next Steps

1. ✅ Use existing `index_mdl_standalone.py` for tables and columns
2. ❌ Create indexing for products/categories/features/metrics (to `entities` collection)
3. ❌ Create retrieval helpers for new entity types
4. ✅ Use existing retrievals for tables, columns, SQL pairs, instructions
5. ✅ Use `contextual_edges` for all relationships

---

## Summary

**Key Insight:** Instead of creating 16 new collections, we:
- **Reuse** `table_descriptions`, `column_metadata`, `sql_pairs`, `instructions` (already indexed!)
- **Extend** `entities` collection with type discriminators for new types
- **Use** `contextual_edges` for all relationships

**Result:** Simpler, cleaner architecture that leverages existing infrastructure! 🎉

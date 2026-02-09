# MDL Knowledge Graph - START HERE

## 🎯 Quick Navigation

**If you want to understand the architecture:**
→ Read [`MDL_KNOWLEDGE_GRAPH_SIMPLIFIED.md`](MDL_KNOWLEDGE_GRAPH_SIMPLIFIED.md)

**If you want to see what's already done:**
→ Read [`MDL_IMPLEMENTATION_CHECKLIST.md`](MDL_IMPLEMENTATION_CHECKLIST.md)

**If you want configuration details:**
→ See [`app/config/mdl_store_mapping_simplified.py`](../app/config/mdl_store_mapping_simplified.py)

---

## 🚀 TL;DR

### What's Already Working (70%)

✅ **Tables** → Indexed by `index_mdl_standalone.py` to `table_descriptions` collection  
✅ **Columns** → Indexed by `index_mdl_standalone.py` to `column_metadata` collection  
✅ **SQL Examples** → Stored in `sql_pairs` collection with retrieval  
✅ **Instructions** → Stored in `instructions` collection with retrieval  
✅ **Relationships** → Stored in `contextual_edges` collection  

### What Needs Small Updates (20%)

❌ **Categories** → Add to `entities` collection with type discriminator  
❌ **Features** → Add to `entities` collection with type discriminator  
❌ **Metrics** → Add to `entities` collection with type discriminator  
❌ **Time Concepts** → Merge into `column_metadata` fields  

### What's Optional (10%)

❌ **Products** → Can add to `entities` collection if needed  

---

## 📖 Key Insight

**Instead of creating 16 new collections**, we:
- **Reuse** existing collections: `table_descriptions`, `column_metadata`, `sql_pairs`, `instructions`
- **Extend** `entities` collection with type discriminators for new types
- **Use** `contextual_edges` for all relationships

**Result**: Simpler architecture that leverages existing infrastructure! 🎉

---

## 🏗️ Architecture (Simplified)

```
MDL Entity Types → Existing Collections

Tables          → table_descriptions    [✅ ALREADY INDEXED]
Columns         → column_metadata       [✅ ALREADY INDEXED]
Examples        → sql_pairs             [✅ ALREADY EXISTS]
Instructions    → instructions          [✅ ALREADY EXISTS]
Relationships   → contextual_edges      [✅ ALREADY EXISTS]

Products        → entities (entity_type="mdl", mdl_entity_type="product")
Categories      → entities (entity_type="mdl", mdl_entity_type="category")
Features        → entities (entity_type="mdl", mdl_entity_type="feature")
Metrics         → entities (entity_type="mdl", mdl_entity_type="metric")
```

---

## ⚡ Quick Start (Use What's Already Available)

### 1. Index Tables and Columns (Already Works!)

```bash
cd knowledge

python -m indexing_cli.index_mdl_standalone \
    --mdl-file ../data/cvedata/snyk_mdl1.json \
    --project-id "Snyk" \
    --product-name "Snyk" \
    --collections db_schema table_descriptions column_metadata
```

### 2. Query Tables (Already Works!)

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

### 3. Query Columns (Already Works!)

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

### 4. Get SQL Examples (Already Works!)

```python
from app.agents.data.sql_pairs_retrieval import SqlPairsRetrieval

sql_pairs_store = doc_store_provider.get_store("sql_pairs")
sql_retrieval = SqlPairsRetrieval(sql_pairs_store, embeddings)

results = await sql_retrieval.run(
    query="how to query high severity vulnerabilities",
    project_id="Snyk"
)
```

### 5. Get Instructions (Already Works!)

```python
from app.agents.data.instructions import Instructions

instructions_store = doc_store_provider.get_store("instructions")
instructions_retrieval = Instructions(instructions_store, embeddings)

results = await instructions_retrieval.run(
    query="best practices for vulnerability scanning",
    project_id="Snyk"
)
```

---

## 📚 Documentation Structure

### Start Here (You Are Here)
- **[START_HERE.md](MDL_KNOWLEDGE_GRAPH_START_HERE.md)** (This file)

### Core Documentation
1. **[MDL_KNOWLEDGE_GRAPH_SIMPLIFIED.md](MDL_KNOWLEDGE_GRAPH_SIMPLIFIED.md)** - Simplified architecture using existing collections
2. **[MDL_IMPLEMENTATION_CHECKLIST.md](MDL_IMPLEMENTATION_CHECKLIST.md)** - What's done vs. what needs to be created
3. **[mdl_store_mapping_simplified.py](../app/config/mdl_store_mapping_simplified.py)** - Configuration with type discriminators

### Reference (Optional - Original Complex Design)
4. **[MDL_KNOWLEDGE_GRAPH_README.md](MDL_KNOWLEDGE_GRAPH_README.md)** - Original design (16 collections)
5. **[MDL_KNOWLEDGE_GRAPH_STRUCTURE.md](MDL_KNOWLEDGE_GRAPH_STRUCTURE.md)** - Complete original structure
6. **[MDL_KNOWLEDGE_GRAPH_USAGE.md](MDL_KNOWLEDGE_GRAPH_USAGE.md)** - Original usage guide

---

## 🎯 Implementation Phases

### Phase 1: Use What's Already Available (Now!)
**Time**: Immediate  
**Effort**: None

✅ Index tables and columns with `index_mdl_standalone.py`  
✅ Query tables with `retrieval.py`  
✅ Query columns with `retrieval.py`  
✅ Get SQL examples with `sql_pairs_retrieval.py`  
✅ Get instructions with `instructions.py`  

**Result**: 70% of functionality works immediately!

### Phase 2: Small Updates (Next)
**Time**: 4-6 hours  
**Effort**: Low

1. Add category tagging to table indexing
2. Merge time concepts into column metadata
3. Update `index_mdl_contextual.py` to use existing collections

**Result**: 90% of functionality works!

### Phase 3: New Entity Types (If Needed)
**Time**: 8-10 hours  
**Effort**: Medium

1. Create `MDLEntityRetrieval` for generic entities
2. Index products/categories to `entities` collection
3. Index features/metrics to `entities` collection

**Result**: 100% of functionality works!

---

## 🔑 Key Files

### Already Available (Use These)
- ✅ `indexing_cli/index_mdl_standalone.py` - Tables/columns indexing
- ✅ `app/agents/data/retrieval.py` - Generic retrieval
- ✅ `app/agents/data/sql_pairs_retrieval.py` - SQL examples
- ✅ `app/agents/data/instructions.py` - Instructions
- ✅ `app/services/contextual_graph_storage.py` - Edges

### Configuration
- 📄 `app/config/mdl_store_mapping_simplified.py` - Simplified mappings
- 📄 `app/config/mdl_store_mapping.py` - Original complex mappings (reference only)

### Documentation
- 📖 `docs/MDL_KNOWLEDGE_GRAPH_SIMPLIFIED.md` - Simplified architecture
- 📖 `docs/MDL_IMPLEMENTATION_CHECKLIST.md` - Implementation status

---

## 💡 Key Concepts

### Type Discriminators

Instead of creating separate collections, use type discriminators:

```python
# Store in entities collection with discriminator
document.metadata = {
    "entity_type": "mdl",           # Discriminator 1
    "mdl_entity_type": "category",  # Discriminator 2
    "category_name": "assets",
    "product_name": "Snyk"
}

# Query with discriminator
results = store.semantic_search(
    query="asset categories",
    where={
        "entity_type": "mdl",
        "mdl_entity_type": "category",
        "product_name": "Snyk"
    }
)
```

### 15 Business Categories

Categories organize tables into business domains:

1. access requests
2. application data
3. assets
4. projects
5. vulnerabilities
6. integrations
7. configuration
8. audit logs
9. risk management
10. deployment
11. groups
12. organizations
13. memberships and roles
14. issues
15. artifacts

### Time Concepts Merged into Columns

Instead of separate time concepts, add fields to column metadata:

```python
column_metadata = {
    "column_name": "created_at",
    "data_type": "timestamp",
    # Time concept fields:
    "is_time_dimension": True,
    "time_granularity": "second",
    "is_event_time": True,
    "is_process_time": False
}
```

---

## 🔗 Integration Points

### With Hybrid Search Service

```python
from app.services.hybrid_search_service import HybridSearchService
from app.config.mdl_store_mapping_simplified import get_chroma_collection, MDLEntityType

# Get collection for entity type
collection = get_chroma_collection(MDLEntityType.TABLE)
# Returns: "table_descriptions"

search_service = HybridSearchService(
    vector_store_client=vector_store_client,
    collection_name=collection
)

results = await search_service.hybrid_search(
    query="tables with vulnerability data",
    top_k=5,
    where={"product_name": "Snyk"}
)
```

### With Context Breakdown Agent

```python
from app.agents.contextual_agents.mdl_context_breakdown_agent import MDLContextBreakdownAgent

agent = MDLContextBreakdownAgent()
breakdown = await agent.breakdown_question(
    user_question="Show me tables with vulnerability data",
    product_name="Snyk"
)

# Identifies:
# - Entity type: TABLE
# - Collection: "table_descriptions" (already indexed!)
# - Filters: {"product_name": "Snyk", "category_name": "vulnerabilities"}
```

---

## ❓ FAQ

### Q: Do I need to create 16 new collections?
**A**: No! Use existing collections with type discriminators.

### Q: Is table indexing already available?
**A**: Yes! Use `index_mdl_standalone.py` - it already works.

### Q: Can I query tables right now?
**A**: Yes! Use `app/agents/data/retrieval.py` - it already works.

### Q: What about SQL examples?
**A**: Already available! Use `sql_pairs_retrieval.py`.

### Q: What about instructions?
**A**: Already available! Use `instructions.py`.

### Q: What needs to be created?
**A**: Just add categories/features/metrics to `entities` collection with discriminators.

---

## ✅ Summary

**Good News**: 70% of the MDL knowledge graph already works!

**What Works Now**:
- ✅ Table indexing and retrieval
- ✅ Column indexing and retrieval
- ✅ SQL examples retrieval
- ✅ Instructions retrieval
- ✅ Relationship edges

**Small Updates Needed** (4-6 hours):
- ❌ Add category tagging
- ❌ Merge time concepts
- ❌ Use existing collections for new types

**Optional** (8-10 hours):
- ❌ Create generic entity retrieval
- ❌ Index products/categories/features/metrics

---

## 📞 Next Steps

1. **Read**: [`MDL_KNOWLEDGE_GRAPH_SIMPLIFIED.md`](MDL_KNOWLEDGE_GRAPH_SIMPLIFIED.md)
2. **Check**: [`MDL_IMPLEMENTATION_CHECKLIST.md`](MDL_IMPLEMENTATION_CHECKLIST.md)
3. **Use**: Existing indexing and retrieval (already works!)
4. **Update**: Small changes to leverage existing collections fully

---

**Questions?** Check the simplified documentation or implementation checklist!

**Ready to start?** Use Phase 1 (already available) immediately! 🚀

# MDL Knowledge Graph - Complete Documentation Index

## 📚 Documentation Overview

This index provides a complete reference to all MDL (Metadata Definition Language) Knowledge Graph documentation, organized by purpose and audience.

---

## 🚀 Quick Start

**New Users Start Here:**

1. **[MDL_KNOWLEDGE_GRAPH_README.md](MDL_KNOWLEDGE_GRAPH_README.md)**
   - Quick start guide
   - Setup instructions
   - Common query patterns
   - 5 minutes to get started

2. **[MDL_KNOWLEDGE_GRAPH_ARCHITECTURE_DIAGRAM.md](MDL_KNOWLEDGE_GRAPH_ARCHITECTURE_DIAGRAM.md)**
   - Visual system overview
   - Component diagrams
   - Data flow diagrams
   - Integration maps

---

## 📖 Core Documentation

### Complete Reference

**[MDL_KNOWLEDGE_GRAPH_STRUCTURE.md](MDL_KNOWLEDGE_GRAPH_STRUCTURE.md)** (11,000+ lines)
- **Purpose:** Complete structural definition
- **Audience:** Developers, architects
- **Contents:**
  - 16 entity type definitions
  - Attributes and relationships
  - 25+ edge type definitions
  - Storage architecture (ChromaDB + PostgreSQL)
  - Hybrid search patterns
  - Query examples

**[MDL_KNOWLEDGE_GRAPH_USAGE.md](MDL_KNOWLEDGE_GRAPH_USAGE.md)** (9,000+ lines)
- **Purpose:** Practical usage guide
- **Audience:** Developers, data scientists
- **Contents:**
  - Code examples for all entity types
  - 8 usage patterns
  - Context breakdown agent integration
  - Edge pruning agent integration
  - PostgreSQL queries
  - Combined hybrid queries
  - Advanced patterns
  - Troubleshooting

**[MDL_KNOWLEDGE_GRAPH_IMPLEMENTATION_SUMMARY.md](MDL_KNOWLEDGE_GRAPH_IMPLEMENTATION_SUMMARY.md)** (4,000+ lines)
- **Purpose:** Implementation overview
- **Audience:** Project managers, architects
- **Contents:**
  - Deliverables summary
  - System architecture
  - Integration points
  - Benefits
  - Status and next steps

---

## 🗄️ Database & Configuration

### PostgreSQL Schema

**Location:** `knowledge/migrations/create_mdl_knowledge_graph_schema.sql` (1,000+ lines)

**Contents:**
- 16 PostgreSQL tables
  - `mdl_products`, `mdl_categories`, `mdl_tables`, `mdl_columns`
  - `mdl_relationships`, `mdl_insights`, `mdl_metrics`, `mdl_features`
  - `mdl_examples`, `mdl_instructions`, `mdl_time_concepts`
  - `mdl_calculated_columns`, `mdl_business_functions`
  - `mdl_frameworks`, `mdl_ownership`, `mdl_contextual_edges`

- 4 Enriched Views
  - `mdl_tables_enriched` - Tables with category/product context
  - `mdl_columns_enriched` - Columns with full context
  - `mdl_feature_table_mapping` - Feature-to-table mappings
  - `mdl_metrics_enriched` - Metrics with table context

- 2 PostgreSQL Functions
  - `get_tables_by_category(category_name)` - Get tables in category
  - `get_edges_for_entity(entity_id)` - Get edges for entity

- Comprehensive indexes and constraints

**Usage:**
```bash
psql -d your_database -f knowledge/migrations/create_mdl_knowledge_graph_schema.sql
```

### Store Mapping Configuration

**Location:** `knowledge/app/config/mdl_store_mapping.py` (800+ lines)

**Contents:**
- `EntityType` enum (16 entity types)
- `EdgeType` enum (25+ edge types)
- `StoreMapping` dataclass
- Complete store mappings
- Edge type priorities
- Query patterns
- 14 helper functions

**Usage:**
```python
from app.config.mdl_store_mapping import (
    EntityType,
    EdgeType,
    get_chroma_collection,
    get_postgres_table,
    get_edge_priority
)

collection = get_chroma_collection(EntityType.TABLE)
# Returns: "mdl_tables"
```

---

## 🏗️ Architecture & Design

### System Architecture

**[MDL_KNOWLEDGE_GRAPH_ARCHITECTURE_DIAGRAM.md](MDL_KNOWLEDGE_GRAPH_ARCHITECTURE_DIAGRAM.md)**
- **Purpose:** Visual architecture reference
- **Contents:**
  - System overview diagram
  - Entity hierarchy diagram
  - Edge priority diagram
  - Store mapping flow
  - Query pattern flow
  - Data flow diagram
  - Component integration map

### Integration Points

**Primary Services:**
1. **HybridSearchService** - Combines ChromaDB + PostgreSQL
2. **MDLContextBreakdownAgent** - Query understanding
3. **MDLEdgePruningAgent** - Relationship filtering

**Storage:**
- **ChromaDB:** 16 collections for semantic search
- **PostgreSQL:** 16 tables for structured queries

---

## 📊 Entity Types Reference

### 16 Entity Types

| # | Type | Collection | Table | Description |
|---|------|-----------|-------|-------------|
| 1 | Product | `mdl_products` | `mdl_products` | Product definitions |
| 2 | Category | `mdl_categories` | `mdl_categories` | 15 business categories |
| 3 | Table | `mdl_tables` | `mdl_tables` | Database tables |
| 4 | Column | `mdl_columns` | `mdl_columns` | Column metadata |
| 5 | Relationship | `mdl_relationships` | `mdl_relationships` | Table relationships |
| 6 | Insight | `mdl_insights` | `mdl_insights` | Metrics, features, concepts |
| 7 | Metric | `mdl_metrics` | `mdl_metrics` | Business metrics & KPIs |
| 8 | Feature | `mdl_features` | `mdl_features` | Product features |
| 9 | Example | `mdl_examples` | `mdl_examples` | Query examples |
| 10 | Instruction | `mdl_instructions` | `mdl_instructions` | Product instructions |
| 11 | Time Concept | `mdl_time_concepts` | `mdl_time_concepts` | Temporal dimensions |
| 12 | Calculated Column | `mdl_calculated_columns` | `mdl_calculated_columns` | Derived columns |
| 13 | Business Function | `mdl_business_functions` | `mdl_business_functions` | Business capabilities |
| 14 | Framework | `mdl_frameworks` | `mdl_frameworks` | Compliance frameworks |
| 15 | Ownership | `mdl_ownership` | `mdl_ownership` | Access & ownership |
| 16 | Edge | `mdl_contextual_edges` | `mdl_contextual_edges` | All relationships |

### 15 Business Categories

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

---

## 🔗 Edge Types Reference

### Priority Levels

**Critical (Score: 1.0)**
- `COLUMN_BELONGS_TO_TABLE`
- `TABLE_BELONGS_TO_CATEGORY`
- `TABLE_RELATES_TO_TABLE`

**High (Score: 0.8)**
- `TABLE_HAS_FEATURE`
- `FEATURE_SUPPORTS_CONTROL`
- `METRIC_FROM_TABLE`
- `EXAMPLE_USES_TABLE`
- `CATEGORY_BELONGS_TO_PRODUCT`

**Medium (Score: 0.6)**
- `TABLE_FOLLOWS_INSTRUCTION`
- `INSIGHT_USES_TABLE`
- `BUSINESS_FUNCTION_USES_TABLE`
- `TABLE_HAS_COLUMN`
- `COLUMN_REFERENCES_COLUMN`
- `COLUMN_IS_TIME_DIMENSION`
- `COLUMN_SUPPORTS_KPI`
- And more...

**Low (Score: 0.4)**
- `OWNERSHIP_FOR_TABLE`
- `FRAMEWORK_MAPS_TO_TABLE`
- `PRODUCT_HAS_CATEGORY`
- `COLUMN_DERIVED_FROM`
- `CALCULATED_COLUMN_DERIVED_FROM`

See [MDL_KNOWLEDGE_GRAPH_STRUCTURE.md](MDL_KNOWLEDGE_GRAPH_STRUCTURE.md) for complete edge type definitions.

---

## 💻 Code Examples

### Basic Query

```python
from app.services.hybrid_search_service import HybridSearchService
from app.config.mdl_store_mapping import EntityType, get_chroma_collection

search_service = HybridSearchService(
    vector_store_client=vector_store_client,
    collection_name=get_chroma_collection(EntityType.TABLE)
)

results = await search_service.hybrid_search(
    query="tables with vulnerability data",
    top_k=5,
    where={"product_name": "Snyk", "category_name": "vulnerabilities"}
)
```

### With Context Breakdown

```python
from app.agents.contextual_agents.mdl_context_breakdown_agent import MDLContextBreakdownAgent

agent = MDLContextBreakdownAgent()
breakdown = await agent.breakdown_question(
    user_question="Show me asset tables with vulnerability information",
    product_name="Snyk"
)

# Use breakdown results for targeted search
```

### With Edge Pruning

```python
from app.agents.contextual_agents.mdl_edge_pruning_agent import MDLEdgePruningAgent

agent = MDLEdgePruningAgent()
pruned_edges = await agent.prune_edges(
    user_question="How are assets related to vulnerabilities?",
    discovered_edges=discovered_edges,
    max_edges=10
)
```

More examples: [MDL_KNOWLEDGE_GRAPH_USAGE.md](MDL_KNOWLEDGE_GRAPH_USAGE.md)

---

## 🔧 Setup & Configuration

### 1. Database Setup

```bash
# Run PostgreSQL migration
psql -d your_database -f knowledge/migrations/create_mdl_knowledge_graph_schema.sql
```

### 2. Indexing

```bash
# Index Snyk MDL data
cd knowledge
python -m indexing_cli.index_mdl_contextual \
    --mdl-file ../data/cvedata/snyk_mdl1.json \
    --project-id "Snyk" \
    --product-name "Snyk" \
    --preview
```

### 3. Verify Setup

```python
# Check collections
from app.config.mdl_store_mapping import get_all_collections

collections = get_all_collections()
for collection in collections:
    print(f"Collection: {collection}")

# Check tables
from app.config.mdl_store_mapping import get_all_postgres_tables

tables = get_all_postgres_tables()
for table in tables:
    print(f"Table: {table}")
```

---

## 📖 Additional Resources

### Related Documentation

**Contextual Agents:**
- `knowledge/app/agents/contextual_agents/README.md` - Agents overview
- `knowledge/docs/contextual_agents/README.md` - Detailed agent docs

**Previous MDL Work:**
- `knowledge/docs/MDL_CONTEXTUAL_INDEXING.md` - Contextual indexing guide
- `knowledge/docs/MDL_EDGE_TYPES.md` - Edge types reference
- `knowledge/docs/MDL_EXTRACTORS.md` - Extractor documentation
- `knowledge/docs/MDL_INDEXING_GUIDE.md` - Step-by-step indexing
- `knowledge/docs/MDL_HYBRID_SEARCH.md` - Hybrid search patterns

**Hybrid Search:**
- `knowledge/docs/hybrid_search.md` - Hybrid search architecture
- `knowledge/docs/README_HYBRID_SEARCH.md` - Hybrid search usage

---

## 🎯 Use Cases

### 1. Product Discovery
Find products and their capabilities
→ See: [Usage Guide - Product Discovery](MDL_KNOWLEDGE_GRAPH_USAGE.md#1-product-discovery)

### 2. Category Exploration
Explore categories within a product
→ See: [Usage Guide - Category Exploration](MDL_KNOWLEDGE_GRAPH_USAGE.md#2-category-exploration)

### 3. Table Discovery
Find tables by semantic description
→ See: [Usage Guide - Table Discovery](MDL_KNOWLEDGE_GRAPH_USAGE.md#3-table-discovery)

### 4. Column Lookup
Search for specific columns with PII or sensitive data
→ See: [Usage Guide - Column Lookup](MDL_KNOWLEDGE_GRAPH_USAGE.md#4-column-lookup)

### 5. Feature Mapping
Map features to tables and columns
→ See: [Usage Guide - Feature Mapping](MDL_KNOWLEDGE_GRAPH_USAGE.md#5-feature-mapping)

### 6. Metric Discovery
Find business metrics and KPIs
→ See: [Usage Guide - Metric Discovery](MDL_KNOWLEDGE_GRAPH_USAGE.md#6-metric-discovery)

### 7. Example Queries
Find example queries for learning
→ See: [Usage Guide - Example Queries](MDL_KNOWLEDGE_GRAPH_USAGE.md#7-example-queries)

### 8. Relationship Traversal
Traverse relationships between entities
→ See: [Usage Guide - Relationship Traversal](MDL_KNOWLEDGE_GRAPH_USAGE.md#8-relationship-traversal)

---

## 🧪 Testing

### Test Suite
```bash
# Run all MDL tests
cd knowledge
pytest tests/test_mdl_contextual_indexing.py -v

# Test specific components
pytest tests/test_mdl_contextual_indexing.py::test_edge_type_validation -v
pytest tests/test_mdl_contextual_indexing.py::test_mdl_table_extractor -v
pytest tests/test_mdl_contextual_indexing.py::test_end_to_end_indexing -v
```

---

## 🐛 Troubleshooting

### Common Issues

**Collections Not Found**
→ See: [Usage Guide - Troubleshooting](MDL_KNOWLEDGE_GRAPH_USAGE.md#troubleshooting)

**No Results from Query**
→ See: [Usage Guide - No Results](MDL_KNOWLEDGE_GRAPH_USAGE.md#no-results-returned)

**Performance Issues**
→ See: [Usage Guide - Performance](MDL_KNOWLEDGE_GRAPH_USAGE.md#performance-issues)

---

## 📝 Change Log

### Version 1.0 (January 2026)
- ✅ Initial release
- ✅ 16 entity types defined
- ✅ 25+ edge types with priorities
- ✅ PostgreSQL schema (16 tables, 4 views, 2 functions)
- ✅ Store mapping configuration
- ✅ Complete documentation (26,000+ lines)
- ✅ Integration with HybridSearchService
- ✅ Context breakdown and edge pruning agents

---

## 🤝 Contributing

### Adding New Entity Types

1. Update `mdl_store_mapping.py` with new entity type
2. Create PostgreSQL table in migration script
3. Create ChromaDB collection
4. Add extractors if needed
5. Update documentation

### Adding New Edge Types

1. Add to `EdgeType` enum in `mdl_store_mapping.py`
2. Define priority level
3. Update edge pruning agent logic
4. Document in structure guide

---

## 📞 Support

For issues or questions:

1. **Documentation:** Check this index for relevant guides
2. **Examples:** See [MDL_KNOWLEDGE_GRAPH_USAGE.md](MDL_KNOWLEDGE_GRAPH_USAGE.md)
3. **Configuration:** Review `app/config/mdl_store_mapping.py`
4. **Schema:** Check `migrations/create_mdl_knowledge_graph_schema.sql`

---

## 📄 File Locations

### Documentation
- `knowledge/docs/MDL_KNOWLEDGE_GRAPH_README.md`
- `knowledge/docs/MDL_KNOWLEDGE_GRAPH_STRUCTURE.md`
- `knowledge/docs/MDL_KNOWLEDGE_GRAPH_USAGE.md`
- `knowledge/docs/MDL_KNOWLEDGE_GRAPH_IMPLEMENTATION_SUMMARY.md`
- `knowledge/docs/MDL_KNOWLEDGE_GRAPH_ARCHITECTURE_DIAGRAM.md`
- `knowledge/docs/MDL_KNOWLEDGE_GRAPH_INDEX.md` (this file)

### Code
- `knowledge/app/config/mdl_store_mapping.py`
- `knowledge/migrations/create_mdl_knowledge_graph_schema.sql`
- `knowledge/app/agents/contextual_agents/mdl_context_breakdown_agent.py`
- `knowledge/app/agents/contextual_agents/mdl_edge_pruning_agent.py`

### Tests
- `knowledge/tests/test_mdl_contextual_indexing.py`

---

## ✅ Status

**Production Ready** - All components implemented and documented

**Version:** 1.0  
**Created:** January 2026  
**Last Updated:** January 2026

---

**Quick Links:**
- [README (Start Here)](MDL_KNOWLEDGE_GRAPH_README.md)
- [Complete Structure](MDL_KNOWLEDGE_GRAPH_STRUCTURE.md)
- [Usage Guide](MDL_KNOWLEDGE_GRAPH_USAGE.md)
- [Architecture Diagrams](MDL_KNOWLEDGE_GRAPH_ARCHITECTURE_DIAGRAM.md)
- [Implementation Summary](MDL_KNOWLEDGE_GRAPH_IMPLEMENTATION_SUMMARY.md)

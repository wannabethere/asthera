# MDL Knowledge Graph - README

## Overview

The MDL (Metadata Definition Language) Knowledge Graph provides a comprehensive, hierarchical structure for organizing and querying Snyk API metadata. It integrates **ChromaDB** for semantic/vector search with **PostgreSQL** for structured queries, enabling hybrid search capabilities through the `HybridSearchService`.

## What's Included

### 📄 Documentation

1. **MDL_KNOWLEDGE_GRAPH_STRUCTURE.md** - Complete hierarchical structure with 15 entity types
2. **MDL_KNOWLEDGE_GRAPH_USAGE.md** - Usage guide with code examples
3. **This README** - Quick start guide

### 🗄️ Database Schema

- **File**: `migrations/create_mdl_knowledge_graph_schema.sql`
- **Tables**: 16 PostgreSQL tables (products, categories, tables, columns, relationships, insights, metrics, features, examples, instructions, time_concepts, calculated_columns, business_functions, frameworks, ownership, contextual_edges)
- **Views**: 4 enriched views for common queries
- **Functions**: Helper functions for category and edge queries

### ⚙️ Configuration

- **File**: `app/config/mdl_store_mapping.py`
- **Purpose**: Maps entity types to ChromaDB collections and PostgreSQL tables
- **Includes**: 
  - EntityType enum (16 types)
  - EdgeType enum (25+ edge types with priorities)
  - Store mappings
  - Query patterns
  - Helper functions

### 🔗 Integration Points

- **HybridSearchService** - Queries ChromaDB collections with metadata filters
- **MDL Context Breakdown Agent** - Identifies entity types and collections to search
- **MDL Edge Pruning Agent** - Selects relevant edges from contextual graph
- **Indexing CLI** - Populates both ChromaDB and PostgreSQL stores

## Quick Start

### 1. Setup Database

```bash
# Run PostgreSQL migration
psql -d your_database -f knowledge/migrations/create_mdl_knowledge_graph_schema.sql
```

### 2. Index Snyk MDL Data

```bash
cd knowledge

# Preview mode (recommended first)
python -m indexing_cli.index_mdl_contextual \
    --mdl-file ../data/cvedata/snyk_mdl1.json \
    --project-id "Snyk" \
    --product-name "Snyk" \
    --preview

# Full indexing
python -m indexing_cli.index_mdl_contextual \
    --mdl-file ../data/cvedata/snyk_mdl1.json \
    --project-id "Snyk" \
    --product-name "Snyk"
```

### 3. Query the Knowledge Graph

```python
from app.services.hybrid_search_service import HybridSearchService
from app.config.mdl_store_mapping import EntityType, get_chroma_collection

# Initialize search service
search_service = HybridSearchService(
    vector_store_client=vector_store_client,
    collection_name=get_chroma_collection(EntityType.TABLE)
)

# Search for tables
results = await search_service.hybrid_search(
    query="tables with vulnerability data",
    top_k=5,
    where={
        "product_name": "Snyk",
        "category_name": "vulnerabilities"
    }
)

for result in results:
    print(f"Table: {result['metadata']['table_name']}")
    print(f"Description: {result['document'][:200]}...")
    print(f"Score: {result['score']}\n")
```

### 4. Use with Context Breakdown Agent

```python
from app.agents.contextual_agents.mdl_context_breakdown_agent import MDLContextBreakdownAgent

# Initialize agent
agent = MDLContextBreakdownAgent()

# Break down user question
breakdown = await agent.breakdown_question(
    user_question="Show me tables related to asset management in Snyk",
    product_name="Snyk"
)

# Use breakdown results
print(f"Query Type: {breakdown.query_type}")
print(f"Entities: {breakdown.identified_entities}")
print(f"Search Questions: {breakdown.search_questions}")
```

## Knowledge Graph Structure

### Hierarchy

```
Product (e.g., Snyk)
  ↓
Categories (15 categories)
  ├── access requests
  ├── application data
  ├── assets
  ├── projects
  ├── vulnerabilities
  ├── integrations
  ├── configuration
  ├── audit logs
  ├── risk management
  ├── deployment
  ├── groups
  ├── organizations
  ├── memberships and roles
  ├── issues
  └── artifacts
  ↓
Tables (schema entities)
  ↓
Columns (attributes)
  ↓
Insights (metrics, features, concepts)
```

### Entity Types (16)

| Entity Type | ChromaDB Collection | PostgreSQL Table | Description |
|-------------|---------------------|------------------|-------------|
| Product | `mdl_products` | `mdl_products` | Product definitions |
| Category | `mdl_categories` | `mdl_categories` | 15 business categories |
| Table | `mdl_tables` | `mdl_tables` | Table schemas |
| Column | `mdl_columns` | `mdl_columns` | Column metadata |
| Relationship | `mdl_relationships` | `mdl_relationships` | Table relationships |
| Insight | `mdl_insights` | `mdl_insights` | Metrics, features, concepts |
| Metric | `mdl_metrics` | `mdl_metrics` | Business metrics and KPIs |
| Feature | `mdl_features` | `mdl_features` | Product features |
| Example | `mdl_examples` | `mdl_examples` | Query examples |
| Instruction | `mdl_instructions` | `mdl_instructions` | Product instructions |
| Time Concept | `mdl_time_concepts` | `mdl_time_concepts` | Temporal dimensions |
| Calculated Column | `mdl_calculated_columns` | `mdl_calculated_columns` | Derived columns |
| Business Function | `mdl_business_functions` | `mdl_business_functions` | Business capabilities |
| Framework | `mdl_frameworks` | `mdl_frameworks` | Compliance frameworks |
| Ownership | `mdl_ownership` | `mdl_ownership` | Access and ownership |
| Edge | `mdl_contextual_edges` | `mdl_contextual_edges` | All relationships |

### Edge Types (25+)

Edges are categorized by priority:

**Critical Priority:**
- `COLUMN_BELONGS_TO_TABLE` - Core schema relationship
- `TABLE_BELONGS_TO_CATEGORY` - Organization structure
- `TABLE_RELATES_TO_TABLE` - Data model relationships

**High Priority:**
- `TABLE_HAS_FEATURE` - Feature to data mapping
- `FEATURE_SUPPORTS_CONTROL` - Compliance mapping
- `METRIC_FROM_TABLE` - Business intelligence
- `EXAMPLE_USES_TABLE` - Usage patterns

**Medium Priority:**
- `TABLE_FOLLOWS_INSTRUCTION` - Best practices
- `INSIGHT_USES_TABLE` - Business insights
- `COLUMN_SUPPORTS_KPI` - KPI definitions

**Low Priority:**
- `OWNERSHIP_FOR_TABLE` - Governance
- `FRAMEWORK_MAPS_TO_TABLE` - Compliance reference

## 15 Categories

The knowledge graph organizes data into 15 business categories:

1. **access requests** - Access request management
2. **application data** - Application data and resources
3. **assets** - Asset management (Asset* tables)
4. **projects** - Project management (Project* tables)
5. **vulnerabilities** - Vulnerability and finding tables
6. **integrations** - Integration and broker connections
7. **configuration** - Configuration and settings
8. **audit logs** - Audit log and catalog progress
9. **risk management** - Risk assessment (Risk* tables)
10. **deployment** - Deployment processes
11. **groups** - Group management (Group* tables)
12. **organizations** - Organization management (Org* tables)
13. **memberships and roles** - Membership and role management
14. **issues** - Issue tracking (Issue* tables)
15. **artifacts** - Artifact repository

## Common Query Patterns

### 1. Find Tables by Category

```python
from app.config.mdl_store_mapping import get_chroma_collection, EntityType

# Search tables in "assets" category
results = await search_service.hybrid_search(
    collection_name=get_chroma_collection(EntityType.TABLE),
    query="asset management tables",
    top_k=10,
    where={"category_name": "assets", "product_name": "Snyk"}
)
```

### 2. Discover Features

```python
# Search features
results = await search_service.hybrid_search(
    collection_name=get_chroma_collection(EntityType.FEATURE),
    query="vulnerability scanning features",
    top_k=5,
    where={"product_name": "Snyk"}
)
```

### 3. Find Metrics

```python
# Search metrics
results = await search_service.hybrid_search(
    collection_name=get_chroma_collection(EntityType.METRIC),
    query="vulnerability remediation metrics",
    top_k=5,
    where={"metric_type": "kpi"}
)
```

### 4. Get Example Queries

```python
# Search examples
results = await search_service.hybrid_search(
    collection_name=get_chroma_collection(EntityType.EXAMPLE),
    query="how to analyze high severity vulnerabilities",
    top_k=5,
    where={"complexity_level": "medium"}
)
```

### 5. Traverse Relationships

```python
# Search edges
results = await search_service.hybrid_search(
    collection_name=get_chroma_collection(EntityType.EDGE),
    query="relationships between asset and vulnerability tables",
    top_k=10,
    where={"edge_type": "TABLE_RELATES_TO_TABLE"}
)
```

## PostgreSQL Queries

Use PostgreSQL for structured queries:

```sql
-- Get all tables in "vulnerabilities" category
SELECT * FROM get_tables_by_category('vulnerabilities');

-- Get all edges for a table
SELECT * FROM get_edges_for_entity('table_123');

-- Enriched view with category and product
SELECT * FROM mdl_tables_enriched WHERE category_name = 'assets';

-- Feature-to-table mappings
SELECT * FROM mdl_feature_table_mapping WHERE product_name = 'Snyk';
```

## Architecture

### Hybrid Search Flow

```
User Query
    ↓
MDL Context Breakdown Agent
    ↓
Identify Entity Types & Collections
    ↓
HybridSearchService
    ├─→ ChromaDB (semantic search)
    └─→ PostgreSQL (structured filters)
    ↓
Combined Results
    ↓
MDL Edge Pruning Agent (if needed)
    ↓
Final Results
```

### Storage Strategy

- **ChromaDB**: Semantic/fuzzy search on descriptions, purposes, business context
- **PostgreSQL**: Structured queries, joins, aggregations, relationship traversal
- **Hybrid**: Combine both for best results

## Configuration Reference

### Entity Type Enum

```python
from app.config.mdl_store_mapping import EntityType

EntityType.PRODUCT
EntityType.CATEGORY
EntityType.TABLE
EntityType.COLUMN
EntityType.RELATIONSHIP
EntityType.INSIGHT
EntityType.METRIC
EntityType.FEATURE
EntityType.EXAMPLE
EntityType.INSTRUCTION
EntityType.TIME_CONCEPT
EntityType.CALCULATED_COLUMN
EntityType.BUSINESS_FUNCTION
EntityType.FRAMEWORK
EntityType.OWNERSHIP
EntityType.EDGE
```

### Helper Functions

```python
from app.config.mdl_store_mapping import (
    get_store_mapping,
    get_chroma_collection,
    get_postgres_table,
    get_edge_priority,
    is_category_valid,
    supports_hybrid_search
)

# Get ChromaDB collection for entity type
collection = get_chroma_collection(EntityType.TABLE)

# Get PostgreSQL table for entity type
table = get_postgres_table(EntityType.FEATURE)

# Check edge priority
priority = get_edge_priority(EdgeType.TABLE_HAS_FEATURE)

# Validate category
is_valid = is_category_valid("assets")
```

## Testing

```bash
# Run tests for MDL knowledge graph
cd knowledge
pytest tests/test_mdl_contextual_indexing.py -v

# Test edge types
pytest tests/test_mdl_contextual_indexing.py::test_edge_type_validation -v

# Test extractors
pytest tests/test_mdl_contextual_indexing.py::test_mdl_table_extractor -v

# Test integration
pytest tests/test_mdl_contextual_indexing.py::test_end_to_end_indexing -v
```

## Troubleshooting

### Collections Not Found

```python
# Check if collection exists
from app.config.mdl_store_mapping import get_all_collections

collections = get_all_collections()
for collection in collections:
    print(f"Collection: {collection}")
```

### No Results from Query

1. Check collection has data: `collection.count()`
2. Try without metadata filters first
3. Adjust search weights (more semantic vs. keyword)
4. Check product_name and category_name values

### Performance Issues

1. Add metadata filters (product_name, category_name)
2. Limit top_k to reasonable numbers (5-20)
3. Use PostgreSQL for structured queries
4. Use ChromaDB for semantic search

## Next Steps

1. **Index Your Data**: Run the indexing CLI with your MDL file
2. **Explore Categories**: Query different categories to understand structure
3. **Try Hybrid Search**: Combine ChromaDB and PostgreSQL queries
4. **Use Agents**: Integrate with Context Breakdown and Edge Pruning agents
5. **Traverse Graph**: Use edges to navigate relationships

## Resources

- **Structure Doc**: `MDL_KNOWLEDGE_GRAPH_STRUCTURE.md` - Complete structure details
- **Usage Guide**: `MDL_KNOWLEDGE_GRAPH_USAGE.md` - Code examples and patterns
- **Schema**: `migrations/create_mdl_knowledge_graph_schema.sql` - PostgreSQL schema
- **Config**: `app/config/mdl_store_mapping.py` - Store mappings and helpers
- **Indexing**: `indexing_cli/index_mdl_contextual.py` - Indexing CLI

## Support

For issues or questions:
1. Check the usage guide for examples
2. Review test cases for patterns
3. Check logs for indexing/query errors
4. Validate schema matches expectations

---

**Status**: ✅ Ready for use

**Version**: 1.0

**Last Updated**: January 2026

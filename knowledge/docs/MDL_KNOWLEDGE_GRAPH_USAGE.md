# MDL Knowledge Graph Usage Guide

## Overview

This guide demonstrates how to use the MDL Knowledge Graph structure with the hybrid search service and contextual agents for querying Snyk API metadata.

## Prerequisites

1. **Database Setup**: Run the PostgreSQL migration script
   ```bash
   psql -d your_database -f migrations/create_mdl_knowledge_graph_schema.sql
   ```

2. **ChromaDB**: Ensure ChromaDB is running and collections are created

3. **Indexing**: Index Snyk MDL data using the contextual indexing CLI
   ```bash
   python -m indexing_cli.index_mdl_contextual \
       --mdl-file data/cvedata/snyk_mdl1.json \
       --project-id "Snyk" \
       --product-name "Snyk" \
       --preview
   ```

## Configuration

### Store Mapping Configuration

The store mapping configuration (`app/config/mdl_store_mapping.py`) defines how entity types map to storage:

```python
from app.config.mdl_store_mapping import (
    EntityType,
    EdgeType,
    get_store_mapping,
    get_chroma_collection,
    get_postgres_table,
    MDL_CATEGORIES
)

# Get ChromaDB collection for tables
collection = get_chroma_collection(EntityType.TABLE)
# Returns: "mdl_tables"

# Get PostgreSQL table for features
pg_table = get_postgres_table(EntityType.FEATURE)
# Returns: "mdl_features"

# Check valid categories
assert "assets" in MDL_CATEGORIES
assert "vulnerabilities" in MDL_CATEGORIES
```

## Usage Patterns

### 1. Product Discovery

Find products and their capabilities:

```python
from app.services.hybrid_search_service import HybridSearchService
from app.config.mdl_store_mapping import EntityType, get_chroma_collection

# Initialize service
search_service = HybridSearchService(
    vector_store_client=vector_store_client,
    collection_name=get_chroma_collection(EntityType.PRODUCT)
)

# Search for products
results = await search_service.hybrid_search(
    query="security scanning platform with vulnerability detection",
    top_k=5,
    where={
        "vendor": "Snyk"
    }
)

for result in results:
    print(f"Product: {result['metadata']['product_name']}")
    print(f"Description: {result['document'][:200]}...")
    print(f"Score: {result['score']}")
```

### 2. Category Exploration

Explore categories within a product:

```python
from app.config.mdl_store_mapping import EntityType, get_chroma_collection

search_service = HybridSearchService(
    vector_store_client=vector_store_client,
    collection_name=get_chroma_collection(EntityType.CATEGORY)
)

# Find categories related to security
results = await search_service.hybrid_search(
    query="security vulnerabilities and asset management",
    top_k=10,
    where={
        "product_id": "snyk"
    }
)

# Results will include:
# - vulnerabilities category
# - assets category
# - risk management category
# etc.
```

### 3. Table Discovery

Find tables by semantic description:

```python
from app.config.mdl_store_mapping import EntityType, get_chroma_collection

search_service = HybridSearchService(
    vector_store_client=vector_store_client,
    collection_name=get_chroma_collection(EntityType.TABLE)
)

# Find tables related to access requests
results = await search_service.hybrid_search(
    query="tables containing user access request data with approval status",
    top_k=5,
    where={
        "category_name": "access requests",
        "product_id": "snyk"
    }
)

for result in results:
    metadata = result['metadata']
    print(f"Table: {metadata['table_name']}")
    print(f"Category: {metadata['category_name']}")
    print(f"Purpose: {metadata['table_purpose']}")
    print(f"Business Context: {metadata['business_context']}")
```

### 4. Column Lookup

Search for specific columns:

```python
from app.config.mdl_store_mapping import EntityType, get_chroma_collection

search_service = HybridSearchService(
    vector_store_client=vector_store_client,
    collection_name=get_chroma_collection(EntityType.COLUMN)
)

# Find columns with PII data
results = await search_service.hybrid_search(
    query="columns containing user identification or personal information",
    top_k=10,
    where={
        "is_pii": True,
        "product_id": "snyk"
    }
)

for result in results:
    metadata = result['metadata']
    print(f"Column: {metadata['column_name']}")
    print(f"Table: {metadata['table_name']}")
    print(f"Data Type: {metadata['data_type']}")
    print(f"Business Significance: {metadata['business_significance']}")
```

### 5. Feature Mapping

Map features to tables and columns:

```python
from app.config.mdl_store_mapping import EntityType, get_chroma_collection

search_service = HybridSearchService(
    vector_store_client=vector_store_client,
    collection_name=get_chroma_collection(EntityType.FEATURE)
)

# Find features for vulnerability scanning
results = await search_service.hybrid_search(
    query="vulnerability scanning and detection features",
    top_k=5,
    where={
        "product_id": "snyk",
        "feature_category": "security"
    }
)

for result in results:
    metadata = result['metadata']
    print(f"Feature: {metadata['feature_name']}")
    print(f"Description: {metadata['feature_description']}")
    print(f"Tables: {metadata['table_ids']}")
    print(f"Maturity: {metadata['maturity_level']}")
```

### 6. Metric Discovery

Find business metrics and KPIs:

```python
from app.config.mdl_store_mapping import EntityType, get_chroma_collection

search_service = HybridSearchService(
    vector_store_client=vector_store_client,
    collection_name=get_chroma_collection(EntityType.METRIC)
)

# Find metrics for vulnerability management
results = await search_service.hybrid_search(
    query="metrics for tracking vulnerability remediation time and counts",
    top_k=5,
    where={
        "metric_type": "kpi",
        "product_id": "snyk"
    }
)

for result in results:
    metadata = result['metadata']
    print(f"Metric: {metadata['metric_name']}")
    print(f"Type: {metadata['metric_type']}")
    print(f"Formula: {metadata['calculation_formula']}")
    print(f"Aggregation: {metadata['aggregation_type']}")
    print(f"Target: {metadata['target_value']}")
```

### 7. Example Queries

Find example queries for learning:

```python
from app.config.mdl_store_mapping import EntityType, get_chroma_collection

search_service = HybridSearchService(
    vector_store_client=vector_store_client,
    collection_name=get_chroma_collection(EntityType.EXAMPLE)
)

# Find examples for vulnerability analysis
results = await search_service.hybrid_search(
    query="how to query high severity vulnerabilities by project",
    top_k=5,
    where={
        "complexity_level": "medium",
        "use_case": "exploration"
    }
)

for result in results:
    metadata = result['metadata']
    print(f"Question: {metadata['question_text']}")
    print(f"SQL: {metadata['sql_query']}")
    print(f"Complexity: {metadata['complexity_level']}")
    print(f"Use Case: {metadata['use_case']}")
```

### 8. Relationship Traversal

Traverse relationships between entities:

```python
from app.config.mdl_store_mapping import EntityType, get_chroma_collection

search_service = HybridSearchService(
    vector_store_client=vector_store_client,
    collection_name=get_chroma_collection(EntityType.EDGE)
)

# Find relationships for a specific table
results = await search_service.hybrid_search(
    query="relationships connecting asset tables to vulnerability data",
    top_k=10,
    where={
        "source_entity_type": "table",
        "edge_type": "TABLE_RELATES_TO_TABLE",
        "product_id": "snyk"
    }
)

for result in results:
    metadata = result['metadata']
    print(f"From: {metadata['source_entity_id']}")
    print(f"To: {metadata['target_entity_id']}")
    print(f"Type: {metadata['edge_type']}")
    print(f"Relevance: {metadata['relevance_score']}")
```

## Integration with Context Breakdown Agent

The MDL Context Breakdown Agent uses the knowledge graph structure:

```python
from app.agents.contextual_agents.mdl_context_breakdown_agent import MDLContextBreakdownAgent
from app.config.mdl_store_mapping import get_entity_types_for_query_pattern

# Initialize agent
breakdown_agent = MDLContextBreakdownAgent()

# Break down a user question
question = "Show me all tables related to vulnerability management in Snyk"
breakdown = await breakdown_agent.breakdown_question(
    user_question=question,
    product_name="Snyk"
)

# The breakdown identifies:
# - Query type: "table_discovery"
# - Entity types: [EntityType.TABLE, EntityType.CATEGORY]
# - Collections to search: ["mdl_tables", "mdl_categories"]
# - Metadata filters: {"product_id": "snyk", "category_name": "vulnerabilities"}

print(f"Query Type: {breakdown.query_type}")
print(f"Entities: {breakdown.identified_entities}")
print(f"Search Questions: {len(breakdown.search_questions)}")

# Use breakdown results to query appropriate collections
for search_q in breakdown.search_questions:
    entity = search_q['entity']
    collection = get_chroma_collection(EntityType[entity.upper()])
    
    # Perform hybrid search
    results = await search_service.hybrid_search(
        collection_name=collection,
        query=search_q['question'],
        top_k=5,
        where=search_q.get('metadata_filters', {})
    )
```

## Integration with Edge Pruning Agent

Use the MDL Edge Pruning Agent to select relevant edges:

```python
from app.agents.contextual_agents.mdl_edge_pruning_agent import MDLEdgePruningAgent
from app.config.mdl_store_mapping import EdgeType, get_edge_priority

# Initialize agent
pruning_agent = MDLEdgePruningAgent()

# Discover edges from contextual edge collection
edge_results = await search_service.hybrid_search(
    collection_name="mdl_contextual_edges",
    query="relationships between asset tables and vulnerability data",
    top_k=50
)

# Convert to ContextualEdge objects
from app.services.contextual_graph_storage import ContextualEdge

discovered_edges = [
    ContextualEdge.from_metadata(
        document=result['document'],
        metadata=result['metadata']
    )
    for result in edge_results
]

# Prune to most relevant edges
pruned_edges = await pruning_agent.prune_edges(
    user_question="Show me asset tables with vulnerability information",
    discovered_edges=discovered_edges,
    max_edges=10
)

# Use pruned edges for traversal
for edge in pruned_edges:
    print(f"Edge: {edge.edge_type}")
    print(f"From: {edge.source_entity_id} ({edge.source_entity_type})")
    print(f"To: {edge.target_entity_id} ({edge.target_entity_type})")
    print(f"Priority: {get_edge_priority(EdgeType[edge.edge_type])}")
    print(f"Relevance: {edge.relevance_score}")
```

## PostgreSQL Direct Queries

For structured queries, use PostgreSQL directly:

```python
import asyncpg

# Connect to database
conn = await asyncpg.connect(database='your_db')

# Get all tables in "assets" category for Snyk
query = """
SELECT 
    t.table_name,
    t.semantic_description,
    t.table_purpose,
    c.category_name,
    p.product_name
FROM mdl_tables t
JOIN mdl_categories c ON t.category_id = c.category_id
JOIN mdl_products p ON t.product_id = p.product_id
WHERE c.category_name = $1 AND p.product_name = $2
"""
rows = await conn.fetch(query, "assets", "Snyk")

for row in rows:
    print(f"Table: {row['table_name']}")
    print(f"Description: {row['semantic_description']}")
    print(f"Purpose: {row['table_purpose']}")

# Get feature-to-table mappings
query = """
SELECT 
    f.feature_name,
    f.feature_description,
    jsonb_array_elements_text(f.table_ids) AS table_id,
    t.table_name
FROM mdl_features f
JOIN mdl_products p ON f.product_id = p.product_id
LEFT JOIN mdl_tables t ON t.table_id = jsonb_array_elements_text(f.table_ids)
WHERE p.product_name = $1
"""
rows = await conn.fetch(query, "Snyk")

# Use PostgreSQL functions
rows = await conn.fetch("SELECT * FROM get_tables_by_category($1)", "vulnerabilities")

# Get all edges for an entity
rows = await conn.fetch("SELECT * FROM get_edges_for_entity($1)", "table_123")
```

## Combined Hybrid Approach

Combine ChromaDB semantic search with PostgreSQL structured queries:

```python
async def find_features_with_tables(product_name: str, feature_query: str):
    """
    Find features using semantic search, then get table details from PostgreSQL
    """
    # Step 1: Semantic search in ChromaDB
    feature_results = await search_service.hybrid_search(
        collection_name="mdl_features",
        query=feature_query,
        top_k=5,
        where={"product_name": product_name}
    )
    
    # Step 2: Extract feature IDs
    feature_ids = [r['metadata']['feature_id'] for r in feature_results]
    
    # Step 3: Get detailed table info from PostgreSQL
    conn = await asyncpg.connect(database='your_db')
    query = """
    SELECT 
        f.feature_name,
        f.feature_description,
        t.table_name,
        t.semantic_description,
        c.category_name
    FROM mdl_features f
    JOIN mdl_products p ON f.product_id = p.product_id
    CROSS JOIN LATERAL jsonb_array_elements_text(f.table_ids) AS table_id
    LEFT JOIN mdl_tables t ON t.table_id = table_id
    LEFT JOIN mdl_categories c ON t.category_id = c.category_id
    WHERE f.feature_id = ANY($1)
    """
    rows = await conn.fetch(query, feature_ids)
    
    # Step 4: Combine results
    results = []
    for row in rows:
        results.append({
            "feature": row['feature_name'],
            "feature_description": row['feature_description'],
            "table": row['table_name'],
            "table_description": row['semantic_description'],
            "category": row['category_name']
        })
    
    return results

# Usage
results = await find_features_with_tables("Snyk", "vulnerability scanning features")
```

## Advanced Query Patterns

### Multi-Entity Search

Search across multiple entity types:

```python
async def comprehensive_search(query: str, product_name: str):
    """
    Search across tables, features, and metrics simultaneously
    """
    from app.config.mdl_store_mapping import EntityType, get_chroma_collection
    
    # Define entity types to search
    entity_types = [EntityType.TABLE, EntityType.FEATURE, EntityType.METRIC]
    
    # Search each collection
    all_results = []
    for entity_type in entity_types:
        collection = get_chroma_collection(entity_type)
        results = await search_service.hybrid_search(
            collection_name=collection,
            query=query,
            top_k=3,
            where={"product_name": product_name}
        )
        all_results.extend([
            {**r, "entity_type": entity_type.value}
            for r in results
        ])
    
    # Sort by combined score
    all_results.sort(key=lambda x: x['score'], reverse=True)
    
    return all_results[:10]  # Top 10 across all entity types
```

### Category-Based Exploration

Explore all entities within a category:

```python
async def explore_category(category_name: str, product_name: str):
    """
    Get comprehensive view of a category
    """
    # Get category info
    category_results = await search_service.hybrid_search(
        collection_name="mdl_categories",
        query=f"{category_name} category",
        top_k=1,
        where={"category_name": category_name, "product_name": product_name}
    )
    
    if not category_results:
        return None
    
    category_info = category_results[0]
    
    # Get tables in category
    table_results = await search_service.hybrid_search(
        collection_name="mdl_tables",
        query=f"tables in {category_name}",
        top_k=20,
        where={"category_name": category_name, "product_name": product_name}
    )
    
    # Get insights for category
    insight_results = await search_service.hybrid_search(
        collection_name="mdl_insights",
        query=f"insights for {category_name}",
        top_k=10,
        where={"category_name": category_name}
    )
    
    return {
        "category": category_info,
        "tables": table_results,
        "insights": insight_results
    }
```

## Best Practices

1. **Use Metadata Filters**: Always filter by `product_name` or `product_id` for better performance
2. **Combine ChromaDB + PostgreSQL**: Use ChromaDB for semantic search, PostgreSQL for structured queries
3. **Edge Discovery**: Use `mdl_contextual_edges` collection for relationship traversal
4. **Category Organization**: Leverage the 15 categories for organized exploration
5. **Context Breakdown**: Use the MDL Context Breakdown Agent for complex queries
6. **Edge Pruning**: Use the MDL Edge Pruning Agent to reduce noise in results

## Troubleshooting

### No Results Returned

```python
# Check if collection exists and has data
collection = await vector_store_client.get_collection("mdl_tables")
count = collection.count()
print(f"Collection has {count} documents")

# Try without metadata filters first
results = await search_service.hybrid_search(
    query="tables",
    top_k=5
    # No where clause
)
```

### Wrong Results

```python
# Adjust weights for more semantic or keyword matching
search_service = HybridSearchService(
    vector_store_client=vector_store_client,
    collection_name="mdl_tables",
    dense_weight=0.8,  # More semantic (default: 0.7)
    sparse_weight=0.2   # Less keyword (default: 0.3)
)
```

### Performance Issues

```python
# Use PostgreSQL for structured queries
# Use ChromaDB for semantic/fuzzy search
# Limit top_k to reasonable numbers (5-20)
# Add appropriate metadata filters
```

## Next Steps

- See `MDL_CONTEXTUAL_INDEXING.md` for indexing data
- See `MDL_EDGE_TYPES.md` for complete edge type reference
- See `MDL_EXTRACTORS.md` for extractor documentation

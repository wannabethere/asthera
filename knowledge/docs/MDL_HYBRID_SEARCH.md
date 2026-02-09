# MDL Hybrid Search Guide

## Overview

MDL Hybrid Search combines vector similarity search, graph traversal, and metadata filtering to answer complex questions about database schemas, tables, and relationships.

## How It Works

```
User Question: "What tables contain vulnerability data for assets?"
        │
        ▼
┌───────────────────────┐
│ Context Breakdown     │
│ - Query type: table   │
│ - Entities: vulns,    │
│   assets              │
│ - Categories: vulns,  │
│   assets              │
└───────┬───────────────┘
        │
        ▼
┌───────────────────────┐
│ Hybrid Search         │
│ 1. Vector search      │
│ 2. Graph traversal    │
│ 3. Metadata filter    │
└───────┬───────────────┘
        │
        ▼
┌───────────────────────┐
│ Edge Discovery        │
│ - Find relevant edges │
│ - Score by priority   │
└───────┬───────────────┘
        │
        ▼
┌───────────────────────┐
│ Edge Pruning          │
│ - LLM-based selection │
│ - Priority ranking    │
└───────┬───────────────┘
        │
        ▼
┌───────────────────────┐
│ Answer Generation     │
│ - Combine results     │
│ - Format response     │
└───────────────────────┘
```

## Search Strategies

### 1. Table Discovery Queries

**Query**: "What tables store asset information?"

**Strategy**:
1. Vector search in `table_descriptions` with query embedding
2. Metadata filter: `category="assets"`
3. Edge discovery: Find `CATEGORY_CONTAINS_TABLE` edges
4. Return: Table names and descriptions

**Example Code**:
```python
from app.agents.contextual_agents.mdl_context_breakdown_agent import MDLContextBreakdownAgent

agent = MDLContextBreakdownAgent()

# Break down question
breakdown = await agent.breakdown_question(
    user_question="What tables store asset information?",
    product_name="Snyk"
)

# Search questions generated:
# - Entity: tables, Question: "tables that store asset data"
# - Metadata filters: {"product_name": "Snyk", "category": "assets"}
```

### 2. Column Discovery Queries

**Query**: "Which columns contain severity information?"

**Strategy**:
1. Vector search in `column_metadata` with "severity" embedding
2. Edge discovery: Find `BELONGS_TO_TABLE` edges
3. Filter by relevance score
4. Return: Column names, types, and parent tables

**Example Code**:
```python
from app.services.hybrid_search_service import HybridSearchService

service = HybridSearchService(...)

results = await service.hybrid_search(
    query="columns with severity information",
    collections=["column_metadata"],
    metadata_filters={"product_name": "Snyk"},
    limit=10
)
```

### 3. Relationship Queries

**Query**: "How are AssetAttributes and VulnerabilityInstances related?"

**Strategy**:
1. Find tables by name in `table_descriptions`
2. Graph traversal: Find `RELATES_TO_TABLE` edges between them
3. Extract relationship metadata (join columns, cardinality)
4. Return: Relationship description and join path

**Example Code**:
```python
from app.services.contextual_graph_storage import ContextualGraphStorageService

graph_service = ContextualGraphStorageService(...)

# Find relationship edges
edges = await graph_service.find_edges_between(
    source_entity="AssetAttributes",
    target_entity="VulnerabilityInstances",
    edge_types=["RELATES_TO_TABLE"]
)
```

### 4. Category Queries

**Query**: "What categories of tables exist in Snyk?"

**Strategy**:
1. Vector search in `category_mapping`
2. Edge discovery: Find `PRODUCT_HAS_CATEGORY` edges
3. Count tables per category
4. Return: Category list with table counts

**Example Code**:
```python
# Get all categories
edges = await graph_service.search_edges(
    query="Snyk categories",
    edge_types=["PRODUCT_HAS_CATEGORY"],
    metadata_filters={"product_name": "Snyk"}
)
```

### 5. Feature Queries

**Query**: "What features are available for risk management?"

**Strategy**:
1. Vector search in `features` collection
2. Metadata filter: Look for tables in "risk management" category
3. Edge discovery: Find `TABLE_HAS_FEATURE` edges
4. Return: Feature names, descriptions, and supporting tables

**Example Code**:
```python
# Find features
results = await service.hybrid_search(
    query="risk management features",
    collections=["features"],
    metadata_filters={
        "product_name": "Snyk",
        "category": "risk management"
    }
)
```

### 6. Natural Question Queries

**Query**: "How do I count the number of critical vulnerabilities?"

**Strategy**:
1. Vector search in `examples` collection for natural questions
2. Find `QUESTION_ANSWERED_BY_TABLE` edges
3. Extract example queries
4. Return: Example queries and explanations

**Example Code**:
```python
# Find natural question matches
results = await service.hybrid_search(
    query="count critical vulnerabilities",
    collections=["examples"],
    metadata_filters={
        "example_type": "natural_question",
        "product_name": "Snyk"
    }
)
```

## Query Patterns

### Pattern 1: Table + Column Discovery

```
Question: "What table has the 'severity' column?"

Steps:
1. Vector search: "severity column" in column_metadata
2. Find edge: BELONGS_TO_TABLE(severity → table)
3. Return: table name + column metadata
```

### Pattern 2: Category + Table Listing

```
Question: "List all vulnerability-related tables"

Steps:
1. Identify category: "vulnerabilities"
2. Find edges: CATEGORY_CONTAINS_TABLE(vulnerabilities → tables)
3. Return: table list with descriptions
```

### Pattern 3: Relationship Chain

```
Question: "How do I join assets with their vulnerabilities?"

Steps:
1. Find tables: AssetAttributes, VulnerabilityInstances
2. Find path: RELATES_TO_TABLE edges
3. Extract: join columns, cardinality
4. Return: JOIN query pattern
```

### Pattern 4: Feature to Tables

```
Question: "What tables support the asset tracking feature?"

Steps:
1. Find feature: "asset tracking"
2. Find edges: TABLE_HAS_FEATURE(tables → asset tracking)
3. Return: table list
```

### Pattern 5: Metric Calculation

```
Question: "How is the 'Total Assets' metric calculated?"

Steps:
1. Find metric: "Total Assets"
2. Find edges: METRIC_FROM_TABLE, METRIC_FROM_COLUMN
3. Extract: calculation method, source tables
4. Return: calculation description
```

## Edge Pruning in Action

### Example: Table Query

**Query**: "What tables store project information?"

**Discovered Edges** (100+ edges):
- 50x BELONGS_TO_TABLE (columns in projects tables)
- 20x HAS_COLUMN (projects tables have columns)
- 10x CATEGORY_CONTAINS_TABLE (projects category)
- 5x TABLE_IN_CATEGORY (projects tables)
- 10x RELATES_TO_TABLE (projects relationships)
- 5x TABLE_HAS_FEATURE (projects features)

**Pruning Strategy**:
1. **High Priority**: CATEGORY_CONTAINS_TABLE (directly answers question)
2. **Medium Priority**: TABLE_IN_CATEGORY (confirms category)
3. **Lower Priority**: BELONGS_TO_TABLE (too granular for overview)

**Selected Edges** (10 total):
- 5x CATEGORY_CONTAINS_TABLE
- 3x TABLE_IN_CATEGORY
- 2x TABLE_HAS_FEATURE

**Reasoning**: User wants table-level overview, not column details

### Example: Column Query

**Query**: "What columns are in AssetAttributes?"

**Discovered Edges** (80+ edges):
- 50x BELONGS_TO_TABLE (columns belong to AssetAttributes)
- 50x HAS_COLUMN (AssetAttributes has columns)
- 10x CATEGORY_CONTAINS_TABLE (category info)
- 5x RELATES_TO_TABLE (relationships)

**Pruning Strategy**:
1. **High Priority**: HAS_COLUMN (directly answers question)
2. **Lower Priority**: BELONGS_TO_TABLE (inverse, less natural)
3. **Low Priority**: CATEGORY_CONTAINS_TABLE (not relevant)

**Selected Edges** (10 total):
- 9x HAS_COLUMN (one per column, limited to 9)
- 1x CATEGORY_CONTAINS_TABLE (for context)

**Reasoning**: User wants column list for specific table

## Using MDL Context Breakdown Agent

### Integration Example

```python
from app.agents.contextual_agents.mdl_context_breakdown_agent import MDLContextBreakdownAgent
from app.services.hybrid_search_service import HybridSearchService

# Initialize agents
breakdown_agent = MDLContextBreakdownAgent()
search_service = HybridSearchService(...)

async def answer_mdl_question(user_question: str, product_name: str):
    """Answer MDL question using context breakdown + hybrid search"""
    
    # Step 1: Break down question
    breakdown = await breakdown_agent.breakdown_question(
        user_question=user_question,
        product_name=product_name
    )
    
    # Step 2: Execute search questions in parallel
    search_tasks = []
    for search_q in breakdown.search_questions:
        task = search_service.hybrid_search(
            query=search_q["question"],
            collections=[search_q["entity"]],
            metadata_filters=search_q.get("metadata_filters", {}),
            limit=5
        )
        search_tasks.append(task)
    
    search_results = await asyncio.gather(*search_tasks)
    
    # Step 3: Discover edges
    all_edges = []
    for results in search_results:
        for result in results:
            # Find related edges
            edges = await graph_service.find_related_edges(
                entity_id=result.metadata.get("table_name"),
                entity_type="table",
                edge_types=["BELONGS_TO_TABLE", "RELATES_TO_TABLE", "HAS_FEATURE"]
            )
            all_edges.extend(edges)
    
    # Step 4: Prune edges
    from app.agents.contextual_agents.mdl_edge_pruning_agent import MDLEdgePruningAgent
    
    pruning_agent = MDLEdgePruningAgent()
    pruned_edges = await pruning_agent.prune_edges(
        user_question=user_question,
        discovered_edges=all_edges,
        max_edges=10,
        context_breakdown=breakdown.__dict__
    )
    
    # Step 5: Generate answer
    answer = generate_answer(
        user_question=user_question,
        search_results=search_results,
        edges=pruned_edges
    )
    
    return answer
```

## Query Examples

### Example 1: Simple Table Query

```python
question = "What is the AssetAttributes table?"

# Expected breakdown:
# - query_type: "table"
# - identified_entities: ["AssetAttributes"]
# - search_questions: [
#     {
#       "entity": "table_descriptions",
#       "question": "AssetAttributes table description",
#       "metadata_filters": {"table_name": "AssetAttributes"}
#     }
#   ]

# Expected edges:
# - HAS_COLUMN (AssetAttributes → columns)
# - CATEGORY_CONTAINS_TABLE (category → AssetAttributes)
# - RELATES_TO_TABLE (AssetAttributes → related tables)
```

### Example 2: Relationship Query

```python
question = "How do I join AssetAttributes with VulnerabilityInstances?"

# Expected breakdown:
# - query_type: "relationship"
# - identified_entities: ["AssetAttributes", "VulnerabilityInstances"]
# - search_questions: [
#     {
#       "entity": "table_descriptions",
#       "question": "relationship between AssetAttributes and VulnerabilityInstances"
#     }
#   ]

# Expected edges:
# - RELATES_TO_TABLE (AssetAttributes ↔ VulnerabilityInstances)
```

### Example 3: Category Query

```python
question = "What tables are related to vulnerabilities?"

# Expected breakdown:
# - query_type: "category"
# - identified_entities: ["vulnerabilities"]
# - potential_categories: ["vulnerabilities"]
# - search_questions: [
#     {
#       "entity": "table_descriptions",
#       "question": "tables in vulnerabilities category",
#       "metadata_filters": {"category": "vulnerabilities"}
#     }
#   ]

# Expected edges:
# - CATEGORY_CONTAINS_TABLE (vulnerabilities → tables)
# - TABLE_IN_CATEGORY (tables → vulnerabilities)
```

### Example 4: Feature Query

```python
question = "What features are built on the AssetAttributes table?"

# Expected breakdown:
# - query_type: "feature"
# - identified_entities: ["AssetAttributes"]
# - search_questions: [
#     {
#       "entity": "features",
#       "question": "features using AssetAttributes table"
#     }
#   ]

# Expected edges:
# - TABLE_HAS_FEATURE (AssetAttributes → features)
# - FEATURE_SUPPORTS_CONTROL (features → controls)
```

## Performance Optimization

### 1. Metadata Filtering First

Always use metadata filters to reduce vector search space:

```python
# Good
results = await search_service.hybrid_search(
    query="severity columns",
    collections=["column_metadata"],
    metadata_filters={"product_name": "Snyk", "data_type": "integer"}
)

# Less efficient
results = await search_service.hybrid_search(
    query="severity columns",
    collections=["column_metadata"]
    # No filters - searches all products
)
```

### 2. Limit Edge Discovery

Specify edge types to reduce graph traversal:

```python
# Good - specific edge types
edges = await graph_service.find_related_edges(
    entity_id="AssetAttributes",
    edge_types=["BELONGS_TO_TABLE", "HAS_COLUMN"]
)

# Less efficient - searches all edge types
edges = await graph_service.find_related_edges(
    entity_id="AssetAttributes"
)
```

### 3. Parallel Search Execution

Execute independent searches in parallel:

```python
# Good - parallel
table_search = search_service.hybrid_search(...)
column_search = search_service.hybrid_search(...)
results = await asyncio.gather(table_search, column_search)

# Less efficient - sequential
table_results = await search_service.hybrid_search(...)
column_results = await search_service.hybrid_search(...)
```

## Best Practices

1. **Use Context Breakdown**: Always break down questions first
2. **Filter by Product**: Always include `product_name` in filters
3. **Specify Edge Types**: Narrow edge discovery to relevant types
4. **Parallel Execution**: Run independent searches in parallel
5. **Prune Edges**: Use edge pruning for better relevance
6. **Cache Results**: Cache common queries
7. **Monitor Performance**: Log query times and edge counts

## Troubleshooting

### No Results Found

**Possible Causes**:
- Metadata filters too restrictive
- Product name mismatch
- Table/column name typo

**Solutions**:
- Remove filters one by one
- Check exact product name in indexed data
- Try partial match queries

### Too Many Edges

**Possible Causes**:
- Query too broad
- No edge type filtering

**Solutions**:
- Use edge pruning agent
- Specify edge types
- Add metadata filters

### Low Relevance Results

**Possible Causes**:
- Vector embeddings not capturing intent
- Edge priorities not aligned

**Solutions**:
- Rephrase query
- Use more specific terms
- Adjust edge type priorities

## See Also

- [MDL Contextual Indexing Overview](./MDL_CONTEXTUAL_INDEXING.md)
- [MDL Edge Types Reference](./MDL_EDGE_TYPES.md)
- [MDL Indexing Guide](./MDL_INDEXING_GUIDE.md)
- [MDL Extractors Documentation](./MDL_EXTRACTORS.md)

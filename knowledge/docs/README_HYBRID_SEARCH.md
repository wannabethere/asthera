# Hybrid Search Service for Metadata Generation Agents

## Overview

The `HybridSearchService` provides a powerful search capability that combines:
1. **Dense Vector Similarity** (semantic understanding via embeddings)
2. **BM25 Sparse Retrieval** (keyword matching)
3. **Metadata Filtering** (structured constraints)

This hybrid approach is ideal for metadata generation agents that need to:
- Find similar contexts and patterns
- Retrieve relevant metadata entries
- Search for domain mappings and analogies

## Architecture

Based on the hybrid search architecture described in `docs/hybrid_search.md`, this service implements:

- **Dense Search**: Uses ChromaDB with OpenAI embeddings for semantic similarity
- **Sparse Search**: Uses BM25 algorithm for keyword-based ranking
- **Hybrid Scoring**: Combines both scores with configurable weights (default: 70% dense, 30% sparse)

## Quick Start

```python
import chromadb
from langchain_openai import OpenAIEmbeddings
from app.services.hybrid_search_service import HybridSearchService

# Initialize ChromaDB client
chroma_client = chromadb.PersistentClient(path="./chroma_store")

# Initialize embeddings
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# Create hybrid search service
search_service = HybridSearchService(
    chroma_client=chroma_client,
    collection_name="metadata_contexts",
    embeddings_model=embeddings,
    dense_weight=0.7,  # 70% semantic similarity
    sparse_weight=0.3   # 30% keyword matching
)

# Add documents
documents = ["Document 1 text...", "Document 2 text..."]
metadatas = [{"context_id": "ctx_001", "industry": "healthcare"}, ...]
ids = ["doc_001", "doc_002"]

search_service.add_documents(
    documents=documents,
    metadatas=metadatas,
    ids=ids
)

# Perform hybrid search
results = search_service.hybrid_search(
    query="Find similar healthcare compliance contexts",
    top_k=5,
    where={"industry": "healthcare"}
)
```

## Integration with Metadata Generation Agents

### 1. Finding Relevant Contexts

When generating metadata for a new domain, find similar contexts:

```python
# In metadata_generation_agent.py or similar
from app.services.hybrid_search_service import HybridSearchService

async def find_similar_contexts(
    context_description: str,
    search_service: HybridSearchService
) -> List[Dict]:
    """Find contexts similar to the target domain"""
    
    results = search_service.find_relevant_contexts(
        context_description=context_description,
        top_k=5,
        where={"maturity_level": {"$in": ["developing", "nascent"]}}
    )
    
    return results
```

### 2. Context-Aware Pattern Retrieval

Retrieve patterns relevant to a specific context:

```python
async def get_contextual_patterns(
    query: str,
    context_id: str,
    search_service: HybridSearchService
) -> List[Dict]:
    """Get patterns prioritized for a specific context"""
    
    results = search_service.context_aware_retrieval(
        query=query,
        context_id=context_id,
        filters={"pattern_type": "structural"},
        top_k=10
    )
    
    return results
```

### 3. Searching for Domain Mappings

Find cross-domain mappings and analogies:

```python
async def find_domain_mappings(
    source_domain: str,
    target_domain: str,
    search_service: HybridSearchService
) -> List[Dict]:
    """Find mappings between source and target domains"""
    
    query = f"Map {source_domain} concepts to {target_domain}"
    
    results = search_service.hybrid_search(
        query=query,
        top_k=10,
        where={
            "source_domain": source_domain,
            "target_domain": target_domain
        }
    )
    
    return results
```

## API Reference

### HybridSearchService

#### `__init__(chroma_client, collection_name, embeddings_model, dense_weight=0.7, sparse_weight=0.3)`

Initialize the hybrid search service.

**Parameters:**
- `chroma_client`: ChromaDB PersistentClient instance
- `collection_name`: Name of the ChromaDB collection
- `embeddings_model`: Langchain embeddings model (defaults to OpenAI)
- `dense_weight`: Weight for dense vector similarity (default: 0.7)
- `sparse_weight`: Weight for BM25 sparse retrieval (default: 0.3)

#### `hybrid_search(query, top_k=5, where=None, candidate_multiplier=2)`

Perform hybrid search combining dense and sparse retrieval.

**Parameters:**
- `query`: Search query string
- `top_k`: Number of results to return
- `where`: Optional metadata filter dictionary
- `candidate_multiplier`: Multiplier for initial candidate retrieval

**Returns:**
List of dictionaries with:
- `id`: Document ID
- `content`: Document content
- `metadata`: Document metadata
- `dense_score`: Dense vector similarity score
- `bm25_score`: BM25 keyword matching score
- `combined_score`: Weighted combination of both scores
- `distance`: ChromaDB distance metric

#### `find_relevant_contexts(context_description, top_k=5, where=None)`

Find contexts most relevant to a description.

**Parameters:**
- `context_description`: Description of the context/situation
- `top_k`: Number of results to return
- `where`: Optional metadata filters

**Returns:**
List of relevant contexts with scores

#### `context_aware_retrieval(query, context_id=None, filters=None, top_k=10)`

Retrieve documents prioritized for a specific context.

**Parameters:**
- `query`: Natural language query
- `context_id`: Optional context ID to filter by
- `filters`: Additional metadata filters
- `top_k`: Number of results to return

**Returns:**
List of context-aware search results

#### `add_documents(documents, metadatas=None, ids=None)`

Add documents to the collection.

**Parameters:**
- `documents`: List of document strings
- `metadatas`: Optional list of metadata dictionaries
- `ids`: Optional list of document IDs

**Returns:**
List of document IDs that were added

#### `delete_by_metadata(where)`

Delete documents matching metadata filters.

**Parameters:**
- `where`: Metadata filter dictionary

**Returns:**
Number of documents deleted

## Metadata Filtering

The `where` parameter supports ChromaDB metadata filtering:

```python
# Simple equality
where={"industry": "healthcare"}

# In operator
where={"regulatory_frameworks": {"$in": ["HIPAA", "SOC2"]}}

# Contains operator
where={"regulatory_frameworks": {"$contains": "HIPAA"}}

# Multiple conditions
where={
    "industry": "healthcare",
    "maturity_level": {"$in": ["developing", "nascent"]},
    "current_situation": "pre_audit"
}
```

## Performance Considerations

1. **Candidate Multiplier**: The `candidate_multiplier` parameter controls how many candidates are retrieved before re-ranking. Higher values (2-3) improve quality but increase latency.

2. **Collection Size**: For large collections (>100k documents), consider:
   - Using metadata filters to narrow the search space
   - Adjusting `candidate_multiplier` based on collection size
   - Pre-filtering by metadata before semantic search

3. **Embedding Model**: The default `text-embedding-3-small` balances quality and speed. For better quality, use `text-embedding-3-large` (slower but more accurate).

## Example: Full Integration

See `examples/hybrid_search_example.py` for a complete working example showing:
- Adding context documents
- Finding relevant contexts
- Context-aware retrieval
- Metadata filtering

## Best Practices

1. **Collection Organization**: Use separate collections for different data types:
   - `metadata_contexts`: Organizational contexts
   - `metadata_patterns`: Learned patterns
   - `domain_mappings`: Cross-domain mappings

2. **Metadata Design**: Include rich metadata for effective filtering:
   - Domain identifiers
   - Framework names
   - Maturity levels
   - Industry classifications

3. **Query Design**: Write queries that leverage both semantic and keyword matching:
   - Include domain-specific terminology
   - Use natural language descriptions
   - Combine with metadata filters

4. **Score Interpretation**: 
   - `combined_score > 0.7`: Very relevant
   - `combined_score 0.5-0.7`: Moderately relevant
   - `combined_score < 0.5`: Less relevant

## Troubleshooting

**No results returned:**
- Check that documents have been added to the collection
- Verify metadata filters are not too restrictive
- Ensure query is not too specific

**Low scores:**
- Try broader queries
- Adjust `dense_weight` and `sparse_weight` ratios
- Check if documents are semantically similar to query

**Performance issues:**
- Reduce `candidate_multiplier`
- Use metadata filters to narrow search space
- Consider using a faster embedding model


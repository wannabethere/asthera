# Separate Collections Design for Policy Documents

## Problem Statement

Previously, all policy document content (entities, context, requirements, evidence, fields, and full content) was stored in a single collection called `policy_documents`. This made it difficult to:

1. Query specific types of extracted information (e.g., only entities or only requirements)
2. Organize and manage different types of compliance data
3. Optimize search performance for specific extraction types
4. Track what types of data are indexed

## Solution

The system now stores different extraction types in **separate collections**:

### Collection Structure

1. **`policy_documents`** - Full policy document content
2. **`policy_entities`** - Extracted entities (policies, requirements, controls, procedures)
3. **`policy_context`** - Organizational context (industry, size, maturity level, etc.)
4. **`policy_requirements`** - Individual requirement documents
5. **`policy_evidence`** - Evidence requirements and needs
6. **`policy_fields`** - Extracted fields and metadata

### Benefits

1. **Better Query Performance**: Query only the collection you need (e.g., search entities separately from full documents)
2. **Clearer Organization**: Each extraction type has its own collection
3. **Easier Management**: Can update/delete specific types without affecting others
4. **Better Tracking**: The indexing result now includes a breakdown of what was indexed where

### Indexing Result Structure

When you index a policy document, the result now includes a breakdown:

```python
{
    "success": True,
    "documents_indexed": 12,  # Total across all collections
    "domain": "compliance",
    "file_path": "/path/to/policy.pdf",
    "breakdown": {
        "context": {
            "success": True,
            "count": 1,
            "store": "policy_context"
        },
        "entities": {
            "success": True,
            "count": 1,
            "store": "policy_entities"
        },
        "requirement": {
            "success": True,
            "count": 9,
            "store": "policy_requirements"
        },
        "full_content": {
            "success": True,
            "count": 1,
            "store": "policy_documents"
        }
    }
}
```

### Usage

The API remains the same - no changes needed to your indexing code:

```python
result = await indexing_service.index_policy_document(
    file_path="path/to/policy.pdf",
    domain="compliance",
    metadata={"source": "cli"}
)

# Check breakdown
print(f"Indexed {result['documents_indexed']} total documents")
print(f"Breakdown: {result['breakdown']}")
```

### Querying Separate Collections

You can now query specific collections:

```python
# Query only entities
entities_store = indexing_service.stores["policy_entities"]
entities_results = entities_store.similarity_search(
    query="Access Control Policy",
    k=5
)

# Query only requirements
requirements_store = indexing_service.stores["policy_requirements"]
requirements_results = requirements_store.similarity_search(
    query="password management",
    k=5
)
```

### Migration Notes

- **Existing Data**: Documents already indexed in the old `policy_documents` collection remain there
- **New Indexing**: New indexing operations will use the separate collections
- **Preview Mode**: Preview mode still saves all documents to a single JSON file for review, but the breakdown shows what would go where

## Technical Details

### Document Routing

Documents are routed to collections based on the `extraction_type` metadata field:

- `extraction_type: "context"` → `policy_context`
- `extraction_type: "entities"` → `policy_entities`
- `extraction_type: "requirement"` → `policy_requirements`
- `extraction_type: "full_content"` → `policy_documents`
- `extraction_type: "evidence"` → `policy_evidence`
- `extraction_type: "fields"` → `policy_fields`

### Store Initialization

Both ChromaDB and Qdrant stores are initialized with the new collections:

```python
store_configs = {
    "policy_documents": {"tf_idf": True},
    "policy_entities": {"tf_idf": True},
    "policy_context": {"tf_idf": True},
    "policy_requirements": {"tf_idf": True},
    "policy_evidence": {"tf_idf": True},
    "policy_fields": {"tf_idf": True},
}
```


# Unified Collection Design with Framework Metadata Filtering

## Overview

The indexing service uses **unified collections** with framework information stored in metadata. This design supports any number of compliance frameworks (SOC2, HIPAA, ISO 27001, PCI-DSS, GDPR, etc.) while enabling cross-framework queries.

## Key Design Principles

### 1. Unified Collections (Not Framework-Specific)

**Design:**
- Single unified collections for each content type
- Framework stored in document metadata for filtering
- Enables cross-framework queries

**Collections:**
- `policy_documents` - All policy documents (filter by `metadata.framework`)
- `policy_entities` - All extracted entities (filter by `metadata.framework`)
- `policy_context` - All organizational context (filter by `metadata.framework`)
- `policy_requirements` - All requirements (filter by `metadata.framework`)
- `policy_evidence` - All evidence needs (filter by `metadata.framework`)
- `policy_fields` - All extracted fields (filter by `metadata.framework`)
- `compliance_controls` - All compliance controls (filter by `metadata.framework`)
- `risk_controls` - All risk controls (filter by `metadata.framework`)

### 2. Framework Metadata Filtering

Framework information is stored in document metadata:
```python
{
    "framework": "SOC2",  # Original framework name
    "domain": "compliance",
    "extraction_type": "entities",
    ...
}
```

This allows:
- **Single-framework queries**: Filter by `framework="SOC2"`
- **Cross-framework queries**: Search across all frameworks
- **Multi-framework queries**: Filter by multiple frameworks

### 3. Framework Name Handling

Framework names are preserved as provided (not normalized in metadata):
- "SOC2" → stored as "SOC2"
- "SOC 2" → stored as "SOC 2"
- "ISO 27001" → stored as "ISO 27001"
- "HIPAA" → stored as "HIPAA"

### 4. Updated Methods

#### `index_policy_document()`
- **New parameter**: `framework` (optional)
- Creates stores: `{framework}_documents`, `{framework}_entities`, `{framework}_context`, etc.
- Defaults to "policy" if framework not provided

#### `index_compliance_controls()` (new generic method)
- Generic method for indexing controls from any framework
- Replaces framework-specific methods
- Creates store: `{framework}_controls`

#### `index_soc2_controls()` (backward compatible)
- Still available for backward compatibility
- Internally calls `index_compliance_controls(framework="SOC2")`

#### `index_risk_controls()`
- **New parameter**: `framework` (optional)
- Creates store: `{framework}_risk_controls`
- Defaults to "Risk Management" if framework not provided

## Store Structure

### Unified Collections

All frameworks share the same collections, differentiated by metadata:

1. **`policy_documents`** - Full document content (all frameworks)
2. **`policy_entities`** - Extracted entities (all frameworks)
3. **`policy_context`** - Organizational context (all frameworks)
4. **`policy_requirements`** - Individual requirements (all frameworks)
5. **`policy_evidence`** - Evidence requirements (all frameworks)
6. **`policy_fields`** - Extracted fields (all frameworks)
7. **`compliance_controls`** - Control documents (all frameworks)
8. **`risk_controls`** - Risk control documents (all frameworks)

### Example: Data in Collections

**policy_documents collection:**
```
Document 1: {framework: "SOC2", content: "Access Control Policy..."}
Document 2: {framework: "HIPAA", content: "HIPAA Access Policy..."}
Document 3: {framework: "ISO 27001", content: "ISO Access Control..."}
```

**policy_entities collection:**
```
Entity 1: {framework: "SOC2", entity_type: "policy", entity_name: "Access Control Policy"}
Entity 2: {framework: "HIPAA", entity_type: "policy", entity_name: "HIPAA Access Policy"}
Entity 3: {framework: "ISO 27001", entity_type: "control", entity_name: "A.9.1.1"}
```

## Usage Examples

### Index Policy Document with Framework

```python
# Index SOC2 policy (stored in policy_documents with framework="SOC2" in metadata)
result = await service.index_policy_document(
    file_path="soc2_policy.pdf",
    framework="SOC2",
    domain="compliance"
)

# Index HIPAA policy (stored in policy_documents with framework="HIPAA" in metadata)
result = await service.index_policy_document(
    file_path="hipaa_policy.pdf",
    framework="HIPAA",
    domain="compliance"
)

# Index ISO 27001 policy (stored in policy_documents with framework="ISO 27001" in metadata)
result = await service.index_policy_document(
    file_path="iso27001_policy.pdf",
    framework="ISO 27001",
    domain="compliance"
)
```

### Index Compliance Controls

```python
# Index SOC2 controls (backward compatible, stored in compliance_controls)
result = await service.index_soc2_controls(
    file_path="soc2_controls.pdf"
)

# Index any framework controls (stored in compliance_controls with framework in metadata)
result = await service.index_compliance_controls(
    file_path="hipaa_controls.pdf",
    framework="HIPAA"
)

result = await service.index_compliance_controls(
    file_path="iso27001_controls.pdf",
    framework="ISO 27001"
)
```

### Search with Framework Filtering

```python
# Search across all frameworks
results = await service.search(
    query="access control requirements",
    content_types=["policy_requirements"]
)

# Search only SOC2
results = await service.search(
    query="access control requirements",
    content_types=["policy_requirements"],
    framework="SOC2"
)

# Search across multiple frameworks (search all, then filter in application)
results = await service.search(
    query="password management",
    content_types=["policy_documents"]
)
# Filter results by framework in application code
soc2_results = [r for r in results["results"] if r.get("metadata", {}).get("framework") == "SOC2"]
hipaa_results = [r for r in results["results"] if r.get("metadata", {}).get("framework") == "HIPAA"]
```

### Cross-Framework Queries

```python
# Find access control policies across all frameworks
results = await service.search(
    query="access control policy",
    content_types=["policy_documents"]
)
# Results include documents from SOC2, HIPAA, ISO 27001, etc.

# Find entities across frameworks
results = await service.search(
    query="password management",
    content_types=["policy_entities"]
)
```

## Benefits

1. **Cross-Framework Queries**: Search across all frameworks in a single query
2. **Scalability**: Supports unlimited frameworks without code changes
3. **Unified Organization**: All frameworks in same collections, filtered by metadata
4. **Flexibility**: Framework names preserved as provided (no forced normalization)
5. **Backward Compatibility**: Existing methods still work
6. **Performance**: Pre-initialized stores, no lazy creation overhead
7. **Simplified Management**: Fewer collections to manage

## Implementation Details

### Store Initialization

All policy/compliance collections are **pre-initialized** (hardcoded) to ensure availability:
- `policy_documents`, `policy_entities`, `policy_context`, `policy_requirements`, `policy_evidence`, `policy_fields`
- `compliance_controls`, `risk_controls`

### Framework Metadata

Framework is stored in document metadata:
```python
doc.metadata = {
    "framework": "SOC2",  # Original framework name
    "domain": "compliance",
    "extraction_type": "entities",
    ...
}
```

### Search Filtering

The `search()` method supports framework filtering:
```python
results = await service.search(
    query="...",
    framework="SOC2",  # Filters by metadata.framework
    content_types=["policy_documents"]
)
```

### TF-IDF Configuration

- **ChromaDB**: TF-IDF enabled by default (`tf_idf=True`)
- **Qdrant**: TF-IDF disabled by default (`tf_idf=False`)
- All policy/compliance stores use same TF-IDF setting per vector store type

## Migration Notes

- **Existing Data**: Documents already indexed in old collections remain accessible
- **New Indexing**: New indexing operations use unified collections with framework in metadata
- **Search**: Use `framework` parameter in `search()` method to filter by framework
- **Cross-Framework Queries**: Omit `framework` parameter to search across all frameworks

## Query Examples

### Single Framework Query
```python
# Get all SOC2 requirements
results = await service.search(
    query="access control",
    content_types=["policy_requirements"],
    framework="SOC2"
)
```

### Cross-Framework Query
```python
# Compare access control requirements across frameworks
results = await service.search(
    query="access control requirements",
    content_types=["policy_requirements"]
)
# Results include SOC2, HIPAA, ISO 27001, etc.
```

### Multi-Framework Analysis
```python
# Get entities from multiple frameworks
soc2_entities = await service.search(
    query="password policy",
    content_types=["policy_entities"],
    framework="SOC2"
)

hipaa_entities = await service.search(
    query="password policy",
    content_types=["policy_entities"],
    framework="HIPAA"
)

# Compare across frameworks
all_entities = await service.search(
    query="password policy",
    content_types=["policy_entities"]
)
```

## Benefits of Unified Collections

1. **Cross-Framework Analysis**: Query across all frameworks simultaneously
2. **Comparative Studies**: Compare how different frameworks handle the same topic
3. **Unified Search**: Single query to find information regardless of framework
4. **Simplified Management**: Fewer collections to maintain
5. **Better Context**: See relationships between frameworks in search results


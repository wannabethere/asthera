# Contextual Edges Compatibility Verification

## Overview
This document confirms that the generated contextual edges are compatible with the existing system architecture, including:
- `hybrid_search_service.py`
- `mdl_context_breakdown_agent.py`
- `mdl_reasoning_nodes.py`
- `contextual_graph_storage.py`

## Edge Structure

### Required Fields in Metadata
All edges include the following required fields in their metadata:

1. **`edge_id`**: Unique identifier for the edge (e.g., `edge_c7e850986657`)
2. **`source_entity_id`**: ID of the source entity (e.g., `framework_soc2`)
3. **`source_entity_type`**: Type of source entity (e.g., `framework`, `control`, `policy`, `actor`, `risk`, `product`, `domain_knowledge`)
4. **`target_entity_id`**: ID of the target entity (e.g., `control_soc2_soc2-sd-001`)
5. **`target_entity_type`**: Type of target entity
6. **`edge_type`**: Relationship type (see Edge Types below)
7. **`context_id`**: Context identifier for grouping (e.g., `framework_soc2`)
8. **`relevance_score`**: Relevance score (0.0 to 1.0)

### Page Content Format
- **`page_content`**: Human-readable document description (string), NOT JSON
  - Example: `"SOC2 framework has control SOC 2 - System Description"`
  - This is used for semantic search and vector similarity matching

### Additional Metadata Fields
- **`content_type`**: Always `"contextual_edges"`
- **`domain`**: Always `"compliance"` for compliance-related edges
- **`framework`**: Framework name when applicable (e.g., `"SOC2"`, `"HIPAA"`, `"ISO27001"`, `"FEDRAMP"`)
- **`product_name`**: Product name for product-related edges (e.g., `"Snyk"`)
- **`indexed_at`**: ISO timestamp of when the edge was created
- **`source`**: Source identifier (e.g., `"hierarchical_edge_generation"`)

## Edge Types

The following edge types are supported:

1. **`HAS_CONTROL`**: Framework → Control
   - Example: `SOC2 framework has control SOC 2 - System Description`

2. **`HAS_POLICY`**: Framework → Policy
   - Example: `SOC2 framework has policy Access Control Policy`

3. **`DEFINES_CONTROL`**: Policy → Control
   - Example: `Policy Access Control Policy defines control SOC 2 - System Description`

4. **`REQUIRES_ACTOR`**: Policy → Actor
   - Example: `Policy Access Control Policy requires actor Compliance Manager`

5. **`MANAGED_BY_ACTOR`**: Control → Actor
   - Example: `Control SOC 2 - System Description is managed by actor Compliance Manager`

6. **`MITIGATES_RISK`**: Control → Risk
   - Example: `Control SOC 2 - System Description mitigates risk Unauthorized Access`

7. **`ADDRESSES_RISK`**: Policy → Risk
   - Example: `Policy Access Control Policy addresses risk Unauthorized Access`

8. **`USES_DOMAIN_KNOWLEDGE`**: Actor → Domain Knowledge
   - Example: `Actor Compliance Manager uses domain knowledge SOC2 Security Compliance`

9. **`RELATED_TO_DOMAIN_KNOWLEDGE`**: Product → Domain Knowledge
   - Example: `Product Snyk is related to domain knowledge SOC2 Security Compliance`

## System Integration

### 1. Hybrid Search Service (`hybrid_search_service.py`)
- **Usage**: Edges are retrieved using hybrid search (vector similarity + BM25 + metadata filtering)
- **Compatibility**: ✅ Edges have proper `page_content` for semantic search and complete metadata for filtering

### 2. MDL Context Breakdown Agent (`mdl_context_breakdown_agent.py`)
- **Usage**: Identifies edge types and generates search questions
- **Filters Used**: 
  - `product_name` (for product-specific queries)
  - Generic entity stores (no specific entity IDs)
- **Compatibility**: ✅ Edges include `product_name` and `framework` metadata for filtering

### 3. MDL Reasoning Nodes (`mdl_reasoning_nodes.py`)
- **Usage**: 
  - Retrieves edges using `retrieve_edges()` with filters
  - Filters by `source_entity_id`, `target_entity_id`, `edge_type`, `product_name`
  - Uses `discover_edges_by_context()` for semantic edge discovery
- **Compatibility**: ✅ All required filter fields are present in edge metadata

### 4. Contextual Graph Storage (`contextual_graph_storage.py`)
- **Usage**: 
  - `discover_edges_by_context()`: Semantic search with optional filters
  - `get_edges_for_context()`: Metadata-only filtering by `context_id`, `source_entity_id`, `edge_type`
  - `ContextualEdge.from_metadata()`: Reconstructs edge objects from stored metadata
- **Compatibility**: ✅ 
  - `page_content` is the document string (not JSON)
  - All metadata fields match `ContextualEdge` class expectations
  - `from_metadata()` can successfully reconstruct edges

## Filter Examples

### By Source Entity
```python
filters = {"source_entity_id": "framework_soc2"}
```

### By Target Entity
```python
filters = {"target_entity_id": "control_soc2_soc2-sd-001"}
```

### By Edge Type
```python
filters = {"edge_type": "HAS_CONTROL"}
```

### By Framework
```python
filters = {"framework": "SOC2"}
```

### By Product
```python
filters = {"product_name": "Snyk"}
```

### Combined Filters
```python
filters = {
    "source_entity_id": "framework_soc2",
    "edge_type": "HAS_CONTROL",
    "framework": "SOC2"
}
```

## Verification

Run the verification script to check compatibility:

```bash
python3 app/indexing/examples/verify_contextual_edges_compatibility.py
```

This will:
1. Verify edge structure matches expected format
2. Check all required fields are present
3. Ensure `page_content` is a string (not JSON)
4. Display edge type summary

## Edge Statistics

Current edge counts by type:
- **ADDRESSES_RISK**: 936 edges
- **DEFINES_CONTROL**: 7,848 edges
- **HAS_CONTROL**: 66 edges
- **HAS_POLICY**: 90 edges
- **MANAGED_BY_ACTOR**: 2,180 edges
- **MITIGATES_RISK**: 19,163 edges
- **RELATED_TO_DOMAIN_KNOWLEDGE**: 27 edges
- **REQUIRES_ACTOR**: 90 edges
- **USES_DOMAIN_KNOWLEDGE**: 135 edges

**Total**: 30,535 edges

## Conclusion

✅ **All contextual edges are fully compatible with the existing system architecture.**

The edges:
- Have the correct structure (`page_content` as document string, metadata with all required fields)
- Support all filter types used by the agents and services
- Include framework and product metadata for proper routing
- Can be successfully parsed by `ContextualEdge.from_metadata()`
- Work with hybrid search for semantic discovery
- Support metadata-only filtering for precise queries

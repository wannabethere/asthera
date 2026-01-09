# Contextual Graph Agents - Data Store Integration Enhancements

## Overview

The Contextual Graph Retrieval and Reasoning agents have been enhanced to use **all available data stores** from the knowledge base, ensuring no extracted information is missed.

## Data Stores Integrated

### 1. Control Storage Service
- **Access**: `contextual_graph_service.control_service`
- **Data**: Control definitions, frameworks, categories, vector document IDs
- **Methods Used**:
  - `get_control(control_id)` - Get control details
  - `get_controls_by_framework(framework)` - Get controls by framework

### 2. Requirement Storage Service
- **Access**: `contextual_graph_service.requirement_service`
- **Data**: Requirements for controls, requirement types, requirement text
- **Methods Used**:
  - `get_requirements_for_control(control_id)` - Get all requirements for a control
  - `get_requirement(requirement_id)` - Get specific requirement

### 3. Evidence Storage Service
- **Access**: `contextual_graph_service.evidence_service`
- **Data**: Evidence types, categories, collection methods
- **Methods Used**:
  - `get_evidence_type(evidence_id)` - Get evidence type details
  - `get_evidence_by_category(category)` - Get evidence by category

### 4. Measurement Storage Service
- **Access**: `contextual_graph_service.measurement_service`
- **Data**: Compliance measurements, risk analytics, historical data
- **Methods Used**:
  - `get_measurements_for_control(control_id, context_id, days)` - Get measurements
  - `get_risk_analytics(control_id)` - Get risk analytics
  - `get_risk_analytics_batch(control_ids)` - Batch analytics

### 5. Vector Storage (Contextual Graph Storage)
- **Access**: `contextual_graph_service.vector_storage`
- **Data**: Contextual edges, control profiles, context definitions
- **Methods Used**:
  - `get_edges_for_context(context_id, source_entity_id, edge_type, top_k)` - Get edges
  - `search_edges(query, context_id, filters, top_k)` - Search edges
  - `get_control_profiles_for_context(context_id, framework, top_k)` - Get profiles
  - `search_control_profiles(query, context_id, filters, top_k)` - Search profiles

## Enhancements Made

### ContextualGraphRetrievalAgent

#### Enhanced Context Enrichment
- **Before**: Only basic metadata (frameworks, systems, completeness)
- **After**: Includes:
  - Edge counts for each context
  - Control profile counts
  - Entity types found in edges
  - Rich metadata from all stores

```python
# Now returns:
{
    "context_id": "ctx_001",
    "edges_count": 45,
    "controls_count": 12,
    "entity_types": ["control", "requirement", "evidence"],
    "context_completeness": 0.85
}
```

### ContextualGraphReasoningAgent

#### 1. Enhanced Priority Controls
- **Before**: Basic control information
- **After**: Enriched with:
  - Requirements for each control
  - Evidence types
  - Measurements and compliance history
  - Risk analytics (trends, scores, failures)
  - Contextual edges (relationships)
  - Entity counts

```python
# Enhanced control result:
{
    "control": {...},
    "requirements": [...],  # NEW
    "requirements_count": 5,  # NEW
    "evidence_types": [...],  # NEW
    "evidence_count": 3,  # NEW
    "measurements": [...],  # NEW
    "measurements_count": 12,  # NEW
    "risk_analytics": {...},  # NEW
    "contextual_edges": [...],  # NEW
    "edges_count": 8  # NEW
}
```

#### 2. Enhanced Reasoning Path
- **Before**: Basic reasoning path with entity IDs
- **After**: Enriched with:
  - Requirements for control entities
  - Evidence edges for requirement entities
  - Analytics and risk levels
  - Edge counts and relationships

```python
# Enhanced reasoning path:
{
    "hop": 1,
    "entity_type": "controls",
    "entities_found": ["HIPAA-AC-001"],
    "entities_enriched": [  # NEW
        {
            "control_id": "HIPAA-AC-001",
            "requirements_count": 3,
            "edges_count": 5,
            "has_analytics": true,
            "risk_level": "high"
        }
    ]
}
```

#### 3. New Method: get_comprehensive_entity_info()
- **Purpose**: Get all available information about any entity
- **Returns**:
  - Entity details (control/requirement/evidence)
  - Outgoing edges (relationships from entity)
  - Incoming edges (relationships to entity)
  - Related entities (requirements, evidence, etc.)
  - Measurements and analytics (for controls)

#### 4. Enhanced infer_context_properties()
- **Before**: LLM-only inference
- **After**: Uses comprehensive entity info from all stores before inference
- **Result**: More accurate, data-driven property inference

## Usage Examples

### Example 1: Get Enriched Controls

```python
result = await reasoning_pipeline.run(
    inputs={
        "query": "access control",
        "context_id": "ctx_001",
        "reasoning_type": "priority_controls",
        "include_requirements": True,
        "include_evidence": True,
        "include_measurements": True
    }
)

# Each control includes all available data
for control in result["data"]["controls"]:
    print(f"Control: {control['control']['control_name']}")
    print(f"  Requirements: {control['requirements']}")
    print(f"  Evidence: {control['evidence_types']}")
    print(f"  Measurements: {control['measurements']}")
    print(f"  Risk: {control['risk_analytics']}")
```

### Example 2: Get Comprehensive Entity Info

```python
entity_info = await reasoning_agent.get_comprehensive_entity_info(
    entity_id="HIPAA-AC-001",
    entity_type="control",
    context_id="ctx_001"
)

# Returns all information:
# - Control details
# - Requirements
# - Evidence types
# - Measurements
# - Analytics
# - Outgoing/incoming edges
```

### Example 3: Enriched Context Retrieval

```python
result = await retrieval_pipeline.run(
    inputs={
        "query": "healthcare compliance",
        "top_k": 5
    }
)

# Contexts now include:
for ctx in result["data"]["contexts"]:
    print(f"Context: {ctx['context_id']}")
    print(f"  Edges: {ctx['edges_count']}")
    print(f"  Controls: {ctx['controls_count']}")
    print(f"  Entity types: {ctx['entity_types']}")
```

## Benefits

1. **Complete Information**: No data is missed - all extracted information is available
2. **Richer Context**: Reasoning uses full knowledge base, not just vector search
3. **Better Decisions**: Analytics and measurements inform prioritization
4. **Comprehensive Analysis**: All relationships and entities are considered
5. **Data-Driven**: LLM reasoning is enhanced with actual data from stores

## Performance Considerations

- **Batch Operations**: Analytics fetched in batches where possible
- **Limits**: Results limited to prevent excessive queries (e.g., top 10 measurements)
- **Caching**: Vector storage results cached for repeated queries
- **Async**: All operations are async for better performance

## Backward Compatibility

All enhancements are **backward compatible**:
- Existing code continues to work
- New parameters are optional (default to True for enrichment)
- Legacy methods still available

## Future Enhancements

Potential future improvements:
1. Caching layer for frequently accessed entities
2. Graph traversal algorithms for complex queries
3. Temporal analysis using measurement history
4. Cross-context comparison capabilities
5. Automated relationship discovery


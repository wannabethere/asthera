# Contextual Graph Schema Migration

## Overview

This migration adds the full contextual graph schema as described in `docs/contextual_graph_reasoning_agent.md`. It extends the existing schema from `create_contextual_graph_schema.sql` with context-aware tables and relationships.

## Migration Files

1. **`create_contextual_graph_schema.sql`** - Base schema (run first)
   - Core entities: `controls`, `requirements`, `evidence_types`
   - Measurements: `compliance_measurements`, `control_risk_analytics`
   - Hard relationships: `control_requirement_mapping`

2. **`add_contextual_graph_tables.sql`** - Contextual graph extension (run second)
   - Unified entities: `entities` table
   - Context definitions: `contexts` table
   - Contextual properties: `entity_contextual_properties` table
   - Contextual relationships: `contextual_relationships` table
   - Context inheritance: `context_inheritance` table

## Installation Order

```bash
# 1. Run base schema first
psql -d your_database -f create_contextual_graph_schema.sql

# 2. Run contextual graph extension
psql -d your_database -f add_contextual_graph_tables.sql
```

## Schema Architecture

### Layer 1: Core Knowledge Graph (Base Schema)
- **Static entities**: Controls, Requirements, Evidence Types
- **Hard relationships**: Control-Requirement mappings
- **Measurements**: Time-series compliance data
- **Analytics**: Aggregated risk scores

### Layer 2: Context Layer (Extension Schema)
- **Context definitions**: Organizational, temporal, operational contexts
- **Contextual properties**: Properties that vary by context
- **Contextual relationships**: Context-aware relationships
- **Context inheritance**: Hierarchical context modeling

## Key Tables

### `entities` Table
Unified registry of all entities. Maps to existing tables:
- `controls` → `entity_type = 'control'`
- `requirements` → `entity_type = 'requirement'`
- `evidence_types` → `entity_type = 'evidence'`

**Use `sync_entities_from_tables()` function to populate from existing tables.**

### `contexts` Table
Stores context definitions with:
- **Context types**: organizational, temporal, operational, situational, risk, stakeholder
- **Hierarchy**: Parent-child relationships via `parent_context_id`
- **Temporal validity**: `valid_from` and `valid_until` timestamps
- **JSONB definition**: Flexible context metadata

### `entity_contextual_properties` Table
Stores context-dependent properties:
- Risk scores that vary by context
- Implementation complexity by context
- Priority levels by context
- Any property that changes based on context

### `contextual_relationships` Table
Context-aware relationships between entities:
- **Conditional logic**: `conditions` JSONB (when relationship holds)
- **Exceptions**: `exceptions` JSONB (when it doesn't apply)
- **Strength**: Relationship strength in this context (0-1)
- **Temporal validity**: When relationship is valid

### `context_inheritance` Table
Supports context hierarchy:
- Child contexts inherit from parent contexts
- Inheritance types: `full`, `partial`, `override`

## Usage Examples

### 1. Sync Entities from Existing Tables

```sql
-- Populate entities table from controls, requirements, evidence_types
SELECT sync_entities_from_tables();
```

### 2. Create a Context

```sql
INSERT INTO contexts (context_type, context_name, context_definition)
VALUES (
    'organizational',
    'Large Healthcare Organization',
    '{
        "industry": "healthcare",
        "employee_count": {"min": 1000, "max": 10000},
        "data_types": ["ePHI", "PII"],
        "regulatory_scope": ["HIPAA", "state_breach_laws"],
        "maturity_level": "developing"
    }'::jsonb
);
```

### 3. Add Contextual Property

```sql
INSERT INTO entity_contextual_properties 
    (entity_id, context_id, property_name, property_value, reasoning)
VALUES (
    'HIPAA-AC-001',
    1,  -- Context ID
    'risk_score',
    '{"likelihood": 3, "impact": 4, "score": 12}'::jsonb,
    'In healthcare context, access control failures have high impact'
);
```

### 4. Create Contextual Relationship

```sql
INSERT INTO contextual_relationships (
    source_entity_id,
    relationship_type,
    target_entity_id,
    context_id,
    strength,
    conditions,
    reasoning
)
VALUES (
    'HIPAA-AC-001',
    'REQUIRES',
    'REQ-001',
    1,  -- Healthcare context
    0.95,
    '{"organization_type": ["healthcare"], "data_sensitivity": ["high"]}'::jsonb,
    'HIPAA controls apply strongly in healthcare context'
);
```

### 5. Query Entity Properties in Context

```sql
-- Get all properties for an entity in a context (including inherited)
SELECT * FROM get_entity_properties_in_context('HIPAA-AC-001', 1);
```

### 6. Query Contextual Relationships

```sql
-- Get all relationships for a control in a context
SELECT * FROM get_contextual_relationships(
    p_source_entity_id => 'HIPAA-AC-001',
    p_context_id => 1
);
```

## Views

### `entity_contextual_view`
Shows entities with their contextual properties.

### `contextual_relationships_view`
Shows relationships with full entity and context details.

### `active_contexts`
Shows only currently valid contexts (within temporal bounds).

### `context_hierarchy`
Shows full context hierarchy tree with depth and path.

## Integration with Vector Store

The contextual graph tables work alongside the ChromaDB vector store:

- **PostgreSQL**: Structured data, relationships, analytics
- **ChromaDB**: Semantic search, document embeddings, hybrid search

The `context_id` in PostgreSQL references context definitions stored in ChromaDB's `context_definitions` collection.

## Migration Notes

1. **Backward Compatible**: This migration doesn't modify existing tables
2. **Optional**: Entities table can be populated via `sync_entities_from_tables()`
3. **Indexes**: All tables have appropriate indexes for performance
4. **Constraints**: Foreign keys and check constraints ensure data integrity
5. **Triggers**: Auto-update `updated_at` timestamps

## Next Steps

After running the migration:

1. **Populate entities**: Run `sync_entities_from_tables()`
2. **Create contexts**: Define organizational/situational contexts
3. **Add contextual properties**: Populate context-dependent properties
4. **Create contextual relationships**: Link entities with context-aware relationships
5. **Use in agents**: The agents will automatically use these tables for enriched reasoning

## Related Documentation

- `docs/contextual_graph_reasoning_agent.md` - Full architecture
- `docs/hybrid_search.md` - Hybrid search patterns
- `app/agents/pipelines/CONTEXTUAL_GRAPH_USAGE.md` - Usage examples



nohup uvicorn app.main:app --reload --host 0.0.0.0 --port 8040 --workers 4 > uvicorn.log 2>&1 & echo $! > run.pid
# MDL Semantic Layer Implementation Summary

## Problem Analysis

The current contextual graph edge discovery and pruning system has limitations for MDL semantic layer queries:

### Issues Identified

1. **Generic Context Breakdown**: The `ContextBreakdownService` focuses on compliance/product context but doesn't understand MDL schema semantics (tables, columns, relationships, categories).

2. **Generic Edge Discovery**: Edge discovery uses generic vector search without leveraging MDL metadata (categories, schema descriptions, table relationships).

3. **Generic Edge Pruning**: The `EdgePruningService` doesn't understand MDL-specific edge types (BELONGS_TO_TABLE, HAS_MANY_TABLES, etc.) and their semantic meanings.

4. **No MDL-Specific Prompts**: The `prompt_generator.py` has generic entity definitions but lacks MDL-specific semantic understanding.

5. **Missing Schema Category Awareness**: The system doesn't leverage schema_descriptions for category-aware queries.

## Solution Implementation

### 1. MDL Prompt Generator (`mdl_prompt_generator.py`)

**Purpose**: Generate MDL-specific system prompts for semantic layer queries.

**Key Features**:
- MDL-specific context breakdown rules
- MDL entity definitions (table_definitions, table_descriptions, schema_descriptions, etc.)
- MDL edge type semantics (BELONGS_TO_TABLE, HAS_MANY_TABLES, etc.)
- Schema category semantics
- MDL-specific examples

**Usage**:
```python
from app.utils.mdl_prompt_generator import get_mdl_context_breakdown_system_prompt

prompt = get_mdl_context_breakdown_system_prompt(include_examples=True)
```

### 2. MDL Context Breakdown Service (`mdl_context_breakdown_service.py`)

**Purpose**: Extend `ContextBreakdownService` with MDL-aware semantic understanding.

**Key Features**:
- Detects MDL query types (table, relationship, column, category, compliance)
- Generates MDL-specific search questions
- Understands schema categories and table relationships
- Constructs proper table entity IDs (entity_{product}_{table})
- Leverages schema_descriptions for category context

**Usage**:
```python
from app.services.mdl_context_breakdown_service import MDLContextBreakdownService

service = MDLContextBreakdownService()
breakdown = await service.breakdown_mdl_question(
    user_question="What tables are related to AccessRequest in Snyk?",
    product_name="Snyk"
)
```

### 3. MDL Edge Pruning Service (`mdl_edge_pruning_service.py`)

**Purpose**: Extend `EdgePruningService` with MDL-aware edge pruning.

**Key Features**:
- Understands MDL edge type semantics
- Prioritizes edges based on MDL query type
- Applies schema-aware scoring
- Considers table relationship hierarchy
- Boosts relevant edge types (BELONGS_TO_TABLE for relationship queries, HAS_FIELD for column queries)

**Usage**:
```python
from app.services.mdl_edge_pruning_service import MDLEdgePruningService

service = MDLEdgePruningService()
pruned_edges = await service.prune_edges(
    user_question="What tables are related to AccessRequest?",
    discovered_edges=edges,
    max_edges=10,
    context_breakdown=breakdown.__dict__
)
```

### 4. MDL Semantic Layer Service (`mdl_semantic_layer_service.py`)

**Purpose**: Integrate all MDL-aware components into a unified service.

**Key Features**:
- MDL-aware edge discovery
- Schema-aware edge pruning
- Schema category enrichment
- Entity retrieval from MDL edges
- Unified interface for MDL semantic queries

**Usage**:
```python
from app.services.mdl_semantic_layer_service import MDLSemanticLayerService

service = MDLSemanticLayerService(
    contextual_graph_storage=storage,
    collection_factory=factory
)

result = await service.discover_mdl_semantic_edges(
    user_question="What tables are related to AccessRequest in Snyk?",
    product_name="Snyk",
    top_k=10
)
```

## Integration Points

### With Existing System

1. **ContextualGraphStorage**: Uses `discover_edges_by_context()` with MDL-aware filters
2. **HybridSearchService**: Leverages hybrid search for schema-aware retrieval
3. **CollectionFactory**: Uses to access schema collections (schema_descriptions, table_descriptions, etc.)
4. **ContextBreakdownService**: Extends with MDL awareness (inheritance-based)

### With MDL Ingestion

The MDL semantic layer works with data ingested by:
- `ingest_mdl_contextual_graph.py`: Creates table entity contexts and relationship edges
- `index_mdl.py`: Indexes MDL schemas to vector stores

## Example Workflow

### Query: "What tables are related to AccessRequest in Snyk?"

1. **Context Breakdown** (`MDLContextBreakdownService`):
   - Detects: table query, relationship query
   - Identifies entities: `context_definitions`, `contextual_edges`, `schema_descriptions`
   - Generates search questions:
     - Schema categories for Snyk
     - AccessRequest table context
     - Relationship edges from AccessRequest

2. **Edge Discovery** (`MDLSemanticLayerService`):
   - Queries `schema_descriptions` for Snyk categories
   - Queries `context_definitions` for AccessRequest context
   - Queries `contextual_edges` with filters:
     - `source_entity_id = "entity_Snyk_AccessRequest"`
     - `edge_type IN [BELONGS_TO_TABLE, HAS_MANY_TABLES, ...]`

3. **Edge Pruning** (`MDLEdgePruningService`):
   - Identifies MDL edges (BELONGS_TO_TABLE, HAS_MANY_TABLES, etc.)
   - Applies MDL edge type priorities
   - Boosts relationship edges for relationship queries
   - Prunes to top 10 most relevant edges

4. **Entity Retrieval** (`MDLSemanticLayerService`):
   - Extracts entity IDs from pruned edges
   - Retrieves entity definitions from `context_definitions`
   - Returns related tables with relationship context

## Benefits

1. **Schema-Aware Understanding**: Understands MDL-specific semantics (categories, relationships, edge types)
2. **Better Edge Discovery**: Uses schema categories and table relationships for more accurate discovery
3. **Smarter Edge Pruning**: Prioritizes edges based on MDL query type and edge semantics
4. **Category Context**: Leverages schema_descriptions for category-aware queries
5. **Relationship Hierarchy**: Understands table relationship hierarchy (belongs_to, has_many, etc.)

## Testing Recommendations

1. **Unit Tests**: Test each service independently
2. **Integration Tests**: Test end-to-end MDL semantic queries
3. **Query Type Tests**: Test different MDL query types (table, relationship, column, category)
4. **Edge Type Tests**: Test different MDL edge types (BELONGS_TO_TABLE, HAS_MANY_TABLES, etc.)
5. **Product Tests**: Test with different products (Snyk, Cornerstone)

## Future Enhancements

1. **Schema Category Learning**: Learn schema categories from usage patterns
2. **Relationship Inference**: Infer table relationships from column names and types
3. **Multi-Product Support**: Better handling of cross-product queries
4. **Schema Evolution**: Track schema changes and update relationships
5. **Performance Optimization**: Cache schema category mappings and relationship graphs
6. **LLM-Based Relationship Discovery**: Use LLM to discover implicit relationships
7. **Schema Documentation Integration**: Integrate with schema documentation for richer context


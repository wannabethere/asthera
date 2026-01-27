# MDL Semantic Layer Architecture

## Overview

The MDL Semantic Layer provides intelligent understanding of Model Definition Language (MDL) schemas through a clean separation of concerns: **Agents** (LLM reasoning), **Retrievers** (data fetching), and **Services** (orchestration).

## Architecture

### Separation of Concerns

```
┌─────────────────────────────────────────────────────────────┐
│ AGENTS (LLM Reasoning)                                      │
│ - MDLContextBreakdownAgent: Breaks down questions using LLM │
│ - MDLEdgePruningAgent: Prunes edges using LLM              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ RETRIEVERS (Data Fetching)                                  │
│ - MDLSemanticRetriever: Fetches data from storage services  │
│   - Uses hybrid search for edges, contexts, schemas         │
│   - Does NOT use LLM - only data fetching                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ SERVICES (Orchestration)                                     │
│ - MDLSemanticLayerService: Orchestrates agents & retrievers │
│   - Coordinates workflow                                    │
│   - Does NOT use LLM directly - delegates to agents         │
│   - Does NOT fetch data directly - delegates to retrievers  │
└─────────────────────────────────────────────────────────────┘
```

### Components

#### 1. Agents (LLM-Based Reasoning)

**Location**: `app/agents/`

**MDLContextBreakdownAgent** (`mdl_context_breakdown_agent.py`)
- **Purpose**: Uses LLM to break down MDL queries into context components
- **Responsibilities**:
  - Analyzes user questions about MDL schemas
  - Detects MDL query types (table, relationship, column, category, compliance)
  - Generates MDL-specific search questions
  - Identifies relevant entities and metadata filters
- **Uses LLM**: Yes (ChatOpenAI)

**MDLEdgePruningAgent** (`mdl_edge_pruning_agent.py`)
- **Purpose**: Uses LLM to prune discovered edges with MDL-aware understanding
- **Responsibilities**:
  - Analyzes edge relevance to MDL queries
  - Understands MDL edge type semantics
  - Prioritizes edges based on MDL query type
  - Selects top N most relevant edges
- **Uses LLM**: Yes (ChatOpenAI)

#### 2. Retrievers (Data Fetching)

**Location**: `app/agents/data/`

**MDLSemanticRetriever** (`mdl_semantic_retriever.py`)
- **Purpose**: Fetches MDL data from storage services
- **Responsibilities**:
  - Retrieves edges using hybrid search
  - Retrieves context definitions
  - Retrieves schema descriptions
  - Retrieves table descriptions
  - Retrieves fields
- **Uses LLM**: No (only data fetching)
- **Uses Storage Services**: Yes (ContextualGraphStorage, CollectionFactory, HybridSearchService)

#### 3. Services (Orchestration)

**Location**: `app/services/`

**MDLSemanticLayerService** (`mdl_semantic_layer_service.py`)
- **Purpose**: Orchestrates MDL agents and retrievers
- **Responsibilities**:
  - Coordinates workflow between agents and retrievers
  - Manages the discovery and pruning pipeline
  - Enriches results with schema categories
  - Provides unified interface for MDL semantic queries
- **Uses LLM**: No (delegates to agents)
- **Fetches Data**: No (delegates to retrievers)

## MDL Edge Types

| Edge Type | Description | Priority | Use Case |
|-----------|-------------|----------|----------|
| BELONGS_TO_TABLE | Table belongs to another (many-to-one) | High | AccessRequest belongs to Project |
| HAS_MANY_TABLES | Table has many related tables (one-to-many) | High | Project has many AccessRequests |
| REFERENCES_TABLE | Table references another (one-to-one) | Medium | User references Profile |
| MANY_TO_MANY_TABLE | Many-to-many relationship | Medium | Users <-> Groups |
| LINKED_TO_TABLE | Tables are linked (general) | Low | Related tables |
| RELATED_TO_TABLE | Tables are related (generic) | Low | Fallback relationship |
| RELEVANT_TO_CONTROL | Table relevant to compliance control | High | AccessRequest relevant to SOC2 CC6.1 |
| HAS_FIELD | Table has field/column | Medium | AccessRequest has field 'requested_at' |

## Usage Example

```python
from app.services.mdl_semantic_layer_service import MDLSemanticLayerService
from app.services.contextual_graph_storage import ContextualGraphStorage
from app.storage.query.collection_factory import CollectionFactory

# Initialize services
contextual_graph_storage = ContextualGraphStorage(...)
collection_factory = CollectionFactory(...)

# Create MDL semantic layer service
mdl_service = MDLSemanticLayerService(
    contextual_graph_storage=contextual_graph_storage,
    collection_factory=collection_factory
)

# Discover MDL semantic edges
# This internally:
# 1. Uses MDLContextBreakdownAgent (LLM) to break down question
# 2. Uses MDLSemanticRetriever (data fetching) to discover edges
# 3. Uses MDLEdgePruningAgent (LLM) to prune edges
# 4. Uses MDLSemanticRetriever (data fetching) to enrich with categories
result = await mdl_service.discover_mdl_semantic_edges(
    user_question="What tables are related to AccessRequest in Snyk?",
    product_name="Snyk",
    top_k=10
)

# Get pruned edges
edges = result["edges"]
context_breakdown = result["context_breakdown"]

# Get entities from edges
entities_result = await mdl_service.get_entities_from_mdl_edges(
    edges=edges,
    user_question="What tables are related to AccessRequest in Snyk?",
    top_k=10
)
```

## Workflow

### Query: "What tables are related to AccessRequest in Snyk?"

1. **Agent (LLM)**: `MDLContextBreakdownAgent.breakdown_mdl_question()`
   - Detects: table query, relationship query
   - Identifies entities: `context_definitions`, `contextual_edges`, `schema_descriptions`
   - Generates search questions with metadata filters

2. **Retriever (Data Fetching)**: `MDLSemanticRetriever.retrieve_edges()`
   - Queries `contextual_edges` collection using hybrid search
   - Filters: `source_entity_id = "entity_Snyk_AccessRequest"`, `edge_type IN [BELONGS_TO_TABLE, ...]`
   - Returns discovered edges

3. **Agent (LLM)**: `MDLEdgePruningAgent.prune_edges()`
   - Analyzes edge relevance using LLM
   - Understands MDL edge type semantics
   - Prioritizes relationship edges
   - Returns top 10 most relevant edges

4. **Retriever (Data Fetching)**: `MDLSemanticRetriever.retrieve_schema_descriptions()`
   - Enriches edges with schema category context
   - Returns final pruned edges with metadata

## Integration with Existing System

The MDL Semantic Layer integrates with:
- **ContextualGraphStorage**: For edge discovery via `discover_edges_by_context()`
- **CollectionFactory**: For accessing schema collections (schema_descriptions, table_descriptions, etc.)
- **HybridSearchService**: For hybrid search capabilities (used by retrievers)

## Benefits

1. **Clean Architecture**: Clear separation between LLM reasoning (agents), data fetching (retrievers), and orchestration (services)
2. **Schema-Aware Understanding**: Understands MDL-specific semantics (categories, relationships, edge types)
3. **Better Edge Discovery**: Uses schema categories and table relationships for more accurate discovery
4. **Smarter Edge Pruning**: Prioritizes edges based on MDL query type and edge semantics
5. **Category Context**: Leverages schema_descriptions for category-aware queries
6. **Relationship Hierarchy**: Understands table relationship hierarchy (belongs_to, has_many, etc.)

## Future Enhancements

1. **Schema Category Learning**: Learn schema categories from usage patterns
2. **Relationship Inference**: Infer table relationships from column names and types
3. **Multi-Product Support**: Better handling of cross-product queries
4. **Schema Evolution**: Track schema changes and update relationships
5. **Performance Optimization**: Cache schema category mappings and relationship graphs

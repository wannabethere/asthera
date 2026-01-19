# Multi-Store Contextual Reasoning

## Overview

The contextual reasoning system has been enhanced to support queries across multiple knowledge stores organized in a hierarchical structure. This enables comprehensive reasoning that connects connectors, domains, compliance controls, risks, and schemas.

## Architecture

### Knowledge Hierarchy

The system organizes knowledge in the following hierarchy:

```
Connector → Domain → Compliance → Risks → Additionals
     ↓         ↓          ↓         ↓
     └─────────┴──────────┴─────────┘
                    ↓
                Schemas (separate)
```

### Collections by Category

#### 1. Connector Collections
- `extendable_entities` - APIs, integrations, data sources
- `product_purpose` - Product descriptions
- `product_docs` - Documentation links
- `product_key_concepts` - Key concepts and terminology

#### 2. Domain Collections
- `domain_knowledge` - Business and data domain knowledge
- `policy_context` - Organizational context

#### 3. Compliance Collections
- `compliance_controls` - Compliance control definitions
- `policy_requirements` - Policy requirements
- `policy_entities` - Extracted policy entities

#### 4. Risk Collections
- `risk_controls` - Risk control documents

#### 5. Additional Collections
- `policy_documents` - Full policy documents
- `policy_evidence` - Evidence requirements
- `policy_fields` - Extracted fields

#### 6. Schema Collections (Separate)
- `table_definitions` - Table structure definitions
- `table_descriptions` - Table descriptions
- `column_definitions` - Column definitions
- `schema_descriptions` - Schema descriptions

## Components

### 1. CollectionFactory

The `CollectionFactory` provides unified access to all collections.

**Location:** `app/storage/query/collection_factory.py`

**Features:**
- Initializes all collection services
- Provides search methods for each category
- Supports hierarchical queries
- Handles schema queries separately

**Usage:**
```python
from app.storage.query import CollectionFactory
import chromadb

chroma_client = chromadb.PersistentClient(path="./chroma_db")
factory = CollectionFactory(
    chroma_client=chroma_client,
    collection_prefix="comprehensive_index"
)

# Search all stores
results = factory.search_all(query="access control", top_k=10)

# Search specific category
connectors = factory.search_connectors(query="Snyk API", top_k=5)
domains = factory.search_domains(query="security domain", top_k=5)
compliance = factory.search_compliance(query="SOC2 controls", top_k=10)
risks = factory.search_risks(query="data breach risk", top_k=5)
schemas = factory.search_schemas(query="user table", top_k=5)
```

### 2. Enhanced Query Engine

The `ContextualGraphQueryEngine` now includes multi-store query capabilities.

**New Methods:**
- `query_all_stores()` - Query across all stores
- `query_hierarchical()` - Query following the hierarchy

**Usage:**
```python
from app.storage.query import ContextualGraphQueryEngine

query_engine = ContextualGraphQueryEngine(
    chroma_client=chroma_client,
    db_pool=db_pool,
    collection_prefix="comprehensive_index"
)

# Query all stores
results = await query_engine.query_all_stores(
    query="What controls are needed for access management?",
    context_id="ctx_123",
    top_k=10
)

# Query following hierarchy
hierarchical_results = await query_engine.query_hierarchical(
    query="access control",
    context_id="ctx_123",
    start_level="connector",
    top_k=5
)
```

### 3. Enhanced Contextual Graph Storage

The `ContextualGraphStorage` now includes methods to build knowledge graphs connecting entities.

**New Methods:**
- `build_hierarchical_edges()` - Build edges following the hierarchy
- `build_schema_connections()` - Connect entities to schemas
- `build_knowledge_graph_from_stores()` - Build complete knowledge graph from all stores

**Usage:**
```python
from app.services.contextual_graph_storage import ContextualGraphStorage
from app.storage.query import CollectionFactory

storage = ContextualGraphStorage(chroma_client=chroma_client)
factory = CollectionFactory(chroma_client=chroma_client)

# Build knowledge graph
kg_stats = storage.build_knowledge_graph_from_stores(
    context_id="ctx_123",
    collection_factory=factory,
    query="access control",
    top_k=10
)
```

### 4. Enhanced Reasoning Agent

The `ContextualGraphReasoningAgent` now uses the collection factory to enrich reasoning with data from all stores.

**Enhancements:**
- Enriches reasoning paths with multi-store data
- Enriches controls with related entities from all stores
- Connects entities across the hierarchy

**Usage:**
```python
from app.agents.contextual_graph_reasoning_agent import ContextualGraphReasoningAgent
from app.storage.query import CollectionFactory

factory = CollectionFactory(chroma_client=chroma_client)
reasoning_agent = ContextualGraphReasoningAgent(
    contextual_graph_service=service,
    collection_factory=factory
)

# Reason with context (now enriched with all stores)
result = await reasoning_agent.reason_with_context(
    query="What evidence do I need for access controls?",
    context_id="ctx_123",
    max_hops=3
)
```

### 5. Enhanced Retrieval Agent

The `ContextualGraphRetrievalAgent` now uses the collection factory to enrich context retrieval.

**Enhancements:**
- Enriches contexts with store statistics
- Includes multi-store context in reasoning plans
- Traverses hierarchy in planning

**Usage:**
```python
from app.agents.contextual_graph_retrieval_agent import ContextualGraphRetrievalAgent
from app.storage.query import CollectionFactory

factory = CollectionFactory(chroma_client=chroma_client)
retrieval_agent = ContextualGraphRetrievalAgent(
    contextual_graph_service=service,
    collection_factory=factory
)

# Retrieve contexts (now enriched with store data)
contexts = await retrieval_agent.retrieve_contexts(
    query="SOC2 compliance for healthcare",
    top_k=5
)

# Create reasoning plan (now includes store traversal)
plan = await retrieval_agent.create_reasoning_plan(
    user_action="Assess access control compliance",
    retrieved_contexts=contexts
)
```

## Knowledge Graph Building

The system can automatically build knowledge graphs connecting entities across stores:

### Hierarchical Connections

1. **Connector → Domain**: Connectors provide data for domains
2. **Domain → Compliance**: Domains are governed by compliance controls
3. **Compliance → Risks**: Compliance controls address risks
4. **Compliance → Additionals**: Compliance controls require additional resources

### Schema Connections

Schemas are connected separately:
- **Connector → Schema**: Connectors provide schemas
- **Domain → Schema**: Domains use schemas
- **Compliance → Schema**: Compliance monitors via schemas

### Example

```python
# Build hierarchical edges
edges = storage.build_hierarchical_edges(
    context_id="ctx_123",
    connector_ids=["conn_snyk", "conn_okta"],
    domain_ids=["domain_security", "domain_access"],
    compliance_ids=["ctrl_cc6_1", "ctrl_cc6_2"],
    risk_ids=["risk_unauthorized_access"],
    additional_ids=["policy_access", "evidence_logs"]
)

# Build schema connections
schema_edges = storage.build_schema_connections(
    context_id="ctx_123",
    entity_id="ctrl_cc6_1",
    entity_type="compliance",
    schema_ids=["table_users", "table_access_logs"],
    connection_type="MONITORS_VIA_SCHEMA"
)
```

## Benefits

1. **Comprehensive Reasoning**: Access to all knowledge stores in a single query
2. **Hierarchical Navigation**: Follow the natural hierarchy of knowledge
3. **Schema Integration**: Connect compliance and risk to actual data structures
4. **Context-Aware**: All queries respect organizational context
5. **Scalable**: Easy to add new collections and entity types

## Migration Guide

### Existing Code

If you have existing code using the contextual reasoning agents, you can enhance it by adding the collection factory:

```python
# Before
reasoning_agent = ContextualGraphReasoningAgent(
    contextual_graph_service=service
)

# After
from app.storage.query import CollectionFactory

factory = CollectionFactory(
    chroma_client=chroma_client,
    collection_prefix="comprehensive_index"
)

reasoning_agent = ContextualGraphReasoningAgent(
    contextual_graph_service=service,
    collection_factory=factory  # Add this
)
```

### New Code

For new code, use the enhanced query engine:

```python
from app.storage.query import ContextualGraphQueryEngine, CollectionFactory

query_engine = ContextualGraphQueryEngine(
    chroma_client=chroma_client,
    db_pool=db_pool,
    collection_prefix="comprehensive_index"
)

# Query all stores
results = await query_engine.query_all_stores(
    query="your query",
    context_id="your_context_id"
)
```

## Future Enhancements

1. **Automatic Graph Building**: Automatically build knowledge graphs when indexing
2. **Graph Traversal**: Advanced traversal algorithms for complex queries
3. **Store-Specific Reasoning**: Specialized reasoning for each store type
4. **Cross-Store Analytics**: Analytics across multiple stores
5. **Dynamic Hierarchy**: Allow custom hierarchies per context


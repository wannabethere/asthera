# Contextual Graph Edge Discovery and Pruning System

## Overview

This document describes the enhanced contextual graph system that uses LLM-based context breakdown and edge discovery to build better knowledge graphs from user questions. The system follows this workflow:

1. **User Question** → Context-based breakdown using LLM
2. **Context Breakdown** → Edge discovery using vector similarity search
3. **Discovered Edges** → Edge pruning using LLM to select best edges
4. **Pruned Edges** → Entity retrieval with specific questions
5. **Processing Results** → Store new edges back to vector store and postgres

## Architecture

### Components

#### 1. Context Breakdown Service (`context_breakdown_service.py`)

Breaks down user questions into context components:
- **Compliance Context**: Which frameworks are mentioned (SOC2, HIPAA, ISO 27001, etc.)
- **Action Context**: What action is the user trying to perform
- **Product Context**: Which products are mentioned (Snyk, Okta, etc.)
- **User Intent**: What the user is trying to accomplish
- **Query Keywords**: Key terms for vector search

**Key Methods:**
- `breakdown_question()`: Analyzes user question and extracts context components
- `get_default_prompt()`: Returns default breakdown when no specific context available

#### 2. Edge Pruning Service (`edge_pruning_service.py`)

Uses LLM to select the best edges from discovered edges:
- Analyzes edge relevance to user question
- Considers edge types and entity types
- Evaluates edge document content
- Uses context breakdown information
- Returns top N most relevant edges

**Key Methods:**
- `prune_edges()`: Selects best edges from discovered edges
- `rank_edges_by_relevance()`: Ranks edges without pruning

#### 3. Enhanced Contextual Graph Storage (`contextual_graph_storage.py`)

Added methods for edge discovery and postgres storage:
- `discover_edges_by_context()`: Uses vector similarity search to find relevant edges
- `save_edge_to_postgres()`: Saves edge to PostgreSQL `contextual_relationships` table
- `save_edges_to_postgres()`: Batch saves edges to postgres

#### 4. Enhanced Retrieval Agent (`contextual_graph_retrieval_agent.py`)

Main workflow orchestration:
- `discover_and_prune_edges()`: Complete workflow from question to pruned edges
- `get_entities_from_edges()`: Retrieves entities using pruned edges with specific questions

#### 5. Enhanced Reasoning Agent (`contextual_graph_reasoning_agent.py`)

Stores new edges discovered during processing:
- `store_new_edges_from_processing()`: Creates and stores edges from processing results

## Workflow

### Step 1: Context Breakdown

```python
# User question
user_question = "What are the SOC2 controls for access management?"

# Break down into context components
context_breakdown = await context_breakdown_service.breakdown_question(user_question)

# Result:
# - compliance_context: "SOC2"
# - action_context: "find controls"
# - user_intent: "understand access control requirements"
# - frameworks: ["SOC2"]
# - query_keywords: ["SOC2", "controls", "access", "management"]
```

### Step 2: Edge Discovery

```python
# Use context breakdown to search for edges
search_query = context_breakdown.to_search_query()  # "SOC2 find controls understand access control requirements..."
metadata_filters = context_breakdown.to_metadata_filters()  # {"framework": "SOC2"}

# Discover edges using vector similarity search
discovered_edges = await storage.discover_edges_by_context(
    context_query=search_query,
    top_k=30,  # Discover more than needed
    filters=metadata_filters
)
```

### Step 3: Edge Pruning

```python
# Use LLM to select best edges
pruned_edges = await edge_pruning_service.prune_edges(
    user_question=user_question,
    discovered_edges=discovered_edges,
    max_edges=10,  # Return top 10
    context_breakdown=context_breakdown.__dict__
)
```

### Step 4: Entity Retrieval

```python
# Get entities from pruned edges
entities_result = await retrieval_agent.get_entities_from_edges(
    edges=pruned_edges,
    user_question=user_question,
    top_k=10
)
```

### Step 5: Store New Edges

```python
# After processing, store new edges discovered
storage_result = await reasoning_agent.store_new_edges_from_processing(
    user_question=user_question,
    context_id=context_id,
    entities_found=entities_result["entities"],
    save_to_postgres=True
)
```

## Usage Example

```python
from app.agents.contextual_graph_retrieval_agent import ContextualGraphRetrievalAgent
from app.agents.contextual_graph_reasoning_agent import ContextualGraphReasoningAgent

# Initialize agents
retrieval_agent = ContextualGraphRetrievalAgent(
    contextual_graph_service=contextual_graph_service,
    collection_factory=collection_factory
)

reasoning_agent = ContextualGraphReasoningAgent(
    contextual_graph_service=contextual_graph_service,
    collection_factory=collection_factory
)

# Step 1: Discover and prune edges
edge_result = await retrieval_agent.discover_and_prune_edges(
    user_question="What are the SOC2 controls for access management?",
    top_k=10
)

# Step 2: Get entities from edges
entities_result = await retrieval_agent.get_entities_from_edges(
    edges=edge_result["edges"],
    user_question="What are the SOC2 controls for access management?",
    top_k=10
)

# Step 3: Process entities (your reasoning logic here)
# ...

# Step 4: Store new edges
storage_result = await reasoning_agent.store_new_edges_from_processing(
    user_question="What are the SOC2 controls for access management?",
    context_id="context_123",
    entities_found=entities_result["entities"],
    save_to_postgres=True
)
```

## Fallback Behavior

If no context is available or edge discovery fails:

1. **Default Prompt**: Uses `get_default_prompt()` to create a minimal context breakdown
2. **Keyword Search**: Falls back to keyword-based search using first 10 words
3. **Score-based Selection**: If LLM pruning fails, uses relevance score sorting

## Database Storage

### Vector Store

Edges are stored in the `contextual_edges` collection with:
- Edge document (rich text description)
- Metadata (edge_type, source/target entity info, context_id, etc.)
- Embeddings for similarity search

### PostgreSQL

Edges are stored in the `contextual_relationships` table with:
- `source_entity_id`: Source entity identifier
- `relationship_type`: Edge type (e.g., "HAS_REQUIREMENT_IN_CONTEXT")
- `target_entity_id`: Target entity identifier
- `context_id`: Context identifier (references `contexts` table)
- `strength`: Relationship strength (0.0-1.0)
- `confidence`: Confidence score (0.0-1.0)
- `reasoning`: Text explanation of the relationship

## Benefits

1. **Context-Aware**: Uses LLM to understand user intent and context
2. **Efficient**: Prunes edges to only most relevant ones
3. **Learnable**: Stores new edges discovered during processing
4. **Fallback-Safe**: Has default behavior when context unavailable
5. **Dual Storage**: Stores in both vector store (for search) and postgres (for structured queries)

## Future Enhancements

1. **Edge Confidence Scoring**: Use LLM to score edge confidence
2. **Multi-hop Edge Discovery**: Discover edges through multiple hops
3. **Edge Validation**: Validate discovered edges before storage
4. **Context Caching**: Cache context breakdowns for similar questions
5. **Edge Analytics**: Track which edges are most useful for different question types


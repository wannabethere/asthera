# MDL Reasoning and Planning Graph - Implementation Summary

## What Was Built

A complete MDL reasoning and planning system with proper separation of concerns:

### Architecture

```
AGENTS (LLM Reasoning)
├── MDLContextBreakdownAgent - Breaks down MDL questions
└── MDLEdgePruningAgent - Prunes edges with MDL awareness

RETRIEVERS (Data Fetching)
└── MDLSemanticRetriever - Fetches data from storage services

SERVICES (Orchestration)
└── MDLSemanticLayerService - Orchestrates agents and retrievers

GRAPH (Workflow)
└── MDLReasoningGraph - LangGraph workflow for end-to-end reasoning
```

## Files Created

### 1. Agents (LLM-Based)

**`app/agents/mdl_context_breakdown_agent.py`**
- Agent that uses LLM to break down MDL queries
- Detects MDL query types (table, relationship, column, category, compliance)
- Generates MDL-specific search questions

**`app/agents/mdl_edge_pruning_agent.py`**
- Agent that uses LLM to prune edges with MDL awareness
- Understands MDL edge type semantics
- Prioritizes edges based on query type

### 2. Retrievers (Data Fetching)

**`app/agents/data/mdl_semantic_retriever.py`**
- Retriever that fetches MDL data from storage
- Methods: retrieve_edges, retrieve_context_definitions, retrieve_schema_descriptions, etc.
- Uses hybrid search, no LLM

### 3. Services (Orchestration)

**`app/services/mdl_semantic_layer_service.py`**
- Service that orchestrates agents and retrievers
- Main method: `discover_mdl_semantic_edges()`
- Coordinates workflow without using LLM or fetching data directly

### 4. Graph Components

**`app/agents/mdl_reasoning_state.py`**
- State class for MDL reasoning graph
- Defines state structure with reducers

**`app/agents/mdl_reasoning_nodes.py`**
- Graph nodes: ContextBreakdown, EntityIdentification, ContextRetrieval, Planning
- Each node performs a specific step in the workflow

**`app/agents/mdl_reasoning_nodes.py`** (includes graph builder)
- Node classes for each step in the workflow
- Graph builder (`MDLReasoningGraphBuilder`) that creates and compiles LangGraph workflow
- Factory function: `create_mdl_reasoning_graph()`

### 5. Utilities

**`app/utils/mdl_prompt_generator.py`**
- MDL-specific prompt generation
- MDL edge type semantics
- Schema category semantics

### 6. Tests and Documentation

**`tests/test_mdl_reasoning_graph.py`**
- Integration test for MDL reasoning graph

**`app/indexing/cli/test_mdl_reasoning_graph.py`**
- CLI script for testing the graph

**`docs/MDL_REASONING_GRAPH.md`**
- Complete documentation

**`docs/MDL_REASONING_GRAPH_SETUP.md`**
- Data setup guide

## Graph Workflow

```
User Question
    ↓
[Context Breakdown Node]
  - Agent: MDLContextBreakdownAgent (LLM)
  - Output: identified_entities, search_questions
    ↓
[Entity Identification Node]
  - Retriever: MDLSemanticRetriever (Data Fetching)
  - Output: tables_found, entities_found
    ↓
[Context Retrieval Node]
  - Service: MDLSemanticLayerService (Orchestration)
  - Output: contexts_retrieved, edges_discovered
    ↓
[Planning Node]
  - Agent: LLM-based planning
  - Output: reasoning_plan, natural_language_questions
    ↓
Final Result
```

## Data Setup Process

### 1. Index MDL Files

```bash
# Preview mode
python -m indexing_cli.index_mdl \
    --mdl-file path/to/snyk_mdl1.json \
    --product-name Snyk \
    --preview

# Index to database
python -m indexing_cli.index_mdl \
    --mdl-file path/to/snyk_mdl1.json \
    --product-name Snyk
```

Creates: `table_definitions`, `table_descriptions`, `schema_descriptions`, `column_definitions`

### 2. Ingest to Contextual Graph

```bash
python -m indexing_cli.ingest_mdl_contextual_graph \
    --mdl-file path/to/snyk_mdl1.json \
    --product-name Snyk
```

Creates: `context_definitions`, `contextual_edges`, `fields`

### 3. Test the Graph

```bash
python -m tests.test_mdl_reasoning_graph \
    --question "What tables are related to AccessRequest in Snyk?" \
    --product-name Snyk
```

## Key Features

1. **Clean Architecture**: Proper separation of agents, retrievers, and services
2. **MDL-Aware**: Understands MDL-specific semantics (categories, relationships, edge types)
3. **Graph-Based**: Uses LangGraph for workflow orchestration
4. **Step-by-Step**: Each step is clearly defined and testable
5. **Natural Language Questions**: Generates questions for each component

## Output Structure

The graph returns:
- **Tables Found**: List of identified tables with metadata
- **Entities Found**: List of identified entities
- **Contexts Retrieved**: Context definitions for tables
- **Edges Discovered**: Relationship edges between entities
- **Reasoning Plan**: Plan for product, controls, risks, metrics
- **Natural Language Questions**: Questions for each component

## Testing

### Quick Test

```bash
python -m tests.test_mdl_reasoning_graph \
    --question "What tables are related to AccessRequest in Snyk?" \
    --product-name Snyk
```

### Integration Test

```bash
cd knowledge
python tests/test_mdl_reasoning_graph.py
```

## Next Steps

1. **Extend Planning**: Add detailed plans for each component (product, controls, risks, metrics)
2. **Add Execution**: Execute the plan to retrieve actual data
3. **Add Metrics Generation**: Generate metrics from identified tables
4. **Add Compliance Integration**: Integrate with compliance controls retrieval
5. **Add Risk Assessment**: Assess risks for identified entities

## Benefits

1. **Modular**: Each component has a single responsibility
2. **Testable**: Each step can be tested independently
3. **Extensible**: Easy to add new nodes or modify workflow
4. **MDL-Aware**: Understands MDL-specific semantics
5. **Graph-Based**: Uses LangGraph for workflow management


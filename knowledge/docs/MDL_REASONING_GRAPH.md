# MDL Reasoning and Planning Graph

## Overview

The MDL Reasoning and Planning Graph is a LangGraph-based workflow that:
1. **Breaks down** user questions about MDL schemas
2. **Identifies** tables and entities
3. **Retrieves** contexts and edges from the contextual graph
4. **Plans** reasoning for product, controls, risks, and metrics

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ MDL Reasoning Graph (LangGraph Workflow)                    │
│                                                             │
│  User Question                                              │
│      ↓                                                      │
│  [Context Breakdown Node]                                   │
│  - Uses MDLContextBreakdownAgent (LLM)                      │
│  - Breaks down question into entities and search questions │
│      ↓                                                      │
│  [Entity Identification Node]                                │
│  - Uses MDLSemanticRetriever (Data Fetching)               │
│  - Identifies tables and entities                          │
│      ↓                                                      │
│  [Context Retrieval Node]                                   │
│  - Uses MDLSemanticLayerService                            │
│  - Retrieves contexts and edges                            │
│      ↓                                                      │
│  [Planning Node]                                            │
│  - Uses LLM for planning                                    │
│  - Creates plan for product, controls, risks, metrics       │
│      ↓                                                      │
│  Final Result                                               │
│  - Entities found                                           │
│  - Natural language questions                               │
│  - Reasoning plan                                           │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. State (`mdl_reasoning_state.py`)

Defines the state structure for the graph workflow:
- User input (question, product_name)
- Context breakdown results
- Entity identification results
- Context retrieval results
- Planning results
- Natural language questions

### 2. Nodes (`mdl_reasoning_nodes.py`)

**MDLContextBreakdownNode**
- Uses `MDLContextBreakdownAgent` (LLM) to break down questions
- Outputs: identified_entities, search_questions

**MDLEntityIdentificationNode**
- Uses `MDLSemanticRetriever` (data fetching) to identify tables/entities
- Outputs: tables_found, entities_found, entity_questions

**MDLContextRetrievalNode**
- Uses `MDLSemanticLayerService` to retrieve contexts and edges
- Outputs: contexts_retrieved, edges_discovered, related_entities

**MDLPlanningNode**
- Uses LLM to create reasoning plan
- Outputs: reasoning_plan, plan_components, natural_language_questions

### 3. Graph Builder (in `mdl_reasoning_nodes.py`)

Builds and compiles the LangGraph workflow. The `MDLReasoningGraphBuilder` class and `create_mdl_reasoning_graph()` factory function are included in the same module as the nodes.

## Data Setup

### Step 1: Index MDL Schema Files

```bash
# Preview mode (saves to files)
python -m indexing_cli.index_mdl \
    --mdl-file path/to/snyk_mdl1.json \
    --product-name Snyk \
    --preview

# Review preview files, then index to database
python -m indexing_cli.index_mdl \
    --mdl-file path/to/snyk_mdl1.json \
    --product-name Snyk
```

### Step 2: Ingest MDL to Contextual Graph

```bash
# Ingest MDL to contextual graph
python -m indexing_cli.ingest_mdl_contextual_graph \
    --mdl-file path/to/snyk_mdl1.json \
    --product-name Snyk
```

This creates:
- `context_definitions` - Table entity contexts
- `contextual_edges` - Table relationships, compliance relationships
- `fields` - Table columns/fields

### Step 3: Index Preview Files (Alternative)

If you have preview files in `indexing_preview/`:

```bash
# Ingest preview files
python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --content-types table_definitions table_descriptions schema_descriptions
```

## Usage

### Using the Graph Directly

```python
from app.agents.mdl_reasoning_nodes import create_mdl_reasoning_graph
from app.services.contextual_graph_storage import ContextualGraphStorage
from app.storage.query.collection_factory import CollectionFactory

# Initialize services
contextual_graph_storage = ContextualGraphStorage(...)
collection_factory = CollectionFactory(...)

# Create graph
graph = create_mdl_reasoning_graph(
    contextual_graph_storage=contextual_graph_storage,
    collection_factory=collection_factory,
    llm=llm
)

# Run graph
initial_state = {
    "user_question": "What tables are related to AccessRequest in Snyk?",
    "product_name": "Snyk",
    "identified_entities": [],
    "search_questions": [],
    "tables_found": [],
    "entities_found": [],
    "entity_questions": [],
    "contexts_retrieved": [],
    "edges_discovered": [],
    "related_entities": [],
    "natural_language_questions": [],
    "current_step": "start",
    "status": "processing",
    "messages": []
}

result = await graph.ainvoke(initial_state)

# Access results
print(f"Tables: {result['tables_found']}")
print(f"Entities: {result['entities_found']}")
print(f"Plan: {result['reasoning_plan']}")
print(f"Questions: {result['natural_language_questions']}")
```

### Using the CLI Test Script

```bash
# Test with a question
python -m tests.test_mdl_reasoning_graph \
    --question "What tables are related to AccessRequest in Snyk?" \
    --product-name Snyk
```

### Using the Test Script

```bash
# Run integration test
cd knowledge
python tests/test_mdl_reasoning_graph.py
```

## Output Structure

The graph returns a state dictionary with:

```python
{
    "user_question": "What tables are related to AccessRequest in Snyk?",
    "product_name": "Snyk",
    
    # Context Breakdown
    "context_breakdown": {
        "identified_entities": ["context_definitions", "contextual_edges", ...],
        "search_questions": [...]
    },
    "identified_entities": [...],
    "search_questions": [...],
    
    # Entity Identification
    "tables_found": [
        {
            "table_name": "AccessRequest",
            "context_id": "entity_Snyk_AccessRequest",
            "entity_type": "table",
            "metadata": {...}
        }
    ],
    "entities_found": [...],
    "entity_questions": [...],
    
    # Context Retrieval
    "contexts_retrieved": [...],
    "edges_discovered": [
        {
            "edge_id": "...",
            "edge_type": "BELONGS_TO_TABLE",
            "source_entity_id": "entity_Snyk_AccessRequest",
            "target_entity_id": "entity_Snyk_Project",
            ...
        }
    ],
    "related_entities": [...],
    
    # Planning
    "reasoning_plan": {
        "overall_plan": "...",
        "steps": [...]
    },
    "plan_components": {
        "product_plan": {...},
        "mdl_entities_plan": {...},
        "compliance_controls_plan": {...},
        "risks_plan": {...},
        "metrics_plan": {...}
    },
    "natural_language_questions": [
        "What is the structure of AccessRequest table?",
        "What compliance controls are relevant to AccessRequest?",
        ...
    ],
    
    # Final Result
    "final_result": {
        "tables_found": [...],
        "entities_found": [...],
        "reasoning_plan": {...},
        "natural_language_questions": [...]
    },
    
    "status": "completed",
    "current_step": "planning"
}
```

## Example Queries

### Query 1: Table Relationships

**Question**: "What tables are related to AccessRequest in Snyk?"

**Expected Output**:
- Tables: AccessRequest, Project, User, Group
- Edges: BELONGS_TO_TABLE, HAS_MANY_TABLES
- Plan: Focus on table relationships

### Query 2: Compliance Controls

**Question**: "What compliance controls are relevant to the AccessRequest table?"

**Expected Output**:
- Tables: AccessRequest
- Edges: RELEVANT_TO_CONTROL
- Plan: Focus on compliance controls

### Query 3: Schema Categories

**Question**: "What tables are in the 'access requests' category for Snyk?"

**Expected Output**:
- Entities: Schema category "access requests"
- Tables: AccessRequest, AccessRequestHistory, etc.
- Plan: Focus on schema categories

## Testing

### Run Test Script

```bash
# Set environment variables
export OPENAI_API_KEY="your-openai-api-key"

# Run test
python -m tests.test_mdl_reasoning_graph \
    --question "What tables are related to AccessRequest in Snyk?" \
    --product-name Snyk
```

### Run Integration Test

```bash
cd knowledge
python tests/test_mdl_reasoning_graph.py
```

## Troubleshooting

### No Tables Found

1. Verify MDL files are indexed
2. Check `indexing_preview/table_definitions/` for preview files
3. Verify contextual graph ingestion created contexts
4. Check product name matches exactly

### No Edges Discovered

1. Verify MDL ingestion created edges
2. Check `contextual_edges` collection exists
3. Verify edge types (BELONGS_TO_TABLE, HAS_MANY_TABLES, etc.)

### Planning Fails

1. Check LLM API key
2. Verify input data is populated
3. Check prompt size (reduce entities if too large)

## Next Steps

1. **Extend Planning**: Add more detailed plans for each component
2. **Add Metrics Generation**: Generate metrics from identified tables
3. **Add Compliance Retrieval**: Retrieve actual compliance controls
4. **Add Risk Assessment**: Assess risks for identified entities
5. **Add Multi-Hop Reasoning**: Traverse multiple relationship hops


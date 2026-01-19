# Startup Initialization

This module handles the initialization of graphs and assistants at application startup.

## Overview

The startup process:
1. Loads dependencies (database, vector store, LLM, etc.)
2. Initializes graphs and assistants
3. Registers them with the graph registry for streaming

## Configuration

### Option 1: Use Config File

Create a `graph_config.yaml` file in `app/core/` (see `graph_config.yaml.example`):

```yaml
assistants:
  - assistant_id: "compliance_assistant"
    name: "Compliance Assistant"
    description: "Helps with compliance and risk analysis"
    graphs:
      - graph_id: "compliance_rag"
        name: "Compliance RAG"
        set_as_default: true
```

The config file will be automatically loaded if it exists.

### Option 2: Programmatic Initialization

Graphs and assistants are initialized programmatically in `startup.py`:

- **Compliance Assistant**: For compliance, risk analysis, and regulatory queries
- **Data Science Assistant**: For data analysis, modeling, and statistical questions
- **Knowledge Assistant**: General purpose knowledge base queries

## Adding New Assistants

### Method 1: Add to startup.py

Edit `app/core/startup.py` and add a new initialization function:

```python
async def _initialize_your_assistant(
    registry: GraphRegistry,
    llm: Any,
    settings: Any
) -> None:
    """Initialize Your Assistant"""
    logger.info("Initializing Your Assistant...")
    
    assistant = registry.register_assistant(
        assistant_id="your_assistant",
        name="Your Assistant",
        description="Description of what it does"
    )
    
    # Create and register graphs
    graph = _create_your_graph(llm, settings)
    if graph:
        registry.register_graph(
            assistant_id="your_assistant",
            graph_id="your_graph",
            graph=graph,
            set_as_default=True
        )
```

Then call it in `initialize_graphs_and_assistants()`.

### Method 2: Use Config File

Add to `graph_config.yaml`:

```yaml
assistants:
  - assistant_id: "your_assistant"
    name: "Your Assistant"
    graphs:
      - graph_id: "your_graph"
        name: "Your Graph"
```

Note: Graphs still need to be created programmatically. The config file is for metadata only.

## Creating Graphs

### Simple Graph

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict

class MyState(TypedDict):
    query: str
    answer: str

def my_node(state: MyState) -> MyState:
    state["answer"] = f"Answer to: {state['query']}"
    return state

graph = StateGraph(MyState)
graph.add_node("processor", my_node)
graph.set_entry_point("processor")
graph.add_edge("processor", END)

checkpointer = MemorySaver()
compiled = graph.compile(checkpointer=checkpointer)
```

### Using Dynamic LangGraph Framework

If you implement the framework from `docs/dynamic_langraph.md`:

```python
from your_framework import GraphBuilder, GraphSpec, RuntimeContext

runtime = RuntimeContext(tool_registry={...})
spec = GraphSpec(name="my_graph", entrypoint="...")
# Add nodes and edges to spec
compiled = GraphBuilder(runtime).compile(spec)
```

## Graph Registry

All graphs and assistants are registered in the global `GraphRegistry`:

```python
from app.streams import get_registry

registry = get_registry()
assistants = registry.list_assistants()
graphs = registry.list_assistant_graphs("compliance_assistant")
```

## Accessing at Runtime

The registry is available in `app.state.graph_registry`:

```python
# In a FastAPI endpoint
@app.get("/assistants")
async def list_assistants(request: Request):
    registry = request.app.state.graph_registry
    return registry.list_assistants()
```

## Health Check

The health check endpoint (`/api/health`) includes graph registry status:

```json
{
  "services": {
    "graph_registry": {
      "status": "available",
      "assistants_count": 3,
      "assistants": ["compliance_assistant", "data_science_assistant", "knowledge_assistant"]
    }
  }
}
```

## Troubleshooting

### Graphs Not Initializing

- Check logs for errors during startup
- Verify dependencies (LLM, database) are available
- Check that graph creation functions don't raise exceptions

### Config File Not Loading

- Ensure `graph_config.yaml` exists in `app/core/`
- Check YAML syntax is valid
- Verify file permissions

### Assistants Not Available

- Check that `initialize_graphs_and_assistants()` is called in `main.py`
- Verify registry is stored in `app.state.graph_registry`
- Check startup logs for initialization errors


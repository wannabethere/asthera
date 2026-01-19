# Graph Streaming Module

A generic streaming solution using Server-Sent Events (SSE) for invoking LangGraph graphs with real-time updates.

## Features

- **SSE Streaming**: Real-time updates during graph execution
- **Multiple Graphs per Assistant**: Each assistant can have multiple configured graphs
- **Event Types**: Comprehensive event system (node starts, completions, state updates, errors, etc.)
- **Session Management**: Support for checkpointing and resumable workflows
- **Keep-Alive**: Automatic keep-alive events to maintain connections
- **FastAPI Integration**: Ready-to-use router endpoints

## Architecture

### Components

1. **Events** (`events.py`): SSE event models and serialization
2. **Graph Registry** (`graph_registry.py`): Manages assistants and their graphs
3. **Streaming Service** (`streaming_service.py`): Core streaming logic using LangGraph's `astream_events`
4. **Models** (`models.py`): Request/response models for API
5. **Router** (`router.py`): FastAPI endpoints for streaming

## Usage

### 1. Register an Assistant and Graph

```python
from app.streams import get_registry, GraphRegistry
from langgraph.graph import StateGraph, END

# Get the registry
registry = get_registry()

# Create an assistant
assistant = registry.register_assistant(
    assistant_id="knowledge_assistant",
    name="Knowledge Assistant",
    description="Helps with knowledge base queries"
)

# Build your LangGraph (example)
graph = StateGraph(YourState)
graph.add_node("node1", your_node_function)
graph.add_edge(END, "node1")
compiled_graph = graph.compile()

# Register the graph
graph_config = registry.register_graph(
    assistant_id="knowledge_assistant",
    graph_id="rag_graph",
    graph=compiled_graph,
    name="RAG Graph",
    description="Self-correcting RAG workflow",
    set_as_default=True
)
```

### 2. Use the Streaming Endpoint

#### Client-side (JavaScript)

```javascript
const eventSource = new EventSource('/streams/invoke', {
    method: 'POST',
    body: JSON.stringify({
        assistant_id: 'knowledge_assistant',
        graph_id: 'rag_graph',  // optional, uses default if not provided
        query: 'What is self-correcting RAG?',
        session_id: 'user-session-123'  // optional, auto-generated if not provided
    })
});

eventSource.addEventListener('graph_started', (e) => {
    const data = JSON.parse(e.data);
    console.log('Graph started:', data);
});

eventSource.addEventListener('node_started', (e) => {
    const data = JSON.parse(e.data);
    console.log('Node started:', data.node_name);
});

eventSource.addEventListener('state_update', (e) => {
    const data = JSON.parse(e.data);
    console.log('State updated:', data.state_snapshot);
});

eventSource.addEventListener('result', (e) => {
    const data = JSON.parse(e.data);
    console.log('Final result:', data.result);
});

eventSource.addEventListener('graph_completed', (e) => {
    const data = JSON.parse(e.data);
    console.log('Graph completed in', data.duration_ms, 'ms');
    eventSource.close();
});

eventSource.addEventListener('graph_error', (e) => {
    const data = JSON.parse(e.data);
    console.error('Error:', data.error);
    eventSource.close();
});
```

#### Python Client

```python
import requests
import json

response = requests.post(
    'http://localhost:8000/streams/invoke',
    json={
        'assistant_id': 'knowledge_assistant',
        'graph_id': 'rag_graph',
        'query': 'What is self-correcting RAG?',
        'session_id': 'user-session-123'
    },
    stream=True
)

for line in response.iter_lines():
    if line:
        line_str = line.decode('utf-8')
        if line_str.startswith('data: '):
            data = json.loads(line_str[6:])
            event_type = data.get('event_type')
            
            if event_type == 'graph_started':
                print(f"Graph started: {data['query']}")
            elif event_type == 'node_started':
                print(f"Node started: {data['node_name']}")
            elif event_type == 'state_update':
                print(f"State updated: {data['changed_keys']}")
            elif event_type == 'result':
                print(f"Result: {data['result']}")
            elif event_type == 'graph_completed':
                print(f"Completed in {data['duration_ms']}ms")
            elif event_type == 'graph_error':
                print(f"Error: {data['error']}")
```

### 3. Programmatic Usage

```python
from app.streams import GraphStreamingService, get_registry

service = GraphStreamingService(registry=get_registry())

async def process_query(query: str):
    async for event in service.stream_graph_execution(
        assistant_id="knowledge_assistant",
        graph_id="rag_graph",
        input_data={"query": query},
        session_id="session-123"
    ):
        # Process SSE event string
        print(event)
```

## Event Types

### Graph Lifecycle Events

- `graph_started`: Graph execution begins
- `graph_completed`: Graph execution completes successfully
- `graph_error`: Graph execution fails

### Node Events

- `node_started`: A node begins execution
- `node_completed`: A node completes execution
- `node_error`: A node execution fails

### State Events

- `state_update`: Graph state is updated (includes changed keys)
- `progress`: Progress update (0.0 to 1.0)

### Result Events

- `result`: Final result data
- `keep_alive`: Keep-alive ping (every 30 seconds by default)

## API Endpoints

### POST `/streams/invoke`

Invoke a graph and stream events.

**Request Body:**
```json
{
    "assistant_id": "string",
    "graph_id": "string (optional)",
    "query": "string",
    "session_id": "string (optional)",
    "input_data": {},
    "config": {}
}
```

### POST `/streams/assistants`

Create a new assistant.

### GET `/streams/assistants`

List all assistants.

### GET `/streams/assistants/{assistant_id}`

Get assistant information.

### GET `/streams/assistants/{assistant_id}/graphs`

List all graphs for an assistant.

### DELETE `/streams/assistants/{assistant_id}`

Delete an assistant.

### DELETE `/streams/assistants/{assistant_id}/graphs/{graph_id}`

Delete a graph from an assistant.

## Integration with FastAPI

Add the router to your FastAPI app:

```python
from fastapi import FastAPI
from app.routers import streaming_router

app = FastAPI()
app.include_router(streaming_router)
```

**Note:** The router is now located in `app/routers/streaming.py` for better organization. See `app/routers/README.md` for more information on adding new routers.

## Example: Integration with Dynamic LangGraph Framework

```python
from app.streams import get_registry
from docs.dynamic_langraph import GraphBuilder, build_demo_spec, RuntimeContext

# Build your graph using the dynamic framework
runtime = RuntimeContext(tool_registry={"calc": lambda a, b: a + b})
spec = build_demo_spec()
app = GraphBuilder(runtime).compile(spec, checkpointer_backend="memory")

# Register with streaming
registry = get_registry()
registry.register_assistant(
    assistant_id="demo_assistant",
    name="Demo Assistant"
)
registry.register_graph(
    assistant_id="demo_assistant",
    graph_id="demo_graph",
    graph=app,
    set_as_default=True
)

# Now you can stream it via the API!
```

## Advanced: Custom Result Extraction

You can provide a custom function to extract results from the final state:

```python
def extract_result(final_state: Dict[str, Any]) -> Dict[str, Any]:
    """Extract only relevant fields from final state"""
    return {
        "answer": final_state.get("final_answer"),
        "confidence": final_state.get("critique", {}).get("confidence"),
        "docs_used": len(final_state.get("retrieved_docs", []))
    }

# Use in streaming
async for event in service.stream_graph_execution(
    assistant_id="knowledge_assistant",
    graph_id="rag_graph",
    input_data={"query": "..."},
    session_id="session-123",
    result_extractor=extract_result
):
    # Events will have extracted result in result event
    pass
```

## Error Handling

All errors are emitted as `graph_error` or `node_error` events with:
- `error`: Error message
- `error_type`: Error class name
- `traceback`: Full traceback (if available)

The stream will continue until completion or error, then close.

## Session Management

Each invocation can use a `session_id` for checkpointing. If not provided, a UUID is auto-generated. The same `session_id` can be used to resume long-running workflows (if your graph supports checkpointing).

## Notes

- Graphs must be registered programmatically (not via API) since LangGraph objects can't be serialized over HTTP
- The registry is in-memory by default. For production, consider persisting to a database
- Keep-alive events are sent every 30 seconds by default to maintain connections
- SSE events are automatically formatted according to the SSE specification


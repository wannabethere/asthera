# Integration Guide: Graph Streaming with Dynamic LangGraph

This guide shows how to integrate the streaming module with the dynamic LangGraph framework from `docs/dynamic_langraph.md`.

## Quick Start

### 1. Build Your Graph Using Dynamic Framework

```python
from docs.dynamic_langraph import GraphBuilder, build_demo_spec, RuntimeContext, BaseGraphState
from app.streams import get_registry

# Build your graph
runtime = RuntimeContext(tool_registry={"calc": lambda a, b: a + b})
spec = build_demo_spec()
compiled_graph = GraphBuilder(runtime).compile(spec, checkpointer_backend="memory")

# Register with streaming
registry = get_registry()
registry.register_assistant(
    assistant_id="knowledge_assistant",
    name="Knowledge Assistant",
    description="Self-correcting RAG assistant"
)

registry.register_graph(
    assistant_id="knowledge_assistant",
    graph_id="self_correcting_rag",
    graph=compiled_graph,
    name="Self-Correcting RAG",
    description="RAG with self-correction loops",
    set_as_default=True
)
```

### 2. Create Result Extractor for BaseGraphState

```python
from typing import Dict, Any
from docs.dynamic_langraph import BaseGraphState

def extract_rag_result(final_state: Dict[str, Any]) -> Dict[str, Any]:
    """Extract relevant fields from BaseGraphState"""
    return {
        "answer": final_state.get("final_answer"),
        "query": final_state.get("query"),
        "confidence": final_state.get("critique", {}).get("confidence", 0.0),
        "evidence_score": final_state.get("critique", {}).get("evidence_score", 0.0),
        "docs_retrieved": len(final_state.get("retrieved_docs", [])),
        "events": final_state.get("events", []),
        "stop_reason": final_state.get("stop_reason")
    }
```

### 3. Use in FastAPI App

```python
from fastapi import FastAPI
from app.routers import streaming_router
from app.streams import GraphStreamingService, get_registry

app = FastAPI()
app.include_router(streaming_router)

# Optional: Register graphs at startup
@app.on_event("startup")
async def startup():
    # Your graph registration code here
    pass
```

### 4. Client Usage

```javascript
// Frontend JavaScript
const eventSource = new EventSource('/streams/invoke', {
    method: 'POST',
    body: JSON.stringify({
        assistant_id: 'knowledge_assistant',
        query: 'What is self-correcting RAG?',
        session_id: 'user-123'
    })
});

// Listen for specific events
eventSource.addEventListener('node_started', (e) => {
    const data = JSON.parse(e.data);
    console.log(`Node started: ${data.node_name}`);
    // Update UI: show which node is running
});

eventSource.addEventListener('state_update', (e) => {
    const data = JSON.parse(e.data);
    if (data.changed_keys.includes('retrieved_docs')) {
        // Update UI: show retrieved documents
        console.log(`Retrieved ${data.state_snapshot.retrieved_docs.length} docs`);
    }
    if (data.changed_keys.includes('draft')) {
        // Update UI: show draft answer
        console.log(`Draft: ${data.state_snapshot.draft}`);
    }
});

eventSource.addEventListener('result', (e) => {
    const data = JSON.parse(e.data);
    console.log('Final answer:', data.result.answer);
    console.log('Confidence:', data.result.confidence);
    // Update UI: show final result
});

eventSource.addEventListener('graph_completed', (e) => {
    eventSource.close();
});
```

## Advanced: Multiple Graphs per Assistant

```python
# Register multiple graphs for different use cases
registry = get_registry()

# Short lane graph (fast, simple queries)
short_graph = build_short_lane_graph()
registry.register_graph(
    assistant_id="knowledge_assistant",
    graph_id="short_lane",
    graph=short_graph,
    name="Short Lane",
    description="Fast path for simple queries"
)

# Long lane graph (complex, multi-step queries)
long_graph = build_long_lane_graph()
registry.register_graph(
    assistant_id="knowledge_assistant",
    graph_id="long_lane",
    graph=long_graph,
    name="Long Lane",
    description="Complex multi-step workflow",
    set_as_default=True
)

# Client can choose which graph to use
fetch('/streams/invoke', {
    method: 'POST',
    body: JSON.stringify({
        assistant_id: 'knowledge_assistant',
        graph_id: 'short_lane',  // or 'long_lane'
        query: 'Simple question'
    })
});
```

## Integration with Self-Correcting RAG Template

The streaming service works seamlessly with the self-correcting RAG template:

```python
from docs.dynamic_langraph import (
    GraphSpec, add_self_correcting_rag_template,
    GraphBuilder, RuntimeContext
)

# Create a custom spec with RAG template
spec = GraphSpec(name="custom_rag", entrypoint="rag.memory_recall")
add_self_correcting_rag_template(spec, prefix="rag")

# Add custom nodes
def custom_retriever(state, deps):
    # Your custom retrieval logic
    state.retrieved_docs = [...]
    return state

spec.nodes["rag.retrieve"].fn = custom_retriever

# Build and register
runtime = RuntimeContext(tool_registry={})
graph = GraphBuilder(runtime).compile(spec)

registry = get_registry()
registry.register_graph(
    assistant_id="knowledge_assistant",
    graph_id="custom_rag",
    graph=graph
)
```

## Session Management and Checkpointing

For long-running workflows with checkpointing:

```python
# Use SQLite checkpointing
graph = GraphBuilder(runtime).compile(
    spec,
    checkpointer_backend="sqlite",
    sqlite_path="checkpoints.db"
)

# Same session_id can resume
registry.register_graph(
    assistant_id="knowledge_assistant",
    graph_id="long_workflow",
    graph=graph
)

# First invocation
POST /streams/invoke
{
    "assistant_id": "knowledge_assistant",
    "graph_id": "long_workflow",
    "query": "Complex query",
    "session_id": "workflow-123"
}

# Later, resume with same session_id
POST /streams/invoke
{
    "assistant_id": "knowledge_assistant",
    "graph_id": "long_workflow",
    "query": "Continue from where we left off",
    "session_id": "workflow-123"  // Same session
}
```

## Error Handling

The streaming service automatically handles errors:

```javascript
eventSource.addEventListener('graph_error', (e) => {
    const data = JSON.parse(e.data);
    console.error('Error:', data.error);
    console.error('Type:', data.error_type);
    // Show error to user
});

eventSource.addEventListener('node_error', (e) => {
    const data = JSON.parse(e.data);
    console.error(`Node ${data.node_name} failed:`, data.error);
    // Show partial progress
});
```

## Monitoring and Observability

All events include timestamps and metadata:

```python
# Events include:
# - timestamp: When the event occurred
# - session_id: Session identifier
# - assistant_id: Assistant identifier
# - graph_id: Graph identifier
# - duration_ms: Execution duration (for completion events)
```

You can log or store these events for monitoring:

```python
async def log_event(event_str: str):
    """Log or store events for monitoring"""
    # Parse and store in your monitoring system
    pass

# In your streaming endpoint
async for event in service.stream_graph_execution(...):
    await log_event(event)
    yield event
```

## Best Practices

1. **Always provide session_id** for resumable workflows
2. **Use result extractors** to reduce payload size
3. **Handle keep-alive events** to detect connection issues
4. **Close EventSource** when graph completes or errors
5. **Register graphs at startup** for better performance
6. **Use descriptive graph names** for better debugging

## Production Considerations

1. **Persistent Registry**: Consider storing graph registry in a database
2. **Rate Limiting**: Add rate limiting to streaming endpoints
3. **Authentication**: Add auth middleware to protect endpoints
4. **Monitoring**: Track event rates, errors, and latencies
5. **Connection Management**: Handle client disconnections gracefully
6. **Resource Cleanup**: Clean up checkpoints and sessions periodically


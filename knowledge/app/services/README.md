# Unified Service Architecture

This module provides a unified service architecture following the pipeline pattern from `agents/docs/pipeline.md` with async invocations.

## Architecture

```
app/services/
├── base.py                    # BaseService with async support
├── models.py                  # Request/Response models (Pydantic)
├── contextual_graph_service.py # Unified service (main entry point)
├── metadata_service.py        # Legacy metadata service
├── hybrid_search_service.py   # Hybrid search service
├── contextual_graph_storage.py # Vector storage service
└── storage/                   # Storage services (PostgreSQL operations)
    ├── control_service.py
    ├── requirement_service.py
    ├── evidence_service.py
    ├── measurement_service.py
    └── contextual_graph_service.py  # Legacy unified storage service
```

## Key Features

- ✅ **Async-first**: All operations are async
- ✅ **Unified Interface**: Single service for all operations
- ✅ **Type-safe**: Pydantic models for requests/responses
- ✅ **Caching**: Built-in request caching with TTL
- ✅ **Error Handling**: Comprehensive error handling
- ✅ **Request Tracking**: Async request tracking and status

## Usage

### Initialize Service

```python
import asyncpg
import chromadb
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from app.services import ContextualGraphService
from app.services.models import (
    ContextSearchRequest,
    ControlSaveRequest,
    MultiHopQueryRequest
)

# Initialize dependencies
db_pool = await asyncpg.create_pool("postgresql://...")
chroma_client = chromadb.PersistentClient(path="./chroma_store")
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
llm = ChatOpenAI(model="gpt-4o")

# Create service
service = ContextualGraphService(
    db_pool=db_pool,
    chroma_client=chroma_client,
    embeddings_model=embeddings,
    llm=llm
)
```

### Context Operations

```python
# Search for contexts
request = ContextSearchRequest(
    description="Healthcare org preparing for HIPAA audit",
    top_k=5
)
response = await service.search_contexts(request)

if response.success:
    for ctx in response.data["contexts"]:
        print(f"Context: {ctx['context_id']}")
```

### Control Operations

```python
# Save control with vector document
request = ControlSaveRequest(
    control_id="HIPAA-AC-001",
    framework="HIPAA",
    control_name="Access Control",
    control_description="Implement access controls for ePHI",
    context_document="Rich implementation guide...",
    context_metadata={"context_id": "ctx_001"}
)
response = await service.save_control(request)
```

### Query Operations

```python
# Multi-hop contextual search
request = MultiHopQueryRequest(
    query="What evidence do I need for access controls?",
    context_id="ctx_001",
    max_hops=3
)
response = await service.multi_hop_query(request)

if response.success:
    print("Reasoning Path:")
    for hop in response.data["reasoning_path"]:
        print(f"  Hop {hop['hop']}: {hop['entity_type']}")
    print(f"\nFinal Answer: {response.data['final_answer']}")
```

### Async Request Processing

```python
# Process request asynchronously
request = ControlSaveRequest(...)
request_id = await service.process_request_async(request)

# Check status
status = service.get_request_status(request_id)
print(f"Status: {status['status']}")

# Cancel if needed
await service.cancel_request(request_id)
```

## Service Methods

### Context Operations
- `search_contexts(request: ContextSearchRequest) -> ContextSearchResponse`
- `save_context(request: ContextSaveRequest) -> ContextSaveResponse`

### Control Operations
- `save_control(request: ControlSaveRequest) -> ControlSaveResponse`
- `search_controls(request: ControlSearchRequest) -> ControlSearchResponse`

### Measurement Operations
- `save_measurement(request: MeasurementSaveRequest) -> MeasurementSaveResponse`
- `query_measurements(request: MeasurementQueryRequest) -> MeasurementQueryResponse`

### Query Operations
- `multi_hop_query(request: MultiHopQueryRequest) -> MultiHopQueryResponse`
- `get_priority_controls(request: PriorityControlsRequest) -> PriorityControlsResponse`

## Request/Response Models

All requests extend `ServiceRequest` and include:
- `request_id`: Auto-generated unique ID

All responses extend `ServiceResponse` and include:
- `success`: Boolean indicating success
- `data`: Response data (if successful)
- `error`: Error message (if failed)
- `metadata`: Additional metadata
- `request_id`: Request ID for tracking

## Error Handling

```python
response = await service.search_contexts(request)

if not response.success:
    logger.error(f"Error: {response.error}")
    # Handle error
else:
    # Process data
    data = response.data
```

## Caching

The service automatically caches results using TTLCache:
- Default TTL: 120 seconds
- Default max size: 1,000,000 entries
- Cache key: Based on request_id

## Integration with Storage Services

The unified service internally uses:
- `app.services.storage.ControlStorageService` - PostgreSQL control operations
- `app.services.storage.RequirementStorageService` - PostgreSQL requirement operations
- `app.services.storage.EvidenceStorageService` - PostgreSQL evidence operations
- `app.services.storage.MeasurementStorageService` - PostgreSQL measurement operations
- `app.services.contextual_graph_storage.ContextualGraphStorage` - ChromaDB vector operations
- `app.storage.query.ContextualGraphQueryEngine` - Query engine for multi-hop reasoning

## Migration from Legacy Services

### Old Way (Direct Service Calls)
```python
from app.services.storage.control_service import ControlStorageService

service = ControlStorageService(db_pool)
control_id = await service.save_control(control)
```

### New Way (Unified Service)
```python
from app.services import ContextualGraphService
from app.services.models import ControlSaveRequest

service = ContextualGraphService(db_pool, chroma_client, embeddings)
request = ControlSaveRequest(
    control_id=control.control_id,
    framework=control.framework,
    control_name=control.control_name
)
response = await service.save_control(request)
```

## Best Practices

1. **Always check response.success** before accessing data
2. **Use request_id** for tracking and debugging
3. **Handle errors gracefully** with try/except
4. **Use async/await** for all service calls
5. **Cache results** when appropriate (automatic with BaseService)


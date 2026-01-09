# Service Architecture

## Overview

Unified service architecture following the pipeline pattern from `agents/docs/pipeline.md` with clear separation of concerns.

## Directory Structure

```
app/services/
├── base.py                          # BaseService with async support
├── models.py                        # Request/Response models (Pydantic)
├── contextual_graph_service.py      # Unified service (main entry point) ⭐
├── metadata_service.py              # Legacy metadata service
├── hybrid_search_service.py        # Hybrid search service
├── contextual_graph_storage.py      # Vector storage service (ChromaDB)
│
├── storage/                         # Storage services (PostgreSQL operations)
│   ├── control_service.py          # Control CRUD operations
│   ├── requirement_service.py      # Requirement CRUD operations
│   ├── evidence_service.py         # Evidence CRUD operations
│   ├── measurement_service.py       # Measurement CRUD operations
│   └── contextual_graph_service.py # Legacy unified storage service
│
└── examples/
    └── unified_service_example.py   # Usage examples
```

## Separation of Concerns

### Main Services (`app/services/`)
**Purpose**: High-level unified services with async interface

- **ContextualGraphService** ⭐ - Main unified service
  - Combines PostgreSQL + ChromaDB
  - Provides async interface for all operations
  - Uses BaseService pattern for caching/tracking
  - Request/Response models for type safety

- **HybridSearchService** - Hybrid search (dense + BM25)
- **MetadataService** - Universal metadata operations
- **ContextualGraphStorage** - Vector storage operations

### Storage Services (`app/services/storage/`)
**Purpose**: Low-level PostgreSQL CRUD operations

- **ControlStorageService** - Control entity operations
- **RequirementStorageService** - Requirement entity operations
- **EvidenceStorageService** - Evidence type operations
- **MeasurementStorageService** - Measurement and analytics operations

## Service Hierarchy

```
ContextualGraphService (Unified)
    ├── Uses: ControlStorageService (PostgreSQL)
    ├── Uses: RequirementStorageService (PostgreSQL)
    ├── Uses: EvidenceStorageService (PostgreSQL)
    ├── Uses: MeasurementStorageService (PostgreSQL)
    ├── Uses: ContextualGraphStorage (ChromaDB)
    └── Uses: ContextualGraphQueryEngine (Query operations)
```

## Usage Patterns

### Pattern 1: Unified Service (Recommended)

```python
from app.services import ContextualGraphService
from app.services.models import ContextSearchRequest

service = ContextualGraphService(db_pool, chroma_client, embeddings, llm)
request = ContextSearchRequest(description="...", top_k=5)
response = await service.search_contexts(request)
```

### Pattern 2: Direct Storage Service (Low-level)

```python
from app.services.storage import ControlStorageService

service = ControlStorageService(db_pool)
control_id = await service.save_control(control)
```

## Request/Response Flow

```
User Code
    ↓
Request Model (Pydantic)
    ↓
ContextualGraphService.process_request()
    ↓
BaseService._process_request_impl()
    ↓
Specific Handler (e.g., search_contexts)
    ↓
Storage Services (PostgreSQL)
    ↓
Vector Storage (ChromaDB)
    ↓
Response Model (Pydantic)
    ↓
User Code
```

## Async Invocations

All services support:
- **Synchronous async**: `await service.method(request)`
- **Async tracking**: `request_id = await service.process_request_async(request)`
- **Status checking**: `status = service.get_request_status(request_id)`
- **Cancellation**: `await service.cancel_request(request_id)`

## Benefits

1. **Clear Separation**: Main services vs storage services
2. **Unified Interface**: Single entry point for all operations
3. **Type Safety**: Pydantic models for requests/responses
4. **Async First**: All operations are async
5. **Caching**: Built-in request caching
6. **Error Handling**: Consistent error responses
7. **Extensibility**: Easy to add new operations

## Migration Guide

### From `app/storage/services/` to `app/services/storage/`

**Old Import:**
```python
from app.storage.services.control_service import ControlStorageService
```

**New Import:**
```python
from app.services.storage import ControlStorageService
# or
from app.services.storage.control_service import ControlStorageService
```

### From Direct Storage to Unified Service

**Old Way:**
```python
control_service = ControlStorageService(db_pool)
control_id = await control_service.save_control(control)
```

**New Way:**
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


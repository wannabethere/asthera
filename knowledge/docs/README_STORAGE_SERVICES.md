# Storage Services

PostgreSQL storage services for contextual graph entities.

## Location

These services are located at `app/services/storage/` to maintain clear separation of concerns:
- **Main services** (`app/services/`) - High-level unified services
- **Storage services** (`app/services/storage/`) - PostgreSQL CRUD operations

## Services

- **ControlStorageService**: Manage control entities
- **RequirementStorageService**: Manage requirement entities
- **EvidenceStorageService**: Manage evidence type entities
- **MeasurementStorageService**: Manage compliance measurements and analytics
- **ContextualGraphStorageService**: Legacy unified storage service (use `app.services.ContextualGraphService` instead)

## Usage

### Direct Usage (Low-level)

```python
from app.services.storage import ControlStorageService
import asyncpg

db_pool = await asyncpg.create_pool("postgresql://...")
service = ControlStorageService(db_pool)

# Save control
control = Control(
    control_id="HIPAA-AC-001",
    framework="HIPAA",
    control_name="Access Control"
)
control_id = await service.save_control(control)
```

### Via Unified Service (Recommended)

```python
from app.services import ContextualGraphService
from app.services.models import ControlSaveRequest

service = ContextualGraphService(db_pool, chroma_client, embeddings)
request = ControlSaveRequest(
    control_id="HIPAA-AC-001",
    framework="HIPAA",
    control_name="Access Control"
)
response = await service.save_control(request)
```

## Architecture

These services handle:
- **PostgreSQL operations**: CRUD for structured entities
- **Data models**: Using `app.storage.models`
- **Async operations**: All methods are async
- **Transaction management**: Uses asyncpg connection pools

The unified service (`app.services.ContextualGraphService`) combines these storage services with vector storage for a complete solution.


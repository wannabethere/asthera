# DomainManager Initialization Fix

## Issue
The `DomainManager` class requires a `session` parameter in its constructor, but when using async sessions with the DocumentIngestionService, we need to pass `None` to indicate that the session will be managed asynchronously.

## Error
```
TypeError: DomainManager.__init__() missing 1 required positional argument: 'session'
```

## Solution

### Option 1: Use the Helper Function (Recommended)
```python
from app.dataingest.docingest_insights import create_services_with_config
from app.core.settings import ServiceConfig

# Create services with proper initialization
config = ServiceConfig()
service, persistence_service = create_services_with_config(
    config=config,
    chroma_path="./chroma_db"
)
```

### Option 2: Manual Initialization
```python
from app.core.settings import ServiceConfig
from app.core.session_manager import SessionManager
from app.utils.history import DomainManager
from app.dataingest.docingest_insights import create_ingestion_service

# Initialize components
config = ServiceConfig()
session_manager = SessionManager(config)
domain_manager = DomainManager(None)  # Pass None for async usage

# Create service
service = create_ingestion_service(
    session_manager=session_manager,
    domain_manager=domain_manager,
    chroma_path="./chroma_db"
)
```

### Option 3: Using DocumentPersistenceService
```python
from app.core.settings import ServiceConfig
from app.core.session_manager import SessionManager
from app.utils.history import DomainManager
from app.service.document_persistence_service import create_document_persistence_service

# Initialize components
config = ServiceConfig()
session_manager = SessionManager(config)
domain_manager = DomainManager(None)  # Pass None for async usage

# Create persistence service
persistence_service = create_document_persistence_service(
    session_manager=session_manager,
    domain_manager=domain_manager
)
```

## Why DomainManager(None)?

The `DomainManager` class was designed to work with synchronous database sessions. However, our DocumentIngestionService uses async sessions managed by the SessionManager. By passing `None` to the DomainManager constructor, we indicate that:

1. The session will be managed asynchronously by the SessionManager
2. Domain operations will be handled through the async session context
3. The DomainManager won't try to use its own session for database operations

## Example Usage

See `example_document_ingestion.py` for a complete working example that demonstrates:

1. Proper service initialization
2. Document ingestion with different types
3. Search and retrieval operations
4. Error handling

## Testing

Run the example script to verify everything works:

```bash
cd dataservices
python example_document_ingestion.py
```

This will test the complete flow and verify that the DomainManager initialization issue is resolved.

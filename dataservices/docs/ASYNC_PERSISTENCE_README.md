# Modified Persistence Service with SessionManager

This document describes the modification of the existing persistence service to use the SessionManager for async database operations.

## Overview

The persistence service has been modified to use the SessionManager for database operations, providing:

1. Async-first approach to database operations
2. Automatic session management through SessionManager
3. Better resource management and error handling
4. Simplified dependency injection

## Architecture

### SessionManager
- **Location**: `app/core/session_manager.py`
- **Purpose**: Manages database sessions and provides async context managers
- **Features**:
  - Singleton pattern for global access
  - Async context manager for database sessions
  - Automatic session cleanup
  - User session management

### Modified Persistence Services
- **Location**: `app/service/persistence_service.py`
- **Purpose**: All persistence services now use SessionManager
- **Services**:
  - `DefinitionPersistenceService`
  - `ProjectPersistenceService`
  - `UserExamplePersistenceService`
  - `SQLFunctionPersistenceService`
  - `InstructionPersistenceService`
  - `KnowledgeBasePersistenceService`

### Factory Pattern
- **Location**: `app/service/persistence_service.py` (PersistenceServiceFactory)
- **Purpose**: Provides access to all persistence services
- **Usage**: Dependency injection in FastAPI endpoints

## Key Changes

### 1. Constructor Changes
All persistence services now take `SessionManager` instead of `Session`:

```python
# Old
def __init__(self, session: Session, project_manager: ProjectManager):
    self.session = session

# New
def __init__(self, session_manager: SessionManager, project_manager: ProjectManager):
    self.session_manager = session_manager
```

### 2. Async Operations
All database operations are now async:

```python
# Old
def persist_user_example(self, user_example: UserExample, project_id: str) -> str:
    try:
        # ... database operations
        self.session.commit()
        return str(example.example_id)
    except Exception as e:
        self.session.rollback()
        raise Exception(f"Failed to persist: {str(e)}")

# New
async def persist_user_example(self, user_example: UserExample, project_id: str) -> str:
    async with self.session_manager.get_async_db_session() as session:
        try:
            # ... database operations
            await session.commit()
            return str(example.example_id)
        except Exception as e:
            await session.rollback()
            raise Exception(f"Failed to persist: {str(e)}")
```

### 3. SQLAlchemy 2.0 Style Queries
Updated to use modern SQLAlchemy 2.0 syntax:

```python
# Old
table = self.session.query(Table).filter(Table.project_id == project_id).first()

# New
result = await session.execute(select(Table).where(Table.project_id == project_id))
table = result.scalar_one_or_none()
```

## Usage

### 1. Service Initialization

The SessionManager is initialized at application startup in `main.py`:

```python
from app.core.session_manager import SessionManager
from app.core.settings import ServiceConfig

# Initialize session manager at startup
session_manager = SessionManager(ServiceConfig())
session_manager.create_tables()
```

### 2. Dependency Injection

Use the dependency injection function to get the persistence factory:

```python
from app.core.dependencies import get_persistence_factory
from app.service.persistence_service import PersistenceServiceFactory

async def my_endpoint(
    factory: PersistenceServiceFactory = Depends(get_persistence_factory)
):
    # Use the factory to access services
    user_example_service = factory.get_user_example_service()
    # ... perform async operations
```

### 3. Service Operations

All persistence operations are now async:

```python
# Create an example
example_id = await user_example_service.persist_user_example(user_example, project_id)

# Get an example
example = await user_example_service.get_user_example_by_id(example_id)

# Update an example
updated_example = await user_example_service.update_user_example(example_id, updates, modified_by)

# Delete an example
success = await user_example_service.delete_user_example(example_id)

# List examples
examples = await user_example_service.get_user_examples(project_id, definition_type)
```

### 4. Router Implementation

Example of router implementation:

```python
@router.post("/", response_model=ExampleRead)
async def create_example(
    example_data: ExampleCreate,
    factory: PersistenceServiceFactory = Depends(get_persistence_factory)
):
    """Create a new example using persistence service"""
    try:
        return await create_example(example_data, factory)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create example: {str(e)}"
        )
```

## Key Features

### 1. Async Context Managers
The SessionManager provides async context managers for automatic session management:

```python
async with self.session_manager.get_async_db_session() as session:
    # Perform database operations
    result = await session.execute(query)
    await session.commit()
```

### 2. Automatic Session Cleanup
Sessions are automatically closed when exiting the context manager, preventing resource leaks.

### 3. Error Handling
All async operations include proper error handling with rollback on exceptions:

```python
try:
    # Database operations
    await session.commit()
except Exception as e:
    await session.rollback()
    raise Exception(f"Failed to persist: {str(e)}")
```

### 4. Modern SQLAlchemy
Uses SQLAlchemy 2.0 style queries with `select()` and `execute()`.

## Migration Guide

### From Old to New

1. **Update imports**:
   ```python
   # Old
   from app.service.persistence_service import PersistenceServiceFactory
   
   # New (same import, but different usage)
   from app.service.persistence_service import PersistenceServiceFactory
   ```

2. **Update function signatures**:
   ```python
   # Old
   def create_example(data: ExampleCreate, db: Session) -> ExampleRead:
   
   # New
   async def create_example(data: ExampleCreate, factory: PersistenceServiceFactory) -> ExampleRead:
   ```

3. **Update service calls**:
   ```python
   # Old
   example_id = user_example_service.persist_user_example(user_example, project_id)
   
   # New
   example_id = await user_example_service.persist_user_example(user_example, project_id)
   ```

4. **Update router endpoints**:
   ```python
   # Old
   def create_example(data: ExampleCreate, db: Session = Depends(get_db)):
   
   # New
   async def create_example(data: ExampleCreate, factory: PersistenceServiceFactory = Depends(get_persistence_factory)):
   ```

## Testing

### Service Testing

When testing services, use `pytest-asyncio`:

```python
import pytest
from app.service.persistence_service import PersistenceServiceFactory

@pytest.mark.asyncio
async def test_create_example():
    # Setup
    session_manager = SessionManager(ServiceConfig())
    factory = PersistenceServiceFactory(session_manager, project_manager)
    
    # Test
    result = await create_example(example_data, factory)
    
    # Assert
    assert result is not None
```

## Benefits

1. **Better Performance**: Async operations allow for better concurrency
2. **Resource Management**: Automatic session cleanup prevents resource leaks
3. **Scalability**: Better handling of concurrent requests
4. **Modern Python**: Uses modern async/await patterns
5. **Maintainability**: Cleaner separation of concerns with dependency injection
6. **Simplified Architecture**: Single persistence service instead of separate sync/async versions

## Future Enhancements

1. **Connection Pooling**: Implement connection pooling for better performance
2. **Caching**: Add caching layer for frequently accessed data
3. **Monitoring**: Add metrics and monitoring for async operations
4. **Retry Logic**: Implement retry logic for transient failures
5. **Batch Operations**: Add support for batch operations

## Troubleshooting

### Common Issues

1. **Session not initialized**: Ensure SessionManager is initialized with config
2. **Missing await**: Remember to await all async operations
3. **Context manager errors**: Ensure proper use of async context managers
4. **Dependency injection errors**: Check that dependencies are properly configured

### Debugging

Enable debug logging in the SessionManager:

```python
session_manager = SessionManager(ServiceConfig(log_level="DEBUG"))
```

This will provide detailed logging of session creation, usage, and cleanup. 
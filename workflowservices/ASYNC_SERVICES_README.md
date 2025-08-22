# Async Services Conversion

This document explains the conversion of workflow services from synchronous to asynchronous operations to enable proper async/await patterns and streaming capabilities.

## Overview

All service classes in the `workflowservices/app/services/` directory have been converted from synchronous to asynchronous operations. This change enables:

1. **Non-blocking database operations** - Services can now properly await database queries
2. **Streaming support** - Services can be used in streaming contexts
3. **Better performance** - Async operations allow for concurrent processing
4. **Modern Python patterns** - Uses current async/await syntax

## Changes Made

### 1. BaseService (`baseservice.py`)

- All methods now use `async def`
- Database queries converted from `self.db.query().filter().first()` to `await self.db.execute(select().where())`
- ChromaDB operations now properly awaited
- Permission checking methods are async

### 2. AlertService (`alertservice.py`)

- All public methods (`create_task`, `get_task`, `update_task`, etc.) are now async
- All private helper methods are async
- Database operations use `select()` statements with `await self.db.execute()`
- ChromaDB operations properly awaited

### 3. ReportService (`reportservice.py`)

- All CRUD operations are now async
- Search and filtering methods are async
- Workflow integration methods are async

## Usage Examples

### Before (Synchronous - Don't use this anymore)

```python
# ❌ OLD WAY - This will cause blocking issues
def some_function():
    alert_service = AlertService(db_session)
    task = alert_service.create_task(user_id, task_data)  # Blocking!
    return task
```

### After (Asynchronous - Use this)

```python
# ✅ NEW WAY - Proper async/await pattern
async def some_function():
    alert_service = AlertService(db_session)
    task = await alert_service.create_task(user_id, task_data)  # Non-blocking!
    return task

# Or in a FastAPI endpoint
@app.post("/tasks")
async def create_task_endpoint(
    task_data: TaskCreate,
    current_user: User = Depends(get_current_user)
):
    alert_service = AlertService(db)
    task = await alert_service.create_task(
        user_id=current_user.id,
        task_data=task_data
    )
    return task
```

### Streaming Example

```python
# ✅ Streaming with async services
async def stream_tasks():
    alert_service = AlertService(db)
    
    # This can now be properly streamed
    async for task in alert_service.stream_tasks(user_id):
        yield task

# In FastAPI
@app.get("/tasks/stream")
async def stream_tasks_endpoint(
    current_user: User = Depends(get_current_user)
):
    return StreamingResponse(
        stream_tasks(),
        media_type="application/json"
    )
```

## Key Benefits

1. **Non-blocking I/O**: Database operations don't block the event loop
2. **Better scalability**: Can handle more concurrent requests
3. **Streaming support**: Services can yield results incrementally
4. **Modern Python**: Uses current async/await patterns
5. **Performance**: Better resource utilization

## Migration Notes

### For Existing Code

If you have existing code that calls these services, you need to:

1. **Add `async`** to the calling function
2. **Add `await`** before service method calls
3. **Update function signatures** to be async where needed

### Example Migration

```python
# Before
def old_function():
    service = AlertService(db)
    tasks = service.search_tasks(user_id, "query")
    return tasks

# After
async def new_function():
    service = AlertService(db)
    tasks = await service.search_tasks(user_id, "query")
    return tasks
```

### For FastAPI Endpoints

```python
# Before
@app.get("/tasks")
def get_tasks():
    service = AlertService(db)
    return service.search_tasks(user_id, "query")

# After
@app.get("/tasks")
async def get_tasks():
    service = AlertService(db)
    return await service.search_tasks(user_id, "query")
```

## Database Session Management

Make sure your database sessions are properly configured for async operations:

```python
# In your dependency injection
async def get_db():
    async with engine.begin() as conn:
        yield conn

# In your services
class AlertService(BaseService):
    def __init__(self, db: AsyncSession, chroma_client=None):
        super().__init__(db, chroma_client)
```

## Error Handling

Async services maintain the same error handling patterns but now properly propagate async context:

```python
async def safe_task_creation():
    try:
        alert_service = AlertService(db)
        task = await alert_service.create_task(user_id, task_data)
        return task
    except PermissionError as e:
        logger.error(f"Permission denied: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
```

## Testing Async Services

When testing async services, use async test functions:

```python
import pytest
import asyncio

@pytest.mark.asyncio
async def test_create_task():
    async with get_test_db() as db:
        service = AlertService(db)
        task = await service.create_task(user_id, task_data)
        assert task.name == task_data.name
```

## Performance Considerations

1. **Concurrent operations**: Multiple async operations can run concurrently
2. **Connection pooling**: Async sessions can be pooled more efficiently
3. **Memory usage**: Better memory management with async operations
4. **Scalability**: Can handle more concurrent users

## Next Steps

1. **Update all calling code** to use async/await
2. **Test thoroughly** to ensure all operations work correctly
3. **Consider adding streaming endpoints** where appropriate
4. **Monitor performance** improvements
5. **Update documentation** to reflect async patterns

## Troubleshooting

### Common Issues

1. **Missing await**: Forgetting to await async service methods
2. **Sync context**: Calling async methods from synchronous functions
3. **Session management**: Not properly managing async database sessions

### Debug Tips

1. Use `asyncio.create_task()` for concurrent operations
2. Check that all database operations are awaited
3. Verify ChromaDB operations are properly awaited
4. Use async logging for better debugging

## Support

If you encounter issues with the async conversion:

1. Check that all service calls use `await`
2. Verify database sessions are `AsyncSession`
3. Ensure ChromaDB client supports async operations
4. Review error logs for async context issues

from fastapi import APIRouter, HTTPException, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.core.dependencies import get_async_db_session, get_session_manager
from app.service.persistence_service import PersistenceServiceFactory
from app.utils.history import ProjectManager
from app.service.models import (
    ExampleCreate, ExampleUpdate, ExampleRead,
    UserExampleCreate, UserExampleUpdate, UserExampleRead,
    UserExample, DefinitionType
)

router = APIRouter()

def get_session_id(request: Request):
    return request.headers.get("X-Session-Id") or "demo-session"

def get_user_id(request: Request):
    return request.headers.get("X-User-Id") or "demo-user"

# ============================================================================
# STANDARD EXAMPLE ENDPOINTS
# ============================================================================

@router.post("/examples/", response_model=ExampleRead, summary="Create a new example.")
async def create(
    data: ExampleCreate, 
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Create a new example within a project."""
    try:
        # TODO: Get actual user from authentication
        created_by = user_id  # Use the user_id from dependency
        
        # Initialize services
        session_manager = get_session_manager()
        project_manager = ProjectManager(None)  # Pass None since we're using async sessions
        factory = PersistenceServiceFactory(session_manager, project_manager)
        user_example_service = factory.get_user_example_service()
        
        # Convert ExampleCreate to UserExample
        user_example = UserExample(
            definition_type=DefinitionType.SQL_PAIR,  # Default, can be enhanced
            name=data.question[:50],  # Use question as name, truncated
            description=data.question,
            sql=data.sql_query,
            additional_context={
                'context': data.context,
                'document_reference': data.document_reference,
                'instructions': data.instructions,
                'samples': data.samples,
                **data.json_metadata
            },
            user_id=created_by
        )
        
        # Persist using the service
        example_id = await user_example_service.persist_user_example(user_example, data.project_id)
        
        # Get the created example
        example = await user_example_service.get_user_example_by_id(example_id)
        
        return ExampleRead.model_validate(example)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create example: {str(e)}")


@router.get(
    "/examples/{example_id}", response_model=ExampleRead, summary="Retrieve an example."
)
async def read(
    example_id: str, 
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Retrieve an example by its unique ID."""
    # Initialize services
    session_manager = get_session_manager()
    project_manager = ProjectManager(None)  # Pass None since we're using async sessions
    factory = PersistenceServiceFactory(session_manager, project_manager)
    user_example_service = factory.get_user_example_service()
    
    example = await user_example_service.get_user_example_by_id(example_id)
    if not example:
        raise HTTPException(status_code=404, detail="Example not found.")
    return ExampleRead.model_validate(example)


@router.patch(
    "/examples/{example_id}", response_model=ExampleRead, summary="Update an example."
)
async def update(
    example_id: str, 
    data: ExampleUpdate, 
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Partially update an example's details."""
    try:
        # TODO: Get actual user from authentication
        modified_by = user_id  # Use the user_id from dependency
        
        # Initialize services
        session_manager = get_session_manager()
        project_manager = ProjectManager(None)  # Pass None since we're using async sessions
        factory = PersistenceServiceFactory(session_manager, project_manager)
        user_example_service = factory.get_user_example_service()
        
        # Get the example by ID
        example = await user_example_service.get_user_example_by_id(example_id)
        
        if not example:
            raise HTTPException(status_code=404, detail="Example not found.")
        
        # Prepare updates
        updates = {}
        if data.question is not None:
            updates['question'] = data.question
        if data.sql_query is not None:
            updates['sql_query'] = data.sql_query
        if data.context is not None:
            updates['context'] = data.context
        if data.document_reference is not None:
            updates['document_reference'] = data.document_reference
        if data.instructions is not None:
            updates['instructions'] = data.instructions
        if data.categories is not None:
            updates['categories'] = data.categories
        if data.samples is not None:
            updates['samples'] = data.samples
        if data.json_metadata is not None:
            updates['json_metadata'] = data.json_metadata
        
        # Update using the service
        updated_example = await user_example_service.update_user_example(example_id, updates, modified_by)
        
        return ExampleRead.model_validate(updated_example)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update example: {str(e)}")


@router.delete("/examples/{example_id}", summary="Delete an example.")
async def delete(
    example_id: str, 
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Remove an example from the database."""
    # Initialize services
    session_manager = get_session_manager()
    project_manager = ProjectManager(None)  # Pass None since we're using async sessions
    factory = PersistenceServiceFactory(session_manager, project_manager)
    user_example_service = factory.get_user_example_service()
    
    if not await user_example_service.delete_user_example(example_id):
        raise HTTPException(status_code=404, detail="Example not found.")
    return {"message": "Example deleted successfully"}


@router.get("/examples/", response_model=List[ExampleRead], summary="List examples.")
async def list_all(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    definition_type: Optional[DefinitionType] = Query(None, description="Filter by definition type"),
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """List examples with optional filtering."""
    # Initialize services
    session_manager = get_session_manager()
    project_manager = ProjectManager(None)  # Pass None since we're using async sessions
    factory = PersistenceServiceFactory(session_manager, project_manager)
    user_example_service = factory.get_user_example_service()
    
    # Get examples
    if project_id:
        examples = await user_example_service.get_user_examples(project_id, definition_type)
    else:
        examples = await user_example_service.get_user_examples("", definition_type)
    
    return [ExampleRead.model_validate(example) for example in examples]


# ============================================================================
# USER EXAMPLE ENDPOINTS
# ============================================================================

@router.post("/user-examples/", response_model=UserExampleRead, summary="Create a new user example.")
async def create_user(
    data: UserExampleCreate, 
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Create a new user example within a project."""
    try:
        # TODO: Get actual user from authentication
        created_by = data.user_id or user_id  # Use provided user_id or default
        
        # Initialize services
        session_manager = get_session_manager()
        project_manager = ProjectManager(None)  # Pass None since we're using async sessions
        factory = PersistenceServiceFactory(session_manager, project_manager)
        user_example_service = factory.get_user_example_service()
        
        # Convert to UserExample
        user_example = UserExample(
            definition_type=data.definition_type,
            name=data.name,
            description=data.description,
            sql=data.sql,
            additional_context=data.additional_context,
            user_id=data.user_id or created_by
        )
        
        # Persist using the service
        example_id = await user_example_service.persist_user_example(user_example, data.project_id)
        
        # Get the created example
        example = await user_example_service.get_user_example_by_id(example_id)
        
        return UserExampleRead.model_validate(example)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create user example: {str(e)}")


@router.get(
    "/user-examples/{example_id}", response_model=UserExampleRead, summary="Retrieve a user example."
)
async def read_user(
    example_id: str, 
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Retrieve a user example by its unique ID."""
    # Initialize services
    session_manager = get_session_manager()
    project_manager = ProjectManager(None)  # Pass None since we're using async sessions
    factory = PersistenceServiceFactory(session_manager, project_manager)
    user_example_service = factory.get_user_example_service()
    
    example = await user_example_service.get_user_example_by_id(example_id)
    if not example:
        raise HTTPException(status_code=404, detail="User example not found.")
    return UserExampleRead.model_validate(example)


@router.patch(
    "/user-examples/{example_id}", response_model=UserExampleRead, summary="Update a user example."
)
async def update_user(
    example_id: str, 
    data: UserExampleUpdate, 
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Partially update a user example's details."""
    try:
        # TODO: Get actual user from authentication
        modified_by = user_id  # Use the user_id from dependency
        
        # Initialize services
        session_manager = get_session_manager()
        project_manager = ProjectManager(None)  # Pass None since we're using async sessions
        factory = PersistenceServiceFactory(session_manager, project_manager)
        user_example_service = factory.get_user_example_service()
        
        # Prepare updates
        updates = {}
        if data.definition_type is not None:
            updates['categories'] = [data.definition_type.value]
        if data.name is not None:
            updates['question'] = data.name  # Map name to question field
        if data.description is not None:
            updates['sql_query'] = data.description  # Map description to sql_query field
        if data.sql is not None:
            updates['sql_query'] = data.sql
        if data.additional_context is not None:
            updates['json_metadata'] = data.additional_context
        
        # Update using the service
        updated_example = await user_example_service.update_user_example(example_id, updates, modified_by)
        
        return UserExampleRead.model_validate(updated_example)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update user example: {str(e)}")


@router.delete("/user-examples/{example_id}", summary="Delete a user example.")
async def delete_user(
    example_id: str, 
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Remove a user example from the database."""
    # Initialize services
    session_manager = get_session_manager()
    project_manager = ProjectManager(None)  # Pass None since we're using async sessions
    factory = PersistenceServiceFactory(session_manager, project_manager)
    user_example_service = factory.get_user_example_service()
    
    if not await user_example_service.delete_user_example(example_id):
        raise HTTPException(status_code=404, detail="User example not found.")
    return {"message": "User example deleted successfully"}


@router.get("/user-examples/", response_model=List[UserExampleRead], summary="List user examples.")
async def list_all_users(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    definition_type: Optional[DefinitionType] = Query(None, description="Filter by definition type"),
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """List user examples with optional filtering."""
    # Initialize services
    session_manager = get_session_manager()
    project_manager = ProjectManager(None)  # Pass None since we're using async sessions
    factory = PersistenceServiceFactory(session_manager, project_manager)
    user_example_service = factory.get_user_example_service()
    
    # Get examples
    if project_id:
        examples = await user_example_service.get_user_examples(project_id, definition_type)
    else:
        examples = await user_example_service.get_user_examples("", definition_type)
    
    return [UserExampleRead.model_validate(example) for example in examples]

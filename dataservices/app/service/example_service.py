"""
Example service for managing examples and user examples
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from app.service.models import (
    ExampleCreate, ExampleUpdate, ExampleRead, 
    UserExampleCreate, UserExampleUpdate, UserExampleRead,
    DefinitionType, UserExample
)
from app.service.persistence_service import PersistenceServiceFactory
from app.utils.history import DomainManager
from app.schemas.dbmodels import Example
from app.core.dependencies import get_persistence_factory


# ============================================================================
# ASYNC SERVICE FUNCTIONS
# ============================================================================

async def create_example(example_data: ExampleCreate, 
                        factory: PersistenceServiceFactory) -> ExampleRead:
    """Create an example using persistence service."""
    user_example_service = factory.get_user_example_service()
    
    # Convert ExampleCreate to UserExample
    user_example = UserExample(
        definition_type=DefinitionType.METRIC,  # Default, can be made configurable
        name=example_data.question[:50],  # Truncate for name
        description=example_data.question,
        sql=example_data.sql_query,
        additional_context={
            'context': example_data.context,
            'document_reference': example_data.document_reference,
            'instructions': example_data.instructions,
            'samples': example_data.samples
        },
        user_id='system'
    )
    
    # Persist using async service
    example_id = await user_example_service.persist_user_example(user_example, example_data.domain_id)
    
    # Get the created example
    example = await user_example_service.get_user_example_by_id(example_id)
    
    if example:
        return ExampleRead.model_validate(example)
    else:
        raise Exception("Failed to create example")


async def get_example(example_id: str, 
                     factory: PersistenceServiceFactory) -> Optional[ExampleRead]:
    """Retrieve an example by its ID using persistence service."""
    user_example_service = factory.get_user_example_service()
    
    # Get example by ID directly
    example = await user_example_service.get_user_example_by_id(example_id)
    
    if example:
        return ExampleRead.model_validate(example)
    return None


async def update_example(example_id: str, example_data: ExampleUpdate, 
                        factory: PersistenceServiceFactory) -> Optional[ExampleRead]:
    """Update an example using persistence service."""
    user_example_service = factory.get_user_example_service()
    
    # Convert ExampleUpdate to dict
    updates = {}
    if example_data.question is not None:
        updates['question'] = example_data.question
    if example_data.sql_query is not None:
        updates['sql_query'] = example_data.sql_query
    if example_data.context is not None:
        updates['context'] = example_data.context
    if example_data.document_reference is not None:
        updates['document_reference'] = example_data.document_reference
    if example_data.instructions is not None:
        updates['instructions'] = example_data.instructions
    if example_data.categories is not None:
        updates['categories'] = example_data.categories
    if example_data.samples is not None:
        updates['samples'] = example_data.samples
    if example_data.metadata is not None:
        updates['json_metadata'] = example_data.metadata
    
    # Update using the service
    example = await user_example_service.update_user_example(example_id, updates, 'system')
    
    if example:
        return ExampleRead.model_validate(example)
    return None


async def delete_example(example_id: str, 
                        factory: PersistenceServiceFactory) -> bool:
    """Delete an example using persistence service."""
    user_example_service = factory.get_user_example_service()
    
    # Delete using the service
    return await user_example_service.delete_user_example(example_id)


async def list_examples(factory: PersistenceServiceFactory,
                       domain_id: Optional[str] = None, 
                       definition_type: Optional[DefinitionType] = None) -> List[ExampleRead]:
    """List examples using persistence service."""
    user_example_service = factory.get_user_example_service()
    
    # Get examples
    if domain_id:
        examples = await user_example_service.get_user_examples(domain_id, definition_type)
    else:
        examples = await user_example_service.get_user_examples("", definition_type)
    
    return [ExampleRead.model_validate(example) for example in examples]


# ============================================================================
# USER EXAMPLE FUNCTIONS
# ============================================================================

async def create_user_example(user_example_data: UserExampleCreate, 
                            factory: PersistenceServiceFactory) -> UserExampleRead:
    """Create a user example using persistence service."""
    user_example_service = factory.get_user_example_service()
    
    # Convert UserExampleCreate to UserExample
    user_example = UserExample(
        definition_type=user_example_data.definition_type,
        name=user_example_data.name,
        description=user_example_data.description,
        sql=user_example_data.sql,
        additional_context=user_example_data.additional_context,
        user_id=user_example_data.user_id
    )
    
    # Persist using async service
    example_id = await user_example_service.persist_user_example(user_example, user_example_data.domain_id)
    
    # Get the created example
    example = await user_example_service.get_user_example_by_id(example_id)
    
    if example:
        return UserExampleRead.model_validate(example)
    else:
        raise Exception("Failed to create user example")


async def get_user_example(example_id: str, 
                         factory: PersistenceServiceFactory) -> Optional[UserExampleRead]:
    """Get a user example by ID using persistence service."""
    user_example_service = factory.get_user_example_service()
    
    # Get example by ID directly
    example = await user_example_service.get_user_example_by_id(example_id)
    
    if example:
        return UserExampleRead.model_validate(example)
    return None


async def update_user_example(example_id: str, user_example_data: UserExampleUpdate, 
                            factory: PersistenceServiceFactory) -> Optional[UserExampleRead]:
    """Update a user example using persistence service."""
    user_example_service = factory.get_user_example_service()
    
    # Convert UserExampleUpdate to dict
    updates = {}
    if user_example_data.definition_type is not None:
        updates['categories'] = [user_example_data.definition_type.value]
    if user_example_data.name is not None:
        updates['json_metadata'] = {'original_name': user_example_data.name}
    if user_example_data.description is not None:
        updates['question'] = user_example_data.description
    if user_example_data.sql is not None:
        updates['sql_query'] = user_example_data.sql
    if user_example_data.additional_context is not None:
        updates['json_metadata'] = {'additional_context': user_example_data.additional_context}
    
    # Update using the service
    example = await user_example_service.update_user_example(example_id, updates, 'system')
    
    if example:
        return UserExampleRead.model_validate(example)
    return None


async def delete_user_example(example_id: str, 
                            factory: PersistenceServiceFactory) -> bool:
    """Delete a user example using persistence service."""
    user_example_service = factory.get_user_example_service()
    
    # Delete using the service
    return await user_example_service.delete_user_example(example_id)


async def list_user_examples(factory: PersistenceServiceFactory,
                           domain_id: Optional[str] = None, 
                           definition_type: Optional[DefinitionType] = None) -> List[UserExampleRead]:
    """List user examples using persistence service."""
    user_example_service = factory.get_user_example_service()
    
    # Get examples
    if domain_id:
        examples = await user_example_service.get_user_examples(domain_id, definition_type)
    else:
        examples = await user_example_service.get_user_examples("", definition_type)
    
    return [UserExampleRead.model_validate(example) for example in examples] 
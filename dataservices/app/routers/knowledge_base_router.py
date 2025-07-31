from fastapi import APIRouter, HTTPException, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from app.core.dependencies import get_async_db_session, get_session_manager
from app.service.persistence_service import PersistenceServiceFactory
from app.utils.history import DomainManager
from app.service.models import (
    KnowledgeBaseCreate, KnowledgeBaseUpdate, KnowledgeBaseRead
)

router = APIRouter()

def get_session_id(request: Request):
    return request.headers.get("X-Session-Id") or "demo-session"

def get_user_id(request: Request):
    return request.headers.get("X-User-Id") or "demo-user"


@router.post(
    "/knowledge-bases/",
    response_model=KnowledgeBaseRead,
    summary="Create a new knowledge base entry.",
)
async def create(
    data: KnowledgeBaseCreate, 
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Create a new knowledge base entry within a domain."""
    try:
        # TODO: Get actual user from authentication
        created_by = user_id  # Use the user_id from dependency
        
        # Initialize services
        session_manager = get_session_manager()
        domain_manager = DomainManager(None)  # Pass None since we're using async sessions
        factory = PersistenceServiceFactory(session_manager, domain_manager)
        kb_service = factory.get_knowledge_base_service()
        
        # Convert to dict format expected by the service
        kb_data = {
            'domain_id': data.domain_id,
            'content_type': data.content_type,
            'title': data.title,
            'content': data.content,
            'metadata': data.json_metadata or {}
        }
        
        kb_id = await kb_service.persist_knowledge_base_entry(kb_data, data.domain_id, created_by)
        kb_entry = await kb_service.get_knowledge_base_by_id(kb_id)
        
        return KnowledgeBaseRead.model_validate(kb_entry)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create knowledge base entry: {str(e)}")


@router.get(
    "/knowledge-bases/{kb_id}",
    response_model=KnowledgeBaseRead,
    summary="Retrieve a knowledge base entry.",
)
async def read(
    kb_id: str, 
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Retrieve a knowledge base entry by its unique ID."""
    # Initialize services
    session_manager = get_session_manager()
    domain_manager = DomainManager(None)  # Pass None since we're using async sessions
    factory = PersistenceServiceFactory(session_manager, domain_manager)
    kb_service = factory.get_knowledge_base_service()
    
    kb_entry = await kb_service.get_knowledge_base_by_id(kb_id)
    if not kb_entry:
        raise HTTPException(status_code=404, detail="Knowledge base entry not found.")
    return KnowledgeBaseRead.model_validate(kb_entry)


@router.patch(
    "/knowledge-bases/{kb_id}",
    response_model=KnowledgeBaseRead,
    summary="Update a knowledge base entry.",
)
async def update(
    kb_id: str, 
    data: KnowledgeBaseUpdate, 
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Partially update a knowledge base entry's details."""
    try:
        # TODO: Get actual user from authentication
        modified_by = user_id  # Use the user_id from dependency
        
        # Initialize services
        session_manager = get_session_manager()
        domain_manager = DomainManager(None)  # Pass None since we're using async sessions
        factory = PersistenceServiceFactory(session_manager, domain_manager)
        kb_service = factory.get_knowledge_base_service()
        
        # Prepare updates
        updates = {}
        if data.content_type is not None:
            updates['content_type'] = data.content_type
        if data.title is not None:
            updates['title'] = data.title
        if data.content is not None:
            updates['content'] = data.content
        if data.json_metadata is not None:
            updates['metadata'] = data.json_metadata
        
        updated_kb = await kb_service.update_knowledge_base_entry(kb_id, updates, modified_by)
        if not updated_kb:
            raise HTTPException(status_code=404, detail="Knowledge base entry not found.")
        return KnowledgeBaseRead.model_validate(updated_kb)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update knowledge base entry: {str(e)}")


@router.delete("/knowledge-bases/{kb_id}", summary="Delete a knowledge base entry.")
async def delete(
    kb_id: str, 
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Remove a knowledge base entry from the database."""
    # Initialize services
    session_manager = get_session_manager()
    domain_manager = DomainManager(None)  # Pass None since we're using async sessions
    factory = PersistenceServiceFactory(session_manager, domain_manager)
    kb_service = factory.get_knowledge_base_service()
    
    if not await kb_service.delete_knowledge_base_entry(kb_id):
        raise HTTPException(status_code=404, detail="Knowledge base entry not found.")
    return {"message": "Knowledge base entry deleted successfully"}


@router.get("/knowledge-bases/", response_model=List[KnowledgeBaseRead], summary="List knowledge base entries.")
async def list_all(
    domain_id: Optional[str] = Query(None, description="Filter by domain ID"),
    content_type: Optional[str] = Query(None, description="Filter by content type"),
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """List knowledge base entries with optional filtering."""
    # Initialize services
    session_manager = get_session_manager()
    domain_manager = DomainManager(None)  # Pass None since we're using async sessions
    factory = PersistenceServiceFactory(session_manager, domain_manager)
    kb_service = factory.get_knowledge_base_service()
    
    if domain_id:
        kb_entries = await kb_service.get_knowledge_base_entries(domain_id, content_type)
    else:
        kb_entries = await kb_service.get_knowledge_base_entries("", content_type)
    
    return [KnowledgeBaseRead.model_validate(kb_entry) for kb_entry in kb_entries]


@router.post("/knowledge-bases/batch/", summary="Create multiple knowledge base entries in batch.")
async def create_batch(
    kb_entries_data: List[Dict[str, Any]],
    domain_id: str = Query(..., description="Domain ID for all knowledge base entries"),
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Create multiple knowledge base entries in batch within a domain."""
    try:
        # TODO: Get actual user from authentication
        created_by = user_id  # Use the user_id from dependency
        
        # Initialize services
        session_manager = get_session_manager()
        domain_manager = DomainManager(None)  # Pass None since we're using async sessions
        factory = PersistenceServiceFactory(session_manager, domain_manager)
        kb_service = factory.get_knowledge_base_service()
        
        kb_ids = await kb_service.persist_knowledge_base_batch(kb_entries_data, domain_id, created_by)
        return {
            "message": f"Successfully created {len(kb_ids)} knowledge base entries",
            "kb_ids": kb_ids
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create knowledge base entries batch: {str(e)}")


@router.get("/knowledge-bases/summary/{domain_id}", summary="Get knowledge base summary for a domain.")
async def get_summary(
    domain_id: str, 
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Get a summary of knowledge base entries for a specific domain."""
    try:
        # Initialize services
        session_manager = get_session_manager()
        domain_manager = DomainManager(None)  # Pass None since we're using async sessions
        factory = PersistenceServiceFactory(session_manager, domain_manager)
        kb_service = factory.get_knowledge_base_service()
        
        summary = await kb_service.get_knowledge_base_summary(domain_id)
        return summary
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get knowledge base summary: {str(e)}")


@router.get("/knowledge-bases/search/", response_model=List[KnowledgeBaseRead], summary="Search knowledge base entries.")
async def search(
    domain_id: str = Query(..., description="Domain ID"),
    search_term: str = Query(..., description="Search term for content"),
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Search knowledge base entries by content."""
    try:
        # Initialize services
        session_manager = get_session_manager()
        domain_manager = DomainManager(None)  # Pass None since we're using async sessions
        factory = PersistenceServiceFactory(session_manager, domain_manager)
        kb_service = factory.get_knowledge_base_service()
        
        kb_entries = await kb_service.search_knowledge_base(domain_id, search_term)
        return [KnowledgeBaseRead.model_validate(kb_entry) for kb_entry in kb_entries]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to search knowledge base entries: {str(e)}")


@router.get("/knowledge-bases/content-type/{content_type}", response_model=List[KnowledgeBaseRead], summary="Get knowledge base entries by content type.")
async def get_by_content_type(
    content_type: str,
    domain_id: str = Query(..., description="Domain ID"),
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Get knowledge base entries by content type."""
    try:
        # Initialize services
        session_manager = get_session_manager()
        domain_manager = DomainManager(None)  # Pass None since we're using async sessions
        factory = PersistenceServiceFactory(session_manager, domain_manager)
        kb_service = factory.get_knowledge_base_service()
        
        kb_entries = await kb_service.get_knowledge_base_entries(domain_id, content_type)
        return [KnowledgeBaseRead.model_validate(kb_entry) for kb_entry in kb_entries]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get knowledge base entries by content type: {str(e)}")


@router.get("/knowledge-bases/domain/{domain_id}/content-types", summary="Get available content types for a domain.")
async def get_content_types(
    domain_id: str, 
    session_id: str = Depends(get_session_id),
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_async_db_session)
):
    """Get all available content types for a domain."""
    try:
        # Initialize services
        session_manager = get_session_manager()
        domain_manager = DomainManager(None)  # Pass None since we're using async sessions
        factory = PersistenceServiceFactory(session_manager, domain_manager)
        kb_service = factory.get_knowledge_base_service()
        
        # Get all knowledge base entries for the domain
        kb_entries = await kb_service.get_knowledge_base_entries(domain_id)
        
        # Extract unique content types
        content_types = set()
        for kb_entry in kb_entries:
            if kb_entry.content_type:
                content_types.add(kb_entry.content_type)
        
        return {
            "domain_id": domain_id,
            "content_types": list(content_types),
            "total_entries": len(kb_entries)
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get content types: {str(e)}")

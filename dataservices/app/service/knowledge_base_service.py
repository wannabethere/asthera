"""
Knowledge base service using the new persistence services
"""

from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from app.service.persistence_service import PersistenceServiceFactory
from app.service.models import (
    KnowledgeBaseCreate, KnowledgeBaseUpdate, KnowledgeBaseRead
)
from app.utils.history import ProjectManager
from app.schemas.dbmodels import KnowledgeBase


def create_knowledge_base(db: Session, data: KnowledgeBaseCreate, created_by: str) -> KnowledgeBaseRead:
    """Create a new knowledge base entry using persistence service."""
    # Initialize services
    project_manager = ProjectManager(db)
    factory = PersistenceServiceFactory(db, project_manager)
    kb_service = factory.get_knowledge_base_service()
    
    # Convert to knowledge base data format
    kb_data = {
        'name': data.name,
        'display_name': data.display_name,
        'description': data.description,
        'file_path': data.file_path,
        'content_type': data.content_type,
        'content': data.content,
        'metadata': data.metadata or {}
    }
    
    # Persist using the service
    kb_id = kb_service.persist_knowledge_base_entry(kb_data, data.project_id, created_by)
    
    # Get the created knowledge base entry
    kb_entry = kb_service.get_knowledge_base_by_id(kb_id)
    
    return KnowledgeBaseRead.model_validate(kb_entry)


def get_knowledge_base(db: Session, kb_id: str) -> Optional[KnowledgeBaseRead]:
    """Retrieve a knowledge base entry by its ID using persistence service."""
    # Initialize services
    project_manager = ProjectManager(db)
    factory = PersistenceServiceFactory(db, project_manager)
    kb_service = factory.get_knowledge_base_service()
    
    # Get knowledge base entry by ID directly
    kb_entry = kb_service.get_knowledge_base_by_id(kb_id)
    
    if kb_entry:
        return KnowledgeBaseRead.model_validate(kb_entry)
    return None


def update_knowledge_base(db: Session, kb_id: str, data: KnowledgeBaseUpdate, modified_by: str) -> Optional[KnowledgeBaseRead]:
    """Update a knowledge base entry using persistence service."""
    # Initialize services
    project_manager = ProjectManager(db)
    factory = PersistenceServiceFactory(db, project_manager)
    kb_service = factory.get_knowledge_base_service()
    
    # Get the knowledge base entry by ID
    kb_entry = kb_service.get_knowledge_base_by_id(kb_id)
    
    if not kb_entry:
        return None
    
    # Prepare updates
    updates = {}
    if data.name is not None:
        updates['name'] = data.name
    if data.display_name is not None:
        updates['display_name'] = data.display_name
    if data.description is not None:
        updates['description'] = data.description
    if data.file_path is not None:
        updates['file_path'] = data.file_path
    if data.content_type is not None:
        updates['content_type'] = data.content_type
    if data.content is not None:
        updates['content'] = data.content
    if data.metadata is not None:
        updates['metadata'] = data.metadata
    
    # Update using the service
    updated_kb_entry = kb_service.update_knowledge_base_entry(kb_id, updates, modified_by)
    
    return KnowledgeBaseRead.model_validate(updated_kb_entry)


def delete_knowledge_base(db: Session, kb_id: str) -> bool:
    """Delete a knowledge base entry using persistence service."""
    # Initialize services
    project_manager = ProjectManager(db)
    factory = PersistenceServiceFactory(db, project_manager)
    kb_service = factory.get_knowledge_base_service()
    
    # Delete using the service
    return kb_service.delete_knowledge_base_entry(kb_id)


def list_knowledge_bases(db: Session, project_id: Optional[str] = None, 
                        content_type: Optional[str] = None) -> List[KnowledgeBaseRead]:
    """List knowledge base entries using persistence service."""
    # Initialize services
    project_manager = ProjectManager(db)
    factory = PersistenceServiceFactory(db, project_manager)
    kb_service = factory.get_knowledge_base_service()
    
    # Get knowledge base entries
    if project_id:
        kb_entries = kb_service.get_knowledge_base_entries(project_id, content_type)
    else:
        # Get all knowledge base entries (not recommended for large datasets)
        kb_entries = kb_service.get_knowledge_base_entries("", content_type)
    
    return [KnowledgeBaseRead.model_validate(kb_entry) for kb_entry in kb_entries]


def create_knowledge_bases_batch(db: Session, kb_entries_data: List[Dict[str, Any]], 
                               project_id: str, created_by: str) -> List[str]:
    """Create multiple knowledge base entries in batch using persistence service."""
    # Initialize services
    project_manager = ProjectManager(db)
    factory = PersistenceServiceFactory(db, project_manager)
    kb_service = factory.get_knowledge_base_service()
    
    # Persist using the service
    kb_ids = kb_service.persist_knowledge_base_batch(kb_entries_data, project_id, created_by)
    
    return kb_ids


def search_knowledge_bases(db: Session, project_id: str, search_term: str) -> List[KnowledgeBaseRead]:
    """Search knowledge base entries by content using persistence service."""
    # Initialize services
    project_manager = ProjectManager(db)
    factory = PersistenceServiceFactory(db, project_manager)
    kb_service = factory.get_knowledge_base_service()
    
    # Search using the service
    kb_entries = kb_service.search_knowledge_base(project_id, search_term)
    
    return [KnowledgeBaseRead.model_validate(kb_entry) for kb_entry in kb_entries]


def get_knowledge_base_summary(db: Session, project_id: str) -> Dict[str, Any]:
    """Get summary of knowledge base entries for a project using persistence service."""
    # Initialize services
    project_manager = ProjectManager(db)
    factory = PersistenceServiceFactory(db, project_manager)
    kb_service = factory.get_knowledge_base_service()
    
    # Get summary using the service
    summary = kb_service.get_knowledge_base_summary(project_id)
    
    return summary


def get_knowledge_base_by_content_type(db: Session, project_id: str, content_type: str) -> List[KnowledgeBaseRead]:
    """Get knowledge base entries by content type using persistence service."""
    # Initialize services
    project_manager = ProjectManager(db)
    factory = PersistenceServiceFactory(db, project_manager)
    kb_service = factory.get_knowledge_base_service()
    
    # Get knowledge base entries by content type
    kb_entries = kb_service.get_knowledge_base_entries(project_id, content_type)
    
    return [KnowledgeBaseRead.model_validate(kb_entry) for kb_entry in kb_entries] 
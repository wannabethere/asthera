import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column, String, Text, Integer, Boolean, DateTime, ForeignKey,
    CheckConstraint, UniqueConstraint, Index, event
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session, validates
from sqlalchemy.sql import func
from sqlalchemy.ext.hybrid import hybrid_property
from app.schemas.dbmodels import Base, TimestampMixin, Domain, Table, Column, DomainVersionHistory


# ============================================================================
# UTILITY CLASSES AND MANAGERS
# ============================================================================

class DomainManager:
    """Utility class for domain management operations"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create_domain(self, domain_id: str, display_name: str, description: str = None, 
                      created_by: str = 'system') -> Domain:
        """Create a new domain"""
        domain = Domain(
            domain_id=domain_id,
            display_name=display_name,
            description=description,
            created_by=created_by,
            last_modified_by=created_by
        )
        self.session.add(domain)
        self.session.commit()
        return domain
    
    def lock_domain_version(self, domain_id: str, locked: bool = True, 
                           modified_by: str = 'system') -> bool:
        """Lock or unlock domain version"""
        domain = self.session.query(Domain).filter(Domain.domain_id == domain_id).first()
        if not domain:
            return False
        
        domain.lock_version(locked)
        domain.last_modified_by = modified_by
        self.session.commit()
        return True
    
    def manual_version_increment(self, domain_id: str, change_type: str, 
                               modified_by: str, description: str) -> Optional[str]:
        """Manually increment domain version"""
        domain = self.session.query(Domain).filter(Domain.domain_id == domain_id).first()
        if not domain:
            return None
        
        old_version = domain.version_string
        new_version = domain.increment_version(
            change_type=change_type,
            entity_type='manual',
            entity_id=None,
            modified_by=modified_by
        )
        
        # Create version history
        version_history = DomainVersionHistory(
            domain_id=domain_id,
            old_version=old_version,
            new_version=new_version,
            change_type=change_type,
            triggered_by_entity='manual',
            triggered_by_user=modified_by,
            change_description=description
        )
        self.session.add(version_history)
        self.session.commit()
        
        return new_version
    
    def get_domain_summary(self, domain_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive domain summary"""
        domain = self.session.query(Domain).filter(Domain.domain_id == domain_id).first()
        if not domain:
            return None
        
        return {
            'domain_id': domain.domain_id,
            'display_name': domain.display_name,
            'current_version': domain.version_string,
            'version_locked': domain.version_locked,
            'last_modified_by': domain.last_modified_by,
            'last_modified_entity': domain.last_modified_entity,
            'status': domain.status,
            'total_datasets': len(domain.datasets),
            'total_tables': len(domain.tables),
            'total_instructions': len(domain.instructions),
            'total_examples': len(domain.examples),
            'total_knowledge_base': len(domain.knowledge_base),
            'version_changes': len(domain.version_history),
            'created_at': domain.created_at,
            'updated_at': domain.updated_at
        }
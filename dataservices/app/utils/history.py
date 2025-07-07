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
from app.schemas.dbmodels import Base, TimestampMixin, Project, Table, Column, ProjectVersionHistory


# ============================================================================
# UTILITY CLASSES AND MANAGERS
# ============================================================================

class ProjectManager:
    """Utility class for project management operations"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create_project(self, project_id: str, display_name: str, description: str = None, 
                      created_by: str = 'system') -> Project:
        """Create a new project"""
        project = Project(
            project_id=project_id,
            display_name=display_name,
            description=description,
            created_by=created_by,
            last_modified_by=created_by
        )
        self.session.add(project)
        self.session.commit()
        return project
    
    def lock_project_version(self, project_id: str, locked: bool = True, 
                           modified_by: str = 'system') -> bool:
        """Lock or unlock project version"""
        project = self.session.query(Project).filter(Project.project_id == project_id).first()
        if not project:
            return False
        
        project.lock_version(locked)
        project.last_modified_by = modified_by
        self.session.commit()
        return True
    
    def manual_version_increment(self, project_id: str, change_type: str, 
                               modified_by: str, description: str) -> Optional[str]:
        """Manually increment project version"""
        project = self.session.query(Project).filter(Project.project_id == project_id).first()
        if not project:
            return None
        
        old_version = project.version_string
        new_version = project.increment_version(
            change_type=change_type,
            entity_type='manual',
            entity_id=None,
            modified_by=modified_by
        )
        
        # Create version history
        version_history = ProjectVersionHistory(
            project_id=project_id,
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
    
    def get_project_summary(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive project summary"""
        project = self.session.query(Project).filter(Project.project_id == project_id).first()
        if not project:
            return None
        
        return {
            'project_id': project.project_id,
            'display_name': project.display_name,
            'current_version': project.version_string,
            'version_locked': project.version_locked,
            'last_modified_by': project.last_modified_by,
            'last_modified_entity': project.last_modified_entity,
            'status': project.status,
            'total_datasets': len(project.datasets),
            'total_tables': len(project.tables),
            'total_instructions': len(project.instructions),
            'total_examples': len(project.examples),
            'total_knowledge_base': len(project.knowledge_base),
            'version_changes': len(project.version_history),
            'created_at': project.created_at,
            'updated_at': project.updated_at
        }
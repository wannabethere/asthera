from sqlalchemy.orm import Session  
from app.service.dbmodels import Project
from app.service.models import CreateProjectRequest
from typing import Optional,Dict,Any



class ProjectManager:
    """Utility class for project management operations"""
    
    def __init__(self, session: Session):
        self.session = session
    
    # In dbmodels.py, inside the ProjectManager class
    def create_project(self, project_data: CreateProjectRequest) -> Project:
        """Create a new project"""
        new_project = Project(
            project_id=project_data.project_id,
            display_name=project_data.display_name,
            description=project_data.description,
            created_by=project_data.created_by if project_data.created_by else 'system',
            last_modified_by=project_data.created_by if project_data.created_by else 'system'
            
        )
        self.session.add(new_project)
        self.session.commit()
        self.session.refresh(new_project) 
        
        return new_project
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
        print("Project ID: ", project_id)
        project = self.session.query(Project).filter(Project.project_id == project_id).first()
        print("Project: ", project)
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

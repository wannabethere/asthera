from typing import Optional, List, Dict, Any, Union
from uuid import UUID
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import chromadb
from app.core.settings import get_settings
import json
from enum import Enum

settings = get_settings()

class SharingPermission(Enum):
    PRIVATE = "private"
    USER = "user"
    TEAM = "team"
    WORKSPACE = "workspace"
    DEFAULT = "default"

class BaseService:
    """Base service class with common functionality for all services"""
    
    def __init__(self, db: Session, chroma_client: chromadb.Client = None):
        self.db = db
        self.chroma_client = chroma_client or chromadb.Client(Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory="./chroma_db"
        ))
        
    def _check_user_permission(
        self, 
        user_id: UUID, 
        resource_type: str, 
        resource_id: UUID, 
        action: str
    ) -> bool:
        """Check if user has permission to perform action on resource"""
        from app.models.rbac import Role, Permission, user_roles
        
        # Check system roles first (superuser, system_admin)
        user_system_roles = self.db.query(Role).join(user_roles).filter(
            and_(
                user_roles.c.user_id == user_id,
                Role.role_type == "system",
                Role.name.in_(["superuser", "system_admin"])
            )
        ).all()
        
        if user_system_roles:
            return True
            
        # Check resource-specific permissions
        permission_query = self.db.query(Permission).join(
            Role.permissions
        ).join(
            user_roles,
            Role.id == user_roles.c.role_id
        ).filter(
            and_(
                user_roles.c.user_id == user_id,
                or_(
                    user_roles.c.object_id == resource_id,
                    user_roles.c.object_id.is_(None)  # Global permissions
                ),
                Permission.resource_type == resource_type,
                Permission.action == action
            )
        )
        
        return permission_query.first() is not None
    
    def _get_user_accessible_resources(
        self,
        user_id: UUID,
        resource_type: str,
        workspace_id: Optional[UUID] = None,
        project_id: Optional[UUID] = None
    ) -> List[UUID]:
        """Get list of resource IDs user has access to"""
        from app.models.workspace import WorkspaceAccess, ProjectAccess
        from app.models.team import team_memberships
        
        accessible_ids = []
        
        # Get workspace access
        if workspace_id:
            workspace_access = self.db.query(WorkspaceAccess).filter(
                and_(
                    WorkspaceAccess.workspace_id == workspace_id,
                    WorkspaceAccess.user_id == user_id
                )
            ).first()
            if workspace_access:
                accessible_ids.append(workspace_id)
        
        # Get project access
        if project_id:
            project_access = self.db.query(ProjectAccess).filter(
                and_(
                    ProjectAccess.project_id == project_id,
                    ProjectAccess.user_id == user_id
                )
            ).first()
            if project_access:
                accessible_ids.append(project_id)
        
        # Get team-based access
        user_teams = self.db.query(team_memberships.c.team_id).filter(
            team_memberships.c.user_id == user_id
        ).all()
        accessible_ids.extend([team_id for (team_id,) in user_teams])
        
        return accessible_ids
    
    def _create_chroma_collection(self, collection_name: str):
        """Create or get ChromaDB collection"""
        try:
            collection = self.chroma_client.get_collection(collection_name)
        except:
            collection = self.chroma_client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        return collection
    
    def _add_to_chroma(
        self,
        collection_name: str,
        document_id: str,
        content: Dict[str, Any],
        metadata: Dict[str, Any]
    ):
        """Add document to ChromaDB collection"""
        collection = self._create_chroma_collection(collection_name)
        
        # Convert content to searchable text
        text_content = json.dumps(content, default=str)
        
        collection.add(
            documents=[text_content],
            ids=[document_id],
            metadatas=[metadata]
        )
    
    def _update_chroma(
        self,
        collection_name: str,
        document_id: str,
        content: Dict[str, Any],
        metadata: Dict[str, Any]
    ):
        """Update document in ChromaDB collection"""
        collection = self._create_chroma_collection(collection_name)
        
        # Convert content to searchable text
        text_content = json.dumps(content, default=str)
        
        collection.update(
            documents=[text_content],
            ids=[document_id],
            metadatas=[metadata]
        )
    
    def _delete_from_chroma(self, collection_name: str, document_id: str):
        """Delete document from ChromaDB collection"""
        collection = self._create_chroma_collection(collection_name)
        collection.delete(ids=[document_id])
    
    def _search_chroma(
        self,
        collection_name: str,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search documents in ChromaDB collection"""
        collection = self._create_chroma_collection(collection_name)
        
        where_clause = filters if filters else {}
        
        results = collection.query(
            query_texts=[query],
            n_results=limit,
            where=where_clause
        )
        
        return [{
            "id": results["ids"][0][i],
            "document": results["documents"][0][i] if results["documents"] else None,
            "metadata": results["metadatas"][0][i] if results["metadatas"] else None,
            "distance": results["distances"][0][i] if results["distances"] else None
        } for i in range(len(results["ids"][0]))]
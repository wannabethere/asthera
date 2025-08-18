from typing import Optional, List, Dict, Any, Union
from uuid import UUID
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from app.services.baseservice import BaseService, SharingPermission
from app.models.dbmodels import Dashboard, DashboardVersion
from app.models.thread import Thread, Workflow
from app.models.workspace import Workspace, Project
from app.models.schema import DashboardCreate, DashboardUpdate, DashboardResponse

class DashboardService(BaseService):
    """Service for managing dashboards with workflow integration"""
    
    def __init__(self, db: Session, chroma_client=None):
        super().__init__(db, chroma_client)
        self.collection_name = "dashboards"
    
    def create_dashboard(
        self,
        user_id: UUID,
        dashboard_data: DashboardCreate,
        workflow_id: Optional[UUID] = None,
        project_id: Optional[UUID] = None,
        workspace_id: Optional[UUID] = None,
        sharing_permission: SharingPermission = SharingPermission.PRIVATE,
        shared_with: Optional[List[UUID]] = None
    ) -> Dashboard:
        """Create a new dashboard with optional workflow association"""
        
        # Check permissions if project/workspace specified
        if project_id and not self._check_user_permission(
            user_id, "project", project_id, "create"
        ):
            raise PermissionError("User doesn't have permission to create dashboard in this project")
        
        if workspace_id and not self._check_user_permission(
            user_id, "workspace", workspace_id, "create"
        ):
            raise PermissionError("User doesn't have permission to create dashboard in this workspace")
        
        # Validate workflow exists and user has access
        if workflow_id:
            workflow = self.db.query(Workflow).filter(
                Workflow.id == workflow_id
            ).first()
            if not workflow:
                raise ValueError(f"Workflow {workflow_id} not found")
            if workflow.user_id != user_id and not self._check_user_permission(
                user_id, "thread", workflow.thread_id, "read"
            ):
                raise PermissionError("User doesn't have access to this workflow")
        
        # Create dashboard
        dashboard = Dashboard(
            name=dashboard_data.name,
            description=dashboard_data.description,
            DashboardType=dashboard_data.DashboardType,
            is_active=dashboard_data.is_active,
            content=dashboard_data.content,
            version="1.0"
        )
        
        self.db.add(dashboard)
        self.db.flush()
        
        # Create initial version
        version = DashboardVersion(
            dashboard_id=dashboard.id,
            version="1.0",
            content=dashboard_data.content
        )
        self.db.add(version)
        
        # Store metadata for permissions and associations
        metadata = {
            "created_by": str(user_id),
            "workflow_id": str(workflow_id) if workflow_id else None,
            "project_id": str(project_id) if project_id else None,
            "workspace_id": str(workspace_id) if workspace_id else None,
            "sharing_permission": sharing_permission.value,
            "shared_with": [str(uid) for uid in shared_with] if shared_with else []
        }
        
        # Add to ChromaDB for searchability
        self._add_to_chroma(
            self.collection_name,
            str(dashboard.id),
            {
                "name": dashboard.name,
                "description": dashboard.description,
                "type": dashboard.DashboardType,
                "content": dashboard.content
            },
            metadata
        )
        
        self.db.commit()
        return dashboard
    
    def get_dashboard(
        self,
        user_id: UUID,
        dashboard_id: UUID
    ) -> Optional[Dashboard]:
        """Get dashboard by ID with permission check"""
        
        dashboard = self.db.query(Dashboard).filter(
            Dashboard.id == dashboard_id
        ).first()
        
        if not dashboard:
            return None
        
        # Check permissions via ChromaDB metadata
        collection = self._create_chroma_collection(self.collection_name)
        result = collection.get(ids=[str(dashboard_id)])
        
        if not result["ids"]:
            return None
        
        metadata = result["metadatas"][0]
        
        # Check access permissions
        if not self._has_dashboard_access(user_id, metadata):
            raise PermissionError("User doesn't have access to this dashboard")
        
        return dashboard
    
    def update_dashboard(
        self,
        user_id: UUID,
        dashboard_id: UUID,
        update_data: DashboardUpdate,
        create_version: bool = True
    ) -> Dashboard:
        """Update dashboard with optional versioning"""
        
        dashboard = self.get_dashboard(user_id, dashboard_id)
        if not dashboard:
            raise ValueError(f"Dashboard {dashboard_id} not found")
        
        # Check update permission
        collection = self._create_chroma_collection(self.collection_name)
        result = collection.get(ids=[str(dashboard_id)])
        metadata = result["metadatas"][0]
        
        if metadata["created_by"] != str(user_id) and not self._check_user_permission(
            user_id, "dashboard", dashboard_id, "update"
        ):
            raise PermissionError("User doesn't have permission to update this dashboard")
        
        # Create version before update if requested
        if create_version and update_data.content:
            current_version = float(dashboard.version)
            new_version = str(current_version + 0.1)
            
            version = DashboardVersion(
                dashboard_id=dashboard.id,
                version=new_version,
                content=update_data.content
            )
            self.db.add(version)
            dashboard.version = new_version
        
        # Update dashboard fields
        for field, value in update_data.dict(exclude_unset=True).items():
            setattr(dashboard, field, value)
        
        dashboard.updated_at = datetime.utcnow()
        
        # Update ChromaDB
        self._update_chroma(
            self.collection_name,
            str(dashboard_id),
            {
                "name": dashboard.name,
                "description": dashboard.description,
                "type": dashboard.DashboardType,
                "content": dashboard.content
            },
            metadata
        )
        
        self.db.commit()
        return dashboard
    
    def delete_dashboard(
        self,
        user_id: UUID,
        dashboard_id: UUID
    ) -> bool:
        """Delete dashboard with permission check"""
        
        dashboard = self.get_dashboard(user_id, dashboard_id)
        if not dashboard:
            return False
        
        # Check delete permission
        collection = self._create_chroma_collection(self.collection_name)
        result = collection.get(ids=[str(dashboard_id)])
        metadata = result["metadatas"][0]
        
        if metadata["created_by"] != str(user_id) and not self._check_user_permission(
            user_id, "dashboard", dashboard_id, "delete"
        ):
            raise PermissionError("User doesn't have permission to delete this dashboard")
        
        # Delete from ChromaDB
        self._delete_from_chroma(self.collection_name, str(dashboard_id))
        
        # Delete from PostgreSQL (versions will cascade)
        self.db.delete(dashboard)
        self.db.commit()
        
        return True
    
    def search_dashboards(
        self,
        user_id: UUID,
        query: str,
        workspace_id: Optional[UUID] = None,
        project_id: Optional[UUID] = None,
        workflow_id: Optional[UUID] = None,
        dashboard_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search dashboards with permission filtering"""
        
        # Build filters for ChromaDB search
        filters = {}
        
        if workspace_id:
            filters["workspace_id"] = str(workspace_id)
        if project_id:
            filters["project_id"] = str(project_id)
        if workflow_id:
            filters["workflow_id"] = str(workflow_id)
        if dashboard_type:
            filters["type"] = dashboard_type
        
        # Search in ChromaDB
        results = self._search_chroma(
            self.collection_name,
            query,
            filters,
            limit * 2  # Get more results for permission filtering
        )
        
        # Filter by permissions
        accessible_results = []
        for result in results:
            if self._has_dashboard_access(user_id, result["metadata"]):
                dashboard_id = UUID(result["id"])
                dashboard = self.db.query(Dashboard).filter(
                    Dashboard.id == dashboard_id
                ).first()
                if dashboard:
                    accessible_results.append({
                        "dashboard": dashboard,
                        "metadata": result["metadata"],
                        "relevance_score": 1 - result["distance"] if result["distance"] else 1
                    })
                    if len(accessible_results) >= limit:
                        break
        
        return accessible_results
    
    def list_user_dashboards(
        self,
        user_id: UUID,
        workspace_id: Optional[UUID] = None,
        project_id: Optional[UUID] = None,
        include_shared: bool = True,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """List dashboards accessible to user with pagination"""
        
        # Get all dashboards from ChromaDB with metadata
        collection = self._create_chroma_collection(self.collection_name)
        
        # Build filter
        where_clause = {}
        if workspace_id:
            where_clause["workspace_id"] = str(workspace_id)
        if project_id:
            where_clause["project_id"] = str(project_id)
        
        # Get all matching documents
        all_results = collection.get(where=where_clause) if where_clause else collection.get()
        
        # Filter by access permissions
        accessible_dashboards = []
        for i, doc_id in enumerate(all_results["ids"]):
            metadata = all_results["metadatas"][i]
            
            # Check if user has access
            if self._has_dashboard_access(user_id, metadata, include_shared):
                dashboard_id = UUID(doc_id)
                dashboard = self.db.query(Dashboard).filter(
                    Dashboard.id == dashboard_id
                ).first()
                if dashboard:
                    accessible_dashboards.append({
                        "dashboard": dashboard,
                        "permissions": metadata
                    })
        
        # Paginate results
        total_count = len(accessible_dashboards)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_results = accessible_dashboards[start_idx:end_idx]
        
        return {
            "dashboards": paginated_results,
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": (total_count + page_size - 1) // page_size
        }
    
    def share_dashboard(
        self,
        user_id: UUID,
        dashboard_id: UUID,
        share_with: List[UUID],
        permission_level: SharingPermission = SharingPermission.USER
    ) -> bool:
        """Share dashboard with users/teams/workspace"""
        
        # Get dashboard and check ownership
        collection = self._create_chroma_collection(self.collection_name)
        result = collection.get(ids=[str(dashboard_id)])
        
        if not result["ids"]:
            raise ValueError(f"Dashboard {dashboard_id} not found")
        
        metadata = result["metadatas"][0]
        
        if metadata["created_by"] != str(user_id):
            raise PermissionError("Only dashboard owner can share it")
        
        # Update sharing permissions
        metadata["sharing_permission"] = permission_level.value
        metadata["shared_with"] = [str(uid) for uid in share_with]
        
        # Update in ChromaDB
        dashboard = self.db.query(Dashboard).filter(
            Dashboard.id == dashboard_id
        ).first()
        
        self._update_chroma(
            self.collection_name,
            str(dashboard_id),
            {
                "name": dashboard.name,
                "description": dashboard.description,
                "type": dashboard.DashboardType,
                "content": dashboard.content
            },
            metadata
        )
        
        return True
    
    def get_dashboard_versions(
        self,
        user_id: UUID,
        dashboard_id: UUID
    ) -> List[DashboardVersion]:
        """Get all versions of a dashboard"""
        
        # Check access permission
        dashboard = self.get_dashboard(user_id, dashboard_id)
        if not dashboard:
            raise ValueError(f"Dashboard {dashboard_id} not found or access denied")
        
        versions = self.db.query(DashboardVersion).filter(
            DashboardVersion.dashboard_id == dashboard_id
        ).order_by(DashboardVersion.created_at.desc()).all()
        
        return versions
    
    def restore_dashboard_version(
        self,
        user_id: UUID,
        dashboard_id: UUID,
        version_id: UUID
    ) -> Dashboard:
        """Restore a specific version of dashboard"""
        
        dashboard = self.get_dashboard(user_id, dashboard_id)
        if not dashboard:
            raise ValueError(f"Dashboard {dashboard_id} not found")
        
        # Check update permission
        collection = self._create_chroma_collection(self.collection_name)
        result = collection.get(ids=[str(dashboard_id)])
        metadata = result["metadatas"][0]
        
        if metadata["created_by"] != str(user_id) and not self._check_user_permission(
            user_id, "dashboard", dashboard_id, "update"
        ):
            raise PermissionError("User doesn't have permission to restore dashboard version")
        
        # Get the version to restore
        version = self.db.query(DashboardVersion).filter(
            and_(
                DashboardVersion.id == version_id,
                DashboardVersion.dashboard_id == dashboard_id
            )
        ).first()
        
        if not version:
            raise ValueError(f"Version {version_id} not found for dashboard {dashboard_id}")
        
        # Create new version with restored content
        new_version_number = str(float(dashboard.version) + 0.1)
        new_version = DashboardVersion(
            dashboard_id=dashboard.id,
            version=new_version_number,
            content=version.content
        )
        self.db.add(new_version)
        
        # Update dashboard
        dashboard.content = version.content
        dashboard.version = new_version_number
        dashboard.updated_at = datetime.utcnow()
        
        self.db.commit()
        return dashboard
    
    def _has_dashboard_access(
        self,
        user_id: UUID,
        metadata: Dict[str, Any],
        include_shared: bool = True
    ) -> bool:
        """Check if user has access to dashboard based on metadata"""
        
        # Owner always has access
        if metadata.get("created_by") == str(user_id):
            return True
        
        # Check sharing permissions
        sharing = metadata.get("sharing_permission", "private")
        
        if sharing == SharingPermission.DEFAULT.value:
            return True
        
        if sharing == SharingPermission.PRIVATE.value:
            return False
        
        if not include_shared:
            return False
        
        # Check if explicitly shared with user
        if str(user_id) in metadata.get("shared_with", []):
            return True
        
        # Check workspace/project membership
        if sharing == SharingPermission.WORKSPACE.value and metadata.get("workspace_id"):
            from app.models.workspace import WorkspaceAccess
            access = self.db.query(WorkspaceAccess).filter(
                and_(
                    WorkspaceAccess.workspace_id == UUID(metadata["workspace_id"]),
                    WorkspaceAccess.user_id == user_id
                )
            ).first()
            return access is not None
        
        # Check team membership
        if sharing == SharingPermission.TEAM.value:
            from app.models.team import team_memberships
            shared_team_ids = metadata.get("shared_with", [])
            if shared_team_ids:
                membership = self.db.query(team_memberships).filter(
                    and_(
                        team_memberships.c.user_id == user_id,
                        team_memberships.c.team_id.in_([UUID(tid) for tid in shared_team_ids])
                    )
                ).first()
                return membership is not None
        
        return False
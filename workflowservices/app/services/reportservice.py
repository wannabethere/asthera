from typing import Optional, List, Dict, Any, Union
from uuid import UUID
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from app.services.baseservice import BaseService, SharingPermission
from app.models.dbmodels import Report, ReportVersion
from app.models.thread import Thread, Workflow
from app.models.workspace import Workspace, Project
from app.models.schema import ReportCreate, ReportUpdate, ReportResponse

class ReportService(BaseService):
    """Service for managing reports with workflow integration"""
    
    def __init__(self, db: Session, chroma_client=None):
        super().__init__(db, chroma_client)
        self.collection_name = "reports"
    
    def create_report(
        self,
        user_id: UUID,
        report_data: ReportCreate,
        workflow_id: Optional[UUID] = None,
        project_id: Optional[UUID] = None,
        workspace_id: Optional[UUID] = None,
        sharing_permission: SharingPermission = SharingPermission.PRIVATE,
        shared_with: Optional[List[UUID]] = None
    ) -> Report:
        """Create a new report with optional workflow association"""
        
        # Check permissions if project/workspace specified
        if project_id and not self._check_user_permission(
            user_id, "project", project_id, "create"
        ):
            raise PermissionError("User doesn't have permission to create report in this project")
        
        if workspace_id and not self._check_user_permission(
            user_id, "workspace", workspace_id, "create"
        ):
            raise PermissionError("User doesn't have permission to create report in this workspace")
        
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
        
        # Create report
        report = Report(
            name=report_data.name,
            description=report_data.description,
            reportType=report_data.reportType,
            is_active=report_data.is_active,
            content=report_data.content,
            version="1.0"
        )
        
        self.db.add(report)
        self.db.flush()
        
        # Create initial version
        version = ReportVersion(
            report_id=report.id,
            version="1.0",
            content=report_data.content
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
            str(report.id),
            {
                "name": report.name,
                "description": report.description,
                "type": report.reportType,
                "content": report.content
            },
            metadata
        )
        
        self.db.commit()
        return report
    
    def get_report(
        self,
        user_id: UUID,
        report_id: UUID
    ) -> Optional[Report]:
        """Get report by ID with permission check"""
        
        report = self.db.query(Report).filter(
            Report.id == report_id
        ).first()
        
        if not report:
            return None
        
        # Check permissions via ChromaDB metadata
        collection = self._create_chroma_collection(self.collection_name)
        result = collection.get(ids=[str(report_id)])
        
        if not result["ids"]:
            return None
        
        metadata = result["metadatas"][0]
        
        # Check access permissions
        if not self._has_report_access(user_id, metadata):
            raise PermissionError("User doesn't have access to this report")
        
        return report
    
    def update_report(
        self,
        user_id: UUID,
        report_id: UUID,
        update_data: ReportUpdate,
        create_version: bool = True
    ) -> Report:
        """Update report with optional versioning"""
        
        report = self.get_report(user_id, report_id)
        if not report:
            raise ValueError(f"Report {report_id} not found")
        
        # Check update permission
        collection = self._create_chroma_collection(self.collection_name)
        result = collection.get(ids=[str(report_id)])
        metadata = result["metadatas"][0]
        
        if metadata["created_by"] != str(user_id) and not self._check_user_permission(
            user_id, "report", report_id, "update"
        ):
            raise PermissionError("User doesn't have permission to update this report")
        
        # Create version before update if requested
        if create_version and update_data.content:
            current_version = float(report.version)
            new_version = str(current_version + 0.1)
            
            version = ReportVersion(
                report_id=report.id,
                version=new_version,
                content=update_data.content
            )
            self.db.add(version)
            report.version = new_version
        
        # Update report fields
        for field, value in update_data.dict(exclude_unset=True).items():
            setattr(report, field, value)
        
        report.updated_at = datetime.utcnow()
        
        # Update ChromaDB
        self._update_chroma(
            self.collection_name,
            str(report_id),
            {
                "name": report.name,
                "description": report.description,
                "type": report.reportType,
                "content": report.content
            },
            metadata
        )
        
        self.db.commit()
        return report
    
    def delete_report(
        self,
        user_id: UUID,
        report_id: UUID
    ) -> bool:
        """Delete report with permission check"""
        
        report = self.get_report(user_id, report_id)
        if not report:
            return False
        
        # Check delete permission
        collection = self._create_chroma_collection(self.collection_name)
        result = collection.get(ids=[str(report_id)])
        metadata = result["metadatas"][0]
        
        if metadata["created_by"] != str(user_id) and not self._check_user_permission(
            user_id, "report", report_id, "delete"
        ):
            raise PermissionError("User doesn't have permission to delete this report")
        
        # Delete from ChromaDB
        self._delete_from_chroma(self.collection_name, str(report_id))
        
        # Delete from PostgreSQL (versions will cascade)
        self.db.delete(report)
        self.db.commit()
        
        return True
    
    def search_reports(
        self,
        user_id: UUID,
        query: str,
        workspace_id: Optional[UUID] = None,
        project_id: Optional[UUID] = None,
        workflow_id: Optional[UUID] = None,
        report_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search reports with permission filtering"""
        
        # Build filters for ChromaDB search
        filters = {}
        
        if workspace_id:
            filters["workspace_id"] = str(workspace_id)
        if project_id:
            filters["project_id"] = str(project_id)
        if workflow_id:
            filters["workflow_id"] = str(workflow_id)
        if report_type:
            filters["type"] = report_type
        
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
            if self._has_report_access(user_id, result["metadata"]):
                report_id = UUID(result["id"])
                report = self.db.query(Report).filter(
                    Report.id == report_id
                ).first()
                if report:
                    accessible_results.append({
                        "report": report,
                        "metadata": result["metadata"],
                        "relevance_score": 1 - result["distance"] if result["distance"] else 1
                    })
                    if len(accessible_results) >= limit:
                        break
        
        return accessible_results
    
    def list_user_reports(
        self,
        user_id: UUID,
        workspace_id: Optional[UUID] = None,
        project_id: Optional[UUID] = None,
        include_shared: bool = True,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """List reports accessible to user with pagination"""
        
        # Get all reports from ChromaDB with metadata
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
        accessible_reports = []
        for i, doc_id in enumerate(all_results["ids"]):
            metadata = all_results["metadatas"][i]
            
            # Check if user has access
            if self._has_report_access(user_id, metadata, include_shared):
                report_id = UUID(doc_id)
                report = self.db.query(Report).filter(
                    Report.id == report_id
                ).first()
                if report:
                    accessible_reports.append({
                        "report": report,
                        "permissions": metadata
                    })
        
        # Paginate results
        total_count = len(accessible_reports)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_results = accessible_reports[start_idx:end_idx]
        
        return {
            "reports": paginated_results,
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": (total_count + page_size - 1) // page_size
        }
    
    def share_report(
        self,
        user_id: UUID,
        report_id: UUID,
        share_with: List[UUID],
        permission_level: SharingPermission = SharingPermission.USER
    ) -> bool:
        """Share report with users/teams/workspace"""
        
        # Get report and check ownership
        collection = self._create_chroma_collection(self.collection_name)
        result = collection.get(ids=[str(report_id)])
        
        if not result["ids"]:
            raise ValueError(f"Report {report_id} not found")
        
        metadata = result["metadatas"][0]
        
        if metadata["created_by"] != str(user_id):
            raise PermissionError("Only report owner can share it")
        
        # Update sharing permissions
        metadata["sharing_permission"] = permission_level.value
        metadata["shared_with"] = [str(uid) for uid in share_with]
        
        # Update in ChromaDB
        report = self.db.query(Report).filter(
            Report.id == report_id
        ).first()
        
        self._update_chroma(
            self.collection_name,
            str(report_id),
            {
                "name": report.name,
                "description": report.description,
                "type": report.reportType,
                "content": report.content
            },
            metadata
        )
        
        return True
    
    def generate_report_from_workflow(
        self,
        user_id: UUID,
        workflow_id: UUID,
        report_template: Optional[Dict[str, Any]] = None
    ) -> Report:
        """Generate a report from workflow data"""
        
        # Get workflow and thread data
        workflow = self.db.query(Workflow).filter(
            Workflow.id == workflow_id
        ).first()
        
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        # Check access to workflow
        if workflow.user_id != user_id and not self._check_user_permission(
            user_id, "thread", workflow.thread_id, "read"
        ):
            raise PermissionError("User doesn't have access to this workflow")
        
        # Get thread and messages
        thread = self.db.query(Thread).filter(
            Thread.id == workflow.thread_id
        ).first()
        
        # Generate report content from workflow
        report_content = self._generate_report_content(workflow, thread, report_template)
        
        # Create report
        report_data = ReportCreate(
            name=f"Report for {workflow.title}",
            description=f"Auto-generated report from workflow: {workflow.description or workflow.title}",
            reportType="Standard",
            is_active=True,
            content=report_content
        )
        
        return self.create_report(
            user_id=user_id,
            report_data=report_data,
            workflow_id=workflow_id,
            project_id=thread.project_id if thread else None
        )
    
    def _generate_report_content(
        self,
        workflow: Workflow,
        thread: Thread,
        template: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate report content from workflow and thread data"""
        
        # Default report structure
        report_content = {
            "title": workflow.title,
            "summary": workflow.description or "",
            "workflow_status": workflow.status,
            "thread_info": {
                "title": thread.title if thread else "",
                "description": thread.description if thread else "",
                "created_at": str(thread.created_at) if thread else None
            },
            "workflow_steps": workflow.steps,
            "metrics": [],
            "insights": [],
            "recommendations": []
        }
        
        # Apply template if provided
        if template:
            report_content.update(template)
        
        # Add thread messages summary if available
        if thread and thread.messages:
            report_content["message_count"] = len(thread.messages)
            report_content["last_message_at"] = str(max(m.created_at for m in thread.messages))
        
        # Add notes if available
        if thread and thread.notes:
            report_content["notes"] = [
                {
                    "title": note.title,
                    "content": note.content[:200] + "..." if len(note.content) > 200 else note.content
                }
                for note in sorted(thread.notes, key=lambda n: n.sortorder)[:5]
            ]
        
        # Add timeline events if available
        if thread and thread.timelines:
            timeline_events = []
            for timeline in thread.timelines:
                timeline_events.extend(timeline.events[:3])  # Top 3 events per timeline
            report_content["key_events"] = timeline_events[:10]  # Max 10 events
        
        return report_content
    
    def _has_report_access(
        self,
        user_id: UUID,
        metadata: Dict[str, Any],
        include_shared: bool = True
    ) -> bool:
        """Check if user has access to report based on metadata"""
        
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
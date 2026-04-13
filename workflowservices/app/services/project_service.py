from typing import Optional, List, Dict, Any
from uuid import UUID
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, delete
from sqlalchemy.orm import selectinload

from app.models.workspace import Project, ProjectArtifact, ProjectAccess
from app.models.dbmodels import Dashboard, Report


class ProjectService:
    """Service for managing Projects and their linked artifacts."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==================== Project CRUD ====================

    async def create_project(
        self,
        user_id: UUID,
        name: str,
        description: Optional[str] = None,
        workspace_id: Optional[UUID] = None,
        goals: Optional[List[str]] = None,
        data_sources: Optional[List[str]] = None,
        thread_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new project and grant owner access to the creator."""
        project = Project(
            name=name,
            description=description,
            workspace_id=workspace_id,
            goals=goals or [],
            data_sources=data_sources or [],
            thread_id=thread_id,
            created_by=user_id,
            status="active",
            project_metadata=metadata or {},
        )
        self.db.add(project)
        await self.db.flush()

        # Create owner access for the creator
        access = ProjectAccess(
            project_id=project.id,
            user_id=user_id,
            is_admin=True,
            can_create=True,
            can_delete=True,
        )
        self.db.add(access)
        await self.db.commit()
        await self.db.refresh(project)

        return self._project_to_dict(project)

    async def get_project(self, project_id: UUID) -> Optional[Dict[str, Any]]:
        """Get a single project by ID."""
        result = await self.db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalars().first()
        if not project:
            return None
        return self._project_to_dict(project)

    async def list_projects(
        self,
        user_id: UUID,
        workspace_id: Optional[UUID] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List projects the user has access to."""
        query = select(Project)

        if workspace_id:
            query = query.where(Project.workspace_id == workspace_id)
        if status:
            query = query.where(Project.status == status)

        query = query.order_by(Project.created_at.desc()).limit(limit)
        result = await self.db.execute(query)
        projects = result.scalars().all()

        return [self._project_to_dict(p) for p in projects]

    async def update_project(
        self, project_id: UUID, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Update project fields."""
        result = await self.db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalars().first()
        if not project:
            return None

        allowed_fields = {"name", "description", "goals", "data_sources", "thread_id", "status", "project_metadata"}
        for key, value in kwargs.items():
            if key in allowed_fields and value is not None:
                setattr(project, key, value)

        await self.db.commit()
        await self.db.refresh(project)
        return self._project_to_dict(project)

    async def delete_project(self, project_id: UUID) -> bool:
        """Soft-delete a project by setting status to archived."""
        result = await self.db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalars().first()
        if not project:
            return False
        project.status = "archived"
        await self.db.commit()
        return True

    # ==================== Artifact Linking ====================

    async def add_artifact(
        self,
        project_id: UUID,
        artifact_type: str,
        artifact_id: UUID,
        parent_artifact_id: Optional[UUID] = None,
        sequence_order: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Link an existing dashboard/report/alert to a project."""
        artifact = ProjectArtifact(
            project_id=project_id,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            parent_artifact_id=parent_artifact_id,
            sequence_order=sequence_order,
            artifact_metadata=metadata or {},
        )
        self.db.add(artifact)
        await self.db.commit()
        await self.db.refresh(artifact)
        return self._artifact_to_dict(artifact)

    async def remove_artifact(self, project_id: UUID, artifact_id: UUID) -> bool:
        """Remove an artifact link from a project."""
        result = await self.db.execute(
            select(ProjectArtifact).where(
                and_(
                    ProjectArtifact.project_id == project_id,
                    ProjectArtifact.artifact_id == artifact_id,
                )
            )
        )
        artifact = result.scalars().first()
        if not artifact:
            return False
        await self.db.delete(artifact)
        await self.db.commit()
        return True

    async def get_project_with_artifacts(self, project_id: UUID) -> Optional[Dict[str, Any]]:
        """Get project with all its linked artifacts and their details."""
        # Get project
        result = await self.db.execute(
            select(Project)
            .options(selectinload(Project.artifacts))
            .where(Project.id == project_id)
        )
        project = result.scalars().first()
        if not project:
            return None

        project_dict = self._project_to_dict(project)
        artifacts = project.artifacts or []

        # Separate artifact IDs by type for batch fetching
        dashboard_ids = [a.artifact_id for a in artifacts if a.artifact_type == "dashboard"]
        report_ids = [a.artifact_id for a in artifacts if a.artifact_type == "report"]
        alert_ids = [a.artifact_id for a in artifacts if a.artifact_type == "alert"]

        # Batch-fetch actual records
        dashboards_map = {}
        if dashboard_ids:
            dash_result = await self.db.execute(
                select(Dashboard).where(Dashboard.id.in_(dashboard_ids))
            )
            for d in dash_result.scalars().all():
                dashboards_map[d.id] = {
                    "id": str(d.id), "name": d.name, "description": d.description,
                    "type": d.DashboardType, "is_active": d.is_active, "version": d.version,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                    "updated_at": d.updated_at.isoformat() if d.updated_at else None,
                }

        reports_map = {}
        if report_ids:
            rep_result = await self.db.execute(
                select(Report).where(Report.id.in_(report_ids))
            )
            for r in rep_result.scalars().all():
                reports_map[r.id] = {
                    "id": str(r.id), "name": r.name, "description": r.description,
                    "type": r.reportType, "is_active": r.is_active, "version": r.version,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                }

        # Build artifact list with details
        artifact_list = []
        for a in artifacts:
            a_dict = self._artifact_to_dict(a)
            if a.artifact_type == "dashboard" and a.artifact_id in dashboards_map:
                a_dict["artifact_details"] = dashboards_map[a.artifact_id]
            elif a.artifact_type == "report" and a.artifact_id in reports_map:
                a_dict["artifact_details"] = reports_map[a.artifact_id]
            # Alert details could be fetched similarly if needed
            artifact_list.append(a_dict)

        project_dict["artifacts"] = artifact_list
        project_dict["dashboard_count"] = len(dashboard_ids)
        project_dict["report_count"] = len(report_ids)
        project_dict["alert_count"] = len(alert_ids)

        return project_dict

    # ==================== Helpers ====================

    def _project_to_dict(self, project: Project) -> Dict[str, Any]:
        return {
            "id": str(project.id),
            "name": project.name,
            "description": project.description,
            "workspace_id": str(project.workspace_id) if project.workspace_id else None,
            "goals": project.goals or [],
            "data_sources": project.data_sources or [],
            "thread_id": str(project.thread_id) if project.thread_id else None,
            "created_by": str(project.created_by) if project.created_by else None,
            "status": project.status or "active",
            "metadata": project.project_metadata or {},
            "created_at": project.created_at.isoformat() if project.created_at else None,
            "updated_at": project.updated_at.isoformat() if project.updated_at else None,
        }

    def _artifact_to_dict(self, artifact: ProjectArtifact) -> Dict[str, Any]:
        return {
            "id": str(artifact.id),
            "project_id": str(artifact.project_id),
            "artifact_type": artifact.artifact_type,
            "artifact_id": str(artifact.artifact_id),
            "parent_artifact_id": str(artifact.parent_artifact_id) if artifact.parent_artifact_id else None,
            "sequence_order": artifact.sequence_order or 0,
            "artifact_metadata": artifact.artifact_metadata or {},
            "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
            "artifact_details": None,
        }

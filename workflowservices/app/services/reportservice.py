from typing import Optional, List, Dict, Any, Union
from uuid import UUID
import uuid
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, func, select
from app.services.baseservice import BaseService, SharingPermission
from app.models.dbmodels import Report, ReportVersion, ReportSnapshot
from app.models.thread import Thread, Workflow
from app.models.workspace import Workspace, Project
from app.models.schema import (
    ReportCreate, ReportUpdate, ReportResponse, 
    ReportSnapshotCreate, ReportSnapshotResponse,
    ReportOutputFormat, ReportSnapshotEventsCreate,
    ReportSnapshotEventCreate, ReportSnapshotEventResponse
)
from app.models.dbmodels import ReportSnapshotEvent
from app.models.workflowmodels import ThreadComponent, ReportWorkflow
import traceback
import json
class ReportService(BaseService):
    """Service for managing reports with workflow integration"""
    
    def __init__(self, db: AsyncSession, chroma_client=None):
        super().__init__(db)
        self.collection_name = "reports"
    
    async def create_report(
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
        if project_id and not await self._check_user_permission(
            user_id, "project", project_id, "create"
        ):
            raise PermissionError("User doesn't have permission to create report in this project")
        
        if workspace_id and not await self._check_user_permission(
            user_id, "workspace", workspace_id, "create"
        ):
            raise PermissionError("User doesn't have permission to create report in this workspace")
        
        try:

                # Validate workflow exists and user has access
                if workflow_id:
                    stmt = select(Workflow).where(Workflow.id == workflow_id)
                    result = await self.db.execute(stmt)
                    workflow = result.scalar_one_or_none()
                    
                    if not workflow:
                        raise ValueError(f"Workflow {workflow_id} not found")
                    if workflow.user_id != user_id and not await self._check_user_permission(
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
                await self.db.flush()
                
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
                    "shared_with": [str(uid) for uid in shared_with] if shared_with else None
                }
                if isinstance(metadata["shared_with"],list):
                    metadata["shared_with"] = json.dumps(metadata["shared_with"])

                metadata = {k: v for k, v in metadata.items() if v is not None}
                
                # Add to ChromaDB for searchability
                await self._add_to_chroma(
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
                
                await self.db.commit()
                return report
        except Exception as e:
                print("==================Error in create report =================")
                traceback.print_exc()
                print("====================Error Ended==================")
    
    async def get_report(
        self,
        user_id: UUID,
        report_id: UUID
    ) -> Optional[Report]:
        """Get report by ID with permission check"""
        
        stmt = select(Report).where(Report.id == report_id)
        result = await self.db.execute(stmt)
        report = result.scalar_one_or_none()
        
        if not report:
            return None
        
        # Check permissions via ChromaDB metadata
        collection = await self._create_chroma_collection(self.collection_name)
        result = collection.get(ids=[str(report_id)])
        
        if not result["ids"]:
            return None
        
        metadata = result["metadatas"][0]
        
        # Check access permissions
        if not await self._has_report_access(user_id, metadata):
            raise PermissionError("User doesn't have access to this report")
        
        return report
    
    async def update_report(
        self,
        user_id: UUID,
        report_id: UUID,
        update_data: ReportUpdate,
        create_version: bool = True
    ) -> Report:
        """Update report with optional versioning"""
        
        report = await self.get_report(user_id, report_id)
        if not report:
            raise ValueError(f"Report {report_id} not found")
        
        # Check update permission
        collection = await self._create_chroma_collection(self.collection_name)
        result = collection.get(ids=[str(report_id)])
        metadata = result["metadatas"][0]
        
        if metadata["created_by"] != str(user_id) and not await self._check_user_permission(
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
        await self._update_chroma(
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
        
        await self.db.commit()
        return report
    
    async def delete_report(
        self,
        user_id: UUID,
        report_id: UUID
    ) -> bool:
        """Delete report with permission check"""
        
        report = await self.get_report(user_id, report_id)
        if not report:
            return False
        
        # Check delete permission
        collection = await self._create_chroma_collection(self.collection_name)
        result = collection.get(ids=[str(report_id)])
        metadata = result["metadatas"][0]
        
        if metadata["created_by"] != str(user_id) and not await self._check_user_permission(
            user_id, "report", report_id, "delete"
        ):
            raise PermissionError("User doesn't have permission to delete this report")
        
        # Delete from ChromaDB
        await self._delete_from_chroma(self.collection_name, str(report_id))
        
        # Delete from PostgreSQL (versions will cascade)
        self.db.delete(report)
        await self.db.commit()
        
        return True
    
    async def search_reports(
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
        results = await self._search_chroma(
            self.collection_name,
            query,
            filters,
            limit * 2  # Get more results for permission filtering
        )
        
        # Filter by permissions
        accessible_results = []
        for result in results:
            if await self._has_report_access(user_id, result["metadata"]):
                report_id = UUID(result["id"])
                stmt = select(Report).where(Report.id == report_id)
                result = await self.db.execute(stmt)
                report = result.scalar_one_or_none()
                if report:
                    accessible_results.append({
                        "report": report,
                        "metadata": result["metadata"],
                        "relevance_score": 1 - result["distance"] if result["distance"] else 1
                    })
                    if len(accessible_results) >= limit:
                        break
        
        return accessible_results
    
    async def list_user_reports(
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
        collection = await self._create_chroma_collection(self.collection_name)
        
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
            if await self._has_report_access(user_id, metadata, include_shared):
                report_id = UUID(doc_id)
                stmt = select(Report).where(Report.id == report_id)
                result = await self.db.execute(stmt)
                report = result.scalar_one_or_none()
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
    
    async def share_report(
        self,
        user_id: UUID,
        report_id: UUID,
        share_with: List[UUID],
        permission_level: SharingPermission = SharingPermission.USER
    ) -> bool:
        """Share report with users/teams/workspace"""
        
        # Get report and check ownership
        collection = await self._create_chroma_collection(self.collection_name)
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
        report = await self.db.execute(select(Report).where(Report.id == report_id))
        report = report.scalar_one_or_none()
        
        if not report:
            raise ValueError(f"Report {report_id} not found")
        
        await self._update_chroma(
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
    
    async def generate_report_from_workflow(
        self,
        user_id: UUID,
        workflow_id: UUID,
        report_template: Optional[Dict[str, Any]] = None
    ) -> Report:
        """Generate a report from workflow data"""
        
        # Get workflow and thread data
        stmt = select(Workflow).where(Workflow.id == workflow_id)
        result = await self.db.execute(stmt)
        workflow = result.scalar_one_or_none()
        
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        # Check access to workflow
        if workflow.user_id != user_id and not await self._check_user_permission(
            user_id, "thread", workflow.thread_id, "read"
        ):
            raise PermissionError("User doesn't have access to this workflow")
        
        # Get thread and messages
        stmt = select(Thread).where(Thread.id == workflow.thread_id)
        result = await self.db.execute(stmt)
        thread = result.scalar_one_or_none()
        
        # Generate report content from workflow
        report_content = await self._generate_report_content(workflow, thread, report_template)
        
        # Create report
        report_data = ReportCreate(
            name=f"Report for {workflow.title}",
            description=f"Auto-generated report from workflow: {workflow.description or workflow.title}",
            reportType="Standard",
            is_active=True,
            content=report_content
        )
        
        return await self.create_report(
            user_id=user_id,
            report_data=report_data,
            workflow_id=workflow_id,
            project_id=thread.project_id if thread else None
        )
    
    async def _generate_report_content(
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
    
    async def _has_report_access(
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
            stmt = select(WorkspaceAccess).where(
                and_(
                    WorkspaceAccess.workspace_id == UUID(metadata["workspace_id"]),
                    WorkspaceAccess.user_id == user_id
                )
            )
            result = await self.db.execute(stmt)
            access = result.scalar_one_or_none()
            return access is not None
        
        # Check team membership
        if sharing == SharingPermission.TEAM.value:
            from app.models.team import team_memberships
            shared_team_ids = metadata.get("shared_with", [])
            if shared_team_ids:
                stmt = select(team_memberships).where(
                    and_(
                        team_memberships.c.user_id == user_id,
                        team_memberships.c.team_id.in_([UUID(tid) for tid in shared_team_ids])
                    )
                )
                result = await self.db.execute(stmt)
                membership = result.scalar_one_or_none()
                return membership is not None
        
        return False
    
    async def create_snapshot(
        self,
        user_id: UUID,
        snapshot_data: ReportSnapshotCreate
    ) -> ReportSnapshot:
        """Create a snapshot of report with thread components and response data"""
        
        # Get report and verify access
        report = await self.get_report(user_id, snapshot_data.report_id)
        if not report:
            raise ValueError(f"Report {snapshot_data.report_id} not found or access denied")
        
        # Prepare report data snapshot
        report_data = {
            "id": str(report.id),
            "name": report.name,
            "description": report.description,
            "reportType": report.reportType,
            "is_active": report.is_active,
            "content": report.content,
            "version": report.version,
            "created_at": report.created_at.isoformat() if report.created_at else None,
            "updated_at": report.updated_at.isoformat() if report.updated_at else None
        }
        
        # Get thread components if workflow_id is provided
        thread_components_data = None
        if snapshot_data.workflow_id:
            # Get workflow and thread components
            stmt = select(ReportWorkflow).where(
                and_(
                    ReportWorkflow.id == snapshot_data.workflow_id,
                    ReportWorkflow.report_id == snapshot_data.report_id
                )
            )
            result = await self.db.execute(stmt)
            workflow = result.scalar_one_or_none()
            
            if workflow:
                # Get all thread components for this workflow
                stmt = select(ThreadComponent).where(
                    ThreadComponent.report_workflow_id == workflow.id
                ).order_by(ThreadComponent.sequence_order)
                result = await self.db.execute(stmt)
                components = result.scalars().all()
                
                thread_components_data = {
                    "workflow_id": str(workflow.id),
                    "workflow_state": workflow.state.value if hasattr(workflow.state, 'value') else str(workflow.state),
                    "components": []
                }
                
                for component in components:
                    comp_data = {
                        "id": str(component.id),
                        "component_type": component.component_type.value if hasattr(component.component_type, 'value') else str(component.component_type),
                        "sequence_order": component.sequence_order,
                        "question": component.question,
                        "description": component.description,
                        "overview": component.overview,
                        "chart_config": component.chart_config,
                        "table_config": component.table_config,
                        "sql_query": component.sql_query,
                        "executive_summary": component.executive_summary,
                        "data_overview": component.data_overview,
                        "visualization_data": component.visualization_data,
                        "sample_data": component.sample_data,
                        "thread_metadata": component.thread_metadata,
                        "chart_schema": component.chart_schema,
                        "reasoning": component.reasoning,
                        "data_count": component.data_count,
                        "validation_results": component.validation_results,
                        "alert_config": component.alert_config,
                        "alert_status": component.alert_status.value if component.alert_status and hasattr(component.alert_status, 'value') else str(component.alert_status) if component.alert_status else None,
                        "configuration": component.configuration,
                        "is_configured": component.is_configured,
                        "thread_message_id": str(component.thread_message_id) if component.thread_message_id else None,
                        "created_at": component.created_at.isoformat() if component.created_at else None,
                        "updated_at": component.updated_at.isoformat() if component.updated_at else None
                    }
                    thread_components_data["components"].append(comp_data)
        
        # Prepare output format if provided
        output_format_data = None
        if snapshot_data.output_format:
            # Convert Pydantic model to dict for JSONB storage
            if hasattr(snapshot_data.output_format, 'dict'):
                output_format_data = snapshot_data.output_format.dict()
            elif hasattr(snapshot_data.output_format, 'model_dump'):
                output_format_data = snapshot_data.output_format.model_dump()
            elif isinstance(snapshot_data.output_format, dict):
                output_format_data = snapshot_data.output_format
            else:
                output_format_data = snapshot_data.output_format
        
        # Create snapshot
        snapshot = ReportSnapshot(
            report_id=snapshot_data.report_id,
            workflow_id=snapshot_data.workflow_id,
            user_id=user_id,
            report_data=report_data,
            thread_components_data=thread_components_data,
            response_data=snapshot_data.response_data,
            output_format=output_format_data,
            metadata_tags=snapshot_data.metadata_tags or {},
            description=snapshot_data.description,
            snapshot_timestamp=datetime.utcnow()
        )
        
        self.db.add(snapshot)
        await self.db.commit()
        await self.db.refresh(snapshot)
        
        return snapshot
    
    async def get_snapshot(
        self,
        user_id: UUID,
        snapshot_id: UUID
    ) -> Optional[ReportSnapshot]:
        """Get a specific report snapshot by ID"""
        
        stmt = select(ReportSnapshot).where(ReportSnapshot.id == snapshot_id)
        result = await self.db.execute(stmt)
        snapshot = result.scalar_one_or_none()
        
        if not snapshot:
            return None
        
        # Verify user has access to the report
        report = await self.get_report(user_id, snapshot.report_id)
        if not report:
            raise PermissionError("User doesn't have access to this snapshot")
        
        return snapshot
    
    async def list_snapshots(
        self,
        user_id: UUID,
        report_id: Optional[UUID] = None,
        workflow_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        metadata_tags: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """List report snapshots with filtering and pagination"""
        
        # Build query
        conditions = []
        
        if report_id:
            conditions.append(ReportSnapshot.report_id == report_id)
        
        if workflow_id:
            conditions.append(ReportSnapshot.workflow_id == workflow_id)
        
        if start_date:
            conditions.append(ReportSnapshot.snapshot_timestamp >= start_date)
        
        if end_date:
            conditions.append(ReportSnapshot.snapshot_timestamp <= end_date)
        
        if metadata_tags:
            # Filter by metadata tags (JSONB contains)
            for key, value in metadata_tags.items():
                conditions.append(
                    ReportSnapshot.metadata_tags[key].astext == str(value)
                )
        
        stmt = select(ReportSnapshot)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        
        # Order by timestamp descending
        stmt = stmt.order_by(ReportSnapshot.snapshot_timestamp.desc())
        
        # Apply pagination
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)
        
        # Execute query
        result = await self.db.execute(stmt)
        snapshots = result.scalars().all()
        
        # Filter by user access - only return snapshots for reports user can access
        accessible_snapshots = []
        for snapshot in snapshots:
            try:
                report = await self.get_report(user_id, snapshot.report_id)
                if report:
                    accessible_snapshots.append(snapshot)
            except PermissionError:
                # Skip snapshots user doesn't have access to
                continue
        
        return {
            "snapshots": accessible_snapshots,
            "total": len(accessible_snapshots),
            "page": page,
            "page_size": page_size,
            "total_pages": (len(accessible_snapshots) + page_size - 1) // page_size
        }
    
    async def delete_snapshot(
        self,
        user_id: UUID,
        snapshot_id: UUID
    ) -> bool:
        """Delete a report snapshot"""
        
        snapshot = await self.get_snapshot(user_id, snapshot_id)
        if not snapshot:
            return False
        
        # Check if user created the snapshot or has report delete permission
        if snapshot.user_id != user_id:
            collection = await self._create_chroma_collection(self.collection_name)
            result = collection.get(ids=[str(snapshot.report_id)])
            if result["ids"]:
                metadata = result["metadatas"][0]
                if not await self._check_user_permission(
                    user_id, "report", snapshot.report_id, "delete"
                ):
                    raise PermissionError("User doesn't have permission to delete this snapshot")
        
        self.db.delete(snapshot)
        await self.db.commit()
        
        return True
    
    async def create_snapshot_events(
        self,
        user_id: UUID,
        events_data: ReportSnapshotEventsCreate
    ) -> List[ReportSnapshotEvent]:
        """Create snapshot events from questions/charts - one event per question/chart for change tracking"""
        
        # Get report and verify access
        report = await self.get_report(user_id, events_data.report_id)
        if not report:
            raise ValueError(f"Report {events_data.report_id} not found or access denied")
        
        # Create events for each question/chart
        events = []
        event_timestamp = datetime.utcnow()
        
        for event_data in events_data.events:
            # Merge common metadata with event-specific metadata
            merged_metadata = {**(events_data.metadata_tags or {}), **(event_data.event_metadata or {})}
            
            event = ReportSnapshotEvent(
                report_id=events_data.report_id,
                workflow_id=events_data.workflow_id or event_data.workflow_id,
                component_id=event_data.component_id,
                user_id=user_id,
                question=event_data.question,
                query_text=event_data.query_text,
                sql_query=event_data.sql_query,
                chart_schema=event_data.chart_schema,
                data=event_data.data,
                summary=event_data.summary,
                executive_summary=event_data.executive_summary,
                component_type=event_data.component_type,
                sequence_order=event_data.sequence_order,
                event_metadata=merged_metadata,
                event_timestamp=event_timestamp
            )
            
            self.db.add(event)
            events.append(event)
        
        await self.db.commit()
        
        # Refresh all events
        for event in events:
            await self.db.refresh(event)
        
        return events
    
    async def create_snapshot_events_from_output_format(
        self,
        user_id: UUID,
        report_id: UUID,
        workflow_id: Optional[UUID],
        output_format: Union[ReportOutputFormat, Dict[str, Any]],
        metadata_tags: Optional[Dict[str, Any]] = None
    ) -> List[ReportSnapshotEvent]:
        """Create snapshot events by parsing output format from agents service"""
        
        # Convert output_format to dict if it's a Pydantic model
        if hasattr(output_format, 'dict'):
            output_dict = output_format.dict()
        elif hasattr(output_format, 'model_dump'):
            output_dict = output_format.model_dump()
        elif isinstance(output_format, dict):
            output_dict = output_format
        else:
            output_dict = {}
        
        events = []
        event_timestamp = datetime.utcnow()
        
        # Extract report_data which contains components
        report_data = output_dict.get("report_data") or {}
        enhanced_report = output_dict.get("enhanced_report") or {}
        
        # Try to extract questions/charts from report_data
        components = report_data.get("components", [])
        sections = report_data.get("sections", [])
        charts = report_data.get("charts", [])
        
        # Process components from report_data
        for idx, component in enumerate(components):
            question = component.get("question") or component.get("query")
            chart_schema = component.get("chart_schema") or component.get("chart_config") or component.get("visualization_data")
            data = component.get("data") or component.get("sample_data") or component.get("visualization_data", {})
            summary = component.get("summary") or component.get("executive_summary") or component.get("reasoning")
            executive_summary = component.get("executive_summary")
            sql_query = component.get("sql_query") or component.get("sql")
            query_text = component.get("query") or component.get("question")
            component_type = component.get("component_type") or component.get("type") or "chart"
            component_id = component.get("id")
            
            if component_id:
                try:
                    component_id = UUID(component_id)
                except:
                    component_id = None
            
            event = ReportSnapshotEvent(
                report_id=report_id,
                workflow_id=workflow_id,
                component_id=component_id,
                user_id=user_id,
                question=question,
                query_text=query_text,
                sql_query=sql_query,
                chart_schema=chart_schema,
                data=data if isinstance(data, dict) else {"value": data},
                summary=summary,
                executive_summary=executive_summary,
                component_type=str(component_type),
                sequence_order=component.get("sequence_order") or component.get("sequence") or idx,
                metadata={
                    **(metadata_tags or {}),
                    "component_id": str(component_id) if component_id else None,
                    "overview": component.get("overview"),
                    "data_count": component.get("data_count"),
                    "chart_config": component.get("chart_config"),
                    "table_config": component.get("table_config"),
                },
                event_timestamp=event_timestamp
            )
            
            self.db.add(event)
            events.append(event)
        
        # Process sections if available
        if not components and sections:
            for section_idx, section in enumerate(sections):
                section_components = section.get("components", []) or section.get("charts", [])
                for idx, component in enumerate(section_components):
                    question = component.get("question") or component.get("title") or section.get("title")
                    chart_schema = component.get("schema") or component.get("chart_schema") or component.get("config")
                    data = component.get("data") or component.get("values") or {}
                    summary = section.get("summary") or component.get("summary")
                    
                    event = ReportSnapshotEvent(
                        report_id=report_id,
                        workflow_id=workflow_id,
                        user_id=user_id,
                        question=question,
                        chart_schema=chart_schema,
                        data=data if isinstance(data, dict) else {"value": data},
                        summary=summary,
                        component_type="section_component",
                        sequence_order=section_idx * 100 + idx,  # Order by section then component
                        metadata={
                            **(metadata_tags or {}),
                            "section_title": section.get("title"),
                            "section_index": section_idx,
                        },
                        event_timestamp=event_timestamp
                    )
                    
                    self.db.add(event)
                    events.append(event)
        
        # Process charts directly if available
        if not components and not sections and charts:
            for idx, chart in enumerate(charts):
                question = chart.get("question") or chart.get("title") or chart.get("query")
                chart_schema = chart.get("schema") or chart.get("chart_schema") or chart.get("config")
                data = chart.get("data") or chart.get("values") or {}
                
                event = ReportSnapshotEvent(
                    report_id=report_id,
                    workflow_id=workflow_id,
                    user_id=user_id,
                    question=question,
                    chart_schema=chart_schema,
                    data=data if isinstance(data, dict) else {"value": data},
                    component_type="chart",
                    sequence_order=chart.get("order") or idx,
                    metadata={
                        **(metadata_tags or {}),
                        "chart_config": chart.get("config"),
                    },
                    event_timestamp=event_timestamp
                )
                
                self.db.add(event)
                events.append(event)
        
        if events:
            await self.db.commit()
            for event in events:
                await self.db.refresh(event)
        
        return events
    
    async def get_event(
        self,
        user_id: UUID,
        event_id: UUID
    ) -> Optional[ReportSnapshotEvent]:
        """Get a specific report snapshot event by ID"""
        
        stmt = select(ReportSnapshotEvent).where(ReportSnapshotEvent.id == event_id)
        result = await self.db.execute(stmt)
        event = result.scalar_one_or_none()
        
        if not event:
            return None
        
        # Verify user has access to the report
        report = await self.get_report(user_id, event.report_id)
        if not report:
            raise PermissionError("User doesn't have access to this event")
        
        return event
    
    async def get_events_by_time(
        self,
        user_id: UUID,
        report_id: UUID,
        timestamp: Optional[datetime] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        exact_timestamp: bool = False,
        tolerance_seconds: int = 60
    ) -> List[ReportSnapshotEvent]:
        """Get report snapshot events by time criteria
        
        Args:
            user_id: User ID for permission check
            report_id: Report ID to filter events
            timestamp: Get events at this specific timestamp (if exact_timestamp=True) or around this time
            start_time: Get events after this time
            end_time: Get events before this time
            exact_timestamp: If True, only get events at exact timestamp; if False, use tolerance_seconds
            tolerance_seconds: Seconds tolerance when timestamp is provided (default: 60 seconds)
        
        Returns:
            List of events matching the time criteria
        """
        
        # Verify access to report
        report = await self.get_report(user_id, report_id)
        if not report:
            raise PermissionError("User doesn't have access to this report")
        
        # Build query conditions
        conditions = [ReportSnapshotEvent.report_id == report_id]
        
        if timestamp:
            if exact_timestamp:
                # Get events at exact timestamp
                conditions.append(ReportSnapshotEvent.event_timestamp == timestamp)
            else:
                # Get events within tolerance window
                tolerance_delta = timedelta(seconds=tolerance_seconds)
                conditions.append(
                    and_(
                        ReportSnapshotEvent.event_timestamp >= timestamp - tolerance_delta,
                        ReportSnapshotEvent.event_timestamp <= timestamp + tolerance_delta
                    )
                )
        
        if start_time:
            conditions.append(ReportSnapshotEvent.event_timestamp >= start_time)
        
        if end_time:
            conditions.append(ReportSnapshotEvent.event_timestamp <= end_time)
        
        # If only start_time is provided, no end limit
        # If only end_time is provided, no start limit
        # If both are provided, use range
        # If timestamp is provided, use it with tolerance or exact
        
        stmt = select(ReportSnapshotEvent).where(
            and_(*conditions)
        ).order_by(ReportSnapshotEvent.event_timestamp.desc())
        
        result = await self.db.execute(stmt)
        events = result.scalars().all()
        
        return list(events)
    
    async def get_event_at_time(
        self,
        user_id: UUID,
        report_id: UUID,
        timestamp: datetime,
        question: Optional[str] = None,
        component_id: Optional[UUID] = None,
        tolerance_seconds: int = 60
    ) -> Optional[ReportSnapshotEvent]:
        """Get the closest event to a specific timestamp
        
        Args:
            user_id: User ID for permission check
            report_id: Report ID to filter events
            timestamp: Target timestamp
            question: Optional question filter to get specific question's event
            component_id: Optional component ID filter
            tolerance_seconds: Maximum seconds difference allowed (default: 60)
        
        Returns:
            Closest event to the timestamp, or None if none found within tolerance
        """
        
        # Verify access to report
        report = await self.get_report(user_id, report_id)
        if not report:
            raise PermissionError("User doesn't have access to this report")
        
        # Build query conditions
        conditions = [ReportSnapshotEvent.report_id == report_id]
        
        if question:
            conditions.append(ReportSnapshotEvent.question == question)
        
        if component_id:
            conditions.append(ReportSnapshotEvent.component_id == component_id)
        
        # Get events within tolerance window
        tolerance_delta = timedelta(seconds=tolerance_seconds)
        conditions.append(
            and_(
                ReportSnapshotEvent.event_timestamp >= timestamp - tolerance_delta,
                ReportSnapshotEvent.event_timestamp <= timestamp + tolerance_delta
            )
        )
        
        # Order by absolute time difference to get closest event
        # Use PostgreSQL's ABS with EXTRACT EPOCH for time difference
        time_diff_expr = func.abs(
            func.extract('epoch', ReportSnapshotEvent.event_timestamp - func.cast(timestamp, func.DateTime))
        )
        
        stmt = select(ReportSnapshotEvent).where(
            and_(*conditions)
        ).order_by(time_diff_expr).limit(1)
        
        result = await self.db.execute(stmt)
        event = result.scalar_one_or_none()
        
        return event
    
    async def list_events(
        self,
        user_id: UUID,
        report_id: Optional[UUID] = None,
        workflow_id: Optional[UUID] = None,
        component_id: Optional[UUID] = None,
        question: Optional[str] = None,
        component_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """List report snapshot events with filtering and pagination for change tracking"""
        
        # Build query
        conditions = []
        
        if report_id:
            conditions.append(ReportSnapshotEvent.report_id == report_id)
        
        if workflow_id:
            conditions.append(ReportSnapshotEvent.workflow_id == workflow_id)
        
        if component_id:
            conditions.append(ReportSnapshotEvent.component_id == component_id)
        
        if question:
            conditions.append(ReportSnapshotEvent.question.ilike(f"%{question}%"))
        
        if component_type:
            conditions.append(ReportSnapshotEvent.component_type == component_type)
        
        if start_date:
            conditions.append(ReportSnapshotEvent.event_timestamp >= start_date)
        
        if end_date:
            conditions.append(ReportSnapshotEvent.event_timestamp <= end_date)
        
        stmt = select(ReportSnapshotEvent)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        
        # Order by timestamp descending
        stmt = stmt.order_by(ReportSnapshotEvent.event_timestamp.desc())
        
        # Apply pagination
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)
        
        # Execute query
        result = await self.db.execute(stmt)
        events = result.scalars().all()
        
        # Filter by user access - only return events for reports user can access
        accessible_events = []
        for event in events:
            try:
                report = await self.get_report(user_id, event.report_id)
                if report:
                    accessible_events.append(event)
            except PermissionError:
                # Skip events user doesn't have access to
                continue
        
        return {
            "events": accessible_events,
            "total": len(accessible_events),
            "page": page,
            "page_size": page_size,
            "total_pages": (len(accessible_events) + page_size - 1) // page_size
        }
    
    async def get_events_by_question(
        self,
        user_id: UUID,
        report_id: UUID,
        question: str,
        limit: int = 10
    ) -> List[ReportSnapshotEvent]:
        """Get historical events for a specific question - useful for change tracking and insights"""
        
        # Verify access
        report = await self.get_report(user_id, report_id)
        if not report:
            raise PermissionError("User doesn't have access to this report")
        
        stmt = select(ReportSnapshotEvent).where(
            and_(
                ReportSnapshotEvent.report_id == report_id,
                ReportSnapshotEvent.question == question
            )
        ).order_by(ReportSnapshotEvent.event_timestamp.desc()).limit(limit)
        
        result = await self.db.execute(stmt)
        events = result.scalars().all()
        
        return list(events)
    
    async def compare_events(
        self,
        user_id: UUID,
        event_id_1: UUID,
        event_id_2: UUID
    ) -> Dict[str, Any]:
        """Compare two events to identify changes - useful for change detection"""
        
        event1 = await self.get_event(user_id, event_id_1)
        event2 = await self.get_event(user_id, event_id_2)
        
        if not event1 or not event2:
            raise ValueError("One or both events not found or access denied")
        
        if event1.report_id != event2.report_id:
            raise ValueError("Events must be from the same report")
        
        # Compare data, chart_schema, summary
        changes = {
            "data_changed": event1.data != event2.data,
            "chart_schema_changed": event1.chart_schema != event2.chart_schema,
            "summary_changed": event1.summary != event2.summary,
            "executive_summary_changed": event1.executive_summary != event2.executive_summary,
            "sql_query_changed": event1.sql_query != event2.sql_query,
            "time_difference_seconds": abs((event1.event_timestamp - event2.event_timestamp).total_seconds()),
            "earlier_event": str(event1.id) if event1.event_timestamp < event2.event_timestamp else str(event2.id),
            "later_event": str(event2.id) if event1.event_timestamp < event2.event_timestamp else str(event1.id)
        }
        
        return changes
import traceback
from typing import Optional, List, Dict, Any, Union
from uuid import UUID
import uuid
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, func, select
from app.services.baseservice import BaseService, SharingPermission
from app.models.dbmodels import Dashboard, DashboardVersion, DashboardSnapshot
from app.models.thread import Thread, Workflow
from app.models.workspace import Workspace, Project
from app.models.schema import (
    DashboardCreate, DashboardUpdate, DashboardResponse, 
    DashboardSnapshotCreate, DashboardSnapshotResponse,
    DashboardOutputFormat, DashboardSnapshotEventsCreate,
    DashboardSnapshotEventCreate, DashboardSnapshotEventResponse
)
from app.models.dbmodels import DashboardSnapshotEvent
from app.models.workflowmodels import ThreadComponent, DashboardWorkflow
import json
class DashboardService(BaseService):
    """Service for managing dashboards with workflow integration"""
    
    def __init__(self, db: AsyncSession, chroma_client=None):
        super().__init__(db, chroma_client)
        self.collection_name = "dashboards"
    
    async def create_dashboard(
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
        if project_id and not await self._check_user_permission(
            user_id, "project", project_id, "create"
        ):
            raise PermissionError("User doesn't have permission to create dashboard in this project")
        
        if workspace_id and not await self._check_user_permission(
            user_id, "workspace", workspace_id, "create"
        ):
            raise PermissionError("User doesn't have permission to create dashboard in this workspace")
        print("crossed all the db conditions")
        # Validate workflow exists and user has access
        if workflow_id:
            print("Entered if worlflowid")
            stmt = select(Workflow).where(Workflow.id == workflow_id)
            result = await self.db.execute(stmt)
            workflow = result.scalar_one_or_none()
            
            if not workflow:
                raise ValueError(f"Workflow {workflow_id} not found")
            if workflow.user_id != user_id and not await self._check_user_permission(
                user_id, "thread", workflow.thread_id, "read"
            ):
                raise PermissionError("User doesn't have access to this workflow")
        try:

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
            await self.db.flush()
            
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
                "shared_with": [str(uid) for uid in shared_with] if shared_with else None
            }
            if isinstance(metadata['shared_with'], list):
                metadata['shared_with'] = json.dumps(metadata['shared_with'])  
            metadata = {k: v for k, v in metadata.items() if v is not None}
            print(f"Metadata is {metadata}")
            
            # Add to ChromaDB for searchability
            await self._add_to_chroma(
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
            
            await self.db.commit()
            return dashboard
        except Exception as e:
            traceback.print_exc()
    
    async def get_dashboard(
        self,
        user_id: UUID,
        dashboard_id: UUID
    ) -> Optional[Dashboard]:
        """Get dashboard by ID with permission check"""
        
        stmt = select(Dashboard).where(Dashboard.id == dashboard_id)
        result = await self.db.execute(stmt)
        dashboard = result.scalar_one_or_none()
        
        if not dashboard:
            return None
        
        # Check permissions via ChromaDB metadata
        collection = await self._create_chroma_collection(self.collection_name)
        result = collection.get(ids=[str(dashboard_id)])
        
        if not result["ids"]:
            return None
        
        metadata = result["metadatas"][0]
        
        # Check access permissions
        if not await self._has_dashboard_access(user_id, metadata):
            raise PermissionError("User doesn't have access to this dashboard")
        
        return dashboard
    
    async def update_dashboard(
        self,
        user_id: UUID,
        dashboard_id: UUID,
        update_data: DashboardUpdate,
        create_version: bool = True
    ) -> Dashboard:
        """Update dashboard with optional versioning"""
        
        dashboard = await self.get_dashboard(user_id, dashboard_id)
        if not dashboard:
            raise ValueError(f"Dashboard {dashboard_id} not found")
        
        # Check update permission
        collection = await self._create_chroma_collection(self.collection_name)
        result = collection.get(ids=[str(dashboard_id)])
        metadata = result["metadatas"][0]
        
        if metadata["created_by"] != str(user_id) and not await self._check_user_permission(
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
        await self._update_chroma(
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
        
        await self.db.commit()
        return dashboard
    
    async def delete_dashboard(
        self,
        user_id: UUID,
        dashboard_id: UUID
    ) -> bool:
        """Delete dashboard with permission check"""
        
        dashboard = await self.get_dashboard(user_id, dashboard_id)
        if not dashboard:
            return False
        
        # Check delete permission
        collection = await self._create_chroma_collection(self.collection_name)
        result = collection.get(ids=[str(dashboard_id)])
        metadata = result["metadatas"][0]
        
        if metadata["created_by"] != str(user_id) and not await self._check_user_permission(
            user_id, "dashboard", dashboard_id, "delete"
        ):
            raise PermissionError("User doesn't have permission to delete this dashboard")
        
        # Delete from ChromaDB
        await self._delete_from_chroma(self.collection_name, str(dashboard_id))
        
        # Delete from PostgreSQL (versions will cascade)
        await self.db.delete(dashboard)
        await self.db.commit()
        
        return True
    
    async def search_dashboards(
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
        results = await self._search_chroma(
            self.collection_name,
            query,
            filters,
            limit * 2  # Get more results for permission filtering
        )
        
        # Filter by permissions
        accessible_results = []
        for result in results:
            if await self._has_dashboard_access(user_id, result["metadata"]):
                dashboard_id = UUID(result["id"])
                stmt = select(Dashboard).where(Dashboard.id == dashboard_id)
                result_obj = await self.db.execute(stmt)
                dashboard = result_obj.scalar_one_or_none()
                
                if dashboard:
                    accessible_results.append({
                        "dashboard": dashboard,
                        "metadata": result["metadata"],
                        "relevance_score": 1 - result["distance"] if result["distance"] else 1
                    })
                    if len(accessible_results) >= limit:
                        break
        
        return accessible_results
    
    async def list_user_dashboards(
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
        accessible_dashboards = []
        for i, doc_id in enumerate(all_results["ids"]):
            metadata = all_results["metadatas"][i]
            
            # Check if user has access
            if await self._has_dashboard_access(user_id, metadata, include_shared):
                dashboard_id = UUID(doc_id)
                stmt = select(Dashboard).where(Dashboard.id == dashboard_id)
                result = await self.db.execute(stmt)
                dashboard = result.scalar_one_or_none()
                
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
    
    async def share_dashboard(
        self,
        user_id: UUID,
        dashboard_id: UUID,
        share_with: List[UUID],
        permission_level: SharingPermission = SharingPermission.USER
    ) -> bool:
        """Share dashboard with users/teams/workspace"""
        
        # Get dashboard and check ownership
        collection = await self._create_chroma_collection(self.collection_name)
        result =  collection.get(ids=[str(dashboard_id)])
        print("I am in Share Dashboard")
        if not result["ids"]:
            raise ValueError(f"Dashboard {dashboard_id} not found")
        
        metadata = result["metadatas"][0]
        
        if metadata["created_by"] != str(user_id):
            raise PermissionError("Only dashboard owner can share it")
        
        # Update sharing permissions
        metadata["sharing_permission"] = permission_level.value
        metadata["shared_with"] = [str(uid) for uid in share_with]
        metadata["shared_with"] = json.dumps(metadata["shared_with"])
        # Update in ChromaDB
        stmt = select(Dashboard).where(Dashboard.id == dashboard_id)
        result = await self.db.execute(stmt)
        dashboard = result.scalar_one_or_none()
        
        await self._update_chroma(
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
    
    async def get_dashboard_versions(
        self,
        user_id: UUID,
        dashboard_id: UUID
    ) -> List[DashboardVersion]:
        """Get all versions of a dashboard"""
        
        # Check access permission
        dashboard = await self.get_dashboard(user_id, dashboard_id)
        if not dashboard:
            raise ValueError(f"Dashboard {dashboard_id} not found or access denied")
        
        stmt = select(DashboardVersion).where(
            DashboardVersion.dashboard_id == dashboard_id
        ).order_by(DashboardVersion.created_at.desc())
        result = await self.db.execute(stmt)
        versions = result.scalars().all()
        
        return versions
    
    async def restore_dashboard_version(
        self,
        user_id: UUID,
        dashboard_id: UUID,
        version_id: UUID
    ) -> Dashboard:
        """Restore a specific version of dashboard"""
        
        dashboard = await self.get_dashboard(user_id, dashboard_id)
        if not dashboard:
            raise ValueError(f"Dashboard {dashboard_id} not found")
        
        # Check update permission
        collection = await self._create_chroma_collection(self.collection_name)
        result = collection.get(ids=[str(dashboard_id)])
        metadata = result["metadatas"][0]
        
        if metadata["created_by"] != str(user_id) and not await self._check_user_permission(
            user_id, "dashboard", dashboard_id, "update"
        ):
            raise PermissionError("User doesn't have permission to restore dashboard version")
        
        # Get the version to restore
        stmt = select(DashboardVersion).where(
            and_(
                DashboardVersion.id == version_id,
                DashboardVersion.dashboard_id == dashboard_id
            )
        )
        result = await self.db.execute(stmt)
        version = result.scalar_one_or_none()
        
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
        
        await self.db.commit()
        return dashboard
    
    async def _has_dashboard_access(
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
    
    async def create_snapshot_events(
        self,
        user_id: UUID,
        events_data: DashboardSnapshotEventsCreate
    ) -> List[DashboardSnapshotEvent]:
        """Create snapshot events from questions/charts - one event per question/chart for change tracking"""
        
        # Get dashboard and verify access
        dashboard = await self.get_dashboard(user_id, events_data.dashboard_id)
        if not dashboard:
            raise ValueError(f"Dashboard {events_data.dashboard_id} not found or access denied")
        
        # Create events for each question/chart
        events = []
        event_timestamp = datetime.utcnow()
        
        for event_data in events_data.events:
            # Merge common metadata with event-specific metadata
            merged_metadata = {**(events_data.metadata_tags or {}), **(event_data.event_metadata or {})}
            
            event = DashboardSnapshotEvent(
                dashboard_id=events_data.dashboard_id,
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
        dashboard_id: UUID,
        workflow_id: Optional[UUID],
        output_format: Union[DashboardOutputFormat, Dict[str, Any]],
        metadata_tags: Optional[Dict[str, Any]] = None
    ) -> List[DashboardSnapshotEvent]:
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
        
        # Extract dashboard_data which contains components
        dashboard_data = output_dict.get("dashboard_data") or {}
        chart_configurations = output_dict.get("chart_configurations") or {}
        conditional_formatting = output_dict.get("conditional_formatting") or {}
        
        # Try to extract questions/charts from dashboard_data
        # The structure might have components, charts, or queries
        components = dashboard_data.get("components", [])
        charts = dashboard_data.get("charts", [])
        queries = dashboard_data.get("queries", [])
        
        # Process components from dashboard_data
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
            
            event = DashboardSnapshotEvent(
                dashboard_id=dashboard_id,
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
        
        # Process charts directly if available
        if not components and charts:
            for idx, chart in enumerate(charts):
                question = chart.get("question") or chart.get("title") or chart.get("query")
                chart_schema = chart.get("schema") or chart.get("chart_schema") or chart.get("config")
                data = chart.get("data") or chart.get("values") or {}
                
                event = DashboardSnapshotEvent(
                    dashboard_id=dashboard_id,
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
        
        # Process queries if available
        if not components and not charts and queries:
            for idx, query in enumerate(queries):
                question = query.get("query") or query.get("question")
                chart_schema = query.get("chart_schema")
                data = query.get("data") or {}
                sql_query = query.get("sql")
                
                event = DashboardSnapshotEvent(
                    dashboard_id=dashboard_id,
                    workflow_id=workflow_id,
                    user_id=user_id,
                    question=question,
                    query_text=question,
                    sql_query=sql_query,
                    chart_schema=chart_schema,
                    data=data if isinstance(data, dict) else {"value": data},
                    component_type="query",
                    sequence_order=idx,
                    metadata=metadata_tags or {},
                    event_timestamp=event_timestamp
                )
                
                self.db.add(event)
                events.append(event)
        
        if events:
            await self.db.commit()
            for event in events:
                await self.db.refresh(event)
        
        return events
    
    async def get_snapshot(
        self,
        user_id: UUID,
        snapshot_id: UUID
    ) -> Optional[DashboardSnapshot]:
        """Get a specific dashboard snapshot by ID"""
        
        stmt = select(DashboardSnapshot).where(DashboardSnapshot.id == snapshot_id)
        result = await self.db.execute(stmt)
        snapshot = result.scalar_one_or_none()
        
        if not snapshot:
            return None
        
        # Verify user has access to the dashboard
        dashboard = await self.get_dashboard(user_id, snapshot.dashboard_id)
        if not dashboard:
            raise PermissionError("User doesn't have access to this snapshot")
        
        return snapshot
    
    async def list_snapshots(
        self,
        user_id: UUID,
        dashboard_id: Optional[UUID] = None,
        workflow_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        metadata_tags: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """List dashboard snapshots with filtering and pagination"""
        
        # Build query
        conditions = []
        
        if dashboard_id:
            conditions.append(DashboardSnapshot.dashboard_id == dashboard_id)
        
        if workflow_id:
            conditions.append(DashboardSnapshot.workflow_id == workflow_id)
        
        if start_date:
            conditions.append(DashboardSnapshot.snapshot_timestamp >= start_date)
        
        if end_date:
            conditions.append(DashboardSnapshot.snapshot_timestamp <= end_date)
        
        if metadata_tags:
            # Filter by metadata tags (JSONB contains)
            for key, value in metadata_tags.items():
                conditions.append(
                    DashboardSnapshot.metadata_tags[key].astext == str(value)
                )
        
        stmt = select(DashboardSnapshot)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        
        # Order by timestamp descending
        stmt = stmt.order_by(DashboardSnapshot.snapshot_timestamp.desc())
        
        # Apply pagination
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)
        
        # Execute query
        result = await self.db.execute(stmt)
        snapshots = result.scalars().all()
        
        # Filter by user access - only return snapshots for dashboards user can access
        accessible_snapshots = []
        for snapshot in snapshots:
            try:
                dashboard = await self.get_dashboard(user_id, snapshot.dashboard_id)
                if dashboard:
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
        """Delete a dashboard snapshot"""
        
        snapshot = await self.get_snapshot(user_id, snapshot_id)
        if not snapshot:
            return False
        
        # Check if user created the snapshot or has dashboard delete permission
        if snapshot.user_id != user_id:
            collection = await self._create_chroma_collection(self.collection_name)
            result = collection.get(ids=[str(snapshot.dashboard_id)])
            if result["ids"]:
                metadata = result["metadatas"][0]
                if not await self._check_user_permission(
                    user_id, "dashboard", snapshot.dashboard_id, "delete"
                ):
                    raise PermissionError("User doesn't have permission to delete this snapshot")
        
        self.db.delete(snapshot)
        await self.db.commit()
        
        return True
    
    async def get_event(
        self,
        user_id: UUID,
        event_id: UUID
    ) -> Optional[DashboardSnapshotEvent]:
        """Get a specific dashboard snapshot event by ID"""
        
        stmt = select(DashboardSnapshotEvent).where(DashboardSnapshotEvent.id == event_id)
        result = await self.db.execute(stmt)
        event = result.scalar_one_or_none()
        
        if not event:
            return None
        
        # Verify user has access to the dashboard
        dashboard = await self.get_dashboard(user_id, event.dashboard_id)
        if not dashboard:
            raise PermissionError("User doesn't have access to this event")
        
        return event
    
    async def get_events_by_time(
        self,
        user_id: UUID,
        dashboard_id: UUID,
        timestamp: Optional[datetime] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        exact_timestamp: bool = False,
        tolerance_seconds: int = 60
    ) -> List[DashboardSnapshotEvent]:
        """Get dashboard snapshot events by time criteria
        
        Args:
            user_id: User ID for permission check
            dashboard_id: Dashboard ID to filter events
            timestamp: Get events at this specific timestamp (if exact_timestamp=True) or around this time
            start_time: Get events after this time
            end_time: Get events before this time
            exact_timestamp: If True, only get events at exact timestamp; if False, use tolerance_seconds
            tolerance_seconds: Seconds tolerance when timestamp is provided (default: 60 seconds)
        
        Returns:
            List of events matching the time criteria
        """
        
        # Verify access to dashboard
        dashboard = await self.get_dashboard(user_id, dashboard_id)
        if not dashboard:
            raise PermissionError("User doesn't have access to this dashboard")
        
        # Build query conditions
        conditions = [DashboardSnapshotEvent.dashboard_id == dashboard_id]
        
        if timestamp:
            if exact_timestamp:
                # Get events at exact timestamp
                conditions.append(DashboardSnapshotEvent.event_timestamp == timestamp)
            else:
                # Get events within tolerance window
                tolerance_delta = timedelta(seconds=tolerance_seconds)
                conditions.append(
                    and_(
                        DashboardSnapshotEvent.event_timestamp >= timestamp - tolerance_delta,
                        DashboardSnapshotEvent.event_timestamp <= timestamp + tolerance_delta
                    )
                )
        
        if start_time:
            conditions.append(DashboardSnapshotEvent.event_timestamp >= start_time)
        
        if end_time:
            conditions.append(DashboardSnapshotEvent.event_timestamp <= end_time)
        
        # If only start_time is provided, no end limit
        # If only end_time is provided, no start limit
        # If both are provided, use range
        # If timestamp is provided, use it with tolerance or exact
        
        stmt = select(DashboardSnapshotEvent).where(
            and_(*conditions)
        ).order_by(DashboardSnapshotEvent.event_timestamp.desc())
        
        result = await self.db.execute(stmt)
        events = result.scalars().all()
        
        return list(events)
    
    async def get_event_at_time(
        self,
        user_id: UUID,
        dashboard_id: UUID,
        timestamp: datetime,
        question: Optional[str] = None,
        component_id: Optional[UUID] = None,
        tolerance_seconds: int = 60
    ) -> Optional[DashboardSnapshotEvent]:
        """Get the closest event to a specific timestamp
        
        Args:
            user_id: User ID for permission check
            dashboard_id: Dashboard ID to filter events
            timestamp: Target timestamp
            question: Optional question filter to get specific question's event
            component_id: Optional component ID filter
            tolerance_seconds: Maximum seconds difference allowed (default: 60)
        
        Returns:
            Closest event to the timestamp, or None if none found within tolerance
        """
        
        # Verify access to dashboard
        dashboard = await self.get_dashboard(user_id, dashboard_id)
        if not dashboard:
            raise PermissionError("User doesn't have access to this dashboard")
        
        # Build query conditions
        conditions = [DashboardSnapshotEvent.dashboard_id == dashboard_id]
        
        if question:
            conditions.append(DashboardSnapshotEvent.question == question)
        
        if component_id:
            conditions.append(DashboardSnapshotEvent.component_id == component_id)
        
        # Get events within tolerance window
        tolerance_delta = timedelta(seconds=tolerance_seconds)
        conditions.append(
            and_(
                DashboardSnapshotEvent.event_timestamp >= timestamp - tolerance_delta,
                DashboardSnapshotEvent.event_timestamp <= timestamp + tolerance_delta
            )
        )
        
        # Order by absolute time difference to get closest event
        # Use PostgreSQL's ABS with EXTRACT EPOCH for time difference
        time_diff_expr = func.abs(
            func.extract('epoch', DashboardSnapshotEvent.event_timestamp - func.cast(timestamp, func.DateTime))
        )
        
        stmt = select(DashboardSnapshotEvent).where(
            and_(*conditions)
        ).order_by(time_diff_expr).limit(1)
        
        result = await self.db.execute(stmt)
        event = result.scalar_one_or_none()
        
        return event
    
    async def list_events(
        self,
        user_id: UUID,
        dashboard_id: Optional[UUID] = None,
        workflow_id: Optional[UUID] = None,
        component_id: Optional[UUID] = None,
        question: Optional[str] = None,
        component_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """List dashboard snapshot events with filtering and pagination for change tracking"""
        
        # Build query
        conditions = []
        
        if dashboard_id:
            conditions.append(DashboardSnapshotEvent.dashboard_id == dashboard_id)
        
        if workflow_id:
            conditions.append(DashboardSnapshotEvent.workflow_id == workflow_id)
        
        if component_id:
            conditions.append(DashboardSnapshotEvent.component_id == component_id)
        
        if question:
            conditions.append(DashboardSnapshotEvent.question.ilike(f"%{question}%"))
        
        if component_type:
            conditions.append(DashboardSnapshotEvent.component_type == component_type)
        
        if start_date:
            conditions.append(DashboardSnapshotEvent.event_timestamp >= start_date)
        
        if end_date:
            conditions.append(DashboardSnapshotEvent.event_timestamp <= end_date)
        
        stmt = select(DashboardSnapshotEvent)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        
        # Order by timestamp descending
        stmt = stmt.order_by(DashboardSnapshotEvent.event_timestamp.desc())
        
        # Apply pagination
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)
        
        # Execute query
        result = await self.db.execute(stmt)
        events = result.scalars().all()
        
        # Filter by user access - only return events for dashboards user can access
        accessible_events = []
        for event in events:
            try:
                dashboard = await self.get_dashboard(user_id, event.dashboard_id)
                if dashboard:
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
        dashboard_id: UUID,
        question: str,
        limit: int = 10
    ) -> List[DashboardSnapshotEvent]:
        """Get historical events for a specific question - useful for change tracking and insights"""
        
        # Verify access
        dashboard = await self.get_dashboard(user_id, dashboard_id)
        if not dashboard:
            raise PermissionError("User doesn't have access to this dashboard")
        
        stmt = select(DashboardSnapshotEvent).where(
            and_(
                DashboardSnapshotEvent.dashboard_id == dashboard_id,
                DashboardSnapshotEvent.question == question
            )
        ).order_by(DashboardSnapshotEvent.event_timestamp.desc()).limit(limit)
        
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
        
        if event1.dashboard_id != event2.dashboard_id:
            raise ValueError("Events must be from the same dashboard")
        
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
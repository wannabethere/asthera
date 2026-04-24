from typing import Optional, List, Dict, Any, Tuple
from fastapi import HTTPException
from uuid import UUID
import asyncio
import uuid
from datetime import datetime, timedelta,timezone
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy import and_, or_, func, select, sql,delete
import traceback
from app.services.baseservice import BaseService, SharingPermission
from app.services.dashboardservice import DashboardService
from app.services.n8n_workflow_creator import N8nWorkflowCreator
from app.models.workflowmodels import (
    DashboardWorkflow, DashboardTemplate, ThreadComponent, ShareConfiguration,
    ScheduleConfiguration, IntegrationConfig, WorkflowVersion,
    WorkflowState, ComponentType, ShareType, ScheduleType, IntegrationType,
    ThreadComponentCreate, ThreadComponentUpdate, ShareConfigCreate,
    ScheduleConfigCreate, IntegrationConfigCreate, AlertType, AlertSeverity,
    AlertStatus, AlertThreadComponentCreate, AlertThreadComponentUpdate,ReportWorkflow
)
from app.models.thread import Thread, ThreadMessage
from app.models.dbmodels import Dashboard, DashboardVersion
from app.models.schema import DashboardCreate, DashboardUpdate
from app.models.workspace import ProjectAccess, Project
from app.models.user import User
from app.models.team import Team
from sqlalchemy import and_, or_

# ── Preview-item → ComponentType mapping ─────────────────────────────────────
# "kpi" is not a valid ComponentType value; map it to "metric".
_PREVIEW_COMPONENT_TYPE_MAP: dict[str, str] = {
    "metric": "metric",
    "kpi": "metric",
    "table": "table",
    "chart": "chart",
}


def _build_initial_dashboard_content(
    template_data: dict,
    layout_id: str,
    preview_items: list[dict],
    status: str = "draft",
) -> dict:
    """Build the structured dashboard.content JSON synchronously from template + preview items.

    Called at workflow creation time so the dashboard is persisted with the right
    content on the very first commit — no second round-trip needed.
    """
    kpis: list = list(template_data.get("kpis") or [])
    charts: list = list(template_data.get("charts") or [])
    overview: str = template_data.get("overview") or ""
    executive_summary: str = template_data.get("executive_summary") or ""
    insights: list = list(template_data.get("insights") or [])

    kpi_index = 0
    chart_index = 0

    for i, preview in enumerate(preview_items):
        if not isinstance(preview, dict):
            continue
        item_type: str = preview.get("item_type") or "metric"
        chart_cfg: dict = preview.get("chart_config") or {
            "title": preview.get("name") or "",
            "chart_type": preview.get("chart_type"),
            "trend_direction": preview.get("trend_direction"),
            "insights": preview.get("insights") or [],
            "explanation": preview.get("explanation") or "",
            "source_schemas": preview.get("source_schemas") or [],
            "focus_area": preview.get("focus_area") or "",
        }
        if preview.get("vega_lite_spec") and "vega_lite_spec" not in chart_cfg:
            chart_cfg["vega_lite_spec"] = preview["vega_lite_spec"]

        if item_type == "kpi":
            kpi_entry = {
                "name": chart_cfg.get("title") or preview.get("name") or f"KPI {kpi_index + 1}",
                "value": None,
                "trend": chart_cfg.get("trend_direction") or preview.get("trend_direction"),
                "status": "ok",
                "description": preview.get("summary") or preview.get("description") or "",
                "insights": chart_cfg.get("insights") or preview.get("insights") or [],
                "visualization_data": preview.get("result_data"),
                "chart_schema": preview.get("vega_lite_spec"),
            }
            kpi_entry = {k: v for k, v in kpi_entry.items() if v is not None}
            if kpi_index < len(kpis):
                kpis[kpi_index] = {**kpis[kpi_index], **kpi_entry}
            else:
                kpis.append(kpi_entry)
            kpi_index += 1
        else:
            vega_spec = preview.get("vega_lite_spec") or chart_cfg.get("vega_lite_spec")
            chart_entry = {
                "type": chart_cfg.get("chart_type") or preview.get("chart_type") or item_type,
                "title": chart_cfg.get("title") or preview.get("name") or f"Chart {chart_index + 1}",
                "overview": preview.get("summary") or preview.get("description") or chart_cfg.get("explanation") or "",
                "insights": chart_cfg.get("insights") or preview.get("insights") or [],
                "source_schemas": chart_cfg.get("source_schemas") or preview.get("source_schemas") or [],
                "focus_area": chart_cfg.get("focus_area") or preview.get("focus_area") or "",
                "visualization_data": preview.get("result_data"),
                **({"chart_schema": vega_spec} if vega_spec else {}),
            }
            chart_entry = {k: v for k, v in chart_entry.items() if v is not None}
            if chart_index < len(charts):
                charts[chart_index] = {**charts[chart_index], **chart_entry}
            else:
                charts.append(chart_entry)
            chart_index += 1

    return {
        "status": status,
        "layout_id": layout_id,
        "overview": overview,
        "executive_summary": executive_summary,
        "kpis": kpis,
        "charts": charts,
        "insights": insights,
    }


def _build_components_from_preview(preview_items: list[dict]) -> list[ThreadComponentCreate]:
    """Convert preview card dicts (from the Dashboard Creator Wizard) into
    ThreadComponentCreate objects ready for add_thread_components."""
    result = []
    for i, preview in enumerate(preview_items):
        if not isinstance(preview, dict):
            continue
        item_type: str = preview.get("item_type") or "metric"
        component_type_str = _PREVIEW_COMPONENT_TYPE_MAP.get(item_type, "metric")
        try:
            component_type = ComponentType(component_type_str)
        except ValueError:
            component_type = ComponentType.METRIC

        chart_cfg: dict = {
            "title": preview.get("name") or "",
            "chart_type": preview.get("chart_type"),
            "trend_direction": preview.get("trend_direction"),
            "insights": preview.get("insights") or [],
            "explanation": preview.get("explanation") or "",
            "source_schemas": preview.get("source_schemas") or [],
            "focus_area": preview.get("focus_area") or "",
        }
        if preview.get("vega_lite_spec"):
            chart_cfg["vega_lite_spec"] = preview["vega_lite_spec"]

        result.append(ThreadComponentCreate(
            component_type=component_type,
            question=preview.get("nl_question") or preview.get("name") or f"Item {i + 1}",
            description=preview.get("summary") or preview.get("description") or "",
            chart_config=chart_cfg,
            visualization_data=preview.get("result_data"),
            metadata={"item_type": item_type, "source": "dashboard_creator_wizard"},
        ))
    return result


class DashboardWorkflowService(BaseService):
    """Service for managing dashboard creation workflows"""

    def __init__(self, db: AsyncSession, chroma_client=None):
        super().__init__(db, chroma_client)
        self.collection_name = "dashboard_workflow"
        self.dashboard_service = DashboardService(db, chroma_client)
        self.n8n_creator = N8nWorkflowCreator()

    async def create_workflow(
        self,
        user_id: UUID,
        dashboard_name: str,
        dashboard_description: str,
        project_id: Optional[UUID] = None,
        workspace_id: Optional[UUID] = None,
        initial_metadata: Dict[str, Any] = None
    ) -> Tuple[DashboardWorkflow, Dashboard]:
        """
        Create a placeholder dashboard + workflow record.

        If initial_metadata contains a ``preview_items`` list (forwarded by the
        Dashboard Creator Wizard), those items are automatically converted to
        ThreadComponent rows via add_thread_components so the caller does not
        need a separate step.  preview_items is stripped from workflow_metadata
        before persisting to avoid storing large blobs there.
        """
        try:
            meta: dict = dict(initial_metadata or {})
            preview_items: list = meta.pop("preview_items", None) or []

            # Build the initial dashboard content synchronously so the correct
            # structured JSON is persisted on the very first commit.
            template_data: dict = meta.get("template_data") or {}
            layout_id: str = meta.get("layout_id") or ""
            if template_data and preview_items:
                initial_content = _build_initial_dashboard_content(
                    template_data=template_data,
                    layout_id=layout_id,
                    preview_items=preview_items,
                )
            else:
                initial_content = {"status": "draft", "components": []}

            # Create placeholder dashboard in draft state
            dashboard_data = DashboardCreate(
                name=dashboard_name,
                description=dashboard_description,
                DashboardType="Dynamic",
                is_active=False,  # Not active until workflow completes
                content=initial_content,
            )

            dashboard = await self.dashboard_service.create_dashboard(
                user_id=user_id,
                dashboard_data=dashboard_data,
                project_id=project_id,
                workspace_id=workspace_id,
                sharing_permission=SharingPermission.PRIVATE  # Private until shared
            )
            print("Crossed the dashboard in dashboard_workflow")
            # Create workflow — store metadata without preview_items (too large)
            workflow_meta = meta or {
                "dashboard_name": dashboard_name,
                "project_id": str(project_id) if project_id else None,
                "workspace_id": str(workspace_id) if workspace_id else None,
            }
            workflow = DashboardWorkflow(
                dashboard_id=dashboard.id,
                user_id=user_id,
                state=WorkflowState.DRAFT,
                current_step=1,
                workflow_metadata=workflow_meta,
            )

            self.db.add(workflow)
            print("Crossed self.ad.add()")
            # Create initial version
            await self._create_workflow_version(workflow, user_id)

            # Add to ChromaDB for searchability
            data = {
                    "project_id": str(project_id) if project_id else None,
                    "workspace_id": str(workspace_id) if workspace_id else None,
                    "created_at": datetime.utcnow().isoformat()
                }
            data = {k: v for k, v in data.items() if v is not None}
            await self._add_to_chroma(
                self.collection_name,
                str(workflow.id),
                {
                    "dashboard_id": str(dashboard.id),
                    "dashboard_name": dashboard_name,
                    "state": workflow.state.value,
                    "user_id": str(user_id)
                },
                data

            )

            await self.db.commit()

            # ── Auto-add preview components (Dashboard Creator Wizard) ───────
            # Do this after the initial commit so workflow.id is available and
            # the FK constraint is satisfied.
            if preview_items:
                components = _build_components_from_preview(preview_items)
                if components:
                    await self.add_thread_components(
                        user_id=user_id,
                        workflow_id=workflow.id,
                        components=components,
                    )

            return workflow, dashboard
        except Exception as e:
            traceback.print_exc()

    async def get_all_shares(self, user_id, share_type, entity_id):
        try:
            select_stmt = select(ShareConfiguration).join(
                ShareConfiguration.workflow
            ).join(
                DashboardWorkflow.dashboard
            ).options(
                joinedload(ShareConfiguration.workflow).joinedload(DashboardWorkflow.dashboard)
            ).where(
                DashboardWorkflow.dashboard_id == entity_id
            )
            result = await self.db.execute(select_stmt)
            shares = result.unique().scalars().all()
            
            # Organize shares by share_type
            shares_by_type = {}
            dashboard = None
            dashboard_id = entity_id
            dashboard_name = None
            owner_id = None
            
            if shares:
                # Get dashboard info from the first share (all shares belong to same dashboard)
                owner_id = shares[0].workflow.user_id
                dashboard = shares[0].workflow.dashboard
                dashboard_id = dashboard.id
                dashboard_name = dashboard.name
                print(f"Crossed dashboard {dashboard}")
                
                for share in shares:
                    share_type_key = share.share_type
                    
                    if share_type_key not in shares_by_type:
                        shares_by_type[share_type_key] = []
                    
                    shares_by_type[share_type_key].append({
                        "target_id": share.target_id,
                        "permission": share.permissions['Action'],
                        "isAuthor": False
                    })
            else:
                # If no shares, we still need to fetch dashboard info to get owner_id
                dashboard_stmt = select(Dashboard).join(
                    Dashboard.workflows
                ).where(
                    Dashboard.id == entity_id
                ).options(
                    joinedload(Dashboard.workflows)
                )
                dashboard_result = await self.db.execute(dashboard_stmt)
                dashboard = dashboard_result.unique().scalar_one_or_none()
                
                if dashboard:
                    dashboard_id = dashboard.id
                    dashboard_name = dashboard.name
                    # Get the first workflow's user_id (assuming one workflow per dashboard)
                    if dashboard.workflows:
                        owner_id = dashboard.workflows[0].user_id if isinstance(dashboard.workflows, list) else dashboard.workflows.user_id
            
            # Add static owner row to "user" share type only if owner_id exists
            if owner_id:
                if "user" not in shares_by_type:
                    shares_by_type["user"] = []
                
                print(f"Crossed owner_id {owner_id}")
                
                # Insert owner at the beginning of user shares
                shares_by_type["user"].insert(0, {
                    "target_id": owner_id,
                    "permission": "Admin",
                    "isAuthor": True
                })
            
            return {
                "dashboard_id": dashboard_id,
                "dashboard_name": dashboard_name,
                "shares": shares_by_type
            }
            
        except Exception as e:
            traceback.print_exc()
            return None
    
    async def get_all_shares(self, user_id, share_type, entity_id):
        try:
            select_stmt = select(ShareConfiguration).join(
                ShareConfiguration.workflow
            ).join(
                DashboardWorkflow.dashboard
            ).options(
                joinedload(ShareConfiguration.workflow).joinedload(DashboardWorkflow.dashboard)
            ).where(
                DashboardWorkflow.dashboard_id == entity_id
            )
            result = await self.db.execute(select_stmt)
            shares = result.unique().scalars().all()
            
            print(f"Total shares fetched: {len(shares)}")
            for s in shares:
                print(f"Share ID: {s.id}, Share Type: {s.share_type}, Target ID: {s.target_id}")
            
            # Organize shares by share_type
            shares_by_type = {}
            dashboard = None
            dashboard_id = entity_id
            dashboard_name = None
            owner_id = None
            
            if shares:
                # Get dashboard info from the first share (all shares belong to same dashboard)
                owner_id = shares[0].workflow.user_id
                dashboard = shares[0].workflow.dashboard
                dashboard_id = dashboard.id
                dashboard_name = dashboard.name
                print(f"Crossed dashboard {dashboard}")
                
                for share in shares:
                    share_type_key = share.share_type
                    print(f"Processing share_type_key: {share_type_key}")
                    
                    if share_type_key not in shares_by_type:
                        shares_by_type[share_type_key] = []
                    
                    shares_by_type[share_type_key].append({
                        "target_id": share.target_id,
                        "permission": share.permissions['Action'],
                        "isAuthor": False
                    })
            else:
                # If no shares, we still need to fetch dashboard info to get owner_id
                dashboard_stmt = select(Dashboard).join(
                    Dashboard.workflows
                ).where(
                    Dashboard.id == entity_id
                ).options(
                    joinedload(Dashboard.workflows)
                )
                dashboard_result = await self.db.execute(dashboard_stmt)
                dashboard = dashboard_result.unique().scalar_one_or_none()
                
                if dashboard:
                    dashboard_id = dashboard.id
                    dashboard_name = dashboard.name
                    # Get the first workflow's user_id (assuming one workflow per dashboard)
                    if dashboard.workflows:
                        owner_id = dashboard.workflows[0].user_id if isinstance(dashboard.workflows, list) else dashboard.workflows.user_id
            
            # Add static owner row to "user" share type only if owner_id exists
            print(f"Owner ID: {owner_id}")
            print(f"Shares by type before owner insert: {shares_by_type}")
            
            if owner_id:
                if "user" not in shares_by_type:
                    shares_by_type["user"] = []
                
                # Insert owner at the beginning of user shares
                shares_by_type["user"].insert(0, {
                    "target_id": owner_id,
                    "permission": "Admin",
                    "isAuthor": True
                })
            
            print(f"Final shares_by_type: {shares_by_type}")
            
            return {
                "dashboard_id": dashboard_id,
                "dashboard_name": dashboard_name,
                "shares": shares_by_type
            }
            
        except Exception as e:
            traceback.print_exc()
            return None



    async def get_all_dashboards(self, user_id, state=None, limit=None):
       
        
        # Get user's teams and projects for shared dashboard filtering
        user_stmt = select(User).options(
            joinedload(User.teams),
            joinedload(User.project_access).joinedload(ProjectAccess.project)
        ).where(User.id == user_id)
        
        user_result = await self.db.execute(user_stmt)
        user = user_result.unique().scalar_one_or_none()
        
        if not user:
            return {"my_dashboards": [], "shared_dashboards": []}
        
        user_team_ids = [str(team.id) for team in user.teams] if user.teams else []
        user_project_ids = [str(pa.project.id) for pa in user.project_access if pa.project] if user.project_access else []
        user_email = user.email if hasattr(user, 'email') else None
        
        # 1. Get owned dashboards
        owned_stmt = select(DashboardWorkflow).options(
            joinedload(DashboardWorkflow.dashboard)
        ).where(
            DashboardWorkflow.user_id == user_id
        )
        
        if state:
            owned_stmt = owned_stmt.where(DashboardWorkflow.state == state)
        
        owned_result = await self.db.execute(owned_stmt)
        owned_workflows = owned_result.scalars().all()
        
        # 2. Get shared dashboard workflow IDs
        share_conditions = [
            and_(ShareConfiguration.share_type == ShareType.USER, ShareConfiguration.target_id == str(user_id)),
        ]
        
        if user_team_ids:
            share_conditions.append(
                and_(ShareConfiguration.share_type == ShareType.TEAM, ShareConfiguration.target_id.in_(user_team_ids))
            )
        
        if user_project_ids:
            share_conditions.append(
                and_(ShareConfiguration.share_type == ShareType.PROJECT, ShareConfiguration.target_id.in_(user_project_ids))
            )
        
        if user_email:
            share_conditions.append(
                and_(ShareConfiguration.share_type == ShareType.EMAIL, ShareConfiguration.target_id == user_email)
            )
        
        shared_stmt = select(ShareConfiguration).options(
            joinedload(ShareConfiguration.workflow).joinedload(DashboardWorkflow.dashboard)
        ).where(
            and_(
                ShareConfiguration.workflow_id.is_not(None),  # Only dashboard shares, not report shares
                or_(*share_conditions) if share_conditions else False
            )
        )
        
        shared_result = await self.db.execute(shared_stmt)
        shared_configs = shared_result.unique().scalars().all()
        
        # Filter shared workflows by state if needed and exclude owned workflows
        owned_workflow_ids = {str(wf.id) for wf in owned_workflows}
        shared_workflows = []
        
        for share_config in shared_configs:
            workflow = share_config.workflow
            if workflow and workflow.dashboard and str(workflow.id) not in owned_workflow_ids:
                if state is None or workflow.state == state:
                    shared_workflows.append((workflow, share_config))
        
        # 3. Build owned dashboards response
        my_dashboards = []
        for workflow in owned_workflows:
            dashboard = workflow.dashboard
            if dashboard is None:
                continue
                
            my_dashboards.append({
                "dashboard_id": str(dashboard.id),
                "dashboard_name": dashboard.name,
                "dashboard_description": dashboard.description,
                "DashboardType": dashboard.DashboardType,
                "content": dashboard.content,
                "is_active": dashboard.is_active,
                "version": dashboard.version,
                "created_at": dashboard.created_at,
                "updated_at": dashboard.updated_at,
                "user_id": str(workflow.user_id),
                "workflow_id": str(workflow.id),
                "permissions": {"Action": "admin"}
            })
        
        # 4. Build shared dashboards response with share info
        shared_dashboards = []
        
        # Get additional info for shared_by field
        share_user_ids = {sc.workflow.user_id for _, sc in shared_workflows if sc.workflow}
        share_team_ids = {sc.target_id for _, sc in shared_workflows if sc.share_type == ShareType.TEAM}
        share_project_ids = {sc.target_id for _, sc in shared_workflows if sc.share_type == ShareType.PROJECT}
        
        # Fetch users for shared_by info
        users_map = {}
        if share_user_ids:
            users_stmt = select(User).where(User.id.in_(share_user_ids))
            users_result = await self.db.execute(users_stmt)
            users_map = {str(user.id): user for user in users_result.scalars().all()}
        
        # Fetch teams for shared_by info
        teams_map = {}
        if share_team_ids:
            teams_stmt = select(Team).where(Team.id.in_([uuid.UUID(tid) for tid in share_team_ids if tid]))
            teams_result = await self.db.execute(teams_stmt)
            teams_map = {str(team.id): team for team in teams_result.scalars().all()}
        
        # Fetch projects for shared_by info
        projects_map = {}
        if share_project_ids:
            projects_stmt = select(Project).where(Project.id.in_([uuid.UUID(pid) for pid in share_project_ids if pid]))
            projects_result = await self.db.execute(projects_stmt)
            projects_map = {str(project.id): project for project in projects_result.scalars().all()}
        
        for workflow, share_config in shared_workflows:
            dashboard = workflow.dashboard
            
            # Determine shared_by based on share_type
            shared_by = ""
            if share_config.share_type == ShareType.USER:
                owner_user = users_map.get(str(workflow.user_id))
                shared_by = owner_user.name if owner_user and hasattr(owner_user, 'name') else f"User {workflow.user_id}"
            elif share_config.share_type == ShareType.TEAM:
                team = teams_map.get(share_config.target_id)
                shared_by = team.name if team and hasattr(team, 'name') else f"Team {share_config.target_id}"
            elif share_config.share_type == ShareType.PROJECT:
                project = projects_map.get(share_config.target_id)
                shared_by = project.name if project and hasattr(project, 'name') else f"Project {share_config.target_id}"
            elif share_config.share_type == ShareType.EMAIL:
                shared_by = share_config.target_id
            
            shared_dashboards.append({
                "dashboard_id": str(dashboard.id),
                "dashboard_name": dashboard.name,
                "dashboard_description": dashboard.description,
                "DashboardType": dashboard.DashboardType,
                "content": dashboard.content,
                "is_active": dashboard.is_active,
                "version": dashboard.version,
                "created_at": dashboard.created_at,
                "updated_at": dashboard.updated_at,
                "user_id": str(workflow.user_id),
                "workflow_id": str(workflow.id),
                "permissions": share_config.permissions or {},
                "shared_by": shared_by,
                "share_type": share_config.share_type.value if hasattr(share_config.share_type, 'value') else str(share_config.share_type),
                "accepted": share_config.accepted
            })
        
        # 5. Apply limit if specified (across both sets)
        if limit:
            total_dashboards = my_dashboards + shared_dashboards
            if len(total_dashboards) > limit:
                # Prioritize owned dashboards, then shared
                if len(my_dashboards) >= limit:
                    my_dashboards = my_dashboards[:limit]
                    shared_dashboards = []
                else:
                    remaining_limit = limit - len(my_dashboards)
                    shared_dashboards = shared_dashboards[:remaining_limit]
        
        return {
            "my_dashboards": my_dashboards,
            "shared_dashboards": shared_dashboards
        }

    async def get_dashboard_by_id(
        self,
        user_id: UUID,
        dashboard_id: UUID,
        workflow_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get a specific dashboard by ID with all details including sharing, scheduling, and integrations"""
        
        # Get dashboard
        stmt = select(Dashboard).where(Dashboard.id == dashboard_id)
        result = await self.db.execute(stmt)
        dashboard = result.scalar_one_or_none()
        
        if not dashboard:
            raise ValueError(f"Dashboard {dashboard_id} not found")
        
        # Get workflow if not provided
        if not workflow_id:
            stmt = select(DashboardWorkflow).options(
                joinedload(DashboardWorkflow.share_configs),
                joinedload(DashboardWorkflow.schedule_config),
                joinedload(DashboardWorkflow.integrations),
                joinedload(DashboardWorkflow.thread_components),
                joinedload(DashboardWorkflow.template)
            ).where(DashboardWorkflow.dashboard_id == dashboard_id)
            result = await self.db.execute(stmt)
            workflow = result.unique().scalar_one_or_none()
        else:
            workflow = await self._get_workflow(workflow_id, user_id)

        if not workflow:
            raise ValueError(f"Workflow not found for dashboard {dashboard_id}")
        
        # Get sharing configurations
        sharing_configs = []
        if workflow.share_configs:
            for config in workflow.share_configs:
                sharing_configs.append({
                    "id": str(config.id),
                    "share_type": config.share_type.value,
                    "target_id": str(config.target_id) if config.target_id else None,
                    "target_email": getattr(config, 'target_email', None),
                    "permission_level": config.permissions.get('permission_level', 'read') if config.permissions else 'read',
                    "created_at": config.created_at.isoformat()
                })
        
        # Get schedule configuration
        schedule_config = None
        if workflow.schedule_config:
            schedule = workflow.schedule_config
            schedule_config = {
                "id": str(schedule.id),
                "schedule_type": schedule.schedule_type.value,
                "cron_expression": schedule.cron_expression,
                "timezone": schedule.timezone,
                "start_date": schedule.start_date.isoformat() if schedule.start_date else None,
                "end_date": schedule.end_date.isoformat() if schedule.end_date else None,
                "next_run": schedule.next_run.isoformat() if schedule.next_run else None,
                "is_active": getattr(schedule, 'is_active', True),
                "run_count": getattr(schedule, 'run_count', 0),
                "last_run": schedule.last_run.isoformat() if getattr(schedule, 'last_run', None) else None,
                "configuration": getattr(schedule, 'configuration', {}),
                "created_at": schedule.created_at.isoformat()
            }
        
        # Get integration configurations
        integration_configs = []
        if workflow.integrations:
            for config in workflow.integrations:
                integration_configs.append({
                    "id": str(config.id),
                    "integration_type": config.integration_type.value,
                    "connection_config": config.connection_config,
                    "is_active": getattr(config, 'is_active', True),
                    "last_sync": config.last_sync.isoformat() if getattr(config, 'last_sync', None) else None,
                    "created_at": config.created_at.isoformat()
                })
        
        # Get thread components
        thread_components = []
        if workflow.thread_components:
            for component in workflow.thread_components:
                thread_components.append({
                    "id": str(component.id),
                    "component_type": component.component_type.value,
                    "question": component.question,
                    "description": component.description,
                    "configuration": component.configuration,
                    "is_configured": component.is_configured,
                    "thread_message_id": str(component.thread_message_id) if component.thread_message_id else None,
                    "created_at": component.created_at.isoformat(),
                    "sql_query": component.sql_query
                })
        
        # Get alert components from ThreadComponent table
        alert_components = []
        
        # First, get alert components from ThreadComponent table
        stmt = select(ThreadComponent).where(
            and_(
                ThreadComponent.workflow_id == workflow.id,
                ThreadComponent.component_type == ComponentType.ALERT
            )
        ).order_by(ThreadComponent.sequence_order)
        result = await self.db.execute(stmt)
        thread_alert_components = result.scalars().all()
        
        for component in thread_alert_components:
            alert_config = component.alert_config or {}
            alert_components.append({
                "id": str(component.id),
                "question": component.question,
                "description": component.description,
                "alert_type": alert_config.get("alert_type"),
                "severity": alert_config.get("severity"),
                "alert_status": component.alert_status.value if component.alert_status else None,
                "trigger_count": component.trigger_count or 0,
                "last_triggered": component.last_triggered.isoformat() if component.last_triggered else None,
                "created_at": component.created_at.isoformat(),
                "sql_query": component.sql_query,
                "executive_summary": component.executive_summary,
                "data_overview": component.data_overview,
                "visualization_data": component.visualization_data,
                "sample_data": component.sample_data,
                "metadata": component.thread_metadata,
                "chart_schema": component.chart_schema,
                "reasoning": component.reasoning,
                "data_count": component.data_count,
                "validation_results": component.validation_results
            })
        
        # Also include alert components from workflow metadata (for backward compatibility)
        if workflow.workflow_metadata and "alerts" in workflow.workflow_metadata:
            for alert in workflow.workflow_metadata["alerts"]:
                # Check if this alert is already included from ThreadComponent table
                alert_id = alert["id"]
                if not any(comp["id"] == alert_id for comp in alert_components):
                    alert_components.append({
                        "id": alert["id"],
                        "question": alert["question"],
                        "description": alert["description"],
                        "alert_type": alert["alert_config"]["alert_type"],
                        "severity": alert["alert_config"]["severity"],
                        "alert_status": alert["alert_status"],
                        "trigger_count": alert["trigger_count"],
                        "last_triggered": alert["last_triggered"],
                        "created_at": alert["created_at"],
                        "sql_query": alert.get("sql_query")
                    })
        
        # Get draft changes
        draft_changes = workflow.workflow_metadata.get("draft_changes", {})

        # Resolve template — fall back to first active template if none linked
        template = workflow.template
        if not template:
            default_stmt = select(DashboardTemplate).where(DashboardTemplate.is_active == True).order_by(DashboardTemplate.created_at).limit(1)
            default_result = await self.db.execute(default_stmt)
            template = default_result.scalar_one_or_none()

        return {
            "dashboard": {
                "id": str(dashboard.id),
                "name": dashboard.name,
                "description": dashboard.description,
                "content": dashboard.content,
                "version": dashboard.version,
                "is_active": dashboard.is_active,
                "created_at": dashboard.created_at.isoformat(),
                "updated_at": dashboard.updated_at.isoformat()
            },
            "workflow": {
                "id": str(workflow.id),
                "state": workflow.state.value,
                "current_step": workflow.current_step,
                "layout": (workflow.workflow_metadata or {}).get("layout"),
                "workflow_metadata": workflow.workflow_metadata,
                "template_id": str(workflow.template_id) if workflow.template_id else None,
                "created_at": workflow.created_at.isoformat(),
                "updated_at": workflow.updated_at.isoformat(),
                "completed_at": workflow.completed_at.isoformat() if workflow.completed_at else None
            },
            "template": {
                "id": str(template.id),
                "source_id": template.source_id,
                "name": template.name,
                "description": template.description,
                "template_type": template.template_type,
                "category": template.category,
                "complexity": template.complexity,
                "domains": template.domains,
                "best_for": template.best_for,
                "layout": template.layout,
            } if template else None,
            "sharing": {
                "configurations": sharing_configs,
                "total_shared": len(sharing_configs)
            },
            "scheduling": {
                "configuration": schedule_config,
                "has_schedule": schedule_config is not None
            },
            "integrations": {
                "configurations": integration_configs,
                "total_integrations": len(integration_configs)
            },
            "components": {
                "thread_components": thread_components,
                "alert_components": alert_components,
                "total_components": len(thread_components) + len(alert_components)
            },
            "draft_changes": {
                "has_draft_changes": draft_changes.get("has_draft_changes", False),
                "last_edited_at": draft_changes.get("last_edited_at"),
                "edited_by": draft_changes.get("edited_by"),
                "last_published_at": draft_changes.get("last_published_at"),
                "published_by": draft_changes.get("published_by")
            }
        }

    

    async def add_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        component_data: ThreadComponentCreate,
        thread_message_id: Optional[UUID] = None,
        commit=True
    ) -> ThreadComponent:
        """
        Step 2: Add thread message components to workflow
        """
        try:
            workflow = await self._get_workflow(workflow_id, user_id)

            # Validate state - allow editing in more states for draft changes
            if workflow.state not in [WorkflowState.DRAFT, WorkflowState.CONFIGURING, WorkflowState.PUBLISHED, WorkflowState.ACTIVE]:
                raise ValueError(f"Cannot add components in {workflow.state} state")

            # Get next sequence order
            stmt = select(func.max(ThreadComponent.sequence_order)).where(
                ThreadComponent.workflow_id == workflow_id
            )
            result = await self.db.execute(stmt)
            max_order = result.scalar() or 0

            # Create thread component
            component = ThreadComponent(
                workflow_id=workflow_id,
                thread_message_id=thread_message_id,
                component_type=component_data.component_type,
                sequence_order=max_order + 1,
                question=component_data.question,
                description=component_data.description,
                overview=component_data.overview,
                chart_config=component_data.chart_config,
                table_config=component_data.table_config,
                configuration=component_data.configuration,
                is_configured=False,
                sql_query=component_data.sql_query,
                executive_summary=component_data.executive_summary,
                data_overview=component_data.data_overview,
                visualization_data=component_data.visualization_data,
                sample_data=component_data.sample_data,
                thread_metadata=component_data.metadata,  # Map metadata to thread_metadata
                chart_schema=component_data.chart_schema,
                reasoning=component_data.reasoning,
                data_count=component_data.data_count,
                validation_results=component_data.validation_results,
            )

            # Add component BEFORE any other operations
            self.db.add(component)

            # Mark as draft changes if workflow is published/active
            if workflow.state in [WorkflowState.PUBLISHED, WorkflowState.ACTIVE]:
                draft_changes = workflow.workflow_metadata.get("draft_changes", {})
                draft_changes["has_draft_changes"] = True
                draft_changes["last_edited_at"] = datetime.utcnow().isoformat()
                draft_changes["edited_by"] = str(user_id)
                workflow.workflow_metadata["draft_changes"] = draft_changes
            else:
                # Update workflow state if first component and in draft/configuring
                if workflow.state == WorkflowState.DRAFT:
                    workflow.state = WorkflowState.CONFIGURING
                    workflow.current_step = 2

            # Flush to get the component ID before updating relationships
            await self.db.flush()

            # Update dashboard content
            await self._update_dashboard_content(workflow, user_id)
            
            # Create version (but don't add here as it causes conflicts)
            try:
                await self._create_workflow_version(workflow, user_id, note="Component added" if workflow.state in [WorkflowState.PUBLISHED, WorkflowState.ACTIVE] else None)
            except Exception as version_error:
                print(f"Warning: Version creation failed: {version_error}")
                # Continue without failing the main operation
                

            if commit:
                await self.db.commit()
                
            print(f"Successfully added component {component.id}")
            return component
            
        except Exception as e:
            print("====================== Error in dashboard workflow add_thread_component")
            traceback.print_exc()
            print("===================== Error Ended here ========================")
            # Rollback the transaction on error
            if commit:
                await self.db.rollback()
            raise

    async def add_thread_components(
        self,
        user_id: UUID,
        workflow_id: UUID,
        components: List[ThreadComponentCreate],
        thread_message_id: Optional[UUID] = None
    ) -> List[ThreadComponent]:
        """
        Add multiple thread components to the dashboard workflow
        Process sequentially to avoid concurrent database conflicts
        """
        try:
            created_components = []
            for i, component in enumerate(components):
                try:
                    print(f"Adding component {i+1}/{len(components)}")
                    result = await self.add_thread_component(
                        user_id=user_id,
                        workflow_id=workflow_id,
                        component_data=component,
                        thread_message_id=thread_message_id,
                        commit=False
                    )
                    if result:
                        created_components.append(result)
                        
                except Exception as e:
                    print(f"Failed to add component {i+1}: {e}")
                    continue
            
            if created_components:
                await self.db.commit()
                print(f"Successfully committed {len(created_components)} components")
            else:
                await self.db.rollback()
                print("No components were created successfully")
                
            return created_components
            
        except Exception as e:
            print("====================== Error in dashboard workflow add_thread_components")
            traceback.print_exc()
            print("===================== Error Ended here ========================")
            await self.db.rollback()
            return []
    
    async def add_alert_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        alert_data: AlertThreadComponentCreate,
        thread_message_id: Optional[UUID] = None
    ) -> ThreadComponent:
        """
        Add an alert as a thread message component to the dashboard workflow
        """

        workflow = await self._get_workflow(workflow_id, user_id)

        # Validate state - allow adding alerts in more states including ACTIVE
        if workflow.state not in [WorkflowState.DRAFT, WorkflowState.CONFIGURING, WorkflowState.ACTIVE, WorkflowState.PUBLISHED]:
            raise ValueError(f"Cannot add alert components in {workflow.state} state")

        # Get next sequence order
        stmt = select(func.max(ThreadComponent.sequence_order)).where(
            ThreadComponent.workflow_id == workflow_id
        )
        result = await self.db.execute(stmt)
        max_order = result.scalar() or 0

        # Create alert configuration
        alert_config = {
            "alert_type": alert_data.alert_type.value,
            "severity": alert_data.severity.value,
            "condition_config": alert_data.condition_config,
            "threshold_config": alert_data.threshold_config,
            "anomaly_config": alert_data.anomaly_config,
            "trend_config": alert_data.trend_config,
            "notification_channels": alert_data.notification_channels,
            "escalation_config": alert_data.escalation_config,
            "cooldown_period": alert_data.cooldown_period
        }

        # Create thread component for alert
        component = ThreadComponent(
            workflow_id=workflow_id,
            thread_message_id=thread_message_id,
            component_type=ComponentType.ALERT,
            sequence_order=max_order + 1,
            question=alert_data.question,
            description=alert_data.description,
            alert_config=alert_config,
            alert_status=AlertStatus.ACTIVE,
            trigger_count=0,
            configuration=alert_data.configuration,
            is_configured=True,  # Alerts are configured when created
            sql_query=alert_data.sql_query,
            executive_summary=alert_data.executive_summary,
            data_overview=alert_data.data_overview,
            visualization_data=alert_data.visualization_data,
            sample_data=alert_data.sample_data,
            thread_metadata=alert_data.metadata,
            chart_schema=alert_data.chart_schema,
            reasoning=alert_data.reasoning,
            data_count=alert_data.data_count,
            validation_results=alert_data.validation_results,

        )

        self.db.add(component)

        # Update workflow state if first component
        if workflow.state == WorkflowState.DRAFT:
            workflow.state = WorkflowState.CONFIGURING
            workflow.current_step = 2

        # Update dashboard content
        await self._update_dashboard_content(workflow, user_id)

        # Create version
        await self._create_workflow_version(workflow, user_id)

        await self.db.commit()
        return component

    async def configure_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        component_id: UUID,
        configuration: Dict[str, Any]
    ) -> ThreadComponent:
        """
        Step 3: Configure individual thread message components
        """

        workflow = await self._get_workflow(workflow_id, user_id)

        # Get component
        stmt = select(ThreadComponent).where(
            and_(
                ThreadComponent.id == component_id,
                ThreadComponent.workflow_id == workflow_id
            )
        )
        result = await self.db.execute(stmt)
        component = result.scalar_one_or_none()

        if not component:
            raise ValueError(f"Component {component_id} not found")

        # Update configuration
        component.configuration = configuration
        component.is_configured = True
        component.updated_at = datetime.utcnow()

        # Check if all components are configured
        stmt = select(ThreadComponent).where(
            and_(
                ThreadComponent.workflow_id == workflow_id,
                ThreadComponent.is_configured == False
            )
        )
        result = await self.db.execute(stmt)
        all_rows = result.scalars().all()  # returns a list
        all_configured = len(all_rows) == 0

        if all_configured and workflow.state == WorkflowState.CONFIGURING:
            workflow.state = WorkflowState.CONFIGURED
            workflow.current_step = 3

        # Update dashboard
        await self._update_dashboard_content(workflow, user_id)

        # Create version
        await self._create_workflow_version(workflow, user_id)

        await self.db.commit()
        return component

    async def update_alert_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        component_id: UUID,
        update_data: AlertThreadComponentUpdate
    ) -> ThreadComponent:
        """
        Update an existing alert thread component
        """

        workflow = await self._get_workflow(workflow_id, user_id)

        # Get component
        stmt = select(ThreadComponent).where(
            and_(
                ThreadComponent.id == component_id,
                ThreadComponent.workflow_id == workflow_id,
                ThreadComponent.component_type == ComponentType.ALERT
            )
        )
        result = await self.db.execute(stmt)
        component = result.scalar_one_or_none()

        if not component:
            raise ValueError(f"Alert component {component_id} not found")

        # Update alert configuration if provided
        if any([
            update_data.condition_config,
            update_data.threshold_config,
            update_data.anomaly_config,
            update_data.trend_config,
            update_data.notification_channels,
            update_data.escalation_config,
            update_data.cooldown_period
        ]):
            current_alert_config = component.alert_config or {}

            # Update alert config fields
            if update_data.condition_config:
                current_alert_config["condition_config"] = update_data.condition_config
            if update_data.threshold_config:
                current_alert_config["threshold_config"] = update_data.threshold_config
            if update_data.anomaly_config:
                current_alert_config["anomaly_config"] = update_data.anomaly_config
            if update_data.trend_config:
                current_alert_config["trend_config"] = update_data.trend_config
            if update_data.notification_channels:
                current_alert_config["notification_channels"] = update_data.notification_channels
            if update_data.escalation_config:
                current_alert_config["escalation_config"] = update_data.escalation_config
            if update_data.cooldown_period:
                current_alert_config["cooldown_period"] = update_data.cooldown_period

            component.alert_config = current_alert_config

        # Update other fields
        if update_data.question:
            component.question = update_data.question
        if update_data.description:
            component.description = update_data.description
        if update_data.severity:
            # Update severity in alert config
            current_alert_config = component.alert_config or {}
            current_alert_config["severity"] = update_data.severity.value
            component.alert_config = current_alert_config
        if update_data.alert_status:
            component.alert_status = update_data.alert_status
        if update_data.configuration:
            component.configuration = update_data.configuration
        
        # Update SQL-related fields
        if update_data.sql_query is not None:
            component.sql_query = update_data.sql_query
        if update_data.executive_summary is not None:
            component.executive_summary = update_data.executive_summary
        if update_data.data_overview is not None:
            component.data_overview = update_data.data_overview
        if update_data.visualization_data is not None:
            component.visualization_data = update_data.visualization_data
        if update_data.sample_data is not None:
            component.sample_data = update_data.sample_data
        if update_data.metadata is not None:
            component.thread_metadata = update_data.metadata
        if update_data.chart_schema is not None:
            component.chart_schema = update_data.chart_schema
        if update_data.reasoning is not None:
            component.reasoning = update_data.reasoning
        if update_data.data_count is not None:
            component.data_count = update_data.data_count
        if update_data.validation_results is not None:
            component.validation_results = update_data.validation_results

        component.updated_at = datetime.utcnow()

        # Update dashboard content
        await self._update_dashboard_content(workflow, user_id)

        # Create version
        await self._create_workflow_version(workflow, user_id)

        await self.db.commit()
        return component

    async def test_alert_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        component_id: UUID,
        test_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Test an alert thread component with sample data
        """

        workflow = await self._get_workflow(workflow_id, user_id)

        # Get alert component
        stmt = select(ThreadComponent).where(
            and_(
                ThreadComponent.id == component_id,
                ThreadComponent.workflow_id == workflow_id,
                ThreadComponent.component_type == ComponentType.ALERT
            )
        )
        result = await self.db.execute(stmt)
        component = result.scalar_one_or_none()

        if not component:
            raise ValueError(f"Alert component {component_id} not found")

        # Test the alert condition
        try:
            test_result = await self._evaluate_alert_condition(component, test_data or {})

            return {
                "success": True,
                "component_id": str(component_id),
                "alert_name": component.question,
                "test_result": test_result,
                "message": "Alert condition evaluated successfully"
            }
        except Exception as e:
            return {
                "success": False,
                "component_id": str(component_id),
                "alert_name": component.question,
                "error": str(e),
                "message": "Failed to evaluate alert condition"
            }

    async def trigger_alert_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        component_id: UUID,
        trigger_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Manually trigger an alert thread component for testing
        """

        workflow = await self._get_workflow(workflow_id, user_id)

        # Get alert component
        stmt = select(ThreadComponent).where(
            and_(
                ThreadComponent.id == component_id,
                ThreadComponent.workflow_id == workflow_id,
                ThreadComponent.component_type == ComponentType.ALERT
            )
        )
        result = await self.db.execute(stmt)
        component = result.scalar_one_or_none()

        if not component:
            raise ValueError(f"Alert component {component_id} not found")

        if component.alert_status != AlertStatus.ACTIVE:
            raise ValueError(f"Alert component '{component.question}' is not active")

        # Check cooldown period
        if component.last_triggered and component.alert_config:
            cooldown_period = component.alert_config.get("cooldown_period", 300)
            time_since_last = (datetime.utcnow() - component.last_triggered).total_seconds()
            if time_since_last < cooldown_period:
                remaining = cooldown_period - time_since_last
                raise ValueError(f"Alert is in cooldown period. Try again in {int(remaining)} seconds")

        # Trigger the alert
        try:
            trigger_result = await self._execute_alert_notifications(component, trigger_data or {})

            # Update alert status
            component.last_triggered = datetime.utcnow()
            component.trigger_count += 1
            component.alert_status = AlertStatus.TRIGGERED

            await self.db.commit()

            return {
                "success": True,
                "component_id": str(component_id),
                "alert_name": component.question,
                "trigger_result": trigger_result,
                "message": "Alert triggered successfully"
            }
        except Exception as e:
            return {
                "success": False,
                "component_id": str(component_id),
                "alert_name": component.question,
                "error": str(e),
                "message": "Failed to trigger alert"
            }

    async def update_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        component_id: UUID,
        update_data: ThreadComponentUpdate
    ) -> ThreadComponent:
        """
        Update existing thread component
        """

        workflow = await self._get_workflow(workflow_id, user_id)

        stmt = select(ThreadComponent).where(
            and_(
                ThreadComponent.id == component_id,
                ThreadComponent.workflow_id == workflow_id
            )
        )
        result = await self.db.execute(stmt)
        component = result.scalar_one_or_none()

        if not component:
            raise ValueError(f"Component {component_id} not found")

        # Update fields with proper field mapping
        update_dict = update_data.dict(exclude_unset=True)
        
        # Handle field name mapping
        if 'metadata' in update_dict:
            component.thread_metadata = update_dict.pop('metadata')
        
        # Update all other fields
        for field, value in update_dict.items():
            if hasattr(component, field):
                setattr(component, field, value)

        component.updated_at = datetime.utcnow()

        # Mark as draft changes if workflow is published/active
        if workflow.state in [WorkflowState.PUBLISHED, WorkflowState.ACTIVE]:
            draft_changes = workflow.workflow_metadata.get("draft_changes", {})
            draft_changes["has_draft_changes"] = True
            draft_changes["last_edited_at"] = datetime.utcnow().isoformat()
            draft_changes["edited_by"] = str(user_id)
            workflow.workflow_metadata["draft_changes"] = draft_changes

        # Update dashboard
        await self._update_dashboard_content(workflow, user_id)

        # Create version
        await self._create_workflow_version(workflow, user_id, note="Component updated" if workflow.state in [WorkflowState.PUBLISHED, WorkflowState.ACTIVE] else None)

        await self.db.commit()
        return component

    async def configure_sharing(
        self,
        user_id: UUID,
        workflow_id: UUID,
        share_config: ShareConfigCreate
    ) -> List[ShareConfiguration]:
        """
        Step 4: Configure sharing settings
        """
        try:

            workflow = await self._get_workflow(workflow_id, user_id)
            # print(f" workflow state {workflow} {workflow.state}")
            # Validate state - allow sharing in more states including ACTIVE
            if workflow.state not in [WorkflowState.CONFIGURED, WorkflowState.SHARING, WorkflowState.CONFIGURING, WorkflowState.ACTIVE, WorkflowState.PUBLISHED]:
                raise ValueError(f"Cannot configure sharing in {workflow.state} state")

            # Update state - only transition from CONFIGURED to SHARING
            # If already ACTIVE/PUBLISHED, keep current state but allow sharing
            if workflow.state == WorkflowState.CONFIGURED:
                workflow.state = WorkflowState.SHARING
                workflow.current_step = 4

            share_configs = []

            for target_id in share_config.target_ids:
                config = ShareConfiguration(
                    workflow_id=workflow_id,
                    share_type=share_config.share_type,
                    target_id=target_id,
                    permissions=share_config.permissions
                )
                self.db.add(config)
                share_configs.append(config)

                # Send notification based on share type
                if share_config.share_type == ShareType.EMAIL:
                    await self._send_email_invitation(target_id, workflow, user_id)

            # Update workflow state - only transition to SHARED if not already ACTIVE/PUBLISHED
            if workflow.state not in [WorkflowState.ACTIVE, WorkflowState.PUBLISHED]:
                workflow.state = WorkflowState.SHARED
                workflow.current_step = 5

            # Update dashboard sharing
            await self._apply_sharing_to_dashboard(workflow, share_configs, user_id)

            # Create version
            await self._create_workflow_version(workflow, user_id)

            await self.db.commit()
            return share_configs
        except Exception as e:
            print("============================= Error in configure sharing ================")
            traceback.print_exc()
            print("====================== Error Ended Here===================")

    async def configure_schedule(
        self,
        user_id: UUID,
        workflow_id: UUID,
        schedule_config: ScheduleConfigCreate
    ) -> ScheduleConfiguration:
        """
        Step 5: Configure scheduling
        """
        try:

            workflow = await self._get_workflow(workflow_id, user_id)

            # Validate state - allow scheduling in more states including ACTIVE
            if workflow.state not in [WorkflowState.SHARED, WorkflowState.SCHEDULING, WorkflowState.ACTIVE, WorkflowState.PUBLISHED]:
                raise ValueError(f"Cannot configure schedule in {workflow.state} state")

            # Update state - only transition from SHARED to SCHEDULING
            # If already ACTIVE/PUBLISHED, keep current state but allow scheduling
            if workflow.state == WorkflowState.SHARED:
                workflow.state = WorkflowState.SCHEDULING
                workflow.current_step = 6

            # Create or update schedule configuration
            stmt = select(ScheduleConfiguration).where(
                ScheduleConfiguration.workflow_id == workflow_id
            )
            result = await self.db.execute(stmt)
            schedule = result.scalar_one_or_none()

            print(f"DEBUG: Found existing schedule: {schedule is not None}")
            print(f"DEBUG: Schedule config: {schedule_config}")

            if not schedule:
                print("DEBUG: Creating new schedule configuration")
                # Convert to GMT/UTC using utility function
                start_date_gmt = self._convert_to_utc(schedule_config.start_date, schedule_config.timezone)
                end_date_gmt = self._convert_to_utc(schedule_config.end_date, schedule_config.timezone)
                
                schedule = ScheduleConfiguration(
                    workflow_id=workflow_id,
                    schedule_type=schedule_config.schedule_type,
                    cron_expression=schedule_config.cron_expression,
                    timezone="UTC",  # Store as UTC
                    start_date=start_date_gmt,
                    end_date=end_date_gmt,
                    configuration=schedule_config.configuration
                )
                self.db.add(schedule)
                print(f"DEBUG: New schedule created: {schedule}")
            else:
                print("DEBUG: Updating existing schedule configuration")
                # Convert to GMT/UTC using utility function
                start_date_gmt = self._convert_to_utc(schedule_config.start_date, schedule_config.timezone)
                end_date_gmt = self._convert_to_utc(schedule_config.end_date, schedule_config.timezone)
                
                schedule.schedule_type = schedule_config.schedule_type
                schedule.cron_expression = schedule_config.cron_expression
                schedule.timezone = "UTC"  # Store as UTC
                schedule.start_date = start_date_gmt
                schedule.end_date = end_date_gmt
                schedule.configuration = schedule_config.configuration
                schedule.updated_at = datetime.utcnow()
                print(f"DEBUG: Schedule updated: {schedule}")

            # Calculate next run time
            if schedule is None:
                raise ValueError("Schedule object is None after creation/update")
            
            schedule.next_run = await self._calculate_next_run(schedule)

            # Update workflow state - only transition to SCHEDULED if not already ACTIVE/PUBLISHED
            if workflow.state not in [WorkflowState.ACTIVE, WorkflowState.PUBLISHED]:
                workflow.state = WorkflowState.SCHEDULED
                workflow.current_step = 7

            # Create version
            await self._create_workflow_version(workflow, user_id)

            await self.db.commit()
            return schedule
        except Exception as e:
            print("================== Error in configure schedule ==================")
            traceback.print_exc()
            print("===============Error ended here =================")

    async def configure_integrations(
        self,
        user_id: UUID,
        workflow_id: UUID,
        integration_configs: List[IntegrationConfigCreate]
    ) -> List[IntegrationConfig]:
        """
        Step 6: Configure integrations for publishing
        """
        try:
            workflow = await self._get_workflow(workflow_id, user_id)
            print(f"Workflow id in integrations: {workflow_id} {workflow}")

            # Validate state - allow integrations in more states including ACTIVE
            if workflow.state not in [WorkflowState.SCHEDULED, WorkflowState.PUBLISHING, WorkflowState.ACTIVE, WorkflowState.PUBLISHED]:
                raise ValueError(f"Cannot configure integrations in {workflow.state} state")

            # Update state - only transition from SCHEDULED to PUBLISHING
            # If already ACTIVE/PUBLISHED, keep current state but allow integrations
            if workflow.state == WorkflowState.SCHEDULED:
                workflow.state = WorkflowState.PUBLISHING
                workflow.current_step = 8

            integrations = []

            for config_data in integration_configs:
                # Encrypt sensitive connection data
                encrypted_config = await self._encrypt_connection_config(config_data.connection_config)

                integration = IntegrationConfig(
                    workflow_id=workflow_id,
                    integration_type=config_data.integration_type,
                    connection_config=encrypted_config,
                    mapping_config=config_data.mapping_config,
                    filter_config=config_data.filter_config,
                    transform_config=config_data.transform_config
                )
                self.db.add(integration)
                integrations.append(integration)

            # Create version
            await self._create_workflow_version(workflow, user_id)

            await self.db.commit()
            return integrations
        except Exception as e:
            print("================== Error in configure integrations ==================")
            traceback.print_exc()
            print("===============Error ended here =================")
            raise HTTPException(status_code=400, detail=str(e))


    async def publish_dashboard(
        self,
        user_id: UUID,
        workflow_id: UUID
    ) -> Dict[str, Any]:
            """
            Step 7: Publish dashboard to all configured integrations
            Now handles draft changes by applying them to the published dashboard
            """

            workflow = await self._get_workflow(workflow_id, user_id)

            # Get dashboard
            stmt = select(Dashboard).where(Dashboard.id == workflow.dashboard_id)
            result = await self.db.execute(stmt)
            dashboard = result.scalar_one_or_none()

            # Check if there are draft changes to apply
            draft_changes = workflow.workflow_metadata.get("draft_changes", {})
            has_draft_changes = draft_changes.get("has_draft_changes", False)

            if has_draft_changes:
                print("has_draft_changes is true")
                # Apply draft changes to the published dashboard
                if "name" in draft_changes:
                    dashboard.name = draft_changes["name"]
                if "description" in draft_changes:
                    dashboard.description = draft_changes["description"]
                if "content" in draft_changes:
                    dashboard.content = draft_changes["content"]
                if "metadata" in draft_changes:
                    dashboard.content = {**(dashboard.content or {}), **{"metadata": draft_changes["metadata"]}}

                # **STEP 1: Get existing ThreadComponents for this workflow**
                stmt = select(ThreadComponent).where(
                    ThreadComponent.workflow_id == workflow_id
                )
                result = await self.db.execute(stmt)
                existing_components = result.scalars().all()
                existing_component_ids = {str(comp.id) for comp in existing_components}
                print("I am after existing_component_ids", existing_component_ids)
                max_sequence = 0
                if existing_components:
                    max_sequence = max(comp.sequence_order for comp in existing_components)


                # **STEP 2: Process components from draft_changes (handle create/delete/reorder)**
                if "components" in draft_changes['content']:
                    components_data = draft_changes['content']['components']
                    print("I am after components_data", components_data)
                    
                    # Get IDs of components that UI is sending
                    incoming_component_ids = {
                        comp_data.get("id") for comp_data in components_data 
                        if comp_data.get("id")
                    }
                    print("I am after incoming_component_ids", incoming_component_ids)
                    
                    # **Delete components that existed before but are not in the new list**
                    components_to_delete = [x for x in existing_component_ids if x not in incoming_component_ids]
                    print("I am after components_to_delete", components_to_delete)
                    from sqlalchemy import and_, delete
                    if components_to_delete:
                        stmt = delete(ThreadComponent).where(
                            and_(
                                ThreadComponent.workflow_id == workflow_id,
                                ThreadComponent.id.in_(components_to_delete)
                            )
                        )
                        await self.db.execute(stmt)
                    
                    for i, comp_data in enumerate(components_data):
                        comp_id = comp_data.get("id")
                        print("I am after comp_id", comp_id)
                        print("I got component_type is ", comp_data.get("component_type"))
                        
                        if not comp_id or comp_id not in existing_component_ids:
                            max_sequence += 1
                            # Create new component with temporary sequence_order (will be updated later)
                            new_component = ThreadComponent(
                                workflow_id=workflow_id,
                                component_type=comp_data.get("component_type"),
                                sequence_order=max_sequence,
                                question=comp_data.get("question"),
                                description=comp_data.get("description"),
                                overview=comp_data.get("overview"),
                                chart_config=comp_data.get("chart_config"),
                                table_config=comp_data.get("table_config"),
                                configuration=comp_data.get("configuration"),
                                is_configured=True if comp_data.get("configuration") else False,
                                sql_query=comp_data.get("sql_query"),
                                executive_summary=comp_data.get("executive_summary"),
                                data_overview=comp_data.get("data_overview"),
                                visualization_data=comp_data.get("visualization_data"),
                                sample_data=comp_data.get("sample_data"),
                                thread_metadata=comp_data.get("metadata"),
                                chart_schema=comp_data.get("chart_schema"),
                                reasoning=comp_data.get("reasoning"),
                                data_count=comp_data.get("data_count"),
                                validation_results=comp_data.get("validation_results"),
                            )
                            self.db.add(new_component)
                    
                    # Flush to ensure new components get IDs
                    await self.db.flush()

                    stmt = select(ThreadComponent).where(
                    ThreadComponent.workflow_id == workflow_id
                    ).order_by(ThreadComponent.sequence_order.asc())
                    result = await self.db.execute(stmt)
                    all_components = result.scalars().all()

                    # Build dashboard.content with all components (complete data)
                    dashboard.content = {
                        "components": []
                    }
                    
                    for comp in all_components:
                        dashboard.content["components"].append({
                            "id": str(comp.id),
                            "workflow_id": str(comp.workflow_id),
                            "component_type": comp.component_type,
                            "sequence_order": comp.sequence_order,
                            "question": comp.question,
                            "description": comp.description,
                            "overview": comp.overview,
                            "chart_config": comp.chart_config,
                            "table_config": comp.table_config,
                            "configuration": comp.configuration,
                            "is_configured": comp.is_configured,
                            "sql_query": comp.sql_query,
                            "executive_summary": comp.executive_summary,
                            "data_overview": comp.data_overview,
                            "visualization_data": comp.visualization_data,
                            "sample_data": comp.sample_data,
                            "thread_metadata": comp.thread_metadata,
                            "chart_schema": comp.chart_schema,
                            "reasoning": comp.reasoning,
                            "data_count": comp.data_count,
                            "validation_results": comp.validation_results,
                            "created_at": comp.created_at.isoformat() if comp.created_at else None,
                            "updated_at": comp.updated_at.isoformat() if comp.updated_at else None
                        })
                        
                        

                # Update dashboard version
                current_version = float(dashboard.version)
                new_version = str(current_version + 1.0)
                dashboard.version = new_version
                dashboard.updated_at = datetime.utcnow()

                # Create new dashboard version
                version = DashboardVersion(
                    dashboard_id=dashboard.id,
                    version=new_version,
                    content=dashboard.content
                )
                self.db.add(version)

                # Clear draft changes
                draft_changes["has_draft_changes"] = False
                draft_changes["last_published_at"] = datetime.utcnow().isoformat()
                draft_changes["published_by"] = str(user_id)
                draft_changes["content"] = {}
                workflow.workflow_metadata["draft_changes"] = draft_changes

                # Update ChromaDB with new content
                await self._update_chroma(
                    self.dashboard_service.collection_name,
                    str(dashboard.id),
                    {
                        "name": dashboard.name,
                        "description": dashboard.description,
                        "type": dashboard.DashboardType,
                        "content": dashboard.content
                    },
                    {
                        "created_by": str(user_id),
                        "workflow_id": str(workflow_id),
                        "updated_at": dashboard.updated_at.isoformat(),
                        "version": new_version
                    }
                )

            # If no draft changes, just update the dashboard to active and proceed with publishing
            else:
                # Just update the timestamp for direct publish without changes
                dashboard.updated_at = datetime.utcnow()

            # Get integrations
            stmt = select(IntegrationConfig).where(IntegrationConfig.workflow_id == workflow_id)
            result = await self.db.execute(stmt)
            integrations = result.scalars().all()

            publish_results = {}

            for integration in integrations:
                try:
                    result = await self._publish_to_integration(
                        dashboard,
                        integration,
                        workflow
                    )
                    publish_results[integration.integration_type.value] = {
                        "success": True,
                        "result": result
                    }
                    integration.last_sync = datetime.utcnow()
                    integration.sync_status = "success"
                except Exception as e:
                    publish_results[integration.integration_type.value] = {
                        "success": False,
                        "error": str(e)
                    }
                    integration.sync_status = "failed"
                    integration.error_message = str(e)

            # Update dashboard to active
            dashboard.is_active = True
            dashboard.updated_at = datetime.utcnow()

            # Update workflow state
            workflow.state = WorkflowState.ACTIVE
            workflow.current_step = 9
            workflow.completed_at = datetime.utcnow()

            # Create final version
            await self._create_workflow_version(
                workflow, 
                user_id, 
                note="Published with changes" if has_draft_changes else "Published"
            )

            # **STEP 3: Get ALL ThreadComponents again (existing + newly created) for n8n workflow**
            try:
                # Get all components, share configs, schedule, and integrations
                stmt = select(ThreadComponent).where(
                    ThreadComponent.workflow_id == workflow_id
                ).order_by(ThreadComponent.sequence_order)
                result = await self.db.execute(stmt)
                components = result.scalars().all()  # This now includes all components

                stmt = select(ShareConfiguration).where(
                    ShareConfiguration.workflow_id == workflow_id
                )
                result = await self.db.execute(stmt)
                share_configs = result.scalars().all()

                stmt = select(ScheduleConfiguration).where(
                    ScheduleConfiguration.workflow_id == workflow_id
                )
                result = await self.db.execute(stmt)
                schedule_config = result.scalar_one_or_none()

                stmt = select(IntegrationConfig).where(
                    IntegrationConfig.workflow_id == workflow_id
                )
                result = await self.db.execute(stmt)
                integrations = result.scalars().all()

                # Generate n8n workflow with all components (existing + new)
                n8n_result = self.n8n_creator.create_dashboard_workflow(
                    dashboard=dashboard,
                    workflow=workflow,
                    components=components,  # Contains all components now
                    share_configs=share_configs,
                    schedule_config=schedule_config,
                    integrations=integrations
                )

                # Add n8n workflow info to publish results
                publish_results["n8n_workflow"] = {
                    "success": True,
                    "file_path": n8n_result["file_path"],
                    "filename": n8n_result["filename"]
                }

            except Exception as e:
                # Log error but don't fail the publish operation
                publish_results["n8n_workflow"] = {
                    "success": False,
                    "error": str(e)
                }

            # Update ChromaDB
            await self._update_chroma(
                self.collection_name,
                str(workflow.id),
                {
                    "dashboard_id": str(dashboard.id),
                    "dashboard_name": dashboard.name,
                    "state": workflow.state.value,
                    "user_id": str(user_id)
                },
                {
                    "completed_at": workflow.completed_at.isoformat(),
                    "integrations": json.dumps([i.value for i in IntegrationType])
                }
            )

            await self.db.commit()

            return {
                "workflow_id": str(workflow.id),
                "dashboard_id": str(dashboard.id),
                "state": workflow.state.value,
                "publish_results": publish_results,
                "completed_at": workflow.completed_at.isoformat()
            }
    
    
    
    async def get_workflow_state(
        self,
        user_id: UUID,
        workflow_id: UUID
    ) -> Dict[str, Any]:
        """Get current workflow state and progress"""

        workflow = await self._get_workflow(workflow_id, user_id)

        # Get all components
        stmt = select(ThreadComponent).where(
            ThreadComponent.workflow_id == workflow_id
        ).order_by(ThreadComponent.sequence_order)
        result = await self.db.execute(stmt)
        components = result.scalars().all()

        # Get share configs
        stmt = select(ShareConfiguration).where(
            ShareConfiguration.workflow_id == workflow_id
        )
        result = await self.db.execute(stmt)
        share_configs = result.scalars().all()

        # Get schedule
        stmt = select(ScheduleConfiguration).where(
            ScheduleConfiguration.workflow_id == workflow_id
        )
        result = await self.db.execute(stmt)
        schedule = result.scalar_one_or_none()

        # Get integrations
        stmt = select(IntegrationConfig).where(
            IntegrationConfig.workflow_id == workflow_id
        )
        result = await self.db.execute(stmt)
        integrations = result.scalars().all()

        return {
            "workflow_id": str(workflow.id),
            "dashboard_id": str(workflow.dashboard_id),
            "state": workflow.state.value,
            "current_step": workflow.current_step,
            "progress_percentage": (workflow.current_step / 9) * 100,
            "components": {
                "total": len(components),
                "configured": sum(1 for c in components if c.is_configured)
            },
            "sharing": {
                "configured": len(share_configs) > 0,
                "targets": len(share_configs)
            },
            "schedule": {
                "configured": schedule is not None,
                "type": schedule.schedule_type.value if schedule else None,
                "next_run": schedule.next_run.isoformat() if schedule and schedule.next_run else None
            },
            "integrations": {
                "configured": len(integrations) > 0,
                "types": [i.integration_type.value for i in integrations]
            },
            "created_at": workflow.created_at.isoformat(),
            "updated_at": workflow.updated_at.isoformat(),
            "completed_at": workflow.completed_at.isoformat() if workflow.completed_at else None
        }

    async def rollback_to_version(
        self,
        user_id: UUID,
        workflow_id: UUID,
        version_id: UUID
    ) -> DashboardWorkflow:
        """Rollback workflow to a specific version"""

        workflow = await self._get_workflow(workflow_id, user_id)

        # Get version
        stmt = select(WorkflowVersion).where(
            and_(
                WorkflowVersion.id == version_id,
                WorkflowVersion.workflow_id == workflow_id
            )
        )
        result = await self.db.execute(stmt)
        version = result.scalar_one_or_none()

        if not version:
            raise ValueError(f"Version {version_id} not found")

        # Restore workflow state from snapshot
        snapshot = version.snapshot_data
        workflow.state = WorkflowState[snapshot["state"]]
        workflow.current_step = snapshot["current_step"]
        workflow.metadata = snapshot["metadata"]

        # Create new version for rollback
        await self._create_workflow_version(workflow, user_id, f"Rollback to version {version.version_number}")

        await self.db.commit()
        return workflow

    async def create_n8n_workflow(
        self,
        user_id: UUID,
        workflow_id: UUID
    ) -> Dict[str, Any]:
        """
        Manually create n8n workflow for an existing active dashboard
        Useful for re-generating workflows or creating them for dashboards that were active before this feature
        """

        workflow = await self._get_workflow(workflow_id, user_id)

        # Check if dashboard is active
        stmt = select(Dashboard).where(Dashboard.id == workflow.dashboard_id)
        result = await self.db.execute(stmt)
        dashboard = result.scalar_one_or_none()

        if not dashboard:
            raise ValueError(f"Dashboard {workflow.dashboard_id} not found")

        if not dashboard.is_active:
            raise ValueError(f"Dashboard {dashboard.id} is not active. Only active dashboards can have n8n workflows.")

        # Get all components, share configs, schedule, and integrations
        stmt = select(ThreadComponent).where(
            ThreadComponent.workflow_id == workflow_id
        ).order_by(ThreadComponent.sequence_order)
        result = await self.db.execute(stmt)
        components = result.scalars().all()

        stmt = select(ShareConfiguration).where(
            ShareConfiguration.workflow_id == workflow_id
        )
        result = await self.db.execute(stmt)
        share_configs = result.scalars().all()

        stmt = select(ScheduleConfiguration).where(
            ScheduleConfiguration.workflow_id == workflow_id
        )
        result = await self.db.execute(stmt)
        schedule_config = result.scalar_one_or_none()

        stmt = select(IntegrationConfig).where(
            IntegrationConfig.workflow_id == workflow_id
        )
        result = await self.db.execute(stmt)
        integrations = result.scalars().all()

        # Generate n8n workflow
        n8n_result = self.n8n_creator.create_dashboard_workflow(
            dashboard=dashboard,
            workflow=workflow,
            components=components,
            share_configs=share_configs,
            schedule_config=schedule_config,
            integrations=integrations
        )

        return {
            "success": True,
            "workflow_id": str(workflow_id),
            "dashboard_id": str(dashboard.id),
            "n8n_workflow": n8n_result
        }

    async def get_n8n_workflow_status(
        self,
        user_id: UUID,
        workflow_id: UUID
    ) -> Dict[str, Any]:
        """Get the status of n8n workflow for a dashboard"""

        workflow = await self._get_workflow(workflow_id, user_id)

        # Check if n8n workflow file exists
        file_path = self.n8n_creator.get_workflow_file_path(
            workflow.dashboard_id, workflow.id
        )

        if file_path:
            return {
                "workflow_id": str(workflow_id),
                "dashboard_id": str(workflow.dashboard_id),
                "n8n_workflow_exists": True,
                "file_path": file_path,
                "filename": f"dashboard_{workflow.dashboard_id}_{workflow.id}.json"
            }
        else:
            return {
                "workflow_id": str(workflow_id),
                "dashboard_id": str(workflow.dashboard_id),
                "n8n_workflow_exists": False,
                "file_path": None,
                "filename": None
            }

    def list_all_n8n_workflows(self) -> List[Dict[str, Any]]:
        """List all generated n8n workflow files"""

        return self.n8n_creator.list_workflow_files()

    async def delete_n8n_workflow(
        self,
        user_id: UUID,
        workflow_id: UUID
    ) -> Dict[str, Any]:
        """Delete n8n workflow file for a dashboard"""

        workflow = await self._get_workflow(workflow_id, user_id)

        # Delete the file
        deleted = self.n8n_creator.delete_workflow_file(
            workflow.dashboard_id, workflow.id
        )

        if deleted:
            return {
                "success": True,
                "workflow_id": str(workflow_id),
                "dashboard_id": str(workflow.dashboard_id),
                "message": "n8n workflow file deleted successfully"
            }
        else:
            return {
                "success": False,
                "workflow_id": str(workflow_id),
                "dashboard_id": str(workflow.dashboard_id),
                "message": "n8n workflow file not found or already deleted"
            }

    # Private helper methods

    async def _get_workflow(self, workflow_id: UUID, user_id: UUID) -> DashboardWorkflow:
        """Get workflow with permission check"""

        stmt = select(DashboardWorkflow).options(
            joinedload(DashboardWorkflow.share_configs),
            joinedload(DashboardWorkflow.schedule_config),
            joinedload(DashboardWorkflow.integrations),
            joinedload(DashboardWorkflow.thread_components)
        ).where(DashboardWorkflow.id == workflow_id)
        result = await self.db.execute(stmt)
        workflow = result.unique().scalar_one_or_none()

        if not workflow:
            stmt = select(ReportWorkflow).where(ReportWorkflow.id == workflow_id)
            result = await self.db.execute(stmt)
            workflow = result.scalar_one_or_none()
            if not workflow:
                raise ValueError(f"Workflow {workflow_id} not found")

        if workflow.user_id != user_id and not await self._check_user_permission(
            user_id, "dashboard", workflow.dashboard_id, "update"
        ):
            raise PermissionError("User doesn't have access to this workflow")

        return workflow

    async def _update_dashboard_content(self, workflow: DashboardWorkflow, user_id: UUID):
        """Update dashboard content with thread components.

        When the workflow was created via the Dashboard Creator Wizard the
        workflow_metadata will contain `template_data` (baseline kpis/charts
        from dashboardLayouts.json) and `layout_id` (the React renderer key).
        Components are merged into that template structure so the published
        dashboard uses the correct layout.

        When no template_data is present the legacy flat {status, components[]}
        shape is preserved for backwards compatibility.
        """

        stmt = select(ThreadComponent).where(
            ThreadComponent.workflow_id == workflow.id
        ).order_by(ThreadComponent.sequence_order)
        result = await self.db.execute(stmt)
        components = result.scalars().all()

        wf_meta: dict = workflow.workflow_metadata or {}
        template_data: dict = wf_meta.get("template_data") or {}
        layout_id: str = wf_meta.get("layout_id") or ""

        if template_data:
            # ── Template-structured content (Dashboard Creator Wizard) ──────
            # Start from the template baseline so layout panels always have
            # at least the placeholder values from dashboardLayouts.json.
            kpis: list = list(template_data.get("kpis") or [])
            charts: list = list(template_data.get("charts") or [])
            overview: str = template_data.get("overview") or ""
            executive_summary: str = template_data.get("executive_summary") or ""
            insights: list = list(template_data.get("insights") or [])

            # Build lookup maps so we can merge by position rather than
            # append duplicates on every content refresh.
            kpi_index = 0
            chart_index = 0

            for comp in components:
                comp_meta: dict = comp.thread_metadata or {}
                item_type: str = comp_meta.get("item_type") or comp.component_type.value
                chart_cfg: dict = comp.chart_config or {}

                if comp.component_type.value == "metric" and item_type == "kpi":
                    # Map KPI component → kpis[] slot (replace placeholder or append)
                    kpi_entry = {
                        "id": str(comp.id),
                        "name": chart_cfg.get("title") or comp.question or f"KPI {kpi_index + 1}",
                        "value": None,
                        "trend": chart_cfg.get("trend_direction"),
                        "status": "ok",
                        "description": comp.description or "",
                        "insights": chart_cfg.get("insights") or [],
                        "visualization_data": comp.visualization_data,
                        "chart_schema": comp.chart_schema or chart_cfg.get("vega_lite_spec"),
                    }
                    if kpi_index < len(kpis):
                        kpis[kpi_index] = {**kpis[kpi_index], **{k: v for k, v in kpi_entry.items() if v is not None}}
                    else:
                        kpis.append(kpi_entry)
                    kpi_index += 1

                elif comp.component_type.value in ("metric", "chart", "table"):
                    # Map metric/chart/table component → charts[] slot
                    vega_spec = chart_cfg.get("vega_lite_spec") or comp.chart_schema
                    chart_entry = {
                        "id": str(comp.id),
                        "type": chart_cfg.get("chart_type") or comp.component_type.value,
                        "title": chart_cfg.get("title") or comp.question or f"Chart {chart_index + 1}",
                        "overview": comp.description or chart_cfg.get("explanation") or "",
                        "insights": chart_cfg.get("insights") or [],
                        "source_schemas": chart_cfg.get("source_schemas") or [],
                        "focus_area": chart_cfg.get("focus_area") or "",
                        "visualization_data": comp.visualization_data,
                        "sample_data": comp.sample_data,
                        "table_data": comp.visualization_data if comp.component_type.value == "table" else None,
                        **({"chart_schema": vega_spec} if vega_spec else {}),
                    }
                    chart_entry = {k: v for k, v in chart_entry.items() if v is not None}
                    if chart_index < len(charts):
                        charts[chart_index] = {**charts[chart_index], **chart_entry}
                    else:
                        charts.append(chart_entry)
                    chart_index += 1

                elif comp.component_type.value == "insight":
                    insights.append({
                        "id": str(comp.id),
                        "text": comp.description or comp.question or "",
                        "metadata": comp_meta,
                    })

                elif comp.component_type.value == "overview":
                    overview = comp.description or comp.question or overview

                elif comp.component_type.value in ("narrative", "description"):
                    executive_summary = comp.description or comp.question or executive_summary

            content = {
                "status": workflow.state.value,
                "layout_id": layout_id,
                "overview": overview,
                "executive_summary": executive_summary,
                "kpis": kpis,
                "charts": charts,
                "insights": insights,
            }

        else:
            # ── Legacy flat content (pre-wizard workflows) ────────────────
            content = {
                "status": workflow.state.value,
                "components": []
            }
            for component in components:
                comp_data = {
                    "id": str(component.id),
                    "type": component.component_type.value,
                    "sequence": component.sequence_order,
                    "question": component.question,
                    "description": component.description,
                    "overview": component.overview,
                    "chart": component.chart_config,
                    "table": component.table_config,
                    "metadata": component.thread_metadata,
                    "sql_query": component.sql_query,
                    "executive_summary": component.executive_summary,
                    "data_overview": component.data_overview,
                    "visualization_data": component.visualization_data,
                    "sample_data": component.sample_data,
                    "chart_schema": component.chart_schema,
                    "reasoning": component.reasoning,
                    "data_count": component.data_count,
                    "validation_results": component.validation_results,
                    "configuration": component.configuration,
                    "is_configured": component.is_configured,
                }
                content["components"].append(comp_data)

        # Update dashboard
        stmt = select(Dashboard).where(Dashboard.id == workflow.dashboard_id)
        result = await self.db.execute(stmt)
        dashboard = result.scalar_one_or_none()

        dashboard.content = content
        dashboard.updated_at = datetime.utcnow()

        # Create dashboard version
        version = DashboardVersion(
            dashboard_id=dashboard.id,
            version=str(float(dashboard.version) + 0.1),
            content=content
        )
        self.db.add(version)
        dashboard.version = version.version

    async def _create_workflow_version(
        self,
        workflow: DashboardWorkflow,
        user_id: UUID,
        note: str = None
    ):
        """Create a version snapshot of the workflow"""

        # Get current version number
        try:

            stmt = select(func.max(WorkflowVersion.version_number)).where(
                WorkflowVersion.workflow_id == workflow.id
            )
            result = await self.db.execute(stmt)
            max_version = result.scalar() or 0

            # Create snapshot
            snapshot = {
                "state": workflow.state.value,
                "current_step": workflow.current_step,
                "metadata": workflow.workflow_metadata if workflow.workflow_metadata else {},
                "note": note,
                "components": [],
                "shares": [],
                "schedule": None,
                "integrations": []
            }

            # Add components to snapshot
            stmt = select(ThreadComponent).where(
                ThreadComponent.workflow_id == workflow.id
            )
            result = await self.db.execute(stmt)
            components = result.scalars().all()

            for comp in components:
                # Get enum value if it exists, otherwise convert to string
                component_type_value = getattr(comp.component_type, 'value', comp.component_type)

                comp_snapshot: dict = {
                    "id": str(comp.id),
                    "type": component_type_value,
                    "sequence_order": comp.sequence_order,
                    "question": comp.question,
                    "description": comp.description,
                    "overview": comp.overview,
                    "chart_config": comp.chart_config,
                    "table_config": comp.table_config,
                    "configuration": comp.configuration,
                    "is_configured": comp.is_configured,
                    "sql_query": comp.sql_query,
                    "executive_summary": comp.executive_summary,
                    "data_overview": comp.data_overview,
                    "visualization_data": comp.visualization_data,
                    "sample_data": comp.sample_data,
                    "chart_schema": comp.chart_schema,
                    "reasoning": comp.reasoning,
                    "data_count": comp.data_count,
                    "validation_results": comp.validation_results,
                    "metadata": comp.thread_metadata,
                }
                # Strip None values to keep snapshot lean
                snapshot["components"].append(
                    {k: v for k, v in comp_snapshot.items() if v is not None}
                )
            # from decimal import Decimal

            # new_version = str(Decimal(max_version) + Decimal('0.1'))
            print(f"New version: {max_version + 1}")
            # Create version9696
            version = WorkflowVersion(
                workflow_id=workflow.id,
                version_number=max_version + 1,
                state=workflow.state,
                snapshot_data=snapshot,
                created_by=user_id
            )
            self.db.add(version)
        except Exception as e:
            print("================== Error in workflow create ===================")
            traceback.print_exc()
            print("====================== Error Ended here=====================")

    async def _apply_sharing_to_dashboard(
        self,
        workflow: DashboardWorkflow,
        share_configs: List[ShareConfiguration],
        user_id: UUID
    ):
        """Apply sharing configuration to dashboard"""

        # Determine sharing level
        share_types = {config.share_type for config in share_configs}

        if ShareType.WORKSPACE in share_types:
            permission_level = SharingPermission.WORKSPACE
        elif ShareType.PROJECT in share_types:
            permission_level = SharingPermission.TEAM
        else:
            permission_level = SharingPermission.USER

        # Get target IDs
        target_ids = []
        for config in share_configs:
            if config.share_type in [ShareType.USER, ShareType.TEAM, ShareType.PROJECT]:
                try:
                    target_ids.append(UUID(config.target_id))
                except:
                    pass  # Skip invalid UUIDs (emails, etc.)

        # Update dashboard sharing
        if target_ids:
            await self.dashboard_service.share_dashboard(
                user_id=user_id,
                dashboard_id=workflow.dashboard_id,
                share_with=target_ids,
                permission_level=permission_level
            )

    def _convert_to_utc(self, dt: datetime, timezone_str: str) -> Optional[datetime]:
        """Convert datetime to UTC, handling both naive and timezone-aware datetimes"""
        if dt is None:
            return None
        
        try:
            import pytz
            if dt.tzinfo is None:
                # If naive datetime, assume it's in the specified timezone
                tz = pytz.timezone(timezone_str)
                return tz.localize(dt).astimezone(pytz.UTC).replace(tzinfo=None)
            else:
                # If timezone-aware, convert to UTC
                return dt.astimezone(pytz.UTC).replace(tzinfo=None)
        except Exception as e:
            print(f"ERROR: Failed to convert datetime to UTC: {e}")
            return dt.replace(tzinfo=None) if dt.tzinfo else dt

    async def _calculate_next_run(self, schedule: ScheduleConfiguration) -> Optional[datetime]:
        """Calculate next run time based on schedule configuration"""

        if schedule is None:
            print("ERROR: Schedule is None in _calculate_next_run")
            return None

        # Use UTC time for calculations
        now = datetime.utcnow()
        print(f"DEBUG: Calculating next run for schedule type: {schedule.schedule_type}")

        if schedule.schedule_type == ScheduleType.ONCE:
            return schedule.start_date if schedule.start_date and schedule.start_date > now else None
        elif schedule.schedule_type == ScheduleType.HOURLY:
            return now + timedelta(hours=1)
        elif schedule.schedule_type == ScheduleType.DAILY:
            return now + timedelta(days=1)
        elif schedule.schedule_type == ScheduleType.WEEKLY:
            return now + timedelta(weeks=1)
        elif schedule.schedule_type == ScheduleType.MONTHLY:
            # Approximate monthly
            return now + timedelta(days=30)
        elif schedule.schedule_type == ScheduleType.REALTIME:
            return now  # Always ready
        elif schedule.schedule_type == ScheduleType.CRON:
            # Would use croniter library in production
            return now + timedelta(hours=1)  # Placeholder

        return None

    async def _encrypt_connection_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt sensitive connection configuration"""
        # In production, use proper encryption (e.g., Fernet, KMS)
        # This is a placeholder
        return {
            "encrypted": True,
            "data": json.dumps(config)  # Would be encrypted in production
        }

    async def _publish_to_integration(
        self,
        dashboard: Dashboard,
        integration: IntegrationConfig,
        workflow: DashboardWorkflow
    ) -> Dict[str, Any]:
        """Publish dashboard to specific integration"""

        if integration.integration_type == IntegrationType.TABLEAU:
            return await self._publish_to_tableau(dashboard, integration)
        elif integration.integration_type == IntegrationType.POWERBI:
            return await self._publish_to_powerbi(dashboard, integration)
        elif integration.integration_type == IntegrationType.SLACK:
            return await self._publish_to_slack(dashboard, integration)
        elif integration.integration_type == IntegrationType.TEAMS:
            return await self._publish_to_teams(dashboard, integration)
        elif integration.integration_type == IntegrationType.CORNERSTONE:
            return await self._publish_to_cornerstone(dashboard, integration)
        elif integration.integration_type == IntegrationType.EMAIL:
            return await self._publish_to_email(dashboard, integration)
        # Add more integrations as needed

        return {"status": "not_implemented"}

    async def _publish_to_tableau(self, dashboard: Dashboard, integration: IntegrationConfig) -> Dict[str, Any]:
        """Publish to Tableau Server/Online"""
        # Placeholder - would use Tableau REST API
        return {
            "tableau_id": str(uuid.uuid4()),
            "url": f"https://tableau.example.com/dashboard/{dashboard.id}",
            "status": "published"
        }

    async def _publish_to_powerbi(self, dashboard: Dashboard, integration: IntegrationConfig) -> Dict[str, Any]:
        """Publish to Power BI"""
        # Placeholder - would use Power BI REST API
        return {
            "powerbi_id": str(uuid.uuid4()),
            "workspace": "Default",
            "url": f"https://powerbi.example.com/dashboard/{dashboard.id}",
            "status": "published"
        }

    async def _publish_to_slack(self, dashboard: Dashboard, integration: IntegrationConfig) -> Dict[str, Any]:
        """Publish to Slack"""
        # Placeholder - would use Slack API
        return {
            "channel": integration.mapping_config.get("channel", "#general"),
            "message_ts": str(datetime.utcnow().timestamp()),
            "status": "sent"
        }

    async def _publish_to_email(self, dashboard: Dashboard, integration: IntegrationConfig) -> Dict[str, Any]:
        """Send dashboard via email"""
        # Placeholder - would use email service
        return {
            "recipients": integration.mapping_config.get("recipients", []),
            "sent_at": datetime.utcnow().isoformat(),
            "status": "sent"
        }

    async def _publish_to_teams(self, dashboard: Dashboard, integration: IntegrationConfig) -> Dict[str, Any]:
        """Publish to Microsoft Teams"""
        # Placeholder - would use Microsoft Teams Graph API
        return {
            "teams_id": str(uuid.uuid4()),
            "channel": integration.mapping_config.get("channel", "General"),
            "team_id": integration.mapping_config.get("team_id"),
            "message_id": str(uuid.uuid4()),
            "url": f"https://teams.microsoft.com/l/message/{integration.mapping_config.get('team_id')}/{str(uuid.uuid4())}",
            "status": "published"
        }

    async def _publish_to_cornerstone(self, dashboard: Dashboard, integration: IntegrationConfig) -> Dict[str, Any]:
        """Publish to Cornerstone OnDemand"""
        # Placeholder - would use Cornerstone REST API
        return {
            "cornerstone_id": str(uuid.uuid4()),
            "course_id": integration.mapping_config.get("course_id"),
            "module_id": integration.mapping_config.get("module_id"),
            "url": f"https://cornerstone.example.com/course/{integration.mapping_config.get('course_id')}/module/{integration.mapping_config.get('module_id')}/dashboard/{dashboard.id}",
            "status": "published"
        }

    async def _send_email_invitation(self, email: str, workflow: DashboardWorkflow, user_id: UUID):
        """Send email invitation for dashboard sharing"""
        # Placeholder - would use email service
        pass

    async def _evaluate_alert_condition(
        self,
        component: ThreadComponent,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate alert condition based on component configuration and data
        """

        alert_config = component.alert_config or {}
        alert_type = alert_config.get("alert_type")
        condition_config = alert_config.get("condition_config", {})
        print(f"alert_type: {alert_type}, condition_config: {condition_config}")

        if alert_type == "threshold":
            return await self._evaluate_threshold_condition(component, data)
        elif alert_type == "anomaly":
            return await self._evaluate_anomaly_condition(component, data)
        elif alert_type == "trend":
            return await self._evaluate_trend_condition(component, data)
        elif alert_type == "comparison":
            return await self._evaluate_comparison_condition(component, data)
        elif alert_type == "schedule":
            return await self._evaluate_schedule_condition(component, data)
        else:
            return {"triggered": False, "reason": f"Unknown alert type: {alert_type}"}

    async def _evaluate_threshold_condition(
        self,
        component: ThreadComponent,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate threshold-based alert condition"""
        print(f"Evaluate Threshold Condition {data}, component={component}")
        alert_config = component.alert_config or {}
        condition_config = alert_config.get("condition_config", {})

        # Extract threshold parameters
        field = condition_config.get("field") or condition_config.get("metric")
        operator = condition_config.get("operator", ">")
        threshold_value = condition_config.get("threshold_value") or condition_config.get("value")

        if not all([field, threshold_value]):
            return {"triggered": False, "reason": "Missing threshold configuration"}

        # Get actual value from data
        actual_value = data.get(field)
        if actual_value is None:
            return {"triggered": False, "reason": f"Field '{field}' not found in data"}

        # Evaluate condition
        triggered = False
        if operator == ">":
            triggered = actual_value > threshold_value
        elif operator == ">=":
            triggered = actual_value >= threshold_value
        elif operator == "<":
            triggered = actual_value < threshold_value
        elif operator == "<=":
            triggered = actual_value <= threshold_value
        elif operator == "==":
            triggered = actual_value == threshold_value
        elif operator == "!=":
            triggered = actual_value != threshold_value

        return {
            "triggered": triggered,
            "field": field,
            "operator": operator,
            "threshold_value": threshold_value,
            "actual_value": actual_value,
            "condition_met": triggered
        }

    async def _evaluate_anomaly_condition(
        self,
        component: ThreadComponent,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate anomaly detection alert condition"""

        alert_config = component.alert_config or {}
        condition_config = alert_config.get("condition_config", {})
        anomaly_config = alert_config.get("anomaly_config", {})

        # Extract anomaly parameters
        field = condition_config.get("field") or condition_config.get("metric")
        method = anomaly_config.get("method", "zscore")
        sensitivity = anomaly_config.get("sensitivity", 2.0)

        if not field:
            return {"triggered": False, "reason": "Missing field configuration"}

        # Get actual value from data
        actual_value = data.get(field)
        if actual_value is None:
            return {"triggered": False, "reason": f"Field '{field}' not found in data"}

        # Simple anomaly detection (in production, use more sophisticated algorithms)
        # This is a placeholder implementation
        triggered = False
        if method == "zscore":
            # Placeholder: would calculate z-score based on historical data
            triggered = False  # Placeholder
        elif method == "iqr":
            # Placeholder: would use interquartile range method
            triggered = False  # Placeholder

        return {
            "triggered": triggered,
            "field": field,
            "method": method,
            "sensitivity": sensitivity,
            "actual_value": actual_value,
            "anomaly_detected": triggered
        }

    async def _evaluate_trend_condition(
        self,
        component: ThreadComponent,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate trend-based alert condition"""

        alert_config = component.alert_config or {}
        condition_config = alert_config.get("condition_config", {})
        trend_config = alert_config.get("trend_config", {})

        # Extract trend parameters
        field = condition_config.get("field") or condition_config.get("metric")
        trend_direction = condition_config.get("trend_direction") or condition_config.get("direction", "increasing")
        period = condition_config.get("period", "daily")

        if not field:
            return {"triggered": False, "reason": "Missing field configuration"}

        # Placeholder: would analyze trend based on historical data
        triggered = False

        return {
            "triggered": triggered,
            "field": field,
            "trend_direction": trend_direction,
            "period": period,
            "trend_detected": triggered
        }

    async def _evaluate_comparison_condition(
        self,
        component: ThreadComponent,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate comparison-based alert condition"""

        alert_config = component.alert_config or {}
        condition_config = alert_config.get("condition_config", {})

        # Extract comparison parameters
        field1 = condition_config.get("field1")
        field2 = condition_config.get("field2")
        operator = condition_config.get("operator", ">")

        if not all([field1, field2]):
            return {"triggered": False, "reason": "Missing field configuration"}

        # Get values from data
        value1 = data.get(field1)
        value2 = data.get(field2)

        if value1 is None or value2 is None:
            return {"triggered": False, "reason": "One or both fields not found in data"}

        # Evaluate comparison
        triggered = False
        if operator == ">":
            triggered = value1 > value2
        elif operator == ">=":
            triggered = value1 >= value2
        elif operator == "<":
            triggered = value1 < value2
        elif operator == "<=":
            triggered = value1 <= value2
        elif operator == "==":
            triggered = value1 == value2
        elif operator == "!=":
            triggered = value1 != value2

        return {
            "triggered": triggered,
            "field1": field1,
            "field2": field2,
            "operator": operator,
            "value1": value1,
            "value2": value2,
            "condition_met": triggered
        }

    async def _evaluate_schedule_condition(
        self,
        component: ThreadComponent,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate schedule-based alert condition"""

        alert_config = component.alert_config or {}
        condition_config = alert_config.get("condition_config", {})

        # Extract schedule parameters
        schedule_type = condition_config.get("schedule_type", "daily")
        time = condition_config.get("time", "09:00")
        days = condition_config.get("days", ["monday", "tuesday", "wednesday", "thursday", "friday"])

        # Placeholder: would check if current time matches schedule
        triggered = False

        return {
            "triggered": triggered,
            "schedule_type": schedule_type,
            "time": time,
            "days": days,
            "schedule_matched": triggered
        }

    async def _execute_alert_notifications(
        self,
        component: ThreadComponent,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute alert notifications through configured channels
        """

        alert_config = component.alert_config or {}
        notification_channels = alert_config.get("notification_channels", [])
        results = {}

        for channel in notification_channels:
            try:
                if channel == "email":
                    result = await self._send_alert_email(component, data)
                elif channel == "slack":
                    result = await self._send_alert_slack(component, data)
                elif channel == "webhook":
                    result = await self._send_alert_webhook(component, data)
                else:
                    result = {"success": False, "error": f"Unknown channel: {channel}"}

                results[channel] = result
            except Exception as e:
                results[channel] = {"success": False, "error": str(e)}

        return results

    async def _send_alert_email(self, component: ThreadComponent, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send alert notification via email"""
        # Placeholder - would use email service
        return {
            "success": True,
            "channel": "email",
            "message": f"Alert '{component.question}' triggered"
        }

    async def _send_alert_slack(self, component: ThreadComponent, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send alert notification via Slack"""
        # Placeholder - would use Slack API
        return {
            "success": True,
            "channel": "slack",
            "message": f"Alert '{component.question}' triggered"
        }

    async def _send_alert_webhook(self, component: ThreadComponent, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send alert notification via webhook"""
        # Placeholder - would use HTTP client
        return {
            "success": True,
            "channel": "webhook",
            "message": f"Alert '{component.question}' triggered"
        }

    async def update_dashboard_info(
        self,
        user_id: UUID,
        workflow_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        content: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dashboard:
        """Update dashboard basic information - creates draft version that doesn't affect published dashboard"""
        
        workflow = await self._get_workflow(workflow_id, user_id)
        
        # Get dashboard
        stmt = select(Dashboard).where(Dashboard.id == workflow.dashboard_id)
        result = await self.db.execute(stmt)
        dashboard = result.scalar_one_or_none()
        
        if not dashboard:
            raise ValueError(f"Dashboard not found for workflow {workflow_id}")
        
        # Store draft changes in workflow metadata instead of updating published dashboard
        draft_changes = workflow.workflow_metadata.get("draft_changes", {})
        
        # Update draft changes
        if name is not None:
            draft_changes["name"] = name
        if description is not None:
            draft_changes["description"] = description
        if content is not None:
            draft_changes["content"] = content
        if metadata is not None:
            draft_changes["metadata"] = metadata
            
        # Mark workflow as having draft changes
        draft_changes["has_draft_changes"] = True
        draft_changes["last_edited_at"] = datetime.utcnow().isoformat()
        draft_changes["edited_by"] = str(user_id)
        
        # Update workflow metadata
        workflow.workflow_metadata["draft_changes"] = draft_changes
        workflow.updated_at = datetime.utcnow()
        
        # Create workflow version for draft changes
        await self._create_workflow_version(workflow, user_id, note="Draft changes made")
        
        await self.db.commit()
        
        # Return dashboard with draft changes applied for preview
        preview_dashboard = Dashboard(
            id=dashboard.id,
            name=draft_changes.get("name", dashboard.name),
            description=draft_changes.get("description", dashboard.description),
            DashboardType=dashboard.DashboardType,
            is_active=dashboard.is_active,
            content=draft_changes.get("content", dashboard.content),
            version=dashboard.version,
            created_at=dashboard.created_at,
            updated_at=workflow.updated_at
        )
        
        return preview_dashboard

    async def remove_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        component_id: UUID
    ) -> bool:
        """Remove a thread component from the workflow"""
        
        workflow = await self._get_workflow(workflow_id, user_id)
        
        # Find and delete component
        stmt = select(ThreadComponent).where(
            and_(
                ThreadComponent.id == component_id,
                ThreadComponent.workflow_id == workflow_id
            )
        )
        result = await self.db.execute(stmt)
        component = result.scalar_one_or_none()
        
        if not component:
            raise ValueError(f"Component {component_id} not found")
        
        # Delete component
        await self.db.delete(component)
        
        # Mark as draft changes if workflow is published/active
        if workflow.state in [WorkflowState.PUBLISHED, WorkflowState.ACTIVE]:
            draft_changes = workflow.workflow_metadata.get("draft_changes", {})
            draft_changes["has_draft_changes"] = True
            draft_changes["last_edited_at"] = datetime.utcnow().isoformat()
            draft_changes["edited_by"] = str(user_id)
            workflow.workflow_metadata["draft_changes"] = draft_changes
        
        # Update dashboard content
        await self._update_dashboard_content(workflow, user_id)
        
        # Create version
        await self._create_workflow_version(workflow, user_id, note="Component removed" if workflow.state in [WorkflowState.PUBLISHED, WorkflowState.ACTIVE] else None)
        
        await self.db.commit()
        return True

    async def get_draft_changes(
        self,
        user_id: UUID,
        workflow_id: UUID
    ) -> Dict[str, Any]:
        """Get current draft changes for a workflow"""
        
        workflow = await self._get_workflow(workflow_id, user_id)
        draft_changes = workflow.workflow_metadata.get("draft_changes", {})
        
        return {
            "has_draft_changes": draft_changes.get("has_draft_changes", False),
            "last_edited_at": draft_changes.get("last_edited_at"),
            "edited_by": draft_changes.get("edited_by"),
            "last_published_at": draft_changes.get("last_published_at"),
            "published_by": draft_changes.get("published_by"),
            "changes": {
                "name": draft_changes.get("name"),
                "description": draft_changes.get("description"),
                "content": draft_changes.get("content"),
                "metadata": draft_changes.get("metadata")
            }
        }

    async def discard_draft_changes(
        self,
        user_id: UUID,
        workflow_id: UUID
    ) -> bool:
        """Discard all draft changes and revert to published state"""
        
        workflow = await self._get_workflow(workflow_id, user_id)
        
        # Clear draft changes
        draft_changes = workflow.workflow_metadata.get("draft_changes", {})
        draft_changes["has_draft_changes"] = False
        draft_changes["discarded_at"] = datetime.utcnow().isoformat()
        draft_changes["discarded_by"] = str(user_id)
        workflow.workflow_metadata["draft_changes"] = draft_changes
        
        # Create version for discard action
        await self._create_workflow_version(workflow, user_id, note="Draft changes discarded")
        
        await self.db.commit()
        return True

    async def get_dashboard_preview(
        self,
        user_id: UUID,
        workflow_id: UUID
    ) -> Dict[str, Any]:
        """Get dashboard preview with draft changes applied"""
        
        workflow = await self._get_workflow(workflow_id, user_id)
        
        # Get dashboard
        stmt = select(Dashboard).where(Dashboard.id == workflow.dashboard_id)
        result = await self.db.execute(stmt)
        dashboard = result.scalar_one_or_none()
        
        if not dashboard:
            raise ValueError(f"Dashboard not found for workflow {workflow_id}")
        
        # Get draft changes
        draft_changes = workflow.workflow_metadata.get("draft_changes", {})
        has_draft_changes = draft_changes.get("has_draft_changes", False)
        
        # Build preview with draft changes applied
        preview = {
            "dashboard_id": str(dashboard.id),
            "name": draft_changes.get("name", dashboard.name),
            "description": draft_changes.get("description", dashboard.description),
            "content": draft_changes.get("content", dashboard.content),
            "metadata": draft_changes.get("metadata"),
            "version": dashboard.version,
            "is_active": dashboard.is_active,
            "created_at": dashboard.created_at.isoformat(),
            "updated_at": dashboard.updated_at.isoformat(),
            "has_draft_changes": has_draft_changes,
            "draft_info": {
                "last_edited_at": draft_changes.get("last_edited_at"),
                "edited_by": draft_changes.get("edited_by"),
                "last_published_at": draft_changes.get("last_published_at"),
                "published_by": draft_changes.get("published_by")
            }
        }

        return preview

    # ==================== Template Methods ====================

    async def get_all_templates(self, template_type: Optional[str] = None) -> List[Dict[str, Any]]:
        stmt = select(DashboardTemplate).where(DashboardTemplate.is_active == True)
        if template_type:
            stmt = stmt.where(DashboardTemplate.template_type == template_type)
        stmt = stmt.order_by(DashboardTemplate.name)
        result = await self.db.execute(stmt)
        templates = result.scalars().all()
        return [self._serialize_template(t) for t in templates]

    async def get_template_by_id(self, template_id: UUID) -> Dict[str, Any]:
        stmt = select(DashboardTemplate).where(DashboardTemplate.id == template_id)
        result = await self.db.execute(stmt)
        template = result.scalar_one_or_none()
        if not template:
            raise ValueError(f"Template {template_id} not found")
        return self._serialize_template(template)

    async def get_template_by_source_id(self, source_id: str) -> Dict[str, Any]:
        stmt = select(DashboardTemplate).where(DashboardTemplate.source_id == source_id)
        result = await self.db.execute(stmt)
        template = result.scalar_one_or_none()
        if not template:
            raise ValueError(f"Template '{source_id}' not found")
        return self._serialize_template(template)

    async def sync_templates_from_compliance_skill(self) -> Dict[str, Any]:
        """
        Pull all templates from the compliance skill (port 8002) and upsert into Postgres.
        Returns counts of created/updated/failed records.
        """
        import httpx
        from app.core.settings import get_settings
        settings = get_settings()
        base_url = settings.compliance_skill_url

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{base_url}/templates")
            resp.raise_for_status()
            data = resp.json()

        raw_templates = data.get("templates", data) if isinstance(data, dict) else data
        created, updated, failed = 0, 0, 0

        for raw in raw_templates:
            try:
                source_id = raw.get("id") or raw.get("template_id")
                if not source_id:
                    failed += 1
                    continue

                # Fetch full detail for layout
                async with httpx.AsyncClient(timeout=30.0) as client:
                    detail_resp = await client.get(f"{base_url}/templates/{source_id}")
                    detail = detail_resp.json() if detail_resp.status_code == 200 else raw

                layout = {
                    k: detail.get(k)
                    for k in ("layout_grid", "panels", "primitives", "chart_types",
                               "has_chat", "has_graph", "has_filters", "strip_cells",
                               "components", "theme_hint", "filter_options")
                    if detail.get(k) is not None
                }

                stmt = select(DashboardTemplate).where(DashboardTemplate.source_id == source_id)
                result = await self.db.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    existing.name = raw.get("name", existing.name)
                    existing.description = raw.get("description", existing.description)
                    existing.category = raw.get("category", existing.category)
                    existing.complexity = raw.get("complexity", existing.complexity)
                    existing.domains = raw.get("domains", existing.domains)
                    existing.best_for = raw.get("best_for", existing.best_for)
                    existing.layout = layout
                    updated += 1
                else:
                    template = DashboardTemplate(
                        source_id=source_id,
                        name=raw.get("name", source_id),
                        description=raw.get("description"),
                        template_type=raw.get("template_type", "dashboard"),
                        category=raw.get("category"),
                        complexity=raw.get("complexity"),
                        domains=raw.get("domains", []),
                        best_for=raw.get("best_for", []),
                        layout=layout,
                    )
                    self.db.add(template)
                    created += 1
            except Exception:
                failed += 1

        await self.db.commit()
        return {"created": created, "updated": updated, "failed": failed, "total": len(raw_templates)}

    def _serialize_template(self, template: DashboardTemplate) -> Dict[str, Any]:
        return {
            "id": str(template.id),
            "source_id": template.source_id,
            "name": template.name,
            "description": template.description,
            "template_type": template.template_type,
            "category": template.category,
            "complexity": template.complexity,
            "domains": template.domains,
            "best_for": template.best_for,
            "layout": template.layout,
            "is_active": template.is_active,
            "created_at": template.created_at.isoformat(),
            "updated_at": template.updated_at.isoformat() if template.updated_at else None,
        }

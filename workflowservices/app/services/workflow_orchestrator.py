from typing import Optional, List, Dict, Any, Union
from uuid import UUID
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
from enum import Enum

def utc_now():
    """Get current UTC datetime for SQLAlchemy defaults"""
    return datetime.now(timezone.utc)

from app.services.dashboard_workflow import DashboardWorkflowService
from app.services.report_workflow import ReportWorkflowService
from app.services.alertservice import AlertService
from app.models.workflowmodels import (
    WorkflowState, ComponentType, ShareType, ScheduleType, IntegrationType,
    ThreadComponentCreate, ShareConfigCreate, ScheduleConfigCreate,
    IntegrationConfigCreate, DashboardWorkflow, ReportWorkflow,
    ThreadComponent, AlertThreadComponentCreate, AlertThreadComponentUpdate
)

class WorkflowType(str, Enum):
    DASHBOARD = "dashboard"
    REPORT = "report"
    ALERT = "alert"

class WorkflowOrchestrator:
    """
    Main orchestrator for managing all workflows (dashboards, reports, alerts)
    Provides a unified interface and handles workflow transitions
    """
    
    def __init__(self, db: AsyncSession, chroma_client=None):
        self.db = db
        self.dashboard_workflow_service = DashboardWorkflowService(db, chroma_client)
        self.report_workflow_service = ReportWorkflowService(db, chroma_client)
        self.alert_service = AlertService(db, chroma_client)
        self.active_workflows = {}  # Track active workflows in memory
    
    # ==================== Unified Workflow Creation ====================
    
    def create_workflow(
        self,
        user_id: UUID,
        workflow_type: WorkflowType,
        name: str,
        description: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a new workflow of any type"""
        
        if workflow_type == WorkflowType.DASHBOARD:
            workflow, dashboard = self.dashboard_workflow_service.create_workflow(
                user_id=user_id,
                dashboard_name=name,
                dashboard_description=description,
                project_id=kwargs.get("project_id"),
                workspace_id=kwargs.get("workspace_id"),
                initial_metadata=kwargs.get("metadata")
            )
            
            result = {
                "workflow_id": str(workflow.id),
                "workflow_type": WorkflowType.DASHBOARD,
                "resource_id": str(dashboard.id),
                "resource_type": "dashboard",
                "state": workflow.state.value,
                "created_at": workflow.created_at.isoformat()
            }
            
        elif workflow_type == WorkflowType.REPORT:
            workflow, report = self.report_workflow_service.create_report_workflow(
                user_id=user_id,
                report_name=name,
                report_description=description,
                report_template=kwargs.get("template", "standard"),
                project_id=kwargs.get("project_id"),
                workspace_id=kwargs.get("workspace_id"),
                workflow_id=kwargs.get("workflow_id")
            )
            
            result = {
                "workflow_id": str(workflow.id),
                "workflow_type": WorkflowType.REPORT,
                "resource_id": str(report.id),
                "resource_type": "report",
                "state": workflow.state.value,
                "created_at": workflow.created_at.isoformat()
            }
            
        elif workflow_type == WorkflowType.ALERT:
            # Alerts have a different workflow pattern
            from app.models.schema import TaskCreate
            task_data = TaskCreate(
                name=name,
                description=description,
                dataset_details=kwargs.get("dataset_details", []),
                metric_details=kwargs.get("metric_details", []),
                condition_details=kwargs.get("condition_details", [])
            )
            
            task = self.alert_service.create_task(
                user_id=user_id,
                task_data=task_data,
                project_id=kwargs.get("project_id"),
                workspace_id=kwargs.get("workspace_id")
            )
            
            result = {
                "workflow_id": str(task.id),
                "workflow_type": WorkflowType.ALERT,
                "resource_id": str(task.id),
                "resource_type": "task",
                "state": "active",
                "created_at": task.created_at.isoformat()
            }
        else:
            raise ValueError(f"Unknown workflow type: {workflow_type}")
        
        # Track active workflow
        self.active_workflows[result["workflow_id"]] = {
            "type": workflow_type,
            "user_id": str(user_id),
            "state": result["state"],
            "created_at": utc_now()
        }
        
        return result
    
    # ==================== Workflow Step Execution ====================
    
    async def execute_workflow_step(
        self,
        user_id: UUID,
        workflow_id: UUID,
        step_name: str,
        step_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a specific workflow step"""
        
        # Determine workflow type
        workflow_info = self._get_workflow_info(workflow_id)
        
        if workflow_info["type"] == WorkflowType.DASHBOARD:
            return await self._execute_dashboard_step(
                user_id, workflow_id, step_name, step_data
            )
        elif workflow_info["type"] == WorkflowType.REPORT:
            return await self._execute_report_step(
                user_id, workflow_id, step_name, step_data
            )
        elif workflow_info["type"] == WorkflowType.ALERT:
            return await self._execute_alert_step(
                user_id, workflow_id, step_name, step_data
            )
        else:
            raise ValueError(f"Unknown workflow type for ID {workflow_id}")
    
    async def _execute_dashboard_step(
        self,
        user_id: UUID,
        workflow_id: UUID,
        step_name: str,
        step_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute dashboard workflow step"""
        
        if step_name == "add_component":
            component = self.dashboard_workflow_service.add_thread_component(
                user_id=user_id,
                workflow_id=workflow_id,
                component_data=ThreadComponentCreate(**step_data),
                thread_message_id=step_data.get("thread_message_id")
            )
            return {"component_id": str(component.id), "success": True}
            
        elif step_name == "configure_component":
            component = self.dashboard_workflow_service.configure_thread_component(
                user_id=user_id,
                workflow_id=workflow_id,
                component_id=step_data["component_id"],
                configuration=step_data["configuration"]
            )
            return {"component_id": str(component.id), "configured": component.is_configured}
            
        elif step_name == "share":
            configs = self.dashboard_workflow_service.configure_sharing(
                user_id=user_id,
                workflow_id=workflow_id,
                share_config=ShareConfigCreate(**step_data)
            )
            return {"shared_with": len(configs), "success": True}
            
        elif step_name == "schedule":
            schedule = self.dashboard_workflow_service.configure_schedule(
                user_id=user_id,
                workflow_id=workflow_id,
                schedule_config=ScheduleConfigCreate(**step_data)
            )
            return {
                "schedule_type": schedule.schedule_type.value,
                "next_run": schedule.next_run.isoformat() if schedule.next_run else None
            }
            
        elif step_name == "add_integrations":
            integrations = self.dashboard_workflow_service.configure_integrations(
                user_id=user_id,
                workflow_id=workflow_id,
                integration_configs=[IntegrationConfigCreate(**i) for i in step_data["integrations"]]
            )
            return {"integrations_count": len(integrations), "success": True}
            
        elif step_name == "publish":
            result = self.dashboard_workflow_service.publish_dashboard(
                user_id=user_id,
                workflow_id=workflow_id
            )
            return result
        
        else:
            raise ValueError(f"Unknown step: {step_name}")
    
    async def _execute_report_step(
        self,
        user_id: UUID,
        workflow_id: UUID,
        step_name: str,
        step_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute report workflow step"""
        
        if step_name == "add_section":
            section = self.report_workflow_service.add_report_section(
                user_id=user_id,
                workflow_id=workflow_id,
                section_type=step_data["section_type"],
                section_config=step_data["section_config"]
            )
            return {"section_id": section["id"], "success": True}
            
        elif step_name == "configure_data_sources":
            sources = self.report_workflow_service.configure_data_sources(
                user_id=user_id,
                workflow_id=workflow_id,
                data_sources=step_data["data_sources"]
            )
            return {"sources_count": len(sources), "success": True}
            
        elif step_name == "configure_formatting":
            formatting = self.report_workflow_service.configure_report_formatting(
                user_id=user_id,
                workflow_id=workflow_id,
                formatting=step_data
            )
            return {"formatting": formatting, "success": True}
            
        elif step_name == "preview":
            preview = self.report_workflow_service.generate_report_preview(
                user_id=user_id,
                workflow_id=workflow_id,
                format_type=step_data.get("format", "html")
            )
            return preview
            
        elif step_name == "schedule":
            schedule = self.report_workflow_service.schedule_report_generation(
                user_id=user_id,
                workflow_id=workflow_id,
                schedule_config=ScheduleConfigCreate(**step_data),
                recipients=step_data.get("recipients")
            )
            return schedule
            
        elif step_name == "publish":
            result = self.report_workflow_service.publish_report(
                user_id=user_id,
                workflow_id=workflow_id,
                publish_options=step_data
            )
            return result
        
        else:
            raise ValueError(f"Unknown step: {step_name}")
    
    async def _execute_alert_step(
        self,
        user_id: UUID,
        workflow_id: UUID,
        step_name: str,
        step_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute alert workflow step"""
        
        if step_name == "evaluate":
            alerts = self.alert_service.evaluate_conditions(
                task_id=workflow_id,
                metric_values=step_data["metric_values"]
            )
            return {"triggered_alerts": alerts, "count": len(alerts)}
            
        elif step_name == "update":
            from app.models.schema import TaskUpdate
            task = self.alert_service.update_task(
                user_id=user_id,
                task_id=workflow_id,
                update_data=TaskUpdate(**step_data)
            )
            return {"task_id": str(task.id), "success": True}
        
        else:
            raise ValueError(f"Unknown step: {step_name}")
    
    # ==================== Batch Operations ====================
    
    async def execute_workflow_batch(
        self,
        user_id: UUID,
        workflow_id: UUID,
        steps: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Execute multiple workflow steps in sequence"""
        
        results = []
        
        for step in steps:
            try:
                result = await self.execute_workflow_step(
                    user_id=user_id,
                    workflow_id=workflow_id,
                    step_name=step["name"],
                    step_data=step["data"]
                )
                results.append({
                    "step": step["name"],
                    "success": True,
                    "result": result
                })
            except Exception as e:
                results.append({
                    "step": step["name"],
                    "success": False,
                    "error": str(e)
                })
                
                # Stop on error if specified
                if step.get("stop_on_error", True):
                    break
        
        return results
    
    # ==================== Workflow Management ====================
    
    def get_workflow_status(
        self,
        user_id: UUID,
        workflow_id: UUID
    ) -> Dict[str, Any]:
        """Get comprehensive workflow status"""
        
        workflow_info = self._get_workflow_info(workflow_id)
        
        if workflow_info["type"] == WorkflowType.DASHBOARD:
            return self.dashboard_workflow_service.get_workflow_state(
                user_id=user_id,
                workflow_id=workflow_id
            )
        elif workflow_info["type"] == WorkflowType.REPORT:
            workflow = self.report_workflow_service._get_report_workflow(
                workflow_id=workflow_id,
                user_id=user_id
            )
            return {
                "workflow_id": str(workflow.id),
                "report_id": str(workflow.report_id),
                "state": workflow.state.value,
                "current_step": workflow.current_step,
                "sections": len(workflow.sections or []),
                "data_sources": len(workflow.data_sources or []),
                "created_at": workflow.created_at.isoformat(),
                "updated_at": workflow.updated_at.isoformat()
            }
        elif workflow_info["type"] == WorkflowType.ALERT:
            task = self.alert_service.get_task(
                user_id=user_id,
                task_id=workflow_id
            )
            return {
                "task_id": str(task.id),
                "state": task.status,
                "datasets": len(task.datasets),
                "metrics": len(task.metrics),
                "conditions": len(task.conditions),
                "created_at": task.created_at.isoformat()
            }
        
        return {}
    
    def list_user_workflows(
        self,
        user_id: UUID,
        workflow_type: Optional[WorkflowType] = None,
        state: Optional[WorkflowState] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """List all workflows for a user"""
        
        workflows = []
        
        # Get dashboard workflows
        if not workflow_type or workflow_type == WorkflowType.DASHBOARD:
            dashboard_workflows = self.db.query(DashboardWorkflow).filter(
                DashboardWorkflow.user_id == user_id
            )
            if state:
                dashboard_workflows = dashboard_workflows.filter(
                    DashboardWorkflow.state == state
                )
            
            for wf in dashboard_workflows.limit(limit).all():
                workflows.append({
                    "workflow_id": str(wf.id),
                    "type": WorkflowType.DASHBOARD,
                    "resource_id": str(wf.dashboard_id),
                    "state": wf.state.value,
                    "created_at": wf.created_at.isoformat()
                })
        
        # Get report workflows
        if not workflow_type or workflow_type == WorkflowType.REPORT:
            from app.models.workflowmodels import ReportWorkflow
            report_workflows = self.db.query(ReportWorkflow).filter(
                ReportWorkflow.user_id == user_id
            )
            if state:
                report_workflows = report_workflows.filter(
                    ReportWorkflow.state == state
                )
            
            for wf in report_workflows.limit(limit).all():
                workflows.append({
                    "workflow_id": str(wf.id),
                    "type": WorkflowType.REPORT,
                    "resource_id": str(wf.report_id),
                    "state": wf.state.value,
                    "created_at": wf.created_at.isoformat()
                })
        
        return workflows[:limit]
    
    def cancel_workflow(
        self,
        user_id: UUID,
        workflow_id: UUID,
        reason: str = None
    ) -> bool:
        """Cancel an active workflow"""
        
        workflow_info = self._get_workflow_info(workflow_id)
        
        if workflow_info["type"] == WorkflowType.DASHBOARD:
            workflow = self.dashboard_workflow_service._get_workflow(workflow_id, user_id)
            workflow.state = WorkflowState.ARCHIVED
            workflow.error_message = reason or "Workflow cancelled by user"
        elif workflow_info["type"] == WorkflowType.REPORT:
            workflow = self.report_workflow_service._get_report_workflow(workflow_id, user_id)
            workflow.state = WorkflowState.ARCHIVED
            workflow.error_message = reason or "Workflow cancelled by user"
        else:
            return False
        
        self.db.commit()
        
        # Remove from active workflows
        if str(workflow_id) in self.active_workflows:
            del self.active_workflows[str(workflow_id)]
        
        return True
    
    def resume_workflow(
        self,
        user_id: UUID,
        workflow_id: UUID
    ) -> Dict[str, Any]:
        """Resume a paused or failed workflow"""
        
        workflow_info = self._get_workflow_info(workflow_id)
        
        if workflow_info["type"] == WorkflowType.DASHBOARD:
            workflow = self.dashboard_workflow_service._get_workflow(workflow_id, user_id)
            if workflow.state in [WorkflowState.PAUSED, WorkflowState.ERROR]:
                workflow.state = WorkflowState.CONFIGURING  # Resume from last known good state
                workflow.error_message = None
        elif workflow_info["type"] == WorkflowType.REPORT:
            workflow = self.report_workflow_service._get_report_workflow(workflow_id, user_id)
            if workflow.state in [WorkflowState.PAUSED, WorkflowState.ERROR]:
                workflow.state = WorkflowState.CONFIGURING
                workflow.error_message = None
        
        self.db.commit()
        
        return self.get_workflow_status(user_id, workflow_id)
    
    # ==================== Helper Methods ====================
    
    def _get_workflow_info(self, workflow_id: UUID) -> Dict[str, Any]:
        """Determine workflow type and basic info"""
        
        # Check in active workflows cache first
        if str(workflow_id) in self.active_workflows:
            return self.active_workflows[str(workflow_id)]
        
        # Check dashboard workflows
        dashboard_wf = self.db.query(DashboardWorkflow).filter(
            DashboardWorkflow.id == workflow_id
        ).first()
        if dashboard_wf:
            return {
                "type": WorkflowType.DASHBOARD,
                "user_id": str(dashboard_wf.user_id),
                "state": dashboard_wf.state.value
            }
        
        # Check report workflows
        from app.models.workflowmodels import ReportWorkflow
        report_wf = self.db.query(ReportWorkflow).filter(
            ReportWorkflow.id == workflow_id
        ).first()
        if report_wf:
            return {
                "type": WorkflowType.REPORT,
                "user_id": str(report_wf.user_id),
                "state": report_wf.state.value
            }
        
        # Check if it's an alert task
        from app.models.dbmodels import Task
        task = self.db.query(Task).filter(
            Task.id == workflow_id
        ).first()
        if task:
            return {
                "type": WorkflowType.ALERT,
                "user_id": None,  # Tasks don't have direct user association
                "state": task.status
            }
        
        raise ValueError(f"Workflow {workflow_id} not found")
    
    async def run_scheduled_workflows(self):
        """Background task to run scheduled workflows"""
        
        # This would be called by a scheduler (like Celery or APScheduler)
        # to execute workflows at their scheduled times
        
        from app.models.workflowmodels import ScheduleConfiguration
        
        now = utc_now()
        
        # Find workflows that need to run
        due_schedules = self.db.query(ScheduleConfiguration).filter(
            ScheduleConfiguration.next_run <= now,
            ScheduleConfiguration.is_active == True
        ).all()
        
        for schedule in due_schedules:
            try:
                # Execute the workflow
                workflow_info = self._get_workflow_info(schedule.workflow_id)
                
                if workflow_info["type"] == WorkflowType.DASHBOARD:
                    # Re-publish dashboard
                    await self._execute_dashboard_step(
                        user_id=UUID(workflow_info["user_id"]),
                        workflow_id=schedule.workflow_id,
                        step_name="publish",
                        step_data={}
                    )
                elif workflow_info["type"] == WorkflowType.REPORT:
                    # Re-generate and send report
                    await self._execute_report_step(
                        user_id=UUID(workflow_info["user_id"]),
                        workflow_id=schedule.workflow_id,
                        step_name="publish",
                        step_data={"formats": ["pdf", "html"], "send_email": True}
                    )
                
                # Update schedule for next run
                schedule.last_run = now
                schedule.run_count += 1
                schedule.next_run = self.dashboard_workflow_service._calculate_next_run(schedule)
                
            except Exception as e:
                print(f"Error executing scheduled workflow {schedule.workflow_id}: {e}")
        
        self.db.commit()
    
    # ==================== N8N Workflow Management ====================
    
    def create_n8n_workflow(
        self,
        user_id: UUID,
        workflow_id: UUID
    ) -> Dict[str, Any]:
        """Create n8n workflow for a dashboard"""
        
        return self.dashboard_workflow_service.create_n8n_workflow(
            user_id=user_id,
            workflow_id=workflow_id
        )
    
    def get_n8n_workflow_status(
        self,
        user_id: UUID,
        workflow_id: UUID
    ) -> Dict[str, Any]:
        """Get n8n workflow status for a dashboard"""
        
        return self.dashboard_workflow_service.get_n8n_workflow_status(
            user_id=user_id,
            workflow_id=workflow_id
        )
    
    def list_all_n8n_workflows(self) -> List[Dict[str, Any]]:
        """List all n8n workflow files"""
        
        return self.dashboard_workflow_service.list_all_n8n_workflows()
    
    def delete_n8n_workflow(
        self,
        user_id: UUID,
        workflow_id: UUID
    ) -> Dict[str, Any]:
        """Delete n8n workflow for a dashboard"""
        
        return self.dashboard_workflow_service.delete_n8n_workflow(
            user_id=user_id,
            workflow_id=workflow_id
        )
    
    # ==================== Alert Thread Component Management ====================
    
    def add_alert_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        alert_data: AlertThreadComponentCreate
    ) -> ThreadComponent:
        """Add alert as a thread message component to a dashboard workflow"""
        
        return self.dashboard_workflow_service.add_alert_thread_component(
            user_id=user_id,
            workflow_id=workflow_id,
            alert_data=alert_data
        )
    
    def update_alert_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        component_id: UUID,
        update_data: AlertThreadComponentUpdate
    ) -> ThreadComponent:
        """Update alert thread component"""
        
        return self.dashboard_workflow_service.update_alert_thread_component(
            user_id=user_id,
            workflow_id=workflow_id,
            component_id=component_id,
            update_data=update_data
        )
    
    def test_alert_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        component_id: UUID,
        test_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Test alert thread component"""
        
        return self.dashboard_workflow_service.test_alert_thread_component(
            user_id=user_id,
            workflow_id=workflow_id,
            component_id=component_id,
            test_data=test_data
        )
    
    def trigger_alert_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        component_id: UUID,
        trigger_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Trigger alert thread component manually"""
        
        return self.dashboard_workflow_service.trigger_alert_thread_component(
            user_id=user_id,
            workflow_id=workflow_id,
            component_id=component_id,
            trigger_data=trigger_data
        )
    
    # ==================== Report Alert Thread Component Management ====================
    
    def add_report_alert_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        alert_data: AlertThreadComponentCreate
    ) -> Dict[str, Any]:
        """Add alert as a thread message component to a report workflow"""
        
        return self.report_workflow_service.add_alert_thread_component(
            user_id=user_id,
            workflow_id=workflow_id,
            alert_data=alert_data
        )
    
    def update_report_alert_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        component_id: str,
        update_data: AlertThreadComponentUpdate
    ) -> Dict[str, Any]:
        """Update alert thread component in a report workflow"""
        
        return self.report_workflow_service.update_alert_thread_component(
            user_id=user_id,
            workflow_id=workflow_id,
            component_id=component_id,
            update_data=update_data
        )
    
    def get_report_alert_thread_components(
        self,
        user_id: UUID,
        workflow_id: UUID
    ) -> List[Dict[str, Any]]:
        """Get all alert thread components for a report workflow"""
        
        return self.report_workflow_service.get_alert_thread_components(
            user_id=user_id,
            workflow_id=workflow_id
        )
    
    def delete_report_alert_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        component_id: str
    ) -> Dict[str, Any]:
        """Delete alert thread component from a report workflow"""
        
        return self.report_workflow_service.delete_alert_thread_component(
            user_id=user_id,
            workflow_id=workflow_id,
            component_id=component_id
        )
    
    def test_report_alert_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        component_id: str,
        test_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Test alert thread component in a report workflow"""
        
        return self.report_workflow_service.test_alert_thread_component(
            user_id=user_id,
            workflow_id=workflow_id,
            component_id=component_id,
            test_data=test_data
        )
    
    def trigger_report_alert_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        component_id: str,
        trigger_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Trigger alert thread component manually in a report workflow"""
        
        return self.report_workflow_service.trigger_alert_thread_component(
            user_id=user_id,
            workflow_id=workflow_id,
            component_id=component_id,
            trigger_data=trigger_data
        )
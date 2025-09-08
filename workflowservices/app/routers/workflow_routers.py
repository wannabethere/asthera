from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

from app.core.dependencies import get_async_db_session
from app.services.workflow_orchestrator import WorkflowOrchestrator, WorkflowType
from app.models.workflowmodels import (
    WorkflowState, ThreadComponentCreate, ShareConfigCreate,
    ScheduleConfigCreate, IntegrationConfigCreate, AlertThreadComponentCreate,
    AlertThreadComponentUpdate, AlertType, AlertSeverity
)
# from app.auth import get_current_user  # Your auth implementation

router = APIRouter(
    prefix="/api/v1/workflows",
    tags=["workflows"]
)

# ==================== Workflow Creation ====================

@router.post("/dashboard")
async def create_dashboard_workflow(
    name: str,
    description: str,
    project_id: Optional[UUID] = None,
    workspace_id: Optional[UUID] = None,
    metadata: Optional[Dict[str, Any]] = None,
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """
    Create a new dashboard workflow
    This initializes a draft dashboard and starts the workflow process.
    """
    orchestrator = WorkflowOrchestrator(db)

    try:
        result = await orchestrator.create_workflow(
            user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),  # current_user.id
            workflow_type=WorkflowType.DASHBOARD,
            name=name,
            description=description,
            project_id=project_id,
            workspace_id=workspace_id,
            metadata=metadata
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/report")
async def create_report_workflow(
    name: str,
    description: str,
    template: str = "standard",
    project_id: Optional[UUID] = None,
    workspace_id: Optional[UUID] = None,
    workflow_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """
    Create a new report workflow
    This initializes a draft report with the specified template.
    """
    orchestrator = WorkflowOrchestrator(db)

    try:
        result = await orchestrator.create_workflow(
            user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),  # current_user.id
            workflow_type=WorkflowType.REPORT,
            name=name,
            description=description,
            template=template,
            project_id=project_id,
            workspace_id=workspace_id,
            workflow_id=workflow_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==================== Dashboard Workflow Steps ====================

@router.post("/{workflow_id}/dashboard/add-component")
async def add_dashboard_component(
    workflow_id: UUID,
    component: ThreadComponentCreate,
    thread_message_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """
    Add a thread component to the dashboard workflow
    Components include: question, description, overview, chart, table
    """
    orchestrator = WorkflowOrchestrator(db)

    step_data = component.dict()
    print(f"step_data: {step_data}")
    if thread_message_id:
        step_data["thread_message_id"] = thread_message_id

    try:
        result = await orchestrator.execute_workflow_step(
            user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),  # current_user.id
            workflow_id=workflow_id,
            step_name="add_component",
            step_data=step_data
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/{workflow_id}/dashboard/configure-component/{component_id}")
async def configure_dashboard_component(
    workflow_id: UUID,
    component_id: UUID,
    configuration: Dict[str, Any],
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """
    Configure a specific dashboard component
    Configuration includes layout, styling, data mappings, etc.
    """
    orchestrator = WorkflowOrchestrator(db)

    try:
        result = await orchestrator.execute_workflow_step(
            user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),  # current_user.id
            workflow_id=workflow_id,
            step_name="configure_component",
            step_data={
                "component_id": component_id,
                "configuration": configuration
            }
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{workflow_id}/dashboard/share")
async def configure_dashboard_sharing(
    workflow_id: UUID,
    share_config: ShareConfigCreate,
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """
    Configure sharing for the dashboard

    Share with users, teams, projects, or via email
    """
    orchestrator = WorkflowOrchestrator(db)

    try:
        result = await orchestrator.execute_workflow_step(
            user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),  # current_user.id
            workflow_id=workflow_id,
            step_name="share",
            step_data=share_config.model_dump()
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{workflow_id}/dashboard/schedule")
async def schedule_dashboard(
    workflow_id: UUID,
    schedule_config: ScheduleConfigCreate,
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """
    Configure scheduling for the dashboard

    Options: once, hourly, daily, weekly, monthly, cron, realtime
    """
    orchestrator = WorkflowOrchestrator(db)

    try:
        result = await orchestrator.execute_workflow_step(
            user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),  # current_user.id
            workflow_id=workflow_id,
            step_name="schedule",
            step_data=schedule_config.model_dump()
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{workflow_id}/dashboard/integrations")
async def configure_dashboard_integrations(
    workflow_id: UUID,
    integrations: List[IntegrationConfigCreate],
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """
    Configure integrations for publishing the dashboard

    Supports: Tableau, PowerBI, Slack, Teams, Email, etc.
    """
    orchestrator = WorkflowOrchestrator(db)

    try:
        result = await orchestrator.execute_workflow_step(
            user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),  # current_user.id
            workflow_id=workflow_id,
            step_name="add_integrations",
            step_data={"integrations": [i.model_dump() for i in integrations]}
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{workflow_id}/dashboard/publish")
async def publish_dashboard(
    workflow_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """
    Publish the dashboard to all configured integrations

    This finalizes the workflow and makes the dashboard active.
    """
    orchestrator = WorkflowOrchestrator(db)

    try:
        result = await orchestrator.execute_workflow_step(
            user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),  # current_user.id
            workflow_id=workflow_id,
            step_name="publish",
            step_data={}
        )

        # Optionally trigger background tasks for large publishes
        # background_tasks.add_task(publish_to_external_systems, workflow_id)

        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==================== Report Workflow Steps ====================

@router.post("/{workflow_id}/report/add-section")
async def add_report_section(
    workflow_id: UUID,
    section_type: str,
    section_config: Dict[str, Any],
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """Add a section to the report"""
    orchestrator = WorkflowOrchestrator(db)

    try:
        result = await orchestrator.execute_workflow_step(
            user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),  # current_user.id
            workflow_id=workflow_id,
            step_name="add_section",
            step_data={
                "section_type": section_type,
                "section_config": section_config
            }
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{workflow_id}/report/data-sources")
async def configure_report_data_sources(
    workflow_id: UUID,
    data_sources: List[Dict[str, Any]],
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """Configure data sources for the report"""
    orchestrator = WorkflowOrchestrator(db)

    try:
        result = await orchestrator.execute_workflow_step(
            user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),  # current_user.id
            workflow_id=workflow_id,
            step_name="configure_data_sources",
            step_data={"data_sources": data_sources}
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{workflow_id}/report/preview")
async def preview_report(
    workflow_id: UUID,
    format_type: str = Query(default="html", regex="^(html|pdf)$"),
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """Generate a preview of the report"""
    orchestrator = WorkflowOrchestrator(db)

    try:
        result = await orchestrator.execute_workflow_step(
            user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),  # current_user.id
            workflow_id=workflow_id,
            step_name="preview",
            step_data={"format": format_type}
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==================== Batch Operations ====================

@router.post("/{workflow_id}/batch")
async def execute_batch_steps(
    workflow_id: UUID,
    steps: List[Dict[str, Any]],
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """
    Execute multiple workflow steps in sequence

    Example:
    [
        {"name": "add_component", "data": {...}},
        {"name": "configure_component", "data": {...}},
        {"name": "share", "data": {...}}
    ]
    """
    orchestrator = WorkflowOrchestrator(db)

    try:
        results = await orchestrator.execute_workflow_batch(
            user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),  # current_user.id
            workflow_id=workflow_id,
            steps=steps
        )
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==================== Workflow Management ====================

@router.get("/{workflow_id}/status")
async def get_workflow_status(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """Get the current status and progress of a workflow"""
    orchestrator = WorkflowOrchestrator(db)

    try:
        status = await orchestrator.get_workflow_status(
            user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),  # current_user.id
            workflow_id=workflow_id
        )
        return status
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/list")
async def list_workflows(
    workflow_type: Optional[WorkflowType] = None,
    state: Optional[WorkflowState] = None,
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """List all workflows for the current user"""
    orchestrator = WorkflowOrchestrator(db)

    workflows = await orchestrator.list_user_workflows(
        user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),  # current_user.id
        workflow_type=workflow_type,
        state=state,
        limit=limit
    )

    return {"workflows": workflows, "count": len(workflows)}

@router.delete("/{workflow_id}")
async def cancel_workflow(
    workflow_id: UUID,
    reason: Optional[str] = None,
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """Cancel an active workflow"""
    orchestrator = WorkflowOrchestrator(db)
    try:
        success = await orchestrator.cancel_workflow(
            user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),  # current_user.id
            workflow_id=workflow_id,
            reason=reason
        )

        if success:
            return {"message": "Workflow cancelled successfully"}
        else:
            raise HTTPException(status_code=400, detail="Failed to cancel workflow")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{workflow_id}/resume")
async def resume_workflow(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """Resume a paused or failed workflow"""
    orchestrator = WorkflowOrchestrator(db)
    try:
        status = await orchestrator.resume_workflow(
            user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),  # current_user.id
            workflow_id=workflow_id
        )
        return status
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==================== Example Complete Workflow ====================

@router.post("/example/complete-dashboard-workflow")
async def example_complete_dashboard_workflow(
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """
    Example endpoint showing a complete dashboard workflow from start to finish
    """
    orchestrator = WorkflowOrchestrator(db)
    user_id = UUID("1e0cba86-110a-4d45-a205-182963880d75")  # current_user.id

    try:
        # Step 1: Create workflow
        workflow = orchestrator.create_workflow(
            user_id=user_id,
            workflow_type=WorkflowType.DASHBOARD,
            name="Sales Dashboard Q4 2024",
            description="Quarterly sales performance dashboard"
        )
        workflow_id = UUID(workflow["workflow_id"])

        # Step 2: Add components
        steps = [
            {
                "name": "add_component",
                "data": {
                    "component_type": "question",
                    "question": "What were our Q4 sales?",
                    "description": "Total sales for Q4 2024"
                }
            },
            {
                "name": "add_component",
                "data": {
                    "component_type": "chart",
                    "chart_config": {
                        "type": "bar",
                        "data_source": "sales_db",
                        "query": "SELECT month, revenue FROM sales WHERE quarter = 'Q4'"
                    }
                }
            },
            {
                "name": "add_component",
                "data": {
                    "component_type": "table",
                    "table_config": {
                        "columns": ["Product", "Units", "Revenue"],
                        "data_source": "sales_db"
                    }
                }
            }
        ]

        # Execute component additions
        batch_results = await orchestrator.execute_workflow_batch(
            user_id=user_id,
            workflow_id=workflow_id,
            steps=steps
        )

        # Step 3: Share
        await orchestrator.execute_workflow_step(
            user_id=user_id,
            workflow_id=workflow_id,
            step_name="share",
            step_data={
                "share_type": "team",
                "target_ids": ["sales-team-id"],
                "permissions": {"view": True, "edit": False}
            }
        )

        # Step 4: Schedule
        await orchestrator.execute_workflow_step(
            user_id=user_id,
            workflow_id=workflow_id,
            step_name="schedule",
            step_data={
                "schedule_type": "weekly",
                "timezone": "UTC",
                "configuration": {"day_of_week": "monday", "time": "09:00"}
            }
        )

        # Step 5: Add integrations
        await orchestrator.execute_workflow_step(
            user_id=user_id,
            workflow_id=workflow_id,
            step_name="add_integrations",
            step_data={
                "integrations": [
                    {
                        "integration_type": "slack",
                        "connection_config": {
                            "webhook_url": "https://hooks.slack.com/...",
                            "channel": "#sales"
                        }
                    },
                    {
                        "integration_type": "powerbi",
                        "connection_config": {
                            "workspace_id": "powerbi-workspace",
                            "api_key": "..."
                        }
                    }
                ]
            }
        )

        # Step 6: Publish
        final_result = await orchestrator.execute_workflow_step(
            user_id=user_id,
            workflow_id=workflow_id,
            step_name="publish",
            step_data={}
        )

        return {
            "success": True,
            "workflow_id": str(workflow_id),
            "dashboard_id": workflow["resource_id"],
            "final_state": final_result
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==================== Scheduled Tasks (for background processing) ====================

@router.post("/scheduled/run")
async def run_scheduled_workflows(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db_session)
):
    """
    Trigger execution of all due scheduled workflows
    This would typically be called by a scheduler/cron job
    """
    orchestrator = WorkflowOrchestrator(db)
    background_tasks.add_task(orchestrator.run_scheduled_workflows)
    return {"message": "Scheduled workflow execution triggered"}

# ==================== N8N Workflow Management ====================

@router.post("/{workflow_id}/n8n/create")
async def create_n8n_workflow(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """
    Manually create n8n workflow for an existing active dashboard
    """
    orchestrator = WorkflowOrchestrator(db)
    try:
        result = await orchestrator.create_n8n_workflow(
            user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),  # current_user.id
            workflow_id=workflow_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{workflow_id}/n8n/status")
async def get_n8n_workflow_status(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """
    Get the status of n8n workflow for a dashboard
    """
    orchestrator = WorkflowOrchestrator(db)
    try:
        result = await orchestrator.get_n8n_workflow_status(
            user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),  # current_user.id
            workflow_id=workflow_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/n8n/workflows")
async def list_all_n8n_workflows(
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """
    List all generated n8n workflow files
    """
    orchestrator = WorkflowOrchestrator(db)
    try:
        result = await orchestrator.list_all_n8n_workflows()
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{workflow_id}/n8n/delete")
async def delete_n8n_workflow(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """
    Delete n8n workflow file for a dashboard
    """
    orchestrator = WorkflowOrchestrator(db)
    try:
        result = await orchestrator.delete_n8n_workflow(
            user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),  # current_user.id
            workflow_id=workflow_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==================== Alert Thread Component Management ====================

@router.post("/{workflow_id}/alerts")
async def add_alert_thread_component(
    workflow_id: UUID,
    alert_data: AlertThreadComponentCreate,
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """
    Add an alert as a thread message component to the dashboard workflow
    """
    orchestrator = WorkflowOrchestrator(db)
    try:
        result = await orchestrator.add_alert_thread_component(
            user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),  # current_user.id
            workflow_id=workflow_id,
            alert_data=alert_data
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/{workflow_id}/alerts/{component_id}")
async def update_alert_thread_component(
    workflow_id: UUID,
    component_id: UUID,
    update_data: AlertThreadComponentUpdate,
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """
    Update an existing alert thread component
    """
    orchestrator = WorkflowOrchestrator(db)
    try:
        result = await orchestrator.update_alert_thread_component(
            user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),  # current_user.id
            workflow_id=workflow_id,
            component_id=component_id,
            update_data=update_data
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{workflow_id}/alerts/{component_id}/test")
async def test_alert_thread_component(
    workflow_id: UUID,
    component_id: UUID,
    test_data: Dict[str, Any] = None,
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """
    Test an alert thread component with sample data
    """
    orchestrator = WorkflowOrchestrator(db)
    try:
        result = await orchestrator.test_alert_thread_component(
            user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),  # current_user.id
            workflow_id=workflow_id,
            component_id=component_id,
            test_data=test_data or {}
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{workflow_id}/alerts/{component_id}/trigger")
async def trigger_alert_thread_component(
    workflow_id: UUID,
    component_id: UUID,
    trigger_data: Dict[str, Any] = None,
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """
    Manually trigger an alert thread component for testing
    """
    orchestrator = WorkflowOrchestrator(db)
    try:
        result = await orchestrator.trigger_alert_thread_component(
            user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),  # current_user.id
            workflow_id=workflow_id,
            component_id=component_id,
            trigger_data=trigger_data or {}
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==================== Report Alert Thread Component Management ====================

@router.post("/reports/{workflow_id}/alerts")
async def add_report_alert_thread_component(
    workflow_id: UUID,
    alert_data: AlertThreadComponentCreate,
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """
    Add an alert as a thread message component to a report workflow
    """
    orchestrator = WorkflowOrchestrator(db)
    try:
        result = await orchestrator.add_report_alert_thread_component(
            user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),  # current_user.id
            workflow_id=workflow_id,
            alert_data=alert_data
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/reports/{workflow_id}/alerts/{alert_id}")
async def update_report_alert_thread_component(
    workflow_id: UUID,
    alert_id: UUID,
    update_data: AlertThreadComponentUpdate,
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """
    Update an existing alert thread component in a report workflow
    """
    orchestrator = WorkflowOrchestrator(db)
    try:
        result = await orchestrator.update_report_alert_thread_component(
            user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),  # current_user.id
            workflow_id=workflow_id,
            alert_id=alert_id,
            update_data=update_data
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/reports/{workflow_id}/alerts")
async def get_report_alert_thread_components(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """
    Get all alert thread components for a report workflow
    """
    orchestrator = WorkflowOrchestrator(db)
    try:
        result = await orchestrator.get_report_alert_thread_components(
            user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),  # current_user.id
            workflow_id=workflow_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/reports/{workflow_id}/alerts/{alert_id}")
async def delete_report_alert_thread_component(
    workflow_id: UUID,
    alert_id: UUID,
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """
    Delete an alert thread component from a report workflow
    """
    orchestrator = WorkflowOrchestrator(db)
    try:
        result = await orchestrator.delete_report_alert_thread_component(
            user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),  # current_user.id
            workflow_id=workflow_id,
            alert_id=str(alert_id)
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/reports/{workflow_id}/alerts/{alert_id}/test")
async def test_report_alert_thread_component(
    workflow_id: UUID,
    alert_id: UUID,
    test_data: Dict[str, Any] = None,
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """
    Test an alert thread component in a report workflow with sample data
    """
    orchestrator = WorkflowOrchestrator(db)
    try:
        result = await orchestrator.test_report_alert_thread_component(
            user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),  # current_user.id
            workflow_id=workflow_id,
            alert_id=alert_id,
            test_data=test_data or {}
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/reports/{workflow_id}/alerts/{alert_id}/trigger")
async def trigger_report_alert_thread_component(
    workflow_id: UUID,
    alert_id: UUID,
    trigger_data: Dict[str, Any] = None,
    db: AsyncSession = Depends(get_async_db_session),
    # current_user = Depends(get_current_user)
):
    """
    Manually trigger an alert thread component in a report workflow for testing
    """
    orchestrator = WorkflowOrchestrator(db)
    try:
        result = await orchestrator.trigger_report_alert_thread_component(
            user_id=UUID("1e0cba86-110a-4d45-a205-182963880d75"),  # current_user.id
            workflow_id=workflow_id,
            alert_id=alert_id,
            trigger_data=trigger_data or {}
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

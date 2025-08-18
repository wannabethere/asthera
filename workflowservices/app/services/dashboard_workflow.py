from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
import uuid
from datetime import datetime, timedelta
import json
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.services.baseservice import BaseService, SharingPermission
from app.services.dashboardservice import DashboardService
from app.services.n8n_workflow_creator import N8nWorkflowCreator
from app.models.workflowmodels import (
    DashboardWorkflow, ThreadComponent, ShareConfiguration,
    ScheduleConfiguration, IntegrationConfig, WorkflowVersion,
    WorkflowState, ComponentType, ShareType, ScheduleType, IntegrationType,
    ThreadComponentCreate, ThreadComponentUpdate, ShareConfigCreate,
    ScheduleConfigCreate, IntegrationConfigCreate, AlertType, AlertSeverity,
    AlertStatus, AlertThreadComponentCreate, AlertThreadComponentUpdate
)
from app.models.thread import Thread, ThreadMessage
from app.models.dbmodels import Dashboard, DashboardVersion
from app.models.schema import DashboardCreate, DashboardUpdate

class DashboardWorkflowService(BaseService):
    """Service for managing dashboard creation workflows"""
    
    def __init__(self, db: Session, chroma_client=None):
        super().__init__(db, chroma_client)
        self.collection_name = "dashboard_workflows"
        self.dashboard_service = DashboardService(db, chroma_client)
        self.n8n_creator = N8nWorkflowCreator()
    
    def create_workflow(
        self,
        user_id: UUID,
        dashboard_name: str,
        dashboard_description: str,
        project_id: Optional[UUID] = None,
        workspace_id: Optional[UUID] = None,
        initial_metadata: Dict[str, Any] = None
    ) -> Tuple[DashboardWorkflow, Dashboard]:
        """
        Step 1: Create initial placeholder dashboard and workflow
        """
        
        # Create placeholder dashboard in draft state
        dashboard_data = DashboardCreate(
            name=dashboard_name,
            description=dashboard_description,
            DashboardType="Dynamic",
            is_active=False,  # Not active until workflow completes
            content={"status": "draft", "components": []}
        )
        
        dashboard = self.dashboard_service.create_dashboard(
            user_id=user_id,
            dashboard_data=dashboard_data,
            project_id=project_id,
            workspace_id=workspace_id,
            sharing_permission=SharingPermission.PRIVATE  # Private until shared
        )
        
        # Create workflow
        workflow = DashboardWorkflow(
            dashboard_id=dashboard.id,
            user_id=user_id,
            state=WorkflowState.DRAFT,
            current_step=1,
            metadata=initial_metadata or {
                "dashboard_name": dashboard_name,
                "project_id": str(project_id) if project_id else None,
                "workspace_id": str(workspace_id) if workspace_id else None
            }
        )
        
        self.db.add(workflow)
        
        # Create initial version
        self._create_workflow_version(workflow, user_id)
        
        # Add to ChromaDB for searchability
        self._add_to_chroma(
            self.collection_name,
            str(workflow.id),
            {
                "dashboard_id": str(dashboard.id),
                "dashboard_name": dashboard_name,
                "state": workflow.state.value,
                "user_id": str(user_id)
            },
            {
                "project_id": str(project_id) if project_id else None,
                "workspace_id": str(workspace_id) if workspace_id else None,
                "created_at": datetime.utcnow().isoformat()
            }
        )
        
        self.db.commit()
        return workflow, dashboard
    
    def add_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        component_data: ThreadComponentCreate,
        thread_message_id: Optional[UUID] = None
    ) -> ThreadComponent:
        """
        Step 2: Add thread message components to workflow
        """
        
        workflow = self._get_workflow(workflow_id, user_id)
        
        # Validate state
        if workflow.state not in [WorkflowState.DRAFT, WorkflowState.CONFIGURING]:
            raise ValueError(f"Cannot add components in {workflow.state} state")
        
        # Get next sequence order
        max_order = self.db.query(func.max(ThreadComponent.sequence_order)).filter(
            ThreadComponent.workflow_id == workflow_id
        ).scalar() or 0
        
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
            is_configured=False
        )
        
        self.db.add(component)
        
        # Update workflow state if first component
        if workflow.state == WorkflowState.DRAFT:
            workflow.state = WorkflowState.CONFIGURING
            workflow.current_step = 2
        
        # Update dashboard content
        self._update_dashboard_content(workflow, user_id)
        
        # Create version
        self._create_workflow_version(workflow, user_id)
        
        self.db.commit()
        return component
    
    def add_alert_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        alert_data: AlertThreadComponentCreate,
        thread_message_id: Optional[UUID] = None
    ) -> ThreadComponent:
        """
        Add an alert as a thread message component to the dashboard workflow
        """
        
        workflow = self._get_workflow(workflow_id, user_id)
        
        # Validate state
        if workflow.state not in [WorkflowState.DRAFT, WorkflowState.CONFIGURING]:
            raise ValueError(f"Cannot add alert components in {workflow.state} state")
        
        # Get next sequence order
        max_order = self.db.query(func.max(ThreadComponent.sequence_order)).filter(
            ThreadComponent.workflow_id == workflow_id
        ).scalar() or 0
        
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
            is_configured=True  # Alerts are configured when created
        )
        
        self.db.add(component)
        
        # Update workflow state if first component
        if workflow.state == WorkflowState.DRAFT:
            workflow.state = WorkflowState.CONFIGURING
            workflow.current_step = 2
        
        # Update dashboard content
        self._update_dashboard_content(workflow, user_id)
        
        # Create version
        self._create_workflow_version(workflow, user_id)
        
        self.db.commit()
        return component
    
    def configure_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        component_id: UUID,
        configuration: Dict[str, Any]
    ) -> ThreadComponent:
        """
        Step 3: Configure individual thread message components
        """
        
        workflow = self._get_workflow(workflow_id, user_id)
        
        # Get component
        component = self.db.query(ThreadComponent).filter(
            and_(
                ThreadComponent.id == component_id,
                ThreadComponent.workflow_id == workflow_id
            )
        ).first()
        
        if not component:
            raise ValueError(f"Component {component_id} not found")
        
        # Update configuration
        component.configuration = configuration
        component.is_configured = True
        component.updated_at = datetime.utcnow()
        
        # Check if all components are configured
        all_configured = self.db.query(ThreadComponent).filter(
            and_(
                ThreadComponent.workflow_id == workflow_id,
                ThreadComponent.is_configured == False
            )
        ).count() == 0
        
        if all_configured and workflow.state == WorkflowState.CONFIGURING:
            workflow.state = WorkflowState.CONFIGURED
            workflow.current_step = 3
        
        # Update dashboard
        self._update_dashboard_content(workflow, user_id)
        
        # Create version
        self._create_workflow_version(workflow, user_id)
        
        self.db.commit()
        return component
    
    def update_alert_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        component_id: UUID,
        update_data: AlertThreadComponentUpdate
    ) -> ThreadComponent:
        """
        Update an existing alert thread component
        """
        
        workflow = self._get_workflow(workflow_id, user_id)
        
        # Get component
        component = self.db.query(ThreadComponent).filter(
            and_(
                ThreadComponent.id == component_id,
                ThreadComponent.workflow_id == workflow_id,
                ThreadComponent.component_type == ComponentType.ALERT
            )
        ).first()
        
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
        
        component.updated_at = datetime.utcnow()
        
        # Update dashboard content
        self._update_dashboard_content(workflow, user_id)
        
        # Create version
        self._create_workflow_version(workflow, user_id)
        
        self.db.commit()
        return component
    
    def test_alert_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        component_id: UUID,
        test_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Test an alert thread component with sample data
        """
        
        workflow = self._get_workflow(workflow_id, user_id)
        
        # Get alert component
        component = self.db.query(ThreadComponent).filter(
            and_(
                ThreadComponent.id == component_id,
                ThreadComponent.workflow_id == workflow_id,
                ThreadComponent.component_type == ComponentType.ALERT
            )
        ).first()
        
        if not component:
            raise ValueError(f"Alert component {component_id} not found")
        
        # Test the alert condition
        try:
            test_result = self._evaluate_alert_condition(component, test_data or {})
            
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
    
    def trigger_alert_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        component_id: UUID,
        trigger_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Manually trigger an alert thread component for testing
        """
        
        workflow = self._get_workflow(workflow_id, user_id)
        
        # Get alert component
        component = self.db.query(ThreadComponent).filter(
            and_(
                ThreadComponent.id == component_id,
                ThreadComponent.workflow_id == workflow_id,
                ThreadComponent.component_type == ComponentType.ALERT
            )
        ).first()
        
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
            trigger_result = self._execute_alert_notifications(component, trigger_data or {})
            
            # Update alert status
            component.last_triggered = datetime.utcnow()
            component.trigger_count += 1
            component.alert_status = AlertStatus.TRIGGERED
            
            self.db.commit()
            
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
    
    def update_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        component_id: UUID,
        update_data: ThreadComponentUpdate
    ) -> ThreadComponent:
        """
        Update existing thread component
        """
        
        workflow = self._get_workflow(workflow_id, user_id)
        
        component = self.db.query(ThreadComponent).filter(
            and_(
                ThreadComponent.id == component_id,
                ThreadComponent.workflow_id == workflow_id
            )
        ).first()
        
        if not component:
            raise ValueError(f"Component {component_id} not found")
        
        # Update fields
        for field, value in update_data.dict(exclude_unset=True).items():
            setattr(component, field, value)
        
        component.updated_at = datetime.utcnow()
        
        # Update dashboard
        self._update_dashboard_content(workflow, user_id)
        
        # Create version
        self._create_workflow_version(workflow, user_id)
        
        self.db.commit()
        return component
    
    def configure_sharing(
        self,
        user_id: UUID,
        workflow_id: UUID,
        share_config: ShareConfigCreate
    ) -> List[ShareConfiguration]:
        """
        Step 4: Configure sharing settings
        """
        
        workflow = self._get_workflow(workflow_id, user_id)
        
        # Validate state
        if workflow.state not in [WorkflowState.CONFIGURED, WorkflowState.SHARING]:
            raise ValueError(f"Cannot configure sharing in {workflow.state} state")
        
        # Update state
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
                self._send_email_invitation(target_id, workflow, user_id)
        
        # Update workflow state
        workflow.state = WorkflowState.SHARED
        workflow.current_step = 5
        
        # Update dashboard sharing
        self._apply_sharing_to_dashboard(workflow, share_configs, user_id)
        
        # Create version
        self._create_workflow_version(workflow, user_id)
        
        self.db.commit()
        return share_configs
    
    def configure_schedule(
        self,
        user_id: UUID,
        workflow_id: UUID,
        schedule_config: ScheduleConfigCreate
    ) -> ScheduleConfiguration:
        """
        Step 5: Configure scheduling
        """
        
        workflow = self._get_workflow(workflow_id, user_id)
        
        # Validate state
        if workflow.state not in [WorkflowState.SHARED, WorkflowState.SCHEDULING]:
            raise ValueError(f"Cannot configure schedule in {workflow.state} state")
        
        # Update state
        if workflow.state == WorkflowState.SHARED:
            workflow.state = WorkflowState.SCHEDULING
            workflow.current_step = 6
        
        # Create or update schedule configuration
        schedule = self.db.query(ScheduleConfiguration).filter(
            ScheduleConfiguration.workflow_id == workflow_id
        ).first()
        
        if not schedule:
            schedule = ScheduleConfiguration(
                workflow_id=workflow_id,
                schedule_type=schedule_config.schedule_type,
                cron_expression=schedule_config.cron_expression,
                timezone=schedule_config.timezone,
                start_date=schedule_config.start_date,
                end_date=schedule_config.end_date,
                configuration=schedule_config.configuration
            )
            self.db.add(schedule)
        else:
            schedule.schedule_type = schedule_config.schedule_type
            schedule.cron_expression = schedule_config.cron_expression
            schedule.timezone = schedule_config.timezone
            schedule.start_date = schedule_config.start_date
            schedule.end_date = schedule_config.end_date
            schedule.configuration = schedule_config.configuration
            schedule.updated_at = datetime.utcnow()
        
        # Calculate next run time
        schedule.next_run = self._calculate_next_run(schedule)
        
        # Update workflow state
        workflow.state = WorkflowState.SCHEDULED
        workflow.current_step = 7
        
        # Create version
        self._create_workflow_version(workflow, user_id)
        
        self.db.commit()
        return schedule
    
    def configure_integrations(
        self,
        user_id: UUID,
        workflow_id: UUID,
        integration_configs: List[IntegrationConfigCreate]
    ) -> List[IntegrationConfig]:
        """
        Step 6: Configure integrations for publishing
        """
        
        workflow = self._get_workflow(workflow_id, user_id)
        
        # Validate state
        if workflow.state not in [WorkflowState.SCHEDULED, WorkflowState.PUBLISHING]:
            raise ValueError(f"Cannot configure integrations in {workflow.state} state")
        
        # Update state
        if workflow.state == WorkflowState.SCHEDULED:
            workflow.state = WorkflowState.PUBLISHING
            workflow.current_step = 8
        
        integrations = []
        
        for config_data in integration_configs:
            # Encrypt sensitive connection data
            encrypted_config = self._encrypt_connection_config(config_data.connection_config)
            
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
        self._create_workflow_version(workflow, user_id)
        
        self.db.commit()
        return integrations
    
    def publish_dashboard(
        self,
        user_id: UUID,
        workflow_id: UUID
    ) -> Dict[str, Any]:
        """
        Step 7: Publish dashboard to all configured integrations
        """
        
        workflow = self._get_workflow(workflow_id, user_id)
        
        # Validate state
        if workflow.state != WorkflowState.PUBLISHING:
            raise ValueError(f"Cannot publish in {workflow.state} state")
        
        # Get dashboard
        dashboard = self.db.query(Dashboard).filter(
            Dashboard.id == workflow.dashboard_id
        ).first()
        
        # Get integrations
        integrations = self.db.query(IntegrationConfig).filter(
            IntegrationConfig.workflow_id == workflow_id
        ).all()
        
        publish_results = {}
        
        for integration in integrations:
            try:
                result = self._publish_to_integration(
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
        self._create_workflow_version(workflow, user_id)
        
        # Create n8n workflow automatically when dashboard becomes active
        try:
            # Get all components, share configs, schedule, and integrations
            components = self.db.query(ThreadComponent).filter(
                ThreadComponent.workflow_id == workflow_id
            ).order_by(ThreadComponent.sequence_order).all()
            
            share_configs = self.db.query(ShareConfiguration).filter(
                ShareConfiguration.workflow_id == workflow_id
            ).all()
            
            schedule_config = self.db.query(ScheduleConfiguration).filter(
                ScheduleConfiguration.workflow_id == workflow_id
            ).first()
            
            integrations = self.db.query(IntegrationConfig).filter(
                IntegrationConfig.workflow_id == workflow_id
            ).all()
            
            # Generate n8n workflow
            n8n_result = self.n8n_creator.create_dashboard_workflow(
                dashboard=dashboard,
                workflow=workflow,
                components=components,
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
        self._update_chroma(
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
                "integrations": [i.value for i in IntegrationType]
            }
        )
        
        self.db.commit()
        
        return {
            "workflow_id": str(workflow.id),
            "dashboard_id": str(dashboard.id),
            "state": workflow.state.value,
            "publish_results": publish_results,
            "completed_at": workflow.completed_at.isoformat()
        }
    
    def get_workflow_state(
        self,
        user_id: UUID,
        workflow_id: UUID
    ) -> Dict[str, Any]:
        """Get current workflow state and progress"""
        
        workflow = self._get_workflow(workflow_id, user_id)
        
        # Get all components
        components = self.db.query(ThreadComponent).filter(
            ThreadComponent.workflow_id == workflow_id
        ).order_by(ThreadComponent.sequence_order).all()
        
        # Get share configs
        share_configs = self.db.query(ShareConfiguration).filter(
            ShareConfiguration.workflow_id == workflow_id
        ).all()
        
        # Get schedule
        schedule = self.db.query(ScheduleConfiguration).filter(
            ScheduleConfiguration.workflow_id == workflow_id
        ).first()
        
        # Get integrations
        integrations = self.db.query(IntegrationConfig).filter(
            IntegrationConfig.workflow_id == workflow_id
        ).all()
        
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
    
    def rollback_to_version(
        self,
        user_id: UUID,
        workflow_id: UUID,
        version_id: UUID
    ) -> DashboardWorkflow:
        """Rollback workflow to a specific version"""
        
        workflow = self._get_workflow(workflow_id, user_id)
        
        # Get version
        version = self.db.query(WorkflowVersion).filter(
            and_(
                WorkflowVersion.id == version_id,
                WorkflowVersion.workflow_id == workflow_id
            )
        ).first()
        
        if not version:
            raise ValueError(f"Version {version_id} not found")
        
        # Restore workflow state from snapshot
        snapshot = version.snapshot_data
        workflow.state = WorkflowState[snapshot["state"]]
        workflow.current_step = snapshot["current_step"]
        workflow.metadata = snapshot["metadata"]
        
        # Create new version for rollback
        self._create_workflow_version(workflow, user_id, f"Rollback to version {version.version_number}")
        
        self.db.commit()
        return workflow
    
    def create_n8n_workflow(
        self,
        user_id: UUID,
        workflow_id: UUID
    ) -> Dict[str, Any]:
        """
        Manually create n8n workflow for an existing active dashboard
        Useful for re-generating workflows or creating them for dashboards that were active before this feature
        """
        
        workflow = self._get_workflow(workflow_id, user_id)
        
        # Check if dashboard is active
        dashboard = self.db.query(Dashboard).filter(
            Dashboard.id == workflow.dashboard_id
        ).first()
        
        if not dashboard:
            raise ValueError(f"Dashboard {workflow.dashboard_id} not found")
        
        if not dashboard.is_active:
            raise ValueError(f"Dashboard {dashboard.id} is not active. Only active dashboards can have n8n workflows.")
        
        # Get all components, share configs, schedule, and integrations
        components = self.db.query(ThreadComponent).filter(
            ThreadComponent.workflow_id == workflow_id
        ).order_by(ThreadComponent.sequence_order).all()
        
        share_configs = self.db.query(ShareConfiguration).filter(
            ShareConfiguration.workflow_id == workflow_id
        ).all()
        
        schedule_config = self.db.query(ScheduleConfiguration).filter(
            ScheduleConfiguration.workflow_id == workflow_id
        ).first()
        
        integrations = self.db.query(IntegrationConfig).filter(
            IntegrationConfig.workflow_id == workflow_id
        ).all()
        
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
    
    def get_n8n_workflow_status(
        self,
        user_id: UUID,
        workflow_id: UUID
    ) -> Dict[str, Any]:
        """Get the status of n8n workflow for a dashboard"""
        
        workflow = self._get_workflow(workflow_id, user_id)
        
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
    
    def delete_n8n_workflow(
        self,
        user_id: UUID,
        workflow_id: UUID
    ) -> Dict[str, Any]:
        """Delete n8n workflow file for a dashboard"""
        
        workflow = self._get_workflow(workflow_id, user_id)
        
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
    
    def _get_workflow(self, workflow_id: UUID, user_id: UUID) -> DashboardWorkflow:
        """Get workflow with permission check"""
        
        workflow = self.db.query(DashboardWorkflow).filter(
            DashboardWorkflow.id == workflow_id
        ).first()
        
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        if workflow.user_id != user_id and not self._check_user_permission(
            user_id, "dashboard", workflow.dashboard_id, "update"
        ):
            raise PermissionError("User doesn't have access to this workflow")
        
        return workflow
    
    def _update_dashboard_content(self, workflow: DashboardWorkflow, user_id: UUID):
        """Update dashboard content with thread components"""
        
        components = self.db.query(ThreadComponent).filter(
            ThreadComponent.workflow_id == workflow.id
        ).order_by(ThreadComponent.sequence_order).all()
        
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
                "configuration": component.configuration,
                "is_configured": component.is_configured
            }
            content["components"].append(comp_data)
        
        # Update dashboard
        dashboard = self.db.query(Dashboard).filter(
            Dashboard.id == workflow.dashboard_id
        ).first()
        
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
    
    def _create_workflow_version(
        self, 
        workflow: DashboardWorkflow, 
        user_id: UUID,
        note: str = None
    ):
        """Create a version snapshot of the workflow"""
        
        # Get current version number
        max_version = self.db.query(func.max(WorkflowVersion.version_number)).filter(
            WorkflowVersion.workflow_id == workflow.id
        ).scalar() or 0
        
        # Create snapshot
        snapshot = {
            "state": workflow.state.value,
            "current_step": workflow.current_step,
            "metadata": workflow.metadata,
            "note": note,
            "components": [],
            "shares": [],
            "schedule": None,
            "integrations": []
        }
        
        # Add components to snapshot
        components = self.db.query(ThreadComponent).filter(
            ThreadComponent.workflow_id == workflow.id
        ).all()
        
        for comp in components:
            snapshot["components"].append({
                "id": str(comp.id),
                "type": comp.component_type.value,
                "configuration": comp.configuration,
                "is_configured": comp.is_configured
            })
        
        # Create version
        version = WorkflowVersion(
            workflow_id=workflow.id,
            version_number=max_version + 1,
            state=workflow.state,
            snapshot_data=snapshot,
            created_by=user_id
        )
        self.db.add(version)
    
    def _apply_sharing_to_dashboard(
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
            self.dashboard_service.share_dashboard(
                user_id=user_id,
                dashboard_id=workflow.dashboard_id,
                share_with=target_ids,
                permission_level=permission_level
            )
    
    def _calculate_next_run(self, schedule: ScheduleConfiguration) -> Optional[datetime]:
        """Calculate next run time based on schedule configuration"""
        
        now = datetime.utcnow()
        
        if schedule.schedule_type == ScheduleType.ONCE:
            return schedule.start_date if schedule.start_date > now else None
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
    
    def _encrypt_connection_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt sensitive connection configuration"""
        # In production, use proper encryption (e.g., Fernet, KMS)
        # This is a placeholder
        return {
            "encrypted": True,
            "data": json.dumps(config)  # Would be encrypted in production
        }
    
    def _publish_to_integration(
        self,
        dashboard: Dashboard,
        integration: IntegrationConfig,
        workflow: DashboardWorkflow
    ) -> Dict[str, Any]:
        """Publish dashboard to specific integration"""
        
        if integration.integration_type == IntegrationType.TABLEAU:
            return self._publish_to_tableau(dashboard, integration)
        elif integration.integration_type == IntegrationType.POWERBI:
            return self._publish_to_powerbi(dashboard, integration)
        elif integration.integration_type == IntegrationType.SLACK:
            return self._publish_to_slack(dashboard, integration)
        elif integration.integration_type == IntegrationType.EMAIL:
            return self._publish_to_email(dashboard, integration)
        # Add more integrations as needed
        
        return {"status": "not_implemented"}
    
    def _publish_to_tableau(self, dashboard: Dashboard, integration: IntegrationConfig) -> Dict[str, Any]:
        """Publish to Tableau Server/Online"""
        # Placeholder - would use Tableau REST API
        return {
            "tableau_id": str(uuid.uuid4()),
            "url": f"https://tableau.example.com/dashboard/{dashboard.id}",
            "status": "published"
        }
    
    def _publish_to_powerbi(self, dashboard: Dashboard, integration: IntegrationConfig) -> Dict[str, Any]:
        """Publish to Power BI"""
        # Placeholder - would use Power BI REST API
        return {
            "powerbi_id": str(uuid.uuid4()),
            "workspace": "Default",
            "url": f"https://powerbi.example.com/dashboard/{dashboard.id}",
            "status": "published"
        }
    
    def _publish_to_slack(self, dashboard: Dashboard, integration: IntegrationConfig) -> Dict[str, Any]:
        """Publish to Slack"""
        # Placeholder - would use Slack API
        return {
            "channel": integration.mapping_config.get("channel", "#general"),
            "message_ts": str(datetime.utcnow().timestamp()),
            "status": "sent"
        }
    
    def _publish_to_email(self, dashboard: Dashboard, integration: IntegrationConfig) -> Dict[str, Any]:
        """Send dashboard via email"""
        # Placeholder - would use email service
        return {
            "recipients": integration.mapping_config.get("recipients", []),
            "sent_at": datetime.utcnow().isoformat(),
            "status": "sent"
        }
    
    def _send_email_invitation(self, email: str, workflow: DashboardWorkflow, user_id: UUID):
        """Send email invitation for dashboard sharing"""
        # Placeholder - would use email service
        pass
    
    def _evaluate_alert_condition(
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
        
        if alert_type == "threshold":
            return self._evaluate_threshold_condition(component, data)
        elif alert_type == "anomaly":
            return self._evaluate_anomaly_condition(component, data)
        elif alert_type == "trend":
            return self._evaluate_trend_condition(component, data)
        elif alert_type == "comparison":
            return self._evaluate_comparison_condition(component, data)
        elif alert_type == "schedule":
            return self._evaluate_schedule_condition(component, data)
        else:
            return {"triggered": False, "reason": f"Unknown alert type: {alert_type}"}
    
    def _evaluate_threshold_condition(
        self,
        component: ThreadComponent,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate threshold-based alert condition"""
        
        alert_config = component.alert_config or {}
        condition_config = alert_config.get("condition_config", {})
        
        # Extract threshold parameters
        field = condition_config.get("field")
        operator = condition_config.get("operator", ">")
        threshold_value = condition_config.get("threshold_value")
        
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
    
    def _evaluate_anomaly_condition(
        self,
        component: ThreadComponent,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate anomaly detection alert condition"""
        
        alert_config = component.alert_config or {}
        condition_config = alert_config.get("condition_config", {})
        anomaly_config = alert_config.get("anomaly_config", {})
        
        # Extract anomaly parameters
        field = condition_config.get("field")
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
    
    def _evaluate_trend_condition(
        self,
        component: ThreadComponent,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate trend-based alert condition"""
        
        alert_config = component.alert_config or {}
        condition_config = alert_config.get("condition_config", {})
        trend_config = alert_config.get("trend_config", {})
        
        # Extract trend parameters
        field = condition_config.get("field")
        trend_direction = condition_config.get("trend_direction", "increasing")
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
    
    def _evaluate_comparison_condition(
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
    
    def _evaluate_schedule_condition(
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
    
    def _execute_alert_notifications(
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
                    result = self._send_alert_email(component, data)
                elif channel == "slack":
                    result = self._send_alert_slack(component, data)
                elif channel == "webhook":
                    result = self._send_alert_webhook(component, data)
                else:
                    result = {"success": False, "error": f"Unknown channel: {channel}"}
                
                results[channel] = result
            except Exception as e:
                results[channel] = {"success": False, "error": str(e)}
        
        return results
    
    def _send_alert_email(self, component: ThreadComponent, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send alert notification via email"""
        # Placeholder - would use email service
        return {
            "success": True,
            "channel": "email",
            "message": f"Alert '{component.question}' triggered"
        }
    
    def _send_alert_slack(self, component: ThreadComponent, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send alert notification via Slack"""
        # Placeholder - would use Slack API
        return {
            "success": True,
            "channel": "slack",
            "message": f"Alert '{component.question}' triggered"
        }
    
    def _send_alert_webhook(self, component: ThreadComponent, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send alert notification via webhook"""
        # Placeholder - would use HTTP client
        return {
            "success": True,
            "channel": "webhook",
            "message": f"Alert '{component.question}' triggered"
        }
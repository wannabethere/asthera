from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
import uuid
import json
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, func, select

def utc_now():
    """Get current UTC datetime for SQLAlchemy defaults"""
    return datetime.now(timezone.utc)

from app.services.baseservice import BaseService, SharingPermission
from app.services.reportservice import ReportService
from app.models.workflowmodels import (
    WorkflowState, ComponentType, ShareType, ScheduleType, IntegrationType,
    ThreadComponentCreate, ShareConfigCreate, ScheduleConfigCreate,
    IntegrationConfigCreate, AlertType, AlertSeverity, AlertStatus,
    AlertThreadComponentCreate, AlertThreadComponentUpdate
)
from app.models.dbmodels import Report, ReportVersion
from app.models.schema import ReportCreate, ReportUpdate

# Import ReportWorkflow from models instead of defining it here
from app.models.workflowmodels import ReportWorkflow

class ReportWorkflowService(BaseService):
    """Service for managing report creation workflows"""
    
    def __init__(self, db: AsyncSession, chroma_client=None):
        super().__init__(db, chroma_client)
        self.collection_name = "report_workflows"
        self.report_service = ReportService(db, chroma_client)
    
    async def create_report_workflow(
        self,
        user_id: UUID,
        report_name: str,
        report_description: str,
        report_template: str = "standard",
        project_id: Optional[UUID] = None,
        workspace_id: Optional[UUID] = None,
        workflow_id: Optional[UUID] = None
    ) -> Tuple[ReportWorkflow, Report]:
        """Create initial report and workflow"""
        
        # Create placeholder report
        report_data = ReportCreate(
            name=report_name,
            description=report_description,
            reportType="Custom",
            is_active=False,
            content={"status": "draft", "sections": []}
        )
        
        report = await self.report_service.create_report(
            user_id=user_id,
            report_data=report_data,
            workflow_id=workflow_id,
            project_id=project_id,
            workspace_id=workspace_id,
            sharing_permission=SharingPermission.PRIVATE
        )
        
        # Create report workflow
        workflow = ReportWorkflow(
            report_id=report.id,
            user_id=user_id,
            state=WorkflowState.DRAFT,
            report_template=report_template,
            current_step=1,
            metadata={
                "report_name": report_name,
                "template": report_template,
                "project_id": str(project_id) if project_id else None,
                "workspace_id": str(workspace_id) if workspace_id else None,
                "workflow_id": str(workflow_id) if workflow_id else None
            }
        )
        
        self.db.add(workflow)
        await self.db.commit()
        
        return workflow, report
    
    async def add_report_section(
        self,
        user_id: UUID,
        workflow_id: UUID,
        section_type: str,
        section_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add a section to the report"""
        
        workflow = await self._get_report_workflow(workflow_id, user_id)
        
        if workflow.state not in [WorkflowState.DRAFT, WorkflowState.CONFIGURING]:
            raise ValueError(f"Cannot add sections in {workflow.state} state")
        
        # Add section
        section = {
            "id": str(uuid.uuid4()),
            "type": section_type,
            "config": section_config,
            "order": len(workflow.sections) + 1,
            "created_at": utc_now().isoformat()
        }
        
        sections = workflow.sections or []
        sections.append(section)
        workflow.sections = sections
        
        # Update state
        if workflow.state == WorkflowState.DRAFT:
            workflow.state = WorkflowState.CONFIGURING
            workflow.current_step = 2
        
        # Update report content
        await self._update_report_content(workflow)
        
        await self.db.commit()
        return section
    
    async def configure_data_sources(
        self,
        user_id: UUID,
        workflow_id: UUID,
        data_sources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Configure data sources for the report"""
        
        workflow = await self._get_report_workflow(workflow_id, user_id)
        
        if workflow.state not in [WorkflowState.CONFIGURING, WorkflowState.CONFIGURED]:
            raise ValueError(f"Cannot configure data sources in {workflow.state} state")
        
        # Validate and add data sources
        validated_sources = []
        for source in data_sources:
            validated_source = {
                "id": str(uuid.uuid4()),
                "type": source.get("type", "database"),
                "connection": source.get("connection", {}),
                "query": source.get("query", ""),
                "refresh_interval": source.get("refresh_interval", "daily"),
                "filters": source.get("filters", [])
            }
            validated_sources.append(validated_source)
        
        workflow.data_sources = validated_sources
        
        # Update state if all sections configured
        if workflow.sections and len(workflow.sections) > 0:
            workflow.state = WorkflowState.CONFIGURED
            workflow.current_step = 3
        
        await self.db.commit()
        return validated_sources
    
    async def configure_report_formatting(
        self,
        user_id: UUID,
        workflow_id: UUID,
        formatting: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Configure report formatting options"""
        
        workflow = await self._get_report_workflow(workflow_id, user_id)
        
        # Formatting options
        workflow.formatting = {
            "theme": formatting.get("theme", "default"),
            "font_family": formatting.get("font_family", "Arial"),
            "font_size": formatting.get("font_size", 11),
            "colors": formatting.get("colors", {}),
            "page_layout": formatting.get("page_layout", "portrait"),
            "margins": formatting.get("margins", {"top": 1, "bottom": 1, "left": 1, "right": 1}),
            "header": formatting.get("header", {}),
            "footer": formatting.get("footer", {}),
            "table_styles": formatting.get("table_styles", {}),
            "chart_styles": formatting.get("chart_styles", {})
        }
        
        # Update report
        await self._update_report_content(workflow)
        
        await self.db.commit()
        return workflow.formatting
    
    async def generate_report_preview(
        self,
        user_id: UUID,
        workflow_id: UUID,
        format_type: str = "html"
    ) -> Dict[str, Any]:
        """Generate a preview of the report"""
        
        workflow = await self._get_report_workflow(workflow_id, user_id)
        
        if workflow.state not in [WorkflowState.CONFIGURED, WorkflowState.SHARED, 
                                  WorkflowState.SCHEDULED, WorkflowState.PUBLISHING]:
            raise ValueError(f"Cannot preview report in {workflow.state} state")
        
        # Get report
        stmt = select(Report).where(Report.id == workflow.report_id)
        result = await self.db.execute(stmt)
        report = result.scalar_one_or_none()
        
        # Generate preview based on format
        if format_type == "html":
            preview = await self._generate_html_preview(report, workflow)
        elif format_type == "pdf":
            preview = await self._generate_pdf_preview(report, workflow)
        else:
            preview = {"error": "Unsupported format"}
        
        return {
            "format": format_type,
            "preview": preview,
            "generated_at": utc_now().isoformat()
        }
    
    async def schedule_report_generation(
        self,
        user_id: UUID,
        workflow_id: UUID,
        schedule_config: ScheduleConfigCreate,
        recipients: List[str] = None
    ) -> Dict[str, Any]:
        """Schedule automatic report generation and distribution"""
        
        workflow = await self._get_report_workflow(workflow_id, user_id)
        
        # Similar to dashboard scheduling but with report-specific options
        schedule_data = {
            "schedule_type": schedule_config.schedule_type.value,
            "cron_expression": schedule_config.cron_expression,
            "timezone": schedule_config.timezone,
            "recipients": recipients or [],
            "format": schedule_config.configuration.get("format", "pdf"),
            "delivery_method": schedule_config.configuration.get("delivery_method", "email")
        }
        
        workflow.metadata["schedule"] = schedule_data
        workflow.state = WorkflowState.SCHEDULED
        workflow.current_step = 6
        
        await self.db.commit()
        
        return schedule_data
    
    async def publish_report(
        self,
        user_id: UUID,
        workflow_id: UUID,
        publish_options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Publish the report to configured destinations"""
        
        workflow = await self._get_report_workflow(workflow_id, user_id)
        
        if workflow.state not in [WorkflowState.SCHEDULED, WorkflowState.PUBLISHING]:
            raise ValueError(f"Cannot publish report in {workflow.state} state")
        
        workflow.state = WorkflowState.PUBLISHING
        
        # Get report
        stmt = select(Report).where(Report.id == workflow.report_id)
        result = await self.db.execute(stmt)
        report = result.scalar_one_or_none()
        
        publish_results = {}
        
        # Generate final report in requested formats
        formats = publish_options.get("formats", ["pdf", "html"])
        for format_type in formats:
            if format_type == "pdf":
                result = await self._generate_pdf_report(report, workflow)
            elif format_type == "html":
                result = await self._generate_html_report(report, workflow)
            elif format_type == "excel":
                result = await self._generate_excel_report(report, workflow)
            else:
                result = {"error": "Unsupported format"}
            
            publish_results[format_type] = result
        
        # Distribute to configured channels
        if publish_options.get("send_email"):
            await self._send_report_email(report, workflow, publish_results)
        
        if publish_options.get("upload_to_sharepoint"):
            await self._upload_to_sharepoint(report, workflow, publish_results)
        
        if publish_options.get("save_to_drive"):
            await self._save_to_google_drive(report, workflow, publish_results)
        
        # Update report status
        report.is_active = True
        report.updated_at = utc_now()
        
        # Update workflow
        workflow.state = WorkflowState.ACTIVE
        workflow.completed_at = utc_now()
        workflow.current_step = 8
        
        await self.db.commit()
        
        return {
            "report_id": str(report.id),
            "workflow_id": str(workflow.id),
            "publish_results": publish_results,
            "completed_at": workflow.completed_at.isoformat()
        }
    
    async def clone_report_workflow(
        self,
        user_id: UUID,
        source_workflow_id: UUID,
        new_name: str
    ) -> Tuple[ReportWorkflow, Report]:
        """Clone an existing report workflow"""
        
        source_workflow = await self._get_report_workflow(source_workflow_id, user_id)
        
        # Clone the report
        stmt = select(Report).where(Report.id == source_workflow.report_id)
        result = await self.db.execute(stmt)
        source_report = result.scalar_one_or_none()
        
        # Create new report
        report_data = ReportCreate(
            name=new_name,
            description=f"Cloned from: {source_report.description}",
            reportType=source_report.reportType,
            is_active=False,
            content=source_report.content
        )
        
        new_report = await self.report_service.create_report(
            user_id=user_id,
            report_data=report_data
        )
        
        # Clone workflow
        new_workflow = ReportWorkflow(
            report_id=new_report.id,
            user_id=user_id,
            state=WorkflowState.DRAFT,
            report_template=source_workflow.report_template,
            data_sources=source_workflow.data_sources,
            sections=source_workflow.sections,
            formatting=source_workflow.formatting,
            metadata=source_workflow.metadata.copy()
        )
        new_workflow.metadata["cloned_from"] = str(source_workflow_id)
        
        self.db.add(new_workflow)
        await self.db.commit()
        
        return new_workflow, new_report
    
    # ==================== Alert Thread Component Management ====================
    
    async def add_alert_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        alert_data: AlertThreadComponentCreate
    ) -> Dict[str, Any]:
        """
        Add an alert as a thread message component to the report workflow
        """
        
        workflow = await self._get_report_workflow(workflow_id, user_id)
        
        # Validate state - can add alerts in most states
        if workflow.state in [WorkflowState.ARCHIVED, WorkflowState.ERROR]:
            raise ValueError(f"Cannot add alerts in {workflow.state} state")
        
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
        
        # Add alert to workflow metadata
        if "alerts" not in workflow.metadata:
            workflow.metadata["alerts"] = []
        
        alert_component = {
            "id": str(uuid.uuid4()),
            "question": alert_data.question,
            "description": alert_data.description,
            "alert_config": alert_config,
            "alert_status": AlertStatus.ACTIVE.value,
            "trigger_count": 0,
            "last_triggered": None,
            "configuration": alert_data.configuration,
            "created_at": utc_now().isoformat(),
            "created_by": str(user_id)
        }
        
        workflow.metadata["alerts"].append(alert_component)
        
        # Update workflow state if this is the first alert
        if workflow.state == WorkflowState.CONFIGURED and len(workflow.metadata["alerts"]) == 1:
            workflow.state = WorkflowState.CONFIGURING
            workflow.current_step = 2
        
        # Update report content
        await self._update_report_content(workflow)
        
        await self.db.commit()
        
        return {
            "success": True,
            "alert_id": alert_component["id"],
            "alert_name": alert_component["question"],
            "message": f"Alert '{alert_component['question']}' added successfully"
        }
    
    async def update_alert_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        alert_id: str,
        update_data: AlertThreadComponentUpdate
    ) -> Dict[str, Any]:
        """
        Update an existing alert thread component
        """
        
        workflow = await self._get_report_workflow(workflow_id, user_id)
        
        # Find the alert component
        alerts = workflow.metadata.get("alerts", [])
        alert_component = None
        alert_index = None
        
        for i, alert in enumerate(alerts):
            if alert["id"] == alert_id:
                alert_component = alert
                alert_index = i
                break
        
        if not alert_component:
            raise ValueError(f"Alert component {alert_id} not found")
        
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
            current_alert_config = alert_component["alert_config"] or {}
            
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
            
            alert_component["alert_config"] = current_alert_config
        
        # Update other fields
        if update_data.question:
            alert_component["question"] = update_data.question
        if update_data.description:
            alert_component["description"] = update_data.description
        if update_data.severity:
            # Update severity in alert config
            current_alert_config = alert_component["alert_config"] or {}
            current_alert_config["severity"] = update_data.severity.value
            alert_component["alert_config"] = current_alert_config
        if update_data.alert_status:
            alert_component["alert_status"] = update_data.alert_status.value
        if update_data.configuration:
            alert_component["configuration"] = update_data.configuration
        
        alert_component["updated_at"] = utc_now().isoformat()
        
        # Update the alert in the list
        alerts[alert_index] = alert_component
        workflow.metadata["alerts"] = alerts
        
        # Update report content
        await self._update_report_content(workflow)
        
        await self.db.commit()
        
        return {
            "success": True,
            "alert_id": alert_id,
            "alert_name": alert_component["question"],
            "message": f"Alert '{alert_component['question']}' updated successfully"
        }
    
    async def get_alert_thread_components(
        self,
        user_id: UUID,
        workflow_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Get all alert thread components for a report workflow
        """
        
        workflow = await self._get_report_workflow(workflow_id, user_id)
        
        return workflow.metadata.get("alerts", [])
    
    async def delete_alert_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        alert_id: str
    ) -> Dict[str, Any]:
        """
        Delete an alert thread component
        """
        
        workflow = await self._get_report_workflow(workflow_id, user_id)
        
        # Find and remove the alert component
        alerts = workflow.metadata.get("alerts", [])
        alert_component = None
        
        for alert in alerts:
            if alert["id"] == alert_id:
                alert_component = alert
                break
        
        if not alert_component:
            raise ValueError(f"Alert component {alert_id} not found")
        
        # Remove the alert
        alerts = [alert for alert in alerts if alert["id"] != alert_id]
        workflow.metadata["alerts"] = alerts
        
        # Update report content
        await self._update_report_content(workflow)
        
        await self.db.commit()
        
        return {
            "success": True,
            "alert_id": alert_id,
            "alert_name": alert_component["question"],
            "message": f"Alert '{alert_component['question']}' deleted successfully"
        }
    
    async def test_alert_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        alert_id: str,
        test_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Test an alert thread component with sample data
        """
        
        workflow = await self._get_report_workflow(workflow_id, user_id)
        
        # Find the alert component
        alerts = workflow.metadata.get("alerts", [])
        alert_component = None
        
        for alert in alerts:
            if alert["id"] == alert_id:
                alert_component = alert
                break
        
        if not alert_component:
            raise ValueError(f"Alert component {alert_id} not found")
        
        # Test the alert condition
        try:
            test_result = await self._evaluate_alert_condition(alert_component, test_data or {})
            
            return {
                "success": True,
                "alert_id": alert_id,
                "alert_name": alert_component["question"],
                "test_result": test_result,
                "message": "Alert condition evaluated successfully"
            }
        except Exception as e:
            return {
                "success": False,
                "alert_id": alert_id,
                "alert_name": alert_component["question"],
                "error": str(e),
                "message": "Failed to evaluate alert condition"
            }
    
    async def trigger_alert_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        alert_id: str,
        trigger_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Manually trigger an alert thread component for testing
        """
        
        workflow = await self._get_report_workflow(workflow_id, user_id)
        
        # Find the alert component
        alerts = workflow.metadata.get("alerts", [])
        alert_component = None
        alert_index = None
        
        for i, alert in enumerate(alerts):
            if alert["id"] == alert_id:
                alert_component = alert
                alert_index = i
                break
        
        if not alert_component:
            raise ValueError(f"Alert component {alert_id} not found")
        
        if alert_component["alert_status"] != AlertStatus.ACTIVE.value:
            raise ValueError(f"Alert component '{alert_component['question']}' is not active")
        
        # Check cooldown period
        if alert_component["last_triggered"] and alert_component["alert_config"]:
            cooldown_period = alert_component["alert_config"].get("cooldown_period", 300)
            last_triggered = datetime.fromisoformat(alert_component["last_triggered"])
            time_since_last = (utc_now() - last_triggered).total_seconds()
            if time_since_last < cooldown_period:
                remaining = cooldown_period - time_since_last
                raise ValueError(f"Alert is in cooldown period. Try again in {int(remaining)} seconds")
        
        # Trigger the alert
        try:
            trigger_result = await self._execute_alert_notifications(alert_component, trigger_data or {})
            
            # Update alert status
            alert_component["last_triggered"] = utc_now().isoformat()
            alert_component["trigger_count"] += 1
            alert_component["alert_status"] = AlertStatus.TRIGGERED.value
            
            # Update the alert in the list
            alerts[alert_index] = alert_component
            workflow.metadata["alerts"] = alerts
            
            await self.db.commit()
            
            return {
                "success": True,
                "alert_id": alert_id,
                "alert_name": alert_component["question"],
                "trigger_result": trigger_result,
                "message": "Alert triggered successfully"
            }
        except Exception as e:
            return {
                "success": False,
                "alert_id": alert_id,
                "alert_name": alert_component["question"],
                "error": str(e),
                "message": "Failed to trigger alert"
            }
    
    # Private helper methods
    
    async def _get_report_workflow(self, workflow_id: UUID, user_id: UUID) -> ReportWorkflow:
        """Get report workflow with permission check"""
        
        stmt = select(ReportWorkflow).where(ReportWorkflow.id == workflow_id)
        result = await self.db.execute(stmt)
        workflow = result.scalar_one_or_none()
        
        if not workflow:
            raise ValueError(f"Report workflow {workflow_id} not found")
        
        if workflow.user_id != user_id and not await self._check_user_permission(
            user_id, "report", workflow.report_id, "update"
        ):
            raise PermissionError("User doesn't have access to this workflow")
        
        return workflow
    
    async def _update_report_content(self, workflow: ReportWorkflow):
        """Update report content based on workflow configuration"""
        
        stmt = select(Report).where(Report.id == workflow.report_id)
        result = await self.db.execute(stmt)
        report = result.scalar_one_or_none()
        
        content = {
            "status": workflow.state.value,
            "template": workflow.report_template,
            "sections": workflow.sections or [],
            "data_sources": workflow.data_sources or [],
            "formatting": workflow.formatting or {},
            "metadata": {
                "updated_at": utc_now().isoformat(),
                "version": report.version
            }
        }
        
        report.content = content
        report.updated_at = utc_now()
        
        # Create version
        new_version = str(float(report.version) + 0.1)
        version = ReportVersion(
            report_id=report.id,
            version=new_version,
            content=content
        )
        self.db.add(version)
        report.version = new_version
    
    async def _generate_html_preview(self, report: Report, workflow: ReportWorkflow) -> str:
        """Generate HTML preview of the report"""
        
        html = f"""
        <html>
        <head>
            <title>{report.name}</title>
            <style>
                body {{ font-family: {workflow.formatting.get('font_family', 'Arial')}; }}
                h1 {{ color: #333; }}
                .section {{ margin: 20px 0; padding: 10px; border: 1px solid #ddd; }}
            </style>
        </head>
        <body>
            <h1>{report.name}</h1>
            <p>{report.description}</p>
        """
        
        for section in workflow.sections or []:
            html += f"""
            <div class="section">
                <h2>Section {section['order']}: {section['type']}</h2>
                <pre>{json.dumps(section['config'], indent=2)}</pre>
            </div>
            """
        
        html += "</body></html>"
        return html
    
    async def _generate_pdf_preview(self, report: Report, workflow: ReportWorkflow) -> Dict[str, Any]:
        """Generate PDF preview metadata"""
        # In production, would use libraries like ReportLab or WeasyPrint
        return {
            "pages": len(workflow.sections or []) + 1,
            "size": "A4",
            "orientation": workflow.formatting.get("page_layout", "portrait")
        }
    
    async def _generate_pdf_report(self, report: Report, workflow: ReportWorkflow) -> Dict[str, Any]:
        """Generate full PDF report"""
        # Placeholder - would use PDF generation library
        return {
            "file_path": f"/reports/{report.id}.pdf",
            "size_bytes": 1024000,
            "pages": len(workflow.sections or []) + 2
        }
    
    async def _generate_html_report(self, report: Report, workflow: ReportWorkflow) -> Dict[str, Any]:
        """Generate full HTML report"""
        html_content = await self._generate_html_preview(report, workflow)
        return {
            "content": html_content,
            "size_bytes": len(html_content)
        }
    
    async def _generate_excel_report(self, report: Report, workflow: ReportWorkflow) -> Dict[str, Any]:
        """Generate Excel report"""
        # Placeholder - would use openpyxl or xlsxwriter
        return {
            "file_path": f"/reports/{report.id}.xlsx",
            "sheets": len(workflow.sections or []),
            "size_bytes": 512000
        }
    
    async def _send_report_email(self, report: Report, workflow: ReportWorkflow, attachments: Dict[str, Any]):
        """Send report via email"""
        # Placeholder - would use email service
        pass
    
    async def _upload_to_sharepoint(self, report: Report, workflow: ReportWorkflow, files: Dict[str, Any]):
        """Upload report to SharePoint"""
        # Placeholder - would use SharePoint API
        pass
    
    async def _save_to_google_drive(self, report: Report, workflow: ReportWorkflow, files: Dict[str, Any]):
        """Save report to Google Drive"""
        # Placeholder - would use Google Drive API
        pass
    
    # ==================== Alert Helper Methods ====================
    
    async def _evaluate_alert_condition(
        self,
        alert_component: Dict[str, Any],
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate alert condition based on component configuration and data
        """
        
        alert_config = alert_component.get("alert_config", {})
        alert_type = alert_config.get("alert_type")
        condition_config = alert_config.get("condition_config", {})
        
        if alert_type == "threshold":
            return await self._evaluate_threshold_condition(alert_component, data)
        elif alert_type == "anomaly":
            return await self._evaluate_anomaly_condition(alert_component, data)
        elif alert_type == "trend":
            return await self._evaluate_trend_condition(alert_component, data)
        elif alert_type == "comparison":
            return await self._evaluate_comparison_condition(alert_component, data)
        elif alert_type == "schedule":
            return await self._evaluate_schedule_condition(alert_component, data)
        else:
            return {"triggered": False, "reason": f"Unknown alert type: {alert_type}"}
    
    async def _evaluate_threshold_condition(
        self,
        alert_component: Dict[str, Any],
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate threshold-based alert condition"""
        
        alert_config = alert_component.get("alert_config", {})
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
    
    async def _evaluate_anomaly_condition(
        self,
        alert_component: Dict[str, Any],
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate anomaly detection alert condition"""
        
        alert_config = alert_component.get("alert_config", {})
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
    
    async def _evaluate_trend_condition(
        self,
        alert_component: Dict[str, Any],
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate trend-based alert condition"""
        
        alert_config = alert_component.get("alert_config", {})
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
    
    async def _evaluate_comparison_condition(
        self,
        alert_component: Dict[str, Any],
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate comparison-based alert condition"""
        
        alert_config = alert_component.get("alert_config", {})
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
        alert_component: Dict[str, Any],
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate schedule-based alert condition"""
        
        alert_config = alert_component.get("alert_config", {})
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
        alert_component: Dict[str, Any],
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute alert notifications through configured channels
        """
        
        alert_config = alert_component.get("alert_config", {})
        notification_channels = alert_config.get("notification_channels", [])
        results = {}
        
        for channel in notification_channels:
            try:
                if channel == "email":
                    result = await self._send_alert_email(alert_component, data)
                elif channel == "slack":
                    result = await self._send_alert_slack(alert_component, data)
                elif channel == "webhook":
                    result = await self._send_alert_webhook(alert_component, data)
                else:
                    result = {"success": False, "error": f"Unknown channel: {channel}"}
                
                results[channel] = result
            except Exception as e:
                results[channel] = {"success": False, "error": str(e)}
        
        return results
    
    async def _send_alert_email(self, alert_component: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Send alert notification via email"""
        # Placeholder - would use email service
        return {
            "success": True,
            "channel": "email",
            "message": f"Alert '{alert_component['question']}' triggered"
        }
    
    async def _send_alert_slack(self, alert_component: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Send alert notification via Slack"""
        # Placeholder - would use Slack API
        return {
            "success": True,
            "channel": "slack",
            "message": f"Alert '{alert_component['question']}' triggered"
        }
    
    async def _send_alert_webhook(self, alert_component: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Send alert notification via webhook"""
        # Placeholder - would use HTTP client
        return {
            "success": True,
            "channel": "webhook",
            "message": f"Alert '{alert_component['question']}' triggered"
        }
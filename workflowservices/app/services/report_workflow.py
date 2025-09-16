from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
import uuid
import json
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, func, select
import traceback

def utc_now():
    """Get current UTC datetime for SQLAlchemy defaults"""
    return datetime.now()

from app.services.baseservice import BaseService
from app.models.workflowmodels import SharingPermission
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

    async def share_report(self, user_id: UUID, report_id: UUID, share_with: List[UUID], permission_level: SharingPermission=SharingPermission.USER):
        try:
            return await self.report_service.share_report(user_id, report_id, share_with, permission_level)
        except Exception as e:
            print("======== Error in share_report============")
            traceback.print_exc()
            print("===============Error ended heree =================")
            await self.db.rollback()
            raise e

    async def share_report_workflow(
        self,
        user_id: UUID,
        workflow_id: UUID,
        share_with: List[UUID],
        permission_level: SharingPermission = SharingPermission.USER
    ) -> Dict[str, Any]:
        """Share report through workflow with state validation"""
        try:
            workflow = await self._get_report_workflow(workflow_id, user_id)
            
            # Validate state - allow sharing in more states including ACTIVE
            if workflow.state not in [WorkflowState.CONFIGURED, WorkflowState.SHARING, WorkflowState.CONFIGURING, WorkflowState.ACTIVE, WorkflowState.PUBLISHED]:
                raise ValueError(f"Cannot share report in {workflow.state} state")
            
            # Share the report
            result = await self.report_service.share_report(
                user_id=user_id,
                report_id=workflow.report_id,
                share_with=share_with,
                permission_level=permission_level
            )
            
            # Update workflow state if needed
            if workflow.state == WorkflowState.CONFIGURED:
                workflow.state = WorkflowState.SHARING
                workflow.current_step = 4
            elif workflow.state not in [WorkflowState.ACTIVE, WorkflowState.PUBLISHED]:
                workflow.state = WorkflowState.SHARED
                workflow.current_step = 5
            
            # Create version
            await self._create_workflow_version(workflow, user_id, note="Report shared")
            
            await self.db.commit()
            
            return {
                "success": True,
                "shared_with": len(share_with),
                "permission_level": permission_level.value,
                "workflow_state": workflow.state.value
            }
        except Exception as e:
            print("======== Error in share_report_workflow============")
            traceback.print_exc()
            print("===============Error ended heree =================")
            await self.db.rollback()
            raise e

    async def add_report_section(
        self,
        user_id: UUID,
        workflow_id: UUID,
        section_type: str,
        section_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add a section to the report"""
        try:
            workflow = await self._get_report_workflow(workflow_id, user_id)

            if workflow.state not in [WorkflowState.DRAFT, WorkflowState.CONFIGURING, WorkflowState.ACTIVE, WorkflowState.PUBLISHED]:
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
        except Exception as e:
            print("======== Error in add_section============")
            traceback.print_exc()
            print("===============Error ended heree =================")
            await self.db.rollback()
            raise e

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

    async def schedule_report_generation(
        self,
        user_id: UUID,
        workflow_id: UUID,
        schedule_config: ScheduleConfigCreate,
        recipients: List[str] = None
    ) -> Dict[str, Any]:
        """Schedule automatic report generation and distribution"""

        workflow = await self._get_report_workflow(workflow_id, user_id)
        
        # Validate state - allow scheduling in more states including ACTIVE
        if workflow.state not in [WorkflowState.CONFIGURED, WorkflowState.SHARED, WorkflowState.SCHEDULED, WorkflowState.ACTIVE, WorkflowState.PUBLISHED]:
            raise ValueError(f"Cannot schedule report in {workflow.state} state")

        # Convert datetime to GMT/UTC for consistent storage using utility function
        start_date_gmt = self._convert_to_utc(schedule_config.start_date, schedule_config.timezone)
        end_date_gmt = self._convert_to_utc(schedule_config.end_date, schedule_config.timezone)

        # Similar to dashboard scheduling but with report-specific options
        schedule_data = {
            "schedule_type": schedule_config.schedule_type.value,
            "cron_expression": schedule_config.cron_expression,
            "timezone": "UTC",  # Store as UTC
            "start_date": start_date_gmt.isoformat() if start_date_gmt else None,
            "end_date": end_date_gmt.isoformat() if end_date_gmt else None,
            "original_timezone": schedule_config.timezone,  # Keep original timezone for reference
            "recipients": recipients or [],
            "format": schedule_config.configuration.get("format", "pdf"),
            "delivery_method": schedule_config.configuration.get("delivery_method", "email")
        }

        workflow.workflow_metadata["schedule"] = schedule_data
        
        # Update state - only transition to SCHEDULED if not already ACTIVE/PUBLISHED
        if workflow.state not in [WorkflowState.ACTIVE, WorkflowState.PUBLISHED]:
            workflow.state = WorkflowState.SCHEDULED
            workflow.current_step = 6

        await self.db.commit()

        return schedule_data

    async def get_report_by_id(
        self,
        user_id: UUID,
        report_id: UUID,
        workflow_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get a specific report by ID with all details including sharing, scheduling, and integrations"""
        
        # Get report
        stmt = select(Report).where(Report.id == report_id)
        result = await self.db.execute(stmt)
        report = result.scalar_one_or_none()
        
        if not report:
            raise ValueError(f"Report {report_id} not found")
        
        # Get workflow if not provided
        if not workflow_id:
            stmt = select(ReportWorkflow).where(ReportWorkflow.report_id == report_id)
            result = await self.db.execute(stmt)
            workflow = result.scalar_one_or_none()
        else:
            workflow = await self._get_report_workflow(workflow_id, user_id)
        
        if not workflow:
            raise ValueError(f"Workflow not found for report {report_id}")
        
        # Get sharing information from report service
        sharing_info = await self.report_service.get_report_sharing_info(user_id, report_id)
        
        # Get schedule configuration from workflow metadata
        schedule_config = None
        if workflow.workflow_metadata and "schedule" in workflow.workflow_metadata:
            schedule_data = workflow.workflow_metadata["schedule"]
            schedule_config = {
                "schedule_type": schedule_data.get("schedule_type"),
                "cron_expression": schedule_data.get("cron_expression"),
                "timezone": schedule_data.get("timezone"),
                "start_date": schedule_data.get("start_date"),
                "end_date": schedule_data.get("end_date"),
                "original_timezone": schedule_data.get("original_timezone"),
                "recipients": schedule_data.get("recipients", []),
                "format": schedule_data.get("format"),
                "delivery_method": schedule_data.get("delivery_method")
            }
        
        # Get sections
        sections = workflow.sections or []
        
        # Get data sources
        data_sources = workflow.data_sources or []
        
        # Get formatting
        formatting = workflow.formatting or {}
        
        # Get alert components
        alert_components = []
        if workflow.workflow_metadata and "alerts" in workflow.workflow_metadata:
            for alert in workflow.workflow_metadata["alerts"]:
                alert_components.append({
                    "id": alert["id"],
                    "question": alert["question"],
                    "description": alert["description"],
                    "alert_type": alert["alert_config"]["alert_type"],
                    "severity": alert["alert_config"]["severity"],
                    "alert_status": alert["alert_status"],
                    "trigger_count": alert["trigger_count"],
                    "last_triggered": alert["last_triggered"],
                    "created_at": alert["created_at"]
                })
        
        # Get draft changes
        draft_changes = workflow.workflow_metadata.get("draft_changes", {})
        
        return {
            "report": {
                "id": str(report.id),
                "name": report.name,
                "description": report.description,
                "content": report.content,
                "metadata": report.metadata,
                "version": report.version,
                "is_active": report.is_active,
                "created_at": report.created_at.isoformat(),
                "updated_at": report.updated_at.isoformat()
            },
            "workflow": {
                "id": str(workflow.id),
                "state": workflow.state.value,
                "current_step": workflow.current_step,
                "report_template": workflow.report_template,
                "created_at": workflow.created_at.isoformat(),
                "updated_at": workflow.updated_at.isoformat(),
                "completed_at": workflow.completed_at.isoformat() if workflow.completed_at else None
            },
            "sharing": {
                "shared_with": sharing_info.get("shared_with", []),
                "permission_level": sharing_info.get("permission_level"),
                "total_shared": len(sharing_info.get("shared_with", []))
            },
            "scheduling": {
                "configuration": schedule_config,
                "has_schedule": schedule_config is not None
            },
            "sections": {
                "list": sections,
                "total_sections": len(sections)
            },
            "data_sources": {
                "list": data_sources,
                "total_sources": len(data_sources)
            },
            "formatting": formatting,
            "components": {
                "alert_components": alert_components,
                "total_components": len(alert_components)
            },
            "draft_changes": {
                "has_draft_changes": draft_changes.get("has_draft_changes", False),
                "last_edited_at": draft_changes.get("last_edited_at"),
                "edited_by": draft_changes.get("edited_by"),
                "last_published_at": draft_changes.get("last_published_at"),
                "published_by": draft_changes.get("published_by")
            }
        }

    async def publish_report(
        self,
        user_id: UUID,
        workflow_id: UUID,
        publish_options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Publish the report to configured destinations - now handles draft changes"""

        workflow = await self._get_report_workflow(workflow_id, user_id)

        if workflow.state not in [WorkflowState.SCHEDULED, WorkflowState.PUBLISHING, WorkflowState.PUBLISHED, WorkflowState.ACTIVE]:
            raise ValueError(f"Cannot publish report in {workflow.state} state")

        workflow.state = WorkflowState.PUBLISHING

        # Get report
        stmt = select(Report).where(Report.id == workflow.report_id)
        result = await self.db.execute(stmt)
        report = result.scalar_one_or_none()

        # Check if there are draft changes to apply
        draft_changes = workflow.workflow_metadata.get("draft_changes", {})
        has_draft_changes = draft_changes.get("has_draft_changes", False)
        print("has_draft_changes: ", has_draft_changes)

        if has_draft_changes:
            # Apply draft changes to the published report
            if "name" in draft_changes:
                report.name = draft_changes["name"]
            if "description" in draft_changes:
                report.description = draft_changes["description"]
            if "content" in draft_changes:
                report.content = draft_changes["content"]
            if "metadata" in draft_changes:
                report.metadata = draft_changes["metadata"]

            # Update report version
            current_version = float(report.version)
            new_version = str(current_version + 1.0)
            report.version = new_version
            report.updated_at = utc_now()

            # Create new report version
            version = ReportVersion(
                report_id=report.id,
                version=new_version,
                content=report.content
            )
            self.db.add(version)
            print("Report version updated")

            # Clear draft changes
            draft_changes["has_draft_changes"] = False
            draft_changes["last_published_at"] = utc_now().isoformat()
            draft_changes["published_by"] = str(user_id)
            workflow.workflow_metadata["draft_changes"] = draft_changes
            print("Draft changes cleared")
            # Update ChromaDB with new content
            await self._update_chroma(
                self.report_service.collection_name,
                str(report.id),
                {
                    "name": report.name,
                    "description": report.description,
                    "type": report.reportType,
                    "content": report.content
                },
                {
                    "created_by": str(user_id),
                    "workflow_id": str(workflow_id),
                    "updated_at": report.updated_at.isoformat(),
                    "version": new_version
                }
            )

        publish_results = {}
        print("Publish results: ", publish_results)
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

        if publish_options.get("send_to_teams"):
            await self._send_to_teams(report, workflow, publish_results)

        if publish_options.get("publish_to_cornerstone"):
            await self._publish_to_cornerstone(report, workflow, publish_results)
        print("Publish results: ", publish_results,publish_options)
        # Update report status
        report.is_active = True
        report.updated_at = utc_now()
        print("Report updated")

        # Update workflow
        workflow.state = WorkflowState.ACTIVE
        workflow.completed_at = utc_now()
        print("Workflow completed")
        workflow.current_step = 8
        print("Workflow current step updated")

        # Create final version
        await self._create_workflow_version(workflow, user_id, note="Published with changes" if has_draft_changes else "Published")
        print("Workflow version created")
        await self.db.commit()
        print("Workflow committed")
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
        try:
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
            if "alerts" not in workflow.workflow_metadata:
                workflow.workflow_metadata["alerts"] = []

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

            workflow.workflow_metadata["alerts"].append(alert_component)

            # Update workflow state if this is the first alert
            if workflow.state == WorkflowState.CONFIGURED and len(workflow.workflow_metadata["alerts"]) == 1:
                workflow.state = WorkflowState.CONFIGURING
                workflow.current_step = 2
            print(f"Alert Component {alert_component}")
            print(f"Workflow Alert Component {workflow}")
            await self._update_report_workflow(workflow_id,workflow.workflow_metadata)
            # Update report content
            await self._update_report_content(workflow)

            await self.db.commit()

            return {
                "success": True,
                "alert_id": alert_component["id"],
                "alert_name": alert_component["question"],
                "message": f"Alert '{alert_component['question']}' added successfully"
            }
        except Exception as e:
            print("============= Error adding alert=====================")
            traceback.print_exc()
            print("=================Error ended here==================== ")
            await self.db.rollback()
            raise e

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
        alerts = workflow.workflow_metadata.get("alerts", [])
        alert_component = None
        alert_index = None

        for i, alert in enumerate(alerts):
            if alert["id"] == str(alert_id):
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
        workflow.workflow_metadata["alerts"] = alerts

        # Update report content
        await self._update_report_content(workflow)
        await self._update_report_workflow(workflow_id, workflow.workflow_metadata)

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

        return workflow.workflow_metadata.get("alerts", [])

    async def delete_alert_thread_component(
        self,
        user_id: UUID,
        workflow_id: UUID,
        alert_id: str
    ) -> Dict[str, Any]:
        """
        Delete an alert thread component
        """
        try:
            

                workflow = await self._get_report_workflow(workflow_id, user_id)

                # Find and remove the alert component
                alerts = workflow.workflow_metadata.get("alerts", [])
                alert_component = None

                for alert in alerts:
                    if alert["id"] == str(alert_id):
                        alert_component = alert
                        break

                if not alert_component:
                    raise ValueError(f"Alert component {alert_id} not found")
                print(f"Alerts before deletion: {alerts}")
                print(f" alert component: {alert_component}")
                # Remove the alert
                alerts = [alert for alert in alerts if alert["id"] != alert_id]
                print(f"Alerts after deletion: {alerts}")
                if alerts:
                    workflow.workflow_metadata["alerts"] = alerts
                else:
                    workflow.workflow_metadata.pop("alerts", None)
                
                await self._update_report_workflow(workflow_id, workflow.workflow_metadata)

                # Update report content
                await self._update_report_content(workflow)

                await self.db.commit()

                return {
                    "success": True,
                    "alert_id": alert_id,
                    "alert_name": alert_component["question"],
                    "message": f"Alert '{alert_component['question']}' deleted successfully"
                }
        except Exception as e:
            print("============= Error deleting alert=====================")
            traceback.print_exc()
            print("=================Error ended here==================== ")
            await self.db.rollback()
            raise e
        
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
        alerts = workflow.workflow_metadata.get("alerts", [])
        print(f"Alerts: {alerts}")
        alert_component = None

        for alert in alerts:
            print(f"alert_id {alert['id']}, type: {type(alert['id'])}, given alert_id: {alert_id}, type: {type(alert_id)}")
            if alert['id'] == str(alert_id):
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


    async def _update_report_workflow(self, workflow_id, workflow_metadata):
        from sqlalchemy import update
        stmt = (
            update(ReportWorkflow)
            .where(ReportWorkflow.id == workflow_id)
            .values(workflow_metadata=workflow_metadata)
        )
        await self.db.execute(stmt)
        await self.db.commit()  # Don't forget to commit if you want changes saved

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
            "alerts": workflow.workflow_metadata.get("alerts", []),
            "metadata": {
                "updated_at": utc_now().isoformat(),
                "version": report.version
            }
        }
        print(f"Content in update content from report workflow service: {content}")


        report.content = content
        report.updated_at = utc_now()

        # Create version
        from decimal import Decimal, ROUND_DOWN

        new_version = str(Decimal(report.version) + Decimal('0.1'))
        version = ReportVersion(
            report_id=report.id,
            version=new_version,
            content=content
        )
        self.db.add(version)
        self.db.add(report)
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

    async def _send_to_teams(self, report: Report, workflow: ReportWorkflow, files: Dict[str, Any]):
        """Send report to Microsoft Teams"""
        # Placeholder - would use Microsoft Teams Graph API
        pass

    async def _publish_to_cornerstone(self, report: Report, workflow: ReportWorkflow, files: Dict[str, Any]):
        """Publish report to Cornerstone OnDemand"""
        # Placeholder - would use Cornerstone REST API
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

    # ==================== Draft-Based Editing Methods ====================

    async def update_report_info(
        self,
        user_id: UUID,
        workflow_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        content: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Report:
        """Update report basic information - creates draft version that doesn't affect published report"""
        
        workflow = await self._get_report_workflow(workflow_id, user_id)
        
        # Get report
        stmt = select(Report).where(Report.id == workflow.report_id)
        result = await self.db.execute(stmt)
        report = result.scalar_one_or_none()
        
        if not report:
            raise ValueError(f"Report not found for workflow {workflow_id}")
        
        # Store draft changes in workflow metadata instead of updating published report
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
        draft_changes["last_edited_at"] = utc_now().isoformat()
        draft_changes["edited_by"] = str(user_id)
        
        # Update workflow metadata
        workflow.workflow_metadata["draft_changes"] = draft_changes
        workflow.updated_at = utc_now()
        
        # Create workflow version for draft changes
        await self._create_workflow_version(workflow, user_id, note="Draft changes made")
        
        await self.db.commit()
        
        # Return report with draft changes applied for preview
        preview_report = Report(
            id=report.id,
            name=draft_changes.get("name", report.name),
            description=draft_changes.get("description", report.description),
            reportType=report.reportType,
            is_active=report.is_active,
            content=draft_changes.get("content", report.content),
            version=report.version,
            created_at=report.created_at,
            updated_at=workflow.updated_at
        )
        
        return preview_report

    async def add_report_section_draft(
        self,
        user_id: UUID,
        workflow_id: UUID,
        section_type: str,
        section_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add a section to the report - creates draft version if report is published"""
        
        workflow = await self._get_report_workflow(workflow_id, user_id)

        # Allow editing in more states for draft changes
        if workflow.state not in [WorkflowState.DRAFT, WorkflowState.CONFIGURING, WorkflowState.PUBLISHED, WorkflowState.ACTIVE]:
            raise ValueError(f"Cannot add sections in {workflow.state} state")

        # Add section
        section = {
            "id": str(uuid.uuid4()),
            "type": section_type,
            "config": section_config,
            "order": len(workflow.sections or []) + 1,
            "created_at": utc_now().isoformat()
        }

        sections = workflow.sections or []
        sections.append(section)
        workflow.sections = sections

        # Mark as draft changes if workflow is published/active
        if workflow.state in [WorkflowState.PUBLISHED, WorkflowState.ACTIVE]:
            draft_changes = workflow.workflow_metadata.get("draft_changes", {})
            draft_changes["has_draft_changes"] = True
            draft_changes["last_edited_at"] = utc_now().isoformat()
            draft_changes["edited_by"] = str(user_id)
            workflow.workflow_metadata["draft_changes"] = draft_changes
        else:
            # Update state if first section and in draft/configuring
            if workflow.state == WorkflowState.DRAFT:
                workflow.state = WorkflowState.CONFIGURING
                workflow.current_step = 2

        # Update report content
        await self._update_report_content(workflow)

        # Create version
        await self._create_workflow_version(workflow, user_id, note="Section added" if workflow.state in [WorkflowState.PUBLISHED, WorkflowState.ACTIVE] else None)

        await self.db.commit()
        return section

    async def update_report_section_draft(
        self,
        user_id: UUID,
        workflow_id: UUID,
        section_id: str,
        section_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a report section - creates draft version if report is published"""
        
        workflow = await self._get_report_workflow(workflow_id, user_id)

        # Find and update section
        sections = workflow.sections or []
        section_found = False
        
        for section in sections:
            if section["id"] == section_id:
                section["config"] = section_config
                section["updated_at"] = utc_now().isoformat()
                section_found = True
                break

        if not section_found:
            raise ValueError(f"Section {section_id} not found")

        workflow.sections = sections

        # Mark as draft changes if workflow is published/active
        if workflow.state in [WorkflowState.PUBLISHED, WorkflowState.ACTIVE]:
            draft_changes = workflow.workflow_metadata.get("draft_changes", {})
            draft_changes["has_draft_changes"] = True
            draft_changes["last_edited_at"] = utc_now().isoformat()
            draft_changes["edited_by"] = str(user_id)
            workflow.workflow_metadata["draft_changes"] = draft_changes

        # Update report content
        await self._update_report_content(workflow)

        # Create version
        await self._create_workflow_version(workflow, user_id, note="Section updated" if workflow.state in [WorkflowState.PUBLISHED, WorkflowState.ACTIVE] else None)

        await self.db.commit()
        return {"section_id": section_id, "updated": True}

    async def remove_report_section_draft(
        self,
        user_id: UUID,
        workflow_id: UUID,
        section_id: str
    ) -> bool:
        """Remove a report section - creates draft version if report is published"""
        
        workflow = await self._get_report_workflow(workflow_id, user_id)

        # Find and remove section
        sections = workflow.sections or []
        section_found = False
        
        for i, section in enumerate(sections):
            if section["id"] == section_id:
                sections.pop(i)
                section_found = True
                break

        if not section_found:
            raise ValueError(f"Section {section_id} not found")

        workflow.sections = sections

        # Mark as draft changes if workflow is published/active
        if workflow.state in [WorkflowState.PUBLISHED, WorkflowState.ACTIVE]:
            draft_changes = workflow.workflow_metadata.get("draft_changes", {})
            draft_changes["has_draft_changes"] = True
            draft_changes["last_edited_at"] = utc_now().isoformat()
            draft_changes["edited_by"] = str(user_id)
            workflow.workflow_metadata["draft_changes"] = draft_changes

        # Update report content
        await self._update_report_content(workflow)

        # Create version
        await self._create_workflow_version(workflow, user_id, note="Section removed" if workflow.state in [WorkflowState.PUBLISHED, WorkflowState.ACTIVE] else None)

        await self.db.commit()
        return True

    async def get_draft_changes(
        self,
        user_id: UUID,
        workflow_id: UUID
    ) -> Dict[str, Any]:
        """Get current draft changes for a report workflow"""
        
        workflow = await self._get_report_workflow(workflow_id, user_id)
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
        
        workflow = await self._get_report_workflow(workflow_id, user_id)
        
        # Clear draft changes
        draft_changes = workflow.workflow_metadata.get("draft_changes", {})
        draft_changes["has_draft_changes"] = False
        draft_changes["discarded_at"] = utc_now().isoformat()
        draft_changes["discarded_by"] = str(user_id)
        workflow.workflow_metadata["draft_changes"] = draft_changes
        
        # Create version for discard action
        await self._create_workflow_version(workflow, user_id, note="Draft changes discarded")
        
        await self.db.commit()
        return True

    async def get_report_preview(
        self,
        user_id: UUID,
        workflow_id: UUID
    ) -> Dict[str, Any]:
        """Get report preview with draft changes applied"""
        
        workflow = await self._get_report_workflow(workflow_id, user_id)
        
        # Get report
        stmt = select(Report).where(Report.id == workflow.report_id)
        result = await self.db.execute(stmt)
        report = result.scalar_one_or_none()
        
        if not report:
            raise ValueError(f"Report not found for workflow {workflow_id}")
        
        # Get draft changes
        draft_changes = workflow.workflow_metadata.get("draft_changes", {})
        has_draft_changes = draft_changes.get("has_draft_changes", False)
        
        # Build preview with draft changes applied
        preview = {
            "report_id": str(report.id),
            "name": draft_changes.get("name", report.name),
            "description": draft_changes.get("description", report.description),
            "content": draft_changes.get("content", report.content),
            "metadata": draft_changes.get("metadata", report.metadata),
            "version": report.version,
            "is_active": report.is_active,
            "created_at": report.created_at.isoformat(),
            "updated_at": report.updated_at.isoformat(),
            "has_draft_changes": has_draft_changes,
            "draft_info": {
                "last_edited_at": draft_changes.get("last_edited_at"),
                "edited_by": draft_changes.get("edited_by"),
                "last_published_at": draft_changes.get("last_published_at"),
                "published_by": draft_changes.get("published_by")
            },
            "sections": workflow.sections or [],
            "data_sources": workflow.data_sources or [],
            "formatting": workflow.formatting or {}
        }
        
        return preview

    async def _create_workflow_version(
        self,
        workflow: ReportWorkflow,
        user_id: UUID,
        note: str = None
    ):
        """Create a workflow version for audit trail"""
        try:
            from app.models.workflowmodels import WorkflowVersion
            print("Creating workflow version")
            # Get current version number
            stmt = select(func.max(WorkflowVersion.version_number)).where(
                WorkflowVersion.report_workflow_id == workflow.id
            )
            result = await self.db.execute(stmt)
            max_version = result.scalar() or 0
            print("Current version number: ", max_version)
            # Create version
            version = WorkflowVersion(
            report_workflow_id=workflow.id,
            version_number=max_version + 1,
            state=workflow.state,
            snapshot_data={
                "sections": workflow.sections,
                "data_sources": workflow.data_sources,
                "formatting": workflow.formatting,
                "workflow_metadata": workflow.workflow_metadata,
                "note": note
            },
            created_by=user_id
            )
            print("Version line")
            self.db.add(version)
            print("Version added db")
            # await self.db.commit()
        except Exception as e:
            print("================== Error in workflow create ===================")
            traceback.print_exc()
            print("====================== Error Ended here=====================")

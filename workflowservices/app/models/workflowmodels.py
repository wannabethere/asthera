from enum import Enum
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.ext.mutable import MutableList, MutableDict
import uuid

def utc_now():
    """
    Get current UTC datetime.

    This creates a timezone-aware datetime and then removes the timezone
    information, making it naive, which is required for a
    'TIMESTAMP WITHOUT TIME ZONE' database column.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, UUID as SQLUUID, JSON, Integer, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.models.dbmodels import Base
from app.models.user import User
from app.models.thread import ThreadMessage

class SharingPermission(Enum):
    PRIVATE = "private"
    USER = "user"
    TEAM = "team"
    WORKSPACE = "workspace"
    DEFAULT = "default"
# Workflow States
class WorkflowState(str, Enum):
    DRAFT = "draft"
    CONFIGURING = "configuring"
    CONFIGURED = "configured"
    SHARING = "sharing"
    SHARED = "shared"
    SCHEDULING = "scheduling"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"
    ERROR = "error"

# Integration Types
class IntegrationType(str, Enum):
    TABLEAU = "tableau"
    POWERBI = "powerbi"
    SLACK = "slack"
    TEAMS = "teams"
    CORNERSTONE = "cornerstone"
    EMAIL = "email"
    WEBHOOK = "webhook"
    GOOGLE_SHEETS = "google_sheets"
    SNOWFLAKE = "snowflake"
    S3 = "s3"
    AZURE_BLOB = "azure_blob"

# Schedule Types
class ScheduleType(str, Enum):
    ONCE = "once"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CRON = "cron"
    REALTIME = "realtime"

# Thread Message Component Types
class ComponentType(str, Enum):
    QUESTION = "question"
    DESCRIPTION = "description"
    OVERVIEW = "overview"
    CHART = "chart"
    TABLE = "table"
    METRIC = "metric"
    INSIGHT = "insight"
    NARRATIVE = "narrative"
    ALERT = "alert"
    SQL_SUMMARY = "sql_summary"  # SQL query summary and visualization component

# Alert Types
class AlertType(str, Enum):
    THRESHOLD = "threshold"
    ANOMALY = "anomaly"
    TREND = "trend"
    COMPARISON = "comparison"
    SCHEDULE = "schedule"
    MANUAL = "manual"

# Alert Severity Levels
class AlertSeverity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

# Alert Status
class AlertStatus(str, Enum):
    ACTIVE = "active"
    TRIGGERED = "triggered"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISABLED = "disabled"

# Share Types
class ShareType(str, Enum):
    USER = "user"
    TEAM = "team"
    PROJECT = "project"
    WORKSPACE = "workspace"
    EMAIL = "email"
    PUBLIC_LINK = "public_link"

# Database Models for Workflow Management
class DashboardWorkflow(Base):
    __tablename__ = "dashboard_workflows"

    id = Column(SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dashboard_id = Column(SQLUUID(as_uuid=True), ForeignKey("dashboards.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(SQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    state = Column(SQLEnum(WorkflowState), nullable=False, default=WorkflowState.DRAFT)
    current_step = Column(Integer, default=0)
    workflow_metadata = Column(MutableDict.as_mutable(JSON), default={})
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    thread_components = relationship("ThreadComponent", back_populates="workflow", cascade="all, delete-orphan")
    share_configs = relationship("ShareConfiguration", back_populates="workflow", cascade="all, delete-orphan")
    schedule_config = relationship("ScheduleConfiguration", back_populates="workflow", uselist=False, cascade="all, delete-orphan")
    integrations = relationship("IntegrationConfig", back_populates="workflow", cascade="all, delete-orphan")
    workflow_versions = relationship("WorkflowVersion", back_populates="workflow", cascade="all, delete-orphan")
    dashboard = relationship("Dashboard", back_populates="workflows", foreign_keys=[dashboard_id])
class ThreadComponent(Base):
    __tablename__ = "thread_components"

    id = Column(SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(SQLUUID(as_uuid=True), ForeignKey("dashboard_workflows.id", ondelete="CASCADE"), nullable=True)
    report_workflow_id = Column(SQLUUID(as_uuid=True), ForeignKey("report_workflows.id", ondelete="CASCADE"), nullable=True)
    thread_message_id = Column(SQLUUID(as_uuid=True), ForeignKey("thread_messages.id", ondelete="SET NULL"), nullable=True)
    component_type = Column(SQLEnum(ComponentType), nullable=False)
    sequence_order = Column(Integer, nullable=False)

    # Component content
    question = Column(String, nullable=True)
    description = Column(String, nullable=True)
    overview = Column(JSON, nullable=True)
    chart_config = Column(JSON, nullable=True)
    table_config = Column(JSON, nullable=True)
    # SQL Summary specific fields
    sql_query = Column(String, nullable=True)  # The SQL query executed
    executive_summary = Column(String, nullable=True)  # Executive summary text
    data_overview = Column(JSON, nullable=True)  # Data overview statistics
    visualization_data = Column(JSON, nullable=True)  # Visualization configuration and data
    sample_data = Column(JSON, nullable=True)  # Sample data for preview
    thread_metadata = Column(JSON, nullable=True)  # Query execution metadata
    chart_schema = Column(JSON, nullable=True)  # Chart schema (vega_lite, plotly, etc.)
    reasoning = Column(String, nullable=True)  # Reasoning behind the analysis
    data_count = Column(Integer, nullable=True)  # Number of records processed
    validation_results = Column(JSON, nullable=True)  # Data validation results


    # Alert-specific configuration (when component_type is ALERT)
    alert_config = Column(JSON, nullable=True)  # Alert type, severity, conditions
    alert_status = Column(SQLEnum(AlertStatus), nullable=True)  # Current alert status
    last_triggered = Column(DateTime, nullable=True)  # When alert was last triggered
    trigger_count = Column(Integer, default=0)  # Number of times triggered

    # Configuration for the component
    configuration = Column(JSON, default={})
    is_configured = Column(Boolean, default=False)

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    workflow = relationship("DashboardWorkflow", back_populates="thread_components", foreign_keys=[workflow_id])
    report_workflow = relationship("ReportWorkflow", back_populates="thread_components", foreign_keys=[report_workflow_id])

    @classmethod
    def create_sql_summary_component(
        cls,
        workflow_id: Optional[str] = None,
        report_workflow_id: Optional[str] = None,
        thread_message_id: Optional[str] = None,
        sequence_order: int = 0,
        sql_summary_data: Dict[str, Any] = None,
        question: Optional[str] = None,
        description: Optional[str] = None
    ) -> "ThreadComponent":
        """Create a ThreadComponent for SQL summary data.

        Args:
            workflow_id: ID of the dashboard workflow
            report_workflow_id: ID of the report workflow
            thread_message_id: ID of the thread message
            sequence_order: Order of the component in the thread
            sql_summary_data: Data from SQL summary response
            question: Optional question text
            description: Optional description text

        Returns:
            ThreadComponent instance configured for SQL summary
        """
        component = cls(
            workflow_id=workflow_id,
            report_workflow_id=report_workflow_id,
            thread_message_id=thread_message_id,
            component_type=ComponentType.SQL_SUMMARY,
            sequence_order=sequence_order,
            question=question,
            description=description,
            is_configured=True
        )

        if sql_summary_data:
            # Map SQL summary response data to component fields
            component.sql_query = sql_summary_data.get("sql_query")
            component.executive_summary = sql_summary_data.get("executive_summary")
            component.data_overview = sql_summary_data.get("data_overview")
            component.visualization_data = sql_summary_data.get("visualization")
            component.sample_data = sql_summary_data.get("sample_data")
            component.metadata = sql_summary_data.get("metadata")
            component.chart_schema = sql_summary_data.get("chart_schema")
            component.reasoning = sql_summary_data.get("reasoning")
            component.data_count = sql_summary_data.get("data_count")
            component.validation_results = sql_summary_data.get("validation_results")

            # Store additional chart schemas in configuration
            additional_config = {}
            if "plotly_schema" in sql_summary_data:
                additional_config["plotly_schema"] = sql_summary_data["plotly_schema"]
            if "powerbi_schema" in sql_summary_data:
                additional_config["powerbi_schema"] = sql_summary_data["powerbi_schema"]
            if "vega_lite_schema" in sql_summary_data:
                additional_config["vega_lite_schema"] = sql_summary_data["vega_lite_schema"]
            if "execution_config" in sql_summary_data:
                additional_config["execution_config"] = sql_summary_data["execution_config"]

            if additional_config:
                component.configuration = additional_config

        return component


class ShareConfiguration(Base):
    __tablename__ = "share_configurations"

    id = Column(SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(SQLUUID(as_uuid=True), ForeignKey("dashboard_workflows.id", ondelete="CASCADE"), nullable=True)
    report_workflow_id = Column(SQLUUID(as_uuid=True), ForeignKey("report_workflows.id", ondelete="CASCADE"), nullable=True)
    share_type = Column(SQLEnum(ShareType), nullable=False)
    target_id = Column(String, nullable=False)  # User ID, Team ID, Email, etc.
    permissions = Column(JSON, default={})
    notification_sent = Column(Boolean, default=False)
    accepted = Column(Boolean, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    workflow = relationship("DashboardWorkflow", back_populates="share_configs", foreign_keys=[workflow_id])
    report_workflow = relationship("ReportWorkflow", back_populates="share_configs", foreign_keys=[report_workflow_id])

class ScheduleConfiguration(Base):
    __tablename__ = "schedule_configurations"

    id = Column(SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(SQLUUID(as_uuid=True), ForeignKey("dashboard_workflows.id", ondelete="CASCADE"), nullable=True)
    report_workflow_id = Column(SQLUUID(as_uuid=True), ForeignKey("report_workflows.id", ondelete="CASCADE"), nullable=True)
    schedule_type = Column(SQLEnum(ScheduleType), nullable=False)
    cron_expression = Column(String, nullable=True)
    timezone = Column(String, default="UTC")
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    last_run = Column(DateTime, nullable=True)
    next_run = Column(DateTime, nullable=True)
    run_count = Column(Integer, default=0)
    configuration = Column(JSON, default={})
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    workflow = relationship("DashboardWorkflow", back_populates="schedule_config", foreign_keys=[workflow_id])
    report_workflow = relationship("ReportWorkflow", back_populates="schedule_config", foreign_keys=[report_workflow_id])

class IntegrationConfig(Base):
    __tablename__ = "integration_configs"

    id = Column(SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(SQLUUID(as_uuid=True), ForeignKey("dashboard_workflows.id", ondelete="CASCADE"), nullable=True)
    report_workflow_id = Column(SQLUUID(as_uuid=True), ForeignKey("report_workflows.id", ondelete="CASCADE"), nullable=True)
    integration_type = Column(SQLEnum(IntegrationType), nullable=False)
    connection_config = Column(JSON, nullable=False)  # Encrypted credentials
    mapping_config = Column(JSON, default={})  # Field mappings
    filter_config = Column(JSON, default={})  # Data filters
    transform_config = Column(JSON, default={})  # Data transformations
    is_active = Column(Boolean, default=True)
    last_sync = Column(DateTime, nullable=True)
    sync_status = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    workflow = relationship("DashboardWorkflow", back_populates="integrations", foreign_keys=[workflow_id])
    report_workflow = relationship("ReportWorkflow", back_populates="integrations", foreign_keys=[report_workflow_id])

class WorkflowVersion(Base):
    __tablename__ = "workflow_versions"

    id = Column(SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(SQLUUID(as_uuid=True), ForeignKey("dashboard_workflows.id", ondelete="CASCADE"), nullable=True)
    report_workflow_id = Column(SQLUUID(as_uuid=True), ForeignKey("report_workflows.id", ondelete="CASCADE"), nullable=True)
    version_number = Column(Integer, nullable=False)
    state = Column(SQLEnum(WorkflowState), nullable=False)
    snapshot_data = Column(JSON, nullable=False)  # Complete snapshot of workflow state
    created_by = Column(SQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    workflow = relationship("DashboardWorkflow", back_populates="workflow_versions", foreign_keys=[workflow_id])
    report_workflow = relationship("ReportWorkflow", back_populates="workflow_versions", foreign_keys=[report_workflow_id])

# Report Workflow Model
class ReportWorkflow(Base):
    __tablename__ = "report_workflows"

    id = Column(SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(SQLUUID(as_uuid=True), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(SQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    state = Column(SQLEnum(WorkflowState), nullable=False, default=WorkflowState.DRAFT)
    report_template = Column(String, nullable=False)
    sections = Column(MutableList.as_mutable(JSON), default=[])
    data_sources = Column(MutableList.as_mutable(JSON), default=[])
    formatting = Column(MutableDict.as_mutable(JSON), default={})
    current_step = Column(Integer, default=0)
    workflow_metadata = Column(JSON, default={})
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    thread_components = relationship("ThreadComponent", back_populates="report_workflow", cascade="all, delete-orphan")
    share_configs = relationship("ShareConfiguration", back_populates="report_workflow", cascade="all, delete-orphan")
    schedule_config = relationship("ScheduleConfiguration", back_populates="report_workflow", uselist=False, cascade="all, delete-orphan")
    integrations = relationship("IntegrationConfig", back_populates="report_workflow", cascade="all, delete-orphan")
    workflow_versions = relationship("WorkflowVersion", back_populates="report_workflow", cascade="all, delete-orphan")

# Pydantic Models for API
class ThreadComponentCreate(BaseModel):
    component_type: ComponentType
    question: Optional[str] = None
    description: Optional[str] = None
    overview: Optional[Dict[str, Any]] = None
    chart_config: Optional[Dict[str, Any]] = None
    table_config: Optional[Dict[str, Any]] = None
    configuration: Dict[str, Any] = Field(default_factory=dict)
    # SQL Summary specific fields
    sql_query: Optional[str] = None
    executive_summary: Optional[str] = None
    data_overview: Optional[Dict[str, Any]] = None
    visualization_data: Optional[Dict[str, Any]] = None
    sample_data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    chart_schema: Optional[Dict[str, Any]] = None
    reasoning: Optional[str] = None
    data_count: Optional[int] = None
    validation_results: Optional[Dict[str, Any]] = None

class ThreadComponentUpdate(BaseModel):
    question: Optional[str] = None
    description: Optional[str] = None
    overview: Optional[Dict[str, Any]] = None
    chart_config: Optional[Dict[str, Any]] = None
    table_config: Optional[Dict[str, Any]] = None
    configuration: Optional[Dict[str, Any]] = None
    is_configured: Optional[bool] = None
    # SQL Summary specific fields
    sql_query: Optional[str] = None
    executive_summary: Optional[str] = None
    data_overview: Optional[Dict[str, Any]] = None
    visualization_data: Optional[Dict[str, Any]] = None
    sample_data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    chart_schema: Optional[Dict[str, Any]] = None
    reasoning: Optional[str] = None
    data_count: Optional[int] = None
    validation_results: Optional[Dict[str, Any]] = None

class ThreadComponentResponse(BaseModel):
    id: UUID
    workflow_id: UUID
    thread_message_id: Optional[UUID]
    component_type: ComponentType
    sequence_order: int
    question: Optional[str]
    description: Optional[str]
    overview: Optional[Dict[str, Any]]
    chart_config: Optional[Dict[str, Any]]
    table_config: Optional[Dict[str, Any]]
    configuration: Dict[str, Any]
    is_configured: bool
    created_at: datetime
    updated_at: datetime
    # SQL Summary specific fields
    sql_query: Optional[str] = None
    executive_summary: Optional[str] = None
    data_overview: Optional[Dict[str, Any]] = None
    visualization_data: Optional[Dict[str, Any]] = None
    sample_data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    chart_schema: Optional[Dict[str, Any]] = None
    reasoning: Optional[str] = None
    data_count: Optional[int] = None
    validation_results: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

class ShareConfigCreate(BaseModel):
    share_type: ShareType
    target_ids: List[str]  # Can be UUIDs or emails
    permissions: Dict[str, Any] = Field(default_factory=dict)

class ShareReportCreate(BaseModel):
    share_with: List[UUID]
    permission_level: SharingPermission

class ScheduleConfigCreate(BaseModel):
    schedule_type: ScheduleType
    cron_expression: Optional[str] = None
    timezone: str = "UTC"
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    configuration: Dict[str, Any] = Field(default_factory=dict)

class IntegrationConfigCreate(BaseModel):
    integration_type: IntegrationType
    connection_config: Dict[str, Any]
    mapping_config: Dict[str, Any] = Field(default_factory=dict)
    filter_config: Dict[str, Any] = Field(default_factory=dict)
    transform_config: Dict[str, Any] = Field(default_factory=dict)

class WorkflowStateUpdate(BaseModel):
    state: WorkflowState
    metadata: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

class DashboardWorkflowCreate(BaseModel):
    dashboard_id: Optional[UUID] = None
    initial_metadata: Dict[str, Any] = Field(default_factory=dict)

class DashboardWorkflowResponse(BaseModel):
    id: UUID
    dashboard_id: UUID
    user_id: UUID
    state: WorkflowState
    current_step: int
    metadata: Dict[str, Any]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    thread_components: List[ThreadComponentResponse] = []

# Alert Thread Component Models
class AlertThreadComponentCreate(BaseModel):
    question: str  # Alert name/title
    description: Optional[str] = None  # Alert description
    alert_type: AlertType
    severity: AlertSeverity = AlertSeverity.MEDIUM
    condition_config: Dict[str, Any]  # Alert conditions
    threshold_config: Optional[Dict[str, Any]] = None  # For threshold alerts
    anomaly_config: Optional[Dict[str, Any]] = None   # For anomaly alerts
    trend_config: Optional[Dict[str, Any]] = None     # For trend alerts
    notification_channels: List[str] = Field(default_factory=list)  # Email, Slack, etc.
    escalation_config: Dict[str, Any] = Field(default_factory=dict)  # Escalation rules
    cooldown_period: int = 300  # Cooldown in seconds
    configuration: Dict[str, Any] = Field(default_factory=dict)
    # SQL Summary specific fields (for SQL-based alerts)
    sql_query: Optional[str] = None
    executive_summary: Optional[str] = None
    data_overview: Optional[Dict[str, Any]] = None
    visualization_data: Optional[Dict[str, Any]] = None
    sample_data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    chart_schema: Optional[Dict[str, Any]] = None
    reasoning: Optional[str] = None
    data_count: Optional[int] = None
    validation_results: Optional[Dict[str, Any]] = None


class AlertThreadComponentUpdate(BaseModel):
    question: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[AlertSeverity] = None
    condition_config: Optional[Dict[str, Any]] = None
    threshold_config: Optional[Dict[str, Any]] = None
    anomaly_config: Optional[Dict[str, Any]] = None
    trend_config: Optional[Dict[str, Any]] = None
    notification_channels: Optional[List[str]] = None
    escalation_config: Optional[Dict[str, Any]] = None
    cooldown_period: Optional[int] = None
    configuration: Optional[Dict[str, Any]] = None
    alert_status: Optional[AlertStatus] = None
    # SQL Summary specific fields (for SQL-based alerts)
    sql_query: Optional[str] = None
    executive_summary: Optional[str] = None
    data_overview: Optional[Dict[str, Any]] = None
    visualization_data: Optional[Dict[str, Any]] = None
    sample_data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    chart_schema: Optional[Dict[str, Any]] = None
    reasoning: Optional[str] = None
    data_count: Optional[int] = None
    validation_results: Optional[Dict[str, Any]] = None

class AlertThreadComponentResponse(BaseModel):
    id: UUID
    workflow_id: UUID
    thread_message_id: Optional[UUID]
    component_type: ComponentType
    sequence_order: int
    question: str
    description: Optional[str]
    alert_config: Dict[str, Any]
    alert_status: AlertStatus
    last_triggered: Optional[datetime]
    trigger_count: int
    configuration: Dict[str, Any]
    is_configured: bool
    created_at: datetime
    updated_at: datetime
    # SQL Summary specific fields (for SQL-based alerts)
    sql_query: Optional[str] = None
    executive_summary: Optional[str] = None
    data_overview: Optional[Dict[str, Any]] = None
    visualization_data: Optional[Dict[str, Any]] = None
    sample_data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    chart_schema: Optional[Dict[str, Any]] = None
    reasoning: Optional[str] = None
    data_count: Optional[int] = None
    validation_results: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

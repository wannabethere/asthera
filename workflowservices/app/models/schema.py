from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime
import uuid
from typing import Dict, List, Any, Optional, Union
from enum import Enum


class DashboardCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Dashboard name")
    description: str = Field(..., max_length=1000, description="Dashboard description")
    DashboardType: str = Field(
        ..., pattern="^(Static|Dynamic)$", title="Dashboard Type"
    )
    is_active: Optional[bool] = Field(
        default=True, description="Dashboard active status"
    )
    content: Union[Dict[str, Any], List[Dict[str, Any]]] = Field(
        ..., description="Dashboard content as JSON"
    )

    class Config:
        schema_extra = {
            "example": {
                "name": "Sales Dashboard",
                "description": "Dashboard for sales analytics",
                "DashboardType": "Static",
                "is_active": True,
                "content": {"charts": [], "widgets": []},
            }
        }


class DashboardBase(BaseModel):
    dashboardid: Optional[str] = Field(None, description="Dashboard ID for updates")
    dashboard_details: Union[DashboardCreate, List[DashboardCreate]] = Field(
        ..., description="Dashboard details - single dashboard or list of dashboards"
    )

    class Config:
        schema_extra = {
            "example": {
                "dashboardid": None,
                "dashboard_details": {
                    "name": "Sales Dashboard",
                    "description": "Dashboard for sales analytics",
                    "DashboardType": "Static",
                    "is_active": True,
                    "content": {"charts": [], "widgets": []},
                },
            }
        }


class DashboardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dashboardid: uuid.UUID
    dashboard_name: str
    dashboard_description: str
    dashboard_type: str
    dashboard_is_active: bool
    dashboard_content: Optional[Any] = None
    dashboard_version: str
    dashboard_created_at: datetime
    dashboard_updated_at: datetime


class DashboardUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    DashboardType: Optional[str] = Field(None, pattern="^(Static|Dynamic)$")
    is_active: Optional[bool] = None
    content: Optional[Dict] = None

    class Config:
        schema_extra = {
            "example": {
                "name": "Updated Sales Dashboard",
                "description": "Updated dashboard for sales analytics",
                "is_active": True,
                "content": {"charts": [], "widgets": [], "updated": True},
            }
        }


class RequestType(str, Enum):
    DASHBOARD = "dashboard"
    ALERTS = "alerts"
    REPORTS = "reports"


class GenericRequest(BaseModel):
    data: Dict[str, Any]


class ConditionDetails(BaseModel):
    condition_name: str = Field(..., description="Condition name")
    condition_type: str = Field(..., description="Condition type")
    metric_name: str = Field(..., description="Metric name")
    comparison: str = Field(..., description="Comparison")
    value: Dict[str, Any] = Field(..., description="Value")
    alert_details: Optional[Dict[str, Any]] = Field(None, description="Alert details")
    update_details: Optional[Dict[str, Any]] = Field(None, description="Update details")


class MetricDetails(BaseModel):
    metric_name: str = Field(..., description="Metric name")
    metric_type: str = Field(..., description="Metric type")
    metric_params: Dict[str, Any] = Field(..., description="Metric parameters")
    description: str = Field(..., description="Metric description")
    label: str = Field(..., description="Metric label")


class DatasetDetails(BaseModel):
    project_id: Optional[str] = Field(None, description="Project ID")
    name: str = Field(..., description="Dataset name")
    begin_date: Optional[str] = Field(None, description="Begin date")
    end_date: Optional[str] = Field(None, description="End date")
    time_dimension: Optional[str] = Field(None, description="Time dimension")
    indexes: Optional[Dict[str, Any]] = Field(None, description="Indexes")
    columns: Optional[List[str]] = Field(None, description="Columns")


class TaskCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Task name")
    description: str = Field(..., max_length=1000, description="Task description")
    status: Optional[str] = Field(None, description="Task status")
    dataset_details: Union[DatasetDetails, List[DatasetDetails]] = Field(
        ..., description="Dataset details"
    )
    metric_details: Union[MetricDetails, List[MetricDetails]] = Field(
        ..., description="Metric details"
    )
    condition_details: Union[ConditionDetails, List[ConditionDetails]] = Field(
        ..., description="Condition details"
    )


class ReportCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="report name")
    description: str = Field(..., max_length=1000, description="report description")
    reportType: str = Field(..., pattern="^(Standard|Custom)$", title="report Type")
    is_active: Optional[bool] = Field(default=True, description="report active status")
    content: Union[Dict[str, Any], List[Dict[str, Any]]] = Field(
        ..., description="report content as JSON"
    )


class ReportBase(BaseModel):
    reportid: Optional[str] = Field(None, description="report ID for updates")
    report_details: Union[ReportCreate, List[ReportCreate]] = Field(
        ..., description="report details - single report or list of reports"
    )


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reportid: uuid.UUID
    report_name: str
    report_description: str
    report_type: str
    report_is_active: bool
    report_content: Optional[Any] = None
    report_version: str
    report_created_at: datetime
    report_updated_at: datetime


class ReportUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    reportType: Optional[str] = Field(None, pattern="^(Static|Dynamic)$")
    is_active: Optional[bool] = None
    content: Optional[Dict] = None


class AlertDetailsUpdate(BaseModel):
    """Update model for alert details within condition"""

    notification_group: Optional[str] = Field(None, description="Notification group")


class UpdateDetailsUpdate(BaseModel):
    """Update model for update action details within condition"""

    action: Optional[str] = Field(None, description="Update action")


class ConditionDetailsUpdate(BaseModel):
    """Update model for condition details - all fields optional for PATCH"""

    condition_name: Optional[str] = Field(None, description="Condition name")
    condition_type: Optional[str] = Field(None, description="Condition type")
    metric_name: Optional[str] = Field(None, description="Metric name")
    comparison: Optional[str] = Field(None, description="Comparison")
    value: Optional[Dict[str, Any]] = Field(None, description="Value")
    alert_details: Optional[AlertDetailsUpdate] = Field(
        None, description="Alert details"
    )
    update_details: Optional[UpdateDetailsUpdate] = Field(
        None, description="Update details"
    )


class MetricDetailsUpdate(BaseModel):
    """Update model for metric details - all fields optional for PATCH"""

    metric_name: Optional[str] = Field(None, description="Metric name")
    metric_type: Optional[str] = Field(None, description="Metric type")
    metric_params: Optional[Dict[str, Any]] = Field(
        None, description="Metric parameters"
    )
    description: Optional[str] = Field(None, description="Metric description")
    label: Optional[str] = Field(None, description="Metric label")


class DatasetDetailsUpdate(BaseModel):
    """Update model for dataset details - all fields optional for PATCH"""

    project_id: Optional[str] = Field(None, description="Project ID")
    name: Optional[str] = Field(None, description="Dataset name")
    begin_date: Optional[str] = Field(None, description="Begin date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD)")
    time_dimension: Optional[str] = Field(None, description="Time dimension")
    indexes: Optional[Dict[str, Any]] = Field(None, description="Indexes")
    columns: Optional[List[str]] = Field(None, description="Columns")


class TaskUpdate(BaseModel):
    """Main model for alert/task updates - all fields optional for PATCH operations"""

    name: Optional[str] = Field(
        None, min_length=1, max_length=255, description="Task name"
    )
    description: Optional[str] = Field(
        None, max_length=1000, description="Task description"
    )
    status: Optional[str] = Field(None, description="Task status")
    dataset_details: Optional[DatasetDetailsUpdate] = Field(
        None, description="Dataset details"
    )
    metric_details: Optional[MetricDetailsUpdate] = Field(
        None, description="Metric details"
    )
    condition_details: Optional[ConditionDetailsUpdate] = Field(
        None, description="Condition details"
    )

    class Config:
        # Allow extra fields to be ignored
        extra = "ignore"


class Condition(BaseModel):
    conditionType: str
    metricselected: str
    schedule: str
    timecolumn: str
    value: Optional[str] = None


class AlertResponse(BaseModel):
    type: str
    question: str
    alertname: str
    summary: str
    reasoning: str
    conditions: List[Condition]
    notificationgroup: str


class Configs(BaseModel):
    conditionTypes: List[str]
    notificationgroups: List[str]
    schedule: List[str]
    timecolumn: List[str]
    availableMetrics: List[str]
    question: str

    class Config:

        extra = "forbid"
        str_strip_whitespace = True


class AlertCreate(BaseModel):
    input: str
    config: Optional[Configs] = None
    session_id: Optional[str] = None

    class Config:

        extra = "forbid"


class DashboardOutputFormat(BaseModel):
    """Generic model for storing dashboard output format - independent of agents service"""
    success: bool = Field(..., description="Whether the dashboard generation was successful")
    dashboard_data: Optional[Dict[str, Any]] = Field(None, description="Main dashboard data")
    conditional_formatting: Optional[Dict[str, Any]] = Field(None, description="Conditional formatting rules")
    chart_configurations: Optional[Dict[str, Any]] = Field(None, description="Chart configuration data")
    dashboard_config: Optional[Dict[str, Any]] = Field(None, description="Dashboard configuration")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    workflow_metadata: Optional[Dict[str, Any]] = Field(None, description="Workflow-related metadata")
    global_executive_summary: Optional[str] = Field(None, description="Global executive summary")
    error: Optional[str] = Field(None, description="Error message if any")


class ReportOutputFormat(BaseModel):
    """Generic model for storing report output format - independent of agents service"""
    success: bool = Field(..., description="Whether the report generation was successful")
    report_data: Optional[Dict[str, Any]] = Field(None, description="Main report data")
    enhanced_report: Optional[Dict[str, Any]] = Field(None, description="Enhanced report data")
    report_config: Optional[Dict[str, Any]] = Field(None, description="Report configuration")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    workflow_metadata: Optional[Dict[str, Any]] = Field(None, description="Workflow-related metadata")
    global_executive_summary: Optional[str] = Field(None, description="Global executive summary")
    error: Optional[str] = Field(None, description="Error message if any")


class DashboardSnapshotCreate(BaseModel):
    """Schema for creating a dashboard snapshot"""
    dashboard_id: uuid.UUID = Field(..., description="Dashboard ID to snapshot")
    workflow_id: Optional[uuid.UUID] = Field(None, description="Associated workflow ID if exists")
    response_data: Optional[Dict[str, Any]] = Field(None, description="Response data that triggered the snapshot")
    output_format: Optional[DashboardOutputFormat] = Field(None, description="Dashboard output format from agents service")
    metadata_tags: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata tags for filtering")
    description: Optional[str] = Field(None, max_length=1000, description="Optional description for the snapshot")


class ReportSnapshotCreate(BaseModel):
    """Schema for creating a report snapshot"""
    report_id: uuid.UUID = Field(..., description="Report ID to snapshot")
    workflow_id: Optional[uuid.UUID] = Field(None, description="Associated workflow ID if exists")
    response_data: Optional[Dict[str, Any]] = Field(None, description="Response data that triggered the snapshot")
    output_format: Optional[ReportOutputFormat] = Field(None, description="Report output format from agents service")
    metadata_tags: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata tags for filtering")
    description: Optional[str] = Field(None, max_length=1000, description="Optional description for the snapshot")


class DashboardSnapshotResponse(BaseModel):
    """Schema for dashboard snapshot response"""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dashboard_id: uuid.UUID
    workflow_id: Optional[uuid.UUID]
    user_id: uuid.UUID
    dashboard_data: Dict[str, Any]
    thread_components_data: Optional[Dict[str, Any]]
    response_data: Optional[Dict[str, Any]]
    output_format: Optional[DashboardOutputFormat] = None
    metadata_tags: Dict[str, Any]
    snapshot_timestamp: datetime
    created_at: datetime
    description: Optional[str]


class ReportSnapshotResponse(BaseModel):
    """Schema for report snapshot response"""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    report_id: uuid.UUID
    workflow_id: Optional[uuid.UUID]
    user_id: uuid.UUID
    report_data: Dict[str, Any]
    thread_components_data: Optional[Dict[str, Any]]
    response_data: Optional[Dict[str, Any]]
    output_format: Optional[ReportOutputFormat] = None
    metadata_tags: Dict[str, Any]
    snapshot_timestamp: datetime
    created_at: datetime
    description: Optional[str]


class DashboardSnapshotOutputResponse(BaseModel):
    """Schema for dashboard snapshot response with output format"""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dashboard_id: uuid.UUID
    workflow_id: Optional[uuid.UUID]
    user_id: uuid.UUID
    dashboard_data: Dict[str, Any]
    thread_components_data: Optional[Dict[str, Any]]
    output_format: Optional[DashboardOutputFormat] = Field(None, description="Dashboard output format from agents service")
    metadata_tags: Dict[str, Any]
    snapshot_timestamp: datetime
    created_at: datetime
    description: Optional[str]


class ReportSnapshotOutputResponse(BaseModel):
    """Schema for report snapshot response with output format"""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    report_id: uuid.UUID
    workflow_id: Optional[uuid.UUID]
    user_id: uuid.UUID
    report_data: Dict[str, Any]
    thread_components_data: Optional[Dict[str, Any]]
    output_format: Optional[ReportOutputFormat] = Field(None, description="Report output format from agents service")
    metadata_tags: Dict[str, Any]
    snapshot_timestamp: datetime
    created_at: datetime
    description: Optional[str]


class DashboardSnapshotEventCreate(BaseModel):
    """Schema for creating a single dashboard snapshot event"""
    dashboard_id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None
    component_id: Optional[uuid.UUID] = None
    question: Optional[str] = Field(None, max_length=1000)
    query_text: Optional[str] = Field(None, max_length=2000)
    sql_query: Optional[str] = Field(None, max_length=5000)
    chart_schema: Optional[Dict[str, Any]] = None
    data: Dict[str, Any] = Field(..., description="Chart/data as JSON")
    summary: Optional[str] = None
    executive_summary: Optional[str] = None
    component_type: Optional[str] = Field(None, max_length=50)
    sequence_order: Optional[int] = None
    event_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class DashboardSnapshotEventsCreate(BaseModel):
    """Schema for creating multiple dashboard snapshot events at once"""
    dashboard_id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None
    events: List[DashboardSnapshotEventCreate] = Field(..., min_items=1, description="List of events to create")
    metadata_tags: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Common metadata for all events")


class ReportSnapshotEventCreate(BaseModel):
    """Schema for creating a single report snapshot event"""
    report_id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None
    component_id: Optional[uuid.UUID] = None
    question: Optional[str] = Field(None, max_length=1000)
    query_text: Optional[str] = Field(None, max_length=2000)
    sql_query: Optional[str] = Field(None, max_length=5000)
    chart_schema: Optional[Dict[str, Any]] = None
    data: Dict[str, Any] = Field(..., description="Chart/data as JSON")
    summary: Optional[str] = None
    executive_summary: Optional[str] = None
    component_type: Optional[str] = Field(None, max_length=50)
    sequence_order: Optional[int] = None
    event_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ReportSnapshotEventsCreate(BaseModel):
    """Schema for creating multiple report snapshot events at once"""
    report_id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None
    events: List[ReportSnapshotEventCreate] = Field(..., min_items=1, description="List of events to create")
    metadata_tags: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Common metadata for all events")


class DashboardSnapshotEventResponse(BaseModel):
    """Schema for dashboard snapshot event response"""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dashboard_id: uuid.UUID
    workflow_id: Optional[uuid.UUID]
    component_id: Optional[uuid.UUID]
    user_id: uuid.UUID
    question: Optional[str]
    query_text: Optional[str]
    sql_query: Optional[str]
    chart_schema: Optional[Dict[str, Any]]
    data: Dict[str, Any]
    summary: Optional[str]
    executive_summary: Optional[str]
    component_type: Optional[str]
    sequence_order: Optional[int]
    event_metadata: Dict[str, Any]
    event_timestamp: datetime
    created_at: datetime


class ReportSnapshotEventResponse(BaseModel):
    """Schema for report snapshot event response"""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    report_id: uuid.UUID
    workflow_id: Optional[uuid.UUID]
    component_id: Optional[uuid.UUID]
    user_id: uuid.UUID
    question: Optional[str]
    query_text: Optional[str]
    sql_query: Optional[str]
    chart_schema: Optional[Dict[str, Any]]
    data: Dict[str, Any]
    summary: Optional[str]
    executive_summary: Optional[str]
    component_type: Optional[str]
    sequence_order: Optional[int]
    event_metadata: Dict[str, Any]
    event_timestamp: datetime
    created_at: datetime


# ==================== Project Schemas ====================

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(None, max_length=2000, description="Project description")
    workspace_id: uuid.UUID = Field(..., description="Workspace this project belongs to")
    goals: Optional[List[str]] = Field(default_factory=list, description="Project goals")
    data_sources: Optional[List[str]] = Field(default_factory=list, description="Connected data sources")
    thread_id: Optional[uuid.UUID] = Field(None, description="Primary conversation thread ID")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    goals: Optional[List[str]] = None
    data_sources: Optional[List[str]] = None
    thread_id: Optional[uuid.UUID] = None
    status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: Optional[str] = None
    workspace_id: uuid.UUID
    goals: Optional[List[str]] = None
    data_sources: Optional[List[str]] = None
    thread_id: Optional[uuid.UUID] = None
    created_by: Optional[uuid.UUID] = None
    status: str = "active"
    created_at: datetime
    updated_at: Optional[datetime] = None


class ProjectArtifactCreate(BaseModel):
    artifact_type: str = Field(..., description="Type: dashboard, report, alert")
    artifact_id: uuid.UUID = Field(..., description="ID of the artifact to link")
    parent_artifact_id: Optional[uuid.UUID] = Field(None, description="Parent artifact ID for nesting (e.g., alert under dashboard)")
    sequence_order: Optional[int] = Field(0, description="Order within the project")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ProjectArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    artifact_type: str
    artifact_id: uuid.UUID
    parent_artifact_id: Optional[uuid.UUID] = None
    sequence_order: int = 0
    artifact_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    # Populated by service layer when fetching with details
    artifact_details: Optional[Dict[str, Any]] = None


class ProjectWithArtifactsResponse(ProjectResponse):
    artifacts: List[ProjectArtifactResponse] = []
    dashboard_count: int = 0
    report_count: int = 0
    alert_count: int = 0


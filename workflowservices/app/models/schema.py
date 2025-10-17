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

    

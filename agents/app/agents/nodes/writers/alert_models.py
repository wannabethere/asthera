from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
from typing import Dict, List, Any, Optional, Union


# Enums for alert types

class AlertConditionType(str, Enum):
    INTELLIGENT_ARIMA = "intelligent_arima"
    THRESHOLD_CHANGE = "threshold_change"
    THRESHOLD_PERCENT_CHANGE = "threshold_percent_change"
    THRESHOLD_ABSOLUTE_CHANGE = "threshold_absolute_change"
    THRESHOLD_VALUE = "threshold_value"

class ScheduleType(str, Enum):
    SCHEDULED = "scheduled"
    INACTIVE = "inactive"
    ACTIVE = "active"
    CRON_SCHEDULE = "cron_schedule"

class ThresholdOperator(str, Enum):
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_EQUAL = ">="
    LESS_EQUAL = "<="
    EQUALS = "="
    NOT_EQUALS = "!="

# Input Models
class SQLAlertRequest(BaseModel):
    """Request structure for SQL-to-Alert generation"""
    sql: str
    query: str  # Natural language description
    project_id: str
    data_description: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None
    alert_request: str  # Natural language alert request
    session_id: Optional[str] = None
    sample_data: Optional[Dict[str, Any]] = None  # Sample data from SQL execution

class SQLAnalysis(BaseModel):
    """Parsed SQL structure"""
    tables: List[str]
    columns: List[str]
    metrics: List[str]  # Derived/calculated columns
    dimensions: List[str]  # Group by columns
    filters: List[Dict[str, Any]]
    aggregations: List[Dict[str, str]]  # column -> aggregation type

# Output Models
class LexyFeedCondition(BaseModel):
    """Lexy Feed condition configuration"""
    condition_type: AlertConditionType
    threshold_type: Optional[str] = None  # For threshold-based conditions
    operator: Optional[ThresholdOperator] = None
    value: Optional[Union[float, int]] = None
    
class LexyFeedMetric(BaseModel):
    """Lexy Feed metric configuration"""
    domain: str
    dataset_id: str
    measure: str
    aggregation: str
    resolution: str = "Daily"  # Daily, Weekly, Monthly, Quarterly, Yearly
    filters: List[Dict[str, Any]] = []
    drilldown_dimensions: List[str] = []

class LexyFeedNotification(BaseModel):
    """Lexy Feed notification settings"""
    schedule_type: ScheduleType
    metric_name: str
    email_addresses: List[str] = []
    subject: str
    email_message: str
    include_feed_report: bool = True
    custom_schedule: Optional[Dict[str, Any]] = None

class LexyFeedConfiguration(BaseModel):
    """Complete Lexy Feed configuration"""
    metric: LexyFeedMetric
    condition: LexyFeedCondition
    notification: LexyFeedNotification
    column_selection: Dict[str, List[str]]  # included/excluded columns
    
class SQLAlertResult(BaseModel):
    """Final result with critique and confidence"""
    feed_configuration: LexyFeedConfiguration
    sql_analysis: SQLAnalysis
    confidence_score: float
    critique_notes: List[str]
    suggestions: List[str]
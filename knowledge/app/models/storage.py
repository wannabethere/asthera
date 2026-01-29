"""
Data models for Contextual Graph PostgreSQL entities
"""
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime


@dataclass
class Control:
    """Control entity model"""
    control_id: str
    framework: str
    control_name: str
    control_description: Optional[str] = None
    category: Optional[str] = None
    vector_doc_id: Optional[str] = None
    embedding_version: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Requirement:
    """Requirement entity model"""
    requirement_id: str
    control_id: str
    requirement_text: str
    requirement_type: Optional[str] = None  # 'SHALL', 'SHOULD', 'MAY', 'GUIDANCE'
    vector_doc_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class EvidenceType:
    """Evidence type entity model"""
    evidence_id: str
    evidence_name: str
    evidence_category: Optional[str] = None  # 'log', 'report', 'configuration', 'documentation'
    collection_method: Optional[str] = None
    vector_doc_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class ControlRequirementMapping:
    """Mapping between controls and requirements"""
    control_id: str
    requirement_id: str
    is_mandatory: bool = True
    created_at: Optional[datetime] = None


@dataclass
class ComplianceMeasurement:
    """Compliance measurement (time-series data)"""
    measurement_id: Optional[int] = None
    control_id: str = ""
    measured_value: Optional[float] = None
    measurement_date: Optional[datetime] = None
    passed: Optional[bool] = None
    context_id: Optional[str] = None
    data_source: Optional[str] = None
    measurement_method: Optional[str] = None
    quality_score: Optional[float] = None
    created_at: Optional[datetime] = None


@dataclass
class ControlRiskAnalytics:
    """Aggregated risk analytics for a control"""
    control_id: str
    avg_compliance_score: Optional[float] = None
    trend: Optional[str] = None  # 'improving', 'stable', 'degrading'
    last_failure_date: Optional[datetime] = None
    failure_count_30d: int = 0
    failure_count_90d: int = 0
    current_risk_score: Optional[float] = None
    risk_level: Optional[str] = None  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    updated_at: Optional[datetime] = None


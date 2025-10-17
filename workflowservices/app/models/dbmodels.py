from sqlalchemy import (
    Column,
    String,
    Boolean,
    UUID,
    DateTime,
    Enum,
    Date,
    ForeignKey,
    func,
    Index,
    Integer,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import relationship
import uuid
import enum

Base = declarative_base()


class MetricType(enum.Enum):
    simple = "simple"
    ratio = "ratio"
    percentage = "percentage"
    count = "count"
    average = "average"
    sum = "sum"
    min = "min"
    max = "max"
    median = "median"
    rate = "rate"
    duration = "duration"
    frequency = "frequency"


class Dashboard(Base):
    __tablename__ = "dashboards"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    description = Column(String(1000), nullable=False)
    DashboardType = Column(String(50), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    content = Column(MutableDict.as_mutable(JSONB), nullable=False)
    version = Column(String(20), default="1.0", nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    versions = relationship(
        "DashboardVersion", back_populates="dashboard", cascade="all, delete-orphan"
    )
    workflows = relationship(
        "DashboardWorkflow", back_populates="dashboard", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("idx_dashboard_name_type", "name", "DashboardType"),
        Index("idx_dashboard_active_created", "is_active", "created_at"),
    )


class DashboardVersion(Base):
    __tablename__ = "dashboard_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    dashboard_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dashboards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version = Column(String(20), nullable=False, index=True)
    content = Column(MutableDict.as_mutable(JSONB), nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    dashboard = relationship("Dashboard", back_populates="versions")

    # Indexes for better performance
    __table_args__ = (
        Index("idx_version_dashboard_version", "dashboard_id", "version"),
        Index("idx_version_created", "created_at"),
    )

    def __repr__(self):
        return f"<DashboardVersion(id={self.id}, dashboard_id={self.dashboard_id}, version='{self.version}')>"

"""
class Alerts(Base):
    __tablename__ = "alerts"  # Changed from "dashboard_versions" to match the model name

    alert_id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    alert_name = Column(String(255), nullable=False, index=True)
    description = Column(String(1000), nullable=False)

    # Added missing fields from JSON
    type = Column(String(50), nullable=False, index=True)
    account = Column(String(255), nullable=False, index=True)
    health_score = Column(Integer, nullable=True)  # 42
    stage = Column(String(100), nullable=True)  # "onboarding"
    tier = Column(String(50), nullable=True)  # "Tier 2"
    date_created = Column(DateTime(timezone=True), nullable=False)

    # Renamed to match JSON structure
    details = Column(MutableDict.as_mutable(JSONB), nullable=False)

    # System timestamps
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)
"""

class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)
    description = Column(String)
    status = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    datasets = relationship(
        "AlertDataset", back_populates="task", cascade="all, delete-orphan"
    )
    metrics = relationship(
        "Metric", back_populates="task", cascade="all, delete-orphan"
    )
    conditions = relationship(
        "Condition", back_populates="task", cascade="all, delete-orphan"
    )


class AlertDataset(Base):
    __tablename__ = "alert_dataset"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)
    project_id = Column(String, nullable=False)
    name = Column(String, nullable=False)

    begin_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    time_dimension = Column(String, nullable=True)

    indexes = Column(
        MutableDict.as_mutable(JSONB)
    )  # e.g., {"defaultcolumn": "primaryid", "partitioning": "state", "distinct": True}
    columns = Column(MutableList.as_mutable(JSONB))  # e.g., ["abc", "xyz", "def"]

    task = relationship("Task", back_populates="datasets")


class Metric(Base):
    __tablename__ = "alert_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)

    name = Column(String, nullable=False)
    label = Column(String)
    description = Column(String)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    type = Column(Enum(MetricType, name="metric_type_enum"), nullable=False)
    type_params = Column(
        MutableDict.as_mutable(JSONB)
    )  # e.g., {"measure": "order_total", "group_by": ["city"], ...}

    task = relationship("Task", back_populates="metrics")


class Condition(Base):
    __tablename__ = "conditions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    name = Column(String, unique=True, nullable=False)

    condition_type = Column(
        Enum("threshold", name="condition_type_enum"), nullable=False
    )
    metric_name = Column(String, nullable=False)
    comparison = Column(
        Enum(
            "greaterthan",
            "lessthan",
            "lessthanequal",
            "equals",
            "notequals",
            "contains",
            "notcontains",
            "startswith",
            "endswith",
            "matchesregex",
            "like",
            "anomaly",
            "zscore",
            "percentage_change",
            "isnull",
            "isnotnull",
            "timesince",
            "rateofchange",
            "consecutiveoccurrences",
            name="comparison_enum",
        ),
        nullable=False,
    )

    value = Column(
        MutableDict.as_mutable(JSONB), nullable=False
    )  # e.g., {"type": "number", "value": 5.0, "measuretype": "rolling", "resolution": "monthly"}

    # One-to-one to Alert and Update
    alert = relationship(
        "Alert", back_populates="condition", uselist=False, cascade="all, delete-orphan"
    )
    update = relationship(
        "UpdateAction",
        back_populates="condition",
        uselist=False,
        cascade="all, delete-orphan",
    )

    task = relationship("Task", back_populates="conditions")


class Alert(Base):
    __tablename__ = "alerts"

    # FIXED: Remove parentheses from uuid.uuid4() to make it a function reference
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    condition_id = Column(
        UUID(as_uuid=True), ForeignKey("conditions.id"), nullable=False
    )
    notification_group = Column(String, nullable=False)
    project_id = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    condition = relationship("Condition", back_populates="alert")


class UpdateAction(Base):
    __tablename__ = "update_actions"

    # FIXED: Remove parentheses from uuid.uuid4() to make it a function reference
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    condition_id = Column(
        UUID(as_uuid=True), ForeignKey("conditions.id"), nullable=False
    )
    action = Column(String, nullable=False)  # e.g., "update state"
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    condition = relationship("Condition", back_populates="update")


class Report(Base):
    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    description = Column(String(1000), nullable=False)
    reportType = Column(String(50), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    content = Column(MutableDict.as_mutable(JSONB), nullable=False)
    version = Column(String(20), default="1.0", nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    versions = relationship(
        "ReportVersion", back_populates="report", cascade="all, delete-orphan"
    )
    report_workflows = relationship("ReportWorkflow", back_populates="report")

    # Indexes
    __table_args__ = (Index("idx_report_name_type", "name", "reportType"),)

    def __repr__(self):
        return f"<Report(id={self.id}, name='{self.name}', type='{self.reportType}')>"


class ReportVersion(Base):
    __tablename__ = "report_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    report_id = Column(
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version = Column(String(20), nullable=False, index=True)
    content = Column(MutableDict.as_mutable(JSONB), nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    report = relationship("Report", back_populates="versions")

    # Indexes for better performance
    __table_args__ = (Index("idx_version_report_version", "report_id", "version"),)

    def __repr__(self):
        return f"<ReportVersion(id={self.id}, report_id={self.report_id}, version='{self.version}')>"

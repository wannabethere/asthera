"""
dbt Artifact models — tracks every gold cube produced from a dashboard/report publish.

Each publish event creates a new DbtArtifactVersion. The DbtArtifact is the
long-lived record per workflow; versions chain backwards via previous_version_id.
"""
import enum
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import relationship

from app.models.dbmodels import Base


class ArtifactType(str, enum.Enum):
    DASHBOARD = "dashboard"
    REPORT    = "report"
    CUBE      = "cube"


class DbtArtifactStatus(str, enum.Enum):
    BUILDING   = "building"
    ACTIVE     = "active"
    FAILED     = "failed"
    DEPRECATED = "deprecated"


class DbtRunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED  = "passed"
    FAILED  = "failed"
    SKIPPED = "skipped"   # hash unchanged — identical SQL would be produced


class DbtIntegrationType(str, enum.Enum):
    ASTHERA_UX = "asthera_ux"
    POWERBI    = "powerbi"
    TABLEAU    = "tableau"
    LOOKER     = "looker"
    CUSTOM     = "custom"


class DbtArtifact(Base):
    __tablename__ = "dbt_artifacts"

    id                    = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    artifact_type         = Column(Enum(ArtifactType), nullable=False)

    # FK to whichever workflow type produced this artifact
    dashboard_workflow_id = Column(
        String(36),
        ForeignKey("dashboard_workflows.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    report_workflow_id    = Column(
        String(36),
        ForeignKey("report_workflows.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    model_name            = Column(String(255), nullable=False)
    # SHA-256 of (grain + sorted dimensions + sorted metrics + source_tables).
    # Unchanged hash → SKIPPED, no Airflow trigger fired.
    model_hash            = Column(String(64), nullable=True)

    current_version_id    = Column(String(36), nullable=True)   # denorm pointer to active version
    integration_type      = Column(Enum(DbtIntegrationType), default=DbtIntegrationType.ASTHERA_UX)
    status                = Column(Enum(DbtArtifactStatus), default=DbtArtifactStatus.BUILDING, nullable=False)

    tenant_id             = Column(String(255), nullable=False, index=True)
    created_by            = Column(String(36), nullable=True)
    created_at            = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at            = Column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    versions = relationship(
        "DbtArtifactVersion",
        back_populates="artifact",
        foreign_keys="DbtArtifactVersion.artifact_id",
        order_by="DbtArtifactVersion.version_number",
        lazy="selectin",
    )

    __table_args__ = (
        Index("idx_dbt_artifact_tenant", "tenant_id"),
        Index("idx_dbt_artifact_dashboard_wf", "dashboard_workflow_id"),
        Index("idx_dbt_artifact_report_wf", "report_workflow_id"),
    )


class DbtArtifactVersion(Base):
    __tablename__ = "dbt_artifact_versions"

    id              = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    artifact_id     = Column(
        String(36),
        ForeignKey("dbt_artifacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number  = Column(Integer, nullable=False)   # mirrors dashboard version int

    # S3 path for SQL + yml source files (always internal)
    s3_artifact_path = Column(String(1024), nullable=True)
    dbt_model_sql    = Column(Text, nullable=True)       # populated by Airflow callback
    dbt_schema_yml   = Column(Text, nullable=True)
    cube_yaml        = Column(Text, nullable=True)

    # Gold table location — depends on destination type
    destination_config_id = Column(
        String(36),
        ForeignKey("gold_destination_configs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    destination_type      = Column(String(50), nullable=True)   # denorm for fast reads
    destination_table_uri = Column(String(1024), nullable=True)
    # Delta/Iceberg versioning
    table_snapshot_id     = Column(String(255), nullable=True)
    table_version_number  = Column(Integer, nullable=True)

    # Airflow orchestration
    dag_run_id  = Column(String(255), nullable=True, index=True)
    run_status  = Column(Enum(DbtRunStatus), default=DbtRunStatus.PENDING, nullable=False)
    run_log     = Column(Text, nullable=True)

    # Cube definition extracted at publish time
    grain        = Column(String(20), nullable=True)
    dimensions   = Column(MutableList.as_mutable(JSONB), default=list)
    metrics      = Column(MutableList.as_mutable(JSONB), default=list)
    source_tables = Column(MutableList.as_mutable(JSONB), default=list)

    previous_version_id = Column(String(36), nullable=True)   # backward chain
    is_current          = Column(Boolean, default=True, nullable=False)
    created_at          = Column(DateTime(timezone=True), default=func.now(), nullable=False)

    artifact            = relationship("DbtArtifact", back_populates="versions", foreign_keys=[artifact_id])
    destination_config  = relationship("GoldDestinationConfig", back_populates="dbt_artifact_versions")

    __table_args__ = (
        Index("idx_dbt_version_artifact_current", "artifact_id", "is_current"),
        Index("idx_dbt_version_dag_run", "dag_run_id"),
    )

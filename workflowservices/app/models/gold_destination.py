"""
Gold Destination Config — customer-configured destination for gold tables.

Each tenant can bring their own data warehouse or lake. The DbtArtifactService
reads the tenant's default destination at publish time and passes it to Airflow,
which generates the correct dbt profile on the fly.
"""
import enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import relationship
from sqlalchemy import func

from app.models.dbmodels import Base


class GoldDestinationType(str, enum.Enum):
    INTERNAL_S3  = "internal_s3"   # managed S3 + Iceberg (default)
    CUSTOMER_S3  = "customer_s3"   # tenant's own S3 bucket
    SNOWFLAKE    = "snowflake"
    BIGQUERY     = "bigquery"
    DATABRICKS   = "databricks"    # Delta Lake
    REDSHIFT     = "redshift"
    AZURE_ADLS   = "azure_adls"
    POSTGRES     = "postgres"


class GoldDestinationConfig(Base):
    __tablename__ = "gold_destination_configs"

    id               = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id        = Column(String(255), nullable=False, index=True)
    name             = Column(String(255), nullable=False)
    destination_type = Column(Enum(GoldDestinationType), nullable=False)
    # Encrypted at application layer before storage
    connection_config = Column(MutableDict.as_mutable(JSONB), nullable=False, default=dict)
    is_default       = Column(Boolean, default=False, nullable=False)
    is_active        = Column(Boolean, default=True, nullable=False)
    created_at       = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at       = Column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    dbt_artifact_versions = relationship(
        "DbtArtifactVersion",
        back_populates="destination_config",
        lazy="selectin",
    )

    __table_args__ = (
        Index("idx_gold_dest_tenant_default", "tenant_id", "is_default"),
        Index("idx_gold_dest_tenant_active", "tenant_id", "is_active"),
    )

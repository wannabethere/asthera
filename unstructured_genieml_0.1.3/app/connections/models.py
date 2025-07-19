import uuid
import sqlalchemy
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import func, TIMESTAMP, Text, ForeignKey
from sqlalchemy.orm import relationship

metadata = sqlalchemy.MetaData()

# Data Sources table (for Airbyte integration)
data_sources = sqlalchemy.Table(
    "data_sources",
    metadata,
    sqlalchemy.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    sqlalchemy.Column("connector_name", sqlalchemy.String, nullable=False),
    sqlalchemy.Column("connector_type", sqlalchemy.String, nullable=False),
    sqlalchemy.Column("description", Text, nullable=True),
    sqlalchemy.Column("config", JSONB, nullable=False),
    sqlalchemy.Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
)

# Connections table (for user management and versioning)
connections = sqlalchemy.Table(
    "connections",
    metadata,
    sqlalchemy.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    sqlalchemy.Column("name", sqlalchemy.String, nullable=False),
    sqlalchemy.Column("type", sqlalchemy.String, nullable=False),
    sqlalchemy.Column("description", Text, nullable=True),
    sqlalchemy.Column("settings", JSONB, nullable=False),
    sqlalchemy.Column("source_id", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("user_id", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("role", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("version", sqlalchemy.String, nullable=False, default="1.0"),
    sqlalchemy.Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    sqlalchemy.Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
)
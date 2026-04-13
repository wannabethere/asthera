"""ORM models for data protection (RLS/CLS). Table prefix ds_dp_ — lives in dataservices DB."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from app.schemas.dbmodels import Base


class DSDataProtectionOrgSettings(Base):
    __tablename__ = "ds_dp_org_settings"

    organization_id = Column(UUID(as_uuid=True), primary_key=True)
    config_version = Column(Integer, nullable=False, default=1)
    summary = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DSDataProtectionRole(Base):
    __tablename__ = "ds_dp_roles"
    __table_args__ = (UniqueConstraint("organization_id", "slug", name="uq_ds_dp_roles_org_slug"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ds_dp_org_settings.organization_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    slug = Column(String(128), nullable=False)
    display_name = Column(String(255), nullable=False, default="")
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class DSDataProtectionSessionProperty(Base):
    __tablename__ = "ds_dp_session_properties"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_ds_dp_session_props_org_name"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ds_dp_org_settings.organization_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True, default="")
    value_type = Column(String(32), nullable=False, default="string")
    required = Column(Boolean, nullable=False, default=True)
    example = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class DSDataProtectionRLSPolicy(Base):
    __tablename__ = "ds_dp_rls_policies"
    __table_args__ = (UniqueConstraint("organization_id", "policy_id", name="uq_ds_dp_rls_org_policy"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ds_dp_org_settings.organization_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    policy_id = Column(String(128), nullable=False)
    display_name = Column(String(255), nullable=False, default="")
    model_ref = Column(String(512), nullable=False)
    description = Column(Text, nullable=True, default="")
    predicate_template = Column(Text, nullable=False, default="")
    session_properties_used = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class DSDataProtectionCLSPolicy(Base):
    __tablename__ = "ds_dp_cls_policies"
    __table_args__ = (UniqueConstraint("organization_id", "policy_id", name="uq_ds_dp_cls_org_policy"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ds_dp_org_settings.organization_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    policy_id = Column(String(128), nullable=False)
    display_name = Column(String(255), nullable=False, default="")
    model_ref = Column(String(512), nullable=False, default="")
    protected_columns = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    session_property = Column(String(128), nullable=False, default="")
    operator = Column(String(32), nullable=False, default="in")
    allowed_values = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    restriction_message = Column(Text, nullable=False, default="Restricted by policy")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class DSDataProtectionConnectionPolicy(Base):
    """Binds a data-protection policy configuration to a specific connection (connector).

    Supports inherit+override from org-level policies or fully independent configs.
    """

    __tablename__ = "ds_dp_connection_policies"
    __table_args__ = (
        UniqueConstraint("connection_id", "organization_id", name="uq_ds_dp_conn_org"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connection_id = Column(
        UUID(as_uuid=True),
        ForeignKey("connection_details.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ds_dp_org_settings.organization_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status = Column(String(32), nullable=False, default="draft")  # draft / active / inactive
    inheritance_mode = Column(String(32), nullable=False, default="inherit_override")
    policy_config = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    rls_overrides = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    cls_overrides = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    excluded_policy_ids = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    generated_by = Column(String(32), nullable=False, default="manual")  # agent / manual
    generation_metadata = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

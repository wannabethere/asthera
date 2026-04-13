"""Persistence for generic RLS/CLS configuration (async SQLAlchemy)."""

from __future__ import annotations

import copy
import logging
import os
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.data_protection_api import (
    CLSPolicyDefinition,
    ConnectionPolicyConfig,
    DataProtectionConfig,
    EffectivePolicyPreview,
    RLSPolicyDefinition,
    RoleDefinition,
    SessionPropertyDefinition,
)
from app.schemas.data_protection_models import (
    DSDataProtectionCLSPolicy,
    DSDataProtectionConnectionPolicy,
    DSDataProtectionOrgSettings,
    DSDataProtectionRLSPolicy,
    DSDataProtectionRole,
    DSDataProtectionSessionProperty,
)

logger = logging.getLogger(__name__)


async def load_config(session: AsyncSession, organization_id: UUID) -> DataProtectionConfig:
    header = await session.get(DSDataProtectionOrgSettings, organization_id)
    if header is None:
        return DataProtectionConfig()

    roles = (
        (
            await session.execute(
                select(DSDataProtectionRole)
                .where(
                    DSDataProtectionRole.organization_id == organization_id,
                    DSDataProtectionRole.is_active.is_(True),
                )
                .order_by(DSDataProtectionRole.slug)
            )
        )
        .scalars()
        .all()
    )
    props = (
        (
            await session.execute(
                select(DSDataProtectionSessionProperty)
                .where(DSDataProtectionSessionProperty.organization_id == organization_id)
                .order_by(DSDataProtectionSessionProperty.name)
            )
        )
        .scalars()
        .all()
    )
    rls = (
        (
            await session.execute(
                select(DSDataProtectionRLSPolicy)
                .where(DSDataProtectionRLSPolicy.organization_id == organization_id)
                .order_by(DSDataProtectionRLSPolicy.policy_id)
            )
        )
        .scalars()
        .all()
    )
    cls_rows = (
        (
            await session.execute(
                select(DSDataProtectionCLSPolicy)
                .where(DSDataProtectionCLSPolicy.organization_id == organization_id)
                .order_by(DSDataProtectionCLSPolicy.policy_id)
            )
        )
        .scalars()
        .all()
    )

    return DataProtectionConfig(
        version=header.config_version,
        summary=header.summary or "",
        roles=[
            RoleDefinition(id=r.slug, display_name=r.display_name or r.slug, description=r.description or "")
            for r in roles
        ],
        session_properties=[
            SessionPropertyDefinition(
                name=p.name,
                description=p.description or "",
                value_type=p.value_type or "string",
                required=bool(p.required),
                example=p.example,
            )
            for p in props
        ],
        rls_policies=[
            RLSPolicyDefinition(
                id=x.policy_id,
                display_name=x.display_name or "",
                model_ref=x.model_ref,
                description=x.description or "",
                predicate_template=x.predicate_template or "",
                session_properties_used=list(x.session_properties_used or []),
            )
            for x in rls
        ],
        cls_policies=[
            CLSPolicyDefinition(
                id=x.policy_id,
                display_name=x.display_name or "",
                model_ref=x.model_ref or "",
                protected_columns=list(x.protected_columns or []),
                session_property=x.session_property or "",
                operator=x.operator or "in",
                allowed_values=list(x.allowed_values or []),
                restriction_message=x.restriction_message or "Restricted by policy",
            )
            for x in cls_rows
        ],
    )


async def _delete_org_children(session: AsyncSession, organization_id: UUID) -> None:
    await session.execute(
        delete(DSDataProtectionCLSPolicy).where(DSDataProtectionCLSPolicy.organization_id == organization_id)
    )
    await session.execute(
        delete(DSDataProtectionRLSPolicy).where(DSDataProtectionRLSPolicy.organization_id == organization_id)
    )
    await session.execute(
        delete(DSDataProtectionSessionProperty).where(
            DSDataProtectionSessionProperty.organization_id == organization_id
        )
    )
    await session.execute(delete(DSDataProtectionRole).where(DSDataProtectionRole.organization_id == organization_id))


async def save_config(session: AsyncSession, organization_id: UUID, cfg: DataProtectionConfig) -> None:
    await _delete_org_children(session, organization_id)
    await session.execute(
        delete(DSDataProtectionOrgSettings).where(DSDataProtectionOrgSettings.organization_id == organization_id)
    )
    await session.flush()

    session.add(
        DSDataProtectionOrgSettings(
            organization_id=organization_id,
            config_version=cfg.version,
            summary=cfg.summary or None,
        )
    )
    await session.flush()

    for role in cfg.roles:
        session.add(
            DSDataProtectionRole(
                organization_id=organization_id,
                slug=role.id,
                display_name=role.display_name or role.id,
                description=role.description or None,
                is_active=True,
            )
        )
    for p in cfg.session_properties:
        session.add(
            DSDataProtectionSessionProperty(
                organization_id=organization_id,
                name=p.name,
                description=p.description or "",
                value_type=p.value_type or "string",
                required=p.required,
                example=p.example,
            )
        )
    for x in cfg.rls_policies:
        session.add(
            DSDataProtectionRLSPolicy(
                organization_id=organization_id,
                policy_id=x.id,
                display_name=x.display_name or "",
                model_ref=x.model_ref,
                description=x.description or "",
                predicate_template=x.predicate_template or "",
                session_properties_used=list(x.session_properties_used or []),
            )
        )
    for x in cfg.cls_policies:
        session.add(
            DSDataProtectionCLSPolicy(
                organization_id=organization_id,
                policy_id=x.id,
                display_name=x.display_name or "",
                model_ref=x.model_ref or "",
                protected_columns=list(x.protected_columns or []),
                session_property=x.session_property or "",
                operator=x.operator or "in",
                allowed_values=list(x.allowed_values or []),
                restriction_message=x.restriction_message or "Restricted by policy",
            )
        )


async def clear_organization(session: AsyncSession, organization_id: UUID) -> None:
    await _delete_org_children(session, organization_id)
    await session.execute(
        delete(DSDataProtectionOrgSettings).where(DSDataProtectionOrgSettings.organization_id == organization_id)
    )


async def reload_config(session: AsyncSession, organization_id: UUID) -> DataProtectionConfig:
    """
    If DATA_PROTECTION_SEED_PATH points to a JSON file, load it; otherwise clear org data (empty config).
    """
    path_str = os.getenv("DATA_PROTECTION_SEED_PATH", "").strip()
    if path_str:
        p = Path(path_str).expanduser()
        if p.is_file():
            try:
                cfg = DataProtectionConfig.model_validate_json(p.read_text(encoding="utf-8"))
                await save_config(session, organization_id, cfg)
                await session.commit()
                logger.info("Reloaded data protection from DATA_PROTECTION_SEED_PATH=%s", p)
                return cfg
            except Exception as e:
                logger.error("Invalid seed file %s: %s", p, e)
                raise
    await clear_organization(session, organization_id)
    await session.commit()
    return DataProtectionConfig()


# ---------------------------------------------------------------------------
# Connection-level policy CRUD
# ---------------------------------------------------------------------------


async def save_connection_policies(
    session: AsyncSession,
    connection_id: UUID,
    organization_id: UUID,
    config: DataProtectionConfig,
    *,
    status: str = "draft",
    inheritance_mode: str = "inherit_override",
    rls_overrides: Optional[List[RLSPolicyDefinition]] = None,
    cls_overrides: Optional[List[CLSPolicyDefinition]] = None,
    excluded_policy_ids: Optional[List[str]] = None,
    generated_by: str = "manual",
    generation_metadata: Optional[dict] = None,
) -> DSDataProtectionConnectionPolicy:
    """Upsert a connection-level policy binding."""

    existing = (
        await session.execute(
            select(DSDataProtectionConnectionPolicy).where(
                DSDataProtectionConnectionPolicy.connection_id == connection_id,
                DSDataProtectionConnectionPolicy.organization_id == organization_id,
            )
        )
    ).scalar_one_or_none()

    payload = dict(
        status=status,
        inheritance_mode=inheritance_mode,
        policy_config=config.model_dump(),
        rls_overrides=[o.model_dump() for o in (rls_overrides or [])],
        cls_overrides=[o.model_dump() for o in (cls_overrides or [])],
        excluded_policy_ids=list(excluded_policy_ids or []),
        generated_by=generated_by,
        generation_metadata=generation_metadata or {},
    )

    if existing:
        await session.execute(
            update(DSDataProtectionConnectionPolicy)
            .where(DSDataProtectionConnectionPolicy.id == existing.id)
            .values(**payload)
        )
        await session.flush()
        return existing
    else:
        row = DSDataProtectionConnectionPolicy(
            connection_id=connection_id,
            organization_id=organization_id,
            **payload,
        )
        session.add(row)
        await session.flush()
        return row


async def load_connection_policies(
    session: AsyncSession, connection_id: UUID
) -> Optional[ConnectionPolicyConfig]:
    """Load the policy binding for a connection, or None."""
    row = (
        await session.execute(
            select(DSDataProtectionConnectionPolicy).where(
                DSDataProtectionConnectionPolicy.connection_id == connection_id
            )
        )
    ).scalar_one_or_none()

    if row is None:
        return None

    return ConnectionPolicyConfig(
        connection_id=row.connection_id,
        organization_id=row.organization_id,
        status=row.status,
        inheritance_mode=row.inheritance_mode,
        config=DataProtectionConfig(**(row.policy_config or {})),
        rls_overrides=[RLSPolicyDefinition(**o) for o in (row.rls_overrides or [])],
        cls_overrides=[CLSPolicyDefinition(**o) for o in (row.cls_overrides or [])],
        excluded_policy_ids=list(row.excluded_policy_ids or []),
        generated_by=row.generated_by or "manual",
        generation_metadata=row.generation_metadata or {},
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def activate_connection_policies(
    session: AsyncSession, connection_id: UUID
) -> bool:
    """Transition connection policies from draft to active. Returns True if updated."""
    result = await session.execute(
        update(DSDataProtectionConnectionPolicy)
        .where(
            DSDataProtectionConnectionPolicy.connection_id == connection_id,
            DSDataProtectionConnectionPolicy.status == "draft",
        )
        .values(status="active")
    )
    await session.flush()
    return result.rowcount > 0


async def list_connections_with_policies(
    session: AsyncSession, organization_id: UUID
) -> List[ConnectionPolicyConfig]:
    """List all connection policies for an org."""
    rows = (
        await session.execute(
            select(DSDataProtectionConnectionPolicy)
            .where(DSDataProtectionConnectionPolicy.organization_id == organization_id)
            .order_by(DSDataProtectionConnectionPolicy.created_at)
        )
    ).scalars().all()

    return [
        ConnectionPolicyConfig(
            connection_id=r.connection_id,
            organization_id=r.organization_id,
            status=r.status,
            inheritance_mode=r.inheritance_mode,
            config=DataProtectionConfig(**(r.policy_config or {})),
            rls_overrides=[RLSPolicyDefinition(**o) for o in (r.rls_overrides or [])],
            cls_overrides=[CLSPolicyDefinition(**o) for o in (r.cls_overrides or [])],
            excluded_policy_ids=list(r.excluded_policy_ids or []),
            generated_by=r.generated_by or "manual",
            generation_metadata=r.generation_metadata or {},
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


async def get_effective_policies(
    session: AsyncSession,
    connection_id: UUID,
    organization_id: UUID,
    role: Optional[str] = None,
) -> EffectivePolicyPreview:
    """Merge org-level + connection-level policies with inherit+override logic."""

    org_config = await load_config(session, organization_id)
    conn_cfg = await load_connection_policies(session, connection_id)

    if conn_cfg is None or conn_cfg.inheritance_mode == "independent":
        effective = conn_cfg.config if conn_cfg else DataProtectionConfig()
        return EffectivePolicyPreview(
            connection_id=connection_id,
            organization_id=organization_id,
            role=role,
            effective_config=effective,
        )

    # Inherit + Override
    effective = copy.deepcopy(org_config)
    excluded = set(conn_cfg.excluded_policy_ids)

    # Filter out excluded org policies
    effective.rls_policies = [p for p in effective.rls_policies if p.id not in excluded]
    effective.cls_policies = [p for p in effective.cls_policies if p.id not in excluded]

    # Apply RLS overrides
    override_rls_ids = {p.id for p in conn_cfg.rls_overrides}
    effective.rls_policies = [
        p for p in effective.rls_policies if p.id not in override_rls_ids
    ] + list(conn_cfg.rls_overrides)

    # Apply CLS overrides
    override_cls_ids = {p.id for p in conn_cfg.cls_overrides}
    effective.cls_policies = [
        p for p in effective.cls_policies if p.id not in override_cls_ids
    ] + list(conn_cfg.cls_overrides)

    # Merge connection-specific policies (from config)
    conn_only_rls = {p.id for p in conn_cfg.config.rls_policies}
    conn_only_cls = {p.id for p in conn_cfg.config.cls_policies}
    existing_rls_ids = {p.id for p in effective.rls_policies}
    existing_cls_ids = {p.id for p in effective.cls_policies}

    for p in conn_cfg.config.rls_policies:
        if p.id not in existing_rls_ids:
            effective.rls_policies.append(p)
    for p in conn_cfg.config.cls_policies:
        if p.id not in existing_cls_ids:
            effective.cls_policies.append(p)

    # Merge roles and session properties
    org_role_ids = {r.id for r in effective.roles}
    for r in conn_cfg.config.roles:
        if r.id not in org_role_ids:
            effective.roles.append(r)

    org_prop_names = {p.name for p in effective.session_properties}
    for p in conn_cfg.config.session_properties:
        if p.name not in org_prop_names:
            effective.session_properties.append(p)

    # If role filter is specified, filter CLS to policies that allow this role
    if role:
        effective.cls_policies = [
            p for p in effective.cls_policies
            if not p.allowed_values or role in p.allowed_values
        ]

    inherited_rls = len(org_config.rls_policies) - len(excluded & {p.id for p in org_config.rls_policies})
    inherited_cls = len(org_config.cls_policies) - len(excluded & {p.id for p in org_config.cls_policies})

    return EffectivePolicyPreview(
        connection_id=connection_id,
        organization_id=organization_id,
        role=role,
        effective_config=effective,
        inherited_rls_count=inherited_rls,
        overridden_rls_count=len(override_rls_ids),
        inherited_cls_count=inherited_cls,
        overridden_cls_count=len(override_cls_ids),
    )

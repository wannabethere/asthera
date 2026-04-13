-- Data Services — generic RLS/CLS policy store (ds_dp_*). Run on phenom_genai_dataservices (or your DATABASE_URL DB).

CREATE TABLE IF NOT EXISTS ds_dp_org_settings (
    organization_id UUID PRIMARY KEY,
    config_version INTEGER NOT NULL DEFAULT 1,
    summary TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ds_dp_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES ds_dp_org_settings (organization_id) ON DELETE CASCADE,
    slug VARCHAR(128) NOT NULL,
    display_name VARCHAR(255) NOT NULL DEFAULT '',
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT uq_ds_dp_roles_org_slug UNIQUE (organization_id, slug)
);

CREATE INDEX IF NOT EXISTS ix_ds_dp_roles_organization_id ON ds_dp_roles (organization_id);

CREATE TABLE IF NOT EXISTS ds_dp_session_properties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES ds_dp_org_settings (organization_id) ON DELETE CASCADE,
    name VARCHAR(128) NOT NULL,
    description TEXT DEFAULT '',
    value_type VARCHAR(32) NOT NULL DEFAULT 'string',
    required BOOLEAN NOT NULL DEFAULT TRUE,
    example TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT uq_ds_dp_session_props_org_name UNIQUE (organization_id, name)
);

CREATE INDEX IF NOT EXISTS ix_ds_dp_session_properties_organization_id ON ds_dp_session_properties (organization_id);

CREATE TABLE IF NOT EXISTS ds_dp_rls_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES ds_dp_org_settings (organization_id) ON DELETE CASCADE,
    policy_id VARCHAR(128) NOT NULL,
    display_name VARCHAR(255) NOT NULL DEFAULT '',
    model_ref VARCHAR(512) NOT NULL,
    description TEXT DEFAULT '',
    predicate_template TEXT NOT NULL DEFAULT '',
    session_properties_used JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT uq_ds_dp_rls_org_policy UNIQUE (organization_id, policy_id)
);

CREATE INDEX IF NOT EXISTS ix_ds_dp_rls_policies_organization_id ON ds_dp_rls_policies (organization_id);

CREATE TABLE IF NOT EXISTS ds_dp_cls_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES ds_dp_org_settings (organization_id) ON DELETE CASCADE,
    policy_id VARCHAR(128) NOT NULL,
    display_name VARCHAR(255) NOT NULL DEFAULT '',
    model_ref VARCHAR(512) NOT NULL DEFAULT '',
    protected_columns JSONB NOT NULL DEFAULT '[]'::jsonb,
    session_property VARCHAR(128) NOT NULL DEFAULT '',
    operator VARCHAR(32) NOT NULL DEFAULT 'in',
    allowed_values JSONB NOT NULL DEFAULT '[]'::jsonb,
    restriction_message TEXT NOT NULL DEFAULT 'Restricted by policy',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT uq_ds_dp_cls_org_policy UNIQUE (organization_id, policy_id)
);

CREATE INDEX IF NOT EXISTS ix_ds_dp_cls_policies_organization_id ON ds_dp_cls_policies (organization_id);

-- Migration: add dashboard_templates table and template_id FK to dashboard_workflows

CREATE TABLE IF NOT EXISTS dashboard_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id VARCHAR(255) NOT NULL UNIQUE,   -- compliance skill template ID e.g. "command-center"
    name VARCHAR(255) NOT NULL,
    description VARCHAR(1000),
    template_type VARCHAR(50) NOT NULL DEFAULT 'dashboard',
    category VARCHAR(100),
    complexity VARCHAR(50),
    domains JSON DEFAULT '[]',
    best_for JSON DEFAULT '[]',
    layout JSON NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

ALTER TABLE dashboard_workflows
    ADD COLUMN IF NOT EXISTS template_id UUID REFERENCES dashboard_templates(id) ON DELETE SET NULL;

-- Migration: add missing columns to projects table
-- Run once against the shared database

ALTER TABLE projects
    ADD COLUMN IF NOT EXISTS goals JSONB DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS data_sources JSONB DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS thread_id UUID REFERENCES threads(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS project_metadata JSONB DEFAULT '{}';

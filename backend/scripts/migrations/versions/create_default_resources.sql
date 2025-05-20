-- Migration: Create default resources
-- Description: Creates default team, workspace, project, and role for the application
-- Author: System
-- Date: 2024-03-14

-- First create system user
INSERT INTO users (id, email, username, first_name, last_name, created_at, updated_at, is_active)
VALUES (
    '00000000-0000-0000-0000-000000000000',
    'system@byzi.ai',
    'system',
    'System',
    'User',
    NOW(),
    NOW(),
    true
) ON CONFLICT (id) DO NOTHING;

-- First create the default team
INSERT INTO teams (id, name, description, created_at, updated_at, created_by)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'Default Team',
    'Default team for all users',
    NOW(),
    NOW(),
    '00000000-0000-0000-0000-000000000000'
);

-- Then create the default workspace
INSERT INTO workspaces (id, name, description, team_id, created_at, updated_at)
VALUES (
    '00000000-0000-0000-0000-000000000002',
    'Default Workspace',
    'Default workspace for all users',
    '00000000-0000-0000-0000-000000000001',
    NOW(),
    NOW()
);

-- Create the default project
INSERT INTO projects (id, name, description, workspace_id, created_at, updated_at)
VALUES (
    '00000000-0000-0000-0000-000000000003',
    'Default Project',
    'Default project for all users',
    '00000000-0000-0000-0000-000000000002',
    NOW(),
    NOW()
);

-- Create default role
INSERT INTO roles (id, name, description, created_at, updated_at)
VALUES (
    '00000000-0000-0000-0000-000000000004',
    'user',
    'Default user role',
    NOW(),
    NOW()
);

-- Add system user to workspace access
INSERT INTO workspace_access (workspace_id, user_id, is_admin, can_create, can_delete, created_at, updated_at)
VALUES (
    '00000000-0000-0000-0000-000000000002',
    '00000000-0000-0000-0000-000000000000',
    true,
    true,
    true,
    NOW(),
    NOW()
);

-- Create a rollback function in case we need to revert
CREATE OR REPLACE FUNCTION rollback_default_resources()
RETURNS void AS $$
BEGIN
    -- Delete in reverse order of creation to respect foreign key constraints
    DELETE FROM workspace_access WHERE workspace_id = '00000000-0000-0000-0000-000000000002';
    DELETE FROM projects WHERE id = '00000000-0000-0000-0000-000000000003';
    DELETE FROM workspaces WHERE id = '00000000-0000-0000-0000-000000000002';
    DELETE FROM teams WHERE id = '00000000-0000-0000-0000-000000000001';
    DELETE FROM roles WHERE id = '00000000-0000-0000-0000-000000000004';
    DELETE FROM users WHERE id = '00000000-0000-0000-0000-000000000000';
END;
$$ LANGUAGE plpgsql;

-- Add a comment explaining the rollback function
COMMENT ON FUNCTION rollback_default_resources() IS 'Function to rollback the creation of default resources';

-- Verify the migration
DO $$
BEGIN
    -- Check if system user was created
    IF NOT EXISTS (
        SELECT 1 FROM users WHERE id = '00000000-0000-0000-0000-000000000000'
    ) THEN
        RAISE EXCEPTION 'Migration verification failed: System user was not created';
    END IF;

    -- Check if all resources were created successfully
    IF NOT EXISTS (
        SELECT 1 FROM teams WHERE id = '00000000-0000-0000-0000-000000000001'
    ) THEN
        RAISE EXCEPTION 'Migration verification failed: Default team was not created';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM workspaces WHERE id = '00000000-0000-0000-0000-000000000002'
    ) THEN
        RAISE EXCEPTION 'Migration verification failed: Default workspace was not created';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM projects WHERE id = '00000000-0000-0000-0000-000000000003'
    ) THEN
        RAISE EXCEPTION 'Migration verification failed: Default project was not created';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM roles WHERE id = '00000000-0000-0000-0000-000000000004'
    ) THEN
        RAISE EXCEPTION 'Migration verification failed: Default role was not created';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM workspace_access 
        WHERE workspace_id = '00000000-0000-0000-0000-000000000002'
        AND user_id = '00000000-0000-0000-0000-000000000000'
    ) THEN
        RAISE EXCEPTION 'Migration verification failed: Workspace access was not created';
    END IF;

    RAISE NOTICE 'Migration verification passed successfully';
END $$; 
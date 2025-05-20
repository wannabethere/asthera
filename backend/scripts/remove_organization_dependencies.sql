-- Remove organization_id column from teams if it exists
ALTER TABLE teams DROP COLUMN IF EXISTS organization_id;

-- Remove organization_id column from workspaces if it exists
ALTER TABLE workspaces DROP COLUMN IF EXISTS organization_id;

-- Drop any foreign key constraints that might exist
ALTER TABLE teams 
    DROP CONSTRAINT IF EXISTS teams_organization_id_fkey;

ALTER TABLE workspaces 
    DROP CONSTRAINT IF EXISTS workspaces_organization_id_fkey;

-- Drop any indexes that might exist
DROP INDEX IF EXISTS idx_teams_organization_id;
DROP INDEX IF EXISTS idx_workspaces_organization_id; 
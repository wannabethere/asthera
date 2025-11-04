-- Drop old team_members table if it exists
DROP TABLE IF EXISTS team_members;

-- Rename team_membersh to team_memberships if it exists
ALTER TABLE IF EXISTS team_membersh RENAME TO team_memberships;

-- Modify teams table structure
ALTER TABLE teams
    -- Add missing columns
    ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES users(id),
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true,
    -- Update timestamps to use timezone
    ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE,
    ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE;

-- Update foreign key constraints in team_memberships table
ALTER TABLE team_memberships
    DROP CONSTRAINT IF EXISTS team_memberships_team_id_fkey,
    DROP CONSTRAINT IF EXISTS team_memberships_user_id_fkey,
    ADD CONSTRAINT team_memberships_team_id_fkey 
        FOREIGN KEY (team_id) 
        REFERENCES teams(id) 
        ON DELETE CASCADE,
    ADD CONSTRAINT team_memberships_user_id_fkey 
        FOREIGN KEY (user_id) 
        REFERENCES users(id) 
        ON DELETE CASCADE;

-- Update foreign key constraints in collaboration_requests table
ALTER TABLE collaboration_requests
    DROP CONSTRAINT IF EXISTS collaboration_requests_team_id_fkey,
    DROP CONSTRAINT IF EXISTS collaboration_requests_requester_id_fkey,
    ADD CONSTRAINT collaboration_requests_team_id_fkey 
        FOREIGN KEY (team_id) 
        REFERENCES teams(id) 
        ON DELETE CASCADE,
    ADD CONSTRAINT collaboration_requests_requester_id_fkey 
        FOREIGN KEY (requester_id) 
        REFERENCES users(id) 
        ON DELETE CASCADE;

-- Update foreign key constraints in team_signup_requests table
ALTER TABLE team_signup_requests
    DROP CONSTRAINT IF EXISTS team_signup_requests_team_id_fkey,
    DROP CONSTRAINT IF EXISTS team_signup_requests_user_id_fkey,
    ADD CONSTRAINT team_signup_requests_team_id_fkey 
        FOREIGN KEY (team_id) 
        REFERENCES teams(id) 
        ON DELETE CASCADE,
    ADD CONSTRAINT team_signup_requests_user_id_fkey 
        FOREIGN KEY (user_id) 
        REFERENCES users(id) 
        ON DELETE CASCADE;

-- Update foreign key constraints in team_invites table
ALTER TABLE team_invites
    DROP CONSTRAINT IF EXISTS team_invites_team_id_fkey,
    DROP CONSTRAINT IF EXISTS team_invites_invited_by_fkey,
    ADD CONSTRAINT team_invites_team_id_fkey 
        FOREIGN KEY (team_id) 
        REFERENCES teams(id) 
        ON DELETE CASCADE,
    ADD CONSTRAINT team_invites_invited_by_fkey 
        FOREIGN KEY (invited_by) 
        REFERENCES users(id) 
        ON DELETE CASCADE;

-- Create or update indexes
CREATE INDEX IF NOT EXISTS idx_teams_name ON teams(name);
CREATE INDEX IF NOT EXISTS idx_teams_created_by ON teams(created_by);
CREATE INDEX IF NOT EXISTS idx_teams_owner_id ON teams(owner_id);
CREATE INDEX IF NOT EXISTS idx_team_memberships_team_id ON team_memberships(team_id);
CREATE INDEX IF NOT EXISTS idx_team_memberships_user_id ON team_memberships(user_id);
CREATE INDEX IF NOT EXISTS idx_collaboration_requests_team_id ON collaboration_requests(team_id);
CREATE INDEX IF NOT EXISTS idx_collaboration_requests_requester_id ON collaboration_requests(requester_id);
CREATE INDEX IF NOT EXISTS idx_team_signup_requests_team_id ON team_signup_requests(team_id);
CREATE INDEX IF NOT EXISTS idx_team_signup_requests_user_id ON team_signup_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_team_invites_team_id ON team_invites(team_id);
CREATE INDEX IF NOT EXISTS idx_team_invites_invited_by ON team_invites(invited_by);

-- Add unique constraints if they don't exist
ALTER TABLE team_memberships
    DROP CONSTRAINT IF EXISTS unique_team_membership,
    ADD CONSTRAINT unique_team_membership UNIQUE (team_id, user_id);

ALTER TABLE team_invites
    DROP CONSTRAINT IF EXISTS unique_team_invite,
    ADD CONSTRAINT unique_team_invite UNIQUE (team_id, email); 


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
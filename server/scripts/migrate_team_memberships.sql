-- Drop existing team_memberships table if it exists
DROP TABLE IF EXISTS team_memberships CASCADE;

-- Create new team_memberships table with updated structure
CREATE TABLE team_memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR NOT NULL DEFAULT 'member',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_team_membership UNIQUE (team_id, user_id)
);

-- Add indexes for better query performance
CREATE INDEX idx_team_memberships_team_id ON team_memberships(team_id);
CREATE INDEX idx_team_memberships_user_id ON team_memberships(user_id);

-- Update teams table to make owner_id nullable and add created_by
ALTER TABLE teams 
    ALTER COLUMN owner_id DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;

-- Update foreign key constraints for related tables
ALTER TABLE collaboration_requests
    DROP CONSTRAINT IF EXISTS collaboration_requests_team_id_fkey,
    DROP CONSTRAINT IF EXISTS collaboration_requests_requester_id_fkey,
    ADD CONSTRAINT collaboration_requests_team_id_fkey 
        FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
    ADD CONSTRAINT collaboration_requests_requester_id_fkey 
        FOREIGN KEY (requester_id) REFERENCES users(id) ON DELETE CASCADE;

ALTER TABLE team_signup_requests
    DROP CONSTRAINT IF EXISTS team_signup_requests_team_id_fkey,
    DROP CONSTRAINT IF EXISTS team_signup_requests_user_id_fkey,
    ADD CONSTRAINT team_signup_requests_team_id_fkey 
        FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
    ADD CONSTRAINT team_signup_requests_user_id_fkey 
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

ALTER TABLE team_invites
    DROP CONSTRAINT IF EXISTS team_invites_team_id_fkey,
    DROP CONSTRAINT IF EXISTS team_invites_invited_by_fkey,
    ADD CONSTRAINT team_invites_team_id_fkey 
        FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
    ADD CONSTRAINT team_invites_invited_by_fkey 
        FOREIGN KEY (invited_by) REFERENCES users(id) ON DELETE CASCADE;

-- Add trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_team_memberships_updated_at
    BEFORE UPDATE ON team_memberships
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE team_memberships IS 'Association table for team memberships with role information';
COMMENT ON COLUMN team_memberships.role IS 'Role of the user in the team (e.g., owner, member)';
COMMENT ON COLUMN team_memberships.created_at IS 'Timestamp when the membership was created';
COMMENT ON COLUMN team_memberships.updated_at IS 'Timestamp when the membership was last updated'; 
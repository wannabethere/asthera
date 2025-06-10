-- Add created_by column to workspaces if it doesn't exist
ALTER TABLE workspaces
ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(id) ON DELETE SET NULL;

-- Add role column to workspace_access table
ALTER TABLE workspace_access 
ADD COLUMN IF NOT EXISTS role VARCHAR DEFAULT 'member';

-- Create index on role column for faster queries
CREATE INDEX IF NOT EXISTS idx_workspace_access_role 
ON workspace_access(role);

-- Create index on created_by for faster lookups
CREATE INDEX IF NOT EXISTS idx_workspaces_created_by 
ON workspaces(created_by);

-- Add comment to role column
COMMENT ON COLUMN workspace_access.role IS 'User role in workspace: owner, admin, or member';

-- Add comment to created_by column
COMMENT ON COLUMN workspaces.created_by IS 'User who created the workspace';

-- Update created_by for existing workspaces based on earliest access
UPDATE workspaces w
SET created_by = (
    SELECT user_id 
    FROM workspace_access wa 
    WHERE wa.workspace_id = w.id 
    ORDER BY wa.created_at ASC 
    LIMIT 1
)
WHERE w.created_by IS NULL;



-- Verify the changes
SELECT 
    w.name as workspace_name,
    u.email as user_email,
    wa.role,
    wa.is_admin,
    wa.can_create,
    wa.can_delete
FROM workspaces w
JOIN workspace_access wa ON w.id = wa.workspace_id
JOIN users u ON wa.user_id = u.id
ORDER BY w.name, wa.role; 



-- Update permissions for workspace creators (owners)
UPDATE workspace_access wa
SET 
    role = 'owner',
    is_admin = true,
    can_create = true,
    can_delete = true
FROM workspaces w
WHERE wa.workspace_id = w.id 
AND wa.user_id = w.created_by;

-- Update permissions for team admins
UPDATE workspace_access wa
SET 
    role = 'admin',
    is_admin = true,
    can_create = true,
    can_delete = false
FROM team_memberships tm
WHERE wa.user_id = tm.user_id 
AND tm.role = 'admin'
AND wa.role = 'member';

-- Update permissions for team members
UPDATE workspace_access wa
SET 
    role = 'member',
    is_admin = false,
    can_create = true,
    can_delete = false
FROM team_memberships tm
WHERE wa.user_id = tm.user_id 
AND tm.role = 'member'
AND wa.role = 'member';

-- Add unique constraint if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM pg_constraint 
        WHERE conname = 'unique_workspace_user'
    ) THEN
        ALTER TABLE workspace_access
        ADD CONSTRAINT unique_workspace_user 
        UNIQUE (workspace_id, user_id);
    END IF;
END $$;


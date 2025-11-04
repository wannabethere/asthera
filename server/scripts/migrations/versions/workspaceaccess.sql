CREATE TABLE collaboration_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    requester_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
 
ALTER TABLE workspaces DROP COLUMN team_id;
ALTER TABLE Workspaces ADD COLUMN Team_id UUID DEFAULT NULL;

-- 2. Grant access to all users
-- Workspace access
INSERT INTO workspace_access (workspace_id, user_id, is_admin, can_create, can_delete, created_at)
SELECT
    (SELECT id FROM workspaces WHERE name = 'Default Workspace'),
    u.id,
    false,
    false,
    false,
    NOW()
FROM users u
WHERE NOT EXISTS (
    SELECT 1 FROM workspace_access wa
    WHERE wa.workspace_id = (SELECT id FROM workspaces WHERE name = 'Default Workspace')
      AND wa.user_id = u.id
);
-- Project access
INSERT INTO project_access (project_id, user_id, is_admin, can_create, can_delete, created_at)
SELECT
    (SELECT id FROM projects WHERE name = 'Default Project'),
    u.id,
    false,
    false,
    false,
    NOW()
FROM users u
WHERE NOT EXISTS (
    SELECT 1 FROM project_access pa
    WHERE pa.project_id = (SELECT id FROM projects WHERE name = 'Default Project')
      AND pa.user_id = u.id
);
-- Team membership
INSERT INTO team_memberships (team_id, user_id, role, created_at)
SELECT
    (SELECT id FROM teams WHERE name = 'Default Team'),
    u.id,
    'member',
    NOW()
FROM users u
WHERE NOT EXISTS (
    SELECT 1 FROM team_memberships tm
    WHERE tm.team_id = (SELECT id FROM teams WHERE name = 'Default Team')
      AND tm.user_id = u.id
);


ALTER TABLE thread_messages
ADD COLUMN response jsonb NOT NULL DEFAULT '{}'::jsonb,
ADD COLUMN status varchar DEFAULT '';
-- Add missing permissions for workspace, project, team, and thread management
INSERT INTO permissions (name, description, resource_type, action) VALUES
    ('workspace:read', 'Read workspace', 'workspace', 'read'),
    ('workspace:update', 'Update workspace', 'workspace', 'update'),
    ('workspace:delete', 'Delete workspace', 'workspace', 'delete'),
    ('workspace:manage_members', 'Manage workspace members', 'workspace', 'manage_members'),
    ('workspace:manage_projects', 'Manage workspace projects', 'workspace', 'manage_projects'),
    ('workspace:subscribe', 'Subscribe to workspace', 'workspace', 'subscribe'),
    ('project:create', 'Create project', 'project', 'create'),
    ('project:read', 'Read project', 'project', 'read'),
    ('project:update', 'Update project', 'project', 'update'),
    ('project:delete', 'Delete project', 'project', 'delete'),
    ('project:manage_members', 'Manage project members', 'project', 'manage_members'),
    ('project:manage_threads', 'Manage project threads', 'project', 'manage_threads'),
    ('project:subscribe', 'Subscribe to project', 'project', 'subscribe'),
    ('team:create', 'Create team', 'team', 'create'),
    ('team:read', 'Read team', 'team', 'read'),
    ('team:update', 'Update team', 'team', 'update'),
    ('team:delete', 'Delete team', 'team', 'delete'),
    ('team:manage_members', 'Manage team members', 'team', 'manage_members'),
    ('thread:create', 'Create thread', 'thread', 'create'),
    ('thread:read', 'Read thread', 'thread', 'read'),
    ('thread:update', 'Update thread', 'thread', 'update'),
    ('thread:subscribe', 'Subscribe to thread', 'thread', 'subscribe'),
    ('search:execute', 'Execute search', 'search', 'execute')
ON CONFLICT (name) DO NOTHING;

-- Assign permissions to workspace_admin role
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name = 'workspace_admin' AND p.name IN (
    'workspace:read',
    'workspace:update',
    'workspace:manage_members',
    'workspace:manage_projects',
    'project:create',
    'project:read',
    'project:update',
    'team:create',
    'team:read',
    'team:update'
)
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Assign permissions to project_admin role
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name = 'project_admin' AND p.name IN (
    'project:read',
    'project:update',
    'project:manage_members',
    'project:manage_threads',
    'thread:create',
    'thread:read',
    'thread:update'
)
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Assign permissions to team_admin role
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name = 'team_admin' AND p.name IN (
    'team:read',
    'team:update',
    'team:manage_members'
)
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Assign permissions to authenticated_user role
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name = 'authenticated_user' AND p.name IN (
    'workspace:read',
    'workspace:subscribe',
    'project:read',
    'project:subscribe',
    'team:read',
    'thread:read',
    'thread:create',
    'thread:update',
    'thread:subscribe',
    'search:execute'
)
ON CONFLICT (role_id, permission_id) DO NOTHING; 
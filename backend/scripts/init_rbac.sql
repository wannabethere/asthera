-- Initialize RBAC system with predefined roles and permissions

-- Insert predefined permissions
INSERT INTO permissions (id, name, description) VALUES
    (uuid_generate_v4(), 'workspace:create', 'Create new workspaces'),
    (uuid_generate_v4(), 'workspace:read', 'View workspaces'),
    (uuid_generate_v4(), 'workspace:update', 'Update workspace details'),
    (uuid_generate_v4(), 'workspace:delete', 'Delete workspaces'),
    (uuid_generate_v4(), 'project:create', 'Create new projects'),
    (uuid_generate_v4(), 'project:read', 'View projects'),
    (uuid_generate_v4(), 'project:update', 'Update project details'),
    (uuid_generate_v4(), 'project:delete', 'Delete projects'),
    (uuid_generate_v4(), 'thread:create', 'Create new threads'),
    (uuid_generate_v4(), 'thread:read', 'View threads'),
    (uuid_generate_v4(), 'thread:update', 'Update thread content'),
    (uuid_generate_v4(), 'thread:delete', 'Delete threads')
ON CONFLICT (name) DO NOTHING;

-- Insert predefined roles
INSERT INTO roles (id, name, description) VALUES
    (uuid_generate_v4(), 'superuser', 'Full system access'),
    (uuid_generate_v4(), 'workspace_admin', 'Can manage workspaces and their contents'),
    (uuid_generate_v4(), 'project_admin', 'Can manage projects and their contents'),
    (uuid_generate_v4(), 'user', 'Basic user access')
ON CONFLICT (name) DO NOTHING;

-- Assign permissions to roles
-- Superuser gets all permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT 
    r.id as role_id,
    p.id as permission_id
FROM roles r
CROSS JOIN permissions p
WHERE r.name = 'superuser'
ON CONFLICT DO NOTHING;

-- Workspace admin permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT 
    r.id as role_id,
    p.id as permission_id
FROM roles r
CROSS JOIN permissions p
WHERE r.name = 'workspace_admin'
    AND p.name IN (
        'workspace:create',
        'workspace:read',
        'workspace:update',
        'workspace:delete',
        'project:create',
        'project:read',
        'project:update',
        'project:delete',
        'thread:create',
        'thread:read',
        'thread:update',
        'thread:delete'
    )
ON CONFLICT DO NOTHING;

-- Project admin permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT 
    r.id as role_id,
    p.id as permission_id
FROM roles r
CROSS JOIN permissions p
WHERE r.name = 'project_admin'
    AND p.name IN (
        'project:read',
        'project:update',
        'thread:create',
        'thread:read',
        'thread:update',
        'thread:delete'
    )
ON CONFLICT DO NOTHING;

-- Basic user permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT 
    r.id as role_id,
    p.id as permission_id
FROM roles r
CROSS JOIN permissions p
WHERE r.name = 'user'
    AND p.name IN (
        'workspace:read',
        'project:read',
        'thread:create',
        'thread:read',
        'thread:update'
    )
ON CONFLICT DO NOTHING;

-- Create a default superuser if not exists
WITH new_user AS (
    INSERT INTO users (
        id,
        email,
        username,
        password_hash,
        first_name,
        last_name,
        is_active,
        is_superuser,
        created_at,
        updated_at
    )
    VALUES (
        uuid_generate_v4(),
        'admin@example.com',
        'admin',
        -- Default password: admin123 (hashed with bcrypt)
        '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewYpR1IOBYyqQK.q',
        'Admin',
        'User',
        true,
        true,
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP
    )
    ON CONFLICT (email) DO NOTHING
    RETURNING id
)
-- Assign superuser role to admin user
INSERT INTO user_roles (user_id, role_id)
SELECT 
    nu.id as user_id,
    r.id as role_id
FROM new_user nu
CROSS JOIN roles r
WHERE r.name = 'superuser'
ON CONFLICT DO NOTHING; 
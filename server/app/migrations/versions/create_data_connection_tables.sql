-- Create data_connections table
CREATE TABLE IF NOT EXISTS data_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR NOT NULL,
    description TEXT,
    source_type VARCHAR NOT NULL,
    connection_config JSONB NOT NULL,
    data_definitions JSONB NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Create data_connection_access table
CREATE TABLE IF NOT EXISTS data_connection_access (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    data_connection_id UUID NOT NULL REFERENCES data_connections(id) ON DELETE CASCADE,
    team_id UUID REFERENCES teams(id) ON DELETE CASCADE,
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    access_level VARCHAR NOT NULL CHECK (access_level IN ('read', 'write', 'admin')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT at_least_one_access_target CHECK (
        (team_id IS NOT NULL)::integer + 
        (workspace_id IS NOT NULL)::integer + 
        (user_id IS NOT NULL)::integer = 1
    )
);

-- Create indexes
CREATE INDEX idx_data_connections_created_by ON data_connections(created_by);
CREATE INDEX idx_data_connection_access_connection_id ON data_connection_access(data_connection_id);
CREATE INDEX idx_data_connection_access_team_id ON data_connection_access(team_id);
CREATE INDEX idx_data_connection_access_workspace_id ON data_connection_access(workspace_id);
CREATE INDEX idx_data_connection_access_user_id ON data_connection_access(user_id);

-- Add permissions for data connections
INSERT INTO permissions (name, description) VALUES
    ('data_connection.create', 'Create data connections'),
    ('data_connection.read', 'Read data connections'),
    ('data_connection.update', 'Update data connections'),
    ('data_connection.delete', 'Delete data connections'),
    ('data_connection.access.manage', 'Manage data connection access');

-- Assign permissions to roles
INSERT INTO role_permissions (role_id, permission_id)
SELECT 
    r.id as role_id,
    p.id as permission_id
FROM roles r
CROSS JOIN permissions p
WHERE p.name IN (
    'data_connection.create',
    'data_connection.read',
    'data_connection.update',
    'data_connection.delete',
    'data_connection.access.manage'
)
AND r.name = 'admin';

-- Assign basic permissions to default role
INSERT INTO role_permissions (role_id, permission_id)
SELECT 
    r.id as role_id,
    p.id as permission_id
FROM roles r
CROSS JOIN permissions p
WHERE p.name IN (
    'data_connection.read'
)
AND r.id = '00000000-0000-0000-0000-000000000004'; 
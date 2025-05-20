-- Team Collaboration System Schema
-- This file contains all table creation statements for the team collaboration system with OAuth integration

-- Users table for storing user account information
CREATE TABLE IF NOT EXISTS collaboration_users (
    id VARCHAR(255) PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- Roles table for storing role definitions and permissions
CREATE TABLE IF NOT EXISTS roles (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    permissions JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User roles table for mapping users to global roles
CREATE TABLE IF NOT EXISTS user_roles (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) REFERENCES collaboration_users(id) ON DELETE CASCADE,
    role_id VARCHAR(255) REFERENCES roles(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, role_id)
);

-- Teams table for storing team information
CREATE TABLE IF NOT EXISTS teams (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    owner_id VARCHAR(255) REFERENCES collaboration_users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- Team members table for mapping users to teams
CREATE TABLE IF NOT EXISTS team_members (
    id VARCHAR(255) PRIMARY KEY,
    team_id VARCHAR(255) REFERENCES teams(id) ON DELETE CASCADE,
    user_id VARCHAR(255) REFERENCES collaboration_users(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_id, user_id)
);

-- Team member roles table for assigning roles within teams
CREATE TABLE IF NOT EXISTS team_member_roles (
    id VARCHAR(255) PRIMARY KEY,
    team_member_id VARCHAR(255) REFERENCES team_members(id) ON DELETE CASCADE,
    role_id VARCHAR(255) REFERENCES roles(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_member_id, role_id)
);

-- Sessions table for storing chat sessions
CREATE TABLE IF NOT EXISTS sessions (
    id VARCHAR(255) PRIMARY KEY,
    state JSONB DEFAULT '{}',
    history JSONB DEFAULT '[]',
    recommendations JSONB DEFAULT '{}',
    data_schema JSONB,
    current_agent VARCHAR(50) DEFAULT 'analysis',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id VARCHAR(255) REFERENCES collaboration_users(id) ON DELETE SET NULL,
    metadata JSONB DEFAULT '{}'
);

-- Session metrics table for analytics
CREATE TABLE IF NOT EXISTS session_metrics (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) REFERENCES sessions(id) ON DELETE CASCADE,
    event_type VARCHAR(50),
    event_data JSONB DEFAULT '{}',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Session shares table for sharing sessions with teams
CREATE TABLE IF NOT EXISTS session_shares (
    id VARCHAR(255) PRIMARY KEY,
    session_id VARCHAR(255) REFERENCES sessions(id) ON DELETE CASCADE,
    team_id VARCHAR(255) REFERENCES teams(id) ON DELETE CASCADE,
    permission_level VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, team_id)
);

-- Session comments table for collaboration
CREATE TABLE IF NOT EXISTS session_comments (
    id VARCHAR(255) PRIMARY KEY,
    session_id VARCHAR(255) REFERENCES sessions(id) ON DELETE CASCADE,
    user_id VARCHAR(255) REFERENCES collaboration_users(id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    parent_id VARCHAR(255) REFERENCES session_comments(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- OAuth provider configurations
CREATE TABLE IF NOT EXISTS oauth_provider_configs (
    id VARCHAR(255) PRIMARY KEY,
    provider VARCHAR(50) UNIQUE NOT NULL,
    client_id VARCHAR(255) NOT NULL,
    client_secret TEXT NOT NULL,
    redirect_uri TEXT NOT NULL,
    authorize_url TEXT,
    token_url TEXT,
    userinfo_url TEXT,
    scope TEXT DEFAULT 'openid email profile',
    additional_params JSONB DEFAULT '{}',
    role_claim VARCHAR(50) DEFAULT 'roles',
    group_claim VARCHAR(50) DEFAULT 'groups',
    role_mapping JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- OAuth connections for users
CREATE TABLE IF NOT EXISTS oauth_connections (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) REFERENCES collaboration_users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    provider_user_id VARCHAR(255) NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_info JSONB DEFAULT '{}',
    UNIQUE(provider, provider_user_id)
);

-- OAuth role synchronization settings
CREATE TABLE IF NOT EXISTS oauth_role_sync_settings (
    id VARCHAR(255) PRIMARY KEY,
    enabled BOOLEAN DEFAULT TRUE,
    auto_create_roles BOOLEAN DEFAULT FALSE,
    role_sync_strategy VARCHAR(20) DEFAULT 'merge',
    default_roles JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default roles
INSERT INTO roles (id, name, description, permissions)
VALUES 
    (gen_random_uuid()::VARCHAR, 'Admin', 'Full administrative access', '{"workspace":"admin","chat_session":"admin","project":"admin","team":"admin"}'),
    (gen_random_uuid()::VARCHAR, 'Editor', 'Can edit content', '{"workspace":"write","chat_session":"write","project":"write","team":"read"}'),
    (gen_random_uuid()::VARCHAR, 'Viewer', 'Read-only access', '{"workspace":"read","chat_session":"read","project":"read","team":"read"}'),
    (gen_random_uuid()::VARCHAR, 'User', 'Standard user with basic permissions', '{"workspace":"read","chat_session":"write","project":"read","team":"read"}')
ON CONFLICT (name) DO NOTHING;

-- Insert default OAuth role sync settings
INSERT INTO oauth_role_sync_settings (id, enabled, auto_create_roles, role_sync_strategy, default_roles)
VALUES (gen_random_uuid()::VARCHAR, TRUE, FALSE, 'merge', '["User"]')
ON CONFLICT DO NOTHING;

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_team_members_user_id ON team_members(user_id);
CREATE INDEX IF NOT EXISTS idx_team_members_team_id ON team_members(team_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_user_id ON user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_role_id ON user_roles(role_id);
CREATE INDEX IF NOT EXISTS idx_session_shares_team_id ON session_shares(team_id);
CREATE INDEX IF NOT EXISTS idx_session_shares_session_id ON session_shares(session_id);
CREATE INDEX IF NOT EXISTS idx_oauth_connections_user_id ON oauth_connections(user_id);
CREATE INDEX IF NOT EXISTS idx_oauth_connections_provider ON oauth_connections(provider);
CREATE INDEX IF NOT EXISTS idx_session_comments_session_id ON session_comments(session_id);
CREATE INDEX IF NOT EXISTS idx_session_comments_user_id ON session_comments(user_id);
CREATE INDEX IF NOT EXISTS idx_session_comments_parent_id ON session_comments(parent_id);
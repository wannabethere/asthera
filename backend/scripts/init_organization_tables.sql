-- Create signup status enum type
CREATE TYPE signup_status AS ENUM ('pending', 'approved', 'rejected');

-- Create application_signups table
CREATE TABLE IF NOT EXISTS application_signups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_name VARCHAR NOT NULL,
    contact_email VARCHAR NOT NULL,
    contact_name VARCHAR NOT NULL,
    contact_phone VARCHAR,
    status signup_status DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP WITH TIME ZONE,
    rejected_at TIMESTAMP WITH TIME ZONE,
    rejection_reason TEXT,
    organization_id UUID REFERENCES organizations(id)
);

-- Create organizations table
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR NOT NULL,
    domain VARCHAR NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create organization_info table
CREATE TABLE IF NOT EXISTS organization_info (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    address VARCHAR,
    city VARCHAR,
    state VARCHAR,
    country VARCHAR,
    postal_code VARCHAR,
    phone VARCHAR,
    website VARCHAR,
    industry VARCHAR,
    size VARCHAR,
    description TEXT,
    logo_url VARCHAR,
    additional_info JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create application_configurations table
CREATE TABLE IF NOT EXISTS application_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    config JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_application_signups_organization_id ON application_signups(organization_id);
CREATE INDEX IF NOT EXISTS idx_application_signups_status ON application_signups(status);
CREATE INDEX IF NOT EXISTS idx_organizations_domain ON organizations(domain);
CREATE INDEX IF NOT EXISTS idx_organization_info_organization_id ON organization_info(organization_id);
CREATE INDEX IF NOT EXISTS idx_application_configurations_organization_id ON application_configurations(organization_id);
CREATE INDEX IF NOT EXISTS idx_organization_info_additional_info ON organization_info USING GIN (additional_info);

-- Create updated_at trigger function if it doesn't exist
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_application_signups_updated_at
    BEFORE UPDATE ON application_signups
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_organizations_updated_at
    BEFORE UPDATE ON organizations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_organization_info_updated_at
    BEFORE UPDATE ON organization_info
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_application_configurations_updated_at
    BEFORE UPDATE ON application_configurations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add organization_id to users table if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'users' 
        AND column_name = 'organization_id'
    ) THEN
        ALTER TABLE users ADD COLUMN organization_id UUID REFERENCES organizations(id);
    END IF;
END $$; 
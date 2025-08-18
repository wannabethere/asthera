-- Workflow Services Database Initialization Script
-- This script creates all necessary tables for the workflow services application

-- Enable UUID extension for PostgreSQL
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create custom enum types
CREATE TYPE metric_type_enum AS ENUM (
    'simple', 'ratio', 'percentage', 'count', 'average', 
    'sum', 'min', 'max', 'median', 'rate', 'duration', 'frequency'
);

CREATE TYPE condition_type_enum AS ENUM ('threshold');

CREATE TYPE comparison_enum AS ENUM (
    'greaterthan', 'lessthan', 'lessthanequal', 'equals', 'notequals',
    'contains', 'notcontains', 'startswith', 'endswith', 'matchesregex',
    'like', 'anomaly', 'zscore', 'percentage_change', 'isnull', 'isnotnull',
    'timesince', 'rateofchange', 'consecutiveoccurrences'
);

-- Create dashboards table
CREATE TABLE dashboards (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description VARCHAR(1000) NOT NULL,
    "DashboardType" VARCHAR(50) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    content JSONB NOT NULL,
    version VARCHAR(20) NOT NULL DEFAULT '1.0',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create dashboard_versions table
CREATE TABLE dashboard_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dashboard_id UUID NOT NULL REFERENCES dashboards(id) ON DELETE CASCADE,
    version VARCHAR(20) NOT NULL,
    content JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create tasks table
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR UNIQUE NOT NULL,
    description TEXT,
    status VARCHAR NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create datasets table
CREATE TABLE datasets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id UUID NOT NULL REFERENCES tasks(id),
    project_id VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    begin_date DATE,
    end_date DATE,
    time_dimension VARCHAR,
    indexes JSONB,
    columns JSONB
);

-- Create metrics table
CREATE TABLE metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id UUID NOT NULL REFERENCES tasks(id),
    name VARCHAR NOT NULL,
    label VARCHAR,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    type metric_type_enum NOT NULL,
    type_params JSONB
);

-- Create conditions table
CREATE TABLE conditions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id UUID NOT NULL REFERENCES tasks(id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    name VARCHAR UNIQUE NOT NULL,
    condition_type condition_type_enum NOT NULL,
    metric_name VARCHAR NOT NULL,
    comparison comparison_enum NOT NULL,
    value JSONB NOT NULL
);

-- Create alerts table
CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    condition_id UUID NOT NULL REFERENCES conditions(id),
    notification_group VARCHAR NOT NULL,
    project_id VARCHAR NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create update_actions table
CREATE TABLE update_actions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    condition_id UUID NOT NULL REFERENCES conditions(id),
    action VARCHAR NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create reports table
CREATE TABLE reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description VARCHAR(1000) NOT NULL,
    "reportType" VARCHAR(50) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    content JSONB NOT NULL,
    version VARCHAR(20) NOT NULL DEFAULT '1.0',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create report_versions table
CREATE TABLE report_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    report_id UUID NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    version VARCHAR(20) NOT NULL,
    content JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX idx_dashboard_name_type ON dashboards(name, "DashboardType");
CREATE INDEX idx_dashboard_active_created ON dashboards(is_active, created_at);
CREATE INDEX idx_dashboard_versions_dashboard_version ON dashboard_versions(dashboard_id, version);
CREATE INDEX idx_dashboard_versions_created ON dashboard_versions(created_at);
CREATE INDEX idx_tasks_name ON tasks(name);
CREATE INDEX idx_datasets_task_id ON datasets(task_id);
CREATE INDEX idx_metrics_task_id ON metrics(task_id);
CREATE INDEX idx_conditions_task_id ON conditions(task_id);
CREATE INDEX idx_conditions_name ON conditions(name);
CREATE INDEX idx_alerts_condition_id ON alerts(condition_id);
CREATE INDEX idx_update_actions_condition_id ON update_actions(condition_id);
CREATE INDEX idx_reports_name_type ON reports(name, "reportType");
CREATE INDEX idx_report_versions_report_version ON report_versions(report_id, version);

-- Create unique constraints
ALTER TABLE conditions ADD CONSTRAINT unique_condition_name UNIQUE (name);
ALTER TABLE tasks ADD CONSTRAINT unique_task_name UNIQUE (name);

-- Add foreign key constraints
ALTER TABLE datasets ADD CONSTRAINT fk_datasets_task_id FOREIGN KEY (task_id) REFERENCES tasks(id);
ALTER TABLE metrics ADD CONSTRAINT fk_metrics_task_id FOREIGN KEY (task_id) REFERENCES tasks(id);
ALTER TABLE conditions ADD CONSTRAINT fk_conditions_task_id FOREIGN KEY (task_id) REFERENCES tasks(id);
ALTER TABLE alerts ADD CONSTRAINT fk_alerts_condition_id FOREIGN KEY (condition_id) REFERENCES conditions(id);
ALTER TABLE update_actions ADD CONSTRAINT fk_update_actions_condition_id FOREIGN KEY (condition_id) REFERENCES conditions(id);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at columns
CREATE TRIGGER update_dashboards_updated_at BEFORE UPDATE ON dashboards
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_dashboard_versions_updated_at BEFORE UPDATE ON dashboard_versions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tasks_updated_at BEFORE UPDATE ON tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_metrics_updated_at BEFORE UPDATE ON metrics
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_conditions_updated_at BEFORE UPDATE ON conditions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_alerts_updated_at BEFORE UPDATE ON alerts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_update_actions_updated_at BEFORE UPDATE ON update_actions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_reports_updated_at BEFORE UPDATE ON reports
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_report_versions_updated_at BEFORE UPDATE ON report_versions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert sample data (optional)
-- Uncomment the following lines if you want to insert sample data

/*
-- Sample dashboard
INSERT INTO dashboards (name, description, "DashboardType", content) VALUES 
('Sample Dashboard', 'A sample dashboard for testing', 'analytics', '{"widgets": [], "layout": "grid"}');

-- Sample task
INSERT INTO tasks (name, description, status) VALUES 
('Sample Task', 'A sample task for testing', 'active');

-- Sample report
INSERT INTO reports (name, description, "reportType", content) VALUES 
('Sample Report', 'A sample report for testing', 'monthly', '{"sections": [], "format": "pdf"}');
*/

-- Grant permissions (adjust as needed for your environment)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_user;

COMMENT ON TABLE dashboards IS 'Stores dashboard configurations and metadata';
COMMENT ON TABLE dashboard_versions IS 'Stores version history for dashboards';
COMMENT ON TABLE tasks IS 'Stores workflow tasks and their status';
COMMENT ON TABLE datasets IS 'Stores dataset configurations for tasks';
COMMENT ON TABLE metrics IS 'Stores metric definitions and parameters';
COMMENT ON TABLE conditions IS 'Stores alert conditions and thresholds';
COMMENT ON TABLE alerts IS 'Stores alert configurations and notifications';
COMMENT ON TABLE update_actions IS 'Stores actions to take when conditions are met';
COMMENT ON TABLE reports IS 'Stores report configurations and metadata';
COMMENT ON TABLE report_versions IS 'Stores version history for reports';

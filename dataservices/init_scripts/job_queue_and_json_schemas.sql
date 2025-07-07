-- Job Queue and Project JSON Storage System PostgreSQL Schema
-- Supports background job processing and project JSON data storage

-- Enable UUID extension for unique identifiers
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- JOB QUEUE SYSTEM TABLES
-- ============================================================================

-- Job Queue table - Main job storage
CREATE TABLE job_queue (
    job_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::VARCHAR(36),
    job_type VARCHAR(50) NOT NULL,
    project_id VARCHAR(50) NOT NULL,
    entity_type VARCHAR(100),
    entity_id VARCHAR(36),
    user_id VARCHAR(100),
    session_id VARCHAR(100),
    priority INTEGER DEFAULT 0 NOT NULL,
    retry_count INTEGER DEFAULT 0 NOT NULL,
    max_retries INTEGER DEFAULT 3 NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    result JSONB,
    error TEXT,
    metadata JSONB,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Job Queue Priority Index - For efficient job retrieval
CREATE TABLE job_queue_priority (
    priority INTEGER NOT NULL,
    job_id VARCHAR(36) NOT NULL REFERENCES job_queue(job_id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (priority, job_id)
);

-- Job History table - Track completed/failed jobs
CREATE TABLE job_history (
    history_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::VARCHAR(36),
    job_id VARCHAR(36) NOT NULL REFERENCES job_queue(job_id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL,
    message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- PROJECT JSON STORAGE TABLES
-- ============================================================================

-- Project JSON Store table - Store project JSON data with ChromaDB integration
CREATE TABLE project_json_store (
    store_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::VARCHAR(36),
    project_id VARCHAR(50) NOT NULL,
    json_type VARCHAR(50) NOT NULL,
    chroma_document_id VARCHAR(100) NOT NULL UNIQUE,
    json_content JSONB NOT NULL,
    version VARCHAR(20) DEFAULT '1.0.0',
    is_active BOOLEAN DEFAULT true,
    last_updated_by VARCHAR(100),
    update_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, json_type)
);

-- Project JSON Search Log table - Track search operations
CREATE TABLE project_json_search_log (
    search_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::VARCHAR(36),
    project_id VARCHAR(50) NOT NULL,
    search_query TEXT NOT NULL,
    json_type VARCHAR(50),
    n_results INTEGER DEFAULT 10,
    total_results INTEGER,
    search_duration_ms INTEGER,
    user_id VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Project JSON Update Log table - Track JSON updates
CREATE TABLE project_json_update_log (
    update_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::VARCHAR(36),
    project_id VARCHAR(50) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id VARCHAR(36) NOT NULL,
    json_type VARCHAR(50) NOT NULL,
    updated_by VARCHAR(100) NOT NULL,
    update_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- SQL FUNCTIONS MANAGEMENT TABLES
-- ============================================================================

-- SQL Functions table - Project-level reusable functions
CREATE TABLE sql_functions (
    function_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::VARCHAR(36),
    project_id VARCHAR(50),
    name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200),
    description TEXT,
    function_sql TEXT NOT NULL,
    return_type VARCHAR(50),
    parameters JSONB,
    is_global BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    created_by VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, name) DEFERRABLE
);

-- SQL Function Usage Log table - Track function usage
CREATE TABLE sql_function_usage_log (
    usage_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::VARCHAR(36),
    function_id VARCHAR(36) NOT NULL REFERENCES sql_functions(function_id) ON DELETE CASCADE,
    project_id VARCHAR(50),
    user_id VARCHAR(100),
    execution_time_ms INTEGER,
    success BOOLEAN,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- SQL Function Dependencies table - Track function dependencies
CREATE TABLE sql_function_dependencies (
    dependency_id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::VARCHAR(36),
    function_id VARCHAR(36) NOT NULL REFERENCES sql_functions(function_id) ON DELETE CASCADE,
    dependent_function_id VARCHAR(36) REFERENCES sql_functions(function_id) ON DELETE CASCADE,
    dependency_type VARCHAR(50) NOT NULL, -- 'calls', 'references', 'imports'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- CONSTRAINTS AND CHECKS
-- ============================================================================

-- Job Queue constraints
ALTER TABLE job_queue ADD CONSTRAINT check_job_status 
    CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled', 'retry'));

ALTER TABLE job_queue ADD CONSTRAINT check_job_priority 
    CHECK (priority >= 0 AND priority <= 10);

ALTER TABLE job_queue ADD CONSTRAINT check_retry_count 
    CHECK (retry_count >= 0);

-- Project JSON Store constraints
ALTER TABLE project_json_store ADD CONSTRAINT check_json_type 
    CHECK (json_type IN ('tables', 'metrics', 'views', 'calculated_columns', 'project_summary', 'enums', 'project'));

-- SQL Functions constraints
ALTER TABLE sql_functions ADD CONSTRAINT check_function_name 
    CHECK (name ~ '^[a-zA-Z_][a-zA-Z0-9_]*$');

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Job Queue indexes
CREATE INDEX idx_job_queue_status ON job_queue(status);
CREATE INDEX idx_job_queue_project_id ON job_queue(project_id);
CREATE INDEX idx_job_queue_job_type ON job_queue(job_type);
CREATE INDEX idx_job_queue_created_at ON job_queue(created_at);
CREATE INDEX idx_job_queue_priority_status ON job_queue(priority, status);
CREATE INDEX idx_job_queue_user_id ON job_queue(user_id);
CREATE INDEX idx_job_queue_session_id ON job_queue(session_id);

-- Job Queue Priority indexes
CREATE INDEX idx_job_queue_priority_order ON job_queue_priority(priority, created_at);
CREATE INDEX idx_job_queue_priority_job_id ON job_queue_priority(job_id);

-- Job History indexes
CREATE INDEX idx_job_history_job_id ON job_history(job_id);
CREATE INDEX idx_job_history_status ON job_history(status);
CREATE INDEX idx_job_history_created_at ON job_history(created_at);

-- Project JSON Store indexes
CREATE INDEX idx_project_json_store_project_id ON project_json_store(project_id);
CREATE INDEX idx_project_json_store_type ON project_json_store(json_type);
CREATE INDEX idx_project_json_store_chroma_id ON project_json_store(chroma_document_id);
CREATE INDEX idx_project_json_store_active ON project_json_store(is_active);
CREATE INDEX idx_project_json_store_updated_at ON project_json_store(updated_at);

-- Project JSON Search Log indexes
CREATE INDEX idx_project_json_search_log_project_id ON project_json_search_log(project_id);
CREATE INDEX idx_project_json_search_log_created_at ON project_json_search_log(created_at);
CREATE INDEX idx_project_json_search_log_query ON project_json_search_log USING gin(to_tsvector('english', search_query));

-- Project JSON Update Log indexes
CREATE INDEX idx_project_json_update_log_project_id ON project_json_update_log(project_id);
CREATE INDEX idx_project_json_update_log_entity ON project_json_update_log(entity_type, entity_id);
CREATE INDEX idx_project_json_update_log_created_at ON project_json_update_log(created_at);

-- SQL Functions indexes
CREATE INDEX idx_sql_functions_project_id ON sql_functions(project_id);
CREATE INDEX idx_sql_functions_name ON sql_functions(name);
CREATE INDEX idx_sql_functions_global ON sql_functions(is_global);
CREATE INDEX idx_sql_functions_active ON sql_functions(is_active);
CREATE INDEX idx_sql_functions_created_at ON sql_functions(created_at);

-- SQL Function Usage Log indexes
CREATE INDEX idx_sql_function_usage_log_function_id ON sql_function_usage_log(function_id);
CREATE INDEX idx_sql_function_usage_log_project_id ON sql_function_usage_log(project_id);
CREATE INDEX idx_sql_function_usage_log_created_at ON sql_function_usage_log(created_at);
CREATE INDEX idx_sql_function_usage_log_success ON sql_function_usage_log(success);

-- SQL Function Dependencies indexes
CREATE INDEX idx_sql_function_dependencies_function_id ON sql_function_dependencies(function_id);
CREATE INDEX idx_sql_function_dependencies_dependent ON sql_function_dependencies(dependent_function_id);
CREATE INDEX idx_sql_function_dependencies_type ON sql_function_dependencies(dependency_type);

-- ============================================================================
-- FUNCTIONS AND TRIGGERS
-- ============================================================================

-- Function to update timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to automatically manage job queue priority
CREATE OR REPLACE FUNCTION manage_job_queue_priority()
RETURNS TRIGGER AS $$
BEGIN
    -- When a job is inserted, add it to the priority queue
    IF TG_OP = 'INSERT' THEN
        INSERT INTO job_queue_priority (priority, job_id) 
        VALUES (NEW.priority, NEW.job_id);
    END IF;
    
    -- When a job is updated, update the priority queue
    IF TG_OP = 'UPDATE' THEN
        -- Remove old priority entry
        DELETE FROM job_queue_priority WHERE job_id = NEW.job_id;
        
        -- Add new priority entry if job is still pending
        IF NEW.status = 'pending' THEN
            INSERT INTO job_queue_priority (priority, job_id) 
            VALUES (NEW.priority, NEW.job_id);
        END IF;
    END IF;
    
    -- When a job is deleted, remove from priority queue
    IF TG_OP = 'DELETE' THEN
        DELETE FROM job_queue_priority WHERE job_id = OLD.job_id;
    END IF;
    
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Function to log job status changes
CREATE OR REPLACE FUNCTION log_job_status_change()
RETURNS TRIGGER AS $$
BEGIN
    -- Log status change
    IF TG_OP = 'UPDATE' AND OLD.status != NEW.status THEN
        INSERT INTO job_history (job_id, status, message) 
        VALUES (NEW.job_id, NEW.status, 
                CASE 
                    WHEN NEW.status = 'running' THEN 'Job started'
                    WHEN NEW.status = 'completed' THEN 'Job completed successfully'
                    WHEN NEW.status = 'failed' THEN COALESCE(NEW.error, 'Job failed')
                    WHEN NEW.status = 'cancelled' THEN 'Job cancelled'
                    WHEN NEW.status = 'retry' THEN 'Job queued for retry'
                    ELSE 'Status changed to ' || NEW.status
                END);
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to get next job from queue
CREATE OR REPLACE FUNCTION get_next_job()
RETURNS TABLE(
    job_id VARCHAR(36),
    job_type VARCHAR(50),
    project_id VARCHAR(50),
    entity_type VARCHAR(100),
    entity_id VARCHAR(36),
    user_id VARCHAR(100),
    session_id VARCHAR(100),
    priority INTEGER,
    retry_count INTEGER,
    max_retries INTEGER,
    metadata JSONB
) AS $$
DECLARE
    next_job_id VARCHAR(36);
BEGIN
    -- Get the next job with highest priority (lowest number)
    SELECT jq.job_id INTO next_job_id
    FROM job_queue jq
    JOIN job_queue_priority jqp ON jq.job_id = jqp.job_id
    WHERE jq.status = 'pending'
    ORDER BY jqp.priority ASC, jq.created_at ASC
    LIMIT 1;
    
    -- Return job details
    RETURN QUERY
    SELECT 
        jq.job_id,
        jq.job_type,
        jq.project_id,
        jq.entity_type,
        jq.entity_id,
        jq.user_id,
        jq.session_id,
        jq.priority,
        jq.retry_count,
        jq.max_retries,
        jq.metadata
    FROM job_queue jq
    WHERE jq.job_id = next_job_id;
END;
$$ LANGUAGE plpgsql;

-- Function to get queue statistics
CREATE OR REPLACE FUNCTION get_queue_stats()
RETURNS TABLE(
    queue_length BIGINT,
    status_counts JSONB,
    avg_priority NUMERIC,
    oldest_job_age_minutes INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*) FILTER (WHERE status = 'pending') as queue_length,
        jsonb_object_agg(status, count) as status_counts,
        AVG(priority) FILTER (WHERE status = 'pending') as avg_priority,
        EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - MIN(created_at))) / 60 FILTER (WHERE status = 'pending') as oldest_job_age_minutes
    FROM job_queue
    GROUP BY ();
END;
$$ LANGUAGE plpgsql;

-- Function to cleanup old jobs
CREATE OR REPLACE FUNCTION cleanup_old_jobs(days_to_keep INTEGER DEFAULT 7)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM job_queue 
    WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '1 day' * days_to_keep
    AND status IN ('completed', 'failed', 'cancelled');
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    -- Also cleanup old history records
    DELETE FROM job_history 
    WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '1 day' * days_to_keep;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- CREATE TRIGGERS
-- ============================================================================

-- Triggers for job queue
CREATE TRIGGER trigger_job_queue_priority_management
    AFTER INSERT OR UPDATE OR DELETE ON job_queue
    FOR EACH ROW EXECUTE FUNCTION manage_job_queue_priority();

CREATE TRIGGER trigger_job_status_logging
    AFTER UPDATE ON job_queue
    FOR EACH ROW EXECUTE FUNCTION log_job_status_change();

CREATE TRIGGER update_job_queue_updated_at BEFORE UPDATE ON job_queue
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Triggers for project JSON store
CREATE TRIGGER update_project_json_store_updated_at BEFORE UPDATE ON project_json_store
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Triggers for SQL functions
CREATE TRIGGER update_sql_functions_updated_at BEFORE UPDATE ON sql_functions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- VIEWS FOR EASY QUERYING
-- ============================================================================

-- Job Queue Status View
CREATE VIEW job_queue_status_view AS
SELECT 
    status,
    COUNT(*) as job_count,
    AVG(priority) as avg_priority,
    MIN(created_at) as oldest_job,
    MAX(created_at) as newest_job
FROM job_queue
GROUP BY status;

-- Project JSON Store Status View
CREATE VIEW project_json_store_status_view AS
SELECT 
    project_id,
    json_type,
    is_active,
    version,
    last_updated_by,
    updated_at,
    jsonb_typeof(json_content) as content_type
FROM project_json_store
ORDER BY project_id, json_type;

-- SQL Functions Usage View
CREATE VIEW sql_functions_usage_view AS
SELECT 
    f.function_id,
    f.name,
    f.project_id,
    f.is_global,
    f.is_active,
    COUNT(u.usage_id) as usage_count,
    AVG(u.execution_time_ms) as avg_execution_time,
    COUNT(u.usage_id) FILTER (WHERE u.success = true) as success_count,
    COUNT(u.usage_id) FILTER (WHERE u.success = false) as failure_count
FROM sql_functions f
LEFT JOIN sql_function_usage_log u ON f.function_id = u.function_id
GROUP BY f.function_id, f.name, f.project_id, f.is_global, f.is_active;

-- ============================================================================
-- SAMPLE DATA INSERTION
-- ============================================================================

-- Insert sample global SQL functions
INSERT INTO sql_functions (function_id, name, display_name, description, function_sql, return_type, is_global, created_by) VALUES
(
    uuid_generate_v4()::VARCHAR(36),
    'calculate_percentage',
    'Calculate Percentage',
    'Calculate percentage of a value relative to total',
    'CREATE OR REPLACE FUNCTION calculate_percentage(value NUMERIC, total NUMERIC) RETURNS NUMERIC AS $$ SELECT CASE WHEN total = 0 THEN 0 ELSE (value / total) * 100 END; $$ LANGUAGE sql;',
    'NUMERIC',
    true,
    'system'
),
(
    uuid_generate_v4()::VARCHAR(36),
    'format_currency',
    'Format Currency',
    'Format number as currency with specified decimal places',
    'CREATE OR REPLACE FUNCTION format_currency(amount NUMERIC, decimal_places INTEGER DEFAULT 2) RETURNS TEXT AS $$ SELECT TO_CHAR(amount, ''FM999,999,999.'' || REPEAT(''0'', decimal_places)); $$ LANGUAGE sql;',
    'TEXT',
    true,
    'system'
);

-- ============================================================================
-- GRANTS AND PERMISSIONS (if using role-based access)
-- ============================================================================

-- Example grants (uncomment and modify as needed)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON job_queue TO job_worker_role;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON project_json_store TO api_role;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON sql_functions TO developer_role;
-- GRANT EXECUTE ON FUNCTION get_next_job() TO job_worker_role;
-- GRANT EXECUTE ON FUNCTION get_queue_stats() TO api_role; 
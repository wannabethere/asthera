-- Project Management System PostgreSQL Schema with Comprehensive Versioning
-- Automatic project version updates when any related entity is modified

-- Enable UUID extension for unique identifiers
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- CORE PROJECT STRUCTURE WITH VERSIONING
-- ============================================================================

-- Projects table - Main project entity with semantic versioning
CREATE TABLE projects (
    project_id VARCHAR(50) PRIMARY KEY,
    display_name VARCHAR(200) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'archived')),
    -- Versioning fields
    major_version INTEGER DEFAULT 1 NOT NULL,
    minor_version INTEGER DEFAULT 0 NOT NULL,
    patch_version INTEGER DEFAULT 0 NOT NULL,
    version_string VARCHAR(20) GENERATED ALWAYS AS (major_version || '.' || minor_version || '.' || patch_version) STORED,
    last_modified_by VARCHAR(100),
    last_modified_entity VARCHAR(100), -- tracks which entity type caused the last version update
    last_modified_entity_id UUID, -- tracks which specific entity caused the last version update
    version_locked BOOLEAN DEFAULT false, -- prevents modifications when true
    metadata JSONB
);

-- Project Version History - Track all version changes
CREATE TABLE project_version_history (
    version_history_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id VARCHAR(50) NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    old_version VARCHAR(20),
    new_version VARCHAR(20),
    change_type VARCHAR(20) NOT NULL, -- 'major', 'minor', 'patch'
    triggered_by_entity VARCHAR(100) NOT NULL,
    triggered_by_entity_id UUID,
    triggered_by_user VARCHAR(100),
    change_description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Datasets table - Collections of tables within a project
CREATE TABLE datasets (
    dataset_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id VARCHAR(50) NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200),
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Entity versioning
    entity_version INTEGER DEFAULT 1 NOT NULL,
    modified_by VARCHAR(100),
    metadata JSONB,
    UNIQUE(project_id, name)
);

-- Tables table - Individual data tables with descriptions
CREATE TABLE tables (
    table_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dataset_id UUID REFERENCES datasets(dataset_id) ON DELETE CASCADE,
    project_id VARCHAR(50) NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200),
    description TEXT,
    mdl_file VARCHAR(200),
    ddl_file VARCHAR(200),
    table_type VARCHAR(20) DEFAULT 'table' CHECK (table_type IN ('table', 'view', 'materialized_view')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Entity versioning
    entity_version INTEGER DEFAULT 1 NOT NULL,
    modified_by VARCHAR(100),
    metadata JSONB,
    UNIQUE(project_id, name)
);

-- Columns table - Table columns with comprehensive metadata
CREATE TABLE columns (
    column_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    table_id UUID NOT NULL REFERENCES tables(table_id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200),
    description TEXT,
    column_type VARCHAR(20) NOT NULL DEFAULT 'column' CHECK (column_type IN ('column', 'calculated_column')),
    data_type VARCHAR(50),
    usage_type VARCHAR(50), -- dimension, measure, attribute, etc.
    is_nullable BOOLEAN DEFAULT true,
    is_primary_key BOOLEAN DEFAULT false,
    is_foreign_key BOOLEAN DEFAULT false,
    default_value TEXT,
    ordinal_position INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Entity versioning
    entity_version INTEGER DEFAULT 1 NOT NULL,
    modified_by VARCHAR(100),
    metadata JSONB,
    UNIQUE(table_id, name)
);

-- ============================================================================
-- CALCULATED COLUMNS AND FUNCTIONS WITH VERSIONING
-- ============================================================================

-- SQL Functions table - Project-level reusable functions
CREATE TABLE sql_functions (
    function_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id VARCHAR(50) NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200),
    description TEXT,
    function_sql TEXT NOT NULL,
    return_type VARCHAR(50),
    parameters JSONB, -- Array of parameter definitions
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Entity versioning
    entity_version INTEGER DEFAULT 1 NOT NULL,
    modified_by VARCHAR(100),
    UNIQUE(project_id, name)
);

-- Calculated Columns table - Special columns with associated functions
CREATE TABLE calculated_columns (
    calculated_column_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    column_id UUID NOT NULL REFERENCES columns(column_id) ON DELETE CASCADE,
    calculation_sql TEXT NOT NULL,
    function_id UUID REFERENCES sql_functions(function_id),
    dependencies JSONB, -- Array of column/table dependencies
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Entity versioning
    entity_version INTEGER DEFAULT 1 NOT NULL,
    modified_by VARCHAR(100)
);

-- ============================================================================
-- METRICS AND VIEWS WITH VERSIONING
-- ============================================================================

-- Metrics table - Table-level metrics and KPIs
CREATE TABLE metrics (
    metric_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    table_id UUID NOT NULL REFERENCES tables(table_id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200),
    description TEXT,
    metric_sql TEXT NOT NULL,
    metric_type VARCHAR(50), -- count, sum, avg, custom, etc.
    aggregation_type VARCHAR(50),
    format_string VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Entity versioning
    entity_version INTEGER DEFAULT 1 NOT NULL,
    modified_by VARCHAR(100),
    metadata JSONB,
    UNIQUE(table_id, name)
);

-- Views table - Table views and perspectives
CREATE TABLE views (
    view_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    table_id UUID NOT NULL REFERENCES tables(table_id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200),
    description TEXT,
    view_sql TEXT NOT NULL,
    view_type VARCHAR(50), -- filtered, aggregated, joined, etc.
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Entity versioning
    entity_version INTEGER DEFAULT 1 NOT NULL,
    modified_by VARCHAR(100),
    metadata JSONB,
    UNIQUE(table_id, name)
);

-- ============================================================================
-- RELATIONSHIPS WITH VERSIONING
-- ============================================================================

-- Relationships table - Define relationships between tables/datasets
CREATE TABLE relationships (
    relationship_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id VARCHAR(50) NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    name VARCHAR(100),
    relationship_type VARCHAR(50) NOT NULL, -- one_to_one, one_to_many, many_to_many
    from_table_id UUID NOT NULL REFERENCES tables(table_id) ON DELETE CASCADE,
    to_table_id UUID NOT NULL REFERENCES tables(table_id) ON DELETE CASCADE,
    from_column_id UUID REFERENCES columns(column_id),
    to_column_id UUID REFERENCES columns(column_id),
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Entity versioning
    entity_version INTEGER DEFAULT 1 NOT NULL,
    modified_by VARCHAR(100),
    metadata JSONB
);

-- ============================================================================
-- KNOWLEDGE BASE AND EXAMPLES WITH VERSIONING
-- ============================================================================

-- Instructions table - Each instruction item as a row (from instructions.json)
CREATE TABLE instructions (
    instruction_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id VARCHAR(50) NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    instructions TEXT NOT NULL,
    sql_query TEXT NOT NULL,
    chain_of_thought TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Entity versioning
    entity_version INTEGER DEFAULT 1 NOT NULL,
    modified_by VARCHAR(100),
    metadata JSONB
);

-- Examples table - Each SQL pair item as a row (from sql_pairs.json)
CREATE TABLE examples (
    example_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id VARCHAR(50) NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    sql_query TEXT NOT NULL,
    context TEXT,
    document_reference VARCHAR(200),
    instructions TEXT,
    categories JSONB, -- Array of category strings
    samples JSONB, -- Array of sample data
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Entity versioning
    entity_version INTEGER DEFAULT 1 NOT NULL,
    modified_by VARCHAR(100),
    metadata JSONB
);

-- Knowledge Base table - Project knowledge base entries
CREATE TABLE knowledge_base (
    kb_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id VARCHAR(50) NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200),
    description TEXT,
    file_path VARCHAR(500),
    content_type VARCHAR(50),
    content TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Entity versioning
    entity_version INTEGER DEFAULT 1 NOT NULL,
    modified_by VARCHAR(100),
    metadata JSONB,
    UNIQUE(project_id, name)
);

-- ============================================================================
-- HISTORY AND AUDIT WITH VERSIONING
-- ============================================================================

-- Project History table - Track changes and versions
CREATE TABLE project_histories (
    history_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id VARCHAR(50) NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    table_id UUID REFERENCES tables(table_id),
    entity_type VARCHAR(50) NOT NULL, -- project, table, column, metric, etc.
    entity_id UUID,
    action VARCHAR(20) NOT NULL, -- create, update, delete
    old_values JSONB,
    new_values JSONB,
    old_entity_version INTEGER,
    new_entity_version INTEGER,
    changed_by VARCHAR(100),
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    change_description TEXT,
    project_version_before VARCHAR(20),
    project_version_after VARCHAR(20)
);

-- ============================================================================
-- VERSIONING FUNCTIONS AND TRIGGERS
-- ============================================================================

-- Function to increment project version based on change type
CREATE OR REPLACE FUNCTION increment_project_version(
    p_project_id VARCHAR(50),
    p_change_type VARCHAR(20), -- 'major', 'minor', 'patch'
    p_entity_type VARCHAR(100),
    p_entity_id UUID,
    p_modified_by VARCHAR(100),
    p_change_description TEXT DEFAULT NULL
)
RETURNS VARCHAR(20) AS $$
DECLARE
    current_major INTEGER;
    current_minor INTEGER;
    current_patch INTEGER;
    old_version VARCHAR(20);
    new_version VARCHAR(20);
    version_locked BOOLEAN;
BEGIN
    -- Check if project version is locked
    SELECT major_version, minor_version, patch_version, version_string, version_locked
    INTO current_major, current_minor, current_patch, old_version, version_locked
    FROM projects 
    WHERE project_id = p_project_id;
    
    -- Prevent changes if version is locked
    IF version_locked THEN
        RAISE EXCEPTION 'Project version is locked. Cannot modify project_id: %', p_project_id;
    END IF;
    
    -- Increment version based on change type
    CASE p_change_type
        WHEN 'major' THEN
            current_major := current_major + 1;
            current_minor := 0;
            current_patch := 0;
        WHEN 'minor' THEN
            current_minor := current_minor + 1;
            current_patch := 0;
        WHEN 'patch' THEN
            current_patch := current_patch + 1;
        ELSE
            RAISE EXCEPTION 'Invalid change_type: %. Must be major, minor, or patch', p_change_type;
    END CASE;
    
    new_version := current_major || '.' || current_minor || '.' || current_patch;
    
    -- Update project version
    UPDATE projects 
    SET 
        major_version = current_major,
        minor_version = current_minor,
        patch_version = current_patch,
        updated_at = CURRENT_TIMESTAMP,
        last_modified_by = p_modified_by,
        last_modified_entity = p_entity_type,
        last_modified_entity_id = p_entity_id
    WHERE project_id = p_project_id;
    
    -- Record version history
    INSERT INTO project_version_history (
        project_id, old_version, new_version, change_type,
        triggered_by_entity, triggered_by_entity_id, triggered_by_user, change_description
    ) VALUES (
        p_project_id, old_version, new_version, p_change_type,
        p_entity_type, p_entity_id, p_modified_by, p_change_description
    );
    
    RETURN new_version;
END;
$$ LANGUAGE plpgsql;

-- Function to determine change type based on entity and modification
CREATE OR REPLACE FUNCTION determine_change_type(
    p_entity_type VARCHAR(100),
    p_action VARCHAR(20),
    p_old_values JSONB DEFAULT NULL,
    p_new_values JSONB DEFAULT NULL
)
RETURNS VARCHAR(20) AS $$
BEGIN
    -- Major version changes (breaking changes)
    IF p_action = 'delete' OR 
       p_entity_type IN ('tables', 'columns', 'relationships') OR
       (p_entity_type = 'sql_functions' AND p_action IN ('update', 'delete')) OR
       (p_entity_type = 'calculated_columns' AND p_action IN ('update', 'delete')) THEN
        RETURN 'major';
    END IF;
    
    -- Minor version changes (new features, non-breaking changes)
    IF p_action = 'create' OR
       p_entity_type IN ('metrics', 'views', 'instructions', 'examples', 'knowledge_base') THEN
        RETURN 'minor';
    END IF;
    
    -- Patch version changes (updates, fixes)
    IF p_action = 'update' THEN
        RETURN 'patch';
    END IF;
    
    -- Default to patch for any other changes
    RETURN 'patch';
END;
$$ LANGUAGE plpgsql;

-- Generic trigger function for version updates
CREATE OR REPLACE FUNCTION trigger_project_version_update()
RETURNS TRIGGER AS $$
DECLARE
    project_id_val VARCHAR(50);
    entity_type_val VARCHAR(100);
    entity_id_val UUID;
    change_type_val VARCHAR(20);
    modified_by_val VARCHAR(100);
    old_values JSONB;
    new_values JSONB;
    action_val VARCHAR(20);
BEGIN
    -- Determine action
    IF TG_OP = 'INSERT' THEN
        action_val := 'create';
        new_values := to_jsonb(NEW);
        old_values := NULL;
    ELSIF TG_OP = 'UPDATE' THEN
        action_val := 'update';
        new_values := to_jsonb(NEW);
        old_values := to_jsonb(OLD);
    ELSIF TG_OP = 'DELETE' THEN
        action_val := 'delete';
        new_values := NULL;
        old_values := to_jsonb(OLD);
    END IF;
    
    -- Get project_id and entity info based on table
    entity_type_val := TG_TABLE_NAME;
    
    CASE TG_TABLE_NAME
        WHEN 'datasets' THEN
            project_id_val := COALESCE(NEW.project_id, OLD.project_id);
            entity_id_val := COALESCE(NEW.dataset_id, OLD.dataset_id);
            modified_by_val := COALESCE(NEW.modified_by, OLD.modified_by);
        WHEN 'tables' THEN
            project_id_val := COALESCE(NEW.project_id, OLD.project_id);
            entity_id_val := COALESCE(NEW.table_id, OLD.table_id);
            modified_by_val := COALESCE(NEW.modified_by, OLD.modified_by);
        WHEN 'columns' THEN
            -- Get project_id through table
            SELECT t.project_id INTO project_id_val 
            FROM tables t 
            WHERE t.table_id = COALESCE(NEW.table_id, OLD.table_id);
            entity_id_val := COALESCE(NEW.column_id, OLD.column_id);
            modified_by_val := COALESCE(NEW.modified_by, OLD.modified_by);
        WHEN 'sql_functions' THEN
            project_id_val := COALESCE(NEW.project_id, OLD.project_id);
            entity_id_val := COALESCE(NEW.function_id, OLD.function_id);
            modified_by_val := COALESCE(NEW.modified_by, OLD.modified_by);
        WHEN 'calculated_columns' THEN
            -- Get project_id through column and table
            SELECT t.project_id INTO project_id_val 
            FROM tables t 
            JOIN columns c ON t.table_id = c.table_id
            WHERE c.column_id = COALESCE(NEW.column_id, OLD.column_id);
            entity_id_val := COALESCE(NEW.calculated_column_id, OLD.calculated_column_id);
            modified_by_val := COALESCE(NEW.modified_by, OLD.modified_by);
        WHEN 'metrics' THEN
            -- Get project_id through table
            SELECT t.project_id INTO project_id_val 
            FROM tables t 
            WHERE t.table_id = COALESCE(NEW.table_id, OLD.table_id);
            entity_id_val := COALESCE(NEW.metric_id, OLD.metric_id);
            modified_by_val := COALESCE(NEW.modified_by, OLD.modified_by);
        WHEN 'views' THEN
            -- Get project_id through table
            SELECT t.project_id INTO project_id_val 
            FROM tables t 
            WHERE t.table_id = COALESCE(NEW.table_id, OLD.table_id);
            entity_id_val := COALESCE(NEW.view_id, OLD.view_id);
            modified_by_val := COALESCE(NEW.modified_by, OLD.modified_by);
        WHEN 'relationships' THEN
            project_id_val := COALESCE(NEW.project_id, OLD.project_id);
            entity_id_val := COALESCE(NEW.relationship_id, OLD.relationship_id);
            modified_by_val := COALESCE(NEW.modified_by, OLD.modified_by);
        WHEN 'instructions' THEN
            project_id_val := COALESCE(NEW.project_id, OLD.project_id);
            entity_id_val := COALESCE(NEW.instruction_id, OLD.instruction_id);
            modified_by_val := COALESCE(NEW.modified_by, OLD.modified_by);
        WHEN 'examples' THEN
            project_id_val := COALESCE(NEW.project_id, OLD.project_id);
            entity_id_val := COALESCE(NEW.example_id, OLD.example_id);
            modified_by_val := COALESCE(NEW.modified_by, OLD.modified_by);
        WHEN 'knowledge_base' THEN
            project_id_val := COALESCE(NEW.project_id, OLD.project_id);
            entity_id_val := COALESCE(NEW.kb_id, OLD.kb_id);
            modified_by_val := COALESCE(NEW.modified_by, OLD.modified_by);
        ELSE
            -- Skip version update for unknown tables
            RETURN COALESCE(NEW, OLD);
    END CASE;
    
    -- Skip if no project_id found or if it's the projects table itself
    IF project_id_val IS NULL OR TG_TABLE_NAME = 'projects' THEN
        RETURN COALESCE(NEW, OLD);
    END IF;
    
    -- Determine change type
    change_type_val := determine_change_type(entity_type_val, action_val, old_values, new_values);
    
    -- Update entity version for UPDATE operations
    IF TG_OP = 'UPDATE' AND TG_TABLE_NAME != 'projects' THEN
        CASE TG_TABLE_NAME
            WHEN 'datasets' THEN NEW.entity_version := OLD.entity_version + 1;
            WHEN 'tables' THEN NEW.entity_version := OLD.entity_version + 1;
            WHEN 'columns' THEN NEW.entity_version := OLD.entity_version + 1;
            WHEN 'sql_functions' THEN NEW.entity_version := OLD.entity_version + 1;
            WHEN 'calculated_columns' THEN NEW.entity_version := OLD.entity_version + 1;
            WHEN 'metrics' THEN NEW.entity_version := OLD.entity_version + 1;
            WHEN 'views' THEN NEW.entity_version := OLD.entity_version + 1;
            WHEN 'relationships' THEN NEW.entity_version := OLD.entity_version + 1;
            WHEN 'instructions' THEN NEW.entity_version := OLD.entity_version + 1;
            WHEN 'examples' THEN NEW.entity_version := OLD.entity_version + 1;
            WHEN 'knowledge_base' THEN NEW.entity_version := OLD.entity_version + 1;
        END CASE;
    END IF;
    
    -- Update project version
    PERFORM increment_project_version(
        project_id_val, 
        change_type_val, 
        entity_type_val, 
        entity_id_val, 
        modified_by_val,
        'Triggered by ' || action_val || ' on ' || entity_type_val
    );
    
    -- Record in project history
    INSERT INTO project_histories (
        project_id, entity_type, entity_id, action,
        old_values, new_values, 
        old_entity_version, new_entity_version,
        changed_by, change_description
    ) VALUES (
        project_id_val, entity_type_val, entity_id_val, action_val,
        old_values, new_values,
        CASE WHEN OLD IS NOT NULL THEN 
            CASE TG_TABLE_NAME
                WHEN 'datasets' THEN OLD.entity_version
                WHEN 'tables' THEN OLD.entity_version
                WHEN 'columns' THEN OLD.entity_version
                WHEN 'sql_functions' THEN OLD.entity_version
                WHEN 'calculated_columns' THEN OLD.entity_version
                WHEN 'metrics' THEN OLD.entity_version
                WHEN 'views' THEN OLD.entity_version
                WHEN 'relationships' THEN OLD.entity_version
                WHEN 'instructions' THEN OLD.entity_version
                WHEN 'examples' THEN OLD.entity_version
                WHEN 'knowledge_base' THEN OLD.entity_version
            END
        END,
        CASE WHEN NEW IS NOT NULL THEN 
            CASE TG_TABLE_NAME
                WHEN 'datasets' THEN NEW.entity_version
                WHEN 'tables' THEN NEW.entity_version
                WHEN 'columns' THEN NEW.entity_version
                WHEN 'sql_functions' THEN NEW.entity_version
                WHEN 'calculated_columns' THEN NEW.entity_version
                WHEN 'metrics' THEN NEW.entity_version
                WHEN 'views' THEN NEW.entity_version
                WHEN 'relationships' THEN NEW.entity_version
                WHEN 'instructions' THEN NEW.entity_version
                WHEN 'examples' THEN NEW.entity_version
                WHEN 'knowledge_base' THEN NEW.entity_version
            END
        END,
        modified_by_val,
        action_val || ' operation on ' || entity_type_val
    );
    
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Function to update timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- CREATE TRIGGERS FOR AUTOMATIC VERSIONING
-- ============================================================================

-- Triggers for project version updates
CREATE TRIGGER trigger_datasets_version_update
    AFTER INSERT OR UPDATE OR DELETE ON datasets
    FOR EACH ROW EXECUTE FUNCTION trigger_project_version_update();

CREATE TRIGGER trigger_tables_version_update
    AFTER INSERT OR UPDATE OR DELETE ON tables
    FOR EACH ROW EXECUTE FUNCTION trigger_project_version_update();

CREATE TRIGGER trigger_columns_version_update
    AFTER INSERT OR UPDATE OR DELETE ON columns
    FOR EACH ROW EXECUTE FUNCTION trigger_project_version_update();

CREATE TRIGGER trigger_sql_functions_version_update
    AFTER INSERT OR UPDATE OR DELETE ON sql_functions
    FOR EACH ROW EXECUTE FUNCTION trigger_project_version_update();

CREATE TRIGGER trigger_calculated_columns_version_update
    AFTER INSERT OR UPDATE OR DELETE ON calculated_columns
    FOR EACH ROW EXECUTE FUNCTION trigger_project_version_update();

CREATE TRIGGER trigger_metrics_version_update
    AFTER INSERT OR UPDATE OR DELETE ON metrics
    FOR EACH ROW EXECUTE FUNCTION trigger_project_version_update();

CREATE TRIGGER trigger_views_version_update
    AFTER INSERT OR UPDATE OR DELETE ON views
    FOR EACH ROW EXECUTE FUNCTION trigger_project_version_update();

CREATE TRIGGER trigger_relationships_version_update
    AFTER INSERT OR UPDATE OR DELETE ON relationships
    FOR EACH ROW EXECUTE FUNCTION trigger_project_version_update();

CREATE TRIGGER trigger_instructions_version_update
    AFTER INSERT OR UPDATE OR DELETE ON instructions
    FOR EACH ROW EXECUTE FUNCTION trigger_project_version_update();

CREATE TRIGGER trigger_examples_version_update
    AFTER INSERT OR UPDATE OR DELETE ON examples
    FOR EACH ROW EXECUTE FUNCTION trigger_project_version_update();

CREATE TRIGGER trigger_knowledge_base_version_update
    AFTER INSERT OR UPDATE OR DELETE ON knowledge_base
    FOR EACH ROW EXECUTE FUNCTION trigger_project_version_update();

-- Triggers for updated_at columns
CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_datasets_updated_at BEFORE UPDATE ON datasets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tables_updated_at BEFORE UPDATE ON tables
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_columns_updated_at BEFORE UPDATE ON columns
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- INSIGHTS VIEW WITH VERSIONING INFORMATION
-- ============================================================================

-- Enhanced insights view with versioning data
CREATE VIEW insights_view AS
SELECT 
    p.project_id,
    p.display_name as project_name,
    p.description as project_description,
    p.status as project_status,
    p.version_string as current_version,
    p.last_modified_entity,
    p.last_modified_by,
    p.version_locked,
    p.created_at as project_created_at,
    
    -- Dataset summary
    COUNT(DISTINCT d.dataset_id) as total_datasets,
    
    -- Table summary
    COUNT(DISTINCT t.table_id) as total_tables,
    COUNT(DISTINCT CASE WHEN t.table_type = 'table' THEN t.table_id END) as physical_tables,
    COUNT(DISTINCT CASE WHEN t.table_type = 'view' THEN t.table_id END) as views,
    
    -- Column summary
    COUNT(DISTINCT c.column_id) as total_columns,
    COUNT(DISTINCT CASE WHEN c.column_type = 'calculated_column' THEN c.column_id END) as calculated_columns,
    
    -- Metrics and relationships
    COUNT(DISTINCT m.metric_id) as total_metrics,
    COUNT(DISTINCT r.relationship_id) as total_relationships,
    
    -- Knowledge base
    COUNT(DISTINCT i.instruction_id) as total_instructions,
    COUNT(DISTINCT e.example_id) as total_examples,
    COUNT(DISTINCT kb.kb_id) as total_kb_entries,
    
    -- Version history summary
    COUNT(DISTINCT pvh.version_history_id) as version_changes,
    
    -- Recent activity
    MAX(GREATEST(
        p.updated_at,
        COALESCE(MAX(t.updated_at), p.updated_at),
        COALESCE(MAX(c.updated_at), p.updated_at)
    )) as last_modified
    
FROM projects p
LEFT JOIN datasets d ON p.project_id = d.project_id
LEFT JOIN tables t ON p.project_id = t.project_id
LEFT JOIN columns c ON t.table_id = c.table_id
LEFT JOIN metrics m ON t.table_id = m.table_id
LEFT JOIN relationships r ON p.project_id = r.project_id
LEFT JOIN instructions i ON p.project_id = i.project_id
LEFT JOIN examples e ON p.project_id = e.project_id
LEFT JOIN knowledge_base kb ON p.project_id = kb.project_id
LEFT JOIN project_version_history pvh ON p.project_id = pvh.project_id
GROUP BY 
    p.project_id, p.display_name, p.description, p.status, p.version_string,
    p.last_modified_entity, p.last_modified_by, p.version_locked, p.created_at, p.updated_at;

-- ============================================================================
-- UTILITY FUNCTIONS FOR VERSION MANAGEMENT
-- ============================================================================

-- Function to lock/unlock project version
CREATE OR REPLACE FUNCTION set_project_version_lock(
    p_project_id VARCHAR(50),
    p_locked BOOLEAN,
    p_modified_by VARCHAR(100)
)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE projects 
    SET 
        version_locked = p_locked,
        last_modified_by = p_modified_by,
        updated_at = CURRENT_TIMESTAMP
    WHERE project_id = p_project_id;
    
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- Function to manually increment project version
CREATE OR REPLACE FUNCTION manual_version_increment(
    p_project_id VARCHAR(50),
    p_change_type VARCHAR(20),
    p_modified_by VARCHAR(100),
    p_description TEXT
)
RETURNS VARCHAR(20) AS $$
BEGIN
    RETURN increment_project_version(
        p_project_id, 
        p_change_type, 
        'manual', 
        NULL, 
        p_modified_by, 
        p_description
    );
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Project indexes
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_version ON projects(major_version, minor_version, patch_version);
CREATE INDEX idx_projects_version_locked ON projects(version_locked);

-- Version history indexes
CREATE INDEX idx_project_version_history_project_id ON project_version_history(project_id);
CREATE INDEX idx_project_version_history_created_at ON project_version_history(created_at);

-- Entity version indexes
CREATE INDEX idx_datasets_entity_version ON datasets(entity_version);
CREATE INDEX idx_tables_entity_version ON tables(entity_version);
CREATE INDEX idx_columns_entity_version ON columns(entity_version);

-- Other performance indexes
CREATE INDEX idx_datasets_project_id ON datasets(project_id);
CREATE INDEX idx_tables_project_id ON tables(project_id);
CREATE INDEX idx_columns_table_id ON columns(table_id);
CREATE INDEX idx_project_histories_project_id ON project_histories(project_id);
CREATE INDEX idx_project_histories_entity ON project_histories(entity_type, entity_id);

-- ============================================================================
-- SAMPLE PROJECT SETUP
-- ============================================================================

-- Insert sample project with initial version
INSERT INTO projects (project_id, display_name, description, created_by, status, last_modified_by)
VALUES ('cornerstone', 'Cornerstone Training Analysis', 'Cornerstone OnDemand training records and completion tracking', 'system', 'active', 'system');
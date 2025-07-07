-- Create project_json_store table for storing project JSON data with ChromaDB integration
CREATE TABLE IF NOT EXISTS project_json_store (
    store_id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    project_id VARCHAR(50) NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    
    -- ChromaDB document ID for the stored JSON
    chroma_document_id VARCHAR(100) NOT NULL UNIQUE,
    
    -- JSON data type and content
    json_type VARCHAR(50) NOT NULL,  -- 'tables', 'metrics', 'views', 'calculated_columns', 'enums', 'project'
    json_content JSONB NOT NULL,
    
    -- Metadata
    version VARCHAR(20) DEFAULT '1.0.0',
    is_active BOOLEAN DEFAULT TRUE,
    last_updated_by VARCHAR(100),
    update_reason TEXT,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_project_json_store_project_id ON project_json_store(project_id);
CREATE INDEX IF NOT EXISTS idx_project_json_store_type ON project_json_store(json_type);
CREATE INDEX IF NOT EXISTS idx_project_json_store_chroma_id ON project_json_store(chroma_document_id);
CREATE INDEX IF NOT EXISTS idx_project_json_store_active ON project_json_store(is_active);
CREATE INDEX IF NOT EXISTS idx_project_json_store_created_at ON project_json_store(created_at);

-- Create unique constraint to ensure one active record per project and JSON type
CREATE UNIQUE INDEX IF NOT EXISTS uq_project_json_type ON project_json_store(project_id, json_type) WHERE is_active = TRUE;

-- Create index on JSONB content for efficient querying
CREATE INDEX IF NOT EXISTS idx_project_json_store_content_gin ON project_json_store USING GIN (json_content);

-- Add comments for documentation
COMMENT ON TABLE project_json_store IS 'Store project JSON data with ChromaDB integration for vector search capabilities';
COMMENT ON COLUMN project_json_store.store_id IS 'Unique identifier for the JSON store record';
COMMENT ON COLUMN project_json_store.project_id IS 'Reference to the project this JSON belongs to';
COMMENT ON COLUMN project_json_store.chroma_document_id IS 'ChromaDB document ID for vector storage and retrieval';
COMMENT ON COLUMN project_json_store.json_type IS 'Type of JSON data (tables, metrics, views, calculated_columns, enums, project)';
COMMENT ON COLUMN project_json_store.json_content IS 'The actual JSON content stored as JSONB for efficient querying';
COMMENT ON COLUMN project_json_store.version IS 'Version of the JSON content';
COMMENT ON COLUMN project_json_store.is_active IS 'Whether this record is currently active (only one active per project/type)';
COMMENT ON COLUMN project_json_store.last_updated_by IS 'User who last updated this JSON';
COMMENT ON COLUMN project_json_store.update_reason IS 'Reason for the last update';

-- Create a function to automatically update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_project_json_store_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically update updated_at
CREATE TRIGGER trigger_update_project_json_store_updated_at
    BEFORE UPDATE ON project_json_store
    FOR EACH ROW
    EXECUTE FUNCTION update_project_json_store_updated_at();

-- Create a view for easy access to active JSON stores
CREATE OR REPLACE VIEW active_project_json_stores AS
SELECT 
    store_id,
    project_id,
    chroma_document_id,
    json_type,
    json_content,
    version,
    last_updated_by,
    update_reason,
    created_at,
    updated_at
FROM project_json_store
WHERE is_active = TRUE;

-- Create a function to get project JSON by type
CREATE OR REPLACE FUNCTION get_project_json_by_type(p_project_id VARCHAR(50), p_json_type VARCHAR(50))
RETURNS JSONB AS $$
DECLARE
    result JSONB;
BEGIN
    SELECT json_content INTO result
    FROM project_json_store
    WHERE project_id = p_project_id 
      AND json_type = p_json_type 
      AND is_active = TRUE;
    
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- Create a function to get all JSON types for a project
CREATE OR REPLACE FUNCTION get_project_json_types(p_project_id VARCHAR(50))
RETURNS TABLE(json_type VARCHAR(50), last_updated TIMESTAMP WITH TIME ZONE) AS $$
BEGIN
    RETURN QUERY
    SELECT pjs.json_type, pjs.updated_at
    FROM project_json_store pjs
    WHERE pjs.project_id = p_project_id 
      AND pjs.is_active = TRUE
    ORDER BY pjs.json_type;
END;
$$ LANGUAGE plpgsql; 
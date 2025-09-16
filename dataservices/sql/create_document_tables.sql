-- =====================================================
-- Document Management Tables Creation Script
-- =====================================================
-- This script creates the necessary tables for the Document Ingestion Service
-- with support for multiple document types, insights extraction, and domain-based organization.

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text similarity searches

-- =====================================================
-- 1. Document Versions Table
-- =====================================================
-- Stores document content and metadata with versioning support
CREATE TABLE IF NOT EXISTS doc_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL,
    source_type TEXT NOT NULL,
    document_type TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    content TEXT NOT NULL,
    json_metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by TEXT,
    domain_id TEXT NOT NULL,
    
    -- Constraints
    CONSTRAINT chk_doc_versions_version_positive CHECK (version > 0),
    CONSTRAINT chk_doc_versions_content_not_empty CHECK (LENGTH(TRIM(content)) > 0)
);

-- =====================================================
-- 2. Document Insight Versions Table
-- =====================================================
-- Stores extracted insights and analysis results with versioning support
CREATE TABLE IF NOT EXISTS doc_insight_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    insight_id UUID NOT NULL,
    document_id UUID NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    source_type TEXT NOT NULL,
    document_type TEXT NOT NULL,
    event_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    chromadb_ids TEXT[] NOT NULL DEFAULT '{}',
    event_type TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by TEXT,
    domain_id TEXT NOT NULL,
    
    -- Simplified structure with key data
    chunk_content TEXT,
    key_phrases TEXT[] DEFAULT '{}',
    
    -- Flexible insights structure for additional extraction data
    insights JSONB,
    extraction_config JSONB,
    extraction_date TIMESTAMP WITH TIME ZONE,
    
    -- Constraints
    CONSTRAINT chk_doc_insight_versions_version_positive CHECK (version > 0),
    CONSTRAINT chk_doc_insight_versions_chromadb_ids_not_empty CHECK (array_length(chromadb_ids, 1) > 0)
);

-- =====================================================
-- 3. Indexes for Performance Optimization
-- =====================================================

-- Document Versions Indexes
CREATE INDEX IF NOT EXISTS idx_doc_versions_document_id ON doc_versions (document_id);
CREATE INDEX IF NOT EXISTS idx_doc_versions_domain_id ON doc_versions (domain_id);
CREATE INDEX IF NOT EXISTS idx_doc_versions_source_type ON doc_versions (source_type);
CREATE INDEX IF NOT EXISTS idx_doc_versions_document_type ON doc_versions (document_type);
CREATE INDEX IF NOT EXISTS idx_doc_versions_created_at ON doc_versions (created_at);
CREATE INDEX IF NOT EXISTS idx_doc_versions_created_by ON doc_versions (created_by);
CREATE INDEX IF NOT EXISTS idx_doc_versions_json_metadata ON doc_versions USING GIN (json_metadata);

-- Full-text search index for document content
CREATE INDEX IF NOT EXISTS idx_doc_versions_content_fts ON doc_versions 
    USING GIN (to_tsvector('english', content));

-- Document Insight Versions Indexes
CREATE INDEX IF NOT EXISTS idx_doc_insight_versions_insight_id ON doc_insight_versions (insight_id);
CREATE INDEX IF NOT EXISTS idx_doc_insight_versions_document_id ON doc_insight_versions (document_id);
CREATE INDEX IF NOT EXISTS idx_doc_insight_versions_domain_id ON doc_insight_versions (domain_id);
CREATE INDEX IF NOT EXISTS idx_doc_insight_versions_source_type ON doc_insight_versions (source_type);
CREATE INDEX IF NOT EXISTS idx_doc_insight_versions_document_type ON doc_insight_versions (document_type);
CREATE INDEX IF NOT EXISTS idx_doc_insight_versions_event_timestamp ON doc_insight_versions (event_timestamp);
CREATE INDEX IF NOT EXISTS idx_doc_insight_versions_created_at ON doc_insight_versions (created_at);
CREATE INDEX IF NOT EXISTS idx_doc_insight_versions_created_by ON doc_insight_versions (created_by);
CREATE INDEX IF NOT EXISTS idx_doc_insight_versions_extraction_date ON doc_insight_versions (extraction_date);

-- Full-text search indexes for insights
CREATE INDEX IF NOT EXISTS idx_doc_insight_versions_chunk_content_fts ON doc_insight_versions 
    USING GIN (to_tsvector('english', chunk_content));

-- GIN indexes for array and JSONB columns
CREATE INDEX IF NOT EXISTS idx_doc_insight_versions_key_phrases ON doc_insight_versions 
    USING GIN (key_phrases);
CREATE INDEX IF NOT EXISTS idx_doc_insight_versions_chromadb_ids ON doc_insight_versions 
    USING GIN (chromadb_ids);
CREATE INDEX IF NOT EXISTS idx_doc_insight_versions_insights ON doc_insight_versions 
    USING GIN (insights);
CREATE INDEX IF NOT EXISTS idx_doc_insight_versions_extraction_config ON doc_insight_versions 
    USING GIN (extraction_config);

-- Composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_doc_insight_versions_domain_doc_type ON doc_insight_versions (domain_id, document_type);
CREATE INDEX IF NOT EXISTS idx_doc_insight_versions_domain_source_type ON doc_insight_versions (domain_id, source_type);
CREATE INDEX IF NOT EXISTS idx_doc_insight_versions_doc_type_extraction_date ON doc_insight_versions (document_type, extraction_date);

-- =====================================================
-- 4. Foreign Key Constraints (Optional)
-- =====================================================
-- Note: These are commented out as they might not be needed depending on your architecture
-- Uncomment if you want to enforce referential integrity

-- ALTER TABLE doc_insight_versions 
--     ADD CONSTRAINT fk_doc_insight_versions_document_id 
--     FOREIGN KEY (document_id) REFERENCES doc_versions (id) ON DELETE CASCADE;

-- =====================================================
-- 5. Views for Common Queries
-- =====================================================

-- View for latest document versions
CREATE OR REPLACE VIEW latest_document_versions AS
SELECT DISTINCT ON (document_id) 
    id, document_id, source_type, document_type, version, content, 
    json_metadata, created_at, created_by, domain_id
FROM doc_versions
ORDER BY document_id, version DESC;

-- View for latest insight versions
CREATE OR REPLACE VIEW latest_insight_versions AS
SELECT DISTINCT ON (insight_id) 
    id, insight_id, document_id, version, source_type, document_type, 
    event_timestamp, chromadb_ids, event_type, created_at, created_by, 
    domain_id, chunk_content, key_phrases, insights, extraction_config, 
    extraction_date
FROM doc_insight_versions
ORDER BY insight_id, version DESC;

-- View for documents with their latest insights
CREATE OR REPLACE VIEW documents_with_insights AS
SELECT 
    d.id as document_id,
    d.source_type,
    d.document_type,
    d.content,
    d.json_metadata,
    d.created_at as doc_created_at,
    d.created_by as doc_created_by,
    d.domain_id,
    i.id as insight_id,
    i.event_timestamp,
    i.chunk_content,
    i.key_phrases,
    i.insights,
    i.extraction_config,
    i.extraction_date
FROM latest_document_versions d
LEFT JOIN latest_insight_versions i ON d.document_id = i.document_id;

-- =====================================================
-- 6. Functions for Common Operations
-- =====================================================

-- Function to get document by ID with latest version
CREATE OR REPLACE FUNCTION get_document_by_id(doc_id UUID)
RETURNS TABLE (
    id UUID,
    document_id UUID,
    source_type TEXT,
    document_type TEXT,
    version INTEGER,
    content TEXT,
    json_metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE,
    created_by TEXT,
    domain_id TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM latest_document_versions 
    WHERE latest_document_versions.document_id = doc_id;
END;
$$ LANGUAGE plpgsql;

-- Function to get insights by document ID
CREATE OR REPLACE FUNCTION get_insights_by_document_id(doc_id UUID)
RETURNS TABLE (
    id UUID,
    insight_id UUID,
    document_id UUID,
    version INTEGER,
    source_type TEXT,
    document_type TEXT,
    event_timestamp TIMESTAMP WITH TIME ZONE,
    chromadb_ids TEXT[],
    event_type TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    created_by TEXT,
    domain_id TEXT,
    chunk_content TEXT,
    key_phrases TEXT[],
    insights JSONB,
    extraction_config JSONB,
    extraction_date TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM doc_insight_versions 
    WHERE doc_insight_versions.document_id = doc_id
    ORDER BY created_at DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to search documents by content
CREATE OR REPLACE FUNCTION search_documents_by_content(
    search_query TEXT,
    domain_filter TEXT DEFAULT NULL,
    doc_type_filter TEXT DEFAULT NULL,
    limit_count INTEGER DEFAULT 10
)
RETURNS TABLE (
    document_id UUID,
    source_type TEXT,
    document_type TEXT,
    content TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    domain_id TEXT,
    rank REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        d.document_id,
        d.source_type,
        d.document_type,
        d.content,
        d.created_at,
        d.domain_id,
        ts_rank(to_tsvector('english', d.content), plainto_tsquery('english', search_query)) as rank
    FROM latest_document_versions d
    WHERE 
        to_tsvector('english', d.content) @@ plainto_tsquery('english', search_query)
        AND (domain_filter IS NULL OR d.domain_id = domain_filter)
        AND (doc_type_filter IS NULL OR d.document_type = doc_type_filter)
    ORDER BY rank DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Function to search insights by key phrases
CREATE OR REPLACE FUNCTION search_insights_by_phrases(
    phrase_array TEXT[],
    domain_filter TEXT DEFAULT NULL,
    doc_type_filter TEXT DEFAULT NULL,
    limit_count INTEGER DEFAULT 10
)
RETURNS TABLE (
    insight_id UUID,
    document_id UUID,
    source_type TEXT,
    document_type TEXT,
    chunk_content TEXT,
    key_phrases TEXT[],
    created_at TIMESTAMP WITH TIME ZONE,
    domain_id TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        i.insight_id,
        i.document_id,
        i.source_type,
        i.document_type,
        i.chunk_content,
        i.key_phrases,
        i.created_at,
        i.domain_id
    FROM latest_insight_versions i
    WHERE 
        i.key_phrases && phrase_array
        AND (domain_filter IS NULL OR i.domain_id = domain_filter)
        AND (doc_type_filter IS NULL OR i.document_type = doc_type_filter)
    ORDER BY i.created_at DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 7. Sample Data and Test Queries
-- =====================================================

-- Insert sample document
INSERT INTO doc_versions (
    document_id, source_type, document_type, content, 
    json_metadata, created_by, domain_id
) VALUES (
    uuid_generate_v4(),
    'file_upload',
    'financial_report',
    'This is a sample financial report containing revenue data and KPIs.',
    '{"file_name": "sample_report.pdf", "file_size": 1024}',
    'system',
    'domain_123'
) ON CONFLICT DO NOTHING;

-- Insert sample insight
INSERT INTO doc_insight_versions (
    insight_id, document_id, source_type, document_type, 
    event_timestamp, chromadb_ids, event_type, created_by, 
    domain_id, chunk_content, key_phrases, insights, 
    extraction_config, extraction_date
) VALUES (
    uuid_generate_v4(),
    (SELECT document_id FROM doc_versions LIMIT 1),
    'file_upload',
    'financial_report',
    NOW(),
    ARRAY['chunk_1', 'chunk_2'],
    'document_ingestion',
    'system',
    'domain_123',
    'Sample financial report content with revenue and KPI data.',
    ARRAY['revenue', 'KPI', 'financial', 'metrics'],
    '{"business_intelligence": {"kpis": ["revenue_growth", "profit_margin"]}}',
    '{"extraction_types": ["business_intelligence"], "model": "gpt-4"}',
    NOW()
) ON CONFLICT DO NOTHING;

-- =====================================================
-- 8. Example Queries
-- =====================================================

-- Query 1: Get all documents in a domain
-- SELECT * FROM latest_document_versions WHERE domain_id = 'domain_123';

-- Query 2: Search documents by content
-- SELECT * FROM search_documents_by_content('revenue growth', 'domain_123', 'financial_report', 5);

-- Query 3: Search insights by key phrases
-- SELECT * FROM search_insights_by_phrases(ARRAY['revenue', 'KPI'], 'domain_123', 'financial_report', 5);

-- Query 4: Get documents with their insights
-- SELECT * FROM documents_with_insights WHERE domain_id = 'domain_123';

-- Query 5: Find insights containing specific business intelligence
-- SELECT * FROM doc_insight_versions 
-- WHERE insights ? 'business_intelligence' 
-- AND domain_id = 'domain_123';

-- Query 6: Get insights by extraction date range
-- SELECT * FROM doc_insight_versions 
-- WHERE extraction_date BETWEEN '2024-01-01' AND '2024-12-31'
-- AND domain_id = 'domain_123';

-- =====================================================
-- 9. Performance Monitoring Queries
-- =====================================================

-- Check table sizes
-- SELECT 
--     schemaname,
--     tablename,
--     pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
-- FROM pg_tables 
-- WHERE tablename IN ('doc_versions', 'doc_insight_versions');

-- Check index usage
-- SELECT 
--     schemaname,
--     tablename,
--     indexname,
--     idx_scan,
--     idx_tup_read,
--     idx_tup_fetch
-- FROM pg_stat_user_indexes 
-- WHERE tablename IN ('doc_versions', 'doc_insight_versions')
-- ORDER BY idx_scan DESC;

-- =====================================================
-- Script completed successfully
-- =====================================================

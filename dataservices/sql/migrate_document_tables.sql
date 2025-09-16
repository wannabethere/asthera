-- =====================================================
-- Document Tables Migration Script
-- =====================================================
-- This script migrates existing document tables to the new schema
-- Run this if you have existing document tables that need to be updated

-- =====================================================
-- 1. Backup existing data (if tables exist)
-- =====================================================

-- Create backup tables if they don't exist
CREATE TABLE IF NOT EXISTS doc_versions_backup AS 
SELECT * FROM doc_versions WHERE 1=0;

CREATE TABLE IF NOT EXISTS doc_insight_versions_backup AS 
SELECT * FROM doc_insight_versions WHERE 1=0;

-- Backup existing data
INSERT INTO doc_versions_backup 
SELECT * FROM doc_versions WHERE EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'doc_versions');

INSERT INTO doc_insight_versions_backup 
SELECT * FROM doc_insight_versions WHERE EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'doc_insight_versions');

-- =====================================================
-- 2. Add new columns to existing tables
-- =====================================================

-- Add domain_id to doc_versions if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'doc_versions' AND column_name = 'domain_id'
    ) THEN
        ALTER TABLE doc_versions ADD COLUMN domain_id TEXT;
        -- Set default domain for existing records
        UPDATE doc_versions SET domain_id = 'default_domain' WHERE domain_id IS NULL;
        -- Make it NOT NULL after setting defaults
        ALTER TABLE doc_versions ALTER COLUMN domain_id SET NOT NULL;
    END IF;
END $$;

-- Add domain_id to doc_insight_versions if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'doc_insight_versions' AND column_name = 'domain_id'
    ) THEN
        ALTER TABLE doc_insight_versions ADD COLUMN domain_id TEXT;
        -- Set default domain for existing records
        UPDATE doc_insight_versions SET domain_id = 'default_domain' WHERE domain_id IS NULL;
        -- Make it NOT NULL after setting defaults
        ALTER TABLE doc_insight_versions ALTER COLUMN domain_id SET NOT NULL;
    END IF;
END $$;

-- Add document_id to doc_insight_versions if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'doc_insight_versions' AND column_name = 'document_id'
    ) THEN
        ALTER TABLE doc_insight_versions ADD COLUMN document_id UUID;
        -- Try to populate from existing data if possible
        -- This is a best-effort approach - you may need to manually fix some records
        UPDATE doc_insight_versions 
        SET document_id = (
            SELECT d.document_id 
            FROM doc_versions d 
            WHERE d.id = doc_insight_versions.insight_id 
            LIMIT 1
        ) 
        WHERE document_id IS NULL;
        -- Make it NOT NULL after setting defaults
        ALTER TABLE doc_insight_versions ALTER COLUMN document_id SET NOT NULL;
    END IF;
END $$;

-- Add new columns for simplified structure
ALTER TABLE doc_insight_versions 
ADD COLUMN IF NOT EXISTS chunk_content TEXT,
ADD COLUMN IF NOT EXISTS key_phrases TEXT[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS insights JSONB,
ADD COLUMN IF NOT EXISTS extraction_config JSONB,
ADD COLUMN IF NOT EXISTS extraction_date TIMESTAMP WITH TIME ZONE;

-- =====================================================
-- 3. Migrate data from old structure to new structure
-- =====================================================

-- Migrate chunk content from old insight column if it exists
UPDATE doc_insight_versions 
SET chunk_content = COALESCE(
    insights->>'content',
    insights->>'text',
    insights->>'chunk_content'
)
WHERE chunk_content IS NULL 
AND insights IS NOT NULL;

-- Migrate key phrases from old phrases column if it exists
UPDATE doc_insight_versions 
SET key_phrases = COALESCE(
    insights->'phrases',
    insights->'key_phrases',
    ARRAY[]::TEXT[]
)
WHERE key_phrases IS NULL OR array_length(key_phrases, 1) IS NULL
AND insights IS NOT NULL;

-- Migrate extraction date from event_timestamp if extraction_date is null
UPDATE doc_insight_versions 
SET extraction_date = event_timestamp 
WHERE extraction_date IS NULL;

-- =====================================================
-- 4. Create new indexes
-- =====================================================

-- Document Versions Indexes
CREATE INDEX IF NOT EXISTS idx_doc_versions_domain_id ON doc_versions (domain_id);
CREATE INDEX IF NOT EXISTS idx_doc_versions_json_metadata ON doc_versions USING GIN (json_metadata);
CREATE INDEX IF NOT EXISTS idx_doc_versions_content_fts ON doc_versions 
    USING GIN (to_tsvector('english', content));

-- Document Insight Versions Indexes
CREATE INDEX IF NOT EXISTS idx_doc_insight_versions_document_id ON doc_insight_versions (document_id);
CREATE INDEX IF NOT EXISTS idx_doc_insight_versions_domain_id ON doc_insight_versions (domain_id);
CREATE INDEX IF NOT EXISTS idx_doc_insight_versions_extraction_date ON doc_insight_versions (extraction_date);
CREATE INDEX IF NOT EXISTS idx_doc_insight_versions_chunk_content_fts ON doc_insight_versions 
    USING GIN (to_tsvector('english', chunk_content));
CREATE INDEX IF NOT EXISTS idx_doc_insight_versions_key_phrases ON doc_insight_versions 
    USING GIN (key_phrases);
CREATE INDEX IF NOT EXISTS idx_doc_insight_versions_insights ON doc_insight_versions 
    USING GIN (insights);
CREATE INDEX IF NOT EXISTS idx_doc_insight_versions_extraction_config ON doc_insight_versions 
    USING GIN (extraction_config);

-- Composite indexes
CREATE INDEX IF NOT EXISTS idx_doc_insight_versions_domain_doc_type ON doc_insight_versions (domain_id, document_type);
CREATE INDEX IF NOT EXISTS idx_doc_insight_versions_domain_source_type ON doc_insight_versions (domain_id, source_type);

-- =====================================================
-- 5. Add constraints
-- =====================================================

-- Add check constraints
ALTER TABLE doc_versions 
ADD CONSTRAINT IF NOT EXISTS chk_doc_versions_version_positive 
CHECK (version > 0);

ALTER TABLE doc_versions 
ADD CONSTRAINT IF NOT EXISTS chk_doc_versions_content_not_empty 
CHECK (LENGTH(TRIM(content)) > 0);

ALTER TABLE doc_insight_versions 
ADD CONSTRAINT IF NOT EXISTS chk_doc_insight_versions_version_positive 
CHECK (version > 0);

ALTER TABLE doc_insight_versions 
ADD CONSTRAINT IF NOT EXISTS chk_doc_insight_versions_chromadb_ids_not_empty 
CHECK (array_length(chromadb_ids, 1) > 0);

-- =====================================================
-- 6. Create or update views
-- =====================================================

-- Drop existing views if they exist
DROP VIEW IF EXISTS latest_document_versions CASCADE;
DROP VIEW IF EXISTS latest_insight_versions CASCADE;
DROP VIEW IF EXISTS documents_with_insights CASCADE;

-- Create updated views
CREATE VIEW latest_document_versions AS
SELECT DISTINCT ON (document_id) 
    id, document_id, source_type, document_type, version, content, 
    json_metadata, created_at, created_by, domain_id
FROM doc_versions
ORDER BY document_id, version DESC;

CREATE VIEW latest_insight_versions AS
SELECT DISTINCT ON (insight_id) 
    id, insight_id, document_id, version, source_type, document_type, 
    event_timestamp, chromadb_ids, event_type, created_at, created_by, 
    domain_id, chunk_content, key_phrases, insights, extraction_config, 
    extraction_date
FROM doc_insight_versions
ORDER BY insight_id, version DESC;

CREATE VIEW documents_with_insights AS
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
-- 7. Create or update functions
-- =====================================================

-- Drop existing functions if they exist
DROP FUNCTION IF EXISTS get_document_by_id(UUID);
DROP FUNCTION IF EXISTS get_insights_by_document_id(UUID);
DROP FUNCTION IF EXISTS search_documents_by_content(TEXT, TEXT, TEXT, INTEGER);
DROP FUNCTION IF EXISTS search_insights_by_phrases(TEXT[], TEXT, TEXT, INTEGER);

-- Create updated functions
CREATE FUNCTION get_document_by_id(doc_id UUID)
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

CREATE FUNCTION get_insights_by_document_id(doc_id UUID)
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

CREATE FUNCTION search_documents_by_content(
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

CREATE FUNCTION search_insights_by_phrases(
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
-- 8. Data validation and cleanup
-- =====================================================

-- Validate that all records have domain_id
DO $$
DECLARE
    missing_domain_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO missing_domain_count 
    FROM doc_versions 
    WHERE domain_id IS NULL;
    
    IF missing_domain_count > 0 THEN
        RAISE WARNING 'Found % records in doc_versions without domain_id', missing_domain_count;
    END IF;
    
    SELECT COUNT(*) INTO missing_domain_count 
    FROM doc_insight_versions 
    WHERE domain_id IS NULL;
    
    IF missing_domain_count > 0 THEN
        RAISE WARNING 'Found % records in doc_insight_versions without domain_id', missing_domain_count;
    END IF;
END $$;

-- =====================================================
-- 9. Optional: Remove old columns (uncomment if needed)
-- =====================================================

-- WARNING: Only uncomment these if you're sure you want to remove old columns
-- Make sure to backup your data first!

-- ALTER TABLE doc_insight_versions DROP COLUMN IF EXISTS phrases;
-- ALTER TABLE doc_insight_versions DROP COLUMN IF EXISTS insight;
-- ALTER TABLE doc_insight_versions DROP COLUMN IF EXISTS extracted_entities;
-- ALTER TABLE doc_insight_versions DROP COLUMN IF EXISTS ner_text;

-- =====================================================
-- Migration completed successfully
-- =====================================================

-- Display summary
SELECT 
    'doc_versions' as table_name,
    COUNT(*) as record_count,
    COUNT(DISTINCT domain_id) as unique_domains
FROM doc_versions
UNION ALL
SELECT 
    'doc_insight_versions' as table_name,
    COUNT(*) as record_count,
    COUNT(DISTINCT domain_id) as unique_domains
FROM doc_insight_versions;

-- ============================================================================
-- DOCUMENT KG INSIGHTS TABLE
-- ============================================================================
-- Stores documents processed during extraction along with extraction type
-- and extracted JSON contents. The doc_id matches ChromaDB document IDs
-- for cross-referencing between PostgreSQL and ChromaDB.

CREATE TABLE IF NOT EXISTS document_kg_insights (
    id SERIAL PRIMARY KEY,
    
    -- ChromaDB document ID (matches the ID used in ChromaDB)
    doc_id VARCHAR(255) NOT NULL,
    
    -- Original document content
    document_content TEXT NOT NULL,
    
    -- Extraction type: 'context', 'control', 'fields', 'entities'
    extraction_type VARCHAR(50) NOT NULL,
    
    -- Extracted data as JSONB
    extracted_data JSONB NOT NULL,
    
    -- Optional context reference
    context_id VARCHAR(100),
    
    -- Optional metadata about the extraction
    extraction_metadata JSONB,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT document_kg_insights_doc_id_unique UNIQUE (doc_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_document_kg_insights_doc_id ON document_kg_insights(doc_id);
CREATE INDEX IF NOT EXISTS idx_document_kg_insights_extraction_type ON document_kg_insights(extraction_type);
CREATE INDEX IF NOT EXISTS idx_document_kg_insights_context_id ON document_kg_insights(context_id);
CREATE INDEX IF NOT EXISTS idx_document_kg_insights_created_at ON document_kg_insights(created_at);
CREATE INDEX IF NOT EXISTS idx_document_kg_insights_extracted_data ON document_kg_insights USING GIN(extracted_data);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_document_kg_insights_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for automatic updated_at
CREATE TRIGGER update_document_kg_insights_updated_at
    BEFORE UPDATE ON document_kg_insights
    FOR EACH ROW
    EXECUTE FUNCTION update_document_kg_insights_updated_at();

-- Comments
COMMENT ON TABLE document_kg_insights IS 'Stores documents processed during extraction with extraction type and extracted JSON contents';
COMMENT ON COLUMN document_kg_insights.doc_id IS 'ChromaDB document ID - matches the ID used in ChromaDB for cross-referencing';
COMMENT ON COLUMN document_kg_insights.document_content IS 'Original document text that was processed';
COMMENT ON COLUMN document_kg_insights.extraction_type IS 'Type of extraction: context, control, fields, entities';
COMMENT ON COLUMN document_kg_insights.extracted_data IS 'JSONB containing the extracted structured data';
COMMENT ON COLUMN document_kg_insights.context_id IS 'Optional context ID if the extraction is context-specific';


-- Migration script to create contextual graph tables
-- Run this before ingesting contextual edges to PostgreSQL

-- Create contexts table
CREATE TABLE IF NOT EXISTS contexts (
    context_id SERIAL PRIMARY KEY,
    context_type VARCHAR(100) NOT NULL DEFAULT 'organizational_situational',
    context_name VARCHAR(255) NOT NULL UNIQUE,
    context_definition JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index on context_name for faster lookups
CREATE INDEX IF NOT EXISTS idx_contexts_context_name ON contexts(context_name);
CREATE INDEX IF NOT EXISTS idx_contexts_context_type ON contexts(context_type);

-- Create contextual_relationships table
CREATE TABLE IF NOT EXISTS contextual_relationships (
    id SERIAL PRIMARY KEY,
    source_entity_id VARCHAR(255) NOT NULL,
    relationship_type VARCHAR(100) NOT NULL,
    target_entity_id VARCHAR(255) NOT NULL,
    context_id INTEGER NOT NULL REFERENCES contexts(context_id) ON DELETE CASCADE,
    strength FLOAT DEFAULT 0.0,
    confidence FLOAT DEFAULT 0.0,
    reasoning TEXT,
    valid_from TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Unique constraint to prevent duplicates
    UNIQUE(source_entity_id, relationship_type, target_entity_id, context_id)
);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_contextual_relationships_source ON contextual_relationships(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_contextual_relationships_target ON contextual_relationships(target_entity_id);
CREATE INDEX IF NOT EXISTS idx_contextual_relationships_type ON contextual_relationships(relationship_type);
CREATE INDEX IF NOT EXISTS idx_contextual_relationships_context ON contextual_relationships(context_id);
CREATE INDEX IF NOT EXISTS idx_contextual_relationships_composite ON contextual_relationships(source_entity_id, relationship_type, target_entity_id);

-- Add comment to tables
COMMENT ON TABLE contexts IS 'Stores organizational and situational contexts for the contextual graph';
COMMENT ON TABLE contextual_relationships IS 'Stores relationships between entities in the contextual graph';

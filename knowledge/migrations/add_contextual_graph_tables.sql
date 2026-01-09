-- ============================================================================
-- POSTGRESQL: Contextual Graph Schema Extension
-- ============================================================================
-- Based on contextual_graph_reasoning_agent.md architecture
-- This migration adds contextual graph tables to support context-aware reasoning
-- Extends the existing schema from create_contextual_graph_schema.sql
--
-- Run this migration AFTER create_contextual_graph_schema.sql
-- ============================================================================

-- ============================================================================
-- 1. CORE ENTITIES TABLE (Unified entity registry)
-- ============================================================================
-- This table provides a unified view of all entities (controls, requirements, evidence, etc.)
-- Maps to existing entity tables via entity_id

CREATE TABLE IF NOT EXISTS entities (
    entity_id VARCHAR(100) PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,  -- 'control', 'requirement', 'evidence', 'system', 'stakeholder', etc.
    entity_name TEXT NOT NULL,
    entity_description TEXT,
    metadata JSONB,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Reference to source table (for joins)
    source_table VARCHAR(50),  -- 'controls', 'requirements', 'evidence_types', etc.
    
    -- Constraints
    CONSTRAINT entities_type_check CHECK (entity_type IN (
        'control', 'requirement', 'evidence', 'system', 'stakeholder', 
        'framework', 'data_type', 'business_process', 'metric'
    ))
);

CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_source_table ON entities(source_table);
CREATE INDEX IF NOT EXISTS idx_entities_metadata ON entities USING GIN (metadata);

COMMENT ON TABLE entities IS 'Unified registry of all entities in the knowledge graph';

-- ============================================================================
-- 2. CONTEXT DEFINITIONS TABLE
-- ============================================================================
-- Stores organizational, temporal, operational, and situational contexts
-- Supports context hierarchy via parent_context_id

CREATE TABLE IF NOT EXISTS contexts (
    context_id SERIAL PRIMARY KEY,
    context_type VARCHAR(50) NOT NULL,  -- 'organizational', 'temporal', 'operational', 'situational', 'risk', 'stakeholder'
    context_name VARCHAR(200) NOT NULL,
    context_definition JSONB NOT NULL,  -- Full context definition as JSONB
    
    -- Hierarchy support
    parent_context_id INTEGER REFERENCES contexts(context_id) ON DELETE SET NULL,
    
    -- Temporal validity
    valid_from TIMESTAMP,
    valid_until TIMESTAMP,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    
    -- Constraints
    CONSTRAINT contexts_type_check CHECK (context_type IN (
        'organizational', 'temporal', 'operational', 'situational', 
        'risk', 'stakeholder', 'environmental'
    )),
    CONSTRAINT contexts_temporal_check CHECK (
        valid_from IS NULL OR valid_until IS NULL OR valid_from <= valid_until
    )
);

CREATE INDEX IF NOT EXISTS idx_contexts_type ON contexts(context_type);
CREATE INDEX IF NOT EXISTS idx_contexts_name ON contexts(context_name);
CREATE INDEX IF NOT EXISTS idx_contexts_definition ON contexts USING GIN (context_definition);
CREATE INDEX IF NOT EXISTS idx_contexts_parent ON contexts(parent_context_id);
CREATE INDEX IF NOT EXISTS idx_contexts_validity ON contexts(valid_from, valid_until);

COMMENT ON TABLE contexts IS 'Context definitions for contextual graph (organizational, temporal, operational, etc.)';

-- ============================================================================
-- 3. ENTITY CONTEXTUAL PROPERTIES TABLE
-- ============================================================================
-- Stores properties that vary by context (risk scores, complexity, feasibility, etc.)
-- Example: Same control has different risk score in healthcare vs finance context

CREATE TABLE IF NOT EXISTS entity_contextual_properties (
    id SERIAL PRIMARY KEY,
    entity_id VARCHAR(100) NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    context_id INTEGER NOT NULL REFERENCES contexts(context_id) ON DELETE CASCADE,
    property_name VARCHAR(100) NOT NULL,  -- 'risk_score', 'implementation_complexity', 'priority', etc.
    property_value JSONB NOT NULL,  -- Flexible JSONB value
    
    -- Confidence and reasoning
    confidence_score DECIMAL(3,2) DEFAULT 0.5 CHECK (confidence_score >= 0 AND confidence_score <= 1),
    reasoning TEXT,  -- LLM reasoning for this property value
    data_source TEXT,  -- Where this property came from
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Unique constraint: one property value per entity-context-property combination
    CONSTRAINT entity_contextual_properties_unique UNIQUE (entity_id, context_id, property_name)
);

CREATE INDEX IF NOT EXISTS idx_contextual_props_entity ON entity_contextual_properties(entity_id);
CREATE INDEX IF NOT EXISTS idx_contextual_props_context ON entity_contextual_properties(context_id);
CREATE INDEX IF NOT EXISTS idx_contextual_props_name ON entity_contextual_properties(property_name);
CREATE INDEX IF NOT EXISTS idx_contextual_props_value ON entity_contextual_properties USING GIN (property_value);
CREATE INDEX IF NOT EXISTS idx_contextual_props_entity_context ON entity_contextual_properties(entity_id, context_id);

COMMENT ON TABLE entity_contextual_properties IS 'Context-dependent properties for entities (risk scores, complexity, etc.)';

-- ============================================================================
-- 4. CONTEXTUAL RELATIONSHIPS TABLE
-- ============================================================================
-- Stores context-aware relationships between entities
-- Example: Control-Requirement relationship with different strength in different contexts

CREATE TABLE IF NOT EXISTS contextual_relationships (
    id SERIAL PRIMARY KEY,
    source_entity_id VARCHAR(100) NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    relationship_type VARCHAR(50) NOT NULL,  -- 'REQUIRES', 'PROVED_BY', 'APPLIES_TO', 'MAPS_TO', 'MEASURED_BY', etc.
    target_entity_id VARCHAR(100) NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    context_id INTEGER NOT NULL REFERENCES contexts(context_id) ON DELETE CASCADE,
    
    -- Relationship strength in this context
    strength DECIMAL(3,2) DEFAULT 1.0 CHECK (strength >= 0 AND strength <= 1),
    confidence DECIMAL(3,2) DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
    
    -- Conditional logic
    conditions JSONB,  -- When does this relationship hold? {"organization_type": ["healthcare"], "data_sensitivity": ["high"]}
    exceptions JSONB,  -- When doesn't this apply? {"IF risk_assessment_justifies": "can extend to 120 days"}
    
    -- Temporal validity
    valid_from TIMESTAMP,
    valid_until TIMESTAMP,
    
    -- Reasoning
    reasoning TEXT,  -- Why does context affect this relationship?
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT contextual_relationships_temporal_check CHECK (
        valid_from IS NULL OR valid_until IS NULL OR valid_from <= valid_until
    ),
    CONSTRAINT contextual_relationships_no_self_reference CHECK (source_entity_id != target_entity_id)
);

CREATE INDEX IF NOT EXISTS idx_contextual_rels_source ON contextual_relationships(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_contextual_rels_target ON contextual_relationships(target_entity_id);
CREATE INDEX IF NOT EXISTS idx_contextual_rels_context ON contextual_relationships(context_id);
CREATE INDEX IF NOT EXISTS idx_contextual_rels_type ON contextual_relationships(relationship_type);
CREATE INDEX IF NOT EXISTS idx_contextual_rels_source_context ON contextual_relationships(source_entity_id, context_id);
CREATE INDEX IF NOT EXISTS idx_contextual_rels_conditions ON contextual_relationships USING GIN (conditions);
CREATE INDEX IF NOT EXISTS idx_contextual_rels_exceptions ON contextual_relationships USING GIN (exceptions);

COMMENT ON TABLE contextual_relationships IS 'Context-aware relationships between entities with conditional logic';

-- ============================================================================
-- 5. CONTEXT INHERITANCE TABLE
-- ============================================================================
-- Supports context hierarchy where child contexts inherit from parent contexts
-- Example: "Large Healthcare Org" inherits from "Healthcare Organization"

CREATE TABLE IF NOT EXISTS context_inheritance (
    child_context_id INTEGER NOT NULL REFERENCES contexts(context_id) ON DELETE CASCADE,
    parent_context_id INTEGER NOT NULL REFERENCES contexts(context_id) ON DELETE CASCADE,
    inheritance_type VARCHAR(50) NOT NULL DEFAULT 'partial',  -- 'full', 'partial', 'override'
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (child_context_id, parent_context_id),
    
    -- Constraints
    CONSTRAINT context_inheritance_no_self_reference CHECK (child_context_id != parent_context_id),
    CONSTRAINT context_inheritance_type_check CHECK (inheritance_type IN ('full', 'partial', 'override'))
);

CREATE INDEX IF NOT EXISTS idx_context_inheritance_child ON context_inheritance(child_context_id);
CREATE INDEX IF NOT EXISTS idx_context_inheritance_parent ON context_inheritance(parent_context_id);

COMMENT ON TABLE context_inheritance IS 'Context inheritance relationships for hierarchical context modeling';

-- ============================================================================
-- 6. VIEWS FOR COMMON QUERIES
-- ============================================================================

-- View: Entity with all contextual properties
CREATE OR REPLACE VIEW entity_contextual_view AS
SELECT 
    e.entity_id,
    e.entity_type,
    e.entity_name,
    e.entity_description,
    c.context_id,
    c.context_type,
    c.context_name,
    ecp.property_name,
    ecp.property_value,
    ecp.confidence_score,
    ecp.reasoning
FROM entities e
JOIN entity_contextual_properties ecp ON e.entity_id = ecp.entity_id
JOIN contexts c ON ecp.context_id = c.context_id;

-- View: Contextual relationships with entity details
CREATE OR REPLACE VIEW contextual_relationships_view AS
SELECT 
    cr.id,
    cr.relationship_type,
    cr.strength,
    cr.confidence,
    cr.context_id,
    c.context_name,
    c.context_type,
    source_e.entity_id AS source_entity_id,
    source_e.entity_type AS source_entity_type,
    source_e.entity_name AS source_entity_name,
    target_e.entity_id AS target_entity_id,
    target_e.entity_type AS target_entity_type,
    target_e.entity_name AS target_entity_name,
    cr.conditions,
    cr.exceptions,
    cr.reasoning,
    cr.valid_from,
    cr.valid_until
FROM contextual_relationships cr
JOIN entities source_e ON cr.source_entity_id = source_e.entity_id
JOIN entities target_e ON cr.target_entity_id = target_e.entity_id
JOIN contexts c ON cr.context_id = c.context_id;

-- View: Active contexts (currently valid)
CREATE OR REPLACE VIEW active_contexts AS
SELECT 
    context_id,
    context_type,
    context_name,
    context_definition,
    parent_context_id,
    valid_from,
    valid_until
FROM contexts
WHERE (valid_from IS NULL OR valid_from <= CURRENT_TIMESTAMP)
  AND (valid_until IS NULL OR valid_until >= CURRENT_TIMESTAMP);

-- View: Context hierarchy (all parent-child relationships)
CREATE OR REPLACE VIEW context_hierarchy AS
WITH RECURSIVE context_tree AS (
    -- Base case: root contexts (no parent)
    SELECT 
        c.context_id,
        c.context_name,
        c.context_type,
        c.parent_context_id,
        0 AS depth,
        ARRAY[c.context_id] AS path
    FROM contexts c
    WHERE c.parent_context_id IS NULL
    
    UNION ALL
    
    -- Recursive case: child contexts
    SELECT 
        c.context_id,
        c.context_name,
        c.context_type,
        c.parent_context_id,
        ct.depth + 1,
        ct.path || c.context_id
    FROM contexts c
    JOIN context_tree ct ON c.parent_context_id = ct.context_id
    WHERE NOT c.context_id = ANY(ct.path)  -- Prevent cycles
)
SELECT * FROM context_tree;

-- ============================================================================
-- 7. FUNCTIONS FOR CONTEXTUAL GRAPH OPERATIONS
-- ============================================================================

-- Function: Get all properties for an entity in a context (including inherited)
CREATE OR REPLACE FUNCTION get_entity_properties_in_context(
    p_entity_id VARCHAR(100),
    p_context_id INTEGER
)
RETURNS TABLE (
    property_name VARCHAR(100),
    property_value JSONB,
    context_id INTEGER,
    context_name VARCHAR(200),
    is_inherited BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    WITH context_ancestors AS (
        -- Get all ancestor contexts (parent chain)
        WITH RECURSIVE ancestor_tree AS (
            SELECT context_id, parent_context_id, 0 AS depth
            FROM contexts
            WHERE context_id = p_context_id
            
            UNION ALL
            
            SELECT c.context_id, c.parent_context_id, at.depth + 1
            FROM contexts c
            JOIN ancestor_tree at ON c.context_id = at.parent_context_id
        )
        SELECT context_id FROM ancestor_tree
    )
    SELECT 
        ecp.property_name,
        ecp.property_value,
        ecp.context_id,
        c.context_name,
        (ecp.context_id != p_context_id) AS is_inherited
    FROM entity_contextual_properties ecp
    JOIN contexts c ON ecp.context_id = c.context_id
    WHERE ecp.entity_id = p_entity_id
      AND ecp.context_id IN (SELECT context_id FROM context_ancestors)
    ORDER BY 
        CASE WHEN ecp.context_id = p_context_id THEN 0 ELSE 1 END,  -- Direct properties first
        ecp.confidence_score DESC;
END;
$$ LANGUAGE plpgsql;

-- Function: Get contextual relationships for entities in a context
CREATE OR REPLACE FUNCTION get_contextual_relationships(
    p_source_entity_id VARCHAR(100) DEFAULT NULL,
    p_target_entity_id VARCHAR(100) DEFAULT NULL,
    p_context_id INTEGER DEFAULT NULL,
    p_relationship_type VARCHAR(50) DEFAULT NULL
)
RETURNS TABLE (
    id INTEGER,
    source_entity_id VARCHAR(100),
    target_entity_id VARCHAR(100),
    relationship_type VARCHAR(50),
    context_id INTEGER,
    strength DECIMAL(3,2),
    confidence DECIMAL(3,2),
    reasoning TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        cr.id,
        cr.source_entity_id,
        cr.target_entity_id,
        cr.relationship_type,
        cr.context_id,
        cr.strength,
        cr.confidence,
        cr.reasoning
    FROM contextual_relationships cr
    WHERE (p_source_entity_id IS NULL OR cr.source_entity_id = p_source_entity_id)
      AND (p_target_entity_id IS NULL OR cr.target_entity_id = p_target_entity_id)
      AND (p_context_id IS NULL OR cr.context_id = p_context_id)
      AND (p_relationship_type IS NULL OR cr.relationship_type = p_relationship_type)
      AND (cr.valid_from IS NULL OR cr.valid_from <= CURRENT_TIMESTAMP)
      AND (cr.valid_until IS NULL OR cr.valid_until >= CURRENT_TIMESTAMP)
    ORDER BY cr.strength DESC, cr.confidence DESC;
END;
$$ LANGUAGE plpgsql;

-- Function: Sync entities from existing tables
-- This function populates the entities table from controls, requirements, evidence_types
CREATE OR REPLACE FUNCTION sync_entities_from_tables()
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER := 0;
BEGIN
    -- Sync controls
    INSERT INTO entities (entity_id, entity_type, entity_name, entity_description, source_table, metadata)
    SELECT 
        control_id,
        'control',
        control_name,
        control_description,
        'controls',
        jsonb_build_object(
            'framework', framework,
            'category', category,
            'vector_doc_id', vector_doc_id
        )
    FROM controls
    ON CONFLICT (entity_id) DO UPDATE SET
        entity_name = EXCLUDED.entity_name,
        entity_description = EXCLUDED.entity_description,
        metadata = EXCLUDED.metadata,
        updated_at = CURRENT_TIMESTAMP;
    
    GET DIAGNOSTICS v_count = ROW_COUNT;
    
    -- Sync requirements
    INSERT INTO entities (entity_id, entity_type, entity_name, entity_description, source_table, metadata)
    SELECT 
        requirement_id,
        'requirement',
        requirement_id,  -- Use ID as name if no separate name field
        requirement_text,
        'requirements',
        jsonb_build_object(
            'control_id', control_id,
            'requirement_type', requirement_type,
            'vector_doc_id', vector_doc_id
        )
    FROM requirements
    ON CONFLICT (entity_id) DO UPDATE SET
        entity_name = EXCLUDED.entity_name,
        entity_description = EXCLUDED.entity_description,
        metadata = EXCLUDED.metadata,
        updated_at = CURRENT_TIMESTAMP;
    
    -- Sync evidence types
    INSERT INTO entities (entity_id, entity_type, entity_name, entity_description, source_table, metadata)
    SELECT 
        evidence_id,
        'evidence',
        evidence_name,
        collection_method,
        'evidence_types',
        jsonb_build_object(
            'evidence_category', evidence_category,
            'vector_doc_id', vector_doc_id
        )
    FROM evidence_types
    ON CONFLICT (entity_id) DO UPDATE SET
        entity_name = EXCLUDED.entity_name,
        entity_description = EXCLUDED.entity_description,
        metadata = EXCLUDED.metadata,
        updated_at = CURRENT_TIMESTAMP;
    
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 8. TRIGGERS
-- ============================================================================

-- Trigger: Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_entities_updated_at
    BEFORE UPDATE ON entities
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_contexts_updated_at
    BEFORE UPDATE ON contexts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_contextual_props_updated_at
    BEFORE UPDATE ON entity_contextual_properties
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_contextual_rels_updated_at
    BEFORE UPDATE ON contextual_relationships
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 9. COMMENTS
-- ============================================================================

COMMENT ON TABLE entities IS 'Unified registry of all entities in the knowledge graph';
COMMENT ON TABLE contexts IS 'Context definitions for contextual graph (organizational, temporal, operational, etc.)';
COMMENT ON TABLE entity_contextual_properties IS 'Context-dependent properties for entities (risk scores, complexity, etc.)';
COMMENT ON TABLE contextual_relationships IS 'Context-aware relationships between entities with conditional logic';
COMMENT ON TABLE context_inheritance IS 'Context inheritance relationships for hierarchical context modeling';

COMMENT ON FUNCTION get_entity_properties_in_context IS 'Get all properties for an entity in a context, including inherited from parent contexts';
COMMENT ON FUNCTION get_contextual_relationships IS 'Get contextual relationships with filtering options';
COMMENT ON FUNCTION sync_entities_from_tables IS 'Sync entities table from existing control, requirement, and evidence tables';

-- ============================================================================
-- 10. INITIAL DATA POPULATION (Optional)
-- ============================================================================
-- Uncomment to automatically sync entities on migration

-- SELECT sync_entities_from_tables();


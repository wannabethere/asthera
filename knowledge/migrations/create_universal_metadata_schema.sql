-- ============================================================================
-- UNIVERSAL RISK METADATA FRAMEWORK - PostgreSQL Schema
-- ============================================================================
-- This schema implements the universal metadata framework for domain-adaptive
-- risk metadata that enables data-driven risk evaluation across any compliance
-- domain using transfer learning.
-- 
-- Key Features:
-- - Universal metadata template that works for any domain
-- - Transfer learning support via pattern storage
-- - Cross-domain mappings and equivalencies
-- - Quantitative risk scoring and prioritization
-- ============================================================================

-- Note: Extensions removed - no external dependencies required
-- uuid-ossp: Not used - UUIDs generated in application code (or use gen_random_uuid() for PostgreSQL 13+)
-- pg_trgm: Not used - text search handled via application-level semantic search (vector embeddings)
-- All functionality works without requiring any PostgreSQL extensions

-- ============================================================================
-- UNIVERSAL METADATA TEMPLATE
-- ============================================================================
-- This template can be instantiated for ANY domain

CREATE TABLE IF NOT EXISTS domain_risk_metadata (
    id SERIAL PRIMARY KEY,
    
    -- Domain identification
    domain_name VARCHAR(100) NOT NULL,  -- e.g., 'cybersecurity', 'hr_compliance', 'financial_risk'
    framework_name VARCHAR(100),        -- e.g., 'HIPAA', 'SOX', 'GDPR', 'GENERAL'
    
    -- Metadata classification
    metadata_category VARCHAR(50) NOT NULL,  -- 'severity', 'likelihood', 'threat', 'control', 'consequence'
    enum_type VARCHAR(100) NOT NULL,         -- Specific type within category
    
    -- Core attributes
    code VARCHAR(100) NOT NULL,
    description TEXT,
    abbreviation VARCHAR(50),
    
    -- Quantitative scores
    numeric_score DECIMAL(10,2) NOT NULL,     -- 0-100 normalized score
    priority_order INTEGER NOT NULL,           -- Ranking within type (1 = highest)
    severity_level INTEGER,                    -- 0-10 severity scale
    weight DECIMAL(5,3) DEFAULT 1.0,          -- Multiplicative weight
    
    -- Risk-specific scores (for threat/event metadata)
    risk_score DECIMAL(10,2),                 -- Combined risk score
    occurrence_likelihood DECIMAL(10,2),      -- Probability of occurrence (0-100)
    consequence_severity DECIMAL(10,2),       -- Impact if occurs (0-100)
    exploitability_score DECIMAL(10,2),       -- How easily exploitable (0-100)
    impact_score DECIMAL(10,2),               -- Potential impact (0-100)
    
    -- Context and reasoning
    rationale TEXT,                           -- Why this score/classification?
    data_source TEXT,                         -- Where does this come from?
    calculation_method TEXT,                  -- How is score calculated?
    data_indicators TEXT,                     -- What data signals indicate this?
    
    -- Relationships
    parent_code VARCHAR(100),                 -- Hierarchical relationships
    equivalent_codes JSONB,                   -- Cross-domain equivalents
    related_codes JSONB,                      -- Related codes in same domain
    
    -- Validation
    confidence_score DECIMAL(5,3),            -- LLM confidence (0-1)
    human_validated BOOLEAN DEFAULT FALSE,
    validation_notes TEXT,
    validation_date TIMESTAMP,
    validated_by VARCHAR(100),
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),                  -- 'llm_agent' or human user
    version INTEGER DEFAULT 1,                -- Version for tracking changes
    
    -- Constraints
    UNIQUE(domain_name, enum_type, code)
);

-- Indexes for performance
CREATE INDEX idx_domain_metadata_domain ON domain_risk_metadata(domain_name);
CREATE INDEX idx_domain_metadata_category ON domain_risk_metadata(metadata_category);
CREATE INDEX idx_domain_metadata_enum_type ON domain_risk_metadata(enum_type);
CREATE INDEX idx_domain_metadata_score ON domain_risk_metadata(numeric_score);
CREATE INDEX idx_domain_metadata_priority ON domain_risk_metadata(priority_order);
CREATE INDEX idx_domain_metadata_risk_score ON domain_risk_metadata(risk_score);
CREATE INDEX idx_domain_metadata_framework ON domain_risk_metadata(framework_name);
CREATE INDEX idx_domain_metadata_created_by ON domain_risk_metadata(created_by);

-- Full-text search index (using standard GIN index on text)
-- Note: For fuzzy text search, consider using PostgreSQL's full-text search (tsvector)
-- or application-level semantic search (vector embeddings)
CREATE INDEX idx_domain_metadata_description_text ON domain_risk_metadata(description) WHERE description IS NOT NULL;

-- ============================================================================
-- TRANSFER LEARNING PATTERN STORAGE
-- ============================================================================
-- Stores learned patterns from source domains for transfer to target domains

CREATE TABLE IF NOT EXISTS metadata_patterns (
    id SERIAL PRIMARY KEY,
    
    -- Pattern identification
    pattern_name VARCHAR(200) NOT NULL,
    pattern_type VARCHAR(50) NOT NULL,  -- 'structural', 'semantic', 'scoring', 'relationship'
    source_domain VARCHAR(100) NOT NULL,  -- Domain where pattern was learned
    
    -- Pattern description
    description TEXT,
    pattern_structure JSONB NOT NULL,  -- JSON structure of the pattern
    pattern_examples JSONB,            -- Example instantiations
    
    -- Pattern metadata
    confidence DECIMAL(5,3),           -- Confidence in pattern validity
    usage_count INTEGER DEFAULT 0,     -- How many times used for transfer
    success_rate DECIMAL(5,3),         -- Success rate of transfers using this pattern
    
    -- Relationships
    related_patterns JSONB,             -- Related pattern IDs
    applicable_domains JSONB,          -- Domains where this pattern applies
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100)
);

CREATE INDEX idx_patterns_type ON metadata_patterns(pattern_type);
CREATE INDEX idx_patterns_source_domain ON metadata_patterns(source_domain);
CREATE INDEX idx_patterns_name ON metadata_patterns(pattern_name);

-- ============================================================================
-- DOMAIN MAPPINGS
-- ============================================================================
-- Maps equivalent concepts across domains

CREATE TABLE IF NOT EXISTS cross_domain_mappings (
    id SERIAL PRIMARY KEY,
    
    -- Source mapping
    source_domain VARCHAR(100) NOT NULL,
    source_code VARCHAR(100) NOT NULL,
    source_enum_type VARCHAR(100) NOT NULL,
    
    -- Target mapping
    target_domain VARCHAR(100) NOT NULL,
    target_code VARCHAR(100) NOT NULL,
    target_enum_type VARCHAR(100) NOT NULL,
    
    -- Mapping metadata
    mapping_type VARCHAR(50),          -- 'exact', 'similar', 'analogical'
    similarity_score DECIMAL(5,3),      -- 0-1 similarity score
    mapping_rationale TEXT,             -- Why these are equivalent
    confidence DECIMAL(5,3),            -- Confidence in mapping
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    
    UNIQUE(source_domain, source_code, target_domain, target_code)
);

CREATE INDEX idx_mappings_source ON cross_domain_mappings(source_domain, source_code);
CREATE INDEX idx_mappings_target ON cross_domain_mappings(target_domain, target_code);
CREATE INDEX idx_mappings_type ON cross_domain_mappings(mapping_type);

-- ============================================================================
-- METADATA GENERATION HISTORY
-- ============================================================================
-- Tracks metadata generation sessions and their results

CREATE TABLE IF NOT EXISTS metadata_generation_sessions (
    id SERIAL PRIMARY KEY,
    session_id UUID,  -- Generated in application code or via trigger
    -- Note: UUID generation handled in application code to avoid extension dependencies
    -- For PostgreSQL 13+: Can use DEFAULT gen_random_uuid()
    -- For older versions: Generate UUIDs in application code
    
    -- Session context
    target_domain VARCHAR(100) NOT NULL,
    source_domains JSONB,               -- Domains used for transfer learning
    framework_name VARCHAR(100),
    
    -- Input documents
    document_count INTEGER,
    document_sources JSONB,             -- Sources of input documents
    
    -- Generation results
    metadata_entries_created INTEGER DEFAULT 0,
    patterns_applied JSONB,            -- Patterns used
    confidence_scores JSONB,            -- Confidence scores per entry
    
    -- Status
    status VARCHAR(50) DEFAULT 'in_progress',  -- 'in_progress', 'completed', 'failed'
    error_message TEXT,
    
    -- Metadata
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    created_by VARCHAR(100)
);

CREATE INDEX idx_sessions_domain ON metadata_generation_sessions(target_domain);
CREATE INDEX idx_sessions_status ON metadata_generation_sessions(status);
CREATE INDEX idx_sessions_session_id ON metadata_generation_sessions(session_id);

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Note: session_id UUID generation
-- Option 1 (Recommended): Generate UUIDs in application code (Python: uuid.uuid4())
-- Option 2: For PostgreSQL 13+, you can add: DEFAULT gen_random_uuid() to session_id column
-- Option 3: If uuid-ossp extension is available, use: DEFAULT uuid_generate_v4()

-- Trigger for domain_risk_metadata
CREATE TRIGGER update_domain_risk_metadata_updated_at
    BEFORE UPDATE ON domain_risk_metadata
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for metadata_patterns
CREATE TRIGGER update_metadata_patterns_updated_at
    BEFORE UPDATE ON metadata_patterns
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- View: Domain metadata summary
CREATE OR REPLACE VIEW domain_metadata_summary AS
SELECT 
    domain_name,
    framework_name,
    metadata_category,
    enum_type,
    COUNT(*) as entry_count,
    AVG(numeric_score) as avg_score,
    MAX(numeric_score) as max_score,
    MIN(numeric_score) as min_score,
    MAX(updated_at) as last_updated
FROM domain_risk_metadata
GROUP BY domain_name, framework_name, metadata_category, enum_type;

-- View: High-risk metadata entries
CREATE OR REPLACE VIEW high_risk_metadata AS
SELECT 
    id,
    domain_name,
    framework_name,
    metadata_category,
    enum_type,
    code,
    description,
    numeric_score,
    risk_score,
    priority_order,
    rationale
FROM domain_risk_metadata
WHERE numeric_score >= 80 OR risk_score >= 80
ORDER BY COALESCE(risk_score, numeric_score) DESC;

-- View: Cross-domain risk comparisons
CREATE OR REPLACE VIEW cross_domain_risk_comparison AS
SELECT 
    cdm.source_domain,
    cdm.source_code,
    cdm.target_domain,
    cdm.target_code,
    cdm.similarity_score,
    src.numeric_score as source_score,
    tgt.numeric_score as target_score,
    ABS(src.numeric_score - tgt.numeric_score) as score_difference
FROM cross_domain_mappings cdm
JOIN domain_risk_metadata src 
    ON cdm.source_domain = src.domain_name 
    AND cdm.source_code = src.code
JOIN domain_risk_metadata tgt 
    ON cdm.target_domain = tgt.domain_name 
    AND cdm.target_code = tgt.code;

-- ============================================================================
-- INITIAL DATA: Example cybersecurity metadata (source domain)
-- ============================================================================
-- This provides a baseline for transfer learning

INSERT INTO domain_risk_metadata (
    domain_name, framework_name, metadata_category, enum_type, code, description,
    numeric_score, priority_order, severity_level, weight, risk_score,
    occurrence_likelihood, consequence_severity, rationale, created_by
) VALUES
    -- Threat/Event metadata examples
    ('cybersecurity', 'GENERAL', 'threat', 'breach_method', 'zero_day', 
     'Zero Day Exploit', 95.0, 1, 10, 1.0, 95.0, 30.0, 95.0,
     'Zero-day exploits are extremely dangerous as they target unknown vulnerabilities. Low likelihood (30) due to rarity, but extreme consequences (95) if successful. Risk score (95) reflects critical priority.',
     'system'),
    
    ('cybersecurity', 'GENERAL', 'threat', 'breach_method', 'compromised_credentials',
     'Compromised Credentials', 90.0, 2, 9, 0.95, 90.0, 85.0, 80.0,
     'Credential compromise is common (likelihood=85) and has high impact (80). Risk score (90) indicates critical priority for credential management.',
     'system'),
    
    -- Severity metadata examples
    ('cybersecurity', 'GENERAL', 'severity', 'risk_level', 'CRITICAL',
     'Critical Risk', 100.0, 1, 10, 1.0, NULL, NULL, NULL,
     'Critical risks require immediate attention and have severe potential consequences.',
     'system'),
    
    ('cybersecurity', 'GENERAL', 'severity', 'risk_level', 'HIGH',
     'High Risk', 75.0, 2, 8, 0.75, NULL, NULL, NULL,
     'High risks require prompt attention and have significant potential consequences.',
     'system'),
    
    -- Impact metadata examples
    ('cybersecurity', 'GENERAL', 'impact', 'impact_class', 'Mission Critical',
     'Mission Critical to Organization', 100.0, 1, 10, 1.0, NULL, NULL, NULL,
     'Mission critical impacts affect core business operations and require immediate response.',
     'system'),
    
    ('cybersecurity', 'GENERAL', 'impact', 'impact_class', 'Critical',
     'Critical Business Impact', 70.0, 2, 7, 0.7, NULL, NULL, NULL,
     'Critical impacts affect important business functions and require prompt response.',
     'system')
ON CONFLICT (domain_name, enum_type, code) DO NOTHING;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE domain_risk_metadata IS 'Universal metadata template for risk evaluation across any compliance domain';
COMMENT ON TABLE metadata_patterns IS 'Stores learned patterns from source domains for transfer learning';
COMMENT ON TABLE cross_domain_mappings IS 'Maps equivalent risk concepts across different domains';
COMMENT ON TABLE metadata_generation_sessions IS 'Tracks metadata generation sessions and their results';

COMMENT ON COLUMN domain_risk_metadata.domain_name IS 'Domain identifier (e.g., cybersecurity, hr_compliance, financial_risk)';
COMMENT ON COLUMN domain_risk_metadata.metadata_category IS 'Category: severity, likelihood, threat, control, consequence';
COMMENT ON COLUMN domain_risk_metadata.equivalent_codes IS 'JSON array of equivalent codes in other domains';
COMMENT ON COLUMN metadata_patterns.pattern_structure IS 'JSON structure defining the pattern schema';
COMMENT ON COLUMN cross_domain_mappings.mapping_type IS 'Type: exact (identical), similar (close match), analogical (conceptually equivalent)';


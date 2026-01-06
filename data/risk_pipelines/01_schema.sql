-- ============================================================================
-- Universal Risk Platform - Database Schema
-- ============================================================================
-- Version: 1.0
-- PostgreSQL 15+ with pgvector extension required
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gin;

-- ============================================================================
-- CORE RISK TYPES
-- ============================================================================

-- Likelihood parameter type
CREATE TYPE likelihood_parameter AS (
    param_name TEXT,
    param_value DECIMAL(10,2),
    param_weight DECIMAL(5,3),
    max_value DECIMAL(10,2),
    decay_function TEXT,
    decay_rate DECIMAL(5,3),
    time_delta DECIMAL(10,2),
    inverse BOOLEAN,
    threshold_low DECIMAL(10,2),
    threshold_high DECIMAL(10,2)
);

-- Impact parameter type
CREATE TYPE impact_parameter AS (
    param_name TEXT,
    param_value DECIMAL(10,2),
    param_weight DECIMAL(5,3),
    max_value DECIMAL(10,2),
    impact_category TEXT,
    amplification_factor DECIMAL(5,3),
    decay_function TEXT,
    decay_rate DECIMAL(5,3),
    time_delta DECIMAL(10,2),
    inverse BOOLEAN,
    threshold_critical DECIMAL(10,2),
    threshold_high DECIMAL(10,2),
    threshold_medium DECIMAL(10,2)
);

-- ============================================================================
-- KNOWLEDGE BASE TABLES
-- ============================================================================

-- Risk patterns (Transfer learning knowledge base)
CREATE TABLE risk_patterns (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(50) NOT NULL,
    pattern_name VARCHAR(200) NOT NULL,
    pattern_description TEXT,
    risk_type VARCHAR(50),
    
    -- Semantic embedding for similarity search
    embedding_vector VECTOR(1536) NOT NULL,
    
    -- Parameter template
    parameter_template JSONB NOT NULL,
    
    -- Performance metrics
    prediction_accuracy DECIMAL(5,2) DEFAULT 0.0,
    usage_count INTEGER DEFAULT 0,
    transferability_score DECIMAL(5,2) DEFAULT 0.7,
    
    -- Transfer learning metadata
    source_domains TEXT[],
    compatible_domains TEXT[],
    
    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(100)
);

-- Indexes for risk_patterns
CREATE INDEX idx_risk_patterns_domain ON risk_patterns(domain);
CREATE INDEX idx_risk_patterns_risk_type ON risk_patterns(risk_type);
CREATE INDEX idx_risk_patterns_accuracy ON risk_patterns(prediction_accuracy DESC);
CREATE INDEX idx_risk_patterns_embedding ON risk_patterns 
    USING ivfflat (embedding_vector vector_cosine_ops) WITH (lists = 100);

-- Risk parameter mappings (Cross-domain parameter relationships)
CREATE TABLE risk_parameter_mappings (
    id SERIAL PRIMARY KEY,
    source_domain VARCHAR(50) NOT NULL,
    target_domain VARCHAR(50) NOT NULL,
    
    -- Parameter mapping
    source_parameter VARCHAR(200) NOT NULL,
    target_parameter VARCHAR(200) NOT NULL,
    
    -- Mapping metadata
    mapping_confidence DECIMAL(5,2),
    weight_transfer_factor DECIMAL(5,3),
    decay_function_similarity DECIMAL(5,2),
    
    -- Semantic embeddings
    source_embedding VECTOR(1536),
    target_embedding VECTOR(1536),
    
    -- Usage tracking
    usage_count INTEGER DEFAULT 0,
    success_rate DECIMAL(5,2),
    
    -- Audit
    created_by VARCHAR(50) DEFAULT 'llm_transfer_learning',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for parameter mappings
CREATE INDEX idx_param_mappings_domains ON risk_parameter_mappings(source_domain, target_domain);
CREATE INDEX idx_param_mappings_source ON risk_parameter_mappings(source_parameter);
CREATE INDEX idx_param_mappings_target ON risk_parameter_mappings(target_parameter);

-- Domain schemas (Schema repository with semantic annotations)
CREATE TABLE domain_schemas (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(50) NOT NULL,
    table_name VARCHAR(200) NOT NULL,
    schema_json JSONB NOT NULL,
    
    -- LLM-generated semantic understanding
    semantic_summary TEXT,
    risk_relevant_columns JSONB,
    entity_relationships JSONB,
    temporal_columns JSONB,
    
    -- Schema embedding
    schema_embedding VECTOR(1536),
    
    -- Metadata
    version VARCHAR(20) DEFAULT '1.0',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for domain schemas
CREATE UNIQUE INDEX idx_domain_schemas_unique ON domain_schemas(domain, table_name, version) 
    WHERE is_active = TRUE;
CREATE INDEX idx_domain_schemas_embedding ON domain_schemas 
    USING ivfflat (schema_embedding vector_cosine_ops) WITH (lists = 50);

-- ============================================================================
-- ML LEARNED PARAMETERS
-- ============================================================================

-- ML-learned parameters (from traditional ML models)
CREATE TABLE ml_learned_parameters (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(50) NOT NULL,
    config JSONB NOT NULL,
    
    -- Model metadata
    model_type VARCHAR(50),  -- 'xgboost', 'random_forest', 'neural_net'
    model_version VARCHAR(20),
    training_samples INTEGER,
    validation_accuracy DECIMAL(5,2),
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    trained_by VARCHAR(100)
);

-- Index for active parameters
CREATE INDEX idx_ml_params_domain_active ON ml_learned_parameters(domain, is_active);

-- ============================================================================
-- OUTCOME TRACKING & FEEDBACK
-- ============================================================================

-- Risk assessments (History of all assessments)
CREATE TABLE risk_assessments (
    id SERIAL PRIMARY KEY,
    entity_id VARCHAR(200) NOT NULL,
    domain VARCHAR(50) NOT NULL,
    risk_specification TEXT,
    
    -- Predictions
    predicted_risk DECIMAL(10,2) NOT NULL,
    predicted_likelihood DECIMAL(10,2) NOT NULL,
    predicted_impact DECIMAL(10,2) NOT NULL,
    risk_level VARCHAR(20),
    
    -- Parameters used
    likelihood_parameters JSONB,
    impact_parameters JSONB,
    
    -- Transfer learning metadata
    transfer_confidence DECIMAL(5,2),
    similar_patterns_used INTEGER[],
    
    -- Explanation
    explanation TEXT,
    recommendations JSONB,
    
    -- Audit
    assessed_at TIMESTAMP DEFAULT NOW(),
    assessed_by VARCHAR(100)
);

-- Indexes for assessments
CREATE INDEX idx_risk_assessments_entity ON risk_assessments(entity_id, domain);
CREATE INDEX idx_risk_assessments_date ON risk_assessments(assessed_at DESC);
CREATE INDEX idx_risk_assessments_risk_level ON risk_assessments(risk_level, domain);

-- Risk outcomes (Actual outcomes for feedback learning)
CREATE TABLE risk_outcomes (
    id SERIAL PRIMARY KEY,
    assessment_id INTEGER REFERENCES risk_assessments(id),
    entity_id VARCHAR(200) NOT NULL,
    domain VARCHAR(50) NOT NULL,
    
    -- Predictions (denormalized for analysis)
    predicted_risk DECIMAL(10,2),
    predicted_likelihood DECIMAL(10,2),
    predicted_impact DECIMAL(10,2),
    
    -- Actual outcome
    actual_outcome BOOLEAN NOT NULL,
    outcome_severity DECIMAL(10,2),
    outcome_date TIMESTAMP,
    outcome_description TEXT,
    
    -- Error analysis
    prediction_error DECIMAL(10,2),
    absolute_error DECIMAL(10,2),
    
    -- Context
    parameters_used JSONB,
    
    -- Audit
    recorded_at TIMESTAMP DEFAULT NOW(),
    recorded_by VARCHAR(100)
);

-- Indexes for outcomes
CREATE INDEX idx_risk_outcomes_assessment ON risk_outcomes(assessment_id);
CREATE INDEX idx_risk_outcomes_entity ON risk_outcomes(entity_id, domain);
CREATE INDEX idx_risk_outcomes_date ON risk_outcomes(outcome_date);

-- ============================================================================
-- AUDIT & COMPLIANCE
-- ============================================================================

-- Audit log
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(200),
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id VARCHAR(200),
    
    -- Request/Response
    request_data JSONB,
    response_data JSONB,
    
    -- Status
    status VARCHAR(20),  -- 'success', 'error'
    error_message TEXT,
    
    -- Performance
    duration_ms INTEGER,
    
    -- Context
    ip_address INET,
    user_agent TEXT,
    
    -- Timestamp
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Indexes for audit log
CREATE INDEX idx_audit_log_user ON audit_log(user_id, timestamp DESC);
CREATE INDEX idx_audit_log_action ON audit_log(action, timestamp DESC);
CREATE INDEX idx_audit_log_entity ON audit_log(entity_type, entity_id);

-- ============================================================================
-- HELPER VIEWS
-- ============================================================================

-- Pattern performance view
CREATE VIEW v_pattern_performance AS
SELECT 
    rp.id,
    rp.domain,
    rp.pattern_name,
    rp.prediction_accuracy,
    rp.usage_count,
    rp.transferability_score,
    COUNT(DISTINCT ro.id) as outcome_count,
    AVG(100 - ro.prediction_error) as actual_accuracy,
    AVG(ro.prediction_error) as avg_error
FROM risk_patterns rp
LEFT JOIN risk_assessments ra ON rp.id = ANY(ra.similar_patterns_used)
LEFT JOIN risk_outcomes ro ON ra.id = ro.assessment_id
GROUP BY rp.id, rp.domain, rp.pattern_name, rp.prediction_accuracy, 
         rp.usage_count, rp.transferability_score;

-- Transfer learning success view
CREATE VIEW v_transfer_learning_success AS
SELECT 
    source_rp.domain as source_domain,
    target_ra.domain as target_domain,
    COUNT(*) as transfer_count,
    AVG(target_ra.transfer_confidence) as avg_confidence,
    AVG(100 - COALESCE(ro.prediction_error, 0)) as avg_accuracy
FROM risk_assessments target_ra
JOIN risk_patterns source_rp ON source_rp.id = ANY(target_ra.similar_patterns_used)
LEFT JOIN risk_outcomes ro ON target_ra.id = ro.assessment_id
WHERE target_ra.domain != source_rp.domain
GROUP BY source_rp.domain, target_ra.domain;

-- Recent assessments summary
CREATE VIEW v_recent_assessments AS
SELECT 
    domain,
    risk_level,
    COUNT(*) as count,
    AVG(predicted_risk) as avg_risk,
    MAX(assessed_at) as last_assessed
FROM risk_assessments
WHERE assessed_at >= NOW() - INTERVAL '30 days'
GROUP BY domain, risk_level;

-- ============================================================================
-- MATERIALIZED VIEWS (for performance)
-- ============================================================================

-- Domain statistics
CREATE MATERIALIZED VIEW mv_domain_statistics AS
SELECT 
    domain,
    COUNT(DISTINCT entity_id) as unique_entities,
    COUNT(*) as total_assessments,
    AVG(predicted_risk) as avg_risk,
    AVG(transfer_confidence) as avg_transfer_confidence,
    MAX(assessed_at) as last_assessment
FROM risk_assessments
GROUP BY domain;

CREATE UNIQUE INDEX ON mv_domain_statistics(domain);

-- Pattern usage statistics
CREATE MATERIALIZED VIEW mv_pattern_usage AS
SELECT 
    rp.id as pattern_id,
    rp.domain,
    rp.pattern_name,
    COUNT(ra.id) as usage_count,
    AVG(ra.transfer_confidence) as avg_confidence,
    COUNT(DISTINCT ra.domain) as domains_used_in
FROM risk_patterns rp
LEFT JOIN risk_assessments ra ON rp.id = ANY(ra.similar_patterns_used)
GROUP BY rp.id, rp.domain, rp.pattern_name;

CREATE UNIQUE INDEX ON mv_pattern_usage(pattern_id);

-- ============================================================================
-- FUNCTIONS FOR MATERIALIZED VIEW REFRESH
-- ============================================================================

CREATE OR REPLACE FUNCTION refresh_statistics()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_domain_statistics;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_pattern_usage;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- PARTITIONING (for large-scale deployments)
-- ============================================================================

-- Partition audit_log by month
CREATE TABLE audit_log_template (
    LIKE audit_log INCLUDING ALL
) PARTITION BY RANGE (timestamp);

-- Example partitions (create monthly)
-- CREATE TABLE audit_log_2026_01 PARTITION OF audit_log_template
--     FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

-- ============================================================================
-- COMMENTS & DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE risk_patterns IS 'Universal risk pattern knowledge base for transfer learning';
COMMENT ON TABLE risk_parameter_mappings IS 'Cross-domain parameter mappings learned from successful transfers';
COMMENT ON TABLE domain_schemas IS 'Repository of domain schemas with semantic annotations';
COMMENT ON TABLE ml_learned_parameters IS 'ML-optimized parameters for specific domains';
COMMENT ON TABLE risk_assessments IS 'History of all risk assessments performed';
COMMENT ON TABLE risk_outcomes IS 'Actual outcomes for feedback and continuous learning';
COMMENT ON TABLE audit_log IS 'Comprehensive audit trail for compliance';

COMMENT ON COLUMN risk_patterns.embedding_vector IS '1536-dimensional embedding from text-embedding-3-large';
COMMENT ON COLUMN risk_patterns.transferability_score IS 'How well this pattern transfers to other domains (0-1)';
COMMENT ON COLUMN risk_assessments.transfer_confidence IS 'Confidence in transfer learning (0-1)';

-- ============================================================================
-- SAMPLE DATA INSERTION
-- ============================================================================

-- Insert default risk classification enum values
CREATE TYPE risk_level_enum AS ENUM ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'MINIMAL');

-- Grant appropriate permissions
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO risk_platform_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO risk_platform_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO risk_platform_app;

-- ============================================================================
-- INITIALIZATION COMPLETE
-- ============================================================================

SELECT 'Universal Risk Platform Schema v1.0 initialized successfully' AS status;

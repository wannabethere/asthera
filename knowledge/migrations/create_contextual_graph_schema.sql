-- ============================================================================
-- POSTGRESQL: Core Structured Data for Contextual Graph
-- ============================================================================
-- Based on hybrid_search.md architecture
-- This schema stores structured entities that are referenced by vector store

-- Core entities with minimal context
CREATE TABLE IF NOT EXISTS controls (
    control_id VARCHAR(100) PRIMARY KEY,
    framework VARCHAR(50) NOT NULL,
    control_name TEXT NOT NULL,
    control_description TEXT,
    category VARCHAR(100),
    
    -- Basic metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Vector store references
    vector_doc_id VARCHAR(100),  -- Reference to vector store document
    embedding_version VARCHAR(50),
    
    -- Indexes
    CONSTRAINT controls_framework_idx UNIQUE (framework, control_id)
);

CREATE INDEX IF NOT EXISTS idx_controls_framework ON controls(framework);
CREATE INDEX IF NOT EXISTS idx_controls_category ON controls(category);
CREATE INDEX IF NOT EXISTS idx_controls_vector_doc ON controls(vector_doc_id);

CREATE TABLE IF NOT EXISTS requirements (
    requirement_id VARCHAR(100) PRIMARY KEY,
    control_id VARCHAR(100) REFERENCES controls(control_id) ON DELETE CASCADE,
    requirement_text TEXT NOT NULL,
    requirement_type VARCHAR(50),  -- 'SHALL', 'SHOULD', 'MAY', 'GUIDANCE'
    
    -- Vector store references
    vector_doc_id VARCHAR(100),
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_requirements_control ON requirements(control_id);
CREATE INDEX IF NOT EXISTS idx_requirements_type ON requirements(requirement_type);
CREATE INDEX IF NOT EXISTS idx_requirements_vector_doc ON requirements(vector_doc_id);

CREATE TABLE IF NOT EXISTS evidence_types (
    evidence_id VARCHAR(100) PRIMARY KEY,
    evidence_name TEXT NOT NULL,
    evidence_category VARCHAR(50),  -- 'log', 'report', 'configuration', 'documentation'
    collection_method TEXT,
    
    -- Vector store references
    vector_doc_id VARCHAR(100),
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_evidence_category ON evidence_types(evidence_category);
CREATE INDEX IF NOT EXISTS idx_evidence_vector_doc ON evidence_types(vector_doc_id);

-- Hard relationships (context-independent)
CREATE TABLE IF NOT EXISTS control_requirement_mapping (
    control_id VARCHAR(100) REFERENCES controls(control_id) ON DELETE CASCADE,
    requirement_id VARCHAR(100) REFERENCES requirements(requirement_id) ON DELETE CASCADE,
    is_mandatory BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (control_id, requirement_id)
);

CREATE INDEX IF NOT EXISTS idx_control_req_mapping_control ON control_requirement_mapping(control_id);
CREATE INDEX IF NOT EXISTS idx_control_req_mapping_req ON control_requirement_mapping(requirement_id);

-- Measurement data (time-series, transactional)
CREATE TABLE IF NOT EXISTS compliance_measurements (
    measurement_id SERIAL PRIMARY KEY,
    control_id VARCHAR(100) REFERENCES controls(control_id) ON DELETE CASCADE,
    measured_value DECIMAL(10,2),
    measurement_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    passed BOOLEAN,
    
    -- Context reference
    context_id VARCHAR(100),  -- References vector store context
    
    -- Additional metadata
    data_source VARCHAR(200),
    measurement_method VARCHAR(100),
    quality_score DECIMAL(5,2),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_measurements_date ON compliance_measurements(measurement_date);
CREATE INDEX IF NOT EXISTS idx_measurements_control ON compliance_measurements(control_id);
CREATE INDEX IF NOT EXISTS idx_measurements_context ON compliance_measurements(context_id);
CREATE INDEX IF NOT EXISTS idx_measurements_passed ON compliance_measurements(passed);

-- Aggregated analytics (PostgreSQL is great for this)
CREATE TABLE IF NOT EXISTS control_risk_analytics (
    control_id VARCHAR(100) PRIMARY KEY REFERENCES controls(control_id) ON DELETE CASCADE,
    avg_compliance_score DECIMAL(5,2),
    trend VARCHAR(20),  -- 'improving', 'stable', 'degrading'
    last_failure_date DATE,
    failure_count_30d INTEGER DEFAULT 0,
    failure_count_90d INTEGER DEFAULT 0,
    
    -- Risk metrics
    current_risk_score DECIMAL(5,2),
    risk_level VARCHAR(20),  -- 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_analytics_trend ON control_risk_analytics(trend);
CREATE INDEX IF NOT EXISTS idx_analytics_risk_level ON control_risk_analytics(risk_level);

-- ============================================================================
-- Views for Common Queries
-- ============================================================================

CREATE OR REPLACE VIEW control_summary AS
SELECT 
    c.control_id,
    c.framework,
    c.control_name,
    c.category,
    COUNT(DISTINCT cr.requirement_id) as requirement_count,
    COUNT(DISTINCT cm.measurement_id) as measurement_count,
    COALESCE(cra.avg_compliance_score, 0) as avg_compliance_score,
    COALESCE(cra.trend, 'unknown') as trend,
    COALESCE(cra.risk_level, 'UNKNOWN') as risk_level
FROM controls c
LEFT JOIN control_requirement_mapping cr ON c.control_id = cr.control_id
LEFT JOIN compliance_measurements cm ON c.control_id = cm.control_id
LEFT JOIN control_risk_analytics cra ON c.control_id = cra.control_id
GROUP BY c.control_id, c.framework, c.control_name, c.category, 
         cra.avg_compliance_score, cra.trend, cra.risk_level;

CREATE OR REPLACE VIEW context_control_metrics AS
SELECT 
    cm.context_id,
    c.control_id,
    c.framework,
    c.control_name,
    COUNT(cm.measurement_id) as measurement_count,
    AVG(cm.measured_value) as avg_value,
    SUM(CASE WHEN cm.passed = false THEN 1 ELSE 0 END) as failure_count,
    MAX(cm.measurement_date) as last_measurement_date
FROM compliance_measurements cm
JOIN controls c ON cm.control_id = c.control_id
GROUP BY cm.context_id, c.control_id, c.framework, c.control_name;

-- ============================================================================
-- Functions for Analytics
-- ============================================================================

CREATE OR REPLACE FUNCTION update_control_risk_analytics()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO control_risk_analytics (
        control_id,
        avg_compliance_score,
        trend,
        last_failure_date,
        failure_count_30d,
        failure_count_90d,
        current_risk_score,
        risk_level,
        updated_at
    )
    SELECT 
        NEW.control_id,
        AVG(measured_value) as avg_compliance_score,
        CASE 
            WHEN AVG(measured_value) > LAG(AVG(measured_value)) OVER (PARTITION BY control_id ORDER BY measurement_date) THEN 'improving'
            WHEN AVG(measured_value) < LAG(AVG(measured_value)) OVER (PARTITION BY control_id ORDER BY measurement_date) THEN 'degrading'
            ELSE 'stable'
        END as trend,
        MAX(CASE WHEN passed = false THEN measurement_date::DATE END) as last_failure_date,
        COUNT(*) FILTER (WHERE passed = false AND measurement_date >= NOW() - INTERVAL '30 days') as failure_count_30d,
        COUNT(*) FILTER (WHERE passed = false AND measurement_date >= NOW() - INTERVAL '90 days') as failure_count_90d,
        CASE 
            WHEN AVG(measured_value) < 50 THEN 25
            WHEN AVG(measured_value) < 70 THEN 15
            WHEN AVG(measured_value) < 85 THEN 8
            ELSE 3
        END as current_risk_score,
        CASE 
            WHEN AVG(measured_value) < 50 THEN 'CRITICAL'
            WHEN AVG(measured_value) < 70 THEN 'HIGH'
            WHEN AVG(measured_value) < 85 THEN 'MEDIUM'
            ELSE 'LOW'
        END as risk_level,
        CURRENT_TIMESTAMP
    FROM compliance_measurements
    WHERE control_id = NEW.control_id
    GROUP BY control_id
    ON CONFLICT (control_id) DO UPDATE SET
        avg_compliance_score = EXCLUDED.avg_compliance_score,
        trend = EXCLUDED.trend,
        last_failure_date = EXCLUDED.last_failure_date,
        failure_count_30d = EXCLUDED.failure_count_30d,
        failure_count_90d = EXCLUDED.failure_count_90d,
        current_risk_score = EXCLUDED.current_risk_score,
        risk_level = EXCLUDED.risk_level,
        updated_at = CURRENT_TIMESTAMP;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_risk_analytics
AFTER INSERT OR UPDATE ON compliance_measurements
FOR EACH ROW
EXECUTE FUNCTION update_control_risk_analytics();

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE controls IS 'Core control entities with framework and category information';
COMMENT ON TABLE requirements IS 'Atomic requirements that controls must satisfy';
COMMENT ON TABLE evidence_types IS 'Types of evidence that prove compliance';
COMMENT ON TABLE control_requirement_mapping IS 'Hard relationships between controls and requirements';
COMMENT ON TABLE compliance_measurements IS 'Time-series measurement data for controls';
COMMENT ON TABLE control_risk_analytics IS 'Aggregated analytics and risk scores for controls';


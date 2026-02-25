-- ============================================================================
-- Security Intelligence Database Tables - PHASE 1 ONLY (Critical/MVP)
-- ============================================================================
-- This script creates only the Phase 1 (critical) tables required for MVP.
-- Use this if you want to start with just the essential tables.
-- 
-- Usage:
--   psql -U postgres -d your_database -f create_phase1_only.sql
-- ============================================================================

BEGIN;

-- ============================================================================
-- PHASE 1 - CRITICAL TABLES (MVP)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. CVE → ATT&CK Technique Mapping
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cve_attack_mapping (
    id SERIAL PRIMARY KEY,
    cve_id VARCHAR(20) NOT NULL,
    attack_technique_id VARCHAR(20),
    attack_tactic VARCHAR(50),
    mapping_source VARCHAR(50),
    confidence_score FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    notes TEXT,
    CONSTRAINT uq_cve_attack UNIQUE (cve_id, attack_technique_id)
);

CREATE INDEX IF NOT EXISTS idx_cve_attack_cve ON cve_attack_mapping(cve_id);
CREATE INDEX IF NOT EXISTS idx_cve_attack_tech ON cve_attack_mapping(attack_technique_id);
CREATE INDEX IF NOT EXISTS idx_cve_attack_tactic ON cve_attack_mapping(attack_tactic);
CREATE INDEX IF NOT EXISTS idx_cve_attack_source ON cve_attack_mapping(mapping_source);

-- ----------------------------------------------------------------------------
-- 2. ATT&CK Technique → Control Mapping
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS attack_technique_control_mapping (
    id SERIAL PRIMARY KEY,
    attack_technique_id VARCHAR(20) NOT NULL,
    control_id VARCHAR(128),
    mitigation_effectiveness VARCHAR(20),
    mapping_source VARCHAR(50),
    confidence_score FLOAT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_attack_control UNIQUE (attack_technique_id, control_id)
);

CREATE INDEX IF NOT EXISTS idx_attack_control_tech ON attack_technique_control_mapping(attack_technique_id);
CREATE INDEX IF NOT EXISTS idx_attack_control_ctrl ON attack_technique_control_mapping(control_id);
CREATE INDEX IF NOT EXISTS idx_attack_control_effectiveness ON attack_technique_control_mapping(mitigation_effectiveness);

-- Add foreign key only if controls table exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'controls') THEN
        ALTER TABLE attack_technique_control_mapping
        ADD CONSTRAINT fk_attack_control_control_id
        FOREIGN KEY (control_id) REFERENCES controls(id) ON DELETE CASCADE;
    END IF;
END $$;

-- ----------------------------------------------------------------------------
-- 3. CPE Dictionary
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cpe_dictionary (
    cpe_uri VARCHAR(255) PRIMARY KEY,
    vendor VARCHAR(255),
    product VARCHAR(255),
    version VARCHAR(100),
    update_version VARCHAR(100),
    edition VARCHAR(100),
    language VARCHAR(50),
    sw_edition VARCHAR(100),
    target_sw VARCHAR(100),
    target_hw VARCHAR(100),
    other VARCHAR(100),
    cpe_title TEXT,
    deprecated BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cpe_vendor_product ON cpe_dictionary(vendor, product);
CREATE INDEX IF NOT EXISTS idx_cpe_product_version ON cpe_dictionary(product, version);
CREATE INDEX IF NOT EXISTS idx_cpe_vendor ON cpe_dictionary(vendor);
CREATE INDEX IF NOT EXISTS idx_cpe_product ON cpe_dictionary(product);
CREATE INDEX IF NOT EXISTS idx_cpe_deprecated ON cpe_dictionary(deprecated);

-- ----------------------------------------------------------------------------
-- 4. CVE → CPE Affected (Junction Table)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cve_cpe_affected (
    id SERIAL PRIMARY KEY,
    cve_id VARCHAR(20) NOT NULL,
    cpe_uri VARCHAR(255) REFERENCES cpe_dictionary(cpe_uri) ON DELETE CASCADE,
    version_start VARCHAR(100),
    version_end VARCHAR(100),
    version_start_including BOOLEAN DEFAULT TRUE,
    version_end_including BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_cve_cpe UNIQUE (cve_id, cpe_uri)
);

CREATE INDEX IF NOT EXISTS idx_cve_cpe_cve ON cve_cpe_affected(cve_id);
CREATE INDEX IF NOT EXISTS idx_cve_cpe_uri ON cve_cpe_affected(cpe_uri);
CREATE INDEX IF NOT EXISTS idx_cve_cpe_version_range ON cve_cpe_affected(version_start, version_end);

-- ----------------------------------------------------------------------------
-- 5. CVE Cache (Optional but recommended)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cve_cache (
    id SERIAL PRIMARY KEY,
    cve_id VARCHAR(20) UNIQUE NOT NULL,
    nvd_data JSONB,
    epss_data JSONB,
    kev_data JSONB,
    cached_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    source VARCHAR(50) DEFAULT 'nvd_api'
);

CREATE INDEX IF NOT EXISTS idx_cve_cache_cve ON cve_cache(cve_id);
CREATE INDEX IF NOT EXISTS idx_cve_cache_expires ON cve_cache(expires_at);

-- ============================================================================
-- CREATE TRIGGERS FOR UPDATED_AT TIMESTAMPS
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_cve_attack_mapping_updated_at
    BEFORE UPDATE ON cve_attack_mapping
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_attack_technique_control_mapping_updated_at
    BEFORE UPDATE ON attack_technique_control_mapping
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_cpe_dictionary_updated_at
    BEFORE UPDATE ON cpe_dictionary
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMIT;

-- Verification
SELECT 
    'Phase 1 tables created successfully!' as status,
    COUNT(*) as table_count
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
      'cve_attack_mapping',
      'attack_technique_control_mapping',
      'cpe_dictionary',
      'cve_cpe_affected',
      'cve_cache'
  );

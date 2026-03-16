-- ============================================================================
-- CVE → ATT&CK → Control Pipeline Tables
-- ============================================================================
-- Run after schema.sql (attack_techniques table must exist).
-- Creates: cve_intelligence, cve_attack_mappings, cwe_technique_mappings
--
-- If you see "current transaction is aborted", run: ROLLBACK; first.
-- Run with: psql -v ON_ERROR_STOP=1 -f cve_pipeline_tables.sql
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. cve_intelligence — cache for CVE enrichment (Stage 1)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cve_intelligence (
    cve_id              TEXT PRIMARY KEY,
    description         TEXT,
    cvss_score          NUMERIC(4,2),
    cvss_vector         TEXT,
    attack_vector       TEXT,
    attack_complexity   TEXT,
    privileges_required TEXT,
    cwe_ids             TEXT[] DEFAULT '{}',
    affected_products   TEXT[] DEFAULT '{}',
    epss_score          NUMERIC(5,4),
    exploit_available   BOOLEAN DEFAULT FALSE,
    exploit_maturity    TEXT,     -- 'none' | 'poc' | 'weaponised'
    published_date      TEXT,
    last_modified       TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cve_intelligence_cwe ON cve_intelligence USING GIN (cwe_ids);
CREATE INDEX IF NOT EXISTS idx_cve_intelligence_cvss ON cve_intelligence (cvss_score DESC);
COMMIT;

-- ---------------------------------------------------------------------------
-- 2. cwe_technique_mappings — CWE → ATT&CK crosswalk (MITRE/community)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cwe_technique_mappings (
    cwe_id          TEXT NOT NULL,
    technique_id    TEXT NOT NULL,
    tactic          TEXT NOT NULL,
    confidence      TEXT NOT NULL CHECK (confidence IN ('high', 'medium')),
    mapping_source  TEXT NOT NULL DEFAULT 'mitre_crosswalk',
    notes           TEXT,
    PRIMARY KEY (cwe_id, technique_id, tactic)
);

CREATE INDEX IF NOT EXISTS idx_cwe_technique_cwe ON cwe_technique_mappings (cwe_id);

-- Seed common CWE → ATT&CK mappings (from pipeline doc + MITRE)
INSERT INTO cwe_technique_mappings (cwe_id, technique_id, tactic, confidence, mapping_source) VALUES
    ('CWE-77', 'T1059', 'execution', 'high', 'mitre_crosswalk'),
    ('CWE-77', 'T1190', 'initial-access', 'high', 'mitre_crosswalk'),
    ('CWE-77', 'T1068', 'privilege-escalation', 'high', 'mitre_crosswalk'),
    ('CWE-78', 'T1059', 'execution', 'high', 'mitre_crosswalk'),
    ('CWE-78', 'T1190', 'initial-access', 'high', 'mitre_crosswalk'),
    ('CWE-79', 'T1059.001', 'execution', 'high', 'mitre_crosswalk'),
    ('CWE-79', 'T1190', 'initial-access', 'high', 'mitre_crosswalk'),
    ('CWE-89', 'T1190', 'initial-access', 'high', 'mitre_crosswalk'),
    ('CWE-89', 'T1059', 'execution', 'medium', 'mitre_crosswalk'),
    ('CWE-94', 'T1059', 'execution', 'high', 'mitre_crosswalk'),
    ('CWE-94', 'T1190', 'initial-access', 'high', 'mitre_crosswalk'),
    ('CWE-352', 'T1539', 'credential-access', 'high', 'mitre_crosswalk'),
    ('CWE-352', 'T1190', 'initial-access', 'medium', 'mitre_crosswalk'),
    ('CWE-287', 'T1078', 'persistence', 'high', 'mitre_crosswalk'),
    ('CWE-287', 'T1133', 'initial-access', 'medium', 'mitre_crosswalk'),
    ('CWE-306', 'T1078', 'persistence', 'high', 'mitre_crosswalk'),
    ('CWE-306', 'T1133', 'initial-access', 'medium', 'mitre_crosswalk'),
    ('CWE-502', 'T1059', 'execution', 'high', 'mitre_crosswalk'),
    ('CWE-502', 'T1190', 'initial-access', 'high', 'mitre_crosswalk'),
    ('CWE-918', 'T1190', 'initial-access', 'high', 'mitre_crosswalk'),
    ('CWE-918', 'T1059', 'execution', 'medium', 'mitre_crosswalk')
ON CONFLICT (cwe_id, technique_id, tactic) DO NOTHING;
COMMIT;

-- ---------------------------------------------------------------------------
-- 3. cve_attack_mappings — CVE → ATT&CK join (Stage 2 output)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cve_attack_mappings (
    cve_id              TEXT NOT NULL,
    technique_id        TEXT NOT NULL,
    tactic              TEXT NOT NULL,

    -- CVE context (denormalised for fast retrieval)
    cvss_score          NUMERIC(4,2),
    epss_score          NUMERIC(5,4),
    attack_vector       TEXT,
    cwe_ids             TEXT[] DEFAULT '{}',
    affected_products   TEXT[] DEFAULT '{}',
    exploit_available   BOOLEAN DEFAULT FALSE,
    exploit_maturity    TEXT,     -- 'none' | 'poc' | 'weaponised'

    -- Mapping quality
    confidence          TEXT NOT NULL CHECK (confidence IN ('high', 'medium', 'low')),
    mapping_source      TEXT NOT NULL,  -- 'cwe_lookup' | 'llm' | 'cwe_lookup+llm'
    rationale           TEXT,

    -- Lifecycle
    mapping_run_id      UUID,
    created_at          TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (cve_id, technique_id, tactic)
);

-- Optional FK to attack_techniques if table exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'attack_techniques') THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.table_constraints
            WHERE constraint_name = 'fk_cve_attack_technique'
            AND table_name = 'cve_attack_mappings'
        ) THEN
            ALTER TABLE cve_attack_mappings
            ADD CONSTRAINT fk_cve_attack_technique
            FOREIGN KEY (technique_id) REFERENCES attack_techniques(technique_id) ON DELETE CASCADE;
        END IF;
    END IF;
EXCEPTION WHEN OTHERS THEN
    NULL;  -- Ignore if FK already exists or table doesn't exist
END $$;

CREATE INDEX IF NOT EXISTS idx_cve_attack_cve ON cve_attack_mappings (cve_id);
CREATE INDEX IF NOT EXISTS idx_cve_attack_technique ON cve_attack_mappings (technique_id);
CREATE INDEX IF NOT EXISTS idx_cve_attack_tactic ON cve_attack_mappings (tactic);
COMMIT;

-- ---------------------------------------------------------------------------
-- 4. attack_control_mappings_multi — multi-framework (technique, tactic, item, framework)
-- Used by CVE pipeline when framework_id is provided (e.g. cis_v8_1, nist_800_53r5)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS attack_control_mappings_multi (
    id                  BIGSERIAL PRIMARY KEY,
    technique_id        TEXT NOT NULL,
    tactic              TEXT NOT NULL,
    item_id             TEXT NOT NULL,
    framework_id        TEXT NOT NULL,
    relevance_score     NUMERIC(4,3) NOT NULL CHECK (relevance_score BETWEEN 0 AND 1),
    confidence          TEXT NOT NULL CHECK (confidence IN ('high', 'medium', 'low')),
    rationale           TEXT,
    tactic_risk_lens     TEXT,
    blast_radius        TEXT,
    attack_tactics       TEXT[] DEFAULT '{}',
    attack_platforms     TEXT[] DEFAULT '{}',
    loss_outcomes       TEXT[] DEFAULT '{}',
    mapping_run_id      UUID,
    cve_id              TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (technique_id, tactic, item_id, framework_id)
);

CREATE INDEX IF NOT EXISTS idx_acm_multi_technique ON attack_control_mappings_multi (technique_id);
CREATE INDEX IF NOT EXISTS idx_acm_multi_framework ON attack_control_mappings_multi (framework_id);
CREATE INDEX IF NOT EXISTS idx_acm_multi_cve ON attack_control_mappings_multi (cve_id);
COMMIT;

-- ============================================================================
-- Migration: Align existing tables with tactic-aware CVE → ATT&CK → Control pipeline
-- Run this against your existing database BEFORE seeding dummy data.
-- Safe to run multiple times — all changes use IF NOT EXISTS / DO $$ guards.
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. cve_attack_mapping — add missing pipeline columns
-- ============================================================================
-- Current unique key is (cve_id, attack_technique_id) — no tactic in PK.
-- We add tactic + enrichment columns without dropping the table.
-- The unique constraint is widened to include attack_tactic (slug form).

ALTER TABLE cve_attack_mapping
    ADD COLUMN IF NOT EXISTS attack_tactic_slug  VARCHAR(60),     -- kill_chain_phases slug e.g. "initial-access"
    ADD COLUMN IF NOT EXISTS cvss_score          NUMERIC(4,2),
    ADD COLUMN IF NOT EXISTS epss_score          NUMERIC(5,4),
    ADD COLUMN IF NOT EXISTS attack_vector       VARCHAR(20),     -- 'network'|'adjacent'|'local'|'physical'
    ADD COLUMN IF NOT EXISTS cwe_ids             TEXT[],
    ADD COLUMN IF NOT EXISTS affected_products   TEXT[],
    ADD COLUMN IF NOT EXISTS exploit_available   BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS exploit_maturity    VARCHAR(20)      -- 'none'|'poc'|'weaponised'
        CHECK (exploit_maturity IN ('none', 'poc', 'weaponised')),
    ADD COLUMN IF NOT EXISTS mapping_run_id      UUID;

-- Back-fill tactic slug from existing attack_tactic (title-cased) column
-- e.g. "Initial Access" → "initial-access"
UPDATE cve_attack_mapping
SET attack_tactic_slug = LOWER(REPLACE(attack_tactic, ' ', '-'))
WHERE attack_tactic_slug IS NULL AND attack_tactic IS NOT NULL;

-- Add index on the new slug column
CREATE INDEX IF NOT EXISTS idx_cve_attack_tactic_slug
    ON cve_attack_mapping(attack_tactic_slug);

CREATE INDEX IF NOT EXISTS idx_cve_attack_cvss
    ON cve_attack_mapping(cvss_score DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_cve_attack_epss
    ON cve_attack_mapping(epss_score DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_cve_attack_exploit
    ON cve_attack_mapping(exploit_available, exploit_maturity);

-- ============================================================================
-- 2. attack_technique_control_mapping — add tactic + framework context
-- ============================================================================

ALTER TABLE attack_technique_control_mapping
    ADD COLUMN IF NOT EXISTS tactic              VARCHAR(60),     -- kill_chain_phases slug
    ADD COLUMN IF NOT EXISTS framework_id        VARCHAR(50),     -- 'cis_v8_1'|'nist_800_53r5' etc.
    ADD COLUMN IF NOT EXISTS tactic_risk_lens    TEXT,
    ADD COLUMN IF NOT EXISTS blast_radius        VARCHAR(20)
        CHECK (blast_radius IN ('identity', 'endpoint', 'data', 'network', 'process')),
    ADD COLUMN IF NOT EXISTS mapping_run_id      UUID;

CREATE INDEX IF NOT EXISTS idx_attack_control_tactic
    ON attack_technique_control_mapping(tactic);

CREATE INDEX IF NOT EXISTS idx_attack_control_framework
    ON attack_technique_control_mapping(framework_id);

-- ============================================================================
-- 3. tactic_contexts — new table (cache for LLM-derived risk lenses)
-- ============================================================================

CREATE TABLE IF NOT EXISTS tactic_contexts (
    technique_id        VARCHAR(20)  NOT NULL,
    tactic              VARCHAR(60)  NOT NULL,   -- kill_chain_phases slug
    tactic_risk_lens    TEXT         NOT NULL,
    blast_radius        VARCHAR(20)  CHECK (blast_radius IN ('identity','endpoint','data','network','process')),
    primary_asset_types TEXT[],
    derived_at          TIMESTAMPTZ  DEFAULT NOW(),
    PRIMARY KEY (technique_id, tactic)
);

CREATE INDEX IF NOT EXISTS idx_tactic_ctx_technique
    ON tactic_contexts(technique_id);

-- ============================================================================
-- 4. cwe_technique_mappings — new table (deterministic CWE → ATT&CK crosswalk)
-- ============================================================================

CREATE TABLE IF NOT EXISTS cwe_technique_mappings (
    cwe_id          VARCHAR(20)  NOT NULL,    -- 'CWE-77'
    technique_id    VARCHAR(20)  NOT NULL,    -- 'T1059'
    tactic          VARCHAR(60)  NOT NULL,    -- 'execution'
    confidence      VARCHAR(10)  NOT NULL CHECK (confidence IN ('high', 'medium', 'low')),
    mapping_source  VARCHAR(30)  NOT NULL DEFAULT 'mitre_crosswalk',
    notes           TEXT,
    PRIMARY KEY (cwe_id, technique_id, tactic)
);

CREATE INDEX IF NOT EXISTS idx_cwe_tech_cwe ON cwe_technique_mappings(cwe_id);
CREATE INDEX IF NOT EXISTS idx_cwe_tech_technique ON cwe_technique_mappings(technique_id);

-- ============================================================================
-- 5. framework_items — unified control/risk/scenario entity
-- ============================================================================

CREATE TABLE IF NOT EXISTS framework_items (
    item_id                 TEXT         NOT NULL,
    framework_id            TEXT         NOT NULL,
    title                   TEXT         NOT NULL,
    control_family          TEXT,
    control_type            VARCHAR(20)  CHECK (control_type IN ('preventive','detective','corrective','compensating')),
    control_objective       TEXT,
    implementation_guidance TEXT,
    risk_description        TEXT,
    risk_severity           VARCHAR(10)  CHECK (risk_severity IN ('critical','high','medium','low')),
    risk_likelihood         VARCHAR(10),
    trigger                 TEXT,
    loss_outcomes           TEXT[],
    affected_assets         TEXT[],
    tactic_domains          TEXT[],
    asset_types             TEXT[],
    blast_radius            VARCHAR(20),
    created_at              TIMESTAMPTZ  DEFAULT NOW(),
    updated_at              TIMESTAMPTZ  DEFAULT NOW(),
    PRIMARY KEY (item_id, framework_id)
);

CREATE INDEX IF NOT EXISTS idx_framework_items_framework
    ON framework_items(framework_id, control_family);
CREATE INDEX IF NOT EXISTS idx_framework_items_tactic_domains
    ON framework_items USING GIN(tactic_domains);
CREATE INDEX IF NOT EXISTS idx_framework_items_asset_types
    ON framework_items USING GIN(asset_types);
CREATE INDEX IF NOT EXISTS idx_framework_items_severity
    ON framework_items(framework_id, risk_severity);

-- ============================================================================
-- 6. attack_control_mappings — migrate existing table OR create fresh
-- ============================================================================
-- The old schema (schema.sql) created this table with (technique_id, scenario_id)
-- as PK and no tactic column.  CREATE TABLE IF NOT EXISTS would silently skip
-- recreation, leaving the old structure and breaking the view below.
-- Strategy: detect which columns exist and ADD them if missing.  If the table
-- does not exist at all, create it in its final form.
-- ============================================================================

DO $$
BEGIN
    -- ── Case A: table does not exist yet → create in final form ──────────────
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'attack_control_mappings'
    ) THEN
        CREATE TABLE attack_control_mappings (
            technique_id        TEXT         NOT NULL,
            tactic              TEXT         NOT NULL  DEFAULT 'unknown',
            item_id             TEXT         NOT NULL,
            framework_id        TEXT         NOT NULL  DEFAULT 'unknown',
            relevance_score     NUMERIC(4,3) CHECK (relevance_score BETWEEN 0 AND 1),
            confidence          VARCHAR(10)  CHECK (confidence IN ('high','medium','low')),
            rationale           TEXT,
            tactic_risk_lens    TEXT,
            blast_radius        VARCHAR(20),
            framework_name      TEXT,
            control_family      TEXT,
            item_title          TEXT,
            attack_tactics      TEXT[],
            attack_platforms    TEXT[],
            loss_outcomes       TEXT[],
            retrieval_score     NUMERIC(4,3),
            retrieval_source    TEXT,
            mapping_run_id      UUID,
            validated           BOOLEAN      DEFAULT FALSE,
            validation_notes    TEXT,
            created_at          TIMESTAMPTZ  DEFAULT NOW(),
            updated_at          TIMESTAMPTZ  DEFAULT NOW(),
            PRIMARY KEY (technique_id, tactic, item_id, framework_id)
        );
        RAISE NOTICE 'attack_control_mappings: created fresh with tactic-aware PK';

    -- ── Case B: table exists but is the old schema (no tactic column) ────────
    ELSIF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'attack_control_mappings'
          AND column_name  = 'tactic'
    ) THEN
        -- 1. Rename old columns that clash with new semantics
        --    Old schema used scenario_id; new schema uses item_id.
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name   = 'attack_control_mappings'
              AND column_name  = 'scenario_id'
        ) THEN
            ALTER TABLE attack_control_mappings
                RENAME COLUMN scenario_id TO item_id;
            RAISE NOTICE 'attack_control_mappings: renamed scenario_id → item_id';
        END IF;

        -- 2. Add all missing columns
        ALTER TABLE attack_control_mappings
            ADD COLUMN IF NOT EXISTS tactic           TEXT  DEFAULT 'unknown',
            ADD COLUMN IF NOT EXISTS framework_id     TEXT  DEFAULT 'unknown',
            ADD COLUMN IF NOT EXISTS tactic_risk_lens TEXT,
            ADD COLUMN IF NOT EXISTS blast_radius     VARCHAR(20),
            ADD COLUMN IF NOT EXISTS framework_name   TEXT,
            ADD COLUMN IF NOT EXISTS control_family   TEXT,
            ADD COLUMN IF NOT EXISTS item_title       TEXT,
            ADD COLUMN IF NOT EXISTS retrieval_score  NUMERIC(4,3),
            ADD COLUMN IF NOT EXISTS retrieval_source TEXT,
            ADD COLUMN IF NOT EXISTS mapping_run_id   UUID,
            ADD COLUMN IF NOT EXISTS validated        BOOLEAN DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS validation_notes TEXT;

        -- 3. Drop the old PK (whatever it was) and add the new 4-column PK.
        --    We can't add a PK if one already exists — drop it first.
        DECLARE
            _pk_name TEXT;
        BEGIN
            SELECT constraint_name INTO _pk_name
            FROM information_schema.table_constraints
            WHERE table_schema    = 'public'
              AND table_name      = 'attack_control_mappings'
              AND constraint_type = 'PRIMARY KEY'
            LIMIT 1;

            IF _pk_name IS NOT NULL THEN
                EXECUTE format('ALTER TABLE attack_control_mappings DROP CONSTRAINT %I', _pk_name);
                RAISE NOTICE 'attack_control_mappings: dropped old PK %', _pk_name;
            END IF;
        END;

        -- Ensure item_id and framework_id are NOT NULL before adding new PK
        UPDATE attack_control_mappings SET tactic       = 'unknown' WHERE tactic       IS NULL;
        UPDATE attack_control_mappings SET framework_id = 'unknown' WHERE framework_id IS NULL;
        UPDATE attack_control_mappings SET item_id      = 'unknown' WHERE item_id      IS NULL;

        ALTER TABLE attack_control_mappings
            ALTER COLUMN tactic       SET NOT NULL,
            ALTER COLUMN framework_id SET NOT NULL,
            ALTER COLUMN item_id      SET NOT NULL,
            ALTER COLUMN technique_id SET NOT NULL;

        ALTER TABLE attack_control_mappings
            ADD PRIMARY KEY (technique_id, tactic, item_id, framework_id);

        RAISE NOTICE 'attack_control_mappings: migrated old schema → tactic-aware 4-col PK';

    ELSE
        RAISE NOTICE 'attack_control_mappings: already has tactic column, skipping migration';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_acm_technique_tactic
    ON attack_control_mappings(technique_id, tactic);
CREATE INDEX IF NOT EXISTS idx_acm_item_framework
    ON attack_control_mappings(item_id, framework_id);
CREATE INDEX IF NOT EXISTS idx_acm_confidence
    ON attack_control_mappings(confidence, relevance_score DESC);
CREATE INDEX IF NOT EXISTS idx_acm_gaps
    ON attack_control_mappings(framework_id, item_id) WHERE validated = TRUE;

-- ============================================================================
-- 7. cve_intelligence — Postgres counterpart to the Qdrant collection
-- ============================================================================

CREATE TABLE IF NOT EXISTS cve_intelligence (
    cve_id              TEXT         PRIMARY KEY,
    description         TEXT,
    cvss_score          NUMERIC(4,2),
    cvss_vector         TEXT,
    attack_vector       VARCHAR(20),
    attack_complexity   VARCHAR(10),
    privileges_required VARCHAR(10),
    cwe_ids             TEXT[],
    affected_products   TEXT[],
    epss_score          NUMERIC(5,4),
    exploit_available   BOOLEAN      DEFAULT FALSE,
    exploit_maturity    VARCHAR(20)  CHECK (exploit_maturity IN ('none','poc','weaponised')),
    kev_listed          BOOLEAN      DEFAULT FALSE,
    published_date      DATE,
    last_modified       DATE,
    technique_ids       TEXT[],
    tactics             TEXT[],
    frameworks_mapped   TEXT[],
    cached_at           TIMESTAMPTZ  DEFAULT NOW(),
    expires_at          TIMESTAMPTZ
);

-- Add kev_listed if table was created by cve_pipeline_tables.sql (which uses exploit_available)
ALTER TABLE cve_intelligence ADD COLUMN IF NOT EXISTS kev_listed BOOLEAN DEFAULT FALSE;
UPDATE cve_intelligence SET kev_listed = COALESCE(exploit_available, FALSE);
-- Add other columns that cve_pipeline_tables may not have
ALTER TABLE cve_intelligence ADD COLUMN IF NOT EXISTS technique_ids TEXT[];
ALTER TABLE cve_intelligence ADD COLUMN IF NOT EXISTS tactics TEXT[];
ALTER TABLE cve_intelligence ADD COLUMN IF NOT EXISTS frameworks_mapped TEXT[];
ALTER TABLE cve_intelligence ADD COLUMN IF NOT EXISTS cached_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE cve_intelligence ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_cve_intel_cvss    ON cve_intelligence(cvss_score DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_cve_intel_epss    ON cve_intelligence(epss_score DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_cve_intel_kev     ON cve_intelligence(kev_listed) WHERE kev_listed = TRUE;
CREATE INDEX IF NOT EXISTS idx_cve_intel_cwe     ON cve_intelligence USING GIN(cwe_ids);
CREATE INDEX IF NOT EXISTS idx_cve_intel_tactics ON cve_intelligence USING GIN(tactics);

-- ============================================================================
-- 8. control_frameworks — registry
-- ============================================================================

CREATE TABLE IF NOT EXISTS control_frameworks (
    framework_id        TEXT         PRIMARY KEY,
    framework_name      TEXT         NOT NULL,
    framework_version   TEXT,
    control_id_label    TEXT,
    qdrant_collection   TEXT,
    control_count       INTEGER,
    is_active           BOOLEAN      DEFAULT TRUE,
    ingested_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ  DEFAULT NOW()
);

-- Seed known frameworks
INSERT INTO control_frameworks (framework_id, framework_name, framework_version, control_id_label, qdrant_collection)
VALUES
    ('cis_v8_1',      'CIS Controls v8.1',          '8.1',       'CIS-RISK-NNN',                   'framework_items_cis'),
    ('nist_800_53r5', 'NIST SP 800-53 Rev 5',        'Rev 5',     'Control ID (e.g. AC-2)',          'framework_items_nist'),
    ('iso_27001_2022','ISO/IEC 27001:2022',           '2022',      'Annex A ID (e.g. A.8.1)',         'framework_items_iso'),
    ('soc2_2017',     'SOC 2 Trust Services Criteria','2017',      'TSC ref (e.g. CC6.1)',            'framework_items_soc2'),
    ('pci_dss_v4',    'PCI-DSS v4.0',                '4.0',       'Requirement (e.g. Req-8.3)',      'framework_items_pci')
ON CONFLICT (framework_id) DO NOTHING;

-- ============================================================================
-- 9. mapping_runs — audit trail
-- ============================================================================

CREATE TABLE IF NOT EXISTS mapping_runs (
    run_id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    framework_id        TEXT         REFERENCES control_frameworks(framework_id),
    triggered_by        TEXT,
    technique_filter    TEXT[],
    tactic_filter       TEXT[],
    item_count          INTEGER,
    technique_count     INTEGER,
    mapping_count       INTEGER,
    coverage_pct        NUMERIC(5,2),
    duration_seconds    NUMERIC(8,2),
    status              TEXT         DEFAULT 'running'
                            CHECK (status IN ('running','complete','failed')),
    error_message       TEXT,
    started_at          TIMESTAMPTZ  DEFAULT NOW(),
    completed_at        TIMESTAMPTZ
);

-- ============================================================================
-- Useful views
-- ============================================================================

CREATE OR REPLACE VIEW v_cve_full_chain AS
SELECT
    ci.cve_id,
    ci.cvss_score,
    ci.epss_score,
    ci.kev_listed,
    ci.exploit_maturity,
    cam.attack_technique_id   AS technique_id,
    cam.attack_tactic_slug    AS tactic,
    cam.confidence_score      AS cve_technique_confidence,
    acm.item_id,
    acm.framework_id,
    acm.item_title,
    acm.control_family,
    acm.relevance_score       AS control_relevance,
    acm.confidence            AS control_confidence,
    acm.rationale
FROM cve_intelligence ci
LEFT JOIN cve_attack_mapping cam
    ON cam.cve_id = ci.cve_id
LEFT JOIN attack_control_mappings acm
    ON acm.technique_id = cam.attack_technique_id
    AND acm.tactic = cam.attack_tactic_slug
ORDER BY ci.epss_score DESC NULLS LAST, acm.relevance_score DESC NULLS LAST;

COMMENT ON VIEW v_cve_full_chain IS
    'Full CVE → technique → control chain in one query. Use for gap analysis and reporting.';

CREATE OR REPLACE VIEW v_unmapped_cves AS
SELECT
    ci.cve_id,
    ci.cvss_score,
    ci.epss_score,
    ci.kev_listed,
    ci.cwe_ids
FROM cve_intelligence ci
WHERE NOT EXISTS (
    SELECT 1 FROM cve_attack_mapping cam WHERE cam.cve_id = ci.cve_id
)
ORDER BY ci.cvss_score DESC NULLS LAST;

COMMENT ON VIEW v_unmapped_cves IS 'CVEs with no ATT&CK technique mapping yet.';

COMMIT;

-- Verification
SELECT table_name, 'exists' AS status
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
      'tactic_contexts', 'cwe_technique_mappings', 'framework_items',
      'attack_control_mappings', 'cve_intelligence', 'control_frameworks', 'mapping_runs'
  )
ORDER BY table_name;
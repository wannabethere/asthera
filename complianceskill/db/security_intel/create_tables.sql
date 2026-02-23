-- ============================================================================
-- Security Intelligence Database Tables - CREATE SCRIPT
-- ============================================================================
-- This script creates all tables required for security intelligence tools.
-- 
-- Usage:
--   psql -U postgres -d your_database -f create_tables.sql
--   Or connect to your database and run: \i create_tables.sql
--
-- Note: Tables are organized by phase (Phase 1 = Critical, Phase 2 = Enhanced, Phase 3 = Compliance)
-- ============================================================================

BEGIN;

-- ============================================================================
-- PHASE 1 - CRITICAL TABLES (MVP)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. CVE → ATT&CK Technique Mapping
-- ----------------------------------------------------------------------------
-- Maps CVEs to MITRE ATT&CK techniques
-- Data sources: MITRE ATT&CK, CTID project, manual curation, LLM-assisted mapping

CREATE TABLE IF NOT EXISTS cve_attack_mapping (
    id SERIAL PRIMARY KEY,
    cve_id VARCHAR(20) NOT NULL,              -- e.g. CVE-2024-1234
    attack_technique_id VARCHAR(20),           -- e.g. T1003.001
    attack_tactic VARCHAR(50),                 -- e.g. Credential Access
    mapping_source VARCHAR(50),                -- mitre_official | ctid | manual | ai_inferred
    confidence_score FLOAT,                   -- 0.0 - 1.0
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    notes TEXT,
    
    -- Ensure unique CVE + technique combinations
    CONSTRAINT uq_cve_attack UNIQUE (cve_id, attack_technique_id)
);

CREATE INDEX IF NOT EXISTS idx_cve_attack_cve ON cve_attack_mapping(cve_id);
CREATE INDEX IF NOT EXISTS idx_cve_attack_tech ON cve_attack_mapping(attack_technique_id);
CREATE INDEX IF NOT EXISTS idx_cve_attack_tactic ON cve_attack_mapping(attack_tactic);
CREATE INDEX IF NOT EXISTS idx_cve_attack_source ON cve_attack_mapping(mapping_source);

COMMENT ON TABLE cve_attack_mapping IS 'Maps CVEs to MITRE ATT&CK techniques';
COMMENT ON COLUMN cve_attack_mapping.cve_id IS 'CVE identifier (e.g., CVE-2024-1234)';
COMMENT ON COLUMN cve_attack_mapping.attack_technique_id IS 'ATT&CK technique ID (e.g., T1003.001)';
COMMENT ON COLUMN cve_attack_mapping.mapping_source IS 'Source of the mapping: mitre_official, ctid, manual, or ai_inferred';
COMMENT ON COLUMN cve_attack_mapping.confidence_score IS 'Confidence score from 0.0 to 1.0';

-- ----------------------------------------------------------------------------
-- 2. ATT&CK Technique → Control Mapping
-- ----------------------------------------------------------------------------
-- Maps ATT&CK techniques to framework controls (CIS, NIST, HIPAA, etc.)
-- Note: control_id references the existing controls table (may not exist yet)

CREATE TABLE IF NOT EXISTS attack_technique_control_mapping (
    id SERIAL PRIMARY KEY,
    attack_technique_id VARCHAR(20) NOT NULL,  -- e.g. T1003.001
    control_id VARCHAR(128),                   -- FK to controls(id) - may be NULL if controls table doesn't exist
    mitigation_effectiveness VARCHAR(20),     -- full | partial | low
    mapping_source VARCHAR(50),                -- manual | ai_generated | mitre_derived
    confidence_score FLOAT,                   -- 0.0 - 1.0
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Ensure unique technique + control combinations
    CONSTRAINT uq_attack_control UNIQUE (attack_technique_id, control_id)
);

CREATE INDEX IF NOT EXISTS idx_attack_control_tech ON attack_technique_control_mapping(attack_technique_id);
CREATE INDEX IF NOT EXISTS idx_attack_control_ctrl ON attack_technique_control_mapping(control_id);
CREATE INDEX IF NOT EXISTS idx_attack_control_effectiveness ON attack_technique_control_mapping(mitigation_effectiveness);

-- Add foreign key constraint only if controls table exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'controls') THEN
        ALTER TABLE attack_technique_control_mapping
        ADD CONSTRAINT fk_attack_control_control_id
        FOREIGN KEY (control_id) REFERENCES controls(id)
        ON DELETE CASCADE;
    END IF;
END $$;

COMMENT ON TABLE attack_technique_control_mapping IS 'Maps ATT&CK techniques to framework controls';
COMMENT ON COLUMN attack_technique_control_mapping.attack_technique_id IS 'ATT&CK technique ID (e.g., T1003.001)';
COMMENT ON COLUMN attack_technique_control_mapping.control_id IS 'Framework control ID (references controls table if it exists)';
COMMENT ON COLUMN attack_technique_control_mapping.mitigation_effectiveness IS 'How effective the control is: full, partial, or low';

-- ----------------------------------------------------------------------------
-- 3. CPE Dictionary
-- ----------------------------------------------------------------------------
-- Common Platform Enumeration dictionary for software/products
-- Data source: NVD CPE Dictionary (500MB+ JSON feed)

CREATE TABLE IF NOT EXISTS cpe_dictionary (
    cpe_uri VARCHAR(255) PRIMARY KEY,          -- cpe:2.3:a:vendor:product:version:...
    vendor VARCHAR(255),
    product VARCHAR(255),
    version VARCHAR(100),
    update_version VARCHAR(100),              -- Update version if applicable
    edition VARCHAR(100),                      -- Edition if applicable
    language VARCHAR(50),                      -- Language if applicable
    sw_edition VARCHAR(100),                  -- Software edition
    target_sw VARCHAR(100),                   -- Target software
    target_hw VARCHAR(100),                   -- Target hardware
    other VARCHAR(100),                       -- Other attributes
    cpe_title TEXT,                           -- Human-readable name
    deprecated BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cpe_vendor_product ON cpe_dictionary(vendor, product);
CREATE INDEX IF NOT EXISTS idx_cpe_product_version ON cpe_dictionary(product, version);
CREATE INDEX IF NOT EXISTS idx_cpe_vendor ON cpe_dictionary(vendor);
CREATE INDEX IF NOT EXISTS idx_cpe_product ON cpe_dictionary(product);
CREATE INDEX IF NOT EXISTS idx_cpe_deprecated ON cpe_dictionary(deprecated);

COMMENT ON TABLE cpe_dictionary IS 'Common Platform Enumeration dictionary for software/products';
COMMENT ON COLUMN cpe_dictionary.cpe_uri IS 'Full CPE URI (e.g., cpe:2.3:a:apache:log4j:2.14.1)';
COMMENT ON COLUMN cpe_dictionary.cpe_title IS 'Human-readable product name';

-- ----------------------------------------------------------------------------
-- 4. CVE → CPE Affected (Junction Table)
-- ----------------------------------------------------------------------------
-- Maps CVEs to affected CPEs with version ranges

CREATE TABLE IF NOT EXISTS cve_cpe_affected (
    id SERIAL PRIMARY KEY,
    cve_id VARCHAR(20) NOT NULL,
    cpe_uri VARCHAR(255) REFERENCES cpe_dictionary(cpe_uri) ON DELETE CASCADE,
    version_start VARCHAR(100),               -- Vulnerable from version X
    version_end VARCHAR(100),                 -- Vulnerable to version Y (NULL = all versions after start)
    version_start_including BOOLEAN DEFAULT TRUE,  -- Include start version
    version_end_including BOOLEAN DEFAULT FALSE,    -- Include end version
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- Ensure unique CVE + CPE combinations
    CONSTRAINT uq_cve_cpe UNIQUE (cve_id, cpe_uri)
);

CREATE INDEX IF NOT EXISTS idx_cve_cpe_cve ON cve_cpe_affected(cve_id);
CREATE INDEX IF NOT EXISTS idx_cve_cpe_uri ON cve_cpe_affected(cpe_uri);
CREATE INDEX IF NOT EXISTS idx_cve_cpe_version_range ON cve_cpe_affected(version_start, version_end);

COMMENT ON TABLE cve_cpe_affected IS 'Maps CVEs to affected CPEs with version ranges';
COMMENT ON COLUMN cve_cpe_affected.version_start_including IS 'Whether the start version is included in the vulnerable range';
COMMENT ON COLUMN cve_cpe_affected.version_end_including IS 'Whether the end version is included in the vulnerable range';

-- ============================================================================
-- PHASE 2 - ENHANCED INTELLIGENCE TABLES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 5. Metasploit Module Index
-- ----------------------------------------------------------------------------
-- Index of Metasploit Framework modules
-- Data source: GitHub repo rapid7/metasploit-framework

CREATE TABLE IF NOT EXISTS metasploit_modules (
    id SERIAL PRIMARY KEY,
    module_path VARCHAR(500) UNIQUE NOT NULL,  -- exploit/windows/smb/ms17_010_eternalblue
    module_type VARCHAR(50) NOT NULL,          -- exploit | auxiliary | post | payload
    name VARCHAR(255),
    fullname VARCHAR(500),                     -- Full module name
    description TEXT,
    author VARCHAR(255)[],                     -- Array of authors
    platform VARCHAR(100)[],                   -- [windows, linux, unix]
    arch VARCHAR(50)[],                        -- [x86, x64, arm]
    cve_references VARCHAR(20)[],               -- Array of CVE IDs
    cwe_references VARCHAR(20)[],               -- Array of CWE IDs
    rank VARCHAR(20),                          -- excellent | great | good | normal | average | low | manual
    disclosure_date DATE,
    check_available BOOLEAN DEFAULT FALSE,     -- Can test without exploiting
    targets TEXT[],                            -- Target list
    notes TEXT,                                -- Additional notes
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_msf_cve ON metasploit_modules USING GIN(cve_references);
CREATE INDEX IF NOT EXISTS idx_msf_platform ON metasploit_modules USING GIN(platform);
CREATE INDEX IF NOT EXISTS idx_msf_type ON metasploit_modules(module_type);
CREATE INDEX IF NOT EXISTS idx_msf_rank ON metasploit_modules(rank);
CREATE INDEX IF NOT EXISTS idx_msf_disclosure_date ON metasploit_modules(disclosure_date);

COMMENT ON TABLE metasploit_modules IS 'Index of Metasploit Framework modules';
COMMENT ON COLUMN metasploit_modules.module_path IS 'Path to module in Metasploit (e.g., exploit/windows/smb/ms17_010_eternalblue)';
COMMENT ON COLUMN metasploit_modules.rank IS 'Module rank: excellent, great, good, normal, average, low, or manual';

-- ----------------------------------------------------------------------------
-- 6. Nuclei Template Index
-- ----------------------------------------------------------------------------
-- Index of Nuclei vulnerability detection templates
-- Data source: GitHub repo projectdiscovery/nuclei-templates

CREATE TABLE IF NOT EXISTS nuclei_templates (
    id SERIAL PRIMARY KEY,
    template_id VARCHAR(255) UNIQUE NOT NULL,  -- CVE-2024-1234.yaml or unique identifier
    name VARCHAR(255) NOT NULL,
    severity VARCHAR(20) NOT NULL,             -- info | low | medium | high | critical
    description TEXT,
    tags VARCHAR(100)[],                       -- [cve, rce, log4j, xss]
    cve_references VARCHAR(20)[],               -- Array of CVE IDs
    cwe_references VARCHAR(20)[],               -- Array of CWE IDs
    template_path VARCHAR(500),                 -- Path in nuclei-templates repo
    author VARCHAR(255)[],                      -- Array of authors
    metadata JSONB,                            -- Full YAML metadata block
    classification JSONB,                       -- Classification data
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_nuclei_cve ON nuclei_templates USING GIN(cve_references);
CREATE INDEX IF NOT EXISTS idx_nuclei_tags ON nuclei_templates USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_nuclei_severity ON nuclei_templates(severity);
CREATE INDEX IF NOT EXISTS idx_nuclei_name ON nuclei_templates(name);
CREATE INDEX IF NOT EXISTS idx_nuclei_metadata ON nuclei_templates USING GIN(metadata);

COMMENT ON TABLE nuclei_templates IS 'Index of Nuclei vulnerability detection templates';
COMMENT ON COLUMN nuclei_templates.template_id IS 'Unique template identifier (usually filename)';
COMMENT ON COLUMN nuclei_templates.metadata IS 'Full YAML metadata as JSONB for flexible querying';

-- ----------------------------------------------------------------------------
-- 7. Exploit-DB Index
-- ----------------------------------------------------------------------------
-- Index of publicly available exploits from Exploit-DB
-- Data source: GitLab repo exploit-database/exploitdb (files_exploits.csv)

CREATE TABLE IF NOT EXISTS exploit_db_index (
    id SERIAL PRIMARY KEY,
    exploit_id INTEGER UNIQUE NOT NULL,        -- EDB-ID
    title VARCHAR(500) NOT NULL,
    description TEXT,
    author VARCHAR(255),
    platform VARCHAR(100),                     -- windows, linux, hardware, etc.
    exploit_type VARCHAR(50),                  -- remote, local, webapps, dos, shellcode, etc.
    cve_id VARCHAR(20),                        -- CVE reference if available
    date_published DATE,
    date_added DATE,                           -- Date added to Exploit-DB
    verified BOOLEAN DEFAULT FALSE,
    codes VARCHAR(100)[],                      -- Shellcode, exploits, etc.
    exploit_url VARCHAR(500),                  -- URL to exploit on Exploit-DB
    application_url VARCHAR(500),              -- URL to application if applicable
    source_url VARCHAR(500),                   -- Original source URL
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_edb_cve ON exploit_db_index(cve_id);
CREATE INDEX IF NOT EXISTS idx_edb_platform ON exploit_db_index(platform);
CREATE INDEX IF NOT EXISTS idx_edb_type ON exploit_db_index(exploit_type);
CREATE INDEX IF NOT EXISTS idx_edb_date_published ON exploit_db_index(date_published);
CREATE INDEX IF NOT EXISTS idx_edb_verified ON exploit_db_index(verified);
CREATE INDEX IF NOT EXISTS idx_edb_title ON exploit_db_index(title);

COMMENT ON TABLE exploit_db_index IS 'Index of publicly available exploits from Exploit-DB';
COMMENT ON COLUMN exploit_db_index.exploit_id IS 'Exploit-DB ID (EDB-ID)';
COMMENT ON COLUMN exploit_db_index.exploit_type IS 'Type: remote, local, webapps, dos, shellcode, etc.';

-- ============================================================================
-- PHASE 3 - COMPLIANCE & ENRICHMENT TABLES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 8. CIS Benchmark Rules
-- ----------------------------------------------------------------------------
-- CIS Benchmark rules and their mappings to controls and ATT&CK techniques
-- Data source: CIS Benchmark PDFs (manual extraction + LLM-assisted mapping)

CREATE TABLE IF NOT EXISTS cis_benchmark_rules (
    id SERIAL PRIMARY KEY,
    benchmark_id VARCHAR(100) NOT NULL,        -- CIS_Ubuntu_Linux_22.04
    rule_number VARCHAR(20) NOT NULL,          -- 1.1.1.1
    title VARCHAR(500) NOT NULL,
    description TEXT,
    rationale TEXT,
    remediation TEXT,
    audit_procedure TEXT,
    level INT,                                  -- 1 | 2
    profile VARCHAR(50),                       -- Server | Workstation | Level_1 | Level_2
    control_id VARCHAR(128),                   -- FK to controls(id) - may be NULL
    attack_techniques VARCHAR(20)[],            -- ATT&CK techniques this mitigates
    compliance_frameworks VARCHAR(100)[],      -- Additional framework mappings
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Ensure unique benchmark + rule combinations
    CONSTRAINT uq_cis_benchmark_rule UNIQUE (benchmark_id, rule_number)
);

CREATE INDEX IF NOT EXISTS idx_cis_benchmark ON cis_benchmark_rules(benchmark_id);
CREATE INDEX IF NOT EXISTS idx_cis_control ON cis_benchmark_rules(control_id);
CREATE INDEX IF NOT EXISTS idx_cis_level ON cis_benchmark_rules(level);
CREATE INDEX IF NOT EXISTS idx_cis_profile ON cis_benchmark_rules(profile);
CREATE INDEX IF NOT EXISTS idx_cis_attack_tech ON cis_benchmark_rules USING GIN(attack_techniques);

-- Add foreign key constraint only if controls table exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'controls') THEN
        ALTER TABLE cis_benchmark_rules
        ADD CONSTRAINT fk_cis_control_id
        FOREIGN KEY (control_id) REFERENCES controls(id)
        ON DELETE SET NULL;
    END IF;
END $$;

COMMENT ON TABLE cis_benchmark_rules IS 'CIS Benchmark rules and their mappings';
COMMENT ON COLUMN cis_benchmark_rules.benchmark_id IS 'CIS Benchmark identifier (e.g., CIS_Ubuntu_Linux_22.04)';
COMMENT ON COLUMN cis_benchmark_rules.level IS 'CIS Level: 1 (basic) or 2 (advanced)';

-- ----------------------------------------------------------------------------
-- 9. Sigma Detection Rules (Future)
-- ----------------------------------------------------------------------------
-- Index of Sigma detection rules for SIEM systems
-- Data source: GitHub repo SigmaHQ/sigma

CREATE TABLE IF NOT EXISTS sigma_rules (
    id SERIAL PRIMARY KEY,
    rule_id VARCHAR(255) UNIQUE NOT NULL,      -- UUID from rule
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL,              -- stable | test | experimental
    level VARCHAR(20),                        -- low | medium | high | critical
    logsource JSONB,                          -- {product: windows, service: sysmon, category: process_creation}
    detection JSONB,                          -- Full detection logic
    falsepositives TEXT[],                    -- Known false positives
    attack_technique_refs VARCHAR(20)[],       -- [T1003.001, T1078]
    tags VARCHAR(100)[],                      -- Additional tags
    author VARCHAR(255),
    date DATE,                                -- Creation/update date
    modified DATE,                            -- Last modification date
    rule_path VARCHAR(500),                   -- Path in sigma repo
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sigma_attack ON sigma_rules USING GIN(attack_technique_refs);
CREATE INDEX IF NOT EXISTS idx_sigma_tags ON sigma_rules USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_sigma_status ON sigma_rules(status);
CREATE INDEX IF NOT EXISTS idx_sigma_level ON sigma_rules(level);
CREATE INDEX IF NOT EXISTS idx_sigma_logsource ON sigma_rules USING GIN(logsource);
CREATE INDEX IF NOT EXISTS idx_sigma_detection ON sigma_rules USING GIN(detection);

COMMENT ON TABLE sigma_rules IS 'Index of Sigma detection rules for SIEM systems';
COMMENT ON COLUMN sigma_rules.rule_id IS 'Unique rule identifier (UUID from Sigma rule)';
COMMENT ON COLUMN sigma_rules.logsource IS 'Log source configuration as JSONB';
COMMENT ON COLUMN sigma_rules.detection IS 'Full detection logic as JSONB';

-- ============================================================================
-- ADDITIONAL UTILITY TABLES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 10. CVE Cache (Optional - for API response caching)
-- ----------------------------------------------------------------------------
-- Cache for NVD API responses to manage rate limits

CREATE TABLE IF NOT EXISTS cve_cache (
    id SERIAL PRIMARY KEY,
    cve_id VARCHAR(20) UNIQUE NOT NULL,
    nvd_data JSONB,                           -- Full NVD API response
    epss_data JSONB,                          -- EPSS score data
    kev_data JSONB,                           -- CISA KEV data
    cached_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,                     -- When cache expires
    source VARCHAR(50) DEFAULT 'nvd_api'      -- Source of the data
);

CREATE INDEX IF NOT EXISTS idx_cve_cache_cve ON cve_cache(cve_id);
CREATE INDEX IF NOT EXISTS idx_cve_cache_expires ON cve_cache(expires_at);

COMMENT ON TABLE cve_cache IS 'Cache for CVE intelligence data from APIs';
COMMENT ON COLUMN cve_cache.expires_at IS 'When the cached data expires (typically 24 hours)';

-- ============================================================================
-- CREATE TRIGGERS FOR UPDATED_AT TIMESTAMPS
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply triggers to tables with updated_at columns
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

CREATE TRIGGER update_metasploit_modules_updated_at
    BEFORE UPDATE ON metasploit_modules
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_nuclei_templates_updated_at
    BEFORE UPDATE ON nuclei_templates
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_exploit_db_index_updated_at
    BEFORE UPDATE ON exploit_db_index
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_cis_benchmark_rules_updated_at
    BEFORE UPDATE ON cis_benchmark_rules
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sigma_rules_updated_at
    BEFORE UPDATE ON sigma_rules
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Display created tables
SELECT 
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'public'
  AND table_name IN (
      'cve_attack_mapping',
      'attack_technique_control_mapping',
      'cpe_dictionary',
      'cve_cpe_affected',
      'metasploit_modules',
      'nuclei_templates',
      'exploit_db_index',
      'cis_benchmark_rules',
      'sigma_rules',
      'cve_cache'
  )
ORDER BY table_name;

-- Display summary
SELECT 
    'Tables created successfully!' as status,
    COUNT(*) as table_count
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
      'cve_attack_mapping',
      'attack_technique_control_mapping',
      'cpe_dictionary',
      'cve_cpe_affected',
      'metasploit_modules',
      'nuclei_templates',
      'exploit_db_index',
      'cis_benchmark_rules',
      'sigma_rules',
      'cve_cache'
  );

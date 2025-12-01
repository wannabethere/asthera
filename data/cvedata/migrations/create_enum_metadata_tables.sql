-- ============================================================================
-- Enum Metadata Tables Migration - Optimized for Pipeline Processing
-- ============================================================================
-- This migration creates PostgreSQL metadata tables for all enums used in
-- risk, impact, and breach parameter calculations.
-- 
-- Key Features:
-- - Related enums are combined into domain-based tables for efficient processing
-- - Numeric prioritization, scoring, and weight fields for pipeline enrichment
-- - All balbix-related entries have been excluded
-- ============================================================================

-- ============================================================================
-- Risk & Impact Metadata (Combined)
-- ============================================================================
-- Combines: risk_issue_levels, impact_class, propagation_class, vuln_level

CREATE TABLE IF NOT EXISTS risk_impact_metadata (
    id SERIAL PRIMARY KEY,
    enum_type VARCHAR(50) NOT NULL,  -- 'risk_level', 'impact_class', 'propagation_class', 'vuln_level'
    code VARCHAR(50) NOT NULL,
    description TEXT,
    priority_order INTEGER NOT NULL,  -- For sorting/ordering (1 = highest priority)
    numeric_score DECIMAL(10,2) NOT NULL,  -- For calculations (0-100 scale)
    severity_level INTEGER,  -- Numeric severity (1-10 scale)
    weight DECIMAL(5,3) DEFAULT 1.0,  -- Weight for weighted calculations
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(enum_type, code)
);

CREATE INDEX idx_risk_impact_type ON risk_impact_metadata(enum_type);
CREATE INDEX idx_risk_impact_priority ON risk_impact_metadata(priority_order);
CREATE INDEX idx_risk_impact_score ON risk_impact_metadata(numeric_score);

INSERT INTO risk_impact_metadata (enum_type, code, description, priority_order, numeric_score, severity_level, weight) VALUES
    -- Risk Issue Levels
    ('risk_level', 'CRITICAL', 'Critical Risk', 1, 100.0, 10, 1.0),
    ('risk_level', 'HIGH', 'High Risk', 2, 75.0, 8, 0.75),
    ('risk_level', 'MEDIUM', 'Medium Risk', 3, 50.0, 5, 0.5),
    
    -- Impact Classes
    ('impact_class', 'Mission Critical', 'Mission Critical Impact', 1, 100.0, 10, 1.0),
    ('impact_class', 'Critical', 'Critical Impact', 2, 70.0, 7, 0.7),
    ('impact_class', 'Other', 'Other Impact', 3, 30.0, 3, 0.3),
    
    -- Propagation Classes
    ('propagation_class', 'Perimeter', 'Perimeter Network', 1, 80.0, 8, 0.8),
    ('propagation_class', 'Core', 'Core Network', 2, 60.0, 6, 0.6),
    
    -- Vulnerability Levels
    ('vuln_level', 'CRITICAL', 'Critical Vulnerability', 1, 100.0, 10, 1.0),
    ('vuln_level', 'HIGH', 'High Vulnerability', 2, 75.0, 8, 0.75),
    ('vuln_level', 'MEDIUM', 'Medium Vulnerability', 3, 50.0, 5, 0.5),
    ('vuln_level', 'LOW', 'Low Vulnerability', 4, 25.0, 2, 0.25),
    ('vuln_level', 'NONE', 'No Vulnerability', 5, 0.0, 0, 0.0),
    ('vuln_level', 'UNKNOWN', 'Unknown Vulnerability', 6, 10.0, 1, 0.1)
ON CONFLICT (enum_type, code) DO NOTHING;

-- ============================================================================
-- Breach Method Metadata (Combined)
-- ============================================================================
-- Combines: breach_methods, bmm_prefix

CREATE TABLE IF NOT EXISTS breach_method_metadata (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    prefix VARCHAR(50),  -- Short-hand prefix
    priority_order INTEGER NOT NULL,  -- Attack vector priority
    risk_score DECIMAL(10,2) NOT NULL,  -- Base risk score (0-100)
    exploitability_score DECIMAL(10,2),  -- How easily exploitable (0-100)
    impact_score DECIMAL(10,2),  -- Potential impact (0-100)
    weight DECIMAL(5,3) DEFAULT 1.0,  -- Weight for calculations
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_breach_method_priority ON breach_method_metadata(priority_order);
CREATE INDEX idx_breach_method_risk_score ON breach_method_metadata(risk_score);

INSERT INTO breach_method_metadata (code, description, prefix, priority_order, risk_score, exploitability_score, impact_score, weight) VALUES
    ('zero_day', 'Zero Day', 'zd', 1, 95.0, 90.0, 95.0, 1.0),
    ('unpatched_vulnerability', 'Unpatched Vulnerability', 'uv', 2, 85.0, 75.0, 85.0, 0.9),
    ('compromised_credentials', 'Compromised Credentials', 'cc', 3, 90.0, 85.0, 80.0, 0.95),
    ('malicious_insider', 'Malicious Insider', 'mi', 4, 95.0, 95.0, 90.0, 1.0),
    ('trust_relationship', 'Trust Relationship', 'tr', 5, 75.0, 70.0, 75.0, 0.8),
    ('misconfiguration', 'Misconfiguration', 'misconfig', 6, 70.0, 65.0, 70.0, 0.75),
    ('phishing', 'Phishing', 'phish', 7, 80.0, 75.0, 70.0, 0.85),
    ('credential_vulnerability', 'Credential Vulnerability', 'creds', 8, 75.0, 70.0, 70.0, 0.8),
    ('lost_stolen_credentials', 'Lost Stolen Credentials', 'lsc', 9, 70.0, 65.0, 65.0, 0.75),
    ('weak_credentials', 'Weak Credentials', 'wp', 10, 60.0, 55.0, 60.0, 0.65),
    ('man_in_the_middle', 'Man in the Middle', 'mitm', 11, 65.0, 60.0, 65.0, 0.7)
ON CONFLICT (code) DO NOTHING;

-- ============================================================================
-- Security Strength Metadata (Combined)
-- ============================================================================
-- Combines: certificate_strength, cipher_strength, encryption_strength, cred_strength

CREATE TABLE IF NOT EXISTS security_strength_metadata (
    id SERIAL PRIMARY KEY,
    enum_type VARCHAR(50) NOT NULL,  -- 'certificate', 'cipher', 'encryption', 'credential'
    code VARCHAR(50) NOT NULL,
    description TEXT,
    strength_order INTEGER NOT NULL,  -- 1 = weakest, higher = stronger
    numeric_score DECIMAL(10,2) NOT NULL,  -- Strength score (0-100)
    security_level INTEGER NOT NULL,  -- 1-5 scale
    weight DECIMAL(5,3) DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(enum_type, code)
);

CREATE INDEX idx_security_strength_type ON security_strength_metadata(enum_type);
CREATE INDEX idx_security_strength_order ON security_strength_metadata(strength_order);

INSERT INTO security_strength_metadata (enum_type, code, description, strength_order, numeric_score, security_level, weight) VALUES
    -- Certificate Strength
    ('certificate', 'WEAK', 'Weak Certificate', 1, 20.0, 1, 0.2),
    ('certificate', 'MODERATE', 'Moderate Certificate', 2, 50.0, 3, 0.5),
    ('certificate', 'STRONG', 'Strong Certificate', 3, 100.0, 5, 1.0),
    
    -- Cipher Strength
    ('cipher', 'WEAK', 'Weak Cipher', 1, 20.0, 1, 0.2),
    ('cipher', 'MODERATE', 'Moderate Cipher', 2, 50.0, 3, 0.5),
    ('cipher', 'STRONG', 'Strong Cipher', 3, 100.0, 5, 1.0),
    
    -- Encryption Strength
    ('encryption', 'WEAK', 'Weak Encryption', 1, 20.0, 1, 0.2),
    ('encryption', 'MODERATE', 'Moderate Encryption', 2, 50.0, 3, 0.5),
    ('encryption', 'STRONG', 'Strong Encryption', 3, 100.0, 5, 1.0),
    
    -- Credential Strength
    ('credential', 'EMPTY', 'Empty Password', 0, 0.0, 0, 0.0),
    ('credential', 'DEFAULT', 'Default Password', 1, 10.0, 1, 0.1),
    ('credential', 'WEAK', 'Weak Password', 2, 30.0, 2, 0.3),
    ('credential', 'MODERATE', 'Moderate Password', 3, 60.0, 3, 0.6),
    ('credential', 'STRONG', 'Strong Password', 4, 100.0, 5, 1.0)
ON CONFLICT (enum_type, code) DO NOTHING;

-- ============================================================================
-- Asset Classification Metadata (Combined)
-- ============================================================================
-- Combines: asset_os_type, asset_device_type, asset_canonical_device_type, 
--           asset_device_subtype, asset_platform

CREATE TABLE IF NOT EXISTS asset_classification_metadata (
    id SERIAL PRIMARY KEY,
    classification_type VARCHAR(50) NOT NULL,  -- 'os_type', 'device_type', 'canonical_type', 'subtype', 'platform'
    code VARCHAR(100) NOT NULL,
    description TEXT,
    priority_order INTEGER,  -- For prioritization in risk calculations
    risk_weight DECIMAL(5,3) DEFAULT 1.0,  -- Risk weight for this asset type
    criticality_score DECIMAL(10,2),  -- Criticality score (0-100)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(classification_type, code)
);

CREATE INDEX idx_asset_classification_type ON asset_classification_metadata(classification_type);
CREATE INDEX idx_asset_classification_priority ON asset_classification_metadata(priority_order);

-- Asset Type to Subtype mapping
CREATE TABLE IF NOT EXISTS asset_type_subtype_map (
    id SERIAL PRIMARY KEY,
    canonical_type_code VARCHAR(100) NOT NULL,
    device_subtype_code VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Note: Foreign keys removed because unique constraint is on (classification_type, code)
    -- canonical_type_code should reference codes where classification_type = 'canonical_type'
    -- device_subtype_code should reference codes where classification_type = 'subtype'
    UNIQUE(canonical_type_code, device_subtype_code)
);

-- Asset Subtype to Platform mapping
CREATE TABLE IF NOT EXISTS asset_subtype_platform_map (
    id SERIAL PRIMARY KEY,
    device_subtype_code VARCHAR(100) NOT NULL,
    platform_code VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Note: Foreign keys removed because unique constraint is on (classification_type, code)
    -- device_subtype_code should reference codes where classification_type = 'subtype'
    -- platform_code should reference codes where classification_type = 'platform'
    UNIQUE(device_subtype_code, platform_code)
);

-- Insert OS Types
INSERT INTO asset_classification_metadata (classification_type, code, description, priority_order, risk_weight, criticality_score) VALUES
    ('os_type', 'Windows', 'Windows', 1, 1.0, 80.0),
    ('os_type', 'Linux/Unix', 'Linux/Unix', 2, 0.9, 75.0),
    ('os_type', 'OSX', 'macOS', 3, 0.8, 70.0),
    ('os_type', 'iOS', 'iOS', 4, 0.7, 65.0),
    ('os_type', 'Android', 'Android', 5, 0.7, 65.0),
    ('os_type', 'Cisco IOS', 'Cisco IOS', 6, 0.9, 75.0),
    ('os_type', 'Panos', 'Panos', 7, 0.9, 75.0),
    ('os_type', 'ChromeOS', 'ChromeOS', 8, 0.6, 60.0),
    ('os_type', 'Embedded', 'Embedded', 9, 0.5, 50.0),
    ('os_type', 'Junos', 'Junos', 10, 0.8, 70.0),
    ('os_type', 'Other Mobile OS', 'Other Mobile OS', 11, 0.5, 50.0),
    ('os_type', 'tvOS', 'tvOS', 12, 0.4, 40.0),
    ('os_type', 'Unknown', 'Unknown', 13, 0.3, 30.0)
ON CONFLICT (classification_type, code) DO NOTHING;

-- Insert Canonical Device Types (with higher criticality scores)
INSERT INTO asset_classification_metadata (classification_type, code, description, priority_order, risk_weight, criticality_score) VALUES
    ('canonical_type', 'Servers', 'Servers', 1, 1.0, 90.0),
    ('canonical_type', 'Networking Assets', 'Networking Assets', 2, 0.95, 85.0),
    ('canonical_type', 'Storage Assets', 'Storage Assets', 3, 0.9, 80.0),
    ('canonical_type', 'OT Assets', 'OT Assets', 4, 0.95, 85.0),
    ('canonical_type', 'Container', 'Container', 5, 0.85, 75.0),
    ('canonical_type', 'Desktops/Laptops', 'Desktops/Laptops', 6, 0.7, 60.0),
    ('canonical_type', 'Smartphones/Tablets', 'Smartphones/Tablets', 7, 0.6, 50.0),
    ('canonical_type', 'AV/VoIP', 'AV/VoIP', 8, 0.5, 45.0),
    ('canonical_type', 'IoT', 'IoT', 9, 0.4, 40.0),
    ('canonical_type', 'Other', 'Other', 10, 0.3, 30.0),
    ('canonical_type', 'Partially Categorized', 'Partially Categorized', 11, 0.2, 20.0),
    ('canonical_type', 'Unexamined', 'Unexamined', 12, 0.1, 10.0)
ON CONFLICT (classification_type, code) DO NOTHING;

-- Insert Platforms
INSERT INTO asset_classification_metadata (classification_type, code, description, priority_order, risk_weight, criticality_score) VALUES
    ('platform', 'Windows', 'Windows', 1, 1.0, 80.0),
    ('platform', 'macOS', 'macOS', 2, 0.8, 70.0),
    ('platform', 'Linux/Unix', 'Linux/Unix', 3, 0.9, 75.0),
    ('platform', 'Unknown', 'Unknown', 4, 0.3, 30.0)
ON CONFLICT (classification_type, code) DO NOTHING;

-- ============================================================================
-- Vulnerability Metadata (Combined)
-- ============================================================================
-- Combines: vulnerability_type, vulnerability_subtype, vuln_states, vuln_tags

CREATE TABLE IF NOT EXISTS vulnerability_metadata (
    id SERIAL PRIMARY KEY,
    enum_type VARCHAR(50) NOT NULL,  -- 'type', 'subtype', 'state', 'tag'
    code VARCHAR(100) NOT NULL,
    description TEXT,
    parent_code VARCHAR(100),  -- For subtypes, references type code
    priority_order INTEGER,
    risk_score DECIMAL(10,2),  -- Risk contribution score
    remediation_priority INTEGER,  -- 1 = highest priority for remediation
    weight DECIMAL(5,3) DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(enum_type, code)
);

CREATE INDEX idx_vuln_metadata_type ON vulnerability_metadata(enum_type);
CREATE INDEX idx_vuln_metadata_parent ON vulnerability_metadata(parent_code);
CREATE INDEX idx_vuln_metadata_priority ON vulnerability_metadata(priority_order);

INSERT INTO vulnerability_metadata (enum_type, code, description, parent_code, priority_order, risk_score, remediation_priority, weight) VALUES
    -- Vulnerability Types
    ('type', 'Software', 'Software Vulnerabilities', NULL, 1, 85.0, 1, 1.0),
    ('type', 'Services', 'Service Vulnerabilities', NULL, 2, 75.0, 2, 0.9),
    ('type', 'Data In Transit', 'Data In Transit Vulnerabilities', NULL, 3, 70.0, 3, 0.85),
    ('type', 'Cloud', 'Cloud Vulnerabilities', NULL, 4, 80.0, 2, 0.95),
    ('type', 'General', 'General Vulnerabilities', NULL, 5, 50.0, 5, 0.6),
    
    -- Vulnerability Subtypes
    ('subtype', 'Software-Vulnerable', 'Vulnerable Software', 'Software', 1, 90.0, 1, 1.0),
    ('subtype', 'Software-Unpatched', 'Unpatched Software', 'Software', 2, 85.0, 1, 0.95),
    ('subtype', 'Software-EOL', 'End of Life Software', 'Software', 3, 80.0, 2, 0.9),
    ('subtype', 'Insecure Services', 'Insecure Services', 'Services', 4, 75.0, 2, 0.85),
    ('subtype', 'Misconfigured Services', 'Misconfigured Services', 'Services', 5, 70.0, 3, 0.8),
    ('subtype', 'Unencrypted Services', 'Unencrypted Services', 'Services', 6, 65.0, 3, 0.75),
    ('subtype', 'SSL/TLS', 'SSL/TLS Issues', 'Data In Transit', 7, 70.0, 3, 0.8),
    ('subtype', 'Certificates', 'Certificate Issues', 'Data In Transit', 8, 65.0, 4, 0.75),
    ('subtype', 'AWS-EC2', 'AWS EC2 Issues', 'Cloud', 9, 80.0, 2, 0.9),
    ('subtype', 'AWS-S3', 'AWS S3 Issues', 'Cloud', 10, 85.0, 2, 0.95),
    ('subtype', 'AWS-IAM', 'AWS IAM Issues', 'Cloud', 11, 90.0, 1, 1.0),
    ('subtype', 'AWS-VPC', 'AWS VPC Issues', 'Cloud', 12, 75.0, 3, 0.85),
    ('subtype', 'Other', 'Other', NULL, 13, 50.0, 5, 0.6),
    
    -- Vulnerability States
    ('state', 'ACTIVE', 'Active Vulnerability', NULL, 1, 100.0, 1, 1.0),
    ('state', 'ACCEPTED', 'Accepted Vulnerability', NULL, 2, 80.0, 3, 0.8),
    ('state', 'MITIGATED', 'Mitigated Vulnerability', NULL, 3, 40.0, 4, 0.4),
    ('state', 'REMEDIATED', 'Remediated Vulnerability', NULL, 4, 0.0, 5, 0.0),
    ('state', 'UNKNOWN', 'Unknown State', NULL, 5, 50.0, 2, 0.5),
    
    -- Vulnerability Tags
    ('tag', 'CISA Known Exploit', 'CISA Known Exploit', NULL, 1, 95.0, 1, 1.0)
ON CONFLICT (enum_type, code) DO NOTHING;

-- ============================================================================
-- Software Metadata (Combined)
-- ============================================================================
-- Combines: product_category, os_enum, sw_part, product_state, patch_state, vuln_state

CREATE TABLE IF NOT EXISTS software_metadata (
    id SERIAL PRIMARY KEY,
    enum_type VARCHAR(50) NOT NULL,  -- 'category', 'os', 'part', 'product_state', 'patch_state', 'vuln_state'
    code VARCHAR(50) NOT NULL,
    description TEXT,
    priority_order INTEGER,
    risk_score DECIMAL(10,2),  -- Risk score for this software classification
    maintenance_priority INTEGER,  -- Priority for maintenance/updates
    weight DECIMAL(5,3) DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(enum_type, code)
);

CREATE INDEX idx_software_metadata_type ON software_metadata(enum_type);
CREATE INDEX idx_software_metadata_priority ON software_metadata(priority_order);

INSERT INTO software_metadata (enum_type, code, description, priority_order, risk_score, maintenance_priority, weight) VALUES
    -- Product Categories
    ('category', 'OPERATING SYSTEM', 'Operating System', 1, 90.0, 1, 1.0),
    ('category', 'SECURITY', 'Security Software', 2, 85.0, 1, 0.95),
    ('category', 'APPLICATION', 'Application', 3, 70.0, 2, 0.8),
    ('category', 'BROWSER', 'Browser', 4, 65.0, 2, 0.75),
    ('category', 'PLUGIN', 'Plugin', 5, 60.0, 3, 0.7),
    ('category', 'HARDWARE', 'Hardware', 6, 50.0, 4, 0.6),
    ('category', 'UNKNOWN', 'Unknown', 7, 30.0, 5, 0.3),
    
    -- OS Types
    ('os', 'WINDOWS', 'Windows', 1, 85.0, 1, 1.0),
    ('os', 'LINUX', 'Linux', 2, 80.0, 1, 0.95),
    ('os', 'MAC', 'macOS', 3, 75.0, 2, 0.9),
    ('os', 'UNKNOWN', 'Unknown', 4, 30.0, 5, 0.3),
    
    -- Software Parts
    ('part', 'OS', 'Operating System', 1, 90.0, 1, 1.0),
    ('part', 'App', 'Application', 2, 70.0, 2, 0.8),
    ('part', 'Pkg', 'Package', 3, 60.0, 3, 0.7),
    
    -- Product States (ordered by risk)
    ('product_state', 'EOL', 'End of Life', 1, 95.0, 1, 1.0),
    ('product_state', 'VULNERABLE', 'Vulnerable', 2, 90.0, 1, 0.95),
    ('product_state', 'UNPATCHED', 'Unpatched', 3, 85.0, 1, 0.9),
    ('product_state', 'UPDATABLE', 'Updatable', 4, 50.0, 3, 0.5),
    ('product_state', 'PATCHED', 'Patched', 5, 20.0, 5, 0.2),
    ('product_state', 'UNKNOWN', 'Unknown', 6, 40.0, 4, 0.4),
    
    -- Patch States
    ('patch_state', 'AVAILABLE', 'Patch Available', 1, 80.0, 1, 0.9),
    ('patch_state', 'PENDING', 'Patch Pending', 2, 70.0, 2, 0.8),
    ('patch_state', 'REBOOT PENDING', 'Reboot Pending', 3, 60.0, 2, 0.7),
    ('patch_state', 'INSTALLED', 'Patch Installed', 4, 20.0, 5, 0.2),
    ('patch_state', 'SUPERSEDED', 'Patch Superseded', 5, 30.0, 4, 0.3),
    
    -- Vulnerability States (for software)
    ('vuln_state', 'EXPOSED', 'Exposed', 1, 100.0, 1, 1.0),
    ('vuln_state', 'UNEXPOSED', 'Unexposed', 2, 50.0, 3, 0.5),
    ('vuln_state', 'REMEDIATED', 'Remediated', 3, 0.0, 5, 0.0)
ON CONFLICT (enum_type, code) DO NOTHING;

-- ============================================================================
-- State & Status Metadata (Combined)
-- ============================================================================
-- Combines: risk_issue_states, process_status, project_status, project_processing_status

CREATE TABLE IF NOT EXISTS state_status_metadata (
    id SERIAL PRIMARY KEY,
    enum_type VARCHAR(50) NOT NULL,  -- 'risk_state', 'process_status', 'project_status', 'project_processing_status'
    code VARCHAR(50) NOT NULL,
    description TEXT,
    status_order INTEGER,  -- Order in workflow
    is_active BOOLEAN DEFAULT TRUE,  -- Whether this is an active state
    is_terminal BOOLEAN DEFAULT FALSE,  -- Whether this is a terminal/final state
    priority_order INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(enum_type, code)
);

CREATE INDEX idx_state_status_type ON state_status_metadata(enum_type);
CREATE INDEX idx_state_status_active ON state_status_metadata(is_active);

INSERT INTO state_status_metadata (enum_type, code, description, status_order, is_active, is_terminal, priority_order) VALUES
    -- Risk Issue States
    ('risk_state', 'ACTIVE', 'Active', 1, TRUE, FALSE, 1),
    ('risk_state', 'ACCEPTED_BY_USER', 'Accepted by User', 2, FALSE, FALSE, 3),
    ('risk_state', 'ACCEPTED_ML_INFERENCE', 'Accepted ML Inference', 3, FALSE, FALSE, 4),
    ('risk_state', 'MITIGATED', 'Mitigated', 4, FALSE, FALSE, 2),
    ('risk_state', 'REMEDIATED', 'Remediated', 5, FALSE, TRUE, 5),
    ('risk_state', 'ERROR', 'Error', 6, FALSE, FALSE, 6),
    ('risk_state', 'DROP', 'Drop', 7, FALSE, TRUE, 7),
    
    -- Process Status
    ('process_status', 'SUCCESS', 'Success', 1, TRUE, TRUE, 1),
    ('process_status', 'DROPPED', 'Dropped', 2, FALSE, TRUE, 3),
    ('process_status', 'FAILURE', 'Failure', 3, FALSE, TRUE, 2),
    
    -- Project Status
    ('project_status', 'CREATING', 'Creating', 1, TRUE, FALSE, 1),
    ('project_status', 'ON TRACK', 'On Track', 2, TRUE, FALSE, 2),
    ('project_status', 'WARNING', 'Warning', 3, TRUE, FALSE, 3),
    ('project_status', 'PAST DUE', 'Past Due', 4, TRUE, FALSE, 4),
    ('project_status', 'COMPLETED', 'Completed', 5, FALSE, TRUE, 5),
    ('project_status', 'DELETING', 'Deleting', 6, FALSE, FALSE, 6),
    
    -- Project Processing Status
    ('project_processing_status', 'CREATING', 'Creating', 1, TRUE, FALSE, 1),
    ('project_processing_status', 'COMPLETED_DEFINITION', 'Completed Definition', 2, TRUE, FALSE, 2),
    ('project_processing_status', 'COMPLETED_ASSETS', 'Completed Assets', 3, TRUE, FALSE, 3),
    ('project_processing_status', 'COMPLETED_PROJECT_DETAILS', 'Completed Project Details', 4, TRUE, FALSE, 4),
    ('project_processing_status', 'COMPLETED_AGGREGATIONS', 'Completed Aggregations', 5, TRUE, FALSE, 5),
    ('project_processing_status', 'COMPLETED', 'Completed', 6, FALSE, TRUE, 6)
ON CONFLICT (enum_type, code) DO NOTHING;

-- ============================================================================
-- Data Source & Event Metadata
-- ============================================================================

CREATE TABLE IF NOT EXISTS data_source_metadata (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    data_source_type VARCHAR(50),  -- 'sensor', 'import', etc.
    confidence_score DECIMAL(10,2) DEFAULT 1.0,  -- Data quality/confidence (0-1)
    priority_order INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_data_source_priority ON data_source_metadata(priority_order);

INSERT INTO data_source_metadata (code, description, data_source_type, confidence_score, priority_order) VALUES
    ('AD', 'Active Directory', 'sensor', 0.9, 1),
    ('HA', 'HA', 'sensor', 0.95, 2),
    ('COMPONENT', 'Component', 'sensor', 0.9, 3),
    ('SNMP', 'SNMP', 'sensor', 0.85, 4),
    ('NA', 'NA', 'sensor', 0.8, 5),
    ('TA', 'TA', 'sensor', 0.75, 6),
    ('PROCESSES', 'Processes', 'sensor', 0.8, 7),
    ('IMPORT', 'Import', 'import', 0.9, 8)
ON CONFLICT (code) DO NOTHING;

CREATE TABLE IF NOT EXISTS event_type_metadata (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    priority_order INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO event_type_metadata (code, description, priority_order) VALUES
    ('first_observed', 'First Observed', 1),
    ('threat_change', 'Threat Change', 2),
    ('last_observed', 'Last Observed', 3)
ON CONFLICT (code) DO NOTHING;

-- ============================================================================
-- Roles Metadata
-- ============================================================================

CREATE TABLE IF NOT EXISTS roles_metadata (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    role_category VARCHAR(50),  -- 'admin', 'service', 'cloud', 'cmdb'
    is_admin_role BOOLEAN DEFAULT FALSE,
    is_proxy_role BOOLEAN DEFAULT FALSE,
    criticality_score DECIMAL(10,2),  -- Criticality of this role (0-100)
    risk_weight DECIMAL(5,3) DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_roles_category ON roles_metadata(role_category);
CREATE INDEX idx_roles_admin ON roles_metadata(is_admin_role);
CREATE INDEX idx_roles_criticality ON roles_metadata(criticality_score);

INSERT INTO roles_metadata (code, description, role_category, is_admin_role, is_proxy_role, criticality_score, risk_weight) VALUES
    -- Admin Roles
    ('NW-ADMIN', 'Network Admin', 'admin', TRUE, FALSE, 95.0, 1.0),
    ('WIN-ADMIN', 'Windows Admin', 'admin', TRUE, FALSE, 95.0, 1.0),
    
    -- Proxy Roles
    ('HTTP-PROXY', 'HTTP Proxy', 'service', FALSE, TRUE, 70.0, 0.8),
    ('SQUID', 'Squid', 'service', FALSE, TRUE, 70.0, 0.8),
    ('SOCKS', 'SOCKS', 'service', FALSE, TRUE, 65.0, 0.75),
    
    -- High Criticality Services
    ('DNS', 'DNS', 'service', FALSE, FALSE, 90.0, 0.95),
    ('DHCP', 'DHCP', 'service', FALSE, FALSE, 85.0, 0.9),
    ('LDAP', 'LDAP', 'service', FALSE, FALSE, 90.0, 0.95),
    ('LDAP-S', 'LDAP Secure', 'service', FALSE, FALSE, 85.0, 0.9),
    ('Kerb', 'Kerberos', 'service', FALSE, FALSE, 90.0, 0.95),
    ('RDP', 'RDP', 'service', FALSE, FALSE, 85.0, 0.9),
    ('SSH', 'SSH', 'service', FALSE, FALSE, 80.0, 0.85),
    ('VPN', 'VPN', 'service', FALSE, FALSE, 85.0, 0.9),
    ('WEB-SRVR', 'Web Server', 'service', FALSE, FALSE, 75.0, 0.8),
    
    -- Database Services
    ('MSSQL', 'MS SQL', 'service', FALSE, FALSE, 90.0, 0.95),
    ('MySQL', 'MySQL', 'service', FALSE, FALSE, 85.0, 0.9),
    ('Postgres', 'PostgreSQL', 'service', FALSE, FALSE, 85.0, 0.9),
    ('RDBMS', 'RDBMS', 'service', FALSE, FALSE, 85.0, 0.9),
    ('SAP-HANA', 'SAP HANA', 'service', FALSE, FALSE, 90.0, 0.95),
    
    -- Other Services
    ('ADC', 'ADC', 'service', FALSE, FALSE, 80.0, 0.85),
    ('EXCH', 'Exchange', 'service', FALSE, FALSE, 85.0, 0.9),
    ('SMTP', 'SMTP', 'service', FALSE, FALSE, 75.0, 0.8),
    ('SMTP-S', 'SMTP Secure', 'service', FALSE, FALSE, 70.0, 0.75),
    ('IMAP', 'IMAP', 'service', FALSE, FALSE, 70.0, 0.75),
    ('IMAP-S', 'IMAP Secure', 'service', FALSE, FALSE, 65.0, 0.7),
    ('POP3', 'POP3', 'service', FALSE, FALSE, 65.0, 0.7),
    ('POP3-S', 'POP3 Secure', 'service', FALSE, FALSE, 65.0, 0.7),
    ('FTP', 'FTP', 'service', FALSE, FALSE, 60.0, 0.65),
    ('TELNET', 'Telnet', 'service', FALSE, FALSE, 55.0, 0.6),
    ('VNC', 'VNC', 'service', FALSE, FALSE, 70.0, 0.75),
    
    -- Infrastructure
    ('HYPERVISOR', 'Hypervisor', 'service', FALSE, FALSE, 90.0, 0.95),
    ('Hyper-V', 'Hyper-V', 'service', FALSE, FALSE, 85.0, 0.9),
    ('Xen', 'Xen', 'service', FALSE, FALSE, 85.0, 0.9),
    ('Openstack', 'OpenStack', 'service', FALSE, FALSE, 80.0, 0.85),
    ('NAS', 'NAS', 'service', FALSE, FALSE, 75.0, 0.8),
    ('NFS', 'NFS', 'service', FALSE, FALSE, 70.0, 0.75),
    ('iSCSI', 'iSCSI', 'service', FALSE, FALSE, 75.0, 0.8),
    
    -- Management
    ('SCCM', 'SCCM', 'service', FALSE, FALSE, 85.0, 0.9),
    ('MS-Updt', 'MS Update', 'service', FALSE, FALSE, 80.0, 0.85),
    ('MS-ForeF', 'MS Forefront', 'service', FALSE, FALSE, 75.0, 0.8),
    ('Puppet', 'Puppet', 'service', FALSE, FALSE, 75.0, 0.8),
    ('Landesk', 'Landesk', 'service', FALSE, FALSE, 70.0, 0.75),
    
    -- Other
    ('CODE-REPO', 'Code Repository', 'service', FALSE, FALSE, 80.0, 0.85),
    ('BIGDATA-ANALYTICS', 'Big Data Analytics', 'service', FALSE, FALSE, 75.0, 0.8),
    ('CRM', 'CRM', 'service', FALSE, FALSE, 70.0, 0.75),
    ('SAP-ABAP', 'SAP ABAP', 'service', FALSE, FALSE, 80.0, 0.85),
    ('SAP-BIZ', 'SAP Business', 'service', FALSE, FALSE, 75.0, 0.8),
    ('SAP-SRVS', 'SAP Services', 'service', FALSE, FALSE, 75.0, 0.8),
    ('ORCL-EM', 'Oracle Enterprise Manager', 'service', FALSE, FALSE, 80.0, 0.85),
    ('JDE-ENT1', 'JDE Enterprise One', 'service', FALSE, FALSE, 75.0, 0.8),
    ('ICM', 'ICM', 'service', FALSE, FALSE, 70.0, 0.75),
    ('R-SVC', 'R Service', 'service', FALSE, FALSE, 60.0, 0.65),
    ('RADIUS', 'RADIUS', 'service', FALSE, FALSE, 75.0, 0.8),
    ('WINS', 'WINS', 'service', FALSE, FALSE, 60.0, 0.65),
    ('Print', 'Print', 'service', FALSE, FALSE, 50.0, 0.5),
    ('Perf', 'Performance', 'service', FALSE, FALSE, 60.0, 0.65),
    ('MM', 'Multimedia', 'service', FALSE, FALSE, 50.0, 0.5),
    ('VoIP', 'VoIP', 'service', FALSE, FALSE, 70.0, 0.75),
    ('Skype', 'Skype', 'service', FALSE, FALSE, 60.0, 0.65),
    ('Chargen', 'Chargen', 'service', FALSE, FALSE, 40.0, 0.4),
    ('UUCP', 'UUCP', 'service', FALSE, FALSE, 40.0, 0.4),
    ('Ident', 'Identity', 'service', FALSE, FALSE, 70.0, 0.75),
    ('DC', 'DC', 'service', FALSE, FALSE, 85.0, 0.9),
    ('SP', 'SP', 'service', FALSE, FALSE, 60.0, 0.65),
    
    -- CMDB Roles
    ('BCA', 'BCA', 'cmdb', FALSE, FALSE, 90.0, 0.95),
    ('CRITICAL', 'Critical', 'cmdb', FALSE, FALSE, 85.0, 0.9),
    ('VITAL', 'Vital', 'cmdb', FALSE, FALSE, 80.0, 0.85),
    ('SENSITIVE', 'Sensitive', 'cmdb', FALSE, FALSE, 75.0, 0.8),
    ('NON-CRITICAL', 'Non-Critical', 'cmdb', FALSE, FALSE, 50.0, 0.5),
    
    -- Cloud Roles
    ('Compute-Instance', 'Compute Instance', 'cloud', FALSE, FALSE, 85.0, 0.9),
    ('EC2', 'EC2', 'cloud', FALSE, FALSE, 85.0, 0.9),
    ('Storage-Container', 'Storage Container', 'cloud', FALSE, FALSE, 80.0, 0.85),
    ('VPC', 'VPC', 'cloud', FALSE, FALSE, 85.0, 0.9),
    ('Container-Management', 'Container Management', 'cloud', FALSE, FALSE, 80.0, 0.85),
    ('Kubernetes', 'Kubernetes', 'cloud', FALSE, FALSE, 85.0, 0.9),
    ('Elasticsearch-Instance', 'Elasticsearch Instance', 'cloud', FALSE, FALSE, 80.0, 0.85),
    ('Database-Instance', 'Database Instance', 'cloud', FALSE, FALSE, 90.0, 0.95)
ON CONFLICT (code) DO NOTHING;

-- ============================================================================
-- Pipeline & Processing Metadata
-- ============================================================================

CREATE TABLE IF NOT EXISTS pipeline_metadata (
    id SERIAL PRIMARY KEY,
    enum_type VARCHAR(50) NOT NULL,  -- 'module', 'module_trigger', 'process_task'
    code VARCHAR(50) NOT NULL,
    description TEXT,
    priority_order INTEGER,
    execution_order INTEGER,  -- Order in pipeline execution
    weight DECIMAL(5,3) DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(enum_type, code)
);

CREATE INDEX idx_pipeline_metadata_type ON pipeline_metadata(enum_type);
CREATE INDEX idx_pipeline_execution_order ON pipeline_metadata(execution_order);

INSERT INTO pipeline_metadata (enum_type, code, description, priority_order, execution_order, weight) VALUES
    -- Modules
    ('module', 'ALL_DATA', 'All Data', 1, 0, 1.0),
    ('module', 'DATA_INTERPRETER', 'Data Interpreter', 2, 1, 1.0),
    ('module', 'TAGGER', 'Tagger', 3, 2, 1.0),
    ('module', 'VULS_TAGGER', 'Vulnerabilities Tagger', 4, 3, 1.0),
    ('module', 'FEATURIZATION', 'Featurization', 5, 4, 1.0),
    ('module', 'CATEGORIZATION', 'Categorization', 6, 5, 1.0),
    ('module', 'CATEGORIZER', 'Categorizer', 7, 6, 1.0),
    ('module', 'EXPERT_SYSTEM', 'Expert System', 8, 7, 1.0),
    ('module', 'LIKELIHOOD', 'Likelihood', 9, 8, 1.0),
    ('module', 'IMPACT_ALLOCATOR', 'Impact Allocator', 10, 9, 1.0),
    ('module', 'MTTP', 'MTTP', 11, 10, 1.0),
    
    -- Module Triggers
    ('module_trigger', 'TRIGGERED', 'Triggered', 1, 1, 1.0),
    ('module_trigger', 'NOT_TRIGGERED', 'Not Triggered', 2, 0, 0.0),
    
    -- Process Tasks
    ('process_task', '0', 'Drop', 1, 0, 0.0),
    ('process_task', '1', 'Replicate', 2, 1, 0.5),
    ('process_task', '2', 'Process', 3, 2, 1.0)
ON CONFLICT (enum_type, code) DO NOTHING;

-- ============================================================================
-- Operations Metrics Metadata
-- ============================================================================

CREATE TABLE IF NOT EXISTS ops_metrics_metadata (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    metric_type VARCHAR(50),  -- 'ttr', 'mttr', 'mttr_threat', 'mttr_severity'
    priority_order INTEGER,
    weight DECIMAL(5,3) DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ops_metrics_type ON ops_metrics_metadata(metric_type);

INSERT INTO ops_metrics_metadata (code, description, metric_type, priority_order, weight) VALUES
    ('TTR_DAYS', 'Time to Remediate (Days)', 'ttr', 1, 1.0),
    ('MTTR_DAYS', 'Mean Time to Remediate (Days)', 'mttr', 2, 1.0),
    ('MTTR_CRITICAL_THREAT_DAYS', 'MTTR Critical Threat (Days)', 'mttr_threat', 3, 1.0),
    ('MTTR_HIGH_THREAT_DAYS', 'MTTR High Threat (Days)', 'mttr_threat', 4, 0.8),
    ('MTTR_CRITICAL_SEVERITY_DAYS', 'MTTR Critical Severity (Days)', 'mttr_severity', 5, 1.0),
    ('MTTR_HIGH_SEVERITY_DAYS', 'MTTR High Severity (Days)', 'mttr_severity', 6, 0.8)
ON CONFLICT (code) DO NOTHING;

-- ============================================================================
-- Protocol & Port Metadata
-- ============================================================================

CREATE TABLE IF NOT EXISTS protocol_port_metadata (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    port_number INTEGER NOT NULL,
    description TEXT,
    protocol_type VARCHAR(50),  -- 'tcp', 'udp', 'both'
    security_risk_score DECIMAL(10,2),  -- Security risk (0-100)
    is_insecure BOOLEAN DEFAULT FALSE,
    priority_order INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_protocol_port_number ON protocol_port_metadata(port_number);
CREATE INDEX idx_protocol_port_risk ON protocol_port_metadata(security_risk_score);

INSERT INTO protocol_port_metadata (code, port_number, description, protocol_type, security_risk_score, is_insecure, priority_order) VALUES
    ('SSH', 22, 'SSH', 'tcp', 30.0, FALSE, 1),
    ('SMTP', 25, 'SMTP', 'tcp', 50.0, FALSE, 2),
    ('FTP', 21, 'FTP', 'tcp', 80.0, TRUE, 3),
    ('TELNET', 23, 'Telnet', 'tcp', 90.0, TRUE, 4),
    ('HTTP', 80, 'HTTP', 'tcp', 70.0, TRUE, 5),
    ('LDAP', 389, 'LDAP', 'tcp', 75.0, TRUE, 6)
ON CONFLICT (code) DO NOTHING;

-- ============================================================================
-- SSL/TLS Protocol Versions Metadata
-- ============================================================================

CREATE TABLE IF NOT EXISTS ssl_tls_version_metadata (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    version_order INTEGER NOT NULL,  -- Chronological order
    security_score DECIMAL(10,2) NOT NULL,  -- Security score (0-100)
    is_vulnerable BOOLEAN DEFAULT TRUE,
    is_deprecated BOOLEAN DEFAULT TRUE,
    priority_order INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ssl_tls_version_order ON ssl_tls_version_metadata(version_order);
CREATE INDEX idx_ssl_tls_security_score ON ssl_tls_version_metadata(security_score);

INSERT INTO ssl_tls_version_metadata (code, description, version_order, security_score, is_vulnerable, is_deprecated, priority_order) VALUES
    ('sslv2', 'SSL v2.0', 1, 0.0, TRUE, TRUE, 1),
    ('sslv3', 'SSL v3.0', 2, 10.0, TRUE, TRUE, 2),
    ('tlsv0', 'TLS v1.0', 3, 30.0, TRUE, TRUE, 3),
    ('tlsv1', 'TLS v1.1', 4, 40.0, TRUE, TRUE, 4),
    ('tlsv2', 'TLS v1.2', 5, 80.0, FALSE, FALSE, 5),
    ('tlsv3', 'TLS v1.3', 6, 100.0, FALSE, FALSE, 6)
ON CONFLICT (code) DO NOTHING;

-- ============================================================================
-- Credential Usage Category Metadata
-- ============================================================================

CREATE TABLE IF NOT EXISTS cred_usage_category_metadata (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    risk_score DECIMAL(10,2) NOT NULL,  -- Risk score (0-100)
    priority_order INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_cred_usage_risk ON cred_usage_category_metadata(risk_score);

INSERT INTO cred_usage_category_metadata (code, description, risk_score, priority_order) VALUES
    ('Intranet', 'Intranet', 40.0, 1),
    ('Internet Work', 'Internet Work', 60.0, 2),
    ('Internet SSO', 'Internet SSO', 70.0, 3),
    ('Internet Leisure', 'Internet Leisure', 80.0, 4),
    ('Internet', 'Internet', 75.0, 5)
ON CONFLICT (code) DO NOTHING;

-- ============================================================================
-- Software Source Metadata
-- ============================================================================

CREATE TABLE IF NOT EXISTS sw_source_metadata (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    data_source_code VARCHAR(50) REFERENCES data_source_metadata(code),
    is_confident BOOLEAN DEFAULT FALSE,
    confidence_score DECIMAL(10,2) DEFAULT 0.5,  -- Data confidence (0-1)
    priority_order INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sw_source_data_source ON sw_source_metadata(data_source_code);
CREATE INDEX idx_sw_source_confidence ON sw_source_metadata(confidence_score);

INSERT INTO sw_source_metadata (code, description, data_source_code, is_confident, confidence_score, priority_order) VALUES
    ('HA_SW_STACK', 'HA Software Stack', 'HA', TRUE, 0.95, 1),
    ('IMPORT_SW_STACK', 'Import Software Stack', 'IMPORT', TRUE, 0.9, 2),
    ('AD_SW_STACK', 'AD Software Stack', 'AD', TRUE, 0.9, 3),
    ('NA_SNMP_SCAN', 'NA SNMP Scan', 'SNMP', TRUE, 0.85, 4),
    ('COMPONENT_SW_STACK', 'Component Software Stack', 'COMPONENT', TRUE, 0.9, 5),
    ('TA_UA_STRING', 'TA User Agent String', 'TA', FALSE, 0.75, 6),
    ('NA_PORT_BANNER', 'NA Port Banner', 'NA', FALSE, 0.8, 7),
    ('PROCESSES_SW_STACK', 'Processes Software Stack', 'PROCESSES', FALSE, 0.8, 8)
ON CONFLICT (code) DO NOTHING;

-- ============================================================================
-- Search Tag Metadata
-- ============================================================================

CREATE TABLE IF NOT EXISTS search_tag_metadata (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    tag_category VARCHAR(50),  -- 'password', 'cve', 'encryption', 'certificate'
    risk_score DECIMAL(10,2),  -- Risk indicator score
    priority_order INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_search_tag_category ON search_tag_metadata(tag_category);
CREATE INDEX idx_search_tag_risk ON search_tag_metadata(risk_score);

INSERT INTO search_tag_metadata (code, description, tag_category, risk_score, priority_order) VALUES
    -- Password related
    ('ftp clear password', 'FTP Clear Password', 'password', 90.0, 1),
    ('http clear password', 'HTTP Clear Password', 'password', 90.0, 2),
    ('ldap clear password', 'LDAP Clear Password', 'password', 85.0, 3),
    ('telnet clear password', 'Telnet Clear Password', 'password', 90.0, 4),
    
    -- CVE related
    ('critical cve on os', 'Critical CVE on OS', 'cve', 95.0, 5),
    ('critical cve on application', 'Critical CVE on Application', 'cve', 90.0, 6),
    
    -- Encryption related
    ('ssl v3', 'SSL v3', 'encryption', 20.0, 7),
    ('tls 1.0', 'TLS 1.0', 'encryption', 30.0, 8),
    ('tls 1.1', 'TLS 1.1', 'encryption', 40.0, 9),
    ('tls 1.2', 'TLS 1.2', 'encryption', 80.0, 10),
    ('bad encryption', 'Bad Encryption', 'encryption', 70.0, 11),
    
    -- Certificate related
    ('expired certificate on server', 'Expired Certificate on Server', 'certificate', 75.0, 12),
    ('self-signed certificate on server', 'Self-Signed Certificate on Server', 'certificate', 70.0, 13)
ON CONFLICT (code) DO NOTHING;

-- ============================================================================
-- Likelihood Vulnerability Attributes Metadata
-- ============================================================================

CREATE TABLE IF NOT EXISTS likelihood_vuln_attributes_metadata (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    attribute_type VARCHAR(50),  -- 'exploitability', 'exposure', 'impact', 'mitigation'
    weight DECIMAL(5,3) DEFAULT 1.0,  -- Weight in likelihood calculation
    priority_order INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_likelihood_attr_type ON likelihood_vuln_attributes_metadata(attribute_type);

INSERT INTO likelihood_vuln_attributes_metadata (code, description, attribute_type, weight, priority_order) VALUES
    ('accessibility', 'Accessibility', 'exploitability', 1.0, 1),
    ('complexity', 'Complexity', 'exploitability', 0.9, 2),
    ('exploit_maturity', 'Exploit Maturity', 'exploitability', 1.0, 3),
    ('exposure', 'Exposure', 'exposure', 1.0, 4),
    ('intent', 'Intent', 'exploitability', 0.8, 5),
    ('mitigation', 'Mitigation', 'mitigation', 0.9, 6),
    ('severity', 'Severity', 'impact', 1.0, 7)
ON CONFLICT (code) DO NOTHING;

-- ============================================================================
-- CPE Metadata
-- ============================================================================

CREATE TABLE IF NOT EXISTS cpe_metadata (
    id SERIAL PRIMARY KEY,
    enum_type VARCHAR(50) NOT NULL,  -- 'portion', 'version_range_specifier'
    code VARCHAR(50) NOT NULL,
    description TEXT,
    portion_order INTEGER,  -- Order in CPE string
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(enum_type, code)
);

CREATE INDEX idx_cpe_metadata_type ON cpe_metadata(enum_type);

INSERT INTO cpe_metadata (enum_type, code, description, portion_order) VALUES
    -- CPE Portions
    ('portion', 'cpe_header', 'CPE Header', 0),
    ('portion', 'cpe_p', 'CPE Part', 1),
    ('portion', 'cpe_pv', 'CPE Part Vendor', 2),
    ('portion', 'cpe_pvp', 'CPE Part Vendor Product', 3),
    ('portion', 'cpe_pvpv', 'CPE Part Vendor Product Version', 4),
    ('portion', 'cpe_pvpvu', 'CPE Part Vendor Product Version Update', 5),
    ('portion', 'cpe_pvpvue', 'CPE Part Vendor Product Version Update Edition', 6),
    ('portion', 'cpe_pvpvuel', 'CPE Part Vendor Product Version Update Edition Language', 7),
    ('portion', 'cpe_pvpvuels', 'CPE Part Vendor Product Version Update Edition Language SW Edition', 8),
    ('portion', 'cpe_pvpvuelst', 'CPE Part Vendor Product Version Update Edition Language SW Edition Target SW', 9),
    ('portion', 'cpe_pvpvuelstto', 'CPE Part Vendor Product Version Update Edition Language SW Edition Target SW Target HW Other', 10),
    
    -- Version Range Specifiers
    ('version_range_specifier', 'versionStartIncluding', 'Version Start Including', 1),
    ('version_range_specifier', 'versionEndIncluding', 'Version End Including', 2),
    ('version_range_specifier', 'versionStartExcluding', 'Version Start Excluding', 3),
    ('version_range_specifier', 'versionEndExcluding', 'Version End Excluding', 4)
ON CONFLICT (enum_type, code) DO NOTHING;

-- ============================================================================
-- Cloud Connector Vulnerability Metadata
-- ============================================================================

CREATE TABLE IF NOT EXISTS cloud_connector_vuln_metadata (
    id SERIAL PRIMARY KEY,
    code VARCHAR(200) UNIQUE NOT NULL,
    description TEXT,
    cloud_service VARCHAR(50),  -- 'EC2', 'S3', 'VPC', 'IAM'
    vulnerability_category VARCHAR(50),  -- 'encryption', 'access', 'logging', 'network'
    risk_score DECIMAL(10,2) NOT NULL,  -- Risk score (0-100)
    remediation_priority INTEGER,  -- 1 = highest priority
    compliance_impact BOOLEAN DEFAULT FALSE,  -- Whether this affects compliance
    weight DECIMAL(5,3) DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_cloud_vuln_service ON cloud_connector_vuln_metadata(cloud_service);
CREATE INDEX idx_cloud_vuln_category ON cloud_connector_vuln_metadata(vulnerability_category);
CREATE INDEX idx_cloud_vuln_risk ON cloud_connector_vuln_metadata(risk_score);

INSERT INTO cloud_connector_vuln_metadata (code, description, cloud_service, vulnerability_category, risk_score, remediation_priority, compliance_impact, weight) VALUES
    -- EC2 Issues
    ('EBS Volumes are unencrypted on EC2 instances', 'EBS Volumes are unencrypted on EC2 instances', 'EC2', 'encryption', 85.0, 1, TRUE, 1.0),
    ('EBS snapshots are publicly restorable', 'EBS snapshots are publicly restorable', 'EC2', 'access', 90.0, 1, TRUE, 1.0),
    ('Security groups allow unrestricted access to port 22 (SSH) on EC2 instances', 'Security groups allow unrestricted access to port 22 (SSH) on EC2 instances', 'EC2', 'network', 80.0, 2, TRUE, 0.9),
    ('Security groups allow unrestricted access to port 3389 (RDP) on EC2 instances', 'Security groups allow unrestricted access to port 3389 (RDP) on EC2 instances', 'EC2', 'network', 80.0, 2, TRUE, 0.9),
    ('Unused security groups on EC2 instances', 'Unused security groups on EC2 instances', 'EC2', 'network', 40.0, 4, FALSE, 0.4),
    
    -- S3 Issues
    ('Public access to S3 buckets and objects is permitted via new ACLs', 'Public access to S3 buckets and objects is permitted via new ACLs', 'S3', 'access', 95.0, 1, TRUE, 1.0),
    ('Public access to S3 buckets and objects is permitted via new policies', 'Public access to S3 buckets and objects is permitted via new policies', 'S3', 'access', 95.0, 1, TRUE, 1.0),
    ('Public and cross-account access is permitted for S3 buckets with public policies', 'Public and cross-account access is permitted for S3 buckets with public policies', 'S3', 'access', 90.0, 1, TRUE, 1.0),
    ('HTTPS connections are not enforced on S3 buckets', 'HTTPS connections are not enforced on S3 buckets', 'S3', 'encryption', 70.0, 3, TRUE, 0.8),
    ('MFA is not required to delete or change S3 bucket versions', 'MFA is not required to delete or change S3 bucket versions', 'S3', 'access', 75.0, 2, TRUE, 0.85),
    ('Server access logging is disabled on S3 buckets', 'Server access logging is disabled on S3 buckets', 'S3', 'logging', 60.0, 3, FALSE, 0.7),
    ('Object versioning is disabled on S3 buckets', 'Object versioning is disabled on S3 buckets', 'S3', 'access', 65.0, 3, FALSE, 0.75),
    ('Default server-side encryption is disabled on S3 buckets', 'Default server-side encryption is disabled on S3 buckets', 'S3', 'encryption', 80.0, 2, TRUE, 0.9),
    ('Public access via ACLs is permitted on S3 buckets', 'Public access via ACLs is permitted on S3 buckets', 'S3', 'access', 90.0, 1, TRUE, 1.0),
    ('CloudTrail logs are publicly accessible on S3 buckets', 'CloudTrail logs are publicly accessible on S3 buckets', 'S3', 'access', 85.0, 1, TRUE, 0.95),
    
    -- VPC Issues
    ('VPC Flow logging is disabled', 'VPC Flow logging is disabled', 'VPC', 'logging', 70.0, 3, FALSE, 0.8),
    ('Default security group does not prohibit inbound and outbound traffic on the VPC', 'Default security group does not prohibit inbound and outbound traffic on the VPC', 'VPC', 'network', 75.0, 2, TRUE, 0.85)
ON CONFLICT (code) DO NOTHING;

-- ============================================================================
-- CVSS Metadata (Combined)
-- ============================================================================
-- Combines all CVSS v2 and v3 enums

CREATE TABLE IF NOT EXISTS cvss_metadata (
    id SERIAL PRIMARY KEY,
    cvss_version VARCHAR(10) NOT NULL,  -- 'v2' or 'v3'
    metric_type VARCHAR(50) NOT NULL,  -- 'base_metric', 'access_vector', 'access_complexity', etc.
    code VARCHAR(10) NOT NULL,
    description TEXT,
    numeric_value INTEGER,  -- Numeric value for calculations
    weight DECIMAL(5,3) DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(cvss_version, metric_type, code)
);

CREATE INDEX idx_cvss_version ON cvss_metadata(cvss_version);
CREATE INDEX idx_cvss_metric_type ON cvss_metadata(metric_type);

-- CVSS v2 Base Metrics
INSERT INTO cvss_metadata (cvss_version, metric_type, code, description, weight) VALUES
    ('v2', 'base_metric', 'AV', 'Access Vector', 1.0),
    ('v2', 'base_metric', 'AC', 'Access Complexity', 1.0),
    ('v2', 'base_metric', 'Au', 'Authentication', 1.0),
    ('v2', 'base_metric', 'C', 'Confidentiality Impact', 1.0),
    ('v2', 'base_metric', 'I', 'Integrity Impact', 1.0),
    ('v2', 'base_metric', 'A', 'Availability Impact', 1.0);

-- CVSS v2 Access Vector Values
INSERT INTO cvss_metadata (cvss_version, metric_type, code, description, numeric_value, weight) VALUES
    ('v2', 'access_vector', 'L', 'Local', 0, 0.4),
    ('v2', 'access_vector', 'A', 'Adjacent Network', 1, 0.6),
    ('v2', 'access_vector', 'N', 'Network', 2, 1.0);

-- CVSS v2 Access Complexity Values
INSERT INTO cvss_metadata (cvss_version, metric_type, code, description, numeric_value, weight) VALUES
    ('v2', 'access_complexity', 'H', 'High', 0, 0.4),
    ('v2', 'access_complexity', 'M', 'Medium', 1, 0.6),
    ('v2', 'access_complexity', 'L', 'Low', 2, 1.0);

-- CVSS v2 Authentication Values
INSERT INTO cvss_metadata (cvss_version, metric_type, code, description, numeric_value, weight) VALUES
    ('v2', 'authentication', 'M', 'Multiple', 0, 0.4),
    ('v2', 'authentication', 'S', 'Single', 1, 0.6),
    ('v2', 'authentication', 'N', 'None', 2, 1.0);

-- CVSS v2 Impact Values (Confidentiality, Integrity, Availability)
INSERT INTO cvss_metadata (cvss_version, metric_type, code, description, numeric_value, weight) VALUES
    ('v2', 'confidentiality_impact', 'N', 'None', 0, 0.0),
    ('v2', 'confidentiality_impact', 'P', 'Partial', 1, 0.5),
    ('v2', 'confidentiality_impact', 'C', 'Complete', 2, 1.0),
    ('v2', 'integrity_impact', 'N', 'None', 0, 0.0),
    ('v2', 'integrity_impact', 'P', 'Partial', 1, 0.5),
    ('v2', 'integrity_impact', 'C', 'Complete', 2, 1.0),
    ('v2', 'availability_impact', 'N', 'None', 0, 0.0),
    ('v2', 'availability_impact', 'P', 'Partial', 1, 0.5),
    ('v2', 'availability_impact', 'C', 'Complete', 2, 1.0);

-- CVSS v3 Base Metrics
INSERT INTO cvss_metadata (cvss_version, metric_type, code, description, weight) VALUES
    ('v3', 'base_metric', 'AV', 'Attack Vector', 1.0),
    ('v3', 'base_metric', 'AC', 'Attack Complexity', 1.0),
    ('v3', 'base_metric', 'PR', 'Privileges Required', 1.0),
    ('v3', 'base_metric', 'UI', 'User Interaction', 1.0),
    ('v3', 'base_metric', 'S', 'Scope', 1.0),
    ('v3', 'base_metric', 'C', 'Confidentiality Impact', 1.0),
    ('v3', 'base_metric', 'I', 'Integrity Impact', 1.0),
    ('v3', 'base_metric', 'A', 'Availability Impact', 1.0);

-- CVSS v3 Attack Vector Values
INSERT INTO cvss_metadata (cvss_version, metric_type, code, description, numeric_value, weight) VALUES
    ('v3', 'attack_vector', 'N', 'Network', 0, 1.0),
    ('v3', 'attack_vector', 'A', 'Adjacent Network', 1, 0.7),
    ('v3', 'attack_vector', 'L', 'Local', 2, 0.5),
    ('v3', 'attack_vector', 'P', 'Physical', 3, 0.3);

-- CVSS v3 Attack Complexity Values
INSERT INTO cvss_metadata (cvss_version, metric_type, code, description, numeric_value, weight) VALUES
    ('v3', 'attack_complexity', 'L', 'Low', 0, 1.0),
    ('v3', 'attack_complexity', 'H', 'High', 1, 0.5);

-- CVSS v3 Privileges Required Values
INSERT INTO cvss_metadata (cvss_version, metric_type, code, description, numeric_value, weight) VALUES
    ('v3', 'privileges_required', 'N', 'None', 0, 1.0),
    ('v3', 'privileges_required', 'L', 'Low', 1, 0.7),
    ('v3', 'privileges_required', 'H', 'High', 2, 0.4);

-- CVSS v3 User Interaction Values
INSERT INTO cvss_metadata (cvss_version, metric_type, code, description, numeric_value, weight) VALUES
    ('v3', 'user_interaction', 'N', 'None', 0, 1.0),
    ('v3', 'user_interaction', 'R', 'Required', 1, 0.6);

-- CVSS v3 Scope Values
INSERT INTO cvss_metadata (cvss_version, metric_type, code, description, numeric_value, weight) VALUES
    ('v3', 'scope', 'U', 'Unchanged', 0, 0.8),
    ('v3', 'scope', 'C', 'Changed', 1, 1.0);

-- CVSS v3 Impact Values (Confidentiality, Integrity, Availability)
INSERT INTO cvss_metadata (cvss_version, metric_type, code, description, numeric_value, weight) VALUES
    ('v3', 'confidentiality_impact', 'N', 'None', 0, 0.0),
    ('v3', 'confidentiality_impact', 'L', 'Low', 1, 0.5),
    ('v3', 'confidentiality_impact', 'H', 'High', 2, 1.0),
    ('v3', 'integrity_impact', 'N', 'None', 0, 0.0),
    ('v3', 'integrity_impact', 'L', 'Low', 1, 0.5),
    ('v3', 'integrity_impact', 'H', 'High', 2, 1.0),
    ('v3', 'availability_impact', 'N', 'None', 0, 0.0),
    ('v3', 'availability_impact', 'L', 'Low', 1, 0.5),
    ('v3', 'availability_impact', 'H', 'High', 2, 1.0);

-- ============================================================================
-- Integer-based Strength Level Metadata (Combined)
-- ============================================================================
-- Combines: IntCredentialLevelEnum, IntCipherStrengthLevelEnum, 
--           IntCertificateStrengthLevelEnum, IntEncryptionStrengthLevelEnum

CREATE TABLE IF NOT EXISTS int_strength_level_metadata (
    id SERIAL PRIMARY KEY,
    enum_type VARCHAR(50) NOT NULL,  -- 'credential', 'cipher', 'certificate', 'encryption'
    code INTEGER NOT NULL,
    description TEXT,
    strength_order INTEGER NOT NULL,
    numeric_score DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(enum_type, code)
);

CREATE INDEX idx_int_strength_type ON int_strength_level_metadata(enum_type);
CREATE INDEX idx_int_strength_order ON int_strength_level_metadata(strength_order);

INSERT INTO int_strength_level_metadata (enum_type, code, description, strength_order, numeric_score) VALUES
    -- Credential Levels
    ('credential', 0, 'Empty', 0, 0.0),
    ('credential', 1, 'Default', 1, 10.0),
    ('credential', 2, 'Weak', 2, 30.0),
    ('credential', 3, 'Moderate', 3, 60.0),
    ('credential', 4, 'Strong', 4, 100.0),
    
    -- Cipher Strength Levels
    ('cipher', 1, 'Weak', 1, 20.0),
    ('cipher', 2, 'Moderate', 2, 50.0),
    ('cipher', 3, 'Strong', 3, 100.0),
    
    -- Certificate Strength Levels
    ('certificate', 1, 'Weak', 1, 20.0),
    ('certificate', 2, 'Moderate', 2, 50.0),
    ('certificate', 3, 'Strong', 3, 100.0),
    
    -- Encryption Strength Levels
    ('encryption', 1, 'Weak', 1, 20.0),
    ('encryption', 2, 'Moderate', 2, 50.0),
    ('encryption', 3, 'Strong', 3, 100.0)
ON CONFLICT (enum_type, code) DO NOTHING;

-- ============================================================================
-- Vulnerability Information Metadata (Combined)
-- ============================================================================
-- Stores detailed information about vulnerabilities from both cloud and sensor
-- sources including background, cause, effect, and remediation steps.
-- Cloud vulnerabilities have HTML-formatted remediation, sensor vulnerabilities
-- have plain text remediation.

CREATE TABLE IF NOT EXISTS vuln_info_metadata (
    id SERIAL PRIMARY KEY,
    vuln_code VARCHAR(100) NOT NULL,  -- Enum name (e.g., 'EBS_UNENC_VOL', 'TELNET_23')
    source_type VARCHAR(20) NOT NULL,  -- 'cloud' or 'sensor'
    vuln_description TEXT NOT NULL,  -- Enum value/description
    vulnerability_type VARCHAR(50) NOT NULL,  -- VulnerabilityType enum value
    vulnerability_subtype VARCHAR(50) NOT NULL,  -- VulnerabilitySubType enum value
    background TEXT,  -- Background information about the vulnerability
    cause TEXT,  -- Cause of the vulnerability
    effect TEXT,  -- Effect of the vulnerability
    remediation TEXT,  -- Remediation steps (HTML for cloud, plain text for sensor)
    remediation_format VARCHAR(10) NOT NULL DEFAULT 'text',  -- 'html' or 'text'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(vuln_code, source_type)
);

CREATE INDEX idx_vuln_info_source_type ON vuln_info_metadata(source_type);
CREATE INDEX idx_vuln_info_type ON vuln_info_metadata(vulnerability_type);
CREATE INDEX idx_vuln_info_subtype ON vuln_info_metadata(vulnerability_subtype);
CREATE INDEX idx_vuln_info_type_subtype ON vuln_info_metadata(vulnerability_type, vulnerability_subtype);

INSERT INTO vuln_info_metadata (vuln_code, source_type, vuln_description, vulnerability_type, vulnerability_subtype, background, cause, effect, remediation, remediation_format) VALUES
    ('EBS_UNENC_VOL', 'cloud', 'EBS Volumes are unencrypted on EC2 instances', 'Cloud', 'AWS-EC2',
     'AWS EBS (Elastic Block Storage) provides block-level storage volumes for use with AWS EC2 instances. EBS volumes may be mounted to one or more EC2 instances and provide long-term data persistence.',
     'AWS EBS volumes are unencrypted by default.',
     'Unencrypted EBS volumes are at risk of exposure of sensitive data to an adversary or privileged user with access to the AWS environment.',
     '<p>Encrypt the EBS volume and/or remove unencrypted volumes. To encrypt an EBS volume attached to one or more EC2 instances:</p><ol><li>On the AWS Console, navigate to the Volumes under "Elastic Block Store". Under the Attachment information, note down the Path (example: /dev/xvda) and navigate to the corresponding EC2 instance to which EBS Volume is attached. Stop the EC2 instance associated with the unencrypted EBS volume.<br>AWS Reference here <a href="https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Stop_Start.html#starting-stopping-instances">https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Stop_Start.html#starting-stopping-instances</a></li><li>Create a snapshot of an unencrypted volume. This snapshot will be unencrypted.<br>AWS Reference here <a href="https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-creating-snapshot.html">https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-creating-snapshot.html</a></li><li>Select the Snapshot. From Actions choose: Create Volume. Fill in the appropriate settings and select the Encryption checkbox. Set Encryption Key to AWS-Managed or Customer-Managed CMK (recommended) as per your compliance requirement.<br>AWS Reference here <a href="https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-restoring-volume.html">https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-restoring-volume.html</a></li><li>Detach the unencrypted volume from the EC2 instance.<br>AWS Reference here <a href="https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-detaching-volume.html">https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-detaching-volume.html</a></li><li>To attach the new encrypted volume as the root device for the EC2 instance, navigate to Volumes under "Elastic Block Store"<ul><li>Select Volume</li><li>From Actions, Click Attach</li><li>It will open "Attach Volume" dialogue box</li><li>Choose Instance</li><li>Choose Device (Mount Path) as per noted from Step1</li><li>Click Attach</li></ul>AWS Reference here <a href="https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-attaching-volume.html">https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-attaching-volume.html</a></li><li>Start the EC2 instance and ensure that it functions as expected.</li><li>Delete the original unencrypted volume as you have already created a new encrypted volume.<br>AWS Reference here <a href="https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-deleting-volume.html">https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-deleting-volume.html</a></li><li>Delete the corresponding unencrypted snapshot as the new encrypted volume can be confiured with encrypted snapshots.<br>AWS Reference here <a href="https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-deleting-snapshot.html">https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-deleting-snapshot.html</a></li></ol><p><strong>Note:</strong></p><ul><li>Steps 3,4 can be technically performed while the EC2 instance is running. The instance can then be stopped at Step 5, just before detaching the volume from the instance.</li><li>However, to preserve the consistency of the root device as data is being updated, it is recommended to stop the instance in Step 1 and restart in Step 6.</li></ul>', 'html'),
    
    ('EBS_PUBLIC_RESTORE', 'cloud', 'EBS snapshots are publicly restorable', 'Cloud', 'AWS-EC2',
     'AWS EBS (Elastic Block Storage) snapshots contain a point-in-time copy of your data, and can be used to enable disaster recovery, migrate data across regions and accounts, and improve backup compliance.',
     'Publicly restorable EBS snapshots enable external access to all data contained in each snapshot.',
     'An adversary may gain full access to any sensitive data, credentials, applications, and even previously deleted data contained in the snapshot.',
     '<p>Configure EBS snapshots for private sharing only.</p><p>Using the AWS Console:</p><ol><li>Open the Amazon EC2 console at <a href="https://console.aws.amazon.com/ec2/">https://console.aws.amazon.com/ec2/</a></li><li>Choose Snapshots in the navigation pane</li><li>Select the snapshot and then choose Actions, Modify Permissions</li><li>Choose the Private radio button</li><li>Choose Save</li></ol><p>Using the AWS CLI:</p><ul><li>Execute the following command:<br>aws ec2 modify-snapshot-attribute --snapshot-id [snapshot_id] --attribute createVolumePermission --operation-type remove --group-names all</li></ul><p>AWS Reference here <a href="https://docs.aws.amazon.com/cli/latest/reference/ec2/modify-snapshot-attribute.html">https://docs.aws.amazon.com/cli/latest/reference/ec2/modify-snapshot-attribute.html</a></p>', 'html'),
    
    ('SEC_GRP_22', 'cloud', 'Security groups allow unrestricted access to port 22 (SSH) on EC2 instances', 'Cloud', 'AWS-EC2',
     'An AWS security group functions as a virtual firewall for EC2 instances to control inbound and outbound traffic.',
     'This security group is configured to permit all external Internet traffic into the associated EC2 instances over port 22, typically used for administrator access via SSH.',
     'An adversary may gain full control of the associated EC2 instances and related sensitive data, along with access to the rest of the cloud or network environment.',
     '<p>Update the security groups configuration to restrict Internet access over port 22. SSH access should be restricted to known entities only via static IP addresses. Perform the following to ensure proper security groups configuration:</p><ol><li>Login to the AWS Management Console at <a href="https://console.aws.amazon.com/vpc/home">https://console.aws.amazon.com/vpc/home</a></li><li>In the left pane, click Security Groups</li><li>For each security group, perform the following:</li><li>Select the security group</li><li>Click the Inbound Rules tab</li><li>Ensure that no rule exists that has a port range that includes port 22 and has a Source of 0.0.0.0/0<br><strong>Note:</strong> A port value of ALL or a port range such as 0-1024 are inclusive of port 22</li></ol><p>Reference to control 4.1 in the AWS CIS Foundations Benchmark here <a href="https://d0.awsstatic.com/whitepapers/compliance/AWS_CIS_Foundations_Benchmark.pdf">https://d0.awsstatic.com/whitepapers/compliance/AWS_CIS_Foundations_Benchmark.pdf</a></p>', 'html'),
    
    ('SEC_GRP_3389', 'cloud', 'Security groups allow unrestricted access to port 3389 (RDP) on EC2 instances', 'Cloud', 'AWS-EC2',
     'An AWS security group functions as a virtual firewall for EC2 instances to control inbound and outbound traffic.',
     'This security group is configured to permit all external Internet traffic into the associated EC2 instances over port 3389, typically used for administrator access via RDP.',
     'An adversary may gain full control of the associated EC2 instances and related sensitive data, along with access to the rest of the cloud or network environment.',
     '<p>Update the security groups configuration to restrict Internet access over port 3389. RDP access should be restricted to known entities only via static IP addresses. Perform the following to ensure proper security groups configuration:</p><ol><li>Login to the AWS Management Console at <a href="https://console.aws.amazon.com/vpc/home">https://console.aws.amazon.com/vpc/home</a></li><li>In the left pane, click Security Groups</li><li>For each security group, perform the following:</li><li>Select the security group</li><li>Click the Inbound Rules tab</li><li>Ensure that no rule exists with a port range that includes port 3389 and has a source of 0.0.0.0/0<br><strong>Note:</strong> A port value of ALL or a port range such as 1024-4098 are inclusive of port 3389 .</li></ol><p>Reference to control 4.2 in the AWS CIS Foundations Benchmark here <a href="https://d0.awsstatic.com/whitepapers/compliance/AWS_CIS_Foundations_Benchmark.pdf">https://d0.awsstatic.com/whitepapers/compliance/AWS_CIS_Foundations_Benchmark.pdf</a></p>', 'html'),
    
    ('S3_PUBLIC_ACL_UPLOAD', 'cloud', 'Public access to S3 buckets and objects is permitted via new ACLs', 'Cloud', 'AWS-S3',
     'AWS S3 (Simple Storage Service) provides an object storage service permitting flexible access to data via buckets (containers for stored objects).',
     'This S3 bucket setting permits the use of new public buckets or object Access Control Lists (ACLs) usually configured to ensure that future PUT requests that include them will fail.',
     'An adversary may gain access to view and/or modify the sensitive data contained within S3 buckets.',
     '<p>Update the S3 bucket configuration to "Block new public ACLs and uploading public objects" in the public access settings.</p><p>Using the AWS Console:</p><ol><li>Sign in to the AWS Management Console and open the Amazon S3 console at <a href="https://console.aws.amazon.com/s3/">https://console.aws.amazon.com/s3/</a></li><li>In the Bucket name list, choose the name of the bucket</li><li>Choose permissions and click Public access settings</li><li>Click edit</li><li>In "Manage public access control lists (ACLs)" section, check the box for "Block public access to buckets and objects granted through new access control lists (ACLs)"</li><li>Choose Save</li><li>When you''re asked for confirmation, choose Confirm to save your changes</li></ol><p>Using the AWS CLI:</p><pre><code># aws s3api put-public-access-block --bucket [BucketName] --public-access-block-configuration BlockPublicAcls=true</code></pre><p>For command usage refer here <a href="https://docs.aws.amazon.com/cli/latest/reference/s3api/put-public-access-block.html">https://docs.aws.amazon.com/cli/latest/reference/s3api/put-public-access-block.html</a></p>', 'html'),
    
    ('S3_PUBLIC_BKT_POLICY', 'cloud', 'Public access to S3 buckets and objects is permitted via new policies', 'Cloud', 'AWS-S3',
     'AWS S3 (Simple Storage Service) provides an object storage service permitting flexible access to data via buckets (containers for stored objects).',
     'This S3 bucket policy can be configured to grant public access.',
     'An adversary may gain access to view and/or modify the sensitive data contained within S3 buckets.',
     '<p>Update the S3 bucket configuration to enable "Block new public bucket policies" in the public access settings.</p><p>Using the AWS Console:</p><ol><li>Sign in to the AWS Management Console and open the Amazon S3 console at <a href="https://console.aws.amazon.com/s3/">https://console.aws.amazon.com/s3/</a></li><li>In the Bucket name list, choose the name of the bucket</li><li>Choose permissions and click Public access settings</li><li>Click edit</li><li>In "Manage public bucket policies" section, check the box for "Block public access to buckets and objects granted through new public bucket or access point policies"</li><li>Choose Save</li><li>When you are asked for confirmation, enter confirm. Then choose Confirm to save your changes</li></ol><p>Using the AWS CLI:</p><pre><code># aws s3api put-public-access-block --bucket [BucketName] --public-access-block-configuration BlockPublicPolicy=true</code></pre><p>For command usage refer here <a href="https://docs.aws.amazon.com/cli/latest/reference/s3api/put-public-access-block.html">https://docs.aws.amazon.com/cli/latest/reference/s3api/put-public-access-block.html</a></p>', 'html'),
    
    ('S3_CROSS_ACC_PUBLIC_ACCESS', 'cloud', 'Public and cross-account access is permitted for S3 buckets with public policies', 'Cloud', 'AWS-S3',
     'AWS S3 (Simple Storage Service) provides an object storage service permitting flexible access to data via buckets (containers for stored objects).',
     'As configured, access to these publicly accessible S3 buckets is not limited to the bucket owner and AWS services.',
     'An adversary may gain access to view and/or modify the sensitive data contained within S3 buckets.',
     '<p>Update the S3 bucket configuration to enable "Block public and cross-account access" in the public access settings.</p><p>Using the AWS Console:</p><ol><li>Sign in to the AWS Management Console and open the Amazon S3 console at <a href="https://console.aws.amazon.com/s3/">https://console.aws.amazon.com/s3/</a></li><li>In the Bucket name list, choose the name of the bucket</li><li>Choose permissions and click Public access settings</li><li>Click edit</li><li>In "Manage public bucket policies" section, check the box for "Block public and cross-account access to buckets and objects through any public bucket or access point policies"</li><li>Choose Save</li><li>When you''re asked for confirmation, enter confirm. Then choose Confirm to save your changes</li></ol><p>Using the AWS CLI:</p><pre><code># aws s3api put-public-access-block --bucket [BucketName] --public-access-block-configuration RestrictPublicBuckets=true</code></pre><p>For command usage refer here <a href="https://docs.aws.amazon.com/cli/latest/reference/s3api/put-public-access-block.html">https://docs.aws.amazon.com/cli/latest/reference/s3api/put-public-access-block.html</a></p>', 'html'),
    
    ('S3_HTTPS_ONLY', 'cloud', 'HTTPS connections are not enforced on S3 buckets', 'Cloud', 'AWS-S3',
     'AWS S3 (Simple Storage Service) provides an object storage service permitting flexible access to data via buckets (containers for stored objects). HTTPS (Hypertext Transfer Protocol Secure) is a secure mechanism for data exchange over the Internet.',
     'This S3 bucket configuration is not enforcing secure SSL/TLS-only access by denying all regular, unencrypted HTTP requests to your buckets.',
     'An adversary may gain access to view the sensitive data contained within S3 buckets, as the communication between the clients (users, applications) and these buckets is vulnerable to eavesdropping and man-in-the-middle (MITM) attacks.',
     '<p>Update the S3 bucket configuration to enforce SSL-only access.</p><p>Using the AWS Console:</p><ol><li>Sign in to the AWS Management Console and open the Amazon S3 console.</li><li>Select the S3 bucket that you want to examine and click the Properties tab from the S3 dashboard top right menu.</li><li>Inside the Properties tab, click Permissions to expand the bucket permissions configuration panel.</li><li>Now click Edit bucket policy to access the bucket policy currently in use. If the selected S3 bucket does not have an access policy defined yet, skip the next step and mark the Audit process as complete.</li><li>Inside the Bucket Policy Editor dialog box, verify the policy document for the following elements: "Condition": { "Bool": { "aws:SecureTransport": "true" } }, when the Effect element value is set to "Allow" or "Condition": { "Bool": { "aws:SecureTransport": "false" } } when the Effect value is "Deny". This S3 policy condition will allow only SSL (encrypted) access to the objects stored on the selected bucket. If this condition is not defined within your existing bucket policy, the selected S3 bucket does not protect its data while in-transit (i.e. as it travels to and from Amazon S3).</li></ol>', 'html'),
    
    ('S3_MFA', 'cloud', 'MFA is not required to delete or change S3 bucket versions', 'Cloud', 'AWS-S3',
     'AWS S3 (Simple Storage Service) provides an object storage service permitting flexible access to data via buckets (containers for stored objects). MFA (Multi-factor Authentication) is a mechanism for requiring multiple methods of authentication.',
     'This S3 bucket configuration does not enforce multi-factor authentication (MFA) to delete a version or change the versioning state of the bucket.',
     'Objects (files) can be easily deleted accidently (or intentionally) by AWS users that have access to the S3 buckets, without requiring multiple methods of authentication.',
     '<p>Update the S3 bucket configuration to enable MFA Delete.<br>Using the AWS CLI:</p><pre><code># aws s3api put-bucket-versioning --bucket [BucketName] --versioning-configuration Status=Enabled,MFADelete=Enabled --mfa "[AuthenticationCode]"</code></pre><p><strong>Note:</strong> For more details on this command, please refer here <a href="https://docs.aws.amazon.com/cli/latest/reference/s3api/put-bucket-versioning.html">https://docs.aws.amazon.com/cli/latest/reference/s3api/put-bucket-versioning.html</a></p>', 'html'),
    
    ('S3_LOGGING', 'cloud', 'Server access logging is disabled on S3 buckets', 'Cloud', 'AWS-S3',
     'AWS S3 (Simple Storage Service) provides an object storage service permitting flexible access to data via buckets (containers for stored objects).',
     'S3 buckets with this configuration will not be able to record access requests useful for security audits, typically used in case of unauthorized access.',
     'An adversary may more readily gain control of, or access to, S3 buckets without detection, exposing sensitive data within the buckets.',
     '<p>Update the S3 Buckets configuration to enable server access logging.</p><p>Using the AWS Console:</p><ol><li>Sign in to the AWS management console and open the Amazon S3 console at <a href="https://console.aws.amazon.com/s3/">https://console.aws.amazon.com/s3/</a></li><li>Select the bucket and click Properties.</li><li>On Properties page, Choose Server Access Logging and click Enable Logging.</li><li>Set Target Bucket to receive the log record objects. Set Target Prefix (Optional).<br>Choose save.</li></ol><p>Using the AWS CLI:</p><pre><code># aws s3api put-bucket-logging --bucket [BucketName] --bucket-logging-status</code></pre><p>For command usage refer to <a href="https://docs.aws.amazon.com/cli/latest/reference/s3api/put-bucket-logging.html">https://docs.aws.amazon.com/cli/latest/reference/s3api/put-bucket-logging.html</a></p>', 'html'),
    
    ('S3_OBJ_VER', 'cloud', 'Object versioning is disabled on S3 buckets', 'Cloud', 'AWS-S3',
     'AWS S3 (Simple Storage Service) provides an object storage service permitting flexible access to data via buckets (containers for stored objects).',
     'S3 buckets with this configuration will not be able to preserve and recover overwritten and deleted S3 objects, typically used as an extra layer of data protection and/or data retention.',
     'An adversary may permenantly delete or modify object data within S3 buckets.',
     '<p>Update S3 bucket configuration to enable versioning.</p><p>Using the AWS Console:</p><ol><li>Sign in to the AWS management console and open the Amazon S3 console at <a href="https://console.aws.amazon.com/s3/">https://console.aws.amazon.com/s3/</a></li><li>Select the bucket, click Properties, then select Versioning.</li><li>Choose Enable Versioning and select Save.</li></ol><p>Using the AWS CLI:</p><pre><code># aws s3api put-bucket-versioning --bucket [BucketName] --versioning-configuration [value]</code></pre><p>For command usage refer here <a href="https://docs.aws.amazon.com/cli/latest/reference/s3api/put-bucket-versioning.html">https://docs.aws.amazon.com/cli/latest/reference/s3api/put-bucket-versioning.html</a></p>', 'html'),
    
    ('S3_SRV_ENC', 'cloud', 'Default server-side encryption is disabled on S3 buckets', 'Cloud', 'AWS-S3',
     'AWS S3 (Simple Storage Service) provides an object storage service permitting flexible access to data via buckets (containers for stored objects).',
     'S3 buckets with this configuration do not perform encryption at rest of all data objects in the bucket by default.',
     'An adversary with access to the storage system may also gain access to the sensitive data contained within S3 buckets.',
     '<p>Update S3 bucket configuration to enable default encryption.</p><p>Using the AWS Console:</p><ol><li>Sign in to the AWS Management Console and open the Amazon S3 console at <a href="https://console.aws.amazon.com/s3/">https://console.aws.amazon.com/s3/</a></li><li>In the Bucket name list, choose the desired bucket</li><li>Choose Properties</li><li>Choose Default encryption</li><li>Choose AES-256 or AWS-KMS</li><li>Choose Save</li></ol><p>Using the AWS CLI:</p><pre><code># aws s3api put-bucket-encryption</code></pre><p>For command usage refer here <a href="https://docs.aws.amazon.com/cli/latest/reference/s3api/put-bucket-encryption.html">https://docs.aws.amazon.com/cli/latest/reference/s3api/put-bucket-encryption.html</a></p><p><strong>Impact:</strong></p><p>Updating S3 bucket configuration to enable default encryption may require an update in bucket policy. If AWS KMS option is used for default encryption configuration, it is subjected to the RPS (requests per second) limits of AWS KMS.</p><p><strong>Note:</strong> Updating this configuration for an existing bucket does not encrypt existing objects in the bucket.</p>', 'html'),
    
    ('S3_PUB_ACCESS_ACL', 'cloud', 'Public access via ACLs is permitted on S3 buckets', 'Cloud', 'AWS-S3',
     'AWS S3 (Simple Storage Service) provides an object storage service permitting flexible access to data via buckets (containers for stored objects). An ACL (Access Control List) is used to grant or deny access to digital resources.',
     'S3 buckets with this configuration may evaluate a public ACL when authorizing a request, effectively permitting the bucket or object to be made public.',
     'An adversary may gain access to view and/or modify the sensitive data contained within S3 buckets.',
     '<p>Update S3 Bucket configuration to enable "Remove public access granted through public ACLs" in public access settings.</p><p>Using the AWS Console:</p><ol><li>Sign in to the AWS Management Console and open the Amazon S3 console at <a href="https://console.aws.amazon.com/s3/">https://console.aws.amazon.com/s3/</a></li><li>In the Bucket name list, choose the name of the bucket</li><li>Choose permissions and click Public access settings</li><li>Click edit</li><li>In "Manage public access control lists (ACLs)" section, check the box for "Block public access to buckets and objects granted through any access control lists (ACLs)"</li><li>Choose Save</li><li>When you''re asked for confirmation, enter confirm. Then choose Confirm to save your changes</li></ol><p>Using the AWS CLI:</p><pre><code># aws s3api put-public-access-block --bucket [BucketName] --public-access-block-configuration IgnorePublicAcls=true</code></pre><p>For command usage refer here <a href="https://docs.aws.amazon.com/cli/latest/reference/s3api/put-public-access-block.html">https://docs.aws.amazon.com/cli/latest/reference/s3api/put-public-access-block.html</a></p>', 'html'),
    
    ('S3_CLOUDTRAIL_PUBLIC', 'cloud', 'CloudTrail logs are publicly accessible on S3 buckets', 'Cloud', 'AWS-S3',
     'AWS S3 (Simple Storage Service) provides an object storage service permitting flexible access to data via buckets (containers for stored objects). AWS CloudTrail logs capture account activity related to actions across the AWS infrstructure.',
     'S3 buckets with this configuration permit public access to CloudTrail log data.',
     'An adversary may gain access to the sensitive CloudTrail log data contained within S3 buckets, to either view sensitive data within the logs (such as credentials) or delete/modify log data to remove evidence of an S3 bucket intrusion.',
     '<p>Update the S3 Bucket Configuration to remove any public access that has been granted to the bucket via an ACL or S3 bucket policy.</p><ol><li>Sign in to the AWS Management Console and open the Amazon S3 console at <a href="https://console.aws.amazon.com/s3/">https://console.aws.amazon.com/s3/</a></li><li>Right-click on the bucket and click Properties.</li><li>In the Properties pane, click the Permissions tab.</li><li>The tab shows a list of grants, one row per grant, in the bucket ACL. Each row identifies the grantee and the permissions granted.</li><li>Select the row that grants permission to Everyone or Any Authenticated User</li><li>Uncheck all the permissions granted to Everyone or Any Authenticated User (click x to delete the row).</li><li>Click Save to save the ACL.</li><li>If the Edit bucket policy button is present, click it.</li><li>Remove any Statement having an Effect set to Allow and a Principal set to "*" or {"AWS" : "*"}.</li></ol>', 'html'),
    
    ('VPC_FLOW_LOG', 'cloud', 'VPC Flow logging is disabled', 'Cloud', 'AWS-VPC',
     'A virtual private cloud (VPC) is a virtual network dedicated to your AWS account and logically isolated from other virtual networks in the AWS cloud. VPC Flow Logs capture information related to IP traffic flowing to and from network interfaces in the VPC.',
     'This VPC is not collecting flow logs which are critical to effectively detect security and access issues such as overly permissive security groups or network ACL, remote logons, and threat detection.',
     'Information security teams may take longer to detect intrusions or malicious activity performed by an adversary within the AWS environment, leading to greater risk of a breach.',
     '<p>Perform following to create a flow log for a VPC or subnet:</p><ol><li>Sign in to the AWS Management Console and open the Amazon S3 console at <a href="https://console.aws.amazon.com/vpc/">https://console.aws.amazon.com/vpc/</a></li><li>In the navigation pane, choose Your VPCs, or choose Subnets.</li><li>Select your VPC or subnet, choose the Flow Logs tab, and then Create Flow Log.</li><li>In the dialog box, complete following information. When you are done, choose Create Flow Log:</li><li>Filter: Select whether the flow log should capture rejected traffic, accepted traffic, or all traffic.</li><li>Role: Specify the name of an IAM role that has permission to publish logs to CloudWatch Logs.</li><li>Destination Log Group: Enter the name of a log group in CloudWatch Logs to which the flow logs will be published. You can use an existing log group, or you can enter a name for a new log group, which we''ll create for you.</li></ol><p>AWS reference here <a href="https://docs.aws.amazon.com/AmazonVPC/latest/UserGuide/flow-logs.html#create-flow-log">https://docs.aws.amazon.com/AmazonVPC/latest/UserGuide/flow-logs.html#create-flow-log</a></p><p>Using the AWS CLI:</p><pre><code># aws ec2 create-flow-logs --resource-type [NetworkInterfac]> --resource-ids [resouceID] --traffic-type REJECT --log-group-name [logGrpName] --deliver-logs-permission-arn [Arn]</code></pre><p>For command usage refer here <a href="https://docs.aws.amazon.com/cli/latest/reference/ec2/create-flow-logs.html">https://docs.aws.amazon.com/cli/latest/reference/ec2/create-flow-logs.html</a></p>', 'html'),
    
    ('SEC_GRP_TRAFFIC', 'cloud', 'Default security group does not prohibit inbound and outbound traffic on the VPC', 'Cloud', 'AWS-VPC',
     'A virtual private cloud (VPC) is a virtual network dedicated to your AWS account and logically isolated from other virtual networks in the AWS cloud. An AWS security group functions as a virtual firewall for EC2 instances within the VPC to control inbound and outbound traffic.',
     'This VPC comes with a default security group whose initial configuration allows all inbound and outbound traffic',
     'An adversary may gain full control of the associated EC2 instances and related sensitive data, along with access to the rest of the cloud or network environment.',
     '<p>Update the configuration of all AWS resources attached to the default security group to appropriately restrict inbound and outbound access.</p><ol><li>Sign in to the AWS Management Console and navigate to EC2 dashboard at <a href="https://console.aws.amazon.com/ec2/">https://console.aws.amazon.com/ec2/</a>.</li><li>Identify AWS resources that exist within the default security group.</li><li>Create a set of least privilege security groups for those resources.</li><li>Place the resources in those security groups.</li><li>Remove the associated resources from the default security group.</li><li>For alerted Security Groups, Log in to the AWS console.</li><li>In the console, select the specific region from the ''Region'' drop-down on the top right corner, for which the alert is generated.</li><li>Navigate to the ''VPC'' service.</li><li>For each region, Click on ''Security Groups'' specific to the alert.</li><li>On section ''Inbound rules'', Click on ''Edit Inbound Rules'' and remove the existing rule, click on ''Save''.</li><li>On section ''Outbound rules'', Click on ''Edit Outbound Rules'' and remove the existing rule, click on ''Save''.</li></ol><p>Using the AWS CLI:</p><pre><code># aws ec2 revoke-security-group-ingress --group-id [SecurityGroupId] --ip-permissions ''[{"IpProtocol": "-1", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}]''<br># aws ec2 revoke-security-group-egress --group-id [SecurityGroupId] --ip-permissions ''[{"IpProtocol": "-1",  "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}]''</code></pre>', 'html'),
    
    -- Sensor vulnerabilities
    ('TELNET_23', 'sensor', 'Insecure service detected: TELNET on port 23', 'Services', 'Insecure Services',

    ('TELNET_23', 'sensor', 'Insecure service detected: TELNET on port 23', 'Services', 'Insecure Services',
     'TELNET is a protocol that permits remote access from one computer system to another on the same network.',
     'TELNET uses unencrypted authentication, and transmits usernames, passwords and data over the network in cleartext.',
     'System credentials and sensitive data can be read by an adversary with access to the network traffic, resulting in not only data theft but also longer-term persistent system access to enable future attacks.',
     'Replace TELNET with SSH (Secure Shell) , which encrypts credentials and data. For Linux and Unix systems, the OpenSSH implementation is typically included with the operating system. An alternative is to configure TELNET to utilize a secure authentication mechanism such as Kerberos.', 'text'),
    
    ('HTTP_80', 'sensor', 'Insecure service detected: HTTP on port 80', 'Services', 'Insecure Services',
     'HTTP (or Hypertext Transfer Protocol) is a protocol for fetching resources such as HTML documents, serving as the foundation for data exchange over the Web.',
     'HTTP does not use encryption, transmitting data over the network in cleartext.',
     'HTTP requests and responses can be read by an adversary with access to the network traffic, resulting in theft of sensitive data, such as credentials entered into web forms.',
     'Replace HTTP with HTTPS (Hypertext Transfer Protocol Secure). Proper configuration typically includes obtaining a secure digital certificate to protect from man-in-the-middle attacks, as well as the use of HSTS (HTTP Strict Transport Security) to automatically serve web pages with HTTPS.', 'text'),
    
    ('X11_60XX', 'sensor', 'Insecure service detected: X11 on ports 6000-6063', 'Services', 'Insecure Services',
     'X11 (or X Protocol) is a protocol that enables remote graphical access to applications.',
     'X11 may permit any remote users or applications to access display, keyboard, and mouse input.',
     'A remote malicious application can view and copy screen contents, record keystrokes (including credentials), remotely control browsers and forge keystrokes.',
     'Remove X11 servers not in use and restrict access using appropriate use of the xhost command.', 'text'),
    
    ('LDAP_389', 'sensor', 'Insecure service detected: LDAP on port 389', 'Services', 'Insecure Services',
     'LDAP (or Lightweight Directory Access Protocol), is a protocol for interacting with directory services, typically for user authentication.',
     'LDAP traffic is unsigned and unencrypted by default, passing sensitive directory information such as usernames and passwords over the network in cleartext.',
     'Credentials and sensitive authentication information can be read by an adversary with access to the network traffic. Additionally, unsigned LDAP traffic is vulnerable to man-in-the-middle attacks such as forged LDAP authentication requests.',
     'Replace LDAP with a secure alternative such as LDAPS (LDAP over SSL/TLS) using port 636.', 'text'),
    
    ('POP3_110', 'sensor', 'Insecure service detected: POP3 on port 110', 'Services', 'Insecure Services',
     'POP3 (or Post Office Protocol 3) is a commonly used protocol for receiving email over the Internet.',
     'By default, POP3 transmits usernames and passwords unencrypted in cleartext.',
     'Credentials can be read by an adversary with access to the network traffic, resulting in exposure of sensitive data via email.',
     'Reconfigure POP3 with a secure alternative such as POP3S (POP3 over SSL/TLS) using port 995.', 'text'),
    
    ('IMAP_143', 'sensor', 'Insecure service detected: IMAP on port 143', 'Services', 'Insecure Services',
     'IMAP (or Internet Message Access Protocol) is a protocol used to synch email across multiple devices.',
     'By default, IMAP transmits usernames and passwords unencrypted in cleartext.',
     'Credentials can be read by an adversary with access to the network traffic, resulting in exposure of sensitive data via email.',
     'Reconfigure IMAP with a secure alternative such as IMAPS (IMAP over SSL/TLS) using port 993.', 'text'),
    
    ('FTP_21', 'sensor', 'Insecure service detected: FTP on port 21', 'Services', 'Insecure Services',
     'FTP (or File Transfer Protocol) is a protocol used to transmit files over a network or the Internet.',
     'FTP uses unencrypted authentication, and transmits usernames, passwords and data over the network in cleartext.',
     'Credentials and sensitive data can be read by an adversary with access to the network traffic, resulting in not only data theft but also longer-term persistent system access to enable future attacks.',
     'Replace FTP with a secure alternative such as FTPS (FTP Secure over SSL/TLS) using port 990 or SFTP (SSH File Transfer Protocol)', 'text'),
    
    ('SSLV2_TRAFFIC', 'sensor', 'Vulnerable SSL/TLS protocol version detected: SSL 2.0', 'Data In Transit', 'SSL/TLS',
     'SSL (or Secure Sockets Layer) is a protocol for establishing secure network communication.',
     'SSL 2.0 has known vulnerabilities related to initial session handshake, message authentication and integrity, encryption strength and session termination.',
     'Network communication is vulnerable to man-in-the-middle attacks, truncation attacks, and weak/compromized message integrity, enabling adversaries to read and/or modify communicated data.',
     'Disable the use of SSL 2.0 and replace with a secure alternative such as TLS 1.2 or TLS 1.3.', 'text'),
    
    ('SSLV3_TRAFFIC', 'sensor', 'Vulnerable SSL/TLS protocol version detected: SSL 3.0', 'Data In Transit', 'SSL/TLS',
     'SSL (or Secure Sockets Layer) is a protocol for establishing secure network communication.',
     'SSL 3.0 has known vulnerabilities including handling of block cipher mode padding.',
     'SSL 3.0 is vulnerable to multiple known exploits including BEAST (CVE-2011-3389) and POODLE (CVE-2014-3566) enabling adversaries with access to the network traffic to read cleartext data.',
     'Disable use of SSL 3.0 and replace with a secure alternative such as TLS 1.2 or TLS 1.3', 'text'),
    
    ('TLS1_0_TRAFFIC', 'sensor', 'Vulnerable SSL/TLS protocol version detected: TLS 1.0', 'Data In Transit', 'SSL/TLS',
     'TLS (Transport Layer Security) is an updated version of the SSL protocol for establishing secure network communication.',
     'TLS 1.0 has known vulnerabilities including handling of block cipher mode padding and the initialization vector (IV), as well as dependence on the vulnerable MD5 and SHA-1 hash algorithms.',
     'TLS 1.0 can be vulnerable to multiple known exploits including BEAST (CVE-2011-3389) and POODLE (CVE-2014-3566) enabling adversaries with access to the network traffic to read cleartext data.',
     'Disable use of TLS 1.0 and replace with a secure alternative such as TLS 1.2 or TLS 1.3', 'text'),
    
    ('TLS1_1_TRAFFIC', 'sensor', 'Vulnerable SSL/TLS protocol version detected: TLS 1.1', 'Data In Transit', 'SSL/TLS',
     'TLS (Transport Layer Security) is an updated version of the SSL protocol for establishing secure network communication.',
     'TLS 1.1 has known vulnerabilities including dependence on the vulnerable MD5 and SHA-1 hash algorithms and lack of support for modern cipher suites, such as Authenticated Encryption with Associated Data (AEAD).',
     'TLS 1.1 is vulnerable to downgrade attacks and can be vulnerable to exploits such as POODLE (CVE-2014-3566), enabling adversaries with access to the network traffic to read cleartext data.',
     'Disable use of TLS 1.1 and replace with a secure alternative such as TLS 1.2 or TLS 1.3', 'text'),
    
    ('SELF_SIGNED_CERTS', 'sensor', 'Self-signed SSL/TLS certificate in use', 'Data In Transit', 'Certificates',
     'Digital certificates are used to secure SSL/TLS network communications, ensuring authenticity of the holder and integrity of the message. Certificates must be cryptographically signed by a publicly trusted certificate authority (CA) in order to verify authenticity.',
     'Self-signed certificates have no public chain of trust established, fail to ensure authenticity of the certificate holder, cannot be revoked in the event of compromise, and never expire.',
     'Adversaries may spoof the identify of the original certificate holder, leading to exposure and/or modification of sensitive data.',
     'Replace with a valid certificate signed by a publically trusted certificate authority (CA)', 'text'),
    
    ('EXPIRED_CERTS', 'sensor', 'Expired SSL/TLS certificate in use', 'Data In Transit', 'Certificates',
     'Digital certificates are used to secure SSL/TLS network communications, ensuring authenticity of the holder and integrity of the message. Certificates are generated with a pre-set expiration date in order to ensure use of current security best-practice and establish a current identity.',
     'Expired certificates should be considered untrusted with potentially insecure cryptography.',
     'Use of expired certificates can lead to system outages as well as man-in-the-middle attacks which result in exposure and/or modification of sensitive date.',
     'Renew or replace with a valid certificate that contains an appropriate future expiry date.', 'text'),
    
    ('WEAK_CERTS', 'sensor', 'Weak SSL/TLS certificate in use', 'Data In Transit', 'Certificates',
     'Digital certificates are used to secure SSL/TLS network communications, ensuring authenticity of the holder and integrity of the message. A cryptographic signature is required to securely generate and verify the certificate.',
     'Weak signature algorithms are vulnerable to collision attacks.',
     'Digital certificates can be forged, enavbling adversaries to spoof the identify of the original certificate holder, leading to exposure and/or modification of sensitive data.',
     'Replace with a digital certificate using a secure signature algorithm, such as the Elliptic Curve Digital Signature Algorithm (ECDSA) with SHA-384', 'text'),
    
    ('SMBV1', 'sensor', 'Insecure service detected: SMBv1', 'Services', 'Insecure Services',
     'SMB (Server Message Block) is a protocol used to share files, printers and other resources over a network.',
     'SMBv1 is an obsolete version of the SMB protocol that does not support encryption and transmits data over the network in cleartext. The Microsoft SMB v1 implementation is vulnerable to multiple remote code execution (RCE) attacks.',
     'An adversary with access to the network traffic can read sensitive data or inject malicious commands via man-in-the-middle attack. SMBv1 is vulnerable to multiple infamous exploits including EternalBlue (CVE-2017-0144), utilized by WannaCry ransomware and Petya.',
     'Disable the use of SMBv1 and replace with the latest SMB version (SMBv3 or later), restricting access only to trusted clients and networks. Remove or replace legacy systems and devices that require the SMBv1 protocol.', 'text'),
    
    ('UUCP_540', 'sensor', 'UUCP on Port 540', 'Services', 'Insecure Services',
     'UUCP (Unix-to-Unix Copy Protocol) refers to a set of Unix programs and protocols used for transferring files and email between systems, in addition to remote execution of commands.',
     'By default, UUCP transmits data unencrypted in cleartext.',
     'Sensitive data can be read by an adversary with access to the network traffic, resulting in data theft.',
     'Ensure that UUCP is configured to run over a secure tunnel to encrypt data in transit.', 'text'),
    
    ('RSYNC_873', 'sensor', 'rsync on Port 873', 'Services', 'Insecure Services',
     'RSYNC (Remote Sync) is a commonly-used tool on Linux and Unix systems to efficiently synchronize files over the network.',
     'When RSYNC is implemented via daemon running on port 873 (RSYNCD), data is transmitted over the network in cleartext.',
     'Sensitive data can be read by an adversary with access to the network traffic, resulting in data theft.',
     'Ensure that all RSYNCD implementations are configured to run over a secure SSH tunnel or VPN.', 'text'),
    
    ('UNENCRYPTED_TRAFFIC_X11', 'sensor', 'Unencrypted Admin traffic on X11 Ports', 'Services', 'Unencrypted Services',
     'X11 (X Window Protocol) is a protocol that enables remote graphical access to applications.',
     'X11 transmits data without encryption.',
     'Sensitive data can be read by an adversary with access to the network traffic.',
     'Remove X11 servers not in use and restrict access using appropriate use of the xhost command. Where required, run the X11 protocol over a secure SSH tunnel.', 'text')
ON CONFLICT (vuln_code, source_type) DO NOTHING;

-- ============================================================================
-- Comments for Documentation
-- ============================================================================

COMMENT ON TABLE risk_impact_metadata IS 'Combined risk, impact, propagation, and vulnerability level metadata with numeric prioritization and scoring';
COMMENT ON TABLE breach_method_metadata IS 'Breach method metadata with risk, exploitability, and impact scores for pipeline enrichment';
COMMENT ON TABLE security_strength_metadata IS 'Combined security strength metadata (certificates, ciphers, encryption, credentials) with numeric scoring';
COMMENT ON TABLE asset_classification_metadata IS 'Combined asset classification metadata with risk weights and criticality scores';
COMMENT ON TABLE vulnerability_metadata IS 'Combined vulnerability type, subtype, state, and tag metadata with risk scoring';
COMMENT ON TABLE software_metadata IS 'Combined software metadata with risk scores and maintenance priorities';
COMMENT ON TABLE roles_metadata IS 'Roles metadata with criticality scores and risk weights';
COMMENT ON TABLE cloud_connector_vuln_metadata IS 'Cloud connector vulnerability metadata with risk scores and compliance impact flags';
COMMENT ON TABLE vuln_info_metadata IS 'Combined vulnerability information from cloud and sensor sources including background, cause, effect, and remediation steps (HTML for cloud, plain text for sensor)';

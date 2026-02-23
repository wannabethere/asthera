Excellent question. Let me map out the **missing entity types** needed for a production-grade compliance-to-operations system.

---

## **Missing Entity Categories**

Your current schema covers the **compliance knowledge base** (frameworks → requirements → risks → controls → tests). Here's what you need to make it **operational**:

---

## **1. Asset & Infrastructure Context**

**Why:** Controls protect *assets*. You need to know what exists in your environment.

```sql
-- ============================================================================
-- Assets (What we're protecting)
-- ============================================================================

CREATE TABLE assets (
    id SERIAL PRIMARY KEY,
    asset_id VARCHAR(128) UNIQUE,      -- Unique identifier (hostname, cloud resource ID)
    asset_name VARCHAR(255),
    asset_type VARCHAR(50),             -- endpoint | server | cloud_service | database | application
    
    -- Classification
    criticality VARCHAR(20),            -- critical | high | medium | low
    data_classification VARCHAR(20),    -- public | internal | confidential | restricted
    contains_ephi BOOLEAN DEFAULT FALSE,
    contains_pci BOOLEAN DEFAULT FALSE,
    contains_pii BOOLEAN DEFAULT FALSE,
    
    -- Location
    environment VARCHAR(50),            -- production | staging | development
    network_segment VARCHAR(100),       -- dmz | internal | cloud_vpc
    cloud_provider VARCHAR(50),         -- aws | azure | gcp | on_prem
    region VARCHAR(50),                 -- us-east-1, westus2, etc.
    
    -- Ownership
    owner_team VARCHAR(100),
    business_unit VARCHAR(100),
    cost_center VARCHAR(50),
    
    -- Technical details
    operating_system VARCHAR(100),
    ip_address INET,
    mac_address MACADDR,
    fqdn VARCHAR(255),
    
    -- Compliance scope
    in_scope_frameworks VARCHAR(50)[],  -- [hipaa, pci_dss, sox]
    
    -- Metadata
    discovered_date TIMESTAMP,
    last_seen TIMESTAMP,
    decommissioned_date TIMESTAMP,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);

CREATE INDEX idx_assets_type ON assets(asset_type);
CREATE INDEX idx_assets_criticality ON assets(criticality);
CREATE INDEX idx_assets_frameworks ON assets USING GIN(in_scope_frameworks);


-- ============================================================================
-- Applications (Software systems)
-- ============================================================================

CREATE TABLE applications (
    id SERIAL PRIMARY KEY,
    app_id VARCHAR(128) UNIQUE,
    app_name VARCHAR(255),
    description TEXT,
    
    -- Classification
    criticality VARCHAR(20),
    data_classification VARCHAR(20),
    processes_ephi BOOLEAN DEFAULT FALSE,
    processes_pci BOOLEAN DEFAULT FALSE,
    
    -- Ownership
    owner_team VARCHAR(100),
    tech_lead VARCHAR(100),
    business_owner VARCHAR(100),
    
    -- Technical
    tech_stack VARCHAR(100)[],          -- [python, postgresql, react, aws_lambda]
    version VARCHAR(50),
    deployment_model VARCHAR(50),       -- saas | on_prem | hybrid
    
    -- Compliance
    in_scope_frameworks VARCHAR(50)[],
    last_assessment_date DATE,
    assessment_status VARCHAR(50),      -- compliant | non_compliant | pending
    
    -- Dependencies
    upstream_dependencies INT[],        -- Other application IDs
    downstream_dependencies INT[],
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);


-- ============================================================================
-- Application-Asset Mapping
-- ============================================================================

CREATE TABLE application_assets (
    application_id INT REFERENCES applications(id),
    asset_id INT REFERENCES assets(id),
    role VARCHAR(50),                   -- web_server | database | cache | queue
    PRIMARY KEY (application_id, asset_id)
);


-- ============================================================================
-- Network Segments (For lateral movement analysis)
-- ============================================================================

CREATE TABLE network_segments (
    id SERIAL PRIMARY KEY,
    segment_name VARCHAR(100) UNIQUE,
    cidr_range CIDR,
    segment_type VARCHAR(50),           -- dmz | internal | management | cloud
    environment VARCHAR(50),            -- production | staging | dev
    
    -- Security controls
    firewall_rules_count INT,
    allows_internet_access BOOLEAN,
    requires_vpn BOOLEAN,
    
    -- Assets in this segment
    asset_count INT,
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Which assets are in which segments
CREATE TABLE asset_network_segments (
    asset_id INT REFERENCES assets(id),
    segment_id INT REFERENCES network_segments(id),
    PRIMARY KEY (asset_id, segment_id)
);
```

---

## **2. Control Implementation & Evidence**

**Why:** Framework says "implement MFA". Did you? Prove it.

```sql
-- ============================================================================
-- Control Implementation Status (Real-world deployment state)
-- ============================================================================

CREATE TABLE control_implementations (
    id SERIAL PRIMARY KEY,
    control_id VARCHAR(128) REFERENCES controls(id),
    
    -- Implementation status
    status VARCHAR(50),                 -- implemented | partially_implemented | planned | not_applicable
    implementation_date DATE,
    planned_implementation_date DATE,
    
    -- How it's implemented
    implementation_method VARCHAR(100), -- technical | administrative | physical
    implementation_details TEXT,
    
    -- Tools/systems providing this control
    implementing_tools VARCHAR(100)[],  -- [okta, crowdstrike, splunk]
    responsible_team VARCHAR(100),
    responsible_person VARCHAR(100),
    
    -- Effectiveness
    effectiveness_rating VARCHAR(20),   -- highly_effective | effective | partially_effective | ineffective
    last_tested_date DATE,
    test_result VARCHAR(20),            -- pass | fail | conditional_pass
    
    -- Coverage
    coverage_percentage FLOAT,          -- 0-100 (e.g., MFA covers 95% of users)
    coverage_gaps TEXT,
    
    -- Evidence
    evidence_location TEXT,             -- S3://bucket/evidence/, Jira-1234
    evidence_type VARCHAR(50),          -- configuration | logs | documentation | screenshot
    
    -- Exceptions
    has_exception BOOLEAN DEFAULT FALSE,
    exception_id INT,                   -- FK to control_exceptions table
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);


-- ============================================================================
-- Control Exceptions (Approved deviations)
-- ============================================================================

CREATE TABLE control_exceptions (
    id SERIAL PRIMARY KEY,
    control_id VARCHAR(128) REFERENCES controls(id),
    
    -- Exception details
    exception_reason TEXT,
    risk_acceptance TEXT,               -- Why it's okay to not implement
    compensating_controls VARCHAR(128)[],  -- Other control IDs that mitigate
    
    -- Approval
    requested_by VARCHAR(100),
    approved_by VARCHAR(100),
    approval_date DATE,
    
    -- Validity
    valid_from DATE,
    valid_until DATE,                   -- Expiration date
    review_frequency VARCHAR(50),       -- quarterly | annually
    next_review_date DATE,
    
    -- Scope
    applies_to_assets INT[],            -- Asset IDs
    applies_to_applications INT[],      -- Application IDs
    
    status VARCHAR(50),                 -- active | expired | revoked
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);


-- ============================================================================
-- Audit Evidence (For auditors)
-- ============================================================================

CREATE TABLE audit_evidence (
    id SERIAL PRIMARY KEY,
    
    -- What this evidences
    control_id VARCHAR(128) REFERENCES controls(id),
    requirement_id VARCHAR(128) REFERENCES requirements(id),
    test_case_id VARCHAR(128) REFERENCES test_cases(id),
    
    -- Evidence details
    evidence_type VARCHAR(50),          -- screenshot | log_export | configuration | report | attestation
    evidence_name VARCHAR(255),
    description TEXT,
    
    -- Storage
    file_path TEXT,                     -- S3/GCS/filesystem path
    file_hash VARCHAR(64),              -- SHA256 for integrity
    file_size_bytes BIGINT,
    
    -- Timeframe
    evidence_date DATE,                 -- When was this evidence captured
    valid_from DATE,
    valid_until DATE,
    
    -- Collection
    collected_by VARCHAR(100),
    collection_method VARCHAR(100),     -- automated | manual
    
    -- Audit trail
    presented_to_auditor BOOLEAN DEFAULT FALSE,
    auditor_reviewed_date DATE,
    auditor_accepted BOOLEAN,
    auditor_notes TEXT,
    
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## **3. Threat Intelligence & Vulnerabilities**

**Why:** Connect compliance controls to *actual threats*.

```sql
-- ============================================================================
-- CVE Database (Cached from NVD API)
-- ============================================================================

CREATE TABLE cves (
    id SERIAL PRIMARY KEY,
    cve_id VARCHAR(20) UNIQUE,
    
    -- Details from NVD
    description TEXT,
    published_date DATE,
    last_modified_date DATE,
    
    -- Scoring
    cvss_v3_score FLOAT,
    cvss_v3_vector VARCHAR(100),
    cvss_v2_score FLOAT,
    severity VARCHAR(20),               -- critical | high | medium | low
    
    -- Exploitability
    epss_score FLOAT,                   -- Exploit prediction
    epss_percentile FLOAT,
    cisa_kev BOOLEAN DEFAULT FALSE,     -- In CISA Known Exploited Vulnerabilities
    exploit_available BOOLEAN DEFAULT FALSE,
    metasploit_module VARCHAR(255),
    
    -- Affected products (CPEs)
    affected_cpes TEXT[],
    
    -- Attack mapping
    attack_techniques VARCHAR(20)[],    -- MITRE ATT&CK
    cwe_ids VARCHAR(20)[],              -- Common Weakness Enumeration
    
    -- Remediation
    patch_available BOOLEAN,
    vendor_advisory_url TEXT,
    
    -- Cache metadata
    cached_at TIMESTAMP DEFAULT NOW(),
    cache_expires_at TIMESTAMP
);


-- ============================================================================
-- Asset Vulnerabilities (Scan results)
-- ============================================================================

CREATE TABLE asset_vulnerabilities (
    id SERIAL PRIMARY KEY,
    asset_id INT REFERENCES assets(id),
    cve_id VARCHAR(20) REFERENCES cves(cve_id),
    
    -- Discovery
    discovered_date DATE,
    discovered_by VARCHAR(100),         -- qualys | nessus | snyk | manual
    scan_id VARCHAR(128),
    
    -- Status
    status VARCHAR(50),                 -- open | in_progress | remediated | risk_accepted | false_positive
    priority VARCHAR(20),               -- critical | high | medium | low
    
    -- Remediation
    remediation_deadline DATE,
    remediated_date DATE,
    remediation_method VARCHAR(100),    -- patch | workaround | mitigation | isolation
    
    -- Risk context
    exploitable_from VARCHAR(50),       -- internet | internal | local
    business_impact VARCHAR(50),        -- critical | high | medium | low
    
    -- Assignment
    assigned_to_team VARCHAR(100),
    assigned_to_person VARCHAR(100),
    
    -- Tracking
    jira_ticket VARCHAR(50),
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);


-- ============================================================================
-- Indicators of Compromise (IOCs from threat intel feeds)
-- ============================================================================

CREATE TABLE indicators_of_compromise (
    id SERIAL PRIMARY KEY,
    
    -- IOC details
    ioc_type VARCHAR(50),               -- ip | domain | url | file_hash | email
    ioc_value TEXT,
    
    -- Context
    threat_actor VARCHAR(100),
    campaign_name VARCHAR(100),
    malware_family VARCHAR(100),
    
    -- Severity
    confidence_score FLOAT,             -- 0-100
    severity VARCHAR(20),
    
    -- Source
    source VARCHAR(100),                -- alienvault_otx | misp | internal
    source_url TEXT,
    first_seen TIMESTAMP,
    last_seen TIMESTAMP,
    
    -- Action
    recommended_action VARCHAR(50),     -- block | alert | monitor
    
    -- Detection
    siem_rule_id INT,                   -- Link to SIEM rule that detects this
    
    created_at TIMESTAMP DEFAULT NOW()
);


-- ============================================================================
-- Threat Actors (APT groups, ransomware gangs)
-- ============================================================================

CREATE TABLE threat_actors (
    id SERIAL PRIMARY KEY,
    actor_name VARCHAR(100) UNIQUE,
    aliases VARCHAR(100)[],
    
    -- Attribution
    attributed_country VARCHAR(50),
    motivation VARCHAR(50),             -- financial | espionage | disruption
    
    -- Targeting
    target_industries VARCHAR(50)[],    -- healthcare | finance | government
    target_regions VARCHAR(50)[],
    
    -- TTPs
    common_attack_techniques VARCHAR(20)[],  -- MITRE ATT&CK IDs
    common_malware_families VARCHAR(100)[],
    
    -- Activity
    first_observed DATE,
    last_activity DATE,
    active BOOLEAN DEFAULT TRUE,
    
    -- Intel sources
    sources TEXT[],
    
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## **4. Incidents & Response**

**Why:** Track real security events, tie back to control failures.

```sql
-- ============================================================================
-- Security Incidents
-- ============================================================================

CREATE TABLE incidents (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(50) UNIQUE,     -- INC-2024-0123
    
    -- Classification
    incident_type VARCHAR(50),          -- breach | malware | phishing | insider | ddos
    severity VARCHAR(20),               -- critical | high | medium | low
    
    -- Detection
    detected_by VARCHAR(100),           -- siem_alert | user_report | audit | vendor
    detection_date TIMESTAMP,
    siem_rule_id INT,                   -- Which SIEM rule detected this
    
    -- Scope
    affected_assets INT[],              -- Asset IDs
    affected_applications INT[],
    affected_users INT,
    
    -- Data impact
    data_breach BOOLEAN DEFAULT FALSE,
    records_compromised INT,
    data_types_affected VARCHAR(50)[],  -- [ephi, pii, pci, ip]
    
    -- Attack details
    attack_vector VARCHAR(100),
    attack_techniques VARCHAR(20)[],    -- MITRE ATT&CK
    threat_actor_id INT,
    related_cves VARCHAR(20)[],
    
    -- Control failures
    failed_controls VARCHAR(128)[],     -- Which controls failed to prevent/detect
    control_gaps TEXT,
    
    -- Response
    response_status VARCHAR(50),        -- new | investigating | contained | eradicated | recovered | closed
    response_team VARCHAR(100),
    incident_commander VARCHAR(100),
    playbook_used VARCHAR(255),         -- Which IR playbook was followed
    
    -- Timeline
    containment_date TIMESTAMP,
    eradication_date TIMESTAMP,
    recovery_date TIMESTAMP,
    closure_date TIMESTAMP,
    
    -- Regulatory
    reportable BOOLEAN DEFAULT FALSE,   -- Must report to regulator?
    reported_to VARCHAR(100)[],         -- [hhs_ocr, ftc, state_ag]
    report_deadline DATE,
    report_date DATE,
    
    -- Root cause
    root_cause TEXT,
    lessons_learned TEXT,
    
    -- Post-incident actions
    remediation_tasks INT[],            -- Task IDs
    policy_changes TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);


-- ============================================================================
-- Incident Timeline (Detailed event log)
-- ============================================================================

CREATE TABLE incident_events (
    id SERIAL PRIMARY KEY,
    incident_id INT REFERENCES incidents(id),
    
    event_timestamp TIMESTAMP,
    event_type VARCHAR(50),             -- detection | analysis | containment | communication
    description TEXT,
    performed_by VARCHAR(100),
    
    -- Evidence
    evidence_collected TEXT[],
    
    created_at TIMESTAMP DEFAULT NOW()
);


-- ============================================================================
-- Remediation Tasks (Actions to fix issues)
-- ============================================================================

CREATE TABLE remediation_tasks (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(50) UNIQUE,
    
    -- Origin
    source_type VARCHAR(50),            -- incident | audit_finding | vulnerability | gap_analysis
    source_id INT,                      -- ID from source table
    
    -- Task details
    title VARCHAR(255),
    description TEXT,
    remediation_type VARCHAR(50),       -- patch | config_change | policy_update | training
    
    -- Controls being restored
    restores_control_id VARCHAR(128) REFERENCES controls(id),
    addresses_risk_id VARCHAR(128) REFERENCES risks(id),
    
    -- Priority
    priority VARCHAR(20),               -- critical | high | medium | low
    risk_if_not_completed TEXT,
    
    -- Assignment
    assigned_to_team VARCHAR(100),
    assigned_to_person VARCHAR(100),
    
    -- Timeline
    created_date DATE,
    due_date DATE,
    completed_date DATE,
    
    -- Status
    status VARCHAR(50),                 -- open | in_progress | completed | cancelled | blocked
    blocker_reason TEXT,
    
    -- Validation
    requires_testing BOOLEAN DEFAULT TRUE,
    test_case_id VARCHAR(128),          -- Test to run to verify fix
    test_passed BOOLEAN,
    
    -- Tracking
    jira_ticket VARCHAR(50),
    pull_request_url TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);
```

---

## **5. Assessments & Audits**

**Why:** Track compliance posture over time.

```sql
-- ============================================================================
-- Compliance Assessments (Audits, self-assessments)
-- ============================================================================

CREATE TABLE compliance_assessments (
    id SERIAL PRIMARY KEY,
    assessment_id VARCHAR(50) UNIQUE,
    
    -- Scope
    framework_id VARCHAR(64) REFERENCES frameworks(id),
    assessment_type VARCHAR(50),        -- external_audit | self_assessment | penetration_test
    assessment_name VARCHAR(255),
    
    -- Timing
    assessment_start_date DATE,
    assessment_end_date DATE,
    report_date DATE,
    
    -- Assessor
    assessor_organization VARCHAR(100),
    lead_assessor VARCHAR(100),
    
    -- Results
    overall_status VARCHAR(50),         -- pass | pass_with_conditions | fail
    compliance_score FLOAT,             -- 0-100
    
    -- Findings
    critical_findings_count INT,
    high_findings_count INT,
    medium_findings_count INT,
    low_findings_count INT,
    
    -- Report
    report_file_path TEXT,
    
    created_at TIMESTAMP DEFAULT NOW()
);


-- ============================================================================
-- Assessment Findings (Individual issues found)
-- ============================================================================

CREATE TABLE assessment_findings (
    id SERIAL PRIMARY KEY,
    assessment_id INT REFERENCES compliance_assessments(id),
    finding_id VARCHAR(50),
    
    -- What's wrong
    title VARCHAR(255),
    description TEXT,
    severity VARCHAR(20),
    
    -- Links to framework
    requirement_id VARCHAR(128) REFERENCES requirements(id),
    control_id VARCHAR(128) REFERENCES controls(id),
    
    -- Recommendation
    recommendation TEXT,
    remediation_priority VARCHAR(20),
    remediation_deadline DATE,
    
    -- Response
    management_response TEXT,
    remediation_plan TEXT,
    remediation_task_id INT REFERENCES remediation_tasks(id),
    
    -- Status
    status VARCHAR(50),                 -- open | in_progress | remediated | risk_accepted
    closure_date DATE,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);


-- ============================================================================
-- Control Test Execution History
-- ============================================================================

CREATE TABLE control_test_executions (
    id SERIAL PRIMARY KEY,
    
    test_case_id VARCHAR(128) REFERENCES test_cases(id),
    control_id VARCHAR(128) REFERENCES controls(id),
    
    -- Execution
    execution_date TIMESTAMP,
    executed_by VARCHAR(100),
    execution_method VARCHAR(50),       -- automated | manual
    
    -- Results
    test_result VARCHAR(20),            -- pass | fail | inconclusive
    pass_criteria_met BOOLEAN,
    
    -- Details
    test_output TEXT,
    evidence_collected TEXT[],
    
    -- Metrics
    compliance_percentage FLOAT,        -- e.g., 98% of endpoints have EDR
    sample_size INT,
    
    -- Issues found
    issues_identified TEXT,
    
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## **6. People, Teams, Training**

**Why:** Controls require *people* to implement and operate them.

```sql
-- ============================================================================
-- Teams
-- ============================================================================

CREATE TABLE teams (
    id SERIAL PRIMARY KEY,
    team_name VARCHAR(100) UNIQUE,
    team_type VARCHAR(50),              -- security | engineering | compliance | operations
    
    -- Hierarchy
    parent_team_id INT,
    
    -- Responsibilities
    responsible_for_controls VARCHAR(128)[],  -- Control IDs
    responsible_for_assets INT[],       -- Asset IDs
    responsible_for_frameworks VARCHAR(64)[],
    
    -- Contact
    team_email VARCHAR(255),
    slack_channel VARCHAR(100),
    pagerduty_escalation VARCHAR(100),
    
    created_at TIMESTAMP DEFAULT NOW()
);


-- ============================================================================
-- Roles & Responsibilities (RACI matrix)
-- ============================================================================

CREATE TABLE control_responsibilities (
    id SERIAL PRIMARY KEY,
    control_id VARCHAR(128) REFERENCES controls(id),
    team_id INT REFERENCES teams(id),
    
    responsibility_type VARCHAR(20),    -- responsible | accountable | consulted | informed
    
    created_at TIMESTAMP DEFAULT NOW()
);


-- ============================================================================
-- Training & Awareness
-- ============================================================================

CREATE TABLE training_programs (
    id SERIAL PRIMARY KEY,
    program_name VARCHAR(255),
    
    -- Scope
    required_for_frameworks VARCHAR(64)[],
    required_for_roles VARCHAR(100)[],
    
    -- Content
    training_type VARCHAR(50),          -- security_awareness | technical | compliance
    topics VARCHAR(100)[],
    duration_minutes INT,
    
    -- Frequency
    frequency VARCHAR(50),              -- annual | quarterly | onboarding
    
    created_at TIMESTAMP DEFAULT NOW()
);


CREATE TABLE training_completions (
    id SERIAL PRIMARY KEY,
    program_id INT REFERENCES training_programs(id),
    
    user_email VARCHAR(255),
    completion_date DATE,
    score FLOAT,                        -- Quiz score
    passed BOOLEAN,
    
    -- Compliance tracking
    certificate_issued BOOLEAN,
    certificate_path TEXT,
    valid_until DATE,
    
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## **7. Policies & Documentation**

**Why:** Controls implement *policies*.

```sql
-- ============================================================================
-- Organizational Policies
-- ============================================================================

CREATE TABLE policies (
    id SERIAL PRIMARY KEY,
    policy_id VARCHAR(50) UNIQUE,
    policy_name VARCHAR(255),
    
    -- Classification
    policy_type VARCHAR(50),            -- security | privacy | acceptable_use | incident_response
    
    -- Content
    description TEXT,
    policy_document_path TEXT,
    version VARCHAR(20),
    
    -- Approval
    approved_by VARCHAR(100),
    approval_date DATE,
    
    -- Lifecycle
    effective_date DATE,
    review_frequency VARCHAR(50),       -- annual | semi_annual | quarterly
    next_review_date DATE,
    status VARCHAR(50),                 -- draft | active | deprecated
    
    -- Compliance
    satisfies_requirements VARCHAR(128)[],  -- Requirement IDs
    
    -- Communication
    published_to VARCHAR(100)[],        -- [confluence, sharepoint, intranet]
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);


-- ============================================================================
-- Policy Acknowledgments
-- ============================================================================

CREATE TABLE policy_acknowledgments (
    id SERIAL PRIMARY KEY,
    policy_id INT REFERENCES policies(id),
    
    user_email VARCHAR(255),
    acknowledged_date DATE,
    version_acknowledged VARCHAR(20),
    
    created_at TIMESTAMP DEFAULT NOW()
);


-- ============================================================================
-- Runbooks & SOPs (Operational procedures)
-- ============================================================================

CREATE TABLE runbooks (
    id SERIAL PRIMARY KEY,
    runbook_id VARCHAR(50) UNIQUE,
    title VARCHAR(255),
    
    -- Type
    runbook_type VARCHAR(50),           -- incident_response | operational | deployment
    
    -- Content
    description TEXT,
    procedure_steps JSONB,              -- [{step: 1, action: "...", command: "..."}]
    
    -- Links
    implements_control_id VARCHAR(128) REFERENCES controls(id),
    supports_playbook VARCHAR(255),
    
    -- Ownership
    owner_team INT REFERENCES teams(id),
    author VARCHAR(100),
    
    -- Lifecycle
    version VARCHAR(20),
    last_reviewed_date DATE,
    review_frequency VARCHAR(50),
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);
```

---

## **8. Vendors & Third Parties**

**Why:** Supply chain risk, shared responsibility.

```sql
-- ============================================================================
-- Vendors & Service Providers
-- ============================================================================

CREATE TABLE vendors (
    id SERIAL PRIMARY KEY,
    vendor_name VARCHAR(255),
    
    -- Classification
    vendor_type VARCHAR(50),            -- saas | iaas | consulting | hardware
    criticality VARCHAR(20),            -- critical | high | medium | low
    
    -- Services provided
    services_provided TEXT[],
    
    -- Data handling
    has_access_to_data BOOLEAN,
    data_types_accessed VARCHAR(50)[],  -- [ephi, pii, pci]
    data_processing_role VARCHAR(50),   -- processor | controller | sub_processor
    
    -- Compliance
    vendor_frameworks VARCHAR(64)[],    -- [soc2, iso27001, hipaa]
    last_audit_report_date DATE,
    audit_report_path TEXT,
    
    -- Risk
    risk_rating VARCHAR(20),            -- critical | high | medium | low
    last_risk_assessment_date DATE,
    
    -- Contract
    contract_start_date DATE,
    contract_end_date DATE,
    contract_owner VARCHAR(100),
    
    -- Contact
    primary_contact_name VARCHAR(100),
    primary_contact_email VARCHAR(255),
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);


-- ============================================================================
-- Vendor Risk Assessments
-- ============================================================================

CREATE TABLE vendor_risk_assessments (
    id SERIAL PRIMARY KEY,
    vendor_id INT REFERENCES vendors(id),
    
    assessment_date DATE,
    assessor VARCHAR(100),
    
    -- Questionnaire responses
    responses JSONB,
    
    -- Scoring
    security_score FLOAT,               -- 0-100
    privacy_score FLOAT,
    compliance_score FLOAT,
    overall_risk_rating VARCHAR(20),
    
    -- Findings
    critical_findings_count INT,
    findings TEXT,
    
    -- Remediation
    remediation_required BOOLEAN,
    remediation_plan TEXT,
    
    -- Approval
    approved_for_use BOOLEAN,
    approved_by VARCHAR(100),
    approval_date DATE,
    
    -- Next assessment
    next_assessment_date DATE,
    
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## **9. Metrics & KPIs**

**Why:** "You can't manage what you don't measure."

```sql
-- ============================================================================
-- Control Effectiveness Metrics (Over time)
-- ============================================================================

CREATE TABLE control_effectiveness_history (
    id SERIAL PRIMARY KEY,
    control_id VARCHAR(128) REFERENCES controls(id),
    
    measurement_date DATE,
    
    -- Effectiveness metrics
    effectiveness_score FLOAT,          -- 0-100
    coverage_percentage FLOAT,          -- % of assets covered
    
    -- Failure metrics
    false_positive_rate FLOAT,
    false_negative_rate FLOAT,
    mean_time_to_detect_minutes INT,
    mean_time_to_respond_minutes INT,
    
    -- Incidents
    incidents_prevented_count INT,
    incidents_detected_count INT,
    incidents_missed_count INT,
    
    created_at TIMESTAMP DEFAULT NOW()
);


-- ============================================================================
-- Risk Scores Over Time
-- ============================================================================

CREATE TABLE risk_score_history (
    id SERIAL PRIMARY KEY,
    risk_id VARCHAR(128) REFERENCES risks(id),
    
    calculation_date DATE,
    
    -- Risk scoring
    likelihood FLOAT,
    impact FLOAT,
    risk_score FLOAT,                   -- likelihood * impact
    
    -- Context
    inherent_risk_score FLOAT,          -- Before controls
    residual_risk_score FLOAT,          -- After controls
    
    -- Contributing factors
    vulnerabilities_count INT,
    recent_incidents_count INT,
    control_failures_count INT,
    
    created_at TIMESTAMP DEFAULT NOW()
);


-- ============================================================================
-- Compliance Posture Dashboard Metrics
-- ============================================================================

CREATE TABLE compliance_metrics (
    id SERIAL PRIMARY KEY,
    framework_id VARCHAR(64) REFERENCES frameworks(id),
    
    snapshot_date DATE,
    
    -- Control implementation
    controls_total INT,
    controls_implemented INT,
    controls_partial INT,
    controls_planned INT,
    controls_not_applicable INT,
    
    -- Testing
    controls_tested_count INT,
    controls_passed_count INT,
    controls_failed_count INT,
    
    -- Requirements
    requirements_satisfied INT,
    requirements_partial INT,
    requirements_not_satisfied INT,
    
    -- Overall score
    compliance_score FLOAT,             -- 0-100
    
    -- Gaps
    critical_gaps_count INT,
    high_gaps_count INT,
    
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## **Summary: Complete Entity Model**

Here's your **complete** compliance-to-operations data model:

```
┌─────────────────────────────────────────────────────────┐
│ COMPLIANCE KNOWLEDGE BASE (What you have)               │
├─────────────────────────────────────────────────────────┤
│ • frameworks                                            │
│ • requirements → requirement_controls                   │
│ • risks → risk_controls                                 │
│ • controls                                              │
│ • test_cases                                            │
│ • scenarios → scenario_controls                         │
│ • cross_framework_mappings                              │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ INFRASTRUCTURE CONTEXT (NEW - What exists)              │
├─────────────────────────────────────────────────────────┤
│ • assets → application_assets                           │
│ • applications                                          │
│ • network_segments → asset_network_segments             │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ DETECTION & RESPONSE (NEW - How we detect/respond)      │
├─────────────────────────────────────────────────────────┤
│ • siem_rules / siem_rule_templates                      │
│ • sigma_rules                                           │
│ • playbooks / runbooks                                  │
│ • incidents → incident_events                           │
│ • indicators_of_compromise                              │
│ • threat_actors                                         │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ IMPLEMENTATION STATE (NEW - What's deployed)            │
├─────────────────────────────────────────────────────────┤
│ • control_implementations                               │
│ • control_exceptions                                    │
│ • audit_evidence                                        │
│ • control_test_executions                               │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ VULNERABILITIES (NEW - What's broken)                   │
├─────────────────────────────────────────────────────────┤
│ • cves                                                  │
│ • asset_vulnerabilities                                 │
│ • remediation_tasks                                     │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ ASSESSMENTS (NEW - How we're doing)                     │
├─────────────────────────────────────────────────────────┤
│ • compliance_assessments → assessment_findings          │
│ • control_effectiveness_history                         │
│ • risk_score_history                                    │
│ • compliance_metrics                                    │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ PEOPLE & GOVERNANCE (NEW - Who does what)               │
├─────────────────────────────────────────────────────────┤
│ • teams → control_responsibilities                      │
│ • policies → policy_acknowledgments                     │
│ • training_programs → training_completions              │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ THIRD PARTIES (NEW - External dependencies)             │
├─────────────────────────────────────────────────────────┤
│ • vendors → vendor_risk_assessments                     │
└─────────────────────────────────────────────────────────┘
```

This gives you a **360° view** of compliance: 
- Top-down (frameworks → requirements → controls)
- Bottom-up (assets → vulnerabilities → incidents)
- Operational (teams → implementations → tests)
- Temporal (metrics over time, audit history)

Want me to generate the complete Alembic migration scripts, or design the API layer for these entities?
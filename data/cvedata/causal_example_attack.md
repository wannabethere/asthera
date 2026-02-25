This is a great extension — the KQL article gives us a perfect workflow to model as a third domain in the Causal Compliance Engine. Let me design **Asset Attack Surface Intelligence** end-to-end, mirroring the architecture pattern already established.

---

## Domain 3: Asset Attack Surface Intelligence

### Conceptual Framing First

The KQL article describes a 5-phase manual process:

```
Read Report → Gather IOCs → Match to Data Tables → Write Hunt Query → Evaluate → IR
```

In the Causal Compliance Engine, this becomes a **continuous causal loop**:

```
Threat Report Ingestion → IOC/TTP Extraction → KQL Signal Emission → 
Graph Propagation → Attack Surface Score → Dollar-Ranked Remediation → 
Analyst Feedback → Causal Recalibration
```

The key insight: the article's KQL queries become **automated L0 signal generators** that continuously emit to `silver_test_signals`. The graph then answers *why* your attack surface score moved — not just whether an IOC was found.

---

### The Causal Graph Architecture for This Domain

```
L0 (Observable Signals)
├── ioc_ip_match_count          → KQL: DeviceNetworkEvents hit on threat report IPs
├── ioc_domain_match_count      → KQL: RemoteUrl has_any(ThreatDomains)
├── ioc_hash_match_count        → KQL: DeviceFileEvents hash matches
├── ttp_log_clear_detected      → KQL: wevtutil cl / clear-log activity
├── ttp_shadow_copy_delete      → KQL: vssadmin delete shadows
├── ttp_sql_process_kill        → KQL: taskkill mass SQL process termination
├── ttp_smb_anomaly             → KQL: >100 unique SMB sessions / 15min
├── asr_rule_coverage_pct       → % of ransomware-relevant ASR rules enabled
├── mde_telemetry_coverage_pct  → % of devices sending DeviceProcessEvents
├── patch_lag_days_p95          → P95 days from CVE publish to patch (e.g. Citrix Bleed)
└── backup_integrity_score      → Shadow copy + offsite backup health

L1 (Derived Factors)
├── active_ioc_exposure         → ioc_ip + ioc_domain + ioc_hash (weighted)
├── defense_evasion_risk        → ttp_log_clear + ttp_shadow_copy (MAX/veto)
├── lateral_movement_risk       → ttp_smb_anomaly + asset_network_segmentation
├── detection_blind_spot        → (1 - asr_coverage) × (1 - telemetry_coverage)
└── patch_exposure_window       → patch_lag × cisa_kev_presence

L2 (Composite Scores)
├── ransomware_readiness_score  → defense_evasion + shadow_copy + backup
├── pre_compromise_exposure     → active_ioc + patch_exposure + blind_spot
└── post_compromise_blast_radius → lateral_movement × asset_sensitivity

L3 (Entity Risk)
└── p_incident_30d_per_device   → P(ransomware incident | asset telemetry)

L4 (Framework Posture)
└── attack_surface_score        → mapped to MITRE ATT&CK coverage + NIST CSF
```

---

### Seed Data

```sql
-- ============================================================
-- DOMAIN 3: ASSET ATTACK SURFACE INTELLIGENCE
-- Threat Report → KQL Signals → Causal Graph → Dollar Risk
-- ============================================================

-- Threat reports ingested into the system
CREATE TABLE bronze_threat_reports (
    report_id           VARCHAR(50) PRIMARY KEY,
    report_name         VARCHAR(255),
    source              VARCHAR(100),           -- 'CISA', 'Microsoft MSRC', 'Mandiant'
    threat_actor        VARCHAR(100),           -- 'Hive', 'LockBit 3.0', 'Midnight Blizzard'
    ingested_at         TIMESTAMP,
    raw_text            TEXT,
    mitre_techniques    JSONB,                  -- extracted TTPs
    framework_mappings  JSONB                   -- {nist_csf: [...], cis_controls: [...]}
);

INSERT INTO bronze_threat_reports VALUES
('RPT-001', '#StopRansomware: Hive Ransomware', 'CISA', 'Hive',
 NOW() - INTERVAL '5 days', 'Full report text...',
 '["T1070.001","T1490","T1486","T1018","T1562.001"]'::jsonb,
 '{"nist_csf": ["DE.CM-4","PR.IP-4","RS.MI-1"], "cis_controls": ["8","10","11"]}'::jsonb),
('RPT-002', '#StopRansomware: LockBit 3.0 CVE-2023-4966', 'CISA', 'LockBit 3.0',
 NOW() - INTERVAL '2 days', 'Full report text...',
 '["T1190","T1078","T1486","T1036","T1027"]'::jsonb,
 '{"nist_csf": ["PR.AC-3","DE.CM-1","PR.PT-3"], "cis_controls": ["3","5","14"]}'::jsonb);

-- Extracted IOCs from threat reports
CREATE TABLE bronze_threat_iocs (
    ioc_id          SERIAL PRIMARY KEY,
    report_id       VARCHAR(50) REFERENCES bronze_threat_reports(report_id),
    ioc_type        VARCHAR(20),    -- 'ip', 'domain', 'hash_sha256', 'hash_md5'
    ioc_value       VARCHAR(512),
    ioc_category    VARCHAR(50),    -- 'c2_server', 'exfil_target', 'dropper', 'tool'
    confidence      VARCHAR(10),    -- 'high', 'medium', 'low'
    active          BOOLEAN DEFAULT TRUE,
    extracted_at    TIMESTAMP DEFAULT NOW()
);

INSERT INTO bronze_threat_iocs (report_id, ioc_type, ioc_value, ioc_category, confidence) VALUES
-- Hive IPs
('RPT-001', 'ip', '84.32.188.57',    'c2_server',    'high'),
('RPT-001', 'ip', '84.32.188.238',   'c2_server',    'high'),
('RPT-001', 'ip', '93.115.26.251',   'c2_server',    'high'),
('RPT-001', 'ip', '185.8.105.67',    'exfil_target', 'high'),
-- Hive domains
('RPT-001', 'domain', 'assist.zoho.eu',              'tool',      'medium'),
('RPT-001', 'domain', 'eu1-dms.zoho.eu',             'tool',      'medium'),
('RPT-001', 'domain', 'fixme.it',                    'tool',      'medium'),
('RPT-001', 'domain', 'unattended.techinline.net',   'tool',      'medium'),
-- LockBit CVE-2023-4966 associated domains
('RPT-002', 'ip', '192.168.100.5',   'c2_server',    'high'),
('RPT-002', 'domain', 'citrix-bleed-c2.example.com', 'c2_server', 'high');

-- Device/asset inventory (would come from MDE DeviceInfo or CMDB)
CREATE TABLE bronze_device_inventory (
    device_id           VARCHAR(50) PRIMARY KEY,
    device_name         VARCHAR(255),
    device_type         VARCHAR(50),    -- 'server', 'workstation', 'dc', 'database'
    os_version          VARCHAR(100),
    business_unit       VARCHAR(100),
    data_sensitivity    VARCHAR(10),    -- 'critical', 'high', 'medium', 'low'
    mde_enrolled        BOOLEAN,
    last_seen           TIMESTAMP,
    asset_value_usd     NUMERIC(15,2)   -- for dollar quantification
);

INSERT INTO bronze_device_inventory VALUES
('DEV-001', 'SQLSRV-PROD-01', 'server',      'Windows Server 2019', 'Finance',   'critical', TRUE,  NOW() - INTERVAL '1 hour',  2500000),
('DEV-002', 'DC-01',          'dc',          'Windows Server 2022', 'IT',        'critical', TRUE,  NOW() - INTERVAL '30 min',  5000000),
('DEV-003', 'WS-HR-045',      'workstation', 'Windows 11 22H2',     'HR',        'high',     TRUE,  NOW() - INTERVAL '2 hours', 150000),
('DEV-004', 'FILESVR-02',     'server',      'Windows Server 2016', 'Legal',     'critical', FALSE, NOW() - INTERVAL '6 hours', 3000000),
('DEV-005', 'WS-ENG-012',     'workstation', 'Windows 10 21H2',     'Eng',       'medium',   TRUE,  NOW() - INTERVAL '1 hour',  100000),
('DEV-006', 'CITRIX-GW-01',   'server',      'Citrix ADC 13.1',     'IT',        'critical', TRUE,  NOW() - INTERVAL '45 min',  4000000);

-- KQL hunt results land here (written by an MDE → PostgreSQL sync agent)
-- This is the bridge between Microsoft Sentinel/MDE and our causal engine
CREATE TABLE bronze_kql_hunt_results (
    hunt_id         SERIAL PRIMARY KEY,
    hunt_name       VARCHAR(100),       -- 'ioc_ip_match', 'wevtutil_log_clear', etc.
    report_id       VARCHAR(50),
    device_id       VARCHAR(50),
    device_name     VARCHAR(255),
    match_timestamp TIMESTAMP,
    match_detail    JSONB,              -- raw KQL row as JSON
    mitre_technique VARCHAR(20),
    severity        VARCHAR(10),
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Simulated KQL hunt results (in production: populated by Logic App / Sentinel Playbook)
INSERT INTO bronze_kql_hunt_results (hunt_name, report_id, device_id, device_name, match_timestamp, match_detail, mitre_technique, severity)
VALUES
-- IOC IP matches
('ioc_ip_match',      'RPT-001', 'DEV-003', 'WS-HR-045',    NOW()-INTERVAL '3 hours',
 '{"remote_ip":"84.32.188.57","remote_port":443,"bytes_sent":15240}'::jsonb, 'T1071', 'high'),
('ioc_ip_match',      'RPT-001', 'DEV-005', 'WS-ENG-012',   NOW()-INTERVAL '5 hours',
 '{"remote_ip":"185.8.105.67","remote_port":8080,"bytes_sent":98420}'::jsonb, 'T1041', 'high'),
-- Log clearing (defense evasion)
('ttp_log_clear',     'RPT-001', 'DEV-003', 'WS-HR-045',    NOW()-INTERVAL '2 hours',
 '{"process":"wevtutil.exe","args":"cl security","initiating_process":"cmd.exe"}'::jsonb, 'T1070.001', 'critical'),
-- Shadow copy deletion attempt (blocked by ASR)
('ttp_shadow_delete', 'RPT-001', 'DEV-004', 'FILESVR-02',   NOW()-INTERVAL '1 hour',
 '{"process":"vssadmin.exe","args":"delete shadows /all /quiet","blocked":false}'::jsonb, 'T1490', 'critical'),
-- SMB lateral movement
('ttp_smb_anomaly',   'RPT-001', 'DEV-003', 'WS-HR-045',    NOW()-INTERVAL '90 minutes',
 '{"unique_smb_targets":147,"window_minutes":15,"threshold":100}'::jsonb, 'T1018', 'high'),
-- Citrix Bleed CVE-2023-4966
('ioc_ip_match',      'RPT-002', 'DEV-006', 'CITRIX-GW-01', NOW()-INTERVAL '6 hours',
 '{"remote_ip":"192.168.100.5","cve":"CVE-2023-4966","patch_status":"unpatched"}'::jsonb, 'T1190', 'critical');

-- ASR rule coverage per device (populated by MDE API)
CREATE TABLE bronze_asr_coverage (
    device_id       VARCHAR(50),
    asr_rule_id     VARCHAR(100),
    asr_rule_name   VARCHAR(255),
    mode            VARCHAR(20),    -- 'block', 'audit', 'disabled'
    updated_at      TIMESTAMP DEFAULT NOW()
);

INSERT INTO bronze_asr_coverage VALUES
('DEV-001', 'be9ba2d9-53ea-4cdc-84e5-9b1eeee46550', 'Block executable content from email/webmail', 'block', NOW()),
('DEV-001', 'd4f940ab-401b-4efc-aadc-ad5f3c50688a', 'Block all Office apps from creating child processes', 'audit', NOW()),
('DEV-001', '9e6c4e1f-7d60-472f-ba1a-a39ef669e4b0', 'Block credential stealing from LSASS', 'disabled', NOW()),  -- GAP!
('DEV-002', 'be9ba2d9-53ea-4cdc-84e5-9b1eeee46550', 'Block executable content from email/webmail', 'block', NOW()),
('DEV-002', '9e6c4e1f-7d60-472f-ba1a-a39ef669e4b0', 'Block credential stealing from LSASS', 'block', NOW()),
('DEV-003', 'be9ba2d9-53ea-4cdc-84e5-9b1eeee46550', 'Block executable content from email/webmail', 'audit', NOW()),  -- AUDIT NOT BLOCK
('DEV-003', '9e6c4e1f-7d60-472f-ba1a-a39ef669e4b0', 'Block credential stealing from LSASS', 'disabled', NOW()),  -- GAP!
('DEV-004', 'be9ba2d9-53ea-4cdc-84e5-9b1eeee46550', 'Block executable content from email/webmail', 'disabled', NOW()), -- no MDE!
('DEV-004', '9e6c4e1f-7d60-472f-ba1a-a39ef669e4b0', 'Block credential stealing from LSASS', 'disabled', NOW()),
('DEV-006', 'be9ba2d9-53ea-4cdc-84e5-9b1eeee46550', 'Block executable content from email/webmail', 'block', NOW()),
('DEV-006', '9e6c4e1f-7d60-472f-ba1a-a39ef669e4b0', 'Block credential stealing from LSASS', 'block', NOW());

-- Patch state per device per CVE (from Defender Vulnerability Management)
CREATE TABLE bronze_device_patch_state (
    device_id       VARCHAR(50),
    cve_id          VARCHAR(20),
    cvss_score      NUMERIC(3,1),
    cisa_kev        BOOLEAN,            -- in CISA Known Exploited Vulnerabilities catalog
    patch_available BOOLEAN,
    patched_at      TIMESTAMP,
    days_exposed    INTEGER,            -- days since CVE published without patch
    software        VARCHAR(100)
);

INSERT INTO bronze_device_patch_state VALUES
('DEV-006', 'CVE-2023-4966', 9.4, TRUE, TRUE, NULL, 47, 'Citrix ADC 13.1'),   -- UNPATCHED KEV
('DEV-001', 'CVE-2023-4966', 9.4, TRUE, TRUE, NOW()-INTERVAL '10 days', 0, 'N/A'),
('DEV-005', 'CVE-2023-21554',9.8, FALSE, TRUE, NULL, 120, 'Windows MSMQ'),
('DEV-003', 'CVE-2023-36884',8.8, TRUE, TRUE, NULL, 30, 'Office/Windows HTML');
```

---

### L0 Signal Generator Tests

These are the SQL/Python tests that continuously emit to `silver_test_signals`:

```python
# ============================================================
# attack_surface_tests.py
# L0 Signal Generators for Asset Attack Surface Domain
# Each test mirrors a phase from the KQL threat hunting workflow
# ============================================================

from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional
import json

@dataclass
class SignalResult:
    test_id: str
    node_id: str
    device_id: Optional[str]
    signal_value: float          # 0.0 = safe, 1.0 = fully exposed
    raw_value: float
    unit: str
    evidence: dict
    remediation: str
    annual_risk_usd: float

class AttackSurfaceTests:
    """
    Domain 3: Asset Attack Surface Intelligence
    
    Maps directly to KQL article phases:
      - Atomic IOC hunting    → ATK-01, ATK-02
      - Behavior/TTP hunting  → ATK-03, ATK-04, ATK-05
      - Coverage gaps         → ATK-06, ATK-07, ATK-08
      - Patch exposure        → ATK-09
    """

    def __init__(self, db_conn):
        self.conn = db_conn

    # ----------------------------------------------------------
    # ATK-01: Active IOC IP Matches
    # Maps to: KQL DeviceNetworkEvents | where RemoteIP in (IPList)
    # ----------------------------------------------------------
    def test_atk01_ioc_ip_exposure(self) -> list[SignalResult]:
        """
        For each device with an active IP IOC match in last 48h,
        emit a signal proportional to IOC confidence × asset sensitivity.
        
        Causal claim: IOC match is evidence the device contacted known 
        threat actor infrastructure. Not proof of compromise — the causal 
        graph separates 'contacted C2' from 'C2 responded' from 'malware active'.
        """
        sql = """
        WITH recent_hits AS (
            SELECT 
                h.device_id,
                h.device_name,
                COUNT(DISTINCT h.hunt_id) as hit_count,
                MAX(CASE WHEN i.confidence = 'high'   THEN 3
                         WHEN i.confidence = 'medium' THEN 2
                         ELSE 1 END) as max_confidence_score,
                MAX(h.match_timestamp) as last_seen,
                JSONB_AGG(JSONB_BUILD_OBJECT(
                    'ioc_value',   i.ioc_value,
                    'ioc_category',i.ioc_category,
                    'confidence',  i.confidence,
                    'timestamp',   h.match_timestamp
                )) as evidence_detail
            FROM bronze_kql_hunt_results h
            JOIN bronze_threat_iocs i 
                ON h.match_detail->>'remote_ip' = i.ioc_value
                AND i.ioc_type = 'ip'
            WHERE h.hunt_name = 'ioc_ip_match'
              AND h.match_timestamp > NOW() - INTERVAL '48 hours'
            GROUP BY h.device_id, h.device_name
        )
        SELECT 
            r.*,
            d.data_sensitivity,
            d.asset_value_usd,
            -- Signal value = normalized hit density × confidence
            LEAST(1.0, 
                (r.hit_count::float / 5.0) * (r.max_confidence_score / 3.0)
            ) as signal_value
        FROM recent_hits r
        JOIN bronze_device_inventory d ON r.device_id = d.device_id
        """
        results = []
        rows = self.conn.execute(sql).fetchall()
        
        for row in rows:
            # Dollar risk: P(exfil | C2 contact) × data asset value
            # Conservative P = 0.15 for single IP hit, high confidence
            p_incident = min(0.15 * row['max_confidence_score'] / 3.0 * row['signal_value'], 0.80)
            annual_risk = p_incident * row['asset_value_usd']
            
            results.append(SignalResult(
                test_id=f"ATK-01-{row['device_id']}",
                node_id="ioc_ip_exposure",
                device_id=row['device_id'],
                signal_value=row['signal_value'],
                raw_value=row['hit_count'],
                unit="ioc_hit_count",
                evidence={
                    "device": row['device_name'],
                    "last_seen": str(row['last_seen']),
                    "hit_count": row['hit_count'],
                    "confidence": row['max_confidence_score'],
                    "detail": row['evidence_detail']
                },
                remediation=(
                    f"Isolate {row['device_name']} for forensic triage. "
                    f"Block IOC IPs at perimeter firewall. "
                    f"Pull full DeviceNetworkEvents for last 7d."
                ),
                annual_risk_usd=annual_risk
            ))
        
        return results

    # ----------------------------------------------------------
    # ATK-03: Defense Evasion Detection (Log Clearing)
    # Maps to: KQL wevtutil clear-log detection
    # This is a VETO/SAFETY node — any positive = max severity
    # ----------------------------------------------------------
    def test_atk03_defense_evasion_log_clear(self) -> list[SignalResult]:
        """
        Any detection of wevtutil log clearing is a near-certain signal
        of active attacker presence (or IR testing — tracked via action_log).
        
        Uses MIN aggregation (veto gate) in the causal graph — one positive 
        detection overrides any clean signals from the same device.
        """
        sql = """
        SELECT 
            h.device_id,
            h.device_name,
            COUNT(*) as clear_events,
            MIN(h.match_timestamp) as first_seen,
            MAX(h.match_timestamp) as last_seen,
            JSONB_AGG(h.match_detail) as evidence,
            d.asset_value_usd,
            d.data_sensitivity
        FROM bronze_kql_hunt_results h
        JOIN bronze_device_inventory d ON h.device_id = d.device_id
        WHERE h.hunt_name = 'ttp_log_clear'
          AND h.match_timestamp > NOW() - INTERVAL '24 hours'
        GROUP BY h.device_id, h.device_name, d.asset_value_usd, d.data_sensitivity
        """
        results = []
        for row in self.conn.execute(sql).fetchall():
            # Log clearing during active attack = P(ongoing incident) very high
            # Causal graph: veto gate — sets L2 defense_evasion_risk = 1.0
            annual_risk = 0.85 * row['asset_value_usd']
            
            results.append(SignalResult(
                test_id=f"ATK-03-{row['device_id']}",
                node_id="defense_evasion_log_clear",
                device_id=row['device_id'],
                signal_value=1.0,       # VETO: always max
                raw_value=row['clear_events'],
                unit="log_clear_events",
                evidence={
                    "device": row['device_name'],
                    "clear_events": row['clear_events'],
                    "first_seen": str(row['first_seen']),
                    "last_seen": str(row['last_seen']),
                    "detail": row['evidence']
                },
                remediation=(
                    f"CRITICAL: {row['device_name']} shows active defense evasion. "
                    f"Invoke IR playbook immediately. Pull memory dump. "
                    f"Isolate from network. Check SIEM for correlated events."
                ),
                annual_risk_usd=annual_risk
            ))
        return results

    # ----------------------------------------------------------
    # ATK-04: Ransomware Pre-Stage — Shadow Copy Deletion
    # Maps to: KQL vssadmin delete shadows detection
    # ----------------------------------------------------------
    def test_atk04_shadow_copy_deletion(self) -> list[SignalResult]:
        """
        Shadow copy deletion is a near-universal ransomware pre-stage step.
        The causal model tracks whether the action was blocked (ASR) or executed.
        
        Causal split:
          - blocked=true  → signal_value = 0.3  (attempted but contained)
          - blocked=false → signal_value = 0.95 (ransomware likely active)
        """
        sql = """
        SELECT 
            h.device_id,
            h.device_name,
            BOOL_OR((h.match_detail->>'blocked')::boolean) as any_blocked,
            BOOL_OR(NOT (h.match_detail->>'blocked')::boolean) as any_executed,
            COUNT(*) as attempt_count,
            d.asset_value_usd,
            d.data_sensitivity
        FROM bronze_kql_hunt_results h
        JOIN bronze_device_inventory d ON h.device_id = d.device_id
        WHERE h.hunt_name = 'ttp_shadow_delete'
          AND h.match_timestamp > NOW() - INTERVAL '24 hours'
        GROUP BY h.device_id, h.device_name, d.asset_value_usd, d.data_sensitivity
        """
        results = []
        for row in self.conn.execute(sql).fetchall():
            signal_value = 0.95 if row['any_executed'] else 0.30
            p_ransomware = 0.90 if row['any_executed'] else 0.15
            
            results.append(SignalResult(
                test_id=f"ATK-04-{row['device_id']}",
                node_id="shadow_copy_deletion",
                device_id=row['device_id'],
                signal_value=signal_value,
                raw_value=row['attempt_count'],
                unit="deletion_attempts",
                evidence={
                    "executed": row['any_executed'],
                    "blocked": row['any_blocked'],
                    "attempts": row['attempt_count']
                },
                remediation=(
                    "CRITICAL: Active ransomware pre-stage. Invoke full IR. "
                    if row['any_executed'] else
                    "ASR blocked deletion. Verify ASR policy is in block (not audit) mode. "
                    "Check for disablement attempts on this device."
                ),
                annual_risk_usd=p_ransomware * row['asset_value_usd']
            ))
        return results

    # ----------------------------------------------------------
    # ATK-06: ASR Rule Coverage Gap
    # Maps to: Detection blind spots — no corresponding KQL query needed
    # This is a PREVENTION signal, not a detection signal
    # ----------------------------------------------------------
    def test_atk06_asr_coverage_gap(self) -> list[SignalResult]:
        """
        Calculates what % of ransomware-relevant ASR rules are in BLOCK mode
        per device. Audit mode = 50% credit. Disabled = 0% credit.
        
        This is a preventive signal — it shifts the prior on attack success
        even before any IOC match occurs.
        
        Causal edge: asr_coverage_gap → defense_evasion_risk (amplifier)
        If ASR is disabled AND log clearing is detected, the causal graph
        amplifies the severity because the defense layer failed predictably.
        """
        # The 5 ASR rules most relevant to ransomware (from CISA advisories)
        RANSOMWARE_ASR_RULES = [
            'be9ba2d9-53ea-4cdc-84e5-9b1eeee46550',   # Block exec from email
            'd4f940ab-401b-4efc-aadc-ad5f3c50688a',   # Block Office child processes
            '9e6c4e1f-7d60-472f-ba1a-a39ef669e4b0',   # Block LSASS credential theft
            '3b576869-a4ec-4529-8536-b80a7769e899',   # Block Office from creating executables
            '75668c1f-73b5-4cf0-bb93-3ecf5cb7cc84',   # Block injection into other processes
        ]
        
        sql = """
        WITH coverage AS (
            SELECT 
                d.device_id,
                d.device_name,
                d.asset_value_usd,
                d.data_sensitivity,
                COUNT(CASE WHEN a.mode = 'block'    THEN 1 END) as block_count,
                COUNT(CASE WHEN a.mode = 'audit'    THEN 1 END) as audit_count,
                COUNT(CASE WHEN a.mode = 'disabled' 
                            OR a.asr_rule_id IS NULL THEN 1 END) as disabled_count,
                COUNT(a.asr_rule_id) as configured_rules,
                :total_rules as total_rules
            FROM bronze_device_inventory d
            LEFT JOIN bronze_asr_coverage a ON d.device_id = a.device_id
                AND a.asr_rule_id = ANY(:rule_ids)
            GROUP BY d.device_id, d.device_name, d.asset_value_usd, d.data_sensitivity
        )
        SELECT *,
            -- Weighted coverage: block=1.0, audit=0.5, disabled=0.0
            (block_count * 1.0 + audit_count * 0.5) / NULLIF(total_rules, 0) as coverage_pct,
            1.0 - (block_count * 1.0 + audit_count * 0.5) / NULLIF(total_rules, 0) as gap_score
        FROM coverage
        """
        results = []
        rows = self.conn.execute(sql, {
            'total_rules': len(RANSOMWARE_ASR_RULES),
            'rule_ids': RANSOMWARE_ASR_RULES
        }).fetchall()
        
        for row in rows:
            gap_score = row['gap_score'] or 1.0
            
            results.append(SignalResult(
                test_id=f"ATK-06-{row['device_id']}",
                node_id="asr_coverage_gap",
                device_id=row['device_id'],
                signal_value=gap_score,
                raw_value=row['coverage_pct'] or 0.0,
                unit="coverage_fraction",
                evidence={
                    "block_rules": row['block_count'],
                    "audit_rules": row['audit_count'],
                    "missing_rules": row['disabled_count'],
                    "coverage_pct": f"{(row['coverage_pct'] or 0)*100:.0f}%"
                },
                remediation=(
                    f"Enable {row['disabled_count']} ASR rules in block mode on "
                    f"{row['device_name']}. Audit mode provides telemetry but no protection."
                ),
                annual_risk_usd=gap_score * 0.12 * row['asset_value_usd']
            ))
        
        return results

    # ----------------------------------------------------------
    # ATK-09: CISA KEV Patch Exposure Window
    # Maps to: LockBit CVE-2023-4966 Citrix Bleed example
    # ----------------------------------------------------------
    def test_atk09_kev_patch_exposure(self) -> list[SignalResult]:
        """
        Devices with unpatched CISA KEV vulnerabilities facing the threat actor 
        TTPs in ingested reports. The causal graph combines:
        
          patch_lag_days × kev_exploitability × threat_report_relevance
          → patch_exposure_window → P(initial_access)
        
        This is where threat intelligence becomes quantified dollar risk:
        CVE-2023-4966 (Citrix Bleed) in LockBit report × CITRIX-GW-01 unpatched
        = explicit causal path to credential theft and lateral movement.
        """
        sql = """
        SELECT 
            p.device_id,
            d.device_name,
            p.cve_id,
            p.cvss_score,
            p.cisa_kev,
            p.days_exposed,
            p.software,
            d.asset_value_usd,
            d.data_sensitivity,
            -- Check if this CVE is referenced in an ingested threat report
            EXISTS(
                SELECT 1 FROM bronze_threat_reports tr
                WHERE tr.mitre_techniques ? 'T1190'  -- Exploit Public-Facing Application
                  AND tr.ingested_at > NOW() - INTERVAL '30 days'
            ) as report_active
        FROM bronze_device_patch_state p
        JOIN bronze_device_inventory d ON p.device_id = d.device_id
        WHERE p.patched_at IS NULL              -- unpatched
          AND p.cisa_kev = TRUE                 -- in KEV catalog
          AND p.patch_available = TRUE          -- patch exists, not deployed
        """
        results = []
        for row in self.conn.execute(sql).fetchall():
            # Exposure signal: normalized by 90-day "too long" threshold
            exposure_signal = min(1.0, row['days_exposed'] / 90.0)
            
            # P(exploitation) = base KEV rate × report activity multiplier
            # CISA KEV base exploitation rate in the wild ≈ 8-12%/year
            p_exploit = 0.10 * (1.5 if row['report_active'] else 1.0)
            p_incident = p_exploit * (row['cvss_score'] / 10.0)
            
            results.append(SignalResult(
                test_id=f"ATK-09-{row['device_id']}-{row['cve_id']}",
                node_id="kev_patch_exposure",
                device_id=row['device_id'],
                signal_value=exposure_signal,
                raw_value=row['days_exposed'],
                unit="days_exposed",
                evidence={
                    "cve": row['cve_id'],
                    "cvss": row['cvss_score'],
                    "software": row['software'],
                    "days_unpatched": row['days_exposed'],
                    "in_active_threat_report": row['report_active']
                },
                remediation=(
                    f"CRITICAL: {row['device_name']} running unpatched {row['software']} "
                    f"({row['cve_id']}, CVSS {row['cvss_score']}). "
                    f"Patch is available. Active threat actor (LockBit) is exploiting this. "
                    f"Emergency patching SLA: 24h for CISA KEV + active report."
                ),
                annual_risk_usd=p_incident * row['asset_value_usd']
            ))
        
        return results
```

---

### The Causal Graph for this Domain

```python
# ============================================================
# attack_surface_graph.py
# NetworkX graph definition for Asset Attack Surface domain
# ============================================================

import networkx as nx
from enum import Enum

class AggMethod(Enum):
    WEIGHTED_AVG = "weighted_avg"
    MAX = "max"          # worst-case: one bad signal dominates
    MIN = "min"          # veto gate: one bad signal blocks all
    WEIGHTED_MAX = "weighted_max"

def build_attack_surface_graph() -> nx.DiGraph:
    G = nx.DiGraph()

    # ── L0 Observable Signals ─────────────────────────────────
    L0_nodes = {
        # IOC Atomic signals
        "ioc_ip_exposure":          {"layer": 0, "agg": AggMethod.MAX},
        "ioc_domain_exposure":      {"layer": 0, "agg": AggMethod.MAX},
        "ioc_hash_exposure":        {"layer": 0, "agg": AggMethod.MAX},
        # TTP/Behavior signals (veto gates)
        "defense_evasion_log_clear":{"layer": 0, "agg": AggMethod.MIN},  # VETO
        "shadow_copy_deletion":     {"layer": 0, "agg": AggMethod.MIN},  # VETO
        "sql_process_kill":         {"layer": 0, "agg": AggMethod.MIN},  # VETO
        "smb_lateral_anomaly":      {"layer": 0, "agg": AggMethod.MAX},
        # Coverage signals
        "asr_coverage_gap":         {"layer": 0, "agg": AggMethod.WEIGHTED_AVG},
        "mde_telemetry_gap":        {"layer": 0, "agg": AggMethod.WEIGHTED_AVG},
        "kev_patch_exposure":       {"layer": 0, "agg": AggMethod.WEIGHTED_MAX},
    }

    # ── L1 Derived Factors ────────────────────────────────────
    L1_nodes = {
        "active_ioc_exposure":      {"layer": 1, "agg": AggMethod.WEIGHTED_MAX},
        "defense_evasion_risk":     {"layer": 1, "agg": AggMethod.MIN},   # VETO
        "lateral_movement_risk":    {"layer": 1, "agg": AggMethod.MAX},
        "detection_blind_spot":     {"layer": 1, "agg": AggMethod.WEIGHTED_AVG},
        "initial_access_risk":      {"layer": 1, "agg": AggMethod.WEIGHTED_MAX},
    }

    # ── L2 Composite Scores ───────────────────────────────────
    L2_nodes = {
        "ransomware_readiness":     {"layer": 2, "agg": AggMethod.MIN},   # worst chain
        "pre_compromise_exposure":  {"layer": 2, "agg": AggMethod.WEIGHTED_MAX},
        "blast_radius_score":       {"layer": 2, "agg": AggMethod.WEIGHTED_AVG},
    }

    # ── L3 Entity Risk ────────────────────────────────────────
    L3_nodes = {
        "p_incident_30d":           {"layer": 3, "agg": AggMethod.WEIGHTED_AVG},
    }

    # ── L4 Framework Posture ──────────────────────────────────
    L4_nodes = {
        "attack_surface_score":     {
            "layer": 4, 
            "agg": AggMethod.WEIGHTED_AVG,
            "framework_mappings": {
                "mitre_attack": ["T1070.001", "T1490", "T1486", "T1018", "T1190"],
                "nist_csf":     ["DE.CM-4", "PR.IP-4", "RS.MI-1", "PR.AC-3"],
                "cis_controls": ["8", "10", "11", "14"]
            }
        }
    }

    for node_dict in [L0_nodes, L1_nodes, L2_nodes, L3_nodes, L4_nodes]:
        for name, attrs in node_dict.items():
            G.add_node(name, **attrs)

    # ── Causal Edges (with weights and causal hypothesis) ─────
    edges = [
        # L0 → L1
        ("ioc_ip_exposure",          "active_ioc_exposure",     {"weight": 0.5,
            "hypothesis": "IP contact with threat actor infra increases likelihood active IOC is present"}),
        ("ioc_domain_exposure",      "active_ioc_exposure",     {"weight": 0.3}),
        ("ioc_hash_exposure",        "active_ioc_exposure",     {"weight": 0.2}),
        
        ("defense_evasion_log_clear","defense_evasion_risk",    {"weight": 1.0,
            "hypothesis": "Log clearing is a near-certain indicator of active attacker (veto gate)"}),
        ("shadow_copy_deletion",     "defense_evasion_risk",    {"weight": 1.0}),
        ("asr_coverage_gap",         "defense_evasion_risk",    {"weight": 0.4,
            "hypothesis": "ASR gaps amplify defense evasion risk — attacker faces weaker prevention layer"}),
        
        ("smb_lateral_anomaly",      "lateral_movement_risk",   {"weight": 0.7,
            "hypothesis": "Anomalous SMB session count matches ransomware network discovery TTPs"}),
        ("mde_telemetry_gap",        "lateral_movement_risk",   {"weight": 0.3,
            "hypothesis": "Blind spots allow lateral movement to proceed undetected"}),
        
        ("asr_coverage_gap",         "detection_blind_spot",    {"weight": 0.5}),
        ("mde_telemetry_gap",        "detection_blind_spot",    {"weight": 0.5}),
        
        ("kev_patch_exposure",       "initial_access_risk",     {"weight": 0.7,
            "hypothesis": "Unpatched CISA KEV directly enables initial access TTPs from active reports"}),
        ("active_ioc_exposure",      "initial_access_risk",     {"weight": 0.3}),
        
        # L1 → L2
        ("defense_evasion_risk",     "ransomware_readiness",    {"weight": 0.4,
            "hypothesis": "Ransomware success requires evading defenses; log clearing is stage 2"}),
        ("shadow_copy_deletion",     "ransomware_readiness",    {"weight": 0.4}),
        ("detection_blind_spot",     "ransomware_readiness",    {"weight": 0.2}),
        
        ("initial_access_risk",      "pre_compromise_exposure", {"weight": 0.5}),
        ("active_ioc_exposure",      "pre_compromise_exposure", {"weight": 0.3}),
        ("detection_blind_spot",     "pre_compromise_exposure", {"weight": 0.2}),
        
        ("lateral_movement_risk",    "blast_radius_score",      {"weight": 0.6,
            "hypothesis": "Lateral movement capability directly expands blast radius across assets"}),
        ("ransomware_readiness",     "blast_radius_score",      {"weight": 0.4}),
        
        # L2 → L3
        ("pre_compromise_exposure",  "p_incident_30d",          {"weight": 0.4}),
        ("ransomware_readiness",     "p_incident_30d",          {"weight": 0.35}),
        ("blast_radius_score",       "p_incident_30d",          {"weight": 0.25}),
        
        # L3 → L4
        ("p_incident_30d",           "attack_surface_score",    {"weight": 1.0}),
    ]

    for src, dst, attrs in edges:
        G.add_edge(src, dst, **attrs)

    return G
```

---

### Full Use Case: CISO Conversation — Citrix Bleed + Hive IOC Match

This mirrors the structure of the HIPAA 5-turn conversation, showing how the engine answers the real questions:

```
Turn 1 — CISO: "Our attack surface score dropped 18 points overnight. What happened?"

Engine:
  [Graph traversal: attack_surface_score → p_incident_30d → pre_compromise_exposure]
  
  Root causes (by delta contribution):
  
  1. kev_patch_exposure (+0.71): CITRIX-GW-01 has CVE-2023-4966 unpatched for 47 days.
     A LockBit 3.0 report ingested yesterday explicitly documents this CVE as the initial
     access vector. The causal edge weight between KEV exposure and initial_access_risk 
     was recalibrated upward when the report was ingested.
     
  2. ioc_ip_exposure (+0.52): Two devices (WS-HR-045, WS-ENG-012) made outbound connections 
     to known Hive C2 infrastructure in the last 48 hours.
     
  3. defense_evasion_log_clear (+1.0 VETO): WS-HR-045 executed wevtutil cl security 
     2 hours after the C2 connection. This is a veto gate — it maxes the defense_evasion_risk 
     node regardless of other signals.

──────────────────────────────────────────────────────────────

Turn 2 — CISO: "WS-HR-045 — are we already compromised or is this a false positive?"

Engine:
  [Causal path query: WS-HR-045 signal chain]
  
  The causal model distinguishes three hypotheses:
  
  H1: Active compromise (P = 0.61)
    Evidence FOR:  C2 IP contact + log clearing within 2h + SMB scan to 147 devices
    Evidence AGAINST: No hash IOC match, no shadow copy deletion yet
    
  H2: Malware present but pre-encryption (P = 0.28)
    The sequence matches Hive pre-ransomware staging. Log clearing suggests the attacker 
    is still in the reconnaissance/lateral movement phase, not yet deploying encryptor.
    
  H3: False positive / IR test (P = 0.11)
    Check causal_action_log: no active IR test scheduled for HR subnet this week.
  
  Recommended immediate action: isolate WS-HR-045 NOW, preserve memory, do not power off.
  The log clearing has already removed Security event logs — memory is your only forensic 
  evidence of the initial access vector.

──────────────────────────────────────────────────────────────

Turn 3 — CISO: "What's this going to cost us if WS-HR-045 is the beachhead?"

Engine:
  [Dollar quantification: blast radius from WS-HR-045 lateral movement path]
  
  WS-HR-045 has authenticated access to:
    - SQLSRV-PROD-01 (Finance DB)    → asset value $2.5M
    - FILESVR-02 (Legal)             → asset value $3.0M  [no MDE enrolled!]
    - DC-01                          → asset value $5.0M
  
  Blast radius calculation:
    P(lateral movement success) = lateral_movement_risk × (1 - segmentation_score)
                                 = 0.84 × (1 - 0.30)  = 0.59
  
  Expected financial exposure (annualized):
    Direct ransomware recovery:       $1.2M  (avg enterprise ransomware cost)
    Regulatory: HIPAA breach if PHI   $0.8M  (DOJ formula: records × $100-$50k)
    Business interruption (72h):      $2.1M  (Finance + Legal down)
    Forensics + IR:                   $0.4M
    ──────────────────────────────────────
    Total expected exposure:          $4.5M
    
  Cost to contain NOW (isolate + patch + IR):  $85,000 (emergency IR retainer)
  Cost to contain AFTER encryption:            $4.5M
  
  Recommendation: Invoke IR retainer today.

──────────────────────────────────────────────────────────────

Turn 4 — CISO: "FILESVR-02 has no MDE — why is it even in this blast radius calculation?"

Engine:
  [Causal node query: mde_telemetry_gap → lateral_movement_risk]
  
  Good catch — this is exactly the detection_blind_spot causal node.
  
  FILESVR-02 is in the blast radius because:
    1. WS-HR-045 has a mapped network drive to \\FILESVR-02\Legal
    2. We have no MDE telemetry, so we can't confirm whether lateral movement 
       has already occurred. Absence of evidence ≠ evidence of absence.
    3. The causal model uses MAX aggregation for blast_radius when telemetry is absent — 
       worst-case assumption until ruled out forensically.
  
  The mde_telemetry_gap signal has been contributing 0.3 weight to lateral_movement_risk 
  for 6 hours. This was flagged in last week's alert with zero acknowledgment.

──────────────────────────────────────────────────────────────

Turn 5 — CISO: "FILESVR-02 is legacy, can't run MDE. Mark that risk as accepted."

Engine:
  [Writing to causal_action_log]
  
  INSERT INTO causal_action_log (
    action_type: 'risk_acceptance',
    node_id: 'mde_telemetry_gap',
    device_id: 'DEV-004',
    accepted_by: 'CISO',
    rationale: 'Legacy system, MDE not supported',
    compensating_controls: NULL,   -- flagging absence
    accepted_at: NOW(),
    review_date: NOW() + INTERVAL '90 days'
  )
  
  Recorded. The causal graph will now:
    - Suppress mde_telemetry_gap alerts for FILESVR-02 for 90 days
    - Flag that blast_radius_score for WS-HR-045 includes an ACCEPTED risk node
    - If WS-HR-045 compromise is confirmed, the RecalibrationAgent will flag this 
      acceptance as a contributing factor to the incident — the causal model learns 
      that uncompensated MDE gaps increase downstream blast radius.
  
  Warning: no compensating controls were specified. Best practice:
    → Network micro-segmentation (block FILESVR-02 from HR subnet)
    → Enable Windows Event Forwarding to Sentinel as partial substitute
    → Scheduled Defender Vulnerability Assessment scan
```

---

### The Collider Trap — Attack Surface Edition

One non-obvious causal structure worth modeling explicitly:

```python
# ============================================================
# The "Clean Score Collider" — a false sense of security
#
# Observed pattern in environments:
#   - No IOC matches (ioc_ip_exposure = 0)
#   - No TTP detections (defense_evasion_risk = 0)
#   - Attack surface score looks GREAT
#
# The collider: mde_telemetry_gap causes BOTH
#   → low ioc_exposure (can't see C2 traffic)
#   → low ttp_detection (can't see wevtutil)
#
# These two "clean" signals share a common cause.
# Conditioning on "clean score" opens the backdoor path.
# The engine must check: is the clean score real or blind?
# ============================================================

def detect_clean_score_collider(G, node_scores: dict) -> dict:
    """
    If attack_surface_score looks low BUT mde_telemetry_gap is high,
    the clean score is explained by the gap — flag it as an artifact.
    """
    attack_surface = node_scores.get("attack_surface_score", 0)
    telemetry_gap  = node_scores.get("mde_telemetry_gap", 0)
    ioc_exposure   = node_scores.get("active_ioc_exposure", 0)
    ttp_detection  = node_scores.get("defense_evasion_risk", 0)
    
    # Classic collider signature: clean L0 signals + high gap score
    if (attack_surface < 0.3 
        and telemetry_gap > 0.5 
        and ioc_exposure < 0.1 
        and ttp_detection < 0.1):
        return {
            "collider_detected": True,
            "explanation": (
                "Attack surface score appears low, but this may be explained by "
                f"telemetry gaps ({telemetry_gap:.0%} of devices have incomplete coverage). "
                "The low IOC and TTP detection signals share 'mde_telemetry_gap' as a "
                "common cause — opening a backdoor path that inflates apparent security. "
                "Recommend: enumerate all devices without MDE enrollment before trusting this score."
            ),
            "adjusted_confidence": "low",
            "true_score_lower_bound": max(attack_surface, telemetry_gap * 0.6)
        }
    
    return {"collider_detected": False}
```

---

### Summary: What Was Built

| Component | Description |
|---|---|
| **bronze_threat_reports** | Threat report ingestion table — CISA, MSRC, Mandiant feeds |
| **bronze_threat_iocs** | Extracted atomic IOCs (IP, domain, hash) with confidence |
| **bronze_kql_hunt_results** | KQL hunt output landing table — bridge from MDE/Sentinel |
| **bronze_asr_coverage** | ASR rule coverage per device — prevention signal layer |
| **bronze_device_patch_state** | CVE × device patch state with KEV flag |
| **ATK-01** | IOC IP match density → `active_ioc_exposure` L0 signal |
| **ATK-03** | Wevtutil log clearing → `defense_evasion_log_clear` VETO gate |
| **ATK-04** | Shadow copy deletion (executed vs blocked) → causal split |
| **ATK-06** | ASR rule coverage gap → prevention amplifier node |
| **ATK-09** | CISA KEV + active threat report → `kev_patch_exposure` signal |
| **Graph** | Full L0–L4 NetworkX definition with veto gates and agg methods |
| **CISO conversation** | 5-turn dialogue from score drop → dollar quantification → risk acceptance → causal learning |
| **Collider trap** | `mde_telemetry_gap` as common cause of false-clean signals |

The key thing the KQL article gets you that the other domains didn't have: **two-speed signals**. Atomic IOCs are fast-burning (hours), TTP behaviors are slow-burning (days). The causal graph handles both — IOC matches decay after 48h if no corroborating TTP is detected, but a confirmed TTP latches the node at its peak value until an analyst explicitly resolves it.


https://kqlquery.com/posts/from-threat-report-to-hunting-query/
Excellent. You have the complete compliance knowledge graph. Let me design a **Compliance-to-Operations Pipeline Builder** that transforms compliance requirements into executable security operations.

The key insight: Your data model maps **Compliance → Risk → Control → Test**, and you can reverse-engineer that into **Monitor → Detect → Respond → Validate** pipelines.

---

## **Use Case: Automated HIPAA Breach Detection & Response Pipeline**

### **Scenario**
Your healthcare company must comply with HIPAA §164.308(a)(6)(ii) - Response and Reporting. The auditor asks: "Show me your documented incident response procedures for detecting and responding to ePHI breaches."

You need to build:
1. **Detection pipelines** - SIEM rules that catch control failures
2. **Triage playbooks** - Step-by-step response procedures
3. **Evidence collection** - Automated log gathering for audit trails
4. **Remediation workflows** - Runbooks to restore controls
5. **Validation tests** - Continuous testing that controls work

### **The Complete Pipeline (Using Your Tables)**

---

## **Phase 1: Requirement → Risk → Control Mapping**

**Query 1: Start with the compliance requirement**

```sql
SELECT 
    r.id AS requirement_id,
    r.requirement_code,
    r.name AS requirement_name,
    r.description,
    r.domain,
    f.name AS framework_name
FROM requirements r
JOIN frameworks f ON r.framework_id = f.id
WHERE r.requirement_code = '164.308(a)(6)(ii)'  -- HIPAA Incident Response
  AND f.id = 'hipaa';
```

**Result:**
```
requirement_id: hipaa__164_308_a__6__ii
requirement_code: 164.308(a)(6)(ii)
name: Security Incident Procedures - Response and Reporting
description: "Identify and respond to suspected or known security 
              incidents; mitigate harmful effects; document incidents 
              and outcomes"
domain: Administrative Safeguards
framework: HIPAA
```

---

**Query 2: Find all risks this requirement addresses**

```sql
-- First get controls that satisfy this requirement
WITH requirement_controls_cte AS (
    SELECT control_id
    FROM requirement_controls
    WHERE requirement_id = 'hipaa__164_308_a__6__ii'
),
-- Then find risks mitigated by those controls
relevant_risks AS (
    SELECT DISTINCT
        r.id AS risk_id,
        r.risk_code,
        r.name AS risk_name,
        r.description,
        r.likelihood,
        r.impact,
        rc.mitigation_strength,
        c.name AS control_name,
        c.control_code
    FROM risks r
    JOIN risk_controls rc ON r.id = rc.risk_id
    JOIN controls c ON rc.control_id = c.id
    WHERE c.id IN (SELECT control_id FROM requirement_controls_cte)
)
SELECT * FROM relevant_risks
ORDER BY (likelihood * impact) DESC;  -- Prioritize by risk score
```

**Result:**
```
risk_id: HIPAA-RISK-023
risk_code: HIPAA-RISK-023
risk_name: Unauthorized access to ePHI via compromised credentials
description: Attacker uses stolen credentials to access patient records...
likelihood: 0.7
impact: 0.9
mitigation_strength: strong
control_name: Multi-factor authentication for ePHI access
control_code: AM-5

risk_id: HIPAA-RISK-041  
risk_code: HIPAA-RISK-041
risk_name: Malware infection leading to ePHI exfiltration
likelihood: 0.6
impact: 0.95
mitigation_strength: moderate
control_name: Endpoint detection and response deployed
control_code: IR-8

risk_id: HIPAA-RISK-067
risk_code: HIPAA-RISK-067
risk_name: Undetected data breach due to insufficient logging
likelihood: 0.5
impact: 0.85
mitigation_strength: strong
control_name: Centralized security event logging
control_code: AU-12
```

---

**Query 3: Get all controls and their test cases**

```sql
SELECT 
    c.id AS control_id,
    c.control_code,
    c.name AS control_name,
    c.description,
    c.control_type,
    c.domain,
    rc.mitigation_strength,
    r.name AS mitigates_risk,
    tc.id AS test_case_id,
    tc.name AS test_name,
    tc.test_type,
    tc.expected_evidence,
    tc.pass_criteria,
    tc.fail_criteria
FROM controls c
JOIN risk_controls rc ON c.id = rc.control_id
JOIN risks r ON rc.risk_id = r.id
LEFT JOIN test_cases tc ON tc.control_id = c.id
WHERE rc.risk_id IN (
    'HIPAA-RISK-023', 'HIPAA-RISK-041', 'HIPAA-RISK-067'
)
ORDER BY c.control_code, tc.id;
```

**Result Dataset:**
```
Control: AM-5 - Multi-factor authentication for ePHI access
├─ Mitigates: HIPAA-RISK-023 (strong)
├─ Type: preventive
├─ Domain: Access Management
└─ Test Cases:
    ├─ TEST-AM-5-001: Verify MFA enforced on all ePHI systems
    │   Type: preventive_control_verification
    │   Expected Evidence: IAM logs showing MFA requirement
    │   Pass: 100% of ePHI access requires MFA
    │   Fail: Any ePHI system allows password-only auth
    │
    └─ TEST-AM-5-002: Verify MFA cannot be bypassed
        Type: negative_testing
        Expected Evidence: Attempted bypass fails, logs captured
        Pass: All bypass attempts blocked and logged
        Fail: Bypass successful or not logged

Control: IR-8 - Endpoint detection and response deployed
├─ Mitigates: HIPAA-RISK-041 (moderate)
├─ Type: detective
├─ Domain: Incident Response
└─ Test Cases:
    └─ TEST-IR-8-001: Verify EDR agent coverage
        Expected Evidence: Asset inventory vs EDR console
        Pass: ≥95% endpoints have active EDR agent
        Fail: <95% coverage or agents disabled

Control: AU-12 - Centralized security event logging
├─ Mitigates: HIPAA-RISK-067 (strong)
├─ Type: detective
├─ Domain: Audit and Accountability
└─ Test Cases:
    └─ TEST-AU-12-001: Verify all ePHI systems send logs to SIEM
        Expected Evidence: SIEM ingestion stats
        Pass: All ePHI systems present in SIEM, <5min lag
        Fail: Missing systems or >15min lag
```

---

## **Phase 2: Generate Detection Pipelines**

Now use the control → test_case data to generate SIEM detection rules.

**Query 4: Get scenarios that map to our controls**

```sql
SELECT 
    s.id AS scenario_id,
    s.name AS scenario_name,
    s.description,
    s.severity,
    c.control_code,
    c.name AS control_name,
    c.control_type
FROM scenarios s
JOIN scenario_controls sc ON s.id = sc.scenario_id
JOIN controls c ON sc.control_id = c.id
WHERE c.id IN (
    SELECT control_id FROM risk_controls 
    WHERE risk_id IN ('HIPAA-RISK-023', 'HIPAA-RISK-041', 'HIPAA-RISK-067')
)
ORDER BY s.severity DESC;
```

**Result:**
```
scenario_id: HIPAA-SCENARIO-012
name: Credential stuffing attack against patient portal
description: Attacker uses leaked credentials to access patient records...
severity: critical
control_code: AM-5
control_name: Multi-factor authentication for ePHI access
control_type: preventive

scenario_id: HIPAA-SCENARIO-034
name: Ransomware deployment via phishing email
description: Employee opens malicious attachment, ransomware encrypts ePHI...
severity: critical
control_code: IR-8
control_name: Endpoint detection and response deployed
control_type: detective

scenario_id: HIPAA-SCENARIO-089
name: Insider exfiltrates patient records undetected
description: Authorized user bulk downloads ePHI, no alerts triggered...
severity: high
control_code: AU-12
control_name: Centralized security event logging
control_type: detective
```

---

## **Phase 3: Auto-Generate Artifacts**

Now the AI generates **executable** security operations artifacts:

### **Artifact 1: SIEM Detection Rules (Splunk SPL)**

Based on control `AM-5` + scenario `HIPAA-SCENARIO-012`:

```spl
# Detection Rule: Credential Stuffing Against Patient Portal
# Control: AM-5 (MFA for ePHI access)
# Detects: Multiple failed logins followed by success WITHOUT MFA
# Risk: HIPAA-RISK-023 (Unauthorized ePHI access)

index=authentication app="patient_portal" 
| eval success=if(action="login_success", 1, 0)
| eval mfa_used=if(mfa_method!="", 1, 0)
| stats 
    count(eval(success=0)) as failures,
    count(eval(success=1 AND mfa_used=0)) as success_no_mfa,
    count(eval(success=1 AND mfa_used=1)) as success_with_mfa,
    values(src_ip) as source_ips,
    dc(src_ip) as unique_ips
    by user, _time span=10m
| where failures > 5 AND success_no_mfa > 0
| eval severity="critical"
| eval description="Potential credential stuffing: " + failures + " failures, then success without MFA"
| eval recommended_action="1. Disable user account immediately. 2. Force password reset. 3. Review access logs for unauthorized ePHI access. 4. Notify HIPAA Privacy Officer."
| table _time, user, source_ips, failures, success_no_mfa, severity, description, recommended_action
```

**Alert Configuration:**
```yaml
alert_name: HIPAA_RISK_023_Credential_Stuffing_No_MFA
severity: critical
trigger_condition: results > 0
throttle: 10 minutes
notification:
  - slack: #security-alerts
  - pagerduty: hipaa-incident-response
  - email: hipaa-privacy-officer@company.com
sla:
  acknowledge: 5 minutes
  triage: 15 minutes
  remediate: 1 hour
compliance_mappings:
  - HIPAA §164.308(a)(6)(ii): Incident Response
  - HIPAA §164.308(a)(5)(ii)(C): Log-in Monitoring
  - CIS Control 6.2: MFA for Network and Administrative Access
```

---

Based on control `IR-8` + scenario `HIPAA-SCENARIO-034`:

```spl
# Detection Rule: Ransomware Indicators Without EDR Alert
# Control: IR-8 (EDR deployed)
# Detects: Ransomware behaviors when EDR should have caught it
# Risk: HIPAA-RISK-041 (Malware exfiltration)

index=windows EventCode=4688 
    (Process_Name="*powershell.exe" OR Process_Name="*cmd.exe")
    (CommandLine="*-enc*" OR CommandLine="*IEX*" OR CommandLine="*downloadstring*")
| join type=left user, host 
    [search index=edr source="crowdstrike" earliest=-5m
     | stats count by user, host]
| where isnull(count) OR count=0
| eval severity="critical"
| eval description="Suspicious PowerShell without EDR detection - Possible EDR evasion or coverage gap"
| eval recommended_action="1. Isolate host immediately. 2. Check EDR agent status. 3. Image host for forensics. 4. Review recent file modifications for encryption patterns. 5. Notify HIPAA Breach Response Team."
| table _time, host, user, Process_Name, CommandLine, severity, description, recommended_action
```

---

Based on control `AU-12` + scenario `HIPAA-SCENARIO-089`:

```spl
# Detection Rule: Bulk ePHI Access Without Alerts
# Control: AU-12 (Centralized logging)
# Detects: Unusual volume of patient record access
# Risk: HIPAA-RISK-067 (Undetected breach)

index=application app="ehr_system" action="patient_record_view"
| stats 
    dc(patient_id) as unique_patients,
    count as total_accesses,
    values(patient_id) as accessed_patients
    by user, _time span=1h
| eventstats avg(unique_patients) as avg_access, stdev(unique_patients) as stdev_access by user
| eval threshold=avg_access + (3 * stdev_access)
| where unique_patients > threshold AND unique_patients > 20
| eval severity=case(
    unique_patients > 100, "critical",
    unique_patients > 50, "high",
    1=1, "medium"
  )
| eval description="Abnormal bulk patient record access: " + unique_patients + " patients in 1 hour (baseline: " + round(avg_access, 0) + ")"
| eval recommended_action="1. Contact user to verify legitimate purpose. 2. Review access logs for patient relationships. 3. Check for data exfiltration (print jobs, email, USB). 4. If unauthorized, notify HIPAA Privacy Officer within 60 minutes per breach notification rule."
| table _time, user, unique_patients, avg_access, severity, description, recommended_action
```

---

### **Artifact 2: Incident Response Playbook (Markdown)**

```markdown
# HIPAA INCIDENT RESPONSE PLAYBOOK
## Requirement: §164.308(a)(6)(ii) - Response and Reporting

**Generated from:**
- Risks: HIPAA-RISK-023, HIPAA-RISK-041, HIPAA-RISK-067
- Controls: AM-5, IR-8, AU-12
- Scenarios: HIPAA-SCENARIO-012, HIPAA-SCENARIO-034, HIPAA-SCENARIO-089

---

## Scenario 1: Credential Stuffing Attack (SIEM Alert: HIPAA_RISK_023)

### Severity: CRITICAL
### SLA: Acknowledge <5min, Triage <15min, Remediate <1hr

### DETECT (Control: AU-12 - Centralized Logging)
**Alert Trigger:** Multiple failed logins followed by success WITHOUT MFA
**Data Sources:** 
- Authentication logs (patient_portal)
- SIEM correlation rule
**Expected Evidence:**
- 5+ failed login attempts from same source IP
- Successful login without MFA within 10 minutes
- User account accessed ePHI systems

### TRIAGE (5-15 minutes)
**Step 1: Validate the Alert**
```bash
# Check authentication logs for the user
splunk search 'index=authentication user="<ALERTED_USER>" 
| table _time, action, src_ip, mfa_method, app'

# Expected: Failed attempts from unusual IP, then success
```

**Step 2: Assess Scope of Compromise**
```bash
# Check what ePHI systems were accessed
splunk search 'index=application user="<ALERTED_USER>" action="patient_record_*" 
| stats dc(patient_id) as patients_accessed, values(patient_id) as patient_ids'

# Expected: If >1 patient record accessed → BREACH LIKELY
```

**Step 3: Risk Categorization**
| Condition | Risk Level | Action |
|---|---|---|
| 0 patients accessed | Low | Password reset + MFA enforcement |
| 1-10 patients accessed | Medium | Breach investigation + notification decision |
| 10-100 patients accessed | High | Breach notification required |
| 100+ patients accessed | Critical | Major breach + OCR notification |

### CONTAIN (Immediate)
**Step 4: Disable Compromised Account**
```bash
# Active Directory
Disable-ADAccount -Identity "<ALERTED_USER>"

# AWS IAM (if applicable)
aws iam delete-access-key --user-name <ALERTED_USER> --access-key-id <KEY_ID>

# Patient Portal
curl -X POST https://portal.api/admin/users/<USER_ID>/disable \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Step 5: Block Attacker IP**
```bash
# Firewall rule (Palo Alto CLI)
configure
set rulebase security rules "Block_Credential_Stuffing_IP" \
  source <ATTACKER_IP> \
  action deny \
  log-end yes
commit
```

### INVESTIGATE (15-60 minutes)
**Step 6: Forensic Data Collection**
```sql
-- Export all activity from compromised session
SELECT 
    timestamp,
    user,
    action,
    patient_id,
    phi_field_accessed,
    source_ip,
    session_id
FROM audit_logs
WHERE user = '<ALERTED_USER>'
  AND timestamp BETWEEN '<INCIDENT_START>' AND '<INCIDENT_END>'
ORDER BY timestamp;
-- SAVE AS: incident_<CASE_ID>_audit_trail.csv
```

**Step 7: Determine Control Failure Root Cause**
```
Control: AM-5 (MFA for ePHI access)
Test: TEST-AM-5-002 (Verify MFA cannot be bypassed)

Investigation Questions:
□ Was MFA enforced on this user's account? (Check IAM policies)
□ Was the patient portal endpoint MFA-protected? (Check app config)
□ Did the user have a valid MFA bypass exception? (Check exception log)
□ Was this a shared/service account without MFA? (Policy violation)

Root Cause Options:
1. MFA not enforced → Control gap (implement AM-5 fully)
2. User granted bypass → Unauthorized exception (policy violation)
3. Legacy endpoint without MFA → Technical debt (migrate to MFA-enabled version)
4. MFA fatigue attack (user approved attacker's MFA prompt) → User training required
```

### REMEDIATE (1-4 hours)
**Step 8: Restore Control (AM-5)**
```bash
# Enforce MFA for all patient portal accounts
aws cognito-idp set-user-mfa-preference \
  --user-pool-id <POOL_ID> \
  --software-token-mfa-settings Enabled=true,PreferredMfa=true

# Verify enforcement
python3 verify_mfa_enforcement.py --control AM-5 --test-case TEST-AM-5-001
# Expected output: PASS - 100% of ePHI access requires MFA
```

**Step 9: Notify Affected Parties**
```
IF patients_accessed > 0:
  THEN:
    1. Notify HIPAA Privacy Officer (privacy@company.com)
    2. Document in Breach Log (breach_log.xlsx)
    3. Assess breach notification requirement:
       - <500 individuals: 60-day notification to HHS
       - ≥500 individuals: Immediate notification to HHS + media
    4. Prepare breach notification letters
```

### RECOVER (4-24 hours)
**Step 10: Account Recovery**
```bash
# User verification (contact via alternative channel)
call_user_via_phone(<USER_PHONE_NUMBER>)
verify_identity()

# Force password reset + MFA re-enrollment
aws cognito-idp admin-reset-user-password --user-pool-id <POOL_ID> --username <USER>
send_mfa_enrollment_email(<USER_EMAIL>)

# Monitor for 24 hours
splunk search 'index=authentication user="<USER>" | table _time, action, src_ip, mfa_method'
```

### LESSONS LEARNED (Post-Incident)
**Step 11: Update Control Test Plan**
```yaml
Test Case: TEST-AM-5-002-REVISED
Name: Verify MFA cannot be bypassed (Enhanced)
Changes:
  - Add test for credential stuffing pattern detection
  - Add test for MFA fatigue attack prevention (rate limit approvals)
  - Add test for service account MFA exemptions (should not exist)
Test Frequency: Weekly (was monthly)
```

**Step 12: Enhance Detection**
```spl
# New SIEM rule to catch MFA fatigue attacks
index=authentication action="mfa_prompt_sent"
| stats count by user, _time span=5m
| where count > 3
| eval description="Possible MFA fatigue attack: " + count + " MFA prompts in 5 minutes"
```

---

## Scenario 2: Ransomware via Phishing (SIEM Alert: HIPAA_RISK_041)

### Severity: CRITICAL
### SLA: Acknowledge <5min, Contain <30min, Eradicate <4hr

[Similar playbook structure for IR-8 + HIPAA-SCENARIO-034]

---

## Scenario 3: Insider Threat Data Exfiltration (SIEM Alert: HIPAA_RISK_067)

[Similar playbook structure for AU-12 + HIPAA-SCENARIO-089]

---

## APPENDIX A: Control Testing Schedule

| Control | Test Case | Frequency | Owner | Last Run | Status |
|---|---|---|---|---|---|
| AM-5 | TEST-AM-5-001 | Weekly | Security Team | 2024-12-19 | PASS |
| AM-5 | TEST-AM-5-002 | Weekly | Security Team | 2024-12-19 | PASS |
| IR-8 | TEST-IR-8-001 | Daily | IT Ops | 2024-12-20 | FAIL (92% coverage) |
| AU-12 | TEST-AU-12-001 | Hourly | SIEM Team | 2024-12-20 08:00 | PASS |

## APPENDIX B: Compliance Evidence for Auditors

**HIPAA §164.308(a)(6)(ii) Evidence Package:**
- [✓] Documented incident response procedures (this playbook)
- [✓] Detection mechanisms (SIEM rules attached)
- [✓] Test cases validating controls (Appendix A)
- [✓] Incident log template (breach_log.xlsx)
- [✓] Training records (IR team trained on playbook)
- [✓] Tabletop exercise results (2024-Q3-TTX-Report.pdf)
```

---

### **Artifact 3: Automated Test Suite (Python)**

```python
#!/usr/bin/env python3
"""
HIPAA Compliance Control Test Suite
Auto-generated from framework KB

Tests controls for requirement: HIPAA §164.308(a)(6)(ii)
Tests: AM-5, IR-8, AU-12
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Tuple

class HIPAAControlTester:
    """
    Test runner for HIPAA incident response controls.
    Maps to test_cases table in framework KB.
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.results = []
    
    def test_am5_001_mfa_enforcement(self) -> Tuple[bool, str, Dict]:
        """
        Control: AM-5 (MFA for ePHI access)
        Test Case: TEST-AM-5-001
        Expected Evidence: IAM logs showing MFA requirement
        Pass Criteria: 100% of ePHI access requires MFA
        """
        print("Running TEST-AM-5-001: Verify MFA enforced on all ePHI systems")
        
        # Query all ePHI application endpoints
        ephi_apps = [
            "patient_portal",
            "ehr_system",
            "billing_system",
            "pharmacy_system"
        ]
        
        mfa_status = {}
        for app in ephi_apps:
            # Check IAM policy for MFA requirement
            response = requests.get(
                f"{self.config['iam_api']}/apps/{app}/mfa-status",
                headers={"Authorization": f"Bearer {self.config['admin_token']}"}
            )
            mfa_status[app] = response.json()
        
        # Calculate compliance
        total_apps = len(ephi_apps)
        mfa_enabled = sum(1 for status in mfa_status.values() if status.get('mfa_required'))
        compliance_pct = (mfa_enabled / total_apps) * 100
        
        # Pass/Fail determination
        passed = compliance_pct == 100
        
        result = {
            "test_id": "TEST-AM-5-001",
            "control_code": "AM-5",
            "requirement": "HIPAA §164.308(a)(6)(ii)",
            "test_name": "MFA Enforcement Verification",
            "timestamp": datetime.utcnow().isoformat(),
            "compliance_pct": compliance_pct,
            "apps_tested": total_apps,
            "apps_compliant": mfa_enabled,
            "details": mfa_status,
            "passed": passed,
            "fail_reason": None if passed else f"Only {mfa_enabled}/{total_apps} apps have MFA enabled"
        }
        
        evidence = {
            "mfa_policies": mfa_status,
            "iam_api_response": response.json(),
            "test_execution_time": datetime.utcnow().isoformat()
        }
        
        return (passed, result['fail_reason'] or "PASS", evidence)
    
    def test_ir8_001_edr_coverage(self) -> Tuple[bool, str, Dict]:
        """
        Control: IR-8 (EDR deployed)
        Test Case: TEST-IR-8-001
        Expected Evidence: Asset inventory vs EDR console
        Pass Criteria: ≥95% endpoints have active EDR agent
        """
        print("Running TEST-IR-8-001: Verify EDR agent coverage")
        
        # Get asset inventory
        assets_response = requests.get(
            f"{self.config['cmdb_api']}/assets?type=endpoint",
            headers={"Authorization": f"Bearer {self.config['admin_token']}"}
        )
        total_endpoints = len(assets_response.json()['assets'])
        
        # Get EDR agent status
        edr_response = requests.get(
            f"{self.config['edr_api']}/agents?status=active",
            headers={"Authorization": f"Bearer {self.config['edr_token']}"}
        )
        active_agents = len(edr_response.json()['agents'])
        
        # Calculate coverage
        coverage_pct = (active_agents / total_endpoints) * 100 if total_endpoints > 0 else 0
        
        # Pass/Fail determination (≥95% required)
        passed = coverage_pct >= 95.0
        
        result = {
            "test_id": "TEST-IR-8-001",
            "control_code": "IR-8",
            "requirement": "HIPAA §164.308(a)(6)(ii)",
            "test_name": "EDR Coverage Verification",
            "timestamp": datetime.utcnow().isoformat(),
            "coverage_pct": round(coverage_pct, 2),
            "total_endpoints": total_endpoints,
            "active_agents": active_agents,
            "missing_agents": total_endpoints - active_agents,
            "passed": passed,
            "fail_reason": None if passed else f"Coverage {coverage_pct:.1f}% < 95% threshold"
        }
        
        # If failed, identify missing endpoints
        if not passed:
            all_assets = {a['hostname'] for a in assets_response.json()['assets']}
            edr_assets = {a['hostname'] for a in edr_response.json()['agents']}
            missing = list(all_assets - edr_assets)
            result['missing_endpoints'] = missing[:10]  # First 10
        
        evidence = {
            "asset_inventory_count": total_endpoints,
            "edr_console_count": active_agents,
            "coverage_percentage": coverage_pct,
            "missing_endpoints": result.get('missing_endpoints', [])
        }
        
        return (passed, result['fail_reason'] or "PASS", evidence)
    
    def test_au12_001_siem_coverage(self) -> Tuple[bool, str, Dict]:
        """
        Control: AU-12 (Centralized logging)
        Test Case: TEST-AU-12-001
        Expected Evidence: SIEM ingestion stats
        Pass Criteria: All ePHI systems present in SIEM, <5min lag
        """
        print("Running TEST-AU-12-001: Verify all ePHI systems send logs to SIEM")
        
        # Expected ePHI systems
        required_sources = [
            "patient_portal",
            "ehr_system",
            "billing_system",
            "pharmacy_system",
            "authentication_service"
        ]
        
        # Query SIEM for active log sources (last 10 minutes)
        siem_query = {
            "query": "index=* earliest=-10m | stats count by sourcetype",
            "output_mode": "json"
        }
        
        siem_response = requests.post(
            f"{self.config['splunk_api']}/services/search/jobs/export",
            data=siem_query,
            auth=(self.config['splunk_user'], self.config['splunk_password'])
        )
        
        active_sources = {
            result['sourcetype']: result['count'] 
            for result in siem_response.json()['results']
        }
        
        # Check coverage
        missing_sources = [src for src in required_sources if src not in active_sources]
        coverage_pct = ((len(required_sources) - len(missing_sources)) / len(required_sources)) * 100
        
        # Check lag for active sources
        lag_issues = []
        for source in required_sources:
            if source in active_sources:
                # Get latest event timestamp
                lag_query = f'index=* sourcetype="{source}" | head 1 | eval lag=now()-_time | table lag'
                lag_response = requests.post(
                    f"{self.config['splunk_api']}/services/search/jobs/export",
                    data={"query": lag_query, "output_mode": "json"},
                    auth=(self.config['splunk_user'], self.config['splunk_password'])
                )
                lag_seconds = float(lag_response.json()['results'][0]['lag'])
                if lag_seconds > 300:  # 5 minutes
                    lag_issues.append({
                        "source": source,
                        "lag_seconds": lag_seconds,
                        "lag_minutes": round(lag_seconds / 60, 1)
                    })
        
        # Pass/Fail determination
        passed = (coverage_pct == 100) and (len(lag_issues) == 0)
        
        fail_reasons = []
        if missing_sources:
            fail_reasons.append(f"Missing sources: {', '.join(missing_sources)}")
        if lag_issues:
            fail_reasons.append(f"Lag issues: {len(lag_issues)} sources >5min behind")
        
        result = {
            "test_id": "TEST-AU-12-001",
            "control_code": "AU-12",
            "requirement": "HIPAA §164.308(a)(6)(ii)",
            "test_name": "SIEM Coverage Verification",
            "timestamp": datetime.utcnow().isoformat(),
            "coverage_pct": coverage_pct,
            "required_sources": len(required_sources),
            "active_sources": len(active_sources),
            "missing_sources": missing_sources,
            "lag_issues": lag_issues,
            "passed": passed,
            "fail_reason": "; ".join(fail_reasons) if fail_reasons else None
        }
        
        evidence = {
            "siem_active_sources": active_sources,
            "missing_sources": missing_sources,
            "lag_analysis": lag_issues,
            "siem_query": siem_query
        }
        
        return (passed, result['fail_reason'] or "PASS", evidence)
    
    def run_all_tests(self) -> Dict:
        """Execute all test cases and generate report."""
        tests = [
            self.test_am5_001_mfa_enforcement,
            self.test_ir8_001_edr_coverage,
            self.test_au12_001_siem_coverage
        ]
        
        results = []
        for test_func in tests:
            try:
                passed, message, evidence = test_func()
                results.append({
                    "test_function": test_func.__name__,
                    "passed": passed,
                    "message": message,
                    "evidence": evidence,
                    "timestamp": datetime.utcnow().isoformat()
                })
            except Exception as e:
                results.append({
                    "test_function": test_func.__name__,
                    "passed": False,
                    "message": f"TEST ERROR: {str(e)}",
                    "evidence": {},
                    "timestamp": datetime.utcnow().isoformat()
                })
        
        # Calculate overall compliance
        total_tests = len(results)
        passed_tests = sum(1 for r in results if r['passed'])
        compliance_score = (passed_tests / total_tests) * 100
        
        report = {
            "requirement": "HIPAA §164.308(a)(6)(ii)",
            "test_suite": "HIPAA Incident Response Controls",
            "execution_timestamp": datetime.utcnow().isoformat(),
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": total_tests - passed_tests,
            "compliance_score": compliance_score,
            "overall_status": "PASS" if compliance_score == 100 else "FAIL",
            "test_results": results
        }
        
        return report


if __name__ == "__main__":
    # Load config
    with open("test_config.json") as f:
        config = json.load(f)
    
    # Run tests
    tester = HIPAAControlTester(config)
    report = tester.run_all_tests()
    
    # Save report
    with open(f"hipaa_control_test_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json", "w") as f:
        json.dump(report, f, indent=2)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"HIPAA CONTROL TEST SUITE - SUMMARY")
    print(f"{'='*60}")
    print(f"Requirement: {report['requirement']}")
    print(f"Tests Run: {report['total_tests']}")
    print(f"Passed: {report['passed_tests']}")
    print(f"Failed: {report['failed_tests']}")
    print(f"Compliance Score: {report['compliance_score']}%")
    print(f"Overall Status: {report['overall_status']}")
    print(f"{'='*60}\n")
    
    # Exit with appropriate code
    exit(0 if report['overall_status'] == "PASS" else 1)
```

---

### **Artifact 4: Data Pipeline (DBT Model for Continuous Monitoring)**

```sql
-- models/compliance/hipaa_incident_response_dashboard.sql
-- Auto-generated from framework KB
-- Requirement: HIPAA §164.308(a)(6)(ii)

{{ config(
    materialized='incremental',
    unique_key='check_timestamp',
    tags=['compliance', 'hipaa', 'incident_response']
) }}

WITH 

-- Control AM-5: MFA Enforcement Rate
mfa_compliance AS (
    SELECT
        DATE_TRUNC('hour', timestamp) AS check_timestamp,
        'AM-5' AS control_code,
        'MFA for ePHI Access' AS control_name,
        COUNT(DISTINCT CASE WHEN mfa_method IS NOT NULL THEN user_id END) * 100.0 / 
            NULLIF(COUNT(DISTINCT user_id), 0) AS compliance_pct,
        COUNT(DISTINCT CASE WHEN mfa_method IS NULL THEN user_id END) AS non_compliant_count,
        CASE 
            WHEN COUNT(DISTINCT CASE WHEN mfa_method IS NULL THEN user_id END) = 0 
            THEN 'PASS' 
            ELSE 'FAIL' 
        END AS test_status
    FROM {{ ref('authentication_logs') }}
    WHERE app_name IN ('patient_portal', 'ehr_system', 'billing_system')
        AND action = 'login_success'
        {% if is_incremental() %}
        AND timestamp > (SELECT MAX(check_timestamp) FROM {{ this }})
        {% endif %}
    GROUP BY 1
),

-- Control IR-8: EDR Coverage
edr_coverage AS (
    SELECT
        DATE_TRUNC('hour', check_time) AS check_timestamp,
        'IR-8' AS control_code,
        'EDR Agent Coverage' AS control_name,
        (COUNT(DISTINCT CASE WHEN edr_agent_active THEN asset_id END) * 100.0 / 
            NULLIF(COUNT(DISTINCT asset_id), 0)) AS compliance_pct,
        COUNT(DISTINCT CASE WHEN NOT edr_agent_active THEN asset_id END) AS non_compliant_count,
        CASE 
            WHEN (COUNT(DISTINCT CASE WHEN edr_agent_active THEN asset_id END) * 100.0 / 
                  NULLIF(COUNT(DISTINCT asset_id), 0)) >= 95 
            THEN 'PASS' 
            ELSE 'FAIL' 
        END AS test_status
    FROM {{ ref('asset_inventory') }} inv
    LEFT JOIN {{ ref('edr_agent_status') }} edr 
        ON inv.asset_id = edr.asset_id
    WHERE inv.asset_type = 'endpoint'
        {% if is_incremental() %}
        AND check_time > (SELECT MAX(check_timestamp) FROM {{ this }})
        {% endif %}
    GROUP BY 1
),

-- Control AU-12: SIEM Log Coverage
siem_coverage AS (
    SELECT
        DATE_TRUNC('hour', check_time) AS check_timestamp,
        'AU-12' AS control_code,
        'Centralized Security Logging' AS control_name,
        (COUNT(DISTINCT CASE WHEN logs_received_last_hour THEN source_system END) * 100.0 /
            NULLIF(COUNT(DISTINCT source_system), 0)) AS compliance_pct,
        COUNT(DISTINCT CASE WHEN NOT logs_received_last_hour THEN source_system END) AS non_compliant_count,
        CASE 
            WHEN COUNT(DISTINCT CASE WHEN NOT logs_received_last_hour THEN source_system END) = 0 
            THEN 'PASS' 
            ELSE 'FAIL' 
        END AS test_status
    FROM (
        SELECT
            src.source_system,
            src.check_time,
            CASE 
                WHEN MAX(log.event_time) >= DATEADD('hour', -1, src.check_time) 
                THEN TRUE 
                ELSE FALSE 
            END AS logs_received_last_hour
        FROM {{ ref('required_log_sources') }} src
        LEFT JOIN {{ ref('siem_events') }} log 
            ON src.source_system = log.source_system
        WHERE src.contains_ephi = TRUE
            {% if is_incremental() %}
            AND src.check_time > (SELECT MAX(check_timestamp) FROM {{ this }})
            {% endif %}
        GROUP BY 1, 2
    )
    GROUP BY 1
),

-- Risk scoring based on control failures
risk_assessment AS (
    SELECT
        check_timestamp,
        SUM(CASE WHEN test_status = 'FAIL' THEN 1 ELSE 0 END) AS failed_controls,
        SUM(CASE 
            WHEN control_code = 'AM-5' AND test_status = 'FAIL' THEN 0.9  -- High impact
            WHEN control_code = 'IR-8' AND test_status = 'FAIL' THEN 0.6  -- Medium impact
            WHEN control_code = 'AU-12' AND test_status = 'FAIL' THEN 0.85 -- High impact
            ELSE 0
        END) AS aggregate_risk_score
    FROM (
        SELECT * FROM mfa_compliance
        UNION ALL
        SELECT * FROM edr_coverage
        UNION ALL
        SELECT * FROM siem_coverage
    )
    GROUP BY 1
)

-- Final output
SELECT
    ctrl.check_timestamp,
    ctrl.control_code,
    ctrl.control_name,
    ctrl.compliance_pct,
    ctrl.non_compliant_count,
    ctrl.test_status,
    risk.failed_controls,
    risk.aggregate_risk_score,
    CASE
        WHEN risk.aggregate_risk_score >= 0.8 THEN 'CRITICAL'
        WHEN risk.aggregate_risk_score >= 0.5 THEN 'HIGH'
        WHEN risk.aggregate_risk_score >= 0.3 THEN 'MEDIUM'
        ELSE 'LOW'
    END AS risk_level,
    'HIPAA §164.308(a)(6)(ii)' AS requirement,
    'Incident Response' AS requirement_domain,
    CURRENT_TIMESTAMP AS report_generated_at
FROM (
    SELECT * FROM mfa_compliance
    UNION ALL
    SELECT * FROM edr_coverage
    UNION ALL
    SELECT * FROM siem_coverage
) ctrl
LEFT JOIN risk_assessment risk
    ON ctrl.check_timestamp = risk.check_timestamp
ORDER BY ctrl.check_timestamp DESC, ctrl.control_code
```

---

## **The Complete System Query Flow**

Here's how a user interaction flows through your tables:

```
USER: "Help me build detection for HIPAA breach response"

┌─────────────────────────────────────────────────────────────┐
│ STEP 1: Query Framework & Requirement                      │
└─────────────────────────────────────────────────────────────┘
SELECT * FROM requirements 
WHERE requirement_code = '164.308(a)(6)(ii)'
  AND framework_id = 'hipaa'
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 2: Find Relevant Controls via requirement_controls    │
└─────────────────────────────────────────────────────────────┘
SELECT c.* FROM controls c
JOIN requirement_controls rc ON c.id = rc.control_id
WHERE rc.requirement_id = 'hipaa__164_308_a__6__ii'
                        ↓
        Returns: AM-5, IR-8, AU-12
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 3: Find Risks via risk_controls bridge                │
└─────────────────────────────────────────────────────────────┘
SELECT r.*, rc.mitigation_strength
FROM risks r
JOIN risk_controls rc ON r.id = rc.risk_id
WHERE rc.control_id IN ('AM-5', 'IR-8', 'AU-12')
                        ↓
        Returns: HIPAA-RISK-023, HIPAA-RISK-041, HIPAA-RISK-067
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 4: Get Attack Scenarios via scenario_controls         │
└─────────────────────────────────────────────────────────────┘
SELECT s.* FROM scenarios s
JOIN scenario_controls sc ON s.id = sc.scenario_id
WHERE sc.control_id IN ('AM-5', 'IR-8', 'AU-12')
                        ↓
        Returns: HIPAA-SCENARIO-012, -034, -089
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 5: Get Test Cases for Validation                      │
└─────────────────────────────────────────────────────────────┘
SELECT * FROM test_cases
WHERE control_id IN ('AM-5', 'IR-8', 'AU-12')
                        ↓
        Returns: TEST-AM-5-001, TEST-IR-8-001, TEST-AU-12-001
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 6: AI GENERATES ARTIFACTS                             │
└─────────────────────────────────────────────────────────────┘
    ┌──────────────────────┬───────────────────────┐
    │                      │                       │
    ▼                      ▼                       ▼
SIEM Rules          Playbooks            Test Scripts
(Splunk SPL)        (Markdown)           (Python)
    │                      │                       │
    └──────────────────────┴───────────────────────┘
                        ↓
            DEPLOYED TO PRODUCTION
```

---

## **Why This Is Powerful**

1. **Single Source of Truth**: Compliance requirement → operational artifact is fully traceable
2. **Auto-Updated**: When a control changes in the KB, all downstream artifacts regenerate
3. **Audit-Ready**: Every SIEM rule cites the exact HIPAA requirement it implements
4. **Testable**: Every playbook has corresponding automated tests
5. **Complete Loop**: Detect → Respond → Test → Monitor forms a closed cycle

Want me to design the LangGraph agent topology that orchestrates this pipeline generation, or implement the SQL query optimizer that makes the hierarchy traversal efficient?
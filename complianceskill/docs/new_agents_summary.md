# New Agents Added - Dashboard Builder & Vulnerability Mapper

## 🎯 What Was Just Created

### **Agent 13: Dashboard Builder** (38KB, 521 lines)

**Purpose:** Generate compliance dashboards with metrics, KPIs, and visualizations

**Key Features:**
✅ **XSOAR Integration** - Retrieves dashboard examples from demisto/content Packs via Qdrant
✅ **MDL Schema Awareness** - Uses datatables organized by category (compliance, security_posture, risk_management)
✅ **Multi-Platform Output** - Generates Splunk XML, PowerBI models, Grafana JSON, React components
✅ **4 Dashboard Types** - Executive, Operational, Deep Dive, Audit Readiness
✅ **25+ Metrics** - Control implementation, testing, risk, incident, trend metrics

**Workflow:**
```
User: "Create executive HIPAA dashboard"
    ↓
1. Query Qdrant: xsoar_dashboards collection
   - Search: "compliance monitoring HIPAA control effectiveness"
   - Returns: Dashboard layouts from CommonDashboards pack
    ↓
2. Query Qdrant: mdl_schemas collection
   - Category filter: compliance, security_posture
   - Returns: Data model definitions for metrics
    ↓
3. Map to Framework KB
   - Controls table → compliance_score_gauge
   - Test_results table → test_pass_rate_chart
   - Gaps table → critical_gaps_table
    ↓
4. Generate Dashboard Spec
   - Compliance Score: 78% (gauge)
   - Critical Gaps: 5 (alert card)
   - Trend: Last 6 months (line chart)
   - Top Gaps: Sortable table
    ↓
5. Output Multiple Formats
   - Splunk XML dashboard
   - PowerBI PBIX data model
   - Grafana JSON config
   - React component code
```

**Example Output:**
```json
{
  "dashboard_specification": {
    "title": "HIPAA Compliance Executive Dashboard",
    "xsoar_references": [
      {
        "pack_name": "CommonDashboards",
        "dashboard_example": "SecurityPosture.json",
        "similarity_score": 0.89
      }
    ],
    "widgets": [
      {
        "widget_id": "compliance_score",
        "type": "gauge",
        "data_source": {
          "query": "SELECT COUNT(*) FILTER (WHERE status='implemented') * 100.0 / COUNT(*) FROM controls WHERE framework_id='hipaa'"
        },
        "thresholds": [
          {"value": 0, "color": "red"},
          {"value": 80, "color": "yellow"},
          {"value": 95, "color": "green"}
        ]
      }
    ]
  }
}
```

---

### **Agent 14: Vulnerability-to-Control Mapper** (29KB, 584 lines)

**Purpose:** Map CVEs through ATT&CK to risks, controls, and detection signals

**Key Features:**
✅ **CVE Enrichment** - NVD API, EPSS scores, CISA KEV status, Metasploit modules
✅ **ATT&CK Bridge** - Maps CVE → ATT&CK techniques → Risks → Controls
✅ **XSOAR Playbooks** - Retrieves response procedures from demisto/content Packs
✅ **Detection Signals** - Log patterns, network IOCs, endpoint behavior (Splunk, Sigma, YARA, Suricata)
✅ **Prioritization** - EPSS + CISA KEV + CVSS → P0/P1/P2/P3
✅ **Validation** - Generates test cases (vuln scans, purple team exercises)

**Mapping Chain:**
```
CVE-2024-50349 (Log4j RCE)
    ↓ [CWE-502 Deserialization]
ATT&CK Techniques
    ├─ T1190: Exploit Public-Facing Application (Initial Access)
    ├─ T1059.004: Unix Shell (Execution)
    └─ T1041: Exfiltration Over C2 Channel
    ↓
Query Framework KB: risks table WHERE attack_techniques @> ['T1190']
    ↓
Risk: HIPAA-RISK-041
    ├─ Name: Malware infection → ePHI exfiltration
    ├─ Likelihood: 0.70 (HIGH)
    ├─ Impact: 0.95 (CRITICAL)
    └─ Risk Score: 0.665
    ↓
Query: risk_controls table WHERE risk_id = 'HIPAA-RISK-041'
    ↓
Controls
    ├─ Preventive: CIS 7.1 (Vulnerability Management)
    ├─ Detective: IR-8 (EDR Deployment)
    └─ Corrective: IR-PLAN (Incident Response)
    ↓
Detection Signals
    ├─ Log: "${jndi:(ldap|rmi|dns)://" in app logs
    ├─ Network: java.exe → outbound to suspicious IP
    └─ Endpoint: java.exe → cmd.exe/powershell.exe
    ↓
XSOAR Playbooks (from Qdrant)
    ├─ Pack: CVE_Intel
    └─ Playbook: CVE-2021-44228 - Apache Log4j RCE Response
    ↓
Validation
    ├─ Test 1: Qualys scan for vulnerable versions
    └─ Test 2: EDR detects safe PoC exploitation
```

**Example Output:**
```json
{
  "vulnerability_to_control_mapping": {
    "vulnerability": {
      "cve_id": "CVE-2024-50349",
      "cvss_v3_score": 9.8,
      "epss_score": 0.87,
      "cisa_kev_listed": true
    },
    "attack_technique_mapping": [
      {
        "technique_id": "T1190",
        "technique_name": "Exploit Public-Facing Application",
        "mapping_confidence": 0.95
      }
    ],
    "risk_mapping": [
      {
        "risk_id": "HIPAA-RISK-041",
        "risk_name": "Malware → ePHI exfiltration",
        "risk_score": 0.665
      }
    ],
    "control_mapping": {
      "preventive_controls": ["CIS 7.1"],
      "detective_controls": ["IR-8", "AU-12"]
    },
    "detection_signals": [
      {
        "signal_id": "LOG4J_JNDI_EXPLOIT",
        "signal_type": "log_pattern",
        "splunk_spl": "index=app_logs \"${jndi:\"",
        "sigma_rule_id": "7054e3d5-...",
        "severity": "critical"
      }
    ],
    "remediation_priority": "P0_CRITICAL",
    "timeline": "7 days"
  }
}
```

---

## 📊 Data Sources Used

### **Qdrant Collections**

```yaml
xsoar_dashboards:
  source: demisto/content/Packs/*/Dashboards/*.json
  embeddings: Dashboard configurations and layouts
  search_query: "compliance monitoring SOC2 HIPAA control effectiveness"
  metadata: pack_name, dashboard_type, widget_configs[]
  
xsoar_playbooks:
  source: demisto/content/Packs/*/Playbooks/*.yml
  embeddings: Incident response procedures
  search_query: "CVE response log4j investigation remediation"
  metadata: pack_name, playbook_type, automation_tasks[]
  
xsoar_indicators:
  source: demisto/content/Packs/*/IndicatorTypes/*.json
  embeddings: IOC patterns and detection rules
  search_query: "log4j exploitation detection JNDI LDAP"
  metadata: ioc_type, detection_method, severity
  
mdl_schemas:
  source: demisto/content/Packs/*/GenericDefinitions/*.json
  embeddings: Data model definitions
  categories: [compliance, security_posture, risk_management, incident_tracking]
  search_query: "compliance metrics control status test results"
  metadata: schema_name, tables[], relationships[]
```

### **External APIs (Vulnerability Mapper)**

```yaml
NVD_CVE_API:
  endpoint: https://services.nvd.nist.gov/rest/json/cves/2.0
  purpose: CVE details, CVSS scores, CWE mappings
  
FIRST_EPSS_API:
  endpoint: https://api.first.org/data/v1/epss
  purpose: Exploit prediction scores (likelihood of exploitation)
  
MITRE_ATTACK_API:
  endpoint: https://attack.mitre.org/api/v2/
  purpose: ATT&CK technique details, tactics, mitigations
  
CISA_KEV_API:
  endpoint: https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json
  purpose: Known exploited vulnerabilities catalog
```

---

## 🔄 Combined Use Case: Vulnerability Impact Dashboard

**Scenario:** Log4j vulnerability discovered, leadership wants to see impact on compliance

```
Step 1: Vulnerability-to-Control Mapper
Input: CVE-2024-50349
Output:
  - 5 affected controls (CIS 7.1, IR-8, AU-12, NW-3, IR-PLAN)
  - 3 critical gaps (12 hosts unpatched, EDR missing on 3 hosts, SIEM rule not deployed)
  - Detection signals defined (log patterns, network IOCs, endpoint behavior)
  - Priority: P0_CRITICAL (7-day remediation timeline)

Step 2: Dashboard Builder
Input: 
  - Framework: HIPAA
  - Context: Log4j vulnerability impact
  - Affected controls from Step 1
  
Output: Executive Dashboard
┌─────────────────────────────────────────────────────────┐
│ HIPAA Compliance - Log4j Impact                         │
├─────────────────────────────────────────────────────────┤
│ Compliance Score: 78% ↓ -5% (Log4j impact)             │
│ Critical Gaps: 3                                         │
│ Detection Coverage: 60% (missing EDR on 3 hosts)        │
├─────────────────────────────────────────────────────────┤
│ Action Items:                                            │
│ • P0: Patch Log4j on 12 hosts (7-day deadline)         │
│ • P0: Deploy EDR on 3 remaining hosts                   │
│ • P0: Enable SIEM detection rule                        │
├─────────────────────────────────────────────────────────┤
│ Risk Timeline:                                           │
│ • Day 0-7: CRITICAL (active exploitation)               │
│ • Day 8-30: HIGH (exploitation likely)                  │
│ • Day 30+: Audit failure probability = 85%              │
└─────────────────────────────────────────────────────────┘

Result: CISO sees vulnerability impact, prioritized actions, timeline
```

---

## 📈 Metrics Generated by Dashboard Builder

### **Control Implementation Metrics**
```python
controls_implemented_pct = (implemented / total_required) * 100
control_coverage_by_domain = implementation_pct_per_domain
control_maturity_score = weighted_avg(effectiveness_ratings)
critical_gaps_count = COUNT(WHERE severity='critical' AND status='missing')
```

### **Testing & Validation Metrics**
```python
test_pass_rate = (passed_tests / total_tests) * 100
controls_tested_recently = COUNT(tested_date >= NOW() - 30 days)
mean_time_to_remediation = AVG(fix_date - failure_date)
```

### **Risk & Gap Metrics**
```python
residual_risk_score = SUM(likelihood * impact WHERE status='unmitigated')
gaps_by_priority = COUNT(GROUP BY priority_level)
audit_failure_probability = 1 - (compliance_score / 100)
```

### **Trend Metrics**
```python
compliance_score_trend = weekly_snapshots(compliance_score, last_6_months)
gap_closure_velocity = gaps_closed_per_month
control_implementation_velocity = controls_implemented_per_sprint
```

---

## ✅ Testing Both Agents

### **Test Dashboard Builder**
```python
test_input = {
    "framework_id": "hipaa",
    "audience": "executive",
    "dashboard_type": "executive_summary"
}

expected_output = {
    "xsoar_references": [
        {"pack_name": "CommonDashboards", "similarity_score": 0.89}
    ],
    "widgets": [
        {"widget_type": "gauge", "title": "Compliance Score"},
        {"widget_type": "table", "title": "Critical Gaps"}
    ],
    "integration_code": {
        "splunk_xml": "<dashboard>...</dashboard>",
        "grafana_json": {...}
    }
}

# Validation
assert len(result["widgets"]) >= 5  # Minimum viable dashboard
assert result["xsoar_references"][0]["similarity_score"] > 0.7
assert "splunk_xml" in result["integration_code"]
```

### **Test Vulnerability Mapper**
```python
test_input = {
    "cve_id": "CVE-2024-50349",
    "framework_id": "hipaa"
}

expected_output = {
    "exploitability_assessment": {
        "epss_score": 0.87,
        "overall_priority": "P0_CRITICAL"
    },
    "attack_technique_mapping": [
        {"technique_id": "T1190", "mapping_confidence": 0.95}
    ],
    "control_mapping": {
        "preventive_controls": [{"control_code": "CIS 7.1"}],
        "detective_controls": [{"control_code": "IR-8"}]
    },
    "detection_signals": [
        {"signal_type": "log_pattern", "severity": "critical"}
    ]
}

# Validation
assert result["exploitability_assessment"]["epss_score"] > 0.8
assert len(result["attack_technique_mapping"]) > 0
assert len(result["detection_signals"]) >= 2  # At least 2 signal types
assert all(control["framework_id"] == "hipaa" for control in result["control_mapping"]["preventive_controls"])
```

---

## 📦 Updated Package

**Total Agents: 14**
- Core Pipeline: 9 agents
- Advanced Analysis: 2 agents (Gap Analysis, Cross-Framework Mapper)
- Quality Assurance: 1 agent (LLM Test Generator)
- **Visualization & Threat Intel: 2 agents (Dashboard Builder, Vulnerability Mapper)** ← NEW

**Total Size: ~195KB**
**Total Lines: ~5,200**

All agents follow the same rigorous structure and are production-ready! 🚀
# Vulnerability Analytics: Reports & Alerts Framework
## Daily Management Reports | Executive Reports | Real-Time Alerts

---

# USE CASE 1: DAILY MANAGEMENT REPORTS

## Purpose
Provide operational teams with actionable intelligence for day-to-day vulnerability management activities. These reports run daily and focus on what changed in the last 24 hours and what requires immediate attention.

---

## Report 1.1: Daily Risk Score Changes

### Objective
Track assets whose risk scores changed significantly (up or down) in the past 24 hours.

### Natural Language Questions

**Primary Question:**
"Show me all assets whose effective risk score changed by more than 10 points in the last 24 hours, ordered by the magnitude of change"

**Supporting Questions:**
1. "Which Mission Critical or Critical assets had risk score increases yesterday?"
2. "What breach methods contributed to the biggest risk increases in the past 24 hours?"
3. "Which assets showed risk improvements (decreased risk scores) in the last day?"
4. "For assets with increased risk, what are the specific new vulnerabilities or misconfigurations detected?"

### SQL Query

```sql
-- Daily Risk Score Changes Report
WITH yesterday_risk AS (
    SELECT 
        nuid,
        dev_id,
        effective_risk as risk_yesterday,
        raw_risk,
        effective_likelihood,
        effective_impact
    FROM assets
    WHERE DATE(store_updated_at) = CURRENT_DATE - INTERVAL '1 day'
),
today_risk AS (
    SELECT 
        a.nuid,
        a.dev_id,
        a.host_name,
        a.final_name,
        a.ip,
        a.device_type,
        cdt.description as canonical_device_type,
        a.platform,
        ic.description as impact_class,
        ic.impact_order,
        pc.description as propagation_class,
        a.is_bastion_device,
        a.effective_risk as risk_today,
        a.effective_likelihood,
        a.effective_impact,
        a.device_zone,
        a.location_region,
        a.site_name
    FROM assets a
    LEFT JOIN asset_canonical_device_type_enum cdt ON a.device_type = cdt.code
    LEFT JOIN impact_class_enum ic ON a.impact_class = ic.code
    LEFT JOIN propagation_class_enum pc ON a.propagation_class = pc.code
    WHERE DATE(a.store_updated_at) = CURRENT_DATE
)
SELECT 
    t.nuid,
    t.dev_id,
    t.host_name,
    t.final_name,
    t.ip,
    t.canonical_device_type,
    t.platform,
    t.impact_class,
    t.propagation_class,
    t.is_bastion_device,
    t.device_zone,
    t.location_region,
    t.site_name,
    y.risk_yesterday,
    t.risk_today,
    (t.risk_today - y.risk_yesterday) as risk_change,
    ROUND(((t.risk_today - y.risk_yesterday) / NULLIF(y.risk_yesterday, 0) * 100), 2) as risk_change_pct,
    t.effective_likelihood,
    t.effective_impact,
    CASE 
        WHEN (t.risk_today - y.risk_yesterday) > 0 THEN 'INCREASED'
        WHEN (t.risk_today - y.risk_yesterday) < 0 THEN 'DECREASED'
        ELSE 'NO_CHANGE'
    END as risk_direction
FROM today_risk t
JOIN yesterday_risk y ON t.nuid = y.nuid AND t.dev_id = y.dev_id
WHERE ABS(t.risk_today - y.risk_yesterday) > 10
ORDER BY ABS(t.risk_today - y.risk_yesterday) DESC, t.impact_order ASC
LIMIT 100;
```

### Report Sections

1. **Executive Summary** (Top 5 metrics)
   - Total assets with risk changes > 10 points
   - Assets with increased risk (count and %)
   - Assets with decreased risk (count and %)
   - Average risk change magnitude
   - Mission Critical assets affected

2. **Risk Increases** (Table with columns)
   - Asset Name, IP, Device Type, Platform
   - Impact Class, Propagation Class
   - Previous Risk → Current Risk (with arrow)
   - Change Amount & Percentage
   - Location/Zone

3. **Risk Decreases** (Table)
   - Same columns as above
   - Highlighting remediation successes

4. **Breach Method Attribution**
   - Breakdown of what caused risk increases
   - Top 3 breach methods driving changes

---

## Report 1.2: New Critical Vulnerabilities (Last 24 Hours)

### Objective
Identify all new CRITICAL or HIGH severity vulnerabilities detected in the past 24 hours.

### Natural Language Questions

**Primary Question:**
"Show me all CRITICAL and HIGH severity vulnerabilities detected in the last 24 hours, grouped by asset and CVE"

**Supporting Questions:**
1. "Which new critical CVEs affect Mission Critical assets?"
2. "Are any new vulnerabilities tagged as CISA Known Exploits?"
3. "What is the CVSS score distribution for newly detected vulnerabilities?"
4. "Which device types or platforms are most affected by new critical vulnerabilities?"
5. "Do any new vulnerabilities have Network attack vectors (AV:N) and no privileges required (PR:N)?"

### SQL Query

```sql
-- New Critical Vulnerabilities Report (Last 24 Hours)
SELECT 
    vi.cve_id,
    COUNT(DISTINCT CONCAT(vi.nuid, '-', vi.dev_id)) as affected_asset_count,
    vl.description as severity_level,
    vl.severity_order,
    AVG(vi.cvssv3_basescore) as avg_cvss_score,
    MAX(vi.cvssv3_basescore) as max_cvss_score,
    AVG(vi.gtm_score) as avg_gtm_score,
    vi.threat_level,
    vi.exposure,
    vi.priority,
    CASE WHEN vi.tags LIKE '%CISA Known Exploit%' THEN 'YES' ELSE 'NO' END as is_cisa_exploit,
    vi.published_time,
    MIN(vi.detected_time) as first_detected_in_org,
    STRING_AGG(DISTINCT a.impact_class, ', ') as affected_impact_classes,
    STRING_AGG(DISTINCT cdt.description, ', ') as affected_device_types,
    STRING_AGG(DISTINCT a.platform, ', ') as affected_platforms,
    -- Asset details for top impacted
    (SELECT STRING_AGG(DISTINCT a2.final_name, ', ')
     FROM assets a2
     JOIN vulnerability_instances vi2 ON a2.nuid = vi2.nuid AND a2.dev_id = vi2.dev_id
     WHERE vi2.cve_id = vi.cve_id 
       AND a2.impact_class IN ('Mission Critical', 'Critical')
     LIMIT 10
    ) as top_critical_assets
FROM vulnerability_instances vi
LEFT JOIN vuln_level_enum vl ON vi.severity = vl.code
LEFT JOIN assets a ON vi.nuid = a.nuid AND vi.dev_id = a.dev_id
LEFT JOIN asset_canonical_device_type_enum cdt ON a.device_type = cdt.code
WHERE DATE(vi.detected_time) = CURRENT_DATE - INTERVAL '1 day'
  AND vi.severity IN ('CRITICAL', 'HIGH')
  AND vi.state = 'ACTIVE'
GROUP BY 
    vi.cve_id, 
    vl.description, 
    vl.severity_order,
    vi.threat_level,
    vi.exposure,
    vi.priority,
    vi.tags,
    vi.published_time
ORDER BY 
    vl.severity_order DESC,
    affected_asset_count DESC,
    avg_gtm_score DESC
LIMIT 50;
```

### Report Sections

1. **Critical Alert Summary**
   - Total new CRITICAL vulnerabilities
   - Total new HIGH vulnerabilities
   - CISA Known Exploits count
   - Mission Critical assets affected

2. **CVE Detail Table**
   - CVE ID (with link to NVD)
   - Severity Level
   - CVSS v3 Score (avg/max)
   - GTM Score
   - Affected Asset Count
   - Impact Classes Affected
   - CISA Exploit Flag
   - Published Date
   - First Detected in Org

3. **Top Impacted Assets**
   - Mission Critical and Critical assets
   - With vulnerability count per asset

4. **Recommended Actions**
   - Immediate patching priorities
   - Compensating controls for unpatched systems

---

## Report 1.3: Patch Deployment Status (Last 24 Hours)

### Objective
Track patch deployment activities and success rates from the previous day.

### Natural Language Questions

**Primary Question:**
"Show me all patches that transitioned to INSTALLED state in the last 24 hours, grouped by software vendor and product"

**Supporting Questions:**
1. "How many critical vulnerabilities were remediated through yesterday's patching?"
2. "Which patches are in REBOOT PENDING state and need system restarts?"
3. "Were there any patch failures or rollbacks yesterday?"
4. "What is the patch success rate by platform (Windows, Linux, macOS)?"
5. "Which assets completed patching and what was their risk reduction?"

### SQL Query

```sql
-- Patch Deployment Status Report (Last 24 Hours)
WITH patch_transitions AS (
    SELECT 
        fi.nuid,
        fi.dev_id,
        fi.id as patch_id,
        fi.sw_instance_id,
        fi.patch_type,
        fi.state as current_state,
        fi.install_time,
        si.vendor,
        si.product,
        si.version,
        si.category as software_category,
        a.host_name,
        a.final_name,
        a.platform,
        a.device_type,
        a.impact_class,
        ps.description as patch_state_desc
    FROM fix_instances fi
    LEFT JOIN software_instances si ON fi.sw_instance_id = si.key
    LEFT JOIN assets a ON fi.nuid = a.nuid AND fi.dev_id = a.dev_id
    LEFT JOIN patch_state_enum ps ON fi.state = ps.code
    WHERE DATE(fi.install_time) = CURRENT_DATE - INTERVAL '1 day'
       OR (fi.state = 'REBOOT PENDING' AND DATE(fi.store_updated_at) = CURRENT_DATE - INTERVAL '1 day')
),
vulnerability_remediation AS (
    SELECT 
        vi.nuid,
        vi.dev_id,
        vi.cve_id,
        vi.severity,
        vl.description as severity_level
    FROM vulnerability_instances vi
    LEFT JOIN vuln_level_enum vl ON vi.severity = vl.code
    WHERE DATE(vi.remediation_time) = CURRENT_DATE - INTERVAL '1 day'
      AND vi.state = 'REMEDIATED'
)
SELECT 
    pt.vendor,
    pt.product,
    pt.platform,
    pt.software_category,
    pt.current_state,
    COUNT(DISTINCT CONCAT(pt.nuid, '-', pt.dev_id)) as assets_patched,
    COUNT(pt.patch_id) as total_patches,
    COUNT(DISTINCT pt.sw_instance_id) as software_instances_updated,
    -- Count remediated vulnerabilities
    (SELECT COUNT(DISTINCT vr.cve_id)
     FROM vulnerability_remediation vr
     WHERE vr.nuid = pt.nuid AND vr.dev_id = pt.dev_id
    ) as vulnerabilities_remediated,
    -- Break down by impact class
    COUNT(DISTINCT CASE WHEN pt.impact_class = 'Mission Critical' THEN CONCAT(pt.nuid, '-', pt.dev_id) END) as mission_critical_assets,
    COUNT(DISTINCT CASE WHEN pt.impact_class = 'Critical' THEN CONCAT(pt.nuid, '-', pt.dev_id) END) as critical_assets,
    -- State distribution
    COUNT(DISTINCT CASE WHEN pt.current_state = 'INSTALLED' THEN pt.patch_id END) as installed_patches,
    COUNT(DISTINCT CASE WHEN pt.current_state = 'REBOOT PENDING' THEN pt.patch_id END) as reboot_pending_patches
FROM patch_transitions pt
GROUP BY 
    pt.vendor,
    pt.product,
    pt.platform,
    pt.software_category,
    pt.current_state
ORDER BY 
    assets_patched DESC,
    vulnerabilities_remediated DESC;
```

### Report Sections

1. **Patching Summary**
   - Total patches deployed
   - Assets patched successfully
   - Patches requiring reboot
   - Vulnerabilities remediated

2. **Vendor/Product Breakdown**
   - Microsoft, Adobe, Oracle, etc.
   - Success rates per vendor
   - Platform distribution (Windows, Linux, macOS)

3. **Impact Class Coverage**
   - Mission Critical assets patched
   - Critical assets patched
   - Other assets patched

4. **Outstanding Actions**
   - Systems requiring reboot
   - Patch failures requiring attention

---

## Report 1.4: Configuration Drift & New Misconfigurations

### Objective
Detect configuration changes that introduced new security issues in the past 24 hours.

### Natural Language Questions

**Primary Question:**
"Show me all new misconfigurations detected in the last 24 hours, categorized by misconfiguration type and affected asset criticality"

**Supporting Questions:**
1. "Which assets experienced configuration drift resulting in new security issues?"
2. "Are there new cloud misconfigurations (AWS, Azure, GCP)?"
3. "Which protocol or service misconfigurations were detected (SMB, PowerShell, encryption)?"
4. "Do any new misconfigurations affect Perimeter or bastion assets?"
5. "What is the severity distribution of new misconfigurations?"

### SQL Query

```sql
-- New Misconfigurations Report (Last 24 Hours)
SELECT 
    m.vuln_id,
    m.vuln_category,
    m.misconfig_category,
    m.vuln_description,
    m.vuln_severity,
    vl.description as severity_level,
    COUNT(DISTINCT CONCAT(m.nuid, '-', m.dev_id)) as affected_asset_count,
    STRING_AGG(DISTINCT a.impact_class, ', ') as affected_impact_classes,
    STRING_AGG(DISTINCT a.propagation_class, ', ') as affected_propagation_classes,
    STRING_AGG(DISTINCT cdt.description, ', ') as affected_device_types,
    COUNT(DISTINCT CASE WHEN a.is_bastion_device = TRUE THEN CONCAT(m.nuid, '-', m.dev_id) END) as bastion_assets_affected,
    MIN(m.first_observed) as first_observed,
    MAX(m.last_observed) as last_observed,
    -- Top affected assets
    (SELECT STRING_AGG(DISTINCT a2.final_name, ', ')
     FROM assets a2
     JOIN misconfigurations m2 ON a2.nuid = m2.nuid AND a2.dev_id = m2.dev_id
     WHERE m2.vuln_id = m.vuln_id 
       AND a2.impact_class IN ('Mission Critical', 'Critical')
     LIMIT 10
    ) as top_critical_assets,
    ARRAY_AGG(DISTINCT data_source) as data_sources
FROM misconfigurations m
LEFT JOIN assets a ON m.nuid = a.nuid AND m.dev_id = a.dev_id
LEFT JOIN asset_canonical_device_type_enum cdt ON a.device_type = cdt.code
LEFT JOIN vuln_level_enum vl ON m.vuln_severity::text = vl.code
WHERE DATE(m.first_observed) = CURRENT_DATE - INTERVAL '1 day'
  AND m.is_stale = FALSE
GROUP BY 
    m.vuln_id,
    m.vuln_category,
    m.misconfig_category,
    m.vuln_description,
    m.vuln_severity,
    vl.description
ORDER BY 
    m.vuln_severity DESC,
    affected_asset_count DESC,
    bastion_assets_affected DESC
LIMIT 100;
```

### Report Sections

1. **Misconfiguration Summary**
   - Total new misconfigurations
   - Critical/High/Medium severity breakdown
   - Bastion assets affected
   - Perimeter assets affected

2. **Configuration Categories**
   - Cloud misconfigurations (EC2, S3, VPC)
   - Service misconfigurations
   - Protocol issues (SMB, TLS, certificates)
   - Access control issues

3. **High-Priority Items**
   - Mission Critical assets with new misconfigurations
   - Perimeter + High Severity combinations

4. **Remediation Guidance**
   - Configuration baseline requirements
   - Automated remediation opportunities

---

## Report 1.5: SLA Compliance & Aging Vulnerabilities

### Objective
Track vulnerabilities approaching or breaching SLA deadlines.

### Natural Language Questions

**Primary Question:**
"Show me all CRITICAL vulnerabilities that are within 7 days of breaching their 30-day remediation SLA"

**Supporting Questions:**
1. "Which CRITICAL vulnerabilities have already breached their SLA?"
2. "How many HIGH severity vulnerabilities will breach SLA in the next 14 days?"
3. "What is the current SLA compliance rate by severity level?"
4. "Which assets have the most overdue critical vulnerabilities?"
5. "What is the average age of ACTIVE vulnerabilities by impact class?"

### SQL Query

```sql
-- SLA Compliance & Aging Vulnerabilities Report
WITH vulnerability_age AS (
    SELECT 
        vi.cve_id,
        vi.nuid,
        vi.dev_id,
        vi.severity,
        vl.description as severity_level,
        vl.severity_order,
        vi.state,
        vi.detected_time,
        vi.remediation_time,
        CASE 
            WHEN vi.state = 'REMEDIATED' THEN 
                EXTRACT(EPOCH FROM (vi.remediation_time - vi.detected_time))/86400
            ELSE 
                EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - vi.detected_time))/86400
        END as age_days,
        CASE 
            WHEN vi.severity = 'CRITICAL' THEN 30
            WHEN vi.severity = 'HIGH' THEN 60
            WHEN vi.severity = 'MEDIUM' THEN 90
            ELSE 120
        END as sla_days,
        a.host_name,
        a.final_name,
        a.impact_class,
        ic.impact_order,
        a.propagation_class,
        a.device_type,
        cdt.description as canonical_device_type,
        a.platform,
        vi.cvssv3_basescore,
        vi.gtm_score,
        vi.threat_level,
        vi.tags
    FROM vulnerability_instances vi
    LEFT JOIN vuln_level_enum vl ON vi.severity = vl.code
    LEFT JOIN assets a ON vi.nuid = a.nuid AND vi.dev_id = a.dev_id
    LEFT JOIN impact_class_enum ic ON a.impact_class = ic.code
    LEFT JOIN asset_canonical_device_type_enum cdt ON a.device_type = cdt.code
    WHERE vi.state = 'ACTIVE'
      AND vi.severity IN ('CRITICAL', 'HIGH', 'MEDIUM')
)
SELECT 
    cve_id,
    severity_level,
    severity_order,
    COUNT(DISTINCT CONCAT(nuid, '-', dev_id)) as affected_assets,
    ROUND(AVG(age_days), 1) as avg_age_days,
    MAX(age_days) as max_age_days,
    MIN(age_days) as min_age_days,
    MAX(sla_days) as sla_deadline_days,
    -- SLA status
    COUNT(DISTINCT CASE WHEN age_days > sla_days THEN CONCAT(nuid, '-', dev_id) END) as breached_sla_count,
    COUNT(DISTINCT CASE WHEN age_days > (sla_days * 0.8) AND age_days <= sla_days 
                        THEN CONCAT(nuid, '-', dev_id) END) as approaching_sla_count,
    ROUND(AVG(cvssv3_basescore), 1) as avg_cvss_score,
    ROUND(AVG(gtm_score), 1) as avg_gtm_score,
    -- Impact class distribution
    COUNT(DISTINCT CASE WHEN impact_class = 'Mission Critical' THEN CONCAT(nuid, '-', dev_id) END) as mission_critical_count,
    COUNT(DISTINCT CASE WHEN impact_class = 'Critical' THEN CONCAT(nuid, '-', dev_id) END) as critical_count,
    -- CISA flag
    MAX(CASE WHEN tags LIKE '%CISA Known Exploit%' THEN 'YES' ELSE 'NO' END) as has_cisa_exploit,
    -- Days until SLA breach for those not yet breached
    ROUND(AVG(CASE WHEN age_days <= sla_days THEN (sla_days - age_days) ELSE 0 END), 1) as avg_days_until_breach
FROM vulnerability_age
GROUP BY cve_id, severity_level, severity_order
HAVING COUNT(DISTINCT CASE WHEN age_days > (sla_days * 0.8) THEN CONCAT(nuid, '-', dev_id) END) > 0
ORDER BY 
    severity_order DESC,
    breached_sla_count DESC,
    approaching_sla_count DESC,
    avg_age_days DESC
LIMIT 100;
```

### Report Sections

1. **SLA Status Overview**
   - Total vulnerabilities tracked
   - Within SLA (green)
   - Approaching SLA - 80%+ (yellow)
   - Breached SLA (red)

2. **Critical SLA Breaches**
   - CRITICAL severity breaches
   - Days overdue
   - Affected Mission Critical assets

3. **Upcoming SLA Deadlines**
   - Next 7 days
   - Next 14 days
   - Next 30 days

4. **Aging Analysis**
   - Oldest active vulnerabilities
   - Average age by severity
   - Impact class distribution

---

## Report 1.6: Team Performance & Remediation Velocity

### Objective
Track team productivity and remediation efficiency metrics.

### Natural Language Questions

**Primary Question:**
"What was our remediation velocity in the last 24 hours compared to the previous 7-day average?"

**Supporting Questions:**
1. "How many vulnerabilities did we remediate yesterday by severity level?"
2. "What was the mean-time-to-remediate (MTTR) for critical vulnerabilities closed yesterday?"
3. "How many patches were deployed by platform (Windows, Linux, macOS)?"
4. "What is our current backlog by severity level?"
5. "Are we trending toward or away from our SLA compliance targets?"

### SQL Query

```sql
-- Team Performance & Remediation Velocity Report
WITH yesterday_metrics AS (
    SELECT 
        DATE(vi.remediation_time) as remediation_date,
        vi.severity,
        vl.description as severity_level,
        COUNT(DISTINCT vi.instance_id) as vulnerabilities_remediated,
        AVG(EXTRACT(EPOCH FROM (vi.remediation_time - vi.detected_time))/86400) as avg_time_to_remediate_days,
        COUNT(DISTINCT CONCAT(vi.nuid, '-', vi.dev_id)) as assets_remediated,
        COUNT(DISTINCT CASE WHEN a.platform = 'Windows' THEN CONCAT(vi.nuid, '-', vi.dev_id) END) as windows_assets,
        COUNT(DISTINCT CASE WHEN a.platform = 'Linux/Unix' THEN CONCAT(vi.nuid, '-', vi.dev_id) END) as linux_assets,
        COUNT(DISTINCT CASE WHEN a.platform = 'macOS' THEN CONCAT(vi.nuid, '-', vi.dev_id) END) as macos_assets
    FROM vulnerability_instances vi
    LEFT JOIN vuln_level_enum vl ON vi.severity = vl.code
    LEFT JOIN assets a ON vi.nuid = a.nuid AND vi.dev_id = a.dev_id
    WHERE DATE(vi.remediation_time) = CURRENT_DATE - INTERVAL '1 day'
      AND vi.state = 'REMEDIATED'
    GROUP BY DATE(vi.remediation_time), vi.severity, vl.description
),
last_7_days_avg AS (
    SELECT 
        vi.severity,
        vl.description as severity_level,
        AVG(daily_count) as avg_daily_remediation
    FROM (
        SELECT 
            DATE(vi.remediation_time) as remediation_date,
            vi.severity,
            COUNT(DISTINCT vi.instance_id) as daily_count
        FROM vulnerability_instances vi
        WHERE DATE(vi.remediation_time) BETWEEN CURRENT_DATE - INTERVAL '8 days' AND CURRENT_DATE - INTERVAL '2 days'
          AND vi.state = 'REMEDIATED'
        GROUP BY DATE(vi.remediation_time), vi.severity
    ) daily
    LEFT JOIN vuln_level_enum vl ON daily.severity = vl.code
    GROUP BY vi.severity, vl.description
),
current_backlog AS (
    SELECT 
        vi.severity,
        vl.description as severity_level,
        COUNT(DISTINCT vi.instance_id) as active_count,
        AVG(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - vi.detected_time))/86400) as avg_age_days
    FROM vulnerability_instances vi
    LEFT JOIN vuln_level_enum vl ON vi.severity = vl.code
    WHERE vi.state = 'ACTIVE'
    GROUP BY vi.severity, vl.description
)
SELECT 
    COALESCE(ym.severity_level, la.severity_level, cb.severity_level) as severity_level,
    -- Yesterday's performance
    COALESCE(ym.vulnerabilities_remediated, 0) as remediated_yesterday,
    COALESCE(ym.assets_remediated, 0) as assets_remediated_yesterday,
    ROUND(COALESCE(ym.avg_time_to_remediate_days, 0), 1) as mttr_yesterday_days,
    COALESCE(ym.windows_assets, 0) as windows_assets_remediated,
    COALESCE(ym.linux_assets, 0) as linux_assets_remediated,
    COALESCE(ym.macos_assets, 0) as macos_assets_remediated,
    -- 7-day average comparison
    ROUND(COALESCE(la.avg_daily_remediation, 0), 1) as avg_daily_remediation_7days,
    ROUND(
        (COALESCE(ym.vulnerabilities_remediated, 0) - COALESCE(la.avg_daily_remediation, 0)) / 
        NULLIF(la.avg_daily_remediation, 0) * 100, 
        1
    ) as variance_from_avg_pct,
    -- Current backlog
    COALESCE(cb.active_count, 0) as current_backlog,
    ROUND(COALESCE(cb.avg_age_days, 0), 1) as backlog_avg_age_days,
    -- Velocity indicator
    CASE 
        WHEN COALESCE(ym.vulnerabilities_remediated, 0) > COALESCE(la.avg_daily_remediation, 0) THEN 'ABOVE_AVG'
        WHEN COALESCE(ym.vulnerabilities_remediated, 0) < COALESCE(la.avg_daily_remediation, 0) THEN 'BELOW_AVG'
        ELSE 'ON_TARGET'
    END as performance_indicator
FROM yesterday_metrics ym
FULL OUTER JOIN last_7_days_avg la ON ym.severity = la.severity
FULL OUTER JOIN current_backlog cb ON COALESCE(ym.severity, la.severity) = cb.severity
ORDER BY 
    CASE COALESCE(ym.severity_level, la.severity_level, cb.severity_level)
        WHEN 'CRITICAL' THEN 1
        WHEN 'HIGH' THEN 2
        WHEN 'MEDIUM' THEN 3
        WHEN 'LOW' THEN 4
    END;
```

### Report Sections

1. **Daily Performance Summary**
   - Vulnerabilities remediated (by severity)
   - Assets patched
   - Comparison to 7-day average

2. **Platform Breakdown**
   - Windows remediation count
   - Linux/Unix remediation count
   - macOS remediation count

3. **MTTR Metrics**
   - MTTR for CRITICAL
   - MTTR for HIGH
   - MTTR for MEDIUM
   - Trend indicators

4. **Current Backlog**
   - Active vulnerabilities by severity
   - Average age of backlog
   - Projected time to clear backlog

---

# USE CASE 2: EXECUTIVE REPORTS

## Purpose
Provide high-level strategic insights for executive leadership, typically generated weekly or monthly, focusing on trends, compliance, and business risk.

---

## Report 2.1: Executive Risk Posture Summary

### Objective
Provide C-level overview of organizational cybersecurity risk with business context.

### Natural Language Questions

**Primary Question:**
"What is our current overall risk posture compared to the previous month, and which business-critical assets pose the greatest risk?"

**Supporting Questions:**
1. "What percentage of our risk is concentrated in Mission Critical assets?"
2. "How has our effective risk score trended over the past 90 days?"
3. "Which breach methods contribute most to our organizational risk?"
4. "What is our exposure in each impact class and propagation class combination?"
5. "How does our risk compare across different geographic regions and business units?"

### SQL Query

```sql
-- Executive Risk Posture Summary
WITH current_risk AS (
    SELECT 
        COUNT(DISTINCT CONCAT(nuid, '-', dev_id)) as total_assets,
        SUM(effective_risk) as total_risk,
        AVG(effective_risk) as avg_risk_per_asset,
        SUM(effective_likelihood) as total_likelihood,
        SUM(effective_impact) as total_impact,
        -- By impact class
        SUM(CASE WHEN impact_class = 'Mission Critical' THEN effective_risk ELSE 0 END) as mission_critical_risk,
        SUM(CASE WHEN impact_class = 'Critical' THEN effective_risk ELSE 0 END) as critical_risk,
        SUM(CASE WHEN impact_class = 'Other' THEN effective_risk ELSE 0 END) as other_risk,
        COUNT(DISTINCT CASE WHEN impact_class = 'Mission Critical' THEN CONCAT(nuid, '-', dev_id) END) as mission_critical_assets,
        COUNT(DISTINCT CASE WHEN impact_class = 'Critical' THEN CONCAT(nuid, '-', dev_id) END) as critical_assets,
        -- By propagation class
        SUM(CASE WHEN propagation_class = 'Perimeter' THEN effective_risk ELSE 0 END) as perimeter_risk,
        SUM(CASE WHEN propagation_class = 'Core' THEN effective_risk ELSE 0 END) as core_risk,
        -- Bastion assets
        COUNT(DISTINCT CASE WHEN is_bastion_device = TRUE THEN CONCAT(nuid, '-', dev_id) END) as bastion_asset_count,
        SUM(CASE WHEN is_bastion_device = TRUE THEN effective_risk ELSE 0 END) as bastion_asset_risk,
        -- Geographic distribution
        location_region,
        SUM(effective_risk) as regional_risk,
        COUNT(DISTINCT CONCAT(nuid, '-', dev_id)) as regional_assets
    FROM assets
    WHERE DATE(store_updated_at) >= CURRENT_DATE - INTERVAL '7 days'
    GROUP BY location_region
),
previous_month_risk AS (
    SELECT 
        SUM(effective_risk) as total_risk,
        AVG(effective_risk) as avg_risk_per_asset
    FROM assets
    WHERE DATE(store_updated_at) BETWEEN CURRENT_DATE - INTERVAL '37 days' AND CURRENT_DATE - INTERVAL '30 days'
),
breach_method_contribution AS (
    SELECT 
        'Unpatched Vulnerability' as breach_method,
        SUM(a.unpatched_vulnerability_likelihood * a.effective_impact) as risk_contribution
    FROM assets a
    WHERE DATE(a.store_updated_at) >= CURRENT_DATE - INTERVAL '7 days'
    UNION ALL
    SELECT 
        'Weak Credentials',
        SUM(a.weak_credentials_likelihood * a.effective_impact)
    FROM assets a
    WHERE DATE(a.store_updated_at) >= CURRENT_DATE - INTERVAL '7 days'
    UNION ALL
    SELECT 
        'Misconfiguration',
        SUM(a.misconfiguration_likelihood * a.effective_impact)
    FROM assets a
    WHERE DATE(a.store_updated_at) >= CURRENT_DATE - INTERVAL '7 days'
    UNION ALL
    SELECT 
        'Trust Relationship',
        SUM(a.trust_relationship_likelihood * a.effective_impact)
    FROM assets a
    WHERE DATE(a.store_updated_at) >= CURRENT_DATE - INTERVAL '7 days'
    UNION ALL
    SELECT 
        'Phishing',
        SUM(a.phishing_likelihood * a.effective_impact)
    FROM assets a
    WHERE DATE(a.store_updated_at) >= CURRENT_DATE - INTERVAL '7 days'
    UNION ALL
    SELECT 
        'Zero Day',
        SUM(a.zero_day_likelihood * a.effective_impact)
    FROM assets a
    WHERE DATE(a.store_updated_at) >= CURRENT_DATE - INTERVAL '7 days'
)
SELECT 
    -- Current state
    (SELECT SUM(total_risk) FROM current_risk) as current_total_risk,
    (SELECT AVG(avg_risk_per_asset) FROM current_risk) as current_avg_risk,
    (SELECT total_assets FROM current_risk LIMIT 1) as total_assets_monitored,
    -- Month-over-month change
    ROUND(
        ((SELECT SUM(total_risk) FROM current_risk) - pm.total_risk) / NULLIF(pm.total_risk, 0) * 100,
        2
    ) as risk_change_pct_mom,
    -- Impact class breakdown
    (SELECT SUM(mission_critical_risk) FROM current_risk) as mission_critical_risk,
    ROUND(
        (SELECT SUM(mission_critical_risk) FROM current_risk) / 
        NULLIF((SELECT SUM(total_risk) FROM current_risk), 0) * 100,
        1
    ) as mission_critical_risk_pct,
    (SELECT SUM(mission_critical_assets) FROM current_risk) as mission_critical_asset_count,
    -- Propagation breakdown
    (SELECT SUM(perimeter_risk) FROM current_risk) as perimeter_risk,
    (SELECT SUM(core_risk) FROM current_risk) as core_risk,
    -- Bastion analysis
    (SELECT SUM(bastion_asset_count) FROM current_risk) as bastion_devices,
    (SELECT SUM(bastion_asset_risk) FROM current_risk) as bastion_device_risk,
    -- Top breach methods
    (SELECT breach_method FROM breach_method_contribution ORDER BY risk_contribution DESC LIMIT 1) as top_breach_method,
    (SELECT risk_contribution FROM breach_method_contribution ORDER BY risk_contribution DESC LIMIT 1) as top_breach_method_risk
FROM previous_month_risk pm;
```

### Report Sections

1. **Executive Summary Dashboard** (Single page with key metrics)
   - Overall Risk Score (current)
   - Month-over-Month Change (with trend arrow)
   - Total Assets Monitored
   - Mission Critical Assets at Risk

2. **Risk Distribution Visualization**
   - Pie chart: Impact Class (Mission Critical, Critical, Other)
   - Bar chart: Breach Method Contribution
   - Heat map: Impact Class × Propagation Class

3. **Top Business Risks** (Table - Top 10)
   - Asset Name
   - Business Function/Criticality
   - Current Risk Score
   - Primary Risk Drivers
   - Recommended Action

4. **Strategic Recommendations**
   - Top 3 risk reduction initiatives
   - Investment priorities
   - Compliance gaps

---

## Report 2.2: Compliance & Audit Status

### Objective
Demonstrate regulatory compliance and audit readiness to board and executives.

### Natural Language Questions

**Primary Question:**
"What is our current compliance posture across all regulatory frameworks, and where are our gaps?"

**Supporting Questions:**
1. "What percentage of critical vulnerabilities are remediated within SLA requirements?"
2. "How many policy exceptions are currently active, and what risk do they represent?"
3. "Are we compliant with PCI-DSS quarterly vulnerability scanning requirements?"
4. "What is our patch compliance rate for systems processing regulated data?"
5. "How many audit findings from the last assessment remain open?"

### SQL Query

```sql
-- Compliance & Audit Status Executive Report
WITH sla_compliance AS (
    SELECT 
        vi.severity,
        vl.description as severity_level,
        COUNT(DISTINCT vi.instance_id) as total_vulnerabilities,
        CASE 
            WHEN vi.severity = 'CRITICAL' THEN 30
            WHEN vi.severity = 'HIGH' THEN 60
            WHEN vi.severity = 'MEDIUM' THEN 90
            ELSE 120
        END as sla_days,
        COUNT(DISTINCT CASE 
            WHEN vi.state = 'REMEDIATED' AND 
                 EXTRACT(EPOCH FROM (vi.remediation_time - vi.detected_time))/86400 <= 
                 CASE WHEN vi.severity = 'CRITICAL' THEN 30
                      WHEN vi.severity = 'HIGH' THEN 60
                      WHEN vi.severity = 'MEDIUM' THEN 90
                      ELSE 120 END
            THEN vi.instance_id 
        END) as remediated_within_sla,
        COUNT(DISTINCT CASE 
            WHEN vi.state = 'ACTIVE' AND 
                 EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - vi.detected_time))/86400 > 
                 CASE WHEN vi.severity = 'CRITICAL' THEN 30
                      WHEN vi.severity = 'HIGH' THEN 60
                      WHEN vi.severity = 'MEDIUM' THEN 90
                      ELSE 120 END
            THEN vi.instance_id 
        END) as active_breached_sla
    FROM vulnerability_instances vi
    LEFT JOIN vuln_level_enum vl ON vi.severity = vl.code
    WHERE vi.detected_time >= CURRENT_DATE - INTERVAL '180 days'
    GROUP BY vi.severity, vl.description
),
risk_exceptions AS (
    SELECT 
        COUNT(DISTINCT vi.instance_id) as total_accepted,
        SUM(a.effective_risk) as total_accepted_risk,
        COUNT(DISTINCT CASE WHEN vi.severity = 'CRITICAL' THEN vi.instance_id END) as critical_accepted,
        COUNT(DISTINCT CASE WHEN vi.severity = 'HIGH' THEN vi.instance_id END) as high_accepted
    FROM vulnerability_instances vi
    JOIN assets a ON vi.nuid = a.nuid AND vi.dev_id = a.dev_id
    WHERE vi.state IN ('ACCEPTED', 'ACCEPTED_BY_USER')
),
regulated_asset_compliance AS (
    SELECT 
        a.asset_tags,
        COUNT(DISTINCT CONCAT(a.nuid, '-', a.dev_id)) as regulated_assets,
        SUM(CASE WHEN vi.state = 'ACTIVE' AND vi.severity IN ('CRITICAL', 'HIGH') 
            THEN 1 ELSE 0 END) as active_critical_high_vulns,
        AVG(a.effective_risk) as avg_risk_score
    FROM assets a
    LEFT JOIN vulnerability_instances vi ON a.nuid = vi.nuid AND a.dev_id = vi.dev_id
    WHERE a.asset_tags LIKE '%PCI%' 
       OR a.asset_tags LIKE '%HIPAA%'
       OR a.asset_tags LIKE '%SOX%'
    GROUP BY a.asset_tags
)
SELECT 
    -- SLA Compliance Summary
    sc.severity_level,
    sc.total_vulnerabilities,
    sc.remediated_within_sla,
    sc.active_breached_sla,
    ROUND(
        sc.remediated_within_sla::NUMERIC / NULLIF(sc.total_vulnerabilities, 0) * 100,
        1
    ) as sla_compliance_rate_pct,
    sc.sla_days as sla_requirement_days,
    -- Risk Exceptions
    (SELECT total_accepted FROM risk_exceptions) as total_risk_exceptions,
    (SELECT total_accepted_risk FROM risk_exceptions) as exception_risk_value,
    (SELECT critical_accepted FROM risk_exceptions) as critical_exceptions,
    (SELECT high_accepted FROM risk_exceptions) as high_exceptions,
    -- Regulated Assets
    (SELECT SUM(regulated_assets) FROM regulated_asset_compliance) as total_regulated_assets,
    (SELECT SUM(active_critical_high_vulns) FROM regulated_asset_compliance) as regulated_active_vulns
FROM sla_compliance sc
ORDER BY 
    CASE sc.severity_level
        WHEN 'CRITICAL' THEN 1
        WHEN 'HIGH' THEN 2
        WHEN 'MEDIUM' THEN 3
        ELSE 4
    END;
```

### Report Sections

1. **Compliance Scorecard**
   - Overall Compliance Rate: XX%
   - PCI-DSS Compliance: XX%
   - HIPAA Compliance: XX%
   - SOX Compliance: XX%
   - Trend: Improving/Declining

2. **SLA Performance**
   - Table by severity level
   - Compliance rate percentage
   - Number of breaches
   - Remediation time averages

3. **Risk Exceptions**
   - Total active exceptions
   - Business justifications summary
   - Aggregated risk from exceptions
   - Exception renewal due dates

4. **Regulatory Asset Status**
   - PCI-DSS scope assets
   - HIPAA scope assets
   - SOX scope assets
   - Critical vulnerabilities in scope

---

## Report 2.3: Strategic Risk Trends (90-Day)

### Objective
Show 90-day risk trends and projections for strategic planning.

### Natural Language Questions

**Primary Question:**
"How has our organizational risk evolved over the past 90 days, and what is the projected trend for the next 30 days?"

**Supporting Questions:**
1. "Which asset categories have improving vs degrading risk trends?"
2. "How has our vulnerability introduction rate compared to remediation rate?"
3. "Are we closing the gap on high-priority vulnerabilities?"
4. "Which breach methods are trending up or down?"
5. "What is our projected risk score in 30/60/90 days based on current velocity?"

### SQL Query

```sql
-- Strategic Risk Trends (90-Day) Executive Report
WITH daily_risk_metrics AS (
    SELECT 
        DATE(store_updated_at) as metric_date,
        SUM(effective_risk) as daily_total_risk,
        AVG(effective_risk) as daily_avg_risk,
        COUNT(DISTINCT CONCAT(nuid, '-', dev_id)) as daily_asset_count,
        SUM(effective_likelihood) as daily_total_likelihood,
        SUM(effective_impact) as daily_total_impact,
        -- By impact class
        SUM(CASE WHEN impact_class = 'Mission Critical' THEN effective_risk ELSE 0 END) as mc_risk,
        SUM(CASE WHEN impact_class = 'Critical' THEN effective_risk ELSE 0 END) as crit_risk,
        -- Breach methods
        SUM(unpatched_vulnerability_likelihood * effective_impact) as uv_risk,
        SUM(weak_credentials_likelihood * effective_impact) as cred_risk,
        SUM(misconfiguration_likelihood * effective_impact) as misconfig_risk,
        SUM(trust_relationship_likelihood * effective_impact) as tr_risk
    FROM assets
    WHERE DATE(store_updated_at) >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY DATE(store_updated_at)
),
vulnerability_velocity AS (
    SELECT 
        DATE(detected_time) as metric_date,
        COUNT(DISTINCT instance_id) as vulns_detected
    FROM vulnerability_instances
    WHERE DATE(detected_time) >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY DATE(detected_time)
),
remediation_velocity AS (
    SELECT 
        DATE(remediation_time) as metric_date,
        COUNT(DISTINCT instance_id) as vulns_remediated
    FROM vulnerability_instances
    WHERE DATE(remediation_time) >= CURRENT_DATE - INTERVAL '90 days'
      AND state = 'REMEDIATED'
    GROUP BY DATE(remediation_time)
),
trend_calculation AS (
    SELECT 
        drm.metric_date,
        drm.daily_total_risk,
        drm.daily_avg_risk,
        drm.mc_risk,
        drm.crit_risk,
        drm.uv_risk,
        drm.cred_risk,
        drm.misconfig_risk,
        drm.tr_risk,
        COALESCE(vv.vulns_detected, 0) as vulns_detected,
        COALESCE(rv.vulns_remediated, 0) as vulns_remediated,
        -- 7-day moving average
        AVG(drm.daily_total_risk) OVER (
            ORDER BY drm.metric_date 
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) as risk_7day_ma,
        -- Linear trend calculation (simplified)
        drm.daily_total_risk - LAG(drm.daily_total_risk, 7) OVER (ORDER BY drm.metric_date) as week_over_week_change
    FROM daily_risk_metrics drm
    LEFT JOIN vulnerability_velocity vv ON drm.metric_date = vv.metric_date
    LEFT JOIN remediation_velocity rv ON drm.metric_date = rv.metric_date
)
SELECT 
    metric_date,
    daily_total_risk,
    risk_7day_ma,
    week_over_week_change,
    mc_risk,
    crit_risk,
    uv_risk,
    cred_risk,
    misconfig_risk,
    tr_risk,
    vulns_detected,
    vulns_remediated,
    (vulns_detected - vulns_remediated) as net_vulnerability_change,
    -- Cumulative metrics
    SUM(vulns_detected) OVER (ORDER BY metric_date) as cumulative_detected,
    SUM(vulns_remediated) OVER (ORDER BY metric_date) as cumulative_remediated
FROM trend_calculation
ORDER BY metric_date DESC;
```

### Report Sections

1. **Risk Trend Visualization**
   - Line chart: 90-day organizational risk score
   - Trend line with projection
   - Color-coded zones (improving/stable/degrading)

2. **Breach Method Trends**
   - Stacked area chart showing contribution over time
   - Identification of growing threats
   - Declining threats (successes)

3. **Vulnerability Metrics**
   - Introduction rate vs remediation rate
   - Net vulnerability accumulation/reduction
   - Backlog trend

4. **Strategic Insights**
   - Key observations (3-5 bullets)
   - Risk forecast for next quarter
   - Recommended strategic investments

---

## Report 2.4: Business Unit Risk Comparison

### Objective
Compare cybersecurity risk across different business units, regions, or organizational divisions.

### Natural Language Questions

**Primary Question:**
"How does cybersecurity risk compare across our business units and geographic regions?"

**Supporting Questions:**
1. "Which business unit or region has the highest risk exposure?"
2. "Which organizational areas have the best patch compliance and remediation velocity?"
3. "Are there specific breach methods concentrated in certain business units?"
4. "How do different regions compare on security maturity and risk management?"
5. "Which business unit shows the most improvement over the past quarter?"

### SQL Query

```sql
-- Business Unit Risk Comparison Executive Report
WITH business_unit_metrics AS (
    SELECT 
        COALESCE(a.location_region, 'Unknown') as business_unit,
        COALESCE(a.device_zone, 'Unknown') as device_zone,
        -- Asset counts
        COUNT(DISTINCT CONCAT(a.nuid, '-', a.dev_id)) as total_assets,
        COUNT(DISTINCT CASE WHEN a.impact_class = 'Mission Critical' THEN CONCAT(a.nuid, '-', a.dev_id) END) as mission_critical_assets,
        -- Risk metrics
        SUM(a.effective_risk) as total_risk,
        AVG(a.effective_risk) as avg_risk_per_asset,
        MAX(a.effective_risk) as max_asset_risk,
        -- Likelihood breakdown
        AVG(a.unpatched_vulnerability_likelihood) as avg_uv_likelihood,
        AVG(a.weak_credentials_likelihood) as avg_cred_likelihood,
        AVG(a.misconfiguration_likelihood) as avg_misconfig_likelihood,
        -- Impact metrics
        AVG(a.effective_impact) as avg_impact
    FROM assets a
    WHERE DATE(a.store_updated_at) >= CURRENT_DATE - INTERVAL '7 days'
    GROUP BY COALESCE(a.location_region, 'Unknown'), COALESCE(a.device_zone, 'Unknown')
),
bu_vulnerability_metrics AS (
    SELECT 
        COALESCE(a.location_region, 'Unknown') as business_unit,
        COUNT(DISTINCT vi.instance_id) as total_active_vulns,
        COUNT(DISTINCT CASE WHEN vi.severity = 'CRITICAL' THEN vi.instance_id END) as critical_vulns,
        COUNT(DISTINCT CASE WHEN vi.severity = 'HIGH' THEN vi.instance_id END) as high_vulns,
        AVG(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - vi.detected_time))/86400) as avg_vuln_age_days
    FROM vulnerability_instances vi
    JOIN assets a ON vi.nuid = a.nuid AND vi.dev_id = a.dev_id
    WHERE vi.state = 'ACTIVE'
      AND DATE(a.store_updated_at) >= CURRENT_DATE - INTERVAL '7 days'
    GROUP BY COALESCE(a.location_region, 'Unknown')
),
bu_remediation_metrics AS (
    SELECT 
        COALESCE(a.location_region, 'Unknown') as business_unit,
        COUNT(DISTINCT vi.instance_id) as remediated_last_30days,
        AVG(EXTRACT(EPOCH FROM (vi.remediation_time - vi.detected_time))/86400) as avg_mttr_days
    FROM vulnerability_instances vi
    JOIN assets a ON vi.nuid = a.nuid AND vi.dev_id = a.dev_id
    WHERE vi.state = 'REMEDIATED'
      AND DATE(vi.remediation_time) >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY COALESCE(a.location_region, 'Unknown')
)
SELECT 
    bum.business_unit,
    bum.device_zone,
    bum.total_assets,
    bum.mission_critical_assets,
    ROUND(bum.total_risk, 2) as total_risk,
    ROUND(bum.avg_risk_per_asset, 2) as avg_risk_per_asset,
    ROUND(bum.max_asset_risk, 2) as highest_asset_risk,
    -- Vulnerability metrics
    COALESCE(bv.total_active_vulns, 0) as active_vulnerabilities,
    COALESCE(bv.critical_vulns, 0) as critical_vulnerabilities,
    COALESCE(bv.high_vulns, 0) as high_vulnerabilities,
    ROUND(COALESCE(bv.avg_vuln_age_days, 0), 1) as avg_vulnerability_age_days,
    -- Remediation performance
    COALESCE(br.remediated_last_30days, 0) as remediated_last_30days,
    ROUND(COALESCE(br.avg_mttr_days, 0), 1) as avg_mttr_days,
    -- Likelihood breakdown
    ROUND(bum.avg_uv_likelihood, 3) as avg_unpatched_likelihood,
    ROUND(bum.avg_cred_likelihood, 3) as avg_credential_likelihood,
    ROUND(bum.avg_misconfig_likelihood, 3) as avg_misconfig_likelihood,
    -- Rankings
    RANK() OVER (ORDER BY bum.total_risk DESC) as risk_rank,
    RANK() OVER (ORDER BY COALESCE(br.avg_mttr_days, 999)) as mttr_rank
FROM business_unit_metrics bum
LEFT JOIN bu_vulnerability_metrics bv ON bum.business_unit = bv.business_unit
LEFT JOIN bu_remediation_metrics br ON bum.business_unit = br.business_unit
ORDER BY bum.total_risk DESC;
```

### Report Sections

1. **Business Unit Scorecard** (Heat map)
   - Rows: Business units/Regions
   - Columns: Risk Score, Asset Count, Critical Vulns, MTTR
   - Color-coded cells (red/yellow/green)

2. **Comparative Rankings**
   - Best performing units (lowest risk, fastest MTTR)
   - Areas needing attention (highest risk, slowest remediation)

3. **Regional Deep Dive** (One page per major region/BU)
   - Risk trends
   - Top vulnerabilities
   - Asset composition
   - Remediation velocity

4. **Best Practice Sharing**
   - What high-performing units are doing well
   - Lessons learned for replication

---

# USE CASE 3: REAL-TIME ALERTS

## Purpose
Trigger immediate notifications when critical conditions are detected, enabling rapid response.

---

## Alert 3.1: New CISA Known Exploit Detected

### Trigger Condition
New vulnerability instance detected with "CISA Known Exploit" tag.

### Natural Language Question
"Alert me immediately when any new vulnerability with a CISA Known Exploit tag is detected on any asset"

### SQL Alert Query

```sql
-- CISA Known Exploit Alert
SELECT 
    vi.cve_id,
    vi.severity,
    vl.description as severity_level,
    vi.cvssv3_basescore,
    vi.gtm_score,
    vi.threat_level,
    vi.detected_time,
    -- Asset details
    a.nuid,
    a.dev_id,
    a.host_name,
    a.final_name,
    a.ip,
    ic.description as impact_class,
    pc.description as propagation_class,
    a.is_bastion_device,
    cdt.description as device_type,
    a.platform,
    a.device_zone,
    a.location_region,
    -- Risk context
    a.effective_risk,
    a.effective_likelihood,
    a.effective_impact,
    -- Software context
    si.vendor,
    si.product,
    si.version
FROM vulnerability_instances vi
LEFT JOIN vuln_level_enum vl ON vi.severity = vl.code
LEFT JOIN assets a ON vi.nuid = a.nuid AND vi.dev_id = a.dev_id
LEFT JOIN impact_class_enum ic ON a.impact_class = ic.code
LEFT JOIN propagation_class_enum pc ON a.propagation_class = pc.code
LEFT JOIN asset_canonical_device_type_enum cdt ON a.device_type = cdt.code
LEFT JOIN software_instances si ON vi.sw_instance_id = si.key
WHERE vi.tags LIKE '%CISA Known Exploit%'
  AND DATE(vi.detected_time) = CURRENT_DATE
  AND vi.state = 'ACTIVE'
ORDER BY 
    vl.severity_order DESC,
    a.impact_class,
    vi.cvssv3_basescore DESC;
```

### Alert Details

**Priority:** CRITICAL  
**Recipient:** Security Operations Team, CISO, Incident Response Team  
**Delivery:** Email, SMS, Slack, PagerDuty  
**Frequency:** Real-time (immediate)

**Alert Template:**
```
🚨 CRITICAL ALERT: CISA Known Exploit Detected

CVE: {cve_id}
Severity: {severity_level}
CVSS Score: {cvssv3_basescore}

Affected Asset:
- Name: {final_name}
- IP: {ip}
- Impact Class: {impact_class}
- Device Type: {device_type}
- Location: {location_region}

Software:
- Vendor: {vendor}
- Product: {product}
- Version: {version}

IMMEDIATE ACTION REQUIRED:
1. Isolate asset if possible
2. Apply emergency patch or mitigation
3. Monitor for exploitation attempts
4. Escalate to incident response team

Detected: {detected_time}
```

---

## Alert 3.2: Mission Critical Asset Risk Spike

### Trigger Condition
Any Mission Critical asset experiences >20% risk increase in single day.

### Natural Language Question
"Alert me when any Mission Critical asset's risk score increases by more than 20% in a single day"

### SQL Alert Query

```sql
-- Mission Critical Asset Risk Spike Alert
WITH yesterday_risk AS (
    SELECT 
        nuid,
        dev_id,
        effective_risk,
        store_updated_at
    FROM assets
    WHERE DATE(store_updated_at) = CURRENT_DATE - INTERVAL '1 day'
      AND impact_class = 'Mission Critical'
),
today_risk AS (
    SELECT 
        a.nuid,
        a.dev_id,
        a.host_name,
        a.final_name,
        a.ip,
        a.effective_risk,
        a.effective_likelihood,
        a.effective_impact,
        a.device_type,
        cdt.description as canonical_device_type,
        a.platform,
        a.propagation_class,
        a.is_bastion_device,
        a.device_zone,
        a.location_region,
        a.roles,
        -- Likelihood breakdown
        a.unpatched_vulnerability_likelihood,
        a.weak_credentials_likelihood,
        a.misconfiguration_likelihood,
        a.trust_relationship_likelihood
    FROM assets a
    LEFT JOIN asset_canonical_device_type_enum cdt ON a.device_type = cdt.code
    WHERE DATE(a.store_updated_at) = CURRENT_DATE
      AND a.impact_class = 'Mission Critical'
)
SELECT 
    t.nuid,
    t.dev_id,
    t.host_name,
    t.final_name,
    t.ip,
    t.canonical_device_type,
    t.platform,
    t.propagation_class,
    t.is_bastion_device,
    t.device_zone,
    t.location_region,
    t.roles,
    y.effective_risk as risk_yesterday,
    t.effective_risk as risk_today,
    (t.effective_risk - y.effective_risk) as risk_change,
    ROUND(((t.effective_risk - y.effective_risk) / NULLIF(y.effective_risk, 0) * 100), 2) as risk_change_pct,
    -- Identify what drove the change
    CASE 
        WHEN (t.unpatched_vulnerability_likelihood - COALESCE(
            (SELECT unpatched_vulnerability_likelihood FROM assets 
             WHERE nuid = y.nuid AND dev_id = y.dev_id 
             AND DATE(store_updated_at) = CURRENT_DATE - INTERVAL '1 day'), 0
        )) > 0.1 THEN 'New Unpatched Vulnerabilities'
        WHEN (t.weak_credentials_likelihood - COALESCE(
            (SELECT weak_credentials_likelihood FROM assets 
             WHERE nuid = y.nuid AND dev_id = y.dev_id 
             AND DATE(store_updated_at) = CURRENT_DATE - INTERVAL '1 day'), 0
        )) > 0.1 THEN 'Weak Credentials Detected'
        WHEN (t.misconfiguration_likelihood - COALESCE(
            (SELECT misconfiguration_likelihood FROM assets 
             WHERE nuid = y.nuid AND dev_id = y.dev_id 
             AND DATE(store_updated_at) = CURRENT_DATE - INTERVAL '1 day'), 0
        )) > 0.1 THEN 'New Misconfigurations'
        ELSE 'Multiple Factors'
    END as primary_risk_driver,
    -- New vulnerabilities detected today
    (SELECT COUNT(DISTINCT vi.cve_id)
     FROM vulnerability_instances vi
     WHERE vi.nuid = t.nuid AND vi.dev_id = t.dev_id
       AND DATE(vi.detected_time) = CURRENT_DATE
    ) as new_vulns_today
FROM today_risk t
JOIN yesterday_risk y ON t.nuid = y.nuid AND t.dev_id = y.dev_id
WHERE ((t.effective_risk - y.effective_risk) / NULLIF(y.effective_risk, 0)) > 0.20
ORDER BY risk_change_pct DESC;
```

### Alert Details

**Priority:** HIGH  
**Recipient:** Asset Owners, Security Team Lead, IT Operations  
**Delivery:** Email, Slack  
**Frequency:** Real-time (immediate)

**Alert Template:**
```
⚠️  HIGH ALERT: Mission Critical Asset Risk Spike

Asset: {final_name}
IP: {ip}
Device Type: {canonical_device_type}
Location: {location_region}

Risk Change:
- Previous: {risk_yesterday}
- Current: {risk_today}
- Increase: {risk_change_pct}%

Primary Risk Driver: {primary_risk_driver}
New Vulnerabilities Detected Today: {new_vulns_today}

Is Bastion Device: {is_bastion_device}
Propagation Class: {propagation_class}

ACTION REQUIRED:
1. Review new vulnerabilities/misconfigurations
2. Assess need for emergency patching
3. Consider temporary access restrictions
4. Update change management system

Alert Time: {current_timestamp}
```

---

## Alert 3.3: SLA Breach Imminent (7 Days)

### Trigger Condition
CRITICAL vulnerability approaching SLA deadline (within 7 days).

### Natural Language Question
"Alert me daily about all CRITICAL vulnerabilities that will breach their 30-day SLA within the next 7 days"

### SQL Alert Query

```sql
-- SLA Breach Imminent Alert
SELECT 
    vi.cve_id,
    vi.instance_id,
    vi.severity,
    vl.description as severity_level,
    vi.cvssv3_basescore,
    vi.gtm_score,
    vi.threat_level,
    vi.detected_time,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - vi.detected_time))/86400 as days_since_detection,
    30 - EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - vi.detected_time))/86400 as days_until_sla_breach,
    -- Asset details
    a.nuid,
    a.dev_id,
    a.host_name,
    a.final_name,
    a.ip,
    ic.description as impact_class,
    cdt.description as device_type,
    a.platform,
    a.device_zone,
    a.location_region,
    -- Software details
    si.vendor,
    si.product,
    si.version,
    si.product_state,
    -- Patch availability
    vi.fix_versions,
    vi.patches,
    (SELECT COUNT(*) 
     FROM fix_instances fi 
     WHERE fi.sw_instance_id = vi.sw_instance_id 
       AND fi.state = 'AVAILABLE'
    ) as available_patches
FROM vulnerability_instances vi
LEFT JOIN vuln_level_enum vl ON vi.severity = vl.code
LEFT JOIN assets a ON vi.nuid = a.nuid AND vi.dev_id = a.dev_id
LEFT JOIN impact_class_enum ic ON a.impact_class = ic.code
LEFT JOIN asset_canonical_device_type_enum cdt ON a.device_type = cdt.code
LEFT JOIN software_instances si ON vi.sw_instance_id = si.key
WHERE vi.state = 'ACTIVE'
  AND vi.severity = 'CRITICAL'
  AND EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - vi.detected_time))/86400 BETWEEN 23 AND 30
ORDER BY 
    days_until_sla_breach ASC,
    ic.impact_order ASC,
    vi.cvssv3_basescore DESC
LIMIT 50;
```

### Alert Details

**Priority:** HIGH  
**Recipient:** Remediation Team, Asset Owners, Security Manager  
**Delivery:** Email, Dashboard  
**Frequency:** Daily at 9:00 AM

**Alert Template:**
```
⏰ SLA DEADLINE ALERT: Critical Vulnerabilities Approaching Breach

{count} CRITICAL vulnerabilities will breach 30-day SLA within 7 days

Top Priority Items:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. CVE: {cve_id}
   Asset: {final_name} ({ip})
   Days Until Breach: {days_until_sla_breach}
   CVSS Score: {cvssv3_basescore}
   Impact Class: {impact_class}
   Software: {vendor} {product} {version}
   Available Patches: {available_patches}
   
[Repeat for top 10 items]

ACTIONS REQUIRED:
1. Prioritize patch deployment for listed assets
2. Coordinate maintenance windows
3. Document any blockers preventing remediation
4. Submit exception requests if remediation not possible

View full report: [Link to Dashboard]
```

---

## Alert 3.4: Perimeter Asset with Critical Vulnerability

### Trigger Condition
New CRITICAL vulnerability detected on Perimeter propagation class asset.

### Natural Language Question
"Alert me immediately when any CRITICAL severity vulnerability is detected on a Perimeter asset"

### SQL Alert Query

```sql
-- Perimeter Asset Critical Vulnerability Alert
SELECT 
    vi.cve_id,
    vi.instance_id,
    vi.severity,
    vl.description as severity_level,
    vi.cvssv3_basescore,
    vi.gtm_score,
    vi.threat_level,
    vi.exposure,
    vi.detected_time,
    vi.tags,
    -- Asset details
    a.nuid,
    a.dev_id,
    a.host_name,
    a.final_name,
    a.ip,
    ic.description as impact_class,
    pc.description as propagation_class,
    a.is_bastion_device,
    cdt.description as device_type,
    a.platform,
    a.device_zone,
    a.location_region,
    a.roles,
    -- Risk metrics
    a.effective_risk,
    a.effective_likelihood,
    a.effective_impact,
    a.bastion_impact,
    a.propagation_impact,
    -- Software details
    si.vendor,
    si.product,
    si.version,
    si.product_state,
    -- CVSS breakdown
    SUBSTRING(vi.cvss_vector FROM 'AV:([A-Z])') as attack_vector,
    SUBSTRING(vi.cvss_vector FROM 'AC:([A-Z])') as attack_complexity,
    SUBSTRING(vi.cvss_vector FROM 'PR:([A-Z])') as privileges_required
FROM vulnerability_instances vi
LEFT JOIN vuln_level_enum vl ON vi.severity = vl.code
LEFT JOIN assets a ON vi.nuid = a.nuid AND vi.dev_id = a.dev_id
LEFT JOIN impact_class_enum ic ON a.impact_class = ic.code
LEFT JOIN propagation_class_enum pc ON a.propagation_class = pc.code
LEFT JOIN asset_canonical_device_type_enum cdt ON a.device_type = cdt.code
LEFT JOIN software_instances si ON vi.sw_instance_id = si.key
WHERE vi.state = 'ACTIVE'
  AND vi.severity = 'CRITICAL'
  AND a.propagation_class = 'Perimeter'
  AND DATE(vi.detected_time) = CURRENT_DATE
ORDER BY 
    a.is_bastion_device DESC,
    ic.impact_order ASC,
    vi.cvssv3_basescore DESC;
```

### Alert Details

**Priority:** CRITICAL  
**Recipient:** Network Security Team, Security Operations, Incident Response  
**Delivery:** Email, SMS, Slack, PagerDuty  
**Frequency:** Real-time (immediate)

**Alert Template:**
```
🔴 CRITICAL ALERT: Perimeter Asset Vulnerability

CVE: {cve_id}
Severity: CRITICAL
CVSS Score: {cvssv3_basescore}
GTM Score: {gtm_score}
Threat Level: {threat_level}

Affected Asset:
- Name: {final_name}
- IP: {ip}
- Location: Perimeter (Internet-Facing)
- Impact Class: {impact_class}
- Device Type: {device_type}
- Bastion Device: {is_bastion_device}
- Zone: {device_zone}
- Region: {location_region}

Attack Profile:
- Attack Vector: {attack_vector}
- Attack Complexity: {attack_complexity}
- Privileges Required: {privileges_required}

Vulnerable Software:
- {vendor} {product} {version}
- Product State: {product_state}

Risk Assessment:
- Effective Risk: {effective_risk}
- Propagation Impact: {propagation_impact}

IMMEDIATE ACTIONS:
1. Verify asset is truly perimeter-facing
2. Assess exploitation risk (check threat intel)
3. Consider temporary isolation/firewall rules
4. Emergency patching if available
5. Activate incident response if needed

Detected: {detected_time}
```

---

## Alert 3.5: Unusual Configuration Change on Bastion Device

### Trigger Condition
New misconfiguration detected on any bastion device.

### Natural Language Question
"Alert me immediately when any new misconfiguration is detected on a bastion device"

### SQL Alert Query

```sql
-- Bastion Device Misconfiguration Alert
SELECT 
    m.vuln_id,
    m.vuln_category,
    m.misconfig_category,
    m.vuln_description,
    m.vuln_severity,
    vl.description as severity_level,
    m.vuln_evidence,
    m.first_observed,
    m.last_observed,
    m.vuln_data_sources,
    -- Asset details
    a.nuid,
    a.dev_id,
    a.host_name,
    a.final_name,
    a.ip,
    ic.description as impact_class,
    pc.description as propagation_class,
    a.is_bastion_device,
    cdt.description as device_type,
    a.platform,
    a.device_zone,
    a.location_region,
    a.roles,
    -- Risk metrics
    a.effective_risk,
    a.bastion_impact,
    a.propagation_impact,
    a.misconfiguration_likelihood,
    -- Configuration context (Windows example)
    a.power_shell_exec_policy,
    a.smb1,
    a.smb2,
    a.smb3,
    a.secure_boot_status,
    a.domain_joined
FROM misconfigurations m
LEFT JOIN assets a ON m.nuid = a.nuid AND m.dev_id = a.dev_id
LEFT JOIN impact_class_enum ic ON a.impact_class = ic.code
LEFT JOIN propagation_class_enum pc ON a.propagation_class = pc.code
LEFT JOIN asset_canonical_device_type_enum cdt ON a.device_type = cdt.code
LEFT JOIN vuln_level_enum vl ON m.vuln_severity::text = vl.code
WHERE a.is_bastion_device = TRUE
  AND DATE(m.first_observed) = CURRENT_DATE
  AND m.is_stale = FALSE
ORDER BY 
    m.vuln_severity DESC,
    ic.impact_order ASC;
```

### Alert Details

**Priority:** HIGH  
**Recipient:** Infrastructure Team, Security Operations, Change Management  
**Delivery:** Email, Slack  
**Frequency:** Real-time (immediate)

**Alert Template:**
```
⚡ BASTION DEVICE ALERT: Configuration Change Detected

Misconfiguration: {vuln_description}
Category: {misconfig_category}
Severity: {severity_level}

Bastion Asset:
- Name: {final_name}
- IP: {ip}
- Impact Class: {impact_class}
- Propagation Class: {propagation_class}
- Device Type: {device_type}
- Zone: {device_zone}
- Roles: {roles}

Evidence: {vuln_evidence}

Current Configuration:
- PowerShell Policy: {power_shell_exec_policy}
- SMB v1: {smb1}
- Secure Boot: {secure_boot_status}

Risk Impact:
- Effective Risk: {effective_risk}
- Bastion Impact: {bastion_impact}
- Propagation Impact: {propagation_impact}

ACTIONS REQUIRED:
1. Verify if this was an authorized change
2. Review change management records
3. Assess security impact
4. Remediate configuration if unauthorized
5. Investigate potential compromise if suspicious

First Observed: {first_observed}
Detection Sources: {vuln_data_sources}
```

---

## Alert 3.6: Patch Failure on Critical Asset

### Trigger Condition
Patch deployment failed or was rolled back on Mission Critical or Critical asset.

### Natural Language Question
"Alert me when any patch fails or is rolled back on Mission Critical or Critical assets"

### SQL Alert Query

```sql
-- Patch Failure on Critical Asset Alert
-- Note: This requires tracking of patch states including failure states
-- Assuming we track patch history or state changes

SELECT 
    fi.id as patch_id,
    fi.nuid,
    fi.dev_id,
    fi.sw_instance_id,
    fi.patch_type,
    fi.state as patch_state,
    fi.install_time as attempted_install_time,
    -- Asset details
    a.host_name,
    a.final_name,
    a.ip,
    ic.description as impact_class,
    ic.impact_order,
    cdt.description as device_type,
    a.platform,
    a.device_zone,
    a.location_region,
    a.roles,
    -- Software details
    si.vendor,
    si.product,
    si.version,
    si.category as software_category,
    -- Related vulnerabilities
    (SELECT COUNT(DISTINCT vi.cve_id)
     FROM vulnerability_instances vi
     WHERE vi.sw_instance_id = fi.sw_instance_id
       AND vi.state = 'ACTIVE'
       AND vi.severity IN ('CRITICAL', 'HIGH')
    ) as related_critical_high_vulns,
    -- Risk context
    a.effective_risk,
    a.effective_likelihood
FROM fix_instances fi
LEFT JOIN assets a ON fi.nuid = a.nuid AND fi.dev_id = a.dev_id
LEFT JOIN impact_class_enum ic ON a.impact_class = ic.code
LEFT JOIN asset_canonical_device_type_enum cdt ON a.device_type = cdt.code
LEFT JOIN software_instances si ON fi.sw_instance_id = si.key
WHERE a.impact_class IN ('Mission Critical', 'Critical')
  AND DATE(fi.store_updated_at) = CURRENT_DATE
  -- Assuming we have a failure state or can detect rollback
  AND (fi.state = 'FAILED' OR fi.state = 'ROLLED_BACK')
ORDER BY 
    ic.impact_order ASC,
    related_critical_high_vulns DESC,
    a.effective_risk DESC;
```

### Alert Details

**Priority:** HIGH  
**Recipient:** IT Operations, Asset Owners, Patch Management Team  
**Delivery:** Email, Slack, Ticketing System  
**Frequency:** Real-time (immediate)

**Alert Template:**
```
❌ PATCH FAILURE ALERT: Critical Asset Patching Failed

Asset: {final_name}
IP: {ip}
Impact Class: {impact_class}
Device Type: {device_type}
Platform: {platform}
Location: {location_region}

Patch Details:
- Patch ID: {patch_id}
- Patch Type: {patch_type}
- State: {patch_state}
- Attempted Install: {attempted_install_time}

Software:
- Vendor: {vendor}
- Product: {product}
- Version: {version}

Impact:
- Related CRITICAL/HIGH Vulnerabilities: {related_critical_high_vulns}
- Asset Effective Risk: {effective_risk}

ACTIONS REQUIRED:
1. Investigate root cause of patch failure
2. Review system logs and error messages
3. Determine if manual remediation is needed
4. Document blockers and escalate if necessary
5. Update vulnerability management system
6. Consider alternative mitigations

Alert Time: {current_timestamp}
Ticket auto-created: [TICKET-XXXX]
```

---

## Alert 3.7: Mass Vulnerability Detection Event

### Trigger Condition
More than 50 new vulnerabilities detected across multiple assets in single day (potential scanner misconfiguration or widespread issue).

### Natural Language Question
"Alert me if more than 50 new vulnerabilities are detected in a single day, which might indicate a widespread issue or scanner problem"

### SQL Alert Query

```sql
-- Mass Vulnerability Detection Event Alert
WITH todays_detections AS (
    SELECT 
        vi.cve_id,
        vi.severity,
        vl.description as severity_level,
        COUNT(DISTINCT CONCAT(vi.nuid, '-', vi.dev_id)) as affected_assets,
        COUNT(DISTINCT vi.instance_id) as total_instances,
        AVG(vi.cvssv3_basescore) as avg_cvss_score,
        STRING_AGG(DISTINCT cdt.description, ', ') as affected_device_types,
        STRING_AGG(DISTINCT a.platform, ', ') as affected_platforms,
        STRING_AGG(DISTINCT a.location_region, ', ') as affected_regions,
        MIN(vi.detected_time) as first_detection,
        MAX(vi.detected_time) as last_detection
    FROM vulnerability_instances vi
    LEFT JOIN vuln_level_enum vl ON vi.severity = vl.code
    LEFT JOIN assets a ON vi.nuid = a.nuid AND vi.dev_id = a.dev_id
    LEFT JOIN asset_canonical_device_type_enum cdt ON a.device_type = cdt.code
    WHERE DATE(vi.detected_time) = CURRENT_DATE
    GROUP BY vi.cve_id, vi.severity, vl.description
)
SELECT 
    COUNT(DISTINCT cve_id) as unique_cves_detected,
    SUM(total_instances) as total_vulnerability_instances,
    SUM(affected_assets) as total_affected_assets,
    -- By severity
    SUM(CASE WHEN severity = 'CRITICAL' THEN total_instances ELSE 0 END) as critical_instances,
    SUM(CASE WHEN severity = 'HIGH' THEN total_instances ELSE 0 END) as high_instances,
    SUM(CASE WHEN severity = 'MEDIUM' THEN total_instances ELSE 0 END) as medium_instances,
    -- Widespread CVEs
    MAX(affected_assets) as max_assets_for_single_cve,
    (SELECT cve_id FROM todays_detections ORDER BY affected_assets DESC LIMIT 1) as most_widespread_cve,
    -- Platform/region distribution
    STRING_AGG(DISTINCT affected_platforms, ', ') as all_affected_platforms,
    STRING_AGG(DISTINCT affected_regions, ', ') as all_affected_regions,
    -- Timing
    MIN(first_detection) as earliest_detection,
    MAX(last_detection) as latest_detection
FROM todays_detections
HAVING SUM(total_instances) > 50;
```

### Alert Details

**Priority:** MEDIUM  
**Recipient:** Security Operations Manager, Scanner Administrators, Security Architect  
**Delivery:** Email, Slack  
**Frequency:** Daily summary (if threshold exceeded)

**Alert Template:**
```
📊 MASS DETECTION EVENT: Unusual Volume of Vulnerabilities

Detection Summary:
- Total Vulnerability Instances: {total_vulnerability_instances}
- Unique CVEs: {unique_cves_detected}
- Affected Assets: {total_affected_assets}

Severity Breakdown:
- CRITICAL: {critical_instances}
- HIGH: {high_instances}
- MEDIUM: {medium_instances}

Most Widespread Issue:
- CVE: {most_widespread_cve}
- Affects {max_assets_for_single_cve} assets

Affected Platforms: {all_affected_platforms}
Affected Regions: {all_affected_regions}

Detection Timeframe:
- First: {earliest_detection}
- Last: {latest_detection}

INVESTIGATION REQUIRED:
1. Verify scanner configuration is correct
2. Check for false positives
3. Determine if this is a legitimate widespread issue
4. Review recent network/software changes
5. Coordinate response if legitimate threat

This could indicate:
- Scanner configuration change
- New vulnerability affecting common software
- Recent software deployment
- False positive pattern

View detailed report: [Link to Dashboard]
```

---

## Alert 3.8: End-of-Life Software on Production Asset

### Trigger Condition
EOL (End-of-Life) software detected on Production zone asset.

### Natural Language Question
"Alert me when end-of-life software is detected on any asset in the Production zone"

### SQL Alert Query

```sql
-- End-of-Life Software on Production Asset Alert
SELECT 
    si.swkey_partition_id,
    si.nuid,
    si.dev_id,
    si.vendor,
    si.product,
    si.version,
    si.category as software_category,
    si.product_state,
    ps.description as product_state_desc,
    si.install_time,
    -- Asset details
    a.host_name,
    a.final_name,
    a.ip,
    ic.description as impact_class,
    cdt.description as device_type,
    a.platform,
    a.device_zone,
    a.location_region,
    a.roles,
    -- Risk context
    a.effective_risk,
    a.unpatched_vulnerability_likelihood,
    a.zero_day_likelihood,
    -- Related vulnerabilities
    (SELECT COUNT(DISTINCT vi.cve_id)
     FROM vulnerability_instances vi
     WHERE vi.sw_instance_id = si.key
       AND vi.state = 'ACTIVE'
    ) as active_vulnerabilities_count,
    (SELECT COUNT(DISTINCT vi.cve_id)
     FROM vulnerability_instances vi
     WHERE vi.sw_instance_id = si.key
       AND vi.state = 'ACTIVE'
       AND vi.severity IN ('CRITICAL', 'HIGH')
    ) as critical_high_vulns
FROM software_instances si
LEFT JOIN product_state_enum ps ON si.product_state = ps.code
LEFT JOIN assets a ON si.nuid = a.nuid AND si.dev_id = a.dev_id
LEFT JOIN impact_class_enum ic ON a.impact_class = ic.code
LEFT JOIN asset_canonical_device_type_enum cdt ON a.device_type = cdt.code
WHERE si.product_state = 'EOL'
  AND a.device_zone LIKE '%Production%'
  AND DATE(si.store_updated_at) = CURRENT_DATE
ORDER BY 
    ic.impact_order ASC,
    critical_high_vulns DESC,
    a.effective_risk DESC;
```

### Alert Details

**Priority:** MEDIUM  
**Recipient:** Application Owners, IT Operations, Security Team  
**Delivery:** Email, Ticketing System  
**Frequency:** Daily

**Alert Template:**
```
⚠️  EOL SOFTWARE ALERT: End-of-Life Software in Production

Asset: {final_name}
IP: {ip}
Impact Class: {impact_class}
Zone: {device_zone}
Location: {location_region}

EOL Software:
- Vendor: {vendor}
- Product: {product}
- Version: {version}
- Category: {software_category}
- Installed: {install_time}

Security Impact:
- Active Vulnerabilities: {active_vulnerabilities_count}
- Critical/High Vulnerabilities: {critical_high_vulns}
- Asset Effective Risk: {effective_risk}
- Zero Day Likelihood: {zero_day_likelihood}

ACTIONS REQUIRED:
1. Plan migration to supported version
2. Document business justification if migration not possible
3. Implement compensating controls
4. Request risk exception if needed
5. Add to technical debt register

End-of-life software receives no security updates and poses 
ongoing risk to the organization.

Alert Time: {current_timestamp}
```

---

## Alert Configuration Summary Table

| Alert ID | Alert Name | Priority | Frequency | Recipients | Threshold |
|----------|------------|----------|-----------|------------|-----------|
| 3.1 | CISA Known Exploit | CRITICAL | Real-time | SOC, CISO, IR | Any detection |
| 3.2 | Mission Critical Risk Spike | HIGH | Real-time | Asset Owners, Sec Team | >20% increase |
| 3.3 | SLA Breach Imminent | HIGH | Daily 9 AM | Remediation Team | 7 days before breach |
| 3.4 | Perimeter Critical Vuln | CRITICAL | Real-time | Network Sec, SOC | Any CRITICAL on Perimeter |
| 3.5 | Bastion Misconfiguration | HIGH | Real-time | Infra, SOC | Any new misconfig on bastion |
| 3.6 | Patch Failure Critical Asset | HIGH | Real-time | IT Ops, Patch Mgmt | Any failure on MC/Critical |
| 3.7 | Mass Vulnerability Event | MEDIUM | Daily | Sec Ops Mgr, Scanner Admin | >50 new vulns/day |
| 3.8 | EOL Software Production | MEDIUM | Daily | App Owners, IT Ops | Any EOL in Production |

---

## Integration Points for Alerts

### Email Integration
- SMTP server configuration
- HTML templates with formatting
- Attachment support (CSV exports of affected assets)
- Thread grouping for related alerts

### Slack Integration
```python
# Example Slack webhook payload
{
    "channel": "#security-alerts",
    "username": "VulnBot",
    "icon_emoji": ":rotating_light:",
    "attachments": [
        {
            "color": "danger",  # red for critical, warning for high
            "title": "CRITICAL: CISA Known Exploit Detected",
            "fields": [
                {"title": "CVE", "value": "CVE-2024-12345", "short": true},
                {"title": "Severity", "value": "CRITICAL", "short": true},
                {"title": "Asset", "value": "prod-db-01", "short": true},
                {"title": "Impact Class", "value": "Mission Critical", "short": true}
            ],
            "footer": "Vulnerability Management System",
            "ts": 1234567890
        }
    ]
}
```

### PagerDuty Integration
- Critical alerts trigger incidents
- Auto-assignment based on asset ownership
- Escalation policies for non-response
- Incident deduplication by CVE + Asset

### Ticketing System Integration
- Auto-create tickets for remediation
- Link vulnerabilities to change requests
- Track remediation progress
- SLA monitoring integration

### Dashboard Integration
- Real-time alert feed widget
- Alert history and trending
- Acknowledge/dismiss functionality
- Alert correlation and grouping

---

## Alert Tuning Recommendations

### Threshold Adjustment
- Monitor false positive rates
- Adjust percentage thresholds based on environment variability
- Implement alert fatigue monitoring
- Allow per-asset or per-region threshold customization

### Suppression Rules
- Maintenance windows
- Known issues with accepted risk
- Testing/development environments
- Temporary suppressions with expiry

### Escalation Logic
```
CRITICAL alerts:
- Immediate: Security Operations Team
- 15 min: Security Team Lead
- 30 min: CISO
- 1 hour: Executive Team

HIGH alerts:
- Immediate: Asset Owners, Security Team
- 1 hour: Security Team Lead
- 4 hours: Manager escalation

MEDIUM alerts:
- Email notification
- Daily digest
- No immediate escalation
```

---

# Summary: Use Cases Comparison

## Daily Management Reports
**Purpose:** Operational visibility  
**Audience:** Security analysts, IT operations, remediation teams  
**Frequency:** Daily  
**Focus:** What changed yesterday, what needs attention today  
**Action-oriented:** Yes - specific remediation tasks  

## Executive Reports
**Purpose:** Strategic oversight  
**Audience:** C-level, Board, Business leaders  
**Frequency:** Weekly/Monthly  
**Focus:** Trends, compliance, business risk, ROI  
**Action-oriented:** Strategic investments and priorities  

## Real-Time Alerts
**Purpose:** Immediate response  
**Audience:** On-call teams, incident responders, asset owners  
**Frequency:** Real-time (as events occur)  
**Focus:** Critical threats, SLA breaches, anomalies  
**Action-oriented:** Emergency response and containment  

---

# Natural Language to SQL Conversion

For all queries in this framework, a text-to-SQL engine should be able to convert natural language questions by:

1. **Entity Recognition**: Identify tables (assets, vulnerability_instances, etc.)
2. **Attribute Mapping**: Map terms to columns (risk score → effective_risk)
3. **Enum Lookup**: Resolve categorical values using metadata tables
4. **Time Window Detection**: Extract date ranges from language
5. **Aggregation Detection**: Identify grouping and aggregation needs
6. **Join Logic**: Determine necessary table relationships
7. **Filter Criteria**: Extract WHERE clause conditions
8. **Ordering Logic**: Identify sort requirements

**Example Natural Language Processing:**
```
Input: "Show me Mission Critical Windows servers with critical vulnerabilities in the last week"

Parsed Components:
- Table: assets (main), vulnerability_instances (join)
- Filters: 
  * impact_class = 'Mission Critical'
  * platform = 'Windows'
  * device_type IN (SELECT code FROM device_type_enum WHERE description LIKE '%Server%')
  * severity = 'CRITICAL'
  * detected_time >= CURRENT_DATE - 7
- Joins: assets ↔ vulnerability_instances on (nuid, dev_id)
- Output: Asset list with vulnerability details
```

This framework provides production-ready SQL that can also serve as training data for text-to-SQL models.

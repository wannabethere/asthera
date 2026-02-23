Let me map out practical use cases for security engineers with concrete workflows showing how your system becomes their AI security analyst.

---

## **Use Case 1: Zero-Day Response - "Log4Shell on Friday Afternoon"**

### **Scenario**
It's 4pm Friday. CVE-2024-50349 just dropped — a critical RCE in a popular Python library. Your CISO asks: "Are we exposed? What do we do?"

### **Traditional Workflow (4-8 hours)**
- Manually search NVD for CVE details
- Grep through asset inventory spreadsheets
- Check each team's Slack for "anyone using this?"
- Google for exploit availability
- Reverse-engineer which compliance controls this violates
- Write incident report over the weekend

### **AI-Powered Workflow (15 minutes)**

**User:** "Tell me everything about CVE-2024-50349"

**System orchestrates:**

1. **CVE Intelligence Tool** queries:
   - NVD API → CVSS 9.8, RCE, affects Python library X versions 2.0-2.4
   - EPSS API → 0.87 (87% likely to be exploited in 30 days)
   - CISA KEV → Not yet listed, but high EPSS suggests imminent
   - Exploit-DB → PoC published 3 hours ago

2. **ATT&CK Mapper** infers:
   - Initial Access: T1190 (Exploit Public-Facing Application)
   - Execution: T1059.006 (Python)
   - Impact: T1485 (Data Destruction) if chained with other vulns

3. **Asset Correlation** (if you have SBOM/dependency data):
   - 12 services use affected library
   - 3 are internet-facing (API gateway, data ingestion pipeline, ML inference endpoint)
   - 9 are internal microservices

4. **Control Coverage Analysis**:
   - Query framework KB: "Which controls mitigate T1190?"
   - Returns: CIS Control 7.1 (Vulnerability Management), NIST PR.IP-12 (Vulnerability Management Plan), HIPAA §164.308(a)(5)(ii)(B) (Protection from Malicious Software)
   - Gap check: "Do we have these controls implemented?"
   - Result: CIS 7.1 only partially implemented (quarterly scanning, but no patch SLA)

5. **Remediation Prioritization**:
   - API gateway: **CRITICAL** (CVSS 9.8 + internet-facing + EPSS 0.87 + exploit available)
   - ML inference: **HIGH** (internet-facing but rate-limited, less attractive target)
   - Internal services: **MEDIUM** (requires initial foothold, but lateral movement risk)

6. **Detection Strategy**:
   - Sigma Rule Generator produces SIEM query:
     ```
     Process: python* 
     CommandLine: *eval(* OR *exec(* OR *__import__*
     Network: Outbound connection within 5sec of process spawn
     ```
   - Nuclei Template search finds existing scanner for this CVE
   - Recommendation: Run Nuclei scan NOW, deploy Sigma rule to SIEM

7. **Automated Report Generation**:

```
CVE-2024-50349 INCIDENT BRIEF
Generated: 2024-12-20 16:12 UTC

EXECUTIVE SUMMARY
Critical RCE vulnerability in Python library X affects 12 internal services, 
3 with internet exposure. Public exploit available. IMMEDIATE ACTION REQUIRED.

TECHNICAL DETAILS
- CVSS: 9.8 (Critical)
- EPSS: 0.87 (87% exploitation probability)
- Exploit Available: YES (PoC published 3hrs ago)
- Attack Vector: Network, No authentication required
- ATT&CK: T1190 (Exploit Public-Facing Application)

AFFECTED ASSETS
HIGH PRIORITY:
  1. api-gateway-prod (34.120.45.23) - Internet-facing
  2. ml-inference-prod (34.120.45.89) - Internet-facing, rate-limited

MEDIUM PRIORITY:
  3. data-ingestion-prod (10.0.5.45) - Internal
  4-12. [See full asset list]

CONTROL GAP ANALYSIS
MISSING CONTROLS:
  ✗ CIS 7.1: No formal patch SLA (we scan quarterly, should be within 30 days)
  ✗ NIST PR.IP-12: Vulnerability management plan not documented
  ✓ HIPAA §164.308(a)(5)(ii)(B): Anti-malware present

IMMEDIATE ACTIONS (Next 2 hours)
1. Run Nuclei scan on 3 internet-facing services
2. Deploy WAF rule blocking exploit pattern (provided below)
3. Enable enhanced logging on affected services
4. Deploy Sigma detection rule to SIEM

SHORT-TERM REMEDIATION (Next 48 hours)
1. Patch api-gateway-prod and ml-inference-prod
2. Isolate data-ingestion-prod network segment
3. Patch remaining 9 internal services

LONG-TERM IMPROVEMENTS
1. Implement CIS 7.1: 30-day patch SLA for critical vulnerabilities
2. Add library X to SBOM scanning (currently missing)
3. Document vulnerability management plan per NIST PR.IP-12

DETECTION & MONITORING
- Sigma rule deployed to SIEM (query provided)
- Nuclei template: nuclei-templates/cves/2024/CVE-2024-50349.yaml
- Expected false positive rate: Low
- Monitoring dashboard: [Link to Grafana]
```

**Time saved:** 4-8 hours → 15 minutes  
**Business impact:** Remediation starts immediately instead of Monday morning

---

## **Use Case 2: Compliance Audit Prep - "SOC2 in 3 Weeks"**

### **Scenario**
Your company needs SOC2 Type II certification. Auditor wants evidence that you've implemented controls for credential theft prevention.

### **Traditional Workflow**
- Read 400-page SOC2 framework PDF
- Map which controls apply to credential theft
- Manually cross-reference to your existing security controls
- Search through Confluence/Google Drive for evidence
- Build spreadsheet showing gaps
- Schedule 10 meetings with different teams to gather proof

### **AI-Powered Workflow**

**User:** "Show me SOC2 controls for credential theft and what we're missing"

**System orchestrates:**

1. **ATT&CK Technique Identification**:
   - "Credential theft" → maps to ATT&CK tactics:
     - T1003 (OS Credential Dumping)
     - T1555 (Credentials from Password Stores)
     - T1552 (Unsecured Credentials)
     - T1078 (Valid Accounts)

2. **Cross-Framework Mapping**:
   - Queries: "Which SOC2 controls mitigate T1003, T1555, T1552, T1078?"
   - Retrieves from `attack_technique_control_mapping` table:
     - SOC2 CC6.1 (Logical and Physical Access Controls)
     - SOC2 CC6.6 (Encryption)
     - SOC2 CC6.7 (Privileged Access)
   - Also retrieves equivalent controls from CIS, NIST, HIPAA for comparison

3. **Control Coverage Analysis**:
   ```
   SOC2 CC6.1 - Logical Access Controls
   ├─ CIS 5.2: MFA for Administrative Access ✓ IMPLEMENTED
   ├─ CIS 5.3: Disable Dormant Accounts ✗ MISSING
   ├─ CIS 6.2: Password Complexity ✓ IMPLEMENTED
   └─ NIST PR.AC-1: Identity Management ✓ IMPLEMENTED
   
   SOC2 CC6.6 - Encryption
   ├─ CIS 3.11: Encrypt Sensitive Data ✗ PARTIAL (only production, not dev)
   └─ HIPAA §164.312(a)(2)(iv): Encryption ✓ IMPLEMENTED
   
   SOC2 CC6.7 - Privileged Access
   ├─ CIS 5.4: PAM Solution ✗ MISSING (no CyberArk/BeyondTrust)
   └─ NIST PR.AC-4: Access Permissions ✓ IMPLEMENTED
   ```

4. **Evidence Collection Assistant**:
   - Searches your Google Drive/Confluence for existing docs:
     - "MFA rollout plan" → Found: `IT/2024-MFA-Implementation.pdf`
     - "Password policy" → Found: `HR/Employee-Handbook.docx` (section 8)
     - "Encryption standards" → Not found → **FLAG: Need to create**
   - Searches Jira for related tickets:
     - MFA-234: "Enable MFA for AWS Console" (Closed, 2024-03)
     - SEC-567: "Implement CyberArk" (Open, 0% complete) → **RISK**

5. **Gap Analysis Report**:

```
SOC2 CC6.1, CC6.6, CC6.7 READINESS ASSESSMENT
Focus: Credential Theft Prevention

CONTROL MATURITY HEATMAP
                    Implemented | Partial | Missing
SOC2 CC6.1              60%        20%       20%
SOC2 CC6.6              40%        40%       20%
SOC2 CC6.7              33%         0%       67%

CRITICAL GAPS (Auditor will flag)
1. No PAM solution for privileged access management
   - SOC2 CC6.7 requirement
   - Mitigates: T1078.002 (Domain Accounts), T1003 (Credential Dumping)
   - Recommendation: Deploy CyberArk or BeyondTrust
   - Timeline: 6-8 weeks (you have 3 weeks → BLOCKER)
   
2. Dormant account cleanup not automated
   - SOC2 CC6.1 requirement
   - Current state: Manual quarterly review (last done 4 months ago)
   - 47 dormant accounts detected in last scan
   - Quick fix: Okta automated deprovisioning (2 day implementation)

3. Dev environment encryption not enforced
   - SOC2 CC6.6 requirement
   - Production: ✓ Encrypted (AWS KMS)
   - Staging: ✓ Encrypted
   - Dev: ✗ Plaintext databases → AUDIT FAILURE RISK
   - Quick fix: Apply same Terraform template (1 day)

AVAILABLE EVIDENCE (Ready for auditor)
✓ MFA-234 ticket + rollout doc
✓ Password policy in employee handbook
✓ AWS CloudTrail logs showing MFA enforcement
✓ Okta access logs (90 days retention)

MISSING EVIDENCE (Create before audit)
✗ Formal encryption standard document
✗ Privileged access management policy
✗ Dormant account review schedule

RECOMMENDED ACTIONS (Priority order)
Week 1:
  1. Enable Okta automated deprovisioning (closes gap #2)
  2. Encrypt dev databases (closes gap #3)
  3. Draft encryption standards doc (evidence for CC6.6)

Week 2:
  4. Draft PAM policy even without tool (shows intent)
  5. Create compensating controls doc for PAM gap
     - Require all privileged actions via bastion host (already implemented)
     - Enable session recording (1 week to deploy)
  6. Generate access review reports for last 12 months

Week 3:
  7. Final evidence package assembly
  8. Mock audit with internal team

RISK ASSESSMENT
- Likelihood of SOC2 failure: MEDIUM
- Primary risk: PAM gap (cannot implement tool in 3 weeks)
- Mitigation: Compensating controls + timeline commitment
- Fallback: Request 90-day extension for PAM implementation
```

**Auditor Talking Points (AI-generated):**
```
"We acknowledge the PAM tool gap. However, we've implemented 
compensating controls:

1. All privileged access via hardened bastion hosts (CIS 5.1)
2. Session recording enabled (deployment 12/22, before audit)
3. MFA enforced for all administrative access (100% coverage)
4. Just-in-time access via Okta workflows (max 4hr sessions)
5. Formal PAM procurement approved, rollout scheduled Q1 2025

These compensating controls satisfy SOC2 CC6.7 intent per 
AICPA guidance section 4.2.3. We respectfully request acceptance 
with a 90-day remediation timeline."
```

**Time saved:** 40 hours → 2 hours  
**Audit confidence:** Medium → High

---

## **Use Case 3: Threat Hunting - "Suspected Lateral Movement"**

### **Scenario**
Your SIEM flagged unusual PowerShell activity on a developer workstation. Is this an adversary moving laterally, or just DevOps doing DevOps things?

### **Traditional Workflow**
- Dig through SIEM logs manually
- Google "PowerShell lateral movement techniques"
- Read 10 blog posts about Pass-the-Hash
- Check if any CVEs enable this technique
- Try to remember which controls prevent lateral movement
- Escalate to IR team after 2 hours of investigation

### **AI-Powered Workflow**

**User:** "Analyze this alert: PowerShell remoting from DEV-WS-042 to multiple servers"

**System orchestrates:**

1. **ATT&CK Technique Recognition**:
   - PowerShell remoting patterns → T1021.006 (Remote Services: Windows Remote Management)
   - Multiple targets → Likely T1021 (Remote Services) + T1570 (Lateral Tool Transfer)
   - Tags as: Lateral Movement tactic

2. **Behavioral Context Analysis**:
   ```
   ALERT ENRICHMENT
   Source: DEV-WS-042 (10.50.3.142)
   User: john.smith@company.com
   Time: 2024-12-20 14:23 UTC
   Targets: 
     - PROD-API-01 (10.10.1.5)
     - PROD-API-02 (10.10.1.6)
     - PROD-DB-01 (10.10.2.3)
   
   PowerShell Commands Observed:
     Invoke-Command -ComputerName PROD-API-01 -ScriptBlock {Get-Process}
     Enter-PSSession -ComputerName PROD-DB-01
     Copy-Item \\DEV-WS-042\share\script.ps1 \\PROD-API-02\C$\Temp\
   
   BASELINE COMPARISON (User john.smith last 30 days)
   ✗ ANOMALY: Never accessed production systems before
   ✗ ANOMALY: First time using PSRemoting
   ✓ NORMAL: PowerShell usage common (developer role)
   ✗ ANOMALY: File copy to C:\Temp\ (unusual pattern)
   ```

3. **Attack Path Reconstruction**:
   - Queries: "What CVEs enable initial access to developer workstations?"
   - Checks recent alerts from DEV-WS-042:
     ```
     T-3 days: Phishing email delivered (blocked by SEG)
     T-2 days: Chrome 0-day CVE-2024-XXXXX (patch pending)
     T-1 day: Suspicious MSI installer executed (john.smith)
     TODAY: Lateral movement observed
     ```
   - **Hypothesis:** Compromised via Chrome 0-day, now moving to production

4. **ATT&CK Chain Visualization**:
   ```
   SUSPECTED ATTACK CHAIN
   
   [Initial Access - T1189]
     └─> Exploit Chrome 0-day (CVE-2024-XXXXX)
         └─> DEV-WS-042 compromised
   
   [Execution - T1204.002]
     └─> User executed malicious MSI (john.smith credentials)
   
   [Lateral Movement - T1021.006]
     └─> PowerShell Remoting to production servers
         ├─> PROD-API-01 (Recon: Get-Process)
         ├─> PROD-DB-01 (Interactive session)
         └─> PROD-API-02 (Dropped script.ps1)
   
   [Potential Next Steps - Predicted]
     └─> Collection (T1005): Access database
     └─> Exfiltration (T1041): C2 over HTTPS
   ```

5. **Control Effectiveness Check**:
   ```
   SHOULD THESE CONTROLS HAVE BLOCKED THIS?
   
   CIS 4.1: Secure Config for Network Devices
     Status: ✓ Implemented
     Expected: Block dev→prod traffic
     Actual: BYPASSED (john.smith has VPN "DevOps" group)
     Gap: VPN policy too permissive
   
   CIS 5.4: Privileged Access Management
     Status: ✗ Missing (flagged in SOC2 audit above)
     Expected: Require approval for prod access
     Actual: No PAM → direct access allowed
     Impact: HIGH (this attack succeeded due to this gap)
   
   CIS 8.5: Centralized Log Collection
     Status: ✓ Implemented
     Expected: Detect lateral movement
     Actual: DETECTED (this alert)
     Impact: Positive (we caught it)
   
   NIST DE.CM-1: Network Monitoring
     Status: ✓ Partial (SIEM, no EDR on workstations)
     Expected: Detect malware on DEV-WS-042
     Actual: MISSED (MSI installer not flagged)
     Gap: No EDR on developer workstations
   ```

6. **Automated Response Recommendations**:
   ```
   IMMEDIATE (Next 10 minutes)
   1. Isolate DEV-WS-042 network (Palo Alto CLI command provided)
   2. Disable john.smith account in AD
   3. Force logoff all john.smith sessions (command provided)
   4. Block script.ps1 hash in AV (SHA256 provided)
   
   SHORT-TERM (Next 4 hours)
   5. Image DEV-WS-042 for forensics
   6. Review PROD-DB-01 database audit logs (query provided)
   7. Check PROD-API-02 for persistence (IOC list provided)
   8. Reset john.smith password + force MFA re-enrollment
   
   INVESTIGATION QUERIES (Copy-paste into Splunk)
   
   // Find all connections from compromised host
   index=firewall src_ip=10.50.3.142 
   | stats count by dest_ip, dest_port 
   | where count > 1
   
   // Check for data exfiltration
   index=proxy src_ip=10.50.3.142 bytes_out > 10000000
   | table _time, url, bytes_out
   
   // Correlate with other user activity
   index=windows EventCode=4624 Account_Name=john.smith 
   | table _time, ComputerName, Logon_Type
   ```

7. **Post-Incident Control Hardening**:
   ```
   ROOT CAUSE: Lack of network segmentation + no PAM
   
   PREVENTIVE CONTROLS TO IMPLEMENT
   1. Network Segmentation (CIS 12.2)
      - Create VLAN separation: Dev | Staging | Prod
      - Firewall rule: DENY dev→prod by default
      - Exception process: Require ticket + approval
      Timeline: 2 weeks
   
   2. PAM Solution (CIS 5.4) - Already flagged in SOC2 audit
      - Require JIT access for production
      - Session recording for all privileged commands
      Timeline: 8 weeks (accelerate after this incident)
   
   3. EDR on Developer Workstations (NIST PR.DS-5)
      - Deploy CrowdStrike/SentinelOne to all dev machines
      - Would have caught malicious MSI
      Timeline: 1 week
   
   DETECTIVE CONTROLS TO ENHANCE
   4. Anomaly Detection (NIST DE.AE-3)
      - Tune UEBA: Flag any dev→prod access by non-DevOps roles
      - Alert on first-time PowerShell remoting
      Timeline: 3 days (Splunk tuning)
   ```

**Time saved:** 4 hours investigation → 20 minutes  
**MTTR (Mean Time To Respond):** 240 minutes → 15 minutes

---

## **Use Case 4: Red Team Planning - "Test Our Defenses"**

### **Scenario**
Your company hired a red team for next quarter. You want to know: "What attacks are we actually ready to detect?" so you can prioritize control improvements before they test you.

### **Traditional Workflow**
- Schedule meetings with red team to learn their methods
- Guess which ATT&CK techniques they might use
- Manually review SIEM rules to see what's covered
- Hope for the best

### **AI-Powered Workflow**

**User:** "Generate a red team attack plan and show me which steps we can/cannot detect"

**System orchestrates:**

1. **Attack Path Generator**:
   - Analyzes your public attack surface (via Shodan API):
     - VPN gateway (Cisco ASA, CVE-2024-XXXXX available)
     - Webmail (OWA, phishing potential)
     - Public website (WordPress, outdated plugins)
   
   - Builds 3 realistic attack chains:
   
   **Chain A: External → Internal via VPN Exploit**
   ```
   T1190: Exploit VPN (CVE-2024-XXXXX)
     └─> Gain foothold on VPN server
   T1078: Valid Accounts (harvested from VPN config)
     └─> Authenticate as legitimate user
   T1021.001: RDP to workstation
     └─> Pivot to internal network
   T1003.001: LSASS credential dumping
     └─> Obtain domain admin hash
   T1550.002: Pass-the-Hash
     └─> Access domain controller
   T1003.006: DCSync attack
     └─> Exfiltrate all AD credentials
   ```
   
   **Chain B: Phishing → Lateral Movement**
   ```
   T1566.001: Spear-phishing with attachment
     └─> User opens malicious Excel
   T1204.002: User execution of macro
     └─> Download Cobalt Strike beacon
   T1055: Process injection into explorer.exe
     └─> Establish C2
   T1083: File and directory discovery
     └─> Find sensitive data shares
   T1039: Data from network shared drive
     └─> Stage 500GB of files
   T1041: C2 channel exfiltration
     └─> Exfiltrate over HTTPS (mimics normal traffic)
   ```
   
   **Chain C: Supply Chain → Persistence**
   ```
   T1195.002: Compromise software supply chain
     └─> Inject backdoor into NPM package you use
   T1072: Software deployment tools
     └─> Deploy via Jenkins CI/CD
   T1053.005: Scheduled task for persistence
     └─> Run backdoor on boot
   T1071.001: C2 over DNS
     └─> Low-and-slow exfiltration
   ```

2. **Detection Coverage Matrix**:
   ```
   ATTACK CHAIN A: VPN Exploit → Domain Admin
   
   Step 1: T1190 - Exploit VPN (CVE-2024-XXXXX)
     Detection Status: ⚠️ PARTIAL
     ├─ Implemented Controls:
     │   ✓ CIS 7.1: Vulnerability scanning (quarterly)
     │   ✓ Intrusion Detection System monitoring VPN
     ├─ Detection Capability:
     │   ✓ IDS signature for exploit pattern (Snort rule 2024-1234)
     │   ✗ No EDR on VPN appliance (can't detect post-exploit)
     └─ Recommendation: Patch VPN NOW (exploit publicly available)
   
   Step 2: T1078 - Valid Account Login
     Detection Status: ✗ BLIND SPOT
     ├─ Implemented Controls:
     │   ✗ No UEBA (can't detect anomalous VPN login)
     │   ✗ No MFA on VPN (red team can reuse stolen creds)
     ├─ Detection Capability:
     │   ✓ Logs collected (VPN → SIEM)
     │   ✗ No alerting on first-time VPN user
     └─ Recommendation: Enable MFA + UEBA alerting
   
   Step 3: T1021.001 - RDP to Workstation
     Detection Status: ✓ DETECTED
     ├─ Implemented Controls:
     │   ✓ CIS 12.2: Network segmentation (firewall logs)
     │   ✓ NIST DE.CM-1: Network monitoring
     ├─ Detection Capability:
     │   ✓ Sigma rule: "RDP from VPN subnet to workstation subnet"
     │   ✓ Alert threshold: >3 destinations in 10min
     └─ Confidence: HIGH (red team will be caught here)
   
   Step 4: T1003.001 - LSASS Credential Dumping
     Detection Status: ⚠️ PARTIAL
     ├─ Implemented Controls:
     │   ✓ EDR on workstations (CrowdStrike)
     │   ✗ No Credential Guard enabled (Windows setting)
     ├─ Detection Capability:
     │   ✓ EDR detects Mimikatz/ProcDump signatures
     │   ✗ Custom LSASS dumpers may evade
     └─ Recommendation: Enable Windows Credential Guard
   
   Step 5: T1550.002 - Pass-the-Hash
     Detection Status: ✗ BLIND SPOT
     ├─ Implemented Controls:
     │   ✗ No PAM (privileged accounts not monitored)
     │   ✗ Lateral movement not restricted
     ├─ Detection Capability:
     │   ✓ Domain Controller logs (Event 4776)
     │   ✗ No alert on hash authentication from workstation
     └─ Recommendation: Deploy PAM + Kerberos monitoring
   
   Step 6: T1003.006 - DCSync Attack
     Detection Status: ✓ DETECTED
     ├─ Implemented Controls:
     │   ✓ Domain Controller monitoring
     │   ✓ Abnormal replication alerts
     ├─ Detection Capability:
     │   ✓ Event 4662 (Directory Service Access)
     │   ✓ Replication from non-DC IP triggers alert
     └─ Confidence: HIGH (SOC will see this within 5 minutes)
   
   OVERALL CHAIN A ASSESSMENT:
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Detection Coverage: 4/6 steps (66%)
   Blind Spots: Steps 2, 5 (Valid Accounts, Pass-the-Hash)
   Likelihood Red Team Succeeds: MEDIUM
   Time to Detection (if successful): 15-30 minutes (caught at RDP or DCSync)
   ```

3. **Control Gap Heatmap**:
   ```
   RED TEAM ATTACK SURFACE ANALYSIS
   
   CRITICAL GAPS (Red team will exploit these)
   1. No MFA on VPN [CIS 6.3, NIST PR.AC-7]
      - Enables: T1078 (Valid Accounts)
      - Impact: Undetected initial access
      - Fix Timeline: 2 weeks
      - Fix Cost: $0 (already licensed in Okta)
   
   2. No PAM solution [CIS 5.4]
      - Enables: T1550.002 (Pass-the-Hash)
      - Impact: Lateral movement undetected
      - Fix Timeline: 8 weeks (procurement + deployment)
      - Fix Cost: $50k/year (CyberArk)
   
   3. No UEBA [NIST DE.AE-3]
      - Enables: Anomalous behavior goes unnoticed
      - Impact: Slow detection (hours instead of minutes)
      - Fix Timeline: 4 weeks (Splunk UBA add-on)
      - Fix Cost: $30k/year
   
   STRENGTHS (Red team will struggle here)
   ✓ Strong EDR coverage (CrowdStrike on 95% of endpoints)
   ✓ Robust network segmentation (firewalls between zones)
   ✓ Good SIEM rule coverage (80% of ATT&CK techniques)
   ✓ Domain Controller monitoring (DCSync will be caught fast)
   ```

4. **Pre-Red-Team Hardening Plan**:
   ```
   PRIORITY 1 (Do before red team arrives - 2 weeks)
   1. Enable MFA on VPN (closes T1078 gap)
   2. Patch VPN CVE-2024-XXXXX (closes T1190 gap)
   3. Enable Windows Credential Guard on all workstations
   4. Deploy Sigma rules for Pass-the-Hash detection (temporary until PAM)
   5. Tune SIEM alert for first-time VPN + RDP combinations
   
   PRIORITY 2 (Won't finish in time, but show progress)
   6. Begin PAM procurement (demo CyberArk, get quote)
   7. Enable Splunk UEBA trial (show you're working on it)
   
   POST-RED-TEAM REMEDIATION (Based on expected findings)
   8. Full PAM deployment after red team validates the gap
   9. UEBA production rollout
   10. Asset inventory cleanup (red team will find shadow IT)
   ```

5. **Red Team "Cheat Sheet" for Your SOC**:
   ```
   WHAT TO WATCH FOR DURING RED TEAM ENGAGEMENT
   
   Week 1-2: Recon & Initial Access
   Watch For:
   - Unusual Shodan/Censys traffic to your IPs
   - Port scan patterns (Nmap signatures)
   - Failed VPN login attempts (password spray)
   - Phishing emails from new domains
   
   SIEM Queries to Monitor:
   index=firewall action=blocked | stats count by src_ip | where count > 100
   index=vpn EventCode=Failed_Login | timechart span=5m count
   
   Week 3: Exploitation & Lateral Movement
   Watch For:
   - RDP from VPN subnet (they got in)
   - PowerShell execution spikes
   - LSASS access attempts
   - Service account logins from workstations (not servers)
   
   SIEM Queries:
   index=windows EventCode=4688 Process_Name=*powershell* Parent_Process=*explorer*
   index=windows EventCode=4656 Object_Name=*lsass.exe*
   
   Week 4: Persistence & Exfiltration
   Watch For:
   - New scheduled tasks on servers
   - Large outbound data transfers
   - DNS queries to suspicious domains
   - C2 beacon patterns (regular 60-second intervals)
   
   SIEM Queries:
   index=proxy bytes_out > 100000000 | stats sum(bytes_out) by src_ip
   index=dns query_type=TXT | stats count by query | where count > 100
   ```

**Time saved:** 2 weeks of prep → 3 hours  
**Detection readiness:** 40% → 80%

---

## **Use Case 5: Security Architecture Review - "New Cloud Migration"**

### **Scenario**
Your company is migrating a legacy Java app to AWS. Architects designed the infrastructure. You need to identify security risks before deployment.

### **Traditional Workflow**
- Review 50-page Terraform/CloudFormation
- Manually check against CIS AWS Benchmark (400 pages)
- Guess which ATT&CK techniques apply to cloud
- Hope you didn't miss anything critical

### **AI-Powered Workflow**

**User:** "Review this AWS architecture diagram and Terraform. What are the security risks?"

**System orchestrates:**

1. **Architecture Parsing** (upload diagram + IaC):
   ```
   DETECTED COMPONENTS:
   - VPC: 10.0.0.0/16
   - Public Subnet: ALB, NAT Gateway
   - Private Subnet: EC2 (Java app), RDS MySQL
   - IAM Roles: app-role, deployment-role, admin-role
   - S3 Buckets: app-logs, user-uploads, backups
   - Security Groups: web-sg, app-sg, db-sg
   - CloudTrail: Enabled (logs to S3)
   ```

2. **CIS AWS Benchmark Compliance Check**:
   ```
   CIS AWS FOUNDATIONS BENCHMARK v1.5.0 ASSESSMENT
   
   CRITICAL FAILURES (Score 0/5)
   ✗ 1.14: Ensure access keys are rotated every 90 days
     Finding: IAM user "jenkins-deploy" has 247-day-old key
     Risk: T1078.004 (Cloud Accounts) - Stolen key = full access
     Remediation: Rotate key + switch to OIDC federation
   
   ✗ 2.1.2: Ensure S3 buckets are not publicly accessible
     Finding: "user-uploads" bucket has "public-read" ACL
     Risk: T1530 (Data from Cloud Storage) - Anyone can download files
     Remediation: Remove public ACL + require presigned URLs
   
   ✗ 2.3.1: Ensure RDS instances are not public
     Finding: RDS "app-db-prod" has PubliclyAccessible=true
     Risk: T1190 (Exploit Public-Facing Application) - Database exposed to internet
     Remediation: Set PubliclyAccessible=false + use bastion host
   
   ✗ 3.1: Ensure CloudTrail log file validation is enabled
     Finding: CloudTrail missing log file integrity validation
     Risk: T1562.008 (Impair Defenses: Disable Cloud Logs) - Attacker can tamper logs
     Remediation: Enable log validation + CloudWatch alarms
   
   ✗ 4.3: Ensure VPC flow logging is enabled
     Finding: VPC missing flow logs
     Risk: Blind spot for lateral movement detection
     Remediation: Enable VPC Flow Logs → CloudWatch Logs
   
   HIGH SEVERITY (Score 2/5)
   ⚠ 1.5: Ensure MFA is enabled for root account
     Finding: MFA configured, but no email alert on root login
     Recommendation: Add SNS alert for root account activity
   
   ⚠ 2.1.1: Ensure S3 bucket access logging is enabled
     Finding: "backups" bucket missing access logs
     Risk: Can't audit who accessed sensitive backup data
     Remediation: Enable S3 server access logging
   
   OVERALL SCORE: 45/100 (FAILING)
   Critical Issues: 5
   High Issues: 2
   Medium Issues: 8
   Low Issues: 12
   ```

3. **ATT&CK Cloud Matrix Analysis**:
   ```
   MITRE ATT&CK CLOUD THREAT MODEL
   
   Initial Access (3 vectors identified)
   T1078.004: Valid Cloud Accounts
     - Old IAM access key for "jenkins-deploy"
     - No MFA on IAM users
     - Overly permissive admin-role (AdministratorAccess policy)
     Likelihood: HIGH (key likely leaked in Jenkins logs)
   
   T1190: Exploit Public-Facing Application
     - RDS database publicly accessible
     - ALB accepts traffic from 0.0.0.0/0
     Likelihood: MEDIUM (depends on app vulnerabilities)
   
   T1530: Data from Cloud Storage
     - S3 "user-uploads" bucket publicly readable
     - Found 1,247 files including PII (scanned sample)
     Likelihood: CRITICAL (already exposed, may be indexed by Google)
   
   Persistence (2 vectors identified)
   T1098.001: Additional Cloud Credentials
     - IAM role "app-role" can create new IAM users
     - No detection for unusual IAM actions
     Attacker could: Create backdoor IAM user
   
   T1136.003: Create Cloud Account
     - Root account doesn't require approval workflow
     - No AWS Organizations SCPs to restrict
     Attacker could: Spin up resources in new accounts
   
   Defense Evasion (3 vectors identified)
   T1562.008: Disable Cloud Logs
     - CloudTrail not immutable (can be deleted)
     - No SNS alert on CloudTrail changes
     Attacker could: Disable logging before attacking
   
   T1562.007: Disable or Modify Cloud Firewall
     - Security groups editable by "app-role"
     - No audit of security group changes
     Attacker could: Open port 3306 to 0.0.0.0/0 before attacking DB
   
   OVERALL CLOUD SECURITY POSTURE: POOR
   Attack Surface: LARGE (multiple easy entry points)
   Detection Capability: LOW (minimal logging/alerting)
   Time to Compromise (estimated): <24 hours
   ```

4. **Exploitability Assessment**:
   ```
   RED TEAM POV: HOW WE'D BREAK IN
   
   Path 1: Steal Jenkins IAM Key (Fastest - 2 hours)
   1. Search public GitHub for "jenkins-deploy" leaked keys
   2. If found, use aws-cli to enumerate resources
   3. Download all data from "user-uploads" S3 bucket
   4. Pivot: Use stolen key to modify security groups
   5. Open RDS port 3306 to attacker IP
   6. Connect to RDS, dump database
   7. Disable CloudTrail, erase evidence
   Total time: 2 hours | Skill level: Low
   
   Path 2: Exploit Public RDS (Medium - 8 hours)
   1. Nmap scan finds RDS on 3306
   2. Brute force weak RDS password (if any)
   3. Or exploit MySQL CVE if unpatched
   4. Dump database including credentials
   5. Use app credentials to access ALB backend
   6. Pivot to EC2 instance via SSRF
   Total time: 8 hours | Skill level: Medium
   
   Path 3: Public S3 Bucket → Lateral Movement (Slow - 24 hours)
   1. Enumerate public S3 buckets (bucket name guessing)
   2. Download "user-uploads" files
   3. Extract credentials from uploaded files (e.g., API keys in logs)
   4. Use found credentials to access app
   5. Exploit app SSRF to hit EC2 metadata service
   6. Steal EC2 instance role credentials
   Total time: 24 hours | Skill level: Low-Medium
   ```

5. **Automated Remediation Plan**:
   ```
   TERRAFORM FIXES (Apply before deployment)
   
   # Fix 1: Remove public RDS access
   resource "aws_db_instance" "app_db" {
   - publicly_accessible = true
   + publicly_accessible = false
   }
   
   # Fix 2: Remove public S3 bucket ACL
   resource "aws_s3_bucket_acl" "user_uploads" {
   - acl = "public-read"
   + acl = "private"
   }
   
   # Fix 3: Enable VPC Flow Logs
   + resource "aws_flow_log" "vpc_flow_log" {
   +   vpc_id          = aws_vpc.main.id
   +   traffic_type    = "ALL"
   +   log_destination = aws_cloudwatch_log_group.flow_log.arn
   + }
   
   # Fix 4: Restrict IAM role permissions
   resource "aws_iam_role_policy" "app_role" {
   - policy = data.aws_iam_policy_document.admin_access.json
   + policy = data.aws_iam_policy_document.least_privilege.json  # New restricted policy
   }
   
   # Fix 5: Enable CloudTrail log validation
   resource "aws_cloudtrail" "main" {
     name           = "main-trail"
   + enable_log_file_validation = true
   + sns_topic_name = aws_sns_topic.cloudtrail_alerts.name
   }
   
   ESTIMATED IMPACT:
   - Deployment delay: 2 days (testing required)
   - Cost increase: +$50/month (Flow Logs, CloudWatch)
   - Attack surface reduction: 80%
   - Compliance score: 45 → 85 (PASSING)
   ```

6. **Detective Control Recommendations**:
   ```
   AWS-SPECIFIC DETECTION RULES (Deploy via CloudWatch → SNS → SIEM)
   
   Alert 1: Public S3 Bucket Created
   Trigger: S3 bucket ACL changed to "public-read" or "public-read-write"
   Response: Auto-remediate (Lambda removes public ACL)
   
   Alert 2: RDS Made Public
   Trigger: RDS instance ModifyDBInstance with PubliclyAccessible=true
   Response: Page on-call engineer + require approval ticket
   
   Alert 3: IAM Access Key Age > 90 Days
   Trigger: Daily Lambda scan of IAM keys
   Response: Email key owner + auto-disable after 120 days
   
   Alert 4: CloudTrail Disabled
   Trigger: CloudTrail StopLogging API call
   Response: CRITICAL page to SOC + auto-restart CloudTrail
   
   Alert 5: Root Account Login
   Trigger: CloudTrail ConsoleLogin from root account
   Response: SMS alert to CISO + Slack message to #security
   
   Alert 6: Security Group Opens 0.0.0.0/0
   Trigger: AuthorizeSecurityGroupIngress with 0.0.0.0/0
   Response: Auto-revert rule + create Jira ticket
   ```

7. **Control Mapping Summary**:
   ```
   COMPLIANCE FRAMEWORK COVERAGE
   
   CIS AWS Benchmark:
   ├─ Before: 45/100 (FAIL)
   └─ After fixes: 85/100 (PASS)
   
   NIST CSF (Cloud Controls):
   ├─ PR.AC-4 (Access Permissions): ✓ Fixed IAM overpermissioning
   ├─ PR.DS-1 (Data at Rest): ⚠ Need to enable S3/RDS encryption
   ├─ DE.CM-1 (Network Monitoring): ✓ VPC Flow Logs enabled
   └─ RS.AN-1 (Notifications): ✓ CloudWatch alarms configured
   
   SOC2 (Cloud-Specific):
   ├─ CC6.1 (Logical Access): ✓ MFA required, IAM least privilege
   ├─ CC6.6 (Encryption): ⚠ Partial (in transit ✓, at rest ✗)
   └─ CC7.2 (Monitoring): ✓ CloudTrail + Flow Logs
   ```

**Time saved:** 3 days of manual review → 1 hour  
**Risk reduction:** Critical issues found before production

---

## **Meta Use Case: The "AI Security Analyst" Daily Standup**

Every morning, the system proactively generates a security intelligence brief:

```
DAILY SECURITY INTELLIGENCE BRIEF
Generated: 2024-12-20 08:00 UTC

NEW THREATS (Last 24 hours)
1. CVE-2024-50349 published (CVSS 9.8, affects Python library you use)
   → See "Use Case 1" analysis above
   
2. CISA added CVE-2024-12345 to KEV (Log4j variant)
   → Your systems: 0 affected (phased out Log4j last year)
   → Action: None required ✓
   
3. AlienVault OTX: New APT29 campaign targeting healthcare
   → Your industry: ✓ Healthcare
   → ATT&CK techniques: T1566.001 (Phishing), T1078 (Valid Accounts)
   → Your controls: ⚠ MFA not enforced on VPN (GAP)
   → Recommendation: Enable MFA this week

UPCOMING COMPLIANCE DEADLINES
- SOC2 audit: 18 days (3 critical gaps remaining)
- HIPAA risk assessment: 45 days (on track)
- CIS benchmark review: 90 days (not started)

YOUR SECURITY POSTURE TRENDS (Last 30 days)
✓ Improved: Patch compliance 67% → 82%
✗ Degraded: Mean time to detect 28min → 45min (EDR coverage dropped)
→ Unchanged: Control coverage 78%

TOP 5 RISKS REQUIRING ATTENTION
1. No PAM solution (enables T1078, T1550 - CRITICAL)
2. Dev environment lacks encryption (SOC2 audit blocker)
3. VPN lacks MFA (APT29 campaign risk)
4. EDR coverage gap: 47 endpoints missing agent
5. Old IAM access key in Jenkins (247 days old)

RECOMMENDED ACTIONS TODAY
□ Rotate Jenkins IAM key (15min)
□ Enable MFA on VPN (2hr)
□ Review SOC2 gap analysis report (30min)
```

---

## Summary: What Makes This Different

Traditional security tools give you **data**. This system gives you **decisions**:

| Traditional | AI-Powered |
|---|---|
| "Here are 10,000 CVEs" | "Here are the 3 CVEs that affect you, how to detect exploitation, and which controls mitigate them" |
| "SOC2 is 400 pages" | "You're missing these 5 controls. Here's the evidence you need. You'll probably fail the audit without fixing #2." |
| "Investigate this alert" | "This alert is likely a lateral movement attempt. Here's the attack chain, what to block, and what to search for in your logs." |
| "Read the ATT&CK matrix" | "Your architecture is vulnerable to these 8 techniques. Red team will probably use paths #1 or #3. Fix these before they arrive." |
| "Review this cloud config" | "This RDS is publicly accessible. An attacker could compromise it in 8 hours. Here's the Terraform fix." |

The value is **synthesis** — connecting CVEs ↔ ATT&CK ↔ Controls ↔ Your Infrastructure ↔ Actionable Response.

Want me to design the LangGraph agent topology that orchestrates these workflows, or dive deeper into any specific use case?
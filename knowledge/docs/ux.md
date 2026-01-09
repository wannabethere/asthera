I can see you're working with a regulatory change management system (4RISK.ai). Let me design mockups that integrate the compliance tracking workflow into your existing interface, connecting regulatory alerts to compliance controls.

# **Compliance Tracking Integration Mockups**

## **1. Compliance Portfolio Entry Point**

```
┌─────────────────────────────────────────────────────────────────┐
│ 4●RISK.ai    Dashboards    My Portfolio    [+Compliance Goals]  │
├─────────────────────────────────────────────────────────────────┤
│ Home > My Portfolio > Compliance Tracking                        │
│                                                                   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 🎯 Active Compliance Goals                                   │ │
│ │                                                              │ │
│ │ ┌──────────────────┐  ┌──────────────────┐  ┌────────────┐ │ │
│ │ │ SOC2 NA Region   │  │ HIPAA PHI Access │  │ + New Goal │ │ │
│ │ │ 📊 12/47 Complete│  │ 📊 8/23 Complete │  │            │ │ │
│ │ │ ⚠️  5 Gaps       │  │ ✓ On Track       │  │            │ │ │
│ │ │ 🔔 3 Alerts      │  │ 🔔 1 Alert       │  │            │ │ │
│ │ └──────────────────┘  └──────────────────┘  └────────────┘ │ │
│ └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## **2. Compliance Goal Setup (Conversational Flow)**

```
┌─────────────────────────────────────────────────────────────────┐
│ 4●RISK.ai                                         [← Back] [✕]  │
├─────────────────────────────────────────────────────────────────┤
│ New Compliance Goal                                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  💬 Compliance Co-Pilot                                         │
│  ─────────────────────────────────────────────────────────────  │
│                                                                   │
│  🤖 Let's set up your compliance monitoring. Tell me your goal: │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ My CISO wants to understand where we stand with SOC2        ││
│  │ compliance for north america region. He would like me to    ││
│  │ address any issues with urgency in the next few months and  ││
│  │ close the gap. In addition he wants weekly progress report  ││
│  │                                                              ││
│  │                                          [Send →]            ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                   │
│  🤖 Perfect! I understand:                                      │
│      • Framework: SOC2                                           │
│      • Region: North America                                    │
│      • Timeline: Next few months (Q1 2026)                      │
│      • Reporting: Weekly progress reports                       │
│                                                                   │
│  I found these data sources connected:                          │
│  ✓ CornerStone (Training & Compliance)                          │
│  ✓ AWS Activity (Cloud Security)                                │
│  ✓ Workday (HR & Access)                                        │
│  ✓ Salesforce (Business Processes)                              │
│                                                                   │
│  Should I also connect Vanta/DRATA to import existing           │
│  control mappings?                                               │
│                                                                   │
│  [Yes, Connect Vanta] [No, Start Fresh] [Connect DRATA]        │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## **3. Control Overview with Regulatory Alert Mapping**

```
┌─────────────────────────────────────────────────────────────────┐
│ 4●RISK.ai    SOC2 Compliance - North America      [⚙️ Settings] │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│ ┌───────────────────────────┐  ┌────────────────────────────────┐│
│ │ Control Status            │  │ Linked Regulatory Alerts (3)   ││
│ │                           │  │                                 ││
│ │ Scope                     │  │ ⚠️  Case ID 1265269            ││
│ │ ● SOC2 Trust Services (47)│  │    SEC - Rule Change Impact    ││
│ │                           │  │    Affects: CC6.1, CC6.7       ││
│ │ Framework Coverage        │  │    Due: 6/15/2023              ││
│ │ ◐ 67% Mapped              │  │    [Review Impact →]           ││
│ │                           │  │                                 ││
│ │ Gap Priority              │  │ ℹ️  Case ID 1265270            ││
│ │ 🔴 Critical: 3            │  │    CFP - Guidance Update       ││
│ │ 🟠 High: 5                │  │    Affects: CC2.1              ││
│ │ 🟡 Medium: 4              │  │    Due: 7/1/2023               ││
│ │ 🟢 Low: 0                 │  │    [Review Impact →]           ││
│ │                           │  │                                 ││
│ │ [View All 47 Controls]    │  │ [View All Alerts →]            ││
│ └───────────────────────────┘  └────────────────────────────────┘│
│                                                                   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Control Categories                              [Grid] [List]│ │
│ ├─────────────────────────────────────────────────────────────┤ │
│ │                                                              │ │
│ │ ┌─────────────────────┐  ┌─────────────────────┐            │ │
│ │ │ CC1: Control Env    │  │ CC2: Communication  │            │ │
│ │ │ ◐ 67% Complete      │  │ ◑ 45% Complete      │            │ │
│ │ │ 📋 8 Controls       │  │ 📋 5 Controls       │            │ │
│ │ │ ⚠️  2 Gaps          │  │ ⚠️  3 Gaps (1 Crit) │            │ │
│ │ │ 🔔 1 Alert Linked   │  │ 🔔 1 Alert Linked   │            │ │
│ │ └─────────────────────┘  └─────────────────────┘            │ │
│ │                                                              │ │
│ │ ┌─────────────────────┐  ┌─────────────────────┐            │ │
│ │ │ CC6: Logical Access │  │ CC7: System Ops     │            │ │
│ │ │ ◔ 34% Complete      │  │ ◕ 78% Complete      │            │ │
│ │ │ 📋 12 Controls      │  │ 📋 11 Controls      │            │ │
│ │ │ ⚠️  5 Gaps (2 Crit) │  │ ⚠️  1 Gap           │            │ │
│ │ │ 🔔 2 Alerts Linked  │  │ 🔔 0 Alerts         │            │ │
│ │ └─────────────────────┘  └─────────────────────┘            │ │
│ │                                                              │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│ [Select Controls to Monitor] [Set Up Metrics →]                 │
└─────────────────────────────────────────────────────────────────┘
```

## **4. Control Detail with Metric Suggestions**

```
┌─────────────────────────────────────────────────────────────────┐
│ CC2: Communication & Information        [← Back] [Save] [Next]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 🤖 You selected CC2.1 (Security Awareness) and CC1.1         │ │
│ │    (Code of Conduct). I found these metrics from your        │ │
│ │    connected data sources:                                   │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Suggested Metrics                    [Select All] [Clear]   │ │
│ ├─────────────────────────────────────────────────────────────┤ │
│ │                                                              │ │
│ │ ☑️ Training Completion Rate                                 │ │
│ │    📊 Source: CornerStone                                   │ │
│ │    🎯 Target: 95% (SOC2 Standard)                           │ │
│ │    📈 Current: 73% (⚠️ 22% gap)                             │ │
│ │    └─ Breakdown: By Dept, Role, Region                      │ │
│ │                                                              │ │
│ │ ☑️ Policy Acknowledgment Coverage                           │ │
│ │    📊 Source: CornerStone                                   │ │
│ │    🎯 Target: 100% (Regulatory)                             │ │
│ │    📈 Current: 89% (⚠️ 11% gap)                             │ │
│ │    └─ Breakdown: By Policy Type, Department                 │ │
│ │                                                              │ │
│ │ ☑️ Onboarding Training Compliance (30-day)                  │ │
│ │    📊 Source: CornerStone + Workday                         │ │
│ │    🎯 Target: 100% within 30 days                           │ │
│ │    📈 Current: 82% (⚠️ 18% gap)                             │ │
│ │    └─ Linked to: Workday hire dates                         │ │
│ │                                                              │ │
│ │ ☐ Failed Quiz Attempts                                      │ │
│ │    📊 Source: CornerStone                                   │ │
│ │    🎯 Threshold: < 3 attempts                               │ │
│ │    📈 Current: Avg 1.8 attempts                             │ │
│ │                                                              │ │
│ │ ☐ Training Recency Distribution                             │ │
│ │    📊 Source: CornerStone                                   │ │
│ │    🎯 Target: < 365 days since last training                │ │
│ │    📈 Current: 23% overdue                                  │ │
│ │                                                              │ │
│ │ ☐ Role-Based Training Gaps                                  │ │
│ │    📊 Source: CornerStone + Workday                         │ │
│ │    🎯 Critical roles: Admin, Engineering, Finance           │ │
│ │    📈 Engineering: 58% complete (🔴 Critical)               │ │
│ │                                                              │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 💬 Ask for More Metrics                                      │ │
│ ├─────────────────────────────────────────────────────────────┤ │
│ │ What about phishing simulation data?                         │ │
│ │                                              [Ask →]         │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│ [← Previous] [Configure Risk Scoring →]                         │
└─────────────────────────────────────────────────────────────────┘
```

## **5. Risk Scoring Configuration**

```
┌─────────────────────────────────────────────────────────────────┐
│ Risk Scoring: 3 Metrics Selected           [← Back] [Save Next] │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Metric 1 of 3: Training Completion Rate                      │ │
│ ├─────────────────────────────────────────────────────────────┤ │
│ │                                                              │ │
│ │ Current State                                                │ │
│ │ • Overall: 73% (Target: 95%)                                 │ │
│ │ • Engineering: 58% 🔴                                        │ │
│ │ • Finance: 85% 🟡                                            │ │
│ │ • Sales: 91% 🟢                                              │ │
│ │                                                              │ │
│ │ Risk Dimensions                                              │ │
│ │ ┌────────────────────────────────────────────────────────┐  │ │
│ │ │ Risk Score (Likelihood of Control Failure)             │  │ │
│ │ │ ●───────────○────────  8.2/10 🔴 High                  │  │ │
│ │ │                                                         │  │ │
│ │ │ Factors:                                                │  │ │
│ │ │ • 27% gap from target                                   │  │ │
│ │ │ • Engineering dept critical role (58% complete)         │  │ │
│ │ │ • Historical trend: -3% over last quarter               │  │ │
│ │ │                                                         │  │ │
│ │ │ [Auto-Calculate] [Manual Override: ___]                │  │ │
│ │ └────────────────────────────────────────────────────────┘  │ │
│ │                                                              │ │
│ │ ┌────────────────────────────────────────────────────────┐  │ │
│ │ │ Impact Score (Business/Regulatory Consequence)          │  │ │
│ │ │ ●──────────────○  9.1/10 🔴 Critical                   │  │ │
│ │ │                                                         │  │ │
│ │ │ Factors:                                                │  │ │
│ │ │ • SOC2 Type II requirement: 100% annually               │  │ │
│ │ │ • Audit finding severity: Major non-conformance         │  │ │
│ │ │ • Linked regulatory alert: Case ID 1265270 (CFP)        │  │ │
│ │ │                                                         │  │ │
│ │ │ [Auto-Calculate] [Manual Override: ___]                │  │ │
│ │ └────────────────────────────────────────────────────────┘  │ │
│ │                                                              │ │
│ │ ┌────────────────────────────────────────────────────────┐  │ │
│ │ │ Breach Correlation (Security Incident Likelihood)       │  │ │
│ │ │ ○────●──────────  5.8/10 🟡 Medium                     │  │ │
│ │ │                                                         │  │ │
│ │ │ Factors:                                                │  │ │
│ │ │ • Training gaps correlate with phishing susceptibility  │  │ │
│ │ │ • No direct breach history from this gap                │  │ │
│ │ │ • Industry data: Indirect factor (DBIR 2024)            │  │ │
│ │ │                                                         │  │ │
│ │ │ [Auto-Calculate] [Manual Override: ___]                │  │ │
│ │ └────────────────────────────────────────────────────────┘  │ │
│ │                                                              │ │
│ │ ┌────────────────────────────────────────────────────────┐  │ │
│ │ │ Composite Risk Score                                    │  │ │
│ │ │ ━━━━━━━━━━━━━━━━━━━━━━━━━━  7.8/10 🔴                 │  │ │
│ │ │                                                         │  │ │
│ │ │ Weighted: Risk(0.4) + Impact(0.5) + Breach(0.1)        │  │ │
│ │ │ Formula: (8.2×0.4) + (9.1×0.5) + (5.8×0.1) = 7.8       │  │ │
│ │ │                                                         │  │ │
│ │ │ [Adjust Weights] [Use ML Prediction]                    │  │ │
│ │ └────────────────────────────────────────────────────────┘  │ │
│ │                                                              │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│ [← Previous Metric] [Next Metric: Policy Acknowledgment →]      │
└─────────────────────────────────────────────────────────────────┘
```

## **6. Artifact Generation Summary**

```
┌─────────────────────────────────────────────────────────────────┐
│ Generate Compliance Artifacts              [← Back] [Generate]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 🤖 Based on your selections, I'll create:                    │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 📈 Dashboards (3)                              [Preview All] │ │
│ ├─────────────────────────────────────────────────────────────┤ │
│ │                                                              │ │
│ │ 1. Executive SOC2 Overview                                   │ │
│ │    ├─ Control health heatmap (47 controls)                   │ │
│ │    ├─ Gap closure velocity tracker                           │ │
│ │    ├─ Weekly progress vs. Q1 2026 goal                       │ │
│ │    └─ Top 5 risk indicators                                  │ │
│ │    Format: Weekly digest (Sunday 8AM)                        │ │
│ │    [Preview →]                                               │ │
│ │                                                              │ │
│ │ 2. CC2.1 Training & Awareness Deep Dive                      │ │
│ │    ├─ Training completion by dept (drill-down enabled)       │ │
│ │    ├─ Policy acknowledgment trends                           │ │
│ │    ├─ Onboarding compliance funnel                           │ │
│ │    └─ Risk-adjusted compliance score                         │ │
│ │    [Preview →]                                               │ │
│ │                                                              │ │
│ │ 3. Alert-Triggered Investigation Dashboard                   │ │
│ │    ├─ Real-time anomaly detection                            │ │
│ │    ├─ Linked regulatory alerts (from Events feed)            │ │
│ │    └─ Remediation action tracker                             │ │
│ │    [Preview →]                                               │ │
│ │                                                              │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 🔄 Automations (4)                             [Configure]   │ │
│ ├─────────────────────────────────────────────────────────────┤ │
│ │                                                              │ │
│ │ ☑️ Daily: CornerStone → Compliance Data Lake Sync           │ │
│ │    Runs: 2:00 AM PST                                         │ │
│ │    Tables: training_records, quiz_results, certifications    │ │
│ │                                                              │ │
│ │ ☑️ Weekly: CISO Report Generation                           │ │
│ │    Runs: Sunday 8:00 AM PST                                  │ │
│ │    Recipients: [email protected], grc-team@               │ │
│ │    Format: PDF + Interactive Dashboard Link                  │ │
│ │                                                              │ │
│ │ ☑️ Real-time: Workday Termination → Training Cleanup        │ │
│ │    Trigger: Employee status change to "Terminated"           │ │
│ │    Action: Archive training records, update compliance calc  │ │
│ │                                                              │ │
│ │ ☑️ Weekly: Vanta Evidence Auto-Upload                       │ │
│ │    Runs: Friday 5:00 PM PST                                  │ │
│ │    Controls: CC2.1, CC1.1, CC6.1                             │ │
│ │    Files: Training reports, access logs                      │ │
│ │                                                              │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 🚨 Alerts (4)                                  [Configure]   │ │
│ ├─────────────────────────────────────────────────────────────┤ │
│ │                                                              │ │
│ │ ☑️ Training Completion < 95%                                │ │
│ │    Check: Every Friday 5PM                                   │ │
│ │    Notify: #security-compliance (Slack), grc-team@ (Email)   │ │
│ │    Severity: 🟡 Medium                                       │ │
│ │    └─ Escalate to 🔴 High if Engineering < 60%              │ │
│ │                                                              │ │
│ │ ☑️ New Employee Missing Training (30-day threshold)         │ │
│ │    Check: Real-time on Workday sync                          │ │
│ │    Notify: HR Manager, Employee's Manager                    │ │
│ │    Severity: 🟠 High                                         │ │
│ │                                                              │ │
│ │ ☑️ Regulatory Alert Impacts Tracked Controls                │ │
│ │    Check: When new alert added to Events feed                │ │
│ │    Notify: CISO, GRC Lead                                    │ │
│ │    Severity: 🔴 Critical (if due date < 30 days)            │ │
│ │    └─ Auto-create task in compliance workflow                │ │
│ │                                                              │ │
│ │ ☑️ Risk Score Threshold Breach (> 8.0)                      │ │
│ │    Check: Daily at 9AM                                       │ │
│ │    Notify: CISO, Control Owner                               │ │
│ │    Severity: 🔴 Critical                                     │ │
│ │                                                              │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 🔗 Integrations                                [Configure]   │ │
│ ├─────────────────────────────────────────────────────────────┤ │
│ │                                                              │ │
│ │ ☑️ Vanta: Auto-sync control evidence for CC2.1, CC1.1       │ │
│ │ ☑️ Events Feed: Link regulatory alerts to impacted controls  │ │
│ │ ☐ Jira: Create remediation tickets (Optional)               │ │
│ │ ☐ ServiceNow: Sync to ITSM workflow (Optional)              │ │
│ │                                                              │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│ [← Back to Scoring] [Generate All Artifacts →]                  │
└─────────────────────────────────────────────────────────────────┘
```

## **7. Dashboard Preview: Executive Overview**

```
┌─────────────────────────────────────────────────────────────────┐
│ 4●RISK.ai    Dashboards > SOC2 NA Compliance      📅 Week 2/12 │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ SOC2 North America - Executive Overview                      │ │
│ │                                           Last Updated: 1/8   │ │
│ ├─────────────────────────────────────────────────────────────┤ │
│ │                                                              │ │
│ │ ┌──────────────────┐  ┌──────────────────┐  ┌────────────┐ │ │
│ │ │ Overall Health   │  │ Gap Closure      │  │ Alerts     │ │ │
│ │ │ ◐ 67%            │  │ +5% This Week    │  │ 🔔 3 Active│ │ │
│ │ │ 12/47 Complete   │  │ On Track ✓       │  │ 1 Critical │ │ │
│ │ └──────────────────┘  └──────────────────┘  └────────────┘ │ │
│ │                                                              │ │
│ │ Control Category Heatmap                        [Export PNG]│ │
│ │ ┌────────────────────────────────────────────────────────┐  │ │
│ │ │         Week 1  Week 2  Week 3  Week 4  Goal (Week 12) │  │ │
│ │ │ CC1     🟢 67%  🟢 72%  ⬜     ⬜     ⬜ 100%        │  │ │
│ │ │ CC2     🔴 45%  🟡 52%  ⬜     ⬜     ⬜ 100%        │  │ │
│ │ │ CC6     🔴 34%  🔴 38%  ⬜     ⬜     ⬜ 100%        │  │ │
│ │ │ CC7     🟢 78%  🟢 81%  ⬜     ⬜     ⬜ 100%        │  │ │
│ │ │ CC8     🟡 56%  🟡 60%  ⬜     ⬜     ⬜ 100%        │  │ │
│ │ └────────────────────────────────────────────────────────┘  │ │
│ │                                                              │ │
│ │ Top Risk Indicators                          [View All (12)]│ │
│ │ ┌────────────────────────────────────────────────────────┐  │ │
│ │ │ 1. CC2.1: Training Completion          🔴 Risk: 7.8/10 │  │ │
│ │ │    Current: 73% | Target: 95% | Gap: 22%               │  │ │
│ │ │    🔗 Linked Alert: Case ID 1265270 (CFP Guidance)     │  │ │
│ │ │    [View Details →]                                     │  │ │
│ │ │                                                         │  │ │
│ │ │ 2. CC6.1: MFA Enforcement              🟠 Risk: 6.4/10 │  │ │
│ │ │    Current: 82% | Target: 100% | Gap: 18%              │  │ │
│ │ │    🔗 Linked Alert: Case ID 1265269 (SEC Rule)         │  │ │
│ │ │    [View Details →]                                     │  │ │
│ │ │                                                         │  │ │
│ │ │ 3. CC1.1: Policy Acknowledgment        🟡 Risk: 5.2/10 │  │ │
│ │ │    Current: 89% | Target: 100% | Gap: 11%              │  │ │
│ │ │    [View Details →]                                     │  │ │
│ │ └────────────────────────────────────────────────────────┘  │ │
│ │                                                              │ │
│ │ Regulatory Alert Impact                      [View Events →]│ │
│ │ ┌────────────────────────────────────────────────────────┐  │ │
│ │ │ ⚠️  3 Active Alerts Affecting Your Controls            │  │ │
│ │ │                                                         │  │ │
│ │ │ • Case 1265270: CFP Guidance → CC2.1 (Due: 2/1/2026)   │  │ │
│ │ │ • Case 1265269: SEC Rule → CC6.1, CC6.7 (Due: 6/15)    │  │ │
│ │ │ • Case 1265268: CFTC Notice → CC8.2 (Due: 3/1/2026)    │  │ │
│ │ │                                                         │  │ │
│ │ │ [Review Impact Analysis →]                              │  │ │
│ │ └────────────────────────────────────────────────────────┘  │ │
│ │                                                              │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│ [← Back to Portfolio] [View Training Dashboard] [Weekly Report]│
└─────────────────────────────────────────────────────────────────┘
```

## **8. Control Deep Dive with Metric Details**

```
┌─────────────────────────────────────────────────────────────────┐
│ CC2.1: Security Awareness Training         [← Back] [Export]    │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│ ┌───────────────────────────┐  ┌────────────────────────────────┐│
│ │ Control Summary           │  │ Risk Profile                   ││
│ │                           │  │                                 ││
│ │ Status: ⚠️ Gap Identified │  │ Risk Score:    🔴 7.8/10       ││
│ │ Completion: 52%           │  │ Impact Score:  🔴 9.1/10       ││
│ │ Target: 100%              │  │ Breach Score:  🟡 5.8/10       ││
│ │ Due: Q1 2026              │  │                                 ││
│ │                           │  │ Last Updated: 1/8/2026          ││
│ │ Linked Alerts: 1          │  │ Next Review: 1/15/2026          ││
│ │ Evidence Files: 3         │  │                                 ││
│ │                           │  │ [Recalculate Risk]              ││
│ └───────────────────────────┘  └────────────────────────────────┘│
│                                                                   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Metrics (3 Active)                         [+ Add Metric]   │ │
│ ├─────────────────────────────────────────────────────────────┤ │
│ │                                                              │ │
│ │ 📊 Training Completion Rate                                 │ │
│ │ ┌────────────────────────────────────────────────────────┐  │ │
│ │ │ Overall: 73% ━━━━━━━━━━━━━━━━━━○────── Target: 95%   │  │ │
│ │ │                                                         │  │ │
│ │ │ By Department:                           [Drill Down ↓]│  │ │
│ │ │ • Engineering  58% ━━━━━━━━━━○─────────────  🔴       │  │ │
│ │ │ • Finance      85% ━━━━━━━━━━━━━━━━○───────  🟡       │  │ │
│ │ │ • Sales        91% ━━━━━━━━━━━━━━━━━━○─────  🟢       │  │ │
│ │ │ • Marketing    88% ━━━━━━━━━━━━━━━━━○──────  🟡       │  │ │
│ │ │ • Operations   76% ━━━━━━━━━━━━○───────────  🟠       │  │ │
│ │ │                                                         │  │ │
│ │ │ Trend (Last 4 Weeks):                                   │  │ │
│ │ │ 70% → 71% → 72% → 73% (+3% total) 📈                   │  │ │
│ │ │                                                         │  │ │
│ │ │ 🔔 Alert: Engineering < 60% threshold                   │  │ │
│ │ │    Triggered: 1/5/2026 | Notified: CISO, Eng Manager   │  │ │
│ │ └────────────────────────────────────────────────────────┘  │ │
│ │                                                              │ │
│ │ 📊 Policy Acknowledgment Coverage                           │ │
│ │ ┌────────────────────────────────────────────────────────┐  │ │
│ │ │ Overall: 89% ━━━━━━━━━━━━━━━━━○─── Target: 100%      │  │ │
│ │ │                                                         │  │ │
│ │ │ By Policy Type:                                         │  │ │
│ │ │ • Security Policy       95% ━━━━━━━━━━━━━━━━━━━○─ ✓   │  │ │
│ │ │ • Privacy Policy        92% ━━━━━━━━━━━━━━━━━━○── ✓   │  │ │
│ │ │ • Data Handling         87% ━━━━━━━━━━━━━━━━○──── ⚠️   │  │ │
│ │ │ • Acceptable Use        84% ━━━━━━━━━━━━━━━○───── ⚠️   │  │ │
│ │ │                                                         │  │ │
│ │ │ 45 employees pending acknowledgment                     │  │ │
│ │ │ [Export Pending List] [Send Reminder]                   │  │ │
│ │ └────────────────────────────────────────────────────────┘  │ │
│ │                                                              │ │
│ │ 📊 Onboarding Training Compliance (30-day)                  │ │
│ │ ┌────────────────────────────────────────────────────────┐  │ │
│ │ │ Overall: 82% ━━━━━━━━━━━━━━━━○──── Target: 100%      │  │ │
│ │ │                                                         │  │ │
│ │ │ Current Cohort (12 new hires in last 30 days):         │  │ │
│ │ │ • Completed:    10 employees (83%)                      │  │ │
│ │ │ • In Progress:   1 employee (8%)                        │  │ │
│ │ │ • Not Started:   1 employee (8%) 🔴                     │  │ │
│ │ │                                                         │  │ │
│ │ │ 🚨 Alert: Sarah Chen (Engineering) - Day 28/30          │  │ │
│ │ │    Hired: 12/10/2025 | Training: Not started            │  │ │
│ │ │    [Send Escalation] [View Profile]                     │  │ │
│ │ └────────────────────────────────────────────────────────┘  │ │
│ │                                                              │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 🔗 Linked Regulatory Alert                                   │ │
│ ├─────────────────────────────────────────────────────────────┤ │
│ │ Case ID 1265270: CFP Guidance Update                         │ │
│ │ Agency: Consumer Financial Protection Bureau                 │ │
│ │ Type: Guidance on Employee Training Requirements             │ │
│ │ Publication: 6/6/2023 | Due: 2/1/2026                       │ │
│ │                                                              │ │
│ │ Impact Analysis:                                             │ │
│ │ • New requirement: Quarterly refresher training              │ │
│ │ • Documentation: Enhanced audit trail requirements           │ │
│ │ • Current gap: Refresher cadence is annual (not quarterly)   │ │
│ │                                                              │ │
│ │ [View Full Alert in Events →] [Update Compliance Plan]      │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 📎 Evidence & Documentation                                  │ │
│ ├─────────────────────────────────────────────────────────────┤ │
│ │ Auto-synced to Vanta: ✓                                      │ │
│ │                                                              │ │
│ │ • training_completion_report_2026_01.csv (CornerStone)       │ │
│ │ • policy_acknowledgment_audit_2026_01.pdf (CornerStone)      │ │
│ │ • new_hire_onboarding_log.xlsx (Workday + CornerStone)       │ │
│ │                                                              │ │
│ │ Last Evidence Upload: 1/7/2026 (Automated)                   │ │
│ │ Next Upload: 1/14/2026                                       │ │
│ │                                                              │ │
│ │ [Manual Upload] [View in Vanta →]                           │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│ [← Back to Overview] [Generate Report] [Configure Alerts]       │
└─────────────────────────────────────────────────────────────────┘
```

## **9. Integration with Existing Events/Alerts Feed**

```
┌─────────────────────────────────────────────────────────────────┐
│ 4●RISK.ai    Home > Events > Alerts          [🔔 Manage My Feed]│
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│ ┌───────────────────────────┐  ┌────────────────────────────────┐│
│ │ Alert Status              │  │ Compliance Impact (New)        ││
│ │                           │  │                                 ││
│ │ Scope                     │  │ ┌────────────────────────────┐ ││
│ │ ● All Sources (128)       │  │ │ 🎯 Linked to Compliance    │ ││
│ │                           │  │ │    Goals: 3 Alerts         │ ││
│ │ Applicability             │  │ │                            │ ││
│ │ 🔴 1 (Critical)           │  │ │ • SOC2 NA: 2 alerts       │ ││
│ │                           │  │ │ • HIPAA PHI: 1 alert       │ ││
│ │ Impact Analyses           │  │ │                            │ ││
│ │ 🔵 1  🟡 1                │  │ │ [View All Linked →]        │ ││
│ │                           │  │ └────────────────────────────┘ ││
│ │ Manage Actions            │  │                                 ││
│ │ 🔴 1 (Urgent)             │  │ ┌────────────────────────────┐ ││
│ │                           │  │ │ 📊 Control Coverage        │ ││
│ │ [Filter Linked to         │  │ │                            │ ││
│ │  Compliance Goals]        │  │ │ Alerts mapped to controls: │ ││
│ │                           │  │ │ CC2.1: 1 alert             │ ││
│ └───────────────────────────┘  │ │ CC6.1: 1 alert             │ ││
│                                 │ │ CC6.7: 1 alert             │ ││
│                                 │ │ CC8.2: 1 alert             │ ││
│                                 │ │                            │ ││
│                                 │ │ [View Mapping →]           │ ││
│                                 │ └────────────────────────────┘ ││
│                                 └────────────────────────────────┘│
│                                                                   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Alerts (with Compliance Linking)               [Sort by ▼]  │ │
│ ├─────────────────────────────────────────────────────────────┤ │
│ │                                                              │ │
│ │ ┌────────────────────────────────────────────────────────┐  │ │
│ │ │ 🎯 Compliance Linked                                    │  │ │
│ │ │ Scope → 🔴 📧 📋 ✉️ 🚨 128                             │  │ │
│ │ │                                                         │  │ │
│ │ │ Case ID 1265270 Self-Regulatory Organizations          │  │ │
│ │ │ CFP: Notice of Guidance on Employee Training            │  │ │
│ │ │ Requirements and Enhanced Documentation Standards       │  │ │
│ │ │                                                         │  │ │
│ │ │ Type: Guidance                                          │  │ │
│ │ │ Agency/Regulatory Source: CFP                           │  │ │
│ │ │ Document Type: Notices                                  │  │ │
│ │ │ Publication Date: 6/6/2023                              │  │ │
│ │ │ Due Date: 2/1/2026 (24 days remaining) ⏰              │  │ │
│ │ │                                                         │  │ │
│ │ │ 🎯 Compliance Impact:                                   │  │ │
│ │ │ • SOC2 NA: CC2.1 (Security Awareness)                   │  │ │
│ │ │ • Current Risk: 🔴 7.8/10                              │  │ │
│ │ │ • Gap Identified: Quarterly refresher training required │  │ │
│ │ │                                                         │  │ │
│ │ │ [View in Compliance Dashboard →]                        │  │ │
│ │ │                                                         │  │ │
│ │ │ Insight ∨                                               │  │ │
│ │ │ ┌─────────────────────────────────────────────────────┐│  │ │
│ │ │ │ General                                           ─ ││  │ │
│ │ │ │ Topic: employee training requirements guidance      ││  │ │
│ │ │ │        documentation standards                      ││  │ │
│ │ │ │        quarterly refresher training                 ││  │ │
│ │ │ └─────────────────────────────────────────────────────┘│  │ │
│ │ └────────────────────────────────────────────────────────┘  │ │
│ │                                                              │ │
│ │ ┌────────────────────────────────────────────────────────┐  │ │
│ │ │ 🎯 Compliance Linked                                    │  │ │
│ │ │ Scope → 🔴 📧 📋 ✉️ 🚨 128                             │  │ │
│ │ │                                                         │  │ │
│ │ │ Case ID 1265269 Self-Regulatory Organizations          │  │ │
│ │ │ SEC: Rule Change - Enhanced MFA Requirements for        │  │ │
│ │ │ Privileged Access and Audit Trail Retention            │  │ │
│ │ │                                                         │  │ │
│ │ │ Type: Rule Change                                       │  │ │
│ │ │ Agency/Regulatory Source: SEC                           │  │ │
│ │ │ Document Type: Notices                                  │  │ │
│ │ │ Publication Date: 6/6/2023                              │  │ │
│ │ │ Due Date: 6/15/2026 (158 days remaining)               │  │ │
│ │ │                                                         │  │ │
│ │ │ 🎯 Compliance Impact:                                   │  │ │
│ │ │ • SOC2 NA: CC6.1 (Logical Access - MFA)                │  │ │
│ │ │ • SOC2 NA: CC6.7 (Audit Logs)                          │  │ │
│ │ │ • Current Risk: 🟠 6.4/10                              │  │ │
│ │ │                                                         │  │ │
│ │ │ [View in Compliance Dashboard →]                        │  │ │
│ │ │                                                         │  │ │
│ │ │ Insight ∨                                               │  │ │
│ │ └────────────────────────────────────────────────────────┘  │ │
│ │                                                              │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## **Key Design Features**

### **1. Seamless Integration**
- Compliance goals live alongside your existing regulatory alerts
- Alerts automatically link to affected compliance controls
- Bidirectional navigation between Events and Compliance dashboards

### **2. Visual Consistency**
- Uses your existing UI patterns (cards, filters, sidebar navigation)
- Consistent color coding: 🔴 Critical, 🟠 High, 🟡 Medium, 🟢 Low
- Same chart/visualization style as your current dashboards

### **3. Conversational Setup**
- Reduces barrier to entry with guided, AI-assisted configuration
- Progressive disclosure prevents overwhelming users
- Natural language metric suggestions based on available data

### **4. Regulatory Alert Linking**
- Automatically maps incoming alerts to relevant controls
- Shows compliance impact directly in the Events feed
- Creates actionable tasks when alerts affect tracked goals

### **5. Data-Driven Intelligence**
- Risk scoring with transparent calculation methodology
- ML-powered predictions with manual override capability
- Real-time metric updates from connected sources

Would you like me to:
1. **Create interactive prototypes** (HTML/React) of these screens?
2. **Design the LangGraph agent architecture** that powers the conversational flow?
3. **Build the alert-to-control mapping engine** that links regulatory changes to compliance goals?
4. **Develop the dashboard generation templates** with your styling?
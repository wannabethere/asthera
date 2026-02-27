# Metric Decision Tree Engine — Design Update v2

## Incorporating Compliance Artifacts & User-Driven Decision Tree Construction

---

## 1. Context

The v1 decision tree engine scores and groups **metrics** against six decision axes (use_case, goal, focus_area, audience, timeframe, metric_type). However, the DT workflow already retrieves and scores five additional compliance artifact types that are not yet first-class participants in the decision tree:

| Artifact | Source | Current Role | Gap |
|----------|--------|-------------|-----|
| **Frameworks** | `dt_framework_retrieval_node` → Qdrant | Scopes control/risk retrieval | Not a scoring dimension; decision tree doesn't weight framework-specific control structures |
| **Controls** | `scored_context.controls[]` | Input to detection/triage engineers | Used only as a pass-through; decision tree doesn't score metrics *per-control* or build control→metric dependency chains |
| **Risks** | `scored_context.risks[]` | Input to detection/triage engineers | Same gap — no per-risk metric affinity scoring |
| **Scenarios** | `scored_context.scenarios[]` | Input to SIEM rule generation | Completely ignored by the metric decision tree; scenarios define *what to measure* but metrics aren't linked to them |
| **Tests** | `test_cases[]` / `test_scripts[]` | Generated downstream by playbook assembler | No feedback loop — test requirements don't inform which metrics are needed to *evidence* the test |

Additionally, the v1 decision tree is statically defined in code. Users cannot add custom questions, adjust scoring weights, or define organization-specific groups. This limits the engine to Anthropic-authored decision paths and prevents customers from encoding their own compliance posture priorities.

This document addresses both gaps.

---

## 2. Incorporating Compliance Artifacts into the Decision Tree

### 2.1 Design Principle: Artifact-Aware Scoring

Instead of treating compliance artifacts as passthrough context for LLM prompts, the decision tree should use them as **scoring signals** — each artifact type contributes a scoring dimension that influences which metrics are selected and how they're grouped.

The core insight: a metric is most valuable when it can **evidence a control**, **quantify a risk**, **detect a scenario**, or **satisfy a test requirement**. The decision tree should score metrics on these axes, not just on category/keyword matching.

### 2.2 New Scoring Dimensions

Extend the 10-dimension scoring engine with 4 new artifact-linked dimensions:

| New Dimension | Weight | Match Logic | Rationale |
|---------------|--------|-------------|-----------|
| `control_evidence` | 20 | metric can produce evidence that a specific control is operating effectively | SOC2 auditors need metrics that directly map to controls being tested |
| `risk_quantification` | 15 | metric can quantify the likelihood or impact of a specific risk | Risk posture reports need metrics that measure actual risk exposure |
| `scenario_detection` | 10 | metric would change value (alert/deviate) if a specific scenario occurred | Operational monitoring needs metrics that serve as early warning signals |
| `test_satisfaction` | 10 | metric output could serve as evidence for a specific test case | Audit preparation needs metrics that pre-answer test questions |

Updated max score: 150 (existing) + 55 (new) = **205**

### 2.3 Control-Metric Evidence Mapping

#### The Problem

Currently, control→metric mapping happens *after* metric selection — the LLM in the detection/triage engineer generates `mapped_control_codes` as part of its output. This is backwards. The decision tree should select metrics *because* they evidence specific controls.

#### The Design

Each control retrieved from the framework has structured attributes:

```
Control {
    code: "CC7.2"
    name: "Monitors System Components for Anomalies"
    domain: "system_operations"
    type: "detective" | "preventive" | "corrective"
    description: "The entity monitors system components and the operation of those components for anomalies..."
    test_criteria: ["anomaly detection is in place", "monitoring covers all in-scope systems", ...]
}
```

The scoring dimension `control_evidence` evaluates:

1. **Domain alignment** — Does the metric's `focus_area` match the control's `domain`? (e.g., `vulnerability_management` metric for `CC7` system_operations control). Weight: 40% of dimension.

2. **Type compatibility** — Detective controls need monitoring/alerting metrics. Preventive controls need coverage/configuration metrics. Corrective controls need remediation/velocity metrics.

    | Control Type | Preferred Metric Types | Score |
    |---|---|---|
    | detective | count, rate, trend (alert volumes, detection rates) | 1.0 if match |
    | preventive | percentage, score (coverage %, config compliance score) | 1.0 if match |
    | corrective | rate, trend (MTTR, remediation velocity) | 1.0 if match |
    | any type → any metric type | | 0.3 (partial) |

    Weight: 30% of dimension.

3. **Test criteria keyword overlap** — Do the control's `test_criteria` keywords appear in the metric's `natural_language_question`, `description`, or `kpis`? This catches semantic alignment that domain/type matching misses. Weight: 30% of dimension.

#### Scoring Formula

```
control_evidence_score = max over all scored_controls of:
    (0.4 × domain_match) + (0.3 × type_compatibility) + (0.3 × keyword_overlap)
```

The max-over-controls approach means a metric only needs to evidence *one* control well to score high. The specific control it best evidences is recorded as `best_control_match` on the scored metric for downstream traceability.

### 2.4 Risk-Metric Quantification Mapping

#### The Problem

Risks have `likelihood` and `impact` attributes but no systematic link to metrics that would *measure* whether the risk is materializing. The triage engineer generates these links via LLM, but the decision tree should pre-compute them.

#### The Design

Each risk from the framework:

```
Risk {
    risk_code: "R-003"
    name: "Unpatched Critical Vulnerabilities"
    category: "technical"
    likelihood: "high"
    impact: "critical"
    description: "Critical vulnerabilities remain unpatched beyond SLA..."
    mitigating_controls: ["CC7.1", "CC7.2"]
    risk_indicators: ["open critical CVEs > 0", "patch SLA breach count > threshold"]
}
```

The `risk_quantification` dimension evaluates:

1. **Risk indicator match** — Do the risk's `risk_indicators` semantically align with the metric's `natural_language_question` or `kpis`? This is the strongest signal — if a risk explicitly states "open critical CVEs > 0" and a metric measures "Vulnerability Count by Severity", that's a direct match. Weight: 50% of dimension.

2. **Category alignment** — Does the risk's `category` map to the metric's `focus_area`?

    | Risk Category | Metric Focus Areas |
    |---|---|
    | technical | vulnerability_management, incident_response |
    | operational | audit_logging, change_management |
    | compliance | training_compliance, access_control, audit_logging |
    | strategic | data_protection |

    Weight: 25% of dimension.

3. **Mitigating control overlap** — If the risk's `mitigating_controls` overlap with the metric's `mapped_control_domains`, the metric helps measure whether the mitigation is working. Weight: 25% of dimension.

#### Impact-Based Weighting

High-impact risks should pull more metrics toward them. After computing the base `risk_quantification` score, apply an impact multiplier:

| Risk Impact | Multiplier |
|---|---|
| critical | 1.0 |
| high | 0.85 |
| medium | 0.65 |
| low | 0.4 |

This ensures metrics that evidence critical risks are ranked higher than equivalent metrics for low risks.

### 2.5 Scenario-Metric Detection Mapping

#### The Problem

Scenarios describe *what could go wrong* (e.g., "Attacker gains admin access via compromised MFA token"). The DT workflow uses scenarios to generate SIEM rules but not to select metrics. A metric that would deviate during a scenario is a valuable early-warning indicator.

#### The Design

Each scenario:

```
Scenario {
    scenario_id: "S-012"
    name: "MFA Bypass via Session Hijacking"
    severity: "high"
    description: "Adversary captures a valid session token..."
    attack_techniques: ["T1539", "T1550.001"]
    affected_controls: ["CC6.1", "CC6.3"]
    observable_indicators: ["unusual login location", "session reuse from new IP", "MFA challenge skipped"]
}
```

The `scenario_detection` dimension evaluates:

1. **Observable indicator → metric alignment** — Would the metric's measured value change if the scenario's `observable_indicators` occurred? For example, "session reuse from new IP" aligns with a metric tracking "authentication anomaly count". This requires keyword matching between indicator text and metric `data_filters` + `natural_language_question`. Weight: 60% of dimension.

2. **Affected control overlap** — If the scenario affects controls that the metric evidences (from `control_evidence` scoring), the metric is doubly valuable — it both evidences the control and detects when it fails. Weight: 40% of dimension.

#### Scenario Severity Weighting

Same pattern as risk impact — high-severity scenarios pull more metrics:

| Severity | Multiplier |
|---|---|
| critical | 1.0 |
| high | 0.85 |
| medium | 0.65 |
| low | 0.4 |

### 2.6 Test-Metric Satisfaction Mapping

#### The Problem

Test cases define what an auditor or internal team needs to verify. Each test has acceptance criteria that often translate directly to "show me a metric that proves X." The decision tree should pre-match metrics to test requirements so the triage engineer can reference them.

#### The Design

Each test case:

```
TestCase {
    test_id: "T-CC7.2-001"
    name: "Verify anomaly detection monitoring"
    control_code: "CC7.2"
    test_type: "inquiry" | "observation" | "inspection" | "reperformance"
    acceptance_criteria: [
        "Evidence that anomaly detection tools are deployed",
        "Alerting thresholds are configured and documented",
        "Alert volume trends show system is actively detecting"
    ]
    evidence_types: ["screenshot", "metric_export", "log_sample", "policy_document"]
}
```

The `test_satisfaction` dimension evaluates:

1. **Evidence type match** — If the test's `evidence_types` includes `metric_export` or the test type is `inspection`/`reperformance`, the test explicitly needs metric-based evidence. Weight: 30%.

2. **Acceptance criteria → metric alignment** — Keyword matching between `acceptance_criteria` text and metric `natural_language_question` + `kpis` + `description`. Weight: 50%.

3. **Control code match** — The test's `control_code` matches the metric's `best_control_match` from the control_evidence dimension. Weight: 20%.

The test_satisfaction score is highest when a metric directly answers one of the test's acceptance criteria with exportable data.

### 2.7 Artifact-Enriched Group Assignment

With the four new scoring dimensions, the grouping algorithm gains richer context for slot assignment:

**KPI slot preference adjustment:**
- Metrics with high `control_evidence` scores → prefer KPI slot (controls need clear KPIs)
- Metrics with high `risk_quantification` scores → prefer KPI slot if risk impact is critical/high
- Metrics with high `scenario_detection` scores → prefer trend slot (detection is temporal)
- Metrics with high `test_satisfaction` scores → prefer metric slot (evidence is point-in-time)

**New group metadata fields:**

Each group in the output gains:

```
{
    "evidenced_controls": ["CC7.1", "CC7.2"],     // controls covered by metrics in this group
    "quantified_risks": ["R-003", "R-007"],        // risks measured by metrics in this group
    "detected_scenarios": ["S-012"],                // scenarios detectable by metrics in this group  
    "satisfied_tests": ["T-CC7.2-001"],             // tests answerable by metrics in this group
    "coverage_gaps": {
        "unevidenced_controls": ["CC6.3"],          // controls with no metric match
        "unquantified_risks": ["R-011"],            // risks with no metric match
        "unsatisfied_tests": ["T-CC6.3-002"],       // tests with no metric evidence
    }
}
```

This transforms the coverage report from "how many metrics per group" into "which compliance obligations are actually being measured."

### 2.8 Cross-Artifact Dependency Chains

The richest value comes from tracing the full chain:

```
Framework → Control → Risk (mitigated by control) → Scenario (exploits risk) → 
    Test (verifies control) → Metric (evidences control, quantifies risk, detects scenario, satisfies test)
```

The decision tree should build these chains during scoring and expose them as `dependency_chains` on each metric:

```
{
    "metric_id": "vuln_count_by_severity",
    "dependency_chains": [
        {
            "framework": "soc2",
            "control": "CC7.1",
            "risks": ["R-003"],
            "scenarios": ["S-015"],
            "tests": ["T-CC7.1-001", "T-CC7.1-003"],
            "chain_strength": 0.87   // product of individual dimension scores
        }
    ]
}
```

Chain strength is the product of the four artifact dimension scores for that specific chain. Metrics with multiple strong chains are the most valuable — they evidence multiple controls, quantify multiple risks, and satisfy multiple tests simultaneously.

---

## 3. User-Driven Decision Tree Construction

### 3.1 Design Principle: Progressive Enrichment

Users should not need to build a decision tree from scratch. Instead, the system provides the default tree (v1) and users progressively enrich it:

1. **Confirm defaults** — System auto-resolves; user accepts or overrides
2. **Add context** — User adds organization-specific options, weights, or groups
3. **Define custom trees** — Power users define entirely new question branches

This mirrors how the existing `registry_unified.py` works: a static template set with user-configurable overrides.

### 3.2 User Input Surfaces

Four input mechanisms, from simplest to most powerful:

#### Surface 1: Conversational Setup (Inline in Chat)

The simplest input — the interactive clarification node already supports this. Extend it to also collect:

- **Custom focus areas** — "Our team also tracks supply chain security — add that as a focus area"
- **Weight adjustments** — "Risk exposure is more important than training for us"  
- **Organization-specific mappings** — "We use 'CC6.1-custom' for our enhanced access control"

This requires no new UI. The `dt_metric_decision_interactive_node` processes natural language inputs and updates the decision tree state.

**Design approach:** The interactive node sends the user's custom input to an LLM with the current decision tree structure as context. The LLM extracts structured modifications:

```
User: "We care most about vulnerability remediation SLA compliance for our SOC2 audit"

LLM extracts → {
    "weight_overrides": {"focus_area.vulnerability_management": 1.2},
    "goal_override": "remediation_velocity",
    "custom_kpi_hints": ["SLA compliance rate", "overdue critical vulns"],
    "use_case_confirmed": "soc2_audit"
}
```

These overrides are stored in state as `dt_user_tree_overrides` and applied during scoring as multipliers on the base weights.

#### Surface 2: Setup Questionnaire (Pre-Workflow)

A structured form presented before the DT workflow runs. Collects decisions explicitly rather than relying on auto-resolve. Designed for compliance teams setting up recurring audit metric packages.

**Questionnaire flow:**

```
Step 1: Use Case Selection
    "What are you building metrics for?"
    → [SOC2 Audit] [LMS Learning Target] [Risk Report] [Custom...]

Step 2: Framework & Scope
    "Which frameworks are in scope?"
    → [SOC2] [HIPAA] [NIST AI RMF] [Multiple...]
    "Which control domains matter most?"
    → Drag-and-drop ranking of control domains
    
Step 3: Data Source Confirmation  
    "Which security tools are connected?"
    → Checklist auto-populated from tenant profile
    → Affects data_source scoring dimension

Step 4: Priority Weighting
    "Rank what matters most for your metrics:"
    → Drag-and-drop ranking:
        Control Evidence (proving controls work)
        Risk Quantification (measuring risk exposure)
        Scenario Detection (early warning signals)
        Test Satisfaction (audit evidence readiness)
    → Converts to weight multipliers

Step 5: Custom Additions (optional)
    "Any specific metrics or KPIs you always need?"
    → Free text or selection from metric registry
    "Any metrics you want to exclude?"
    → Selection from metric registry
    "Custom groups to organize metrics by?"
    → Free text group names + descriptions
```

**Output:** A `decision_tree_profile` object stored per-tenant:

```
{
    "profile_id": "tenant-123-soc2-audit",
    "profile_name": "Q1 2026 SOC2 Audit Metrics",
    "created_by": "user@company.com",
    "decisions": {
        "use_case": "soc2_audit",
        "goal": "compliance_posture",
        "focus_area": "vulnerability_management",
        ...
    },
    "weight_overrides": {
        "control_evidence": 1.5,
        "risk_quantification": 1.2,
        "test_satisfaction": 1.3,
        "scenario_detection": 0.8
    },
    "forced_includes": ["vuln_count_by_severity", "mttr_by_severity"],
    "forced_excludes": ["training_completion_rate"],
    "custom_groups": [
        {
            "group_id": "custom_sla_compliance",
            "group_name": "SLA Compliance Tracking",
            "goal": "Track remediation against contractual SLAs",
            "slots": {"kpis": {"min": 2, "max": 4}, "metrics": {"min": 3, "max": 6}, "trends": {"min": 1, "max": 2}},
            "affinity_keywords": ["sla", "remediation", "overdue", "breach"]
        }
    ],
    "control_priority_ranking": ["CC7", "CC6", "CC8", "CC9"],
    "risk_priority_ranking": ["R-003", "R-001", "R-007"]
}
```

**Persistence:** Profiles are stored in a new Qdrant collection `decision_tree_profiles` or in the tenant's project configuration. They can be reused across workflow runs and shared within a team.

#### Surface 3: Compliance Profile Import

Users upload or connect existing compliance documentation that the system parses into decision tree inputs:

| Import Source | Extracted Artifacts | Decision Tree Impact |
|---|---|---|
| SOC2 control matrix (Excel/CSV) | Control codes, domains, test criteria | Populates `control_evidence` scoring inputs, custom control→domain mappings |
| Risk register (Excel/CSV) | Risk IDs, categories, likelihood, impact, indicators | Populates `risk_quantification` scoring inputs, risk priority ranking |
| Audit readiness checklist (doc/PDF) | Test cases, acceptance criteria, evidence types | Populates `test_satisfaction` scoring inputs |
| Threat model (JSON/STRIDE) | Scenarios, attack techniques, affected controls | Populates `scenario_detection` scoring inputs |
| Previous audit findings (PDF) | Gap areas, remediation requirements | Populates forced_includes for metrics addressing findings |

**Design approach:** A dedicated import node (`dt_compliance_import_node`) runs before the decision tree node. It uses the existing document parsing capabilities (PDF, Excel via the skills) to extract structured artifacts and merge them into the decision tree state.

The import is additive — it enriches the framework-retrieved artifacts with customer-specific data, rather than replacing them.

#### Surface 4: Decision Tree Builder (Admin UI)

For power users and compliance consultants who want full control over the decision tree structure itself. This is a visual editor, not a chat interface.

**Capabilities:**

1. **Add custom questions** — New decision axes beyond the default 6. Example: "Regulatory jurisdiction" with options like "US Federal", "EU GDPR", "APAC" that affect which frameworks and controls are in scope.

2. **Modify option tag bundles** — Change which attributes an option maps to. Example: Making "SOC2 Audit" also require the "remediation_velocity" group as required instead of optional.

3. **Create custom scoring formulas** — Override the default linear weighted sum with organization-specific logic. Example: "If use_case is soc2_audit AND control type is detective, double the control_evidence weight."

4. **Define conditional branches** — Questions that only appear based on previous answers. Example: "Which LMS platform?" only appears if use_case is "lms_learning_target".

5. **Version and publish** — Decision trees are versioned. Changes create a new version; published versions are immutable and can be referenced by workflow runs for reproducibility.

**Data model for custom trees:**

```
DecisionTreeVersion {
    tree_id: str
    version: int
    tenant_id: str
    name: str
    description: str
    base_tree: "default_v1" | <tree_id>    // inheritance
    questions: [
        {
            key: str
            question: str
            options: [...]
            condition: {                    // conditional display
                depends_on: str             // question key
                show_when: [str]            // option IDs that trigger this question
            }
            override: bool                  // true = replaces base question; false = adds to it
        }
    ]
    scoring_overrides: {
        weight_multipliers: {...},
        custom_dimensions: [...],
        conditional_rules: [...]
    }
    group_overrides: {
        additions: [...],
        removals: [...],
        modifications: {...}
    }
    published_at: datetime | null
    created_by: str
}
```

**Inheritance model:** Custom trees inherit from a base tree (default or another custom tree). Only overrides are stored — the engine merges the base tree with overrides at runtime. This means improvements to the default tree automatically flow to custom trees unless explicitly overridden.

### 3.3 Override Application Order

When multiple input surfaces contribute to the decision tree, overrides are applied in a deterministic order:

```
1. Default decision tree (metric_decision_tree.py)
   ↓ merged with
2. Custom tree version (DecisionTreeVersion, if published)
   ↓ merged with  
3. Compliance profile import (dt_compliance_import_node output)
   ↓ merged with
4. Tenant decision tree profile (decision_tree_profile from questionnaire)
   ↓ merged with
5. Conversational overrides (dt_user_tree_overrides from chat)
   ↓ merged with
6. Auto-resolved decisions (resolve_decisions() output)
```

Later layers override earlier layers. This means a user's real-time chat input always takes priority over stored profiles, which take priority over the default tree.

**Merge rules:**

| Field Type | Merge Behavior |
|---|---|
| Single value (use_case, goal) | Later value replaces earlier |
| List (forced_includes, required_groups) | Union — all lists are combined |
| Weight multipliers | Product — `1.5 × 1.2 = 1.8` (compounding) with a cap of 3.0 |
| Scoring dimensions | Custom dimensions are appended; existing dimensions can have weight overrides |
| Groups | Custom groups added; existing groups can be modified or removed by ID |

### 3.4 Feedback Loop: Scoring Transparency

For users to make informed overrides, they need to understand *why* the decision tree selected certain metrics and excluded others. The engine should expose:

**Per-metric explanation:**

```
{
    "metric_id": "vuln_count_by_severity",
    "composite_score": 0.87,
    "explanation": {
        "top_reasons": [
            "Directly evidences control CC7.1 (domain match + detective type match)",
            "Quantifies risk R-003 'Unpatched Critical Vulnerabilities' (indicator match)",
            "Satisfies test T-CC7.1-001 acceptance criteria 'show vulnerability count by severity'"
        ],
        "score_breakdown": {
            "control_evidence": "0.92 — best match: CC7.1 (domain=system_operations, type=detective)",
            "risk_quantification": "0.88 — risk R-003 indicator 'open critical CVEs > 0' matches",
            "use_case": "0.85 — tagged for soc2_audit",
            "goal": "0.80 — aligns with risk_exposure goal",
            ...
        },
        "group_assignment": "risk_exposure → KPI slot (high control_evidence + high risk_quantification)",
    }
}
```

**Per-group gap report:**

```
{
    "group_id": "compliance_posture",
    "gap_analysis": {
        "unevidenced_controls": [
            {"code": "CC6.3", "reason": "No metric in registry measures physical access controls", 
             "suggestion": "Add a badge access metric or import from physical security system"}
        ],
        "unquantified_risks": [
            {"risk_code": "R-011", "reason": "Risk 'insider threat' has no matching metric",
             "suggestion": "Consider adding user behavior analytics metrics"}
        ]
    }
}
```

Users can then use these gaps to add custom metrics (via forced_includes), adjust weights, or import additional data sources.

---

## 4. State Extensions

New state fields required for the artifact-aware scoring and user input:

```python
# Artifact scoring inputs (populated by framework retrieval + optional import)
"dt_control_artifacts": [],          # Enriched controls with domain, type, test_criteria
"dt_risk_artifacts": [],             # Enriched risks with indicators, mitigating_controls  
"dt_scenario_artifacts": [],         # Enriched scenarios with observables, affected_controls
"dt_test_artifacts": [],             # Test cases with acceptance_criteria, evidence_types

# User input
"dt_user_tree_overrides": {},        # Conversational overrides from chat
"dt_decision_tree_profile_id": "",   # Reference to stored profile
"dt_decision_tree_version_id": "",   # Reference to custom tree version
"dt_compliance_import_results": {},  # Parsed import from uploaded documents

# Artifact-enriched output
"dt_metric_dependency_chains": [],   # Full framework→control→risk→scenario→test→metric chains
"dt_artifact_coverage_gaps": {},     # Controls/risks/tests with no metric match
"dt_scoring_explanations": [],       # Per-metric explanation objects
```

---

## 5. Workflow Changes

### 5.1 New Optional Node: `dt_compliance_import_node`

Runs before `dt_metric_decision_node` when user has uploaded compliance documents or when `dt_decision_tree_profile_id` references a profile with import data.

```
dt_planner → dt_framework_retrieval → dt_metrics_retrieval → dt_mdl_schema_retrieval
  → calculation_needs_assessment → calculation_planner
    → [NEW] dt_compliance_import_node (optional, if import data present)
      → dt_metric_decision_node (now artifact-aware)
        → dt_scoring_validator → ...
```

### 5.2 Modified Node: `dt_metric_decision_node`

The existing node gains:

1. Load and merge overrides (profile + tree version + conversational + auto-resolve)
2. Run enriched scoring with all 14 dimensions (10 existing + 4 artifact dimensions)
3. Build dependency chains
4. Generate gap report
5. Generate per-metric explanations

### 5.3 New Optional Node: `dt_decision_tree_setup_node`

A pre-workflow node that handles the setup questionnaire flow. Runs only when invoked explicitly (not part of the default graph path).

Emits the questionnaire structure → waits for user response → stores as `decision_tree_profile` → workflow continues with profile applied.

---

## 6. Data Flow Diagram

```
                    ┌─────────────────────────────┐
                    │   User Input Surfaces         │
                    │                               │
                    │  ┌─────────────────────────┐  │
                    │  │ 1. Conversational Chat   │  │
                    │  │ 2. Setup Questionnaire   │──┼──→ decision_tree_profile
                    │  │ 3. Compliance Import     │──┼──→ dt_compliance_import_results
                    │  │ 4. Tree Builder (Admin)  │──┼──→ DecisionTreeVersion
                    │  └─────────────────────────┘  │
                    └───────────────┬───────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────┐
│                     DT Workflow                               │
│                                                              │
│  Framework Retrieval                                         │
│    ├── controls[] ─────────┐                                 │
│    ├── risks[]    ─────────┤                                 │
│    ├── scenarios[]─────────┤                                 │
│    └── tests[]    ─────────┤                                 │
│                            ▼                                 │
│              ┌──────────────────────────┐                    │
│              │  Artifact Enrichment      │                    │
│              │  (merge retrieved +       │                    │
│              │   imported artifacts)     │                    │
│              └────────────┬─────────────┘                    │
│                           ▼                                  │
│              ┌──────────────────────────┐                    │
│              │  Override Merger          │                    │
│              │  (default tree            │                    │
│              │   + custom version        │                    │
│              │   + profile               │                    │
│              │   + conversational        │                    │
│              │   + auto-resolve)         │                    │
│              └────────────┬─────────────┘                    │
│                           ▼                                  │
│  Metrics Registry  ──→  Scoring Engine (14 dimensions)       │
│                           │                                  │
│                           ├──→ Scored Metrics                │
│                           ├──→ Dependency Chains             │
│                           ├──→ Coverage Gap Report           │
│                           └──→ Scoring Explanations          │
│                           │                                  │
│                           ▼                                  │
│                    Grouping Engine                            │
│                    (artifact-enriched groups)                 │
│                           │                                  │
│                           ▼                                  │
│                    Detection / Triage Engineers               │
│                    (consume groups + chains + gaps)           │
└──────────────────────────────────────────────────────────────┘
```

---

## 7. Implementation Phases

| Phase | Scope | Dependency |
|-------|-------|------------|
| **Phase A: Artifact scoring dimensions** | Add 4 new scoring dimensions to `metric_scoring.py`. Consume existing `scored_context.controls[]`, `risks[]`, `scenarios[]` from state. No new retrieval needed. | v1 decision tree engine complete |
| **Phase B: Test case integration** | Extend framework retrieval to also retrieve/store test cases. Add `test_satisfaction` scoring. | Phase A + test cases in Qdrant |
| **Phase C: Dependency chain builder** | Post-scoring pass that traces framework→control→risk→scenario→test→metric chains. Expose on scored metrics and in group metadata. | Phase A + B |
| **Phase D: Conversational overrides** | Extend interactive node to accept natural language overrides. LLM extracts structured modifications. Store in `dt_user_tree_overrides`. | Phase A |
| **Phase E: Setup questionnaire** | New pre-workflow node with structured form. Stores `decision_tree_profile`. | Phase A |
| **Phase F: Compliance document import** | Import node that parses uploaded Excel/CSV/PDF into enriched artifacts. Merges with framework-retrieved data. | Phase A + document parsing |
| **Phase G: Scoring transparency** | Per-metric explanations and per-group gap reports. Exposed in playbook assembler output and dashboard context. | Phase C |
| **Phase H: Decision tree builder** | Admin UI for custom trees. Versioning, inheritance, conditional branches. | Phase A through G stable |

Phases A–D can be implemented incrementally on top of the v1 engine without breaking changes. Phases E–H are additive features that build on the enriched scoring foundation.

---

## 8. Key Design Decisions

1. **Max-over-artifacts scoring** — A metric's `control_evidence` score is the maximum across all scored controls, not the average. This prevents a metric that perfectly evidences one control from being diluted by unrelated controls. The best match is recorded for traceability.

2. **Multiplicative weight overrides** — User weight adjustments are multipliers (not replacements) with a 3.0 cap. This prevents users from zeroing out dimensions while allowing significant re-prioritization. Compounding across layers (profile × conversational) allows fine-grained control.

3. **Inheritance-based custom trees** — Custom decision trees inherit from a base and only store deltas. This ensures improvements to the default tree propagate automatically unless explicitly overridden. It also keeps custom tree definitions small and auditable.

4. **Import is additive, not replacement** — Uploaded compliance documents enrich the framework-retrieved artifacts rather than replacing them. This prevents a stale uploaded control matrix from silently dropping controls that the framework retrieval would have found.

5. **Explanations are computed, not LLM-generated** — Per-metric scoring explanations are derived directly from the dimension scores and match details. No LLM is needed. This makes explanations deterministic, fast, and auditable.

6. **Gap reports drive the feedback loop** — The coverage gap report (unevidenced controls, unquantified risks, unsatisfied tests) is the primary mechanism for users to understand what's missing and take action. Gaps surface naturally from the artifact-aware scoring rather than requiring a separate analysis step.
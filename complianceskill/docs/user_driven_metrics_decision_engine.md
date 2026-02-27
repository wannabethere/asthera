# Metric Decision Tree Engine — Design Update v3

## LLM-Assisted Decision Tree Construction

---

## 1. What Changes and Why

The v1 and v2 designs rely on static, hand-coded mappings for three critical data structures:

| Structure | Current Approach | Limitation |
|-----------|-----------------|------------|
| **Use case groups** | `METRIC_GROUPS` dict in `metric_grouping.py` — 6 groups with hardcoded slot configs, affinity categories, visualization suggestions | Groups are generic. A SOC2 audit for a healthcare company needs different groups than a SOC2 audit for a fintech. Slot min/max values are arbitrary. Affinity categories miss domain-specific nuance. |
| **Control domain taxonomy** | `control_domain_taxonomy.json` — static mapping of control codes → domains → focus areas → risk categories | Taxonomy is shallow. CC7 maps to "system_operations" but doesn't capture that CC7.1 (vulnerability monitoring) and CC7.2 (anomaly detection) serve fundamentally different measurement goals. Risk category mappings are generic labels, not derived from actual risk text. |
| **Metric enrichment** | `enrich_metric_registry.py` — rule-based inference from category names using `CATEGORY_TO_*` lookup tables | Inference is lossy. A metric named "Mean Time to Remediate Critical Vulnerabilities by Business Unit" gets tagged as `focus_area: vulnerability_management` but misses that it's also relevant to `organizational_risk_distribution`, that it implies a `comparison` metric type across business units, and that it directly evidences CC7.1's requirement for "timely remediation." |

The common failure mode: **static mappings encode what the system designer thought was important, not what the actual compliance artifacts say is important.**

An LLM reading the actual control text, risk descriptions, metric definitions, and tenant context can produce richer, more accurate mappings. But LLM calls are expensive, non-deterministic, and slow. The design must preserve the deterministic scoring engine while using LLMs to build better inputs to it.

### Core Design Principle: LLM Generates, Engine Scores

```
LLM (slow, rich, non-deterministic)
    ↓ generates once
Materialized artifacts (cached, structured, validated)
    ↓ consumed by
Deterministic scoring engine (fast, reproducible, auditable)
```

The LLM never runs during scoring. It runs during a **generation phase** that produces structured artifacts. Those artifacts are validated, cached, and then consumed by the same deterministic scoring engine from v1. If the LLM produces garbage, validation catches it. If the LLM is unavailable, the system falls back to static mappings.

---

## 2. Generation Phase: Where LLM Calls Happen

### 2.1 New Workflow Stage: `dt_decision_tree_generation`

A new stage that runs **once per unique combination of (framework, use_case, tenant_context)** — not on every workflow invocation. Results are cached and reused across runs.

```
EXISTING FLOW:
  dt_intent_classifier → dt_planner → dt_framework_retrieval → dt_metrics_retrieval → ...

NEW FLOW:
  dt_intent_classifier → dt_planner → dt_framework_retrieval → dt_metrics_retrieval
    → [NEW] dt_decision_tree_generation (if cache miss)
        ├── LLM: generate_use_case_groups
        ├── LLM: generate_control_taxonomy  
        ├── LLM: enrich_metrics
        └── Validate + cache
    → dt_mdl_schema_retrieval → ... (rest of pipeline unchanged)
```

Cache key: `hash(framework_id + use_case + sorted(control_codes) + sorted(metric_ids) + tenant_id)`

Cache TTL: configurable, default 7 days. Invalidated when framework version changes, new metrics are added to registry, or user explicitly requests regeneration.

### 2.2 Three LLM Generation Tasks

Each task is a separate LLM call with a focused prompt, structured output schema, and validation step. They can run in parallel since they don't depend on each other's output (they all depend on the same inputs: retrieved controls, risks, scenarios, metrics).

```
                    ┌─── controls[] ──┐
                    ├─── risks[]     ──┤
                    ├─── scenarios[]  ──┤
                    ├─── metrics[]   ──┼──→ inputs to all three tasks
                    ├─── tests[]     ──┤
                    └─── user_query  ──┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
     Task 1: Groups    Task 2: Taxonomy   Task 3: Enrichment
              │               │               │
              ▼               ▼               ▼
         Validate        Validate        Validate
              │               │               │
              └───────────────┼───────────────┘
                              ▼
                     Cache materialized artifacts
                              │
                              ▼
                     Deterministic scoring engine
```

---

## 3. Task 1: LLM-Generated Use Case Groups

### 3.1 What the LLM Receives

The LLM gets the full context that a human compliance consultant would use to design metric groups:

**Input payload:**

```
- use_case: "soc2_audit"
- framework_id: "soc2"
- tenant_context: {industry, size, compliance_maturity, prior_audit_findings}
- retrieved_controls: [full control objects with code, name, domain, type, description, test_criteria]
- retrieved_risks: [full risk objects with code, name, category, likelihood, impact, indicators]
- retrieved_scenarios: [full scenario objects with name, severity, attack_techniques, observables]
- available_metrics: [metric objects with id, name, description, category, kpis, trends, source_schemas]
- available_data_sources: ["qualys", "okta", "splunk", ...]
- user_stated_priorities: (from conversational input or questionnaire, if available)
```

### 3.2 What the LLM Produces

**Output schema (enforced via structured output):**

```json
{
  "groups": [
    {
      "group_id": "<snake_case identifier>",
      "group_name": "<human readable name>",
      "goal": "<1-2 sentence description of what this group measures>",
      "priority": "high | medium | low",
      "rationale": "<why this group exists given the specific controls/risks/use_case>",
      "slots": {
        "kpis": {
          "min": "<int>",
          "max": "<int>",
          "prefer_types": ["<metric_type>", ...],
          "guidance": "<what makes a good KPI for this group>"
        },
        "metrics": {
          "min": "<int>",
          "max": "<int>",
          "prefer_types": ["<metric_type>", ...],
          "guidance": "<what supporting metrics this group needs>"
        },
        "trends": {
          "min": "<int>",
          "max": "<int>",
          "prefer_types": ["<metric_type>", ...],
          "guidance": "<what temporal patterns matter for this group>"
        }
      },
      "affinity_criteria": {
        "categories": ["<metric categories that belong here>"],
        "control_codes": ["<specific control codes this group serves>"],
        "risk_codes": ["<specific risk codes this group quantifies>"],
        "keywords": ["<domain-specific terms that signal affinity>"]
      },
      "visualization_suggestions": ["<chart types>"],
      "audience": ["<who consumes this group>"],
      "evidences_controls": ["<control codes this group should cover>"],
      "quantifies_risks": ["<risk codes this group should measure>"],
      "medallion_layer_hint": "silver | gold"
    }
  ],
  "group_relationships": [
    {
      "from_group": "<group_id>",
      "to_group": "<group_id>",
      "relationship": "feeds_into | depends_on | complements",
      "description": "<how these groups relate>"
    }
  ],
  "coverage_expectations": {
    "every_control_should_appear_in_at_least": 1,
    "every_high_risk_should_appear_in_at_least": 1,
    "minimum_total_groups": "<int>",
    "maximum_total_groups": "<int>"
  }
}
```

### 3.3 Why This Is Better Than Static Groups

**Static approach produces:**
- 6 generic groups that are the same regardless of what controls/risks were retrieved
- Affinity based on category string matching ("vulnerabilities" → risk_exposure group)
- No connection between groups — they're independent buckets

**LLM approach produces:**
- Groups shaped by the actual controls retrieved (if CC6 controls dominate, a dedicated "Access Control Posture" group emerges instead of being folded into generic "Compliance Posture")
- Groups that reference specific control and risk codes (the group *knows* it should cover CC7.1 and R-003)
- `group_relationships` that describe information flow ("Vulnerability Triage" feeds into "Remediation Tracking" which feeds into "Compliance Posture")
- Slot guidance that's contextual ("KPIs for this group should measure time-based SLA compliance because the retrieved risks emphasize remediation deadlines")
- Dynamic group count — if the tenant's compliance scope is narrow (5 controls), maybe 3 groups suffice; if broad (25 controls), maybe 8 groups

### 3.4 Prompt Design Principles

The generation prompt must:

1. **Ground in artifacts** — Every group must reference specific control codes and risk codes from the input. No invented references. The prompt includes a hard constraint: "Every control code in the input must appear in at least one group's `evidences_controls`. Every risk with impact=critical or high must appear in at least one group's `quantifies_risks`."

2. **Respect the scoring engine's needs** — The LLM output must be consumable by the deterministic grouping engine. This means `affinity_criteria` must use the same vocabulary as metric attributes (`categories`, `control_codes`, `keywords`). The prompt includes the metric attribute schema so the LLM knows what fields exist for matching.

3. **Explain itself** — `rationale` on each group is mandatory. This serves both as a quality check (reviewable by the user) and as context for the triage engineer downstream.

4. **Stay bounded** — The prompt specifies min/max group count (3–10) and min/max metrics per group. Prevents the LLM from producing 30 micro-groups or 1 mega-group.

### 3.5 Fallback

If the LLM call fails, times out, or produces invalid output, the engine falls back to the static `METRIC_GROUPS` from v1. The fallback is transparent — a flag `groups_source: "llm_generated" | "static_fallback"` is set on the output so downstream consumers and users know which path was taken.

---

## 4. Task 2: LLM-Generated Control Domain Taxonomy

### 4.1 The Problem with Static Taxonomy

The static `control_domain_taxonomy.json` maps at the control-prefix level:

```
CC7 → domain: system_operations
       focus_areas: [vulnerability_management, incident_response, audit_logging]
       risk_categories: [unpatched_systems, delayed_response, uncontained_breach]
```

This misses sub-control granularity. CC7.1 ("The entity identifies and manages vulnerabilities") and CC7.4 ("The entity implements controls to prevent or detect unauthorized software") have the same prefix but different measurement needs. CC7.1 needs vulnerability count/trend metrics; CC7.4 needs software inventory and allowlist compliance metrics.

It also misses the *text* of the control. The taxonomy was built from a human's understanding of what CC7 means, not from the actual control description retrieved from the framework.

### 4.2 What the LLM Receives

Each individual control object as retrieved from the framework, plus its associated risks and scenarios:

```
- control: {code, name, description, type, test_criteria, ...}
- associated_risks: [risks whose mitigating_controls include this control code]
- associated_scenarios: [scenarios whose affected_controls include this control code]
- available_metric_categories: [list of all categories in the metrics registry]
- available_focus_areas: [list of valid focus area identifiers]
```

### 4.3 What the LLM Produces

**Per-control taxonomy entry:**

```json
{
  "control_code": "CC7.1",
  "domain": "<domain classification>",
  "sub_domain": "<more specific classification>",
  "measurement_goal": "<what should be measured to evidence this control>",
  "focus_areas": ["<focus area IDs relevant to this specific control>"],
  "risk_categories": ["<risk categories this control mitigates>"],
  "metric_type_preferences": {
    "primary": "<metric type most useful for evidencing this control>",
    "secondary": ["<additional useful types>"],
    "rationale": "<why these types>"
  },
  "evidence_requirements": {
    "what_to_measure": "<natural language description of ideal metric>",
    "data_signals": ["<specific data points that evidence this control>"],
    "temporal_expectation": "point_in_time | trending | continuous",
    "comparison_baseline": "<what to compare against: SLA, industry benchmark, prior period, etc.>"
  },
  "affinity_keywords": ["<terms from the control description that should match metric descriptions>"],
  "control_type_classification": {
    "type": "detective | preventive | corrective | compensating",
    "confidence": "<float>",
    "reasoning": "<why this classification>"
  }
}
```

### 4.4 Why This Is Better Than Static Taxonomy

**Static taxonomy says:** CC7 → vulnerability_management, incident_response

**LLM taxonomy says (for CC7.1 specifically):**
- `measurement_goal`: "Demonstrate that vulnerabilities are identified through regular scanning and prioritized by risk severity"
- `evidence_requirements.what_to_measure`: "Count of open vulnerabilities by severity, scan coverage percentage, mean time from discovery to remediation"
- `evidence_requirements.data_signals`: ["vulnerability scan results", "CVE severity scores", "remediation timestamps", "asset coverage ratio"]
- `evidence_requirements.temporal_expectation`: "trending" (auditors want to see improvement over time)
- `evidence_requirements.comparison_baseline`: "SLA targets by severity level"
- `affinity_keywords`: ["vulnerability", "scan", "severity", "remediation", "CVE", "patch", "SLA"]

This gives the scoring engine dramatically better signal for matching metrics to controls. Instead of checking if a metric's category string matches "vulnerability_management", the engine can check if the metric's `data_filters` include "severity" and its `natural_language_question` mentions "remediation" — keywords extracted from the actual control text by the LLM.

### 4.5 Batching Strategy

Generating taxonomy for each control individually would require N LLM calls (one per control). For a typical SOC2 scope with 30-50 controls, this is expensive.

**Batch approach:** Send controls in groups of 8-12 per LLM call, organized by domain prefix (all CC6.x together, all CC7.x together). This:
- Reduces call count to 4-6 per workflow
- Gives the LLM sibling context (seeing CC7.1 and CC7.2 together helps it differentiate their measurement needs)
- Stays within reasonable output token budgets

**Parallel execution:** All batches can run in parallel since they're independent.

### 4.6 Taxonomy Output Feeds Into Scoring

The LLM-generated taxonomy replaces the static taxonomy as input to the `control_evidence` scoring dimension (v2 §2.3). Specifically:

| v2 Static Scoring | v3 LLM-Informed Scoring |
|---|---|
| Domain match: `metric.focus_area == control.domain` | Domain match: `metric.focus_area ∈ control.focus_areas` (LLM-generated, sub-control specific) |
| Type compatibility: hardcoded detective→count, preventive→percentage | Type compatibility: `metric.metric_type ∈ control.metric_type_preferences` (LLM-reasoned per control) |
| Keyword overlap: generic keyword matching | Keyword overlap: `metric.description ∩ control.affinity_keywords` (LLM-extracted from actual control text) |
| No evidence requirement awareness | Evidence match: `metric.data_filters ∩ control.evidence_requirements.data_signals` |

The scoring formula stays the same weighted sum — only the input quality improves.

---

## 5. Task 3: LLM-Enriched Metric Attributes

### 5.1 The Problem with Rule-Based Enrichment

The v1 `enrich_metric_registry.py` uses lookup tables:

```python
category="vulnerabilities" → goals=["risk_exposure", "compliance_posture", "remediation_velocity"]
```

This produces the same enrichment for every vulnerability metric regardless of what it actually measures. "Vulnerability Count by Severity" and "Mean Time to Remediate by Business Unit" both get identical `goals`, `focus_areas`, and `group_affinity` tags — but they serve completely different measurement purposes.

### 5.2 What the LLM Receives

Each metric object plus the full compliance context:

```
- metric: {id, name, description, category, kpis, trends, natural_language_question, 
           source_schemas, data_filters, data_groups, source_capabilities}
- all_controls: [control objects, including LLM-generated taxonomy from Task 2]
- all_risks: [risk objects]
- use_case: "soc2_audit"
- goal_options: [valid goal identifiers from decision tree]
- focus_area_options: [valid focus area identifiers]
- group_options: [group IDs from Task 1 output]
```

### 5.3 What the LLM Produces

**Per-metric enrichment:**

```json
{
  "metric_id": "vuln_count_by_severity",
  "enrichment": {
    "goals": {
      "values": ["risk_exposure", "remediation_velocity"],
      "reasoning": "This metric directly quantifies risk exposure through vulnerability counts and supports remediation velocity tracking via severity-based prioritization"
    },
    "focus_areas": {
      "values": ["vulnerability_management"],
      "reasoning": "Directly measures vulnerability management program output"
    },
    "use_cases": {
      "values": ["soc2_audit", "risk_posture_report", "operational_monitoring"],
      "reasoning": "Vulnerability counts are standard SOC2 CC7.1 evidence, essential for risk posture, and used in daily SOC operations"
    },
    "audience_levels": {
      "values": ["security_ops", "compliance_team", "executive_board"],
      "reasoning": "SOC uses for triage, compliance for audit evidence, executives for risk summary"
    },
    "metric_type": {
      "value": "distribution",
      "reasoning": "Although it produces counts, the 'by severity' grouping makes this a distribution metric — the shape of the distribution matters more than the raw total"
    },
    "aggregation_windows": {
      "values": ["daily", "weekly", "monthly"],
      "reasoning": "Daily for operational alerting, weekly for trend detection, monthly for audit reporting"
    },
    "group_affinity": {
      "values": ["risk_exposure", "compliance_posture", "remediation_velocity"],
      "reasoning": "Primary home is risk_exposure (quantifies vulnerability risk), secondary in compliance_posture (CC7.1 evidence), tertiary in remediation_velocity (severity breakdown drives SLA tracking)"
    },
    "control_evidence_hints": {
      "best_controls": ["CC7.1", "CC7.2"],
      "evidence_strength": "strong",
      "reasoning": "Directly evidences CC7.1 (vulnerability identification) and CC7.2 (anomaly monitoring via severity distribution changes)"
    },
    "risk_quantification_hints": {
      "best_risks": ["R-003"],
      "quantification_type": "direct_measurement",
      "reasoning": "R-003 'Unpatched Critical Vulnerabilities' is directly measured by the critical severity count from this metric"
    },
    "scenario_detection_hints": {
      "relevant_scenarios": ["S-015"],
      "detection_mechanism": "spike_detection",
      "reasoning": "A sudden increase in critical vulnerabilities (S-015: zero-day exploitation campaign) would be visible as a distribution shift"
    }
  }
}
```

### 5.4 Why This Is Better Than Rule-Based Enrichment

The LLM reads the actual metric description, its KPIs, its natural language question, and the actual controls/risks in scope. It produces:

- **Contextual metric_type** — "vuln_count_by_severity" is classified as `distribution` not `count` because the LLM understands "by severity" implies the shape matters
- **Ranked group affinity** — Instead of equal-weight membership in 3 groups, the LLM ranks primary/secondary/tertiary with reasoning
- **Cross-artifact hints** — `control_evidence_hints` and `risk_quantification_hints` pre-compute what the scoring engine would need to match, using knowledge of the actual controls and risks in scope (not generic mappings)
- **Scenario detection reasoning** — The LLM identifies *how* the metric would detect a scenario (spike detection, threshold breach, distribution shift), which is impossible to derive from category string matching

### 5.5 Batching Strategy

Metrics can be batched in groups of 5-8 per LLM call. Group by category so the LLM can differentiate similar metrics within the same domain. Typical registry has 30-50 metrics after initial filtering, so 4-8 parallel calls.

### 5.6 Enrichment Merging

LLM-generated enrichment is merged onto the metric objects in state:

```python
for metric in resolved_metrics:
    enrichment = llm_enrichments.get(metric["metric_id"])
    if enrichment:
        # LLM values override rule-based values
        metric["goals"] = enrichment["goals"]["values"]
        metric["focus_areas"] = enrichment["focus_areas"]["values"]
        metric["group_affinity"] = enrichment["group_affinity"]["values"]
        # ... etc
        
        # Store reasoning for transparency
        metric["enrichment_reasoning"] = {
            k: v.get("reasoning", "") 
            for k, v in enrichment.items() 
            if isinstance(v, dict) and "reasoning" in v
        }
        metric["enrichment_source"] = "llm_generated"
    else:
        metric["enrichment_source"] = "rule_based_fallback"
```

---

## 6. Validation Layer

LLM outputs are non-deterministic. Every generated artifact passes through validation before entering the scoring engine.

### 6.1 Group Validation

| Rule | Check | On Failure |
|------|-------|------------|
| G-V1: Schema compliance | Output matches JSON schema exactly | Reject, retry once, then fallback to static |
| G-V2: Control coverage | Every input control code appears in at least one group's `evidences_controls` | Log gap, add uncovered controls to nearest-affinity group |
| G-V3: Risk coverage | Every critical/high risk appears in at least one group's `quantifies_risks` | Log gap, add uncovered risks to risk_exposure group |
| G-V4: Group count bounds | 3 ≤ len(groups) ≤ 10 | Reject, retry with explicit count constraint |
| G-V5: Slot bounds | All min/max values are positive integers, min ≤ max | Clamp to valid range |
| G-V6: No hallucinated references | All control_codes in output exist in input control list | Strip invalid references |
| G-V7: No duplicate group IDs | group_id values are unique | Rename duplicates with suffix |
| G-V8: Required group coverage | use_case required groups (from v1 config) are present or a clear superset exists | Inject missing required groups from static fallback |

### 6.2 Taxonomy Validation

| Rule | Check | On Failure |
|------|-------|------------|
| T-V1: Schema compliance | Per-control entry matches schema | Reject entry, fallback to static for that control |
| T-V2: Focus area validity | All focus_areas are valid identifiers from the decision tree | Strip invalid, keep valid |
| T-V3: Metric type validity | Primary and secondary types are from allowed set | Replace with nearest valid type |
| T-V4: Keyword quality | affinity_keywords are non-empty and contain actual terms from control description | Regenerate from control description via simple extraction |
| T-V5: Control type consistency | LLM classification matches the control's stated type if present | Prefer the control's own stated type |
| T-V6: No cross-contamination | Taxonomy for CC7.1 doesn't reference CC6.x control concepts | Log warning, don't block |

### 6.3 Enrichment Validation

| Rule | Check | On Failure |
|------|-------|------------|
| E-V1: Schema compliance | Enrichment matches expected structure | Reject, use rule-based fallback for that metric |
| E-V2: Value validity | goals, focus_areas, use_cases, audience_levels contain only valid identifiers | Strip invalid values |
| E-V3: Non-empty required fields | goals, focus_areas, group_affinity each have at least 1 value | Fill from rule-based inference |
| E-V4: Control hint validity | best_controls are actual control codes from input | Strip invalid references |
| E-V5: Risk hint validity | best_risks are actual risk codes from input | Strip invalid references |
| E-V6: Reasoning present | Every object with a `reasoning` field has non-empty text | Accept without reasoning (reasoning is informational) |
| E-V7: Metric type consistency | If original metric has an obvious type (name contains "count"), LLM shouldn't contradict without reasoning | Log discrepancy, prefer LLM if reasoning is present |

### 6.4 Retry and Fallback Strategy

```
Attempt 1: Full LLM generation
    ↓ validation fails?
Attempt 2: Retry with validation errors injected into prompt
    ↓ still fails?
Fallback: Use static mappings from v1
    ↓ set flag
enrichment_source: "static_fallback"
```

Maximum 2 LLM attempts per task. Total generation phase budget: 3 LLM calls × 2 attempts × 3 tasks = 18 calls worst case. Typical case: 3-6 calls (parallel, single attempt each).

---

## 7. Caching and Invalidation

### 7.1 Cache Architecture

Generated artifacts are cached at two levels:

**Level 1: In-state cache** — Stored in `context_cache["decision_tree_generation"]` during a single workflow run. Prevents re-generation if the workflow loops through scoring multiple times (e.g., refinement iterations).

**Level 2: Persistent cache** — Stored in Qdrant collection `decision_tree_generated_artifacts` or tenant-scoped storage. Reused across workflow runs.

```
Cache entry {
    cache_key: hash(framework_id + use_case + sorted(control_codes) + sorted(metric_ids))
    tenant_id: str
    created_at: datetime
    ttl_days: 7
    artifacts: {
        groups: [...],
        taxonomy: [...],
        enrichments: [...],
    }
    generation_metadata: {
        model: "claude-sonnet-4-5-20250929",
        prompt_version: "v3.1",
        input_hash: str,
        generation_duration_ms: int,
        validation_results: {...},
    }
}
```

### 7.2 Invalidation Triggers

| Trigger | Action |
|---------|--------|
| Metrics registry updated (new metrics added) | Invalidate enrichments, keep groups and taxonomy |
| Framework version changed | Invalidate all three artifacts |
| User modifies decision tree profile | Invalidate groups only (taxonomy and enrichments are profile-independent) |
| User explicitly requests regeneration | Invalidate all three artifacts |
| TTL expired | Regenerate on next workflow run |
| Control set changes significantly (>20% new controls) | Invalidate taxonomy and groups |

### 7.3 Partial Regeneration

Not all three artifacts need regenerating together. If only the metrics registry changes, only Task 3 (enrichment) needs to re-run. The cache stores artifacts independently so partial invalidation is cheap.

---

## 8. Impact on Scoring Engine

The scoring engine (`metric_scoring.py`) itself does not change. It remains a deterministic weighted sum. What changes is the **quality of its inputs**:

### 8.1 Before (v1 Static)

```
Scoring dimension: focus_area
    Input: metric.focus_areas = ["vulnerability_management"]  (from CATEGORY_TO_FOCUS_AREAS lookup)
    Match: decisions.focus_area == "vulnerability_management" → 1.0

Scoring dimension: control_evidence
    Input: metric.mapped_control_domains = ["CC7"]  (from FOCUS_TO_CONTROL_DOMAINS lookup)
    Match: any scored_control.code starts with "CC7" → partial match
```

### 8.2 After (v3 LLM-Generated)

```
Scoring dimension: focus_area
    Input: metric.focus_areas = ["vulnerability_management"]  (from LLM enrichment with reasoning)
    Match: decisions.focus_area == "vulnerability_management" → 1.0
    [same score, but higher confidence that the tag is correct]

Scoring dimension: control_evidence
    Input: metric.control_evidence_hints.best_controls = ["CC7.1", "CC7.2"]
           metric.enrichment_reasoning.control_evidence = "Directly evidences CC7.1..."
    Match: scored_control CC7.1 in best_controls → 1.0
    [stronger match because LLM identified specific sub-controls, not just prefix]

Scoring dimension: group_affinity (used in grouping)
    Input: metric.group_affinity = ["risk_exposure", "compliance_posture", "remediation_velocity"]
           (ranked by LLM, not equal-weight membership)
    Match: Group "risk_exposure" gets affinity score 3.0, "compliance_posture" 2.0, "remediation_velocity" 1.0
    [ordering from LLM creates natural prioritization in slot assignment]
```

### 8.3 New Scoring Optimization: Hint-Based Boost

The LLM enrichment produces `control_evidence_hints`, `risk_quantification_hints`, and `scenario_detection_hints` that pre-compute cross-artifact relevance. The scoring engine can use these as a fast path:

```
If metric has control_evidence_hints.best_controls:
    For each scored_control:
        If control.code in metric.control_evidence_hints.best_controls:
            control_evidence_score = 0.95  (near-certain match, LLM pre-validated)
        Else:
            Fall through to normal domain/type/keyword matching
```

This is strictly an optimization — the same score would be reached through normal matching, but the hint-based path avoids keyword scanning for pre-matched pairs.

---

## 9. Impact on Grouping Engine

### 9.1 Before (v1 Static Groups)

```python
METRIC_GROUPS = {
    "compliance_posture": {
        "affinity_categories": ["compliance_events", "audit_logging", "access_control", ...],
        ...
    }
}
```

Grouping uses category string matching. A metric with `category="vulnerabilities"` never lands in the "compliance_posture" group unless explicitly listed in `affinity_categories`.

### 9.2 After (v3 LLM-Generated Groups)

```python
llm_groups = [
    {
        "group_id": "vulnerability_risk_posture",
        "affinity_criteria": {
            "categories": ["vulnerabilities", "patch_compliance", "cve_exposure"],
            "control_codes": ["CC7.1", "CC7.2", "CC8.1"],
            "risk_codes": ["R-003", "R-007", "R-012"],
            "keywords": ["vulnerability", "CVE", "patch", "remediation", "severity", "SLA"]
        },
        "evidences_controls": ["CC7.1", "CC7.2"],
        "quantifies_risks": ["R-003", "R-007"],
        ...
    }
]
```

The grouping engine now has three matching paths instead of one:

1. **Category match** (same as v1): `metric.category ∈ group.affinity_criteria.categories`
2. **Control code match** (new): `metric.control_evidence_hints.best_controls ∩ group.affinity_criteria.control_codes`
3. **Risk code match** (new): `metric.risk_quantification_hints.best_risks ∩ group.affinity_criteria.risk_codes`
4. **Keyword match** (new): `metric.description keywords ∩ group.affinity_criteria.keywords`

The affinity score formula becomes:

```
affinity = (3.0 × explicit_group_affinity_match)    // metric.group_affinity includes this group_id
         + (2.5 × control_code_overlap)              // NEW: pre-computed from hints
         + (2.0 × risk_code_overlap)                 // NEW: pre-computed from hints
         + (2.0 × category_match)                    // same as v1
         + (1.0 × keyword_match)                     // NEW: extracted from control descriptions
         + (0.5 × composite_score)                   // tiebreaker
```

### 9.3 Group Relationship Awareness

The LLM-generated `group_relationships` enable a new post-grouping validation:

If group A `feeds_into` group B, metrics in group A should have temporal precedence (real-time/daily) while group B metrics should have aggregation windows (weekly/monthly). If this ordering is violated, the grouping engine logs a warning.

If group A `depends_on` group B, group B must have at least minimum coverage before group A is considered fully covered. This creates a natural priority ordering for the candidate pool promotion logic.

---

## 10. Prompt Architecture

### 10.1 Shared Context Block

All three generation tasks share a common context block to ensure consistent terminology:

```
CONTEXT:
You are helping build a metric decision tree for a {use_case} workflow.

Framework: {framework_id}
Total controls in scope: {len(controls)}
Total risks in scope: {len(risks)}  
Total scenarios in scope: {len(scenarios)}
Total metrics available: {len(metrics)}
Connected data sources: {data_sources}

VALID IDENTIFIERS (use only these):
- Focus areas: {list of valid focus_area IDs from decision tree}
- Goals: {list of valid goal IDs}
- Metric types: count, rate, percentage, score, distribution, comparison, trend
- Audience levels: security_ops, compliance_team, executive_board, risk_management, learning_admin, auditor

COMPLIANCE ARTIFACTS:
{formatted controls with code, name, type, description}
{formatted risks with code, name, likelihood, impact, indicators}
{formatted scenarios with name, severity, observables}
{formatted metrics with id, name, description, category, kpis}
```

### 10.2 Task-Specific Instruction Blocks

Each task gets a focused instruction block that:

1. States the exact output schema (JSON)
2. Lists the validation rules the output will be checked against
3. Provides 1-2 examples of good output for a different framework/use_case
4. States anti-patterns to avoid (hallucinated references, over-generic groupings, ignoring low-severity risks)

### 10.3 Prompt Versioning

Prompts are versioned alongside the cache. When a prompt version changes, all cached artifacts generated by the old version are invalidated. This ensures prompt improvements propagate without stale cache interference.

---

## 11. Cost and Latency Budget

### 11.1 Token Estimates Per Task

| Task | Input Tokens | Output Tokens | Calls (typical) | Calls (parallel) |
|------|-------------|---------------|-----------------|-------------------|
| Generate groups | ~4,000 (context) + ~2,000 (controls+risks summary) | ~2,000-3,000 | 1 | 1 |
| Generate taxonomy | ~1,500 (context) + ~800 per batch of 8 controls | ~1,200 per batch | 4-6 | all parallel |
| Enrich metrics | ~2,000 (context) + ~600 per batch of 5 metrics | ~1,500 per batch | 4-8 | all parallel |

**Worst case total (no cache, with retries):**
- Input: ~40,000 tokens
- Output: ~25,000 tokens
- Wall-clock time: ~15-25 seconds (parallel execution)

**Typical case (cache hit on at least taxonomy):**
- Input: ~12,000 tokens
- Output: ~8,000 tokens
- Wall-clock time: ~5-10 seconds

### 11.2 Cost Mitigation

1. **Aggressive caching** — Most workflow runs will hit the cache (7-day TTL). LLM generation only runs on first invocation or after significant scope changes.
2. **Parallel execution** — All three tasks and all batches within tasks run in parallel.
3. **Smaller model for enrichment** — Task 3 (metric enrichment) is the most mechanical and can use a faster model. Tasks 1 and 2 benefit from stronger reasoning.
4. **Incremental regeneration** — Adding 2 new metrics doesn't require regenerating groups or taxonomy, only enriching the 2 new metrics.

---

## 12. Implementation Phases

| Phase | Scope | Dependency | Estimated Effort |
|-------|-------|------------|-----------------|
| **Phase 1: Generation node shell** | Add `dt_decision_tree_generation_node` to workflow. Parallel task execution framework. Cache read/write. Fallback wiring. No actual LLM prompts yet — uses static artifacts through the new node path. | v1 engine complete | 1-2 days |
| **Phase 2: Task 2 — Control taxonomy** | LLM prompt for per-control taxonomy. Batching. Validation (T-V1 through T-V6). Integration with `control_evidence` scoring dimension. | Phase 1 | 2-3 days |
| **Phase 3: Task 3 — Metric enrichment** | LLM prompt for per-metric enrichment. Batching. Validation (E-V1 through E-V7). Merge with existing metrics. Hint-based scoring boost. | Phase 1 | 2-3 days |
| **Phase 4: Task 1 — Use case groups** | LLM prompt for group generation. Validation (G-V1 through G-V8). Updated grouping engine to consume LLM groups. Group relationships. | Phase 1 | 2-3 days |
| **Phase 5: Scoring transparency** | Surface LLM reasoning in per-metric explanations. Show "enrichment_source" and "enrichment_reasoning" in gap reports. | Phases 2-4 | 1 day |
| **Phase 6: Cache management** | Persistent cache in Qdrant. Partial invalidation. TTL management. Manual regeneration trigger. | Phases 2-4 | 1-2 days |

Phases 2, 3, and 4 can be developed in parallel after Phase 1 is complete.

---

## 13. Key Design Decisions

1. **LLM generates, engine scores** — The LLM never participates in real-time scoring. It produces structured artifacts offline that feed into the deterministic scoring engine. This preserves reproducibility, auditability, and speed while getting richer inputs.

2. **Validation is mandatory, not optional** — Every LLM output is validated against a strict schema and business rules before entering the scoring pipeline. Invalid outputs trigger retry then fallback. The system never scores against unvalidated LLM output.

3. **Cache-first, generate-on-miss** — The default path reads from cache. LLM generation only runs on cache miss. This means the typical workflow run adds zero LLM latency for the decision tree phase. The cost of LLM generation is amortized across all runs within the TTL window.

4. **Reasoning is a first-class output** — The LLM must explain every classification with a `reasoning` field. This serves three purposes: quality assurance (reviewable by users), transparency (surfaced in scoring explanations), and debugging (when a metric is unexpectedly excluded, the reasoning shows why).

5. **Static fallback is always available** — The v1 static mappings remain in the codebase as the fallback path. If LLM generation fails completely, the system degrades to v1 behavior, not to failure. The `enrichment_source` flag makes the degradation visible.

6. **Batching over individual calls** — Controls and metrics are batched into groups of 5-12 per LLM call. This reduces cost, allows the LLM to use sibling context for differentiation (CC7.1 vs CC7.2), and keeps output within manageable token budgets. The trade-off is that a single bad generation can affect multiple items, but validation catches this per-item.

7. **Sub-control granularity matters** — The static taxonomy operates at the control-prefix level (CC7). The LLM taxonomy operates at the full control code level (CC7.1). This is the single largest quality improvement — metrics that evidence CC7.1 but not CC7.4 can now be scored correctly instead of getting a generic CC7 match.
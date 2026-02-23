Here are concrete test queries for each node, designed to specifically exercise the logic that node is responsible for.

---

## Node Test Cases

---

### `dt_intent_classifier_node`
**What you're testing:** Correct enrichment signal extraction — specifically that `needs_mdl`, `needs_metrics`, `suggested_focus_areas`, `metrics_intent`, and `playbook_template_hint` are all populated correctly for an ambiguous multi-signal query.

```markdown
For SOC2 CC7 and CC6, I need both Splunk detection rules for unauthorized access 
and KPI tracking to show auditors our remediation trend over the last 90 days.
```

**What to verify in the output state:**
- `intent` → `full_pipeline`
- `needs_mdl` → `true` (trend + tables implied)
- `needs_metrics` → `true` (KPI tracking, trend)
- `metrics_intent` → `trend` (90-day trend language)
- `suggested_focus_areas` → contains `identity_access_management` and `log_management_siem`
- `playbook_template_hint` → `full_chain`

---

### `dt_planner_node`
**What you're testing:** That the planner correctly omits steps for unconfigured sources and populates `dt_gap_notes` explaining why.

```markdown
Generate HIPAA audit logging detection rules and compliance metrics. 
My data sources are Okta and Splunk only.
```

**What to verify in the output state:**
- `dt_data_sources_in_scope` → `["okta", "splunk"]` (no Qualys, Tenable, etc.)
- `dt_playbook_template` → `C` (full_chain — both detection and metrics requested)
- `dt_gap_notes` → contains notes about vulnerability management metrics being unavailable without a vuln scanner
- `context_cache["dt_semantic_questions"]` → populated with specific questions per retrieval step

---

### `dt_framework_retrieval_node`
**What you're testing:** That detective controls are ranked first, and that scenarios relevant to a specific requirement code are retrieved with high relevance scores.

```markdown
Show me the detective controls and attack scenarios for HIPAA requirement 164.312(b) 
audit controls.
```

**What to verify in the output state:**
- `dt_retrieved_controls` → items where `control_type == "detective"` appear before others
- `dt_retrieved_risks` → risks reference audit logging or unauthorized access
- `dt_retrieved_scenarios` → scenarios reference ePHI access or audit trail tampering
- `controls` (base state) → same list (kept in sync)

---

### `dt_metrics_retrieval_node`
**What you're testing:** That metrics are filtered to only sources in scope AND that gap notes are generated for metrics that require an unconfigured source.

```markdown
What are the SOC2 vulnerability management KPIs I can track with Qualys? 
I do not have Tenable or Snyk configured.
```

**What to verify in the output state:**
- `resolved_metrics` → all items have `source_capabilities` containing `qualys.*`
- No metrics with `tenable.*` or `snyk.*` as sole source should appear at the top
- `dt_gap_notes` → contains mention of metrics available only via Tenable or Snyk
- `focus_area_categories` → contains `vulnerabilities` and/or `patch_compliance`

---

### `dt_mdl_schema_retrieval_node`
**What you're testing:** The direct-name lookup path — that schemas referenced in `resolved_metrics.source_schemas` are fetched by exact name, not semantic guessing.

```markdown
How do I calculate mean time to remediate critical vulnerabilities using Qualys data? 
Show me what tables are available.
```

**What to verify in the output state:**
- `context_cache["schema_resolution"]["schemas"]` → table names match exactly what was in `source_schemas` of resolved metrics (e.g., `vulnerability_instances` not a semantically similar variant)
- `lookup_hits` → non-empty (exact matches found)
- `lookup_misses` → if any, these are the schema names that need to be investigated
- `dt_gold_standard_tables` → populated if project has a gold table for vulnerability management

---

### `dt_scoring_validator_node`
**What you're testing:** That the validator drops irrelevant items, flags low-confidence items, and correctly detects schema gaps where a metric references a table not found in MDL.

This one requires a slightly adversarial setup — run a query where the focus area is narrow but some retrieved items will be off-topic:

```markdown
I need HIPAA breach detection rules for credential stuffing. 
My configured sources are Okta and CrowdStrike only.
```

**What to verify in the output state:**
- `dt_dropped_items` → contains at least one item with `D4=0.0` (source unavailable) for any metric requiring Qualys or Tenable
- `dt_schema_gaps` → any metric referencing `vulnerability_instances_schema` shows as a gap (no vuln scanner configured)
- `dt_scored_context.controls` → all retained controls have composite_score ≥ 0.50
- `dt_scored_context.controls[0].score_breakdown` → visible scoring breakdown with all four dimensions
- `dt_scoring_threshold_applied` → `0.50` (or `0.40` if fallback was triggered)

---

### `dt_detection_engineer_node`
**What you're testing:** That rules are only generated for log sources in scope, that every rule has `mapped_control_codes` from the scored_context, and that the CVE tooling is triggered when a CVE is named.

```markdown
Generate Splunk detection rules for CVE-2024-12356 exploitation against 
HIPAA-covered systems. My log sources are Splunk and CrowdStrike endpoint.
```

**What to verify in the output state:**
- `siem_rules` → all rules have `log_sources_required` containing only `splunk.*` or `crowdstrike.*`
- `siem_rules[*].mapped_control_codes` → non-empty on every rule
- `siem_rules[*].mapped_attack_techniques` → populated from ATT&CK tool call (T-format IDs)
- `siem_rules[*].alert_config` → has `threshold`, `time_window`, `severity`
- `dt_rule_gaps` → if any scenario required a log source not in scope, it appears here with `recommended_integration` populated

---

### `dt_triage_engineer_node`
**What you're testing:** That calculation steps contain zero SQL, that `needs_silver` is set correctly based on `data_capability`, and that `gold_available` accurately reflects whether the gold table is in `dt_gold_standard_tables`.

```markdown
What KPIs should I track for SOC2 vulnerability management compliance and how 
should I structure the data pipeline from raw Qualys data to weekly executive metrics?
```

**What to verify in the output state:**
- `dt_metric_recommendations` → count ≥ 10
- Every `calculation_plan_steps` entry → zero SQL keywords (`SELECT`, `WHERE`, `GROUP BY`, etc.)
- Every `calculation_plan_steps[0]` → starts with a table reference like `"From the vulnerability_instances table..."`
- `dt_medallion_plan.entries[*].needs_silver` → `true` for trend metrics (weekly grain implied)
- `dt_medallion_plan.entries[*].gold_available` → matches actual `dt_gold_standard_tables` (should be `false` if the project has no gold tables)
- `dt_metric_recommendations[*].mapped_control_codes` → non-empty on every recommendation

---

### `dt_siem_rule_validator_node`
**What you're testing:** That RULE-V3 (log source out of scope) triggers correctly, and that the validator catches a missing `alert_config`.

Run `dt_detection_engineer_node` first with a deliberately narrow source scope, then let the validator run on those rules:

```markdown
Generate detection rules for lateral movement and privilege escalation for 
SOC2 CC6. I only have Azure AD logs configured, no endpoint or network sources.
```

**What to verify in the output state:**
- `dt_siem_validation_passed` → `false` (expected — lateral movement rules typically need endpoint logs)
- `dt_siem_validation_failures` → contains RULE-V3 failures for rules referencing endpoint sources
- Each failure has a specific `fix_instruction` naming the exact out-of-scope source
- `dt_validation_iteration` → incremented to `1` after routing back for refinement

---

### `dt_metric_calculation_validator_node`
**What you're testing:** RULE-C2 (SQL detection) and RULE-M2 (gold_available accuracy). The best way is to let the triage engineer run on a project with no gold tables and verify the validator catches any incorrect `gold_available: true` claims.

```markdown
Give me HIPAA audit logging compliance metrics with calculation steps. 
This is a new tenant with no pre-built gold tables.
```

**What to verify in the output state:**
- `dt_metric_validation_rule_summary["RULE-C2"]` → `pass` (no SQL found)
- `dt_metric_validation_rule_summary["RULE-M2"]` → `pass` (no false gold_available claims since gold tables list is empty)
- `dt_metric_validation_rule_summary["RULE-W1"]` → `pass` if ≥ 10 recommendations, `warning` if fewer
- `dt_metric_validation_failures` → ideally empty on first pass; if not, failures have `step_number` pointing to the exact step

---

### `dt_playbook_assembler_node`
**What you're testing:** Template C (full_chain) output — that both the SIEM rule section and the metric recommendation section appear, and that the traceability section links each rule to at least one KPI.

```markdown
Build me a complete HIPAA breach detection and response package for unauthorized 
ePHI access — I need both the Splunk rules and the compliance dashboard metrics 
to show auditors after an incident.
```

**What to verify in the output state:**
- `dt_assembled_playbook` → has keys matching Template C sections (Executive Summary, Detection Rules, Medallion Architecture Plan, Metric Recommendations, Traceability, Gap Analysis)
- The Traceability section → each SIEM rule ID appears alongside the KPI it informs (e.g., `rule_hipaa_001 → failed_login_rate metric`)
- `quality_score` → above 60 on a clean first-pass run (no refinement iterations)
- `dt_gap_notes` → summarized in the Gap Analysis section (not silently dropped)

---

## Recommended test order

Run these sequentially with the same data source config (`["okta", "splunk", "qualys"]`) to get a full end-to-end trace:

1. Query 3 (framework retrieval isolation) → verify retrieval quality first
2. Query 5 (MDL schema — exact hit verification) → confirm your MDL has the expected schemas
3. Query 6 (scoring — adversarial narrow scope) → verify the 0.50 threshold is working
4. Query 12 (full end-to-end Template C) → smoke test the complete pipeline

The MDL schema test (query 5) is the most important one to run early — `lookup_misses` will tell you immediately which schema names in your metrics registry don't have matching entries in `leen_db_schema`, which is the most common integration failure point.
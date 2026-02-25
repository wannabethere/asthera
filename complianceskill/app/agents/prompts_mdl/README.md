# Detection & Triage Engineering Workflow — Prompt Package

**Version:** 1.0  
**Status:** Architecture + Prompts — Ready for Implementation  
**Related:** DETECTION_TRIAGE_WORKFLOW_ARCHITECTURE.md

---

## Prompt Files

| File | Agent | Role | New / Updated |
|---|---|---|---|
| `01_intent_classifier.md` | Intent Classifier | Classifies query + produces enrichment signals (focus areas, needs_mdl, metrics_intent) | Updated |
| `02_detection_triage_planner.md` | Planner | Builds atomic retrieval + execution plans using focus_area_config and available_data_sources | New |
| `03_detection_engineer.md` | Detection Engineer | Generates SIEM rules anchored to scored_context controls and scenarios | Updated |
| `04_triage_engineer.md` | Triage Engineer | Medallion architecture plan + 10+ metric recommendations in natural language | New |
| `05_relevance_scoring_validator.md` | Scoring Validator | Cross-scores retrieved controls/metrics/schemas before execution agents | New |
| `06_metric_calculation_validator.md` | Metric Validator | Validates triage output — traceability, no-SQL rules, medallion completeness | New |

---

## Example Files

| File | Covers | Used By |
|---|---|---|
| `examples/classifier_examples.yaml` | 6 annotated classifier examples + anti-patterns | `01_intent_classifier.md` |
| `examples/planner_hipaa_full_chain.yaml` | Full chain plan, HIPAA breach detection (Template A, detection_focused) | `02_detection_triage_planner.md` |
| `examples/planner_soc2_triage.yaml` | Triage plan, SOC2 vuln management (Template B, triage_focused) | `02_detection_triage_planner.md` |
| `examples/triage_engineer_soc2_vuln.yaml` | Full medallion plan + 12 metric recommendations, SOC2 | `04_triage_engineer.md` |
| `examples/detection_engineer_hipaa_auth.yaml` | 3 SIEM rules (SPL + Sigma) for HIPAA credential theft | `03_detection_engineer.md` |

---

## How Prompts Connect — Data Flow

```
01 Intent Classifier
   └─ outputs: intent, framework_id, data_enrichment
              (needs_mdl, needs_metrics, focus_areas, metrics_intent, template_hint)
   
02 Planner
   └─ inputs: classifier output + focus_area_config + available_data_sources
   └─ outputs: execution_plan (ordered steps with semantic_questions)
              playbook_template selection
   
   RETRIEVAL PHASE (driven by plan steps):
   ├─ framework_analyzer / semantic_search → framework_controls, risks, scenarios
   ├─ metrics_lookup → leen_metrics_registry (filtered by focus area + source capability)
   └─ mdl_lookup → leen_db_schema (direct by name) + GoldStandardTables
   
05 Relevance Scoring Validator
   └─ inputs: all retrieved collections
   └─ outputs: scored_context (filtered, cross-scored, schema-gap-flagged)
   
   EXECUTION PHASE:
   ├─ 03 Detection Engineer → siem_rules (anchored to scored_context.controls)
   └─ 04 Triage Engineer → medallion_plan + metric_recommendations
   
   VALIDATION PHASE:
   ├─ siem_rule_validator → validates syntax, logic, control traceability
   └─ 06 Metric Calculation Validator → validates traceability, no-SQL, completeness
```

---

## Key Design Constraints (All Prompts Enforce)

1. **Data source boundary** — No step, rule, or metric may reference a source not in `available_data_sources`
2. **No fabricated tables** — MDL lookups use exact schema names from metrics registry, never semantic search
3. **Natural language only in calculations** — `calculation_plan_steps` must contain zero SQL keywords
4. **Minimum 10 metrics** — Triage engineer is blocked by validator until this threshold is met
5. **Every metric traces to a control** — `mapped_control_codes` required on every recommendation
6. **Semantic questions required** — Every search step has an explicit `semantic_question` field

---

## Focus Area Configuration (Referenced by Planner)

The static `focus_area_config` maps focus areas to framework controls and metric categories.
This lives in application config — not in any prompt. Prompts reference it by name only.

See `DETECTION_TRIAGE_WORKFLOW_ARCHITECTURE.md` Section 5 for the full mapping table.

---

## Playbook Templates (Selected by Planner)

| Template | Intent | Sections |
|---|---|---|
| A — Detection Focused | `detection_engineering`, `detection_focused` | Executive Summary, Detection Rules, Triage Metrics (top 5), Data Source Requirements, Validation Steps |
| B — Triage Focused | `triage_engineering`, `triage_focused` | Executive Summary, Medallion Architecture Plan, Metric Recommendations (10+), Gap Analysis, Implementation Notes |
| C — Full Chain | `full_pipeline`, `full_chain` | All of Template A + Template B + Traceability: Rules ↔ KPIs |

# CSOD domain add-on — Intent classifier

Append after the shared analysis intent classifier prompt and injected catalog.

## Product context

Users work with **Cornerstone OnDemand (CSOD)**, **Workday HCM**, and related learning/compliance data. Questions may mention training completion, certifications, curricula, learners, org units, compliance deadlines, audits, dashboards, KPIs, metrics, lineage, or data engineering (medallion/dbt).

## Focus area taxonomy (`data_enrichment.suggested_focus_areas`)

Pick **1–3** slugs from this list only:

- `ld_training` — Training plans, assignments, completion, compliance training monitoring  
- `ld_operations` — Learning measurement, cost, vendor/ILT, program utilization  
- `ld_engagement` — LMS adoption, logins, active users, role usage  
- `hr_workforce` — Headcount, lifecycle, HR/training alignment, Workday-aligned metrics  
- `talent_management` — Skills, competency, career, performance  
- `recruitment` — Hiring pipeline, time-to-fill  
- `onboarding` — New hire training, onboarding completion  
- `compliance_training` — Certifications, policy attestations, audit readiness  
- `hybrid_compliance` — Cross-domain GRC-style reporting  
- `security_operations` / `vulnerability_management` — Only if the query clearly mixes security-tool context with learning data  

## Persona slug hints (`persona`)

When intent is `dashboard_generation_for_persona` and the user names an audience, map to:  
`learning_admin`, `training_coordinator`, `team_manager`, `l&d_director`, `learning_operations_manager`, `hr_operations_manager`, `compliance_officer`, `executive`, `analyst` — or `null`.

## CSOD-specific guidance

- **Metric relationships / causal “why” / reasoning plans** → usually `metric_kpi_advisor`.  
- **Gold/medallion/data model + metric list without deep causal reasoning** → `metrics_recommender_with_gold_plan`.  
- **Layout/plan for a metrics dashboard** → `metrics_dashboard_plan`.  
- **Concrete dashboard for a named persona** → `dashboard_generation_for_persona`.  
- **SQL tests, alerts, audit checks** → `compliance_test_generator`.  
- **Data inventory / what exists** → `data_discovery`.  
- **Trace metric to sources** → `data_lineage`.  
- **Trust, freshness, completeness** → `data_quality_analysis`.  
- **Pipeline/dbt/medallion design** → `data_planner`.  

**Unified analysis spine:** Gap, cohort, anomaly, predictive risk, ROI, funnel, crown-jewel, skill-gap, behavioral, and benchmark intents still use **distinct catalog ids** so DT/CCE and `analysis_requirements` stay precise — but the **runtime graph** always lands on the same implemented tail (**`metrics_recommender`** after MDL → metrics → scoring → DT → optional causal). Prefer the **most specific** catalog id when the user’s goal is clearly analytical rather than presentational; do not invent alternate executor names.

## Lexy conversation registry (`lexy_conversation_flows.json`)

Prefer these **catalog ids** when the question matches the demo flows (each row may list `maps_to_pipeline_intent` in the injected JSON — routing still uses that canonical intent internally):

| User pattern | Prefer `intent` (registry) | Typical `quadrant` | Typical `routing` |
|--------------|----------------------------|--------------------|---------------------|
| Audit/deadline + current % vs target + close the gap | `compliance_gap_close` | Diagnostic | `full_spine` |
| Plain gap vs target (generic wording) | `gap_analysis` | Diagnostic | `full_spine` |
| “Who will miss … deadline” / forward risk | `predictive_risk_analysis` | Predictive | `full_spine` |
| Single headline number / “this week’s rate” | `current_state_metric_lookup` | Exploratory | `short_circuit` |
| Follow-up drill-down by segment (when prior turn established metrics) | `cohort_analysis` | Exploratory | `direct_dispatch` (if add-on marks follow-up) |
| “Build/show dashboard for [persona]” | `dashboard_generation_for_persona` | Operational | `full_spine` |
| Training plan admin / division plan view | `training_plan_dashboard` | Operational | `full_spine` |
| System or metric anomaly / spike or drop | `anomaly_detection` | Diagnostic | `full_spine` |

For **`stage_1_intent.signals`**, use keys similar to the registry examples: `terminal_metric`, `urgency`, `time_horizon`, `scope`, `output`, `metric`, `cohort_dimension`, `persona`, `output_type`, `trigger`, `enforce`, etc., with **values paraphrased from the user text**, not copied from static examples.

# CCE Intent Planner — Walkthrough Example
### Platform: Cornerstone OnDemand (CSOD Learn)

This document shows a complete end-to-end trace of the CCE (Compliance Conversation Engine)
Intent Planner for a realistic multi-intent query. Each stage shows the raw inputs, the LLM
output, and how state is mutated before the next step.

---

## Example Query

> **"Our compliance training completion rate has dropped from 89% to 71% over the last 30 days.
> We have a SOC2 audit coming up in 30 days. Which teams are most at risk, and can we actually
> close that gap in time?"**

---

## Stage 0 — Datasource Selection

```
csod_selected_datasource : "cornerstone"
csod_datasource_confirmed : true          ← auto-confirmed (only one datasource configured)
```

---

## Stage 1 — Intent Splitting  `intent_splitter_node`

The LLM decomposes the query into **2 independent analytical intents**.

### LLM Input (system + user prompt)
```
User question: "Our compliance training completion rate has dropped from 89% to 71% over
the last 30 days. We have a SOC2 audit coming up in 30 days. Which teams are most at risk,
and can we actually close that gap in time?"
Platform/datasource: cornerstone
```

### LLM Output (raw JSON)
```json
[
  {
    "intent_id": "i1",
    "description": "Compliance training completion rate dropped 18 pts in 30 days — identify root cause and which teams are driving the drop",
    "analytical_goal": "Diagnose the structural cause of the completion rate decline and rank teams by contribution to the gap",
    "key_entities": ["completion_rate", "mandatory_training", "org_unit", "training_assignment"],
    "extracted_signals": [
      {
        "label": "terminal_metric",
        "value": "compliance_training_rate — dropped from 89% to 71%, gap of 18 pts over 30 days, immediately computable from transcript + assignment data"
      },
      {
        "label": "analysis_type",
        "value": "Causal decomposition + cohort breakdown — need lag structure (when assignments were issued vs when completions stalled) before ranking teams"
      },
      {
        "label": "primary_driver_hypothesis",
        "value": "Assignment volume surge or content change most likely — need to compare new_assignments_issued vs completion_rate on same 30-day window"
      },
      {
        "label": "segmentation_needed",
        "value": "OU-level breakdown required — company-wide rate masks which specific departments are dragging the average down"
      },
      {
        "label": "implicit",
        "value": "Which 2-3 OUs account for the majority of the 18pt drop, and is the drop uniform or concentrated?"
      }
    ]
  },
  {
    "intent_id": "i2",
    "description": "SOC2 audit in 30 days — assess current audit readiness posture and whether the compliance gap is closable in the available window",
    "analytical_goal": "Determine audit readiness score, identify the highest-risk uncompleted requirement tags, and model whether 30-day completion is feasible",
    "key_entities": ["audit_readiness_score", "pending_required_modules", "compliance_gap_count", "overdue_rate"],
    "extracted_signals": [
      {
        "label": "terminal_metric",
        "value": "audit_readiness_score — composite of percent_fully_compliant, compliance_gap_count, and evidence_documentation_count; target is audit-passable threshold"
      },
      {
        "label": "urgency",
        "value": "30-day hard deadline — forward projection of completion velocity vs outstanding assignments determines whether the gap is physically closable"
      },
      {
        "label": "compliance_context",
        "value": "SOC2 audit — auditors care about trajectory and documented evidence (completion timestamps, certification records), not just raw rate on audit day"
      },
      {
        "label": "analysis_type",
        "value": "Gap analysis with forward projection — intervention ordering is critical: highest-risk requirement tags must be completed first to maximise audit posture"
      },
      {
        "label": "implicit",
        "value": "Is the 19pt gap closable in 30 days given current assignment velocity? Answer requires causal lag structure, not just current completion rate"
      },
      {
        "label": "evidence_requirement",
        "value": "SOC2 auditors require timestamped completion records per user per requirement tag — missing documentation is a separate risk from low completion rate"
      }
    ]
  }
]
```

### State Written
```
csod_intent_splits: [
  { intent_id: "i1", description: "...", extracted_signals: [ 5 signals ] },
  { intent_id: "i2", description: "...", extracted_signals: [ 6 signals ] }
]
```

---

## Stage 2 — MDL-Aware Resolution  `mdl_project_resolver_node`

For each intent the LLM reads the **project catalog** (from `csod_project_metadata_enriched.json`)
and the **concept + area registry** to select specific projects and areas.

### Project Catalog Fed to LLM (condensed)

| project_id | Title | Data Categories |
|---|---|---|
| `csod_transcript_statuses` | CSOD Learn — Transcript & Statuses | training_completion, compliance_training, certification_tracking |
| `csod_assignments_lat` | CSOD Learn — Assignments (LAT) | compliance_training, training_assignment, overdue_tracking |
| `csod_organizational_units` | CSOD Learn — Organizational Units | org_hierarchy, user_segmentation |
| `csod_user_core_details` | CSOD Learn — User Core Details | user_master, hr_data, user_ou_association |
| `csod_training_catalog_lo` | CSOD Learn — Training Catalog (LOs) | content_catalog, training_metadata, delivery_method |
| `csod_assessment_qa` | CSOD Learn — Assessment & Q&A | learning_effectiveness, certification_tracking |
| `csod_scorm` | CSOD Learn — SCORM Content | scorm_interactions, content_delivery |
| `csod_ilt_event_session` | CSOD Learn — ILT Events & Sessions | ilt_delivery, attendance, facility_cost |

### LLM Resolution Output
```json
[
  {
    "intent_id": "i1",
    "concept_id": "compliance_training",
    "matched_project_ids": [
      "csod_transcript_statuses",
      "csod_assignments_lat",
      "csod_organizational_units",
      "csod_user_core_details"
    ],
    "project_rationale": "Completion rate drop requires transcript + assignment tables to measure the lag between assignment issue and completion; OU and user tables are needed for team-level breakdown.",
    "area_ids": ["completion_trends", "overdue_risk"]
  },
  {
    "intent_id": "i2",
    "concept_id": "compliance_training",
    "matched_project_ids": [
      "csod_transcript_statuses",
      "csod_assignments_lat",
      "csod_training_catalog_lo"
    ],
    "project_rationale": "Audit readiness requires completed-vs-pending counts from transcript and assignment tables, plus training catalog metadata to map completions to SOC2 requirement tags.",
    "area_ids": ["audit_readiness", "overdue_risk"]
  }
]
```

### Post-Hydration (areas pulled from concept_recommendation_registry)

#### Intent i1 — Resolved Areas

**Area 1: `completion_trends` — Completion Trends & Drivers**

| Field | Value |
|---|---|
| Description | Monitor trends in compliance training completion, detect drops, identify drivers |
| Metrics | `completion_rate`, `new_assignments_issued`, `median_time_to_completion`, `assessment_pass_rate` |
| KPIs | `month_over_month_completion_change`, `compliance_training_rate`, `average_time_to_completion` |
| Filters | `time_period`, `org_unit`, `delivery_method`, `training_category` |
| Causal Paths | `Increased_assignments → Lower_completion_rate` · `Complex_content → Longer_time_to_completion` |
| MDL Tables | `training_assignment_core`, `transcript_core`, `training_scorm_core`, `assessment_result_core` |

**Area 2: `overdue_risk` — Overdue & At-Risk Teams**

| Field | Value |
|---|---|
| Description | Identify teams and users with overdue mandatory compliance assignments |
| Metrics | `total_mandatory_assignments`, `overdue_assignment_count`, `average_days_overdue`, `percent_assignments_past_due` |
| KPIs | `overdue_rate`, `on_time_completion_rate`, `at_risk_team_count` |
| Filters | `org_unit`, `due_date_range`, `training_type`, `user_status` |
| Causal Paths | `Insufficient_availability → Overdue_assignment_count` · `High_assignment_volume → Decreased_on_time_completion_rate` |
| MDL Tables | `training_assignment_core`, `transcript_core`, `user_ou_core`, `users_core` |

#### Intent i2 — Resolved Areas

**Area 1: `audit_readiness` — Audit Readiness & Evidence**

| Field | Value |
|---|---|
| Description | Assess overall readiness for an upcoming audit |
| Metrics | `audit_compliance_rate`, `mandatory_training_completed_count`, `pending_required_modules`, `evidence_documentation_count` |
| KPIs | `audit_readiness_score`, `percent_fully_compliant`, `compliance_gap_count` |
| Filters | `audit_window`, `org_unit`, `requirement_tag`, `certification_status` |
| Causal Paths | `Low_completion_rate → Failed_audit_items` · `Missing_documentation → Reduced_audit_readiness` |
| MDL Tables | `transcript_core`, `training_requirement_tag_core`, `training_assignment_core`, `training_bundle_core` |

**Area 2: `overdue_risk`** — shared with i1 (same area, different analytical lens)

### State Written
```
csod_intent_resolutions: [
  {
    intent_id: "i1",
    concept_id: "compliance_training",
    concept_display_name: "Compliance Training Risk",
    matched_project_ids: ["csod_transcript_statuses", "csod_assignments_lat",
                          "csod_organizational_units", "csod_user_core_details"],
    project_display_names: ["Transcript & Statuses", "Assignments (LAT)",
                             "Organizational Units", "User Core Details"],
    area_ids: ["completion_trends", "overdue_risk"],
    areas: [ { ...full area dicts... } ]
  },
  {
    intent_id: "i2",
    concept_id: "compliance_training",
    concept_display_name: "Compliance Training Risk",
    matched_project_ids: ["csod_transcript_statuses", "csod_assignments_lat",
                          "csod_training_catalog_lo"],
    project_display_names: ["Transcript & Statuses", "Assignments (LAT)", "Training Catalog"],
    area_ids: ["audit_readiness", "overdue_risk"],
    areas: [ { ...full area dicts... } ]
  }
]
```

---

## Stage 3 — Intent Confirm Checkpoint  `csod_intent_confirm_node`

This is the **only user-facing turn** that replaces the old concept_confirm + area_confirm pair
for the initial scope selection. The frontend renders an `INTENT_SELECTION` widget.

### Checkpoint Payload Sent to Frontend

```json
{
  "phase": "intent_confirm",
  "turn": {
    "phase": "intent_confirm",
    "turn_type": "intent_selection",
    "message": "I found 2 distinct analytical angles in your question. Select the one(s) you'd like to explore:",
    "options": [
      {
        "id": "i1",
        "label": "Compliance Training Risk",
        "description": "Compliance training completion rate dropped 18 pts in 30 days — identify root cause and which teams are driving the drop",
        "concept_id": "compliance_training",
        "concept_display_name": "Compliance Training Risk",
        "project_ids": ["csod_transcript_statuses", "csod_assignments_lat", "csod_organizational_units", "csod_user_core_details"],
        "project_display_names": ["Transcript & Statuses", "Assignments (LAT)", "Organizational Units", "User Core Details"],
        "project_rationale": "Completion rate drop requires transcript + assignment tables plus OU and user tables for team-level breakdown.",
        "area_ids": ["completion_trends", "overdue_risk"],
        "area_display_names": ["Completion Trends & Drivers", "Overdue & At-Risk Teams"],
        "top_metrics": ["completion_rate", "new_assignments_issued", "median_time_to_completion"],
        "extracted_signals": [
          { "label": "terminal_metric",         "value": "compliance_training_rate — dropped from 89% to 71%, gap of 18 pts over 30 days" },
          { "label": "analysis_type",            "value": "Causal decomposition + cohort breakdown — lag structure between assignment issue and completion stall" },
          { "label": "primary_driver_hypothesis","value": "Assignment volume surge or content change — compare new_assignments_issued vs completion_rate on same 30-day window" },
          { "label": "segmentation_needed",      "value": "OU-level breakdown required — company-wide rate masks which departments are dragging average down" },
          { "label": "implicit",                 "value": "Which 2-3 OUs account for the majority of the 18pt drop, and is the drop uniform or concentrated?" }
        ],
        "action": "select"
      },
      {
        "id": "i2",
        "label": "Compliance Training Risk",
        "description": "SOC2 audit in 30 days — assess current audit readiness and whether the compliance gap is closable in time",
        "concept_id": "compliance_training",
        "concept_display_name": "Compliance Training Risk",
        "project_ids": ["csod_transcript_statuses", "csod_assignments_lat", "csod_training_catalog_lo"],
        "project_display_names": ["Transcript & Statuses", "Assignments (LAT)", "Training Catalog"],
        "project_rationale": "Audit readiness requires completed vs pending counts from transcript/assignment tables, plus catalog metadata to map completions to SOC2 requirement tags.",
        "area_ids": ["audit_readiness", "overdue_risk"],
        "area_display_names": ["Audit Readiness & Evidence", "Overdue & At-Risk Teams"],
        "top_metrics": ["audit_compliance_rate", "pending_required_modules", "compliance_gap_count"],
        "extracted_signals": [
          { "label": "terminal_metric",    "value": "audit_readiness_score — composite of percent_fully_compliant, compliance_gap_count, and evidence_documentation_count" },
          { "label": "urgency",            "value": "30-day hard deadline — velocity of completions vs outstanding assignments determines whether gap is physically closable" },
          { "label": "compliance_context", "value": "SOC2 audit — auditors care about trajectory and documented evidence, not just raw rate on audit day" },
          { "label": "analysis_type",      "value": "Gap analysis with forward projection — intervention ordering is critical: highest-risk requirement tags completed first" },
          { "label": "implicit",           "value": "Is the 19pt gap closable in 30 days given current assignment velocity? Requires causal lag structure, not just current rate" },
          { "label": "evidence_requirement","value": "SOC2 auditors require timestamped completion records per user per requirement tag — missing docs are a separate risk" }
        ],
        "action": "select"
      },
      {
        "id": "rephrase",
        "label": "Let me rephrase",
        "action": "rephrase"
      }
    ],
    "metadata": {
      "signal_map": {
        "i1": [
          { "label": "terminal_metric",         "value": "compliance_training_rate — dropped from 89% to 71%, gap of 18 pts over 30 days" },
          { "label": "analysis_type",            "value": "Causal decomposition + cohort breakdown" },
          { "label": "primary_driver_hypothesis","value": "Assignment volume surge or content change" },
          { "label": "segmentation_needed",      "value": "OU-level breakdown required" },
          { "label": "implicit",                 "value": "Which 2-3 OUs account for the majority of the 18pt drop?" }
        ],
        "i2": [
          { "label": "terminal_metric",    "value": "audit_readiness_score — composite of percent_fully_compliant + compliance_gap_count" },
          { "label": "urgency",            "value": "30-day hard deadline — forward projection required" },
          { "label": "compliance_context", "value": "SOC2 audit — trajectory and evidence matter as much as raw rate" },
          { "label": "analysis_type",      "value": "Gap analysis with forward projection — intervention ordering critical" },
          { "label": "implicit",           "value": "Is the 19pt gap closable in 30 days?" },
          { "label": "evidence_requirement","value": "Timestamped completion records per user per requirement tag required" }
        ]
      }
    }
  },
  "resume_with_field": "csod_selected_intent_ids"
}
```

### What the User Sees (conceptual UI)

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  I found 2 distinct analytical angles in your question.                      ║
║  Select the one(s) you'd like to explore:                                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  ☑  Compliance Training Risk  ·  Completion drop root cause                 ║
║     Projects: Transcript & Statuses · Assignments (LAT) · Org Units          ║
║     Areas:    Completion Trends & Drivers · Overdue & At-Risk Teams          ║
║                                                                              ║
║     SIGNAL EXTRACTION ────────────────────────────────────────────           ║
║     terminal_metric         compliance_training_rate — 89% → 71%,           ║
║                             gap 18pts over 30 days                           ║
║     analysis_type           Causal decomposition + cohort breakdown          ║
║     primary_driver_hypothesis  Assignment volume surge or content change     ║
║     segmentation_needed     OU-level breakdown required                      ║
║     implicit                Which 2-3 OUs account for the 18pt drop?         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  ☑  Compliance Training Risk  ·  SOC2 audit readiness in 30 days            ║
║     Projects: Transcript & Statuses · Assignments (LAT) · Training Catalog  ║
║     Areas:    Audit Readiness & Evidence · Overdue & At-Risk Teams           ║
║                                                                              ║
║     SIGNAL EXTRACTION ────────────────────────────────────────────           ║
║     terminal_metric         audit_readiness_score — composite KPI           ║
║     urgency                 30-day hard deadline — forward projection req'd  ║
║     compliance_context      SOC2 audit — evidence + trajectory matter       ║
║     analysis_type           Gap analysis with forward projection             ║
║     implicit                Is the 19pt gap closable in 30 days?             ║
║     evidence_requirement    Timestamped records per user per req. tag        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  ○  Let me rephrase                                                          ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### User Selects Both Intents

```json
{ "csod_selected_intent_ids": ["i1", "i2"] }
```

---

## Stage 3 Resume — State After `_apply_selections()`

```
csod_selected_intent_ids      : ["i1", "i2"]
csod_confirmed_concept_ids    : ["compliance_training"]
csod_selected_concepts        : [{ concept_id: "compliance_training",
                                   display_name: "Compliance Training Risk",
                                   score: 1.0, coverage_confidence: 0.9 }]
csod_concept_matches          : [ same as above + project_ids ]
csod_resolved_project_ids     : ["csod_transcript_statuses",   ← 4 specific projects
                                  "csod_assignments_lat",          NOT all 16
                                  "csod_organizational_units",
                                  "csod_user_core_details",
                                  "csod_training_catalog_lo"]
csod_primary_project_id       : "csod_transcript_statuses"
csod_llm_resolved_areas       : {
  "compliance_training": [
    { area_id: "completion_trends",  score: 1.0, metrics: [...], filters: [...] },
    { area_id: "overdue_risk",       score: 1.0, metrics: [...], filters: [...] },
    { area_id: "audit_readiness",    score: 1.0, metrics: [...], filters: [...] }
  ]
}
csod_extracted_signals        : [
  { label: "terminal_metric",          value: "compliance_training_rate — 89% → 71%..." },
  { label: "analysis_type",            value: "Causal decomposition + cohort breakdown" },
  { label: "primary_driver_hypothesis",value: "Assignment volume surge or content change" },
  { label: "segmentation_needed",      value: "OU-level breakdown required" },
  { label: "implicit",                 value: "Which 2-3 OUs account for the 18pt drop?" },
  { label: "terminal_metric",          value: "audit_readiness_score — composite KPI" },
  { label: "urgency",                  value: "30-day hard deadline — forward projection req'd" },
  { label: "compliance_context",       value: "SOC2 audit — evidence + trajectory matter" },
  { label: "analysis_type",            value: "Gap analysis with forward projection" },
  { label: "implicit",                 value: "Is the 19pt gap closable in 30 days?" },
  { label: "evidence_requirement",     value: "Timestamped records per user per req. tag" }
]
csod_concepts_confirmed       : true
csod_checkpoint_resolved      : true
```

---

## Stage 4 — Preliminary Area Matcher  `preliminary_area_matcher_node`

Looks up the first LLM-resolved area for `compliance_training` to determine scoping filters.

```
csod_preliminary_area_matches : [
  {
    area_id:      "completion_trends",
    concept_id:   "compliance_training",
    display_name: "Completion Trends & Drivers",
    filters:      ["time_period", "org_unit", "delivery_method", "training_category"],
    score:        1.0
  }
]
```

---

## Stage 5 — Scoping  `scoping_node`  *(checkpoint)*

Filter hints extracted from the original query:
- `time_period` → `last_30d` (extracted from "last 30 days")
- `audit_window` → `next_30d` (extracted from "audit coming up in 30 days")

### Scoping Checkpoint Shown to User

```
╔══════════════════════════════════════════════════════╗
║  A few quick questions to narrow the analysis:        ║
╠══════════════════════════════════════════════════════╣
║  Time window                                          ║
║  ● Last 30 days  ○ Last 60 days  ○ Last 90 days       ║
║  ○ Custom range                                       ║
╠══════════════════════════════════════════════════════╣
║  Org scope                                            ║
║  ○ Company-wide  ● By department  ○ By division       ║
║  ○ Specific team                                      ║
╠══════════════════════════════════════════════════════╣
║  Training type                                        ║
║  ● All mandatory  ○ SOC2-tagged only  ○ Specific tag  ║
╠══════════════════════════════════════════════════════╣
║  Audit window                                         ║
║  ● Next 30 days  ○ Next 60 days  ○ Custom             ║
╚══════════════════════════════════════════════════════╝
```

### User Answers

```
csod_scoping_answers : {
  time_period:    "last_30d",
  org_unit:       "department",
  training_type:  "all_mandatory",
  audit_window:   "next_30d"
}
```

---

## Stage 6 — Area Matcher  `area_matcher_node`

Pulls top 3 areas from `csod_llm_resolved_areas["compliance_training"]` (already resolved at Stage 2).

```
csod_area_matches : [
  { area_id: "completion_trends", display_name: "Completion Trends & Drivers",   score: 1.0 },
  { area_id: "overdue_risk",      display_name: "Overdue & At-Risk Teams",        score: 1.0 },
  { area_id: "audit_readiness",   display_name: "Audit Readiness & Evidence",     score: 1.0 }
]
csod_primary_area : {
  area_id:           "completion_trends",
  display_name:      "Completion Trends & Drivers",
  metrics:           ["completion_rate", "new_assignments_issued",
                      "median_time_to_completion", "assessment_pass_rate"],
  kpis:              ["month_over_month_completion_change", "compliance_training_rate",
                      "average_time_to_completion"],
  data_requirements: ["training_assignment_core", "transcript_core",
                      "training_scorm_core", "assessment_result_core"],
  causal_paths:      ["Increased_assignments → Lower_completion_rate",
                      "Complex_content_or_assessment_failures → Longer_time_to_completion"]
}
```

---

## Stage 7 — Area Confirm  `area_confirm_node`  *(checkpoint)*

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  Here are the 3 analysis areas that fit your question.                       ║
║  Which one should I focus on?                                                ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  ●  Completion Trends & Drivers                                              ║
║     Why is the completion rate dropping, and what's driving it?              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  ○  Overdue & At-Risk Teams                                                  ║
║     Which teams have the most overdue assignments right now?                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  ○  Audit Readiness & Evidence                                               ║
║     Are we ready for the SOC2 audit, and where are the gaps?                 ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

User selects **"Audit Readiness & Evidence"** (most urgent given the SOC2 deadline):

```
csod_confirmed_area_id : "audit_readiness"
csod_primary_area      : {
  area_id:           "audit_readiness",
  display_name:      "Audit Readiness & Evidence",
  metrics:           ["audit_compliance_rate", "mandatory_training_completed_count",
                      "pending_required_modules", "evidence_documentation_count"],
  kpis:              ["audit_readiness_score", "percent_fully_compliant",
                      "compliance_gap_count"],
  data_requirements: ["transcript_core", "training_requirement_tag_core",
                      "training_assignment_core", "training_bundle_core"],
  causal_paths:      ["Low_completion_rate → Failed_audit_items",
                      "Missing_documentation → Reduced_audit_readiness"]
}
```

---

## Stage 8 — Metric Narration  `metric_narration_node`  *(checkpoint)*

LLM generates a plain-language explanation of what will be measured.

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  Here's what I'll measure:                                                   ║
║                                                                              ║
║  I'll calculate your current audit readiness score using completion and      ║
║  evidence data from Cornerstone — specifically how many users have           ║
║  completed each required module and whether completion records are           ║
║  properly timestamped for SOC2 documentation. I'll identify which            ║
║  requirement tags have the largest gaps, rank teams by outstanding           ║
║  assignments, and project whether the remaining completions can be           ║
║  achieved before the audit window closes.                                    ║
║                                                                              ║
║  Key metrics:                                                                ║
║  • audit_readiness_score      — current posture vs audit-pass threshold      ║
║  • compliance_gap_count       — requirement tags below required threshold    ║
║  • pending_required_modules   — outstanding completions across all users     ║
║  • evidence_documentation_count — verified timestamped records available    ║
║                                                                              ║
║  [ Looks right — proceed ]  [ Adjust focus ]                                ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## Stage 9 — Workflow Router  `workflow_router_node`

Packs everything into `compliance_profile` and routes to the CSOD downstream workflow.

### Final `compliance_profile`

```json
{
  "selected_concepts":      ["compliance_training"],
  "selected_area_ids":      ["completion_trends", "overdue_risk", "audit_readiness"],
  "selected_project_ids":   [
    "csod_transcript_statuses",
    "csod_assignments_lat",
    "csod_organizational_units",
    "csod_user_core_details",
    "csod_training_catalog_lo"
  ],
  "priority_metrics": [
    "audit_compliance_rate",
    "mandatory_training_completed_count",
    "pending_required_modules",
    "evidence_documentation_count"
  ],
  "priority_kpis": [
    "audit_readiness_score",
    "percent_fully_compliant",
    "compliance_gap_count"
  ],
  "data_requirements": [
    "transcript_core",
    "training_requirement_tag_core",
    "training_assignment_core",
    "training_bundle_core"
  ],
  "causal_paths": [
    "Low_completion_rate → Failed_audit_items",
    "Missing_documentation → Reduced_audit_readiness"
  ],
  "extracted_signals": [
    { "label": "terminal_metric",          "value": "compliance_training_rate — dropped from 89% to 71%, gap 18pts over 30 days" },
    { "label": "analysis_type",            "value": "Causal decomposition + cohort breakdown" },
    { "label": "primary_driver_hypothesis","value": "Assignment volume surge or content change" },
    { "label": "segmentation_needed",      "value": "OU-level breakdown required" },
    { "label": "implicit",                 "value": "Which 2-3 OUs account for the 18pt drop?" },
    { "label": "terminal_metric",          "value": "audit_readiness_score — composite of percent_fully_compliant + compliance_gap_count" },
    { "label": "urgency",                  "value": "30-day hard deadline — forward projection required" },
    { "label": "compliance_context",       "value": "SOC2 audit — trajectory and evidence matter as much as raw rate" },
    { "label": "analysis_type",            "value": "Gap analysis with forward projection — intervention ordering critical" },
    { "label": "implicit",                 "value": "Is the 19pt gap closable in 30 days?" },
    { "label": "evidence_requirement",     "value": "Timestamped completion records per user per requirement tag required" }
  ],
  "lexy_metric_narration": "I'll calculate your current audit readiness score using completion and evidence data from Cornerstone...",
  "time_window":      "last_30d",
  "org_unit":         "department",
  "training_type":    "all_mandatory",
  "audit_window":     "next_30d"
}
```

### Downstream Routing

```
active_project_id        : "csod_transcript_statuses"    ← primary project for L3 MDL retrieval
selected_data_sources    : ["cornerstone"]
next_agent_id            : "csod-workflow"
is_planner_output        : true
csod_interactive_checkpoints : true
```

---

## Summary — What Changed vs the Old Flow

| | Old Flow | New Flow |
|---|---|---|
| **Concept resolution** | Static registry → all 16 projects returned | LLM + MDL → 4–5 specific projects per intent |
| **Intent splitting** | Single query treated atomically | 2 intents extracted, each with 5–6 dynamic signals |
| **Signal extraction** | None | `terminal_metric`, `urgency`, `analysis_type`, `compliance_context`, `implicit` + more — fully dynamic labels |
| **User selection turn** | `concept_confirm` (text list of concept names) | `intent_selection` (signals panel + projects + area preview per intent) |
| **Project scope downstream** | `csod_resolved_project_ids` = all 16 (static) | `csod_resolved_project_ids` = 4–5 most relevant (LLM-selected) |
| **Area resolution** | LLM over concept/area registry only | LLM over concept/area registry + MDL project metadata |
| **compliance_profile** | No signals, no selected_project_ids | `extracted_signals` + `selected_project_ids` both populated |

---

## Key MDL Tables Used in This Example

| Table | Project | Role in Analysis |
|---|---|---|
| `transcript_core` | `csod_transcript_statuses` | Completion timestamps, pass/fail status per user per course |
| `training_assignment_core` | `csod_assignments_lat` | Assignment dates, due dates, status — drives overdue calculation |
| `user_ou_core` | `csod_organizational_units` | OU hierarchy — maps users to departments for team breakdown |
| `users_core` | `csod_user_core_details` | User master data — active/inactive status filter |
| `training_requirement_tag_core` | `csod_training_catalog_lo` | SOC2 tag mapping — which courses count toward which audit requirement |
| `training_bundle_core` | `csod_training_catalog_lo` | Bundle/curriculum definitions — groups required modules per requirement |

---

*All concept IDs, area IDs, metric names, project IDs, and table names in this example are drawn
directly from the live registries in `preview_out/registries/` and `data/csod_project_metadata_enriched.json`.*

# CCE Intent Planner — Dashboard & Metrics Tracking Example
### Platform: Cornerstone OnDemand (CSOD Learn)

This document shows a complete CCE Intent Planner trace for a **dashboard build and recurring
metrics tracking** request — a structurally different query type from the one-time diagnostic
example. Signal labels, project selection, area routing, and scoping questions all shift
to reflect the operational/monitoring intent.

---

## Example Query

> **"We need a weekly operational dashboard for our L&D team showing compliance training
> completion by business unit, certification expiry risk across the org, and overall LMS
> platform engagement trends. Department heads should get this every Monday morning."**

---

## How This Differs from a Diagnostic Query

| Dimension | Diagnostic ("Why is rate dropping?") | Dashboard ("Build a weekly view") |
|---|---|---|
| **Query intent** | Investigate a known problem | Construct a recurring operational view |
| **Output type** | Root cause + ranked factors | Multi-panel dashboard with stable KPIs |
| **Time orientation** | Backward-looking (what happened) | Current state + forward projection |
| **Audience** | Analyst / L&D team | Department heads + L&D team |
| **Signal labels emitted** | `terminal_metric`, `urgency`, `implicit` | `dashboard_type`, `refresh_cadence`, `audience`, `visualization_intent` |
| **Area selection** | Causal / drill-down areas | Tracking / overview areas |
| **Scoping questions** | Time window, org unit | BU scope, threshold alerts, delivery format |

---

## Stage 0 — Datasource Selection

```
csod_selected_datasource : "cornerstone"
csod_datasource_confirmed : true          ← auto-confirmed
```

---

## Stage 1 — Intent Splitting  `intent_splitter_node`

The query covers three independent tracking domains — the LLM splits into **3 intents**.

### LLM Output (raw JSON)

```json
[
  {
    "intent_id": "i1",
    "description": "Weekly compliance training completion dashboard by business unit — current rate, overdue count, and trend line per BU",
    "analytical_goal": "Give department heads a stable, recurring view of where each BU stands on mandatory training completion, with overdue flagging",
    "key_entities": ["completion_rate", "overdue_assignment_count", "org_unit", "mandatory_training"],
    "extracted_signals": [
      {
        "label": "dashboard_type",
        "value": "Operational tracking — recurring weekly snapshot, not one-time analysis; requires stable metric definitions and consistent BU grouping"
      },
      {
        "label": "primary_kpi",
        "value": "compliance_training_rate by business unit — headline number each department head sees first; must be comparable week-over-week"
      },
      {
        "label": "audience",
        "value": "Department heads — need BU-level aggregation with overdue flags; do NOT need individual user drill-down at this layer"
      },
      {
        "label": "refresh_cadence",
        "value": "Weekly, delivered Monday morning — data must reflect previous week's completions; requires a defined cutoff window (e.g. Sunday EOD)"
      },
      {
        "label": "visualization_intent",
        "value": "Current rate (large KPI chip) + 8-week trend sparkline + overdue count ranked by OU — standard L&D operations format"
      },
      {
        "label": "alert_threshold",
        "value": "BUs below 80% completion rate or with >10 overdue assignments should be highlighted as red — threshold is configurable"
      }
    ]
  },
  {
    "intent_id": "i2",
    "description": "Certification expiry risk tracker — who has certifications expiring in the next 30/60/90 days and what is the renewal rate trend",
    "analytical_goal": "Surface certification lapse risk before it becomes a compliance or operational problem, prioritized by OU and expiry window",
    "key_entities": ["certifications_expiring_count", "percent_expiring_within_30_days", "certification_renewal_rate", "org_unit"],
    "extracted_signals": [
      {
        "label": "dashboard_type",
        "value": "Risk monitoring — forward-looking expiry calendar combined with renewal rate; acts as an early-warning panel not a historical report"
      },
      {
        "label": "primary_kpi",
        "value": "percent_expiring_within_30_days — the most urgent signal; drives immediate manager action before lapse occurs"
      },
      {
        "label": "time_horizon",
        "value": "Rolling 30/60/90-day expiry windows — standard triaging buckets for certification ops; allows prioritization by urgency tier"
      },
      {
        "label": "audience",
        "value": "L&D team and compliance managers — need user-level detail (name, cert type, expiry date, OU) to initiate outreach"
      },
      {
        "label": "action_type",
        "value": "Outreach trigger — the dashboard must surface manager contact alongside user/cert data so L&D can escalate directly"
      },
      {
        "label": "implicit",
        "value": "Are we losing certifications faster than we're renewing them? Renewal rate trend determines whether the backlog is growing or shrinking"
      }
    ]
  },
  {
    "intent_id": "i3",
    "description": "LMS platform engagement trend — weekly active users, session activity, and license utilization across the org",
    "analytical_goal": "Give the L&D team a platform health view showing whether users are actively engaging with the LMS or if adoption is stalling",
    "key_entities": ["active_users", "weekly_active_user_percentage", "avg_sessions_per_user", "license_utilization_rate"],
    "extracted_signals": [
      {
        "label": "dashboard_type",
        "value": "Platform health monitoring — engagement KPIs that signal whether the LMS investment is being used; input for L&D strategy decisions"
      },
      {
        "label": "primary_kpi",
        "value": "weekly_active_user_percentage — ratio of users who logged in and interacted this week vs total licensed seats; proxy for adoption health"
      },
      {
        "label": "audience",
        "value": "L&D team internally — granular enough to see which OUs are disengaged and which content drives return visits"
      },
      {
        "label": "refresh_cadence",
        "value": "Weekly rollup with 12-week trailing trend — single-week snapshots are noisy; trend line over 12 weeks reveals structural patterns"
      },
      {
        "label": "segmentation",
        "value": "Engagement must be broken by OU and delivery method (SCORM vs ILT vs eLearning) — different modalities have different engagement patterns"
      },
      {
        "label": "implicit",
        "value": "Are users logging in but not completing content, or are they not logging in at all? These require different interventions"
      }
    ]
  }
]
```

### State Written
```
csod_intent_splits: [
  { intent_id: "i1", description: "Compliance completion by BU", extracted_signals: [6] },
  { intent_id: "i2", description: "Certification expiry risk tracker", extracted_signals: [6] },
  { intent_id: "i3", description: "LMS platform engagement trend", extracted_signals: [6] }
]
```

---

## Stage 2 — MDL-Aware Resolution  `mdl_project_resolver_node`

### LLM Resolution — Condensed

| Intent | Concept | Matched Projects | Areas |
|---|---|---|---|
| i1 | `compliance_training` | `csod_transcript_statuses`, `csod_assignments_lat`, `csod_organizational_units` | `completion_overview`, `overdue_risk` |
| i2 | `certification_tracking` | `csod_transcript_statuses`, `csod_user_core_details`, `csod_organizational_units` | `expiring_certifications`, `renewal_and_completion_rate` |
| i3 | `lms_health` | `csod_user_core_details`, `csod_transcript_statuses`, `csod_scorm` | `platform_engagement`, `adoption_trend` |

### Project Rationale (LLM explanations)

**i1 — Compliance Completion:**
> Transcript tables hold the actual completion and status records; assignment tables provide the
> mandatory assignment baseline needed to calculate the rate; OU tables are required to group
> users into BUs for the department head view.

**i2 — Certification Expiry:**
> Transcript records include certification completion timestamps and expiry dates; user tables
> supply active status and manager chain for outreach; OU tables segment by business unit.

**i3 — LMS Engagement:**
> User tables record login activity and employment status; SCORM session tables capture
> content interaction depth (session duration, error rates, interaction history); transcript
> tables provide the completion signal that confirms whether engagement led to outcomes.

---

### Resolved Areas — Full Detail

#### Intent i1: `compliance_training`

**Area 1: `completion_overview` — Completion Overview**

| Field | Value |
|---|---|
| Description | At-a-glance view of overall training assignment completion and timeliness across the org |
| Metrics | `total_assigned`, `total_completed`, `completion_rate`, `avg_time_to_completion` |
| KPIs | `overall_completion_rate`, `avg_time_to_completion_days`, `percent_overdue` |
| Filters | `org_unit`, `delivery_method`, `assignment_status`, `date_range` |
| Dashboard Axes | overall_completion_rate · completion_by_org_unit · avg_time_to_completion_trend |
| Causal Paths | `assignment_availability_window → completion_rate` · `assignment_status_on_publish → overall_completion_rate` |
| MDL Tables | `transcript_core`, `transcript_assignment_core`, `training_assignment_core`, `ou_core` |

**Area 2: `overdue_risk` — Overdue & At-Risk Teams**

| Field | Value |
|---|---|
| Description | Identify teams and users with overdue mandatory compliance assignments |
| Metrics | `total_mandatory_assignments`, `overdue_assignment_count`, `average_days_overdue`, `percent_assignments_past_due` |
| KPIs | `overdue_rate`, `on_time_completion_rate`, `at_risk_team_count` |
| Filters | `org_unit`, `due_date_range`, `training_type`, `user_status` |
| Dashboard Axes | Overdue assignments by org unit · Average days overdue trend · Top at-risk teams |
| Causal Paths | `High_assignment_volume → Decreased_on_time_completion_rate` |
| MDL Tables | `training_assignment_core`, `transcript_core`, `user_ou_core`, `users_core` |

#### Intent i2: `certification_tracking`

**Area 1: `expiring_certifications` — Expiring Certifications**

| Field | Value |
|---|---|
| Description | Identifies certifications expiring in upcoming windows and users who need action |
| Metrics | `certifications_expiring_count`, `days_until_expiration_avg`, `expirations_by_time_window`, `users_with_expiring_certifications` |
| KPIs | `percent_expiring_within_30_days`, `total_expiring_next_90_days` |
| Filters | `expiration_date`, `org_unit`, `certification_status`, `training_type` |
| Dashboard Axes | Expirations timeline (30/60/90 days) · Users with upcoming expirations by OU · Expiry heatmap by cert type |
| Causal Paths | `insufficient_notification → missed_renewals` · `expiring_certs_concentrated_in_unit → elevated_compliance_risk` |
| MDL Tables | `transcript_core`, `training_core`, `users_core`, `user_ou_core` |

**Area 2: `renewal_and_completion_rate` — Renewal & Completion Rate**

| Field | Value |
|---|---|
| Description | Measures renewal effectiveness — how many eligible learners complete recertification on time |
| Metrics | `renewal_completion_count`, `average_time_to_renewal_days`, `overdue_renewal_count`, `renewal_attempts_by_delivery_type` |
| KPIs | `certification_renewal_rate`, `average_days_to_renew` |
| Filters | `certification_type`, `org_unit`, `time_period`, `delivery_method` |
| Dashboard Axes | Renewal rate over time · Average time to renew by cert · Completion by delivery method |
| Causal Paths | `limited_training_availability → delayed_renewal_completion` |
| MDL Tables | `transcript_core`, `training_assignment_core`, `training_availability_by_user_core`, `training_ilt_session_core` |

#### Intent i3: `lms_health`

**Area 1: `platform_engagement` — Platform Engagement**

| Field | Value |
|---|---|
| Description | Tracks user activity and learning interactions — how actively users are using the LMS |
| Metrics | `active_users`, `avg_sessions_per_user`, `avg_session_duration_seconds`, `course_completion_rate` |
| KPIs | `daily_active_users`, `weekly_active_user_percentage`, `course_completion_rate_target` |
| Filters | `org_unit`, `user_type`, `time_period`, `training_id` |
| Dashboard Axes | Engagement Over Time (DAU/WAU/MAU) · Top Courses by Active Users · Session Duration Distribution |
| Causal Paths | `increased_reminders → higher_active_users` · `high_scorm_error_rate → reduced_session_duration` |
| MDL Tables | `training_assignment_user_core`, `user_login_core`, `scorm_session`, `transcript_core` |

**Area 2: `adoption_trend` — Adoption & Growth**

| Field | Value |
|---|---|
| Description | Measures new user adoption, license utilization, and course uptake |
| Metrics | `monthly_new_users`, `adoption_rate`, `avg_courses_per_user` |
| KPIs | `month_over_month_user_growth_pct`, `user_adoption_rate_target`, `license_utilization_rate` |
| Filters | `org_unit`, `user_employment_status`, `time_period`, `training_type` |
| Dashboard Axes | User Growth & Adoption Trend · License Utilization and Active Seats · New Users by OU |
| Causal Paths | `improved_onboarding → higher_adoption_rate` · `increased_catalog_visibility → higher_avg_courses_per_user` |
| MDL Tables | `users_core`, `user_ou_core`, `training_purchase_core`, `training_core` |

---

## Stage 3 — Intent Confirm Checkpoint  `csod_intent_confirm_node`

### What the User Sees (conceptual UI)

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  I found 3 distinct analytical angles in your question.                      ║
║  Select the one(s) you'd like to explore:                                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  ☑  Compliance Training Risk  ·  Weekly completion tracking by BU           ║
║     Projects: Transcript & Statuses · Assignments (LAT) · Org Units          ║
║     Areas:    Completion Overview · Overdue & At-Risk Teams                  ║
║                                                                              ║
║     SIGNAL EXTRACTION ────────────────────────────────────────────           ║
║     dashboard_type        Operational tracking — recurring weekly snapshot   ║
║     primary_kpi           compliance_training_rate by business unit          ║
║     audience              Department heads — BU-level aggregation + flags    ║
║     refresh_cadence       Weekly, Monday morning, Sunday EOD cutoff          ║
║     visualization_intent  KPI chip + 8-week sparkline + overdue ranked by OU ║
║     alert_threshold       BUs below 80% or >10 overdue flagged red           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  ☑  Certification Tracking  ·  Expiry risk & renewal rate                   ║
║     Projects: Transcript & Statuses · User Core Details · Org Units          ║
║     Areas:    Expiring Certifications · Renewal & Completion Rate            ║
║                                                                              ║
║     SIGNAL EXTRACTION ────────────────────────────────────────────           ║
║     dashboard_type        Risk monitoring — forward-looking expiry calendar  ║
║     primary_kpi           percent_expiring_within_30_days                    ║
║     time_horizon          Rolling 30/60/90-day expiry buckets                ║
║     audience              L&D team + compliance managers — user-level detail ║
║     action_type           Outreach trigger — manager contact alongside data  ║
║     implicit              Is renewal rate keeping pace with expirations?     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  ☑  LMS Health & KPI Monitoring  ·  Platform engagement trend               ║
║     Projects: User Core Details · Transcript & Statuses · SCORM Content      ║
║     Areas:    Platform Engagement · Adoption & Growth                        ║
║                                                                              ║
║     SIGNAL EXTRACTION ────────────────────────────────────────────           ║
║     dashboard_type        Platform health — engagement KPIs for LMS ROI     ║
║     primary_kpi           weekly_active_user_percentage                      ║
║     audience              L&D team — OU + delivery method breakdown          ║
║     refresh_cadence       Weekly with 12-week trailing trend                 ║
║     segmentation          OU × delivery method (SCORM / ILT / eLearning)    ║
║     implicit              Login but no completion vs not logging in at all?  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  ○  Let me rephrase                                                          ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### Checkpoint Payload (abridged)

```json
{
  "phase": "intent_confirm",
  "turn": {
    "turn_type": "intent_selection",
    "message": "I found 3 distinct analytical angles in your question. Select the one(s) you'd like to explore:",
    "options": [
      {
        "id": "i1",
        "label": "Compliance Training Risk",
        "concept_id": "compliance_training",
        "project_ids": ["csod_transcript_statuses", "csod_assignments_lat", "csod_organizational_units"],
        "area_ids": ["completion_overview", "overdue_risk"],
        "top_metrics": ["completion_rate", "total_assigned", "avg_time_to_completion"],
        "extracted_signals": [
          { "label": "dashboard_type",       "value": "Operational tracking — recurring weekly snapshot" },
          { "label": "primary_kpi",          "value": "compliance_training_rate by business unit" },
          { "label": "audience",             "value": "Department heads — BU-level aggregation + overdue flags" },
          { "label": "refresh_cadence",      "value": "Weekly, Monday morning, Sunday EOD cutoff" },
          { "label": "visualization_intent", "value": "KPI chip + 8-week sparkline + overdue ranked by OU" },
          { "label": "alert_threshold",      "value": "BUs below 80% or >10 overdue flagged red" }
        ]
      },
      {
        "id": "i2",
        "label": "Certification Tracking",
        "concept_id": "certification_tracking",
        "project_ids": ["csod_transcript_statuses", "csod_user_core_details", "csod_organizational_units"],
        "area_ids": ["expiring_certifications", "renewal_and_completion_rate"],
        "top_metrics": ["certifications_expiring_count", "percent_expiring_within_30_days", "certification_renewal_rate"],
        "extracted_signals": [
          { "label": "dashboard_type", "value": "Risk monitoring — forward-looking expiry calendar" },
          { "label": "primary_kpi",    "value": "percent_expiring_within_30_days" },
          { "label": "time_horizon",   "value": "Rolling 30/60/90-day expiry buckets" },
          { "label": "audience",       "value": "L&D team + compliance managers — user-level detail" },
          { "label": "action_type",    "value": "Outreach trigger — manager contact alongside user/cert data" },
          { "label": "implicit",       "value": "Is renewal rate keeping pace with expirations?" }
        ]
      },
      {
        "id": "i3",
        "label": "LMS Health & KPI Monitoring",
        "concept_id": "lms_health",
        "project_ids": ["csod_user_core_details", "csod_transcript_statuses", "csod_scorm"],
        "area_ids": ["platform_engagement", "adoption_trend"],
        "top_metrics": ["active_users", "weekly_active_user_percentage", "avg_sessions_per_user"],
        "extracted_signals": [
          { "label": "dashboard_type",  "value": "Platform health monitoring — engagement KPIs" },
          { "label": "primary_kpi",     "value": "weekly_active_user_percentage" },
          { "label": "audience",        "value": "L&D team — OU + delivery method breakdown" },
          { "label": "refresh_cadence", "value": "Weekly with 12-week trailing trend" },
          { "label": "segmentation",    "value": "OU × delivery method (SCORM / ILT / eLearning)" },
          { "label": "implicit",        "value": "Login but no completion vs not logging in at all?" }
        ]
      },
      { "id": "rephrase", "label": "Let me rephrase", "action": "rephrase" }
    ],
    "metadata": {
      "signal_map": {
        "i1": [ "dashboard_type", "primary_kpi", "audience", "refresh_cadence", "visualization_intent", "alert_threshold" ],
        "i2": [ "dashboard_type", "primary_kpi", "time_horizon", "audience", "action_type", "implicit" ],
        "i3": [ "dashboard_type", "primary_kpi", "audience", "refresh_cadence", "segmentation", "implicit" ]
      }
    }
  },
  "resume_with_field": "csod_selected_intent_ids"
}
```

### User Selects All Three

```json
{ "csod_selected_intent_ids": ["i1", "i2", "i3"] }
```

---

## Stage 3 Resume — State After `_apply_selections()`

```
csod_confirmed_concept_ids    : ["compliance_training", "certification_tracking", "lms_health"]
csod_resolved_project_ids     : [
  "csod_transcript_statuses",      ← shared across all 3 intents
  "csod_assignments_lat",          ← compliance tracking
  "csod_organizational_units",     ← shared BU grouping
  "csod_user_core_details",        ← cert + engagement
  "csod_scorm"                     ← SCORM engagement data
]                                  5 projects, not all 16
csod_primary_project_id       : "csod_transcript_statuses"
csod_llm_resolved_areas       : {
  "compliance_training":   [ completion_overview, overdue_risk ],
  "certification_tracking": [ expiring_certifications, renewal_and_completion_rate ],
  "lms_health":            [ platform_engagement, adoption_trend ]
}
csod_extracted_signals        : [
  { label: "dashboard_type",       value: "Operational tracking — recurring weekly snapshot" },
  { label: "primary_kpi",          value: "compliance_training_rate by business unit" },
  { label: "audience",             value: "Department heads — BU-level aggregation + overdue flags" },
  { label: "refresh_cadence",      value: "Weekly, Monday morning, Sunday EOD cutoff" },
  { label: "visualization_intent", value: "KPI chip + 8-week sparkline + overdue ranked by OU" },
  { label: "alert_threshold",      value: "BUs below 80% or >10 overdue flagged red" },
  { label: "dashboard_type",       value: "Risk monitoring — forward-looking expiry calendar" },
  { label: "primary_kpi",          value: "percent_expiring_within_30_days" },
  { label: "time_horizon",         value: "Rolling 30/60/90-day expiry buckets" },
  { label: "action_type",          value: "Outreach trigger — manager contact alongside data" },
  { label: "implicit",             value: "Is renewal rate keeping pace with expirations?" },
  { label: "primary_kpi",          value: "weekly_active_user_percentage" },
  { label: "segmentation",         value: "OU × delivery method (SCORM / ILT / eLearning)" },
  { label: "implicit",             value: "Login but no completion vs not logging in at all?" }
]
```

---

## Stage 4 — Preliminary Area Matcher

Uses first LLM-resolved area for primary concept (`compliance_training → completion_overview`)
to determine which scoping filters to ask:

```
Filters from completion_overview: ["org_unit", "delivery_method", "assignment_status", "date_range"]
```

---

## Stage 5 — Scoping  `scoping_node`  *(checkpoint)*

Filter hints extracted from original query:
- `org_unit` → `whole_org` ("across the org")
- `time_period` → `last_8_weeks` (implied by "weekly trend" + "Monday" delivery cadence)

### Scoping Questions Shown

```
╔══════════════════════════════════════════════════════╗
║  A few quick questions to narrow the dashboard:       ║
╠══════════════════════════════════════════════════════╣
║  Organizational scope                                 ║
║  ● Whole organization  ○ Specific divisions           ║
║  ○ Select business units                              ║
╠══════════════════════════════════════════════════════╣
║  Completion threshold for alerts                      ║
║  ○ 70%  ● 80%  ○ 90%  ○ Custom                        ║
╠══════════════════════════════════════════════════════╣
║  Training type in scope                               ║
║  ● All mandatory  ○ Compliance-tagged only            ║
║  ○ All training (including optional)                  ║
╠══════════════════════════════════════════════════════╣
║  Certification expiry window to highlight             ║
║  ○ 30 days  ● 30 / 60 / 90 days  ○ Custom            ║
╚══════════════════════════════════════════════════════╝
```

### User Answers

```
csod_scoping_answers : {
  org_unit:         "whole_org",
  alert_threshold:  "80_percent",
  training_type:    "all_mandatory",
  deadline_window:  "30_60_90_days"
}
```

---

## Stage 6 — Area Matcher  `area_matcher_node`

Returns top 3 areas from `csod_llm_resolved_areas` across all confirmed concepts:

```
csod_area_matches : [
  { area_id: "completion_overview",         concept_id: "compliance_training",    score: 1.0 },
  { area_id: "expiring_certifications",     concept_id: "certification_tracking", score: 1.0 },
  { area_id: "platform_engagement",         concept_id: "lms_health",             score: 1.0 }
]
csod_primary_area : completion_overview    ← first area from primary concept
```

---

## Stage 7 — Area Confirm  `area_confirm_node`  *(checkpoint)*

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  Here are the 3 analysis areas I'll build the dashboard around.             ║
║  Which should be the primary focus panel?                                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  ●  Completion Overview                                                      ║
║     Org-wide completion rate, overdue %, and BU breakdown — weekly view      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  ○  Expiring Certifications                                                  ║
║     Rolling 30/60/90-day expiry calendar with user-level detail              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  ○  Platform Engagement                                                      ║
║     Weekly active users, sessions, and adoption trend                        ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

User selects **"Completion Overview"** as the primary focus panel:

```
csod_confirmed_area_id : "completion_overview"
csod_primary_area : {
  area_id:           "completion_overview",
  metrics:           ["total_assigned", "total_completed", "completion_rate", "avg_time_to_completion"],
  kpis:              ["overall_completion_rate", "avg_time_to_completion_days", "percent_overdue"],
  data_requirements: ["transcript_core", "transcript_assignment_core",
                      "training_assignment_core", "ou_core"],
  causal_paths:      ["assignment_availability_window → completion_rate",
                      "assignment_status_on_publish → overall_completion_rate"]
}
```

---

## Stage 8 — Metric Narration  `metric_narration_node`  *(checkpoint)*

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  Here's what I'll build:                                                     ║
║                                                                              ║
║  I'll create a weekly operational dashboard anchored on compliance           ║
║  training completion across business units, pulling data from Cornerstone   ║
║  transcript and assignment records. The primary panel will show the          ║
║  overall completion rate with an 8-week trend, BU-level breakdown with       ║
║  red flags for units below 80%, and a ranked overdue list.                  ║
║                                                                              ║
║  The dashboard will also include a certification expiry panel (30/60/90-    ║
║  day rolling windows) and a platform engagement section showing weekly       ║
║  active users and SCORM interaction trends.                                  ║
║                                                                              ║
║  Primary metrics tracked:                                                    ║
║  • overall_completion_rate        — org-wide mandatory training completion   ║
║  • completion_rate by org_unit    — per-BU view for department heads         ║
║  • percent_overdue                — BUs above threshold flagged red          ║
║  • percent_expiring_within_30d    — certs at immediate lapse risk            ║
║  • weekly_active_user_percentage  — LMS engagement health                   ║
║                                                                              ║
║  [ Looks right — proceed ]  [ Adjust focus ]                                ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## Stage 9 — Workflow Router  `workflow_router_node`

### Final `compliance_profile`

```json
{
  "selected_concepts":    ["compliance_training", "certification_tracking", "lms_health"],
  "selected_area_ids":    ["completion_overview", "expiring_certifications", "platform_engagement"],
  "selected_project_ids": [
    "csod_transcript_statuses",
    "csod_assignments_lat",
    "csod_organizational_units",
    "csod_user_core_details",
    "csod_scorm"
  ],
  "priority_metrics": [
    "total_assigned",
    "total_completed",
    "completion_rate",
    "avg_time_to_completion"
  ],
  "priority_kpis": [
    "overall_completion_rate",
    "avg_time_to_completion_days",
    "percent_overdue"
  ],
  "data_requirements": [
    "transcript_core",
    "transcript_assignment_core",
    "training_assignment_core",
    "ou_core"
  ],
  "causal_paths": [
    "assignment_availability_window → completion_rate",
    "assignment_status_on_publish → overall_completion_rate"
  ],
  "extracted_signals": [
    { "label": "dashboard_type",       "value": "Operational tracking — recurring weekly snapshot" },
    { "label": "primary_kpi",          "value": "compliance_training_rate by business unit" },
    { "label": "audience",             "value": "Department heads — BU-level aggregation + overdue flags" },
    { "label": "refresh_cadence",      "value": "Weekly, Monday morning, Sunday EOD cutoff" },
    { "label": "visualization_intent", "value": "KPI chip + 8-week sparkline + overdue ranked by OU" },
    { "label": "alert_threshold",      "value": "BUs below 80% or >10 overdue flagged red" },
    { "label": "primary_kpi",          "value": "percent_expiring_within_30_days" },
    { "label": "time_horizon",         "value": "Rolling 30/60/90-day expiry buckets" },
    { "label": "action_type",          "value": "Outreach trigger — manager contact alongside data" },
    { "label": "primary_kpi",          "value": "weekly_active_user_percentage" },
    { "label": "segmentation",         "value": "OU × delivery method (SCORM / ILT / eLearning)" }
  ],
  "lexy_metric_narration": "I'll create a weekly operational dashboard anchored on compliance training completion...",
  "org_unit":        "whole_org",
  "training_type":   "all_mandatory",
  "deadline_window": "30_60_90_days"
}
```

---

## Full MDL Table Map for this Dashboard

| Table | Project | Used for |
|---|---|---|
| `transcript_core` | `csod_transcript_statuses` | Completion timestamps, status, pass/fail per user per course |
| `transcript_assignment_core` | `csod_transcript_statuses` | Links transcript records to source assignment — required for rate calculation |
| `training_assignment_core` | `csod_assignments_lat` | Assignment dates, due dates, mandatory flag — denominator for completion rate |
| `ou_core` | `csod_organizational_units` | OU tree — maps users to business units for BU-level dashboard panels |
| `user_ou_core` | `csod_organizational_units` | User↔OU membership — resolves which BU each user belongs to |
| `users_core` | `csod_user_core_details` | Active/inactive status — filters to only current employees |
| `training_core` | `csod_user_core_details` | Course metadata — certification flag, expiry window definition |
| `training_availability_by_user_core` | `csod_user_core_details` | Per-user training availability — used for renewal scheduling |
| `scorm_session` | `csod_scorm` | SCORM session records — engagement depth, session duration, error counts |
| `scorm_subsession_interaction` | `csod_scorm` | Interaction-level SCORM data — determines whether users engaged with content or just launched it |

---

## Signal Label Comparison: Dashboard vs Diagnostic

The LLM chooses completely different signal labels depending on the **intent type** — the
labels are not a fixed taxonomy but are generated to match the analytical context.

| Signal Label | Appears in Dashboard query? | Appears in Diagnostic query? | Why |
|---|---|---|---|
| `dashboard_type` | ✅ | ❌ | Build request — defines what kind of artefact is being created |
| `refresh_cadence` | ✅ | ❌ | Recurring output — cadence defines the data window |
| `audience` | ✅ | ❌ | Delivery context — shapes aggregation level and detail |
| `visualization_intent` | ✅ | ❌ | Output format — KPI chip vs trend line vs ranked list |
| `alert_threshold` | ✅ | ❌ | Operational trigger — defines red/amber thresholds |
| `action_type` | ✅ | ❌ | Outreach trigger — what action the dashboard enables |
| `terminal_metric` | ❌ | ✅ | Diagnostic — one metric being investigated |
| `urgency` | ❌ | ✅ | Deadline-driven — 30-day constraint shapes the analysis |
| `compliance_context` | ❌ | ✅ | Audit framing — SOC2 changes what "good" looks like |
| `primary_driver_hypothesis` | ❌ | ✅ | Causal investigation — hypothesis to test |
| `implicit` | ✅ (some) | ✅ | Unstated real question — appears in both but with different framing |
| `evidence_requirement` | ❌ | ✅ | Audit-specific — documentation completeness |

---

*All concept IDs, area IDs, metric names, KPI names, project IDs, and table names are drawn
directly from the live registries in `preview_out/registries/` and `data/csod_project_metadata_enriched.json`.*

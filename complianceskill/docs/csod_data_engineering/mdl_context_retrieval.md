# Stage 2.5 — MDL Retrieval

**Position in pipeline:** After Goal planner (Stage 2) · Before Capability resolver (Stage 3)  
**Trigger:** Any Analysis-path question — NL or alert  
**Purpose:** Ground causal concepts in real schema objects so metric recommendations
             are semantically precise and actually satisfiable from connected sources.

---

## What this stage is NOT doing

- Not generating SQL
- Not building query strings
- Not deciding which agent runs what

The SQL agent handles all query construction downstream, reading the MDL context
as one of its inputs. This stage only resolves: *which metrics exist, what they
mean semantically, and how they relate to the causal concepts*.

---

## Inputs consumed

From state at entry to Stage 2.5:

```python
# From goal planner (Stage 2)
state["candidate_concepts"]  # list of concepts with required_capabilities per concept
state["active_domains"]      # ["lms"]
state["focus_areas"]         # ["training_compliance"]
state["primary_domain"]      # "lms"
state["terminal"]            # "compliance_training_lms"

# From tenant registry (Postgres — loaded once at session start)
tenant["source_systems"]     # ["csod"]
tenant["tenant_id"]          # "acme_corp"
```

---

## Retrieval sequence

Three tiers queried in order. Each tier narrows what the next tier searches for.

---

### L1 — Source system confirmation

Confirm the connected source system is active and which schema namespace to search.
Reads from `lexy_registered_adapters` (Postgres). Not a vector query.

```python
l1_result = {
  "source_id":        "csod",
  "tenant_id":        "acme_corp",
  "status":           "active",
  "schema_namespace": "csod",          # prefix for all L2/L3 lookups
  "domain_coverage":  ["lms", "hr"],   # what domains this source covers
  "last_synced":      "2026-03-19T22:00:00Z",
}
```

If status ≠ active → capability resolver will mark all capabilities as UNRESOLVABLE.
Pipeline halts with a structured error before questions are generated.

---

### L2 — Table / entity level

Query the L2 Qdrant collection for tables that are relevant to the active
`focus_areas` and `active_domains`. L2 records describe tables: what business
entity they represent, their grain, primary and foreign keys, and which
capability tags they satisfy.

**Query:**

```python
l2_queries = [
  {
    "query_text": "compliance training completion rate lms learning management",
    "filter":     { "source_system": "csod", "domain": "lms" },
    "n_results":  8,
  },
  {
    "query_text": "organization department segmentation user hierarchy",
    "filter":     { "source_system": "csod", "domain": "lms" },
    "n_results":  5,
  },
]
```

**L2 results — table registry:**

```yaml
csod.trans_completion_fact:
  description: >
    Central fact table. One row per user-curriculum assignment.
    Tracks completion lifecycle — not started, in progress, completed.
    Use for all completion rate and overdue assignment calculations.
  grain:             "one row per user × curriculum assignment"
  capability_tags:   ["completion.rate", "metric.aggregatable", "deadline.dimension"]
  primary_key:       [user_id, curriculum_id, assignment_date]
  foreign_keys:
    - user_id       → csod.org_unit_dim.user_id
    - curriculum_id → csod.curriculum_dim.curriculum_id
  filters_required:
    - "required_flag = TRUE  (scope to mandatory compliance curricula only)"
  semantic_note: >
    completion_status values: C=completed, I=in-progress, N=not-started.
    Completion rate = COUNT(status=C) / COUNT(*) for the scoped population.

csod.curriculum_dim:
  description: >
    One row per curriculum definition. Holds deadline, required flag,
    and curriculum path configuration. Join to fact table on curriculum_id.
  grain:             "one row per curriculum"
  capability_tags:   ["deadline.dimension", "deadline.buffer_days"]
  primary_key:       [curriculum_id]
  semantic_note: >
    has_completion_path = FALSE indicates a broken curriculum configuration —
    assignments in this curriculum cannot reach status=C regardless of learner
    action. Flag these separately in coverage analysis.

csod.org_unit_dim:
  description: >
    User-to-organisation mapping. Supports grouping by department, region,
    manager, and cost centre. One row per user.
  grain:             "one row per user"
  capability_tags:   ["entity.segmentation_dimension"]
  primary_key:       [user_id]
  foreign_keys:
    - manager_id → csod.org_unit_dim.user_id   # self-referencing for hierarchy
  semantic_note: >
    department_name is the primary segmentation dimension for coverage analysis.
    region is secondary. Both are available for cohort_comparator activation.

csod.user_activity:
  description: >
    Daily platform engagement log. One row per user per active day.
    Use for login frequency and engagement trend signals only.
    Do not use for completion rate calculations — different grain.
  grain:             "one row per user per day"
  capability_tags:   ["engagement.login_trend"]
  foreign_keys:
    - user_id → csod.org_unit_dim.user_id
  semantic_note: >
    Engagement trend = rolling average of login_count over a time window.
    Declining trend (negative slope over 14+ days) is a leading indicator
    for completion rate drop with ~21-day lag per causal edge metadata.
```

---

### L3 — Column / metric level

Query the L3 Qdrant collection for specific columns within the tables identified
in L2. L3 records are the most granular: column name, type, semantic description,
value semantics, and which capability it satisfies.

**Query — one per distinct `required_capability` across all candidate concepts:**

```python
l3_queries = {
  "completion.rate": {
    "query_text": "completion status finished done completed training indicator",
    "filter":     { "table": "csod.trans_completion_fact" },
    "n_results":  3,
  },
  "deadline.dimension": {
    "query_text": "due date deadline expiry cutoff assignment end date",
    "filter":     { "table": "csod.curriculum_dim" },
    "n_results":  3,
  },
  "entity.segmentation_dimension": {
    "query_text": "department organization group team segment label",
    "filter":     { "table": "csod.org_unit_dim" },
    "n_results":  3,
  },
  "engagement.login_trend": {
    "query_text": "login last active session frequency platform access",
    "filter":     { "table": "csod.user_activity" },
    "n_results":  3,
  },
  "deadline.buffer_days": {
    "query_text": "warning buffer grace days before deadline",
    "filter":     { "table": "csod.curriculum_dim" },
    "n_results":  2,
  },
}
```

**L3 results — column registry:**

```yaml
csod.trans_completion_fact.completion_status:
  capability:        "completion.rate"
  type:              CHAR(1)
  value_semantics:   "C = completed · I = in-progress · N = not started"
  metric_role:       "numerator signal — COUNT WHERE = C / total COUNT"
  semantic_note: >
    Coverage rate = proportion of assigned learners who have reached C.
    Gap = (target_rate - actual_rate). Negative gap = at risk.

csod.trans_completion_fact.assignment_date:
  capability:        "metric.aggregatable"
  type:              DATE
  semantic_note: >
    Use for scoping time windows. Overdue = due_date < today AND status ≠ C.

csod.curriculum_dim.due_date:
  capability:        "deadline.dimension"
  type:              DATE
  semantic_note: >
    Hard deadline per curriculum. Scope coverage queries to due_date <= audit_deadline
    to limit to curricula that must close before the audit.

csod.curriculum_dim.required_flag:
  capability:        "completion.rate"  # filter guard
  type:              BOOLEAN
  semantic_note: >
    Must = TRUE for compliance scope. Including optional curricula inflates
    the denominator and depresses the apparent completion rate artificially.

csod.curriculum_dim.has_completion_path:
  capability:        "metric.current_value"   # diagnostic signal
  type:              BOOLEAN
  semantic_note: >
    FALSE = curriculum is misconfigured. Assignments cannot complete.
    Surface these separately — they are a structural cause, not a learner cause.

csod.curriculum_dim.warning_days:
  capability:        "deadline.buffer_days"
  type:              INT
  semantic_note: >
    Days before due_date at which escalation should begin. Feeds deadline_sla
    urgency amplifier: if (due_date - today) < warning_days → urgency HIGH.

csod.org_unit_dim.department_name:
  capability:        "entity.segmentation_dimension"
  type:              VARCHAR
  semantic_note: >
    Primary GROUP BY dimension for coverage gap analysis by segment.

csod.user_activity.login_count:
  capability:        "engagement.login_trend"
  type:              INT
  semantic_note: >
    Daily login events per user. Aggregate with AVG over 14-21 day window
    to produce trend signal. Declining average is the causal precursor
    to completion rate drop per edge engagement_signal → compliance_training_lms.
```

---

## Output — `mdl_schema_context`

Assembled from L1 + L2 + L3 results. This is what all downstream stages consume.
Structured as a map from concept → grounded metric objects.

```python
state["mdl_schema_context"] = {

  "compliance_training_lms": {
    "grounded": True,
    "metrics": [
      {
        "metric_id":    "compliance_coverage_rate",
        "description":  "Proportion of learners who completed required curricula "
                        "with due date on or before audit deadline",
        "how":          "COUNT(completion_status=C) / COUNT(*) "
                        "WHERE required_flag=TRUE AND due_date <= audit_deadline",
        "tables":       ["csod.trans_completion_fact", "csod.curriculum_dim"],
        "join_path":    "trans_completion_fact.curriculum_id = curriculum_dim.curriculum_id",
        "segmentable":  True,
        "segment_col":  "csod.org_unit_dim.department_name",
        "segment_join": "trans_completion_fact.user_id = org_unit_dim.user_id",
        "causal_role":  "terminal",
        "causal_edge":  None,
      },
      {
        "metric_id":    "broken_curriculum_count",
        "description":  "Count of required curricula where has_completion_path=FALSE. "
                        "Structural gap — cannot be resolved by learner action.",
        "tables":       ["csod.curriculum_dim"],
        "causal_role":  "structural_diagnostic",
        "causal_edge":  "curriculum_gap → compliance_training_lms",
      },
    ],
  },

  "overdue_count": {
    "grounded": True,
    "metrics": [
      {
        "metric_id":    "overdue_assignment_count",
        "description":  "Count of required assignments where due_date < today "
                        "and completion_status ≠ C",
        "tables":       ["csod.trans_completion_fact", "csod.curriculum_dim"],
        "join_path":    "trans_completion_fact.curriculum_id = curriculum_dim.curriculum_id",
        "time_window":  "lag_windows['overdue_count']",   # bound at runtime from CCE
        "segmentable":  True,
        "segment_col":  "csod.org_unit_dim.department_name",
        "causal_role":  "root",
        "causal_edge":  "overdue_count → compliance_training_lms (lag 14d, conf 0.91)",
      },
    ],
  },

  "engagement_signal": {
    "grounded": True,
    "metrics": [
      {
        "metric_id":    "avg_login_frequency",
        "description":  "Average daily logins per learner over the causal lag window. "
                        "Declining trend is a leading indicator for completion drop.",
        "tables":       ["csod.user_activity", "csod.org_unit_dim"],
        "join_path":    "user_activity.user_id = org_unit_dim.user_id",
        "time_window":  "lag_windows['engagement_signal']",
        "segmentable":  True,
        "segment_col":  "csod.org_unit_dim.department_name",
        "trend_signal": True,
        "trend_direction": "negative_is_causal",
        "causal_role":  "root",
        "causal_edge":  "engagement_signal → compliance_training_lms (lag 21d, conf 0.71)",
      },
    ],
  },

  "manager_assignment_rate": {
    "grounded": True,
    "metrics": [
      {
        "metric_id":    "manager_assignment_rate",
        "description":  "Proportion of managers who assigned required curricula "
                        "to their direct reports within the causal lag window.",
        "tables":       ["csod.trans_completion_fact", "csod.org_unit_dim"],
        "join_path":    "trans_completion_fact.user_id = org_unit_dim.user_id "
                        "JOIN org_unit_dim manager ON org_unit_dim.manager_id = manager.user_id",
        "time_window":  "lag_windows['manager_assignment_rate']",
        "segmentable":  True,
        "segment_col":  "csod.org_unit_dim.department_name",
        "causal_role":  "root",
        "causal_edge":  "manager_assignment_rate → compliance_training_lms (lag 7d, conf 0.65)",
      },
    ],
  },

  "deadline_sla": {
    "grounded": True,
    "metrics": [
      {
        "metric_id":    "days_to_audit_deadline",
        "description":  "Days remaining until audit deadline (2026-03-31). "
                        "If < warning_days → urgency HIGH. Amplifies Shapley weights "
                        "on all root-to-terminal paths.",
        "tables":       ["csod.curriculum_dim"],
        "causal_role":  "mediator",
        "causal_edge":  "deadline_sla → compliance_training_lms (urgency amplifier)",
        "computed":     "(deadline - today)",
        "current_value": 11,
        "urgency_level": "high",
      },
    ],
  },

  "cohort_comparator": {
    "grounded": True,
    "segment_dim": {
      "column":      "csod.org_unit_dim.department_name",
      "join_anchor": "csod.trans_completion_fact.user_id = csod.org_unit_dim.user_id",
      "description": "Department-level segmentation for coverage gap comparison",
    },
  },

}
```

---

## What changes downstream because of this

### Stage 3 — Capability resolver

Instead of checking abstract capability flags, the resolver reads `mdl_schema_context`
and confirms each metric has a `grounded: True` entry with at least one resolved table.
Ungrounded concepts are excluded from the final concept set with reason
`"mdl_unresolvable"` rather than passing silently.

```python
# Before MDL retrieval — resolver was checking:
capability_flags = { "completion.rate": True, "deadline.dimension": True }

# After MDL retrieval — resolver checks:
grounded_metrics = {
  "compliance_training_lms": { "grounded": True, "metrics": [...] },
  "overdue_count":            { "grounded": True, "metrics": [...] },
  # ...
}
# Richer: knows exactly which tables, joins, and columns back each capability
```

### Stage 6 — Question generator

Before MDL retrieval, the question generator produced generic NL questions:

```
# Generic (no MDL context):
"What is the compliance training completion rate by department?"
```

After MDL retrieval, it produces semantically grounded NL questions — referencing
the actual metric definitions, value semantics, and causal framing:

```
# Grounded (MDL context available):
"What is the compliance coverage rate by department for required curricula
 with a due date on or before 2026-03-31 — specifically the proportion of
 learners who have reached completed status, excluding in-progress?"

"How many required assignments per department are overdue (past due date,
 not yet completed) in the 14-day window ending today — and how does that
 compare to the prior 14-day period?"

"What is the average daily login frequency per learner by department over
 the past 21 days? Flag any department showing a declining trend —
 this is a 21-day leading indicator for completion rate drop."

"Are there any required curricula assigned to learners in at-risk departments
 where the completion path is not configured? These assignments cannot close
 regardless of learner action."
```

The difference: the question generator knows that `completion_status = C` is
the completed state (not a boolean), that `required_flag = TRUE` is the compliance
scope filter, that `has_completion_path = FALSE` is a structural blocker distinct
from a learner-behavior cause, and that the 21-day window on engagement is causal
(from the edge metadata), not arbitrary.

### Metric recommendation order

Metric recommendations are produced by combining two inputs:

```
Causal edge weight (from concept graph)
        ×
MDL grounding confidence (from L3 retrieval score)
        =
Metric recommendation priority
```

Example for gap analysis:

| Metric | Causal edge conf | MDL grounding score | Recommendation priority |
|---|---|---|---|
| `compliance_coverage_rate` | — (terminal) | 0.97 | **Show first — the metric in question** |
| `overdue_assignment_count` | 0.91 | 0.95 | **Investigate first — strongest causal path** |
| `avg_login_frequency` | 0.71 | 0.88 | Investigate second |
| `manager_assignment_rate` | 0.65 | 0.82 | Investigate third |
| `broken_curriculum_count` | 0.58 | 0.91 | Surface as structural diagnostic |
| `days_to_audit_deadline` | mediator | 1.0 | Show as urgency context, not a cause |

This ordering is what the question generator uses to sequence the NL questions
and what the output assembler uses to order the metric view panels.

---

## State summary after Stage 2.5

```python
state["mdl_schema_context"]      # full grounding map — consumed by Stages 3, 6, agents
state["metric_recommendations"]  # ordered list of metric_ids with priority scores
state["mdl_retrieval_meta"] = {
  "l1_source":        "csod",
  "l1_status":        "active",
  "l2_tables_found":  4,
  "l3_columns_found": 9,
  "ungrounded":       [],          # empty = all concepts grounded
  "retrieval_time_ms": 84,
}
```

---

## Failure modes

| Failure | What happens |
|---|---|
| L1 source not active | All capabilities marked UNRESOLVABLE. Pipeline halts before question generation. User sees: "Your CSOD connection is inactive — reconnect to run this analysis." |
| L2 table not found for capability | Capability marked UNRESOLVABLE for that concept. Concept excluded from final set with reason logged. |
| L3 column ambiguous (multiple matches) | Top match used. Alternatives logged to `mdl_retrieval_meta.ambiguous_columns`. Insight agent receives both candidates with confidence scores. |
| MDL collection stale (last sync > 24h) | Warning added to `mdl_retrieval_meta`. Analysis proceeds but output includes: "Schema last updated 26 hours ago — column availability may have changed." |
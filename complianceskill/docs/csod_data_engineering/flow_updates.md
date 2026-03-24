Let me trace through the exact query that was used to diagnose the gap analysis routing problem, end to end, so you can see what changes and why.

---

## The Query

> *"Using Cornerstone data, I want to track my organization's skill compliance training gaps over the last 1 year"*

---

## Before Seeding (Current Behaviour)

### Turn 1 — Goal Intent
Lexy asks: *"What would you like to do?"*
User sees four radio options. Picks **"Analyze metrics & KPIs"**.

### Turn 2 — Concept Confirm
The LLM resolver runs against the registry doing **keyword matching**.
It sees "compliance training" → scores `compliance_training` at 0.90.
It sees "skill" and "gaps" but `workforce_capability` has no "compliance" vocabulary → scores 0.35.

User sees:
```
Lexy identified: Compliance Training
☑ Compliance Training  (0.90)
☐ Workforce Capability (0.35)
```
User confirms the pre-selected answer and moves on.

### Turn 3 — Scoping
Lexy asks time range, department, role. User answers "last 12 months, all departments".

### Turn 4 — Area Confirm
`compliance_training` only has three areas in the registry:
```
○ Overdue Risk         — who's behind on mandatory training
○ Audit Readiness      — evidence posture for SOC2/HIPAA
● Completion Trends    — training completion rates over time  ← best available match
```
"Skill gap analysis" doesn't appear at all. User is forced to pick `completion_trends` because it's the closest thing.

### Turn 5 — Metric Narration
Lexy describes what it will measure:
> *"I'll track completion rate, overdue count, and on-time completion trend over 12 months."*

These are completion metrics. There is no mention of skills, role alignment, or gap analysis because those came from a different concept's areas that were never entered.

### Main Execution
CCE runs but has no seeded graph data → builds a sparse graph with whatever it
can scrape from the metric registry. The output assembler produces a
**completion rate trend report** — not a gap analysis.

**The user asked for "gaps". They got a completion trend. The routing was wrong from Turn 2.**

---

## After Seeding (New Behaviour)

The four collections are now live. Here is the same query.

---

### Turn 1 — Goal Intent
*(Identical — no change here)*

---

### Turn 2 — Concept Confirm

The LLM resolver now runs with a **goal-oriented system prompt**. Instead of
counting keyword overlaps it reasons:

> *"Goal: measure the gap between required skills and actual compliance training
> completions. Capability needed: gap analysis + role-skill mapping. That
> capability lives in `workforce_capability / skill_gap_analysis`, not in
> `compliance_training` which only tracks completion rates and overdue queues.
> However `compliance_training / completion_trends` is useful enrichment for
> the compliance angle."*

It also hits the **`lms_use_case_groups` collection**:
Query embedding of `"skill compliance training gaps"` → top match is
`skill_gap_analysis` use case (the embedded text is *"skill_gap_analysis:
Requires role-skill mapping source of truth. Required metric groups:
skill_coverage, curriculum_evidence…"*). This confirms the routing.

User now sees:

```
Lexy identified: Workforce Capability
☑ Workforce Capability  (0.88) — competency mapping, skill gap identification
☐ Compliance Training   (0.72) — mandatory training completion & audit targets
```

The scores are reversed compared to before. `workforce_capability` wins
because its **analytical capability** (gap analysis) matches the goal, not
because it has matching keywords.

---

### Turn 3 — Scoping
*(Same questions, same answers)*

---

### Turn 4 — Area Confirm

With `workforce_capability` as the confirmed concept, the area matcher now
presents areas from that concept:

```
● Skill Gap Analysis        ← directly answers the question
  Metrics: role_skill_match_rate, skill_coverage_pct, curriculum_gap_pct
  KPIs: % roles fully covered, median skill gap per department

○ Curriculum Coverage       ← related but broader
  Metrics: curriculum_breadth, content_utilisation_rate

○ Succession Readiness      ← different goal
  Metrics: bench_strength_ratio, readiness_score
```

`Skill Gap Analysis` is the first option and is pre-selected. This is the area
that was completely unreachable before.

The **`lms_focus_area_taxonomy` collection** is also queried here. It returns
the `skill_development` entry, which carries:
- `causal_terminals: ["role_skill_match_rate"]` — the outcome metric to anchor CCE
- `csod_schemas: ["csod_competencies", "csod_curriculum", "csod_job_profiles", "workday_job_families"]`
  — the L3 schema whitelist that MDL retrieval will use

These are stored in state and passed forward.

---

### Turn 5 — Metric Narration

With `skill_gap_analysis` area confirmed, the narration is now grounded in the
right registry data:

```
Lexy will measure:

I'll analyze skill compliance training gaps by comparing your organization's
role-required competencies against actual training completion records over the
past 12 months — surfacing which roles and departments have the widest gaps
between what's required and what's been completed.

Key metrics:
  role_skill_match_rate     (outcome)    — % of role-required skills covered
  skill_coverage_pct        (driver)     — curriculum coverage of required skills
  curriculum_gap_pct        (guardrail)  — % of required skills with no assigned training
  compliance_assigned_count (driver)     — training assignments mapped to skill requirements

KPIs: % roles fully covered, median gap by department
```

This is the narration the user actually asked for. It mentions skills, gaps, roles, and curriculum — not just completion rates.

---

### CCE Stage (Main Graph — After `csod_spine_precheck`)

The causal graph node now has real seed data to work with.

**Node retrieval** from `lms_causal_nodes`:
Query: embed `"skill compliance training gaps"` + filter `domains = ["lms"]`,
`collider_warning = false`

Top nodes returned:
```
role_skill_match_rate    — terminal, is_outcome=true
skill_coverage_pct       — mediator
curriculum_gap_pct       — mediator
compliance_rate          — terminal, is_outcome=true
compliance_assigned_dist — root (exogenous input)
self_directed_ratio      — mediator
```

**Edge expansion** from `lms_causal_edges`:
Query: filter `source_node_id IN {retrieved_node_ids}` OR
`target_node_id IN {retrieved_node_ids}`, `confidence >= 0.65`

Edges retrieved (examples):
```
skill_coverage_pct ──(positive, lag=14d)──► role_skill_match_rate
compliance_assigned_dist ──(positive)──► skill_coverage_pct
self_directed_ratio ──(positive, lag=7d)──► skill_coverage_pct
compliance_rate ──(negative, lag=30d)──► training_cost_avg_per_learner
```

CCE assembles a **real directed acyclic graph**:

```
compliance_assigned_dist  ──►  skill_coverage_pct  ──►  role_skill_match_rate
                                      ▲
self_directed_ratio  ────────────────►┘
```

The causal graph now knows:
- The **terminal outcome** is `role_skill_match_rate`
- The key **driver** is `skill_coverage_pct` (curriculum must cover required skills)
- `compliance_assigned_dist` is a root cause (how many learners are assigned mandatory skill training)

---

### Turn 6 — Cross-Concept Check (New Checkpoint)

`csod_cross_concept_check_node` runs.

It inspects `csod_area_matches` for areas from concepts other than
`workforce_capability`. It finds `compliance_training / completion_trends`
scored at 0.72.

It also checks the CCE graph: `compliance_rate` is a terminal node in the
assembled graph. Its node payload says `focus_areas: ["training_compliance"]`.
This amplifies the `compliance_training` concept score by +0.15 → 0.87.

The checkpoint triggers because 0.87 ≥ 0.40 threshold.

User sees:

```
The causal analysis found connections spanning multiple analytical domains.
Your primary focus is Skill Gap Analysis.

The following related areas could enrich your analysis:

☐  Completion Trends  (87% match)
   compliance_training
   The causal graph links skill coverage to compliance completion rates.
   Including this adds: completion_rate, overdue_count, on_time_pct
   Causal path: skill_coverage_pct → compliance_rate

[Add Selected & Continue]   [Skip]
```

The user sees **why** the second area is being suggested — not just a list, but
the causal path that connects them. They choose to add it.

`csod_additional_area_ids = ["completion_trends"]` is stored in state.

---

### Metrics Retrieval Stage

The metrics retrieval node now has two areas to pull from:
- Primary: `skill_gap_analysis` → metrics from the skill/curriculum domain
- Additional: `completion_trends` → compliance completion rate metrics

The scorer receives a combined metric set that spans both. The scoring weights
come from the `lms_use_case_groups` collection (`skill_gap_analysis` entry):
`alpha: null, beta: null, gamma: null` — no override, so standard weights apply.

---

### MDL Schema Retrieval

The L3 schema whitelist from the `lms_focus_area_taxonomy` payload is used:
```
csod_competencies
csod_curriculum
csod_job_profiles
workday_job_families        ← from skill_gap_analysis
csod_compliance_status      ← added because completion_trends was included
csod_completion_log
```

Without the taxonomy seed, MDL retrieval would have to scan all available
tables. With it, only the 6 relevant schemas are queried — faster and less
noise in the SQL planner.

---

### Final Output

The assembler produces a report that combines:

1. **Skill gap breakdown** — which roles have the widest gap between required skills and completed training, segmented by department
2. **Curriculum coverage** — which skill requirements have no assigned training at all (the `curriculum_gap_pct` metric the user couldn't reach before)
3. **Compliance completion trend overlay** — how the gap has been moving over 12 months (the completion rate from the added area), including a causal explanation: *"Departments with lower curriculum coverage show declining compliance rates with a ~14-day lag"*

---

## Side-by-Side Summary

| Stage | Before seeding | After seeding |
|---|---|---|
| Concept confirm | `compliance_training` (keyword match) | `workforce_capability` (capability match) |
| Area shown | Overdue Risk, Audit Readiness, Completion Trends | **Skill Gap Analysis**, Curriculum Coverage, Succession Readiness |
| Metric narration | Completion rate, overdue count | Role-skill match rate, curriculum gap, skill coverage |
| CCE graph | Sparse / generic | 47 nodes, 58 edges — typed DAG with confidence and lag |
| Cross-concept checkpoint | Not triggered | Surfaces `completion_trends` with causal path explanation |
| MDL schema scope | All tables | 6 targeted schemas only |
| Final answer | Completion rate trend | **Gap analysis + compliance overlay with causal explanation** |

The seed data doesn't add new UI screens — it changes what appears *inside* the existing checkpoints, grounds the narration in real causal structure, and enables the cross-concept check to give an explainable suggestion rather than a blind list.
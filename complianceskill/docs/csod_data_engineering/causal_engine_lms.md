# Causal Expert System — Conversation Examples
## How Questions, Rejections, and Interventions Update the Knowledge Base

> **Reading guide:** Each scenario shows a real conversation between a user and the system, the causal graph assembled in real time from retrieved edges, the outcome or feedback signal generated, and what changes in the knowledge base as a result. Four signal types are covered: analyst explanation rejection, intervention outcome tracking, graph incoherence detection, and curator hypothesis review.

---

## Scenario 1 — Analyst Rejection Signal
### Domain: Compliance Training · Cornerstone · L&D Analyst

---

**Context:** A compliance officer at a 4,000-person financial services firm is investigating a drop in compliance training completion. The system retrieves edges from the knowledge base and assembles a local causal graph.

---

**Conversation**

---

**User**
> Our compliance training completion rate dropped from 84% to 71% over the last quarter. What's driving it?

---

**System**
I've assembled a causal graph from your Cornerstone data and the knowledge base. Here's what the evidence points to.

The primary driver is **assignment queue overload.** Your `compliance_assigned_distribution` increased 34% this quarter — new regulatory requirements added 3 mandatory courses to the standard compliance curriculum. This is flowing through `overdue_count`, which is up 41%, and that pressure is suppressing `completion_rate`.

A secondary driver is **engagement decay.** `login_count_weekly_trend` has declined 18% — this is reducing `session_to_user_ratio`, which independently also suppresses completion rate.

**Important:** `completion_rate` is a collider in this graph — it is caused independently by both assignment pressure and engagement decay. Filtering your reports by completion rate will produce misleading cross-team comparisons. Teams with higher assignment loads will appear less engaged even if their actual engagement is identical.

**Recommended intervention:** Stagger the assignment window for the 3 new courses across 8 weeks rather than assigning all simultaneously. This addresses the root cause. Sending reminder emails addresses neither root — it adds notification load to people already overwhelmed.

*Graph assembled from 6 edges · 4 nodes · corpus confidence: 0.74 avg*

---

**User**
> This doesn't feel right for our org. We went through a system migration 6 weeks ago and our completion rate was fine during the migration window. Login count dropped because of the migration, not disengagement. The assignment load explanation makes sense but the engagement decay path feels wrong here.

---

**System**
That's a useful correction. You're saying the `login_count` decline is explained by the migration event rather than genuine disengagement — meaning the edge `login_count_weekly_trend → session_to_user_ratio` is present but its downstream effect on completion rate didn't materialize because the mechanism (voluntary disengagement) isn't active.

Let me rebuild the graph excluding that path.

With engagement decay removed, the graph simplifies to a single root: `compliance_assigned_distribution → overdue_count → completion_rate`. The Shapley attribution shifts — assignment queue overload now accounts for an estimated 89% of the completion rate drop rather than 61%.

The intervention recommendation sharpens: stagger the assignment window. The reminder email recommendation is even less appropriate — there is no engagement problem to address.

*Feedback signal recorded: edge `login_count_weekly_trend → completion_rate` path suppressed for migration-context queries · routed to curator queue*

---

**Knowledge Base Update**

```
SIGNAL TYPE: Analyst rejection — path suppression
TRIGGER: User identified confounding event (system migration) masking true mechanism

HYPOTHESIS GENERATED FOR CURATOR:
  Edge chain: login_count_weekly_trend → session_to_user_ratio → completion_rate
  Observation: Analyst at Org [FS-014] identified this path as inactive
               during platform migration events (weeks 1–8 post-migration)
  Pattern: 2 prior orgs (FS-007, FS-011) showed same suppression during
           similar migration windows — completion rate held despite login drop
  
  Hypothesis: This edge chain requires a context condition:
    ACTIVE when: login_drop is gradual, no system event in prior 8 weeks
    INACTIVE when: login_drop correlates with migration, cutover, or
                   major platform change event in same window

  Proposed edge modification:
    BEFORE:
      login_count_weekly_trend → session_to_user_ratio
      confidence: 0.74 | corpus_match: confirmed | condition: none

    AFTER (proposed):
      login_count_weekly_trend → session_to_user_ratio
      confidence: 0.74 | corpus_match: confirmed
      condition: platform_event_flag = false
      
      NEW CONDITIONAL EDGE:
      login_count_weekly_trend → session_to_user_ratio [SUPPRESSED]
      condition: platform_event_flag = true (migration, cutover, major release)
      confidence: 0.61 | corpus_match: analogous | status: proposed

CURATOR ACTION REQUIRED:
  [ ] Approve conditional edge addition
  [ ] Reject — different explanation
  [ ] Escalate — needs more org observations before promoting
  
QUEUE PRIORITY: Medium (2 prior corroborating orgs)
CURATOR ASSIGNED: —
```

---

## Scenario 2 — Intervention Outcome Signal
### Domain: ILT Cost Efficiency · Cornerstone · L&D Director

---

**Context:** An L&D director acted on a system recommendation 90 days ago. The system is now measuring whether the intervention moved the terminal metric.

---

**Conversation**

---

**User**
> Three months ago you told me to fix the ILT approval backlog to reduce cost per learner. We cleared the backlog — reduced `ilt_for_approval_count` from 47 sessions to 6. Did it work?

---

**System**
Let me pull your current metrics and compare against the pre-intervention baseline.

**What moved:**

| Metric | Before | After | Direction |
|---|---|---|---|
| `ilt_for_approval_count` | 47 sessions | 6 sessions | ✅ Intervention applied |
| `ilt_avg_capacity` | 61% | 74% | ✅ Improved +13pts |
| `no_show_rate` | 19% | 17% | → Marginal improvement |
| `completion_count_total` | 340/qtr | 389/qtr | ✅ Improved +49 completions |
| `training_cost_avg_per_learner` | £312 | £271 | ✅ Improved -£41 |

**What didn't move as predicted:**

`no_show_rate` improved only marginally — from 19% to 17% rather than the predicted 12%. The graph predicted that clearing the approval backlog would reduce waiting list pressure, which would reduce the cancel-and-rebook behavior that drives no-shows. That chain partially worked but not to the predicted degree.

`training_cost_avg_per_learner` improved by £41 against a predicted improvement of £58. The gap is explained by the no-show rate not falling as far as predicted.

**Assessment:** The intervention worked on the primary path — `ilt_for_approval_count → ilt_avg_capacity → completion_count_total` — and delivered meaningful cost efficiency. The secondary path through `ilt_waiting_list_count → no_show_rate` underperformed. Something is sustaining no-show behavior independently of the waiting list.

*Outcome signal recorded · edge confidence adjustments routed to curator queue*

---

**User**
> Why is the no-show rate still high if the waiting list pressure is gone?

---

**System**
Good question. With waiting list pressure removed as the primary driver, the graph suggests two remaining candidates.

The first is **calendar conflict density.** Your `ilt_session_scheduling_spread` — how many sessions are clustered in the same 2-week windows — is still high. Learners book ILT sessions and then get pulled into competing priorities when too many sessions cluster. This would produce no-shows that aren't related to waiting list behavior at all.

The second is **manager release rate.** In some orgs `manager_approval_for_ilt_attendance` is a required step, and when managers are under delivery pressure they informally block attendance even for registered learners. This doesn't show up in LMS data directly but it appears as unexplained no-shows.

I don't have confirmed edges for either of these in your data model yet. Do either of these match what you're observing on the ground?

---

**User**
> The calendar clustering one is exactly it. We have a compliance deadline in March and everyone tries to complete ILT in February. It's not a waiting list problem, it's a scheduling problem.

---

**System**
That identifies a new root node — `ilt_session_calendar_concentration` — driving `no_show_rate` independently of waiting list dynamics. This is not currently in the knowledge base as a confirmed edge.

*New edge hypothesis generated · routed to curator queue with high priority*

---

**Knowledge Base Update**

```
SIGNAL TYPE: Intervention outcome + analyst identification of missing root

─────────────────────────────────────────────────────────────────
OUTCOME SIGNAL — Edge confidence adjustment

  Edge: ilt_for_approval_count → ilt_avg_capacity
  Predicted effect: +13-16pts capacity improvement
  Observed effect: +13pts
  Verdict: Within prediction range
  
  Confidence adjustment:
    BEFORE: 0.68 | corpus_match: analogous
    AFTER:  0.73 | corpus_match: analogous → promoted to confirmed
    Basis: Intervention outcome confirmed at Org [LD-022]
           3 prior orgs (LD-007, LD-015, LD-019) showed same direction
           Promoting to confirmed at 4-org threshold

  Edge: ilt_waiting_list_count → no_show_rate
  Predicted effect: -7pts no-show reduction
  Observed effect: -2pts
  Verdict: Underperformed — partial mechanism only
  
  Confidence adjustment:
    BEFORE: 0.74 | corpus_match: confirmed
    AFTER:  0.69 | corpus_match: confirmed → demoted to analogous
    Note: Edge likely conditional on absence of calendar concentration
          Do not demote further until conditional is modeled

─────────────────────────────────────────────────────────────────
NEW EDGE HYPOTHESIS — Analyst-identified missing root

  Proposed new node:
    node_id: ilt_session_calendar_concentration
    name: ILT Session Calendar Concentration
    type: ROOT
    observable: true
    grain: monthly
    description: Proportion of ILT sessions scheduled within a
                 compressed window (e.g. >40% of sessions in a
                 rolling 3-week period)
    vertical: L&D · Cornerstone · ILT
    status: proposed

  Proposed new edge:
    source: ilt_session_calendar_concentration
    target: no_show_rate
    direction: positive
    lag: 0d
    confidence: 0.58 | corpus_match: novel
    mechanism: Learners register for ILT during high-concentration
               windows, then cannot attend due to competing priorities
               when too many organizational deadlines cluster in the
               same period. No-shows increase without waiting list
               dynamics present.
    observed_at: [LD-022]
    status: proposed — 1 org observation, requires 2 more to promote

CURATOR ACTION REQUIRED:
  [ ] Approve new node + edge as novel (0.58)
  [ ] Reject — different mechanism
  [ ] Request: find analogous pattern in other compliance-deadline
               driven orgs before adding to base knowledge

QUEUE PRIORITY: High — explains systematic prediction gap across
                multiple ILT cost efficiency analyses
CURATOR ASSIGNED: —
```

---

## Scenario 3 — Graph Incoherence Detection
### Domain: Certification Compliance · Workday Learning · Automated Signal

---

**Context:** No user interaction. The system detects structural incoherence in a local graph assembled for a certification compliance query at a healthcare org.

---

**Automated Detection Log**

```
QUERY: "Why are our nursing certification renewal rates declining?"
ORG: Healthcare [HC-031] · Workday Learning
TIMESTAMP: [auto]

LOCAL GRAPH ASSEMBLED:
  Nodes retrieved: 4
    cert_expiry_count (terminal) ✅
    cert_renewal_rate (terminal) ✅  
    ilt_waiting_list_count (mediator) ✅
    ilt_instructor_count (root) ✅

  Edges retrieved: 3
    ilt_instructor_count → ilt_waiting_list_count (–0.71, 14d)
    ilt_waiting_list_count → cert_renewal_rate (–0.68, 21d)
    ilt_instructor_count → cert_expiry_count (+0.52, 30d)

INCOHERENCE FLAGS:

  FLAG 1 — Orphaned terminal path
    cert_expiry_count has no path from any root except a weak
    indirect edge (0.52). The Shapley attribution assigns 71%
    of cert_expiry variance to ilt_instructor_count — implausibly
    high for a single weak path.
    
    Hypothesis: Missing intermediate node between
    ilt_instructor_count and cert_expiry_count.
    Candidate: cert_renewal_scheduling_lead_time or
               ilt_seat_availability_per_cert_type

  FLAG 2 — Missing confounder
    cert_renewal_rate and ilt_waiting_list_count are correlated
    in this org's data at r=0.71. But the retrieved graph has no
    node that independently drives both. In the base knowledge
    base, ilt_waiting_list_count is a confounder in the ILT
    cost graph — but its confounder role in certification
    compliance has not been modeled.
    
    Hypothesis: ilt_instructor_count may be the unmodeled
    confounder driving both waiting list pressure AND
    cert expiry rate independently — two separate paths,
    not one chain.

  FLAG 3 — Node type inconsistency
    cert_renewal_rate is typed as terminal in this graph.
    In 3 prior healthcare org graphs, cert_renewal_rate
    was typed as mediator (→ compliance_rate terminal).
    
    Hypothesis: compliance_rate (the true terminal) was not
    retrieved for this query. Retrieval gap, not knowledge gap.

GRAPH COHERENCE SCORE: 0.41 (threshold for curator escalation: 0.60)
ACTION: Escalated to curator queue — do not surface this
        explanation to user until reviewed
```

---

**Curator Review Interface**

```
CURATOR QUEUE ITEM #247
TYPE: Graph incoherence — automated detection
ORG CONTEXT: Healthcare [HC-031] · Workday Learning
COHERENCE SCORE: 0.41
PRIORITY: High

FLAGS SUMMARY:
  1. Orphaned terminal — missing intermediate node
  2. Unmodeled confounder candidate
  3. Node type inconsistency (likely retrieval gap)

CURATOR ACTIONS:

  For Flag 3 (retrieval gap):
  [X] APPROVED — Add compliance_rate as required retrieval
      anchor for all certification compliance queries.
      If cert_renewal_rate is retrieved, compliance_rate
      must also be retrieved as its downstream terminal.
      
      RETRIEVAL RULE ADDED:
        when node_type=mediator AND node_id contains "renewal_rate":
          always retrieve downstream terminal in same domain

  For Flag 2 (unmodeled confounder):
  [X] APPROVED — Promote ilt_instructor_count to confounder
      role in certification compliance subgraph.
      
      NEW EDGE ADDED:
        source: ilt_instructor_count
        target: cert_expiry_count
        direction: positive
        lag: 21d
        confidence: 0.63 | corpus_match: analogous
        mechanism: Instructor headcount reduction creates
                   two independent effects: (1) longer waiting
                   lists → delayed renewal → cert expiry, and
                   (2) direct reduction in available renewal
                   session capacity → cert expiry regardless
                   of waiting list dynamics
        node_role_update: ilt_instructor_count promoted to
                          CONFOUNDER in cert_compliance subgraph
                          (remains ROOT in ILT cost subgraph)

  For Flag 1 (missing intermediate node):
  [ ] PENDING — Need to check whether cert_renewal_scheduling_
      lead_time exists in Workday Learning data model at HC-031
      before adding. Assigned to services team for data model
      review at next customer touchpoint.
      
      PLACEHOLDER EDGE (not yet active):
        source: ilt_instructor_count  
        target: cert_renewal_scheduling_lead_time [PROPOSED NODE]
        target: cert_expiry_count
        status: blocked pending data model confirmation

CURATOR NOTES:
  "The healthcare vertical consistently shows certification
   compliance as a capacity problem, not an engagement problem.
   We should consider a healthcare-specific subgraph variant
   where ilt_instructor_count is always retrieved as a root
   when cert_renewal_rate or cert_expiry_count are in scope.
   Flagging for vertical-specific retrieval rule discussion."

KNOWLEDGE BASE DIFF AFTER CURATOR REVIEW:
  Nodes modified: 1 (ilt_instructor_count role updated)
  Edges added: 1 (confirmed), 1 (placeholder/blocked)
  Retrieval rules added: 1
  Coherence score (projected): 0.71 (above threshold)
```

---

## Scenario 4 — Cross-Domain Bridge Edge Discovery
### Domain: Compliance Training + ServiceNow ITSM · Multi-System

---

**Context:** A CISO at a technology company is asking about security incident rates. The question touches both Cornerstone (compliance training) and ServiceNow (incident management). A bridge edge between the two subgraphs is discovered.

---

**Conversation**

---

**User**
> We've had a 40% increase in P1 security incidents over the last two quarters. Our board is asking whether our security awareness training program is effective. Is there a connection?

---

**System**
This question spans two domains — your Cornerstone security awareness training data and your ServiceNow incident data. I'm assembling a cross-domain graph. Note that bridge edges between these systems have lower confidence than within-domain edges — I'll flag epistemic status clearly.

**What the within-domain graphs show:**

On the Cornerstone side, your `security_awareness_completion_rate` is at 67% — below the 80% threshold that appears in the base knowledge as the point where non-completion begins correlating meaningfully with behavioral risk. `phishing_simulation_pass_rate` has declined from 78% to 61% over the same period. This is the most direct behavioral proxy for whether training is actually transferring.

On the ServiceNow side, your `p1_incident_count` increase of 40% is concentrated in two categories: credential compromise (18 incidents) and phishing-origin intrusions (14 incidents). The remaining 8 incidents are unrelated to security awareness behavior.

**The bridge edge — flagged as novel:**

There is a proposed edge in the knowledge base between `phishing_simulation_pass_rate` and `phishing_origin_incident_rate`. This edge is currently classified as `novel` at 0.58 confidence — it has been observed at 2 other technology-sector orgs but has not been promoted to `analogous` yet. I'm surfacing it because the pattern fits your data, but you should treat this connection as a hypothesis rather than a confirmed mechanism.

If the bridge edge holds: approximately 60–70% of your P1 incident increase may be attributable to training effectiveness decay, specifically the phishing simulation pass rate decline. The remaining 30–40% likely has non-training causes — patch management, access control, or external threat landscape changes.

**What I cannot tell you with current confidence:**

Whether the training effectiveness decay is a *cause* of the incident increase or whether both are caused by a common upstream factor — for example, a period of organizational disruption (rapid hiring, restructuring) that simultaneously reduced training engagement AND increased attack surface. I don't have a node for organizational disruption context in this graph.

*Cross-domain graph assembled · bridge edge confidence: 0.58 (novel) · recommend curator review before acting on bridge edge*

---

**User**
> The phishing simulation connection feels right. We also went through a major acquisition 18 months ago and onboarded 800 new employees who came through a lighter security training track. Could that be the missing piece?

---

**System**
Yes — that's a strong candidate for the missing upstream node. What you're describing is `new_hire_cohort_security_training_depth` as a root that independently drives both `phishing_simulation_pass_rate` decay (through the lighter training track) and potentially `p1_incident_count` directly (through a less security-aware cohort entering the environment).

This would make `phishing_simulation_pass_rate` a mediator rather than a root — the acquisition cohort effect flows through training performance and also directly into incident risk.

This is not currently in the knowledge base. You're proposing a structural addition.

*New node + 2 edges proposed · routed to curator queue as high priority — acquisition-driven security training gap pattern has cross-domain implications across HR, LMS, and ITSM verticals*

---

**Knowledge Base Update**

```
SIGNAL TYPE: Cross-domain bridge edge + analyst-identified missing root

─────────────────────────────────────────────────────────────────
BRIDGE EDGE CONFIDENCE UPDATE

  Edge: phishing_simulation_pass_rate → phishing_origin_incident_rate
  Prior observations: 2 technology orgs
  New observation: HC-031 (3rd org, same direction, similar magnitude)
  
  Confidence adjustment:
    BEFORE: 0.58 | corpus_match: novel | observations: 2
    AFTER:  0.64 | corpus_match: novel → analogous | observations: 3
    Note: 3-org threshold reached — promoting to analogous.
          Requires 2 more orgs or curator endorsement for confirmed.

─────────────────────────────────────────────────────────────────
NEW CROSS-DOMAIN NODE PROPOSED

  node_id: new_hire_cohort_security_training_depth
  name: New Hire Cohort Security Training Depth
  type: ROOT
  observable: true (derivable from Cornerstone onboarding curriculum data)
  grain: cohort (quarterly)
  description: Depth and completeness of security awareness curriculum
               delivered to new hire cohorts. Distinguishes standard
               track from accelerated/lighter onboarding tracks.
               Exogenous — set by HR policy at time of onboarding.
  vertical: L&D · HR · Security · Cross-domain
  status: proposed

  Proposed edges from new node:

    Edge A:
      source: new_hire_cohort_security_training_depth
      target: phishing_simulation_pass_rate
      direction: positive
      lag: 90d (cohort effect takes 1-2 quarters to appear in aggregate)
      confidence: 0.61 | corpus_match: analogous
      mechanism: Lighter onboarding training tracks produce cohorts
                 with lower phishing recognition capability; this
                 surfaces in simulation pass rates as the cohort
                 becomes a larger proportion of the total employee base
      status: proposed

    Edge B:
      source: new_hire_cohort_security_training_depth
      target: phishing_origin_incident_rate
      direction: negative
      lag: 120d
      confidence: 0.55 | corpus_match: novel
      mechanism: Direct path from cohort training depth to incident
                 rate, independent of simulation pass rate — cohort
                 behavioral risk exists even before simulation data
                 captures it
      status: proposed — weaker, requires more org evidence

─────────────────────────────────────────────────────────────────
CURATOR NOTES GENERATED

  "This is the first cross-domain node that bridges HR onboarding
   policy (Workday HCM), LMS training curriculum (Cornerstone),
   and ITSM incident data (ServiceNow). If confirmed, it creates
   a causal chain that no single system's reporting can surface:
   
   HR acquisition decision
     → onboarding curriculum depth (HR/LMS policy)
       → phishing simulation performance (LMS)
         → security incident rate (ITSM)
   
   This chain would be invisible to the CISO looking only at
   ServiceNow, and invisible to the CHRO looking only at
   onboarding completion rates. It only emerges cross-domain.
   
   Recommend: prioritize for vertical knowledge expansion.
   Assign to security + L&D domain expert pair for review.
   High strategic value — relevant to every org that has
   gone through acquisition or rapid headcount growth."

CURATOR ACTION REQUIRED:
  [ ] Approve new node + Edge A (analogous confidence)
  [ ] Approve Edge B (novel — weaker evidence)
  [ ] Request additional org observations before promoting
  [ ] Commission domain expert review: security + L&D pair

QUEUE PRIORITY: High — cross-domain strategic value
                First bridge between HR, LMS, and ITSM verticals
CURATOR ASSIGNED: —
```

---

## Summary — How the Knowledge Base Evolves

| Scenario | Signal type | What changed | Before | After |
|---|---|---|---|---|
| 1 — Login drop during migration | Analyst rejection | Conditional added to login → engagement edge | Unconditional edge (0.74, confirmed) | Context-conditional edge with platform_event suppression |
| 2 — ILT cost intervention outcome | Intervention outcome + analyst identification | Approval backlog edge promoted; waiting list → no-show demoted; new calendar concentration root proposed | 2 edges at analogous confidence | 1 promoted to confirmed, 1 demoted, 1 new edge at novel |
| 3 — Certification coherence failure | Graph incoherence (automated) | Instructor count promoted to confounder; retrieval rule added; placeholder edge for missing node | Incoherent graph (0.41) | Coherent graph (0.71); 1 retrieval rule added |
| 4 — Acquisition security gap | Cross-domain analyst identification | Bridge edge promoted from novel to analogous; new cross-domain root node proposed | Bridge edge at novel (0.58, 2 orgs) | Bridge edge at analogous (0.64, 3 orgs); new node proposed |

---

## The Learning Loop in One View

```
User question
     │
     ▼
Local graph assembled from retrieved edges + nodes
     │
     ├── Coherence score < 0.60 ──► Incoherence flags generated
     │                               ├── Retrieval gap → retrieval rule update
     │                               ├── Missing parent → new edge hypothesis
     │                               └── Node type conflict → curator review
     │
     ├── User accepts explanation ──► No signal (baseline)
     │
     ├── User rejects explanation ──► Path suppression hypothesis
     │                                └── Conditional edge proposed
     │
     ├── User identifies missing node ──► New node + edges proposed at novel
     │
     └── Intervention outcome measured ──► Confidence adjustment
                                           ├── Predicted → promote confidence
                                           ├── Underperformed → demote confidence
                                           └── Wrong direction → edge review

All signals ──► Curator hypothesis queue (prioritized)
                     │
                     ├── Approve → knowledge base updated
                     ├── Reject → signal discarded, pattern noted
                     └── Escalate → domain expert review, more orgs needed

Knowledge base state:
  Edges: novel (0.55-0.60) → analogous (0.61-0.79) → confirmed (0.80+)
  Nodes: proposed → active → deprecated
  Retrieval rules: added as structural patterns emerge
```

---

*These examples demonstrate the 70% → 95% accuracy trajectory. Cold start (first query) assembles from base curated knowledge. Each signal — rejection, outcome, incoherence, new observation — incrementally refines the graph. No single interaction is expected to be perfect. The system is honest about confidence levels and surfaces uncertainty rather than hiding it.*

Here’s a **clean, practical way to build a hierarchy** that starts from a framework like **SOC 2** and flows all the way down to **issues**, in a way that works for **governance, automation, and tooling** (not just docs).

I’ll give you:

1. The **canonical hierarchy**
2. A **concrete SOC 2 example**
3. How this maps to **real systems + agentic automation**
4. Common mistakes to avoid

---

## 1️⃣ Canonical Hierarchy (Framework → Issue)

Think of this as a **many-to-many, graph-first hierarchy**, not a simple tree.

```
Framework
  ↓
Trust Service Criteria (TSC)
  ↓
Control Objective
  ↓
Control
  ↓
Policy / Standard
  ↓
Procedure
  ↓
Evidence
  ↓
Finding / Issue
```

Each level answers a **different question**:

| Level             | Answers                                    |
| ----------------- | ------------------------------------------ |
| Framework         | What compliance regime are we following?   |
| TSC               | What trust outcome must be achieved?       |
| Control Objective | What must be true to satisfy the criteria? |
| Control           | How do we ensure that outcome?             |
| Policy            | What is the company rule?                  |
| Procedure         | How is the rule executed?                  |
| Evidence          | What proves it happened?                   |
| Issue             | Where did it fail or drift?                |

---

### Policy controls and risk (aligned with `extractions.json`)

**Controls** in this hierarchy are defined and detected using:

| Source in `extractions.json` | Purpose |
| ---------------------------- | ------- |
| **Control level** | Doc type `control`; section label when heading contains *control*, *control objective*, *control statement* |
| **Control verbs** | `patterns.keywords.control_verbs`: implement, ensure, enforce, restrict, review, monitor, detect, alert, log, audit, approve, rotate, encrypt, backup, patch, scan, validate |
| **Control extractor** | `extractors.control_extractor`: `control_heading_cues` (control, control objective, control statement); content with these cues or control verbs is treated as control-related |

So in the hierarchy, **Control** = “How do we ensure that outcome?” and is recognized by control objectives/statements and by those verbs in policy/standard text.

**Risk** is represented in two ways in the same hierarchy:

1. **Exception / risk-acceptance path** (from `extractions.json`):
   - **Doc type** `exception` when headings contain: *exception*, *risk acceptance*, *waiver*
   - **Headings** `patterns.headings.exception_markers`: exception, waiver, risk acceptance, compensating control, deviation
   - These sit alongside the main chain (e.g. policy → exception, or control → compensating control) and represent accepted or mitigated risk.

2. **Finding / Issue** (already in the hierarchy):
   - Risk is *created* at **Issue** (and optionally **Evidence** gaps), not at the policy level — e.g. “Quarterly access review not completed” is an issue that implies control/risk.

Extended view with controls and risk made explicit:

```
Framework
  ↓
Trust Service Criteria (TSC)
  ↓
Control Objective
  ↓
Control          ← control_verbs, control objective/statement (extractions.json)
  ↓
Policy / Standard
  ↓
Procedure
  ↓
Evidence
  ↓
Finding / Issue  ← risk created here (operational drift)
  +
Exception / Waiver / Risk acceptance / Compensating control  ← risk path (extractions.json exception_markers)
```

So: **controls** are the “how we ensure” layer (identified via control objectives/statements and control_verbs); **risk** appears both as the **exception/waiver/risk-acceptance** path and as **findings/issues** at the bottom of the hierarchy.

---

## 2️⃣ Concrete SOC 2 Example

### **Framework**

**SOC 2**

---

### **Trust Service Criteria**

**CC6 – Logical and Physical Access Controls**

---

### **Control Objective**

> Ensure that access to systems and data is restricted to authorized users.

---

### **Control**

**CC6.1 – Logical Access Control**

* User access is approved
* Access is role-based
* Access is reviewed periodically

---

### **Policy**

**Access Control Policy**

* Defines least privilege
* Defines approval requirements
* Defines review cadence

---

### **Procedure**

**User Access Provisioning Procedure**

1. Manager submits access request
2. Security reviews request
3. Access granted via IAM
4. Quarterly access review performed

---

### **Evidence**

* IAM role assignments
* Access request tickets
* Quarterly access review reports
* Audit logs

---

### **Finding / Issue**

> Quarterly access review not completed for Engineering group in Q2

This is where **risk is created**, not at the policy level.

---

## 3️⃣ Turning This into a Working Data Model (Important)

If you want this to scale (and support Agentic AI), **don’t model this as documents** — model it as **entities with relationships**.

### **Core Entities**

```text
framework
trust_service_criteria
control_objective
control          ← (control_verbs, control objective/statement per extractions.json)
policy
procedure
evidence
issue
exception       ← (waiver, risk acceptance, compensating control per extractions.json)
```

### **Key Relationships**

```text
framework ── has_many ──> TSC
TSC ── has_many ──> control_objective
control_objective ── has_many ──> control
control ── implemented_by ──> policy
policy ── executed_by ──> procedure
procedure ── produces ──> evidence
evidence ── supports ──> control
issue ── violates ──> control / procedure
exception ── mitigates_or_accepts ──> control / policy
```

This lets you answer:

* *“Which SOC 2 criteria are currently at risk?”*
* *“Which issues impact CC6?”*
* *“Which policies generate weak evidence?”*

---

## 4️⃣ Where Issues Actually Come From (Key Insight)

Issues **do not originate from frameworks**.
They originate from **operational drift**.

Typical issue sources:

* Missing evidence
* Late execution (e.g., review not done)
* Evidence quality degradation
* Control no longer matches reality
* Tool integration failure

That’s why **issues should attach to controls/procedures**, not frameworks.

---

## 5️⃣ How This Enables Automation & Agentic AI

Once this hierarchy exists:

### 🔹 Discovery Agents

* Map frameworks → controls
* Detect missing mappings

### 🔹 Evidence Agents

* Pull logs, tickets, IAM data
* Validate freshness & completeness

### 🔹 Risk Agents

* Convert issues into likelihood × impact
* Score control effectiveness decay

### 🔹 Compliance Agents

* Generate SOC 2 readiness views
* Explain *why* a control is failing

Frameworks become **metadata**, not work.

---

## 6️⃣ Common Mistakes to Avoid

❌ Treating policies as controls
❌ Treating evidence as static files
❌ Attaching issues directly to SOC 2
❌ One-policy-per-control thinking
❌ No temporal dimension (controls change over time)

---

## 7️⃣ TL;DR Hierarchy (Pasteable)

```
SOC 2
 → Trust Service Criteria
   → Control Objectives
     → Controls
       → Policies
         → Procedures
           → Evidence
             → Issues (Failures / Drift)
```

If you want, next I can:

* Design this as a **Postgres schema**
* Convert it into a **Neo4j / knowledge graph**
* Show how to calculate **control effectiveness & risk**
* Map this to **ServiceNow / Vanta / Drata-style models**

Just tell me the direction.


The short answer is:
**user actions are the atomic signals that drive procedures → evidence → control effectiveness → issues**.

Below is a **clear mental model + concrete mapping** you can actually implement.

---

## 1️⃣ Where user actions fit in the hierarchy

Extend the hierarchy you already have by inserting **User Actions** at the bottom, *before evidence*:

```
Framework
 → Trust Service Criteria
   → Control Objective
     → Control
       → Policy
         → Procedure
           → User Action   ← (what people/systems actually do)
             → Evidence
               → Issue
```

**Key insight:**
Controls don’t fail because policies are bad.
They fail because **user actions drift**.

---

## 2️⃣ What is a “User Action”?

A **user action** is a **time-bound, attributable event** performed by:

* a human (employee, admin, contractor)
* or a system acting on their behalf

Examples:

* Approving access
* Creating a ticket
* Running a review
* Acknowledging an alert
* Deploying a change
* Disabling MFA
* Ignoring a task

Think of user actions as **verbs**, not documents.

---

## 3️⃣ Concrete SOC 2 example (end-to-end)

### Control

**CC6.1 – Logical Access Controls**

> Access is approved, role-based, and periodically reviewed.

---

### Procedure

**Quarterly User Access Review**

---

### Required User Actions

| Action                   | Actor    | System    |
| ------------------------ | -------- | --------- |
| Generate access report   | System   | IAM       |
| Review access list       | Manager  | IAM       |
| Approve / revoke access  | Manager  | IAM       |
| Record review completion | Manager  | Ticketing |
| Audit verification       | Security | GRC       |

---

### Evidence (derived from actions)

* Access report generated timestamp
* Approval/revocation logs
* Ticket marked “Completed”
* IAM change events

**Evidence is a projection of actions.**

---

### Issue (if actions fail)

> “Access review completed but no revocations performed despite stale users.”

This issue exists **even though evidence exists** — because the *action quality* was poor.

---

## 4️⃣ Action → Evidence → Issue mapping (explicit)

### Action quality dimensions (critical)

Each user action should be evaluated on:

| Dimension    | Example                            |
| ------------ | ---------------------------------- |
| Timeliness   | Was it done on time?               |
| Completeness | Were all required actions taken?   |
| Authority    | Did the right role perform it?     |
| Outcome      | Did it change system state?        |
| Consistency  | Does it match historical behavior? |

---

### Example: Same evidence, different outcome

| Scenario                          | Evidence | Issue? |
| --------------------------------- | -------- | ------ |
| Review done, stale access revoked | Yes      | ❌      |
| Review done, no changes           | Yes      | ⚠️     |
| Review skipped                    | No       | ❌❌     |
| Review auto-approved              | Yes      | ❌      |

**This is why evidence-only compliance fails.**

---

## 5️⃣ Modeling this correctly (data model)

### Core entities

```text
user_action
procedure
evidence
issue
```

### Example fields for `user_action`

```sql
user_action (
  action_id
  action_type          -- approve_access, review_completed
  actor_id
  actor_role
  system               -- IAM, ServiceNow, GitHub
  target_resource
  timestamp
  expected_outcome
  actual_outcome
  metadata
)
```

### Relationships

```text
procedure ── requires ──> user_action
user_action ── produces ──> evidence
evidence ── supports ──> control
issue ── caused_by ──> missing_or_invalid user_action
```

---

## 6️⃣ How this enables risk-based compliance (important)

Once actions are first-class:

### 🔹 Control effectiveness

```text
effectiveness = % of required actions
                × action quality score
                × freshness
```

### 🔹 Likelihood modeling

* Repeated missed actions → ↑ likelihood
* Rubber-stamp behavior → ↑ likelihood
* Automation without oversight → ↑ likelihood

### 🔹 Impact modeling

* Action touches crown-jewel asset → ↑ impact
* Privileged role involved → ↑ impact

---

## 7️⃣ Agentic AI view (how agents reason about actions)

### Discovery Agent

* “What actions are required for this control?”

### Monitoring Agent

* “Which actions are missing, late, or anomalous?”

### Risk Agent

* “What does this pattern of actions imply about control decay?”

### Compliance Agent

* “Explain *why* CC6 is failing in plain English.”

> “Access reviews are being completed on time, but managers rarely revoke access. This suggests review fatigue and reduced control effectiveness.”

---

## 8️⃣ Common mistakes

❌ Treating actions as evidence
❌ Not evaluating action quality
❌ Ignoring *who* performed the action
❌ No historical baseline of behavior
❌ No linkage from action → business impact

---

## 9️⃣ TL;DR (mental model)

* **Controls are intentions**
* **Procedures are plans**
* **User actions are reality**
* **Evidence is a shadow**
* **Issues are gaps between intent and reality**

If you want next, I can:

* Show how to score **action risk**
* Map actions to **ServiceNow / IAM / GitHub events**
* Design a **user-action → risk pipeline**
* Show how to detect **“checkbox compliance” behavior**

Just tell me where to go deeper.



python -m indexing_cli.ingest_preview_files \
    --preview-dir indexing_preview \
    --content-types table_definitions table_descriptions column_definitions knowledgebase contextual_edges
# ATT&CK → Framework Controls Mapping Design

> Use as `@attack_to_controls_mapping_design.md` in Cursor when building:
> - `app/agents/tools/attack_risk_mapper.py`
> - `app/agents/tools/risk_control_mapper.py`
> - `app/ingestion/framework_intel/hipaa_loader.py`
> - `app/ingestion/framework_intel/control_test_loader.py`
> - `indexing_cli/framework_ingest.py`

---

## What this system does

Takes an ATT&CK technique + tactic and produces a pre-computed, reusable mapping graph:
1. Which **risk scenarios** from HIPAA/SOC2/NIST/ISO this technique threatens
2. Which **controls** mitigate each of those risk scenarios
3. Which **test cases / evidence signals** verify each control is operating
4. A **coverage gap** record — techniques with no mapped scenarios or controls

All three outputs are computed once as a batch ingestion job and stored in
Postgres. Downstream consumers (agents, dashboards, reports) query the tables
directly — no LLM is invoked at query time.

---

## Your data — what you already have

### HIPAA enriched JSON (`hipaa_enriched.json`)

Per control (e.g. `AST-12`):
- `control_code`, `domain`, `sub_domain`
- `measurement_goal`
- `focus_areas` — list of security domains (e.g. `data_protection`, `endpoint_security`)
- `risk_categories` — list of ISO-style categories
- `affinity_keywords` — rich semantic signal for LLM matching
- `control_type_classification.type` — `preventive | detective | corrective`
- `evidence_requirements.data_signals` — exactly what evidence proves this control operates
- `differentiation_note` — what makes this control unique vs neighbors

### Controls YAML (`controls_hipaa.yaml`)

Per control:
- `control_id` (e.g. `AST-12`)
- `name` (short label)
- `description` (full implementation guidance)

### Risk scenarios YAML (`scenarios_hipaa.yaml`)

Per scenario:
- `scenario_id` (e.g. `HIPAA-RISK-001`)
- `name` — the risk scenario sentence
- `category` — ISO-style domain
- `asset` — asset class affected
- `trigger` — `control failure | human error | ...`
- `loss_outcomes` — `[breach, operational impact, fine]`
- `mitigated_by` — **list of control IDs** that already have a static mapping

This `mitigated_by` list is the **seed** for Stage B LLM. Don't ignore it — it is
ground truth that the LLM should validate, not replace.

### Requirements YAML (`requirements_hipaa.yaml`)

Per requirement:
- `requirement_id` (e.g. `164.308(a)(1)(i)`)
- `description` — full regulatory intent text

---

## Core tables to build

### 1. `attack_risk_mappings` — Technique → Risk scenario

```sql
CREATE TABLE attack_risk_mappings (
    id              SERIAL PRIMARY KEY,
    technique_id    TEXT NOT NULL,          -- e.g. T1078
    tactic          TEXT NOT NULL,          -- e.g. initial-access
    scenario_id     TEXT NOT NULL,          -- e.g. HIPAA-RISK-001
    framework       TEXT NOT NULL,          -- hipaa | soc2 | nist_csf | iso27001
    confidence      TEXT NOT NULL CHECK (confidence IN ('high', 'medium', 'low')),
    mapping_basis   TEXT NOT NULL,          -- semantic | keyword | curated
    rationale       TEXT,                   -- LLM explanation
    loss_outcomes   TEXT[],                 -- from scenario: breach | operational_impact
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (technique_id, tactic, scenario_id, framework)
);
```

### 2. `risk_control_mappings` — Risk scenario → Control

```sql
CREATE TABLE risk_control_mappings (
    id              SERIAL PRIMARY KEY,
    scenario_id     TEXT NOT NULL,          -- e.g. HIPAA-RISK-001
    framework       TEXT NOT NULL,
    control_id      TEXT NOT NULL,          -- e.g. AST-12
    coverage_type   TEXT NOT NULL CHECK (coverage_type IN ('preventive', 'detective', 'corrective')),
    confidence      TEXT NOT NULL,
    mapping_source  TEXT NOT NULL,          -- static (from mitigated_by) | llm_validated | llm_inferred
    rationale       TEXT,
    UNIQUE (scenario_id, control_id, framework)
);
```

### 3. `control_test_mappings` — Control → Test cases + evidence

```sql
CREATE TABLE control_test_mappings (
    id              SERIAL PRIMARY KEY,
    control_id      TEXT NOT NULL,
    framework       TEXT NOT NULL,
    test_id         TEXT NOT NULL,          -- e.g. AST-12-T1
    test_name       TEXT,
    evidence_signals TEXT[],               -- from evidence_requirements.data_signals
    metric_logic    TEXT,                   -- from measurement_goal
    control_type    TEXT,                   -- from control_type_classification.type
    UNIQUE (control_id, test_id, framework)
);
```

### 4. `coverage_gaps` — techniques with incomplete mapping paths

```sql
CREATE TABLE coverage_gaps (
    id              SERIAL PRIMARY KEY,
    technique_id    TEXT NOT NULL,
    tactic          TEXT NOT NULL,
    framework       TEXT NOT NULL,
    gap_type        TEXT,                   -- no_scenario | no_control | no_test
    scenario_ids    TEXT[],                 -- which scenarios were found (if any)
    detected_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (technique_id, tactic, framework, gap_type)
);
```

---

## Two LLM stages

### Stage A — Technique → Risk scenario

**When to run:** When a new `(technique_id, tactic)` pair has no rows in
`attack_risk_mappings` for the target framework.

**Inputs passed to LLM:**
```python
{
    "technique_id":   "T1078",
    "tactic":         "initial-access",
    "technique_name": "Valid Accounts",
    "technique_desc": "Adversaries may obtain and abuse credentials of existing accounts...",
    "data_sources":   ["Logon Session", "User Account"],

    "candidate_scenarios": [
        {
            "scenario_id":    "HIPAA-RISK-001",
            "name":           "Appropriate contacts are not maintained...",
            "category":       "Information security operations",
            "asset":          "information_security_operations",
            "loss_outcomes":  ["breach"],
            "description":    "..."   # truncated to 400 chars
        },
        # ... top-K by keyword overlap (see retrieval below)
    ]
}
```

**Retrieval — how to select top-K candidates without vector search:**

Score each scenario against the technique by keyword overlap:
```python
def _score_scenario_technique(technique: dict, scenario: dict) -> float:
    technique_tokens = set(
        technique["technique_name"].lower().split() +
        technique["tactic"].replace("-", " ").split()
    )
    scenario_tokens = set(
        scenario["name"].lower().split() +
        scenario.get("category", "").lower().split() +
        [o.replace("_", " ") for o in scenario.get("loss_outcomes", [])]
    )
    return len(technique_tokens & scenario_tokens) / max(len(technique_tokens), 1)
```

Take top-15 by score, then pass to LLM for semantic validation and ranking.

**LLM prompt (Stage A):**
```
You are a security analyst mapping ATT&CK techniques to compliance risk scenarios.

Technique: {technique_id} — {technique_name}
Tactic: {tactic}
Description: {technique_desc}

Below are candidate HIPAA risk scenarios. For each, decide:
1. Does this technique enable or directly threaten this risk scenario?
2. Assign confidence: high | medium | low
3. Identify the loss_outcome this technique most directly triggers (breach | operational_impact)

Return JSON list:
[
  {
    "scenario_id": "HIPAA-RISK-XXX",
    "matches": true | false,
    "confidence": "high | medium | low",
    "loss_outcome": "breach | operational_impact",
    "rationale": "one sentence"
  }
]

Only return scenarios where matches=true. Return empty list if none match.

Candidate scenarios:
{candidate_scenarios_json}
```

**Write output to** `attack_risk_mappings`.

---

### Stage B — Risk scenario → Control (LLM validates the `mitigated_by` seed)

**When to run:** When a `scenario_id` has no rows in `risk_control_mappings`
for the target framework.

**Critical:** `scenarios_hipaa.yaml` already has `mitigated_by: [control_ids]`.
These are ground-truth static mappings. Stage B has two jobs:
1. **Validate** each static mapping — confirm it is relevant and assign coverage_type
2. **Infer additional controls** the static list missed using the enriched JSON

**Inputs:**
```python
{
    "scenario": {
        "scenario_id":   "HIPAA-RISK-001",
        "name":          "Appropriate contacts not maintained...",
        "description":   "...",
        "loss_outcomes": ["breach"],
        "trigger":       "control failure"
    },
    "static_controls": [
        {
            "control_id":  "IRO-12",
            "name":        "Incident response procedures",
            "description": "...",       # from controls_hipaa.yaml
            "control_type": "corrective",  # from hipaa_enriched.json
            "affinity_keywords": [...],
            "focus_areas": [...],
        },
        # ... all controls from mitigated_by
    ],
    "candidate_additional_controls": [
        # controls NOT in mitigated_by, scored by affinity_keyword overlap
        # top-10 by overlap with scenario keywords
    ]
}
```

**LLM prompt (Stage B):**
```
You are a compliance engineer mapping HIPAA risk scenarios to controls.

Risk Scenario: {scenario_id}
Name: {scenario_name}
Description: {scenario_description}
Loss outcomes: {loss_outcomes}
Trigger: {trigger}

Task 1 — Validate these EXISTING control mappings (from mitigated_by):
For each, confirm whether this control genuinely mitigates the scenario.
Assign: coverage_type (preventive | detective | corrective), confidence, rationale.

Task 2 — Review these CANDIDATE additional controls.
Add any that genuinely mitigate this scenario with their coverage_type and confidence.

Return JSON:
{
  "validated": [
    {
      "control_id": "IRO-12",
      "coverage_type": "corrective",
      "confidence": "high",
      "rationale": "one sentence",
      "retain": true
    }
  ],
  "added": [
    {
      "control_id": "MON-9",
      "coverage_type": "detective",
      "confidence": "medium",
      "rationale": "one sentence"
    }
  ]
}

Static controls to validate:
{static_controls_json}

Candidate additional controls:
{candidate_controls_json}
```

**Write output to** `risk_control_mappings`:
- Records from `validated` where `retain=true`: `mapping_source = "static_validated"`
- Records from `validated` where `retain=false`: do not persist (log as dropped)
- Records from `added`: `mapping_source = "llm_inferred"`

---

## Stage C — Control → Test cases (no LLM needed)

This is a **deterministic load** from `hipaa_enriched.json`. No LLM required.

```python
def load_control_test_mappings(enriched: dict, framework: str) -> list[dict]:
    rows = []
    for control_id, data in enriched[framework].items():
        signals = data.get("evidence_requirements", {}).get("data_signals", [])
        metric  = data.get("measurement_goal", "")
        ctype   = data.get("control_type_classification", {}).get("type", "unknown")
        for i, signal in enumerate(signals):
            rows.append({
                "control_id":      control_id,
                "framework":       framework,
                "test_id":         f"{control_id}-T{i+1}",
                "test_name":       signal[:100],
                "evidence_signals": [signal],
                "metric_logic":    metric[:500],
                "control_type":    ctype,
            })
    return rows
```

Run once after `hipaa_enriched.json` is loaded. Output goes to
`control_test_mappings`.

---

## Ingestion order

Run once per framework before any downstream consumer queries the mapping tables:

```
1. load_controls(framework)           → upsert controls table from YAML
2. load_scenarios(framework)          → upsert scenarios table from YAML (includes mitigated_by)
3. load_control_test_mappings()       → Stage C: deterministic load from enriched JSON
4. run_stage_a(framework)             → LLM: all ATT&CK techniques → scenarios
5. run_stage_b(framework)             → LLM: scenarios → controls (validates mitigated_by + infers)
```

Stages A and B run as a **batch ingestion job**. They produce pre-computed
mappings that all downstream consumers query as plain SQL — no LLM at query time.

---

## Multi-framework support

The same Stage A / Stage B logic applies to all frameworks. Only the
scenario file and control file change per framework.

| Framework | Scenario file | Controls file | Enriched JSON |
|---|---|---|---|
| HIPAA | `scenarios_hipaa.yaml` | `controls_hipaa.yaml` | `hipaa_enriched.json` |
| SOC2 | `scenarios_soc2.yaml` | `controls_soc2.yaml` | `soc2_enriched.json` |
| NIST CSF 2.0 | `scenarios_nist_csf.yaml` | `controls_nist.yaml` | `nist_csf_2_0_enriched.json` |
| ISO 27001 2022 | `scenarios_iso.yaml` | `controls_iso.yaml` | `iso27001_2022_enriched.json` |

The `framework` column in every table is the join key across frameworks.
A single technique can have mapping rows for all four frameworks in parallel.

---

## Coverage scoring (per technique, per framework)

Query the mapping graph to understand how well each technique is covered:

```sql
-- Full path coverage: technique → scenarios → controls
SELECT
    arm.technique_id,
    arm.tactic,
    arm.framework,
    COUNT(DISTINCT arm.scenario_id)                          AS scenarios_matched,
    COUNT(DISTINCT rcm.control_id)                           AS controls_mapped,
    COUNT(DISTINCT CASE WHEN rcm.coverage_type = 'preventive'
                   THEN rcm.control_id END)                  AS preventive_count,
    COUNT(DISTINCT CASE WHEN rcm.coverage_type = 'detective'
                   THEN rcm.control_id END)                  AS detective_count,
    COUNT(DISTINCT CASE WHEN rcm.coverage_type = 'corrective'
                   THEN rcm.control_id END)                  AS corrective_count,
    ARRAY_AGG(DISTINCT arm.scenario_id)                      AS scenario_ids,
    ARRAY_AGG(DISTINCT rcm.control_id)                       AS control_ids
FROM      attack_risk_mappings  arm
LEFT JOIN risk_control_mappings rcm
       ON rcm.scenario_id = arm.scenario_id
      AND rcm.framework   = arm.framework
WHERE arm.technique_id = :technique_id
  AND arm.framework    = :framework
GROUP BY arm.technique_id, arm.tactic, arm.framework;
```

```sql
-- Gap summary: which techniques have no controls for a framework
SELECT
    technique_id,
    tactic,
    gap_type,
    COUNT(*) AS gap_count
FROM  coverage_gaps
WHERE framework = :framework
GROUP BY technique_id, tactic, gap_type
ORDER BY gap_count DESC;
```

---

## Files to create

| File | Purpose |
|---|---|
| `app/ingestion/framework_intel/hipaa_loader.py` | Load controls + scenarios + requirements from YAML into Postgres |
| `app/ingestion/framework_intel/control_test_loader.py` | Stage C: deterministic load of `control_test_mappings` from enriched JSON |
| `app/agents/tools/attack_risk_mapper.py` | Stage A: `(technique_id, tactic)` → `attack_risk_mappings` |
| `app/agents/tools/risk_control_mapper.py` | Stage B: `scenario_id` → `risk_control_mappings` |
| `indexing_cli/framework_ingest.py` | CLI runner: runs all five ingestion steps for a given framework |

---

## Key design rules

1. **LLM runs once per unique triple, never at query time.** Stage A runs
   once per `(technique_id, tactic, framework)`. Stage B runs once per
   `(scenario_id, framework)`. All downstream consumers read from tables.

2. **`mitigated_by` is ground truth, not a suggestion.** Stage B validates
   the static list, not replaces it. A LLM `retain=false` verdict should be
   logged and reviewed — never auto-dropped silently.

3. **Stage C is zero-LLM.** The `evidence_requirements.data_signals` array
   in the enriched JSON is already the test case list. Load it directly.

4. **Coverage gaps are first-class outputs.** Any technique that reaches
   Stage A or Stage B with no matching result writes to `coverage_gaps`.
   This table is the primary input for "what is your compliance blind spot."

5. **Confidence propagates through the chain.** When a downstream consumer
   reads a full path `technique → scenario → control`, the effective confidence
   is `min(attack_risk_mappings.confidence, risk_control_mappings.confidence)`.
   A high-confidence technique mapped through a low-confidence control path
   is a `low` confidence end-to-end result.
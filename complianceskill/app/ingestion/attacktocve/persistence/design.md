# ATT&CK Control Mapper — Holistic Redesign

## The Core Insight

The current enricher treats **controls**, **risk scenarios**, and **framework items** as three separate things to map independently. But in every control framework they are three lenses on the same object:

- A **control** is a safeguard that exists because a risk is real.
- A **risk scenario** is a concrete description of how that control fails.
- The **technique** is what an attacker does to cause that failure.

Separating them creates three retrieval passes, three mapping calls, and three sets of results that then need reconciling. The holistic model collapses them into one: a **FrameworkItem** that carries all three aspects, mapped once per `(technique, tactic)` pair.

---

## Unified Entity Model

### FrameworkItem — the single unit of mapping

Instead of separate scenario, control, and risk tables, every framework loads into one table: `framework_items`. Each row is simultaneously a control (what the safeguard requires), a risk (what fails when it is absent), and a scenario (the concrete conditions under which it fails).

| Aspect | What it answers | Example field |
|---|---|---|
| Control | What must be implemented | `control_objective` |
| Risk | What goes wrong if not | `risk_description` |
| Scenario | Under what conditions | `trigger`, `loss_outcomes` |

This means the retrieval query, the LLM mapping prompt, and the stored mapping record all operate on the same row. There is no join, no reconciliation, no "which of the three results wins."

---

## SQL Schema

### `control_frameworks` — framework registry

```sql
control_frameworks (
    framework_id        TEXT PRIMARY KEY,
    framework_name      TEXT NOT NULL,
    framework_version   TEXT,
    control_id_label    TEXT,
    qdrant_collection   TEXT NOT NULL,
    control_count       INTEGER,
    is_active           BOOLEAN DEFAULT TRUE,
    ingested_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
)
```

One row per registered framework. `qdrant_collection` is the name of the collection in your existing Qdrant instance that holds this framework's items. The graph reads framework identity from here at startup — nothing is hardcoded.

---

### `framework_items` — the unified control / risk / scenario entity

```sql
framework_items (
    item_id             TEXT NOT NULL,
    framework_id        TEXT NOT NULL REFERENCES control_frameworks(framework_id),

    -- Identity
    title               TEXT NOT NULL,
    control_family      TEXT,
    control_type        TEXT,          -- 'preventive' | 'detective' | 'corrective' | 'compensating'

    -- Control lens
    control_objective   TEXT,          -- what the safeguard requires
    implementation_guidance TEXT,

    -- Risk lens
    risk_description    TEXT,          -- what fails when the control is absent
    risk_severity       TEXT,          -- 'critical' | 'high' | 'medium' | 'low'
    risk_likelihood     TEXT,

    -- Scenario lens
    trigger             TEXT,          -- what causes the scenario to activate
    loss_outcomes       TEXT[],        -- 'breach' | 'compliance violation' | 'operational impact'
    affected_assets     TEXT[],

    -- ATT&CK alignment metadata (set at ingest time)
    tactic_domains      TEXT[],        -- ATT&CK tactic families this item addresses
    asset_types         TEXT[],        -- 'identity' | 'endpoint' | 'data' | 'network' | 'process'
    blast_radius        TEXT,

    -- Lifecycle
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (item_id, framework_id)
)
```

**Why one table covers all frameworks:** `framework_id` scopes every row. Queries always carry a `WHERE framework_id = ?` filter. Existing CIS rows keep their `item_id` as `CIS-RISK-001`. NIST rows use `AC-2`. ISO rows use `A.8.1`. The schema does not care.

---

### `attack_techniques` — ATT&CK catalogue (unchanged structure, clarified role)

```sql
attack_techniques (
    technique_id        TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    description         TEXT,
    tactics             TEXT[],
    platforms           TEXT[],
    data_sources        TEXT[],
    detection           TEXT,
    mitigations         JSONB,
    url                 TEXT,
    ingested_at         TIMESTAMPTZ DEFAULT NOW()
)
```

No changes needed. The key design decision is that this table is **read-only input** to the mapping pipeline. The pipeline never writes back to it.

---

### `tactic_contexts` — cached tactic risk lenses

```sql
tactic_contexts (
    technique_id        TEXT NOT NULL REFERENCES attack_techniques(technique_id),
    tactic              TEXT NOT NULL,
    tactic_risk_lens    TEXT NOT NULL,
    blast_radius        TEXT,
    primary_asset_types TEXT[],
    derived_at          TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (technique_id, tactic)
)
```

The `tactic_risk_lens` is the LLM-derived risk framing for a specific `(technique, tactic)` pair — for example, T1078 under `persistence` produces a different lens than T1078 under `initial-access`. This is computed once and cached here. Every subsequent pipeline run for the same pair reads from this table and skips the LLM derivation call.

---

### `attack_control_mappings` — partitioned by framework

```sql
attack_control_mappings (
    technique_id        TEXT NOT NULL,
    tactic              TEXT NOT NULL,
    item_id             TEXT NOT NULL,
    framework_id        TEXT NOT NULL,

    -- Scores
    relevance_score     NUMERIC(4,3) NOT NULL CHECK (relevance_score BETWEEN 0 AND 1),
    confidence          TEXT NOT NULL CHECK (confidence IN ('high', 'medium', 'low')),

    -- Reasoning
    rationale           TEXT,
    tactic_risk_lens    TEXT,
    blast_radius        TEXT,

    -- Denormalised for fast query (avoids joins in reporting)
    framework_name      TEXT,
    control_family      TEXT,
    item_title          TEXT,
    attack_tactics      TEXT[],
    attack_platforms    TEXT[],
    loss_outcomes       TEXT[],

    -- Provenance
    retrieval_score     NUMERIC(4,3),
    retrieval_source    TEXT,
    mapping_run_id      UUID,
    validated           BOOLEAN DEFAULT FALSE,
    validation_notes    TEXT,

    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (technique_id, tactic, item_id, framework_id)
)
PARTITION BY LIST (framework_id);
```

**Primary key is a 4-tuple.** `(T1078, persistence, AC-2, nist_800_53r5)` and `(T1078, initial-access, AC-2, nist_800_53r5)` are two distinct rows. Same technique, same control, different tactic context, different rationale, different relevance score.

**Partitions — one per framework:**
```sql
attack_control_mappings_cis   FOR VALUES IN ('cis_v8_1')
attack_control_mappings_nist  FOR VALUES IN ('nist_800_53r5')
attack_control_mappings_iso   FOR VALUES IN ('iso_27001_2022')
attack_control_mappings_soc2  FOR VALUES IN ('soc2_2017')
attack_control_mappings_pci   FOR VALUES IN ('pci_dss_v4')
```

Every framework query hits exactly one physical table. No cross-framework scan. Adding a new framework is `CREATE TABLE ... PARTITION OF` with zero application changes.

---

### `mapping_runs` — audit trail

```sql
mapping_runs (
    run_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    framework_id        TEXT REFERENCES control_frameworks(framework_id),
    triggered_by        TEXT,
    technique_filter    TEXT[],
    tactic_filter       TEXT[],
    item_count          INTEGER,
    technique_count     INTEGER,
    mapping_count       INTEGER,
    coverage_pct        NUMERIC(5,2),
    duration_seconds    NUMERIC(8,2),
    status              TEXT DEFAULT 'running'
                            CHECK (status IN ('running', 'complete', 'failed')),
    error_message       TEXT,
    started_at          TIMESTAMPTZ DEFAULT NOW(),
    completed_at        TIMESTAMPTZ
)
```

---

## Qdrant Collection Design

One collection per framework, matching `control_frameworks.qdrant_collection`.

**Document text** (what gets embedded):

```
{item.title}. {item.control_objective}. {item.risk_description}. {item.trigger}
```

All three lenses — control, risk, scenario — are embedded together into one vector. This is the holistic payoff: a single embedding captures what the control requires, what goes wrong, and how. Retrieval with a `tactic_risk_lens` query finds the most relevant item across all three dimensions simultaneously.

**Payload** (filterable metadata):

```json
{
  "item_id":         "AC-2",
  "framework_id":    "nist_800_53r5",
  "control_family":  "Access Control",
  "control_type":    "preventive",
  "tactic_domains":  ["initial-access", "persistence", "privilege-escalation"],
  "asset_types":     ["identity"],
  "blast_radius":    "identity",
  "risk_severity":   "high",
  "loss_outcomes":   ["breach", "compliance violation"]
}
```

**Query filter at retrieval time:**

```
WHERE framework_id = {framework_id}
  AND tactic_domains CONTAINS {active_tactic}
```

The `tactic_domains` filter is applied before semantic ranking. The semantic query is the `tactic_risk_lens` string. This means the candidate set is already tactic-scoped before the embeddings are compared — faster and more precise than post-filtering.

---

## How the Enricher Changes — Holistic View

### Current flow (fragmented)

```
Technique
  → retrieve CIS scenarios       (pass 1)
  → map to scenarios             (LLM call 1)
  → retrieve controls            (pass 2, if separate)
  → map to controls              (LLM call 2)
  → reconcile overlapping results
```

### New flow (holistic)

```
(Technique, Tactic)
  → derive tactic_risk_lens      (cached after first run)
  → retrieve FrameworkItems      (single pass, one collection, tactic pre-filtered)
  → map to items                 (single LLM call, prompt carries all three lenses)
  → one mapping record per item  (captures control + risk + scenario in one row)
```

The LLM sees a candidate that says: *"Control AC-2 requires account lifecycle management. The risk when absent is that terminated accounts remain active. The scenario trigger is employee offboarding process failure. Loss outcomes: breach, compliance violation."* That is richer context for a single mapping call than three separate calls against fragmented tables.

### What the mapping record now captures

A single `attack_control_mappings` row for `(T1078, persistence, AC-2, nist_800_53r5)` answers all of these at once:

- Which **control** does this technique threaten? → `item_id = AC-2`, `control_family = Access Control`
- Which **risk** does it exploit? → `tactic_risk_lens`, `blast_radius`
- Under what **scenario** does it play out? → `loss_outcomes`, inherited from `framework_items`
- How confident are we? → `confidence`, `relevance_score`
- What is the reasoning? → `rationale` (written against all three lenses)

---

## Key Indexes

```sql
-- Fast framework-scoped queries
CREATE INDEX ON framework_items (framework_id, control_family);
CREATE INDEX ON framework_items USING GIN (tactic_domains);
CREATE INDEX ON framework_items USING GIN (asset_types);

-- Mapping lookups
CREATE INDEX ON attack_control_mappings (technique_id, tactic);
CREATE INDEX ON attack_control_mappings (item_id, framework_id);
CREATE INDEX ON attack_control_mappings (confidence, relevance_score DESC);

-- Tactic context cache
CREATE INDEX ON tactic_contexts (technique_id);

-- Coverage gap view
CREATE INDEX ON attack_control_mappings (framework_id, item_id)
    WHERE validated = TRUE;
```

---

## Useful Views

**`v_unmapped_items`** — framework items with no confirmed mapping (your gap list)

```sql
SELECT fi.*
FROM framework_items fi
LEFT JOIN attack_control_mappings m
    ON m.item_id = fi.item_id AND m.framework_id = fi.framework_id
WHERE m.item_id IS NULL
ORDER BY fi.framework_id, fi.risk_severity DESC
```

**`v_tactic_coverage`** — which tactics are well-covered vs thin across a framework

```sql
SELECT
    m.framework_id,
    m.tactic,
    COUNT(DISTINCT m.item_id)       AS items_covered,
    AVG(m.relevance_score)          AS avg_relevance,
    COUNT(*) FILTER (WHERE m.confidence = 'high') AS high_confidence
FROM attack_control_mappings m
GROUP BY m.framework_id, m.tactic
ORDER BY m.framework_id, items_covered DESC
```

**`v_item_technique_matrix`** — the full coverage matrix per framework

```sql
SELECT
    fi.item_id,
    fi.title,
    fi.control_family,
    fi.risk_severity,
    ARRAY_AGG(DISTINCT m.technique_id) AS techniques,
    ARRAY_AGG(DISTINCT m.tactic)       AS tactics_covered,
    MAX(m.relevance_score)             AS best_relevance
FROM framework_items fi
LEFT JOIN attack_control_mappings m
    ON m.item_id = fi.item_id AND m.framework_id = fi.framework_id
WHERE fi.framework_id = :framework_id
GROUP BY fi.item_id, fi.title, fi.control_family, fi.risk_severity
```

---

## Migration from Current Schema

| Current table / column | New table / column | Change |
|---|---|---|
| `cis_risk_scenarios` | `framework_items` | All frameworks in one table, scoped by `framework_id` |
| `scenario_id` | `item_id` | Renamed, now framework-neutral |
| No `tactic` column in mappings | `tactic TEXT NOT NULL` in PK | Tactic is now part of the natural key |
| Single flat `attack_control_mappings` | Partitioned by `framework_id` | One physical table per framework |
| No `tactic_contexts` table | `tactic_contexts` | New: caches LLM-derived risk lenses |
| No `control_objective` / `risk_description` split | Both columns in `framework_items` | Control and risk lenses explicit |
| VS: single collection | VS: one collection per framework | Collection name stored in `control_frameworks.qdrant_collection` |
| Embedded text: description only | Embedded text: `title + objective + risk + trigger` | Holistic embedding |

The existing CIS data migrates by inserting into `framework_items` with `framework_id = 'cis_v8_1'`, mapping `scenario_id → item_id`, `description → risk_description`, and leaving `control_objective` to be populated from the CIS Controls source document. Existing mappings migrate by adding `tactic = 'unknown'` for rows that pre-date the tactic-aware pipeline — they remain queryable but are flagged for re-enrichment.
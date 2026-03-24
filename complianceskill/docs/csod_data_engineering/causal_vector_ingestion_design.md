# Causal Engine Vector Store — Ingestion Design

## Overview

Four seed files need to be ingested into the vector store to power the CCE
(`csod_causal_graph_node`) and downstream metric retrieval.  Each file plays a
distinct role in the retrieval pipeline and maps to a dedicated Qdrant
collection.

| File | Items | Role in CCE |
|------|-------|-------------|
| `lms_causal_nodes_seed.json` | 47 nodes | Graph vertices — root causes, mediators, outcomes |
| `lms_causal_edges_v2.json` | 58 edges | Graph edges — directed causal mechanisms |
| `lms_focus_area_taxonomy.json` | 11 areas | Bridge: registry area → causal context |
| `lms_metric_use_case_groups_v2.json` | 18 intents | Bridge: intent classifier → metric group selection |

---

## 1. Collection Architecture

Four dedicated Qdrant collections, one per file type.  All collections share
the same embedding model (existing `EXECUTOR` LLM / text embeddings already
used by CCE).

```
qdrant/
├── lms_causal_nodes          ← 47 documents
├── lms_causal_edges          ← 58 documents
├── lms_focus_area_taxonomy   ← 11 documents
└── lms_use_case_groups       ← 18 documents
```

**Why not a single unified collection?**
The four item types serve completely different retrieval patterns.  Nodes are
fetched by metric proximity; edges are fetched by source/target node pair;
focus areas are fetched by registry concept/area name; use case groups are
fetched by intent string.  Keeping them separate allows per-collection filters
and avoids type bleed in similarity search.

---

## 2. What Gets Embedded vs What Goes in Payload

The general rule:

- **Embedding text** = the richest natural-language description of what this
  item *means* and what analytical question it answers.
- **Payload (metadata)** = structured fields used as Qdrant filters
  (`must`, `should`, `must_not`).

### 2.1 `lms_causal_nodes` collection

**Embedding text** (concatenate at ingest time):

```
{display_name}. {description}. LMS context: {domain_context.lms}
```

Example for `compliance_rate`:
> "Compliance Rate. Percentage of learners who completed all assigned mandatory
> training before the deadline within a defined period. LMS context: Core
> outcome KPI for SOC2/HIPAA training programmes; measured monthly for audit
> submission."

**Payload fields (metadata filters):**

| Field | Type | Filter use |
|-------|------|------------|
| `node_id` | string | exact match when expanding edges |
| `node_type` | string enum | `terminal / root / mediator / collider` |
| `domains` | string[] | domain-scoped queries (`lms`, `hr`) |
| `temporal_grain` | string | `weekly / monthly / quarterly` |
| `is_outcome` | bool | restrict to terminal outcomes |
| `collider_warning` | bool | exclude colliders from attribution paths |
| `framework_codes` | string[] | filter by compliance framework (SOC2, HIPAA, NIST) |
| `focus_areas` | string[] | filter by focus area name |
| `required_capabilities` | string[] | capability-gated retrieval |
| `observable` | bool | filter to observable-only metrics |
| `version` | string | schema version |

---

### 2.2 `lms_causal_edges` collection

**Embedding text** (concatenate at ingest time):

```
{source_name} causes {target_name}. {mechanism}. Domain: {domain}.
```

Example for `E01`:
> "login_count_weekly_trend causes session_to_user_ratio. Higher weekly login
> frequency leads to higher session-per-user ratios, reflecting deeper platform
> integration. Domain: lms.engagement_chain."

**Payload fields (metadata filters):**

| Field | Type | Filter use |
|-------|------|------------|
| `entry_id` | string | dedup on re-ingest |
| `edge_id` | string | shorthand reference |
| `source_node_id` | string | graph expansion from a known source node |
| `target_node_id` | string | reverse expansion to a known target |
| `direction` | string | `positive / negative` |
| `domains` | string[] | domain-scoped queries |
| `domain` | string | fine-grained domain chain (e.g. `lms.engagement_chain`) |
| `confidence` | float | minimum confidence threshold filter |
| `lag_window_days` | int | deadline-bounded path queries |
| `corpus_match_type` | string | `confirmed / analogous / novel` |
| `source_capability` | string | capability-gated expansion |
| `target_capability` | string | capability-gated expansion |
| `version` | string | schema version |

---

### 2.3 `lms_focus_area_taxonomy` collection

**Embedding text** (concatenate at ingest time):

```
{focus_area_key}: {description}. Intent signals: {intent_tags joined with ", "}.
Framework controls: {all framework codes joined}.
```

Example for `training_compliance`:
> "training_compliance: Mandatory and regulatory training completion against
> policy and audit targets. Intent signals: compliance, mandatory, policy,
> soc2, hipaa, audit, overdue. Framework controls: CC1.1, CC1.2, CC2.1,
> 164.308(a)(5)(i), 164.308(a)(5)(ii)(A), GOVERN.1, GOVERN.2, A.7.2.2."

**Payload fields (metadata filters):**

| Field | Type | Filter use |
|-------|------|------------|
| `focus_area_key` | string | exact match from registry area lookup |
| `domain` | string | domain filter |
| `causal_terminals` | string[] | terminal node IDs — used to seed CCE graph traversal |
| `framework_codes` | string[] | compliance framework filter |
| `csod_schemas` | string[] | L3 schema names required for this area |
| `dt_use_cases` | string[] | use case groups this area feeds |
| `capabilities_required` | string[] | required capability IDs |
| `capabilities_optional` | string[] | optional capability IDs |
| `metric_categories` | string[] | metric category names |
| `intent_tags` | string[] | keyword tags for pre-embedding fallback |

---

### 2.4 `lms_use_case_groups` collection

**Embedding text** (concatenate at ingest time):

```
{use_case_key}: {notes}. Required metric groups: {required_groups joined}.
Audience: {default_audience}. Causal terminals: {causal_terminals joined}.
```

Example for `skill_gap_analysis`:
> "skill_gap_analysis: Requires role-skill mapping source of truth. Required
> metric groups: skill_coverage, curriculum_evidence. Audience: learning_admin.
> Causal terminals: role_skill_match_rate."

**Payload fields (metadata filters):**

| Field | Type | Filter use |
|-------|------|------------|
| `use_case_key` | string | exact match from intent classifier output |
| `domain` | string | domain filter |
| `default_audience` | string | persona filter |
| `default_timeframe` | string | `daily / weekly / monthly / quarterly` |
| `causal_terminals` | string[] | terminal node IDs for CCE seeding |
| `primary_focus_areas` | string[] | focus area cross-reference |
| `required_capabilities` | string[] | capability gate |
| `required_groups` | string[] | metric groups the scorer must include |
| `optional_groups` | string[] | metric groups the scorer may include |
| `scorer_weights_override` | object | `{alpha, beta, gamma}` or null |
| `requires_cce` | bool | derive from notes: true if "CCE" mentioned |
| `requires_shapley` | bool | derive from notes: true if "Shapley" mentioned |
| `collider_guard` | bool | derive from notes: true if "collider guard" mentioned |

---

## 3. Ingestion Flow

### 3.1 Sequence

```
Seed files (JSON)
      │
      ▼
1. Parse + validate schema
      │
      ▼
2. Build embedding text string per record
      │
      ▼
3. Batch embed (existing LLM embedder)
      │
      ▼
4. Upsert into Qdrant collection
   (id = entry_id / node_id / focus_area_key / use_case_key)
      │
      ▼
5. Write ingest manifest to Postgres
   (collection, record_count, version, ingested_at)
```

### 3.2 ID Strategy

Each collection uses a stable string ID so re-ingestion is idempotent (upsert,
not insert):

| Collection | Document ID field |
|------------|-------------------|
| `lms_causal_nodes` | `node_id` (e.g. `compliance_rate`) |
| `lms_causal_edges` | `entry_id` (e.g. `corpus_lms_e01`) |
| `lms_focus_area_taxonomy` | `focus_area_key` (e.g. `training_compliance`) |
| `lms_use_case_groups` | `use_case_key` (e.g. `skill_gap_analysis`) |

### 3.3 Ingest Functions (module location)

The seed files already reference the intended ingest functions in their `meta`
blocks.  Place both under:

```
app/agents/causalgraph/vector_causal_graph_builder.py
```

```python
ingest_nodes(path: Path, collection: str = "lms_causal_nodes")
ingest_edges(path: Path, collection: str = "lms_causal_edges")
ingest_focus_areas(path: Path, collection: str = "lms_focus_area_taxonomy")
ingest_use_case_groups(path: Path, collection: str = "lms_use_case_groups")
```

A top-level orchestrator:

```python
ingest_all_lms_seed_data(docs_dir: Path)
```

called once on startup (guarded by version-check against Postgres manifest) or
via a CLI command.

---

## 4. Retrieval Patterns in CCE

Once ingested, the four collections are used in different stages of
`csod_causal_graph_node` and the surrounding pipeline:

### Stage A — Intent resolution (before CCE)
`lms_use_case_groups` collection
Query: embed `user_query` → similarity search → top-1 `use_case_key`
Payload: read `required_capabilities`, `causal_terminals`, `scorer_weights_override`
Output → feeds `csod_intent_classifier` and `csod_scoring_validator`

### Stage B — Focus area to causal seed (after area_confirm)
`lms_focus_area_taxonomy` collection
Query: exact match on `focus_area_key` = confirmed area id
Payload: read `causal_terminals`, `csod_schemas`, `capabilities_required`
Output → seed node IDs for graph traversal; L3 schema whitelist

### Stage C — Node retrieval (inside CCE)
`lms_causal_nodes` collection
Query: embed `user_query` + filter `domains = ["lms"]`, `collider_warning = false`
Optional filters: `framework_codes`, `focus_areas`, `is_outcome`
Output → candidate metric nodes, typed (root / mediator / terminal)

### Stage D — Edge expansion (inside CCE)
`lms_causal_edges` collection
Query: for each retrieved node, filter `source_node_id IN {node_ids}` OR
`target_node_id IN {node_ids}`, optionally filter `confidence >= 0.65`
Output → directed edge set → assembled into DAG

### Stage E — Graph pruning
Use `collider_warning = true` filter to flag / exclude collider nodes
(`completion_rate`, `ilt_attendance_rate`) from attribution paths.
Use `lag_window_days` to prune edges outside deadline horizon for
`compliance_gap_close` use case.

---

## 5. Cross-File Linkage Map

The four files form an interconnected graph of references.  The ingest
pipeline should surface these as payload fields (already done above) so
retrieval can traverse across collections at query time.

```
lms_use_case_groups
  └─ causal_terminals ──────────────► lms_causal_nodes (node_id)
  └─ primary_focus_areas ───────────► lms_focus_area_taxonomy (focus_area_key)
  └─ required_capabilities ─────────► lms_causal_nodes (required_capabilities)

lms_focus_area_taxonomy
  └─ causal_terminals ──────────────► lms_causal_nodes (node_id)
  └─ dt_use_cases ──────────────────► lms_use_case_groups (use_case_key)
  └─ csod_schemas ──────────────────► L3 MDL schema retrieval (csod_mdl_schema_retrieval_node)

lms_causal_nodes
  └─ node_id ───────────────────────► lms_causal_edges (source_node_id / target_node_id)
  └─ focus_areas ───────────────────► lms_focus_area_taxonomy (focus_area_key)
  └─ framework_codes ───────────────► compliance framework filter context

lms_causal_edges
  └─ source_node_id / target_node_id ► lms_causal_nodes (node_id)
  └─ source_capability / target_capability ► lms_use_case_groups (required_capabilities)
```

---

## 6. Embedding Text Construction — Worked Examples

### Node: `role_skill_match_rate`
```
Role-Skill Match Rate. Proportion of role-required skills covered by a
learner's verified training completions or certifications. LMS context:
Terminal KPI for competency-based learning programmes; used in skill gap
analysis to report alignment between job profile requirements and
demonstrated training evidence.
```

### Edge: `E47` (skill-gap domain)
```
skill_coverage_pct causes role_skill_match_rate. Higher curriculum coverage
of role-required skills directly improves the proportion of learners whose
training portfolio matches their job profile skill requirements. Domain:
lms.skills.
```

### Focus area: `skill_development`
```
skill_development: Competency mapping, skill gap identification, curriculum
coverage, role-skill alignment. Intent signals: skill, competency, gap,
curriculum, role, job_profile. Framework controls: CC1.1, GOVERN.1, MAP.1,
A.7.2.2.
```

### Use case group: `skill_gap_analysis`
```
skill_gap_analysis: Requires role-skill mapping source of truth. Required
metric groups: skill_coverage, curriculum_evidence. Audience: learning_admin.
Causal terminals: role_skill_match_rate.
```

With these four embeddings, a query like *"skill compliance training gaps over
the last year"* should semantically surface:
- `skill_gap_analysis` use case (embedding hits "skill gap" + "curriculum
  evidence")
- `role_skill_match_rate` node (terminal outcome)
- `skill_development` focus area
- edges in the `lms.skills` domain chain

---

## 7. Ingest Manifest Schema (Postgres)

Track each ingest run to support idempotent startup checks and version-gated
re-ingestion:

```sql
CREATE TABLE causal_ingest_manifest (
    id            SERIAL PRIMARY KEY,
    collection    VARCHAR(80)   NOT NULL,  -- e.g. lms_causal_nodes
    source_file   VARCHAR(255)  NOT NULL,  -- filename (not full path)
    file_version  VARCHAR(20)   NOT NULL,  -- from meta.version
    record_count  INTEGER       NOT NULL,
    ingested_at   TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    ingested_by   VARCHAR(80),             -- service / user
    UNIQUE (collection, file_version)
);
```

On startup the orchestrator queries `causal_ingest_manifest` for each
collection.  If the `file_version` in the JSON `meta` block is already present
it skips; otherwise it re-ingests and upserts the row.

---

## 8. Node Type Handling Notes

The 47 nodes break into 4 types with distinct CCE treatment:

| Type | Count | CCE treatment |
|------|-------|---------------|
| `root` | 10 | Exogenous inputs — valid path starts; never filtered out |
| `mediator` | 27 | Internal path nodes — primary traversal targets |
| `terminal` | 8 | Outcome KPIs — graph endpoints; `is_outcome = true` |
| `collider` | 2 | Collider-warning nodes (`completion_rate`, `ilt_attendance_rate`) — flag in payload, exclude from Shapley attribution paths unless explicitly requested |

Colliders must be retrievable (they are real metrics users ask about) but CCE
must not route causal attribution through them.  The `collider_warning = true`
payload field enables this selective exclusion at query time without removing
the documents.

---

## 9. Edge Confidence Tiers

The 58 edges span confidence 0.61–0.88.  Three retrieval tiers:

| Tier | Range | Default query filter |
|------|-------|----------------------|
| High | ≥ 0.80 | Always included |
| Medium | 0.65–0.79 | Included by default |
| Low | < 0.65 | Only included when `corpus_match_type = "confirmed"` |

Expose as a named filter parameter in `ingest_edges` so callers can override:
`min_confidence: float = 0.65`.

---

## 10. File → Collection → CCE Node Mapping Summary

```
Seed file                         Collection                  Used by
─────────────────────────────────────────────────────────────────────────────
lms_causal_nodes_seed.json    →  lms_causal_nodes         →  csod_causal_graph_node
                                                               csod_cross_concept_check_node (via area_matches)
                                                               csod_scoring_validator_node

lms_causal_edges_v2.json      →  lms_causal_edges         →  csod_causal_graph_node (DAG assembly)

lms_focus_area_taxonomy.json  →  lms_focus_area_taxonomy  →  csod_area_matcher_node (planner graph)
                                                               csod_mdl_schema_retrieval_node (schema whitelist)
                                                               csod_cross_concept_check_node

lms_metric_use_case_groups_v2 →  lms_use_case_groups      →  csod_intent_classifier_node
    .json                                                      csod_scoring_validator_node (weights override)
                                                               csod_metrics_retrieval_node (group selection)
```

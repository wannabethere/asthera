# ATT&CK → Control Mapping — Tool Design Against Actual Codebase

## What the Three Files Tell Us

### `attack_tools.py`

`ATTACKTechniqueDetail` already has two tactic fields:

| Field | Content | Example |
|---|---|---|
| `tactics` | Title-cased human label | `["Initial Access", "Persistence"]` |
| `kill_chain_phases` | Raw MITRE slug | `["initial-access", "persistence"]` |

The slugs in `kill_chain_phases` are the values to use for tactic filtering — they match ATT&CK's canonical tactic identifiers exactly. The title-cased `tactics` are for display only.

**Existing bug:** `_query_postgres()` reads from the `attack_techniques` table but does not populate `kill_chain_phases` — it is left as an empty list. Any technique fetched from Postgres returns an `ATTACKTechniqueDetail` with `kill_chain_phases = []`, making tactic disambiguation impossible on the cached path. This must be fixed before anything else.

---

### `collections.py`

`FrameworkCollections` splits framework knowledge across five collections:

```
framework_controls      → what the safeguard requires
framework_requirements  → compliance requirements
framework_risks         → what fails when the control is absent
framework_test_cases    → how to test the control
framework_scenarios     → concrete conditions under which failure occurs
```

`AttackCollections` has one collection: `attack_techniques`.

There is no collection for tactic risk lenses, and no unified framework item collection. Both need to be added.

---

### `vector_store.py`

`ChromaVectorStoreClient.normalize_filter()` has complete logic: list values become `{"$in": [...]}`, multiple conditions wrap in `{"$and": [...]}`.

`QdrantVectorStoreClient.normalize_filter()` returns the filter dict unchanged (`return where`). This means any filter that requires Qdrant-specific structure — specifically array-contains for `tactic_domains` — will not be normalised automatically. The new retrieval tool produces a `tactic_domains` filter that needs explicit handling here.

Both clients delegate to `DocumentQdrantStore` / `DocumentChromaStore` via `_get_document_store()`, which is instantiated per collection and cached in `_document_stores`. The `semantic_search()` method is called on these store objects. The `query()` method normalises the return format to `{ids, documents, metadatas, distances}` across both backends.

---

## Changes to Existing Files

### `attack_tools.py` — two changes only

**Change 1: Fix `_query_postgres()` missing `kill_chain_phases`**

The `attack_techniques` Postgres table has a `tactics` column (array of title-cased strings like `["Initial Access", "Persistence"]`). When constructing `ATTACKTechniqueDetail` from a Postgres row, `kill_chain_phases` must be derived from `tactics` by lowercasing each value and replacing spaces with hyphens. This makes both the STIX path and the Postgres cache path return a consistent object.

**Change 2: Add `tactic_contexts` field to `ATTACKTechniqueDetail`**

```
tactic_contexts: Dict[str, str]  default: {}
```

Key is a `kill_chain_phases` slug (e.g. `"persistence"`), value is the LLM-derived `tactic_risk_lens` string. Populated lazily by `TacticContextualiserTool` after enrichment. Defaults to an empty dict so no existing call site breaks. Flows into LangGraph state automatically via `model_dump()`.

Nothing else in `attack_tools.py` changes. The enrichment tool factories, `ingest_stix_to_postgres`, and the `SecurityTool` wrapper are all unchanged.

---

### `collections.py` — two additions only

**`AttackCollections`** gains one constant:

```
TACTIC_CONTEXTS = "attack_tactic_contexts"
```

Updated `ALL`:
```
ALL = [TECHNIQUES, TACTIC_CONTEXTS]
```

This collection stores pre-computed tactic risk lenses. Document text is the `tactic_risk_lens` string itself. Payload carries `technique_id`, `tactic`, `blast_radius`, and `primary_asset_types`. Documents are keyed by `f"{technique_id}::{tactic}"` (e.g. `"T1078::persistence"`) so retrieval is a point lookup, not a semantic search.

---

**`FrameworkCollections`** gains one constant:

```
ITEMS = "framework_items"
```

Updated `ALL_FRAMEWORK`:
```
ALL_FRAMEWORK = [CONTROLS, REQUIREMENTS, RISKS, TEST_CASES, SCENARIOS, ITEMS]
```

`ALL` (which includes `USER_POLICIES`) does not change. `ITEMS` is the unified collection — each document embeds `title + control_objective + risk_description + trigger` concatenated, with `framework_id`, `tactic_domains`, `asset_types`, `control_family`, and `blast_radius` as filterable payload. The five existing collections remain untouched; `RetrievalService` continues to query them for all existing agents.

---

**`ComplianceSkillCollections.ACTIVE_COLLECTIONS`** — add the two new collections to the active dict so `is_collection_active()` and `get_collection_info()` return accurate results. Add an `"attack_mapping"` entry to the `get_collection_info()` return dict alongside `"framework_kb"`, `"mdl"`, etc.

No backward-compat aliases change. `Collections = _LegacyCollections` is untouched.

---

### `vector_store.py` — one change only

**`QdrantVectorStoreClient.normalize_filter()`** currently returns `where` unchanged. It needs to handle the array-contains pattern that `FrameworkItemRetrievalTool` uses.

Convention: a filter key suffixed with `__contains` (e.g. `{"tactic_domains__contains": "persistence"}`) signals an array membership check. `normalize_filter` should strip the `__contains` suffix and convert the condition to the structure that `DocumentQdrantStore.semantic_search()` accepts for array membership — either a Qdrant `FieldCondition` with `MatchAny`, or the equivalent dict form if `DocumentQdrantStore` handles the conversion internally.

**Action before implementing:** Check `app/storage/documents.py` to confirm whether `DocumentQdrantStore.semantic_search(where=...)` already converts list values to `MatchAny` internally. If it does, `normalize_filter` only needs to strip the `__contains` suffix and pass the value as a list. If it does not, the full Qdrant filter structure must be built here.

No changes to `ChromaVectorStoreClient` — its `normalize_filter` already handles list values correctly.

---

## New Tools

### Tool 1 — `TacticContextualiserTool`

**File:** `app/agents/tools/tactic_contextualiser.py`

**Role:** Given a technique and one of its tactics, derive a natural-language `tactic_risk_lens` that frames the technique's risk profile specifically under that tactic. Cache the result in Postgres and in `AttackCollections.TACTIC_CONTEXTS`.

**Input schema:**
```
technique_id : str   — e.g. "T1078"
tactic       : str   — kill_chain_phases slug, e.g. "persistence"
```

**Output schema:**
```
technique_id        : str
tactic              : str
tactic_risk_lens    : str    — LLM-derived, 2–3 sentences
blast_radius        : str    — "identity" | "endpoint" | "data" | "network" | "process"
primary_asset_types : List[str]
source              : str    — "cache_postgres" | "cache_qdrant" | "derived"
```

**Resolution order:**

1. Query `tactic_contexts` Postgres table for `(technique_id, tactic)`. If found, return with `source = "cache_postgres"`.
2. Point-query `AttackCollections.TACTIC_CONTEXTS` by id `f"{technique_id}::{tactic}"` via `get_vector_store_client()`. If found, return with `source = "cache_qdrant"` and write back to Postgres to repair the gap.
3. Call `ATTACKEnrichmentTool.get_technique(technique_id)` to get the full `ATTACKTechniqueDetail`. Verify the requested `tactic` exists in `kill_chain_phases` — raise a descriptive error if not. This guards against callers passing a tactic the technique does not appear under.
4. Call LLM with technique description + tactic slug → derive `tactic_risk_lens` and `blast_radius`.
5. Write to `tactic_contexts` Postgres table.
6. Write to `AttackCollections.TACTIC_CONTEXTS` via `get_vector_store_client().add_documents()`.
7. Update `ATTACKTechniqueDetail.tactic_contexts[tactic]` in the enrichment tool's local cache.
8. Return with `source = "derived"`.

**LangChain tool name:** `attack_tactic_contextualise`

**Why step 3 validates the tactic:** With the `kill_chain_phases` fix in place, `ATTACKTechniqueDetail` is now reliable on both fetch paths. A tactic absent from `kill_chain_phases` means the caller has the wrong pairing — catching it here prevents a permanently cached lens derived from incorrect inputs.

**Example output for T1078 under different tactics:**

| Tactic | `tactic_risk_lens` | `blast_radius` |
|---|---|---|
| `initial-access` | Attacker uses stolen or default credentials to bypass authentication at the network perimeter or cloud console. Primary risk is authentication boundary failure. | identity |
| `persistence` | Attacker creates or repurposes accounts to maintain long-term access after initial compromise. Primary risk is undetected durable footholds via dormant or cloned credentials. | identity |
| `privilege-escalation` | Attacker uses higher-privileged account credentials obtained during lateral movement. Primary risk is permission boundary bypass enabling access to sensitive data or systems. | identity |
| `defense-evasion` | Attacker operates under a legitimate account identity to blend with normal user behaviour. Primary risk is detection failure due to activity appearing legitimate in audit logs. | endpoint |

---

### Tool 2 — `FrameworkItemRetrievalTool`

**File:** `app/agents/tools/framework_item_retrieval.py`

**Role:** Query `FrameworkCollections.ITEMS` for a given framework, pre-filtered by tactic domain, semantically ranked by a tactic risk lens. Replaces the current pattern of querying `framework_risks` and `framework_scenarios` separately and reconciling.

**Input schema:**
```
query           : str    — the tactic_risk_lens string from TacticContextualiserTool
framework_id    : str    — e.g. "cis_v8_1", "nist_800_53r5"
tactic          : str    — kill_chain_phases slug, used as pre-filter on tactic_domains
top_k           : int    — default 8
score_threshold : float  — default 0.35
```

**Output schema:** `List[FrameworkItemResult]`, each:
```
item_id           : str
framework_id      : str
title             : str
control_family    : str
control_objective : str
risk_description  : str
trigger           : str
loss_outcomes     : List[str]
tactic_domains    : List[str]
asset_types       : List[str]
blast_radius      : str
similarity_score  : float
```

**Query pattern:**

Calls `get_vector_store_client()` — the same factory already used across the codebase — to get the active backend. Calls `client.query()` on `FrameworkCollections.ITEMS` with:

```
query_texts = [tactic_risk_lens]
n_results   = top_k
where       = client.normalize_filter({
    "framework_id": framework_id,
    "tactic_domains__contains": tactic
})
```

The `__contains` convention is normalised by `normalize_filter()` per backend. This makes the tool backend-agnostic — it constructs the filter in a neutral convention and the client handles the translation to Chroma `$in` or Qdrant `MatchAny`.

Results below `score_threshold` are discarded after retrieval.

**Fallback when `framework_items` collection is empty:**

Query `FrameworkCollections.RISKS` and `FrameworkCollections.SCENARIOS` separately via the same `client.query()` interface. Merge results by `item_id`, deduplicate (keep highest similarity score), return as `FrameworkItemResult` list with fields available from those collections populated and missing fields (e.g. `control_objective`) left as empty strings. This makes the tool usable before `framework_items` is fully populated.

**LangChain tool name:** `framework_item_retrieval`

---

### Tool 3 — `AttackControlMappingTool`

**File:** `app/agents/tools/attack_control_mapping.py`

**Role:** Orchestrate the full mapping pipeline for a single `(technique, tactic, framework)` triple. Calls the above two tools in sequence, then runs the LLM mapping and validation pass.

**Input schema:**
```
technique_id   : str   — e.g. "T1078"
tactic         : str   — kill_chain_phases slug
framework_id   : str   — e.g. "nist_800_53r5"
top_k          : int   — default 8
```

**Output schema:** `List[ControlMappingResult]`, each:
```
technique_id      : str
tactic            : str
item_id           : str
framework_id      : str
relevance_score   : float
confidence        : str    — "high" | "medium" | "low"
rationale         : str
tactic_risk_lens  : str
blast_radius      : str
control_family    : str
attack_tactics    : List[str]
attack_platforms  : List[str]
loss_outcomes     : List[str]
```

**Internal sequence:**

1. `ATTACKEnrichmentTool.get_technique(technique_id)` → full `ATTACKTechniqueDetail`
2. `TacticContextualiserTool(technique_id, tactic)` → `tactic_risk_lens`, `blast_radius`
3. `FrameworkItemRetrievalTool(tactic_risk_lens, framework_id, tactic, top_k)` → candidate items
4. Lookup `framework_name` and `control_id_label` from `control_frameworks` Postgres table — single query, cached in tool instance state after first call per framework. Falls back to `prompts.FRAMEWORKS` dict if Postgres is unavailable.
5. LLM mapping call — `prompts.CONTROL_MAPPING_SYSTEM` and `CONTROL_MAPPING_USER` injected with `framework_name`, `control_id_label`, technique context, `tactic_risk_lens`, and candidate items
6. LLM validation call — `prompts.VALIDATION_SYSTEM` and `VALIDATION_USER`
7. Return `List[ControlMappingResult]`

**LangChain tool name:** `attack_control_map`

**Multi-tactic usage:** To map a technique across all its tactics, the caller iterates over `ATTACKTechniqueDetail.kill_chain_phases` and calls this tool once per tactic. Each call produces independent `ControlMappingResult` records with distinct `tactic` values, distinct `tactic_risk_lens` values, and potentially different `item_id` sets. This is the fan-out pattern described in the redesign doc — it is the caller's responsibility, not this tool's.

---

### Tool 4 — `FrameworkItemIngestTool` *(setup only, not agent-facing)*

**File:** `app/agents/tools/framework_item_ingest.py`

**Role:** Populate `FrameworkCollections.ITEMS` for a given framework. Reads from the existing five framework collections and the `framework_items` Postgres table, joins on `item_id`, runs a one-shot LLM classifier to derive `tactic_domains` and `asset_types`, and upserts into `FrameworkCollections.ITEMS` via `get_vector_store_client().add_documents()`.

**Embedded text per document (the holistic embedding):**
```
{title}. {control_objective}. {risk_description}. {trigger}
```

All four fields concatenated. A semantic query for a `tactic_risk_lens` string finds the most relevant item across what the control requires, what breaks, and how it breaks — from a single similarity score.

**Upsert logic:** Delete existing point by `item_id` before re-inserting. Safe to re-run.

Not wrapped as a LangChain StructuredTool. Invoked directly from the ingest CLI. Run once per framework registration, and again when framework content changes.

---

## Full Dependency Map

```
get_vector_store_client()              ← existing factory, used by all new tools
        │
        ├──► ATTACKEnrichmentTool            (existing — fix kill_chain_phases gap only)
        │           │
        │           ▼
        │    TacticContextualiserTool         (NEW — Postgres + Qdrant cache)
        │           │
        │           ▼
        ├──► FrameworkItemRetrievalTool       (NEW — queries framework_items collection)
        │           │
        │           ▼
        │    AttackControlMappingTool         (NEW — orchestrates all + LLM mapping)
        │           │
        │           ▼
        │    MappingRepository               (existing — persists to attack_control_mappings)
        │
                └──► FrameworkItemIngestTool            (NEW — setup only, populates framework_items)
```

---

## Collection × Tool Access Matrix

| Collection | Registry Constant | Read by | Written by |
|---|---|---|---|
| `attack_techniques` | `AttackCollections.TECHNIQUES` | `ATTACKEnrichmentTool` (existing) | `ingest_stix_to_postgres` (existing) |
| `attack_tactic_contexts` | `AttackCollections.TACTIC_CONTEXTS` | `TacticContextualiserTool` (cache check) | `TacticContextualiserTool` (on miss) |
| `framework_controls` | `FrameworkCollections.CONTROLS` | `RetrievalService` (existing, unchanged) | Existing ingest |
| `framework_requirements` | `FrameworkCollections.REQUIREMENTS` | `RetrievalService` (existing, unchanged) | Existing ingest |
| `framework_risks` | `FrameworkCollections.RISKS` | `RetrievalService` (existing) + `FrameworkItemRetrievalTool` (fallback only) | Existing ingest |
| `framework_scenarios` | `FrameworkCollections.SCENARIOS` | `RetrievalService` (existing) + `FrameworkItemRetrievalTool` (fallback only) | Existing ingest |
| `framework_items` | `FrameworkCollections.ITEMS` | `FrameworkItemRetrievalTool` (primary path) | `FrameworkItemIngestTool` (setup) |

---

## What Does Not Change

| Component | Reason |
|---|---|
| `VectorStoreClient` ABC and all method signatures | Interface is sufficient as-is |
| `ChromaVectorStoreClient` — all methods | `normalize_filter` already handles lists correctly |
| `QdrantVectorStoreClient` — all methods except `normalize_filter` | `semantic_search` path via `DocumentQdrantStore` unchanged |
| `get_vector_store_client()` factory | New tools call it identically to existing code |
| All five existing `FrameworkCollections` constants | Read-only from new tools perspective |
| All `MDLCollections`, `XSOARCollections`, `LLMSafetyCollections` | Not involved |
| `ComprehensiveIndexingCollections` | Not involved |
| `ATTACKTechniqueTool` and its `SecurityTool` wrapper | Unchanged |
| `create_attack_technique_tool()` and `create_attack_enrichment_tool()` factories | Unchanged |
| `ATTACKEnrichInput` and `ATTACKTechniqueInput` schemas | Unchanged |
| `ingest_stix_to_postgres()` | Unchanged |
| All existing LangGraph nodes | Not touched |
| `prompts.py` | Already framework-parameterised — no changes needed |
| `Collections = _LegacyCollections` backward-compat alias | Untouched |
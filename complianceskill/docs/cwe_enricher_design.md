# CVE Enricher Redesign — CWE from DB + Stage Entry Points

> Use as `@cve_enricher_redesign.md` in Cursor when modifying:
> - `app/agents/tools/cve_enrichment.py`
> - `app/agents/tools/cve_attack_mapper.py`
> - `app/ingestion/attacktocve/batch_cve_enrich.py`
> - `indexing_cli/cve_enrich_pipeline.py`

---

## What changed and why

**Before:** Stage 2 (`_execute_cve_to_attack_map`) used a hardcoded Python list
(`CURATED_CWE_ATTACK` in `cwe_capec_attack_mapper.py`) as its CWE → technique
lookup. This was a static snapshot baked into source code.

**After:** Stage 2 queries `cwe_technique_mappings` from Postgres — a table
that is populated offline by `cwe_enrich.py` + `cwe_capec_attack_mapper.py`
using live data from NVD, CAPEC XML, MITRE ATT&CK TAXII, and CISA KEV. The
lookup is deterministic, always up to date, and shares one table with the
mapper — no duplication.

**Additionally:** The batch runner gains a `--start-stage` flag so you can
enter the pipeline at Stage 2 or Stage 3 when CVEs are already enriched,
avoiding redundant NVD API calls and LLM recomputation.

---

## Part 1 — CWE from DB in Stage 2

### Offline pipeline (run once, or on a schedule)

```
cwe_enrich.py                  →  fetches NVD, CWE API, CAPEC XML, ATT&CK TAXII, KEV
        │
        ▼
cwe_capec_attack_mapper.py     →  builds CWE → CAPEC → ATT&CK triples
        │
        ▼  persist_mappings_to_db()
        ├──▶ cwe_capec_attack_mappings   (full detail: capec_id, mapping_basis, example_cves)
        └──▶ cwe_technique_mappings      (lightweight: cwe_id, technique_id, tactic, confidence)
```

`cwe_technique_mappings` is the only table Stage 2 needs. It is already
populated by `persist_mappings_to_db()` in `cwe_capec_attack_mapper.py` —
no schema changes required.

### What changes in `_execute_cve_to_attack_map`

Replace the import of `CURATED_CWE_ATTACK` with a DB query function:

```python
# app/agents/tools/cve_attack_mapper.py

def _lookup_cwe_techniques(cwe_ids: list[str]) -> list[dict]:
    """
    Query cwe_technique_mappings for all (technique_id, tactic, confidence)
    rows matching the given CWE IDs. Returns empty list if table is empty
    or no match — caller falls through to LLM-only path.

    SELECT technique_id, tactic, confidence, mapping_source
    FROM   cwe_technique_mappings
    WHERE  cwe_id = ANY(:cwe_ids)
    ORDER BY confidence DESC
    """
    from app.storage.sqlalchemy_session import get_security_intel_session
    from sqlalchemy import text

    if not cwe_ids:
        return []

    try:
        with get_security_intel_session("cve_attack") as session:
            rows = session.execute(
                text("""
                    SELECT technique_id, tactic, confidence, mapping_source
                    FROM   cwe_technique_mappings
                    WHERE  cwe_id = ANY(:cwe_ids)
                    ORDER BY confidence DESC
                """),
                {"cwe_ids": cwe_ids},
            ).fetchall()
        return [dict(r._mapping) for r in rows]
    except Exception as e:
        logger.warning(f"cwe_technique_mappings lookup failed: {e}. Falling back to LLM-only.")
        return []
```

Stage 2 logic after the change:

```python
def _execute_cve_to_attack_map(
    cve_id: str,
    cve_detail: dict,
    frameworks: list[str],
) -> list[dict]:
    cwe_ids = cve_detail.get("cwe_ids") or []

    # Step 1: deterministic DB lookup (fast, no LLM)
    db_candidates = _lookup_cwe_techniques(cwe_ids)

    # Step 2: LLM refines/augments the candidate set
    #   - Pass db_candidates as the "seed" list
    #   - LLM confirms, rejects, adds technique IDs the CWE lookup misses
    #   - If db_candidates is empty, LLM runs from scratch (same as before)
    mappings = _llm_refine_attack_mappings(
        cve_id=cve_id,
        cve_detail=cve_detail,
        candidates=db_candidates,
    )

    # Step 3: Persist to cve_attack_mapping
    _persist_attack_mappings(cve_id, mappings)
    return mappings
```

### Fallback chain — never hard-fail Stage 2

```
1. cve_attack_mapping (Postgres)    ← existing rows for this CVE? return immediately, no LLM
2. cwe_technique_mappings (Postgres) ← DB lookup for CWE IDs from cve_detail
3. LLM from scratch                  ← no CWE match in DB, or DB query failed
```

Step 1 is the existing cache check that should already be in place (see
`cve_enricher_design.md`). Step 2 is new. Step 3 is unchanged.

### Null/empty guard

If `cve_detail["cwe_ids"]` is empty (NVD returned no CWE for this CVE — common
for older CVEs), skip the DB lookup entirely and go straight to LLM. Do not
query with an empty list.

---

## Part 2 — Stage entry points (`--start-stage`)

### New parameter

```python
# enrich_cves_from_csv signature change
def enrich_cves_from_csv(
    ...
    start_stage: int = 1,   # NEW: 1 | 2 | 3
    ...
)
```

```bash
# CLI flags — add to cve_enrich_pipeline.py argparse
--start-stage {1,2,3}     Start from stage 1 (default), 2, or 3
                           Stage 2: reads cve_intelligence, skips NVD
                           Stage 3: reads cve_attack_mapping, skips NVD + LLM S2
```

### What each entry point loads

#### `--start-stage 1` (default — unchanged)

No change. Full pipeline: NVD pre-fetch → Stage 1 → Stage 2 → Stage 3.

#### `--start-stage 2`

Skip Stage 1. Load `cve_detail` for each CVE directly from `cve_intelligence`.

```python
def _load_cve_detail_from_db(cve_id: str) -> dict | None:
    """
    SELECT * FROM cve_intelligence WHERE cve_id = :cve_id
    Returns None if not found (caller should warn and skip).
    """
    from app.storage.sqlalchemy_session import get_security_intel_session
    from sqlalchemy import text

    with get_security_intel_session("cve_attack") as session:
        row = session.execute(
            text("SELECT * FROM cve_intelligence WHERE cve_id = :cve_id"),
            {"cve_id": cve_id},
        ).fetchone()
    if row is None:
        return None
    r = dict(row._mapping)
    # Normalise array columns (stored as TEXT[] in Postgres, returned as list)
    r["cwe_ids"]          = r.get("cwe_ids") or []
    r["affected_products"] = r.get("affected_products") or []
    r["technique_ids"]    = r.get("technique_ids") or []
    r["tactics"]          = r.get("tactics") or []
    return r
```

In the batch row loop when `start_stage == 2`:

```python
if start_stage >= 2:
    cve_detail = _load_cve_detail_from_db(cve_id_norm)
    if cve_detail is None:
        logger.warning(f"[start-stage 2] {cve_id_norm} not in cve_intelligence — skipping")
        summary["failed"] += 1
        continue
    # skip NVD pre-fetch entirely — Phase 1 block does not run
```

#### `--start-stage 3`

Skip Stage 1 and Stage 2. Load existing technique/tactic triples from
`cve_attack_mapping` for each CVE. Feed them directly into the two-pass
Stage 3 de-duplication block.

```python
def _load_attack_mappings_from_db(cve_id: str) -> list[dict]:
    """
    SELECT attack_technique_id AS technique_id,
           attack_tactic_slug  AS tactic,
           confidence_score    AS confidence
    FROM   cve_attack_mapping
    WHERE  cve_id = :cve_id
    """
    from app.storage.sqlalchemy_session import get_security_intel_session
    from sqlalchemy import text

    with get_security_intel_session("cve_attack") as session:
        rows = session.execute(
            text("""
                SELECT attack_technique_id AS technique_id,
                       attack_tactic_slug  AS tactic,
                       confidence_score    AS confidence,
                       cvss_score, epss_score, attack_vector,
                       cwe_ids, exploit_available, exploit_maturity
                FROM   cve_attack_mapping
                WHERE  cve_id = :cve_id
            """),
            {"cve_id": cve_id},
        ).fetchall()
    return [dict(r._mapping) for r in rows]
```

In the batch row loop when `start_stage == 3`:

```python
if start_stage >= 3:
    mappings = _load_attack_mappings_from_db(cve_id_norm)
    if not mappings:
        logger.warning(f"[start-stage 3] {cve_id_norm} not in cve_attack_mapping — skipping")
        summary["failed"] += 1
        continue
    # cve_detail is still needed for Stage 3 context — load from cve_intelligence
    cve_detail = _load_cve_detail_from_db(cve_id_norm) or {}
    stage2_results[cve_id_norm] = mappings
    # skip Stage 2 block entirely
```

---

## Part 3 — Two-pass execution (applies to all entry points)

This is the fix for the 17-hour batch time. Applies regardless of which
`--start-stage` you use.

### Pass 1: collect all CVE → technique/tactic triples

For every CVE in the batch:
1. Load or compute `cve_detail` (Stage 1 or DB load, depending on `start_stage`)
2. Load or compute `mappings` (Stage 2 or DB load, depending on `start_stage`)
3. Store in `stage2_results: dict[str, list[dict]]` — no Stage 3 yet

```python
stage2_results: dict[str, list[dict]] = {}

for cve_id_norm in all_cve_ids:
    if start_stage == 3:
        mappings = _load_attack_mappings_from_db(cve_id_norm)
    else:
        cve_detail = _load_or_fetch_cve_detail(cve_id_norm, start_stage, ...)
        mappings = _load_or_run_stage2(cve_id_norm, cve_detail, frameworks, ...)
    stage2_results[cve_id_norm] = mappings
```

### De-duplicate across all CVEs

```python
all_triples: set[tuple[str, str, str]] = set()
for mappings in stage2_results.values():
    for m in mappings:
        for fw in frameworks:
            all_triples.add((m["technique_id"], m["tactic"], fw))
```

### Check existing rows before running Stage 3

```python
def _get_existing_control_mappings(
    technique_id: str, tactic: str, framework_id: str
) -> list[dict]:
    """
    SELECT item_id, relevance_score, confidence, framework_id
    FROM   attack_control_mappings
    WHERE  technique_id = :technique_id
      AND  tactic       = :tactic
      AND  framework_id = :framework_id
    """
    ...
```

```python
triple_cache: dict[tuple, list[dict]] = {}
triples_to_run: list[tuple] = []

for triple in all_triples:
    existing = _get_existing_control_mappings(*triple)
    if existing:
        triple_cache[triple] = existing      # reuse — zero LLM calls
    else:
        triples_to_run.append(triple)
```

### Pass 2: run Stage 3 only for new triples

```python
for technique_id, tactic, fw in triples_to_run:
    results = _execute_attack_control_map(
        technique_id=technique_id,
        tactic=tactic,
        framework_id=fw,
        persist=True,
    )
    triple_cache[(technique_id, tactic, fw)] = results
```

### Assemble per-CVE output from triple_cache

```python
for cve_id_norm, mappings in stage2_results.items():
    controls = []
    for m in mappings:
        for fw in frameworks:
            controls.extend(triple_cache.get((m["technique_id"], m["tactic"], fw), []))
    # write to output_rows
```

Stage 3 LLM calls drop from `N_cves × avg_techniques × N_frameworks` to
`unique_new_triples`. For 440 CVEs sharing ~50 unique technique/tactic pairs,
this is ~4,400 LLM chains → ~60 on first run, ~0 on subsequent runs.

---

## Files changed

| File | Change |
|---|---|
| `app/agents/tools/cve_attack_mapper.py` | Add `_lookup_cwe_techniques()`, wire into `_execute_cve_to_attack_map` as Step 1 before LLM |
| `app/agents/tools/cve_attack_mapper.py` | Add `_get_existing_control_mappings()` for triple cache check |
| `app/agents/tools/cve_enrichment.py` | Add `_load_cve_detail_from_db()` for `start_stage >= 2` |
| `app/agents/tools/cve_attack_mapper.py` | Add `_load_attack_mappings_from_db()` for `start_stage >= 3` |
| `app/ingestion/attacktocve/batch_cve_enrich.py` | Add `start_stage: int = 1` param; add two-pass logic; add `_load_or_fetch_cve_detail()` and `_load_or_run_stage2()` dispatch helpers |
| `indexing_cli/cve_enrich_pipeline.py` | Add `--start-stage` argparse flag; pass to `enrich_cves_from_csv` |
| `app/ingestion/cwe_threat_intel/cwe_capec_attack_mapper.py` | No changes — `persist_mappings_to_db()` already writes `cwe_technique_mappings` |

---

## Dispatch helpers (implement in batch_cve_enrich.py)

These two functions hide the `start_stage` branching from the main loop:

```python
def _load_or_fetch_cve_detail(
    cve_id: str,
    start_stage: int,
    epss_lookup: dict,
    kev_lookup: set,
    nvd_lookup: dict,
    skip_nvd_fetch: bool,
) -> dict:
    """Return cve_detail from DB (start_stage>=2) or via live fetch (start_stage=1)."""
    if start_stage >= 2:
        detail = _load_cve_detail_from_db(cve_id)
        if detail is None:
            raise CVENotFoundError(f"{cve_id} not in cve_intelligence; run Stage 1 first")
        return detail
    # start_stage == 1: use existing enrichment tool
    from app.agents.tools.cve_enrichment import _execute_cve_enrich
    return _execute_cve_enrich(
        cve_id,
        epss_lookup=epss_lookup,
        kev_lookup=kev_lookup,
        nvd_lookup=nvd_lookup,
        skip_nvd_fetch=skip_nvd_fetch,
    )


def _load_or_run_stage2(
    cve_id: str,
    cve_detail: dict,
    frameworks: list[str],
    start_stage: int,
) -> list[dict]:
    """Return mappings from DB (start_stage>=3) or via Stage 2 (start_stage<=2)."""
    if start_stage >= 3:
        mappings = _load_attack_mappings_from_db(cve_id)
        if not mappings:
            raise ValueError(f"{cve_id} not in cve_attack_mapping; run Stage 2 first")
        return mappings
    # start_stage <= 2: check DB cache first, then run Stage 2
    from app.agents.tools.cve_attack_mapper import (
        _get_existing_attack_mappings,
        _execute_cve_to_attack_map,
    )
    existing = _get_existing_attack_mappings(cve_id)
    if existing:
        return existing
    return _execute_cve_to_attack_map(cve_id, cve_detail, frameworks)
```

---

## Prerequisite checklist before running with `--start-stage 2` or `--start-stage 3`

| Prerequisite | How to verify |
|---|---|
| `cwe_technique_mappings` populated | `SELECT COUNT(*) FROM cwe_technique_mappings` → should be > 0 |
| `cve_intelligence` populated for target CVEs | `SELECT COUNT(*) FROM cve_intelligence WHERE cve_id = ANY('{...}')` |
| `cve_attack_mapping` populated for target CVEs | `SELECT COUNT(*) FROM cve_attack_mapping WHERE cve_id = ANY('{...}')` |
| `framework_items` (Qdrant) populated | Required for Stage 3 regardless of start stage |

If `cve_intelligence` is missing rows when using `--start-stage 2`, those CVEs
are logged as failed and skipped — they do not cause the batch to abort. Same
pattern for `--start-stage 3` with `cve_attack_mapping`.

---

## CLI usage examples

```bash
# Full pipeline (unchanged behaviour)
python -m indexing_cli.cve_enrich_pipeline -i cves.csv -o out.csv

# Skip NVD, use already-enriched cve_intelligence for Stage 1 data
python -m indexing_cli.cve_enrich_pipeline -i cves.csv -o out.csv --start-stage 2

# Skip NVD + Stage 2 LLM entirely, only run Stage 3 control mapping
python -m indexing_cli.cve_enrich_pipeline -i cves.csv -o out.csv --start-stage 3

# Stage 3 only, specific frameworks
python -m indexing_cli.cve_enrich_pipeline -i cves.csv -o out.csv \
  --start-stage 3 --frameworks nist_800_53r5

# Stage 3 only, background mode
python -m indexing_cli.cve_enrich_pipeline -i cves.csv -o out.csv \
  --start-stage 3 --background
```

---

## Error handling additions

| Condition | Behaviour |
|---|---|
| `--start-stage 2` but CVE not in `cve_intelligence` | Log WARNING, mark failed, skip — do not abort batch |
| `--start-stage 3` but CVE not in `cve_attack_mapping` | Log WARNING, mark failed, skip — do not abort batch |
| `cwe_technique_mappings` empty (offline pipeline not run yet) | Log WARNING once at batch start; Stage 2 proceeds with LLM-only path |
| `_get_existing_control_mappings` query fails | Log WARNING; treat as cache miss; run Stage 3 LLM for that triple |s
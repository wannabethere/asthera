# CVE Enrichment Pipeline — Design Reference

> Use this file as a Cursor context document (`@cve_enrichment_design.md`) when
> modifying `cve_enrichment.py`, `batch_cve_enrich.py`, `cve_enrich_pipeline.py`,
> or `attack_enrichment.py`.

---

## Architecture overview

Three-stage pipeline. Every stage has a deterministic fallback before LLM is
invoked. Postgres is the source of truth; Qdrant is the semantic retrieval layer;
NVD/EPSS/KEV are external data sources that are always cached after first fetch.

```
CSV (cve_id list)
    │
    ▼
[ Stage 1 — CVE Enrichment ]           cve_enrichment.py
  cache-aside: cve_cache → cve_intelligence → NVD API
  writes → cve_intelligence, cve_cache
    │
    ▼
[ Stage 2 — CVE → ATT&CK ]             cve_attack_mapper.py
  deterministic: cwe_technique_mappings lookup (no LLM)
  refinement:    LLM confirms/augments candidates
  writes → cve_attack_mapping
    │
    ▼
[ Stage 3 — ATT&CK → Control ]         attack_control_mapping.py
  TacticContextualiserTool → tactic_risk_lens
  FrameworkItemRetrievalTool → Qdrant (framework_items)
  AttackControlMappingTool  → LLM → attack_control_mappings
    │
    ▼
[ Output ]
  cve_enriched.csv  (batch)  /  result.json  (single)
```

---

## Stage 1 — CVE Enrichment (`_execute_cve_enrich`)

### Resolution order — strict, no skipping

```
1. cve_cache (Postgres)          TTL = 7 days, source = 'seed' | 'nvd' | 'circl'
2. cve_intelligence (Postgres)   from a previous enrichment run → rebuild cache entry
3. NVD API 2.0                   primary live source
4. FIRST EPSS API                augment CVSS; call only if NVD fetch succeeds
5. CIRCL CVE-Search              fallback if NVD returns 429 after retries
```

**Rule:** never fall through to the next source unless the current one returns
empty or raises. A partial NVD response (missing EPSS) is NOT a miss — augment
with EPSS separately and persist.

### NVD rate limiter — shared singleton

```python
# module-level in cve_enrichment.py
_nvd_rate_limiter = TokenBucketRateLimiter(
    capacity   = int(os.getenv("NVD_RATE_LIMIT", "5")),   # 5 without key, 50 with
    refill_per = 30,   # seconds
)

# NVD_API_KEY presence doubles effective throughput — read from env, never hardcode
NVD_HEADERS = {"apiKey": os.getenv("NVD_API_KEY")} if os.getenv("NVD_API_KEY") else {}
```

**Token bucket rules:**
- Capacity: `5` (no API key) · `50` (with API key) per 30-second window
- Acquire 1 token before every NVD HTTP call
- Block (sleep) if no token available — do NOT raise, do NOT skip
- Retry on 429 with exponential backoff: `10s → 20s → 40s`, then raise

**Rate limiter implementation skeleton:**

```python
import time, threading

class TokenBucketRateLimiter:
    def __init__(self, capacity: int, refill_per: float):
        self._capacity   = capacity
        self._tokens     = float(capacity)
        self._refill_per = refill_per          # seconds per full refill
        self._rate       = capacity / refill_per  # tokens per second
        self._lock       = threading.Lock()
        self._last       = time.monotonic()

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            self._last = now
            if self._tokens < 1:
                wait = (1 - self._tokens) / self._rate
                time.sleep(wait)
                self._tokens = 0.0
            else:
                self._tokens -= 1.0
```

### Write-through — always dual-write on a live NVD fetch

```python
# Inside _execute_cve_enrich, after successful NVD + EPSS merge:
with db.transaction():
    db.upsert("cve_intelligence", cve_record)   # full enrichment row
    db.upsert("cve_cache", {                    # NVD + EPSS + KEV blobs
        "cve_id":     cve_id,
        "nvd_data":   nvd_blob,
        "epss_data":  epss_blob,
        "kev_data":   kev_blob,
        "expires_at": now() + timedelta(days=7),
        "source":     "nvd",
    })
```

**ON CONFLICT strategy:** `DO UPDATE SET` — never `DO NOTHING` on a live fetch,
because the row may be a stale seed entry that needs refreshing.

### `CVEDetail` return shape (contract for Stage 2)

```python
@dataclass
class CVEDetail:
    cve_id:              str
    description:         str
    cvss_score:          float
    cvss_vector:         str
    attack_vector:       str          # "network"|"adjacent"|"local"|"physical"
    attack_complexity:   str          # "low"|"high"
    privileges_required: str          # "none"|"low"|"high"
    cwe_ids:             list[str]    # ["CWE-77", ...]
    affected_products:   list[str]
    epss_score:          float        # 0.0–1.0
    exploit_available:   bool
    exploit_maturity:    str          # "none"|"poc"|"weaponised"
    kev_listed:          bool
    published_date:      str          # ISO date
    last_modified:       str          # ISO date
```

Never return `None` from `_execute_cve_enrich` — raise `CVENotFoundError` so
callers can log and move on cleanly.

---

## Stage 1 batch runner (`batch_cve_enrich.py` + `cve_enrich_pipeline.py`)

### Three additions required

#### 1 — Checkpoint manager

Prevents re-fetching CVEs already enriched in a previous interrupted run.

```python
import json, os
from pathlib import Path

class CheckpointManager:
    def __init__(self, path: str = ".cve_batch_checkpoint.json"):
        self._path = Path(path)
        self._done: set[str] = set()
        if self._path.exists():
            self._done = set(json.loads(self._path.read_text()).get("done", []))

    def is_done(self, cve_id: str) -> bool:
        return cve_id in self._done

    def mark_done(self, cve_id: str) -> None:
        self._done.add(cve_id)
        self._path.write_text(json.dumps({"done": list(self._done)}, indent=2))

    def clear(self) -> None:
        self._path.unlink(missing_ok=True)
        self._done.clear()
```

**Usage in the row loop:**

```python
ckpt = CheckpointManager()
for row in rows:
    cve_id = row[col].strip()
    if ckpt.is_done(cve_id):
        continue          # skip — already in Postgres from a prior run
    try:
        enriched = _enrich_single(cve_id, epss_lookup, kev_lookup, ...)
        ckpt.mark_done(cve_id)
    except Exception as e:
        logger.warning(f"Failed {cve_id}: {e}")
```

#### 2 — EPSS + KEV pre-fetch (once per batch run)

Download EPSS and KEV **once** at the top of the batch, not per CVE. This
eliminates ~4,000 extra API calls for a 2,104-CVE batch.

```python
def _prefetch_epss() -> dict[str, float]:
    """Returns {cve_id: epss_score} for all current CVEs."""
    import gzip, csv, io, requests
    url = "https://epss.cyentia.com/epss_scores-current.csv.gz"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    with gzip.open(io.BytesIO(r.content), "rt") as f:
        reader = csv.DictReader(f)
        return {row["cve"]: float(row["epss"]) for row in reader}

def _prefetch_kev() -> set[str]:
    """Returns set of CVE IDs in CISA KEV."""
    import requests
    url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    data = requests.get(url, timeout=30).json()
    return {v["cveID"] for v in data.get("vulnerabilities", [])}
```

**Pass both dicts into `_enrich_single` as keyword args:**

```python
# Top of batch run — once
epss_lookup = _prefetch_epss()
kev_lookup  = _prefetch_kev()

# Each row
enriched = _enrich_single(
    cve_id,
    full_pipeline=full_pipeline,
    frameworks=frameworks,
    epss_lookup=epss_lookup,    # NEW
    kev_lookup=kev_lookup,      # NEW
)
```

**Inside `_enrich_single`:** read `epss_lookup.get(cve_id, 0.0)` and
`cve_id in kev_lookup` to augment the NVD response before persisting. Do NOT
call EPSS or KEV APIs individually inside this function.

#### 3 — Rate limiter integration (transparent)

The `TokenBucketRateLimiter` singleton lives in `cve_enrichment.py`. Import and
acquire it at the top of every NVD HTTP call. The batch loop does not need to
know about it — rate limiting is the tool's responsibility, not the caller's.

---

## Seed execution order

Run exactly once before the first full batch enrichment. Steps 1–3 are
prerequisites; steps 4–6 are the new batch warm-up sequence.

| # | Script / command | What it populates | Blocking? |
|---|---|---|---|
| 1 | `migrate_schema.sql` | All tables | ✅ Hard prerequisite |
| 2 | `seed_cve_2024_2025.sql` (section 1) | `cwe_technique_mappings` | ✅ Required before Stage 2 |
| 3 | `FrameworkItemIngestTool.run(framework_id)` × N frameworks | `framework_items` (Postgres + Qdrant) | ✅ Required before Stage 3 |
| 4 | `_prefetch_epss()` + `_prefetch_kev()` | In-memory dicts for the batch run | Run at batch start |
| 5 | `batch_cve_enrich.py` Stage 1 only across all 2,104 CVEs | `cve_intelligence` + `cve_cache` | Warm-up run — no LLM |
| 6 | `seed_cve_2024_2025.sql` (sections 2–5) | `cve_attack_mapping`, `cpe_dictionary`, `cve_cpe_affected`, `cve_cache` for 15 seeded CVEs | Optional — kept for deterministic test data |
| 7 | `cve_enrich_pipeline.py` full pipeline | All Stage 2 + 3 tables | Production run |

**Timing estimates for step 5:**

| NVD API key? | Effective rate | Time for 2,104 CVEs |
|---|---|---|
| No | 5 req / 30s | ~3.5 hours |
| Yes | 50 req / 30s | ~21 minutes |

Get a free NVD API key at `https://nvd.nist.gov/developers/request-an-api-key`.
Set it as `NVD_API_KEY` in your `.env` before running step 5.

---

## `cwe_technique_mappings` — coverage gaps to fix

The seed file covers the most common CWEs. The following CWEs appear in the
2,104-CVE batch but are NOT in the current seed — add them to
`seed_cve_2024_2025.sql` section 1 before running Step 2:

| CWE | Description | Technique | Tactic | Confidence |
|---|---|---|---|---|
| `CWE-787` | Out-of-bounds write | `T1203` | `execution` | `high` |
| `CWE-787` | Out-of-bounds write | `T1190` | `initial-access` | `medium` |
| `CWE-362` | Race condition | `T1203` | `execution` | `medium` |
| `CWE-362` | Race condition | `T1068` | `privilege-escalation` | `medium` |
| `CWE-200` | Info exposure | `T1005` | `collection` | `high` |
| `CWE-20`  | Improper input validation | `T1190` | `initial-access` | `medium` |
| `CWE-863` | Incorrect authorisation | `T1078` | `initial-access` | `high` |
| `CWE-863` | Incorrect authorisation | `T1068` | `privilege-escalation` | `medium` |
| `CWE-400` | Resource exhaustion | `T1499` | `impact` | `high` |
| `CWE-611` | XXE | `T1005` | `collection` | `high` |
| `CWE-611` | XXE | `T1083` | `discovery` | `medium` |
| `CWE-601` | Open redirect | `T1566.002` | `initial-access` | `medium` |
| `CWE-306` | Missing auth (already seeded) | confirm present | — | — |

For any CVE whose CWE is not in `cwe_technique_mappings`, Stage 2 falls back
entirely to LLM mapping — this is valid but slower and less deterministic. The
CWE lookup is the high-confidence fast path.

---

## `framework_items` prerequisite

`FrameworkItemRetrievalTool` in Stage 3 queries the `framework_items` Qdrant
collection. If it is empty, the tool falls back to `framework_risks` +
`framework_scenarios` — lower quality retrieval.

Run `FrameworkItemIngestTool` for every framework you intend to map controls
against, **before** any Stage 3 call:

```bash
# Example call — adapt to your CLI entry point
python -m indexing_cli.framework_ingest --framework cis_v8_1
python -m indexing_cli.framework_ingest --framework nist_800_53r5
```

`framework_items` schema (reference):

```
framework_items (
    item_id         TEXT PRIMARY KEY,   -- e.g. "CIS-RISK-012"
    framework_id    TEXT NOT NULL,      -- "cis_v8_1" | "nist_800_53r5" | ...
    tactic          TEXT,               -- ATT&CK tactic slug for pre-filtering
    title           TEXT NOT NULL,
    description     TEXT,
    embedding       VECTOR(1536),       -- pre-computed; Qdrant also holds this
    created_at      TIMESTAMPTZ DEFAULT NOW()
)
```

---

## Key table contracts (do not break these interfaces)

### `cve_intelligence` — written by Stage 1, read by Stage 2

```sql
cve_intelligence (
    cve_id              TEXT PRIMARY KEY,
    description         TEXT,
    cvss_score          NUMERIC(4,2),
    cvss_vector         TEXT,
    attack_vector       TEXT,
    attack_complexity   TEXT,
    privileges_required TEXT,
    cwe_ids             TEXT[],
    affected_products   TEXT[],
    epss_score          NUMERIC(5,4),
    exploit_available   BOOLEAN,
    exploit_maturity    TEXT,           -- 'none' | 'poc' | 'weaponised'
    kev_listed          BOOLEAN,
    published_date      DATE,
    last_modified       DATE,
    technique_ids       TEXT[],         -- filled by Stage 2 back-write
    tactics             TEXT[]          -- filled by Stage 2 back-write
)
```

### `cve_cache` — cache layer, 7-day TTL

```sql
cve_cache (
    cve_id      TEXT PRIMARY KEY,
    nvd_data    JSONB,
    epss_data   JSONB,
    kev_data    JSONB,
    expires_at  TIMESTAMPTZ,
    source      TEXT        -- 'seed' | 'nvd' | 'circl'
)
```

### `cve_attack_mapping` — written by Stage 2, read by Stage 3

```sql
cve_attack_mapping (
    cve_id              TEXT NOT NULL,
    attack_technique_id TEXT NOT NULL,
    attack_tactic_name  TEXT,
    attack_tactic_slug  TEXT,
    mapping_source      TEXT,           -- 'mitre_official' | 'ai_inferred' | 'cwe_lookup'
    confidence_score    NUMERIC(4,2),
    cvss_score          NUMERIC(4,2),
    epss_score          NUMERIC(5,4),
    attack_vector       TEXT,
    cwe_ids             TEXT[],
    exploit_available   BOOLEAN,
    exploit_maturity    TEXT,
    notes               TEXT,
    PRIMARY KEY (cve_id, attack_technique_id)
)
```

---

## Error handling contracts

| Condition | Behaviour |
|---|---|
| NVD returns 404 for a CVE ID | Raise `CVENotFoundError(cve_id)` — log, skip row, write error to output CSV |
| NVD returns 429 after 3 retries | Raise `NVDRateLimitError` — batch runner should pause 60s then resume |
| `cwe_technique_mappings` has no entry for a CWE | Fall through to LLM Stage 2 — log as `WARNING`, not error |
| `framework_items` Qdrant collection is empty | Fall through to `framework_risks` + `framework_scenarios` — log as `WARNING` |
| Stage 3 control mapping LLM call fails | Log warning, skip that `(technique, tactic, framework)` triple, continue |
| Checkpoint file corrupted / unreadable | Log error, start fresh (do not abort batch) |

---

## Output CSV columns (batch mode)

Produced by `_result_to_csv_row` in `cve_enrich_pipeline.py`.
Do not rename or remove existing columns — downstream consumers depend on them.

**Stage 1 columns (always present):**

| Column | Source |
|---|---|
| `cve_id` | input |
| `description` | NVD |
| `cvss_score` | NVD |
| `cvss_vector` | NVD |
| `attack_vector` | NVD |
| `attack_complexity` | NVD |
| `privileges_required` | NVD |
| `cwe_ids` | NVD · pipe-separated |
| `affected_products` | NVD · pipe-separated · max 500 chars |
| `epss_score` | EPSS bulk |
| `exploit_available` | EPSS / KEV |
| `exploit_maturity` | derived |
| `published_date` | NVD |
| `last_modified` | NVD |

**Stage 2 columns (present when `--full-pipeline` or `cve_enrich_pipeline.py`):**

| Column | Source |
|---|---|
| `technique_ids` | Stage 2 · pipe-separated |
| `tactics` | Stage 2 · pipe-separated |
| `technique_tactic_pairs` | Stage 2 · `T1190:initial-access` format · pipe-separated |
| `attack_mapping_count` | Stage 2 |
| `attack_mappings_json` | Stage 2 · JSON array · rationale truncated at 200 chars |

**Stage 3 columns (present in `cve_enrich_pipeline.py` only):**

| Column | Source |
|---|---|
| `control_mapping_count` | Stage 3 |
| `controls_cis_v8_1` | Stage 3 · pipe-separated · max 50 items |
| `controls_nist_800_53r5` | Stage 3 · pipe-separated · max 50 items |

**Error columns:**

| Column | When |
|---|---|
| `enrichment_error` | Stage 1 failure |
| `attack_mapping_error` | Stage 2 failure (`batch_cve_enrich.py` only) |

---

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `NVD_API_KEY` | No | — | NVD API key — increases rate limit from 5 to 50 req/30s |
| `NVD_RATE_LIMIT` | No | `5` | Override token bucket capacity (set to `50` if key is set) |
| `DATABASE_URL` | Yes | — | Postgres connection string |
| `QDRANT_URL` | Yes | — | Qdrant host URL |
| `QDRANT_API_KEY` | No | — | Qdrant API key (if cloud-hosted) |
| `OPENAI_API_KEY` | Yes | — | LLM for Stage 2 + Stage 3 |

---

## Files changed by this design

| File | Change type |
|---|---|
| `app/agents/tools/cve_enrichment.py` | Add `TokenBucketRateLimiter`, fix resolution order, add write-through dual-persist |
| `app/ingestion/attacktocve/batch_cve_enrich.py` | Add `CheckpointManager`, `_prefetch_epss`, `_prefetch_kev`, wire into row loop |
| `indexing_cli/cve_enrich_pipeline.py` | Wire EPSS/KEV pre-fetch; checkpoint integration for batch mode |
| `db/seeds/seed_cve_2024_2025.sql` | Extend `cwe_technique_mappings` with missing CWEs (section 1) |
| `app/agents/tools/attack_enrichment.py` | No changes — re-export shim only |



Found it. There are **4 compounding problems** in the code. The math explains exactly where those 17 hours went.

---

## Root cause breakdown

### Problem 1 — Stage 3 runs per CVE, not per unique technique (the main killer)

Lines 212–225 run `_execute_attack_control_map` inside the per-CVE loop. Stage 3 is 3 chained LLM calls per `(technique, tactic, framework)` triple. The same triple gets computed fresh for every CVE that maps to it.

```
440 CVEs × ~5 techniques avg × 2 frameworks = 4,400 Stage 3 LLM chains
```

T1190 (`initial-access`) appears in the majority of your CVEs. If 300 CVEs map to it, you're running `(T1190, initial-access, cis_v8_1)` **300 times** instead of once. At ~8s per triple (TacticContextualiser + FrameworkItemRetrieval + AttackControlMapping):

```
4,400 triples × 8s = ~10 hours
```

### Problem 2 — No check against existing `attack_control_mappings` rows

Before calling the LLM, the code never queries whether `(technique_id, tactic, framework_id)` already has rows in `attack_control_mappings`. On a second run it recomputes everything from scratch even if 90% is already persisted.

### Problem 3 — Checkpoint writes on every single CVE

Line 443: `ckpt.mark_done(cve_id_norm)` rewrites the entire JSON file after every CVE. That's 440 serialise-and-write operations. Minor on its own but compounds with Problem 4.

### Problem 4 — Incremental CSV rewrite rewrites the entire file

Lines 467–473: every `progress_interval` CVEs (default 25), the code rewrites **the entire output CSV from scratch**. At 440 CVEs with interval=25, that's 17 full rewrites of a growing file. At 350 rows × 25 columns, each rewrite is small, but the pattern is wrong — it should append, not rewrite.

---

## The fix — 3 surgical changes

### Fix 1 — De-duplicate Stage 3 across the entire batch (fixes ~10 hours)

Collect all unique `(technique_id, tactic, framework_id)` triples **before the row loop** and check `attack_control_mappings` first. Run the LLM only for triples with no existing rows, then reuse results in the per-CVE loop via an in-memory dict.

```python
# BEFORE the row loop in enrich_cves_from_csv:

from app.agents.tools.attack_control_mapping import (
    _execute_attack_control_map,
    _get_existing_control_mappings,  # new helper — SELECT from attack_control_mappings
)

# --- Collect all unique triples after Stage 2 is done for all CVEs --------
# First pass: Stage 1 + Stage 2 only (no Stage 3 yet)
stage2_results: Dict[str, List[Dict]] = {}  # cve_id → mappings
for row in rows:
    cve_id = ...
    if already_done: continue
    cve_detail = _execute_cve_enrich(...)
    mappings   = _execute_cve_to_attack_map(...)
    stage2_results[cve_id] = mappings

# De-duplicate triples across all CVEs
all_triples: set[tuple] = set()
for mappings in stage2_results.values():
    for m in mappings:
        for fw in frameworks:
            all_triples.add((m["technique_id"], m["tactic"], fw))

# Check which triples already have rows in attack_control_mappings
triple_cache: Dict[tuple, List[Dict]] = {}
triples_to_run = []
for triple in all_triples:
    existing = _get_existing_control_mappings(*triple)  # SELECT WHERE technique_id=... AND tactic=... AND framework_id=...
    if existing:
        triple_cache[triple] = existing      # reuse — no LLM call
    else:
        triples_to_run.append(triple)

# Run Stage 3 only for NEW triples
for technique_id, tactic, fw in triples_to_run:
    results = _execute_attack_control_map(technique_id, tactic, fw, persist=True)
    triple_cache[(technique_id, tactic, fw)] = results

# Second pass: assemble per-CVE results from triple_cache (no LLM calls)
for cve_id, mappings in stage2_results.items():
    controls = []
    for m in mappings:
        for fw in frameworks:
            controls.extend(triple_cache.get((m["technique_id"], m["tactic"], fw), []))
    # write to output_rows
```

For 440 CVEs sharing a common pool of ~30–50 unique technique/tactic pairs, Stage 3 drops from 4,400 LLM chains to **~60–100 on the first run, and ~0 on subsequent runs**.

### Fix 2 — Stage 2 cache check against `cve_attack_mapping`

Before calling `_execute_cve_to_attack_map`, check if mappings already exist for this CVE:

```python
# In _enrich_single, Stage 2 block:
from app.agents.tools.cve_attack_mapper import _get_existing_attack_mappings

existing_mappings = _get_existing_attack_mappings(cve_id_norm)  # SELECT FROM cve_attack_mapping WHERE cve_id=...
if existing_mappings:
    mappings = existing_mappings    # skip LLM entirely
else:
    mappings = _execute_cve_to_attack_map(cve_id_norm, cve_detail, frameworks)
```

### Fix 3 — Checkpoint batch write + CSV append

```python
# Batch checkpoint writes — only flush every 25 CVEs
_ckpt_buffer: List[str] = []

def _flush_checkpoint(ckpt, buffer):
    for cid in buffer:
        ckpt._done.add(cid)
    ckpt._path.write_text(json.dumps({"done": sorted(ckpt._done)}, indent=2))
    buffer.clear()

# In the row loop:
_ckpt_buffer.append(cve_id_norm)
if len(_ckpt_buffer) >= 25:
    _flush_checkpoint(ckpt, _ckpt_buffer)

# Replace the every-N full CSV rewrite with a single write at the end.
# Remove lines 467-473 entirely — the final write at lines 475-480 is sufficient.
```

---

## Expected time after fixes

| Stage | Before | After fix |
|---|---|---|
| NVD pre-fetch (440 CVEs, with API key) | ~5 min | ~5 min (unchanged) |
| Stage 2 LLM (440 CVEs, cache cold) | ~22 min | ~22 min first run, **~0 on resume** |
| Stage 3 LLM (4,400 triples → ~60 unique) | **~10 hours** | **~8 min first run, ~0 on resume** |
| Checkpoint + CSV writes | ~15 min | ~1 min |
| **Total** | **~17 hours** | **~35 min (first run), ~10 min (warm)** |

The single change that matters most is the two-pass approach in Fix 1 — de-duplicate before you LLM, not after.
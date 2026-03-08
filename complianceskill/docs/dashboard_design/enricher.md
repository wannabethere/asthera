# CCE Dashboard Enricher — Setup & Run Guide

Transforms three raw registry files into enriched templates, metrics, and a decision tree, then ingests them into Postgres and/or a ChromaDB vector store.

---

## What It Produces

| Output | Description | Used by |
|---|---|---|
| `enriched_templates.json` | 32 templates with canonical categories, focus areas, destinations, audience, complexity | Scoring node, registry lookup |
| `enriched_metrics.json` | 86 metrics with profile, source capabilities, good_direction | Spec generation node |
| `decision_tree.json` | 7-question tree (destination → category → focus area → ...) with 42 options | LLM resolution prompt |
| `embedding_texts.json` | Pre-built embedding strings for all templates and metrics | Re-indexing without recomputing |
| Postgres tables | `dashboard_templates`, `dashboard_metrics`, `decision_tree_config` + 3 junction tables | Runtime querying, scoring |
| Vector collections | `layout_templates`, `metric_catalog`, `decision_tree_options` | Retrieval points 1 & 2 |

---

## File Layout

```
enricher/
├── run_enricher.py          ← entry point — run this
├── models.py                ← Pydantic models for all enriched entities
├── enricher.py              ← core enrichment logic (no external deps)
├── postgres_writer.py       ← Postgres schema + upsert writer
├── vector_writer.py         ← ChromaDB/Qdrant embedding + indexing
│
├── dashboard_registry.json          ← source: security dashboards (26)
├── ld_templates_registry.json       ← source: L&D templates (6)
└── lms_dashboard_metrics.json       ← source: LMS metrics (86)
```

---

## Prerequisites

**Python 3.10+** is required.

Install core dependencies:
```bash
pip install pydantic
```

Install Postgres driver (if using `--postgres`):
```bash
pip install psycopg2-binary
```

Install vector store driver (if using `--vector-store`):
```bash
pip install chromadb
# or for Qdrant:
pip install qdrant-client
```

Install OpenAI embeddings (if using semantic embeddings):
```bash
pip install openai
```

> **No embeddings API?** The enricher includes a deterministic hash-fingerprint fallback. It will index successfully but similarity search won't be semantic. Fine for development and schema validation.

---

## Environment Variables

| Variable | Required for | Description |
|---|---|---|
| `DATABASE_URL` | `--postgres` | Full Postgres DSN, e.g. `postgresql://user:pass@localhost:5432/cce` |
| `OPENAI_API_KEY` | Semantic embeddings | OpenAI API key for `text-embedding-3-small` |
| `CHROMA_DIR` | `--vector-store` | Directory to persist ChromaDB data (default: `./chroma_db`) |

Set them in your shell or a `.env` file:
```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/cce_dashboard"
export OPENAI_API_KEY="sk-..."
export CHROMA_DIR="./chroma_db"
```

---

## Postgres Setup

### 1. Create the database

```sql
CREATE DATABASE cce_dashboard;
```

The enricher creates all tables automatically on first run — you do not need to run any DDL manually.

### 2. Tables created

| Table | Purpose |
|---|---|
| `dashboard_templates` | One row per enriched template (32 rows from current registries) |
| `dashboard_metrics` | One row per enriched metric (86 rows) |
| `decision_tree_config` | One row per tree version, JSONB. Active version flagged with `is_active = TRUE` |
| `template_focus_areas` | Junction: template ↔ focus area |
| `template_destinations` | Junction: template ↔ destination type |
| `metric_focus_areas` | Junction: metric ↔ focus area |

All upserts key on `content_hash` — re-running the enricher on unchanged files is a no-op.

---

## ChromaDB Setup

No setup required. ChromaDB creates the persistence directory and all collections on first run.

### Collections created

| Collection | Contents | Used by |
|---|---|---|
| `layout_templates` | One doc per template, metadata includes category/audience/complexity/destinations | `scoring_node` — RETRIEVAL POINT 1 |
| `metric_catalog` | One doc per metric, metadata includes thresholds/good_direction/chart_type | `retrieve_context_node` — RETRIEVAL POINT 2 |
| `decision_tree_options` | One doc per decision tree option across all 7 questions | LLM resolution prompt injection |

### Swapping to Qdrant

In `vector_writer.py`, replace `_get_client()`:

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

def _get_client(persist_dir: str):
    return QdrantClient(url=os.environ["QDRANT_URL"])
```

And update `_get_or_create()` to use `qdrant_client.recreate_collection()`.

---

## Running the Enricher

### Dry run — enrich and write JSON only, no DB writes

```bash
python run_enricher.py --dry-run
```

Output written to `./enriched_output/` by default. Use this to inspect the enriched data before committing to any store.

### JSON output only

```bash
python run_enricher.py --output-dir ./enriched_output
```

### Postgres only

```bash
python run_enricher.py --postgres --db-url postgresql://user:pass@localhost:5432/cce_dashboard
```

### Vector store only

```bash
python run_enricher.py --vector-store --chroma-dir ./chroma_db
```

### Full pipeline (recommended)

```bash
python run_enricher.py \
  --postgres \
  --vector-store \
  --output-dir ./enriched_output \
  --db-url postgresql://user:pass@localhost:5432/cce_dashboard \
  --chroma-dir ./chroma_db
```

### Custom source file paths

If your registry files are not in the same directory as `run_enricher.py`:

```bash
python run_enricher.py \
  --dashboard-registry    /path/to/dashboard_registry.json \
  --ld-templates-registry /path/to/ld_templates_registry.json \
  --lms-metrics           /path/to/lms_dashboard_metrics.json \
  --postgres --vector-store
```

---

## Expected Output

A successful run prints:

```
════════════════════════════════════════════════════════════
CCE Dashboard Enricher — starting pipeline
════════════════════════════════════════════════════════════
  Source [dashboard_registry]:    dashboard_registry.json
  Source [ld_templates_registry]: ld_templates_registry.json
  Source [lms_metrics]:           lms_dashboard_metrics.json

── ENRICHMENT ──────────────────────────────────────────
dashboard_registry: 26 templates enriched
ld_templates_registry: 6 templates enriched
Total templates enriched: 32
lms_metrics: 86 metrics enriched
Decision tree built: 42 total options across 7 questions

── POSTGRES ─────────────────────────────────────────
Postgres schema ready
Templates: 32 upserted, 0 unchanged
Metrics:   86 upserted, 0 unchanged
Decision tree v1.0.0 stored

── VECTOR STORE ─────────────────────────────────────
layout_templates:      32 indexed, 0 skipped → 32 total
metric_catalog:        86 indexed, 0 skipped → 86 total
decision_tree_options: 42 options → 42 total

── SUMMARY ──────────────────────────────────────────────
  Templates enriched : 32 (26 security + 6 L&D)
  Metrics enriched   : 86
  Decision tree      : v1.0.0, 7 questions
  Elapsed            : 4.2s
════════════════════════════════════════════════════════════
```

Re-running on unchanged files:
```
Templates: 0 upserted, 32 unchanged
Metrics:   0 upserted, 86 unchanged
```

---

## Verifying the Stores

### Postgres

```sql
-- Row counts
SELECT 'templates' AS table, COUNT(*) FROM dashboard_templates
UNION ALL
SELECT 'metrics',   COUNT(*) FROM dashboard_metrics
UNION ALL
SELECT 'tree',      COUNT(*) FROM decision_tree_config;

-- Check destination coverage
SELECT destination_type, COUNT(*) 
FROM template_destinations 
GROUP BY destination_type ORDER BY 2 DESC;

-- Check focus area distribution
SELECT focus_area, COUNT(*) 
FROM template_focus_areas 
GROUP BY focus_area ORDER BY 2 DESC;

-- Active decision tree
SELECT version, built_at, is_active 
FROM decision_tree_config 
ORDER BY built_at DESC;
```

### ChromaDB (Python)

```python
import chromadb

client = chromadb.PersistentClient(path="./chroma_db")

for name in ["layout_templates", "metric_catalog", "decision_tree_options"]:
    col = client.get_collection(name)
    print(f"{name}: {col.count()} documents")

# Test template retrieval (RETRIEVAL POINT 1)
templates = client.get_collection("layout_templates")
results = templates.query(
    query_texts=["soc2 compliance training completion dashboard"],
    n_results=3,
    include=["metadatas", "distances"],
)
for meta, dist in zip(results["metadatas"][0], results["distances"][0]):
    print(f"  {meta['template_id']} ({meta['category']}) — distance: {dist:.3f}")

# Test metric retrieval (RETRIEVAL POINT 2)
catalog = client.get_collection("metric_catalog")
results = catalog.query(
    query_texts=["training completion rate overdue assignments"],
    n_results=5,
    include=["metadatas"],
)
for meta in results["metadatas"][0]:
    print(f"  {meta['name']} ({meta['metric_type']}) — {meta['chart_type']}")
```

---

## Re-running After Registry Changes

The enricher is idempotent. When you update a source file:

1. Run the full pipeline again — changed records are detected via `content_hash` and upserted; unchanged records are skipped.
2. The decision tree version stays at `1.0.0` unless you bump it manually in `enricher.py` (`build_decision_tree` → `DecisionTree(version=...)`). Bumping the version marks the old tree `is_active = FALSE` in Postgres and re-indexes all options in the vector store.

---

## Swap Points Summary

| Component | File | Function | Default | Alternatives |
|---|---|---|---|---|
| Embedding model | `vector_writer.py` | `_embed()` | OpenAI `text-embedding-3-small` | Cohere, SentenceTransformers, local |
| Vector store client | `vector_writer.py` | `_get_client()` | ChromaDB PersistentClient | Qdrant, pgvector |
| Postgres DSN | env / `--db-url` | — | `DATABASE_URL` env var | Any psycopg2-compatible DSN |
| Embedding fallback | `vector_writer.py` | `_hash_embed()` | SHA-256 fingerprint | Replace with any float vector |
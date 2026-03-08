# CCE Layout Advisor — Developer README

**Post-retrieval refactor.** This document covers the changes made to introduce vector store retrieval, an actual LLM call for spec generation, and the new `retrieval.py` module. Read this before touching any of the five changed files.

---

## What Changed and Why

Before this refactor the pipeline had three problems:

1. `spec_generation_node` was a pure dict constructor — it echoed the selected template back with no LLM involvement and no per-metric configuration (no thresholds, no axis labels, no chart type mapping).
2. `search_templates` in `tools.py` was a stub that returned a comment string instead of querying a vector store.
3. There was no retrieval step anywhere in the pipeline — template scoring and spec generation both ran without any semantic context.

The refactor fixes all three and keeps retrieval isolated to a single new file.

---

## File Map

| File | Status | What changed |
|---|---|---|
| `retrieval.py` | **New** | All vector store calls live here |
| `nodes.py` | Modified | Retrieval Point 1 added to `scoring_node`; new `retrieve_context_node`; `spec_generation_node` replaced with LLM call |
| `graph.py` | Modified | `retrieve_context` node added between customization and spec generation |
| `tools.py` | Modified | `search_templates` stub replaced with real retrieval call |
| `state.py` | Modified | Two new fields: `retrieved_metric_context`, `retrieved_past_specs` |

---

## Graph Topology (updated)

```
START
  │
intake
  │
  ├─(goal-driven)──→ bind ──────────────────────┐
  └─(standard)────→ await_decision_input         │
                         │                       │
                      decision ←──────┐          │
                         │            │          │
                    (more questions)──┘          │
                         │                       │
                         └──(bind)──→ bind       │
                                       │         │
                                    scoring ←────┘   ← RETRIEVAL POINT 1
                                       │
                                 recommendation
                                       │
                               await_selection_input
                                       │
                                    selection
                                       │
                          ┌────────────┴────────────┐
                          │                         │
                  await_data_tables_input   await_customization_input
                          │                         │
                      data_tables              customization ←──┐
                          │                         │           │
                          └────────────────→ (more tweaks) ─────┘
                                                    │
                                           retrieve_context   ← RETRIEVAL POINTS 2 + 3
                                                    │
                                           spec_generation    ← LangChain LLM call
                                                    │
                                                   END
```

---

## The Three Retrieval Points

### Retrieval Point 1 — Template Similarity Boost
**Where:** `scoring_node` in `nodes.py`
**When:** Runs every time scoring runs (both standard and goal-driven paths)
**Collection:** `layout_templates`
**What it does:** Builds a query string from `goal_statement + domain + complexity + data_sources`, calls `retrieve_similar_templates()`, and adds the returned `+0–15` boosts on top of the deterministic rule scores before final ranking.
**Fallback:** If the vector store is unavailable, scoring proceeds with rule scores only. No exception is raised.

### Retrieval Point 2 — Metric Catalog Context
**Where:** `retrieve_context_node` in `nodes.py`
**When:** Runs once, immediately before `spec_generation_node`
**Collection:** `metric_catalog`
**What it does:** Takes every `metric_id` in `metric_gold_model_bindings`, looks up each one in the catalog, and returns display names, units, recommended chart types, warning/critical thresholds, good_direction, axis labels, and aggregation method.
**Output state key:** `retrieved_metric_context` — a list of dicts, one per matched metric
**Fallback:** Returns `[]`. The LLM will generate the spec using the binding data alone, without catalog enrichment.

### Retrieval Point 3 — Past Approved Specs
**Where:** `retrieve_context_node` in `nodes.py`
**When:** Same node, same run as Retrieval Point 2
**Collection:** `past_layout_specs`
**What it does:** Queries by domain, returns up to 2 prior approved specs as few-shot examples. Excludes the current `group_id` to prevent circular retrieval. Each example is truncated to 800 chars for prompt budget.
**Output state key:** `retrieved_past_specs` — a list of dicts with `group_id`, `domain`, `template_id`, `version`, and `layout_spec_snippet`
**Fallback:** Returns `[]`. The LLM generates without few-shot examples.

---

## `retrieval.py` — The Swap Points

All retrieval logic is in `retrieval.py`. Nothing else calls a vector store directly.

### Swapping the vector store client

Open `retrieval.py` and replace the body of `_get_store()`:

```python
# Default (ChromaDB in-memory — dev only):
def _get_store(collection: str):
    import chromadb
    client = chromadb.Client()
    return client.get_or_create_collection(collection)

# Production — ChromaDB persistent:
def _get_store(collection: str):
    import chromadb
    client = chromadb.PersistentClient(path="/data/chromadb")
    return client.get_or_create_collection(collection)

# Qdrant:
def _get_store(collection: str):
    from qdrant_client import QdrantClient
    return QdrantClient(url=os.environ["QDRANT_URL"])
    # Note: Qdrant calls differ — update query calls in each function too

# pgvector / LangChain:
def _get_store(collection: str):
    from langchain_postgres import PGVector
    return PGVector(
        collection_name=collection,
        connection=os.environ["DATABASE_URL"],
        embeddings=your_embedder,
    )
```

### Swapping the embedding function

Replace `_embed()` in `retrieval.py`:

```python
# OpenAI (current default):
def _embed(text: str) -> list[float]:
    from langchain_openai import OpenAIEmbeddings
    return OpenAIEmbeddings(model="text-embedding-3-small").embed_query(text)

# Cohere:
def _embed(text: str) -> list[float]:
    import cohere
    res = cohere.Client(os.environ["COHERE_API_KEY"]).embed(
        texts=[text], model="embed-english-v3.0", input_type="search_query"
    )
    return res.embeddings[0]

# Sentence Transformers (local):
def _embed(text: str) -> list[float]:
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")
    return model.encode(text).tolist()
```

### Three collections required

| Collection name | Contents | Indexed by |
|---|---|---|
| `layout_templates` | One document per template. Use `get_template_embedding_text(tpl)` from `templates.py` to build the text to embed. Metadata must include `template_id`. | `templates.py` on startup or a separate indexing script |
| `metric_catalog` | One document per metric. Document text = metric definition. Metadata must include `metric_id`, `display_name`, `unit`, `chart_type`, `threshold_warning`, `threshold_critical`, `good_direction`, `axis_label`, `aggregation`. | Your metric catalog ETL |
| `past_layout_specs` | One document per approved spec version. Use `index_approved_layout_spec()` from `retrieval.py` to write entries. Metadata must include `group_id`, `domain`, `template_id`, `version`, `metric_count`. | `storage_node` write-back (see below) |

---

## `spec_generation_node` — LLM Call Details

`spec_generation_node` now makes a `ChatAnthropic.invoke()` call via LangChain. It does not return until the LLM responds.

**Model config** (set in `agent_config`):
```python
agent_config = {
    "spec_gen_model": "claude-sonnet-4-5-20250514",  # default
    "spec_gen_temperature": 0.1,                      # default
    "group_id": "your_group_id",                      # used for retrieval point 3
}
```

**What the LLM receives:**
- The selected template's structure (primitives, panels, strip_cells)
- All accumulated decisions (domain, theme, complexity, etc.)
- Metric bindings enriched with catalog data (thresholds, display names, chart types from Retrieval Point 2)
- Control anchors from `resolution_payload`
- Any customization requests from the conversation
- Up to 2 past approved spec snippets as few-shot context (from Retrieval Point 3)

**What the LLM returns:**
A JSON object with `strip_kpis[]` and `charts[]` arrays where each metric is individually configured — not a template echo. Each chart entry includes `chart_type`, `panel`, `axis_label`, `unit`, `aggregation`, `good_direction`, `color_rules`, and `gold_table`.

**Fallback behaviour:**
If the LLM call fails or the response is not valid JSON, `_build_fallback_spec()` runs deterministically from the enriched bindings. The output spec will contain `"_fallback": true` so you can detect this in logs or downstream. The pipeline does not crash.

---

## Write-Back — Closing the Loop for Retrieval Point 3

After a spec is approved and committed to git + Postgres, call `index_approved_layout_spec()` from `storage_node`:

```python
from .retrieval import index_approved_layout_spec

# In storage_node, after promote_version() succeeds:
index_approved_layout_spec(
    group_id=group_id,
    domain=decisions.get("domain", ""),
    template_id=selected_template_id,
    version=new_version,
    layout_spec=committed_spec,
    metric_count=len(metric_gold_model_bindings),
)
```

This makes every approved spec available as a future few-shot example. The collection improves with each approved run.

---

## New State Fields

Two fields were added to `LayoutAdvisorState`:

```python
retrieved_metric_context: list  # RETRIEVAL POINT 2 output — list of metric catalog dicts
retrieved_past_specs: list      # RETRIEVAL POINT 3 output — list of past spec dicts
```

Both are written by `retrieve_context_node` and read by `spec_generation_node`. They are not user-facing and should not appear in conversation messages.

---

## Environment Variables Required

| Variable | Used by | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | `spec_generation_node`, `llm_agent_node` | LangChain Anthropic client |
| `OPENAI_API_KEY` | `_embed()` in `retrieval.py` (default) | Embedding function — remove if swapping to local embeddings |
| `QDRANT_URL` | `_get_store()` if using Qdrant | Vector store URL |
| `DATABASE_URL` | `_get_store()` if using pgvector | Postgres connection string |

---

## Indexing the `layout_templates` Collection

This collection needs to be populated once (and updated if templates change). A minimal indexing script:

```python
from cce_layout_advisor.templates import TEMPLATES, get_template_embedding_text
from cce_layout_advisor.retrieval import _get_store, _embed

store = _get_store("layout_templates")

for tid, tpl in TEMPLATES.items():
    text = get_template_embedding_text(tpl)
    embedding = _embed(text)
    store.upsert(
        ids=[tid],
        embeddings=[embedding],
        documents=[text],
        metadatas=[{"template_id": tid, "domain": tpl["domains"][0] if tpl["domains"] else ""}],
    )

print(f"Indexed {len(TEMPLATES)} templates")
```

Run this once on startup or as a separate management command. The `metric_catalog` collection is owned by your metric catalog ETL pipeline.

---

## Testing the Retrieval Points in Isolation

Each retrieval function can be tested independently without running the full graph:

```python
from cce_layout_advisor.retrieval import (
    retrieve_similar_templates,
    retrieve_metric_catalog_context,
    retrieve_past_layout_specs,
)

# Retrieval Point 1
boosts = retrieve_similar_templates("SOC2 compliance training completion", k=5)
# Returns: [{"template_id": "...", "boost": 12, "similarity": 0.81}, ...]

# Retrieval Point 2
catalog = retrieve_metric_catalog_context(["training.completion_rate", "vuln.critical_unpatched"])
# Returns: [{"metric_id": "...", "display_name": "...", "thresholds": {...}, ...}, ...]

# Retrieval Point 3
past = retrieve_past_layout_specs(group_id="soc2_audit_hybrid", domain="compliance", k=2)
# Returns: [{"group_id": "...", "layout_spec_snippet": "...", ...}, ...]
```

All three return `[]` gracefully if the vector store is not running — safe to test against a cold environment.

---

## Checklist Before First Run

- [ ] Vector store client configured in `_get_store()` in `retrieval.py`
- [ ] Embedding function configured in `_embed()` in `retrieval.py`
- [ ] `layout_templates` collection indexed (run the script above)
- [ ] `metric_catalog` collection populated by your ETL
- [ ] `ANTHROPIC_API_KEY` set in environment
- [ ] `agent_config["group_id"]` set when invoking the graph
- [ ] `agent_config["spec_gen_model"]` set (or left as default `claude-sonnet-4-5-20250514`)
- [ ] `storage_node` updated to call `index_approved_layout_spec()` after each approval
# Dashboard Agent Ingestion Plan

**Purpose:** All ingestion steps required for the Dashboard Layout Advisor Agent (Resolve → Bind → Score → Recommend → Verify pipeline) to work and report correctly.

---

## 1. Overview

The dashboard agent depends on:

| Layer | Data Source | Storage | Used By |
|-------|-------------|---------|---------|
| **Registry** | JSON files | File system | All stages |
| **Taxonomy** | JSON files | File system | BIND, RESOLVE, taxonomy_matcher |
| **Vector Store** | Ingested docs | Qdrant/Chroma | Semantic search (optional) |
| **Metrics Registry** | Ingested docs | Qdrant | L&D/CSOD flows |

---

## 2. Prerequisites

### 2.1 Environment

- **Vector store**: Qdrant or ChromaDB running (configured via `VECTOR_STORE_TYPE`, `QDRANT_*`, `CHROMA_*`)
- **Embeddings**: `OPENAI_API_KEY` or configured embedder
- **LLM** (for taxonomy generation): Anthropic/OpenAI for `generate_dashboard_taxonomy` and `enrich_dashboard_taxonomy`

### 2.2 Registry Files (Must Exist)

**Ingestion data** — `data/dashboard/`:
| File | Purpose | Required |
|------|---------|----------|
| `templates_registry.json` | Base 17 security/compliance templates | Yes |
| `ld_templates_registry.json` | 6 L&D templates | Yes |
| `lms_dashboard_metrics.json` | LMS metrics for L&D dashboards | For L&D flows |
| `metrics_registry.json` | Security metrics | Optional |
| `lms_metrics_registry.json` | LMS metrics registry | Optional |
| `dashboard_registry.json` | Dashboard registry | Optional |

**Config** — `app/config/dashboard/`:
| File | Purpose | Required |
|------|---------|----------|
| `dashboard_domain_taxonomy.json` | Domain taxonomy (generated or manual) | Yes |
| `dashboard_domain_taxonomy_enriched.json` | Enriched taxonomy (from enrich script) | Recommended |
| `metric_use_case_groups.json` | Use case → metric groups | Yes |
| `control_domain_taxonomy.json` | Control anchors | Yes |
| `taxonomy_keyword_index.json` | Keyword → domain_ids (built from taxonomy) | Optional (auto-built by ingestion) |

---

## 3. Ingestion Pipeline (Ordered)

### Phase A: Taxonomy Generation (First-Time or Refresh)

**When:** New templates added, or taxonomy structure changed.

#### Step A1: Generate Dashboard Domain Taxonomy

```bash
python -m app.ingestion.generate_dashboard_taxonomy \
    --templates-dir data/dashboard \
    --output app/config/dashboard/dashboard_domain_taxonomy.json \
    --max-samples 20
```
Or use defaults (no args needed): `python -m app.ingestion.generate_dashboard_taxonomy`

- **Input:** `ld_templates_registry.json`, `lms_dashboard_metrics.json`, `templates_registry.json`
- **Output:** `dashboard_domain_taxonomy.json` (domains, goals, focus_areas, use_cases, audience_levels)
- **Requires:** LLM (Anthropic/OpenAI)

#### Step A2: Enrich Dashboard Taxonomy

```bash
python -m app.ingestion.enrich_dashboard_taxonomy \
    --input app/config/dashboard/dashboard_domain_taxonomy.json \
    --output app/config/dashboard/dashboard_domain_taxonomy_enriched.json \
    --templates-dir data/dashboard \
    --method llm
```
Or use defaults: `python -m app.ingestion.enrich_dashboard_taxonomy --method llm`

- **Input:** Generated taxonomy + templates
- **Output:** `dashboard_domain_taxonomy_enriched.json` (improved goals, mappings)
- **Requires:** LLM

---

### Phase B: Vector Store Ingestion

**When:** After registry/taxonomy is stable. Run when templates change.

#### Step B1: Ingest Dashboard Templates

```bash
python -m app.ingestion.ingest_dashboard_templates --reinit --verify
```

- **Input:** `registry_unified` (templates_registry + ld_templates_registry)
- **Output:** Collection `dashboard_templates` in Qdrant/Chroma
- **Purpose:** Semantic search for template matching
- **Flags:**
  - `--reinit`: Delete and recreate collection
  - `--verify`: Run sample queries after ingestion

**Note:** `DashboardTemplateRetrievalService` currently builds an in-memory FAISS/Chroma from the registry at runtime. To use the pre-ingested collection instead, the service would need to be wired to `get_doc_store_provider().stores["dashboard_templates"]` when available. This is a future enhancement.

#### Step B2: Ingest Dashboard Metrics Registry (Optional, for L&D/CSOD)

```bash
python -m app.ingestion.ingest_dashboard_metrics_registry \
    --templates-dir data/dashboard \
    --output-collection dashboard_metrics_registry \
    --reinit
```
Or use default templates-dir: `python -m app.ingestion.ingest_dashboard_metrics_registry --reinit`

- **Input:** `ld_templates_registry.json`, `lms_dashboard_metrics.json`, `templates_registry.json`, `metrics_registry.json`
- **Output:** Collection `dashboard_metrics_registry`
- **Purpose:** Unified dashboard+metrics for L&D and CSOD flows

---

### Phase C: No Ingestion (File-Based)

These are loaded at runtime from JSON; no ingestion step:

| Data | Location | Used By |
|------|----------|---------|
| `metric_use_case_groups.json` | `app/config/dashboard/` | `expand_use_case_group`, BIND |
| `control_domain_taxonomy.json` | `app/config/dashboard/` | `join_control_anchors`, BIND |
| `dashboard_domain_taxonomy*.json` | `app/config/dashboard/` | `taxonomy_matcher`, domain scoring |

---

## 4. Verification Checklist

After ingestion, verify:

| Check | Command / Action |
|-------|-------------------|
| Templates load | `python -c "from app.utils.registry_config.registry_unified import ALL_TEMPLATES; print(len(ALL_TEMPLATES))"` → expect 23 |
| Taxonomy loads | `python -c "from app.agents.dashboard_agent.taxonomy_matcher import load_taxonomy; t=load_taxonomy(); print(len(t.get('domains',{})))"` |
| Use case groups | `python -c "from app.agents.dashboard_agent.taxonomy_matcher import expand_use_case_group; print(expand_use_case_group('soc2_audit','high'))"` |
| Control anchors | `python -c "from app.agents.dashboard_agent.taxonomy_matcher import join_control_anchors; print(len(join_control_anchors(['training_compliance'],'soc2')))"` |
| Dashboard templates collection | Run `ingest_dashboard_templates --verify` |
| Service works | `python -c "from app.services.dashboard_template_service import DashboardTemplateRetrievalService; s=DashboardTemplateRetrievalService(); r=s.search_by_decisions({'domain':'ld_training','has_chat':True}, k=3); print(r.total_hits))"` |

---

## 5. Reporting / Observability

### 5.1 Ingestion Report (Proposed)

After each ingestion run, output a summary:

```
=== Dashboard Agent Ingestion Report ===
Date: YYYY-MM-DD HH:MM
Vector Store: qdrant | chroma

Phase A - Taxonomy:
  dashboard_domain_taxonomy.json: OK (N domains)
  dashboard_domain_taxonomy_enriched.json: OK (N domains)

Phase B - Vector Store:
  dashboard_templates: 23 docs indexed
  dashboard_metrics_registry: N docs indexed (if run)

Phase C - File-Based:
  metric_use_case_groups.json: OK (5 use cases)
  control_domain_taxonomy.json: OK (soc2, hipaa, nist_ai_rmf)

Verification:
  Template search: OK
  Taxonomy match: OK
  Service search_by_decisions: OK
```

### 5.2 Add `--report` Flag

Extend ingestion scripts to support `--report` that prints this summary after completion.

---

## 6. Orchestration Script

Single entry point to run full pipeline:

```bash
# From complianceskill/ directory
python scripts/run_dashboard_ingestion.py

# Skip taxonomy (use existing files)
python scripts/run_dashboard_ingestion.py --skip-taxonomy

# Include L&D metrics registry
python scripts/run_dashboard_ingestion.py --metrics

# Dry run (print commands only)
python scripts/run_dashboard_ingestion.py --dry-run
```

---

## 7. Gaps & Recommendations

| Gap | Recommendation |
|-----|----------------|
| Service uses in-memory vector store, not ingested collection | Wire `DashboardTemplateRetrievalService` to use `doc_store["dashboard_templates"]` when available; fallback to in-memory build |
| ~~No single orchestration script~~ | Done: `scripts/run_dashboard_ingestion.py` |
| No ingestion report | Add `--report` to scripts; consider `ingest_dashboard_templates --report` |
| `metric_use_case_groups` and `control_domain_taxonomy` in decision_trees, not registry_config | Consider moving to `app/utils/registry_config/` for consistency, or document the split |
| Taxonomy paths in taxonomy_matcher | Already supports both `decision_trees/` and `utils/registry_config/` |

---

## 8. Quick Start (Minimal)

For the dashboard agent to work with rule-based scoring only (no vector search from ingested collection):

1. Ensure registry files exist: `templates_registry.json`, `ld_templates_registry.json`
2. Ensure taxonomy files exist: `dashboard_domain_taxonomy_enriched.json` (or `.json`), `metric_use_case_groups.json`, `control_domain_taxonomy.json`
3. No ingestion required — agent uses file-based registry and taxonomy

For full semantic search and L&D flows:

1. Run Phase A (taxonomy)
2. Run Phase B (ingest templates)
3. Optionally run `ingest_dashboard_metrics_registry` for L&D

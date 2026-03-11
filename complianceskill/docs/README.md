# Causal Graph Creator Module

This module provides causal graph construction capabilities for the CSOD workflow, enabling metrics recommendations based on causal relationships between metrics.

## Overview

The causal graph creator uses a **vector-store-backed approach** to:
1. Retrieve semantically relevant causal nodes and edges from a curated knowledge base
2. Assemble a typed causal graph using LLM reasoning
3. Extract causal context signals for metrics recommender integration

This replaces the traditional N1→N5 pipeline (decomposer → node proposer → edge proposer → lag estimator → validator) with a single vector retrieval + LLM assembly step.

## Architecture

### Components

1. **`causal_engine_state.py`** — State schema and data models
   - `CSODCausalPipelineState` — TypedDict state schema
   - `CausalNode`, `CausalEdge` — Core data models
   - `GraphMetadata`, `ValidationResult` — Supporting types

2. **`vector_causal_graph_builder.py`** — Vector retrieval and LLM assembly
   - `ingest_nodes()` / `ingest_edges()` — Ingest nodes/edges into vector store
   - `retrieve_causal_nodes()` — Semantic node retrieval
   - `retrieve_causal_edges()` — Semantic + structural edge retrieval
   - `assemble_causal_graph_with_llm()` — Single LLM call for graph assembly
   - `vector_causal_graph_node()` — LangGraph node function

3. **`causal_context_extractor.py`** — Bridge layer
   - `extract_causal_context()` — Translates graph → decision signals
   - Derives focus_area, complexity, metric_profile from graph structure
   - Builds hot paths, latent node warnings, causal node index

4. **`causal_graph_nodes.py`** — CSOD workflow integration
   - `causal_graph_creator_node()` — Main node for CSOD workflow

## Usage

### Basic Integration with CSOD Workflow

```python
from app.agents.causalgraph import causal_graph_creator_node

# In your CSOD workflow, add the causal graph node:
state = causal_graph_creator_node(state)

# After execution, state contains:
# - causal_proposed_nodes: List of selected causal nodes
# - causal_proposed_edges: List of selected causal edges
# - causal_graph_metadata: Graph summary metadata
# - causal_signals: Derived decision signals (focus_area, complexity, etc.)
# - causal_graph_panel_data: Graph data for dashboard rendering
# - causal_node_index: metric_ref → node metadata mapping
```

### Ingesting Initial Knowledge Base

```python
from app.agents.causalgraph import ingest_nodes, ingest_edges

# Load your metric registry and causal corpus
nodes = load_metric_registry()  # List[Dict[str, Any]]
edges = load_causal_corpus()    # List[Dict[str, Any]]

# Ingest into vector store
await ingest_nodes(nodes)
await ingest_edges(edges)
```

### State Requirements

The causal graph creator expects the following state fields:

**Input:**
- `user_query` — The user's question about metrics
- `causal_vertical` — Vertical identifier (e.g., "lms", "hr")
- `metric_registry` — Optional metric registry for query enrichment
- `cce_db_url` — Optional Postgres connection string for structural lookups

**Output:**
- `causal_proposed_nodes` — Selected nodes from retrieval
- `causal_proposed_edges` — Selected edges from retrieval
- `causal_graph_metadata` — Graph summary (node_count, edge_count, confidence, etc.)
- `causal_signals` — Derived signals for decision tree
- `causal_graph_panel_data` — Graph data for dashboard panel
- `causal_node_index` — Metric reference → node metadata mapping

## Node Types

The causal graph uses typed nodes:

- **`root`** — Exogenous driver, no parents in scope
- **`mediator`** — Caused by something AND causes something else
- **`confounder`** — Independently drives 2+ other metrics (must be controlled)
- **`collider`** — Caused by 2+ independent parents (⚠️ never filter by this)
- **`terminal`** — Outcome variable (what the question is about)

## Edge Properties

Each edge carries:
- `mechanism` — Causal mechanism description
- `direction` — positive, negative, nonlinear, unknown
- `lag_window_days` — Days before effect is measurable
- `confidence_score` — 0.0–1.0 confidence in the relationship
- `corpus_match_type` — confirmed, analogous, novel, untested

## Integration with Metrics Recommender

The causal graph creator enriches the CSOD metrics recommender by:

1. **Focus Area Derivation** — Maps terminal node categories to focus areas
2. **Complexity Calibration** — Derives complexity from graph depth × confidence
3. **Metric Profile Hint** — Suggests trend_heavy vs scorecard based on temporal grain
4. **Hot Paths** — Identifies top 3 root-to-terminal causal pathways
5. **Collider Warnings** — Flags metrics that should not be used as filters

The metrics recommender can use `causal_node_index` to:
- Override chart types based on node type (e.g., terminal → gauge)
- Add collider warnings to chart configs
- Include temporal grain in axis configs

## Vector Store Architecture

Uses the unified `VectorStoreClient` from `app.storage.vector_store`:
- Supports ChromaDB and Qdrant backends
- Automatic embedding model initialization
- Collection-based organization (nodes vs edges)

Collections:
- `cce_causal_nodes` — Node embeddings
- `cce_causal_edges` — Edge embeddings

## Postgres Structural Lookups (Optional)

If `cce_db_url` is provided, the system also performs structural adjacency lookups using Postgres:
- Uses `cce.causal_adjacency` table with B-tree indexes
- Single indexed query replaces 20-call ChromaDB loop
- ~2ms lookup regardless of corpus size

See `app.agents.csod.csod_causal_graph.fetch_adjacent_edges_pg()` for implementation.

## Design Principles

Based on `causal_dashboard_design_doc.md`:

- **P1** — LLM for semantics, rules for structure
- **P2** — Graph structure before data (topology from registry + corpus)
- **P3** — Explicit uncertainty (every edge has confidence + match type)
- **P4** — Vertical configuration at boundary (all vertical logic in config)
- **P5** — Intervention log required (feedback loop for learning)
- **P6** — Dashboard as causal surface (graph is first-class UI element)

## Example Workflow

```
User Query: "Why is our compliance rate dropping?"

1. Vector Retrieval:
   - Query: "Why is our compliance rate dropping?"
   - Retrieves: 20 nodes (compliance_rate, overdue_count, assignment_load, etc.)
   - Retrieves: 30 edges (overdue_count → compliance_rate, etc.)

2. LLM Assembly:
   - Selects relevant subset (12 nodes, 15 edges)
   - Identifies: compliance_rate (terminal), assignment_load (root), overdue_count (mediator)
   - Flags: completion_rate (collider) — don't filter by this
   - Builds hot paths: assignment_load → overdue_count → compliance_rate

3. Context Extraction:
   - derived_focus_area: "compliance_posture"
   - derived_complexity: "medium"
   - causal_metric_profile_hint: "scorecard"
   - hot_paths: [assignment_load → overdue_count → compliance_rate]

4. Metrics Recommender Integration:
   - Recommends metrics along the hot path
   - Includes collider warnings
   - Uses focus_area for dashboard template selection
```

## Future Enhancements

- **Intervention Feedback Loop** — Update edge confidence from observed outcomes
- **Corpus Growth** — Append live interventions to corpus
- **Multi-Vertical Support** — Extend beyond LMS/HR to other domains
- **Graph Hydration** — Activate node observability from silver tables
- **NetworkX Integration** — Full graph structure for path analysis

## References

- `causal_dashboard_design_doc.md` — Full design specification
- `hybrid_causal_graph.md` — Hybrid retrieval pattern
- `vector_causal_graph_builder.py` — Original implementation reference
- `lms_schema_definitions.md` — LMS silver layer schema

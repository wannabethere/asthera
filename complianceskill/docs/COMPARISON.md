# Causal Graph Implementation Comparison

This document compares the implementation in `complianceskill/app/agents/causalgraph` with the reference implementations in `causalgraphs/lms_causal_metrics/code/` to identify gaps and integration points.

## Implementation Status

### ✅ Completed Components

1. **`causal_engine_state.py`** — State schema and data models
   - ✅ `CSODCausalPipelineState` — TypedDict state schema
   - ✅ `CausalNode`, `CausalEdge` — Core data models
   - ✅ `GraphMetadata`, `ValidationResult` — Supporting types
   - **Status**: Matches reference implementation structure

2. **`vector_causal_graph_builder.py`** — Vector retrieval and LLM assembly
   - ✅ `ingest_nodes()` / `ingest_edges()` — Ingestion using unified VectorStoreClient
   - ✅ `retrieve_causal_nodes()` — Semantic node retrieval
   - ✅ `retrieve_causal_edges()` — Semantic + structural edge retrieval
   - ✅ `assemble_causal_graph_with_llm()` — Single LLM call for graph assembly
   - ✅ `vector_causal_graph_node()` — LangGraph node function
   - **Status**: Adapted for unified storage architecture (ChromaDB/Qdrant via VectorStoreClient)
   - **Difference**: Uses async/await pattern with unified client vs. direct ChromaDB client

3. **`causal_context_extractor.py`** — Bridge layer
   - ✅ `extract_causal_context()` — Translates graph → decision signals
   - ✅ Derives focus_area, complexity, metric_profile from graph structure
   - ✅ Builds hot paths, latent node warnings, causal node index
   - **Status**: Simplified version of reference (710 lines → ~300 lines)
   - **Gap**: Missing NetworkX graph reconstruction (uses simpler path finding)

4. **`causal_graph_nodes.py`** — CSOD workflow integration
   - ✅ `causal_graph_creator_node()` — Main node for CSOD workflow
   - **Status**: Wrapper around vector_causal_graph_node + extract_causal_context

5. **`csod_workflow_integration.py`** — CSOD integration
   - ✅ `csod_causal_graph_entry_node()` — Entry node bridging CSOD → causal graph
   - ✅ `enrich_metrics_with_causal_insights()` — Metric enrichment helper
   - **Status**: Simplified integration pattern

6. **`csod_metric_advisor.py`** — Metric advisor with causal insights
   - ✅ `csod_metric_advisor_node()` — Advisor node using causal graph
   - ✅ `_enhance_metrics_with_causal_insights()` — Metric enrichment
   - ✅ `_build_reasoning_plan()` — Reasoning plan generation
   - **Status**: New implementation based on reference pattern

7. **`csod_metric_advisor_workflow.py`** — Standalone advisor workflow
   - ✅ Workflow definition with causal graph integration
   - ✅ Routing functions
   - ✅ Initial state factory
   - **Status**: New workflow for metric advisor intent

## Gaps and Differences

### 1. **Full N1-N7 Pipeline vs. Vector Retrieval**

**Reference Implementation** (`causal_graph_nodes.py`):
- Full 7-node pipeline: N1 (decomposer) → N2 (node proposer) → N3 (edge proposer) → N4 (lag estimator) → N5 (validation) → N6 (hydrator) → N7 (assembler)
- Revision loop for edge validation
- Corpus matching and graph coherence validation

**Our Implementation**:
- Single vector retrieval + LLM assembly (replaces N1-N5)
- No revision loop (edges validated at retrieval time)
- Simpler but faster approach

**Decision**: Our approach is intentional — we use vector retrieval + single LLM assembly for speed, trading off some validation rigor for performance. The reference N1-N7 pipeline can be added later if needed.

### 2. **NetworkX Graph Structure**

**Reference Implementation**:
- Full NetworkX DiGraph reconstruction in `causal_context_extractor.py`
- Uses `nx.node_link_graph()` and `nx.descendants()` for path analysis
- More robust graph traversal

**Our Implementation**:
- Simplified path finding (DFS-based)
- No NetworkX dependency in causal_context_extractor
- Graph structure stored as node_link_data but not actively used

**Gap**: Should add NetworkX for robust graph operations. **Action**: Add NetworkX to `causal_context_extractor.py`.

### 3. **Causal Context Extractor Completeness**

**Reference Implementation** (710 lines):
- Full terminal → focus_area mapping with LMS_TERMINAL_TO_FOCUS_AREA
- NetworkX-based hot path building
- Latent node warning generation with downstream analysis
- Causal node index with chart type overrides

**Our Implementation** (~300 lines):
- Simplified focus_area derivation
- Basic hot path building (DFS)
- Simplified latent node warnings
- Basic causal node index

**Gap**: Missing some sophistication in signal derivation. **Action**: Enhance `causal_context_extractor.py` with NetworkX and full mapping.

### 4. **State Field Alignment**

**Reference Implementation** uses:
- `causal_proposed_nodes`, `causal_proposed_edges` (from N2, N3)
- `causal_graph`, `causal_graph_metadata` (from N7)
- `causal_signals`, `causal_graph_panel_data`, `causal_node_index` (from B1)

**Our Implementation** uses:
- Same field names ✅
- Compatible structure ✅

**Status**: Aligned.

### 5. **CSOD Workflow Integration Pattern**

**Reference Implementation** (`csod_workflow_integration.py`):
- Adds new intent: `causal_metrics_dashboard`
- New node: `csod_causal_dashboard_entry_node` (runs full N1-N7 + B1 + D1-D4)
- Routes: `metrics_recommender` → `causal_dashboard` → `scheduler`

**Our Implementation**:
- Uses existing `csod_causal_graph_node` (enhanced to use causal_graph_creator)
- Routes: `scoring_validator` → `causal_graph` → `metrics_recommender`
- No separate dashboard decision tree integration

**Gap**: Missing dashboard decision tree integration (D1-D4 nodes). **Action**: Can add later if dashboard generation is needed.

### 6. **Metric Advisor Workflow**

**Reference Implementation** (`csod_metric_advisor_workflow.py`):
- Full workflow with `csod_metric_kpi_relations_node` and `csod_reasoning_plan_node`
- Relation mapping (metric-to-metric, metric-to-KPI, KPI hierarchy)
- Detailed reasoning plan with action triggers

**Our Implementation**:
- Simplified advisor using causal graph insights
- Missing relation mapping node
- Reasoning plan is simpler

**Gap**: Missing detailed relation mapping. **Action**: Can enhance `csod_metric_advisor_node` with relation mapping if needed.

## Integration Points

### Current CSOD Workflow Integration

The existing `csod_workflow.py` already has:
- ✅ `csod_causal_graph_node` integrated after `csod_scoring_validator`
- ✅ Feature flag: `csod_causal_graph_enabled`
- ✅ State fields: `csod_causal_nodes`, `csod_causal_edges`, `csod_causal_graph_metadata`

**What We Added**:
- ✅ Enhanced `csod_causal_graph_node` to use `causal_graph_creator_node` (full assembly)
- ✅ Added causal context extraction for metrics recommender
- ✅ Enhanced metrics recommender prompt with causal insights

### Metrics Recommender Enrichment

**Current**: `csod_metrics_recommender_node` already includes causal graph context in prompt.

**Enhancement**: Updated to include:
- Hot paths
- Causal signals (focus_area, complexity)
- Causal node index for chart type hints

## Recommended Next Steps

### High Priority

1. **Add NetworkX to causal_context_extractor**
   - Import NetworkX
   - Use `nx.node_link_graph()` for graph reconstruction
   - Use `nx.descendants()` for latent node analysis
   - Use `nx.all_simple_paths()` for hot path building

2. **Enhance focus_area mapping**
   - Add full `LMS_TERMINAL_TO_FOCUS_AREA` mapping
   - Support vertical-specific mappings
   - Add confidence scoring for focus_area derivation

### Medium Priority

3. **Add revision loop (optional)**
   - If edge quality becomes an issue, add N5 validation + revision loop
   - Currently edges are validated at retrieval time (sufficient for MVP)

4. **Enhance metric advisor**
   - Add relation mapping node (metric-to-metric, metric-to-KPI)
   - Add detailed reasoning plan with action triggers
   - Add monitoring cadence recommendations

### Low Priority

5. **Dashboard decision tree integration**
   - Add D1-D4 nodes if dashboard generation is needed
   - Currently metrics recommender is sufficient

6. **Intervention feedback loop**
   - Add `record_dashboard_intervention()` and `apply_intervention_feedback()`
   - For corpus growth over time

## Code Quality

### ✅ Strengths

- Uses unified storage architecture (VectorStoreClient)
- Async/await pattern for better performance
- Clean separation of concerns (retrieval, assembly, extraction)
- Feature flag controlled (backward compatible)
- Comprehensive error handling

### ⚠️ Areas for Improvement

- Add NetworkX for robust graph operations
- Add more comprehensive focus_area mapping
- Consider adding revision loop if edge quality issues arise
- Add unit tests for causal context extraction

## Summary

The implementation successfully provides:
- ✅ Vector-store-backed causal graph retrieval
- ✅ LLM assembly for graph construction
- ✅ Causal context extraction for metrics recommender
- ✅ CSOD workflow integration
- ✅ Metric advisor with causal insights

**Key Difference**: We use a simplified, faster approach (vector retrieval + single LLM assembly) vs. the full N1-N7 pipeline. This is intentional for performance, but the full pipeline can be added if needed.

**Main Gap**: Missing NetworkX for robust graph operations in `causal_context_extractor.py`. This should be added for production use.

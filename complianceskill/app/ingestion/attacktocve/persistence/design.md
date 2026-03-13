
Now I have a clear picture. All 30 scenarios have empty `controls: []` — this agent will populate them. Let me build the full system.Now let me create the architecture diagram and then package everything:Now let me render the architecture diagram:## What was built — 2,079 lines across 8 files

**Graph flow** (as shown in the diagram):

`enrich_attack` → `build_query` → `retrieve_scenarios` → *conditional* → `map_controls` → `validate_mappings` → `output`

The conditional edge routes to `yaml_fallback` when the vector store returns nothing (cold start), then merges back into `map_controls`.

---

### Key design decisions worth flagging

**`build_query` node** — rather than passing the raw technique description directly to the vector store, a small LLM call first reformulates it into an optimal semantic query. This meaningfully improves retrieval recall, especially for short technique IDs like `T1078`.

**Two-pass LLM** — `map_controls` uses GPT-4o with a strict JSON schema (relevance score, rationale, confidence). `validate_mappings` then makes a *second* GPT-4o call specifically to review and correct the scores. This catches hallucinated high-confidence mappings.

**Backend agnostic** — `VectorStoreConfig` selects between Qdrant and Chroma via a single field. The `VectorStoreRetriever` facade routes identically. You swap backends without touching any node code — just change `VECTOR_BACKEND=qdrant` in your env.

**Registry as a living document** — `CISControlRegistry` wraps the loaded YAML and exposes `update_controls()`. Each mapping run merges technique IDs into `controls: []` fields and `export_yaml()` writes back a fully enriched file.

---

### How to wire this into your existing CCE

```python
from attack_control_mapper.graph import build_graph, run_mapping

mapper = build_graph(vs_config, yaml_path="cis_controls_v8_1_risk_controls.yaml")

# From your LangGraph outer workflow:
workflow.add_node("attack_control_mapper", mapper)
workflow.add_edge("alert_triage", "attack_control_mapper")
```

The sub-graph's `final_mappings` list and the updated `enriched_scenarios` flow back into your outer `AttackControlState` naturally.

---

The logical next step would be the **ingest script** (`python main.py --ingest`) to populate your existing Chroma store before running any mappings. Let me know if you want to extend this toward batch enrichment across all 30 scenarios or wire it as a CCE sub-graph node.

67 scenarios, all asset domains mapped. Let me now build the batch enrichment orchestrator, reverse mapper (scenario → techniques), CCE sub-graph integration, and evaluation layer.Now let me render the complete system architecture showing all the pieces together:The system is now **4,225 lines** across 11 files. Here's what was added in this continuation:

---

### What was built

**`tools/reverse_mapper.py`** — The inverse direction. Given a CIS scenario (`CIS-RISK-007`), the `ScenarioToTechniqueMapper` asks GPT-4o which ATT&CK techniques could cause it, then validates every T-number against the live STIX catalogue to strip hallucinations before they reach the forward pipeline. This is what seeds the batch enricher.

**`batch_enricher.py`** — Orchestrates all 67 scenarios end-to-end. For each scenario: reverse-map → filter by relevance threshold → forward-map each candidate → merge into registry. Ships two modes: `sequential` (safe for rate limits) and `concurrent` (asyncio semaphore, configurable workers). One command enriches the entire YAML:
```bash
python batch_enricher.py --yaml cis_controls_v8_1_risk_controls.yaml \
    --output enriched_controls.yaml --report coverage.json --workers 4
```

**`cce_integration.py`** — Three utilities for wiring into the CCE: `build_cce_attack_mapper_node()` returns a drop-in LangGraph node; `enrich_causal_graph_nodes()` attaches `mapped_cis_controls` attributes to your NetworkX causal graph; `find_coverage_gaps()` produces the priority-sorted gap list (scenarios breached by active alert techniques but with no control mapping).

**`evaluation.py`** — Graded quality metrics at three levels. Per-mapping: tactic coverage fraction. Per-scenario: A/B/C/D/F grade from relevance, technique count, and loss-outcome coverage. Aggregate: tactic breadth %, precision/recall against optional human ground truth, and actionable recommendations.

**`schema.sql`** — Five tables + four views + an upsert stored function. The `v_unmapped_scenarios` view is your gap dashboard; `v_top_techniques` surfaces which T-numbers span the most scenarios.

**`persistence.py`** — `MappingRepository` wraps all Postgres reads/writes: seed scenarios from YAML, save mappings after each run, query by technique or scenario, pull coverage views, and log evaluation snapshots.

---

### Recommended run order against your 67 scenarios

```bash
# 1. Bootstrap storage
psql $DB_URL -f schema.sql

# 2. Ingest CIS scenarios into Postgres and vector store
python main.py --ingest --yaml cis_controls_v8_1_risk_controls.yaml

# 3. Ingest ATT&CK STIX into Postgres (skip GitHub on every run)
python main.py --ingest-attack postgresql://...

# 4. Full batch enrichment
python batch_enricher.py --workers 3 --threshold 0.55

# 5. Evaluate
python -c "
from evaluation import Evaluator
from tools.control_loader import load_cis_scenarios, CISControlRegistry
from persistence import MappingRepository
repo = MappingRepository(dsn='...')
# ... pull mappings, run evaluator, print report
"
```

The logical next steps from here would be a FastAPI query layer over `MappingRepository`, or integrating `find_coverage_gaps()` into the CCE's noisy-OR triage scoring to prioritise alerts that touch unmapped scenarios.
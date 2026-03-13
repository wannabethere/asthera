# ATT&CK → CIS Control Mapping Agent

A LangGraph-based pipeline that maps MITRE ATT&CK techniques to CIS Controls v8.1
risk scenarios. Combines vector-store semantic retrieval (Qdrant or Chroma) with
LLM-powered reasoning to populate the `controls` field across your scenario registry.

---

## Graph Topology

```
[enrich_attack]           # STIX → ATTACKTechniqueDetail (Postgres cache or GitHub)
      │
[build_query]             # LLM reformulates technique into optimal VS query
      │
[retrieve_scenarios]      # Semantic search → top-k CIS scenarios
      │ (conditional)
      ├─ hits  ──────────→ [map_controls]      # GPT-4o maps ATT&CK → CIS JSON
      └─ empty ──→ [yaml_fallback] → [map_controls]
                                          │
                                   [validate_mappings]  # GPT-4o reviews scores
                                          │
                                      [output]          # Updates registry + summary
                                          │
                                         END
```

---

## Quick Start

### 1. Install
```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...
```

### 2. Ingest CIS scenarios into your vector store
```bash
# Chroma (default, local persist)
python main.py --ingest --yaml cis_controls_v8_1_risk_controls.yaml

# Qdrant
VECTOR_BACKEND=qdrant QDRANT_URL=http://localhost:6333 \
  python main.py --ingest --yaml cis_controls_v8_1_risk_controls.yaml
```

### 3. Map a single technique
```bash
python main.py --technique T1078
python main.py --technique T1059.001 --filter operations_security
```

### 4. Batch mapping → enriched YAML output
```bash
# techniques.txt: one T-number per line
python main.py --batch techniques.txt --output enriched_controls.yaml
```

### 5. Ingest ATT&CK into Postgres (production)
```bash
python main.py --ingest-attack postgresql://user:pass@localhost/ccdb
```

---

## Environment Variables

| Variable              | Default                   | Description                          |
|-----------------------|---------------------------|--------------------------------------|
| `OPENAI_API_KEY`      | —                         | Required for embeddings + LLM calls  |
| `VECTOR_BACKEND`      | `chroma`                  | `chroma` or `qdrant`                 |
| `VECTOR_COLLECTION`   | `cis_controls_v8_1`       | Collection / index name              |
| `CHROMA_PERSIST_DIR`  | `./chroma_store`          | Local Chroma persistence path        |
| `CHROMA_HOST`         | —                         | Remote Chroma server host            |
| `QDRANT_URL`          | `http://localhost:6333`   | Qdrant server URL                    |
| `QDRANT_API_KEY`      | —                         | Qdrant cloud API key                 |
| `EMBEDDING_MODEL`     | `text-embedding-3-small`  | OpenAI embedding model               |
| `RETRIEVAL_TOP_K`     | `5`                       | Candidate scenarios per technique    |

---

## Programmatic Usage

```python
from tools.vectorstore_retrieval import VectorStoreConfig, VectorBackend
from graph import build_graph, run_mapping

config = VectorStoreConfig(
    backend=VectorBackend.CHROMA,
    collection="cis_controls_v8_1",
    openai_api_key="sk-...",
)

graph = build_graph(config, yaml_path="cis_controls_v8_1_risk_controls.yaml")
state = run_mapping(graph, "T1078")

for mapping in state["final_mappings"]:
    print(f"{mapping.scenario_id} | {mapping.confidence} | {mapping.rationale}")

print(state["output_summary"])
```

---

## File Structure

```
attack_control_mapper/
├── state.py                  # AttackControlState TypedDict + sub-models
├── prompts.py                # All prompt templates
├── nodes.py                  # LangGraph node implementations
├── graph.py                  # Graph assembly + run helpers
├── main.py                   # CLI entry point
├── requirements.txt
└── tools/
    ├── attack_enrichment.py  # STIX fetcher + Postgres cache
    ├── vectorstore_retrieval.py  # Qdrant + Chroma retriever + ingestor
    └── control_loader.py     # YAML parser + CISControlRegistry
```

---

## Adding to CCE / LangGraph Workflow

The `build_graph()` call returns a compiled LangGraph that can be invoked as a
sub-graph node inside your larger CCE pipeline:

```python
from attack_control_mapper.graph import build_graph

mapper_graph = build_graph(vs_config, yaml_path="...")

# Inside your outer LangGraph workflow:
workflow.add_node("attack_control_mapper", mapper_graph)
workflow.add_edge("alert_triage", "attack_control_mapper")
```

---

## Extending: Adding Your Own Vector Store

Implement the interface used by `VectorStoreRetriever`:

```python
class MyRetriever:
    def retrieve(self, query, top_k, asset_filter) -> List[RetrievedScenario]: ...
    def ingest(self, scenarios) -> int: ...
```

Then register it in `VectorStoreRetriever.__init__` by adding a new
`VectorBackend` enum value and wiring the new class.

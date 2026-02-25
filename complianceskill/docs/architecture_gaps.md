# Architecture Gap Analysis — Compliance Automation LangGraph System

**Reviewed:** nodes.py (2,067 lines), workflow.py, TOOLS_AND_RETRIEVAL.md, tools_quick_reference.md, CHAT_SUMMARY.md  
**Status:** Ready to build — gaps below must be addressed before production

---

## WHAT'S CONFIRMED BUILT ✅

| Component | Status | Notes |
|-----------|--------|-------|
| `nodes.py` | ✅ Complete | 16 node functions |
| `workflow.py` | ✅ Complete | Full graph with routing |
| 14 Agent Prompts | ✅ Complete | ~230KB in /outputs/prompts/ |
| Tool integration framework | ✅ Complete | `get_tools_for_agent()`, conditional loading |
| `RetrievalService` | ✅ Used | Postgres KB (controls, requirements, risks, scenarios, test_cases) |
| `MDLRetrievalService` | ⚠️ Partial | Only in `dashboard_generator_node` |
| `XSOARRetrievalService` | ⚠️ Partial | Only in `dashboard_generator_node` + `risk_control_mapper_node` |
| Validation chain | ✅ Complete | siem → playbook → test_script → cross_artifact → feedback |
| Refinement loop | ✅ Complete | Max 3 iterations with feedback injection |

---

## GAP 1 — MISSING NODES (Critical 🔴)

**Three agent prompts exist but have zero corresponding node functions.**

### 1A. Gap Analysis Node (`gap_analysis_node`)
- **Prompt exists:** `10_gap_analysis_agent.md`
- **Node in nodes.py:** ❌ Not implemented
- **Workflow routing:** ❌ No route in `workflow.py`
- **Intent routing:** ❌ `route_from_intent_classifier` has no `gap_analysis` branch
- **State output:** ❌ No `gap_analysis_results` field in state

**What it should do:** Uses framework KB + controls to identify missing controls, prioritize by risk-effort matrix, estimate costs/timelines. Outputs structured gap inventory.

**What you need to add:**
```python
# nodes.py
def gap_analysis_node(state) -> state:
    prompt_text = load_prompt("10_gap_analysis_agent")
    tools = get_tools_for_agent("gap_analysis", state=state, conditional=True)
    # retrieve controls, requirements, risks from RetrievalService
    # invoke LLM with prompt + context
    # store result in state["gap_analysis_results"]

# workflow.py
workflow.add_node("gap_analysis", gap_analysis_node)
workflow.add_edge("gap_analysis", "artifact_assembler")

# route_from_intent_classifier
if intent == "gap_analysis":
    return "gap_analysis"

# route_from_plan_executor  
elif next_agent == "gap_analysis":
    return "gap_analysis"
```

---

### 1B. Cross-Framework Mapper Node (`cross_framework_mapper_node`)
- **Prompt exists:** `11_cross_framework_mapper.md`
- **Node in nodes.py:** ❌ Not implemented
- **Workflow routing:** ❌ Not in workflow.py
- **State output:** ❌ No `cross_framework_mappings` field in state

**What it should do:** Maps controls across frameworks (HIPAA ↔ SOC2 ↔ CIS), finds consolidation opportunities, outputs equivalency tables with coverage percentages.

**What you need to add:**
```python
# nodes.py
def cross_framework_mapper_node(state) -> state:
    prompt_text = load_prompt("11_cross_framework_mapper")
    # retrieve controls for multiple frameworks
    # invoke LLM 
    # store result in state["cross_framework_mappings"]

# workflow.py
workflow.add_node("cross_framework_mapper", cross_framework_mapper_node)
workflow.add_edge("cross_framework_mapper", "artifact_assembler")
```

---

### 1C. LLM Application Test Generator (Agent 12)
- **Prompt exists:** `12_llm_application_test_generator.md`
- **Current `test_generator_node` loads:** `"09_test_generator"` (the operational test generator for controls)
- **Agent 12 purpose:** Tests the AI agents themselves — schema validation, hallucination detection, adversarial testing
- **Status:** ❌ No node; prompt 09 and prompt 12 are conflated

**Fix:** Keep `test_generator_node` for prompt 09. Add a separate `llm_test_generator_node` that loads prompt 12. This would be invoked during CI/CD testing, not during normal pipeline execution — likely a separate subgraph or invoked standalone.

---

## GAP 2 — METRICS REGISTRY NOT INTEGRATED (High 🔴)

You stated: **"I have metrics registry in Qdrant DB collections."**

This is **not referenced anywhere** in nodes.py, workflow.py, or the retrieval docs.

**What's happening now:**
- `MDLRetrievalService` in `dashboard_generator_node` pulls `mdl_result.metrics` — but this assumes metrics are part of MDL schemas, not a dedicated collection
- No `metrics_registry` Qdrant collection is searched
- No node other than `dashboard_generator` uses metrics data

**What you likely have:**
- A Qdrant collection: `metrics_registry` (or similar name) containing KPI definitions, metric formulas, thresholds, compliance metric definitions
- This data should flow into: **gap analysis** (measure current vs. target), **dashboard generator** (source of truth for KPIs), **artifact assembler** (quality scoring), **cross-framework mapper** (coverage %)

**What you need:**
```python
# New retrieval in MetricsRetrievalService or extend MDLRetrievalService
async def search_metrics_registry(query: str, limit: int = 10) -> List[MetricDefinition]:
    results = await self.qdrant_client.search(
        collection_name="metrics_registry",
        query_vector=await self.embed(query),
        limit=limit
    )
    return [MetricDefinition(**r.payload) for r in results]

# Add to state schema
"metrics_context": List[Dict]  # Metric definitions from registry

# Use in: gap_analysis_node, dashboard_generator_node, artifact_assembler_node
```

**Action needed:** Clarify the exact Qdrant collection name and schema for the metrics registry so retrieval can be wired in.

---

## GAP 3 — INCONSISTENT QDRANT RETRIEVAL ACROSS NODES (Medium 🟡)

Only 2 of 16 nodes use XSOAR/MDL Qdrant retrieval. The others rely only on Postgres.

| Node | Postgres (RetrievalService) | MDL Qdrant | XSOAR Qdrant | Metrics Qdrant |
|------|-----------------------------|------------|--------------|----------------|
| `intent_classifier` | ❌ | ❌ | ❌ | ❌ |
| `planner` | ❌ | ❌ | ❌ | ❌ |
| `plan_executor` | ✅ | ❌ | ❌ | ❌ |
| `framework_analyzer` | ✅ | ❌ | ❌ | ❌ |
| `detection_engineer` | ✅ | ❌ | ❌ | ❌ |
| `playbook_writer` | ✅ | ❌ | ❌ | ❌ |
| `test_generator` | ✅ | ❌ | ❌ | ❌ |
| `dashboard_generator` | ✅ | ✅ | ✅ (dashboards) | ❌ |
| `risk_control_mapper` | ✅ | ❌ | ✅ (playbooks/scripts) | ❌ |

### Missing Qdrant retrieval by node:

**`detection_engineer_node`** should retrieve:
- `xsoar_playbooks`: detection/response patterns for the threat being modeled
- `xsoar_indicators`: IOC patterns to embed in SIEM rules (this collection is NEVER used anywhere)

**`playbook_writer_node`** should retrieve:
- `xsoar_playbooks`: reference playbooks as templates
- `xsoar_indicators`: IOC patterns for triage steps

**`test_generator_node`** should retrieve:
- `mdl_schemas`: table/field definitions for writing accurate test queries
- `xsoar_playbooks`: validation patterns used in automation testing

**`gap_analysis_node`** (once built) should retrieve:
- `metrics_registry`: target metric thresholds to measure gaps against
- `mdl_schemas`: data model context for understanding current state

### The `xsoar_indicators` collection is NEVER queried
- Defined in CHAT_SUMMARY architecture as a Qdrant collection
- Contains IOC patterns for detection
- Zero nodes search it
- Should feed into: `detection_engineer_node` (SIEM rule IOC patterns) and `playbook_writer_node` (triage IOC context)

---

## GAP 4 — TOOL STUBS USED IN PRODUCTION NODES (Medium 🟡)

Four tools are stubs (`🚧`) but are listed as "always loaded" for active nodes:

| Stub Tool | Loaded For | Risk |
|-----------|-----------|------|
| `gap_analysis` | test_generator | Silent no-op — LLM gets no gap data |
| `attack_path_builder` | detection_engineer, playbook_writer | LLM thinks it called this, gets empty result |
| `risk_calculator` | detection_engineer, playbook_writer, risk_control_mapper | Risk scores will be hallucinated |
| `remediation_prioritizer` | (available in registry) | No prioritization data |

**Immediate risk:** The LLM calls these tools, receives stub/empty responses, and may hallucinate results or silently skip enrichment. Stub tools should either return a clear `"NOT_IMPLEMENTED"` message so the LLM knows to skip, or be removed from tool lists until implemented.

---

## GAP 5 — DB TABLES NEEDED FOR CORE INTELLIGENCE (Medium 🟡)

Several `⚠️ Needs DB` tools are critical for the CVE→ATT&CK→Control flow (Agent 14 / `risk_control_mapper`):

| Table | Used By | Priority |
|-------|---------|----------|
| `cve_attack_mapping` | `cve_to_attack_mapper` tool | **P0** — Core mapping |
| `attack_technique_control_mapping` | `attack_to_control_mapper` tool | **P0** — Core mapping |
| `cpe_dictionary` + `cve_cpe_affected` | `cpe_resolver` | P1 |
| `metasploit_modules` | `metasploit_module_search` | P1 |
| `nuclei_templates` | `nuclei_template_search` | P1 |
| `exploit_db_index` | `exploit_db_search` | P1 |
| `cis_benchmark_rules` | `cis_benchmark_lookup` | P2 |

Without `cve_attack_mapping` and `attack_technique_control_mapping`, the `risk_control_mapper_node` falls back entirely to LLM reasoning for CVE→ATT&CK→Control mappings — which will hallucinate technique IDs and control codes.

---

## GAP 6 — STATE SCHEMA MISSING FIELDS (Low-Medium 🟡)

`EnhancedCompliancePipelineState` (in `app/agents/state.py`, not uploaded) likely does not define:

| Field | Needed By | Type |
|-------|-----------|------|
| `gap_analysis_results` | gap_analysis_node output | `List[Dict]` |
| `cross_framework_mappings` | cross_framework_mapper_node output | `List[Dict]` |
| `metrics_context` | metrics registry retrieval | `List[Dict]` |
| `llm_test_results` | llm_test_generator_node output | `List[Dict]` |
| `xsoar_indicators` | xsoar_indicators collection retrieval | `List[Dict]` |

`risk_control_mapper_node` writes to `state["vulnerability_mappings"]` (line 2056) — verify this field is in the state TypedDict, otherwise it's a runtime KeyError.

---

## GAP 7 — WORKFLOW ROUTING INCOMPLETE (Low 🟢)

In `workflow.py`, `route_from_plan_executor` handles these `next_agent` values:
```python
["framework_analyzer", "detection_engineer", "playbook_writer", 
 "test_generator", "dashboard_generator", "risk_control_mapper", "pipeline_builder"]
```

Missing from routing:
- `"gap_analysis"` → needs node + route
- `"cross_framework_mapper"` → needs node + route
- `"llm_test_generator"` → needs node + route
- `"pipeline_builder"` → listed in routing but **no node exists** for it

`"pipeline_builder"` appears in both `route_from_plan_executor` and `route_from_feedback_analyzer` but the node is never added to the workflow. This will cause a `KeyError` at runtime if the planner ever sets `next_agent = "pipeline_builder"`.

---

## GAP 8 — WHAT'S NOT DONE (Confirmed)

From CHAT_SUMMARY — confirmed still missing:
- ❌ API endpoints (FastAPI routers)
- ❌ Web UI
- ❌ State persistence beyond MemorySaver (Redis/PostgreSQL checkpointer for production)
- ❌ `app/agents/tools/__init__.py` — tool registry and factory functions
- ❌ `app/retrieval/service.py` — full RetrievalService implementation
- ❌ `app/retrieval/xsoar_service.py` — XSOARRetrievalService
- ❌ `app/retrieval/mdl_service.py` — MDLRetrievalService
- ❌ Data ingestion jobs (NVD, CISA KEV, EPSS, ATT&CK STIX, Exploit-DB)
- ❌ API keys configured (TAVILY, OTX, VirusTotal)

---

## PRIORITY BUILD ORDER

```
WEEK 1 — Close Critical Gaps
├── 1. Add gap_analysis_node (prompt 10 exists, ~80 lines of code)
├── 2. Add cross_framework_mapper_node (prompt 11 exists, ~80 lines)
├── 3. Fix pipeline_builder phantom route in workflow.py (remove or add node)
├── 4. Wire xsoar_indicators retrieval into detection_engineer + playbook_writer
└── 5. Clarify metrics_registry collection schema → wire into dashboard_generator + gap_analysis

WEEK 2 — Data Infrastructure
├── 6. Create P0 DB tables: cve_attack_mapping, attack_technique_control_mapping
├── 7. Implement cve_to_attack_mapper + attack_to_control_mapper tools (remove stub)
├── 8. Build data ingestion jobs: NVD daily, ATT&CK weekly, CISA KEV daily
└── 9. Implement risk_calculator tool (currently stub, always loaded for 3 nodes)

WEEK 3 — Hardening
├── 10. Add state fields: gap_analysis_results, cross_framework_mappings, metrics_context
├── 11. Update state TypedDict with vulnerability_mappings (runtime risk today)
├── 12. Replace silent stubs with NOT_IMPLEMENTED responses
├── 13. Add llm_test_generator_node as separate subgraph
└── 14. Add production checkpointer (PostgreSQL or Redis)
```

---

## QUESTIONS TO RESOLVE BEFORE BUILDING

1. **Metrics Registry collection:** What is the exact Qdrant collection name? What does a metric record look like (fields: metric_id, name, formula, threshold, framework_id, category)?

2. **MDL schemas vs. Metrics:** Are metrics stored inside `mdl_schemas` collection or in a separate `metrics_registry` collection? The current code (`mdl_result.metrics`) suggests they're embedded in MDL results.

3. **`pipeline_builder` agent:** Was this planned as a node that dynamically builds pipeline configs? If so, what prompt does it use? If not, remove it from `route_from_plan_executor`.

4. **Agent 12 (LLM Test Generator):** Should this run as part of every pipeline execution, or only as a CI/CD validation tool? This determines whether it needs a workflow node or is a standalone script.

5. **Cross-framework mapper state output:** When the mapper runs, should it write to `state["cross_framework_mappings"]` as a list of equivalencies, or produce a full compliance coverage matrix?

6. **Production checkpointer:** Are you using PostgreSQL (existing infra) or Redis for LangGraph state persistence in production?
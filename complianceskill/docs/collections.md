# Collections Used in Compliance Skill

This document lists all collections actively used in the Compliance Skill system. Collections are organized by category and accessed via specific services.

## Collections Registry

All collection names are defined in `app/storage/collections.py` for a single source of truth.

---

## 1. Framework Knowledge Base Collections (Qdrant)

**Accessed via:** `RetrievalService` (in `app/retrieval/service.py`)

**Collections:**
- `framework_controls` - Compliance controls (HIPAA, SOC2, CIS, NIST, ISO, PCI-DSS)
- `framework_requirements` - Framework requirements
- `framework_risks` - Risk scenarios
- `framework_test_cases` - Test cases for control validation
- `framework_scenarios` - Attack scenarios
- `user_policies` - User-uploaded policy documents

**Total:** 6 collections

**Note:** These collections are managed by `app/storage/qdrant_framework_store.py` and accessed via `RetrievalService` methods like `search_controls()`, `search_risks()`, etc.

---

## 2. MDL Collections (Qdrant/ChromaDB)

**Accessed via:** `MDLRetrievalService` (in `app/retrieval/mdl_service.py`)

**Collections:**
- `leen_db_schema` - Database schema DDL chunks (TABLE + TABLE_COLUMNS)
- `leen_table_description` - Table descriptions with columns and relationships
- `leen_project_meta` - Project metadata (one per file)
- `leen_metrics_registry` - Metric definitions, KPIs, trends, filters

**Total:** 4 collections

**Note:** These collections are initialized in `get_doc_store_provider()` and accessed via `MDLRetrievalService.search_all_mdl()`.

---

## 3. XSOAR Collections (Qdrant/ChromaDB)

**Accessed via:** `XSOARRetrievalService` (in `app/retrieval/xsoar_service.py`)

**Collections:**
- `xsoar_enriched` - XSOAR content with `entity_type` filtering:
  - `entity_type="playbook"` - Response playbooks
  - `entity_type="dashboard"` - Dashboard examples
  - `entity_type="script"` - Enrichment and analysis scripts
  - `entity_type="integration"` - Vulnerability scanner integrations
  - `entity_type="indicator"` - IOC patterns and detection signals

**Total:** 1 collection (with 5 entity types)

**Note:** This collection is initialized in `get_doc_store_provider()` and accessed via `XSOARRetrievalService.search_all_xsoar()`.

---

## 4. Comprehensive Indexing Collections (Qdrant/ChromaDB)

**Accessed via:** `CollectionFactory` (in `app/storage/query/collection_factory.py`)

**Used by:** Workforce assistants (Product Assistant, Compliance Workforce Assistant)

**Collections:**
- `domain_knowledge` - Policies, risks, products (filtered by `metadata.type`)
- `compliance_controls` - Compliance controls
- `entities` - General entities (filtered by `metadata.type`)
- `evidence` - Evidence documents (filtered by `metadata.type`)
- `fields` - Field definitions (filtered by `metadata.type`)
- `controls` - General controls (filtered by `metadata.type`)
- `policy_documents` - Policy documents
- `table_definitions` - Table definitions (unprefixed)
- `table_descriptions` - Table descriptions (unprefixed)
- `column_definitions` - Column definitions (unprefixed)
- `schema_descriptions` - Schema descriptions (unprefixed)
- `features` - Feature knowledge base
- `contextual_edges` - Relationship edges between tables/entities

**Total:** 13 collections

**Note:** These collections may have a `collection_prefix` applied (e.g., `comprehensive_index_*`). Schema collections are always unprefixed. These are primarily used by workforce assistants, not the main compliance skill workflow.

---

## Summary

### Active Collections in Compliance Skill Workflow

**Total Active:** 11 collections
- Framework KB: 6 collections
- MDL: 4 collections
- XSOAR: 1 collection

### All Collections (Including Workforce Assistants)

**Total All:** 24 collections
- Framework KB: 6 collections
- MDL: 4 collections
- XSOAR: 1 collection
- Comprehensive Indexing: 13 collections

---

## Collection Access Patterns

### Framework KB Collections
```python
from app.retrieval.service import RetrievalService

service = RetrievalService()
context = service.search_controls(query="access control", framework_filter=["hipaa"])
```

### MDL Collections
```python
from app.retrieval.mdl_service import MDLRetrievalService

service = MDLRetrievalService()
context = await service.search_all_mdl(query="compliance metrics", limit_per_collection=5)
```

### XSOAR Collections
```python
from app.retrieval.xsoar_service import XSOARRetrievalService

service = XSOARRetrievalService()
context = await service.search_all_xsoar(
    query="log4j detection",
    entity_types=["playbook", "indicator"],
    limit_per_entity_type=10
)
```

### Comprehensive Indexing Collections
```python
from app.storage.query.collection_factory import CollectionFactory

factory = CollectionFactory(vector_store_client=client, embeddings_model=embeddings)
results = await factory.search_compliance(query="HIPAA controls", top_k=10)
```

---

## Removed Collections

The following Knowledge App collections were **removed** from `dependencies.py` as they are not used in the compliance skill:

- `db_schema` (replaced by `leen_db_schema`)
- `sql_pairs` (not used)
- `instructions` (not used)
- `historical_question` (not used)
- `table_descriptions` (replaced by `leen_table_description`)
- `project_meta` (replaced by `leen_project_meta`)
- `document_insights` (not used)
- `document_planning` (not used)
- `alert_knowledge_base` (not used)
- `column_metadata` (not used)
- `sql_functions` (not used)

---

## Collection Registry Location

All collection names are centrally defined in:
- **`app/storage/collections.py`** - Single source of truth for all collection names

Use this module to:
- Get collection names programmatically
- Check if a collection is actively used
- Get collection information by category

```python
from app.storage.collections import (
    FrameworkCollections,
    MDLCollections,
    XSOARCollections,
    ComplianceSkillCollections
)

# Get all active collections
active = ComplianceSkillCollections.get_all_active_collections()

# Get collection info
info = ComplianceSkillCollections.get_collection_info()
```



GAP From analysis for the following to be addressed: 


---

## Example Use Case

**"For HIPAA § 164.312(b) Audit Controls, validate my risk and control coverage and show me a compliance dashboard"**

Expected chain:
```
HIPAA § 164.312(b) [Framework]
    → Unauthorized ePHI Access Risk [Risk]
        → Audit Logging Control (AU-12, AC-7) [Control]
            → Failed login spikes, audit log gaps [Signal]
                → HIPAA Audit Compliance KPIs [Metrics/Dashboard]
```

---

## What CURRENTLY Works ✅

**Framework → Risk → Control** (first half of the chain)

This part is solid. Here's how it flows:

1. `intent_classifier_node` sets `framework_id = "hipaa"`, `requirement_code = "164.312(b)"`
2. `planner_node` creates steps for requirement lookup, risk retrieval, control retrieval
3. `plan_executor_node` fires `intelligent_retrieval()` against:
   - `framework_requirements` → finds §164.312(b) requirement record
   - `framework_risks` → finds associated risks (unauthorized access to ePHI, audit failure)
   - `framework_controls` → finds AU-12, AC-7 controls
4. `framework_analyzer_node` does the direct DB lookups when exact IDs are resolved

This three-hop retrieval works today. The Postgres + Qdrant collections (`framework_requirements`, `framework_risks`, `framework_controls`) are properly wired through `RetrievalService` and `intelligent_retrieval()`.

**Dashboard generation in isolation** also works — when the intent is `dashboard_generation`, it routes directly to `dashboard_generator_node` which queries `leen_metrics_registry` and `xsoar_enriched` (entity_type=dashboard).

---

## Where It Breaks Down 🔴

### Gap A — No Single Intent Covers the Full Chain

The intent classifier today routes to one of these discrete intents:
- `requirement_analysis` → framework/risk/control path
- `dashboard_generation` → bypasses everything, goes direct to dashboard
- `detection_engineering` → goes to SIEM rule generation

There is **no composite intent** like `validate_compliance_chain` that would sequence the full framework → risk → control → signal → dashboard pipeline in a single invocation.

If you submit the use case above today, you get **either** the controls analysis **or** a dashboard, not both connected. You'd need two separate queries, and the dashboard wouldn't know which controls were retrieved in the first query.

---

### Gap B — Signal Generation Doesn't Pull from `xsoar_enriched` (Indicators)

`detection_engineer_node` generates SIEM rules using:
- Controls from state (from framework_controls)
- ATT&CK tools (when DB tables exist)
- General LLM reasoning

What it **doesn't** do: query `xsoar_enriched` with `entity_type="indicator"` to retrieve actual IOC patterns. These are your pre-built detection signals — things like the `${jndi:` pattern for Log4j or specific regex patterns for credential stuffing. The detection engineer generates signals from scratch instead of anchoring to your curated indicator library.

The `xsoar_enriched` collection exists. The entity_type filtering capability exists. But `detection_engineer_node` has zero retrieval code targeting it.

---

### Gap C — The Dashboard Doesn't Know Which Controls Were Validated

This is the biggest structural gap. When `dashboard_generator_node` queries `leen_metrics_registry`, it does a **semantic search** with the user's original query. It has no awareness of:

- Which specific controls were retrieved in steps 1-3 (AU-12, AC-7)
- Which risks were identified (unauthorized ePHI access)
- Which SIEM rules were generated

So the dashboard will show generic "HIPAA Audit Compliance" KPIs rather than KPIs specifically scoped to the controls that were validated. The metrics are decoupled from the chain state.

For the metrics to be meaningful in this flow, `leen_metrics_registry` would need to be queried with the **control IDs as filters**, not just a free-text query. The state carries the controls, but `dashboard_generator_node` doesn't use them as retrieval anchors.

---

### Gap D — `framework_scenarios` Collection Is Underused as a Bridge

Your `framework_scenarios` collection contains attack scenarios — these are the natural bridge between Risk and Signal. The scenario for "unauthorized ePHI access" would describe *how* the risk materializes (e.g., brute force, credential stuffing, insider access), which directly informs what signals to generate.

Currently, `plan_executor_node` may retrieve scenarios as part of retrieval queries, but no node specifically uses the scenario to drive signal generation logic. The detection engineer gets scenarios in its context but they're mixed in with controls and risks — there's no "scenario → signal" reasoning step enforced by the architecture.

---

### Gap E — No Chain Validation Node

You used the word "validate" in your question. The current validators (`siem_rule_validator`, `playbook_validator`, `cross_artifact_validator`) validate **artifact quality** — syntax, completeness, format.

No node validates the **semantic chain**: "Does this SIEM rule actually detect signals relevant to this control?" and "Does this control actually address the identified risk?" and "Does the dashboard metric actually measure the control effectiveness?"

The `cross_artifact_validator_node` is the closest thing, but looking at the code it cross-validates consistency across generated artifacts, not traceability back to the original framework requirement.

---

## Summary Table

| Chain Step | Retrieval Collection | Node Responsible | Works Today? |
|---|---|---|---|
| Framework → Requirement | `framework_requirements` | `framework_analyzer_node` | ✅ Yes |
| Requirement → Risk | `framework_risks` | `plan_executor_node` (intelligent_retrieval) | ✅ Yes |
| Risk → Control | `framework_controls` | `plan_executor_node` + `framework_analyzer_node` | ✅ Yes |
| Control → Attack Scenario | `framework_scenarios` | `plan_executor_node` | ⚠️ Retrieved but not driven |
| Scenario → Signal (IOCs) | `xsoar_enriched` [indicator] | `detection_engineer_node` | ❌ Not queried |
| Control → SIEM Rule | ATT&CK tools + LLM | `detection_engineer_node` | ⚠️ Works without DB tables |
| Controls → Metrics | `leen_metrics_registry` | `dashboard_generator_node` | ⚠️ Not control-scoped |
| Metrics → Dashboard | `xsoar_enriched` [dashboard] | `dashboard_generator_node` | ✅ Works in isolation |
| Chain Semantic Validation | None | None | ❌ Doesn't exist |
| Single-invocation full chain | — | No composite intent | ❌ Two queries needed |

---

## The Minimum Fixes to Make This Possible

You don't need new agents. You need:

1. **A composite intent** — something like `compliance_validation` that tells the planner to sequence framework analysis → signal generation → dashboard in one plan, passing state through all steps

2. **`detection_engineer_node` queries `xsoar_enriched` (entity_type=indicator)** — same pattern already used in `dashboard_generator_node` and `risk_control_mapper_node` for XSOAR retrieval

3. **`dashboard_generator_node` uses `state["controls"]` as retrieval anchors** — filter `leen_metrics_registry` by the control IDs already in state, not just the raw user query

4. **`framework_scenarios` drives the detection engineer** — the scenario for the risk should be the primary context for signal generation, not just additional context alongside controls

The agent prompts (10, 11, 13, 14) already describe this chain conceptually. The gap is purely in the orchestration layer — intent routing and how state flows from the retrieval nodes into the signal and dashboard nodes.
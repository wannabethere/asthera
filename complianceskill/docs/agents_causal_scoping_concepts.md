# Agents: causal graph, area scoping, and concept narrowing

Reference for where CSOD / planner code loads data and which files participate.

## Causal nodes and edges

| Role | Path |
|------|------|
| LangGraph node → CSOD state | `app/agents/csod/csod_nodes/node_causal.py` (`csod_causal_graph_node`) |
| Orchestrator | `app/agents/causalgraph/causal_graph_nodes.py` (`causal_graph_creator_node`) |
| Vector retrieval + LLM assembly | `app/agents/causalgraph/vector_causal_graph_builder.py` |
| Signals / focus boost / node index | `app/agents/causalgraph/causal_context_extractor.py` |
| Optional attribution | `app/agents/causalgraph/cce_attribution.py` |
| Hybrid retrieval (vector + Postgres) | `app/agents/csod/csod_causal_graph.py` |
| Domain scores for retrieval | `app/agents/causalgraph/lexy_domain_context.py` |
| Per-domain collection names | `app/agents/domain_config.py`, `config/domains/*.json` |

**State keys (CSOD):** `csod_causal_nodes`, `csod_causal_edges`, `csod_causal_graph_metadata`, `csod_causal_centrality`, `causal_signals`, etc.

**Vector collections:** defaults from `app/core/settings.py` — `LMS_CAUSAL_NODES_COLLECTION`, `LMS_CAUSAL_EDGES_COLLECTION`, plus seed path settings (`LMS_CAUSAL_*_SEED_PATH`, `LMS_CAUSAL_EDGES_PATH`, …).

**In-repo seed example:** `app/agents/causalgraph/data/lms_causal_edge_seed.json`

## Area scoping

| Role | Path |
|------|------|
| Planner graph (order + nodes) | `app/conversation/planner_workflow.py` — `preliminary_area_matcher` → `scoping` → `area_matcher` → `area_confirm` → … |
| Scoping checkpoint + filter chips | `app/conversation/nodes/scoping.py` |
| L2: scoping answers → areas | `app/ingestion/registry_vector_lookup.py` — `resolve_scoping_to_areas()` |
| Scoping question definitions | `app/conversation/config.py` — `ScopingQuestionTemplate`, `VerticalConversationConfig` |

**Vector / JSON backing (registry):** `registry_vector_lookup.py` uses L2 collection (`MDLCollections.CSOD_L2_RECOMMENDATION_AREAS` when importable) and JSON under `registries/` or `preview_out/registries/` (`source_concept_registry.json`, `concept_recommendation_registry.json`), plus `data/csod_project_metadata_enriched.json` where referenced.

**Focus-area taxonomy (static):** `config/lms_focus_area_taxonomy.json` (copy also under `docs/csod_data_engineering/`).

**Shared pipeline state:** `app/agents/state.py` — e.g. `resolved_focus_areas`, `focus_area_categories`; planner uses `csod_llm_resolved_areas`, `csod_scoping_answers`, `csod_area_matches`, `csod_primary_area`.

## Concept narrowing (intent → concept → projects → areas)

| Role | Path |
|------|------|
| Planner sequence | `app/conversation/planner_workflow.py` — `intent_splitter` → `mdl_project_resolver` → `csod_intent_confirm` |
| Query → 1–3 intents + signals | `app/ingestion/intent_splitter.py` |
| Intents → concepts / projects / areas (LLM + JSON) | `app/ingestion/mdl_intent_resolver.py` |
| User checkpoint + resume into legacy keys | `app/conversation/nodes/csod_intent_confirm.py` |
| Inline L1-style context (CSOD graph) | `app/agents/csod/csod_nodes/node_concept_context.py` |

**Primary JSON inputs for MDL resolution:** `preview_out/data/csod_project_metadata_enriched.json` and `preview_out/data/csod_project_metadata.json` (paths defined in `mdl_intent_resolver.py`).

**Legacy planner + vector concept resolver:** `archived/csod/csod_planner_workflow_legacy.py` (`csod_concept_resolver_node`); L1 lookup in `registry_vector_lookup.py` — `resolve_intent_to_concept()`.

## Related prompts

- Analysis planner mentions `focus_areas` / narrowing: `app/agents/prompt_utils/csod/30_analysis_planner.md`
- Follow-up scope changes: `app/agents/prompt_utils/csod/28_followup_router.md`

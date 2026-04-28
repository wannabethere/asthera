
User types question + clicks Send
      │
      ▼
[UI] cpSend() → addMsgToConv(user) → _showAnalysisModeChoice()
      │
      ▼
[UI] Inline assistant bubble appears with 2 buttons:
     ┌──────────────────┐  ┌──────────────────┐
     │  Direct answer   │  │ Explore metrics  │
     └──────────────────┘  └──────────────────┘
      │                       │
   user picks ─────────►  _pickAnalysisMode(mode, cardId)
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
       mode === 'direct'              mode === 'explore'
       initial_state =                no extra state
       { csod_planner_only:true }     (existing behavior)
              │                               │
              ▼                               ▼
       streamReply(conv, msg, opts)   streamReply(conv, msg)
       
Direct flow (csod_planner_only: true)

[UI] streamReply(conv, msg, { initial_state: { csod_planner_only: true } })
  POST /api/v1/chat/send  body: { query, thread_id, initial_state, agent_id: 'csod-planner', ... }
      │
      ▼
[astherabackend] chat.py /send
  • Creates user + assistant ThreadMessage rows in DB
  • Resolves agent_id → 'csod-planner'
  • _extra_payload = { thread_id, initial_state }
  • client.invoke_agent_stream(agent_id='csod-planner', extra_payload=_extra_payload)
      │
      │ POST compliance-skill /v1/agents/invoke
      │ body: { agent_id, input, thread_id, initial_state, ... }
      ▼
[compliance-skill] agents.py /v1/agents/invoke
  • InvokeRequest (extra="allow") → keeps initial_state
  • payload = request.model_dump()  (includes initial_state)
  • invocation_service.invoke_agent(agent_id='csod-planner', payload, ...)
      │
      ▼
[compliance-skill] agent_invocation_service.invoke_agent
  • Resolves csod-planner agent + adapter (CSODLangGraphAdapter wrapping conversation planner workflow)
  • Calls adapter.stream(payload, context, config)
      │
      ▼
[compliance-skill] base_langgraph_adapter._build_graph_input
  • Merges payload['initial_state'] into graph_input  ← csod_planner_only flows in
      │
      ▼
[compliance-skill] conversation planner workflow runs
  • intent_splitter (1 LLM call)               ─► SSE: state_update / node events
  • mdl_intent_resolver                        ─► SSE: state_update
  • csod_intent_confirm
      ─ planner_only?  YES  → auto-pick all intents (no checkpoint)
      ─ planner_only?  NO   → emit intent_selection checkpoint
  • concept_confirm  (auto if already confirmed)
  • datasource auto-select (cornerstone)
  • area_matcher
  • area_confirm                               ─► SSE: checkpoint (area_confirm)  ⏸ pause
      │
      ▼ user picks area in UI → POST /api/v1/workflow/checkpoint → resume
      ▼
  • metric_narration (auto-confirmed)
  • Final routing step
      ─ planner_only?  YES  → next_agent_id = None  (skip chain)
      ─ planner_only?  NO   → next_agent_id = 'csod-workflow'
      │
      ▼
[compliance-skill] adapter emits STEP_FINAL with final_state
      │
      ▼
[compliance-skill] agent_invocation_service after adapter.stream():
  ┌────────────────────────────────────────────────────────────┐
  │ if planner_output AND next_agent_id  → chain (Explore path)│
  │ else if csod_planner_only            → preview short-circuit│
  └────────────────────────────────────────────────────────────┘
      │
      ▼
[compliance-skill] Direct short-circuit
  • generate_single_preview(name=user_question, nl_question=user_question,
                            focus_area=primary_area, source_tables=[...])
      ─ ONE LLM call (summary, insights, chart spec)
      ─ + dummy result_data based on schema
  • SSE: TOKEN  { content: markdown summary }
  • SSE: STEP_FINAL { preview: { summary, insights, vega_lite_spec, result_data, ... },
                     planner_only: true }
  • return  ← no chain, no other agent
      │
      ▼
[astherabackend] chat.py forwards events through process_event() → SSE to UI
      │
      ▼
[UI] processStream
  • TOKEN          → typed into chat bubble (markdown summary)
  • step_final     → detects p.preview → _renderInlinePreview(msgEl, preview)
                     reuses _renderPreviewCardContent → chart + insights card in bubble
  Stream ends.



  Explore flow (no flag — existing behavior)


  [UI] streamReply(conv, msg)   ← no initial_state
  POST /api/v1/chat/send  body: { query, thread_id, agent_id: 'csod-planner', ... }
      │
      ▼
[astherabackend] chat.py /send
  Same as Direct, but _extra_payload = { thread_id }  (no initial_state)
      │
      ▼
[compliance-skill] /v1/agents/invoke → agent_invocation_service → CSODLangGraphAdapter
      │
      ▼
[compliance-skill] conversation planner workflow runs
  • intent_splitter
  • mdl_intent_resolver
  • csod_intent_confirm  ──────────────► SSE: checkpoint (intent_selection)  ⏸
      ▲ user picks intent → POST /api/v1/workflow/checkpoint → resume
  • concept_confirm     ──────────────► SSE: checkpoint (concept_select) if needed  ⏸
  • datasource auto-select
  • area_matcher
  • area_confirm        ──────────────► SSE: checkpoint (area_confirm)  ⏸
      ▲ user picks area → resume
  • metric_narration (auto-confirmed)
  • Final routing → next_agent_id = 'csod-workflow', is_planner_output = True
      │
      ▼
[compliance-skill] adapter emits STEP_FINAL with planner_output + next_agent_id='csod-workflow'
      │
      ▼
[compliance-skill] agent_invocation_service:
  planner_output AND next_agent_id  → _chain_to_next_agent('csod-workflow', planner_output)
      │
      ▼
[compliance-skill] csod-workflow agent (CSOD Phase 1 graph) runs
  • csod_followup_router
  • csod_intent_classifier
  • skill_intent_identifier → skill_analysis_planner
  • csod_analysis_mode_selector  (no-op, sets explore)
  • csod_mdl_schema_retrieval_early
  • csod_analysis_planner          (heavy LLM call)
  • csod_causal_graph
  • csod_cross_concept_check       ─► SSE: checkpoint (cross_concept_check) if areas exist  ⏸
  • csod_metrics_retrieval
  • csod_metric_qualification
  • csod_layout_resolver
  • skill_recommender_prep
  • csod_metrics_recommender
  • skill_validator
  • csod_metric_selection          ─► SSE: checkpoint (metric_selection)  ⏸
      ▲ user picks metrics → resume
  • END
      │
      ▼
[compliance-skill] adapter emits STEP_FINAL with metric_recommendations + kpi_recommendations
      │
      ▼
[UI] processStream + _handleWorkflowComplete
  • Renders metric/KPI/table placeholder cards
  • Per card → POST /api/v1/workflow/preview_item (one LLM call each)
  • _renderPreviewCardContent populates each card with chart, summary, insights
  Stream ends.



Key SSE event types (frontend-facing)
Event	Direct flow	Explore flow
agent_start	✓	✓
node_start / node_complete	✓ planner nodes	✓ planner + workflow nodes
state_update	✓ planner state	✓ planner + workflow state
checkpoint (area_confirm)	✓ if multi-area	✓
checkpoint (intent_selection)	✗ auto-confirmed	✓ if multi-intent
checkpoint (cross_concept_check)	✗	✓ if cross-concept areas
checkpoint (metric_selection)	✗	✓
token (markdown summary)	✓ once	✗
step_final (with preview)	✓ inline preview	✗
step_final (with metric_recommendations)	✗	✓
workflow_complete / agent_end	✓	✓

# CSOD Planner Workflow — Flow Redesign Fix Plan

**Scope:** `csod_planner_workflow.py` · `skills_config.json` · `data/prompts/csod/`

---

## 1. What Is Wrong Today

### 1.1 Current graph topology

```
csod_planner_router
  → csod_datasource_selector   (optional)
    → csod_concept_resolver    (vector search only, no LLM)
      → csod_area_matcher      (scoping_answers always {})
        → csod_skill_identifier  ← WRONG POSITION
          → csod_workflow_router
```

### 1.2 The three design problems

**Problem A — Datasource selection blocks concept resolution**

The planner treats datasource selection as a hard prerequisite. In the no-datasource flow (user does not specify a platform), the LLM identification step runs, finds `cornerstone` with high confidence, then still creates a `datasource_select` checkpoint asking the user to confirm. Only after that confirmation does concept_resolver run. This doubles the turn count for no reason and, when the checkpoint state is mis-handled across turns (see the loop bug history), concept resolution never runs at all.

In the datasource-provided flow, `csod_datasource_confirmed=True` is set immediately, the anti-loop guard fires in `csod_datasource_selector_node`, and the graph jumps directly to concept_resolver — but the stale checkpoint left in state from a previous turn can still block it.

**Problem B — Concept resolver is pure vector search with no LLM reasoning**

`csod_concept_resolver_node` calls `resolve_intent_to_concept()` and presents the raw vector matches to the user. The scores in your logs (`0.3984`, `0.3265`) are not high — the system is not confident which concept fits. There is no step where the LLM reads the user query and the top-N candidates and decides which is most likely correct before presenting it to the user. The user is asked to choose from a list with no framing or recommendation.

**Problem C — Skill identifier runs AFTER area matching, but skill determines which scoping questions to ask**

The area matcher calls `resolve_scoping_to_areas()` with `scoping_answers={}` always because no scoping node exists. Scoping questions (what the plan designs as `compliance_scope_node`) depend on what skill was identified — a `metrics_recommendations` skill needs time_window and org_unit; a `dashboard_generation` skill needs persona. Running skill identification after area matching means the area is resolved without the additional info it needs, and the additional info cannot be customised per skill.

---

## 2. Target Graph Topology

```
csod_planner_router
  → csod_datasource_selector    (OPTIONAL — skip if datasource already known)
    → csod_concept_resolver     (vector search + LLM ranking → concept checkpoint)
      → csod_skill_identifier   ← MOVED UP (after concept, before scoping)
        → csod_scoping_node     ← NEW (questions driven by skill + concept)
          → csod_area_matcher   (now has scoping context)
            → csod_workflow_router
```

Key changes:
- Datasource selector becomes truly optional — concept_resolver runs regardless
- Concept resolver adds an LLM ranking step before presenting options to the user
- Skill identifier moves before scoping, because skill determines what to ask
- Scoping node is created (currently missing) and asks skill-specific questions
- Area matcher now always receives populated `scoping_answers`

---

## 3. Fix A — Make Datasource Selection Truly Optional

### What to change in `csod_planner_router_node`

The router currently treats an identified (but unconfirmed) datasource the same as a confirmed one. The fix separates two distinct states:

- **Known datasource** (confirmed in initial state or from tenant profile): skip datasource_selector entirely, go straight to concept_resolver
- **Unknown datasource** (no value in state): let concept_resolver run first using the query alone, then identify the datasource from the concept match domain as a secondary step — or ask for it after concept confirmation

```python
def _route_from_planner_router(state) -> str:
    """
    Route from planner router.
    
    Datasource is only required if the concept registry demands source filtering.
    In the CSOD L1 collection, concepts are not source-filtered (connected_source_ids=[]).
    Concept resolution can run without a confirmed datasource.
    """
    selected_datasource = state.get("csod_selected_datasource")
    datasource_confirmed = state.get("csod_datasource_confirmed", False)

    if datasource_confirmed and selected_datasource:
        # Confirmed by caller — skip datasource selection entirely
        logger.info(f"Datasource confirmed ({selected_datasource}), going direct to concept_resolver")
        return "csod_concept_resolver"

    # No confirmed datasource — still go to concept_resolver first.
    # csod_datasource_selector will run ONLY if the user explicitly needs to choose.
    # The LLM identification in datasource_selector already defaults to cornerstone when
    # the query is LMS-related, so the question is rarely needed.
    # Decision: only ask for datasource if concept domain does not imply a clear source.
    # For now: always start with concept_resolver, datasource_selector is invoked
    # only as a fallback node after concept resolution if source is still ambiguous.
    logger.info("No confirmed datasource, starting with concept_resolver")
    return "csod_concept_resolver"
```

### What to change in the graph builder

```python
# OLD
workflow.set_entry_point("csod_planner_router")
workflow.add_conditional_edges("csod_planner_router", _route_from_planner_router, {
    "csod_datasource_selector": "csod_datasource_selector",
    "csod_concept_resolver":    "csod_concept_resolver",
})

# NEW
workflow.set_entry_point("csod_planner_router")
workflow.add_conditional_edges("csod_planner_router", _route_from_planner_router, {
    "csod_concept_resolver": "csod_concept_resolver",  # always — datasource resolved downstream
})
# Datasource selector is now only reachable as fallback, wired separately if needed
```

### What to change in `csod_concept_resolver_node` 

Remove the dependency on `csod_selected_datasource` as a required precondition. The vector search call already passes `connected_source_ids=[]`, so it works without a datasource filter. The only change is to stop treating a missing datasource as a blocker:

```python
# DELETE this guard (currently at top of csod_concept_resolver_node):
# if not state.get("csod_selected_datasource"):
#     logger.warning("No datasource selected")
#     return state
```

After concept resolution, the concept match's `domain` field (`lms`, `security`, `hr`) can be used to infer the datasource automatically if not already set:

```python
# After successful vector search in concept_resolver:
if concept_matches and not state.get("csod_selected_datasource"):
    # Infer datasource from concept domain
    domain_to_source = {"lms": "cornerstone", "hr": "workday", "security": "cce"}
    inferred_domain = concept_matches[0].domain  # top match domain
    inferred_source = domain_to_source.get(inferred_domain, "cornerstone")
    state["csod_selected_datasource"] = inferred_source
    logger.info(f"Datasource inferred from concept domain: {inferred_source} (domain: {inferred_domain})")
```

---

## 4. Fix B — Add LLM Concept Ranking Step

### Where it fits

After the vector search returns top-N concept matches, and **before** the concept_select checkpoint is created, a lightweight LLM call reads the user query and the candidates and returns a ranked selection with a confidence score and a plain-English reason for each. This replaces the raw score-sorted list with a reasoned recommendation.

### New function: `_rank_concepts_with_llm()`

```python
def _rank_concepts_with_llm(
    user_query: str,
    concept_matches: List[ConceptMatch],
) -> Optional[Dict[str, Any]]:
    """
    Use LLM to rank concept matches and identify the best fit.

    Called after vector search. Returns a dict with:
      - ranked_concepts: list of concept_id in recommended order
      - primary_concept_id: single best match
      - confidence: "high" | "medium" | "low"
      - reasoning: plain-English explanation of why the top concept fits
      - show_alternatives: bool — whether to surface other options to the user
    """
    try:
        prompt_text = load_prompt("13_concept_ranker", prompts_dir=str(PROMPTS_CSOD))
    except FileNotFoundError:
        # Inline fallback if prompt file not yet created
        prompt_text = """You are an analytics concept identifier for an LMS platform.

The user has asked a question. I have found these candidate concept categories from the knowledge base:

{candidates}

Your task:
1. Identify which concept BEST matches what the user is asking about.
2. Assign a confidence level: high (clearly matches), medium (likely matches), low (ambiguous).
3. Provide a one-sentence plain-English reason for the top pick.
4. If confidence is medium or low, set show_alternatives=true so the user can confirm.

Respond ONLY with a JSON object. No preamble. No markdown.
{
  "primary_concept_id": "string",
  "ranked_concepts": ["concept_id_1", "concept_id_2"],
  "confidence": "high|medium|low",
  "reasoning": "string",
  "show_alternatives": true|false
}"""

    # Format candidates
    candidates_text = "\n".join(
        f"- ID: {m.concept_id}\n  Name: {m.display_name}\n"
        f"  Domain: {m.domain}\n  Vector score: {m.score:.3f}\n"
        f"  Keywords: {', '.join(m.trigger_keywords[:5])}"
        for m in concept_matches
    )
    prompt_text = prompt_text.replace("{candidates}", candidates_text)

    # Escape braces for LangChain template
    prompt_text = prompt_text.replace("{input}", "___INPUT___")
    prompt_text = prompt_text.replace("{", "{{").replace("}", "}}")
    prompt_text = prompt_text.replace("___INPUT___", "{input}")

    llm = get_llm(temperature=0)
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", prompt_text),
        ("human", "{input}"),
    ])
    response = (prompt_template | llm).invoke({"input": user_query})
    content = response.content if hasattr(response, "content") else str(response)

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
        return json.loads(m.group(1)) if m else None
```

### Where to call it in `csod_concept_resolver_node`

```python
# After resolve_intent_to_concept() returns concept_matches:

# --- NEW: LLM ranking step ---
llm_ranking = None
if concept_matches:
    llm_ranking = _rank_concepts_with_llm(user_query, concept_matches)

# Reorder concept_matches if LLM returned a ranking
if llm_ranking and llm_ranking.get("ranked_concepts"):
    ranked_ids = llm_ranking["ranked_concepts"]
    match_by_id = {m.concept_id: m for m in concept_matches}
    # Reorder: ranked first, then any not in ranking list
    concept_matches = (
        [match_by_id[cid] for cid in ranked_ids if cid in match_by_id]
        + [m for m in concept_matches if m.concept_id not in ranked_ids]
    )

# Build checkpoint message using LLM reasoning
primary_id = llm_ranking.get("primary_concept_id") if llm_ranking else None
confidence = llm_ranking.get("confidence", "low") if llm_ranking else "low"
reasoning = llm_ranking.get("reasoning", "") if llm_ranking else ""
show_alternatives = llm_ranking.get("show_alternatives", True) if llm_ranking else True

if primary_id and confidence == "high" and not show_alternatives:
    primary_match = next((m for m in concept_matches if m.concept_id == primary_id), None)
    if primary_match:
        # High-confidence single match → CONFIRMATION turn
        message = (
            f"I'll analyse **{primary_match.display_name}** for you. "
            f"{reasoning} Is that right?"
        )
else:
    # Medium/low confidence or multiple candidates → DECISION turn
    names = ", ".join(f"**{m.display_name}**" for m in concept_matches[:3])
    message = f"I found these topic areas: {names}. Which ones are relevant to your question?"

state["csod_planner_checkpoint"] = {
    "phase": "concept_select",
    "message": message,
    "options": concept_options,  # sorted by LLM ranking, not just vector score
    "requires_user_input": True,
    "llm_confidence": confidence,
    "llm_reasoning": reasoning,
}
```

### New prompt file: `data/prompts/csod/13_concept_ranker.md`

```
You are an analytics concept identifier for enterprise LMS platforms (Cornerstone OnDemand, Workday Learning).

The user has asked a question. I have retrieved these candidate concept categories from the knowledge base using semantic search:

{candidates}

Your task:
1. Read the user's question carefully.
2. Identify which concept BEST matches what the user is asking about.
   - "Compliance Training Risk" = questions about mandatory training, overdue courses, regulatory deadlines, certification gaps
   - "Learning Program Effectiveness" = questions about pass rates, knowledge retention, assessment scores, course quality
3. Assign confidence: high (the query clearly maps to one concept), medium (likely matches, minor ambiguity), low (ambiguous — could be either or neither).
4. Set show_alternatives=true if the user should be asked to confirm, false if you are certain.

Rules:
- Never invent concept IDs. Only use the IDs from the candidate list.
- Reasoning must be one plain-English sentence. No jargon.
- primary_concept_id must be from ranked_concepts[0].

Respond ONLY with a JSON object. No markdown, no preamble.
```

---

## 5. Fix C — Move Skill Identifier Before Scoping

### New position in the graph

```
concept_select checkpoint → user confirms concept
  → csod_skill_identifier    ← runs here with confirmed concepts in state
    → csod_scoping_node      ← NEW: asks skill-specific questions
      → csod_area_matcher    ← now has populated scoping_answers
```

### Why this order is correct

The skill identifier reads `user_query` and the skills from `skills_config`. After concept confirmation, `csod_selected_concepts` is populated in state. The skill identifier can now use **both** the query and the confirmed concept domain to make a more accurate skill classification. A `compliance_training` concept almost always maps to `metrics_recommendations` or `compliance_reporting` skills — the concept narrows the skill space before the LLM sees it.

The scoping questions then depend on the identified skill:
- `metrics_recommendations` → ask org_unit, time_window, training_type
- `dashboard_generation` → ask persona, time_window
- `causal_analysis` → ask org_unit, time_window
- `adhoc_data_questions` → no scoping needed, go straight to area_matcher
- `data_lineage` → ask source_system (optional)
- `reports` → ask report_format, time_window

### What to change in `csod_skill_identifier_node`

Pass confirmed concept info alongside the query so the LLM has full context:

```python
def csod_skill_identifier_node(state):
    user_query = state.get("user_query", "")
    selected_concepts = state.get("csod_selected_concepts", [])
    
    # Build enriched context for skill identification
    concept_context = ""
    if selected_concepts:
        concept_names = ", ".join(c.get("display_name", "") for c in selected_concepts)
        concept_context = f"\nConfirmed topic area(s): {concept_names}"
    
    # Pass enriched query to LLM
    enriched_query = user_query + concept_context
    
    skills_config = load_skills_config()
    skill_info = _identify_skills_with_llm(enriched_query, skills_config)
    ...
```

### New graph wiring

```python
# In build_csod_planner_workflow():

# OLD order:
# concept_resolver → area_matcher → skill_identifier → workflow_router

# NEW order:
workflow.add_conditional_edges(
    "csod_concept_resolver",
    _route_after_concept_resolver,
    {
        "csod_skill_identifier": "csod_skill_identifier",  # ← goes to skill first
        "wait_for_user_input": END,
    },
)
workflow.add_conditional_edges(
    "csod_skill_identifier",
    _route_after_skill_identifier,
    {"csod_scoping_node": "csod_scoping_node"},  # ← then scoping
)
workflow.add_conditional_edges(
    "csod_scoping_node",
    _route_after_scoping,
    {
        "csod_area_matcher": "csod_area_matcher",
        "wait_for_user_input": END,
    },
)
workflow.add_conditional_edges(
    "csod_area_matcher",
    _route_after_area_matcher,
    {"csod_workflow_router": "csod_workflow_router"},  # ← no more skill_identifier here
)
```

---

## 6. Fix D — New Scoping Node (skill-driven questions)

### Why it doesn't exist yet

`csod_area_matcher_node` logs `Scoping answers: {}` on every run because there is no node that populates `csod_scoping_answers` before area_matcher runs. The scoping node was identified as the primary missing piece in the original fix plan but was never implemented in the current planner.

### `csod_scoping_node` design

```python
# Skill → required scoping filters
SKILL_SCOPING_FILTERS = {
    "metrics_recommendations": ["org_unit", "time_period", "training_type"],
    "causal_analysis":         ["org_unit", "time_period"],
    "dashboard_generation":    ["persona", "time_period"],
    "compliance_reporting":    ["org_unit", "time_period", "due_date_range"],
    "adhoc_data_questions":    [],   # no scoping — goes straight to area_matcher
    "data_lineage":            [],   # no scoping
    "reports":                 ["time_period", "report_format"],
    "automations":             ["org_unit"],
    "discovery":               [],
}

# These are always asked regardless of skill
ALWAYS_INCLUDE_FILTERS = ["org_unit", "time_period"]

def csod_scoping_node(state):
    primary_skill = state.get("csod_primary_skill")
    skills_config = load_skills_config()
    
    # Get skill-specific filters from config (falls back to SKILL_SCOPING_FILTERS if not in config)
    skill_info = skills_config.get("skills", {}).get(primary_skill, {})
    config_filters = skill_info.get("scoping_filters", None)
    filters = config_filters if config_filters is not None else SKILL_SCOPING_FILTERS.get(primary_skill, [])
    
    # Always include org_unit and time_period
    all_filters = list(dict.fromkeys(ALWAYS_INCLUDE_FILTERS + filters))  # dedup, preserve order
    
    # Check if all filters already answered (from initial state or previous run)
    existing_answers = state.get("csod_scoping_answers", {})
    unanswered = [f for f in all_filters if f not in existing_answers]
    
    if not unanswered:
        # All scoping answered — skip checkpoint
        state["csod_scoping_complete"] = True
        logger.info(f"All scoping filters already answered for skill {primary_skill}, skipping")
        return state
    
    # Build questions for unanswered filters (cap at 3 per turn)
    questions = []
    for filter_name in unanswered[:3]:
        template = LMS_SCOPING_TEMPLATES.get(filter_name)
        if template:
            questions.append(template.to_question_dict())
        # Unknown filter names are silently skipped
    
    if not questions:
        state["csod_scoping_complete"] = True
        return state
    
    state["csod_planner_checkpoint"] = {
        "phase": "scoping",
        "message": f"Before I search for the best analysis approach, I need a bit more context.",
        "questions": questions,
        "requires_user_input": True,
        "skill": primary_skill,
    }
    return state
```

### Routing after scoping

```python
def _route_after_scoping(state) -> str:
    checkpoint = state.get("csod_planner_checkpoint")
    if checkpoint and checkpoint.get("phase") == "scoping" and checkpoint.get("requires_user_input"):
        return "wait_for_user_input"
    return "csod_area_matcher"
```

---

## 7. Skills Config — Extended Schema

The current `skills_config.json` only has `metrics_recommendations` and `causal_analysis`. It needs the full skill set the user defined, plus two new fields per skill: `scoping_filters` (what to ask) and `needs_area_matching` (whether to run area_matcher at all).

### Updated `skills_config.json` schema

```json
{
  "skills": {
    "metrics_recommendations": {
      "display_name": "Metrics & KPI Recommendations",
      "description": "Recommend metrics, KPIs, and causal drivers for a training or compliance area",
      "agents": ["csod_metric_advisor_workflow"],
      "scoping_filters": ["org_unit", "time_period", "training_type"],
      "needs_area_matching": true,
      "icon": "chart-bar"
    },
    "causal_analysis": {
      "display_name": "Causal Analysis",
      "description": "Understand causal relationships between training inputs and business outcomes",
      "agents": ["csod_metric_advisor_workflow"],
      "scoping_filters": ["org_unit", "time_period"],
      "needs_area_matching": true,
      "icon": "git-branch"
    },
    "dashboard_generation": {
      "display_name": "Dashboard Generation",
      "description": "Build a visual dashboard for a specific persona and training area",
      "agents": ["csod_workflow"],
      "scoping_filters": ["persona", "time_period"],
      "needs_area_matching": true,
      "icon": "layout-dashboard"
    },
    "adhoc_data_questions": {
      "display_name": "Adhoc Data Questions",
      "description": "Answer specific data questions with SQL or direct queries — no dashboard, no recommendations",
      "agents": ["csod_workflow"],
      "scoping_filters": [],
      "needs_area_matching": false,
      "icon": "terminal"
    },
    "data_lineage": {
      "display_name": "Data Lineage",
      "description": "Trace how a metric or data field flows through the medallion architecture",
      "agents": ["csod_workflow"],
      "scoping_filters": [],
      "needs_area_matching": false,
      "icon": "share-2"
    },
    "discovery": {
      "display_name": "Discovery",
      "description": "Explore what data, metrics, and schemas are available for a topic",
      "agents": ["csod_workflow"],
      "scoping_filters": [],
      "needs_area_matching": false,
      "icon": "search"
    },
    "reports": {
      "display_name": "Reports",
      "description": "Generate a formatted report (PDF, Excel, scheduled) for a training area",
      "agents": ["csod_workflow"],
      "scoping_filters": ["time_period", "report_format"],
      "needs_area_matching": true,
      "icon": "file-text"
    },
    "automations": {
      "display_name": "Automations",
      "description": "Set up automated alerts, triggers, or scheduled workflows based on training data",
      "agents": ["csod_workflow"],
      "scoping_filters": ["org_unit"],
      "needs_area_matching": false,
      "icon": "zap"
    }
  },
  "agent_mapping": {
    "csod_workflow": {
      "agent_id": "csod-workflow"
    },
    "csod_metric_advisor_workflow": {
      "agent_id": "csod-metric-advisor"
    }
  },
  "default_agent": "csod_workflow"
}
```

### Using `needs_area_matching` in the router

```python
def _route_after_scoping(state) -> str:
    # Checkpoint still needs answering
    checkpoint = state.get("csod_planner_checkpoint")
    if checkpoint and checkpoint.get("phase") == "scoping" and checkpoint.get("requires_user_input"):
        return "wait_for_user_input"
    
    # Check if skill needs area matching
    primary_skill = state.get("csod_primary_skill")
    skills_config = load_skills_config()
    skill_info = skills_config.get("skills", {}).get(primary_skill, {})
    
    if skill_info.get("needs_area_matching", True):
        return "csod_area_matcher"
    else:
        # Skills like adhoc_data_questions, data_lineage, discovery skip area_matcher
        # and go straight to workflow_router with concept context only
        return "csod_workflow_router"
```

---

## 8. Fix the Stale Checkpoint Loop (the original bug)

This is the checkpoint loop described in the previous session. Three targeted fixes that must land alongside the topology changes.

### Fix 8.1 — `csod_concept_resolver_node`: always overwrite the checkpoint

Remove the guard that only creates the concept_select checkpoint when no checkpoint exists. Replace with an unconditional write:

```python
# OLD (line ~435):
if not state.get("csod_planner_checkpoint"):
    # Recreate checkpoint if it doesn't exist
    state["csod_planner_checkpoint"] = {...}

# NEW — always set, regardless of existing checkpoint:
state["csod_planner_checkpoint"] = {
    "phase": "concept_select",
    "message": message,
    "options": concept_options,
    "requires_user_input": True,
    "llm_confidence": confidence,     # from Fix B
    "llm_reasoning": reasoning,       # from Fix B
}
```

### Fix 8.2 — `normalize_event` in `base_langgraph_adapter.py`: stop using `get_state()` for checkpoint detection

`get_state()` reads from the checkpointer, which is committed after `on_chain_end` fires. It always returns the **previous** turn's state, not the current node's output. Use the event `output` directly:

```python
elif event_type == "on_chain_end":
    output = data.get("output", {})
    
    # Use the node's output directly.
    # get_state() returns PREVIOUS committed state here — not the current node's changes.
    state_to_check = output if isinstance(output, dict) else {}
    
    if isinstance(state_to_check, dict):
        checkpoint = self.extract_checkpoint_from_state(state_to_check, name)
        if checkpoint:
            return AgentEvent(type=EventType.CHECKPOINT, ...)
    
    # get_state() is only appropriate for the step_final handler below,
    # where the full terminal state is needed.
```

### Fix 8.3 — Add datasource fields to `get_preserved_state_keys()`

```python
# In CSODLangGraphAdapter:
def get_preserved_state_keys(self) -> List[str]:
    return [
        "csod_concept_matches",
        "csod_available_datasources",
        "csod_scoping_answers",
        "csod_selected_datasource",   # ← ADD
        "csod_datasource_confirmed",  # ← ADD
        "csod_selected_concepts",     # ← ADD (prevents re-asking concept after resume)
        "csod_confirmed_concept_ids", # ← ADD
        "user_query",
    ]
```

---

## 9. New Prompt: `13_concept_ranker.md`

Create at `data/prompts/csod/13_concept_ranker.md`:

```
You are an analytics concept identifier for enterprise LMS platforms (Cornerstone OnDemand, Workday Learning).

The user has asked a question. I have retrieved these candidate concept categories from the knowledge base using semantic search:

{candidates}

Your task:
1. Read the user's question carefully.
2. Identify which concept BEST matches what the user is asking about.
3. Assign confidence: high (clearly maps to one concept), medium (likely, minor ambiguity), low (ambiguous).
4. Set show_alternatives=true if confidence is medium or low.
5. Provide a one-sentence reasoning in plain business language — no technical terms, no IDs.

Rules:
- Only use concept IDs from the candidate list above.
- primary_concept_id must equal ranked_concepts[0].
- reasoning must be one sentence maximum.

Respond ONLY with a JSON object. No markdown fences, no preamble.
{
  "primary_concept_id": "...",
  "ranked_concepts": ["...", "..."],
  "confidence": "high|medium|low",
  "reasoning": "...",
  "show_alternatives": true|false
}
```

---

## 10. Updated `12_skill_advisor.md` — Concept Context Section

Add to the existing skill advisor prompt (after the skills list):

```
You will also receive the confirmed concept category the user is working with.
Use this to narrow the skill options:
- "Compliance Training Risk" concept → skills most likely: metrics_recommendations, compliance_reporting, dashboard_generation
- "Learning Program Effectiveness" concept → skills most likely: metrics_recommendations, causal_analysis, dashboard_generation
- No concept → consider all skills equally

The concept context is provided at the end of the user message in the format:
"Confirmed topic area(s): [name]"
```

---

## 11. Implementation Order for Cursor

Build in this exact order. Each step is independently testable.

| Step | File | What | Test |
|---|---|---|---|
| 1 | `skills_config.json` | Add all 8 skills with `scoping_filters` and `needs_area_matching` | Load config → assert 8 skill keys |
| 2 | `csod_planner_workflow.py` | `_route_from_planner_router` — remove datasource as hard prerequisite, always route to concept_resolver | Mock state with no datasource → routes to concept_resolver |
| 3 | `csod_planner_workflow.py` | `csod_concept_resolver_node` — add domain→datasource inference after vector search | Mock state with no datasource, concept domain=lms → `csod_selected_datasource="cornerstone"` inferred |
| 4 | `data/prompts/csod/13_concept_ranker.md` | Create prompt file | File exists, no template errors |
| 5 | `csod_planner_workflow.py` | `_rank_concepts_with_llm()` function | Mock 2 concept matches → returns dict with `primary_concept_id`, `confidence`, `reasoning` |
| 6 | `csod_planner_workflow.py` | Wire `_rank_concepts_with_llm()` into concept_resolver, update checkpoint message and options order | High-confidence match → CONFIRMATION message. Low-confidence → DECISION message with alternatives |
| 7 | `csod_planner_workflow.py` | Fix: always overwrite checkpoint in `existing_concept_matches` branch (Fix 8.1) | Mock state with stale datasource_select checkpoint + concept_matches → checkpoint updated to concept_select |
| 8 | `csod_planner_workflow.py` | `csod_skill_identifier_node` — add concept context to enriched query | Skill identified with concept context is more accurate than query alone |
| 9 | `csod_planner_workflow.py` | `csod_scoping_node` — new node with SKILL_SCOPING_FILTERS, always-include filters, 3-question cap | Skill=metrics_recommendations → 3 scoping questions. Skill=adhoc_data_questions → scoping_complete=True, no checkpoint |
| 10 | `csod_planner_workflow.py` | Update graph wiring: concept_resolver → skill_identifier → scoping_node → area_matcher. Add `needs_area_matching` bypass in scoping router | Graph compiles. Run with skill=adhoc_data_questions → area_matcher skipped |
| 11 | `base_langgraph_adapter.py` | `normalize_event` — replace `get_state()` with direct `output` for checkpoint detection (Fix 8.2) | concept_resolver `on_chain_end` emits concept_select checkpoint, not datasource_select |
| 12 | `csod_langgraph_adapter.py` | `get_preserved_state_keys` — add 4 new keys (Fix 8.3) | Resume turn preserves `csod_selected_datasource` and `csod_confirmed_concept_ids` without re-prompting |
| 13 | `data/prompts/csod/12_skill_advisor.md` | Add concept context section | Skill advisor prompt contains concept narrowing instructions |

---

## 12. State Fields Added by This Fix

| Field | Set by | Read by | Notes |
|---|---|---|---|
| `csod_llm_concept_ranking` | concept_resolver (new) | concept checkpoint builder | Dict: `{primary_concept_id, ranked_concepts, confidence, reasoning}` |
| `csod_primary_skill` | skill_identifier (existing, moved) | scoping_node, workflow_router | Already exists — just earlier in graph |
| `csod_scoping_answers` | scoping_node (new) | area_matcher | Was always `{}` before — now populated |
| `csod_scoping_complete` | scoping_node (new) | `_route_after_scoping` | True when all filters answered or skill has no scoping |

---

## 13. Summary of Flow Changes

| | **Current (broken)** | **After this fix** |
|---|---|---|
| Datasource required before concepts? | Yes — blocks concept resolution | No — datasource inferred from concept domain |
| Concept selection uses LLM? | No — raw vector scores only | Yes — LLM ranks and reasons before presenting |
| Skill identified before or after scoping? | After area matching | Before scoping (concept → skill → scoping → area) |
| Scoping node exists? | No — `scoping_answers` always `{}` | Yes — skill-driven, 3-question cap |
| Skills in config? | 2 skills (metrics, causal) | 8 skills with scoping_filters and needs_area_matching |
| Checkpoint stale loop? | Present | Fixed (8.1, 8.2, 8.3) |
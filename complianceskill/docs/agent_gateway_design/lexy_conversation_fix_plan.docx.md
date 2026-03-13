**Lexy Conversation Engine — Fix & Generic Design Plan**

Comatrix Labs · Lexy AI · CSOD / LMS Vertical

*Metadata-driven multi-turn conversation engine — works for any vertical*

# **1\.  What Is Broken and Exactly Where**

The planner workflow (csod\_planner\_workflow.py) is a straight pipeline masquerading as a conversation. All four nodes run in a single shot with no mechanism to pause, surface output to the user, and resume with their response. Three specific breaks cause the conversational questions to never appear.

## **1.1  Root Cause: No Interrupt Mechanism**

LangGraph's interrupt() is not wired up anywhere in the planner workflow. The graph runs datasource\_selector → concept\_resolver → area\_matcher → workflow\_router in one execution and then calls the downstream CSOD pipeline immediately. The user sees nothing between question submission and final pipeline output.

## **1.2  The Five Specific Breaks**

| Node / Location | What It Currently Does | Break |
| :---- | :---- | :---- |
| **csod\_datasource\_selector\_node** | Auto-selects datasource; sets checkpoint only when not yet confirmed | If datasource is pre-set in state it skips the checkpoint entirely and flows through silently |
| **csod\_concept\_resolver\_node** | Calls resolve\_intent\_to\_concept() → writes csod\_concept\_matches, project\_ids, mdl\_table\_refs | No checkpoint written. User never sees matched concepts. No confirmation possible. |
| **csod\_area\_matcher\_node** | Calls resolve\_scoping\_to\_areas(scoping\_answers={}, concept\_id) | scoping\_answers is ALWAYS {} — no node ever asks scoping questions before this runs. Area matching has zero scoping context. |
| **csod\_workflow\_router\_node** | Builds compliance\_profile from area.metrics/kpis/causal\_paths, fires downstream | compliance\_profile.lexy\_metric\_narration is never set → intent bypass in csod\_intent\_classifier never triggers. Time\_window, org\_unit, training\_type all missing. |
| **\_generate\_area\_confirmation()** | LLM call to generate confirmation message using 10\_area\_confirmation.md | Only called when csod\_generate\_area\_confirmation=True. That flag is never set anywhere in the workflow. |

| KEY | The single most impactful missing piece: scoping\_node does not exist. csod\_area\_matcher\_node calls resolve\_scoping\_to\_areas(scoping\_answers={}) and scoping\_answers is ALWAYS an empty dict because nothing ever asks the user for scoping context before area matching runs. |
| :---: | :---- |

# **2\.  Architecture: Generic Conversation Turn Engine**

The fix introduces a Conversation Turn Engine — a framework layer that sits in front of any downstream analytics pipeline. It is not CSOD-specific. A VerticalConversationConfig object drives all behaviour. Swapping the config switches the engine from LMS mode to Security mode to HR mode with zero engine code changes.

## **2.1  Pipeline vs Conversation Turn**

| PIPELINE — current, broken | CONVERSATION TURNS — required |
| :---- | :---- |
| All four nodes run in one shot. User sees nothing until the downstream pipeline fires. scoping\_answers={} forever. Area matching has no context. Compliance profile missing time\_window, org\_unit, training\_type. | Each conversation node writes a checkpoint and stops. API reads checkpoint → sends turn to client. Client sends user response → API injects into state → graph resumes. area\_matcher re-runs WITH scoping context. compliance\_profile fully populated before pipeline fires. |

## **2.2  Turn Types**

Four turn types cover all conversational interactions. The type is declared on TurnOutputType and drives the frontend widget selection — not the backend. The backend only writes data; the frontend decides how to render it.

| Type | Used for | Frontend widget |
| :---- | :---- | :---- |
| CONFIRMATION | Lexy restates intent — user verifies or adjusts | Summary card \+ Yes / No / Adjust — no chips, a clear primary CTA |
| SCOPING | Lexy needs more information before proceeding | Grouped chip questions — form style, left-aligned, all questions in one block. Visual language: fill in a blank |
| DECISION | Meaningful path fork — each option leads to different output | Large cards with descriptions — navigation style. One question per turn, no grouping |
| METRIC\_NARRATION | Lexy explains what it will measure and why | Metric grid with causal role tags \+ confirm CTA. Inline adjustments (add YoY, narrow to at-risk) |

## **2.3  Conversation Flow with Interrupt Points**

The planner workflow now has explicit interrupt nodes. Each conversation\_\* node writes a ConversationCheckpoint to state and the routing function checks whether to stop the graph or continue.

| Phase | New Node | Turn Type | Pauses? | User Response → state field |
| :---- | :---- | :---- | :---- | :---- |
| 0A | datasource\_selector\_node (existing) | DECISION | ✓ | csod\_datasource\_confirmed |
| 0B | concept\_confirm\_node (NEW) | CONFIRMATION | ✓ | csod\_confirmed\_concept\_ids |
| 0C | **scoping\_node (NEW) ← main fix** | SCOPING | ✓ | csod\_scoping\_answers |
| 0D | area\_matcher\_node (existing, re-runs with scoping) | — | — | — |
| 0E | area\_confirm\_node (NEW) | CONFIRMATION | ✓ | csod\_confirmed\_area\_id |
| 0F | metric\_narration\_node (NEW) | METRIC\_NARRATION | ✓ | csod\_metric\_narration\_confirmed |
| 0G | workflow\_router\_node (existing) | — | — | Fires CSOD downstream pipeline |

| HOW RESUME WORKS | The API layer holds the LangGraph thread\_id across turns. When the user responds, the API injects the user's answer into the state field declared by checkpoint.resume\_with\_field, sets csod\_checkpoint\_resolved=True, and calls graph.ainvoke() again. LangGraph's MemorySaver restores the graph at the point it stopped and continues from there. |
| :---: | :---- |

# **3\.  The Generic Configuration Object**

One VerticalConversationConfig instance per vertical. All conversation behaviour is derived from this config. The engine nodes read config; they contain no vertical-specific logic.

## **3.1  VerticalConversationConfig Fields**

| Field | Type | Purpose |
| :---- | :---- | :---- |
| **vertical\_id** | str | Identifier used in logging, state keys, and route prefixes. 'lms' | 'security' | 'hr' |
| **display\_name** | str | Human-facing vertical name shown in Lexy UI header |
| **l1\_collection** | str | ChromaDB collection name for concept-level (L1) vector lookup |
| **l2\_collection** | str | ChromaDB collection name for recommendation area (L2) vector lookup |
| **supported\_datasources** | List\[dict\] | Available datasources for this vertical. Each has id, display\_name, description |
| **scoping\_question\_templates** | Dict\[str, ScopingQuestionTemplate\] | Maps area.filters\[\] filter\_name → question to ask user. Unknown filter names are silently skipped |
| **always\_include\_filters** | List\[str\] | Filter names always asked regardless of what area.filters\[\] contains. LMS defaults: \['org\_unit', 'time\_period'\] |
| **intent\_to\_workflow** | Dict\[str, str\] | Maps confirmed csod\_intent → downstream workflow name. Used by workflow\_router to fire the right pipeline |
| **default\_workflow** | str | Fallback workflow if intent does not match any key in intent\_to\_workflow |
| **max\_scoping\_questions\_per\_turn** | int | Cap on questions shown in a single scoping turn. Default: 3\. Avoids overwhelming the user |

## **3.2  ScopingQuestionTemplate Fields**

Each template maps one filter\_name (from recommendation\_area.filters\[\]) to one question. The template is reusable across areas and verticals — the same time\_period template works for LMS and Security.

| Field | Type | Purpose |
| :---- | :---- | :---- |
| **filter\_name** | str | Must match exactly one value in area.filters\[\]. This is the lookup key. |
| **question\_id** | str | Stable identifier for the question. Appears in ConversationTurn.questions\[\].id |
| **label** | str | Plain-English question shown to user. No technical terms. |
| **interaction\_mode** | str | 'single' for single-select chips. 'multi' for multi-select (user\_status, severity) |
| **options** | List\[dict\] | Available chip options. Each has id and label. id is written into scoping\_answers. |
| **state\_key** | str | Key in csod\_scoping\_answers dict that this answer populates |
| **required** | bool | If True, question is always included when the filter is matched |

## **3.3  LMS Scoping Question Templates**

These 8 templates cover all filter\_names used by recommendation areas in the current concept\_recommendation\_registry. Unknown filter\_names in future areas are silently skipped at runtime — no code change needed, just add a new template to the dict.

| filter\_name (from area.filters\[\]) | Question shown to user | state\_key written | Type |
| :---- | :---- | :---- | :---- |
| **org\_unit** | Which part of the organisation should I focus on? | org\_unit | single |
| **time\_period** | What time window matters most to you? | time\_window | single |
| **due\_date\_range** | Which deadline window are you most concerned about? | deadline\_window | single |
| **training\_type** | What kind of training are you most concerned about? | training\_type | single |
| **delivery\_method** | Which delivery method do you want to focus on? | delivery\_method | single |
| **audit\_window** | When is the audit? | audit\_window | single |
| **course\_id** | Do you want to focus on a specific course or programme? | course\_scope | single |
| **user\_status** | Which learner population should I include? | user\_status | multi |

# **4\.  New Node Designs**

## **4.1  concept\_confirm\_node  (NEW — Phase 0B)**

Runs immediately after concept\_resolver. Reads csod\_concept\_matches from state. Formats the top matched concept as a CONFIRMATION turn. User can confirm, expand to additional concepts, or rephrase.

* State reads: csod\_concept\_matches, csod\_selected\_datasource

* State writes: csod\_conversation\_checkpoint (CONFIRMATION type)

* resume\_with\_field: csod\_confirmed\_concept\_ids

* Zero-match fallback: writes checkpoint with a rephrase prompt instead of confirmation options

| Option shown | What it does |
| :---- | :---- |
| Yes — \[concept\] is right | Sets csod\_confirmed\_concept\_ids \= \[concept\_id\]. Graph continues to scoping\_node. |
| Add another area | Multi-select from concept\_matches\[1:\]. Both concept IDs written to csod\_confirmed\_concept\_ids. |
| Let me rephrase | resume\_with\_field \= user\_query. Graph resumes at concept\_resolver with new query. |

## **4.2  scoping\_node  (NEW — Phase 0C — The Main Fix)**

This is the missing node. It is the primary reason scoping\_answers is always empty and area matching has no context.

The node reads area\_matches\[0\].filters\[\] from a preliminary first-pass area lookup (run immediately after concept\_confirm, before scoping). It resolves each filter\_name against config.scoping\_question\_templates. It always adds config.always\_include\_filters. It caps at config.max\_scoping\_questions\_per\_turn. It writes a SCOPING turn checkpoint and stops.

* State reads: csod\_area\_matches (preliminary), csod\_confirmed\_concept\_ids

* State writes: csod\_conversation\_checkpoint (SCOPING type)

* resume\_with\_field: csod\_scoping\_answers

* On resume: csod\_scoping\_answers is populated. Graph continues to area\_matcher, which now runs with full scoping context.

* Unknown filter\_names: silently skipped. New areas can add new filters without breaking the engine.

* Empty filters\[\]: sets csod\_scoping\_complete=True and skips the checkpoint entirely — no unnecessary questions.

| WHY PRELIMINARY AREA LOOKUP | scoping\_node needs to know which filters the primary area requires before it can ask the right questions. A lightweight first-pass area lookup runs before scoping (without scoping context — just concept\_id). After scoping answers are collected, area\_matcher runs again with the full scoping context to produce the final match. This two-pass approach is necessary because the area drives the questions, but the questions refine the area selection. |
| :---: | :---- |

## **4.3  area\_confirm\_node  (NEW — Phase 0E)**

Runs after area\_matcher (which has now run with scoping\_answers populated). Calls the existing \_generate\_area\_confirmation() function from csod\_planner\_workflow.py — no rewrite. Removes the dead csod\_generate\_area\_confirmation flag (it was never set).

* State reads: csod\_area\_matches, csod\_selected\_concepts, user\_query

* State writes: csod\_area\_confirmation, csod\_conversation\_checkpoint (CONFIRMATION type)

* resume\_with\_field: csod\_confirmed\_area\_id

* Area options: all matched areas (up to 3\) as selectable options

* Fallback: if area\_matches=\[\] even with scoping, asks user to rephrase

## **4.4  metric\_narration\_node  (NEW — Phase 0F)**

Generates a plain-language explanation of what Lexy will measure and why, grounded entirely in the registry area data. No hallucination — every claim traces to area.causal\_paths, area.metrics, area.kpis, or csod\_scoping\_answers. Sets compliance\_profile.lexy\_metric\_narration, which triggers the intent bypass in csod\_intent\_classifier\_node.

* State reads: csod\_primary\_area, csod\_scoping\_answers, user\_query

* State writes: csod\_metric\_narration, csod\_conversation\_checkpoint (METRIC\_NARRATION type)

* resume\_with\_field: csod\_metric\_narration\_confirmed

* LLM prompt: grounded in area.causal\_paths \+ metrics \+ kpis \+ scoping. Template-first for speed; LLM enriches.

* On confirm: workflow\_router sets compliance\_profile.lexy\_metric\_narration \= csod\_metric\_narration → triggers intent bypass

# **5\.  Rebuilt Graph Topology**

## **5.1  \_route\_with\_interrupt — The Generic Routing Function**

A single routing function used at every conversation node. No node-specific routing logic needed.

| Condition | Route |
| :---- | :---- |
| csod\_conversation\_checkpoint is set AND csod\_checkpoint\_resolved is not True | → 'interrupt' (END). API reads checkpoint and sends to client. |
| csod\_checkpoint\_resolved is True | → 'continue'. Clears checkpoint. Graph continues to next node. |

def \_route\_with\_interrupt(state) \-\> str:

    checkpoint \= state.get('csod\_conversation\_checkpoint')

    if checkpoint and not state.get('csod\_checkpoint\_resolved'):

        return 'interrupt'  \# → END, API handles client interaction

    state\['csod\_conversation\_checkpoint'\] \= None

    state\['csod\_checkpoint\_resolved'\] \= False

    return 'continue'

## **5.2  Node Execution Order**

| Node | Type | On interrupt resolved by |
| :---- | :---- | :---- |
| datasource\_selector (existing) | Pipeline | — |
| concept\_resolver (existing) | Pipeline | — |
| preliminary\_area\_matcher (lightweight, no scoping) | Pipeline | — |
| concept\_confirm\_node ← NEW | CONVERSATION (interrupt) | User confirms concepts → csod\_confirmed\_concept\_ids |
| scoping\_node ← NEW (main fix) | CONVERSATION (interrupt) | User answers scoping Qs → csod\_scoping\_answers |
| area\_matcher (existing, re-runs with scoping) | Pipeline | — |
| area\_confirm\_node ← NEW | CONVERSATION (interrupt) | User confirms area → csod\_confirmed\_area\_id |
| metric\_narration\_node ← NEW | CONVERSATION (interrupt) | User confirms metrics → csod\_metric\_narration\_confirmed |
| workflow\_router (existing, updated) | Pipeline | — |
| → CSOD downstream pipeline | External invocation | — |

# **6\.  State Fields — Before and After**

All fields that need to be added, removed, or fixed.

| Field | Set by | Read by | Status |
| :---- | :---- | :---- | :---- |
| **csod\_selected\_datasource** | datasource\_selector | all downstream | ✅ Working |
| **csod\_concept\_matches** | concept\_resolver | concept\_confirm\_node | ✅ Resolved — ❌ Never shown to user |
| **csod\_confirmed\_concept\_ids** | API layer (from user) | scoping\_node | ❌ Field does not exist |
| **csod\_scoping\_answers** | API layer (from user) | area\_matcher\_node | ❌ Always {} — scoping\_node missing |
| **csod\_area\_matches** | area\_matcher\_node | area\_confirm\_node | ⚠️ Runs without scoping context |
| **csod\_confirmed\_area\_id** | API layer (from user) | metric\_narration\_node | ❌ Field does not exist |
| **csod\_metric\_narration** | metric\_narration\_node | workflow\_router, csod\_planner\_node | ❌ Node does not exist |
| **csod\_metric\_narration\_confirmed** | API layer (from user) | workflow\_router | ❌ Field does not exist |
| **csod\_conversation\_checkpoint** | each conversation\_\* node | API layer \+ \_route\_with\_interrupt | ❌ Was csod\_planner\_checkpoint, only set for datasource |
| **compliance\_profile.lexy\_metric\_narration** | workflow\_router\_node | csod\_intent\_classifier (bypass) | ❌ Never populated; bypass never triggers |
| **compliance\_profile.time\_window** | workflow\_router (from scoping) | csod\_planner\_node | ❌ Always missing |
| **compliance\_profile.org\_unit** | workflow\_router (from scoping) | csod\_planner\_node | ❌ Always missing |
| **compliance\_profile.training\_type** | workflow\_router (from scoping) | csod\_planner\_node | ❌ Always missing |

## **6.1  workflow\_router\_node Changes**

The existing csod\_workflow\_router\_node needs three additions to properly populate compliance\_profile for the downstream CSOD pipeline:

* Set compliance\_profile.lexy\_metric\_narration \= state\['csod\_metric\_narration'\]. This triggers the intent bypass in csod\_intent\_classifier\_node, which already checks for this field.

* Unpack csod\_scoping\_answers into compliance\_profile top-level keys: time\_window, org\_unit, training\_type, deadline\_window, delivery\_method, etc. These are read by csod\_planner\_node when building filter\_context.

* Set csod\_intent from confirmed area if not already set. The confirmed area's recommended\_intent (from concept\_recommendation\_registry) should override the default classification.

# **7\.  API Layer — Resume Protocol**

The API layer connects LangGraph graph interrupts to the frontend. It must persist thread\_id across HTTP requests and inject user responses into the right state field.

| Request field | Description |
| :---- | :---- |
| session\_id | Used as LangGraph thread\_id. Persisted in MemorySaver (dev) or Redis (prod). All turns in a conversation use the same session\_id. |
| response.field | The state field to inject the user's answer into. This is checkpoint.resume\_with\_field from the previous turn response. |
| response.value | The actual answer (string, dict, or list depending on turn type). For SCOPING turns: a dict mapping state\_key → selected option id. |

POST /api/conversation/turn

{

  session\_id: 'abc-123',

  response: {

    field: 'csod\_scoping\_answers',    // from previous checkpoint.resume\_with\_field

    value: {

      org\_unit: 'department',

      time\_window: 'last\_quarter',

      training\_type: 'mandatory'

    }

  }

}

// Response when another turn is needed:

{ session\_id, phase, turn: ConversationTurn, is\_complete: false }

// Response when all turns complete:

{ session\_id, phase: 'confirmed', is\_complete: true, csod\_initial\_state: {...} }

# **8\.  Implementation Steps for Cursor**

Build in this exact order. Each step has testable acceptance criteria before moving to the next.

| Step | File to Create / Edit | What to Implement | Test |
| :---- | :---- | :---- | :---- |
| **1** | app/conversation/turn.py (NEW) | ConversationTurn, TurnOutputType (CONFIRMATION | SCOPING | DECISION | METRIC\_NARRATION), TurnQuestion, ConversationCheckpoint dataclasses. All serialisable to JSON. | Instantiate each type, JSON round-trip |
| **2** | app/conversation/config.py (NEW) | ScopingQuestionTemplate, VerticalConversationConfig dataclasses. No CSOD logic — pure metadata containers. | Import without error, assert fields |
| **3** | app/conversation/verticals/lms\_config.py (NEW) | LMS\_SCOPING\_TEMPLATES dict with 8 templates (org\_unit, time\_period, due\_date\_range, training\_type, delivery\_method, audit\_window, course\_id, user\_status). LMS\_CONVERSATION\_CONFIG instance. | Assert all 8 keys load; assert config.always\_include\_filters \== \['org\_unit','time\_period'\] |
| **4** | app/conversation/nodes/concept\_confirm.py (NEW) | concept\_confirm\_node(state, config). Reads csod\_concept\_matches. Writes csod\_conversation\_checkpoint with CONFIRMATION turn. Handles zero-match fallback. | Mock state with 3 concept\_matches → checkpoint.phase \== 'concept\_confirm'. Mock with \[\] → checkpoint.message asks to rephrase. |
| **5 ← main fix** | app/conversation/nodes/scoping.py (NEW) | scoping\_node(state, config). Reads area\_matches\[0\].filters\[\]. Looks up each filter in config.scoping\_question\_templates. Caps at max\_scoping\_questions\_per\_turn. Always includes always\_include\_filters. Writes checkpoint with SCOPING turn. | A: filters=\['org\_unit','time\_period','training\_type'\] → 3 questions. B: filters=\['unknown\_xyz'\] → gracefully skipped, still includes always\_include. C: filters=\[\] → scoping\_complete=True, no checkpoint. |
| **6** | app/conversation/nodes/area\_confirm.py (NEW) | area\_confirm\_node(state, config). Calls existing \_generate\_area\_confirmation() (no rewrite). Formats area options. Always writes checkpoint. Removes dead csod\_generate\_area\_confirmation flag. | Mock area\_matches → checkpoint.phase \== 'area\_confirm', options include all matched areas. |
| **7** | app/conversation/nodes/metric\_narration.py (NEW) | metric\_narration\_node(state, config). Reads primary\_area.causal\_paths \+ metrics \+ kpis \+ scoping\_answers. LLM call grounded in registry data (no hallucination). Writes checkpoint with METRIC\_NARRATION turn. | Assert LLM prompt contains causal\_paths from area. Assert checkpoint.metadata has metrics and kpis arrays. |
| **8** | app/conversation/planner\_workflow.py (NEW, replaces csod\_planner\_workflow.py) | build\_conversation\_planner\_workflow(config: VerticalConversationConfig) → StateGraph. \_route\_with\_interrupt() function. Correct node order: datasource\_selector → concept\_resolver → concept\_confirm → scoping → area\_matcher → area\_confirm → metric\_narration → workflow\_router. | Build graph → assert node list. Run \_route\_with\_interrupt with checkpoint set → 'interrupt'. Run with checkpoint\_resolved=True → 'continue'. |
| **9** | app/conversation/planner\_workflow.py — workflow\_router\_node update | In csod\_workflow\_router\_node: set compliance\_profile.lexy\_metric\_narration from csod\_metric\_narration. Set time\_window, org\_unit, training\_type from csod\_scoping\_answers. Set csod\_intent from confirmed area. | Assert compliance\_profile contains all scoping fields after router runs. |
| **10** | api/routes/conversation.py (NEW or update) | POST /conversation/turn. Reads checkpoint from state. Injects user response into resume\_with\_field. Uses LangGraph thread\_id \= session\_id for MemorySaver resume. Returns next checkpoint or is\_complete=True with csod\_initial\_state. | Simulate 5-turn conversation: datasource → concept confirm → scoping → area confirm → metric narration. Assert final is\_complete=True and compliance\_profile.time\_window is set. |
| **11** | csod\_planner\_workflow.py — remove dead code | Remove csod\_generate\_area\_confirmation flag (never used). Remove csod\_planner\_checkpoint field (replaced by csod\_conversation\_checkpoint). Remove dead \_route\_after\_\* functions replaced by \_route\_with\_interrupt. | Grep codebase for csod\_generate\_area\_confirmation → zero hits after removal. |

# **9\.  Adding a New Vertical — Zero Engine Changes**

The engine (turn.py, config.py, concept\_confirm.py, scoping.py, area\_confirm.py, metric\_narration.py, planner\_workflow.py) does not change. Only a new config file is needed.

| Config Field | LMS / CSOD value | Security / CCE value |
| :---- | :---- | :---- |
| **vertical\_id** | lms | security |
| **l1\_collection** | lexy\_concepts\_l1 | cce\_concepts\_l1 |
| **l2\_collection** | lexy\_areas\_l2 | cce\_areas\_l2 |
| **supported\_datasources** | cornerstone, workday | snyk, wiz, crowdstrike |
| **scoping\_question\_templates** | org\_unit, time\_period, training\_type, … | severity, time\_period, environment, asset\_type, … |
| **always\_include\_filters** | \['org\_unit', 'time\_period'\] | \['severity', 'time\_period'\] |
| **intent\_to\_workflow** | metrics\_dashboard\_plan → csod\_workflow | vulnerability\_analysis → cce\_workflow |
| **default\_workflow** | csod\_workflow | cce\_workflow |

To wire a new vertical:

1. **Create app/conversation/verticals/security\_config.py with SECURITY\_SCOPING\_TEMPLATES and SECURITY\_CONVERSATION\_CONFIG.**

2. **Add L1 and L2 collections to the vector store for the new vertical's concepts and recommendation areas.**

3. **In the API router, instantiate: app \= build\_conversation\_planner\_workflow(SECURITY\_CONVERSATION\_CONFIG).compile(checkpointer=...)**

4. **Point the endpoint to the new app instance. Done.**

| SHARED TEMPLATES | Templates like time\_period are vertical-agnostic. Define them once in app/conversation/templates/shared.py and import them into both LMS and Security configs. Any update to the time\_period question options applies everywhere automatically. |
| :---: | :---- |

# **10\.  Prompt Changes Required**

Existing prompts are correct. Three targeted additions are needed.

| Prompt file | Status | Change |
| :---- | :---- | :---- |
| 01\_intent\_classifier.md | ✅ No change needed | Bypass logic already implemented in csod\_intent\_classifier\_node. Triggers correctly once lexy\_metric\_narration is set. |
| 02\_csod\_planner.md | ✅ No change needed | Filter context section already reads time\_window, org\_unit, training\_type from compliance\_profile. Will work correctly once scoping populates these fields. |
| 10\_area\_confirmation.md | ✅ No change needed | Prompt is correct. The only change is that area\_confirm\_node now always calls it (flag removed). Output is still consumed by the new checkpoint. |
| 11\_metric\_narration.md (NEW) | ❌ Create this file | System prompt for metric\_narration\_node. Must instruct LLM to use ONLY area.causal\_paths, metrics, kpis, and scoping\_answers. No fabrication. Output: 2-3 plain-English sentences \+ metric set justification. |
| 12\_concept\_confirm.md (optional) | ⚠️ Optional | concept\_confirm\_node can use a template message without LLM. Only add this prompt if the confirmation message needs to be more dynamic than a template string. |

## **11\_metric\_narration.md — Key Instructions**

The prompt must enforce three constraints:

* Ground every claim in the registry. The LLM receives area.causal\_paths, area.metrics, area.kpis, and csod\_scoping\_answers. It must cite only these — no hallucinated metric names.

* Plain business language. No table names, metric IDs, technical identifiers. The audience is a non-technical training coordinator or compliance officer.

* 2-3 sentences maximum for the narration. Then a bullet list of 3-5 key metrics with causal role (driver / outcome / guardrail) drawn from area.causal\_paths.

*Comatrix Labs · Lexy AI Platform · Confidential*
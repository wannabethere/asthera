

**Security Agents — Conversation Engine**

**Fix & Conversation Design Plan**

Comatrix Labs  ·  CCE / Detection & Triage / Compliance Vertical

# **1\.  What Is Broken and Exactly Where**

Both the Compliance workflow (workflow.py) and the Detection & Triage workflow (dt\_workflow.py) share the same root failure as the CSOD planner: every node runs in a single uninterrupted shot. No checkpoint is written. No user input is collected between intent classification and agent execution. The user submits a query and sees nothing until the final pipeline output — with no opportunity to confirm the framework, specify their tools, choose a template, or approve the execution plan.

## **1.1  Compliance Workflow — The Seven Specific Breaks**

| ROOT CAUSE:  route\_from\_profile\_resolver fires immediately after intent\_classifier with zero user interaction. framework\_id is never confirmed. selected\_data\_sources is never asked. For dashboard intent, persona is never collected. The planner fires a multi-step execution plan that the user has never seen or approved. |  |  |
| :---- | :---- | :---- |
| **Node / Location** | **What It Currently Does** | **Break** |
| intent\_classifier\_node | LLM call classifies intent from raw query. Writes state.intent. | No bypass exists. If intent is mis-classified (e.g. user says 'show me my gaps' but gets 'risk\_control\_mapping'), the entire routing tree is wrong. User never confirms. No playbook\_resolved\_intent check. |
| route\_from\_profile\_resolver | Immediately routes to dashboard\_generator, risk\_control\_mapper, gap\_analysis, cross\_framework\_mapper, or planner based on intent \+ data\_enrichment. | Fires without any user context collected. framework\_id unconfirmed. selected\_data\_sources never collected. data\_enrichment.needs\_metrics is set by LLM in intent\_classifier — user never influences it. |
| framework\_id — never confirmed | profile\_resolver\_node presumably extracts framework from query context. | User never sees what framework was resolved before gap\_analysis, cross\_framework\_mapper, or framework\_analyzer starts building on it. A mis-identified framework silently produces wrong output for every downstream agent. |
| selected\_data\_sources — never collected | No node in workflow.py asks which security tools are in use. | dashboard\_generator, risk\_control\_mapper, and the planner chain all need data source context to generate relevant output. metrics\_recommender\_node runs without knowing which tool schemas are available. |
| planner\_node → plan\_executor\_node | planner generates multi-step execution plan. plan\_executor dispatches framework\_analyzer, detection\_engineer, playbook\_writer, test\_generator immediately. | User never sees the plan before execution begins. No approval step. A hallucinated or wrong plan step causes an entire agent chain to run and fail before the user can intervene. |
| dashboard\_generator — no persona | dashboard\_generator\_node fires immediately on dashboard\_generation intent. | Persona (SOC analyst, CISO, compliance officer) is never collected. Dashboard is generated for an assumed audience, producing charts and KPIs that may be completely irrelevant to the actual user. |
| route\_from\_metrics\_recommender — missing branches | Routes to dashboard\_generator or planner only. | gap\_analysis and cross\_framework\_mapping are missing from the conditional map. If needs\_metrics=True and intent is gap\_analysis, the graph routes incorrectly to planner. Silent mis-routing. |

## **1.2  Detection & Triage Workflow — The Ten Specific Breaks**

| ROOT CAUSE:  dt\_playbook\_template is never set by user interaction. \_route\_after\_scoring defaults to Template A (detection engineer) when template is unset, but a triage-only user gets the full detection pipeline. framework\_id and selected\_data\_sources are never confirmed. Two routing functions mutate state directly, making the refinement loop counters unreliable. |  |  |
| :---- | :---- | :---- |
| **Node / Location** | **What It Currently Does** | **Break** |
| dt\_playbook\_template — never set | \_route\_after\_scoring checks dt\_playbook\_template to decide detection-only (A), triage-only (B), or full chain (C). | Template defaults to 'A' when not in state. A user who wants triage-only recommendations silently gets the full detection engineer \+ SIEM validator chain. The most critical routing decision in the DT workflow is never surfaced to the user. |
| dt\_intent\_classifier\_node → dt\_planner\_node | Classifies intent from raw query. Planner fires immediately after. | No bypass for pre-resolved intent. No user confirmation. dt\_planner\_node starts building the enrichment pipeline (sets needs\_metrics, needs\_mdl) before the user has confirmed what they actually want to generate. |
| framework\_id — never confirmed | dt\_framework\_retrieval\_node retrieves controls using framework\_id as primary lookup key. | If framework\_id is absent from the query or mis-classified, dt\_framework\_retrieval\_node retrieves wrong or empty controls. dt\_metrics\_retrieval\_node and dt\_mdl\_schema\_retrieval\_node both depend on what framework retrieval returns. A bad framework silently corrupts the entire enrichment chain. |
| selected\_data\_sources — never asked | dt\_metrics\_retrieval\_node and dt\_mdl\_schema\_retrieval\_node filter by data source. | If selected\_data\_sources=\[\], schema retrieval returns generic results or fails silently. Product capability scoring (in dt\_tool\_integration.py) cannot match tools to controls. The Qdrant query uses product\_id from selected\_data\_sources — empty list means zero product-specific context. |
| data\_enrichment.needs\_metrics \+ needs\_mdl | Set by dt\_planner\_node LLM call. Gates two major enrichment branches. | User never confirms whether metric retrieval and MDL schema retrieval should run. If planner sets needs\_mdl=False but the user needs dbt schema generation, the entire calculation\_needs\_assessment → calculation\_planner → cubejs\_schema\_generation branch is skipped silently. |
| is\_leen\_request — never asked | Gates dt\_unified\_format\_converter → cubejs\_schema\_generation in \_route\_after\_playbook\_assembler. | LEEN users get plain playbook output instead of Cube.js schema. Non-LEEN users who need the gold model SQL plan never trigger the conversion path. The flag defaults to False in create\_dt\_initial\_state, so format conversion never runs unless the caller explicitly sets it — and no conversation mechanism exists to do so. |
| \_route\_after\_siem\_validator — state mutation in router | state\['dt\_validation\_iteration'\] \= iteration \+ 1 inside routing function. | LangGraph routing functions are not guaranteed to persist state mutations reliably depending on checkpointer implementation. Counter may not increment, causing refinement loop to over-iterate (infinite loop risk) or not iterate at all. Iteration tracking must happen inside a node, not a router. |
| \_route\_after\_metric\_validator — state mutation in router | state\['dt\_validating\_detection\_metrics'\] \= False and state\['dt\_validation\_iteration'\] \= 0 inside routing function. | Same issue as SIEM validator router. Both reset operations must be moved into a dedicated node that runs before the next agent to guarantee the state change is persisted. |
| dt\_dashboard\_clarifier\_node — silent run | When intent=dashboard\_generation, pipeline runs: context\_discoverer → clarifier → question\_generator. | Despite being named 'clarifier', dt\_dashboard\_clarifier\_node runs as a pipeline node with no user interaction. The clarification output is never surfaced. Dashboard questions are generated for an assumed context. persona is never collected. |
| persona — never asked for dashboard intent | dt\_dashboard\_assembler fires without persona context. | Dashboard is assembled for an unspecified audience. The dt\_dashboard\_context\_discoverer and dt\_dashboard\_question\_generator nodes would produce more relevant output if they knew whether the audience is a SOC analyst, security manager, or CISO. |

# **2\.  Architecture: Conversation Turn Engine for Security Agents**

The fix applies the same Conversation Turn Engine pattern used for the CSOD fix. A SecurityConversationConfig object drives all behaviour. The engine nodes contain no agent-specific logic. Swapping the config switches from Compliance mode to DT mode. Both agents share the same interrupt mechanism, the same checkpoint dataclasses, and the same resume protocol.

## **2.1  Pipeline vs Conversation Turns**

| PIPELINE — current, broken | CONVERSATION TURNS — required |
| :---- | :---- |
| intent\_classifier fires immediately. profile\_resolver routes to specialist agents. No user input collected before execution. framework\_id unconfirmed. selected\_data\_sources empty. Planner fires a plan nobody approved. | Each conversation node writes a checkpoint and stops. API reads checkpoint and sends turn to client. Client answers → API injects into state field → graph resumes. framework\_id confirmed before any agent reads it. selected\_data\_sources collected before retrieval nodes run. Plan is previewed before executor fires. |
| DT: dt\_playbook\_template defaults to A. is\_leen\_request defaults to False. dashboard persona never asked. Refinement counters mutate in routing functions. | DT: Template A/B/C is the first question asked. is\_leen\_request collected in scoping turn. Dashboard persona asked before question\_generator runs. Refinement counter increments inside a dedicated reset node, not a router. |

## **2.2  Turn Types (Shared with CSOD Engine)**

| Type | Used for | Frontend widget |
| :---- | :---- | :---- |
| CONFIRMATION | Engine restates what it matched — user verifies or corrects. | Summary card \+ Yes / No / Adjust CTA |
| SCOPING | Engine needs additional context before proceeding. | Grouped chip questions — form style, all questions in one block |
| DECISION | Meaningful path fork — each option leads to different output. | Large navigation cards with descriptions. One question per turn. |
| EXECUTION\_PREVIEW | Engine summarises what it will run — user approves before planner fires. | Plan summary card \+ Approve / Adjust CTA. Security-specific type not in CSOD. |

## **2.3  Compliance Workflow — Conversation Flow with Interrupt Points**

| HOW RESUME WORKS:  The API holds the LangGraph thread\_id across turns as session\_id. When the user responds, the API injects the answer into checkpoint.resume\_with\_field, sets compliance\_checkpoint\_resolved=True, and calls graph.ainvoke() again. The graph restores at the stopped node and continues. |  |  |  |  |
| :---- | :---- | :---- | :---- | :---- |
| **Phase** | **New Node** | **Turn Type** | **Pauses?** | **User Response → state field** |
| 0A | intent\_confirm\_node (NEW) | DECISION | ✓ | intent |
| 0B | framework\_confirm\_node (NEW) | CONFIRMATION | ✓ | framework\_id |
| 0C | datasource\_scoping\_node (NEW) | SCOPING | ✓ | selected\_data\_sources |
| 0D | compliance\_scope\_node (NEW) ← main fix | SCOPING | ✓ | compliance\_scoping\_answers |
| 0E (dashboard only) | persona\_confirm\_node (NEW) | DECISION | ✓ | persona |
| 0F | execution\_preview\_node (NEW) | EXECUTION\_PREVIEW | ✓ | compliance\_execution\_confirmed |
| — | intent\_classifier (existing, with bypass) | — | — | reads pre-resolved intent |
| — | profile\_resolver (existing) | — | — | — |
| → | Downstream specialist agents fire | — | — | — |

## **2.4  Detection & Triage Workflow — Conversation Flow with Interrupt Points**

| KEY DIFFERENCE FROM COMPLIANCE:  DT's first question is always the template selector (A/B/C). This is the single most important piece of information for DT — it determines whether detection\_engineer, triage\_engineer, or both run. It must be asked before framework or datasource collection because template C changes which enrichment paths fire. |  |  |  |  |
| :---- | :---- | :---- | :---- | :---- |
| **Phase** | **New Node** | **Turn Type** | **Pauses?** | **User Response → state field** |
| 0A | dt\_template\_confirm\_node (NEW) ← first question | DECISION | ✓ | dt\_playbook\_template |
| 0B | dt\_framework\_confirm\_node (NEW) | CONFIRMATION | ✓ | framework\_id |
| 0C | dt\_datasource\_scoping\_node (NEW) | SCOPING | ✓ | selected\_data\_sources |
| 0D | dt\_scope\_node (NEW) ← main fix | SCOPING | ✓ | dt\_scoping\_answers |
| 0E (dashboard only) | dt\_persona\_confirm\_node (NEW) | DECISION | ✓ | dt\_dashboard\_persona |
| — | dt\_intent\_classifier (existing, with bypass) | — | — | reads pre-resolved template \+ intent |
| — | dt\_planner (existing) | — | — | — |
| → | DT enrichment \+ execution pipeline fires | — | — | — |

# **3\.  The Security Configuration Object**

One SecurityConversationConfig instance per agent. All conversation behaviour is derived from this config. The engine nodes contain no agent-specific logic — they read config and produce checkpoints. Unlike the LMS VerticalConversationConfig, the security config does not use L1/L2 vector concept lookup. Instead, it resolves framework and datasource choices from static option sets.

## **3.1  SecurityConversationConfig Fields**

| Field | Type | Purpose |
| :---- | :---- | :---- |
| agent\_id | str | Identifier for logging and route prefixes. 'compliance' | 'detection\_triage' |
| display\_name | str | Human-facing agent name shown in Lexy UI. |
| framework\_options | List\[dict\] | All selectable frameworks. Each has id, label, description. Shown in framework\_confirm\_node DECISION or CONFIRMATION turn. |
| datasource\_options | List\[dict\] | All selectable security tools. Each has id, label. Shown in datasource\_scoping\_node SCOPING turn (multi-select chips). |
| template\_options | List\[dict\] | None | DT only. A/B/C template choices shown in dt\_template\_confirm\_node. None for compliance (no template concept). |
| scoping\_question\_templates | Dict\[str, ScopingQuestionTemplate\] | Maps filter\_name → question. Shared template lookup mechanism identical to LMS. Security-specific filter names: severity, time\_period, environment, asset\_type, threat\_scenario. |
| always\_include\_filters | List\[str\] | Filter names always asked regardless of area/context. Security defaults: \['severity', 'time\_period'\]. |
| intent\_options | List\[dict\] | Selectable intents shown in intent\_confirm\_node. Each has id, label, description. Compliance: 5 intents. DT: 4 intents. |
| requires\_execution\_preview | bool | If True, execution\_preview\_node fires after scoping and before intent\_classifier. Default True for compliance (has multi-step planner). False for DT (single-path pipeline). |
| intent\_to\_workflow | Dict\[str, str\] | Maps confirmed intent → downstream workflow id. Used by workflow router to fire correct pipeline. |
| state\_key\_prefix | str | Prefix for all conversation state keys. 'compliance' or 'dt'. Prevents key collision between agents. |
| max\_scoping\_questions\_per\_turn | int | Cap on questions shown in a single scoping turn. Default: 3\. |

## **3.2  Security Scoping Question Templates**

These templates cover all filter\_names relevant to the security agents. The same ScopingQuestionTemplate dataclass is used as in the LMS config — no code change. Unknown filter names are silently skipped.

| filter\_name | Question shown to user | state\_key written | Type | Agents |
| :---- | :---- | :---- | :---- | :---- |
| severity | Which severity levels should I focus on? | severity\_filter | multi | Both |
| time\_period | What time window matters most? | time\_window | single | Both |
| environment | Which environment should I analyse? | environment | single | Both |
| asset\_type | What type of assets are in scope? | asset\_type | multi | Compliance |
| threat\_scenario | What threat scenario are you focused on? | threat\_scenario | single | Both |
| assessment\_scope | What should the analysis cover? | assessment\_scope | single | Compliance |
| secondary\_frameworks | Which other frameworks should I map to? | secondary\_framework\_ids | multi | Compliance (cross-framework) |
| generate\_sql | Should I generate dbt-compatible gold model SQL? | generate\_sql | single | DT (leen path) |
| is\_leen\_request | Are you requesting Cube.js schema output? | is\_leen\_request | single | DT |

## **3.3  Compliance Config — Intent Options**

Five intent options shown in intent\_confirm\_node. All use DECISION turn type (large navigation cards).

| intent id | Label | Description shown to user |
| :---- | :---- | :---- |
| detection\_engineering | Write detection rules and SIEM queries | Generate SIEM rules, sigma rules, and detection logic for a specific framework and threat |
| risk\_control\_mapping | Map risks to controls | Identify which controls apply to your risks across your security stack |
| gap\_analysis | Find compliance gaps | Identify what is missing against a framework — controls not implemented, evidence not collected |
| cross\_framework\_mapping | Map across multiple frameworks | See how your controls satisfy NIST, ISO 27001, SOC 2, and HIPAA simultaneously |
| dashboard\_generation | Build a compliance dashboard | Generate a dashboard showing compliance posture, control coverage, and risk metrics |

## **3.4  DT Config — Template Options (First Question)**

| template id | Label | Description shown to user |
| :---- | :---- | :---- |
| A | Detection rules only | SIEM rules, sigma rules, detection queries — no triage recommendations. Runs: detection\_engineer → siem\_rule\_validator → metric\_calculation\_validator → playbook\_assembler. |
| B | Triage recommendations only | Metric recommendations and triage guidance — no SIEM rules generated. Runs: metric\_feasibility\_filter → triage\_engineer → metric\_calculation\_validator → playbook\_assembler. |
| C | Full pipeline — detection \+ triage | SIEM rules first, then triage recommendations that reference detection output. Runs both engineer paths in sequence. |
| dashboard | Dashboard for detection metrics | Generate a dashboard showing detection coverage, alert volume, and triage KPIs. Bypasses detection and triage engineers entirely. |

# **4\.  New Node Designs**

## **4.1  intent\_confirm\_node  (NEW — Compliance Phase 0A)**

The first node in the compliance conversation planner. Runs before intent\_classifier. Checks whether intent is already inferrable from the query with high confidence. If yes, presents it as a CONFIRMATION turn. If not, presents the full DECISION turn with all five intent cards.

* State reads: user\_query, intent (if pre-resolved by API context)

* State writes: compliance\_conversation\_checkpoint (DECISION or CONFIRMATION type)

* resume\_with\_field: intent

* High-confidence signal: keywords like 'gap analysis', 'detect', 'dashboard' resolve to CONFIRMATION. Ambiguous queries get DECISION.

* On resume: state.intent is set. Graph continues to framework\_confirm\_node.

| Option shown (DECISION type) | What it does |
| :---- | :---- |
| Detection rules \+ SIEM queries | Sets intent=detection\_engineering. Graph continues to framework\_confirm\_node. |
| Map risks to controls | Sets intent=risk\_control\_mapping. |
| Find compliance gaps | Sets intent=gap\_analysis. |
| Map across frameworks | Sets intent=cross\_framework\_mapping. Adds secondary\_frameworks to always\_include\_filters for scope\_node. |
| Build a compliance dashboard | Sets intent=dashboard\_generation. Adds persona question to scope\_node. |

## **4.2  dt\_template\_confirm\_node  (NEW — DT Phase 0A — The First Question)**

The most important new node in the DT conversation planner. Always runs first — before framework, before datasource, before anything else. The template selection directly determines which branches of the DT pipeline fire. Getting this wrong wastes the entire detection or triage chain.

* State reads: user\_query, dt\_playbook\_template (if pre-set in API context)

* State writes: dt\_conversation\_checkpoint (DECISION type — large cards, always shown)

* resume\_with\_field: dt\_playbook\_template

* Never skipped: Even if query contains 'detection', the template still needs explicit confirmation — 'detection' could mean A or C.

* Skip condition: dt\_playbook\_template is already set in state AND api\_context.confirmed=True. This allows programmatic pre-fill from the calling service.

## **4.3  framework\_confirm\_node  (NEW — Compliance Phase 0B / DT Phase 0B)**

Shared node for both agents. If a framework signal is found in the user query (keyword match), presents CONFIRMATION turn ('I will use HIPAA — is that right?'). If no signal found, presents DECISION turn with all framework options.

* State reads: user\_query, framework\_id (if pre-extracted)

* State writes: compliance\_conversation\_checkpoint or dt\_conversation\_checkpoint (CONFIRMATION or DECISION)

* resume\_with\_field: framework\_id

* Keyword signals: 'hipaa', 'phi' → HIPAA. 'nist', 'csf' → NIST CSF. 'soc 2', 'trust services' → SOC 2\. 'iso 27001' → ISO 27001\. 'pci' → PCI DSS.

* Adjust option: If CONFIRMATION turn, user can select 'Use a different framework' → graph shows DECISION with all options.

| Option in CONFIRMATION turn | What it does |
| :---- | :---- |
| Yes — \[detected\_framework\] is correct | Sets framework\_id \= detected\_id. Continues to datasource\_scoping\_node. |
| Use a different framework | resume\_with\_field \= framework\_id. Converts turn to DECISION with all framework options shown. |

## **4.4  datasource\_scoping\_node  (NEW — Compliance Phase 0C / DT Phase 0C)**

Collects selected\_data\_sources as a multi-select SCOPING turn. This is the single field that gates product capability scoring, MDL schema retrieval, and Qdrant product\_capabilities lookup. It is always required — there is no skip condition.

* State reads: selected\_data\_sources (if pre-populated from tenant profile API)

* Skip condition: selected\_data\_sources is already non-empty AND api\_context.datasources\_confirmed=True.

* State writes: checkpoint with SCOPING turn. Multi-select chips from config.datasource\_options.

* resume\_with\_field: selected\_data\_sources (list of tool ids)

* Note for DT: selected\_data\_sources feeds directly into dt\_metrics\_retrieval\_node product capability query and dt\_mdl\_schema\_retrieval\_node schema lookup. Empty list \= generic output.

## **4.5  compliance\_scope\_node  (NEW — Compliance Phase 0D — Main Fix)**

The missing scoping node for the compliance workflow. Builds the scoping questions based on the confirmed intent. Each intent has a different set of always\_include\_filters and optional filters. Unknown filter names are silently skipped. Caps at max\_scoping\_questions\_per\_turn.

* State reads: intent, framework\_id (confirmed), selected\_data\_sources (confirmed)

* State writes: compliance\_conversation\_checkpoint (SCOPING type)

* resume\_with\_field: compliance\_scoping\_answers

* Filters always included: severity, time\_period

* Filters included for detection\_engineering: \+ threat\_scenario, environment

* Filters included for gap\_analysis: \+ assessment\_scope

* Filters included for cross\_framework\_mapping: \+ secondary\_frameworks

* Filters included for dashboard\_generation: \+ persona (as DECISION question)

* Empty filter case: sets compliance\_scoping\_complete=True, skips checkpoint. No unnecessary questions.

## **4.6  dt\_scope\_node  (NEW — DT Phase 0D — Main Fix)**

The missing scoping node for the DT workflow. Builds scoping questions based on the confirmed template and framework. Template A/C always ask threat\_scenario and severity. Template B (triage-only) skips threat\_scenario. Dashboard template asks persona.

* State reads: dt\_playbook\_template (confirmed), framework\_id (confirmed)

* State writes: dt\_conversation\_checkpoint (SCOPING type)

* resume\_with\_field: dt\_scoping\_answers

* Filters always included: time\_period

* Filters for template A/C: \+ severity, threat\_scenario, environment

* Filters for template B: \+ severity, environment (threat\_scenario skipped — triage is reactive)

* Filters for dashboard template: \+ persona (as DECISION question)

* is\_leen\_request and generate\_sql: collected here as single-select yes/no options. Both default to False.

## **4.7  execution\_preview\_node  (NEW — Compliance Phase 0F only)**

Specific to the compliance workflow. After scoping is complete, this node summarises the execution plan that the planner would generate — the sequence of specialist agents that will run — and presents it as an EXECUTION\_PREVIEW turn. User approves or adjusts before planner\_node fires.

* State reads: intent, framework\_id, compliance\_scoping\_answers

* State writes: compliance\_conversation\_checkpoint (EXECUTION\_PREVIEW type)

* resume\_with\_field: compliance\_execution\_confirmed

* The preview is template-based (no LLM call). intent=gap\_analysis always runs gap\_analysis\_node. intent=cross\_framework\_mapping always runs cross\_framework\_mapper\_node. Full-planner intents preview the planned agent chain: framework\_analyzer → detection\_engineer → playbook\_writer → test\_generator.

* Approve option: sets compliance\_execution\_confirmed=True. Graph continues to intent\_classifier (with bypass) → profile\_resolver → downstream agents.

* Adjust option: sets resume\_with\_field=intent. Graph resumes at intent\_confirm\_node — user picks a different intent.

## **4.8  dt\_validation\_reset\_node  (NEW — DT — Routing Bug Fix)**

A single-purpose node that runs between dt\_siem\_rule\_validator and dt\_detection\_engineer (on re-try), and between dt\_metric\_calculation\_validator and the next engineer (on re-try). It increments or resets dt\_validation\_iteration and clears dt\_validating\_detection\_metrics. Moves state mutation out of routing functions where it is unreliable.

* State reads: dt\_siem\_validation\_passed, dt\_metric\_validation\_passed, dt\_validating\_detection\_metrics, dt\_validation\_iteration

* State writes: dt\_validation\_iteration (incremented on retry, reset to 0 on phase transition), dt\_validating\_detection\_metrics (reset to False when moving to triage phase)

* This node replaces the state mutations currently in \_route\_after\_siem\_validator and \_route\_after\_metric\_validator

* Routing functions become pure: they only read state and return a string. No mutations.

# **5\.  Rebuilt Graph Topology**

## **5.1  \_route\_with\_interrupt — The Generic Routing Function**

Identical to the CSOD implementation. Used at every conversation node. State key prefix changes per agent ('compliance\_' or 'dt\_') but the logic is identical.

def \_route\_with\_interrupt(state, checkpoint\_key, resolved\_key) \-\> str:

    checkpoint \= state.get(checkpoint\_key)

    if checkpoint and not state.get(resolved\_key):

        return 'interrupt'  \# → END, API handles client interaction

    state\[checkpoint\_key\] \= None

    state\[resolved\_key\] \= False

    return 'continue'

## **5.2  Compliance — New Conversation Planner Topology**

| Node | Type | On interrupt: resumed by |
| :---- | :---- | :---- |
| intent\_confirm\_node ← NEW | CONVERSATION (interrupt) | User selects intent → intent |
| framework\_confirm\_node ← NEW | CONVERSATION (interrupt) | User confirms or selects framework → framework\_id |
| datasource\_scoping\_node ← NEW | CONVERSATION (interrupt) | User multi-selects tools → selected\_data\_sources |
| compliance\_scope\_node ← NEW (main fix) | CONVERSATION (interrupt) | User answers scoping Qs → compliance\_scoping\_answers |
| persona\_confirm\_node ← NEW (dashboard only) | CONVERSATION (interrupt) | User selects persona → persona |
| execution\_preview\_node ← NEW | CONVERSATION (interrupt) | User approves plan → compliance\_execution\_confirmed |
| intent\_classifier (existing \+ bypass) | Pipeline | — |
| profile\_resolver (existing) | Pipeline | — |
| → metrics\_recommender / gap\_analysis / cross\_framework / dashboard / planner chain | External pipeline | — |

## **5.3  Detection & Triage — New Conversation Planner Topology**

| Node | Type | On interrupt: resumed by |
| :---- | :---- | :---- |
| dt\_template\_confirm\_node ← NEW (first) | CONVERSATION (interrupt) | User selects A/B/C/dashboard → dt\_playbook\_template |
| dt\_framework\_confirm\_node ← NEW | CONVERSATION (interrupt) | User confirms framework → framework\_id |
| dt\_datasource\_scoping\_node ← NEW | CONVERSATION (interrupt) | User multi-selects tools → selected\_data\_sources |
| dt\_scope\_node ← NEW (main fix) | CONVERSATION (interrupt) | User answers scoping Qs → dt\_scoping\_answers |
| dt\_persona\_confirm\_node ← NEW (dashboard only) | CONVERSATION (interrupt) | User selects persona → dt\_dashboard\_persona |
| dt\_intent\_classifier (existing \+ bypass) | Pipeline | — |
| dt\_planner (existing) | Pipeline | — |
| dt\_framework\_retrieval (existing) | Pipeline | Now has framework\_id confirmed before running |
| → enrichment \+ detection/triage pipeline fires | External pipeline | — |

## **5.4  route\_from\_metrics\_recommender — Missing Branch Fix**

The existing routing function from metrics\_recommender only maps to dashboard\_generator and planner. Three branches are missing. This must be fixed alongside the conversation nodes.

def route\_from\_metrics\_recommender(state):

    intent \= state.get('intent', '')

    if intent \== 'dashboard\_generation':    return 'dashboard\_generator'

    elif intent \== 'risk\_control\_mapping':  return 'risk\_control\_mapper'   \# MISSING

    elif intent \== 'gap\_analysis':           return 'gap\_analysis'          \# MISSING

    elif intent \== 'cross\_framework\_mapping': return 'cross\_framework\_mapper' \# MISSING

    else:                                    return 'planner'

The workflow.add\_conditional\_edges() call for 'metrics\_recommender' must also be updated to include the three missing target keys in the routing map.

# **6\.  State Fields — Before and After**

## **6.1  Compliance Workflow State Fields**

| Field | Set by | Read by | Status |
| :---- | :---- | :---- | :---- |
| intent | intent\_classifier\_node | route\_from\_profile\_resolver, all agents | ✅ Working — ❌ Never confirmed with user |
| framework\_id | profile\_resolver\_node (inferred) | gap\_analysis, cross\_framework\_mapper, framework\_analyzer | ❌ Never confirmed. User never sees which framework was matched. |
| selected\_data\_sources | — | metrics\_recommender, dashboard\_generator, planner | ❌ Never collected. No node asks. |
| compliance\_scoping\_answers | — | compliance\_scope\_node (planned), workflow\_router | ❌ Field does not exist. Scoping node does not exist. |
| persona | — | dashboard\_generator | ❌ Never collected. Dashboard fires for unknown audience. |
| compliance\_execution\_confirmed | — | execution\_preview\_node (planned) | ❌ Field does not exist. User never approves plan. |
| compliance\_conversation\_checkpoint | — | API layer \+ \_route\_with\_interrupt | ❌ Does not exist. No interrupt mechanism. |
| compliance\_checkpoint\_resolved | — | API layer \+ \_route\_with\_interrupt | ❌ Does not exist. |
| compliance\_profile.playbook\_resolved\_intent | — | intent\_classifier\_node (bypass) | ❌ Bypass never triggers. Intent re-classified on every run. |
| data\_enrichment.needs\_metrics | intent\_classifier\_node (LLM) | route\_from\_profile\_resolver | ⚠️ Set by LLM with no user confirmation. Gates metrics\_recommender branch. |

## **6.2  Detection & Triage Workflow State Fields**

| Field | Set by | Read by | Status |
| :---- | :---- | :---- | :---- |
| dt\_playbook\_template | Defaults to 'A' in \_route\_after\_scoring | All routing functions | ❌ Never set by user. Triage-only users get detection pipeline. |
| framework\_id | dt\_intent\_classifier\_node (inferred) | dt\_framework\_retrieval\_node | ❌ Never confirmed. Wrong framework silently corrupts control retrieval. |
| selected\_data\_sources | create\_dt\_initial\_state default \[\] | dt\_metrics\_retrieval, dt\_mdl\_schema\_retrieval | ❌ Never asked. Product capability scoring runs with empty source list. |
| data\_enrichment.needs\_mdl | dt\_planner\_node (LLM) | route after framework retrieval | ⚠️ LLM decides without user input. If False, dbt schema generation branch skipped. |
| is\_leen\_request | create\_dt\_initial\_state default False | \_route\_after\_playbook\_assembler | ❌ Never asked. Cube.js path never fires for LEEN users. |
| dt\_scoping\_answers | — | dt\_scope\_node (planned) | ❌ Field does not exist. Scoping node does not exist. |
| dt\_conversation\_checkpoint | — | API layer \+ \_route\_with\_interrupt | ❌ Does not exist. No interrupt mechanism. |
| dt\_validation\_iteration | Mutated in \_route\_after\_siem\_validator router | All validator routing functions | ⚠️ State mutation in routing function. Counter may not persist reliably. |
| dt\_validating\_detection\_metrics | Mutated in \_route\_after\_metric\_validator router | \_route\_after\_metric\_validator | ⚠️ Same issue. Reset may not persist. |
| dt\_siem\_validation\_passed | dt\_siem\_rule\_validator\_node | \_route\_after\_siem\_validator | ✅ Set by node correctly. |
| dt\_metric\_validation\_passed | dt\_metric\_calculation\_validator\_node | \_route\_after\_metric\_validator | ✅ Set by node correctly. |

## **6.3  intent\_classifier\_node Bypass — Both Agents**

Once the conversation planner has confirmed intent and populated compliance\_profile.playbook\_resolved\_intent, the internal intent classifiers must bypass their LLM calls. Four lines added to each classifier — no other changes.

\# In compliance intent\_classifier\_node:

if state.get('intent') and state.get('compliance\_profile', {}).get('playbook\_resolved\_intent'):

    logger.info(f"Intent pre-resolved: {state\['intent'\]}")

    return state  \# skip LLM call

\# In dt\_intent\_classifier\_node:

if state.get('intent') and state.get('compliance\_profile', {}).get('playbook\_resolved\_intent'):

    logger.info(f"DT intent pre-resolved: {state\['intent'\]}")

    if not state.get('dt\_playbook\_template'):

        state\['dt\_playbook\_template'\] \= 'C'  \# safe default if template was not asked

    return state

## **6.4  Compliance workflow\_router\_node — Required Additions**

After scoping answers are collected, workflow\_router must unpack them into the compliance\_profile and set playbook\_resolved\_intent to trigger the bypass.

* Set compliance\_profile.playbook\_resolved\_intent \= True

* Unpack compliance\_scoping\_answers into compliance\_profile top-level keys: severity\_filter, time\_window, environment, threat\_scenario, assessment\_scope, secondary\_framework\_ids

* Set persona on compliance\_profile if collected (dashboard intent)

* Set compliance\_profile.selected\_data\_sources from confirmed selected\_data\_sources

## **6.5  DT — dt\_planner\_node Changes After Scoping**

After dt\_scoping\_answers are collected, dt\_planner\_node receives them via state. Three additions needed:

* Read dt\_scoping\_answers and copy severity\_filter, time\_window, environment, threat\_scenario into compliance\_profile for downstream node access

* Read is\_leen\_request from dt\_scoping\_answers and write it directly to state.is\_leen\_request

* Read generate\_sql from dt\_scoping\_answers and write it to state.dt\_generate\_sql

* Set compliance\_profile.playbook\_resolved\_intent \= True (triggers bypass)

# **7\.  API Layer — Resume Protocol**

The API layer is identical for both agents and reuses the same session and resume mechanism as CSOD. The only difference is the agent\_type field in the request, which determines which conversation planner graph to invoke.

| Request field | Description |
| :---- | :---- |
| session\_id | LangGraph thread\_id. Persisted in MemorySaver (dev) / Redis (prod). All turns in a conversation use the same session\_id. |
| agent\_type | 'compliance' | 'detection\_triage'. Determines which conversation planner graph and SecurityConversationConfig instance to use. |
| response.field | The state field to inject the user answer into. This is checkpoint.resume\_with\_field from the previous turn response. |
| response.value | The actual answer. For DECISION: a string. For SCOPING: a dict mapping state\_key → selected option id or list of ids. For EXECUTION\_PREVIEW: 'approve' or 'adjust'. |

## **7.1  Request/Response Shape**

POST /api/conversation/turn

{

  session\_id: 'abc-123',

  agent\_type: 'detection\_triage',

  response: {

    field: 'dt\_playbook\_template',    // from previous checkpoint.resume\_with\_field

    value: 'C'                        // Template C selected

  }

}

// Response when another turn is needed:

{ session\_id, phase, turn: ConversationTurn, is\_complete: false }

// Response when all conversation turns complete (compliance):

{ session\_id, phase: 'confirmed', is\_complete: true,

  compliance\_initial\_state: { intent, framework\_id, selected\_data\_sources,

    compliance\_profile: { severity\_filter, time\_window, playbook\_resolved\_intent: true } } }

// Response when all conversation turns complete (DT):

{ session\_id, phase: 'confirmed', is\_complete: true,

  dt\_initial\_state: { dt\_playbook\_template, framework\_id, selected\_data\_sources,

    is\_leen\_request, dt\_generate\_sql, dt\_scoping\_answers, ... } }

# **8\.  Implementation Steps for Cursor**

Build in this exact order. Each step has testable acceptance criteria before moving to the next. Steps 1-3 are shared infrastructure (if the CSOD conversation engine is already built, these files exist and only need extensions). Steps 4-12 are agent-specific.

| Step | File to Create / Edit | What to Implement | Test |
| :---- | :---- | :---- | :---- |
| 1 | app/conversation/turn.py (extend) | Add EXECUTION\_PREVIEW to TurnOutputType enum. Add ExecutionPreviewTurn dataclass with fields: steps\[\] (list of agent names), intent, framework\_id, estimated\_agents. | Instantiate ExecutionPreviewTurn, JSON round-trip. Assert type serialises to 'EXECUTION\_PREVIEW'. |
| 2 | app/conversation/security\_config.py (NEW) | SecurityConversationConfig and SecurityScopingQuestionTemplate dataclasses. Shared framework\_options list (NIST CSF, SOC 2, HIPAA, ISO 27001, PCI DSS). Shared datasource\_options list (Qualys, CrowdStrike, Okta, Splunk, Sentinel, Wiz, Snyk, Elastic). | Import without error. Assert len(framework\_options) \== 6\. Assert len(datasource\_options) \== 8\. |
| 3 | app/conversation/verticals/compliance\_config.py (NEW) | COMPLIANCE\_SCOPING\_TEMPLATES with 7 templates (severity, time\_period, environment, asset\_type, threat\_scenario, assessment\_scope, secondary\_frameworks). COMPLIANCE\_CONVERSATION\_CONFIG instance. | Assert all 7 keys load. Assert config.always\_include\_filters \== \['severity', 'time\_period'\]. Assert config.requires\_execution\_preview \== True. |
| 4 | app/conversation/verticals/dt\_config.py (NEW) | DT\_SCOPING\_TEMPLATES with 7 templates (severity, time\_period, environment, threat\_scenario, is\_leen\_request, generate\_sql, persona). DT\_TEMPLATE\_OPTIONS list (A, B, C, dashboard). DT\_CONVERSATION\_CONFIG instance. | Assert all 7 keys load. Assert config.requires\_execution\_preview \== False. Assert len(config.template\_options) \== 4\. |
| 5 | app/conversation/nodes/intent\_confirm.py (NEW) | intent\_confirm\_node(state, config). Reads user\_query, keyword-matches for intent signals. Writes checkpoint: CONFIRMATION if signal found, DECISION with config.intent\_options if not. resume\_with\_field: intent. | Mock state with 'show me my compliance gaps' → CONFIRMATION with intent=gap\_analysis. Mock with 'help me with compliance' → DECISION with 5 options. Mock with pre-set intent → skip. |
| 6 | app/conversation/nodes/dt\_template\_confirm.py (NEW) | dt\_template\_confirm\_node(state, config). Always DECISION turn with config.template\_options unless api\_context.confirmed=True. No keyword extraction — always ask. resume\_with\_field: dt\_playbook\_template. | Mock any query → DECISION with 4 template options. Mock with api\_context.confirmed=True and dt\_playbook\_template='A' → skip. |
| 7 | app/conversation/nodes/framework\_confirm.py (NEW) | framework\_confirm\_node(state, config). Keyword matches query against config.framework\_options signals. CONFIRMATION if match found. DECISION if no match. Handles 'adjust' option. resume\_with\_field: framework\_id. | Mock 'HIPAA PHI protection' → CONFIRMATION with framework\_id=hipaa. Mock 'security framework rules' → DECISION. Mock with framework\_id pre-set → skip. |
| 8 | app/conversation/nodes/datasource\_scoping.py (NEW) | datasource\_scoping\_node(state, config). Always SCOPING multi-select from config.datasource\_options. Skip if selected\_data\_sources non-empty and api\_context.datasources\_confirmed=True. resume\_with\_field: selected\_data\_sources. | Mock empty state → SCOPING checkpoint with 8 options. Mock pre-confirmed sources → skip. Assert interaction\_mode='multi'. |
| 9 ← MAIN FIX | app/conversation/nodes/compliance\_scope.py (NEW) | compliance\_scope\_node(state, config). Reads intent. Looks up filter\_names in config.scoping\_question\_templates. Always adds always\_include\_filters. Caps at max\_scoping\_questions\_per\_turn. Filters framework\_id from secondary\_frameworks list. Writes SCOPING checkpoint. | A: intent=gap\_analysis → severity \+ time\_period \+ assessment\_scope (3 questions). B: intent=cross\_framework\_mapping → secondary\_frameworks shown without confirmed framework. C: intent=dashboard\_generation → persona as DECISION question. D: all scoping pre-answered → scoping\_complete=True, no checkpoint. |
| 10 ← MAIN FIX | app/conversation/nodes/dt\_scope.py (NEW) | dt\_scope\_node(state, config). Reads dt\_playbook\_template. Builds filter list per template: A/C → severity \+ time\_period \+ environment \+ threat\_scenario. B → severity \+ time\_period \+ environment. dashboard → persona. Adds is\_leen\_request and generate\_sql for all templates. Writes SCOPING checkpoint. | A: template=A → 5 questions (severity, time\_period, env, threat, is\_leen). B: template=B → 4 questions (severity, time\_period, env, is\_leen). C: template=dashboard → persona \+ time\_period \+ is\_leen. D: all pre-answered → scoping\_complete=True. |
| 11 | app/conversation/nodes/execution\_preview.py (NEW) | execution\_preview\_node(state, config). Reads intent \+ framework\_id \+ scoping\_answers. Builds static preview dict: maps intent to agent chain list (no LLM). Writes EXECUTION\_PREVIEW checkpoint. | intent=gap\_analysis → preview shows \['gap\_analysis'\]. intent=detection\_engineering → shows \['framework\_analyzer', 'detection\_engineer', 'playbook\_writer', 'test\_generator'\]. Approve response → compliance\_execution\_confirmed=True. |
| 12 | app/agents/detectiontriage/dt\_workflow.py — validation\_reset\_node | dt\_validation\_reset\_node(state). Reads dt\_siem\_validation\_passed, dt\_metric\_validation\_passed, dt\_validation\_iteration. Increments iteration on failure \+ under limit. Resets to 0 on phase transition. Clears dt\_validating\_detection\_metrics. Returns updated state. Remove state mutations from both routing functions. | Assert state mutation in \_route\_after\_siem\_validator removed. Assert node called with failed validation increments counter. Assert node called after triage phase clears dt\_validating\_detection\_metrics. |
| 13 | app/conversation/compliance\_planner\_workflow.py (NEW) | build\_compliance\_conversation\_planner(config) → StateGraph. \_route\_with\_interrupt for compliance. Correct node order: intent\_confirm → framework\_confirm → datasource\_scoping → compliance\_scope → \[persona\_confirm if dashboard\] → execution\_preview → intent\_classifier (with bypass) → profile\_resolver → downstream. | Build graph → assert node list. Run \_route\_with\_interrupt with checkpoint → 'interrupt'. Run with resolved=True → 'continue'. |
| 14 | app/conversation/dt\_planner\_workflow.py (NEW) | build\_dt\_conversation\_planner(config) → StateGraph. \_route\_with\_interrupt for DT. Node order: dt\_template\_confirm → dt\_framework\_confirm → dt\_datasource\_scoping → dt\_scope → \[dt\_persona\_confirm if dashboard\] → dt\_intent\_classifier (with bypass) → dt\_planner → DT pipeline. | Build graph → assert node list. Assert dt\_template\_confirm is entry point. |
| 15 | app/agents/nodes.py \+ dt\_nodes.py — add bypass | Add 4-line playbook\_resolved\_intent bypass to intent\_classifier\_node (compliance) and dt\_intent\_classifier\_node (DT). Add scoping\_answers unpack to compliance workflow\_router\_node and dt\_planner\_node. | Run intent\_classifier with pre-resolved intent \+ playbook\_resolved\_intent=True → returns immediately, no LLM call. Assert compliance\_profile.severity\_filter populated after router runs with scoping\_answers. |
| 16 | detectiontriageworkflows/workflow.py — fix routing map | Update route\_from\_metrics\_recommender to add risk\_control\_mapping, gap\_analysis, cross\_framework\_mapping branches. Update add\_conditional\_edges call to include 3 missing target keys. | Assert intent=gap\_analysis \+ needs\_metrics=True → routes to gap\_analysis, not planner. |
| 17 | api/routes/conversation.py (extend) | Add agent\_type routing: 'compliance' → compliance planner. 'detection\_triage' → DT planner. Reuse session\_id / MemorySaver pattern from CSOD endpoint. Return compliance\_initial\_state or dt\_initial\_state on is\_complete. | Simulate 5-turn DT conversation: template → framework → datasources → scoping → is\_complete. Assert dt\_initial\_state.dt\_playbook\_template='C', framework\_id set, selected\_data\_sources non-empty. |
| 18 | tests/conversation/test\_compliance\_dt.py (NEW) | E2E tests per agent. See Section 9 acceptance tests. | All 8 scenarios pass. |

# **9\.  Prompt Changes Required**

Existing agent prompts do not change. The conversation planner nodes are mostly template-based (no LLM calls) with the exception of framework keyword inference, which uses a simple in-process signal match rather than an LLM. Four prompt files are needed.

| Prompt file | Status | Change |
| :---- | :---- | :---- |
| Existing compliance prompts | ✅ No change needed | compliance\_profile.severity\_filter, time\_window, threat\_scenario are already referenced in planner prompts. Will work correctly once scoping populates these fields. |
| Existing dt\_planner prompt | ✅ No change needed | dt\_planner already reads selected\_data\_sources, framework\_id, and compliance\_profile fields. Will work better once fields are populated before planner runs. |
| 13\_execution\_preview.md (NEW) | ❌ Create this file | System prompt for execution\_preview\_node. Must list the agent chain for each intent without LLM creativity — use a static template with variable substitution. Format: numbered list of agent names with one-line descriptions. No fabrication. |
| 14\_framework\_confirm.md (optional) | ⚠️ Optional | framework\_confirm\_node uses in-process keyword matching, not an LLM call. Only create this prompt if keyword matching proves insufficient and an LLM inference step is needed. Default: skip, use keyword signals. |

## **9.1  13\_execution\_preview.md — Key Instructions**

The execution preview prompt enforces three constraints:

* Template-first: the LLM receives a static agent\_chain list derived from intent. It must summarise the chain in plain language — not invent new steps.

* Plain business language: 'I will analyse your framework controls, then write detection rules, then generate a validation test script.' No node names or technical identifiers shown to user.

* Maximum 3 sentences: Brief and reassuring. The user should feel confident, not overwhelmed. Confirm button is prominent.

## **9.2  E2E Acceptance Tests (Step 18\)**

**Compliance Tests**

* test\_compliance\_gap\_analysis\_keyword\_extracted: 'I need a gap analysis against NIST CSF' → framework\_id pre-extracted via keyword. Turn 0: intent CONFIRMATION. Turn 1: framework CONFIRMATION. Turn 2: datasource SCOPING. Turn 3: compliance\_scope (severity \+ time\_period \+ assessment\_scope). Turn 4: execution\_preview. Turn 5: is\_complete=True. Assert compliance\_profile.assessment\_scope set.

* test\_compliance\_dashboard\_persona\_required: 'Build me a compliance dashboard' → Turn 0: intent CONFIRMATION (dashboard). Scoping includes persona DECISION. is\_complete only after persona confirmed. Assert persona set in compliance\_initial\_state.

* test\_compliance\_cross\_framework\_excludes\_primary: selected framework\_id=nist\_csf → secondary\_frameworks option list must not include NIST CSF.

* test\_compliance\_metrics\_recommender\_routing: intent=gap\_analysis \+ needs\_metrics=True → routes to gap\_analysis, not planner. Assert no planner\_node call.

**Detection & Triage Tests**

* test\_dt\_template\_always\_asked: Any query → Turn 0 is always dt\_template\_confirm DECISION. No pre-extraction skips it without api\_context.confirmed=True.

* test\_dt\_template\_B\_skips\_threat\_scenario: template=B selected → dt\_scope\_node does NOT include threat\_scenario in questions. Assert dt\_scoping\_answers has no threat\_scenario key.

* test\_dt\_leen\_path\_collected: user selects is\_leen\_request=True in scoping → state.is\_leen\_request=True in dt\_initial\_state. \_route\_after\_playbook\_assembler routes to dt\_unified\_format\_converter.

* test\_dt\_validation\_reset\_node\_increments: siem\_validation\_passed=False, iteration=0 → validation\_reset\_node sets iteration=1. Called again: iteration=2. At max iterations: routes to metric\_calculation\_validator.

* test\_dt\_validation\_routing\_function\_is\_pure: Assert \_route\_after\_siem\_validator does not mutate state (no state\['key'\] \= ... assignments).

* test\_dt\_dashboard\_template\_routes\_to\_persona: template=dashboard → dt\_scope\_node includes persona question. dt\_dashboard\_context\_discoverer receives persona in state.

# **10\.  Shared Templates with LMS Engine**

Some scoping question templates are vertical-agnostic. Define them once and import into all configs.

| Template | Defined in | Imported by |
| :---- | :---- | :---- |
| time\_period | app/conversation/templates/shared.py | lms\_config.py, compliance\_config.py, dt\_config.py |
| persona | app/conversation/templates/shared.py | lms\_config.py (dashboard intent), compliance\_config.py, dt\_config.py |
| severity | app/conversation/templates/security\_shared.py (NEW) | compliance\_config.py, dt\_config.py |
| environment | app/conversation/templates/security\_shared.py (NEW) | compliance\_config.py, dt\_config.py |
| threat\_scenario | app/conversation/templates/security\_shared.py (NEW) | compliance\_config.py, dt\_config.py (template A/C only) |

*Any update to the time\_period question options (e.g. adding 'last 90 days') applies automatically to LMS, Compliance, and DT with a single file change.*

Comatrix Labs · CCE Security Agents · Confidential
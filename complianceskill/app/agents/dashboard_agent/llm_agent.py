"""
CCE Layout Advisor — LLM Agent Node
====================================
Two routing paths, selected automatically in intake_node_llm:

  FAST PATH  (routing = "fast")
  ─────────────────────────────
  Triggered when the upstream pipeline has already provided:
    • goal_statement  (what the dashboard should achieve)
    • primary_area / area_concepts  (analytical area confirmed by the user)
    • metrics / kpis  (confirmed metric set)

  intake_node_llm pre-scores templates via DashboardDecisionTreeService and
  puts them in state.  The LLM's only job is to present the top-3 with a
  one-sentence rationale, ask the user to pick one, then call generate_layout_spec.
  No 7-question interrogation.

  SLOW PATH  (routing = "slow")
  ─────────────────────────────
  Triggered when context is sparse (no confirmed area, no metrics, etc.).
  The LLM walks the user through the 7-question decision tree to gather
  destination, category, focus area, metric profile, audience, complexity,
  and interaction mode before scoring and recommending templates.
"""

from __future__ import annotations
import json
from typing import Optional

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_anthropic import ChatAnthropic
from langchain_core.runnables import RunnableConfig

from .state import LayoutAdvisorState, Phase
from .templates import TEMPLATES, CATEGORIES, DECISION_TREE
from .tools import LAYOUT_TOOLS


# ═══════════════════════════════════════════════════════════════════════
# SYSTEM PROMPTS — one per routing path
# ═══════════════════════════════════════════════════════════════════════

# ── FAST PATH ──────────────────────────────────────────────────────────
FAST_PATH_PROMPT = """\
You are the CCE Layout Advisor. The pipeline has already collected the user's goal,
confirmed area/concepts, and selected metrics. Skip the decision-tree questions —
everything you need is in the upstream context.

## What you have
- **goal_statement** — the user's original question / business goal
- **primary_area / area_concepts** — the compliance or analytical area confirmed in the pipeline
- **metrics / kpis** — the specific metrics confirmed by the user
- **persona** — the user's role (e.g. Compliance Analyst, CISO)
- **output_format** — target renderer (echarts → embedded, powerbi, simple)
- **pre_scored_templates** — top templates already ranked by the decision tree

## Your workflow
1. Read pre_scored_templates (or call score_templates once if absent).
2. Present the top 3 options. For each, write one sentence that connects the
   template to the user's **specific** goal and area — e.g.
   "Given your training_completion focus and 11 confirmed metrics, the
   Learning Compliance Command Center fits because it has a 6-cell KPI strip
   for completion rates and drill-down by department."
3. Ask exactly one question: "Which option fits best? (1 / 2 / 3 or describe a change)"
4. When the user picks one, call generate_layout_spec immediately.

## Rules
- Do NOT ask about destination, audience, category, complexity, or metric profile —
  derive them from what you already know.
- Keep each option description to 2–3 sentences maximum.
- Reference the actual area/concept and metric names the user confirmed.
- destination_type ← output_format (echarts→embedded, powerbi→powerbi)
- complexity ← metric count (≤4 low · ≤8 medium · >8 high)
- audience ← persona
"""

# ── SLOW PATH ──────────────────────────────────────────────────────────
SLOW_PATH_PROMPT = """\
You are the CCE Layout Advisor. You are starting without full pipeline context,
so you need to collect a few decisions before recommending a dashboard template.

## 7-Question Decision Tree
Work through these in order — stop as soon as you have enough to score templates.

1. **Destination** — Where will this render?
   embedded/ECharts · powerbi · simple HTML · slack_digest · api_json
2. **Category** — Primary domain:
   compliance_audit · security_operations · learning_development · hr_workforce ·
   risk_management · executive_reporting · data_operations · cross_domain
3. **Focus Area** — e.g. training_completion, vulnerability_management, incident_response
4. **Metric Profile** — What kind of numbers dominate?
   count_heavy · trend_heavy · rate_percentage · comparison · mixed · scorecard
5. **Audience** — Who reads this?
   security_ops · compliance_team · executive_board · learning_admin · data_engineer
6. **Complexity** — How much detail?
   low (summary KPIs only) · medium (standard panels) · high (full drill-down)
7. **Interaction** — How will users engage?
   drill_down · read_only · real_time · scheduled_report

## Conversation flow
1. Review any context already in upstream_context — skip questions you can answer.
2. Ask 1–2 questions per turn (not all 7 at once).
3. Once you have destination + category + focus_area, call match_domain_from_metrics_tool
   (if metrics are present) then call score_templates.
4. Present top 3 and let the user select.
5. Call generate_layout_spec with the chosen template + accumulated decisions.

## Tools available
- match_domain_from_metrics_tool · score_templates · get_template_detail
- generate_layout_spec · list_templates · search_templates · apply_adjustment_handle

## Rules
- Never ask questions that are already answered in upstream_context.
- Destination gates template availability — resolve it first.
- Keep responses concise; explain WHY each template was recommended.
"""


# ═══════════════════════════════════════════════════════════════════════
# ROUTING HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _has_rich_context(upstream: dict) -> bool:
    """
    Return True when the pipeline has provided enough context to skip
    the 7-question decision tree (fast path).

    Requires ALL of:
      • non-empty goal_statement
      • at least one of: primary_area, area_concepts, focus_areas
      • at least one metric or KPI
    """
    has_goal    = bool((upstream.get("goal_statement") or "").strip())
    has_area    = bool(
        upstream.get("primary_area") or
        upstream.get("area_concepts") or
        upstream.get("focus_areas")
    )
    has_metrics = (
        len(upstream.get("metrics", [])) > 0 or
        len(upstream.get("kpis", [])) > 0
    )
    return has_goal and has_area and has_metrics


def _pick_system_prompt(routing: str) -> str:
    return FAST_PATH_PROMPT if routing == "fast" else SLOW_PATH_PROMPT


# ═══════════════════════════════════════════════════════════════════════
# AGENT FACTORY
# ═══════════════════════════════════════════════════════════════════════

def create_llm_agent(
    routing: str = "fast",
    model_name: str = "claude-sonnet-4-5-20250514",
    temperature: float = 0.2,
):
    """Create the LLM agent with the appropriate system prompt bound."""
    llm = ChatAnthropic(model=model_name, temperature=temperature, max_tokens=4096)
    llm_with_tools = llm.bind_tools(LAYOUT_TOOLS)

    prompt = ChatPromptTemplate.from_messages([
        ("system", _pick_system_prompt(routing)),
        ("system", "Upstream context:\n{upstream_context}"),
        ("system", "Decisions resolved so far:\n{decisions}"),
        ("system", "Phase: {phase}  |  Routing: {routing}"),
        MessagesPlaceholder(variable_name="messages"),
    ])

    return prompt | llm_with_tools


# ═══════════════════════════════════════════════════════════════════════
# AGENT NODE  (single node, dual behaviour)
# ═══════════════════════════════════════════════════════════════════════

def llm_agent_node(state: LayoutAdvisorState, config: RunnableConfig) -> dict:
    """LangGraph node. Picks fast or slow prompt based on state['routing']."""
    routing = state.get("routing", "fast")
    agent   = create_llm_agent(routing=routing)

    # Build LangChain message list from state history
    lc_messages = []
    for msg in state.get("messages", []):
        role    = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif role == "agent":
            lc_messages.append(AIMessage(content=content))
        elif role == "system":
            lc_messages.append(SystemMessage(content=content))

    user_response = state.get("user_response", "")
    if user_response and (not lc_messages or lc_messages[-1].content != user_response):
        lc_messages.append(HumanMessage(content=user_response))

    upstream = state.get("upstream_context", {})

    # Enrich upstream with pre-scored templates + area concepts
    enhanced_upstream = _build_enhanced_upstream(upstream, state)

    # Auto-derive decisions from upstream so LLM doesn't have to ask
    auto_decisions   = _derive_decisions_from_upstream(upstream)
    merged_decisions = {**auto_decisions, **state.get("decisions", {})}

    response = agent.invoke({
        "messages":         lc_messages,
        "upstream_context": json.dumps(enhanced_upstream, indent=2, default=str),
        "decisions":        json.dumps(merged_decisions, indent=2, default=str),
        "phase":            state.get("phase", Phase.INTAKE).value,
        "routing":          routing,
    }, config=config)

    if response.tool_calls:
        return _handle_tool_calls(state, response, merged_decisions)

    new_messages = []
    if user_response:
        new_messages.append({"role": "user", "content": user_response, "metadata": {}})
    new_messages.append({
        "role": "agent",
        "content": response.content,
        "metadata": {"phase": state.get("phase", Phase.INTAKE).value, "routing": routing},
    })

    phase = state.get("phase", Phase.INTAKE)
    needs_input = phase not in (Phase.COMPLETE, Phase.SCORING)

    return {
        "messages":        new_messages,
        "decisions":       merged_decisions,
        "needs_user_input": needs_input,
    }


# ═══════════════════════════════════════════════════════════════════════
# CONTEXT HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _build_enhanced_upstream(upstream: dict, state: dict) -> dict:
    """Inject pre-scored templates and normalised area concepts into upstream."""
    enhanced = dict(upstream)

    pre_scored = state.get("recommended_top3") or state.get("candidate_templates")
    if pre_scored:
        enhanced["pre_scored_templates"] = pre_scored

    area_concepts = list(upstream.get("area_concepts") or upstream.get("focus_areas") or [])
    primary_area  = upstream.get("primary_area") or upstream.get("csod_primary_area") or ""
    if primary_area and primary_area not in area_concepts:
        area_concepts = [primary_area] + area_concepts
    if area_concepts:
        enhanced["area_concepts"] = area_concepts

    enhanced["_metric_count"] = len(upstream.get("metrics", []))
    enhanced["_kpi_count"]    = len(upstream.get("kpis", []))

    return enhanced


def _derive_decisions_from_upstream(upstream: dict) -> dict:
    """Auto-resolve decision dimensions that can be inferred from pipeline context."""
    d: dict = {}

    output_format = (upstream.get("output_format") or "echarts").lower()
    dest_map = {"echarts": "embedded", "powerbi": "powerbi",
                "html": "simple", "simple": "simple",
                "slack": "slack_digest", "api": "api_json"}
    d["destination_type"] = dest_map.get(output_format, "embedded")

    persona = (upstream.get("persona") or "").lower()
    if any(x in persona for x in ("exec", "ciso", "vp", "director", "board")):
        d["audience"] = "executive"
    elif any(x in persona for x in ("analyst", "engineer", "ops", "developer")):
        d["audience"] = "operational"
    else:
        d["audience"] = "compliance_team"

    n = len(upstream.get("metrics", [])) + len(upstream.get("kpis", []))
    d["complexity"] = "low" if n <= 4 else "medium" if n <= 8 else "high"

    area_concepts = upstream.get("area_concepts") or upstream.get("focus_areas") or []
    primary_area  = upstream.get("primary_area") or upstream.get("csod_primary_area") or ""
    focus = primary_area or (area_concepts[0] if area_concepts else "")
    if focus:
        d["focus_area"] = focus if isinstance(focus, str) else str(focus)

    if upstream.get("goal_statement"):
        d["goal_statement"] = upstream["goal_statement"]

    return d


# ═══════════════════════════════════════════════════════════════════════
# TOOL CALL HANDLER
# ═══════════════════════════════════════════════════════════════════════

def _handle_tool_calls(state: LayoutAdvisorState, response, merged_decisions: dict) -> dict:
    from .tools import (
        score_templates         as score_fn,
        get_template_detail     as detail_fn,
        generate_layout_spec    as gen_fn,
        apply_adjustment_handle as adjust_fn,
        list_templates          as list_fn,
        match_domain_from_metrics_tool as match_domain_fn,
        search_templates        as search_fn,
    )
    tool_map = {
        "score_templates":                 score_fn,
        "get_template_detail":             detail_fn,
        "generate_layout_spec":            gen_fn,
        "apply_adjustment_handle":         adjust_fn,
        "list_templates":                  list_fn,
        "match_domain_from_metrics_tool":  match_domain_fn,
        "search_templates":                search_fn,
    }

    results       = []
    state_updates: dict = {}

    for tc in response.tool_calls:
        fn = tool_map.get(tc["name"])
        if not fn:
            continue
        result = fn.invoke(tc["args"])
        results.append({"tool": tc["name"], "result": result})

        if tc["name"] == "generate_layout_spec":
            try:
                spec = json.loads(result)
                if "error" not in spec:
                    state_updates["layout_spec"] = spec
                    state_updates["phase"] = Phase.COMPLETE
            except json.JSONDecodeError:
                pass

        elif tc["name"] == "match_domain_from_metrics_tool":
            try:
                recs = json.loads(result)
                if recs.get("recommended_decisions"):
                    state_updates["decisions"] = {**merged_decisions, **recs["recommended_decisions"]}
                    state_updates["taxonomy_match"] = recs
                    state_updates["auto_resolved"] = {
                        **(state.get("auto_resolved", {})),
                        "domain": True, "category": True, "complexity": True, "theme": True,
                    }
            except json.JSONDecodeError:
                pass

        elif tc["name"] == "score_templates":
            try:
                scored = json.loads(result)
                state_updates["candidate_templates"] = scored
                state_updates["recommended_top3"]    = scored[:3]
            except json.JSONDecodeError:
                pass

    summary = response.content or "\n".join(
        f"- **{r['tool']}**: {str(r['result'])[:120]}…" for r in results
    )

    return {
        "messages": [{
            "role": "agent",
            "content": summary,
            "metadata": {"tools_called": [r["tool"] for r in results]},
        }],
        **state_updates,
    }


# ═══════════════════════════════════════════════════════════════════════
# INTAKE NODE — sets routing, pre-scores templates on fast path
# ═══════════════════════════════════════════════════════════════════════

def intake_node_llm(state: LayoutAdvisorState) -> dict:
    """
    Decide fast vs slow path, then:
    - Fast: pre-score templates via DashboardDecisionTreeService.
    - Slow: taxonomy-hint only; LLM will ask questions.
    """
    upstream = state.get("upstream_context", {})
    routing  = "fast" if _has_rich_context(upstream) else "slow"

    goal          = upstream.get("goal_statement") or upstream.get("use_case") or ""
    area_concepts = upstream.get("area_concepts") or upstream.get("focus_areas") or []
    primary_area  = upstream.get("primary_area") or upstream.get("csod_primary_area") or ""
    metrics       = upstream.get("metrics", [])
    kpis          = upstream.get("kpis", [])
    output_format = (upstream.get("output_format") or "echarts").lower()

    state_patch: dict = {"routing": routing}

    if routing == "fast":
        # Build semantic query from goal + area + metric names
        area_clause  = " ".join(filter(None, [
            primary_area,
            " ".join(a if isinstance(a, str) else str(a) for a in area_concepts[:5]),
        ])).strip()
        metric_names = " ".join(
            m.get("name", "") if isinstance(m, dict) else str(m)
            for m in (metrics + kpis)[:10]
        )
        query = " ".join(filter(None, [goal, area_clause, metric_names])) or "compliance dashboard"

        dest_map    = {"echarts": "embedded", "powerbi": "powerbi", "html": "simple"}
        destination = dest_map.get(output_format, "embedded")

        # Category hint from area
        concept_str = (primary_area + " " + area_clause + " " + goal).lower()
        if any(x in concept_str for x in ("training", "learning", "lms", "completion", "cornerstone")):
            category_hint = "learning_development"
        elif any(x in concept_str for x in ("vuln", "security", "siem", "incident", "threat")):
            category_hint = "security_operations"
        elif any(x in concept_str for x in ("compliance", "audit", "soc2", "hipaa", "nist", "risk")):
            category_hint = "compliance_audit"
        elif any(x in concept_str for x in ("hr", "workforce", "headcount", "workday")):
            category_hint = "hr_workforce"
        else:
            category_hint = None

        pre_scored: list = []
        dt_note = ""
        try:
            from app.agents.decision_trees.dashboard.dashboard_decision_tree_service import (
                DashboardDecisionTreeService,
            )
            svc = DashboardDecisionTreeService()
            ctx = svc.search_all(
                query=query,
                templates_limit=5,
                metrics_limit=15,
                category_filter=category_hint,
                destination_filter=destination,
            )
            for tpl in ctx.templates[:3]:
                d = tpl.__dict__ if hasattr(tpl, "__dict__") else dict(tpl)
                pre_scored.append({
                    "template_id": d.get("template_id", ""),
                    "name":        d.get("name", ""),
                    "description": d.get("description", ""),
                    "category":    d.get("category", ""),
                    "complexity":  d.get("complexity", "medium"),
                    "score":       round(float(d.get("score") or 0), 3),
                    "chart_types": d.get("chart_types", []),
                    "panels":      d.get("panels"),
                })
            dt_note = (
                f"Decision-tree pre-scored {len(pre_scored)} templates "
                f"(query={query!r} category={category_hint!r} dest={destination!r}). "
                "Present these immediately — do NOT re-run score_templates."
            ) if pre_scored else "Decision-tree returned no results — call score_templates."
        except Exception as e:
            dt_note = f"Pre-scoring unavailable ({e}) — call score_templates to get candidates."

        if pre_scored:
            state_patch["recommended_top3"]    = pre_scored
            state_patch["candidate_templates"] = pre_scored

        init_msg = (
            f"[FAST PATH] Pipeline context available.\n"
            f"  Goal:        {goal!r}\n"
            f"  Primary area: {primary_area!r}  |  Concepts: {area_concepts}\n"
            f"  Metrics: {len(metrics)} metrics · {len(kpis)} KPIs\n"
            f"  Output format: {output_format!r}\n"
            f"  {dt_note}\n\n"
            "Present the top-3 template recommendations with rationale. "
            "Reference the user's area and metrics. Then ask which one they want."
        )
        state_patch["phase"] = Phase.RECOMMEND

    else:  # slow path
        taxonomy_hint = ""
        if metrics or kpis:
            try:
                from .taxonomy_matcher import get_domain_recommendations
                recs = get_domain_recommendations(
                    metrics=metrics, kpis=kpis,
                    use_case=goal,
                    data_sources=upstream.get("data_sources", []),
                    top_k=1,
                )
                if recs.get("recommended_domain"):
                    top = recs.get("top_domains", [{}])[0]
                    taxonomy_hint = (
                        f"\nTaxonomy hint: domain={recs['recommended_domain']!r} "
                        f"score={top.get('score', 0):.1f} "
                        f"reasons={top.get('reasons', [])[:3]}\n"
                        "Use match_domain_from_metrics_tool for full details."
                    )
            except Exception:
                pass

        init_msg = (
            f"[SLOW PATH] Sparse pipeline context — need to ask the user.\n"
            f"  Goal:    {goal!r}\n"
            f"  Metrics: {len(metrics)} metrics · {len(kpis)} KPIs\n"
            f"{taxonomy_hint}\n"
            "Begin the 7-question decision tree. Skip any question already answered above."
        )
        state_patch["phase"] = Phase.DECISION_INTENT

    state_patch["messages"] = [{
        "role": "system",
        "content": init_msg,
        "metadata": {"phase": "intake", "routing": routing},
    }]

    return state_patch


# ═══════════════════════════════════════════════════════════════════════
# LLM-BASED GRAPH
# ═══════════════════════════════════════════════════════════════════════

def build_llm_layout_advisor_graph():
    """
    Build the LLM-driven layout advisor graph.

    Topology is the same for both paths — routing only changes the system prompt.

      intake → agent_turn (→ await_user ↔ agent_turn) → END
    """
    from langgraph.graph import StateGraph, START, END
    from app.core.checkpointer_provider import get_checkpointer

    workflow = StateGraph(LayoutAdvisorState)

    workflow.add_node("intake",      intake_node_llm)
    workflow.add_node("agent_turn",  llm_agent_node)
    workflow.add_node("await_user",  lambda s: {"needs_user_input": True})

    workflow.add_edge(START, "intake")
    workflow.add_edge("intake", "agent_turn")

    workflow.add_conditional_edges(
        "agent_turn",
        lambda s: "complete" if s.get("phase") == Phase.COMPLETE else "await_user",
        {"complete": END, "await_user": "await_user"},
    )

    workflow.add_edge("await_user", "agent_turn")

    return workflow.compile(
        checkpointer=get_checkpointer(),
        interrupt_before=["await_user"],
    )

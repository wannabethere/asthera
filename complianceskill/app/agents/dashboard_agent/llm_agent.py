"""
CCE Layout Advisor — LLM Agent Node
====================================
Alternative to the rule-based decision nodes: uses an actual LLM
(Claude/GPT) with tool-calling to drive the layout conversation.

This is the "smart" version that can handle freeform conversation,
understand nuanced requirements, and use tools to search/score templates.

Wire this into the graph instead of (or alongside) the rule-based nodes
for a more natural conversational experience.
"""

from __future__ import annotations
import json
from typing import Optional

from langchain_core.messages import (
    HumanMessage, AIMessage, SystemMessage, ToolMessage,
)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_anthropic import ChatAnthropic
from langchain_core.runnables import RunnableConfig

from .state import LayoutAdvisorState, Phase
from .templates import TEMPLATES, CATEGORIES, DECISION_TREE
from .tools import LAYOUT_TOOLS


# ═══════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ═══════════════════════════════════════════════════════════════════════

LAYOUT_ADVISOR_SYSTEM_PROMPT = """\
You are the CCE Layout Advisor Agent. Your job is to help users define 
a dashboard layout through conversation using the 7-question decision tree.

## Your Position in the Pipeline
- **Upstream**: Other agents have already identified metrics, KPIs, tables, 
  and visual types. This context is provided to you.
- **Your Job**: Define the layout — which template, theme, panel structure, 
  KPI strip, filters, and card anatomy.
- **Downstream**: A renderer will consume your layout_spec JSON to generate 
  the actual dashboard. You do NOT generate HTML/React.

## 7-Question Decision Tree (dashboard_decision_tree.md)
Resolve these dimensions before template scoring. Destination gates which templates are available.

1. **Destination Type** — Where will the dashboard render? (embedded/ECharts, powerbi, simple/HTML, slack_digest, api_json)
2. **Category** — Domain: compliance_audit, security_operations, learning_development, hr_workforce, risk_management, executive_reporting, data_operations, cross_domain
3. **Focus Area** — e.g. vulnerability_management, training_completion, incident_response, learner_engagement
4. **Metric Profile** — count_heavy, trend_heavy, rate_percentage, comparison, mixed, scorecard (derived from metrics)
5. **Audience** — security_ops, compliance_team, executive_board, learning_admin, data_engineer
6. **Complexity** — low (summary), medium (standard), high (full detail)
7. **Interaction Mode** — drill_down, read_only, real_time, scheduled_report

**Destination gates**: Templates are filtered by supported_destinations before scoring. output_format=echarts → embedded; powerbi → powerbi; etc.

## Conversation Flow
1. Greet and review upstream context (metrics, KPIs, goal_statement, output_format)
2. **Use `match_domain_from_metrics_tool`** to get recommended domain and decisions
3. Resolve destination_type from output_format (echarts→embedded, powerbi→powerbi)
4. **Use `score_templates`** with decisions + goal_statement + metrics — uses decision tree + vector store when available
5. Recommend top 3 and let user select
6. Generate layout_spec via `generate_layout_spec`

## Tools Available
- `match_domain_from_metrics_tool` — Match metrics/KPIs to dashboard domains (category, focus_area, audience)
- `score_templates` — Score templates (prefers 7-question decision tree + vector store; pass goal_statement, output_format, metrics)
- `get_template_detail` — Get full spec for a template
- `generate_layout_spec` — Build the final layout_spec JSON
- `apply_adjustment_handle` — Apply a pre-computed modification
- `list_templates` — Browse templates by category
- `search_templates` — Semantic search across templates

## Rules
- Resolve destination_type first (from output_format) — it gates template availability
- Use match_domain_from_metrics_tool when metrics/KPIs are available
- Pass goal_statement and metrics to score_templates for best results (enables decision tree flow)
- Keep responses concise; explain WHY a template was recommended
- The layout_spec is the final output — no data binding, no HTML generation
"""


# ═══════════════════════════════════════════════════════════════════════
# AGENT NODE (for LangGraph)
# ═══════════════════════════════════════════════════════════════════════

def create_llm_agent(
    model_name: str = "claude-sonnet-4-5-20250514",
    temperature: float = 0.3,
):
    """
    Create the LLM agent with tools bound.
    
    Returns a runnable that takes messages and returns AI response.
    """
    llm = ChatAnthropic(
        model=model_name,
        temperature=temperature,
        max_tokens=4096,
    )

    # Bind tools
    llm_with_tools = llm.bind_tools(LAYOUT_TOOLS)

    # Build prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", LAYOUT_ADVISOR_SYSTEM_PROMPT),
        ("system", "Upstream context:\n{upstream_context}"),
        ("system", "Current decisions so far:\n{decisions}"),
        ("system", "Current phase: {phase}"),
        MessagesPlaceholder(variable_name="messages"),
    ])

    return prompt | llm_with_tools


def llm_agent_node(state: LayoutAdvisorState, config: RunnableConfig) -> dict:
    """
    LangGraph node that runs the LLM agent.
    
    Converts state messages to LangChain format, runs the LLM,
    and converts back to state format.
    """
    agent = create_llm_agent()

    # Convert state messages to LangChain format
    lc_messages = []
    for msg in state.get("messages", []):
        if msg["role"] == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "agent":
            lc_messages.append(AIMessage(content=msg["content"]))
        elif msg["role"] == "system":
            lc_messages.append(SystemMessage(content=msg["content"]))

    # Add the latest user response if not already in messages
    user_response = state.get("user_response", "")
    if user_response and (not lc_messages or lc_messages[-1].content != user_response):
        lc_messages.append(HumanMessage(content=user_response))

    # Extract metrics/KPIs from upstream context for taxonomy matching
    upstream = state.get("upstream_context", {})
    metrics = upstream.get("metrics", [])
    kpis = upstream.get("kpis", [])
    use_case = upstream.get("use_case", "")
    data_sources = upstream.get("data_sources", [])
    
    # Build enhanced upstream context with taxonomy hints
    enhanced_upstream = {
        **upstream,
        "_taxonomy_available": True,
        "_metrics_count": len(metrics),
        "_kpis_count": len(kpis),
    }
    
    # Run the agent
    response = agent.invoke({
        "messages": lc_messages,
        "upstream_context": json.dumps(enhanced_upstream, indent=2),
        "decisions": json.dumps(state.get("decisions", {}), indent=2),
        "phase": state.get("phase", Phase.INTAKE).value,
    }, config=config)

    # Process tool calls if any
    if response.tool_calls:
        return _handle_tool_calls(state, response)

    # Convert response back to state format
    new_messages = []
    if user_response:
        new_messages.append({
            "role": "user",
            "content": user_response,
            "metadata": {},
        })
    new_messages.append({
        "role": "agent",
        "content": response.content,
        "metadata": {"phase": state.get("phase", Phase.INTAKE).value},
    })

    # Determine if we need more input
    phase = state.get("phase", Phase.INTAKE)
    needs_input = phase not in (Phase.COMPLETE, Phase.SCORING)

    return {
        "messages": new_messages,
        "needs_user_input": needs_input,
    }


def _handle_tool_calls(state: LayoutAdvisorState, response) -> dict:
    """Process tool calls from the LLM and return state updates."""
    from .tools import (
        score_templates as score_fn,
        get_template_detail as detail_fn,
        generate_layout_spec as gen_fn,
        apply_adjustment_handle as adjust_fn,
        list_templates as list_fn,
        match_domain_from_metrics_tool as match_domain_fn,
    )

    tool_map = {
        "score_templates": score_fn,
        "get_template_detail": detail_fn,
        "generate_layout_spec": gen_fn,
        "apply_adjustment_handle": adjust_fn,
        "list_templates": list_fn,
        "match_domain_from_metrics_tool": match_domain_fn,
    }

    results = []
    state_updates = {}

    for tool_call in response.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        if tool_name in tool_map:
            result = tool_map[tool_name].invoke(tool_args)
            results.append({
                "tool": tool_name,
                "args": tool_args,
                "result": result,
            })

            # Extract state updates from tool results
            if tool_name == "generate_layout_spec":
                try:
                    spec = json.loads(result)
                    if "error" not in spec:
                        state_updates["layout_spec"] = spec
                        state_updates["phase"] = Phase.COMPLETE
                except json.JSONDecodeError:
                    pass

            elif tool_name == "match_domain_from_metrics_tool":
                try:
                    recommendations = json.loads(result)
                    # Auto-populate decisions from taxonomy recommendations
                    if recommendations.get("recommended_decisions"):
                        rec_decisions = recommendations["recommended_decisions"]
                        current_decisions = state.get("decisions", {})
                        # Merge recommended decisions
                        state_updates["decisions"] = {
                            **current_decisions,
                            **rec_decisions,
                        }
                        state_updates["taxonomy_match"] = recommendations
                        state_updates["auto_resolved"] = {
                            **(state.get("auto_resolved", {})),
                            "domain": True,
                            "category": True,
                            "complexity": True,
                            "theme": True,
                        }
                except json.JSONDecodeError:
                    pass
            
            elif tool_name == "score_templates":
                try:
                    scored = json.loads(result)
                    state_updates["candidate_templates"] = scored
                    state_updates["recommended_top3"] = scored[:3]
                except json.JSONDecodeError:
                    pass

    # Build agent message summarizing tool results
    tool_summary = "I used the following tools:\n"
    for r in results:
        tool_summary += f"- **{r['tool']}**: {r['result'][:200]}...\n"

    new_messages = [{
        "role": "agent",
        "content": response.content if response.content else tool_summary,
        "metadata": {"tools_called": [r["tool"] for r in results]},
    }]

    return {
        "messages": new_messages,
        **state_updates,
    }


# ═══════════════════════════════════════════════════════════════════════
# LLM-BASED GRAPH (alternative to rule-based)
# ═══════════════════════════════════════════════════════════════════════

def build_llm_layout_advisor_graph():
    """
    Build a simpler graph that uses the LLM for all conversation handling.
    Instead of separate nodes for each decision, the LLM drives everything.
    
    Graph:
      intake → llm_conversation_loop → spec_complete
    """
    from langgraph.graph import StateGraph, START, END
    from langgraph.checkpoint.memory import MemorySaver

    workflow = StateGraph(LayoutAdvisorState)

    # Nodes
    workflow.add_node("intake", intake_node_llm)
    workflow.add_node("agent_turn", llm_agent_node)
    workflow.add_node("await_user", lambda s: {"needs_user_input": True})

    # Edges
    workflow.add_edge(START, "intake")
    workflow.add_edge("intake", "agent_turn")

    workflow.add_conditional_edges(
        "agent_turn",
        lambda s: "complete" if s.get("phase") == Phase.COMPLETE else "await_user",
        {
            "complete": END,
            "await_user": "await_user",
        },
    )

    # await_user → agent_turn (resume after human input)
    workflow.add_edge("await_user", "agent_turn")

    return workflow.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["await_user"],
    )


def intake_node_llm(state: LayoutAdvisorState) -> dict:
    """Simplified intake for LLM-driven graph with taxonomy pre-matching."""
    upstream = state.get("upstream_context", {})
    
    # Proactively match domain if metrics/KPIs are available
    metrics = upstream.get("metrics", [])
    kpis = upstream.get("kpis", [])
    use_case = upstream.get("use_case", "")
    data_sources = upstream.get("data_sources", [])
    
    taxonomy_hint = ""
    if metrics or kpis:
        from .taxonomy_matcher import get_domain_recommendations
        try:
            recommendations = get_domain_recommendations(
                metrics=metrics,
                kpis=kpis,
                use_case=use_case,
                data_sources=data_sources,
                top_k=1,
            )
            if recommendations.get("recommended_domain"):
                domain_info = recommendations["top_domains"][0] if recommendations.get("top_domains") else {}
                taxonomy_hint = (
                    f"\n\nTaxonomy Analysis:\n"
                    f"Recommended domain: {recommendations['recommended_domain']} "
                    f"({domain_info.get('display_name', '')})\n"
                    f"Match score: {domain_info.get('score', 0):.1f}\n"
                    f"Match reasons: {', '.join(domain_info.get('reasons', [])[:3])}\n"
                    f"Suggested decisions: {json.dumps(recommendations.get('recommended_decisions', {}), indent=2)}\n"
                    f"\nYou should use match_domain_from_metrics_tool to confirm and get full details."
                )
        except Exception as e:
            # Taxonomy matching failed, continue without it
            pass
    
    return {
        "messages": [{
            "role": "system",
            "content": (
                f"Upstream context received:\n"
                f"{json.dumps(upstream, indent=2, default=str)}"
                f"{taxonomy_hint}\n\n"
                "Begin the layout advisor conversation. "
                "If metrics/KPIs are available, use match_domain_from_metrics_tool first."
            ),
            "metadata": {"phase": "intake"},
        }],
        "phase": Phase.DECISION_INTENT,
    }

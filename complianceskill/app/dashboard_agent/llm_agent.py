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
a dashboard layout through conversation.

## Your Position in the Pipeline
- **Upstream**: Other agents have already identified metrics, KPIs, tables, 
  and visual types. This context is provided to you.
- **Your Job**: Define the layout — which template, theme, panel structure, 
  KPI strip, filters, and card anatomy.
- **Downstream**: A renderer will consume your layout_spec JSON to generate 
  the actual dashboard. You do NOT generate HTML/React.

## Available Templates
You have access to 17 dashboard templates across these categories:
- Security Operations (command-center, triage-focused, vulnerability-posture, incident-timeline)
- Executive/Board (posture-overview, executive-risk-summary)
- HR & Learning (lms-training, hr-workforce, onboarding-offboarding)
- Cross-Domain (hybrid-compliance)
- Data Operations (migration-tracker, pipeline-health)
- GRC/Risk (risk-register, vendor-risk, regulatory-change)
- Identity & Access (access-certification)
- Compliance (audit-evidence)

## Conversation Flow
1. Greet the user and review any upstream context
2. Ask about: intent, systems involved, audience, AI chat needs, KPI count
3. Auto-resolve decisions when upstream context provides clear answers
4. Score templates and recommend top 3
5. Let user select and customize
6. Generate the final layout_spec JSON

## Tools Available
- `score_templates` — Score all templates against accumulated decisions
- `get_template_detail` — Get full spec for a specific template
- `generate_layout_spec` — Build the final output JSON
- `apply_customization` — Modify an existing spec
- `list_templates` — Browse available templates
- `search_templates` — Semantic search across templates

## Rules
- Keep responses concise and actionable
- Present options clearly with numbers
- When you have enough info, proactively score and recommend
- Always explain WHY a template was recommended (match reasons)
- The layout_spec is the final output — make sure it's complete
- You define layout only — no data binding, no HTML generation
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

    # Run the agent
    response = agent.invoke({
        "messages": lc_messages,
        "upstream_context": json.dumps(state.get("upstream_context", {}), indent=2),
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
    from tools import (
        score_templates as score_fn,
        get_template_detail as detail_fn,
        generate_layout_spec as gen_fn,
        apply_customization as custom_fn,
        list_templates as list_fn,
    )

    tool_map = {
        "score_templates": score_fn,
        "get_template_detail": detail_fn,
        "generate_layout_spec": gen_fn,
        "apply_customization": custom_fn,
        "list_templates": list_fn,
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
    """Simplified intake for LLM-driven graph."""
    upstream = state.get("upstream_context", {})
    return {
        "messages": [{
            "role": "system",
            "content": (
                f"Upstream context received:\n"
                f"{json.dumps(upstream, indent=2, default=str)}\n\n"
                "Begin the layout advisor conversation."
            ),
            "metadata": {"phase": "intake"},
        }],
        "phase": Phase.DECISION_INTENT,
    }

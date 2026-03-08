"""
CCE Layout Advisor — LangGraph Workflow
========================================
The main graph definition that orchestrates the layout advisor conversation.

Pipeline position:
  Upstream Agents (metrics, KPIs, tables, visuals)
    → THIS GRAPH (layout definition via conversation)
      → Downstream Renderer (actual HTML/React generation)

Graph topology:
  ┌──────────┐
  │  INTAKE   │  ← receives upstream_context
  └────┬──────┘
       │ (auto-resolved all?) ──→ SCORING
       ▼
  ┌──────────────────┐
  │  DECISION LOOP   │  ← human-in-the-loop at each step
  │  intent → systems│
  │  → audience →    │
  │  chat → kpis     │
  └────┬─────────────┘
       ▼
  ┌──────────┐
  │ SCORING  │  ← hybrid rule+vector scoring
  └────┬─────┘
       ▼
  ┌──────────────┐
  │RECOMMENDATION│  ← present top 3
  └────┬─────────┘
       ▼
  ┌──────────┐
  │SELECTION │  ← user picks template (human-in-the-loop)
  └────┬─────┘
       ▼
  ┌──────────────┐
  │CUSTOMIZATION │  ← optional tweaks loop (human-in-the-loop)
  └────┬─────────┘
       ▼
  ┌──────────────┐
  │SPEC GENERATION│  ← produces layout_spec JSON
  └────┬─────────┘
       ▼
  ┌──────────┐
  │ COMPLETE │  ← output ready for downstream
  └──────────┘
"""

from __future__ import annotations
from typing import Literal

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from .state import LayoutAdvisorState, Phase
from .nodes import (
    intake_node,
    decision_node,
    bind_node,
    scoring_node,
    recommendation_node,
    selection_node,
    data_tables_node,
    customization_node,
    retrieve_context_node,
    spec_generation_node,
)


# ═══════════════════════════════════════════════════════════════════════
# ROUTING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def route_after_intake(state: LayoutAdvisorState) -> str:
    """After intake, either go to bind (goal-driven), first decision, or scoring."""
    phase = state.get("phase")
    if phase == Phase.BIND:
        return "bind"
    if phase == Phase.SCORING:
        return "scoring"
    return "decision"


def route_after_decision(state: LayoutAdvisorState) -> str:
    """After a decision, either continue decisions, move to bind, or scoring."""
    phase = state.get("phase")
    if phase == Phase.BIND:
        return "bind"
    if phase == Phase.SCORING:
        return "scoring"
    return "await_decision_input"


def route_after_selection(state: LayoutAdvisorState) -> str:
    """After selection, go to data tables (if enabled) or customization."""
    # Guard: if selection failed, stay at selection interrupt
    if not state.get("selected_template_id"):
        return "await_selection_input"

    phase = state.get("phase")
    if phase == Phase.DATA_TABLES:
        return "await_data_tables_input"
    return "await_customization_input"


def route_after_data_tables(state: LayoutAdvisorState) -> str:
    """After data tables, either loop for more or go to customization."""
    phase = state.get("phase")
    if phase == Phase.CUSTOMIZATION:
        return "await_customization_input"
    return "await_data_tables_input"


def route_after_customization(state: LayoutAdvisorState) -> str:
    """After customization, either loop for more tweaks or run retrieval + generate spec."""
    phase = state.get("phase")
    if phase == Phase.SPEC_GENERATION:
        return "retrieve_context"   # retrieval runs first, then spec_generation
    return "await_customization_input"


# ═══════════════════════════════════════════════════════════════════════
# HUMAN-IN-THE-LOOP INTERRUPT NODES
# ═══════════════════════════════════════════════════════════════════════
# These are "pass-through" nodes that the graph pauses at.
# When the user responds, the graph resumes from here.

def await_decision_input(state: LayoutAdvisorState) -> dict:
    """Pause point — waiting for user to answer a decision question."""
    return {"needs_user_input": True}


def await_selection_input(state: LayoutAdvisorState) -> dict:
    """Pause point — waiting for user to select a template."""
    return {"needs_user_input": True}


def await_data_tables_input(state: LayoutAdvisorState) -> dict:
    """Pause point — waiting for user to add data tables or skip."""
    return {"needs_user_input": True}


def await_customization_input(state: LayoutAdvisorState) -> dict:
    """Pause point — waiting for user to customize or finalize."""
    return {"needs_user_input": True}


# ═══════════════════════════════════════════════════════════════════════
# BUILD THE GRAPH
# ═══════════════════════════════════════════════════════════════════════

def build_layout_advisor_graph() -> StateGraph:
    """
    Construct the LangGraph StateGraph for the Layout Advisor.
    
    Returns a compiled graph with MemorySaver checkpointing.
    """
    workflow = StateGraph(LayoutAdvisorState)

    # ── Add nodes ─────────────────────────────────────────────────────
    workflow.add_node("intake", intake_node)
    workflow.add_node("await_decision_input", await_decision_input)
    workflow.add_node("decision", decision_node)
    workflow.add_node("bind", bind_node)
    workflow.add_node("scoring", scoring_node)
    workflow.add_node("recommendation", recommendation_node)
    workflow.add_node("await_selection_input", await_selection_input)
    workflow.add_node("selection", selection_node)
    workflow.add_node("await_data_tables_input", await_data_tables_input)
    workflow.add_node("data_tables", data_tables_node)
    workflow.add_node("await_customization_input", await_customization_input)
    workflow.add_node("customization", customization_node)
    # retrieve_context runs BEFORE spec_generation (metric catalog + past specs)
    workflow.add_node("retrieve_context", retrieve_context_node)
    workflow.add_node("spec_generation", spec_generation_node)

    # ── Entry point ───────────────────────────────────────────────────
    workflow.add_edge(START, "intake")

    # ── Intake → decision, bind, or scoring ──────────────────────────
    workflow.add_conditional_edges(
        "intake",
        route_after_intake,
        {
            "decision": "await_decision_input",
            "bind": "bind",
            "scoring": "scoring",
        },
    )

    # ── Bind → scoring (goal-driven path) ─────────────────────────────
    workflow.add_edge("bind", "scoring")

    # ── Decision loop ─────────────────────────────────────────────────
    # await_decision_input is an interrupt point
    workflow.add_edge("await_decision_input", "decision")

    workflow.add_conditional_edges(
        "decision",
        route_after_decision,
        {
            "bind": "bind",
            "scoring": "scoring",
            "await_decision_input": "await_decision_input",
        },
    )

    # ── Scoring → Recommendation ──────────────────────────────────────
    workflow.add_edge("scoring", "recommendation")

    # ── Recommendation → Selection ────────────────────────────────────
    workflow.add_edge("recommendation", "await_selection_input")
    workflow.add_edge("await_selection_input", "selection")

    # ── Selection → Data Tables (if enabled) or Customization ─────────
    workflow.add_conditional_edges(
        "selection",
        route_after_selection,
        {
            "await_selection_input": "await_selection_input",
            "await_data_tables_input": "await_data_tables_input",
            "await_customization_input": "await_customization_input",
        },
    )

    # ── Data Tables loop (human-in-the-loop) ───────────────────────────
    workflow.add_edge("await_data_tables_input", "data_tables")
    workflow.add_conditional_edges(
        "data_tables",
        route_after_data_tables,
        {
            "await_customization_input": "await_customization_input",
            "await_data_tables_input": "await_data_tables_input",
        },
    )

    # ── Customization loop ────────────────────────────────────────────
    workflow.add_edge("await_customization_input", "customization")

    workflow.add_conditional_edges(
        "customization",
        route_after_customization,
        {
            "retrieve_context": "retrieve_context",
            "await_customization_input": "await_customization_input",
        },
    )

    # ── Retrieval → Spec generation → END ────────────────────────────
    workflow.add_edge("retrieve_context", "spec_generation")
    workflow.add_edge("spec_generation", END)

    return workflow


def compile_layout_advisor(
    checkpointer=None,
    interrupt_before: list[str] | None = None,
):
    """
    Compile the graph with checkpointing and interrupt configuration.
    
    Args:
        checkpointer: LangGraph checkpointer (default: MemorySaver)
        interrupt_before: Nodes to interrupt before (for human-in-the-loop)
    
    Returns:
        Compiled graph ready for .invoke() / .stream()
    """
    workflow = build_layout_advisor_graph()

    if checkpointer is None:
        checkpointer = MemorySaver()

    if interrupt_before is None:
        interrupt_before = [
            "await_decision_input",
            "await_selection_input",
            "await_data_tables_input",
            "await_customization_input",
        ]

    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_before,
    )


# ═══════════════════════════════════════════════════════════════════════
# CONVENIENCE: Get the graph for visualization
# ═══════════════════════════════════════════════════════════════════════

def get_graph_mermaid() -> str:
    """Return Mermaid diagram string for the workflow."""
    workflow = build_layout_advisor_graph()
    return workflow.compile().get_graph().draw_mermaid()

"""
CCE Layout Advisor Agent — State Schema
========================================
Position in pipeline:
  Upstream Agents (metrics, KPIs, tables, visuals)
    → THIS AGENT (layout definition via conversation)
      → Downstream Renderer (actual HTML/React generation)

State flows through LangGraph nodes accumulating decisions
until a final layout_spec JSON is produced.
"""

from __future__ import annotations
from typing import TypedDict, Literal, Optional, Annotated
from dataclasses import dataclass, field
from enum import Enum
import operator


# ── Upstream Context (from prior agents in pipeline) ──────────────────

class UpstreamContext(TypedDict, total=False):
    """What the upstream metric/KPI/visual agents have already resolved."""
    use_case: str                     # e.g. "SOC2 monitoring", "training compliance"
    data_sources: list[str]           # e.g. ["siem", "cornerstone", "workday"]
    persona: str                      # e.g. "SOC Analyst", "CISO"
    metrics: list[dict]               # [{name, type, source_table}, ...]
    kpis: list[dict]                  # [{label, value_expr, threshold}, ...]
    tables: list[dict]                # [{name, schema, row_count}, ...]
    visuals: list[dict]               # [{type: "line_chart", metric, ...}, ...]
    has_chat_requirement: bool
    kpi_count: int
    framework: str                    # "SOC2", "HIPAA", "NIST AI RMF"


# ── Decision Accumulator ─────────────────────────────────────────────

class Decisions(TypedDict, total=False):
    """Accumulated decisions from the conversation."""
    category: list[str]       # ["compliance", "grc"]
    domain: str               # "security" | "cornerstone" | "workday" | "hybrid" | "data_ops"
    theme: str                # "dark" | "light"
    complexity: str           # "low" | "medium" | "high"
    has_chat: bool
    strip_cells: int          # 0, 4, 6, 8


# ── Conversation Message ─────────────────────────────────────────────

class Message(TypedDict):
    role: Literal["agent", "user", "system"]
    content: str
    metadata: dict  # optional: step_id, auto_resolved, decision_applied


# ── Agent Phase Enum ─────────────────────────────────────────────────

class Phase(str, Enum):
    INTAKE = "intake"                      # receive upstream context
    DECISION_INTENT = "decision_intent"    # ask purpose
    DECISION_SYSTEMS = "decision_systems"  # ask systems
    DECISION_AUDIENCE = "decision_audience" # ask audience
    DECISION_CHAT = "decision_chat"        # ask AI chat
    DECISION_KPIS = "decision_kpis"        # ask KPI count
    SCORING = "scoring"                    # score templates
    RECOMMENDATION = "recommendation"      # present top 3
    SELECTION = "selection"                # user picks
    CUSTOMIZATION = "customization"        # optional tweaks
    SPEC_GENERATION = "spec_generation"    # build final spec
    COMPLETE = "complete"                  # done


# ── Graph State ──────────────────────────────────────────────────────

class LayoutAdvisorState(TypedDict):
    """Full state for the Layout Advisor LangGraph."""
    
    # Pipeline context
    upstream_context: UpstreamContext
    
    # Conversation
    messages: Annotated[list[Message], operator.add]
    
    # Agent progress
    phase: Phase
    decisions: Decisions
    auto_resolved: dict          # which decisions were auto-filled from upstream
    
    # Template scoring
    candidate_templates: list[dict]   # [{template_id, score, reasons}, ...]
    recommended_top3: list[dict]      # top 3 from scoring
    
    # Selection & customization
    selected_template_id: str
    customization_requests: list[str]
    
    # Output
    layout_spec: dict            # final JSON spec for downstream renderer
    
    # Control
    needs_user_input: bool       # pause graph for human-in-the-loop
    user_response: str           # latest user message
    error: str

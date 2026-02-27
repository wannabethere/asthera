"""
CCE Layout Advisor Agent
========================
LangGraph-powered conversational agent for defining dashboard layouts.

Pipeline position:
  Upstream Agents → THIS AGENT → Downstream Renderer

Usage:
    from cce_layout_agent import LayoutAdvisorSession
    
    session = LayoutAdvisorSession()
    response = session.start(upstream_context={...})
    response = session.respond("Monitor compliance posture")
    ...
    spec = response.layout_spec
"""

from .state import LayoutAdvisorState, Phase, UpstreamContext, Decisions, Message
from .templates import TEMPLATES, CATEGORIES, DECISION_TREE
from .vector_store import score_templates_hybrid
from .tools import LAYOUT_TOOLS
from .graph import build_layout_advisor_graph, compile_layout_advisor
from .runner import LayoutAdvisorSession, SessionManager, AdvisorResponse

__all__ = [
    # State
    "LayoutAdvisorState",
    "Phase",
    "UpstreamContext",
    "Decisions",
    "Message",
    # Templates
    "TEMPLATES",
    "CATEGORIES",
    "DECISION_TREE",
    # Scoring utilities
    "score_templates_hybrid",
    # Tools
    "LAYOUT_TOOLS",
    # Graph
    "build_layout_advisor_graph",
    "compile_layout_advisor",
    # Runner
    "LayoutAdvisorSession",
    "SessionManager",
    "AdvisorResponse",
]

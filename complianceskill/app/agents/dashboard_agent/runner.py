"""
CCE Layout Advisor — Session Runner
=====================================
High-level API for running the layout advisor conversation.
Manages the graph lifecycle, human-in-the-loop turns, and
provides a clean interface for both CLI and web integrations.

Usage:
    session = LayoutAdvisorSession()
    
    # Start with upstream context
    response = session.start(upstream_context={
        "use_case": "SOC2 monitoring",
        "data_sources": ["siem", "cornerstone"],
        "kpis": [{"label": "Posture Score"}, {"label": "Controls Passing"}],
    })
    print(response.agent_message)
    print(response.options)  # decision options if applicable
    
    # User responds
    response = session.respond("Monitor compliance posture")
    
    # ... continue until complete
    if response.is_complete:
        print(response.layout_spec)
"""

from __future__ import annotations
import uuid
import json
from dataclasses import dataclass, field
from typing import Optional

from .state import LayoutAdvisorState, Phase, UpstreamContext
from .graph import compile_layout_advisor
from .templates import TEMPLATES, DECISION_TREE
from .config import LayoutAdvisorConfig


# ═══════════════════════════════════════════════════════════════════════
# RESPONSE DTO
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class AdvisorResponse:
    """Response from a conversation turn."""
    agent_message: str
    phase: str
    is_complete: bool = False
    needs_input: bool = True
    options: list[str] = field(default_factory=list)     # clickable options
    recommended: list[dict] = field(default_factory=list) # top 3 templates
    selected_template: Optional[str] = None
    layout_spec: Optional[dict] = None
    decisions_so_far: dict = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "agent_message": self.agent_message,
            "phase": self.phase,
            "is_complete": self.is_complete,
            "needs_input": self.needs_input,
            "options": self.options,
            "recommended": self.recommended,
            "selected_template": self.selected_template,
            "layout_spec": self.layout_spec,
            "decisions_so_far": self.decisions_so_far,
            "error": self.error,
        }


# ═══════════════════════════════════════════════════════════════════════
# SESSION MANAGER
# ═══════════════════════════════════════════════════════════════════════

# Phase → decision tree index mapping
PHASE_TO_DECISION = {
    Phase.DECISION_INTENT: 0,
    Phase.DECISION_SYSTEMS: 1,
    Phase.DECISION_AUDIENCE: 2,
    Phase.DECISION_CHAT: 3,
    Phase.DECISION_KPIS: 4,
}


class LayoutAdvisorSession:
    """
    Manages a single layout advisor conversation session.
    Wraps the LangGraph with a simple request/response interface.
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        agent_config: Optional[LayoutAdvisorConfig | dict] = None,
    ):
        self.session_id = session_id or str(uuid.uuid4())
        self.graph = compile_layout_advisor()
        self.config = {"configurable": {"thread_id": self.session_id}}
        self._started = False
        self.agent_config = (
            LayoutAdvisorConfig.from_dict(agent_config)
            if isinstance(agent_config, dict)
            else (agent_config or LayoutAdvisorConfig())
        )

    def start(
        self,
        upstream_context: Optional[dict] = None,
    ) -> AdvisorResponse:
        """
        Start a new layout advisor conversation.
        
        Args:
            upstream_context: Output from upstream agents (metrics, KPIs, etc.)
        
        Returns:
            AdvisorResponse with greeting and first question.
        """
        initial_state = {
            "upstream_context": upstream_context or {},
            "agent_config": self.agent_config.to_dict(),
            "messages": [],
            "phase": Phase.INTAKE,
            "decisions": {},
            "auto_resolved": {},
            "candidate_templates": [],
            "recommended_top3": [],
            "selected_template_id": "",
            "customization_requests": [],
            "user_added_tables": [],
            "layout_spec": {},
            "needs_user_input": False,
            "user_response": "",
            "error": "",
        }

        # Run the graph until it hits an interrupt
        result = self.graph.invoke(initial_state, self.config)
        self._started = True

        return self._build_response(result)

    def respond(self, user_message: str) -> AdvisorResponse:
        """
        Send a user message and get the next agent response.
        
        Args:
            user_message: The user's text input
        
        Returns:
            AdvisorResponse with agent reply and next options.
        """
        if not self._started:
            return AdvisorResponse(
                agent_message="Session not started. Call .start() first.",
                phase="error",
                error="Session not started",
            )

        # Step 1: Inject user input into the existing checkpoint state.
        # update_state merges only the fields provided into the checkpoint.
        self.graph.update_state(self.config, {"user_response": user_message})

        # Step 2: Resume from the interrupt point — None means "continue".
        # Passing a dict to invoke() RESTARTS the graph with that as initial state.
        result = self.graph.invoke(None, self.config)

        return self._build_response(result)

    def auto_run(
        self,
        upstream_context: Optional[dict] = None,
        max_iterations: int = 50,
    ) -> AdvisorResponse:
        """
        Run the full flow automatically, picking the first valid option at each step.
        Use for demos and validation — no human input required.
        """
        response = self.start(upstream_context)
        for _ in range(max_iterations):
            if response.is_complete:
                return response
            if not response.needs_input:
                return response
            # Pick first valid option
            if response.phase == "selection" and response.recommended:
                user_msg = "1"
            elif response.phase == "data_tables":
                user_msg = "skip"
            elif response.options:
                user_msg = response.options[0]
            else:
                user_msg = "looks good"
            response = self.respond(user_msg)
        return response

    def get_state(self) -> dict:
        """Get the current graph state."""
        snapshot = self.graph.get_state(self.config)
        return snapshot.values if snapshot else {}

    def get_spec(self) -> Optional[dict]:
        """Get the final layout spec if complete."""
        state = self.get_state()
        spec = state.get("layout_spec")
        return spec if spec else None

    def reset(self) -> AdvisorResponse:
        """Reset the session and start over."""
        self.session_id = str(uuid.uuid4())
        self.config = {"configurable": {"thread_id": self.session_id}}
        self.graph = compile_layout_advisor()
        self._started = False
        return AdvisorResponse(
            agent_message="Session reset. Call .start() to begin a new conversation.",
            phase="reset",
        )

    def _build_response(self, state: dict) -> AdvisorResponse:
        """Convert graph state to AdvisorResponse."""
        messages = state.get("messages", [])
        phase = state.get("phase", Phase.INTAKE)
        decisions = state.get("decisions", {})

        # Get the latest agent message
        agent_msg = ""
        for msg in reversed(messages):
            if msg.get("role") == "agent":
                agent_msg = msg.get("content", "")
                break

        # Build options based on current phase
        options = self._get_options_for_phase(phase, state)

        # Check for completion
        is_complete = phase == Phase.COMPLETE
        layout_spec = state.get("layout_spec") if is_complete else None

        # Get recommended templates
        recommended = state.get("recommended_top3", [])

        return AdvisorResponse(
            agent_message=agent_msg,
            phase=phase.value if isinstance(phase, Phase) else str(phase),
            is_complete=is_complete,
            needs_input=state.get("needs_user_input", True),
            options=options,
            recommended=recommended,
            selected_template=state.get("selected_template_id"),
            layout_spec=layout_spec,
            decisions_so_far=decisions,
        )

    def _get_options_for_phase(self, phase: Phase, state: dict) -> list[str]:
        """Get clickable options for the current phase."""
        auto_resolved = state.get("auto_resolved", {})

        if phase in PHASE_TO_DECISION:
            decision_idx = PHASE_TO_DECISION[phase]
            decision = DECISION_TREE[decision_idx]
            # Skip if auto-resolved
            if decision["id"] in auto_resolved:
                return []
            return [opt["label"] for opt in decision["options"]]

        if phase == Phase.SELECTION:
            top3 = state.get("recommended_top3", [])
            return [
                f"{i+1}. {t.get('icon', '')} {t['name']} (score: {t['score']})"
                for i, t in enumerate(top3)
            ]

        if phase == Phase.DATA_TABLES:
            return [
                "Add vulnerability data",
                "Include agent coverage",
                "Show backlog trend",
                "Skip — continue to customization",
            ]

        if phase == Phase.CUSTOMIZATION:
            return ["Looks good — finalize", "Change theme", "Adjust KPIs", "Modify panels"]

        return []


# ═══════════════════════════════════════════════════════════════════════
# MULTI-SESSION MANAGER (for API server)
# ═══════════════════════════════════════════════════════════════════════

class SessionManager:
    """
    Manages multiple concurrent layout advisor sessions.
    Use this in a FastAPI/Flask server to handle many users.
    """

    def __init__(self):
        self._sessions: dict[str, LayoutAdvisorSession] = {}

    def create_session(
        self,
        session_id: Optional[str] = None,
        agent_config: Optional[LayoutAdvisorConfig | dict] = None,
    ) -> str:
        """Create a new session and return its ID."""
        session = LayoutAdvisorSession(session_id=session_id, agent_config=agent_config)
        self._sessions[session.session_id] = session
        return session.session_id

    def get_session(self, session_id: str) -> Optional[LayoutAdvisorSession]:
        """Get an existing session."""
        return self._sessions.get(session_id)

    def start_session(
        self, session_id: str, upstream_context: Optional[dict] = None,
    ) -> AdvisorResponse:
        """Start a session with upstream context."""
        session = self._sessions.get(session_id)
        if not session:
            return AdvisorResponse(
                agent_message="Session not found.",
                phase="error",
                error=f"Session {session_id} not found",
            )
        return session.start(upstream_context)

    def respond_session(
        self, session_id: str, user_message: str,
    ) -> AdvisorResponse:
        """Send a message to an existing session."""
        session = self._sessions.get(session_id)
        if not session:
            return AdvisorResponse(
                agent_message="Session not found.",
                phase="error",
                error=f"Session {session_id} not found",
            )
        return session.respond(user_message)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def list_sessions(self) -> list[str]:
        """List all active session IDs."""
        return list(self._sessions.keys())

"""
Dashboard Agent (Layout Advisor) Service

Service layer for the CCE Layout Advisor — dashboard layout selection via
conversational decision tree. Wraps the dashboard_agent's LayoutAdvisorSession.
"""
import asyncio
import logging
from typing import Dict, Any, Optional, List, AsyncGenerator

from app.agents.dashboard_agent.runner import (
    SessionManager as DashboardSessionManager,
    LayoutAdvisorSession,
    AdvisorResponse,
    Phase,
)
from app.services.workflow_stream_utils import maybe_llm_stream_event

logger = logging.getLogger(__name__)


class DashboardAgentService:
    """
    Service for managing Dashboard Layout Advisor (dashboard_agent) sessions.

    Provides methods for:
    - Creating layout advisor sessions
    - Starting conversations with upstream context
    - Sending user responses (turn-based)
    - Listing and managing sessions
    """

    def __init__(self):
        self._session_manager = DashboardSessionManager()
        logger.info("DashboardAgentService initialized")

    def create_session(
        self,
        session_id: Optional[str] = None,
        agent_config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create a new layout advisor session.

        Args:
            session_id: Optional session ID (auto-generated if not provided)
            agent_config: Optional agent configuration dict

        Returns:
            Session ID
        """
        return self._session_manager.create_session(
            session_id=session_id,
            agent_config=agent_config,
        )

    def start_session(
        self,
        session_id: str,
        upstream_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Start a layout advisor conversation with upstream context.

        Args:
            session_id: Session identifier
            upstream_context: Output from upstream agents (metrics, KPIs, use_case, etc.)

        Returns:
            AdvisorResponse as dict (agent_message, phase, is_complete, options, etc.)
        """
        response = self._session_manager.start_session(
            session_id=session_id,
            upstream_context=upstream_context,
        )
        return response.to_dict()

    def respond(
        self,
        session_id: str,
        user_message: str,
    ) -> Dict[str, Any]:
        """
        Send a user message to an existing layout advisor session.

        Args:
            session_id: Session identifier
            user_message: User's text input

        Returns:
            AdvisorResponse as dict
        """
        response = self._session_manager.respond_session(
            session_id=session_id,
            user_message=user_message,
        )
        return response.to_dict()

    def get_session(self, session_id: str) -> Optional[LayoutAdvisorSession]:
        """Get an existing layout advisor session."""
        return self._session_manager.get_session(session_id)

    def get_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current graph state for a session.

        Returns:
            State dict or None if session not found
        """
        session = self._session_manager.get_session(session_id)
        if not session:
            return None
        return session.get_state()

    def get_layout_spec(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the final layout spec if the session is complete.

        Returns:
            Layout spec dict or None
        """
        session = self._session_manager.get_session(session_id)
        if not session:
            return None
        return session.get_spec()

    def delete_session(self, session_id: str) -> bool:
        """Delete a layout advisor session."""
        return self._session_manager.delete_session(session_id)

    def list_sessions(self) -> List[str]:
        """List all active layout advisor session IDs."""
        return self._session_manager.list_sessions()

    async def start_session_stream(
        self,
        session_id: str,
        upstream_context: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Start a layout advisor conversation with streaming SSE events.

        Yields: node_start, node_complete, llm_chunk, llm_start, llm_end,
                state_update, response (final AdvisorResponse when done).
        """
        session = self._session_manager.get_session(session_id)
        if not session:
            yield {"event": "error", "data": {"error": f"Session {session_id} not found"}}
            return

        initial_state = {
            "upstream_context": upstream_context or {},
            "agent_config": session.agent_config.to_dict(),
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

        try:
            async for event in session.graph.astream_events(
                initial_state, session.config, version="v2"
            ):
                ev = self._event_to_sse(event, session_id)
                if ev:
                    yield ev

            session._started = True
            state = session.get_state()
            response = session._build_response(state)
            yield {"event": "response", "data": response.to_dict()}
        except Exception as e:
            logger.error(f"Dashboard agent start_stream error: {e}", exc_info=True)
            yield {"event": "error", "data": {"error": str(e)}}

    async def respond_stream(
        self,
        session_id: str,
        user_message: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Send a user message and stream SSE events until next response.

        Yields: node_start, node_complete, llm_chunk, state_update, response.
        """
        session = self._session_manager.get_session(session_id)
        if not session:
            yield {"event": "error", "data": {"error": f"Session {session_id} not found"}}
            return

        session.graph.update_state(session.config, {"user_response": user_message})

        try:
            async for event in session.graph.astream_events(None, session.config, version="v2"):
                ev = self._event_to_sse(event, session_id)
                if ev:
                    yield ev

            state = session.get_state()
            response = session._build_response(state)
            yield {"event": "response", "data": response.to_dict()}
        except Exception as e:
            logger.error(f"Dashboard agent respond_stream error: {e}", exc_info=True)
            yield {"event": "error", "data": {"error": str(e)}}

    def _event_to_sse(self, event: Dict[str, Any], session_id: str) -> Optional[Dict[str, Any]]:
        """Convert LangGraph event to SSE event dict."""
        event_kind = event.get("event")
        event_name = event.get("name", "")
        run_id = event.get("run_id", "")

        llm_ev = maybe_llm_stream_event(event, session_id)
        if llm_ev:
            return llm_ev

        if event_kind == "on_chain_start":
            return {
                "event": "node_start",
                "data": {
                    "session_id": session_id,
                    "node": event_name,
                    "run_id": run_id,
                },
            }
        if event_kind == "on_chain_end":
            return {
                "event": "node_complete",
                "data": {
                    "session_id": session_id,
                    "node": event_name,
                    "run_id": run_id,
                },
            }
        return None


_dashboard_agent_service = None


def get_dashboard_agent_service() -> DashboardAgentService:
    """
    Get the global Dashboard Agent service instance.
    """
    global _dashboard_agent_service
    if _dashboard_agent_service is None:
        _dashboard_agent_service = DashboardAgentService()
    return _dashboard_agent_service

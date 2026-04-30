"""
Agent Invocation Service

Orchestrates agent invocation with context composition, token minting,
and event streaming. This is the main service layer between the API
and the agent adapters.

Routing is two-tier:
- **Gateway (this module + AgentRegistry):** `agent_id` selects which LangGraph app runs.
  CSOD apps are compiled in `agent_registration.register_all_agents` from:
  - `csod-planner` → `planner_workflow.create_conversation_planner_app(LMS_CONVERSATION_CONFIG)`
  - `csod-workflow` → `workflows.csod_main_graph.get_csod_app`
  - `csod-metric-advisor` → same LangGraph app as `csod-workflow` (deprecated id)
  Invocation only passes `agent_id` + payload into the registry; it does not import those graphs.
- **Inside CSOD graphs:** `app.agents.csod.executor_registry` (merged with
  `executor_registry_planned.planned_executors_v5`) supplies `registry_summary_for_planner()`
  to `csod_planner_node` for intent → execution_plan → executor_id. That registry is not
  consulted here; see `agent_describe_context.build_agent_describe_context` for the same
  catalog exposed to describe/proxy clients.
"""

import logging
from typing import Dict, Any, Optional, AsyncIterator
from uuid import uuid4


def build_planner_chain_invoke_payload(
    planner_output: Dict[str, Any],
    *,
    thread_id: str,
    original_run_id: Optional[str] = None,
    original_step_id: str = "step_1",
) -> Dict[str, Any]:
    """
    Payload for invoking the planner's next_agent — same shape as production chaining.

    Use from tests/scripts so manual POST /v1/agents/invoke matches _chain_to_next_agent.
    """
    rid = original_run_id or str(uuid4())
    next_payload: Dict[str, Any] = {
        "input": planner_output.get("user_query", ""),
        "thread_id": thread_id,
        "run_id": f"{rid}_chain",
        "step_id": f"{original_step_id}_chain",
        "step_index": 1,
        "planner_output": planner_output,
        "active_project_id": planner_output.get("active_project_id"),
        "selected_data_sources": planner_output.get("selected_data_sources", []),
        "compliance_profile": planner_output.get("compliance_profile", {}),
        "skip_conversation_phase0": True,
    }
    if planner_output.get("csod_intent"):
        next_payload["csod_intent"] = planner_output["csod_intent"]
    return next_payload

from app.adapters.base import AgentEvent, EventType, ComposedContext
from app.adapters.registry import AgentRegistry, AgentMeta
from app.services.context_composer import ContextComposer
from app.services.context_token import ContextTokenService

logger = logging.getLogger(__name__)


class AgentInvocationService:
    """
    Service for invoking agents with proper context composition and streaming.
    """
    
    def __init__(
        self,
        registry: AgentRegistry,
        context_composer: ContextComposer,
        context_token_service: ContextTokenService,
    ):
        """
        Initialize agent invocation service.
        
        Args:
            registry: Agent registry
            context_composer: Context composition service
            context_token_service: Context token service
        """
        self.registry = registry
        self.context_composer = context_composer
        self.context_token_service = context_token_service
    
    async def invoke_agent(
        self,
        agent_id: str,
        payload: Dict[str, Any],
        claims: Dict[str, Any],
        use_context_token: bool = True,
    ) -> AsyncIterator[AgentEvent]:
        """
        Invoke an agent and stream events.
        
        Args:
            agent_id: Agent identifier
            payload: Invocation payload containing:
                - input: User query or agent-specific input
                - thread_id: Thread identifier
                - step_id: Plan step identifier (optional)
                - data_scope: Data scoping filters (optional)
            claims: Resolved JWT claims
            use_context_token: If True, mint context token instead of inline context
        
        Yields:
            AgentEvent: Stream of agent execution events
        """
        # Get agent metadata and adapter
        try:
            agent_meta = self.registry.get_meta(agent_id)
            adapter = self.registry.get_adapter(agent_id)
        except Exception as e:
            logger.error(f"Failed to get agent {agent_id}: {e}")
            yield AgentEvent(
                type=EventType.ERROR,
                agent_id=agent_id,
                run_id=payload.get("run_id", str(uuid4())),
                step_id=payload.get("step_id", "unknown"),
                tenant_id=claims.get("tenant_id", "default"),
                data={"error": f"Agent not found: {agent_id}"},
                metadata={},
            )
            return
        
        # Extract payload fields
        thread_id = payload.get("thread_id", str(uuid4()))
        run_id = payload.get("run_id", str(uuid4()))
        step_id = payload.get("step_id", "step_1")
        user_input = payload.get("input", "")
        step_index = payload.get("step_index", 0)
        
        # Check if agent should use conversation Phase 0 (skipped when chained from planner)
        conversation_state = None
        if (
            agent_meta.use_conversation_phase0
            and agent_meta.conversation_vertical
            and not payload.get("skip_conversation_phase0")
        ):
            try:
                conversation_state = await self._run_conversation_phase0(
                    user_input=user_input,
                    thread_id=thread_id,
                    vertical_id=agent_meta.conversation_vertical,
                    claims=claims,
                    extra_initial_state=payload.get("initial_state"),
                )
                
                if conversation_state:
                    if conversation_state.get("is_complete"):
                        # Conversation completed - merge enriched state into payload
                        # The adapter will use this to build proper initial state
                        user_input = conversation_state.get("user_query", user_input)
                        
                        # Merge conversation state into payload for workflow
                        # This includes: active_project_id, selected_data_sources, compliance_profile, etc.
                        payload["conversation_state"] = conversation_state
                        payload["active_project_id"] = conversation_state.get("active_project_id")
                        payload["selected_data_sources"] = conversation_state.get("selected_data_sources", [])
                        payload["compliance_profile"] = conversation_state.get("compliance_profile", {})
                        
                        # Set intent if conversation determined it
                        if conversation_state.get("csod_intent"):
                            payload["csod_intent"] = conversation_state.get("csod_intent")

                        logger.info(f"Conversation Phase 0 completed, enriched payload with conversation state")

                        if conversation_state.get("csod_planner_only"):
                            logger.info(
                                "Direct mode (csod_planner_only) — Phase 0 complete, "
                                "chaining to Phase 1 decomposition planner flow"
                            )
                    else:
                        # Conversation needs user input - yield checkpoint event
                        checkpoint = conversation_state.get("csod_conversation_checkpoint")
                        if checkpoint:
                            yield AgentEvent(
                                type=EventType.STEP_START,
                                agent_id=agent_id,
                                run_id=run_id,
                                step_id=step_id,
                                tenant_id=claims.get("tenant_id", "default"),
                                data={
                                    "checkpoint": checkpoint,
                                    "message": "Conversation Phase 0 requires user input",
                                },
                                metadata={"phase": "conversation"},
                            )
                            return
            except Exception as e:
                logger.warning(f"Conversation Phase 0 failed, continuing without it: {e}", exc_info=True)
                # Continue without conversation if it fails
        
        # Compose context
        try:
            context = await self.context_composer.compose(
                thread_id=thread_id,
                user_input=user_input,
                agent_meta=agent_meta,
                claims=claims,
                step_index=step_index,
            )
        except Exception as e:
            logger.error(f"Failed to compose context: {e}", exc_info=True)
            yield AgentEvent(
                type=EventType.ERROR,
                agent_id=agent_id,
                run_id=run_id,
                step_id=step_id,
                tenant_id=claims.get("tenant_id", "default"),
                data={"error": f"Context composition failed: {e}"},
                metadata={},
            )
            return
        
        # Mint context token if requested
        if use_context_token:
            try:
                ctx_token = await self.context_token_service.mint(context, ttl=300)
                # Replace context with token in payload
                payload["ctx_token"] = ctx_token
                payload["hint"] = {
                    "message_count": len(context.session.get("messages", [])),
                    "has_summary": bool(context.session.get("summary")),
                    "has_memory": bool(context.memory),
                    "tenant_id": claims.get("tenant_id", "default"),
                    "context_tier": claims.get("context_tier", "standard"),
                }
            except Exception as e:
                logger.warning(f"Failed to mint context token, using inline context: {e}")
                use_context_token = False
        
        # Build adapter payload
        adapter_payload = {
            **payload,
            "agent_id": agent_id,
            "run_id": run_id,
            "step_id": step_id,
            "tenant_id": claims.get("tenant_id", "default"),
        }
        
        # Add data scope from claims
        data_scope = claims.get("data_scope", {})
        if data_scope:
            adapter_payload["data_scope"] = data_scope
        
        # Build adapter config
        adapter_config = {
            "timeout": payload.get("timeout_seconds", 60),
            "configurable": {
                "thread_id": thread_id,
            },
        }
        
        # Stream agent events and detect planner output for chaining
        planner_output = None
        next_agent_id = None
        
        try:
            async for event in adapter.stream(
                adapter_payload,
                context if not use_context_token else ComposedContext(
                    system={},
                    session={},
                    turn={},
                    memory=None,
                ),
                adapter_config,
            ):
                # Ensure event has required fields
                if not event.agent_id:
                    event.agent_id = agent_id
                if not event.run_id:
                    event.run_id = run_id
                if not event.step_id:
                    event.step_id = step_id
                if not event.tenant_id:
                    event.tenant_id = claims.get("tenant_id", "default")
                
                # Check for planner output in STEP_FINAL event
                if event.type == EventType.STEP_FINAL:
                    event_data = event.data or {}
                    if event_data.get("is_planner_output"):
                        planner_output = event_data.get("final_state", {})
                        next_agent_id = event_data.get("next_agent_id")
                        logger.info(f"Planner output detected, next agent: {next_agent_id}")
                
                yield event
            
            # After agent completes, chain to next agent if planner output detected
            if planner_output and next_agent_id:
                logger.info(f"Chaining from planner to agent: {next_agent_id}")
                async for chained_event in self._chain_to_next_agent(
                    planner_output=planner_output,
                    next_agent_id=next_agent_id,
                    original_run_id=run_id,
                    original_step_id=step_id,
                    thread_id=thread_id,
                    claims=claims,
                    use_context_token=use_context_token,
                ):
                    yield chained_event
        
        except Exception as e:
            logger.error(f"Agent execution error: {e}", exc_info=True)
            yield AgentEvent(
                type=EventType.ERROR,
                agent_id=agent_id,
                run_id=run_id,
                step_id=step_id,
                tenant_id=claims.get("tenant_id", "default"),
                data={"error": str(e)},
                metadata={"error_type": type(e).__name__},
            )
    
    async def resolve_context_token(self, token: str) -> ComposedContext:
        """
        Resolve a context token (for agent-side context fetching).
        
        Args:
            token: Context token string
        
        Returns:
            ComposedContext instance
        
        Raises:
            ContextExpiredError: If token is invalid or expired
        """
        return await self.context_token_service.resolve(token)
    
    async def _chain_to_next_agent(
        self,
        planner_output: Dict[str, Any],
        next_agent_id: str,
        original_run_id: str,
        original_step_id: str,
        thread_id: str,
        claims: Dict[str, Any],
        use_context_token: bool = True,
    ) -> AsyncIterator[AgentEvent]:
        """
        Chain from planner output to the next agent.
        
        Args:
            planner_output: Final state from planner workflow
            next_agent_id: Agent ID to chain to
            original_run_id: Original run ID from planner
            original_step_id: Original step ID from planner
            thread_id: Thread identifier
            claims: JWT claims
            use_context_token: Whether to use context tokens
        
        Yields:
            AgentEvent: Stream of events from the chained agent
        """
        logger.info(f"Chaining to agent {next_agent_id} with planner output")
        next_payload = build_planner_chain_invoke_payload(
            planner_output,
            thread_id=thread_id,
            original_run_id=original_run_id,
            original_step_id=original_step_id,
        )
        # Chain to next agent
        async for event in self.invoke_agent(
            agent_id=next_agent_id,
            payload=next_payload,
            claims=claims,
            use_context_token=use_context_token,
        ):
            # Update metadata to indicate this is a chained event
            event.metadata = event.metadata or {}
            event.metadata["chained_from"] = "csod-planner"
            event.metadata["original_run_id"] = original_run_id
            yield event
    
    async def _run_conversation_phase0(
        self,
        user_input: str,
        thread_id: str,
        vertical_id: str,
        claims: Dict[str, Any],
        extra_initial_state: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Run conversation Phase 0 before agent execution.
        
        Args:
            user_input: User query
            thread_id: Thread identifier
            vertical_id: Vertical ID for conversation config (e.g., "lms", "dt")
            claims: JWT claims
        
        Returns:
            Conversation state dict, or None if conversation not needed/available
        """
        try:
            from app.conversation.planner_workflow import create_conversation_planner_app
            from app.conversation.verticals.lms_config import LMS_CONVERSATION_CONFIG
            from app.conversation.integration import create_dt_conversation_config
            
            # Get conversation config based on vertical
            if vertical_id == "lms":
                config = LMS_CONVERSATION_CONFIG
            elif vertical_id == "dt":
                config = create_dt_conversation_config()
            else:
                logger.warning(f"Unknown vertical_id: {vertical_id}, skipping conversation Phase 0")
                return None
            
            # Create conversation app
            conversation_app = create_conversation_planner_app(config)
            
            # Build initial state
            initial_state = {
                "user_query": user_input,
                "session_id": thread_id,
                "thread_id": thread_id,
            }
            # Merge caller-supplied extra fields (e.g. csod_planner_only) so the
            # planner workflow can read them.
            if extra_initial_state:
                initial_state.update(extra_initial_state)
            
            # Run conversation
            config_dict = {"configurable": {"thread_id": thread_id}}
            conversation_state = conversation_app.invoke(initial_state, config=config_dict)
            
            logger.info(f"Conversation Phase 0 completed: is_complete={conversation_state.get('is_complete')}")
            return conversation_state
            
        except Exception as e:
            logger.error(f"Failed to run conversation Phase 0: {e}", exc_info=True)
            return None


def get_agent_invocation_service(
    registry = None,
    context_composer = None,
    context_token_service = None,
):
    """
    Get or create agent invocation service instance.
    
    Args:
        registry: Optional agent registry (will create if None)
        context_composer: Optional context composer (will create if None)
        context_token_service: Optional context token service (will create if None)
    
    Returns:
        AgentInvocationService instance
    """
    from app.adapters.registry import get_agent_registry
    from app.core.dependencies import get_dependencies
    from app.services.context_composer import ContextComposer
    from app.services.context_token import ContextTokenService
    from app.core.settings import get_settings
    
    if registry is None:
        registry = get_agent_registry()
    
    if context_composer is None or context_token_service is None:
        # Get cache client
        # Note: get_dependencies() is async and cannot be called from sync context.
        # Dependencies are initialized at startup and stored in app.state.dependencies.
        # For this sync function, we use get_cache_client() directly.
        from app.storage.cache import get_cache_client
        cache = get_cache_client()
        
        if context_composer is None:
            context_composer = ContextComposer(cache)
        
        if context_token_service is None:
            settings = get_settings()
            secret_key = getattr(settings, "CONTEXT_TOKEN_SECRET", "default-secret-key-change-in-production")
            context_token_service = ContextTokenService(cache, secret_key)
    
    return AgentInvocationService(
        registry=registry,
        context_composer=context_composer,
        context_token_service=context_token_service,
    )

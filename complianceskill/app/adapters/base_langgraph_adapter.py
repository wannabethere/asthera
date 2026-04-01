"""
Base LangGraph Adapter

Generic LangGraph adapter with workflow-agnostic checkpoint handling.
Specialized adapters (CSOD, MDL, DT, etc.) extend this base class.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Dict, Any, Optional, List, Set
from uuid import uuid4

from langgraph.checkpoint.base import BaseCheckpointSaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

from app.adapters.base import AgentAdapter, AgentEvent, EventType, ComposedContext

logger = logging.getLogger(__name__)


@dataclass
class NarratorContext:
    """Context for the planner narrator LLM."""
    user_query: str
    node_name: str
    node_output: Dict[str, Any]
    node_status: str
    narrative_so_far: str
    next_step_label: Optional[str]


def _build_narrator_prompt(ctx: NarratorContext) -> str:
    """Build the human message for the narrator LLM."""
    parts = [f"User question: {ctx.user_query}\n"]
    if ctx.narrative_so_far:
        parts.append(f"What I have said so far:\n{ctx.narrative_so_far}\n")
    parts.append(f"Step just completed: {ctx.node_name}")
    parts.append(f"Status: {ctx.node_status}")
    parts.append(f"What this step found:\n{json.dumps(ctx.node_output, indent=2)}")
    if ctx.next_step_label:
        parts.append(f"Next step: {ctx.next_step_label}")
    else:
        parts.append("This is the final step.")
    return "\n\n".join(parts)


class BaseLangGraphAdapter(AgentAdapter):
    """
    Base adapter for LangGraph workflows with generic checkpoint handling.
    
    Specialized adapters should extend this class and override:
    - get_preserved_state_keys() - return list of state keys to preserve on checkpoint resume
    - get_checkpoint_response_fields() - return list of payload keys that indicate checkpoint resume
    - extract_checkpoint_from_state() - extract checkpoint info from workflow-specific state
    """
    
    def __init__(
        self,
        graph: Any,  # Compiled LangGraph (result of StateGraph.compile())
        checkpointer: Optional[BaseCheckpointSaver] = None,
    ):
        """
        Initialize base LangGraph adapter.
        
        Args:
            graph: Compiled LangGraph workflow
            checkpointer: Optional checkpointer for state persistence
        """
        self.graph = graph
        self.checkpointer = checkpointer
    
    def get_preserved_state_keys(self) -> List[str]:
        """
        Get list of state keys to preserve when resuming from checkpoint.
        
        Override in subclasses to specify workflow-specific keys.
        
        Returns:
            List of state key names to preserve
        """
        return []
    
    def get_checkpoint_response_fields(self) -> List[str]:
        """
        Get list of payload keys that indicate we're resuming from a checkpoint.
        
        Override in subclasses to specify workflow-specific checkpoint response fields.
        
        Returns:
            List of payload key names that indicate checkpoint resume
        """
        return []
    
    def extract_checkpoint_from_state(self, state: Dict[str, Any], node_name: str) -> Optional[Dict[str, Any]]:
        """
        Extract checkpoint information from workflow state.
        
        Override in subclasses to handle workflow-specific checkpoint formats.
        
        Args:
            state: LangGraph state dictionary
            node_name: Name of the node that may have created a checkpoint
        
        Returns:
            Checkpoint dictionary if found, None otherwise
        """
        # Generic checkpoint extraction - check for common patterns
        checkpoints = state.get("checkpoints", [])
        if checkpoints:
            for checkpoint in reversed(checkpoints):
                if isinstance(checkpoint, dict) and checkpoint.get("requires_user_input", False):
                    return {
                        "checkpoint_id": checkpoint.get("node", node_name),
                        "checkpoint_type": checkpoint.get("type", "unknown"),
                        "node": checkpoint.get("node", node_name),
                        "data": checkpoint.get("data", {}),
                        "message": checkpoint.get("message", "Waiting for user input"),
                        "requires_user_input": True,
                    }
        
        return None

    def get_narrator_nodes(self) -> Set[str]:
        """Set of node names that trigger the planner narrator. Override in subclasses (e.g. CSOD)."""
        return set()

    def get_narrator_prompt_path(self) -> Optional[Path]:
        """Path to prompts dir for narrator (e.g. PROMPTS_CSOD). None = no narrator."""
        return None

    def get_next_step_label(self, node_name: str) -> Optional[str]:
        """Human-readable label for what runs after this node. Override in subclasses."""
        return None

    async def _stream_narrator(
        self,
        node_name: str,
        node_output: Dict[str, Any],
        state: Dict[str, Any],
        agent_id: str,
        run_id: str,
        step_id: str,
        tenant_id: str,
    ) -> AsyncIterator[AgentEvent]:
        """
        Call the narrator LLM and stream its tokens as REASONING_TOKEN events.
        Yields REASONING_TOKEN then REASONING_DONE. Degrades gracefully if prompt missing or LLM fails.
        """
        prompts_dir = self.get_narrator_prompt_path()
        if not prompts_dir:
            return
        try:
            from app.agents.prompt_loader import load_prompt
            prompt_text = load_prompt("14_planner_narrator", prompts_dir=str(prompts_dir))
        except FileNotFoundError:
            return
        narrative_so_far = "\n".join(
            entry.get("text", "") for entry in state.get("csod_reasoning_narrative", [])
        )
        ctx = NarratorContext(
            user_query=state.get("user_query", ""),
            node_name=node_name,
            node_output=node_output.get("findings", {}),
            node_status=node_output.get("status", "success"),
            narrative_so_far=narrative_so_far,
            next_step_label=self.get_next_step_label(node_name),
        )
        human_message = _build_narrator_prompt(ctx)
        from app.core.dependencies import get_llm
        from langchain_core.prompts import ChatPromptTemplate
        llm = get_llm(temperature=0.3)
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", prompt_text),
            ("human", "{input}"),
        ])
        chain = prompt_template | llm
        accumulated: List[str] = []
        try:
            async for chunk in chain.astream({"input": human_message}):
                content = chunk.content if hasattr(chunk, "content") else str(chunk)
                if content:
                    accumulated.append(content)
                    yield AgentEvent(
                        type=EventType.REASONING_TOKEN,
                        agent_id=agent_id,
                        run_id=run_id,
                        step_id=step_id,
                        tenant_id=tenant_id,
                        data={"text": content, "node": node_name},
                        metadata={"node": node_name},
                    )
        except Exception as e:
            logger.warning(f"Narrator LLM error for node {node_name}: {e}")
            return
        full_text = "".join(accumulated)
        yield AgentEvent(
            type=EventType.REASONING_DONE,
            agent_id=agent_id,
            run_id=run_id,
            step_id=step_id,
            tenant_id=tenant_id,
            data={"node": node_name, "text": full_text, "node_output": node_output},
            metadata={"node": node_name},
        )
        if "csod_reasoning_narrative" not in state:
            state["csod_reasoning_narrative"] = []
        state["csod_reasoning_narrative"].append({"node": node_name, "text": full_text})
    
    async def stream(
        self,
        payload: Dict[str, Any],
        context: ComposedContext,
        config: Dict[str, Any]
    ) -> AsyncIterator[AgentEvent]:
        """
        Stream LangGraph execution events.
        
        Args:
            payload: Agent invocation payload
            context: Composed context
            config: Additional configuration
        
        Yields:
            AgentEvent: Standardized events
        """
        # Extract payload fields
        run_id = payload.get("run_id", str(uuid4()))
        step_id = payload.get("step_id", "step_1")
        tenant_id = payload.get("tenant_id", "default")
        agent_id = payload.get("agent_id", "unknown")
        thread_id = payload.get("thread_id", str(uuid4()))
        user_input = payload.get("input", "")
        
        # Build LangGraph config
        graph_config = {
            "configurable": {
                "thread_id": thread_id,
                **config.get("configurable", {}),
            }
        }
        
        # Resolve the effective checkpointer: prefer the one passed at construction time,
        # but fall back to the one baked into the compiled graph (e.g. MemorySaver from
        # create_csod_planner_app / create_*_app).  This is the root fix for the adapter
        # always seeing self.checkpointer = None even though the graph has a checkpointer.
        _checkpointer = self.checkpointer or getattr(self.graph, "checkpointer", None)
        
        # Check if we're resuming from a checkpoint
        checkpoint_response_fields = self.get_checkpoint_response_fields()
        is_resuming = any(payload.get(field) for field in checkpoint_response_fields)
        
        # If resuming, try to restore existing state from checkpointer
        existing_state = {}
        if is_resuming and _checkpointer:
            try:
                state_snapshot = self.graph.get_state(graph_config)
                if state_snapshot and state_snapshot.values:
                    existing_state = state_snapshot.values
                    logger.info(f"✓ Restored existing state from checkpointer with {len(existing_state)} keys")
                    # Log which keys we're preserving
                    preserved_keys = self.get_preserved_state_keys()
                    important_keys = [k for k in existing_state.keys() if k in preserved_keys]
                    if important_keys:
                        logger.info(f"  Will preserve state keys: {important_keys}")
                        # Log specific values for debugging
                        for key in important_keys:
                            if key in existing_state:
                                value = existing_state[key]
                                if isinstance(value, list):
                                    logger.info(f"    {key}: {len(value)} item(s)")
                                elif isinstance(value, dict):
                                    logger.info(f"    {key}: {len(value)} key(s)")
                                else:
                                    logger.info(f"    {key}: {type(value).__name__}")
            except Exception as e:
                logger.warning(f"Could not restore state from checkpointer (may be first run): {e}", exc_info=True)
        
        # Guard: session expired (service restart cleared in-memory checkpointer)
        # is_resuming=True means the request carries checkpoint-response fields,
        # but the MemorySaver has no record of this thread (e.g. server was restarted).
        # Proceeding with an empty user_query causes the concept resolver to return nothing
        # and the user sees a "let me rephrase" loop.  Instead, emit a session_expired
        # CHECKPOINT so the frontend can display a friendly error and allow the user to
        # start a fresh conversation.
        if is_resuming and not existing_state:
            logger.warning(
                "Session expired: is_resuming=True but MemorySaver has no state for "
                f"thread_id={thread_id}. Emitting session_expired checkpoint."
            )
            yield AgentEvent(
                type=EventType.STEP_START,
                agent_id=agent_id,
                run_id=run_id,
                step_id=step_id,
                tenant_id=tenant_id,
                data={"input": user_input},
                metadata={"thread_id": thread_id},
            )
            yield AgentEvent(
                type=EventType.CHECKPOINT,
                agent_id=agent_id,
                run_id=run_id,
                step_id=step_id,
                tenant_id=tenant_id,
                data={
                    "checkpoint_type": "session_expired",
                    "phase": "session_expired",
                    "message": (
                        "Your session has expired (the server was restarted). "
                        "Please start a new conversation and re-enter your question."
                    ),
                    "resume_with_field": None,
                },
                metadata={"thread_id": thread_id},
            )
            yield AgentEvent(
                type=EventType.STEP_FINAL,
                agent_id=agent_id,
                run_id=run_id,
                step_id=step_id,
                tenant_id=tenant_id,
                data={"status": "session_expired"},
                metadata={},
            )
            return

        # Build LangGraph input state
        # When resuming, we want to update only the checkpoint response fields
        # and let LangGraph restore the rest from the checkpointer
        if is_resuming and existing_state:
            # When resuming, start with minimal input - only checkpoint response fields
            # LangGraph will automatically merge this with the restored state
            graph_input = self._build_graph_input(payload, context)
            
            # Preserve important state fields that should persist across checkpoint resume
            preserved_keys = self.get_preserved_state_keys()
            logger.info(f"Merging preserved state keys into graph input...")
            for key in preserved_keys:
                if key in existing_state:
                    existing_value = existing_state[key]
                    current_value = graph_input.get(key)
                    
                    # Always preserve if current value is empty/None, or if it's a critical key
                    # For critical keys like csod_concept_matches, prefer checkpointer version (complete) over payload version (partial)
                    should_preserve = (
                        not current_value or 
                        (isinstance(current_value, list) and len(current_value) == 0) or
                        (isinstance(current_value, dict) and len(current_value) == 0)
                    )
                    
                    # For checkpoint_responses, always prefer payload over checkpointer
                    # because checkpoint responses are per-turn and should come from the current request
                    if key == "csod_checkpoint_responses":
                        logger.info(f"  Processing csod_checkpoint_responses preservation:")
                        logger.info(f"    Payload has {len(current_value) if isinstance(current_value, dict) else 0} response(s)")
                        logger.info(f"    Checkpointer has {len(existing_value) if isinstance(existing_value, dict) else 0} response(s)")
                        
                        # Always prefer payload checkpoint responses (they're per-turn responses)
                        if current_value and isinstance(current_value, dict) and len(current_value) > 0:
                            logger.info(f"    Using payload checkpoint responses (per-turn responses take precedence)")
                            should_preserve = False  # Don't overwrite payload with checkpointer
                        elif not current_value or (isinstance(current_value, dict) and len(current_value) == 0):
                            # Payload has no checkpoint responses, preserve from checkpointer
                            logger.info(f"    Preserving checkpoint responses from checkpointer (payload has none)")
                            should_preserve = True
                    
                    # For concept_matches, prefer checkpointer version even if payload has a value
                    # because checkpointer has complete data (project_ids, mdl_table_refs) while payload is partial
                    elif key == "csod_concept_matches":
                        logger.info(f"  Processing csod_concept_matches preservation:")
                        logger.info(f"    Payload has {len(current_value) if isinstance(current_value, list) else 0} matches")
                        logger.info(f"    Checkpointer has {len(existing_value) if isinstance(existing_value, list) else 0} matches")
                        
                        # If payload has matches but checkpointer is empty, use payload (don't preserve empty checkpointer)
                        if current_value and isinstance(current_value, list) and len(current_value) > 0:
                            if not existing_value or (isinstance(existing_value, list) and len(existing_value) == 0):
                                logger.info(f"    Using payload concept matches (checkpointer is empty)")
                                should_preserve = False  # Don't overwrite payload with empty checkpointer
                            elif existing_value and isinstance(existing_value, list) and len(existing_value) > 0:
                                # Both have values - check which is more complete
                                first_existing = existing_value[0] if isinstance(existing_value[0], dict) else {}
                                first_current = current_value[0] if isinstance(current_value[0], dict) else {}
                                # Prefer checkpointer version if it has project_ids (more complete)
                                if first_existing.get("project_ids") and not first_current.get("project_ids"):
                                    should_preserve = True
                                    logger.info(f"    Preferring checkpointer version (has project_ids) over payload version")
                                else:
                                    logger.info(f"    Using payload version (checkpointer doesn't have project_ids or payload is more complete)")
                                    should_preserve = False

                    # Scoping answers are accumulated across checkpoint turns; payload is only
                    # the latest keys — must merge with checkpointer or prior answers are lost
                    # and the planner loops forever on scoping.
                    elif key == "csod_scoping_answers":
                        ckpt = existing_value if isinstance(existing_value, dict) else {}
                        pay = current_value if isinstance(current_value, dict) else {}
                        graph_input[key] = {**ckpt, **pay}
                        logger.info(
                            "✓ Merged csod_scoping_answers checkpoint+payload keys: %s → %s",
                            (list(ckpt.keys()), list(pay.keys())),
                            list(graph_input[key].keys()),
                        )
                        self._log_preserved_state_key(key, graph_input[key])
                        continue

                    if should_preserve:
                        graph_input[key] = existing_value
                        logger.info(f"✓ Preserved state key from checkpointer: {key} (value type: {type(existing_value).__name__})")
                        # Log size for list/dict values
                        if isinstance(existing_value, (list, dict)):
                            size = len(existing_value)
                            logger.info(f"  Preserved {size} item(s)")
                        # Call workflow-specific logging hook
                        self._log_preserved_state_key(key, existing_value)
                    else:
                        logger.debug(f"  Skipped preserving {key} (already has value in graph_input)")
            
            # If checkpoint responses are present in payload, clear any existing checkpoint from checkpointer
            # This ensures the workflow processes the response instead of re-prompting
            checkpoint_responses = graph_input.get("csod_checkpoint_responses", {})
            if checkpoint_responses and isinstance(checkpoint_responses, dict) and len(checkpoint_responses) > 0:
                # Clear checkpoint from checkpointer state if it exists
                if "csod_planner_checkpoint" in existing_state:
                    logger.info("  Clearing checkpoint from checkpointer state (checkpoint response present in payload)")
                    graph_input["csod_planner_checkpoint"] = None
                # Also clear from graph_input if it was set from checkpointer
                elif "csod_planner_checkpoint" in graph_input:
                    logger.info("  Clearing checkpoint from graph_input (checkpoint response present)")
                    graph_input["csod_planner_checkpoint"] = None
            elif payload.get("csod_scoping_answers"):
                cp = existing_state.get("csod_planner_checkpoint") if isinstance(existing_state.get("csod_planner_checkpoint"), dict) else {}
                if cp.get("phase") == "scoping":
                    logger.info("  Clearing scoping checkpoint (csod_scoping_answers in payload)")
                    graph_input["csod_planner_checkpoint"] = None
        else:
            # Not resuming - build normal input
            graph_input = self._build_graph_input(payload, context)
        
        # Emit STEP_START event
        yield AgentEvent(
            type=EventType.STEP_START,
            agent_id=agent_id,
            run_id=run_id,
            step_id=step_id,
            tenant_id=tenant_id,
            data={"input": user_input},
            metadata={"thread_id": thread_id},
        )
        
        # Log graph input before streaming (for debugging)
        if is_resuming:
            logger.info(f"Graph input keys before streaming: {list(graph_input.keys())}")
            preserved_keys = self.get_preserved_state_keys()
            for key in preserved_keys:
                if key in graph_input:
                    value = graph_input[key]
                    if isinstance(value, list):
                        logger.info(f"  {key} in graph_input: {len(value)} item(s)")
                    elif isinstance(value, dict):
                        logger.info(f"  {key} in graph_input: {len(value)} key(s)")
                    else:
                        logger.info(f"  {key} in graph_input: {type(value).__name__}")
        
        try:
            # Track last state seen in events (fallback if checkpointer retrieval fails)
            # Prioritize state that has checkpoints
            last_seen_state = None
            checkpoint_state = None  # State with checkpoint takes priority

            # Auto-resume loop: when LangGraph pauses at interrupt_after but the
            # node did NOT create a user-facing checkpoint (e.g. pass-through /
            # auto-confirm), we re-invoke with input=None so the graph continues
            # to the next node.  Mirrors csod_workflow_service.py's approach.
            _MAX_AUTO_RESUMES = 5
            _run_input = graph_input  # first pass uses the built graph_input
            _checkpoint_emitted = False

            for _auto_pass in range(_MAX_AUTO_RESUMES + 1):
                _found_checkpoint_this_pass = False

                # Stream LangGraph events
                async for raw_event in self.graph.astream_events(
                    _run_input,
                    version="v2",
                    config=graph_config,
                ):
                    # Capture state from on_state_update events
                    if raw_event.get("event") == "on_state_update":
                        event_data = raw_event.get("data", {})
                        state_update = event_data.get("state", {})
                        name = raw_event.get("name", "")
                        if isinstance(state_update, dict) and any(
                            k.startswith("csod_") or k.startswith("compliance_") or k.startswith("dt_")
                            for k in state_update.keys()
                        ):
                            has_checkpoint = (
                                "csod_planner_checkpoint" in state_update or
                                "csod_conversation_checkpoint" in state_update or
                                any("checkpoint" in k.lower() for k in state_update.keys())
                            )
                            if has_checkpoint:
                                checkpoint_state = state_update
                                logger.info(f"✓ Captured state with checkpoint from on_state_update (node: '{name}'): {len(state_update)} keys")
                                if "csod_planner_checkpoint" in state_update:
                                    cp = state_update["csod_planner_checkpoint"]
                                    if isinstance(cp, dict):
                                        logger.info(f"  Checkpoint phase: {cp.get('phase', 'unknown')}, requires_input: {cp.get('requires_user_input', False)}")
                            else:
                                last_seen_state = state_update
                                logger.debug(f"Captured state from on_state_update event (node: {name}): {len(state_update)} keys")

                    # Also capture state from on_chain_end events as additional fallback
                    elif raw_event.get("event") == "on_chain_end":
                        event_data = raw_event.get("data", {})
                        output = event_data.get("output", {})
                        name = raw_event.get("name", "")
                        if isinstance(output, dict) and any(
                            k.startswith("csod_") or k.startswith("compliance_") or k.startswith("dt_")
                            for k in output.keys()
                        ):
                            has_checkpoint = (
                                "csod_planner_checkpoint" in output or
                                "csod_conversation_checkpoint" in output or
                                any("checkpoint" in k.lower() for k in output.keys())
                            )
                            if has_checkpoint and not checkpoint_state:
                                checkpoint_state = output
                                logger.info(f"✓ Captured state with checkpoint from on_chain_end (node: '{name}'): {len(output)} keys")
                                if "csod_planner_checkpoint" in output:
                                    cp = output["csod_planner_checkpoint"]
                                    if isinstance(cp, dict):
                                        logger.info(f"  Checkpoint phase: {cp.get('phase', 'unknown')}, requires_input: {cp.get('requires_user_input', False)}")
                            elif not last_seen_state:
                                last_seen_state = output
                                logger.debug(f"Captured state from on_chain_end event (node: {name}): {len(output)} keys")

                    # ── Emit STATE_UPDATE for key pipeline state fields ──────────
                    # When on_chain_end or on_state_update carries fields the
                    # frontend pipeline UI needs (intent, signals, persona, etc.),
                    # forward a lightweight STATE_UPDATE event so the SSE stream
                    # delivers them before the workflow finishes.
                    _state_src = None
                    if raw_event.get("event") == "on_chain_end":
                        _state_src = raw_event.get("data", {}).get("output")
                    elif raw_event.get("event") == "on_state_update":
                        _state_src = raw_event.get("data", {}).get("state")
                    if isinstance(_state_src, dict):
                        _UI_STATE_KEYS = (
                            "csod_stage_1_intent", "csod_intent", "csod_intent_confidence",
                            "csod_persona", "csod_intent_classifier_output",
                            "csod_metric_recommendations", "csod_kpi_recommendations",
                            "csod_area_matches", "csod_primary_area",
                            "data_enrichment", "goal_intent",
                        )
                        _ui_slice = {k: _state_src[k] for k in _UI_STATE_KEYS if k in _state_src}
                        if _ui_slice:
                            yield AgentEvent(
                                type=EventType.STATE_UPDATE,
                                agent_id=agent_id, run_id=run_id,
                                step_id=step_id, tenant_id=tenant_id,
                                data={"state": _ui_slice, "node": raw_event.get("name", "")},
                                metadata={"node": raw_event.get("name", "")},
                            )

                    # Narrator: after a narrator node completes, stream narrator LLM tokens
                    if raw_event.get("event") == "on_chain_end":
                        event_data_inner = raw_event.get("data", {})
                        output_inner = event_data_inner.get("output", {})
                        name_inner = raw_event.get("name", "")
                        if (isinstance(output_inner, dict)
                                and name_inner in self.get_narrator_nodes()):
                            node_output_entry = output_inner.get("csod_node_output")
                            if node_output_entry:
                                async for r_event in self._stream_narrator(
                                    node_name=name_inner,
                                    node_output=node_output_entry,
                                    state=output_inner,
                                    agent_id=agent_id,
                                    run_id=run_id,
                                    step_id=step_id,
                                    tenant_id=tenant_id,
                                ):
                                    yield r_event

                    # Normalize and yield events
                    event = self.normalize_event(raw_event, graph_config)
                    if event:
                        event.agent_id = agent_id
                        event.run_id = run_id
                        event.step_id = step_id
                        event.tenant_id = tenant_id
                        if event.type == EventType.CHECKPOINT:
                            _found_checkpoint_this_pass = True
                            _checkpoint_emitted = True
                        yield event
                        # When a CHECKPOINT is returned for a graph node, the
                        # TOOL_END (node_complete) was skipped by normalize_event.
                        # Emit it here so the frontend flow step transitions to "done".
                        if event.type == EventType.CHECKPOINT:
                            _re = raw_event
                            _meta = _re.get("metadata", {})
                            _lg = _meta.get("langgraph_node", "")
                            _nm = _re.get("name", "")
                            _is_gn = bool(_lg) or any(_nm.startswith(p) for p in ("csod_","dt_","compliance_","mdl_"))
                            if _is_gn:
                                yield AgentEvent(
                                    type=EventType.TOOL_END,
                                    agent_id=agent_id, run_id=run_id,
                                    step_id=step_id, tenant_id=tenant_id,
                                    data={"tool": _lg or _nm, "output": ""},
                                    metadata={"node": _lg or _nm, "is_graph_node": True},
                                )

                # ── Auto-resume check ───────────────────────────────────────
                # After astream_events completes (graph hit interrupt_after or END),
                # check if the graph is paused at an interrupt without a user checkpoint.
                if _found_checkpoint_this_pass:
                    break  # User checkpoint emitted — wait for user input

                try:
                    _snap = self.graph.get_state(graph_config)
                    _pending = list(_snap.next) if (_snap and _snap.next) else []
                except Exception:
                    _pending = []

                if not _pending:
                    break  # Workflow truly finished

                if _auto_pass >= _MAX_AUTO_RESUMES:
                    logger.warning(
                        "Reached auto-resume limit (%d) — treating as complete",
                        _MAX_AUTO_RESUMES,
                    )
                    break

                logger.info(
                    "Auto-resuming from interrupt (no user checkpoint) — pending: %s (pass %d)",
                    _pending, _auto_pass + 1,
                )
                _run_input = None  # pass None so LangGraph resumes from interrupt point

            # ── End of auto-resume loop ────────────────────────────────────

            # Get final state to check for planner output
            final_state = None
            try:
                if _checkpointer and graph_config:
                    logger.info(f"Attempting to retrieve final state from checkpointer (thread_id: {graph_config.get('configurable', {}).get('thread_id', 'N/A')})")
                    state_snapshot = self.graph.get_state(graph_config)
                    if state_snapshot:
                        logger.info(f"State snapshot retrieved: has_values={state_snapshot.values is not None}")
                        if state_snapshot.values:
                            final_state = state_snapshot.values
                            logger.info(f"✓ Retrieved final state from checkpointer with {len(final_state)} keys")
                            # Log if checkpoint is present
                            if "csod_planner_checkpoint" in final_state:
                                logger.info(f"  Found csod_planner_checkpoint in final_state")
                        else:
                            logger.warning(f"State snapshot has no values")
                    else:
                        logger.warning(f"get_state() returned None")
                else:
                    if not _checkpointer:
                        logger.warning(f"Cannot retrieve final state: checkpointer is None")
                    if not graph_config:
                        logger.warning(f"Cannot retrieve final state: graph_config is None")
            except Exception as e:
                logger.warning(f"Could not get final state from checkpointer: {e}", exc_info=True)

            # Fallback to checkpoint state first, then last seen state
            if not final_state:
                if checkpoint_state:
                    logger.info(f"Using checkpoint state from events as fallback ({len(checkpoint_state)} keys)")
                    final_state = checkpoint_state
                elif last_seen_state:
                    logger.info(f"Using last seen state from events as fallback ({len(last_seen_state)} keys)")
                    final_state = last_seen_state

            # ── Check for unresolved checkpoint in final state ──────────
            # The graph may have set a checkpoint (e.g. csod_metric_selection)
            # but completed without interrupt_after pausing it.  Emit the
            # checkpoint so the frontend can show the selection UI.
            if (
                final_state
                and not _checkpoint_emitted
                and final_state.get("csod_conversation_checkpoint")
                and not final_state.get("csod_checkpoint_resolved", True)
            ):
                _cp = final_state["csod_conversation_checkpoint"]
                _cp_data = self.extract_checkpoint_from_state(final_state, "final") or {
                    "checkpoint_type": _cp.get("phase", "unknown"),
                    "message": (_cp.get("turn") or {}).get("message", ""),
                    "data": _cp,
                }
                logger.info(
                    "[Adapter] Emitting deferred checkpoint from final state: %s",
                    _cp_data.get("checkpoint_type"),
                )
                yield AgentEvent(
                    type=EventType.CHECKPOINT,
                    agent_id=agent_id, run_id=run_id,
                    step_id=step_id, tenant_id=tenant_id,
                    data=_cp_data,
                    metadata={"deferred": True},
                )
                _checkpoint_emitted = True

            # ── Auto-trigger preview generation after Phase 1 completes ──
            # When final_state has metric recommendations (Phase 1 produced output),
            # stream previews one at a time so the frontend can render cards
            # incrementally without holding all previews in memory at once.
            if (
                final_state
                and not _checkpoint_emitted
                and (
                    final_state.get("csod_metric_recommendations")
                    or final_state.get("csod_adhoc_nl_queries")
                )
            ):
                try:
                    from app.agents.csod.csod_nodes.node_sql_agent import generate_previews_stream

                    metrics = final_state.get("csod_metric_recommendations") or []
                    kpis = final_state.get("csod_kpi_recommendations") or []
                    tables = final_state.get("csod_table_recommendations") or []

                    logger.info(
                        "[Adapter] Phase 1 complete — auto-triggering preview generation "
                        "(metrics=%d, adhoc=%d)",
                        len(metrics),
                        len(final_state.get("csod_adhoc_nl_queries") or []),
                    )

                    all_previews: list = []
                    async for preview in generate_previews_stream(
                        metrics=metrics,
                        kpis=kpis,
                        tables=tables,
                        intent=final_state.get("csod_intent") or "",
                        primary_focus_area=final_state.get("csod_primary_area") or "",
                    ):
                        all_previews.append(preview)
                        # Emit each preview individually so the frontend
                        # can render cards as they arrive.
                        yield AgentEvent(
                            type=EventType.STATE_UPDATE,
                            agent_id=agent_id, run_id=run_id,
                            step_id=step_id, tenant_id=tenant_id,
                            data={
                                "state": {
                                    "csod": {"metric_previews": all_previews},
                                    "csod_metric_previews": all_previews,
                                },
                                "node": "preview_generator",
                            },
                            metadata={"node": "preview_generator", "preview_index": len(all_previews) - 1},
                        )

                    if all_previews:
                        final_state["csod_metric_previews"] = all_previews
                        logger.info("[Adapter] Preview generation produced %d previews", len(all_previews))

                except Exception as e:
                    logger.warning(
                        "[Adapter] Auto-preview generation failed (non-fatal): %s", e,
                        exc_info=True,
                    )

            # Emit STEP_FINAL event with final state if available
            step_final_data = {"status": "completed"}
            if final_state:
                step_final_data["final_state"] = final_state
                # Check for workflow-specific output metadata
                workflow_metadata = self._extract_workflow_metadata(final_state)
                if workflow_metadata:
                    step_final_data.update(workflow_metadata)

                # Explicitly check for checkpoint in final_state and include it in step_final
                # This makes checkpoint detection easier for clients
                checkpoint = self.extract_checkpoint_from_state(final_state, "final")
                if checkpoint:
                    logger.info(f"Including checkpoint in step_final: type={checkpoint.get('checkpoint_type', checkpoint.get('phase', 'unknown'))}")
                    step_final_data["checkpoint"] = checkpoint
            else:
                logger.warning(f"No final_state available for step_final event (checkpointer={_checkpointer is not None}, last_seen_state={last_seen_state is not None})")

            yield AgentEvent(
                type=EventType.STEP_FINAL,
                agent_id=agent_id,
                run_id=run_id,
                step_id=step_id,
                tenant_id=tenant_id,
                data=step_final_data,
                metadata={},
            )
            
        except Exception as e:
            logger.error(f"LangGraph execution error: {e}", exc_info=True)
            yield AgentEvent(
                type=EventType.STEP_ERROR,
                agent_id=agent_id,
                run_id=run_id,
                step_id=step_id,
                tenant_id=tenant_id,
                data={"error": str(e)},
                metadata={"error_type": type(e).__name__},
            )
            raise
    
    def _extract_workflow_metadata(self, final_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract workflow-specific metadata from final state.
        
        Override in subclasses to extract workflow-specific output metadata.
        
        Args:
            final_state: Final state from workflow
        
        Returns:
            Dictionary with workflow-specific metadata (e.g., is_planner_output, next_agent_id)
        """
        return {}
    
    def normalize_event(self, raw_event: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Optional[AgentEvent]:
        """
        Convert LangGraph event to AgentEvent protocol.
        
        Args:
            raw_event: Raw LangGraph event
            config: LangGraph config (for state retrieval)
        
        Returns:
            AgentEvent if event should be emitted, None otherwise
        """
        event_type = raw_event.get("event", "")
        name = raw_event.get("name", "")
        data = raw_event.get("data", {})
        
        # Map LangGraph events to AgentEvent types

        # ── Graph node lifecycle (on_chain_start / on_chain_end) ──────────
        # LangGraph v2 astream_events emits on_chain_start for each node.
        # We forward these as TOOL_START (→ workflow_node_start SSE) so the
        # frontend pipeline can show the node in the conversational flow.
        # Only emit for actual graph nodes (identified by langgraph_node in
        # metadata or csod_/compliance_/dt_ prefix in name).
        if event_type == "on_chain_start":
            meta = raw_event.get("metadata", {})
            lg_node = meta.get("langgraph_node", "")
            # Accept if it's a langgraph_node OR has a csod_/dt_/compliance_ prefix
            is_graph_node = bool(lg_node) or any(
                name.startswith(pfx) for pfx in ("csod_", "dt_", "compliance_", "mdl_")
            )
            if is_graph_node:
                node_label = lg_node or name
                return AgentEvent(
                    type=EventType.TOOL_START,
                    agent_id="",
                    run_id="",
                    step_id="",
                    tenant_id="",
                    data={"tool": node_label, "input": {}},
                    metadata={"node": node_label, "is_graph_node": True},
                )
            return None  # skip non-graph chain starts

        elif event_type == "on_chat_model_stream":
            # Streaming token
            chunk = data.get("chunk")
            if chunk and hasattr(chunk, "content"):
                content = chunk.content
                if content:
                    return AgentEvent(
                        type=EventType.TOKEN,
                        agent_id="",
                        run_id="",
                        step_id="",
                        tenant_id="",
                        data={"text": content},
                        metadata={"node": name},
                    )
        
        elif event_type == "on_tool_start":
            # Tool invocation
            tool_name = data.get("name", name)
            tool_input = data.get("input", {})
            return AgentEvent(
                type=EventType.TOOL_START,
                agent_id="",
                run_id="",
                step_id="",
                tenant_id="",
                data={"tool": tool_name, "input": tool_input},
                metadata={"node": name},
            )
        
        elif event_type == "on_tool_end":
            # Tool completion
            tool_name = data.get("name", name)
            tool_output = data.get("output", "")
            return AgentEvent(
                type=EventType.TOOL_END,
                agent_id="",
                run_id="",
                step_id="",
                tenant_id="",
                data={"tool": tool_name, "output": str(tool_output)},
                metadata={"node": name},
            )
        
        elif event_type == "on_chain_end":
            # Chain/node completion
            output = data.get("output", {})
            meta = raw_event.get("metadata", {})
            lg_node = meta.get("langgraph_node", "")
            # Fix 8.2: Use the node's output directly for checkpoint detection.
            # get_state() returns PREVIOUS committed state here — not the current node's changes.
            state_to_check = output if isinstance(output, dict) else {}
            if isinstance(state_to_check, dict):
                # Check for checkpoints first
                checkpoint = self.extract_checkpoint_from_state(state_to_check, name)
                if checkpoint:
                    logger.info(f"Checkpoint detected in node {name}: {checkpoint.get('checkpoint_type')}")
                    return AgentEvent(
                        type=EventType.CHECKPOINT,
                        agent_id="",
                        run_id="",
                        step_id="",
                        tenant_id="",
                        data=checkpoint,
                        metadata={"node": name},
                    )

                # Only emit FINAL for actual final outputs, not state dicts
                if "output" in state_to_check:
                    is_state_dict = any(
                        k.startswith("csod_") or
                        k.startswith("compliance_") or
                        k.startswith("dt_") or
                        k.startswith("mdl_") or
                        k in ["user_query", "session_id", "messages", "created_at"]
                        for k in state_to_check.keys()
                    )
                    if not is_state_dict:
                        final_text = self._extract_final_text(state_to_check)
                        if final_text:
                            return AgentEvent(
                                type=EventType.FINAL,
                                agent_id="",
                                run_id="",
                                step_id="",
                                tenant_id="",
                                data={"text": final_text},
                                metadata={"node": name},
                            )

            # Emit TOOL_END for graph nodes so the frontend sees node completion
            # (pairs with the TOOL_START emitted from on_chain_start above)
            is_graph_node = bool(lg_node) or any(
                name.startswith(pfx) for pfx in ("csod_", "dt_", "compliance_", "mdl_")
            )
            if is_graph_node:
                node_label = lg_node or name
                return AgentEvent(
                    type=EventType.TOOL_END,
                    agent_id="",
                    run_id="",
                    step_id="",
                    tenant_id="",
                    data={"tool": node_label, "output": ""},
                    metadata={"node": node_label, "is_graph_node": True},
                )
        
        elif event_type == "on_state_update":
            # State update - check for checkpoints
            checkpoint = self.extract_checkpoint_from_state(data.get("state", {}), name)
            if checkpoint:
                return AgentEvent(
                    type=EventType.CHECKPOINT,
                    agent_id="",
                    run_id="",
                    step_id="",
                    tenant_id="",
                    data=checkpoint,
                    metadata={"node": name},
                )
        
        # Filter out other event types
        return None
    
    def _build_graph_input(
        self,
        payload: Dict[str, Any],
        context: ComposedContext
    ) -> Dict[str, Any]:
        """
        Build LangGraph input state from payload and context.
        
        Override in subclasses to add workflow-specific input building logic.
        
        Args:
            payload: Agent invocation payload
            context: Composed context
        
        Returns:
            LangGraph input state dict
        """
        # Start with user input
        graph_input = {
            "user_query": payload.get("input", ""),
        }
        
        # Add session context (messages)
        if context.session:
            messages = context.session.get("messages", [])
            if messages:
                graph_input["messages"] = self._convert_messages(messages)
        
        # Add turn context (recent messages)
        if context.turn:
            recent = context.turn.get("recent", [])
            if recent:
                if "messages" not in graph_input:
                    graph_input["messages"] = []
                graph_input["messages"].extend(self._convert_messages(recent))
        
        # Add system context
        if context.system:
            graph_input.update(context.system)
        
        # Add data scope from payload
        data_scope = payload.get("data_scope", {})
        if data_scope:
            graph_input["data_scope"] = data_scope
        
        # Add common fields
        for key in ["session_id", "active_project_id", "selected_data_sources", "compliance_profile"]:
            if key in payload:
                graph_input[key] = payload[key]
        
        return graph_input
    
    def _convert_messages(self, messages: list) -> list[BaseMessage]:
        """Convert message dicts to LangChain BaseMessage objects"""
        result = []
        for msg in messages:
            if isinstance(msg, BaseMessage):
                result.append(msg)
            elif isinstance(msg, dict):
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                if role == "user":
                    result.append(HumanMessage(content=content))
                elif role == "assistant" or role == "agent":
                    result.append(AIMessage(content=content))
                elif role == "system":
                    result.append(SystemMessage(content=content))
        
        return result
    
    def _extract_final_text(self, output: Dict[str, Any]) -> Optional[str]:
        """Extract final text from LangGraph output"""
        if "output" in output:
            output_val = output["output"]
            if isinstance(output_val, str):
                return output_val
            if isinstance(output_val, dict) and "output" in output_val:
                return str(output_val["output"])
        
        if "messages" in output:
            messages = output["messages"]
            if messages and isinstance(messages[-1], BaseMessage):
                return messages[-1].content
            if messages and isinstance(messages[-1], dict):
                return messages[-1].get("content", "")
        
        return str(output)
    
    def _log_preserved_state_key(self, key: str, value: Any) -> None:
        """
        Log workflow-specific information about a preserved state key.
        
        Override in subclasses to add workflow-specific logging.
        
        Args:
            key: State key name
            value: State value that was preserved
        """
        # Base implementation does nothing - subclasses can override
        pass
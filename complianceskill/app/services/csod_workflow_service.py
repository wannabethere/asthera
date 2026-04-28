"""
CSOD Workflow Service

Service layer for CSOD (Cornerstone/Workday) workflow operations, providing a clean
abstraction for executing, managing, and monitoring CSOD metrics/KPIs workflows.
"""
import logging
import asyncio
from typing import Dict, Any, Optional, AsyncGenerator
from datetime import datetime

from app.agents.csod.csod_workflow import (
    create_csod_app,
    create_csod_initial_state,
    create_csod_interactive_app,
    create_csod_output_app,
)
from app.agents.csod.workflows.csod_main_graph import (
    create_csod_phase1_app,
)
from app.api.session_manager import (
    SessionManager,
    WorkflowType,
    SessionStatus,
    Checkpoint,
)
from app.api.state_transformer import (
    transform_to_external_state,
    extract_checkpoint_from_state,
)
from app.core.telemetry import (
    instrument_workflow_invocation,
    instrument_workflow_stream_events,
)
from app.services.workflow_stream_utils import maybe_llm_stream_event

logger = logging.getLogger(__name__)


def _slim_intent_output(raw):
    """Extract only display-relevant fields from csod_intent_classifier_output."""
    if not raw or not isinstance(raw, dict):
        return None
    return {
        "intent": raw.get("intent"),
        "confidence_score": raw.get("confidence_score"),
        "intent_signals": raw.get("intent_signals"),
        "persona": raw.get("persona"),
    }


def _slim_state_for_viz(state: dict) -> dict:
    """
    Extract only the fields the frontend pipeline visualization needs.

    Returns lightweight metadata (intent, persona, counts) for intermediate
    state_update events.  When recommendations are available (after the
    recommender runs), includes the FULL recommendation arrays so the
    frontend can pass them to the preview_generator endpoint.
    """
    causal_nodes_raw = state.get("csod_causal_nodes")
    if isinstance(causal_nodes_raw, dict):
        nodes_count = len(causal_nodes_raw.get("selected_nodes") or [])
        edges_count = len(causal_nodes_raw.get("selected_edges") or [])
    elif isinstance(causal_nodes_raw, list):
        nodes_count = len(causal_nodes_raw)
        edges_count = len(state.get("csod_causal_edges") or [])
    else:
        nodes_count = 0
        edges_count = 0
    result = {
        "csod_intent": state.get("csod_intent"),
        "csod_intent_confidence": state.get("csod_intent_confidence"),
        "csod_persona": state.get("csod_persona"),
        "csod_intent_classifier_output": _slim_intent_output(
            state.get("csod_intent_classifier_output")
        ),
        "csod_stage_1_intent": state.get("csod_stage_1_intent"),
        # Counts only — not full arrays (intermediate updates)
        "metrics_candidates": len(state.get("csod_metric_recommendations") or []),
        "kpi_candidates": len(state.get("csod_kpi_recommendations") or []),
        "table_candidates": len(state.get("csod_table_recommendations") or []),
        "dt_scored_metrics": len(state.get("dt_scored_metrics") or []),
        "nodes": nodes_count,
        "edges": edges_count,
        "focus_areas": state.get("csod_focus_areas"),
        "needs_mdl": state.get("csod_needs_mdl"),
        "needs_metrics": state.get("csod_needs_metrics"),
        "follow_up_eligible": state.get("csod_follow_up_eligible"),
    }

    # ── Full recommendation arrays for preview_generator endpoint ─────
    # Only included when recommender has produced output (avoids bloating
    # intermediate state_update events during retrieval / scoring stages).
    recs = state.get("csod_metric_recommendations") or []
    if recs:
        result["csod_metric_recommendations"] = recs
        result["csod_kpi_recommendations"] = state.get("csod_kpi_recommendations") or []
        result["csod_table_recommendations"] = state.get("csod_table_recommendations") or []
        result["csod_resolved_schemas"] = state.get("csod_resolved_schemas") or []
        result["csod_primary_area"] = state.get("csod_primary_area") or ""

    # ── Question rephraser output (direct analysis mode) ─────────────
    rephraser_output = state.get("csod_question_rephraser_output")
    if rephraser_output:
        result["csod_question_rephraser_output"] = rephraser_output
        result["csod_direct_analysis_mode"] = state.get("csod_direct_analysis_mode")

    # ── Adhoc/RCA NL queries (if adhoc path was taken) ────────────────
    adhoc_qs = state.get("csod_adhoc_nl_queries") or []
    if adhoc_qs:
        result["csod_adhoc_nl_queries"] = adhoc_qs

    # ── Data intelligence outputs (if data intel path was taken) ──────
    for key in ("csod_data_discovery_results", "csod_test_cases",
                "csod_data_lineage_results", "csod_data_quality_results"):
        val = state.get(key)
        if val:
            result[key] = val

    # ── Preview data and narration (Analysis Dashboard deliverables) ──
    previews = state.get("csod_metric_previews")
    if previews:
        result["csod"] = {
            "metric_previews": previews,
            "completion_narration": state.get("csod_completion_narration"),
        }
    return result


class CSODWorkflowService:
    """
    Service for managing CSOD workflow execution.

    Provides methods for:
    - Creating and initializing CSOD workflows
    - Executing workflows (streaming and non-streaming)
    - Resuming workflows from checkpoints
    - Managing workflow state and sessions
    """

    def __init__(self, session_manager: SessionManager):
        """
        Initialize the CSOD workflow service.

        Args:
            session_manager: Session manager instance for tracking workflow sessions
        """
        self.session_manager = session_manager
        self._csod_app = None
        self._csod_interactive_app = None  # Compiled with interrupt_after for human-in-the-loop
        self._csod_output_app = None  # Streamlined output/deploy pipeline
        self._interactive_sessions: set = set()  # session_ids started with interactive mode
        logger.info("CSODWorkflowService initialized")

    def get_workflow_app(self, dependencies: Optional[Dict[str, Any]] = None, interactive: bool = False):
        """
        Get or create the CSOD Phase 1 workflow app instance.

        Phase 1 is a planner-only graph ending at metric_selection → END.
        Previews are generated via a separate preview_generator endpoint.

        Args:
            dependencies: Optional dependencies dict (for future use)
            interactive: If True, returns the app compiled with interrupt_after for
                         human-in-the-loop checkpoints (csod_cross_concept_check, csod_metric_selection)

        Returns:
            Compiled LangGraph application for CSOD Phase 1 workflow
        """
        from app.core.checkpointer_provider import get_checkpointer
        from app.agents.csod.workflows.csod_main_graph import build_csod_phase1_workflow

        if interactive:
            if self._csod_interactive_app is None:
                self._csod_interactive_app = build_csod_phase1_workflow().compile(
                    checkpointer=get_checkpointer(),
                    interrupt_after=[
                        "csod_analysis_mode_selector",
                        "csod_cross_concept_check",
                        "csod_metric_selection",
                    ],
                )
                logger.info("CSOD Phase 1 interactive app created (interrupt_after enabled)")
            return self._csod_interactive_app
        if self._csod_app is None:
            self._csod_app = create_csod_phase1_app()
            logger.info("CSOD Phase 1 workflow app created successfully")
        return self._csod_app

    def create_initial_state(
        self,
        user_query: str,
        session_id: str,
        active_project_id: Optional[str] = None,
        selected_data_sources: Optional[list] = None,
        compliance_profile: Optional[dict] = None,
        silver_gold_tables_only: bool = False,
        generate_sql: bool = False,
        **additional_state: Any,
    ) -> Dict[str, Any]:
        """
        Create initial state for CSOD workflow execution.

        Args:
            user_query: User's natural language query
            session_id: Unique session identifier
            active_project_id: Project ID for GoldStandardTable lookup
            selected_data_sources: List of data source IDs (e.g., ["cornerstone", "workday"])
            compliance_profile: Full compliance profile dict
            silver_gold_tables_only: Skip source/bronze tables
            generate_sql: Generate SQL for gold models
            **additional_state: Additional state fields to merge

        Returns:
            Initial state dict ready for workflow execution
        """
        initial_state = create_csod_initial_state(
            user_query=user_query,
            session_id=session_id,
            active_project_id=active_project_id,
            selected_data_sources=selected_data_sources or [],
            compliance_profile=compliance_profile or {},
            silver_gold_tables_only=silver_gold_tables_only,
            generate_sql=generate_sql,
        )
        hitl_reasoning_patch = (
            additional_state.get("csod_reasoning_hitl_patch")
            if isinstance(additional_state, dict)
            else None
        )
        initial_state.update(additional_state)
        prior = additional_state.get("prior_csod_state") if additional_state else None
        if isinstance(prior, dict):
            for k in (
                "dt_scored_metrics",
                "dt_metric_groups",
                "dt_metric_decisions",
                "csod_resolved_schemas",
                "csod_intent",
                "csod_causal_edges",
                "csod_causal_nodes",
                "csod_causal_centrality",
                "csod_causal_graph_result",
                "csod_metric_recommendations",
                "csod_reasoning_trace",
            ):
                if prior.get(k) is not None:
                    initial_state[k] = prior[k]
        if additional_state and additional_state.get("csod_session_turn") is not None:
            initial_state["csod_session_turn"] = int(additional_state["csod_session_turn"])
        initial_state.pop("prior_csod_state", None)
        initial_state.pop("csod_reasoning_hitl_patch", None)
        if isinstance(hitl_reasoning_patch, dict):
            try:
                from app.agents.csod.reasoning_trace import apply_hitl_patch

                apply_hitl_patch(initial_state, hitl_reasoning_patch)
            except Exception:
                logger.exception("apply_hitl_patch failed for csod_reasoning_hitl_patch")
        return initial_state

    async def execute_workflow_stream(
        self,
        user_query: str,
        session_id: str,
        initial_state_data: Optional[Dict[str, Any]] = None,
        dependencies: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute CSOD workflow with streaming response.

        Args:
            user_query: User's natural language query
            session_id: Unique session identifier
            initial_state_data: Additional initial state fields
            dependencies: Optional dependencies dict

        Yields:
            Event dictionaries with workflow execution updates
        """
        initial_state_data = initial_state_data or {}

        session = self.session_manager.create_session(
            session_id=session_id,
            workflow_type=WorkflowType.CSOD,
            user_query=user_query,
        )

        initial_state = self.create_initial_state(
            user_query=user_query,
            session_id=session_id,
            active_project_id=initial_state_data.get("active_project_id"),
            selected_data_sources=initial_state_data.get("selected_data_sources"),
            compliance_profile=initial_state_data.get("compliance_profile"),
            silver_gold_tables_only=initial_state_data.get("silver_gold_tables_only", False),
            generate_sql=initial_state_data.get("generate_sql", False),
            **{
                k: v for k, v in initial_state_data.items()
                if k not in [
                    "active_project_id", "selected_data_sources", "compliance_profile",
                    "silver_gold_tables_only", "generate_sql",
                ]
            },
        )

        # Use interactive app (interrupt_after on checkpoint nodes) when requested
        interactive = bool(initial_state_data.get("csod_interactive_checkpoints"))
        if interactive:
            self._interactive_sessions.add(session_id)
        workflow_app = self.get_workflow_app(dependencies=dependencies, interactive=interactive)

        # Nodes the interactive app actually interrupts at (must match interrupt_after list).
        # Only these nodes should trigger a checkpoint SSE event; earlier nodes that also
        # set csod_conversation_checkpoint (e.g. concept-detect CCE nodes) are bypassed by
        # the interrupt_after compilation — we must NOT break the stream for them.
        _INTERRUPT_NODES = frozenset({
            "csod_analysis_mode_selector",
            "csod_cross_concept_check",
            "csod_metric_selection",
        }) if interactive else frozenset()
        config = {"configurable": {"thread_id": session.thread_id}}

        self.session_manager.update_session_status(session_id, SessionStatus.RUNNING)

        yield {
            "event": "workflow_start",
            "data": {
                "session_id": session_id,
                "workflow_type": "csod",
                "user_query": user_query,
                "status": SessionStatus.RUNNING.value,
            },
        }

        checkpoint_reached = False
        final_state = None
        # Track narrative stream index so we only emit *new* entries as message_delta
        last_narrative_idx = 0

        # run_input is initial_state on first pass; None on auto-resume passes
        # (LangGraph resumes from an interrupt when initial_state=None)
        run_input = initial_state
        _MAX_AUTO_RESUMES = 5   # safety guard

        try:
          for _auto_pass in range(_MAX_AUTO_RESUMES + 1):
            _found_cp_this_pass = False
            async for event in instrument_workflow_stream_events(
                workflow_app,
                run_input,
                config=config,
                workflow_name="csod",
                version="v2",
            ):
                event_kind = event.get("event")
                event_name = event.get("name", "")
                run_id = event.get("run_id", "")

                # Forward LLM streaming events for constant updates
                llm_ev = maybe_llm_stream_event(event, session_id)
                if llm_ev:
                    yield llm_ev

                if event_kind == "on_chain_start":
                    self.session_manager.add_node(
                        session_id=session_id,
                        node_id=run_id,
                        node_name=event_name,
                        status="running",
                    )
                    yield {
                        "event": "node_start",
                        "data": {
                            "session_id": session_id,
                            "node": event_name,
                            "node_id": run_id,
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    }

                elif event_kind == "on_chain_end":
                    self.session_manager.add_node(
                        session_id=session_id,
                        node_id=run_id,
                        node_name=event_name,
                        status="completed",
                    )

                    try:
                        current_state_snapshot = workflow_app.get_state(config)
                        if current_state_snapshot and current_state_snapshot.values:
                            current_state = current_state_snapshot.values
                            final_state = current_state

                            external_state = transform_to_external_state(
                                current_state,
                                workflow_type="csod",
                            )
                            self.session_manager.update_external_state(
                                session_id=session_id,
                                external_state=external_state,
                            )

                            # ── Emit new narrative stream entries as message_delta ──
                            # These appear in the chat bubble as plain-English updates
                            # instead of raw JSON state blobs.
                            narrative_stream = current_state.get("csod_narrative_stream") or []
                            if len(narrative_stream) > last_narrative_idx:
                                for entry in narrative_stream[last_narrative_idx:]:
                                    msg = entry.get("message", "")
                                    title = entry.get("title", "")
                                    text = f"**{title}**\n{msg}" if title and msg else (msg or title or "")
                                    if text.strip():
                                        yield {
                                            "event": "message_delta",
                                            "data": {
                                                "session_id": session_id,
                                                "content": text + "\n\n",
                                                "node": event_name,
                                            },
                                        }
                                last_narrative_idx = len(narrative_stream)

                            # ── Slim state_update for pipeline viz only (no full JSON) ──
                            yield {
                                "event": "state_update",
                                "data": {
                                    "session_id": session_id,
                                    "node": event_name,
                                    "state": _slim_state_for_viz(current_state),
                                },
                            }

                            # Only check for checkpoint at nodes the interactive app
                            # actually interrupts at.  Earlier nodes (CCE, concept-detect)
                            # may also write csod_conversation_checkpoint but LangGraph
                            # does NOT pause there — breaking early would desync state.
                            should_check_cp = (
                                not _INTERRUPT_NODES
                                or event_name in _INTERRUPT_NODES
                            )
                            # Debug: log checkpoint extraction attempt
                            _cp_raw = current_state.get("csod_conversation_checkpoint")
                            _cp_resolved = current_state.get("csod_checkpoint_resolved")
                            logger.info(
                                "[CSOD-CP-DEBUG] node=%s should_check=%s "
                                "has_cp=%s cp_resolved=%s cp_phase=%s",
                                event_name, should_check_cp,
                                _cp_raw is not None, _cp_resolved,
                                (_cp_raw or {}).get("phase") if isinstance(_cp_raw, dict) else None,
                            )
                            checkpoint_data = (
                                extract_checkpoint_from_state(current_state, event_name)
                                if should_check_cp else None
                            )
                            logger.info(
                                "[CSOD-CP-DEBUG] extract result: %s",
                                checkpoint_data.get("checkpoint_type") if checkpoint_data else None,
                            )
                            if checkpoint_data:
                                checkpoint = Checkpoint(
                                    checkpoint_id=checkpoint_data["checkpoint_id"],
                                    checkpoint_type=checkpoint_data["checkpoint_type"],
                                    node=checkpoint_data["node"],
                                    data=checkpoint_data["data"],
                                    message=checkpoint_data["message"],
                                    requires_user_input=checkpoint_data["requires_user_input"],
                                )
                                self.session_manager.add_checkpoint(
                                    session_id=session_id,
                                    checkpoint=checkpoint,
                                )
                                checkpoint_reached = True
                                _found_cp_this_pass = True
                                yield {
                                    "event": "checkpoint",
                                    "data": {
                                        "session_id": session_id,
                                        "checkpoint_id": checkpoint.checkpoint_id,
                                        "checkpoint_type": checkpoint.checkpoint_type,
                                        "node": checkpoint.node,
                                        "data": checkpoint.data,
                                        "message": checkpoint.message,
                                        "requires_user_input": checkpoint.requires_user_input,
                                    },
                                }
                                session = self.session_manager.get_session(session_id)
                                yield {
                                    "event": "session_update",
                                    "data": {
                                        "session_id": session_id,
                                        "session": session.to_dict(),
                                    },
                                }
                                break
                    except Exception as e:
                        logger.warning(f"Could not get state from checkpointer: {e}", exc_info=True)

                    yield {
                        "event": "node_complete",
                        "data": {
                            "session_id": session_id,
                            "node": event_name,
                            "node_id": run_id,
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    }

                elif event_kind == "on_chain_error":
                    error_data = event.get("data", {})
                    error_msg = str(error_data.get("error", "Unknown error"))
                    self.session_manager.add_node(
                        session_id=session_id,
                        node_id=run_id,
                        node_name=event_name,
                        status="failed",
                    )
                    self.session_manager.update_session_status(
                        session_id=session_id,
                        status=SessionStatus.FAILED,
                        error=error_msg,
                    )
                    yield {
                        "event": "error",
                        "data": {
                            "session_id": session_id,
                            "node": event_name,
                            "error": error_msg,
                            "error_type": error_data.get("error_type", "Unknown"),
                        },
                    }

            # ── After each inner async-for pass ──────────────────────────────
            if _found_cp_this_pass:
                # A user-facing checkpoint was emitted — stop and wait for response
                break  # exits the outer for _auto_pass loop

            # No checkpoint found this pass.  Check whether LangGraph paused at
            # an interrupt node that auto-confirmed without needing user input
            # (e.g. csod_metric_selection when csod_metric_recommendations is
            # empty) but there are still pending nodes to run (e.g. csod_goal_intent).
            try:
                _snap = workflow_app.get_state(config)
                _pending = list(_snap.next) if (_snap and _snap.next) else []
            except Exception:
                _pending = []

            if not _pending:
                # Workflow truly finished — fall through to workflow_complete below
                break

            if _auto_pass >= _MAX_AUTO_RESUMES:
                logger.warning(
                    "[CSOD] Reached auto-resume limit (%d) — treating as complete",
                    _MAX_AUTO_RESUMES,
                )
                break

            logger.info(
                "[CSOD] Auto-resuming from interrupt (no user checkpoint) — pending: %s",
                _pending,
            )
            run_input = None   # pass None so LangGraph resumes from interrupt point

          # ── End of outer auto-resume for loop ────────────────────────────
          if not checkpoint_reached:
                if final_state:
                    external_state = transform_to_external_state(
                        final_state,
                        workflow_type="csod",
                    )
                    self.session_manager.update_external_state(
                        session_id=session_id,
                        external_state=external_state,
                    )

                # ── Preview generation removed from service ──────────────
                # Previews are now rendered lazily by the frontend.
                # The workflow_complete event carries recommendations;
                # the frontend renders placeholder cards, then fetches
                # each preview individually via /workflow/preview_item.

                self.session_manager.update_session_status(
                    session_id=session_id,
                    status=SessionStatus.COMPLETED,
                )
                session = self.session_manager.get_session(session_id)
                yield {
                    "event": "workflow_complete",
                    "data": {
                        "session_id": session_id,
                        "session": session.to_dict(),
                    },
                }

        except Exception as e:
            logger.error(f"CSOD workflow execution error: {e}", exc_info=True)
            self.session_manager.update_session_status(
                session_id=session_id,
                status=SessionStatus.FAILED,
                error=str(e),
            )
            yield {
                "event": "error",
                "data": {
                    "error": str(e),
                    "session_id": session_id,
                },
            }

    async def execute_workflow_invoke(
        self,
        user_query: str,
        session_id: str,
        initial_state_data: Optional[Dict[str, Any]] = None,
        dependencies: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute CSOD workflow synchronously (non-streaming).
        """
        initial_state_data = initial_state_data or {}

        session = self.session_manager.create_session(
            session_id=session_id,
            workflow_type=WorkflowType.CSOD,
            user_query=user_query,
        )

        initial_state = self.create_initial_state(
            user_query=user_query,
            session_id=session_id,
            active_project_id=initial_state_data.get("active_project_id"),
            selected_data_sources=initial_state_data.get("selected_data_sources"),
            compliance_profile=initial_state_data.get("compliance_profile"),
            silver_gold_tables_only=initial_state_data.get("silver_gold_tables_only", False),
            generate_sql=initial_state_data.get("generate_sql", False),
            **{
                k: v for k, v in initial_state_data.items()
                if k not in [
                    "active_project_id", "selected_data_sources", "compliance_profile",
                    "silver_gold_tables_only", "generate_sql",
                ]
            },
        )

        workflow_app = self.get_workflow_app(dependencies=dependencies)
        config = {"configurable": {"thread_id": session.thread_id}}

        self.session_manager.update_session_status(session_id, SessionStatus.RUNNING)

        loop = asyncio.get_event_loop()
        workflow_result = await loop.run_in_executor(
            None,
            lambda: instrument_workflow_invocation(
                workflow_app,
                initial_state,
                config=config,
                workflow_name="csod",
            ),
        )

        external_state = transform_to_external_state(
            workflow_result,
            workflow_type="csod",
        )
        self.session_manager.update_external_state(session_id, external_state)
        self.session_manager.update_session_status(session_id, SessionStatus.COMPLETED)

        session = self.session_manager.get_session(session_id)
        return {
            "session_id": session_id,
            "session": session.to_dict(),
        }

    async def resume_workflow_stream(
        self,
        session_id: str,
        checkpoint_id: str,
        user_input: Dict[str, Any],
        approved: bool = True,
        dependencies: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Resume CSOD workflow execution from a checkpoint.
        """
        session = self.session_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        if session.status != SessionStatus.CHECKPOINT:
            raise ValueError(
                f"Session {session_id} is not at a checkpoint (current status: {session.status.value})"
            )

        self.session_manager.resolve_checkpoint(
            session_id=session_id,
            checkpoint_id=checkpoint_id,
            user_input=user_input,
            approved=approved,
        )

        # Sessions that reached a checkpoint via the interactive app must use the
        # same app instance (same MemorySaver) for state consistency on resume.
        interactive = session_id in self._interactive_sessions
        workflow_app = self.get_workflow_app(dependencies=dependencies, interactive=interactive)
        config = {"configurable": {"thread_id": session.thread_id}}

        try:
            last_state_snapshot = workflow_app.get_state(config)
            if not last_state_snapshot or not last_state_snapshot.values:
                raise ValueError("No checkpoint state found for this session")
            current_state = last_state_snapshot.values.copy()
            current_state["user_checkpoint_input"] = user_input

            # Inject user selections at the correct state key so checkpoint nodes
            # can read them on resume.  The resume_with_field tells us which key to set.
            resume_field = user_input.get("resume_with_field")
            if resume_field and resume_field in user_input:
                current_state[resume_field] = user_input[resume_field]
                logger.info("Injected resume_with_field '%s' into state: %s", resume_field, user_input[resume_field])
            # Also handle well-known fields forwarded from the asthera checkpoint endpoint
            for known_field in (
                "csod_selected_metric_ids",
                "csod_metrics_user_confirmed",
                "goal_intent",
                "csod_confirmed_concept_ids",
                "csod_concepts_confirmed",
                "csod_selected_datasources",
                "csod_datasource_confirmed",
                "csod_cross_concept_confirmed",
                "csod_analysis_mode_selection",
                "csod_direct_analysis_mode",
            ):
                if known_field in user_input:
                    current_state[known_field] = user_input[known_field]
            # Mark the conversation checkpoint as resolved so it doesn't re-trigger
            current_state["csod_checkpoint_resolved"] = True

            if "checkpoints" in current_state:
                for checkpoint in current_state["checkpoints"]:
                    if isinstance(checkpoint, dict) and checkpoint.get("node") == checkpoint_id:
                        checkpoint["status"] = "approved" if approved else "rejected"
                        checkpoint["user_input"] = user_input
                        break
            workflow_app.update_state(config, current_state)
        except AttributeError:
            raise ValueError("Checkpoint state retrieval not supported with current checkpointer")
        except Exception as e:
            raise ValueError(f"Cannot resume: {str(e)}")

        self.session_manager.update_session_status(session_id, SessionStatus.RUNNING)

        yield {
            "event": "workflow_resumed",
            "data": {
                "session_id": session_id,
                "checkpoint_id": checkpoint_id,
                "message": "Resuming CSOD workflow from checkpoint",
            },
        }

        checkpoint_reached = False
        final_state = None

        try:
            # For interrupt-based resume (interactive mode), pass None so LangGraph
            # resumes from the interrupt point using the state saved in MemorySaver.
            # For non-interactive legacy resume, pass the updated state.
            resume_input = None if interactive else current_state

            async for event in instrument_workflow_stream_events(
                workflow_app,
                resume_input,
                config=config,
                workflow_name="csod",
                version="v2",
            ):
                event_kind = event.get("event")
                event_name = event.get("name", "")
                run_id = event.get("run_id", "")

                # Forward LLM streaming events for constant updates
                llm_ev = maybe_llm_stream_event(event, session_id)
                if llm_ev:
                    yield llm_ev

                if event_kind == "on_chain_start":
                    self.session_manager.add_node(
                        session_id=session_id,
                        node_id=run_id,
                        node_name=event_name,
                        status="running",
                    )
                    yield {
                        "event": "node_start",
                        "data": {
                            "session_id": session_id,
                            "node": event_name,
                            "node_id": run_id,
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    }

                elif event_kind == "on_chain_end":
                    self.session_manager.add_node(
                        session_id=session_id,
                        node_id=run_id,
                        node_name=event_name,
                        status="completed",
                    )
                    try:
                        current_state_snapshot = workflow_app.get_state(config)
                        if current_state_snapshot and current_state_snapshot.values:
                            current_state = current_state_snapshot.values
                            final_state = current_state
                            external_state = transform_to_external_state(
                                current_state,
                                workflow_type="csod",
                            )
                            self.session_manager.update_external_state(
                                session_id=session_id,
                                external_state=external_state,
                            )
                            yield {
                                "event": "state_update",
                                "data": {
                                    "session_id": session_id,
                                    "node": event_name,
                                    "state": external_state,
                                },
                            }
                            # On resume, always check only the interrupt nodes
                            _resume_interrupt_nodes = frozenset({
                                "csod_analysis_mode_selector",
                                "csod_cross_concept_check",
                                "csod_metric_selection",
                                "csod_goal_intent",
                            }) if interactive else frozenset()
                            should_check_cp = (
                                not _resume_interrupt_nodes
                                or event_name in _resume_interrupt_nodes
                            )
                            checkpoint_data = (
                                extract_checkpoint_from_state(current_state, event_name)
                                if should_check_cp else None
                            )
                            if checkpoint_data:
                                checkpoint = Checkpoint(
                                    checkpoint_id=checkpoint_data["checkpoint_id"],
                                    checkpoint_type=checkpoint_data["checkpoint_type"],
                                    node=checkpoint_data["node"],
                                    data=checkpoint_data["data"],
                                    message=checkpoint_data["message"],
                                    requires_user_input=checkpoint_data["requires_user_input"],
                                )
                                self.session_manager.add_checkpoint(
                                    session_id=session_id,
                                    checkpoint=checkpoint,
                                )
                                checkpoint_reached = True
                                yield {
                                    "event": "checkpoint",
                                    "data": {
                                        "session_id": session_id,
                                        "checkpoint_id": checkpoint.checkpoint_id,
                                        "checkpoint_type": checkpoint.checkpoint_type,
                                        "node": checkpoint.node,
                                        "data": checkpoint.data,
                                        "message": checkpoint.message,
                                        "requires_user_input": checkpoint.requires_user_input,
                                    },
                                }
                                session = self.session_manager.get_session(session_id)
                                yield {
                                    "event": "session_update",
                                    "data": {
                                        "session_id": session_id,
                                        "session": session.to_dict(),
                                    },
                                }
                                break
                    except Exception as e:
                        logger.warning(f"Could not get state from checkpointer: {e}", exc_info=True)

                    yield {
                        "event": "node_complete",
                        "data": {
                            "session_id": session_id,
                            "node": event_name,
                            "node_id": run_id,
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    }

                elif event_kind == "on_chain_error":
                    error_data = event.get("data", {})
                    error_msg = str(error_data.get("error", "Unknown error"))
                    self.session_manager.add_node(
                        session_id=session_id,
                        node_id=run_id,
                        node_name=event_name,
                        status="failed",
                    )
                    self.session_manager.update_session_status(
                        session_id=session_id,
                        status=SessionStatus.FAILED,
                        error=error_msg,
                    )
                    yield {
                        "event": "error",
                        "data": {
                            "session_id": session_id,
                            "node": event_name,
                            "error": error_msg,
                            "error_type": error_data.get("error_type", "Unknown"),
                        },
                    }

            if not checkpoint_reached:
                if final_state:
                    external_state = transform_to_external_state(
                        final_state,
                        workflow_type="csod",
                    )
                    self.session_manager.update_external_state(
                        session_id=session_id,
                        external_state=external_state,
                    )
                self.session_manager.update_session_status(
                    session_id=session_id,
                    status=SessionStatus.COMPLETED,
                )
                session = self.session_manager.get_session(session_id)
                yield {
                    "event": "workflow_complete",
                    "data": {
                        "session_id": session_id,
                        "session": session.to_dict(),
                    },
                }

        except Exception as e:
            logger.error(f"CSOD workflow resume error: {e}", exc_info=True)
            self.session_manager.update_session_status(
                session_id=session_id,
                status=SessionStatus.FAILED,
                error=str(e),
            )
            yield {
                "event": "error",
                "data": {
                    "error": str(e),
                    "session_id": session_id,
                },
            }


    # ──────────────────────────────────────────────────────────────────────
    # OUTPUT GRAPH (deploy-time pipeline)
    # ──────────────────────────────────────────────────────────────────────

    def get_output_workflow_app(self):
        """Get or create the CSOD output (deploy) workflow app."""
        if self._csod_output_app is None:
            self._csod_output_app = create_csod_output_app()
            logger.info("CSOD output workflow app created")
        return self._csod_output_app

    async def execute_output_workflow_stream(
        self,
        session_id: str,
        phase1_state: Dict[str, Any],
        deploy_payload: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute the output/deploy pipeline using Phase 1 final state.

        Args:
            session_id: Session identifier (reuse from Phase 1 or new)
            phase1_state: Complete state from Phase 1 (metrics, schemas, selections)
            deploy_payload: Deploy-time overrides (goal_intent, etc.)

        Yields:
            Event dicts with workflow execution updates
        """
        deploy_payload = deploy_payload or {}

        try:
            session = self.session_manager.create_session(
                session_id=session_id,
                workflow_type=WorkflowType.CSOD,
                user_query=phase1_state.get("user_query", ""),
            )

            workflow_app = self.get_output_workflow_app()

            # Merge deploy-time overrides into Phase 1 state
            output_state = dict(phase1_state)
            if deploy_payload.get("goal_intent"):
                output_state["goal_intent"] = deploy_payload["goal_intent"]
            for key in ("goal_output_intents", "csod_generate_sql"):
                if key in deploy_payload:
                    output_state[key] = deploy_payload[key]

            config = {"configurable": {"thread_id": session_id}}

            yield {
                "event": "workflow_start",
                "data": {
                    "session_id": session_id,
                    "workflow_type": "csod_output",
                },
            }

            async for event in workflow_app.astream_events(
                output_state, config=config, version="v2"
            ):
                kind = event.get("event", "")

                if kind == "on_chain_start":
                    node_name = event.get("name", "")
                    if node_name and node_name != "LangGraph":
                        yield {
                            "event": "node_start",
                            "data": {"node": node_name, "session_id": session_id},
                        }

                elif kind == "on_chain_end":
                    node_name = event.get("name", "")
                    run_output = event.get("data", {}).get("output", {})
                    if node_name and node_name != "LangGraph" and isinstance(run_output, dict):
                        checkpoint_data = extract_checkpoint_from_state(run_output)
                        if checkpoint_data:
                            self.session_manager.update_session_status(
                                session_id=session_id,
                                status=SessionStatus.CHECKPOINT,
                            )
                            yield {
                                "event": "checkpoint",
                                "data": {
                                    "session_id": session_id,
                                    "checkpoint": checkpoint_data,
                                },
                            }
                        yield {
                            "event": "node_complete",
                            "data": {"node": node_name, "session_id": session_id},
                        }

                llm_event = maybe_llm_stream_event(event, session_id)
                if llm_event:
                    yield llm_event

            # Workflow complete
            self.session_manager.update_session_status(
                session_id=session_id,
                status=SessionStatus.COMPLETED,
            )
            session = self.session_manager.get_session(session_id)
            yield {
                "event": "workflow_complete",
                "data": {
                    "session_id": session_id,
                    "session": session.to_dict(),
                },
            }

        except Exception as e:
            logger.error(f"CSOD output workflow error: {e}", exc_info=True)
            self.session_manager.update_session_status(
                session_id=session_id,
                status=SessionStatus.FAILED,
                error=str(e),
            )
            yield {
                "event": "error",
                "data": {"error": str(e), "session_id": session_id},
            }


    # ──────────────────────────────────────────────────────────────────────
    # PREVIEW GENERATOR — called by frontend after Phase 1 completes
    # ──────────────────────────────────────────────────────────────────────

    async def execute_preview_generator_stream(
        self,
        session_id: str,
        preview_input: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generate metric previews from Phase 1 output, streaming each preview
        back via SSE as soon as it is ready.

        Only extracts the fields the preview generator actually needs from
        ``preview_input`` — avoids copying the entire Phase 1 state.

        Args:
            session_id: Session ID from Phase 1
            preview_input: Dict with keys from Phase 1 final state
        """
        from app.agents.csod.csod_nodes.node_sql_agent import generate_previews_stream

        yield {
            "event": "preview_start",
            "data": {"session_id": session_id},
        }

        try:
            # Extract only the fields the preview generator reads
            metrics = preview_input.get("csod_metric_recommendations") or []
            kpis = preview_input.get("csod_kpi_recommendations") or []
            tables = preview_input.get("csod_table_recommendations") or []
            intent = preview_input.get("csod_intent") or ""
            primary_focus_area = preview_input.get("csod_primary_area") or ""

            all_previews: list = []

            async for preview in generate_previews_stream(
                metrics=metrics,
                kpis=kpis,
                tables=tables,
                intent=intent,
                primary_focus_area=primary_focus_area,
            ):
                all_previews.append(preview)
                yield {
                    "event": "preview_item",
                    "data": {
                        "session_id": session_id,
                        "preview": preview,
                        "index": len(all_previews) - 1,
                    },
                }

            logger.info(
                "Preview generator produced %d previews for session %s",
                len(all_previews), session_id,
            )

            # Backward-compatible bulk state_update with full list
            yield {
                "event": "state_update",
                "data": {
                    "session_id": session_id,
                    "node": "preview_generator",
                    "state": {
                        "csod": {
                            "metric_previews": all_previews,
                        },
                    },
                },
            }

            yield {
                "event": "preview_complete",
                "data": {
                    "session_id": session_id,
                    "preview_count": len(all_previews),
                },
            }

        except Exception as e:
            logger.error(f"Preview generator failed: {e}", exc_info=True)
            yield {
                "event": "error",
                "data": {"error": str(e), "session_id": session_id},
            }


_csod_workflow_service = None


def get_csod_workflow_service(session_manager=None) -> CSODWorkflowService:
    """
    Get the global CSOD workflow service instance.
    """
    global _csod_workflow_service
    if _csod_workflow_service is None:
        from app.api.session_manager import get_session_manager
        session_manager = session_manager or get_session_manager()
        _csod_workflow_service = CSODWorkflowService(session_manager)
    return _csod_workflow_service

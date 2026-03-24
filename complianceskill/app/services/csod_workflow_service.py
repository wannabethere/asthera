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
        logger.info("CSODWorkflowService initialized")

    def get_workflow_app(self, dependencies: Optional[Dict[str, Any]] = None):
        """
        Get or create the CSOD workflow app instance.

        Args:
            dependencies: Optional dependencies dict (for future use)

        Returns:
            Compiled LangGraph application for CSOD workflow
        """
        if self._csod_app is None:
            self._csod_app = create_csod_app()
            logger.info("CSOD workflow app created successfully")
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

        workflow_app = self.get_workflow_app(dependencies=dependencies)
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

        try:
            async for event in instrument_workflow_stream_events(
                workflow_app,
                initial_state,
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

                            checkpoint_data = extract_checkpoint_from_state(
                                current_state,
                                event_name,
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

        workflow_app = self.get_workflow_app(dependencies=dependencies)
        config = {"configurable": {"thread_id": session.thread_id}}

        try:
            last_state_snapshot = workflow_app.get_state(config)
            if not last_state_snapshot or not last_state_snapshot.values:
                raise ValueError("No checkpoint state found for this session")
            current_state = last_state_snapshot.values.copy()
            current_state["user_checkpoint_input"] = user_input
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
            async for event in instrument_workflow_stream_events(
                workflow_app,
                current_state,
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
                            checkpoint_data = extract_checkpoint_from_state(
                                current_state,
                                event_name,
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

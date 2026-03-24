"""
Detection & Triage Workflow Service

Service layer for DT workflow operations, providing a clean abstraction
for executing, managing, and monitoring DT workflows.
"""
import logging
import asyncio
from typing import Dict, Any, Optional, AsyncGenerator
from datetime import datetime

from app.agents.mdlworkflows.dt_workflow import (
    create_detection_triage_app,
    create_dt_initial_state,
)
from app.agents.state import EnhancedCompliancePipelineState
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


class DTWorkflowService:
    """
    Service for managing Detection & Triage workflow execution.
    
    Provides methods for:
    - Creating and initializing DT workflows
    - Executing workflows (streaming and non-streaming)
    - Resuming workflows from checkpoints
    - Managing workflow state and sessions
    """
    
    def __init__(self, session_manager: SessionManager):
        """
        Initialize the DT workflow service.
        
        Args:
            session_manager: Session manager instance for tracking workflow sessions
        """
        self.session_manager = session_manager
        self._dt_app = None
        logger.info("DTWorkflowService initialized")
    
    def get_workflow_app(self):
        """
        Get or create the DT workflow app instance.
        
        Returns:
            Compiled LangGraph application for DT workflow
        """
        if self._dt_app is None:
            self._dt_app = create_detection_triage_app()
            logger.info("DT workflow app created successfully")
        return self._dt_app
    
    def create_initial_state(
        self,
        user_query: str,
        session_id: str,
        framework_id: Optional[str] = None,
        selected_data_sources: Optional[list] = None,
        active_project_id: Optional[str] = None,
        compliance_profile: Optional[dict] = None,
        **additional_state: Any,
    ) -> EnhancedCompliancePipelineState:
        """
        Create initial state for DT workflow execution.
        
        Args:
            user_query: User's natural language query
            session_id: Unique session identifier
            framework_id: Optional framework override
            selected_data_sources: List of data source IDs
            active_project_id: Project ID for GoldStandardTable lookup
            compliance_profile: Full compliance profile dict
            **additional_state: Additional state fields to merge
        
        Returns:
            Initial state dictionary ready for workflow execution
        """
        initial_state = create_dt_initial_state(
            user_query=user_query,
            session_id=session_id,
            framework_id=framework_id,
            selected_data_sources=selected_data_sources or [],
            active_project_id=active_project_id,
            compliance_profile=compliance_profile,
        )

        hitl_reasoning_patch = (
            additional_state.get("dt_reasoning_hitl_patch")
            if isinstance(additional_state, dict)
            else None
        )

        # Merge any additional state fields
        initial_state.update(additional_state)

        prior = additional_state.get("prior_dt_state") if isinstance(additional_state, dict) else None
        if isinstance(prior, dict) and prior.get("dt_reasoning_trace") is not None:
            initial_state["dt_reasoning_trace"] = prior["dt_reasoning_trace"]

        initial_state.pop("prior_dt_state", None)
        initial_state.pop("dt_reasoning_hitl_patch", None)

        if isinstance(hitl_reasoning_patch, dict):
            try:
                from app.agents.mdlworkflows.dt_reasoning_trace import apply_dt_hitl_patch

                apply_dt_hitl_patch(initial_state, hitl_reasoning_patch)
            except Exception:
                logger.exception("apply_dt_hitl_patch failed for dt_reasoning_hitl_patch")

        return initial_state
    
    async def execute_workflow_stream(
        self,
        user_query: str,
        session_id: str,
        initial_state_data: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute DT workflow with streaming response.
        
        Args:
            user_query: User's natural language query
            session_id: Unique session identifier
            initial_state_data: Additional initial state fields
        
        Yields:
            Event dictionaries with workflow execution updates
        """
        initial_state_data = initial_state_data or {}
        
        # Create session
        session = self.session_manager.create_session(
            session_id=session_id,
            workflow_type=WorkflowType.DETECTION_TRIAGE,
            user_query=user_query,
        )
        
        # Create initial state
        initial_state = self.create_initial_state(
            user_query=user_query,
            session_id=session_id,
            framework_id=initial_state_data.get("framework_id"),
            selected_data_sources=initial_state_data.get("selected_data_sources"),
            active_project_id=initial_state_data.get("active_project_id"),
            compliance_profile=initial_state_data.get("compliance_profile"),
            **{
                k: v for k, v in initial_state_data.items()
                if k not in ["framework_id", "selected_data_sources", "active_project_id", "compliance_profile"]
            }
        )
        
        # Get workflow app
        workflow_app = self.get_workflow_app()
        config = {"configurable": {"thread_id": session.thread_id}}
        
        # Update session status
        self.session_manager.update_session_status(session_id, SessionStatus.RUNNING)
        
        # Yield workflow start event
        workflow_start_event = {
            "event": "workflow_start",
            "data": {
                "session_id": session_id,
                "workflow_type": "detection_triage",
                "user_query": user_query,
                "status": SessionStatus.RUNNING.value,
            }
        }
        logger.info(f"[DT_WORKFLOW] Yielding event: workflow_start for session {session_id}")
        yield workflow_start_event
        
        checkpoint_reached = False
        final_state = None
        
        try:
            # Stream workflow execution
            async for event in instrument_workflow_stream_events(
                workflow_app,
                initial_state,
                config=config,
                workflow_name="detection_triage",
                version="v2"
            ):
                event_kind = event.get("event")
                event_name = event.get("name", "")
                run_id = event.get("run_id", "")

                # Forward LLM streaming events for constant updates
                llm_ev = maybe_llm_stream_event(event, session_id)
                if llm_ev:
                    yield llm_ev

                # Handle node start events
                if event_kind == "on_chain_start":
                    self.session_manager.add_node(
                        session_id=session_id,
                        node_id=run_id,
                        node_name=event_name,
                        status="running",
                    )
                    
                    node_start_event = {
                        "event": "node_start",
                        "data": {
                            "session_id": session_id,
                            "node": event_name,
                            "node_id": run_id,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    }
                    logger.info(f"[DT_WORKFLOW] Yielding event: node_start - node={event_name}, node_id={run_id}, session_id={session_id}")
                    yield node_start_event
                
                # Handle node end events
                elif event_kind == "on_chain_end":
                    logger.info(f"Node {event_name} completed")
                    
                    # Update node status
                    self.session_manager.add_node(
                        session_id=session_id,
                        node_id=run_id,
                        node_name=event_name,
                        status="completed",
                    )
                    
                    # Get current state from checkpointer
                    try:
                        current_state_snapshot = workflow_app.get_state(config)
                        if current_state_snapshot and current_state_snapshot.values:
                            current_state = current_state_snapshot.values
                            final_state = current_state
                            
                            # Transform to external state
                            external_state = transform_to_external_state(
                                current_state,
                                workflow_type="detection_triage",
                            )
                            
                            # Update session external state
                            self.session_manager.update_external_state(
                                session_id=session_id,
                                external_state=external_state,
                            )
                            
                            # Yield state update
                            state_update_event = {
                                "event": "state_update",
                                "data": {
                                    "session_id": session_id,
                                    "node": event_name,
                                    "state": external_state,
                                }
                            }
                            state_keys = list(external_state.keys())[:5] if isinstance(external_state, dict) else "N/A"
                            logger.info(f"[DT_WORKFLOW] Yielding event: state_update - node={event_name}, state_keys={state_keys}, session_id={session_id}")
                            yield state_update_event
                            
                            # Check for checkpoints
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
                                
                                checkpoint_event = {
                                    "event": "checkpoint",
                                    "data": {
                                        "session_id": session_id,
                                        "checkpoint_id": checkpoint.checkpoint_id,
                                        "checkpoint_type": checkpoint.checkpoint_type,
                                        "node": checkpoint.node,
                                        "data": checkpoint.data,
                                        "message": checkpoint.message,
                                        "requires_user_input": checkpoint.requires_user_input,
                                    }
                                }
                                logger.info(f"[DT_WORKFLOW] Yielding event: checkpoint - checkpoint_id={checkpoint.checkpoint_id}, type={checkpoint.checkpoint_type}, node={checkpoint.node}, session_id={session_id}")
                                yield checkpoint_event
                                
                                # Yield session update
                                session = self.session_manager.get_session(session_id)
                                yield {
                                    "event": "session_update",
                                    "data": {
                                        "session_id": session_id,
                                        "session": session.to_dict(),
                                    }
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
                        }
                    }
                
                # Handle errors
                elif event_kind == "on_chain_error":
                    error_data = event.get("data", {})
                    error_msg = str(error_data.get("error", "Unknown error"))
                    
                    # Update node status
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
                        }
                    }
            
            # If no checkpoint was reached, workflow completed
            if not checkpoint_reached:
                if final_state:
                    external_state = transform_to_external_state(
                        final_state,
                        workflow_type="detection_triage",
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
                    }
                }
        
        except Exception as e:
            logger.error(f"Workflow execution error: {e}", exc_info=True)
            self.session_manager.update_session_status(
                session_id=session_id,
                status=SessionStatus.FAILED,
                error=str(e),
            )
            error_event = {
                "event": "error",
                "data": {
                    "error": str(e),
                    "session_id": session_id,
                }
            }
            logger.error(f"[DT_WORKFLOW] Yielding event: error - session_id={session_id}, error={str(e)}")
            yield error_event
    
    async def execute_workflow_invoke(
        self,
        user_query: str,
        session_id: str,
        initial_state_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute DT workflow synchronously (non-streaming).
        
        Args:
            user_query: User's natural language query
            session_id: Unique session identifier
            initial_state_data: Additional initial state fields
        
        Returns:
            Complete workflow result with session information
        """
        initial_state_data = initial_state_data or {}
        
        # Create session
        session = self.session_manager.create_session(
            session_id=session_id,
            workflow_type=WorkflowType.DETECTION_TRIAGE,
            user_query=user_query,
        )
        
        # Create initial state
        initial_state = self.create_initial_state(
            user_query=user_query,
            session_id=session_id,
            framework_id=initial_state_data.get("framework_id"),
            selected_data_sources=initial_state_data.get("selected_data_sources"),
            active_project_id=initial_state_data.get("active_project_id"),
            compliance_profile=initial_state_data.get("compliance_profile"),
            **{
                k: v for k, v in initial_state_data.items()
                if k not in ["framework_id", "selected_data_sources", "active_project_id", "compliance_profile"]
            }
        )
        
        # Get workflow app
        workflow_app = self.get_workflow_app()
        config = {"configurable": {"thread_id": session.thread_id}}
        
        # Update session status
        self.session_manager.update_session_status(session_id, SessionStatus.RUNNING)
        
        # Execute workflow with telemetry instrumentation
        loop = asyncio.get_event_loop()
        workflow_result = await loop.run_in_executor(
            None,
            lambda: instrument_workflow_invocation(
                workflow_app,
                initial_state,
                config=config,
                workflow_name="detection_triage"
            )
        )
        
        # Transform to external state
        external_state = transform_to_external_state(
            workflow_result,
            workflow_type="detection_triage",
        )
        
        # Update session
        self.session_manager.update_external_state(session_id, external_state)
        self.session_manager.update_session_status(session_id, SessionStatus.COMPLETED)
        
        # Get updated session
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
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Resume DT workflow execution from a checkpoint.
        
        Args:
            session_id: Session identifier
            checkpoint_id: ID of the checkpoint to resolve
            user_input: User input for checkpoint
            approved: Whether checkpoint is approved
        
        Yields:
            Event dictionaries with workflow execution updates
        """
        # Get session
        session = self.session_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        if session.status != SessionStatus.CHECKPOINT:
            raise ValueError(
                f"Session {session_id} is not at a checkpoint (current status: {session.status.value})"
            )
        
        # Resolve checkpoint in session
        self.session_manager.resolve_checkpoint(
            session_id=session_id,
            checkpoint_id=checkpoint_id,
            user_input=user_input,
            approved=approved,
        )
        
        # Get workflow app
        workflow_app = self.get_workflow_app()
        config = {"configurable": {"thread_id": session.thread_id}}
        
        # Get current state from checkpointer
        try:
            last_state_snapshot = workflow_app.get_state(config)
            
            if not last_state_snapshot or not last_state_snapshot.values:
                raise ValueError("No checkpoint state found for this session")
            
            # Update state with checkpoint input
            current_state = last_state_snapshot.values.copy()
            current_state["user_checkpoint_input"] = user_input
            
            # Mark checkpoint as resolved in state
            if "checkpoints" in current_state:
                for checkpoint in current_state["checkpoints"]:
                    if isinstance(checkpoint, dict) and checkpoint.get("node") == checkpoint_id:
                        checkpoint["status"] = "approved" if approved else "rejected"
                        checkpoint["user_input"] = user_input
                        break
            
            # Update the state in the checkpointer
            workflow_app.update_state(config, current_state)
        
        except AttributeError:
            logger.warning("get_state not available, using alternative approach")
            raise ValueError("Checkpoint state retrieval not supported with current checkpointer")
        except Exception as e:
            logger.warning(f"Could not retrieve checkpoint state: {e}")
            raise ValueError(f"Cannot resume: {str(e)}")
        
        # Update session status
        self.session_manager.update_session_status(session_id, SessionStatus.RUNNING)
        
        # Yield resume event
        yield {
            "event": "workflow_resumed",
            "data": {
                "session_id": session_id,
                "checkpoint_id": checkpoint_id,
                "message": "Resuming workflow from checkpoint",
            }
        }
        
        checkpoint_reached = False
        final_state = None
        
        try:
            # Continue streaming with updated state
            async for event in instrument_workflow_stream_events(
                workflow_app,
                current_state,
                config=config,
                workflow_name="detection_triage",
                version="v2"
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
                        }
                    }
                
                elif event_kind == "on_chain_end":
                    self.session_manager.add_node(
                        session_id=session_id,
                        node_id=run_id,
                        node_name=event_name,
                        status="completed",
                    )
                    
                    # Get current state
                    try:
                        current_state_snapshot = workflow_app.get_state(config)
                        if current_state_snapshot and current_state_snapshot.values:
                            current_state = current_state_snapshot.values
                            final_state = current_state
                            
                            # Transform to external state
                            external_state = transform_to_external_state(
                                current_state,
                                workflow_type="detection_triage",
                            )
                            
                            # Update session external state
                            self.session_manager.update_external_state(
                                session_id=session_id,
                                external_state=external_state,
                            )
                            
                            # Yield state update
                            yield {
                                "event": "state_update",
                                "data": {
                                    "session_id": session_id,
                                    "node": event_name,
                                    "state": external_state,
                                }
                            }
                            
                            # Check for new checkpoints
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
                                    }
                                }
                                
                                session = self.session_manager.get_session(session_id)
                                yield {
                                    "event": "session_update",
                                    "data": {
                                        "session_id": session_id,
                                        "session": session.to_dict(),
                                    }
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
                        }
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
                        }
                    }
            
            # If no checkpoint was reached, workflow completed
            if not checkpoint_reached:
                if final_state:
                    external_state = transform_to_external_state(
                        final_state,
                        workflow_type="detection_triage",
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
                    }
                }
        
        except Exception as e:
            logger.error(f"Workflow resume error: {e}", exc_info=True)
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
                }
            }


# Global service instance
_dt_workflow_service = None


def get_dt_workflow_service(session_manager=None) -> DTWorkflowService:
    """
    Get the global DT workflow service instance.
    
    Args:
        session_manager: Optional session manager instance.
                        If None, uses the global session manager.
    
    Returns:
        DTWorkflowService instance
    """
    global _dt_workflow_service
    
    if _dt_workflow_service is None:
        from app.api.session_manager import get_session_manager
        session_manager = session_manager or get_session_manager()
        _dt_workflow_service = DTWorkflowService(session_manager)
    
    return _dt_workflow_service

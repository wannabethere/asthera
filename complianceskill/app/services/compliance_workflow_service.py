"""
Compliance Workflow Service

Service layer for compliance workflow operations, providing a clean abstraction
for executing, managing, and monitoring compliance workflows.
"""
import logging
import asyncio
from typing import Dict, Any, Optional, AsyncGenerator
from datetime import datetime

from app.agents.detectiontriageworkflows.workflow import create_compliance_app
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

logger = logging.getLogger(__name__)


class ComplianceWorkflowService:
    """
    Service for managing Compliance workflow execution.
    
    Provides methods for:
    - Creating and initializing compliance workflows
    - Executing workflows (streaming and non-streaming)
    - Resuming workflows from checkpoints
    - Managing workflow state and sessions
    """
    
    def __init__(self, session_manager: SessionManager):
        """
        Initialize the compliance workflow service.
        
        Args:
            session_manager: Session manager instance for tracking workflow sessions
        """
        self.session_manager = session_manager
        self._compliance_app = None
        logger.info("ComplianceWorkflowService initialized")
    
    def get_workflow_app(self, dependencies: Optional[Dict[str, Any]] = None):
        """
        Get or create the compliance workflow app instance.
        
        Args:
            dependencies: Optional dependencies dict (for future use)
        
        Returns:
            Compiled LangGraph application for compliance workflow
        """
        if self._compliance_app is None:
            self._compliance_app = create_compliance_app()
            logger.info("Compliance workflow app created successfully")
        return self._compliance_app
    
    def create_initial_state(
        self,
        user_query: str,
        session_id: str,
        **additional_state: Any,
    ) -> EnhancedCompliancePipelineState:
        """
        Create initial state for compliance workflow execution.
        
        Args:
            user_query: User's natural language query
            session_id: Unique session identifier
            **additional_state: Additional state fields to merge
        
        Returns:
            Initial state dictionary ready for workflow execution
        """
        initial_state: EnhancedCompliancePipelineState = {
            "user_query": user_query,
            "session_id": session_id,
            "messages": [],
            "execution_plan": None,
            "current_step_index": 0,
            "plan_completion_status": {},
            "validation_results": [],
            "iteration_count": 0,
            "max_iterations": 5,
            "refinement_history": [],
            "context_cache": {},
            "execution_steps": [],
            **additional_state
        }
        
        return initial_state
    
    async def execute_workflow_stream(
        self,
        user_query: str,
        session_id: str,
        initial_state_data: Optional[Dict[str, Any]] = None,
        dependencies: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute compliance workflow with streaming response.
        
        Args:
            user_query: User's natural language query
            session_id: Unique session identifier
            initial_state_data: Additional initial state fields
            dependencies: Optional dependencies dict
        
        Yields:
            Event dictionaries with workflow execution updates
        """
        initial_state_data = initial_state_data or {}
        
        # Create session
        session = self.session_manager.create_session(
            session_id=session_id,
            workflow_type=WorkflowType.COMPLIANCE,
            user_query=user_query,
        )
        
        # Create initial state
        initial_state = self.create_initial_state(
            user_query=user_query,
            session_id=session_id,
            **initial_state_data
        )
        
        # Get workflow app
        workflow_app = self.get_workflow_app(dependencies=dependencies)
        config = {"configurable": {"thread_id": session.thread_id}}
        
        # Update session status
        self.session_manager.update_session_status(session_id, SessionStatus.RUNNING)
        
        # Yield workflow start event
        workflow_start_event = {
            "event": "workflow_start",
            "data": {
                "session_id": session_id,
                "workflow_type": "compliance",
                "user_query": user_query,
                "status": SessionStatus.RUNNING.value,
            }
        }
        logger.info(f"[COMPLIANCE_WORKFLOW] Yielding event: workflow_start for session {session_id}")
        yield workflow_start_event
        
        checkpoint_reached = False
        final_state = None
        
        try:
            # Stream workflow execution
            async for event in instrument_workflow_stream_events(
                workflow_app,
                initial_state,
                config=config,
                workflow_name="compliance",
                version="v2"
            ):
                event_kind = event.get("event")
                event_name = event.get("name", "")
                run_id = event.get("run_id", "")
                
                # Handle node start events
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
                                workflow_type="compliance",
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
                        workflow_type="compliance",
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
            yield {
                "event": "error",
                "data": {
                    "error": str(e),
                    "session_id": session_id,
                }
            }
    
    async def execute_workflow_invoke(
        self,
        user_query: str,
        session_id: str,
        initial_state_data: Optional[Dict[str, Any]] = None,
        dependencies: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute compliance workflow synchronously (non-streaming).
        
        Args:
            user_query: User's natural language query
            session_id: Unique session identifier
            initial_state_data: Additional initial state fields
            dependencies: Optional dependencies dict
        
        Returns:
            Complete workflow result with session information
        """
        initial_state_data = initial_state_data or {}
        
        # Create session
        session = self.session_manager.create_session(
            session_id=session_id,
            workflow_type=WorkflowType.COMPLIANCE,
            user_query=user_query,
        )
        
        # Create initial state
        initial_state = self.create_initial_state(
            user_query=user_query,
            session_id=session_id,
            **initial_state_data
        )
        
        # Get workflow app
        workflow_app = self.get_workflow_app(dependencies=dependencies)
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
                workflow_name="compliance"
            )
        )
        
        # Transform to external state
        external_state = transform_to_external_state(
            workflow_result,
            workflow_type="compliance",
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
        dependencies: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Resume compliance workflow execution from a checkpoint.
        
        Args:
            session_id: Session identifier
            checkpoint_id: ID of the checkpoint to resolve
            user_input: User input for checkpoint
            approved: Whether checkpoint is approved
            dependencies: Optional dependencies dict
        
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
        workflow_app = self.get_workflow_app(dependencies=dependencies)
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
                workflow_name="compliance",
                version="v2"
            ):
                event_kind = event.get("event")
                event_name = event.get("name", "")
                run_id = event.get("run_id", "")
                
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
                                workflow_type="compliance",
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
                        workflow_type="compliance",
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
_compliance_workflow_service = None


def get_compliance_workflow_service(session_manager=None) -> ComplianceWorkflowService:
    """
    Get the global compliance workflow service instance.
    
    Args:
        session_manager: Optional session manager instance.
                        If None, uses the global session manager.
    
    Returns:
        ComplianceWorkflowService instance
    """
    global _compliance_workflow_service
    
    if _compliance_workflow_service is None:
        from app.api.session_manager import get_session_manager
        session_manager = session_manager or get_session_manager()
        _compliance_workflow_service = ComplianceWorkflowService(session_manager)
    
    return _compliance_workflow_service

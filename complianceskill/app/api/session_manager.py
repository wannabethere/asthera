"""
Session Manager for Workflow State Management

Maintains session state separate from LangGraph internal state,
providing a clean separation between internal workflow execution
and external API responses.
"""
import logging
from typing import Dict, Any, Optional, Literal
from datetime import datetime
from dataclasses import dataclass, field, asdict
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class WorkflowType(str, Enum):
    """Supported workflow types"""
    COMPLIANCE = "compliance"
    DETECTION_TRIAGE = "detection_triage"
    CSOD = "csod"
    DASHBOARD_AGENT = "dashboard_agent"


class SessionStatus(str, Enum):
    """Session status"""
    PENDING = "pending"
    RUNNING = "running"
    CHECKPOINT = "checkpoint"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Checkpoint:
    """Checkpoint requiring user input"""
    checkpoint_id: str
    checkpoint_type: str
    node: str
    data: Dict[str, Any]
    message: str
    requires_user_input: bool = True
    status: Literal["pending", "approved", "rejected"] = "pending"
    user_input: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class WorkflowNode:
    """Node execution information"""
    node_id: str
    node_name: str
    status: Literal["pending", "running", "completed", "failed"]
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class WorkflowSession:
    """Workflow session state"""
    session_id: str
    workflow_type: WorkflowType
    status: SessionStatus
    user_query: str
    
    # Workflow execution state
    current_node: Optional[str] = None
    nodes: Dict[str, WorkflowNode] = field(default_factory=dict)
    checkpoints: Dict[str, Checkpoint] = field(default_factory=dict)
    active_checkpoint_id: Optional[str] = None
    
    # External state (transformed from LangGraph state)
    external_state: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    
    # LangGraph thread config
    thread_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for API response"""
        return {
            "session_id": self.session_id,
            "workflow_type": self.workflow_type.value,
            "status": self.status.value,
            "user_query": self.user_query,
            "current_node": self.current_node,
            "nodes": {
                node_id: {
                    "node_id": node.node_id,
                    "node_name": node.node_name,
                    "status": node.status,
                    "started_at": node.started_at.isoformat() if node.started_at else None,
                    "completed_at": node.completed_at.isoformat() if node.completed_at else None,
                    "error": node.error,
                }
                for node_id, node in self.nodes.items()
            },
            "checkpoints": {
                cp_id: {
                    "checkpoint_id": cp.checkpoint_id,
                    "checkpoint_type": cp.checkpoint_type,
                    "node": cp.node,
                    "data": cp.data,
                    "message": cp.message,
                    "requires_user_input": cp.requires_user_input,
                    "status": cp.status,
                    "user_input": cp.user_input,
                    "created_at": cp.created_at.isoformat(),
                }
                for cp_id, cp in self.checkpoints.items()
            },
            "active_checkpoint_id": self.active_checkpoint_id,
            "external_state": self.external_state,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
        }


class SessionManager:
    """Manages workflow sessions"""
    
    def __init__(self):
        self._sessions: Dict[str, WorkflowSession] = {}
        logger.info("SessionManager initialized")
    
    def create_session(
        self,
        session_id: str,
        workflow_type: WorkflowType,
        user_query: str,
    ) -> WorkflowSession:
        """Create a new workflow session"""
        session = WorkflowSession(
            session_id=session_id,
            workflow_type=workflow_type,
            status=SessionStatus.PENDING,
            user_query=user_query,
        )
        self._sessions[session_id] = session
        logger.info(f"Created session {session_id} for workflow {workflow_type.value}")
        return session
    
    def get_session(self, session_id: str) -> Optional[WorkflowSession]:
        """Get session by ID"""
        return self._sessions.get(session_id)
    
    def update_session_status(
        self,
        session_id: str,
        status: SessionStatus,
        error: Optional[str] = None,
    ) -> None:
        """Update session status"""
        session = self.get_session(session_id)
        if not session:
            logger.warning(f"Session {session_id} not found for status update")
            return
        
        session.status = status
        session.updated_at = datetime.utcnow()
        if error:
            session.error = error
        if status == SessionStatus.COMPLETED:
            session.completed_at = datetime.utcnow()
        
        logger.debug(f"Updated session {session_id} status to {status.value}")
    
    def add_node(
        self,
        session_id: str,
        node_id: str,
        node_name: str,
        status: Literal["pending", "running", "completed", "failed"] = "running",
    ) -> WorkflowNode:
        """Add or update a node in the session"""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        if node_id not in session.nodes:
            node = WorkflowNode(
                node_id=node_id,
                node_name=node_name,
                status=status,
            )
            session.nodes[node_id] = node
        else:
            node = session.nodes[node_id]
            node.status = status
        
        if status == "running" and not node.started_at:
            node.started_at = datetime.utcnow()
        elif status in ("completed", "failed"):
            node.completed_at = datetime.utcnow()
        
        session.current_node = node_name
        session.updated_at = datetime.utcnow()
        
        return node
    
    def add_checkpoint(
        self,
        session_id: str,
        checkpoint: Checkpoint,
    ) -> None:
        """Add a checkpoint to the session"""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        session.checkpoints[checkpoint.checkpoint_id] = checkpoint
        session.active_checkpoint_id = checkpoint.checkpoint_id
        session.status = SessionStatus.CHECKPOINT
        session.updated_at = datetime.utcnow()
        
        logger.info(f"Added checkpoint {checkpoint.checkpoint_id} to session {session_id}")
    
    def resolve_checkpoint(
        self,
        session_id: str,
        checkpoint_id: str,
        user_input: Dict[str, Any],
        approved: bool = True,
    ) -> None:
        """Resolve a checkpoint with user input"""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        checkpoint = session.checkpoints.get(checkpoint_id)
        if not checkpoint:
            raise ValueError(f"Checkpoint {checkpoint_id} not found in session {session_id}")
        
        checkpoint.status = "approved" if approved else "rejected"
        checkpoint.user_input = user_input
        session.active_checkpoint_id = None
        session.status = SessionStatus.RUNNING
        session.updated_at = datetime.utcnow()
        
        logger.info(f"Resolved checkpoint {checkpoint_id} in session {session_id}")
    
    def update_external_state(
        self,
        session_id: str,
        external_state: Dict[str, Any],
    ) -> None:
        """Update the external state for the session"""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        session.external_state = external_state
        session.updated_at = datetime.utcnow()
    
    def delete_session(self, session_id: str) -> None:
        """Delete a session"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Deleted session {session_id}")
    
    def list_sessions(self, workflow_type: Optional[WorkflowType] = None) -> list[WorkflowSession]:
        """List all sessions, optionally filtered by workflow type"""
        sessions = list(self._sessions.values())
        if workflow_type:
            sessions = [s for s in sessions if s.workflow_type == workflow_type]
        return sessions


# Global session manager instance
_session_manager = SessionManager()


def get_session_manager() -> SessionManager:
    """Get the global session manager instance"""
    return _session_manager

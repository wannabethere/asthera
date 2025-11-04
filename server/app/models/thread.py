from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, UUID, Text, JSON, Integer,Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint
import uuid
from app.database import Base
from sqlalchemy.ext.mutable import MutableList,MutableDict
from uuid import uuid4
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
class Thread(Base):
    __tablename__ = "threads"
 
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False, default="No description provided")
    dataset_id = Column(Text)
    dataset_name=Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)
 
    # Relationships
    project = relationship("Project", back_populates="threads")
    creator = relationship("User", foreign_keys=[created_by])
    messages = relationship("ThreadMessage", back_populates="thread", cascade="all, delete-orphan")
    workflows = relationship("Workflow", back_populates="thread", cascade="all, delete-orphan")
    notes = relationship("Note", back_populates="thread", cascade="all, delete-orphan")
    timelines = relationship("Timeline", back_populates="thread", cascade="all, delete-orphan")
    collaborators = relationship("ThreadCollaborator", back_populates="thread", cascade="all, delete-orphan")
    configuration = relationship("ThreadConfiguration", back_populates="thread", uselist=False, cascade="all, delete-orphan")
 
    def __repr__(self):
        return f"<Thread {self.title}>"
 
class ThreadMessage(Base):
    __tablename__ = "thread_messages"
 
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id = Column(UUID(as_uuid=True), ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    response = Column(MutableDict.as_mutable(JSONB), nullable=True)
    status=Column(String)
 
    # Relationships
    thread = relationship("Thread", back_populates="messages")
    user = relationship("User")
    audits = relationship("Audit", back_populates="thread_message")
 
class Workflow(Base):
    __tablename__ = "workflows"
 
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id = Column(UUID(as_uuid=True), ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text)
    steps = Column(MutableList.as_mutable(JSON), nullable=False)  # Stores the sequence of actions
    status = Column(String, nullable=False, default="draft")  # draft, active, completed
    is_dashboard = Column(Boolean,default=False)
    is_report = Column(Boolean,default=False)
    is_alert = Column(Boolean,default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
 
    # Relationships
    thread = relationship("Thread", back_populates="workflows")
    user = relationship("User")
 
    def __repr__(self):
        return f"<Workflow {self.title}>"
 
class Note(Base):
    __tablename__ = "notes"
 
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id = Column(UUID(as_uuid=True), ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    sortorder = Column(Integer, nullable=False)  # For maintaining the sequence of notes
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
 
    # Relationships
    thread = relationship("Thread", back_populates="notes")
    user = relationship("User")
 
    def __repr__(self):
        return f"<Note {self.title}>"
 
class Timeline(Base):
    __tablename__ = "timelines"
 
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id = Column(UUID(as_uuid=True), ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text)
    events = Column(JSON, nullable=False)  # Stores the sequence of Q&A or important events
    sortorder = Column(Integer, nullable=False)  # For maintaining the sequence of timeline events
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
 
    # Relationships
    thread = relationship("Thread", back_populates="timelines")
    user = relationship("User")
 
    def __repr__(self):
        return f"<Timeline {self.title}>"
 
class ThreadCollaborator(Base):
    __tablename__ = "thread_collaborators"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id = Column(UUID(as_uuid=True), ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role = Column(String, nullable=False, default="collaborator")  # e.g., 'owner', 'collaborator', 'viewer'
    status = Column(String, nullable=False, default="pending")  # pending, accepted, rejected
    message = Column(Text)
    data_connection = Column(JSON)  # Store any additional data/connection info
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
 
    # Relationships
    thread = relationship("Thread", back_populates="collaborators")
    user = relationship("User")
 
    __table_args__ = (
        UniqueConstraint('thread_id', 'user_id', name='unique_thread_collaborator'),
    )
 
class ThreadConfiguration(Base):
    __tablename__ = "thread_configurations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id = Column(UUID(as_uuid=True), ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    config = Column(JSON, nullable=False)  # Store configuration as JSON
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
 
    # Relationships
    thread = relationship("Thread", back_populates="configuration")
 
    __table_args__ = (
        UniqueConstraint('thread_id', 'name', name='unique_thread_config_name'),
    )

class Audit(Base):
    __tablename__ = 'audits'
    
    auditid = Column(String(255), primary_key=True, default=lambda: f"audit_{uuid4().hex[:8]}")
    auditName = Column(String(255), nullable=False)
    messageid = Column(UUID(as_uuid=True), ForeignKey('thread_messages.id'), nullable=False) 
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    total_time = Column(Float, nullable=True) 
    steps = Column(Integer, default=3) 
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False) 
    
    # Relationships
    thread_message = relationship("ThreadMessage", back_populates="audits")
    traces = relationship("Trace", back_populates="audit", cascade="all, delete-orphan")
    user = relationship("User", back_populates="audits")
    
    def calculate_total_time(self):
        """Calculate total time from all traces"""
        try:
            if self.traces:
                total = sum(trace.time_taken for trace in self.traces if trace.time_taken is not None)
                return total if total > 0 else None
            return None
        except Exception as e:
            logger.error(f"Error calculating total time for audit {self.auditid}: {str(e)}")
            return None

class Trace(Base):  # Fixed class name from Traces to Trace
    __tablename__ = 'traces'
    
    trace_id = Column(String(255), primary_key=True, default=lambda: f"trace_{uuid4().hex[:8]}")
    auditid = Column(String(255), ForeignKey('audits.auditid'), nullable=False)
    sequence = Column(Integer, nullable=False) 
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    component = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default='pending') 
    input_data = Column(MutableDict.as_mutable(JSONB), nullable=True)
    output_data = Column(MutableDict.as_mutable(JSONB), nullable=True)
    time_taken = Column(Float, nullable=True)
    
    # Relationships
    audit = relationship("Audit", back_populates="traces")
 
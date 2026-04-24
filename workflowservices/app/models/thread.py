from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, UUID, Text, JSON, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint
import uuid
from app.models.dbmodels import Base

class Thread(Base):
    __tablename__ = "threads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False, default="No description provided")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)

    # Relationships
    project = relationship("Project", back_populates="threads", foreign_keys=[project_id])
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

    # Relationships
    thread = relationship("Thread", back_populates="messages")
    user = relationship("User")

class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id = Column(UUID(as_uuid=True), ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text)
    steps = Column(JSON, nullable=False)  # Stores the sequence of actions
    status = Column(String, nullable=False, default="draft")  # draft, active, completed
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
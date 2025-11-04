from sqlalchemy import Column, String, DateTime, ForeignKey, UUID, Boolean, Text, Integer, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
import enum
from app.database import Base

class StepStatus(enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"

class ThreadStep(Base):
    __tablename__ = "thread_steps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id = Column(UUID(as_uuid=True), ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(StepStatus), default=StepStatus.PENDING)
    order = Column(Integer, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)

    # Relationships
    thread = relationship("Thread", back_populates="steps")
    creator = relationship("User", foreign_keys=[created_by])
    assignee = relationship("User", foreign_keys=[assigned_to])
    messages = relationship("ThreadMessage", back_populates="step")

    def __repr__(self):
        return f"<ThreadStep {self.title}>"

class ThreadNote(Base):
    __tablename__ = "thread_notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id = Column(UUID(as_uuid=True), ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)

    # Relationships
    thread = relationship("Thread", back_populates="notes")
    creator = relationship("User", foreign_keys=[created_by])
    messages = relationship("ThreadMessage", back_populates="note")

    def __repr__(self):
        return f"<ThreadNote {self.title}>"

class TimelineEventType(enum.Enum):
    STEP_CREATED = "step_created"
    STEP_UPDATED = "step_updated"
    STEP_COMPLETED = "step_completed"
    NOTE_CREATED = "note_created"
    NOTE_UPDATED = "note_updated"
    MESSAGE_ADDED = "message_added"
    MESSAGE_UPDATED = "message_updated"
    THREAD_CREATED = "thread_created"
    THREAD_UPDATED = "thread_updated"

class ThreadTimeline(Base):
    __tablename__ = "thread_timeline"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id = Column(UUID(as_uuid=True), ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(Enum(TimelineEventType), nullable=False)
    description = Column(Text, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    related_object_id = Column(UUID(as_uuid=True), nullable=True)  # Can reference step, note, or message
    related_object_type = Column(String, nullable=True)  # Type of the related object

    # Relationships
    thread = relationship("Thread", back_populates="timeline")
    creator = relationship("User", foreign_keys=[created_by])

    def __repr__(self):
        return f"<ThreadTimeline {self.event_type}>" 
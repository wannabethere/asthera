from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, JSON, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from app.database import Base

class DataConnection(Base):
    __tablename__ = "data_connections"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(Text)
    source_type = Column(String, nullable=False)  # e.g., 'postgresql', 'mysql', 's3', etc.
    connection_config = Column(JSON, nullable=False)  # Connection details like host, port, credentials
    data_definitions = Column(JSON, nullable=False)  # Schema definitions and filters
    is_active = Column(Boolean, default=True)
    created_by = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    access_controls = relationship("DataConnectionAccess", back_populates="data_connection", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<DataConnection {self.name}>"

class DataConnectionAccess(Base):
    __tablename__ = "data_connection_access"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    data_connection_id = Column(String, ForeignKey("data_connections.id", ondelete="CASCADE"), nullable=False)
    team_id = Column(String, ForeignKey("teams.id", ondelete="CASCADE"), nullable=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    access_level = Column(String, nullable=False)  # 'read', 'write', 'admin'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    data_connection = relationship("DataConnection", back_populates="access_controls")
    team = relationship("Team")
    workspace = relationship("Workspace")
    user = relationship("User")

    def __repr__(self):
        return f"<DataConnectionAccess {self.id}>" 
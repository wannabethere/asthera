from sqlalchemy import Column, String, DateTime, ForeignKey, UUID, Boolean, UniqueConstraint, Integer, Index, event
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, backref
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict, MutableList
import uuid
from app.models.dbmodels import Base

# Default permissions for different roles
DEFAULT_WORKSPACE_PERMISSIONS = {
    "owner": {
        "is_admin": True,
        "can_create": True,
        "can_delete": True
    },
    "admin": {
        "is_admin": True,
        "can_create": True,
        "can_delete": False
    },
    "member": {
        "is_admin": False,
        "can_create": True,
        "can_delete": False
    }
}

class WorkspaceAccess(Base):
    __tablename__ = "workspace_access"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    is_admin = Column(Boolean, default=False)
    can_create = Column(Boolean, default=True)
    can_delete = Column(Boolean, default=False)
    role = Column(String, default="member")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    workspace = relationship("Workspace", back_populates="access")
    user = relationship("User")

    __table_args__ = (
        UniqueConstraint('workspace_id', 'user_id', name='unique_workspace_user'),
    )

class ProjectAccess(Base):
    __tablename__ = "project_access"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    is_admin = Column(Boolean, default=False)
    can_create = Column(Boolean, default=True)
    can_delete = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    project = relationship("Project", back_populates="access")
    user = relationship("User")

class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(String)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    team = relationship("Team", back_populates="workspaces")
    projects = relationship("Project", back_populates="workspace", cascade="all, delete-orphan")
    access = relationship("WorkspaceAccess", back_populates="workspace", cascade="all, delete-orphan")
    invites = relationship("WorkspaceInvite", back_populates="workspace", cascade="all, delete-orphan")
    creator = relationship("User", foreign_keys=[created_by])

    def add_user_access(self, user_id: UUID, role: str = "member"):
        """Add a user to the workspace with specified role and permissions"""
        permissions = DEFAULT_WORKSPACE_PERMISSIONS.get(role, DEFAULT_WORKSPACE_PERMISSIONS["member"])
        access = WorkspaceAccess(
            workspace_id=self.id,
            user_id=user_id,
            role=role,
            **permissions
        )
        return access

@event.listens_for(Workspace, 'after_insert')
def create_default_access(mapper, connection, target):
    """Create default access for workspace creator"""
    if target.created_by:
        access = target.add_user_access(target.created_by, "owner")
        connection.execute(
            WorkspaceAccess.__table__.insert(),
            {
                "id": uuid.uuid4(),
                "workspace_id": target.id,
                "user_id": target.created_by,
                "role": "owner",
                **DEFAULT_WORKSPACE_PERMISSIONS["owner"]
            }
        )

class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(String)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    goals = Column(MutableList.as_mutable(JSONB), default=[], nullable=True)
    data_sources = Column(MutableList.as_mutable(JSONB), default=[], nullable=True)
    thread_id = Column(UUID(as_uuid=True), ForeignKey("threads.id", ondelete="SET NULL"), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(String, default="active")
    project_metadata = Column(MutableDict.as_mutable(JSONB), default={}, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    workspace = relationship("Workspace", back_populates="projects")
    access = relationship("ProjectAccess", back_populates="project", cascade="all, delete-orphan")
    threads = relationship("Thread", back_populates="project", foreign_keys="Thread.project_id", cascade="all, delete-orphan")
    primary_thread = relationship("Thread", foreign_keys=[thread_id], uselist=False)
    creator = relationship("User", foreign_keys=[created_by])
    artifacts = relationship("ProjectArtifact", back_populates="project", cascade="all, delete-orphan")


class ProjectArtifact(Base):
    """Polymorphic linking table: links Projects to Dashboards/Reports/Alerts without modifying those tables."""
    __tablename__ = "project_artifacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    artifact_type = Column(String(50), nullable=False)  # "dashboard", "report", "alert"
    artifact_id = Column(UUID(as_uuid=True), nullable=False)  # ID of the dashboard/report/alert
    parent_artifact_id = Column(UUID(as_uuid=True), ForeignKey("project_artifacts.id", ondelete="SET NULL"), nullable=True)
    sequence_order = Column(Integer, default=0)
    artifact_metadata = Column(MutableDict.as_mutable(JSONB), default={}, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project", back_populates="artifacts")
    children = relationship("ProjectArtifact", backref=backref("parent", remote_side="ProjectArtifact.id"))

    __table_args__ = (
        Index("idx_project_artifacts_project", "project_id"),
        Index("idx_project_artifacts_type_id", "artifact_type", "artifact_id"),
        UniqueConstraint("project_id", "artifact_type", "artifact_id", name="uix_project_artifact"),
    )

class WorkspaceInvite(Base):
    __tablename__ = "workspace_invites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    email = Column(String, nullable=False)
    role = Column(String, default="member")
    status = Column(String, default="pending")
    invited_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    workspace = relationship("Workspace", back_populates="invites")
    inviter = relationship("User")

    __table_args__ = (
        UniqueConstraint('workspace_id', 'email', name='uix_workspace_invite_email'),
    ) 
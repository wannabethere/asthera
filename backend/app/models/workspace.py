from sqlalchemy import Column, String, DateTime, ForeignKey, UUID, Boolean, UniqueConstraint, event
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from app.database import Base

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
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    workspace = relationship("Workspace", back_populates="projects")
    access = relationship("ProjectAccess", back_populates="project", cascade="all, delete-orphan")
    threads = relationship("Thread", back_populates="project", cascade="all, delete-orphan")

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
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Boolean, UUID, Table, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from app.database import Base
from passlib.context import CryptContext
from app.models.rbac import user_roles
import logging
from datetime import datetime

# Import the team_memberships table from team model
from app.models.team import team_memberships

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")



class UserToken(Base):
    __tablename__ = "user_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String, unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True)
    device_info = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # Relationship to User
    user = relationship("User", back_populates="tokens")

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    okta_id = Column(String, unique=True, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    last_login = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Core relationships
    roles = relationship("Role", secondary=user_roles, back_populates="users")
    tokens = relationship("UserToken", back_populates="user", cascade="all, delete-orphan")

    # Team relationships
    teams = relationship("Team", secondary=team_memberships, back_populates="members")
    created_teams = relationship("Team", foreign_keys="[Team.created_by]", back_populates="creator")
    owned_teams = relationship("Team", foreign_keys="[Team.owner_id]", back_populates="owner")

    # Workspace relationships
    workspace_access = relationship("WorkspaceAccess", back_populates="user", cascade="all, delete-orphan")
    project_access = relationship("ProjectAccess", back_populates="user", cascade="all, delete-orphan")

    # Thread relationships
    created_threads = relationship("Thread", foreign_keys="[Thread.created_by]", back_populates="creator", cascade="all, delete-orphan")

    # Request relationships
    collaboration_requests = relationship("CollaborationRequest", foreign_keys="[CollaborationRequest.requester_id]", back_populates="requester")
    team_signup_requests = relationship("TeamSignupRequest", foreign_keys="[TeamSignupRequest.user_id]", back_populates="user")
    team_invites = relationship("TeamInvite", foreign_keys="[TeamInvite.invited_by]", back_populates="inviter")

    def set_password(self, password: str):
        self.password_hash = pwd_context.hash(password)

    def check_password(self, password: str) -> bool:
        logger.info(f"Checking password for user {self.username}: {password} == {self.password_hash}")
        hashed_password =  pwd_context.hash(password)
        logger.info(f"Hashed password: {hashed_password}")
        return pwd_context.verify(password, self.password_hash)

    def __repr__(self):
        return f"<User {self.username}>"

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    def get_id(self):
        return str(self.id) 
    

    
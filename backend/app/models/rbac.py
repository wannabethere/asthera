from sqlalchemy import Column, String, DateTime, ForeignKey, UUID, Table, UniqueConstraint, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
import enum
from app.database import Base

class RoleType(enum.Enum):
    SYSTEM = "system"  # Built-in system roles
    EXTERNAL = "external"  # Configurable external roles

class ObjectType(enum.Enum):
    WORKSPACE = "workspace"
    PROJECT = "project"
    TEAM = "team"

# Association table for user roles
user_roles = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', UUID(as_uuid=True), ForeignKey('users.id', ondelete="CASCADE"), primary_key=True),
    Column('role_id', UUID(as_uuid=True), ForeignKey('roles.id', ondelete="CASCADE"), primary_key=True),
    Column('object_id', UUID(as_uuid=True), nullable=True),  # ID of the workspace/project/team
    Column('object_type', String, nullable=True),  # Type of the object: 'workspace', 'project', 'team'
    Column('role_name', String, nullable=True)  # Name of the role for easier lookup
)

# Association table for role permissions
role_permissions = Table(
    'role_permissions',
    Base.metadata,
    Column('role_id', UUID(as_uuid=True), ForeignKey('roles.id', ondelete="CASCADE"), primary_key=True),
    Column('permission_id', UUID(as_uuid=True), ForeignKey('permissions.id', ondelete="CASCADE"), primary_key=True)
)

class Role(Base):
    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)
    description = Column(String)
    role_type = Column(String, nullable=True, default=None)  # No Enum, nullable, default None
    object_type = Column(String, nullable=True, default=None)  # No Enum, nullable, default None
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    users = relationship("User", secondary=user_roles, back_populates="roles")
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")

class Permission(Base):
    __tablename__ = "permissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)
    description = Column(String)
    resource_type = Column(String, nullable=False)  # workspace, project, team, etc.
    action = Column(String, nullable=False)  # create, read, update, delete
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")

# Default system roles
SYSTEM_ROLES = {
    "superuser": {
        "type": RoleType.SYSTEM,
        "object_type": None,
        "description": "Full system access",
        "permissions": ["*"]  # All permissions
    },
    "system_admin": {
        "type": RoleType.SYSTEM,
        "object_type": None,
        "description": "System administration access",
        "permissions": [
            "workspace:*",
            "project:*",
            "team:*",
            "thread:*"
        ]
    },
    "authenticated_user": {
        "type": RoleType.SYSTEM,
        "object_type": None,
        "description": "Default role for all authenticated users",
        "permissions": [
            "workspace:read",
            "workspace:subscribe",
            "project:read",
            "project:subscribe",
            "team:read",
            "thread:read",
            "thread:create",
            "thread:update",
            "thread:subscribe",
            "search:execute"
        ]
    }
}

# Default external roles for each object type
EXTERNAL_ROLES = {
    ObjectType.WORKSPACE: {
        "owner": {
            "description": "Full workspace access and management",
            "permissions": [
                "workspace:read",
                "workspace:update",
                "workspace:delete",
                "workspace:manage_members",
                "workspace:manage_projects",
                "project:*",
                "team:*"
            ]
        },
        "admin": {
            "description": "Workspace administration access",
            "permissions": [
                "workspace:read",
                "workspace:update",
                "workspace:manage_members",
                "workspace:manage_projects",
                "project:create",
                "project:read",
                "project:update",
                "team:create",
                "team:read",
                "team:update"
            ]
        },
        "member": {
            "description": "Basic workspace access",
            "permissions": [
                "workspace:read",
                "project:read",
                "team:read"
            ]
        }
    },
    ObjectType.PROJECT: {
        "owner": {
            "description": "Full project access and management",
            "permissions": [
                "project:read",
                "project:update",
                "project:delete",
                "project:manage_members",
                "project:manage_threads",
                "thread:*"
            ]
        },
        "admin": {
            "description": "Project administration access",
            "permissions": [
                "project:read",
                "project:update",
                "project:manage_members",
                "project:manage_threads",
                "thread:create",
                "thread:read",
                "thread:update"
            ]
        },
        "member": {
            "description": "Basic project access",
            "permissions": [
                "project:read",
                "thread:create",
                "thread:read",
                "thread:update"
            ]
        }
    },
    ObjectType.TEAM: {
        "owner": {
            "description": "Full team access and management",
            "permissions": [
                "team:read",
                "team:update",
                "team:delete",
                "team:manage_members"
            ]
        },
        "admin": {
            "description": "Team administration access",
            "permissions": [
                "team:read",
                "team:update",
                "team:manage_members"
            ]
        },
        "member": {
            "description": "Basic team access",
            "permissions": [
                "team:read"
            ]
        }
    }
}

def create_system_roles(db):
    """Create system roles if they don't exist"""
    for role_name, role_info in SYSTEM_ROLES.items():
        role = db.query(Role).filter(Role.name == role_name).first()
        if not role:
            role = Role(
                name=role_name,
                description=role_info["description"],
                role_type=role_info["type"],
                object_type=role_info["object_type"]
            )
            db.add(role)
    db.commit()

def create_external_roles(db):
    """Create external roles for each object type if they don't exist"""
    for object_type, roles in EXTERNAL_ROLES.items():
        for role_name, role_info in roles.items():
            full_role_name = f"{object_type.value}_{role_name}"
            role = db.query(Role).filter(Role.name == full_role_name).first()
            if not role:
                role = Role(
                    name=full_role_name,
                    description=role_info["description"],
                    role_type=RoleType.EXTERNAL,
                    object_type=object_type
                )
                db.add(role)
    db.commit()

def initialize_rbac(db):
    """Initialize RBAC system with default roles"""
    create_system_roles(db)
    create_external_roles(db) 
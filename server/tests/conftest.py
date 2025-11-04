import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models.rbac import Role, Permission
from app.models.user import User
from app.models.team import Team
from app.models.workspace import Workspace
from app.models.thread import Thread

# Test database URL
TEST_DATABASE_URL = "postgresql://postgres:Test%40123@localhost:5432/genai"

@pytest.fixture(scope="session")
def engine():
    """Create a test database engine"""
    engine = create_engine(TEST_DATABASE_URL)
    return engine

@pytest.fixture(scope="session")
def tables(engine):
    """Create all tables in the test database"""
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)

@pytest.fixture
def db_session(engine, tables):
    """Create a new database session for a test"""
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture
def db(db_session):
    """Return a database session"""
    return db_session

@pytest.fixture
def init_rbac(db):
    """Initialize RBAC system with roles and permissions"""
    # Create roles
    roles = {
        "superuser": Role(name="superuser", description="Full system access"),
        "workspace_admin": Role(name="workspace_admin", description="Can manage workspaces"),
        "project_admin": Role(name="project_admin", description="Can manage projects"),
        "user": Role(name="user", description="Basic user access")
    }
    
    for role in roles.values():
        db.add(role)
    db.commit()
    
    # Create permissions
    permissions = {
        "workspace:create": Permission(name="workspace:create", description="Create workspaces"),
        "workspace:read": Permission(name="workspace:read", description="View workspaces"),
        "workspace:update": Permission(name="workspace:update", description="Update workspaces"),
        "workspace:delete": Permission(name="workspace:delete", description="Delete workspaces"),
        "project:create": Permission(name="project:create", description="Create projects"),
        "project:read": Permission(name="project:read", description="View projects"),
        "project:update": Permission(name="project:update", description="Update projects"),
        "project:delete": Permission(name="project:delete", description="Delete projects"),
        "thread:create": Permission(name="thread:create", description="Create threads"),
        "thread:read": Permission(name="thread:read", description="View threads"),
        "thread:update": Permission(name="thread:update", description="Update threads"),
        "thread:delete": Permission(name="thread:delete", description="Delete threads")
    }
    
    for permission in permissions.values():
        db.add(permission)
    db.commit()
    
    # Assign permissions to roles
    # Superuser gets all permissions
    for permission in permissions.values():
        roles["superuser"].permissions.append(permission)
    
    # Workspace admin permissions
    workspace_permissions = [p for p in permissions.values() if p.name.startswith("workspace:")]
    project_permissions = [p for p in permissions.values() if p.name.startswith("project:")]
    thread_permissions = [p for p in permissions.values() if p.name.startswith("thread:")]
    
    for permission in workspace_permissions + project_permissions + thread_permissions:
        roles["workspace_admin"].permissions.append(permission)
    
    # Project admin permissions
    for permission in project_permissions + thread_permissions:
        roles["project_admin"].permissions.append(permission)
    
    # Basic user permissions
    basic_permissions = [
        permissions["workspace:read"],
        permissions["project:read"],
        permissions["thread:create"],
        permissions["thread:read"],
        permissions["thread:update"]
    ]
    for permission in basic_permissions:
        roles["user"].permissions.append(permission)
    
    db.commit()
    return roles 
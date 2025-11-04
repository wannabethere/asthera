import pytest
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.team import Team, TeamMembership
from app.models.workspace import Workspace, WorkspaceAccess, Project
from app.models.thread import Thread, ThreadMessage
from app.models.rbac import Role, Permission
from app.database import get_db
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def test_complete_workflow(db: Session):
    """Test the complete workflow from user signup to thread creation"""
    
    # 0. Create roles and permissions first
    # Create permissions
    permissions = {
        "workspace": Permission(name="workspace", description="Workspace management"),
        "project": Permission(name="project", description="Project management"),
        "thread": Permission(name="thread", description="Thread management")
    }
    for perm in permissions.values():
        db.add(perm)
    db.commit()
    
    # Create roles
    roles = {
        "superuser": Role(
            name="superuser",
            description="Superuser with all permissions"
        ),
        "user": Role(
            name="user",
            description="Regular user"
        )
    }
    
    # Assign permissions to roles
    roles["superuser"].permissions.extend([
        permissions["workspace"],
        permissions["project"],
        permissions["thread"]
    ])
    roles["user"].permissions.extend([
        permissions["thread"]
    ])
    
    for role in roles.values():
        db.add(role)
    db.commit()
    
    # 1. Create admin user
    admin = User(
        email="admin@example.com",
        username="admin",
        password_hash=pwd_context.hash("admin123"),
        first_name="Admin",
        last_name="User",
        is_active=True,
        is_superuser=True
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    
    # Assign superuser role
    admin.roles.append(roles["superuser"])
    db.commit()
    
    # 2. Create regular users
    users = []
    for i in range(3):
        user = User(
            email=f"user{i}@example.com",
            username=f"user{i}",
            password_hash=pwd_context.hash("password123"),
            first_name=f"User{i}",
            last_name="Test",
            is_active=True
        )
        db.add(user)
        users.append(user)
    db.commit()
    
    # Assign basic user role to regular users
    for user in users:
        user.roles.append(roles["user"])
    db.commit()
    
    # 3. Create a team
    team = Team(
        name="Test Team",
        created_by=admin.id
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    
    # Add users to team
    for user in users:
        membership = TeamMembership(
            team_id=team.id,
            user_id=user.id,
            role="member"
        )
        db.add(membership)
    db.commit()
    
    # 4. Create a workspace
    workspace = Workspace(
        name="Test Workspace",
        description="A test workspace",
        team_id=team.id
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    
    # Add workspace access for users
    for user in users:
        access = WorkspaceAccess(
            workspace_id=workspace.id,
            user_id=user.id,
            is_admin=False,
            can_create=True,
            can_delete=False
        )
        db.add(access)
    db.commit()
    
    # 5. Create a project
    project = Project(
        name="Test Project",
        description="A test project",
        workspace_id=workspace.id
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    
    # 6. Create a thread
    thread = Thread(
        title="Test Thread",
        content="This is a test thread",
        project_id=project.id,
        created_by=users[0].id
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    
    # 7. Add messages to the thread
    for i, user in enumerate(users):
        message = ThreadMessage(
            thread_id=thread.id,
            content=f"Message {i+1} from {user.username}",
            user_id=user.id
        )
        db.add(message)
    db.commit()
    
    # 8. Verify all relationships
    # Verify team memberships
    assert len(team.members) == 3
    assert all(member.role == "member" for member in team.members)
    
    # Verify workspace access
    assert len(workspace.access) == 3
    assert all(access.can_create for access in workspace.access)
    
    # Verify thread messages
    assert len(thread.messages) == 3
    assert all(msg.content.startswith("Message") for msg in thread.messages)
    
    # Verify user roles
    assert admin.roles[0].name == "superuser"
    assert all(user.roles[0].name == "user" for user in users)
    
    # 9. Test collaboration
    # Add a new user to the team
    new_user = User(
        email="newuser@example.com",
        username="newuser",
        password_hash=pwd_context.hash("password123"),
        first_name="New",
        last_name="User",
        is_active=True
    )
    db.add(new_user)
    new_user.roles.append(roles["user"])
    db.commit()
    
    # Add new user to team
    new_membership = TeamMembership(
        team_id=team.id,
        user_id=new_user.id,
        role="member"
    )
    db.add(new_membership)
    
    # Add new user to workspace
    new_access = WorkspaceAccess(
        workspace_id=workspace.id,
        user_id=new_user.id,
        is_admin=False,
        can_create=True,
        can_delete=False
    )
    db.add(new_access)
    db.commit()
    
    # Verify new user can access the thread
    assert new_user in [member.user for member in team.members]
    assert new_user in [access.user for access in workspace.access]
    
    # Note: We're not cleaning up the database after the test
    # This allows us to inspect the data after the test runs
    # and helps with debugging 
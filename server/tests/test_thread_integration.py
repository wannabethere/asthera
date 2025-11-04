import pytest
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.team import Team, TeamMembership, TeamInvite
from app.models.workspace import Workspace, WorkspaceAccess, WorkspaceInvite
from app.models.workspace import Project, ProjectAccess
from app.models.thread import Thread, ThreadMessage
from app.models.rbac import Role, Permission
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def test_thread_workflow(db: Session):
    """Test the complete thread workflow including invitations and collaboration"""
    
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
        "workspace_admin": Role(
            name="workspace_admin",
            description="Workspace administrator"
        ),
        "user": Role(
            name="user",
            description="Regular user"
        )
    }
    
    # Assign permissions to roles
    roles["workspace_admin"].permissions.extend([
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
    
    # 1. Create team owner
    team_owner = User(
        email="team_owner@example.com",
        username="team_owner",
        password_hash=pwd_context.hash("password123"),
        first_name="Team",
        last_name="Owner",
        is_active=True
    )
    db.add(team_owner)
    db.commit()
    
    # Assign workspace_admin role to team owner
    team_owner.roles.append(roles["workspace_admin"])
    db.commit()
    
    # 2. Create a team
    team = Team(
        name="Thread Test Team",
        description="Team for thread testing",
        created_by=team_owner.id
    )
    db.add(team)
    db.commit()
    
    # Add team owner as team member
    owner_membership = TeamMembership(
        team_id=team.id,
        user_id=team_owner.id,
        role="admin"
    )
    db.add(owner_membership)
    db.commit()
    
    # 3. Create a workspace
    workspace = Workspace(
        name="Thread Test Workspace",
        description="Workspace for thread testing",
        team_id=team.id
    )
    db.add(workspace)
    db.commit()
    
    # Add workspace access for team owner
    owner_access = WorkspaceAccess(
        workspace_id=workspace.id,
        user_id=team_owner.id,
        is_admin=True,
        can_create=True,
        can_delete=True
    )
    db.add(owner_access)
    db.commit()
    
    # 4. Create a project
    project = Project(
        name="Thread Test Project",
        description="Project for thread testing",
        workspace_id=workspace.id
    )
    db.add(project)
    db.commit()
    
    # Add project access for team owner
    owner_project_access = ProjectAccess(
        project_id=project.id,
        user_id=team_owner.id,
        is_admin=True,
        can_create=True,
        can_delete=True
    )
    db.add(owner_project_access)
    db.commit()
    
    # 5. Create initial thread
    initial_thread = Thread(
        title="Initial Discussion",
        content="Let's start the discussion",
        project_id=project.id,
        created_by=team_owner.id
    )
    db.add(initial_thread)
    db.commit()
    
    # 6. Create and invite new users
    new_users = []
    for i in range(2):
        # Create user
        user = User(
            email=f"thread_user{i}@example.com",
            username=f"thread_user{i}",
            password_hash=pwd_context.hash("password123"),
            first_name=f"Thread{i}",
            last_name="User",
            is_active=True
        )
        db.add(user)
        new_users.append(user)
    db.commit()
    
    # Assign basic user role
    for user in new_users:
        user.roles.append(roles["user"])
    db.commit()
    
    # Send team invites
    for user in new_users:
        team_invite = TeamInvite(
            team_id=team.id,
            email=user.email,
            role="member",
            invited_by=team_owner.id
        )
        db.add(team_invite)
    db.commit()
    
    # Accept team invites (simulate acceptance)
    for user in new_users:
        membership = TeamMembership(
            team_id=team.id,
            user_id=user.id,
            role="member"
        )
        db.add(membership)
    db.commit()
    
    # Send workspace invites
    for user in new_users:
        workspace_invite = WorkspaceInvite(
            workspace_id=workspace.id,
            email=user.email,
            role="member",
            invited_by=team_owner.id
        )
        db.add(workspace_invite)
    db.commit()
    
    # Accept workspace invites (simulate acceptance)
    for user in new_users:
        access = WorkspaceAccess(
            workspace_id=workspace.id,
            user_id=user.id,
            is_admin=False,
            can_create=True,
            can_delete=False
        )
        db.add(access)
    db.commit()
    
    # 7. Add messages to the initial thread
    for i, user in enumerate(new_users):
        message = ThreadMessage(
            thread_id=initial_thread.id,
            content=f"Hello, I'm {user.username}!",
            user_id=user.id
        )
        db.add(message)
    db.commit()
    
    # 8. Create a new thread by one of the new users
    new_thread = Thread(
        title="Follow-up Discussion",
        content="Let's continue the discussion",
        project_id=project.id,
        created_by=new_users[0].id
    )
    db.add(new_thread)
    db.commit()
    
    # 9. Add messages to the new thread
    for i, user in enumerate([team_owner] + new_users):
        message = ThreadMessage(
            thread_id=new_thread.id,
            content=f"Message {i+1} from {user.username}",
            user_id=user.id
        )
        db.add(message)
    db.commit()
    
    # 10. Verify all relationships and data
    # Verify team memberships
    assert len(team.members) == 3  # owner + 2 new users
    assert any(member.role == "admin" for member in team.members)
    assert all(user in [member.user for member in team.members] for user in new_users)
    
    # Verify workspace access
    assert len(workspace.access) == 3
    assert any(access.is_admin for access in workspace.access)
    assert all(user in [access.user for access in workspace.access] for user in new_users)
    
    # Verify threads and messages
    assert len(project.threads) == 2
    assert len(initial_thread.messages) == 2  # 2 new users
    assert len(new_thread.messages) == 3  # owner + 2 new users
    
    # Verify thread creators
    assert initial_thread.creator == team_owner
    assert new_thread.creator == new_users[0]
    
    # Verify message authors
    assert all(msg.created_by in [user.id for user in new_users] for msg in initial_thread.messages)
    assert all(msg.created_by in [user.id for user in [team_owner] + new_users] for msg in new_thread.messages)
    
    # 11. List all threads with their messages
    all_threads = db.query(Thread).filter(Thread.project_id == project.id).all()
    for thread in all_threads:
        print(f"\nThread: {thread.title}")
        print(f"Created by: {thread.creator.username}")
        print("Messages:")
        for msg in thread.messages:
            print(f"- {msg.creator.username}: {msg.content}")
    
    # Note: We're not cleaning up the database after the test
    # This allows us to inspect the data after the test runs
    # and helps with debugging 
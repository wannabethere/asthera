import pytest
from app.services.user_service import UserService
from app.models.user import User
from app.models.team import Team
from app.models.workspace import Workspace, Project
from app.models.thread import Thread
from sqlalchemy.orm import Session
from uuid import uuid4

def create_user(db, username):
    user = User(email=f"{username}@test.com", username=username, password_hash="test")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def create_team(db, owner):
    team = Team(name=f"{owner.username}'s Team", created_by=owner.id, owner_id=owner.id)
    db.add(team)
    db.commit()
    db.refresh(team)
    return team

def create_workspace(db, team):
    ws = Workspace(name="Test Workspace", team_id=team.id)
    db.add(ws)
    db.commit()
    db.refresh(ws)
    return ws

def create_project(db, ws):
    project = Project(name="Test Project", workspace_id=ws.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

def create_thread(db, project, creator):
    thread = Thread(project_id=project.id, created_by=creator.id, title="Test Thread", description="desc")
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread

@pytest.fixture
def user_service(db_session):
    return UserService(db_session)

@pytest.fixture
def setup_entities(db_session):
    user1 = create_user(db_session, "user1")
    user2 = create_user(db_session, "user2")
    team = create_team(db_session, user1)
    ws = create_workspace(db_session, team)
    project = create_project(db_session, ws)
    thread = create_thread(db_session, project, user1)
    return dict(user1=user1, user2=user2, team=team, ws=ws, project=project, thread=thread)

def test_get_users_for_team(user_service, setup_entities, db_session):
    user1, team = setup_entities["user1"], setup_entities["team"]
    users = user_service.get_users_for_team(team.id)
    assert any(u.id == user1.id for u in users)

def test_get_users_for_project(user_service, setup_entities, db_session):
    user1, project = setup_entities["user1"], setup_entities["project"]
    users = user_service.get_users_for_project(project.id)
    # User1 should have access by default creation
    assert any(u.id == user1.id for u in users)

def test_get_users_for_workspace(user_service, setup_entities, db_session):
    user1, ws = setup_entities["user1"], setup_entities["ws"]
    users = user_service.get_users_for_workspace(ws.id)
    assert any(u.id == user1.id for u in users)

def test_get_users_for_thread(user_service, setup_entities, db_session):
    user1, thread = setup_entities["user1"], setup_entities["thread"]
    users = user_service.get_users_for_thread(thread.id)
    assert any(u.id == user1.id for u in users)

def test_get_connected_users_via_teams(user_service, setup_entities, db_session):
    user1, user2, team = setup_entities["user1"], setup_entities["user2"], setup_entities["team"]
    # Add user2 to the same team
    from app.models.team import team_memberships
    db_session.execute(team_memberships.insert().values(team_id=team.id, user_id=user2.id, role="member"))
    db_session.commit()
    users = user_service.get_connected_users_via_teams(user1.id)
    assert any(u.id == user2.id for u in users) 
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.user_service import UserService
from app.schemas.user import UserResponse, user_to_response
from app.auth.okta import get_current_user
from app.models.user import User
from uuid import UUID
from typing import List
from app.services.system_info_service import SystemInfoService

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/team/{team_id}", response_model=List[UserResponse])
def get_users_for_team(team_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    service = UserService(db)
    users = service.get_users_for_team(team_id)
    return [user_to_response(u) for u in users]

@router.get("/project/{project_id}", response_model=List[UserResponse])
def get_users_for_project(project_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    service = UserService(db)
    users = service.get_users_for_project(project_id)
    return [user_to_response(u) for u in users]

@router.get("/workspace/{workspace_id}", response_model=List[UserResponse])
def get_users_for_workspace(workspace_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    service = UserService(db)
    users = service.get_users_for_workspace(workspace_id)
    return [user_to_response(u) for u in users]

@router.get("/thread/{thread_id}", response_model=List[UserResponse])
def get_users_for_thread(thread_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    service = UserService(db)
    users = service.get_users_for_thread(thread_id)
    return [user_to_response(u) for u in users]

@router.get("/connected", response_model=List[UserResponse])
def get_connected_users_via_teams(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    service = UserService(db)
    users = service.get_connected_users_via_teams(current_user.id)
    return [user_to_response(u) for u in users]

@router.get("/system-info")
def get_system_info(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    service = SystemInfoService(db)
    roles = service.get_all_roles()
    permissions = service.get_permissions_for_user(current_user)
    workspaces = service.get_workspaces_for_user(current_user)
    teams = service.get_teams_for_user(current_user)
    projects = service.get_projects_for_user(current_user)
    default_roles = service.get_default_roles()
    default_permissions = service.get_authenticated_user_permissions()
    default_project_id = service.get_default_project_id()
    default_workspace_id = service.get_default_workspace_id()
    return {
        "roles": [r.name for r in roles],
        "permissions": permissions,
        "workspaces": [{"id": str(w.id), "name": w.name} for w in workspaces],
        "teams": [{"id": str(t.id), "name": t.name} for t in teams],
        "projects": [{"id": str(p.id), "name": p.name} for p in projects],
        "default_roles": default_roles,
        "authenticated_user_permissions": default_permissions,
        "default_project_id": default_project_id,
        "default_workspace_id": default_workspace_id
    } 
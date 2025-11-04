from fastapi import HTTPException, status, Depends
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.workspace import WorkspaceAccess, Workspace, ProjectAccess, Project
from app.models.rbac import Role, Permission
from app.models.team import team_memberships
from app.database import get_db
from app.auth.okta import get_current_user

def user_has_permission(user: User, permission_name: str) -> bool:
    for role in user.roles:
        for perm in role.permissions:
            if perm.name == permission_name or perm.name == "*":
                return True
    return False

def check_team_access(db: Session, team_id: str, user_id: str, require_owner: bool = False) -> bool:
    user = db.query(User).filter(User.id == user_id).first()
    if user and user.is_superuser:
        return True

    # Query the team_memberships table directly
    membership = db.query(team_memberships).filter(
        team_memberships.c.team_id == team_id,
        team_memberships.c.user_id == user_id
    ).first()

    if not membership:
        return False

    if require_owner and membership.role != "owner":
        return False

    return True

def check_workspace_access(db: Session, workspace_id: str, user_id: str, require_admin: bool = False, require_create: bool = False, require_delete: bool = False) -> bool:
    user = db.query(User).filter(User.id == user_id).first()
    if user and user.is_superuser:
        return True

    # First check if user has direct workspace access
    access = db.query(WorkspaceAccess).filter(
        WorkspaceAccess.workspace_id == workspace_id,
        WorkspaceAccess.user_id == user_id
    ).first()

    if access:
        if require_admin and not access.is_admin:
            return False
        if require_create and not access.can_create:
            return False
        if require_delete and not access.can_delete:
            return False
        return True

    # If no direct access, check if user is team owner
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if workspace:
        return check_team_access(db, workspace.team_id, user_id, require_owner=True)

    return False

def check_project_access(db: Session, project_id: str, user_id: str, require_admin: bool = False, require_create: bool = False, require_delete: bool = False) -> bool:
    user = db.query(User).filter(User.id == user_id).first()
    if user and user.is_superuser:
        return True

    # First check if user has direct project access
    access = db.query(ProjectAccess).filter(
        ProjectAccess.project_id == project_id,
        ProjectAccess.user_id == user_id
    ).first()

    if access:
        if require_admin and not access.is_admin:
            return False
        if require_create and not access.can_create:
            return False
        if require_delete and not access.can_delete:
            return False
        return True

    # If no direct access, check workspace access
    project = db.query(Project).filter(Project.id == project_id).first()
    if project:
        return check_workspace_access(db, project.workspace_id, user_id)

    return False

def require_permission(permission_name: str):
    def dependency(current_user: User = Depends(get_current_user)):
        if not user_has_permission(current_user, permission_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User does not have permission: {permission_name}"
            )
        return current_user
    return dependency

def require_team_owner(team_id: str):
    def dependency(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        if not check_team_access(db, team_id, str(current_user.id), require_owner=True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only team owner can perform this action"
            )
        return current_user
    
    return dependency

def require_workspace_admin(workspace_id: str):
    def dependency(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        if not check_workspace_access(db, workspace_id, str(current_user.id), require_admin=True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only workspace admin can perform this action"
            )
        return current_user
    return dependency
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.workspace import Workspace, Project,  WorkspaceAccess, ProjectAccess
from app.models.thread import Thread
from app.models.team import Team, team_memberships
from app.models.user import User
from app.auth.okta import get_current_user
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from sqlalchemy import select

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

# Access Control Models
class WorkspaceAccessCreate(BaseModel):
    user_id: str
    is_admin: bool = False
    can_create: bool = False
    can_delete: bool = False

class WorkspaceAccessResponse(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    is_admin: bool
    can_create: bool
    can_delete: bool
    created_at: str
    updated_at: Optional[str]
    class Config:
        orm_mode = True

class ProjectAccessCreate(BaseModel):
    user_id: str
    is_admin: bool = False
    can_create: bool = False
    can_delete: bool = False

class ProjectAccessResponse(BaseModel):
    id: str
    project_id: str
    user_id: str
    is_admin: bool
    can_create: bool
    can_delete: bool
    created_at: str
    updated_at: Optional[str]
    class Config:
        orm_mode = True

# Workspace Models
class WorkspaceCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    team_id: str

class WorkspaceResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    team_id: str
    created_at: str
    updated_at: Optional[str]
    class Config:
        orm_mode = True

# Project Models
class ProjectCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    workspace_id: str

class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    workspace_id: str
    created_at: str
    updated_at: Optional[str]
    class Config:
        orm_mode = True

# Thread Models
class ThreadCreateRequest(BaseModel):
    title: str
    content: Optional[str] = None
    project_id: str

class ThreadResponse(BaseModel):
    id: str
    title: str
    content: Optional[str]
    project_id: str
    created_by: str
    created_at: str
    updated_at: Optional[str]
    class Config:
        orm_mode = True

# Helper functions for access control
def check_workspace_access(db: Session, workspace_id: str, user_id: str, require_admin: bool = False, require_create: bool = False, require_delete: bool = False):
    # Check if user is superuser
    user = db.query(User).filter(User.id == user_id).first()
    if user and user.is_superuser:
        return True

    # Check workspace access
    access = db.query(WorkspaceAccess).filter(
        WorkspaceAccess.workspace_id == workspace_id,
        WorkspaceAccess.user_id == user_id
    ).first()

    if not access:
        return False

    if require_admin and not access.is_admin:
        return False
    if require_create and not access.can_create:
        return False
    if require_delete and not access.can_delete:
        return False

    return True

def check_project_access(db: Session, project_id: str, user_id: str, require_admin: bool = False, require_create: bool = False, require_delete: bool = False):
    # Check if user is superuser
    user = db.query(User).filter(User.id == user_id).first()
    if user and user.is_superuser:
        return True

    # Check project access
    access = db.query(ProjectAccess).filter(
        ProjectAccess.project_id == project_id,
        ProjectAccess.user_id == user_id
    ).first()

    if not access:
        return False

    if require_admin and not access.is_admin:
        return False
    if require_create and not access.can_create:
        return False
    if require_delete and not access.can_delete:
        return False

    return True

def user_has_permission(user: User, permission_name: str) -> bool:
    for role in user.roles:
        for perm in role.permissions:
            if perm.name == permission_name or perm.name == "*":
                return True
    return False

# Workspace Routes
@router.post("/", response_model=WorkspaceResponse)
async def create_workspace(
    req: WorkspaceCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check if user is team member
    membership = db.execute(
        select(team_memberships).where(
            team_memberships.c.team_id == req.team_id,
            team_memberships.c.user_id == str(current_user.id)
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Not a team member")

    workspace = Workspace(
        name=req.name,
        description=req.description,
        team_id=req.team_id
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)

    # Create default admin access for the creator
    access = WorkspaceAccess(
        workspace_id=workspace.id,
        user_id=str(current_user.id),
        is_admin=True,
        can_create=True,
        can_delete=True
    )
    db.add(access)
    db.commit()

    return {
  "id": str(workspace.id),
  "name": workspace.name,
  "description": workspace.description,
  "team_id": str(workspace.team_id),
  "created_at": str(workspace.created_at),
  "updated_at": str(workspace.updated_at)
}

@router.get("/", response_model=List[WorkspaceResponse])
async def list_workspaces(
    team_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Workspace)
    if team_id:
        # Check if user is team member
        membership = db.execute(
            select(team_memberships).where(
                team_memberships.c.team_id == team_id,
                team_memberships.c.user_id == str(current_user.id)
            )
        ).first()
        if not membership:
            raise HTTPException(status_code=403, detail="Not a team member")
        query = query.filter(Workspace.team_id == team_id)
    else:
        # Get all teams where user is a member
        memberships = db.execute(
            select(team_memberships).where(
                team_memberships.c.user_id == str(current_user.id)
            )
        ).all()
        team_ids = [m.team_id for m in memberships]
        query = query.filter(Workspace.team_id.in_(team_ids))
    
    return [
        {
  "id": str(workspace.id),
  "name": workspace.name,
  "description": workspace.description,
  "team_id": str(workspace.team_id),
  "created_at": str(workspace.created_at),
  "updated_at": str(workspace.updated_at)
}

    for workspace in query.all()]

# Project Routes
@router.post("/projects", response_model=ProjectResponse)
async def create_project(
    req: ProjectCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check if workspace exists and user has access
    workspace = db.query(Workspace).filter(Workspace.id == req.workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    if not check_workspace_access(db, req.workspace_id, str(current_user.id), require_create=True):
        raise HTTPException(status_code=403, detail="Not authorized to create projects in this workspace")

    project = Project(
        name=req.name,
        description=req.description,
        workspace_id=req.workspace_id
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    # Create default admin access for the creator
    access = ProjectAccess(
        project_id=project.id,
        user_id=str(current_user.id),
        is_admin=True,
        can_create=True,
        can_delete=True
    )
    db.add(access)
    db.commit()

    return {
  "id": str(project.id),
  "name": project.name,
  "description": project.description,
  "workspace_id": str(project.id),
  "created_at": str(project.created_at),
  "updated_at": str(project.updated_at)
}

@router.get("/projects", response_model=List[ProjectResponse])
async def list_projects(
    workspace_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Project)
    if workspace_id:
        # Check if user has access to workspace
        workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")
        
        if not check_workspace_access(db, workspace_id, str(current_user.id)):
            raise HTTPException(status_code=403, detail="Not authorized to access this workspace")
        
        query = query.filter(Project.workspace_id == workspace_id)
    else:
        # Get all workspaces where user has access
        memberships = db.execute(
            select(team_memberships).where(
                team_memberships.c.user_id == str(current_user.id)
            )
        ).all()
        team_ids = [m.team_id for m in memberships]
        workspaces = db.query(Workspace).filter(Workspace.team_id.in_(team_ids)).all()
        workspace_ids = [w.id for w in workspaces]
        query = query.filter(Project.workspace_id.in_(workspace_ids))
    
    return [
        {
  "id": str(project.id),
  "name": project.name,
  "description": project.description,
  "workspace_id": str(project.id),
  "created_at": str(project.created_at),
  "updated_at": str(project.updated_at)
}
    for project in query.all()]

# Thread Routes
@router.post("/threads", response_model=ThreadResponse)
async def create_thread(
    req: ThreadCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check if project exists and user has access
    project = db.query(Project).filter(Project.id == req.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Any user with access to the project can create threads
    if not check_project_access(db, req.project_id, str(current_user.id)):
        raise HTTPException(status_code=403, detail="Not authorized to access this project")

    thread = Thread(
        title=req.title,
        description=req.content,
        project_id=req.project_id,
        created_by=str(current_user.id)
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return {
  "id": str(thread.id),
  "title": thread.title,
  "content": thread.description,
  "project_id": str(thread.project_id),
  "created_by": str(thread.created_by),
  "created_at": str(thread.created_at),
  "updated_at": str(thread.updated_at)
}

@router.get("/threads", response_model=List[ThreadResponse])
async def list_threads(
    project_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Thread)
    if project_id:
        # Check if user has access to project
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        if not check_project_access(db, project_id, str(current_user.id)):
            raise HTTPException(status_code=403, detail="Not authorized to access this project")
        
        query = query.filter(Thread.project_id == project_id)
    else:
        # Get all projects where user has access
        memberships = db.execute(
            select(team_memberships).where(
                team_memberships.c.user_id == str(current_user.id)
            )
        ).all()
        team_ids = [m.team_id for m in memberships]
        workspaces = db.query(Workspace).filter(Workspace.team_id.in_(team_ids)).all()
        workspace_ids = [w.id for w in workspaces]
        projects = db.query(Project).filter(Project.workspace_id.in_(workspace_ids)).all()
        project_ids = [p.id for p in projects]
        query = query.filter(Thread.project_id.in_(project_ids))
    
    return [ 
        {
  "id": str(thread.id),
  "title": thread.title,
  "content": thread.description,
  "project_id": str(thread.project_id),
  "created_by": str(thread.created_by),
  "created_at": str(thread.created_at),
  "updated_at": str(thread.updated_at)
}
        for thread in  query.all()]

# Workspace Access Routes
@router.post("/{workspace_id}/access", response_model=WorkspaceAccessResponse)
async def create_workspace_access(
    workspace_id: str,
    req: WorkspaceAccessCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check if workspace exists
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Check if current user has admin access
    if not check_workspace_access(db, workspace_id, str(current_user.id), require_admin=True):
        raise HTTPException(status_code=403, detail="Not authorized to manage workspace access")

    # Check if access already exists
    existing_access = db.query(WorkspaceAccess).filter(
        WorkspaceAccess.workspace_id == workspace_id,
        WorkspaceAccess.user_id == req.user_id
    ).first()
    if existing_access:
        raise HTTPException(status_code=400, detail="Access already exists for this user")

    access = WorkspaceAccess(
        workspace_id=workspace_id,
        user_id=req.user_id,
        is_admin=req.is_admin,
        can_create=req.can_create,
        can_delete=req.can_delete
    )
    db.add(access)
    db.commit()
    db.refresh(access)
    return {
  "id": str(access.id),
  "workspace_id": str(access.workspace_id),
  "user_id": str(access.user_id),
  "is_admin": access.is_admin,
  "can_create": access.can_create,
  "can_delete": access.can_delete,
  "created_at": str(access.created_at),
  "updated_at": str(access.updated_at)
}

@router.get("/{workspace_id}/access", response_model=List[WorkspaceAccessResponse])
async def list_workspace_access(
    workspace_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check if workspace exists
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Check if current user has access
    if not check_workspace_access(db, workspace_id, str(current_user.id)):
        raise HTTPException(status_code=403, detail="Not authorized to view workspace access")

    return [ 
        {
  "id": str(access.id),
  "workspace_id": str(access.workspace_id),
  "user_id": str(access.user_id),
  "is_admin": access.is_admin,
  "can_create": access.can_create,
  "can_delete": access.can_delete,
  "created_at": str(access.created_at),
  "updated_at": str(access.updated_at)
    }
        for access in db.query(WorkspaceAccess).filter(WorkspaceAccess.workspace_id == workspace_id).all()]

# Project Access Routes
@router.post("/projects/{project_id}/access", response_model=ProjectAccessResponse)
async def create_project_access(
    project_id: str,
    req: ProjectAccessCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check if project exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if current user has admin access to the workspace
    if not check_workspace_access(db, project.workspace_id, str(current_user.id), require_admin=True):
        raise HTTPException(status_code=403, detail="Not authorized to manage project access")

    # Check if access already exists
    existing_access = db.query(ProjectAccess).filter(
        ProjectAccess.project_id == project_id,
        ProjectAccess.user_id == req.user_id
    ).first()
    if existing_access:
        raise HTTPException(status_code=400, detail="Access already exists for this user")

    access = ProjectAccess(
        project_id=project_id,
        user_id=req.user_id,
        is_admin=req.is_admin,
        can_create=req.can_create,
        can_delete=req.can_delete
    )
    db.add(access)
    db.commit()
    db.refresh(access)
    return {
  "id": str(access.id),
  "project_id": str(access.project_id),
  "user_id": str(access.user_id),
  "is_admin": access.is_admin,
  "can_create": access.can_create,
  "can_delete": access.can_delete,
  "created_at": str(access.created_at),
  "updated_at": str(access.updated_at)
}

@router.get("/projects/{project_id}/access", response_model=List[ProjectAccessResponse])
async def list_project_access(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check if project exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if current user has access to the workspace
    if not check_workspace_access(db, project.workspace_id, str(current_user.id)):
        raise HTTPException(status_code=403, detail="Not authorized to view project access")

    return [
        {
  "id": str(access.id),
  "project_id": str(access.project_id),
  "user_id": str(access.user_id),
  "is_admin": access.is_admin,
  "can_create": access.can_create,
  "can_delete": access.can_delete,
  "created_at": str(access.created_at),
  "updated_at": str(access.updated_at)
} for access in db.query(ProjectAccess).filter(ProjectAccess.project_id == project_id).all()] 
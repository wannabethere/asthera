from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session,joinedload
from app.database import get_db
from app.models.team import Team, TeamInvite, CollaborationRequest, TeamSignupRequest
from app.models.workspace import Workspace, WorkspaceInvite, WorkspaceAccess
from app.models.user import User
from app.auth.okta import get_current_user
from app.services.team_service import TeamService

from pydantic import BaseModel, EmailStr
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from app.services.authorization import (
    check_team_access,
    check_workspace_access,
    require_team_owner,
    require_workspace_admin
)

router = APIRouter(prefix="/invites", tags=["invites"])

class InviteCreate(BaseModel):
    email: EmailStr
    team_id: Optional[UUID] = None
    workspace_id: Optional[UUID] = None
    role: str = "member"

class InviteResponse(BaseModel):
    id: UUID
    email: str
    team_id: Optional[UUID] = None
    workspace_id: Optional[UUID] =None
    role: str
    status: str
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True



@router.post("/team", response_model=InviteResponse)
async def send_team_invite(
    req: InviteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not req.team_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team ID is required for team invites"
        )

    # Check if user is team owner
    require_team_owner(req.team_id)(current_user, db)

    # Check if invite already exists
    existing_invite = db.query(TeamInvite).filter(
        TeamInvite.team_id == req.team_id,
        TeamInvite.email == req.email,
        TeamInvite.status == "pending"
    ).first()

    if existing_invite:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An active invite already exists for this email"
        )

    # Create new invite
    invite = TeamInvite(
        team_id=req.team_id,
        email=req.email,
        role=req.role,
        invited_by=str(current_user.id)
    )
    
    db.add(invite)
    db.commit()
    db.refresh(invite)
    
    return {
        "id": str(invite.id),
    "email": invite.email,
    "team_id": str(invite.team_id),
    "workspace_id":None,
    "role": invite.role,
    "status": invite.status,
    "created_by": str(invite.invited_by),
    "created_at": invite.created_at,
    "updated_at": invite.updated_at,
    }

@router.post("/workspace", response_model=InviteResponse)
async def send_workspace_invite(
    req: InviteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not req.workspace_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workspace ID is required for workspace invites"
        )

    # Check if user is workspace admin
    require_workspace_admin(req.workspace_id)(current_user, db)

    # Check if invite already exists
    existing_invite = db.query(WorkspaceInvite).filter(
        WorkspaceInvite.workspace_id == req.workspace_id,
        WorkspaceInvite.email == req.email,
        WorkspaceInvite.status == "pending"
    ).first()

    if existing_invite:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An active invite already exists for this email"
        )

    # Create new invite
    invite = WorkspaceInvite(
        workspace_id=req.workspace_id,
        email=req.email,
        role=req.role,
        invited_by=str(current_user.id)
    )
    
    db.add(invite)
    db.commit()
    db.refresh(invite)
    
    return {
        "id": str(invite.id),
    "email": invite.email,
    "team_id": None,
    "workspace_id":str(invite.workspace_id),
    "role": invite.role,
    "status": invite.status,
    "created_by": str(invite.invited_by),

    "created_at": invite.created_at,
    "updated_at": invite.updated_at,
    }

@router.get("/")#, response_model=List[InviteResponse]
async def list_invites(
    team_id: Optional[UUID] = None,
    workspace_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Initialize empty lists for both types of invites
    team_invites = []
    workspace_invites = []
 
    # Query team invites
    team_query = db.query(TeamInvite).filter(TeamInvite.email == current_user.email)
    if team_id:
        # Check if user is team owner
        # await require_team_owner(team_id)(current_user, db)
        team_query = team_query.filter(TeamInvite.team_id == team_id)
    elif not workspace_id:
        # If no specific team_id or workspace_id, get all team invites for the user
        team_invites = team_query.all()
 
    # Query workspace invites
    workspace_query = db.query(WorkspaceInvite).filter(WorkspaceInvite.email == current_user.email)
    if workspace_id:
        # Check if user is workspace admin
        # await require_workspace_admin(workspace_id)(current_user, db)
        workspace_query = workspace_query.filter(WorkspaceInvite.workspace_id == workspace_id)
    elif not team_id:
        # If no specific team_id or workspace_id, get all workspace invites for the user
        workspace_invites = workspace_query.all()
 
    # Combine both types of invites
    all_invites = team_invites + workspace_invites
    
    # Sort by created_at in descending order
    all_invites.sort(key=lambda x: x.created_at, reverse=True)
    
    return all_invites
 

@router.get("/{invite_id}")#, response_model=InviteResponse Removed part
async def get_invite(
    invite_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # invite = db.query(TeamInvite).filter(TeamInvite.id == invite_id).first()
    # if not invite:
    #     raise HTTPException(
    #         status_code=status.HTTP_404_NOT_FOUND,
    #         detail="Invite not found"
    #     )

    # Check if user has permission to view the invite
    teamInvite =  db.query(TeamInvite).filter(TeamInvite.id == invite_id).options(joinedload(TeamInvite.inviter),joinedload(TeamInvite.team)).first()
    workspaceInvite =  db.query(WorkspaceInvite).options(joinedload(WorkspaceInvite.inviter),joinedload(WorkspaceInvite.workspace)).filter(WorkspaceInvite.id == invite_id).first()
    if teamInvite:
        return {
            "id":str(teamInvite.id),
            "team_name":teamInvite.team.name if teamInvite.team else None,
            "role":teamInvite.role,
            "invited_by":f'{teamInvite.inviter.first_name} {teamInvite.inviter.last_name}' if teamInvite.inviter else None,
            "status":teamInvite.status,
            "created_at":str(teamInvite.created_at),
            "updated_at":str(teamInvite.updated_at) if teamInvite.updated_at else None,
            "email":teamInvite.email

        }
    elif workspaceInvite:
        return {
            "id":str(workspaceInvite.id),
            "workspace_name":workspaceInvite.workspace.name if workspaceInvite.workspace else None,
            "role":workspaceInvite.role,
            "invited_by":f'{workspaceInvite.inviter.first_name} {workspaceInvite.inviter.last_name}' if workspaceInvite else None,
            "status":workspaceInvite.status,
            "created_at":str(workspaceInvite.created_at),
            "updated_at":str(workspaceInvite.updated_at) if workspaceInvite.updated_at else None,
            "email":workspaceInvite.email}

        
    elif teamInvite and teamInvite.invited_by !=current_user.id and workspaceInvite.invited_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this invite"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found"
        )
    # if invite.team_id:
    #     # require_team_owner(invite.team_id)(current_user, db)
    # elif invite.workspace_id:
    #     require_workspace_admin(invite.workspace_id)(current_user, db)
    # elif invite.invited_by != current_user.id:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Not authorized to view this invite"
    #     )

    # return invite

@router.delete("/{invite_id}", response_model=InviteResponse)
async def delete_invite(
    invite_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    invite = db.query(TeamInvite).filter(TeamInvite.id == invite_id).first()
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found"
        )

    # Check if user has permission to delete the invite
    if invite.team_id:
        require_team_owner(invite.team_id)(current_user, db)
    elif invite.workspace_id:
        require_workspace_admin(invite.workspace_id)(current_user, db)
    elif invite.invited_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this invite"
        )

    invite.status = "cancelled"
    db.commit()
    db.refresh(invite)
    return invite

class InviteActionRequest(BaseModel):
    invite_id: str
    invite_type: str  # 'team' or 'workspace'
    action: str  # 'accept' or 'decline'

@router.post("/respond", response_model=InviteResponse)
async def respond_invite(
    req: InviteActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if req.invite_type == "team":
        invite = db.query(TeamInvite).filter(TeamInvite.id == req.invite_id).first()
        if not invite:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team invite not found"
            )

        if invite.email != current_user.email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This invite is not for your email"
            )

        if invite.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This invite is no longer valid"
            )

        if req.action == "accept":
            try:
                team_service = TeamService(db)
                team_service.add_team_member(
                    team_id=str(invite.team_id),
                    user_id=str(current_user.id),
                    role=invite.role
                )
                invite.status = "accepted"
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e)
                )
        else:
            invite.status = "declined"

        invite.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(invite)
        return invite

    elif req.invite_type == "workspace":
        invite = db.query(WorkspaceInvite).filter(WorkspaceInvite.id == req.invite_id).first()
        if not invite:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace invite not found"
            )

        if invite.email != current_user.email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This invite is not for your email"
            )

        if invite.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This invite is no longer valid"
            )

        if req.action == "accept":
            # Add workspace access
            access = WorkspaceAccess(
                workspace_id=invite.workspace_id,
                user_id=str(current_user.id),
                role=invite.role
            )
            db.add(access)
            invite.status = "accepted"
        else:
            invite.status = "declined"

        invite.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(invite)
        return invite

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invite type"
        ) 
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.team import Team, CollaborationRequest, TeamSignupRequest
from app.models.user import User
from app.auth.okta import get_current_user
from app.services.team_service import TeamService
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime

router = APIRouter(prefix="/teams", tags=["teams"])

class TeamCreateRequest(BaseModel):
    name: str

class TeamResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    owner_id: Optional[str] = None
    is_active: bool = True

    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }

class TeamMembershipRequest(BaseModel):
    user_id: str
    role: Optional[str] = "member"

class TeamMembershipResponse(BaseModel):
    id: str
    team_id: str
    user_id: str
    role: Optional[str]
    created_at: str
    class Config:
        orm_mode = True

class CollaborationRequestCreate(BaseModel):
    team_id: str
    message: Optional[str] = None

class CollaborationRequestResponse(BaseModel):
    id: str
    team_id: str
    requester_id: str
    status: str
    message: Optional[str]
    created_at: str
    updated_at: Optional[str]
    class Config:
        orm_mode = True

class TeamSignupRequestCreate(BaseModel):
    team_id: str
    message: Optional[str] = None

class TeamSignupRequestResponse(BaseModel):
    id: str
    team_id: str
    user_id: str
    status: str
    message: Optional[str]
    created_at: str
    updated_at: Optional[str]
    class Config:
        orm_mode = True

@router.post("", response_model=TeamResponse)
async def create_team(
    req: TeamCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        team_service = TeamService(db)
        team = team_service.create_team(req.name, current_user)
        return team
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("", response_model=List[TeamResponse])
async def list_teams(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    team_service = TeamService(db)
    return team_service.get_user_teams(str(current_user.id))

@router.post("/{team_id}/members", response_model=TeamMembershipResponse)
async def add_team_member(
    team_id: str,
    req: TeamMembershipRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        team_service = TeamService(db)
        membership = team_service.add_team_member(
            team_id=team_id,
            user_id=req.user_id,
            role=req.role,
            added_by=str(current_user.id)
        )
        return membership
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{team_id}/members", response_model=List[TeamMembershipResponse])
async def list_team_members(
    team_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        team_service = TeamService(db)
        return team_service.get_team_members(team_id, str(current_user.id))
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

@router.post("/collaboration-requests", response_model=CollaborationRequestResponse)
async def create_collaboration_request(
    req: CollaborationRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        team_service = TeamService(db)
        request = team_service.create_collaboration_request(
            team_id=req.team_id,
            requester_id=str(current_user.id),
            message=req.message
        )
        return request
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/collaboration-requests", response_model=List[CollaborationRequestResponse])
async def list_collaboration_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    team_service = TeamService(db)
    return team_service.get_collaboration_requests(str(current_user.id))

@router.post("/collaboration-requests/{request_id}/respond")
async def respond_to_collaboration_request(
    request_id: str,
    accept: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        team_service = TeamService(db)
        team_service.respond_to_collaboration_request(
            request_id=request_id,
            user_id=str(current_user.id),
            accept=accept
        )
        return {"status": "success"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/signup-requests", response_model=TeamSignupRequestResponse)
async def create_team_signup_request(
    req: TeamSignupRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        team_service = TeamService(db)
        request = team_service.create_team_signup_request(
            team_id=req.team_id,
            user_id=str(current_user.id),
            message=req.message
        )
        return request
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/signup-requests", response_model=List[TeamSignupRequestResponse])
async def list_team_signup_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    team_service = TeamService(db)
    return team_service.get_team_signup_requests(str(current_user.id))

@router.post("/signup-requests/{request_id}/respond")
async def respond_to_team_signup_request(
    request_id: str,
    accept: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        team_service = TeamService(db)
        team_service.respond_to_team_signup_request(
            request_id=request_id,
            user_id=str(current_user.id),
            accept=accept
        )
        return {"status": "success"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) 
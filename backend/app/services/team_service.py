from sqlalchemy.orm import Session
from app.models.team import Team, CollaborationRequest, TeamSignupRequest, team_memberships
from app.models.user import User
from typing import List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class TeamService:
    def __init__(self, db: Session):
        self.db = db

    def create_team(self, name: str, creator: User) -> Team:
        """Create a new team and add creator as owner"""
        if self.db.query(Team).filter(Team.name == name).first():
            raise ValueError("Team name already exists")
            
        team = Team(
            name=name,
            created_by=creator.id,
            owner_id=creator.id,
            is_active=True
        )
        self.db.add(team)
        self.db.flush()
        
        # Add creator as owner
        self.db.execute(
            team_memberships.insert().values(
                team_id=team.id,
                user_id=str(creator.id),
                role="owner",
                created_at=datetime.utcnow()
            )
        )
        self.db.commit()
        self.db.refresh(team)
        return team

    def get_user_teams(self, user_id: str) -> List[Team]:
        """Get all teams a user is a member of"""
        result = self.db.execute(
            team_memberships.select().where(
                team_memberships.c.user_id == user_id
            )
        ).fetchall()
        team_ids = [row.team_id for row in result]
        return self.db.query(Team).filter(Team.id.in_(team_ids)).all()

    def add_team_member(self, team_id: str, user_id: str, role: str = "member", added_by: str = None) -> dict:
        """Add a user to a team with specified role"""
        # Check if adder has permission
        if added_by:
            owner = self.db.execute(
                team_memberships.select().where(
                    team_memberships.c.team_id == team_id,
                    team_memberships.c.user_id == added_by,
                    team_memberships.c.role == "owner"
                )
            ).first()
            if not owner:
                raise ValueError("Only team owner can add members")

        # Check if user is already in team
        existing = self.db.execute(
            team_memberships.select().where(
                team_memberships.c.team_id == team_id,
                team_memberships.c.user_id == user_id
            )
        ).first()
        if existing:
            raise ValueError("User already in team")

        # Add new member
        result = self.db.execute(
            team_memberships.insert().values(
                team_id=team_id,
                user_id=user_id,
                role=role,
                created_at=datetime.utcnow()
            ).returning(team_memberships)
        ).first()
        self.db.commit()
        return dict(result)

    def get_team_members(self, team_id: str, user_id: str = None) -> List[dict]:
        """Get all members of a team, optionally checking if requesting user is a member"""
        if user_id:
            member = self.db.execute(
                team_memberships.select().where(
                    team_memberships.c.team_id == team_id,
                    team_memberships.c.user_id == user_id
                )
            ).first()
            if not member:
                raise ValueError("Not a team member")

        memberships = self.db.execute(
            team_memberships.select().where(
                team_memberships.c.team_id == team_id
            )
        ).fetchall()
        return [dict(row) for row in memberships]

    def create_collaboration_request(self, team_id: str, requester_id: str, message: str = None) -> CollaborationRequest:
        """Create a new collaboration request"""
        # Check if team exists
        team = self.db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise ValueError("Team not found")
        
        # Check if user is already a member
        existing_membership = self.db.execute(
            team_memberships.select().where(
                team_memberships.c.team_id == team_id,
                team_memberships.c.user_id == requester_id
            )
        ).first()
        if existing_membership:
            raise ValueError("Already a team member")
        
        # Check if there's already a pending request
        existing_request = self.db.query(CollaborationRequest).filter(
            CollaborationRequest.team_id == team_id,
            CollaborationRequest.requester_id == requester_id,
            CollaborationRequest.status == "pending"
        ).first()
        if existing_request:
            raise ValueError("Collaboration request already pending")
        
        request = CollaborationRequest(
            team_id=team_id,
            requester_id=requester_id,
            message=message
        )
        self.db.add(request)
        self.db.commit()
        self.db.refresh(request)
        return request

    def get_collaboration_requests(self, user_id: str) -> List[CollaborationRequest]:
        """Get all pending collaboration requests for teams owned by user"""
        # Get teams where user is owner
        owned_teams = self.db.execute(
            team_memberships.select().where(
                team_memberships.c.user_id == user_id,
                team_memberships.c.role == "owner"
            )
        ).fetchall()
        team_ids = [row.team_id for row in owned_teams]
        
        return self.db.query(CollaborationRequest).filter(
            CollaborationRequest.team_id.in_(team_ids),
            CollaborationRequest.status == "pending"
        ).all()

    def respond_to_collaboration_request(self, request_id: str, user_id: str, accept: bool) -> None:
        """Respond to a collaboration request"""
        request = self.db.query(CollaborationRequest).filter(CollaborationRequest.id == request_id).first()
        if not request:
            raise ValueError("Request not found")
        
        # Check if user is team owner
        owner = self.db.execute(
            team_memberships.select().where(
                team_memberships.c.team_id == request.team_id,
                team_memberships.c.user_id == user_id,
                team_memberships.c.role == "owner"
            )
        ).first()
        if not owner:
            raise ValueError("Not authorized to respond to this request")
        
        if accept:
            # Add user as team member
            self.db.execute(
                team_memberships.insert().values(
                    team_id=request.team_id,
                    user_id=request.requester_id,
                    role="member",
                    created_at=datetime.utcnow()
                )
            )
            request.status = "accepted"
        else:
            request.status = "rejected"
        
        request.updated_at = datetime.utcnow()
        self.db.commit()

    def create_team_signup_request(self, team_id: str, user_id: str, message: str = None) -> TeamSignupRequest:
        """Create a new team signup request"""
        # Check if team exists
        team = self.db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise ValueError("Team not found")
        
        # Check if user is already a member
        existing_membership = self.db.execute(
            team_memberships.select().where(
                team_memberships.c.team_id == team_id,
                team_memberships.c.user_id == user_id
            )
        ).first()
        if existing_membership:
            raise ValueError("Already a team member")
        
        # Check if there's already a pending request
        existing_request = self.db.query(TeamSignupRequest).filter(
            TeamSignupRequest.team_id == team_id,
            TeamSignupRequest.user_id == user_id,
            TeamSignupRequest.status == "pending"
        ).first()
        if existing_request:
            raise ValueError("Signup request already pending")
        
        request = TeamSignupRequest(
            team_id=team_id,
            user_id=user_id,
            message=message
        )
        self.db.add(request)
        self.db.commit()
        self.db.refresh(request)
        return request

    def get_team_signup_requests(self, user_id: str) -> List[TeamSignupRequest]:
        """Get all pending signup requests for teams owned by user"""
        # Get teams where user is owner
        owned_teams = self.db.execute(
            team_memberships.select().where(
                team_memberships.c.user_id == user_id,
                team_memberships.c.role == "owner"
            )
        ).fetchall()
        team_ids = [row.team_id for row in owned_teams]
        
        return self.db.query(TeamSignupRequest).filter(
            TeamSignupRequest.team_id.in_(team_ids),
            TeamSignupRequest.status == "pending"
        ).all()

    def respond_to_team_signup_request(self, request_id: str, user_id: str, accept: bool) -> None:
        """Respond to a team signup request"""
        request = self.db.query(TeamSignupRequest).filter(TeamSignupRequest.id == request_id).first()
        if not request:
            raise ValueError("Request not found")
        
        # Check if user is team owner
        owner = self.db.execute(
            team_memberships.select().where(
                team_memberships.c.team_id == request.team_id,
                team_memberships.c.user_id == user_id,
                team_memberships.c.role == "owner"
            )
        ).first()
        if not owner:
            raise ValueError("Not authorized to respond to this request")
        
        if accept:
            # Add user as team member
            self.db.execute(
                team_memberships.insert().values(
                    team_id=request.team_id,
                    user_id=request.user_id,
                    role="member",
                    created_at=datetime.utcnow()
                )
            )
            request.status = "accepted"
        else:
            request.status = "rejected"
        
        request.updated_at = datetime.utcnow()
        self.db.commit() 
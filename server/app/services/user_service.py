from sqlalchemy.orm import Session
from app.models.user import User
from app.models.team import Team, team_memberships
from app.models.workspace import Workspace, WorkspaceAccess
from app.models.workspace import Project, ProjectAccess
from app.models.rbac import Role
from typing import Optional
import logging
from datetime import datetime
from uuid import UUID

logger = logging.getLogger(__name__)

DEFAULT_PROJECT_ID = UUID('00000000-0000-0000-0000-000000000003')
DEFAULT_WORKSPACE_ID = UUID('10000000-0000-0000-0000-000000000003')

class UserService:
    def __init__(self, db: Session):
        self.db = db

    def create_user_with_defaults(
        self,
        email: str,
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        username: Optional[str] = None
    ) -> User:
        """Create a new user with default team, workspace, and project memberships"""
        try:
            # Create the user
            user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                username=username or email,
                is_superuser=False,
                is_active=True
            )
            user.set_password(password)
            
            # Assign default user role
            default_role = self.db.query(Role).filter(Role.name == "user").first()
            if default_role:
                user.roles.append(default_role)
            
            self.db.add(user)
            self.db.flush()  # Flush to get the user ID
            
            # Create default team
            default_team = Team(
                name=f"{user.username}'s Team",
                description="Default team created for new user",
                created_by=user.id,
                owner_id=user.id
            )
            self.db.add(default_team)
            self.db.flush()
            
            # Add user to team using the team_memberships table
            self.db.execute(
                team_memberships.insert().values(
                    team_id=default_team.id,
                    user_id=user.id,
                    role="owner",
                    created_at=datetime.utcnow()
                )
            )
            
            # Create default workspace
            default_workspace = Workspace(
                name=f"{user.username}'s Workspace",
                description="Default workspace created for new user",
                team_id=default_team.id
            )
            self.db.add(default_workspace)
            self.db.flush()
            
            # Add workspace access
            workspace_access = WorkspaceAccess(
                workspace_id=default_workspace.id,
                user_id=user.id,
                is_admin=True,
                can_create=True,
                can_delete=True
            )
            self.db.add(workspace_access)
            
            # Create default project
            default_project = Project(
                name=f"{user.username}'s Project",
                description="Default project created for new user",
                workspace_id=default_workspace.id
            )
            self.db.add(default_project)
            self.db.flush()
            
            # Add project access
            project_access = ProjectAccess(
                project_id=default_project.id,
                user_id=user.id,
                is_admin=True,
                can_create=True,
                can_delete=True
            )
            self.db.add(project_access)
            
            # Commit all changes
            self.db.commit()
            self.db.refresh(user)
            
            return user
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating user with defaults: {str(e)}")
            raise 

    def get_users_for_team(self, team_id):
        from app.models.team import team_memberships, Team
        from app.models.user import User
        users = self.db.query(User).join(team_memberships, User.id == team_memberships.c.user_id).filter(team_memberships.c.team_id == team_id).all()
        return users

    def get_users_for_project(self, project_id):
        from app.models.workspace import ProjectAccess
        from app.models.user import User
        users = self.db.query(User).join(ProjectAccess, User.id == ProjectAccess.user_id).filter(ProjectAccess.project_id == project_id).all()
        return users

    def get_users_for_workspace(self, workspace_id):
        from app.models.workspace import WorkspaceAccess
        from app.models.user import User
        users = self.db.query(User).join(WorkspaceAccess, User.id == WorkspaceAccess.user_id).filter(WorkspaceAccess.workspace_id == workspace_id).all()
        return users

    def get_users_for_thread(self, thread_id):
        from app.models.thread import ThreadCollaborator, Thread
        from app.models.user import User
        # Get collaborators
        collaborators = self.db.query(User).join(ThreadCollaborator, User.id == ThreadCollaborator.user_id).filter(ThreadCollaborator.thread_id == thread_id, ThreadCollaborator.status == 'accepted').all()
        # Get thread creator
        thread = self.db.query(Thread).filter(Thread.id == thread_id).first()
        if thread:
            creator = self.db.query(User).filter(User.id == thread.created_by).first()
            if creator and creator not in collaborators:
                collaborators.append(creator)
        return collaborators

    def get_connected_users_via_teams(self, user_id):
        from app.models.team import team_memberships
        from app.models.user import User
        # Get all team_ids the user is a member of
        team_ids = [row.team_id for row in self.db.execute(team_memberships.select().with_only_columns([team_memberships.c.team_id]).where(team_memberships.c.user_id == user_id)).fetchall()]
        # Get all users in those teams (excluding the user themself)
        users = self.db.query(User).join(team_memberships, User.id == team_memberships.c.user_id).filter(team_memberships.c.team_id.in_(team_ids), User.id != user_id).distinct().all()
        return users 
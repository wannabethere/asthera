from sqlalchemy.orm import Session
from app.models.rbac import Role, Permission, SYSTEM_ROLES
from app.models.workspace import Workspace, Project
from app.models.team import Team
from app.services.user_service import DEFAULT_PROJECT_ID, DEFAULT_WORKSPACE_ID

class SystemInfoService:
    def __init__(self, db: Session):
        self.db = db

    def get_all_roles(self):
        return self.db.query(Role).all()

    def get_all_permissions(self):
        return self.db.query(Permission).all()

    def get_all_workspaces(self):
        return self.db.query(Workspace).all()

    def get_all_teams(self):
        return self.db.query(Team).all()

    def get_all_projects(self):
        return self.db.query(Project).all()

    def get_default_roles(self):
        return SYSTEM_ROLES

    def get_authenticated_user_permissions(self):
        return SYSTEM_ROLES["authenticated_user"]["permissions"]

    def get_default_project_id(self):
        return str(DEFAULT_PROJECT_ID)

    def get_default_workspace_id(self):
        return str(DEFAULT_WORKSPACE_ID)

    def get_permissions_for_user(self, user):
        # Aggregate permissions from all roles assigned to the user
        permissions = set()
        for role in user.roles:
            for perm in role.permissions:
                permissions.add(perm.name)
        return list(permissions)

    def get_workspaces_for_user(self, user):
        # Return workspaces the user has access to
        from app.models.workspace import WorkspaceAccess
        workspace_ids = [wa.workspace_id for wa in user.workspace_access]
        return self.db.query(Workspace).filter(Workspace.id.in_(workspace_ids)).all()

    def get_teams_for_user(self, user):
        # Return teams the user is a member of
        return user.teams

    def get_projects_for_user(self, user):
        # Return projects the user has access to
        from app.models.workspace import ProjectAccess, Project
        project_ids = [pa.project_id for pa in user.project_access]
        return self.db.query(Project).filter(Project.id.in_(project_ids)).all() 
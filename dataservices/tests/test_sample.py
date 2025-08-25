from fastapi import Depends, HTTPException,APIRouter,FastAPI
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from httpx import AsyncClient

app = FastAPI()
# TestRouter = APIRouter()

security = HTTPBearer()

def get_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    if not token:
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    return token


@app.post("/test")
async def test_endpoint(token: str = Depends(get_token)):
    async with AsyncClient() as client:
        response = await client.post("http://127.0.0.1:8023/api/v1/auth/validate-session", params={"token": token})
        print(f"Response: {response.json()}")
    return {"message": "Test endpoint called successfully", "token": token,"response": response.json()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8025)



from app.core.session_manager import SessionManager
from sqlalchemy import MetaData, Table, select
from httpx import AsyncClient
from pydantic import BaseModel, Field
from typing import Literal
from enum import Enum


class PermissionLevel(str, Enum):
    read = "read"
    read_write = "read_write"
    admin = "admin"

class EntityType(str, Enum):
    user = "user"
    team = "team"
    project = "project"
    workspace = "workspace"

class ShareInfo(BaseModel):
    entity_id: str = Field(..., description="ID of the entity to share with")
    entity_type: EntityType = Field(..., description="Type of entity (user, team, project, workspace)")
    permission: PermissionLevel = Field(..., description="Permission level (read, read_write, admin)")

class SharePermissions:
    def __init__(self):
        self.session_manager = SessionManager()
        self.genai_client = AsyncClient()
        self.genai_url="http://127.0.0.1:8023"
        self.metadata = MetaData()
        self.permissions={
            "permissions": [
                {
                "permission_name": "read",
                "permission_description": "Can view data but cannot modify it.",
                "actions": ["view"]
                },
                {
                "permission_name": "read_write",
                "permission_description": "Can view and modify data.",
                "actions": ["view", "create", "update"]
                },
                {
                "permission_name": "admin",
                "permission_description": "Full access to all data and settings.",
                "actions": ["view", "create", "update", "delete", "manage_permissions"]
                }
            ]
    }

    async def _validate_user(self,token):
        try:
            response = await self.genai_client.get(f"{self.genai_url}/api/v1/auth/validate-session", params={"token": token})
            if response.status_code == 200:
                response = response.json()
                if response.get("is_valid"):
                    return response.get('user')
                else:
                    raise ValueError("Invalid token")
            else:
                raise HTTPException(status_code=response.status_code, detail=response.text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    async def get_share_datamodel_info(self,token):
        try:
            user = await self._validate_user(token)
            if user == False:
                raise HTTPException(status_code=401, detail="Invalid token")
            headers = {
                "Authorization": f"Bearer {token}"
            }
            response = await self.genai_client.get(f"{self.genai_url}/api/v1/users/system-info", headers=headers)
            if response.status_code == 200:
                response = response.json()
            else:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            
            try:
                self.genai_session = await self.session_manager.get_async_genai_db_session()
                User = Table(
                "users",
                self.metadata,
                autoload_with=self.genai_session.bind  # session.bind gives you the engine
                )
                result = await self.genai_session.execute(select(User))
                all_users = result.scalars().all()
                final_response = {
                    "viewable_users": all_users,
                    "viewable_workspaces": response.get("workspaces", []),
                    "viewable_projects": response.get("projects", []),
                    "viewable_teams": response.get("teams", []),
                    "Permissions":self.permissions
                }
                return final_response
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
            
            
            
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def store_info(self,token,share_info:ShareInfo):
        try:
            user = await self._validate_user(token)
            if user == False:
                raise HTTPException(status_code=401, detail="Invalid token")
            headers = {
                "Authorization": f"Bearer {token}"
            }

            try:
                self.session = await self.session_manager.get_async_db_session()
                share_permission = SharePermission(
                    entity_id=share_info.entity_id,
                    shared_with=share_info.entity_type,
                    permission=share_info.permission,
                    shared_by=user.get("id"),
                    
                    
                )

                self.session.add(share_permission)
                await self.session.commit()
                await self.session.refresh(share_permission)
                return {"message": "Permission shared successfully","share_permission": share_permission}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))





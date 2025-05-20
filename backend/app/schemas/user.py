from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List
from app.models.user import User

class UserResponse(BaseModel):
    id: UUID
    email: str
    username: str
    first_name: Optional[str]
    last_name: Optional[str]
    roles: List[str]
    permissions: Optional[List[str]] = None
    class Config:
        orm_mode = True 


def user_to_response(user: User) -> UserResponse:
    # Collect all unique permissions from all roles
    permissions = set()
    for role in user.roles:
        for perm in getattr(role, 'permissions', []):
            permissions.add(perm.name)
    return UserResponse(
        id=str(user.id),
        email=user.email,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        roles=[role.name for role in user.roles],
        permissions=sorted(list(permissions)) if permissions else None
    ) 
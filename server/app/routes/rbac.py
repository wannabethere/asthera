from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.rbac import Role, Permission, SYSTEM_ROLES, role_permissions, user_roles
from app.models.user import User
from app.auth.okta import get_current_user
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter(prefix="/rbac", tags=["rbac"])

# Models
class PermissionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    resource_type: str
    action: str

class PermissionResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    resource_type: str
    action: str
    created_at: str
    updated_at: Optional[str]
    class Config:
        orm_mode = True

class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    permission_ids: List[str]

class RoleResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    is_system_role: bool
    permissions: List[PermissionResponse]
    created_at: str
    updated_at: Optional[str]
    class Config:
        orm_mode = True

class UserRoleAssignment(BaseModel):
    role_ids: List[str]

# Helper functions
def check_superuser(user: User) -> bool:
    return user.is_superuser

def get_user_permissions(db: Session, user_id: str) -> List[str]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return []
    
    if user.is_superuser:
        return ["*"]  # Superuser has all permissions
    
    # Get all permissions from user's roles
    permissions = set()
    for role in user.roles:
        for permission in role.permissions:
            permissions.add(f"{permission.resource_type}:{permission.action}")
    
    return list(permissions)

# Permission Routes
@router.post("/permissions", response_model=PermissionResponse)
async def create_permission(
    req: PermissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not check_superuser(current_user):
        raise HTTPException(status_code=403, detail="Only superusers can create permissions")

    # Check if permission already exists
    existing = db.query(Permission).filter(
        Permission.resource_type == req.resource_type,
        Permission.action == req.action
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Permission already exists")

    permission = Permission(
        name=req.name,
        description=req.description,
        resource_type=req.resource_type,
        action=req.action
    )
    db.add(permission)
    db.commit()
    db.refresh(permission)
    return permission

@router.get("/permissions", response_model=List[PermissionResponse])
async def list_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
   # Get permissions for the current user
    permissions = get_user_permissions(db, str(current_user.id))

    # If user is superuser or has all permissions, return all permissions
    if "*" in permissions:
        return db.query(Permission).all()

        # Otherwise return only the permissions the user has access to
    return db.query(Permission).filter(
        Permission.resource_type + ":" + Permission.action.in_(permissions)
    ).all()
   
# Role Routes
@router.post("/roles", response_model=RoleResponse)
async def create_role(
    req: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not check_superuser(current_user):
        raise HTTPException(status_code=403, detail="Only superusers can create roles")

    # Check if role name already exists
    existing = db.query(Role).filter(Role.name == req.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Role name already exists")

    # Verify all permissions exist
    permissions = db.query(Permission).filter(Permission.id.in_(req.permission_ids)).all()
    if len(permissions) != len(req.permission_ids):
        raise HTTPException(status_code=400, detail="One or more permissions not found")

    role = Role(
        name=req.name,
        description=req.description,
        is_system_role=False
    )
    role.permissions = permissions
    db.add(role)
    db.commit()
    db.refresh(role)
    return role

@router.get("/roles", response_model=List[RoleResponse])
async def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not check_superuser(current_user):
        raise HTTPException(status_code=403, detail="Only superusers can list roles")
    return db.query(Role).all()

@router.put("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: str,
    req: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not check_superuser(current_user):
        raise HTTPException(status_code=403, detail="Only superusers can update roles")

    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    if role.is_system_role:
        raise HTTPException(status_code=400, detail="Cannot modify system roles")

    # Check if new name conflicts with existing role
    existing = db.query(Role).filter(Role.name == req.name, Role.id != role_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Role name already exists")

    # Verify all permissions exist
    permissions = db.query(Permission).filter(Permission.id.in_(req.permission_ids)).all()
    if len(permissions) != len(req.permission_ids):
        raise HTTPException(status_code=400, detail="One or more permissions not found")

    role.name = req.name
    role.description = req.description
    role.permissions = permissions
    role.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(role)
    return role

@router.delete("/roles/{role_id}")
async def delete_role(
    role_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not check_superuser(current_user):
        raise HTTPException(status_code=403, detail="Only superusers can delete roles")

    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    if role.is_system_role:
        raise HTTPException(status_code=400, detail="Cannot delete system roles")

    db.delete(role)
    db.commit()
    return {"status": "success"}

# User Role Management
@router.post("/users/{user_id}/roles", response_model=List[RoleResponse])
async def assign_roles_to_user(
    user_id: str,
    req: UserRoleAssignment,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not check_superuser(current_user):
        raise HTTPException(status_code=403, detail="Only superusers can assign roles")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify all roles exist
    roles = db.query(Role).filter(Role.id.in_(req.role_ids)).all()
    if len(roles) != len(req.role_ids):
        raise HTTPException(status_code=400, detail="One or more roles not found")

    user.roles = roles
    db.commit()
    db.refresh(user)
    return user.roles

@router.get("/users/{user_id}/roles", response_model=List[RoleResponse])
async def get_user_roles(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not check_superuser(current_user) and str(current_user.id) != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view user roles")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user.roles

@router.get("/users/{user_id}/permissions")
async def get_user_permissions_endpoint(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not check_superuser(current_user) and str(current_user.id) != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view user permissions")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {"permissions": get_user_permissions(db, user_id)} 
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.auth.okta import get_current_user
from app.services.data_connection import DataConnectionService
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID

router = APIRouter(prefix="/data-connections", tags=["data-connections"])

class DataConnectionCreate(BaseModel):
    name: str
    description: str
    source_type: str
    connection_config: Dict[str, Any]
    data_definitions: Dict[str, Any]

class DataConnectionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    connection_config: Optional[Dict[str, Any]] = None
    data_definitions: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class DataConnectionResponse(BaseModel):
    id: str
    name: str
    description: str
    source_type: str
    connection_config: Dict[str, Any]
    data_definitions: Dict[str, Any]
    is_active: bool
    created_by: str
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class AccessControlCreate(BaseModel):
    team_id: Optional[str] = None
    workspace_id: Optional[str] = None
    user_id: Optional[str] = None
    access_level: str = "read"

class AccessControlResponse(BaseModel):
    id: str
    data_connection_id: str
    team_id: Optional[str]
    workspace_id: Optional[str]
    user_id: Optional[str]
    access_level: str
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

@router.post("/", response_model=DataConnectionResponse)
async def create_data_connection(
    connection_data: DataConnectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new data connection."""
    service = DataConnectionService(db)
    connection = service.create_connection(
        name=connection_data.name,
        description=connection_data.description,
        source_type=connection_data.source_type,
        connection_config=connection_data.connection_config,
        data_definitions=connection_data.data_definitions,
        created_by=str(current_user.id)
    )
    return connection

@router.get("/", response_model=List[DataConnectionResponse])
async def list_data_connections(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all data connections accessible to the current user."""
    service = DataConnectionService(db)
    return service.list_connections(str(current_user.id))

@router.get("/{connection_id}", response_model=DataConnectionResponse)
async def get_data_connection(
    connection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific data connection."""
    service = DataConnectionService(db)
    connection = service.get_connection(connection_id)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data connection not found"
        )
    
    if not service.check_access(connection_id, str(current_user.id)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this data connection"
        )
    
    return connection

@router.put("/{connection_id}", response_model=DataConnectionResponse)
async def update_data_connection(
    connection_id: str,
    connection_data: DataConnectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a data connection."""
    service = DataConnectionService(db)
    if not service.check_access(connection_id, str(current_user.id), "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this data connection"
        )
    
    connection = service.update_connection(
        connection_id=connection_id,
        name=connection_data.name,
        description=connection_data.description,
        connection_config=connection_data.connection_config,
        data_definitions=connection_data.data_definitions,
        is_active=connection_data.is_active
    )
    
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data connection not found"
        )
    
    return connection

@router.delete("/{connection_id}")
async def delete_data_connection(
    connection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a data connection."""
    service = DataConnectionService(db)
    if not service.check_access(connection_id, str(current_user.id), "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this data connection"
        )
    
    if not service.delete_connection(connection_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data connection not found"
        )
    
    return {"message": "Data connection deleted successfully"}

@router.post("/{connection_id}/access", response_model=AccessControlResponse)
async def add_access_control(
    connection_id: str,
    access_data: AccessControlCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add access control to a data connection."""
    service = DataConnectionService(db)
    if not service.check_access(connection_id, str(current_user.id), "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify access controls"
        )
    
    access = service.add_access(
        connection_id=connection_id,
        team_id=access_data.team_id,
        workspace_id=access_data.workspace_id,
        user_id=access_data.user_id,
        access_level=access_data.access_level
    )
    return access

@router.delete("/{connection_id}/access")
async def remove_access_control(
    connection_id: str,
    access_data: AccessControlCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove access control from a data connection."""
    service = DataConnectionService(db)
    if not service.check_access(connection_id, str(current_user.id), "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify access controls"
        )
    
    if not service.remove_access(
        connection_id=connection_id,
        team_id=access_data.team_id,
        workspace_id=access_data.workspace_id,
        user_id=access_data.user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Access control not found"
        )
    
    return {"message": "Access control removed successfully"}

@router.get("/{connection_id}/access", response_model=List[AccessControlResponse])
async def list_access_controls(
    connection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all access controls for a data connection."""
    service = DataConnectionService(db)
    if not service.check_access(connection_id, str(current_user.id), "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view access controls"
        )
    
    return service.list_access(connection_id) 
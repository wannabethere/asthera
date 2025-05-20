from sqlalchemy.orm import Session
from app.models.data_connection import DataConnection, DataConnectionAccess
from app.models.user import User
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status
import json

class DataConnectionService:
    def __init__(self, db: Session):
        self.db = db

    def create_connection(
        self,
        name: str,
        description: str,
        source_type: str,
        connection_config: Dict[str, Any],
        data_definitions: Dict[str, Any],
        created_by: str
    ) -> DataConnection:
        """Create a new data connection."""
        connection = DataConnection(
            name=name,
            description=description,
            source_type=source_type,
            connection_config=connection_config,
            data_definitions=data_definitions,
            created_by=created_by
        )
        self.db.add(connection)
        self.db.commit()
        self.db.refresh(connection)
        return connection

    def get_connection(self, connection_id: str) -> Optional[DataConnection]:
        """Get a data connection by ID."""
        return self.db.query(DataConnection).filter(DataConnection.id == connection_id).first()

    def list_connections(self, user_id: str) -> List[DataConnection]:
        """List all data connections accessible to a user."""
        return self.db.query(DataConnection).join(
            DataConnectionAccess,
            DataConnection.id == DataConnectionAccess.data_connection_id
        ).filter(
            (DataConnectionAccess.user_id == user_id) |
            (DataConnection.created_by == user_id)
        ).distinct().all()

    def update_connection(
        self,
        connection_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        connection_config: Optional[Dict[str, Any]] = None,
        data_definitions: Optional[Dict[str, Any]] = None,
        is_active: Optional[bool] = None
    ) -> Optional[DataConnection]:
        """Update a data connection."""
        connection = self.get_connection(connection_id)
        if not connection:
            return None

        if name is not None:
            connection.name = name
        if description is not None:
            connection.description = description
        if connection_config is not None:
            connection.connection_config = connection_config
        if data_definitions is not None:
            connection.data_definitions = data_definitions
        if is_active is not None:
            connection.is_active = is_active

        self.db.commit()
        self.db.refresh(connection)
        return connection

    def delete_connection(self, connection_id: str) -> bool:
        """Delete a data connection."""
        connection = self.get_connection(connection_id)
        if not connection:
            return False

        self.db.delete(connection)
        self.db.commit()
        return True

    def add_access(
        self,
        connection_id: str,
        team_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        access_level: str = "read"
    ) -> DataConnectionAccess:
        """Add access control for a data connection."""
        if not any([team_id, workspace_id, user_id]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one of team_id, workspace_id, or user_id must be provided"
            )

        # Check if access already exists
        existing_access = self.db.query(DataConnectionAccess).filter(
            DataConnectionAccess.data_connection_id == connection_id,
            DataConnectionAccess.team_id == team_id,
            DataConnectionAccess.workspace_id == workspace_id,
            DataConnectionAccess.user_id == user_id
        ).first()

        if existing_access:
            existing_access.access_level = access_level
            self.db.commit()
            self.db.refresh(existing_access)
            return existing_access

        access = DataConnectionAccess(
            data_connection_id=connection_id,
            team_id=team_id,
            workspace_id=workspace_id,
            user_id=user_id,
            access_level=access_level
        )
        self.db.add(access)
        self.db.commit()
        self.db.refresh(access)
        return access

    def remove_access(
        self,
        connection_id: str,
        team_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> bool:
        """Remove access control for a data connection."""
        access = self.db.query(DataConnectionAccess).filter(
            DataConnectionAccess.data_connection_id == connection_id,
            DataConnectionAccess.team_id == team_id,
            DataConnectionAccess.workspace_id == workspace_id,
            DataConnectionAccess.user_id == user_id
        ).first()

        if not access:
            return False

        self.db.delete(access)
        self.db.commit()
        return True

    def list_access(self, connection_id: str) -> List[DataConnectionAccess]:
        """List all access controls for a data connection."""
        return self.db.query(DataConnectionAccess).filter(
            DataConnectionAccess.data_connection_id == connection_id
        ).all()

    def check_access(
        self,
        connection_id: str,
        user_id: str,
        required_level: str = "read"
    ) -> bool:
        """Check if a user has the required access level to a data connection."""
        access = self.db.query(DataConnectionAccess).filter(
            DataConnectionAccess.data_connection_id == connection_id,
            DataConnectionAccess.user_id == user_id
        ).first()

        if not access:
            return False

        # Define access level hierarchy
        access_levels = {
            "read": 1,
            "write": 2,
            "admin": 3
        }

        return access_levels.get(access.access_level, 0) >= access_levels.get(required_level, 0) 
from sqlalchemy.orm import Session
from sqlalchemy import Table, Column, UUID, String, DateTime, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base
from typing import List, Optional
from datetime import datetime
import uuid
from app.models.user import User
from app.models.organization import Organization
from app.database import Base
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Association table for user-organization relationship
organization_users = Table(
    "organization_users",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("organization_id", UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True),
    Column("role", String, default="member"),  # e.g., 'admin', 'member'
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), onupdate=func.now())
)

class OrganizationUserService:
    def __init__(self, db: Session):
        self.db = db

    async def add_user_to_organization(
        self,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        role: str = "member"
    ) -> bool:
        """Add a user to an organization with a specific role."""
        try:
            # Check if user and organization exist
            user = self.db.query(User).filter(User.id == user_id).first()
            organization = self.db.query(Organization).filter(Organization.id == organization_id).first()
            
            if not user or not organization:
                logger.error(f"User {user_id} or organization {organization_id} not found")
                return False

            # Check if relationship already exists
            existing = self.db.execute(
                organization_users.select().where(
                    organization_users.c.user_id == user_id,
                    organization_users.c.organization_id == organization_id
                )
            ).first()

            if existing:
                logger.info(f"User {user_id} is already a member of organization {organization_id}")
                return True

            # Add user to organization
            self.db.execute(
                organization_users.insert().values(
                    user_id=user_id,
                    organization_id=organization_id,
                    role=role,
                    created_at=datetime.utcnow()
                )
            )
            self.db.commit()
            logger.info(f"Added user {user_id} to organization {organization_id} with role {role}")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error adding user to organization: {str(e)}")
            return False

    async def remove_user_from_organization(
        self,
        user_id: uuid.UUID,
        organization_id: uuid.UUID
    ) -> bool:
        """Remove a user from an organization."""
        try:
            result = self.db.execute(
                organization_users.delete().where(
                    organization_users.c.user_id == user_id,
                    organization_users.c.organization_id == organization_id
                )
            )
            self.db.commit()
            
            if result.rowcount > 0:
                logger.info(f"Removed user {user_id} from organization {organization_id}")
                return True
            else:
                logger.warning(f"User {user_id} was not a member of organization {organization_id}")
                return False

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error removing user from organization: {str(e)}")
            return False

    async def get_user_organizations(
        self,
        user_id: uuid.UUID
    ) -> List[Organization]:
        """Get all organizations a user belongs to."""
        try:
            result = self.db.execute(
                organization_users.select().where(
                    organization_users.c.user_id == user_id
                )
            ).fetchall()
            
            organization_ids = [row.organization_id for row in result]
            organizations = self.db.query(Organization).filter(
                Organization.id.in_(organization_ids)
            ).all()
            
            return organizations

        except Exception as e:
            logger.error(f"Error getting user organizations: {str(e)}")
            return []

    async def get_organization_users(
        self,
        organization_id: uuid.UUID,
        role: Optional[str] = None
    ) -> List[User]:
        """Get all users in an organization, optionally filtered by role."""
        try:
            query = organization_users.select().where(
                organization_users.c.organization_id == organization_id
            )
            
            if role:
                query = query.where(organization_users.c.role == role)
            
            result = self.db.execute(query).fetchall()
            
            user_ids = [row.user_id for row in result]
            users = self.db.query(User).filter(
                User.id.in_(user_ids)
            ).all()
            
            return users

        except Exception as e:
            logger.error(f"Error getting organization users: {str(e)}")
            return []

    async def update_user_role(
        self,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        new_role: str
    ) -> bool:
        """Update a user's role in an organization."""
        try:
            result = self.db.execute(
                organization_users.update()
                .where(
                    organization_users.c.user_id == user_id,
                    organization_users.c.organization_id == organization_id
                )
                .values(role=new_role, updated_at=datetime.utcnow())
            )
            self.db.commit()
            
            if result.rowcount > 0:
                logger.info(f"Updated role for user {user_id} in organization {organization_id} to {new_role}")
                return True
            else:
                logger.warning(f"User {user_id} is not a member of organization {organization_id}")
                return False

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating user role: {str(e)}")
            return False

    async def get_user_role(
        self,
        user_id: uuid.UUID,
        organization_id: uuid.UUID
    ) -> Optional[str]:
        """Get a user's role in an organization."""
        try:
            result = self.db.execute(
                organization_users.select().where(
                    organization_users.c.user_id == user_id,
                    organization_users.c.organization_id == organization_id
                )
            ).first()
            
            return result.role if result else None

        except Exception as e:
            logger.error(f"Error getting user role: {str(e)}")
            return None

    async def is_user_in_organization(
        self,
        user_id: uuid.UUID,
        organization_id: uuid.UUID
    ) -> bool:
        """Check if a user is a member of an organization."""
        try:
            result = self.db.execute(
                organization_users.select().where(
                    organization_users.c.user_id == user_id,
                    organization_users.c.organization_id == organization_id
                )
            ).first()
            
            return result is not None

        except Exception as e:
            logger.error(f"Error checking user organization membership: {str(e)}")
            return False 
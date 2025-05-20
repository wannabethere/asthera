from sqlalchemy.orm import Session
from app.models.organization import ApplicationSignup, Organization, OrganizationInfo, ApplicationConfiguration
from app.models.user import User
from app.schemas.organization import (
    ApplicationSignupCreate, OrganizationCreate, OrganizationInfoCreate,
    ApplicationConfigurationCreate, OrganizationInvite
)
from app.core.security import get_password_hash, create_access_token
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import uuid
from app.utils.email import send_organization_invite_email
from app.utils.logger import logger
from app.settings import get_settings

settings = get_settings()

class OrganizationService:
    def __init__(self, db: Session):
        self.db = db

    def create_application_signup(self, signup_data: ApplicationSignupCreate) -> ApplicationSignup:
        """Create a new application signup request"""
        try:
            signup = ApplicationSignup(
                organization_name=signup_data.organization_name,
                contact_email=signup_data.contact_email,
                contact_name=signup_data.contact_name,
                contact_phone=signup_data.contact_phone
            )
            self.db.add(signup)
            self.db.commit()
            self.db.refresh(signup)
            return signup
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating application signup: {str(e)}")
            raise

    def approve_signup(self, signup_id: uuid.UUID) -> Organization:
        """Approve an application signup and create organization"""
        try:
            signup = self.db.query(ApplicationSignup).filter(ApplicationSignup.id == signup_id).first()
            if not signup:
                raise ValueError("Signup request not found")
            
            if signup.status != 'pending':
                raise ValueError(f"Signup request is already {signup.status}")

            # Create organization
            organization = Organization(
                name=signup.organization_name,
                domain=signup.contact_email.split('@')[1]  # Use email domain as organization domain
            )
            self.db.add(organization)
            self.db.flush()

            # Create organization info
            info = OrganizationInfo(organization_id=organization.id)
            self.db.add(info)

            # Create default application configuration
            config = ApplicationConfiguration(
                organization_id=organization.id,
                config={
                    "max_users": 10,
                    "max_threads": 100,
                    "features": {
                        "chat": True,
                        "collaboration": True,
                        "analytics": True
                    }
                }
            )
            self.db.add(config)

            # Update signup status
            signup.status = 'approved'
            signup.approved_at = datetime.utcnow()
            signup.organization_id = organization.id

            self.db.commit()
            self.db.refresh(organization)
            return organization
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error approving signup: {str(e)}")
            raise

    def reject_signup(self, signup_id: uuid.UUID, reason: str) -> ApplicationSignup:
        """Reject an application signup"""
        try:
            signup = self.db.query(ApplicationSignup).filter(ApplicationSignup.id == signup_id).first()
            if not signup:
                raise ValueError("Signup request not found")
            
            if signup.status != 'pending':
                raise ValueError(f"Signup request is already {signup.status}")

            signup.status = 'rejected'
            signup.rejected_at = datetime.utcnow()
            signup.rejection_reason = reason

            self.db.commit()
            self.db.refresh(signup)
            return signup
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error rejecting signup: {str(e)}")
            raise

    def create_organization_invite(self, invite_data: OrganizationInvite) -> dict:
        """Create an organization invite and send email"""
        try:
            organization = self.db.query(Organization).filter(Organization.id == invite_data.organization_id).first()
            if not organization:
                raise ValueError("Organization not found")

            # Create temporary user with random password
            temp_password = str(uuid.uuid4())
            user = User(
                email=invite_data.email,
                hashed_password=get_password_hash(temp_password),
                organization_id=organization.id,
                role=invite_data.role,
                is_active=True
            )
            self.db.add(user)
            self.db.flush()

            # Create invite token
            expires_delta = timedelta(hours=settings.INVITE_TOKEN_EXPIRE_HOURS)
            invite_token = create_access_token(
                data={"sub": user.email, "org_id": str(organization.id)},
                expires_delta=expires_delta
            )

            # Send invite email
            send_organization_invite_email(
                email_to=invite_data.email,
                organization_name=organization.name,
                invite_token=invite_token
            )

            return {
                "user_id": user.id,
                "email": user.email,
                "organization_id": organization.id,
                "role": user.role,
                "expires_at": datetime.utcnow() + expires_delta
            }
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating organization invite: {str(e)}")
            raise

    def get_organization(self, organization_id: uuid.UUID) -> Optional[Organization]:
        """Get organization by ID"""
        return self.db.query(Organization).filter(Organization.id == organization_id).first()

    def update_organization(self, organization_id: uuid.UUID, update_data: dict) -> Organization:
        """Update organization details"""
        try:
            organization = self.get_organization(organization_id)
            if not organization:
                raise ValueError("Organization not found")

            for key, value in update_data.items():
                setattr(organization, key, value)

            self.db.commit()
            self.db.refresh(organization)
            return organization
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating organization: {str(e)}")
            raise

    def get_organization_config(self, organization_id: uuid.UUID) -> Optional[ApplicationConfiguration]:
        """Get organization application configuration"""
        return self.db.query(ApplicationConfiguration).filter(
            ApplicationConfiguration.organization_id == organization_id
        ).first()

    def update_organization_config(self, organization_id: uuid.UUID, config_data: dict) -> ApplicationConfiguration:
        """Update organization application configuration"""
        try:
            config = self.get_organization_config(organization_id)
            if not config:
                raise ValueError("Organization configuration not found")

            config.config.update(config_data)
            self.db.commit()
            self.db.refresh(config)
            return config
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating organization config: {str(e)}")
            raise

    def get_organization_info(self, organization_id: uuid.UUID) -> Optional[OrganizationInfo]:
        """Get organization info by organization ID"""
        return self.db.query(OrganizationInfo).filter(
            OrganizationInfo.organization_id == organization_id
        ).first()

    def update_organization_info(self, organization_id: uuid.UUID, info_data: dict) -> OrganizationInfo:
        """Update organization info"""
        try:
            info = self.get_organization_info(organization_id)
            if not info:
                raise ValueError("Organization info not found")

            for key, value in info_data.items():
                if key == 'additional_info':
                    # Merge additional_info instead of replacing
                    current_additional_info = info.additional_info or {}
                    current_additional_info.update(value)
                    setattr(info, key, current_additional_info)
                else:
                    setattr(info, key, value)

            self.db.commit()
            self.db.refresh(info)
            return info
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating organization info: {str(e)}")
            raise

    def update_additional_info(self, organization_id: uuid.UUID, additional_info: Dict[str, Any]) -> OrganizationInfo:
        """Update only the additional_info field of organization info"""
        try:
            info = self.get_organization_info(organization_id)
            if not info:
                raise ValueError("Organization info not found")

            current_additional_info = info.additional_info or {}
            current_additional_info.update(additional_info)
            info.additional_info = current_additional_info

            self.db.commit()
            self.db.refresh(info)
            return info
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating additional info: {str(e)}")
            raise

    def get_additional_info(self, organization_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Get only the additional_info field of organization info"""
        info = self.get_organization_info(organization_id)
        return info.additional_info if info else None 
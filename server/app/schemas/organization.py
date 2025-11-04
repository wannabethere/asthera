from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr, HttpUrl
from datetime import datetime
from uuid import UUID

class ApplicationSignupBase(BaseModel):
    organization_name: str
    contact_email: EmailStr
    contact_name: str
    contact_phone: Optional[str] = None

class ApplicationSignupCreate(ApplicationSignupBase):
    pass

class ApplicationSignupUpdate(BaseModel):
    status: Optional[str] = None
    rejection_reason: Optional[str] = None

class ApplicationSignup(ApplicationSignupBase):
    id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    organization_id: Optional[UUID] = None

    class Config:
        from_attributes = True

class OrganizationInfoBase(BaseModel):
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[HttpUrl] = None
    industry: Optional[str] = None
    size: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[HttpUrl] = None

class OrganizationInfoCreate(OrganizationInfoBase):
    pass

class OrganizationInfoUpdate(OrganizationInfoBase):
    pass

class OrganizationInfo(OrganizationInfoBase):
    id: UUID
    organization_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ApplicationConfigurationBase(BaseModel):
    config: Dict[str, Any]

class ApplicationConfigurationCreate(ApplicationConfigurationBase):
    pass

class ApplicationConfigurationUpdate(ApplicationConfigurationBase):
    pass

class ApplicationConfiguration(ApplicationConfigurationBase):
    id: UUID
    organization_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class OrganizationBase(BaseModel):
    name: str
    domain: str

class OrganizationCreate(OrganizationBase):
    info: Optional[OrganizationInfoCreate] = None
    config: Optional[ApplicationConfigurationCreate] = None

class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
    is_active: Optional[bool] = None

class Organization(OrganizationBase):
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    info: Optional[OrganizationInfo] = None
    config: Optional[ApplicationConfiguration] = None

    class Config:
        from_attributes = True

class OrganizationInvite(BaseModel):
    email: EmailStr
    organization_id: UUID
    role: str = "admin"  # Default role for organization signup

class OrganizationInviteResponse(BaseModel):
    id: UUID
    email: EmailStr
    organization_id: UUID
    role: str
    status: str
    created_at: datetime
    expires_at: datetime

    class Config:
        from_attributes = True 
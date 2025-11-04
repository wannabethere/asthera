from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, JSON, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from app.database import Base

class ApplicationSignup(Base):
    __tablename__ = "application_signups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_name = Column(String, nullable=False)
    contact_email = Column(String, nullable=False)
    contact_name = Column(String, nullable=False)
    contact_phone = Column(String)
    status = Column(Enum('pending', 'approved', 'rejected', name='signup_status'), default='pending')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    approved_at = Column(DateTime)
    rejected_at = Column(DateTime)
    rejection_reason = Column(String)
    
    # Once approved, link to organization
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'))
    organization = relationship("Organization", back_populates="signup")

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    domain = Column(String, nullable=False, unique=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    signup = relationship("ApplicationSignup", back_populates="organization", uselist=False)
    info = relationship("OrganizationInfo", back_populates="organization", uselist=False)
    config = relationship("ApplicationConfiguration", back_populates="organization", uselist=False)

class OrganizationInfo(Base):
    __tablename__ = "organization_info"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=False)
    address = Column(String)
    city = Column(String)
    state = Column(String)
    country = Column(String)
    postal_code = Column(String)
    phone = Column(String)
    website = Column(String)
    industry = Column(String)
    size = Column(String)
    description = Column(String)
    logo_url = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    organization = relationship("Organization", back_populates="info")

class ApplicationConfiguration(Base):
    __tablename__ = "application_configurations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=False)
    config = Column(JSONB, nullable=False, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    organization = relationship("Organization", back_populates="config") 
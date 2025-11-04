from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.organization import (
    ApplicationSignupCreate, ApplicationSignup, OrganizationCreate,
    Organization, OrganizationInfo, ApplicationConfiguration,
    OrganizationInvite, OrganizationInviteResponse
)
from app.services.organization_service import OrganizationService
from app.auth.okta import get_current_user, get_current_admin_user
from typing import List, Dict, Any
from app.utils.logger import logger, log_request, log_response, log_error
import uuid

router = APIRouter(prefix="/organizations", tags=["organizations"])

@router.post("/signup", response_model=ApplicationSignup)
async def create_application_signup(
    signup_data: ApplicationSignupCreate,
    db: Session = Depends(get_db)
):
    """Create a new application signup request"""
    try:
        log_request(logger, "POST /organizations/signup", signup_data.dict())
        service = OrganizationService(db)
        signup = service.create_application_signup(signup_data)
        log_response(logger, "POST /organizations/signup", signup.__dict__)
        return signup
    except Exception as e:
        log_error(logger, "POST /organizations/signup", e, signup_data.dict())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/signup/{signup_id}/approve", response_model=Organization)
async def approve_signup(
    signup_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Approve an application signup request"""
    try:
        log_request(logger, f"POST /organizations/signup/{signup_id}/approve", {})
        service = OrganizationService(db)
        organization = service.approve_signup(signup_id)
        log_response(logger, f"POST /organizations/signup/{signup_id}/approve", organization.__dict__)
        return organization
    except ValueError as e:
        log_error(logger, f"POST /organizations/signup/{signup_id}/approve", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        log_error(logger, f"POST /organizations/signup/{signup_id}/approve", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/signup/{signup_id}/reject", response_model=ApplicationSignup)
async def reject_signup(
    signup_id: uuid.UUID,
    reason: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Reject an application signup request"""
    try:
        log_request(logger, f"POST /organizations/signup/{signup_id}/reject", {"reason": reason})
        service = OrganizationService(db)
        signup = service.reject_signup(signup_id, reason)
        log_response(logger, f"POST /organizations/signup/{signup_id}/reject", signup.__dict__)
        return signup
    except ValueError as e:
        log_error(logger, f"POST /organizations/signup/{signup_id}/reject", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        log_error(logger, f"POST /organizations/signup/{signup_id}/reject", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/invite", response_model=OrganizationInviteResponse)
async def create_organization_invite(
    invite_data: OrganizationInvite,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Create an organization invite"""
    try:
        log_request(logger, "POST /organizations/invite", invite_data.dict())
        service = OrganizationService(db)
        invite = service.create_organization_invite(invite_data)
        log_response(logger, "POST /organizations/invite", invite)
        return invite
    except ValueError as e:
        log_error(logger, "POST /organizations/invite", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        log_error(logger, "POST /organizations/invite", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/{organization_id}", response_model=Organization)
async def get_organization(
    organization_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get organization details"""
    try:
        log_request(logger, f"GET /organizations/{organization_id}", {})
        service = OrganizationService(db)
        organization = service.get_organization(organization_id)
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        log_response(logger, f"GET /organizations/{organization_id}", organization.__dict__)
        return organization
    except Exception as e:
        log_error(logger, f"GET /organizations/{organization_id}", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.put("/{organization_id}", response_model=Organization)
async def update_organization(
    organization_id: uuid.UUID,
    update_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Update organization details"""
    try:
        log_request(logger, f"PUT /organizations/{organization_id}", update_data)
        service = OrganizationService(db)
        organization = service.update_organization(organization_id, update_data)
        log_response(logger, f"PUT /organizations/{organization_id}", organization.__dict__)
        return organization
    except ValueError as e:
        log_error(logger, f"PUT /organizations/{organization_id}", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        log_error(logger, f"PUT /organizations/{organization_id}", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/{organization_id}/config", response_model=ApplicationConfiguration)
async def get_organization_config(
    organization_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get organization application configuration"""
    try:
        log_request(logger, f"GET /organizations/{organization_id}/config", {})
        service = OrganizationService(db)
        config = service.get_organization_config(organization_id)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization configuration not found"
            )
        log_response(logger, f"GET /organizations/{organization_id}/config", config.__dict__)
        return config
    except Exception as e:
        log_error(logger, f"GET /organizations/{organization_id}/config", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.put("/{organization_id}/config", response_model=ApplicationConfiguration)
async def update_organization_config(
    organization_id: uuid.UUID,
    config_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Update organization application configuration"""
    try:
        log_request(logger, f"PUT /organizations/{organization_id}/config", config_data)
        service = OrganizationService(db)
        config = service.update_organization_config(organization_id, config_data)
        log_response(logger, f"PUT /organizations/{organization_id}/config", config.__dict__)
        return config
    except ValueError as e:
        log_error(logger, f"PUT /organizations/{organization_id}/config", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        log_error(logger, f"PUT /organizations/{organization_id}/config", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/{organization_id}/info", response_model=OrganizationInfo)
async def get_organization_info(
    organization_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get organization info"""
    try:
        log_request(logger, f"GET /organizations/{organization_id}/info", {})
        service = OrganizationService(db)
        info = service.get_organization_info(organization_id)
        if not info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization info not found"
            )
        log_response(logger, f"GET /organizations/{organization_id}/info", info.__dict__)
        return info
    except Exception as e:
        log_error(logger, f"GET /organizations/{organization_id}/info", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.put("/{organization_id}/info", response_model=OrganizationInfo)
async def update_organization_info(
    organization_id: uuid.UUID,
    info_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Update organization info"""
    try:
        log_request(logger, f"PUT /organizations/{organization_id}/info", info_data)
        service = OrganizationService(db)
        info = service.update_organization_info(organization_id, info_data)
        log_response(logger, f"PUT /organizations/{organization_id}/info", info.__dict__)
        return info
    except ValueError as e:
        log_error(logger, f"PUT /organizations/{organization_id}/info", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        log_error(logger, f"PUT /organizations/{organization_id}/info", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/{organization_id}/additional-info", response_model=Dict[str, Any])
async def get_additional_info(
    organization_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get organization additional info"""
    try:
        log_request(logger, f"GET /organizations/{organization_id}/additional-info", {})
        service = OrganizationService(db)
        additional_info = service.get_additional_info(organization_id)
        if additional_info is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization info not found"
            )
        log_response(logger, f"GET /organizations/{organization_id}/additional-info", additional_info)
        return additional_info
    except Exception as e:
        log_error(logger, f"GET /organizations/{organization_id}/additional-info", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.put("/{organization_id}/additional-info", response_model=OrganizationInfo)
async def update_additional_info(
    organization_id: uuid.UUID,
    additional_info: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Update organization additional info"""
    try:
        log_request(logger, f"PUT /organizations/{organization_id}/additional-info", additional_info)
        service = OrganizationService(db)
        info = service.update_additional_info(organization_id, additional_info)
        log_response(logger, f"PUT /organizations/{organization_id}/additional-info", info.__dict__)
        return info
    except ValueError as e:
        log_error(logger, f"PUT /organizations/{organization_id}/additional-info", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        log_error(logger, f"PUT /organizations/{organization_id}/additional-info", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        ) 
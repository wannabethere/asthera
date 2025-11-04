from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User, UserToken
from app.models.rbac import Role, Permission
from app.auth.okta import create_access_token, get_current_user
from app.settings import get_settings
from app.services.user_service import UserService
from datetime import timedelta, datetime
from pydantic import BaseModel, EmailStr
from typing import Optional, Set, List
from passlib.context import CryptContext
import uuid
from jose import JWTError, jwt
import logging
import json

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Initialize password context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# In-memory storage (replace with database in production)
users_db = {}
logged_in_users: Set[str] = set()

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = ""

class UserInfo(BaseModel):
    id: str
    email: str
    username: str
    first_name: Optional[str]
    last_name: Optional[str]



class UserResponse(BaseModel):
    id: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    is_active: bool
    is_superuser: bool
    roles: List[str] = []

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    expires_at: datetime
    user: UserResponse

class LoginRequest(BaseModel):
    email: str
    password: str

class SessionResponse(BaseModel):
    is_valid: bool
    user: Optional[UserResponse] = None
    error: Optional[str] = None

def create_user_token(db: Session, user: User, token: str, expires_delta: timedelta, request: Request = None) -> UserToken:
    """Create a new user token record"""
    expires_at = datetime.utcnow() + expires_delta
    
    # Get device info and IP address from request if available
    device_info = None
    ip_address = None
    if request:
        user_agent = request.headers.get("user-agent")
        if user_agent:
            device_info = user_agent
        ip_address = request.client.host if request.client else None

    user_token = UserToken(
        user_id=user.id,
        token=token,
        expires_at=expires_at,
        device_info=device_info,
        ip_address=ip_address
    )
    
    db.add(user_token)
    db.commit()
    db.refresh(user_token)
    return user_token

@router.post("/register", response_model=UserResponse)
async def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    # Check if user already exists with the same email
    existing_user_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_user_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if user already exists with the same username
    if user_data.username:
        existing_user_username = db.query(User).filter(User.username == user_data.username).first()
        if existing_user_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
    
    try:
        # Create user with default memberships using the service
        user_service = UserService(db)
        user = user_service.create_user_with_defaults(
            email=user_data.email,
            password=user_data.password,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            username=user_data.username
        )
        
        return user_to_response(user)
        
    except Exception as e:
        logger.error(f"Error in user registration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating user account"
        )

@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    request: Request = None
):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not user.check_password(form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires
    )
    
    # Create token record
    user_token = create_user_token(db, user, access_token, access_token_expires, request)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_at": user_token.expires_at
    }

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.post("/login", response_model=Token)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
    http_request: Request = None
):
    """Handle user login and return JWT token with user details"""
    try:
        logger.info(f"Login attempt for email: {request.email}")
        
        # Query user from database
        user = db.query(User).filter(User.email == request.email).first()
        logger.info(f"User found: {user.id if user else 'None'}")
        
        # Validate user exists and password is correct
        if not user or not user.check_password(request.password):
            logger.warning(f"Invalid credentials for email: {request.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Generate JWT token with 1 year validity
        access_token_expires = timedelta(days=365)  # 1 year
        logger.info(f"Creating access token for user {user.id}")
        
        # Create token data
        token_data = {"sub": str(user.id)}
        logger.info(f"Token data: {token_data}")
        
        access_token = create_access_token(
            data=token_data,
            expires_delta=access_token_expires
        )
        logger.info(f"Access token created: {access_token[:20]}...")
        
        # Create token record
        user_token = create_user_token(db, user, access_token, access_token_expires, http_request)
        logger.info(f"User token record created with ID: {user_token.id}")
        
        # Convert user to response model
        user_response = user_to_response(user)
        
        # Create response using the Token model
        response = Token(
            access_token=access_token,
            token_type="bearer",
            expires_at=user_token.expires_at,
            user=user_response
        )
        
        logger.info(f"Login response prepared for user {user.id}")
        logger.debug(f"Full login response: {response.json()}")
        
        return response
        
    except Exception as e:
        logger.error(f"Error during login: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

@router.post("/validate-session", response_model=SessionResponse)
async def validate_session(
    token: str,
    db: Session = Depends(get_db)
):
    """
    Validate an existing JWT session token and return user information if valid.
    This endpoint can be used to check if a user's session is still valid.
    """
    try:
        # First check if token exists in database and is active
        db_token = db.query(UserToken).filter(
            UserToken.token == token,
            UserToken.is_active == True,
            UserToken.expires_at > datetime.utcnow()
        ).first()
        
        if not db_token:
            return SessionResponse(
                is_valid=False,
                error="Invalid or expired token"
            )
        
        # Decode and verify the JWT token
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            return SessionResponse(
                is_valid=False,
                error="Invalid token payload"
            )
        
        # Get user from database
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            return SessionResponse(
                is_valid=False,
                error="User not found"
            )
        
        # Check if user is still active
        if not user.is_active:
            return SessionResponse(
                is_valid=False,
                error="User account is inactive"
            )
        
        # Update last used timestamp
        db_token.last_used_at = datetime.utcnow()
        db.commit()
        
        # Return successful validation with user info
        return SessionResponse(
            is_valid=True,
            user=user_to_response(user)
        )
    except JWTError:
        return SessionResponse(
            is_valid=False,
            error="Invalid or expired token"
        )
    except Exception as e:
        return SessionResponse(
            is_valid=False,
            error=f"Error validating session: {str(e)}"
        )

@router.post("/logout")
async def logout(token: str, db: Session = Depends(get_db)):
    """Invalidate a JWT token"""
    db_token = db.query(UserToken).filter(UserToken.token == token).first()
    if db_token:
        db_token.is_active = False
        db.commit()
        return {"message": "Successfully logged out"}
    return {"message": "Token not found"}

def user_to_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        roles=[role.name for role in user.roles]
    ) 
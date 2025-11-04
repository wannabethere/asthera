from fastapi import HTTPException, Security, Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
from typing import Optional
from app.models.user import User
from sqlalchemy.orm import Session
from app.settings import get_settings
from app.database import get_db
import jwt
from datetime import datetime, timedelta
 # Okta verification
from okta_jwt_verifier import JWTVerifier
from jose import JWTError
import logging

settings = get_settings()
security = HTTPBearer()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

logger = logging.getLogger(__name__)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt

async def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    try:
        token = credentials.credentials
        if settings.USE_OKTA:
           
            jwt_verifier = JWTVerifier(
                issuer=settings.OKTA_ISSUER,
                client_id=settings.OKTA_CLIENT_ID
            )
            claims = await jwt_verifier.verify_access_token(token)
        else:
            # Local JWT verification
            claims = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return claims
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials"
        )

async def get_current_user_old(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError as e:
        logger.error(f"JWT decode error: {str(e)}")
        raise credentials_exception
        
    # Check if user exists in the database
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user

# New get_current_user using HTTPBearer
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError as e:
        logger.error(f"JWT decode error: {str(e)}")
        raise credentials_exception
        
    # Check if user exists in the database
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user

async def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges"
        )
    return current_user

async def get_current_user_ws(token: str, db: Session = Depends(get_db)) -> Optional[User]:
    """
    Get current user from JWT token for WebSocket connections.
    Returns None instead of raising an exception for better WebSocket error handling.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            logger.error("No user_id in JWT payload")
            return None
            
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            logger.error(f"User not found for id: {user_id}")
            return None
            
        return user
        
    except JWTError as e:
        logger.error(f"JWT decode error in WebSocket auth: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in WebSocket auth: {str(e)}")
        return None 
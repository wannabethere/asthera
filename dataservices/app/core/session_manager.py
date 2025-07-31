from typing import Dict, Any, Optional
import logging
from datetime import datetime, timedelta
import uuid
from app.core.settings import ServiceConfig
from app.schemas.dbmodels import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
logger = logging.getLogger(__name__)

class SessionManager:
    """Manages user sessions and their associated data, including database operations."""
    
    _instance = None
    
    def __new__(cls, config: ServiceConfig = None, session_timeout: int = 3600):
        """Singleton pattern to ensure only one session manager instance"""
        if cls._instance is None:
            cls._instance = super(SessionManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, config: ServiceConfig = None, session_timeout: int = 3600):
        """Initialize the session manager.
        
        Args:
            config: Service configuration containing database settings
            session_timeout: Time in seconds before a session expires (default: 1 hour)
        """
        # Only initialize if not already initialized
        if hasattr(self, '_sessions'):
            return
            
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._session_timeout = session_timeout
        self.config = config
        
        if config:
            self.engine = create_async_engine(
            config.database_url,  # Must be 'postgresql+asyncpg://...'
            echo=config.log_level == "DEBUG"
            )
        self.async_session_maker = async_sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            class_=AsyncSession
        )
        
    async def create_tables(self):
        async with self.engine.begin() as conn:
            print("Creating tables...")
            await conn.run_sync(Base.metadata.create_all)
    
    # def get_db_session(self) -> Session:
    #     """Get database session"""
    #     if not hasattr(self, 'SessionLocal'):
    #         raise RuntimeError("SessionManager not initialized with config")
    #     return self.SessionLocal()
    
    @asynccontextmanager
    async def get_async_db_session(self):
        async with self.async_session_maker() as session:
            try:
                yield session
            finally:
                await session.close()
    
    @classmethod
    def get_instance(cls) -> 'SessionManager':
        """Get the singleton instance of SessionManager"""
        if cls._instance is None:
            raise RuntimeError("SessionManager not initialized. Call SessionManager(config) first.")
        return cls._instance
        
    def create_session(self, user_id: Optional[str] = None) -> str:
        """Create a new session.
        
        Args:
            user_id: Optional user ID to associate with the session
            
        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = {
            'created_at': datetime.utcnow(),
            'last_accessed': datetime.utcnow(),
            'user_id': user_id,
            'data': {}
        }
        logger.info(f"Created new session {session_id} for user {user_id}")
        return session_id
        
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data if it exists and hasn't expired.
        
        Args:
            session_id: ID of the session to retrieve
            
        Returns:
            Session data if valid, None otherwise
        """
        if session_id not in self._sessions:
            return None
            
        session = self._sessions[session_id]
        if self._is_session_expired(session):
            self.delete_session(session_id)
            return None
            
        # Update last accessed time
        session['last_accessed'] = datetime.utcnow()
        return session
        
    def update_session_data(self, session_id: str, data: Dict[str, Any]) -> bool:
        """Update session data.
        
        Args:
            session_id: ID of the session to update
            data: New session data
            
        Returns:
            True if update was successful, False otherwise
        """
        if session := self.get_session(session_id):
            session['data'].update(data)
            return True
        return False
        
    def delete_session(self, session_id: str) -> None:
        """Delete a session.
        
        Args:
            session_id: ID of the session to delete
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Deleted session {session_id}")
            
    def _is_session_expired(self, session: Dict[str, Any]) -> bool:
        """Check if a session has expired.
        
        Args:
            session: Session data to check
            
        Returns:
            True if session has expired, False otherwise
        """
        last_accessed = session['last_accessed']
        expiration_time = last_accessed + timedelta(seconds=self._session_timeout)
        return datetime.utcnow() > expiration_time
        
    def cleanup_expired_sessions(self) -> int:
        """Remove all expired sessions.
        
        Returns:
            Number of sessions removed
        """
        expired_sessions = [
            session_id for session_id, session in self._sessions.items()
            if self._is_session_expired(session)
        ]
        
        for session_id in expired_sessions:
            self.delete_session(session_id)
            
        return len(expired_sessions)
        
    def get_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Get all active (non-expired) sessions.
        
        Returns:
            Dictionary of active sessions
        """
        return {
            session_id: session
            for session_id, session in self._sessions.items()
            if not self._is_session_expired(session)
        } 
    




from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
import os
from app.config.settings import get_settings

# Create a base class for models
Base = declarative_base()

class PostgresManager:
    def __init__(self):
        settings = get_settings()
        # Create database URL from environment variables
        db_url = f"postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
        
        # Create SQLAlchemy engine
        self.engine = create_engine(db_url)
        
        # Create session factory
        self.session_factory = sessionmaker(bind=self.engine)
        
        # Create a scoped session
        self.Session = scoped_session(self.session_factory)
        
        # Create a session for use
        self._session = None
    
    @property
    def session(self):
        """Get the current session or create a new one if none exists"""
        if self._session is None:
            self._session = self.Session()
        return self._session
    
    def close(self):
        """Close the current session"""
        if self._session is not None:
            self._session.close()
            self._session = None
        
    def init_db(self):
        """Initialize database tables"""
        # Use the Base class defined at the module level
        Base.metadata.create_all(self.engine)

# Create a singleton instance
postgres_manager = PostgresManager() 
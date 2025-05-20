# This is how sessionmanager.py should be updated
from typing import Dict, Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from app.settings import get_settings

settings = get_settings()

def get_session_manager(db_config: Dict[str, Any] = None):
    """
    Get or create a session manager for database operations.
    
    Args:
        db_config: Optional database configuration dict. If not provided,
                  it will use settings from the Settings class.
    
    Returns:
        SessionManager instance
    """
    if db_config is None:
        # Get settings instance
        settings = get_settings()
        
        # Create db_config from settings
        db_config = {
            "host": settings.POSTGRES_HOST,
            "port": settings.POSTGRES_PORT,
            "database": settings.POSTGRES_DB,
            "user": settings.POSTGRES_USER,
            "password": settings.POSTGRES_PASSWORD
        }
    
    return SessionManager(db_config)

class SessionManager:
    """Manager for database sessions."""
    
    def __init__(self, db_config: Dict[str, Any]):
        """
        Initialize the session manager.
        
        Args:
            db_config: Database configuration dict with host, port, database, user, password
        """
        self.db_config = db_config
        self.engine = self._create_engine()
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    def _create_engine(self):
        """Create SQLAlchemy engine from configuration."""
        db_url = f"postgresql://{self.db_config['user']}:{self.db_config['password']}@{self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}"
        return create_engine(db_url)
    
    @contextmanager
    def get_session(self):
        """Get a database session."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_db(self):
        """Generator for FastAPI dependency injection."""
        with self.get_session() as session:
            yield session
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging
from app.settings import get_settings, get_postgres_url

logger = logging.getLogger(__name__)

settings = get_settings()

SQLALCHEMY_DATABASE_URL = get_postgres_url(settings)

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create a new MetaData instance
metadata = MetaData()
Base = declarative_base(metadata=metadata)

def init_db():
    """
    Initialize the database by creating all tables.
    Only drops existing tables if ENABLE_DB_INIT is True.
    """
    # Clear any existing metadata
    metadata.clear()
    
    # Import all models here to ensure they are registered with Base
    # Import order matters - import base models first, then models with foreign keys
    from app.models.user import User  # Base model
    from app.models.team import Team  # Depends on User
    from app.models.workspace import Workspace, Project, WorkspaceAccess, ProjectAccess  # Depends on Team and User
    from app.models.thread import Thread  # Depends on Project and User
    from app.models.rbac import Permission, Role, role_permissions, user_roles  # RBAC tables
    
    try:
        
        # Only drop tables if initialization is enabled
        if settings.ENABLE_DB_INIT:
            # Drop all tables in reverse order of dependencies
            for table in reversed(metadata.sorted_tables):
                print(f"Dropping table: {table.name}")
                table.drop(engine, checkfirst=True)
            print("Dropped all existing tables")
        
        # Create tables in explicit order following the hierarchy
        tables_to_create = [
            # 1. Base tables
            User.__table__,
            Team.__table__,
            
            # 2. Workspace and Project tables
            Workspace.__table__,
            Project.__table__,
            
            # 3. Access control tables
            WorkspaceAccess.__table__,
            ProjectAccess.__table__,
            
            # 4. Thread table
            Thread.__table__,
            
            # 5. RBAC tables
            Permission.__table__,
            Role.__table__,
            role_permissions,
            user_roles
        ]
        
        print("\nCreating tables in order:")
        for table in tables_to_create:
            print(f"Creating table: {table.name}")
            table.create(engine, checkfirst=True)
        print("\nCreated all tables successfully")
        
    except Exception as e:
        logger.error(f"Error during database initialization: {str(e)}")
        raise

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 
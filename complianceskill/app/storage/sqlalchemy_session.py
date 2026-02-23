"""
SQLAlchemy session management for ingestion module.
Reuses existing database configuration from storage infrastructure.
"""

import os
import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine setup - reuses existing database config
# ---------------------------------------------------------------------------

_settings = None
_engine = None
_SessionLocal = None


def _get_database_url() -> str:
    """Build database URL from settings, with fallback to DATABASE_URL env var."""
    # First try DATABASE_URL env var (for backward compatibility)
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url
    
    # Otherwise build from settings
    settings = get_settings()
    db_config = settings.get_database_config()
    
    if db_config["type"] == "postgres":
        user = db_config.get("user") or "postgres"
        password = db_config.get("password") or "postgres"
        host = db_config.get("host") or "localhost"
        port = db_config.get("port", 5432)
        database = db_config.get("database") or "framework_kb"
        
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"
    else:
        raise ValueError(f"SQLAlchemy session only supports PostgreSQL, got: {db_config['type']}")


def _get_engine():
    """Get or create SQLAlchemy engine."""
    global _engine
    if _engine is None:
        database_url = _get_database_url()
        _engine = create_engine(
            database_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,   # reconnect on stale connections
            echo=os.getenv("SQL_ECHO", "false").lower() == "true",
        )
        logger.info(f"SQLAlchemy engine created for ingestion")
    return _engine


def _get_session_local():
    """Get or create session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        engine = _get_engine()
        _SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return _SessionLocal


# ---------------------------------------------------------------------------
# Table management
# ---------------------------------------------------------------------------

def create_tables(drop_existing: bool = False) -> None:
    """
    Create all tables defined in models. Safe to call multiple times.
    
    Args:
        drop_existing: If True, drop all existing tables first (destructive).
                      Use only in dev/test environments.
    
    Creates tables in dependency order to avoid foreign key constraint issues.
    """
    # Lazy import to avoid circular dependency
    from app.ingestion.models import Base
    
    engine = _get_engine()
    
    # Drop existing tables if requested (for clean slate)
    if drop_existing:
        logger.warning("Dropping all existing tables...")
        Base.metadata.drop_all(bind=engine)
        logger.info("All tables dropped.")
    
    # Import models to ensure they're registered with Base
    from app.ingestion.models import (
        Framework,
        Requirement,
        Risk,
        Control,
        TestCase,
        Scenario,
        RiskControl,
        RequirementControl,
        ScenarioControl,
        CrossFrameworkMapping,
        UserSession,
        UploadedDocument,
        DocumentChunk,
        GapAnalysisResult,
    )
    
    # Use create_all with checkfirst=True - SQLAlchemy handles dependency order
    # This is safer than manual ordering and handles all edge cases
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
        logger.info("Database tables created / verified.")
    except Exception as exc:
        # If creation fails, it might be due to existing tables with wrong schema
        # Log the error and suggest dropping tables
        logger.error(f"Failed to create tables: {exc}")
        logger.error("If tables exist with a different schema, try dropping them first:")
        logger.error("  from app.storage.sqlalchemy_session import drop_tables; drop_tables()")
        raise


def drop_tables(cascade: bool = True) -> None:
    """
    Drop all tables. Destructive — use only in dev/test environments.
    
    Args:
        cascade: If True, use CASCADE to drop dependent objects (views, constraints, etc.)
    """
    # Lazy import to avoid circular dependency
    from app.ingestion.models import Base
    
    engine = _get_engine()
    
    if cascade:
        # Drop with CASCADE to handle dependent objects (views, constraints, etc.)
        with engine.connect() as conn:
            # Get all table names from metadata
            table_names = [table.name for table in Base.metadata.sorted_tables]
            
            # Drop each table with CASCADE
            for table_name in reversed(table_names):  # Reverse order for dependencies
                try:
                    conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))
                    logger.debug(f"Dropped table: {table_name}")
                except Exception as exc:
                    logger.warning(f"Error dropping table {table_name}: {exc}")
            
            conn.commit()
        
        logger.warning("All database tables dropped (with CASCADE).")
    else:
        # Standard drop (will fail if dependencies exist)
        Base.metadata.drop_all(bind=engine)
        logger.warning("All database tables dropped.")


def check_connection() -> bool:
    """Verify database connectivity. Returns True on success."""
    try:
        engine = _get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error(f"Database connection failed: {exc}")
        return False


# ---------------------------------------------------------------------------
# Session context manager
# ---------------------------------------------------------------------------

@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Yields a SQLAlchemy Session with automatic commit/rollback.
    Reuses existing database configuration.

    Usage:
        with get_session() as session:
            session.add(some_object)
    """
    SessionLocal = _get_session_local()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session_dependency() -> Generator[Session, None, None]:
    """
    FastAPI dependency style session provider (no auto-commit).
    Caller is responsible for commit.
    """
    SessionLocal = _get_session_local()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def get_security_intel_session(source: str) -> Generator[Session, None, None]:
    """
    Get SQLAlchemy session for a specific security intelligence source.
    
    Supports separate database connections for different security intelligence sources:
    - "cve_attack": CVE → ATT&CK mappings, ATT&CK → Control mappings
    - "cpe": CPE dictionary and CVE-CPE relationships
    - "exploit": Exploit-DB, Metasploit, Nuclei templates
    - "compliance": CIS benchmarks, Sigma rules
    
    If source-specific configuration is not provided, falls back to default database.
    
    Args:
        source: Security intelligence source identifier
    
    Yields:
        SQLAlchemy Session with automatic commit/rollback
    """
    settings = get_settings()
    db_config = settings.get_security_intel_db_config(source)
    
    # Check if using default database
    default_config = settings.get_database_config()
    if (db_config.get("host") == default_config.get("host") and
        db_config.get("database") == default_config.get("database")):
        # Use default session - delegate to get_session context manager
        logger.debug(f"Source '{source}' using default database session")
        # Properly delegate to the get_session context manager
        with get_session() as session:
            yield session
        return
    
    # Create source-specific engine and session
    if db_config["type"] == "postgres":
        user = db_config.get("user") or "postgres"
        password = db_config.get("password") or "postgres"
        host = db_config.get("host") or "localhost"
        port = db_config.get("port", 5432)
        database = db_config.get("database") or "framework_kb"
        
        database_url = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        
        engine = create_engine(
            database_url,
            pool_size=db_config.get("pool_min_size", 10),
            max_overflow=db_config.get("pool_max_size", 20) - db_config.get("pool_min_size", 10),
            pool_pre_ping=True,
            echo=os.getenv("SQL_ECHO", "false").lower() == "true",
        )
        
        SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        session = SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
            engine.dispose()
    else:
        raise ValueError(f"SQLAlchemy session only supports PostgreSQL, got: {db_config['type']}")

#!/usr/bin/env python3
"""
Database table management script for security intelligence tables.

This script provides a convenient way to create or drop security intelligence
database tables from Python, using the database configuration from settings.

Usage:
    # Create all tables
    python manage_tables.py create

    # Create only Phase 1 tables
    python manage_tables.py create --phase 1

    # Drop all tables
    python manage_tables.py drop

    # Drop only Phase 1 tables
    python manage_tables.py drop --phase 1

    # Create tables in source-specific database
    python manage_tables.py create --source cve_attack
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import create_engine, text
from app.core.settings import get_settings

logger = logging.getLogger(__name__)

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent


def get_database_url(source: Optional[str] = None) -> str:
    """
    Get database URL for the specified source.
    
    Args:
        source: Security intelligence source (cve_attack, cpe, exploit, compliance)
                If None, uses default database
    
    Returns:
        Database connection URL
    """
    settings = get_settings()
    
    if source:
        db_config = settings.get_security_intel_db_config(source)
    else:
        db_config = settings.get_database_config()
    
    if db_config["type"] == "postgres":
        user = db_config.get("user") or "postgres"
        password = db_config.get("password") or "postgres"
        host = db_config.get("host") or "localhost"
        port = db_config.get("port", 5432)
        database = db_config.get("database") or "framework_kb"
        
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"
    else:
        raise ValueError(f"Unsupported database type: {db_config['type']}")


def execute_sql_file(engine, sql_file: Path, source: Optional[str] = None):
    """
    Execute a SQL file using the provided engine.
    
    Args:
        engine: SQLAlchemy engine
        sql_file: Path to SQL file
        source: Source name for logging
    """
    if not sql_file.exists():
        raise FileNotFoundError(f"SQL file not found: {sql_file}")
    
    logger.info(f"Executing SQL file: {sql_file.name}")
    if source:
        logger.info(f"Using database for source: {source}")
    
    with open(sql_file, 'r') as f:
        sql_content = f.read()
    
    # Split by semicolons and execute each statement
    # Note: This is a simple approach. For complex SQL with functions/triggers,
    # we execute the whole file as one transaction
    with engine.connect() as conn:
        # Use a transaction
        trans = conn.begin()
        try:
            # Execute the entire SQL file
            conn.execute(text(sql_content))
            trans.commit()
            logger.info(f"Successfully executed {sql_file.name}")
        except Exception as e:
            trans.rollback()
            logger.error(f"Error executing {sql_file.name}: {e}")
            raise


def create_tables(phase: Optional[int] = None, source: Optional[str] = None):
    """
    Create security intelligence tables.
    
    Args:
        phase: Phase number (1, 2, 3) or None for all phases
        source: Security intelligence source (cve_attack, cpe, exploit, compliance)
    """
    db_url = get_database_url(source)
    engine = create_engine(db_url, echo=False)
    
    if phase == 1:
        sql_file = SCRIPT_DIR / "create_phase1_only.sql"
        logger.info("Creating Phase 1 (Critical) tables only")
    else:
        sql_file = SCRIPT_DIR / "create_tables.sql"
        logger.info("Creating all security intelligence tables")
    
    execute_sql_file(engine, sql_file, source)
    logger.info("✓ Tables created successfully")


def drop_tables(phase: Optional[int] = None, source: Optional[str] = None):
    """
    Drop security intelligence tables.
    
    Args:
        phase: Phase number (1, 2, 3) or None for all phases
        source: Security intelligence source (cve_attack, cpe, exploit, compliance)
    """
    db_url = get_database_url(source)
    engine = create_engine(db_url, echo=False)
    
    if phase == 1:
        sql_file = SCRIPT_DIR / "drop_phase1_only.sql"
        logger.info("Dropping Phase 1 (Critical) tables only")
    else:
        sql_file = SCRIPT_DIR / "drop_tables.sql"
        logger.info("Dropping all security intelligence tables")
    
    # Confirm before dropping
    response = input("⚠️  WARNING: This will delete all data. Continue? (yes/no): ")
    if response.lower() != 'yes':
        logger.info("Operation cancelled")
        return
    
    execute_sql_file(engine, sql_file, source)
    logger.info("✓ Tables dropped successfully")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Manage security intelligence database tables",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create all tables in default database
  python manage_tables.py create

  # Create only Phase 1 tables
  python manage_tables.py create --phase 1

  # Create tables in source-specific database
  python manage_tables.py create --source cve_attack

  # Drop all tables
  python manage_tables.py drop

  # Drop only Phase 1 tables
  python manage_tables.py drop --phase 1
        """
    )
    
    parser.add_argument(
        'action',
        choices=['create', 'drop'],
        help='Action to perform: create or drop tables'
    )
    
    parser.add_argument(
        '--phase',
        type=int,
        choices=[1, 2, 3],
        help='Phase number (1=Critical, 2=Enhanced, 3=Compliance). If not specified, all phases are included.'
    )
    
    parser.add_argument(
        '--source',
        choices=['cve_attack', 'cpe', 'exploit', 'compliance'],
        help='Security intelligence source. If not specified, uses default database.'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        if args.action == 'create':
            create_tables(phase=args.phase, source=args.source)
        elif args.action == 'drop':
            drop_tables(phase=args.phase, source=args.source)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=args.verbose)
        sys.exit(1)


if __name__ == '__main__':
    main()

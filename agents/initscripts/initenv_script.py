#!/usr/bin/env python3
"""
Database Setup Script

This script reads environment variables from a .env file,
connects to a PostgreSQL database, and creates all necessary tables
for the team collaboration system using the predefined schema.

Usage:
    python db_setup.py --env-file=.env --schema-file=schema.sql

Example:
    python db_setup.py --env-file=.env.prod --schema-file=./sql/schema.sql
"""

import os
import sys
import argparse
import logging
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('db_setup')

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Database setup script")
    parser.add_argument('--env-file', default='.env', help='Path to the environment file')
    parser.add_argument('--schema-file', default='schema.sql', help='Path to the SQL schema file')
    parser.add_argument('--create-db', action='store_true', help='Create the database if it does not exist')
    return parser.parse_args()

def parse_env_file(file_path: str) -> dict:
    """
    Parse a .env file and return a dictionary of key-value pairs
    
    Args:
        file_path: Path to the .env file
        
    Returns:
        Dictionary of environment variables
    """
    if not os.path.exists(file_path):
        logger.error(f"Environment file not found: {file_path}")
        return {}
    
    env_vars = {}
    
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Handle export keyword (shell compatibility)
            if line.startswith('export '):
                line = line[7:]
            
            # Split by first equals sign
            if '=' not in line:
                logger.warning(f"Invalid line in {file_path}: {line}")
                continue
                
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()
            
            # Remove quotes if present
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            
            env_vars[key] = value
    
    return env_vars

def load_env_vars(env_vars: dict, overwrite: bool = False) -> None:
    """
    Load environment variables into os.environ
    
    Args:
        env_vars: Dictionary of environment variables
        overwrite: Whether to overwrite existing environment variables
    """
    for key, value in env_vars.items():
        if overwrite or key not in os.environ:
            os.environ[key] = value
            logger.debug(f"Set environment variable: {key}")

def read_sql_file(file_path: str) -> str:
    """
    Read a SQL file and return its contents
    
    Args:
        file_path: Path to the SQL file
        
    Returns:
        Contents of the SQL file
    """
    if not os.path.exists(file_path):
        logger.error(f"SQL file not found: {file_path}")
        return ""
    
    with open(file_path, 'r') as f:
        return f.read()

def create_database_if_not_exists(db_config: dict) -> bool:
    """
    Create the database if it does not exist
    
    Args:
        db_config: Database configuration dictionary
        
    Returns:
        True if the database was created or already exists, False otherwise
    """
    # Create a connection to the PostgreSQL server (not to a specific database)
    conn_params = {
        'host': db_config['host'],
        'port': db_config['port'],
        'user': db_config['user'],
        'password': db_config['password']
    }
    
    try:
        conn = psycopg2.connect(**conn_params, database='postgres')
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = %s;", (db_config['database'],))
        exists = cursor.fetchone()
        
        if not exists:
            logger.info(f"Creating database: {db_config['database']}")
            cursor.execute(f"CREATE DATABASE {db_config['database']};")
            logger.info(f"Database created: {db_config['database']}")
        else:
            logger.info(f"Database already exists: {db_config['database']}")
        
        cursor.close()
        conn.close()
        return True
    
    except Exception as e:
        logger.error(f"Error creating database: {e}")
        return False

def create_tables(db_config: dict, sql_script: str) -> bool:
    """
    Execute the SQL script to create the tables
    
    Args:
        db_config: Database configuration dictionary
        sql_script: SQL script to execute
        
    Returns:
        True if the tables were created successfully, False otherwise
    """
    conn_params = {
        'host': db_config['host'],
        'port': db_config['port'],
        'user': db_config['user'],
        'password': db_config['password'],
        'database': db_config['database']
    }
    
    try:
        conn = psycopg2.connect(**conn_params)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        logger.info("Executing SQL script to create tables...")
        cursor.execute(sql_script)
        
        cursor.close()
        conn.close()
        
        logger.info("Tables created successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        return False

def main():
    """Main function"""
    args = parse_args()
    
    # Parse and load environment variables
    env_vars = parse_env_file(args.env_file)
    if not env_vars:
        logger.error("No environment variables found")
        sys.exit(1)
    
    load_env_vars(env_vars)
    
    # Check required environment variables
    required_vars = ['POSTGRES_HOST', 'POSTGRES_PORT', 'POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD']
    missing_vars = [var for var in required_vars if var not in os.environ]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)
    
    # Configure database connection
    db_config = {
        'host': os.environ['POSTGRES_HOST'],
        'port': os.environ['POSTGRES_PORT'],
        'database': os.environ['POSTGRES_DB'],
        'user': os.environ['POSTGRES_USER'],
        'password': os.environ['POSTGRES_PASSWORD']
    }
    
    # Read SQL schema
    sql_script = read_sql_file(args.schema_file)
    if not sql_script:
        logger.error("No SQL script found")
        sys.exit(1)
    
    # Create database if requested
    if args.create_db:
        if not create_database_if_not_exists(db_config):
            logger.error("Failed to create database")
            sys.exit(1)
    
    # Create tables
    if not create_tables(db_config, sql_script):
        logger.error("Failed to create tables")
        sys.exit(1)
    
    logger.info("Database setup completed successfully")

if __name__ == "__main__":
    main()
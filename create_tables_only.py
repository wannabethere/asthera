#!/usr/bin/env python3
"""
Script to create PostgreSQL tables based on MDL schemas without loading data.
This separates table creation from data loading for better control and debugging.
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
import psycopg2
from psycopg2.extras import RealDictCursor
import sqlalchemy
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError
import warnings

# Suppress pandas warnings
warnings.filterwarnings('ignore', category=FutureWarning)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('create_tables.log')
    ]
)

logger = logging.getLogger(__name__)


class TableCreator:
    """Class for creating PostgreSQL tables based on MDL configurations."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the table creator with configuration."""
        self.config = config
        self.engine = None
        self.connection = None
        self.table_mappings = self._build_table_mappings()
        
    def _build_table_mappings(self) -> Dict[str, Dict[str, str]]:
        """Build mappings between table names and their corresponding MDL schemas."""
        mappings = {}
        
        mdl_directory = Path(self.config['mdl_directory'])
        
        # Define table mappings based on your MDL files
        table_configs = {
            'dev_agents': 'mdl_agents.json',
            'dev_assets': 'mdl_assets.json', 
            'dev_software_instances': 'mdl_software_instances.json',
            'dev_cve': 'mdl_cve.json',
            'dev_network_devices': 'mdl_interfaces.json',  # Correct table name
            'dev_vulnerability_instances': 'mdl_vuln_instance.json'  # Correct table name
        }
        
        for table_name, mdl_file in table_configs.items():
            mdl_path = mdl_directory / mdl_file
            if mdl_path.exists():
                mappings[table_name] = {
                    'mdl_file': str(mdl_path),
                    'table_name': table_name
                }
            else:
                logger.warning(f"MDL file not found: {mdl_path}")
        
        return mappings
    
    def connect_to_database(self) -> bool:
        """Establish connection to PostgreSQL database."""
        try:
            db_config = self.config['database']
            connection_string = (
                f"postgresql://{db_config['user']}:{db_config['password']}@"
                f"{db_config['host']}:{db_config['port']}/{db_config['database']}"
            )
            
            # Add connection timeout and other parameters
            self.engine = create_engine(
                connection_string, 
                echo=False,
                connect_args={
                    "connect_timeout": 30,
                    "application_name": "table_creator"
                },
                pool_timeout=30,
                pool_recycle=3600
            )
            self.connection = self.engine.connect()
            
            logger.info(f"Successfully connected to PostgreSQL database: {db_config['database']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to database: {str(e)}")
            return False
    
    def load_mdl_schema(self, mdl_file_path: str) -> Dict[str, Any]:
        """Load MDL schema from JSON file."""
        try:
            with open(mdl_file_path, 'r') as f:
                schema = json.load(f)
            logger.info(f"Loaded MDL schema from: {mdl_file_path}")
            return schema
        except Exception as e:
            logger.error(f"Failed to load MDL schema from {mdl_file_path}: {str(e)}")
            return {}
    
    def _get_sql_type(self, field_type: str) -> str:
        """Convert MDL field type to PostgreSQL type."""
        type_mapping = {
            'string': 'VARCHAR(255)',
            'text': 'TEXT',
            'integer': 'INTEGER',
            'float': 'REAL',
            'double': 'DOUBLE PRECISION',
            'boolean': 'BOOLEAN',
            'date': 'DATE',
            'datetime': 'TIMESTAMP',
            'timestamp': 'TIMESTAMP',
            'uuid': 'UUID'
        }
        return type_mapping.get(field_type.lower(), 'TEXT')
    
    def _is_parent_table(self, table_name: str) -> bool:
        """Check if table is a parent table that should be created first."""
        parent_tables = ['dev_assets', 'dev_cve']
        return table_name in parent_tables
    
    def _get_foreign_key_constraints(self, table_name: str, schema: Dict[str, Any]) -> List[str]:
        """Generate foreign key constraints for a table."""
        constraints = []
        
        try:
            if 'relationships' not in schema:
                return constraints
            
            for relationship in schema['relationships']:
                if 'condition' not in relationship or 'models' not in relationship:
                    continue
                    
                models = relationship['models']
                condition = relationship['condition']
                
                # Determine which table is the child (references the other)
                if len(models) == 2:
                    other_table = models[1] if models[0] == table_name else models[0]
                    
                    # Only create FK if this table is the child (not a parent table)
                    if not self._is_parent_table(table_name):
                        # Skip conditions with OR as they're too complex for FK constraints
                        if ' OR ' in condition:
                            logger.debug(f"Skipping complex OR condition for {table_name}: {condition}")
                            continue
                        
                        # Parse the condition to extract column references
                        if ' AND ' in condition:
                            # Composite key relationship
                            parts = condition.split(' AND ')
                            fk_columns = []
                            ref_columns = []
                            
                            for part in parts:
                                if '=' in part:
                                    try:
                                        left, right = part.strip().split('=', 1)  # Split only on first '='
                                        left = left.strip()
                                        right = right.strip()
                                        
                                        if f"{table_name}." in left:
                                            fk_columns.append(left.split('.')[1].strip('"'))
                                            ref_columns.append(right.split('.')[1].strip('"'))
                                    except ValueError as e:
                                        logger.warning(f"Failed to parse condition part '{part}': {str(e)}")
                                        continue
                            
                            if fk_columns and ref_columns:
                                fk_clause = f"FOREIGN KEY ({', '.join(fk_columns)}) REFERENCES {other_table}({', '.join(ref_columns)})"
                                constraints.append(fk_clause)
                        else:
                            # Simple key relationship
                            if '=' in condition:
                                try:
                                    left, right = condition.strip().split('=', 1)  # Split only on first '='
                                    left = left.strip()
                                    right = right.strip()
                                    
                                    if f"{table_name}." in left:
                                        fk_column = left.split('.')[1].strip('"')
                                        ref_column = right.split('.')[1].strip('"')
                                        fk_clause = f"FOREIGN KEY ({fk_column}) REFERENCES {other_table}({ref_column})"
                                        constraints.append(fk_clause)
                                except ValueError as e:
                                    logger.warning(f"Failed to parse condition '{condition}': {str(e)}")
                                    continue
        except Exception as e:
            logger.warning(f"Failed to parse foreign key constraints for {table_name}: {str(e)}")
        
        return constraints
    
    def create_table_from_mdl(self, table_name: str, schema: Dict[str, Any]) -> bool:
        """Create PostgreSQL table from MDL schema."""
        try:
            # Find the model for this table
            model = None
            if 'models' in schema:
                for m in schema['models']:
                    if m.get('name') == table_name:
                        model = m
                        break
            
            if not model or 'columns' not in model:
                logger.error(f"No columns found in schema for table: {table_name}")
                return False
            
            # Build column definitions
            columns = []
            
            for column in model['columns']:
                column_name = column['name']
                column_type = self._get_sql_type(column['type'])
                
                # Handle nullable fields (default to True if not specified)
                nullable = column.get('nullable', True)
                not_null = " NOT NULL" if not nullable else ""
                
                column_def = f'"{column_name}" {column_type}{not_null}'
                columns.append(column_def)
            
            # Add primary key constraint from model level
            if 'primaryKey' in model:
                primary_key = model['primaryKey']
                if ',' in primary_key:
                    # Composite primary key
                    pk_columns = [f'"{col.strip()}"' for col in primary_key.split(',')]
                    pk_clause = f'PRIMARY KEY ({", ".join(pk_columns)})'
                else:
                    pk_clause = f'PRIMARY KEY ("{primary_key}")'
                columns.append(pk_clause)
            
            # Get foreign key constraints (but don't add them yet - we'll add them after all tables are created)
            fk_constraints = self._get_foreign_key_constraints(table_name, schema)
            
            # Create table SQL
            create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" (\n  ' + ',\n  '.join(columns) + '\n)'
            
            logger.info(f"Creating table: {table_name}")
            logger.info(f"SQL: {create_sql}")
            
            self.connection.execute(text(create_sql))
            self.connection.commit()
            
            logger.info(f"✓ Successfully created table: {table_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create table {table_name}: {str(e)}")
            return False
    
    def drop_table_if_exists(self, table_name: str) -> bool:
        """Drop table if it exists."""
        try:
            drop_sql = f'DROP TABLE IF EXISTS "{table_name}" CASCADE'
            self.connection.execute(text(drop_sql))
            logger.info(f"Dropped table: {table_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to drop table {table_name}: {str(e)}")
            return False
    
    def create_foreign_key_constraints(self) -> bool:
        """Create foreign key constraints after all tables are created."""
        try:
            logger.info("Creating foreign key constraints...")
            
            # Define the order for creating foreign keys (child tables first)
            fk_order = [
                'dev_agents',
                'dev_software_instances', 
                'dev_network_devices',  # Correct table name
                'dev_vulnerability_instances'  # Correct table name
            ]
            
            for table_name in fk_order:
                if table_name not in self.table_mappings:
                    continue
                    
                schema = self.load_mdl_schema(self.table_mappings[table_name]['mdl_file'])
                if not schema:
                    continue
                
                fk_constraints = self._get_foreign_key_constraints(table_name, schema)
                
                for constraint in fk_constraints:
                    try:
                        # Fix foreign key constraints to only reference nuid from dev_assets
                        if 'dev_assets' in constraint and 'dev_id' in constraint:
                            # Replace composite key with just nuid
                            constraint = constraint.replace('(dev_id, nuid)', '(nuid)')
                            constraint = constraint.replace('dev_assets(dev_id, nuid)', 'dev_assets(nuid)')
                        
                        alter_sql = f'ALTER TABLE "{table_name}" ADD CONSTRAINT fk_{table_name}_{int(time.time())} {constraint}'
                        logger.info(f"Adding constraint: {constraint}")
                        self.connection.execute(text(alter_sql))
                        self.connection.commit()  # Commit each constraint individually
                        logger.info(f"✓ Added constraint to {table_name}")
                    except Exception as e:
                        logger.warning(f"Failed to add constraint to {table_name}: {str(e)}")
                        # Rollback the failed constraint but continue with others
                        try:
                            self.connection.rollback()
                        except:
                            pass
            
            logger.info("✓ All foreign key constraints created")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create foreign key constraints: {str(e)}")
            return False
    
    def create_all_tables(self, drop_existing: bool = False) -> bool:
        """Create all tables in the correct order."""
        try:
            # Define table creation order (parent tables first)
            table_order = [
                'dev_assets',      # Parent table
                'dev_cve',         # Parent table  
                'dev_agents',      # References dev_assets
                'dev_software_instances',  # References dev_assets
                'dev_network_devices',  # References dev_assets - correct table name
                'dev_vulnerability_instances'  # References dev_assets and dev_software_instances - correct table name
            ]
            
            logger.info(f"Creating {len(table_order)} tables...")
            logger.info(f"Table creation order: {table_order}")
            
            success_count = 0
            
            for table_name in table_order:
                if table_name not in self.table_mappings:
                    logger.warning(f"Table {table_name} not found in mappings, skipping...")
                    continue
                
                logger.info(f"Processing table: {table_name}")
                
                # Drop table if requested
                if drop_existing:
                    self.drop_table_if_exists(table_name)
                
                # Load schema
                schema = self.load_mdl_schema(self.table_mappings[table_name]['mdl_file'])
                if not schema:
                    logger.error(f"Failed to load schema for {table_name}")
                    continue
                
                # Create table
                if self.create_table_from_mdl(table_name, schema):
                    success_count += 1
                    logger.info(f"✓ Successfully processed table: {table_name}")
                else:
                    logger.error(f"✗ Failed to process table: {table_name}")
            
            # Create foreign key constraints after all tables are created
            if success_count > 0:
                self.create_foreign_key_constraints()
            
            logger.info(f"✓ Successfully created {success_count}/{len(table_order)} tables")
            return success_count == len(table_order)
            
        except Exception as e:
            logger.error(f"Failed to create tables: {str(e)}")
            return False
    
    def list_existing_tables(self) -> List[str]:
        """List existing tables in the database."""
        try:
            inspector = inspect(self.engine)
            tables = inspector.get_table_names()
            logger.info(f"Existing tables: {tables}")
            return tables
        except Exception as e:
            logger.error(f"Failed to list tables: {str(e)}")
            return []
    
    def close_connection(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
        if self.engine:
            self.engine.dispose()
        logger.info("Database connection closed")


def load_config(config_path: str) -> Optional[Dict[str, Any]]:
    """Load configuration from JSON file."""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        logger.error(f"Failed to load configuration: {str(e)}")
        return None


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Create PostgreSQL tables from MDL schemas')
    parser.add_argument('--config', required=True, help='Path to configuration JSON file')
    parser.add_argument('--drop-tables', action='store_true', help='Drop existing tables before creating new ones')
    parser.add_argument('--list-tables', action='store_true', help='List existing tables and exit')
    parser.add_argument('--table', help='Create only specific table name')
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    if not config:
        logger.error("Failed to load configuration")
        return 1
    
    # Validate required configuration
    required_keys = ['database', 'mdl_directory']
    for key in required_keys:
        if key not in config:
            logger.error(f"Missing required configuration key: {key}")
            return 1
    
    # Initialize table creator
    creator = TableCreator(config)
    
    try:
        # Connect to database
        if not creator.connect_to_database():
            return 1
        
        # List tables if requested
        if args.list_tables:
            creator.list_existing_tables()
            return 0
        
        # Create tables
        if args.table:
            # Create single table
            if args.table not in creator.table_mappings:
                logger.error(f"Table {args.table} not found in mappings")
                return 1
            
            if args.drop_tables:
                creator.drop_table_if_exists(args.table)
            
            schema = creator.load_mdl_schema(creator.table_mappings[args.table]['mdl_file'])
            if schema:
                success = creator.create_table_from_mdl(args.table, schema)
                if success:
                    logger.info(f"✓ Successfully created table: {args.table}")
                else:
                    logger.error(f"✗ Failed to create table: {args.table}")
                    return 1
            else:
                logger.error(f"Failed to load schema for {args.table}")
                return 1
        else:
            # Create all tables
            success = creator.create_all_tables(drop_existing=args.drop_tables)
            if success:
                logger.info("✓ All tables created successfully!")
            else:
                logger.error("✗ Some tables failed to create")
                return 1
        
        return 0
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return 1
    finally:
        creator.close_connection()


if __name__ == "__main__":
    sys.exit(main())

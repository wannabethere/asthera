#!/usr/bin/env python3
"""
CSV to PostgreSQL Data Loader

This script loads CSV files into PostgreSQL tables based on MDL JSON configurations.
It supports dropping existing tables and appending new data based on configuration flags.

Usage:
    python csv_to_postgres_loader.py --config config.json --drop-tables
    python csv_to_postgres_loader.py --config config.json --append-only
"""

import argparse
import json
import logging
import os
import sys
import time
import signal
from pathlib import Path
from typing import Dict, List, Optional, Any
import pandas as pd
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
        logging.FileHandler('csv_loader.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class CSVToPostgresLoader:
    """Main class for loading CSV files into PostgreSQL based on MDL configurations."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the loader with configuration."""
        self.config = config
        self.engine = None
        self.connection = None
        self.table_mappings = self._build_table_mappings()
        self.batch_size = config.get('batch_size', 1000)  # Default batch size
        
    def _build_table_mappings(self) -> Dict[str, Dict[str, str]]:
        """Build mappings between table names and their corresponding CSV files and MDL schemas."""
        mappings = {}
        
        # Define the mapping based on project metadata and file patterns
        table_mappings = {
            'dev_agents': {
                'csv_file': 'agents-part-00000-ceed7770-f667-47db-94af-686f33b3a68d-c000.snappy.csv',
                'mdl_file': 'mdl_agents.json',
                'table_name': 'dev_agents'
            },
            'dev_cve': {
                'csv_file': 'cve.csv',
                'mdl_file': 'mdl_cve.json', 
                'table_name': 'dev_cve'
            },
            'dev_assets': {
                'csv_file': 'assets-part-00000-72684b7e-2a4e-45ae-ba2f-d7a8e7480c9a-c000.snappy.csv',
                'mdl_file': 'mdl_assets.json',
                'table_name': 'dev_assets'
            },
            'dev_software_instances': {
                'csv_file': 'software_instances-part-00000-c7546cd4-cc72-420f-b58f-8ec6db39af97-c000.snappy.csv',
                'mdl_file': 'mdl_software_instances.json',
                'table_name': 'dev_software_instances'
            },
            'dev_vuln_instance': {
                'csv_file': 'vuln_instance-part-00000-1aff29e9-eef1-4821-a33b-4f43280c0fa9-c000.snappy.csv',
                'mdl_file': 'mdl_vuln_instance.json',
                'table_name': 'dev_vulnerability_instances'
            },
            'dev_network_devices': {
                'csv_file': 'interfaces-part-00000-f84005e0-391d-43d7-b91b-be4c973931d0-c000.snappy.csv',
                'mdl_file': 'mdl_interfaces.json',
                'table_name': 'dev_network_devices'
            }
        }
        
        return table_mappings
    
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
                    "application_name": "csv_loader"
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
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load MDL schema from {mdl_file_path}: {str(e)}")
            return {}
    
    def get_model_from_schema(self, schema: Dict[str, Any], table_name: str) -> Optional[Dict[str, Any]]:
        """Extract the specific model from the MDL schema."""
        if 'models' not in schema:
            return None
        
        for model in schema['models']:
            if model.get('name') == table_name:
                return model
        
        return None
    
    def create_table_from_mdl(self, table_name: str, mdl_schema: Dict[str, Any]) -> bool:
        """Create PostgreSQL table based on MDL schema with relationships."""
        try:
            logger.info(f"Starting table creation for {table_name}")
            logger.debug(f"MDL schema keys: {list(mdl_schema.keys()) if mdl_schema else 'None'}")
            
            if not mdl_schema or 'models' not in mdl_schema:
                logger.error(f"No valid models found in MDL schema for table {table_name}")
                return False
            
            # Find the model for this table
            model = None
            logger.debug(f"Searching for model with name: {table_name}")
            for i, m in enumerate(mdl_schema['models']):
                model_name = m.get('name')
                table_ref = m.get('tableReference', {}).get('table')
                logger.debug(f"Model {i}: name='{model_name}', tableReference='{table_ref}'")
                if model_name == table_name or table_ref == table_name:
                    model = m
                    logger.info(f"Found matching model: {model_name}")
                    break
            
            if not model:
                logger.error(f"Model not found for table {table_name} in MDL schema")
                logger.error(f"Available models: {[m.get('name') for m in mdl_schema['models']]}")
                return False
            
            # Get the CSV file to determine actual columns
            csv_file = self.table_mappings[table_name]['csv_file']
            csv_path = Path(self.config['data_directory']) / csv_file
            
            if not csv_path.exists():
                logger.error(f"CSV file not found: {csv_path}")
                return False
            
            # Read CSV header to get actual columns
            import pandas as pd
            try:
                df_sample = pd.read_csv(csv_path, nrows=1)
                actual_columns = list(df_sample.columns)
                logger.info(f"CSV has {len(actual_columns)} columns, MDL has {len(model.get('columns', []))} columns")
            except Exception as e:
                logger.error(f"Failed to read CSV header: {str(e)}")
                return False
            
            # Create a mapping of MDL columns for type information
            mdl_columns = {col['name']: col for col in model.get('columns', [])}
            logger.info(f"MDL columns: {mdl_columns}")
            # Build CREATE TABLE statement using MDL columns (which has all 97 columns)
            columns = []
            logger.info(f"Building CREATE TABLE statement with {len(model.get('columns', []))} columns from MDL")
            
            for i, col_def in enumerate(model.get('columns', [])):
                col_name = col_def['name']
                col_type = self._map_mdl_type_to_postgres(col_def['type'])
                not_null = col_def.get('notNull', False)
                
                column_def_sql = f'"{col_name}" {col_type}'
                if not_null:
                    column_def_sql += ' NOT NULL'
                
                columns.append(column_def_sql)
                
                # Log first few columns for debugging
                if i < 5:
                    logger.debug(f"Column {i+1}: {column_def_sql}")
            
            logger.info(f"Built {len(columns)} column definitions")
            
            # Add primary key if specified in MDL
            primary_key = model.get('primaryKey')
            if primary_key:
                if ',' in primary_key:
                    # Composite primary key
                    pk_columns = [f'"{col.strip()}"' for col in primary_key.split(',')]
                    columns.append(f'PRIMARY KEY ({", ".join(pk_columns)})')
                else:
                    columns.append(f'PRIMARY KEY ("{primary_key}")')
            
            # Add foreign key constraints based on relationships
            try:
                foreign_keys = self._get_foreign_key_constraints(table_name, mdl_schema)
                columns.extend(foreign_keys)
            except Exception as e:
                logger.warning(f"Failed to generate foreign key constraints for {table_name}: {str(e)}")
                logger.info(f"Creating table {table_name} without foreign key constraints")
            
            create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" (\n  ' + ',\n  '.join(columns) + '\n)'
            
            # Execute table creation
            logger.info(f"Executing CREATE TABLE SQL for {table_name}")
            logger.debug(f"SQL: {create_sql}")
            logger.info(f"Number of columns to create: {len(columns)}")
            
            try:
                logger.info(f"About to execute CREATE TABLE SQL for {table_name}")
                logger.debug(f"SQL length: {len(create_sql)} characters")
                result = self.connection.execute(text(create_sql))
                logger.info(f"✓ CREATE TABLE SQL executed successfully for {table_name}")
                logger.debug(f"SQL execution result: {result}")
                
                self.connection.commit()
                logger.info(f"✓ Transaction committed for {table_name}")
            except Exception as sql_error:
                logger.error(f"✗ SQL execution failed for {table_name}: {str(sql_error)}")
                logger.error(f"SQL that failed: {create_sql[:500]}...")
                raise sql_error
            
            # Create indexes on foreign key columns for better performance
            self._create_foreign_key_indexes(table_name, mdl_schema)
            
            # Verify table was created
            if self.table_exists(table_name):
                logger.info(f"✓ Successfully created table: {table_name}")
                
                # Log table structure for debugging
                try:
                    table_columns_query = f"""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = '{table_name}' 
                    ORDER BY ordinal_position
                    """
                    table_columns_result = self.connection.execute(text(table_columns_query))
                    table_columns = table_columns_result.fetchall()
                    logger.info(f"Table {table_name} has {len(table_columns)} columns")
                    if len(table_columns) > 0:
                        logger.debug(f"First 5 columns: {[col[0] for col in table_columns[:5]]}")
                except Exception as e:
                    logger.warning(f"Could not query table structure: {str(e)}")
                
                return True
            else:
                logger.error(f"✗ Table {table_name} was not created successfully")
                return False
            
        except Exception as e:
            logger.error(f"Failed to create table {table_name}: {str(e)}")
            return False
    
    def _get_foreign_key_constraints(self, table_name: str, mdl_schema: Dict[str, Any]) -> List[str]:
        """Generate foreign key constraints based on MDL relationships."""
        foreign_keys = []
        
        try:
            if 'relationships' not in mdl_schema:
                return foreign_keys

            for relationship in mdl_schema['relationships']:
                models = relationship.get('models', [])
                condition = relationship.get('condition', '')

                # Check if this table is involved in the relationship
                if table_name not in models:
                    continue

                # Skip conditions with OR as they're too complex for FK constraints
                if ' OR ' in condition:
                    logger.debug(f"Skipping complex OR condition for {table_name}: {condition}")
                    continue

                # Handle complex join conditions with AND
                if ' AND ' in condition:
                    # Parse multiple conditions (only if no OR conditions)
                    conditions = [c.strip() for c in condition.split(' AND ')]
                    fk_pairs = []

                    for cond in conditions:
                        if '=' in cond and ' OR ' not in cond:
                            parts = cond.split('=')
                            if len(parts) == 2:
                                left_side = parts[0].strip()
                                right_side = parts[1].strip()

                                try:
                                    left_table, left_column = self._parse_table_column(left_side)
                                    right_table, right_column = self._parse_table_column(right_side)

                                    # Only create FK if this table is the referencing table (child)
                                    # and the referenced table (parent) exists or will be created
                                    if (left_table == table_name and right_table != table_name and
                                        self._is_parent_table(right_table)):
                                        fk_pairs.append((left_column, right_table, right_column))
                                except (ValueError, IndexError) as e:
                                    logger.warning(f"Failed to parse condition '{cond}': {str(e)}")
                                    continue

                    # Create composite foreign key if multiple columns
                    if len(fk_pairs) > 1:
                        fk_columns = [f'"{col}"' for col, _, _ in fk_pairs]
                        ref_columns = [f'"{ref_col}"' for _, _, ref_col in fk_pairs]
                        ref_table = fk_pairs[0][1]  # All should reference the same table

                        fk_constraint = f'FOREIGN KEY ({", ".join(fk_columns)}) REFERENCES "{ref_table}"({", ".join(ref_columns)})'
                        foreign_keys.append(fk_constraint)
                    elif len(fk_pairs) == 1:
                        col, ref_table, ref_col = fk_pairs[0]
                        fk_constraint = f'FOREIGN KEY ("{col}") REFERENCES "{ref_table}"("{ref_col}")'
                        foreign_keys.append(fk_constraint)

                else:
                    # Simple single condition
                    if '=' in condition and ' OR ' not in condition:
                        parts = condition.split('=')
                        if len(parts) == 2:
                            left_side = parts[0].strip()
                            right_side = parts[1].strip()

                            try:
                                left_table, left_column = self._parse_table_column(left_side)
                                right_table, right_column = self._parse_table_column(right_side)

                                # Only create FK if this table is the referencing table (child)
                                # and the referenced table (parent) exists or will be created
                                if (left_table == table_name and right_table != table_name and
                                    self._is_parent_table(right_table)):
                                    fk_constraint = f'FOREIGN KEY ("{left_column}") REFERENCES "{right_table}"("{right_column}")'
                                    foreign_keys.append(fk_constraint)
                            except (ValueError, IndexError) as e:
                                logger.warning(f"Failed to parse condition '{condition}': {str(e)}")
                                continue

        except Exception as e:
            logger.warning(f"Failed to parse foreign key constraints for {table_name}: {str(e)}")

        return foreign_keys
    
    def _is_parent_table(self, table_name: str) -> bool:
        """Check if a table is a parent table that should be created before others."""
        # Define parent tables that should be created first
        parent_tables = {
            'dev_assets',      # Base table for all assets
            'dev_cve'          # Independent CVE data
        }
        return table_name in parent_tables
    
    def _create_foreign_key_indexes(self, table_name: str, mdl_schema: Dict[str, Any]):
        """Create indexes on foreign key columns for better query performance."""
        try:
            if 'relationships' not in mdl_schema:
                return
            
            for relationship in mdl_schema['relationships']:
                models = relationship.get('models', [])
                condition = relationship.get('condition', '')
                
                if table_name not in models:
                    continue
                
                # Extract columns used in foreign key relationships
                fk_columns = []
                
                if ' AND ' in condition:
                    conditions = [c.strip() for c in condition.split(' AND ')]
                    for cond in conditions:
                        if '=' in cond:
                            parts = cond.split('=')
                            if len(parts) == 2:
                                left_side = parts[0].strip()
                                right_side = parts[1].strip()
                                
                                left_table, left_column = self._parse_table_column(left_side)
                                right_table, right_column = self._parse_table_column(right_side)
                                
                                if left_table == table_name and right_table != table_name:
                                    fk_columns.append(left_column)
                else:
                    if '=' in condition:
                        parts = condition.split('=')
                        if len(parts) == 2:
                            left_side = parts[0].strip()
                            right_side = parts[1].strip()
                            
                            left_table, left_column = self._parse_table_column(left_side)
                            right_table, right_column = self._parse_table_column(right_side)
                            
                            if left_table == table_name and right_table != table_name:
                                fk_columns.append(left_column)
                
                # Create indexes for foreign key columns
                for column in fk_columns:
                    index_name = f"idx_{table_name}_{column}"
                    index_sql = f'CREATE INDEX IF NOT EXISTS "{index_name}" ON "{table_name}" ("{column}")'
                    try:
                        self.connection.execute(text(index_sql))
                        logger.info(f"Created index: {index_name}")
                    except Exception as e:
                        logger.warning(f"Failed to create index {index_name}: {str(e)}")
            
        except Exception as e:
            logger.warning(f"Failed to create foreign key indexes for {table_name}: {str(e)}")
    
    def _validate_relationships(self, table_name: str):
        """Validate that foreign key relationships are properly maintained."""
        try:
            # Get the MDL schema for this table
            if table_name not in self.table_mappings:
                return
            
            mapping = self.table_mappings[table_name]
            mdl_file = mapping['mdl_file']
            mdl_path = Path(self.config['mdl_directory']) / mdl_file
            
            if not mdl_path.exists():
                return
            
            mdl_schema = self.load_mdl_schema(str(mdl_path))
            if not mdl_schema or 'relationships' not in mdl_schema:
                return
            
            # Check each relationship
            for relationship in mdl_schema['relationships']:
                models = relationship.get('models', [])
                condition = relationship.get('condition', '')
                
                if table_name not in models:
                    continue
                
                # Parse the relationship condition
                if ' AND ' in condition:
                    conditions = [c.strip() for c in condition.split(' AND ')]
                    fk_checks = []
                    
                    for cond in conditions:
                        if '=' in cond:
                            parts = cond.split('=')
                            if len(parts) == 2:
                                left_side = parts[0].strip()
                                right_side = parts[1].strip()
                                
                                left_table, left_column = self._parse_table_column(left_side)
                                right_table, right_column = self._parse_table_column(right_side)
                                
                                if left_table == table_name and right_table != table_name:
                                    fk_checks.append((left_column, right_table, right_column))
                    
                    # Validate composite foreign key
                    if len(fk_checks) > 1:
                        self._validate_composite_fk(table_name, fk_checks)
                    elif len(fk_checks) == 1:
                        col, ref_table, ref_col = fk_checks[0]
                        self._validate_single_fk(table_name, col, ref_table, ref_col)
                
                else:
                    # Simple single foreign key
                    if '=' in condition:
                        parts = condition.split('=')
                        if len(parts) == 2:
                            left_side = parts[0].strip()
                            right_side = parts[1].strip()
                            
                            left_table, left_column = self._parse_table_column(left_side)
                            right_table, right_column = self._parse_table_column(right_side)
                            
                            if left_table == table_name and right_table != table_name:
                                self._validate_single_fk(table_name, left_column, right_table, right_column)
        
        except Exception as e:
            logger.warning(f"Failed to validate relationships for {table_name}: {str(e)}")
    
    def _validate_single_fk(self, table_name: str, fk_column: str, ref_table: str, ref_column: str):
        """Validate a single foreign key relationship."""
        try:
            # Check if reference table exists
            if not self.table_exists(ref_table):
                logger.warning(f"Reference table {ref_table} does not exist for FK validation")
                return
            
            # Check for orphaned records
            query = f"""
            SELECT COUNT(*) as orphaned_count
            FROM "{table_name}" t1
            LEFT JOIN "{ref_table}" t2 ON t1."{fk_column}" = t2."{ref_column}"
            WHERE t2."{ref_column}" IS NULL AND t1."{fk_column}" IS NOT NULL
            """
            
            result = self.connection.execute(text(query)).fetchone()
            orphaned_count = result[0] if result else 0
            
            if orphaned_count > 0:
                logger.warning(f"Found {orphaned_count} orphaned records in {table_name}.{fk_column} referencing {ref_table}.{ref_column}")
            else:
                logger.info(f"✓ Foreign key relationship {table_name}.{fk_column} -> {ref_table}.{ref_column} is valid")
        
        except Exception as e:
            logger.warning(f"Failed to validate FK {table_name}.{fk_column} -> {ref_table}.{ref_column}: {str(e)}")
    
    def _validate_composite_fk(self, table_name: str, fk_checks: List[tuple]):
        """Validate a composite foreign key relationship."""
        try:
            ref_table = fk_checks[0][1]  # All should reference the same table
            
            if not self.table_exists(ref_table):
                logger.warning(f"Reference table {ref_table} does not exist for composite FK validation")
                return
            
            # Build the JOIN condition
            join_conditions = []
            for fk_column, _, ref_column in fk_checks:
                join_conditions.append(f't1."{fk_column}" = t2."{ref_column}"')
            
            join_clause = ' AND '.join(join_conditions)
            
            # Check for orphaned records
            query = f"""
            SELECT COUNT(*) as orphaned_count
            FROM "{table_name}" t1
            LEFT JOIN "{ref_table}" t2 ON {join_clause}
            WHERE t2."{fk_checks[0][2]}" IS NULL
            """
            
            result = self.connection.execute(text(query)).fetchone()
            orphaned_count = result[0] if result else 0
            
            fk_columns = [col for col, _, _ in fk_checks]
            ref_columns = [ref_col for _, _, ref_col in fk_checks]
            
            if orphaned_count > 0:
                logger.warning(f"Found {orphaned_count} orphaned records in {table_name}({', '.join(fk_columns)}) referencing {ref_table}({', '.join(ref_columns)})")
            else:
                logger.info(f"✓ Composite foreign key relationship {table_name}({', '.join(fk_columns)}) -> {ref_table}({', '.join(ref_columns)}) is valid")
        
        except Exception as e:
            logger.warning(f"Failed to validate composite FK for {table_name}: {str(e)}")
    
    def _parse_table_column(self, table_column: str) -> tuple:
        """Parse table.column format and return (table, column)."""
        if '.' in table_column:
            parts = table_column.split('.', 1)
            if len(parts) != 2:
                logger.warning(f"Unexpected table.column format: '{table_column}' - got {len(parts)} parts")
                return '', table_column.strip()
            table, column = parts
            return table.strip(), column.strip()
        return '', table_column.strip()
    
    def _map_mdl_type_to_postgres(self, mdl_type: str) -> str:
        """Map MDL data types to PostgreSQL data types."""
        type_mapping = {
            'VARCHAR': 'VARCHAR(255)',
            'TEXT': 'TEXT',
            'INTEGER': 'INTEGER',
            'FLOAT': 'REAL',
            'DECIMAL': 'DECIMAL(10,2)',
            'BOOLEAN': 'BOOLEAN',
            'DATE': 'DATE',
            'TIMESTAMP': 'TIMESTAMP',
            'JSON': 'JSONB'
        }
        return type_mapping.get(mdl_type.upper(), 'TEXT')
    
    def _infer_column_type(self, pandas_series) -> str:
        """Infer PostgreSQL data type from pandas Series."""
        import pandas as pd
        import numpy as np
        
        # Handle missing values
        series = pandas_series.dropna()
        
        if len(series) == 0:
            return 'TEXT'
        
        # Check for boolean values
        if series.dtype == 'bool' or series.dtype == 'object':
            unique_vals = series.unique()
            if set(unique_vals).issubset({True, False, 'True', 'False', 'true', 'false', 'TRUE', 'FALSE', '1', '0', 'yes', 'no', 'Yes', 'No', 'YES', 'NO'}):
                return 'BOOLEAN'
        
        # Check for numeric types
        if pd.api.types.is_numeric_dtype(series):
            if pd.api.types.is_integer_dtype(series):
                return 'INTEGER'
            elif pd.api.types.is_float_dtype(series):
                return 'REAL'
        
        # Check for datetime types
        if pd.api.types.is_datetime64_any_dtype(series):
            return 'TIMESTAMP'
        
        # Check for date-like strings
        if series.dtype == 'object':
            try:
                pd.to_datetime(series, errors='raise')
                return 'TIMESTAMP'
            except:
                pass
        
        # Check string length to determine VARCHAR size
        if series.dtype == 'object':
            max_length = series.astype(str).str.len().max()
            if max_length <= 255:
                return 'VARCHAR(255)'
            elif max_length <= 1000:
                return 'VARCHAR(1000)'
            else:
                return 'TEXT'
        
        # Default to TEXT
        return 'TEXT'
    
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
    
    def load_csv_to_table(self, csv_file_path: str, table_name: str, append_mode: bool = False) -> bool:
        """Load CSV data into PostgreSQL table in batches with progress tracking."""
        try:
            # Read CSV file
            logger.info(f"Reading CSV file: {csv_file_path}")
            logger.info(f"File size: {os.path.getsize(csv_file_path) / (1024*1024):.2f} MB")
            
            # Try to read with different encodings and separators
            df = None
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    logger.info(f"Attempting to read with encoding: {encoding}")
                    df = pd.read_csv(csv_file_path, encoding=encoding, low_memory=False, nrows=5)  # Read first 5 rows to test
                    logger.info(f"Successfully read sample with encoding: {encoding}")
                    
                    # Now read the full file
                    logger.info(f"Reading full file with encoding: {encoding}")
                    if self.config.get('test_mode', False):
                        df = pd.read_csv(csv_file_path, encoding=encoding, low_memory=False, nrows=100)
                        logger.info(f"Test mode: loaded only first 100 rows")
                    else:
                        df = pd.read_csv(csv_file_path, encoding=encoding, low_memory=False)
                    logger.info(f"Successfully read full CSV with encoding: {encoding}")
                    break
                except UnicodeDecodeError as e:
                    logger.warning(f"Failed with encoding {encoding}: {str(e)}")
                    continue
                except Exception as e:
                    logger.warning(f"Error reading with encoding {encoding}: {str(e)}")
                    continue
            
            if df is None:
                logger.error(f"Failed to read CSV file with any encoding: {csv_file_path}")
                return False
            
            total_rows = len(df)
            logger.info(f"CSV file loaded: {total_rows} rows, {len(df.columns)} columns")
            logger.info(f"Columns: {list(df.columns)}")
            
            # Clean column names (remove special characters, handle spaces)
            df.columns = [col.strip().replace(' ', '_').replace('-', '_') for col in df.columns]
            
            # Get table columns from database to filter CSV columns
            table_columns_query = f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = '{table_name}' 
            ORDER BY ordinal_position
            """
            table_columns_result = self.connection.execute(text(table_columns_query))
            table_columns = [row[0] for row in table_columns_result.fetchall()]
            
            # Clean table column names to match CSV cleaning logic
            cleaned_table_columns = [col.strip().replace(' ', '_').replace('-', '_') for col in table_columns]
            
            # Debug logging for column comparison
            logger.info(f"=== COLUMN COMPARISON DEBUG ===")
            logger.info(f"CSV columns ({len(df.columns)}): {list(df.columns)}")
            logger.info(f"Raw table columns ({len(table_columns)}): {table_columns}")
            logger.info(f"Cleaned table columns ({len(cleaned_table_columns)}): {cleaned_table_columns}")
            
            # Find columns that exist in both CSV and table
            common_columns = [col for col in df.columns if col in cleaned_table_columns]
            csv_only_columns = [col for col in df.columns if col not in cleaned_table_columns]
            table_only_columns = [col for col in cleaned_table_columns if col not in df.columns]
            
            logger.info(f"Common columns: {len(common_columns)}")
            if csv_only_columns:
                logger.warning(f"CSV-only columns (will be ignored): {csv_only_columns}")
            if table_only_columns:
                logger.info(f"Table-only columns (computed/derived): {table_only_columns}")
            logger.info(f"=== END COLUMN COMPARISON DEBUG ===")
            
            # Filter DataFrame to only include common columns
            if common_columns:
                df = df[common_columns]
                logger.info(f"Filtered to {len(common_columns)} common columns: {common_columns}")
            else:
                logger.error("No common columns found between CSV and table!")
                return False
            
            # Handle missing values
            df = df.fillna('')
            
            # Convert boolean columns
            for col in df.columns:
                if df[col].dtype == 'object':
                    # Check if column contains boolean-like values
                    unique_vals = df[col].dropna().unique()
                    if set(unique_vals).issubset({'True', 'False', 'true', 'false', 'TRUE', 'FALSE', '', 'nan'}):
                        df[col] = df[col].map({'True': True, 'true': True, 'TRUE': True, 
                                             'False': False, 'false': False, 'FALSE': False, 
                                             '': None, 'nan': None})
            
            # If not append mode, truncate table first
            if not append_mode:
                truncate_sql = f'TRUNCATE TABLE "{table_name}"'
                self.connection.execute(text(truncate_sql))
                logger.info(f"Truncated table: {table_name}")
            
            # Load data in batches with progress tracking
            # Adjust batch size based on file size
            if total_rows > 100000:  # Large files
                batch_size = min(self.batch_size, 500)  # Smaller batches for large files
                logger.info(f"Large file detected ({total_rows} rows), using smaller batch size: {batch_size}")
            else:
                batch_size = self.batch_size
                
            total_batches = (total_rows + batch_size - 1) // batch_size
            
            logger.info(f"Loading data in {total_batches} batches of {batch_size} rows each...")
            logger.info(f"Starting data processing for table: {table_name}")
            
            rows_loaded = 0
            start_time = time.time()
            
            for batch_num in range(total_batches):
                batch_start_time = time.time()
                start_idx = batch_num * batch_size
                end_idx = min(start_idx + batch_size, total_rows)
                
                logger.info(f"Processing batch {batch_num + 1}/{total_batches}: rows {start_idx}-{end_idx-1}")
                
                # Get batch data
                batch_df = df.iloc[start_idx:end_idx]
                logger.info(f"Batch data extracted: {len(batch_df)} rows, {len(batch_df.columns)} columns")
                
                # Show progress every 10 batches or for small files
                if batch_num % 10 == 0 or total_batches < 20:
                    logger.info(f"Progress: {batch_num + 1}/{total_batches} batches ({((batch_num + 1) / total_batches * 100):.1f}%)")
                
                try:
                    logger.info(f"Inserting batch {batch_num + 1} into database...")
                    logger.info(f"Batch data preview: {batch_df.head(2).to_dict()}")
                    
                    # Load batch using pandas to_sql
                    batch_df.to_sql(
                        table_name, 
                        self.engine, 
                        if_exists='append',
                        index=False,
                        method='multi',
                        chunksize=1000
                    )
                    logger.info(f"✓ Batch {batch_num + 1} inserted successfully")
                    
                    rows_loaded += len(batch_df)
                    progress = (batch_num + 1) / total_batches * 100
                    
                    # Calculate timing information
                    batch_time = time.time() - batch_start_time
                    elapsed_time = time.time() - start_time
                    avg_time_per_batch = elapsed_time / (batch_num + 1)
                    remaining_batches = total_batches - (batch_num + 1)
                    estimated_remaining_time = remaining_batches * avg_time_per_batch
                    
                    # Calculate rows per second
                    rows_per_second = len(batch_df) / batch_time if batch_time > 0 else 0
                    
                    # Create progress bar
                    bar_length = 30
                    filled_length = int(bar_length * progress / 100)
                    bar = '█' * filled_length + '░' * (bar_length - filled_length)
                    
                    logger.info(f"Batch {batch_num + 1}/{total_batches} completed: {rows_loaded}/{total_rows} rows ({progress:.1f}%) - "
                              f"[{bar}] - Batch time: {batch_time:.2f}s, Rows/sec: {rows_per_second:.0f}, "
                              f"ETA: {estimated_remaining_time/60:.1f}min")
                    
                except Exception as e:
                    logger.error(f"Failed to load batch {batch_num + 1}: {str(e)}")
                    return False
            
            # Calculate final statistics
            total_time = time.time() - start_time
            avg_rows_per_second = rows_loaded / total_time if total_time > 0 else 0
            
            logger.info(f"✓ Successfully loaded {rows_loaded} rows into table: {table_name}")
            logger.info(f"  Total time: {total_time/60:.2f} minutes, Average speed: {avg_rows_per_second:.0f} rows/sec")
            
            # Validate relationships after loading data
            self._validate_relationships(table_name)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load CSV into table {table_name}: {str(e)}")
            return False
    
    def process_table(self, table_name: str, drop_table: bool = False, append_mode: bool = False) -> bool:
        """Process a single table (create, drop if needed, load data)."""
        
        if table_name not in self.table_mappings:
            logger.error(f"No mapping found for table: {table_name}")
            return False
        
        mapping = self.table_mappings[table_name]
        csv_file = mapping['csv_file']
        mdl_file = mapping['mdl_file']
        
        # Construct file paths
        csv_path = Path(self.config['data_directory']) / csv_file
        mdl_path = Path(self.config['mdl_directory']) / mdl_file
        
        if not csv_path.exists():
            logger.error(f"CSV file not found: {csv_path}")
            return False
        
        if not mdl_path.exists():
            logger.error(f"MDL file not found: {mdl_path}")
            return False
        
        # Load MDL schema
        mdl_schema = self.load_mdl_schema(str(mdl_path))
        if not mdl_schema:
            return False
        
        # Start a new transaction for this table
        try:
            # Drop table if requested
            if drop_table:
                if not self.drop_table_if_exists(table_name):
                    return False
            
            # Use the actual table name from mapping, not the mapping key
            actual_table_name = mapping.get('table_name', table_name)
            logger.info(f"Using actual table name: {actual_table_name}")
            
            # Create table if it doesn't exist
            if not self.table_exists(actual_table_name):
                logger.info(f"Creating table {actual_table_name} from MDL schema...")
                logger.info(f"MDL schema has {len(mdl_schema.get('models', [{}])[0].get('columns', []))} columns")
                
                logger.info(f"Calling create_table_from_mdl for {actual_table_name}")
                table_creation_result = self.create_table_from_mdl(actual_table_name, mdl_schema)
                logger.info(f"create_table_from_mdl returned: {table_creation_result}")
                
                if not table_creation_result:
                    logger.error(f"Failed to create table {actual_table_name}")
                    return False
                logger.info(f"Table {table_name} created successfully")
                
                # Verify table was created with correct structure
                if self.table_exists(actual_table_name):
                    table_columns_query = f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = '{actual_table_name}' 
                    ORDER BY ordinal_position
                    """
                    table_columns_result = self.connection.execute(text(table_columns_query))
                    table_columns = [row[0] for row in table_columns_result.fetchall()]
                    logger.info(f"✓ Verified table {actual_table_name} has {len(table_columns)} columns")
                    if len(table_columns) > 0:
                        logger.debug(f"First 5 columns: {table_columns[:5]}")
                else:
                    logger.error(f"✗ Table {actual_table_name} does not exist after creation attempt")
                    return False
            else:
                logger.info(f"Table {table_name} already exists")
            
            # Load CSV data
            actual_table_name = mapping.get('table_name', table_name)
            if not self.load_csv_to_table(str(csv_path), actual_table_name, append_mode):
                return False
            
            # Commit the transaction
            self.connection.commit()
            logger.info(f"Successfully processed table: {table_name}")
            return True
            
        except Exception as e:
            # Rollback the transaction on error
            self.connection.rollback()
            logger.error(f"Failed to process table {table_name}: {str(e)}")
            return False
    
    def table_exists(self, table_name: str) -> bool:
        """Check if table exists in the database."""
        try:
            inspector = inspect(self.engine)
            return table_name in inspector.get_table_names()
        except Exception as e:
            logger.error(f"Failed to check if table {table_name} exists: {str(e)}")
            return False
    
    def process_all_tables(self, drop_tables: bool = False, append_mode: bool = False) -> bool:
        """Process all tables defined in the mappings in proper dependency order."""
        success_count = 0
        total_count = len(self.table_mappings)
        
        logger.info(f"Processing {total_count} tables...")
        logger.info(f"Drop tables: {drop_tables}, Append mode: {append_mode}")
        
        # Define table creation order based on dependencies
        # Parent tables must be created before child tables
        table_order = [
            'dev_assets',           # Base table for assets
            'dev_agents',           # References assets (nuid, dev_id)
            'dev_software_instances', # References assets (nuid, dev_id)
            'dev_cve',              # Independent CVE data
            'dev_network_devices',  # References assets (nuid, dev_id) - correct table name
            'dev_vuln_instance'     # References both software and CVE - using mapping key
        ]
        
        # Filter to only include tables that exist in mappings
        ordered_tables = [t for t in table_order if t in self.table_mappings]
        
        # Add any remaining tables not in the predefined order
        remaining_tables = [t for t in self.table_mappings.keys() if t not in ordered_tables]
        ordered_tables.extend(remaining_tables)
        
        logger.info(f"Table creation order: {ordered_tables}")
        
        for table_name in ordered_tables:
            logger.info(f"Processing table: {table_name}")
            if self.process_table(table_name, drop_tables, append_mode):
                success_count += 1
            else:
                logger.error(f"Failed to process table: {table_name}")
        
        logger.info(f"Processed {success_count}/{total_count} tables successfully")
        
        # Create foreign key constraints after all tables are created
        if success_count > 0:
            self._create_foreign_key_constraints_after_creation()
        
        return success_count == total_count
    
    def _create_foreign_key_constraints_after_creation(self):
        """Create foreign key constraints after all tables are created."""
        try:
            logger.info("Creating foreign key constraints after table creation...")
            
            # Define the foreign key constraints that need to be added
            fk_constraints = [
                # dev_agents -> dev_assets
                {
                    'table': 'dev_agents',
                    'constraint': 'fk_agents_assets',
                    'sql': 'ALTER TABLE "dev_agents" ADD CONSTRAINT "fk_agents_assets" FOREIGN KEY ("nuid") REFERENCES "dev_assets"("nuid")'
                },
                # dev_software_instances -> dev_assets
                {
                    'table': 'dev_software_instances',
                    'constraint': 'fk_software_assets',
                    'sql': 'ALTER TABLE "dev_software_instances" ADD CONSTRAINT "fk_software_assets" FOREIGN KEY ("nuid") REFERENCES "dev_assets"("nuid")'
                },
                # dev_network_devices -> dev_assets (note: using correct table name)
                {
                    'table': 'dev_network_devices',
                    'constraint': 'fk_interfaces_assets',
                    'sql': 'ALTER TABLE "dev_network_devices" ADD CONSTRAINT "fk_interfaces_assets" FOREIGN KEY ("nuid") REFERENCES "dev_assets"("nuid")'
                },
                # dev_vulnerability_instances -> dev_cve (note: using correct table name)
                {
                    'table': 'dev_vulnerability_instances',
                    'constraint': 'fk_vuln_cve',
                    'sql': 'ALTER TABLE "dev_vulnerability_instances" ADD CONSTRAINT "fk_vuln_cve" FOREIGN KEY ("cve_id") REFERENCES "dev_cve"("cve_id")'
                },
                # dev_vulnerability_instances -> dev_assets
                {
                    'table': 'dev_vulnerability_instances',
                    'constraint': 'fk_vuln_assets',
                    'sql': 'ALTER TABLE "dev_vulnerability_instances" ADD CONSTRAINT "fk_vuln_assets" FOREIGN KEY ("nuid") REFERENCES "dev_assets"("nuid")'
                },
                # dev_vulnerability_instances -> dev_software_instances (note: using correct table name)
                {
                    'table': 'dev_vulnerability_instances',
                    'constraint': 'fk_vuln_software',
                    'sql': 'ALTER TABLE "dev_vulnerability_instances" ADD CONSTRAINT "fk_vuln_software" FOREIGN KEY ("sw_instance_id") REFERENCES "dev_software_instances"("key")'
                }
            ]
            
            for fk in fk_constraints:
                try:
                    # Check if table exists before adding constraint
                    if self.table_exists(fk['table']):
                        self.connection.execute(text(fk['sql']))
                        logger.info(f"Created foreign key constraint: {fk['constraint']}")
                    else:
                        logger.warning(f"Table {fk['table']} does not exist, skipping constraint {fk['constraint']}")
                except Exception as e:
                    logger.warning(f"Failed to create constraint {fk['constraint']}: {str(e)}")
            
            self.connection.commit()
            logger.info("Foreign key constraints creation completed")
            
        except Exception as e:
            logger.error(f"Failed to create foreign key constraints: {str(e)}")
            self.connection.rollback()
    
    def close_connection(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
        if self.engine:
            self.engine.dispose()
        logger.info("Database connection closed")


def load_config(config_file: str) -> Dict[str, Any]:
    """Load configuration from JSON file."""
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config file {config_file}: {str(e)}")
        return {}


def create_sample_config(config_file: str):
    """Create a sample configuration file."""
    sample_config = {
        "database": {
            "host": "localhost",
            "port": 5432,
            "database": "cve_data",
            "user": "postgres",
            "password": "password"
        },
        "data_directory": "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/cvedata/data",
        "mdl_directory": "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/sql_meta/cve_data"
    }
    
    with open(config_file, 'w') as f:
        json.dump(sample_config, f, indent=2)
    
    logger.info(f"Sample configuration created: {config_file}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Load CSV files into PostgreSQL based on MDL configurations')
    parser.add_argument('--config', required=True, help='Path to configuration JSON file')
    parser.add_argument('--drop-tables', action='store_true', help='Drop existing tables before loading')
    parser.add_argument('--append-only', action='store_true', help='Append data to existing tables (don\'t truncate)')
    parser.add_argument('--table', help='Process only specific table name')
    parser.add_argument('--batch-size', type=int, help='Override batch size for data loading (default: 1000)')
    parser.add_argument('--test-mode', action='store_true', help='Test mode: load only first 100 rows of each table')
    parser.add_argument('--create-config', help='Create sample configuration file and exit')
    
    args = parser.parse_args()
    
    if args.create_config:
        create_sample_config(args.create_config)
        return
    
    # Load configuration
    config = load_config(args.config)
    if not config:
        logger.error("Failed to load configuration")
        return 1
    
    # Override batch size if provided
    if args.batch_size:
        config['batch_size'] = args.batch_size
        logger.info(f"Using batch size: {args.batch_size}")
    
    # Set test mode if provided
    if args.test_mode:
        config['test_mode'] = True
        logger.info("Test mode enabled: will load only first 100 rows of each table")
    
    # Validate required configuration
    required_keys = ['database', 'data_directory', 'mdl_directory']
    for key in required_keys:
        if key not in config:
            logger.error(f"Missing required configuration key: {key}")
            return 1
    
    # Initialize loader
    loader = CSVToPostgresLoader(config)
    
    try:
        # Connect to database
        if not loader.connect_to_database():
            return 1
        
        # Process tables
        if args.table:
            # Process single table
            success = loader.process_table(
                args.table, 
                drop_tables=args.drop_tables,
                append_mode=args.append_only
            )
        else:
            # Process all tables
            success = loader.process_all_tables(
                drop_tables=args.drop_tables,
                append_mode=args.append_only
            )
        
        if success:
            logger.info("All operations completed successfully")
            return 0
        else:
            logger.error("Some operations failed")
            return 1
            
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return 1
    finally:
        loader.close_connection()


if __name__ == "__main__":
    sys.exit(main())

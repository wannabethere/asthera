#!/usr/bin/env python3
"""
CSV to PostgreSQL Importer

This script reads CSV files from the cvedata/data directory and imports them into PostgreSQL
tables using table names defined in corresponding JSON metadata files from sql_meta/cve_data.

Usage:
    python csv_to_postgres_importer.py [--config config.json] [--dry-run]

Features:
- Automatic CSV to table mapping using JSON metadata
- Data type inference and conversion
- Batch processing for large files
- Error handling and logging
- Dry-run mode for testing
"""

import os
import json
import logging
import argparse
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from sqlalchemy import create_engine, text
from typing import Dict, List, Optional, Tuple
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('csv_import.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class CSVToPostgresImporter:
    """Main class for importing CSV files to PostgreSQL using metadata mapping."""
    
    def __init__(self, config: Dict):
        """Initialize the importer with configuration."""
        self.config = config
        self.csv_dir = config.get('csv_directory', 'data/cvedata/data')
        self.metadata_dir = config.get('metadata_directory', 'data/sql_meta/cve_data')
        self.dry_run = config.get('dry_run', False)
        
        # Database connection
        self.db_config = config.get('database', {})
        self.engine = None
        self.connection = None
        
        # File mappings
        self.csv_metadata_mapping = self._build_csv_metadata_mapping()
        
    def _build_csv_metadata_mapping(self) -> Dict[str, str]:
        """Build mapping between CSV files and their corresponding metadata files."""
        mapping = {}
        
        # Define the mapping based on file naming patterns
        csv_files = [f for f in os.listdir(self.csv_dir) if f.endswith('.csv')]
        metadata_files = [f for f in os.listdir(self.metadata_dir) if f.endswith('.json')]
        
        # Create mapping based on filename patterns
        for csv_file in csv_files:
            csv_name = csv_file.replace('.csv', '').replace('.snappy', '')
            
            # Try to find matching metadata file
            for metadata_file in metadata_files:
                metadata_name = metadata_file.replace('.json', '')
                
                # Check for direct match or pattern match
                if (csv_name == metadata_name or 
                    csv_name.startswith(metadata_name.replace('mdl_', '')) or
                    metadata_name.startswith('mdl_') and csv_name in metadata_name):
                    mapping[csv_file] = metadata_file
                    break
            
            # If no mapping found, use filename as table name (no metadata)
            if csv_file not in mapping:
                # Extract clean table name from filename
                table_name = csv_file.replace('.csv', '').replace('.snappy', '')
                # Remove partition info if present
                if '-part-' in table_name:
                    table_name = table_name.split('-part-')[0]
                mapping[csv_file] = None  # No metadata file
                logger.info(f"No metadata found for {csv_file}, will use table name: {table_name}")
        
        logger.info(f"Built mapping for {len(mapping)} CSV files")
        return mapping
    
    def _connect_database(self):
        """Establish database connection."""
        if self.dry_run:
            logger.info("DRY RUN: Skipping database connection")
            return
            
        try:
            # Create SQLAlchemy engine
            db_url = (
                f"postgresql://{self.db_config['user']}:{self.db_config['password']}"
                f"@{self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}"
            )
            self.engine = create_engine(db_url)
            self.connection = self.engine.connect()
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def _disconnect_database(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
        if self.engine:
            self.engine.dispose()
        logger.info("Database connection closed")
    
    def _load_metadata(self, metadata_file: str) -> Dict:
        """Load JSON metadata file."""
        metadata_path = os.path.join(self.metadata_dir, metadata_file)
        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            logger.info(f"Loaded metadata from {metadata_file}")
            return metadata
        except Exception as e:
            logger.error(f"Failed to load metadata from {metadata_file}: {e}")
            raise
    
    def _get_table_name(self, metadata: Dict) -> str:
        """Extract table name from metadata."""
        try:
            # Get table name from the first model's tableReference
            models = metadata.get('models', [])
            if models and len(models) > 0:
                table_ref = models[0].get('tableReference', {})
                table_name = table_ref.get('table', '')
                if table_name:
                    return table_name
            
            # Fallback: use model name
            if models and len(models) > 0:
                model_name = models[0].get('name', '')
                if model_name:
                    return model_name.replace('_', '')
            
            raise ValueError("No table name found in metadata")
        except Exception as e:
            logger.error(f"Failed to extract table name from metadata: {e}")
            raise
    
    def _get_column_mapping(self, metadata: Dict) -> Dict[str, str]:
        """Extract column mapping from metadata."""
        column_mapping = {}
        try:
            models = metadata.get('models', [])
            if models and len(models) > 0:
                columns = models[0].get('columns', [])
                for col in columns:
                    col_name = col.get('name', '')
                    col_type = col.get('type', '')
                    if col_name and col_type:
                        column_mapping[col_name] = col_type
        except Exception as e:
            logger.warning(f"Failed to extract column mapping: {e}")
        
        return column_mapping
    
    def _infer_data_types(self, df: pd.DataFrame, column_mapping: Dict[str, str]) -> Dict[str, str]:
        """Infer and convert data types for DataFrame columns."""
        dtype_mapping = {}
        
        for col in df.columns:
            # Use metadata type if available
            if col in column_mapping:
                metadata_type = column_mapping[col].upper()
                if 'VARCHAR' in metadata_type or 'TEXT' in metadata_type:
                    dtype_mapping[col] = 'object'
                elif 'INTEGER' in metadata_type:
                    dtype_mapping[col] = 'Int64'  # Nullable integer
                elif 'DECIMAL' in metadata_type or 'FLOAT' in metadata_type:
                    dtype_mapping[col] = 'float64'
                elif 'BOOLEAN' in metadata_type:
                    dtype_mapping[col] = 'boolean'
                elif 'TIMESTAMP' in metadata_type or 'DATE' in metadata_type:
                    dtype_mapping[col] = 'datetime64[ns]'
                else:
                    dtype_mapping[col] = 'object'
            else:
                # Infer from data
                if df[col].dtype == 'object':
                    # Try to convert to numeric
                    try:
                        pd.to_numeric(df[col], errors='raise')
                        dtype_mapping[col] = 'float64'
                    except:
                        # Try to convert to datetime with format inference
                        try:
                            # Sample a few values to check if they look like dates
                            sample_values = df[col].dropna().head(5)
                            if len(sample_values) > 0:
                                # Try common datetime formats first
                                for fmt in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S%z']:
                                    try:
                                        pd.to_datetime(sample_values, format=fmt, errors='raise')
                                        dtype_mapping[col] = 'datetime64[ns]'
                                        break
                                    except:
                                        continue
                                else:
                                    # If no format works, try general parsing with warnings suppressed
                                    import warnings
                                    with warnings.catch_warnings():
                                        warnings.simplefilter("ignore")
                                        pd.to_datetime(df[col], errors='raise')
                                        dtype_mapping[col] = 'datetime64[ns]'
                            else:
                                dtype_mapping[col] = 'object'
                        except:
                            dtype_mapping[col] = 'object'
                else:
                    dtype_mapping[col] = str(df[col].dtype)
        
        return dtype_mapping
    
    def _clean_dataframe(self, df: pd.DataFrame, metadata: Dict = None) -> pd.DataFrame:
        """Clean and prepare DataFrame for database insertion."""
        # Remove completely empty rows
        df = df.dropna(how='all')
        
        # Replace empty strings with None
        df = df.replace('', None)
        
        # Handle NOT NULL constraints from metadata
        if metadata:
            models = metadata.get('models', [])
            if models and len(models) > 0:
                columns = models[0].get('columns', [])
                for col_info in columns:
                    col_name = col_info.get('name', '')
                    not_null = col_info.get('notNull', False)
                    
                    # Sanitize column name to match DataFrame columns
                    sanitized_col_name = self._sanitize_column_name(col_name)
                    
                    if not_null and sanitized_col_name in df.columns:
                        # Replace null values with a default value for NOT NULL columns
                        if df[sanitized_col_name].isnull().any():
                            if col_info.get('type', '').upper() in ['VARCHAR', 'TEXT']:
                                # For text columns, use 'Unknown' as default
                                df[sanitized_col_name] = df[sanitized_col_name].fillna('Unknown')
                            elif col_info.get('type', '').upper() == 'INTEGER':
                                # For integer columns, use 0 as default
                                df[sanitized_col_name] = df[sanitized_col_name].fillna(0)
                            elif col_info.get('type', '').upper() in ['DECIMAL', 'FLOAT']:
                                # For decimal columns, use 0.0 as default
                                df[sanitized_col_name] = df[sanitized_col_name].fillna(0.0)
                            elif col_info.get('type', '').upper() == 'BOOLEAN':
                                # For boolean columns, use False as default
                                df[sanitized_col_name] = df[sanitized_col_name].fillna(False)
                            else:
                                # For other types, use 'Unknown' as default
                                df[sanitized_col_name] = df[sanitized_col_name].fillna('Unknown')
        
        # Handle boolean columns
        for col in df.columns:
            if df[col].dtype == 'object':
                # Convert string booleans
                df[col] = df[col].replace({'True': True, 'False': False, 'true': True, 'false': False})
        
        return df
    
    def _process_dataframe_chunk(self, df: pd.DataFrame, table_name: str, column_mapping: Dict[str, str], metadata: Dict):
        """Process a single DataFrame chunk for large files."""
        try:
            # Sanitize column names in DataFrame
            original_columns = df.columns.tolist()
            sanitized_columns = [self._get_safe_column_name(col) for col in original_columns]
            df.columns = sanitized_columns
            
            # Clean and prepare data
            df = self._clean_dataframe(df, metadata)
            
            # Infer data types
            dtype_mapping = self._infer_data_types(df, column_mapping)
            
            # Convert data types
            for col, dtype in dtype_mapping.items():
                if col in df.columns:
                    try:
                        if dtype == 'datetime64[ns]':
                            # Handle timezone-aware datetime conversion
                            if df[col].dtype == 'object':
                                # Try to parse as timezone-aware first, then convert to naive
                                try:
                                    # Parse as timezone-aware and convert to naive
                                    df[col] = pd.to_datetime(df[col], utc=True).dt.tz_localize(None)
                                except:
                                    # If that fails, try timezone-naive parsing
                                    try:
                                        df[col] = pd.to_datetime(df[col], utc=False)
                                    except:
                                        # If both fail, try mixed format parsing
                                        try:
                                            df[col] = pd.to_datetime(df[col], format='mixed', errors='coerce')
                                        except:
                                            # Keep as object if all datetime parsing fails
                                            logger.warning(f"Could not parse datetime column {col}, keeping as object")
                                            continue
                            else:
                                # If already a datetime type, handle timezone conversion
                                if hasattr(df[col].dtype, 'tz') and df[col].dtype.tz is not None:
                                    # Convert timezone-aware to naive
                                    df[col] = df[col].dt.tz_localize(None)
                                else:
                                    df[col] = df[col].astype(dtype)
                        else:
                            df[col] = df[col].astype(dtype)
                    except Exception as e:
                        logger.warning(f"Failed to convert column {col} to {dtype}: {e}")
                        # Keep as object type if conversion fails
                        df[col] = df[col].astype('object')
            
            # Insert data
            self._insert_data(table_name, df)
            
        except Exception as e:
            logger.error(f"Failed to process chunk: {e}")
            raise
    
    def _sanitize_column_name(self, col_name: str) -> str:
        """Sanitize column name for PostgreSQL compatibility."""
        # Remove or replace invalid characters
        sanitized = col_name.replace(':', '_').replace(' ', '_').replace('-', '_')
        sanitized = sanitized.replace('(', '').replace(')', '').replace('[', '').replace(']', '')
        sanitized = sanitized.replace('{', '').replace('}', '').replace(';', '').replace(',', '')
        
        # Remove leading/trailing underscores and ensure it starts with letter or underscore
        sanitized = sanitized.strip('_')
        if sanitized and not sanitized[0].isalpha() and sanitized[0] != '_':
            sanitized = f'col_{sanitized}'
        
        # Handle empty or very short names
        if not sanitized or len(sanitized) < 2:
            sanitized = f'column_{hash(col_name) % 10000}'
        
        return sanitized

    def _quote_column_name(self, col_name: str) -> str:
        """Quote column name if it's a PostgreSQL reserved keyword."""
        reserved_keywords = {
            'references', 'order', 'group', 'select', 'from', 'where', 'having',
            'insert', 'update', 'delete', 'create', 'drop', 'alter', 'table',
            'index', 'view', 'database', 'schema', 'user', 'role', 'grant',
            'revoke', 'commit', 'rollback', 'begin', 'end', 'transaction',
            'constraint', 'primary', 'foreign', 'key', 'unique', 'check',
            'default', 'null', 'not', 'and', 'or', 'in', 'exists', 'between',
            'like', 'ilike', 'similar', 'to', 'escape', 'is', 'case', 'when',
            'then', 'else', 'cast', 'extract', 'current_date', 'current_time',
            'current_timestamp', 'localtime', 'localtimestamp', 'now', 'interval',
            'true', 'false', 'unknown', 'all', 'any', 'some', 'distinct',
            'union', 'intersect', 'except', 'limit', 'offset', 'asc', 'desc'
        }
        
        # First sanitize the column name
        sanitized_name = self._sanitize_column_name(col_name)
        
        if sanitized_name.lower() in reserved_keywords:
            return f'"{sanitized_name}"'
        return sanitized_name
    
    def _get_safe_column_name(self, col_name: str) -> str:
        """Get a safe column name for use in DataFrame (without quotes)."""
        # Just sanitize, don't quote - let pandas handle the quoting during SQL generation
        return self._sanitize_column_name(col_name)
    
    def _create_table_if_not_exists(self, table_name: str, df: pd.DataFrame, metadata: Dict):
        """Create table if it doesn't exist."""
        if self.dry_run:
            logger.info(f"DRY RUN: Would create table {table_name}")
            return
        
        try:
            if metadata:
                # Get column definitions from metadata
                models = metadata.get('models', [])
                if models and len(models) > 0:
                    columns = models[0].get('columns', [])
                    
                    # Build CREATE TABLE statement
                    create_sql = f"CREATE TABLE IF NOT EXISTS {table_name} (\n"
                    column_definitions = []
                    
                    # Use DataFrame columns directly (they are already sanitized)
                    # Map metadata column types to DataFrame columns
                    metadata_col_types = {col.get('name', ''): col.get('type', 'VARCHAR') for col in columns}
                    metadata_not_null = {col.get('name', ''): col.get('notNull', False) for col in columns}
                    
                    for col in df.columns:
                        # Use the same column name as in DataFrame (already sanitized)
                        # For reserved keywords, we'll let PostgreSQL handle it with quotes in the SQL
                        col_name = col
                        
                        # Try to find matching metadata column (original name)
                        col_type = 'VARCHAR'  # default
                        not_null = False
                        
                        for orig_name, orig_type in metadata_col_types.items():
                            if self._sanitize_column_name(orig_name) == col:
                                col_type = orig_type
                                not_null = metadata_not_null.get(orig_name, False)
                                break
                        
                        # Map pandas types to PostgreSQL types
                        if col_type.upper() in ['VARCHAR', 'TEXT']:
                            pg_type = 'TEXT'
                        elif col_type.upper() == 'INTEGER':
                            pg_type = 'INTEGER'
                        elif col_type.upper() in ['DECIMAL', 'FLOAT']:
                            pg_type = 'DECIMAL'
                        elif col_type.upper() == 'BOOLEAN':
                            pg_type = 'BOOLEAN'
                        elif col_type.upper() in ['TIMESTAMP', 'DATE']:
                            pg_type = 'TIMESTAMP'
                        else:
                            # Fallback to DataFrame dtype inference for columns not in metadata
                            if df[col].dtype == 'object':
                                pg_type = 'TEXT'
                            elif 'int' in str(df[col].dtype):
                                pg_type = 'INTEGER'
                            elif 'float' in str(df[col].dtype):
                                pg_type = 'DECIMAL'
                            elif 'bool' in str(df[col].dtype):
                                pg_type = 'BOOLEAN'
                            elif 'datetime' in str(df[col].dtype):
                                pg_type = 'TIMESTAMP'
                            else:
                                pg_type = 'TEXT'
                        
                        null_constraint = 'NOT NULL' if not_null else ''
                        column_definitions.append(f"    \"{col_name}\" {pg_type} {null_constraint}")
                    
                    # Ensure we have at least one column
                    if not column_definitions:
                        raise ValueError(f"No valid columns found for table {table_name}")
                    
                    create_sql += ',\n'.join(column_definitions)
                    create_sql += "\n);"
                    
                    # Log the CREATE TABLE statement for debugging
                    column_names = [col.split()[0].strip('"') for col in column_definitions]
                    logger.info(f"Creating table {table_name} with columns: {column_names}")
                    
                    # Execute CREATE TABLE with proper transaction handling
                    try:
                        self.connection.execute(text(create_sql))
                        self.connection.commit()
                        logger.info(f"Created table {table_name} with metadata")
                    except Exception as e:
                        self.connection.rollback()
                        raise e
            else:
                # Create table using DataFrame columns and inferred types
                create_sql = f"CREATE TABLE IF NOT EXISTS {table_name} (\n"
                column_definitions = []
                
                for col in df.columns:
                    # Use the same column name as in DataFrame (already sanitized)
                    # Quote all column names to handle reserved keywords
                    col_name = col
                    
                    # Infer PostgreSQL type from pandas dtype
                    if df[col].dtype == 'object':
                        pg_type = 'TEXT'
                    elif 'int' in str(df[col].dtype):
                        pg_type = 'INTEGER'
                    elif 'float' in str(df[col].dtype):
                        pg_type = 'DECIMAL'
                    elif 'bool' in str(df[col].dtype):
                        pg_type = 'BOOLEAN'
                    elif 'datetime' in str(df[col].dtype):
                        pg_type = 'TIMESTAMP'
                    else:
                        pg_type = 'TEXT'
                    
                    column_definitions.append(f"    \"{col_name}\" {pg_type}")
                
                # Ensure we have at least one column
                if not column_definitions:
                    raise ValueError(f"No valid columns found for table {table_name}")
                
                create_sql += ',\n'.join(column_definitions)
                create_sql += "\n);"
                
                # Execute CREATE TABLE with proper transaction handling
                try:
                    self.connection.execute(text(create_sql))
                    self.connection.commit()
                    logger.info(f"Created table {table_name} without metadata")
                except Exception as e:
                    self.connection.rollback()
                    raise e
                
        except Exception as e:
            logger.error(f"Failed to create table {table_name}: {e}")
            # Ensure transaction is rolled back
            try:
                self.connection.rollback()
            except:
                pass
            raise
    
    def _insert_data(self, table_name: str, df: pd.DataFrame):
        """Insert DataFrame data into PostgreSQL table."""
        if self.dry_run:
            logger.info(f"DRY RUN: Would insert {len(df)} rows into {table_name}")
            return
        
        try:
            # Create a copy of the DataFrame - column names should already match table schema
            df_copy = df.copy()
            
            # Log DataFrame columns for debugging
            logger.info(f"Inserting data into {table_name} with columns: {list(df_copy.columns)}")
            
            # Use pandas to_sql for efficient bulk insert with smaller chunks
            df_copy.to_sql(
                table_name,
                self.engine,
                if_exists='append',
                index=False,
                method='multi',
                chunksize=500  # Smaller chunks to avoid memory issues
            )
            logger.info(f"Inserted {len(df)} rows into {table_name}")
            
        except Exception as e:
            logger.error(f"Failed to insert data into {table_name}: {e}")
            logger.error(f"DataFrame columns: {list(df.columns)}")
            # Try to rollback any partial transaction
            try:
                self.connection.rollback()
            except:
                pass
            raise
    
    def import_csv_file(self, csv_file: str) -> bool:
        """Import a single CSV file to PostgreSQL."""
        try:
            logger.info(f"Processing CSV file: {csv_file}")
            
            # Get corresponding metadata file
            metadata_file = self.csv_metadata_mapping.get(csv_file)
            
            if metadata_file is None:
                # No metadata file, use filename as table name
                table_name = csv_file.replace('.csv', '').replace('.snappy', '')
                if '-part-' in table_name:
                    table_name = table_name.split('-part-')[0]
                logger.info(f"No metadata file found for {csv_file}, using table name: {table_name}")
                metadata = None
            else:
                # Load metadata
                metadata = self._load_metadata(metadata_file)
                # Get table name from metadata
                table_name = self._get_table_name(metadata)
            
            logger.info(f"Target table: {table_name}")
            
            # Read CSV file
            csv_path = os.path.join(self.csv_dir, csv_file)
            
            # Check file size and read in chunks if large
            file_size = os.path.getsize(csv_path)
            if file_size > 100 * 1024 * 1024:  # 100MB
                logger.info(f"Large file detected ({file_size / (1024*1024):.1f}MB), reading in chunks")
                df = pd.read_csv(csv_path, chunksize=10000)
                # Process first chunk to get schema
                df_chunk = next(df)
                logger.info(f"Read {len(df_chunk)} rows from first chunk of {csv_file}")
                
                # Process remaining chunks
                chunk_count = 1
                for chunk in df:
                    chunk_count += 1
                    logger.info(f"Processing chunk {chunk_count} with {len(chunk)} rows")
                    # Process this chunk
                    self._process_dataframe_chunk(chunk, table_name, column_mapping, metadata)
                
                # Use first chunk for table creation
                df = df_chunk
            else:
                df = pd.read_csv(csv_path)
                logger.info(f"Read {len(df)} rows from {csv_file}")
            
            # Get column mapping (empty if no metadata)
            column_mapping = self._get_column_mapping(metadata) if metadata else {}
            
            # Sanitize column names in DataFrame
            original_columns = df.columns.tolist()
            sanitized_columns = [self._get_safe_column_name(col) for col in original_columns]
            df.columns = sanitized_columns
            
            # Log column name changes
            for orig, new in zip(original_columns, sanitized_columns):
                if orig != new:
                    logger.info(f"Renamed column '{orig}' to '{new}'")
            
            # Update column mapping to use sanitized names
            if metadata:
                updated_column_mapping = {}
                for orig_col, col_type in column_mapping.items():
                    sanitized_col = self._sanitize_column_name(orig_col)
                    updated_column_mapping[sanitized_col] = col_type
                column_mapping = updated_column_mapping
            
            # Clean and prepare data
            df = self._clean_dataframe(df, metadata)
            
            # Infer data types
            dtype_mapping = self._infer_data_types(df, column_mapping)
            
            # Convert data types
            for col, dtype in dtype_mapping.items():
                if col in df.columns:
                    try:
                        if dtype == 'datetime64[ns]':
                            # Handle timezone-aware datetime conversion
                            if df[col].dtype == 'object':
                                # Try to parse as timezone-aware first, then convert to naive
                                try:
                                    # Parse as timezone-aware and convert to naive
                                    df[col] = pd.to_datetime(df[col], utc=True).dt.tz_localize(None)
                                except:
                                    # If that fails, try timezone-naive parsing
                                    try:
                                        df[col] = pd.to_datetime(df[col], utc=False)
                                    except:
                                        # If both fail, try mixed format parsing
                                        try:
                                            df[col] = pd.to_datetime(df[col], format='mixed', errors='coerce')
                                        except:
                                            # Keep as object if all datetime parsing fails
                                            logger.warning(f"Could not parse datetime column {col}, keeping as object")
                                            continue
                            else:
                                # If already a datetime type, handle timezone conversion
                                if hasattr(df[col].dtype, 'tz') and df[col].dtype.tz is not None:
                                    # Convert timezone-aware to naive
                                    df[col] = df[col].dt.tz_localize(None)
                                else:
                                    df[col] = df[col].astype(dtype)
                        else:
                            df[col] = df[col].astype(dtype)
                    except Exception as e:
                        logger.warning(f"Failed to convert column {col} to {dtype}: {e}")
                        # Keep as object type if conversion fails
                        df[col] = df[col].astype('object')
            
            # Create table if not exists
            self._create_table_if_not_exists(table_name, df, metadata)
            
            # Insert data
            self._insert_data(table_name, df)
            
            logger.info(f"Successfully imported {csv_file} to {table_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to import {csv_file}: {e}")
            return False
    
    def import_all_csv_files(self) -> Dict[str, bool]:
        """Import all CSV files."""
        results = {}
        
        # Connect to database
        self._connect_database()
        
        try:
            csv_files = [f for f in os.listdir(self.csv_dir) if f.endswith('.csv')]
            logger.info(f"Found {len(csv_files)} CSV files to process")
            
            for csv_file in csv_files:
                success = self.import_csv_file(csv_file)
                results[csv_file] = success
            
            # Summary
            successful = sum(1 for success in results.values() if success)
            total = len(results)
            logger.info(f"Import completed: {successful}/{total} files successful")
            
        finally:
            self._disconnect_database()
        
        return results

def load_config(config_file: str) -> Dict:
    """Load configuration from JSON file."""
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        logger.error(f"Failed to load config file {config_file}: {e}")
        raise

def create_default_config() -> Dict:
    """Create default configuration."""
    return {
        "csv_directory": "data/cvedata/data",
        "metadata_directory": "data/sql_meta/cve_data",
        "dry_run": False,
        "database": {
            "host": "localhost",
            "port": 5432,
            "database": "cve_data",
            "user": "postgres",
            "password": "password"
        }
    }

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Import CSV files to PostgreSQL using metadata mapping')
    parser.add_argument('--config', '-c', help='Configuration file path', default='config.json')
    parser.add_argument('--dry-run', action='store_true', help='Run in dry-run mode (no database operations)')
    parser.add_argument('--create-config', action='store_true', help='Create default configuration file')
    
    args = parser.parse_args()
    
    # Create default config if requested
    if args.create_config:
        config = create_default_config()
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=2)
        logger.info("Created default configuration file: config.json")
        return
    
    # Load configuration
    if os.path.exists(args.config):
        config = load_config(args.config)
    else:
        logger.warning(f"Config file {args.config} not found, using defaults")
        config = create_default_config()
    
    # Override dry_run if specified
    if args.dry_run:
        config['dry_run'] = True
    
    # Create and run importer
    importer = CSVToPostgresImporter(config)
    results = importer.import_all_csv_files()
    
    # Print summary
    print("\n" + "="*50)
    print("IMPORT SUMMARY")
    print("="*50)
    for csv_file, success in results.items():
        status = "✓ SUCCESS" if success else "✗ FAILED"
        print(f"{csv_file:<50} {status}")
    
    successful = sum(1 for success in results.values() if success)
    total = len(results)
    print(f"\nTotal: {successful}/{total} files imported successfully")

if __name__ == "__main__":
    main()

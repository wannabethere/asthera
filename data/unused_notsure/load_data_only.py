#!/usr/bin/env python3
"""
Script to load CSV data into existing PostgreSQL tables.
This uses a different approach than pandas - using COPY or direct INSERT statements.
"""

import argparse
import json
import logging
import os
import sys
import time
import csv
from pathlib import Path
from typing import Dict, List, Optional, Any
import psycopg2
from psycopg2.extras import RealDictCursor
import sqlalchemy
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError
import warnings

# Suppress warnings
warnings.filterwarnings('ignore', category=FutureWarning)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('load_data.log')
    ]
)

logger = logging.getLogger(__name__)


class DataLoader:
    """Class for loading CSV data into PostgreSQL tables."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the data loader with configuration."""
        self.config = config
        self.engine = None
        self.connection = None
        self.table_mappings = self._build_table_mappings()
        
    def _build_table_mappings(self) -> Dict[str, Dict[str, str]]:
        """Build mappings between table names and their corresponding CSV files."""
        mappings = {}
        
        data_directory = Path(self.config['data_directory'])
        
        # Define table mappings based on your CSV files
        table_configs = {
            'dev_agents': 'agents-part-00000-ceed7770-f667-47db-94af-686f33b3a68d-c000.snappy.csv',
            'dev_assets': 'assets-part-00000-72684b7e-2a4e-45ae-ba2f-d7a8e7480c9a-c000.snappy.csv',
            'dev_software_instances': 'software_instances-part-00000-c7546cd4-cc72-420f-b58f-8ec6db39af97-c000.snappy.csv',
            'dev_cve': 'cve.csv',
            'dev_interfaces': 'interfaces-part-00000-f84005e0-391d-43d7-b91b-be4c973931d0-c000.snappy.csv',
            'dev_vuln_instance': 'vuln_instance-part-00000-1aff29e9-eef1-4821-a33b-4f43280c0fa9-c000.snappy.csv'
        }
        
        for table_name, csv_file in table_configs.items():
            csv_path = data_directory / csv_file
            if csv_path.exists():
                mappings[table_name] = {
                    'csv_file': str(csv_path),
                    'table_name': table_name
                }
            else:
                logger.warning(f"CSV file not found: {csv_path}")
        
        return mappings
    
    def connect_to_database(self) -> bool:
        """Establish connection to PostgreSQL database."""
        try:
            db_config = self.config['database']
            connection_string = (
                f"postgresql://{db_config['user']}:{db_config['password']}@"
                f"{db_config['host']}:{db_config['port']}/{db_config['database']}"
            )
            
            self.engine = create_engine(
                connection_string, 
                echo=False,
                connect_args={
                    "connect_timeout": 30,
                    "application_name": "data_loader"
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
    
    def get_table_columns(self, table_name: str) -> List[str]:
        """Get column names for a table."""
        try:
            inspector = inspect(self.engine)
            columns = inspector.get_columns(table_name)
            return [col['name'] for col in columns]
        except Exception as e:
            logger.error(f"Failed to get columns for {table_name}: {str(e)}")
            return []
    
    def load_csv_with_copy(self, csv_file_path: str, table_name: str, batch_size: int = 1000) -> bool:
        """Load CSV data using PostgreSQL COPY command."""
        try:
            logger.info(f"Loading CSV with COPY: {csv_file_path}")
            logger.info(f"File size: {os.path.getsize(csv_file_path) / (1024*1024):.2f} MB")
            
            # Get table columns
            columns = self.get_table_columns(table_name)
            if not columns:
                logger.error(f"No columns found for table: {table_name}")
                return False
            
            # Read CSV file and process in batches
            with open(csv_file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                batch_data = []
                total_rows = 0
                batch_num = 0
                
                for row in reader:
                    # Clean and prepare row data
                    cleaned_row = {}
                    for col in columns:
                        value = row.get(col, '')
                        # Handle empty values
                        if value == '' or value is None:
                            cleaned_row[col] = None
                        else:
                            cleaned_row[col] = value
                    
                    batch_data.append(cleaned_row)
                    
                    # Process batch when it reaches batch_size
                    if len(batch_data) >= batch_size:
                        if self._insert_batch(table_name, columns, batch_data, batch_num):
                            total_rows += len(batch_data)
                            batch_num += 1
                            logger.info(f"Processed batch {batch_num}: {total_rows} rows total")
                        else:
                            logger.error(f"Failed to process batch {batch_num}")
                            return False
                        batch_data = []
                
                # Process remaining data
                if batch_data:
                    if self._insert_batch(table_name, columns, batch_data, batch_num):
                        total_rows += len(batch_data)
                        batch_num += 1
                        logger.info(f"Processed final batch {batch_num}: {total_rows} rows total")
                    else:
                        logger.error(f"Failed to process final batch {batch_num}")
                        return False
            
            logger.info(f"✓ Successfully loaded {total_rows} rows into {table_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load CSV with COPY: {str(e)}")
            return False
    
    def _insert_batch(self, table_name: str, columns: List[str], batch_data: List[Dict], batch_num: int) -> bool:
        """Insert a batch of data into the table."""
        try:
            if not batch_data:
                return True
            
            # Build INSERT statement
            placeholders = ', '.join(['%s'] * len(columns))
            column_names = ', '.join([f'"{col}"' for col in columns])
            insert_sql = f'INSERT INTO "{table_name}" ({column_names}) VALUES ({placeholders})'
            
            # Prepare data for insertion
            values_list = []
            for row in batch_data:
                values = [row.get(col) for col in columns]
                values_list.append(values)
            
            # Execute batch insert
            with self.connection.begin():
                self.connection.execute(text(insert_sql), values_list)
            
            logger.info(f"✓ Batch {batch_num + 1} inserted: {len(batch_data)} rows")
            return True
            
        except Exception as e:
            logger.error(f"Failed to insert batch {batch_num + 1}: {str(e)}")
            return False
    
    def load_csv_with_pandas(self, csv_file_path: str, table_name: str, batch_size: int = 1000) -> bool:
        """Load CSV data using pandas (fallback method)."""
        try:
            import pandas as pd
            
            logger.info(f"Loading CSV with pandas: {csv_file_path}")
            logger.info(f"File size: {os.path.getsize(csv_file_path) / (1024*1024):.2f} MB")
            
            # Read CSV in chunks
            chunk_size = batch_size
            total_rows = 0
            chunk_num = 0
            
            for chunk in pd.read_csv(csv_file_path, chunksize=chunk_size, low_memory=False):
                try:
                    # Clean column names
                    chunk.columns = [col.strip().replace(' ', '_').replace('-', '_') for col in chunk.columns]
                    
                    # Handle missing values
                    chunk = chunk.fillna('')
                    
                    # Load chunk to database
                    chunk.to_sql(
                        table_name,
                        self.engine,
                        if_exists='append',
                        index=False,
                        method='multi'
                    )
                    
                    total_rows += len(chunk)
                    chunk_num += 1
                    
                    logger.info(f"✓ Chunk {chunk_num} loaded: {len(chunk)} rows (Total: {total_rows})")
                    
                except Exception as e:
                    logger.error(f"Failed to load chunk {chunk_num}: {str(e)}")
                    return False
            
            logger.info(f"✓ Successfully loaded {total_rows} rows into {table_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load CSV with pandas: {str(e)}")
            return False
    
    def truncate_table(self, table_name: str) -> bool:
        """Truncate table to remove existing data."""
        try:
            truncate_sql = f'TRUNCATE TABLE "{table_name}"'
            self.connection.execute(text(truncate_sql))
            self.connection.commit()
            logger.info(f"Truncated table: {table_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to truncate table {table_name}: {str(e)}")
            return False
    
    def load_table_data(self, table_name: str, method: str = 'copy', batch_size: int = 1000, truncate: bool = False) -> bool:
        """Load data for a specific table."""
        try:
            if table_name not in self.table_mappings:
                logger.error(f"Table {table_name} not found in mappings")
                return False
            
            csv_file = self.table_mappings[table_name]['csv_file']
            
            logger.info(f"Loading data for table: {table_name}")
            logger.info(f"CSV file: {csv_file}")
            logger.info(f"Method: {method}, Batch size: {batch_size}")
            
            # Truncate table if requested
            if truncate:
                self.truncate_table(table_name)
            
            # Load data based on method
            if method == 'copy':
                success = self.load_csv_with_copy(csv_file, table_name, batch_size)
            elif method == 'pandas':
                success = self.load_csv_with_pandas(csv_file, table_name, batch_size)
            else:
                logger.error(f"Unknown method: {method}")
                return False
            
            if success:
                logger.info(f"✓ Successfully loaded data for {table_name}")
            else:
                logger.error(f"✗ Failed to load data for {table_name}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error loading data for {table_name}: {str(e)}")
            return False
    
    def load_all_data(self, method: str = 'copy', batch_size: int = 1000, truncate: bool = False) -> bool:
        """Load data for all tables."""
        try:
            # Define loading order (parent tables first)
            table_order = [
                'dev_assets',      # Parent table
                'dev_cve',         # Parent table  
                'dev_agents',      # References dev_assets
                'dev_software_instances',  # References dev_assets
                'dev_interfaces',  # References dev_assets
                'dev_vuln_instance'  # References dev_assets and dev_software_instances
            ]
            
            logger.info(f"Loading data for {len(table_order)} tables...")
            logger.info(f"Method: {method}, Batch size: {batch_size}, Truncate: {truncate}")
            
            success_count = 0
            
            for table_name in table_order:
                if table_name not in self.table_mappings:
                    logger.warning(f"Table {table_name} not found in mappings, skipping...")
                    continue
                
                logger.info(f"Processing table: {table_name}")
                
                if self.load_table_data(table_name, method, batch_size, truncate):
                    success_count += 1
                    logger.info(f"✓ Successfully processed table: {table_name}")
                else:
                    logger.error(f"✗ Failed to process table: {table_name}")
            
            logger.info(f"✓ Successfully loaded data for {success_count}/{len(table_order)} tables")
            return success_count == len(table_order)
            
        except Exception as e:
            logger.error(f"Failed to load data: {str(e)}")
            return False
    
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
    parser = argparse.ArgumentParser(description='Load CSV data into PostgreSQL tables')
    parser.add_argument('--config', required=True, help='Path to configuration JSON file')
    parser.add_argument('--method', choices=['copy', 'pandas'], default='copy', help='Loading method (copy or pandas)')
    parser.add_argument('--batch-size', type=int, default=1000, help='Batch size for loading data')
    parser.add_argument('--truncate', action='store_true', help='Truncate tables before loading data')
    parser.add_argument('--table', help='Load data for specific table only')
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    if not config:
        logger.error("Failed to load configuration")
        return 1
    
    # Validate required configuration
    required_keys = ['database', 'data_directory']
    for key in required_keys:
        if key not in config:
            logger.error(f"Missing required configuration key: {key}")
            return 1
    
    # Initialize data loader
    loader = DataLoader(config)
    
    try:
        # Connect to database
        if not loader.connect_to_database():
            return 1
        
        # Load data
        if args.table:
            # Load single table
            success = loader.load_table_data(args.table, args.method, args.batch_size, args.truncate)
            if success:
                logger.info(f"✓ Successfully loaded data for {args.table}")
            else:
                logger.error(f"✗ Failed to load data for {args.table}")
                return 1
        else:
            # Load all tables
            success = loader.load_all_data(args.method, args.batch_size, args.truncate)
            if success:
                logger.info("✓ All data loaded successfully!")
            else:
                logger.error("✗ Some data failed to load")
                return 1
        
        return 0
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return 1
    finally:
        loader.close_connection()


if __name__ == "__main__":
    sys.exit(main())

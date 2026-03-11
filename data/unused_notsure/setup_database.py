#!/usr/bin/env python3
"""
Complete database setup script that creates tables and loads data.
This is a wrapper that calls the separate table creation and data loading scripts.
"""

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('setup_database.log')
    ]
)

logger = logging.getLogger(__name__)


def run_command(command: list, description: str) -> bool:
    """Run a command and return success status."""
    try:
        logger.info(f"Running: {description}")
        logger.info(f"Command: {' '.join(command)}")
        
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        
        if result.stdout:
            logger.info(f"Output: {result.stdout}")
        
        logger.info(f"✓ {description} completed successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"✗ {description} failed with exit code {e.returncode}")
        if e.stdout:
            logger.error(f"STDOUT: {e.stdout}")
        if e.stderr:
            logger.error(f"STDERR: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"✗ {description} failed with error: {str(e)}")
        return False


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Complete database setup: create tables and load data')
    parser.add_argument('--config', required=True, help='Path to configuration JSON file')
    parser.add_argument('--drop-tables', action='store_true', help='Drop existing tables before creating new ones')
    parser.add_argument('--truncate-data', action='store_true', help='Truncate tables before loading data')
    parser.add_argument('--method', choices=['copy', 'pandas'], default='copy', help='Data loading method')
    parser.add_argument('--batch-size', type=int, default=1000, help='Batch size for data loading')
    parser.add_argument('--tables-only', action='store_true', help='Create tables only, skip data loading')
    parser.add_argument('--data-only', action='store_true', help='Load data only, skip table creation')
    parser.add_argument('--table', help='Process specific table only')
    
    args = parser.parse_args()
    
    # Check if config file exists
    if not Path(args.config).exists():
        logger.error(f"Configuration file not found: {args.config}")
        return 1
    
    logger.info("Database Setup Script")
    logger.info("=" * 50)
    logger.info(f"Config: {args.config}")
    logger.info(f"Drop tables: {args.drop_tables}")
    logger.info(f"Truncate data: {args.truncate_data}")
    logger.info(f"Method: {args.method}")
    logger.info(f"Batch size: {args.batch_size}")
    logger.info(f"Tables only: {args.tables_only}")
    logger.info(f"Data only: {args.data_only}")
    logger.info(f"Specific table: {args.table}")
    
    start_time = time.time()
    
    # Step 1: Create tables (unless data-only mode)
    if not args.data_only:
        logger.info("\n" + "="*50)
        logger.info("STEP 1: Creating Tables")
        logger.info("="*50)
        
        table_command = [
            'python', 'create_tables_only.py',
            '--config', args.config
        ]
        
        if args.drop_tables:
            table_command.append('--drop-tables')
        
        if args.table:
            table_command.extend(['--table', args.table])
        
        if not run_command(table_command, "Table creation"):
            logger.error("Table creation failed. Stopping.")
            return 1
        
        logger.info("✓ Tables created successfully")
    else:
        logger.info("Skipping table creation (data-only mode)")
    
    # Step 2: Load data (unless tables-only mode)
    if not args.tables_only:
        logger.info("\n" + "="*50)
        logger.info("STEP 2: Loading Data")
        logger.info("="*50)
        
        data_command = [
            'python', 'load_data_only.py',
            '--config', args.config,
            '--method', args.method,
            '--batch-size', str(args.batch_size)
        ]
        
        if args.truncate_data:
            data_command.append('--truncate')
        
        if args.table:
            data_command.extend(['--table', args.table])
        
        if not run_command(data_command, "Data loading"):
            logger.error("Data loading failed.")
            return 1
        
        logger.info("✓ Data loaded successfully")
    else:
        logger.info("Skipping data loading (tables-only mode)")
    
    # Summary
    total_time = time.time() - start_time
    logger.info("\n" + "="*50)
    logger.info("SETUP COMPLETE")
    logger.info("="*50)
    logger.info(f"Total time: {total_time/60:.2f} minutes")
    
    if not args.tables_only and not args.data_only:
        logger.info("✓ Database setup completed successfully!")
        logger.info("  - Tables created with proper relationships")
        logger.info("  - Data loaded with progress tracking")
    elif args.tables_only:
        logger.info("✓ Tables created successfully!")
    elif args.data_only:
        logger.info("✓ Data loaded successfully!")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

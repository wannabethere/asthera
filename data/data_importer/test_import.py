#!/usr/bin/env python3
"""
Test script for CSV to PostgreSQL importer

This script demonstrates how to use the CSVToPostgresImporter class
and provides a simple test of the import functionality.
"""

import json
import os
import sys
from csv_to_postgres_importer import CSVToPostgresImporter

def test_dry_run():
    """Test the importer in dry-run mode."""
    print("Testing CSV to PostgreSQL importer in dry-run mode...")
    
    # Create test configuration
    config = {
        "csv_directory": "data/cvedata/data",
        "metadata_directory": "data/sql_meta/cve_data",
        "dry_run": True,
        "database": {
            "host": "localhost",
            "port": 5432,
            "database": "test_db",
            "user": "test_user",
            "password": "test_password"
        }
    }
    
    # Create importer
    importer = CSVToPostgresImporter(config)
    
    # Test CSV metadata mapping
    print(f"Found {len(importer.csv_metadata_mapping)} CSV to metadata mappings:")
    for csv_file, metadata_file in importer.csv_metadata_mapping.items():
        print(f"  {csv_file} -> {metadata_file}")
    
    # Test importing a single file (dry run)
    csv_files = [f for f in os.listdir(importer.csv_dir) if f.endswith('.csv')]
    if csv_files:
        test_file = csv_files[0]
        print(f"\nTesting import of {test_file}...")
        success = importer.import_csv_file(test_file)
        print(f"Import result: {'SUCCESS' if success else 'FAILED'}")
    else:
        print("No CSV files found to test")
    
    print("\nDry-run test completed successfully!")

def test_metadata_loading():
    """Test metadata loading functionality."""
    print("\nTesting metadata loading...")
    
    config = {
        "csv_directory": "data/cvedata/data",
        "metadata_directory": "data/sql_meta/cve_data",
        "dry_run": True,
        "database": {}
    }
    
    importer = CSVToPostgresImporter(config)
    
    # Test loading metadata files
    metadata_files = [f for f in os.listdir(importer.metadata_dir) if f.endswith('.json')]
    print(f"Found {len(metadata_files)} metadata files:")
    
    for metadata_file in metadata_files[:3]:  # Test first 3 files
        try:
            metadata = importer._load_metadata(metadata_file)
            table_name = importer._get_table_name(metadata)
            column_mapping = importer._get_column_mapping(metadata)
            print(f"  {metadata_file}:")
            print(f"    Table: {table_name}")
            print(f"    Columns: {len(column_mapping)}")
        except Exception as e:
            print(f"  {metadata_file}: ERROR - {e}")

def main():
    """Main test function."""
    print("CSV to PostgreSQL Importer Test")
    print("=" * 40)
    
    # Check if required directories exist
    if not os.path.exists("data/cvedata/data"):
        print("ERROR: data/cvedata/data directory not found")
        return
    
    if not os.path.exists("data/sql_meta/cve_data"):
        print("ERROR: data/sql_meta/cve_data directory not found")
        return
    
    # Run tests
    test_dry_run()
    test_metadata_loading()
    
    print("\nAll tests completed!")

if __name__ == "__main__":
    main()

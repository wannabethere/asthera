#!/usr/bin/env python3
"""
Example usage of the CSV to PostgreSQL loader

This script demonstrates how to use the CSV loader programmatically
for different scenarios.
"""

import json
from csv_to_postgres_loader import CSVToPostgresLoader


def example_basic_usage():
    """Example of basic usage - load all tables."""
    print("Example 1: Basic Usage - Load All Tables")
    print("-" * 50)
    
    # Load configuration
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    # Initialize loader
    loader = CSVToPostgresLoader(config)
    
    try:
        # Connect to database
        if not loader.connect_to_database():
            print("Failed to connect to database")
            return False
        
        # Load all tables (drop existing)
        success = loader.process_all_tables(drop_tables=True, append_mode=False)
        
        if success:
            print("✓ Successfully loaded all tables")
        else:
            print("✗ Failed to load some tables")
        
        return success
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return False
    finally:
        loader.close_connection()


def example_append_mode():
    """Example of append mode - add new data to existing tables."""
    print("\nExample 2: Append Mode - Add New Data")
    print("-" * 50)
    
    # Load configuration
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    # Initialize loader
    loader = CSVToPostgresLoader(config)
    
    try:
        # Connect to database
        if not loader.connect_to_database():
            print("Failed to connect to database")
            return False
        
        # Load all tables in append mode
        success = loader.process_all_tables(drop_tables=False, append_mode=True)
        
        if success:
            print("✓ Successfully appended data to all tables")
        else:
            print("✗ Failed to append data to some tables")
        
        return success
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return False
    finally:
        loader.close_connection()


def example_single_table():
    """Example of loading a single table."""
    print("\nExample 3: Single Table Loading")
    print("-" * 50)
    
    # Load configuration
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    # Initialize loader
    loader = CSVToPostgresLoader(config)
    
    try:
        # Connect to database
        if not loader.connect_to_database():
            print("Failed to connect to database")
            return False
        
        # Load only the agents table
        table_name = 'dev_agents'
        success = loader.process_table(table_name, drop_tables=True, append_mode=False)
        
        if success:
            print(f"✓ Successfully loaded table: {table_name}")
        else:
            print(f"✗ Failed to load table: {table_name}")
        
        return success
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return False
    finally:
        loader.close_connection()


def example_custom_configuration():
    """Example of using custom configuration."""
    print("\nExample 4: Custom Configuration")
    print("-" * 50)
    
    # Create custom configuration
    custom_config = {
        "database": {
            "host": "localhost",
            "port": 5432,
            "database": "my_custom_db",
            "user": "my_user",
            "password": "my_password"
        },
        "data_directory": "/custom/path/to/csv/files",
        "mdl_directory": "/custom/path/to/mdl/schemas"
    }
    
    # Initialize loader with custom config
    loader = CSVToPostgresLoader(custom_config)
    
    print("Custom configuration created:")
    print(f"  Database: {custom_config['database']['database']}")
    print(f"  Data Directory: {custom_config['data_directory']}")
    print(f"  MDL Directory: {custom_config['mdl_directory']}")
    
    # Note: This example doesn't actually connect since it's using dummy config
    print("✓ Custom configuration example completed")
    return True


def example_error_handling():
    """Example of error handling."""
    print("\nExample 5: Error Handling")
    print("-" * 50)
    
    # Create configuration with invalid database settings
    invalid_config = {
        "database": {
            "host": "invalid_host",
            "port": 5432,
            "database": "nonexistent_db",
            "user": "invalid_user",
            "password": "invalid_password"
        },
        "data_directory": "/nonexistent/path",
        "mdl_directory": "/nonexistent/mdl/path"
    }
    
    # Initialize loader
    loader = CSVToPostgresLoader(invalid_config)
    
    try:
        # Try to connect (this will fail)
        if not loader.connect_to_database():
            print("✓ Correctly handled database connection failure")
        else:
            print("✗ Should have failed to connect")
            return False
        
        # Try to process tables (this will also fail)
        success = loader.process_all_tables()
        if not success:
            print("✓ Correctly handled processing failure")
        else:
            print("✗ Should have failed to process tables")
            return False
        
        return True
        
    except Exception as e:
        print(f"✓ Correctly caught exception: {str(e)}")
        return True
    finally:
        loader.close_connection()


def main():
    """Run all examples."""
    print("CSV to PostgreSQL Loader - Usage Examples")
    print("=" * 60)
    
    examples = [
        ("Basic Usage", example_basic_usage),
       # ("Append Mode", example_append_mode),
       # ("Single Table", example_single_table),
       # ("Custom Configuration", example_custom_configuration),
       # ("Error Handling", example_error_handling)
    ]
    
    for example_name, example_func in examples:
        try:
            example_func()
        except Exception as e:
            print(f"Example '{example_name}' failed with error: {str(e)}")
    
    print("\n" + "=" * 60)
    print("All examples completed!")
    print("\nNote: Some examples may fail if database is not configured.")
    print("Make sure to update config.json with your actual database settings.")


if __name__ == "__main__":
    main()

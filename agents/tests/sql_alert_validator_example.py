"""
SQL Alert Condition Validator Usage Example

This example demonstrates how to use the SQLAlertConditionValidator to validate
alert conditions using both PandasEngine and PostgreSQL engine.

Examples included:
1. Core service validation with PandasEngine
2. Threshold validation with PandasEngine
3. Percentage validation with PandasEngine
4. Change validation with PandasEngine
5. Percent change validation with PandasEngine
6. Error handling examples
7. PostgreSQL engine validation (requires database connection)
8. PostgreSQL with sample data creation and validation
"""

import asyncio
import aiohttp
import pandas as pd
from datetime import datetime

from app.core.pandas_engine import PandasEngine
from app.core.engine_provider import EngineProvider
from app.core.sql_validation import (
    SQLValidationService, 
    SQLAlertConditionValidator,
    AlertConditionType, 
    ThresholdOperator,
    LexyFeedCondition
)
from app.settings import get_settings, EngineType


def is_non_select_statement(sql: str) -> bool:
    """Check if SQL statement is DDL/DML that doesn't support LIMIT clause"""
    sql_upper = sql.strip().upper()
    # DDL statements that don't support LIMIT
    ddl_keywords = ['CREATE', 'DROP', 'ALTER', 'TRUNCATE', 'RENAME', 'COMMENT']
    # DML statements that don't support LIMIT
    dml_keywords = ['INSERT', 'UPDATE', 'DELETE']
    return any(sql_upper.startswith(keyword) for keyword in ddl_keywords + dml_keywords)


async def example_core_service_validation():
    """Example of using the core SQLValidationService directly"""
    
    # Create sample data
    sample_data = pd.DataFrame({
        'division': ['Engineering', 'Sales', 'Marketing', 'Support'],
        'completion_rate': [95.5, 92.3, 78.1, 88.9],
        'total_training': [100, 150, 80, 120]
    })
    
    # Create PandasEngine with sample data
    engine = PandasEngine()
    engine.add_data_source('training_data', sample_data)
    
    # Create validation service directly
    validation_service = SQLValidationService(engine)
    
    # Example: Validate completion rate > 90%
    sql_query = "SELECT completion_rate FROM training_data WHERE division = 'Engineering'"
    
    result = await validation_service.validate_threshold_condition(
        sql_query=sql_query,
        condition_type=AlertConditionType.THRESHOLD_VALUE,
        operator=ThresholdOperator.GREATER_THAN,
        threshold_value=90.0,
        metric_column='completion_rate'
    )
    
    print("=== Core Service Validation Example ===")
    print(f"SQL Query: {sql_query}")
    print(f"Condition: completion_rate > 90.0")
    print(f"Result: {result}")
    print(f"Current Value: {result.current_value}")
    print(f"Condition Met: {result.condition_met}")
    print(f"Execution Time: {result.execution_time_ms}ms")
    print()


async def example_threshold_validation():
    """Example of validating a simple threshold condition using the wrapper"""
    
    # Create sample data
    sample_data = pd.DataFrame({
        'division': ['Engineering', 'Sales', 'Marketing', 'Support'],
        'completion_rate': [85.5, 92.3, 78.1, 88.9],
        'total_training': [100, 150, 80, 120]
    })
    
    # Create PandasEngine with sample data
    engine = PandasEngine()
    engine.add_data_source('training_data', sample_data)
    
    # Create validator (wrapper around core service)
    validator = SQLAlertConditionValidator(engine)
    
    # Example 1: Validate completion rate > 90%
    sql_query = "SELECT completion_rate FROM training_data WHERE division = 'Sales'"
    
    result = await validator.validate_threshold_condition(
        sql_query=sql_query,
        condition_type=AlertConditionType.THRESHOLD_VALUE,
        operator=ThresholdOperator.GREATER_THAN,
        threshold_value=90.0,
        metric_column='completion_rate'
    )
    
    print("=== Threshold Validation Example ===")
    print(f"SQL Query: {sql_query}")
    print(f"Condition: completion_rate > 90.0")
    print(f"Result: {result}")
    print(f"Current Value: {result.current_value}")
    print(f"Condition Met: {result.condition_met}")
    print(f"Execution Time: {result.execution_time_ms}ms")
    print()
    
    # Example 2: Validate using LexyFeedCondition object
    condition = LexyFeedCondition(
        condition_type=AlertConditionType.THRESHOLD_VALUE,
        operator=ThresholdOperator.LESS_THAN,
        value=80.0
    )
    
    result2 = await validator.validate_condition(
        sql_query="SELECT completion_rate FROM training_data WHERE division = 'Marketing'",
        condition=condition,
        metric_column='completion_rate'
    )
    
    print("=== LexyFeedCondition Validation Example ===")
    print(f"Condition: {condition}")
    print(f"Result: {result2}")
    print(f"Current Value: {result2.current_value}")
    print(f"Condition Met: {result2.condition_met}")
    print()


async def example_percentage_validation():
    """Example of validating percentage conditions"""
    
    # Create sample data with percentage values
    sample_data = pd.DataFrame({
        'department': ['HR', 'Finance', 'IT', 'Operations'],
        'budget_utilization': [75.2, 89.5, 65.8, 92.1],  # Percentage values
        'employee_count': [25, 30, 45, 60]
    })
    
    engine = PandasEngine()
    engine.add_data_source('department_data', sample_data)
    validator = SQLAlertConditionValidator(engine)
    
    # Validate budget utilization < 85%
    result = await validator.validate_percentage_condition(
        sql_query="SELECT budget_utilization FROM department_data WHERE department = 'Finance' AND employee_count > 30",
        operator=ThresholdOperator.LESS_THAN,
        threshold_percentage=85.0,
        metric_column='budget_utilization'
    )
    
    print("=== Percentage Validation Example ===")
    print(f"Condition: budget_utilization < 85%")
    print(f"Result: {result}")
    print(f"Current Value: {result.current_value}%")
    print(f"Condition Met: {result.condition_met}")
    print()


async def example_change_validation():
    """Example of validating change-based conditions"""
    
    # Create sample data for current and previous periods
    current_data = pd.DataFrame({
        'metric_name': ['sales', 'revenue', 'customers'],
        'current_value': [15000, 250000, 1200]
    })
    
    previous_data = pd.DataFrame({
        'metric_name': ['sales', 'revenue', 'customers'],
        'previous_value': [12000, 200000, 1000]
    })
    
    engine = PandasEngine()
    engine.add_data_source('current_metrics', current_data)
    engine.add_data_source('previous_metrics', previous_data)
    validator = SQLAlertConditionValidator(engine)
    
    # Validate sales increase > 2000
    current_sql = "SELECT current_value FROM current_metrics WHERE metric_name = 'sales'"
    previous_sql = "SELECT previous_value FROM previous_metrics WHERE metric_name = 'sales'"
    
    result = await validator.validate_change_condition(
        current_sql=current_sql,
        previous_sql=previous_sql,
        operator=ThresholdOperator.GREATER_THAN,
        change_threshold=2000.0,
        metric_column='current_value'
    )
    
    print("=== Change Validation Example ===")
    print(f"Current SQL: {current_sql}")
    print(f"Previous SQL: {previous_sql}")
    print(f"Condition: sales change > 2000")
    print(f"Result: {result}")
    print(f"Absolute Change: {result.current_value}")
    print(f"Condition Met: {result.condition_met}")
    print()


async def example_percent_change_validation():
    """Example of validating percentage change conditions"""
    
    # Create sample data for current and previous periods
    current_data = pd.DataFrame({
        'metric_name': ['conversion_rate', 'retention_rate', 'satisfaction_score'],
        'current_value': [3.2, 85.5, 4.1]
    })
    
    previous_data = pd.DataFrame({
        'metric_name': ['conversion_rate', 'retention_rate', 'satisfaction_score'],
        'previous_value': [2.8, 90.0, 3.9]
    })
    
    engine = PandasEngine()
    engine.add_data_source('current_metrics', current_data)
    engine.add_data_source('previous_metrics', previous_data)
    validator = SQLAlertConditionValidator(engine)
    
    # Validate conversion rate increase > 10%
    current_sql = "SELECT current_value FROM current_metrics WHERE metric_name = 'conversion_rate'"
    previous_sql = "SELECT previous_value FROM previous_metrics WHERE metric_name = 'conversion_rate'"
    
    result = await validator.validate_percent_change_condition(
        current_sql=current_sql,
        previous_sql=previous_sql,
        operator=ThresholdOperator.GREATER_THAN,
        percent_change_threshold=10.0,
        metric_column='current_value'
    )
    
    print("=== Percent Change Validation Example ===")
    print(f"Current SQL: {current_sql}")
    print(f"Previous SQL: {previous_sql}")
    print(f"Condition: conversion rate change > 10%")
    print(f"Result: {result}")
    print(f"Percent Change: {result.current_value}%")
    print(f"Condition Met: {result.condition_met}")
    print()


async def example_error_handling():
    """Example of error handling in validation"""
    
    # Create sample data for valid case
    sample_data = pd.DataFrame({
        'metric_name': ['test_metric'],
        'value': [50.0]
    })
    
    engine = PandasEngine()
    engine.add_data_source('test_table', sample_data)
    validator = SQLAlertConditionValidator(engine)
    
    sql_query = "SELECT * FROM non_existent_table"
    # Try to validate with invalid SQL (non-existent table)
    result = await validator.validate_threshold_condition(
        sql_query="SELECT * FROM non_existent_table",
        condition_type=AlertConditionType.THRESHOLD_VALUE,
        operator=ThresholdOperator.GREATER_THAN,
        threshold_value=100.0
    )
    
    print("=== Error Handling Example ===")
    print(f"SQL Query: {sql_query}")
    print(f"Invalid SQL Query Result: {result}")
    print(f"Is Valid: {result.is_valid}")
    print(f"Error Message: {result.error_message}")
    print()
    sql_query = "SELECT value FROM test_table WHERE metric_name = 'test_metric'"
    # Also show a valid case for comparison
    valid_result = await validator.validate_threshold_condition(
        sql_query="SELECT value FROM test_table WHERE metric_name = 'test_metric'",
        condition_type=AlertConditionType.THRESHOLD_VALUE,
        operator=ThresholdOperator.GREATER_THAN,
        threshold_value=40.0
    )
    
    print("=== Valid SQL Query Result ===")
    print(f"SQL Query: {sql_query}")
    print(f"Valid SQL Query Result: {valid_result}")
    print(f"Is Valid: {valid_result.is_valid}")
    print(f"Current Value: {valid_result.current_value}")
    print(f"Condition Met: {valid_result.condition_met}")
    print()


async def example_postgres_validation():
    """Example of using PostgreSQL engine for validation"""
    
    print("=== PostgreSQL Engine Validation Example ===")
    
    try:
        # Get settings to check PostgreSQL configuration
        settings = get_settings()
        print(f"Using PostgreSQL engine with database: {settings.POSTGRES_DB}")
        print(f"Host: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}")
        
        # Create PostgreSQL engine using EngineProvider
        engine = EngineProvider.get_engine(engine_type=EngineType.POSTGRES)
        print(f"Engine type: {engine.engine_type}")
        
        # Create validator with PostgreSQL engine
        validator = SQLAlertConditionValidator(engine)
        
        # First, let's check what tables exist in the database
        print("\nChecking available tables in the database...")
        tables_query = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
        
        try:
            # Create aiohttp session for execute_sql
            async with aiohttp.ClientSession() as session:
                success, tables_result = await engine.execute_sql(tables_query, session, dry_run=False)
                if success and tables_result and 'data' in tables_result and len(tables_result['data']) > 0:
                    available_tables = [row[0] for row in tables_result['data']]
                    print(f"Available tables: {', '.join(available_tables)}")
                    
                    # Use the first available table for our examples
                    if available_tables:
                        sample_table = available_tables[0]
                        print(f"Using table '{sample_table}' for validation examples")
                        
                        # Example 1: Count records in the table
                        count_sql = f"SELECT COUNT(*) as total_records FROM {sample_table}"
                        print(f"\nTesting record count validation:")
                        print(f"SQL Query: {count_sql}")
                        
                        result = await validator.validate_threshold_condition(
                            sql_query=count_sql,
                            condition_type=AlertConditionType.THRESHOLD_VALUE,
                            operator=ThresholdOperator.GREATER_THAN,
                            threshold_value=0.0,
                            metric_column='total_records'
                        )
                        
                        print(f"Record Count Validation Result:")
                        print(f"  Is Valid: {result.is_valid}")
                        print(f"  Current Value: {result.current_value}")
                        print(f"  Condition Met: {result.condition_met}")
                        print(f"  Execution Time: {result.execution_time_ms}ms")
                        
                        if not result.is_valid:
                            print(f"  Error Message: {result.error_message}")
                        
                        # Example 2: Try to get a sample of data from the table
                        if len(available_tables) > 0:
                            sample_sql = f"SELECT * FROM {sample_table} LIMIT 1"
                            print(f"\nTesting sample data retrieval:")
                            print(f"SQL Query: {sample_sql}")
                            
                            try:
                                sample_success, sample_result = await engine.execute_sql(sample_sql, session, dry_run=False)
                                if sample_success and sample_result and 'data' in sample_result and len(sample_result['data']) > 0:
                                    print(f"Sample data retrieved successfully: {len(sample_result['data'])} row(s)")
                                    if sample_result['data'] and len(sample_result['data']) > 0:
                                        first_row = sample_result['data'][0]
                                        if hasattr(first_row, 'keys'):
                                            print(f"Columns: {list(first_row.keys())}")
                                        else:
                                            print(f"Sample row: {first_row}")
                                else:
                                    print("No data found in the table")
                            except Exception as e:
                                print(f"Sample data retrieval failed: {str(e)}")
                    else:
                        print("No tables found in the database")
                else:
                    print("No tables found in the database")
                
        except Exception as e:
            print(f"Failed to check available tables: {str(e)}")
        
        # Example 3: Test error handling with invalid table
        print(f"\nTesting Error Handling with Invalid Table:")
        invalid_sql = "SELECT * FROM non_existent_table_12345 WHERE id = 1"
        print(f"SQL Query: {invalid_sql}")
        
        result3 = await validator.validate_threshold_condition(
            sql_query=invalid_sql,
            condition_type=AlertConditionType.THRESHOLD_VALUE,
            operator=ThresholdOperator.GREATER_THAN,
            threshold_value=100.0
        )
        
        print(f"Invalid SQL Result:")
        print(f"  Is Valid: {result3.is_valid}")
        print(f"  Error Message: {result3.error_message}")
        
        # Example 4: Test with system tables (these should always exist)
        print(f"\nTesting with system table (information_schema):")
        system_sql = "SELECT COUNT(*) as table_count FROM information_schema.tables WHERE table_schema = 'public'"
        print(f"SQL Query: {system_sql}")
        
        # Create a new session for this validation
        async with aiohttp.ClientSession() as session:
            result4 = await validator.validate_threshold_condition(
                sql_query=system_sql,
                condition_type=AlertConditionType.THRESHOLD_VALUE,
                operator=ThresholdOperator.GREATER_THAN,
                threshold_value=0.0,
                metric_column='table_count',
                session=session
            )
        
        print(f"System Table Validation Result:")
        print(f"  Is Valid: {result4.is_valid}")
        print(f"  Current Value: {result4.current_value}")
        print(f"  Condition Met: {result4.condition_met}")
        print(f"  Execution Time: {result4.execution_time_ms}ms")
        
    except Exception as e:
        print(f"PostgreSQL validation failed: {str(e)}")
        print("This might be due to:")
        print("  - PostgreSQL connection issues")
        print("  - Missing tables in the database")
        print("  - Network connectivity problems")
        print("  - Invalid database credentials")
    
    print()


async def example_postgres_with_sample_data():
    """Example of using PostgreSQL engine with sample data creation and validation"""
    
    print("=== PostgreSQL with Sample Data Example ===")
    
    try:
        # Get settings and create PostgreSQL engine
        settings = get_settings()
        engine = EngineProvider.get_engine(engine_type=EngineType.POSTGRES)
        validator = SQLAlertConditionValidator(engine)
        
        print(f"Using PostgreSQL engine with database: {settings.POSTGRES_DB}")
        
        # Create sample tables and data in PostgreSQL
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS employee_training_metrics (
            id SERIAL PRIMARY KEY,
            division VARCHAR(50) NOT NULL,
            completion_rate DECIMAL(5,2) NOT NULL,
            total_assignments INTEGER NOT NULL,
            completed_assignments INTEGER NOT NULL,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        insert_data_sql = """
        INSERT INTO employee_training_metrics (division, completion_rate, total_assignments, completed_assignments) 
        VALUES 
            ('Engineering', 95.5, 100, 95),
            ('Sales', 92.3, 150, 138),
            ('Marketing', 78.1, 80, 62),
            ('Support', 88.9, 120, 107),
            ('HR', 85.2, 90, 77)
        ON CONFLICT DO NOTHING;
        """
        
        print("Creating sample table and data...")
        
        # Execute table creation and data insertion
        async with aiohttp.ClientSession() as session:
            # Use limit=0 for DDL/DML statements to prevent automatic LIMIT addition
            create_limit = 0 if is_non_select_statement(create_table_sql) else None
            insert_limit = 0 if is_non_select_statement(insert_data_sql) else None
            await engine.execute_sql(create_table_sql, session, dry_run=False, limit=create_limit)
            await engine.execute_sql(insert_data_sql, session, dry_run=False, limit=insert_limit)
        
        print("Sample data created successfully!")
        
        # Example 1: Validate completion rate threshold
        sql_query = """
        SELECT completion_rate 
        FROM employee_training_metrics 
        WHERE division = 'Engineering'
        """
        
        print(f"\nTesting completion rate validation:")
        print(f"SQL Query: {sql_query.strip()}")
        
        result = await validator.validate_threshold_condition(
            sql_query=sql_query,
            condition_type=AlertConditionType.THRESHOLD_VALUE,
            operator=ThresholdOperator.GREATER_THAN,
            threshold_value=90.0,
            metric_column='completion_rate'
        )
        
        print(f"Result:")
        print(f"  Is Valid: {result.is_valid}")
        print(f"  Current Value: {result.current_value}")
        print(f"  Condition Met: {result.condition_met}")
        print(f"  Execution Time: {result.execution_time_ms}ms")
        
        # Example 2: Validate average completion rate across all divisions
        avg_sql_query = """
        SELECT AVG(completion_rate) as avg_completion_rate
        FROM employee_training_metrics
        """
        
        print(f"\nTesting average completion rate validation:")
        print(f"SQL Query: {avg_sql_query.strip()}")
        
        avg_result = await validator.validate_threshold_condition(
            sql_query=avg_sql_query,
            condition_type=AlertConditionType.THRESHOLD_VALUE,
            operator=ThresholdOperator.GREATER_THAN,
            threshold_value=85.0,
            metric_column='avg_completion_rate'
        )
        
        print(f"Average Completion Rate Result:")
        print(f"  Is Valid: {avg_result.is_valid}")
        print(f"  Current Value: {avg_result.current_value}")
        print(f"  Condition Met: {avg_result.condition_met}")
        
        # Example 3: Validate percentage condition
        percentage_sql = """
        SELECT completion_rate 
        FROM employee_training_metrics 
        WHERE division = 'Marketing'
        """
        
        print(f"\nTesting percentage validation:")
        print(f"SQL Query: {percentage_sql.strip()}")
        
        percentage_result = await validator.validate_percentage_condition(
            sql_query=percentage_sql,
            operator=ThresholdOperator.LESS_THAN,
            threshold_percentage=80.0,
            metric_column='completion_rate'
        )
        
        print(f"Percentage Validation Result:")
        print(f"  Is Valid: {percentage_result.is_valid}")
        print(f"  Current Value: {percentage_result.current_value}%")
        print(f"  Condition Met: {percentage_result.condition_met}")
        
        # Example 4: Complex query with multiple conditions
        complex_sql = """
        SELECT COUNT(*) as low_performers
        FROM employee_training_metrics 
        WHERE completion_rate < 85.0
        """
        
        print(f"\nTesting complex query validation:")
        print(f"SQL Query: {complex_sql.strip()}")
        
        complex_result = await validator.validate_threshold_condition(
            sql_query=complex_sql,
            condition_type=AlertConditionType.THRESHOLD_VALUE,
            operator=ThresholdOperator.LESS_THAN,
            threshold_value=2.0,
            metric_column='low_performers'
        )
        
        print(f"Complex Query Result:")
        print(f"  Is Valid: {complex_result.is_valid}")
        print(f"  Current Value: {complex_result.current_value}")
        print(f"  Condition Met: {complex_result.condition_met}")
        
        # Clean up - drop the sample table
        cleanup_sql = "DROP TABLE IF EXISTS employee_training_metrics;"
        async with aiohttp.ClientSession() as session:
            # Use limit=0 for DDL/DML statements to prevent automatic LIMIT addition
            cleanup_limit = 0 if is_non_select_statement(cleanup_sql) else None
            await engine.execute_sql(cleanup_sql, session, dry_run=False, limit=cleanup_limit)
        print(f"\nSample table cleaned up successfully!")
        
    except Exception as e:
        print(f"PostgreSQL sample data validation failed: {str(e)}")
        print("This might be due to:")
        print("  - PostgreSQL connection issues")
        print("  - Insufficient permissions to create tables")
        print("  - Network connectivity problems")
        print("  - Invalid database credentials")
    
    print()


async def main():
    """Run all examples"""
    print("SQL Alert Condition Validator Examples")
    print("=" * 50)
    print()
    
    await example_core_service_validation()
    await example_threshold_validation()
    await example_percentage_validation()
    await example_change_validation()
    await example_percent_change_validation()
    await example_error_handling()
    await example_postgres_validation()
    await example_postgres_with_sample_data()
    
    print("All examples completed!")


if __name__ == "__main__":
    asyncio.run(main())

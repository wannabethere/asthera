"""
PostgreSQL Alert Validator Demo

This is a focused demo script that shows how to use the SQLAlertConditionValidator
with PostgreSQL engine as configured in settings.py.

Usage:
    python postgres_alert_validator_demo.py

Prerequisites:
    - PostgreSQL database connection configured in settings.py
    - Required dependencies installed (psycopg2, sqlalchemy)
    - Database permissions to create/drop tables (for sample data example)
"""

import asyncio
import logging
import aiohttp
from app.core.engine_provider import EngineProvider
from app.core.sql_validation import (
    SQLAlertConditionValidator,
    AlertConditionType, 
    ThresholdOperator
)
from app.settings import get_settings, EngineType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def is_non_select_statement(sql: str) -> bool:
    """Check if SQL statement is DDL/DML that doesn't support LIMIT clause"""
    sql_upper = sql.strip().upper()
    # DDL statements that don't support LIMIT
    ddl_keywords = ['CREATE', 'DROP', 'ALTER', 'TRUNCATE', 'RENAME', 'COMMENT']
    # DML statements that don't support LIMIT
    dml_keywords = ['INSERT', 'UPDATE', 'DELETE']
    return any(sql_upper.startswith(keyword) for keyword in ddl_keywords + dml_keywords)

async def demo_postgres_validation():
    """Demo PostgreSQL validation with existing data"""
    
    print("=== PostgreSQL Alert Validator Demo ===")
    print()
    
    try:
        # Get settings and create PostgreSQL engine
        settings = get_settings()
        print(f"Connecting to PostgreSQL database: {settings.POSTGRES_DB}")
        print(f"Host: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}")
        print()
        
        # Create PostgreSQL engine using EngineProvider
        engine = EngineProvider.get_engine(engine_type=EngineType.POSTGRES)
        validator = SQLAlertConditionValidator(engine)
        
        print("✅ PostgreSQL engine initialized successfully!")
        print()
        
        # First, check what tables are available
        print("Checking available tables in the database...")
        tables_query = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
        
        try:
            async with aiohttp.ClientSession() as session:
                success, tables_result = await engine.execute_sql(tables_query, session, dry_run=False)
                if success and tables_result and 'data' in tables_result and len(tables_result['data']) > 0:
                    available_tables = [row[0] for row in tables_result['data']]
                    print(f"📋 Available tables: {', '.join(available_tables)}")
                    print()
                    
                    # Use the first available table for our examples
                    if available_tables:
                        sample_table = available_tables[0]
                        print(f"Using table '{sample_table}' for validation examples")
                        print()
                        
                        # Example 1: Count records in the table
                        print("Example 1: Record Count Validation")
                        print("-" * 40)
                        
                        count_sql = f"SELECT COUNT(*) as total_records FROM {sample_table}"
                        print(f"SQL Query: {count_sql}")
                        
                        result = await validator.validate_threshold_condition(
                            sql_query=count_sql,
                            condition_type=AlertConditionType.THRESHOLD_VALUE,
                            operator=ThresholdOperator.GREATER_THAN,
                            threshold_value=0.0,
                            metric_column='total_records',
                            session=session
                        )
                        
                        print(f"Result:")
                        print(f"  ✅ Is Valid: {result.is_valid}")
                        print(f"  📊 Current Value: {result.current_value}")
                        print(f"  🎯 Condition Met: {result.condition_met}")
                        print(f"  ⏱️  Execution Time: {result.execution_time_ms}ms")
                        print()
                        
                        # Example 2: Try to get column information
                        print("Example 2: Column Information")
                        print("-" * 40)
                        
                        columns_sql = f"""
                        SELECT column_name, data_type 
                        FROM information_schema.columns 
                        WHERE table_name = '{sample_table}' 
                        AND table_schema = 'public'
                        LIMIT 5
                        """
                        print(f"SQL Query: {columns_sql.strip()}")
                        
                        try:
                            columns_success, columns_result = await engine.execute_sql(columns_sql, session, dry_run=False)
                            if columns_success and columns_result and 'data' in columns_result and len(columns_result['data']) > 0:
                                print(f"📋 Sample columns from {sample_table}:")
                                for row in columns_result['data']:
                                    print(f"  - {row[0]} ({row[1]})")
                            else:
                                print("No column information found")
                        except Exception as e:
                            print(f"Failed to get column information: {str(e)}")
                        print()
                    else:
                        print("No tables found in the database")
                else:
                    print("No tables found in the database")
        except Exception as e:
            print(f"Failed to check available tables: {str(e)}")
        
        # Example 3: System table validation (always works)
        print("Example 3: System Table Validation")
        print("-" * 40)
        
        system_sql = """
        SELECT COUNT(*) as total_records
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        """
        
        print(f"SQL Query: {system_sql.strip()}")
        
        async with aiohttp.ClientSession() as session:
            result = await validator.validate_threshold_condition(
                sql_query=system_sql,
                condition_type=AlertConditionType.THRESHOLD_VALUE,
                operator=ThresholdOperator.GREATER_THAN,
                threshold_value=0.0,
                metric_column='total_records',
                session=session
            )
        
        print(f"Result:")
        print(f"  ✅ Is Valid: {result.is_valid}")
        print(f"  📊 Current Value: {result.current_value}")
        print(f"  🎯 Condition Met: {result.condition_met}")
        print(f"  ⏱️  Execution Time: {result.execution_time_ms}ms")
        print()
        
        # Example 4: Test error handling
        print("Example 4: Error Handling")
        print("-" * 40)
        
        invalid_sql = "SELECT * FROM non_existent_table_12345"
        print(f"SQL Query: {invalid_sql}")
        
        error_result = await validator.validate_threshold_condition(
            sql_query=invalid_sql,
            condition_type=AlertConditionType.THRESHOLD_VALUE,
            operator=ThresholdOperator.GREATER_THAN,
            threshold_value=100.0
        )
        
        print(f"Result:")
        print(f"  ❌ Is Valid: {error_result.is_valid}")
        print(f"  🚨 Error Message: {error_result.error_message}")
        print()
        
        print("✅ PostgreSQL validation demo completed successfully!")
        
    except Exception as e:
        print(f"❌ Demo failed: {str(e)}")
        print()
        print("Troubleshooting tips:")
        print("1. Check your PostgreSQL connection settings in settings.py")
        print("2. Ensure PostgreSQL server is running and accessible")
        print("3. Verify database credentials are correct")
        print("4. Check network connectivity to the database server")
        print("5. Ensure required dependencies are installed: pip install psycopg2-binary sqlalchemy")

async def demo_postgres_with_sample_data():
    """Demo PostgreSQL validation with sample data creation"""
    
    print("=== PostgreSQL with Sample Data Demo ===")
    print()
    
    try:
        # Get settings and create PostgreSQL engine
        settings = get_settings()
        engine = EngineProvider.get_engine(engine_type=EngineType.POSTGRES)
        validator = SQLAlertConditionValidator(engine)
        
        print(f"Using database: {settings.POSTGRES_DB}")
        print()
        
        # Create sample table
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS demo_metrics (
            id SERIAL PRIMARY KEY,
            metric_name VARCHAR(100) NOT NULL,
            value DECIMAL(10,2) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        print("Creating sample table...")
        async with aiohttp.ClientSession() as session:
            # Use limit=0 for DDL/DML statements to prevent automatic LIMIT addition
            create_limit = 0 if is_non_select_statement(create_table_sql) else None
            await engine.execute_sql(create_table_sql, session, dry_run=False, limit=create_limit)
        print("✅ Sample table created!")
        
        # Insert sample data
        insert_data_sql = """
        INSERT INTO demo_metrics (metric_name, value) 
        VALUES 
            ('completion_rate', 95.5),
            ('error_rate', 2.1),
            ('response_time', 150.0),
            ('throughput', 1000.0)
        ON CONFLICT DO NOTHING;
        """
        
        print("Inserting sample data...")
        async with aiohttp.ClientSession() as session:
            # Use limit=0 for DDL/DML statements to prevent automatic LIMIT addition
            insert_limit = 0 if is_non_select_statement(insert_data_sql) else None
            await engine.execute_sql(insert_data_sql, session, dry_run=False, limit=insert_limit)
        print("✅ Sample data inserted!")
        print()
        
        # Example 1: Validate completion rate
        print("Example 1: Completion Rate Validation")
        print("-" * 40)
        
        sql_query = "SELECT value FROM demo_metrics WHERE metric_name = 'completion_rate'"
        print(f"SQL Query: {sql_query}")
        
        result = await validator.validate_threshold_condition(
            sql_query=sql_query,
            condition_type=AlertConditionType.THRESHOLD_VALUE,
            operator=ThresholdOperator.GREATER_THAN,
            threshold_value=90.0,
            metric_column='value'
        )
        
        print(f"Result:")
        print(f"  ✅ Is Valid: {result.is_valid}")
        print(f"  📊 Current Value: {result.current_value}")
        print(f"  🎯 Condition Met: {result.condition_met}")
        print()
        
        # Example 2: Validate error rate
        print("Example 2: Error Rate Validation")
        print("-" * 40)
        
        error_sql = "SELECT value FROM demo_metrics WHERE metric_name = 'error_rate'"
        print(f"SQL Query: {error_sql}")
        
        error_result = await validator.validate_threshold_condition(
            sql_query=error_sql,
            condition_type=AlertConditionType.THRESHOLD_VALUE,
            operator=ThresholdOperator.LESS_THAN,
            threshold_value=5.0,
            metric_column='value'
        )
        
        print(f"Result:")
        print(f"  ✅ Is Valid: {error_result.is_valid}")
        print(f"  📊 Current Value: {error_result.current_value}")
        print(f"  🎯 Condition Met: {error_result.condition_met}")
        print()
        
        # Example 3: Percentage validation
        print("Example 3: Percentage Validation")
        print("-" * 40)
        
        percentage_sql = "SELECT value FROM demo_metrics WHERE metric_name = 'completion_rate'"
        print(f"SQL Query: {percentage_sql}")
        
        percentage_result = await validator.validate_percentage_condition(
            sql_query=percentage_sql,
            operator=ThresholdOperator.GREATER_THAN,
            threshold_percentage=90.0,
            metric_column='value'
        )
        
        print(f"Result:")
        print(f"  ✅ Is Valid: {percentage_result.is_valid}")
        print(f"  📊 Current Value: {percentage_result.current_value}%")
        print(f"  🎯 Condition Met: {percentage_result.condition_met}")
        print()
        
        # Clean up
        print("Cleaning up sample data...")
        cleanup_sql = "DROP TABLE IF EXISTS demo_metrics;"
        async with aiohttp.ClientSession() as session:
            # Use limit=0 for DDL/DML statements to prevent automatic LIMIT addition
            cleanup_limit = 0 if is_non_select_statement(cleanup_sql) else None
            await engine.execute_sql(cleanup_sql, session, dry_run=False, limit=cleanup_limit)
        print("✅ Sample data cleaned up!")
        print()
        
        print("✅ PostgreSQL sample data demo completed successfully!")
        
    except Exception as e:
        print(f"❌ Sample data demo failed: {str(e)}")
        print()
        print("This might be due to:")
        print("1. Insufficient database permissions to create/drop tables")
        print("2. PostgreSQL connection issues")
        print("3. Database schema restrictions")

async def main():
    """Run the PostgreSQL demos"""
    
    print("PostgreSQL Alert Validator Demo")
    print("=" * 50)
    print()
    
    # Run basic validation demo
    await demo_postgres_validation()
    print()
    
    # Ask user if they want to run the sample data demo
    print("Would you like to run the sample data demo? (This will create/drop tables)")
    print("Note: This requires database permissions to create and drop tables.")
    print()
    
    # For automated testing, we'll run both demos
    # In a real scenario, you might want to add user input here
    print("Running sample data demo...")
    await demo_postgres_with_sample_data()
    
    print()
    print("🎉 All PostgreSQL demos completed!")

if __name__ == "__main__":
    asyncio.run(main())

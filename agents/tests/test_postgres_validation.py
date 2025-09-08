"""
Quick test script to verify PostgreSQL validation examples work correctly.

This script tests the updated PostgreSQL examples that dynamically discover
available tables in the database instead of assuming specific table names.
"""

import asyncio
import logging
import aiohttp
from app.core.engine_provider import EngineProvider
from app.core.sql_validation import SQLAlertConditionValidator, AlertConditionType, ThresholdOperator
from app.settings import get_settings, EngineType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_postgres_connection():
    """Test basic PostgreSQL connection and table discovery"""
    
    print("=== PostgreSQL Connection Test ===")
    print()
    
    try:
        # Get settings
        settings = get_settings()
        print(f"Testing connection to: {settings.POSTGRES_DB}")
        print(f"Host: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}")
        print()
        
        # Create engine
        engine = EngineProvider.get_engine(engine_type=EngineType.POSTGRES)
        print("✅ Engine created successfully")
        
        # Test basic connection
        test_query = "SELECT 1 as test_value"
        async with aiohttp.ClientSession() as session:
            success, result = await engine.execute_sql(test_query, session, dry_run=False)
            print(f"✅ Basic connection test passed: {result}")
            print()
            
            # Test table discovery
            print("Discovering available tables...")
            tables_query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
            
            success, tables_result = await engine.execute_sql(tables_query, session, dry_run=False)
            if success and tables_result and 'data' in tables_result and len(tables_result['data']) > 0:
                available_tables = [row[0] for row in tables_result['data']]
                print(f"✅ Found {len(available_tables)} tables: {', '.join(available_tables)}")
                
                # Test validation with first table
                if available_tables:
                    sample_table = available_tables[0]
                    print(f"\nTesting validation with table: {sample_table}")
                    
                    validator = SQLAlertConditionValidator(engine)
                    
                    # Test count validation
                    count_sql = f"SELECT COUNT(*) as total_records FROM {sample_table}"
                    print(f"SQL: {count_sql}")
                    
                    result = await validator.validate_threshold_condition(
                        sql_query=count_sql,
                        condition_type=AlertConditionType.THRESHOLD_VALUE,
                        operator=ThresholdOperator.GREATER_THAN,
                        threshold_value=0.0,
                        metric_column='total_records',
                        session=session
                    )
                    
                    print(f"✅ Validation result:")
                    print(f"   Is Valid: {result.is_valid}")
                    print(f"   Current Value: {result.current_value}")
                    print(f"   Condition Met: {result.condition_met}")
                    print(f"   Execution Time: {result.execution_time_ms}ms")
                    
                    if not result.is_valid:
                        print(f"   Error: {result.error_message}")
                else:
                    print("⚠️  No tables found in the database")
            else:
                print("⚠️  No tables found in the database")
            
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        print("\nTroubleshooting:")
        print("1. Check PostgreSQL connection settings in settings.py")
        print("2. Ensure PostgreSQL server is running")
        print("3. Verify database credentials")
        print("4. Check network connectivity")
        return False
    
    print("\n✅ PostgreSQL validation test completed successfully!")
    return True

async def main():
    """Run the test"""
    print("PostgreSQL Validation Test")
    print("=" * 40)
    print()
    
    success = await test_postgres_connection()
    
    if success:
        print("\n🎉 All tests passed! The PostgreSQL examples should work correctly.")
    else:
        print("\n❌ Tests failed. Please check the connection and try again.")

if __name__ == "__main__":
    asyncio.run(main())

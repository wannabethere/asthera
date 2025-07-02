"""
Example script demonstrating PandasEngine caching functionality
"""
import asyncio
import pandas as pd
import aiohttp
from pandas_engine import PandasEngine, PandasEngineConfig
from app.utils.cache import InMemoryCache

async def main():
    """Demonstrate caching functionality"""
    
    # Create sample data
    sample_data = {
        'users': pd.DataFrame({
            'id': [1, 2, 3, 4, 5],
            'name': ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve'],
            'age': [25, 30, 35, 28, 32],
            'city': ['NYC', 'LA', 'Chicago', 'Boston', 'Seattle']
        }),
        'orders': pd.DataFrame({
            'id': [1, 2, 3, 4, 5],
            'user_id': [1, 2, 1, 3, 4],
            'amount': [100, 200, 150, 300, 250],
            'status': ['completed', 'pending', 'completed', 'shipped', 'pending']
        })
    }
    
    # Create engine with custom cache
    custom_cache = InMemoryCache()
    engine = PandasEngineConfig.from_dataframes(
        dataframes=sample_data,
        cache_provider=custom_cache,
        cache_ttl=1800  # 30 minutes
    )
    
    # Create aiohttp session (required by the interface)
    async with aiohttp.ClientSession() as session:
        
        # First query - should miss cache
        print("=== First Query (Cache Miss) ===")
        sql1 = "SELECT * FROM users WHERE age > 25"
        success1, result1 = await engine.execute_sql(sql1, session, dry_run=False)
        print(f"Success: {success1}")
        print(f"Rows returned: {result1.get('row_count', 0)}")
        print(f"Cache stats: {engine.get_cache_stats()}")
        
        # Second identical query - should hit cache
        print("\n=== Second Query (Cache Hit) ===")
        success2, result2 = await engine.execute_sql(sql1, session, dry_run=False)
        print(f"Success: {success2}")
        print(f"Rows returned: {result2.get('row_count', 0)}")
        print(f"Cache stats: {engine.get_cache_stats()}")
        
        # Query with different limit - should miss cache
        print("\n=== Query with Limit (Cache Miss) ===")
        success3, result3 = await engine.execute_sql(sql1, session, dry_run=False, limit=2)
        print(f"Success: {success3}")
        print(f"Rows returned: {result3.get('row_count', 0)}")
        print(f"Cache stats: {engine.get_cache_stats()}")
        
        # Query with cache disabled
        print("\n=== Query with Cache Disabled ===")
        success4, result4 = await engine.execute_sql(sql1, session, dry_run=False, use_cache=False)
        print(f"Success: {success4}")
        print(f"Rows returned: {result4.get('row_count', 0)}")
        
        # Batch query example
        print("\n=== Batch Query Example ===")
        sql_batch = "SELECT * FROM orders ORDER BY amount"
        success5, result5 = await engine.execute_sql_in_batches(
            sql_batch, 
            session, 
            batch_size=2, 
            dry_run=False
        )
        print(f"Success: {success5}")
        print(f"Total rows: {result5.get('total_count', 0)}")
        print(f"Batches processed: {result5.get('batches_processed', 0)}")
        
        # Clear cache
        print("\n=== Clearing Cache ===")
        await engine.clear_cache()
        print(f"Cache stats after clear: {engine.get_cache_stats()}")
        
        # Add new data source (should clear cache automatically)
        print("\n=== Adding New Data Source ===")
        new_data = pd.DataFrame({
            'id': [6, 7],
            'name': ['Frank', 'Grace'],
            'age': [40, 45],
            'city': ['Miami', 'Denver']
        })
        engine.add_data_source('users', new_data)
        print("New data source added - cache should be cleared automatically")
        print(f"Cache stats: {engine.get_cache_stats()}")

if __name__ == "__main__":
    asyncio.run(main()) 
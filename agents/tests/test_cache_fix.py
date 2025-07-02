"""
Test script to verify the engine_type fix for caching functionality
"""
import asyncio
import pandas as pd
import aiohttp
from pandas_engine import PandasEngine, PandasEngineConfig
from app.utils.cache import InMemoryCache
from app.settings import EngineType

async def test_engine_type_handling():
    """Test that engine_type is handled correctly whether it's an enum or string"""
    
    # Create sample data
    sample_data = {
        'users': pd.DataFrame({
            'id': [1, 2, 3],
            'name': ['Alice', 'Bob', 'Charlie'],
            'age': [25, 30, 35]
        })
    }
    
    # Test 1: Engine with enum engine_type
    print("=== Test 1: Enum EngineType ===")
    engine_enum = PandasEngineConfig.from_dataframes(
        dataframes=sample_data,
        engine_type=EngineType.PANDAS,
        cache_provider=InMemoryCache()
    )
    
    async with aiohttp.ClientSession() as session:
        sql = "SELECT * FROM users"
        success, result = await engine_enum.execute_sql(sql, session, dry_run=False)
        print(f"Enum engine success: {success}")
        print(f"Enum engine rows: {result.get('row_count', 0)}")
        print(f"Enum engine cache stats: {engine_enum.get_cache_stats()}")
    
    # Test 2: Engine with string engine_type
    print("\n=== Test 2: String EngineType ===")
    engine_string = PandasEngine(
        engine_type="PANDAS",  # String instead of enum
        data_sources=sample_data,
        cache_provider=InMemoryCache()
    )
    
    async with aiohttp.ClientSession() as session:
        sql = "SELECT * FROM users"
        success, result = await engine_string.execute_sql(sql, session, dry_run=False)
        print(f"String engine success: {success}")
        print(f"String engine rows: {result.get('row_count', 0)}")
        print(f"String engine cache stats: {engine_string.get_cache_stats()}")
    
    # Test 3: Cache key generation
    print("\n=== Test 3: Cache Key Generation ===")
    cache_key_enum = engine_enum._generate_cache_key("SELECT * FROM users", limit=10)
    cache_key_string = engine_string._generate_cache_key("SELECT * FROM users", limit=10)
    print(f"Enum engine cache key: {cache_key_enum}")
    print(f"String engine cache key: {cache_key_string}")
    print(f"Cache keys are different: {cache_key_enum != cache_key_string}")
    
    # Test 4: Cache hit/miss behavior
    print("\n=== Test 4: Cache Hit/Miss Behavior ===")
    async with aiohttp.ClientSession() as session:
        # First query - should miss cache
        success1, result1 = await engine_string.execute_sql(sql, session, dry_run=False)
        print(f"First query - cache miss: {result1.get('row_count', 0)} rows")
        
        # Second identical query - should hit cache
        success2, result2 = await engine_string.execute_sql(sql, session, dry_run=False)
        print(f"Second query - cache hit: {result2.get('row_count', 0)} rows")
        
        # Query with different limit - should miss cache
        success3, result3 = await engine_string.execute_sql(sql, session, dry_run=False, limit=2)
        print(f"Query with limit - cache miss: {result3.get('row_count', 0)} rows")
    
    print("\n=== Test completed successfully! ===")

if __name__ == "__main__":
    asyncio.run(test_engine_type_handling()) 
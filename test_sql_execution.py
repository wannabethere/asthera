#!/usr/bin/env python3
"""
Test script to verify SQL execution is working correctly after disabling caching
"""

import asyncio
import sys
import os
import logging

# Add the agents directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'agents'))

from app.core.pandas_engine import PandasEngine, EngineType
from app.core.provider import InMemoryCache
import pandas as pd

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_sql_execution():
    """Test SQL execution with the CSOD training records data"""
    
    # Create sample data similar to the CSOD training records
    sample_data = {
        'training_title': ['Code of Conduct Awareness', 'Effective Communication', 'Product Knowledge', 'Time Management'],
        'assigned_date': ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04'],
        'completed_date': ['2024-02-15', '2024-02-20', '2024-02-10', '2024-02-12'],
        'is_completed': [True, True, True, True]
    }
    
    # Convert to DataFrame
    df = pd.DataFrame(sample_data)
    df['assigned_date'] = pd.to_datetime(df['assigned_date'])
    df['completed_date'] = pd.to_datetime(df['completed_date'])
    
    # Create pandas engine with sample data
    engine = PandasEngine(
        engine_type=EngineType.PANDAS,
        data_sources={'csod_training_records': df},
        cache_provider=InMemoryCache(),
        cache_ttl=3600
    )
    
    # Test SQL query
    sql = """
    SELECT training_title, AVG(CAST(completed_date - assigned_date AS INTEGER)) AS avg_completion_time 
    FROM csod_training_records 
    WHERE is_completed = true 
    GROUP BY training_title 
    ORDER BY training_title
    """
    
    logger.info(f"Testing SQL execution with query: {sql}")
    
    # Execute SQL
    success, result = await engine.execute_sql(
        sql=sql,
        session=None,  # Not used in pandas engine
        dry_run=False,
        use_cache=False  # Explicitly disable caching
    )
    
    logger.info(f"SQL execution success: {success}")
    logger.info(f"SQL execution result: {result}")
    
    if success and result.get('data'):
        logger.info("✅ SQL execution successful - data returned!")
        logger.info(f"Number of rows: {len(result['data'])}")
        for row in result['data']:
            logger.info(f"Row: {row}")
    else:
        logger.error("❌ SQL execution failed or returned no data")
        logger.error(f"Error: {result.get('error', 'Unknown error')}")
    
    return success, result

if __name__ == "__main__":
    asyncio.run(test_sql_execution())

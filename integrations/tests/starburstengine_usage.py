"""
StarburstPandasEngine Usage Examples
===================================

Comprehensive examples showing how to use the StarburstPandasEngine
for different Starburst/Trino configurations and authentication methods.
"""

import asyncio
import pandas as pd
import aiohttp
import logging
from starburst_pandas_engine import StarburstPandasEngine, StarburstEngineConfig

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# 1. Basic Starburst Cloud Connection
# ============================================================================

async def example_starburst_cloud_basic():
    """Basic Starburst Cloud connection with username/password"""
    
    # Create engine for Starburst Cloud
    engine = StarburstEngineConfig.for_starburst_cloud(
        cluster_url='https://your-cluster.starburst.io',
        username='your-email@company.com',
        password='your-password',
        catalog='datalake',
        schema='analytics',
        session_properties={
            'query_max_memory': '2GB',
            'query_max_run_time': '1h',
            'join_distribution_type': 'AUTOMATIC'
        },
        client_info='my-analytics-app',
        client_tags=['production', 'analytics']
    )
    
    # Example queries
    queries = {
        'customer_analysis': """
            SELECT 
                customer_segment,
                COUNT(*) as customer_count,
                AVG(total_spent) as avg_spent,
                SUM(total_orders) as total_orders
            FROM datalake.analytics.customers 
            WHERE registration_date >= DATE '2024-01-01'
            GROUP BY customer_segment
            ORDER BY avg_spent DESC
        """,
        
        'sales_trend': """
            SELECT 
                DATE_TRUNC('month', order_date) as month,
                SUM(amount) as monthly_revenue,
                COUNT(DISTINCT customer_id) as unique_customers,
                AVG(amount) as avg_order_value
            FROM datalake.sales.orders
            WHERE order_date >= DATE '2024-01-01'
            GROUP BY DATE_TRUNC('month', order_date)
            ORDER BY month
        """
    }
    
    async with aiohttp.ClientSession() as session:
        for query_name, sql in queries.items():
            print(f"\n=== Executing {query_name} ===")
            
            success, result = await engine.execute_sql(
                sql=sql,
                session=session,
                dry_run=False,
                limit=100
            )
            
            if success:
                print(f"✓ Query returned {result['row_count']} rows")
                print(f"Columns: {result['columns']}")
                
                # Convert to pandas DataFrame for analysis
                df = pd.DataFrame(result['data'])
                print("\nSample data:")
                print(df.head())
                
                # Example analysis
                if 'avg_spent' in df.columns:
                    print(f"\nSpending analysis:")
                    print(f"Highest spending segment: {df.loc[df['avg_spent'].idxmax(), 'customer_segment']}")
                    print(f"Average spending: ${df['avg_spent'].mean():.2f}")
                
            else:
                print(f"✗ Query failed: {result.get('error')}")
    
    # Get cluster information
    cluster_info = engine.get_cluster_info()
    print(f"\nCluster info: {cluster_info}")
    
    # Cleanup
    engine.cleanup()

# ============================================================================
# 2. Open Source Trino Connection
# ============================================================================

async def example_trino_open_source():
    """Connection to open-source Trino cluster"""
    
    engine = StarburstEngineConfig.for_trino_cluster(
        host='trino.company.com',
        user='analyst',
        catalog='hive',
        schema='warehouse',
        port=8080,
        http_scheme='http',
        session_properties={
            'query_max_memory': '1GB'
        }
    )
    
    # Explore the cluster
    catalogs = engine.get_available_catalogs()
    print(f"Available catalogs: {catalogs}")
    
    schemas = engine.get_available_schemas('hive')
    print(f"Available schemas in 'hive': {schemas}")
    
    tables = engine.get_available_tables('hive', 'warehouse')
    print(f"Available tables in 'hive.warehouse': {tables}")
    
    # Get table information
    if tables:
        table_info = engine.get_table_info(tables[0], 'hive', 'warehouse')
        print(f"\nTable info for {tables[0]}: {table_info}")
    
    engine.cleanup()

# ============================================================================
# 3. JWT Authentication
# ============================================================================

async def example_jwt_authentication():
    """JWT authentication example"""
    
    # JWT token (in practice, obtain this from your OAuth provider)
    jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    
    engine = StarburstEngineConfig.for_jwt_auth(
        host='secure-cluster.starburst.io',
        user='service-account',
        catalog='secure_data',
        jwt_token=jwt_token,
        schema='production',
        session_properties={
            'query_max_run_time': '30m'
        }
    )
    
    # Example secure query
    sql = """
    SELECT 
        anonymized_user_id,
        action_type,
        timestamp,
        session_id
    FROM secure_data.production.user_events
    WHERE DATE(timestamp) = CURRENT_DATE
    LIMIT 1000
    """
    
    async with aiohttp.ClientSession() as session:
        success, result = await engine.execute_sql(
            sql=sql,
            session=session,
            dry_run=False
        )
        
        if success:
            print(f"Secure query returned {result['row_count']} rows")
        else:
            print(f"Secure query failed: {result.get('error')}")
    
    engine.cleanup()

# ============================================================================
# 4. Batch Processing for Large Datasets
# ============================================================================

async def example_batch_processing():
    """Process large datasets in batches"""
    
    engine = StarburstEngineConfig.for_starburst_cloud(
        cluster_url='https://your-cluster.starburst.io',
        username='your-email@company.com',
        password='your-password',
        catalog='datalake',
        schema='raw_data'
    )
    
    # Large dataset query
    large_query = """
    SELECT 
        user_id,
        event_timestamp,
        event_type,
        properties
    FROM datalake.raw_data.user_events
    WHERE DATE(event_timestamp) >= DATE '2024-01-01'
      AND DATE(event_timestamp) <= DATE '2024-03-31'
    """
    
    async with aiohttp.ClientSession() as session:
        # Process in batches of 5000 rows
        batch_size = 5000
        batch_num = 0
        all_data = []
        
        while True:
            print(f"Processing batch {batch_num}...")
            
            success, result = await engine.execute_sql_in_batches(
                sql=large_query,
                session=session,
                batch_size=batch_size,
                batch_num=batch_num,
                dry_run=False
            )
            
            if not success:
                print(f"Batch {batch_num} failed: {result.get('error')}")
                break
            
            batch_data = result.get('data', [])
            if not batch_data:
                print("No more data to process")
                break
            
            all_data.extend(batch_data)
            
            # Check if this is the last batch
            if result.get('batch_info', {}).get('is_last_batch', False):
                print("Reached last batch")
                break
            
            batch_num += 1
            
            # Safety limit for demo
            if batch_num >= 10:
                print("Reached batch limit for demo")
                break
        
        print(f"Total rows processed: {len(all_data)}")
        
        # Convert to DataFrame for analysis
        if all_data:
            df = pd.DataFrame(all_data)
            print("\nData analysis:")
            print(f"Date range: {df['event_timestamp'].min()} to {df['event_timestamp'].max()}")
            print(f"Unique users: {df['user_id'].nunique()}")
            print(f"Event types: {df['event_type'].value_counts().to_dict()}")
    
    engine.cleanup()

# ============================================================================
# 5. Advanced Configuration with Session Properties
# ============================================================================

async def example_advanced_configuration():
    """Advanced configuration with custom session properties"""
    
    engine = StarburstPandasEngine(
        host='advanced-cluster.starburst.io',
        user='data-scientist',
        catalog='warehouse',
        schema='analytics',
        port=443,
        auth_type='basic',
        username='data-scientist',
        password='secure-password',
        http_scheme='https',
        verify=True,
        request_timeout=60,
        session_properties={
            # Memory and performance settings
            'query_max_memory': '8GB',
            'query_max_memory_per_node': '2GB',
            'query_max_run_time': '2h',
            'query_max_execution_time': '90m',
            
            # Join and aggregation settings
            'join_distribution_type': 'BROADCAST',
            'join_reordering_strategy': 'AUTOMATIC',
            'aggregation_operator_unspill_memory_limit': '4MB',
            
            # Spilling settings
            'spill_enabled': 'true',
            'spill_order_by': 'true',
            'spill_window_operator': 'true',
            
            # Optimization settings
            'optimize_hash_generation': 'true',
            'push_table_write_through_union': 'true',
            'task_concurrency': '16',
            
            # Security settings
            'legacy_timestamp': 'false',
            'parse_decimal_literals_as_double': 'false'
        },
        client_info='advanced-analytics-pipeline',
        client_tags=['ml-training', 'heavy-compute'],
        roles={'warehouse': 'admin'},
        timezone='UTC',
        use_sqlalchemy=True,  # Use SQLAlchemy for connection pooling
        cache_ttl=1800  # 30-minute cache
    )
    
    # Complex analytical query
    complex_query = """
    WITH customer_metrics AS (
        SELECT 
            c.customer_id,
            c.customer_segment,
            c.registration_date,
            COUNT(o.order_id) as total_orders,
            SUM(o.amount) as total_spent,
            AVG(o.amount) as avg_order_value,
            MAX(o.order_date) as last_order_date,
            MIN(o.order_date) as first_order_date
        FROM warehouse.analytics.customers c
        LEFT JOIN warehouse.analytics.orders o ON c.customer_id = o.customer_id
        WHERE c.registration_date >= DATE '2023-01-01'
        GROUP BY c.customer_id, c.customer_segment, c.registration_date
    ),
    customer_segments AS (
        SELECT 
            *,
            CASE 
                WHEN total_spent >= 10000 THEN 'VIP'
                WHEN total_spent >= 5000 THEN 'Premium'
                WHEN total_spent >= 1000 THEN 'Regular'
                ELSE 'Basic'
            END as spending_tier,
            DATE_DIFF('day', first_order_date, last_order_date) as customer_lifespan_days
        FROM customer_metrics
    )
    SELECT 
        customer_segment,
        spending_tier,
        COUNT(*) as customer_count,
        AVG(total_spent) as avg_total_spent,
        AVG(total_orders) as avg_total_orders,
        AVG(avg_order_value) as avg_order_value,
        AVG(customer_lifespan_days) as avg_lifespan_days,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total_spent) as median_spent,
        PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY total_spent) as p90_spent
    FROM customer_segments
    GROUP BY customer_segment, spending_tier
    ORDER BY customer_segment, spending_tier
    """
    
    async with aiohttp.ClientSession() as session:
        print("Executing complex analytical query...")
        
        success, result = await engine.execute_sql(
            sql=complex_query,
            session=session,
            dry_run=False,
            use_cache=True
        )
        
        if success:
            print(f"✓ Analysis complete: {result['row_count']} segments analyzed")
            
            # Convert to DataFrame and perform additional analysis
            df = pd.DataFrame(result['data'])
            
            print("\nCustomer Segment Analysis:")
            print("=" * 50)
            
            for segment in df['customer_segment'].unique():
                segment_data = df[df['customer_segment'] == segment]
                print(f"\n{segment.upper()} Segment:")
                print(f"  Total customers: {segment_data['customer_count'].sum():,}")
                print(f"  Avg spending: ${segment_data['avg_total_spent'].mean():.2f}")
                print(f"  Avg orders: {segment_data['avg_total_orders'].mean():.1f}")
                print(f"  Avg lifespan: {segment_data['avg_lifespan_days'].mean():.0f} days")
            
            # Cache statistics
            cache_stats = engine.get_cache_stats()
            print(f"\nCache statistics: {cache_stats}")
            
        else:
            print(f"✗ Query failed: {result.get('error')}")
    
    engine.cleanup()

# ============================================================================
# 6. Hybrid Analysis with Local Data
# ============================================================================

async def example_hybrid_local_remote():
    """Combine remote Starburst data with local pandas DataFrames"""
    
    # Create some local data
    local_enrichment_data = pd.DataFrame({
        'customer_segment': ['enterprise', 'mid_market', 'smb'],
        'segment_priority': [1, 2, 3],
        'account_manager': ['Alice Johnson', 'Bob Smith', 'Carol Davis'],
        'target_growth_rate': [0.15, 0.25, 0.35]
    })
    
    # Create engine with local data
    engine = StarburstEngineConfig.for_starburst_cloud(
        cluster_url='https://your-cluster.starburst.io',
        username='your-email@company.com',
        password='your-password',
        catalog='sales',
        schema='reporting'
    )
    
    # Add local data to engine
    engine.add_local_data_source('segment_enrichment', local_enrichment_data)
    
    # Query remote data
    remote_query = """
    SELECT 
        customer_segment,
        COUNT(*) as customer_count,
        SUM(annual_revenue) as total_revenue,
        AVG(annual_revenue) as avg_revenue
    FROM sales.reporting.accounts
    WHERE status = 'active'
    GROUP BY customer_segment
    """
    
    async with aiohttp.ClientSession() as session:
        # Get remote data
        success, result = await engine.execute_sql(
            sql=remote_query,
            session=session,
            dry_run=False
        )
        
        if success:
            # Convert to DataFrame
            remote_df = pd.DataFrame(result['data'])
            
            # Merge with local enrichment data
            enriched_df = remote_df.merge(
                local_enrichment_data,
                on='customer_segment',
                how='left'
            )
            
            # Calculate insights
            enriched_df['revenue_per_customer'] = enriched_df['total_revenue'] / enriched_df['customer_count']
            enriched_df['target_new_revenue'] = enriched_df['total_revenue'] * enriched_df['target_growth_rate']
            
            print("Hybrid Analysis Results:")
            print("=" * 40)
            print(enriched_df.to_string(index=False))
            
            # Priority recommendations
            print("\nAccount Manager Assignments:")
            for _, row in enriched_df.iterrows():
                print(f"{row['customer_segment'].title()}: {row['account_manager']} "
                      f"(Target: +${row['target_new_revenue']:,.0f})")
    
    engine.cleanup()

# ============================================================================
# 7. Error Handling and Monitoring
# ============================================================================

async def example_error_handling_monitoring():
    """Demonstrate error handling and monitoring capabilities"""
    
    engine = StarburstEngineConfig.for_starburst_cloud(
        cluster_url='https://your-cluster.starburst.io',
        username='your-email@company.com',
        password='your-password',
        catalog='monitoring',
        schema='logs',
        request_timeout=10,  # Short timeout for demo
        session_properties={
            'query_max_run_time': '30s'  # Short limit for demo
        }
    )
    
    test_queries = [
        ("valid_query", "SELECT 1 as test_value"),
        ("syntax_error", "SELECT * FORM invalid_table"),  # Intentional syntax error
        ("timeout_query", "SELECT COUNT(*) FROM system.runtime.queries WHERE query_id IS NOT NULL"),  # May timeout
        ("missing_table", "SELECT * FROM non_existent_table"),
        ("permission_error", "SELECT * FROM restricted.secret.data")  # May have permission issues
    ]
    
    async with aiohttp.ClientSession() as session:
        results = {}
        
        for query_name, sql in test_queries:
            print(f"\nTesting: {query_name}")
            
            try:
                success, result = await engine.execute_sql(
                    sql=sql,
                    session=session,
                    dry_run=False,
                    limit=10
                )
                
                if success:
                    print(f"✓ Success: {result['row_count']} rows")
                    results[query_name] = 'success'
                else:
                    print(f"✗ Failed: {result.get('error', 'Unknown error')}")
                    results[query_name] = 'failed'
                    
            except asyncio.TimeoutError:
                print(f"⏱ Timeout: Query exceeded time limit")
                results[query_name] = 'timeout'
            except Exception as e:
                print(f"💥 Exception: {str(e)}")
                results[query_name] = 'exception'
        
        # Summary
        print(f"\nTest Results Summary:")
        print("=" * 30)
        for query_name, status in results.items():
            status_emoji = {'success': '✓', 'failed': '✗', 'timeout': '⏱', 'exception': '💥'}
            print(f"{status_emoji.get(status, '?')} {query_name}: {status}")
    
    engine.cleanup()

# ============================================================================
# Main execution function
# ============================================================================

async def main():
    """Run all examples"""
    examples = [
        ("Starburst Cloud Basic", example_starburst_cloud_basic),
        ("Trino Open Source", example_trino_open_source),
        ("JWT Authentication", example_jwt_authentication),
        ("Batch Processing", example_batch_processing),
        ("Advanced Configuration", example_advanced_configuration),
        ("Hybrid Local/Remote", example_hybrid_local_remote),
        ("Error Handling", example_error_handling_monitoring)
    ]
    
    for name, example_func in examples:
        print(f"\n{'='*60}")
        print(f"Running Example: {name}")
        print(f"{'='*60}")
        
        try:
            await example_func()
        except Exception as e:
            print(f"Example failed: {e}")
            logger.exception(f"Error in {name}")
        
        print(f"\nCompleted: {name}")

if __name__ == "__main__":
    # Run examples
    print("StarburstPandasEngine Examples")
    print("=" * 60)
    
    # Note: Update connection details before running
    print("📝 Remember to update connection details (host, credentials) before running!")
    print("🔧 Install dependencies: pip install trino pandas aiohttp sqlalchemy")
    
    # Uncomment to run examples
    # asyncio.run(main())
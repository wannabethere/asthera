#!/usr/bin/env python3
"""
Example demonstrating the integration of PandasEngine with ML pipeline analysis.

This example shows how to:
1. Use PandasEngine to load and query data from various sources
2. Integrate with the analyze_question_with_intent_classification function
3. Create a unified workflow from data loading to ML analysis
"""

import pandas as pd
import asyncio
import os
import sys
from pathlib import Path

# Add the insightsagents path to sys.path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from agents.app.core.pandas_engine import PandasEngine, PandasEngineConfig
from tests.mlagents.funnelanalysistoolusage import analyze_question_with_intent_classification


def create_sample_financial_data():
    """Create sample financial data for demonstration"""
    import numpy as np
    from datetime import datetime, timedelta
    
    # Generate sample dates
    start_date = datetime(2024, 1, 1)
    dates = [start_date + timedelta(days=i) for i in range(365)]
    
    # Sample data
    np.random.seed(42)
    n_records = 1000
    
    data = {
        'Date': np.random.choice(dates, n_records),
        'Region': np.random.choice(['North', 'South', 'East', 'West'], n_records),
        'Project': np.random.choice(['Project A', 'Project B', 'Project C', 'Project D', None], n_records),
        'Cost_Center': np.random.choice(['Center A', 'Center B', 'Center C'], n_records),
        'Department': np.random.choice(['Engineering', 'Sales', 'Marketing', 'Finance'], n_records),
        'Source': np.random.choice(['PROJECT_ACCOUNTING', 'PAYABLES', 'REVALUATION', 'SPREADSHEET'], n_records),
        'Category': np.random.choice(['MISCELLANEOUS_COST', 'PURCHASE_INVOICES', 'ACCRUAL', 'REVALUE_PROFIT_LOSS'], n_records),
        'Transactional_Value': np.random.uniform(100, 10000, n_records),
        'Functional_Value': np.random.uniform(100, 10000, n_records),
        'Forecasted_Value': np.random.uniform(100, 10000, n_records),
        'PO_Number': [f'NEW_PO_{np.random.randint(1000, 9999)}' for _ in range(n_records)]
    }
    
    df = pd.DataFrame(data)
    
    # Add some missing values to make it realistic
    df.loc[np.random.choice(df.index, size=50), 'Project'] = None
    df.loc[np.random.choice(df.index, size=30), 'Transactional_Value'] = None
    
    return df


def demonstrate_pandas_engine_integration():
    """Demonstrate the integration of PandasEngine with ML pipeline analysis"""
    
    print("🚀 PandasEngine + ML Pipeline Integration Example")
    print("=" * 60)
    
    # Step 1: Create sample data
    print("\n📊 Step 1: Creating sample financial data...")
    financial_df = create_sample_financial_data()
    print(f"✅ Created dataset with {len(financial_df)} records")
    print(f"📋 Columns: {list(financial_df.columns)}")
    print(f"📈 Shape: {financial_df.shape}")
    
    # Step 2: Initialize PandasEngine with the data
    print("\n🔧 Step 2: Initializing PandasEngine...")
    engine = PandasEngineConfig.from_dataframes({
        'financial_data': financial_df
    })
    print("✅ PandasEngine initialized successfully")
    
    # Step 3: Demonstrate SQL queries on the data
    print("\n🔍 Step 3: Demonstrating SQL queries on the data...")
    
    # Query 1: Basic aggregation
    print("\n   Query 1: Daily transactional value by region")
    sql1 = """
    SELECT Date, Region, AVG(Transactional_Value) as avg_value, COUNT(*) as count
    FROM financial_data 
    WHERE Transactional_Value IS NOT NULL
    GROUP BY Date, Region
    ORDER BY Date, Region
    LIMIT 10
    """
    
    success, result1 = asyncio.run(engine.execute_sql(sql1, None, dry_run=False))
    if success:
        print(f"   ✅ Query executed successfully")
        print(f"   📊 Results: {result1['row_count']} rows")
        print(f"   🔍 First few results:")
        for i, row in enumerate(result1['data'][:3]):
            print(f"      {row}")
    else:
        print(f"   ❌ Query failed: {result1.get('error', 'Unknown error')}")
    
    # Query 2: Complex analysis
    print("\n   Query 2: Project performance analysis")
    sql2 = """
    SELECT 
        Project,
        Region,
        AVG(Transactional_Value) as avg_transactional,
        AVG(Forecasted_Value) as avg_forecasted,
        COUNT(*) as transaction_count
    FROM financial_data 
    WHERE Project IS NOT NULL 
    AND Transactional_Value IS NOT NULL
    GROUP BY Project, Region
    ORDER BY avg_transactional DESC
    LIMIT 10
    """
    
    success, result2 = asyncio.run(engine.execute_sql(sql2, None, dry_run=False))
    if success:
        print(f"   ✅ Query executed successfully")
        print(f"   📊 Results: {result2['row_count']} rows")
        print(f"   🔍 First few results:")
        for i, row in enumerate(result2['data'][:3]):
            print(f"      {row}")
    else:
        print(f"   ❌ Query failed: {result2.get('error', 'Unknown error')}")
    
    # Step 4: Integrate with ML pipeline analysis
    print("\n🤖 Step 4: Integrating with ML pipeline analysis...")
    
    # Define column descriptions for the ML analysis
    columns_description = {
        "Date": "Transaction date in YYYY-MM-DD format",
        "Region": "Geographic region where the transaction occurred",
        "Project": "Project identifier or project number",
        "Cost_Center": "Organizational cost center identifier",
        "Department": "Department responsible for the transaction",
        "Source": "Source system that generated the transaction",
        "Category": "Transaction category or type",
        "Transactional_Value": "Original transaction amount in transaction currency",
        "Functional_Value": "Transaction amount in functional currency",
        "Forecasted_Value": "Forecasted transaction amount",
        "PO_Number": "Purchase Order number identifier"
    }
    
    # Example 1: Analyze daily trends
    print("\n   📈 Example 1: Analyzing daily trends of transactional values...")
    question1 = "What are the daily trends of transactional values by region and project?"
    
    try:
        analysis_result1 = analyze_question_with_intent_classification(
            question=question1,
            dataframe=financial_df,
            dataframe_description="Financial transaction data with project, cost center, and department information",
            dataframe_summary="Dataset contains financial transactions over time with grouping dimensions for analysis",
            columns_description=columns_description,
            enable_code_generation=True,
            context="Analyze daily trends in transactional values to understand spending patterns",
            dataframe_name="financial_data"
        )
        
        print(f"   ✅ Analysis completed successfully")
        print(f"   🎯 Intent classification: {analysis_result1['intent_classification'].can_be_answered}")
        if 'generated_code' in analysis_result1:
            print(f"   💻 Code generated: {len(analysis_result1['generated_code'])} characters")
        else:
            print(f"   ⚠️  No code generated")
            
    except Exception as e:
        print(f"   ❌ Analysis failed: {str(e)}")
    
    # Example 2: Anomaly detection
    print("\n   🔍 Example 2: Detecting anomalies in spending patterns...")
    question2 = "Find anomalies in daily spending patterns that deviate from normal business patterns by region and project"
    
    try:
        analysis_result2 = analyze_question_with_intent_classification(
            question=question2,
            dataframe=financial_df,
            dataframe_description="Financial transaction data with project, cost center, and department information",
            dataframe_summary="Dataset contains financial transactions over time with grouping dimensions for analysis",
            columns_description=columns_description,
            enable_code_generation=True,
            context="Detect unusual spending patterns for fraud detection and budget monitoring",
            dataframe_name="financial_data"
        )
        
        print(f"   ✅ Analysis completed successfully")
        print(f"   🎯 Intent classification: {analysis_result2['intent_classification'].can_be_answered}")
        if 'generated_code' in analysis_result2:
            print(f"   💻 Code generated: {len(analysis_result2['generated_code'])} characters")
        else:
            print(f"   ⚠️  No code generated")
            
    except Exception as e:
        print(f"   ❌ Analysis failed: {str(e)}")
    
    # Example 3: Distribution analysis
    print("\n   📊 Example 3: Analyzing distribution of transactional values...")
    question3 = "What is the distribution of transactional values for each source by region and project?"
    
    try:
        analysis_result3 = analyze_question_with_intent_classification(
            question=question3,
            dataframe=financial_df,
            dataframe_description="Financial transaction data with project, cost center, and department information",
            dataframe_summary="Dataset contains financial transactions over time with grouping dimensions for analysis",
            columns_description=columns_description,
            enable_code_generation=True,
            context="Understand the distribution of transaction values across different sources and dimensions",
            dataframe_name="financial_data"
        )
        
        print(f"   ✅ Analysis completed successfully")
        print(f"   🎯 Intent classification: {analysis_result3['intent_classification'].can_be_answered}")
        if 'generated_code' in analysis_result3:
            print(f"   💻 Code generated: {len(analysis_result3['generated_code'])} characters")
        else:
            print(f"   ⚠️  No code generated")
            
    except Exception as e:
        print(f"   ❌ Analysis failed: {str(e)}")
    
    # Step 5: Demonstrate advanced PandasEngine features
    print("\n⚡ Step 5: Demonstrating advanced PandasEngine features...")
    
    # Batch processing
    print("\n   📦 Batch processing example:")
    sql_batch = "SELECT * FROM financial_data WHERE Region = 'North'"
    
    success, batch_result = asyncio.run(engine.execute_sql_in_batches(
        sql_batch, 
        None, 
        batch_size=100, 
        max_batches=3,
        dry_run=False
    ))
    
    if success:
        print(f"   ✅ Batch processing completed")
        print(f"   📊 Total rows processed: {batch_result['total_count']}")
        print(f"   🔢 Batches processed: {batch_result['batches_processed']}")
        print(f"   📏 Batch size: {batch_result['batch_size']}")
    else:
        print(f"   ❌ Batch processing failed: {batch_result.get('error', 'Unknown error')}")
    
    # Cache statistics
    print("\n   💾 Cache statistics:")
    cache_stats = engine.get_cache_stats()
    for key, value in cache_stats.items():
        print(f"      {key}: {value}")
    
    # Table information
    print("\n   📋 Table information:")
    table_info = engine.get_table_info('financial_data')
    if 'error' not in table_info:
        print(f"      Table: {table_info['name']}")
        print(f"      Source: {table_info['source']}")
        print(f"      Rows: {table_info['row_count']}")
        print(f"      Columns: {len(table_info['columns'])}")
    else:
        print(f"      ❌ Could not get table info: {table_info['error']}")
    
    # Available tables
    print("\n   🗂️  Available tables:")
    tables = engine.get_available_tables()
    for table in tables:
        print(f"      - {table}")
    
    # Step 6: Cleanup
    print("\n🧹 Step 6: Cleaning up resources...")
    engine.cleanup()
    print("✅ Resources cleaned up successfully")
    
    print("\n🎉 Integration demonstration completed successfully!")
    print("=" * 60)


def demonstrate_postgres_integration():
    """Demonstrate PandasEngine with PostgreSQL integration"""
    
    print("\n🐘 PostgreSQL Integration Example")
    print("=" * 40)
    
    # Note: This requires actual PostgreSQL credentials
    print("⚠️  Note: This example requires actual PostgreSQL credentials")
    print("   To use this feature, you would configure it like this:")
    
    postgres_config = {
        'host': 'your-postgres-host.com',
        'port': 5432,
        'database': 'your_database',
        'username': 'your_username',
        'password': 'your_password'
    }
    
    print(f"   postgres_config = {postgres_config}")
    
    # Example configuration
    print("\n   Example configuration:")
    print("   engine = PandasEngineConfig.from_postgres(")
    print("       host='localhost',")
    print("       database='financial_db',")
    print("       username='analytics_user',")
    print("       password='secure_password'")
    print("   )")
    
    print("\n   This would allow you to:")
    print("   - Query PostgreSQL databases directly")
    print("   - Use the same ML pipeline analysis on database data")
    print("   - Combine local DataFrames with database tables")
    print("   - Cache query results for performance")


def demonstrate_mixed_sources():
    """Demonstrate PandasEngine with mixed data sources"""
    
    print("\n🔀 Mixed Data Sources Example")
    print("=" * 40)
    
    # Create sample CSV data
    print("📊 Creating sample CSV data...")
    sample_csv_data = pd.DataFrame({
        'customer_id': range(1, 101),
        'customer_name': [f'Customer_{i}' for i in range(1, 101)],
        'segment': ['Premium', 'Standard', 'Basic'] * 33 + ['Premium'],
        'lifetime_value': [1000 + i * 10 for i in range(100)]
    })
    
    csv_path = "sample_customers.csv"
    sample_csv_data.to_csv(csv_path, index=False)
    print(f"✅ Created {csv_path}")
    
    # Create sample Excel data
    print("📊 Creating sample Excel data...")
    sample_excel_data = pd.DataFrame({
        'product_id': range(1, 51),
        'product_name': [f'Product_{i}' for i in range(1, 51)],
        'category': ['Electronics', 'Clothing', 'Books'] * 16 + ['Electronics', 'Clothing'],
        'price': [50 + i * 2 for i in range(50)]
    })
    
    excel_path = "sample_products.xlsx"
    sample_excel_data.to_excel(excel_path, index=False)
    print(f"✅ Created {excel_path}")
    
    # Initialize engine with mixed sources
    print("🔧 Initializing engine with mixed sources...")
    engine = PandasEngineConfig.from_mixed_sources(
        dataframes={'financial_data': create_sample_financial_data()},
        csv_files={'customers': csv_path},
        excel_file=excel_path,
        excel_sheet_mapping={'products': 'Sheet1'}
    )
    
    print("✅ Engine initialized with mixed sources")
    
    # Query across multiple sources
    print("\n🔍 Querying across multiple data sources...")
    
    # Get available tables
    tables = engine.get_available_tables()
    print(f"📋 Available tables: {tables}")
    
    # Query customers
    print("\n   Querying customer data:")
    customer_sql = "SELECT segment, COUNT(*) as count, AVG(lifetime_value) as avg_value FROM customers GROUP BY segment"
    success, customer_result = asyncio.run(engine.execute_sql(customer_sql, None, dry_run=False))
    
    if success:
        print(f"   ✅ Customer query successful: {customer_result['row_count']} rows")
        for row in customer_result['data']:
            print(f"      {row}")
    else:
        print(f"   ❌ Customer query failed: {customer_result.get('error', 'Unknown error')}")
    
    # Query products
    print("\n   Querying product data:")
    product_sql = "SELECT category, COUNT(*) as count, AVG(price) as avg_price FROM products GROUP BY category"
    success, product_result = asyncio.run(engine.execute_sql(product_sql, None, dry_run=False))
    
    if success:
        print(f"   ✅ Product query successful: {product_result['row_count']} rows")
        for row in product_result['data']:
            print(f"      {row}")
    else:
        print(f"   ❌ Product query failed: {product_result.get('error', 'Unknown error')}")
    
    # Cleanup
    print("\n🧹 Cleaning up temporary files...")
    engine.cleanup()
    
    # Remove temporary files
    if os.path.exists(csv_path):
        os.remove(csv_path)
    if os.path.exists(excel_path):
        os.remove(excel_path)
    
    print("✅ Temporary files cleaned up")


def main():
    """Main function to run all demonstrations"""
    
    try:
        # Main integration demonstration
        demonstrate_pandas_engine_integration()
        
        # PostgreSQL integration example
        demonstrate_postgres_integration()
        
        # Mixed sources demonstration
        demonstrate_mixed_sources()
        
        print("\n🎯 Summary of Integration Benefits:")
        print("=" * 50)
        print("✅ PandasEngine provides unified SQL interface to multiple data sources")
        print("✅ ML pipeline analysis works seamlessly with engine data")
        print("✅ Caching improves performance for repeated queries")
        print("✅ Batch processing handles large datasets efficiently")
        print("✅ Mixed data sources enable comprehensive analysis")
        print("✅ PostgreSQL integration for enterprise data access")
        print("✅ Easy deployment with generated executable code")
        
        print("\n🚀 Next Steps:")
        print("=" * 30)
        print("1. Customize the data loading functions for your data sources")
        print("2. Integrate with your existing ML pipeline tools")
        print("3. Deploy the generated code to production environments")
        print("4. Add more data source connectors as needed")
        
    except Exception as e:
        print(f"\n❌ Error during demonstration: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

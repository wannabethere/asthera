#!/usr/bin/env python3
"""
Example usage of the QueryExecutor.
This script demonstrates various ways to use the QueryExecutor class.
"""

from query_executor import QueryExecutor


def example_basic_usage():
    """Example 1: Basic usage with default settings."""
    print("📝 Example 1: Basic Usage")
    print("=" * 50)
    
    executor = QueryExecutor()
    
    # Simple query
    query = """
    SELECT 
        user_id,
        username,
        email,
        created_at
    FROM users 
    WHERE active = true 
    ORDER BY created_at DESC
    """
    
    # Generate PostgreSQL executor
    output_file = executor.generate_executable_code(query, "postgres")
    print(f"✅ Generated: {output_file}")
    print(f"🐍 Run with: python {output_file}")
    print()


def example_with_connection_config():
    """Example 2: Using connection configuration."""
    print("📝 Example 2: With Connection Configuration")
    print("=" * 50)
    
    executor = QueryExecutor()
    
    # Connection configuration
    config = {
        "host": "analytics.company.com",
        "port": 5432,
        "database": "analytics_db",
        "user": "data_analyst",
        "password": "secure_password_123"
    }
    
    # Analytics query
    query = """
    SELECT 
        DATE_TRUNC('month', order_date) as month,
        COUNT(*) as total_orders,
        SUM(order_amount) as total_revenue,
        AVG(order_amount) as avg_order_value
    FROM orders 
    WHERE order_date >= '2024-01-01'
    GROUP BY DATE_TRUNC('month', order_date)
    ORDER BY month
    """
    
    # Generate with config
    output_file = executor.generate_executable_code(
        query, "postgres", connection_config=config
    )
    print(f"✅ Generated: {output_file}")
    print(f"🔗 Database: {config['host']}:{config['port']}/{config['database']}")
    print(f"👤 User: {config['user']}")
    print()


def example_trino_executor():
    """Example 3: Generating Trino executor."""
    print("📝 Example 3: Trino Executor")
    print("=" * 50)
    
    executor = QueryExecutor()
    
    # Trino query
    query = """
    SELECT 
        customer_id,
        customer_name,
        COUNT(*) as transaction_count,
        SUM(amount) as total_amount
    FROM hive.default.transactions 
    WHERE transaction_date >= CURRENT_DATE - INTERVAL '30' DAY
    GROUP BY customer_id, customer_name
    HAVING COUNT(*) > 5
    ORDER BY total_amount DESC
    LIMIT 100
    """
    
    # Generate Trino executor
    output_file = executor.generate_executable_code(query, "trino")
    print(f"✅ Generated: {output_file}")
    print(f"🔍 Query type: Trino")
    print(f"📊 Data source: hive.default.transactions")
    print()


def example_deployment_package():
    """Example 4: Generating deployment package."""
    print("📝 Example 4: Deployment Package")
    print("=" * 50)
    
    executor = QueryExecutor()
    
    # Production query
    query = """
    SELECT 
        product_id,
        product_name,
        category,
        SUM(quantity_sold) as total_quantity,
        SUM(revenue) as total_revenue,
        AVG(unit_price) as avg_unit_price
    FROM sales_facts sf
    JOIN products p ON sf.product_id = p.id
    JOIN categories c ON p.category_id = c.id
    WHERE sf.sale_date >= '2024-01-01'
    GROUP BY product_id, product_name, category
    ORDER BY total_revenue DESC
    """
    
    # Connection config for production
    config = {
        "host": "prod-data-warehouse.company.com",
        "port": 5432,
        "database": "data_warehouse",
        "user": "etl_user",
        "password": "etl_password_456"
    }
    
    # Generate deployment package
    package_dir = executor.generate_deployment_package(
        query, "postgres", connection_config=config
    )
    print(f"✅ Deployment package generated: {package_dir}")
    print(f"📦 Package contents:")
    print(f"   - main.py (executable)")
    print(f"   - requirements.txt (dependencies)")
    print(f"   - README.md (documentation)")
    print(f"   - deploy.sh (deployment script)")
    print(f"🚀 Deploy with: cd {package_dir} && ./deploy.sh")
    print()


def example_batch_generation():
    """Example 5: Batch generation of multiple executors."""
    print("📝 Example 5: Batch Generation")
    print("=" * 50)
    
    executor = QueryExecutor()
    
    # Multiple queries for different purposes
    queries = {
        "user_analytics": """
            SELECT 
                user_id,
                registration_date,
                last_login_date,
                total_logins,
                is_premium
            FROM user_analytics 
            WHERE registration_date >= '2024-01-01'
        """,
        
        "sales_performance": """
            SELECT 
                sales_rep_id,
                sales_rep_name,
                territory,
                total_sales,
                commission_earned
            FROM sales_performance 
            WHERE year = 2024
        """,
        
        "inventory_status": """
            SELECT 
                product_id,
                product_name,
                current_stock,
                reorder_level,
                supplier_name
            FROM inventory 
            WHERE current_stock <= reorder_level
        """
    }
    
    # Generate executors for each query
    generated_files = {}
    for name, query in queries.items():
        output_file = executor.generate_executable_code(
            query, "postgres", 
            output_file=f"{name}_executor.py"
        )
        generated_files[name] = output_file
        print(f"✅ {name}: {output_file}")
    
    print(f"\n📊 Generated {len(generated_files)} executors")
    print("🚀 All ready for deployment!")
    print()


def main():
    """Run all examples."""
    print("🚀 QueryExecutor Examples")
    print("=" * 60)
    print()
    
    examples = [
        example_basic_usage,
        example_with_connection_config,
        example_trino_executor,
        example_deployment_package,
        example_batch_generation
    ]
    
    for example in examples:
        example()
        print("-" * 60)
        print()
    
    print("🎉 All examples completed!")
    print("\n💡 Tips:")
    print("   - Use --help with cli.py to see all command-line options")
    print("   - Check the README.md for detailed documentation")
    print("   - Run test_executor.py to verify functionality")
    print("   - Customize templates for your specific needs")


if __name__ == "__main__":
    main()

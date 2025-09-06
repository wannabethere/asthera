"""
Template registry and usage examples for the Jinja-based template system.
"""

from typing import Dict, Type
from pathlib import Path
from app.executor.base_template import BaseTemplate
from app.executor.jinja_template_manager import template_manager,create_executable, preview_template
from app.executor.templates.trino_jinja_template import TrinoTemplate
from app.executor.templates.postgres_jinja_template import PostgreSQLTemplate


# Template Registry - Import and register all available templates
TEMPLATE_REGISTRY: Dict[str, Type[BaseTemplate]] = {}

try:
    TEMPLATE_REGISTRY["trino"] = TrinoTemplate
except ImportError:
    pass

try:
    TEMPLATE_REGISTRY["postgresql"] = PostgreSQLTemplate
except ImportError:
    pass

# You can add more templates here as they are developed
# try:
#     from .mysql_template import MySQLTemplate
#     TEMPLATE_REGISTRY["mysql"] = MySQLTemplate
# except ImportError:
#     pass


def demo_usage():
    """Demonstrate how to use the Jinja template system."""
    
    
    print("🚀 Jinja Template System Demo")
    print("=" * 40)
    
    # List available templates
    print("\n📋 Available templates:")
    for template_name in template_manager.list_templates():
        print(f"  • {template_name}")
    
    # Get template information
    print("\n📊 Template Information:")
    for template_name in template_manager.list_templates():
        info = template_manager.get_template_info(template_name)
        if info:
            print(f"\n🔧 {template_name.upper()}:")
            print(f"  Dependencies: {', '.join(info['dependencies'])}")
            print(f"  Required params: {', '.join(info['connection_parameters'])}")
    
    # Demo 1: Generate Trino template
    print("\n" + "=" * 40)
    print("📝 Demo 1: Trino Template Generation")
    print("=" * 40)
    
    trino_config = {
        "host": "trino-cluster.example.com",
        "port": 8080,
        "catalog": "data_lake",
        "schema": "analytics", 
        "user": "analyst_user",
        "show_info": True,
        "debug": True
    }
    
    trino_query = """
    SELECT 
        customer_id,
        SUM(order_amount) as total_spent,
        COUNT(*) as order_count
    FROM orders 
    WHERE order_date >= date('2024-01-01')
    GROUP BY customer_id
    ORDER BY total_spent DESC
    LIMIT 10
    """
    
    try:
        trino_code = template_manager.create_executable("trino", trino_query, trino_config)
        print("✅ Generated Trino code:")
        print("-" * 40)
        print(trino_code[:500] + "..." if len(trino_code) > 500 else trino_code)
    except Exception as e:
        print(f"❌ Error generating Trino code: {e}")
    
    # Demo 2: Generate PostgreSQL template
    print("\n" + "=" * 40)
    print("📝 Demo 2: PostgreSQL Template Generation")  
    print("=" * 40)
    
    postgres_config = {
        "host": "postgres-prod.example.com",
        "port": 5432,
        "database": "ecommerce",
        "user": "readonly_user",
        "password": "secure_password123",
        "ssl_mode": "require",
        "connection_pool": True,
        "pool_size": 10,
        "test_connection": True,
        "show_info": True,
        "show_stats": True,
        "debug": False
    }
    
    postgres_query = """
    SELECT 
        p.product_name,
        c.category_name,
        AVG(r.rating) as avg_rating,
        COUNT(r.rating) as review_count,
        p.price
    FROM products p
    JOIN categories c ON p.category_id = c.id  
    LEFT JOIN reviews r ON p.id = r.product_id
    WHERE p.active = true
    GROUP BY p.id, p.product_name, c.category_name, p.price
    HAVING COUNT(r.rating) >= 5
    ORDER BY avg_rating DESC, review_count DESC
    LIMIT 20
    """
    
    try:
        postgres_code = template_manager.create_executable("postgresql", postgres_query, postgres_config)
        print("✅ Generated PostgreSQL code:")
        print("-" * 40) 
        print(postgres_code[:500] + "..." if len(postgres_code) > 500 else postgres_code)
    except Exception as e:
        print(f"❌ Error generating PostgreSQL code: {e}")
    
    # Demo 3: Export templates to files
    print("\n" + "=" * 40)
    print("📁 Demo 3: Export Templates to Files")
    print("=" * 40)
    
    output_dir = Path("generated_scripts")
    output_dir.mkdir(exist_ok=True)
    
    try:
        # Export Trino script
        trino_file = output_dir / "trino_analysis.py"
        template_manager.export_template("trino", trino_file, trino_query, trino_config)
        
        # Export PostgreSQL script  
        postgres_file = output_dir / "postgres_analysis.py"
        template_manager.export_template("postgresql", postgres_file, postgres_query, postgres_config)
        
        print(f"✅ Scripts exported to {output_dir}/")
        
    except Exception as e:
        print(f"❌ Error exporting templates: {e}")
    
    # Demo 4: Template validation and stats
    print("\n" + "=" * 40)
    print("🔍 Demo 4: Template Validation & Stats")
    print("=" * 40)
    
    # Validate templates
    for template_name in template_manager.list_templates():
        is_valid = template_manager.validate_template(template_name)
        status = "✅ Valid" if is_valid else "❌ Invalid"
        print(f"  {template_name}: {status}")
    
    # Show template stats
    stats = template_manager.get_template_stats()
    print(f"\n📊 Template Statistics:")
    print(f"  Total templates: {stats['total_templates']}")
    print(f"  Instantiated: {stats['instantiated_templates']}")
    print(f"  By dependency:")
    for dep, templates in stats['templates_by_type'].items():
        print(f"    {dep}: {', '.join(templates)}")


def create_custom_template_example():
    """Example of creating a custom template."""
    
    print("ℹ️ Skipping MySQL template creation as requested")
    print("This example demonstrates how to create custom templates when needed")
    
    # Example of what a custom template would look like:
    print("\n📝 Example custom template structure:")
    print("""
    class CustomTemplate(BaseTemplate):
        @property
        def data_source_name(self) -> str:
            return "custom_source"
        
        @property 
        def required_dependencies(self) -> List[str]:
            return ["pandas", "custom_library"]
        
        @property
        def connection_parameters(self) -> List[str]:
            return ["host", "port", "user", "password"]
        
        @property
        def query_placeholder(self) -> str:
            return "SELECT 1"
        
        @property
        def jinja_template_content(self) -> str:
            return 'your_jinja_template_content_here'
        
        def apply_connection_config(self, code: str, config: Dict) -> str:
            return code
    """)


def advanced_usage_examples():
    """Show advanced usage patterns."""
    
    
    print("\n🎯 Advanced Usage Examples")
    print("=" * 40)
    
    # Example 1: Using convenience functions
    print("\n1️⃣ Using convenience functions:")
    try:
        preview = preview_template("trino", "SHOW TABLES")
        print("Preview generated successfully!")
    except Exception as e:
        print(f"Error: {e}")
    
    # Example 2: Configuration validation
    print("\n2️⃣ Configuration validation:")
    invalid_config = {"host": "localhost"}  # Missing required fields
    
    try:
        template_manager.create_executable("postgresql", "SELECT 1", invalid_config)
    except ValueError as e:
        print(f"✅ Validation caught error: {e}")
    
    # Example 3: Template schema inspection
    print("\n3️⃣ Template schema inspection:")
    schema = template_manager.get_config_schema("postgresql")
    if schema:
        required_fields = schema.get("required", [])
        print(f"Required fields for PostgreSQL: {', '.join(required_fields)}")
    
    # Example 4: Batch processing
    print("\n4️⃣ Batch template generation:")
    queries = [
        "SELECT COUNT(*) FROM users",
        "SELECT AVG(order_amount) FROM orders",
        "SELECT MAX(created_at) FROM products"
    ]
    
    base_config = {
        "host": "localhost",
        "port": 5432,
        "database": "test_db", 
        "user": "test_user",
        "password": "test_pass"
    }
    
    for i, query in enumerate(queries, 1):
        try:
            code = create_executable("postgresql", query, base_config)
            print(f"✅ Generated script {i} ({len(code)} characters)")
        except Exception as e:
            print(f"❌ Script {i} failed: {e}")


if __name__ == "__main__":
    """Run all demonstrations."""
    try:
        demo_usage()
        create_custom_template_example() 
        advanced_usage_examples()
        print("\n🎉 All demos completed successfully!")
        
    except Exception as e:
        print(f"\n💥 Demo failed: {e}")
        import traceback
        traceback.print_exc()
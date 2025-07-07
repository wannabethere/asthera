"""
Tests for MDL Builder Service
Tests the MDL builder functionality using PostgreSQL objects
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.session_manager import SessionManager
from app.core.config import ServiceConfig
from app.services.mdl_builder_service import mdl_builder_service
from app.schemas.dbmodels import (
    Project, Dataset, Table, SQLColumn, Metric, View, 
    CalculatedColumn, SQLFunction, Relationship
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_mdl_builder_service():
    """Test MDL builder service functionality"""
    
    print("\n🔧 Testing MDL Builder Service...")
    
    # Initialize session manager
    config = ServiceConfig(
        database_url="postgresql+asyncpg://user:password@localhost:5432/testdb",
        log_level="INFO"
    )
    session_manager = SessionManager(config)
    
    try:
        # Create test data
        async with session_manager.get_async_db_session() as db:
            test_project = await create_test_project(db)
            print(f"✅ Created test project: {test_project.project_id}")
            
            # Test 1: Build project MDL
            print("\n📋 Test 1: Building project MDL...")
            project_mdl = await mdl_builder_service.build_project_mdl(
                project_id=test_project.project_id,
                db=db,
                include_llm_definitions=True
            )
            
            print(f"✅ Project MDL built successfully")
            print(f"   Tables: {len(project_mdl.get('tables', []))}")
            print(f"   Metrics: {len(project_mdl.get('metrics', []))}")
            print(f"   Views: {len(project_mdl.get('views', []))}")
            print(f"   Calculated Columns: {len(project_mdl.get('calculated_columns', []))}")
            print(f"   Functions: {len(project_mdl.get('functions', []))}")
            print(f"   Relationships: {len(project_mdl.get('relationships', []))}")
            
            # Test 2: Build table MDL
            print("\n📊 Test 2: Building table MDL...")
            if project_mdl.get('tables'):
                table_id = project_mdl['tables'][0]['table_id']
                table_mdl = await mdl_builder_service.build_table_mdl(
                    table_id=table_id,
                    db=db,
                    include_llm_definitions=True
                )
                
                print(f"✅ Table MDL built successfully")
                print(f"   Table: {table_mdl['name']}")
                print(f"   Columns: {len(table_mdl.get('columns', []))}")
                print(f"   Metrics: {len(table_mdl.get('metrics', []))}")
                print(f"   Views: {len(table_mdl.get('views', []))}")
            
            # Test 3: Save MDL to file
            print("\n💾 Test 3: Saving MDL to file...")
            file_path = f"test_mdl_files/{test_project.project_id}_test_mdl.json"
            save_result = await mdl_builder_service.save_mdl_to_file(
                mdl_data=project_mdl,
                file_path=file_path
            )
            
            if save_result["success"]:
                print(f"✅ MDL file saved successfully")
                print(f"   File path: {save_result['file_path']}")
                print(f"   File size: {save_result['file_size']} bytes")
                
                # Verify file content
                with open(file_path, 'r') as f:
                    saved_mdl = json.load(f)
                    print(f"   Saved MDL has {len(saved_mdl.get('tables', []))} tables")
            else:
                print(f"❌ Failed to save MDL file: {save_result['error']}")
            
            # Test 4: Build MDL without LLM definitions
            print("\n🚀 Test 4: Building MDL without LLM definitions...")
            project_mdl_no_llm = await mdl_builder_service.build_project_mdl(
                project_id=test_project.project_id,
                db=db,
                include_llm_definitions=False
            )
            
            print(f"✅ MDL without LLM definitions built successfully")
            print(f"   Tables: {len(project_mdl_no_llm.get('tables', []))}")
            
            # Test 5: Validate MDL structure
            print("\n✅ Test 5: Validating MDL structure...")
            validation_result = validate_mdl_structure(project_mdl)
            print(f"✅ MDL validation completed")
            print(f"   Is valid: {validation_result['is_valid']}")
            print(f"   Errors: {len(validation_result['errors'])}")
            print(f"   Warnings: {len(validation_result['warnings'])}")
            
            # Cleanup test files
            cleanup_test_files(test_project.project_id)
            
            print("\n✅ MDL Builder Service tests completed successfully!")
            
    except Exception as e:
        print(f"❌ Error during MDL builder service test: {str(e)}")
        import traceback
        traceback.print_exc()


async def create_test_project(db: AsyncSession) -> Project:
    """Create a test project with comprehensive data"""
    
    # Create project
    project = Project(
        project_id="mdl_test_project_001",
        display_name="MDL Builder Test Project",
        description="Test project for MDL builder functionality",
        created_by="test_user",
        status='active',
        version_locked=False,
        json_metadata={
            "context": {
                "business_domain": "E-commerce",
                "target_users": ["Data Analysts", "Business Users"],
                "key_business_concepts": ["Customer", "Order", "Product"]
            },
            "llm_definitions": {
                "generated_at": datetime.utcnow().isoformat(),
                "definitions_count": 2,
                "tables_processed": 2
            }
        }
    )
    
    # Create dataset
    dataset = Dataset(
        dataset_id="test_dataset_001",
        project_id=project.project_id,
        name="test_dataset",
        display_name="Test Dataset",
        description="Test dataset for MDL builder"
    )
    
    # Create table 1
    table1 = Table(
        table_id="test_table_001",
        dataset_id=dataset.dataset_id,
        project_id=project.project_id,
        name="customers",
        display_name="Customers",
        description="Customer master data table",
        table_type="table",
        json_metadata={
            "llm_definitions": {
                "business_purpose": "Store and manage customer information",
                "primary_use_cases": ["Customer analytics", "Sales reporting"],
                "key_relationships": ["Orders", "Payments"],
                "data_lineage": "Extracted from CRM system",
                "update_frequency": "Daily",
                "data_retention": "7 years",
                "access_patterns": ["Read-heavy", "Batch updates"],
                "performance_considerations": ["Indexed on customer_id"]
            }
        }
    )
    
    # Create table 2
    table2 = Table(
        table_id="test_table_002",
        dataset_id=dataset.dataset_id,
        project_id=project.project_id,
        name="orders",
        display_name="Orders",
        description="Order transaction data",
        table_type="table",
        json_metadata={
            "llm_definitions": {
                "business_purpose": "Track order transactions and status",
                "primary_use_cases": ["Order tracking", "Revenue analysis"],
                "key_relationships": ["Customers", "Products"],
                "data_lineage": "Extracted from order management system",
                "update_frequency": "Real-time",
                "data_retention": "5 years",
                "access_patterns": ["Read-heavy", "Real-time queries"],
                "performance_considerations": ["Indexed on order_id", "Partitioned by date"]
            }
        }
    )
    
    # Create columns for table 1
    customer_id_col = SQLColumn(
        column_id="customer_id_col_001",
        table_id=table1.table_id,
        name="customer_id",
        display_name="Customer ID",
        description="Unique customer identifier",
        column_type="column",
        data_type="VARCHAR(50)",
        usage_type="identifier",
        is_nullable=False,
        is_primary_key=True,
        is_foreign_key=False,
        ordinal_position=1,
        json_metadata={
            "llm_definitions": {
                "business_description": "Primary key for customer records",
                "example_values": ["CUST001", "CUST002"],
                "business_rules": ["Must be unique", "Cannot be null"],
                "data_quality_checks": ["Uniqueness", "Format validation"],
                "related_concepts": ["Customer", "Account"],
                "privacy_classification": "PII",
                "aggregation_suggestions": ["Count", "Distinct count"],
                "filtering_suggestions": ["Exact match", "Pattern matching"]
            }
        }
    )
    
    customer_name_col = SQLColumn(
        column_id="customer_name_col_001",
        table_id=table1.table_id,
        name="customer_name",
        display_name="Customer Name",
        description="Full name of the customer",
        column_type="column",
        data_type="VARCHAR(100)",
        usage_type="attribute",
        is_nullable=False,
        is_primary_key=False,
        is_foreign_key=False,
        ordinal_position=2,
        json_metadata={
            "llm_definitions": {
                "business_description": "Customer's full legal name",
                "example_values": ["John Doe", "Jane Smith"],
                "business_rules": ["Cannot be null", "Minimum 2 characters"],
                "data_quality_checks": ["Length validation", "Character validation"],
                "related_concepts": ["Name", "Person"],
                "privacy_classification": "PII",
                "aggregation_suggestions": ["Count", "Group by"],
                "filtering_suggestions": ["Partial match", "Case insensitive"]
            }
        }
    )
    
    # Create calculated column
    calculated_col = SQLColumn(
        column_id="calculated_col_001",
        table_id=table1.table_id,
        name="customer_initials",
        display_name="Customer Initials",
        description="Customer initials derived from name",
        column_type="calculated_column",
        data_type="VARCHAR(10)",
        usage_type="derived",
        is_nullable=True,
        is_primary_key=False,
        is_foreign_key=False,
        ordinal_position=3,
        json_metadata={
            "llm_definitions": {
                "business_description": "First letter of first and last name",
                "calculation_logic": "Extract first letter of first and last name",
                "business_rules": ["Derived from customer_name"],
                "dependencies_explanation": ["Depends on customer_name column"]
            }
        }
    )
    
    calculated_column_def = CalculatedColumn(
        calculated_column_id="calc_col_def_001",
        column_id=calculated_col.column_id,
        calculation_sql="UPPER(LEFT(customer_name, 1) || LEFT(SUBSTRING(customer_name FROM POSITION(' ' IN customer_name) + 1), 1))",
        function_id=None,
        dependencies=["customer_name"]
    )
    
    # Create columns for table 2
    order_id_col = SQLColumn(
        column_id="order_id_col_001",
        table_id=table2.table_id,
        name="order_id",
        display_name="Order ID",
        description="Unique order identifier",
        column_type="column",
        data_type="VARCHAR(50)",
        usage_type="identifier",
        is_nullable=False,
        is_primary_key=True,
        is_foreign_key=False,
        ordinal_position=1
    )
    
    customer_id_fk_col = SQLColumn(
        column_id="customer_id_fk_col_001",
        table_id=table2.table_id,
        name="customer_id",
        display_name="Customer ID",
        description="Foreign key to customers table",
        column_type="column",
        data_type="VARCHAR(50)",
        usage_type="foreign_key",
        is_nullable=False,
        is_primary_key=False,
        is_foreign_key=True,
        ordinal_position=2
    )
    
    # Create metric
    metric = Metric(
        metric_id="test_metric_001",
        table_id=table1.table_id,
        name="total_customers",
        display_name="Total Customers",
        description="Total number of customers",
        metric_sql="COUNT(DISTINCT customer_id)",
        metric_type="count",
        aggregation_type="count",
        format_string="#,##0",
        json_metadata={
            "llm_definitions": {
                "business_purpose": "Track total customer count",
                "calculation_logic": "Count distinct customer IDs",
                "business_rules": ["Excludes null customer IDs"],
                "interpretation_guidelines": ["Use for customer growth analysis"],
                "related_metrics": ["new_customers", "active_customers"],
                "alert_thresholds": ["Decline > 10% month-over-month"]
            }
        }
    )
    
    # Create view
    view = View(
        view_id="test_view_001",
        table_id=table1.table_id,
        name="active_customers",
        display_name="Active Customers",
        description="View of customers with recent activity",
        view_sql="SELECT * FROM customers WHERE last_activity_date >= CURRENT_DATE - INTERVAL '30 days'",
        view_type="filtered",
        json_metadata={
            "llm_definitions": {
                "business_purpose": "Show customers with recent activity",
                "use_cases": ["Customer engagement analysis", "Marketing campaigns"],
                "data_sources": ["customers table"],
                "refresh_frequency": "Daily",
                "access_patterns": ["Read-only", "Filtered queries"]
            }
        }
    )
    
    # Create function
    function = SQLFunction(
        function_id="test_function_001",
        project_id=project.project_id,
        name="calculate_customer_lifetime_value",
        display_name="Calculate Customer Lifetime Value",
        description="Calculate customer lifetime value based on order history",
        function_sql="""
        CREATE OR REPLACE FUNCTION calculate_customer_lifetime_value(customer_id VARCHAR)
        RETURNS DECIMAL AS $$
        BEGIN
            RETURN (
                SELECT COALESCE(SUM(order_total), 0)
                FROM orders
                WHERE customer_id = $1
            );
        END;
        $$ LANGUAGE plpgsql;
        """,
        return_type="DECIMAL",
        parameters=[
            {"name": "customer_id", "type": "VARCHAR", "description": "Customer ID"}
        ]
    )
    
    # Create relationship
    relationship = Relationship(
        relationship_id="test_relationship_001",
        project_id=project.project_id,
        name="customer_orders",
        relationship_type="one_to_many",
        from_table_id=table1.table_id,
        to_table_id=table2.table_id,
        from_column_id=customer_id_col.column_id,
        to_column_id=customer_id_fk_col.column_id,
        description="Relationship between customers and orders",
        is_active=True
    )
    
    # Add all entities to database
    db.add(project)
    db.add(dataset)
    db.add(table1)
    db.add(table2)
    db.add(customer_id_col)
    db.add(customer_name_col)
    db.add(calculated_col)
    db.add(calculated_column_def)
    db.add(order_id_col)
    db.add(customer_id_fk_col)
    db.add(metric)
    db.add(view)
    db.add(function)
    db.add(relationship)
    
    await db.commit()
    await db.refresh(project)
    
    return project


def validate_mdl_structure(mdl_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate MDL structure and return validation results"""
    validation_result = {
        "is_valid": True,
        "errors": [],
        "warnings": [],
        "statistics": {
            "tables_without_description": 0,
            "columns_without_description": 0,
            "tables_without_columns": 0,
            "metrics_without_sql": 0,
            "views_without_sql": 0
        }
    }
    
    # Validate required top-level fields
    required_fields = ["project_id", "project_name", "version", "generated_at"]
    for field in required_fields:
        if field not in mdl_data:
            validation_result["errors"].append(f"Missing required field: {field}")
            validation_result["is_valid"] = False
    
    # Validate tables
    for table in mdl_data.get("tables", []):
        if not table.get("description"):
            validation_result["warnings"].append(f"Table '{table['name']}' has no description")
            validation_result["statistics"]["tables_without_description"] += 1
        
        if not table.get("columns"):
            validation_result["warnings"].append(f"Table '{table['name']}' has no columns")
            validation_result["statistics"]["tables_without_columns"] += 1
        
        # Validate columns
        for column in table.get("columns", []):
            if not column.get("description"):
                validation_result["warnings"].append(f"Column '{table['name']}.{column['name']}' has no description")
                validation_result["statistics"]["columns_without_description"] += 1
    
    # Validate metrics
    for metric in mdl_data.get("metrics", []):
        if not metric.get("metric_sql"):
            validation_result["errors"].append(f"Metric '{metric['name']}' has no SQL definition")
            validation_result["statistics"]["metrics_without_sql"] += 1
            validation_result["is_valid"] = False
    
    # Validate views
    for view in mdl_data.get("views", []):
        if not view.get("view_sql"):
            validation_result["errors"].append(f"View '{view['name']}' has no SQL definition")
            validation_result["statistics"]["views_without_sql"] += 1
            validation_result["is_valid"] = False
    
    return validation_result


def cleanup_test_files(project_id: str):
    """Clean up test files"""
    try:
        test_dir = Path("test_mdl_files")
        if test_dir.exists():
            for file_path in test_dir.glob(f"{project_id}_*"):
                file_path.unlink()
            print(f"✅ Cleaned up test files for project {project_id}")
    except Exception as e:
        print(f"⚠️ Warning: Could not clean up test files: {str(e)}")


if __name__ == "__main__":
    # Run the test
    asyncio.run(test_mdl_builder_service()) 
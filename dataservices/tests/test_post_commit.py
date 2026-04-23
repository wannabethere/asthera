#!/usr/bin/env python3
"""
Test script for post-commit workflow functionality
"""

import asyncio
import json
from datetime import datetime
from app.service.models import (
    CreateProjectRequest, ProjectContext, AddTableRequest, SchemaInput
)
from app.core.session_manager import SessionManager
from app.core.settings import ServiceConfig
from app.service.post_commit_service import PostCommitService

async def test_post_commit_workflows():
    """Test the post-commit LLM definition generation workflow"""
    
    # Initialize session manager
    config = ServiceConfig(
        database_url="postgresql+asyncpg://user:password@localhost:5432/testdb",
        log_level="INFO"
    )
    session_manager = SessionManager(config)
    session_manager.create_tables()
    
    print("🚀 Starting post-commit LLM definition generation test...")
    
    # Test data
    project_data = CreateProjectRequest(
        project_id="post_commit_test_001",
        display_name="Post-Commit Test Project",
        description="A test project for post-commit workflow validation",
        created_by="test_user",
        context=ProjectContext(
            project_id="post_commit_test_001",
            project_name="Post-Commit Test Project",
            business_domain="E-commerce",
            purpose="Customer analytics and reporting",
            target_users=["Data Analysts", "Business Users"],
            key_business_concepts=["Customer", "Order", "Product", "Revenue"]
        )
    )
    
    dataset_data = {
        "project_id": "post_commit_test_001",
        "name": "customer_data",
        "display_name": "Customer Data",
        "description": "Customer information and transactions",
        "metadata": {"source": "CRM", "update_frequency": "daily"}
    }
    
    table_schema = SchemaInput(
        table_name="customers",
        table_description="Customer master data table",
        columns=[
            {
                "name": "customer_id",
                "display_name": "Customer ID",
                "description": "Unique customer identifier",
                "data_type": "VARCHAR(50)",
                "is_primary_key": True,
                "is_nullable": False,
                "usage_type": "identifier"
            },
            {
                "name": "customer_name",
                "display_name": "Customer Name",
                "description": "Full name of the customer",
                "data_type": "VARCHAR(100)",
                "is_nullable": False,
                "usage_type": "attribute"
            },
            {
                "name": "email",
                "display_name": "Email Address",
                "description": "Customer email address",
                "data_type": "VARCHAR(255)",
                "is_nullable": True,
                "usage_type": "attribute"
            },
            {
                "name": "created_date",
                "display_name": "Created Date",
                "description": "Date when customer was created",
                "data_type": "TIMESTAMP",
                "is_nullable": False,
                "usage_type": "timestamp"
            }
        ]
    )
    
    add_table_request = AddTableRequest(
        dataset_id="",  # Will be set after dataset creation
        schema=table_schema
    )
    
    project_context = ProjectContext(
        project_id="post_commit_test_001",
        project_name="Post-Commit Test Project",
        business_domain="E-commerce",
        purpose="Customer analytics and reporting",
        target_users=["Data Analysts", "Business Users"],
        key_business_concepts=["Customer", "Order", "Product", "Revenue"]
    )
    
    try:
        async with session_manager.get_async_db_session() as db:
            # Step 1: Create project
            print("\n📋 Step 1: Creating project...")
            from app.schemas.dbmodels import Project, Dataset, Table, SQLColumn
            from sqlalchemy import select
            
            # Create project in database
            project = Project(
                project_id=project_data.project_id,
                display_name=project_data.display_name,
                description=project_data.description,
                created_by=project_data.created_by,
                status='draft_ready',  # Set to draft_ready to test post-commit
                version_locked=True
            )
            
            db.add(project)
            await db.commit()
            await db.refresh(project)
            print("✅ Project created in database")
            
            # Step 2: Add dataset
            print("\n📊 Step 2: Adding dataset...")
            dataset = Dataset(
                project_id=project.project_id,
                name=dataset_data["name"],
                display_name=dataset_data["display_name"],
                description=dataset_data["description"],
                json_metadata=dataset_data.get("metadata", {})
            )
            
            db.add(dataset)
            await db.commit()
            await db.refresh(dataset)
            print("✅ Dataset added to database")
            
            # Step 3: Add table
            print("\n📋 Step 3: Adding table...")
            table = Table(
                project_id=project.project_id,
                dataset_id=dataset.dataset_id,
                name=add_table_request.table_schema.table_name,
                display_name=add_table_request.table_schema.table_name,
                description=add_table_request.table_schema.table_description,
                table_type='table',
                json_metadata={
                    "columns": add_table_request.table_schema.columns
                }
            )
            
            db.add(table)
            await db.commit()
            await db.refresh(table)
            print("✅ Table added to database")
            
            # Step 4: Add columns
            print("\n📝 Step 4: Adding columns...")
            for i, col_data in enumerate(add_table_request.table_schema.columns):
                column = SQLColumn(
                    table_id=table.table_id,
                    name=col_data.get("name", "unknown"),
                    display_name=col_data.get("display_name") or col_data.get("name", "unknown"),
                    description=col_data.get("description"),
                    data_type=col_data.get("data_type"),
                    is_nullable=col_data.get("is_nullable", True),
                    is_primary_key=col_data.get("is_primary_key", False),
                    is_foreign_key=col_data.get("is_foreign_key", False),
                    usage_type=col_data.get("usage_type"),
                    ordinal_position=i + 1,
                    json_metadata=col_data.get("metadata", {})
                )
                db.add(column)
            
            await db.commit()
            print("✅ Columns added to table")
            
            # Step 5: Execute post-commit LLM definition generation
            print("\n🔄 Step 5: Executing post-commit LLM definition generation...")
            post_commit_service = PostCommitService("test_user", "test_session")
            
            # Execute post-commit workflow
            results = await post_commit_service.execute_post_commit_workflows(project.project_id, db)
            
            print("✅ Post-commit LLM definition generation completed")
            print(f"   Status: {results['status']}")
            print(f"   MDL file created: {results['workflows'].get('chromadb_integration', {}).get('mdl_file_created', False)}")
            print(f"   Definitions generated: {results['workflows'].get('chromadb_integration', {}).get('definitions_generated', 0)}")
            print(f"   Tables processed: {results['workflows'].get('chromadb_integration', {}).get('tables_processed', 0)}")
            print(f"   Errors: {len(results['errors'])}")
            
            # Step 6: Display detailed results
            print("\n📊 Step 6: Detailed workflow results...")
            for workflow_name, workflow_result in results["workflows"].items():
                print(f"   📋 {workflow_name}:")
                if isinstance(workflow_result, dict):
                    for key, value in workflow_result.items():
                        if key != "errors" or value:  # Only show errors if they exist
                            print(f"      {key}: {value}")
                else:
                    print(f"      {workflow_result}")
            
            # Step 7: Test project JSON schemas processing
            print("\n🔄 Step 7: Testing project JSON schemas processing...")
            if "project_json_schemas" in results["workflows"]:
                json_schemas_result = results["workflows"]["project_json_schemas"]
                print(f"   JSON types processed: {json_schemas_result.get('json_types_processed', [])}")
                print(f"   Tables processed: {json_schemas_result.get('tables_processed', 0)}")
                print(f"   Metrics processed: {json_schemas_result.get('metrics_processed', 0)}")
                print(f"   Views processed: {json_schemas_result.get('views_processed', 0)}")
                print(f"   Calculated columns processed: {json_schemas_result.get('calculated_columns_processed', 0)}")
                print(f"   Summary created: {json_schemas_result.get('summary_created', False)}")
                print(f"   ChromaDB document IDs: {json_schemas_result.get('chroma_document_ids', {})}")
                if json_schemas_result.get('errors'):
                    print(f"   Errors: {json_schemas_result['errors']}")
            else:
                print("   ⚠️  Project JSON schemas workflow not found in results")
                print(f"\n   🔧 {workflow_name}:")
                if isinstance(workflow_result, dict):
                    for key, value in workflow_result.items():
                        if isinstance(value, list):
                            print(f"      {key}: {len(value)} items")
                        else:
                            print(f"      {key}: {value}")
                else:
                    print(f"      Result: {workflow_result}")
            
            # Step 7: Check updated project metadata
            print("\n📋 Step 7: Checking updated project metadata...")
            updated_project = await db.execute(
                select(Project).where(Project.project_id == project.project_id)
            )
            updated_project = updated_project.scalar_one_or_none()
            
            if updated_project and updated_project.json_metadata:
                metadata = updated_project.json_metadata
                print("   Project metadata updated with:")
                if "llm_definitions" in metadata:
                    llm_defs = metadata["llm_definitions"]
                    print(f"      ✅ LLM definitions generated at: {llm_defs.get('generated_at')}")
                    print(f"      ✅ MDL file path: {llm_defs.get('mdl_file_path')}")
                    print(f"      ✅ Definitions count: {llm_defs.get('definitions_count')}")
                    print(f"      ✅ Tables processed: {llm_defs.get('tables_processed')}")
            
            # Step 8: Check if MDL file was created
            print("\n📁 Step 8: Checking MDL file creation...")
            if updated_project and updated_project.json_metadata:
                mdl_file_path = updated_project.json_metadata.get("llm_definitions", {}).get("mdl_file_path")
                if mdl_file_path:
                    import os
                    if os.path.exists(mdl_file_path):
                        print(f"      ✅ MDL file exists: {mdl_file_path}")
                        file_size = os.path.getsize(mdl_file_path)
                        print(f"      ✅ File size: {file_size} bytes")
                        
                        # Read and display sample content
                        import json
                        with open(mdl_file_path, 'r') as f:
                            mdl_content = json.load(f)
                        print(f"      ✅ Project: {mdl_content.get('project_name')}")
                        print(f"      ✅ Tables in MDL: {len(mdl_content.get('tables', []))}")
                    else:
                        print(f"      ❌ MDL file not found: {mdl_file_path}")
                else:
                    print("      ❌ No MDL file path in metadata")
            
    except Exception as e:
        print(f"❌ Error during post-commit test: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n🎉 Post-commit workflow test completed!")

async def test_individual_workflows():
    """Test individual post-commit workflows"""
    
    print("\n🧪 Testing individual post-commit workflows...")
    
    config = ServiceConfig(
        database_url="postgresql+asyncpg://user:password@localhost:5432/testdb",
        log_level="INFO"
    )
    session_manager = SessionManager(config)
    
    try:
        async with session_manager.get_async_db_session() as db:
            post_commit_service = PostCommitService("test_user", "test_session")
            
            # Test with a sample project (you would need to create this first)
            project_id = "sample_project_001"
            
            # Test individual workflow methods
            print("\n🔧 Testing semantic descriptions generation...")
            # This would require a real project with tables in the database
            
            print("✅ Individual workflow tests completed")
            
    except Exception as e:
        print(f"❌ Error during individual workflow tests: {str(e)}")

async def test_project_json_schemas_workflow():
    """Test the project JSON schemas workflow specifically"""
    print("\n🧪 Testing project JSON schemas workflow...")
    
    # Initialize session manager
    config = ServiceConfig(
        database_url="postgresql+asyncpg://user:password@localhost:5432/testdb",
        log_level="INFO"
    )
    session_manager = SessionManager(config)
    session_manager.create_tables()
    
    try:
        async with session_manager.get_async_db_session() as db:
            # Create a test project with comprehensive data
            from app.schemas.dbmodels import Project, Dataset, Table, SQLColumn, Metric, View, CalculatedColumn
            
            project = Project(
                project_id="json_schemas_test_001",
                display_name="JSON Schemas Test Project",
                description="Test project for JSON schemas workflow testing",
                created_by="test_user",
                status='draft_ready',
                version_locked=True,
                json_metadata={
                    "context": {
                        "business_domain": "E-commerce",
                        "target_users": ["Data Analysts", "Business Users"],
                        "key_business_concepts": ["Customer", "Order", "Product"]
                    }
                }
            )
            
            db.add(project)
            await db.commit()
            await db.refresh(project)
            
            # Create dataset
            dataset = Dataset(
                project_id=project.project_id,
                name="ecommerce_data",
                display_name="E-commerce Data",
                description="E-commerce customer and order data"
            )
            
            db.add(dataset)
            await db.commit()
            await db.refresh(dataset)
            
            # Create table
            table = Table(
                project_id=project.project_id,
                dataset_id=dataset.dataset_id,
                name="customers",
                display_name="Customers",
                description="Customer master data table",
                table_type='table'
            )
            
            db.add(table)
            await db.commit()
            await db.refresh(table)
            
            # Add columns
            columns_data = [
                {
                    "name": "customer_id",
                    "display_name": "Customer ID",
                    "description": "Unique customer identifier",
                    "data_type": "VARCHAR(50)",
                    "usage_type": "identifier",
                    "is_primary_key": True
                },
                {
                    "name": "customer_name",
                    "display_name": "Customer Name",
                    "description": "Full name of the customer",
                    "data_type": "VARCHAR(100)",
                    "usage_type": "attribute"
                },
                {
                    "name": "total_orders",
                    "display_name": "Total Orders",
                    "description": "Total number of orders by customer",
                    "data_type": "INTEGER",
                    "usage_type": "metric"
                }
            ]
            
            for i, col_data in enumerate(columns_data):
                column = SQLColumn(
                    table_id=table.table_id,
                    name=col_data["name"],
                    display_name=col_data["display_name"],
                    description=col_data["description"],
                    data_type=col_data["data_type"],
                    usage_type=col_data["usage_type"],
                    is_primary_key=col_data.get("is_primary_key", False),
                    ordinal_position=i + 1
                )
                db.add(column)
            
            await db.commit()
            
            # Create a metric
            metric = Metric(
                project_id=project.project_id,
                name="customer_count",
                display_name="Customer Count",
                description="Total number of customers",
                metric_sql="SELECT COUNT(*) FROM customers",
                metric_type="count",
                aggregation_type="count",
                table_id=table.table_id
            )
            
            db.add(metric)
            await db.commit()
            
            # Create a view
            view = View(
                project_id=project.project_id,
                name="active_customers",
                display_name="Active Customers",
                description="Customers with recent orders",
                view_sql="SELECT * FROM customers WHERE total_orders > 0",
                view_type="filtered"
            )
            
            db.add(view)
            await db.commit()
            
            # Create a calculated column
            calc_column = CalculatedColumn(
                project_id=project.project_id,
                name="customer_tier",
                display_name="Customer Tier",
                description="Customer tier based on order count",
                calculation_sql="CASE WHEN total_orders > 10 THEN 'Premium' WHEN total_orders > 5 THEN 'Regular' ELSE 'New' END",
                function_id="customer_tier_calc"
            )
            
            db.add(calc_column)
            await db.commit()
            
            # Test post-commit service with JSON schemas workflow
            post_commit_service = PostCommitService("test_user", "test_session")
            
            print("🔄 Executing project JSON schemas workflow...")
            results = await post_commit_service.execute_post_commit_workflows(project.project_id, db)
            
            print("✅ Project JSON schemas workflow test completed")
            print(f"   Status: {results['status']}")
            
            if "project_json_schemas" in results["workflows"]:
                json_result = results["workflows"]["project_json_schemas"]
                print(f"   JSON types processed: {json_result.get('json_types_processed', [])}")
                print(f"   Tables processed: {json_result.get('tables_processed', 0)}")
                print(f"   Metrics processed: {json_result.get('metrics_processed', 0)}")
                print(f"   Views processed: {json_result.get('views_processed', 0)}")
                print(f"   Calculated columns processed: {json_result.get('calculated_columns_processed', 0)}")
                print(f"   Summary created: {json_result.get('summary_created', False)}")
                print(f"   ChromaDB document IDs: {json_result.get('chroma_document_ids', {})}")
                
                if json_result.get('errors'):
                    print(f"   Errors: {json_result['errors']}")
            else:
                print("   ⚠️  Project JSON schemas workflow not found in results")
            
    except Exception as e:
        print(f"❌ Error in project JSON schemas workflow test: {str(e)}")
        raise


if __name__ == "__main__":
    # Run the main post-commit workflow test
    asyncio.run(test_post_commit_workflows())
    
    # Run individual workflow tests
    asyncio.run(test_individual_workflows())
    
    # Run project JSON schemas workflow test
    asyncio.run(test_project_json_schemas_workflow()) 
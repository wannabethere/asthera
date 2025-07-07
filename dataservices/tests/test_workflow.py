#!/usr/bin/env python3
"""
Test script for the project workflow functionality
"""

import asyncio
import json
from datetime import datetime
from app.service.models import (
    CreateProjectRequest, ProjectContext, AddTableRequest, SchemaInput
)
from app.core.session_manager import SessionManager
from app.core.settings import ServiceConfig

async def test_workflow():
    """Test the complete workflow: create project -> add dataset -> add table -> commit"""
    
    # Initialize session manager
    config = ServiceConfig(
        database_url="postgresql+asyncpg://user:password@localhost:5432/testdb",
        log_level="INFO"
    )
    session_manager = SessionManager(config)
    session_manager.create_tables()
    
    print("🚀 Starting workflow test...")
    
    # Test data
    project_data = CreateProjectRequest(
        project_id="test_project_001",
        display_name="Test Project",
        description="A test project for workflow validation",
        created_by="test_user",
        context=ProjectContext(
            project_id="test_project_001",
            project_name="Test Project",
            business_domain="E-commerce",
            purpose="Customer analytics and reporting",
            target_users=["Data Analysts", "Business Users"],
            key_business_concepts=["Customer", "Order", "Product", "Revenue"]
        )
    )
    
    dataset_data = {
        "project_id": "test_project_001",
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
        project_id="test_project_001",
        project_name="Test Project",
        business_domain="E-commerce",
        purpose="Customer analytics and reporting",
        target_users=["Data Analysts", "Business Users"],
        key_business_concepts=["Customer", "Order", "Product", "Revenue"]
    )
    
    try:
        # Step 1: Create project
        print("\n📋 Step 1: Creating project...")
        async with session_manager.get_async_db_session() as db:
            # This would normally be done through the router
            # For testing, we'll simulate the workflow service directly
            from app.service.project_workflow_service import ProjectWorkflowService
            
            workflow_service = ProjectWorkflowService("test_user", "test_session")
            
            # Create project in workflow state
            await workflow_service.create_project({
                "project_id": project_data.project_id,
                "display_name": project_data.display_name,
                "description": project_data.description,
                "created_by": project_data.created_by,
                "context": project_data.context.dict() if project_data.context else None
            })
            
            print("✅ Project created in workflow state")
            
            # Step 2: Add dataset
            print("\n📊 Step 2: Adding dataset...")
            await workflow_service.add_dataset(dataset_data)
            print("✅ Dataset added to workflow state")
            
            # Step 3: Add table
            print("\n📋 Step 3: Adding table...")
            # Update dataset_id in the request
            add_table_request.dataset_id = "temp_dataset_id"  # In real scenario, this would be the actual dataset ID
            
            documented_table = await workflow_service.add_table(add_table_request, project_context)
            print("✅ Table added with enhanced documentation")
            print(f"   Table description: {documented_table.description}")
            print(f"   Business purpose: {documented_table.business_purpose}")
            print(f"   Primary use cases: {documented_table.primary_use_cases}")
            
            # Step 4: Commit workflow
            print("\n💾 Step 4: Committing workflow...")
            state = await workflow_service.commit_workflow(db)
            print("✅ Workflow committed successfully")
            
            # Step 5: Get workflow status
            print("\n📈 Step 5: Getting workflow status...")
            workflow_state = workflow_service.get_workflow_state()
            print(f"   Workflow state: {json.dumps(workflow_state, indent=2, default=str)}")
            
    except Exception as e:
        print(f"❌ Error during workflow test: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n🎉 Workflow test completed!")

if __name__ == "__main__":
    asyncio.run(test_workflow()) 
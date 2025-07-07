#!/usr/bin/env python3
"""
Test script for the project workflow service with semantics description integration
"""

import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.service.project_workflow_service import ProjectWorkflowService
from app.service.models import AddTableRequest, SchemaInput, ProjectContext

async def test_workflow_semantics():
    """Test the project workflow service with semantics description integration"""
    
    # Create project context
    project_context = ProjectContext(
        project_id="test_workflow_project",
        project_name="Test Workflow Project",
        business_domain="E-commerce",
        purpose="Track customer orders and inventory",
        target_users=["Analysts", "Managers", "Developers"],
        key_business_concepts=["Customer", "Order", "Product", "Inventory"]
    )
    
    # Create sample table schema
    schema_input = SchemaInput(
        table_name="orders",
        table_description="Stores customer order information including items, quantities, and status",
        columns=[
            {
                "name": "order_id",
                "display_name": "Order ID",
                "description": "Unique identifier for each order",
                "data_type": "UUID",
                "is_primary_key": True,
                "is_nullable": False,
                "usage_type": "identifier"
            },
            {
                "name": "customer_id",
                "display_name": "Customer ID",
                "description": "Reference to the customer who placed the order",
                "data_type": "UUID",
                "is_primary_key": False,
                "is_nullable": False,
                "usage_type": "identifier"
            },
            {
                "name": "order_date",
                "display_name": "Order Date",
                "description": "Date and time when the order was placed",
                "data_type": "TIMESTAMP",
                "is_primary_key": False,
                "is_nullable": False,
                "usage_type": "timestamp"
            },
            {
                "name": "total_amount",
                "display_name": "Total Amount",
                "description": "Total cost of the order including tax and shipping",
                "data_type": "DECIMAL(10,2)",
                "is_primary_key": False,
                "is_nullable": False,
                "usage_type": "measure"
            },
            {
                "name": "status",
                "display_name": "Order Status",
                "description": "Current status of the order (pending, shipped, delivered, etc.)",
                "data_type": "VARCHAR(50)",
                "is_primary_key": False,
                "is_nullable": False,
                "usage_type": "dimension"
            }
        ]
    )
    
    # Create add table request
    add_table_request = AddTableRequest(
        dataset_id="test_dataset",
        schema=schema_input
    )
    
    print("Testing Project Workflow Service with Semantics Description")
    print("=" * 60)
    print(f"Project: {project_context.project_name}")
    print(f"Domain: {project_context.business_domain}")
    print(f"Table: {schema_input.table_name}")
    print(f"Columns: {len(schema_input.columns)}")
    print()
    
    try:
        # Create workflow service
        workflow_service = ProjectWorkflowService(
            user_id="test_user",
            session_id="test_session"
        )
        
        # Test semantic description generation
        print("1. Testing Semantic Description Generation")
        print("-" * 40)
        semantic_description = await workflow_service.get_semantic_description_for_table(
            add_table_request, project_context
        )
        
        print("✅ Successfully generated semantic description!")
        print()
        print("Generated Description:")
        print("-" * 30)
        print(semantic_description.get("description", "No description"))
        print()
        
        print("Table Purpose:")
        print("-" * 30)
        print(semantic_description.get("table_purpose", "No purpose specified"))
        print()
        
        print("Key Columns:")
        print("-" * 30)
        for col in semantic_description.get("key_columns", []):
            print(f"• {col.get('name')}: {col.get('description')}")
            print(f"  Business Significance: {col.get('business_significance')}")
            print(f"  Data Type: {col.get('data_type')}")
            print()
        
        print("Business Context:")
        print("-" * 30)
        print(semantic_description.get("business_context", "No context provided"))
        print()
        
        print("Data Patterns:")
        print("-" * 30)
        for pattern in semantic_description.get("data_patterns", []):
            print(f"• {pattern}")
        print()
        
        print("Suggested Relationships:")
        print("-" * 30)
        for rel in semantic_description.get("suggested_relationships", []):
            print(f"• {rel.get('related_entity')} ({rel.get('relationship_type')})")
            print(f"  Reasoning: {rel.get('reasoning')}")
            print()
        
        # Test adding table to workflow
        print("2. Testing Add Table to Workflow")
        print("-" * 40)
        documented_table = await workflow_service.add_table(add_table_request, project_context)
        
        print("✅ Successfully added table to workflow!")
        print(f"Table Name: {documented_table.table_name}")
        print(f"Display Name: {documented_table.display_name}")
        print(f"Description: {documented_table.description}")
        print(f"Business Purpose: {documented_table.business_purpose}")
        print(f"Columns: {len(documented_table.columns)}")
        
        if documented_table.semantic_description:
            print("✅ Semantic description attached to documented table!")
            print(f"Semantic Description: {documented_table.semantic_description.get('description', 'No description')}")
        else:
            print("⚠️ No semantic description attached to documented table")
        
        # Test workflow state
        print()
        print("3. Testing Workflow State")
        print("-" * 40)
        state = workflow_service.get_workflow_state()
        print(f"Project: {state.get('project')}")
        print(f"Datasets: {len(state.get('datasets', []))}")
        print(f"Tables: {len(state.get('tables', []))}")
        
        if state.get('tables'):
            table = state['tables'][0]
            print(f"Table in state: {table.name}")
            print(f"Table metadata: {table.metadata}")
            
            if table.metadata and 'semantic_description' in table.metadata:
                print("✅ Semantic description stored in table metadata!")
            else:
                print("⚠️ Semantic description not found in table metadata")
        
        print()
        print("🎉 All tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Exception occurred: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_workflow_semantics()) 
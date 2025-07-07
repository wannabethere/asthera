#!/usr/bin/env python3
"""
Test script for the project workflow service with relationship recommendations
"""

import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.service.project_workflow_service import ProjectWorkflowService
from app.service.models import AddTableRequest, SchemaInput, ProjectContext

async def test_workflow_relationships():
    """Test the project workflow service with relationship recommendations"""
    
    print("Testing Project Workflow Service with Relationship Recommendations")
    print("=" * 70)
    
    # Create workflow service
    workflow_service = ProjectWorkflowService(user_id="test_user", session_id="test_session")
    
    # Create project context
    project_context = ProjectContext(
        project_id="test_project_123",
        project_name="E-commerce Analytics",
        business_domain="Retail",
        purpose="Analyze customer behavior and sales performance",
        target_users=["Data Analysts", "Business Managers", "Marketing Team"],
        key_business_concepts=["Customer Lifetime Value", "Sales Conversion", "Product Performance"],
        data_sources=["CRM System", "E-commerce Platform", "Payment Gateway"],
        compliance_requirements=["GDPR", "PCI DSS"]
    )
    
    # Create sample table schema
    schema_input = SchemaInput(
        table_name="order_items",
        table_description="Stores individual items within customer orders",
        columns=[
            {
                "name": "order_item_id",
                "display_name": "Order Item ID",
                "description": "Unique identifier for each order item",
                "data_type": "UUID",
                "is_primary_key": True,
                "is_nullable": False
            },
            {
                "name": "order_id",
                "display_name": "Order ID",
                "description": "Reference to the parent order",
                "data_type": "UUID",
                "is_primary_key": False,
                "is_nullable": False,
                "is_foreign_key": True
            },
            {
                "name": "product_id",
                "display_name": "Product ID",
                "description": "Reference to the product being ordered",
                "data_type": "UUID",
                "is_primary_key": False,
                "is_nullable": False,
                "is_foreign_key": True
            },
            {
                "name": "quantity",
                "display_name": "Quantity",
                "description": "Number of units ordered",
                "data_type": "INTEGER",
                "is_primary_key": False,
                "is_nullable": False
            },
            {
                "name": "unit_price",
                "display_name": "Unit Price",
                "description": "Price per unit at time of order",
                "data_type": "DECIMAL(10,2)",
                "is_primary_key": False,
                "is_nullable": False
            },
            {
                "name": "total_price",
                "display_name": "Total Price",
                "description": "Total price for this item (quantity * unit_price)",
                "data_type": "DECIMAL(10,2)",
                "is_primary_key": False,
                "is_nullable": False
            }
        ]
    )
    
    # Create add table request
    add_table_request = AddTableRequest(
        dataset_id="dataset_123",
        schema=schema_input
    )
    
    print(f"Project: {project_context.project_name}")
    print(f"Business Domain: {project_context.business_domain}")
    print(f"Table: {schema_input.table_name}")
    print(f"Description: {schema_input.table_description}")
    print(f"Columns: {len(schema_input.columns)}")
    print()
    
    try:
        # Test relationship recommendation generation
        print("1. Testing Relationship Recommendation Generation")
        print("-" * 50)
        
        relationship_recommendations = await workflow_service.get_relationship_recommendation_for_table(
            add_table_request, project_context
        )
        
        print("✅ Successfully generated relationship recommendations!")
        print()
        
        if relationship_recommendations:
            print("Relationships Found:")
            print("-" * 30)
            for rel in relationship_recommendations.get("relationships", []):
                print(f"• {rel.get('source_table')} → {rel.get('target_table')}")
                print(f"  Type: {rel.get('relationship_type')}")
                print(f"  Columns: {rel.get('source_column')} → {rel.get('target_column')}")
                print(f"  Explanation: {rel.get('explanation')}")
                print(f"  Business Value: {rel.get('business_value')}")
                print(f"  Confidence: {rel.get('confidence_score')}")
                print()
            
            print("Summary:")
            print("-" * 30)
            summary = relationship_recommendations.get("summary", {})
            print(f"Total Relationships: {summary.get('total_relationships', 0)}")
            print(f"Primary Relationships: {', '.join(summary.get('primary_relationships', []))}")
            print()
            
            print("Recommendations:")
            print("-" * 30)
            for rec in summary.get("recommendations", []):
                print(f"• {rec}")
            print()
        
        # Test semantic description generation
        print("2. Testing Semantic Description Generation")
        print("-" * 50)
        
        semantic_description = await workflow_service.get_semantic_description_for_table(
            add_table_request, project_context
        )
        
        print("✅ Successfully generated semantic description!")
        print()
        
        if semantic_description:
            print("Semantic Description:")
            print("-" * 30)
            print(f"Description: {semantic_description.get('description', 'N/A')}")
            print(f"Purpose: {semantic_description.get('table_purpose', 'N/A')}")
            print(f"Business Context: {semantic_description.get('business_context', 'N/A')}")
            print()
            
            print("Key Columns:")
            print("-" * 30)
            for col in semantic_description.get("key_columns", []):
                print(f"• {col.get('name')}: {col.get('description')}")
            print()
        
        # Test adding table with both services
        print("3. Testing Table Addition with Both Services")
        print("-" * 50)
        
        documented_table = await workflow_service.add_table(add_table_request, project_context)
        
        print("✅ Successfully added table with both semantic description and relationship recommendations!")
        print()
        
        print("Documented Table Information:")
        print("-" * 30)
        print(f"Table Name: {documented_table.table_name}")
        print(f"Display Name: {documented_table.display_name}")
        print(f"Description: {documented_table.description}")
        print(f"Business Purpose: {documented_table.business_purpose}")
        print()
        
        print("Primary Use Cases:")
        print("-" * 30)
        for use_case in documented_table.primary_use_cases:
            print(f"• {use_case}")
        print()
        
        print("Key Relationships:")
        print("-" * 30)
        for relationship in documented_table.key_relationships:
            print(f"• {relationship}")
        print()
        
        # Check if semantic description and relationship recommendations are attached
        if documented_table.semantic_description:
            print("✅ Semantic description attached to documented table")
        else:
            print("⚠️ No semantic description attached")
            
        if documented_table.relationship_recommendations:
            print("✅ Relationship recommendations attached to documented table")
            print(f"   Found {len(documented_table.relationship_recommendations.get('relationships', []))} relationships")
        else:
            print("⚠️ No relationship recommendations attached")
        
        # Check workflow state
        print("\n4. Checking Workflow State")
        print("-" * 50)
        
        workflow_state = workflow_service.get_workflow_state()
        print(f"Tables in workflow: {len(workflow_state.get('tables', []))}")
        
        if workflow_state.get('tables'):
            table = workflow_state['tables'][0]
            print(f"Table metadata keys: {list(table.metadata.keys()) if hasattr(table, 'metadata') else 'No metadata'}")
            
            if hasattr(table, 'metadata') and table.metadata:
                if 'semantic_analysis' in table.metadata:
                    print("✅ Semantic analysis stored in table metadata")
                if 'relationship_recommendations' in table.metadata:
                    print("✅ Relationship recommendations stored in table metadata")
        
        print("\n🎉 All tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Exception occurred: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_workflow_relationships()) 
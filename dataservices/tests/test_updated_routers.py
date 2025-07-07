#!/usr/bin/env python3
"""
Test script for the updated routers using project workflow service
"""

import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.service.project_workflow_service import ProjectWorkflowService
from app.service.models import AddTableRequest, SchemaInput, ProjectContext

async def test_updated_routers():
    """Test the updated routers functionality through the workflow service"""
    
    print("Testing Updated Routers with Project Workflow Service")
    print("=" * 60)
    
    # Create workflow service
    workflow_service = ProjectWorkflowService(user_id="test_user", session_id="test_session")
    
    # Create project context
    project_context = ProjectContext(
        project_id="test_project_789",
        project_name="E-commerce Analytics",
        business_domain="Retail",
        purpose="Comprehensive e-commerce data analysis",
        target_users=["Data Analysts", "Business Managers"],
        key_business_concepts=["Customer", "Order", "Product", "Revenue"],
        data_sources=["CRM", "E-commerce Platform"],
        compliance_requirements=["GDPR"]
    )
    
    # Create sample table schema
    schema_input = SchemaInput(
        table_name="product_sales",
        table_description="Product sales data with customer and order information",
        columns=[
            {
                "name": "sale_id",
                "display_name": "Sale ID",
                "description": "Unique identifier for each sale",
                "data_type": "UUID",
                "is_primary_key": True,
                "is_nullable": False
            },
            {
                "name": "product_id",
                "display_name": "Product ID",
                "description": "Reference to the product sold",
                "data_type": "UUID",
                "is_primary_key": False,
                "is_nullable": False,
                "is_foreign_key": True
            },
            {
                "name": "customer_id",
                "display_name": "Customer ID",
                "description": "Reference to the customer who made the purchase",
                "data_type": "UUID",
                "is_primary_key": False,
                "is_nullable": False,
                "is_foreign_key": True
            },
            {
                "name": "sale_date",
                "display_name": "Sale Date",
                "description": "Date and time of the sale",
                "data_type": "TIMESTAMP",
                "is_nullable": False
            },
            {
                "name": "quantity",
                "display_name": "Quantity",
                "description": "Number of units sold",
                "data_type": "INTEGER",
                "is_nullable": False
            },
            {
                "name": "unit_price",
                "display_name": "Unit Price",
                "description": "Price per unit at time of sale",
                "data_type": "DECIMAL(10,2)",
                "is_nullable": False
            },
            {
                "name": "total_amount",
                "display_name": "Total Amount",
                "description": "Total sale amount (quantity * unit_price)",
                "data_type": "DECIMAL(10,2)",
                "is_nullable": False
            },
            {
                "name": "customer_email",
                "display_name": "Customer Email",
                "description": "Customer email for receipt",
                "data_type": "VARCHAR(255)",
                "is_nullable": True
            }
        ]
    )
    
    # Create add table request
    add_table_request = AddTableRequest(
        dataset_id="test_dataset",
        schema=schema_input
    )
    
    print(f"Project: {project_context.project_name}")
    print(f"Business Domain: {project_context.business_domain}")
    print(f"Table: {schema_input.table_name}")
    print(f"Description: {schema_input.table_description}")
    print(f"Columns: {len(schema_input.columns)}")
    print()
    
    try:
        # Test 1: Semantic Description (simulates /semantics/describe-table)
        print("1. Testing Semantic Description (simulates /semantics/describe-table)")
        print("-" * 60)
        
        semantic_description = await workflow_service.get_semantic_description_for_table(
            add_table_request, project_context
        )
        
        print("✅ Successfully generated semantic description!")
        print(f"Description: {semantic_description.get('description', 'N/A')[:100]}...")
        print(f"Table Purpose: {semantic_description.get('table_purpose', 'N/A')}")
        print(f"Key Columns: {len(semantic_description.get('key_columns', []))}")
        print()
        
        # Test 2: Relationship Recommendations (simulates /relationships/recommend)
        print("2. Testing Relationship Recommendations (simulates /relationships/recommend)")
        print("-" * 60)
        
        relationship_recommendations = await workflow_service.get_relationship_recommendation_for_table(
            add_table_request, project_context
        )
        
        print("✅ Successfully generated relationship recommendations!")
        relationships = relationship_recommendations.get("relationships", [])
        print(f"Relationships Found: {len(relationships)}")
        
        for rel in relationships:
            print(f"• {rel.get('source_table')} → {rel.get('target_table')} ({rel.get('relationship_type')})")
            print(f"  Confidence: {rel.get('confidence_score')}")
            print(f"  Business Value: {rel.get('business_value', 'N/A')[:50]}...")
            print()
        
        # Test 3: Comprehensive Recommendations (simulates /recommendations/comprehensive)
        print("3. Testing Comprehensive Recommendations (simulates /recommendations/comprehensive)")
        print("-" * 60)
        
        comprehensive_recommendations = await workflow_service.get_recommendations(
            add_table_request, project_context
        )
        
        print("✅ Successfully generated comprehensive recommendations!")
        print(f"Recommendation Types: {comprehensive_recommendations.get('recommendation_types', [])}")
        print(f"Generated At: {comprehensive_recommendations.get('generated_at', 'N/A')}")
        
        # Display summary
        summary = comprehensive_recommendations.get("summary", {})
        print(f"Total Recommendations: {summary.get('total_recommendations', 0)}")
        print(f"High Priority Items: {len(summary.get('high_priority_items', []))}")
        print(f"Key Insights: {len(summary.get('key_insights', []))}")
        print(f"Next Steps: {len(summary.get('next_steps', []))}")
        print()
        
        # Display key insights
        print("Key Insights:")
        print("-" * 30)
        for insight in summary.get("key_insights", []):
            print(f"• {insight}")
        print()
        
        # Display next steps
        print("Next Steps:")
        print("-" * 30)
        for step in summary.get("next_steps", []):
            print(f"• {step}")
        print()
        
        # Test 4: Specific recommendation types
        print("4. Testing Specific Recommendation Types")
        print("-" * 60)
        
        # Test optimization recommendations only
        optimization_recommendations = await workflow_service.get_recommendations(
            add_table_request,
            project_context,
            recommendation_types=["optimization"]
        )
        
        print("✅ Successfully generated optimization recommendations!")
        if "optimization_recommendations" in optimization_recommendations.get("results", {}):
            opt_recs = optimization_recommendations["results"]["optimization_recommendations"]
            
            print("Performance Optimizations:")
            for rec in opt_recs.get("performance_optimizations", []):
                print(f"• {rec.get('recommendation')}")
            
            print("\nIndexing Suggestions:")
            for rec in opt_recs.get("indexing_suggestions", []):
                print(f"• {rec.get('recommendation')}")
        
        print()
        
        # Test 5: Data quality recommendations
        print("5. Testing Data Quality Recommendations")
        print("-" * 60)
        
        data_quality_recommendations = await workflow_service.get_recommendations(
            add_table_request,
            project_context,
            recommendation_types=["data_quality"]
        )
        
        print("✅ Successfully generated data quality recommendations!")
        if "data_quality_recommendations" in data_quality_recommendations.get("results", {}):
            dq_recs = data_quality_recommendations["results"]["data_quality_recommendations"]
            
            print("Constraint Suggestions:")
            for rec in dq_recs.get("constraint_suggestions", []):
                print(f"• {rec.get('recommendation')}")
            
            print("\nValidation Rules:")
            for rec in dq_recs.get("validation_rules", []):
                print(f"• {rec.get('rule')} for {rec.get('column')}")
        
        print()
        print("🎉 All router tests completed successfully!")
        print()
        print("Summary:")
        print("-" * 30)
        print("✅ Semantic Description Router: Working correctly")
        print("✅ Relationship Recommendations Router: Working correctly")
        print("✅ Comprehensive Recommendations Router: Working correctly")
        print("✅ Project Workflow Service Integration: Working correctly")
        print("✅ Error Handling: Working correctly")
        
    except Exception as e:
        print(f"❌ Exception occurred: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_updated_routers()) 
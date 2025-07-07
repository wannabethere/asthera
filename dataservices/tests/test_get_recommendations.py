#!/usr/bin/env python3
"""
Test script for the get_recommendations method in project workflow service
"""

import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.service.project_workflow_service import ProjectWorkflowService
from app.service.models import AddTableRequest, SchemaInput, ProjectContext

async def test_get_recommendations():
    """Test the get_recommendations method with comprehensive recommendations"""
    
    print("Testing Project Workflow Service - get_recommendations Method")
    print("=" * 70)
    
    # Create workflow service
    workflow_service = ProjectWorkflowService(user_id="test_user", session_id="test_session")
    
    # Create project context
    project_context = ProjectContext(
        project_id="test_project_456",
        project_name="E-commerce Analytics Platform",
        business_domain="Retail",
        purpose="Comprehensive e-commerce data analysis and reporting",
        target_users=["Data Analysts", "Business Managers", "Marketing Team", "Developers"],
        key_business_concepts=["Customer Lifetime Value", "Sales Conversion", "Product Performance", "Inventory Management"],
        data_sources=["CRM System", "E-commerce Platform", "Payment Gateway", "Inventory System"],
        compliance_requirements=["GDPR", "PCI DSS", "SOX"]
    )
    
    # Create sample table schema with various data types for testing
    schema_input = SchemaInput(
        table_name="customer_orders",
        table_description="Comprehensive customer order information with detailed tracking",
        columns=[
            {
                "name": "order_id",
                "display_name": "Order ID",
                "description": "Unique identifier for each order",
                "data_type": "UUID",
                "is_primary_key": True,
                "is_nullable": False
            },
            {
                "name": "customer_id",
                "display_name": "Customer ID",
                "description": "Reference to the customer who placed the order",
                "data_type": "UUID",
                "is_primary_key": False,
                "is_nullable": False,
                "is_foreign_key": True
            },
            {
                "name": "order_date",
                "display_name": "Order Date",
                "description": "Date and time when the order was placed",
                "data_type": "TIMESTAMP",
                "is_nullable": False
            },
            {
                "name": "total_amount",
                "display_name": "Total Amount",
                "description": "Total cost of the order including tax and shipping",
                "data_type": "DECIMAL(10,2)",
                "is_nullable": False
            },
            {
                "name": "status",
                "display_name": "Order Status",
                "description": "Current status of the order (pending, shipped, delivered, etc.)",
                "data_type": "VARCHAR(255)",
                "is_nullable": False
            },
            {
                "name": "customer_email",
                "display_name": "Customer Email",
                "description": "Email address for order notifications",
                "data_type": "VARCHAR(255)",
                "is_nullable": True
            },
            {
                "name": "customer_phone",
                "display_name": "Customer Phone",
                "description": "Phone number for delivery coordination",
                "data_type": "VARCHAR(20)",
                "is_nullable": True
            },
            {
                "name": "shipping_address_id",
                "display_name": "Shipping Address ID",
                "description": "Reference to the shipping address for this order",
                "data_type": "UUID",
                "is_primary_key": False,
                "is_nullable": True,
                "is_foreign_key": True
            },
            {
                "name": "product_id",
                "display_name": "Product ID",
                "description": "Reference to the main product in this order",
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
                "is_nullable": False
            },
            {
                "name": "unit_price",
                "display_name": "Unit Price",
                "description": "Price per unit at time of order",
                "data_type": "DECIMAL(10,2)",
                "is_nullable": False
            },
            {
                "name": "discount_amount",
                "display_name": "Discount Amount",
                "description": "Discount applied to this order",
                "data_type": "DECIMAL(10,2)",
                "is_nullable": True
            },
            {
                "name": "tax_amount",
                "display_name": "Tax Amount",
                "description": "Tax amount for this order",
                "data_type": "DECIMAL(10,2)",
                "is_nullable": False
            },
            {
                "name": "shipping_cost",
                "display_name": "Shipping Cost",
                "description": "Shipping cost for this order",
                "data_type": "DECIMAL(10,2)",
                "is_nullable": False
            },
            {
                "name": "payment_method",
                "display_name": "Payment Method",
                "description": "Method used for payment (credit_card, paypal, etc.)",
                "data_type": "VARCHAR(50)",
                "is_nullable": False
            },
            {
                "name": "tracking_number",
                "display_name": "Tracking Number",
                "description": "Shipping tracking number",
                "data_type": "VARCHAR(100)",
                "is_nullable": True
            },
            {
                "name": "estimated_delivery",
                "display_name": "Estimated Delivery",
                "description": "Estimated delivery date",
                "data_type": "TIMESTAMP",
                "is_nullable": True
            },
            {
                "name": "actual_delivery",
                "display_name": "Actual Delivery",
                "description": "Actual delivery date",
                "data_type": "TIMESTAMP",
                "is_nullable": True
            },
            {
                "name": "customer_feedback_url",
                "display_name": "Customer Feedback URL",
                "description": "URL for customer feedback survey",
                "data_type": "VARCHAR(500)",
                "is_nullable": True
            },
            {
                "name": "notes",
                "display_name": "Order Notes",
                "description": "Additional notes about the order",
                "data_type": "TEXT",
                "is_nullable": True
            }
        ]
    )
    
    # Create add table request
    add_table_request = AddTableRequest(
        dataset_id="dataset_456",
        schema=schema_input
    )
    
    print(f"Project: {project_context.project_name}")
    print(f"Business Domain: {project_context.business_domain}")
    print(f"Table: {schema_input.table_name}")
    print(f"Description: {schema_input.table_description}")
    print(f"Columns: {len(schema_input.columns)}")
    print()
    
    try:
        # Test 1: Get all recommendations (default)
        print("1. Testing get_recommendations with all types (default)")
        print("-" * 60)
        
        all_recommendations = await workflow_service.get_recommendations(
            add_table_request, project_context
        )
        
        print("✅ Successfully generated comprehensive recommendations!")
        print(f"Recommendation Types: {all_recommendations.get('recommendation_types', [])}")
        print(f"Generated At: {all_recommendations.get('generated_at', 'N/A')}")
        print()
        
        # Display summary
        summary = all_recommendations.get("summary", {})
        print("Summary:")
        print("-" * 30)
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
        
        # Display high priority items
        print("High Priority Items:")
        print("-" * 30)
        for item in summary.get("high_priority_items", []):
            print(f"• {item.get('type').title()}: {item.get('description')}")
            if item.get('confidence'):
                print(f"  Confidence: {item.get('confidence')}")
            if item.get('impact'):
                print(f"  Impact: {item.get('impact')}")
            print()
        
        # Test 2: Get specific recommendation types
        print("2. Testing get_recommendations with specific types")
        print("-" * 60)
        
        specific_recommendations = await workflow_service.get_recommendations(
            add_table_request, 
            project_context,
            recommendation_types=["semantic", "relationships"]
        )
        
        print("✅ Successfully generated specific recommendations!")
        print(f"Requested Types: {specific_recommendations.get('recommendation_types', [])}")
        print(f"Generated Results: {list(specific_recommendations.get('results', {}).keys())}")
        print()
        
        # Test 3: Get optimization recommendations only
        print("3. Testing optimization recommendations")
        print("-" * 60)
        
        optimization_recommendations = await workflow_service.get_recommendations(
            add_table_request,
            project_context,
            recommendation_types=["optimization"]
        )
        
        if "optimization_recommendations" in optimization_recommendations.get("results", {}):
            opt_recs = optimization_recommendations["results"]["optimization_recommendations"]
            
            print("Performance Optimizations:")
            print("-" * 30)
            for rec in opt_recs.get("performance_optimizations", []):
                print(f"• {rec.get('recommendation')}")
                print(f"  Priority: {rec.get('priority')}")
                print(f"  Impact: {rec.get('impact')}")
                print()
            
            print("Structure Improvements:")
            print("-" * 30)
            for rec in opt_recs.get("structure_improvements", []):
                print(f"• {rec.get('recommendation')}")
                print(f"  Priority: {rec.get('priority')}")
                print(f"  Impact: {rec.get('impact')}")
                print()
            
            print("Indexing Suggestions:")
            print("-" * 30)
            for rec in opt_recs.get("indexing_suggestions", []):
                print(f"• {rec.get('recommendation')}")
                print(f"  Priority: {rec.get('priority')}")
                print(f"  Impact: {rec.get('impact')}")
                print()
        
        # Test 4: Get data quality recommendations only
        print("4. Testing data quality recommendations")
        print("-" * 60)
        
        data_quality_recommendations = await workflow_service.get_recommendations(
            add_table_request,
            project_context,
            recommendation_types=["data_quality"]
        )
        
        if "data_quality_recommendations" in data_quality_recommendations.get("results", {}):
            dq_recs = data_quality_recommendations["results"]["data_quality_recommendations"]
            
            print("Constraint Suggestions:")
            print("-" * 30)
            for rec in dq_recs.get("constraint_suggestions", []):
                print(f"• {rec.get('recommendation')}")
                print(f"  Priority: {rec.get('priority')}")
                print(f"  Impact: {rec.get('impact')}")
                print()
            
            print("Validation Rules:")
            print("-" * 30)
            for rec in dq_recs.get("validation_rules", []):
                print(f"• {rec.get('rule')} for {rec.get('column')}")
                print(f"  Priority: {rec.get('priority')}")
                print(f"  Pattern: {rec.get('pattern')}")
                print()
            
            print("Monitoring Recommendations:")
            print("-" * 30)
            for rec in dq_recs.get("monitoring_recommendations", []):
                print(f"• {rec.get('recommendation')}")
                print(f"  Type: {rec.get('type')}")
                print(f"  Priority: {rec.get('priority')}")
                print()
        
        print("🎉 All get_recommendations tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Exception occurred: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_get_recommendations()) 
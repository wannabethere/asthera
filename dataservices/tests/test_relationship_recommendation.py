#!/usr/bin/env python3
"""
Test script for the relationship recommendation service
"""

import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.agents.relationship_recommendation import RelationshipRecommendation

async def test_relationship_recommendation():
    """Test the relationship recommendation service with sample table data"""
    
    # Sample table data
    table_data = {
        "name": "orders",
        "display_name": "Customer Orders",
        "description": "Stores customer order information including items, quantities, and status",
        "columns": [
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
                "data_type": "VARCHAR(50)",
                "is_nullable": False
            },
            {
                "name": "shipping_address_id",
                "display_name": "Shipping Address ID",
                "description": "Reference to the shipping address for this order",
                "data_type": "UUID",
                "is_primary_key": False,
                "is_nullable": True,
                "is_foreign_key": True
            }
        ]
    }
    
    print("Testing Relationship Recommendation Service")
    print("=" * 60)
    print(f"Table: {table_data['display_name']}")
    print(f"Description: {table_data['description']}")
    print(f"Columns: {len(table_data['columns'])}")
    print()
    
    try:
        # Create relationship recommendation service instance
        recommendation_service = RelationshipRecommendation()
        
        # Generate recommendations
        result = await recommendation_service.recommend(
            RelationshipRecommendation.Input(
                id="test_orders_table",
                table_data=table_data,
                project_id="test_project"
            )
        )
        
        print("Result Status:", result.status)
        print()
        
        if result.status == "finished" and result.response:
            print("✅ Successfully generated relationship recommendations!")
            print()
            
            response = result.response
            
            print("Relationships:")
            print("-" * 30)
            for rel in response.get("relationships", []):
                print(f"• {rel.get('source_table')} → {rel.get('target_table')}")
                print(f"  Type: {rel.get('relationship_type')}")
                print(f"  Columns: {rel.get('source_column')} → {rel.get('target_column')}")
                print(f"  Explanation: {rel.get('explanation')}")
                print(f"  Business Value: {rel.get('business_value')}")
                print(f"  Confidence: {rel.get('confidence_score')}")
                print()
            
            print("Summary:")
            print("-" * 30)
            summary = response.get("summary", {})
            print(f"Total Relationships: {summary.get('total_relationships', 0)}")
            print(f"Primary Relationships: {', '.join(summary.get('primary_relationships', []))}")
            print()
            
            print("Recommendations:")
            print("-" * 30)
            for rec in summary.get("recommendations", []):
                print(f"• {rec}")
            print()
                
        elif result.status == "failed":
            print("❌ Failed to generate relationship recommendations")
            print(f"Error: {result.error.message if result.error else 'Unknown error'}")
        else:
            print("⚠️ Unexpected result status:", result.status)
            
    except Exception as e:
        print(f"❌ Exception occurred: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_relationship_recommendation()) 
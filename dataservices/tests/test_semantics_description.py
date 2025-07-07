#!/usr/bin/env python3
"""
Test script for the semantics description service
"""

import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.agents.semantics_description import SemanticsDescription

async def test_semantics_description():
    """Test the semantics description service with sample table data"""
    
    # Sample table data
    table_data = {
        "name": "customers",
        "display_name": "Customer Information",
        "description": "Stores customer master data including contact information and account details",
        "columns": [
            {
                "name": "customer_id",
                "display_name": "Customer ID",
                "description": "Unique identifier for each customer",
                "data_type": "UUID",
                "is_primary_key": True,
                "is_nullable": False
            },
            {
                "name": "email",
                "display_name": "Email Address",
                "description": "Customer's primary email address",
                "data_type": "VARCHAR(255)",
                "is_nullable": False
            },
            {
                "name": "first_name",
                "display_name": "First Name",
                "description": "Customer's first name",
                "data_type": "VARCHAR(100)",
                "is_nullable": True
            },
            {
                "name": "last_name",
                "display_name": "Last Name",
                "description": "Customer's last name",
                "data_type": "VARCHAR(100)",
                "is_nullable": True
            },
            {
                "name": "created_at",
                "display_name": "Created Date",
                "description": "Timestamp when customer record was created",
                "data_type": "TIMESTAMP",
                "is_nullable": False
            },
            {
                "name": "status",
                "display_name": "Account Status",
                "description": "Current status of the customer account",
                "data_type": "VARCHAR(20)",
                "is_nullable": False
            }
        ]
    }
    
    print("Testing Semantics Description Service")
    print("=" * 50)
    print(f"Table: {table_data['display_name']}")
    print(f"Description: {table_data['description']}")
    print(f"Columns: {len(table_data['columns'])}")
    print()
    
    try:
        # Create semantics description service instance
        semantics_service = SemanticsDescription()
        
        # Generate description
        result = await semantics_service.describe(
            SemanticsDescription.Input(
                id="test_customers_table",
                table_data=table_data,
                project_id="test_project"
            )
        )
        
        print("Result Status:", result.status)
        print()
        
        if result.status == "finished" and result.response:
            print("✅ Successfully generated semantic description!")
            print()
            print("Generated Description:")
            print("-" * 30)
            print(result.response.get("description", "No description"))
            print()
            
            print("Table Purpose:")
            print("-" * 30)
            print(result.response.get("table_purpose", "No purpose specified"))
            print()
            
            print("Key Columns:")
            print("-" * 30)
            for col in result.response.get("key_columns", []):
                print(f"• {col.get('name')}: {col.get('description')}")
                print(f"  Business Significance: {col.get('business_significance')}")
                print(f"  Data Type: {col.get('data_type')}")
                print()
            
            print("Business Context:")
            print("-" * 30)
            print(result.response.get("business_context", "No context provided"))
            print()
            
            print("Data Patterns:")
            print("-" * 30)
            for pattern in result.response.get("data_patterns", []):
                print(f"• {pattern}")
            print()
            
            print("Suggested Relationships:")
            print("-" * 30)
            for rel in result.response.get("suggested_relationships", []):
                print(f"• {rel.get('related_entity')} ({rel.get('relationship_type')})")
                print(f"  Reasoning: {rel.get('reasoning')}")
                print()
                
        elif result.status == "failed":
            print("❌ Failed to generate semantic description")
            print(f"Error: {result.error.message if result.error else 'Unknown error'}")
        else:
            print("⚠️ Unexpected result status:", result.status)
            
    except Exception as e:
        print(f"❌ Exception occurred: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_semantics_description()) 
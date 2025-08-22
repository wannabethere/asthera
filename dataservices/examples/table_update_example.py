#!/usr/bin/env python3
"""
Example script demonstrating how to use the new table update APIs
"""

import asyncio
import json
from typing import Dict, Any

# Example request data for updating a table
def create_update_table_request(
    dataset_id: str,
    table_name: str,
    columns: list,
    update_description: bool = True,
    update_columns: bool = True,
    update_enhanced_metadata: bool = True,
    preserve_existing_metadata: bool = False
) -> Dict[str, Any]:
    """
    Create an UpdateTableRequest payload for the API
    
    Args:
        dataset_id: ID of the dataset containing the table
        table_name: Name of the table to update
        columns: List of column definitions
        update_description: Whether to update table description
        update_columns: Whether to update column definitions
        update_enhanced_metadata: Whether to update enhanced metadata
        preserve_existing_metadata: Whether to preserve existing metadata
    
    Returns:
        Dict containing the request payload
    """
    
    return {
        "dataset_id": dataset_id,
        "schema": {
            "table_name": table_name,
            "columns": columns
        },
        "update_description": update_description,
        "update_columns": update_columns,
        "update_enhanced_metadata": update_enhanced_metadata,
        "preserve_existing_metadata": preserve_existing_metadata
    }

def create_sample_columns() -> list:
    """Create sample column definitions for testing"""
    return [
        {
            "name": "customer_id",
            "display_name": "Customer ID",
            "description": "Unique identifier for each customer",
            "data_type": "VARCHAR(50)",
            "is_nullable": False,
            "is_primary_key": True,
            "is_foreign_key": False,
            "usage_type": "identifier"
        },
        {
            "name": "customer_name",
            "display_name": "Customer Name",
            "description": "Full name of the customer",
            "data_type": "VARCHAR(255)",
            "is_nullable": False,
            "is_primary_key": False,
            "is_foreign_key": False,
            "usage_type": "dimension"
        },
        {
            "name": "email",
            "display_name": "Email Address",
            "description": "Customer's email address",
            "data_type": "VARCHAR(255)",
            "is_nullable": True,
            "is_primary_key": False,
            "is_foreign_key": False,
            "usage_type": "attribute"
        },
        {
            "name": "created_date",
            "display_name": "Created Date",
            "description": "Date when the customer record was created",
            "data_type": "TIMESTAMP",
            "is_nullable": False,
            "is_primary_key": False,
            "is_foreign_key": False,
            "usage_type": "timestamp"
        }
    ]

async def demonstrate_table_updates():
    """Demonstrate different table update scenarios"""
    
    print("=== Table Update API Examples ===\n")
    
    # Example 1: Full table update (PUT endpoint)
    print("1. Full Table Update (PUT /workflow/table/{table_id})")
    print("   - Updates all aspects of the table")
    print("   - Replaces existing data completely")
    
    full_update_request = create_update_table_request(
        dataset_id="dataset_123",
        table_name="customers",
        columns=create_sample_columns(),
        update_description=True,
        update_columns=True,
        update_enhanced_metadata=True,
        preserve_existing_metadata=False
    )
    
    print(f"   Request payload:")
    print(json.dumps(full_update_request, indent=2))
    print()
    
    # Example 2: Partial table update - columns only (PATCH endpoint)
    print("2. Partial Update - Columns Only (PATCH /workflow/table/{table_id})")
    print("   - Updates only column definitions")
    print("   - Preserves existing enhanced metadata")
    
    columns_only_request = create_update_table_request(
        dataset_id="dataset_123",
        table_name="customers",
        columns=create_sample_columns(),
        update_description=False,
        update_columns=True,
        update_enhanced_metadata=False,
        preserve_existing_metadata=True
    )
    
    print(f"   Request payload:")
    print(json.dumps(columns_only_request, indent=2))
    print()
    
    # Example 3: Partial table update - enhanced metadata only (PATCH endpoint)
    print("3. Partial Update - Enhanced Metadata Only (PATCH /workflow/table/{table_id})")
    print("   - Updates only enhanced metadata and descriptions")
    print("   - Preserves existing column definitions")
    
    metadata_only_request = create_update_table_request(
        dataset_id="dataset_123",
        table_name="customers",
        columns=create_sample_columns(),  # Still needed for LLM processing
        update_description=True,
        update_columns=False,
        update_enhanced_metadata=True,
        preserve_existing_metadata=True
    )
    
    print(f"   Request payload:")
    print(json.dumps(metadata_only_request, indent=2))
    print()
    
    # Example 4: Minimal update - description only (PATCH endpoint)
    print("4. Minimal Update - Description Only (PATCH /workflow/table/{table_id})")
    print("   - Updates only table description")
    print("   - Preserves all existing data")
    
    description_only_request = create_update_table_request(
        dataset_id="dataset_123",
        table_name="customers",
        columns=create_sample_columns(),  # Still needed for LLM processing
        update_description=True,
        update_columns=False,
        update_enhanced_metadata=False,
        preserve_existing_metadata=True
    )
    
    print(f"   Request payload:")
    print(json.dumps(description_only_request, indent=2))
    print()
    
    # Example 5: Selective column update
    print("5. Selective Column Update")
    print("   - Update specific columns while preserving others")
    print("   - Useful for incremental schema changes")
    
    selective_columns = [
        {
            "name": "customer_id",
            "display_name": "Customer ID",
            "description": "Unique identifier for each customer",
            "data_type": "VARCHAR(100)",  # Increased size
            "is_nullable": False,
            "is_primary_key": True,
            "is_foreign_key": False,
            "usage_type": "identifier"
        },
        {
            "name": "phone_number",  # New column
            "display_name": "Phone Number",
            "description": "Customer's contact phone number",
            "data_type": "VARCHAR(20)",
            "is_nullable": True,
            "is_primary_key": False,
            "is_foreign_key": False,
            "usage_type": "attribute"
        }
    ]
    
    selective_update_request = create_update_table_request(
        dataset_id="dataset_123",
        table_name="customers",
        columns=selective_columns,
        update_description=False,
        update_columns=True,
        update_enhanced_metadata=False,
        preserve_existing_metadata=True
    )
    
    print(f"   Request payload:")
    print(json.dumps(selective_update_request, indent=2))
    print()

def print_api_endpoints():
    """Print the available API endpoints"""
    print("=== Available API Endpoints ===\n")
    
    print("POST   /workflow/table")
    print("       - Create a new table with enhanced documentation")
    print("       - Requires AddTableRequest")
    print()
    
    print("PUT    /workflow/table/{table_id}")
    print("       - Full table update (replace all data)")
    print("       - Creates table if it doesn't exist")
    print("       - Requires UpdateTableRequest")
    print()
    
    print("PATCH  /workflow/table/{table_id}")
    print("       - Partial table update (selective updates)")
    print("       - Requires UpdateTableRequest with selective flags")
    print()
    
    print("GET    /workflow/table/{table_id}/enhanced-columns")
    print("       - Retrieve enhanced column definitions")
    print()

def print_usage_notes():
    """Print important usage notes"""
    print("=== Usage Notes ===\n")
    
    print("• PUT endpoint: Use for complete table replacements")
    print("• PATCH endpoint: Use for selective updates")
    print("• All endpoints require domain to be in 'draft' or 'draft_ready' status")
    print("• Enhanced metadata includes LLM-generated insights")
    print("• Column updates will recreate all columns (can't update individual columns)")
    print("• Metadata updates preserve existing data unless explicitly overwritten")
    print("• All updates increment entity_version for tracking changes")
    print()

if __name__ == "__main__":
    print("Table Update API Examples")
    print("=" * 50)
    print()
    
    # Demonstrate the different update scenarios
    asyncio.run(demonstrate_table_updates())
    
    # Print API endpoint information
    print_api_endpoints()
    
    # Print usage notes
    print_usage_notes()
    
    print("For more information, check the API documentation and source code.")

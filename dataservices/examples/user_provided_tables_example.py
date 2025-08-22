#!/usr/bin/env python3
"""
Example: Using User-Provided Tables for Relationship Workflow

This example demonstrates how to use the new approach where users provide
table definitions directly instead of relying on domain ID lookup.

This gives users greater control over semantic definitions and relationships.
"""

import asyncio
import json
from typing import Dict, Any, List

# Example table definitions that users can provide
EXAMPLE_TABLES = [
    {
        "name": "customers",
        "display_name": "Customer Information",
        "description": "Stores customer details and demographics for sales analytics",
        "columns": [
            {
                "name": "customer_id",
                "data_type": "INTEGER",
                "description": "Unique customer identifier",
                "is_primary_key": True,
                "is_nullable": False,
                "usage_type": "identifier",
                "metadata": {
                    "business_description": "Primary identifier for customer records",
                    "example_values": ["1001", "1002", "1003"]
                }
            },
            {
                "name": "customer_name",
                "data_type": "VARCHAR(100)",
                "description": "Full name of the customer",
                "is_nullable": False,
                "usage_type": "attribute",
                "metadata": {
                    "business_description": "Customer's full legal name",
                    "example_values": ["John Smith", "Jane Doe", "Bob Johnson"]
                }
            },
            {
                "name": "email",
                "data_type": "VARCHAR(255)",
                "description": "Customer email address",
                "is_nullable": True,
                "usage_type": "identifier",
                "metadata": {
                    "business_description": "Primary contact email for customer communications",
                    "example_values": ["john@example.com", "jane@example.com"]
                }
            },
            {
                "name": "registration_date",
                "data_type": "TIMESTAMP",
                "description": "Date when customer first registered",
                "is_nullable": False,
                "usage_type": "timestamp",
                "metadata": {
                    "business_description": "Customer acquisition date for analytics",
                    "example_values": ["2024-01-15", "2024-02-20"]
                }
            }
        ],
        "metadata": {
            "business_context": {
                "business_entity": "Customer",
                "data_owner": "Sales Team",
                "update_frequency": "Daily",
                "privacy_level": "PII",
                "retention_policy": "7 years"
            }
        }
    },
    {
        "name": "orders",
        "display_name": "Customer Orders",
        "description": "Stores order information and line items for sales tracking",
        "columns": [
            {
                "name": "order_id",
                "data_type": "INTEGER",
                "description": "Unique order identifier",
                "is_primary_key": True,
                "is_nullable": False,
                "usage_type": "identifier",
                "metadata": {
                    "business_description": "Primary identifier for order records",
                    "example_values": ["5001", "5002", "5003"]
                }
            },
            {
                "name": "customer_id",
                "data_type": "INTEGER",
                "description": "Reference to customer who placed the order",
                "is_foreign_key": True,
                "is_nullable": False,
                "usage_type": "identifier",
                "metadata": {
                    "business_description": "Links order to customer record",
                    "example_values": ["1001", "1002", "1001"]
                }
            },
            {
                "name": "order_date",
                "data_type": "TIMESTAMP",
                "description": "Date and time when order was placed",
                "is_nullable": False,
                "usage_type": "timestamp",
                "metadata": {
                    "business_description": "Order creation timestamp for analytics",
                    "example_values": ["2024-03-01 10:30:00", "2024-03-02 14:15:00"]
                }
            },
            {
                "name": "total_amount",
                "data_type": "DECIMAL(10,2)",
                "description": "Total order amount in dollars",
                "is_nullable": False,
                "usage_type": "measure",
                "metadata": {
                    "business_description": "Total value of the order for revenue tracking",
                    "example_values": ["99.99", "149.50", "75.25"]
                }
            },
            {
                "name": "order_status",
                "data_type": "VARCHAR(20)",
                "description": "Current status of the order",
                "is_nullable": False,
                "usage_type": "attribute",
                "metadata": {
                    "business_description": "Order lifecycle status for tracking",
                    "example_values": ["pending", "confirmed", "shipped", "delivered"]
                }
            }
        ],
        "metadata": {
            "business_context": {
                "business_entity": "Order",
                "data_owner": "Operations Team",
                "update_frequency": "Real-time",
                "privacy_level": "Internal",
                "retention_policy": "5 years"
            }
        }
    },
    {
        "name": "products",
        "display_name": "Product Catalog",
        "description": "Stores product information and pricing",
        "columns": [
            {
                "name": "product_id",
                "data_type": "INTEGER",
                "description": "Unique product identifier",
                "is_primary_key": True,
                "is_nullable": False,
                "usage_type": "identifier",
                "metadata": {
                    "business_description": "Primary identifier for product records",
                    "example_values": ["2001", "2002", "2003"]
                }
            },
            {
                "name": "product_name",
                "data_type": "VARCHAR(200)",
                "description": "Name of the product",
                "is_nullable": False,
                "usage_type": "attribute",
                "metadata": {
                    "business_description": "Human-readable product name",
                    "example_values": ["Laptop Pro", "Wireless Mouse", "USB Cable"]
                }
            },
            {
                "name": "category_id",
                "data_type": "INTEGER",
                "description": "Reference to product category",
                "is_foreign_key": True,
                "is_nullable": True,
                "usage_type": "identifier",
                "metadata": {
                    "business_description": "Links product to category for organization",
                    "example_values": ["1", "2", "3"]
                }
            },
            {
                "name": "price",
                "data_type": "DECIMAL(8,2)",
                "description": "Product price in dollars",
                "is_nullable": False,
                "usage_type": "measure",
                "metadata": {
                    "business_description": "Current selling price for revenue calculations",
                    "example_values": ["999.99", "29.99", "9.99"]
                }
            },
            {
                "name": "stock_quantity",
                "data_type": "INTEGER",
                "description": "Available stock quantity",
                "is_nullable": False,
                "usage_type": "measure",
                "metadata": {
                    "business_description": "Current inventory level for supply chain",
                    "example_values": ["50", "100", "200"]
                }
            }
        ],
        "metadata": {
            "business_context": {
                "business_entity": "Product",
                "data_owner": "Product Team",
                "update_frequency": "Weekly",
                "privacy_level": "Public",
                "retention_policy": "Indefinite"
            }
        }
    }
]

# Enhanced business context for better relationship analysis
ENHANCED_BUSINESS_CONTEXT = {
    "industry": "E-commerce",
    "business_process": "Order Management",
    "key_metrics": [
        "Customer Lifetime Value",
        "Order Conversion Rate",
        "Average Order Value",
        "Customer Acquisition Cost"
    ],
    "data_governance": {
        "privacy_level": "PII",
        "retention_policy": "7 years",
        "access_control": "Role-based",
        "data_quality": "High"
    },
    "business_rules": [
        "One customer can have multiple orders",
        "Each order must have exactly one customer",
        "Products can be in multiple orders",
        "Customer email must be unique if provided"
    ],
    "reporting_needs": [
        "Sales performance by customer segment",
        "Product popularity analysis",
        "Customer behavior patterns",
        "Inventory optimization"
    ]
}

def create_relationship_request(domain_id: str, session_id: str = None) -> Dict[str, Any]:
    """
    Create a relationship workflow request with user-provided tables
    
    Args:
        domain_id: The domain ID for the workflow
        session_id: Optional session ID for workflow mode
        
    Returns:
        Dictionary representing the request payload
    """
    request = {
        "domain_id": domain_id,
        "domain_name": "Sales Analytics",
        "business_domain": "Sales",
        "tables": EXAMPLE_TABLES,
        "business_context": ENHANCED_BUSINESS_CONTEXT
    }
    
    if session_id:
        request["session_id"] = session_id
    
    return request

def print_request_summary(request: Dict[str, Any]):
    """Print a summary of the relationship request"""
    print("🔍 Relationship Workflow Request Summary")
    print("=" * 50)
    print(f"Domain ID: {request['domain_id']}")
    print(f"Domain Name: {request['domain_name']}")
    print(f"Business Domain: {request['business_domain']}")
    print(f"Session ID: {request.get('session_id', 'None (Standalone Mode)')}")
    print(f"Tables Count: {len(request['tables'])}")
    print(f"Business Context Keys: {list(request['business_context'].keys())}")
    
    print("\n📊 Table Details:")
    for i, table in enumerate(request['tables'], 1):
        print(f"  {i}. {table['name']} ({table['display_name']})")
        print(f"     Columns: {len(table['columns'])}")
        print(f"     Description: {table['description']}")
        
        # Show key columns
        key_columns = [col for col in table['columns'] if col.get('is_primary_key') or col.get('is_foreign_key')]
        if key_columns:
            print(f"     Key Columns: {[col['name'] for col in key_columns]}")
    
    print("\n🏢 Business Context:")
    for key, value in request['business_context'].items():
        if isinstance(value, list):
            print(f"  {key}: {len(value)} items")
        elif isinstance(value, dict):
            print(f"  {key}: {len(value)} sub-items")
        else:
            print(f"  {key}: {value}")

def simulate_api_call(request: Dict[str, Any], endpoint: str):
    """
    Simulate an API call to the relationship workflow endpoints
    
    Args:
        request: The request payload
        endpoint: The endpoint being called
    """
    print(f"\n🚀 Simulating API Call to: {endpoint}")
    print("-" * 40)
    
    # Simulate request validation
    print("✅ Request validation passed")
    print(f"✅ {len(request['tables'])} tables provided")
    print(f"✅ Business context included")
    
    # Simulate processing
    print("🔄 Processing tables for relationship analysis...")
    print("🔄 Building enhanced MDL representation...")
    print("🔄 Calling LLM relationship service...")
    
    # Simulate results
    total_relationships = len(request['tables']) * 2  # Rough estimate
    print(f"✅ Generated {total_relationships} relationship recommendations")
    
    return {
        "status": "success",
        "total_tables": len(request['tables']),
        "total_relationships": total_relationships,
        "user_provided_tables": True,
        "enhanced_context": True
    }

def main():
    """Main function demonstrating the user-provided tables approach"""
    print("🎯 User-Provided Tables Relationship Workflow Example")
    print("=" * 60)
    print("This example shows how users can provide table definitions directly")
    print("instead of relying on domain ID lookup for greater control.\n")
    
    # Create request for workflow mode
    workflow_request = create_relationship_request("sales_analytics_001", "session_123")
    print("📋 WORKFLOW MODE REQUEST:")
    print_request_summary(workflow_request)
    
    # Simulate API call to workflow endpoint
    workflow_result = simulate_api_call(workflow_request, "/workflow/relationships/recommendations")
    
    print(f"\n📈 Workflow Mode Results:")
    for key, value in workflow_result.items():
        print(f"  {key}: {value}")
    
    # Create request for standalone mode
    standalone_request = create_relationship_request("sales_analytics_001")  # No session_id
    print("\n\n📋 STANDALONE MODE REQUEST:")
    print_request_summary(standalone_request)
    
    # Simulate API call to standalone endpoint
    standalone_result = simulate_api_call(standalone_request, "/workflow/relationships/analyze-tables")
    
    print(f"\n📈 Standalone Mode Results:")
    for key, value in standalone_result.items():
        print(f"  {key}: {value}")
    
    print("\n\n🎉 Example completed successfully!")
    print("\nKey Benefits of User-Provided Tables:")
    print("✅ Greater control over semantic definitions")
    print("✅ Flexibility to analyze tables from different sources")
    print("✅ Enhanced business context for better analysis")
    print("✅ Standalone usage without workflow setup")
    print("✅ Better understanding of business relationships")

if __name__ == "__main__":
    main()

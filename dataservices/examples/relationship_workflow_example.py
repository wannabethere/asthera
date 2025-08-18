"""
Relationship Workflow Example
Demonstrates the complete workflow for managing relationships in a domain

This example shows how to:
1. Create a domain and add tables to the workflow
2. Generate comprehensive relationship recommendations using LLM
3. Add custom relationships based on business knowledge
4. Manage and validate the relationship workflow
5. Commit the workflow with relationships defined

The relationship workflow step is essential for creating the MDL schema and should
be performed after all tables have been added to the workflow.
"""

import asyncio
import json
import logging
from typing import Dict, Any, List
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RelationshipWorkflowExample:
    """Example class demonstrating the relationship workflow step"""
    
    def __init__(self):
        self.user_id = "example_user_123"
        self.session_id = f"workflow_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.domain_id = "example_domain_456"
        
        # Mock domain context
        self.domain_context = {
            "domain_id": self.domain_id,
            "domain_name": "Example Business Domain",
            "business_domain": "E-commerce and Customer Management",
            "purpose": "Manage customer data, orders, and product information",
            "target_users": ["Business Analysts", "Data Scientists", "Product Managers"],
            "key_business_concepts": ["Customer Analytics", "Order Management", "Product Performance"],
            "data_sources": ["CRM System", "E-commerce Platform", "Analytics Tools"],
            "compliance_requirements": ["GDPR", "Data Privacy"]
        }
        
        # Sample table schemas for the example
        self.sample_tables = [
            {
                "name": "customers",
                "description": "Customer information and demographics",
                "columns": [
                    {"name": "customer_id", "data_type": "VARCHAR(50)", "is_primary_key": True, "description": "Unique customer identifier"},
                    {"name": "first_name", "data_type": "VARCHAR(100)", "description": "Customer first name"},
                    {"name": "last_name", "data_type": "VARCHAR(100)", "description": "Customer last name"},
                    {"name": "email", "data_type": "VARCHAR(255)", "description": "Customer email address"},
                    {"name": "phone", "data_type": "VARCHAR(20)", "description": "Customer phone number"},
                    {"name": "registration_date", "data_type": "TIMESTAMP", "description": "Date customer registered"},
                    {"name": "status", "data_type": "VARCHAR(20)", "description": "Customer status (active, inactive, suspended)"}
                ]
            },
            {
                "name": "orders",
                "description": "Customer order information",
                "columns": [
                    {"name": "order_id", "data_type": "VARCHAR(50)", "is_primary_key": True, "description": "Unique order identifier"},
                    {"name": "customer_id", "data_type": "VARCHAR(50)", "is_foreign_key": True, "description": "Reference to customer"},
                    {"name": "order_date", "data_type": "TIMESTAMP", "description": "Date order was placed"},
                    {"name": "total_amount", "data_type": "DECIMAL(10,2)", "description": "Total order amount"},
                    {"name": "status", "data_type": "VARCHAR(20)", "description": "Order status (pending, confirmed, shipped, delivered)"},
                    {"name": "shipping_address", "data_type": "TEXT", "description": "Shipping address details"}
                ]
            },
            {
                "name": "products",
                "description": "Product catalog information",
                "columns": [
                    {"name": "product_id", "data_type": "VARCHAR(50)", "is_primary_key": True, "description": "Unique product identifier"},
                    {"name": "name", "data_type": "VARCHAR(255)", "description": "Product name"},
                    {"name": "description", "data_type": "TEXT", "description": "Product description"},
                    {"name": "category_id", "data_type": "VARCHAR(50)", "is_foreign_key": True, "description": "Reference to product category"},
                    {"name": "price", "data_type": "DECIMAL(10,2)", "description": "Product price"},
                    {"name": "stock_quantity", "data_type": "INTEGER", "description": "Available stock quantity"},
                    {"name": "is_active", "data_type": "BOOLEAN", "description": "Whether product is active"}
                ]
            },
            {
                "name": "order_items",
                "description": "Individual items within orders",
                "columns": [
                    {"name": "order_item_id", "data_type": "VARCHAR(50)", "is_primary_key": True, "description": "Unique order item identifier"},
                    {"name": "order_id", "data_type": "VARCHAR(50)", "is_foreign_key": True, "description": "Reference to order"},
                    {"name": "product_id", "data_type": "VARCHAR(50)", "is_foreign_key": True, "description": "Reference to product"},
                    {"name": "quantity", "data_type": "INTEGER", "description": "Quantity ordered"},
                    {"name": "unit_price", "data_type": "DECIMAL(10,2)", "description": "Unit price at time of order"},
                    {"name": "total_price", "data_type": "DECIMAL(10,2)", "description": "Total price for this item"}
                ]
            },
            {
                "name": "categories",
                "description": "Product category classification",
                "columns": [
                    {"name": "category_id", "data_type": "VARCHAR(50)", "is_primary_key": True, "description": "Unique category identifier"},
                    {"name": "name", "data_type": "VARCHAR(100)", "description": "Category name"},
                    {"name": "description", "data_type": "TEXT", "description": "Category description"},
                    {"name": "parent_category_id", "data_type": "VARCHAR(50)", "is_foreign_key": True, "description": "Reference to parent category (for hierarchy)"},
                    {"name": "is_active", "data_type": "BOOLEAN", "description": "Whether category is active"}
                ]
            }
        ]

    async def run_complete_workflow(self):
        """Run the complete relationship workflow example"""
        logger.info("Starting Relationship Workflow Example")
        logger.info("=" * 50)
        
        try:
            # Step 1: Initialize the workflow
            await self.initialize_workflow()
            
            # Step 2: Add tables to the workflow
            await self.add_tables_to_workflow()
            
            # Step 3: Generate relationship recommendations
            await self.generate_relationship_recommendations()
            
            # Step 4: Add custom relationships
            await self.add_custom_relationships()
            
            # Step 5: Review and validate workflow
            await self.review_and_validate_workflow()
            
            # Step 6: Show final workflow state
            await self.show_final_workflow_state()
            
            # Step 7: Demonstrate workflow management operations
            await self.demonstrate_workflow_management()
            
            logger.info("Relationship Workflow Example completed successfully!")
            
        except Exception as e:
            logger.error(f"Error in workflow example: {str(e)}")
            raise

    async def initialize_workflow(self):
        """Initialize the domain workflow"""
        logger.info("Step 1: Initializing Domain Workflow")
        
        # In a real implementation, you would use the actual DomainWorkflowService
        # For this example, we'll simulate the workflow state
        self.workflow_state = {
            "domain": self.domain_context,
            "context": None,
            "datasets": [],
            "tables": [],
            "relationships": [],
            "relationship_recommendations": None
        }
        
        logger.info(f"✓ Workflow initialized for domain: {self.domain_context['domain_name']}")
        logger.info(f"✓ Session ID: {self.session_id}")

    async def add_tables_to_workflow(self):
        """Add sample tables to the workflow"""
        logger.info("Step 2: Adding Tables to Workflow")
        
        for table_schema in self.sample_tables:
            # Simulate adding table to workflow
            table_data = {
                "name": table_schema["name"],
                "description": table_schema["description"],
                "columns": table_schema["columns"],
                "added_at": datetime.now().isoformat()
            }
            
            self.workflow_state["tables"].append(table_data)
            logger.info(f"✓ Added table: {table_schema['name']} with {len(table_schema['columns'])} columns")
        
        logger.info(f"✓ Total tables in workflow: {len(self.workflow_state['tables'])}")

    async def generate_relationship_recommendations(self):
        """Generate comprehensive relationship recommendations using LLM"""
        logger.info("Step 3: Generating Relationship Recommendations")
        
        # Simulate LLM-generated relationship recommendations from existing service
        recommendations = {
            "domain_id": self.domain_id,
            "total_tables": len(self.workflow_state["tables"]),
            "generated_at": datetime.now().isoformat(),
            "relationships": [
                {
                    "from_table": "orders",
                    "to_table": "customers",
                    "from_column": "customer_id",
                    "to_column": "customer_id",
                    "relationship_type": "many_to_one",
                    "confidence_score": 0.95,
                    "reasoning": "Orders table has customer_id foreign key that references customers table primary key",
                    "suggested_action": "Implement foreign key constraint",
                    "source": "llm_generated"
                },
                {
                    "from_table": "order_items",
                    "to_table": "orders",
                    "from_column": "order_id",
                    "to_column": "order_id",
                    "relationship_type": "many_to_one",
                    "confidence_score": 0.95,
                    "reasoning": "Order items belong to orders - clear parent-child relationship",
                    "suggested_action": "Implement foreign key constraint",
                    "source": "llm_generated"
                },
                {
                    "from_table": "order_items",
                    "to_table": "products",
                    "from_column": "product_id",
                    "to_column": "product_id",
                    "relationship_type": "many_to_one",
                    "confidence_score": 0.95,
                    "reasoning": "Order items reference products - standard e-commerce pattern",
                    "suggested_action": "Implement foreign key constraint",
                    "source": "llm_generated"
                }
            ],
            "summary": {
                "total_relationships": 3,
                "high_priority_relationships": [
                    {"table": "orders", "relationship": "orders → customers", "confidence": 0.95},
                    {"table": "order_items", "relationship": "order_items → orders", "confidence": 0.95},
                    {"table": "order_items", "relationship": "order_items → products", "confidence": 0.95}
                ],
                "medium_priority_relationships": [],
                "low_priority_relationships": [],
                "recommendations": [
                    "Implement 3 high-confidence relationships first",
                    "Validate all relationships against business requirements before implementation",
                    "Consider adding indexes on foreign key columns for performance"
                ]
            }
        }
        
        self.workflow_state["relationship_recommendations"] = recommendations
        
        logger.info(f"✓ Generated {recommendations['summary']['total_relationships']} relationship recommendations")
        logger.info(f"✓ High priority: {len(recommendations['summary']['high_priority_relationships'])}")
        logger.info(f"✓ Medium priority: {len(recommendations['summary']['medium_priority_relationships'])}")

    async def add_custom_relationships(self):
        """Add custom relationships based on business knowledge"""
        logger.info("Step 4: Adding Custom Relationships")
        
        # Add some custom relationships that might not be detected by LLM
        custom_relationships = [
            {
                "relationship_id": "custom_rel_001",
                "from_table": "customers",
                "to_table": "orders",
                "relationship_type": "one_to_many",
                "description": "Customers can have multiple orders over time",
                "confidence_score": 1.0,
                "reasoning": "Business rule: One customer can place multiple orders",
                "source": "user_defined",
                "business_justification": "Core business model - customers make repeat purchases"
            },
            {
                "relationship_id": "custom_rel_002",
                "from_table": "products",
                "to_table": "order_items",
                "relationship_type": "one_to_many",
                "description": "Products can appear in multiple order items",
                "confidence_score": 1.0,
                "reasoning": "Business rule: Popular products appear in many orders",
                "source": "user_defined",
                "business_justification": "Product performance tracking and inventory management"
            }
        ]
        
        for rel in custom_relationships:
            self.workflow_state["relationships"].append(rel)
            logger.info(f"✓ Added custom relationship: {rel['from_table']} → {rel['to_table']}")
        
        logger.info(f"✓ Total custom relationships: {len(custom_relationships)}")

    async def review_and_validate_workflow(self):
        """Review and validate the relationship workflow"""
        logger.info("Step 5: Reviewing and Validating Workflow")
        
        # Get workflow summary
        tables_count = len(self.workflow_state["tables"])
        relationships_count = len(self.workflow_state["relationships"])
        recommendations_available = bool(self.workflow_state["relationship_recommendations"])
        
        logger.info(f"✓ Workflow Status:")
        logger.info(f"  - Tables: {tables_count}")
        logger.info(f"  - Relationships: {relationships_count}")
        logger.info(f"  - Recommendations: {'Available' if recommendations_available else 'Not generated'}")
        
        # Validate relationships
        if relationships_count > 0:
            logger.info("✓ Relationship Validation:")
            for rel in self.workflow_state["relationships"]:
                logger.info(f"  - {rel['from_table']} → {rel['to_table']} ({rel['relationship_type']})")
        
        # Show next steps
        logger.info("✓ Next Steps:")
        if relationships_count == 0:
            logger.info("  - Review LLM recommendations and add relationships")
        elif relationships_count > 0:
            logger.info("  - Review all relationships for accuracy")
            logger.info("  - Consider committing workflow to database")
            logger.info("  - Generate MDL schema with defined relationships")

    async def show_final_workflow_state(self):
        """Show the final workflow state"""
        logger.info("Step 6: Final Workflow State")
        logger.info("=" * 50)
        
        # Create a summary of the workflow
        workflow_summary = {
            "domain": self.workflow_state["domain"]["domain_name"],
            "session_id": self.session_id,
            "workflow_progress": {
                "tables_added": len(self.workflow_state["tables"]),
                "relationships_defined": len(self.workflow_state["relationships"]),
                "recommendations_generated": bool(self.workflow_state["relationship_recommendations"]),
                "workflow_step": "relationship_management_completed"
            },
            "relationships_summary": {
                "total_relationships": len(self.workflow_state["relationships"]),
                "llm_recommendations": len(self.workflow_state["relationship_recommendations"]["cross_table_relationships"]) if self.workflow_state["relationship_recommendations"] else 0,
                "custom_relationships": len([r for r in self.workflow_state["relationships"] if r.get("source") == "user_defined"]),
                "ready_for_mdl": True
            },
            "mdl_schema_ready": True,
            "next_workflow_steps": [
                "Commit workflow to database",
                "Generate MDL schema file",
                "Validate schema with business stakeholders",
                "Implement database constraints based on relationships"
            ]
        }
        
        logger.info("Final Workflow Summary:")
        logger.info(json.dumps(workflow_summary, indent=2, default=str))
        
        return workflow_summary

    def export_workflow_to_json(self, filename: str = None):
        """Export the workflow state to a JSON file"""
        if filename is None:
            filename = f"relationship_workflow_{self.session_id}.json"
        
        workflow_export = {
            "export_info": {
                "exported_at": datetime.now().isoformat(),
                "session_id": self.session_id,
                "domain_id": self.domain_id,
                "export_type": "relationship_workflow"
            },
            "workflow_state": self.workflow_state,
            "metadata": {
                "total_tables": len(self.workflow_state["tables"]),
                "total_relationships": len(self.workflow_state["relationships"]),
                "recommendations_generated": bool(self.workflow_state["relationship_recommendations"])
            }
        }
        
        with open(filename, 'w') as f:
            json.dump(workflow_export, f, indent=2, default=str)
        
        logger.info(f"✓ Workflow exported to: {filename}")
        return filename

    async def demonstrate_workflow_management(self):
        """Demonstrate the workflow management operations"""
        logger.info("Step 7: Demonstrating Workflow Management Operations")
        logger.info("=" * 50)
        
        # Simulate the workflow management endpoint response
        workflow_management_data = {
            "domain_id": self.domain_id,
            "workflow_status": "ready_for_management",
            "current_state": {
                "relationships": self.workflow_state["relationships"],
                "recommendations": self.workflow_state["relationship_recommendations"],
                "summary": {
                    "total_relationships": len(self.workflow_state["relationships"]),
                    "total_recommendations": len(self.workflow_state["relationship_recommendations"]["cross_table_relationships"]) if self.workflow_state["relationship_recommendations"] else 0,
                    "workflow_progress": {
                        "tables_added": len(self.workflow_state["tables"]),
                        "relationships_defined": len(self.workflow_state["relationships"]),
                        "recommendations_generated": bool(self.workflow_state["relationship_recommendations"])
                    }
                }
            },
            "available_actions": [
                "generate_recommendations",
                "add_custom_relationship", 
                "update_relationship",
                "remove_relationship",
                "validate_workflow",
                "commit_workflow"
            ],
            "next_steps": [
                "Review LLM-generated recommendations",
                "Add custom relationships if needed",
                "Update relationship details",
                "Validate all relationships",
                "Commit workflow when ready"
            ]
        }
        
        logger.info("✓ Workflow Management Status:")
        logger.info(f"  - Status: {workflow_management_data['workflow_status']}")
        logger.info(f"  - Available Actions: {len(workflow_management_data['available_actions'])}")
        logger.info(f"  - Next Steps: {len(workflow_management_data['next_steps'])}")
        
        # Demonstrate batch operations
        logger.info("✓ Batch Operations Example:")
        batch_operations = [
            {
                "action": "add",
                "data": {
                    "from_table": "customers",
                    "to_table": "addresses",
                    "relationship_type": "one_to_many",
                    "description": "Customers can have multiple addresses"
                }
            },
            {
                "action": "update",
                "relationship_id": "custom_rel_001",
                "data": {
                    "description": "Updated: Customers can have multiple orders over time",
                    "confidence_score": 0.95
                }
            }
        ]
        
        logger.info(f"  - Batch operations prepared: {len(batch_operations)}")
        for i, op in enumerate(batch_operations):
            logger.info(f"    {i+1}. {op['action']}: {op.get('data', {}).get('description', 'N/A')}")
        
        # Show final management summary
        logger.info("✓ Management Summary:")
        logger.info(f"  - Total relationships: {workflow_management_data['current_state']['summary']['total_relationships']}")
        logger.info(f"  - Ready for commit: {workflow_management_data['workflow_status'] == 'ready_for_management'}")
        logger.info(f"  - Actions available: {', '.join(workflow_management_data['available_actions'][:3])}...")

async def main():
    """Main function to run the example"""
    example = RelationshipWorkflowExample()
    
    try:
        # Run the complete workflow
        await example.run_complete_workflow()
        
        # Export the workflow
        export_file = example.export_workflow_to_json()
        
        print(f"\n🎉 Relationship Workflow Example completed successfully!")
        print(f"📁 Workflow exported to: {export_file}")
        print(f"📊 Final state: {len(example.workflow_state['tables'])} tables, {len(example.workflow_state['relationships'])} relationships")
        print(f"🔗 Ready for MDL schema generation: {example.workflow_state['relationships'] > 0}")
        
    except Exception as e:
        logger.error(f"Example failed: {str(e)}")
        raise

if __name__ == "__main__":
    # Run the async example
    asyncio.run(main())

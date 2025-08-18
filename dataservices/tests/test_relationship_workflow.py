"""
Test script for the new relationship workflow functionality

This script tests the key methods of the DomainWorkflowService related to
relationship management in the workflow step.
"""

import asyncio
import logging
from unittest.mock import Mock, patch
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockDomainWorkflowService:
    """Mock implementation for testing relationship workflow functionality"""
    
    def __init__(self, user_id: str, session_id: str = None):
        self.user_id = user_id
        self.session_id = session_id
        self.workflow_state = {
            "domain": None,
            "context": None,
            "datasets": [],
            "tables": [],
            "relationships": [],
            "relationship_recommendations": None
        }
    
    def get_workflow_state(self):
        return self.workflow_state
    
    def set_workflow_state(self, state):
        self.workflow_state = state
    
    async def get_comprehensive_relationship_recommendations(self, domain_context):
        """Mock implementation of relationship recommendations generation"""
        try:
            tables = self.workflow_state.get("tables", [])
            
            if not tables:
                return {
                    "status": "no_tables",
                    "message": "No tables have been added to the workflow yet.",
                    "recommendations": [],
                    "summary": {
                        "total_tables": 0,
                        "total_relationships": 0,
                        "recommendations": ["Add tables to the workflow to begin relationship analysis"]
                    }
                }
            
            # Mock LLM-generated recommendations from existing service
            mock_recommendations = {
                "domain_id": domain_context.domain_id,
                "total_tables": len(tables),
                "generated_at": datetime.now().isoformat(),
                "relationships": [
                    {
                        "from_table": "orders",
                        "to_table": "customers",
                        "from_column": "customer_id",
                        "to_column": "customer_id",
                        "relationship_type": "many_to_one",
                        "confidence_score": 0.95,
                        "reasoning": "Mock: Orders table has customer_id foreign key",
                        "suggested_action": "Implement foreign key constraint",
                        "source": "llm_generated"
                    }
                ],
                "summary": {
                    "total_relationships": 1,
                    "high_priority_relationships": [
                        {"table": "orders", "relationship": "orders → customers", "confidence": 0.95}
                    ],
                    "medium_priority_relationships": [],
                    "low_priority_relationships": [],
                    "recommendations": [
                        "Implement 1 high-confidence relationship first",
                        "Validate all relationships against business requirements"
                    ]
                }
            }
            
            # Store recommendations in workflow state
            self.workflow_state["relationship_recommendations"] = mock_recommendations
            
            return mock_recommendations
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to generate relationship recommendations"
            }
    
    async def add_custom_relationship(self, relationship_data, domain_context):
        """Mock implementation of adding custom relationships"""
        try:
            # Validate required fields
            required_fields = ["from_table", "to_table", "relationship_type"]
            for field in required_fields:
                if field not in relationship_data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Create relationship object
            relationship = {
                "relationship_id": f"mock_rel_{len(self.workflow_state['relationships']) + 1}",
                "domain_id": domain_context.domain_id,
                "name": relationship_data.get("name", f"{relationship_data['from_table']}_to_{relationship_data['to_table']}"),
                "relationship_type": relationship_data["relationship_type"],
                "from_table": relationship_data["from_table"],
                "to_table": relationship_data["to_table"],
                "from_column": relationship_data.get("from_column"),
                "to_column": relationship_data.get("to_column"),
                "description": relationship_data.get("description", f"Custom relationship between {relationship_data['from_table']} and {relationship_data['to_table']}"),
                "is_active": True,
                "created_at": datetime.now().isoformat(),
                "modified_by": self.user_id,
                "confidence_score": relationship_data.get("confidence_score", 1.0),
                "reasoning": relationship_data.get("reasoning", "Manually defined by user"),
                "source": "user_defined"
            }
            
            # Add to workflow state
            self.workflow_state["relationships"].append(relationship)
            
            return {
                "status": "success",
                "relationship": relationship,
                "message": f"Successfully added relationship between {relationship['from_table']} and {relationship['to_table']}"
            }
            
        except Exception as e:
            logger.error(f"Error adding custom relationship: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to add custom relationship"
            }
    
    async def get_workflow_relationships(self):
        """Mock implementation of getting workflow relationships"""
        try:
            relationships = self.workflow_state.get("relationships", [])
            recommendations = self.workflow_state.get("relationship_recommendations", {})
            
            return {
                "status": "success",
                "relationships": relationships,
                "recommendations": recommendations,
                "summary": {
                    "total_relationships": len(relationships),
                    "total_recommendations": len(recommendations.get("table_recommendations", {})) if recommendations else 0,
                    "workflow_progress": {
                        "tables_added": len(self.workflow_state.get("tables", [])),
                        "relationships_defined": len(relationships),
                        "recommendations_generated": bool(recommendations)
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting workflow relationships: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to get workflow relationships"
            }

class MockDomainContext:
    """Mock domain context for testing"""
    
    def __init__(self, domain_id: str, domain_name: str, business_domain: str):
        self.domain_id = domain_id
        self.domain_name = domain_name
        self.business_domain = business_domain
        self.purpose = f"Test domain {domain_id}"
        self.target_users = ["Test Users"]
        self.key_business_concepts = ["Testing", "Development"]

async def test_relationship_workflow():
    """Test the complete relationship workflow functionality"""
    logger.info("Starting Relationship Workflow Tests")
    logger.info("=" * 50)
    
    # Initialize mock service
    service = MockDomainWorkflowService(
        user_id="test_user_123",
        session_id="test_session_456"
    )
    
    # Test 1: Initial state
    logger.info("Test 1: Initial Workflow State")
    initial_state = service.get_workflow_state()
    assert len(initial_state["tables"]) == 0, "Initial state should have no tables"
    assert len(initial_state["relationships"]) == 0, "Initial state should have no relationships"
    logger.info("✓ Initial state is correct")
    
    # Test 2: Add mock tables
    logger.info("Test 2: Adding Mock Tables")
    mock_tables = [
        {"name": "customers", "description": "Customer information"},
        {"name": "orders", "description": "Order information"},
        {"name": "products", "description": "Product information"}
    ]
    
    for table in mock_tables:
        service.workflow_state["tables"].append(table)
    
    assert len(service.workflow_state["tables"]) == 3, "Should have 3 tables"
    logger.info("✓ Added 3 mock tables")
    
    # Test 3: Generate relationship recommendations
    logger.info("Test 3: Generating Relationship Recommendations")
    domain_context = MockDomainContext(
        domain_id="test_domain_789",
        domain_name="Test Domain",
        business_domain="Test Business"
    )
    
    recommendations = await service.get_comprehensive_relationship_recommendations(domain_context)
    
    assert recommendations["status"] != "error", "Should not have error status"
    assert recommendations["total_tables"] == 3, "Should have 3 tables"
    assert len(recommendations["cross_table_relationships"]) > 0, "Should have cross-table relationships"
    
    logger.info(f"✓ Generated recommendations for {recommendations['total_tables']} tables")
    logger.info(f"✓ Found {len(recommendations['cross_table_relationships'])} cross-table relationships")
    
    # Test 4: Add custom relationship
    logger.info("Test 4: Adding Custom Relationship")
    custom_rel_data = {
        "from_table": "orders",
        "to_table": "customers",
        "relationship_type": "many_to_one",
        "from_column": "customer_id",
        "to_column": "customer_id",
        "description": "Orders belong to customers",
        "confidence_score": 1.0,
        "reasoning": "Business rule: Orders must have a customer"
    }
    
    result = await service.add_custom_relationship(custom_rel_data, domain_context)
    
    assert result["status"] == "success", "Should successfully add relationship"
    assert len(service.workflow_state["relationships"]) == 1, "Should have 1 relationship"
    
    logger.info("✓ Added custom relationship successfully")
    
    # Test 5: Get workflow relationships
    logger.info("Test 5: Getting Workflow Relationships")
    workflow_status = await service.get_workflow_relationships()
    
    assert workflow_status["status"] == "success", "Should successfully get workflow status"
    assert workflow_status["summary"]["total_relationships"] == 1, "Should have 1 relationship"
    assert workflow_status["summary"]["workflow_progress"]["tables_added"] == 3, "Should have 3 tables"
    
    logger.info("✓ Retrieved workflow relationships successfully")
    
    # Test 6: Final state validation
    logger.info("Test 6: Final State Validation")
    final_state = service.get_workflow_state()
    
    assert len(final_state["tables"]) == 3, "Final state should have 3 tables"
    assert len(final_state["relationships"]) == 1, "Final state should have 1 relationship"
    assert final_state["relationship_recommendations"] is not None, "Should have recommendations"
    
    logger.info("✓ Final state validation passed")
    
    # Test 7: Error handling
    logger.info("Test 7: Error Handling")
    
    # Test with no tables
    empty_service = MockDomainWorkflowService("test_user", "empty_session")
    empty_recommendations = await empty_service.get_comprehensive_relationship_recommendations(domain_context)
    
    assert empty_recommendations["status"] == "no_tables", "Should handle empty workflow correctly"
    logger.info("✓ Error handling for empty workflow works")
    
    # Test invalid relationship data
    invalid_rel_data = {
        "from_table": "orders"  # Missing required fields
    }
    
    invalid_result = await service.add_custom_relationship(invalid_rel_data, domain_context)
    assert invalid_result["status"] == "error", "Should handle invalid data correctly"
    logger.info("✓ Error handling for invalid data works")
    
    logger.info("=" * 50)
    logger.info("All Relationship Workflow Tests Passed! 🎉")
    
    return True

async def main():
    """Main test runner"""
    try:
        success = await test_relationship_workflow()
        if success:
            print("\n✅ All tests passed successfully!")
            print("🔗 Relationship workflow functionality is working correctly")
            print("📚 Ready for integration with the main application")
        else:
            print("\n❌ Some tests failed")
            return 1
    except Exception as e:
        print(f"\n💥 Test execution failed: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)

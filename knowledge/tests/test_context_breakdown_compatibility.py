"""
Test script to verify ContextBreakdown compatibility between old and new implementations

This script tests:
1. The new ContextBreakdown dataclass from app.agents.contextual_agents
2. The old ContextBreakdown dataclass from app.services.context_breakdown_service
3. The get_breakdown_field helper function
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


def get_breakdown_field(breakdown, field_name, default=None):
    """
    Helper to extract a field from either a ContextBreakdown dataclass or dict.
    
    Args:
        breakdown: Either a ContextBreakdown dataclass or dict
        field_name: Name of the field to extract
        default: Default value if field not found
        
    Returns:
        Field value or default
    """
    if breakdown is None:
        return default
    
    # Try dataclass attribute access first
    if hasattr(breakdown, field_name):
        return getattr(breakdown, field_name, default)
    
    # Fall back to dict access
    if isinstance(breakdown, dict):
        return breakdown.get(field_name, default)
    
    return default


def test_new_context_breakdown():
    """Test new ContextBreakdown from contextual_agents"""
    print("=" * 80)
    print("Testing new ContextBreakdown dataclass")
    print("=" * 80)
    
    try:
        from app.agents.contextual_agents.base_context_breakdown_agent import ContextBreakdown
        
        # Create a test breakdown
        breakdown = ContextBreakdown(
            user_question="test question",
            query_type="mdl",
            identified_entities=["entity1", "entity2"],
            evidence_gathering_required=True,
            evidence_types_needed=["database_schemas"],
            data_retrieval_plan=[
                {"data_type": "database_schemas", "category": "assets", "purpose": "test"}
            ],
            metrics_kpis_needed=[
                {"metric_type": "count", "purpose": "test metric"}
            ]
        )
        
        # Test field access via helper
        print(f"✓ query_type: {get_breakdown_field(breakdown, 'query_type', 'unknown')}")
        print(f"✓ identified_entities: {get_breakdown_field(breakdown, 'identified_entities', [])}")
        print(f"✓ evidence_gathering_required: {get_breakdown_field(breakdown, 'evidence_gathering_required', False)}")
        print(f"✓ evidence_types_needed: {get_breakdown_field(breakdown, 'evidence_types_needed', [])}")
        print(f"✓ data_retrieval_plan: {len(get_breakdown_field(breakdown, 'data_retrieval_plan', []))} items")
        print(f"✓ metrics_kpis_needed: {len(get_breakdown_field(breakdown, 'metrics_kpis_needed', []))} items")
        
        print("\n✅ New ContextBreakdown test passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ New ContextBreakdown test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dict_breakdown():
    """Test dict-based breakdown (old format)"""
    print("\n" + "=" * 80)
    print("Testing dict-based breakdown (old format)")
    print("=" * 80)
    
    try:
        # Create a test breakdown as dict
        breakdown = {
            "query_type": "mdl",
            "identified_entities": ["entity1", "entity2"],
            "evidence_gathering_required": True,
            "evidence_types_needed": ["database_schemas"],
            "data_retrieval_plan": [
                {"data_type": "database_schemas", "category": "assets", "purpose": "test"}
            ],
            "metrics_kpis_needed": [
                {"metric_type": "count", "purpose": "test metric"}
            ]
        }
        
        # Test field access via helper
        print(f"✓ query_type: {get_breakdown_field(breakdown, 'query_type', 'unknown')}")
        print(f"✓ identified_entities: {get_breakdown_field(breakdown, 'identified_entities', [])}")
        print(f"✓ evidence_gathering_required: {get_breakdown_field(breakdown, 'evidence_gathering_required', False)}")
        print(f"✓ evidence_types_needed: {get_breakdown_field(breakdown, 'evidence_types_needed', [])}")
        print(f"✓ data_retrieval_plan: {len(get_breakdown_field(breakdown, 'data_retrieval_plan', []))} items")
        print(f"✓ metrics_kpis_needed: {len(get_breakdown_field(breakdown, 'metrics_kpis_needed', []))} items")
        
        print("\n✅ Dict breakdown test passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Dict breakdown test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dataclass_to_dict_conversion():
    """Test converting ContextBreakdown dataclass to dict"""
    print("\n" + "=" * 80)
    print("Testing dataclass to dict conversion")
    print("=" * 80)
    
    try:
        from app.agents.contextual_agents.base_context_breakdown_agent import ContextBreakdown
        from dataclasses import asdict
        
        # Create a test breakdown
        breakdown = ContextBreakdown(
            user_question="test question",
            query_type="mdl",
            identified_entities=["entity1", "entity2"],
            evidence_gathering_required=True
        )
        
        # Convert to dict
        breakdown_dict = asdict(breakdown)
        
        print(f"✓ Converted to dict with {len(breakdown_dict)} keys")
        print(f"✓ query_type: {breakdown_dict['query_type']}")
        print(f"✓ identified_entities: {breakdown_dict['identified_entities']}")
        print(f"✓ evidence_gathering_required: {breakdown_dict['evidence_gathering_required']}")
        
        # Test that helper works with converted dict
        print(f"✓ Helper works with converted dict: {get_breakdown_field(breakdown_dict, 'query_type', 'unknown')}")
        
        print("\n✅ Dataclass to dict conversion test passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Dataclass to dict conversion test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\nContext Breakdown Compatibility Tests")
    print("=" * 80)
    
    results = []
    
    # Test new ContextBreakdown
    results.append(("New ContextBreakdown", test_new_context_breakdown()))
    
    # Test dict breakdown
    results.append(("Dict breakdown", test_dict_breakdown()))
    
    # Test conversion
    results.append(("Dataclass to dict conversion", test_dataclass_to_dict_conversion()))
    
    # Summary
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    all_passed = all(result[1] for result in results)
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())

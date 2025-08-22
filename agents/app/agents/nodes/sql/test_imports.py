#!/usr/bin/env python3
"""
Test script to verify that all dashboard classes can be imported correctly
"""

def test_imports():
    """Test importing all dashboard classes"""
    try:
        # Test models
        from .dashboard_models import (
            FilterOperator, FilterType, ActionType,
            ControlFilter, ConditionalFormat, DashboardConfiguration
        )
        print("✓ Models imported successfully")
        
        # Test retriever
        from .dashboard_retriever import ConditionalFormattingRetriever
        print("✓ Retriever imported successfully")
        
        # Test agent
        from .dashboard_agent import ConditionalFormattingAgent
        print("✓ Agent imported successfully")
        
        # Test service
        from .dashboard_service import DashboardConditionalFormattingService
        print("✓ Service imported successfully")
        
        # Test pipeline
        from .dashboard_pipeline import ConditionalFormattingPipeline
        print("✓ Pipeline imported successfully")
        
        # Test factory
        from .dashboard_factory import (
            create_conditional_formatting_service,
            create_conditional_formatting_pipeline
        )
        print("✓ Factory functions imported successfully")
        
        # Test controller (should import everything)
        from .dashboard_controller import (
            FilterOperator as FO, FilterType as FT, ActionType as AT,
            ControlFilter as CF, ConditionalFormat as CF2, DashboardConfiguration as DC,
            ConditionalFormattingRetriever as CFR, ConditionalFormattingAgent as CFA,
            DashboardConditionalFormattingService as DCFS, ConditionalFormattingPipeline as CFP
        )
        print("✓ Controller imports successful")
        
        print("\n🎉 All imports successful! The refactor is working correctly.")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    test_imports()

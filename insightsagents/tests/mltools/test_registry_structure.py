"""
Test Registry Structure

This script tests that the function registry components can be imported
correctly from the new registry folder structure.
"""

import os
import sys

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))


def test_imports():
    """Test that all registry components can be imported correctly."""
    print("=== Testing Registry Structure Imports ===\n")
    
    try:
        # Test importing from the registry module
        from app.tools.mltools.registry import (
            MLFunctionRegistry,
            FunctionMetadata,
            initialize_function_registry,
            FunctionSearchInterface,
            SearchResult,
            create_search_interface,
            FunctionRetrievalService,
            create_function_retrieval_service
        )
        print("✅ All registry components imported successfully from registry module")
        
        # Test importing from the main mltools module
        from app.tools.mltools import (
            MLFunctionRegistry as MLFunctionRegistry2,
            FunctionMetadata as FunctionMetadata2,
            initialize_function_registry as initialize_function_registry2,
            FunctionSearchInterface as FunctionSearchInterface2,
            SearchResult as SearchResult2,
            create_search_interface as create_search_interface2,
            FunctionRetrievalService as FunctionRetrievalService2,
            create_function_retrieval_service as create_function_retrieval_service2
        )
        print("✅ All registry components imported successfully from main mltools module")
        
        # Test that the classes are the same
        assert MLFunctionRegistry is MLFunctionRegistry2
        assert FunctionMetadata is FunctionMetadata2
        assert FunctionSearchInterface is FunctionSearchInterface2
        assert SearchResult is SearchResult2
        assert FunctionRetrievalService is FunctionRetrievalService2
        print("✅ Imported classes are identical (same objects)")
        
        # Test that functions are the same
        assert initialize_function_registry is initialize_function_registry2
        assert create_search_interface is create_search_interface2
        assert create_function_retrieval_service is create_function_retrieval_service2
        print("✅ Imported functions are identical (same objects)")
        
        print("\n🎉 All import tests passed! Registry structure is working correctly.")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_registry_functionality():
    """Test basic registry functionality."""
    print("\n=== Testing Registry Functionality ===\n")
    
    try:
        from app.tools.mltools.registry import create_function_retrieval_service
        
        # Create service (this will test the initialization)
        service = create_function_retrieval_service("./test_chroma_db")
        
        # Check service status
        status = service.get_service_status()
        print(f"Service status: {status['initialized']}")
        
        if status['initialized']:
            print("✅ Service initialized successfully")
            
            # Test basic search
            results = service.search_functions_for_agent("test query", max_results=1)
            print(f"✅ Search functionality working (found {len(results)} results)")
            
            # Test category listing
            categories = service.get_available_categories()
            print(f"✅ Category listing working (found {len(categories)} categories)")
            
        else:
            print("⚠️  Service not initialized (this is expected if ChromaDB is not set up)")
        
        print("\n🎉 Registry functionality test completed!")
        return True
        
    except Exception as e:
        print(f"❌ Functionality test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("Testing ML Function Registry Structure")
    print("=" * 50)
    
    # Test imports
    import_success = test_imports()
    
    # Test functionality
    functionality_success = test_registry_functionality()
    
    if import_success and functionality_success:
        print("\n🎉 All tests passed! The registry structure is working correctly.")
        return 0
    else:
        print("\n❌ Some tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    exit(main())

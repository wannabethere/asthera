"""
Test LLM-Powered Function Registry

This script tests the new LLM-powered function registry system that replaces
hardcoded mappings with intelligent, dynamic function identification.
"""

import os
import sys
import json
from typing import Dict, Any, List

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

import chromadb
from app.tools.mltools.registry import (
    create_function_retrieval_service,
    initialize_enhanced_function_registry,
    create_llm_metadata_generator,
    create_dynamic_function_matcher
)


def test_llm_metadata_generation():
    """Test LLM metadata generation for functions."""
    print("=== Testing LLM Metadata Generation ===\n")
    
    try:
        # Create LLM metadata generator
        metadata_generator = create_llm_metadata_generator("gpt-3.5-turbo")
        
        # Test with a sample function
        def sample_function(data, threshold=0.5):
            """Detect anomalies in time series data using statistical methods.
            
            Args:
                data: Time series data
                threshold: Anomaly detection threshold
                
            Returns:
                List of anomaly flags
            """
            return [x > threshold for x in data]
        
        # Generate metadata
        metadata = metadata_generator.generate_function_metadata(sample_function, "test_module")
        
        print(f"Generated metadata for sample function:")
        print(f"Category: {metadata.category}")
        print(f"Subcategory: {metadata.subcategory}")
        print(f"Description: {metadata.description}")
        print(f"Use Cases: {metadata.use_cases}")
        print(f"Data Requirements: {metadata.data_requirements}")
        print(f"Complexity: {metadata.complexity_level}")
        print(f"Tags: {metadata.tags}")
        print(f"Keywords: {metadata.keywords}")
        print(f"Confidence Score: {metadata.confidence_score}")
        
        return True
        
    except Exception as e:
        print(f"Error testing LLM metadata generation: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dynamic_function_matching():
    """Test dynamic function matching with LLM."""
    print("\n=== Testing Dynamic Function Matching ===\n")
    
    try:
        # Create LLM components
        metadata_generator = create_llm_metadata_generator("gpt-3.5-turbo")
        dynamic_matcher = create_dynamic_function_matcher(metadata_generator)
        
        # Sample function data
        sample_functions = [
            {
                "name": "detect_anomalies",
                "description": "Detect statistical anomalies in time series data",
                "category": "anomaly_detection",
                "use_cases": ["outlier detection", "quality control"],
                "tags": ["anomaly", "statistical", "time_series"],
                "keywords": ["anomaly", "outlier", "detection", "statistical"]
            },
            {
                "name": "forecast_sales",
                "description": "Forecast sales trends using time series analysis",
                "category": "time_series",
                "use_cases": ["sales forecasting", "demand planning"],
                "tags": ["forecast", "time_series", "sales"],
                "keywords": ["forecast", "trend", "sales", "prediction"]
            },
            {
                "name": "segment_customers",
                "description": "Segment customers based on behavior patterns",
                "category": "segmentation",
                "use_cases": ["customer segmentation", "behavioral analysis"],
                "tags": ["segmentation", "clustering", "customers"],
                "keywords": ["segment", "cluster", "customer", "behavior"]
            }
        ]
        
        # Register functions
        dynamic_matcher.register_functions(sample_functions)
        
        # Test queries
        test_queries = [
            "I need to find outliers in my data",
            "Help me predict future sales",
            "How can I group my customers?",
            "What functions work with time series data?",
            "I want to analyze customer behavior"
        ]
        
        print("Testing dynamic function matching:")
        for query in test_queries:
            print(f"\nQuery: '{query}'")
            matches = dynamic_matcher.find_best_matches(query, max_results=2)
            
            for i, match in enumerate(matches, 1):
                print(f"  {i}. {match['function_name']} (Score: {match.get('relevance_score', 0):.3f})")
                print(f"     Reasoning: {match.get('reasoning', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"Error testing dynamic function matching: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_enhanced_registry():
    """Test the enhanced registry with LLM integration."""
    print("\n=== Testing Enhanced Registry ===\n")
    
    try:
        # Initialize ChromaDB client
        chroma_path = "./test_llm_chroma_db"
        client = chromadb.PersistentClient(path=chroma_path)
        
        # Create enhanced registry
        print("Creating enhanced registry with LLM integration...")
        registry = initialize_enhanced_function_registry(client, "gpt-3.5-turbo")
        
        # Get statistics
        stats = registry.get_function_statistics()
        print(f"Registry Statistics:")
        print(f"Total functions: {stats['total_functions']}")
        print(f"LLM generated functions: {stats['llm_generated_functions']}")
        print(f"Categories: {list(stats['by_category'].keys())}")
        print(f"Use cases: {len(stats['use_cases'])}")
        print(f"Data requirements: {len(stats['data_requirements'])}")
        
        # Test search functionality
        print("\nTesting search functionality:")
        search_queries = [
            "detect anomalies in time series data",
            "forecast sales trends",
            "segment customers by behavior",
            "analyze cohort retention",
            "calculate risk metrics"
        ]
        
        for query in search_queries:
            print(f"\nQuery: '{query}'")
            results = registry.search_functions(query, n_results=2)
            
            for i, result in enumerate(results, 1):
                metadata = result['metadata']
                print(f"  {i}. {metadata['function_name']} ({metadata['category']})")
                print(f"     Score: {result.get('score', 0):.3f}")
                print(f"     Description: {metadata.get('description', 'N/A')[:100]}...")
        
        # Test use case matching
        print("\nTesting use case matching:")
        use_cases = [
            "anomaly detection",
            "time series forecasting",
            "customer segmentation",
            "cohort analysis",
            "risk analysis"
        ]
        
        for use_case in use_cases:
            print(f"\nUse case: '{use_case}'")
            results = registry.find_functions_by_use_case(use_case, n_results=2)
            
            for i, result in enumerate(results, 1):
                metadata = result['metadata']
                print(f"  {i}. {metadata['function_name']} (Score: {result.get('score', 0):.3f})")
        
        return True
        
    except Exception as e:
        print(f"Error testing enhanced registry: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agent_integration():
    """Test agent integration with LLM-powered registry."""
    print("\n=== Testing Agent Integration ===\n")
    
    try:
        # Create function retrieval service
        service = create_function_retrieval_service("./test_llm_chroma_db", "gpt-3.5-turbo")
        
        # Check service status
        status = service.get_service_status()
        print(f"Service Status: {status['initialized']}")
        
        if not status['initialized']:
            print("Service not initialized. Please run the enhanced registry initialization first.")
            return False
        
        # Test agent queries
        agent_scenarios = [
            {
                "query": "I need to detect anomalies in my sales data",
                "context": {
                    "task_type": "anomaly_detection",
                    "data_columns": ["date", "sales", "region"],
                    "complexity_level": "intermediate"
                }
            },
            {
                "query": "Help me forecast customer demand for next quarter",
                "context": {
                    "task_type": "forecasting",
                    "data_columns": ["date", "demand", "product"],
                    "complexity_level": "advanced"
                }
            },
            {
                "query": "I want to segment my customers by purchase behavior",
                "context": {
                    "task_type": "segmentation",
                    "data_columns": ["customer_id", "purchase_amount", "frequency"],
                    "complexity_level": "intermediate"
                }
            }
        ]
        
        print("Testing agent integration:")
        for i, scenario in enumerate(agent_scenarios, 1):
            print(f"\n--- Scenario {i} ---")
            print(f"Query: {scenario['query']}")
            print(f"Context: {json.dumps(scenario['context'], indent=2)}")
            
            results = service.search_functions_for_agent(
                scenario['query'],
                context=scenario['context'],
                max_results=3
            )
            
            print(f"Found {len(results)} relevant functions:")
            for j, result in enumerate(results, 1):
                print(f"  {j}. {result['function_name']} ({result['category']})")
                print(f"     Relevance Score: {result['relevance_score']:.3f}")
                print(f"     Description: {result['description'][:100]}...")
                print(f"     Data Requirements: {', '.join(result['data_requirements'])}")
        
        return True
        
    except Exception as e:
        print(f"Error testing agent integration: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_use_case_mappings():
    """Test dynamic use case mappings."""
    print("\n=== Testing Dynamic Use Case Mappings ===\n")
    
    try:
        # Create function retrieval service
        service = create_function_retrieval_service("./test_llm_chroma_db", "gpt-3.5-turbo")
        
        if not service.get_service_status()['initialized']:
            print("Service not initialized. Please run the enhanced registry initialization first.")
            return False
        
        # Test various use cases
        use_cases = [
            "detect outliers in sensor data",
            "forecast revenue for next year",
            "group customers by spending patterns",
            "analyze user retention rates",
            "calculate portfolio risk",
            "track conversion funnel performance",
            "smooth noisy time series data",
            "identify seasonal trends"
        ]
        
        print("Testing dynamic use case mappings:")
        for use_case in use_cases:
            print(f"\nUse case: '{use_case}'")
            results = service.search_functions_by_use_case(use_case)
            
            print(f"Found {len(results)} relevant functions:")
            for i, result in enumerate(results[:3], 1):
                print(f"  {i}. {result['function_name']} ({result['category']})")
                print(f"     Score: {result['relevance_score']:.3f}")
                print(f"     Description: {result['description'][:80]}...")
        
        return True
        
    except Exception as e:
        print(f"Error testing use case mappings: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all LLM-powered registry tests."""
    print("LLM-Powered Function Registry Test Suite")
    print("=" * 50)
    
    tests = [
        ("LLM Metadata Generation", test_llm_metadata_generation),
        ("Dynamic Function Matching", test_dynamic_function_matching),
        ("Enhanced Registry", test_enhanced_registry),
        ("Agent Integration", test_agent_integration),
        ("Use Case Mappings", test_use_case_mappings)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            success = test_func()
            results[test_name] = success
            if success:
                print(f"✅ {test_name} passed")
            else:
                print(f"❌ {test_name} failed")
        except Exception as e:
            print(f"❌ {test_name} failed with error: {e}")
            results[test_name] = False
    
    # Summary
    print(f"\n{'='*50}")
    print("Test Summary:")
    passed = sum(1 for success in results.values() if success)
    total = len(results)
    
    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {test_name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! LLM-powered registry is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    exit(main())

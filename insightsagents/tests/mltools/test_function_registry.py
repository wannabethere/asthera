"""
Test Function Registry

This script tests the ML function registry system with various queries
to demonstrate its capabilities.
"""

import os
import sys
import json
from typing import Dict, Any

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

import chromadb
from app.tools.mltools.registry import create_function_retrieval_service


def test_function_registry():
    """Test the function registry with various queries."""
    print("=== Testing ML Function Registry ===\n")
    
    # Initialize ChromaDB client
    chroma_path = "./test_chroma_db"
    client = chromadb.PersistentClient(path=chroma_path)
    
    try:
        # Create function retrieval service
        print("Initializing function retrieval service...")
        service = create_function_retrieval_service(chroma_path)
        
        # Check service status
        status = service.get_service_status()
        print(f"Service Status: {json.dumps(status, indent=2)}\n")
        
        if not status["initialized"]:
            print("Service not initialized. Please run the initialization script first.")
            return
        
        # Test 1: Search for anomaly detection functions
        print("--- Test 1: Anomaly Detection Functions ---")
        results = service.search_functions_for_agent(
            "detect anomalies in time series data",
            context={
                "task_type": "anomaly_detection",
                "data_columns": ["date", "value", "region"],
                "complexity_level": "intermediate"
            },
            max_results=3
        )
        
        print(f"Found {len(results)} anomaly detection functions:")
        for i, result in enumerate(results, 1):
            print(f"{i}. {result['function_name']} ({result['category']})")
            print(f"   Description: {result['description']}")
            print(f"   Complexity: {result['complexity']}")
            print(f"   Relevance Score: {result['relevance_score']:.3f}")
            print(f"   Tags: {', '.join(result['tags'])}")
            print()
        
        # Test 2: Search for customer segmentation functions
        print("--- Test 2: Customer Segmentation Functions ---")
        results = service.search_functions_by_use_case("customer segmentation")
        
        print(f"Found {len(results)} segmentation functions:")
        for i, result in enumerate(results[:3], 1):
            print(f"{i}. {result['function_name']} ({result['category']})")
            print(f"   Description: {result['description']}")
            print(f"   Data Requirements: {', '.join(result['data_requirements'])}")
            print()
        
        # Test 3: Search for time series forecasting functions
        print("--- Test 3: Time Series Forecasting Functions ---")
        results = service.search_functions_for_agent(
            "forecast time series trends",
            context={
                "task_type": "forecasting",
                "data_columns": ["date", "sales", "region"],
                "complexity_level": "advanced"
            },
            max_results=3
        )
        
        print(f"Found {len(results)} forecasting functions:")
        for i, result in enumerate(results, 1):
            print(f"{i}. {result['function_name']} ({result['category']})")
            print(f"   Description: {result['description']}")
            print(f"   Parameters: {len(result['parameters'])} parameters")
            if result['examples']:
                print(f"   Example: {result['examples'][0]}")
            print()
        
        # Test 4: Get function by name
        print("--- Test 4: Get Function by Name ---")
        if results:
            function_name = results[0]['function_name']
            function_info = service.get_function_by_name(function_name)
            
            if function_info:
                print(f"Function: {function_info['function_name']}")
                print(f"Module: {function_info['module']}")
                print(f"Category: {function_info['category']}")
                print(f"Description: {function_info['description']}")
                print(f"Parameters:")
                for param_name, param_info in function_info['parameters'].items():
                    required = "Required" if param_info['required'] else "Optional"
                    print(f"  - {param_name}: {param_info['type']} ({required})")
                print()
        
        # Test 5: Get functions by category
        print("--- Test 5: Functions by Category ---")
        categories = service.get_available_categories()
        print(f"Available categories: {', '.join(categories)}")
        
        # Get functions from a specific category
        if categories:
            category = categories[0]
            category_functions = service.get_functions_by_category(category)
            print(f"\nFunctions in '{category}' category ({len(category_functions)} functions):")
            for i, func in enumerate(category_functions[:5], 1):
                print(f"{i}. {func['function_name']} - {func['description']}")
            print()
        
        # Test 6: Get function recommendations
        print("--- Test 6: Function Recommendations ---")
        if results:
            recommendations = service.get_function_recommendations(
                results[0]['function_name'], 
                max_recommendations=3
            )
            
            print(f"Recommendations for {results[0]['function_name']}:")
            for i, rec in enumerate(recommendations, 1):
                print(f"{i}. {rec['function_name']} ({rec['category']})")
                print(f"   Description: {rec['description']}")
                print(f"   Relevance Score: {rec['relevance_score']:.3f}")
                print()
        
        # Test 7: Search with different complexity levels
        print("--- Test 7: Search by Complexity ---")
        complexity_levels = ["simple", "intermediate", "advanced"]
        
        for complexity in complexity_levels:
            results = service.search_functions_for_agent(
                "statistical analysis",
                context={"complexity_level": complexity},
                max_results=2
            )
            
            print(f"{complexity.capitalize()} functions:")
            for result in results:
                print(f"  - {result['function_name']} ({result['complexity']})")
            print()
        
        print("=== All Tests Completed Successfully ===")
        
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()


def test_agent_integration():
    """Test how the function registry integrates with ML agents."""
    print("\n=== Testing Agent Integration ===\n")
    
    chroma_path = "./test_chroma_db"
    service = create_function_retrieval_service(chroma_path)
    
    # Simulate an agent query
    agent_context = {
        "task_type": "anomaly_detection",
        "data_columns": ["timestamp", "value", "category", "region"],
        "complexity_level": "intermediate",
        "output_requirements": ["anomaly_flags", "confidence_scores"]
    }
    
    query = "I need to detect anomalies in my time series data with multiple categories and regions"
    
    print(f"Agent Query: {query}")
    print(f"Agent Context: {json.dumps(agent_context, indent=2)}")
    print()
    
    # Search for relevant functions
    results = service.search_functions_for_agent(query, agent_context, max_results=5)
    
    print(f"Found {len(results)} relevant functions:")
    for i, result in enumerate(results, 1):
        print(f"\n{i}. {result['function_name']} ({result['category']})")
        print(f"   Description: {result['description']}")
        print(f"   Relevance Score: {result['relevance_score']:.3f}")
        print(f"   Complexity: {result['complexity']}")
        print(f"   Data Requirements: {', '.join(result['data_requirements'])}")
        print(f"   Parameters: {len(result['parameters'])} parameters")
        
        # Show parameter details
        if result['parameters']:
            print("   Parameter Details:")
            for param_name, param_info in result['parameters'].items():
                required = "Required" if param_info['required'] else "Optional"
                print(f"     - {param_name}: {param_info['type']} ({required})")
        
        # Show usage patterns
        if result['usage_patterns']:
            print(f"   Usage Patterns:")
            for pattern in result['usage_patterns'][:2]:
                print(f"     - {pattern}")


if __name__ == "__main__":
    # Run tests
    test_function_registry()
    test_agent_integration()

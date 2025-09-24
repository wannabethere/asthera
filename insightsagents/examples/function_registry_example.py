"""
Function Registry Example

This example demonstrates how to use the ML Function Registry
with the existing ML agents for better function discovery.
"""

import os
import sys
import json
from typing import Dict, Any, List

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import chromadb
from app.tools.mltools.registry import create_function_retrieval_service


def demonstrate_agent_integration():
    """Demonstrate how ML agents can use the function registry."""
    print("=== ML Agent Integration Example ===\n")
    
    # Initialize the function retrieval service
    chroma_path = "./example_chroma_db"
    service = create_function_retrieval_service(chroma_path)
    
    # Check if service is available
    status = service.get_service_status()
    if not status["initialized"]:
        print("Function registry not initialized. Please run the initialization script first.")
        print("Run: python -m app.tools.mltools.initialize_function_registry")
        return
    
    # Simulate different agent scenarios
    agent_scenarios = [
        {
            "name": "Anomaly Detection Agent",
            "query": "I need to detect anomalies in my time series data",
            "context": {
                "task_type": "anomaly_detection",
                "data_columns": ["timestamp", "value", "category"],
                "complexity_level": "intermediate",
                "output_requirements": ["anomaly_flags", "confidence_scores"]
            }
        },
        {
            "name": "Customer Segmentation Agent", 
            "query": "Help me segment customers based on their behavior",
            "context": {
                "task_type": "segmentation",
                "data_columns": ["customer_id", "purchase_amount", "frequency", "category"],
                "complexity_level": "advanced",
                "output_requirements": ["cluster_assignments", "segment_profiles"]
            }
        },
        {
            "name": "Time Series Forecasting Agent",
            "query": "I want to forecast sales trends for the next quarter",
            "context": {
                "task_type": "forecasting",
                "data_columns": ["date", "sales", "region", "product"],
                "complexity_level": "advanced",
                "output_requirements": ["forecast_values", "confidence_intervals"]
            }
        },
        {
            "name": "Cohort Analysis Agent",
            "query": "Analyze customer retention and lifetime value",
            "context": {
                "task_type": "cohort_analysis",
                "data_columns": ["customer_id", "signup_date", "purchase_date", "amount"],
                "complexity_level": "intermediate",
                "output_requirements": ["retention_rates", "ltv_metrics"]
            }
        }
    ]
    
    for scenario in agent_scenarios:
        print(f"--- {scenario['name']} ---")
        print(f"Query: {scenario['query']}")
        print(f"Context: {json.dumps(scenario['context'], indent=2)}")
        
        # Search for relevant functions
        results = service.search_functions_for_agent(
            scenario['query'],
            context=scenario['context'],
            max_results=3
        )
        
        print(f"\nFound {len(results)} relevant functions:")
        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result['function_name']} ({result['category']})")
            print(f"   Description: {result['description']}")
            print(f"   Relevance Score: {result['relevance_score']:.3f}")
            print(f"   Complexity: {result['complexity']}")
            print(f"   Data Requirements: {', '.join(result['data_requirements'])}")
            
            # Show parameter information
            if result['parameters']:
                print(f"   Parameters:")
                for param_name, param_info in result['parameters'].items():
                    required = "Required" if param_info['required'] else "Optional"
                    print(f"     - {param_name}: {param_info['type']} ({required})")
            
            # Show usage patterns
            if result['usage_patterns']:
                print(f"   Usage Patterns:")
                for pattern in result['usage_patterns'][:2]:
                    print(f"     - {pattern}")
        
        print("\n" + "="*60 + "\n")


def demonstrate_search_capabilities():
    """Demonstrate various search capabilities."""
    print("=== Search Capabilities Demonstration ===\n")
    
    chroma_path = "./example_chroma_db"
    service = create_function_retrieval_service(chroma_path)
    
    # Test different types of queries
    search_queries = [
        "detect outliers in my data",
        "forecast time series trends",
        "segment customers by behavior",
        "calculate moving averages",
        "analyze cohort retention",
        "risk analysis var cvar",
        "funnel conversion analysis",
        "statistical correlation analysis"
    ]
    
    print("Testing various search queries:")
    for query in search_queries:
        results = service.search_functions_for_agent(query, max_results=2)
        print(f"\n'{query}':")
        for result in results:
            print(f"  - {result['function_name']} ({result['category']}) - Score: {result['relevance_score']:.3f}")
    
    print("\n" + "="*60 + "\n")


def demonstrate_use_case_search():
    """Demonstrate use case-based search."""
    print("=== Use Case Search Demonstration ===\n")
    
    chroma_path = "./example_chroma_db"
    service = create_function_retrieval_service(chroma_path)
    
    use_cases = [
        "anomaly_detection",
        "time_series_forecasting",
        "customer_segmentation", 
        "cohort_analysis",
        "risk_analysis",
        "funnel_analysis",
        "data_aggregation",
        "moving_averages"
    ]
    
    print("Searching by use case:")
    for use_case in use_cases:
        results = service.search_functions_by_use_case(use_case)
        print(f"\n{use_case.replace('_', ' ').title()}:")
        for result in results[:3]:
            print(f"  - {result['function_name']} ({result['category']})")
    
    print("\n" + "="*60 + "\n")


def demonstrate_function_details():
    """Demonstrate getting detailed function information."""
    print("=== Function Details Demonstration ===\n")
    
    chroma_path = "./example_chroma_db"
    service = create_function_retrieval_service(chroma_path)
    
    # Get a sample function
    results = service.search_functions_for_agent("detect anomalies", max_results=1)
    
    if results:
        function_name = results[0]['function_name']
        print(f"Getting details for: {function_name}")
        
        function_info = service.get_function_by_name(function_name)
        
        if function_info:
            print(f"\nFunction: {function_info['function_name']}")
            print(f"Module: {function_info['module']}")
            print(f"Category: {function_info['category']}")
            print(f"Complexity: {function_info['complexity']}")
            print(f"Description: {function_info['description']}")
            
            print(f"\nParameters:")
            for param_name, param_info in function_info['parameters'].items():
                required = "Required" if param_info['required'] else "Optional"
                default = f" (default: {param_info['default']})" if param_info['default'] is not None else ""
                print(f"  - {param_name}: {param_info['type']} ({required}){default}")
            
            print(f"\nReturn Type: {function_info['return_type']}")
            print(f"Output Description: {function_info['output_description']}")
            
            if function_info['examples']:
                print(f"\nExamples:")
                for example in function_info['examples'][:2]:
                    print(f"  {example}")
            
            if function_info['usage_patterns']:
                print(f"\nUsage Patterns:")
                for pattern in function_info['usage_patterns'][:2]:
                    print(f"  {pattern}")
            
            print(f"\nData Requirements: {', '.join(function_info['data_requirements'])}")
            print(f"Tags: {', '.join(function_info['tags'])}")
            print(f"Dependencies: {', '.join(function_info['dependencies'])}")
    
    print("\n" + "="*60 + "\n")


def demonstrate_recommendations():
    """Demonstrate function recommendations."""
    print("=== Function Recommendations Demonstration ===\n")
    
    chroma_path = "./example_chroma_db"
    service = create_function_retrieval_service(chroma_path)
    
    # Get a sample function
    results = service.search_functions_for_agent("detect anomalies", max_results=1)
    
    if results:
        function_name = results[0]['function_name']
        print(f"Getting recommendations for: {function_name}")
        
        recommendations = service.get_function_recommendations(
            function_name, 
            max_recommendations=5
        )
        
        print(f"\nFound {len(recommendations)} recommendations:")
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec['function_name']} ({rec['category']})")
            print(f"   Description: {rec['description']}")
            print(f"   Relevance Score: {rec['relevance_score']:.3f}")
            print(f"   Complexity: {rec['complexity']}")
    
    print("\n" + "="*60 + "\n")


def main():
    """Run all demonstrations."""
    print("ML Function Registry Demonstration")
    print("=" * 50)
    
    # Check if ChromaDB is available
    try:
        client = chromadb.PersistentClient(path="./example_chroma_db")
        collections = [col.name for col in client.list_collections()]
        
        if "ml_function_definitions" not in collections:
            print("Function registry not found. Please initialize it first:")
            print("python -m app.tools.mltools.initialize_function_registry --chroma-path ./example_chroma_db")
            return
        
        print("Function registry found. Running demonstrations...\n")
        
    except Exception as e:
        print(f"Error connecting to ChromaDB: {e}")
        return
    
    # Run demonstrations
    demonstrate_agent_integration()
    demonstrate_search_capabilities()
    demonstrate_use_case_search()
    demonstrate_function_details()
    demonstrate_recommendations()
    
    print("=== All Demonstrations Completed ===")


if __name__ == "__main__":
    main()

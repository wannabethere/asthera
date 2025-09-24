"""
Unified ML Function Registry Initialization

This script provides a unified interface for initializing different types of ML function registries:
- Basic Function Registry (MLFunctionRegistry)
- Enhanced Function Registry (with LLM integration)
- Comprehensive Function Registry (with rich context and AI-powered matching)
"""

import os
import sys
import argparse
import json
from typing import Dict, Any, Optional
from datetime import datetime

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

import chromadb
from chromadb.config import Settings

from app.tools.mltools.registry.function_registry import initialize_function_registry
from app.tools.mltools.registry.enhanced_comprehensive_registry import initialize_enhanced_comprehensive_registry
from app.tools.mltools.registry.function_search_interface import create_search_interface


def initialize_basic_registry(
    chroma_path: str = "./chroma_db",
    collection_name: str = "ml_function_definitions",
    force_recreate: bool = False
) -> Dict[str, Any]:
    """Initialize the basic function registry.
    
    Args:
        chroma_path: Path to ChromaDB storage
        collection_name: Name of the collection
        force_recreate: Whether to recreate the collection if it exists
        
    Returns:
        Dictionary with initialization results
    """
    print("=== Initializing Basic ML Function Registry ===\n")
    
    # Initialize ChromaDB client
    print(f"Connecting to ChromaDB at: {chroma_path}")
    client = chromadb.PersistentClient(path=chroma_path)
    
    # Check if collection already exists
    existing_collections = client.list_collections()
    
    if collection_name in existing_collections:
        if force_recreate:
            print(f"Deleting existing collection: {collection_name}")
            client.delete_collection(collection_name)
        else:
            print(f"Collection '{collection_name}' already exists. Use --force-recreate to overwrite.")
            return {"status": "exists", "collection_name": collection_name}
    
    # Initialize function registry
    print("Registering ML tool functions...")
    start_time = datetime.now()
    
    try:
        registry = initialize_function_registry(client)
        end_time = datetime.now()
        
        # Get statistics
        stats = registry.get_function_statistics()
        
        print(f"\n=== Initialization Complete ===")
        print(f"Time taken: {end_time - start_time}")
        print(f"Total functions registered: {stats['total_functions']}")
        print(f"Categories: {list(stats['by_category'].keys())}")
        print(f"Functions by category:")
        for category, count in stats['by_category'].items():
            print(f"  - {category}: {count}")
        
        return {
            "status": "success",
            "registry_type": "basic",
            "collection_name": collection_name,
            "total_functions": stats['total_functions'],
            "categories": stats['by_category'],
            "time_taken": str(end_time - start_time)
        }
        
    except Exception as e:
        print(f"Error during initialization: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


def initialize_enhanced_registry(
    chroma_path: str = "./chroma_db",
    collection_name: str = "ml_function_definitions",
    llm_model: str = "gpt-3.5-turbo",
    force_recreate: bool = False
) -> Dict[str, Any]:
    """Initialize the enhanced function registry with LLM integration.
    
    Args:
        chroma_path: Path to ChromaDB storage
        collection_name: Name of the collection
        llm_model: LLM model to use for metadata generation
        force_recreate: Whether to recreate the collection if it exists
        
    Returns:
        Dictionary with initialization results
    """
    print("=== Initializing Enhanced ML Function Registry with LLM Integration ===\n")
    
    # Initialize ChromaDB client
    print(f"Connecting to ChromaDB at: {chroma_path}")
    client = chromadb.PersistentClient(path=chroma_path)
    
    # Check if collection already exists
    existing_collections = client.list_collections()
    
    if collection_name in existing_collections:
        if force_recreate:
            print(f"Deleting existing collection: {collection_name}")
            client.delete_collection(collection_name)
        else:
            print(f"Collection '{collection_name}' already exists. Use --force-recreate to overwrite.")
            return {"status": "exists", "collection_name": collection_name}
    
    # Initialize enhanced function registry
    print(f"Registering ML tool functions with LLM metadata generation (model: {llm_model})...")
    start_time = datetime.now()
    
    try:
        registry = initialize_function_registry(client)
        end_time = datetime.now()
        
        # Get statistics
        stats = registry.get_function_statistics()
        
        print(f"\n=== Initialization Complete ===")
        print(f"Time taken: {end_time - start_time}")
        print(f"Total functions registered: {stats['total_functions']}")
        print(f"Categories: {list(stats['by_category'].keys())}")
        print(f"Functions by category:")
        for category, count in stats['by_category'].items():
            print(f"  - {category}: {count}")
        
        return {
            "status": "success",
            "registry_type": "enhanced",
            "collection_name": collection_name,
            "llm_model": llm_model,
            "total_functions": stats['total_functions'],
            "categories": stats['by_category'],
            "time_taken": str(end_time - start_time)
        }
        
    except Exception as e:
        print(f"Error during initialization: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


def initialize_comprehensive_registry(
    collection_name: str = "comprehensive_ml_functions",
    toolspecs_path: str = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/toolspecs",
    instructions_path: str = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/instructions",
    usage_examples_path: str = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/usage_examples",
    code_examples_path: str = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/code_examples",
    force_recreate: bool = False,
    chroma_path: str = None,
    llm_model: str = "gpt-3.5-turbo",
    llm=None,
    retrieval_helper=None
) -> Dict[str, Any]:
    """Initialize the comprehensive function registry with rich context and AI-powered matching.
    
    Args:
        collection_name: Name of the collection
        toolspecs_path: Path to function specifications JSON files
        instructions_path: Path to instructions JSON files
        usage_examples_path: Path to usage examples JSON files
        code_examples_path: Path to code examples JSON files
        force_recreate: Whether to recreate the collection if it exists
        chroma_path: Path to ChromaDB storage (uses CHROMA_STORE_PATH if None)
        llm_model: LLM model to use for metadata generation
        llm: LangChain LLM instance for enhanced retrieval
        retrieval_helper: RetrievalHelper instance for comprehensive function retrieval
        
    Returns:
        Dictionary with initialization results
    """
    print("=== Initializing Comprehensive ML Function Registry ===\n")
    
    # Initialize comprehensive function registry
    print("Loading comprehensive function data...")
    start_time = datetime.now()
    
    try:
        registry = initialize_enhanced_comprehensive_registry(
            collection_name=collection_name,
            force_recreate=force_recreate,
            toolspecs_path=toolspecs_path,
            instructions_path=instructions_path,
            usage_examples_path=usage_examples_path,
            code_examples_path=code_examples_path,
            chroma_path=chroma_path,
            llm_model=llm_model,
            llm=llm,
            retrieval_helper=retrieval_helper
        )
        
        end_time = datetime.now()
        
        # Get statistics
        stats = registry.get_function_statistics()
        
        print(f"\n=== Initialization Complete ===")
        print(f"Time taken: {end_time - start_time}")
        print(f"Total functions registered: {stats['total_functions']}")
        print(f"Categories: {list(stats['by_category'].keys())}")
        print(f"Functions by category:")
        for category, count in stats['by_category'].items():
            print(f"  - {category}: {count}")
        
        return {
            "status": "success",
            "registry_type": "comprehensive",
            "collection_name": collection_name,
            "total_functions": stats['total_functions'],
            "categories": stats['by_category'],
            "time_taken": str(end_time - start_time)
        }
        
    except Exception as e:
        print(f"Error during initialization: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


def test_registry_functionality(
    registry_type: str = "comprehensive",
    collection_name: str = "comprehensive_ml_functions",
    chroma_path: str = "./chroma_db",
    llm_model: str = "gpt-3.5-turbo"
) -> Dict[str, Any]:
    """Test the registry functionality.
    
    Args:
        registry_type: Type of registry to test ("basic", "enhanced", "comprehensive")
        collection_name: Name of the collection
        chroma_path: Path to ChromaDB storage
        llm_model: LLM model to use
        
    Returns:
        Dictionary with test results
    """
    print(f"\n=== Testing {registry_type.title()} Registry Functionality ===\n")
    
    try:
        # Initialize ChromaDB client
        client = chromadb.PersistentClient(path=chroma_path)
        
        if registry_type == "comprehensive":
            # Initialize comprehensive registry
            from .enhanced_comprehensive_registry import EnhancedComprehensiveRegistry
            registry = EnhancedComprehensiveRegistry(
                collection_name=collection_name,
                chroma_path=chroma_path,
                llm_model=llm_model
            )
        else:
            # Create search interface for basic/enhanced
            search_interface = create_search_interface(client, llm_model)
            registry = search_interface.registry
        
        # Test queries
        test_queries = [
            "detect anomalies in time series data",
            "customer segmentation clustering",
            "forecast time series trends",
            "cohort analysis retention",
            "risk analysis var cvar",
            "funnel analysis conversion",
            "moving averages rolling",
            "statistical analysis correlation"
        ]
        
        test_results = {}
        
        for query in test_queries:
            print(f"Testing query: '{query}'")
            results = registry.search_functions(query, n_results=3)
            
            test_results[query] = {
                "results_count": len(results),
                "top_functions": [r.get('function_name', r.function_name if hasattr(r, 'function_name') else 'unknown') for r in results[:3]]
            }
            
            print(f"  Found {len(results)} results")
            for result in results[:3]:
                if isinstance(result, dict):
                    func_name = result.get('function_name', 'unknown')
                    category = result.get('category', 'unknown')
                else:
                    func_name = getattr(result, 'function_name', 'unknown')
                    category = getattr(result, 'category', 'unknown')
                print(f"    - {func_name} ({category})")
            print()
        
        # Test category filtering
        print("Testing category filtering...")
        anomaly_results = registry.search_functions(
            "detect anomalies", 
            category="anomaly_detection", 
            n_results=3
        )
        print(f"Anomaly detection functions: {len(anomaly_results)}")
        
        # Test complexity filtering (if supported)
        if hasattr(registry, 'search_functions') and 'complexity' in registry.search_functions.__code__.co_varnames:
            print("Testing complexity filtering...")
            simple_results = registry.search_functions(
                "basic statistics", 
                complexity="simple", 
                n_results=3
            )
            print(f"Simple functions: {len(simple_results)}")
        
        # Get registry statistics
        if hasattr(registry, 'get_function_statistics'):
            stats = registry.get_function_statistics()
            print(f"\nRegistry Statistics:")
            print(f"Total functions: {stats.get('total_functions', 'N/A')}")
            if 'functions_with_examples' in stats:
                print(f"Functions with examples: {stats['functions_with_examples']}")
            if 'functions_with_instructions' in stats:
                print(f"Functions with instructions: {stats['functions_with_instructions']}")
        
        return {
            "status": "success",
            "registry_type": registry_type,
            "test_queries": test_results
        }
        
    except Exception as e:
        print(f"Error during testing: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


def export_function_catalog(
    registry_type: str = "comprehensive",
    collection_name: str = "comprehensive_ml_functions",
    chroma_path: str = "./chroma_db",
    output_file: str = "function_catalog.json",
    llm_model: str = "gpt-3.5-turbo"
) -> Dict[str, Any]:
    """Export the function catalog to a JSON file.
    
    Args:
        registry_type: Type of registry to export ("basic", "enhanced", "comprehensive")
        collection_name: Name of the collection
        chroma_path: Path to ChromaDB storage
        output_file: Output file path
        llm_model: LLM model to use
        
    Returns:
        Dictionary with export results
    """
    print(f"\n=== Exporting {registry_type.title()} Function Catalog ===\n")
    
    try:
        # Initialize ChromaDB client
        client = chromadb.PersistentClient(path=chroma_path)
        
        if registry_type == "comprehensive":
            # Initialize comprehensive registry
            from .enhanced_comprehensive_registry import EnhancedComprehensiveRegistry
            registry = EnhancedComprehensiveRegistry(
                collection_name=collection_name,
                chroma_path=chroma_path,
                llm_model=llm_model
            )
            
            # Get all functions
            all_functions = registry.get_all_functions()
            
            # Create comprehensive catalog
            catalog = {
                "export_timestamp": datetime.now().isoformat(),
                "registry_type": "comprehensive",
                "total_functions": len(all_functions),
                "functions": []
            }
            
            for func_metadata in all_functions:
                function_info = {
                    "name": func_metadata.name,
                    "module": func_metadata.module,
                    "category": func_metadata.category,
                    "description": func_metadata.description,
                    "complexity": func_metadata.complexity,
                    "tags": func_metadata.tags,
                    "parameters": func_metadata.parameters,
                    "return_type": func_metadata.return_type,
                    "examples": func_metadata.examples,
                    "usage_patterns": func_metadata.usage_patterns,
                    "data_requirements": func_metadata.data_requirements,
                    "output_description": func_metadata.output_description,
                    "dependencies": func_metadata.dependencies
                }
                catalog["functions"].append(function_info)
        else:
            # Create search interface for basic/enhanced
            search_interface = create_search_interface(client, llm_model)
            all_functions = search_interface.registry.get_all_functions()
            
            # Create catalog
            catalog = {
                "export_timestamp": datetime.now().isoformat(),
                "registry_type": registry_type,
                "total_functions": len(all_functions),
                "functions": []
            }
            
            for func_metadata in all_functions:
                function_info = {
                    "name": func_metadata.name,
                    "module": func_metadata.module,
                    "category": func_metadata.category,
                    "description": func_metadata.description,
                    "complexity": func_metadata.complexity,
                    "tags": func_metadata.tags,
                    "parameters": func_metadata.parameters,
                    "return_type": func_metadata.return_type,
                    "examples": func_metadata.examples,
                    "usage_patterns": func_metadata.usage_patterns,
                    "data_requirements": func_metadata.data_requirements,
                    "output_description": func_metadata.output_description,
                    "dependencies": func_metadata.dependencies
                }
                catalog["functions"].append(function_info)
        
        # Write to file
        with open(output_file, 'w') as f:
            json.dump(catalog, f, indent=2)
        
        print(f"Function catalog exported to: {output_file}")
        print(f"Total functions exported: {len(all_functions)}")
        
        return {
            "status": "success",
            "output_file": output_file,
            "total_functions": len(all_functions)
        }
        
    except Exception as e:
        print(f"Error during export: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


def main():
    """Main function for command-line interface."""
    parser = argparse.ArgumentParser(description="Unified ML Function Registry Initialization")
    
    # Registry type selection
    parser.add_argument("--registry-type", 
                       choices=["basic", "enhanced", "comprehensive"], 
                       default="comprehensive",
                       help="Type of registry to initialize")
    
    # Common arguments
    parser.add_argument("--chroma-path", default="./chroma_db", help="Path to ChromaDB storage")
    parser.add_argument("--collection-name", default="comprehensive_ml_functions", help="Collection name")
    parser.add_argument("--force-recreate", action="store_true", help="Force recreate existing collection")
    
    # LLM arguments
    parser.add_argument("--llm-model", default="gpt-3.5-turbo", help="LLM model to use for metadata generation")
    
    # Comprehensive registry specific arguments
    parser.add_argument("--toolspecs-path", 
                       default="/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/toolspecs", 
                       help="Path to function specifications")
    parser.add_argument("--instructions-path", 
                       default="/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/instructions", 
                       help="Path to instructions")
    parser.add_argument("--usage-examples-path", 
                       default="/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/usage_examples", 
                       help="Path to usage examples")
    parser.add_argument("--code-examples-path", 
                       default="/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/code_examples", 
                       help="Path to code examples")
    
    # Action arguments
    parser.add_argument("--test", action="store_true", help="Run registry functionality tests")
    parser.add_argument("--export", action="store_true", help="Export function catalog")
    parser.add_argument("--output-file", default="function_catalog.json", help="Output file for export")
    
    args = parser.parse_args()
    
    # Initialize registry based on type
    if args.registry_type == "basic":
        init_result = initialize_basic_registry(
            chroma_path=args.chroma_path,
            collection_name=args.collection_name,
            force_recreate=args.force_recreate
        )
    elif args.registry_type == "enhanced":
        init_result = initialize_enhanced_registry(
            chroma_path=args.chroma_path,
            collection_name=args.collection_name,
            llm_model=args.llm_model,
            force_recreate=args.force_recreate
        )
    else:  # comprehensive
        init_result = initialize_comprehensive_registry(
            collection_name=args.collection_name,
            toolspecs_path=args.toolspecs_path,
            instructions_path=args.instructions_path,
            usage_examples_path=args.usage_examples_path,
            code_examples_path=args.code_examples_path,
            force_recreate=args.force_recreate,
            chroma_path=args.chroma_path,
            llm_model=args.llm_model
        )
    
    if init_result["status"] == "error":
        print(f"Initialization failed: {init_result['error']}")
        return 1
    
    # Run tests if requested
    if args.test:
        test_result = test_registry_functionality(
            registry_type=args.registry_type,
            collection_name=args.collection_name,
            chroma_path=args.chroma_path,
            llm_model=args.llm_model
        )
        if test_result["status"] == "error":
            print(f"Testing failed: {test_result['error']}")
            return 1
    
    # Export catalog if requested
    if args.export:
        export_result = export_function_catalog(
            registry_type=args.registry_type,
            collection_name=args.collection_name,
            chroma_path=args.chroma_path,
            output_file=args.output_file,
            llm_model=args.llm_model
        )
        if export_result["status"] == "error":
            print(f"Export failed: {export_result['error']}")
            return 1
    
    print("\n=== All operations completed successfully ===")
    return 0


if __name__ == "__main__":
    exit(main())

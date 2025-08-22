#!/usr/bin/env python3
"""
Example script demonstrating how to use the N8nChromaDBStore utility programmatically.

This script shows various ways to interact with the n8n components stored in ChromaDB.
"""

import sys
from pathlib import Path

# Add the parent directory to the Python path to import the utility
sys.path.append(str(Path(__file__).parent.parent))

from app.utils.n8n_chromadb_store import N8nChromaDBStore


def example_basic_usage():
    """Basic usage example: initialize store and get stats."""
    print("=== Basic Usage Example ===")
    
    # Initialize the store (defaults to 'n8n_store' collection)
    store = N8nChromaDBStore()
    
    # Get collection statistics
    stats = store.get_collection_stats()
    print(f"Collection: {stats['collection_name']}")
    print(f"Storage Type: {stats['storage_type']}")
    print(f"Storage Path: {stats['storage_path']}")
    print(f"Total nodes: {stats['total_nodes']}")
    print(f"Metadata keys: {stats['sample_metadata_keys']}")
    
    return store


def example_local_storage():
    """Example of using local storage with custom path."""
    print("\n=== Local Storage Example ===")
    
    # Initialize store with local storage
    local_store = N8nChromaDBStore(
        use_local=True,
        local_path="custom_n8n_store"
    )
    
    # Get storage information
    storage_info = local_store.get_storage_info()
    print(f"Local Storage Configuration:")
    print(f"  Collection: {storage_info['collection_name']}")
    print(f"  Local Path: {storage_info['absolute_local_path']}")
    print(f"  Path Exists: {storage_info['local_path_exists']}")
    print(f"  Path Size: {storage_info['local_path_size']} bytes")
    
    return local_store


def example_search_nodes(store):
    """Example of searching for specific types of nodes."""
    print("\n=== Search Examples ===")
    
    # Search for HTTP-related nodes
    print("Searching for 'HTTP' nodes...")
    http_results = store.search_nodes("HTTP", n_results=5)
    
    if http_results:
        print(f"Found {len(http_results)} HTTP-related nodes:")
        for i, result in enumerate(http_results, 1):
            metadata = result['metadata']
            print(f"  {i}. {metadata.get('node_name', 'Unknown')}")
            print(f"     Type: {metadata.get('node_type', 'Unknown')}")
            print(f"     Similarity: {1 - result['distance']:.4f}")
    
    # Search for email-related nodes
    print("\nSearching for 'email' nodes...")
    email_results = store.search_nodes("email", n_results=3)
    
    if email_results:
        print(f"Found {len(email_results)} email-related nodes:")
        for i, result in enumerate(email_results, 1):
            metadata = result['metadata']
            print(f"  {i}. {metadata.get('node_name', 'Unknown')}")
            print(f"     Type: {metadata.get('node_type', 'Unknown')}")
            print(f"     Similarity: {1 - result['distance']:.4f}")


def example_filtered_search(store):
    """Example of using metadata filters for search."""
    print("\n=== Filtered Search Examples ===")
    
    # Search for nodes with specific resource type
    print("Searching for nodes with 'resource' in metadata...")
    resource_results = store.search_nodes(
        "request", 
        n_results=5,
        filters={"resource": {"$exists": True}}
    )
    
    if resource_results:
        print(f"Found {len(resource_results)} nodes with resource metadata:")
        for i, result in enumerate(resource_results, 1):
            metadata = result['metadata']
            print(f"  {i}. {metadata.get('node_name', 'Unknown')}")
            print(f"     Resource: {metadata.get('resource', 'N/A')}")
            print(f"     Operation: {metadata.get('operation', 'N/A')}")


def example_get_specific_node(store):
    """Example of retrieving a specific node by ID."""
    print("\n=== Get Specific Node Example ===")
    
    # First, search for a node to get its ID
    search_results = store.search_nodes("HTTP", n_results=1)
    
    if search_results:
        node_id = search_results[0]['id']
        print(f"Retrieving node with ID: {node_id}")
        
        # Get the specific node
        node_data = store.get_node_by_id(node_id)
        
        if node_data:
            print("Node retrieved successfully:")
            print(f"  Name: {node_data['metadata'].get('node_name', 'Unknown')}")
            print(f"  Type: {node_data['metadata'].get('node_type', 'Unknown')}")
            print(f"  Content preview: {node_data['document'][:200]}...")
        else:
            print("Failed to retrieve node")
    else:
        print("No nodes found to retrieve")


def example_batch_operations(store):
    """Example of batch operations and collection management."""
    print("\n=== Batch Operations Example ===")
    
    # Get current collection stats
    current_stats = store.get_collection_stats()
    print(f"Current collection size: {current_stats['total_nodes']} nodes")
    
    # Example: You could add more nodes here
    # new_nodes = [...]
    # for node in new_nodes:
    #     store.store_node(node)
    
    # Example: Clear collection (commented out for safety)
    # print("Clearing collection...")
    # store.clear_collection()
    # print("Collection cleared")
    
    print("Batch operations completed")


def main():
    """Main function to run all examples."""
    try:
        print("N8nChromaDBStore Utility Examples")
        print("=" * 50)
        
        # Check if collection has data
        store = example_basic_usage()
        
        if store.get_collection_stats()['total_nodes'] == 0:
            print("\nNo nodes found in collection. Please load nodes first using:")
            print("python scripts/load_n8n_to_chromadb.py")
            return
        
        # Run examples
        example_local_storage()
        example_search_nodes(store)
        example_filtered_search(store)
        example_get_specific_node(store)
        example_batch_operations(store)
        
        print("\n" + "=" * 50)
        print("All examples completed successfully!")
        
    except Exception as e:
        print(f"Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

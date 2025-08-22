#!/usr/bin/env python3
"""
Script to load n8n node components into ChromaDB.
This script uses the N8nChromaDBStore utility to parse and store n8n components.

Usage:
    python load_n8n_to_chromadb.py [--file path/to/nodes.json] [--collection n8n_store] [--clear] [--search query]
"""

import argparse
import sys
import os
from pathlib import Path

# Add the parent directory to the Python path to import the utility
sys.path.append(str(Path(__file__).parent.parent))

from app.utils.n8n_chromadb_store import N8nChromaDBStore


def main():
    parser = argparse.ArgumentParser(
        description="Load n8n node components into ChromaDB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Load nodes from default nodes.json file
    python load_n8n_to_chromadb.py
    
    # Load nodes from specific file
    python load_n8n_to_chromadb.py --file /path/to/custom_nodes.json
    
    # Use custom collection name
    python load_n8n_to_chromadb.py --collection my_n8n_nodes
    
    # Clear existing collection before loading
    python load_n8n_to_chromadb.py --clear
    
    # Search for specific nodes after loading
    python load_n8n_to_chromadb.py --search "HTTP request"
    
    # Just search without loading
    python load_n8n_to_chromadb.py --search "email" --no-load
        """
    )
    
    parser.add_argument(
        '--file', '-f',
        type=str,
        default=None,
        help='Path to the n8n nodes JSON file (default: auto-detect)'
    )
    
    parser.add_argument(
        '--collection', '-c',
        type=str,
        default=None,
        help='ChromaDB collection name (default: from settings)'
    )
    
    parser.add_argument(
        '--local', '-l',
        action='store_true',
        default=None,
        help='Force local storage (default: from settings)'
    )
    
    parser.add_argument(
        '--local-path',
        type=str,
        default=None,
        help='Custom local storage path (default: from settings)'
    )
    
    parser.add_argument(
        '--clear',
        action='store_true',
        help='Clear existing collection before loading new data'
    )
    
    parser.add_argument(
        '--search', '-s',
        type=str,
        default=None,
        help='Search query to execute after loading'
    )
    
    parser.add_argument(
        '--no-load',
        action='store_true',
        help='Skip loading nodes, only perform search if specified'
    )
    
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show collection statistics'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    try:
        # Initialize the store with custom settings if provided
        print(f"Initializing ChromaDB store...")
        store = N8nChromaDBStore(
            collection_name=args.collection,
            use_local=args.local,
            local_path=args.local_path
        )
        
        # Show storage configuration
        storage_info = store.get_storage_info()
        print(f"Collection: {storage_info['collection_name']}")
        print(f"Storage Type: {storage_info['storage_type']}")
        if storage_info['storage_type'] == 'local':
            print(f"Local Path: {storage_info['absolute_local_path']}")
        else:
            print(f"Remote Host: {storage_info['remote_host']}:{storage_info['remote_port']}")
        
        # Show initial stats
        if args.stats:
            print("\nInitial collection statistics:")
            stats = store.get_collection_stats()
            for key, value in stats.items():
                print(f"  {key}: {value}")
        
        # Clear collection if requested
        if args.clear:
            print(f"\nClearing collection: {args.collection}")
            store.clear_collection()
            print("Collection cleared successfully")
        
        # Load nodes if not skipped
        if not args.no_load:
            # Determine file path
            if args.file:
                nodes_file = Path(args.file)
                if not nodes_file.exists():
                    print(f"Error: File not found: {nodes_file}")
                    sys.exit(1)
            else:
                # Auto-detect nodes.json
                nodes_file = Path(__file__).parent.parent / "app" / "n8ncomponents" / "nodes.json"
                if not nodes_file.exists():
                    print(f"Error: nodes.json not found at: {nodes_file}")
                    print("Please specify the file path using --file option")
                    sys.exit(1)
            
            print(f"\nLoading nodes from: {nodes_file}")
            print(f"File size: {nodes_file.stat().st_size / (1024*1024):.2f} MB")
            
            # Load nodes
            stored_ids = store.store_nodes_from_json(str(nodes_file))
            print(f"\nSuccessfully stored {len(stored_ids)} nodes in ChromaDB")
            
            # Show updated stats
            if args.stats:
                print("\nUpdated collection statistics:")
                updated_stats = store.get_collection_stats()
                for key, value in updated_stats.items():
                    print(f"  {key}: {value}")
        
        # Perform search if requested
        if args.search:
            print(f"\nSearching for: '{args.search}'")
            search_results = store.search_nodes(args.search, n_results=10)
            
            if search_results:
                print(f"Found {len(search_results)} results:")
                for i, result in enumerate(search_results, 1):
                    metadata = result['metadata']
                    print(f"\n{i}. {metadata.get('node_name', 'Unknown')}")
                    print(f"   Type: {metadata.get('node_type', 'Unknown')}")
                    print(f"   Resource: {metadata.get('resource', 'N/A')}")
                    print(f"   Operation: {metadata.get('operation', 'N/A')}")
                    print(f"   Similarity: {1 - result['distance']:.4f}")
                    
                    # Show first few lines of content
                    content = result['document']
                    if content:
                        lines = content.split('\n')[:3]
                        print(f"   Content preview: {' | '.join(lines)}")
            else:
                print("No search results found")
        
        print("\nOperation completed successfully!")
        
    except KeyboardInterrupt:
        print("\nOperation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

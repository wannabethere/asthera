#!/usr/bin/env python3
"""
Utility script to fix ChromaDB collections that don't have embedding functions configured.

This script helps resolve the "You must provide an embedding function to compute embeddings" error
by recreating collections with proper embedding functions.
"""

import sys
import os
from typing import Optional, Dict, Any

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.utils.chromadb import ChromaDB
from chromadb import EmbeddingFunction
from chromadb.utils import embedding_functions


def create_default_embedding_function() -> EmbeddingFunction:
    """Create a default embedding function using sentence-transformers."""
    try:
        # Try to use sentence-transformers if available
        return embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
    except ImportError:
        print("Warning: sentence-transformers not available. Using default embedding function.")
        # Fallback to a basic embedding function
        return embedding_functions.DefaultEmbeddingFunction()


def fix_collection(collection_name: str, connection_params: Optional[Dict[str, Any]] = None) -> bool:
    """
    Fix a collection by recreating it with an embedding function.
    
    Args:
        collection_name: Name of the collection to fix
        connection_params: Optional connection parameters for ChromaDB
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create embedding function
        embedding_function = create_default_embedding_function()
        
        # Initialize ChromaDB with embedding function
        chroma_db = ChromaDB(
            connection_params=connection_params,
            embedding_function=embedding_function,
            log_level="INFO"
        )
        
        print(f"Checking collection '{collection_name}'...")
        
        # Check if collection has embedding function
        if chroma_db.check_collection_embedding_function(collection_name):
            print(f"✓ Collection '{collection_name}' already has an embedding function configured.")
            return True
        
        print(f"✗ Collection '{collection_name}' does not have an embedding function.")
        print(f"Recreating collection '{collection_name}' with embedding function...")
        
        # Recreate the collection with embedding function
        collection = chroma_db.recreate_collection_with_embedding(collection_name)
        
        # Verify the fix
        if chroma_db.check_collection_embedding_function(collection_name):
            print(f"✓ Successfully recreated collection '{collection_name}' with embedding function.")
            return True
        else:
            print(f"✗ Failed to verify embedding function for collection '{collection_name}'.")
            return False
            
    except Exception as e:
        print(f"✗ Error fixing collection '{collection_name}': {str(e)}")
        return False


def list_collections_with_embedding_status(connection_params: Optional[Dict[str, Any]] = None) -> None:
    """
    List all collections and their embedding function status.
    
    Args:
        connection_params: Optional connection parameters for ChromaDB
    """
    try:
        # Initialize ChromaDB
        chroma_db = ChromaDB(
            connection_params=connection_params,
            log_level="INFO"
        )
        
        print("Listing all collections and their embedding function status:")
        print("-" * 60)
        
        collections = chroma_db.list_collections()
        
        if not collections:
            print("No collections found.")
            return
        
        for collection in collections:
            collection_name = collection.name
            has_embedding = chroma_db.check_collection_embedding_function(collection_name)
            status = "✓ Has embedding function" if has_embedding else "✗ No embedding function"
            print(f"{collection_name}: {status}")
            
    except Exception as e:
        print(f"Error listing collections: {str(e)}")


def main():
    """Main function to handle command line arguments."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Fix ChromaDB collections that don't have embedding functions configured"
    )
    parser.add_argument(
        "action",
        choices=["fix", "list"],
        help="Action to perform: 'fix' to fix a specific collection, 'list' to list all collections"
    )
    parser.add_argument(
        "--collection",
        help="Name of the collection to fix (required for 'fix' action)"
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="ChromaDB host (default: localhost)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="ChromaDB port (default: 8000)"
    )
    
    args = parser.parse_args()
    
    # Set up connection parameters
    connection_params = {
        "host": args.host,
        "port": args.port
    }
    
    if args.action == "list":
        list_collections_with_embedding_status(connection_params)
    elif args.action == "fix":
        if not args.collection:
            print("Error: --collection is required for 'fix' action")
            sys.exit(1)
        
        success = fix_collection(args.collection, connection_params)
        if success:
            print(f"\n✓ Collection '{args.collection}' has been fixed successfully!")
            sys.exit(0)
        else:
            print(f"\n✗ Failed to fix collection '{args.collection}'.")
            sys.exit(1)


if __name__ == "__main__":
    main() 
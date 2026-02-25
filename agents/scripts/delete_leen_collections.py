#!/usr/bin/env python3
"""
Script to delete leen_* collections from Qdrant.

This script deletes:
- leen_db_schema
- leen_table_description
- leen_column_metadata

Usage:
    python delete_leen_collections.py --host localhost --port 6333
"""

import logging
import sys
from pathlib import Path

# Add agents directory to path
agents_dir = Path(__file__).parent.parent
sys.path.insert(0, str(agents_dir))

from qdrant_client import QdrantClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def delete_collections(host: str = "localhost", port: int = 6333):
    """Delete leen_* collections from Qdrant."""
    collections_to_delete = [
        "leen_db_schema",
        "leen_table_description",
        "leen_column_metadata",
    ]
    
    logger.info("=" * 80)
    logger.info("DELETING LEEN COLLECTIONS FROM QDRANT")
    logger.info("=" * 80)
    logger.info(f"Qdrant: {host}:{port}")
    logger.info(f"Collections to delete: {', '.join(collections_to_delete)}")
    logger.info("=" * 80)
    
    # Confirm before proceeding
    response = input("\n⚠️  This will DELETE the entire collections. Continue? (yes/no): ")
    if response.lower() != "yes":
        logger.info("Cancelled by user")
        return
    
    try:
        # Connect to Qdrant
        client = QdrantClient(host=host, port=port)
        
        # Get existing collections
        existing_collections = client.get_collections().collections
        existing_names = {col.name for col in existing_collections}
        
        deleted = []
        not_found = []
        errors = []
        
        for collection_name in collections_to_delete:
            try:
                if collection_name in existing_names:
                    logger.info(f"Deleting collection: {collection_name}")
                    client.delete_collection(collection_name=collection_name)
                    deleted.append(collection_name)
                    logger.info(f"✓ Successfully deleted: {collection_name}")
                else:
                    logger.warning(f"Collection not found: {collection_name}")
                    not_found.append(collection_name)
            except Exception as e:
                error_msg = f"Error deleting {collection_name}: {str(e)}"
                logger.error(error_msg)
                errors.append((collection_name, str(e)))
        
        # Print summary
        logger.info("\n" + "=" * 80)
        logger.info("DELETION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Deleted: {len(deleted)}")
        if deleted:
            logger.info(f"  ✓ {', '.join(deleted)}")
        
        if not_found:
            logger.info(f"Not found: {len(not_found)}")
            logger.info(f"  - {', '.join(not_found)}")
        
        if errors:
            logger.error(f"Errors: {len(errors)}")
            for collection, error in errors:
                logger.error(f"  ✗ {collection}: {error}")
        else:
            logger.info("All collections processed successfully! ✓")
        
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Delete leen_* collections from Qdrant"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Qdrant host (default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=6333,
        help="Qdrant port (default: 6333)",
    )
    
    args = parser.parse_args()
    delete_collections(host=args.host, port=args.port)

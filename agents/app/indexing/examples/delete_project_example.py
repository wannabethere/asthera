#!/usr/bin/env python3
"""
Example script demonstrating how to delete a project and all its associated data.

This script shows how to use the new project deletion functionality to remove
all data associated with a specific project ID from all document stores.
"""

import asyncio
import logging
import chromadb
from pathlib import Path

from app.indexing.project_reader import ProjectReader
from app.settings import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("delete-project-example")

async def delete_project_example(project_id: str):
    """Example function showing how to delete a project.
    
    Args:
        project_id: The project ID to delete
    """
    try:
        # Get settings
        settings = get_settings()
        
        # Initialize ChromaDB client
        persistent_client = chromadb.PersistentClient(
            path=settings.CHROMA_STORE_PATH
        )
        
        # Set up base path for project files
        base_path = Path("/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/sql_meta")
        
        # Initialize ProjectReader
        reader = ProjectReader(base_path, persistent_client)
        
        logger.info(f"Starting deletion of project: {project_id}")
        
        # Delete the project and all its associated data
        deletion_result = await reader.delete_project(project_id)
        
        # Print results
        logger.info(f"\n{'='*60}")
        logger.info(f"DELETION RESULTS FOR PROJECT: {project_id}")
        logger.info(f"{'='*60}")
        
        logger.info(f"Total documents deleted: {deletion_result.get('total_documents_deleted', 0)}")
        logger.info(f"Components processed: {len(deletion_result.get('components_deleted', {}))}")
        
        logger.info("\nComponent deletion details:")
        for component, result in deletion_result.get('components_deleted', {}).items():
            if isinstance(result, dict):
                docs_deleted = result.get('documents_deleted', 0)
                logger.info(f"  {component}: {docs_deleted} documents deleted")
            else:
                logger.info(f"  {component}: {result}")
        
        if deletion_result.get('errors'):
            logger.warning(f"\nErrors encountered ({len(deletion_result['errors'])}):")
            for error in deletion_result['errors']:
                logger.warning(f"  - {error}")
        else:
            logger.info("\n✅ No errors encountered during deletion")
        
        logger.info(f"\n🎉 Project '{project_id}' deletion completed successfully!")
        
        return deletion_result
        
    except Exception as e:
        logger.error(f"❌ Error during project deletion: {str(e)}")
        raise

async def main():
    """Main function to run the deletion example."""
    
    # Example project ID to delete
    # Change this to the actual project ID you want to delete
    project_id = "cve_data"
    
    logger.info("Project Deletion Example")
    logger.info("=" * 50)
    logger.info(f"Project ID to delete: {project_id}")
    logger.info("=" * 50)
    
    # Confirm deletion (in a real application, you might want to add user confirmation)
    logger.warning(f"⚠️  WARNING: This will delete ALL data for project '{project_id}'")
    logger.warning("This includes:")
    logger.warning("  - Database schemas")
    logger.warning("  - Table descriptions") 
    logger.warning("  - Historical questions")
    logger.warning("  - Instructions")
    logger.warning("  - Project metadata")
    logger.warning("  - SQL pairs/examples")
    logger.warning("  - Project-specific collections")
    
    # Uncomment the line below to actually perform the deletion
    result = await delete_project_example(project_id)
    
    # For safety, we'll just show what would happen without actually deleting
    logger.info(f"\nTo actually delete project '{project_id}', uncomment the deletion call in the main() function")
    logger.info("Example usage:")
    logger.info("  result = await delete_project_example(project_id)")

if __name__ == "__main__":
    asyncio.run(main())

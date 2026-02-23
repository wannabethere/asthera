"""
Direct test for MDL retrieval to debug why table names are showing as 'unknown'.

This script directly calls the MDL service with the same query used in the workflow
to see what's actually being returned from Qdrant.
"""
import asyncio
import json
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.retrieval.mdl_service import MDLRetrievalService
from app.core.dependencies import get_doc_store_provider

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    stream=sys.stdout,
    force=True
)
logger = logging.getLogger(__name__)

# Enable verbose logging for relevant modules
logging.getLogger("app.retrieval.mdl_service").setLevel(logging.DEBUG)
logging.getLogger("app.storage.documents").setLevel(logging.DEBUG)
logging.getLogger("app.core.dependencies").setLevel(logging.DEBUG)


async def test_mdl_retrieval():
    """Test MDL retrieval with the same query from the workflow."""
    query = "vulnerabilities patch_compliance cve_exposure How do I calculate mean time to remediate critical vulnerabilities using Qualys data? Show me what tables are available."
    
    logger.info("=" * 80)
    logger.info("Testing MDL Retrieval Service")
    logger.info("=" * 80)
    logger.info(f"Query: {query}")
    logger.info("")
    
    try:
        # Initialize MDL service
        logger.info("Initializing MDL retrieval service...")
        doc_store_provider = get_doc_store_provider()
        mdl_service = MDLRetrievalService(doc_store_provider=doc_store_provider)
        logger.info("✓ MDL service initialized")
        logger.info("")
        
        # Test table descriptions search
        logger.info("=" * 80)
        logger.info("Testing search_table_descriptions")
        logger.info("=" * 80)
        table_descriptions = await mdl_service.search_table_descriptions(
            query=query,
            limit=5
        )
        
        logger.info("")
        logger.info(f"Found {len(table_descriptions)} table description results")
        logger.info("")
        
        for i, result in enumerate(table_descriptions[:3], 1):
            logger.info(f"Result [{i}]:")
            logger.info(f"  table_name: {result.table_name}")
            logger.info(f"  description (first 200 chars): {result.description[:200] if result.description else 'EMPTY'}")
            logger.info(f"  score: {result.score}")
            logger.info(f"  id: {result.id}")
            logger.info(f"  metadata keys: {list(result.metadata.keys())}")
            logger.info(f"  metadata: {json.dumps(result.metadata, default=str, indent=2)}")
            logger.info("")
        
        # Test db schema search
        logger.info("=" * 80)
        logger.info("Testing search_db_schema")
        logger.info("=" * 80)
        db_schemas = await mdl_service.search_db_schema(
            query=query,
            limit=5
        )
        
        logger.info("")
        logger.info(f"Found {len(db_schemas)} schema results")
        logger.info("")
        
        for i, result in enumerate(db_schemas[:3], 1):
            logger.info(f"Result [{i}]:")
            logger.info(f"  table_name: {result.table_name}")
            logger.info(f"  schema_ddl (first 200 chars): {result.schema_ddl[:200] if result.schema_ddl else 'EMPTY'}")
            logger.info(f"  score: {result.score}")
            logger.info(f"  id: {result.id}")
            logger.info(f"  metadata keys: {list(result.metadata.keys())}")
            logger.info(f"  metadata: {json.dumps(result.metadata, default=str, indent=2)}")
            logger.info("")
        
        # Direct Qdrant inspection
        logger.info("=" * 80)
        logger.info("Direct Qdrant Store Inspection")
        logger.info("=" * 80)
        
        stores = doc_store_provider.stores if hasattr(doc_store_provider, 'stores') else {}
        table_desc_store = stores.get("leen_table_description")
        
        if table_desc_store:
            logger.info("Testing direct semantic_search on leen_table_description store...")
            raw_results = table_desc_store.semantic_search(
                query=query,
                k=3
            )
            
            logger.info(f"Raw Qdrant results: {len(raw_results)}")
            logger.info("")
            
            for i, result in enumerate(raw_results[:3], 1):
                logger.info(f"Raw Result [{i}]:")
                logger.info(f"  Keys: {list(result.keys())}")
                logger.info(f"  content type: {type(result.get('content'))}")
                logger.info(f"  content length: {len(str(result.get('content', '')))}")
                logger.info(f"  content: {str(result.get('content', ''))[:500]}")
                logger.info(f"  metadata type: {type(result.get('metadata'))}")
                logger.info(f"  metadata keys: {list(result.get('metadata', {}).keys())}")
                logger.info(f"  metadata: {json.dumps(result.get('metadata', {}), default=str, indent=2)}")
                logger.info(f"  score: {result.get('score')}")
                logger.info(f"  id: {result.get('id')}")
                logger.info("")
        else:
            logger.warning("leen_table_description store not found in doc_store_provider")
        
        logger.info("=" * 80)
        logger.info("Test Complete")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Error during test: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(test_mdl_retrieval())

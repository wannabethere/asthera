"""
Quick test to verify Qdrant connection and RetrievalHelper initialization

Usage:
    python -m tests.test_qdrant_connection
"""
import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_qdrant_connection():
    """Test Qdrant connection and RetrievalHelper"""
    logger.info("=" * 80)
    logger.info("Testing Qdrant Connection and RetrievalHelper")
    logger.info("=" * 80)
    
    try:
        # Step 1: Load settings
        logger.info("\n1. Loading settings...")
        from app.core.settings import get_settings, clear_settings_cache
        clear_settings_cache()
        settings = get_settings()
        
        logger.info(f"✓ VECTOR_STORE_TYPE: {settings.VECTOR_STORE_TYPE}")
        logger.info(f"✓ QDRANT_HOST: {settings.QDRANT_HOST}")
        logger.info(f"✓ QDRANT_PORT: {settings.QDRANT_PORT}")
        
        # Step 2: Get embeddings
        logger.info("\n2. Getting embeddings model...")
        from app.core.dependencies import get_embeddings_model
        embeddings = get_embeddings_model()
        logger.info(f"✓ Embeddings model: {type(embeddings).__name__}")
        
        # Step 3: Get vector store client
        logger.info("\n3. Creating vector store client...")
        from app.core.dependencies import get_vector_store_client
        vector_store_client = await get_vector_store_client(
            embeddings_model=embeddings,
            config=settings.get_vector_store_config()
        )
        logger.info(f"✓ Vector store client type: {type(vector_store_client).__name__}")
        logger.info(f"✓ Vector store initialized: {getattr(vector_store_client, '_initialized', False)}")
        
        # Step 4: Test client connection
        logger.info("\n4. Testing client connection...")
        if hasattr(vector_store_client, 'client'):
            qdrant_client = vector_store_client.client
            logger.info(f"✓ Qdrant client available: {qdrant_client is not None}")
            
            # Try to get collections
            try:
                if hasattr(qdrant_client, 'get_collections'):
                    collections = await qdrant_client.get_collections()
                    logger.info(f"✓ Collections available: {len(collections.collections) if hasattr(collections, 'collections') else 'unknown'}")
                    if hasattr(collections, 'collections'):
                        for coll in collections.collections[:5]:
                            logger.info(f"  - {coll.name}")
                else:
                    logger.warning("  Qdrant client doesn't have get_collections method")
            except Exception as e:
                logger.warning(f"  Could not list collections: {e}")
        else:
            logger.warning("  Vector store client doesn't have 'client' attribute")
        
        # Step 5: Create RetrievalHelper
        logger.info("\n5. Creating RetrievalHelper...")
        from app.agents.data.retrieval_helper import RetrievalHelper
        retrieval_helper = RetrievalHelper(vector_store_client=vector_store_client)
        logger.info(f"✓ RetrievalHelper created: {retrieval_helper is not None}")
        logger.info(f"✓ Has get_table_names_and_schema_contexts: {hasattr(retrieval_helper, 'get_table_names_and_schema_contexts')}")
        
        # Step 6: Test retrieval
        logger.info("\n6. Testing table retrieval...")
        if hasattr(retrieval_helper, 'get_table_names_and_schema_contexts'):
            try:
                result = await retrieval_helper.get_table_names_and_schema_contexts(
                    query="What are access request related tables?",
                    project_id="Snyk",
                    table_retrieval={
                        "table_retrieval_size": 5,
                        "table_column_retrieval_size": 50,
                        "allow_using_db_schemas_without_pruning": True
                    },
                    histories=None,
                    tables=None
                )
                
                schemas = result.get("schemas", []) if result else []
                logger.info(f"✓ Retrieved {len(schemas)} table schemas")
                for i, schema in enumerate(schemas[:3], 1):
                    table_name = schema.get("table_name", "Unknown")
                    logger.info(f"  {i}. {table_name}")
                
                if len(schemas) == 0:
                    logger.warning("⚠️  No tables retrieved - check if data is indexed in Qdrant")
            except Exception as e:
                logger.error(f"✗ Error during retrieval: {e}")
                import traceback
                logger.error(traceback.format_exc())
        else:
            logger.error("✗ RetrievalHelper doesn't have get_table_names_and_schema_contexts method")
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ Qdrant connection test completed!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(test_qdrant_connection())

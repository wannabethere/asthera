"""
Simple Qdrant connectivity test

Usage:
    python3 -m tests.test_qdrant_simple
"""
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_qdrant_connection():
    """Test basic Qdrant server connectivity"""
    
    logger.info("=" * 80)
    logger.info("Testing Qdrant Server Connectivity")
    logger.info("=" * 80)
    
    # Load settings
    from app.core.settings import get_settings, clear_settings_cache
    clear_settings_cache()
    settings = get_settings()
    
    logger.info(f"Qdrant Host: {settings.QDRANT_HOST}")
    logger.info(f"Qdrant Port: {settings.QDRANT_PORT}")
    logger.info("")
    
    # Test 1: Basic connection
    logger.info("Test 1: Creating Qdrant client...")
    try:
        from qdrant_client import QdrantClient
        
        client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            timeout=10
        )
        logger.info("✓ Qdrant client created")
        
        # Test 2: Get collections
        logger.info("\nTest 2: Fetching collections...")
        collections = client.get_collections()
        logger.info(f"✓ Connected! Found {len(collections.collections)} collections:")
        for coll in collections.collections:
            logger.info(f"  - {coll.name} (vectors: {coll.vectors_count if hasattr(coll, 'vectors_count') else 'unknown'})")
        
        # Test 3: Check specific collections
        logger.info("\nTest 3: Checking required collections...")
        required_collections = ['table_descriptions', 'table_definitions', 'db_schema']
        for coll_name in required_collections:
            try:
                info = client.get_collection(coll_name)
                logger.info(f"✓ {coll_name}: {info.points_count} points")
            except Exception as e:
                logger.warning(f"✗ {coll_name}: Not found or error - {e}")
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ Qdrant connectivity test PASSED")
        logger.info("=" * 80)
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Qdrant connectivity test FAILED: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        logger.info("\nTroubleshooting:")
        logger.info("1. Check if Qdrant server is running")
        logger.info("2. Verify network connectivity to 52.6.13.191:6333")
        logger.info("3. Check firewall rules")
        logger.info("4. Verify the server is not under heavy load")
        return False


if __name__ == "__main__":
    import sys
    success = test_qdrant_connection()
    sys.exit(0 if success else 1)

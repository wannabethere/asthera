"""
Test Qdrant metadata and payload fields

Usage:
    python3 -m tests.test_qdrant_metadata
"""
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_qdrant_metadata():
    """Test Qdrant collection metadata and payload"""
    
    logger.info("=" * 80)
    logger.info("Testing Qdrant Metadata and Payload Fields")
    logger.info("=" * 80)
    
    # Load settings
    from app.core.settings import get_settings, clear_settings_cache
    clear_settings_cache()
    settings = get_settings()
    
    from qdrant_client import QdrantClient
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    
    client = QdrantClient(
        host=settings.QDRANT_HOST,
        port=settings.QDRANT_PORT,
        timeout=10
    )
    
    collections = ['table_descriptions', 'db_schema', 'table_definitions']
    
    for collection_name in collections:
        logger.info(f"\n{'=' * 80}")
        logger.info(f"Collection: {collection_name}")
        logger.info('=' * 80)
        
        try:
            # Get collection info
            info = client.get_collection(collection_name)
            logger.info(f"✓ Points count: {info.points_count}")
            logger.info(f"✓ Vector size: {info.config.params.vectors.size if hasattr(info.config.params, 'vectors') else 'N/A'}")
            
            # Get a sample point to see its structure
            logger.info("\nFetching sample points...")
            sample_points = client.scroll(
                collection_name=collection_name,
                limit=3,
                with_payload=True,
                with_vectors=False
            )[0]
            
            if sample_points:
                logger.info(f"✓ Retrieved {len(sample_points)} sample points")
                
                # Show first point's payload
                first_point = sample_points[0]
                logger.info(f"\nSample point ID: {first_point.id}")
                logger.info("Payload keys:")
                for key in sorted(first_point.payload.keys()):
                    value = first_point.payload[key]
                    if isinstance(value, str) and len(value) > 100:
                        value = value[:100] + "..."
                    logger.info(f"  - {key}: {value}")
                
                # Test filtering by project_id
                logger.info("\nTest 1: Filter by project_id='Snyk'")
                try:
                    filtered_results = client.scroll(
                        collection_name=collection_name,
                        scroll_filter=Filter(
                            must=[
                                FieldCondition(
                                    key="project_id",
                                    match=MatchValue(value="Snyk")
                                )
                            ]
                        ),
                        limit=5,
                        with_payload=True,
                        with_vectors=False
                    )[0]
                    logger.info(f"✓ Filter by project_id='Snyk': {len(filtered_results)} results")
                    
                    if len(filtered_results) == 0:
                        logger.warning("⚠️  No results with project_id='Snyk'")
                        logger.info("Checking what project_id values exist...")
                        
                        # Get all points and check project_id values
                        all_sample_points = client.scroll(
                            collection_name=collection_name,
                            limit=10,
                            with_payload=True,
                            with_vectors=False
                        )[0]
                        
                        project_ids = set()
                        for point in all_sample_points:
                            if 'project_id' in point.payload:
                                project_ids.add(point.payload['project_id'])
                        
                        logger.info(f"Found project_id values: {project_ids}")
                    
                except Exception as e:
                    logger.error(f"✗ Filter failed: {e}")
                
                # Test filtering by type
                logger.info("\nTest 2: Filter by type='TABLE_DESCRIPTION'")
                try:
                    filtered_results = client.scroll(
                        collection_name=collection_name,
                        scroll_filter=Filter(
                            must=[
                                FieldCondition(
                                    key="type",
                                    match=MatchValue(value="TABLE_DESCRIPTION")
                                )
                            ]
                        ),
                        limit=5,
                        with_payload=True,
                        with_vectors=False
                    )[0]
                    logger.info(f"✓ Filter by type='TABLE_DESCRIPTION': {len(filtered_results)} results")
                    
                    if len(filtered_results) == 0:
                        logger.warning("⚠️  No results with type='TABLE_DESCRIPTION'")
                        logger.info("Checking what type values exist...")
                        
                        types = set()
                        for point in all_sample_points:
                            if 'type' in point.payload:
                                types.add(point.payload['type'])
                        
                        logger.info(f"Found type values: {types}")
                    
                except Exception as e:
                    logger.error(f"✗ Filter failed: {e}")
                
            else:
                logger.warning("⚠️  No points found in collection")
                
        except Exception as e:
            logger.error(f"✗ Error checking collection: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    logger.info("\n" + "=" * 80)
    logger.info("✅ Metadata test completed")
    logger.info("=" * 80)


if __name__ == "__main__":
    test_qdrant_metadata()

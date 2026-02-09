"""
Diagnostic Script: Debug Why Qdrant Collections Return 0 Results
Run this to verify your collections have data and the metadata structure is correct
"""

import logging
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION - UPDATE THESE
# =============================================================================

QDRANT_HOST = "52.6.13.191"
QDRANT_PORT = 6333
PROJECT_ID = "hr_compliance_risk"

# Collections to check
COLLECTIONS = [
    "core_table_descriptions",
    "core_column_descriptions",
    "core_sql_pairs",
    "core_instructions"
]


# =============================================================================
# DIAGNOSTIC FUNCTIONS
# =============================================================================

def check_collection_exists(client: QdrantClient, collection_name: str) -> bool:
    """Check if collection exists"""
    try:
        collections = client.get_collections()
        exists = collection_name in [c.name for c in collections.collections]
        
        if exists:
            logger.info(f"✓ Collection '{collection_name}' EXISTS")
        else:
            logger.error(f"✗ Collection '{collection_name}' DOES NOT EXIST")
        
        return exists
    except Exception as e:
        logger.error(f"✗ Error checking collection: {e}")
        return False


def check_collection_points(client: QdrantClient, collection_name: str) -> int:
    """Check number of points in collection"""
    try:
        info = client.get_collection(collection_name)
        count = info.points_count
        
        if count > 0:
            logger.info(f"✓ Collection '{collection_name}' has {count} points")
        else:
            logger.error(f"✗ Collection '{collection_name}' is EMPTY (0 points)")
        
        return count
    except Exception as e:
        logger.error(f"✗ Error getting collection info: {e}")
        return 0


def sample_collection_data(client: QdrantClient, collection_name: str, limit: int = 3):
    """Sample some points to see data structure"""
    try:
        logger.info(f"\nSampling {limit} points from '{collection_name}'...")
        
        result, _ = client.scroll(
            collection_name=collection_name,
            limit=limit,
            with_payload=True,
            with_vectors=False
        )
        
        if not result:
            logger.error(f"✗ No points returned from collection")
            return
        
        logger.info(f"✓ Retrieved {len(result)} sample points\n")
        
        for i, point in enumerate(result, 1):
            logger.info(f"Point {i}:")
            logger.info(f"  ID: {point.id}")
            logger.info(f"  Payload keys: {list(point.payload.keys())}")
            
            # Check metadata structure
            if "metadata" in point.payload:
                metadata = point.payload["metadata"]
                logger.info(f"  Metadata type: {type(metadata)}")
                
                if isinstance(metadata, dict):
                    logger.info(f"  Metadata keys: {list(metadata.keys())}")
                    
                    # Check for project_id
                    if "project_id" in metadata:
                        logger.info(f"  ✓ project_id: {metadata['project_id']}")
                    else:
                        logger.warning(f"  ✗ NO project_id in metadata!")
                    
                    # Check for type
                    if "type" in metadata:
                        logger.info(f"  ✓ type: {metadata['type']}")
                    else:
                        logger.warning(f"  ✗ NO type in metadata!")
                    
                    # Check for name
                    if "name" in metadata:
                        logger.info(f"  ✓ name: {metadata['name']}")
            else:
                # Check if metadata fields are at top level
                logger.warning(f"  ⚠ No 'metadata' key in payload")
                logger.info(f"  Top-level payload: {point.payload}")
                
                if "project_id" in point.payload:
                    logger.info(f"  ✓ project_id at top level: {point.payload['project_id']}")
            
            logger.info("")
    
    except Exception as e:
        logger.error(f"✗ Error sampling collection: {e}")


def test_filter_with_scroll(client: QdrantClient, collection_name: str, project_id: str):
    """Test filtering using scroll (no embeddings needed)"""
    try:
        logger.info(f"\nTesting filter on '{collection_name}' with project_id='{project_id}'...")
        
        # Test with metadata.project_id
        filter_obj = Filter(
            must=[FieldCondition(key="metadata.project_id", match=MatchValue(value=project_id))]
        )
        
        result, _ = client.scroll(
            collection_name=collection_name,
            scroll_filter=filter_obj,
            limit=10,
            with_payload=True,
            with_vectors=False
        )
        
        if result:
            logger.info(f"✓ Filter WORKS! Found {len(result)} points with project_id='{project_id}'")
            logger.info(f"  Sample point IDs: {[str(p.id)[:8] for p in result[:3]]}")
            
            # Show first result metadata
            if result[0].payload.get("metadata"):
                logger.info(f"  First result metadata: {result[0].payload['metadata']}")
        else:
            logger.error(f"✗ Filter returned 0 results")
            logger.info(f"  This means either:")
            logger.info(f"    1. No points have project_id='{project_id}'")
            logger.info(f"    2. Metadata structure is different (not nested under 'metadata')")
            
            # Try without metadata. prefix
            logger.info(f"\nTrying filter WITHOUT 'metadata.' prefix...")
            filter_obj2 = Filter(
                must=[FieldCondition(key="project_id", match=MatchValue(value=project_id))]
            )
            
            result2, _ = client.scroll(
                collection_name=collection_name,
                scroll_filter=filter_obj2,
                limit=10,
                with_payload=True
            )
            
            if result2:
                logger.info(f"✓ Filter WORKS with top-level 'project_id'! Found {len(result2)} points")
                logger.info(f"  ⚠ Your data uses TOP-LEVEL metadata, not nested under 'metadata' key")
                logger.info(f"  FIX: Change 'metadata.project_id' to just 'project_id' in your filter")
            else:
                logger.error(f"✗ Still 0 results. Checking what project_ids exist...")
                
                # Get all points and check project_ids
                all_points, _ = client.scroll(
                    collection_name=collection_name,
                    limit=100,
                    with_payload=True
                )
                
                project_ids = set()
                for p in all_points:
                    if "metadata" in p.payload and isinstance(p.payload["metadata"], dict):
                        pid = p.payload["metadata"].get("project_id")
                        if pid:
                            project_ids.add(pid)
                    elif "project_id" in p.payload:
                        project_ids.add(p.payload["project_id"])
                
                if project_ids:
                    logger.info(f"  Available project_ids: {project_ids}")
                    logger.error(f"  ✗ '{project_id}' NOT FOUND in collection")
                else:
                    logger.error(f"  ✗ No project_id found in any points!")
    
    except Exception as e:
        logger.error(f"✗ Error testing filter: {e}")


def check_metadata_structure(client: QdrantClient, collection_name: str):
    """Analyze metadata structure across multiple points"""
    try:
        logger.info(f"\nAnalyzing metadata structure in '{collection_name}'...")
        
        result, _ = client.scroll(
            collection_name=collection_name,
            limit=20,
            with_payload=True,
            with_vectors=False
        )
        
        if not result:
            logger.error(f"✗ Collection is empty")
            return
        
        # Check metadata structure
        nested_count = 0
        top_level_count = 0
        
        for point in result:
            if "metadata" in point.payload and isinstance(point.payload["metadata"], dict):
                nested_count += 1
            elif "project_id" in point.payload or "type" in point.payload:
                top_level_count += 1
        
        logger.info(f"\nMetadata Structure Analysis ({len(result)} points checked):")
        logger.info(f"  Nested under 'metadata': {nested_count} points")
        logger.info(f"  Top-level: {top_level_count} points")
        
        if nested_count > 0 and top_level_count > 0:
            logger.warning(f"  ⚠ MIXED STRUCTURE! Some points use nested, some use top-level")
        elif nested_count > 0:
            logger.info(f"  ✓ All points use NESTED structure (metadata.project_id)")
        elif top_level_count > 0:
            logger.info(f"  ✓ All points use TOP-LEVEL structure (project_id)")
        else:
            logger.error(f"  ✗ Unclear metadata structure")
    
    except Exception as e:
        logger.error(f"✗ Error analyzing metadata: {e}")


# =============================================================================
# MAIN DIAGNOSTIC
# =============================================================================

def run_diagnostics():
    """Run all diagnostics"""
    
    print("\n" + "=" * 80)
    print("QDRANT COLLECTIONS DIAGNOSTIC")
    print("=" * 80)
    print(f"\nHost: {QDRANT_HOST}:{QDRANT_PORT}")
    print(f"Project ID: {PROJECT_ID}")
    print(f"Collections to check: {COLLECTIONS}\n")
    
    # Connect to Qdrant
    try:
        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        logger.info("✓ Connected to Qdrant\n")
    except Exception as e:
        logger.error(f"✗ Failed to connect to Qdrant: {e}")
        return
    
    # Check each collection
    for collection_name in COLLECTIONS:
        print("\n" + "=" * 80)
        print(f"CHECKING: {collection_name}")
        print("=" * 80)
        
        # 1. Check exists
        if not check_collection_exists(client, collection_name):
            continue
        
        # 2. Check point count
        count = check_collection_points(client, collection_name)
        if count == 0:
            logger.error(f"✗ PROBLEM: Collection '{collection_name}' is empty!")
            logger.info(f"  SOLUTION: You need to index data into this collection first")
            continue
        
        # 3. Sample data
        sample_collection_data(client, collection_name, limit=3)
        
        # 4. Check metadata structure
        check_metadata_structure(client, collection_name)
        
        # 5. Test filtering
        test_filter_with_scroll(client, collection_name, PROJECT_ID)
    
    # Summary
    print("\n" + "=" * 80)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 80)
    
    print("\nCommon Issues and Solutions:")
    print("\n1. Collection is EMPTY (0 points)")
    print("   → You need to run your indexing process to populate the collection")
    print("   → Check your data pipeline is writing to the correct collection name")
    
    print("\n2. Wrong metadata structure")
    print("   → If using nested: filter should be 'metadata.project_id'")
    print("   → If using top-level: filter should be 'project_id'")
    print("   → Check your indexing code to see how metadata is stored")
    
    print("\n3. Wrong project_id value")
    print("   → The project_id in your data doesn't match the filter value")
    print("   → Check the 'Available project_ids' output above")
    
    print("\n4. Collection name mismatch")
    print("   → Your code is searching 'core_instructions' but data is in 'instructions'")
    print("   → Check collection naming in your indexing vs retrieval code")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    run_diagnostics()
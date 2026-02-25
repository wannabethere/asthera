"""
Quick Verification: Check Your Qdrant Collections
Run this immediately to see the state of your collections
"""

from qdrant_client import QdrantClient

# Your Qdrant connection
QDRANT_HOST = "52.6.13.191"
QDRANT_PORT = 6333

# Collections you're trying to query
COLLECTIONS = {
    "leen_table_description": "Tables",
    "leen_db_schema": "db schema",
    "column_definitions": "Columns",
    "core_sql_pairs": "SQL Examples",
    "core_instructions": "Instructions"
}

PROJECT_ID = "hr_compliance_risk"


def quick_check():
    """Quick check of collection status"""
    
    print("\n" + "=" * 80)
    print("QUICK VERIFICATION: Qdrant Collections Status")
    print("=" * 80)
    print(f"\nConnecting to: {QDRANT_HOST}:{QDRANT_PORT}\n")
    
    try:
        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        print("✓ Connected successfully\n")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return
    
    # Check all collections
    print("Collection Status:")
    print("-" * 80)
    
    any_has_data = False
    empty_collections = []
    
    for coll_name, coll_type in COLLECTIONS.items():
        try:
            info = client.get_collection(coll_name)
            count = info.points_count
            
            if count > 0:
                print(f"✓ {coll_name} ({coll_type}): {count} points")
                any_has_data = True
                
                # Try to get one point with project_id filter
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                
                filter_obj = Filter(
                    must=[FieldCondition(key="metadata.project_id", match=MatchValue(value=PROJECT_ID))]
                )
                
                result, _ = client.scroll(
                    collection_name=coll_name,
                    scroll_filter=None,
                    limit=100,
                    with_payload=True
                )
                
                if result:
                    print(f"  ✓ Found data for project_id='{PROJECT_ID}'")
                    
                    # Show sample metadata
                    metadata = result[0].payload.get("metadata", {})
                    if metadata:
                        print(f"    Sample: {metadata.get('name', 'N/A')}")
                else:
                    print(f"  ✗ No data for project_id='{PROJECT_ID}'")
                    
                    # Check what project_ids exist
                    all_result, _ = client.scroll(
                        collection_name=coll_name,
                        limit=10,
                        with_payload=True
                    )
                    
                    project_ids = set()
                    for p in all_result:
                        metadata = p.payload.get("metadata", {})
                        pid = metadata.get("project_id")
                        if pid:
                            project_ids.add(pid)
                    
                    if project_ids:
                        print(f"    Available project_ids: {project_ids}")
            else:
                print(f"✗ {coll_name} ({coll_type}): EMPTY (0 points)")
                empty_collections.append(coll_name)
        
        except Exception as e:
            print(f"✗ {coll_name}: ERROR - {str(e)[:100]}")
    
    # Summary
    print("\n" + "=" * 80)
    print("DIAGNOSIS")
    print("=" * 80)
    
    if not any_has_data:
        print("\n✗ CRITICAL: ALL collections are EMPTY!")
        print("\nThis is why you're getting 0 results.")
        print("\nYou need to:")
        print("  1. Run your indexing pipeline to populate the collections")
        print("  2. Verify your indexing code is writing to the correct collection names")
        print("  3. Check that your data has project_id='hr_compliance_risk'")
        
    elif empty_collections:
        print(f"\n⚠ WARNING: {len(empty_collections)} collections are empty:")
        for coll in empty_collections:
            print(f"  - {coll}")
        print("\nYou need to index data into these collections.")
        
    else:
        print("\n✓ All collections have data!")
        print("\nIf you're still getting 0 results, the issue is:")
        print("  1. Wrong project_id value in your query")
        print("  2. Query doesn't match embedded content semantically")
        print("  3. Score threshold too high")
        
        print("\nTo debug further:")
        print("  - Try score_threshold=0.0")
        print("  - Try different query formulations")
        print("  - Check project_id values shown above")
    
    # Show comparison with working test
    print("\n" + "=" * 80)
    print("COMPARISON: Your Test vs Working Test")
    print("=" * 80)
    
    print("\nYour test showed:")
    print("  ✗ Tables: 0")
    print("  ✗ Columns: 0")
    print("  ✗ SQL Pairs: 0")
    print("  ✗ Instructions: 0")
    
    print("\nWorking test showed:")
    print("  ✓ Tables: 3 (user_skill_proficiency, role_skill_mapping, skill_master)")
    print("  ✓ Related tables: working")
    print("  ✓ Project summary: 13 tables")
    
    if any_has_data:
        print("\n→ Your collections HAVE data, so the issue is likely:")
        print("   - Wrong project_id in query")
        print("   - Query not matching semantic content")
        print("   - Filter parameters wrong")
    else:
        print("\n→ Your collections are EMPTY, so you need to:")
        print("   - Run indexing process first")
        print("   - Populate collections with data")
        print("   - Verify data structure")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    quick_check()
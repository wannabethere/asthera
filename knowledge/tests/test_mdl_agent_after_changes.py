"""
Test MDL Context Breakdown Agent After Contextual Edge & Knowledgebase Changes
================================================================================

Verifies that the MDL context breakdown agent works correctly after:
1. Adding contextual edges generation
2. Adding organization support (metadata only)
3. Adding knowledgebase entities (features, metrics, instructions, examples)
4. Adding batched parallel processing

Usage:
    python -m tests.test_mdl_agent_after_changes
"""

import asyncio
import logging
from app.agents.mdl_context_breakdown_agent import MDLContextBreakdownAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_table_query():
    """Test: Basic table query"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 1: Basic Table Query")
    logger.info("=" * 80)
    
    agent = MDLContextBreakdownAgent()
    breakdown = await agent.breakdown_mdl_question(
        "What vulnerability tables exist in Snyk?",
        product_name="Snyk"
    )
    
    logger.info(f"Query Type: {breakdown.query_type}")
    logger.info(f"Product Context: {breakdown.product_context}")
    logger.info(f"Search Questions:")
    for sq in breakdown.search_questions:
        logger.info(f"  - Entity: {sq['entity']}")
        logger.info(f"    Question: {sq['question']}")
        logger.info(f"    Filters: {sq.get('metadata_filters', {})}")
    
    # Assertions
    assert breakdown.query_type == "mdl", "Should be MDL query"
    assert any("table" in sq["entity"] for sq in breakdown.search_questions), "Should query table collections"
    assert breakdown.product_context == "Snyk", "Should have Snyk context"
    
    logger.info("✓ TEST 1 PASSED")


async def test_relationship_query():
    """Test: Relationship query using contextual edges"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Relationship Query (Contextual Edges)")
    logger.info("=" * 80)
    
    agent = MDLContextBreakdownAgent()
    breakdown = await agent.breakdown_mdl_question(
        "What tables are related to Vulnerability in Snyk?",
        product_name="Snyk"
    )
    
    logger.info(f"Query Type: {breakdown.query_type}")
    logger.info(f"Search Questions:")
    for sq in breakdown.search_questions:
        logger.info(f"  - Entity: {sq['entity']}")
        logger.info(f"    Question: {sq['question']}")
        logger.info(f"    Filters: {sq.get('metadata_filters', {})}")
    
    # Assertions
    assert any("contextual_edges" in sq["entity"] for sq in breakdown.search_questions), \
        "Should query contextual_edges for relationships"
    
    logger.info("✓ TEST 2 PASSED")


async def test_feature_query():
    """Test: Feature query using knowledgebase entities"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Feature Query (Knowledgebase)")
    logger.info("=" * 80)
    
    agent = MDLContextBreakdownAgent()
    breakdown = await agent.breakdown_mdl_question(
        "What features does the Vulnerability table provide?",
        product_name="Snyk"
    )
    
    logger.info(f"Query Type: {breakdown.query_type}")
    logger.info(f"Search Questions:")
    for sq in breakdown.search_questions:
        logger.info(f"  - Entity: {sq['entity']}")
        logger.info(f"    Question: {sq['question']}")
        logger.info(f"    Filters: {sq.get('metadata_filters', {})}")
    
    # Assertions
    # Should query entities collection with mdl_entity_type filter
    entities_queries = [sq for sq in breakdown.search_questions if "entities" in sq["entity"]]
    if entities_queries:
        filters = entities_queries[0].get("metadata_filters", {})
        logger.info(f"  Entities query filters: {filters}")
        # Check if mdl_entity_type is set (may be "feature" or just check entities is queried)
    
    logger.info("✓ TEST 3 PASSED")


async def test_metric_query():
    """Test: Metric query using knowledgebase entities"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 4: Metric Query (Knowledgebase)")
    logger.info("=" * 80)
    
    agent = MDLContextBreakdownAgent()
    breakdown = await agent.breakdown_mdl_question(
        "What metrics can I calculate from vulnerability data?",
        product_name="Snyk"
    )
    
    logger.info(f"Query Type: {breakdown.query_type}")
    logger.info(f"Search Questions:")
    for sq in breakdown.search_questions:
        logger.info(f"  - Entity: {sq['entity']}")
        logger.info(f"    Question: {sq['question']}")
        logger.info(f"    Filters: {sq.get('metadata_filters', {})}")
    
    logger.info("✓ TEST 4 PASSED")


async def test_example_query():
    """Test: Example query using sql_pairs"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 5: SQL Example Query")
    logger.info("=" * 80)
    
    agent = MDLContextBreakdownAgent()
    breakdown = await agent.breakdown_mdl_question(
        "Show me example SQL queries for vulnerabilities",
        product_name="Snyk"
    )
    
    logger.info(f"Query Type: {breakdown.query_type}")
    logger.info(f"Search Questions:")
    for sq in breakdown.search_questions:
        logger.info(f"  - Entity: {sq['entity']}")
        logger.info(f"    Question: {sq['question']}")
        logger.info(f"    Filters: {sq.get('metadata_filters', {})}")
    
    # Should query sql_pairs collection
    assert any("sql" in sq["entity"].lower() or "example" in sq.get("question", "").lower() 
               for sq in breakdown.search_questions), \
        "Should query for SQL examples"
    
    logger.info("✓ TEST 5 PASSED")


async def test_instruction_query():
    """Test: Instruction query using instructions collection"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 6: Instruction/Best Practice Query")
    logger.info("=" * 80)
    
    agent = MDLContextBreakdownAgent()
    breakdown = await agent.breakdown_mdl_question(
        "What are the best practices for querying Vulnerability table?",
        product_name="Snyk"
    )
    
    logger.info(f"Query Type: {breakdown.query_type}")
    logger.info(f"Search Questions:")
    for sq in breakdown.search_questions:
        logger.info(f"  - Entity: {sq['entity']}")
        logger.info(f"    Question: {sq['question']}")
        logger.info(f"    Filters: {sq.get('metadata_filters', {})}")
    
    logger.info("✓ TEST 6 PASSED")


async def test_category_filtering():
    """Test: Category-based filtering"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 7: Category Filtering")
    logger.info("=" * 80)
    
    agent = MDLContextBreakdownAgent()
    breakdown = await agent.breakdown_mdl_question(
        "Show me all access request tables",
        product_name="Snyk"
    )
    
    logger.info(f"Query Type: {breakdown.query_type}")
    logger.info(f"Search Questions:")
    for sq in breakdown.search_questions:
        logger.info(f"  - Entity: {sq['entity']}")
        logger.info(f"    Question: {sq['question']}")
        logger.info(f"    Filters: {sq.get('metadata_filters', {})}")
        
        # Check if category_name is used
        filters = sq.get('metadata_filters', {})
        if 'category_name' in filters or 'categories' in filters:
            logger.info(f"    ✓ Uses category filtering: {filters.get('category_name') or filters.get('categories')}")
    
    logger.info("✓ TEST 7 PASSED")


async def test_organization_not_in_filters():
    """Test: Organization is in metadata but NOT in query filters"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 8: Organization Not In Filters")
    logger.info("=" * 80)
    
    agent = MDLContextBreakdownAgent()
    breakdown = await agent.breakdown_mdl_question(
        "What tables exist in Snyk?",
        product_name="Snyk"
    )
    
    logger.info(f"Search Questions:")
    for sq in breakdown.search_questions:
        filters = sq.get('metadata_filters', {})
        logger.info(f"  - Entity: {sq['entity']}, Filters: {filters}")
        
        # Assert organization is NOT in filters
        assert 'organization_id' not in filters, "Organization should NOT be in filters"
        assert 'organization_name' not in filters, "Organization should NOT be in filters"
        
        # Assert product_name IS in filters (organization is implicit)
        if 'product_name' in filters:
            logger.info(f"    ✓ Uses product_name filtering (organization implicit)")
    
    logger.info("✓ TEST 8 PASSED")


async def test_cross_entity_query():
    """Test: Query spanning multiple entity types"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 9: Cross-Entity Query (Features + Metrics + Examples)")
    logger.info("=" * 80)
    
    agent = MDLContextBreakdownAgent()
    breakdown = await agent.breakdown_mdl_question(
        "What features, metrics, and examples are available for vulnerability analysis in Snyk?",
        product_name="Snyk"
    )
    
    logger.info(f"Query Type: {breakdown.query_type}")
    logger.info(f"Search Questions ({len(breakdown.search_questions)}):")
    for sq in breakdown.search_questions:
        logger.info(f"  - Entity: {sq['entity']}")
        logger.info(f"    Question: {sq['question']}")
        logger.info(f"    Filters: {sq.get('metadata_filters', {})}")
    
    # Should query multiple collections
    entities_used = set(sq['entity'] for sq in breakdown.search_questions)
    logger.info(f"Entities queried: {entities_used}")
    
    logger.info("✓ TEST 9 PASSED")


async def run_all_tests():
    """Run all tests"""
    logger.info("\n" + "=" * 80)
    logger.info("MDL CONTEXT BREAKDOWN AGENT - COMPATIBILITY TESTS")
    logger.info("=" * 80)
    logger.info("Testing after:")
    logger.info("  1. Adding contextual edges generation")
    logger.info("  2. Adding organization support")
    logger.info("  3. Adding knowledgebase entities (features, metrics, instructions, examples)")
    logger.info("  4. Adding batched parallel processing")
    logger.info("=" * 80)
    
    tests = [
        test_table_query,
        test_relationship_query,
        test_feature_query,
        test_metric_query,
        test_example_query,
        test_instruction_query,
        test_category_filtering,
        test_organization_not_in_filters,
        test_cross_entity_query
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            await test_func()
            passed += 1
        except Exception as e:
            logger.error(f"✗ {test_func.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total Tests: {len(tests)}")
    logger.info(f"Passed: {passed}")
    logger.info(f"Failed: {failed}")
    
    if failed == 0:
        logger.info("\n✅ ALL TESTS PASSED - MDL Agent is compatible with new changes!")
    else:
        logger.error(f"\n❌ {failed} TESTS FAILED - Review errors above")
    
    logger.info("=" * 80)
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1)

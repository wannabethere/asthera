#!/usr/bin/env python3
"""
Test script to demonstrate the new metadata cache functionality in SQLRAGAgent
"""

import asyncio
import json
from unittest.mock import Mock, AsyncMock
from genieml.agents.app.agents.nodes.sql.sql_rag_agent import SQLRAGAgent
from genieml.agents.app.core.engine import Engine


async def test_metadata_cache():
    """Test the metadata cache functionality"""
    
    # Mock dependencies
    mock_llm = Mock()
    mock_engine = Mock(spec=Engine)
    mock_retrieval_helper = Mock()
    
    # Mock the metadata retrieval methods
    mock_retrieval_helper.get_sql_pairs = AsyncMock(return_value={
        "sql_pairs": [
            {"question": "Show me sales data", "sql": "SELECT * FROM sales"},
            {"question": "Revenue by month", "sql": "SELECT month, SUM(revenue) FROM sales GROUP BY month"}
        ]
    })
    
    mock_retrieval_helper.get_instructions = AsyncMock(return_value={
        "documents": [
            "Use proper date formatting for time series analysis",
            "Always include appropriate WHERE clauses for filtering"
        ]
    })
    
    mock_retrieval_helper.get_metrics = AsyncMock(return_value={
        "metrics": [
            {"name": "Total Revenue", "description": "Sum of all revenue"},
            {"name": "Average Order Value", "description": "Mean of order amounts"}
        ]
    })
    
    mock_retrieval_helper.get_views = AsyncMock(return_value={
        "views": [
            {"name": "monthly_sales", "description": "Aggregated sales by month"},
            {"name": "customer_summary", "description": "Customer performance metrics"}
        ]
    })
    
    # Create agent instance
    agent = SQLRAGAgent(
        llm=mock_llm,
        engine=mock_engine,
        retrieval_helper=mock_retrieval_helper
    )
    
    print("=== Testing Metadata Cache Functionality ===\n")
    
    # Test 1: First call - should retrieve metadata
    print("Test 1: First metadata retrieval")
    query1 = "Show me sales data for Q1"
    project_id = "test_project"
    
    metadata1 = await agent._retrieve_and_cache_metadata(
        query=query1,
        project_id=project_id
    )
    
    print(f"Retrieved metadata: {json.dumps(metadata1, indent=2, default=str)}")
    print(f"Cache size: {len(agent._metadata_cache)}")
    
    # Test 2: Second call with same query - should use cache
    print("\nTest 2: Second call with same query (should use cache)")
    metadata2 = await agent._retrieve_and_cache_metadata(
        query=query1,
        project_id=project_id
    )
    
    print(f"Cached metadata: {json.dumps(metadata2, indent=2, default=str)}")
    print(f"Cache size: {len(agent._metadata_cache)}")
    
    # Test 3: Different query - should retrieve new metadata
    print("\nTest 3: Different query (should retrieve new metadata)")
    query2 = "What are the top customers by revenue?"
    
    metadata3 = await agent._retrieve_and_cache_metadata(
        query=query2,
        project_id=project_id
    )
    
    print(f"New metadata: {json.dumps(metadata3, indent=2, default=str)}")
    print(f"Cache size: {len(agent._metadata_cache)}")
    
    # Test 4: Cache statistics
    print("\nTest 4: Cache statistics")
    cache_stats = agent.get_cache_stats()
    print(f"Cache stats: {json.dumps(cache_stats, indent=2, default=str)}")
    
    # Test 5: Manual cache addition
    print("\nTest 5: Manual cache addition")
    custom_metadata = {
        "sql_pairs": [{"question": "Custom question", "sql": "SELECT 1"}],
        "instructions": ["Custom instruction"],
        "metrics": [{"name": "Custom Metric", "description": "Custom description"}],
        "views": [{"name": "custom_view", "description": "Custom view"}]
    }
    
    agent.add_metadata_to_cache(
        query="Custom query",
        project_id="custom_project",
        metadata=custom_metadata
    )
    
    print(f"Cache size after manual addition: {len(agent._metadata_cache)}")
    
    # Test 6: Get cached metadata
    print("\nTest 6: Get cached metadata")
    cached_metadata = agent.get_cached_metadata("Custom query", "custom_project")
    print(f"Cached custom metadata: {json.dumps(cached_metadata, indent=2, default=str)}")
    
    # Test 7: Clear cache
    print("\nTest 7: Clear cache")
    agent.clear_metadata_cache()
    print(f"Cache size after clearing: {len(agent._metadata_cache)}")
    
    print("\n=== All tests completed ===")


if __name__ == "__main__":
    asyncio.run(test_metadata_cache()) 
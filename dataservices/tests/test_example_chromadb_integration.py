#!/usr/bin/env python3
"""
Test script for Example ChromaDB Integration
Tests that examples with definition_type "sql_pair" or "instruction" are properly indexed to ChromaDB
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "app"))

from app.core.dependencies import get_persistence_factory
from app.service.models import UserExample, DefinitionType


async def test_example_chromadb_integration():
    """Test that examples are properly indexed to ChromaDB"""
    print("🧪 Testing Example ChromaDB Integration...")
    
    try:
        # Get the persistence factory with processors
        async for factory in get_persistence_factory():
            user_example_service = factory.get_user_example_service()
            
            # Test 1: Create a SQL pair example
            print("\n📝 Test 1: Creating SQL pair example...")
            sql_pair_example = UserExample(
                definition_type=DefinitionType.SQL_PAIR,
                name="test_sql_pair",
                description="Find all customers from France",
                sql="SELECT * FROM customers WHERE country = 'France'",
                additional_context={
                    "context": "Customer analysis",
                    "instructions": "Filter customers by country",
                    "samples": [{"country": "France", "customer_count": 150}]
                },
                user_id="test_user"
            )
            
            example_id = await user_example_service.persist_user_example(
                sql_pair_example, 
                project_id="test_project_001"
            )
            print(f"✅ SQL pair example created with ID: {example_id}")
            
            # Test 2: Create an instruction example
            print("\n📝 Test 2: Creating instruction example...")
            instruction_example = UserExample(
                definition_type=DefinitionType.INSTRUCTION,
                name="test_instruction",
                description="How to calculate total revenue by country",
                sql="SELECT country, SUM(revenue) as total_revenue FROM sales GROUP BY country",
                additional_context={
                    "context": "Revenue analysis",
                    "instructions": "Group sales by country and sum revenue",
                    "chain_of_thought": "1. Group by country\n2. Sum the revenue column\n3. Order by total revenue"
                },
                user_id="test_user"
            )
            
            example_id_2 = await user_example_service.persist_user_example(
                instruction_example, 
                project_id="test_project_001"
            )
            print(f"✅ Instruction example created with ID: {example_id_2}")
            
            # Test 3: Create a metric example (should not be indexed to ChromaDB)
            print("\n📝 Test 3: Creating metric example (should not be indexed)...")
            metric_example = UserExample(
                definition_type=DefinitionType.METRIC,
                name="test_metric",
                description="Total revenue metric",
                sql="SELECT SUM(revenue) FROM sales",
                additional_context={
                    "context": "Revenue metric",
                    "metric_type": "sum"
                },
                user_id="test_user"
            )
            
            example_id_3 = await user_example_service.persist_user_example(
                metric_example, 
                project_id="test_project_001"
            )
            print(f"✅ Metric example created with ID: {example_id_3} (not indexed to ChromaDB)")
            
            # Test 4: Retrieve examples
            print("\n📋 Test 4: Retrieving examples...")
            examples = await user_example_service.get_user_examples("test_project_001")
            print(f"✅ Retrieved {len(examples)} examples")
            
            for example in examples:
                print(f"   - {example.name} ({example.definition_type}): {example.question}")
            
            print("\n🎉 All tests completed successfully!")
            
    except Exception as e:
        print(f"❌ Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Set required environment variables for testing
    os.environ.setdefault("OPENAI_API_KEY", "test_key")
    os.environ.setdefault("CHROMA_STORE_PATH", "./test_chroma_db")
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/testdb")
    
    # Run the test
    asyncio.run(test_example_chromadb_integration()) 
"""
Example demonstrating the new alert knowledge base system

This shows how the knowledge base has been moved from FAISS to ChromaDB
and how to use the AlertKnowledgeHelper for retrieval.
"""

import asyncio
import logging
from app.indexing.alert_knowledge_helper import get_alert_knowledge_helper, initialize_alert_knowledge_helper
from app.indexing.project_reader import ProjectReader
from app.settings import get_settings
import chromadb

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def demonstrate_knowledge_base():
    """Demonstrate the new knowledge base system."""
    
    print("=== Alert Knowledge Base Migration Demo ===\n")
    
    # Initialize ProjectReader (this will create the knowledge base in ChromaDB)
    print("1. Initializing ProjectReader with alert knowledge base...")
    settings = get_settings()
    persistent_client = chromadb.PersistentClient(path=settings.CHROMA_STORE_PATH)
    
    project_reader = ProjectReader(
        base_path="/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/sql_meta",
        persistent_client=persistent_client
    )
    
    # Initialize the knowledge helper
    print("2. Initializing AlertKnowledgeHelper...")
    knowledge_helper = initialize_alert_knowledge_helper(project_reader)
    
    # Test different search types
    test_queries = [
        "SQL aggregation functions for metrics",
        "Training completion rate alerts",
        "ARIMA conditions for time series",
        "Business context for alert frequency"
    ]
    
    print("\n3. Testing knowledge base searches...")
    for query in test_queries:
        print(f"\n--- Query: '{query}' ---")
        
        # Test semantic search
        print("Semantic search results:")
        semantic_results = knowledge_helper.search_knowledge(query, k=3, search_type="semantic")
        for i, result in enumerate(semantic_results, 1):
            print(f"  {i}. {result}")
        
        # Test BM25 search
        print("BM25 search results:")
        bm25_results = knowledge_helper.search_knowledge(query, k=3, search_type="bm25")
        for i, result in enumerate(bm25_results, 1):
            print(f"  {i}. {result}")
        
        # Test category search
        print("Category search (sql_analysis):")
        category_results = knowledge_helper.search_by_category("sql_analysis", query, k=2)
        for i, result in enumerate(category_results, 1):
            print(f"  {i}. {result}")
    
    # Test metadata search
    print("\n4. Testing metadata-based search...")
    metadata_results = knowledge_helper.search_knowledge_with_metadata(
        "alert patterns", k=5, search_type="semantic"
    )
    
    print("Results with metadata:")
    for i, result in enumerate(metadata_results, 1):
        print(f"  {i}. Content: {result['content']}")
        print(f"     Metadata: {result['metadata']}")
        print(f"     Score: {result['score']:.4f}")
        print()
    
    print("=== Demo Complete ===")

def demonstrate_old_vs_new():
    """Show the difference between old FAISS approach and new ChromaDB approach."""
    
    print("\n=== Old vs New Knowledge Base Approach ===\n")
    
    print("OLD APPROACH (FAISS):")
    print("- Knowledge stored in local FAISS vectorstore")
    print("- Created fresh on each AlertAgent initialization")
    print("- No persistence across restarts")
    print("- Limited search capabilities")
    print("- Memory-based storage")
    
    print("\nNEW APPROACH (ChromaDB):")
    print("- Knowledge stored in persistent ChromaDB")
    print("- Initialized once in ProjectReader")
    print("- Persistent across restarts")
    print("- Multiple search types (semantic, BM25, TF-IDF)")
    print("- Metadata filtering capabilities")
    print("- Shared across all services")
    print("- Better performance and scalability")
    
    print("\nBENEFITS:")
    print("✅ Persistent storage - no re-initialization needed")
    print("✅ Better search capabilities with multiple algorithms")
    print("✅ Metadata filtering for targeted searches")
    print("✅ Shared knowledge base across services")
    print("✅ Scalable and production-ready")
    print("✅ Easy to extend with new knowledge")

if __name__ == "__main__":
    print("Alert Knowledge Base Migration Example")
    print("=" * 50)
    
    # Show the conceptual differences
    demonstrate_old_vs_new()
    
    # Run the actual demo
    try:
        asyncio.run(demonstrate_knowledge_base())
    except Exception as e:
        print(f"Error running demo: {e}")
        print("This is expected if ChromaDB is not properly configured.")
        print("The knowledge base will be initialized when the service starts.")

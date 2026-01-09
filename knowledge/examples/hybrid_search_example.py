"""
Example usage of Hybrid Search Service for Metadata Generation Agents

This example demonstrates how to use the hybrid search service to:
1. Find relevant contexts for metadata generation
2. Perform context-aware retrieval
3. Search for similar patterns and metadata entries
"""
"""
Example usage of Hybrid Search Service for Metadata Generation Agents

This example demonstrates how to use the hybrid search service to:
1. Find relevant contexts for metadata generation
2. Perform context-aware retrieval
3. Search for similar patterns and metadata entries
"""
import logging
import asyncio
import os
import chromadb
from langchain_openai import OpenAIEmbeddings

from app.services.hybrid_search_service import HybridSearchService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_hybrid_search():
    """Example of using hybrid search for metadata generation"""
    
    # Get OpenAI API key from environment
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.error("OPENAI_API_KEY environment variable not set")
        return
    
    # Initialize ChromaDB client
    chroma_client = chromadb.PersistentClient(path="./chroma_metadata_store")
    
    # Initialize embeddings model
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=openai_api_key
    )
    
    # Initialize hybrid search service
    search_service = HybridSearchService(
        chroma_client=chroma_client,
        collection_name="metadata_contexts",
        embeddings_model=embeddings,
        dense_weight=0.7,  # 70% weight for semantic similarity
        sparse_weight=0.3   # 30% weight for keyword matching
    )
    
    # Example 1: Add context documents
    logger.info("=== Example 1: Adding Context Documents ===")
    
    contexts = [
        {
            "document": """
            Large healthcare organization with developing compliance maturity.
            Operates in United States with 1000-5000 employees. Manages electronic 
            Protected Health Information (ePHI) across Epic EHR, Workday HCM, and 
            PACS systems. Subject to HIPAA and state breach notification laws.
            Has medium automation capability with established IAM (Okta) and 
            SIEM (Splunk) platforms. Currently preparing for upcoming HIPAA 
            compliance audit scheduled within 90 days.
            """,
            "metadata": {
                "context_id": "ctx_001",
                "context_type": "organizational_situational",
                "industry": "healthcare",
                "organization_size": "large",
                "employee_count_range": "1000-5000",
                "maturity_level": "developing",
                "regulatory_frameworks": ["HIPAA", "state_breach_laws"],
                "data_types": ["ePHI", "PHI", "PII"],
                "systems": ["Epic_EHR", "Workday", "PACS", "Okta", "Splunk"],
                "automation_capability": "medium",
                "current_situation": "pre_audit",
                "audit_timeline_days": 90
            }
        },
        {
            "document": """
            Small technology startup in rapid growth phase. Located in California
            with 50-200 employees. Primarily handles customer data (PII) and 
            payment information (PCI). Subject to SOC 2 Type II requirements 
            for B2B SaaS customers. Limited compliance maturity with basic 
            security controls in place. High automation capability using modern
            cloud infrastructure (AWS, Okta, Datadog). Planning SOC 2 audit
            for first time in 6 months.
            """,
            "metadata": {
                "context_id": "ctx_002",
                "context_type": "organizational_situational",
                "industry": "technology",
                "organization_size": "small",
                "employee_count_range": "50-200",
                "maturity_level": "nascent",
                "regulatory_frameworks": ["SOC2", "PCI_DSS_lite"],
                "data_types": ["PII", "payment_data"],
                "systems": ["AWS", "Okta", "Datadog", "Stripe"],
                "automation_capability": "high",
                "current_situation": "first_audit_prep",
                "audit_timeline_days": 180
            }
        }
    ]
    
    documents = [ctx["document"] for ctx in contexts]
    metadatas = [ctx["metadata"] for ctx in contexts]
    ids = [ctx["metadata"]["context_id"] for ctx in contexts]
    
    added_ids = search_service.add_documents(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )
    logger.info(f"Added {len(added_ids)} context documents")
    
    # Example 2: Find relevant contexts using hybrid search
    logger.info("\n=== Example 2: Finding Relevant Contexts ===")
    
    user_description = """
    We're a healthcare provider with about 2000 employees. We use Epic for 
    our EHR and Workday for HR. We have a HIPAA audit coming up in about 
    3 months and need to make sure our access controls are solid. We've got 
    Okta set up but haven't really configured access reviews properly yet.
    """
    
    relevant_contexts = search_service.find_relevant_contexts(
        context_description=user_description,
        top_k=3
    )
    
    logger.info(f"Found {len(relevant_contexts)} relevant contexts:")
    for i, ctx in enumerate(relevant_contexts, 1):
        logger.info(f"\nContext {i}: {ctx['id']}")
        logger.info(f"  Combined Score: {ctx['combined_score']:.3f}")
        logger.info(f"  - Dense (semantic): {ctx['dense_score']:.3f}")
        logger.info(f"  - BM25 (keyword): {ctx['bm25_score']:.3f}")
        logger.info(f"  Industry: {ctx['metadata'].get('industry', 'N/A')}")
        logger.info(f"  Size: {ctx['metadata'].get('organization_size', 'N/A')}")
        logger.info(f"  Situation: {ctx['metadata'].get('current_situation', 'N/A')}")
    
    # Example 3: Context-aware retrieval with filters
    logger.info("\n=== Example 3: Context-Aware Retrieval ===")
    
    query = "What are the most important access control requirements for HIPAA compliance?"
    
    results = search_service.context_aware_retrieval(
        query=query,
        context_id="ctx_001",  # Filter by specific context
        filters={
            "regulatory_frameworks": {"$contains": "HIPAA"}
        },
        top_k=5
    )
    
    logger.info(f"Found {len(results)} context-aware results:")
    for i, result in enumerate(results, 1):
        logger.info(f"\nResult {i}:")
        logger.info(f"  Combined Score: {result['combined_score']:.3f}")
        logger.info(f"  Content preview: {result['content'][:100]}...")
        logger.info(f"  Metadata: {result['metadata']}")
    
    # Example 4: Hybrid search with metadata filtering
    logger.info("\n=== Example 4: Hybrid Search with Metadata Filters ===")
    
    search_query = "Show me controls for organizations preparing for audit"
    
    filtered_results = search_service.hybrid_search(
        query=search_query,
        top_k=5,
        where={
            "current_situation": "pre_audit",
            "maturity_level": {"$in": ["developing", "nascent"]}
        }
    )
    
    logger.info(f"Found {len(filtered_results)} filtered results:")
    for i, result in enumerate(filtered_results, 1):
        logger.info(f"\nResult {i}: {result['id']}")
        logger.info(f"  Combined Score: {result['combined_score']:.3f}")
        logger.info(f"  Context: {result['metadata'].get('context_id', 'N/A')}")


async def example_metadata_generation_integration():
    """
    Example showing how metadata generation agents can use hybrid search
    """
    logger.info("\n=== Metadata Generation Agent Integration Example ===")
    
    # Get OpenAI API key from environment
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.error("OPENAI_API_KEY environment variable not set")
        return
    
    chroma_client = chromadb.PersistentClient(path="./chroma_metadata_store")
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=openai_api_key
    )
    
    # Initialize search service for metadata patterns
    pattern_search = HybridSearchService(
        chroma_client=chroma_client,
        collection_name="metadata_patterns",
        embeddings_model=embeddings
    )
    
    # Example: Search for similar risk patterns
    risk_query = "access control violations in healthcare organizations"
    
    similar_patterns = pattern_search.hybrid_search(
        query=risk_query,
        top_k=5,
        where={"domain": "healthcare"}
    )
    
    logger.info(f"Found {len(similar_patterns)} similar risk patterns:")
    for pattern in similar_patterns:
        logger.info(f"  - Pattern: {pattern['id']}")
        logger.info(f"    Score: {pattern['combined_score']:.3f}")
        logger.info(f"    Content: {pattern['content'][:150]}...")


if __name__ == "__main__":
    # Run examples
    asyncio.run(example_hybrid_search())
    asyncio.run(example_metadata_generation_integration())


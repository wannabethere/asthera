"""
Workforce Assistants Usage Examples
Demonstrates how to use Product, Compliance, and Domain Knowledge assistants.

Run examples:
    python -m examples.workforce_assistants_usage
"""
import asyncio
import logging
from typing import Dict, Any, List

from app.assistants.workforce_assistants import (
    create_product_assistant,
    create_compliance_assistant,
    create_domain_knowledge_assistant,
    WorkforceAssistant
)
from app.assistants.workforce_config import (
    AssistantType,
    AssistantConfig,
    DataSourceConfig,
    get_assistant_config
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# EXAMPLE 1: PRODUCT ASSISTANT - BASIC USAGE
# ============================================================================

async def example_product_basic():
    """Basic product assistant usage"""
    print("\n" + "="*80)
    print("EXAMPLE 1: Product Assistant - Basic Usage")
    print("="*80 + "\n")
    
    # Create product assistant
    assistant = create_product_assistant()
    
    # Process query
    result = await assistant.process_query(
        user_question="How do I configure Snyk to scan for high-severity vulnerabilities?",
        available_products=["Snyk"],
        available_actions=["Configure", "Scan", "Monitor", "Filter"],
        output_format="summary"
    )
    
    print(f"Query Type: {result['breakdown'].query_type}")
    print(f"User Intent: {result['breakdown'].user_intent}")
    print(f"Products Detected: {result['breakdown'].metadata.get('products', [])}")
    print(f"Retrieved Docs: {len(result['retrieved_docs'])}")
    print(f"\nResponse:\n{result['response']}")


# ============================================================================
# EXAMPLE 2: PRODUCT ASSISTANT - WITH CUSTOM CONFIG
# ============================================================================

async def example_product_custom_config():
    """Product assistant with custom configuration"""
    print("\n" + "="*80)
    print("EXAMPLE 2: Product Assistant - Custom Configuration")
    print("="*80 + "\n")
    
    # Create custom config
    custom_config = AssistantConfig(
        assistant_type=AssistantType.PRODUCT,
        model_name="gpt-4o-mini",
        temperature=0.1,  # Lower temperature for more deterministic responses
        system_prompt_template=get_assistant_config(AssistantType.PRODUCT).system_prompt_template,
        human_prompt_template=get_assistant_config(AssistantType.PRODUCT).human_prompt_template,
        data_sources=[
            DataSourceConfig(
                source_name="chroma_product_docs",
                enabled=True,
                categories=["api_docs"],  # Focus on API docs only
                priority=10
            )
        ],
        web_search_enabled=False,  # Disable web search
        max_edges=5  # Limit to top 5 edges
    )
    
    # Create assistant with custom config
    assistant = create_product_assistant(config=custom_config)
    
    # Process query
    result = await assistant.process_query(
        user_question="What API endpoints does Snyk provide for vulnerability scanning?",
        available_products=["Snyk"],
        output_format="json"
    )
    
    print(f"Query Type: {result['breakdown'].query_type}")
    print(f"Web Search Enabled: {custom_config.web_search_enabled}")
    print(f"Max Edges: {custom_config.max_edges}")
    print(f"\nResponse:\n{result['response']}")


# ============================================================================
# EXAMPLE 3: COMPLIANCE ASSISTANT - BASIC USAGE
# ============================================================================

async def example_compliance_basic():
    """Basic compliance assistant usage"""
    print("\n" + "="*80)
    print("EXAMPLE 3: Compliance Assistant - Basic Usage")
    print("="*80 + "\n")
    
    # Create compliance assistant
    assistant = create_compliance_assistant()
    
    # Process query
    result = await assistant.process_query(
        user_question="What SOC2 controls are required for access control and monitoring?",
        available_frameworks=["SOC2", "ISO 27001"],
        available_products=["Okta", "Snyk"],
        available_actors=["Compliance Officer", "Auditor", "CISO"],
        output_format="summary"
    )
    
    print(f"Query Type: {result['breakdown'].query_type}")
    print(f"Compliance Context: {result['breakdown'].compliance_context}")
    print(f"Frameworks: {result['breakdown'].frameworks}")
    print(f"Retrieved Docs: {len(result['retrieved_docs'])}")
    print(f"\nResponse:\n{result['response']}")


# ============================================================================
# EXAMPLE 4: COMPLIANCE ASSISTANT - WITH TSC HIERARCHY
# ============================================================================

async def example_compliance_tsc():
    """Compliance assistant using TSC hierarchy"""
    print("\n" + "="*80)
    print("EXAMPLE 4: Compliance Assistant - TSC Hierarchy")
    print("="*80 + "\n")
    
    # Create compliance assistant
    assistant = create_compliance_assistant()
    
    # Process query about specific TSC category
    result = await assistant.process_query(
        user_question="What are the Security Privacy controls in SOC2 for data encryption?",
        available_frameworks=["SOC2"],
        available_products=["Snyk"],
        output_format="json"
    )
    
    print(f"Query Type: {result['breakdown'].query_type}")
    print(f"Compliance Context: {result['breakdown'].compliance_context}")
    print(f"Identified Entities: {result['breakdown'].identified_entities}")
    print(f"\nResponse (TSC Hierarchy):\n{result['response']}")


# ============================================================================
# EXAMPLE 5: DOMAIN KNOWLEDGE ASSISTANT - BASIC USAGE
# ============================================================================

async def example_domain_knowledge_basic():
    """Basic domain knowledge assistant usage"""
    print("\n" + "="*80)
    print("EXAMPLE 5: Domain Knowledge Assistant - Basic Usage")
    print("="*80 + "\n")
    
    # Create domain knowledge assistant
    assistant = create_domain_knowledge_assistant()
    
    # Process query
    result = await assistant.process_query(
        user_question="What are the best practices for implementing encryption at rest?",
        available_domains=["Security", "Privacy", "Cloud"],
        available_concepts=["Encryption", "Data Protection"],
        output_format="summary"
    )
    
    print(f"Query Type: {result['breakdown'].query_type}")
    print(f"Domain Context: {result['breakdown'].metadata.get('domain_context')}")
    print(f"Domains: {result['breakdown'].metadata.get('domains', [])}")
    print(f"Concepts: {result['breakdown'].metadata.get('concepts', [])}")
    print(f"\nResponse:\n{result['response']}")


# ============================================================================
# EXAMPLE 6: DOMAIN KNOWLEDGE ASSISTANT - WITH WEB SEARCH
# ============================================================================

async def example_domain_knowledge_web_search():
    """Domain knowledge assistant with web search enabled"""
    print("\n" + "="*80)
    print("EXAMPLE 6: Domain Knowledge Assistant - Web Search")
    print("="*80 + "\n")
    
    # Create assistant
    assistant = create_domain_knowledge_assistant()
    
    # Process query that benefits from web search
    result = await assistant.process_query(
        user_question="What is Zero Trust Architecture and how does it differ from traditional network security?",
        available_domains=["Security", "Network"],
        available_concepts=["Zero Trust", "Network Security"],
        output_format="summary"
    )
    
    print(f"Query Type: {result['breakdown'].query_type}")
    print(f"Web Search Queries: {result['breakdown'].metadata.get('web_search_queries', [])}")
    print(f"Web Search Results: {len(result['web_search_results'])}")
    print(f"\nResponse:\n{result['response']}")


# ============================================================================
# EXAMPLE 7: CUSTOM RETRIEVAL FUNCTION
# ============================================================================

async def custom_chroma_retrieval(breakdown, source_config) -> List[Dict[str, Any]]:
    """Custom retrieval function for Chroma"""
    logger.info(f"Custom retrieval for {source_config.source_name}")
    
    # In production, implement actual Chroma retrieval here
    # For demo, return mock data
    return [
        {
            "document": "Snyk provides vulnerability scanning through REST API endpoints...",
            "metadata": {"product_name": "Snyk", "category": "api_docs"},
            "relevance_score": 0.95
        },
        {
            "document": "To configure high-severity filtering, use the severity parameter...",
            "metadata": {"product_name": "Snyk", "category": "user_guides"},
            "relevance_score": 0.88
        }
    ]


async def example_custom_retrieval():
    """Using custom retrieval function"""
    print("\n" + "="*80)
    print("EXAMPLE 7: Custom Retrieval Function")
    print("="*80 + "\n")
    
    # Create assistant
    assistant = create_product_assistant()
    
    # Process query with custom retrieval
    result = await assistant.process_query(
        user_question="How do I use Snyk's API for vulnerability scanning?",
        available_products=["Snyk"],
        output_format="summary",
        # Provide custom retrieval function
        chroma_product_docs_retrieval_fn=custom_chroma_retrieval
    )
    
    print(f"Query Type: {result['breakdown'].query_type}")
    print(f"Retrieved Docs (custom): {len(result['retrieved_docs'])}")
    print(f"\nResponse:\n{result['response']}")


# ============================================================================
# EXAMPLE 8: COMPARING ALL THREE ASSISTANTS
# ============================================================================

async def example_compare_assistants():
    """Compare responses from all three assistants for similar queries"""
    print("\n" + "="*80)
    print("EXAMPLE 8: Comparing All Three Assistants")
    print("="*80 + "\n")
    
    # Create all three assistants
    product_assistant = create_product_assistant()
    compliance_assistant = create_compliance_assistant()
    domain_assistant = create_domain_knowledge_assistant()
    
    # Same base question, adapted for each domain
    base_question = "authentication and access control"
    
    # Product query
    print("\n--- PRODUCT ASSISTANT ---")
    product_result = await product_assistant.process_query(
        user_question=f"How does Okta handle {base_question}?",
        available_products=["Okta"],
        output_format="summary"
    )
    print(f"Type: {product_result['breakdown'].query_type}")
    print(f"Context: {product_result['breakdown'].product_context}")
    
    # Compliance query
    print("\n--- COMPLIANCE ASSISTANT ---")
    compliance_result = await compliance_assistant.process_query(
        user_question=f"What SOC2 controls cover {base_question}?",
        available_frameworks=["SOC2"],
        output_format="summary"
    )
    print(f"Type: {compliance_result['breakdown'].query_type}")
    print(f"Context: {compliance_result['breakdown'].compliance_context}")
    
    # Domain knowledge query
    print("\n--- DOMAIN KNOWLEDGE ASSISTANT ---")
    domain_result = await domain_assistant.process_query(
        user_question=f"What are best practices for {base_question}?",
        available_domains=["Security", "Identity"],
        output_format="summary"
    )
    print(f"Type: {domain_result['breakdown'].query_type}")
    print(f"Context: {domain_result['breakdown'].metadata.get('domain_context')}")


# ============================================================================
# EXAMPLE 9: BATCH PROCESSING
# ============================================================================

async def example_batch_processing():
    """Process multiple queries in batch"""
    print("\n" + "="*80)
    print("EXAMPLE 9: Batch Processing")
    print("="*80 + "\n")
    
    # Create assistant
    assistant = create_product_assistant()
    
    # List of queries
    queries = [
        "How do I integrate Snyk with GitHub?",
        "What API endpoints does Snyk provide?",
        "How do I configure Snyk to scan Docker images?"
    ]
    
    # Process all queries concurrently
    tasks = [
        assistant.process_query(
            user_question=query,
            available_products=["Snyk"],
            output_format="summary"
        )
        for query in queries
    ]
    
    results = await asyncio.gather(*tasks)
    
    print(f"Processed {len(results)} queries")
    for i, result in enumerate(results):
        print(f"\nQuery {i+1}: {queries[i]}")
        print(f"Type: {result['breakdown'].query_type}")
        print(f"Intent: {result['breakdown'].user_intent}")


# ============================================================================
# MAIN
# ============================================================================

async def main():
    """Run all examples"""
    print("\n" + "="*80)
    print("WORKFORCE ASSISTANTS USAGE EXAMPLES")
    print("="*80)
    
    examples = [
        ("Product Basic", example_product_basic),
        ("Product Custom Config", example_product_custom_config),
        ("Compliance Basic", example_compliance_basic),
        ("Compliance TSC", example_compliance_tsc),
        ("Domain Knowledge Basic", example_domain_knowledge_basic),
        ("Domain Knowledge Web Search", example_domain_knowledge_web_search),
        ("Custom Retrieval", example_custom_retrieval),
        ("Compare Assistants", example_compare_assistants),
        ("Batch Processing", example_batch_processing),
    ]
    
    for name, example_fn in examples:
        try:
            await example_fn()
        except Exception as e:
            logger.error(f"Error running example '{name}': {str(e)}", exc_info=True)
    
    print("\n" + "="*80)
    print("ALL EXAMPLES COMPLETE")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

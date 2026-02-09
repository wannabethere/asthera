"""
Integration Example
Demonstrates how to use ComprehensiveIndexingService with project_reader.py
and domain configurations.
"""
import asyncio
import json
import logging
from pathlib import Path

from app.indexing.comprehensive_indexing_service import ComprehensiveIndexingService
from app.config.domain_config import get_assets_domain_config, get_domain_config
from app.core.dependencies import (
    get_chromadb_client,
    get_embeddings_model,
    get_llm
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_index_mdl_schema():
    """Example: Index schema from MDL file."""
    # Initialize indexing service with ChromaDB using dependency injection
    persistent_client = get_chromadb_client()
    embeddings = get_embeddings_model()
    llm = get_llm(temperature=0.2)
    
    indexing_service = ComprehensiveIndexingService(
        vector_store_type="chroma",
        persistent_client=persistent_client,
        embeddings_model=embeddings,
        llm=llm,
        collection_prefix="snyk_index"
    )
    
    # Load MDL file
    mdl_path = Path("../../agents/tests/output/snyk_mdl1.json")
    if not mdl_path.exists():
        logger.error(f"MDL file not found: {mdl_path}")
        return
    
    with open(mdl_path, "r") as f:
        mdl_data = json.load(f)
    
    # Index schema with Assets domain
    result = await indexing_service.index_schema_from_mdl(
        mdl_data=mdl_data,
        product_name="Snyk",
        domain="Assets",
        metadata={
            "source": "snyk_mdl1.json",
            "version": "1.0"
        }
    )
    
    logger.info(f"Indexing result: {result}")


async def example_index_assets_domain():
    """Example: Index Assets domain configuration."""
    # Initialize indexing service using dependency injection
    persistent_client = get_chromadb_client()
    embeddings = get_embeddings_model()
    llm = get_llm(temperature=0.2)
    
    indexing_service = ComprehensiveIndexingService(
        vector_store_type="chroma",
        persistent_client=persistent_client,
        embeddings_model=embeddings,
        llm=llm,
        collection_prefix="assets_domain"
    )
    
    # Get Assets domain configuration
    assets_config = get_assets_domain_config()
    
    # Index example schema
    example_schema = assets_config.example_schema
    if example_schema:
        table_result = await indexing_service.index_table_definition(
            table_name=example_schema.table_name,
            columns=example_schema.columns,
            description=example_schema.description,
            product_name="Assets Management System",
            domain="Assets",
            metadata={
                "is_example": True,
                "primary_key": example_schema.primary_key
            }
        )
        logger.info(f"Indexed example table: {table_result}")
    
    # Index example use case
    example_use_case = assets_config.example_use_case
    if example_use_case:
        use_case_content = f"""
        Use Case: {example_use_case.name}
        
        Description: {example_use_case.description}
        
        Business Value: {example_use_case.business_value or 'N/A'}
        
        Example Queries:
        {chr(10).join(f'- {q}' for q in example_use_case.example_queries)}
        
        Example Data:
        {json.dumps(example_use_case.example_data, indent=2)}
        """
        
        knowledge_result = await indexing_service.index_domain_knowledge(
            knowledge=use_case_content,
            domain="Assets",
            product_name="Assets Management System",
            metadata={
                "use_case_name": example_use_case.name,
                "is_example": True
            }
        )
        logger.info(f"Indexed example use case: {knowledge_result}")
    
    # Index domain description
    domain_description = f"""
    Domain: {assets_config.domain_name}
    
    {assets_config.description}
    
    Related Domains: {', '.join(assets_config.metadata.get('related_domains', []))}
    Common Integrations: {', '.join(assets_config.metadata.get('common_integrations', []))}
    Compliance Frameworks: {', '.join(assets_config.metadata.get('compliance_frameworks', []))}
    """
    
    product_result = await indexing_service.index_product_description(
        description=domain_description,
        product_name="Assets Management System",
        domain="Assets",
        metadata={
            "domain_config": True
        }
    )
    logger.info(f"Indexed domain description: {product_result}")


async def example_search():
    """Example: Search indexed content."""
    # Initialize indexing service using dependency injection
    persistent_client = get_chromadb_client()
    embeddings = get_embeddings_model()
    
    indexing_service = ComprehensiveIndexingService(
        vector_store_type="chroma",
        persistent_client=persistent_client,
        embeddings_model=embeddings,
        collection_prefix="snyk_index"
    )
    
    # Search for asset-related content
    search_result = await indexing_service.search(
        query="What are the asset tables and their columns?",
        domain="Assets",
        k=5,
        search_type="semantic"
    )
    
    logger.info(f"Search results: {len(search_result['results'])} found")
    for i, result in enumerate(search_result["results"][:3], 1):
        logger.info(f"\nResult {i}:")
        logger.info(f"  Content Type: {result.get('content_type')}")
        logger.info(f"  Score: {result.get('score', 0):.4f}")
        logger.info(f"  Content Preview: {result.get('content', '')[:200]}...")


async def example_index_api_docs():
    """Example: Index API documentation."""
    # Initialize indexing service using dependency injection
    persistent_client = get_chromadb_client()
    embeddings = get_embeddings_model()
    llm = get_llm(temperature=0.2)
    
    indexing_service = ComprehensiveIndexingService(
        vector_store_type="chroma",
        persistent_client=persistent_client,
        embeddings_model=embeddings,
        llm=llm,
        collection_prefix="api_docs"
    )
    
    # Example API documentation
    api_docs = [
        {
            "endpoint": "/api/v1/assets",
            "method": "GET",
            "description": "Retrieve a list of assets",
            "parameters": [
                {"name": "asset_type", "type": "string", "required": False},
                {"name": "status", "type": "string", "required": False}
            ],
            "response": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/Asset"}
            }
        },
        {
            "endpoint": "/api/v1/assets/{asset_id}",
            "method": "GET",
            "description": "Retrieve a specific asset by ID",
            "parameters": [
                {"name": "asset_id", "type": "string", "required": True, "in": "path"}
            ],
            "response": {"$ref": "#/components/schemas/Asset"}
        }
    ]
    
    result = await indexing_service.index_api_docs(
        api_docs=api_docs,
        product_name="Assets API",
        domain="Assets",
        metadata={
            "api_version": "v1",
            "base_url": "https://api.example.com"
        }
    )
    
    logger.info(f"Indexed API docs: {result}")


async def example_index_snyk_product():
    """Example: Index Snyk product information with comprehensive details."""
    # Initialize indexing service using dependency injection
    persistent_client = get_chromadb_client()
    embeddings = get_embeddings_model()
    llm = get_llm(temperature=0.2)
    
    indexing_service = ComprehensiveIndexingService(
        vector_store_type="chroma",
        persistent_client=persistent_client,
        embeddings_model=embeddings,
        llm=llm,
        collection_prefix="snyk_product"
    )
    
    # Get comprehensive Snyk config
    try:
        from indexing_examples.snyk_product_config import (
            get_snyk_product_config,
            get_snyk_cve_exploit_db_explanation
        )
        snyk_config = get_snyk_product_config()
        cve_explanation = get_snyk_cve_exploit_db_explanation()
    except ImportError:
        logger.warning("Snyk config not available, using minimal example")
        snyk_config = {
            "product_name": "Snyk",
            "product_purpose": "Developer security platform",
            "product_docs_link": "https://docs.snyk.io",
            "key_concepts": [],
            "extendable_entities": [],
            "extendable_docs": []
        }
        cve_explanation = None
    
    # Index product information
    result = await indexing_service.index_product_from_dict(
        product_data=snyk_config,
        domain="Security"
    )
    logger.info(f"Indexed Snyk product information: {result}")
    
    # Index CVE/Exploit DB explanation if available
    if cve_explanation:
        cve_content = f"""
        {cve_explanation['title']}
        
        {cve_explanation['description']}
        
        Vulnerability Database:
        {cve_explanation['vulnerability_database']['overview']}
        
        Data Sources:
        {chr(10).join(f'- {source}' for source in cve_explanation['vulnerability_database']['data_sources'])}
        
        CVE Integration:
        {cve_explanation['vulnerability_database']['cve_integration']['how_it_works']}
        
        Exploit Maturity:
        {cve_explanation['vulnerability_database']['exploit_maturity']['overview']}
        """
        
        cve_result = await indexing_service.index_domain_knowledge(
            knowledge=cve_content,
            domain="Security",
            product_name="Snyk",
            metadata={
                "content_type": "cve_exploit_db_explanation",
                "source": "docs.snyk.io"
            }
        )
        logger.info(f"Indexed CVE/Exploit DB explanation: {cve_result}")


async def main():
    """Run all examples."""
    logger.info("Running comprehensive indexing examples...")
    
    # Example 1: Index Assets domain
    logger.info("\n=== Example 1: Index Assets Domain ===")
    await example_index_assets_domain()
    
    # Example 2: Index API docs
    logger.info("\n=== Example 2: Index API Docs ===")
    await example_index_api_docs()
    
    # Example 3: Index Snyk product
    logger.info("\n=== Example 3: Index Snyk Product ===")
    await example_index_snyk_product()
    
    # Example 4: Search
    logger.info("\n=== Example 4: Search ===")
    await example_search()
    
    # Example 5: Index MDL schema (if file exists)
    logger.info("\n=== Example 5: Index MDL Schema ===")
    try:
        await example_index_mdl_schema()
    except Exception as e:
        logger.warning(f"MDL indexing example skipped: {e}")


if __name__ == "__main__":
    asyncio.run(main())


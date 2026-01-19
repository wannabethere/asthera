"""
Example: Index Compliance Documents
Demonstrates how to index SOC2 controls, policy documents, and risk controls
using the comprehensive indexing service with extraction pipelines.
"""
import asyncio
import logging
from pathlib import Path

from app.indexing.comprehensive_indexing_service import ComprehensiveIndexingService
from app.core.dependencies import get_chromadb_client, get_embeddings_model, get_llm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def index_compliance_documents():
    """Index compliance documents (SOC2, policies, risk controls) with extraction pipelines."""
    
    # Initialize indexing service using dependency injection
    persistent_client = get_chromadb_client()
    embeddings = get_embeddings_model()
    llm = get_llm(temperature=0.2)
    
    indexing_service = ComprehensiveIndexingService(
        vector_store_type="chroma",
        persistent_client=persistent_client,
        embeddings_model=embeddings,
        llm=llm,
        collection_prefix="compliance_baseline"
    )
    
    # Get example files directory
    examples_dir = Path(__file__).parent
    
    # 1. Index Policy Document (PDF)
    policy_pdf = examples_dir / "Full Policy Packet.pdf"
    if policy_pdf.exists():
        logger.info(f"\n{'='*50}")
        logger.info("Indexing Policy Document")
        logger.info(f"{'='*50}")
        
        try:
            result = await indexing_service.index_policy_document(
                file_path=policy_pdf,
                domain="compliance",
                metadata={
                    "document_category": "policy",
                    "source": "baseline_documentation"
                }
            )
            logger.info(f"Policy indexing result: {result}")
        except Exception as e:
            logger.error(f"Error indexing policy document: {e}")
    else:
        logger.warning(f"Policy PDF not found: {policy_pdf}")
    
    # 2. Index Risk Controls (Excel)
    risk_controls_excel = examples_dir / "Risk and Controls.xlsx"
    if risk_controls_excel.exists():
        logger.info(f"\n{'='*50}")
        logger.info("Indexing Risk Controls")
        logger.info(f"{'='*50}")
        
        try:
            result = await indexing_service.index_risk_controls(
                file_path=risk_controls_excel,
                domain="compliance",
                metadata={
                    "document_category": "risk_controls",
                    "source": "baseline_documentation"
                }
            )
            logger.info(f"Risk controls indexing result: {result}")
        except Exception as e:
            logger.error(f"Error indexing risk controls: {e}")
    else:
        logger.warning(f"Risk controls Excel not found: {risk_controls_excel}")
    
    # 3. Index SOC2 Controls (if you have a SOC2 PDF or Excel)
    # Example for PDF:
    # soc2_pdf = examples_dir / "SOC2_Controls.pdf"
    # if soc2_pdf.exists():
    #     logger.info(f"\n{'='*50}")
    #     logger.info("Indexing SOC2 Controls")
    #     logger.info(f"{'='*50}")
    #     
    #     try:
    #         result = await indexing_service.index_soc2_controls(
    #             file_path=soc2_pdf,
    #             domain="compliance",
    #             metadata={
    #                 "document_category": "soc2_controls",
    #                 "source": "baseline_documentation"
    #             }
    #         )
    #         logger.info(f"SOC2 controls indexing result: {result}")
    #     except Exception as e:
    #         logger.error(f"Error indexing SOC2 controls: {e}")
    
    # 4. Search indexed compliance documents
    logger.info(f"\n{'='*50}")
    logger.info("Searching Compliance Documents")
    logger.info(f"{'='*50}")
    
    search_queries = [
        "What are the key security controls?",
        "What policies govern data access?",
        "What are the risk management procedures?",
        "What controls are required for SOC2 compliance?"
    ]
    
    for query in search_queries:
        logger.info(f"\nQuery: {query}")
        try:
            results = await indexing_service.search(
                query=query,
                content_types=["soc2_controls", "policy_documents", "risk_controls"],
                domain="compliance",
                k=5,
                search_type="semantic"
            )
            
            logger.info(f"Found {results['count']} results:")
            for i, result in enumerate(results['results'][:3], 1):
                logger.info(f"  Result {i}:")
                logger.info(f"    Score: {result.get('score', 0):.4f}")
                logger.info(f"    Content Type: {result.get('content_type', 'unknown')}")
                logger.info(f"    Content Preview: {result.get('content', '')[:200]}...")
        except Exception as e:
            logger.error(f"Error searching: {e}")


if __name__ == "__main__":
    asyncio.run(index_compliance_documents())


"""
Example: Index Compliance Documents with Flags
Demonstrates how to use flags to index different document types separately or comprehensively.
"""
import asyncio
import logging
from pathlib import Path

from app.indexing.comprehensive_indexing_service import ComprehensiveIndexingService
from app.core.dependencies import get_chromadb_client, get_embeddings_model, get_llm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def index_with_flags(
    index_policies: bool = False,
    index_risk_controls: bool = False,
    index_soc2: bool = False,
    comprehensive: bool = False,
    preview_mode: bool = True,
    preview_dir: str = "indexing_preview"
):
    """
    Index compliance documents with flags.
    
    Args:
        index_policies: Index policy documents
        index_risk_controls: Index risk controls
        index_soc2: Index SOC2 controls
        comprehensive: Index all document types
        preview_mode: Save to files instead of database
        preview_dir: Directory for preview files
    """
    # Get example files directory
    examples_dir = Path(__file__).parent
    
    # Initialize indexing service
    persistent_client = get_chromadb_client()
    embeddings = get_embeddings_model()
    llm = get_llm(temperature=0.2)
    
    indexing_service = ComprehensiveIndexingService(
        vector_store_type="chroma",
        persistent_client=persistent_client,
        embeddings_model=embeddings,
        llm=llm,
        collection_prefix="compliance_baseline",
        preview_mode=preview_mode,
        preview_output_dir=preview_dir
    )
    
    results = {}
    
    # Determine what to index
    if comprehensive:
        logger.info("Running in comprehensive mode - indexing all document types")
        index_policies = True
        index_risk_controls = True
        index_soc2 = True
    
    # Index policies
    if index_policies:
        policy_pdf = examples_dir / "Full Policy Packet.pdf"
        if policy_pdf.exists():
            logger.info(f"\n{'='*50}")
            logger.info("Indexing Policy Document")
            logger.info(f"{'='*50}")
            try:
                result = await indexing_service.index_policy_document(
                    file_path=policy_pdf,
                    domain="compliance",
                    metadata={"source": "example_script", "comprehensive": comprehensive}
                )
                results["policy"] = result
                if preview_mode:
                    logger.info(f"Preview saved to: {result.get('file_storage', {}).get('file_path', 'N/A')}")
                else:
                    logger.info(f"Indexed {result.get('documents_indexed', 0)} policy documents")
            except Exception as e:
                logger.error(f"Error indexing policy document: {e}")
                results["policy"] = {"error": str(e)}
        else:
            logger.warning(f"Policy PDF not found: {policy_pdf}")
    
    # Index risk controls
    if index_risk_controls:
        risk_controls_excel = examples_dir / "Risk and Controls.xlsx"
        if risk_controls_excel.exists():
            logger.info(f"\n{'='*50}")
            logger.info("Indexing Risk Controls")
            logger.info(f"{'='*50}")
            try:
                result = await indexing_service.index_risk_controls(
                    file_path=risk_controls_excel,
                    domain="compliance",
                    metadata={"source": "example_script", "comprehensive": comprehensive}
                )
                results["risk_controls"] = result
                if preview_mode:
                    logger.info(f"Preview saved to: {result.get('file_storage', {}).get('file_path', 'N/A')}")
                else:
                    logger.info(f"Indexed {result.get('documents_indexed', 0)} risk control documents")
            except Exception as e:
                logger.error(f"Error indexing risk controls: {e}")
                results["risk_controls"] = {"error": str(e)}
        else:
            logger.warning(f"Risk controls Excel not found: {risk_controls_excel}")
    
    # Index SOC2 controls (if you have a file)
    if index_soc2:
        logger.info(f"\n{'='*50}")
        logger.info("SOC2 Controls")
        logger.info(f"{'='*50}")
        logger.info("No SOC2 file provided in examples - skipping")
        # Uncomment and provide file path when available:
        # soc2_file = examples_dir / "SOC2_Controls.pdf"
        # if soc2_file.exists():
        #     result = await indexing_service.index_soc2_controls(
        #         file_path=soc2_file,
        #         domain="compliance"
        #     )
        #     results["soc2_controls"] = result
    
    # Summary
    logger.info(f"\n{'='*50}")
    logger.info("Indexing Summary")
    logger.info(f"{'='*50}")
    for doc_type, result in results.items():
        if result.get("preview_mode"):
            file_path = result.get("file_storage", {}).get("file_path", "N/A")
            logger.info(f"{doc_type}: Preview mode - saved to {file_path}")
        elif result.get("success"):
            logger.info(f"{doc_type}: Successfully indexed {result.get('documents_indexed', 0)} documents")
        else:
            logger.error(f"{doc_type}: Error - {result.get('error', 'Unknown error')}")


async def main():
    """Example usage with different flags."""
    
    # Example 1: Preview mode - just policies
    logger.info("Example 1: Preview mode - Policies only")
    await index_with_flags(
        index_policies=True,
        preview_mode=True
    )
    
    # Example 2: Preview mode - risk controls only
    # logger.info("\nExample 2: Preview mode - Risk Controls only")
    # await index_with_flags(
    #     index_risk_controls=True,
    #     preview_mode=True
    # )
    
    # Example 3: Comprehensive preview mode
    # logger.info("\nExample 3: Comprehensive preview mode")
    # await index_with_flags(
    #     comprehensive=True,
    #     preview_mode=True
    # )
    
    # Example 4: Index to database (after reviewing preview files)
    # logger.info("\nExample 4: Index to database")
    # await index_with_flags(
    #     comprehensive=True,
    #     preview_mode=False
    # )


if __name__ == "__main__":
    asyncio.run(main())


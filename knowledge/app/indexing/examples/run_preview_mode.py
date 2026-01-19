"""
Example: Run Comprehensive Indexing Service in Preview Mode

This script demonstrates how to use the ComprehensiveIndexingService in preview mode
to generate preview files instead of indexing directly to the vector database.

Preview mode is useful for:
- Reviewing extracted documents before committing to database
- Testing extraction pipelines
- Debugging document processing
- Validating data quality

Output files are saved to: indexing_preview/ (default)
"""
import asyncio
import logging
from pathlib import Path

from app.indexing.comprehensive_indexing_service import ComprehensiveIndexingService
from app.core.dependencies import get_chromadb_client, get_embeddings_model, get_llm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_preview_mode_example():
    """
    Example: Run indexing in preview mode.
    
    In preview mode, documents are saved to JSON files instead of being
    stored in the vector database. This allows you to review the extracted
    content before committing to the database.
    """
    
    # Initialize the service with preview_mode=True
    persistent_client = get_chromadb_client()
    embeddings = get_embeddings_model()
    llm = get_llm(temperature=0.2)
    
    indexing_service = ComprehensiveIndexingService(
        vector_store_type="chroma",
        persistent_client=persistent_client,
        embeddings_model=embeddings,
        llm=llm,
        collection_prefix="preview_test",
        preview_mode=True,  # Enable preview mode
        preview_output_dir="indexing_preview"  # Output directory (default)
    )
    
    logger.info("=" * 80)
    logger.info("Running Comprehensive Indexing Service in Preview Mode")
    logger.info("=" * 80)
    logger.info(f"Preview output directory: {indexing_service.file_storage.output_dir}")
    logger.info("")
    
    # Example 1: Index a policy document in preview mode
    examples_dir = Path(__file__).parent
    policy_pdf = examples_dir / "Full Policy Packet.pdf"
    
    if policy_pdf.exists():
        logger.info("Example 1: Indexing Policy Document (Preview Mode)")
        logger.info("-" * 80)
        
        result = await indexing_service.index_policy_document(
            file_path=policy_pdf,
            framework="SOC2",  # Optional: specify framework
            domain="compliance",
            metadata={"source": "preview_example"}
        )
        
        if result.get("preview_mode"):
            file_path = result.get("file_storage", {}).get("file_path", "N/A")
            summary_path = result.get("file_storage", {}).get("summary_path", "N/A")
            logger.info(f"✓ Preview saved to: {file_path}")
            logger.info(f"✓ Summary saved to: {summary_path}")
            logger.info(f"✓ Documents indexed: {result.get('documents_indexed', 0)}")
            logger.info(f"✓ Breakdown: {result.get('breakdown', {})}")
        else:
            logger.warning("Preview mode not active - documents were indexed to database")
    else:
        logger.warning(f"Policy PDF not found: {policy_pdf}")
        logger.info("Skipping policy document example")
    
    logger.info("")
    
    # Example 2: Index risk controls in preview mode
    risk_controls_excel = examples_dir / "Risk and Controls.xlsx"
    
    if risk_controls_excel.exists():
        logger.info("Example 2: Indexing Risk Controls (Preview Mode)")
        logger.info("-" * 80)
        
        result = await indexing_service.index_risk_controls(
            file_path=risk_controls_excel,
            framework="Risk Management",  # Optional: specify framework
            domain="compliance",
            metadata={"source": "preview_example"}
        )
        
        if result.get("preview_mode"):
            file_path = result.get("file_storage", {}).get("file_path", "N/A")
            logger.info(f"✓ Preview saved to: {file_path}")
            logger.info(f"✓ Documents indexed: {result.get('documents_indexed', 0)}")
        else:
            logger.warning("Preview mode not active")
    else:
        logger.warning(f"Risk controls Excel not found: {risk_controls_excel}")
        logger.info("Skipping risk controls example")
    
    logger.info("")
    
    # Example 3: Index API docs in preview mode
    logger.info("Example 3: Indexing API Documentation (Preview Mode)")
    logger.info("-" * 80)
    
    api_docs = [
        {
            "endpoint": "/api/v1/assets",
            "method": "GET",
            "description": "Retrieve a list of assets",
            "parameters": [
                {"name": "asset_type", "type": "string", "required": False},
                {"name": "status", "type": "string", "required": False}
            ]
        }
    ]
    
    result = await indexing_service.index_api_docs(
        api_docs=api_docs,
        product_name="Example API",
        domain="Assets",
        metadata={"source": "preview_example"}
    )
    
    # Note: API docs don't automatically use preview mode in the same way
    # They're stored in the database. To use preview mode for API docs,
    # you'd need to manually save them using FileStorage.
    logger.info(f"✓ API docs indexed: {result.get('documents_indexed', 0)}")
    logger.info("")
    
    # Example 4: Index product information in preview mode
    logger.info("Example 4: Indexing Product Information (Preview Mode)")
    logger.info("-" * 80)
    
    result = await indexing_service.index_product_info(
        product_name="Example Product",
        product_purpose="An example product for demonstration",
        product_docs_link="https://docs.example.com",
        key_concepts=["Concept 1", "Concept 2"],
        domain="Assets"
    )
    
    logger.info(f"✓ Product info indexed: {result.get('documents_indexed', 0)}")
    logger.info(f"✓ Breakdown: {result.get('breakdown', {})}")
    logger.info("")
    
    # Summary
    logger.info("=" * 80)
    logger.info("Preview Mode Summary")
    logger.info("=" * 80)
    logger.info(f"All preview files saved to: {indexing_service.file_storage.output_dir}")
    logger.info("")
    logger.info("To review the preview files:")
    logger.info("1. Check the JSON files in the output directory")
    logger.info("2. Review the summary .txt files for quick overview")
    logger.info("3. Once satisfied, run again with preview_mode=False to index to database")
    logger.info("")


async def run_with_custom_output_dir():
    """Example: Run with custom output directory."""
    
    indexing_service = ComprehensiveIndexingService(
        vector_store_type="chroma",
        persistent_client=get_chromadb_client(),
        embeddings_model=get_embeddings_model(),
        llm=get_llm(temperature=0.2),
        preview_mode=True,
        preview_output_dir="custom_preview_output"  # Custom directory
    )
    
    logger.info(f"Using custom output directory: {indexing_service.file_storage.output_dir}")


async def main():
    """Main entry point."""
    await run_preview_mode_example()
    
    # Uncomment to run with custom output directory:
    # await run_with_custom_output_dir()


if __name__ == "__main__":
    asyncio.run(main())


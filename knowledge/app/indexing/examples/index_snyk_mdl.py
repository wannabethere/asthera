"""
Direct Example: Index Snyk MDL File

This is a simple example script specifically for indexing the snyk_mdl1.json file.
You can use this as a template or run it directly.

Usage:
    # Preview mode (recommended first)
    python -m app.indexing.examples.index_snyk_mdl --preview

    # Index to database
    python -m app.indexing.examples.index_snyk_mdl
"""
import asyncio
import json
import logging
from pathlib import Path

from app.indexing.comprehensive_indexing_service import ComprehensiveIndexingService
from app.core.dependencies import get_chromadb_client, get_embeddings_model, get_llm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main(preview_mode: bool = False):
    """
    Index snyk_mdl1.json file.
    
    Args:
        preview_mode: If True, saves to files instead of indexing to database
    """
    # Path to snyk_mdl1.json (adjust if needed)
    # This assumes the file is in agents/tests/output/snyk_mdl1.json
    # relative to the flowharmonicai root
    script_dir = Path(__file__).parent.parent.parent.parent
    mdl_file = script_dir / "agents" / "tests" / "output" / "snyk_mdl1.json"
    
    if not mdl_file.exists():
        logger.error(f"MDL file not found: {mdl_file}")
        logger.info("Please update the path in the script or provide the file path as an argument")
        return
    
    logger.info("=" * 80)
    logger.info("Indexing Snyk MDL File")
    logger.info("=" * 80)
    logger.info(f"MDL File: {mdl_file}")
    logger.info(f"Preview Mode: {preview_mode}")
    logger.info("")
    
    # Load MDL file
    logger.info("Loading MDL file...")
    with open(mdl_file, "r", encoding="utf-8") as f:
        mdl_data = json.load(f)
    
    models_count = len(mdl_data.get("models", []))
    logger.info(f"Loaded MDL with {models_count} models")
    logger.info("")
    
    # Initialize service
    persistent_client = get_chromadb_client()
    embeddings = get_embeddings_model()
    llm = get_llm(temperature=0.2)
    
    service = ComprehensiveIndexingService(
        vector_store_type="chroma",
        persistent_client=persistent_client,
        embeddings_model=embeddings,
        llm=llm,
        collection_prefix="snyk_index",
        preview_mode=preview_mode,
        preview_output_dir="indexing_preview",
        enable_pipeline_processing=False,  # Skip pipelines for structured MDL schema data
        pipeline_batch_size=50  # Larger batch size if pipelines were enabled
    )
    
    # Index using schema processor (includes TableDescription + table definitions)
    logger.info("Indexing schema from MDL...")
    result = await service.index_schema_from_mdl(
        mdl_data=mdl_data,
        product_name="Snyk",
        domain="security",
        metadata={"source_file": str(mdl_file)},
        use_table_description_structure=True
    )
    
    # Display results
    logger.info("")
    logger.info("=" * 80)
    logger.info("Results")
    logger.info("=" * 80)
    
    if preview_mode:
        logger.info("Preview mode: Documents saved to files")
        logger.info(f"Preview output directory: indexing_preview/")
        logger.info("")
        logger.info("Review the preview files before indexing to database.")
        logger.info("To index to database, run without --preview flag.")
        
        if result.get("preview_mode"):
            logger.info(f"Table descriptions indexed: {result.get('table_descriptions_indexed', 0)}")
            if "schema_file_storage" in result:
                file_storage = result["schema_file_storage"]
                logger.info(f"Schema description saved to: {file_storage.get('file_path')}")
    else:
        logger.info("Database mode: Documents indexed to vector store")
        if result.get("success"):
            logger.info(f"✓ Tables indexed: {result.get('tables_indexed', 0)}")
            logger.info(f"✓ Columns indexed: {result.get('columns_indexed', 0)}")
            logger.info(f"✓ Table descriptions indexed: {result.get('table_descriptions_indexed', 0)}")
        else:
            logger.error(f"✗ Indexing failed: {result.get('error', 'Unknown error')}")
    
    logger.info("")
    logger.info("=" * 80)
    
    return result


if __name__ == "__main__":
    import sys
    
    preview_mode = "--preview" in sys.argv or "-p" in sys.argv
    
    asyncio.run(main(preview_mode=preview_mode))


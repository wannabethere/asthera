"""
CLI for indexing MDL (Model Definition Language) schema files.

This script provides a command-line interface for ingesting MDL JSON files
using the processors with preview mode support.

Usage:
    # Preview mode (saves to files)
    python -m app.indexing.cli.index_mdl \
        --mdl-file path/to/snyk_mdl1.json \
        --product-name Snyk \
        --preview

    # Run mode (indexes to database)
    python -m app.indexing.cli.index_mdl \
        --mdl-file path/to/snyk_mdl1.json \
        --product-name Snyk

    # Use specific processor
    python -m app.indexing.cli.index_mdl \
        --mdl-file path/to/snyk_mdl1.json \
        --product-name Snyk \
        --processor db_schema \
        --preview
"""
import asyncio
import argparse
import json
import logging
from pathlib import Path
from typing import Optional

from app.indexing.comprehensive_indexing_service import ComprehensiveIndexingService
from app.core.dependencies import get_chromadb_client, get_embeddings_model, get_llm

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def index_mdl_file(
    mdl_file_path: str,
    product_name: str,
    domain: Optional[str] = None,
    processor_type: str = "schema",
    preview_mode: bool = False,
    preview_output_dir: str = "indexing_preview",
    vector_store_type: str = "chroma",
    enable_pipeline_processing: bool = False,
    pipeline_batch_size: int = 50
):
    """
    Index an MDL file using the specified processor.
    
    Args:
        mdl_file_path: Path to MDL JSON file
        product_name: Product name (e.g., "Snyk")
        domain: Optional domain filter
        processor_type: Type of processor to use:
            - "schema": Uses index_schema_from_mdl (TableDescription + table definitions)
            - "db_schema": Uses index_db_schema_from_mdl (DBSchemaProcessor)
        preview_mode: If True, saves to files instead of indexing to database
        preview_output_dir: Directory for preview files
        vector_store_type: "chroma" or "qdrant"
        enable_pipeline_processing: If True, processes documents through extraction pipelines.
                                   Set to False for structured MDL data to skip LLM calls (default: False)
        pipeline_batch_size: Batch size for pipeline processing when enabled (default: 50)
    """
    mdl_path = Path(mdl_file_path)
    if not mdl_path.exists():
        raise FileNotFoundError(f"MDL file not found: {mdl_file_path}")
    
    logger.info("=" * 80)
    logger.info("MDL Schema Indexing")
    logger.info("=" * 80)
    logger.info(f"MDL File: {mdl_file_path}")
    logger.info(f"Product Name: {product_name}")
    logger.info(f"Domain: {domain or 'None'}")
    logger.info(f"Processor Type: {processor_type}")
    logger.info(f"Preview Mode: {preview_mode}")
    logger.info(f"Vector Store: {vector_store_type}")
    logger.info("")
    
    # Load MDL file
    logger.info(f"Loading MDL file: {mdl_path}")
    with open(mdl_path, "r", encoding="utf-8") as f:
        mdl_data = json.load(f)
    
    logger.info(f"Loaded MDL with {len(mdl_data.get('models', []))} models")
    logger.info("")
    
    # Initialize service
    persistent_client = None
    qdrant_client = None
    
    if vector_store_type == "chroma":
        persistent_client = get_chromadb_client()
    elif vector_store_type == "qdrant":
        # Qdrant client initialization would go here
        pass
    
    embeddings = get_embeddings_model()
    llm = get_llm(temperature=0.2)
    
    service = ComprehensiveIndexingService(
        vector_store_type=vector_store_type,
        persistent_client=persistent_client,
        qdrant_client=qdrant_client,
        embeddings_model=embeddings,
        llm=llm,
        collection_prefix="",  # Use empty prefix to match project_reader.py collections (db_schema, table_descriptions, column_metadata are unprefixed)
        preview_mode=preview_mode,
        preview_output_dir=preview_output_dir,
        enable_pipeline_processing=enable_pipeline_processing,
        pipeline_batch_size=pipeline_batch_size
    )
    
    # Index based on processor type
    if processor_type == "schema":
        logger.info("Using schema processor (TableDescription + table definitions)")
        result = await service.index_schema_from_mdl(
            mdl_data=mdl_data,
            product_name=product_name,
            domain=domain,
            metadata={"source_file": str(mdl_path)},
            use_table_description_structure=True
        )
    elif processor_type == "db_schema":
        logger.info("Using DB schema processor (DBSchemaProcessor)")
        result = await service.index_db_schema_from_mdl(
            mdl_data=mdl_data,
            product_name=product_name,
            domain=domain,
            metadata={"source_file": str(mdl_path)}
        )
    else:
        raise ValueError(f"Unknown processor type: {processor_type}. Use 'schema' or 'db_schema'")
    
    # Display results
    logger.info("")
    logger.info("=" * 80)
    logger.info("Indexing Results")
    logger.info("=" * 80)
    
    if preview_mode:
        logger.info("Preview mode: Documents saved to files")
        if result.get("preview_mode"):
            if processor_type == "schema":
                if "table_descriptions_indexed" in result:
                    logger.info(f"Table descriptions indexed: {result['table_descriptions_indexed']}")
                if "schema_file_storage" in result:
                    file_storage = result["schema_file_storage"]
                    logger.info(f"Schema description saved to: {file_storage.get('file_path')}")
            elif processor_type == "db_schema":
                file_storage = result.get("file_storage", {})
                logger.info(f"DB schema documents saved to: {file_storage.get('file_path')}")
        
        logger.info(f"Preview output directory: {preview_output_dir}")
        logger.info("")
        logger.info("Review the preview files before indexing to database.")
        logger.info("To index to database, run without --preview flag.")
    else:
        logger.info("Database mode: Documents indexed to vector store")
        if result.get("success"):
            if processor_type == "schema":
                logger.info(f"Tables indexed: {result.get('tables_indexed', 0)}")
                logger.info(f"Columns indexed: {result.get('columns_indexed', 0)}")
                logger.info(f"Table descriptions indexed: {result.get('table_descriptions_indexed', 0)}")
            elif processor_type == "db_schema":
                logger.info(f"Documents indexed: {result.get('documents_indexed', 0)}")
                logger.info(f"Store: {result.get('store', 'N/A')}")
        else:
            logger.error(f"Indexing failed: {result.get('error', 'Unknown error')}")
    
    logger.info("")
    logger.info("=" * 80)
    
    return result


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Index MDL schema files with preview/run options",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--mdl-file",
        required=True,
        help="Path to MDL JSON file"
    )
    
    parser.add_argument(
        "--product-name",
        required=True,
        help="Product name (e.g., 'Snyk')"
    )
    
    parser.add_argument(
        "--domain",
        default=None,
        help="Domain filter (optional)"
    )
    
    parser.add_argument(
        "--processor",
        choices=["schema", "db_schema"],
        default="schema",
        help="Processor type: 'schema' (TableDescription + tables) or 'db_schema' (DBSchemaProcessor)"
    )
    
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Enable preview mode (saves to files instead of database)"
    )
    
    parser.add_argument(
        "--preview-dir",
        default="indexing_preview",
        help="Directory for preview files (default: indexing_preview)"
    )
    
    parser.add_argument(
        "--vector-store",
        choices=["chroma", "qdrant"],
        default="chroma",
        help="Vector store type (default: chroma)"
    )
    
    parser.add_argument(
        "--enable-pipelines",
        action="store_true",
        help="Enable pipeline processing (entity/field extraction). Default: False (skipped for structured MDL data)"
    )
    
    parser.add_argument(
        "--pipeline-batch-size",
        type=int,
        default=50,
        help="Batch size for pipeline processing when enabled (default: 50)"
    )
    
    args = parser.parse_args()
    
    # Run async function
    asyncio.run(index_mdl_file(
        mdl_file_path=args.mdl_file,
        product_name=args.product_name,
        domain=args.domain,
        processor_type=args.processor,
        preview_mode=args.preview,
        preview_output_dir=args.preview_dir,
        vector_store_type=args.vector_store,
        enable_pipeline_processing=args.enable_pipelines,
        pipeline_batch_size=args.pipeline_batch_size
    ))


if __name__ == "__main__":
    main()


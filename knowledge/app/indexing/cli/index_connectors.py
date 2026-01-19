"""
CLI for indexing connector/product configurations with preview mode support.

This script indexes product/connector definitions, purposes, data source types, and
extendable entities into ChromaDB or Qdrant stores. It supports preview mode to dump
configurations to files before indexing, similar to index_compliance.py.

The script can load product configurations from:
- Python modules (e.g., snyk_product_config.py with SNYK_PRODUCT_CONFIG)
- JSON files with product configuration structure

Usage:
    # Preview mode (saves to files)
    python -m app.indexing.cli.index_connectors \
        --config-file knowledge/app/indexing/examples/snyk_product_config.py \
        --product-name Snyk \
        --preview

    # Direct indexing mode
    python -m app.indexing.cli.index_connectors \
        --config-file knowledge/app/indexing/examples/snyk_product_config.py \
        --product-name Snyk

    # Load from JSON file
    python -m app.indexing.cli.index_connectors \
        --config-file path/to/product_config.json \
        --product-name MyProduct \
        --config-format json \
        --preview

    # Index multiple products
    python -m app.indexing.cli.index_connectors \
        --config-file path/to/configs/ \
        --config-format directory \
        --preview
"""
import asyncio
import argparse
import json
import logging
import importlib.util
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List

from app.indexing.comprehensive_indexing_service import ComprehensiveIndexingService
from app.core.dependencies import get_chromadb_client, get_embeddings_model, get_llm

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config_from_python(file_path: Path) -> Dict[str, Any]:
    """
    Load product configuration from a Python file.
    
    Looks for variables named:
    - {PRODUCT_NAME}_PRODUCT_CONFIG (e.g., SNYK_PRODUCT_CONFIG)
    - PRODUCT_CONFIG
    - Any variable ending with _PRODUCT_CONFIG
    
    Args:
        file_path: Path to Python file
        
    Returns:
        Dictionary with product configuration
    """
    spec = importlib.util.spec_from_file_location("product_config", file_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Could not load Python module from {file_path}")
    
    module = importlib.util.module_from_spec(spec)
    sys.modules["product_config"] = module
    spec.loader.exec_module(module)
    
    # Look for product config variables
    config_vars = [
        var for var in dir(module)
        if not var.startswith("_") and (
            var.endswith("_PRODUCT_CONFIG") or var == "PRODUCT_CONFIG"
        )
    ]
    
    if not config_vars:
        raise ValueError(
            f"No product configuration found in {file_path}. "
            f"Expected variable ending with _PRODUCT_CONFIG or PRODUCT_CONFIG"
        )
    
    # Use the first matching variable
    config_var = config_vars[0]
    config = getattr(module, config_var)
    
    logger.info(f"Loaded product configuration from {file_path} (variable: {config_var})")
    return config


def load_config_from_json(file_path: Path) -> Dict[str, Any]:
    """
    Load product configuration from a JSON file.
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        Dictionary with product configuration
    """
    with open(file_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    logger.info(f"Loaded product configuration from {file_path}")
    return config


def load_product_config(
    config_path: str,
    config_format: str = "auto"
) -> Dict[str, Any]:
    """
    Load product configuration from file or directory.
    
    Args:
        config_path: Path to config file or directory
        config_format: Format type - "auto", "python", "json", or "directory"
        
    Returns:
        Dictionary with product configuration
    """
    path = Path(config_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Config path does not exist: {config_path}")
    
    # Handle directory
    if path.is_dir() or config_format == "directory":
        # Look for Python or JSON files in directory
        python_files = list(path.glob("*.py"))
        json_files = list(path.glob("*.json"))
        
        if python_files:
            # Use first Python file
            return load_config_from_python(python_files[0])
        elif json_files:
            # Use first JSON file
            return load_config_from_json(json_files[0])
        else:
            raise ValueError(f"No Python or JSON config files found in {path}")
    
    # Handle single file
    if config_format == "auto":
        # Auto-detect format
        if path.suffix == ".py":
            config_format = "python"
        elif path.suffix == ".json":
            config_format = "json"
        else:
            raise ValueError(f"Could not auto-detect format for {path}. Use --config-format")
    
    if config_format == "python":
        return load_config_from_python(path)
    elif config_format == "json":
        return load_config_from_json(path)
    else:
        raise ValueError(f"Unknown config format: {config_format}")


async def index_connector_config(
    config_file: str,
    product_name: Optional[str] = None,
    domain: Optional[str] = None,
    config_format: str = "auto",
    preview_mode: bool = False,
    preview_output_dir: str = "indexing_preview",
    vector_store_type: str = "chroma",
    collection_prefix: str = "connector_index",
    metadata: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Index connector/product configuration.
    
    Args:
        config_file: Path to config file or directory
        product_name: Product name (overrides config if provided)
        domain: Domain filter
        config_format: Format type - "auto", "python", "json", or "directory"
        preview_mode: If True, saves to files instead of indexing to database
        preview_output_dir: Directory for preview files
        vector_store_type: "chroma" or "qdrant"
        collection_prefix: Prefix for collection names
        metadata: Additional metadata
        
    Returns:
        Dictionary with indexing results
    """
    logger.info("=" * 80)
    logger.info("Connector/Product Configuration Indexing")
    logger.info("=" * 80)
    logger.info(f"Config File: {config_file}")
    logger.info(f"Product Name: {product_name or 'From config'}")
    logger.info(f"Domain: {domain or 'None'}")
    logger.info(f"Config Format: {config_format}")
    logger.info(f"Preview Mode: {preview_mode}")
    logger.info(f"Vector Store: {vector_store_type}")
    logger.info(f"Collection Prefix: {collection_prefix}")
    logger.info("")
    
    # Load configuration
    try:
        product_config = load_product_config(config_file, config_format)
    except Exception as e:
        logger.error(f"Error loading product configuration: {e}")
        return {
            "success": False,
            "error": f"Failed to load configuration: {e}"
        }
    
    # Extract product name
    if not product_name:
        product_name = product_config.get("product_name")
        if not product_name:
            raise ValueError("product_name must be provided or present in config")
    
    logger.info(f"Loaded configuration for product: {product_name}")
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
        collection_prefix=collection_prefix,
        preview_mode=preview_mode,
        preview_output_dir=preview_output_dir,
        enable_pipeline_processing=True,  # Enable pipelines for product info
        pipeline_batch_size=50
    )
    
    # Prepare metadata
    indexing_metadata = {
        "source": "cli",
        "config_file": str(config_file),
        "config_format": config_format,
        **(metadata or {})
    }
    
    # Index product configuration
    try:
        result = await service.index_product_from_dict(
            product_data=product_config,
            domain=domain,
            metadata=indexing_metadata
        )
    except Exception as e:
        logger.error(f"Error indexing product configuration: {e}")
        return {
            "success": False,
            "error": str(e),
            "product_name": product_name
        }
    
    # Display results
    logger.info("")
    logger.info("=" * 80)
    logger.info("Indexing Results")
    logger.info("=" * 80)
    
    if preview_mode:
        logger.info("Preview mode: Documents saved to files")
        logger.info(f"Preview output directory: {preview_output_dir}")
        logger.info("")
        logger.info("Review the preview files before indexing to database.")
        logger.info("To index to database, run without --preview flag.")
        logger.info("")
        logger.info("To ingest preview files, run:")
        logger.info(f"  python -m app.indexing.cli.ingest_preview_files \\")
        logger.info(f"      --preview-dir {preview_output_dir} \\")
        logger.info(f"      --collection-prefix {collection_prefix}")
    else:
        logger.info("Database mode: Documents indexed to vector store")
        if result.get("success"):
            logger.info(f"Product: {result.get('product_name')}")
            logger.info(f"Total documents indexed: {result.get('documents_indexed', 0)}")
            logger.info("Breakdown by store:")
            breakdown = result.get("breakdown", {})
            for store_name, count in breakdown.items():
                logger.info(f"  {store_name}: {count} documents")
        else:
            logger.error(f"Indexing failed: {result.get('error', 'Unknown error')}")
    
    logger.info("")
    logger.info("=" * 80)
    
    return result


async def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Index connector/product configurations with preview mode support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--config-file",
        type=str,
        required=True,
        help="Path to product configuration file (Python or JSON) or directory"
    )
    
    parser.add_argument(
        "--product-name",
        type=str,
        default=None,
        help="Product name (overrides config if provided)"
    )
    
    parser.add_argument(
        "--domain",
        type=str,
        default=None,
        help="Domain filter (e.g., 'security', 'compliance')"
    )
    
    parser.add_argument(
        "--config-format",
        type=str,
        choices=["auto", "python", "json", "directory"],
        default="auto",
        help="Config file format (default: auto-detect)"
    )
    
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Preview mode: save to files instead of indexing in database"
    )
    
    parser.add_argument(
        "--preview-dir",
        type=str,
        default="indexing_preview",
        help="Directory for preview files (default: indexing_preview)"
    )
    
    parser.add_argument(
        "--vector-store",
        type=str,
        choices=["chroma", "qdrant"],
        default="chroma",
        help="Vector store type (default: chroma)"
    )
    
    parser.add_argument(
        "--collection-prefix",
        type=str,
        default="connector_index",
        help="Prefix for collection names (default: connector_index)"
    )
    
    args = parser.parse_args()
    
    # Run indexing
    result = await index_connector_config(
        config_file=args.config_file,
        product_name=args.product_name,
        domain=args.domain,
        config_format=args.config_format,
        preview_mode=args.preview,
        preview_output_dir=args.preview_dir,
        vector_store_type=args.vector_store,
        collection_prefix=args.collection_prefix
    )
    
    if not result.get("success"):
        logger.error(f"Indexing failed: {result.get('error', 'Unknown error')}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))


#!/usr/bin/env python3
"""
Command-line interface for the new ingestion architecture.
This CLI allows running ingestion pipelines for different data sources.
"""
import argparse
import logging
import json
import sys
import os
from typing import Dict, Any, Optional
from pathlib import Path

from ingestions.source_based_ingestion.factories import (
    IngestFactory,
    GongIngestFactory,
    get_factory
)
from ingestions.source_based_ingestion.pipeline import IngestPipeline, run_pipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load configuration from a JSON file.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        Configuration dictionary
    """
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading configuration from {config_path}: {e}")
        sys.exit(1)

def get_factory_for_source(source_type: str) -> IngestFactory:
    """
    Get the appropriate factory for the given source type.
    
    Args:
        source_type: Type of data source
        
    Returns:
        Factory instance for the specified source type
    """
    try:
        return get_factory(source_type)
    except ValueError as e:
        logger.error(str(e))
        logger.error(f"Supported source types: gong (more coming soon)")
        sys.exit(1)

def run_ingestion(
    source_type: str,
    config: Dict[str, Any],
    debug: bool = False,
    test_mode: bool = False,
    limit: Optional[int] = None,
    skip_insights: bool = False
) -> None:
    """
    Run an ingestion pipeline for the specified source type.
    
    Args:
        source_type: Type of data source
        config: Configuration dictionary
        debug: Enable debug logging
        test_mode: Run in test mode (no actual storage)
        limit: Limit the number of documents to process
        skip_insights: Skip insights generation
    """
    # Set debug flag
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")
    
    # Add runtime flags to config
    config["debug"] = debug
    config["test_mode"] = test_mode
    config["limit"] = limit
    config["skip_insights"] = skip_insights
    
    # Determine storage type based on config
    storage_type = "default"
    if config.get("use_postgres", True) and not config.get("use_chroma", True):
        storage_type = "postgres"
    elif config.get("use_chroma", True) and not config.get("use_postgres", True):
        storage_type = "chroma"
    
    logger.info(f"Starting ingestion pipeline for source type: {source_type}")
    
    if test_mode:
        logger.info("Running in TEST MODE - no actual storage will occur")
    
    if limit:
        logger.info(f"Processing limited to {limit} documents")
    
    if skip_insights:
        logger.info("Insights generation will be skipped")
    
    # Run the pipeline using the convenience function
    try:
        results = run_pipeline(source_type, config, storage_type)
        logger.info(f"Ingestion pipeline completed successfully")
        logger.info(f"Processed {results.get('documents_extracted', 0)} documents")
        logger.info(f"Generated {results.get('vectors_created', 0)} vector chunks")
        logger.info(f"Generated {results.get('stats_generated', 0)} stats records")
        
        # Print success/failure
        if results.get("success", False):
            logger.info("Pipeline completed successfully")
        else:
            logger.warning("Pipeline completed with errors")
            for error in results.get("errors", []):
                logger.error(f"Error: {error}")
    except Exception as e:
        logger.error(f"Error running ingestion pipeline: {e}")
        if debug:
            import traceback
            logger.debug(traceback.format_exc())
        sys.exit(1)

def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Run ingestion pipelines for different data sources"
    )
    
    # Source type argument
    parser.add_argument(
        "source_type",
        choices=["gong", "pdf", "gdrive", "salesforce"],
        help="Type of data source to ingest"
    )
    
    # Configuration options
    parser.add_argument(
        "-c", "--config",
        help="Path to configuration file (JSON)",
        required=False
    )
    
    # Source-specific options
    parser.add_argument(
        "-i", "--input",
        help="Path to input file or directory",
        required=False
    )
    
    parser.add_argument(
        "-o", "--output",
        help="Path to output directory",
        required=False
    )
    
    # Storage options
    parser.add_argument(
        "--no-postgres",
        action="store_true",
        help="Skip PostgreSQL storage"
    )
    
    parser.add_argument(
        "--no-chroma",
        action="store_true",
        help="Skip ChromaDB storage"
    )
    
    # Runtime options
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run in test mode (no actual storage)"
    )
    
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit the number of documents to process"
    )
    
    parser.add_argument(
        "--skip-insights",
        action="store_true",
        help="Skip insights generation"
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Load configuration
    config = {}
    if args.config:
        config = load_config(args.config)
    
    # Add command-line options to config
    if args.input:
        config["input_path"] = args.input
    
    if args.output:
        config["output_path"] = args.output
    
    # Storage options
    config["use_postgres"] = not args.no_postgres
    config["use_chroma"] = not args.no_chroma
    
    # Run the ingestion pipeline
    run_ingestion(
        source_type=args.source_type,
        config=config,
        debug=args.debug,
        test_mode=args.test,
        limit=args.limit,
        skip_insights=args.skip_insights
    )

if __name__ == "__main__":
    main() 
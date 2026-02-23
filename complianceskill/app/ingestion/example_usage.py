"""
CLI script to test framework ingestion.

This script:
1. Loads environment variables from .env file (via app.core.settings)
2. Initializes database tables and Qdrant collections
3. Ingests frameworks from YAML files
4. Verifies collections using FrameworkCollectionFactory
5. Provides detailed status reporting

Environment Variables (from .env file):
    DATABASE_URL          - Postgres connection string (optional, uses settings if not set)
    POSTGRES_HOST         - Database host (from settings)
    POSTGRES_PORT         - Database port (from settings)
    POSTGRES_DB           - Database name (from settings)
    POSTGRES_USER         - Database user (from settings)
    POSTGRES_PASSWORD     - Database password (from settings)
    QDRANT_URL            - Qdrant URL (optional, uses settings if not set)
    QDRANT_HOST           - Qdrant host (from settings)
    QDRANT_PORT           - Qdrant port (from settings)
    QDRANT_API_KEY        - Qdrant API key (optional)
    OPENAI_API_KEY        - Required for embeddings (unless --skip-qdrant)

Usage:
    python -m app.ingestion.example_usage --data-dir /path/to/risk_control_yaml
    python -m app.ingestion.example_usage --data-dir /path/to/risk_control_yaml --frameworks cis_v8_1 hipaa
    python -m app.ingestion.example_usage --data-dir /path/to/risk_control_yaml --reinit --verify
"""

import argparse
import logging
import sys
from pathlib import Path

# Ensure .env is loaded by importing settings early
from app.core.settings import get_settings

# Import services after settings are loaded
from app.ingestion.service import IngestionService
from app.storage.framework_collection_factory import (
    FrameworkCollectionFactory,
    FrameworkArtifactType,
)
from app.storage.qdrant_framework_store import Collections
from app.ingestion.frameworks import ADAPTER_REGISTRY

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def verify_collections():
    """Verify that all framework collections exist and have data."""
    logger.info("\n" + "=" * 60)
    logger.info("Verifying Qdrant Collections")
    logger.info("=" * 60)
    
    factory = FrameworkCollectionFactory()
    
    # Get all collection names
    all_collections = FrameworkCollectionFactory.get_all_collections()
    framework_collections = FrameworkCollectionFactory.get_framework_collections()
    
    logger.info(f"\nFramework Collections: {len(framework_collections)}")
    for collection in framework_collections:
        info = factory.get_collection_info(collection)
        if "error" in info:
            logger.warning(f"  ✗ {collection}: {info['error']}")
        else:
            logger.info(f"  ✓ {collection}: {info.get('points_count', 0)} points")
    
    logger.info(f"\nAll Collections: {len(all_collections)}")
    for collection in all_collections:
        info = factory.get_collection_info(collection)
        if "error" in info:
            logger.warning(f"  ✗ {collection}: {info['error']}")
        else:
            logger.info(f"  ✓ {collection}: {info.get('points_count', 0)} points")
    
    # Test collection name mapping
    logger.info("\nCollection Name Mapping:")
    for artifact_type in FrameworkArtifactType:
        collection_name = FrameworkCollectionFactory.get_collection_for_artifact(artifact_type)
        logger.info(f"  {artifact_type.value} → {collection_name}")


def verify_database_tables(service: IngestionService):
    """Verify that database tables have data."""
    logger.info("\n" + "=" * 60)
    logger.info("Verifying Database Tables")
    logger.info("=" * 60)
    
    # List all frameworks
    frameworks = service.list_frameworks()
    logger.info(f"\nIngested Frameworks: {len(frameworks)}")
    for fw in frameworks:
        logger.info(f"  - {fw['id']}: {fw['name']} {fw['version']}")
    
    # Get stats for each framework
    for fw_id in [fw['id'] for fw in frameworks]:
        stats = service.get_framework_stats(fw_id)
        if stats:
            logger.info(f"\n{fw_id} Statistics:")
            for artifact_type, count in stats.items():
                logger.info(f"  {artifact_type}: {count}")
        else:
            logger.warning(f"  No stats available for {fw_id}")


def main():
    parser = argparse.ArgumentParser(
        description="Test framework ingestion and verify collections",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Ingest all frameworks
  python -m app.ingestion.example_usage --data-dir /path/to/risk_control_yaml

  # Ingest specific frameworks
  python -m app.ingestion.example_usage --data-dir /path/to/risk_control_yaml --frameworks cis_v8_1 hipaa

  # Reinitialize collections (destructive)
  python -m app.ingestion.example_usage --data-dir /path/to/risk_control_yaml --reinit

  # Verify collections after ingestion
  python -m app.ingestion.example_usage --data-dir /path/to/risk_control_yaml --verify

  # Postgres only (skip Qdrant)
  python -m app.ingestion.example_usage --data-dir /path/to/risk_control_yaml --skip-qdrant
        """
    )
    
    parser.add_argument(
        "--data-dir",
        type=str,
        required=True,
        help="Directory containing framework YAML files",
    )
    parser.add_argument(
        "--frameworks",
        nargs="*",
        choices=list(ADAPTER_REGISTRY.keys()),
        default=None,
        help="Specific frameworks to ingest (default: all)",
    )
    parser.add_argument(
        "--reinit",
        action="store_true",
        help="Reinitialize Qdrant collections (destructive - wipes existing data)",
    )
    parser.add_argument(
        "--reinit-db",
        action="store_true",
        help="Drop and recreate database tables (destructive - wipes existing data). "
             "Use this if you get foreign key constraint errors due to schema mismatches.",
    )
    parser.add_argument(
        "--skip-qdrant",
        action="store_true",
        help="Skip Qdrant operations (Postgres only)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify collections and database tables after ingestion",
    )
    parser.add_argument(
        "--no-fail-fast",
        action="store_true",
        help="Continue ingesting even if one framework fails",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip cross-framework mapping validation",
    )
    
    args = parser.parse_args()
    
    # Load settings early to ensure .env is loaded
    # This will automatically load from .env file via pydantic_settings
    settings = get_settings()
    logger.info("Environment configuration loaded from .env file")
    logger.debug(f"Database: {settings.DATABASE_TYPE}, Qdrant: {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
    
    # Validate data directory
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        logger.error(f"Data directory does not exist: {data_dir}")
        return 1
    
    logger.info("=" * 60)
    logger.info("Framework Ingestion Test")
    logger.info("=" * 60)
    logger.info(f"Data directory: {data_dir.resolve()}")
    logger.info(f"Frameworks: {args.frameworks or 'all available'}")
    logger.info(f"Reinitialize Qdrant: {args.reinit}")
    logger.info(f"Reinitialize Database: {args.reinit_db}")
    logger.info(f"Skip Qdrant: {args.skip_qdrant}")
    logger.info("")
    
    # ---------------------------------------------------------------------------
    # Step 1: Initialize IngestionService
    # ---------------------------------------------------------------------------
    logger.info("Step 1: Initializing IngestionService...")
    service = IngestionService(skip_qdrant=args.skip_qdrant)
    
    # ---------------------------------------------------------------------------
    # Step 2: Initialize Storage (tables and collections)
    # ---------------------------------------------------------------------------
    logger.info("\nStep 2: Initializing storage (database tables and Qdrant collections)...")
    
    # Drop database tables if requested
    if args.reinit_db:
        from app.storage.sqlalchemy_session import drop_tables
        logger.warning("Dropping all database tables...")
        drop_tables()
    
    if not service.initialize_storage(
        recreate_qdrant=args.reinit,
        check_connections=True,
    ):
        logger.error("Failed to initialize storage. Check your configuration.")
        logger.error("Make sure:")
        logger.error("  - Database is running and accessible")
        if not args.skip_qdrant:
            logger.error("  - Qdrant is running and accessible")
            logger.error("  - OPENAI_API_KEY is set (for embeddings)")
        return 1
    
    logger.info("✓ Storage initialized successfully")
    
    # Show available frameworks
    available = IngestionService.get_available_frameworks()
    logger.info(f"\nAvailable frameworks: {available}")
    
    # ---------------------------------------------------------------------------
    # Step 3: Ingest Frameworks
    # ---------------------------------------------------------------------------
    logger.info("\nStep 3: Ingesting frameworks...")
    summary = service.ingest_frameworks(
        data_dir=data_dir,
        framework_ids=args.frameworks,
        fail_fast=not args.no_fail_fast,
        validate_mappings=not args.skip_validation,
    )
    
    # ---------------------------------------------------------------------------
    # Step 4: Report Results
    # ---------------------------------------------------------------------------
    logger.info("\n" + "=" * 60)
    logger.info("Ingestion Results")
    logger.info("=" * 60)
    logger.info(f"Total frameworks: {summary.total_frameworks}")
    logger.info(f"Succeeded: {len(summary.succeeded)} - {summary.succeeded}")
    if summary.failed:
        logger.warning(f"Failed: {len(summary.failed)} - {summary.failed}")
    
    # Detailed results
    if summary.results:
        logger.info("\nDetailed Results:")
        for result in summary.results:
            if result.success:
                logger.info(f"  ✓ {result.framework_id}:")
                for artifact_type, count in result.stats.items():
                    logger.info(f"      {artifact_type}: {count}")
            else:
                logger.error(f"  ✗ {result.framework_id}: {result.error}")
    
    # Validation report
    if summary.validation_report:
        logger.info("\nCross-Framework Mapping Validation:")
        print(summary.validation_report)
    
    # ---------------------------------------------------------------------------
    # Step 5: Verify Collections (if requested)
    # ---------------------------------------------------------------------------
    if args.verify:
        if not args.skip_qdrant:
            verify_collections()
        verify_database_tables(service)
    
    # ---------------------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------------------
    logger.info("\n" + "=" * 60)
    logger.info("Summary")
    logger.info("=" * 60)
    if summary.failed:
        logger.warning(f"Ingestion completed with {len(summary.failed)} failure(s)")
        return 1
    else:
        logger.info("✓ Ingestion completed successfully!")
        return 0


if __name__ == "__main__":
    sys.exit(main())

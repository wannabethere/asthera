"""
Main ingestion script using IngestionService.

Usage:
  # Ingest all frameworks (frameworks with YAML files in DATA_DIR)
  python -m app.ingestion.ingest --data-dir /path/to/yamls

  # Ingest specific frameworks
  python -m app.ingestion.ingest --data-dir /path/to/yamls --frameworks cis_v8_1 hipaa

  # Re-initialize Qdrant collections (wipes existing vectors)
  python -m app.ingestion.ingest --data-dir /path/to/yamls --reinit-qdrant

  # Skip embedding (Postgres only — fast, for schema iteration)
  python -m app.ingestion.ingest --data-dir /path/to/yamls --skip-qdrant

  # Continue on errors (don't fail fast)
  python -m app.ingestion.ingest --data-dir /path/to/yamls --no-fail-fast

  # Skip cross-framework validation
  python -m app.ingestion.ingest --data-dir /path/to/yamls --skip-validation

Environment variables:
  DATABASE_URL    Postgres connection string (uses app.core.settings if not set)
  QDRANT_URL      Qdrant URL (uses app.core.settings if not set)
  QDRANT_HOST     Qdrant host (uses app.core.settings if not set)
  QDRANT_PORT     Qdrant port (uses app.core.settings if not set)
  OPENAI_API_KEY  Required unless --skip-qdrant is set
"""

import argparse
import logging
import sys
from pathlib import Path

from app.ingestion.service import IngestionService
from app.ingestion.frameworks import ADAPTER_REGISTRY

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest compliance framework YAML files into Postgres + Qdrant"
    )
    parser.add_argument(
        "--data-dir",
        default=".",
        help="Directory containing framework YAML files (default: current dir)",
    )
    parser.add_argument(
        "--frameworks",
        nargs="*",
        choices=list(ADAPTER_REGISTRY.keys()),
        default=None,
        help="Frameworks to ingest (default: all registered). E.g.: cis_v8_1 hipaa",
    )
    parser.add_argument(
        "--reinit-qdrant",
        action="store_true",
        help="Delete and recreate Qdrant collections (destructive)",
    )
    parser.add_argument(
        "--skip-qdrant",
        action="store_true",
        help="Populate Postgres only; skip embedding and Qdrant upsert",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip cross-framework mapping validation pass",
    )
    parser.add_argument(
        "--no-fail-fast",
        action="store_true",
        help="Continue ingesting remaining frameworks even if one fails",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # ------------------------------------------------------------------
    # Initialize IngestionService
    # ------------------------------------------------------------------
    service = IngestionService(skip_qdrant=args.skip_qdrant)

    # ------------------------------------------------------------------
    # Initialize storage (database tables and Qdrant collections)
    # ------------------------------------------------------------------
    logger.info("Initializing storage...")
    if not service.initialize_storage(
        recreate_qdrant=args.reinit_qdrant,
        check_connections=True,
    ):
        logger.error("Storage initialization failed. Check your configuration.")
        return 1

    # ------------------------------------------------------------------
    # Ingest frameworks
    # ------------------------------------------------------------------
    data_dir = Path(args.data_dir)
    framework_ids = args.frameworks if args.frameworks else None

    logger.info(f"Data directory: {data_dir.resolve()}")
    if framework_ids:
        logger.info(f"Ingesting frameworks: {framework_ids}")
    else:
        logger.info("Ingesting all available frameworks")

    summary = service.ingest_frameworks(
        data_dir=data_dir,
        framework_ids=framework_ids,
        fail_fast=not args.no_fail_fast,
        validate_mappings=not args.skip_validation,
    )

    # ------------------------------------------------------------------
    # Print validation report if available
    # ------------------------------------------------------------------
    if summary.validation_report:
        logger.info("\nCross-framework mapping validation report:")
        print(summary.validation_report)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    logger.info(f"\n{'=' * 50}")
    logger.info(f"Ingestion complete.")
    logger.info(f"  Total: {summary.total_frameworks}")
    logger.info(f"  Succeeded: {len(summary.succeeded)} - {summary.succeeded}")
    if summary.failed:
        logger.warning(f"  Failed: {len(summary.failed)} - {summary.failed}")
    logger.info(f"{'=' * 50}")

    # Print detailed results
    if summary.results:
        logger.info("\nDetailed results:")
        for result in summary.results:
            if result.success:
                logger.info(f"  ✓ {result.framework_id}: {result.stats}")
            else:
                logger.error(f"  ✗ {result.framework_id}: {result.error}")

    return 1 if summary.failed else 0


if __name__ == "__main__":
    sys.exit(main())

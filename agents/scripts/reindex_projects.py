#!/usr/bin/env python3
"""
Script to delete and re-index projects in Qdrant with the correct document format.

This script will:
1. Delete existing project data from Qdrant
2. Re-index all projects with the correct format (nested metadata, proper page_content)

Usage:
    python reindex_projects.py --prefix qualys_
    python reindex_projects.py --prefix sentinel_
    python reindex_projects.py --prefix snyk_
    python reindex_projects.py --prefix wiz_
    python reindex_projects.py  # Re-index all projects
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add agents directory to path
agents_dir = Path(__file__).parent.parent
sys.path.insert(0, str(agents_dir))

from app.indexing.project_reader_qdrant import ingest_all_projects_from_sql_meta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Delete and re-index projects in Qdrant"
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default=None,
        help="Project name prefix to filter (e.g., 'qualys_', 'sentinel_', 'snyk_', 'wiz_'). If not provided, re-indexes all projects.",
    )
    parser.add_argument(
        "--base-path",
        type=str,
        default="../../data/sql_meta",
        help="Path to sql_meta directory (default: ../../data/sql_meta)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Qdrant host (default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=6333,
        help="Qdrant port (default: 6333)",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first error (default: continue with remaining projects)",
    )
    parser.add_argument(
        "--no-delete",
        action="store_true",
        help="Skip deletion step (only re-index, don't delete existing data)",
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("PROJECT RE-INDEXING SCRIPT")
    logger.info("=" * 80)
    logger.info(f"Base path: {args.base_path}")
    logger.info(f"Qdrant: {args.host or 'localhost'}:{args.port}")
    if args.prefix:
        logger.info(f"Project prefix filter: {args.prefix}")
    else:
        logger.info("Re-indexing ALL projects")
    logger.info(f"Delete existing: {not args.no_delete}")
    logger.info(f"Fail fast: {args.fail_fast}")
    logger.info("=" * 80)
    
    # Confirm before proceeding
    if not args.no_delete:
        response = input("\n⚠️  This will DELETE existing project data before re-indexing. Continue? (yes/no): ")
        if response.lower() != "yes":
            logger.info("Cancelled by user")
            return
    
    try:
        # Run the ingestion
        summary = await ingest_all_projects_from_sql_meta(
            base_path=args.base_path,
            project_name_prefix=args.prefix,
            delete_existing=not args.no_delete,
            fail_fast=args.fail_fast,
            host=args.host,
            port=args.port,
        )
        
        # Print final summary
        logger.info("\n" + "=" * 80)
        logger.info("RE-INDEXING SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total projects: {summary['total']}")
        logger.info(f"Succeeded: {len(summary['succeeded'])}")
        if summary['succeeded']:
            logger.info(f"  ✓ {', '.join(summary['succeeded'])}")
        
        if summary['failed']:
            logger.warning(f"Failed: {len(summary['failed'])}")
            logger.warning(f"  ✗ {', '.join(summary['failed'])}")
            logger.warning("\nErrors:")
            for project, error in summary['errors'].items():
                logger.warning(f"  {project}: {error}")
        else:
            logger.info("All projects re-indexed successfully! ✓")
        
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

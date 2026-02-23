"""
Script to re-run cross-framework mapping resolution for all ingested frameworks.

This is useful after the initial ingestion when some mappings were skipped because
target frameworks hadn't been ingested yet. After all frameworks are ingested,
run this script to create the previously skipped mappings.

Usage:
    python -m app.ingestion.resolve_mappings --data-dir /path/to/yamls
"""

import argparse
import logging
import sys
from pathlib import Path

from app.ingestion.service import IngestionService
from app.ingestion.frameworks import ADAPTER_REGISTRY
from app.ingestion.orchestrator import IngestionOrchestrator
from app.storage.sqlalchemy_session import get_session
from app.ingestion.models import Framework

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def resolve_mappings_for_all_frameworks(data_dir: Path) -> int:
    """
    Re-run cross-framework mapping resolution for all ingested frameworks.
    
    This will:
    1. Find all frameworks that exist in the database
    2. For each framework, reload its YAML files
    3. Re-run the cross-framework mapping resolution (which will now succeed
       since all frameworks exist)
    
    Returns:
        Number of frameworks processed
    """
    data_dir = Path(data_dir)
    
    # Map framework_id to directory name (same as in service.py)
    framework_dir_map = {
        "cis_v8_1": "cis_controls_v8_1",
        "hipaa": "hipaa",
        "soc2": "soc2",
        "nist_csf_2_0": "nist_csf_2_0",
        "iso27001": "iso27001_2022",
    }
    
    # Get all frameworks that exist in the database
    with get_session() as session:
        ingested_frameworks = session.query(Framework).all()
        framework_ids = [fw.id for fw in ingested_frameworks]
    
    if not framework_ids:
        logger.error("No frameworks found in database. Run ingestion first.")
        return 0
    
    logger.info(f"Found {len(framework_ids)} frameworks in database: {framework_ids}")
    logger.info("Re-running cross-framework mapping resolution...")
    
    orchestrator = IngestionOrchestrator()
    processed = 0
    
    for framework_id in framework_ids:
        if framework_id not in ADAPTER_REGISTRY:
            logger.warning(f"Skipping {framework_id}: not in adapter registry")
            continue
        
        framework_dir_name = framework_dir_map.get(framework_id)
        if not framework_dir_name:
            logger.warning(f"Skipping {framework_id}: no directory mapping")
            continue
        
        framework_data_dir = data_dir / framework_dir_name
        if not framework_data_dir.exists():
            logger.warning(f"Skipping {framework_id}: directory not found: {framework_data_dir}")
            continue
        
        logger.info(f"\n{'─' * 50}")
        logger.info(f"Processing: {framework_id}")
        logger.info(f"{'─' * 50}")
        
        try:
            # Load the framework bundle
            from app.ingestion.frameworks import get_adapter
            adapter = get_adapter(framework_id, str(framework_data_dir))
            bundle = adapter.load()
            
            if not bundle.controls:
                logger.warning(f"No controls found for {framework_id}, skipping mapping resolution")
                continue
            
            # Build control map (we need the postgres IDs)
            with get_session() as session:
                from app.ingestion.models import Control
                
                # Get all controls for this framework
                controls = session.query(Control).filter_by(framework_id=framework_id).all()
                control_map = {ctrl.control_code: ctrl.id for ctrl in controls}
                
                if not control_map:
                    logger.warning(f"No controls in database for {framework_id}, skipping")
                    continue
                
                # Re-run cross-framework mapping resolution
                orchestrator._resolve_cross_framework_mappings(
                    session, bundle, control_map
                )
                session.commit()
            
            processed += 1
            logger.info(f"✓ Completed mapping resolution for {framework_id}")
            
        except Exception as exc:
            logger.error(f"✗ Failed to process {framework_id}: {exc}", exc_info=True)
    
    logger.info(f"\n{'=' * 50}")
    logger.info(f"Mapping resolution complete.")
    logger.info(f"  Processed: {processed}/{len(framework_ids)} frameworks")
    logger.info(f"{'=' * 50}")
    
    return processed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Re-run cross-framework mapping resolution for all ingested frameworks"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        required=True,
        help="Directory containing framework YAML files (parent directory with framework subdirectories)",
    )
    
    args = parser.parse_args()
    
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        logger.error(f"Data directory not found: {data_dir}")
        return 1
    
    processed = resolve_mappings_for_all_frameworks(data_dir)
    
    if processed == 0:
        logger.error("No frameworks were processed. Check that frameworks are ingested.")
        return 1
    
    # Run validation to see the results
    logger.info("\n" + "=" * 50)
    logger.info("Running cross-framework mapping validation...")
    logger.info("=" * 50)
    
    try:
        from app.ingestion.frameworks.cross_framework import validate_cross_framework_mappings
        report = validate_cross_framework_mappings()
        logger.info("\nCross-framework mapping validation report:")
        print(report)
    except Exception as exc:
        logger.error(f"Validation failed: {exc}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

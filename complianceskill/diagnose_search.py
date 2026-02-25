"""
Diagnostic script to check why risk_control_mappings search returns 0 results.

This script checks:
1. If controls exist in the framework_controls Qdrant collection
2. If controls exist in the Postgres database
3. If risk-control relationships exist in the database
4. Sample some controls to see their structure
"""

import logging
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

def check_qdrant_collection():
    """Check if framework_controls collection has data."""
    try:
        from app.storage.qdrant_framework_store import (
            _get_underlying_qdrant_client,
            Collections
        )
        
        client = _get_underlying_qdrant_client()
        info = client.get_collection(Collections.CONTROLS)
        
        logger.info(f"✓ Collection '{Collections.CONTROLS}' exists")
        logger.info(f"  Points count: {info.points_count}")
        
        if info.points_count == 0:
            logger.error("  ✗ PROBLEM: Collection is EMPTY!")
            logger.error("  SOLUTION: You need to ingest the YAML files using:")
            logger.error("    python -m app.ingestion.ingest --data-dir <path_to_risk_control_yaml>")
            return False
        
        # Sample a few points
        logger.info(f"\n  Sampling {min(3, info.points_count)} points:")
        result, _ = client.scroll(
            collection_name=Collections.CONTROLS,
            limit=3,
            with_payload=True
        )
        
        for i, point in enumerate(result, 1):
            payload = point.payload
            logger.info(f"\n  Point {i}:")
            logger.info(f"    artifact_id: {payload.get('artifact_id')}")
            logger.info(f"    framework_id: {payload.get('framework_id')}")
            logger.info(f"    name: {payload.get('name', 'N/A')[:60]}...")
            logger.info(f"    domain: {payload.get('domain', 'N/A')}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Error checking Qdrant collection: {e}", exc_info=True)
        return False


def check_database():
    """Check if controls exist in Postgres database."""
    try:
        from app.storage.sqlalchemy_session import get_session
        from app.ingestion.models import Control, Risk, RiskControl, Framework
        
        with get_session() as session:
            # Check frameworks
            frameworks = session.query(Framework).all()
            logger.info(f"\n✓ Found {len(frameworks)} frameworks in database:")
            for fw in frameworks:
                logger.info(f"  - {fw.id}: {fw.name} {fw.version}")
            
            # Check controls
            control_count = session.query(Control).count()
            logger.info(f"\n✓ Found {control_count} controls in database")
            
            if control_count == 0:
                logger.error("  ✗ PROBLEM: No controls in database!")
                logger.error("  SOLUTION: You need to ingest the YAML files using:")
                logger.error("    python -m app.ingestion.ingest --data-dir <path_to_risk_control_yaml>")
                return False
            
            # Sample some controls
            sample_controls = session.query(Control).limit(3).all()
            logger.info(f"\n  Sample controls:")
            for ctrl in sample_controls:
                logger.info(f"    - {ctrl.id}: {ctrl.name[:60]}...")
                logger.info(f"      Framework: {ctrl.framework_id}")
                logger.info(f"      Domain: {ctrl.domain or 'N/A'}")
            
            # Check risks
            risk_count = session.query(Risk).count()
            logger.info(f"\n✓ Found {risk_count} risks in database")
            
            # Check risk-control relationships
            relationship_count = session.query(RiskControl).count()
            logger.info(f"\n✓ Found {relationship_count} risk-control relationships")
            
            if relationship_count == 0:
                logger.warning("  ⚠ WARNING: No risk-control relationships found!")
                logger.warning("  This means controls won't show associated risks in search results.")
                logger.warning("  Check that your YAML files have risk->control mappings.")
            
            # Sample some relationships
            if relationship_count > 0:
                sample_rels = session.query(RiskControl).limit(3).all()
                logger.info(f"\n  Sample relationships:")
                for rel in sample_rels:
                    risk = session.get(Risk, rel.risk_id)
                    control = session.get(Control, rel.control_id)
                    if risk and control:
                        logger.info(f"    - Risk '{risk.risk_code}' -> Control '{control.control_code}'")
            
            return True
            
    except Exception as e:
        logger.error(f"✗ Error checking database: {e}", exc_info=True)
        return False


def test_search():
    """Test the actual search to see what happens."""
    try:
        from app.retrieval import RetrievalService
        
        logger.info("\n" + "=" * 60)
        logger.info("Testing search_risk_control_mappings with 'access control'")
        logger.info("=" * 60)
        
        service = RetrievalService()
        context = service.search_risk_control_mappings(
            query="access control",
            limit=10,
            search_by="control"
        )
        
        logger.info(f"\nSearch results:")
        logger.info(f"  Total hits: {context.total_hits}")
        logger.info(f"  Controls found: {len(context.controls)}")
        logger.info(f"  Risks found: {len(context.risks)}")
        
        if context.total_hits == 0:
            logger.error("\n  ✗ PROBLEM: Search returned 0 results")
            logger.error("  This could mean:")
            logger.error("    1. No controls match 'access control' semantically")
            logger.error("    2. Controls exist but embeddings don't match")
            logger.error("    3. Collection is empty (check above)")
        else:
            logger.info(f"\n  ✓ Found {context.total_hits} results")
            for i, ctrl in enumerate(context.controls[:3], 1):
                logger.info(f"\n  Control {i}:")
                logger.info(f"    Name: {ctrl.name}")
                logger.info(f"    Code: {ctrl.control_code}")
                logger.info(f"    Framework: {ctrl.framework_name}")
                logger.info(f"    Mitigated Risks: {len(ctrl.mitigated_risks) if ctrl.mitigated_risks else 0}")
        
        return context.total_hits > 0
        
    except Exception as e:
        logger.error(f"✗ Error testing search: {e}", exc_info=True)
        return False


def main():
    logger.info("=" * 60)
    logger.info("DIAGNOSING RISK-CONTROL MAPPINGS SEARCH ISSUE")
    logger.info("=" * 60)
    
    results = {
        "qdrant": check_qdrant_collection(),
        "database": check_database(),
        "search": test_search(),
    }
    
    logger.info("\n" + "=" * 60)
    logger.info("DIAGNOSTIC SUMMARY")
    logger.info("=" * 60)
    
    for check, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"  {status}: {check}")
    
    if not all(results.values()):
        logger.error("\nISSUES FOUND:")
        if not results["qdrant"]:
            logger.error("  - Qdrant collection is empty or inaccessible")
        if not results["database"]:
            logger.error("  - Database is empty or inaccessible")
        if not results["search"]:
            logger.error("  - Search is not finding results")
        
        logger.error("\nSOLUTION:")
        logger.error("  Make sure you've ingested the YAML files using:")
        logger.error("    python -m app.ingestion.ingest --data-dir <path_to_risk_control_yaml>")
        logger.error("\n  The data directory should contain framework folders like:")
        logger.error("    - nist_csf_2_0/")
        logger.error("    - cis_controls_v8_1/")
        logger.error("    - hipaa/")
        logger.error("    - soc2/")
        logger.error("    - iso27001_2022/")
        return 1
    
    logger.info("\n✓ All checks passed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())

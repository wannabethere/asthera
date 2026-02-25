"""
Ingestion Service

High-level service that combines orchestrator, embedder, and storage operations
to provide a unified API for ingesting compliance frameworks.

This service:
1. Initializes database and Qdrant collections
2. Loads framework data from YAML files via adapters
3. Ingests data into both PostgreSQL and Qdrant
4. Validates cross-framework mappings
5. Provides status and error reporting
"""

import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from app.storage.sqlalchemy_session import (
    create_tables,
    check_connection as check_db_connection,
)
from app.storage.qdrant_framework_store import (
    initialize_collections,
    check_qdrant_connection,
)
from app.ingestion.frameworks import ADAPTER_REGISTRY, get_adapter
from app.ingestion.orchestrator import IngestionOrchestrator
from app.ingestion.embedder import EmbeddingService
from app.ingestion.frameworks.cross_framework import validate_cross_framework_mappings

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    """Result of ingesting a single framework."""
    framework_id: str
    success: bool
    error: Optional[str] = None
    stats: Dict[str, int] = field(default_factory=dict)


@dataclass
class IngestionSummary:
    """Summary of ingestion operation."""
    total_frameworks: int
    succeeded: List[str]
    failed: List[str]
    results: List[IngestionResult] = field(default_factory=list)
    validation_report: Optional[Any] = None


class IngestionService:
    """
    High-level service for ingesting compliance frameworks.
    
    Combines orchestrator, embedder, and storage operations into a unified API.
    
    Usage:
        service = IngestionService()
        summary = service.ingest_frameworks(
            data_dir="/path/to/yamls",
            framework_ids=["cis_v8_1", "hipaa"]
        )
    """
    
    def __init__(
        self,
        embedder: Optional[EmbeddingService] = None,
        skip_qdrant: bool = False,
    ):
        """
        Initialize the ingestion service.
        
        Args:
            embedder: Optional EmbeddingService instance. If None, creates a new one.
            skip_qdrant: If True, skip Qdrant operations (Postgres only).
        """
        self._embedder = embedder or EmbeddingService()
        self._skip_qdrant = skip_qdrant
        self._orchestrator = IngestionOrchestrator(embedder=self._embedder)
        
        if skip_qdrant:
            # Monkey-patch: disable Qdrant upserts
            import app.storage.qdrant_framework_store as qs
            qs.upsert_points = lambda collection, points, batch_size=100: (
                logger.debug(f"[skip-qdrant] Would upsert {len(points)} points to {collection}")
            )
    
    # ---------------------------------------------------------------------------
    # Initialization
    # ---------------------------------------------------------------------------
    
    def initialize_storage(
        self,
        recreate_qdrant: bool = False,
        check_connections: bool = True,
    ) -> bool:
        """
        Initialize database tables and Qdrant collections.
        
        Args:
            recreate_qdrant: If True, delete and recreate Qdrant collections.
            check_connections: If True, verify database and Qdrant connectivity.
            
        Returns:
            True if initialization succeeded, False otherwise.
        """
        if check_connections:
            logger.info("Checking database connection...")
            if not check_db_connection():
                logger.error("Cannot connect to database. Check configuration.")
                return False
            
            if not self._skip_qdrant:
                logger.info("Checking Qdrant connection...")
                if not check_qdrant_connection():
                    logger.error("Cannot connect to Qdrant. Check configuration.")
                    return False
        
        logger.info("Initializing database tables...")
        # Try to create tables - if it fails due to schema mismatch, 
        # user can drop tables manually or use --reinit-db flag
        create_tables(drop_existing=False)
        
        if not self._skip_qdrant:
            logger.info("Initializing Qdrant collections...")
            initialize_collections(recreate=recreate_qdrant)
        
        logger.info("Storage initialization complete.")
        return True
    
    # ---------------------------------------------------------------------------
    # Framework ingestion
    # ---------------------------------------------------------------------------
    
    def ingest_framework(
        self,
        framework_id: str,
        data_dir: Path,
    ) -> IngestionResult:
        """
        Ingest a single framework.
        
        Args:
            framework_id: Framework ID (must be in ADAPTER_REGISTRY)
            data_dir: Directory containing framework YAML files (parent directory with framework subdirectories)
            
        Returns:
            IngestionResult with success status and stats
        """
        logger.info(f"Ingesting framework: {framework_id}")
        
        try:
            # Map framework_id to directory name
            # The YAML files are organized in subdirectories by framework name
            framework_dir_map = {
                "cis_v8_1": "cis_controls_v8_1",
                "hipaa": "hipaa",
                "soc2": "soc2",
                "nist_csf_2_0": "nist_csf_2_0",
                "iso27001": "iso27001_2022",  # Default to 2022 version
            }
            
            framework_dir_name = framework_dir_map.get(framework_id)
            if not framework_dir_name:
                return IngestionResult(
                    framework_id=framework_id,
                    success=False,
                    error=f"No directory mapping found for framework_id '{framework_id}'. Available: {list(framework_dir_map.keys())}",
                )
            
            # Construct path to framework-specific subdirectory
            framework_data_dir = data_dir / framework_dir_name
            if not framework_data_dir.exists():
                return IngestionResult(
                    framework_id=framework_id,
                    success=False,
                    error=f"Framework directory not found: {framework_data_dir}. Check that the YAML files are organized in subdirectories.",
                )
            
            # Get adapter and load data
            adapter = get_adapter(framework_id, str(framework_data_dir))
            bundle = adapter.load()
            
            # Check if bundle is empty
            if (
                not bundle.controls
                and not bundle.requirements
                and not bundle.risks
                and not bundle.scenarios
                and not bundle.test_cases
            ):
                return IngestionResult(
                    framework_id=framework_id,
                    success=False,
                    error=f"Adapter produced empty bundle. Check YAML files in {framework_data_dir}. Expected files like controls_*.yaml, *_risk_controls.yaml, etc.",
                )
            
            # Ingest via orchestrator
            self._orchestrator.ingest(bundle)
            
            # Collect stats
            stats = {
                "controls": len(bundle.controls),
                "requirements": len(bundle.requirements),
                "risks": len(bundle.risks),
                "scenarios": len(bundle.scenarios),
                "test_cases": len(bundle.test_cases),
            }
            
            logger.info(f"✓ {framework_id} ingested successfully: {stats}")
            return IngestionResult(
                framework_id=framework_id,
                success=True,
                stats=stats,
            )
            
        except Exception as exc:
            logger.error(f"✗ {framework_id} ingestion failed: {exc}", exc_info=True)
            return IngestionResult(
                framework_id=framework_id,
                success=False,
                error=str(exc),
            )
    
    def ingest_frameworks(
        self,
        data_dir: Path,
        framework_ids: Optional[List[str]] = None,
        fail_fast: bool = True,
        validate_mappings: bool = True,
    ) -> IngestionSummary:
        """
        Ingest multiple frameworks.
        
        Args:
            data_dir: Parent directory containing framework subdirectories (e.g., 
                     risk_control_yaml/ with subdirs like cis_controls_v8_1/, hipaa/, etc.)
            framework_ids: List of framework IDs to ingest. If None, ingests all registered.
            fail_fast: If True, stop on first failure. If False, continue with remaining.
            validate_mappings: If True, run cross-framework mapping validation after ingestion.
            
        Returns:
            IngestionSummary with results for all frameworks
        """
        frameworks_to_ingest = framework_ids or list(ADAPTER_REGISTRY.keys())
        data_dir = Path(data_dir)
        
        logger.info(f"Starting ingestion of {len(frameworks_to_ingest)} frameworks")
        logger.info(f"Data directory: {data_dir.resolve()}")
        
        results: List[IngestionResult] = []
        failed: List[str] = []
        
        for fw_id in frameworks_to_ingest:
            logger.info(f"\n{'─' * 50}")
            logger.info(f"Ingesting: {fw_id}")
            logger.info(f"{'─' * 50}")
            
            result = self.ingest_framework(fw_id, data_dir)
            results.append(result)
            
            if not result.success:
                failed.append(fw_id)
                if fail_fast:
                    logger.error("Stopping due to failure (fail_fast=True)")
                    break
        
        # Cross-framework mapping validation
        validation_report = None
        if validate_mappings and not failed:
            logger.info(f"\n{'─' * 50}")
            logger.info("Running cross-framework mapping validation...")
            logger.info(f"{'─' * 50}")
            try:
                validation_report = validate_cross_framework_mappings()
                logger.info("Validation complete.")
            except Exception as exc:
                logger.error(f"Validation failed: {exc}", exc_info=True)
        
        succeeded = [r.framework_id for r in results if r.success]
        
        summary = IngestionSummary(
            total_frameworks=len(frameworks_to_ingest),
            succeeded=succeeded,
            failed=failed,
            results=results,
            validation_report=validation_report,
        )
        
        logger.info(f"\n{'=' * 50}")
        logger.info(f"Ingestion complete.")
        logger.info(f"  Total: {summary.total_frameworks}")
        logger.info(f"  Succeeded: {len(succeeded)}")
        if failed:
            logger.warning(f"  Failed: {len(failed)}")
        logger.info(f"{'=' * 50}")
        
        return summary
    
    # ---------------------------------------------------------------------------
    # Utility methods
    # ---------------------------------------------------------------------------
    
    @staticmethod
    def get_available_frameworks() -> List[str]:
        """Get list of all available framework IDs."""
        return list(ADAPTER_REGISTRY.keys())
    
    def get_framework_stats(self, framework_id: str) -> Optional[Dict[str, int]]:
        """
        Get statistics for an ingested framework.
        
        Args:
            framework_id: Framework ID
            
        Returns:
            Dictionary with counts per artifact type, or None if framework not found
        """
        from app.storage.sqlalchemy_session import get_session
        from app.ingestion.models import Framework, Control, Requirement, Risk, Scenario, TestCase
        
        try:
            with get_session() as session:
                framework = session.get(Framework, framework_id)
                if not framework:
                    return None
                
                return {
                    "controls": session.query(Control).filter_by(framework_id=framework_id).count(),
                    "requirements": session.query(Requirement).filter_by(framework_id=framework_id).count(),
                    "risks": session.query(Risk).filter_by(framework_id=framework_id).count(),
                    "scenarios": session.query(Scenario).filter_by(framework_id=framework_id).count(),
                    "test_cases": session.query(TestCase).filter_by(framework_id=framework_id).count(),
                }
        except Exception as exc:
            logger.error(f"Failed to get stats for {framework_id}: {exc}")
            return None
    
    def list_frameworks(self) -> List[Dict[str, Any]]:
        """
        List all ingested frameworks.
        
        Returns:
            List of dictionaries with framework information
        """
        from app.storage.sqlalchemy_session import get_session
        from app.ingestion.models import Framework
        
        try:
            with get_session() as session:
                frameworks = session.query(Framework).all()
                return [
                    {
                        "id": fw.id,
                        "name": fw.name,
                        "version": fw.version,
                        "description": fw.description,
                    }
                    for fw in frameworks
                ]
        except Exception as exc:
            logger.error(f"Failed to list frameworks: {exc}")
            return []

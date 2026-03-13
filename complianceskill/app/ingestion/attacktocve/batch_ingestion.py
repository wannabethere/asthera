"""
Batch Framework Ingestion
=========================
Ingests risk scenarios from all compliance frameworks into the vector store.

Supports:
- All frameworks in risk_control_yaml directory
- Checkpointing for resumable ingestion
- Background execution
- Progress tracking
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.dependencies import get_settings
from app.core.settings import get_settings as _get_settings

try:
    from .framework_helper import list_frameworks, find_framework_yaml, get_framework_path
    from .control_loader import load_cis_scenarios
    from .framework_loaders import (
        load_framework_controls, load_framework_requirements, load_framework_risks,
        load_all_framework_data
    )
    from .vectorstore_retrieval import (
        VectorStoreConfig, VectorBackend, ingest_cis_scenarios, ingest_framework_documents
    )
    from .persistence.checkpoint_manager import CheckpointManager
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))
    from app.ingestion.attacktocve.framework_helper import list_frameworks, find_framework_yaml, get_framework_path
    from app.ingestion.attacktocve.control_loader import load_cis_scenarios
    from app.ingestion.attacktocve.framework_loaders import (
        load_framework_controls, load_framework_requirements, load_framework_risks,
        load_all_framework_data
    )
    from app.ingestion.attacktocve.vectorstore_retrieval import (
        VectorStoreConfig, VectorBackend, ingest_cis_scenarios, ingest_framework_documents
    )
    from app.ingestion.attacktocve.persistence.checkpoint_manager import CheckpointManager

logger = logging.getLogger(__name__)


@dataclass
class FrameworkIngestionResult:
    """Result of ingesting a single framework."""
    framework: str
    framework_name: str
    scenarios_loaded: int = 0
    scenarios_ingested: int = 0
    controls_loaded: int = 0
    controls_ingested: int = 0
    requirements_loaded: int = 0
    requirements_ingested: int = 0
    risks_loaded: int = 0
    risks_ingested: int = 0
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    collections_used: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "framework": self.framework,
            "framework_name": self.framework_name,
            "scenarios_loaded": self.scenarios_loaded,
            "scenarios_ingested": self.scenarios_ingested,
            "controls_loaded": self.controls_loaded,
            "controls_ingested": self.controls_ingested,
            "requirements_loaded": self.requirements_loaded,
            "requirements_ingested": self.requirements_ingested,
            "risks_loaded": self.risks_loaded,
            "risks_ingested": self.risks_ingested,
            "errors": self.errors,
            "duration_seconds": round(self.duration_seconds, 2),
            "collections_used": self.collections_used,
        }


@dataclass
class BatchIngestionReport:
    """Report for batch ingestion of all frameworks."""
    total_frameworks: int = 0
    successful_frameworks: int = 0
    failed_frameworks: int = 0
    total_scenarios_ingested: int = 0
    total_controls_ingested: int = 0
    total_requirements_ingested: int = 0
    total_risks_ingested: int = 0
    framework_results: List[Dict[str, Any]] = field(default_factory=list)
    total_duration_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": {
                "total_frameworks": self.total_frameworks,
                "successful_frameworks": self.successful_frameworks,
                "failed_frameworks": self.failed_frameworks,
                "total_scenarios_ingested": self.total_scenarios_ingested,
                "total_controls_ingested": self.total_controls_ingested,
                "total_requirements_ingested": self.total_requirements_ingested,
                "total_risks_ingested": self.total_risks_ingested,
                "total_duration_seconds": round(self.total_duration_seconds, 1),
            },
            "framework_results": self.framework_results,
        }


class BatchFrameworkIngester:
    """Ingests scenarios from all frameworks into vector store."""
    
    def __init__(
        self,
        checkpoint_dir: Optional[str] = None,
        resume: bool = True,
        collection_prefix: Optional[str] = None,
    ):
        """
        Initialize batch ingester.
        
        Args:
            checkpoint_dir: Directory for checkpoint files
            resume: Whether to resume from checkpoint
            collection_prefix: Optional prefix for collection names (e.g., "framework_")
        """
        self.settings = _get_settings()
        self.resume = resume
        self.collection_prefix = collection_prefix or ""
        
        # Initialize checkpoint manager
        if checkpoint_dir:
            self.checkpoint_manager = CheckpointManager(checkpoint_dir)
        else:
            checkpoint_base = Path(".checkpoints") / "batch_ingestion"
            self.checkpoint_manager = CheckpointManager(checkpoint_base)
        
        # Load checkpoint state
        self.processed_frameworks: set = set()
        if resume and self.checkpoint_manager.has_checkpoint():
            checkpoint_state = self.checkpoint_manager.state
            if checkpoint_state.get("type") == "batch_ingestion":
                self.processed_frameworks = set(checkpoint_state.get("processed_frameworks", []))
                logger.info(
                    f"📂 Resuming batch ingestion: {len(self.processed_frameworks)} frameworks already processed"
                )
        
        # Build vector store config
        self.vs_config = self._build_vector_store_config()
        
        logger.info(
            f"[BatchFrameworkIngester] Checkpointing: enabled | "
            f"Resume: {resume} ({len(self.processed_frameworks)} already processed)"
        )
    
    def _build_vector_store_config(self) -> VectorStoreConfig:
        """Build VectorStoreConfig from centralized settings."""
        return VectorStoreConfig.from_settings()
    
    def ingest_framework(
        self,
        framework: str,
        collection_name: Optional[str] = None,
    ) -> FrameworkIngestionResult:
        """
        Ingest all data types (scenarios, controls, requirements, risks) from a single framework.
        
        Args:
            framework: Framework identifier
            collection_name: Optional collection name (ignored - uses FrameworkCollections)
            
        Returns:
            FrameworkIngestionResult
        """
        import time
        start = time.time()
        
        result = FrameworkIngestionResult(
            framework=framework,
            framework_name=framework.replace("_", " ").title(),
        )
        
        try:
            from app.storage.collections import FrameworkCollections
            
            # Load all framework data
            logger.info(f"Loading all data for framework: {framework}")
            framework_data = load_all_framework_data(framework)
            
            # Get framework name for metadata
            from .framework_helper import get_framework_info
            try:
                framework_info = get_framework_info(framework)
                framework_name = framework_info.get("name", framework.replace("_", " ").title())
            except:
                framework_name = framework.replace("_", " ").title()
            
            # Ingest scenarios
            if framework_data["scenarios"]:
                result.scenarios_loaded = len(framework_data["scenarios"])
                scenarios_config = VectorStoreConfig(
                    backend=self.vs_config.backend,
                    collection=FrameworkCollections.SCENARIOS,
                    qdrant_url=self.vs_config.qdrant_url,
                    qdrant_api_key=self.vs_config.qdrant_api_key,
                    chroma_persist_dir=self.vs_config.chroma_persist_dir,
                    chroma_host=self.vs_config.chroma_host,
                    chroma_port=self.vs_config.chroma_port,
                    openai_api_key=self.vs_config.openai_api_key,
                    embedding_model=self.vs_config.embedding_model,
                )
                
                scenario_dicts = [s.model_dump() for s in framework_data["scenarios"]]
                for s in scenario_dicts:
                    s["framework"] = framework
                
                logger.info(f"Ingesting {len(scenario_dicts)} scenarios from {framework}")
                result.scenarios_ingested = ingest_cis_scenarios(scenario_dicts, scenarios_config)
                result.collections_used.append(FrameworkCollections.SCENARIOS)
            
            # Ingest controls
            if framework_data["controls"]:
                result.controls_loaded = len(framework_data["controls"])
                controls_config = VectorStoreConfig(
                    backend=self.vs_config.backend,
                    collection=FrameworkCollections.CONTROLS,
                    qdrant_url=self.vs_config.qdrant_url,
                    qdrant_api_key=self.vs_config.qdrant_api_key,
                    chroma_persist_dir=self.vs_config.chroma_persist_dir,
                    chroma_host=self.vs_config.chroma_host,
                    chroma_port=self.vs_config.chroma_port,
                    openai_api_key=self.vs_config.openai_api_key,
                    embedding_model=self.vs_config.embedding_model,
                )
                
                control_dicts = [c.model_dump() for c in framework_data["controls"]]
                for c in control_dicts:
                    c["framework"] = framework
                
                logger.info(f"Ingesting {len(control_dicts)} controls from {framework}")
                result.controls_ingested = ingest_framework_documents(
                    control_dicts, controls_config, document_type="controls"
                )
                result.collections_used.append(FrameworkCollections.CONTROLS)
            
            # Ingest requirements
            if framework_data["requirements"]:
                result.requirements_loaded = len(framework_data["requirements"])
                requirements_config = VectorStoreConfig(
                    backend=self.vs_config.backend,
                    collection=FrameworkCollections.REQUIREMENTS,
                    qdrant_url=self.vs_config.qdrant_url,
                    qdrant_api_key=self.vs_config.qdrant_api_key,
                    chroma_persist_dir=self.vs_config.chroma_persist_dir,
                    chroma_host=self.vs_config.chroma_host,
                    chroma_port=self.vs_config.chroma_port,
                    openai_api_key=self.vs_config.openai_api_key,
                    embedding_model=self.vs_config.embedding_model,
                )
                
                requirement_dicts = [r.model_dump() for r in framework_data["requirements"]]
                for r in requirement_dicts:
                    r["framework"] = framework
                
                logger.info(f"Ingesting {len(requirement_dicts)} requirements from {framework}")
                result.requirements_ingested = ingest_framework_documents(
                    requirement_dicts, requirements_config, document_type="requirements"
                )
                result.collections_used.append(FrameworkCollections.REQUIREMENTS)
            
            # Ingest risks (if different from scenarios)
            if framework_data["risks"]:
                result.risks_loaded = len(framework_data["risks"])
                risks_config = VectorStoreConfig(
                    backend=self.vs_config.backend,
                    collection=FrameworkCollections.RISKS,
                    qdrant_url=self.vs_config.qdrant_url,
                    qdrant_api_key=self.vs_config.qdrant_api_key,
                    chroma_persist_dir=self.vs_config.chroma_persist_dir,
                    chroma_host=self.vs_config.chroma_host,
                    chroma_port=self.vs_config.chroma_port,
                    openai_api_key=self.vs_config.openai_api_key,
                    embedding_model=self.vs_config.embedding_model,
                )
                
                risk_dicts = [r.model_dump() for r in framework_data["risks"]]
                for r in risk_dicts:
                    r["framework"] = framework
                
                logger.info(f"Ingesting {len(risk_dicts)} risks from {framework}")
                result.risks_ingested = ingest_framework_documents(
                    risk_dicts, risks_config, document_type="risks"
                )
                result.collections_used.append(FrameworkCollections.RISKS)
            
            result.duration_seconds = time.time() - start
            
            total_ingested = (
                result.scenarios_ingested + result.controls_ingested +
                result.requirements_ingested + result.risks_ingested
            )
            logger.info(
                f"✅ {framework}: {total_ingested} documents ingested "
                f"(scenarios: {result.scenarios_ingested}, controls: {result.controls_ingested}, "
                f"requirements: {result.requirements_ingested}, risks: {result.risks_ingested}) "
                f"({result.duration_seconds:.1f}s)"
            )
            
        except Exception as e:
            logger.error(f"❌ Failed to ingest {framework}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            result.errors.append(str(e))
            result.duration_seconds = time.time() - start
        
        return result
    
    def ingest_all_frameworks(
        self,
        frameworks: Optional[List[str]] = None,
        skip_frameworks: Optional[List[str]] = None,
    ) -> BatchIngestionReport:
        """
        Ingest scenarios from all frameworks.
        
        Args:
            frameworks: Optional list of frameworks to ingest (defaults to all)
            skip_frameworks: Optional list of frameworks to skip
            
        Returns:
            BatchIngestionReport
        """
        if frameworks is None:
            frameworks = list_frameworks()
        
        if skip_frameworks:
            frameworks = [f for f in frameworks if f not in skip_frameworks]
        
        report = BatchIngestionReport(total_frameworks=len(frameworks))
        all_results = self.checkpoint_manager.get_results() if self.resume else []
        
        import time
        total_start = time.time()
        
        for i, framework in enumerate(frameworks, 1):
            # Skip if already processed (when resuming)
            if framework in self.processed_frameworks:
                logger.info(f"[{i}/{len(frameworks)}] ⏭️  Skipping {framework} (already processed)")
                # Find existing result
                existing_result = next(
                    (r for r in all_results if r.get("framework") == framework),
                    None
                )
                if existing_result:
                    report.framework_results.append(existing_result)
                    report.total_scenarios_ingested += existing_result.get("scenarios_ingested", 0)
                    report.total_controls_ingested += existing_result.get("controls_ingested", 0)
                    report.total_requirements_ingested += existing_result.get("requirements_ingested", 0)
                    report.total_risks_ingested += existing_result.get("risks_ingested", 0)
                    if not existing_result.get("errors"):
                        report.successful_frameworks += 1
                    else:
                        report.failed_frameworks += 1
                continue
            
            logger.info(f"[{i}/{len(frameworks)}] Processing {framework}...")
            
            # Ingest framework
            result = self.ingest_framework(framework)
            result_dict = result.to_dict()
            report.framework_results.append(result_dict)
            all_results.append(result_dict)
            
            # Update report
            if result.errors:
                report.failed_frameworks += 1
            else:
                report.successful_frameworks += 1
            report.total_scenarios_ingested += result.scenarios_ingested
            report.total_controls_ingested += result.controls_ingested
            report.total_requirements_ingested += result.requirements_ingested
            report.total_risks_ingested += result.risks_ingested
            
            # Save checkpoint after each framework
            self.processed_frameworks.add(framework)
            self._save_checkpoint(all_results, len(frameworks))
        
        report.total_duration_seconds = time.time() - total_start
        return report
    
    def _save_checkpoint(
        self,
        results: List[Dict[str, Any]],
        total_frameworks: int,
    ) -> None:
        """Save checkpoint after processing frameworks."""
        self.checkpoint_manager.save_checkpoint(
            framework="batch_ingestion",
            processed_scenarios=list(self.processed_frameworks),  # Reusing field name
            total_scenarios=total_frameworks,  # Reusing field name
            results=results,
            registry_state={},  # Not needed for ingestion
            metadata={
                "type": "batch_ingestion",
                "processed_frameworks": list(self.processed_frameworks),
            },
        )
    
    def export_report(
        self,
        report: BatchIngestionReport,
        output_file: Optional[str] = None,
    ) -> Path:
        """Export ingestion report to JSON file."""
        if output_file:
            report_file = Path(output_file)
        else:
            report_file = self.checkpoint_manager.checkpoint_dir / "ingestion_report.json"
        
        report_file.write_text(
            json.dumps(report.to_dict(), indent=2),
            encoding="utf-8"
        )
        logger.info(f"📄 Ingestion report exported to: {report_file}")
        return report_file
    
    def print_summary(self, report: BatchIngestionReport) -> None:
        """Print summary of batch ingestion."""
        print("\n" + "=" * 60)
        print("Batch Framework Ingestion Summary")
        print("=" * 60)
        print(f"Total frameworks: {report.total_frameworks}")
        print(f"Successful: {report.successful_frameworks}")
        print(f"Failed: {report.failed_frameworks}")
        print(f"\nDocuments Ingested:")
        print(f"  Scenarios: {report.total_scenarios_ingested}")
        print(f"  Controls: {report.total_controls_ingested}")
        print(f"  Requirements: {report.total_requirements_ingested}")
        print(f"  Risks: {report.total_risks_ingested}")
        print(f"\nTotal duration: {report.total_duration_seconds:.1f}s")
        print("=" * 60)
        
        if report.framework_results:
            print("\nFramework Results:")
            for result in report.framework_results:
                status = "✅" if not result.get("errors") else "❌"
                print(
                    f"  {status} {result['framework']:20s} | "
                    f"Scenarios: {result.get('scenarios_ingested', 0):4d} | "
                    f"Controls: {result.get('controls_ingested', 0):4d} | "
                    f"Requirements: {result.get('requirements_ingested', 0):4d} | "
                    f"Risks: {result.get('risks_ingested', 0):4d}"
                )
                if result.get("collections_used"):
                    print(f"    Collections: {', '.join(result['collections_used'])}")
        print("=" * 60 + "\n")


async def ingest_all_frameworks_async(
    checkpoint_dir: Optional[str] = None,
    resume: bool = True,
    frameworks: Optional[List[str]] = None,
    skip_frameworks: Optional[List[str]] = None,
    collection_prefix: Optional[str] = None,
) -> BatchIngestionReport:
    """
    Async wrapper for batch framework ingestion.
    
    Args:
        checkpoint_dir: Directory for checkpoint files
        resume: Whether to resume from checkpoint
        frameworks: Optional list of frameworks to ingest
        skip_frameworks: Optional list of frameworks to skip
        collection_prefix: Optional prefix for collection names
        
    Returns:
        BatchIngestionReport
    """
    ingester = BatchFrameworkIngester(
        checkpoint_dir=checkpoint_dir,
        resume=resume,
        collection_prefix=collection_prefix,
    )
    
    # Run in executor to avoid blocking
    loop = asyncio.get_event_loop()
    report = await loop.run_in_executor(
        None,
        ingester.ingest_all_frameworks,
        frameworks,
        skip_frameworks,
    )
    
    return report

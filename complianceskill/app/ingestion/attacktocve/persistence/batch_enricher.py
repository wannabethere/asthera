"""
Batch Enrichment Orchestrator
==============================
Enriches ALL risk scenarios in the YAML with mapped ATT&CK techniques.
Supports multiple compliance frameworks (CIS, NIST, HIPAA, SOC2, ISO27001).

Strategy
--------
1. Load all scenarios from YAML (supports multiple frameworks).
2. For each scenario, call the reverse mapper → get candidate technique IDs.
3. For each candidate technique, run the forward LangGraph pipeline
   (enrich_attack → retrieve → map_controls → validate → output).
4. Merge all mappings back into the registry.
5. Export the enriched YAML and a JSON coverage report.
6. Optionally generate previews and ingest into vector store.

Two processing modes:
  - sequential   : safe for rate-limited OpenAI accounts
  - concurrent   : uses asyncio + semaphore for throughput (default: 4 workers)

Usage
-----
    python main.py --batch-enrich \
        --framework cis_controls_v8_1 \
        --output enriched_controls.yaml \
        --report coverage_report.json \
        --workers 4 \
        --preview-dir ./previews
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Handle both relative imports (when run as module) and absolute imports (when run as script)
try:
    from app.core.settings import get_settings as _get_settings
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))
    from app.core.settings import get_settings as _get_settings

try:
    from .reverse_mapper import ScenarioToTechniqueMapper, TechniqueSuggestion
    from .checkpoint_manager import CheckpointManager
    from ..control_loader import CISControlRegistry, CISRiskScenario, load_cis_scenarios
    from ..graph import build_graph, run_mapping
    from ..state import ControlMapping
    from ..vectorstore_retrieval import VectorStoreConfig, VectorBackend
    from ..preview_generator import PreviewGenerator
except ImportError:
    # Fallback for when run as script
    from app.ingestion.attacktocve.persistence.reverse_mapper import ScenarioToTechniqueMapper, TechniqueSuggestion
    from app.ingestion.attacktocve.persistence.checkpoint_manager import CheckpointManager
    from app.ingestion.attacktocve.control_loader import CISControlRegistry, CISRiskScenario, load_cis_scenarios
    from app.ingestion.attacktocve.graph import build_graph, run_mapping
    from app.ingestion.attacktocve.state import ControlMapping
    from app.ingestion.attacktocve.vectorstore_retrieval import VectorStoreConfig, VectorBackend
    from app.ingestion.attacktocve.preview_generator import PreviewGenerator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-scenario result
# ---------------------------------------------------------------------------

@dataclass
class ScenarioEnrichmentResult:
    scenario_id: str
    scenario_name: str
    suggested_techniques: List[TechniqueSuggestion] = field(default_factory=list)
    confirmed_mappings: List[ControlMapping] = field(default_factory=list)
    skipped_techniques: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def technique_ids(self) -> List[str]:
        return [m.technique_id for m in self.confirmed_mappings]

    @property
    def avg_confidence(self) -> str:
        if not self.confirmed_mappings:
            return "none"
        scores = {"high": 3, "medium": 2, "low": 1}
        avg = sum(scores.get(m.confidence, 1) for m in self.confirmed_mappings) / len(
            self.confirmed_mappings
        )
        return "high" if avg >= 2.5 else "medium" if avg >= 1.5 else "low"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "technique_count": len(self.confirmed_mappings),
            "techniques": self.technique_ids,
            "avg_confidence": self.avg_confidence,
            "skipped": self.skipped_techniques,
            "errors": self.errors,
            "duration_seconds": round(self.duration_seconds, 2),
        }


# ---------------------------------------------------------------------------
# Coverage report
# ---------------------------------------------------------------------------

@dataclass
class CoverageReport:
    total_scenarios: int = 0
    enriched_scenarios: int = 0
    total_mappings: int = 0
    unique_techniques: int = 0
    asset_coverage: Dict[str, int] = field(default_factory=dict)
    technique_frequency: Dict[str, int] = field(default_factory=dict)
    confidence_distribution: Dict[str, int] = field(default_factory=dict)
    scenario_results: List[Dict[str, Any]] = field(default_factory=list)
    total_duration_seconds: float = 0.0
    framework: str = ""

    @property
    def coverage_pct(self) -> float:
        return round(self.enriched_scenarios / self.total_scenarios * 100, 1) if self.total_scenarios else 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "framework": self.framework,
            "summary": {
                "total_scenarios": self.total_scenarios,
                "enriched_scenarios": self.enriched_scenarios,
                "coverage_pct": self.coverage_pct,
                "total_mappings": self.total_mappings,
                "unique_techniques_mapped": self.unique_techniques,
                "total_duration_seconds": round(self.total_duration_seconds, 1),
            },
            "asset_coverage": self.asset_coverage,
            "top_techniques": dict(
                sorted(self.technique_frequency.items(), key=lambda x: -x[1])[:20]
            ),
            "confidence_distribution": self.confidence_distribution,
            "scenario_results": self.scenario_results,
        }


# ---------------------------------------------------------------------------
# Core enricher
# ---------------------------------------------------------------------------

class BatchEnricher:
    """
    Orchestrates end-to-end enrichment of all risk scenarios.
    
    For each scenario:
      1. Reverse-map → candidate ATT&CK T-numbers
      2. Forward-map each T-number through the LangGraph pipeline
      3. Accumulate all ControlMapping objects onto the scenario
    """

    def __init__(
        self,
        yaml_path: str,
        framework: str = "cis_controls_v8_1",
        max_techniques_per_scenario: int = 5,
        relevance_threshold: float = 0.55,
        skip_existing: bool = True,
        use_preview: bool = False,
        preview_dir: Optional[str] = None,
        checkpoint_dir: Optional[str] = None,
        resume: bool = True,
    ):
        self.yaml_path = yaml_path
        self.framework = framework
        self.max_techniques = max_techniques_per_scenario
        self.relevance_threshold = relevance_threshold
        self.skip_existing = skip_existing
        self.use_preview = use_preview
        self.preview_dir = Path(preview_dir) if preview_dir else None
        self.resume = resume
        
        # Get settings
        self.settings = _get_settings()
        
        # Initialize checkpoint manager
        if checkpoint_dir:
            self.checkpoint_manager = CheckpointManager(checkpoint_dir)
        else:
            # Default checkpoint directory
            checkpoint_base = Path(yaml_path).parent / ".checkpoints" / framework
            self.checkpoint_manager = CheckpointManager(checkpoint_base)
        
        # Load checkpoint if resuming
        self.processed_scenarios: set = set()
        if resume and self.checkpoint_manager.has_checkpoint():
            checkpoint_state = self.checkpoint_manager.state
            if checkpoint_state.get("framework") == framework:
                self.processed_scenarios = self.checkpoint_manager.get_processed_scenarios()
                logger.info(
                    f"📂 Resuming from checkpoint: {len(self.processed_scenarios)} scenarios already processed"
                )
            else:
                logger.warning(
                    f"⚠️  Checkpoint framework mismatch: "
                    f"expected {framework}, found {checkpoint_state.get('framework')}. Starting fresh."
                )
                self.processed_scenarios = set()
        
        # Build vector store config from centralized settings
        self.vs_config = self._build_vector_store_config()

        # Load scenarios - prefer scenarios_*.yaml, fallback to *_risk_controls.yaml
        # This ensures we use the correct file for each framework
        from ..framework_helper import find_framework_yaml
        scenario_file = find_framework_yaml(framework, file_type="scenarios")
        if not scenario_file:
            scenario_file = find_framework_yaml(framework, file_type="risk_controls")
        
        # Use the found scenario file if it exists, otherwise use provided yaml_path
        if scenario_file and scenario_file.exists():
            logger.info(f"Using scenario file: {scenario_file} for framework {framework}")
            actual_yaml_path = str(scenario_file)
            self.scenarios = load_cis_scenarios(scenario_file)
        else:
            logger.info(f"Using provided YAML path: {yaml_path} for framework {framework}")
            actual_yaml_path = yaml_path
            self.scenarios = load_cis_scenarios(yaml_path)
        
        # Store the actual YAML path used for graph building
        self.actual_yaml_path = actual_yaml_path
        
        self.registry = CISControlRegistry(self.scenarios)
        
        # Restore registry state from checkpoint if resuming
        if resume and self.checkpoint_manager.has_checkpoint():
            registry_state = self.checkpoint_manager.get_registry_state()
            if registry_state:
                # Restore controls from checkpoint
                for scenario_id, controls in registry_state.get("controls", {}).items():
                    self.registry.update_controls(scenario_id, controls)
                logger.info(f"📂 Restored registry state from checkpoint")
        
        self.reverse_mapper = ScenarioToTechniqueMapper(validate_ids=True)
        # Use the actual YAML path that was loaded
        self.graph = build_graph(self.vs_config, yaml_path=actual_yaml_path, framework_id=framework)
        
        # Preview generator if enabled
        self.preview_generator = None
        if use_preview and preview_dir:
            self.preview_generator = PreviewGenerator(
                preview_dir=preview_dir,
                yaml_path=yaml_path,
                use_vector_store=True,
            )

        logger.info(
            f"[BatchEnricher] Framework: {framework} | "
            f"Loaded {len(self.scenarios)} scenarios | "
            f"Backend: {self.vs_config.backend} | "
            f"Max techniques/scenario: {max_techniques_per_scenario} | "
            f"Preview mode: {use_preview} | "
            f"Checkpointing: enabled | "
            f"Resume: {resume} ({len(self.processed_scenarios)} already processed)"
        )

    def _build_vector_store_config(self) -> VectorStoreConfig:
        """Build VectorStoreConfig from centralized settings."""
        # Use unified framework_scenarios collection
        try:
            from app.storage.collections import FrameworkCollections
            collection_name = FrameworkCollections.SCENARIOS
        except ImportError:
            # Fallback if collections.py not available
            collection_name = "framework_scenarios"
        
        return VectorStoreConfig.from_settings(collection=collection_name)

    # ------------------------------------------------------------------
    # Public: run all
    # ------------------------------------------------------------------

    def run(
        self,
        asset_filter: Optional[str] = None,
        max_scenarios: Optional[int] = None,
        workers: int = 1,
    ) -> CoverageReport:
        """
        Enrich all (or filtered) scenarios.

        Args:
            asset_filter  : Only process scenarios in this asset domain.
            max_scenarios : Cap the run (useful for testing).
            workers       : Async concurrency level (1 = sequential).
        """
        scenarios = self.scenarios
        if asset_filter:
            scenarios = [s for s in scenarios if asset_filter.lower() in s.asset.lower()]
        if max_scenarios:
            scenarios = scenarios[:max_scenarios]

        logger.info(f"[BatchEnricher] Processing {len(scenarios)} scenarios (workers={workers})")

        if workers > 1:
            results = asyncio.run(self._run_concurrent(scenarios, workers))
        else:
            results = self._run_sequential(scenarios)

        # Store results for later access (e.g., for database persistence)
        self._last_results = results

        report = self._build_report(results)
        report.framework = self.framework
        return report
    
    def get_all_mappings(self) -> List[ControlMapping]:
        """
        Get all confirmed mappings from the last enrichment run.
        This includes mappings from all scenarios, even those that were skipped.
        """
        if not hasattr(self, '_last_results'):
            return []
        
        all_mappings = []
        for result in self._last_results:
            all_mappings.extend(result.confirmed_mappings)
        
        return all_mappings

    # ------------------------------------------------------------------
    # Sequential mode
    # ------------------------------------------------------------------

    def _run_sequential(
        self, scenarios: List[CISRiskScenario]
    ) -> List[ScenarioEnrichmentResult]:
        results = []
        all_results = self.checkpoint_manager.get_results() if self.resume else []
        
        for i, scenario in enumerate(scenarios, 1):
            # Skip if already processed (when resuming)
            if scenario.scenario_id in self.processed_scenarios:
                logger.debug(f"[{i}/{len(scenarios)}] ⏭️  Skipping {scenario.scenario_id} (already processed)")
                # Find existing result
                existing_result = next(
                    (r for r in all_results if r.get("scenario_id") == scenario.scenario_id),
                    None
                )
                if existing_result:
                    # Reconstruct result from checkpoint
                    # Restore mappings from registry if available
                    scenario = self.registry.get(existing_result["scenario_id"])
                    confirmed_mappings = []
                    if scenario and scenario.controls:
                        confirmed_mappings = [
                            ControlMapping(
                                technique_id=tid,
                                scenario_id=scenario.scenario_id,
                                scenario_name=scenario.name,
                                relevance_score=0.7,  # Default from checkpoint
                                rationale="Restored from checkpoint",
                                confidence="medium",
                            )
                            for tid in scenario.controls
                        ]
                    
                    result = ScenarioEnrichmentResult(
                        scenario_id=existing_result["scenario_id"],
                        scenario_name=existing_result["scenario_name"],
                        confirmed_mappings=confirmed_mappings,
                        skipped_techniques=existing_result.get("skipped", []),
                        errors=existing_result.get("errors", []),
                        duration_seconds=existing_result.get("duration_seconds", 0.0),
                    )
                    results.append(result)
                continue
            
            logger.info(f"[{i}/{len(scenarios)}] Processing {scenario.scenario_id} – {scenario.name[:50]}")
            result = self._enrich_scenario(scenario)
            results.append(result)
            self._apply_result(result)
            
            # Log progress
            if result.confirmed_mappings:
                logger.info(f"  ✓ {len(result.confirmed_mappings)} mappings found")
            elif result.errors:
                logger.warning(f"  ✗ Errors: {result.errors}")
            elif not result.suggested_techniques:
                logger.warning(f"  ⚠ No techniques suggested")
            elif not result.confirmed_mappings and result.suggested_techniques:
                logger.warning(f"  ⚠ {len(result.suggested_techniques)} techniques suggested but none confirmed")
            
            # Generate preview if enabled
            if self.use_preview and self.preview_generator and result.confirmed_mappings:
                self._generate_preview_for_scenario(scenario, result)
            
            # Save checkpoint after each scenario
            self.processed_scenarios.add(scenario.scenario_id)
            all_results.append(result.to_dict())
            self._save_checkpoint(all_results, len(scenarios))
        
        return results

    # ------------------------------------------------------------------
    # Concurrent mode
    # ------------------------------------------------------------------

    async def _run_concurrent(
        self, scenarios: List[CISRiskScenario], workers: int
    ) -> List[ScenarioEnrichmentResult]:
        # Filter out already processed scenarios
        remaining_scenarios = [
            s for s in scenarios
            if s.scenario_id not in self.processed_scenarios
        ]
        
        if not remaining_scenarios:
            logger.info("All scenarios already processed - returning checkpointed results")
            all_results = self.checkpoint_manager.get_results()
            return [
                ScenarioEnrichmentResult(
                    scenario_id=r["scenario_id"],
                    scenario_name=r["scenario_name"],
                    duration_seconds=r.get("duration_seconds", 0.0),
                )
                for r in all_results
            ]
        
        semaphore = asyncio.Semaphore(workers)
        loop = asyncio.get_event_loop()
        all_results = self.checkpoint_manager.get_results() if self.resume else []

        async def _bounded(scenario: CISRiskScenario) -> ScenarioEnrichmentResult:
            async with semaphore:
                return await loop.run_in_executor(None, self._enrich_scenario, scenario)

        tasks = [_bounded(s) for s in remaining_scenarios]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        enrichment_results = []
        for scenario, result in zip(remaining_scenarios, results):
            if isinstance(result, Exception):
                logger.error(f"[concurrent] {scenario.scenario_id} failed: {result}")
                enrichment_results.append(
                    ScenarioEnrichmentResult(
                        scenario_id=scenario.scenario_id,
                        scenario_name=scenario.name,
                        errors=[str(result)],
                    )
                )
            else:
                enrichment_results.append(result)
                self._apply_result(result)
                
                # Generate preview if enabled
                if self.use_preview and self.preview_generator and result.confirmed_mappings:
                    self._generate_preview_for_scenario(scenario, result)
                
                # Save checkpoint after each scenario
                self.processed_scenarios.add(scenario.scenario_id)
                all_results.append(result.to_dict())
                self._save_checkpoint(all_results, len(scenarios))

        return enrichment_results

    # ------------------------------------------------------------------
    # Single-scenario enrichment
    # ------------------------------------------------------------------

    def _enrich_scenario(self, scenario: CISRiskScenario) -> ScenarioEnrichmentResult:
        start = time.time()
        result = ScenarioEnrichmentResult(
            scenario_id=scenario.scenario_id,
            scenario_name=scenario.name,
        )

        # Skip if already enriched and skip_existing is set
        existing = self.registry.get(scenario.scenario_id)
        if self.skip_existing and existing and existing.controls:
            logger.debug(f"[skip] {scenario.scenario_id} already has controls: {existing.controls}")
            result.confirmed_mappings = [
                ControlMapping(
                    technique_id=t,
                    scenario_id=scenario.scenario_id,
                    scenario_name=scenario.name,
                    relevance_score=1.0,
                    rationale="Pre-existing mapping",
                    confidence="high",
                )
                for t in existing.controls
            ]
            result.duration_seconds = time.time() - start
            return result

        # Step 1: Reverse-map → candidate technique IDs
        try:
            suggestions = self.reverse_mapper.suggest(scenario)
        except Exception as exc:
            logger.error(f"[reverse] {scenario.scenario_id}: {exc}")
            result.errors.append(f"reverse_mapper: {exc}")
            result.duration_seconds = time.time() - start
            return result

        result.suggested_techniques = suggestions

        # Filter by relevance threshold and cap count
        candidates = [
            s for s in suggestions if s.relevance >= self.relevance_threshold
        ][: self.max_techniques]

        if not candidates:
            logger.warning(f"[{scenario.scenario_id}] No candidates above threshold {self.relevance_threshold}")
            result.duration_seconds = time.time() - start
            return result

        # Step 2: Forward-map each candidate through the LangGraph
        all_mappings: List[ControlMapping] = []
        for suggestion in candidates:
            tid = suggestion.technique_id
            try:
                state = run_mapping(
                    self.graph,
                    technique_id=tid,
                    scenario_filter=None,
                )
                # Only keep mappings that matched THIS scenario
                matched = False
                for m in state.get("final_mappings", []):
                    if m.scenario_id == scenario.scenario_id:
                        all_mappings.append(m)
                        matched = True
                        logger.debug(f"  ✓ {tid} → {scenario.scenario_id} (relevance: {m.relevance_score:.2f}, confidence: {m.confidence})")
                        break
                
                if not matched:
                    # No forward match for this scenario — record as skipped
                    result.skipped_techniques.append(tid)
                    logger.debug(f"  ✗ {tid} did not match {scenario.scenario_id} in forward mapping")
            except Exception as exc:
                logger.error(f"[forward] {scenario.scenario_id}/{tid}: {exc}")
                result.errors.append(f"forward_map/{tid}: {exc}")

        result.confirmed_mappings = all_mappings
        result.duration_seconds = time.time() - start

        if all_mappings:
            logger.info(
                f"[{scenario.scenario_id}] ✓ {len(candidates)} candidates → {len(all_mappings)} confirmed mappings "
                f"({result.duration_seconds:.1f}s)"
            )
        else:
            logger.warning(
                f"[{scenario.scenario_id}] ⚠ {len(candidates)} candidates → 0 confirmed mappings "
                f"(skipped: {len(result.skipped_techniques)}, errors: {len(result.errors)})"
            )
        return result

    def _generate_preview_for_scenario(
        self,
        scenario: CISRiskScenario,
        result: ScenarioEnrichmentResult,
    ) -> None:
        """Generate preview for a scenario's technique mappings."""
        if not self.preview_generator or not result.confirmed_mappings:
            return
        
        # Generate previews for each technique that mapped to this scenario
        for mapping in result.confirmed_mappings:
            try:
                self.preview_generator.generate_preview(mapping.technique_id)
            except Exception as e:
                logger.warning(f"Failed to generate preview for {mapping.technique_id}: {e}")

    # ------------------------------------------------------------------
    # Apply result to registry
    # ------------------------------------------------------------------

    def _apply_result(self, result: ScenarioEnrichmentResult) -> None:
        """Merge confirmed mappings into the registry."""
        technique_ids = [m.technique_id for m in result.confirmed_mappings]
        if technique_ids:
            self.registry.update_controls(result.scenario_id, technique_ids)
    
    def _save_checkpoint(self, results: List[Dict[str, Any]], total_scenarios: int) -> None:
        """Save checkpoint after processing scenarios."""
        # Build registry state snapshot
        registry_state = {
            "controls": {
                scenario.scenario_id: scenario.controls
                for scenario in self.registry.all()
                if scenario.controls
            }
        }
        
        self.checkpoint_manager.save_checkpoint(
            framework=self.framework,
            processed_scenarios=list(self.processed_scenarios),
            total_scenarios=total_scenarios,
            results=results,
            registry_state=registry_state,
            metadata={
                "max_techniques": self.max_techniques,
                "relevance_threshold": self.relevance_threshold,
            },
        )

    # ------------------------------------------------------------------
    # Build coverage report
    # ------------------------------------------------------------------

    def _build_report(self, results: List[ScenarioEnrichmentResult]) -> CoverageReport:
        report = CoverageReport(total_scenarios=len(results))
        all_techniques: set = set()
        confidence_counts: Dict[str, int] = {"high": 0, "medium": 0, "low": 0}
        asset_counts: Dict[str, int] = {}
        technique_freq: Dict[str, int] = {}

        for r in results:
            if r.confirmed_mappings:
                report.enriched_scenarios += 1
            report.total_mappings += len(r.confirmed_mappings)
            report.total_duration_seconds += r.duration_seconds

            # Per-scenario asset count
            scenario = self.registry.get(r.scenario_id)
            if scenario:
                asset = scenario.asset
                asset_counts[asset] = asset_counts.get(asset, 0) + (
                    1 if r.confirmed_mappings else 0
                )

            for m in r.confirmed_mappings:
                all_techniques.add(m.technique_id)
                technique_freq[m.technique_id] = technique_freq.get(m.technique_id, 0) + 1
                confidence_counts[m.confidence] = confidence_counts.get(m.confidence, 0) + 1

            report.scenario_results.append(r.to_dict())

        report.unique_techniques = len(all_techniques)
        report.asset_coverage = asset_counts
        report.technique_frequency = technique_freq
        report.confidence_distribution = confidence_counts
        return report

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export(
        self,
        output_yaml: Optional[str] = None,
        output_json: Optional[str] = None,
        report: Optional[CoverageReport] = None,
    ) -> None:
        if output_yaml:
            self.registry.export_yaml(output_yaml)
            logger.info(f"Exported enriched YAML → {output_yaml}")

        if output_json and report:
            Path(output_json).write_text(
                json.dumps(report.to_dict(), indent=2), encoding="utf-8"
            )
            logger.info(f"Exported coverage report → {output_json}")

        if report:
            self._print_summary(report)
        
        # Export checkpoint status
        if self.checkpoint_manager:
            self.checkpoint_manager.export_status()
            progress = self.checkpoint_manager.get_progress()
            logger.info(
                f"📊 Progress: {progress['processed']}/{progress['total']} "
                f"({progress['progress_pct']}%)"
            )

    # ------------------------------------------------------------------
    # Console summary
    # ------------------------------------------------------------------

    @staticmethod
    def _print_summary(report: CoverageReport) -> None:
        s = report.to_dict()["summary"]
        print("\n" + "═" * 60)
        print(f"  ATT&CK → {report.framework.upper()} Control Mapping — Coverage Report")
        print("═" * 60)
        print(f"  Scenarios enriched : {s['enriched_scenarios']} / {s['total_scenarios']} ({s['coverage_pct']}%)")
        print(f"  Total mappings     : {s['total_mappings']}")
        print(f"  Unique techniques  : {s['unique_techniques_mapped']}")
        print(f"  Total runtime      : {s['total_duration_seconds']}s")
        conf = report.confidence_distribution
        print(f"  Confidence         : high={conf.get('high',0)} medium={conf.get('medium',0)} low={conf.get('low',0)}")
        print("═" * 60)

        if report.technique_frequency:
            top5 = sorted(report.technique_frequency.items(), key=lambda x: -x[1])[:5]
            print("  Most frequent techniques:")
            for tid, count in top5:
                print(f"    {tid:12s}  {count} scenario(s)")
        print("═" * 60 + "\n")

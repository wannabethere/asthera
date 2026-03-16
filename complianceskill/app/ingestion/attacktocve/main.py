"""
CLI Entry Point & Integration Examples
=======================================

Usage
-----
# Single technique
python main.py --technique T1078

# Batch from file
python main.py --batch techniques.txt --output enriched_controls.yaml

# Asset-domain filter
python main.py --technique T1059.001 --filter operations_security

# Generate preview (new workflow)
python main.py --preview --technique T1078 --preview-dir ./previews
python main.py --preview --batch techniques.txt --preview-dir ./previews

# Ingest preview files into vector store
python main.py --ingest-previews --preview-dir ./previews

# Ingest CIS scenarios into Chroma first
python main.py --ingest --yaml cis_controls_v8_1_risk_controls.yaml

# Framework items (unified collection for mapping pipeline) - all frameworks
python main.py --ingest-framework-items

# Framework items - single framework
python main.py --ingest-framework-items --framework cis_controls_v8_1

# CVE batch enrichment from CSV (Stage 1: NVD/EPSS/KEV data)
python main.py --enrich-cves-from-csv -i cves.csv -o cve_enriched.csv

# CVE batch enrichment with full pipeline (Stage 1 + ATT&CK mapping)
python main.py --enrich-cves-from-csv -i cves.csv -o cve_enriched.csv --full-pipeline

# Postgres + vector store ATT&CK ingest (uses settings for destinations)
python main.py --ingest-attack

# With explicit DSN
python main.py --ingest-attack postgresql://user:pass@localhost/ccdb

# Postgres only (skip vector store)
python main.py --ingest-attack --no-vector-store
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Handle both relative imports (when run as module) and absolute imports (when run as script)
try:
    from .control_loader import load_cis_scenarios, CISControlRegistry
    from .vectorstore_retrieval import VectorStoreConfig, VectorBackend, ingest_cis_scenarios
    from .graph import build_graph, run_mapping, run_batch_mapping
    from .preview_generator import PreviewGenerator, generate_preview_from_file
    from .ingestion import AttackEnrichmentIngester, ingest_preview_directory
    from .framework_helper import get_framework_path, list_frameworks, find_framework_yaml
    from .batch_ingestion import BatchFrameworkIngester, ingest_all_frameworks_async
except ImportError:
    # Fallback for when run as script
    import sys
    import os
    from pathlib import Path
    
    # Add workspace root to path for app.* imports
    # main.py is at: complianceskill/app/ingestion/attacktocve/main.py
    # We need: complianceskill/ (where app/ is)
    workspace_root = Path(__file__).parent.parent.parent.parent
    workspace_root_str = str(workspace_root)
    if workspace_root_str not in sys.path:
        sys.path.insert(0, workspace_root_str)
    
    # Also add the attacktocve directory for direct file imports
    attacktocve_dir = Path(__file__).parent
    attacktocve_dir_str = str(attacktocve_dir)
    if attacktocve_dir_str not in sys.path:
        sys.path.insert(0, attacktocve_dir_str)
    
    # Import directly from files in attacktocve directory (avoiding app.ingestion package)
    # These imports will work because attacktocve_dir is in sys.path
    from control_loader import load_cis_scenarios, CISControlRegistry
    from vectorstore_retrieval import VectorStoreConfig, VectorBackend, ingest_cis_scenarios
    from graph import build_graph, run_mapping, run_batch_mapping
    # preview_generator, ingestion, framework_helper, batch_ingestion will handle their own imports
    from preview_generator import PreviewGenerator, generate_preview_from_file
    from ingestion import AttackEnrichmentIngester, ingest_preview_directory
    from framework_helper import get_framework_path, list_frameworks, find_framework_yaml
    from batch_ingestion import BatchFrameworkIngester, ingest_all_frameworks_async

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _vs_config_from_env() -> VectorStoreConfig:
    """
    Build VectorStoreConfig from centralized settings.
    
    This function is kept for backward compatibility but now uses
    VectorStoreConfig.from_settings() which reads from settings.py.
    """
    return VectorStoreConfig.from_settings()


# ---------------------------------------------------------------------------
# Preview commands
# ---------------------------------------------------------------------------

def cmd_preview_single(
    technique_id: str,
    preview_dir: str,
    yaml_path: Optional[str] = None,
    scenario_filter: Optional[str] = None,
) -> None:
    """Generate preview for a single ATT&CK technique."""
    generator = PreviewGenerator(preview_dir, yaml_path=yaml_path)
    preview = generator.generate_preview(technique_id, scenario_filter=scenario_filter)
    print(f"✅  Generated preview for {technique_id} in {preview_dir}")


def cmd_preview_batch(
    batch_file: str,
    preview_dir: str,
    yaml_path: Optional[str] = None,
    scenario_filter: Optional[str] = None,
) -> None:
    """Generate previews for multiple ATT&CK techniques."""
    previews = generate_preview_from_file(
        batch_file,
        preview_dir,
        yaml_path=yaml_path,
        scenario_filter=scenario_filter,
    )
    print(f"✅  Generated {len(previews)} previews in {preview_dir}")


# ---------------------------------------------------------------------------
# Ingest commands
# ---------------------------------------------------------------------------

async def cmd_ingest_previews(
    preview_dir: str,
    collection_name: Optional[str] = None,
    limit: Optional[int] = None,
) -> None:
    """Ingest preview files into vector store."""
    stats = await ingest_preview_directory(
        preview_dir,
        collection_name=collection_name,
        limit=limit,
    )
    print(f"✅  Ingestion complete:")
    print(f"    Files processed: {stats['total_files']}")
    print(f"    Successful: {stats['successful']}")
    print(f"    Failed: {stats['failed']}")
    print(f"    Documents ingested: {stats.get('ingested_documents', 0)}")


# ---------------------------------------------------------------------------
# Batch enrichment commands
# ---------------------------------------------------------------------------

def cmd_batch_enrich(
    framework: str,
    yaml_path: Optional[str] = None,
    output_yaml: Optional[str] = None,
    output_json: Optional[str] = None,
    asset_filter: Optional[str] = None,
    max_scenarios: Optional[int] = None,
    workers: int = 1,
    max_techniques: int = 5,
    threshold: float = 0.55,
    use_preview: bool = False,
    preview_dir: Optional[str] = None,
    no_skip: bool = False,
    evaluate: bool = False,
    persist: bool = False,
    db_dsn: Optional[str] = None,
    checkpoint_dir: Optional[str] = None,
    resume: bool = True,
    re_ingest: bool = False,
    vs_config: Optional[VectorStoreConfig] = None,
) -> None:
    """Run batch enrichment for a compliance framework."""
    try:
        from .persistence.batch_enricher import BatchEnricher
        from .persistence.evaluation import Evaluator
        from .persistence.persistence import MappingRepository
    except ImportError:
        try:
            from app.ingestion.attacktocve.persistence.batch_enricher import BatchEnricher
            from app.ingestion.attacktocve.persistence.evaluation import Evaluator
            from app.ingestion.attacktocve.persistence.persistence import MappingRepository
        except ImportError as e:
            logger.error(f"Failed to import batch enricher modules: {e}")
            print("❌  Batch enrichment modules not available")
            return
    
    # Find framework YAML file - prefer scenarios_*.yaml, fallback to *_risk_controls.yaml
    if not yaml_path:
        # Try scenarios first (for frameworks like HIPAA)
        yaml_path = find_framework_yaml(framework, file_type="scenarios")
        if not yaml_path:
            # Fallback to risk_controls (for frameworks like CIS)
            yaml_path = find_framework_yaml(framework, file_type="risk_controls")
        if not yaml_path:
            print(f"❌  Could not find YAML file for framework: {framework}")
            print(f"    Available frameworks: {', '.join(list_frameworks())}")
            return
        yaml_path = str(yaml_path)
    
    logger.info(f"Using YAML file: {yaml_path} for framework: {framework}")
    
    # Initialize batch enricher
    enricher = BatchEnricher(
        yaml_path=yaml_path,
        framework=framework,
        max_techniques_per_scenario=max_techniques,
        relevance_threshold=threshold,
        skip_existing=not no_skip,
        use_preview=use_preview,
        preview_dir=preview_dir,
        checkpoint_dir=checkpoint_dir,
        resume=resume,
    )
    
    # Run enrichment
    print(f"\n🔍  Starting batch enrichment for {framework}...")
    print(f"   Total scenarios loaded: {len(enricher.scenarios)}")
    if max_scenarios:
        print(f"   Limiting to {max_scenarios} scenarios (for testing)")
    if asset_filter:
        print(f"   Filtering by asset: {asset_filter}")
    print(f"   Workers: {workers}")
    print(f"   Relevance threshold: {threshold}")
    print(f"   Max techniques per scenario: {max_techniques}")
    print(f"   Skip existing: {not no_skip}")
    
    report = enricher.run(
        asset_filter=asset_filter,
        max_scenarios=max_scenarios,
        workers=workers,
    )
    
    print(f"\n📊 Enrichment Summary:")
    print(f"   Total scenarios: {report.total_scenarios}")
    print(f"   Enriched scenarios: {report.enriched_scenarios}")
    print(f"   Total mappings: {report.total_mappings}")
    print(f"   Unique techniques: {report.unique_techniques}")
    print(f"   Coverage: {report.coverage_pct}%")
    
    # Export results
    enricher.export(
        output_yaml=output_yaml,
        output_json=output_json,
        report=report,
    )
    
    # Evaluation
    if evaluate:
        try:
            evaluator = Evaluator()
            # Get all mappings from the registry
            scenarios = enricher.registry.all()
            mappings = []
            for scenario in scenarios:
                if scenario.controls:
                    for tid in scenario.controls:
                        # Create a simple mapping (we don't have full mapping details here)
                        from .state import ControlMapping
                        mappings.append(
                            ControlMapping(
                                technique_id=tid,
                                scenario_id=scenario.scenario_id,
                                scenario_name=scenario.name,
                                relevance_score=0.7,  # Default
                                rationale="Batch enriched",
                                confidence="medium",
                            )
                        )
            
            eval_report = evaluator.evaluate(
                mappings=mappings,
                scenarios=scenarios,
            )
            evaluator.print_report(eval_report)
            
            if output_json:
                eval_path = str(Path(output_json).with_suffix('.eval.json'))
                evaluator.export_report(eval_report, eval_path)
                print(f"💾  Saved evaluation report to {eval_path}")
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            print(f"⚠️  Evaluation failed: {e}")
    
    # Persistence
    if persist and db_dsn:
        try:
            repo = MappingRepository(dsn=db_dsn)
            run_id = repo.create_run(
                triggered_by="batch_enricher",
                technique_count=report.unique_techniques,
                scenario_count=len(enricher.scenarios),
            )
            
            # Save scenarios
            repo.seed_scenarios(enricher.registry.all())
            
            # Save mappings - use actual enrichment results, not just registry
            # This includes all confirmed mappings with full details (relevance, confidence, etc.)
            mappings = enricher.get_all_mappings()
            
            if not mappings:
                logger.warning("No mappings found in enrichment results. Falling back to registry-based mappings.")
                # Fallback: create mappings from registry if no enrichment results
                scenarios = enricher.registry.all()
                from .state import ControlMapping
                for scenario in scenarios:
                    if scenario.controls:
                        for tid in scenario.controls:
                            mappings.append(
                                ControlMapping(
                                    technique_id=tid,
                                    scenario_id=scenario.scenario_id,
                                    scenario_name=scenario.name,
                                    relevance_score=0.7,
                                    rationale="Batch enriched (from registry)",
                                    confidence="medium",
                                )
                            )
            
            logger.info(f"Saving {len(mappings)} mappings to database...")
            repo.save_mappings(mappings, run_id=run_id, retrieval_source="batch_enricher")
            repo.complete_run(
                run_id=run_id,
                mapping_count=len(mappings),
                coverage_pct=report.coverage_pct,
            )
            print(f"💾  Saved {len(mappings)} mappings to database (run_id: {run_id})")
            print(f"   Total scenarios processed: {report.total_scenarios}")
            print(f"   Enriched scenarios: {report.enriched_scenarios}")
            print(f"   Unique techniques: {report.unique_techniques}")
        except Exception as e:
            logger.error(f"Persistence failed: {e}")
            print(f"⚠️  Persistence failed: {e}")
            import traceback
            traceback.print_exc()
    
    # Re-ingest enriched scenarios to vector store
    if re_ingest:
        try:
            print(f"\n🔄 Re-ingesting enriched scenarios to vector store...")
            # Ingest enriched scenarios
            from .vectorstore_retrieval import ingest_cis_scenarios
            scenarios = enricher.registry.all()
            scenario_dicts = [s.model_dump() for s in scenarios]
            
            # Use provided config or build from enricher's config
            if vs_config:
                framework_config = vs_config
            else:
                # Build config from enricher's vs_config
                framework_config = enricher.vs_config
            
            # Use unified framework_scenarios collection from collections.py
            try:
                from app.storage.collections import FrameworkCollections
                collection_name = FrameworkCollections.SCENARIOS
            except ImportError:
                # Fallback if collections.py not available
                collection_name = "framework_scenarios"
            
            # Create framework-specific config with collection name
            from .vectorstore_retrieval import VectorBackend
            if framework_config.backend == VectorBackend.QDRANT:
                framework_config = VectorStoreConfig(
                    backend=framework_config.backend,
                    collection=collection_name,
                    qdrant_url=framework_config.qdrant_url,
                    qdrant_api_key=framework_config.qdrant_api_key,
                    openai_api_key=framework_config.openai_api_key,
                    embedding_model=framework_config.embedding_model,
                )
            else:
                framework_config = VectorStoreConfig(
                    backend=framework_config.backend,
                    collection=collection_name,
                    chroma_persist_dir=framework_config.chroma_persist_dir,
                    chroma_host=framework_config.chroma_host,
                    chroma_port=framework_config.chroma_port,
                    openai_api_key=framework_config.openai_api_key,
                    embedding_model=framework_config.embedding_model,
                )
            
            ingested_count = ingest_cis_scenarios(scenario_dicts, framework_config)
            print(f"✅ Re-ingested {ingested_count} enriched scenarios to unified collection: {collection_name} (framework: {framework})")
        except Exception as e:
            logger.error(f"Re-ingestion failed: {e}")
            print(f"⚠️  Re-ingestion failed: {e}")


def cmd_ingest_cis(yaml_path: str, config: VectorStoreConfig) -> None:
    """Embed and upsert all CIS scenarios into the vector store."""
    logger.info(f"Loading CIS scenarios from {yaml_path}…")
    scenarios = load_cis_scenarios(yaml_path)
    n = ingest_cis_scenarios([s.model_dump() for s in scenarios], config)
    print(f"✅  Ingested {n} CIS risk scenarios into {config.backend} [{config.collection}]")


def cmd_ingest_attack(
    pg_dsn: Optional[str] = None,
    vector_store: bool = True,
) -> None:
    """
    Download ATT&CK STIX bundle and ingest into Postgres and optionally vector store.

    Uses settings for destinations when not provided:
    - pg_dsn: from get_attack_db_dsn() (SEC_INTEL_CVE_ATTACK_DB_* or POSTGRES_*)
    - vector store: from VectorStoreConfig.from_settings() with ATTACK_TECHNIQUES_COLLECTION
    """
    try:
        from .attack_enrichment import ingest_stix_to_postgres
    except ImportError:
        from app.ingestion.attacktocve.attack_enrichment import ingest_stix_to_postgres

    from app.core.settings import get_settings

    settings = get_settings()
    dsn = pg_dsn or settings.get_attack_db_dsn()

    vs_config = None
    if vector_store:
        vs_config = _vs_config_from_env()
        vs_config = vs_config.model_copy(update={"collection": settings.ATTACK_TECHNIQUES_COLLECTION})

    print("Downloading ATT&CK STIX data …")
    n = ingest_stix_to_postgres(dsn, vector_store_config=vs_config)
    print(f"✅  Ingested {n} ATT&CK techniques into Postgres")
    if vs_config:
        print(f"✅  Ingested ATT&CK techniques into vector store [{vs_config.collection}]")


# ---------------------------------------------------------------------------
# Mapping commands
# ---------------------------------------------------------------------------

def cmd_single(
    technique_id: str,
    yaml_path: str,
    config: VectorStoreConfig,
    asset_filter: Optional[str] = None,
    output_json: Optional[str] = None,
) -> None:
    # Try to detect framework from yaml_path
    framework_id = None
    if yaml_path:
        yaml_str = str(yaml_path)
        for fw in ["cis_controls_v8_1", "nist_csf_2_0", "hipaa", "soc2", "iso27001_2013", "iso27001_2022"]:
            if fw in yaml_str:
                framework_id = fw
                break
    
    graph = build_graph(config, yaml_path=yaml_path, framework_id=framework_id)
    print(f"\n🔍  Mapping ATT&CK {technique_id} → CIS Controls …\n")
    state = run_mapping(graph, technique_id, scenario_filter=asset_filter, stream=True)

    mappings = state.get("final_mappings", [])
    print(f"\n{'─'*60}")
    print(f"RESULTS: {len(mappings)} mapping(s) for {technique_id}")
    print(f"{'─'*60}")
    for m in mappings:
        print(
            f"  [{m.confidence.upper():6}] {m.scenario_id} – {m.scenario_name}\n"
            f"           Score: {m.relevance_score:.2f} | {m.rationale[:100]}…\n"
        )

    if output_json:
        Path(output_json).write_text(
            json.dumps([m.model_dump() for m in mappings], indent=2)
        )
        print(f"\n💾  Saved mappings to {output_json}")


def cmd_batch(
    batch_file: str,
    yaml_path: str,
    config: VectorStoreConfig,
    output_yaml: Optional[str] = None,
) -> None:
    technique_ids = [
        line.strip()
        for line in Path(batch_file).read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    print(f"Processing {len(technique_ids)} technique(s) …")
    # Try to detect framework from yaml_path
    framework_id = None
    if yaml_path:
        yaml_str = str(yaml_path)
        for fw in ["cis_controls_v8_1", "nist_csf_2_0", "hipaa", "soc2", "iso27001_2013", "iso27001_2022"]:
            if fw in yaml_str:
                framework_id = fw
                break
    
    graph = build_graph(config, yaml_path=yaml_path, framework_id=framework_id)
    results = run_batch_mapping(graph, technique_ids)

    total_mappings = sum(len(s.get("final_mappings", [])) for s in results.values())
    print(f"\n✅  Done: {len(technique_ids)} techniques → {total_mappings} total mappings")

    if output_yaml:
        # Export enriched scenarios
        scenarios = load_cis_scenarios(yaml_path)
        registry = CISControlRegistry(scenarios)
        for state in results.values():
            for m in state.get("final_mappings", []):
                registry.update_controls(m.scenario_id, [m.technique_id])
        registry.export_yaml(output_yaml)
        print(f"💾  Saved enriched scenarios to {output_yaml}")
        print(f"📊  Coverage: {registry.coverage_report()}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ATT&CK → CIS Control Mapping Agent"
    )
    parser.add_argument("--technique", "-t", help="Single ATT&CK technique ID (e.g. T1078)")
    parser.add_argument("--batch", "-b", help="File with one technique ID per line")
    parser.add_argument("--filter", "-f", help="CIS asset domain filter")
    parser.add_argument("--yaml", "-y", default="cis_controls_v8_1_risk_controls.yaml",
                        help="Path to CIS controls YAML")
    parser.add_argument("--output", "-o", help="Output file (JSON for single, YAML for batch)")
    
    # Preview mode
    parser.add_argument("--preview", action="store_true",
                        help="Generate preview files instead of direct processing")
    parser.add_argument("--preview-dir", default="./previews",
                        help="Directory to write preview files (default: ./previews)")
    
    # Ingest modes
    parser.add_argument("--ingest", action="store_true",
                        help="Ingest CIS scenarios into vector store and exit")
    parser.add_argument("--ingest-attack", metavar="PG_DSN", nargs="?",
                        const="", default=None,
                        help="Ingest ATT&CK STIX into Postgres and vector store. Optional DSN (uses settings if omitted)")
    parser.add_argument("--no-vector-store", action="store_true",
                        help="When using --ingest-attack, skip vector store ingestion (Postgres only)")
    parser.add_argument("--ingest-previews", action="store_true",
                        help="Ingest preview files into vector store")
    parser.add_argument("--collection", help="Vector store collection name for ingestion")
    parser.add_argument("--limit", type=int, help="Limit number of preview files to ingest")
    
    # Batch enrichment
    parser.add_argument("--batch-enrich", action="store_true",
                        help="Run batch enrichment for all scenarios in a framework")
    parser.add_argument("--framework", choices=list_frameworks(),
                        help="Compliance framework (for --ingest-framework-items: single framework; omit for all)")
    parser.add_argument("--max-techniques", type=int, default=5,
                        help="Maximum techniques per scenario")
    parser.add_argument("--threshold", type=float, default=0.55,
                        help="Minimum relevance threshold for techniques")
    parser.add_argument("--workers", "-w", type=int, default=1,
                        help="Number of concurrent workers (1 = sequential)")
    parser.add_argument("--max-scenarios", "-n", type=int,
                        help="Limit number of scenarios (for testing)")
    parser.add_argument("--no-skip", action="store_true",
                        help="Re-map scenarios that already have controls")
    parser.add_argument("--evaluate", action="store_true",
                        help="Run evaluation after enrichment")
    parser.add_argument("--persist", action="store_true",
                        help="Save results to database")
    parser.add_argument("--db-dsn", help="Database DSN for persistence")
    parser.add_argument("--re-ingest", action="store_true",
                        help="Re-ingest enriched scenarios back to vector store after enrichment")
    parser.add_argument("--checkpoint-dir", help="Directory for checkpoint files")
    parser.add_argument("--no-resume", action="store_true",
                        help="Don't resume from checkpoint (start fresh)")
    parser.add_argument("--background", "-bg", action="store_true",
                        help="Run in background (daemon mode)")
    parser.add_argument("--status", action="store_true",
                        help="Check status of running/previous batch enrichment")
    parser.add_argument("--clear-checkpoint", action="store_true",
                        help="Clear existing checkpoint and start fresh")
    
    # CVE batch enrichment from CSV
    parser.add_argument("--enrich-cves-from-csv", action="store_true",
                        help="Enrich CVEs from a CSV file and write to a new CSV with all enrichment fields")
    parser.add_argument("-i", "--input-csv", help="Input CSV path (column with CVE IDs)")
    parser.add_argument("-o", "--output-csv", default="cve_enriched.csv",
                        help="Output CSV path (default: cve_enriched.csv)")
    parser.add_argument("--cve-column", help="Column name containing CVE IDs (auto-detected if omitted)")
    parser.add_argument("--full-pipeline", action="store_true",
                        help="Run full pipeline: CVE enrichment + ATT&CK mapping (adds technique_ids, tactics)")
    parser.add_argument("--frameworks", nargs="+", default=["cis_v8_1", "nist_800_53r5"],
                        help="Frameworks for ATT&CK mapping when --full-pipeline (default: cis_v8_1 nist_800_53r5)")

    # Framework items ingestion (unified framework_items collection)
    parser.add_argument("--ingest-framework-items", action="store_true",
                        help="Populate framework_items (Postgres + vector store) for mapping pipeline")
    parser.add_argument("--no-llm-classifier", action="store_true",
                        help="Skip LLM tactic_domains/asset_types classification (use empty lists)")

    # Batch framework ingestion
    parser.add_argument("--ingest-all-frameworks", action="store_true",
                        help="Ingest scenarios from all frameworks into vector store")
    parser.add_argument("--skip-frameworks", nargs="+",
                        help="Frameworks to skip during batch ingestion")
    parser.add_argument("--collection-prefix", default="",
                        help="Prefix for collection names (e.g., 'framework_')")

    args = parser.parse_args()
    config = _vs_config_from_env()

    # Preview mode
    if args.preview:
        if args.technique:
            cmd_preview_single(
                args.technique,
                args.preview_dir,
                yaml_path=args.yaml,
                scenario_filter=args.filter,
            )
        elif args.batch:
            cmd_preview_batch(
                args.batch,
                args.preview_dir,
                yaml_path=args.yaml,
                scenario_filter=args.filter,
            )
        else:
            parser.error("--preview requires --technique or --batch")
        sys.exit(0)
    
    # Ingest previews mode
    if args.ingest_previews:
        asyncio.run(cmd_ingest_previews(
            args.preview_dir,
            collection_name=args.collection,
            limit=args.limit,
        ))
        sys.exit(0)

    # Legacy ingest modes
    if args.ingest:
        cmd_ingest_cis(args.yaml, config)
        sys.exit(0)

    if args.ingest_attack is not None:
        pg_dsn = args.ingest_attack if args.ingest_attack else None
        cmd_ingest_attack(pg_dsn=pg_dsn, vector_store=not args.no_vector_store)
        sys.exit(0)

    # CVE batch enrichment from CSV
    if args.enrich_cves_from_csv:
        try:
            from .batch_cve_enrich import enrich_cves_from_csv
        except ImportError:
            from app.ingestion.attacktocve.batch_cve_enrich import enrich_cves_from_csv

        if not args.input_csv:
            parser.error("--enrich-cves-from-csv requires -i/--input-csv")
        print(f"\n🔍 Enriching CVEs from {args.input_csv} → {args.output_csv}")
        if args.full_pipeline:
            print(f"   Full pipeline: CVE enrichment + ATT&CK mapping (frameworks: {args.frameworks})")
        summary = enrich_cves_from_csv(
            input_csv=args.input_csv,
            output_csv=args.output_csv,
            cve_column=args.cve_column,
            full_pipeline=args.full_pipeline,
            frameworks=args.frameworks,
        )
        print(f"\n✅ Done: {summary['succeeded']} enriched, {summary['failed']} failed")
        print(f"   Output: {args.output_csv}")
        if summary["errors"]:
            for e in summary["errors"][:5]:
                print(f"   Error: {e['cve']} — {e['error'][:80]}")
            if len(summary["errors"]) > 5:
                print(f"   ... and {len(summary['errors']) - 5} more")
        sys.exit(0)

    # Framework items ingestion mode (unified framework_items for mapping pipeline)
    if args.ingest_framework_items:
        try:
            from .framework_item_ingest import ingest_framework_items, ingest_all_framework_items
        except ImportError:
            from app.ingestion.attacktocve.framework_item_ingest import ingest_framework_items, ingest_all_framework_items

        use_llm = not args.no_llm_classifier
        framework = args.framework

        if framework:
            result = ingest_framework_items(framework, use_llm_classifier=use_llm)
            print(f"\n✅ Framework items: {framework}")
            print(f"   Loaded: {result['items_loaded']} | Postgres: {result['items_postgres']} | Vector store: {result['items_vector_store']}")
            if result.get("errors"):
                print(f"   Errors: {result['errors']}")
        else:
            report = ingest_all_framework_items(
                skip_frameworks=args.skip_frameworks,
                use_llm_classifier=use_llm,
            )
            print("\n" + "=" * 60)
            print("Framework Items Batch Ingestion Summary")
            print("=" * 60)
            print(f"Total frameworks: {report['total_frameworks']}")
            print(f"Successful: {report['successful']}")
            print(f"Failed: {report['failed']}")
            print("-" * 60)
            for r in report["results"]:
                status = "✅" if not r.get("errors") else "❌"
                print(f"  {status} {r['framework']:25} | Items: {r.get('items_vector_store', 0):4} to vector store")
            print("=" * 60)
        sys.exit(0)

    # Batch framework ingestion mode
    if args.ingest_all_frameworks:
        # Background execution
        if args.background:
            import subprocess
            import sys as _sys
            
            cmd = [_sys.executable, _sys.argv[0]] + [
                arg for arg in _sys.argv[1:]
                if arg != "--background" and arg != "-bg"
            ]
            
            log_file = f"batch_ingestion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            print(f"🚀 Starting batch framework ingestion in background...")
            print(f"   Log file: {log_file}")
            print(f"   Check status with: python main.py --status --ingest-all-frameworks")
            
            with open(log_file, 'w') as log:
                process = subprocess.Popen(
                    cmd,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            
            print(f"   Process ID: {process.pid}")
            print(f"   To stop: kill {process.pid}")
            sys.exit(0)
        
        # Foreground execution
        ingester = BatchFrameworkIngester(
            checkpoint_dir=args.checkpoint_dir,
            resume=not args.no_resume,
            collection_prefix=args.collection_prefix,
        )
        
        print(f"\n🔍 Starting batch ingestion of all frameworks...")
        report = ingester.ingest_all_frameworks(
            skip_frameworks=args.skip_frameworks,
        )
        
        ingester.print_summary(report)
        ingester.export_report(report)
        
        # Export checkpoint status
        if ingester.checkpoint_manager:
            ingester.checkpoint_manager.export_status()
            progress = ingester.checkpoint_manager.get_progress()
            logger.info(
                f"📊 Progress: {progress['processed']}/{progress['total']} "
                f"({progress['progress_pct']}%)"
            )
        
        sys.exit(0)
    
    # Status check mode
    if args.status:
        try:
            from .persistence.checkpoint_manager import CheckpointManager
        except ImportError:
            from app.ingestion.attacktocve.persistence.checkpoint_manager import CheckpointManager
        
        # Check if this is for batch ingestion or batch enrichment
        if args.ingest_all_frameworks or (not args.batch_enrich and not args.framework):
            # Batch ingestion status
            if args.checkpoint_dir:
                checkpoint_dir = Path(args.checkpoint_dir)
            else:
                checkpoint_dir = Path(".checkpoints") / "batch_ingestion"
            
            manager = CheckpointManager(checkpoint_dir)
            if manager.has_checkpoint():
                progress = manager.get_progress()
                print("\n" + "=" * 60)
                print("Batch Framework Ingestion Status")
                print("=" * 60)
                print(f"Type: {manager.state.get('metadata', {}).get('type', 'unknown')}")
                print(f"Progress: {progress['processed']} / {progress['total']} frameworks ({progress['progress_pct']}%)")
                print(f"Remaining: {progress['remaining']} frameworks")
                print(f"Last Updated: {progress['last_updated']}")
                print(f"Checkpoint Count: {progress['checkpoint_count']}")
                print("=" * 60)
                manager.export_status()
            else:
                print("No checkpoint found - batch ingestion has not been run or checkpoint was cleared.")
        else:
            # Batch enrichment status
            framework = args.framework or "cis_controls_v8_1"
            if args.checkpoint_dir:
                checkpoint_dir = Path(args.checkpoint_dir)
            else:
                # Find YAML to determine checkpoint location
                yaml_path = find_framework_yaml(framework) or args.yaml
                if yaml_path:
                    checkpoint_dir = Path(yaml_path).parent / ".checkpoints" / framework
                else:
                    checkpoint_dir = Path(".checkpoints") / framework
            
            manager = CheckpointManager(checkpoint_dir)
            if manager.has_checkpoint():
                progress = manager.get_progress()
                print("\n" + "=" * 60)
                print("Batch Enrichment Status")
                print("=" * 60)
                print(f"Framework: {progress['framework']}")
                print(f"Progress: {progress['processed']} / {progress['total']} scenarios ({progress['progress_pct']}%)")
                print(f"Remaining: {progress['remaining']} scenarios")
                print(f"Last Updated: {progress['last_updated']}")
                print(f"Checkpoint Count: {progress['checkpoint_count']}")
                print("=" * 60)
                manager.export_status()
            else:
                print("No checkpoint found - batch enrichment has not been run or checkpoint was cleared.")
        sys.exit(0)
    
    # Clear checkpoint mode
    if args.clear_checkpoint:
        try:
            from .persistence.checkpoint_manager import CheckpointManager
        except ImportError:
            from app.ingestion.attacktocve.persistence.checkpoint_manager import CheckpointManager
        
        # Check if this is for batch ingestion or batch enrichment
        if args.ingest_all_frameworks:
            # Batch ingestion checkpoint
            if args.checkpoint_dir:
                checkpoint_dir = Path(args.checkpoint_dir)
            else:
                checkpoint_dir = Path(".checkpoints") / "batch_ingestion"
            
            manager = CheckpointManager(checkpoint_dir)
            manager.clear_checkpoint()
            print(f"✅ Batch ingestion checkpoint cleared")
        else:
            # Batch enrichment checkpoint
            framework = args.framework or "cis_controls_v8_1"
            if args.checkpoint_dir:
                checkpoint_dir = Path(args.checkpoint_dir)
            else:
                yaml_path = find_framework_yaml(framework) or args.yaml
                if yaml_path:
                    checkpoint_dir = Path(yaml_path).parent / ".checkpoints" / framework
                else:
                    checkpoint_dir = Path(".checkpoints") / framework
            
            manager = CheckpointManager(checkpoint_dir)
            manager.clear_checkpoint()
            print(f"✅ Checkpoint cleared for framework: {framework}")
        sys.exit(0)
    
    # Batch enrichment mode
    if args.batch_enrich:
        framework = args.framework or "cis_controls_v8_1"
        output_yaml = args.output or f"enriched_{framework}.yaml"
        output_json = args.output.replace(".yaml", ".json") if args.output and args.output.endswith(".yaml") else f"coverage_{framework}.json"
        
        # Background execution
        if args.background:
            import subprocess
            import sys as _sys
            
            # Build command for background execution
            cmd = [_sys.executable, _sys.argv[0]] + [
                arg for arg in _sys.argv[1:]
                if arg != "--background" and arg != "-bg"
            ]
            
            # Add nohup and redirect output
            log_file = f"batch_enrich_{framework}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            print(f"🚀 Starting batch enrichment in background...")
            print(f"   Log file: {log_file}")
            print(f"   Check status with: python main.py --status --framework {framework}")
            
            with open(log_file, 'w') as log:
                process = subprocess.Popen(
                    cmd,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,  # Detach from parent
                )
            
            print(f"   Process ID: {process.pid}")
            print(f"   To stop: kill {process.pid}")
            sys.exit(0)
        
        # Foreground execution
        cmd_batch_enrich(
            framework=framework,
            yaml_path=args.yaml,
            output_yaml=output_yaml,
            output_json=output_json,
            asset_filter=args.filter,
            max_scenarios=args.max_scenarios,
            workers=args.workers,
            max_techniques=args.max_techniques,
            threshold=args.threshold,
            use_preview=args.preview,
            preview_dir=args.preview_dir if args.preview else None,
            no_skip=args.no_skip,
            evaluate=args.evaluate,
            persist=args.persist,
            db_dsn=args.db_dsn,
            checkpoint_dir=args.checkpoint_dir,
            resume=not args.no_resume,
            re_ingest=args.re_ingest,
            vs_config=config,
        )
        sys.exit(0)
    
    # Direct processing mode (legacy)
    if args.technique:
        cmd_single(args.technique, args.yaml, config, args.filter, args.output)
    elif args.batch:
        cmd_batch(args.batch, args.yaml, config, args.output)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

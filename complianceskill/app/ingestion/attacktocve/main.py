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

# Postgres ATT&CK ingest
python main.py --ingest-attack --pg postgresql://user:pass@localhost/ccdb
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
    Build VectorStoreConfig from environment variables.

    VECTOR_BACKEND      = "chroma" | "qdrant"  (default: chroma)
    VECTOR_COLLECTION   = collection name       (default: cis_controls_v8_1)
    QDRANT_URL          = http://localhost:6333
    QDRANT_API_KEY      = ...
    CHROMA_PERSIST_DIR  = ./chroma_store
    CHROMA_HOST         = (optional, for remote Chroma)
    OPENAI_API_KEY      = sk-...
    EMBEDDING_MODEL     = text-embedding-3-small
    RETRIEVAL_TOP_K     = 5
    """
    backend = os.getenv("VECTOR_BACKEND", "chroma")
    return VectorStoreConfig(
        backend=VectorBackend(backend),
        collection=os.getenv("VECTOR_COLLECTION", "cis_controls_v8_1"),
        qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        qdrant_api_key=os.getenv("QDRANT_API_KEY"),
        chroma_persist_dir=os.getenv("CHROMA_PERSIST_DIR", "./chroma_store"),
        chroma_host=os.getenv("CHROMA_HOST"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        top_k=int(os.getenv("RETRIEVAL_TOP_K", "5")),
    )


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
    
    # Find framework YAML file
    if not yaml_path:
        yaml_path = find_framework_yaml(framework)
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
    report = enricher.run(
        asset_filter=asset_filter,
        max_scenarios=max_scenarios,
        workers=workers,
    )
    
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
            )
            
            # Save scenarios
            repo.seed_scenarios(enricher.registry.all())
            
            # Save mappings
            scenarios = enricher.registry.all()
            from .state import ControlMapping
            mappings = []
            for scenario in scenarios:
                if scenario.controls:
                    for tid in scenario.controls:
                        mappings.append(
                            ControlMapping(
                                technique_id=tid,
                                scenario_id=scenario.scenario_id,
                                scenario_name=scenario.name,
                                relevance_score=0.7,
                                rationale="Batch enriched",
                                confidence="medium",
                            )
                        )
            
            repo.save_mappings(mappings, run_id=run_id)
            repo.complete_run(
                run_id=run_id,
                mapping_count=len(mappings),
                coverage_pct=report.coverage_pct,
            )
            print(f"💾  Saved to database (run_id: {run_id})")
        except Exception as e:
            logger.error(f"Persistence failed: {e}")
            print(f"⚠️  Persistence failed: {e}")


def cmd_ingest_cis(yaml_path: str, config: VectorStoreConfig) -> None:
    """Embed and upsert all CIS scenarios into the vector store."""
    logger.info(f"Loading CIS scenarios from {yaml_path}…")
    scenarios = load_cis_scenarios(yaml_path)
    n = ingest_cis_scenarios([s.model_dump() for s in scenarios], config)
    print(f"✅  Ingested {n} CIS risk scenarios into {config.backend} [{config.collection}]")


def cmd_ingest_attack(pg_dsn: str) -> None:
    """Download ATT&CK STIX bundle and ingest into Postgres."""
    try:
        from .attack_enrichment import ingest_stix_to_postgres
    except ImportError:
        from app.ingestion.attacktocve.attack_enrichment import ingest_stix_to_postgres
    print("Downloading ATT&CK STIX data …")
    n = ingest_stix_to_postgres(pg_dsn)
    print(f"✅  Ingested {n} ATT&CK techniques into Postgres")


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
    parser.add_argument("--ingest-attack", metavar="PG_DSN",
                        help="Ingest ATT&CK STIX into Postgres (provide DSN)")
    parser.add_argument("--ingest-previews", action="store_true",
                        help="Ingest preview files into vector store")
    parser.add_argument("--collection", help="Vector store collection name for ingestion")
    parser.add_argument("--limit", type=int, help="Limit number of preview files to ingest")
    
    # Batch enrichment
    parser.add_argument("--batch-enrich", action="store_true",
                        help="Run batch enrichment for all scenarios in a framework")
    parser.add_argument("--framework", choices=list_frameworks(),
                        help="Compliance framework to use (default: cis_controls_v8_1)")
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
    parser.add_argument("--checkpoint-dir", help="Directory for checkpoint files")
    parser.add_argument("--no-resume", action="store_true",
                        help="Don't resume from checkpoint (start fresh)")
    parser.add_argument("--background", "-bg", action="store_true",
                        help="Run in background (daemon mode)")
    parser.add_argument("--status", action="store_true",
                        help="Check status of running/previous batch enrichment")
    parser.add_argument("--clear-checkpoint", action="store_true",
                        help="Clear existing checkpoint and start fresh")
    
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

    if args.ingest_attack:
        cmd_ingest_attack(args.ingest_attack)
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

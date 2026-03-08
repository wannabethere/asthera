#!/usr/bin/env python3
"""
Run the full Dashboard Agent ingestion pipeline.

Orchestrates Phase A (taxonomy generation), Phase B (vector store ingestion),
and optional metrics registry ingestion per docs/dashboard_design/INGESTION_PLAN.md.

Usage:
    # Full pipeline (taxonomy + templates + optional metrics)
    python scripts/run_dashboard_ingestion.py

    # Skip taxonomy (use existing)
    python scripts/run_dashboard_ingestion.py --skip-taxonomy

    # Skip template ingestion
    python scripts/run_dashboard_ingestion.py --skip-templates

    # Include L&D metrics registry
    python scripts/run_dashboard_ingestion.py --metrics

    # Dry run (print commands only)
    python scripts/run_dashboard_ingestion.py --dry-run
"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Project root
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def run_cmd(cmd: list[str], dry_run: bool = False) -> bool:
    """Run a command; return True on success."""
    if dry_run:
        print(f"  [dry-run] {' '.join(cmd)}")
        return True
    result = subprocess.run(cmd, cwd=BASE_DIR)
    return result.returncode == 0


def check_file(path: Path, label: str) -> bool:
    """Check if file exists; print status."""
    exists = path.exists()
    status = "OK" if exists else "MISSING"
    print(f"  {label}: {status}")
    return exists


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Dashboard Agent ingestion pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--skip-taxonomy",
        action="store_true",
        help="Skip Phase A (generate + enrich taxonomy)",
    )
    parser.add_argument(
        "--skip-templates",
        action="store_true",
        help="Skip Phase B1 (ingest dashboard templates)",
    )
    parser.add_argument(
        "--metrics",
        action="store_true",
        help="Run Phase B2 (ingest dashboard metrics registry for L&D/CSOD)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands only, do not execute",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=20,
        help="Max samples for taxonomy generation (default: 20)",
    )
    args = parser.parse_args()

    # Paths
    try:
        from app.config.dashboard_paths import (
            DASHBOARD_DATA_DIR,
            DASHBOARD_CONFIG_DIR,
            get_templates_registry_path,
            get_dashboard_domain_taxonomy_path,
            get_dashboard_domain_taxonomy_enriched_path,
            get_metric_use_case_groups_path,
            get_control_domain_taxonomy_path,
        )
    except ImportError:
        print("Error: Could not import dashboard_paths. Ensure you run from complianceskill/.")
        return 1

    templates_dir = str(DASHBOARD_DATA_DIR)
    taxonomy_out = str(get_dashboard_domain_taxonomy_path())
    taxonomy_enriched_out = str(get_dashboard_domain_taxonomy_enriched_path())

    print("=" * 60)
    print("Dashboard Agent Ingestion")
    print("=" * 60)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Project root: {BASE_DIR}")
    if args.dry_run:
        print("Mode: DRY RUN (no changes)")
    print()

    # Prereq check
    if not get_templates_registry_path().exists():
        print("Error: templates_registry.json not found in data/dashboard/")
        print("  Expected: ", get_templates_registry_path())
        return 1

    # Phase A: Taxonomy
    if not args.skip_taxonomy:
        print("Phase A: Taxonomy Generation")
        print("-" * 40)
        ok = run_cmd(
            [
                sys.executable,
                "-m",
                "app.ingestion.generate_dashboard_taxonomy",
                "--templates-dir",
                templates_dir,
                "--output",
                taxonomy_out,
                "--max-samples",
                str(args.max_samples),
            ],
            dry_run=args.dry_run,
        )
        if not ok:
            print("Failed: generate_dashboard_taxonomy")
            return 1

        ok = run_cmd(
            [
                sys.executable,
                "-m",
                "app.ingestion.enrich_dashboard_taxonomy",
                "--input",
                taxonomy_out,
                "--output",
                taxonomy_enriched_out,
                "--templates-dir",
                templates_dir,
                "--method",
                "llm",
            ],
            dry_run=args.dry_run,
        )
        if not ok:
            print("Failed: enrich_dashboard_taxonomy")
            return 1

        # Build keyword index from taxonomy (reduces taxonomy slice for matching/prompts)
        if not args.dry_run:
            try:
                from app.agents.dashboard_agent.taxonomy_matcher import build_and_save_keyword_index
                idx_path = build_and_save_keyword_index()
                print(f"  Built taxonomy_keyword_index.json ({idx_path.stat().st_size} bytes)")
            except Exception as e:
                print(f"  Warning: Could not build keyword index: {e}")
        print()
    else:
        print("Phase A: Skipped (--skip-taxonomy)")
        print()

    # Phase B1: Ingest templates
    if not args.skip_templates:
        print("Phase B1: Ingest Dashboard Templates")
        print("-" * 40)
        ok = run_cmd(
            [
                sys.executable,
                "-m",
                "app.ingestion.ingest_dashboard_templates",
                "--reinit",
                "--verify",
            ],
            dry_run=args.dry_run,
        )
        if not ok:
            print("Failed: ingest_dashboard_templates")
            return 1
        print()
    else:
        print("Phase B1: Skipped (--skip-templates)")
        print()

    # Phase B2: Metrics registry (optional)
    if args.metrics:
        print("Phase B2: Ingest Dashboard Metrics Registry")
        print("-" * 40)
        ok = run_cmd(
            [
                sys.executable,
                "-m",
                "app.ingestion.ingest_dashboard_metrics_registry",
                "--templates-dir",
                templates_dir,
                "--output-collection",
                "dashboard_metrics_registry",
                "--reinit",
            ],
            dry_run=args.dry_run,
        )
        if not ok:
            print("Failed: ingest_dashboard_metrics_registry")
            return 1
        print()
    else:
        print("Phase B2: Skipped (use --metrics for L&D/CSOD flows)")
        print()

    # Report
    print("=" * 60)
    print("Ingestion Report")
    print("=" * 60)
    print("Phase A - Taxonomy:")
    check_file(get_dashboard_domain_taxonomy_path(), "dashboard_domain_taxonomy.json")
    check_file(get_dashboard_domain_taxonomy_enriched_path(), "dashboard_domain_taxonomy_enriched.json")
    try:
        from app.config.dashboard_paths import get_taxonomy_keyword_index_path
        check_file(get_taxonomy_keyword_index_path(), "taxonomy_keyword_index.json")
    except ImportError:
        pass
    print("Phase C - File-based config:")
    check_file(get_metric_use_case_groups_path(), "metric_use_case_groups.json")
    check_file(get_control_domain_taxonomy_path(), "control_domain_taxonomy.json")
    print()
    print("Ingestion complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

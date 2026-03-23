#!/usr/bin/env python3
"""
Ingest ATT&CK → control mappings via risk scenarios (YAML mitigated_by) + enriched taxonomy.

Loads scenarios from data/cvedata/risk_control_yaml/... and enriched JSON from
control_taxonomy_enriched/. Reads technique/tactic pairs from Postgres (attack_techniques,
or DISTINCT cve_attack_mappings). Persists to attack_technique_control_mapping and
attack_control_mappings_multi.

Usage (from complianceskill/, with DATABASE_URL or .env):
  python -m indexing_cli.scenario_attack_control_ingest --framework hipaa --dry-run
  python -m indexing_cli.scenario_attack_control_ingest --framework hipaa
  python -m indexing_cli.scenario_attack_control_ingest --all-frameworks

All-framework mode loads one framework's YAML + JSON at a time; pairs are fetched once.
Use larger --pair-chunk-size / --persist-batch-size if stable; smaller if memory-bound.

Background:
  PYTHONPATH=. python -m indexing_cli.scenario_attack_control_ingest --all-frameworks --background \\
    --pair-chunk-size 400 --persist-batch-size 1000 \\
    --log-file ./scenario_attack_control_ingest.log

Optional:
  CVE_DATA_DIR=/path/to/data/cvedata
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import List

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _build_child_argv(args: argparse.Namespace) -> List[str]:
    """Rebuild CLI args for the worker process (no --background / --log-file)."""
    argv: List[str] = []
    if args.all_frameworks:
        argv.append("--all-frameworks")
    elif args.framework:
        argv.extend(["--framework", args.framework])
    if args.dry_run:
        argv.append("--dry-run")
    argv.extend(["--top-k-scenarios", str(args.top_k_scenarios)])
    argv.extend(["--min-score", str(args.min_score)])
    if args.limit_pairs is not None:
        argv.extend(["--limit-pairs", str(args.limit_pairs)])
    if args.cve_data_root is not None:
        argv.extend(["--cve-data-root", str(args.cve_data_root)])
    argv.extend(["--pair-chunk-size", str(args.pair_chunk_size)])
    argv.extend(["--persist-batch-size", str(args.persist_batch_size)])
    if args.fail_on_missing:
        argv.append("--fail-on-missing")
    if getattr(args, "no_mapping_vectors", False):
        argv.append("--no-mapping-vectors")
    if getattr(args, "mapping_vector_batch_size", 64) != 64:
        argv.extend(["--mapping-vector-batch-size", str(args.mapping_vector_batch_size)])
    return argv


def _spawn_background_worker(args: argparse.Namespace) -> int:
    log_path = (
        Path(args.log_file).expanduser().resolve()
        if args.log_file
        else (Path.cwd() / "scenario_attack_control_ingest.log").resolve()
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)

    child = [sys.executable, "-m", "indexing_cli.scenario_attack_control_ingest", *_build_child_argv(args)]
    popen_kw: dict = {
        "cwd": os.getcwd(),
        "env": os.environ.copy(),
    }
    if sys.platform == "win32":
        popen_kw["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | 0x00000008  # DETACHED_PROCESS
    else:
        popen_kw["start_new_session"] = True

    # Parent closes its file object after fork/exec; child keeps a dup'd fd for the log.
    with open(log_path, "ab", buffering=0) as log_f:
        proc = subprocess.Popen(
            child,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            **popen_kw,
        )

    info = {
        "background": True,
        "pid": proc.pid,
        "log_file": str(log_path),
        "command": child,
    }
    print(json.dumps(info, indent=2))
    logger.info("Spawned background worker pid=%s logging to %s", proc.pid, log_path)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Scenario-based ATT&CK → control ingest")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--framework",
        default=None,
        help="hipaa | soc2 | nist_csf_2_0 | iso27001_2022 | iso27001_2013 | cis_controls_v8_1",
    )
    mode.add_argument(
        "--all-frameworks",
        action="store_true",
        help="Run every known framework sequentially (one YAML+JSON in memory at a time)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not write to Postgres")
    parser.add_argument("--top-k-scenarios", type=int, default=15, help="Max scenarios per technique/tactic")
    parser.add_argument("--min-score", type=float, default=0.02, help="Minimum keyword score to keep a scenario")
    parser.add_argument("--limit-pairs", type=int, default=None, help="Cap technique/tactic pairs (debug)")
    parser.add_argument("--cve-data-root", type=Path, default=None, help="Override CVE_DATA_DIR / default data/cvedata")
    parser.add_argument(
        "--pair-chunk-size",
        type=int,
        default=250,
        help="Technique/tactic pairs to expand per in-memory batch before SQL flush (default 250)",
    )
    parser.add_argument(
        "--persist-batch-size",
        type=int,
        default=500,
        help="Rows per INSERT executemany batch (default 500)",
    )
    parser.add_argument(
        "--fail-on-missing",
        action="store_true",
        help="With --all-frameworks: error if any framework's YAML/JSON is missing (default: skip)",
    )
    parser.add_argument(
        "--background",
        action="store_true",
        help="Detach a child process with the same workload args; parent prints pid and exits",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="With --background: append stdout/stderr here (default: ./scenario_attack_control_ingest.log)",
    )
    parser.add_argument(
        "--no-mapping-vectors",
        action="store_true",
        help="Skip Qdrant/Chroma upsert for attack→control mappings (collection attack_control_mappings)",
    )
    parser.add_argument(
        "--mapping-vector-batch-size",
        type=int,
        default=64,
        help="Embedding/upsert batch size for mapping vectors (default 64)",
    )
    args = parser.parse_args()

    if args.background:
        return _spawn_background_worker(args)

    from app.ingestion.attacktocve.scenario_attack_control_ingest import (
        run_all_frameworks_scenario_attack_control_ingest,
        run_scenario_attack_control_ingest,
    )

    try:
        if args.all_frameworks:
            summary = run_all_frameworks_scenario_attack_control_ingest(
                cve_data_root=args.cve_data_root,
                top_k_scenarios=args.top_k_scenarios,
                min_scenario_score=args.min_score,
                dry_run=args.dry_run,
                limit_technique_pairs=args.limit_pairs,
                pair_chunk_size=args.pair_chunk_size,
                persist_batch_size=args.persist_batch_size,
                skip_missing_inputs=not args.fail_on_missing,
                ingest_mapping_vectors=not args.no_mapping_vectors,
                mapping_vector_batch_size=args.mapping_vector_batch_size,
            )
        else:
            summary = run_scenario_attack_control_ingest(
                args.framework,
                cve_data_root=args.cve_data_root,
                top_k_scenarios=args.top_k_scenarios,
                min_scenario_score=args.min_score,
                dry_run=args.dry_run,
                limit_technique_pairs=args.limit_pairs,
                pair_chunk_size=args.pair_chunk_size,
                persist_batch_size=args.persist_batch_size,
                ingest_mapping_vectors=not args.no_mapping_vectors,
                mapping_vector_batch_size=args.mapping_vector_batch_size,
            )
    except Exception as e:
        logger.exception("Ingest failed: %s", e)
        return 1

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

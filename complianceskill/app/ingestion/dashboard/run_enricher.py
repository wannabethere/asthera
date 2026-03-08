"""
CCE Dashboard Enricher — Pipeline Entry Point
===============================================
Runs the full enrichment pipeline in one command.

Usage:
    # Enrich + write JSON only (no DB required):
    python run_enricher.py --output-dir ./enriched

    # Enrich + ingest to Postgres:
    python run_enricher.py --postgres --db-url postgresql://user:pass@localhost/cce

    # Enrich + ingest to vector store (uses VECTOR_STORE_TYPE, CHROMA_STORE_PATH, etc. from settings):
    python run_enricher.py --vector-store

    # Full pipeline:
    python run_enricher.py --postgres --vector-store --output-dir ./enriched

    # Dry run (validate enrichment, write JSON, no DB writes):
    python run_enricher.py --dry-run --output-dir ./enriched

Environment variables (alternative to flags):
    DATABASE_URL      Postgres DSN
    OPENAI_API_KEY    OpenAI API key for embeddings
    VECTOR_STORE_TYPE, CHROMA_STORE_PATH (or Qdrant config) control which store is used
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

# ── Ensure local modules and app are importable ───────────────────────
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
# Project root for app.core.dependencies (used by ingest_vector_store)
PROJECT_ROOT = HERE.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from enricher import (
    enrich_dashboard_registry,
    enrich_ld_templates_registry,
    enrich_lms_metrics,
    build_decision_tree,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("enricher.pipeline")

# ── Source file defaults (data/dashboard/ or same dir) ─────────────────
DATA_DASHBOARD = PROJECT_ROOT / "data" / "dashboard"
DEFAULT_SOURCES = {
    "dashboard_registry":    DATA_DASHBOARD / "dashboard_registry.json",
    "ld_templates_registry": DATA_DASHBOARD / "ld_templates_registry.json",
    "lms_metrics":           DATA_DASHBOARD / "lms_dashboard_metrics.json",
}


def run(args: argparse.Namespace):
    start = datetime.now(timezone.utc)
    logger.info("═" * 60)
    logger.info("CCE Dashboard Enricher — starting pipeline")
    logger.info("═" * 60)

    # ── Step 1: Resolve source file paths ─────────────────────────────
    sources = {
        "dashboard_registry":    Path(args.dashboard_registry    or DEFAULT_SOURCES["dashboard_registry"]),
        "ld_templates_registry": Path(args.ld_templates_registry or DEFAULT_SOURCES["ld_templates_registry"]),
        "lms_metrics":           Path(args.lms_metrics           or DEFAULT_SOURCES["lms_metrics"]),
    }
    for name, path in sources.items():
        if not path.exists():
            logger.error(f"Source file not found: {path} ({name})")
            sys.exit(1)
        logger.info(f"  Source [{name}]: {path}")

    # ── Step 2: Enrich ────────────────────────────────────────────────
    logger.info("\n── ENRICHMENT ──────────────────────────────────────────")

    logger.info("Enriching dashboard_registry...")
    dr_templates = enrich_dashboard_registry(sources["dashboard_registry"])

    logger.info("Enriching ld_templates_registry...")
    ld_templates = enrich_ld_templates_registry(sources["ld_templates_registry"])

    all_templates = dr_templates + ld_templates
    logger.info(f"Total templates enriched: {len(all_templates)}")

    logger.info("Enriching lms metrics...")
    metrics = enrich_lms_metrics(sources["lms_metrics"])
    logger.info(f"Total metrics enriched: {len(metrics)}")

    logger.info("Building decision tree...")
    tree = build_decision_tree(all_templates, metrics)
    logger.info(f"Decision tree built: {sum(len(q.options) for q in tree.questions)} total options across {len(tree.questions)} questions")

    # ── Step 3: Write JSON output ─────────────────────────────────────
    if args.output_dir:
        out = Path(args.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        logger.info(f"\n── JSON OUTPUT → {out} ─────────────────────────────")

        # Templates
        templates_out = [t.dict() for t in all_templates]
        _write_json(out / "enriched_templates.json", {
            "meta": {
                "total": len(all_templates),
                "from_dashboard_registry": len(dr_templates),
                "from_ld_templates": len(ld_templates),
                "generated_at": start.isoformat(),
            },
            "templates": templates_out,
        })
        logger.info(f"  Wrote enriched_templates.json ({len(all_templates)} templates)")

        # Metrics
        metrics_out = [m.dict() for m in metrics]
        _write_json(out / "enriched_metrics.json", {
            "meta": {
                "total": len(metrics),
                "generated_at": start.isoformat(),
            },
            "metrics": metrics_out,
        })
        logger.info(f"  Wrote enriched_metrics.json ({len(metrics)} metrics)")

        # Decision tree
        _write_json(out / "decision_tree.json", tree.dict())
        logger.info(f"  Wrote decision_tree.json (v{tree.version})")

        # Embedding texts — for inspection / re-indexing without recomputing
        embedding_texts = {
            "templates": {t.template_id: t.embedding_text for t in all_templates},
            "metrics":   {m.metric_id:   m.embedding_text for m in metrics},
        }
        _write_json(out / "embedding_texts.json", embedding_texts)
        logger.info(f"  Wrote embedding_texts.json")

    # ── Step 4: Postgres ──────────────────────────────────────────────
    if args.postgres and not args.dry_run:
        logger.info("\n── POSTGRES ─────────────────────────────────────────")
        try:
            from postgres_writer import PostgresWriter
            dsn = args.db_url or os.environ.get("DATABASE_URL")
            if not dsn:
                logger.error("No DATABASE_URL set. Pass --db-url or set DATABASE_URL env var.")
                sys.exit(1)

            pg = PostgresWriter(dsn=dsn)
            pg.create_schema()

            t_ins, t_skip = pg.upsert_templates(all_templates)
            m_ins, m_skip = pg.upsert_metrics(metrics)
            pg.upsert_decision_tree(tree)

            logger.info(f"  Templates: {t_ins} upserted, {t_skip} unchanged")
            logger.info(f"  Metrics:   {m_ins} upserted, {m_skip} unchanged")
            logger.info(f"  Decision tree v{tree.version} stored")

        except Exception as e:
            logger.error(f"Postgres write failed: {e}")
            if args.strict:
                raise

    # ── Step 5: Vector Store (via app dependencies) ────────────────────
    if args.vector_store and not args.dry_run:
        logger.info("\n── VECTOR STORE ─────────────────────────────────────")
        try:
            from ingest_vector_store import ingest_dashboard_to_vector_store

            result = ingest_dashboard_to_vector_store(all_templates, metrics, tree)
            t_idx = result.get("layout_templates", 0)
            t_skip = result.get("layout_templates_skipped", 0)
            m_idx = result.get("metric_catalog", 0)
            m_skip = result.get("metric_catalog_skipped", 0)
            dt_idx = result.get("decision_tree_options", 0)

            logger.info(f"  layout_templates:      {t_idx} indexed, {t_skip} skipped")
            logger.info(f"  metric_catalog:       {m_idx} indexed, {m_skip} skipped")
            logger.info(f"  decision_tree_options: {dt_idx} options indexed")

        except Exception as e:
            logger.error(f"Vector store write failed: {e}")
            if args.strict:
                raise

    # ── Summary ───────────────────────────────────────────────────────
    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    logger.info("\n── SUMMARY ──────────────────────────────────────────────")
    logger.info(f"  Templates enriched : {len(all_templates)} ({len(dr_templates)} security + {len(ld_templates)} L&D)")
    logger.info(f"  Metrics enriched   : {len(metrics)}")
    logger.info(f"  Decision tree      : v{tree.version}, {len(tree.questions)} questions")
    logger.info(f"  Elapsed            : {elapsed:.1f}s")
    logger.info(f"  Mode               : {'DRY RUN' if args.dry_run else 'LIVE'}")
    logger.info("═" * 60)

    return {
        "templates": all_templates,
        "metrics":   metrics,
        "tree":      tree,
    }


def _write_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def main():
    parser = argparse.ArgumentParser(
        description="CCE Dashboard Enricher — enrich registries and ingest into Postgres + vector store"
    )

    # Source files
    parser.add_argument("--dashboard-registry",    help="Path to dashboard_registry.json")
    parser.add_argument("--ld-templates-registry", help="Path to ld_templates_registry.json")
    parser.add_argument("--lms-metrics",           help="Path to lms_dashboard_metrics.json")

    # Output
    parser.add_argument("--output-dir", default="./enriched_output",
                        help="Directory for JSON output files (default: ./enriched_output)")

    # Ingest targets
    parser.add_argument("--postgres",     action="store_true", help="Write to Postgres")
    parser.add_argument("--vector-store", action="store_true", help="Write to vector store")

    # Connection config
    parser.add_argument("--db-url",    help="Postgres DSN (or set DATABASE_URL)")
    parser.add_argument("--chroma-dir", help="(Deprecated) Vector store config now from settings")

    # Flags
    parser.add_argument("--dry-run", action="store_true",
                        help="Enrich and write JSON only, skip all DB writes")
    parser.add_argument("--strict",  action="store_true",
                        help="Raise on any DB write error instead of logging and continuing")

    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()

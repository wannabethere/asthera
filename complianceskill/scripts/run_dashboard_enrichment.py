#!/usr/bin/env python3
"""
Manually enrich dashboard data from source registries.

Reads:
  - data/dashboard/dashboard_registry.json
  - data/dashboard/ld_templates_registry.json
  - data/dashboard/lms_dashboard_metrics.json

Writes to app/ingestion/dashboard/:
  - enriched_templates.json
  - enriched_metrics.json
  - decision_tree.json
  - embedding_texts.json

Usage (from complianceskill root):
  python scripts/run_dashboard_enrichment.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root for app imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Add dashboard dir so "models" resolves
DASHBOARD_DIR = PROJECT_ROOT / "app" / "ingestion" / "dashboard"
sys.path.insert(0, str(DASHBOARD_DIR))

from enricher import (
    enrich_dashboard_registry,
    enrich_ld_templates_registry,
    enrich_lms_metrics,
    build_decision_tree,
)

DATA_DIR = PROJECT_ROOT / "data" / "dashboard"
SOURCES = {
    "dashboard_registry": DATA_DIR / "dashboard_registry.json",
    "ld_templates_registry": DATA_DIR / "ld_templates_registry.json",
    "lms_metrics": DATA_DIR / "lms_dashboard_metrics.json",
}
OUTPUT_DIR = DASHBOARD_DIR


def main():
    start = datetime.now(timezone.utc)
    print("=" * 60)
    print("Dashboard Enrichment — manual run from source registries")
    print("=" * 60)

    for name, path in SOURCES.items():
        if not path.exists():
            print(f"ERROR: Source not found: {path}")
            sys.exit(1)
        print(f"  Source [{name}]: {path}")

    # Enrich
    print("\n-- ENRICHMENT --")
    dr_templates = enrich_dashboard_registry(SOURCES["dashboard_registry"])
    ld_templates = enrich_ld_templates_registry(SOURCES["ld_templates_registry"])
    all_templates = dr_templates + ld_templates
    metrics = enrich_lms_metrics(SOURCES["lms_metrics"])
    tree = build_decision_tree(all_templates, metrics)

    print(f"  Templates: {len(all_templates)} ({len(dr_templates)} security + {len(ld_templates)} L&D)")
    print(f"  Metrics: {len(metrics)}")
    print(f"  Decision tree: v{tree.version}")

    # Write outputs
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # enriched_templates.json
    templates_data = {
        "meta": {
            "total": len(all_templates),
            "from_dashboard_registry": len(dr_templates),
            "from_ld_templates": len(ld_templates),
            "generated_at": start.isoformat(),
        },
        "templates": [_to_dict(t) for t in all_templates],
    }
    _write_json(OUTPUT_DIR / "enriched_templates.json", templates_data)
    print(f"\n  Wrote enriched_templates.json ({len(all_templates)} templates)")

    # enriched_metrics.json
    metrics_data = {
        "meta": {"total": len(metrics), "generated_at": start.isoformat()},
        "metrics": [_to_dict(m) for m in metrics],
    }
    _write_json(OUTPUT_DIR / "enriched_metrics.json", metrics_data)
    print(f"  Wrote enriched_metrics.json ({len(metrics)} metrics)")

    # decision_tree.json
    tree_dict = _to_dict(tree)
    _write_json(OUTPUT_DIR / "decision_tree.json", tree_dict)
    print(f"  Wrote decision_tree.json (v{tree.version})")

    # embedding_texts.json
    embedding_texts = {
        "templates": {t.template_id: t.embedding_text for t in all_templates},
        "metrics": {m.metric_id: m.embedding_text for m in metrics},
    }
    _write_json(OUTPUT_DIR / "embedding_texts.json", embedding_texts)
    print(f"  Wrote embedding_texts.json")

    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    print(f"\n  Done in {elapsed:.1f}s")
    print("=" * 60)


def _to_dict(obj):
    """Pydantic v1 uses .dict(), v2 uses .model_dump()."""
    return obj.model_dump() if hasattr(obj, "model_dump") else obj.dict()


def _write_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


if __name__ == "__main__":
    main()

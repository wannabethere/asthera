#!/usr/bin/env python3
"""
Upsert CWE→CAPEC→ATT&CK mapping rows into the vector collection
``threat_intel_cwe_capec_attack_mappings`` (or ``THREAT_INTEL_CWE_CAPEC_ATTACK_COLLECTION``).

Prerequisites:
  - Table ``cwe_capec_attack_mappings`` populated (e.g. ``cwe_capec_attack_mapper`` / DB ingest).
  - Vector store configured (.env: Chroma or Qdrant + OpenAI embeddings).

Usage (from complianceskill/, PYTHONPATH=.):
  python -m indexing_cli.cwe_capec_attack_vector_ingest --from-db
  python -m indexing_cli.cwe_capec_attack_vector_ingest --from-json path/to/cwe_capec_attack_mappings.json
  python -m indexing_cli.cwe_capec_attack_vector_ingest --from-db --batch-size 100
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest CWE→CAPEC→ATT&CK mappings into vector store")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--from-db",
        action="store_true",
        help="Load rows from Postgres cwe_capec_attack_mappings (with optional CWE/technique joins)",
    )
    src.add_argument(
        "--from-json",
        metavar="PATH",
        help="Load array JSON (same shape as cwe_capec_attack_mappings.json)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Documents per upsert batch (default 50)",
    )
    parser.add_argument(
        "--collection",
        default=None,
        help="Override collection name (else settings.THREAT_INTEL_CWE_CAPEC_ATTACK_COLLECTION)",
    )
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY is not set; embedding calls may fail.")

    try:
        from app.core.settings import get_settings

        get_settings()
    except Exception as e:
        logger.error("Failed to load settings: %s", e)
        return 1

    from app.ingestion.cwe_threat_intel.cwe_capec_attack_vector_ingest import (
        cwe_capec_attack_collection_name,
        ingest_cwe_capec_attack_mappings_from_db,
        ingest_cwe_capec_attack_mappings_from_json,
    )

    coll = args.collection or cwe_capec_attack_collection_name()
    logger.info("Collection: %r", coll)

    try:
        if args.from_db:
            n = ingest_cwe_capec_attack_mappings_from_db(
                collection_name=args.collection,
                batch_size=args.batch_size,
            )
        else:
            n = ingest_cwe_capec_attack_mappings_from_json(
                args.from_json,
                collection_name=args.collection,
                batch_size=args.batch_size,
            )
    except Exception as e:
        logger.exception("Ingest failed: %s", e)
        return 1

    logger.info("Done. Upserted %s vectors.", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Ingest CWE CSV files into DB. Loads from local CSV folder, deduplicates by CWE-ID, upserts to cwe_entries.

Usage:
  python -m indexing_cli.cwe_csv_ingest --cwe-dir /Users/sameermangalampalli/data/cwe

Run this first to populate cwe_entries, then use cwe_enrich for CAPEC/NVD/ATT&CK/KEV (skips CWE API).
"""

from __future__ import annotations

import csv
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def _normalize_cwe_id(val: Any) -> str | None:
    """Normalize to CWE-{id} format."""
    if val is None or val == "":
        return None
    s = str(val).strip()
    if not s:
        return None
    if s.upper().startswith("CWE-"):
        return s
    if s.isdigit():
        return f"CWE-{s}"
    return f"CWE-{s}" if not s.startswith("CWE") else s


def _parse_cwe_csv(path: Path) -> List[Dict[str, Any]]:
    """Parse a single CWE CSV file. Returns list of row dicts."""
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cwe_id = _normalize_cwe_id(row.get("CWE-ID") or row.get("CWE_ID") or row.get("cwe_id"))
            if not cwe_id:
                continue
            rows.append({
                "cwe_id": cwe_id,
                "name": (row.get("Name") or "").strip().replace("\n", " ")[:500],
                "description": (row.get("Description") or "").strip().replace("\n", " ")[:5000],
                "extended_description": (row.get("Extended Description") or "").strip()[:5000],
                "weakness_abstraction": (row.get("Weakness Abstraction") or "").strip(),
                "status": (row.get("Status") or "").strip(),
                "related_weaknesses": (row.get("Related Weaknesses") or "").strip()[:2000],
                "related_attack_patterns": (row.get("Related Attack Patterns") or "").strip()[:2000],
                "raw_row": dict(row),
            })
    return rows


def load_and_dedupe(cwe_dir: Path) -> Dict[str, Dict[str, Any]]:
    """
    Load all CWE CSV files, deduplicate by cwe_id.
    When duplicates exist, keep the row with longer description (more complete).
    """
    csv_files = sorted(cwe_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No *.csv files in {cwe_dir}")

    all_entries: Dict[str, Dict[str, Any]] = {}
    total_rows = 0
    for path in csv_files:
        try:
            rows = _parse_cwe_csv(path)
            total_rows += len(rows)
            for row in rows:
                cid = row["cwe_id"]
                existing = all_entries.get(cid)
                # Keep row with longer description (more complete)
                if existing is None or len(row.get("description", "") or "") > len(existing.get("description", "") or ""):
                    all_entries[cid] = row
        except Exception as e:
            logger.warning(f"Failed to parse {path}: {e}")

    return all_entries, total_rows


def ingest_to_db(entries: Dict[str, Dict[str, Any]]) -> int:
    """Upsert CWE entries into cwe_entries table."""
    from app.storage.sqlalchemy_session import get_security_intel_session
    from sqlalchemy import text

    from app.ingestion.cwe_threat_intel.db_schema import create_cwe_threat_intel_tables

    total = len(entries)
    count = 0
    with get_security_intel_session("cve_attack") as session:
        create_cwe_threat_intel_tables(session)
        for i, (cwe_id, row) in enumerate(entries.items()):
            name = row.get("name", "")
            desc = row.get("description", "") or row.get("extended_description", "")
            raw_data = {
                "name": name,
                "description": desc,
                "weakness_abstraction": row.get("weakness_abstraction"),
                "status": row.get("status"),
                "related_weaknesses": row.get("related_weaknesses"),
                "related_attack_patterns": row.get("related_attack_patterns"),
            }
            session.execute(
                text("""
                    INSERT INTO cwe_entries (cwe_id, raw_data, name, description, updated_at)
                    VALUES (:cwe_id, :raw_data, :name, :description, NOW())
                    ON CONFLICT (cwe_id) DO UPDATE SET
                        raw_data = EXCLUDED.raw_data,
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        updated_at = NOW()
                """),
                {
                    "cwe_id": cwe_id,
                    "raw_data": json.dumps(raw_data),
                    "name": name,
                    "description": desc,
                },
            )
            count += 1
            if (i + 1) % 500 == 0 or (i + 1) == total:
                print(f"  Ingested {i + 1}/{total}...", flush=True)
    return count


def main(cwe_dir: str, vector_store: bool = False) -> None:
    path = Path(cwe_dir)
    if not path.exists():
        logger.error(f"Directory not found: {path}")
        sys.exit(1)

    print(f"Loading CWE CSVs from {path}...", flush=True)
    csv_files = sorted(path.glob("*.csv"))
    if not csv_files:
        logger.error(f"No *.csv files in {path}")
        sys.exit(1)
    print(f"  Found {len(csv_files)} files: {[f.name for f in csv_files]}", flush=True)

    entries, total_rows = load_and_dedupe(path)
    print(f"  Parsed {total_rows} rows (before dedupe)", flush=True)
    print(f"  Deduplicated: {len(entries)} unique CWE entries", flush=True)

    print("Ingesting into DB...", flush=True)
    count = ingest_to_db(entries)
    print(f"Done. Ingested {count} CWE entries into cwe_entries.", flush=True)

    if vector_store:
        print("Ingesting into vector store for search...", flush=True)
        try:
            from app.ingestion.cwe_threat_intel.vector_store_ingest import ingest_cwe_to_vector_store
            vs_count = ingest_cwe_to_vector_store(entries)
            print(f"  Ingested {vs_count} CWE entries into threat_intel_cwe_capec.", flush=True)
        except Exception as e:
            logger.error(f"Vector store ingest failed: {e}")
            raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest CWE CSV files into DB")
    parser.add_argument("--cwe-dir", required=True, help="Path to folder containing CWE CSV files")
    parser.add_argument("--vector-store", action="store_true", help="Also ingest into vector store for semantic search")
    args = parser.parse_args()
    main(args.cwe_dir, vector_store=args.vector_store)

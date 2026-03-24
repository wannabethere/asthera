#!/usr/bin/env python3
"""
Ingest CAPEC CSV files into DB. Loads from local CSV folder, deduplicates by CAPEC-ID,
parses Related Weaknesses for CWE links, upserts to capec and cwe_to_capec tables.

Usage:
  python -m indexing_cli.capec_csv_ingest --capec-dir /Users/sameermangalampalli/data/capec

Run after cwe_csv_ingest. Then use cwe_enrich with --capec-from-db to skip CAPEC XML fetch.
"""

from __future__ import annotations

import csv
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def _strip_quotes(s: str) -> str:
    """Strip leading/trailing single or double quotes."""
    if not s:
        return ""
    return str(s).strip().strip("'\"")


def _normalize_capec_id(val: Any) -> str | None:
    """Normalize to CAPEC-{id} format."""
    if val is None or val == "":
        return None
    s = _strip_quotes(str(val))
    if not s or not s.replace("-", "").isdigit():
        return None
    if s.upper().startswith("CAPEC-"):
        return s
    return f"CAPEC-{s}"


def _parse_related_weaknesses(val: str) -> List[str]:
    """Parse Related Weaknesses (e.g. '::120::119::131::') to ['CWE-120', 'CWE-119', 'CWE-131']."""
    if not val:
        return []
    parts = re.split(r"::+", _strip_quotes(val))
    cwe_ids: List[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if p.isdigit():
            cwe_ids.append(f"CWE-{p}")
        elif p.upper().startswith("CWE-"):
            cwe_ids.append(p)
    return list(dict.fromkeys(cwe_ids))


def _parse_capec_csv(path: Path) -> List[Dict[str, Any]]:
    """Parse a single CAPEC CSV file. Returns list of row dicts."""
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Handle 'ID column (leading quote in header)
            id_val = row.get("'ID") or row.get("ID") or row.get("id")
            capec_id = _normalize_capec_id(id_val)
            if not capec_id:
                continue
            rw_raw = row.get("Related Weaknesses") or ""
            related_cwes = _parse_related_weaknesses(rw_raw)
            rows.append({
                "capec_id": capec_id,
                "name": _strip_quotes(row.get("Name") or "").replace("\n", " ")[:500],
                "description": _strip_quotes(row.get("Description") or "").replace("\n", " ")[:5000],
                "abstraction": _strip_quotes(row.get("Abstraction") or ""),
                "status": _strip_quotes(row.get("Status") or ""),
                "related_cwes": related_cwes,
                "raw_row": dict(row),
            })
    return rows


def load_and_dedupe(capec_dir: Path) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Set[str]], int]:
    """
    Load all CAPEC CSV files, deduplicate by capec_id.
    Returns (capec_by_id, cwe_to_capec, total_rows).
    """
    csv_files = sorted(capec_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No *.csv files in {capec_dir}")

    all_entries: Dict[str, Dict[str, Any]] = {}
    cwe_to_capec: Dict[str, Set[str]] = {}
    total_rows = 0

    for path in csv_files:
        try:
            rows = _parse_capec_csv(path)
            total_rows += len(rows)
            for row in rows:
                cid = row["capec_id"]
                existing = all_entries.get(cid)
                if existing is None or len(row.get("description", "") or "") > len(existing.get("description", "") or ""):
                    all_entries[cid] = row
                # Build cwe_to_capec: map each CWE to its CAPEC IDs (use set to dedupe)
                for cwe_id in row.get("related_cwes", []):
                    if cwe_id and cid:
                        cwe_to_capec.setdefault(cwe_id, set()).add(cid)
        except Exception as e:
            logger.warning(f"Failed to parse {path}: {e}")

    return all_entries, cwe_to_capec, total_rows


def ingest_to_db(
    capec_by_id: Dict[str, Dict[str, Any]],
    cwe_to_capec: Dict[str, Set[str]],
) -> Tuple[int, int]:
    """Upsert into capec and cwe_to_capec tables. Returns (capec_count, cwe_to_capec_count)."""
    from app.storage.sqlalchemy_session import get_security_intel_session
    from sqlalchemy import text

    from app.ingestion.cwe_threat_intel.db_schema import create_cwe_threat_intel_tables

    with get_security_intel_session("cve_attack") as session:
        create_cwe_threat_intel_tables(session)

        capec_total = len(capec_by_id)
        capec_count = 0
        for i, (capec_id, row) in enumerate(capec_by_id.items()):
            name = row.get("name", "")
            desc = row.get("description", "")
            related = row.get("related_cwes", [])
            raw_data = {
                "name": name,
                "description": desc,
                "abstraction": row.get("abstraction"),
                "status": row.get("status"),
                "related_cwes": related,
            }
            session.execute(
                text("""
                    INSERT INTO capec (capec_id, name, description, related_cwes, raw_data, updated_at)
                    VALUES (:capec_id, :name, :description, :related_cwes, :raw_data, NOW())
                    ON CONFLICT (capec_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        related_cwes = EXCLUDED.related_cwes,
                        raw_data = EXCLUDED.raw_data,
                        updated_at = NOW()
                """),
                {
                    "capec_id": capec_id,
                    "name": name,
                    "description": desc,
                    "related_cwes": json.dumps(related),
                    "raw_data": json.dumps(raw_data),
                },
            )
            capec_count += 1
            if (i + 1) % 200 == 0 or (i + 1) == capec_total:
                print(f"  Ingested {i + 1}/{capec_total} CAPEC entries...", flush=True)

        cwe_capec_count = 0
        for cwe_id, capec_ids in cwe_to_capec.items():
            for capec_id in capec_ids or []:
                if not cwe_id or not capec_id:
                    continue
                try:
                    session.execute(
                        text("""
                            INSERT INTO cwe_to_capec (cwe_id, capec_id)
                            VALUES (:cwe_id, :capec_id)
                            ON CONFLICT (cwe_id, capec_id) DO NOTHING
                        """),
                        {"cwe_id": cwe_id, "capec_id": capec_id},
                    )
                    cwe_capec_count += 1
                except Exception:
                    pass
        print(f"  Ingested {cwe_capec_count} CWE→CAPEC links", flush=True)

    return capec_count, cwe_capec_count


def main(capec_dir: str, vector_store: bool = False) -> None:
    path = Path(capec_dir)
    if not path.exists():
        logger.error(f"Directory not found: {path}")
        sys.exit(1)

    print(f"Loading CAPEC CSVs from {path}...", flush=True)
    csv_files = sorted(path.glob("*.csv"))
    if not csv_files:
        logger.error(f"No *.csv files in {path}")
        sys.exit(1)
    print(f"  Found {len(csv_files)} files: {[f.name for f in csv_files]}", flush=True)

    capec_by_id, cwe_to_capec, total_rows = load_and_dedupe(path)
    print(f"  Parsed {total_rows} rows (before dedupe)", flush=True)
    print(f"  Deduplicated: {len(capec_by_id)} unique CAPEC entries", flush=True)
    link_count = sum(len(v) for v in cwe_to_capec.values())
    print(f"  CWE→CAPEC links: {link_count} from {len(cwe_to_capec)} CWEs", flush=True)

    print("Ingesting into DB...", flush=True)
    capec_count, cwe_capec_count = ingest_to_db(capec_by_id, cwe_to_capec)
    print(f"Done. Ingested {capec_count} CAPEC entries, {cwe_capec_count} CWE→CAPEC links.", flush=True)

    if vector_store:
        print("Ingesting into vector store for search...", flush=True)
        try:
            from app.ingestion.cwe_threat_intel.vector_store_ingest import ingest_capec_to_vector_store
            vs_count = ingest_capec_to_vector_store(capec_by_id)
            print(f"  Ingested {vs_count} CAPEC entries into threat_intel_cwe_capec.", flush=True)
        except Exception as e:
            logger.error(f"Vector store ingest failed: {e}")
            raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest CAPEC CSV files into DB")
    parser.add_argument("--capec-dir", required=True, help="Path to folder containing CAPEC CSV files")
    parser.add_argument("--vector-store", action="store_true", help="Also ingest into vector store for semantic search")
    args = parser.parse_args()
    main(args.capec_dir, vector_store=args.vector_store)

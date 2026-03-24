#!/usr/bin/env python3
"""
Enrich a CVE CSV with control IDs from Postgres ``attack_control_mappings_multi``.

Reads ``technique_tactic_pairs`` (``T1190:initial-access|...``) per row, looks up
rows for the given ``framework_id`` values, and fills ``controls_<framework_id>``
columns (pipe-separated control ``item_id`` values), matching the aggregation
style used in ``batch_cve_enrich``.

Usage (from ``complianceskill/``, with ``DATABASE_URL`` or settings):

  PYTHONPATH=. python -m indexing_cli.enrich_csv_attack_control_mappings \\
    -i out.csv -o out_enriched.csv

  PYTHONPATH=. python -m indexing_cli.enrich_csv_attack_control_mappings \\
    -i out.csv --frameworks hipaa iso27001_2013 iso27001_2022 nist_csf_2_0 soc2
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, DefaultDict, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_FRAMEWORKS: Tuple[str, ...] = (
    "hipaa",
    "iso27001_2013",
    "iso27001_2022",
    "nist_csf_2_0",
    "soc2",
)

# Max pairs per unnest join (keep queries planner-friendly)
_PAIR_CHUNK = 400


def _csv_safe(val: Any) -> str:
    if val is None:
        return ""
    s = str(val)
    return s.replace("\r\n", " ").replace("\n", " ").replace("\r", " ").replace("\t", " ")


def _norm_technique(tid: str) -> str:
    return (tid or "").strip().upper()


def _norm_tactic(tactic: str) -> str:
    return (tactic or "").strip().lower().replace(" ", "-")


def _parse_technique_tactic_pairs(cell: str) -> List[Tuple[str, str]]:
    """Parse ``T1190:initial-access|T1005:collection`` into normalized pairs."""
    out: List[Tuple[str, str]] = []
    raw = (cell or "").strip()
    if not raw:
        return out
    for part in raw.split("|"):
        part = part.strip()
        if not part or ":" not in part:
            continue
        tid, tac = part.split(":", 1)
        nt = _norm_technique(tid)
        na = _norm_tactic(tac)
        if nt and na:
            out.append((nt, na))
    return out


def _fallback_pairs_from_columns(
    technique_ids_cell: str,
    tactics_cell: str,
) -> List[Tuple[str, str]]:
    """If ``technique_tactic_pairs`` is empty, zip ``technique_ids`` and ``tactics`` (same length)."""
    tids = [_norm_technique(x) for x in (technique_ids_cell or "").split("|") if x.strip()]
    tacs = [_norm_tactic(x) for x in (tactics_cell or "").split("|") if x.strip()]
    if not tids or len(tids) != len(tacs):
        return []
    return list(zip(tids, tacs))


def _control_column_for_framework(framework_id: str) -> str:
    return f"controls_{framework_id}"


def _collect_pairs_from_rows(rows: List[Dict[str, str]]) -> Set[Tuple[str, str]]:
    seen: Set[Tuple[str, str]] = set()
    for row in rows:
        pairs = _parse_technique_tactic_pairs(row.get("technique_tactic_pairs") or "")
        if not pairs:
            pairs = _fallback_pairs_from_columns(
                row.get("technique_ids") or "",
                row.get("tactics") or "",
            )
        for p in pairs:
            seen.add(p)
    return seen


def _fetch_mappings_for_pairs(
    session,
    pairs: Sequence[Tuple[str, str]],
    frameworks: Sequence[str],
) -> DefaultDict[Tuple[str, str, str], List[Dict[str, Any]]]:
    """
    Return cache (technique_id, tactic, framework_id) -> list of row dicts
    (item_id, relevance_score), ordered by relevance_score descending.
    """
    cache: DefaultDict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    if not pairs or not frameworks:
        return cache

    fws = list(frameworks)
    pair_list = list(pairs)

    for i in range(0, len(pair_list), _PAIR_CHUNK):
        chunk = pair_list[i : i + _PAIR_CHUNK]
        tids = [p[0] for p in chunk]
        tacs = [p[1] for p in chunk]
        q = text(
            """
            SELECT m.technique_id, m.tactic, m.framework_id, m.item_id, m.relevance_score
            FROM attack_control_mappings_multi m
            INNER JOIN (
                SELECT * FROM unnest(CAST(:tids AS text[]), CAST(:tacs AS text[]))
                    AS u(technique_id, tactic)
            ) u USING (technique_id, tactic)
            WHERE m.framework_id = ANY(CAST(:fws AS text[]))
            ORDER BY m.relevance_score DESC NULLS LAST
            """
        )
        result = session.execute(
            q,
            {"tids": tids, "tacs": tacs, "fws": fws},
        )
        for row in result:
            tid, tac, fid, item_id, rel = row[0], row[1], row[2], row[3], row[4]
            key = (_norm_technique(tid), _norm_tactic(tac), (fid or "").strip().lower())
            cache[key].append(
                {
                    "item_id": (item_id or "").strip(),
                    "relevance_score": float(rel) if rel is not None else 0.0,
                }
            )
    return cache


def _dedupe_items_preserve_order(items: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen: Set[str] = set()
    for x in items:
        if not x or x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def enrich_rows(
    rows: List[Dict[str, str]],
    cache: DefaultDict[Tuple[str, str, str], List[Dict[str, Any]]],
    frameworks: Sequence[str],
) -> List[Dict[str, str]]:
    """Return new row dicts with control columns and counts updated."""
    out_rows: List[Dict[str, str]] = []
    for row in rows:
        new_row = dict(row)
        pairs = _parse_technique_tactic_pairs(new_row.get("technique_tactic_pairs") or "")
        if not pairs:
            pairs = _fallback_pairs_from_columns(
                new_row.get("technique_ids") or "",
                new_row.get("tactics") or "",
            )

        control_results: List[Dict[str, Any]] = []
        by_fw: DefaultDict[str, List[str]] = defaultdict(list)

        for tid, tac in pairs:
            for fw in frameworks:
                fid = fw.strip().lower()
                for m in cache.get((tid, tac, fid), []):
                    item = m.get("item_id") or ""
                    if not item:
                        continue
                    control_results.append(
                        {
                            "framework_id": fid,
                            "item_id": item,
                            "relevance_score": m.get("relevance_score", 0.0),
                        }
                    )
                    by_fw[fid].append(item)

        new_row["control_mapping_count"] = str(len(control_results))
        new_row["control_mapping_error"] = ""

        for fw in frameworks:
            col = _control_column_for_framework(fw)
            ordered = _dedupe_items_preserve_order(by_fw.get(fw.strip().lower(), []))
            new_row[col] = "|".join(ordered[:500])

        # Back-compat: single ``controls_iso27001`` merges ISO 2013 + 2022 item IDs
        if "iso27001_2013" in frameworks or "iso27001_2022" in frameworks:
            merged: List[str] = []
            for fw in ("iso27001_2013", "iso27001_2022"):
                if fw in frameworks:
                    merged.extend(by_fw.get(fw, []))
            new_row["controls_iso27001"] = "|".join(_dedupe_items_preserve_order(merged)[:500])

        out_rows.append(new_row)
    return out_rows


def _extend_fieldnames(fieldnames: Optional[List[str]], frameworks: Sequence[str]) -> List[str]:
    base = list(fieldnames or [])
    seen = set(base)
    extra_cols = [_control_column_for_framework(fw) for fw in frameworks]
    for c in extra_cols:
        if c not in seen:
            base.append(c)
            seen.add(c)
    for c in ("controls_iso27001_2013", "controls_iso27001_2022"):
        if c not in seen:
            base.append(c)
            seen.add(c)
    return base


def run(
    input_csv: Path,
    output_csv: Path,
    frameworks: Sequence[str],
) -> Dict[str, Any]:
    from app.storage.sqlalchemy_session import get_security_intel_session

    frameworks = tuple((f or "").strip().lower() for f in frameworks if (f or "").strip())
    if not frameworks:
        frameworks = tuple(DEFAULT_FRAMEWORKS)

    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    with open(input_csv, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        in_fieldnames = reader.fieldnames or []
        rows = list(reader)

    all_pairs = _collect_pairs_from_rows(rows)
    logger.info("Rows: %d, distinct (technique, tactic) pairs: %d", len(rows), len(all_pairs))

    cache: DefaultDict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    if all_pairs:
        with get_security_intel_session("cve_attack") as session:
            cache = _fetch_mappings_for_pairs(session, sorted(all_pairs), frameworks)
        total_cells = sum(len(v) for v in cache.values())
        logger.info("Loaded %d mapping rows into cache keys", total_cells)

    enriched = enrich_rows(rows, cache, frameworks)
    out_fieldnames = _extend_fieldnames(in_fieldnames, frameworks)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in enriched:
            writer.writerow({k: _csv_safe(r.get(k, "")) for k in out_fieldnames})

    nonempty = sum(
        1
        for r in enriched
        if any((r.get(_control_column_for_framework(fw)) or "").strip() for fw in frameworks)
    )
    return {
        "input": str(input_csv),
        "output": str(output_csv),
        "rows": len(enriched),
        "rows_with_any_control": nonempty,
        "frameworks": list(frameworks),
    }


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Enrich CVE CSV from attack_control_mappings_multi (by technique + tactic)."
    )
    p.add_argument("-i", "--input", required=True, type=Path, help="Input CSV path")
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output CSV path (default: <input_stem>_controls_enriched.csv)",
    )
    p.add_argument(
        "--frameworks",
        nargs="*",
        default=list(DEFAULT_FRAMEWORKS),
        help="framework_id values in DB (default: five multi-framework IDs)",
    )
    args = p.parse_args(argv)

    out = args.output
    if out is None:
        out = args.input.with_name(f"{args.input.stem}_controls_enriched{args.input.suffix}")

    try:
        summary = run(args.input, out, tuple(args.frameworks))
    except Exception as e:
        logger.exception("Enrichment failed: %s", e)
        return 1

    logger.info("Wrote %s (%d rows, %d with at least one control column)", summary["output"], summary["rows"], summary["rows_with_any_control"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

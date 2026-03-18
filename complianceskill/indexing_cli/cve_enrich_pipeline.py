"""
CVE Enrichment Pipeline — runs the full CVE → ATT&CK → Control pipeline per pipeline doc.

Implements the three-stage flow from docs/cvetoattack_pipeline.md:
  Stage 1: CVE Enrichment (cve_enrich) — NVD/CIRCL, EPSS, KEV
  Stage 2: CVE → ATT&CK (cve_to_attack_map) — CWE lookup + LLM refinement
  Stage 3: ATT&CK → Control (attack_control_map) — per (technique, tactic, framework)

Uses tools from app.agents.tools: cve_enrich, cve_to_attack_map, attack_control_map.

Usage (run from complianceskill directory):
  # Single CVE → JSON
  python -m indexing_cli.cve_enrich_pipeline --cve CVE-2024-3400 -o result.json

  # Batch from CSV → CSV with all enrichment fields
  python -m indexing_cli.cve_enrich_pipeline -i cves.csv -o cve_enriched.csv

  # With specific frameworks
  python -m indexing_cli.cve_enrich_pipeline -i cves.csv -o out.csv --frameworks cis_v8_1 nist_800_53r5
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# CVE column candidates for CSV auto-detection
CVE_COLUMN_CANDIDATES = ("cve_id", "CVE", "cve", "cveId", "CVE ID", "cve-id")


def _detect_cve_column(headers: List[str]) -> Optional[str]:
    """Detect which column contains CVE IDs."""
    for cand in CVE_COLUMN_CANDIDATES:
        for h in headers:
            if h.strip().lower() == cand.lower():
                return h
    for h in headers:
        if "cve" in h.lower():
            return h
    return None


def _run_full_pipeline(
    cve_id: str,
    frameworks: List[str],
) -> Dict[str, Any]:
    """
    Run the full CVE → ATT&CK → Control pipeline using tools.
    Stage 1: cve_enrich
    Stage 2: cve_to_attack_map
    Stage 3: attack_control_map (per technique, tactic, framework)
    """
    from app.agents.tools.cve_enrichment import _execute_cve_enrich
    from app.agents.tools.cve_attack_mapper import _execute_cve_to_attack_map
    from app.agents.tools.attack_control_mapping import _execute_attack_control_map

    # Stage 1: CVE Enrichment
    cve_detail = _execute_cve_enrich(cve_id)

    # Stage 2: CVE → ATT&CK
    mappings = _execute_cve_to_attack_map(cve_id, cve_detail, frameworks)

    # Stage 3: ATT&CK → Control (per technique, tactic, framework)
    control_results: List[Dict[str, Any]] = []
    for m in mappings:
        for fw in frameworks:
            try:
                results = _execute_attack_control_map(
                    technique_id=m["technique_id"],
                    tactic=m["tactic"],
                    framework_id=fw,
                    cve_id=cve_id,
                    cve_context=cve_detail,
                    persist=True,
                )
                control_results.extend(results)
            except Exception as e:
                logger.warning(
                    f"Control mapping failed for {m['technique_id']}/{m['tactic']}/{fw}: {e}"
                )

    return {
        "cve_id": cve_id,
        "cve_detail": cve_detail,
        "technique_tactic_mappings": mappings,
        "control_mappings": control_results,
    }


def _result_to_csv_row(result: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten pipeline result into a single CSV row."""
    cve_detail = result.get("cve_detail", {})
    mappings = result.get("technique_tactic_mappings", [])
    controls = result.get("control_mappings", [])

    technique_ids = list(dict.fromkeys(m.get("technique_id", "") for m in mappings if m.get("technique_id")))
    tactics = list(dict.fromkeys(m.get("tactic", "") for m in mappings if m.get("tactic")))
    technique_tactic_pairs = [f"{m.get('technique_id', '')}:{m.get('tactic', '')}" for m in mappings]

    # Control IDs per framework
    control_by_fw: Dict[str, List[str]] = {}
    for c in controls:
        fw = c.get("framework_id", "")
        item = c.get("item_id", "")
        if fw and item:
            control_by_fw.setdefault(fw, []).append(item)

    row = {
        "cve_id": result.get("cve_id", ""),
        "description": cve_detail.get("description", ""),
        "cvss_score": cve_detail.get("cvss_score", 0.0),
        "cvss_vector": cve_detail.get("cvss_vector", ""),
        "attack_vector": cve_detail.get("attack_vector", ""),
        "attack_complexity": cve_detail.get("attack_complexity", ""),
        "privileges_required": cve_detail.get("privileges_required", ""),
        "cwe_ids": "|".join(cve_detail.get("cwe_ids") or []),
        "affected_products": "|".join(cve_detail.get("affected_products") or [])[:500],
        "epss_score": cve_detail.get("epss_score", 0.0),
        "exploit_available": cve_detail.get("exploit_available", False),
        "exploit_maturity": cve_detail.get("exploit_maturity", ""),
        "published_date": cve_detail.get("published_date", ""),
        "last_modified": cve_detail.get("last_modified", ""),
        "technique_ids": "|".join(technique_ids),
        "tactics": "|".join(tactics),
        "technique_tactic_pairs": "|".join(technique_tactic_pairs),
        "attack_mapping_count": len(mappings),
        "control_mapping_count": len(controls),
    }
    for fw, items in control_by_fw.items():
        row[f"controls_{fw}"] = "|".join(items[:50])  # Limit per framework
    return row


def run_single(cve_id: str, output_path: str, frameworks: List[str]) -> None:
    """Enrich a single CVE and write JSON output."""
    result = _run_full_pipeline(cve_id, frameworks)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    logger.info(f"Wrote {output_path}")


def run_batch_csv(
    input_csv: str,
    output_csv: str,
    cve_column: Optional[str],
    frameworks: List[str],
    preserve_input: bool,
) -> Dict[str, Any]:
    """Enrich CVEs from CSV and write to output CSV."""
    input_path = Path(input_csv)
    output_path = Path(output_csv)
    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    with open(input_path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = list(reader)

    col = cve_column or _detect_cve_column(headers)
    if not col:
        raise ValueError(
            f"Could not detect CVE column. Headers: {headers}. Use --cve-column."
        )

    # Build output headers
    base_cols = [
        "cve_id", "description", "cvss_score", "cvss_vector", "attack_vector",
        "attack_complexity", "privileges_required", "cwe_ids", "affected_products",
        "epss_score", "exploit_available", "exploit_maturity", "published_date", "last_modified",
        "technique_ids", "tactics", "technique_tactic_pairs",
        "attack_mapping_count", "control_mapping_count",
    ]
    if preserve_input:
        seen = {h.strip().lower() for h in headers}
        out_headers = list(headers)
        for c in base_cols:
            if c.lower() not in seen:
                out_headers.append(c)
                seen.add(c.lower())
        # Add controls_* columns as we discover frameworks
        out_headers_set = set(out_headers)
    else:
        out_headers = list(base_cols)
        out_headers_set = set(out_headers)

    summary = {"processed": 0, "succeeded": 0, "failed": 0, "errors": []}
    output_rows: List[Dict[str, Any]] = []

    for row in rows:
        raw_cve = (row.get(col) or "").strip()
        if not raw_cve:
            if preserve_input:
                output_rows.append(dict(row))
            continue

        summary["processed"] += 1
        try:
            result = _run_full_pipeline(raw_cve, frameworks)
            flat = _result_to_csv_row(result)
            for k in flat:
                if k not in out_headers_set:
                    out_headers.append(k)
                    out_headers_set.add(k)
            if preserve_input:
                merged = dict(row)
                merged.update(flat)
                output_rows.append(merged)
            else:
                output_rows.append(flat)
            summary["succeeded"] += 1
        except Exception as e:
            summary["failed"] += 1
            summary["errors"].append({"cve": raw_cve, "error": str(e)})
            logger.warning(f"Pipeline failed for {raw_cve}: {e}")
            fallback = dict(row) if preserve_input else {}
            fallback.update({"cve_id": raw_cve, "enrichment_error": str(e)[:300]})
            output_rows.append(fallback)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_headers, extrasaction="ignore")
        writer.writeheader()
        for r in output_rows:
            writer.writerow({k: r.get(k, "") for k in out_headers})

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CVE Enrichment Pipeline — CVE → ATT&CK → Control (per pipeline doc)"
    )
    parser.add_argument("--cve", "-c", help="Single CVE ID (e.g. CVE-2024-3400)")
    parser.add_argument("-i", "--input-csv", help="Input CSV with CVE IDs")
    parser.add_argument("-o", "--output", default="cve_enriched.csv",
                        help="Output path (CSV for batch, JSON for single)")
    parser.add_argument("--cve-column", help="CSV column with CVE IDs (auto-detected if omitted)")
    parser.add_argument("--frameworks", nargs="+", default=["cis_v8_1", "nist_800_53r5"],
                        help="Frameworks for control mapping")
    parser.add_argument("--no-preserve-input", action="store_true",
                        help="Do not include original CSV columns in output")

    args = parser.parse_args()

    if args.cve:
        # Single CVE → JSON
        out = args.output if args.output.endswith(".json") else f"{args.output}.json"
        run_single(args.cve, out, args.frameworks)
        print(f"✅ Enriched {args.cve} → {out}")
        return

    if args.input_csv:
        summary = run_batch_csv(
            input_csv=args.input_csv,
            output_csv=args.output,
            cve_column=args.cve_column,
            frameworks=args.frameworks,
            preserve_input=not args.no_preserve_input,
        )
        print(f"\n✅ Done: {summary['succeeded']} enriched, {summary['failed']} failed")
        print(f"   Output: {args.output}")
        if summary["errors"]:
            for e in summary["errors"][:5]:
                print(f"   Error: {e['cve']} — {e['error'][:80]}")
            if len(summary["errors"]) > 5:
                print(f"   ... and {len(summary['errors']) - 5} more")
        return

    parser.error("Provide --cve or -i/--input-csv")


if __name__ == "__main__":
    main()

"""
Batch CVE enrichment from CSV — reads CVE IDs from a CSV, enriches via CVE pipeline, writes to CSV.

Usage:
    python -m app.ingestion.attacktocve.main --enrich-cves-from-csv -i cves.csv -o cve_enriched.csv
    python -m app.ingestion.attacktocve.main --enrich-cves-from-csv -i cves.csv -o out.csv --full-pipeline
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# CVE column name candidates (first match wins)
CVE_COLUMN_CANDIDATES = ("cve_id", "CVE", "cve", "cveId", "CVE ID", "cve-id")


def _detect_cve_column(headers: List[str]) -> Optional[str]:
    """Detect which column contains CVE IDs."""
    headers_lower = [h.strip().lower() for h in headers]
    for cand in CVE_COLUMN_CANDIDATES:
        for h in headers:
            if h.strip().lower() == cand.lower():
                return h
    # Fallback: any column containing "cve"
    for h in headers:
        if "cve" in h.lower():
            return h
    return None


def _row_to_flat_dict(row: Dict[str, Any], cve_column: str) -> Dict[str, Any]:
    """Preserve original row and add enrichment fields. Returns a flat dict for CSV."""
    out = dict(row)
    # Ensure cve_id is present for downstream
    if "cve_id" not in out and cve_column in out:
        out["cve_id"] = out[cve_column]
    return out


def _enrich_single(
    cve_id: str,
    full_pipeline: bool = False,
    frameworks: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Enrich a single CVE. Returns flat dict with all enrichment fields.
    """
    from app.agents.tools.cve_enrichment import _execute_cve_enrich
    from app.agents.tools.cve_attack_mapper import _execute_cve_to_attack_map

    frameworks = frameworks or ["cis_v8_1", "nist_800_53r5"]

    # Stage 1: CVE enrichment
    cve_detail = _execute_cve_enrich(cve_id)

    result = {
        "cve_id": cve_detail.get("cve_id", cve_id),
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
    }

    if full_pipeline:
        # Stage 2: CVE → ATT&CK
        try:
            mappings = _execute_cve_to_attack_map(cve_id, cve_detail, frameworks)
            technique_ids = list(dict.fromkeys(m.get("technique_id", "") for m in mappings if m.get("technique_id")))
            tactics = list(dict.fromkeys(m.get("tactic", "") for m in mappings if m.get("tactic")))
            technique_tactic_pairs = [f"{m.get('technique_id', '')}:{m.get('tactic', '')}" for m in mappings]
            result["technique_ids"] = "|".join(technique_ids)
            result["tactics"] = "|".join(tactics)
            result["technique_tactic_pairs"] = "|".join(technique_tactic_pairs)
            result["attack_mapping_count"] = len(mappings)
            result["attack_mappings_json"] = json.dumps(
                [{"technique_id": m.get("technique_id"), "tactic": m.get("tactic"), "confidence": m.get("confidence"), "rationale": m.get("rationale", "")[:200]} for m in mappings]
            )
        except Exception as e:
            logger.warning(f"CVE→ATT&CK mapping failed for {cve_id}: {e}")
            result["technique_ids"] = ""
            result["tactics"] = ""
            result["technique_tactic_pairs"] = ""
            result["attack_mapping_count"] = 0
            result["attack_mappings_json"] = ""
            result["attack_mapping_error"] = str(e)[:200]

    return result


def enrich_cves_from_csv(
    input_csv: str,
    output_csv: str,
    cve_column: Optional[str] = None,
    full_pipeline: bool = False,
    frameworks: Optional[List[str]] = None,
    preserve_input_columns: bool = True,
) -> Dict[str, Any]:
    """
    Read CVEs from CSV, enrich each, write to output CSV with all new fields.

    Args:
        input_csv: Path to input CSV (must have a column with CVE IDs)
        output_csv: Path to output CSV
        cve_column: Column name containing CVE IDs (auto-detected if None)
        full_pipeline: If True, run Stage 2 (CVE→ATT&CK mapping)
        frameworks: Frameworks for ATT&CK→control (only used if full_pipeline)
        preserve_input_columns: If True, include all input columns in output

    Returns:
        Summary dict: processed, succeeded, failed, errors
    """
    input_path = Path(input_csv)
    output_path = Path(output_csv)
    frameworks = frameworks or ["cis_v8_1", "nist_800_53r5"]

    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    with open(input_path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = list(reader)

    col = cve_column or _detect_cve_column(headers)
    if not col:
        raise ValueError(
            f"Could not detect CVE column. Tried: {CVE_COLUMN_CANDIDATES}. "
            f"Headers: {headers}. Use --cve-column to specify."
        )

    # Output columns: input columns (if preserve) + enrichment columns
    enrich_cols = [
        "cve_id", "description", "cvss_score", "cvss_vector", "attack_vector",
        "attack_complexity", "privileges_required", "cwe_ids", "affected_products",
        "epss_score", "exploit_available", "exploit_maturity", "published_date", "last_modified",
    ]
    if full_pipeline:
        enrich_cols.extend([
            "technique_ids", "tactics", "technique_tactic_pairs",
            "attack_mapping_count", "attack_mappings_json", "attack_mapping_error",
        ])
    enrich_cols.append("enrichment_error")  # For failed rows

    if preserve_input_columns:
        # Avoid duplicates, put enrichment cols after input cols
        seen = set(h.strip().lower() for h in headers)
        out_headers = list(headers)
        for c in enrich_cols:
            if c.lower() not in seen:
                out_headers.append(c)
                seen.add(c.lower())
    else:
        out_headers = enrich_cols

    summary = {"processed": 0, "succeeded": 0, "failed": 0, "errors": []}
    output_rows: List[Dict[str, Any]] = []

    for i, row in enumerate(rows):
        raw_cve = (row.get(col) or "").strip()
        if not raw_cve:
            output_rows.append(_row_to_flat_dict(row, col))
            continue

        summary["processed"] += 1
        try:
            enriched = _enrich_single(raw_cve, full_pipeline=full_pipeline, frameworks=frameworks)
            if preserve_input_columns:
                merged = dict(row)
                merged.update(enriched)
                output_rows.append(merged)
            else:
                output_rows.append(enriched)
            summary["succeeded"] += 1
        except Exception as e:
            summary["failed"] += 1
            summary["errors"].append({"cve": raw_cve, "error": str(e)})
            logger.warning(f"Enrichment failed for {raw_cve}: {e}")
            fallback = dict(row) if preserve_input_columns else {}
            fallback.update({
                "cve_id": raw_cve,
                "description": "",
                "cvss_score": 0,
                "epss_score": 0,
                "enrichment_error": str(e)[:300],
            })
            output_rows.append(fallback)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_headers, extrasaction="ignore")
        writer.writeheader()
        for r in output_rows:
            writer.writerow({k: r.get(k, "") for k in out_headers})

    return summary

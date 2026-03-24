"""
CVE Enrichment Pipeline — runs the full CVE → ATT&CK → Control pipeline per pipeline doc.

Implements the three-stage flow from docs/cvetoattack_pipeline.md:
  Stage 1: CVE Enrichment (cve_enrich) — NVD/CIRCL, EPSS, KEV
  Stage 2: CVE → ATT&CK (cve_to_attack_map) — CWE lookup + LLM refinement
  Stage 3: ATT&CK → Control (attack_control_map) — per (technique, tactic, framework)

Uses tools from app.agents.tools: cve_enrich, cve_to_attack_map, attack_control_map.

Uses DB-backed data when available: cisa_kev (KEV), cwe_technique_mappings (CWE→ATT&CK).
Populate these separately via indexing_cli.cwe_enrich and indexing_cli.cwe_capec_attack_mapper.

Usage (run from complianceskill directory):
  # Single CVE → JSON
  python -m indexing_cli.cve_enrich_pipeline --cve CVE-2024-3400 -o result.json

  # Batch from CSV → CSV with all enrichment fields
  python -m indexing_cli.cve_enrich_pipeline -i cves.csv -o cve_enriched.csv

  # With specific frameworks (omit --frameworks for all under risk_control_yaml)
  python -m indexing_cli.cve_enrich_pipeline -i cves.csv -o out.csv --frameworks cis_v8_1 nist_csf_2_0
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# CVE column candidates for CSV auto-detection
CVE_COLUMN_CANDIDATES = ("cve_id", "CVE", "cve", "cveId", "CVE ID", "cve-id")


def _resolve_frameworks_arg(fw: Optional[List[str]]) -> List[str]:
    """Empty / omitted --frameworks → all frameworks under risk_control_yaml (control taxonomy scope)."""
    if fw:
        return list(fw)
    from app.ingestion.attacktocve.pipeline_frameworks import default_pipeline_framework_ids
    return default_pipeline_framework_ids()


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
    control_errors: List[str] = []
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
                err_msg = str(e)[:200]
                logger.warning(
                    f"Control mapping failed for {m['technique_id']}/{m['tactic']}/{fw}: {e}"
                )
                control_errors.append(f"{m['technique_id']}/{m['tactic']}/{fw}: {err_msg}")

    return {
        "cve_id": cve_id,
        "cve_detail": cve_detail,
        "technique_tactic_mappings": mappings,
        "control_mappings": control_results,
        "control_mapping_error": "; ".join(control_errors)[:500] if control_errors else "",
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
        "control_mapping_error": result.get("control_mapping_error", ""),
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


def preload_nvd_from_csv(
    input_csv: str,
    cve_column: Optional[str] = None,
    nvd_batch_size: int = 10,
) -> Dict[str, Any]:
    """
    Fetch NVD data for all CVEs in CSV and store in cve_intelligence.
    Future enrichment runs will use cache (no refetch).
    """
    from app.ingestion.attacktocve.batch_cve_enrich import (
        _prefetch_epss,
        _prefetch_kev,
        CVE_COLUMN_CANDIDATES,
    )
    from app.agents.tools.cve_enrichment import (
        _get_cached_cve_detail,
        _prefetch_nvd_batch,
        _parse_nvd_to_detail,
        _upsert_cve_intelligence,
    )

    input_path = Path(input_csv)
    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    with open(input_path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = list(reader)

    col = cve_column
    if not col:
        for cand in CVE_COLUMN_CANDIDATES:
            for h in headers:
                if h.strip().lower() == cand.lower():
                    col = h
                    break
            if col:
                break
        if not col:
            for h in headers:
                if "cve" in h.lower():
                    col = h
                    break
    if not col:
        raise ValueError(f"Could not detect CVE column. Headers: {headers}")

    def _norm(s: str) -> str:
        c = (s or "").strip().upper()
        if not c:
            return ""
        if not c.startswith("CVE-"):
            c = f"CVE-{c}" if not c.startswith("CVE") else c
        return c

    cve_ids = list(dict.fromkeys(_norm(r.get(col) or "") for r in rows if (r.get(col) or "").strip()))
    cve_ids = [c for c in cve_ids if c]

    logger.info("Pre-fetching EPSS and KEV...")
    epss_lookup = _prefetch_epss()
    kev_lookup = _prefetch_kev()
    logger.info(f"EPSS: {len(epss_lookup)} | KEV: {len(kev_lookup)}")

    needs_nvd = [c for c in cve_ids if _get_cached_cve_detail(c) is None]
    if not needs_nvd:
        logger.info("All CVEs already in cache. Nothing to fetch.")
        return {"total": len(cve_ids), "cached": len(cve_ids), "fetched": 0, "stored": 0}

    logger.info(f"Fetching NVD for {len(needs_nvd)} CVEs (batch size {nvd_batch_size})...")
    nvd_lookup = _prefetch_nvd_batch(needs_nvd, batch_size=nvd_batch_size)

    stored = 0
    for cid, nvd in nvd_lookup.items():
        if nvd.get("vulnerabilities"):
            epss_score = epss_lookup.get(cid, 0.0)
            epss = {"data": [{"epss": epss_score}]} if epss_score else {}
            kev = cid in kev_lookup
            detail = _parse_nvd_to_detail(cid, nvd, epss, kev)
            _upsert_cve_intelligence(detail)
            stored += 1

    logger.info(f"Stored {stored} CVEs in cve_intelligence. Run enrichment with --skip-nvd to use cache.")
    return {"total": len(cve_ids), "cached": len(cve_ids) - len(needs_nvd), "fetched": len(nvd_lookup), "stored": stored}


def validate_batch(
    input_csv: str,
    cve_column: Optional[str] = None,
    frameworks: Optional[List[str]] = None,
    checkpoint_path: Optional[str] = ".cve_batch_checkpoint.json",
) -> Dict[str, Any]:
    """
    Validate batching without running enrichment. Reports:
    - NVD: CVEs to fetch vs cached, batch size
    - Stage 3: unique triples (deduplication), cached triples
    - Checkpoint: CVEs already done
    """
    import csv
    from pathlib import Path

    frameworks = frameworks or ["cis_v8_1", "nist_800_53r5"]
    cve_col_candidates = ("cve_id", "CVE", "cve", "cveId", "CVE ID", "cve-id")

    def _detect_col(headers: List[str]) -> Optional[str]:
        for c in cve_col_candidates:
            for h in headers:
                if (h or "").strip().lower() == c.lower():
                    return h
        for h in headers:
            if "cve" in (h or "").lower():
                return h
        return None

    def _norm(s: str) -> str:
        c = (s or "").strip().upper()
        if not c:
            return ""
        if not c.startswith("CVE-"):
            c = f"CVE-{c}" if not c.startswith("CVE") else c
        return c

    path = Path(input_csv)
    if not path.exists():
        return {"error": f"Input CSV not found: {input_csv}"}

    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = list(reader)

    col = cve_column or _detect_col(headers)
    if not col:
        return {"error": f"Could not detect CVE column. Headers: {headers}"}

    cve_ids = list(dict.fromkeys(_norm(r.get(col) or "") for r in rows if (r.get(col) or "").strip()))
    cve_ids = [c for c in cve_ids if c]
    total_cves = len(cve_ids)

    # Checkpoint
    done_count = 0
    if checkpoint_path and Path(checkpoint_path).exists():
        try:
            import json
            data = json.loads(Path(checkpoint_path).read_text())
            done = set((c or "").strip().upper() for c in data.get("done", []))
            done_count = len([c for c in cve_ids if c in done])
        except Exception:
            pass

    cves_to_process = total_cves - done_count

    # NVD cache
    needs_nvd = 0
    try:
        from app.agents.tools.cve_enrichment import _get_cached_cve_detail
        for cid in cve_ids[:min(500, len(cve_ids))]:  # Sample up to 500
            if _get_cached_cve_detail(cid) is None:
                needs_nvd += 1
        if len(cve_ids) > 500:
            needs_nvd = int(needs_nvd * len(cve_ids) / 500)  # Extrapolate
    except Exception as e:
        needs_nvd = "unknown (check failed)"

    # Stage 3 triple stats (from cve_attack_mappings if available)
    unique_triples = 0
    cached_triples = 0
    try:
        from app.agents.tools.cve_attack_mapper import _get_attack_mappings_for_cves
        from app.agents.tools.attack_control_mapping import _get_existing_control_mappings

        attack_mappings = _get_attack_mappings_for_cves(cve_ids)
        all_triples: set = set()
        for mappings in attack_mappings.values():
            for m in mappings:
                tid = (m.get("technique_id") or "").strip().upper()
                tactic = (m.get("tactic") or "").strip().lower().replace(" ", "-")
                for fw in frameworks:
                    if tid and tactic:
                        all_triples.add((tid, tactic, fw))
        unique_triples = len(all_triples)
        for tri in all_triples:
            if _get_existing_control_mappings(tri[0], tri[1], tri[2]):
                cached_triples += 1
    except Exception as e:
        unique_triples = "N/A (requires DB)"
        cached_triples = "N/A"

    # NVD batch size (from settings)
    nvd_batch_size = 10
    try:
        from app.core.settings import get_settings
        api_key = get_settings().NVD_API_KEY or __import__("os").environ.get("NVD_API_KEY")
        if not api_key:
            nvd_batch_size = 5
    except Exception:
        pass

    stage3_to_run = (unique_triples - cached_triples) if isinstance(unique_triples, int) and isinstance(cached_triples, int) else "N/A"
    return {
        "total_cves": total_cves,
        "cves_done_checkpoint": done_count,
        "cves_to_process": cves_to_process,
        "nvd_needs_fetch": needs_nvd,
        "nvd_batch_size": nvd_batch_size,
        "stage3_unique_triples": unique_triples,
        "stage3_cached_triples": cached_triples,
        "stage3_to_run": stage3_to_run,
    }


def validate_all_stages(csv_path: str) -> Dict[str, Any]:
    """
    Validate all three pipeline stages on an enriched output CSV.
    Reports pass/fail counts for Stage 1 (CVE enrich), Stage 2 (ATT&CK), Stage 3 (Control).
    """
    from pathlib import Path

    path = Path(csv_path)
    if not path.exists():
        return {"error": f"CSV not found: {csv_path}"}

    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    total = len(rows)
    if total == 0:
        return {"error": "CSV has no data rows"}

    # Stage 1: CVE enrichment (description, cvss_score, epss_score present)
    stage1_ok = sum(1 for r in rows if (r.get("description") or "").strip() and (r.get("cvss_score") or r.get("epss_score") or ""))
    stage1_fail = sum(1 for r in rows if not (r.get("description") or "").strip())
    enrichment_errors = sum(1 for r in rows if (r.get("enrichment_error") or "").strip())

    # Stage 2: ATT&CK mapping (technique_ids or attack_mapping_count > 0)
    stage2_ok = sum(1 for r in rows if int(r.get("attack_mapping_count") or 0) > 0 or (r.get("technique_ids") or "").strip())
    stage2_no_mappings = sum(1 for r in rows if int(r.get("attack_mapping_count") or 0) == 0 and not (r.get("technique_ids") or "").strip())
    attack_errors = sum(1 for r in rows if (r.get("attack_mapping_error") or "").strip())

    # Stage 3: Control mapping (control_mapping_count > 0 or controls_* populated)
    stage3_ok = sum(1 for r in rows if int(r.get("control_mapping_count") or 0) > 0)
    stage3_missing = sum(1 for r in rows if int(r.get("attack_mapping_count") or 0) > 0 and int(r.get("control_mapping_count") or 0) == 0)
    control_errors = sum(1 for r in rows if (r.get("control_mapping_error") or "").strip())

    return {
        "total": total,
        "stage1_ok": stage1_ok,
        "stage1_fail": stage1_fail,
        "enrichment_errors": enrichment_errors,
        "stage2_ok": stage2_ok,
        "stage2_no_mappings": stage2_no_mappings,
        "attack_errors": attack_errors,
        "stage3_ok": stage3_ok,
        "stage3_missing": stage3_missing,
        "control_errors": control_errors,
    }


def run_batch_csv(
    input_csv: str,
    output_csv: str,
    cve_column: Optional[str],
    frameworks: List[str],
    preserve_input: bool,
    checkpoint_path: Optional[str] = ".cve_batch_checkpoint.json",
    epss_csv_path: Optional[str] = None,
    progress_interval: int = 25,
    nvd_batch_size: int = 10,
    skip_nvd: bool = False,
    start_stage: int = 1,
) -> Dict[str, Any]:
    """Enrich CVEs from CSV and write to output CSV. Delegates to batch_cve_enrich with full pipeline."""
    from app.ingestion.attacktocve.batch_cve_enrich import enrich_cves_from_csv

    return enrich_cves_from_csv(
        input_csv=input_csv,
        output_csv=output_csv,
        cve_column=cve_column,
        full_pipeline=True,  # Always run full pipeline (Stage 1 + 2 + 3)
        frameworks=frameworks,
        preserve_input_columns=preserve_input,
        checkpoint_path=checkpoint_path,
        epss_csv_path=epss_csv_path,
        progress_interval=progress_interval,
        nvd_batch_size=nvd_batch_size,
        skip_nvd=skip_nvd,
        start_stage=start_stage,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CVE Enrichment Pipeline — CVE → ATT&CK → Control (per pipeline doc)"
    )
    parser.add_argument("--cve", "-c", help="Single CVE ID (e.g. CVE-2024-3400)")
    parser.add_argument("-i", "--input-csv", help="Input CSV with CVE IDs")
    parser.add_argument("-o", "--output", default="cve_enriched.csv",
                        help="Output path (CSV for batch, JSON for single)")
    parser.add_argument("--cve-column", help="CSV column with CVE IDs (auto-detected if omitted)")
    parser.add_argument(
        "--frameworks",
        nargs="*",
        default=None,
        metavar="FRAMEWORK_ID",
        help=(
            "Framework IDs for Stage 3 control mapping. "
            "Omit or pass no values to use all frameworks discovered under risk_control_yaml "
            "(same scope as control_taxonomy_enriched)."
        ),
    )
    parser.add_argument("--no-preserve-input", action="store_true",
                        help="Do not include original CSV columns in output")
    parser.add_argument("--checkpoint", default=".cve_batch_checkpoint.json",
                        help="Checkpoint file for resume (default: .cve_batch_checkpoint.json)")
    parser.add_argument("--no-checkpoint", action="store_true",
                        help="Disable checkpoint (no resume support)")
    parser.add_argument("--epss-csv", help="Local EPSS CSV path (or set EPSS_CSV_PATH env)")
    parser.add_argument("--background", "-bg", action="store_true",
                        help="Run batch in background (checkpoint + resume supported)")
    parser.add_argument("--progress-interval", type=int, default=25,
                        help="Print progress every N CVEs (default: 25)")
    parser.add_argument("--nvd-batch-size", type=int, default=10,
                        help="NVD API batch size for pre-fetch (default: 10, 5 without API key)")
    parser.add_argument("--skip-nvd", action="store_true",
                        help="Use only cache (cve_intelligence/cve_cache); no NVD pre-fetch or API calls")
    parser.add_argument("--preload-nvd", action="store_true",
                        help="Fetch NVD for all CVEs in CSV and store in DB; then exit (no enrichment)")
    parser.add_argument("--batch-api", action="store_true",
                        help="Use OpenAI Batch API (~50%% cost savings, up to 24h). Requires LLM_PROVIDER=openai.")
    parser.add_argument("--stage3-only", action="store_true",
                        help="Run only Stage 3 (ATT&CK→Control). Uses existing cve_attack_mappings. -i optional (all CVEs if omitted).")
    parser.add_argument("--validate-batch", action="store_true",
                        help="Validate batching (NVD, Stage 3 dedup, checkpoint) without running enrichment. Use with -i.")
    parser.add_argument("--validate-all-stages", action="store_true",
                        help="Validate Stage 1/2/3 on an enriched output CSV. Use with -i (path to enriched CSV).")
    parser.add_argument("--start-stage", type=int, choices=[1, 2, 3], default=1,
                        help="Start from stage 1 (default), 2, or 3. Stage 2: load cve_intelligence, skip NVD. Stage 3: load cve_attack_mappings, skip NVD + Stage 2 LLM.")
    parser.add_argument("--batch-errors", metavar="BATCH_ID",
                        help="Download and show error summary for a failed batch (e.g. batch_69bc18fc4a848190a1b09ee33559a432)")
    parser.add_argument("--openai-batch-chunk-size", type=int, default=0,
                        help="Max requests per OpenAI Batch job (0=auto: smaller chunks when total is large)")

    args = parser.parse_args()
    args.frameworks = _resolve_frameworks_arg(args.frameworks)

    # validate-all-stages: pure CSV read, no app/DB deps — run before loading settings
    if args.validate_all_stages:
        if not args.input_csv:
            parser.error("--validate-all-stages requires -i/--input-csv")
        result = validate_all_stages(args.input_csv)
        if "error" in result:
            print(f"❌ {result['error']}")
            sys.exit(1)
        print("\n" + "=" * 60)
        print("All Stages Validation Report")
        print("=" * 60)
        print(f"  Total records:              {result['total']}")
        print("-" * 60)
        print("  Stage 1 (CVE Enrichment):")
        print(f"    ✓ Enriched (desc+cvss):   {result['stage1_ok']}")
        print(f"    ✗ Missing description:   {result['stage1_fail']}")
        print(f"    ! enrichment_error:       {result['enrichment_errors']}")
        print("-" * 60)
        print("  Stage 2 (CVE → ATT&CK):")
        print(f"    ✓ Has ATT&CK mappings:    {result['stage2_ok']}")
        print(f"    - No mappings:            {result['stage2_no_mappings']}")
        print(f"    ! attack_mapping_error:   {result['attack_errors']}")
        print("-" * 60)
        print("  Stage 3 (ATT&CK → Control):")
        print(f"    ✓ Has control mappings:   {result['stage3_ok']}")
        print(f"    ✗ ATT&CK but no controls: {result['stage3_missing']}")
        print(f"    ! control_mapping_error:  {result['control_errors']}")
        print("=" * 60)
        s1 = "PASS" if result["stage1_fail"] == 0 and result["enrichment_errors"] == 0 else "FAIL"
        s2 = "PASS" if result["attack_errors"] == 0 else "FAIL"
        s3 = "PASS" if result["control_errors"] == 0 else "FAIL"
        print(f"\n  Stage 1: {s1}  |  Stage 2: {s2}  |  Stage 3: {s3}")
        return

    # Load settings (and .env) so NVD_API_KEY is available for NVD API calls
    from app.core.settings import get_settings
    get_settings()

    if args.batch_errors:
        from openai import OpenAI
        from app.core.settings import get_settings
        from app.ingestion.attacktocve.openai_batch import (
            download_batch_errors,
            _summarize_batch_errors,
        )
        batch_id = args.batch_errors.strip()
        s = get_settings()
        api_key = s.OPENAI_API_KEY or __import__("os").environ.get("OPENAI_API_KEY")
        client = OpenAI(api_key=api_key) if api_key else None
        if client:
            b = client.batches.retrieve(batch_id)
            rc = getattr(b, "request_counts", None)
            print(
                f"Batch status={b.status} | "
                f"output_file_id={'yes' if getattr(b, 'output_file_id', None) else 'no'} | "
                f"error_file_id={'yes' if getattr(b, 'error_file_id', None) else 'no'} | "
                f"completed={getattr(rc, 'completed', 0)} failed={getattr(rc, 'failed', 0)}"
            )
        content = download_batch_errors(batch_id)
        if not content:
            print(
                f"No failure lines found for {batch_id}. "
                "If the batch succeeded, there are no errors. "
                "If status is not completed, wait and retry."
            )
            sys.exit(0)
        summary = _summarize_batch_errors(content, max_samples=10)
        print(f"Batch {batch_id} errors:\n{summary}")
        out_path = Path(f"batch_errors_{batch_id}.jsonl")
        out_path.write_text(content, encoding="utf-8")
        print(f"Failure lines saved to {out_path}")
        return

    if args.cve:
        # Single CVE → JSON
        out = args.output if args.output.endswith(".json") else f"{args.output}.json"
        run_single(args.cve, out, args.frameworks)
        print(f"✅ Enriched {args.cve} → {out}")
        return

    if args.validate_batch:
        if not args.input_csv:
            parser.error("--validate-batch requires -i/--input-csv")
        result = validate_batch(
            input_csv=args.input_csv,
            cve_column=args.cve_column,
            frameworks=args.frameworks,
            checkpoint_path=None if args.no_checkpoint else args.checkpoint,
        )
        if "error" in result:
            print(f"❌ {result['error']}")
            sys.exit(1)
        print("\n" + "=" * 60)
        print("Batching Validation Report")
        print("=" * 60)
        print(f"  Total CVEs in CSV:        {result['total_cves']}")
        print(f"  Checkpoint (already done): {result['cves_done_checkpoint']}")
        print(f"  CVEs to process:          {result['cves_to_process']}")
        print("-" * 60)
        print(f"  NVD batch size:           {result['nvd_batch_size']} (concurrent requests)")
        print(f"  NVD needs fetch:          {result['nvd_needs_fetch']} (rest from cache)")
        if isinstance(result['nvd_needs_fetch'], int) and result['nvd_needs_fetch'] > 0:
            batches = (result['nvd_needs_fetch'] + result['nvd_batch_size'] - 1) // result['nvd_batch_size']
            print(f"  NVD batch count:          ~{batches} batches (6s delay between)")
        print("-" * 60)
        print(f"  Stage 3 unique triples:   {result['stage3_unique_triples']} (dedup across CVEs)")
        print(f"  Stage 3 cached:           {result['stage3_cached_triples']}")
        print(f"  Stage 3 to run:           {result['stage3_to_run']}")
        print("=" * 60)
        print("\nBatching is working if:")
        print("  • NVD: Pre-fetches in batches (see 'Phase 1: Pre-fetching NVD' in logs)")
        print("  • Stage 3: Unique triples << per-CVE triples (deduplication)")
        print("  • Checkpoint: Skips done CVEs on resume")
        return

    if args.stage3_only:
        if args.background:
            log_file = f"cve_stage3_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            cmd = [sys.executable, "-m", "indexing_cli.cve_enrich_pipeline", "--stage3-only"]
            if args.input_csv:
                cmd += ["-i", args.input_csv, "-o", args.output]
            cmd += ["--frameworks"] + args.frameworks
            if args.cve_column:
                cmd += ["--cve-column", args.cve_column]
            if args.batch_api:
                cmd += ["--batch-api"]
            print(f"🚀 Starting Stage 3 only in background...")
            print(f"   Log file: {log_file}")
            if args.input_csv:
                print(f"   Output: {args.output}")
            print(f"   tail -f {log_file} to watch progress")
            with open(log_file, "w") as log:
                proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            print(f"   PID: {proc.pid}")
            return

        from app.ingestion.attacktocve.batch_cve_enrich import run_stage3_only
        result = run_stage3_only(
            input_csv=args.input_csv,
            output_csv=args.output if args.input_csv else None,
            cve_column=args.cve_column,
            frameworks=args.frameworks,
            use_batch_api=args.batch_api,
        )
        print(f"\n✅ Stage 3 only: {result['triples_processed']} processed, {result['triples_cached']} cached")
        if args.output and args.input_csv:
            print(f"   Output: {args.output}")
        return

    if args.input_csv:
        if args.preload_nvd:
            result = preload_nvd_from_csv(
                input_csv=args.input_csv,
                cve_column=args.cve_column,
                nvd_batch_size=args.nvd_batch_size,
            )
            print(f"\n✅ Preload complete: {result['stored']} stored, {result['cached']} already cached")
            print(f"   Run enrichment with --skip-nvd to use cache")
            return

        if args.batch_api and args.background:
            log_file = f"cve_batch_api_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            cmd = [sys.executable, "-m", "indexing_cli.cve_enrich_pipeline", "-i", args.input_csv, "-o", args.output, "--batch-api"]
            cmd += ["--frameworks"] + args.frameworks
            if not args.no_checkpoint:
                cmd += ["--checkpoint", args.checkpoint]
            if args.epss_csv:
                cmd += ["--epss-csv", args.epss_csv]
            if args.skip_nvd:
                cmd += ["--skip-nvd"]
            if args.start_stage != 1:
                cmd += ["--start-stage", str(args.start_stage)]
            if args.no_preserve_input:
                cmd += ["--no-preserve-input"]
            cmd += ["--openai-batch-chunk-size", str(args.openai_batch_chunk_size)]
            print(f"🚀 Starting CVE enrichment (OpenAI Batch API) in background...")
            print(f"   Log file: {log_file}")
            print(f"   Output: {args.output}")
            print(f"   tail -f {log_file} to watch progress")
            with open(log_file, "w") as log:
                proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            print(f"   PID: {proc.pid}")
            return

        if args.batch_api:
            from app.ingestion.attacktocve.batch_cve_enrich import enrich_cves_from_csv_batch
            summary = enrich_cves_from_csv_batch(
                input_csv=args.input_csv,
                output_csv=args.output,
                cve_column=args.cve_column,
                frameworks=args.frameworks,
                preserve_input_columns=not args.no_preserve_input,
                checkpoint_path=None if args.no_checkpoint else args.checkpoint,
                epss_csv_path=args.epss_csv,
                nvd_batch_size=args.nvd_batch_size,
                skip_nvd=args.skip_nvd,
                start_stage=args.start_stage,
                openai_batch_chunk_size=args.openai_batch_chunk_size,
            )
            skipped = summary.get("skipped", 0)
            print(f"\n✅ Batch API done: {summary['succeeded']} enriched, {summary['failed']} failed" + (f", {skipped} skipped (resumed)" if skipped else ""))
            print(f"   Output: {args.output}")
            return

        if args.background:
            log_file = f"cve_enrich_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            cmd = [sys.executable, "-m", "indexing_cli.cve_enrich_pipeline", "-i", args.input_csv, "-o", args.output]
            cmd += ["--frameworks"] + args.frameworks
            if not args.no_checkpoint:
                cmd += ["--checkpoint", args.checkpoint]
            if args.epss_csv:
                cmd += ["--epss-csv", args.epss_csv]
            if args.no_preserve_input:
                cmd += ["--no-preserve-input"]
            cmd += ["--progress-interval", str(args.progress_interval)]
            cmd += ["--nvd-batch-size", str(args.nvd_batch_size)]
            if args.skip_nvd:
                cmd += ["--skip-nvd"]
            if args.start_stage != 1:
                cmd += ["--start-stage", str(args.start_stage)]
            print(f"🚀 Starting CVE enrichment in background...")
            print(f"   Log file: {log_file}")
            print(f"   Output: {args.output}")
            print(f"   Resume: re-run same command to continue from checkpoint")
            with open(log_file, "w") as log:
                proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            print(f"   PID: {proc.pid} | tail -f {log_file} to watch progress")
            return

        summary = run_batch_csv(
            input_csv=args.input_csv,
            output_csv=args.output,
            cve_column=args.cve_column,
            frameworks=args.frameworks,
            preserve_input=not args.no_preserve_input,
            checkpoint_path=None if args.no_checkpoint else args.checkpoint,
            epss_csv_path=args.epss_csv,
            progress_interval=args.progress_interval,
            nvd_batch_size=args.nvd_batch_size,
            skip_nvd=args.skip_nvd,
            start_stage=args.start_stage,
        )
        skipped = summary.get("skipped", 0)
        print(f"\n✅ Done: {summary['succeeded']} enriched, {summary['failed']} failed" + (f", {skipped} skipped (resumed)" if skipped else ""))
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

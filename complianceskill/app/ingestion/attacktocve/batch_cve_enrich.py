"""
Batch CVE enrichment from CSV — reads CVE IDs from a CSV, enriches via CVE pipeline, writes to CSV.

Usage:
    python -m app.ingestion.attacktocve.main --enrich-cves-from-csv -i cves.csv -o cve_enriched.csv
    python -m app.ingestion.attacktocve.main --enrich-cves-from-csv -i cves.csv -o out.csv --full-pipeline
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import logging
import requests
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from app.ingestion.attacktocve.pipeline_frameworks import default_pipeline_framework_ids

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Checkpoint Manager
# ---------------------------------------------------------------------------


class CheckpointManager:
    """Prevents re-fetching CVEs already enriched in a previous interrupted run."""

    def __init__(self, path: str = ".cve_batch_checkpoint.json"):
        self._path = Path(path)
        self._done: Set[str] = set()
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text())
                self._done = set(data.get("done", []))
            except Exception as e:
                logger.warning(f"Checkpoint file corrupted or unreadable: {e}. Starting fresh.")

    def is_done(self, cve_id: str) -> bool:
        return cve_id.strip().upper() in self._done

    def mark_done(self, cve_id: str) -> None:
        self._done.add(cve_id.strip().upper())
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps({"done": sorted(self._done)}, indent=2))

    def mark_done_batch(self, cve_ids: List[str]) -> None:
        """Batch checkpoint write (Fix 3: flush every N CVEs instead of every CVE)."""
        if not cve_ids:
            return
        for cid in cve_ids:
            self._done.add(cid.strip().upper())
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps({"done": sorted(self._done)}, indent=2))

    def clear(self) -> None:
        self._path.unlink(missing_ok=True)
        self._done.clear()


# ---------------------------------------------------------------------------
# EPSS + KEV pre-fetch (once per batch run)
# ---------------------------------------------------------------------------


def _prefetch_epss(epss_csv_path: Optional[str] = None) -> Dict[str, float]:
    """Returns {cve_id: epss_score} for all current CVEs. Uses local file if provided (or EPSS_CSV_PATH env), else downloads."""
    try:
        import os
        local_path = epss_csv_path
        if not local_path:
            try:
                from app.core.settings import get_settings
                local_path = get_settings().EPSS_CSV_PATH
            except Exception:
                local_path = os.getenv("EPSS_CSV_PATH")
        if local_path and Path(local_path).exists():
            with open(local_path, "r", encoding="utf-8") as f:
                return _parse_epss_csv(f)
        url = "https://epss.cyentia.com/epss_scores-current.csv.gz"
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        with gzip.open(io.BytesIO(r.content), "rt") as f:
            return _parse_epss_csv(f)
    except Exception as e:
        logger.warning(f"EPSS pre-fetch failed: {e}. Will fall back to per-CVE EPSS API.")
        return {}


def _parse_epss_csv(f) -> Dict[str, float]:
    """Parse EPSS CSV (handles comment lines starting with #)."""
    reader = csv.DictReader((line for line in f if not line.strip().startswith("#")))
    fieldnames = reader.fieldnames or []
    headers_lower = {h.strip().lower(): h for h in fieldnames if h}
    cve_col = headers_lower.get("cve")
    epss_col = headers_lower.get("epss")
    if not cve_col or not epss_col:
        raise ValueError(f"EPSS CSV missing cve/epss columns. Headers: {fieldnames}")
    rows = list(reader)
    if not rows:
        return {}
    return {
        row[cve_col]: float(row.get(epss_col, 0) or 0)
        for row in rows
        if row.get(cve_col)
    }


def _prefetch_kev() -> Set[str]:
    """Returns set of CVE IDs in CISA KEV. Uses DB (cisa_kev) if populated, else downloads."""
    try:
        from app.storage.sqlalchemy_session import get_security_intel_session
        from sqlalchemy import text

        with get_security_intel_session("cve_attack") as session:
            result = session.execute(text("SELECT cve_id FROM cisa_kev"))
            rows = result.fetchall()
            if rows:
                return {r[0] for r in rows if r[0]}
    except Exception as e:
        if "does not exist" not in str(e).lower():
            logger.debug(f"KEV DB lookup failed: {e}")

    try:
        url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
        data = requests.get(url, timeout=30).json()
        return {v["cveID"] for v in data.get("vulnerabilities", [])}
    except Exception as e:
        logger.warning(f"KEV pre-fetch failed: {e}. Will fall back to per-CVE KEV check.")
        return set()

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


def _csv_safe(val: Any) -> str:
    """Replace newlines/tabs in strings so CSV stays one physical line per row (Excel-friendly)."""
    if val is None:
        return ""
    s = str(val)
    return s.replace("\r\n", " ").replace("\n", " ").replace("\r", " ").replace("\t", " ")


def _load_or_fetch_cve_detail(
    cve_id: str,
    start_stage: int,
    epss_lookup: Optional[Dict[str, float]] = None,
    kev_lookup: Optional[Set[str]] = None,
    nvd_lookup: Optional[Dict[str, Dict]] = None,
    skip_nvd_fetch: bool = False,
) -> Dict[str, Any]:
    """Return cve_detail from DB (start_stage>=2) or via live fetch (start_stage=1)."""
    from app.agents.tools.cve_enrichment import _load_cve_detail_from_db, _execute_cve_enrich

    cve_id_norm = cve_id.strip().upper()
    if not cve_id_norm.startswith("CVE-"):
        cve_id_norm = f"CVE-{cve_id_norm}" if not cve_id_norm.startswith("CVE") else cve_id_norm

    if start_stage >= 2:
        detail = _load_cve_detail_from_db(cve_id_norm)
        if detail is None:
            raise ValueError(f"{cve_id_norm} not in cve_intelligence; run Stage 1 first")
        return detail
    return _execute_cve_enrich(
        cve_id_norm,
        epss_lookup=epss_lookup,
        kev_lookup=kev_lookup,
        nvd_lookup=nvd_lookup,
        skip_nvd_fetch=skip_nvd_fetch,
    )


def _load_or_run_stage2(
    cve_id: str,
    cve_detail: Dict[str, Any],
    frameworks: List[str],
    start_stage: int,
) -> List[Dict[str, Any]]:
    """Return mappings from DB (start_stage>=3) or via Stage 2 (start_stage<=2)."""
    from app.agents.tools.cve_attack_mapper import (
        _get_existing_attack_mappings,
        _execute_cve_to_attack_map,
        _load_attack_mappings_from_db,
    )

    cve_id_norm = cve_id.strip().upper()
    if not cve_id_norm.startswith("CVE-"):
        cve_id_norm = f"CVE-{cve_id_norm}" if not cve_id_norm.startswith("CVE") else cve_id_norm

    if start_stage >= 3:
        mappings = _load_attack_mappings_from_db(cve_id_norm)
        if not mappings:
            raise ValueError(f"{cve_id_norm} not in cve_attack_mappings; run Stage 2 first")
        return mappings
    existing = _get_existing_attack_mappings(cve_id_norm)
    if existing:
        return existing
    return _execute_cve_to_attack_map(cve_id_norm, cve_detail, frameworks)


def _enrich_stage1_stage2_only(
    cve_id: str,
    epss_lookup: Optional[Dict[str, float]] = None,
    kev_lookup: Optional[Set[str]] = None,
    nvd_lookup: Optional[Dict[str, Dict]] = None,
    skip_nvd_fetch: bool = False,
    frameworks: Optional[List[str]] = None,
    start_stage: int = 1,
) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Stage 1 + Stage 2 only. Returns (cve_detail, mappings). Used for two-pass Stage 3 de-dup."""
    frameworks = frameworks or default_pipeline_framework_ids()
    cve_detail = _load_or_fetch_cve_detail(
        cve_id,
        start_stage=start_stage,
        epss_lookup=epss_lookup,
        kev_lookup=kev_lookup,
        nvd_lookup=nvd_lookup,
        skip_nvd_fetch=skip_nvd_fetch,
    )
    mappings = _load_or_run_stage2(cve_id, cve_detail, frameworks, start_stage)
    return (cve_detail, mappings)


def _enrich_single(
    cve_id: str,
    full_pipeline: bool = False,
    frameworks: Optional[List[str]] = None,
    epss_lookup: Optional[Dict[str, float]] = None,
    kev_lookup: Optional[Set[str]] = None,
    nvd_lookup: Optional[Dict[str, Dict]] = None,
    skip_nvd_fetch: bool = False,
) -> Dict[str, Any]:
    """
    Enrich a single CVE. Returns flat dict with all enrichment fields.
    When epss_lookup and kev_lookup are provided (batch mode), uses them instead of per-CVE API calls.
    """
    from app.agents.tools.cve_enrichment import _execute_cve_enrich
    from app.agents.tools.cve_attack_mapper import _execute_cve_to_attack_map
    from app.agents.tools.attack_control_mapping import _execute_attack_control_map

    frameworks = frameworks or default_pipeline_framework_ids()
    cve_id_norm = cve_id.strip().upper()
    if not cve_id_norm.startswith("CVE-"):
        cve_id_norm = f"CVE-{cve_id_norm}" if not cve_id_norm.startswith("CVE") else cve_id_norm

    # Stage 1: CVE enrichment (uses pre-fetched epss/kev/nvd when provided, or cache-only if skip_nvd_fetch)
    cve_detail = _execute_cve_enrich(
        cve_id_norm,
        epss_lookup=epss_lookup,
        kev_lookup=kev_lookup,
        nvd_lookup=nvd_lookup,
        skip_nvd_fetch=skip_nvd_fetch,
    )

    result = {
        "cve_id": cve_detail.get("cve_id", cve_id_norm),
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
        # Stage 2: CVE → ATT&CK (use cache if mappings exist)
        try:
            from app.agents.tools.cve_attack_mapper import _get_existing_attack_mappings

            existing_mappings = _get_existing_attack_mappings(cve_id_norm)
            if existing_mappings:
                mappings = existing_mappings
            else:
                mappings = _execute_cve_to_attack_map(cve_id_norm, cve_detail, frameworks)
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
                            cve_id=cve_id_norm,
                            cve_context=cve_detail,
                            persist=True,
                        )
                        control_results.extend(results)
                    except Exception as e:
                        err_msg = str(e)[:200]
                        logger.warning(f"Control mapping failed for {m['technique_id']}/{m['tactic']}/{fw}: {e}")
                        control_errors.append(f"{m['technique_id']}/{m['tactic']}/{fw}: {err_msg}")
            result["control_mapping_count"] = len(control_results)
            result["control_mapping_error"] = "; ".join(control_errors)[:500] if control_errors else ""
            control_by_fw: Dict[str, List[str]] = {}
            for c in control_results:
                fw = c.get("framework_id", "")
                item = c.get("item_id", "")
                if fw and item:
                    control_by_fw.setdefault(fw, []).append(item)
            for fw, items in control_by_fw.items():
                result[f"controls_{fw}"] = "|".join(items[:50])
        except Exception as e:
            logger.warning(f"CVE→ATT&CK mapping failed for {cve_id_norm}: {e}")
            result["technique_ids"] = ""
            result["tactics"] = ""
            result["technique_tactic_pairs"] = ""
            result["attack_mapping_count"] = 0
            result["attack_mappings_json"] = ""
            result["attack_mapping_error"] = str(e)[:200]
            result["control_mapping_count"] = 0
            result["control_mapping_error"] = ""

    return result


def enrich_cves_from_csv_batch(
    input_csv: str,
    output_csv: str,
    cve_column: Optional[str] = None,
    frameworks: Optional[List[str]] = None,
    preserve_input_columns: bool = True,
    checkpoint_path: Optional[str] = ".cve_batch_checkpoint.json",
    epss_csv_path: Optional[str] = None,
    nvd_batch_size: int = 10,
    skip_nvd: bool = False,
    start_stage: int = 1,
    poll_interval: int = 60,
    openai_batch_chunk_size: int = 0,
) -> Dict[str, Any]:
    """
    Enrich CVEs via OpenAI Batch API (Stage 2 + Stage 3).
    ~50% cost savings, higher rate limits. Results within 24h.
    """
    from app.ingestion.attacktocve.openai_batch import (
        _ensure_openai_provider,
        build_stage2_jsonl,
        build_stage3_jsonl,
        openai_batch_request_chunk_size,
        parse_stage2_output,
        parse_stage3_output,
        summarize_stage2_batch_output,
        upload_and_create_batch,
        poll_batch_until_done,
        download_batch_output,
    )
    from app.agents.tools.cve_enrichment import (
        _get_cached_cve_detail,
        _prefetch_nvd_batch,
        _parse_nvd_to_detail,
        _upsert_cve_intelligence,
    )
    from app.agents.tools.cve_attack_mapper import (
        _query_cwe_technique_mappings,
        _get_existing_attack_mappings,
        _persist_cve_attack_mappings,
        _load_attack_mappings_from_db,
    )
    from app.agents.tools.attack_control_mapping import (
        build_control_mapping_prompt_for_batch,
        _get_existing_control_mappings,
        _persist_control_mappings_multi,
    )

    _ensure_openai_provider()

    input_path = Path(input_csv)
    output_path = Path(output_csv)
    frameworks = frameworks or default_pipeline_framework_ids()

    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    with open(input_path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = list(reader)

    col = cve_column or _detect_cve_column(headers)
    if not col:
        raise ValueError(f"Could not detect CVE column. Headers: {headers}")

    def _norm(s: str) -> str:
        c = (s or "").strip().upper()
        if not c or not c.startswith("CVE-"):
            c = f"CVE-{c}" if c and not c.startswith("CVE") else c
        return c

    cve_ids = list(dict.fromkeys(_norm(r.get(col) or "") for r in rows if (r.get(col) or "").strip()))
    cve_ids = [c for c in cve_ids if c]

    ckpt = CheckpointManager(checkpoint_path) if checkpoint_path else None
    done_cve_ids: Set[str] = set(ckpt._done) if ckpt else set()
    previous_output: Dict[str, Dict[str, Any]] = {}
    if output_path.exists():
        try:
            with open(output_path, newline="", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    cid = (r.get("cve_id") or "").strip().upper()
                    if cid:
                        previous_output[cid] = dict(r)
                        done_cve_ids.add(cid)
        except Exception as e:
            logger.warning(f"Could not read previous output for resume: {e}")

    logger.info("Pre-fetching EPSS and KEV...")
    epss_lookup = _prefetch_epss(epss_csv_path=epss_csv_path)
    kev_lookup = _prefetch_kev()

    nvd_lookup: Dict[str, Dict] = {}
    if not skip_nvd and start_stage <= 1:
        needs_nvd = [c for c in cve_ids if _get_cached_cve_detail(c) is None]
        if needs_nvd:
            logger.info(f"Pre-fetching NVD for {len(needs_nvd)} CVEs...")
            nvd_lookup = _prefetch_nvd_batch(needs_nvd, batch_size=nvd_batch_size)
            for cid, nvd in nvd_lookup.items():
                if nvd.get("vulnerabilities"):
                    epss_score = epss_lookup.get(cid, 0.0)
                    epss = {"data": [{"epss": epss_score}]} if epss_score else {}
                    kev = cid in kev_lookup
                    detail = _parse_nvd_to_detail(cid, nvd, epss, kev)
                    _upsert_cve_intelligence(detail)

    cves_to_process = [c for c in cve_ids if c not in done_cve_ids]
    if not cves_to_process:
        logger.info("All CVEs already done (checkpoint). Nothing to process.")
        return {"succeeded": 0, "failed": 0, "skipped": len(done_cve_ids), "errors": []}

    logger.info(f"Batch API: processing {len(cves_to_process)} CVEs (skipping {len(done_cve_ids)} done)")

    cve_details: List[Dict[str, Any]] = []
    cwe_candidates_by_cve: Dict[str, List[Dict[str, Any]]] = {}
    row_by_cve: Dict[str, Dict[str, Any]] = {}

    for cve_id in cves_to_process:
        detail = _get_cached_cve_detail(cve_id)
        if not detail:
            logger.warning(f"No CVE detail for {cve_id}, skipping")
            continue
        cve_details.append(detail)
        cwe_candidates_by_cve[cve_id] = _query_cwe_technique_mappings(detail.get("cwe_ids", []))
        for r in rows:
            if _norm(r.get(col) or "") == cve_id:
                row_by_cve[cve_id] = r
                break

    if not cve_details:
        logger.warning("No CVE details available. Run without --skip-nvd first (or preload NVD).")
        return {"succeeded": 0, "failed": len(cves_to_process), "skipped": len(done_cve_ids), "errors": []}

    stage2_results: Dict[str, List[Dict[str, Any]]] = {}
    if start_stage >= 3:
        logger.info("Start stage 3: loading ATT&CK mappings from DB (skipping Stage 2 batch)")
        for detail in cve_details:
            cve_id = (detail.get("cve_id") or "").strip().upper()
            mappings = _load_attack_mappings_from_db(cve_id)
            if mappings:
                stage2_results[cve_id] = mappings
    else:
        n2 = len(cve_details)
        chunk2 = openai_batch_request_chunk_size(n2, openai_batch_chunk_size)
        num_chunks2 = (n2 + chunk2 - 1) // chunk2 if chunk2 else 1
        logger.info(
            f"Stage 2: {n2} requests in {num_chunks2} OpenAI batch job(s) (≤{chunk2} requests per job)"
        )
        for off in range(0, n2, chunk2):
            chunk_details = cve_details[off : off + chunk2]
            chunk_cwe: Dict[str, List[Dict[str, Any]]] = {}
            for d in chunk_details:
                cid = (d.get("cve_id") or "").strip().upper()
                chunk_cwe[cid] = cwe_candidates_by_cve.get(cid, [])
            stage2_jsonl = build_stage2_jsonl(chunk_details, chunk_cwe)
            ci = off // chunk2 + 1
            logger.info(f"Stage 2 batch {ci}/{num_chunks2}: {len(chunk_details)} requests")
            batch2_id = upload_and_create_batch(
                stage2_jsonl,
                metadata={"stage": "cve_to_attack", "chunk": str(ci)},
            )
            batch2 = poll_batch_until_done(batch2_id, poll_interval=poll_interval)
            if batch2.status not in ("completed", "cancelled", "failed", "expired"):
                raise RuntimeError(
                    f"Stage 2 batch chunk {ci} unexpected status: {batch2.status}"
                )

            stage2_output = download_batch_output(batch2_id)
            partial = parse_stage2_output(stage2_output)
            stage2_results.update(partial)
            n_chunk = len(chunk_details)
            chunk_cve_ids = {(d.get("cve_id") or "").strip().upper() for d in chunk_details}
            n_ok = sum(
                1
                for cid in chunk_cve_ids
                if partial.get(cid) and len(partial[cid]) > 0
            )
            if n_ok < n_chunk:
                st = summarize_stage2_batch_output(stage2_output, chunk_cve_ids)
                codes = st.get("http_error_codes") or {}
                samples = st.get("http_sample_msgs") or []
                sample_txt = ("; ".join(samples)) if samples else "—"
                logger.warning(
                    f"Stage 2 chunk {ci}/{num_chunks2}: {n_ok}/{n_chunk} CVEs with non-empty mappings. "
                    f"Breakdown — http_errors={st.get('http_non_200', 0)} {codes or '{}'} "
                    f"batch_cancelled={st.get('batch_cancelled', 0)} "
                    f"no_choices={st.get('success_no_choices', 0)} empty_content={st.get('success_empty_content', 0)} "
                    f"bad_json_or_not_list={st.get('json_not_list_or_parse', 0)} empty_list={st.get('empty_list', 0)} "
                    f"missing_output_line={st.get('missing_lines_in_output', 0)} "
                    f"line_parse_errors={st.get('parse_line_errors', 0)}. "
                    f"Samples: {sample_txt}. "
                    f"Failed CVEs are not checkpointed — fix model/API issues and re-run to retry."
                )
            else:
                logger.info(f"Stage 2 chunk {ci}/{num_chunks2}: {n_ok}/{n_chunk} CVEs OK")

            for cve_id, mappings in partial.items():
                detail = next(
                    (d for d in chunk_details if (d.get("cve_id") or "").strip().upper() == cve_id),
                    None,
                )
                if not detail:
                    continue
                seen: set = set()
                final: List[Dict[str, Any]] = []
                for m in mappings:
                    tid = (m.get("technique_id") or "").strip().upper()
                    tactic = (m.get("tactic") or "").strip().lower().replace(" ", "-")
                    if not tid or not tactic or (tid, tactic) in seen:
                        continue
                    seen.add((tid, tactic))
                    final.append({
                        "cve_id": cve_id,
                        "technique_id": tid,
                        "tactic": tactic,
                        "confidence": (m.get("confidence") or "medium").lower(),
                        "mapping_source": (m.get("mapping_source") or "llm").lower(),
                        "rationale": m.get("rationale", ""),
                    })
                if final:
                    _persist_cve_attack_mappings(cve_id, detail, final)

    # Hashable keys only — cve_detail is a dict and cannot live inside a set element.
    all_triple_keys: Set[tuple] = set()
    cve_detail_by_id = {d.get("cve_id", "").strip().upper(): d for d in cve_details if d.get("cve_id")}
    for cve_id, mappings in stage2_results.items():
        for m in mappings:
            tid = (m.get("technique_id") or "").strip().upper()
            tactic = (m.get("tactic") or "").strip().lower().replace(" ", "-")
            if not tid or not tactic:
                continue
            for fw in frameworks:
                all_triple_keys.add((tid, tactic, fw, cve_id))

    triples_to_run: List[tuple] = []
    triple_cache: Dict[tuple, List[Dict]] = {}
    for tid, tactic, fw, cve_id in all_triple_keys:
        detail = cve_detail_by_id.get(cve_id)
        existing = _get_existing_control_mappings(tid, tactic, fw)
        if existing:
            triple_cache[(tid, tactic, fw)] = existing
        else:
            triples_to_run.append((tid, tactic, fw, cve_id, detail))

    stage3_prompts: List[Dict[str, Any]] = []
    triple_meta: Dict[str, Dict[str, str]] = {}
    for tid, tactic, fw, cve_id, detail in triples_to_run:
        prompt_data = build_control_mapping_prompt_for_batch(
            technique_id=tid,
            tactic=tactic,
            framework_id=fw,
            cve_id=cve_id,
            cve_context=detail,
        )
        if prompt_data:
            custom_id = f"stage3-{tid}:{tactic}:{fw}"
            stage3_prompts.append({
                "custom_id": custom_id,
                "system_prompt": prompt_data["system_prompt"],
                "user_prompt": prompt_data["user_prompt"],
            })
            triple_meta[custom_id] = {
                "tactic_risk_lens": prompt_data.get("tactic_risk_lens", ""),
                "blast_radius": prompt_data.get("blast_radius", "identity"),
            }

    if not stage3_prompts:
        n_cached = len(triple_cache)
        n_need = len(triples_to_run)
        n_keys = len(all_triple_keys)
        logger.info(
            "Stage 3: no OpenAI batch run — "
            f"cve-scoped triples={n_keys}, already cached (T,tactic,framework)={n_cached}, "
            f"uncached needing LLM={n_need}. "
            + (
                "All uncached triples had no batch prompt (check framework YAML / tactic / Qdrant items)."
                if n_need > 0
                else "Nothing to call OpenAI for (all triples had existing control mappings or no ATT&CK rows)."
            )
        )

    if stage3_prompts:
        n3 = len(stage3_prompts)
        chunk3 = openai_batch_request_chunk_size(n3, openai_batch_chunk_size)
        num_chunks3 = (n3 + chunk3 - 1) // chunk3 if chunk3 else 1
        logger.info(
            f"Stage 3: {n3} requests in {num_chunks3} OpenAI batch job(s) (≤{chunk3} requests per job)"
        )
        for off in range(0, n3, chunk3):
            chunk_prompts = stage3_prompts[off : off + chunk3]
            ci = off // chunk3 + 1
            logger.info(f"Stage 3 batch {ci}/{num_chunks3}: {len(chunk_prompts)} requests")
            stage3_jsonl = build_stage3_jsonl(chunk_prompts)
            batch3_id = upload_and_create_batch(
                stage3_jsonl,
                metadata={"stage": "attack_to_control", "chunk": str(ci)},
            )
            batch3 = poll_batch_until_done(batch3_id, poll_interval=poll_interval)
            if batch3.status not in ("completed", "cancelled", "failed", "expired"):
                raise RuntimeError(
                    f"Stage 3 batch chunk {ci} unexpected status: {batch3.status}"
                )

            stage3_output = download_batch_output(batch3_id)
            stage3_results = parse_stage3_output(stage3_output)
            n_p = len(chunk_prompts)
            chunk_cids = {p["custom_id"] for p in chunk_prompts}
            n_s3 = sum(
                1
                for cid in chunk_cids
                if stage3_results.get(cid) and len(stage3_results[cid]) > 0
            )
            if n_s3 < n_p:
                logger.warning(
                    f"Stage 3 chunk {ci}/{num_chunks3}: {n_s3}/{n_p} prompts returned mappings "
                    f"(others failed; triples stay uncached for retry)"
                )
            else:
                logger.info(f"Stage 3 chunk {ci}/{num_chunks3}: {n_s3}/{n_p} prompts OK")

            for custom_id, raw_mappings in stage3_results.items():
                parts = custom_id.replace("stage3-", "").split(":")
                if len(parts) != 3:
                    continue
                tid, tactic, fw = parts[0], parts[1], parts[2]
                meta = triple_meta.get(custom_id, {})
                tactic_risk_lens = meta.get("tactic_risk_lens", "")
                blast_radius = meta.get("blast_radius", "identity")
                results = []
                for m in raw_mappings:
                    item_id = m.get("scenario_id") or m.get("item_id") or ""
                    if not item_id:
                        continue
                    results.append({
                        "technique_id": tid,
                        "tactic": tactic,
                        "item_id": item_id,
                        "framework_id": fw,
                        "relevance_score": float(m.get("relevance_score", 0.5)),
                        "confidence": m.get("confidence", "medium"),
                        "rationale": m.get("rationale", ""),
                        "tactic_risk_lens": tactic_risk_lens,
                        "blast_radius": blast_radius,
                        "control_family": m.get("control_family", ""),
                        "attack_tactics": m.get("attack_tactics", []),
                        "attack_platforms": m.get("attack_platforms", []),
                        "loss_outcomes": m.get("loss_outcomes", []),
                    })
                if results:
                    _persist_control_mappings_multi(results)
                    triple_cache[(tid, tactic, fw)] = results

    enrich_cols = [
        "cve_id", "description", "cvss_score", "cvss_vector", "attack_vector",
        "attack_complexity", "privileges_required", "cwe_ids", "affected_products",
        "epss_score", "exploit_available", "exploit_maturity", "published_date", "last_modified",
        "technique_ids", "tactics", "technique_tactic_pairs",
        "attack_mapping_count", "attack_mappings_json", "attack_mapping_error",
        "control_mapping_count", "control_mapping_error",
    ]
    for fw in frameworks:
        enrich_cols.append(f"controls_{fw}")
    enrich_cols.append("enrichment_error")

    if preserve_input_columns:
        seen = set(h.strip().lower() for h in headers)
        out_headers = list(headers)
        for c in enrich_cols:
            if c.lower() not in seen:
                out_headers.append(c)
                seen.add(c.lower())
    else:
        out_headers = enrich_cols

    final_rows: List[Dict[str, Any]] = []
    for row in rows:
        raw_cve = (row.get(col) or "").strip()
        if not raw_cve:
            final_rows.append(_row_to_flat_dict(row, col))
            continue
        cve_id_norm = _norm(raw_cve)
        if cve_id_norm in done_cve_ids:
            prev = previous_output.get(cve_id_norm)
            if prev and preserve_input_columns:
                merged = dict(row)
                merged.update(prev)
                final_rows.append(merged)
            elif prev:
                final_rows.append(prev)
            else:
                fallback = dict(row) if preserve_input_columns else {}
                fallback.setdefault("cve_id", raw_cve)
                final_rows.append(fallback)
            continue

        detail = cve_detail_by_id.get(cve_id_norm) or _get_cached_cve_detail(cve_id_norm)
        mappings = stage2_results.get(cve_id_norm, [])

        result = {
            "cve_id": detail.get("cve_id", cve_id_norm) if detail else cve_id_norm,
            "description": (detail.get("description", "") if detail else ""),
            "cvss_score": (detail.get("cvss_score", 0.0) if detail else 0.0),
            "cvss_vector": (detail.get("cvss_vector", "") if detail else ""),
            "attack_vector": (detail.get("attack_vector", "") if detail else ""),
            "attack_complexity": (detail.get("attack_complexity", "") if detail else ""),
            "privileges_required": (detail.get("privileges_required", "") if detail else ""),
            "cwe_ids": "|".join(detail.get("cwe_ids", []) or []) if detail else "",
            "affected_products": "|".join((detail.get("affected_products") or [])[:500]) if detail else "",
            "epss_score": (detail.get("epss_score", 0.0) if detail else 0.0),
            "exploit_available": (detail.get("exploit_available", False) if detail else False),
            "exploit_maturity": (detail.get("exploit_maturity", "") if detail else ""),
            "published_date": (detail.get("published_date", "") if detail else ""),
            "last_modified": (detail.get("last_modified", "") if detail else ""),
            "technique_ids": "|".join(dict.fromkeys(m.get("technique_id", "") for m in mappings if m.get("technique_id"))),
            "tactics": "|".join(dict.fromkeys(m.get("tactic", "") for m in mappings if m.get("tactic"))),
            "technique_tactic_pairs": "|".join(f"{m.get('technique_id', '')}:{m.get('tactic', '')}" for m in mappings),
            "attack_mapping_count": len(mappings),
            "attack_mappings_json": json.dumps([{"technique_id": m.get("technique_id"), "tactic": m.get("tactic"), "confidence": m.get("confidence"), "rationale": (m.get("rationale") or "")[:200]} for m in mappings]),
            "attack_mapping_error": "",
            "control_mapping_count": 0,
            "control_mapping_error": "",
            "enrichment_error": "",
        }
        control_results: List[Dict] = []
        for m in mappings:
            tid = (m.get("technique_id") or "").strip().upper()
            tactic = (m.get("tactic") or "").strip().lower().replace(" ", "-")
            for fw in frameworks:
                control_results.extend(triple_cache.get((tid, tactic, fw), []))
        result["control_mapping_count"] = len(control_results)
        control_by_fw: Dict[str, List[str]] = {}
        for c in control_results:
            fw = c.get("framework_id", "")
            item = c.get("item_id", "")
            if fw and item:
                control_by_fw.setdefault(fw, []).append(item)
        for fw in frameworks:
            result[f"controls_{fw}"] = "|".join(control_by_fw.get(fw, [])[:50])

        if preserve_input_columns:
            merged = dict(row)
            merged.update(result)
            final_rows.append(merged)
        else:
            final_rows.append(result)

        if ckpt and cve_id_norm in stage2_results:
            ckpt.mark_done_batch([cve_id_norm])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_headers, extrasaction="ignore")
        writer.writeheader()
        for r in final_rows:
            writer.writerow({k: _csv_safe(r.get(k, "")) for k in out_headers})

    succeeded = len([c for c in cves_to_process if c in stage2_results])
    return {
        "succeeded": succeeded,
        "failed": len(cves_to_process) - succeeded,
        "skipped": len(done_cve_ids),
        "errors": [],
    }


def run_stage3_only(
    input_csv: Optional[str] = None,
    output_csv: Optional[str] = None,
    cve_column: Optional[str] = None,
    frameworks: Optional[List[str]] = None,
    use_batch_api: bool = False,
    poll_interval: int = 60,
) -> Dict[str, Any]:
    """
    Run Stage 3 only (ATT&CK → Control). Uses existing cve_attack_mappings.
    If input_csv is provided, process only those CVEs. Otherwise process all CVEs in cve_attack_mappings.
    If output_csv is provided, write enriched CSV. Otherwise only persist to attack_control_mappings_multi.
    """
    from app.agents.tools.cve_attack_mapper import _get_attack_mappings_for_cves
    from app.agents.tools.cve_enrichment import _get_cached_cve_detail
    from app.agents.tools.attack_control_mapping import (
        build_control_mapping_prompt_for_batch,
        _get_existing_control_mappings,
        _persist_control_mappings_multi,
    )

    frameworks = frameworks or default_pipeline_framework_ids()

    cve_ids: Optional[List[str]] = None
    if input_csv:
        input_path = Path(input_csv)
        if not input_path.exists():
            raise FileNotFoundError(f"Input CSV not found: {input_path}")
        with open(input_path, newline="", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            rows = list(reader)
        col = cve_column or _detect_cve_column(headers)
        if not col:
            raise ValueError(f"Could not detect CVE column. Headers: {headers}")
        def _norm(s: str) -> str:
            c = (s or "").strip().upper()
            if not c or not c.startswith("CVE-"):
                c = f"CVE-{c}" if c and not c.startswith("CVE") else c
            return c
        cve_ids = list(dict.fromkeys(_norm(r.get(col) or "") for r in rows if (r.get(col) or "").strip()))
        cve_ids = [c for c in cve_ids if c]
        logger.info(f"Stage 3 only: {len(cve_ids)} CVEs from CSV")

    attack_mappings = _get_attack_mappings_for_cves(cve_ids)
    if not attack_mappings:
        logger.warning("No CVE→ATT&CK mappings found. Run Stage 2 first.")
        return {"triples_processed": 0, "triples_cached": 0, "triples_failed": 0}

    seen_triples: Set[tuple] = set()
    triple_to_context: Dict[tuple, tuple] = {}
    cve_detail_by_id: Dict[str, Dict[str, Any]] = {}
    for cve_id, mappings in attack_mappings.items():
        detail = _get_cached_cve_detail(cve_id)
        if detail:
            cve_detail_by_id[cve_id] = detail
        for m in mappings:
            tid = (m.get("technique_id") or "").strip().upper()
            tactic = (m.get("tactic") or "").strip().lower().replace(" ", "-")
            if not tid or not tactic:
                continue
            for fw in frameworks:
                tri = (tid, tactic, fw)
                if tri not in seen_triples:
                    seen_triples.add(tri)
                    triple_to_context[tri] = (cve_id, cve_detail_by_id.get(cve_id))

    triples_to_run: List[tuple] = []
    triple_cache: Dict[tuple, List[Dict]] = {}
    for tri in seen_triples:
        tid, tactic, fw = tri
        cve_id, detail = triple_to_context.get(tri, (None, None))
        existing = _get_existing_control_mappings(tid, tactic, fw)
        if existing:
            triple_cache[tri] = existing
        else:
            triples_to_run.append((tid, tactic, fw, cve_id, detail))

    logger.info(f"Stage 3: {len(triple_cache)} cached, {len(triples_to_run)} to run")
    triple_failures: Dict[tuple, str] = {}

    if use_batch_api:
        from app.ingestion.attacktocve.openai_batch import (
            _ensure_openai_provider,
            build_stage3_jsonl,
            parse_stage3_output,
            upload_and_create_batch,
            poll_batch_until_done,
            download_batch_output,
        )
        _ensure_openai_provider()

        stage3_prompts: List[Dict[str, Any]] = []
        triple_meta: Dict[str, Dict[str, str]] = {}
        for tid, tactic, fw, cve_id, detail in triples_to_run:
            prompt_data = build_control_mapping_prompt_for_batch(
                technique_id=tid,
                tactic=tactic,
                framework_id=fw,
                cve_id=cve_id,
                cve_context=detail,
            )
            if prompt_data:
                custom_id = f"stage3-{tid}:{tactic}:{fw}"
                stage3_prompts.append({
                    "custom_id": custom_id,
                    "system_prompt": prompt_data["system_prompt"],
                    "user_prompt": prompt_data["user_prompt"],
                })
                triple_meta[custom_id] = {
                    "tactic_risk_lens": prompt_data.get("tactic_risk_lens", ""),
                    "blast_radius": prompt_data.get("blast_radius", "identity"),
                }

        if stage3_prompts:
            logger.info(f"Stage 3 batch: {len(stage3_prompts)} requests")
            stage3_jsonl = build_stage3_jsonl(stage3_prompts)
            batch_id = upload_and_create_batch(stage3_jsonl, metadata={"stage": "attack_to_control"})
            batch = poll_batch_until_done(batch_id, poll_interval=poll_interval)
            if batch.status != "completed":
                raise RuntimeError(f"Stage 3 batch failed: {batch.status}")

            stage3_output = download_batch_output(batch_id)
            stage3_results = parse_stage3_output(stage3_output)

            for custom_id, raw_mappings in stage3_results.items():
                parts = custom_id.replace("stage3-", "").split(":")
                if len(parts) != 3:
                    continue
                tid, tactic, fw = parts[0], parts[1], parts[2]
                meta = triple_meta.get(custom_id, {})
                tactic_risk_lens = meta.get("tactic_risk_lens", "")
                blast_radius = meta.get("blast_radius", "identity")
                results = []
                for m in raw_mappings:
                    item_id = m.get("scenario_id") or m.get("item_id") or ""
                    if not item_id:
                        continue
                    results.append({
                        "technique_id": tid,
                        "tactic": tactic,
                        "item_id": item_id,
                        "framework_id": fw,
                        "relevance_score": float(m.get("relevance_score", 0.5)),
                        "confidence": m.get("confidence", "medium"),
                        "rationale": m.get("rationale", ""),
                        "tactic_risk_lens": tactic_risk_lens,
                        "blast_radius": blast_radius,
                        "control_family": m.get("control_family", ""),
                        "attack_tactics": m.get("attack_tactics", []),
                        "attack_platforms": m.get("attack_platforms", []),
                        "loss_outcomes": m.get("loss_outcomes", []),
                    })
                if results:
                    _persist_control_mappings_multi(results)
                    triple_cache[(tid, tactic, fw)] = results
    else:
        from app.agents.tools.attack_control_mapping import _execute_attack_control_map
        for tid, tactic, fw, cve_id, detail in triples_to_run:
            try:
                results = _execute_attack_control_map(
                    technique_id=tid,
                    tactic=tactic,
                    framework_id=fw,
                    cve_id=cve_id,
                    cve_context=detail,
                    persist=True,
                )
                triple_cache[(tid, tactic, fw)] = results
            except Exception as e:
                err_msg = str(e)[:200]
                logger.warning(f"Stage 3 failed for {tid}/{tactic}/{fw}: {e}")
                triple_cache[(tid, tactic, fw)] = []
                triple_failures[(tid, tactic, fw)] = err_msg

    if output_csv and input_csv:
        output_path = Path(output_csv)
        enrich_cols = [
            "cve_id", "description", "cvss_score", "cvss_vector", "attack_vector",
            "attack_complexity", "privileges_required", "cwe_ids", "affected_products",
            "epss_score", "exploit_available", "exploit_maturity", "published_date", "last_modified",
            "technique_ids", "tactics", "technique_tactic_pairs",
            "attack_mapping_count", "attack_mappings_json", "attack_mapping_error",
            "control_mapping_count", "control_mapping_error",
        ]
        for fw in frameworks:
            enrich_cols.append(f"controls_{fw}")
        enrich_cols.append("enrichment_error")

        with open(input_path, newline="", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            rows = list(reader)
        col = cve_column or _detect_cve_column(headers)
        seen = set(h.strip().lower() for h in headers)
        out_headers = list(headers)
        for c in enrich_cols:
            if c.lower() not in seen:
                out_headers.append(c)
                seen.add(c.lower())

        final_rows: List[Dict[str, Any]] = []
        for row in rows:
            raw_cve = (row.get(col) or "").strip()
            if not raw_cve:
                final_rows.append(_row_to_flat_dict(row, col))
                continue
            cve_id_norm = (raw_cve or "").strip().upper()
            if not cve_id_norm.startswith("CVE-"):
                cve_id_norm = f"CVE-{cve_id_norm}" if cve_id_norm else cve_id_norm
            mappings = attack_mappings.get(cve_id_norm, [])
            detail = cve_detail_by_id.get(cve_id_norm) or _get_cached_cve_detail(cve_id_norm)

            result = {
                "cve_id": detail.get("cve_id", cve_id_norm) if detail else cve_id_norm,
                "description": (detail.get("description", "") if detail else ""),
                "cvss_score": (detail.get("cvss_score", 0.0) if detail else 0.0),
                "cvss_vector": (detail.get("cvss_vector", "") if detail else ""),
                "attack_vector": (detail.get("attack_vector", "") if detail else ""),
                "attack_complexity": (detail.get("attack_complexity", "") if detail else ""),
                "privileges_required": (detail.get("privileges_required", "") if detail else ""),
                "cwe_ids": "|".join(detail.get("cwe_ids", []) or []) if detail else "",
                "affected_products": "|".join((detail.get("affected_products") or [])[:500]) if detail else "",
                "epss_score": (detail.get("epss_score", 0.0) if detail else 0.0),
                "exploit_available": (detail.get("exploit_available", False) if detail else False),
                "exploit_maturity": (detail.get("exploit_maturity", "") if detail else ""),
                "published_date": (detail.get("published_date", "") if detail else ""),
                "last_modified": (detail.get("last_modified", "") if detail else ""),
                "technique_ids": "|".join(dict.fromkeys(m.get("technique_id", "") for m in mappings if m.get("technique_id"))),
                "tactics": "|".join(dict.fromkeys(m.get("tactic", "") for m in mappings if m.get("tactic"))),
                "technique_tactic_pairs": "|".join(f"{m.get('technique_id', '')}:{m.get('tactic', '')}" for m in mappings),
                "attack_mapping_count": len(mappings),
                "attack_mappings_json": json.dumps([{"technique_id": m.get("technique_id"), "tactic": m.get("tactic"), "confidence": m.get("confidence"), "rationale": (m.get("rationale") or "")[:200]} for m in mappings]),
                "attack_mapping_error": "",
                "control_mapping_count": 0,
                "control_mapping_error": "",
                "enrichment_error": "",
            }
            control_results = []
            cve_control_errors: List[str] = []
            for m in mappings:
                tid = (m.get("technique_id") or "").strip().upper()
                tactic = (m.get("tactic") or "").strip().lower().replace(" ", "-")
                for fw in frameworks:
                    tri = (tid, tactic, fw)
                    control_results.extend(triple_cache.get(tri, []))
                    if tri in triple_failures:
                        cve_control_errors.append(f"{tid}/{tactic}/{fw}: {triple_failures[tri]}")
            result["control_mapping_count"] = len(control_results)
            result["control_mapping_error"] = "; ".join(cve_control_errors)[:500] if cve_control_errors else ""
            control_by_fw: Dict[str, List[str]] = {}
            for c in control_results:
                fw = c.get("framework_id", "")
                item = c.get("item_id", "")
                if fw and item:
                    control_by_fw.setdefault(fw, []).append(item)
            for fw in frameworks:
                result[f"controls_{fw}"] = "|".join(control_by_fw.get(fw, [])[:50])

            merged = dict(row)
            merged.update(result)
            final_rows.append(merged)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=out_headers, extrasaction="ignore")
            writer.writeheader()
            for r in final_rows:
                writer.writerow({k: _csv_safe(r.get(k, "")) for k in out_headers})
        logger.info(f"Wrote {output_path}")

    return {
        "triples_processed": len(triples_to_run),
        "triples_cached": len(triple_cache),
        "triples_failed": 0,
    }


def enrich_cves_from_csv(
    input_csv: str,
    output_csv: str,
    cve_column: Optional[str] = None,
    full_pipeline: bool = False,
    frameworks: Optional[List[str]] = None,
    preserve_input_columns: bool = True,
    checkpoint_path: Optional[str] = ".cve_batch_checkpoint.json",
    epss_csv_path: Optional[str] = None,
    progress_interval: int = 25,
    nvd_batch_size: int = 10,
    skip_nvd: bool = False,
    start_stage: int = 1,
) -> Dict[str, Any]:
    """
    Read CVEs from CSV, enrich each, write to output CSV with all new fields.

    Args:
        input_csv: Path to input CSV (must have a column with CVE IDs)
        output_csv: Path to output CSV
        cve_column: Column name containing CVE IDs (auto-detected if None)
        full_pipeline: If True, run Stage 2 (CVE→ATT&CK) + Stage 3 (ATT&CK→Control)
        frameworks: Frameworks for ATT&CK→control (only used if full_pipeline)
        preserve_input_columns: If True, include all input columns in output
        checkpoint_path: Path to checkpoint file for resume; None to disable
        epss_csv_path: Local path to EPSS CSV (or set EPSS_CSV_PATH env); skips download if provided
        progress_interval: Print progress every N CVEs (0 = disabled)
        nvd_batch_size: NVD API concurrent batch size for Phase 1 pre-fetch (default: 10)
        skip_nvd: If True, use only cache (cve_intelligence/cve_cache); no NVD pre-fetch or API calls
        start_stage: 1 (default) | 2 | 3. Stage 2: load cve_detail from DB, skip NVD. Stage 3: load mappings from DB, skip NVD + Stage 2 LLM.

    Returns:
        Summary dict: processed, succeeded, failed, errors
    """
    input_path = Path(input_csv)
    output_path = Path(output_csv)
    frameworks = frameworks or default_pipeline_framework_ids()

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

    # Pre-fetch EPSS and KEV once per batch (eliminates ~4000+ API calls for large batches)
    logger.info("Pre-fetching EPSS and KEV data (once per batch)...")
    epss_lookup = _prefetch_epss(epss_csv_path=epss_csv_path)
    kev_lookup = _prefetch_kev()
    logger.info(f"EPSS: {len(epss_lookup)} CVEs | KEV: {len(kev_lookup)} CVEs")

    # Warn once if cwe_technique_mappings is empty (run cwe_enrich + cwe_capec_attack_mapper first)
    if full_pipeline and start_stage <= 2:
        try:
            from app.storage.sqlalchemy_session import get_security_intel_session
            from sqlalchemy import text
            with get_security_intel_session("cve_attack") as session:
                cnt = session.execute(text("SELECT COUNT(*) FROM cwe_technique_mappings")).scalar() or 0
            if cnt == 0:
                logger.warning(
                    "cwe_technique_mappings is empty. Stage 2 will use LLM-only path. "
                    "Run cwe_enrich --ingest-db and cwe_capec_attack_mapper to populate."
                )
        except Exception:
            pass

    ckpt = CheckpointManager(checkpoint_path) if checkpoint_path else None

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
            "control_mapping_count", "control_mapping_error",
        ])
        for fw in frameworks:
            enrich_cols.append(f"controls_{fw}")
    enrich_cols.append("enrichment_error")  # For failed rows

    if preserve_input_columns:
        seen = set(h.strip().lower() for h in headers)
        out_headers = list(headers)
        for c in enrich_cols:
            if c.lower() not in seen:
                out_headers.append(c)
                seen.add(c.lower())
    else:
        out_headers = enrich_cols
    out_headers_set = set(out_headers)

    # When resuming: use checkpoint + previous output. Skip CVEs in either.
    previous_output: Dict[str, Dict[str, Any]] = {}
    done_cve_ids: Set[str] = set()
    if ckpt:
        done_cve_ids = set(ckpt._done)
        logger.info(f"Checkpoint: {len(done_cve_ids)} CVEs already done")
    if output_path.exists():
        try:
            with open(output_path, newline="", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                prev_headers = reader.fieldnames or []
                for r in reader:
                    cid = (r.get("cve_id") or "").strip().upper()
                    if cid:
                        previous_output[cid] = dict(r)
                        done_cve_ids.add(cid)
                for h in prev_headers or []:
                    if h and h not in out_headers_set:
                        out_headers.append(h)
                        out_headers_set.add(h)
            logger.info(f"Resuming: {len(previous_output)} rows from output, {len(done_cve_ids)} total to skip")
        except Exception as e:
            logger.warning(f"Could not read previous output for resume: {e}")
    elif done_cve_ids:
        logger.info(f"Resuming: {len(done_cve_ids)} CVEs from checkpoint (no output file yet)")

    # Phase 1: Pre-fetch NVD for all CVEs not in cache (skipped when --skip-nvd or --start-stage >= 2)
    nvd_lookup: Dict[str, Dict] = {}
    if skip_nvd or start_stage >= 2:
        logger.info(
            f"Phase 1: Skipped ({'--skip-nvd' if skip_nvd else '--start-stage ' + str(start_stage)}): "
            "using cve_intelligence only, no NVD fetch"
        )
    else:
        from app.agents.tools.cve_enrichment import _get_cached_cve_detail, _prefetch_nvd_batch

        def _norm_cve(raw: str) -> str:
            c = (raw or "").strip().upper()
            if not c:
                return ""
            if not c.startswith("CVE-"):
                c = f"CVE-{c}" if not c.startswith("CVE") else c
            return c

        all_to_process = [
            _norm_cve(row.get(col) or "")
            for row in rows
            if (row.get(col) or "").strip()
        ]
        all_to_process = [c for c in all_to_process if c and c not in done_cve_ids]

        logger.info(f"Phase 1: Checking cache for {len(all_to_process)} CVEs (resume skips {len(done_cve_ids)})...")
        needs_nvd: List[str] = []
        for i, cid in enumerate(all_to_process):
            if _get_cached_cve_detail(cid) is None:
                needs_nvd.append(cid)
            if (i + 1) % 200 == 0:
                logger.info(f"Phase 1: Cache check {i + 1}/{len(all_to_process)} ({len(needs_nvd)} need NVD)")

        if needs_nvd:
            logger.info(f"Phase 1: Pre-fetching NVD for {len(needs_nvd)} CVEs (batch size {nvd_batch_size})...")
            nvd_lookup = _prefetch_nvd_batch(needs_nvd, batch_size=nvd_batch_size)
            logger.info(f"NVD pre-fetch complete: {len(nvd_lookup)} responses")
            # Persist to cve_intelligence so future runs use cache (no refetch)
            from app.agents.tools.cve_enrichment import _parse_nvd_to_detail, _upsert_cve_intelligence

            stored = 0
            for cid, nvd in nvd_lookup.items():
                if nvd.get("vulnerabilities"):
                    epss_score = epss_lookup.get(cid, 0.0)
                    epss = {"data": [{"epss": epss_score}]} if epss_score else {}
                    kev = cid in kev_lookup
                    detail = _parse_nvd_to_detail(cid, nvd, epss, kev)
                    _upsert_cve_intelligence(detail)
                    stored += 1
            if stored:
                logger.info(f"Phase 1: Stored {stored} CVEs in cve_intelligence (cache for future runs)")
        else:
            logger.info("Phase 1: All CVEs cached, skipping NVD pre-fetch")

    # Count CVEs to process (for progress)
    total_cves = sum(1 for r in rows if (r.get(col) or "").strip())
    logger.info(f"Total CVEs to process: {total_cves} (resuming skips {len(done_cve_ids)} already done)")

    summary = {"processed": 0, "succeeded": 0, "failed": 0, "skipped": 0, "errors": []}
    output_rows: List[Dict[str, Any]] = []
    ckpt_buffer: List[str] = []

    def _flush_checkpoint() -> None:
        if ckpt and ckpt_buffer:
            ckpt.mark_done_batch(ckpt_buffer)
            ckpt_buffer.clear()

    for i, row in enumerate(rows):
        raw_cve = (row.get(col) or "").strip()
        if not raw_cve:
            output_rows.append(_row_to_flat_dict(row, col))
            continue

        cve_id_norm = raw_cve.strip().upper()
        if not cve_id_norm.startswith("CVE-"):
            cve_id_norm = f"CVE-{cve_id_norm}" if not cve_id_norm.startswith("CVE") else cve_id_norm

        if cve_id_norm in done_cve_ids:
            summary["skipped"] += 1
            prev = previous_output.get(cve_id_norm)
            if prev:
                if preserve_input_columns:
                    merged = dict(row)
                    merged.update(prev)
                    output_rows.append(merged)
                else:
                    output_rows.append(prev)
            else:
                # In checkpoint but no output file row (e.g. run interrupted before write)
                # Use input row with empty enrichment to avoid reprocessing
                fallback = dict(row) if preserve_input_columns else {}
                fallback.setdefault("cve_id", raw_cve)
                output_rows.append(fallback)
            continue

        summary["processed"] += 1
        if full_pipeline:
            # Two-pass: Stage 1+2 first, then Stage 3 de-dup (handled below)
            try:
                cve_detail, mappings = _enrich_stage1_stage2_only(
                    raw_cve,
                    epss_lookup=epss_lookup,
                    kev_lookup=kev_lookup,
                    nvd_lookup=nvd_lookup,
                    skip_nvd_fetch=skip_nvd,
                    frameworks=frameworks,
                    start_stage=start_stage,
                )
                output_rows.append({
                    "_row": row,
                    "_cve_id_norm": cve_id_norm,
                    "_cve_detail": cve_detail,
                    "_mappings": mappings,
                    "_preserve": preserve_input_columns,
                })
                summary["succeeded"] += 1
                if ckpt:
                    ckpt_buffer.append(cve_id_norm)
                    if len(ckpt_buffer) >= max(1, progress_interval):
                        _flush_checkpoint()
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
                    "technique_ids": "",
                    "tactics": "",
                    "technique_tactic_pairs": "",
                    "attack_mapping_count": 0,
                    "attack_mappings_json": "",
                    "attack_mapping_error": str(e)[:200],
                    "control_mapping_count": 0,
                    "control_mapping_error": "",
                })
                for fw in frameworks:
                    fallback[f"controls_{fw}"] = ""
                output_rows.append({"._final": fallback})
        else:
            # Single-pass: Stage 1 only
            try:
                enriched = _enrich_single(
                    raw_cve,
                    full_pipeline=False,
                    frameworks=frameworks,
                    epss_lookup=epss_lookup,
                    kev_lookup=kev_lookup,
                    nvd_lookup=nvd_lookup,
                    skip_nvd_fetch=skip_nvd,
                )
                for k in enriched:
                    if k not in out_headers_set:
                        out_headers.append(k)
                        out_headers_set.add(k)
                if preserve_input_columns:
                    merged = dict(row)
                    merged.update(enriched)
                    output_rows.append({"._final": merged})
                else:
                    output_rows.append({"._final": enriched})
                summary["succeeded"] += 1
                if ckpt:
                    ckpt_buffer.append(cve_id_norm)
                    if len(ckpt_buffer) >= max(1, progress_interval):
                        _flush_checkpoint()
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
                output_rows.append({"._final": fallback})

        # Progress display
        done = summary["succeeded"] + summary["failed"] + summary["skipped"]
        if progress_interval > 0 and done > 0:
            if done % progress_interval == 0 or done == total_cves:
                pct = 100 * done / total_cves if total_cves else 0
                logger.info(
                    f"Progress: {done}/{total_cves} ({pct:.1f}%) | "
                    f"✓ {summary['succeeded']} succeeded, ✗ {summary['failed']} failed, ⊘ {summary['skipped']} skipped"
                )
        # Incremental CSV write for resume (keeps out.csv in sync with checkpoint)
        if done > 0 and done % max(1, progress_interval) == 0:
            _rows_to_write: List[Dict[str, Any]] = []
            for r in output_rows:
                if "._final" in r:
                    _rows_to_write.append(r["._final"])
                elif "_mappings" in r:
                    # Partial row (Stage 1+2 only) for full_pipeline - controls empty until Stage 3
                    row, cve_id_norm, cve_detail, mappings, preserve = r["_row"], r["_cve_id_norm"], r["_cve_detail"], r["_mappings"], r["_preserve"]
                    partial = {
                        "cve_id": cve_detail.get("cve_id", cve_id_norm),
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
                        "technique_ids": "|".join(dict.fromkeys(m.get("technique_id", "") for m in mappings if m.get("technique_id"))),
                        "tactics": "|".join(dict.fromkeys(m.get("tactic", "") for m in mappings if m.get("tactic"))),
                        "technique_tactic_pairs": "|".join(f"{m.get('technique_id', '')}:{m.get('tactic', '')}" for m in mappings),
                        "attack_mapping_count": len(mappings),
                        "attack_mappings_json": json.dumps([{"technique_id": m.get("technique_id"), "tactic": m.get("tactic"), "confidence": m.get("confidence"), "rationale": m.get("rationale", "")[:200]} for m in mappings]),
                        "attack_mapping_error": "",
                        "control_mapping_count": 0,
                        "control_mapping_error": "",
                    }
                    for fw in frameworks:
                        partial[f"controls_{fw}"] = ""
                    if preserve:
                        merged = dict(row)
                        merged.update(partial)
                        _rows_to_write.append(merged)
                    else:
                        _rows_to_write.append(partial)
                else:
                    _rows_to_write.append(r)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=out_headers, extrasaction="ignore")
                w.writeheader()
                for r in _rows_to_write:
                    w.writerow({k: _csv_safe(r.get(k, "")) for k in out_headers})

    # Full pipeline: Stage 3 de-dup + assemble final rows
    if full_pipeline and any("_mappings" in r for r in output_rows):
        from app.agents.tools.attack_control_mapping import (
            _get_existing_control_mappings,
            _execute_attack_control_map,
        )

        stage2_items = [(r["_row"], r["_cve_id_norm"], r["_cve_detail"], r["_mappings"], r["_preserve"]) for r in output_rows if "_mappings" in r]
        all_triples: Set[tuple] = set()
        for _, _, _, mappings, _ in stage2_items:
            for m in mappings:
                for fw in frameworks:
                    tid = (m.get("technique_id") or "").strip().upper()
                    tactic = (m.get("tactic") or "").strip().lower().replace(" ", "-")
                    if tid and tactic:
                        all_triples.add((tid, tactic, fw))

        logger.info(f"Stage 3: {len(all_triples)} unique (technique, tactic, framework) triples")
        triple_cache: Dict[tuple, List[Dict]] = {}
        triples_to_run = []
        for tri in all_triples:
            existing = _get_existing_control_mappings(tri[0], tri[1], tri[2])
            if existing:
                triple_cache[tri] = existing
            else:
                triples_to_run.append(tri)

        logger.info(f"Stage 3: {len(triple_cache)} cached, {len(triples_to_run)} to run (batch dedup: 1 run per unique triple)")
        triple_failures: Dict[tuple, str] = {}  # (tid, tactic, fw) -> error message
        progress_interval = max(1, len(triples_to_run) // 10)  # Log every ~10%
        for idx, (technique_id, tactic, fw) in enumerate(triples_to_run):
            if progress_interval and (idx + 1) % progress_interval == 0:
                logger.info(f"Stage 3 progress: {idx + 1}/{len(triples_to_run)} triples")
            try:
                results = _execute_attack_control_map(
                    technique_id=technique_id,
                    tactic=tactic,
                    framework_id=fw,
                    persist=True,
                )
                triple_cache[(technique_id, tactic, fw)] = results
            except Exception as e:
                err_msg = str(e)[:200]
                logger.warning(f"Stage 3 failed for {technique_id}/{tactic}/{fw}: {e}")
                triple_cache[(technique_id, tactic, fw)] = []
                triple_failures[(technique_id, tactic, fw)] = err_msg

        # Assemble final rows from stage2 + triple_cache
        final_rows: List[Dict[str, Any]] = []
        for r in output_rows:
            if "._final" in r:
                final_rows.append(r["._final"])
            elif "_mappings" in r:
                row, cve_id_norm, cve_detail, mappings, preserve = r["_row"], r["_cve_id_norm"], r["_cve_detail"], r["_mappings"], r["_preserve"]
                control_results: List[Dict[str, Any]] = []
                cve_control_errors: List[str] = []
                for m in mappings:
                    for fw in frameworks:
                        tri = ((m.get("technique_id") or "").strip().upper(), (m.get("tactic") or "").strip().lower().replace(" ", "-"), fw)
                        control_results.extend(triple_cache.get(tri, []))
                        if tri in triple_failures:
                            cve_control_errors.append(f"{tri[0]}/{tri[1]}/{fw}: {triple_failures[tri]}")

                result = {
                    "cve_id": cve_detail.get("cve_id", cve_id_norm),
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
                    "technique_ids": "|".join(dict.fromkeys(m.get("technique_id", "") for m in mappings if m.get("technique_id"))),
                    "tactics": "|".join(dict.fromkeys(m.get("tactic", "") for m in mappings if m.get("tactic"))),
                    "technique_tactic_pairs": "|".join(f"{m.get('technique_id', '')}:{m.get('tactic', '')}" for m in mappings),
                    "attack_mapping_count": len(mappings),
                    "attack_mappings_json": json.dumps([{"technique_id": m.get("technique_id"), "tactic": m.get("tactic"), "confidence": m.get("confidence"), "rationale": m.get("rationale", "")[:200]} for m in mappings]),
                    "attack_mapping_error": "",
                    "control_mapping_count": len(control_results),
                    "control_mapping_error": "; ".join(cve_control_errors)[:500] if cve_control_errors else "",
                }
                control_by_fw: Dict[str, List[str]] = {}
                for c in control_results:
                    fw = c.get("framework_id", "")
                    item = c.get("item_id", "")
                    if fw and item:
                        control_by_fw.setdefault(fw, []).append(item)
                for fw, items in control_by_fw.items():
                    result[f"controls_{fw}"] = "|".join(items[:50])
                for k in result:
                    if k not in out_headers_set:
                        out_headers.append(k)
                        out_headers_set.add(k)
                if preserve:
                    merged = dict(row)
                    merged.update(result)
                    final_rows.append(merged)
                else:
                    final_rows.append(result)
            else:
                final_rows.append(r)  # empty or skipped row (plain dict)
        output_rows = final_rows

    # Flush checkpoint buffer
    _flush_checkpoint()

    # Single final CSV write (Fix 3: no incremental rewrite)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows_to_write = []
    for r in output_rows:
        if "._final" in r:
            rows_to_write.append(r["._final"])
        else:
            rows_to_write.append(r)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_headers, extrasaction="ignore")
        writer.writeheader()
        for r in rows_to_write:
            writer.writerow({k: _csv_safe(r.get(k, "")) for k in out_headers})

    return summary

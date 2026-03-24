"""
OpenAI Batch API integration for CVE enrichment pipeline.

Submits Stage 2 (CVE→ATT&CK) and Stage 3 (ATT&CK→Control) LLM calls via the
Batch API for ~50% cost savings and higher rate limits.

Usage: Use --batch-api flag with cve_enrich_pipeline CLI.
"""

from __future__ import annotations

import json
import logging
import re
import tempfile
import time
from pathlib import Path
from collections import Counter
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> Any:
    """Extract JSON from LLM response (handle markdown fences)."""
    text = (text or "").strip()
    if "```" in text:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            text = match.group(1).strip()
    return json.loads(text)


def _ensure_openai_provider() -> None:
    """Raise if LLM provider is not OpenAI (Batch API is OpenAI-only)."""
    from app.core.settings import get_settings
    s = get_settings()
    provider = (getattr(s, "LLM_PROVIDER", "openai") or "openai").lower()
    if provider != "openai":
        raise ValueError(
            f"Batch API requires OpenAI. Current provider: {provider}. "
            "Set LLM_PROVIDER=openai and OPENAI_API_KEY."
        )


def _get_openai_client():
    """Get OpenAI client for Batch API."""
    from openai import OpenAI
    from app.core.settings import get_settings
    s = get_settings()
    api_key = s.OPENAI_API_KEY or __import__("os").environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY required for Batch API")
    return OpenAI(api_key=api_key)


def _get_model() -> str:
    """Get model name for batch requests."""
    from app.core.settings import get_settings
    return get_settings().LLM_MODEL or "gpt-4o-mini"


def _chat_completion_body_extras() -> Dict[str, Any]:
    """
    Extra fields for Batch API /v1/chat/completions body.
    - Use max_completion_tokens (not max_tokens) for newer models.
    - Do not set temperature here: reasoning models (o1/o3/o4, etc.) reject non-default
      temperature (e.g. 0.2). Omitting uses the model/API default and avoids 400s.
    """
    return {"max_completion_tokens": 2000}


# ---------------------------------------------------------------------------
# Stage 2: CVE → ATT&CK
# ---------------------------------------------------------------------------

CVE_TO_ATTACK_LLM_SYSTEM = """You are a cybersecurity analyst mapping CVEs to MITRE ATT&CK techniques.

Given a CVE's description, CVSS, CWE, affected products, and exploit status, you will:
1. Confirm or reject each CWE-derived candidate (technique_id, tactic) based on the specific exploit
2. Add additional techniques the CWE crosswalk may miss (e.g. persistence, defense-evasion)
3. Assign confidence: high (direct match), medium (plausible), low (tangential)
4. Set mapping_source: "cwe_lookup+llm" if confirming CWE candidate, "llm" if adding new

Return ONLY a JSON array. No markdown, no preamble.
[
  {"technique_id": "T1190", "tactic": "initial-access", "confidence": "high", "mapping_source": "cwe_lookup+llm", "rationale": "..."},
  ...
]
"""


def openai_batch_request_chunk_size(total_requests: int, explicit_cap: int = 0) -> int:
    """
    Max requests per OpenAI Batch job. Larger total runs use smaller chunks.
    explicit_cap: if > 0, use min(explicit_cap, total_requests); else adaptive.
    """
    if total_requests <= 0:
        return 0
    if explicit_cap > 0:
        return max(1, min(explicit_cap, total_requests))
    if total_requests <= 200:
        return total_requests
    if total_requests <= 600:
        return 200
    if total_requests <= 1500:
        return 150
    return 100


def build_stage2_jsonl(
    cve_details: List[Dict[str, Any]],
    cwe_candidates_by_cve: Dict[str, List[Dict[str, Any]]],
    model: Optional[str] = None,
) -> str:
    """
    Build JSONL file content for Stage 2 (CVE→ATT&CK) batch.
    One chat completion request per CVE.
    """
    model = model or _get_model()
    lines = []
    for cve_detail in cve_details:
        cve_id = (cve_detail.get("cve_id") or "").strip().upper()
        if not cve_id:
            continue
        cwe_candidates = cwe_candidates_by_cve.get(cve_id, [])
        desc = cve_detail.get("description", "")[:1200]
        cvss = cve_detail.get("cvss_score", 0)
        cwe_ids = cve_detail.get("cwe_ids", [])
        products = cve_detail.get("affected_products", [])[:10]
        epss = cve_detail.get("epss_score", 0)
        exploit = cve_detail.get("exploit_available", False)
        maturity = cve_detail.get("exploit_maturity", "none")

        user = f"""CVE: {cve_id}
Description: {desc}
CVSS: {cvss} | EPSS: {epss} | Exploit: {exploit} ({maturity})
CWE: {', '.join(cwe_ids)}
Affected: {', '.join(products) if products else 'unknown'}

CWE-derived candidates:
{json.dumps(cwe_candidates, indent=2)}

Refine and augment. Return JSON array of mappings. Include rationale for each."""

        req = {
            "custom_id": f"stage2-{cve_id}",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": model,
                "messages": [
                    {"role": "system", "content": CVE_TO_ATTACK_LLM_SYSTEM},
                    {"role": "user", "content": user},
                ],
                **_chat_completion_body_extras(),
            },
        }
        lines.append(json.dumps(req))
    return "\n".join(lines)


def summarize_stage2_batch_output(
    output_jsonl: str,
    expected_cve_ids: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """
    Classify Stage 2 batch output lines for logging (why some CVEs lack mappings).
    Does not replace parse_stage2_output; mirrors its success criteria.
    """
    http_error_codes: Counter = Counter()
    http_sample_msgs: List[str] = []
    batch_cancelled = 0
    http_non_200 = 0
    success_no_choices = 0
    success_empty_content = 0
    json_not_list = 0
    empty_list = 0
    nonempty = 0
    cve_ids_seen: Set[str] = set()
    parse_line_errors = 0

    for line in (output_jsonl or "").strip().split("\n"):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            custom_id = row.get("custom_id", "")
            if not custom_id.startswith("stage2-"):
                continue
            cve_id = custom_id.replace("stage2-", "").strip().upper()
            cve_ids_seen.add(cve_id)

            top_err = row.get("error")
            if isinstance(top_err, dict) and top_err.get("code") == "batch_cancelled":
                batch_cancelled += 1
                continue

            resp = row.get("response") or {}
            sc = resp.get("status_code")
            if sc is not None and sc != 200:
                http_non_200 += 1
                body = resp.get("body") or {}
                inner = (body.get("error") or {}) if isinstance(body, dict) else {}
                code = inner.get("code") or f"http_{sc}"
                http_error_codes[code] += 1
                msg = (inner.get("message") or "")[:100]
                if msg and len(http_sample_msgs) < 4:
                    http_sample_msgs.append(f"{cve_id}: {msg}")
                continue

            body = resp.get("body", {}) if isinstance(resp, dict) else {}
            choices = body.get("choices", [])
            if not choices:
                success_no_choices += 1
                continue
            content = choices[0].get("message", {}).get("content", "")
            if not content:
                success_empty_content += 1
                continue
            try:
                mappings = _extract_json(content)
            except Exception:
                json_not_list += 1
                continue
            if not isinstance(mappings, list):
                json_not_list += 1
                continue
            if len(mappings) == 0:
                empty_list += 1
            else:
                nonempty += 1
        except Exception:
            parse_line_errors += 1

    missing = 0
    if expected_cve_ids:
        missing = len(expected_cve_ids - cve_ids_seen)

    return {
        "http_non_200": http_non_200,
        "http_error_codes": dict(http_error_codes),
        "http_sample_msgs": http_sample_msgs,
        "batch_cancelled": batch_cancelled,
        "success_no_choices": success_no_choices,
        "success_empty_content": success_empty_content,
        "json_not_list_or_parse": json_not_list,
        "empty_list": empty_list,
        "nonempty_mappings": nonempty,
        "missing_lines_in_output": missing,
        "parse_line_errors": parse_line_errors,
    }


def parse_stage2_output(output_jsonl: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Parse Stage 2 batch output JSONL. Returns {cve_id: [mappings]}.
    """
    results = {}
    for line in output_jsonl.strip().split("\n"):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            custom_id = row.get("custom_id", "")
            if not custom_id.startswith("stage2-"):
                continue
            cve_id = custom_id.replace("stage2-", "").strip().upper()
            resp = row.get("response", {})
            if resp.get("status_code") != 200:
                logger.debug(f"Stage 2 batch failed for {cve_id}: {resp}")
                continue
            body = resp.get("body", {})
            choices = body.get("choices", [])
            if not choices:
                continue
            content = choices[0].get("message", {}).get("content", "")
            if not content:
                continue
            mappings = _extract_json(content)
            if not isinstance(mappings, list):
                continue
            results[cve_id] = mappings
        except Exception as e:
            logger.debug(f"Parse Stage 2 line failed: {e}")
    return results


# ---------------------------------------------------------------------------
# Stage 3: ATT&CK → Control (mapping only; validation skipped in batch mode)
# ---------------------------------------------------------------------------

def build_stage3_jsonl(
    triples_with_prompts: List[Dict[str, Any]],
    model: Optional[str] = None,
) -> str:
    """
    Build JSONL for Stage 3 (ATT&CK→Control) batch.
    triples_with_prompts: list of {
        "custom_id": "stage3-T1078:persistence:cis_v8_1",
        "system_prompt": "...",
        "user_prompt": "...",
    }
    """
    model = model or _get_model()
    lines = []
    for item in triples_with_prompts:
        req = {
            "custom_id": item["custom_id"],
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": model,
                "messages": [
                    {"role": "system", "content": item["system_prompt"]},
                    {"role": "user", "content": item["user_prompt"]},
                ],
                **_chat_completion_body_extras(),
            },
        }
        lines.append(json.dumps(req))
    return "\n".join(lines)


def parse_stage3_output(output_jsonl: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Parse Stage 3 batch output. Returns {custom_id: [control_mappings]}.
    """
    results = {}
    for line in output_jsonl.strip().split("\n"):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            custom_id = row.get("custom_id", "")
            if not custom_id.startswith("stage3-"):
                continue
            resp = row.get("response", {})
            if resp.get("status_code") != 200:
                logger.warning(f"Stage 3 batch failed for {custom_id}: {resp}")
                results[custom_id] = []
                continue
            body = resp.get("body", {})
            choices = body.get("choices", [])
            if not choices:
                results[custom_id] = []
                continue
            content = choices[0].get("message", {}).get("content", "")
            if not content:
                results[custom_id] = []
                continue
            mappings = _extract_json(content)
            if not isinstance(mappings, list):
                results[custom_id] = []
                continue
            results[custom_id] = mappings
        except Exception as e:
            logger.warning(f"Parse Stage 3 line failed: {e}")
    return results


# ---------------------------------------------------------------------------
# Batch lifecycle: upload, create, poll, download
# ---------------------------------------------------------------------------

def upload_and_create_batch(
    jsonl_content: str,
    endpoint: str = "/v1/chat/completions",
    metadata: Optional[Dict[str, str]] = None,
) -> str:
    """
    Upload JSONL to Files API, create batch, return batch_id.
    """
    client = _get_openai_client()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        f.write(jsonl_content)
        tmp_path = f.name
    try:
        with open(tmp_path, "rb") as f:
            file_resp = client.files.create(file=f, purpose="batch")
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    file_id = file_resp.id
    logger.info(f"Uploaded batch input file: {file_id}")

    batch_params = {
        "input_file_id": file_id,
        "endpoint": endpoint,
        "completion_window": "24h",
    }
    if metadata:
        batch_params["metadata"] = metadata

    batch = client.batches.create(**batch_params)
    batch_id = batch.id
    logger.info(f"Created batch: {batch_id}")
    return batch_id


def _is_batch_output_line_failure(row: Dict[str, Any]) -> bool:
    """True if a batch output JSONL line represents a failed request."""
    if row.get("error"):
        return True
    resp = row.get("response")
    if isinstance(resp, dict):
        sc = resp.get("status_code")
        if sc is not None and sc != 200:
            return True
    return False


def _summarize_batch_errors(err_jsonl: str, max_samples: int = 5) -> str:
    """
    Parse OpenAI batch JSONL: dedicated error file OR output file lines with failures.
    Output file failures use response.status_code != 200 or top-level error (e.g. batch_cancelled).
    """
    from collections import Counter
    codes: Counter = Counter()
    samples: List[str] = []
    for line in err_jsonl.strip().split("\n"):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            custom_id = (row.get("custom_id") or "")[:60]
            code = None
            msg = ""
            resp = row.get("response")
            if isinstance(resp, dict) and resp.get("status_code") not in (None, 200):
                body = resp.get("body") or {}
                inner = body.get("error") or {}
                code = inner.get("code") or f"http_{resp.get('status_code')}"
                msg = (inner.get("message") or "")[:160]
            elif row.get("error"):
                err = row["error"]
                code = err.get("code", "unknown")
                msg = (err.get("message") or "")[:160]
            if code is not None:
                codes[code] += 1
                if len(samples) < max_samples and msg:
                    suffix = f" ({custom_id})" if custom_id else ""
                    samples.append(f"  [{code}]{suffix} {msg}")
        except Exception:
            pass
    if not codes:
        return "No parseable errors in content."
    parts = [f"Error codes: {dict(codes)}"]
    if samples:
        parts.append("Sample errors:")
        parts.extend(samples[:max_samples])
    return "\n".join(parts)


def poll_batch_until_done(batch_id: str, poll_interval: int = 60) -> Dict[str, Any]:
    """
    Poll batch status until completed, failed, expired, or cancelled.
    Returns final batch object.
    """
    client = _get_openai_client()
    while True:
        batch = client.batches.retrieve(batch_id)
        status = batch.status
        rc = getattr(batch, "request_counts", None)
        completed = getattr(rc, "completed", 0) if rc else 0
        failed = getattr(rc, "failed", 0) if rc else 0
        logger.info(f"Batch {batch_id}: {status} | completed={completed}, failed={failed}")
        if status in ("completed", "failed", "expired", "cancelled"):
            return batch
        time.sleep(poll_interval)


def download_batch_output(batch_id: str, max_retries: int = 5, retry_delay: int = 10) -> str:
    """
    Download batch output file content. Returns JSONL string (may be empty).
    Successful lines are parsed by callers; failed requests are skipped in parsers.
    Does not raise when an entire job has zero successes — returns "" so pipelines
    can continue with other chunks / CVEs.
    Retries if output_file_id is not yet populated (propagation delay after completion).
    """
    client = _get_openai_client()
    terminal_no_output = ("failed", "expired", "cancelled")
    for attempt in range(max_retries):
        batch = client.batches.retrieve(batch_id)
        output_file_id = getattr(batch, "output_file_id", None)
        if output_file_id:
            return client.files.content(output_file_id).text

        status = batch.status
        rc = getattr(batch, "request_counts", None)
        completed = getattr(rc, "completed", 0) if rc else 0
        failed = getattr(rc, "failed", 0) if rc else 0

        if status in terminal_no_output:
            logger.warning(
                f"Batch {batch_id} status={status} (completed={completed}, failed={failed}); "
                "no output file — continuing without this job's results."
            )
            return ""

        if status != "completed":
            if attempt < max_retries - 1:
                logger.info(
                    f"Batch {batch_id}: status={status}, waiting for output_file_id "
                    f"({attempt + 1}/{max_retries})"
                )
                time.sleep(retry_delay)
                continue
            logger.warning(f"Batch {batch_id} still status={status} after waits; returning empty output.")
            return ""

        if completed == 0 and failed > 0:
            err_msg = (
                f"Batch {batch_id}: all {failed} request(s) in this job failed "
                f"(continuing; other chunks / CVEs are unaffected)."
            )
            error_file_id = getattr(batch, "error_file_id", None)
            if error_file_id:
                try:
                    err_content = client.files.content(error_file_id).text
                    summary = _summarize_batch_errors(err_content, max_samples=5)
                    logger.error(f"{err_msg}\n{summary}")
                    err_path = Path(f"batch_errors_{batch_id}.jsonl")
                    err_path.write_text(err_content, encoding="utf-8")
                    logger.error(f"Full error file saved to {err_path}")
                except Exception as e:
                    logger.error(f"{err_msg} (error file download failed: {e})")
            else:
                logger.error(err_msg)
            return ""

        if attempt < max_retries - 1:
            logger.info(
                f"Batch {batch_id}: output_file_id not yet available, retrying in {retry_delay}s "
                f"({attempt + 1}/{max_retries})"
            )
            time.sleep(retry_delay)

    batch = client.batches.retrieve(batch_id)
    rc = getattr(batch, "request_counts", None)
    completed = getattr(rc, "completed", 0) if rc else 0
    failed = getattr(rc, "failed", 0) if rc else 0
    if completed > 0:
        logger.error(
            f"Batch {batch_id}: completed with {completed} successes but output_file_id never appeared "
            f"after {max_retries} retries (failed={failed}). Returning empty output."
        )
    else:
        logger.error(
            f"Batch {batch_id}: no output_file_id after {max_retries} retries "
            f"(completed={completed}, failed={failed}). Returning empty output."
        )
    return ""


def download_batch_errors(batch_id: str) -> Optional[str]:
    """
    Download batch failures for inspection.
    Uses error_file_id when set; otherwise extracts failed lines from output_file_id
    (OpenAI often puts per-request 400s in the output file, not the error file).
    """
    client = _get_openai_client()
    batch = client.batches.retrieve(batch_id)
    error_file_id = getattr(batch, "error_file_id", None)
    if error_file_id:
        return client.files.content(error_file_id).text
    output_file_id = getattr(batch, "output_file_id", None)
    if not output_file_id:
        return None
    text = client.files.content(output_file_id).text
    failed_lines: List[str] = []
    for line in text.strip().split("\n"):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if _is_batch_output_line_failure(row):
                failed_lines.append(line)
        except Exception:
            continue
    if not failed_lines:
        return None
    return "\n".join(failed_lines)

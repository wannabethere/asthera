#!/usr/bin/env python3
"""
CWE/CAPEC/ATT&CK/KEV enricher — run separately from CVE pipeline.
Fetches threat intel and ingests into DB. CVE pipeline uses this data when available.

Sources: NVD CVE API 2.0, CWE REST API, CAPEC XML, MITRE ATT&CK TAXII 2.1, CISA KEV JSON.
Env: NVD_API_KEY (optional but recommended).

Usage:
  # Fetch to files only
  python -m indexing_cli.cwe_enrich

  # Fetch and ingest into DB
  python -m indexing_cli.cwe_enrich --ingest-db --data-dir threat_intel_data

Workflow (CWE + CAPEC from local CSVs, no API):
  1. python -m indexing_cli.cwe_csv_ingest --cwe-dir /path/to/cwe/csvs --vector-store
  2. python -m indexing_cli.capec_csv_ingest --capec-dir /path/to/capec/csvs --vector-store
  3. python -m indexing_cli.cwe_enrich --ingest-db --all-from-db --data-dir threat_intel_data  # DB only, no web
  4. python -m indexing_cli.cwe_capec_attack_mapper --data-dir threat_intel_data
"""

from __future__ import annotations

import json
import os
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

OUT_DIR = Path("threat_intel_data")
OUT_DIR.mkdir(parents=True, exist_ok=True)

NVD_API_KEY = os.getenv("NVD_API_KEY")

# Top CWEs you mentioned + a few common exploit-relevant ones
DEFAULT_CWES = [
    "CWE-476",  # NULL Pointer Dereference
    "CWE-416",  # Use After Free
    "CWE-125",  # Out-of-bounds Read
    "CWE-787",  # Out-of-bounds Write
    "CWE-362",  # Race Condition
    "CWE-20",   # Improper Input Validation
    "CWE-22",   # Path Traversal
    "CWE-78",   # OS Command Injection
    "CWE-79",   # XSS
    "CWE-89",   # SQL Injection
    "CWE-94",   # Code Injection
    "CWE-119",  # Improper Restriction within Buffer Bounds
    "CWE-190",  # Integer Overflow or Wraparound
    "CWE-287",  # Improper Authentication
    "CWE-306",  # Missing Authentication for Critical Function
]

NVD_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"
CWE_API_BASE = "https://cwe-api.mitre.org/api/v1"
CAPEC_XML_URL = "https://capec.mitre.org/data/xml/capec_latest.xml"
ATTACK_TAXII_BASE = "https://attack-taxii.mitre.org/api/v21"
CISA_KEV_JSON_URL = (
    "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
)

REQUEST_TIMEOUT = 60


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def session_with_defaults() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": "cwe-attack-enrichment/1.0",
            "Accept": "application/json",
        }
    )
    if NVD_API_KEY:
        s.headers["apiKey"] = NVD_API_KEY
    return s


def _json_default(obj: Any) -> Any:
    """Handle Decimal and other non-JSON-serializable types."""
    from decimal import Decimal
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=_json_default), encoding="utf-8")


def save_text(path: Path, data: str) -> None:
    path.write_text(data, encoding="utf-8")


def get_json(session: requests.Session, url: str, **kwargs) -> Dict[str, Any]:
    resp = session.get(url, timeout=REQUEST_TIMEOUT, **kwargs)
    resp.raise_for_status()
    return resp.json()


def get_json_with_retry(
    session: requests.Session,
    url: str,
    max_retries: int = 5,
    base_delay: float = 30.0,
    **kwargs,
) -> Dict[str, Any]:
    """Fetch JSON with retry on 429 (Too Many Requests). Matches cve_enrichment rate-limit handling."""
    last_exc = None
    for attempt in range(max_retries):
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT, **kwargs)
            if resp.status_code == 429:
                wait = base_delay * (2 ** attempt)
                _progress(f"  NVD rate limit (429), waiting {wait:.0f}s before retry {attempt + 1}/{max_retries}...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                wait = base_delay * (2 ** attempt)
                _progress(f"  NVD rate limit (429), waiting {wait:.0f}s before retry {attempt + 1}/{max_retries}...")
                time.sleep(wait)
                last_exc = e
                continue
            raise
        except Exception as e:
            last_exc = e
            if attempt + 1 < max_retries:
                wait = base_delay * (2 ** attempt)
                time.sleep(wait)
            else:
                raise
    if last_exc:
        raise last_exc
    return {}


# ---------------------------------------------------------------------
# NVD
# ---------------------------------------------------------------------

def fetch_nvd_cves_for_cwe(
    session: requests.Session,
    cwe_id: str,
    results_per_page: int = 2000,
    max_records: Optional[int] = None,
    include_only_kev: bool = False,
) -> List[Dict[str, Any]]:
    """
    Fetch all CVEs from NVD for a given CWE using offset-based pagination.
    """
    start_index = 0
    all_items: List[Dict[str, Any]] = []

    while True:
        params = {
            "cweId": cwe_id,
            "startIndex": start_index,
            "resultsPerPage": results_per_page,
            "noRejected": None,  # flag parameter
        }
        if include_only_kev:
            params["hasKev"] = None  # flag parameter

        # requests removes params with value None, so handle flags manually
        query_parts = [
            f"cweId={cwe_id}",
            f"startIndex={start_index}",
            f"resultsPerPage={results_per_page}",
            "noRejected",
        ]
        if include_only_kev:
            query_parts.append("hasKev")
        url = f"{NVD_BASE}?{'&'.join(query_parts)}"

        data = get_json_with_retry(session, url)
        vulns = data.get("vulnerabilities", [])
        all_items.extend(vulns)

        total = data.get("totalResults", len(all_items))
        print(f"[NVD] {cwe_id}: fetched {len(all_items)} / {total}", flush=True)

        if max_records and len(all_items) >= max_records:
            return all_items[:max_records]

        start_index += len(vulns)
        if not vulns or start_index >= total:
            break

        # polite pacing; more important if you have no API key
        time.sleep(0.6 if NVD_API_KEY else 2.0)

    return all_items


def normalize_nvd_vuln(v: Dict[str, Any]) -> Dict[str, Any]:
    cve = v.get("cve", {})
    weaknesses = []
    for w in cve.get("weaknesses", []):
        descs = w.get("description", [])
        for d in descs:
            weaknesses.append(d.get("value"))

    metrics = cve.get("metrics", {})
    descriptions = cve.get("descriptions", [])
    desc_en = next((d.get("value") for d in descriptions if d.get("lang") == "en"), None)

    refs = [r.get("url") for r in cve.get("references", []) if r.get("url")]

    return {
        "cve_id": cve.get("id"),
        "published": cve.get("published"),
        "last_modified": cve.get("lastModified"),
        "source_identifier": cve.get("sourceIdentifier"),
        "vuln_status": cve.get("vulnStatus"),
        "description": desc_en,
        "weaknesses": sorted(set(w for w in weaknesses if w)),
        "metrics": metrics,
        "references": refs,
        "configurations": cve.get("configurations", []),
    }


# ---------------------------------------------------------------------
# CWE
# ---------------------------------------------------------------------

def fetch_cwe_entry(session: requests.Session, cwe_id: str) -> Dict[str, Any]:
    """
    Attempts a few plausible endpoint patterns because the CWE REST API has
    multiple resources and may evolve. If one pattern fails, the next is tried.
    """
    candidate_urls = [
        f"{CWE_API_BASE}/cwe/{cwe_id}",
        f"{CWE_API_BASE}/weakness/{cwe_id}",
        f"{CWE_API_BASE}/weaknesses/{cwe_id}",
        f"{CWE_API_BASE}/cwes/{cwe_id}",
    ]
    errors = []
    for url in candidate_urls:
        try:
            return get_json(session, url)
        except Exception as exc:
            errors.append(f"{url} -> {exc}")
    raise RuntimeError(f"Could not fetch {cwe_id} from CWE API.\n" + "\n".join(errors))


# ---------------------------------------------------------------------
# CAPEC
# ---------------------------------------------------------------------

def fetch_capec_xml(session: requests.Session) -> str:
    resp = session.get(CAPEC_XML_URL, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.text


def parse_capec_cwe_links(xml_text: str) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, List[str]]]:
    """
    Returns:
      1) capec_by_id: CAPEC metadata keyed by CAPEC-ID
      2) cwe_to_capec: map from CWE-ID -> [CAPEC-ID, ...]
    """
    ns = {"capec": "http://capec.mitre.org/capec-3"}
    root = ET.fromstring(xml_text)

    capec_by_id: Dict[str, Dict[str, Any]] = {}
    cwe_to_capec: Dict[str, List[str]] = {}

    for ap in root.findall(".//capec:Attack_Pattern", ns):
        capec_id = ap.attrib.get("ID")
        name = ap.attrib.get("Name")
        abstraction = ap.attrib.get("Abstraction")
        status = ap.attrib.get("Status")

        capec_key = f"CAPEC-{capec_id}" if capec_id else None
        if not capec_key:
            continue

        summary = None
        summary_el = ap.find("./capec:Description", ns)
        if summary_el is not None and summary_el.text:
            summary = summary_el.text.strip()

        related_cwes = []
        for rw in ap.findall(".//capec:Related_Weakness", ns):
            cwe_val = rw.attrib.get("CWE_ID")
            if cwe_val:
                cwe_id = f"CWE-{cwe_val}" if not str(cwe_val).startswith("CWE-") else str(cwe_val)
                related_cwes.append(cwe_id)
                cwe_to_capec.setdefault(cwe_id, []).append(capec_key)

        capec_by_id[capec_key] = {
            "capec_id": capec_key,
            "name": name,
            "abstraction": abstraction,
            "status": status,
            "description": summary,
            "related_cwes": sorted(set(related_cwes)),
        }

    for cwe_id, capecs in cwe_to_capec.items():
        cwe_to_capec[cwe_id] = sorted(set(capecs))

    return capec_by_id, cwe_to_capec


# ---------------------------------------------------------------------
# ATT&CK TAXII
# ---------------------------------------------------------------------

def fetch_attack_collections(session: requests.Session) -> List[Dict[str, Any]]:
    headers = {"Accept": "application/taxii+json;version=2.1"}
    data = get_json(session, f"{ATTACK_TAXII_BASE}/collections", headers=headers)
    return data.get("collections", [])


def find_enterprise_attack_collection_id(collections: Iterable[Dict[str, Any]]) -> str:
    for c in collections:
        if c.get("title") == "Enterprise ATT&CK":
            return c["id"]
    raise RuntimeError("Could not find Enterprise ATT&CK TAXII collection")


def fetch_attack_objects(session: requests.Session, collection_id: str) -> List[Dict[str, Any]]:
    """
    Fetch STIX objects from the Enterprise ATT&CK collection.
    """
    headers = {"Accept": "application/taxii+json;version=2.1"}
    url = f"{ATTACK_TAXII_BASE}/collections/{collection_id}/objects"
    data = get_json(session, url, headers=headers)
    return data.get("objects", [])


def extract_attack_techniques(objects: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Pull out Enterprise ATT&CK techniques/sub-techniques from STIX.
    """
    techniques = []
    for obj in objects:
        if obj.get("type") != "attack-pattern":
            continue
        # ATT&CK-specific external ID lives in external_references
        attack_id = None
        for ref in obj.get("external_references", []):
            if ref.get("source_name") == "mitre-attack":
                attack_id = ref.get("external_id")
                break

        if not attack_id:
            continue

        techniques.append(
            {
                "attack_id": attack_id,
                "stix_id": obj.get("id"),
                "name": obj.get("name"),
                "description": obj.get("description"),
                "domains": obj.get("x_mitre_domains", []),
                "platforms": obj.get("x_mitre_platforms", []),
                "is_subtechnique": obj.get("x_mitre_is_subtechnique", False),
                "kill_chain_phases": obj.get("kill_chain_phases", []),
                "revoked": obj.get("revoked", False),
                "deprecated": obj.get("x_mitre_deprecated", False),
            }
        )
    return sorted(techniques, key=lambda x: x["attack_id"])


# ---------------------------------------------------------------------
# CISA KEV
# ---------------------------------------------------------------------

def fetch_cisa_kev(session: requests.Session) -> Dict[str, Any]:
    return get_json(session, CISA_KEV_JSON_URL)


# ---------------------------------------------------------------------
# Optional convenience joins
# ---------------------------------------------------------------------

def build_summary(
    cwe_ids: List[str],
    cwe_entries: Dict[str, Any],
    cwe_to_capec: Dict[str, List[str]],
    capec_by_id: Dict[str, Dict[str, Any]],
    nvd_by_cwe: Dict[str, List[Dict[str, Any]]],
    kev_catalog: Dict[str, Any],
) -> Dict[str, Any]:
    kev_cves = {
        item.get("cveID")
        for item in kev_catalog.get("vulnerabilities", [])
        if item.get("cveID")
    }

    summary: Dict[str, Any] = {}
    for cwe_id in cwe_ids:
        normalized_cves = [normalize_nvd_vuln(v) for v in nvd_by_cwe.get(cwe_id, [])]
        cve_ids_for_cwe = {v["cve_id"] for v in normalized_cves if v.get("cve_id")}
        related_capecs = cwe_to_capec.get(cwe_id, [])

        summary[cwe_id] = {
            "cwe": cwe_entries.get(cwe_id, {}),
            "nvd_cve_count": len(normalized_cves),
            "kev_cve_count": len(cve_ids_for_cwe & kev_cves),
            "related_capec_ids": related_capecs,
            "related_capecs": [capec_by_id[cid] for cid in related_capecs if cid in capec_by_id],
            "sample_cves": normalized_cves[:25],
        }
    return summary


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main(cwe_ids: Optional[List[str]] = None) -> None:
    cwe_ids = cwe_ids or DEFAULT_CWES
    session = session_with_defaults()

    # 1) CWE metadata
    cwe_entries: Dict[str, Any] = {}
    for cwe_id in cwe_ids:
        try:
            cwe_entries[cwe_id] = fetch_cwe_entry(session, cwe_id)
            print(f"[CWE] fetched {cwe_id}")
            time.sleep(0.2)
        except Exception as exc:
            print(f"[CWE] failed for {cwe_id}: {exc}")
            cwe_entries[cwe_id] = {"error": str(exc)}

    save_json(OUT_DIR / "cwe_entries.json", cwe_entries)

    # 2) CAPEC
    capec_xml = fetch_capec_xml(session)
    save_text(OUT_DIR / "capec_latest.xml", capec_xml)
    capec_by_id, cwe_to_capec = parse_capec_cwe_links(capec_xml)
    save_json(OUT_DIR / "capec_by_id.json", capec_by_id)
    save_json(OUT_DIR / "cwe_to_capec.json", cwe_to_capec)

    # 3) NVD CVEs by CWE
    nvd_by_cwe: Dict[str, List[Dict[str, Any]]] = {}
    for cwe_id in cwe_ids:
        try:
            vulns = fetch_nvd_cves_for_cwe(session, cwe_id)
            nvd_by_cwe[cwe_id] = vulns
        except Exception as exc:
            print(f"[NVD] failed for {cwe_id}: {exc}")
            nvd_by_cwe[cwe_id] = [{"error": str(exc)}]

    save_json(OUT_DIR / "nvd_raw_by_cwe.json", nvd_by_cwe)

    normalized_nvd = {
        cwe_id: [normalize_nvd_vuln(v) for v in vulns if "cve" in v]
        for cwe_id, vulns in nvd_by_cwe.items()
    }
    save_json(OUT_DIR / "nvd_normalized_by_cwe.json", normalized_nvd)

    # 4) ATT&CK
    collections = fetch_attack_collections(session)
    save_json(OUT_DIR / "attack_taxii_collections.json", collections)

    enterprise_collection_id = find_enterprise_attack_collection_id(collections)
    attack_objects = fetch_attack_objects(session, enterprise_collection_id)
    save_json(OUT_DIR / "attack_enterprise_objects.json", attack_objects)

    attack_techniques = extract_attack_techniques(attack_objects)
    save_json(OUT_DIR / "attack_enterprise_techniques.json", attack_techniques)

    # 5) CISA KEV
    kev_catalog = fetch_cisa_kev(session)
    save_json(OUT_DIR / "cisa_kev.json", kev_catalog)

    # 6) Summary structure for downstream mapping
    summary = build_summary(
        cwe_ids=cwe_ids,
        cwe_entries=cwe_entries,
        cwe_to_capec=cwe_to_capec,
        capec_by_id=capec_by_id,
        nvd_by_cwe=nvd_by_cwe,
        kev_catalog=kev_catalog,
    )
    save_json(OUT_DIR / "cwe_enrichment_summary.json", summary)

    print("\nDone.")
    print(f"Files written to: {OUT_DIR.resolve()}")


def _progress(msg: str) -> None:
    """Print progress with immediate flush (avoids buffering when not a TTY)."""
    print(msg, flush=True)


def _load_cwe_ids_from_db() -> List[str]:
    """Load CWE IDs from cwe_entries table (populated by cwe_csv_ingest)."""
    try:
        from app.storage.sqlalchemy_session import get_security_intel_session
        from sqlalchemy import text
        with get_security_intel_session("cve_attack") as session:
            rows = session.execute(text("SELECT cwe_id FROM cwe_entries ORDER BY cwe_id")).fetchall()
            return [r[0] for r in rows if r[0]]
    except Exception:
        return []


def _load_capec_from_db() -> Tuple[Dict[str, Dict[str, Any]], Dict[str, List[str]]]:
    """Load CAPEC and CWE→CAPEC from DB (populated by capec_csv_ingest)."""
    capec_by_id: Dict[str, Dict[str, Any]] = {}
    cwe_to_capec: Dict[str, List[str]] = {}
    try:
        from app.storage.sqlalchemy_session import get_security_intel_session
        from sqlalchemy import text
        with get_security_intel_session("cve_attack") as session:
            for row in session.execute(text(
                "SELECT capec_id, name, description, related_cwes, raw_data FROM capec"
            )).fetchall():
                capec_id, name, desc, related_json, raw_json = row[0], row[1], row[2], row[3], row[4]
                if not capec_id:
                    continue
                related = json.loads(related_json) if related_json else []
                capec_by_id[capec_id] = {
                    "capec_id": capec_id,
                    "name": name or "",
                    "description": desc or "",
                    "related_cwes": related,
                }
            for row in session.execute(text(
                "SELECT cwe_id, capec_id FROM cwe_to_capec"
            )).fetchall():
                cwe_id, capec_id = row[0], row[1]
                if cwe_id and capec_id:
                    cwe_to_capec.setdefault(cwe_id, []).append(capec_id)
            for cwe_id in cwe_to_capec:
                cwe_to_capec[cwe_id] = sorted(set(cwe_to_capec[cwe_id]))
    except Exception as e:
        _progress(f"Warning: could not load CAPEC from DB: {e}")
    return capec_by_id, cwe_to_capec


def _load_nvd_from_db(cwe_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Load NVD CVEs by CWE from nvd_cves_by_cwe table.
    If empty, fall back to cve_intelligence (populated by cve_enrichment pipeline).
    """
    nvd_normalized: Dict[str, List[Dict[str, Any]]] = {cid: [] for cid in cwe_ids}
    try:
        from app.storage.sqlalchemy_session import get_security_intel_session
        from sqlalchemy import text
        with get_security_intel_session("cve_attack") as session:
            for row in session.execute(text(
                "SELECT cwe_id, cve_id, normalized_data FROM nvd_cves_by_cwe"
            )).fetchall():
                cwe_id, cve_id, norm_json = row[0], row[1], row[2]
                if not cwe_id or not cve_id:
                    continue
                if cwe_id not in nvd_normalized:
                    nvd_normalized[cwe_id] = []
                v = json.loads(norm_json) if norm_json else {"cve_id": cve_id}
                if not v.get("cve_id"):
                    v["cve_id"] = cve_id
                nvd_normalized[cwe_id].append(v)
        total = sum(len(v) for v in nvd_normalized.values())
        if total == 0:
            nvd_normalized = _load_nvd_from_cve_intelligence(cwe_ids)
    except Exception as e:
        if "does not exist" not in str(e).lower():
            _progress(f"Warning: could not load NVD from DB: {e}")
        nvd_normalized = _load_nvd_from_cve_intelligence(cwe_ids)
    return nvd_normalized


def _load_nvd_from_cve_intelligence(cwe_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Build CWE→CVE mapping from cve_intelligence (populated by cve_enrichment pipeline).
    Reuses same DB tables as CVE→ATT&CK pipeline.
    """
    nvd_normalized: Dict[str, List[Dict[str, Any]]] = {cid: [] for cid in cwe_ids}
    try:
        from app.storage.sqlalchemy_session import get_security_intel_session
        from sqlalchemy import text
        with get_security_intel_session("cve_attack") as session:
            result = session.execute(text(
                "SELECT cve_id, description, cvss_score, cvss_vector, cwe_ids, published_date, last_modified FROM cve_intelligence"
            ))
            for row in result.fetchall():
                cve_id, desc, cvss, vector, cwe_ids_json, pub, mod = row[0], row[1], row[2], row[3], row[4], row[5], row[6]
                if not cve_id:
                    continue
                cwe_list = json.loads(cwe_ids_json) if isinstance(cwe_ids_json, str) else (cwe_ids_json or [])
                if not cwe_list:
                    continue
                cvss_val = float(cvss) if cvss is not None else 0.0
                v = {
                    "cve_id": cve_id,
                    "description": desc or "",
                    "published": pub or "",
                    "last_modified": mod or "",
                    "weaknesses": sorted(set(c for c in cwe_list if c)),
                    "metrics": {"cvssMetricV31": [{"cvssData": {"baseScore": cvss_val, "vectorString": vector or ""}}]} if cvss_val else {},
                    "references": [],
                    "configurations": [],
                }
                for cwe_id in cwe_list:
                    if cwe_id not in nvd_normalized:
                        nvd_normalized[cwe_id] = []
                    nvd_normalized[cwe_id].append(v)
        total = sum(len(v) for v in nvd_normalized.values())
        if total > 0:
            _progress(f"  Built CWE→CVE from cve_intelligence: {total} CVEs across {len([k for k, v in nvd_normalized.items() if v])} CWEs")
    except Exception as e:
        if "does not exist" not in str(e).lower() and "relation" not in str(e).lower():
            _progress(f"Warning: cve_intelligence fallback failed: {e}")
    return nvd_normalized


def _load_attack_from_db() -> List[Dict[str, Any]]:
    """Load ATT&CK techniques from attack_enterprise_techniques table."""
    techniques: List[Dict[str, Any]] = []
    try:
        from app.storage.sqlalchemy_session import get_security_intel_session
        from sqlalchemy import text
        with get_security_intel_session("cve_attack") as session:
            for row in session.execute(text(
                "SELECT technique_id, name, description, raw_data FROM attack_enterprise_techniques"
            )).fetchall():
                tid, name, desc, raw_json = row[0], row[1], row[2], row[3]
                if not tid:
                    continue
                raw = json.loads(raw_json) if raw_json else {}
                techniques.append({
                    "attack_id": tid,
                    "name": name or raw.get("name", ""),
                    "description": desc or raw.get("description", ""),
                    **{k: v for k, v in raw.items() if k not in ("attack_id", "name", "description")},
                })
        techniques.sort(key=lambda t: t.get("attack_id", ""))
    except Exception as e:
        _progress(f"Warning: could not load ATT&CK from DB: {e}")
    return techniques


def _load_kev_from_db() -> Dict[str, Any]:
    """Load CISA KEV from cisa_kev table."""
    vulns: List[Dict[str, Any]] = []
    catalog_date = ""
    try:
        from app.storage.sqlalchemy_session import get_security_intel_session
        from sqlalchemy import text
        with get_security_intel_session("cve_attack") as session:
            for row in session.execute(text(
                "SELECT cve_id, catalog_date, raw_data FROM cisa_kev"
            )).fetchall():
                cve_id, cat_date, raw_json = row[0], row[1], row[2]
                if not cve_id:
                    continue
                raw = json.loads(raw_json) if raw_json else {}
                raw["cveID"] = cve_id
                vulns.append(raw)
                if cat_date:
                    catalog_date = cat_date
    except Exception as e:
        _progress(f"Warning: could not load KEV from DB: {e}")
    return {"vulnerabilities": vulns, "dateReleased": catalog_date, "catalogVersion": catalog_date}


def run_fetch_and_ingest(
    cwe_ids: Optional[List[str]] = None,
    out_dir: Optional[Path] = None,
    skip_cwe_fetch: bool = False,
    skip_capec_fetch: bool = False,
    all_from_db: bool = False,
    ingest_vector_store: bool = False,
) -> Dict[str, int]:
    """
    Fetch all CWE threat intel and ingest into DB.
    Returns summary of ingested row counts.
    """
    from app.ingestion.cwe_threat_intel.ingest import ingest_from_fetched_data

    out = out_dir or OUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    if all_from_db:
        skip_cwe_fetch = True
        skip_capec_fetch = True
        # Ensure tables exist before loading (cisa_kev, attack_enterprise_techniques, etc.)
        try:
            from app.storage.sqlalchemy_session import get_security_intel_session
            from app.ingestion.cwe_threat_intel.db_schema import create_cwe_threat_intel_tables
            with get_security_intel_session("cve_attack") as session:
                create_cwe_threat_intel_tables(session)
        except Exception:
            pass

    if skip_cwe_fetch:
        cwe_ids = _load_cwe_ids_from_db() or DEFAULT_CWES
        _progress("=" * 60)
        _progress("CWE/CAPEC/ATT&CK/KEV enricher — DB only (no web fetch)")
        _progress("=" * 60)
        _progress(f"CWEs: {len(cwe_ids)} from cwe_entries | Output: {out}")
    else:
        cwe_ids = cwe_ids or DEFAULT_CWES
        _progress("=" * 60)
        _progress("CWE/CAPEC/ATT&CK/KEV enricher — fetch and ingest to DB")
        _progress("=" * 60)
        _progress(f"CWEs: {len(cwe_ids)} | Output: {out}")

    _progress("")

    session = session_with_defaults()

    # 1) CWE metadata (skip if using DB)
    if skip_cwe_fetch:
        _progress("[1/6] Skipping CWE fetch (using cwe_entries from DB)")
        cwe_entries = {}  # Not re-ingesting; already in DB from cwe_csv_ingest
    else:
        _progress("[1/6] Fetching CWE metadata...")
        cwe_entries = {}
        for i, cwe_id in enumerate(cwe_ids):
            try:
                cwe_entries[cwe_id] = fetch_cwe_entry(session, cwe_id)
                _progress(f"  [{i+1}/{len(cwe_ids)}] {cwe_id} ✓")
                time.sleep(0.2)
            except Exception as exc:
                _progress(f"  [{i+1}/{len(cwe_ids)}] {cwe_id} ✗ {exc}")
                cwe_entries[cwe_id] = {"error": str(exc)}

    # 2) CAPEC
    if skip_capec_fetch:
        _progress("\n[2/6] Skipping CAPEC fetch (using capec + cwe_to_capec from DB)")
        capec_by_id, cwe_to_capec = _load_capec_from_db()
        capec_xml = ""  # Not saved when from DB
        _progress(f"  Loaded {len(capec_by_id)} CAPEC entries, {len(cwe_to_capec)} CWE→CAPEC links from DB")
    else:
        _progress("\n[2/6] Fetching CAPEC XML...")
        capec_xml = fetch_capec_xml(session)
        capec_by_id, cwe_to_capec = parse_capec_cwe_links(capec_xml)
        _progress(f"  Parsed {len(capec_by_id)} CAPEC entries, {len(cwe_to_capec)} CWE→CAPEC links")

    # 3) NVD CVEs by CWE
    if all_from_db:
        _progress("\n[3/6] Loading NVD from DB...")
        normalized_nvd = _load_nvd_from_db(cwe_ids)
        total_cves = sum(len(v) for v in normalized_nvd.values())
        _progress(f"  Loaded {total_cves} CVEs for {len(cwe_ids)} CWEs from nvd_cves_by_cwe")
    else:
        _progress("\n[3/6] Fetching NVD CVEs by CWE (rate-limited; may take 15–90 min for 900+ CWEs)...")
        nvd_delay = 1.0 if NVD_API_KEY else 7.0  # NVD: 50/30s with key, 5/30s without
        nvd_by_cwe = {}
        for i, cwe_id in enumerate(cwe_ids):
            try:
                vulns = fetch_nvd_cves_for_cwe(session, cwe_id)
                nvd_by_cwe[cwe_id] = vulns
                _progress(f"  [{i+1}/{len(cwe_ids)}] {cwe_id}: {len(vulns)} CVEs")
            except Exception as exc:
                _progress(f"  [{i+1}/{len(cwe_ids)}] {cwe_id} ✗ {exc}")
                nvd_by_cwe[cwe_id] = [{"error": str(exc)}]
            if i + 1 < len(cwe_ids):
                time.sleep(nvd_delay)

        normalized_nvd = {
            cwe_id: [normalize_nvd_vuln(v) for v in vulns if "cve" in v]
            for cwe_id, vulns in nvd_by_cwe.items()
        }
        total_cves = sum(len(v) for v in normalized_nvd.values())
        _progress(f"  Total: {total_cves} CVEs normalized")

    # 4) ATT&CK
    if all_from_db:
        _progress("\n[4/6] Loading ATT&CK from DB...")
        attack_techniques = _load_attack_from_db()
        _progress(f"  Loaded {len(attack_techniques)} techniques from attack_enterprise_techniques")
    else:
        _progress("\n[4/6] Fetching ATT&CK Enterprise (TAXII)...")
        collections = fetch_attack_collections(session)
        enterprise_collection_id = find_enterprise_attack_collection_id(collections)
        attack_objects = fetch_attack_objects(session, enterprise_collection_id)
        attack_techniques = extract_attack_techniques(attack_objects)
        _progress(f"  {len(attack_techniques)} techniques extracted")

    # 5) CISA KEV
    if all_from_db:
        _progress("\n[5/6] Loading CISA KEV from DB...")
        kev_catalog = _load_kev_from_db()
        kev_count = len(kev_catalog.get("vulnerabilities", []))
        _progress(f"  Loaded {kev_count} KEV entries from cisa_kev")
    else:
        _progress("\n[5/6] Fetching CISA KEV...")
        kev_catalog = fetch_cisa_kev(session)
        kev_count = len(kev_catalog.get("vulnerabilities", []))
        _progress(f"  {kev_count} KEV entries")

    # 6) Ingest into DB
    _progress("\n[6/6] Ingesting into DB...")
    results = ingest_from_fetched_data(
        cwe_entries=cwe_entries if not skip_cwe_fetch else {},  # Don't overwrite DB CWE data
        capec_by_id=capec_by_id,
        cwe_to_capec=cwe_to_capec,
        nvd_normalized=normalized_nvd,
        attack_techniques=attack_techniques,
        kev_catalog=kev_catalog,
    )
    for k, v in results.items():
        _progress(f"  {k}: {v} rows")

    if ingest_vector_store:
        _progress("\n[Vector store] Ingesting CWE + CAPEC for semantic search...")
        try:
            from app.ingestion.cwe_threat_intel.vector_store_ingest import ingest_from_db_to_vector_store
            vs_results = ingest_from_db_to_vector_store()
            _progress(f"  CWE: {vs_results.get('cwe', 0)}, CAPEC: {vs_results.get('capec', 0)}")
        except Exception as e:
            _progress(f"  Vector store ingest failed: {e}")

    # Optionally save files (skip cwe_entries.json if we didn't fetch)
    if not skip_cwe_fetch:
        save_json(out / "cwe_entries.json", cwe_entries)
    if capec_xml:
        save_text(out / "capec_latest.xml", capec_xml)
    save_json(out / "capec_by_id.json", capec_by_id)
    save_json(out / "cwe_to_capec.json", cwe_to_capec)
    save_json(out / "nvd_raw_by_cwe.json", nvd_by_cwe if not all_from_db else {})
    save_json(out / "nvd_normalized_by_cwe.json", normalized_nvd)
    save_json(out / "attack_enterprise_techniques.json", attack_techniques)
    save_json(out / "cisa_kev.json", kev_catalog)
    _progress(f"\nFiles saved to {out}")

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CWE/CAPEC/ATT&CK/KEV enricher (run separately from CVE pipeline)")
    parser.add_argument("--ingest-db", action="store_true", help="Fetch and ingest into DB")
    parser.add_argument("--cwe-from-db", action="store_true",
                        help="Use CWE IDs from cwe_entries (run cwe_csv_ingest first). Skips CWE API fetch.")
    parser.add_argument("--capec-from-db", action="store_true",
                        help="Use CAPEC from DB (run capec_csv_ingest first). Skips CAPEC XML fetch.")
    parser.add_argument("--all-from-db", action="store_true",
                        help="Load all data from DB (CWE, CAPEC, NVD, ATT&CK, KEV). No web fetch. Use after initial ingest.")
    parser.add_argument("--vector-store", action="store_true",
                        help="Also ingest CWE + CAPEC into vector store for semantic search")
    parser.add_argument("--ingest-from-files", action="store_true",
                        help="Ingest from existing JSON files in --data-dir (no fetch)")
    parser.add_argument("--data-dir", default="threat_intel_data", help="Output/input directory")
    parser.add_argument("--cwe", nargs="*", help="CWE IDs to fetch (default: top 15)")
    args = parser.parse_args()

    if args.ingest_db:
        print("Loading settings...", flush=True)
        from app.core.settings import get_settings
        get_settings()
        results = run_fetch_and_ingest(
            cwe_ids=args.cwe or None,
            out_dir=Path(args.data_dir),
            skip_cwe_fetch=args.cwe_from_db,
            skip_capec_fetch=args.capec_from_db,
            all_from_db=args.all_from_db,
            ingest_vector_store=args.vector_store,
        )
        print("\n" + "=" * 60, flush=True)
        print("Ingested into DB:", flush=True)
        for k, v in results.items():
            print(f"  {k}: {v}", flush=True)
        print("\nRun mapper to build CWE→ATT&CK mappings:", flush=True)
        print(f"  python -m indexing_cli.cwe_capec_attack_mapper --data-dir {args.data_dir}", flush=True)
    elif args.ingest_from_files:
        from app.core.settings import get_settings
        get_settings()
        from app.ingestion.cwe_threat_intel.ingest import ingest_from_files
        results = ingest_from_files(Path(args.data_dir))
        print("\nIngested from files into DB:")
        for k, v in results.items():
            print(f"  {k}: {v}")
    else:
        main(cwe_ids=args.cwe)
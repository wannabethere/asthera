"""
Ingest CWE/CAPEC/ATT&CK/KEV data into DB.
Can load from JSON files (output of cwe_enrich.py) or fetch and ingest directly.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _ensure_tables(session) -> None:
    from app.ingestion.cwe_threat_intel.db_schema import create_cwe_threat_intel_tables

    create_cwe_threat_intel_tables(session)


def _parse_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def ingest_cwe_entries(session, data: Dict[str, Any]) -> int:
    """Ingest cwe_entries.json into cwe_entries table."""
    _ensure_tables(session)
    from sqlalchemy import text

    count = 0
    for cwe_id, raw in data.items():
        if not cwe_id or "error" in str(raw).lower():
            continue
        name = ""
        desc = ""
        if isinstance(raw, dict):
            name = raw.get("name") or raw.get("title") or ""
            d = raw.get("description")
            if isinstance(d, str):
                desc = d
            elif isinstance(d, list) and d:
                desc = d[0].get("value", "") if isinstance(d[0], dict) else str(d[0])
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
                "raw_data": json.dumps(raw) if isinstance(raw, dict) else raw,
                "name": name,
                "description": desc,
            },
        )
        count += 1
    return count


def ingest_capec(session, capec_by_id: Dict[str, Dict[str, Any]]) -> int:
    """Ingest capec_by_id.json into capec table."""
    _ensure_tables(session)
    from sqlalchemy import text

    count = 0
    for capec_id, raw in capec_by_id.items():
        if not capec_id:
            continue
        name = raw.get("name", "")
        desc = raw.get("description", "")
        related = raw.get("related_cwes", [])
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
                "related_cwes": json.dumps(related) if isinstance(related, list) else "[]",
                "raw_data": json.dumps(raw),
            },
        )
        count += 1
    return count


def ingest_cwe_to_capec(session, cwe_to_capec: Dict[str, List[str]]) -> int:
    """Ingest cwe_to_capec.json into cwe_to_capec table."""
    _ensure_tables(session)
    from sqlalchemy import text

    count = 0
    for cwe_id, capec_ids in cwe_to_capec.items():
        if not cwe_id:
            continue
        for capec_id in capec_ids or []:
            if not capec_id:
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
                count += 1
            except Exception:
                pass
    return count


def ingest_nvd_normalized_by_cwe(session, nvd_normalized: Dict[str, List[Dict[str, Any]]]) -> int:
    """Ingest nvd_normalized_by_cwe.json into nvd_cves_by_cwe table."""
    _ensure_tables(session)
    from sqlalchemy import text

    count = 0
    for cwe_id, vulns in nvd_normalized.items():
        if not cwe_id:
            continue
        for v in vulns or []:
            cve_id = v.get("cve_id") if isinstance(v, dict) else None
            if not cve_id:
                continue
            try:
                session.execute(
                    text("""
                        INSERT INTO nvd_cves_by_cwe (cwe_id, cve_id, normalized_data)
                        VALUES (:cwe_id, :cve_id, :normalized_data)
                        ON CONFLICT (cwe_id, cve_id) DO UPDATE SET
                            normalized_data = EXCLUDED.normalized_data
                    """),
                    {
                        "cwe_id": cwe_id,
                        "cve_id": cve_id,
                        "normalized_data": json.dumps(v),
                    },
                )
                count += 1
            except Exception:
                pass
    return count


def ingest_attack_techniques(session, techniques: List[Dict[str, Any]]) -> int:
    """Ingest attack_enterprise_techniques.json into attack_enterprise_techniques table."""
    _ensure_tables(session)
    from sqlalchemy import text

    count = 0
    for t in techniques or []:
        tid = t.get("attack_id")
        if not tid:
            continue
        name = t.get("name", "")
        desc = t.get("description", "")
        session.execute(
            text("""
                INSERT INTO attack_enterprise_techniques (technique_id, name, description, raw_data, updated_at)
                VALUES (:technique_id, :name, :description, :raw_data, NOW())
                ON CONFLICT (technique_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    raw_data = EXCLUDED.raw_data,
                    updated_at = NOW()
            """),
            {
                "technique_id": tid,
                "name": name,
                "description": desc,
                "raw_data": json.dumps(t),
            },
        )
        count += 1
    return count


def ingest_cisa_kev(session, kev_catalog: Dict[str, Any]) -> int:
    """Ingest cisa_kev.json into cisa_kev table."""
    _ensure_tables(session)
    from sqlalchemy import text

    vulns = kev_catalog.get("vulnerabilities", [])
    catalog_date = kev_catalog.get("dateReleased") or kev_catalog.get("catalogVersion")
    count = 0
    for v in vulns:
        cve_id = v.get("cveID")
        if not cve_id:
            continue
        try:
            session.execute(
                text("""
                    INSERT INTO cisa_kev (cve_id, catalog_date, raw_data, updated_at)
                    VALUES (:cve_id, :catalog_date, :raw_data, NOW())
                    ON CONFLICT (cve_id) DO UPDATE SET
                        catalog_date = EXCLUDED.catalog_date,
                        raw_data = EXCLUDED.raw_data,
                        updated_at = NOW()
                """),
                {
                    "cve_id": cve_id,
                    "catalog_date": catalog_date,
                    "raw_data": json.dumps(v),
                },
            )
            count += 1
        except Exception:
            pass
    return count


def ingest_from_files(data_dir: Path) -> Dict[str, int]:
    """
    Ingest all CWE threat intel from JSON files in data_dir.
    Expects: cwe_entries.json, capec_by_id.json, cwe_to_capec.json,
             nvd_normalized_by_cwe.json, attack_enterprise_techniques.json, cisa_kev.json
    """
    from app.storage.sqlalchemy_session import get_security_intel_session

    results: Dict[str, int] = {}
    for name, path in [
        ("cwe_entries", data_dir / "cwe_entries.json"),
        ("capec_by_id", data_dir / "capec_by_id.json"),
        ("cwe_to_capec", data_dir / "cwe_to_capec.json"),
        ("nvd_normalized_by_cwe", data_dir / "nvd_normalized_by_cwe.json"),
        ("attack_enterprise_techniques", data_dir / "attack_enterprise_techniques.json"),
        ("cisa_kev", data_dir / "cisa_kev.json"),
    ]:
        if not path.exists():
            logger.warning(f"File not found: {path}")
            results[name] = 0
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        with get_security_intel_session("cve_attack") as session:
            if name == "cwe_entries":
                results[name] = ingest_cwe_entries(session, data)
            elif name == "capec_by_id":
                results[name] = ingest_capec(session, data)
            elif name == "cwe_to_capec":
                results[name] = ingest_cwe_to_capec(session, data)
            elif name == "nvd_normalized_by_cwe":
                results[name] = ingest_nvd_normalized_by_cwe(session, data)
            elif name == "attack_enterprise_techniques":
                results[name] = ingest_attack_techniques(session, data)
            elif name == "cisa_kev":
                results[name] = ingest_cisa_kev(session, data)
        logger.info(f"Ingested {results[name]} rows into {name}")
    return results


def ingest_from_fetched_data(
    cwe_entries: Dict[str, Any],
    capec_by_id: Dict[str, Dict[str, Any]],
    cwe_to_capec: Dict[str, List[str]],
    nvd_normalized: Dict[str, List[Dict[str, Any]]],
    attack_techniques: List[Dict[str, Any]],
    kev_catalog: Dict[str, Any],
) -> Dict[str, int]:
    """Ingest from in-memory data (fetched by cwe_enrich)."""
    from app.storage.sqlalchemy_session import get_security_intel_session

    with get_security_intel_session("cve_attack") as session:
        results = {
            "cwe_entries": ingest_cwe_entries(session, cwe_entries),
            "capec": ingest_capec(session, capec_by_id),
            "cwe_to_capec": ingest_cwe_to_capec(session, cwe_to_capec),
            "nvd_cves_by_cwe": ingest_nvd_normalized_by_cwe(session, nvd_normalized),
            "attack_techniques": ingest_attack_techniques(session, attack_techniques),
            "cisa_kev": ingest_cisa_kev(session, kev_catalog),
        }
    return results

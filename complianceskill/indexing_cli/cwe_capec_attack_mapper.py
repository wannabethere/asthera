"""
CWE → CAPEC → ATT&CK mapper.
Produces a derived table cwe_capec_attack_mappings with columns:
  cwe_id, capec_id, attack_id, tactic, mapping_basis, confidence, example_cves

mapping_basis: capec-derived | cve-observed | curated

MITRE/NVD do not expose a native CWE→ATT&CK mapping. This mapper builds
a derived table from:
- CAPEC CWE links (capec-derived)
- NVD CVEs by CWE + observed exploit patterns (cve-observed)
- Curated fallback (curated)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Curated CWE → (attack_id, tactic) for top CWEs when no CAPEC/CVE-derived mapping exists
CURATED_CWE_ATTACK: List[Tuple[str, str, str, str]] = [
    ("CWE-476", "T1059", "execution", "high"),
    ("CWE-416", "T1059", "execution", "high"),
    ("CWE-125", "T1059", "execution", "medium"),
    ("CWE-787", "T1059", "execution", "high"),
    ("CWE-362", "T1059", "execution", "medium"),
    ("CWE-20", "T1190", "initial-access", "medium"),
    ("CWE-22", "T1083", "discovery", "high"),
    ("CWE-78", "T1059", "execution", "high"),
    ("CWE-78", "T1190", "initial-access", "high"),
    ("CWE-79", "T1059.001", "execution", "high"),
    ("CWE-79", "T1190", "initial-access", "high"),
    ("CWE-89", "T1190", "initial-access", "high"),
    ("CWE-89", "T1059", "execution", "medium"),
    ("CWE-94", "T1059", "execution", "high"),
    ("CWE-94", "T1190", "initial-access", "high"),
    ("CWE-119", "T1059", "execution", "high"),
    ("CWE-190", "T1059", "execution", "medium"),
    ("CWE-287", "T1078", "persistence", "high"),
    ("CWE-287", "T1133", "initial-access", "medium"),
    ("CWE-306", "T1078", "persistence", "high"),
    ("CWE-306", "T1133", "initial-access", "medium"),
    ("CWE-77", "T1059", "execution", "high"),
    ("CWE-77", "T1190", "initial-access", "high"),
    ("CWE-77", "T1068", "privilege-escalation", "high"),
    ("CWE-352", "T1539", "credential-access", "high"),
    ("CWE-352", "T1190", "initial-access", "medium"),
    ("CWE-502", "T1059", "execution", "high"),
    ("CWE-502", "T1190", "initial-access", "high"),
    ("CWE-918", "T1190", "initial-access", "high"),
    ("CWE-918", "T1059", "execution", "medium"),
]

# CAPEC ID → (attack_id, tactic) — derived from CAPEC attack pattern names / MITRE mappings
# This is a simplified mapping; in practice you'd use CAPEC→ATT&CK crosswalk if available
CAPEC_TO_ATTACK: Dict[str, List[Tuple[str, str]]] = {
    "CAPEC-6": [("T1190", "initial-access"), ("T1059", "execution")],
    "CAPEC-7": [("T1190", "initial-access"), ("T1059", "execution")],
    "CAPEC-31": [("T1059", "execution")],
    "CAPEC-66": [("T1059", "execution"), ("T1190", "initial-access")],
    "CAPEC-67": [("T1059", "execution")],
    "CAPEC-88": [("T1059", "execution")],
    "CAPEC-89": [("T1059", "execution")],
    "CAPEC-136": [("T1059", "execution")],
    "CAPEC-184": [("T1059", "execution")],
    "CAPEC-233": [("T1059", "execution")],
}


def build_mappings(
    cwe_to_capec: Dict[str, List[str]],
    capec_by_id: Dict[str, Dict[str, Any]],
    nvd_normalized_by_cwe: Dict[str, List[Dict[str, Any]]],
    attack_techniques: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Build cwe_capec_attack_mappings from CWE→CAPEC and curated data.
    Returns list of dicts: cwe_id, capec_id, attack_id, tactic, mapping_basis, confidence, example_cves
    """
    attack_ids = {t.get("attack_id") for t in attack_techniques if t.get("attack_id")}
    mappings: List[Dict[str, Any]] = []
    seen: set = set()

    # 1) CAPEC-derived: CWE → CAPEC → ATT&CK
    for cwe_id, capec_ids in cwe_to_capec.items():
        for capec_id in capec_ids or []:
            for attack_id, tactic in CAPEC_TO_ATTACK.get(capec_id, []):
                if attack_id not in attack_ids:
                    continue
                key = (cwe_id, attack_id, tactic)
                if key in seen:
                    continue
                seen.add(key)
                example_cves = _sample_cves_for_cwe(nvd_normalized_by_cwe, cwe_id, 5)
                mappings.append({
                    "cwe_id": cwe_id,
                    "capec_id": capec_id,
                    "attack_id": attack_id,
                    "tactic": tactic,
                    "mapping_basis": "capec-derived",
                    "confidence": "medium",
                    "example_cves": example_cves,
                })

    # 2) Curated fallback for CWEs without CAPEC-derived mappings
    for cwe_id, attack_id, tactic, confidence in CURATED_CWE_ATTACK:
        key = (cwe_id, attack_id, tactic)
        if key in seen:
            continue
        if attack_id not in attack_ids:
            continue
        seen.add(key)
        example_cves = _sample_cves_for_cwe(nvd_normalized_by_cwe, cwe_id, 5)
        mappings.append({
            "cwe_id": cwe_id,
            "capec_id": None,
            "attack_id": attack_id,
            "tactic": tactic,
            "mapping_basis": "curated",
            "confidence": confidence,
            "example_cves": example_cves,
        })

    return mappings


def _sample_cves_for_cwe(
    nvd_normalized: Dict[str, List[Dict[str, Any]]],
    cwe_id: str,
    limit: int = 5,
) -> List[str]:
    vulns = nvd_normalized.get(cwe_id, [])
    cve_ids = [v.get("cve_id") for v in vulns if isinstance(v, dict) and v.get("cve_id")]
    return list(dict.fromkeys(cve_ids))[:limit]


def persist_mappings_to_db(mappings: List[Dict[str, Any]]) -> int:
    """Upsert mappings into cwe_capec_attack_mappings and cwe_technique_mappings."""
    from app.storage.sqlalchemy_session import get_security_intel_session
    from sqlalchemy import text

    from app.ingestion.cwe_threat_intel.db_schema import create_cwe_threat_intel_tables

    total = len(mappings)
    logger.info(f"Persisting {total} mappings to DB...")
    count = 0
    with get_security_intel_session("cve_attack") as session:
        create_cwe_threat_intel_tables(session)
        for i, m in enumerate(mappings):
            session.execute(
                text("""
                    INSERT INTO cwe_capec_attack_mappings
                    (cwe_id, capec_id, attack_id, tactic, mapping_basis, confidence, example_cves)
                    VALUES (:cwe_id, :capec_id, :attack_id, :tactic, :mapping_basis, :confidence, :example_cves)
                    ON CONFLICT (cwe_id, attack_id, tactic) DO UPDATE SET
                        capec_id = EXCLUDED.capec_id,
                        mapping_basis = EXCLUDED.mapping_basis,
                        confidence = EXCLUDED.confidence,
                        example_cves = EXCLUDED.example_cves
                """),
                {
                    "cwe_id": m["cwe_id"],
                    "capec_id": m.get("capec_id"),
                    "attack_id": m["attack_id"],
                    "tactic": m["tactic"],
                    "mapping_basis": m["mapping_basis"],
                    "confidence": m.get("confidence", "medium"),
                    "example_cves": json.dumps(m.get("example_cves") or []),
                },
            )
            # Also populate cwe_technique_mappings for cve_attack_mapper
            session.execute(
                text("""
                    INSERT INTO cwe_technique_mappings (cwe_id, technique_id, tactic, confidence, mapping_source)
                    VALUES (:cwe_id, :technique_id, :tactic, :confidence, :mapping_source)
                    ON CONFLICT (cwe_id, technique_id, tactic) DO UPDATE SET
                        confidence = EXCLUDED.confidence,
                        mapping_source = EXCLUDED.mapping_source
                """),
                {
                    "cwe_id": m["cwe_id"],
                    "technique_id": m["attack_id"],
                    "tactic": m["tactic"],
                    "confidence": m.get("confidence", "medium"),
                    "mapping_source": m.get("mapping_basis", "cwe_lookup"),
                },
            )
            count += 1
            if (i + 1) % 50 == 0 or (i + 1) == total:
                logger.info(f"  Persisted {i + 1}/{total} mappings")
    return count


def run_mapper_from_files(data_dir: Path) -> List[Dict[str, Any]]:
    """Load from JSON files and build mappings."""
    logger.info(f"Loading from {data_dir}...")
    cwe_to_capec = json.loads((data_dir / "cwe_to_capec.json").read_text())
    logger.info(f"  cwe_to_capec: {len(cwe_to_capec)} CWEs")
    capec_by_id = json.loads((data_dir / "capec_by_id.json").read_text())
    logger.info(f"  capec_by_id: {len(capec_by_id)} CAPEC entries")
    nvd_normalized = json.loads((data_dir / "nvd_normalized_by_cwe.json").read_text())
    total_cves = sum(len(v) for v in nvd_normalized.values())
    logger.info(f"  nvd_normalized_by_cwe: {len(nvd_normalized)} CWEs, {total_cves} CVEs")
    attack_techniques = json.loads((data_dir / "attack_enterprise_techniques.json").read_text())
    logger.info(f"  attack_enterprise_techniques: {len(attack_techniques)} techniques")
    logger.info("Building CWE→CAPEC→ATT&CK mappings...")
    mappings = build_mappings(cwe_to_capec, capec_by_id, nvd_normalized, attack_techniques)
    logger.info(f"Built {len(mappings)} mappings")
    return mappings


def main(data_dir: Optional[str] = None) -> None:
    data_dir = Path(data_dir or "threat_intel_data")
    if not data_dir.exists():
        logger.error(f"Data dir not found: {data_dir}. Run cwe_enrich first.")
        return
    logger.info("CWE→CAPEC→ATT&CK mapper starting...")
    mappings = run_mapper_from_files(data_dir)
    count = persist_mappings_to_db(mappings)
    out = data_dir / "cwe_capec_attack_mappings.json"
    out.write_text(json.dumps(mappings, indent=2))
    logger.info(f"Done. Persisted {count} mappings to DB, wrote {out}")


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="threat_intel_data", help="Path to cwe_enrich output dir")
    args = parser.parse_args()
    main(args.data_dir)

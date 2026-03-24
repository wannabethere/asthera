"""
Embed CWE→CAPEC→ATT&CK mapping rows into a dedicated vector collection for semantic search.

Source of truth: Postgres ``cwe_capec_attack_mappings`` (optionally enriched with
``cwe_entries`` and ``attack_enterprise_techniques`` names/descriptions).

Collection: ``ThreatIntelCollections.CWE_CAPEC_ATTACK_MAPPINGS`` or
``settings.THREAT_INTEL_CWE_CAPEC_ATTACK_COLLECTION``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import text

logger = logging.getLogger(__name__)

ENTITY_TYPE = "cwe_capec_attack"
BATCH_SIZE = 50


def cwe_capec_attack_collection_name() -> str:
    from app.core.settings import get_settings
    from app.storage.collections import ThreatIntelCollections

    s = get_settings()
    name = getattr(s, "THREAT_INTEL_CWE_CAPEC_ATTACK_COLLECTION", None)
    if name and str(name).strip():
        return str(name).strip()
    return ThreatIntelCollections.CWE_CAPEC_ATTACK_MAPPINGS


def _stable_id(cwe_id: str, attack_id: str, tactic: str) -> str:
    return f"cwe_capec_attack:{cwe_id}:{attack_id}:{tactic}"


def _parse_example_cves(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw if x]
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [str(x) for x in data if x]
        except Exception:
            pass
    return []


def build_mapping_document(
    cwe_id: str,
    capec_id: Optional[str],
    attack_id: str,
    tactic: str,
    mapping_basis: str,
    confidence: Optional[str],
    example_cves: List[str],
    cwe_name: str = "",
    cwe_description: str = "",
    technique_name: str = "",
    technique_description: str = "",
) -> Tuple[str, Dict[str, Any], str]:
    """Return (document_text, metadata_chroma, point_id)."""
    cn = (cwe_name or "").strip()
    cd = (cwe_description or "").strip()
    tn = (technique_name or "").strip()
    td = (technique_description or "").strip()
    cap = (capec_id or "").strip()
    conf = (confidence or "medium").strip()
    cves = example_cves[:15]
    cve_line = ", ".join(cves) if cves else ""

    lines: List[str] = [
        f"CWE {cwe_id}" + (f": {cn}" if cn else ""),
        f"MITRE ATT&CK technique {attack_id}" + (f": {tn}" if tn else ""),
        f"Kill-chain tactic: {tactic}",
    ]
    if cap:
        lines.append(f"Related CAPEC: {cap}")
    lines.append(f"Mapping basis: {mapping_basis}. Confidence: {conf}.")
    if cve_line:
        lines.append(f"Example CVEs associated with this weakness: {cve_line}")
    if cd:
        lines.append(f"CWE description: {cd[:2500]}")
    if td:
        lines.append(f"Technique description: {td[:2500]}")

    doc_text = "\n\n".join(lines)

    meta: Dict[str, Any] = {
        "entity_type": ENTITY_TYPE,
        "cwe_id": cwe_id,
        "capec_id": cap,
        "attack_id": attack_id,
        "tactic": tactic,
        "mapping_basis": mapping_basis or "",
        "confidence": conf,
    }
    if cn:
        meta["cwe_name"] = cn[:500]
    if tn:
        meta["technique_name"] = tn[:500]

    return doc_text, meta, _stable_id(cwe_id, attack_id, tactic)


def row_to_parts(
    row: Sequence[Any],
    *,
    joined: bool,
) -> Tuple[str, Dict[str, Any], str]:
    """Map a DB row tuple to (text, metadata, id)."""
    if joined and len(row) >= 11:
        (
            cwe_id,
            capec_id,
            attack_id,
            tactic,
            mapping_basis,
            confidence,
            example_cves_raw,
            cwe_name,
            cwe_desc,
            tech_name,
            tech_desc,
        ) = row[:11]
    else:
        cwe_id, capec_id, attack_id, tactic, mapping_basis, confidence, example_cves_raw = row[:7]
        cwe_name, cwe_desc, tech_name, tech_desc = "", "", "", ""

    ex = _parse_example_cves(example_cves_raw)
    return build_mapping_document(
        str(cwe_id),
        str(capec_id) if capec_id else None,
        str(attack_id),
        str(tactic),
        str(mapping_basis or ""),
        str(confidence) if confidence else None,
        ex,
        cwe_name=str(cwe_name or ""),
        cwe_description=str(cwe_desc or ""),
        technique_name=str(tech_name or ""),
        technique_description=str(tech_desc or ""),
    )


def load_mapping_rows_from_db() -> Tuple[List[Sequence[Any]], bool]:
    """
    Load rows from security_intel. Returns (rows, joined) where joined indicates
    whether columns include cwe/technique enrichment.
    """
    from app.storage.sqlalchemy_session import get_security_intel_session

    joined_sql = text(
        """
        SELECT m.cwe_id, m.capec_id, m.attack_id, m.tactic, m.mapping_basis, m.confidence,
               m.example_cves,
               ce.name, ce.description,
               t.name, t.description
        FROM cwe_capec_attack_mappings m
        LEFT JOIN cwe_entries ce ON ce.cwe_id = m.cwe_id
        LEFT JOIN attack_enterprise_techniques t ON t.technique_id = m.attack_id
        ORDER BY m.cwe_id, m.attack_id, m.tactic
        """
    )
    simple_sql = text(
        """
        SELECT cwe_id, capec_id, attack_id, tactic, mapping_basis, confidence, example_cves
        FROM cwe_capec_attack_mappings
        ORDER BY cwe_id, attack_id, tactic
        """
    )
    with get_security_intel_session("cve_attack") as session:
        try:
            rows = session.execute(joined_sql).fetchall()
            return (list(rows), True)
        except Exception as e:
            logger.warning("Joined cwe_capec_attack_mappings load failed, falling back: %s", e)
            rows = session.execute(simple_sql).fetchall()
            return (list(rows), False)


def load_mappings_from_json_list(data: List[Dict[str, Any]]) -> List[Tuple[str, Dict[str, Any], str]]:
    """Build (text, meta, id) triples from mapper JSON list."""
    out: List[Tuple[str, Dict[str, Any], str]] = []
    for m in data:
        if not isinstance(m, dict):
            continue
        cwe_id = m.get("cwe_id")
        attack_id = m.get("attack_id")
        tactic = m.get("tactic")
        if not cwe_id or not attack_id or not tactic:
            continue
        ex = m.get("example_cves") or []
        if not isinstance(ex, list):
            ex = []
        doc, meta, pid = build_mapping_document(
            str(cwe_id),
            m.get("capec_id"),
            str(attack_id),
            str(tactic),
            str(m.get("mapping_basis") or ""),
            str(m.get("confidence") or "medium"),
            [str(x) for x in ex],
        )
        out.append((doc, meta, pid))
    return out


async def _ingest_batch(
    client,
    collection_name: str,
    documents: List[str],
    metadatas: List[Dict[str, Any]],
    ids: List[str],
) -> int:
    if not documents:
        return 0
    await client.add_documents(
        collection_name=collection_name,
        documents=documents,
        metadatas=metadatas,
        ids=ids,
    )
    return len(documents)


async def ingest_mapping_triples_async(
    triples: List[Tuple[str, Dict[str, Any], str]],
    *,
    collection_name: Optional[str] = None,
    batch_size: int = BATCH_SIZE,
) -> int:
    from app.storage.vector_store import get_vector_store_client

    coll = collection_name or cwe_capec_attack_collection_name()
    client = get_vector_store_client()
    await client.initialize()

    docs: List[str] = []
    metas: List[Dict[str, Any]] = []
    ids: List[str] = []
    total = 0
    bs = max(1, int(batch_size))

    for doc_text, meta, pid in triples:
        docs.append(doc_text)
        metas.append(meta)
        ids.append(pid)
        if len(docs) >= bs:
            total += await _ingest_batch(client, coll, docs, metas, ids)
            docs, metas, ids = [], [], []

    if docs:
        total += await _ingest_batch(client, coll, docs, metas, ids)

    logger.info("Ingested %s CWE→CAPEC→ATT&CK mapping vectors into %r", total, coll)
    return total


def ingest_cwe_capec_attack_mappings_from_db(
    *,
    collection_name: Optional[str] = None,
    batch_size: int = BATCH_SIZE,
) -> int:
    """Load mappings from Postgres and upsert into the vector collection."""
    rows, joined = load_mapping_rows_from_db()
    if not rows:
        logger.warning("No rows in cwe_capec_attack_mappings; nothing to ingest")
        return 0
    triples: List[Tuple[str, Dict[str, Any], str]] = []
    for row in rows:
        triples.append(row_to_parts(row, joined=joined))
    return asyncio.run(
        ingest_mapping_triples_async(triples, collection_name=collection_name, batch_size=batch_size)
    )


def ingest_cwe_capec_attack_mappings_from_json(
    path: str,
    *,
    collection_name: Optional[str] = None,
    batch_size: int = BATCH_SIZE,
) -> int:
    """Load ``cwe_capec_attack_mappings.json`` (array of objects) and ingest."""
    from pathlib import Path

    p = Path(path).expanduser().resolve()
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Expected a JSON array of mapping objects")
    triples = load_mappings_from_json_list(data)
    if not triples:
        logger.warning("No valid mappings in %s", p)
        return 0
    return asyncio.run(
        ingest_mapping_triples_async(triples, collection_name=collection_name, batch_size=batch_size)
    )

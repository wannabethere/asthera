"""
Ingest CWE and CAPEC data into the configured vector store for semantic search.
Used by cwe_csv_ingest, capec_csv_ingest, and cwe_enrich when --vector-store is passed.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

COLLECTION = "threat_intel_cwe_capec"
BATCH_SIZE = 50


def _doc_text_cwe(cwe_id: str, name: str, description: str, related: str = "") -> str:
    """Build searchable text for a CWE entry."""
    parts = [f"{cwe_id}: {name}"]
    if description:
        parts.append(description[:3000])
    if related:
        parts.append(f"Related: {related[:500]}")
    return "\n\n".join(parts)


def _doc_text_capec(capec_id: str, name: str, description: str, related: str = "") -> str:
    """Build searchable text for a CAPEC entry."""
    parts = [f"{capec_id}: {name}"]
    if description:
        parts.append(description[:3000])
    if related:
        parts.append(f"Related CWEs: {related[:500]}")
    return "\n\n".join(parts)


def _metadata_cwe(cwe_id: str, name: str) -> Dict[str, Any]:
    """Metadata for CWE (ChromaDB/Qdrant compatible: str, int, float, bool)."""
    return {
        "entity_type": "cwe",
        "id": cwe_id,
        "name": (name or "")[:500],
    }


def _metadata_capec(capec_id: str, name: str) -> Dict[str, Any]:
    """Metadata for CAPEC."""
    return {
        "entity_type": "capec",
        "id": capec_id,
        "name": (name or "")[:500],
    }


async def _ingest_batch(
    client,
    collection_name: str,
    documents: List[str],
    metadatas: List[Dict[str, Any]],
    ids: List[str],
) -> int:
    """Add a batch of documents to the vector store."""
    if not documents:
        return 0
    await client.add_documents(
        collection_name=collection_name,
        documents=documents,
        metadatas=metadatas,
        ids=ids,
    )
    return len(documents)


async def _ingest_cwe_async(entries: Dict[str, Dict[str, Any]]) -> int:
    """Ingest CWE entries into the vector store. Returns count."""
    from app.storage.vector_store import get_vector_store_client
    from app.storage.collections import ThreatIntelCollections

    coll = ThreatIntelCollections.CWE_CAPEC
    client = get_vector_store_client()
    await client.initialize()

    docs: List[str] = []
    metas: List[Dict[str, Any]] = []
    ids_list: List[str] = []
    count = 0

    for cwe_id, row in entries.items():
        name = (row.get("name") or "").strip()
        desc = (row.get("description") or row.get("extended_description") or "").strip()
        related = (row.get("related_attack_patterns") or row.get("related_weaknesses") or "").strip()
        text = _doc_text_cwe(cwe_id, name, desc, related)
        docs.append(text)
        metas.append(_metadata_cwe(cwe_id, name))
        ids_list.append(f"cwe:{cwe_id}")

        if len(docs) >= BATCH_SIZE:
            count += await _ingest_batch(client, coll, docs, metas, ids_list)
            docs, metas, ids_list = [], [], []

    if docs:
        count += await _ingest_batch(client, coll, docs, metas, ids_list)

    return count


async def _ingest_capec_async(entries: Dict[str, Dict[str, Any]]) -> int:
    """Ingest CAPEC entries into the vector store. Returns count."""
    from app.storage.vector_store import get_vector_store_client
    from app.storage.collections import ThreatIntelCollections

    coll = ThreatIntelCollections.CWE_CAPEC
    client = get_vector_store_client()
    await client.initialize()

    docs: List[str] = []
    metas: List[Dict[str, Any]] = []
    ids_list: List[str] = []
    count = 0

    for capec_id, row in entries.items():
        name = (row.get("name") or "").strip()
        desc = (row.get("description") or "").strip()
        related_cwes = row.get("related_cwes", [])
        related = ", ".join(related_cwes) if isinstance(related_cwes, list) else str(related_cwes)
        text = _doc_text_capec(capec_id, name, desc, related)
        docs.append(text)
        metas.append(_metadata_capec(capec_id, name))
        ids_list.append(f"capec:{capec_id}")

        if len(docs) >= BATCH_SIZE:
            count += await _ingest_batch(client, coll, docs, metas, ids_list)
            docs, metas, ids_list = [], [], []

    if docs:
        count += await _ingest_batch(client, coll, docs, metas, ids_list)

    return count


def ingest_cwe_to_vector_store(entries: Dict[str, Dict[str, Any]]) -> int:
    """Synchronous wrapper: ingest CWE entries into vector store."""
    return asyncio.run(_ingest_cwe_async(entries))


def ingest_capec_to_vector_store(entries: Dict[str, Dict[str, Any]]) -> int:
    """Synchronous wrapper: ingest CAPEC entries into vector store."""
    return asyncio.run(_ingest_capec_async(entries))


def ingest_cwe_and_capec_to_vector_store(
    cwe_entries: Dict[str, Dict[str, Any]],
    capec_entries: Dict[str, Dict[str, Any]],
) -> Dict[str, int]:
    """Ingest both CWE and CAPEC. Returns {'cwe': n, 'capec': m}."""
    cwe_count = ingest_cwe_to_vector_store(cwe_entries)
    capec_count = ingest_capec_to_vector_store(capec_entries)
    return {"cwe": cwe_count, "capec": capec_count}


def load_cwe_from_db() -> Dict[str, Dict[str, Any]]:
    """Load CWE entries from DB for vector store ingestion."""
    entries: Dict[str, Dict[str, Any]] = {}
    try:
        from app.storage.sqlalchemy_session import get_security_intel_session
        from sqlalchemy import text
        with get_security_intel_session("cve_attack") as session:
            for row in session.execute(text(
                "SELECT cwe_id, name, description, raw_data FROM cwe_entries"
            )).fetchall():
                cwe_id, name, desc, raw_json = row[0], row[1], row[2], row[3]
                if not cwe_id:
                    continue
                raw = {}
                if raw_json:
                    try:
                        raw = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
                    except Exception:
                        pass
                entries[cwe_id] = {
                    "name": name or raw.get("name", ""),
                    "description": desc or raw.get("description", ""),
                    "extended_description": raw.get("extended_description", ""),
                    "related_weaknesses": raw.get("related_weaknesses", ""),
                    "related_attack_patterns": raw.get("related_attack_patterns", ""),
                }
    except Exception as e:
        logger.warning(f"Could not load CWE from DB: {e}")
    return entries


def load_capec_from_db() -> Dict[str, Dict[str, Any]]:
    """Load CAPEC entries from DB for vector store ingestion."""
    entries: Dict[str, Dict[str, Any]] = {}
    try:
        from app.storage.sqlalchemy_session import get_security_intel_session
        from sqlalchemy import text
        with get_security_intel_session("cve_attack") as session:
            for row in session.execute(text(
                "SELECT capec_id, name, description, related_cwes FROM capec"
            )).fetchall():
                capec_id, name, desc, related_json = row[0], row[1], row[2], row[3]
                if not capec_id:
                    continue
                related = []
                if related_json:
                    try:
                        related = json.loads(related_json) if isinstance(related_json, str) else related_json
                    except Exception:
                        pass
                entries[capec_id] = {
                    "name": name or "",
                    "description": desc or "",
                    "related_cwes": related,
                }
    except Exception as e:
        logger.warning(f"Could not load CAPEC from DB: {e}")
    return entries


def ingest_from_db_to_vector_store() -> Dict[str, int]:
    """Load CWE and CAPEC from DB and ingest into vector store."""
    cwe_entries = load_cwe_from_db()
    capec_entries = load_capec_from_db()
    return ingest_cwe_and_capec_to_vector_store(cwe_entries, capec_entries)

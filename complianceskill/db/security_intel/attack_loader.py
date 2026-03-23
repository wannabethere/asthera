"""
db/security_intel/attack_loader.py

Fetches the MITRE ATT&CK Enterprise STIX bundle and ingests tactics + techniques
into Postgres, and optionally into the vector store (Qdrant or Chroma) using the
same collection name as ``AttackCollections.TECHNIQUES`` (``attack_techniques``)
and the same document shape as ``ingest_attack_techniques`` in
``app/ingestion/attacktocve/vectorstore_retrieval.py`` so enrichment pipelines
and tools stay aligned.

Usage (from complianceskill/ with PYTHONPATH=. or run this file — repo root is added automatically):

    python db/security_intel/attack_loader.py
    python db/security_intel/attack_loader.py --version 18.1
    python db/security_intel/attack_loader.py --file ./enterprise-attack.json
    python db/security_intel/attack_loader.py --no-vector-store
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from sqlalchemy import text

logger = logging.getLogger(__name__)

_REPO_ROOT_PREPENDED = False


def _ensure_repo_root_on_path() -> None:
    """Allow imports of ``app.*`` when this file is run as a script from db/security_intel/."""
    global _REPO_ROOT_PREPENDED
    if _REPO_ROOT_PREPENDED:
        return
    import sys

    root = Path(__file__).resolve().parent.parent.parent
    rs = str(root)
    if rs not in sys.path:
        sys.path.insert(0, rs)
    _REPO_ROOT_PREPENDED = True

# Always points to the latest release
BUNDLE_URL = (
    "https://raw.githubusercontent.com/mitre-attack/attack-stix-data"
    "/master/enterprise-attack/enterprise-attack.json"
)

# Versioned URL pattern — swap {version} for e.g. "18.1"
BUNDLE_URL_VERSIONED = (
    "https://raw.githubusercontent.com/mitre-attack/attack-stix-data"
    "/master/enterprise-attack/enterprise-attack-{version}.json"
)


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def fetch_bundle(version: str | None = None, local_file: str | None = None) -> dict:
    """Download or load the STIX bundle. Returns the parsed JSON dict."""
    if local_file:
        path = Path(local_file)
        logger.info(f"Loading STIX bundle from {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    url = BUNDLE_URL_VERSIONED.format(version=version) if version else BUNDLE_URL
    logger.info(f"Fetching ATT&CK STIX bundle: {url}")
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    logger.info(f"Bundle downloaded ({len(r.content) / 1_000_000:.1f} MB)")
    return r.json()


# ---------------------------------------------------------------------------
# Parse helpers
# ---------------------------------------------------------------------------

def _external_id(obj: dict) -> str | None:
    """Extract the ATT&CK ID (TA0001, T1078, T1078.001) from external_references."""
    for ref in obj.get("external_references", []):
        if ref.get("source_name") == "mitre-attack":
            return ref.get("external_id")
    return None


def _external_url(obj: dict) -> str | None:
    for ref in obj.get("external_references", []):
        if ref.get("source_name") == "mitre-attack":
            return ref.get("url")
    return None


def _attack_version(obj: dict) -> str | None:
    return obj.get("x_mitre_version") or obj.get("spec_version")


def _is_revoked_or_deprecated(obj: dict) -> tuple[bool, bool]:
    return bool(obj.get("revoked")), bool(obj.get("x_mitre_deprecated"))


# ---------------------------------------------------------------------------
# Parse tactics
# ---------------------------------------------------------------------------

def parse_tactics(objects: list[dict]) -> list[dict]:
    """
    Extract x-mitre-tactic objects.
    Returns list of dicts ready for attack_tactics table.
    """
    tactics = []
    for obj in objects:
        if obj.get("type") != "x-mitre-tactic":
            continue
        tactic_id = _external_id(obj)
        if not tactic_id:
            continue
        tactics.append({
            "tactic_id":      tactic_id,                        # TA0001
            "name":           obj["name"],                      # Initial Access
            "shortname":      obj["x_mitre_shortname"],         # initial-access
            "description":    obj.get("description", ""),
            "attack_version": _attack_version(obj),
            "url":            _external_url(obj),
        })
    logger.info(f"Parsed {len(tactics)} tactics")
    return tactics


# ---------------------------------------------------------------------------
# Parse techniques
# ---------------------------------------------------------------------------

def parse_techniques(
    objects: list[dict],
    tactic_shortname_to_id: dict[str, str],
    include_revoked: bool = False,
    include_deprecated: bool = False,
) -> list[dict]:
    """
    Extract attack-pattern objects (techniques + sub-techniques).

    tactic_shortname_to_id: {"initial-access": "TA0001", ...}
        Built from parse_tactics output so tactic_ids can be populated.

    Returns list of dicts ready for attack_techniques table.
    """
    techniques = []

    for obj in objects:
        if obj.get("type") != "attack-pattern":
            continue

        revoked, deprecated = _is_revoked_or_deprecated(obj)
        if revoked and not include_revoked:
            continue
        if deprecated and not include_deprecated:
            continue

        technique_id = _external_id(obj)
        if not technique_id or not technique_id.startswith("T"):
            continue

        is_sub = bool(obj.get("x_mitre_is_subtechnique", False))

        # Parent technique ID: T1078.001 → T1078
        parent_id = None
        if is_sub and "." in technique_id:
            parent_id = technique_id.rsplit(".", 1)[0]

        # Tactic association via kill_chain_phases
        # kill_chain_name == "mitre-attack", phase_name == tactic shortname
        tactic_shortnames = [
            kcp["phase_name"]
            for kcp in obj.get("kill_chain_phases", [])
            if kcp.get("kill_chain_name") == "mitre-attack"
        ]
        tactic_ids = [
            tactic_shortname_to_id[s]
            for s in tactic_shortnames
            if s in tactic_shortname_to_id
        ]

        techniques.append({
            "technique_id":         technique_id,
            "parent_technique_id":  parent_id,
            "name":                 obj["name"],
            "description":          obj.get("description", ""),
            "is_subtechnique":      is_sub,
            "tactic_shortnames":    tactic_shortnames,
            "tactic_ids":           tactic_ids,
            "platforms":            obj.get("x_mitre_platforms", []),
            "data_sources":         obj.get("x_mitre_data_sources", []),
            "detection":            obj.get("x_mitre_detection", ""),
            "url":                  _external_url(obj),
            "attack_version":       _attack_version(obj),
            "revoked":              revoked,
            "deprecated":           deprecated,
        })

    logger.info(
        f"Parsed {len(techniques)} techniques "
        f"({sum(1 for t in techniques if t['is_subtechnique'])} sub-techniques)"
    )
    return techniques


# ---------------------------------------------------------------------------
# Persist
# ---------------------------------------------------------------------------

def persist_tactics(session, tactics: list[dict]) -> int:
    count = 0
    for t in tactics:
        session.execute(text("""
            INSERT INTO attack_tactics
                (tactic_id, name, shortname, description, attack_version, url)
            VALUES
                (:tactic_id, :name, :shortname, :description, :attack_version, :url)
            ON CONFLICT (tactic_id) DO UPDATE SET
                name           = EXCLUDED.name,
                shortname      = EXCLUDED.shortname,
                description    = EXCLUDED.description,
                attack_version = EXCLUDED.attack_version,
                url            = EXCLUDED.url,
                updated_at     = NOW()
        """), t)
        count += 1
    logger.info(f"Upserted {count} tactics")
    return count


def persist_techniques(session, techniques: list[dict]) -> int:
    count = 0
    for t in techniques:
        session.execute(text("""
            INSERT INTO attack_techniques (
                technique_id, parent_technique_id, name, description,
                is_subtechnique, tactic_ids, tactic_shortnames,
                platforms, data_sources, detection,
                url, attack_version, revoked, deprecated
            ) VALUES (
                :technique_id, :parent_technique_id, :name, :description,
                :is_subtechnique, :tactic_ids, :tactic_shortnames,
                :platforms, :data_sources, :detection,
                :url, :attack_version, :revoked, :deprecated
            )
            ON CONFLICT (technique_id) DO UPDATE SET
                parent_technique_id = EXCLUDED.parent_technique_id,
                name                = EXCLUDED.name,
                description         = EXCLUDED.description,
                is_subtechnique     = EXCLUDED.is_subtechnique,
                tactic_ids          = EXCLUDED.tactic_ids,
                tactic_shortnames   = EXCLUDED.tactic_shortnames,
                platforms           = EXCLUDED.platforms,
                data_sources        = EXCLUDED.data_sources,
                detection           = EXCLUDED.detection,
                url                 = EXCLUDED.url,
                attack_version      = EXCLUDED.attack_version,
                revoked             = EXCLUDED.revoked,
                deprecated          = EXCLUDED.deprecated,
                updated_at          = NOW()
        """), {
            **t,
            "tactic_ids":        t["tactic_ids"],        # list → passed as-is; SQLAlchemy + psycopg2 handle TEXT[]
            "tactic_shortnames": t["tactic_shortnames"],
            "platforms":         t["platforms"],
            "data_sources":      t["data_sources"],
        })
        count += 1
    logger.info(f"Upserted {count} techniques")
    return count


# ---------------------------------------------------------------------------
# Vector store (Qdrant / Chroma) — same collection + payload contract as vectorstore_retrieval
# ---------------------------------------------------------------------------

def techniques_for_vector_store(techniques: list[dict]) -> list[dict]:
    """
    Map parsed technique rows to the dict shape expected by ``ingest_attack_techniques``:
    technique_id, name, description, tactics (list[str]), platforms, data_sources,
    detection, url.
    """
    out: list[dict] = []
    for t in techniques:
        tid = (t.get("technique_id") or "").strip()
        if not tid:
            continue
        tactics = t.get("tactic_shortnames") or []
        if not isinstance(tactics, list):
            tactics = [str(tactics)] if tactics else []
        out.append({
            "technique_id": tid,
            "name": t.get("name") or tid,
            "description": (t.get("description") or "").strip(),
            "tactics": [str(x) for x in tactics if x],
            "platforms": list(t.get("platforms") or []),
            "data_sources": list(t.get("data_sources") or []),
            "detection": (t.get("detection") or "")[:2000],
            "url": t.get("url") or "",
        })
    return out


def ingest_techniques_vector_store(
    techniques: list[dict],
    *,
    batch_size: int = 128,
    collection_name: Optional[str] = None,
) -> int:
    """
    Embed + upsert techniques into the configured vector backend.

    Uses ``AttackCollections.TECHNIQUES`` (``attack_techniques``) unless
    ``collection_name`` is passed. This must match ``settings.ATTACK_TECHNIQUES_COLLECTION``
    and the registry in ``app/storage/collections.py`` so retrieval tools hit the same index.
    """
    _ensure_repo_root_on_path()
    from app.ingestion.attacktocve.vectorstore_retrieval import VectorStoreConfig, ingest_attack_techniques
    from app.storage.collections import AttackCollections

    coll = collection_name or AttackCollections.TECHNIQUES
    try:
        from app.core.settings import get_settings

        cfg_name = getattr(get_settings(), "ATTACK_TECHNIQUES_COLLECTION", None)
        if cfg_name and cfg_name != coll:
            logger.warning(
                "ATTACK_TECHNIQUES_COLLECTION=%r differs from canonical %r; ingesting into %r.",
                cfg_name,
                AttackCollections.TECHNIQUES,
                coll,
            )
    except Exception as e:
        logger.debug("Could not compare ATTACK_TECHNIQUES_COLLECTION: %s", e)

    docs = techniques_for_vector_store(techniques)
    if not docs:
        logger.info("No techniques to ingest into vector store")
        return 0

    config = VectorStoreConfig.from_settings(collection=coll)
    bs = max(1, int(batch_size))
    total = 0
    for i in range(0, len(docs), bs):
        chunk = docs[i : i + bs]
        n = ingest_attack_techniques(chunk, config)
        total += n
        logger.info(
            "Vector store batch %d–%d / %d upserted (%d points) → collection %r",
            i,
            min(i + bs, len(docs)),
            len(docs),
            n,
            coll,
        )
    return total


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def load_attack_enterprise(
    version: str | None = None,
    local_file: str | None = None,
    include_revoked: bool = False,
    include_deprecated: bool = False,
    *,
    ingest_vector_store: bool = True,
    vector_store_batch_size: int = 128,
    vector_collection_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Full pipeline: fetch → parse → persist to Postgres; optionally embed + upsert
    techniques to the vector store (``attack_techniques`` collection).

    Returns counts plus ``vector_ingested`` when vector ingest runs; on failure
    ``vector_ingested`` is 0 and ``vector_store_error`` may be set.
    """
    _ensure_repo_root_on_path()
    from app.storage.sqlalchemy_session import get_security_intel_session

    bundle = fetch_bundle(version=version, local_file=local_file)
    objects = bundle.get("objects", [])
    logger.info(f"Bundle contains {len(objects)} STIX objects")

    # Parse tactics first — needed to resolve tactic shortname → ID
    tactics = parse_tactics(objects)
    shortname_to_id = {t["shortname"]: t["tactic_id"] for t in tactics}

    techniques = parse_techniques(
        objects,
        tactic_shortname_to_id=shortname_to_id,
        include_revoked=include_revoked,
        include_deprecated=include_deprecated,
    )

    with get_security_intel_session("cve_attack") as session:
        n_tactics = persist_tactics(session, tactics)
        n_techniques = persist_techniques(session, techniques)
        session.commit()

    result: Dict[str, Any] = {
        "tactics": n_tactics,
        "techniques": n_techniques,
    }

    if ingest_vector_store:
        try:
            result["vector_ingested"] = ingest_techniques_vector_store(
                techniques,
                batch_size=vector_store_batch_size,
                collection_name=vector_collection_name,
            )
        except Exception as e:
            logger.warning("Vector store ingest failed (Postgres load succeeded): %s", e)
            result["vector_ingested"] = 0
            result["vector_store_error"] = str(e)
    else:
        result["vector_ingested"] = None

    return result


def main() -> None:
    import argparse
    import json
    import sys

    _ensure_repo_root_on_path()

    parser = argparse.ArgumentParser(description="Load MITRE ATT&CK Enterprise into Postgres + vector store")
    parser.add_argument("--version", default=None, help="Bundle version, e.g. 18.1 (omit for default bundle URL)")
    parser.add_argument("--file", default=None, help="Local enterprise-attack*.json path")
    parser.add_argument("--include-revoked", action="store_true")
    parser.add_argument("--include-deprecated", action="store_true")
    parser.add_argument("--no-vector-store", action="store_true", help="Skip Qdrant/Chroma technique embeddings")
    parser.add_argument("--vector-batch-size", type=int, default=128)
    args = parser.parse_args()

    try:
        out = load_attack_enterprise(
            version=args.version,
            local_file=args.file,
            include_revoked=args.include_revoked,
            include_deprecated=args.include_deprecated,
            ingest_vector_store=not args.no_vector_store,
            vector_store_batch_size=args.vector_batch_size,
        )
    except Exception as e:
        logger.exception("load_attack_enterprise failed: %s", e)
        sys.exit(1)

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
"""
ATT&CK Enrichment Tool
======================
Fetches and parses MITRE ATT&CK STIX data for a given technique ID.

Production path:
  1. Download enterprise-attack.json once → ingest into Postgres (attack_techniques table)
  2. All lookups query Postgres; GitHub fetch is the cold-start fallback.

This module ships:
  - ATTACKEnrichmentTool  – raw technique fetcher/parser
  - create_attack_enrichment_tool() – LangChain StructuredTool wrapper
  - create_attack_stix_ingestor()   – one-shot ingest helper
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# STIX source
# ---------------------------------------------------------------------------

STIX_ENTERPRISE_URL = (
    "https://raw.githubusercontent.com/mitre-attack/attack-stix-data"
    "/master/enterprise-attack/enterprise-attack-14.1.json"
)


# ---------------------------------------------------------------------------
# Input schema
# ---------------------------------------------------------------------------

class ATTACKEnrichInput(BaseModel):
    technique_id: str = Field(
        description=(
            "MITRE ATT&CK technique or sub-technique ID, e.g. 'T1059' or 'T1059.001'."
        )
    )


# ---------------------------------------------------------------------------
# Result dataclass (mirrors state.ATTACKTechniqueDetail)
# ---------------------------------------------------------------------------

class ATTACKTechniqueDetail(BaseModel):
    technique_id: str
    name: str
    description: str
    tactics: List[str] = Field(default_factory=list)
    platforms: List[str] = Field(default_factory=list)
    mitigations: List[Dict[str, str]] = Field(default_factory=list)
    data_sources: List[str] = Field(default_factory=list)
    detection: str = ""
    kill_chain_phases: List[str] = Field(default_factory=list)
    url: str = ""


# ---------------------------------------------------------------------------
# In-process STIX cache (avoids repeated large JSON downloads)
# ---------------------------------------------------------------------------

_STIX_BUNDLE_CACHE: Optional[Dict[str, Any]] = None


def _load_stix_bundle() -> Dict[str, Any]:
    global _STIX_BUNDLE_CACHE
    if _STIX_BUNDLE_CACHE is not None:
        return _STIX_BUNDLE_CACHE

    logger.info("Downloading ATT&CK STIX bundle …")
    resp = requests.get(STIX_ENTERPRISE_URL, timeout=60)
    resp.raise_for_status()
    _STIX_BUNDLE_CACHE = resp.json()
    logger.info(f"Loaded {len(_STIX_BUNDLE_CACHE.get('objects', []))} STIX objects")
    return _STIX_BUNDLE_CACHE


def _extract_attack_id(stix_obj: Dict[str, Any]) -> Optional[str]:
    """Pull the T-number from external_references."""
    for ref in stix_obj.get("external_references", []):
        if ref.get("source_name") == "mitre-attack":
            return ref.get("external_id")
    return None


def _extract_url(stix_obj: Dict[str, Any]) -> str:
    for ref in stix_obj.get("external_references", []):
        if ref.get("source_name") == "mitre-attack":
            return ref.get("url", "")
    return ""


# ---------------------------------------------------------------------------
# Core enrichment logic
# ---------------------------------------------------------------------------

class ATTACKEnrichmentTool:
    """Fetches full ATT&CK technique metadata from STIX bundle."""

    def __init__(self, use_postgres: bool = False, pg_dsn: Optional[str] = None):
        self.use_postgres = use_postgres
        self.pg_dsn = pg_dsn
        self._local_cache: Dict[str, ATTACKTechniqueDetail] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_technique(self, technique_id: str) -> ATTACKTechniqueDetail:
        tid = technique_id.strip().upper()

        # 1. Hot cache
        if tid in self._local_cache:
            return self._local_cache[tid]

        # 2. Postgres (if configured)
        if self.use_postgres:
            result = self._query_postgres(tid)
            if result:
                self._local_cache[tid] = result
                return result

        # 3. STIX bundle
        result = self._parse_from_stix(tid)
        self._local_cache[tid] = result
        return result

    # ------------------------------------------------------------------
    # STIX parsing
    # ------------------------------------------------------------------

    def _parse_from_stix(self, technique_id: str) -> ATTACKTechniqueDetail:
        bundle = _load_stix_bundle()
        objects = bundle.get("objects", [])

        # Index: attack-id → stix object
        technique_map: Dict[str, Dict] = {}
        mitigation_map: Dict[str, str] = {}      # stix-id → name
        relationship_list: List[Dict] = []

        for obj in objects:
            obj_type = obj.get("type", "")
            aid = _extract_attack_id(obj)

            if obj_type == "attack-pattern" and aid:
                technique_map[aid] = obj

            elif obj_type == "course-of-action" and aid:
                mitigation_map[obj["id"]] = obj.get("name", aid)

            elif obj_type == "relationship":
                relationship_list.append(obj)

        if technique_id not in technique_map:
            # Return stub if not found
            return ATTACKTechniqueDetail(
                technique_id=technique_id,
                name=f"Unknown technique {technique_id}",
                description="Technique not found in ATT&CK bundle.",
            )

        obj = technique_map[technique_id]

        # Tactics via kill-chain phases
        tactics = [
            phase["phase_name"].replace("-", " ").title()
            for phase in obj.get("kill_chain_phases", [])
            if phase.get("kill_chain_name") == "mitre-attack"
        ]

        # Platforms
        platforms = obj.get("x_mitre_platforms", [])

        # Data sources
        data_sources = obj.get("x_mitre_data_sources", [])

        # Detection
        detection = obj.get("x_mitre_detection", "")

        # Mitigations via relationships
        mitigations: List[Dict[str, str]] = []
        for rel in relationship_list:
            if (
                rel.get("relationship_type") == "mitigates"
                and rel.get("target_ref") == obj["id"]
            ):
                src_id = rel.get("source_ref", "")
                mit_name = mitigation_map.get(src_id, src_id)
                mit_attack_id = _extract_attack_id(
                    next((o for o in objects if o.get("id") == src_id), {})
                ) or ""
                mitigations.append({"id": mit_attack_id, "name": mit_name})

        return ATTACKTechniqueDetail(
            technique_id=technique_id,
            name=obj.get("name", technique_id),
            description=obj.get("description", ""),
            tactics=tactics,
            platforms=platforms,
            mitigations=mitigations,
            data_sources=data_sources,
            detection=detection,
            kill_chain_phases=[p["phase_name"] for p in obj.get("kill_chain_phases", [])],
            url=_extract_url(obj),
        )

    # ------------------------------------------------------------------
    # Postgres path (stub – wire to your pg_dsn)
    # ------------------------------------------------------------------

    def _query_postgres(self, technique_id: str) -> Optional[ATTACKTechniqueDetail]:
        """
        Query pre-ingested ATT&CK table.

        Expected schema:
          CREATE TABLE attack_techniques (
            technique_id   TEXT PRIMARY KEY,
            name           TEXT,
            description    TEXT,
            tactics        TEXT[],
            platforms      TEXT[],
            data_sources   TEXT[],
            detection      TEXT,
            mitigations    JSONB,
            url            TEXT,
            ingested_at    TIMESTAMPTZ DEFAULT now()
          );
        """
        try:
            import psycopg2
            import psycopg2.extras

            conn = psycopg2.connect(self.pg_dsn)
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT * FROM attack_techniques WHERE technique_id = %s",
                (technique_id,),
            )
            row = cur.fetchone()
            conn.close()

            if row:
                return ATTACKTechniqueDetail(
                    technique_id=row["technique_id"],
                    name=row["name"],
                    description=row["description"],
                    tactics=row["tactics"] or [],
                    platforms=row["platforms"] or [],
                    data_sources=row["data_sources"] or [],
                    detection=row["detection"] or "",
                    mitigations=row["mitigations"] or [],
                    url=row["url"] or "",
                )
        except Exception as e:
            logger.warning(f"Postgres ATT&CK lookup failed: {e}")
        return None


# ---------------------------------------------------------------------------
# LangChain tool factory
# ---------------------------------------------------------------------------

def create_attack_enrichment_tool(
    use_postgres: bool = False,
    pg_dsn: Optional[str] = None,
) -> StructuredTool:
    """
    Returns a LangChain StructuredTool for ATT&CK technique enrichment.
    Wire `use_postgres=True` + `pg_dsn` to avoid GitHub fetches in production.
    """
    tool_instance = ATTACKEnrichmentTool(use_postgres=use_postgres, pg_dsn=pg_dsn)

    def _execute(technique_id: str) -> Dict[str, Any]:
        try:
            detail = tool_instance.get_technique(technique_id)
            return detail.model_dump()
        except Exception as exc:
            logger.error(f"ATTACKEnrichmentTool error: {exc}")
            return {"error": str(exc), "technique_id": technique_id}

    return StructuredTool.from_function(
        func=_execute,
        name="attack_technique_enrich",
        description=(
            "Fetch full MITRE ATT&CK technique metadata (name, description, tactics, "
            "platforms, data sources, mitigations, detection notes) for a given "
            "technique or sub-technique ID such as 'T1059.001'."
        ),
        args_schema=ATTACKEnrichInput,
    )


# ---------------------------------------------------------------------------
# One-shot STIX → Postgres ingestor
# ---------------------------------------------------------------------------

def ingest_stix_to_postgres(pg_dsn: str) -> int:
    """
    Download ATT&CK STIX bundle and upsert all techniques into Postgres.
    Call once during bootstrapping.  Returns number of rows upserted.
    """
    import psycopg2
    import psycopg2.extras

    tool = ATTACKEnrichmentTool()
    bundle = _load_stix_bundle()
    objects = bundle.get("objects", [])

    rows = 0
    conn = psycopg2.connect(pg_dsn)
    cur = conn.cursor()

    for obj in objects:
        if obj.get("type") != "attack-pattern":
            continue
        aid = _extract_attack_id(obj)
        if not aid:
            continue
        detail = tool._parse_from_stix(aid)
        cur.execute(
            """
            INSERT INTO attack_techniques
              (technique_id, name, description, tactics, platforms,
               data_sources, detection, mitigations, url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (technique_id) DO UPDATE SET
              name        = EXCLUDED.name,
              description = EXCLUDED.description,
              tactics     = EXCLUDED.tactics,
              platforms   = EXCLUDED.platforms,
              data_sources = EXCLUDED.data_sources,
              detection   = EXCLUDED.detection,
              mitigations = EXCLUDED.mitigations,
              url         = EXCLUDED.url
            """,
            (
                detail.technique_id,
                detail.name,
                detail.description,
                detail.tactics,
                detail.platforms,
                detail.data_sources,
                detail.detection,
                json.dumps(detail.mitigations),
                detail.url,
            ),
        )
        rows += 1

    conn.commit()
    conn.close()
    logger.info(f"Ingested {rows} ATT&CK techniques into Postgres")
    return rows

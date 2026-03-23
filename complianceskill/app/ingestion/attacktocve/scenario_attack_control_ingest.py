"""
Load risk-control YAML (scenarios + mitigated_by) and enriched control taxonomy JSON,
score ATT&CK (technique, tactic) pairs against scenarios, and persist:

- attack_technique_control_mapping (phase1)
- attack_control_mappings_multi (CVE pipeline)
- Qdrant/Chroma collection ``attack_control_mappings`` (settings.ATTACK_CONTROL_MAPPINGS_COLLECTION)
  for semantic retrieval of the same mappings

Uses the keyword-overlap retrieval from attack_control_design.md (Stage A retrieval).
Reuses security_intel DB sessions and tactic context from the CVE pipeline tools.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import yaml

from app.agents.tools.attack_tools import _tactics_to_kill_chain_phases

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Framework packs: DB framework_id, scenario YAML, enriched JSON path, JSON root key
# Paths are resolved under CVE data root (flowharmonicai/data/cvedata by default).
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FrameworkPack:
    framework_id: str
    scenarios_relpath: str
    enriched_relpath: str
    enriched_root_key: str


DEFAULT_FRAMEWORK_PACKS: Tuple[FrameworkPack, ...] = (
    FrameworkPack("hipaa", "risk_control_yaml/hipaa/scenarios_hipaa.yaml", "control_taxonomy_enriched/hipaa_enriched.json", "hipaa"),
    FrameworkPack("soc2", "risk_control_yaml/soc2/scenarios_soc2.yaml", "control_taxonomy_enriched/soc2_enriched.json", "soc2"),
    FrameworkPack("nist_csf_2_0", "risk_control_yaml/nist_csf_2_0/scenarios_nist_csf_2_0.yaml", "control_taxonomy_enriched/nist_csf_2_0_enriched.json", "nist_csf_2_0"),
    FrameworkPack("iso27001_2022", "risk_control_yaml/iso27001_2022/scenarios_iso27001_2022.yaml", "control_taxonomy_enriched/iso27001_2022_enriched.json", "iso27001_2022"),
    FrameworkPack("iso27001_2013", "risk_control_yaml/iso27001_2013/scenarios_iso27001_2013.yaml", "control_taxonomy_enriched/iso27001_2013_enriched.json", "iso27001_2013"),
    FrameworkPack("cis_controls_v8_1", "risk_control_yaml/cis_controls_v8_1/scenarios_cis_controls_v8_1.yaml", "control_taxonomy_enriched/cis_controls_v8_1_enriched.json", "cis_controls_v8_1"),
)


def _default_cve_data_root() -> Path:
    try:
        from app.core.settings import get_settings

        base = get_settings().BASE_DIR.resolve()
        candidate = base.parent / "data" / "cvedata"
        if candidate.is_dir():
            return candidate
    except Exception:
        pass
    # .../flowharmonicai/complianceskill/app/ingestion/attacktocve/this_file.py → parents[4] == complianceskill
    here = Path(__file__).resolve()
    for p in (here.parents[4] / ".." / "data" / "cvedata", here.parents[5] / "data" / "cvedata"):
        rp = p.resolve()
        if rp.is_dir():
            return rp
    return (here.parents[4].parent / "data" / "cvedata").resolve()


def resolve_cve_data_root(explicit: Optional[Path] = None) -> Path:
    import os

    if explicit is not None:
        return explicit.expanduser().resolve()
    env = os.getenv("CVE_DATA_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return _default_cve_data_root().resolve()


def _tokenize(*text_parts: str) -> set:
    blob = " ".join(p for p in text_parts if p)
    return set(re.findall(r"[a-z0-9]+", blob.lower()))


def score_scenario_technique(
    technique_name: str,
    tactic_slug: str,
    scenario: Dict[str, Any],
    description_excerpt: str = "",
) -> float:
    """Keyword overlap score (design doc: Stage A retrieval)."""
    name = (technique_name or "").strip()
    tactic = (tactic_slug or "").strip().lower().replace(" ", "-")
    scenario_name = str(scenario.get("name") or "").strip()
    category = str(scenario.get("category") or "")
    loss = scenario.get("loss_outcomes") or []
    loss_bits = [str(o).replace("_", " ") for o in loss if o]
    asset = str(scenario.get("asset") or "").replace("_", " ")
    scenario_tokens = _tokenize(scenario_name, category, asset, *loss_bits)

    technique_tokens = _tokenize(name, tactic.replace("-", " "))
    if description_excerpt:
        technique_tokens |= _tokenize(description_excerpt[:600])

    if not technique_tokens:
        return 0.0
    inter = technique_tokens & scenario_tokens
    return len(inter) / max(len(technique_tokens), 1)


@lru_cache(maxsize=4096)
def _tactic_context_cached(technique_id: str, tactic: str) -> Tuple[str, str]:
    """(tactic_risk_lens, blast_radius); cached for batch ingest."""
    try:
        from app.agents.tools.tactic_contextualiser import _execute_tactic_contextualise

        ctx = _execute_tactic_contextualise(technique_id, tactic)
        return (ctx.get("tactic_risk_lens") or "", ctx.get("blast_radius") or "identity")
    except Exception as e:
        logger.debug("tactic_contextualiser skipped for %s/%s: %s", technique_id, tactic, e)
        return ("", "identity")


def _confidence_label(score: float) -> str:
    if score >= 0.12:
        return "high"
    if score >= 0.05:
        return "medium"
    return "low"


def _effectiveness_for_control(enriched_by_id: Dict[str, Any], control_id: str) -> str:
    row = enriched_by_id.get(control_id) or {}
    ctype = (row.get("control_type_classification") or {}).get("type")
    if ctype in ("preventive", "detective", "corrective"):
        return ctype
    return "unknown"


def load_scenarios_yaml(path: Path) -> List[Dict[str, Any]]:
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, list):
        raise ValueError(f"Expected YAML list in {path}")
    out: List[Dict[str, Any]] = []
    for item in data:
        if isinstance(item, dict) and item.get("scenario_id"):
            out.append(item)
    return out


def load_enriched_controls(path: Path, root_key: str) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    block = data.get(root_key)
    if not isinstance(block, dict):
        logger.warning(f"Enriched JSON missing or empty root {root_key!r} in {path}")
        return {}
    return block


def get_framework_pack(framework_id: str) -> FrameworkPack:
    fid = framework_id.strip().lower()
    for p in DEFAULT_FRAMEWORK_PACKS:
        if p.framework_id == fid:
            return p
    raise ValueError(f"Unknown framework_id {framework_id!r}. Choose one of: {[p.framework_id for p in DEFAULT_FRAMEWORK_PACKS]}")


def fetch_technique_tactic_pairs_from_db() -> List[Dict[str, Any]]:
    """
    Prefer attack_techniques (full metadata). Fallback: DISTINCT from cve_attack_mappings.
    Each dict: technique_id, tactic, technique_name, description, data_sources (list[str]), platforms (list[str]).
    """
    from sqlalchemy import text

    from app.storage.sqlalchemy_session import get_security_intel_session

    pairs: List[Dict[str, Any]] = []
    with get_security_intel_session("cve_attack") as session:
        rows = session.execute(
            text(
                """
                SELECT technique_id, name, description, tactics, data_sources, platforms
                FROM attack_techniques
                ORDER BY technique_id
                """
            )
        ).fetchall()

        if rows:
            for r in rows:
                tid = (r[0] or "").strip().upper()
                name = r[1] or tid
                desc = r[2] or ""
                tactics = r[3] or []
                ds = r[4] or []
                pl = r[5] or []
                phases = _tactics_to_kill_chain_phases(list(tactics) if tactics else [])
                if not phases:
                    phases = ["initial-access"]
                all_tactics = list(phases)
                for tactic in phases:
                    pairs.append({
                        "technique_id": tid,
                        "tactic": tactic,
                        "technique_name": name,
                        "description": desc,
                        "data_sources": list(ds) if isinstance(ds, (list, tuple)) else [],
                        "platforms": list(pl) if isinstance(pl, (list, tuple)) else [],
                        "kill_chain_phases": all_tactics,
                    })
            return pairs

        rows2 = session.execute(
            text(
                """
                SELECT DISTINCT technique_id, tactic
                FROM cve_attack_mappings
                ORDER BY technique_id, tactic
                """
            )
        ).fetchall()

    # Enrich from ATT&CK without holding DB session during HTTP/STIX
    cache: Dict[str, Dict[str, Any]] = {}
    for r in rows2:
        tid = (r[0] or "").strip().upper()
        tactic = (r[1] or "").strip().lower().replace(" ", "-")
        if not tid or not tactic:
            continue
        if tid not in cache:
            cache[tid] = _fetch_technique_detail_dict(tid)
        d = cache[tid]
        kc = d.get("kill_chain_phases") or [tactic]
        pairs.append({
            "technique_id": tid,
            "tactic": tactic,
            "technique_name": d.get("name") or tid,
            "description": d.get("description") or "",
            "data_sources": d.get("data_sources") or [],
            "platforms": d.get("platforms") or [],
            "kill_chain_phases": list(kc),
        })
    return pairs


def _fetch_technique_detail_dict(technique_id: str) -> Dict[str, Any]:
    try:
        from app.agents.tools.attack_tools import ATTACKEnrichmentTool
        from app.core.settings import get_settings

        settings = get_settings()
        pg_dsn = settings.get_attack_db_dsn() if hasattr(settings, "get_attack_db_dsn") else None
        enricher = ATTACKEnrichmentTool(use_postgres=bool(pg_dsn), pg_dsn=pg_dsn)
        detail = enricher.get_technique(technique_id)
        return {
            "name": detail.name,
            "description": detail.description,
            "data_sources": list(detail.data_sources or []),
            "platforms": list(detail.platforms or []),
            "kill_chain_phases": list(detail.kill_chain_phases or []),
        }
    except Exception as e:
        logger.debug(f"ATT&CK enrich fallback for {technique_id}: {e}")
        return {
            "name": technique_id,
            "description": "",
            "data_sources": [],
            "platforms": [],
            "kill_chain_phases": [],
        }


def _top_scenarios_for_technique(
    technique_row: Dict[str, Any],
    scenarios: Sequence[Dict[str, Any]],
    top_k: int,
    min_score: float,
) -> List[Tuple[Dict[str, Any], float]]:
    ds_hint = " ".join(technique_row.get("data_sources") or [])[:400]
    excerpt = (technique_row.get("description") or "")[:800]
    scored: List[Tuple[Dict[str, Any], float]] = []
    for sc in scenarios:
        s = score_scenario_technique(
            technique_row["technique_name"],
            technique_row["tactic"],
            sc,
            description_excerpt=excerpt + " " + ds_hint,
        )
        if s >= min_score:
            scored.append((sc, s))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


def build_rows_for_pair(
    technique_row: Dict[str, Any],
    scenario: Dict[str, Any],
    scenario_score: float,
    enriched_by_id: Dict[str, Any],
    framework_id: str,
    mapping_run_id: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Returns (phase1_rows, multi_rows) for one (technique, tactic) and one scenario.
    """
    mitigated = scenario.get("mitigated_by") or scenario.get("controls") or []
    if not isinstance(mitigated, list):
        mitigated = []
    control_ids = [str(c).strip() for c in mitigated if c]

    scenario_id = str(scenario.get("scenario_id") or "")
    loss_outcomes = [str(x) for x in (scenario.get("loss_outcomes") or []) if x]

    phase1: List[Dict[str, Any]] = []
    multi: List[Dict[str, Any]] = []

    conf = _confidence_label(scenario_score)
    rel = max(0.001, min(1.0, round(float(scenario_score), 3)))

    tactic_lens, blast = _tactic_context_cached(technique_row["technique_id"], technique_row["tactic"])

    rationale = (
        f"Scenario {scenario_id} ({scenario_score:.3f} keyword overlap); "
        f"{str(scenario.get('name') or '')[:160]}"
    )
    notes = f"scenario_id={scenario_id}; framework={framework_id}; run={mapping_run_id}"

    for cid in control_ids:
        effectiveness = _effectiveness_for_control(enriched_by_id, cid)
        phase1.append({
            "attack_technique_id": technique_row["technique_id"],
            "control_id": cid,
            "mitigation_effectiveness": effectiveness,
            "mapping_source": "scenario_keyword",
            "confidence_score": float(rel),
            "notes": notes,
            # Internal: used to satisfy FK into controls + frameworks (stripped before INSERT)
            "_ingest_framework_id": framework_id,
        })
        multi.append({
            "technique_id": technique_row["technique_id"],
            "tactic": technique_row["tactic"],
            "item_id": cid,
            "framework_id": framework_id,
            "relevance_score": float(rel),
            "confidence": conf,
            "rationale": rationale,
            "tactic_risk_lens": tactic_lens,
            "blast_radius": blast,
            "attack_tactics": list(technique_row.get("kill_chain_phases") or [technique_row["tactic"]]),
            "attack_platforms": list(technique_row.get("platforms") or []),
            "loss_outcomes": loss_outcomes,
        })
    return phase1, multi


def _has_phase1_control_fk(session) -> bool:
    """True when attack_technique_control_mapping.control_id references controls(id)."""
    from sqlalchemy import text

    try:
        row = session.execute(
            text(
                """
                SELECT 1
                FROM information_schema.table_constraints
                WHERE table_schema = 'public'
                  AND table_name = 'attack_technique_control_mapping'
                  AND constraint_name = 'fk_attack_control_control_id'
                  AND constraint_type = 'FOREIGN KEY'
                LIMIT 1
                """
            )
        ).fetchone()
        return row is not None
    except Exception as e:
        logger.debug("Could not inspect FK fk_attack_control_control_id: %s", e)
        return False


def _existing_controls_ids(session, control_ids: set[str]) -> set[str]:
    """Return subset of control_ids that exist in controls.id (chunked IN queries)."""
    from sqlalchemy import text

    if not control_ids:
        return set()
    found: set[str] = set()
    ids = sorted(control_ids)
    chunk_sz = 400
    for off in range(0, len(ids), chunk_sz):
        part = ids[off : off + chunk_sz]
        placeholders = ", ".join(f":c{j}" for j in range(len(part)))
        params = {f"c{j}": part[j] for j in range(len(part))}
        try:
            rows = session.execute(
                text(f"SELECT id FROM controls WHERE id IN ({placeholders})"),
                params,
            ).fetchall()
        except Exception as e:
            err = str(e).lower()
            if "does not exist" in err or "undefined_table" in err or "relation" in err and "controls" in err:
                logger.warning(
                    "controls table missing while resolving phase1 FK rows; skipping phase1 writes: %s",
                    e,
                )
                return set()
            raise
        for r in rows:
            if r[0] is not None:
                found.add(str(r[0]))
    return found


def _table_exists(session, table_name: str) -> bool:
    from sqlalchemy import text

    row = session.execute(
        text(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = :t
            LIMIT 1
            """
        ),
        {"t": table_name},
    ).fetchone()
    return row is not None


def _get_table_columns(session, table_name: str) -> set[str]:
    from sqlalchemy import text

    rows = session.execute(
        text(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :t
            """
        ),
        {"t": table_name},
    ).fetchall()
    return {str(r[0]) for r in rows if r[0]}


def _control_row_exists(session, control_id: str) -> bool:
    from sqlalchemy import text

    try:
        row = session.execute(
            text("SELECT 1 FROM controls WHERE id = :id LIMIT 1"),
            {"id": control_id},
        ).fetchone()
        return row is not None
    except Exception:
        return False


def _ensure_framework_stub(session, framework_id: str) -> None:
    """Minimal frameworks row so controls.framework_id FK can be satisfied."""
    from sqlalchemy import text

    if not framework_id or not _table_exists(session, "frameworks"):
        return
    cols = _get_table_columns(session, "frameworks")
    if "id" not in cols or "name" not in cols:
        return
    name = framework_id.replace("_", " ").title()[:256]
    # Caller should run inside session.begin_nested() so failures roll back a savepoint only.
    if "version" in cols:
        session.execute(
            text(
                """
                INSERT INTO frameworks (id, name, version)
                VALUES (:id, :name, :version)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"id": framework_id, "name": name, "version": "auto"},
        )
    else:
        session.execute(
            text(
                """
                INSERT INTO frameworks (id, name)
                VALUES (:id, :name)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"id": framework_id, "name": name},
        )


def _ensure_control_stub_impl(session, control_id: str, framework_id: str) -> bool:
    """
    Insert a minimal controls row with id=control_id when missing (run inside savepoint).
    Tries the common framework-KB shape first, then id+name.
    """
    from sqlalchemy import text

    if not _table_exists(session, "controls"):
        return False
    if _control_row_exists(session, control_id):
        return True

    cols = _get_table_columns(session, "controls")
    fw = framework_id or "unknown_framework"
    display_name = f"Control {control_id}"[:512]
    description = "Auto-created for scenario-based attack→control ingest (FK)."

    if {"id", "framework_id", "control_code", "name"}.issubset(cols):
        _ensure_framework_stub(session, fw)
        base_cols = ["id", "framework_id", "control_code", "name"]
        params: Dict[str, Any] = {
            "id": control_id,
            "framework_id": fw,
            "control_code": control_id,
            "name": display_name,
        }
        if "description" in cols:
            base_cols.append("description")
            params["description"] = description[:10000]
        col_sql = ", ".join(base_cols)
        val_sql = ", ".join(f":{c}" for c in base_cols)
        session.execute(
            text(
                f"""
                INSERT INTO controls ({col_sql})
                VALUES ({val_sql})
                ON CONFLICT (id) DO NOTHING
                """
            ),
            params,
        )
        return _control_row_exists(session, control_id)

    if {"id", "name"}.issubset(cols):
        session.execute(
            text(
                """
                INSERT INTO controls (id, name) VALUES (:id, :name)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"id": control_id, "name": display_name},
        )
        return _control_row_exists(session, control_id)

    logger.warning(
        "Could not auto-create controls row for id=%r (table columns: %s)",
        control_id,
        sorted(cols),
    )
    return False


def _ensure_control_stub(session, control_id: str, framework_id: str) -> bool:
    """
    Insert a minimal controls row when missing. Uses a SAVEPOINT so a failed INSERT
    (constraint, type error, etc.) does not leave the session in an aborted transaction.
    """
    if not control_id:
        return False
    try:
        with session.begin_nested():
            return _ensure_control_stub_impl(session, control_id, framework_id)
    except Exception as e:
        logger.debug("Control stub savepoint rolled back for %s: %s", control_id, e)
        return False


def _ensure_control_stubs_for_phase1_chunk(session, chunk: List[Dict[str, Any]]) -> int:
    """Create missing controls (and frameworks if needed) for unique ids in chunk. Returns rows created."""
    if not chunk or not _has_phase1_control_fk(session):
        return 0
    seen: set[tuple[str, str]] = set()
    created = 0
    for r in chunk:
        cid = str(r.get("control_id") or "").strip()
        if not cid:
            continue
        fw = str(r.get("_ingest_framework_id") or "").strip() or "unknown_framework"
        key = (cid, fw)
        if key in seen:
            continue
        seen.add(key)
        if _control_row_exists(session, cid):
            continue
        if _ensure_control_stub(session, cid, fw):
            created += 1
    return created


def _phase1_insert_params(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{k: v for k, v in r.items() if not str(k).startswith("_")} for r in rows]


def persist_phase1_mappings(
    rows: Sequence[Dict[str, Any]],
    batch_size: int = 500,
) -> int:
    """
    Upsert phase1 rows using executemany in chunks.

    When ``fk_attack_control_control_id`` is present, missing ``controls`` rows are
    auto-created (minimal stub: same ``id`` as YAML ``control_id``, plus ``frameworks``
    row if required). Then mappings are inserted. Any row whose control still cannot
    be created is skipped (logged).
    """
    if not rows:
        return 0
    from sqlalchemy import text

    from app.storage.sqlalchemy_session import get_security_intel_session

    stmt = text(
        """
                    INSERT INTO attack_technique_control_mapping (
                        attack_technique_id, control_id, mitigation_effectiveness,
                        mapping_source, confidence_score, notes
                    ) VALUES (
                        :attack_technique_id, :control_id, :mitigation_effectiveness,
                        :mapping_source, :confidence_score, :notes
                    )
                    ON CONFLICT (attack_technique_id, control_id) DO UPDATE SET
                        mitigation_effectiveness = EXCLUDED.mitigation_effectiveness,
                        confidence_score = GREATEST(
                            COALESCE(attack_technique_control_mapping.confidence_score, 0),
                            EXCLUDED.confidence_score
                        ),
                        mapping_source = EXCLUDED.mapping_source,
                        notes = EXCLUDED.notes,
                        updated_at = NOW()
                    """
    )
    bs = max(1, int(batch_size))
    n = 0
    skipped_fk = 0
    stubs_created = 0
    with get_security_intel_session("cve_attack") as session:
        enforce_fk = _has_phase1_control_fk(session)
        for i in range(0, len(rows), bs):
            chunk = [dict(r) for r in rows[i : i + bs]]
            if enforce_fk:
                stubs_created += _ensure_control_stubs_for_phase1_chunk(session, chunk)
                candidates = {str(r["control_id"]) for r in chunk if r.get("control_id")}
                valid = _existing_controls_ids(session, candidates)
                if candidates and not valid:
                    skipped_fk += len(chunk)
                    continue
                filtered = [r for r in chunk if r.get("control_id") and str(r["control_id"]) in valid]
                skipped_fk += len(chunk) - len(filtered)
                chunk = filtered
            if not chunk:
                continue
            try:
                with session.begin_nested():
                    session.execute(stmt, _phase1_insert_params(chunk))
                n += len(chunk)
            except Exception as e:
                logger.warning(
                    "Phase1 attack_technique_control_mapping chunk failed (%s rows), skipped: %s",
                    len(chunk),
                    e,
                )
    if stubs_created:
        logger.info(
            "Phase1: auto-created %s control stub(s) in `controls` (and frameworks if needed) for FK.",
            stubs_created,
        )
    if skipped_fk:
        logger.info(
            "Phase1 attack_technique_control_mapping: skipped %s row(s) after stub ensure "
            "(control_id still not in `controls`).",
            skipped_fk,
        )
    return n


def _ingest_multi_mappings_vector_store(
    rows: List[Dict[str, Any]],
    mapping_run_id: str,
    *,
    batch_size: int = 64,
) -> int:
    """
    Embed + upsert the same rows as ``ingest_attack_control_mappings`` into the vector store
    (collection ``AttackCollections.CONTROL_MAPPINGS`` / ATTACK_CONTROL_MAPPINGS_COLLECTION).
    """
    if not rows:
        return 0
    try:
        from app.core.settings import get_settings
        from app.ingestion.attacktocve.vectorstore_retrieval import (
            VectorStoreConfig,
            ingest_attack_control_mappings,
        )
        from app.storage.collections import AttackCollections

        settings = get_settings()
        coll = getattr(settings, "ATTACK_CONTROL_MAPPINGS_COLLECTION", None) or AttackCollections.CONTROL_MAPPINGS
        cfg_name = getattr(settings, "ATTACK_CONTROL_MAPPINGS_COLLECTION", None)
        if cfg_name and cfg_name != AttackCollections.CONTROL_MAPPINGS:
            logger.debug(
                "ATTACK_CONTROL_MAPPINGS_COLLECTION=%r (registry %r)",
                cfg_name,
                AttackCollections.CONTROL_MAPPINGS,
            )

        config = VectorStoreConfig.from_settings(collection=coll)
        docs: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            d["mapping_run_id"] = d.get("mapping_run_id") or mapping_run_id
            d.setdefault("cve_id", d.get("cve_id") or "")
            docs.append(d)

        bs = max(1, int(batch_size))
        total = 0
        for i in range(0, len(docs), bs):
            total += ingest_attack_control_mappings(docs[i : i + bs], config)
        logger.info(
            "Upserted %s attack→control mapping vector(s) into collection %r",
            total,
            coll,
        )
        return total
    except Exception as e:
        logger.warning("Vector store ingest for attack→control mappings failed: %s", e)
        return 0


def persist_multi_mappings(
    rows: Sequence[Dict[str, Any]],
    mapping_run_id: Optional[str] = None,
    batch_size: int = 500,
    *,
    ingest_mapping_vectors: bool = True,
    mapping_vector_batch_size: int = 64,
) -> Tuple[int, int]:
    """
    Persist to Postgres and optionally to the vector store.
    Returns (postgres_upsert_count, vector_upsert_count).
    """
    if not rows:
        return (0, 0)
    from app.agents.tools.attack_control_mapping import _persist_control_mappings_multi

    run_id = mapping_run_id or str(uuid.uuid4())
    db_n = _persist_control_mappings_multi(
        list(rows),
        cve_id=None,
        mapping_run_id=run_id,
        batch_size=batch_size,
    )
    vec_n = 0
    if ingest_mapping_vectors and db_n > 0:
        vec_n = _ingest_multi_mappings_vector_store(
            list(rows),
            run_id,
            batch_size=mapping_vector_batch_size,
        )
    return (db_n, vec_n)


def _run_ingest_with_loaded_framework_data(
    pack: FrameworkPack,
    scenarios: List[Dict[str, Any]],
    enriched: Dict[str, Any],
    pairs: List[Dict[str, Any]],
    *,
    run_id: str,
    top_k_scenarios: int,
    min_scenario_score: float,
    dry_run: bool,
    pair_chunk_size: int,
    persist_batch_size: int,
    ingest_mapping_vectors: bool = True,
    mapping_vector_batch_size: int = 64,
) -> Dict[str, Any]:
    """
    One framework: scenarios + enriched already in memory. Processes technique pairs in
    chunks, persists each chunk (unless dry_run) to cap RAM and use batched SQL.
    """
    pcs = max(1, int(pair_chunk_size))
    pbs = max(1, int(persist_batch_size))
    _tactic_context_cached.cache_clear()

    total_phase1_rows = 0
    total_multi_rows = 0
    phase1_upserts = 0
    multi_upserts = 0
    multi_vectors_upserted = 0

    for off in range(0, len(pairs), pcs):
        chunk = pairs[off : off + pcs]
        phase1_chunk: List[Dict[str, Any]] = []
        multi_chunk: List[Dict[str, Any]] = []
        for row in chunk:
            top = _top_scenarios_for_technique(row, scenarios, top_k_scenarios, min_scenario_score)
            for sc, sc_score in top:
                p1, mu = build_rows_for_pair(row, sc, sc_score, enriched, pack.framework_id, run_id)
                phase1_chunk.extend(p1)
                multi_chunk.extend(mu)

        total_phase1_rows += len(phase1_chunk)
        total_multi_rows += len(multi_chunk)

        if dry_run:
            continue
        if phase1_chunk:
            phase1_upserts += persist_phase1_mappings(phase1_chunk, batch_size=pbs)
        if multi_chunk:
            db_m, vec_m = persist_multi_mappings(
                multi_chunk,
                mapping_run_id=run_id,
                batch_size=pbs,
                ingest_mapping_vectors=ingest_mapping_vectors,
                mapping_vector_batch_size=mapping_vector_batch_size,
            )
            multi_upserts += db_m
            multi_vectors_upserted += vec_m

    out: Dict[str, Any] = {
        "framework_id": pack.framework_id,
        "mapping_run_id": run_id,
        "technique_tactic_pairs": len(pairs),
        "scenarios_loaded": len(scenarios),
        "enriched_controls": len(enriched),
        "pair_chunk_size": pcs,
        "persist_batch_size": pbs,
    }
    if dry_run:
        out["dry_run"] = True
        out["phase1_rows"] = total_phase1_rows
        out["multi_rows"] = total_multi_rows
        out["multi_vectors_upserted"] = 0
    else:
        out["dry_run"] = False
        out["phase1_upserts"] = phase1_upserts
        out["multi_upserts"] = multi_upserts
        out["multi_vectors_upserted"] = multi_vectors_upserted
    return out


def run_scenario_attack_control_ingest(
    framework_id: str,
    *,
    cve_data_root: Optional[Path] = None,
    top_k_scenarios: int = 15,
    min_scenario_score: float = 0.02,
    dry_run: bool = False,
    limit_technique_pairs: Optional[int] = None,
    mapping_run_id: Optional[str] = None,
    pairs_preloaded: Optional[List[Dict[str, Any]]] = None,
    pair_chunk_size: int = 250,
    persist_batch_size: int = 500,
    ingest_mapping_vectors: bool = True,
    mapping_vector_batch_size: int = 64,
) -> Dict[str, Any]:
    """
    Load YAML + enriched JSON for framework_id, score DB techniques against scenarios,
    persist phase1 + attack_control_mappings_multi (chunked + batched), and optionally
    upsert the same mappings into the vector store.
    """
    pack = get_framework_pack(framework_id)
    root = resolve_cve_data_root(cve_data_root)
    scenarios_path = root / pack.scenarios_relpath
    enriched_path = root / pack.enriched_relpath
    if not scenarios_path.is_file():
        raise FileNotFoundError(f"Scenarios YAML not found: {scenarios_path}")
    if not enriched_path.is_file():
        raise FileNotFoundError(f"Enriched JSON not found: {enriched_path}")

    scenarios = load_scenarios_yaml(scenarios_path)
    enriched = load_enriched_controls(enriched_path, pack.enriched_root_key)

    pairs = list(pairs_preloaded) if pairs_preloaded is not None else fetch_technique_tactic_pairs_from_db()
    if limit_technique_pairs is not None:
        pairs = pairs[: max(0, limit_technique_pairs)]

    run_id = mapping_run_id or str(uuid.uuid4())
    try:
        return _run_ingest_with_loaded_framework_data(
            pack,
            scenarios,
            enriched,
            pairs,
            run_id=run_id,
            top_k_scenarios=top_k_scenarios,
            min_scenario_score=min_scenario_score,
            dry_run=dry_run,
            pair_chunk_size=pair_chunk_size,
            persist_batch_size=persist_batch_size,
            ingest_mapping_vectors=ingest_mapping_vectors,
            mapping_vector_batch_size=mapping_vector_batch_size,
        )
    finally:
        del scenarios
        del enriched


def run_all_frameworks_scenario_attack_control_ingest(
    *,
    cve_data_root: Optional[Path] = None,
    top_k_scenarios: int = 15,
    min_scenario_score: float = 0.02,
    dry_run: bool = False,
    limit_technique_pairs: Optional[int] = None,
    mapping_run_id: Optional[str] = None,
    pair_chunk_size: int = 250,
    persist_batch_size: int = 500,
    skip_missing_inputs: bool = True,
    ingest_mapping_vectors: bool = True,
    mapping_vector_batch_size: int = 64,
) -> Dict[str, Any]:
    """
    Run ingest for every known framework pack, one framework at a time in memory
    (only that framework's YAML + enriched JSON loaded). Technique/tactic pairs are
    fetched once and reused. Shares one mapping_run_id across frameworks when provided
    or generates a single UUID for the whole job.
    """
    root = resolve_cve_data_root(cve_data_root)
    run_id = mapping_run_id or str(uuid.uuid4())
    pairs = fetch_technique_tactic_pairs_from_db()
    if limit_technique_pairs is not None:
        pairs = pairs[: max(0, limit_technique_pairs)]

    summaries: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    for pack in DEFAULT_FRAMEWORK_PACKS:
        scenarios_path = root / pack.scenarios_relpath
        enriched_path = root / pack.enriched_relpath
        if not scenarios_path.is_file() or not enriched_path.is_file():
            msg = f"missing_yaml_or_json: {scenarios_path.name}, {enriched_path.name}"
            if not skip_missing_inputs:
                raise FileNotFoundError(
                    f"{pack.framework_id}: scenarios or enriched file missing "
                    f"({scenarios_path} / {enriched_path})"
                )
            logger.warning("Skipping framework %s (%s)", pack.framework_id, msg)
            skipped.append({"framework_id": pack.framework_id, "skipped": True, "reason": msg})
            continue

        scenarios = load_scenarios_yaml(scenarios_path)
        enriched = load_enriched_controls(enriched_path, pack.enriched_root_key)
        try:
            logger.info(
                "Scenario→control ingest: framework=%s scenarios=%s enriched_controls=%s pairs=%s",
                pack.framework_id,
                len(scenarios),
                len(enriched),
                len(pairs),
            )
            summaries.append(
                _run_ingest_with_loaded_framework_data(
                    pack,
                    scenarios,
                    enriched,
                    pairs,
                    run_id=run_id,
                    top_k_scenarios=top_k_scenarios,
                    min_scenario_score=min_scenario_score,
                    dry_run=dry_run,
                    pair_chunk_size=pair_chunk_size,
                    persist_batch_size=persist_batch_size,
                    ingest_mapping_vectors=ingest_mapping_vectors,
                    mapping_vector_batch_size=mapping_vector_batch_size,
                )
            )
        finally:
            del scenarios
            del enriched

    return {
        "all_frameworks": True,
        "mapping_run_id": run_id,
        "technique_tactic_pairs": len(pairs),
        "frameworks_completed": summaries,
        "frameworks_skipped": skipped,
        "dry_run": dry_run,
    }

"""
Postgres Persistence Layer
==========================
Saves and loads ATT&CK → CIS control mappings to/from the CCE Postgres database.
Applies the schema defined in schema.sql.

Usage
-----
    from persistence import MappingRepository

    repo = MappingRepository(dsn="postgresql://user:pass@localhost/ccdb")

    # After a mapping run:
    run_id = repo.create_run(triggered_by="cce_node", technique_count=5)
    repo.save_mappings(state["final_mappings"], run_id=run_id, retrieval_source="chroma")
    repo.complete_run(run_id, mapping_count=len(state["final_mappings"]), coverage_pct=82.5)

    # Query:
    mappings = repo.get_mappings_for_scenario("CIS-RISK-007")
    gaps = repo.get_unmapped_scenarios()
"""

from __future__ import annotations

import json
import logging
import uuid
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

# Handle both relative imports (when run as module) and absolute imports (when run as script)
try:
    from ..state import ControlMapping
    from ..control_loader import CISRiskScenario
except ImportError:
    from app.ingestion.attacktocve.state import ControlMapping
    from app.ingestion.attacktocve.control_loader import CISRiskScenario

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connection pool helper (psycopg2)
# ---------------------------------------------------------------------------

class _DB:
    """Minimal connection wrapper. For production use psycopg2.pool or asyncpg."""

    def __init__(self, dsn: str):
        self.dsn = dsn

    @contextmanager
    def cursor(self, dict_cursor: bool = True):
        import psycopg2
        import psycopg2.extras

        conn = psycopg2.connect(self.dsn)
        try:
            factory = psycopg2.extras.RealDictCursor if dict_cursor else None
            cur = conn.cursor(cursor_factory=factory)
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

class MappingRepository:
    """
    CRUD operations for the attack_control_mappings schema.

    Designed to be instantiated once per CCE run and shared across nodes.
    Thread-safe if each caller holds its own connection (no connection pooling here;
    add psycopg2.pool.ThreadedConnectionPool for high-throughput scenarios).
    """

    def __init__(self, dsn: str):
        self._db = _DB(dsn)

    # ------------------------------------------------------------------
    # Run lifecycle
    # ------------------------------------------------------------------

    def create_run(
        self,
        triggered_by: str = "unknown",
        technique_filter: Optional[str] = None,
        asset_filter: Optional[str] = None,
        scenario_count: Optional[int] = None,
        technique_count: Optional[int] = None,
    ) -> str:
        """Insert a new mapping_runs row and return its UUID."""
        run_id = str(uuid.uuid4())
        with self._db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mapping_runs
                  (run_id, triggered_by, technique_filter, asset_filter,
                   scenario_count, technique_count, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'running')
                """,
                (run_id, triggered_by, technique_filter, asset_filter,
                 scenario_count, technique_count),
            )
        logger.info(f"[repo] Created run {run_id}")
        return run_id

    def complete_run(
        self,
        run_id: str,
        mapping_count: int = 0,
        coverage_pct: float = 0.0,
        duration_seconds: float = 0.0,
        status: str = "complete",
        error_message: Optional[str] = None,
    ) -> None:
        with self._db.cursor() as cur:
            cur.execute(
                """
                UPDATE mapping_runs SET
                    mapping_count   = %s,
                    coverage_pct    = %s,
                    duration_seconds = %s,
                    status          = %s,
                    error_message   = %s,
                    completed_at    = NOW()
                WHERE run_id = %s
                """,
                (mapping_count, coverage_pct, duration_seconds, status, error_message, run_id),
            )
        logger.info(f"[repo] Run {run_id} → {status}")

    # ------------------------------------------------------------------
    # Save mappings
    # ------------------------------------------------------------------

    def save_mappings(
        self,
        mappings: List[ControlMapping],
        run_id: Optional[str] = None,
        retrieval_source: str = "unknown",
        validated: bool = False,
    ) -> int:
        """
        Upsert all mappings from a pipeline run.
        Returns number of rows inserted/updated.
        """
        if not mappings:
            return 0

        count = 0
        with self._db.cursor(dict_cursor=False) as cur:
            for m in mappings:
                cur.execute(
                    "SELECT upsert_attack_control_mapping(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        m.technique_id,
                        m.scenario_id,
                        m.relevance_score,
                        m.confidence,
                        m.rationale,
                        m.attack_tactics or [],
                        m.attack_platforms or [],
                        m.loss_outcomes or [],
                        run_id,
                        retrieval_source,
                        validated,
                        None,
                    ),
                )
                count += 1

        logger.info(f"[repo] Saved {count} mapping(s) for run {run_id}")
        return count

    def save_evaluation(
        self,
        eval_dict: Dict[str, Any],
        run_id: Optional[str] = None,
    ) -> None:
        agg = eval_dict.get("aggregate", {})
        with self._db.cursor(dict_cursor=False) as cur:
            cur.execute(
                """
                INSERT INTO mapping_evaluations
                  (run_id, scenario_coverage_pct, total_mappings,
                   unique_techniques, tactic_breadth_pct, avg_relevance_score,
                   precision_vs_gt, recall_vs_gt, issues_count, full_report)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    run_id,
                    agg.get("scenario_coverage_pct"),
                    agg.get("total_mappings"),
                    agg.get("unique_techniques_mapped"),
                    agg.get("tactic_breadth_pct"),
                    agg.get("avg_relevance_score"),
                    agg.get("precision_vs_ground_truth"),
                    agg.get("recall_vs_ground_truth"),
                    len(eval_dict.get("issues", [])),
                    json.dumps(eval_dict),
                ),
            )

    # ------------------------------------------------------------------
    # Seed / sync from YAML
    # ------------------------------------------------------------------

    def seed_scenarios(self, scenarios: List[CISRiskScenario]) -> int:
        """Upsert CIS risk scenarios from the loaded YAML registry."""
        count = 0
        with self._db.cursor(dict_cursor=False) as cur:
            for s in scenarios:
                cur.execute(
                    """
                    INSERT INTO cis_risk_scenarios
                      (scenario_id, name, asset, trigger, loss_outcomes, description)
                    VALUES (%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (scenario_id) DO UPDATE SET
                        name        = EXCLUDED.name,
                        asset       = EXCLUDED.asset,
                        trigger     = EXCLUDED.trigger,
                        loss_outcomes = EXCLUDED.loss_outcomes,
                        description = EXCLUDED.description,
                        updated_at  = NOW()
                    """,
                    (s.scenario_id, s.name, s.asset, s.trigger,
                     s.loss_outcomes, s.description),
                )
                count += 1
        logger.info(f"[repo] Seeded {count} CIS scenarios")
        return count

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def get_mappings_for_scenario(self, scenario_id: str) -> List[Dict[str, Any]]:
        """Return all confirmed technique mappings for a given scenario."""
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT m.*, t.name AS technique_name, t.tactics, t.platforms
                FROM attack_control_mappings m
                JOIN attack_techniques t ON t.technique_id = m.technique_id
                WHERE m.scenario_id = %s
                ORDER BY m.relevance_score DESC
                """,
                (scenario_id,),
            )
            return [dict(row) for row in cur.fetchall()]

    def get_mappings_for_technique(self, technique_id: str) -> List[Dict[str, Any]]:
        """Return all CIS scenarios mapped to a given ATT&CK technique."""
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT m.*, s.name AS scenario_name, s.asset, s.loss_outcomes
                FROM attack_control_mappings m
                JOIN cis_risk_scenarios s ON s.scenario_id = m.scenario_id
                WHERE m.technique_id = %s
                ORDER BY m.relevance_score DESC
                """,
                (technique_id,),
            )
            return [dict(row) for row in cur.fetchall()]

    def get_unmapped_scenarios(self) -> List[Dict[str, Any]]:
        """Return scenarios with no confirmed ATT&CK mappings."""
        with self._db.cursor() as cur:
            cur.execute("SELECT * FROM v_unmapped_scenarios")
            return [dict(row) for row in cur.fetchall()]

    def get_coverage_report(self) -> Dict[str, Any]:
        """Pull the current asset-domain coverage view."""
        with self._db.cursor() as cur:
            cur.execute("SELECT * FROM v_asset_coverage")
            asset_rows = [dict(row) for row in cur.fetchall()]
            cur.execute("SELECT * FROM v_top_techniques LIMIT 20")
            top_techniques = [dict(row) for row in cur.fetchall()]
        return {"asset_coverage": asset_rows, "top_techniques": top_techniques}

    def technique_exists(self, technique_id: str) -> bool:
        with self._db.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM attack_techniques WHERE technique_id = %s", (technique_id,)
            )
            return cur.fetchone() is not None

    def mapping_exists(self, technique_id: str, scenario_id: str) -> bool:
        with self._db.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM attack_control_mappings WHERE technique_id=%s AND scenario_id=%s",
                (technique_id, scenario_id),
            )
            return cur.fetchone() is not None

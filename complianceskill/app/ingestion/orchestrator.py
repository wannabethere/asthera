"""
Ingestion orchestrator.

Execution order per framework:
  1. Upsert Framework row in Postgres
  2. Upsert Controls (Postgres) → embed → Qdrant (payload carries postgres_id)
  3. Upsert Requirements (Postgres) → embed → Qdrant
  4. Upsert Risks (Postgres) → embed → Qdrant
  5. Upsert Scenarios (Postgres) → embed → Qdrant
  6. Upsert TestCases (Postgres) → embed → Qdrant
  7. Resolve bridge tables: RiskControl, RequirementControl, ScenarioControl
  8. Resolve cross-framework mappings

The Qdrant point ID is a deterministic UUID derived from the Postgres primary key
so re-running ingestion is idempotent (upserts, not inserts).
"""

import hashlib
import logging
import uuid
from typing import List, Optional, Dict, Tuple

from sqlalchemy.orm import Session
from qdrant_client.http import models as qmodels

from app.ingestion.base import (
    FrameworkIngestionBundle,
    NormalizedControl,
    NormalizedRequirement,
    NormalizedRisk,
    NormalizedTestCase,
    NormalizedScenario,
    BaseFrameworkAdapter,
)
from app.ingestion.models import (
    Framework,
    Control,
    Requirement,
    Risk,
    TestCase,
    Scenario,
    RiskControl,
    RequirementControl,
    ScenarioControl,
    CrossFrameworkMapping,
)
from app.storage.sqlalchemy_session import get_session
from app.storage.qdrant_framework_store import Collections, upsert_points
from app.ingestion.embedder import (
    EmbeddingService,
    build_control_embedding_text,
    build_risk_embedding_text,
    build_requirement_embedding_text,
    build_test_case_embedding_text,
    build_scenario_embedding_text,
)

logger = logging.getLogger(__name__)


def _stable_uuid(seed: str) -> str:
    """Generate a deterministic UUID v5 from a seed string (for Qdrant point IDs)."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, seed))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

class IngestionOrchestrator:
    """
    Orchestrates the full ingestion pipeline for one framework at a time.

    Usage:
        orchestrator = IngestionOrchestrator()
        orchestrator.ingest(bundle)
    """

    def __init__(self, embedder: Optional[EmbeddingService] = None):
        self._embedder = embedder or EmbeddingService()

    def ingest(self, bundle: FrameworkIngestionBundle) -> None:
        """
        Run the full ingestion pipeline for one framework bundle.
        Idempotent: safe to re-run; existing records are updated.
        """
        fw = bundle.framework
        logger.info(f"Starting ingestion: {fw.id} ({fw.name} {fw.version})")

        with get_session() as session:
            self._upsert_framework(session, bundle)
            control_map = self._upsert_controls(session, bundle)
            req_map = self._upsert_requirements(session, bundle)
            risk_map = self._upsert_risks(session, bundle)
            self._upsert_scenarios(session, bundle, control_map)
            self._upsert_test_cases(session, bundle, risk_map, control_map)
            self._resolve_risk_controls(session, bundle, risk_map, control_map)
            self._resolve_cross_framework_mappings(session, bundle, control_map)

        logger.info(f"Ingestion complete: {fw.id}")

    # ------------------------------------------------------------------
    # Step 1: Framework
    # ------------------------------------------------------------------

    def _upsert_framework(self, session: Session, bundle: FrameworkIngestionBundle) -> None:
        fw = bundle.framework
        existing = session.get(Framework, fw.id)
        if existing:
            existing.name = fw.name
            existing.version = fw.version
            existing.description = fw.description
            existing.source_url = fw.source_url
        else:
            session.add(Framework(
                id=fw.id,
                name=fw.name,
                version=fw.version,
                description=fw.description,
                source_url=fw.source_url,
            ))
        session.flush()
        logger.debug(f"Framework upserted: {fw.id}")

    # ------------------------------------------------------------------
    # Step 2: Controls
    # ------------------------------------------------------------------

    def _upsert_controls(
        self, session: Session, bundle: FrameworkIngestionBundle
    ) -> Dict[str, str]:
        """
        Returns: dict mapping control_code → postgres control.id
        """
        if not bundle.controls:
            return {}

        fw = bundle.framework
        embed_texts = [
            build_control_embedding_text(
                name=c.name,
                description=c.description,
                domain=c.domain,
                framework_name=fw.name,
                control_type=c.control_type,
                cis_control_id=c.cis_control_id,
            )
            for c in bundle.controls
        ]
        vectors = self._embedder.embed(embed_texts)

        code_to_pg_id: Dict[str, str] = {}
        qdrant_points: List[qmodels.PointStruct] = []

        for ctrl, vector in zip(bundle.controls, vectors):
            pg_id = BaseFrameworkAdapter.make_control_id(fw.id, ctrl.control_code)
            qdrant_id = _stable_uuid(pg_id)
            code_to_pg_id[ctrl.control_code] = pg_id

            # Postgres upsert
            existing = session.get(Control, pg_id)
            if existing:
                existing.name = ctrl.name
                existing.description = ctrl.description
                existing.domain = ctrl.domain
                existing.control_type = ctrl.control_type
                existing.cis_control_id = ctrl.cis_control_id
                existing.qdrant_vector_id = qdrant_id
                existing.metadata_ = ctrl.metadata
            else:
                session.add(Control(
                    id=pg_id,
                    framework_id=fw.id,
                    control_code=ctrl.control_code,
                    name=ctrl.name,
                    description=ctrl.description,
                    domain=ctrl.domain,
                    control_type=ctrl.control_type,
                    cis_control_id=ctrl.cis_control_id,
                    qdrant_vector_id=qdrant_id,
                    metadata_=ctrl.metadata,
                ))

            # Qdrant point
            qdrant_points.append(qmodels.PointStruct(
                id=qdrant_id,
                vector=vector,
                payload={
                    "artifact_type": "control",
                    "artifact_id": pg_id,
                    "framework_id": fw.id,
                    "framework_name": fw.name,
                    "control_code": ctrl.control_code,
                    "name": ctrl.name,
                    "domain": ctrl.domain or "",
                    "control_type": ctrl.control_type or "",
                    "cis_control_id": ctrl.cis_control_id or "",
                    # Inline cross-framework refs for fast filtered search
                    "cross_framework_refs": ctrl.cross_framework_refs,
                },
            ))

        session.flush()
        if qdrant_points:
            upsert_points(Collections.CONTROLS, qdrant_points)
        logger.info(f"Upserted {len(bundle.controls)} controls for {fw.id}")
        return code_to_pg_id

    # ------------------------------------------------------------------
    # Step 3: Requirements
    # ------------------------------------------------------------------

    def _upsert_requirements(
        self, session: Session, bundle: FrameworkIngestionBundle
    ) -> Dict[str, str]:
        """Returns: dict mapping requirement_code → postgres requirement.id"""
        if not bundle.requirements:
            return {}

        fw = bundle.framework
        embed_texts = [
            build_requirement_embedding_text(
                requirement_code=r.requirement_code,
                description=r.description,
                domain=r.domain,
                compliance_type=r.compliance_type,
                framework_name=fw.name,
            )
            for r in bundle.requirements
        ]
        vectors = self._embedder.embed(embed_texts)

        code_to_pg_id: Dict[str, str] = {}
        qdrant_points: List[qmodels.PointStruct] = []

        for req, vector in zip(bundle.requirements, vectors):
            pg_id = _make_requirement_id(fw.id, req.requirement_code)
            qdrant_id = _stable_uuid(pg_id)
            code_to_pg_id[req.requirement_code] = pg_id

            existing = session.get(Requirement, pg_id)
            if existing:
                existing.name = req.name
                existing.description = req.description
                existing.domain = req.domain
                existing.compliance_type = req.compliance_type
                existing.qdrant_vector_id = qdrant_id
                existing.metadata_ = req.metadata
            else:
                session.add(Requirement(
                    id=pg_id,
                    framework_id=fw.id,
                    requirement_code=req.requirement_code,
                    name=req.name,
                    description=req.description,
                    domain=req.domain,
                    compliance_type=req.compliance_type,
                    qdrant_vector_id=qdrant_id,
                    metadata_=req.metadata,
                ))

            qdrant_points.append(qmodels.PointStruct(
                id=qdrant_id,
                vector=vector,
                payload={
                    "artifact_type": "requirement",
                    "artifact_id": pg_id,
                    "framework_id": fw.id,
                    "framework_name": fw.name,
                    "requirement_code": req.requirement_code,
                    "name": req.name or req.requirement_code,
                    "domain": req.domain or "",
                    "compliance_type": req.compliance_type or "",
                },
            ))

        session.flush()
        if qdrant_points:
            upsert_points(Collections.REQUIREMENTS, qdrant_points)
        logger.info(f"Upserted {len(bundle.requirements)} requirements for {fw.id}")
        return code_to_pg_id

    # ------------------------------------------------------------------
    # Step 4: Risks
    # ------------------------------------------------------------------

    def _upsert_risks(
        self, session: Session, bundle: FrameworkIngestionBundle
    ) -> Dict[str, str]:
        """Returns: dict mapping risk_code → postgres risk.id"""
        if not bundle.risks:
            return {}

        fw = bundle.framework
        embed_texts = [
            build_risk_embedding_text(
                name=r.name,
                description=r.description,
                asset=r.asset,
                loss_outcomes=r.loss_outcomes,
                framework_name=fw.name,
            )
            for r in bundle.risks
        ]
        vectors = self._embedder.embed(embed_texts)

        code_to_pg_id: Dict[str, str] = {}
        qdrant_points: List[qmodels.PointStruct] = []

        for risk, vector in zip(bundle.risks, vectors):
            pg_id = risk.risk_code   # Risk IDs are globally unique by convention
            qdrant_id = _stable_uuid(pg_id)
            code_to_pg_id[risk.risk_code] = pg_id

            existing = session.get(Risk, pg_id)
            if existing:
                existing.name = risk.name
                existing.description = risk.description
                existing.asset = risk.asset
                existing.trigger = risk.trigger
                existing.loss_outcomes = risk.loss_outcomes
                existing.qdrant_vector_id = qdrant_id
                existing.metadata_ = risk.metadata
            else:
                session.add(Risk(
                    id=pg_id,
                    framework_id=fw.id,
                    risk_code=risk.risk_code,
                    name=risk.name,
                    description=risk.description,
                    asset=risk.asset,
                    trigger=risk.trigger,
                    loss_outcomes=risk.loss_outcomes,
                    qdrant_vector_id=qdrant_id,
                    metadata_=risk.metadata,
                ))

            qdrant_points.append(qmodels.PointStruct(
                id=qdrant_id,
                vector=vector,
                payload={
                    "artifact_type": "risk",
                    "artifact_id": pg_id,
                    "framework_id": fw.id,
                    "framework_name": fw.name,
                    "risk_code": risk.risk_code,
                    "name": risk.name,
                    "asset": risk.asset or "",
                    "trigger": risk.trigger or "",
                    "loss_outcomes": risk.loss_outcomes,
                },
            ))

        session.flush()
        if qdrant_points:
            upsert_points(Collections.RISKS, qdrant_points)
        logger.info(f"Upserted {len(bundle.risks)} risks for {fw.id}")
        return code_to_pg_id

    # ------------------------------------------------------------------
    # Step 5: Scenarios
    # ------------------------------------------------------------------

    def _upsert_scenarios(
        self, session: Session, bundle: FrameworkIngestionBundle,
        control_map: Dict[str, str],
    ) -> Dict[str, str]:
        if not bundle.scenarios:
            return {}

        fw = bundle.framework
        embed_texts = [
            build_scenario_embedding_text(
                name=s.name,
                description=s.description,
                asset=s.asset,
                framework_name=fw.name,
            )
            for s in bundle.scenarios
        ]
        vectors = self._embedder.embed(embed_texts)

        code_to_pg_id: Dict[str, str] = {}
        qdrant_points: List[qmodels.PointStruct] = []

        for scenario, vector in zip(bundle.scenarios, vectors):
            pg_id = scenario.scenario_code
            qdrant_id = _stable_uuid(pg_id)
            code_to_pg_id[scenario.scenario_code] = pg_id

            existing = session.get(Scenario, pg_id)
            if existing:
                existing.name = scenario.name
                existing.description = scenario.description
                existing.asset = scenario.asset
                existing.trigger = scenario.trigger
                existing.loss_outcomes = scenario.loss_outcomes
                existing.qdrant_vector_id = qdrant_id
            else:
                session.add(Scenario(
                    id=pg_id,
                    framework_id=fw.id,
                    scenario_code=scenario.scenario_code,
                    name=scenario.name,
                    description=scenario.description,
                    asset=scenario.asset,
                    trigger=scenario.trigger,
                    loss_outcomes=scenario.loss_outcomes,
                    qdrant_vector_id=qdrant_id,
                    metadata_=scenario.metadata,
                ))

            qdrant_points.append(qmodels.PointStruct(
                id=qdrant_id,
                vector=vector,
                payload={
                    "artifact_type": "scenario",
                    "artifact_id": pg_id,
                    "framework_id": fw.id,
                    "framework_name": fw.name,
                    "scenario_code": scenario.scenario_code,
                    "name": scenario.name,
                    "asset": scenario.asset or "",
                    "loss_outcomes": scenario.loss_outcomes,
                },
            ))

        session.flush()
        if qdrant_points:
            upsert_points(Collections.SCENARIOS, qdrant_points)

        # Resolve scenario→control bridge links
        for scenario in bundle.scenarios:
            pg_sid = scenario.scenario_code
            for ctrl_code in scenario.relevant_control_codes:
                ctrl_pg_id = control_map.get(ctrl_code)
                if not ctrl_pg_id:
                    continue
                exists = session.get(ScenarioControl, (pg_sid, ctrl_pg_id))
                if not exists:
                    session.add(ScenarioControl(
                        scenario_id=pg_sid, control_id=ctrl_pg_id
                    ))
        session.flush()
        logger.info(f"Upserted {len(bundle.scenarios)} scenarios for {fw.id}")
        return code_to_pg_id

    # ------------------------------------------------------------------
    # Step 6: Test Cases
    # ------------------------------------------------------------------

    def _upsert_test_cases(
        self, session: Session, bundle: FrameworkIngestionBundle,
        risk_map: Dict[str, str], control_map: Dict[str, str],
    ) -> None:
        if not bundle.test_cases:
            return

        fw = bundle.framework
        embed_texts = [
            build_test_case_embedding_text(
                name=tc.name,
                objective=tc.objective,
                test_type=tc.test_type,
                success_criteria=tc.success_criteria,
                framework_name=fw.name,
            )
            for tc in bundle.test_cases
        ]
        vectors = self._embedder.embed(embed_texts)
        qdrant_points: List[qmodels.PointStruct] = []

        for tc, vector in zip(bundle.test_cases, vectors):
            pg_id = tc.test_id
            qdrant_id = _stable_uuid(pg_id)
            risk_pg_id = risk_map.get(tc.risk_code) if tc.risk_code else None
            ctrl_pg_id = control_map.get(tc.control_code) if tc.control_code else None

            existing = session.get(TestCase, pg_id)
            if existing:
                existing.name = tc.name
                existing.test_type = tc.test_type
                existing.objective = tc.objective
                existing.test_steps = tc.test_steps
                existing.expected_result = tc.expected_result
                existing.evidence_required = tc.evidence_required
                existing.success_criteria = tc.success_criteria
                existing.qdrant_vector_id = qdrant_id
            else:
                session.add(TestCase(
                    id=pg_id,
                    risk_id=risk_pg_id,
                    control_id=ctrl_pg_id,
                    framework_id=fw.id,
                    name=tc.name,
                    test_type=tc.test_type,
                    objective=tc.objective,
                    test_steps=tc.test_steps,
                    expected_result=tc.expected_result,
                    evidence_required=tc.evidence_required,
                    success_criteria=tc.success_criteria,
                    qdrant_vector_id=qdrant_id,
                    metadata_=tc.metadata,
                ))

            qdrant_points.append(qmodels.PointStruct(
                id=qdrant_id,
                vector=vector,
                payload={
                    "artifact_type": "test_case",
                    "artifact_id": pg_id,
                    "framework_id": fw.id,
                    "framework_name": fw.name,
                    "risk_id": risk_pg_id or "",
                    "name": tc.name,
                    "test_type": tc.test_type or "",
                },
            ))

        session.flush()
        if qdrant_points:
            upsert_points(Collections.TEST_CASES, qdrant_points)
        logger.info(f"Upserted {len(bundle.test_cases)} test cases for {fw.id}")

    # ------------------------------------------------------------------
    # Step 7: Risk-Control bridge
    # ------------------------------------------------------------------

    def _resolve_risk_controls(
        self, session: Session, bundle: FrameworkIngestionBundle,
        risk_map: Dict[str, str], control_map: Dict[str, str],
    ) -> None:
        """Populate risk_controls bridge from mitigating_control_codes in risks."""
        linked = 0
        for risk in bundle.risks:
            risk_pg_id = risk_map.get(risk.risk_code)
            if not risk_pg_id:
                continue
            for ctrl_code in risk.mitigating_control_codes:
                ctrl_pg_id = control_map.get(ctrl_code)
                if not ctrl_pg_id:
                    logger.debug(f"Risk {risk.risk_code}: control code '{ctrl_code}' not found in control_map")
                    continue
                exists = session.get(RiskControl, (risk_pg_id, ctrl_pg_id))
                if not exists:
                    session.add(RiskControl(
                        risk_id=risk_pg_id,
                        control_id=ctrl_pg_id,
                    ))
                    linked += 1
        session.flush()
        logger.info(f"Resolved {linked} risk→control links for {bundle.framework.id}")

    # ------------------------------------------------------------------
    # Step 8: Cross-framework mappings
    # ------------------------------------------------------------------

    def _resolve_cross_framework_mappings(
        self, session: Session, bundle: FrameworkIngestionBundle,
        control_map: Dict[str, str],
    ) -> None:
        """
        Parse inline cross_framework_refs from controls and write to
        cross_framework_mappings table.

        For each ref, we store:
          - source_control_id (resolved)
          - target_framework_id (known)
          - target_raw_code (the raw code string, e.g. "CC 2.1, CC 4.1")
          - target_control_id = None initially (resolved in a later validation pass)
        
        Note: Only creates mappings if the target framework exists in the database.
        Mappings to frameworks that haven't been ingested yet will be skipped
        (they can be resolved in a later validation pass after all frameworks are ingested).
        """
        fw = bundle.framework
        inserted = 0
        skipped = 0

        for ctrl in bundle.controls:
            src_ctrl_pg_id = control_map.get(ctrl.control_code)
            if not src_ctrl_pg_id:
                continue

            for target_framework_key, raw_codes in ctrl.cross_framework_refs.items():
                # Normalize framework key to our IDs
                target_fw_id = _normalize_framework_key(target_framework_key)
                
                # Check if target framework exists in database
                # Skip mappings to frameworks that haven't been ingested yet
                target_fw = session.get(Framework, target_fw_id)
                if not target_fw:
                    logger.debug(
                        f"Skipping cross-framework mapping: {fw.id}/{ctrl.control_code} → "
                        f"{target_fw_id} (target framework not yet ingested)"
                    )
                    skipped += 1
                    continue

                # Each raw_codes may be a comma-separated list — create one row per code
                for raw_code in _split_codes(raw_codes):
                    # Check if this exact raw mapping already exists
                    from sqlalchemy import and_, select
                    stmt = (
                        select(CrossFrameworkMapping)
                        .where(
                            and_(
                                CrossFrameworkMapping.source_control_id == src_ctrl_pg_id,
                                CrossFrameworkMapping.target_framework_id == target_fw_id,
                                CrossFrameworkMapping.target_raw_code == raw_code,
                            )
                        )
                    )
                    existing = session.execute(stmt).scalars().first()
                    if existing:
                        continue

                    session.add(CrossFrameworkMapping(
                        source_framework_id=fw.id,
                        source_control_id=src_ctrl_pg_id,
                        target_framework_id=target_fw_id,
                        target_raw_code=raw_code,
                        target_control_id=None,  # resolved in validation pass
                        mapping_type="related",
                        confidence_score=0.9,    # high confidence for YAML-inline refs
                        source="yaml_inline",
                    ))
                    inserted += 1

        session.flush()
        logger.info(
            f"Inserted {inserted} cross-framework mappings for {fw.id}"
            + (f" (skipped {skipped} mappings to frameworks not yet ingested)" if skipped > 0 else "")
        )


# ---------------------------------------------------------------------------
# Module-level helper functions
# ---------------------------------------------------------------------------

def _make_requirement_id(framework_id: str, requirement_code: str) -> str:
    safe = requirement_code.replace("(", "_").replace(")", "_").replace(".", "_")
    return f"{framework_id}__{safe}"




def _normalize_framework_key(key: str) -> str:
    """Map YAML inline keys to our framework IDs."""
    mapping = {
        "soc2": "soc2",
        "nist_csf_2_0": "nist_csf_2_0",
        "nist": "nist_csf_2_0",
        "iso27001": "iso27001",
        "iso_27001": "iso27001",
        "hipaa": "hipaa",
        "cis": "cis_v8_1",
        "cis_v8_1": "cis_v8_1",
        "fedramp": "fedramp",
    }
    return mapping.get(key.lower(), key.lower())


def _split_codes(raw: str) -> List[str]:
    """Split comma-separated control codes, stripping whitespace."""
    return [c.strip() for c in raw.split(",") if c.strip()]

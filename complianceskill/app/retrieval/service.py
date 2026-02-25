"""
RetrievalService — the single interface the agents use to fetch data.

Two-step pattern for every semantic search:
  1. Query Qdrant with the embedded query → get artifact_ids and scores
  2. Fetch full records from Postgres using those IDs → hydrate relationships

Direct lookup methods (get_control_context, get_risk_context, etc.) skip
Qdrant entirely and go straight to Postgres — used when an agent already
knows the exact artifact ID.

All public methods return typed result dataclasses (see retrieval/results.py).
Agents never touch raw ORM rows or Qdrant payloads.
"""

import logging
from typing import Optional, List, Dict, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.storage.sqlalchemy_session import get_session
from app.storage.qdrant_framework_store import Collections, search_collection
from app.ingestion.embedder import EmbeddingService
from app.ingestion.models import (
    Control, Requirement, Risk, TestCase, Scenario,
    CrossFrameworkMapping, Framework,
    RiskControl, RequirementControl, ScenarioControl,
)
from app.retrieval.results import (
    ControlResult, RequirementResult, RiskResult, TestCaseResult,
    ScenarioResult, CrossFrameworkResult, RetrievedContext,
)
from app.retrieval.converters import (
    control_to_result, requirement_to_result, risk_to_result,
    test_case_to_result, scenario_to_result, cross_framework_mapping_to_result,
)
from qdrant_client.http import models as qmodels

logger = logging.getLogger(__name__)

# Default number of results per search
DEFAULT_LIMIT = 10


class RetrievalService:
    """
    Unified retrieval interface for the framework knowledge base.

    Usage:
        service = RetrievalService()

        # Semantic search across controls
        ctx = service.search_controls("vulnerability scanning", limit=5)

        # Full context for a specific control
        ctx = service.get_control_context("cis_v8_1__VPM-2")

        # Cross-framework equivalents
        ctx = service.get_cross_framework_equivalents(
            "cis_v8_1__VPM-2", target_frameworks=["hipaa", "soc2"]
        )

        # Search everything at once
        ctx = service.search_all("patch management", framework_filter=["cis_v8_1"])
    """

    def __init__(self, embedder: Optional[EmbeddingService] = None):
        self._embedder = embedder or EmbeddingService()

    # ===========================================================================
    # Semantic search methods
    # ===========================================================================

    def search_controls(
        self,
        query: str,
        limit: int = DEFAULT_LIMIT,
        framework_filter: Optional[List[str]] = None,
        fetch_context: bool = False,
    ) -> RetrievedContext:
        """
        Semantic search over controls.

        Args:
            query: Natural language query.
            limit: Max results to return.
            framework_filter: Restrict to specific framework IDs, e.g. ["cis_v8_1", "hipaa"].
            fetch_context: If True, hydrate each control with its related risks,
                           requirements, test cases, and cross-framework mappings.
        """
        vector = self._embedder.embed_one(query)
        qdrant_filter = self._build_framework_filter(framework_filter)
        hits = search_collection(Collections.CONTROLS, vector, limit=limit, filters=qdrant_filter)

        id_score_map = {h.payload["artifact_id"]: h.score for h in hits}

        with get_session() as session:
            controls = self._fetch_controls_by_ids(session, list(id_score_map.keys()), fetch_context)
            results = [
                self._attach_context(
                    control_to_result(c, score=id_score_map.get(c.id), framework_name=c.framework.name),
                    c, session, fetch_context,
                )
                for c in controls
            ]

        results.sort(key=lambda r: r.similarity_score or 0, reverse=True)
        return RetrievedContext(
            query=query,
            artifact_type="control",
            controls=results,
            framework_filter=framework_filter,
            total_hits=len(hits),
        )

    def search_requirements(
        self,
        query: str,
        limit: int = DEFAULT_LIMIT,
        framework_filter: Optional[List[str]] = None,
        fetch_context: bool = False,
    ) -> RetrievedContext:
        """Semantic search over requirements."""
        vector = self._embedder.embed_one(query)
        qdrant_filter = self._build_framework_filter(framework_filter)
        hits = search_collection(Collections.REQUIREMENTS, vector, limit=limit, filters=qdrant_filter)

        id_score_map = {h.payload["artifact_id"]: h.score for h in hits}

        with get_session() as session:
            reqs = self._fetch_requirements_by_ids(session, list(id_score_map.keys()), fetch_context)
            results = []
            for req in reqs:
                r = requirement_to_result(req, score=id_score_map.get(req.id), framework_name=req.framework.name)
                if fetch_context:
                    r.satisfying_controls = [
                        control_to_result(rc.control, framework_name=rc.control.framework.name)
                        for rc in req.requirement_controls
                        if rc.control
                    ]
                results.append(r)

        results.sort(key=lambda r: r.similarity_score or 0, reverse=True)
        return RetrievedContext(
            query=query,
            artifact_type="requirement",
            requirements=results,
            framework_filter=framework_filter,
            total_hits=len(hits),
        )

    def search_risks(
        self,
        query: str,
        limit: int = DEFAULT_LIMIT,
        framework_filter: Optional[List[str]] = None,
        fetch_context: bool = False,
    ) -> RetrievedContext:
        """Semantic search over risks."""
        vector = self._embedder.embed_one(query)
        qdrant_filter = self._build_framework_filter(framework_filter)
        hits = search_collection(Collections.RISKS, vector, limit=limit, filters=qdrant_filter)

        id_score_map = {h.payload["artifact_id"]: h.score for h in hits}

        with get_session() as session:
            risks = self._fetch_risks_by_ids(session, list(id_score_map.keys()), fetch_context)
            results = []
            for risk in risks:
                r = risk_to_result(risk, score=id_score_map.get(risk.id), framework_name=risk.framework.name)
                if fetch_context:
                    r.mitigating_controls = [
                        control_to_result(rc.control, framework_name=rc.control.framework.name)
                        for rc in risk.risk_controls
                        if rc.control
                    ]
                    r.test_cases = [
                        test_case_to_result(tc, framework_name=tc.framework.name)
                        for tc in risk.test_cases
                    ]
                results.append(r)

        results.sort(key=lambda r: r.similarity_score or 0, reverse=True)
        return RetrievedContext(
            query=query,
            artifact_type="risk",
            risks=results,
            framework_filter=framework_filter,
            total_hits=len(hits),
        )

    def search_test_cases(
        self,
        query: str,
        limit: int = DEFAULT_LIMIT,
        framework_filter: Optional[List[str]] = None,
    ) -> RetrievedContext:
        """Semantic search over test cases."""
        vector = self._embedder.embed_one(query)
        qdrant_filter = self._build_framework_filter(framework_filter)
        hits = search_collection(Collections.TEST_CASES, vector, limit=limit, filters=qdrant_filter)

        id_score_map = {h.payload["artifact_id"]: h.score for h in hits}

        with get_session() as session:
            tcs = self._fetch_test_cases_by_ids(session, list(id_score_map.keys()))
            results = [
                test_case_to_result(tc, score=id_score_map.get(tc.id), framework_name=tc.framework.name)
                for tc in tcs
            ]

        results.sort(key=lambda r: r.similarity_score or 0, reverse=True)
        return RetrievedContext(
            query=query,
            artifact_type="test_case",
            test_cases=results,
            framework_filter=framework_filter,
            total_hits=len(hits),
        )

    def search_scenarios(
        self,
        query: str,
        limit: int = DEFAULT_LIMIT,
        framework_filter: Optional[List[str]] = None,
    ) -> RetrievedContext:
        """Semantic search over risk scenarios."""
        vector = self._embedder.embed_one(query)
        qdrant_filter = self._build_framework_filter(framework_filter)
        hits = search_collection(Collections.SCENARIOS, vector, limit=limit, filters=qdrant_filter)

        id_score_map = {h.payload["artifact_id"]: h.score for h in hits}

        with get_session() as session:
            scenarios = self._fetch_scenarios_by_ids(session, list(id_score_map.keys()))
            results = [
                scenario_to_result(sc, score=id_score_map.get(sc.id), framework_name=sc.framework.name)
                for sc in scenarios
            ]

        results.sort(key=lambda r: r.similarity_score or 0, reverse=True)
        return RetrievedContext(
            query=query,
            artifact_type="scenario",
            scenarios=results,
            framework_filter=framework_filter,
            total_hits=len(hits),
        )

    def search_all(
        self,
        query: str,
        limit_per_collection: int = 5,
        framework_filter: Optional[List[str]] = None,
    ) -> RetrievedContext:
        """
        Search all collections simultaneously and merge results.
        Uses a single embedding computation shared across all five searches.
        Results are ordered by score within each artifact type.
        """
        vector = self._embedder.embed_one(query)
        qdrant_filter = self._build_framework_filter(framework_filter)

        # Fan out to all collections in parallel using the pre-computed vector
        ctrl_hits = search_collection(Collections.CONTROLS, vector, limit=limit_per_collection, filters=qdrant_filter)
        req_hits = search_collection(Collections.REQUIREMENTS, vector, limit=limit_per_collection, filters=qdrant_filter)
        risk_hits = search_collection(Collections.RISKS, vector, limit=limit_per_collection, filters=qdrant_filter)
        tc_hits = search_collection(Collections.TEST_CASES, vector, limit=limit_per_collection, filters=qdrant_filter)
        sc_hits = search_collection(Collections.SCENARIOS, vector, limit=limit_per_collection, filters=qdrant_filter)

        with get_session() as session:
            controls = self._hydrate_controls(session, ctrl_hits)
            requirements = self._hydrate_requirements(session, req_hits)
            risks = self._hydrate_risks(session, risk_hits)
            test_cases = self._hydrate_test_cases(session, tc_hits)
            scenarios = self._hydrate_scenarios(session, sc_hits)

        total = len(ctrl_hits) + len(req_hits) + len(risk_hits) + len(tc_hits) + len(sc_hits)
        return RetrievedContext(
            query=query,
            artifact_type="multi",
            controls=controls,
            requirements=requirements,
            risks=risks,
            test_cases=test_cases,
            scenarios=scenarios,
            framework_filter=framework_filter,
            total_hits=total,
        )

    # ===========================================================================
    # Direct lookup methods — skip Qdrant, go straight to Postgres hierarchy
    # ===========================================================================

    def get_control_context(
        self,
        control_id: str,
        include_cross_framework: bool = True,
    ) -> RetrievedContext:
        """
        Fetch the full hierarchy context for a known control ID.

        Loads:
          - The control itself
          - Risks it mitigates (via risk_controls bridge)
          - Requirements it satisfies (via requirement_controls bridge)
          - Test cases linked to this control's risks
          - Cross-framework mappings (source and target)
        """
        with get_session() as session:
            ctrl = session.execute(
                select(Control)
                .options(
                    joinedload(Control.framework),
                    selectinload(Control.risk_controls).joinedload(RiskControl.risk)
                        .selectinload(Risk.test_cases),
                    selectinload(Control.requirement_controls).joinedload(RequirementControl.requirement)
                        .joinedload(Requirement.framework),
                )
                .where(Control.id == control_id)
            ).scalars().first()

            if not ctrl:
                return RetrievedContext(
                    query=control_id,
                    artifact_type="control",
                    warnings=[f"Control '{control_id}' not found."],
                )

            result = control_to_result(ctrl, framework_name=ctrl.framework.name)

            # Mitigated risks
            result.mitigated_risks = [
                risk_to_result(rc.risk, framework_name=rc.risk.framework.name)
                for rc in ctrl.risk_controls
                if rc.risk
            ]
            for risk_result in result.mitigated_risks:
                risk_obj = next(
                    (rc.risk for rc in ctrl.risk_controls if rc.risk and rc.risk.id == risk_result.id), None
                )
                if risk_obj:
                    risk_result.test_cases = [
                        test_case_to_result(tc, framework_name=ctrl.framework.name)
                        for tc in risk_obj.test_cases
                    ]

            # Satisfied requirements
            result.satisfied_requirements = [
                requirement_to_result(rc.requirement, framework_name=rc.requirement.framework.name)
                for rc in ctrl.requirement_controls
                if rc.requirement
            ]

            # All test cases from mitigated risks (deduplicated)
            all_tc_ids = set()
            for risk_r in result.mitigated_risks:
                for tc in risk_r.test_cases:
                    if tc.id not in all_tc_ids:
                        result.related_test_cases.append(tc)
                        all_tc_ids.add(tc.id)

            # Cross-framework mappings
            if include_cross_framework:
                result.cross_framework_mappings = self._fetch_cross_framework_mappings(
                    session, control_id
                )

        return RetrievedContext(
            query=control_id,
            artifact_type="control",
            controls=[result],
            total_hits=1,
        )

    def get_risk_context(self, risk_id: str) -> RetrievedContext:
        """
        Fetch the full hierarchy context for a known risk ID.

        Loads:
          - The risk itself
          - All mitigating controls
          - All test cases for this risk
        """
        with get_session() as session:
            risk = session.execute(
                select(Risk)
                .options(
                    joinedload(Risk.framework),
                    selectinload(Risk.risk_controls).joinedload(RiskControl.control)
                        .joinedload(Control.framework),
                    selectinload(Risk.test_cases),
                )
                .where(Risk.id == risk_id)
            ).scalars().first()

            if not risk:
                return RetrievedContext(
                    query=risk_id,
                    artifact_type="risk",
                    warnings=[f"Risk '{risk_id}' not found."],
                )

            result = risk_to_result(risk, framework_name=risk.framework.name)
            result.mitigating_controls = [
                control_to_result(rc.control, framework_name=rc.control.framework.name)
                for rc in risk.risk_controls
                if rc.control
            ]
            result.test_cases = [
                test_case_to_result(tc, framework_name=risk.framework.name)
                for tc in risk.test_cases
            ]

        return RetrievedContext(
            query=risk_id,
            artifact_type="risk",
            risks=[result],
            total_hits=1,
        )

    def get_requirement_context(self, requirement_id: str) -> RetrievedContext:
        """
        Fetch a requirement and all controls that satisfy it.
        """
        with get_session() as session:
            req = session.execute(
                select(Requirement)
                .options(
                    joinedload(Requirement.framework),
                    selectinload(Requirement.requirement_controls)
                        .joinedload(RequirementControl.control)
                        .joinedload(Control.framework),
                )
                .where(Requirement.id == requirement_id)
            ).scalars().first()

            if not req:
                return RetrievedContext(
                    query=requirement_id,
                    artifact_type="requirement",
                    warnings=[f"Requirement '{requirement_id}' not found."],
                )

            result = requirement_to_result(req, framework_name=req.framework.name)
            result.satisfying_controls = [
                control_to_result(rc.control, framework_name=rc.control.framework.name)
                for rc in req.requirement_controls
                if rc.control
            ]

        return RetrievedContext(
            query=requirement_id,
            artifact_type="requirement",
            requirements=[result],
            total_hits=1,
        )

    # ===========================================================================
    # Risk-Control Mapping Search
    # ===========================================================================

    def search_risk_control_mappings(
        self,
        query: str,
        limit: int = DEFAULT_LIMIT,
        framework_filter: Optional[List[str]] = None,
        search_by: str = "risk",  # "risk" or "control"
    ) -> RetrievedContext:
        """
        Search for risk-control mappings by querying either risks or controls.
        
        Args:
            query: Natural language query (e.g., "data breach", "access control")
            limit: Max results to return
            framework_filter: Restrict to specific framework IDs
            search_by: "risk" to search risks and return their controls,
                      "control" to search controls and return their risks
        
        Returns:
            RetrievedContext with risks and controls populated based on mappings
        """
        if search_by == "risk":
            # Search risks, then fetch their controls
            vector = self._embedder.embed_one(query)
            qdrant_filter = self._build_framework_filter(framework_filter)
            hits = search_collection(Collections.RISKS, vector, limit=limit, filters=qdrant_filter)
            
            id_score_map = {h.payload["artifact_id"]: h.score for h in hits}
            
            with get_session() as session:
                risks = session.execute(
                    select(Risk)
                    .options(
                        joinedload(Risk.framework),
                        selectinload(Risk.risk_controls).joinedload(RiskControl.control)
                            .joinedload(Control.framework),
                    )
                    .where(Risk.id.in_(list(id_score_map.keys())))
                ).scalars().all()
                
                risk_results = []
                control_results = []
                control_ids_seen = set()
                
                for risk in risks:
                    risk_result = risk_to_result(
                        risk,
                        score=id_score_map.get(risk.id),
                        framework_name=risk.framework.name
                    )
                    # Get mitigating controls
                    risk_result.mitigating_controls = [
                        control_to_result(rc.control, framework_name=rc.control.framework.name)
                        for rc in risk.risk_controls
                        if rc.control
                    ]
                    risk_results.append(risk_result)
                    
                    # Collect unique controls
                    for rc in risk.risk_controls:
                        if rc.control and rc.control.id not in control_ids_seen:
                            control_results.append(
                                control_to_result(rc.control, framework_name=rc.control.framework.name)
                            )
                            control_ids_seen.add(rc.control.id)
                
                return RetrievedContext(
                    query=query,
                    artifact_type="risk_control_mapping",
                    risks=risk_results,
                    controls=control_results,
                    total_hits=len(risk_results),
                    framework_filter=framework_filter,
                )
        
        else:  # search_by == "control"
            # Search controls, then fetch their risks
            vector = self._embedder.embed_one(query)
            qdrant_filter = self._build_framework_filter(framework_filter)
            hits = search_collection(Collections.CONTROLS, vector, limit=limit, filters=qdrant_filter)
            
            id_score_map = {h.payload["artifact_id"]: h.score for h in hits}
            
            with get_session() as session:
                controls = session.execute(
                    select(Control)
                    .options(
                        joinedload(Control.framework),
                        selectinload(Control.risk_controls).joinedload(RiskControl.risk)
                            .joinedload(Risk.framework),
                    )
                    .where(Control.id.in_(list(id_score_map.keys())))
                ).scalars().all()
                
                control_results = []
                risk_results = []
                risk_ids_seen = set()
                
                for ctrl in controls:
                    control_result = control_to_result(
                        ctrl,
                        score=id_score_map.get(ctrl.id),
                        framework_name=ctrl.framework.name
                    )
                    # Get mitigated risks
                    control_result.mitigated_risks = [
                        risk_to_result(rc.risk, framework_name=rc.risk.framework.name)
                        for rc in ctrl.risk_controls
                        if rc.risk
                    ]
                    control_results.append(control_result)
                    
                    # Collect unique risks
                    for rc in ctrl.risk_controls:
                        if rc.risk and rc.risk.id not in risk_ids_seen:
                            risk_results.append(
                                risk_to_result(rc.risk, framework_name=rc.risk.framework.name)
                            )
                            risk_ids_seen.add(rc.risk.id)
                
                return RetrievedContext(
                    query=query,
                    artifact_type="risk_control_mapping",
                    controls=control_results,
                    risks=risk_results,
                    total_hits=len(control_results),
                    framework_filter=framework_filter,
                )

    # ===========================================================================
    # Cross-framework lookup
    # ===========================================================================

    def get_cross_framework_equivalents(
        self,
        control_id: str,
        target_frameworks: Optional[List[str]] = None,
        resolved_only: bool = False,
    ) -> RetrievedContext:
        """
        Given a control ID, find all mapped controls in other frameworks.

        Args:
            control_id: Postgres control primary key.
            target_frameworks: Restrict to specific target framework IDs.
                               None = return all frameworks.
            resolved_only: If True, only return mappings where target_control_id
                           has been resolved (i.e. the target control exists in DB).
        """
        with get_session() as session:
            stmt = (
                select(CrossFrameworkMapping)
                .options(
                    joinedload(CrossFrameworkMapping.source_control)
                        .joinedload(Control.framework),
                    joinedload(CrossFrameworkMapping.target_control)
                        .joinedload(Control.framework),
                )
                .where(CrossFrameworkMapping.source_control_id == control_id)
            )

            if target_frameworks:
                stmt = stmt.where(
                    CrossFrameworkMapping.target_framework_id.in_(target_frameworks)
                )
            if resolved_only:
                stmt = stmt.where(CrossFrameworkMapping.target_control_id.isnot(None))

            mappings = session.execute(stmt).scalars().all()

            results = []
            warnings = []
            for mapping in mappings:
                r = cross_framework_mapping_to_result(mapping)
                # Hydrate target control if resolved
                if mapping.target_control:
                    r.target_control = control_to_result(
                        mapping.target_control,
                        framework_name=mapping.target_control.framework.name,
                    )
                elif mapping.target_raw_code:
                    warnings.append(
                        f"Unresolved mapping: {control_id} → "
                        f"{mapping.target_framework_id}/'{mapping.target_raw_code}'"
                    )
                results.append(r)

        if not results:
            warnings.append(f"No cross-framework mappings found for control '{control_id}'.")

        return RetrievedContext(
            query=control_id,
            artifact_type="cross_framework",
            cross_framework_mappings=results,
            framework_filter=target_frameworks,
            total_hits=len(results),
            warnings=warnings,
        )

    def get_framework_summary(self, framework_id: str) -> Dict:
        """
        Return counts of all artifacts for a framework.
        Useful for agents building gap analysis context.
        """
        with get_session() as session:
            fw = session.get(Framework, framework_id)
            if not fw:
                return {"error": f"Framework '{framework_id}' not found."}

            from sqlalchemy import func
            counts = {}
            for model, label in [
                (Control, "controls"),
                (Requirement, "requirements"),
                (Risk, "risks"),
                (TestCase, "test_cases"),
                (Scenario, "scenarios"),
            ]:
                n = session.execute(
                    select(func.count(model.id)).where(model.framework_id == framework_id)
                ).scalar()
                counts[label] = n

            return {
                "framework_id": fw.id,
                "name": fw.name,
                "version": fw.version,
                "counts": counts,
            }

    def list_frameworks(self) -> List[Dict]:
        """Return all ingested frameworks with their artifact counts."""
        with get_session() as session:
            frameworks = session.execute(select(Framework)).scalars().all()
            return [
                {
                    "id": fw.id,
                    "name": fw.name,
                    "version": fw.version,
                    "description": fw.description,
                }
                for fw in frameworks
            ]

    # ===========================================================================
    # Private helpers
    # ===========================================================================

    # --- Qdrant filter builder ---

    @staticmethod
    def _build_framework_filter(
        framework_filter: Optional[List[str]],
    ) -> Optional[qmodels.Filter]:
        if not framework_filter:
            return None
        return qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="framework_id",
                    match=qmodels.MatchAny(any=framework_filter),
                )
            ]
        )

    # --- Postgres fetchers by ID list ---

    @staticmethod
    def _fetch_controls_by_ids(
        session: Session, ids: List[str], with_relationships: bool = False
    ) -> List[Control]:
        if not ids:
            return []
        stmt = select(Control).where(Control.id.in_(ids))
        if with_relationships:
            stmt = stmt.options(
                joinedload(Control.framework),
                selectinload(Control.risk_controls).joinedload(RiskControl.risk),
                selectinload(Control.requirement_controls).joinedload(RequirementControl.requirement)
                    .joinedload(Requirement.framework),
            )
        else:
            stmt = stmt.options(joinedload(Control.framework))
        return session.execute(stmt).scalars().all()

    @staticmethod
    def _fetch_requirements_by_ids(
        session: Session, ids: List[str], with_relationships: bool = False
    ) -> List[Requirement]:
        if not ids:
            return []
        stmt = select(Requirement).where(Requirement.id.in_(ids))
        if with_relationships:
            stmt = stmt.options(
                joinedload(Requirement.framework),
                selectinload(Requirement.requirement_controls).joinedload(RequirementControl.control)
                    .joinedload(Control.framework),
            )
        else:
            stmt = stmt.options(joinedload(Requirement.framework))
        return session.execute(stmt).scalars().all()

    @staticmethod
    def _fetch_risks_by_ids(
        session: Session, ids: List[str], with_relationships: bool = False
    ) -> List[Risk]:
        if not ids:
            return []
        stmt = select(Risk).where(Risk.id.in_(ids))
        if with_relationships:
            stmt = stmt.options(
                joinedload(Risk.framework),
                selectinload(Risk.risk_controls).joinedload(RiskControl.control)
                    .joinedload(Control.framework),
                selectinload(Risk.test_cases),
            )
        else:
            stmt = stmt.options(joinedload(Risk.framework))
        return session.execute(stmt).scalars().all()

    @staticmethod
    def _fetch_test_cases_by_ids(session: Session, ids: List[str]) -> List[TestCase]:
        if not ids:
            return []
        return session.execute(
            select(TestCase)
            .options(joinedload(TestCase.framework))
            .where(TestCase.id.in_(ids))
        ).scalars().all()

    @staticmethod
    def _fetch_scenarios_by_ids(session: Session, ids: List[str]) -> List[Scenario]:
        if not ids:
            return []
        return session.execute(
            select(Scenario)
            .options(joinedload(Scenario.framework))
            .where(Scenario.id.in_(ids))
        ).scalars().all()

    # --- Qdrant hit hydrators (for search_all) ---

    def _hydrate_controls(
        self, session: Session, hits: list
    ) -> List[ControlResult]:
        id_score = {h.payload["artifact_id"]: h.score for h in hits}
        rows = self._fetch_controls_by_ids(session, list(id_score.keys()))
        results = [
            control_to_result(c, score=id_score.get(c.id), framework_name=c.framework.name)
            for c in rows
        ]
        return sorted(results, key=lambda r: r.similarity_score or 0, reverse=True)

    def _hydrate_requirements(
        self, session: Session, hits: list
    ) -> List[RequirementResult]:
        id_score = {h.payload["artifact_id"]: h.score for h in hits}
        rows = self._fetch_requirements_by_ids(session, list(id_score.keys()))
        results = [
            requirement_to_result(r, score=id_score.get(r.id), framework_name=r.framework.name)
            for r in rows
        ]
        return sorted(results, key=lambda r: r.similarity_score or 0, reverse=True)

    def _hydrate_risks(
        self, session: Session, hits: list
    ) -> List[RiskResult]:
        id_score = {h.payload["artifact_id"]: h.score for h in hits}
        rows = self._fetch_risks_by_ids(session, list(id_score.keys()))
        results = [
            risk_to_result(r, score=id_score.get(r.id), framework_name=r.framework.name)
            for r in rows
        ]
        return sorted(results, key=lambda r: r.similarity_score or 0, reverse=True)

    def _hydrate_test_cases(
        self, session: Session, hits: list
    ) -> List[TestCaseResult]:
        id_score = {h.payload["artifact_id"]: h.score for h in hits}
        rows = self._fetch_test_cases_by_ids(session, list(id_score.keys()))
        results = [
            test_case_to_result(tc, score=id_score.get(tc.id), framework_name=tc.framework.name)
            for tc in rows
        ]
        return sorted(results, key=lambda r: r.similarity_score or 0, reverse=True)

    def _hydrate_scenarios(
        self, session: Session, hits: list
    ) -> List[ScenarioResult]:
        id_score = {h.payload["artifact_id"]: h.score for h in hits}
        rows = self._fetch_scenarios_by_ids(session, list(id_score.keys()))
        results = [
            scenario_to_result(sc, score=id_score.get(sc.id), framework_name=sc.framework.name)
            for sc in rows
        ]
        return sorted(results, key=lambda r: r.similarity_score or 0, reverse=True)

    # --- Shared context attachment ---

    @staticmethod
    def _attach_context(
        result: ControlResult,
        orm_ctrl: Control,
        session: Session,
        fetch_context: bool,
    ) -> ControlResult:
        """Populate relational fields on a ControlResult if fetch_context=True."""
        if not fetch_context:
            return result
        result.mitigated_risks = [
            risk_to_result(rc.risk, framework_name=rc.risk.framework.name)
            for rc in orm_ctrl.risk_controls if rc.risk
        ]
        result.satisfied_requirements = [
            requirement_to_result(rc.requirement, framework_name=rc.requirement.framework.name)
            for rc in orm_ctrl.requirement_controls if rc.requirement
        ]
        return result

    def _fetch_cross_framework_mappings(
        self, session: Session, control_id: str
    ) -> List[CrossFrameworkResult]:
        mappings = session.execute(
            select(CrossFrameworkMapping)
            .options(
                joinedload(CrossFrameworkMapping.source_control),
                joinedload(CrossFrameworkMapping.target_control).joinedload(Control.framework),
            )
            .where(CrossFrameworkMapping.source_control_id == control_id)
        ).scalars().all()

        results = []
        for m in mappings:
            r = cross_framework_mapping_to_result(m)
            if m.target_control:
                r.target_control = control_to_result(
                    m.target_control, framework_name=m.target_control.framework.name
                )
            results.append(r)
        return results
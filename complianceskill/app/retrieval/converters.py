"""
Converters from SQLAlchemy ORM rows → result dataclasses.

Each function takes an ORM model instance and an optional similarity score
(present when the record was found via vector search).

Keeping this separate from the service class means:
  1. The service stays focused on query logic.
  2. Converters are independently testable.
  3. Adding new fields to results only requires changes here.
"""

from typing import Optional, List

from app.ingestion.models import (
    Control, Requirement, Risk, TestCase, Scenario, CrossFrameworkMapping, Framework
)
from app.retrieval.results import (
    ControlResult, RequirementResult, RiskResult, TestCaseResult,
    ScenarioResult, CrossFrameworkResult,
)


def control_to_result(
    ctrl: Control,
    score: Optional[float] = None,
    framework_name: Optional[str] = None,
) -> ControlResult:
    fw_name = framework_name or (ctrl.framework.name if ctrl.framework else ctrl.framework_id)
    return ControlResult(
        id=ctrl.id,
        control_code=ctrl.control_code,
        framework_id=ctrl.framework_id,
        framework_name=fw_name,
        name=ctrl.name,
        description=ctrl.description,
        domain=ctrl.domain,
        control_type=ctrl.control_type,
        cis_control_id=ctrl.cis_control_id,
        similarity_score=score,
        metadata=ctrl.metadata_ or {},
    )


def requirement_to_result(
    req: Requirement,
    score: Optional[float] = None,
    framework_name: Optional[str] = None,
) -> RequirementResult:
    fw_name = framework_name or (req.framework.name if req.framework else req.framework_id)
    return RequirementResult(
        id=req.id,
        requirement_code=req.requirement_code,
        framework_id=req.framework_id,
        framework_name=fw_name,
        name=req.name,
        description=req.description,
        domain=req.domain,
        compliance_type=req.compliance_type,
        similarity_score=score,
        metadata=req.metadata_ or {},
    )


def risk_to_result(
    risk: Risk,
    score: Optional[float] = None,
    framework_name: Optional[str] = None,
) -> RiskResult:
    fw_name = framework_name or (risk.framework.name if risk.framework else risk.framework_id)
    return RiskResult(
        id=risk.id,
        risk_code=risk.risk_code,
        framework_id=risk.framework_id,
        framework_name=fw_name,
        name=risk.name,
        description=risk.description,
        asset=risk.asset,
        trigger=risk.trigger,
        loss_outcomes=risk.loss_outcomes or [],
        similarity_score=score,
        metadata=risk.metadata_ or {},
    )


def test_case_to_result(
    tc: TestCase,
    score: Optional[float] = None,
    framework_name: Optional[str] = None,
) -> TestCaseResult:
    fw_name = framework_name or (tc.framework.name if tc.framework else tc.framework_id)
    return TestCaseResult(
        id=tc.id,
        framework_id=tc.framework_id,
        framework_name=fw_name,
        name=tc.name,
        test_type=tc.test_type,
        objective=tc.objective,
        test_steps=tc.test_steps or [],
        expected_result=tc.expected_result,
        evidence_required=tc.evidence_required or [],
        success_criteria=tc.success_criteria or [],
        risk_id=tc.risk_id,
        control_id=tc.control_id,
        similarity_score=score,
        metadata=tc.metadata_ or {},
    )


def scenario_to_result(
    sc: Scenario,
    score: Optional[float] = None,
    framework_name: Optional[str] = None,
) -> ScenarioResult:
    fw_name = framework_name or (sc.framework.name if sc.framework else sc.framework_id)
    return ScenarioResult(
        id=sc.id,
        scenario_code=sc.scenario_code,
        framework_id=sc.framework_id,
        framework_name=fw_name,
        name=sc.name,
        description=sc.description,
        asset=sc.asset,
        trigger=sc.trigger,
        loss_outcomes=sc.loss_outcomes or [],
        similarity_score=score,
        metadata=sc.metadata_ or {},
    )


def cross_framework_mapping_to_result(
    mapping: CrossFrameworkMapping,
) -> CrossFrameworkResult:
    source_code = (
        mapping.source_control.control_code
        if mapping.source_control
        else mapping.source_control_id
    )
    target_code = (
        mapping.target_control.control_code
        if mapping.target_control
        else None
    )
    return CrossFrameworkResult(
        source_control_id=mapping.source_control_id,
        source_control_code=source_code,
        source_framework_id=mapping.source_framework_id,
        target_control_id=mapping.target_control_id,
        target_control_code=target_code,
        target_raw_code=mapping.target_raw_code,
        target_framework_id=mapping.target_framework_id,
        mapping_type=mapping.mapping_type,
        confidence_score=mapping.confidence_score,
        source=mapping.source,
    )
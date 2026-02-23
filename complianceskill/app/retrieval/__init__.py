"""
Retrieval layer — the interface between agents and the knowledge base.

Public exports:
  RetrievalService  — main query interface (semantic + relational)
  MDLRetrievalService — MDL collections retrieval (leen_db_schema, leen_table_description, etc.)
  XSOARRetrievalService — XSOAR enriched collection retrieval
  RetrievedContext  — typed result envelope agents consume
  ControlResult, RiskResult, RequirementResult, TestCaseResult,
  ScenarioResult, CrossFrameworkResult — individual artifact results
  MDLRetrievedContext, XSOARRetrievedContext — MDL/XSOAR result types
"""

from app.retrieval.service import RetrievalService
from app.retrieval.mdl_service import MDLRetrievalService
from app.retrieval.xsoar_service import XSOARRetrievalService
from app.retrieval.results import (
    RetrievedContext,
    ControlResult,
    RequirementResult,
    RiskResult,
    TestCaseResult,
    ScenarioResult,
    CrossFrameworkResult,
)
from app.retrieval.mdl_results import (
    MDLRetrievedContext,
    MDLSchemaResult,
    MDLTableDescriptionResult,
    MDLProjectMetaResult,
    MDLMetricResult,
)
from app.retrieval.xsoar_results import (
    XSOARRetrievedContext,
    XSOARPlaybookResult,
    XSOARDashboardResult,
    XSOARScriptResult,
    XSOARIntegrationResult,
)

__all__ = [
    "RetrievalService",
    "MDLRetrievalService",
    "XSOARRetrievalService",
    "RetrievedContext",
    "ControlResult",
    "RequirementResult",
    "RiskResult",
    "TestCaseResult",
    "ScenarioResult",
    "CrossFrameworkResult",
    "MDLRetrievedContext",
    "MDLSchemaResult",
    "MDLTableDescriptionResult",
    "MDLProjectMetaResult",
    "MDLMetricResult",
    "XSOARRetrievedContext",
    "XSOARPlaybookResult",
    "XSOARDashboardResult",
    "XSOARScriptResult",
    "XSOARIntegrationResult",
]
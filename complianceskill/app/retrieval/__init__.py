"""
Retrieval layer — the interface between agents and the knowledge base.

Public exports:
  RetrievalService  — main query interface (semantic + relational)
  MDLRetrievalService — MDL collections retrieval (leen_db_schema, leen_table_description, etc.)
  XSOARRetrievalService — XSOAR enriched collection retrieval
  DecisionTreeRetrievalService — Decision tree metrics and control taxonomy retrieval
  DashboardTemplateRetrievalService — Dashboard template retrieval (unified registry)
  RetrievedContext  — typed result envelope agents consume
  ControlResult, RiskResult, RequirementResult, TestCaseResult,
  ScenarioResult, CrossFrameworkResult — individual artifact results
  MDLRetrievedContext, XSOARRetrievedContext — MDL/XSOAR result types
  DecisionTreeRetrievedContext, MetricResult, ControlTaxonomyResult — Decision tree result types
  DashboardTemplateRetrievedContext, DashboardTemplateResult — Dashboard template result types
"""

from app.retrieval.service import RetrievalService
from app.retrieval.mdl_service import MDLRetrievalService
from app.retrieval.xsoar_service import XSOARRetrievalService
from app.retrieval.decision_tree_service import DecisionTreeRetrievalService
from app.dashboard_agent.dashboard_template_service import DashboardTemplateRetrievalService
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
from app.retrieval.decision_tree_results import (
    DecisionTreeRetrievedContext,
    MetricResult,
    ControlTaxonomyResult,
)
from app.dashboard_agent.dashboard_template_results import (
    DashboardTemplateRetrievedContext,
    DashboardTemplateResult,
)

__all__ = [
    "RetrievalService",
    "MDLRetrievalService",
    "XSOARRetrievalService",
    "DecisionTreeRetrievalService",
    "DashboardTemplateRetrievalService",
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
    "DecisionTreeRetrievedContext",
    "MetricResult",
    "ControlTaxonomyResult",
    "DashboardTemplateRetrievedContext",
    "DashboardTemplateResult",
]
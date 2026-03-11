"""
Cornerstone OnDemand (CSOD) Metrics, Tables, and KPIs Recommender Workflow

A workflow for recommending metrics, tables, and KPIs for Cornerstone/Workday integrations.
Similar architecture to DT workflow but focused on HR/learning management use cases.
"""

from .csod_metric_advisor_workflow import (
    build_csod_metric_advisor_workflow,
    create_csod_metric_advisor_app,
    get_csod_metric_advisor_app,
    create_csod_metric_advisor_initial_state,
    ADVISOR_INTENT,
)

__all__ = [
    "build_csod_metric_advisor_workflow",
    "create_csod_metric_advisor_app",
    "get_csod_metric_advisor_app",
    "create_csod_metric_advisor_initial_state",
    "ADVISOR_INTENT",
]

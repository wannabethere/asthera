"""
CSOD metric advisor workflow — entrypoint.

Graph + routing: app.agents.csod.workflows.csod_metric_advisor_graph,
app.agents.csod.workflows.csod_metric_advisor_routing.
"""
from app.agents.csod.workflows.csod_metric_advisor_graph import (
    ADVISOR_INTENT,
    build_csod_metric_advisor_workflow,
    create_csod_metric_advisor_app,
    create_csod_metric_advisor_initial_state,
    get_csod_metric_advisor_app,
)

__all__ = [
    "ADVISOR_INTENT",
    "build_csod_metric_advisor_workflow",
    "create_csod_metric_advisor_app",
    "create_csod_metric_advisor_initial_state",
    "get_csod_metric_advisor_app",
]

if __name__ == "__main__":
    _app = get_csod_metric_advisor_app()
    print("CSOD Metric Advisor workflow compiled successfully!")
    print(f"Nodes: {list(_app.nodes.keys())}")

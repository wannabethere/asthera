"""
CSOD main LangGraph workflow — entrypoint.

Implementation: app.agents.csod.workflows.csod_main_graph (graph) +
app.agents.csod.workflows.csod_main_routing (edges) +
app.agents.csod.workflows.csod_initial_state (defaults).
"""
from app.agents.csod.workflows.csod_initial_state import create_csod_initial_state
from app.agents.csod.workflows.csod_main_graph import (
    build_csod_workflow,
    create_csod_app,
    get_csod_app,
)

__all__ = [
    "build_csod_workflow",
    "create_csod_app",
    "create_csod_initial_state",
    "get_csod_app",
]

if __name__ == "__main__":
    _app = get_csod_app()
    print("CSOD workflow compiled successfully!")
    print(f"Nodes: {list(_app.nodes.keys())}")

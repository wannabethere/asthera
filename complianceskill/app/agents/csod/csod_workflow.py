"""
CSOD main LangGraph workflow — entrypoint.

Three app variants:
  - Full (monolith):  get_csod_app()         — backward compat, runs end-to-end
  - Phase 1 (split):  get_csod_phase1_app()  — stops at metric selection + SQL preview
  - Phase 2 (split):  get_csod_phase2_app()  — output format → assembly → narration

Implementation: app.agents.csod.workflows.csod_main_graph (graph) +
app.agents.csod.workflows.csod_main_routing (edges) +
app.agents.csod.workflows.csod_initial_state (defaults).
"""
from app.agents.csod.workflows.csod_initial_state import create_csod_initial_state
from app.agents.csod.workflows.csod_main_graph import (
    build_csod_workflow,
    create_csod_app,
    get_csod_app,
    build_csod_phase1_workflow,
    create_csod_phase1_app,
    get_csod_phase1_app,
    build_csod_phase2_workflow,
    create_csod_phase2_app,
    get_csod_phase2_app,
)

__all__ = [
    "build_csod_workflow",
    "create_csod_app",
    "create_csod_initial_state",
    "get_csod_app",
    # Phase 1/2 split
    "build_csod_phase1_workflow",
    "create_csod_phase1_app",
    "get_csod_phase1_app",
    "build_csod_phase2_workflow",
    "create_csod_phase2_app",
    "get_csod_phase2_app",
]

if __name__ == "__main__":
    _app = get_csod_app()
    print("CSOD full workflow compiled successfully!")
    print(f"  Nodes: {list(_app.nodes.keys())}")

    _p1 = get_csod_phase1_app()
    print("CSOD Phase 1 workflow compiled successfully!")
    print(f"  Nodes: {list(_p1.nodes.keys())}")

    _p2 = get_csod_phase2_app()
    print("CSOD Phase 2 workflow compiled successfully!")
    print(f"  Nodes: {list(_p2.nodes.keys())}")

"""
CSOD main LangGraph workflow — entrypoint.

Three app variants:
  - Full (monolith):  get_csod_app()            — backward compat, runs end-to-end
  - Phase 1 (split):  get_csod_phase1_app()     — stops at metric selection + SQL preview
  - Output (deploy):  get_csod_output_app()     — goal_intent → gold models → CubeJS → scheduler → assembler

Implementation: app.agents.csod.workflows.csod_main_graph (monolith + phase1) +
app.agents.csod.workflows.csod_output_graph (output/deploy) +
app.agents.csod.workflows.csod_main_routing (edges) +
app.agents.csod.workflows.csod_initial_state (defaults).
"""
from app.agents.csod.workflows.csod_initial_state import create_csod_initial_state
from app.agents.csod.workflows.csod_main_graph import (
    build_csod_workflow,
    create_csod_app,
    create_csod_interactive_app,
    get_csod_app,
    get_csod_interactive_app,
    build_csod_phase1_workflow,
    create_csod_phase1_app,
    get_csod_phase1_app,
    # Backward-compat aliases (delegate to csod_output_graph)
    build_csod_phase2_workflow,
    create_csod_phase2_app,
    get_csod_phase2_app,
)
from app.agents.csod.workflows.csod_output_graph import (
    build_csod_output_workflow,
    create_csod_output_app,
    get_csod_output_app,
)

__all__ = [
    "build_csod_workflow",
    "create_csod_app",
    "create_csod_interactive_app",
    "create_csod_initial_state",
    "get_csod_app",
    "get_csod_interactive_app",
    # Phase 1 (analysis + preview)
    "build_csod_phase1_workflow",
    "create_csod_phase1_app",
    "get_csod_phase1_app",
    # Output graph (deploy-time)
    "build_csod_output_workflow",
    "create_csod_output_app",
    "get_csod_output_app",
    # Deprecated Phase 2 aliases → output graph
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

    _out = get_csod_output_app()
    print("CSOD Output workflow compiled successfully!")
    print(f"  Nodes: {list(_out.nodes.keys())}")

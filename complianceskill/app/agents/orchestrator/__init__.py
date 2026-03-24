"""
Security Orchestrator — top-level workflow that dispatches subtasks
to CSOD (data analysis) and DT (detection/triage) sub-graph workflows.

Architecture:
  User Request
    ↓
  security_request_classifier    — What kind of request is this?
    ↓
  capability_router              — What capabilities are needed?
    ↓
  hybrid_plan_builder            — Break into subtasks
    ↓
  subtask_dispatcher             — Route subtasks to sub-graphs
    ├── analysis subtasks → CSOD data analysis workflow
    ├── detection subtasks → DT detection workflow (with/without MDL)
    ↓
  subtask_result_merger          — Combine results from both workflows
    ↓
  final_detection_artifact_assembler
    ↓
  final_validation
    ↓
  completion_narration → END
"""
from app.agents.orchestrator.orchestrator_graph import (
    build_orchestrator_workflow,
    create_orchestrator_app,
    get_orchestrator_app,
)

__all__ = [
    "build_orchestrator_workflow",
    "create_orchestrator_app",
    "get_orchestrator_app",
]

"""
Orchestrator State Schema — defines the state for the top-level orchestrator
that dispatches subtasks to CSOD and DT sub-graph workflows.
"""
from typing import TypedDict, List, Dict, Optional, Any, Literal


class Subtask(TypedDict, total=False):
    """A single subtask produced by the hybrid plan builder."""
    subtask_id: str
    subtask_type: str  # "analysis" | "detection" | "triage" | "dashboard"
    target_workflow: str  # "csod" | "dt"
    description: str
    priority: int  # 1 = highest
    depends_on: List[str]  # subtask_ids this depends on

    # Input context for the sub-graph
    user_query: str  # Rewritten query scoped to this subtask
    intent_hint: Optional[str]  # Suggested intent for the sub-graph classifier
    focus_areas: List[str]
    framework_id: Optional[str]
    requirement_code: Optional[str]

    # Execution state
    status: str  # "pending" | "dispatched" | "completed" | "failed"
    result: Optional[Dict[str, Any]]  # Sub-graph output after completion
    error: Optional[str]


class OrchestratorState(TypedDict, total=False):
    """
    State for the top-level security orchestrator workflow.

    This is the parent graph's state. Sub-graphs (CSOD, DT) have their own
    state schemas — the orchestrator passes input/output through Subtask dicts.
    """
    # ── Input ─────────────────────────────────────────────────────────────
    user_query: str
    messages: List[Any]
    thread_id: Optional[str]
    run_id: Optional[str]

    # Context from conversation layer (if available)
    compliance_profile: Optional[Dict[str, Any]]
    selected_data_sources: List[str]
    active_project_id: Optional[str]

    # ── Stage 1: Classification ───────────────────────────────────────────
    request_classification: Optional[Dict[str, Any]]
    # {
    #   "request_type": "detection_only" | "analysis_only" | "hybrid" | "dashboard",
    #   "confidence": 0.92,
    #   "primary_domain": "security" | "lms",
    #   "framework_signals": ["SOC2", "HIPAA", ...],
    #   "analysis_signals": ["gap", "metrics", "dashboard", ...],
    #   "detection_signals": ["siem", "rule", "playbook", "alert", ...],
    # }

    # ── Stage 2: Capability routing ───────────────────────────────────────
    capabilities_needed: Optional[Dict[str, Any]]
    # {
    #   "needs_data_analysis": bool,
    #   "needs_detection_engineering": bool,
    #   "needs_dashboard": bool,
    #   "has_data_sources": bool,       # Are MDL schemas available?
    #   "has_framework_context": bool,  # Is a framework KB available?
    #   "dt_mode": "with_mdl" | "no_mdl",  # DT retrieval mode
    # }

    # ── Stage 3: Hybrid plan ─────────────────────────────────────────────
    subtasks: List[Subtask]
    execution_order: List[str]  # Ordered subtask_ids respecting dependencies

    # ── Stage 4: Dispatch results ─────────────────────────────────────────
    csod_results: Optional[Dict[str, Any]]  # Aggregated CSOD sub-graph outputs
    dt_results: Optional[Dict[str, Any]]    # Aggregated DT sub-graph outputs

    # ── Stage 5: Final assembly ───────────────────────────────────────────
    merged_results: Optional[Dict[str, Any]]
    final_artifacts: Optional[Dict[str, Any]]
    # {
    #   "playbook": {...},               # DT playbook (if detection subtasks)
    #   "siem_rules": [...],             # SIEM rules (if detection subtasks)
    #   "metric_recommendations": [...], # CSOD metrics (if analysis subtasks)
    #   "dashboard": {...},              # Dashboard spec (if dashboard subtasks)
    #   "medallion_plan": {...},         # Gold layer plan (if analysis subtasks)
    #   "data_analysis_context": {...},  # Hand-off context from DT for further CSOD work
    # }

    validation_result: Optional[Dict[str, Any]]
    completion_narration: Optional[str]

    # ── Orchestrator metadata ─────────────────────────────────────────────
    orchestrator_narrative_stream: List[Dict[str, Any]]
    execution_steps: List[Dict[str, Any]]
    error: Optional[str]

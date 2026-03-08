"""
Centralized prompt storage under app/agents/prompt_utils/.

Subdirectories:
- base: Default prompts for nodes, calculation_planner, dt fallbacks
- mdl: DT workflow prompts (detection triage, dashboard, etc.)
- decision_trees: Decision tree generation prompts
- csod: CSOD workflow prompts
"""
from app.agents.prompt_loader import (
    load_prompt,
    get_prompt_path,
    PROMPTS_BASE,
    PROMPTS_MDL,
    PROMPTS_DECISION_TREES,
    PROMPTS_CSOD,
)

__all__ = [
    "load_prompt",
    "get_prompt_path",
    "PROMPTS_BASE",
    "PROMPTS_MDL",
    "PROMPTS_DECISION_TREES",
    "PROMPTS_CSOD",
]

"""
Skill Recommender Node — Phase 3 of the skill pipeline.

This node runs *before* (or wraps) the existing metrics recommender.
It injects skill-specific instructions and context into the recommender
prompt so that metric recommendations are framed for the active skill.

If ``skill_context`` is None, this node is a pass-through.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.agents.skills import SkillRegistry
from app.agents.skills.nodes.skill_intent_node import SKILL_CONTEXT_KEY, SKILL_DATA_PLAN_KEY

logger = logging.getLogger(__name__)

# State key where skill-injected recommender instructions are stored.
# The existing metrics_recommender node reads this to augment its prompt.
SKILL_RECOMMENDER_CONTEXT_KEY = "skill_recommender_context"


def skill_recommender_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase 3: Prepare skill-specific recommender instructions.

    This node does NOT replace the existing metrics recommender — it builds
    a ``skill_recommender_context`` dict that the recommender node reads to
    augment its prompt with skill-specific framing, selection biases, and
    output field requirements.

    Reads:
        - skill_context (from Phase 1)
        - skill_data_plan (from Phase 2)

    Writes:
        - skill_recommender_context: {
              skill_block: str (markdown block for prompt injection),
              metric_instructions: str (from skill prompt),
              data_plan: dict (from Phase 2),
              framing: str,
              output_guidance: str,
              causal_usage: str,
          }

    The existing ``csod_metrics_recommender`` / DT recommender checks for
    ``skill_recommender_context`` in state and, if present, appends the
    skill block + metric instructions to its system prompt.
    """
    skill_context = state.get(SKILL_CONTEXT_KEY)

    if not skill_context or not skill_context.get("confirmed", False):
        state[SKILL_RECOMMENDER_CONTEXT_KEY] = None
        return state

    skill_id = skill_context["skill_id"]
    registry = SkillRegistry.instance()
    skill = registry.get(skill_id)

    if not skill:
        state[SKILL_RECOMMENDER_CONTEXT_KEY] = None
        return state

    # Build the recommender context (including domain config)
    domain_block = ""
    try:
        from app.agents.domain_config import DomainRegistry
        domain_cfg = DomainRegistry.instance().get_for_state(state)
        domain_block = (
            f"\n### Domain Context: {domain_cfg.display_name}\n"
            f"- **Focus areas:** {', '.join(domain_cfg.focus_area_category_map.keys()) or 'any'}\n"
            f"- **Data sources:** {', '.join(domain_cfg.data_sources) or 'any'}\n"
        )
    except Exception:
        pass

    ctx: Dict[str, Any] = {
        "skill_id": skill_id,
        "skill_block": skill.build_skill_context_block() + domain_block,
        "metric_instructions": skill.get_prompt("metric_instructions") or "",
        "data_plan": state.get(SKILL_DATA_PLAN_KEY),
        "framing": skill.recommender_instructions.framing,
        "metric_selection_bias": skill.recommender_instructions.metric_selection_bias,
        "output_guidance": skill.recommender_instructions.output_guidance,
        "causal_usage": skill.recommender_instructions.causal_usage,
        "extracted_params": skill_context.get("extracted_params", {}),
        "domain_id": skill_context.get("domain_id", "lms"),
    }

    state[SKILL_RECOMMENDER_CONTEXT_KEY] = ctx

    _log_skill_step(state, "skill_recommender_prep", skill_id, ctx)

    return state


def get_skill_augmented_prompt(
    base_prompt: str,
    state: Dict[str, Any],
) -> str:
    """
    Utility for the existing metrics recommender to call.

    If ``skill_recommender_context`` is set, appends the skill context block
    and metric_instructions to the base prompt.  Otherwise returns the base
    prompt unchanged.

    Usage in existing ``csod_metrics_recommender_node``::

        from app.agents.skills.nodes.skill_recommender_node import get_skill_augmented_prompt
        prompt_text = get_skill_augmented_prompt(prompt_text, state)
    """
    ctx = state.get(SKILL_RECOMMENDER_CONTEXT_KEY)
    if not ctx:
        return base_prompt

    parts = [base_prompt]

    skill_block = ctx.get("skill_block", "")
    if skill_block:
        parts.append("\n\n---\n\n")
        parts.append(skill_block)

    metric_instructions = ctx.get("metric_instructions", "")
    if metric_instructions:
        parts.append("\n\n---\n\n")
        parts.append(metric_instructions)

    # Add extracted parameters as context
    params = ctx.get("extracted_params", {})
    if params:
        parts.append("\n\n### Skill-Extracted Parameters\n")
        for k, v in params.items():
            parts.append(f"- **{k}:** {v}")

    return "\n".join(parts)


def _log_skill_step(state: Dict[str, Any], step_name: str, skill_id: str, ctx: Dict) -> None:
    from datetime import datetime
    if "execution_steps" not in state:
        state["execution_steps"] = []
    state["execution_steps"].append({
        "step_name": step_name,
        "agent_name": f"skill:{skill_id}",
        "timestamp": datetime.utcnow().isoformat(),
        "status": "completed",
        "inputs": {"skill_id": skill_id},
        "outputs": {
            "has_instructions": bool(ctx.get("metric_instructions")),
            "framing": ctx.get("framing", ""),
        },
    })

"""
Skill Intent Identifier Node — Phase 1 of the skill pipeline.

Runs *after* the main intent classifier (csod or dt).  Resolves the matching
skill definition and extracts skill-specific parameters from the user query.

If no skill definition exists for the classified intent, this node is a
transparent pass-through — the traditional workflow continues unchanged.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from langchain_core.prompts import ChatPromptTemplate

from app.core.dependencies import get_llm
from app.agents.skills import SkillRegistry

logger = logging.getLogger(__name__)

# State key where the active skill's context is stored
SKILL_CONTEXT_KEY = "skill_context"
SKILL_DATA_PLAN_KEY = "skill_data_plan"


def _get_intent_key(state: Dict[str, Any]) -> str:
    """Determine which state key holds the classified intent (csod vs dt)."""
    if state.get("csod_intent"):
        return "csod_intent"
    if state.get("intent"):
        return "intent"
    return "csod_intent"


def skill_intent_identifier_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase 1: Resolve the analysis skill and extract skill-specific parameters.

    Reads:
        - csod_intent / intent (classified pipeline intent)
        - user_query
        - skill_pipeline_enabled (feature flag, default False)

    Writes:
        - skill_context: {skill_id, confirmed, extracted_params, analysis_requirements, ...}

    If the feature flag is disabled or no skill exists for the intent, sets
    ``skill_context`` to ``None`` — downstream nodes check this to decide
    whether to apply skill-specific logic or fall through to traditional path.
    """
    # Feature flag check
    if not state.get("skill_pipeline_enabled", False):
        state[SKILL_CONTEXT_KEY] = None
        return state

    intent_key = _get_intent_key(state)
    intent = state.get(intent_key)
    user_query = state.get("user_query", "")

    if not intent:
        state[SKILL_CONTEXT_KEY] = None
        return state

    # Resolve skill from registry
    registry = SkillRegistry.instance()
    skill = registry.resolve_skill_for_intent(intent)

    if not skill:
        logger.debug("No skill definition for intent '%s' — pass-through", intent)
        state[SKILL_CONTEXT_KEY] = None
        return state

    # Check workflow compatibility
    workflow = "csod" if intent_key == "csod_intent" else "dt"
    if workflow not in skill.workflows:
        logger.debug("Skill '%s' not available for workflow '%s' — pass-through", skill.skill_id, workflow)
        state[SKILL_CONTEXT_KEY] = None
        return state

    # Check domain compatibility (if skill is domain-locked)
    if skill.domain:
        active_domain = state.get("primary_domain", "lms")
        if skill.domain != active_domain:
            logger.debug("Skill '%s' locked to domain '%s', active is '%s' — pass-through", skill.skill_id, skill.domain, active_domain)
            state[SKILL_CONTEXT_KEY] = None
            return state

    # Load the skill's intent_identifier prompt
    prompt_text = skill.get_prompt("intent_identifier")

    if prompt_text:
        # LLM-based extraction
        try:
            skill_context = _invoke_skill_intent_llm(prompt_text, user_query, skill, state)
        except Exception:
            logger.warning("Skill intent LLM failed for '%s' — using defaults", skill.skill_id, exc_info=True)
            skill_context = _default_skill_context(skill)
    else:
        # No prompt file — use declarative defaults from skill definition
        skill_context = _default_skill_context(skill)

    # Enrich with domain config context
    try:
        from app.agents.domain_config import DomainRegistry
        domain_cfg = DomainRegistry.instance().get_for_state(state)
        skill_context["domain_id"] = domain_cfg.domain_id
        skill_context["domain_display_name"] = domain_cfg.display_name
        skill_context["state_key_prefix"] = domain_cfg.state_key_prefix
    except Exception:
        skill_context.setdefault("domain_id", "lms")

    state[SKILL_CONTEXT_KEY] = skill_context

    # Log the step
    _log_skill_step(state, "skill_intent_identifier", skill.skill_id, skill_context)

    return state


def _invoke_skill_intent_llm(
    prompt_text: str,
    user_query: str,
    skill: Any,
    state: Dict[str, Any],
) -> Dict[str, Any]:
    """Run the skill's intent_identifier prompt through LLM."""
    llm = get_llm(temperature=0)

    prompt = ChatPromptTemplate.from_messages([
        ("system", prompt_text.replace("{", "{{").replace("}", "}}")),
        ("human", "{input}"),
    ])

    # Build human message with query + context
    human_msg = f"User query: {user_query}"
    compliance_profile = state.get("compliance_profile", {})
    if compliance_profile:
        filters = []
        for k in ("time_window", "org_unit", "training_type", "persona"):
            v = compliance_profile.get(k)
            if v:
                filters.append(f"  {k}: {v}")
        if filters:
            human_msg += "\n\nCompliance profile context:\n" + "\n".join(filters)

    chain = prompt | llm
    response = chain.invoke({"input": human_msg})
    content = response.content if hasattr(response, "content") else str(response)

    # Parse JSON from response
    parsed = _parse_json(content)

    if parsed and isinstance(parsed, dict):
        parsed["skill_id"] = skill.skill_id
        parsed["skill_display_name"] = skill.display_name
        parsed["skill_category"] = skill.category
        return parsed

    # Fallback
    return _default_skill_context(skill)


def _default_skill_context(skill: Any) -> Dict[str, Any]:
    """Build a default skill_context from the skill definition (no LLM)."""
    return {
        "skill_id": skill.skill_id,
        "skill_display_name": skill.display_name,
        "skill_category": skill.category,
        "confirmed": True,
        "confidence": 0.80,
        "extracted_params": {},
        "analysis_requirements": list(skill.intent_signals.analysis_requirements),
        "ambiguity_notes": None,
    }


def _parse_json(text: str) -> Any:
    """Parse JSON from LLM output, handling ```json fences."""
    import re
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None


def _log_skill_step(state: Dict[str, Any], step_name: str, skill_id: str, context: Dict) -> None:
    """Append to execution_steps for observability."""
    from datetime import datetime
    if "execution_steps" not in state:
        state["execution_steps"] = []
    state["execution_steps"].append({
        "step_name": step_name,
        "agent_name": f"skill:{skill_id}",
        "timestamp": datetime.utcnow().isoformat(),
        "status": "completed",
        "inputs": {"skill_id": skill_id},
        "outputs": {"confirmed": context.get("confirmed", False)},
    })

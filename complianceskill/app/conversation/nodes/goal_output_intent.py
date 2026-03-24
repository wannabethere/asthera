"""
Goal output intent — after ``goal_intent`` is set, LLM proposes deliverables + pipeline flags.

Uses ``app.agents.shared.goal_output_routing.apply_goal_output_routing_to_state``.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict

from langchain_core.prompts import ChatPromptTemplate

from app.agents.prompt_loader import PROMPTS_SHARED, load_prompt
from app.agents.shared.goal_output_routing import (
    ALL_DELIVERABLES,
    DELIVERABLE_METRICS_REC,
    apply_goal_output_routing_to_state,
    normalize_deliverables,
)
from app.agents.state import EnhancedCompliancePipelineState
from app.conversation.config import VerticalConversationConfig
from app.core.dependencies import get_llm

logger = logging.getLogger(__name__)


def _parse_json_response(response_content: str, fallback: Dict[str, Any]) -> Dict[str, Any]:
    try:
        out = json.loads(response_content)
        return out if isinstance(out, dict) else fallback
    except json.JSONDecodeError:
        match = re.search(r"```json\s*(\{.*?\})\s*```", response_content, re.DOTALL)
        if match:
            try:
                out = json.loads(match.group(1))
                return out if isinstance(out, dict) else fallback
            except json.JSONDecodeError:
                pass
        return fallback


def goal_output_intent_node(
    state: EnhancedCompliancePipelineState,
    config: VerticalConversationConfig,
) -> EnhancedCompliancePipelineState:
    if not getattr(config, "enable_goal_intent_phases", True):
        return state

    goal_intent = (state.get("goal_intent") or "").strip()
    if not goal_intent:
        logger.warning("goal_output_intent_node: missing goal_intent, skipping")
        return state

    prev = state.get("goal_output_classifier_result")
    if isinstance(prev, dict) and prev.get("source_goal_intent") == goal_intent:
        return state

    user_query = state.get("user_query", "") or ""
    cp = state.get("compliance_profile") if isinstance(state.get("compliance_profile"), dict) else {}

    try:
        prompt_text = load_prompt("02_goal_output_intent_classifier", prompts_dir=str(PROMPTS_SHARED))
    except FileNotFoundError:
        logger.error("Missing prompt 02_goal_output_intent_classifier.md under prompt_utils/shared")
        fb_deliv = (
            [goal_intent]
            if goal_intent in ALL_DELIVERABLES
            else [DELIVERABLE_METRICS_REC]
        )
        apply_goal_output_routing_to_state(
            state,
            {
                "deliverables": fb_deliv,
                "pipeline_flags": {"needs_metrics_registry": True, "needs_mdl_schemas": True},
                "primary_user_goal_summary": user_query[:500],
                "reasoning": "Prompt missing; conservative fallback.",
            },
            source_goal_intent=goal_intent,
        )
        return state

    human = json.dumps(
        {
            "user_goal_intent_id": goal_intent,
            "user_query": user_query,
            "compliance_profile_excerpt": {k: cp.get(k) for k in list(cp.keys())[:24]},
        },
        indent=2,
    )

    llm = get_llm(temperature=0)
    system_prompt = prompt_text.replace("{", "{{").replace("}", "}}")
    tpl = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "{input}"),
        ]
    )
    chain = tpl | llm
    try:
        response = chain.invoke({"input": human})
        text = response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        logger.error("goal_output_intent LLM failed: %s", e, exc_info=True)
        text = "{}"

    parsed = _parse_json_response(
        text,
        {
            "deliverables": [goal_intent],
            "pipeline_flags": {"needs_metrics_registry": True},
            "primary_user_goal_summary": "",
            "reasoning": "parse_fallback",
        },
    )
    if not normalize_deliverables(parsed.get("deliverables")):
        parsed = {
            **parsed,
            "deliverables": (
                [goal_intent]
                if goal_intent in ALL_DELIVERABLES
                else [DELIVERABLE_METRICS_REC]
            ),
            "reasoning": (parsed.get("reasoning") or "") + "; empty_deliverables_fallback",
        }
    apply_goal_output_routing_to_state(state, parsed, source_goal_intent=goal_intent)
    return state

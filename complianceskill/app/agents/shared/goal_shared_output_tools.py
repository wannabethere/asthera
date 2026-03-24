"""
Goal-driven invocation of shared generators before final output assembly (CSOD + DT).

Uses ``compliance_profile.goal_pipeline_flags`` (from goal output intent routing).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.core.settings import get_settings

logger = logging.getLogger(__name__)


def _goal_pipeline_flags(state: Dict[str, Any]) -> Dict[str, Any]:
    cp = state.get("compliance_profile")
    if not isinstance(cp, dict):
        return {}
    raw = cp.get("goal_pipeline_flags")
    return raw if isinstance(raw, dict) else {}


def _has_goal_routing(state: Dict[str, Any]) -> bool:
    if state.get("goal_output_classifier_result"):
        return True
    cp = state.get("compliance_profile")
    if isinstance(cp, dict) and cp.get("goal_pipeline_flags"):
        return True
    return False


def apply_goal_shared_pipeline(state: Dict[str, Any], workflow: str) -> List[str]:
    """
    Fill calculation plan / gold SQL / Cube.js when goal flags ask for it.
    ``workflow`` is ``\"csod\"`` or ``\"dt\"`` (maps medallion + gold SQL state keys).
    """
    if not _has_goal_routing(state):
        return []

    flags = _goal_pipeline_flags(state)
    actions: List[str] = []
    wf = workflow if workflow in ("csod", "dt") else "csod"

    if flags.get("needs_calculation_plan") and "calculation_plan" not in state:
        from app.agents.shared.calculation_planner import calculation_planner_node

        state["needs_calculation"] = True
        try:
            calculation_planner_node(state)
            actions.append("calculation_planner")
        except Exception as e:
            logger.warning("goal assembly: calculation_planner failed: %s", e, exc_info=True)

    plan_key = "csod_medallion_plan" if wf == "csod" else "dt_medallion_plan"
    plan = state.get(plan_key) or {}
    want_gold = bool(
        flags.get("needs_gold_dbt_sql")
        or (
            state.get("csod_generate_sql")
            if wf == "csod"
            else state.get("dt_generate_sql")
        )
    )
    has_plan = bool(
        plan.get("requires_gold_model") and (plan.get("specifications") or [])
    )
    gold_key = "csod_generated_gold_model_sql" if wf == "csod" else "dt_generated_gold_model_sql"
    existing_sql = state.get(gold_key) or []
    demo_sql = bool(get_settings().DEMO_FAKE_SQL_AND_INSIGHTS)

    if want_gold and not existing_sql and demo_sql:
        from app.agents.shared.demo_sql_insight_agent import (
            apply_demo_sql_insight_agent_to_dt_state,
            apply_demo_sql_insight_agent_to_state,
        )

        if wf == "csod":
            state["csod_generate_sql"] = True
            try:
                if apply_demo_sql_insight_agent_to_state(state):
                    actions.append("demo_sql_insight_agent")
            except Exception as e:
                logger.warning(
                    "goal assembly: demo SQL/insight agent failed: %s", e, exc_info=True
                )
        else:
            state["dt_generate_sql"] = True
            try:
                if apply_demo_sql_insight_agent_to_dt_state(state):
                    actions.append("demo_sql_insight_agent_dt")
            except Exception as e:
                logger.warning(
                    "goal assembly: demo SQL/insight (dt) failed: %s", e, exc_info=True
                )
    elif want_gold and has_plan and not existing_sql:
        from app.agents.csod.csod_nodes.node_gold_sql import (
            csod_gold_model_sql_generator_node,
        )

        if wf == "csod":
            state["csod_generate_sql"] = True
            try:
                csod_gold_model_sql_generator_node(state)
                actions.append("gold_model_sql_generator")
            except Exception as e:
                logger.warning(
                    "goal assembly: gold SQL generator failed: %s", e, exc_info=True
                )
        else:
            state["dt_generate_sql"] = True
            saved_csod_plan = state.get("csod_medallion_plan")
            saved_csod_sql = state.get("csod_generated_gold_model_sql")
            saved_csod_art = state.get("csod_gold_model_artifact_name")
            saved_csod_res = state.get("csod_resolved_schemas")
            try:
                state["csod_medallion_plan"] = plan
                state["csod_resolved_schemas"] = state.get("dt_resolved_schemas") or []
                state["csod_generate_sql"] = True
                csod_gold_model_sql_generator_node(state)
                state["dt_generated_gold_model_sql"] = state.get(
                    "csod_generated_gold_model_sql", []
                )
                state["dt_gold_model_artifact_name"] = state.get(
                    "csod_gold_model_artifact_name"
                )
                actions.append("gold_model_sql_generator_dt")
            except Exception as e:
                logger.warning(
                    "goal assembly: DT gold SQL generator failed: %s", e, exc_info=True
                )
            finally:
                state["csod_medallion_plan"] = saved_csod_plan
                state["csod_generated_gold_model_sql"] = saved_csod_sql
                state["csod_gold_model_artifact_name"] = saved_csod_art
                state["csod_resolved_schemas"] = saved_csod_res

    want_cube = bool(flags.get("needs_cubejs") or state.get("output_format") == "cubejs")
    gold_sql_csod = state.get("csod_generated_gold_model_sql") or []
    gold_sql_dt = state.get("dt_generated_gold_model_sql") or []
    gold_sql = gold_sql_csod or gold_sql_dt
    existing_cubes = state.get("cubejs_schema_files") or []
    if want_cube and gold_sql and not existing_cubes:
        from app.agents.shared.cubejs_generation.node import cubejs_schema_generation_node

        state["output_format"] = "cubejs"
        try:
            out = cubejs_schema_generation_node(state)
            if isinstance(out, dict):
                state.update(out)
            actions.append("cubejs_schema_generation")
        except Exception as e:
            logger.warning("goal assembly: cubejs generation failed: %s", e, exc_info=True)

    return actions


def apply_goal_shared_tools_before_csod_assembly(state: Dict[str, Any]) -> List[str]:
    actions = apply_goal_shared_pipeline(state, "csod")
    if actions:
        state["csod_assembler_goal_actions"] = actions
        logger.info("goal_shared_output_tools (csod): applied %s", actions)
    return actions


def apply_goal_shared_tools_before_dt_assembly(state: Dict[str, Any]) -> List[str]:
    actions = apply_goal_shared_pipeline(state, "dt")
    if actions:
        state["dt_assembler_goal_actions"] = actions
        logger.info("goal_shared_output_tools (dt): applied %s", actions)
    return actions

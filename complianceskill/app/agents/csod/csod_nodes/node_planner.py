"""
Planner node — produces execution plan with inlined concept context + spine precheck.

Consolidates three previously separate nodes:
  1. csod_concept_context — backfills L1 concept anchors (safety net)
  2. csod_planner — LLM-based execution plan generation
  3. csod_spine_precheck — DT axis seeds + capability resolution
"""
import json

from langchain_core.messages import AIMessage

from app.agents.prompt_loader import load_prompt, PROMPTS_CSOD
from app.agents.csod.csod_tool_integration import csod_get_tools_for_agent
from app.agents.csod.csod_nodes._helpers import (
    CSOD_State,
    _csod_log_step,
    _llm_invoke,
    _parse_json_response,
    logger,
)


def _ensure_concept_context(state: CSOD_State) -> None:
    """
    Backfill MDL anchors from L1 concepts when planner chain skipped resolution.

    Inlined from the former ``csod_concept_context_node``. Only runs when
    state lacks project/table hints (conversation Phase 0 normally fills these).
    """
    from app.agents.csod.csod_nodes.node_concept_context import (
        _has_mdl_anchors,
        csod_concept_context_node,
    )
    if not _has_mdl_anchors(state):
        csod_concept_context_node(state)


def _run_spine_precheck(state: CSOD_State) -> None:
    """
    DT axis seeds + capability resolution before metrics retrieval.

    Inlined from the former ``csod_spine_precheck_node``.
    """
    try:
        from app.agents.capabilities.capability_spine import precheck_csod_dt_and_capabilities
        precheck_csod_dt_and_capabilities(state)
        cap = state.get("capability_resolution") or {}
        logger.info(
            "Spine precheck: use_case=%s, coverage=%.2f",
            cap.get("use_case", ""),
            cap.get("capability_coverage_ratio", 0),
        )
    except Exception as e:
        logger.warning("Spine precheck failed (non-fatal): %s", e, exc_info=True)
        state.setdefault("capability_resolution", {})
        state.setdefault("capability_retrieval_hints", "")


def csod_planner_node(state: CSOD_State) -> CSOD_State:
    """
    Produces the CSOD execution plan based on the classified intent.

    Now includes inlined concept context backfill (pre-step) and spine
    precheck (post-step) that were previously separate graph nodes.

    Output fields populated:
        csod_plan_summary, csod_estimated_complexity, csod_execution_plan,
        csod_data_sources_in_scope, csod_gap_notes,
        capability_resolution, csod_dt_seed_decisions (from spine precheck)
    """
    try:
        # Pre-step: ensure concept context is populated
        _ensure_concept_context(state)
        try:
            prompt_text = load_prompt("02_csod_planner", prompts_dir=str(PROMPTS_CSOD))
        except FileNotFoundError as e:
            logger.error(f"CSOD planner prompt file not found: {e}")
            raise FileNotFoundError(
                f"CSOD planner prompt file not found. "
                f"Expected file: {PROMPTS_CSOD / '02_csod_planner.md'}. "
                f"Please ensure the prompt file exists."
            )

        tools = csod_get_tools_for_agent("csod_planner", state=state, conditional=True)
        use_tool_calling = bool(tools)

        intent = state.get("csod_intent", "")
        user_query = state.get("user_query", "")
        data_enrichment = state.get("data_enrichment", {})
        focus_areas = data_enrichment.get("suggested_focus_areas", [])
        selected_data_sources = state.get("selected_data_sources", [])
        
        # Extract compliance_profile fields for filter context (from Lexy conversational layer)
        compliance_profile = state.get("compliance_profile", {})
        time_window = compliance_profile.get("time_window")
        org_unit = compliance_profile.get("org_unit")
        org_unit_value = compliance_profile.get("org_unit_value")
        persona = compliance_profile.get("persona") or state.get("csod_persona")
        training_type = compliance_profile.get("training_type")
        cost_focus = compliance_profile.get("cost_focus")
        skills_domain = compliance_profile.get("skills_domain")
        
        # NEW: Registry-resolved context from planner workflow
        causal_paths = compliance_profile.get("causal_paths", [])
        selected_concepts = compliance_profile.get("selected_concepts", [])
        selected_area_ids = compliance_profile.get("selected_area_ids", [])
        
        # Build filter context string
        filter_context_parts = []
        if time_window:
            filter_context_parts.append(f"Time Window: {time_window}")
        if org_unit:
            filter_context_str = f"Org Unit: {org_unit}"
            if org_unit_value:
                filter_context_str += f" ({org_unit_value})"
            filter_context_parts.append(filter_context_str)
        if persona:
            filter_context_parts.append(f"Persona: {persona}")
        if training_type:
            filter_context_parts.append(f"Training Type: {training_type}")
        if cost_focus:
            filter_context_parts.append(f"Cost Focus: {cost_focus}")
        if skills_domain:
            filter_context_parts.append(f"Skills Domain: {skills_domain}")
        
        filter_context = "\n".join(filter_context_parts) if filter_context_parts else "None specified"

        human_message = f"""User Query: {user_query}
Intent: {intent}
Focus Areas: {json.dumps(focus_areas)}
Selected Data Sources: {json.dumps(selected_data_sources)}
Metrics Intent: {data_enrichment.get('metrics_intent', 'current_state')}
Needs MDL: {data_enrichment.get('needs_mdl', False)}
Needs Metrics: {data_enrichment.get('needs_metrics', False)}

Filter Context (from conversational scoping):
{filter_context}

Use the filter context above to scope the execution plan appropriately. These filters replace the need for clarifying questions."""

        # NEW: Inject causal paths and selected area context
        if causal_paths:
            human_message += f"\n\nKnown causal paths for this analysis:\n{json.dumps(causal_paths, indent=2)}"
        if selected_concepts:
            human_message += f"\n\nUser-selected concept domains: {', '.join(selected_concepts)}"
        if selected_area_ids:
            human_message += f"\n\nFocus recommendation areas: {', '.join(selected_area_ids)}"

        human_message += "\n\nProduce the execution plan JSON as specified in your instructions."

        # Inject executor registry summary (planner-executor architecture v4.0)
        try:
            from app.agents.csod.executor_registry import registry_summary_for_planner
            registry_summary = registry_summary_for_planner()
            human_message += f"\n\nAVAILABLE EXECUTORS (for execution_plan executor_id selection):\n{json.dumps(registry_summary, indent=2)}"
        except Exception as reg_err:
            logger.debug(f"Executor registry injection skipped: {reg_err}")

        response_content = _llm_invoke(
            state, "csod_planner", prompt_text, human_message,
            tools, use_tool_calling, max_tool_iterations=5,
        )

        plan_result = _parse_json_response(response_content, {})

        # Persist plan fields
        state["csod_plan_summary"] = plan_result.get("plan_summary", "")
        state["csod_estimated_complexity"] = plan_result.get("estimated_complexity", "moderate")
        state["csod_execution_plan"] = plan_result.get("execution_plan", [])
        state["csod_gap_notes"] = plan_result.get("gap_notes", [])
        state["csod_data_sources_in_scope"] = (
            plan_result.get("data_sources_in_scope") or selected_data_sources
        )
        state["csod_narrative_preview"] = plan_result.get("narrative_preview") or ""
        state["csod_follow_up_eligible"] = bool(
            plan_result.get("follow_up_eligible", False)
        )
        if state.get("csod_narrative_preview"):
            try:
                from app.agents.csod.csod_nodes.narrative import append_csod_narrative

                append_csod_narrative(
                    state,
                    "planner",
                    "Planner",
                    state["csod_narrative_preview"],
                )
            except Exception:
                pass

        _csod_log_step(
            state, "csod_planning", "csod_planner",
            inputs={
                "user_query": user_query,
                "intent": intent,
                "focus_areas": focus_areas,
            },
            outputs={
                "plan_summary": state["csod_plan_summary"],
                "complexity": state["csod_estimated_complexity"],
                "data_sources_in_scope": state["csod_data_sources_in_scope"],
            },
        )
        try:
            from app.agents.csod.reasoning_trace import refresh_reasoning_trace_after_planner

            refresh_reasoning_trace_after_planner(state)
        except Exception:
            pass

        state["messages"].append(AIMessage(
            content=(
                f"CSOD Plan: {state['csod_plan_summary'][:100]} | "
                f"sources={state['csod_data_sources_in_scope']}"
            )
        ))

        # Post-step: spine precheck (DT axis seeds + capability resolution)
        _run_spine_precheck(state)

    except Exception as e:
        logger.error(f"csod_planner_node failed: {e}", exc_info=True)
        state["error"] = f"CSOD planner failed: {str(e)}"
        state.setdefault("csod_plan_summary", "")
        state.setdefault("csod_estimated_complexity", "moderate")
        state.setdefault("csod_execution_plan", [])
        state.setdefault("csod_data_sources_in_scope", state.get("selected_data_sources", []))

    return state

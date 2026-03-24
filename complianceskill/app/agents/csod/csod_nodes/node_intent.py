"""Intent classification node."""
from typing import Optional

from langchain_core.messages import AIMessage

from app.agents.prompt_loader import load_prompt, PROMPTS_CSOD, PROMPTS_SHARED
from app.agents.csod.csod_tool_integration import csod_get_tools_for_agent
from app.agents.causalgraph.lexy_domain_context import apply_domain_classification_to_state
from app.agents.csod.csod_nodes._helpers import (
    CSOD_State,
    _csod_log_step,
    _llm_invoke,
    _parse_json_response,
    logger,
)

def _apply_pipeline_intent_extras(state: CSOD_State, pipeline_intent: Optional[str]) -> None:
    from app.agents.csod.intent_config import (
        get_default_advisory_mode_for_pipeline_intent,
        get_intent_family_for_pipeline_intent,
    )

    state["intent_family"] = get_intent_family_for_pipeline_intent(pipeline_intent)
    state["advisory_mode"] = get_default_advisory_mode_for_pipeline_intent(pipeline_intent)


def _build_csod_intent_classifier_prompt() -> str:
    """Shared analysis classifier + injected catalog + CSOD domain add-on."""
    core = load_prompt("01_analysis_intent_classifier", str(PROMPTS_SHARED))
    from app.agents.csod.intent_config import get_csod_intent_classifier_catalog_json

    catalog_json = get_csod_intent_classifier_catalog_json()
    core = core.replace("<<<INTENT_CATALOG_JSON>>>", catalog_json)
    addon = load_prompt("01_intent_classifier_domain_addon", str(PROMPTS_CSOD))
    return f"{core}\n\n{addon}"


def csod_intent_classifier_node(state: CSOD_State) -> CSOD_State:
    """
    Classifies the user query via the shared analysis intent classifier prompt plus an
    injected JSON catalog from ``intent_config`` (all CSOD / DT analysis intents).

    Output fields populated:
        csod_intent (canonical pipeline id for executors), csod_intent_registry_id (Lexy/catalog label
        when different), csod_stage_1_intent (Lexy-shaped stage_1 for UI),
        csod_intent_classifier_output, csod_persona, data_enrichment
    
    If Lexy conversational layer has pre-resolved the intent (indicated by
    compliance_profile.lexy_metric_narration and csod_intent being set),
    this node skips LLM classification and passes through the pre-resolved intent.
    """
    state.setdefault("csod_narrative_stream", [])
    state["csod_followup_short_circuit"] = False
    try:
        # Check if conversation layer already resolved intent
        profile = state.get("compliance_profile", {})
        lexy_narration = profile.get("lexy_metric_narration")
        pre_resolved_intent = state.get("csod_intent")
        
        if lexy_narration and pre_resolved_intent:
            from app.agents.csod.intent_config import (
                default_quadrant_for_intent,
                get_cce_enabled_for_intent,
                resolve_pipeline_intent,
            )

            registry_intent = str(pre_resolved_intent).strip()
            pipeline_intent = resolve_pipeline_intent(registry_intent) or registry_intent
            logger.info(
                "Intent pre-resolved by Lexy: registry=%s pipeline=%s",
                registry_intent,
                pipeline_intent,
            )
            state["csod_intent_registry_id"] = registry_intent
            state["csod_intent"] = pipeline_intent
            state["intent"] = pipeline_intent
            try:
                state["csod_causal_graph_enabled"] = get_cce_enabled_for_intent(pipeline_intent)
            except Exception:
                pass
            _apply_pipeline_intent_extras(state, pipeline_intent)
            state["csod_stage_1_intent"] = {
                "intent": registry_intent,
                "confidence": 1.0,
                "quadrant": default_quadrant_for_intent(registry_intent),
                "routing": "full_spine",
                "spine_steps_skipped": [],
                "tags": ["lexy_pre_resolved"],
                "signals": [
                    {
                        "key": "lexy_metric_narration",
                        "value": "Intent supplied by conversational layer (Lexy)",
                    }
                ],
                "implicit_questions": [],
            }

            # Ensure persona is set from compliance_profile if available
            persona = profile.get("persona")
            if persona:
                state["csod_persona"] = persona

            # Set default data_enrichment if not present
            if "data_enrichment" not in state:
                state["data_enrichment"] = {
                    "needs_mdl": True,
                    "needs_metrics": True,
                    "suggested_focus_areas": [],
                    "metrics_intent": "current_state",
                }

            _csod_log_step(
                state, "intent_classification", "csod_intent_classifier",
                inputs={"user_query": state.get("user_query", ""), "lexy_pre_resolved": True},
                outputs={
                    "intent_registry": registry_intent,
                    "intent_pipeline": pipeline_intent,
                    "persona": state.get("csod_persona"),
                    "source": "lexy_conversational_layer",
                },
            )

            state["messages"].append(
                AIMessage(
                    content=(
                        f"CSOD Intent pre-resolved by Lexy: registry={registry_intent} "
                        f"pipeline={pipeline_intent} | persona={state.get('csod_persona', 'N/A')}"
                    )
                )
            )

            apply_domain_classification_to_state(state)
            try:
                from app.agents.csod.reasoning_trace import refresh_reasoning_trace_after_intent

                refresh_reasoning_trace_after_intent(state)
            except Exception:
                pass
            return state

        try:
            prompt_text = _build_csod_intent_classifier_prompt()
        except FileNotFoundError as e:
            logger.error(f"CSOD intent classifier prompt file not found: {e}")
            raise FileNotFoundError(
                "CSOD intent classifier requires prompt_utils/shared/01_analysis_intent_classifier.md "
                f"and {PROMPTS_CSOD / '01_intent_classifier_domain_addon.md'}."
            ) from e

        tools = csod_get_tools_for_agent("csod_intent_classifier", state=state, conditional=True)
        use_tool_calling = bool(tools)

        human_message = f"User Query: {state.get('user_query', '')}"

        response_content = _llm_invoke(
            state, "csod_intent_classifier", prompt_text, human_message,
            tools, use_tool_calling, max_tool_iterations=3,
        )

        result = _parse_json_response(response_content, {})

        from app.agents.csod.intent_config import (
            ALLOWED_CSOD_ANALYSIS_INTENTS,
            build_stage_1_intent_from_classifier,
            get_cce_enabled_for_intent,
            resolve_pipeline_intent,
        )

        registry_intent = (result.get("intent") or "").strip()
        if not registry_intent or registry_intent not in ALLOWED_CSOD_ANALYSIS_INTENTS:
            if registry_intent:
                logger.warning(
                    "Classifier returned unknown intent %r; falling back to metrics_dashboard_plan",
                    registry_intent,
                )
            registry_intent = "metrics_dashboard_plan"

        pipeline_intent = resolve_pipeline_intent(registry_intent) or registry_intent
        state["csod_intent_registry_id"] = registry_intent
        state["csod_intent"] = pipeline_intent
        state["intent"] = pipeline_intent
        state["csod_stage_1_intent"] = build_stage_1_intent_from_classifier(
            result, registry_intent
        )
        try:
            state["csod_causal_graph_enabled"] = get_cce_enabled_for_intent(pipeline_intent)
        except Exception:
            pass

        _apply_pipeline_intent_extras(state, pipeline_intent)

        envelope = {
            "agent": result.get("agent"),
            "narrative": result.get("narrative"),
            "detail": result.get("detail"),
            "intent_signals": result.get("intent_signals"),
            "alternate_intents": result.get("alternate_intents"),
            "analysis_requirements": result.get("analysis_requirements"),
            "confidence_score": result.get("confidence_score"),
            "intent_registry": registry_intent,
            "intent_pipeline": pipeline_intent,
        }
        state["csod_intent_classifier_output"] = envelope

        persona = result.get("persona")
        if persona:
            state["csod_persona"] = persona

        # Store data_enrichment block
        data_enrichment = result.get("data_enrichment", {})
        if not isinstance(data_enrichment, dict):
            data_enrichment = {}

        data_enrichment.setdefault("needs_mdl", True)  # CSOD typically needs MDL
        data_enrichment.setdefault("needs_metrics", True)  # CSOD typically needs metrics
        data_enrichment.setdefault("suggested_focus_areas", [])
        data_enrichment.setdefault("metrics_intent", "current_state")

        ar = result.get("analysis_requirements")
        if isinstance(ar, dict) and ar:
            data_enrichment["analysis_requirements"] = ar

        state["data_enrichment"] = data_enrichment

        try:
            from app.agents.csod.csod_nodes.narrative import append_csod_narrative

            areas = data_enrichment.get("suggested_focus_areas") or []
            area_s = ", ".join(str(a) for a in areas[:5]) if areas else "general"
            narrative_line = result.get("narrative") or (
                f"Intent `{registry_intent}` → pipeline `{pipeline_intent}`. "
                f"Focus areas: {area_s}."
            )
            append_csod_narrative(
                state,
                "intent",
                result.get("agent") or "Intent classifier",
                narrative_line,
                meta={
                    "detail": result.get("detail"),
                    "intent_signals": result.get("intent_signals"),
                },
            )
        except Exception:
            pass

        _csod_log_step(
            state, "intent_classification", "csod_intent_classifier",
            inputs={"user_query": state.get("user_query", "")},
            outputs={
                "intent_registry": registry_intent,
                "intent_pipeline": state.get("csod_intent"),
                "persona": state.get("csod_persona"),
                "confidence_score": result.get("confidence_score"),
                "needs_mdl": data_enrichment.get("needs_mdl"),
                "needs_metrics": data_enrichment.get("needs_metrics"),
                "suggested_focus_areas": data_enrichment.get("suggested_focus_areas"),
                "detail": result.get("detail"),
            },
        )

        state["messages"].append(AIMessage(
            content=(
                f"CSOD Intent classified: registry={registry_intent} "
                f"pipeline={state.get('csod_intent')} | "
                f"persona={state.get('csod_persona', 'N/A')} | "
                f"needs_metrics={data_enrichment.get('needs_metrics')} | "
                f"detail={result.get('detail', 'N/A')}"
            )
        ))

        apply_domain_classification_to_state(state)
        try:
            from app.agents.csod.reasoning_trace import refresh_reasoning_trace_after_intent

            refresh_reasoning_trace_after_intent(state)
        except Exception:
            pass

    except Exception as e:
        logger.error(f"csod_intent_classifier_node failed: {e}", exc_info=True)
        state["error"] = f"CSOD intent classification failed: {str(e)}"
        # Set default intent
        state.setdefault("csod_intent", "metrics_dashboard_plan")
        _apply_pipeline_intent_extras(state, state.get("csod_intent"))

    return state

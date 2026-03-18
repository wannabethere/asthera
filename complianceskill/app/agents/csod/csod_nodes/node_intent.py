"""Intent classification node."""
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

ADVISOR_WORKFLOW = "csod_metric_advisor_workflow"
METRIC_KPI_ADVISOR_INTENT = "metric_kpi_advisor"


def csod_intent_classifier_node(state: CSOD_State) -> CSOD_State:
    """
    Classifies the user query into one of 5 CSOD intents:
    1. metrics_dashboard_plan - Plan for a metrics dashboard
    2. metrics_recommender_with_gold_plan - Metrics recommender with gold plan
    3. dashboard_generation_for_persona - Dashboard generation for a persona
    4. compliance_test_generator - Compliance test generator that runs alerts (SQL operations)
    5. metric_kpi_advisor - Metric/KPI recommendations with causal reasoning, relationship mapping, and structured analysis plans
    
    Output fields populated:
        csod_intent, csod_persona (if applicable), data_enrichment
        (needs_mdl, needs_metrics, suggested_focus_areas, metrics_intent)
    
    If Lexy conversational layer has pre-resolved the intent (indicated by
    compliance_profile.lexy_metric_narration and csod_intent being set),
    this node skips LLM classification and passes through the pre-resolved intent.
    """
    try:
        # Check if conversation layer already resolved intent
        profile = state.get("compliance_profile", {})
        lexy_narration = profile.get("lexy_metric_narration")
        pre_resolved_intent = state.get("csod_intent")
        
        if lexy_narration and pre_resolved_intent:
            # Intent pre-resolved by conversational layer — pass through
            logger.info(f"Intent pre-resolved by Lexy: {pre_resolved_intent}")
            
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
                    "intent": pre_resolved_intent,
                    "persona": state.get("csod_persona"),
                    "source": "lexy_conversational_layer",
                },
            )
            
            state["messages"].append(AIMessage(
                content=(
                    f"CSOD Intent pre-resolved by Lexy: {pre_resolved_intent} | "
                    f"persona={state.get('csod_persona', 'N/A')}"
                )
            ))
            
            return state

        # Planner already routed to metric-advisor workflow; do not re-classify (would
        # change intent and skip MDL → metrics → CCE → recommender → advisor path).
        advisor_by_target = state.get("csod_target_workflow") == ADVISOR_WORKFLOW
        advisor_by_intent = state.get("csod_intent") == METRIC_KPI_ADVISOR_INTENT
        if state.get("csod_from_planner_chain") and (
            advisor_by_target
            or (advisor_by_intent and state.get("csod_primary_skill"))
        ):
            state["csod_intent"] = METRIC_KPI_ADVISOR_INTENT
            logger.info(
                "Intent pre-reserved from csod-planner: metric_kpi_advisor (pipeline: "
                "MDL → metrics retrieval → scoring → DT → causal → recommender → advisor)"
            )
            if "data_enrichment" not in state:
                state["data_enrichment"] = {
                    "needs_mdl": True,
                    "needs_metrics": True,
                    "suggested_focus_areas": [],
                    "metrics_intent": "current_state",
                }
            try:
                from app.agents.csod.intent_config import get_cce_enabled_for_intent

                if not isinstance(state.get("csod_causal_graph_enabled"), bool):
                    state["csod_causal_graph_enabled"] = get_cce_enabled_for_intent(
                        METRIC_KPI_ADVISOR_INTENT
                    )
            except Exception:
                state.setdefault("csod_causal_graph_enabled", True)
            _csod_log_step(
                state,
                "intent_classification",
                "csod_intent_classifier",
                inputs={"user_query": state.get("user_query", ""), "planner_chain": True},
                outputs={
                    "intent": METRIC_KPI_ADVISOR_INTENT,
                    "source": "planner_routed_metric_advisor",
                },
            )
            state["messages"].append(
                AIMessage(
                    content=(
                        f"CSOD Intent from planner chain: {METRIC_KPI_ADVISOR_INTENT} | "
                        f"causal_graph_enabled={state.get('csod_causal_graph_enabled')}"
                    )
                )
            )
            return state

        try:
            prompt_text = load_prompt("01_intent_classifier", prompts_dir=str(PROMPTS_CSOD))
        except FileNotFoundError as e:
            logger.error(f"CSOD intent classifier prompt file not found: {e}")
            raise FileNotFoundError(
                f"CSOD intent classifier prompt file not found. "
                f"Expected file: {PROMPTS_CSOD / '01_intent_classifier.md'}. "
                f"Please ensure the prompt file exists."
            )

        tools = csod_get_tools_for_agent("csod_intent_classifier", state=state, conditional=True)
        use_tool_calling = bool(tools)

        human_message = f"User Query: {state.get('user_query', '')}"

        response_content = _llm_invoke(
            state, "csod_intent_classifier", prompt_text, human_message,
            tools, use_tool_calling, max_tool_iterations=3,
        )

        result = _parse_json_response(response_content, {})

        # Persist classifier output fields
        intent = result.get("intent", "")
        if intent:
            state["csod_intent"] = intent
            state["intent"] = intent  # Also set base intent for compatibility
            # CCE gating from intent (prompts_updates v2.2)
            try:
                from app.agents.csod.intent_config import get_cce_enabled_for_intent
                state["csod_causal_graph_enabled"] = get_cce_enabled_for_intent(intent)
            except Exception:
                pass
        
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

        state["data_enrichment"] = data_enrichment

        _csod_log_step(
            state, "intent_classification", "csod_intent_classifier",
            inputs={"user_query": state.get("user_query", "")},
            outputs={
                "intent": state.get("csod_intent"),
                "persona": state.get("csod_persona"),
                "confidence_score": result.get("confidence_score"),
                "needs_mdl": data_enrichment.get("needs_mdl"),
                "needs_metrics": data_enrichment.get("needs_metrics"),
                "suggested_focus_areas": data_enrichment.get("suggested_focus_areas"),
            },
        )

        state["messages"].append(AIMessage(
            content=(
                f"CSOD Intent classified: {state.get('csod_intent')} | "
                f"persona={state.get('csod_persona', 'N/A')} | "
                f"needs_metrics={data_enrichment.get('needs_metrics')}"
            )
        ))

    except Exception as e:
        logger.error(f"csod_intent_classifier_node failed: {e}", exc_info=True)
        state["error"] = f"CSOD intent classification failed: {str(e)}"
        # Set default intent
        state.setdefault("csod_intent", "metrics_dashboard_plan")

    return state

"""
Conversation Planner Workflow - Generic Multi-Turn Conversation Engine

This workflow replaces the legacy monolith in archived/csod/csod_planner_workflow_legacy.py
that supports interrupts and multi-turn interactions.

Graph topology:
    datasource_selector
      → intent_splitter          (LLM: decompose query into 1–3 analytical intents)
        → mdl_project_resolver   (LLM + MDL: map each intent to specific projects + areas)
          → intent_confirm       (interrupt: user selects intent(s) + projects)
            → preliminary_area_matcher
              → scoping          (interrupt: time/org/filter questions)
                → concept_confirm (interrupt: user selects concept domains to focus on)
                  → area_matcher  (scoped to confirmed concepts — scalable to 100s of areas)
                    → area_confirm (interrupt: user selects recommendation area)
                      → metric_narration (interrupt: user confirms what will be measured)
                        → workflow_router
                          → [invoke downstream workflow]
                            → END
"""
import logging
from typing import Any, Dict, Optional

from langgraph.graph import StateGraph, END
from app.core.checkpointer_provider import get_checkpointer

from app.agents.state import EnhancedCompliancePipelineState
from app.conversation.config import VerticalConversationConfig
from app.conversation.turn import ConversationCheckpoint
from app.conversation.nodes.scoping import scoping_node
from app.conversation.nodes.concept_confirm import concept_confirm_node
from app.conversation.nodes.area_confirm import area_confirm_node
from app.conversation.nodes.metric_narration import metric_narration_node
from app.conversation.nodes.goal_intent import goal_intent_node
from app.conversation.nodes.goal_output_intent import goal_output_intent_node
from app.conversation.nodes.csod_intent_confirm import csod_intent_confirm_node
from app.ingestion.intent_splitter import split_user_intent
from app.ingestion.mdl_intent_resolver import resolve_intents_to_projects_and_areas
from app.agents.csod.csod_query_utils import effective_user_query

logger = logging.getLogger(__name__)


# ============================================================================
# Planner nodes (logic ported from archived/csod/csod_planner_workflow_legacy.py)
# ============================================================================

def datasource_selector_node(
    state: EnhancedCompliancePipelineState,
    config: VerticalConversationConfig,
) -> EnhancedCompliancePipelineState:
    """
    Phase 0 Step A: Datasource selection.
    
    If datasource is not yet selected, prompts user to select.
    If already selected, passes through to concept resolver.
    """
    selected_datasource = state.get("csod_selected_datasource")
    user_message = state.get("user_query", "").lower()
    inferred_from_query = False

    if not selected_datasource:
        # Try to match from user message
        for ds in config.supported_datasources:
            if ds["id"] in user_message or ds.get("display_name", "").lower() in user_message:
                selected_datasource = ds["id"]
                inferred_from_query = True
                break

        # Default to first datasource if only one is configured or none was found
        if not selected_datasource and config.supported_datasources:
            selected_datasource = config.supported_datasources[0]["id"]
            # Auto-confirm when there is only one choice
            if len(config.supported_datasources) == 1:
                inferred_from_query = True
            logger.info(f"No datasource specified, defaulting to {selected_datasource}")

    state["csod_selected_datasource"] = selected_datasource
    state["csod_available_datasources"] = config.supported_datasources

    # Auto-confirm when datasource was inferred from the query or only one option exists
    if not state.get("csod_datasource_confirmed"):
        if inferred_from_query:
            logger.info(f"Datasource '{selected_datasource}' inferred from query — auto-confirming")
            state["csod_datasource_confirmed"] = True
            state["csod_checkpoint_resolved"] = True
            return state

        from app.conversation.turn import ConversationCheckpoint, ConversationTurn, TurnOutputType

        checkpoint = ConversationCheckpoint(
            phase="datasource_select",
            turn=ConversationTurn(
                phase="datasource_select",
                turn_type=TurnOutputType.DECISION,
                message="Which platform are you analyzing today?",
                options=[
                    {
                        "id": ds["id"],
                        "label": ds.get("display_name", ds["id"]),
                        "description": ds.get("description", ""),
                    }
                    for ds in config.supported_datasources
                ],
            ),
            resume_with_field="csod_datasource_confirmed",
        )
        state["csod_conversation_checkpoint"] = checkpoint.to_dict()
        state["csod_checkpoint_resolved"] = False
        return state

    state["csod_datasource_confirmed"] = True
    # Clear any lingering checkpoint from a prior turn so that subsequent nodes
    # (concept_resolver, etc.) don't see a stale datasource_select checkpoint.
    # Edge-function mutations in _route_with_interrupt do NOT persist in LangGraph
    # channel state — this node-level clear is the reliable way to commit the change.
    state["csod_conversation_checkpoint"] = None
    state["csod_checkpoint_resolved"] = True
    return state


def intent_splitter_node(
    state: EnhancedCompliancePipelineState,
    config: VerticalConversationConfig,
) -> EnhancedCompliancePipelineState:
    """
    Phase 0 Step B: Intent decomposition.

    LLM decomposes the user query into 1–3 independent analytical intents.
    Skipped on resume if intents are already split and concepts confirmed.
    """
    # Skip if intents already split (preserved through checkpoint resume — see fresh-query reset).
    # Do NOT require csod_concepts_confirmed: that flag is reset on fresh queries, so checking it
    # would cause the LLM to re-run on every checkpoint resume (wasteful and non-deterministic).
    if state.get("csod_intent_splits"):
        logger.info("intent_splitter: already split (%d intents) — skipping", len(state["csod_intent_splits"]))
        return state

    user_query = effective_user_query(state)
    selected_datasource = state.get("csod_selected_datasource", "")

    if not user_query:
        goal_intent = (state.get("goal_intent") or "").strip()
        if goal_intent and selected_datasource:
            user_query = f"{goal_intent} analysis for {selected_datasource}"
            logger.info("intent_splitter: synthesised fallback query: %r", user_query)
            state["user_query"] = user_query
        else:
            logger.warning(
                "intent_splitter: no user query and no context to synthesise from — "
                "goal_intent=%r datasource=%r",
                goal_intent, selected_datasource,
            )
            state["csod_intent_splits"] = []
            return state

    state["user_query"] = user_query

    intents = split_user_intent(user_query, datasource_id=selected_datasource)
    state["csod_intent_splits"] = intents

    logger.info(
        "intent_splitter: %d intent(s) for query %r",
        len(intents),
        user_query[:80],
    )
    return state


def mdl_project_resolver_node(
    state: EnhancedCompliancePipelineState,
    config: VerticalConversationConfig,
) -> EnhancedCompliancePipelineState:
    """
    Phase 0 Step C: MDL-aware intent → project + area resolution.

    For each intent from intent_splitter_node, the LLM identifies:
    - Specific CSOD projects relevant to that intent (not all 16)
    - Best-fit concept and recommendation areas
    Skipped on resume if resolutions already exist and concepts are confirmed.
    """
    # Skip if already resolved (preserved through checkpoint resume — see fresh-query reset).
    # Do NOT require csod_concepts_confirmed: same reasoning as intent_splitter_node above.
    if state.get("csod_intent_resolutions"):
        logger.info("mdl_project_resolver: already resolved (%d resolutions) — skipping", len(state["csod_intent_resolutions"]))
        return state

    intents = state.get("csod_intent_splits") or []
    if not intents:
        logger.warning("mdl_project_resolver: no intents to resolve")
        state["csod_intent_resolutions"] = []
        return state

    selected_datasource = state.get("csod_selected_datasource", "")
    resolutions = resolve_intents_to_projects_and_areas(intents, datasource_id=selected_datasource)
    state["csod_intent_resolutions"] = resolutions

    logger.info(
        "mdl_project_resolver: %d resolution(s); projects per intent: %s",
        len(resolutions),
        [len(r.get("matched_project_ids", [])) for r in resolutions],
    )
    return state


def preliminary_area_matcher_node(
    state: EnhancedCompliancePipelineState,
    config: VerticalConversationConfig,
) -> EnhancedCompliancePipelineState:
    """
    Preliminary area matcher - lightweight first-pass lookup without scoping.
    
    Used by scoping_node to determine which filters to ask about.
    """
    confirmed_concept_ids = state.get("csod_confirmed_concept_ids") or []
    
    if not confirmed_concept_ids:
        state["csod_preliminary_area_matches"] = []
        return state
    
    primary_concept_id = confirmed_concept_ids[0]
    llm_areas = (state.get("csod_llm_resolved_areas") or {}).get(primary_concept_id, [])

    # Use the top LLM-resolved area to get its filters for scoping questions
    state["csod_preliminary_area_matches"] = [
        {
            "area_id": a["area_id"],
            "concept_id": a["concept_id"],
            "display_name": a["display_name"],
            "score": a["score"],
            "filters": a["filters"],
            "description": a["description"],
        }
        for a in llm_areas[:1]
    ]
    logger.info(
        f"preliminary_area_matcher: {len(state['csod_preliminary_area_matches'])} areas "
        f"for concept {primary_concept_id}"
    )
    return state


def area_matcher_node(
    state: EnhancedCompliancePipelineState,
    config: VerticalConversationConfig,
) -> EnhancedCompliancePipelineState:
    """
    Phase 0 Step D: Recommendation area matching using L2 collection.

    Now runs WITH scoping context (scoping_answers populated).
    """
    confirmed_concept_ids = state.get("csod_confirmed_concept_ids") or []
    scoping_answers = state.get("csod_scoping_answers") or {}

    # Pass-through: if area is already confirmed by the user, do not overwrite area_matches
    # so that area_confirm_node can still see the confirmed area for the primary_area promotion.
    if state.get("csod_confirmed_area_id"):
        logger.info(
            "area_matcher: area already confirmed (%s) — pass-through",
            state.get("csod_confirmed_area_id"),
        )
        return state

    if not confirmed_concept_ids:
        logger.warning("No confirmed concepts for area matching")
        state["csod_area_matches"] = []
        return state

    llm_resolved = state.get("csod_llm_resolved_areas") or {}
    logger.info(
        "area_matcher: concept_ids=%s | llm_resolved keys=%s | scoping_answers=%s",
        confirmed_concept_ids,
        list(llm_resolved.keys())[:5],
        list((scoping_answers or {}).keys()),
    )
    seen_area_ids: set = set()
    all_area_matches = []

    for concept_id in confirmed_concept_ids:
        # Try string and original key to guard against int/str type mismatches
        for key in (str(concept_id), concept_id):
            for a in llm_resolved.get(key, []):
                if a["area_id"] not in seen_area_ids:
                    seen_area_ids.add(a["area_id"])
                    all_area_matches.append(a)
        if all_area_matches:
            break

    if not all_area_matches:
        # Fallback: use preliminary area matches computed before scoping.
        # This covers the case where the LLM-resolved cache key format doesn't
        # line up with confirmed_concept_ids on a checkpoint-resume pass.
        preliminary = state.get("csod_preliminary_area_matches") or []
        if preliminary:
            logger.warning(
                "area_matcher: LLM-resolved lookup returned 0 matches (concept_ids=%s, "
                "llm_resolved keys=%s). Falling back to %d preliminary area match(es).",
                confirmed_concept_ids,
                list(llm_resolved.keys())[:5],
                len(preliminary),
            )
            all_area_matches = preliminary
        else:
            # Also try preserving any existing area_matches from a prior run
            existing = state.get("csod_area_matches") or []
            if existing:
                logger.warning(
                    "area_matcher: no matches and no preliminary matches; "
                    "preserving %d existing area_matches from prior run.",
                    len(existing),
                )
                all_area_matches = existing  # use existing but still ensure primary_area is set

    state["csod_area_matches"] = all_area_matches[:3]

    if all_area_matches:
        p = all_area_matches[0]
        # Always (re)set csod_primary_area so metric_narration_node and
        # workflow_router_node never see None regardless of which code path ran.
        if not state.get("csod_primary_area"):
            state["csod_primary_area"] = {
                "area_id": p.get("area_id", ""),
                "display_name": p.get("display_name", ""),
                "metrics": p.get("metrics", []),
                "kpis": p.get("kpis", []),
                "data_requirements": p.get("data_requirements", []),
                "causal_paths": p.get("causal_paths", []),
            }

    logger.info(f"area_matcher: {len(all_area_matches)} areas resolved, primary_area set: {bool(state.get('csod_primary_area'))}")
    return state


def workflow_router_node(
    state: EnhancedCompliancePipelineState,
    config: VerticalConversationConfig,
) -> EnhancedCompliancePipelineState:
    """
    Phase 0 Final: Route to appropriate downstream workflow.
    
    Updated to populate compliance_profile with scoping fields and metric narration.
    """
    primary_area = state.get("csod_primary_area") or {}
    confirmed_area_id = state.get("csod_confirmed_area_id")
    metric_narration = state.get("csod_metric_narration", "")
    scoping_answers = state.get("csod_scoping_answers") or {}

    state["csod_target_workflow"] = config.default_workflow
    # Intent will be determined by csod_intent_classifier in the main workflow
    
    # Prepare state for downstream workflow
    # Build compliance_profile with resolved context
    compliance_profile = state.get("compliance_profile") or {}
    
    # Add registry-resolved context
    _goal_patch: Dict[str, Any] = {}
    if state.get("goal_intent"):
        _goal_patch["goal_intent"] = state["goal_intent"]
    if state.get("goal_output_intents"):
        _goal_patch["goal_output_intents"] = state["goal_output_intents"]
    gor = state.get("goal_output_classifier_result")
    if isinstance(gor, dict):
        _goal_patch["goal_output_classifier_result"] = gor
    compliance_profile.update(_goal_patch)
    compliance_profile.update({
        "selected_concepts": [c["concept_id"] for c in (state.get("csod_selected_concepts") or [])],
        "selected_area_ids": [a["area_id"] for a in (state.get("csod_area_matches") or [])],
        "selected_project_ids": state.get("csod_resolved_project_ids") or [],
        "priority_metrics": primary_area.get("metrics", []),
        "priority_kpis": primary_area.get("kpis", []),
        "data_requirements": primary_area.get("data_requirements", []),
        "causal_paths": primary_area.get("causal_paths", []),
        # Dynamic signals extracted during intent decomposition — [{label, value}]
        # Label names are LLM-chosen (e.g. terminal_metric, urgency, analysis_type…)
        "extracted_signals": state.get("csod_extracted_signals") or [],
        # active_mdl_tables resolved later by L3 in the downstream workflow
    })
    
    # CRITICAL: Set lexy_metric_narration - triggers intent bypass
    if metric_narration:
        compliance_profile["lexy_metric_narration"] = metric_narration
    
    # CRITICAL: Unpack scoping_answers into compliance_profile top-level keys
    # These are read by csod_planner_node when building filter_context
    if scoping_answers:
        compliance_profile.update({
            "time_window": scoping_answers.get("time_window"),
            "org_unit": scoping_answers.get("org_unit"),
            "training_type": scoping_answers.get("training_type"),
            "deadline_window": scoping_answers.get("deadline_window"),
            "delivery_method": scoping_answers.get("delivery_method"),
            "audit_window": scoping_answers.get("audit_window"),
            "course_scope": scoping_answers.get("course_scope"),
            "user_status": scoping_answers.get("user_status"),
        })
    
    # Set csod_intent from confirmed area if not already set
    if not state.get("csod_intent") and confirmed_area_id:
        # Could extract intent from area metadata if available
        pass
    
    state["compliance_profile"] = compliance_profile

    # Set active_project_id for downstream workflow
    if state.get("csod_primary_project_id"):
        state["active_project_id"] = state["csod_primary_project_id"]

    # Set selected_data_sources
    selected_datasource = state.get("csod_selected_datasource", "")
    if selected_datasource:
        state["selected_data_sources"] = [selected_datasource]

    # Signal the invocation service to chain to the downstream workflow.
    # next_agent_id uses hyphens to match the registered agent ID (e.g. "csod-workflow").
    target = state["csod_target_workflow"]
    next_agent = target.replace("_", "-")  # "csod_workflow" → "csod-workflow"
    state["is_planner_output"] = True
    state["next_agent_id"] = next_agent
    # Enable interactive checkpoints in the CSOD workflow (metric selection, goal intent)
    state["csod_interactive_checkpoints"] = True

    logger.info(f"Routing to {target} → chaining to agent '{next_agent}'")

    return state


# ============================================================================
# Generic Routing Function - The Interrupt Mechanism
# ============================================================================

def _route_with_interrupt(state: EnhancedCompliancePipelineState) -> str:
    """
    Generic routing function used at every conversation node.
    
    Checks if checkpoint is set and not resolved - if so, route to 'interrupt' (END).
    Otherwise, clear checkpoint and route to 'continue'.
    """
    checkpoint_data = state.get("csod_conversation_checkpoint")
    
    if checkpoint_data and not state.get("csod_checkpoint_resolved"):
        return "interrupt"  # → END, API handles client interaction
    
    # Clear checkpoint and continue
    state["csod_conversation_checkpoint"] = None
    state["csod_checkpoint_resolved"] = False
    
    return "continue"


def _route_after_concept_confirm(state: EnhancedCompliancePipelineState) -> str:
    """
    After concept_confirm: must pause for the concept UI even when csod_checkpoint_resolved
    was left True by goal_intent / earlier nodes (otherwise we clear the checkpoint and
    scoping/area_matcher run with no csod_confirmed_concept_ids → empty areas → rephrase UI).
    """
    checkpoint = state.get("csod_conversation_checkpoint") or {}
    phase = checkpoint.get("phase")
    turn = checkpoint.get("turn") or {}
    pending_concept_ui = phase == "concept_confirm" and bool(turn)

    confirmed = [str(x) for x in (state.get("csod_confirmed_concept_ids") or []) if x]
    concept_resp = (state.get("csod_checkpoint_responses") or {}).get("concept_select")
    if isinstance(concept_resp, dict) and concept_resp.get("csod_confirmed_concept_ids"):
        confirmed = [str(x) for x in concept_resp["csod_confirmed_concept_ids"] if x]

    if pending_concept_ui and confirmed:
        state["csod_conversation_checkpoint"] = None
        state["csod_checkpoint_resolved"] = False
        return "continue"

    if pending_concept_ui:
        return "interrupt"

    return _route_with_interrupt(state)


# ============================================================================
# Node Wrappers (to inject config)
# ============================================================================

def _wrap_node(node_func, config: VerticalConversationConfig):
    """Wrap a node function to inject config."""
    def wrapped(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
        return node_func(state, config)
    return wrapped


# ============================================================================
# Workflow Builder
# ============================================================================

def build_conversation_planner_workflow(config: VerticalConversationConfig) -> StateGraph:
    """
    Build the conversation planner workflow with interrupt mechanism.
    
    Args:
        config: VerticalConversationConfig instance
    
    Returns:
        Un-compiled StateGraph
    """
    workflow = StateGraph(EnhancedCompliancePipelineState)
    
    # Add nodes
    workflow.add_node("goal_intent", _wrap_node(goal_intent_node, config))
    workflow.add_node("goal_output_intent", _wrap_node(goal_output_intent_node, config))
    workflow.add_node("datasource_selector", _wrap_node(datasource_selector_node, config))
    workflow.add_node("intent_splitter", _wrap_node(intent_splitter_node, config))
    workflow.add_node("mdl_project_resolver", _wrap_node(mdl_project_resolver_node, config))
    workflow.add_node("intent_confirm", _wrap_node(csod_intent_confirm_node, config))
    workflow.add_node("preliminary_area_matcher", _wrap_node(preliminary_area_matcher_node, config))
    workflow.add_node("scoping", _wrap_node(scoping_node, config))
    workflow.add_node("concept_confirm", _wrap_node(concept_confirm_node, config))
    workflow.add_node("area_matcher", _wrap_node(area_matcher_node, config))
    workflow.add_node("area_confirm", _wrap_node(area_confirm_node, config))
    workflow.add_node("metric_narration", _wrap_node(metric_narration_node, config))
    workflow.add_node("workflow_router", _wrap_node(workflow_router_node, config))

    # Set entry point — skip goal_intent (moved to CSOD workflow after metrics recommender)
    workflow.set_entry_point("datasource_selector")

    workflow.add_conditional_edges(
        "datasource_selector",
        _route_with_interrupt,
        {
            "interrupt": END,
            "continue": "intent_splitter",
        },
    )

    workflow.add_edge("intent_splitter", "mdl_project_resolver")

    workflow.add_edge("mdl_project_resolver", "intent_confirm")

    workflow.add_conditional_edges(
        "intent_confirm",
        _route_with_interrupt,
        {
            "interrupt": END,
            "continue": "preliminary_area_matcher",
        },
    )

    workflow.add_edge("preliminary_area_matcher", "scoping")
    
    workflow.add_conditional_edges(
        "scoping",
        _route_with_interrupt,
        {
            "interrupt": END,
            "continue": "concept_confirm",
        },
    )

    workflow.add_conditional_edges(
        "concept_confirm",
        _route_after_concept_confirm,
        {
            "interrupt": END,
            "continue": "area_matcher",
        },
    )

    workflow.add_edge("area_matcher", "area_confirm")
    
    workflow.add_conditional_edges(
        "area_confirm",
        _route_with_interrupt,
        {
            "interrupt": END,
            "continue": "metric_narration",
        },
    )
    
    workflow.add_conditional_edges(
        "metric_narration",
        _route_with_interrupt,
        {
            "interrupt": END,
            "continue": "workflow_router",
        },
    )
    
    workflow.add_edge("workflow_router", END)
    
    return workflow


# ============================================================================
# App Factory
# ============================================================================

def create_conversation_planner_app(
    config: VerticalConversationConfig,
    checkpointer=None,
) -> Any:
    """
    Create and compile the conversation planner workflow.
    
    Args:
        config: VerticalConversationConfig instance
        checkpointer: Optional LangGraph checkpointer (defaults to MemorySaver)
    
    Returns:
        Compiled LangGraph application
    """
    if checkpointer is None:
        checkpointer = get_checkpointer()
    
    workflow = build_conversation_planner_workflow(config)
    return workflow.compile(checkpointer=checkpointer)

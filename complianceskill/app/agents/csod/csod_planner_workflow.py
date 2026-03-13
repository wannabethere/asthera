"""
CSOD Planner Workflow - Phase 0: Context Setup (LEGACY)

⚠️ DEPRECATED: This workflow has been replaced by app.conversation.planner_workflow
which provides multi-turn conversation support with interrupts.

This legacy workflow is kept for backward compatibility but should not be used for new features.
Use app.conversation.planner_workflow.build_conversation_planner_workflow() instead.

The new conversation engine provides:
- Multi-turn conversation with interrupt mechanism
- Scoping questions based on area filters
- Concept and area confirmation
- Metric narration
- Generic configuration system (works for any vertical)

This workflow handles the initial conversation phase before calling the main CSOD workflows:
1. Datasource selection
2. Concept selection (using L1 collection)
3. Recommendation area matching (using L2 collection)
4. Workflow routing (csod_workflow vs csod_metric_advisor_workflow)

After Phase 0 completes, the resolved state is passed to the appropriate downstream workflow.

Graph topology:
    csod_datasource_selector
      → csod_concept_resolver
        → csod_area_matcher
          → csod_workflow_router
            → [invoke csod_workflow OR csod_metric_advisor_workflow]
              → END
"""
import logging
from typing import Any, Dict, List, Optional

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.agents.state import EnhancedCompliancePipelineState
from app.core.dependencies import get_llm
from app.ingestion.registry_vector_lookup import (
    resolve_intent_to_concept,
    resolve_scoping_to_areas,
    ConceptMatch,
    RecommendationAreaMatch,
)

logger = logging.getLogger(__name__)

# Supported datasources
SUPPORTED_DATASOURCES = [
    {
        "id": "cornerstone",
        "display_name": "Cornerstone OnDemand",
        "description": "LMS platform — training, compliance, assessments, ILT",
    },
    # Add more as integrations are built
]

# Intent constant for metric advisor
ADVISOR_INTENT = "metric_kpi_advisor"


# ============================================================================
# Planner Nodes
# ============================================================================

def csod_datasource_selector_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Phase 0 Step A: Datasource selection.
    
    If datasource is not yet selected, prompts user to select.
    If already selected, passes through to concept resolver.
    """
    # Check if datasource is already selected
    selected_datasource = state.get("csod_selected_datasource")
    user_message = state.get("user_query", "").lower()
    
    if not selected_datasource:
        # Try to match from user message
        for ds in SUPPORTED_DATASOURCES:
            if ds["id"] in user_message or ds["display_name"].lower() in user_message:
                selected_datasource = ds["id"]
                break
        
        # Default to cornerstone if not specified
        if not selected_datasource:
            selected_datasource = "cornerstone"
            logger.info(f"No datasource specified, defaulting to {selected_datasource}")
    
    state["csod_selected_datasource"] = selected_datasource
    state["csod_available_datasources"] = SUPPORTED_DATASOURCES
    
    # Add checkpoint for user interaction if needed
    if not state.get("csod_datasource_confirmed"):
        state["csod_planner_checkpoint"] = {
            "phase": "datasource_select",
            "message": "Which platform are you analyzing today?",
            "options": [
                {"id": ds["id"], "label": ds["display_name"], "description": ds["description"]}
                for ds in SUPPORTED_DATASOURCES
            ],
            "requires_user_input": True,
        }
        return state
    
    state["csod_datasource_confirmed"] = True
    return state


def csod_concept_resolver_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Phase 0 Step B+C: Concept resolution using L1 collection.
    
    Resolves user query to concepts and extracts project_ids, mdl_table_refs.
    """
    user_query = state.get("user_query", "")
    selected_datasource = state.get("csod_selected_datasource", "cornerstone")
    
    if not user_query:
        logger.warning("No user query provided for concept resolution")
        state["csod_concept_matches"] = []
        return state
    
    # Resolve concepts using L1 collection
    try:
        concept_matches: List[ConceptMatch] = resolve_intent_to_concept(
            user_query=user_query,
            connected_source_ids=[selected_datasource],
            top_k=5,
        )
        
        # Extract resolved information
        selected_concepts = []
        all_project_ids = []
        all_mdl_table_refs = []
        
        for match in concept_matches[:3]:  # Top 3 concepts
            selected_concepts.append({
                "concept_id": match.concept_id,
                "display_name": match.display_name,
                "score": match.score,
                "coverage_confidence": match.coverage_confidence,
            })
            all_project_ids.extend(match.project_ids)
            all_mdl_table_refs.extend(match.mdl_table_refs)
        
        # Deduplicate
        all_project_ids = list(set(all_project_ids))
        all_mdl_table_refs = list(set(all_mdl_table_refs))
        
        state["csod_concept_matches"] = [
            {
                "concept_id": m.concept_id,
                "display_name": m.display_name,
                "score": m.score,
                "coverage_confidence": m.coverage_confidence,
                "project_ids": m.project_ids,
                "mdl_table_refs": m.mdl_table_refs,
            }
            for m in concept_matches
        ]
        state["csod_selected_concepts"] = selected_concepts
        state["csod_resolved_project_ids"] = all_project_ids
        state["csod_resolved_mdl_table_refs"] = all_mdl_table_refs
        
        # Set primary project_id (first match)
        if all_project_ids:
            state["csod_primary_project_id"] = all_project_ids[0]
        
        logger.info(
            f"Resolved {len(selected_concepts)} concepts, "
            f"{len(all_project_ids)} project_ids, "
            f"{len(all_mdl_table_refs)} mdl_table_refs"
        )
        
    except Exception as e:
        logger.error(f"Error in concept resolution: {e}", exc_info=True)
        state["csod_concept_matches"] = []
        state["csod_selected_concepts"] = []
        state["csod_resolved_project_ids"] = []
        state["csod_resolved_mdl_table_refs"] = []
    
    return state


def csod_area_matcher_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Phase 0 Step D: Recommendation area matching using L2 collection.
    
    Matches user query and scoping to recommendation areas.
    Optionally generates confirmation message using prompt if generate_confirmation=True.
    """
    user_query = state.get("user_query", "")
    selected_concepts = state.get("csod_selected_concepts", [])
    scoping_answers = state.get("csod_scoping_answers", {})
    # REMOVED: csod_generate_area_confirmation flag - always generate confirmation now
    
    if not selected_concepts:
        logger.warning("No selected concepts for area matching")
        state["csod_area_matches"] = []
        return state
    
    # Use primary concept for area matching
    primary_concept_id = selected_concepts[0]["concept_id"] if selected_concepts else None
    
    if not primary_concept_id:
        state["csod_area_matches"] = []
        return state
    
    try:
        # Resolve recommendation areas using L2 collection
        area_matches: List[RecommendationAreaMatch] = resolve_scoping_to_areas(
            scoping_answers=scoping_answers,
            confirmed_concept_id=primary_concept_id,
            top_k=3,
        )
        
        state["csod_area_matches"] = [
            {
                "area_id": a.area_id,
                "concept_id": a.concept_id,
                "display_name": a.display_name,
                "score": a.score,
                "metrics": a.metrics,
                "kpis": a.kpis,
                "filters": a.filters,
                "causal_paths": a.causal_paths,
                "data_requirements": a.data_requirements,
            }
            for a in area_matches
        ]
        
        # Set primary area (first match)
        if area_matches:
            primary_area = area_matches[0]
            state["csod_primary_area"] = {
                "area_id": primary_area.area_id,
                "display_name": primary_area.display_name,
                "metrics": primary_area.metrics,
                "kpis": primary_area.kpis,
                "data_requirements": primary_area.data_requirements,
                "causal_paths": primary_area.causal_paths,
            }
        
        # Always generate confirmation message (removed flag check)
        if area_matches:
            confirmation = _generate_area_confirmation(
                user_query=user_query,
                selected_concepts=selected_concepts,
                area_matches=area_matches,
            )
            state["csod_area_confirmation"] = confirmation
        
        logger.info(f"Matched {len(area_matches)} recommendation areas")
        
    except Exception as e:
        logger.error(f"Error in area matching: {e}", exc_info=True)
        state["csod_area_matches"] = []
    
    return state


def _generate_area_confirmation(
    user_query: str,
    selected_concepts: List[Dict[str, Any]],
    area_matches: List[RecommendationAreaMatch],
) -> Dict[str, Any]:
    """
    Generate area confirmation message using prompt from prompt_utils.
    
    Args:
        user_query: Original user question
        selected_concepts: List of selected concept dicts
        area_matches: List of matched recommendation areas
    
    Returns:
        Dict with "message" and "primary_area_id"
    """
    try:
        from app.agents.prompt_loader import load_prompt, PROMPTS_CSOD
        from app.core.dependencies import get_llm
        import json
        
        # Load prompt
        prompt_text = load_prompt("10_area_confirmation", prompts_dir=str(PROMPTS_CSOD))
        
        # Format areas for prompt
        concept_names = ", ".join(c.get("display_name", c.get("concept_id", "")) for c in selected_concepts)
        areas_text = "\n".join(
            f"- {a.display_name} (score: {a.score:.2f})\n  {getattr(a, 'description', '')}"
            for a in area_matches[:3]
        )
        
        # Build human message with context
        human_message = f"""User question: {user_query}
Selected concepts: {concept_names}
Matched analysis areas:
{areas_text}"""
        
        # Get LLM
        llm = get_llm()
        
        # Generate response using system prompt + human message
        from langchain_core.prompts import ChatPromptTemplate
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", prompt_text),
            ("human", "{input}"),
        ])
        chain = prompt_template | llm
        response = chain.invoke({"input": human_message})
        response_content = response.content if hasattr(response, "content") else str(response)
        
        # Parse JSON response
        try:
            result = json.loads(response_content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                # Fallback: create simple confirmation
                primary_area = area_matches[0] if area_matches else None
                result = {
                    "message": (
                        f"I understand you're asking about {user_query}. "
                        f"I've identified {len(area_matches)} relevant analysis areas. "
                        f"Would you like me to proceed with analyzing these?"
                    ),
                    "primary_area_id": primary_area.area_id if primary_area else "",
                }
        
        return result
        
    except Exception as e:
        logger.error(f"Error generating area confirmation: {e}", exc_info=True)
        # Fallback confirmation
        primary_area = area_matches[0] if area_matches else None
        return {
            "message": (
                f"I understand you're asking about {user_query}. "
                f"I've identified {len(area_matches)} relevant analysis areas. "
                f"Would you like me to proceed?"
            ),
            "primary_area_id": primary_area.area_id if primary_area else "",
        }


def csod_workflow_router_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Phase 0 Final: Route to appropriate downstream workflow.
    
    Determines whether to use csod_workflow or csod_metric_advisor_workflow
    based on intent and user query.
    """
    user_query = state.get("user_query", "").lower()
    primary_area = state.get("csod_primary_area", {})
    
    # Check if this is a metric advisor request
    advisor_keywords = ["advisor", "recommend", "suggest", "what metrics", "which kpis", "help me choose"]
    is_advisor_request = any(kw in user_query for kw in advisor_keywords)
    
    # Also check if user explicitly wants advisor workflow
    use_advisor = state.get("csod_use_advisor_workflow", False)
    
    if is_advisor_request or use_advisor:
        state["csod_target_workflow"] = "csod_metric_advisor_workflow"
        state["csod_intent"] = ADVISOR_INTENT
    else:
        state["csod_target_workflow"] = "csod_workflow"
        # Intent will be determined by csod_intent_classifier in the main workflow
    
    # Prepare state for downstream workflow
    # Build compliance_profile with resolved context
    compliance_profile = state.get("compliance_profile", {})
    
    # Add registry-resolved context
    compliance_profile.update({
        "selected_concepts": [c["concept_id"] for c in state.get("csod_selected_concepts", [])],
        "selected_area_ids": [a["area_id"] for a in state.get("csod_area_matches", [])],
        "priority_metrics": primary_area.get("metrics", []),
        "priority_kpis": primary_area.get("kpis", []),
        "data_requirements": primary_area.get("data_requirements", []),
        "causal_paths": primary_area.get("causal_paths", []),
        "active_mdl_tables": state.get("csod_resolved_mdl_table_refs", []),
    })
    
    state["compliance_profile"] = compliance_profile
    
    # Set active_project_id for downstream workflow
    if state.get("csod_primary_project_id"):
        state["active_project_id"] = state["csod_primary_project_id"]
    
    # Set selected_data_sources
    selected_datasource = state.get("csod_selected_datasource", "cornerstone")
    state["selected_data_sources"] = [selected_datasource]
    
    logger.info(f"Routing to {state['csod_target_workflow']}")
    
    return state


# ============================================================================
# Routing functions
# ============================================================================

def _route_after_datasource_selector(state: EnhancedCompliancePipelineState) -> str:
    """After datasource selection, go to concept resolver."""
    # REMOVED: csod_planner_checkpoint check - use csod_conversation_checkpoint instead
    # This routing function is legacy - new conversation engine uses _route_with_interrupt
    return "csod_concept_resolver"


def _route_after_concept_resolver(state: EnhancedCompliancePipelineState) -> str:
    """After concept resolution, go to area matcher."""
    return "csod_area_matcher"


def _route_after_area_matcher(state: EnhancedCompliancePipelineState) -> str:
    """After area matching, go to workflow router."""
    return "csod_workflow_router"


def _route_after_workflow_router(state: EnhancedCompliancePipelineState) -> str:
    """After routing, workflow is ready to invoke downstream."""
    return "end"


# ============================================================================
# Workflow builder
# ============================================================================

def build_csod_planner_workflow() -> StateGraph:
    """
    Build the CSOD planner workflow for Phase 0 context setup.
    """
    workflow = StateGraph(EnhancedCompliancePipelineState)
    
    # Add nodes
    workflow.add_node("csod_datasource_selector", csod_datasource_selector_node)
    workflow.add_node("csod_concept_resolver", csod_concept_resolver_node)
    workflow.add_node("csod_area_matcher", csod_area_matcher_node)
    workflow.add_node("csod_workflow_router", csod_workflow_router_node)
    
    # Set entry point
    workflow.set_entry_point("csod_datasource_selector")
    
    # Add edges
    workflow.add_conditional_edges(
        "csod_datasource_selector",
        _route_after_datasource_selector,
        {
            "csod_concept_resolver": "csod_concept_resolver",
            "wait_for_user_input": END,  # API layer handles user input
        },
    )
    
    workflow.add_conditional_edges(
        "csod_concept_resolver",
        _route_after_concept_resolver,
        {"csod_area_matcher": "csod_area_matcher"},
    )
    
    workflow.add_conditional_edges(
        "csod_area_matcher",
        _route_after_area_matcher,
        {"csod_workflow_router": "csod_workflow_router"},
    )
    
    workflow.add_conditional_edges(
        "csod_workflow_router",
        _route_after_workflow_router,
        {"end": END},
    )
    
    return workflow


# ============================================================================
# App factory
# ============================================================================

def create_csod_planner_app(checkpointer=None):
    """
    Create and compile the CSOD planner workflow.
    
    Args:
        checkpointer: Optional LangGraph checkpointer (defaults to MemorySaver).
    Returns:
        Compiled LangGraph application.
    """
    if checkpointer is None:
        checkpointer = MemorySaver()
    return build_csod_planner_workflow().compile(checkpointer=checkpointer)


def get_csod_planner_app():
    """Convenience: return default CSOD planner app."""
    return create_csod_planner_app()


# ============================================================================
# Initial state factory
# ============================================================================

def create_csod_planner_initial_state(
    user_query: str,
    session_id: str,
    datasource: Optional[str] = None,
    scoping_answers: Optional[Dict[str, Any]] = None,
    use_advisor_workflow: bool = False,
) -> Dict[str, Any]:
    """
    Build initial state for the CSOD planner workflow.
    
    Args:
        user_query: Natural language query
        session_id: Unique session identifier
        datasource: Pre-selected datasource (optional)
        scoping_answers: Pre-filled scoping answers (optional)
        use_advisor_workflow: Force advisor workflow (optional)
    
    Returns:
        Initial state dict
    """
    import uuid
    from datetime import datetime
    
    return {
        # Core
        "user_query": user_query,
        "session_id": session_id or str(uuid.uuid4()),
        "messages": [],
        "created_at": datetime.utcnow(),
        
        # Planner-specific fields
        "csod_selected_datasource": datasource,
        "csod_datasource_confirmed": datasource is not None,
        "csod_scoping_answers": scoping_answers or {},
        "csod_use_advisor_workflow": use_advisor_workflow,
        
        # Will be populated by nodes
        "csod_concept_matches": [],
        "csod_selected_concepts": [],
        "csod_resolved_project_ids": [],
        "csod_resolved_mdl_table_refs": [],
        "csod_primary_project_id": None,
        "csod_area_matches": [],
        "csod_primary_area": {},
        "csod_target_workflow": None,
        # REMOVED: csod_planner_checkpoint - use csod_conversation_checkpoint instead
        
        # Base state fields
        "compliance_profile": {},
        "active_project_id": None,
        "selected_data_sources": [],
    }


# ============================================================================
# Helper: Invoke downstream workflow
# ============================================================================

def invoke_downstream_workflow(
    planner_state: Dict[str, Any],
    csod_app=None,
    csod_metric_advisor_app=None,
) -> Dict[str, Any]:
    """
    Invoke the appropriate downstream workflow based on planner routing.
    
    Args:
        planner_state: Final state from planner workflow
        csod_app: Compiled csod_workflow app (optional, will create if None)
        csod_metric_advisor_app: Compiled csod_metric_advisor_workflow app (optional)
    
    Returns:
        Final state from downstream workflow
    """
    target_workflow = planner_state.get("csod_target_workflow", "csod_workflow")
    
    if target_workflow == "csod_metric_advisor_workflow":
        from app.agents.csod.csod_metric_advisor_workflow import (
            get_csod_metric_advisor_app,
            create_csod_metric_advisor_initial_state,
        )
        
        if csod_metric_advisor_app is None:
            csod_metric_advisor_app = get_csod_metric_advisor_app()
        
        # Build initial state for metric advisor workflow
        initial_state = create_csod_metric_advisor_initial_state(
            user_query=planner_state.get("user_query", ""),
            session_id=planner_state.get("session_id", ""),
            active_project_id=planner_state.get("active_project_id"),
            selected_data_sources=planner_state.get("selected_data_sources", []),
            compliance_profile=planner_state.get("compliance_profile", {}),
            causal_graph_enabled=True,  # Default for advisor
            causal_vertical="lms",
        )
        
        # Merge planner state into initial state
        initial_state.update(planner_state)
        
        logger.info("Invoking csod_metric_advisor_workflow")
        return csod_metric_advisor_app.invoke(initial_state)
    
    else:
        from app.agents.csod.csod_workflow import (
            get_csod_app,
            create_csod_initial_state,
        )
        
        if csod_app is None:
            csod_app = get_csod_app()
        
        # Build initial state for main CSOD workflow
        initial_state = create_csod_initial_state(
            user_query=planner_state.get("user_query", ""),
            session_id=planner_state.get("session_id", ""),
            active_project_id=planner_state.get("active_project_id"),
            selected_data_sources=planner_state.get("selected_data_sources", []),
            compliance_profile=planner_state.get("compliance_profile", {}),
            causal_graph_enabled=planner_state.get("csod_causal_graph_enabled", False),
            causal_vertical="lms",
        )
        
        # Merge planner state into initial state
        initial_state.update(planner_state)
        
        logger.info("Invoking csod_workflow")
        return csod_app.invoke(initial_state)


if __name__ == "__main__":
    app = get_csod_planner_app()
    print("CSOD Planner workflow compiled successfully!")
    print(f"Nodes: {list(app.nodes.keys())}")

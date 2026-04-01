"""
CSOD LangGraph Adapter

Specialized adapter for CSOD workflows with CSOD-specific checkpoint handling.
"""

import logging
from typing import Dict, Any, Optional, List

from app.adapters.base_langgraph_adapter import BaseLangGraphAdapter
from app.adapters.base import ComposedContext
from typing import Dict, Any, Any as AnyType

logger = logging.getLogger(__name__)


class CSODLangGraphAdapter(BaseLangGraphAdapter):
    """
    CSOD-specific LangGraph adapter.
    
    Handles CSOD-specific checkpoint formats and state preservation.
    """

    NARRATOR_NODES = {
        "csod_concept_resolver",
        "csod_skill_identifier",
        "csod_scoping_node",
        "csod_area_matcher",
        "csod_workflow_router",
    }

    NEXT_STEP_LABELS = {
        "csod_concept_resolver": "understanding what kind of analysis you need",
        "csod_skill_identifier": "gathering a bit of context before searching",
        "csod_scoping_node": "finding the best analysis framework for your question",
        "csod_area_matcher": "selecting the right agent to answer your question",
        "csod_workflow_router": None,
    }
    
    def get_narrator_nodes(self):
        """Nodes that trigger the planner narrator stream."""
        return self.NARRATOR_NODES

    def get_narrator_prompt_path(self):
        """Path to CSOD prompts for the narrator."""
        from app.agents.prompt_loader import PROMPTS_CSOD
        from pathlib import Path
        return Path(PROMPTS_CSOD)

    def get_next_step_label(self, node_name: str) -> Optional[str]:
        """Human-readable label for what runs after this node."""
        return self.NEXT_STEP_LABELS.get(node_name)
    
    def get_preserved_state_keys(self) -> List[str]:
        """
        Get list of CSOD state keys to preserve when resuming from checkpoint.
        
        Returns:
            List of CSOD state key names to preserve
        """
        return [
            # concept phase
            "csod_concept_matches",
            "csod_selected_concepts",
            "csod_confirmed_concept_ids",
            "csod_concepts_confirmed",
            "csod_llm_resolved_areas",
            # datasource phase
            "csod_available_datasources",
            "csod_selected_datasource",
            "csod_datasource_confirmed",
            # scoping phase
            "csod_scoping_answers",
            "csod_preliminary_area_matches",
            # area phase
            "csod_area_matches",
            "csod_primary_area",
            "csod_confirmed_area_id",
            # metric narration phase
            "csod_metric_narration",
            # cross-concept phase
            "csod_cross_concept_areas",
            # general
            "csod_checkpoint_responses",
            "csod_reasoning_narrative",
            "user_query",
        ]
    
    def get_checkpoint_response_fields(self) -> List[str]:
        """
        Get list of payload keys that indicate CSOD checkpoint resume.
        When any of these are present we restore state from checkpointer so
        concept/selected_concepts etc. are not lost when responding to scoping.
        """
        return [
            "csod_concepts_confirmed",
            "csod_datasource_confirmed",
            "csod_concept_matches",
            "csod_scoping_answers",           # Scoping checkpoint response
            "goal_intent",                    # Goal intent checkpoint response
            "goal_output_intents",
            "csod_confirmed_area_id",         # Area confirm checkpoint response
            "csod_confirmed_concept_ids",
            "csod_metric_narration_confirmed", # Metric narration confirm checkpoint response
            "csod_selected_metric_ids",       # Metric selection checkpoint response
            "csod_metrics_user_confirmed",    # Metric selection confirmed flag
            "csod_cross_concept_confirmed",   # Cross-concept check checkpoint response
        ]
    
    def extract_checkpoint_from_state(self, state: Dict[str, Any], node_name: str) -> Optional[Dict[str, Any]]:
        """
        Extract CSOD-specific checkpoint information from state.
        
        Args:
            state: LangGraph state dictionary
            node_name: Name of the node that may have created a checkpoint
        
        Returns:
            Checkpoint dictionary if found, None otherwise
        """
        # Check for CSOD conversation checkpoint (area_confirm, concept_confirm, scoping, etc.)
        # These are produced by area_confirm_node, concept_confirm_node, scoping_node using
        # ConversationCheckpoint.to_dict() and stored as csod_conversation_checkpoint.
        csod_conv_checkpoint = state.get("csod_conversation_checkpoint")
        if csod_conv_checkpoint and isinstance(csod_conv_checkpoint, dict):
            # Only emit if checkpoint is unresolved (waiting for user)
            # Default False: if checkpoint exists, assume it needs resolution
            if not state.get("csod_checkpoint_resolved", False):
                phase = csod_conv_checkpoint.get("phase", "unknown")
                turn = csod_conv_checkpoint.get("turn", {})
                return {
                    "checkpoint_id": f"{phase}_checkpoint",
                    "checkpoint_type": phase,
                    "node": node_name,
                    "data": csod_conv_checkpoint,
                    "message": turn.get("message", "Waiting for user input"),
                    "requires_user_input": True,
                    "phase": phase,
                    "options": turn.get("options", []),
                    "metadata": turn.get("metadata", {}),
                    "resume_with_field": csod_conv_checkpoint.get("resume_with_field"),
                }

        # Check for CSOD planner checkpoint (legacy/deprecated)
        csod_checkpoint = state.get("csod_planner_checkpoint")
        if csod_checkpoint and isinstance(csod_checkpoint, dict):
            if csod_checkpoint.get("requires_user_input", False):
                return {
                    "checkpoint_id": f"{node_name}_checkpoint",
                    "checkpoint_type": csod_checkpoint.get("phase", "unknown"),
                    "node": node_name,
                    "data": csod_checkpoint,
                    "message": csod_checkpoint.get("message", "Waiting for user input"),
                    "requires_user_input": True,
                    "phase": csod_checkpoint.get("phase"),
                    "options": csod_checkpoint.get("options", []),
                }

        # Fall back to generic checkpoint extraction
        return super().extract_checkpoint_from_state(state, node_name)
    
    def _build_graph_input(
        self,
        payload: Dict[str, Any],
        context: ComposedContext
    ) -> Dict[str, Any]:
        """
        Build CSOD-specific LangGraph input state.
        
        Args:
            payload: Agent invocation payload
            context: Composed context
        
        Returns:
            LangGraph input state dict with CSOD-specific fields
        """
        # Start with base graph input
        graph_input = super()._build_graph_input(payload, context)

        # For a fresh query (no checkpoint response fields present), explicitly reset all
        # conversation-phase state so LangGraph's MemorySaver doesn't bleed stale values
        # from a prior turn (old csod_confirmed_concept_ids, csod_scoping_answers, etc.)
        # into the new run.  Without these overrides LangGraph merges the saved checkpoint
        # state with graph_input, causing concept_confirm / scoping_node to skip and
        # area_matcher to use stale concept IDs → empty area_matches → "Let me rephrase".
        resume_fields = self.get_checkpoint_response_fields()
        # checkpoint_type is always set in the payload for checkpoint resumes.
        # We cannot rely solely on resume_fields values because some responses
        # (e.g. "Apply Defaults" on scoping) send an empty dict {} which is falsy.
        is_checkpoint_resume = (
            any(payload.get(f) for f in resume_fields)
            or bool(payload.get("checkpoint_type"))
        )
        is_planner_chain = bool(payload.get("planner_output"))
        if not is_checkpoint_resume and not is_planner_chain:
            graph_input.update({
                # concept phase
                "csod_concept_matches": None,
                "csod_selected_concepts": None,
                "csod_confirmed_concept_ids": None,
                "csod_concepts_confirmed": None,
                "csod_checkpoint_responses": None,
                "csod_resolved_project_ids": None,
                "csod_resolved_mdl_table_refs": None,
                "csod_primary_project_id": None,
                # datasource phase  (keep if payload explicitly sets it, but clear stale flag)
                "csod_datasource_confirmed": None,
                # scoping phase
                "csod_scoping_answers": None,
                "csod_scoping_complete": None,
                "csod_preliminary_area_matches": None,
                # area phase
                "csod_area_matches": None,
                "csod_primary_area": None,
                "csod_confirmed_area_id": None,
                "csod_area_confirmation": None,
                # LLM-resolved areas cache (re-resolved per query)
                "csod_llm_resolved_areas": None,
                # general conversation checkpoint
                "csod_conversation_checkpoint": None,
                "csod_checkpoint_resolved": None,
                # goal intent (re-infer from new query)
                "goal_intent": None,
                "goal_output_intents": None,
                "goal_output_classifier_result": None,
                # metric narration
                "csod_metric_narration": None,
                "csod_metric_narration_confirmed": None,
                # cross-concept check
                "csod_cross_concept_confirmed": None,
                "csod_cross_concept_areas": None,
                "csod_additional_area_ids": None,
            })
            logger.info("Fresh query detected — reset conversation-phase state to prevent MemorySaver bleed")

        # Check if planner output is available (from csod-planner)
        planner_output = payload.get("planner_output")
        
        # Check if conversation state is available (from Phase 0)
        conversation_state = payload.get("conversation_state")
        
        # If planner output is available, use it to build enriched initial state
        if planner_output:
            graph_input.update({
                "user_query": planner_output.get("user_query", payload.get("input", "")),
                "session_id": planner_output.get("session_id", payload.get("thread_id", "")),
                "active_project_id": planner_output.get("active_project_id") or payload.get("active_project_id"),
                "selected_data_sources": planner_output.get("selected_data_sources", []) or payload.get("selected_data_sources", []),
                "compliance_profile": planner_output.get("compliance_profile", {}) or payload.get("compliance_profile", {}),
            })
            
            # Add CSOD-specific fields from planner
            for key in [
                "csod_selected_datasource",
                "csod_selected_concepts",
                "csod_resolved_project_ids",
                "csod_resolved_mdl_table_refs",
                "csod_primary_project_id",
                "csod_area_matches",
                "csod_primary_area",
                "csod_intent",
                "csod_identified_skills",
                "csod_primary_skill",
                "csod_causal_graph_enabled",
                "csod_target_workflow",
                "csod_scoping_answers",
                "csod_scoping_complete",
                "csod_interactive_checkpoints",
                # Checkpoint-resume fields: passed back through csod-planner state
                # when the user responds to metric_selection or goal_intent checkpoints.
                # Without these the csod-workflow graph resumes without the user's choices.
                "csod_selected_metric_ids",
                "csod_metrics_user_confirmed",
                "goal_intent",
                "goal_output_intents",
            ]:
                if key in planner_output:
                    graph_input[key] = planner_output[key]

            # When a metric_selection or goal_intent checkpoint was just resolved
            # (user responded, csod-planner propagated the answer), clear the stale
            # csod_conversation_checkpoint so the CSOD workflow graph resumes cleanly
            # without re-emitting the same checkpoint.
            if planner_output.get("csod_selected_metric_ids") is not None or planner_output.get("goal_intent"):
                graph_input["csod_conversation_checkpoint"] = None
                graph_input["csod_checkpoint_resolved"] = True
                if planner_output.get("csod_selected_metric_ids") is not None:
                    graph_input["csod_metrics_user_confirmed"] = True
                    logger.info(
                        "✓ Chain: passing csod_selected_metric_ids (%d) and clearing checkpoint",
                        len(planner_output.get("csod_selected_metric_ids") or []),
                    )
                if planner_output.get("goal_intent"):
                    logger.info(
                        "✓ Chain: passing goal_intent=%s and clearing checkpoint",
                        planner_output["goal_intent"],
                    )

            graph_input["csod_from_planner_chain"] = True
        
        # If conversation state is available (and no planner output), use it
        elif conversation_state and conversation_state.get("is_complete"):
            graph_input.update({
                "user_query": conversation_state.get("user_query", payload.get("input", "")),
                "session_id": conversation_state.get("session_id", payload.get("thread_id", "")),
                "active_project_id": conversation_state.get("active_project_id"),
                "selected_data_sources": conversation_state.get("selected_data_sources", []),
                "compliance_profile": conversation_state.get("compliance_profile", {}),
            })
            
            # Add CSOD-specific fields from conversation
            for key in [
                "csod_intent",
                "csod_resolved_project_ids",
                "csod_resolved_mdl_table_refs",
                "csod_selected_concepts",
                "csod_primary_area",
                "csod_target_workflow",
            ]:
                if key in conversation_state:
                    graph_input[key] = conversation_state[key]
        
        # Handle CSOD checkpoint response data (for resuming from checkpoints)
        # Build checkpoint responses state - consolidates all checkpoint responses
        checkpoint_responses = graph_input.get("csod_checkpoint_responses", {})
        
        # Datasource checkpoint response
        if payload.get("csod_datasource_confirmed") or payload.get("csod_selected_datasource"):
            checkpoint_responses["datasource_select"] = {
                "csod_selected_datasource": payload.get("csod_selected_datasource"),
                "csod_datasource_confirmed": payload.get("csod_datasource_confirmed", True),
            }
            # Also set directly for backward compatibility
            graph_input["csod_datasource_confirmed"] = True
            if payload.get("csod_selected_datasource"):
                graph_input["csod_selected_datasource"] = payload["csod_selected_datasource"]
            # Clear stale conversation checkpoint (datasource_select) so LangGraph's channel
            # merge puts None into state — without this, the checkpointer's datasource_select
            # checkpoint bleeds into the initial state and _route_with_interrupt's in-function
            # mutation (which doesn't persist in LangGraph channels) fails to clear it, causing
            # concept_resolver to see a stale checkpoint and skip concept resolution.
            graph_input["csod_conversation_checkpoint"] = None
            graph_input["csod_checkpoint_resolved"] = True
            logger.info("✓ Datasource confirmed — cleared stale conversation checkpoint")
        
        # Goal intent checkpoint response
        if payload.get("goal_intent"):
            graph_input["goal_intent"] = payload["goal_intent"]
            graph_input["csod_conversation_checkpoint"] = None
            graph_input["csod_checkpoint_resolved"] = True
            logger.info(f"✓ Goal intent response: goal_intent={payload['goal_intent']}")
        if payload.get("goal_output_intents") is not None:
            graph_input["goal_output_intents"] = payload["goal_output_intents"]
            logger.info(
                "✓ Goal output intents: %s",
                payload["goal_output_intents"],
            )

        # Metric selection checkpoint response
        if payload.get("csod_selected_metric_ids") is not None or payload.get("selected_metric_ids") is not None:
            selected = payload.get("csod_selected_metric_ids") or payload.get("selected_metric_ids") or []
            graph_input["csod_selected_metric_ids"] = selected
            graph_input["csod_metrics_user_confirmed"] = True
            graph_input["csod_conversation_checkpoint"] = None
            graph_input["csod_checkpoint_resolved"] = True
            logger.info(f"✓ Metric selection response: {len(selected)} metrics selected")

        # Concept checkpoint response
        if payload.get("csod_concepts_confirmed") or payload.get("csod_confirmed_concept_ids"):
            concept_ids_from_payload = payload.get("csod_confirmed_concept_ids") or []
            concept_response = {
                "csod_confirmed_concept_ids": concept_ids_from_payload,
                "csod_concepts_confirmed": payload.get("csod_concepts_confirmed", True),
            }
            if payload.get("csod_concept_matches"):
                concept_response["csod_concept_matches"] = payload["csod_concept_matches"]
            checkpoint_responses["concept_select"] = concept_response

            graph_input["csod_concepts_confirmed"] = True
            # Clear stale conversation checkpoint so it doesn't fire interrupts in every node
            graph_input["csod_conversation_checkpoint"] = None
            graph_input["csod_checkpoint_resolved"] = True
            # Only set confirmed IDs directly if explicitly provided (non-empty)
            if concept_ids_from_payload:
                graph_input["csod_confirmed_concept_ids"] = concept_ids_from_payload
            if payload.get("csod_concept_matches"):
                concept_matches = payload["csod_concept_matches"]
                graph_input["csod_concept_matches"] = concept_matches
                logger.info(f"✓ Loaded {len(concept_matches)} concept matches from resume payload")
                if concept_matches:
                    ids = [m.get("concept_id") for m in concept_matches if isinstance(m, dict)]
                    logger.info(f"  Concept IDs: {ids}")
        
        # Store checkpoint responses in state
        if checkpoint_responses:
            graph_input["csod_checkpoint_responses"] = checkpoint_responses
            logger.info(f"✓ Built checkpoint responses state with phases: {list(checkpoint_responses.keys())}")
            if "csod_planner_checkpoint" in graph_input:
                graph_input["csod_planner_checkpoint"] = None

        # Area confirm checkpoint response (user selected a recommendation area)
        if payload.get("csod_confirmed_area_id"):
            area_id = payload["csod_confirmed_area_id"]
            checkpoint_responses["area_confirm"] = {
                "csod_confirmed_area_id": area_id,
            }
            graph_input["csod_confirmed_area_id"] = area_id
            # Clear the conversation checkpoint so routing continues past area_confirm node
            graph_input["csod_conversation_checkpoint"] = None
            logger.info(f"✓ Area confirm response: csod_confirmed_area_id={area_id}")

        # Metric narration confirmation checkpoint response
        if payload.get("csod_metric_narration_confirmed"):
            graph_input["csod_metric_narration_confirmed"] = True
            graph_input["csod_conversation_checkpoint"] = None
            graph_input["csod_checkpoint_resolved"] = True
            logger.info("✓ Metric narration confirmed — advancing past narration checkpoint")

        # Cross-concept check confirmation checkpoint response
        if payload.get("csod_cross_concept_confirmed"):
            graph_input["csod_cross_concept_confirmed"] = True
            # Store the selected additional area IDs if user picked any
            if payload.get("csod_additional_area_ids"):
                graph_input["csod_additional_area_ids"] = payload["csod_additional_area_ids"]
            graph_input["csod_conversation_checkpoint"] = None
            graph_input["csod_checkpoint_resolved"] = True
            logger.info(
                "✓ Cross-concept check confirmed — additional_area_ids=%s",
                payload.get("csod_additional_area_ids", []),
            )

        # Merge scoping answers from payload (when user responds to scoping checkpoint).
        # Use `is not None` — an empty dict {} means "Apply Defaults" (valid response, not missing).
        scoping_answers_from_payload = payload.get("csod_scoping_answers")
        if payload.get("checkpoint_type") == "scoping" or scoping_answers_from_payload is not None:
            existing = graph_input.get("csod_scoping_answers") or {}
            merged = {**existing, **(scoping_answers_from_payload or {})}
            graph_input["csod_scoping_answers"] = merged
            # Mark scoping complete so scoping_node doesn't re-create the checkpoint
            graph_input["csod_scoping_complete"] = True
            graph_input["csod_conversation_checkpoint"] = None
            graph_input["csod_checkpoint_resolved"] = True
            logger.info(
                "✓ Scoping checkpoint response — answers=%s (Apply Defaults=%s)",
                list(merged.keys()),
                not merged,
            )

        # Chain from planner: question lives on planner_output when follow-up payload.input is empty
        uq = (graph_input.get("user_query") or "").strip()
        if not uq:
            po = payload.get("planner_output") or {}
            pq = (po.get("user_query") or "").strip()
            if pq:
                graph_input["user_query"] = pq

        # Checkpoint resume often sends input=""; do not push empty user_query (overwrites checkpointer text)
        if is_checkpoint_resume and not (payload.get("input") or "").strip():
            if not (graph_input.get("user_query") or "").strip():
                graph_input.pop("user_query", None)

        # Always enable interactive checkpoints for agent-gateway invocations
        # so metric_selection_node and goal_intent_node emit checkpoints instead
        # of auto-confirming.  Set LAST so planner_output merges can't override.
        graph_input["csod_interactive_checkpoints"] = True

        return graph_input
    
    def _extract_workflow_metadata(self, final_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract CSOD-specific metadata from final state.
        
        Args:
            final_state: Final state from CSOD workflow
        
        Returns:
            Dictionary with CSOD-specific metadata
        """
        metadata = {}
        
        # Check if this is planner output
        if final_state.get("is_planner_output"):
            metadata["is_planner_output"] = True
            metadata["next_agent_id"] = final_state.get("next_agent_id")
            metadata["target_workflow"] = final_state.get("csod_target_workflow")
            logger.info(f"Planner output detected in final state: next_agent={final_state.get('next_agent_id')}")
        
        return metadata
    
    def _log_preserved_state_key(self, key: str, value: AnyType) -> None:
        """
        Log CSOD-specific information about preserved state keys.
        
        Args:
            key: State key name
            value: State value that was preserved
        """
        # For concept_matches, log the concept IDs
        if key == "csod_concept_matches" and isinstance(value, list):
            concept_ids = [m.get("concept_id") for m in value if isinstance(m, dict)]
            if concept_ids:
                logger.info(f"  Concept IDs in preserved matches: {concept_ids}")

    # ──────────────────────────────────────────────────────────────────────
    # OUTPUT GRAPH (deploy-time) state builder
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def build_output_graph_input(
        phase1_state: Dict[str, Any],
        deploy_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build input state for the output/deploy graph from Phase 1 final state.

        Extracts the subset of Phase 1 state needed by the output pipeline
        and merges any deploy-time overrides (goal_intent, etc.).

        Args:
            phase1_state: Complete state dict from Phase 1 completion
            deploy_payload: Deploy-time overrides from the UI/middleware

        Returns:
            State dict ready for the output graph entry point (csod_goal_intent)
        """
        deploy_payload = deploy_payload or {}

        # Keys to carry over from Phase 1
        _PHASE1_CARRY_KEYS = [
            # Core identifiers
            "user_query", "session_id", "active_project_id",
            "selected_data_sources", "compliance_profile",
            # Intent & planning
            "csod_intent", "csod_intent_registry_id", "csod_stage_1_intent",
            "csod_identified_skills", "csod_primary_skill",
            "csod_target_workflow",
            # Causal graph
            "csod_causal_nodes", "csod_causal_edges",
            "csod_causal_graph_metadata", "csod_causal_centrality",
            "causal_signals", "causal_node_index",
            # Schemas & metrics
            "csod_resolved_schemas", "csod_retrieved_metrics",
            "csod_metric_recommendations", "csod_kpi_recommendations",
            "csod_table_recommendations", "csod_data_science_insights",
            "csod_selected_metric_ids", "csod_metrics_user_confirmed",
            # Decision tree
            "dt_scored_metrics", "dt_metric_groups", "dt_metric_decisions",
            # Metric qualification & layout
            "csod_metric_qualification_result", "csod_metrics_layout",
            # SQL previews
            "csod_metric_previews", "csod_sql_agent_results",
            # Config flags
            "csod_generate_sql", "csod_interactive_checkpoints",
            "csod_silver_gold_tables_only",
            # Messages
            "messages",
        ]

        output_state: Dict[str, Any] = {}
        for key in _PHASE1_CARRY_KEYS:
            if key in phase1_state and phase1_state[key] is not None:
                output_state[key] = phase1_state[key]

        # Merge deploy-time overrides
        if deploy_payload.get("goal_intent"):
            output_state["goal_intent"] = deploy_payload["goal_intent"]
        if deploy_payload.get("goal_output_intents") is not None:
            output_state["goal_output_intents"] = deploy_payload["goal_output_intents"]
        if "csod_generate_sql" in deploy_payload:
            output_state["csod_generate_sql"] = deploy_payload["csod_generate_sql"]

        logger.info(
            "Built output graph input: %d keys carried from Phase 1, goal_intent=%s",
            len(output_state),
            output_state.get("goal_intent", "<not set>"),
        )

        return output_state
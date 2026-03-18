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
            "csod_concept_matches",
            "csod_available_datasources",
            "csod_scoping_answers",
            "csod_selected_datasource",
            "csod_datasource_confirmed",
            "csod_selected_concepts",
            "csod_confirmed_concept_ids",
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
            "csod_scoping_answers",  # Responding to scoping checkpoint — must restore full state
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
        # Check for CSOD planner checkpoint
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
                    "phase": csod_checkpoint.get("phase"),  # Include phase for easier identification
                    "options": csod_checkpoint.get("options", []),  # Include options for easier access
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
            ]:
                if key in planner_output:
                    graph_input[key] = planner_output[key]
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
        
        # Concept checkpoint response
        if payload.get("csod_concepts_confirmed") or payload.get("csod_confirmed_concept_ids"):
            concept_response = {
                "csod_confirmed_concept_ids": payload.get("csod_confirmed_concept_ids", []),
                "csod_concepts_confirmed": payload.get("csod_concepts_confirmed", True),
            }
            if payload.get("csod_concept_matches"):
                concept_response["csod_concept_matches"] = payload["csod_concept_matches"]
            checkpoint_responses["concept_select"] = concept_response
            
            # Also set directly for backward compatibility
            graph_input["csod_concepts_confirmed"] = True
            if payload.get("csod_confirmed_concept_ids"):
                graph_input["csod_confirmed_concept_ids"] = payload["csod_confirmed_concept_ids"]
            if payload.get("csod_concept_matches"):
                concept_matches = payload["csod_concept_matches"]
                graph_input["csod_concept_matches"] = concept_matches
                logger.info(f"✓ Loaded {len(concept_matches)} concept matches from resume payload")
                if concept_matches:
                    concept_ids = [m.get("concept_id") for m in concept_matches if isinstance(m, dict)]
                    logger.info(f"  Concept IDs: {concept_ids}")
        
        # Store checkpoint responses in state
        if checkpoint_responses:
            graph_input["csod_checkpoint_responses"] = checkpoint_responses
            logger.info(f"✓ Built checkpoint responses state with phases: {list(checkpoint_responses.keys())}")
            if "csod_planner_checkpoint" in graph_input:
                graph_input["csod_planner_checkpoint"] = None

        # Merge scoping answers from payload (when user responds to scoping checkpoint)
        if payload.get("csod_scoping_answers"):
            existing = graph_input.get("csod_scoping_answers") or {}
            graph_input["csod_scoping_answers"] = {**existing, **payload["csod_scoping_answers"]}
            logger.info(f"✓ Merged scoping answers from payload: {list(payload['csod_scoping_answers'].keys())}")

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
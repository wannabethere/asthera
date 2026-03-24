"""
CSOD Planner Workflow - Phase 0: Context Setup (ARCHIVED LEGACY)

Moved from app/agents/csod/csod_planner_workflow.py — not imported by the application.

⚠️ DEPRECATED: Replaced by app.conversation.planner_workflow (+ LMS_CONVERSATION_CONFIG).

This file is reference-only. Active code uses skills_config_helpers for skills_config.json
and create_conversation_planner_app for the csod-planner agent.

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
4. Workflow routing (csod_workflow)

After Phase 0 completes, the resolved state is passed to the appropriate downstream workflow.

Graph topology:
    csod_datasource_selector
      → csod_concept_resolver
        → csod_area_matcher
          → csod_workflow_router
            → [invoke csod_workflow]
              → END
"""
import logging
import json
import re
from pathlib import Path
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

# Path to skills configuration (live JSON lives under app/agents/csod/)
_SKILLS_ROOT = Path(__file__).resolve().parents[2]
SKILLS_CONFIG_PATH = _SKILLS_ROOT / "app" / "agents" / "csod" / "skills_config.json"
CSOD_PROJECT_METADATA_ENRICHED_PATH = (
    "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/complianceskill/data/csod_project_metadata_llm_enriched.json"
)
CSOD_MDL_REFERENCE_PATH = (
    "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/complianceskill/data/csod_learn_mdl_reference.md"
)

# ============================================================================
# Data Source Configuration
# ============================================================================

def get_available_data_sources() -> List[Dict[str, Any]]:
    """
    Returns the list of available data sources for CSOD workflows.
    
    Returns:
        List of datasource dictionaries with id, display_name, and description
    """
    return [
        {
            "id": "cornerstone",
            "display_name": "Cornerstone OnDemand",
            "description": "LMS platform — training, compliance, assessments, ILT",
        },
        {
            "id": "workday",
            "display_name": "Workday",
            "description": "HCM platform — HR, talent management, workforce planning",
        },
    ]


# Legacy constant for backward compatibility
SUPPORTED_DATASOURCES = get_available_data_sources()

# ============================================================================
# Skills Configuration
# ============================================================================

def load_skills_config() -> Dict[str, Any]:
    """Load skills configuration from JSON file."""
    try:
        if SKILLS_CONFIG_PATH.exists():
            with open(SKILLS_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            logger.warning(f"Skills config not found at {SKILLS_CONFIG_PATH}, using defaults")
            return _get_default_skills_config()
    except Exception as e:
        logger.error(f"Error loading skills config: {e}", exc_info=True)
        return _get_default_skills_config()


def _get_default_skills_config() -> Dict[str, Any]:
    """Default skills configuration fallback."""
    return {
        "skills": {
            "metrics_recommendations": {
                "display_name": "Metrics Recommendations",
                "agents": ["csod_workflow"]
            },
            "causal_analysis": {
                "display_name": "Causal Analysis",
                "agents": ["csod_workflow"]
            },
        },
        "agent_mapping": {
            "csod_workflow": {
                "agent_id": "csod-workflow",
            },
            "csod_metric_advisor_workflow": {
                "agent_id": "csod-workflow",
            }
        },
        "default_agent": "csod_workflow",
    }


def get_agent_for_skill(skill_id: str, skills_config: Optional[Dict[str, Any]] = None) -> str:
    """
    Get the agent ID for a given skill.
    
    Args:
        skill_id: Skill identifier
        skills_config: Optional skills config (loads if not provided)
    
    Returns:
        Agent workflow identifier (e.g., "csod_workflow")
    """
    if skills_config is None:
        skills_config = load_skills_config()
    
    skill_info = skills_config.get("skills", {}).get(skill_id, {})
    agents = skill_info.get("agents", [])
    
    if agents:
        return agents[0]  # Use first agent for the skill
    
    # Fallback to default
    return skills_config.get("default_agent", "csod_workflow")


def _set_node_output(
    state: Dict[str, Any],
    node: str,
    status: str,
    findings: Dict[str, Any],
    next_step: Optional[str] = None,
) -> None:
    """Write structured node output for the planner narrator. Called by each narrator-aware node before returning."""
    state["csod_node_output"] = {
        "node": node,
        "status": status,
        "findings": findings,
        "next": next_step,
    }


# ============================================================================
# Planner Nodes
# ============================================================================

def _identify_datasource_with_llm(
    user_query: str,
    available_datasources: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    Use LLM to identify the most likely datasource from the user query.
    
    Args:
        user_query: The user's natural language query
        available_datasources: List of available datasource dictionaries
    
    Returns:
        Dictionary with identified datasource info, or None if unclear
    """
    try:
        from app.agents.prompt_loader import load_prompt, PROMPTS_CSOD
        from app.core.dependencies import get_llm
        from langchain_core.prompts import ChatPromptTemplate
        import json
        
        # Load datasource identification prompt
        try:
            prompt_text = load_prompt("00_datasource_identifier", prompts_dir=str(PROMPTS_CSOD))
        except FileNotFoundError:
            # Fallback prompt if file doesn't exist
            prompt_text = """You are a datasource identification assistant. Analyze the user's query and identify which data source platform they are referring to.

Available data sources:
{datasources}

Respond with a JSON object containing:
- "identified_datasource_id": The ID of the most likely datasource (or null if unclear)
- "confidence": "high", "medium", or "low"
- "reasoning": Brief explanation of why this datasource was identified

Example response:
{{"identified_datasource_id": "cornerstone", "confidence": "high", "reasoning": "User mentions learning and development metrics, which aligns with Cornerstone OnDemand LMS platform"}}"""
        
        # Format datasources for prompt
        datasources_text = "\n".join(
            f"- {ds['id']}: {ds['display_name']} - {ds['description']}"
            for ds in available_datasources
        )
        
        # Replace {datasources} placeholder in prompt
        prompt_text = prompt_text.replace("{datasources}", datasources_text)
        
        # Escape curly braces in JSON examples so LangChain doesn't treat them as template variables
        # Replace { with {{ and } with }}, but preserve actual template variables like {input}
        import re
        # First, protect actual template variables
        prompt_text = prompt_text.replace("{input}", "___INPUT_PLACEHOLDER___")
        # Escape all remaining curly braces
        prompt_text = prompt_text.replace("{", "{{").replace("}", "}}")
        # Restore template variables
        prompt_text = prompt_text.replace("___INPUT_PLACEHOLDER___", "{input}")
        
        # Build human message with user query
        human_message = user_query
        
        # Get LLM
        llm = get_llm(temperature=0)
        
        # Generate response
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
                logger.warning(f"Could not parse LLM response as JSON: {response_content}")
                return None
        
        identified_id = result.get("identified_datasource_id")
        if identified_id:
            # Find the matching datasource
            for ds in available_datasources:
                if ds["id"] == identified_id:
                    return {
                        "datasource": ds,
                        "confidence": result.get("confidence", "medium"),
                        "reasoning": result.get("reasoning", ""),
                    }
        
        return None
        
    except Exception as e:
        logger.error(f"Error in LLM datasource identification: {e}", exc_info=True)
        return None


def csod_datasource_selector_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Phase 0 Step A: Datasource selection.
    
    Uses LLM to identify the datasource from user query, then asks user to verify.
    If datasource is already confirmed, passes through to concept resolver.
    """
    # Get available datasources
    available_datasources = get_available_data_sources()
    state["csod_available_datasources"] = available_datasources
    
    # Check if datasource checkpoint was already responded to (via response state)
    checkpoint_responses = state.get("csod_checkpoint_responses", {})
    datasource_response = checkpoint_responses.get("datasource_select")
    
    if datasource_response:
        # Datasource was already responded to - use response data
        selected_ds = datasource_response.get("csod_selected_datasource")
        confirmed = datasource_response.get("csod_datasource_confirmed", False)
        
        if selected_ds:
            state["csod_selected_datasource"] = selected_ds
            state["csod_datasource_confirmed"] = confirmed or True
            logger.info(f"Datasource already responded to (via response state): {selected_ds} (confirmed: {confirmed or True})")
        else:
            # Fallback if response doesn't have datasource
            state["csod_selected_datasource"] = "cornerstone"
            state["csod_datasource_confirmed"] = True
        
        # Clear the checkpoint so routing continues to concept resolver
        if "csod_planner_checkpoint" in state:
            checkpoint_phase = state["csod_planner_checkpoint"].get("phase") if isinstance(state["csod_planner_checkpoint"], dict) else None
            if checkpoint_phase == "datasource_select":
                logger.info("Clearing datasource checkpoint after confirmation (response state present)")
                state["csod_planner_checkpoint"] = None
        return state
    
    # Also check legacy flag for backward compatibility
    if state.get("csod_datasource_confirmed"):
        # Already confirmed, just ensure it's set and continue
        if not state.get("csod_selected_datasource"):
            state["csod_selected_datasource"] = "cornerstone"  # Fallback
        # Clear the checkpoint so routing continues to concept resolver
        if "csod_planner_checkpoint" in state:
            logger.info("Clearing datasource checkpoint after confirmation")
            state["csod_planner_checkpoint"] = None
        return state
    
    # Check if datasource is already selected (but not confirmed)
    selected_datasource = state.get("csod_selected_datasource")
    user_query = state.get("user_query", "")
    
    # If datasource is already selected (even if not explicitly confirmed), don't create a checkpoint
    # This prevents infinite loops when resuming from checkpoint
    if selected_datasource:
        logger.info(f"Datasource already selected ({selected_datasource}), skipping checkpoint creation")
        # Ensure it's confirmed to avoid re-prompting
        if not state.get("csod_datasource_confirmed"):
            state["csod_datasource_confirmed"] = True
        # Clear any existing checkpoint
        if "csod_planner_checkpoint" in state:
            logger.info("Clearing checkpoint since datasource is already selected")
            state["csod_planner_checkpoint"] = None
        return state
    
    # Use LLM to identify datasource if not already selected
    identified_datasource_info = None
    if not selected_datasource and user_query:
        identified_datasource_info = _identify_datasource_with_llm(user_query, available_datasources)
        
        if identified_datasource_info:
            identified_ds = identified_datasource_info["datasource"]
            selected_datasource = identified_ds["id"]
            state["csod_selected_datasource"] = selected_datasource
            logger.info(
                f"LLM identified datasource: {selected_datasource} "
                f"(confidence: {identified_datasource_info.get('confidence', 'unknown')})"
            )
        else:
            # LLM couldn't identify, default to cornerstone
            selected_datasource = "cornerstone"
            state["csod_selected_datasource"] = selected_datasource
            logger.info(f"LLM could not identify datasource, defaulting to {selected_datasource}")
    
    # If still no datasource, default to cornerstone
    if not selected_datasource:
        selected_datasource = "cornerstone"
        state["csod_selected_datasource"] = selected_datasource
    
    # Find the selected datasource object
    selected_ds_obj = next(
        (ds for ds in available_datasources if ds["id"] == selected_datasource),
        available_datasources[0]  # Fallback to first
    )
    
    # Don't create checkpoint if response state already exists for datasource
    checkpoint_responses = state.get("csod_checkpoint_responses", {})
    if checkpoint_responses.get("datasource_select"):
        logger.info("Datasource response state exists, skipping checkpoint creation")
        # Ensure datasource is set from response
        ds_response = checkpoint_responses["datasource_select"]
        if ds_response.get("csod_selected_datasource"):
            state["csod_selected_datasource"] = ds_response["csod_selected_datasource"]
            state["csod_datasource_confirmed"] = ds_response.get("csod_datasource_confirmed", True)
        return state
    
    # Create checkpoint for user verification
    if identified_datasource_info:
        # LLM identified a datasource - ask for verification
        confidence = identified_datasource_info.get("confidence", "medium")
        reasoning = identified_datasource_info.get("reasoning", "")
        
        if confidence == "high" and reasoning:
            message = f"I identified **{selected_ds_obj['display_name']}** as the data source based on: {reasoning}\n\nIs this correct?"
        else:
            message = f"I think you're referring to **{selected_ds_obj['display_name']}**. Is this correct?"
    else:
        # No LLM identification - show selection options
        message = "Which platform are you analyzing today?"
    
    state["csod_planner_checkpoint"] = {
        "phase": "datasource_select",
        "message": message,
        "identified_datasource": {
            "id": selected_ds_obj["id"],
            "label": selected_ds_obj["display_name"],
            "description": selected_ds_obj["description"],
        } if identified_datasource_info else None,
        "options": [
            {"id": ds["id"], "label": ds["display_name"], "description": ds["description"]}
            for ds in available_datasources
        ],
        "requires_user_input": True,
    }
    
    return state


def _rank_concepts_with_llm(
    user_query: str,
    concept_matches: List[Any],
) -> Optional[Dict[str, Any]]:
    """
    Use LLM to rank concept matches and identify the best fit.

    Called after vector search. Returns a dict with:
      - ranked_concepts: list of concept_id in recommended order
      - primary_concept_id: single best match
      - confidence: "high" | "medium" | "low"
      - reasoning: plain-English explanation of why the top concept fits
      - show_alternatives: bool — whether to surface other options to the user
    """
    try:
        from app.agents.prompt_loader import load_prompt, PROMPTS_CSOD
        from langchain_core.prompts import ChatPromptTemplate
        prompt_text = load_prompt("13_concept_ranker", prompts_dir=str(PROMPTS_CSOD))
    except FileNotFoundError:
        prompt_text = """You are an analytics concept identifier for an LMS platform.

The user has asked a question. I have found these candidate concept categories from the knowledge base:

{candidates}

Your task:
1. Identify which concept BEST matches what the user is asking about.
2. Assign a confidence level: high (clearly matches), medium (likely matches), low (ambiguous).
3. Provide a one-sentence plain-English reason for the top pick.
4. If confidence is medium or low, set show_alternatives=true so the user can confirm.

Respond ONLY with a JSON object. No preamble. No markdown.
{{
  "primary_concept_id": "string",
  "ranked_concepts": ["concept_id_1", "concept_id_2"],
  "confidence": "high|medium|low",
  "reasoning": "string",
  "show_alternatives": true|false
}}"""

    def _get(m, key, default=None):
        if isinstance(m, dict):
            return m.get(key, default)
        return getattr(m, key, default)

    candidates_text = "\n".join(
        f"- ID: {_get(m, 'concept_id', '')}\n  Name: {_get(m, 'display_name', '')}\n"
        f"  Domain: {_get(m, 'domain', '')}\n  Vector score: {(_get(m, 'score', 0) or 0):.3f}\n"
        f"  Keywords: {', '.join((_get(m, 'trigger_keywords', []) or [])[:5])}"
        for m in concept_matches
    )
    prompt_text = prompt_text.replace("{candidates}", candidates_text)
    prompt_text = prompt_text.replace("{input}", "___INPUT___")
    prompt_text = prompt_text.replace("{", "{{").replace("}", "}}")
    prompt_text = prompt_text.replace("___INPUT___", "{input}")

    llm = get_llm(temperature=0)
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", prompt_text),
        ("human", "{input}"),
    ])
    response = (prompt_template | llm).invoke({"input": user_query})
    content = response.content if hasattr(response, "content") else str(response)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
        return json.loads(m.group(1)) if m else None


def csod_concept_resolver_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Phase 0 Step B+C: Concept resolution using L1 collection.

    Resolves user query to concepts via vector search, then LLM ranking, then asks user to confirm/select.
    Datasource is not required; it is inferred from concept domain if not set.
    """
    user_query = state.get("user_query", "")
    
    # If there's a datasource checkpoint but we have a datasource response, clear it
    checkpoint_responses = state.get("csod_checkpoint_responses", {})
    if checkpoint_responses.get("datasource_select"):
        # Datasource was responded to - clear any datasource checkpoint
        checkpoint = state.get("csod_planner_checkpoint")
        if checkpoint and checkpoint.get("phase") == "datasource_select":
            logger.info("Clearing datasource checkpoint in concept resolver (response state present)")
            state["csod_planner_checkpoint"] = None
    
    # Check if concept checkpoint was already responded to (via response state)
    concept_response = checkpoint_responses.get("concept_select")
    # Defence-in-depth: if csod_checkpoint_responses didn't make it into state (e.g. merge order on resume),
    # but we have confirmation fields in state from the payload, treat as already confirmed so we don't re-prompt.
    if not concept_response and state.get("csod_concepts_confirmed") and state.get("csod_confirmed_concept_ids") and state.get("csod_concept_matches"):
        concept_response = {
            "csod_confirmed_concept_ids": state["csod_confirmed_concept_ids"],
            "csod_concepts_confirmed": True,
            "csod_concept_matches": state["csod_concept_matches"],
        }
        logger.info("Concepts already confirmed (from state keys); using as concept_response for resume")
    
    # Fix 2: Clear stale confirmation flags when this is a fresh resolution (not a confirmation)
    # Only check legacy flag if we have a concept response OR if we have both confirmed IDs and matches
    # This prevents stale checkpointer state from bypassing concept selection
    concepts_confirmed_legacy = False
    if concept_response:
        # We have a concept response - this is a confirmation turn, use legacy flag if present
        concepts_confirmed_legacy = state.get("csod_concepts_confirmed", False)
    else:
        # No concept response - this is a fresh resolution
        # Only trust legacy flag if we have BOTH confirmed IDs AND concept matches (complete state)
        confirmed_ids = state.get("csod_confirmed_concept_ids", [])
        concept_matches = state.get("csod_concept_matches", [])
        if confirmed_ids and concept_matches and len(confirmed_ids) > 0 and len(concept_matches) > 0:
            # Has both - likely valid confirmation from previous turn
            concepts_confirmed_legacy = state.get("csod_concepts_confirmed", False)
        else:
            # Missing either IDs or matches - likely stale, clear flags
            if state.get("csod_concepts_confirmed"):
                logger.info("Clearing stale concept confirmation flags (fresh resolution, incomplete state)")
                state["csod_concepts_confirmed"] = False
                state["csod_confirmed_concept_ids"] = []
    
    if concept_response or concepts_confirmed_legacy:
        # Concepts were already responded to - use response data
        if concept_response:
            confirmed_concept_ids = concept_response.get("csod_confirmed_concept_ids", [])
            concept_matches = concept_response.get("csod_concept_matches", [])
            
            # Also set in state for backward compatibility
            state["csod_concepts_confirmed"] = concept_response.get("csod_concepts_confirmed", True)
            state["csod_confirmed_concept_ids"] = confirmed_concept_ids
            if concept_matches:
                state["csod_concept_matches"] = concept_matches
            
            logger.info(f"Concepts already responded to (via response state): {len(confirmed_concept_ids)} concept IDs")
            logger.info(f"Concept matches from response: {len(concept_matches)} matches")
        else:
            # Legacy: extract from state
            confirmed_concept_ids = state.get("csod_confirmed_concept_ids", [])
            concept_matches = state.get("csod_concept_matches", [])
            logger.info(f"Concepts already confirmed (legacy): {len(confirmed_concept_ids)} concept IDs")
        
        # Clear the checkpoint immediately so routing continues to area matcher
        if "csod_planner_checkpoint" in state:
            logger.info("Clearing concept checkpoint after confirmation")
            state["csod_planner_checkpoint"] = None
        
        # Process confirmed concepts if we have them
        if confirmed_concept_ids and concept_matches:
            logger.info(f"Concepts confirmed via checkpoint: {confirmed_concept_ids}")
            logger.info(f"Concept matches available in state: {len(concept_matches)} matches")
            logger.info(f"State keys: {list(state.keys())}")
            
            # Log concept matches details if available
            if concept_matches:
                for idx, match in enumerate(concept_matches[:3], 1):  # Log first 3
                    if isinstance(match, dict):
                        logger.info(f"  Match {idx}: {match.get('concept_id')} - {match.get('display_name')} (has project_ids: {bool(match.get('project_ids'))})")
            else:
                logger.warning(f"  ⚠️ CRITICAL: csod_concept_matches is empty in state!")
                logger.warning(f"  This means concept matches were not preserved from checkpoint or payload")
                logger.warning(f"  State keys present: {[k for k in state.keys() if 'concept' in k.lower()]}")
            
            if concept_matches:
                logger.info(f"  Available concept IDs: {[m.get('concept_id') for m in concept_matches if isinstance(m, dict)]}")
            else:
                logger.warning(f"  ⚠️ No concept matches in state! State keys: {list(state.keys())[:20]}")
                # If no concept matches but we have confirmed IDs, we can't proceed
                if confirmed_concept_ids:
                    logger.error(f"  ⚠️ CRITICAL: Have confirmed concept IDs {confirmed_concept_ids} but no concept matches in state!")
                    logger.error(f"  This means state restoration failed. State keys present: {list(state.keys())}")
                    # Try to continue anyway - maybe the area matcher can work without them
                    state["csod_selected_concepts"] = []
                    state["csod_resolved_project_ids"] = []
                    state["csod_resolved_mdl_table_refs"] = []
                    return state
            
            # Filter to only confirmed concepts
            selected_concepts = [
                {
                    "concept_id": m["concept_id"],
                    "display_name": m["display_name"],
                    "score": m["score"],
                    "coverage_confidence": m["coverage_confidence"],
                }
                for m in concept_matches
                if m["concept_id"] in confirmed_concept_ids
            ]
            
            # Log which concepts were selected
            if selected_concepts:
                logger.info(f"Selected {len(selected_concepts)} concept(s) from confirmed list:")
                for idx, concept in enumerate(selected_concepts, 1):
                    logger.info(f"  {idx}. {concept.get('display_name')} (ID: {concept.get('concept_id')}, Score: {concept.get('score', 0):.2f})")
            else:
                logger.warning(f"No concepts matched confirmed IDs. Confirmed: {confirmed_concept_ids}, Available: {[m.get('concept_id') for m in concept_matches]}")
            
            # Extract project_ids and mdl_table_refs from confirmed concepts
            all_project_ids = []
            all_mdl_table_refs = []
            for m in concept_matches:
                if m["concept_id"] in confirmed_concept_ids:
                    all_project_ids.extend(m.get("project_ids", []))
                    all_mdl_table_refs.extend(m.get("mdl_table_refs", []))
            
            # Deduplicate
            all_project_ids = list(set(all_project_ids))
            all_mdl_table_refs = list(set(all_mdl_table_refs))
            
            state["csod_selected_concepts"] = selected_concepts
            state["csod_resolved_project_ids"] = all_project_ids
            state["csod_resolved_mdl_table_refs"] = all_mdl_table_refs
            
            # Set primary project_id (first match)
            if all_project_ids:
                state["csod_primary_project_id"] = all_project_ids[0]
            
            logger.info(
                f"Using {len(selected_concepts)} confirmed concepts, "
                f"{len(all_project_ids)} project_ids, "
                f"{len(all_mdl_table_refs)} mdl_table_refs"
            )
            return state
    
    # Check if we already have concept matches from a previous run (checkpoint resume)
    existing_concept_matches = state.get("csod_concept_matches", [])
    if existing_concept_matches:
        # Defence-in-depth: if confirmation is present via direct state flags (e.g. state
        # was restored from checkpointer but csod_checkpoint_responses was not yet merged),
        # process the confirmation instead of recreating the checkpoint.
        confirmed_ids = state.get("csod_confirmed_concept_ids", [])
        if state.get("csod_concepts_confirmed") and confirmed_ids:
            logger.info(
                f"Concepts already confirmed via state flags (ids={confirmed_ids}), "
                "processing confirmation without recreating checkpoint"
            )
            selected_concepts = [
                {
                    "concept_id": m["concept_id"],
                    "display_name": m["display_name"],
                    "score": m["score"],
                    "coverage_confidence": m["coverage_confidence"],
                }
                for m in existing_concept_matches
                if m.get("concept_id") in confirmed_ids
            ]
            all_project_ids = list({pid for m in existing_concept_matches if m.get("concept_id") in confirmed_ids for pid in m.get("project_ids", [])})
            all_mdl_table_refs = list({ref for m in existing_concept_matches if m.get("concept_id") in confirmed_ids for ref in m.get("mdl_table_refs", [])})
            state["csod_selected_concepts"] = selected_concepts
            state["csod_resolved_project_ids"] = all_project_ids
            state["csod_resolved_mdl_table_refs"] = all_mdl_table_refs
            if all_project_ids:
                state["csod_primary_project_id"] = all_project_ids[0]
            state["csod_planner_checkpoint"] = None
            logger.info(f"Confirmed {len(selected_concepts)} concept(s) from state flags")
            return state

        logger.info(f"Found existing concept matches in state ({len(existing_concept_matches)} matches), skipping re-resolution")
        logger.info(f"  Existing concept IDs: {[m.get('concept_id') for m in existing_concept_matches if isinstance(m, dict)]}")
        # Fix 8.1: Always overwrite checkpoint so stale checkpoint (e.g. datasource_select) is replaced
        concept_options = [
            {
                "id": m.get("concept_id"),
                "label": m.get("display_name"),
                "description": f"Domain: {m.get('domain', 'unknown')}, Score: {m.get('score', 0):.2f}",
                "score": m.get("score", 0),
                "coverage_confidence": m.get("coverage_confidence", 0),
            }
            for m in existing_concept_matches
        ]
        concept_options.sort(key=lambda x: x["score"], reverse=True)
        if len(existing_concept_matches) == 1:
            message = f"I found the topic category **{existing_concept_matches[0].get('display_name')}**. Is this correct?"
        else:
            concepts_list = ", ".join([f"**{m.get('display_name')}**" for m in existing_concept_matches[:3]])
            message = f"I found these topic categories: {concepts_list}. Which ones are relevant to your question?"
        state["csod_planner_checkpoint"] = {
            "phase": "concept_select",
            "message": message,
            "options": concept_options,
            "requires_user_input": True,
            "llm_confidence": "low",
            "llm_reasoning": "",
        }
        _set_node_output(
            state, "csod_concept_resolver",
            status="success",
            findings={
                "candidates": [
                    {"id": m.get("concept_id"), "name": m.get("display_name"), "score": round(m.get("score", 0), 3), "keywords": []}
                    for m in existing_concept_matches
                ],
                "llm_primary": None,
                "llm_confidence": "low",
                "llm_reasoning": "",
                "datasource_inferred": state.get("csod_selected_datasource"),
            },
            next_step="csod_skill_identifier",
        )
        logger.info(f"Recreated checkpoint with {len(existing_concept_matches)} concept matches")
        return state
    
    if not user_query:
        logger.warning("No user query provided for concept resolution")
        state["csod_concept_matches"] = []
        return state
    
    # Resolve concepts using L1 collection (vector search - no source filtering)
    try:
        concept_matches: List[ConceptMatch] = resolve_intent_to_concept(
            user_query=user_query,
            connected_source_ids=[],  # Empty list - no source filtering, search all concepts
            top_k=5,
        )
        if not concept_matches:
            logger.warning("No concept matches found")
            state["csod_concept_matches"] = []
            state["csod_selected_concepts"] = []
            return state

        # Infer datasource from concept domain if not already set
        if concept_matches and not state.get("csod_selected_datasource"):
            domain_to_source = {"lms": "cornerstone", "hr": "workday", "security": "cce"}
            inferred_domain = concept_matches[0].domain
            inferred_source = domain_to_source.get(inferred_domain, "cornerstone")
            state["csod_selected_datasource"] = inferred_source
            logger.info(f"Datasource inferred from concept domain: {inferred_source} (domain: {inferred_domain})")

        # LLM ranking step (Fix B)
        llm_ranking = None
        if concept_matches:
            llm_ranking = _rank_concepts_with_llm(user_query, concept_matches)
        if llm_ranking and llm_ranking.get("ranked_concepts"):
            ranked_ids = llm_ranking["ranked_concepts"]
            match_by_id = {m.concept_id: m for m in concept_matches}
            concept_matches = (
                [match_by_id[cid] for cid in ranked_ids if cid in match_by_id]
                + [m for m in concept_matches if m.concept_id not in ranked_ids]
            )

        primary_id = llm_ranking.get("primary_concept_id") if llm_ranking else None
        confidence = llm_ranking.get("confidence", "low") if llm_ranking else "low"
        reasoning = llm_ranking.get("reasoning", "") if llm_ranking else ""
        show_alternatives = llm_ranking.get("show_alternatives", True) if llm_ranking else True

        # Store all matches for user selection
        state["csod_concept_matches"] = [
            {
                "concept_id": m.concept_id,
                "display_name": m.display_name,
                "score": m.score,
                "coverage_confidence": m.coverage_confidence,
                "project_ids": m.project_ids,
                "mdl_table_refs": m.mdl_table_refs,
                "domain": m.domain,
                "api_categories": m.api_categories,
            }
            for m in concept_matches
        ]

        # Don't create checkpoint if response state already exists for concepts
        checkpoint_responses = state.get("csod_checkpoint_responses", {})
        if checkpoint_responses.get("concept_select"):
            logger.info("Concept response state exists, skipping checkpoint creation")
            concept_response = checkpoint_responses["concept_select"]
            confirmed_concept_ids = concept_response.get("csod_confirmed_concept_ids", [])
            if confirmed_concept_ids:
                selected_concepts = [
                    {"concept_id": m["concept_id"], "display_name": m["display_name"], "score": m["score"], "coverage_confidence": m["coverage_confidence"]}
                    for m in state["csod_concept_matches"] if m["concept_id"] in confirmed_concept_ids
                ]
                all_project_ids = []
                all_mdl_table_refs = []
                for m in state["csod_concept_matches"]:
                    if m["concept_id"] in confirmed_concept_ids:
                        all_project_ids.extend(m.get("project_ids", []))
                        all_mdl_table_refs.extend(m.get("mdl_table_refs", []))
                state["csod_selected_concepts"] = selected_concepts
                state["csod_resolved_project_ids"] = list(set(all_project_ids))
                state["csod_resolved_mdl_table_refs"] = list(set(all_mdl_table_refs))
                if all_project_ids:
                    state["csod_primary_project_id"] = all_project_ids[0]
            return state

        # Build checkpoint message using LLM reasoning
        concept_options = [
            {"id": m.concept_id, "label": m.display_name, "description": f"Domain: {m.domain}, Score: {m.score:.2f}", "score": m.score, "coverage_confidence": m.coverage_confidence}
            for m in concept_matches
        ]
        concept_options.sort(key=lambda x: x["score"], reverse=True)
        if primary_id and confidence == "high" and not show_alternatives:
            primary_match = next((m for m in concept_matches if m.concept_id == primary_id), None)
            if primary_match:
                message = f"I'll analyse **{primary_match.display_name}** for you. {reasoning} Is that right?"
            else:
                message = f"I found these topic categories: {', '.join(f'**{m.display_name}**' for m in concept_matches[:3])}. Which ones are relevant to your question?"
        else:
            names = ", ".join(f"**{m.display_name}**" for m in concept_matches[:3])
            message = f"I found these topic areas: {names}. Which ones are relevant to your question?"

        state["csod_planner_checkpoint"] = {
            "phase": "concept_select",
            "message": message,
            "options": concept_options,
            "requires_user_input": True,
            "llm_confidence": confidence,
            "llm_reasoning": reasoning,
        }
        _set_node_output(
            state, "csod_concept_resolver",
            status="success" if concept_matches else "no_results",
            findings={
                "candidates": [
                    {"id": m.concept_id, "name": m.display_name, "score": round(m.score, 3), "keywords": getattr(m, "trigger_keywords", [])[:5]}
                    for m in concept_matches
                ],
                "llm_primary": primary_id,
                "llm_confidence": confidence,
                "llm_reasoning": reasoning,
                "datasource_inferred": state.get("csod_selected_datasource"),
            },
            next_step="csod_skill_identifier",
        )
        logger.info(f"Found {len(concept_matches)} concept matches, requesting user selection")
        
    except Exception as e:
        logger.error(f"Error in concept resolution: {e}", exc_info=True)
        state["csod_concept_matches"] = []
        state["csod_selected_concepts"] = []
        state["csod_resolved_project_ids"] = []
        state["csod_resolved_mdl_table_refs"] = []
        _set_node_output(state, "csod_concept_resolver", status="error", findings={"error": str(e)}, next_step="csod_skill_identifier")
    
    return state


# Skill → required scoping filters (used when not in skills_config)
SKILL_SCOPING_FILTERS: Dict[str, List[str]] = {
    "metrics_recommendations": ["org_unit", "time_period", "training_type"],
    "causal_analysis": ["org_unit", "time_period"],
    "dashboard_generation": ["persona", "time_period"],
    "compliance_reporting": ["org_unit", "time_period", "due_date_range"],
    "adhoc_data_questions": [],
    "data_lineage": [],
    "reports": ["time_period", "report_format"],
    "automations": ["org_unit"],
    "discovery": [],
}
ALWAYS_INCLUDE_FILTERS = ["org_unit", "time_period"]

# Simple question templates for scoping (key -> question text)
# Defaults when user asks to skip scoping (e.g. "use defaults for all")
LMS_SCOPING_DEFAULT_VALUES: Dict[str, str] = {
    "org_unit": "All organizational units",
    "time_period": "Last 90 days",
    "training_type": "All types (compliance, mandatory, and optional)",
    "persona": "Learning administrator",
    "due_date_range": "Next 90 days",
    "report_format": "Interactive summary",
}


def _user_requested_scoping_defaults(state: EnhancedCompliancePipelineState) -> bool:
    uq = (state.get("user_query") or "").strip().lower()
    if not uq:
        return False
    phrases = (
        "use default",
        "defaults for all",
        "default for all",
        "use defaults",
        "apply defaults",
        "just default",
        "standard defaults",
    )
    return any(p in uq for p in phrases)


LMS_SCOPING_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "org_unit": {"key": "org_unit", "question": "Which organization unit or department should we focus on?"},
    "time_period": {"key": "time_period", "question": "What time period are you interested in? (e.g. last 90 days, Q1)"},
    "training_type": {"key": "training_type", "question": "What type of training? (compliance, mandatory, optional)"},
    "persona": {"key": "persona", "question": "Who is the primary audience for this? (e.g. HR manager, learning admin)"},
    "due_date_range": {"key": "due_date_range", "question": "What due date range matters for compliance?"},
    "report_format": {"key": "report_format", "question": "What report format do you need? (PDF, Excel, scheduled)"},
}


def _build_scoping_question_for_filter(filter_name: str) -> Dict[str, Any]:
    """
    Build one scoping question. Uses LMS_SCOPING_TEMPLATES, then skills_config.scoping_filters,
    then a generic fallback so we never drop unanswered filters silently.
    """
    tmpl = LMS_SCOPING_TEMPLATES.get(filter_name)
    if tmpl:
        return {
            "key": tmpl.get("key", filter_name),
            "question": tmpl.get("question", f"Please specify {filter_name}."),
        }
    try:
        cfg = load_skills_config()
        spec = (cfg.get("scoping_filters") or {}).get(filter_name)
        if isinstance(spec, dict):
            label = spec.get("label") or filter_name.replace("_", " ").title()
            desc = (spec.get("description") or "").strip()
            opts = spec.get("options")
            if desc:
                question = desc
            else:
                question = f"What {label.lower()} should we use?"
            if isinstance(opts, list) and opts:
                question += f" Options: {', '.join(str(o) for o in opts)}."
            return {"key": filter_name, "question": question}
    except Exception:
        pass
    label = filter_name.replace("_", " ").title()
    return {"key": filter_name, "question": f"Please specify {label} for this analysis."}


def csod_scoping_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Ask skill-specific scoping questions before area matching.
    Populates csod_scoping_answers for use by area_matcher.
    """
    primary_skill = state.get("csod_primary_skill")
    skills_config = load_skills_config()
    skill_info = skills_config.get("skills", {}).get(primary_skill or "", {})
    config_filters = skill_info.get("scoping_filters", None)
    filters = config_filters if config_filters is not None else SKILL_SCOPING_FILTERS.get(primary_skill or "", [])
    all_filters = list(dict.fromkeys(ALWAYS_INCLUDE_FILTERS + filters))

    existing_answers = dict(state.get("csod_scoping_answers") or {})
    unanswered = [f for f in all_filters if f not in existing_answers]

    logger.info(
        "csod_scoping_node: primary_skill=%r all_filters=%s unanswered=%s "
        "apply_scoping_defaults=%s existing_answer_keys=%s",
        primary_skill,
        all_filters,
        unanswered,
        skill_info.get("apply_scoping_defaults"),
        list(existing_answers.keys()),
    )

    if unanswered and skill_info.get("apply_scoping_defaults"):
        for f in unanswered:
            existing_answers[f] = LMS_SCOPING_DEFAULT_VALUES.get(f, "Not specified")
        state["csod_scoping_answers"] = existing_answers
        unanswered = []
        logger.info(
            "apply_scoping_defaults for skill %s — filled: %s",
            primary_skill,
            list(existing_answers.keys()),
        )

    if unanswered and _user_requested_scoping_defaults(state):
        for f in unanswered:
            existing_answers[f] = LMS_SCOPING_DEFAULT_VALUES.get(f, "Not specified")
        state["csod_scoping_answers"] = existing_answers
        unanswered = []
        logger.info(
            "User requested defaults — filled scoping filters: %s",
            list(existing_answers.keys()),
        )

    if not unanswered:
        state["csod_scoping_complete"] = True
        state["csod_planner_checkpoint"] = None
        _set_node_output(state, "csod_scoping_node", status="skipped", findings={"filters_needed": all_filters, "filters_answered": list(existing_answers.keys()), "questions_queued": 0, "skipped": True}, next_step="csod_area_matcher")
        logger.info(f"All scoping filters already answered for skill {primary_skill}, skipping")
        return state

    questions = []
    for filter_name in unanswered[:3]:
        questions.append(_build_scoping_question_for_filter(filter_name))

    if not questions:
        logger.warning(
            "csod_scoping_node: unanswered was non-empty but built no questions "
            "(unexpected); marking scoping complete. unanswered=%s",
            unanswered,
        )
        state["csod_scoping_complete"] = True
        state["csod_planner_checkpoint"] = None
        _set_node_output(state, "csod_scoping_node", status="skipped", findings={"filters_needed": all_filters, "filters_answered": list(existing_answers.keys()), "questions_queued": 0, "skipped": True}, next_step="csod_area_matcher")
        return state

    logger.info(
        "csod_scoping_node: queuing scoping checkpoint with %d question(s) for phase=scoping",
        len(questions),
    )
    state["csod_planner_checkpoint"] = {
        "phase": "scoping",
        "message": "Before I search for the best analysis approach, I need a bit more context.",
        "questions": questions,
        "requires_user_input": True,
        "skill": primary_skill,
    }
    # Explicitly mark scoping as NOT complete so _route_after_scoping can detect this
    # even when csod_planner_checkpoint is not visible to the routing function.
    state["csod_scoping_complete"] = False
    _set_node_output(
        state, "csod_scoping_node",
        status="success",
        findings={
            "filters_needed": all_filters,
            "filters_answered": list(existing_answers.keys()),
            "questions_queued": len(questions),
            "skipped": False,
        },
        next_step="csod_area_matcher",
    )
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
    logger.info(f"Scoping answers: {scoping_answers}")
    logger.info(f"Selected concepts: {selected_concepts}")
    logger.info(f"Concept matches: {state.get('csod_concept_matches', [])}")
    logger.info(f"Primary concept id: {state.get('csod_primary_concept_id', None)}")
    logger.info(f"Primary area: {state.get('csod_primary_area', None)}")
    
    # REMOVED: csod_generate_area_confirmation flag - always generate confirmation now
    
    if not selected_concepts:
        # Log what concepts were available but not selected
        concept_matches = state.get("csod_concept_matches", [])
        if concept_matches:
            available_concept_ids = [m.get("concept_id") for m in concept_matches]
            logger.warning(
                f"No selected concepts for area matching. "
                f"Available concepts: {available_concept_ids} "
                f"({[m.get('display_name') for m in concept_matches]})"
            )
        else:
            logger.warning("No selected concepts for area matching (no concept matches found)")
        state["csod_area_matches"] = []
        _set_node_output(state, "csod_area_matcher", status="no_results", findings={"areas_matched": [], "scoping_used": scoping_answers}, next_step="csod_workflow_router")
        return state
    
    # Log which concepts are being used
    concept_ids = [c.get("concept_id") for c in selected_concepts]
    concept_names = [c.get("display_name") for c in selected_concepts]
    logger.info(f"Using {len(selected_concepts)} selected concept(s) for area matching:")
    for idx, (cid, cname) in enumerate(zip(concept_ids, concept_names), 1):
        logger.info(f"  {idx}. {cname} (ID: {cid})")
    
    # Use primary concept for area matching
    primary_concept_id = selected_concepts[0]["concept_id"] if selected_concepts else None
    
    if not primary_concept_id:
        state["csod_area_matches"] = []
        return state
    
    try:
        # Default behavior: always use LLM for area recommendation so flow does not depend
        # on L2 collection population.
        area_matches_payload = _llm_recommend_areas(
            user_query=user_query,
            selected_concepts=selected_concepts,
            scoping_answers=scoping_answers,
        )
        area_source = "llm_default" if area_matches_payload else "none"

        # Optional secondary guardrail (legacy): if LLM fails unexpectedly, try vector/registry.
        # This keeps runtime resilience without making vector path the primary dependency.
        area_matches: List[RecommendationAreaMatch] = []
        if not area_matches_payload:
            logger.warning("LLM default area recommendation returned no results; trying vector/registry backup")
            area_matches = resolve_scoping_to_areas(
                scoping_answers=scoping_answers,
                confirmed_concept_id=primary_concept_id,
                top_k=3,
            )
            area_matches_payload = [
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
            area_source = "vector_or_registry_backup" if area_matches_payload else "none"

        state["csod_area_matches"] = area_matches_payload

        # Set primary area (first match)
        if area_matches_payload:
            primary_area = area_matches_payload[0]
            state["csod_primary_area"] = {
                "area_id": primary_area.get("area_id"),
                "display_name": primary_area.get("display_name"),
                "metrics": primary_area.get("metrics", []),
                "kpis": primary_area.get("kpis", []),
                "data_requirements": primary_area.get("data_requirements", []),
                "causal_paths": primary_area.get("causal_paths", []),
            }

        # Always generate confirmation message when areas exist.
        # _generate_area_confirmation expects RecommendationAreaMatch, so only call it for
        # vector/registry results. For LLM fallback, use a direct confirmation object.
        if area_matches and area_source == "vector_or_registry_backup":
            confirmation = _generate_area_confirmation(
                user_query=user_query,
                selected_concepts=selected_concepts,
                area_matches=area_matches,
            )
            state["csod_area_confirmation"] = confirmation
        elif area_matches_payload and area_source == "llm_default":
            state["csod_area_confirmation"] = {
                "message": (
                    f"I identified {len(area_matches_payload)} recommendation area(s) based on your "
                    "confirmed concepts and scoping context. Would you like me to proceed with these?"
                ),
                "primary_area_id": area_matches_payload[0].get("area_id", ""),
            }
        
        _set_node_output(
            state, "csod_area_matcher",
            status="success" if area_matches_payload else "no_results",
            findings={
                "areas_matched": [
                    {
                        "id": a.get("area_id"),
                        "name": a.get("display_name"),
                        "score": round(float(a.get("score", 0.0)), 2),
                    }
                    for a in area_matches_payload
                ],
                "primary_area_id": area_matches_payload[0].get("area_id") if area_matches_payload else None,
                "primary_area_name": area_matches_payload[0].get("display_name") if area_matches_payload else None,
                "scoping_used": scoping_answers,
                "area_source": area_source,
            },
            next_step="csod_workflow_router",
        )
        logger.info(f"Matched {len(area_matches_payload)} recommendation areas (source={area_source})")
        
    except Exception as e:
        logger.error(f"Error in area matching: {e}", exc_info=True)
        state["csod_area_matches"] = []
        _set_node_output(state, "csod_area_matcher", status="error", findings={"error": str(e)}, next_step="csod_workflow_router")
    
    return state


def _llm_recommend_areas(
    user_query: str,
    selected_concepts: List[Dict[str, Any]],
    scoping_answers: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    LLM fallback for recommendation area generation when vector + registry area lookup returns empty.
    Returns up to 3 areas in csod_area_matches-compatible shape.
    """
    try:
        from langchain_core.prompts import ChatPromptTemplate
    except Exception:
        logger.exception("Failed to import ChatPromptTemplate for LLM area recommendation")
        return []

    if not selected_concepts:
        return []

    concept_lines = "\n".join(
        f"- concept_id: {c.get('concept_id', '')}, display_name: {c.get('display_name', '')}"
        for c in selected_concepts
    )
    scoping_json = json.dumps(scoping_answers or {}, ensure_ascii=True)
    grounded_context = _build_grounded_area_context(
        user_query=user_query,
        selected_concepts=selected_concepts,
    )

    system_prompt = (
        "You are a CSOD LMS analytics recommendation planner.\n"
        "Generate 2-3 recommendation areas from the user's query, confirmed concepts, and scoping answers.\n"
        "Return ONLY valid JSON as an array of objects, no markdown and no extra text.\n"
        "Each object MUST follow this schema:\n"
        "{\n"
        '  "area_id": "snake_case_id",\n'
        '  "concept_id": "must be one of confirmed concept_id values",\n'
        '  "display_name": "human readable area name",\n'
        '  "score": 1.0,\n'
        '  "metrics": ["metric 1", "metric 2"],\n'
        '  "kpis": ["kpi 1", "kpi 2"],\n'
        '  "filters": ["org_unit", "time_period"],\n'
        '  "causal_paths": ["cause -> effect"],\n'
        '  "data_requirements": ["table/view/field names needed"]\n'
        "}\n"
        "Rules:\n"
        "- Keep score as 1.0 for all generated areas.\n"
        "- Use only realistic CSOD-style metrics/KPIs tied to confirmed concepts.\n"
        "- Use scoping answers to tailor filters and recommendations.\n"
        "- Prefer concise, implementation-friendly names."
    )

    human_prompt = (
        f"User query:\n{user_query}\n\n"
        f"Confirmed concepts:\n{concept_lines}\n\n"
        f"Scoping answers (JSON):\n{scoping_json}\n\n"
        f"Grounded context from CSOD metadata and MDL reference:\n{grounded_context}\n\n"
        "Output JSON array now."
    )

    try:
        llm = get_llm(temperature=0)
        # Escape literal JSON braces so ChatPromptTemplate treats only {input} as a variable.
        system_prompt_escaped = system_prompt.replace("{", "{{").replace("}", "}}")
        prompt = ChatPromptTemplate.from_messages(
            [("system", system_prompt_escaped), ("human", "{input}")]
        )
        response = (prompt | llm).invoke({"input": human_prompt})
        content = response.content if hasattr(response, "content") else str(response)
        parsed = _extract_json_array(content)
        validated = _normalize_area_matches(parsed, selected_concepts)
        logger.info("LLM area fallback produced %d area(s)", len(validated))
        return validated
    except Exception as e:
        logger.error("LLM area fallback failed: %s", e, exc_info=True)
        return []


def _extract_json_array(raw_text: str) -> List[Dict[str, Any]]:
    """Parse a JSON array from raw LLM output."""
    try:
        parsed = json.loads(raw_text)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        pass

    code_block = re.search(r"```json\s*(\[.*?\])\s*```", raw_text, re.DOTALL)
    if code_block:
        try:
            parsed = json.loads(code_block.group(1))
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []

    bracket_block = re.search(r"(\[.*\])", raw_text, re.DOTALL)
    if bracket_block:
        try:
            parsed = json.loads(bracket_block.group(1))
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []

    return []


def _normalize_area_matches(
    areas: List[Dict[str, Any]],
    selected_concepts: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Validate and coerce LLM output to the csod_area_matches schema."""
    if not areas:
        return []

    concept_ids = [c.get("concept_id") for c in selected_concepts if c.get("concept_id")]
    default_concept_id = concept_ids[0] if concept_ids else ""
    normalized: List[Dict[str, Any]] = []

    for idx, area in enumerate(areas[:3]):
        if not isinstance(area, dict):
            continue
        concept_id = area.get("concept_id") if area.get("concept_id") in concept_ids else default_concept_id
        area_id = str(area.get("area_id") or f"recommended_area_{idx + 1}")
        display_name = str(area.get("display_name") or area_id.replace("_", " ").title())
        normalized.append(
            {
                "area_id": area_id,
                "concept_id": concept_id,
                "display_name": display_name,
                "score": 1.0,
                "metrics": [str(v) for v in (area.get("metrics") or [])][:10],
                "kpis": [str(v) for v in (area.get("kpis") or [])][:10],
                "filters": [str(v) for v in (area.get("filters") or [])][:10],
                "causal_paths": [str(v) for v in (area.get("causal_paths") or [])][:10],
                "data_requirements": [str(v) for v in (area.get("data_requirements") or [])][:10],
            }
        )

    return normalized


def _build_grounded_area_context(
    user_query: str,
    selected_concepts: List[Dict[str, Any]],
) -> str:
    """Build compact grounding context from enriched project metadata + MDL reference."""
    context_parts: List[str] = []

    metadata_context = _extract_project_metadata_context(selected_concepts)
    if metadata_context:
        context_parts.append("Project metadata context:\n" + metadata_context)

    mdl_context = _extract_mdl_reference_context(user_query, selected_concepts)
    if mdl_context:
        context_parts.append("MDL reference context:\n" + mdl_context)

    if not context_parts:
        return "No extra grounded context available."
    return "\n\n".join(context_parts)


def _extract_project_metadata_context(selected_concepts: List[Dict[str, Any]]) -> str:
    """Extract relevant projects/tables from csod_project_metadata_llm_enriched.json."""
    try:
        if not CSOD_PROJECT_METADATA_ENRICHED_PATH.exists():
            logger.warning("Enriched project metadata not found at %s", CSOD_PROJECT_METADATA_ENRICHED_PATH)
            return ""
        with open(CSOD_PROJECT_METADATA_ENRICHED_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as e:
        logger.warning("Failed reading enriched project metadata: %s", e)
        return ""

    projects = payload.get("projects", []) if isinstance(payload, dict) else []
    if not isinstance(projects, list) or not projects:
        return ""

    selected_concept_ids = {
        c.get("concept_id", "").strip().lower()
        for c in selected_concepts
        if isinstance(c, dict) and c.get("concept_id")
    }

    matched_projects: List[Dict[str, Any]] = []
    for p in projects:
        if not isinstance(p, dict):
            continue
        project_concepts = {str(cid).strip().lower() for cid in (p.get("concept_ids") or [])}
        if selected_concept_ids and selected_concept_ids.intersection(project_concepts):
            matched_projects.append(p)

    # If no explicit concept match, still provide a small high-signal sample.
    if not matched_projects:
        matched_projects = [p for p in projects if isinstance(p, dict)][:3]

    lines: List[str] = []
    for p in matched_projects[:6]:
        project_id = p.get("project_id", "")
        title = p.get("title", "")
        description = p.get("description", "")
        concept_ids = p.get("concept_ids", []) or []
        mdl_tables = p.get("mdl_tables", {}) or {}
        primary_tables = (mdl_tables.get("primary") or [])[:8] if isinstance(mdl_tables, dict) else []
        table_names = [t.get("name") for t in (p.get("tables") or []) if isinstance(t, dict) and t.get("name")]
        if not primary_tables:
            primary_tables = table_names[:8]
        lines.append(
            f"- project_id={project_id}, title={title}, concepts={concept_ids}, "
            f"primary_tables={primary_tables}, description={description}"
        )

    return "\n".join(lines)


def _extract_mdl_reference_context(
    user_query: str,
    selected_concepts: List[Dict[str, Any]],
) -> str:
    """Select relevant subsections from csod_learn_mdl_reference.md based on concept/query keywords."""
    try:
        if not CSOD_MDL_REFERENCE_PATH.exists():
            logger.warning("MDL reference not found at %s", CSOD_MDL_REFERENCE_PATH)
            return ""
        text = CSOD_MDL_REFERENCE_PATH.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning("Failed reading MDL reference: %s", e)
        return ""

    sections = re.split(r"(?=^###\s+)", text, flags=re.MULTILINE)
    if not sections:
        return ""

    concept_terms: List[str] = []
    for concept in selected_concepts:
        if not isinstance(concept, dict):
            continue
        concept_terms.extend(str(concept.get("concept_id", "")).lower().split("_"))
        concept_terms.extend(str(concept.get("display_name", "")).lower().split())

    query_terms = re.findall(r"[a-zA-Z_]{4,}", (user_query or "").lower())
    base_terms = {
        "training",
        "completion",
        "compliance",
        "mandatory",
        "overdue",
        "assessment",
        "learning",
        "effectiveness",
        "certification",
        "transcript",
        "assignment",
        "ilt",
        "scorm",
        "ou",
        "user",
    }
    match_terms = {t for t in (concept_terms + query_terms) if len(t) >= 4}
    match_terms.update(base_terms)

    scored_sections: List[Dict[str, Any]] = []
    for section in sections:
        s = section.strip()
        if not s.startswith("###"):
            continue
        lower_s = s.lower()
        score = sum(1 for t in match_terms if t in lower_s)
        if score <= 0:
            continue
        lines = s.splitlines()
        excerpt = "\n".join(lines[:18])
        scored_sections.append({"score": score, "excerpt": excerpt})

    scored_sections.sort(key=lambda item: item["score"], reverse=True)
    top = scored_sections[:3]
    if not top:
        return ""
    return "\n\n".join(item["excerpt"] for item in top)


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
        # Escape literal JSON braces from prompt text (if any) while preserving {input}.
        prompt_text = prompt_text.replace("{input}", "___INPUT_PLACEHOLDER___")
        prompt_text = prompt_text.replace("{", "{{").replace("}", "}}")
        prompt_text = prompt_text.replace("___INPUT_PLACEHOLDER___", "{input}")
        
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


def _identify_skills_with_llm(
    user_query: str,
    skills_config: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Use LLM to identify skills from the user query.
    
    Args:
        user_query: The user's natural language query
        skills_config: Skills configuration dictionary
    
    Returns:
        Dictionary with identified skills info, or None if error
    """
    try:
        from app.agents.prompt_loader import load_prompt, PROMPTS_CSOD
        from app.core.dependencies import get_llm
        from langchain_core.prompts import ChatPromptTemplate
        import json
        
        # Load skill advisor prompt
        try:
            prompt_text = load_prompt("12_skill_advisor", prompts_dir=str(PROMPTS_CSOD))
        except FileNotFoundError:
            # Fallback prompt if file doesn't exist
            prompt_text = """You are a skill advisor that identifies the type of analysis needed from user queries.

Available skills:
{skills_list}

Respond with JSON containing primary_skill, secondary_skills (array), skill_confidence (dict), and reasoning."""
        
        # Format skills for prompt
        skills = skills_config.get("skills", {})
        skills_list = "\n".join(
            f"- {skill_id}: {info.get('display_name', skill_id)} - {info.get('description', '')}"
            for skill_id, info in skills.items()
        )
        
        # Replace {skills_list} placeholder in prompt
        prompt_text = prompt_text.replace("{skills_list}", skills_list)
        
        # Escape curly braces in JSON examples so LangChain doesn't treat them as template variables
        # Replace { with {{ and } with }}, but preserve actual template variables like {input}
        import re
        # First, protect actual template variables
        prompt_text = prompt_text.replace("{input}", "___INPUT_PLACEHOLDER___")
        # Escape all remaining curly braces
        prompt_text = prompt_text.replace("{", "{{").replace("}", "}}")
        # Restore template variables
        prompt_text = prompt_text.replace("___INPUT_PLACEHOLDER___", "{input}")
        
        # Build human message with user query
        human_message = user_query
        
        # Get LLM
        llm = get_llm(temperature=0)
        
        # Generate response
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
                logger.warning(f"Could not parse LLM response as JSON: {response_content}")
                return None
        
        # Validate result
        if "primary_skill" not in result:
            logger.warning(f"LLM response missing primary_skill: {result}")
            return None
        
        return result
        
    except Exception as e:
        logger.error(f"Error in LLM skill identification: {e}", exc_info=True)
        return None


def csod_skill_identifier_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Phase 0 Step E: Skill identification using LLM.

    Identifies the type of analysis needed (use case, SQL, metrics, dashboard, etc.)
    and maps to appropriate agents via skills configuration. Uses confirmed concept
    context to narrow skill options when available.
    """
    user_query = state.get("user_query", "")
    selected_concepts = state.get("csod_selected_concepts", [])

    if not user_query:
        logger.warning("No user query provided for skill identification")
        state["csod_identified_skills"] = []
        state["csod_primary_skill"] = None
        return state

    concept_context = ""
    if selected_concepts:
        concept_names = ", ".join(c.get("display_name", "") for c in selected_concepts)
        concept_context = f"\nConfirmed topic area(s): {concept_names}"
    enriched_query = user_query + concept_context

    skills_config = load_skills_config()
    skill_info = _identify_skills_with_llm(enriched_query, skills_config)
    
    if skill_info:
        primary_skill = skill_info.get("primary_skill")
        secondary_skills = skill_info.get("secondary_skills", [])
        reasoning = skill_info.get("reasoning", "")
        
        # Store identified skills
        all_skills = [primary_skill] + secondary_skills
        state["csod_identified_skills"] = all_skills
        state["csod_primary_skill"] = primary_skill
        state["csod_skill_reasoning"] = reasoning
        
        primary_display = skills_config.get("skills", {}).get(primary_skill, {}).get("display_name", primary_skill or "")
        concept_context = ", ".join(c.get("display_name", "") for c in selected_concepts) if selected_concepts else ""
        _set_node_output(
            state, "csod_skill_identifier",
            status="success",
            findings={
                "primary_skill": primary_skill,
                "primary_display": primary_display,
                "secondary_skills": secondary_skills,
                "reasoning": reasoning,
                "concept_context": concept_context,
            },
            next_step="csod_scoping_node",
        )
        logger.info(
            f"Identified skills: primary={primary_skill}, "
            f"secondary={secondary_skills}, reasoning={reasoning[:100]}"
        )
    else:
        # Fallback: use default skill
        logger.warning("LLM skill identification failed, using default")
        state["csod_identified_skills"] = []
        state["csod_primary_skill"] = None
        _set_node_output(state, "csod_skill_identifier", status="success", findings={"primary_skill": None, "primary_display": "", "secondary_skills": [], "reasoning": "Defaulted to workflow.", "concept_context": ""}, next_step="csod_scoping_node")
    
    return state


def csod_workflow_router_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Phase 0 Final: Route to appropriate downstream workflow based on identified skills.
    
    Uses skills configuration to map identified skills to agents.
    """
    primary_skill = state.get("csod_primary_skill")
    skills_config = load_skills_config()
    
    # Determine target workflow based on skill
    if primary_skill:
        target_workflow = get_agent_for_skill(primary_skill, skills_config)
        state["csod_target_workflow"] = target_workflow
        logger.info(f"Routing to {target_workflow} based on skill: {primary_skill}")
    else:
        # Fallback: use default agent
        target_workflow = skills_config.get("default_agent", "csod_workflow")
        state["csod_target_workflow"] = target_workflow
        logger.info(f"No skill identified, using default workflow: {target_workflow}")
    
    # Intent will be determined by csod_intent_classifier in the main workflow
    state["csod_intent"] = None
    
    primary_area = state.get("csod_primary_area", {})
    
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
    
    # Mark this as planner output with next agent to call
    state["is_planner_output"] = True
    state["next_agent_id"] = _get_agent_id_from_workflow(target_workflow, skills_config)
    state["csod_planner_checkpoint"] = None

    _set_node_output(
        state, "csod_workflow_router",
        status="success",
        findings={
            "target_workflow": target_workflow,
            "next_agent_id": state["next_agent_id"],
            "intent": state.get("csod_intent"),
            "reason": f"Skill maps to {target_workflow}.",
        },
        next_step=None,
    )
    logger.info(f"Planner complete: routing to {target_workflow} (agent: {state['next_agent_id']})")
    
    return state


def _get_agent_id_from_workflow(workflow_name: str, skills_config: Optional[Dict[str, Any]] = None) -> str:
    """
    Get the agent ID from workflow name using skills config.
    
    Args:
        workflow_name: Workflow identifier (e.g., "csod_workflow")
        skills_config: Optional skills config (loads if not provided)
    
    Returns:
        Agent ID (e.g., "csod-workflow")
    """
    if skills_config is None:
        skills_config = load_skills_config()
    
    agent_mapping = skills_config.get("agent_mapping", {})
    workflow_info = agent_mapping.get(workflow_name, {})
    agent_id = workflow_info.get("agent_id")
    
    if agent_id:
        return agent_id
    
    # Fallback mapping (legacy workflow name → main CSOD agent)
    if workflow_name == "csod_metric_advisor_workflow":
        return "csod-workflow"
    if workflow_name == "csod_workflow":
        return "csod-workflow"
    return "csod-workflow"


# ============================================================================
# Routing functions
# ============================================================================

def csod_planner_router_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Router node that determines workflow entry point.
    
    If datasource is already provided/confirmed, skip datasource selection and go to concept resolver.
    Otherwise, start with datasource selection.
    """
    # Check response state first - if datasource was responded to, use that
    checkpoint_responses = state.get("csod_checkpoint_responses", {})
    datasource_response = checkpoint_responses.get("datasource_select")
    concept_response = checkpoint_responses.get("concept_select")
    
    # Fix 1: Clear stale concept confirmation flags unless we're responding to a concept checkpoint
    # This prevents stale checkpointer state from bypassing concept selection on fresh runs
    if not concept_response:
        # Not responding to concept checkpoint - clear any stale flags from previous runs
        if state.get("csod_concepts_confirmed") and not state.get("csod_confirmed_concept_ids"):
            # Has confirmed flag but no IDs - likely stale from checkpointer
            logger.info("Clearing stale csod_concepts_confirmed flag (no concept response in payload)")
            state["csod_concepts_confirmed"] = False
        elif state.get("csod_concepts_confirmed") and not state.get("csod_concept_matches"):
            # Has confirmed flag and IDs but no matches - likely stale
            logger.info("Clearing stale csod_concepts_confirmed flag (no concept matches in state)")
            state["csod_concepts_confirmed"] = False
            state["csod_confirmed_concept_ids"] = []
    
    if datasource_response:
        selected_datasource = datasource_response.get("csod_selected_datasource")
        datasource_confirmed = datasource_response.get("csod_datasource_confirmed", True)
        
        if selected_datasource:
            state["csod_selected_datasource"] = selected_datasource
            state["csod_datasource_confirmed"] = datasource_confirmed
            logger.info(f"Datasource from response state ({selected_datasource}), skipping datasource selection")
    else:
        # Check if datasource is already provided (legacy or initial state)
        selected_datasource = state.get("csod_selected_datasource")
        datasource_confirmed = state.get("csod_datasource_confirmed", False)
        
        # If datasource is already selected and confirmed, we can skip datasource selection
        if selected_datasource and datasource_confirmed:
            logger.info(f"Datasource already provided ({selected_datasource}), skipping datasource selection")
            # Ensure it's set in state
            state["csod_selected_datasource"] = selected_datasource
            state["csod_datasource_confirmed"] = True
        elif selected_datasource:
            # Datasource is selected but not confirmed - still skip selection (assume it's valid)
            logger.info(f"Datasource already selected ({selected_datasource}), skipping datasource selection")
            state["csod_selected_datasource"] = selected_datasource
            # Auto-confirm if not already confirmed
            if not datasource_confirmed:
                state["csod_datasource_confirmed"] = True
    
    # This node just passes through state - routing decision is made by _route_from_planner_router
    return state


def _route_from_planner_router(state: EnhancedCompliancePipelineState) -> str:
    """
    Route from planner router.

    Datasource is only required if the concept registry demands source filtering.
    In the CSOD L1 collection, concepts are not source-filtered (connected_source_ids=[]).
    Concept resolution can run without a confirmed datasource. Always start with
    concept_resolver; datasource is inferred from concept domain if not set.
    """
    selected_datasource = state.get("csod_selected_datasource")
    datasource_confirmed = state.get("csod_datasource_confirmed", False)

    if datasource_confirmed and selected_datasource:
        logger.info(f"Datasource confirmed ({selected_datasource}), going direct to concept_resolver")
        return "csod_concept_resolver"

    # No confirmed datasource — still go to concept_resolver first.
    # csod_datasource_selector is only reachable as fallback if needed later.
    logger.info("No confirmed datasource, starting with concept_resolver")
    return "csod_concept_resolver"


def _route_after_datasource_selector(state: EnhancedCompliancePipelineState) -> str:
    """After datasource selection, check for checkpoint or go to concept resolver."""
    # Check response state first - if datasource was responded to, continue
    checkpoint_responses = state.get("csod_checkpoint_responses", {})
    if checkpoint_responses.get("datasource_select"):
        logger.info("Datasource responded to (via response state), routing to concept resolver")
        # Clear any existing checkpoint since we have a response
        if "csod_planner_checkpoint" in state:
            logger.info("Clearing datasource checkpoint (response state present)")
            state["csod_planner_checkpoint"] = None
        return "csod_concept_resolver"
    
    # If datasource is confirmed (legacy check), always go to concept resolver (skip checkpoint)
    if state.get("csod_datasource_confirmed") and state.get("csod_selected_datasource"):
        logger.info("Datasource confirmed (legacy), routing to concept resolver")
        # Clear any existing checkpoint since datasource is confirmed
        if "csod_planner_checkpoint" in state:
            logger.info("Clearing datasource checkpoint (datasource confirmed)")
            state["csod_planner_checkpoint"] = None
        return "csod_concept_resolver"
    
    # Check if checkpoint requires user input (only if no response state)
    checkpoint = state.get("csod_planner_checkpoint")
    if checkpoint and checkpoint.get("requires_user_input", False):
        # Only route to wait if it's a datasource checkpoint
        checkpoint_phase = checkpoint.get("phase")
        if checkpoint_phase == "datasource_select":
            return "wait_for_user_input"
        # Otherwise, continue to concept resolver
        logger.info(f"Checkpoint phase is {checkpoint_phase}, continuing to concept resolver")
        return "csod_concept_resolver"
    return "csod_concept_resolver"


def _route_after_concept_resolver(state: EnhancedCompliancePipelineState) -> str:
    """After concept resolution, check for checkpoint or go to skill identifier."""
    checkpoint_responses = state.get("csod_checkpoint_responses", {})
    if checkpoint_responses.get("concept_select"):
        logger.info("Concepts responded to (via response state), routing to skill_identifier")
        if "csod_planner_checkpoint" in state:
            state["csod_planner_checkpoint"] = None
        return "csod_skill_identifier"
    if state.get("csod_concepts_confirmed") and state.get("csod_confirmed_concept_ids"):
        logger.info("Concepts confirmed (legacy), routing to skill_identifier")
        if "csod_planner_checkpoint" in state:
            state["csod_planner_checkpoint"] = None
        return "csod_skill_identifier"
    # Use csod_concept_matches (declared in EnhancedCompliancePipelineState): if matches exist
    # but user hasn't confirmed yet, pause for user input.
    concept_matches = state.get("csod_concept_matches", [])
    if concept_matches:
        logger.info(
            f"concept_resolver produced {len(concept_matches)} match(es), "
            "concepts not yet confirmed → waiting for user input"
        )
        return "wait_for_user_input"
    # No matches found (empty result or error) → fall through to skill_identifier
    logger.info("No concept matches found, routing directly to skill_identifier")
    return "csod_skill_identifier"


def _route_after_skill_identifier(state: EnhancedCompliancePipelineState) -> str:
    """After skill identification, go to scoping node."""
    logger.info(
        "After csod_skill_identifier → csod_scoping_node (skill=%r)",
        state.get("csod_primary_skill"),
    )
    return "csod_scoping_node"


def _route_after_scoping(state: EnhancedCompliancePipelineState) -> str:
    """After scoping: wait for user if checkpoint set, else area_matcher or workflow_router by needs_area_matching."""
    scoping_complete = state.get("csod_scoping_complete")
    if scoping_complete is False:
        # Explicitly marked not-complete by csod_scoping_node when questions are pending.
        logger.info("Scoping not complete (csod_scoping_complete=False) → waiting for user input")
        return "wait_for_user_input"
    if scoping_complete is None:
        # Field not set yet (first turn, before scoping node ran).
        # Fall back to the checkpoint flag as belt-and-suspenders; if that's also absent,
        # assume scoping is not needed and continue.
        checkpoint = state.get("csod_planner_checkpoint")
        if checkpoint and checkpoint.get("phase") == "scoping" and checkpoint.get("requires_user_input"):
            return "wait_for_user_input"
    primary_skill = state.get("csod_primary_skill")
    skills_config = load_skills_config()
    skill_info = skills_config.get("skills", {}).get(primary_skill or "", {})
    if skill_info.get("needs_area_matching", True):
        return "csod_area_matcher"
    return "csod_workflow_router"


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
    
    The workflow supports two modes:
    1. Full flow: datasource selection → concept selection → area matcher → skill identifier → workflow router
    2. Skip datasource: concept selection → area matcher → skill identifier → workflow router
        (when datasource is already provided in initial state)
    """
    workflow = StateGraph(EnhancedCompliancePipelineState)
    
    # Add nodes
    workflow.add_node("csod_planner_router", csod_planner_router_node)
    workflow.add_node("csod_datasource_selector", csod_datasource_selector_node)
    workflow.add_node("csod_concept_resolver", csod_concept_resolver_node)
    workflow.add_node("csod_skill_identifier", csod_skill_identifier_node)
    workflow.add_node("csod_scoping_node", csod_scoping_node)
    workflow.add_node("csod_area_matcher", csod_area_matcher_node)
    workflow.add_node("csod_workflow_router", csod_workflow_router_node)
    
    # Set entry point to router (always goes to concept_resolver; datasource resolved downstream)
    workflow.set_entry_point("csod_planner_router")
    workflow.add_conditional_edges(
        "csod_planner_router",
        _route_from_planner_router,
        {"csod_concept_resolver": "csod_concept_resolver"},
    )
    
    # Add edges from datasource selector
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
        {
            "csod_skill_identifier": "csod_skill_identifier",
            "wait_for_user_input": END,
        },
    )
    workflow.add_conditional_edges(
        "csod_skill_identifier",
        _route_after_skill_identifier,
        {"csod_scoping_node": "csod_scoping_node"},
    )
    workflow.add_conditional_edges(
        "csod_scoping_node",
        _route_after_scoping,
        {
            "csod_area_matcher": "csod_area_matcher",
            "csod_workflow_router": "csod_workflow_router",
            "wait_for_user_input": END,
        },
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
        use_advisor_workflow: Legacy flag (ignored; routing uses csod_workflow only)
    
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
        
        # Skill identification fields
        "csod_identified_skills": [],
        "csod_primary_skill": None,
        "csod_skill_reasoning": None,

        # Planner narrator (streaming thinking)
        "csod_reasoning_narrative": [],
        
        # Base state fields
        "compliance_profile": {},
        "active_project_id": None,
        "selected_data_sources": [],
    }


# ============================================================================
# Helper: Extract planner output for downstream agent
# ============================================================================

def extract_planner_output_for_agent(planner_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract planner output and format it for downstream agent invocation.
    
    This function prepares the planner state to be passed to the next agent.
    The agent_invocation_service will use this to build the initial state
    for the downstream workflow.
    
    Args:
        planner_state: Final state from planner workflow
    
    Returns:
        Dict with planner output ready for agent invocation
    """
    return {
        "planner_output": planner_state,
        "next_agent_id": planner_state.get("next_agent_id", "csod-workflow"),
        "target_workflow": planner_state.get("csod_target_workflow", "csod_workflow"),
        "user_query": planner_state.get("user_query", ""),
        "session_id": planner_state.get("session_id", ""),
        "active_project_id": planner_state.get("active_project_id"),
        "selected_data_sources": planner_state.get("selected_data_sources", []),
        "compliance_profile": planner_state.get("compliance_profile", {}),
        "csod_intent": planner_state.get("csod_intent"),
        "csod_causal_graph_enabled": planner_state.get("csod_causal_graph_enabled", False),
    }


if __name__ == "__main__":
    app = get_csod_planner_app()
    print("CSOD Planner workflow compiled successfully!")
    print(f"Nodes: {list(app.nodes.keys())}")

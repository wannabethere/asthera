"""
LangGraph workflow nodes for the compliance pipeline.

This module contains all agent nodes that make up the compliance automation workflow,
including intent classification, planning, execution, validation, and refinement.
"""
import json
import logging
import re
import ast
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.state import (
    EnhancedCompliancePipelineState,
    PlanStep,
    ValidationResult,
)
from app.agents.prompt_loader import load_prompt
from app.agents.shared.tool_integration import (
    intelligent_retrieval,
    get_tools_for_agent,
    format_retrieved_context_for_prompt,
    create_tool_calling_agent,
    should_use_tool_calling_agent,
)
from app.core.dependencies import get_llm
from app.retrieval.service import RetrievalService

logger = logging.getLogger(__name__)


# ============================================================================
# Step-by-Step Execution Logging (JSON output)
# ============================================================================

def log_execution_step(
    state: EnhancedCompliancePipelineState,
    step_name: str,
    agent_name: str,
    inputs: Dict[str, Any],
    outputs: Dict[str, Any],
    status: str = "completed",
    error: Optional[str] = None
) -> None:
    """
    Log an execution step to the state for JSON output.
    
    Args:
        state: The pipeline state
        step_name: Name of the step (e.g., "test_generation", "mdl_retrieval")
        agent_name: Name of the agent executing this step
        inputs: Input data for this step
        outputs: Output data from this step
        status: Step status ("completed", "failed", "skipped")
        error: Error message if status is "failed"
    """
    if "execution_steps" not in state:
        state["execution_steps"] = []
    
    step = {
        "step_name": step_name,
        "agent_name": agent_name,
        "timestamp": datetime.utcnow().isoformat(),
        "status": status,
        "inputs": inputs,
        "outputs": outputs,
        "error": error
    }
    
    state["execution_steps"].append(step)


# ============================================================================
# Intent Classifier Node
# ============================================================================

def intent_classifier_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Classifies user intent and extracts metadata (framework, requirement code, etc.).
    Can use web search tools for context on frameworks/requirements.
    """
    # Bypass if intent is pre-resolved by conversation planner
    if state.get("intent") and state.get("compliance_profile", {}).get("playbook_resolved_intent"):
        logger.info(f"Intent pre-resolved: {state['intent']}")
        return state  # skip LLM call
    
    try:
        prompt_text = load_prompt("01_intent_classifier")
        
        # Get tools conditionally
        tools = get_tools_for_agent("intent_classifier", state=state, conditional=True)
        use_tool_calling = should_use_tool_calling_agent("intent_classifier", state=state)
        
        llm = get_llm(temperature=0)
        
        # Format the human message with user query first
        formatted_human_message = f"User Query: {state['user_query']}"
        
        # Try to use tool-calling agent if tools are available
        if use_tool_calling and tools:
            try:
                system_prompt = prompt_text + "\n\nYou have access to web search tools to look up framework details if needed."
                
                # Escape curly braces in system prompt to prevent LangChain from parsing JSON examples as template variables
                system_prompt = system_prompt.replace("{", "{{").replace("}", "}}")
                
                # Use a prompt template with agent_scratchpad for tool-calling agent
                prompt = ChatPromptTemplate.from_messages([
                    ("system", system_prompt),
                    ("human", "{input}"),  # Single variable for the formatted input
                    MessagesPlaceholder(variable_name="agent_scratchpad")  # Required for tool-calling agent
                ])
                
                agent_executor = create_tool_calling_agent(
                    llm=llm,
                    tools=tools,
                    prompt=prompt,
                    use_react_agent=False,  # Use direct tool-calling agent to avoid stop sequence issues
                    executor_kwargs={"max_iterations": 3, "verbose": False}
                )
                
                if agent_executor:
                    response = agent_executor.invoke({
                        "input": formatted_human_message
                    })
                    # Extract content from agent response
                    if isinstance(response, dict) and "output" in response:
                        response_content = response["output"]
                    else:
                        response_content = str(response)
                    
                    # Store the raw LLM response for review
                    state["llm_response"] = response_content
                    state["llm_prompt"] = {
                        "system_prompt": system_prompt,
                        "human_message": formatted_human_message
                    }
                    
                    # Log tool-calling agent invocation step
                    log_execution_step(
                        state=state,
                        step_name="llm_invocation_with_tools",
                        agent_name="intent_classifier",
                        inputs={
                            "system_prompt_length": len(system_prompt),
                            "human_message_length": len(formatted_human_message),
                            "tools_available": len(tools),
                            "tool_names": [getattr(t, 'name', str(t)) for t in tools] if tools else [],
                            "user_query": state["user_query"]
                        },
                        outputs={
                            "response_length": len(response_content),
                            "response_preview": response_content[:500] if len(response_content) > 500 else response_content
                        },
                        status="completed"
                    )
                else:
                    raise ValueError("Agent executor creation failed")
            except Exception as e:
                logger.warning(f"Tool-calling agent failed for intent_classifier, falling back to simple chain: {e}")
                use_tool_calling = False
        
        # Fallback to simple LLM chain
        if not use_tool_calling:
            # Escape curly braces in system prompt to prevent LangChain from parsing JSON examples as template variables
            system_prompt = prompt_text.replace("{", "{{").replace("}", "}}")
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "{input}")  # Single variable for the formatted input
            ])
            chain = prompt | llm
            response = chain.invoke({
                "input": formatted_human_message
            })
            response_content = response.content if hasattr(response, 'content') else str(response)
            
            # Store the raw LLM response for review
            state["llm_response"] = response_content
            state["llm_prompt"] = {
                "system_prompt": system_prompt,
                "human_message": formatted_human_message
            }
            
            # Log LLM invocation step
            log_execution_step(
                state=state,
                step_name="llm_invocation",
                agent_name="intent_classifier",
                inputs={
                    "system_prompt_length": len(system_prompt),
                    "human_message_length": len(formatted_human_message),
                    "user_query": state["user_query"]
                },
                outputs={
                    "response_length": len(response_content),
                    "response_preview": response_content[:500] if len(response_content) > 500 else response_content
                },
                status="completed"
            )
        
        # Parse JSON response
        try:
            result = json.loads(response_content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                # Fallback: try to parse as plain JSON
                try:
                    result = json.loads(response_content)
                except:
                    # Last resort: create minimal result
                    result = {"intent": "requirement_analysis", "framework_id": None, "requirement_code": None}
        
        # Update state with classification results
        state["intent"] = result.get("intent", "requirement_analysis")
        state["framework_id"] = result.get("framework_id")
        state["requirement_code"] = result.get("requirement_code")
        
        # Store extracted metadata
        if "scope_indicators" in result:
            scope = result["scope_indicators"]
            # Could store domain, asset_type, risk_area if needed
        
        # Store data enrichment signals
        if "data_enrichment" in result:
            state["data_enrichment"] = result["data_enrichment"]
        else:
            # Default values if not provided
            state["data_enrichment"] = {
                "needs_mdl": False,
                "needs_metrics": False,
                "needs_xsoar_dashboard": False,
                "suggested_focus_areas": [],
                "metrics_intent": None
            }
        
        # Log intent classification step
        log_execution_step(
            state=state,
            step_name="intent_classification",
            agent_name="intent_classifier",
            inputs={
                "user_query": state["user_query"]
            },
            outputs={
                "intent": state["intent"],
                "framework_id": state.get("framework_id"),
                "requirement_code": state.get("requirement_code"),
                "data_enrichment": state.get("data_enrichment"),
                "classification_result": result
            },
            status="completed"
        )
        
        state["messages"].append(AIMessage(
            content=f"Classified intent: {state['intent']}, Framework: {state.get('framework_id', 'N/A')}"
        ))
        
    except Exception as e:
        logger.error(f"Intent classification failed: {e}", exc_info=True)
        state["error"] = f"Intent classification failed: {str(e)}"
        state["intent"] = "requirement_analysis"  # Fallback
        state["messages"].append(AIMessage(
            content="Intent classification encountered an error. Defaulting to requirement_analysis."
        ))
    
    return state


# ============================================================================
# Profile Resolver Node
# ============================================================================

def profile_resolver_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Resolves tenant compliance profile and selected data sources.
    
    With human-in-the-loop:
    - Uses LLM to recommend data sources based on user query
    - Creates checkpoint for user to select data sources
    - After selection, creates checkpoint for focus area selection
    """
    try:
        logger.info("Profile resolver node executing")
        
        # Get data_enrichment early so it's always available for logging
        data_enrichment = state.get("data_enrichment", {})
        user_query = state.get("user_query", "")
        framework_id = (state.get("framework_id") or "").lower()
        
        # Check if user has provided checkpoint input for data source selection
        user_checkpoint_input = state.get("user_checkpoint_input", {})
        checkpoint_type = user_checkpoint_input.get("checkpoint_type", "")
        
        # Initialize checkpoints list if not exists
        if "checkpoints" not in state:
            state["checkpoints"] = []
        
        # Check if we already have selected data sources from checkpoint
        if checkpoint_type == "profile_resolver_data_sources":
            # User has selected data sources, use them
            selected_data_sources = user_checkpoint_input.get("selected_data_sources", [])
            logger.info(f"Using user-selected data sources: {selected_data_sources}")
            
            # Update compliance profile (initialize if None)
            compliance_profile = state.get("compliance_profile")
            if compliance_profile is None:
                compliance_profile = {}
            compliance_profile["data_sources"] = selected_data_sources
            state["compliance_profile"] = compliance_profile
            state["selected_data_sources"] = selected_data_sources
            
        elif checkpoint_type == "profile_resolver_focus_areas":
            # User has selected focus areas, use them
            selected_focus_areas = user_checkpoint_input.get("selected_focus_areas", [])
            logger.info(f"Using user-selected focus areas: {selected_focus_areas}")
            
            # Filter resolved focus areas to only include selected ones
            all_focus_areas = state.get("resolved_focus_areas", [])
            resolved_focus_areas = [
                fa for fa in all_focus_areas 
                if fa.get("id") in selected_focus_areas or fa.get("name") in selected_focus_areas
            ]
            state["resolved_focus_areas"] = resolved_focus_areas
            
            # Update categories
            focus_area_categories = []
            for fa in resolved_focus_areas:
                categories = fa.get("categories", [])
                for cat in categories:
                    if cat not in focus_area_categories:
                        focus_area_categories.append(cat)
            state["focus_area_categories"] = focus_area_categories
            
            # No more checkpoints needed
            return state
        
        # Check if we need to get data source recommendations
        compliance_profile = state.get("compliance_profile")
        selected_data_sources = state.get("selected_data_sources", [])
        
        if not selected_data_sources:
            # Need to get data source recommendations and create checkpoint
            logger.info("Getting data source recommendations")
            
            # Get all available data sources
            from app.config.focus_areas import get_all_supported_data_sources
            all_sources = get_all_supported_data_sources()
            
            # Get taxonomy focus areas from intent classifier (if available)
            suggested_focus_areas = data_enrichment.get("suggested_focus_areas", [])
            
            # Use focus areas to recommend data sources based on source_capabilities_pattern
            recommended_by_focus_areas = []
            if suggested_focus_areas:
                logger.info(f"Using {len(suggested_focus_areas)} taxonomy focus areas to recommend data sources")
                from app.config.focus_areas.taxonomy_loader import get_focus_area_by_id
                
                # Map focus areas to recommended data sources via source_capabilities_pattern
                focus_area_to_sources = {}
                for fa_id in suggested_focus_areas:
                    fa_def = get_focus_area_by_id(fa_id)
                    if fa_def:
                        patterns = fa_def.get("source_capabilities_pattern", [])
                        # Extract data source names from patterns (e.g., "qualys.*" -> "qualys")
                        for pattern in patterns:
                            if pattern.endswith(".*"):
                                source_name = pattern[:-2]
                                if source_name in all_sources:
                                    if fa_id not in focus_area_to_sources:
                                        focus_area_to_sources[fa_id] = []
                                    if source_name not in focus_area_to_sources[fa_id]:
                                        focus_area_to_sources[fa_id].append(source_name)
                            else:
                                # Handle patterns like "snyk.auth_access" -> "snyk"
                                source_name = pattern.split(".")[0]
                                if source_name in all_sources:
                                    if fa_id not in focus_area_to_sources:
                                        focus_area_to_sources[fa_id] = []
                                    if source_name not in focus_area_to_sources[fa_id]:
                                        focus_area_to_sources[fa_id].append(source_name)
                
                # Collect all recommended sources with their focus areas
                source_scores = {}
                for fa_id, sources in focus_area_to_sources.items():
                    for source in sources:
                        if source not in source_scores:
                            source_scores[source] = {"count": 0, "focus_areas": []}
                        source_scores[source]["count"] += 1
                        source_scores[source]["focus_areas"].append(fa_id)
                
                # Create recommendations from focus area mappings
                for source, info in sorted(source_scores.items(), key=lambda x: x[1]["count"], reverse=True):
                    recommended_by_focus_areas.append({
                        "name": source,
                        "description": f"Supports {len(info['focus_areas'])} focus area(s): {', '.join(info['focus_areas'])}",
                        "relevance_score": min(10, 5 + info["count"] * 2),  # Score based on number of matching focus areas
                        "recommended_by": "focus_areas"
                    })
                
                logger.info(f"Recommended {len(recommended_by_focus_areas)} data sources based on focus areas")
            
            # Use LLM to recommend additional data sources or refine recommendations
            llm = get_llm()
            
            # Build prompt with focus area context
            focus_area_context = ""
            if suggested_focus_areas:
                from app.config.focus_areas.taxonomy_loader import get_focus_area_by_id
                focus_area_descriptions = []
                for fa_id in suggested_focus_areas:
                    fa_def = get_focus_area_by_id(fa_id)
                    if fa_def:
                        focus_area_descriptions.append(f"- {fa_id}: {fa_def.get('description', '')}")
                focus_area_context = f"\nRelevant Focus Areas (from intent classifier):\n" + "\n".join(focus_area_descriptions)
            
            prompt = f"""Based on the following user query, compliance framework, and focus areas, recommend the most relevant data sources.

User Query: {user_query}
Framework: {framework_id or "SOC 2"}
Available Data Sources: {', '.join(all_sources)}
{focus_area_context}
{'Already recommended by focus areas: ' + ', '.join([r['name'] for r in recommended_by_focus_areas]) if recommended_by_focus_areas else ''}

For each data source, provide:
- name: The data source ID
- description: Why this source is relevant
- relevance_score: 1-10 score

Return a JSON array of recommended data sources, ordered by relevance.
Example format:
[
  {{"name": "qualys", "description": "Vulnerability scanning for infrastructure", "relevance_score": 9}},
  {{"name": "snyk", "description": "Application security scanning", "relevance_score": 8}}
]

Return only the JSON array, no other text."""
            
            try:
                response = llm.invoke(prompt)
                response_text = response.content if hasattr(response, 'content') else str(response)
                
                # Parse JSON response
                json_match = re.search(r'\[.*?\]', response_text, re.DOTALL)
                if json_match:
                    llm_recommendations = json.loads(json_match.group(0))
                else:
                    llm_recommendations = []
            except Exception as e:
                logger.warning(f"Failed to get LLM recommendations: {e}")
                llm_recommendations = []
            
            # Merge focus area recommendations with LLM recommendations
            # Prioritize focus area recommendations, then add LLM recommendations that aren't duplicates
            recommendations = recommended_by_focus_areas.copy()
            llm_source_names = {r.get("name") for r in llm_recommendations}
            focus_area_source_names = {r.get("name") for r in recommended_by_focus_areas}
            
            # Add LLM recommendations that aren't already recommended by focus areas
            for llm_rec in llm_recommendations:
                if llm_rec.get("name") not in focus_area_source_names:
                    llm_rec["recommended_by"] = "llm"
                    recommendations.append(llm_rec)
            
            # If no recommendations from either source, fallback to all sources
            if not recommendations:
                logger.warning("No recommendations from focus areas or LLM, using all sources")
                recommendations = [{"name": src, "description": f"Data source: {src}", "relevance_score": 5, "recommended_by": "fallback"} for src in all_sources]
            
            # Sort by relevance score (descending)
            recommendations.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
            
            logger.info(f"Final data source recommendations: {len(recommendations)} sources ({len(recommended_by_focus_areas)} from focus areas, {len(llm_recommendations)} from LLM)")
            
            # Create checkpoint for data source selection
            checkpoint = {
                "node": "profile_resolver",
                "type": "profile_resolver_data_sources",
                "data": {
                    "recommended_data_sources": recommendations,
                    "all_available_sources": all_sources,
                    "framework": framework_id or "soc2",
                    "user_query": user_query
                },
                "requires_user_input": True,
                "message": "Please select the data sources you want to use for compliance analysis. The recommendations are based on your query and framework."
            }
            
            state["checkpoints"] = [checkpoint]
            logger.info(f"Created data source selection checkpoint with {len(recommendations)} recommendations")
            return state
        
        # If we have selected data sources but no focus areas yet, create focus area selection checkpoint
        resolved_focus_areas = state.get("resolved_focus_areas", [])
        if not resolved_focus_areas:
            # Resolve all possible focus areas first
            from app.config.focus_areas import (
                get_focus_areas_by_framework,
                get_focus_areas_by_data_source
            )
            
            logger.info(f"Resolving focus areas for data sources: {selected_data_sources}, framework: {framework_id or 'none'}")
            
            all_focus_areas = []
            for data_source in selected_data_sources:
                try:
                    if framework_id:
                        focus_areas = get_focus_areas_by_framework(data_source, framework_id)
                        logger.info(f"Loaded {len(focus_areas)} focus areas for {data_source} with framework {framework_id}")
                    else:
                        focus_areas = get_focus_areas_by_data_source(data_source)
                        logger.info(f"Loaded {len(focus_areas)} focus areas for {data_source} (no framework filter)")
                    
                    for fa in focus_areas:
                        if not any(existing.get("id") == fa.get("id") for existing in all_focus_areas):
                            all_focus_areas.append(fa)
                except Exception as e:
                    logger.warning(f"Error loading focus areas for {data_source}: {e}")
                    # Try without framework filter as fallback
                    try:
                        focus_areas = get_focus_areas_by_data_source(data_source)
                        logger.info(f"Fallback: Loaded {len(focus_areas)} focus areas for {data_source} without framework filter")
                        for fa in focus_areas:
                            if not any(existing.get("id") == fa.get("id") for existing in all_focus_areas):
                                all_focus_areas.append(fa)
                    except Exception as e2:
                        logger.error(f"Failed to load focus areas for {data_source} even without framework filter: {e2}")
            
            logger.info(f"Total unique focus areas resolved: {len(all_focus_areas)}")
            if all_focus_areas:
                sample_categories = set()
                for fa in all_focus_areas[:5]:  # Check first 5
                    sample_categories.update(fa.get('categories', []))
                logger.info(f"Sample focus area categories found: {list(sample_categories)}")
            else:
                logger.warning("No focus areas were resolved! Check if focus area catalog files exist for the selected data sources.")
            
            # Store all focus areas temporarily
            state["resolved_focus_areas"] = all_focus_areas
            
            # Try to use taxonomy focus areas from intent classifier if available
            # This narrows down the set before LLM recommendation
            suggested_focus_areas = data_enrichment.get("suggested_focus_areas", [])
            candidate_focus_areas = all_focus_areas
            
            if suggested_focus_areas:
                logger.info(f"Using {len(suggested_focus_areas)} taxonomy focus areas from intent classifier: {suggested_focus_areas}")
                # Map taxonomy focus areas to data-source-specific focus areas
                from app.config.focus_areas.taxonomy_loader import map_taxonomy_to_data_source_focus_areas
                mapped_focus_areas = map_taxonomy_to_data_source_focus_areas(
                    suggested_focus_areas,
                    all_focus_areas
                )
                if mapped_focus_areas:
                    candidate_focus_areas = mapped_focus_areas
                    logger.info(f"Mapped to {len(candidate_focus_areas)} data-source-specific focus areas")
                else:
                    logger.warning("Could not map taxonomy focus areas to data-source focus areas, using all")
            
            # Use LLM to recommend focus areas from candidate set
            logger.info(f"Getting focus area recommendations from LLM (from {len(candidate_focus_areas)} candidates)")
            
            llm = get_llm()
            focus_areas_summary = [
                {
                    "id": fa.get("id"),
                    "name": fa.get("name"),
                    "description": fa.get("description", ""),
                    "categories": fa.get("categories", [])
                }
                for fa in candidate_focus_areas[:50]  # Limit to first 50 for prompt
            ]
            
            prompt = f"""Based on the user query and selected data sources, recommend the most relevant focus areas.

User Query: {user_query}
Framework: {framework_id or "SOC 2"}
Selected Data Sources: {', '.join(selected_data_sources)}
{'Taxonomy Focus Areas (from intent): ' + ', '.join(suggested_focus_areas) if suggested_focus_areas else ''}
Available Focus Areas: {json.dumps(focus_areas_summary, indent=2)}

For each focus area, provide:
- id: The focus area ID
- name: The focus area name
- description: Why this focus area is relevant
- relevance_score: 1-10 score

Return a JSON array of recommended focus areas, ordered by relevance.
Return only the JSON array, no other text."""
            
            try:
                response = llm.invoke(prompt)
                response_text = response.content if hasattr(response, 'content') else str(response)
                
                # Parse JSON response
                json_match = re.search(r'\[.*?\]', response_text, re.DOTALL)
                if json_match:
                    recommendations = json.loads(json_match.group(0))
                else:
                    # Fallback: use all focus areas
                    recommendations = focus_areas_summary[:10]
            except Exception as e:
                logger.warning(f"Failed to get LLM recommendations: {e}, using top focus areas")
                recommendations = focus_areas_summary[:10]
            
            # Create checkpoint for focus area selection
            checkpoint = {
                "node": "profile_resolver",
                "type": "profile_resolver_focus_areas",
                "data": {
                    "recommended_focus_areas": recommendations,
                    "all_available_focus_areas": focus_areas_summary,
                    "selected_data_sources": selected_data_sources,
                    "framework": framework_id or "soc2",
                    "user_query": user_query
                },
                "requires_user_input": True,
                "message": "Please select the focus areas you want to analyze. The recommendations are based on your query, framework, and selected data sources."
            }
            
            state["checkpoints"] = [checkpoint]
            logger.info(f"Created focus area selection checkpoint with {len(recommendations)} recommendations")
            return state
        
        # If we reach here, we have both data sources and focus areas selected
        # Extract final values
        selected_data_sources = state.get("selected_data_sources", [])
        resolved_focus_areas = state.get("resolved_focus_areas", [])
        
        # Calculate focus area categories
        focus_area_categories = []
        for fa in resolved_focus_areas:
            categories = fa.get("categories", [])
            for cat in categories:
                if cat not in focus_area_categories:
                    focus_area_categories.append(cat)
        
        state["focus_area_categories"] = focus_area_categories
        
        # Log execution step
        log_execution_step(
            state=state,
            step_name="profile_resolution",
            agent_name="profile_resolver",
            inputs={
                "framework_id": framework_id,
                "data_enrichment_signals": data_enrichment.get("data_enrichment_signals", [])
            },
            outputs={
                "compliance_profile": compliance_profile,
                "selected_data_sources": selected_data_sources,
                "resolved_focus_areas_count": len(resolved_focus_areas),
                "focus_area_categories": focus_area_categories
            },
            status="completed"
        )
        
        state["messages"].append(AIMessage(
            content=f"Resolved compliance profile: {len(selected_data_sources)} data sources, "
                   f"{len(resolved_focus_areas)} focus areas, {len(focus_area_categories)} categories"
        ))
        
    except Exception as e:
        logger.error(f"Profile resolver failed: {e}", exc_info=True)
        state["error"] = f"Profile resolver failed: {str(e)}"
        # Set defaults on error
        state["compliance_profile"] = {"framework": "soc2", "data_sources": [], "tenant_field_mappings": {}}
        state["selected_data_sources"] = []
        state["resolved_focus_areas"] = []
        state["focus_area_categories"] = []
    
    return state


# ============================================================================
# Metrics Recommender Node
# ============================================================================

def metrics_recommender_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Filters metrics from leen_metrics_registry based on:
    1. source_capabilities (match tenant's configured data sources)
    2. category (derived from resolved focus areas)
    3. data_capability match (temporal vs semantic based on metrics_intent)
    """
    try:
        logger.info("Metrics recommender node executing")
        
        from app.retrieval.mdl_service import MDLRetrievalService
        
        # Get inputs
        selected_data_sources = state.get("selected_data_sources", [])
        focus_area_categories = state.get("focus_area_categories", [])
        data_enrichment = state.get("data_enrichment", {})
        metrics_intent = data_enrichment.get("metrics_intent", "current_state")
        framework_id = (state.get("framework_id") or "").lower()
        
        if not selected_data_sources:
            logger.warning("No data sources selected, cannot filter metrics")
            state["resolved_metrics"] = []
            return state
        
        # Build source_capabilities filter patterns
        # Each data source maps to capability patterns (e.g., "qualys.*", "snyk.*")
        source_patterns = []
        for ds in selected_data_sources:
            # Standard patterns for known data sources
            pattern_map = {
                "qualys": "qualys.*",
                "snyk": "snyk.*",
                "wiz": "wiz.*",
                "sentinel": "sentinel.*",
            }
            pattern = pattern_map.get(ds.lower(), f"{ds.lower()}.*")
            source_patterns.append(pattern)
        
        # Build search query combining focus area categories
        search_query = " ".join(focus_area_categories) if focus_area_categories else "compliance metrics"
        
        # Search metrics registry
        # Use asyncio to run async operations in sync context
        import asyncio
        mdl_service = MDLRetrievalService()
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                try:
                    import nest_asyncio
                    nest_asyncio.apply()
                    metrics_results = asyncio.run(mdl_service.search_metrics_registry(
                        query=search_query,
                        limit=50  # Get more results, then filter
                    ))
                except ImportError:
                    # nest_asyncio not available, create new event loop in thread
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, mdl_service.search_metrics_registry(query=search_query, limit=50))
                        metrics_results = future.result()
            else:
                metrics_results = loop.run_until_complete(mdl_service.search_metrics_registry(
                    query=search_query,
                    limit=50  # Get more results, then filter
                ))
        except RuntimeError:
            # No event loop, create new one
            metrics_results = asyncio.run(mdl_service.search_metrics_registry(
                query=search_query,
                limit=50  # Get more results, then filter
            ))
        
        # Filter metrics by source_capabilities and category
        # Note: Semantic search already filtered by focus area relevance, so we trust those results
        # Source capabilities filtering is secondary - we prefer matching but don't exclude if missing
        resolved_metrics = []
        
        logger.info(f"Processing {len(metrics_results)} metrics from semantic search (already filtered by focus area relevance)")
        logger.info(f"Applying secondary filters: source_capabilities={source_patterns if selected_data_sources else 'none'}, categories={focus_area_categories}")
        
        for metric_result in metrics_results:
            # Extract metric data from MDLMetricResult
            # MDLMetricResult is a dataclass with: metric_name, metric_definition, kpi_type, thresholds, metadata, score, id
            metadata = metric_result.metadata if hasattr(metric_result, 'metadata') and metric_result.metadata else {}
            
            # Get source_capabilities from metadata (which now includes merged content)
            source_capabilities = metadata.get("source_capabilities", [])
            
            # Check source_capabilities match (preference, not requirement)
            # Since semantic search already filtered by relevance, we trust those results
            # Source capabilities filtering is just a preference/boost, not a hard filter
            source_match_score = 0.0
            if selected_data_sources and source_capabilities:
                for pattern in source_patterns:
                    pattern_prefix = pattern.replace(".*", "")
                    for capability in source_capabilities:
                        if isinstance(capability, str) and capability.startswith(pattern_prefix):
                            source_match_score = 1.0  # Boost score if matches
                            break
                    if source_match_score > 0:
                        break
            elif not selected_data_sources:
                # No data sources specified, accept all (no penalty)
                source_match_score = 0.5
            # If source_capabilities missing but we have data sources, don't exclude, just don't boost
            
            # Check category match (preference, not requirement)
            # Semantic search already filtered by focus area, so we trust category relevance
            metric_category = metadata.get("category", "")
            category_match_score = 0.0
            if not focus_area_categories:
                # No category filter, accept all
                category_match_score = 0.5
            elif not metric_category:
                # No category in metric - semantic search found it relevant, so accept
                category_match_score = 0.3
            elif metric_category in focus_area_categories:
                category_match_score = 1.0  # Exact match
            else:
                # Check if category is related (e.g., "vulnerabilities" matches "vulnerability_management")
                for cat in focus_area_categories:
                    if cat in metric_category or metric_category in cat:
                        category_match_score = 0.8  # Partial match
                        break
                # If no match, still accept (semantic search found it relevant)
                if category_match_score == 0.0:
                    category_match_score = 0.2
            
            # Check data_capability match (if metrics_intent is "trend", prefer temporal)
            data_capability = metadata.get("data_capability", "")
            if not data_capability:
                # Try to get from content or direct attribute
                if hasattr(metric_result, 'data_capability'):
                    data_capability = metric_result.data_capability
                elif hasattr(metric_result, 'content') and isinstance(metric_result.content, dict):
                    data_capability = metric_result.content.get("data_capability", "")
            
            # Handle data_capability as string or list
            if isinstance(data_capability, list):
                data_capability_str = " ".join(str(d) for d in data_capability)
            else:
                data_capability_str = str(data_capability) if data_capability else ""
            if metrics_intent == "trend" and "temporal" not in data_capability_str:
                # Prefer temporal but don't exclude non-temporal
                pass
            elif metrics_intent == "current_state" and "temporal" in data_capability_str:
                # Prefer non-temporal for current_state but don't exclude temporal
                pass
            
            # Extract metric fields from metadata, content, or result object
            def get_field(key, default=None):
                # Check metadata first
                if key in metadata:
                    return metadata[key]
                # Check content dict
                if hasattr(metric_result, 'content') and isinstance(metric_result.content, dict):
                    if key in metric_result.content:
                        return metric_result.content[key]
                # Check direct attribute
                if hasattr(metric_result, key):
                    return getattr(metric_result, key)
                return default
            
            # Calculate combined relevance score
            # Base score from semantic search + boost from source/category matches
            base_score = metric_result.score if hasattr(metric_result, "score") else 0.0
            combined_score = base_score + (source_match_score * 0.1) + (category_match_score * 0.1)
            
            # Add to resolved metrics (accept all metrics from semantic search)
            resolved_metrics.append({
                "metric_id": get_field("metric_id") or get_field("id", "") or metric_result.id or "",
                "name": get_field("name") or metric_result.metric_name or "",
                "description": get_field("description") or metric_result.metric_definition or "",
                "category": metric_category,
                "source_capabilities": source_capabilities if isinstance(source_capabilities, list) else [],
                "source_schemas": get_field("source_schemas", []),
                "kpis": get_field("kpis", []),
                "trends": get_field("trends", []),
                "natural_language_question": get_field("natural_language_question", ""),
                "data_filters": get_field("data_filters", []),
                "data_groups": get_field("data_groups", []),
                "data_capability": data_capability_str if data_capability_str else (data_capability if isinstance(data_capability, (str, list)) else ""),
                "score": combined_score  # Use combined score for ranking
            })
        
        logger.info(f"Processed {len(resolved_metrics)} metrics (all from semantic search, ranked by relevance + source/category match)")
        
        # Sort by combined score (relevance + source/category match boost)
        resolved_metrics.sort(key=lambda m: m.get("score", 0.0), reverse=True)
        
        # Limit to top 20 metrics
        resolved_metrics = resolved_metrics[:20]
        
        state["resolved_metrics"] = resolved_metrics

        try:
            from app.agents.shared.mdl_recommender_schema_scope import retrieve_area_scoped_dt_schemas

            area_schemas = retrieve_area_scoped_dt_schemas(state, limit=15)
            if area_schemas:
                state["dt_resolved_schemas"] = area_schemas
                prev_ctx = state.get("dt_scored_context")
                merged_ctx = dict(prev_ctx) if isinstance(prev_ctx, dict) else {}
                merged_ctx["resolved_schemas"] = area_schemas
                state["dt_scored_context"] = merged_ctx
        except Exception as prefetch_exc:
            logger.warning(
                "metrics_recommender: area-scoped MDL prefetch failed: %s",
                prefetch_exc,
            )
        
        if len(resolved_metrics) == 0:
            logger.warning(f"No metrics resolved. This may indicate an issue with the semantic search or metric structure.")
            if len(metrics_results) > 0:
                sample_metadata = metrics_results[0].metadata if hasattr(metrics_results[0], 'metadata') else {}
                logger.warning(f"Sample metric structure: metadata keys={list(sample_metadata.keys())}")
                logger.warning(f"Sample metric: name={metrics_results[0].metric_name if hasattr(metrics_results[0], 'metric_name') else 'N/A'}")
        
        # ── Enrich metrics with decision tree logic ────────────────────
        # This enriches metrics with decision tree scoring and grouping
        # Can be disabled by setting dt_use_decision_tree=False in state
        use_decision_tree = state.get("dt_use_decision_tree", True)
        if use_decision_tree and resolved_metrics:
            try:
                from app.agents.decision_trees.dt_metric_decision_nodes import enrich_metrics_with_decision_tree
                state = enrich_metrics_with_decision_tree(state)
                logger.info(
                    f"metrics_recommender: Enriched {len(resolved_metrics)} metrics with decision tree. "
                    f"Groups: {len(state.get('dt_metric_groups', []))}, "
                    f"Scored: {len(state.get('dt_scored_metrics', []))}"
                )
            except Exception as e:
                logger.warning(f"metrics_recommender: Decision tree enrichment failed: {e}", exc_info=True)
                # Continue without enrichment - don't fail the node
        
        # Log execution step
        decision_tree_info = {}
        if use_decision_tree and state.get("dt_metric_groups"):
            decision_tree_info = {
                "decision_tree_groups": len(state.get("dt_metric_groups", [])),
                "decision_tree_scored": len(state.get("dt_scored_metrics", [])),
            }
        
        log_execution_step(
            state=state,
            step_name="metrics_resolution",
            agent_name="metrics_recommender",
            inputs={
                "selected_data_sources": selected_data_sources,
                "focus_area_categories": focus_area_categories,
                "metrics_intent": metrics_intent,
                "framework_id": framework_id,
                "decision_tree_enabled": use_decision_tree,
            },
            outputs={
                "resolved_metrics_count": len(resolved_metrics),
                "resolved_metrics": [{"metric_id": m.get("metric_id"), "name": m.get("name"), "category": m.get("category")} for m in resolved_metrics[:5]],
                **decision_tree_info,
            },
            status="completed"
        )
        
        decision_tree_summary = ""
        if use_decision_tree and state.get("dt_metric_groups"):
            groups = state.get("dt_metric_groups", [])
            group_summary = ", ".join(
                f"{g.get('group_name', 'unknown')}({g.get('total_assigned', 0)})"
                for g in groups[:3] if g.get("total_assigned", 0) > 0
            )
            if group_summary:
                decision_tree_summary = f" | Decision tree: {len(groups)} groups ({group_summary})"
        
        state["messages"].append(AIMessage(
            content=f"Resolved {len(resolved_metrics)} metrics from registry matching data sources and focus areas{decision_tree_summary}"
        ))
        
    except Exception as e:
        logger.error(f"Metrics recommender failed: {e}", exc_info=True)
        state["error"] = f"Metrics recommender failed: {str(e)}"
        state["resolved_metrics"] = []
    
    return state


# ============================================================================
# Planner Node
# ============================================================================

def planner_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Breaks down user intent into atomic, context-retrieving steps.
    Can use web search and framework tools for planning context.
    """
    try:
        prompt_text = load_prompt("02_planner")
        
        # Get tools conditionally
        tools = get_tools_for_agent("planner", state=state, conditional=True)
        use_tool_calling = should_use_tool_calling_agent("planner", state=state)
        
        llm = get_llm(temperature=0)
        
        human_message = """
User Query: {user_query}
Intent: {intent}
Framework: {framework_id}
Requirement Code: {requirement_code}
Data Enrichment: {data_enrichment}
Selected Data Sources: {selected_data_sources}
Resolved Focus Areas: {resolved_focus_areas}

Create an execution plan with atomic steps. If data_enrichment flags are present, include enrichment steps (metrics_resolution, schema_resolution, xsoar_pattern_retrieval, calculation_planning) as appropriate.

For schema_resolution step (if needs_mdl: true):
- Use semantic search in MDL collections (leen_db_schema, leen_table_description)
- Construct search query combining: selected data sources + focus areas + user query context
- Example queries: "qualys vulnerabilities scanning assessment" OR "snyk cloud infrastructure security posture"
- The query should help find relevant table schemas for the selected data sources and focus areas
"""
        
        # Skip tool-calling for planner - planning doesn't require tools and tool-calling has compatibility issues
        # The planner just needs to create an execution plan based on the user query and intent
        # Tools are better used by downstream agents (framework_analyzer, detection_engineer, etc.)
        use_tool_calling = False
        
        # Fallback to simple LLM chain
        if not use_tool_calling:
            # Format the human message with actual values first
            data_enrichment = state.get("data_enrichment")
            data_enrichment_str = json.dumps(data_enrichment, indent=2) if data_enrichment else "null"
            
            # Get selected data sources (from tenant profile or state)
            selected_data_sources = state.get("selected_data_sources", [])
            if not selected_data_sources and data_enrichment:
                # Try to infer from compliance_profile if available
                compliance_profile = state.get("compliance_profile")
                if compliance_profile and isinstance(compliance_profile, dict):
                    selected_data_sources = compliance_profile.get("data_sources", [])
            selected_data_sources_str = json.dumps(selected_data_sources) if selected_data_sources else "[]"
            
            # Get resolved focus areas
            resolved_focus_areas = state.get("resolved_focus_areas", [])
            if not resolved_focus_areas and data_enrichment:
                # Use suggested_focus_areas from data_enrichment as fallback
                suggested = data_enrichment.get("suggested_focus_areas", [])
                if suggested:
                    resolved_focus_areas = [{"id": fa, "name": fa} for fa in suggested]
            resolved_focus_areas_str = json.dumps(resolved_focus_areas, indent=2) if resolved_focus_areas else "[]"
            
            formatted_human_message = human_message.format(
                user_query=state["user_query"],
                intent=state.get("intent", "requirement_analysis"),
                framework_id=state.get("framework_id", "null"),
                requirement_code=state.get("requirement_code", "null"),
                data_enrichment=data_enrichment_str,
                selected_data_sources=selected_data_sources_str,
                resolved_focus_areas=resolved_focus_areas_str
            )
            
            # Use a simple prompt template (prompts now use YAML instead of JSON, so no escaping needed)
            prompt = ChatPromptTemplate.from_messages([
                ("system", prompt_text),  # System prompt with YAML examples (no curly braces)
                ("human", "{input}")  # Single variable for the formatted input
            ])
            chain = prompt | llm
            response = chain.invoke({
                "input": formatted_human_message
            })
            response_content = response.content if hasattr(response, 'content') else str(response)
        
        # Parse JSON response
        try:
            plan_data = json.loads(response_content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_content, re.DOTALL)
            if json_match:
                plan_data = json.loads(json_match.group(1))
            else:
                raise ValueError(f"Could not parse plan JSON. Response: {response_content[:500]}")
        
        # Convert to PlanStep objects
        plan_steps = []
        for step_dict in plan_data.get("execution_plan", []):
            step = PlanStep(
                step_id=step_dict["step_id"],
                description=step_dict["description"],
                required_data=step_dict.get("required_data", []),
                retrieval_queries=step_dict.get("retrieval_queries", []),
                agent=step_dict["agent"],
                dependencies=step_dict.get("dependencies", [])
            )
            plan_steps.append(step)
        
        state["execution_plan"] = plan_steps
        state["current_step_index"] = 0
        state["plan_completion_status"] = {}
        
        # Log planning step
        log_execution_step(
            state=state,
            step_name="planning",
            agent_name="planner",
            inputs={
                "user_query": state["user_query"],
                "intent": state.get("intent"),
                "framework_id": state.get("framework_id"),
                "requirement_code": state.get("requirement_code")
            },
            outputs={
                "plan_steps_count": len(plan_steps),
                "plan_steps": [{"step_id": s.step_id, "description": s.description, "agent": s.agent} for s in plan_steps]
            },
            status="completed"
        )
        
        state["messages"].append(AIMessage(
            content=f"Created execution plan with {len(plan_steps)} steps:\n" + 
                    "\n".join([f"{i+1}. {s.description}" for i, s in enumerate(plan_steps)])
        ))
        
    except Exception as e:
        logger.error(f"Planning failed: {e}", exc_info=True)
        state["error"] = f"Planning failed: {str(e)}"
        state["messages"].append(AIMessage(
            content="Could not create plan. Falling back to default workflow."
        ))
    
    return state


# ============================================================================
# Plan Executor Node
# ============================================================================

def plan_executor_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Executes the current step in the plan.
    Routes to appropriate agent based on plan step.
    """
    plan = state.get("execution_plan", [])
    if not plan:
        state["next_agent"] = "validation_orchestrator"
        return state
    
    current_idx = state.get("current_step_index", 0)
    
    if current_idx >= len(plan):
        # Plan complete, move to validation
        state["next_agent"] = "validation_orchestrator"
        return state
    
    current_step = plan[current_idx]
    
    # Check dependencies
    for dep_id in current_step.dependencies:
        if state.get("plan_completion_status", {}).get(dep_id) != "completed":
            state["error"] = f"Step {current_step.step_id} blocked: dependency {dep_id} not completed"
            state["next_agent"] = "FINISH"
            return state
    
    # Mark step as in progress
    current_step.status = "in_progress"
    
    # Execute retrieval queries for this step (if any)
    step_context = {}
    retrieval_service = RetrievalService()
    
    for query in current_step.retrieval_queries:
        try:
            # Check if this is a schema_resolution step (semantic search in MDL collections)
            if current_step.agent == "semantic_search" and "schema" in current_step.description.lower():
                # Handle schema resolution: semantic search in MDL collections
                from app.retrieval.mdl_service import MDLRetrievalService
                mdl_service = MDLRetrievalService()
                
                # Get context filters from step
                context_filter = current_step.context_filter or {}
                data_sources = context_filter.get("data_sources", state.get("selected_data_sources", []))
                focus_areas = context_filter.get("focus_areas", state.get("focus_area_categories", []))
                
                # Build enhanced query combining user query with data sources and focus areas
                enhanced_query = query
                if data_sources:
                    enhanced_query = f"{' '.join(data_sources)} {enhanced_query}"
                if focus_areas:
                    enhanced_query = f"{' '.join(focus_areas)} {enhanced_query}"
                
                # Search both leen_db_schema and leen_table_description
                # Use asyncio to run async operations in sync context
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # If loop is running, use nest_asyncio if available
                        try:
                            import nest_asyncio
                            nest_asyncio.apply()
                            schema_results = asyncio.run(mdl_service.search_db_schema(
                                query=enhanced_query,
                                limit=10
                            ))
                            table_desc_results = asyncio.run(mdl_service.search_table_descriptions(
                                query=enhanced_query,
                                limit=10
                            ))
                        except ImportError:
                            # nest_asyncio not available, create new event loop in thread
                            import concurrent.futures
                            with concurrent.futures.ThreadPoolExecutor() as executor:
                                future1 = executor.submit(asyncio.run, mdl_service.search_db_schema(query=enhanced_query, limit=10))
                                future2 = executor.submit(asyncio.run, mdl_service.search_table_descriptions(query=enhanced_query, limit=10))
                                schema_results = future1.result()
                                table_desc_results = future2.result()
                    else:
                        schema_results = loop.run_until_complete(mdl_service.search_db_schema(
                            query=enhanced_query,
                            limit=10
                        ))
                        table_desc_results = loop.run_until_complete(mdl_service.search_table_descriptions(
                            query=enhanced_query,
                            limit=10
                        ))
                except RuntimeError:
                    # No event loop, create new one
                    schema_results = asyncio.run(mdl_service.search_db_schema(
                        query=enhanced_query,
                        limit=10
                    ))
                    table_desc_results = asyncio.run(mdl_service.search_table_descriptions(
                        query=enhanced_query,
                        limit=10
                    ))
                
                # Format results (MDLSchemaResult has: table_name, schema_ddl, columns, metadata, score, id)
                retrieved_data = {
                    "schemas": [
                        {
                            "table_name": r.table_name,
                            "table_ddl": r.schema_ddl,  # MDLSchemaResult uses schema_ddl
                            "column_metadata": r.columns,  # MDLSchemaResult uses columns
                            "description": r.metadata.get("description", "") if r.metadata else "",
                            "score": r.score,
                            "id": r.id
                        }
                        for r in schema_results
                    ],
                    "table_descriptions": [
                        {
                            "table_name": r.table_name,
                            "description": r.description,
                            "columns": r.relationships if hasattr(r, "relationships") else [],  # May need to check actual structure
                            "relationships": r.relationships if hasattr(r, "relationships") else [],
                            "score": r.score,
                            "id": r.id
                        }
                        for r in table_desc_results
                    ],
                    "query": enhanced_query,
                    "data_sources": data_sources,
                    "focus_areas": focus_areas
                }
                
                step_context[query] = retrieved_data
                
                # Store in context_cache for downstream nodes
                if "context_cache" not in state:
                    state["context_cache"] = {}
                state["context_cache"]["schema_resolution"] = retrieved_data
                
            else:
                # Use intelligent retrieval that routes based on required_data
                retrieved_data = intelligent_retrieval(
                    query=query,
                    required_data=current_step.required_data,
                    framework_id=state.get("framework_id"),
                    retrieval_service=retrieval_service
                )
                step_context[query] = retrieved_data
            
            # Update state with retrieved data (for use by downstream agents)
            if "controls" in retrieved_data and retrieved_data["controls"]:
                existing_controls = state.get("controls", [])
                # Avoid duplicates
                existing_ids = {c.get("id") for c in existing_controls}
                new_controls = [c for c in retrieved_data["controls"] if c.get("id") not in existing_ids]
                state["controls"].extend(new_controls)
            
            if "risks" in retrieved_data and retrieved_data["risks"]:
                existing_risks = state.get("risks", [])
                existing_ids = {r.get("id") for r in existing_risks}
                new_risks = [r for r in retrieved_data["risks"] if r.get("id") not in existing_ids]
                state["risks"].extend(new_risks)
            
            if "scenarios" in retrieved_data and retrieved_data["scenarios"]:
                existing_scenarios = state.get("scenarios", [])
                existing_ids = {s.get("id") for s in existing_scenarios}
                new_scenarios = [s for s in retrieved_data["scenarios"] if s.get("id") not in existing_ids]
                state["scenarios"].extend(new_scenarios)
            
            if "test_cases" in retrieved_data and retrieved_data["test_cases"]:
                existing_test_cases = state.get("test_cases", [])
                existing_ids = {tc.get("id") for tc in existing_test_cases}
                new_test_cases = [tc for tc in retrieved_data["test_cases"] if tc.get("id") not in existing_ids]
                state["test_cases"].extend(new_test_cases)
            
        except Exception as e:
            logger.warning(f"Retrieval query failed for '{query}': {e}")
            step_context[query] = {"error": str(e)}
    
    # Store context for this step
    current_step.context = step_context
    if "context_cache" not in state:
        state["context_cache"] = {}
    state["context_cache"][current_step.step_id] = step_context
    
    # Route to the agent specified in the plan
    state["next_agent"] = current_step.agent
    
    state["messages"].append(AIMessage(
        content=f"Executing Step {current_idx + 1}/{len(plan)}: {current_step.description}"
    ))
    
    return state


# ============================================================================
# Mark Step Complete Node
# ============================================================================

def mark_step_complete_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Marks current step as complete and advances to next step.
    Called after an agent finishes executing.
    """
    plan = state.get("execution_plan", [])
    current_idx = state.get("current_step_index", 0)
    
    if current_idx < len(plan):
        current_step = plan[current_idx]
        current_step.status = "completed"
        if "plan_completion_status" not in state:
            state["plan_completion_status"] = {}
        state["plan_completion_status"][current_step.step_id] = "completed"
        
        # Advance to next step
        state["current_step_index"] = current_idx + 1
    
    # Route back to plan executor to check next step
    state["next_agent"] = "plan_executor"
    
    return state


# ============================================================================
# Framework Analyzer Node (for direct DB lookups)
# ============================================================================

def framework_analyzer_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Performs direct database lookups for requirements, controls, risks, etc.
    Used when exact IDs are known. Can use compliance tools for additional context.
    """
    try:
        retrieval_service = RetrievalService()
        plan = state.get("execution_plan", [])
        current_idx = state.get("current_step_index", 0)
        
        # Get tools conditionally
        tools = get_tools_for_agent("framework_analyzer", state=state, conditional=True)
        
        if current_idx < len(plan):
            current_step = plan[current_idx]
            
            # Based on required_data, fetch from database
            if "requirement_id" in current_step.required_data or "requirement_code" in current_step.required_data:
                if state.get("requirement_code"):
                    # Search for requirement by code using semantic search
                    req_context = retrieval_service.search_requirements(
                        query=state["requirement_code"],
                        limit=1,
                        framework_filter=[state.get("framework_id")] if state.get("framework_id") else None
                    )
                    if req_context and req_context.requirements:
                        req = req_context.requirements[0]
                        state["requirement_id"] = req.id
                        state["requirement_name"] = req.name
                        state["requirement_description"] = req.description
            
            # Fetch controls if needed
            if "controls" in str(current_step.required_data).lower():
                if state.get("requirement_id"):
                    # Get controls for this requirement
                    req_context = retrieval_service.get_requirement_context(state["requirement_id"])
                    if req_context and hasattr(req_context, 'requirements') and req_context.requirements:
                        req = req_context.requirements[0]
                        if hasattr(req, 'satisfying_controls'):
                            # Convert control results to dicts
                            state["controls"] = [
                                {
                                    "id": c.id,
                                    "control_code": getattr(c, 'control_code', c.id),
                                    "name": c.name,
                                    "description": c.description,
                                    "control_type": getattr(c, 'control_type', None),
                                }
                                for c in req.satisfying_controls
                            ]
                
                # Use tools to enrich control information if available
                if tools and state.get("controls"):
                    try:
                        # Use framework_control_search tool to get additional context
                        framework_tool = next((t for t in tools if hasattr(t, 'name') and 'framework_control' in t.name.lower()), None)
                        if framework_tool:
                            # Could enrich controls with tool data
                            logger.debug(f"Framework analyzer has {len(tools)} tools available for enrichment")
                    except Exception as e:
                        logger.warning(f"Failed to use tools in framework_analyzer: {e}")
            
            # Store step output
            current_step.output = {
                "requirement_id": state.get("requirement_id"),
                "controls_count": len(state.get("controls", []))
            }
        
        state["messages"].append(AIMessage(
            content=f"Framework analysis complete. Retrieved {len(state.get('controls', []))} controls."
        ))
        
    except Exception as e:
        logger.error(f"Framework analyzer failed: {e}", exc_info=True)
        state["error"] = f"Framework analysis failed: {str(e)}"
    
    return state


# ============================================================================
# Detection Engineer Node (Enhanced with Feedback)
# ============================================================================

def detection_engineer_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Generates SIEM detection rules. Incorporates feedback from validation if this is a refinement iteration.
    
    This agent actively uses security intelligence tools (CVE, ATT&CK, exploit intelligence) to enrich
    detection rules with threat context.
    """
    try:
        prompt_text = load_prompt("03_detection_engineer")
        
        # Check if this is a refinement iteration
        iteration = state.get("iteration_count", 0)
        refinement_history = state.get("refinement_history", [])
        
        feedback_context = ""
        if iteration > 0 and refinement_history:
            latest_refinement = refinement_history[-1]
            siem_refinements = [
                r for r in latest_refinement.get("refinement_plan", [])
                if r["artifact_type"] == "siem_rule"
            ]
            
            if siem_refinements:
                refinement = siem_refinements[0]
                feedback_context = f"""
PREVIOUS ATTEMPT FAILED. You must fix these issues:

CRITICAL ERRORS (must fix):
{chr(10).join('- ' + fix for fix in refinement.get('specific_fixes', []))}

IMPROVEMENTS (should address):
{chr(10).join('- ' + imp for imp in refinement.get('improvements', []))}

Failed artifact IDs: {refinement.get('failed_artifact_ids', [])}
"""
        
        # Get tools conditionally based on state content
        tools = get_tools_for_agent("detection_engineer", state=state, conditional=True)
        use_tool_calling = should_use_tool_calling_agent("detection_engineer", state=state)
        
        llm = get_llm(temperature=0)
        
        # Retrieve XSOAR playbooks and indicators for detection patterns
        xsoar_context = {}
        try:
            import asyncio
            from app.retrieval.xsoar_service import XSOARRetrievalService
            
            xsoar_service = XSOARRetrievalService()
            
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop = asyncio.new_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
            
            # Search for relevant XSOAR playbooks and indicators
            query = state.get("user_query", "") or "detection monitoring SIEM"
            xsoar_playbooks = loop.run_until_complete(
                xsoar_service.search_playbooks(
                    query=f"{query} detection response",
                    limit=5
                )
            )
            xsoar_indicators = loop.run_until_complete(
                xsoar_service.search_indicators(
                    query=f"{query} IOC detection pattern",
                    limit=5
                )
            )
            
            xsoar_context = {
                "playbooks": [p.__dict__ for p in xsoar_playbooks],
                "indicators": [i.__dict__ for i in xsoar_indicators],
            }
            state["xsoar_indicators"] = [i.__dict__ for i in xsoar_indicators]
        except Exception as e:
            logger.warning(f"XSOAR retrieval failed for detection_engineer: {e}")
        
        # Format scenarios, controls, risks for prompt
        # SCENARIOS ARE PRIMARY CONTEXT - they describe how risks materialize
        scenarios_str = json.dumps(state.get("scenarios", []), indent=2)
        controls_str = json.dumps(state.get("controls", []), indent=2)
        risks_str = json.dumps(state.get("risks", []), indent=2)
        
        # Format XSOAR context (indicators are critical for signal generation)
        xsoar_str = format_retrieved_context_for_prompt(
            {"xsoar": xsoar_context},
            include_mdl=False,
            include_xsoar=True
        ) if xsoar_context else ""
        
        # Build scenario-driven context message
        scenario_context = ""
        if state.get("scenarios"):
            scenario_context = f"""
PRIMARY CONTEXT - ATTACK SCENARIOS:
These scenarios describe HOW the identified risks materialize. Use them to drive signal generation:
{scenarios_str}

For each scenario, identify:
1. What attack patterns/behaviors occur
2. What IOCs/indicators would be present
3. What detection signals would catch this
"""
        
        human_message = """
Requirement: {requirement_name}
{scenario_context}
Risks: {risks}
Controls: {controls}

XSOAR Indicators & Playbooks (for IOC patterns):
{xsoar_str}

Generate SIEM detection rules that:
1. Are driven by the attack scenarios above (scenarios describe HOW risks materialize)
2. Use XSOAR indicators as reference patterns for IOCs
3. Detect the attack patterns described in scenarios
4. Support the controls identified
5. Use available tools to enrich rules with CVE details, ATT&CK mappings, and exploit intelligence when relevant.
"""
        
        # Use tool-calling agent if tools are available
        if use_tool_calling and tools:
            try:
                system_prompt = prompt_text
                if feedback_context:
                    system_prompt += "\n\n" + feedback_context
                system_prompt += f"\n\nYou have access to {len(tools)} security intelligence tools. Use them to look up CVE details, ATT&CK techniques, exploit information, and threat intelligence to enrich your detection rules."
                
                # Format the human message with actual values first
                formatted_human_message = human_message.format(
                    requirement_name=state.get("requirement_name", "N/A"),
                    scenario_context=scenario_context,
                    risks=risks_str,
                    controls=controls_str,
                    xsoar_str=xsoar_str
                )
                
                # Use a prompt template with agent_scratchpad for tool-calling agent
                prompt = ChatPromptTemplate.from_messages([
                    ("system", system_prompt),
                    ("human", "{input}"),  # Single variable for the formatted input
                    MessagesPlaceholder(variable_name="agent_scratchpad")  # Required for tool-calling agent
                ])
                
                agent_executor = create_tool_calling_agent(
                    llm=llm,
                    tools=tools,
                    prompt=prompt,
                    use_react_agent=False,  # Use direct tool-calling agent to avoid stop sequence issues
                    executor_kwargs={"max_iterations": 10, "verbose": False}
                )
                
                if agent_executor:
                    response = agent_executor.invoke({
                        "input": formatted_human_message
                    })
                    response_content = response.get("output", str(response)) if isinstance(response, dict) else str(response)
                else:
                    raise ValueError("Agent executor creation failed")
            except Exception as e:
                logger.warning(f"Tool-calling agent failed for detection_engineer, falling back to simple chain: {e}")
                use_tool_calling = False
        
        # Fallback to simple LLM chain
        if not use_tool_calling:
            system_prompt = prompt_text
            if feedback_context:
                system_prompt += "\n\n" + feedback_context
            if tools:
                system_prompt += f"\n\nNote: {len(tools)} security intelligence tools are available but tool-calling is disabled. Consider mentioning relevant CVEs, ATT&CK techniques, and exploit information in your rules."
            
            # Format the human message with actual values first
            formatted_human_message = human_message.format(
                requirement_name=state.get("requirement_name", "N/A"),
                scenario_context=scenario_context,
                risks=risks_str,
                controls=controls_str,
                xsoar_str=xsoar_str
            )
            
            # Use a simple prompt template with formatted input
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "{input}")  # Single variable for the formatted input
            ])
            chain = prompt | llm
            response = chain.invoke({
                "input": formatted_human_message
            })
            response_content = response.content if hasattr(response, 'content') else str(response)
        
        # Parse JSON response
        try:
            result = json.loads(response_content)
        except json.JSONDecodeError:
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                result = {"siem_rules": [{"raw_content": response_content}]}
        
        # Update state with generated rules
        if "siem_rules" in result:
            state["siem_rules"] = result["siem_rules"]
        
        state["messages"].append(AIMessage(
            content=f"Generated {len(state.get('siem_rules', []))} SIEM rules (iteration {iteration})"
        ))
        
    except Exception as e:
        logger.error(f"Detection engineer failed: {e}", exc_info=True)
        state["error"] = f"Detection engineering failed: {str(e)}"
    
    return state


# ============================================================================
# Playbook Writer Node (Enhanced with Feedback)
# ============================================================================

def playbook_writer_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Generates incident response playbooks. Incorporates feedback from validation.
    Can use threat intelligence and ATT&CK tools for attack context.
    """
    try:
        prompt_text = load_prompt("04_playbook_writer")
        
        # Check for feedback
        iteration = state.get("iteration_count", 0)
        refinement_history = state.get("refinement_history", [])
        
        feedback_context = ""
        if iteration > 0 and refinement_history:
            latest_refinement = refinement_history[-1]
            playbook_refinements = [
                r for r in latest_refinement.get("refinement_plan", [])
                if r["artifact_type"] == "playbook"
            ]
            
            if playbook_refinements:
                refinement = playbook_refinements[0]
                feedback_context = f"""
PREVIOUS ATTEMPT FAILED. You must fix these issues:

CRITICAL ERRORS (must fix):
{chr(10).join('- ' + fix for fix in refinement.get('specific_fixes', []))}

IMPROVEMENTS (should address):
{chr(10).join('- ' + imp for imp in refinement.get('improvements', []))}
"""
        
        # Get tools conditionally
        tools = get_tools_for_agent("playbook_writer", state=state, conditional=True)
        use_tool_calling = should_use_tool_calling_agent("playbook_writer", state=state)
        
        llm = get_llm(temperature=0)
        
        # Retrieve XSOAR playbooks and indicators for reference
        xsoar_context = {}
        try:
            import asyncio
            from app.retrieval.xsoar_service import XSOARRetrievalService
            
            xsoar_service = XSOARRetrievalService()
            
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop = asyncio.new_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
            
            query = state.get("user_query", "") or "incident response playbook"
            xsoar_playbooks = loop.run_until_complete(
                xsoar_service.search_playbooks(
                    query=f"{query} incident response",
                    limit=5
                )
            )
            xsoar_indicators = loop.run_until_complete(
                xsoar_service.search_indicators(
                    query=f"{query} IOC triage",
                    limit=5
                )
            )
            
            xsoar_context = {
                "playbooks": [p.__dict__ for p in xsoar_playbooks],
                "indicators": [i.__dict__ for i in xsoar_indicators],
            }
        except Exception as e:
            logger.warning(f"XSOAR retrieval failed for playbook_writer: {e}")
        
        scenarios_str = json.dumps(state.get("scenarios", []), indent=2)
        controls_str = json.dumps(state.get("controls", []), indent=2)
        test_cases_str = json.dumps(state.get("test_cases", []), indent=2)
        
        xsoar_str = format_retrieved_context_for_prompt(
            {"xsoar": xsoar_context},
            include_mdl=False,
            include_xsoar=True
        ) if xsoar_context else ""
        
        human_message = """
Scenarios: {scenarios}
Controls: {controls}
Test Cases: {test_cases}
Requirement: {requirement_name}

XSOAR Playbook Examples & Indicators:
{xsoar_context}

Generate incident response playbooks. Use available tools to look up threat intelligence, ATT&CK techniques, and attack paths for context.
Use XSOAR playbooks as templates and indicators for triage steps.
"""
        
        # Use tool-calling agent if tools are available
        if use_tool_calling and tools:
            try:
                system_prompt = prompt_text
                if feedback_context:
                    system_prompt += "\n\n" + feedback_context
                system_prompt += f"\n\nYou have access to {len(tools)} threat intelligence and ATT&CK tools. Use them to enrich playbooks with attack context."
                
                # Format the human message with actual values first
                formatted_human_message = human_message.format(
                    scenarios=scenarios_str,
                    controls=controls_str,
                    test_cases=test_cases_str,
                    requirement_name=state.get("requirement_name", "N/A"),
                    xsoar_context=xsoar_str
                )
                
                # Use a prompt template with agent_scratchpad for tool-calling agent
                prompt = ChatPromptTemplate.from_messages([
                    ("system", system_prompt),
                    ("human", "{input}"),  # Single variable for the formatted input
                    MessagesPlaceholder(variable_name="agent_scratchpad")  # Required for tool-calling agent
                ])
                
                agent_executor = create_tool_calling_agent(
                    llm=llm,
                    tools=tools,
                    prompt=prompt,
                    use_react_agent=False,  # Use direct tool-calling agent to avoid stop sequence issues
                    executor_kwargs={"max_iterations": 8, "verbose": False}
                )
                
                if agent_executor:
                    response = agent_executor.invoke({
                        "input": formatted_human_message
                    })
                    response_content = response.get("output", str(response)) if isinstance(response, dict) else str(response)
                else:
                    raise ValueError("Agent executor creation failed")
            except Exception as e:
                logger.warning(f"Tool-calling agent failed for playbook_writer, falling back to simple chain: {e}")
                use_tool_calling = False
        
        # Fallback to simple LLM chain
        if not use_tool_calling:
            system_prompt = prompt_text
            if feedback_context:
                system_prompt += "\n\n" + feedback_context
            
            # Format the human message with actual values first
            formatted_human_message = human_message.format(
                scenarios=scenarios_str,
                controls=controls_str,
                test_cases=test_cases_str,
                requirement_name=state.get("requirement_name", "N/A"),
                xsoar_context=xsoar_str
            )
            
            # Use a simple prompt template with formatted input
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "{input}")  # Single variable for the formatted input
            ])
            chain = prompt | llm
            response = chain.invoke({
                "input": formatted_human_message
            })
            response_content = response.content if hasattr(response, 'content') else str(response)
        
        # Parse response - playbooks are typically in Markdown format
        # The prompt should instruct the LLM to return JSON with playbook content
        try:
            result = json.loads(response_content)
        except json.JSONDecodeError:
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                # Fallback: treat entire response as playbook content
                result = {"playbooks": [{"markdown_content": response_content}]}
        
        if "playbooks" in result:
            state["playbooks"] = result["playbooks"]
        
        state["messages"].append(AIMessage(
            content=f"Generated {len(state.get('playbooks', []))} playbooks (iteration {iteration})"
        ))
        
    except Exception as e:
        logger.error(f"Playbook writer failed: {e}", exc_info=True)
        state["error"] = f"Playbook generation failed: {str(e)}"
    
    return state


# ============================================================================
# Test Generator Node (Enhanced with Feedback)
# ============================================================================

def test_generator_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Generates Python test automation scripts. Incorporates feedback from validation.
    Can use compliance tools for control context.
    """
    try:
        prompt_text = load_prompt("09_test_generator")
        
        # Check for feedback
        iteration = state.get("iteration_count", 0)
        refinement_history = state.get("refinement_history", [])
        
        feedback_context = ""
        if iteration > 0 and refinement_history:
            latest_refinement = refinement_history[-1]
            test_refinements = [
                r for r in latest_refinement.get("refinement_plan", [])
                if r["artifact_type"] == "test_script"
            ]
            
            if test_refinements:
                refinement = test_refinements[0]
                feedback_context = f"""
PREVIOUS ATTEMPT FAILED. You must fix these issues:

CRITICAL ERRORS (must fix):
{chr(10).join('- ' + fix for fix in refinement.get('specific_fixes', []))}

IMPROVEMENTS (should address):
{chr(10).join('- ' + imp for imp in refinement.get('improvements', []))}
"""
        
        # Get tools conditionally
        tools = get_tools_for_agent("test_generator", state=state, conditional=True)
        use_tool_calling = should_use_tool_calling_agent("test_generator", state=state)
        
        llm = get_llm(temperature=0)
        
        # Retrieve LLM Safety context if available (for test generation)
        llm_safety_context = ""
        try:
            from app.retrieval.llm_safety_integration import get_llm_safety_context_sync
            
            # Search for relevant LLM safety techniques and detection rules
            # This helps generate tests that reference real attack patterns
            safety_query = f"testing LLM agents {state.get('query', '')} {state.get('intent', '')}"
            llm_safety_context = get_llm_safety_context_sync(
                query=safety_query,
                limit_per_type=2,
                entity_types=["technique", "detection_rule"]
            )
            if llm_safety_context:
                logger.info("Retrieved LLM Safety context for test generation")
        except Exception as e:
            logger.debug(f"LLM Safety retrieval not available: {e}")
        
        # Retrieve MDL schemas for data model context
        mdl_context = {}
        mdl_query_used = ""
        try:
            import asyncio
            from app.retrieval.mdl_service import MDLRetrievalService
            
            mdl_service = MDLRetrievalService()
            
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop = asyncio.new_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
            
            # Generate MDL query focused on specific entity types that exist in the database
            # CRITICAL: Only search for entities that exist: assets/hosts/devices, networks, vulnerabilities/issues, applications/projects/users
            query = state.get("user_query", "") or "test validation"
            
            # Build focused MDL query based on control context and available entity types
            controls = state.get("controls", [])
            control_types = [c.get("control_type", "").lower() for c in controls]
            control_names = [c.get("name", "").lower() for c in controls]
            
            # Map control context to MDL entity categories that exist in database
            # Available categories: assets, projects, vulnerabilities, issues, applications, users
            # Also: networks (if available), hosts, devices
            mdl_entity_keywords = []
            
            # Check for asset/host/device related controls
            if any("asset" in cn or "host" in cn or "device" in cn or "endpoint" in cn for cn in control_names):
                mdl_entity_keywords.extend(["assets", "hosts", "devices"])
            
            # Check for network related controls
            if any("network" in cn or "network" in ct for cn, ct in zip(control_names, control_types)):
                mdl_entity_keywords.append("networks")
            
            # Check for vulnerability/issue related controls
            if any("vulnerability" in cn or "vulnerability" in ct or "issue" in cn for cn, ct in zip(control_names, control_types)):
                mdl_entity_keywords.extend(["vulnerabilities", "issues"])
            
            # Check for application/project/user related controls
            if any("application" in cn or "app" in cn or "project" in cn or "user" in cn or "access" in cn for cn in control_names):
                mdl_entity_keywords.extend(["applications", "projects", "users"])
            
            # Default to core entity types if no specific focus
            if not mdl_entity_keywords:
                mdl_entity_keywords = ["assets", "hosts", "devices", "vulnerabilities", "issues", "applications", "projects", "users"]
            
            # Build focused query with entity type keywords
            focused_query = f"{query} {' '.join(set(mdl_entity_keywords))} schema tables"
            mdl_query_used = focused_query
            
            mdl_result = loop.run_until_complete(
                mdl_service.search_all_mdl(
                    query=focused_query,
                    limit_per_collection=3
                )
            )
            mdl_context = {
                "db_schemas": [s.__dict__ for s in mdl_result.db_schemas],
                "table_descriptions": [t.__dict__ for t in mdl_result.table_descriptions],
            }
            
            # Log MDL retrieval step
            log_execution_step(
                state=state,
                step_name="mdl_retrieval",
                agent_name="test_generator",
                inputs={
                    "query": focused_query,
                    "entity_focus": list(set(mdl_entity_keywords)),
                    "limit_per_collection": 3
                },
                outputs={
                    "db_schemas_found": len(mdl_result.db_schemas),
                    "table_descriptions_found": len(mdl_result.table_descriptions),
                    "mdl_context_keys": list(mdl_context.keys())
                },
                status="completed"
            )
        except Exception as e:
            error_msg = str(e)
            log_execution_step(
                state=state,
                step_name="mdl_retrieval",
                agent_name="test_generator",
                inputs={"query": mdl_query_used or query},
                outputs={},
                status="failed",
                error=error_msg
            )
        
        controls_str = json.dumps(state.get("controls", []), indent=2)
        test_cases_str = json.dumps(state.get("test_cases", []), indent=2)
        
        mdl_str = format_retrieved_context_for_prompt(
            {"mdl": mdl_context},
            include_mdl=True,
            include_xsoar=False
        ) if mdl_context else ""
        
        # Build LLM Safety Context section
        llm_safety_section = ""
        if llm_safety_context:
            llm_safety_section = f"\nLLM Safety Context (for reference on attack patterns and detection rules):\n{llm_safety_context}"
        
        # Include resolved metrics and calculation plan if available (for data assistant agents)
        resolved_metrics = state.get("resolved_metrics", [])
        calculation_plan = state.get("calculation_plan", {})
        
        metrics_section = ""
        if resolved_metrics:
            # Format metrics for test generation context
            metrics_list = []
            for m in resolved_metrics[:10]:  # Limit to top 10 for prompt size
                metric_info = {
                    "metric_id": m.get("metric_id", ""),
                    "name": m.get("name", ""),
                    "description": m.get("description", ""),
                    "kpis": m.get("kpis", []),
                    "category": m.get("category", ""),
                    "source_schemas": m.get("source_schemas", [])
                }
                metrics_list.append(metric_info)
            metrics_section = f"\n\nResolved Metrics/KPIs (available for test validation):\n{json.dumps(metrics_list, indent=2)}\n\nIf metrics are available, you can generate tests that validate/register these metrics. For example, if a metric measures 'critical_vuln_count', you can create a test that queries the database and validates the metric calculation is correct."
        
        calculation_plan_section = ""
        if calculation_plan:
            # Include field and metric instructions that can be used for test queries
            field_instructions = calculation_plan.get("field_instructions", [])
            metric_instructions = calculation_plan.get("metric_instructions", [])
            if field_instructions or metric_instructions:
                calc_info = {
                    "field_instructions_count": len(field_instructions),
                    "metric_instructions_count": len(metric_instructions),
                    "sample_field_instructions": field_instructions[:3] if field_instructions else [],
                    "sample_metric_instructions": metric_instructions[:3] if metric_instructions else []
                }
                calculation_plan_section = f"\n\nCalculation Plan (field and metric instructions for test queries):\n{json.dumps(calc_info, indent=2)}\n\nUse these field and metric instructions to write accurate test queries that validate the metrics are calculated correctly."
        
        human_message = """
Controls: {controls}
Test Cases: {test_cases}

MDL Schema Context (for accurate test queries):
{mdl_str}{metrics_section}{calculation_plan_section}{llm_safety_section}

Generate Python test automation scripts. Use available tools to look up control details and CIS benchmarks if needed.
Use MDL schemas to write accurate test queries against actual table/column names.
If metrics/KPIs are available, generate tests that validate those metrics are calculated correctly and can register metric values.
"""
        
        # Use tool-calling agent if tools are available
        if use_tool_calling and tools:
            try:
                system_prompt = prompt_text
                if feedback_context:
                    system_prompt += "\n\n" + feedback_context
                system_prompt += f"\n\nYou have access to {len(tools)} compliance tools. Use them to look up control details and benchmarks."
                
                # Escape curly braces in system prompt to prevent LangChain from parsing JSON examples as template variables
                # We only want {input} and agent_scratchpad in the template, not in the system prompt
                system_prompt = system_prompt.replace("{", "{{").replace("}", "}}")
                
                # Format the human message with actual values first
                formatted_human_message = human_message.format(
                    controls=controls_str,
                    test_cases=test_cases_str,
                    mdl_str=mdl_str,
                    metrics_section=metrics_section,
                    calculation_plan_section=calculation_plan_section,
                    llm_safety_section=llm_safety_section
                )
                
                # Use a prompt template with agent_scratchpad for tool-calling agent
                prompt = ChatPromptTemplate.from_messages([
                    ("system", system_prompt),
                    ("human", "{input}"),  # Single variable for the formatted input
                    MessagesPlaceholder(variable_name="agent_scratchpad")  # Required for tool-calling agent
                ])
                
                agent_executor = create_tool_calling_agent(
                    llm=llm,
                    tools=tools,
                    prompt=prompt,
                    use_react_agent=False,  # Use direct tool-calling agent to avoid stop sequence issues
                    executor_kwargs={"max_iterations": 5, "verbose": False}
                )
                
                if agent_executor:
                    response = agent_executor.invoke({
                        "input": formatted_human_message
                    })
                    response_content = response.get("output", str(response)) if isinstance(response, dict) else str(response)
                    
                    # Store the raw LLM response for review
                    state["llm_response"] = response_content
                    state["llm_prompt"] = {
                        "system_prompt": system_prompt,
                        "human_message": formatted_human_message
                    }
                    
                    # Log tool-calling agent invocation step
                    log_execution_step(
                        state=state,
                        step_name="llm_invocation_with_tools",
                        agent_name="test_generator",
                        inputs={
                            "system_prompt_length": len(system_prompt),
                            "human_message_length": len(formatted_human_message),
                            "tools_available": len(tools),
                            "tool_names": [getattr(t, 'name', str(t)) for t in tools] if tools else []
                        },
                        outputs={
                            "response_length": len(response_content),
                            "response_preview": response_content[:500] if len(response_content) > 500 else response_content,
                            "tool_calls_made": response.get("intermediate_steps", []) if isinstance(response, dict) else []
                        },
                        status="completed"
                    )
                else:
                    raise ValueError("Agent executor creation failed")
            except Exception as e:
                logger.warning(f"Tool-calling agent failed for test_generator, falling back to simple chain: {e}")
                use_tool_calling = False
        
        # Fallback to simple LLM chain
        if not use_tool_calling:
            system_prompt = prompt_text
            if feedback_context:
                system_prompt += "\n\n" + feedback_context
            
            # Escape curly braces in system prompt to prevent LangChain from parsing JSON examples as template variables
            # We only want {input} in the human message, not in the system prompt
            system_prompt = system_prompt.replace("{", "{{").replace("}", "}}")
            
            # Format the human message with actual values first
            formatted_human_message = human_message.format(
                controls=controls_str,
                test_cases=test_cases_str,
                mdl_str=mdl_str,
                llm_safety_section=llm_safety_section
            )
            
            # Use a simple prompt template with formatted input
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "{input}")  # Single variable for the formatted input
            ])
            
            chain = prompt | llm
            response = chain.invoke({
                "input": formatted_human_message
            })
            response_content = response.content if hasattr(response, 'content') else str(response)
            
            # Store the raw LLM response for review
            state["llm_response"] = response_content
            state["llm_prompt"] = {
                "system_prompt": system_prompt,
                "human_message": formatted_human_message
            }
            
            # Log LLM invocation step
            log_execution_step(
                state=state,
                step_name="llm_invocation",
                agent_name="test_generator",
                inputs={
                    "system_prompt_length": len(system_prompt),
                    "human_message_length": len(formatted_human_message),
                    "tools_available": len(tools) if tools else 0
                },
                outputs={
                    "response_length": len(response_content),
                    "response_preview": response_content[:500] if len(response_content) > 500 else response_content
                },
                status="completed"
            )
        
        # Parse response - try JSON first, then YAML, then extract from code blocks
        result = {"test_scripts": []}
        
        # Try 1: Parse as JSON
        try:
            result = json.loads(response_content)
            if "test_scripts" in result:
                logger.info("Successfully parsed JSON response")
        except json.JSONDecodeError:
            # Try 2: Extract JSON from markdown code block
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_content, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(1))
                    logger.info("Successfully extracted and parsed JSON from code block")
                except json.JSONDecodeError:
                    pass
            
            # Try 3: Parse as YAML (since prompt shows YAML format)
            if "test_scripts" not in result or len(result.get("test_scripts", [])) == 0:
                try:
                    import yaml
                    # Try parsing entire response as YAML
                    result = yaml.safe_load(response_content)
                    if result and "test_scripts" in result:
                        logger.info("Successfully parsed YAML response")
                except (ImportError, yaml.YAMLError):
                    # Try 4: Extract YAML from markdown code block
                    yaml_match = re.search(r'```yaml\s*(.*?)\s*```', response_content, re.DOTALL)
                    if yaml_match:
                        try:
                            import yaml
                            result = yaml.safe_load(yaml_match.group(1))
                            if result and "test_scripts" in result:
                                logger.info("Successfully extracted and parsed YAML from code block")
                        except (ImportError, yaml.YAMLError):
                            pass
            
            # Try 5: If still no test_scripts, try to extract YAML without code block markers
            if "test_scripts" not in result or len(result.get("test_scripts", [])) == 0:
                # Look for YAML-like structure starting with "test_scripts:"
                yaml_start = response_content.find("test_scripts:")
                if yaml_start >= 0:
                    try:
                        import yaml
                        yaml_content = response_content[yaml_start:]
                        # Try to find the end of the YAML block (look for double newline or end of string)
                        # For multi-line python_code, we need to be smarter
                        lines = yaml_content.split('\n')
                        yaml_lines = []
                        in_python_code = False
                        python_code_indent = 0
                        
                        for i, line in enumerate(lines):
                            if i == 0 or (i == 1 and line.strip() == '-'):
                                yaml_lines.append(line)
                                continue
                            
                            # Check if we're entering python_code field
                            if 'python_code:' in line or 'python_code: |' in line:
                                yaml_lines.append(line)
                                in_python_code = True
                                python_code_indent = len(line) - len(line.lstrip())
                                continue
                            
                            # If in python_code, continue until we hit a line with same or less indent that's not empty
                            if in_python_code:
                                if line.strip() == '':
                                    yaml_lines.append(line)
                                    continue
                                current_indent = len(line) - len(line.lstrip())
                                if current_indent > python_code_indent:
                                    yaml_lines.append(line)
                                    continue
                                else:
                                    # End of python_code block
                                    in_python_code = False
                            
                            # Check if this looks like the start of a new top-level key or end of YAML
                            stripped = line.strip()
                            if stripped == '' or (stripped and not stripped.startswith('-') and ':' in stripped and len(stripped.split(':')) == 2):
                                # Might be end of YAML block
                                if i > 10:  # Only break if we've processed some content
                                    break
                            
                            yaml_lines.append(line)
                        
                        yaml_content = '\n'.join(yaml_lines)
                        result = yaml.safe_load(yaml_content)
                        if result and "test_scripts" in result:
                            logger.info("Successfully parsed YAML from response body")
                    except (ImportError, yaml.YAMLError) as e:
                        logger.warning(f"YAML parsing failed: {e}")
                        # Last resort: try to manually extract test script info
                        logger.info("Attempting manual extraction from YAML-like response...")
                        # Extract basic info using regex as fallback
                        control_code_match = re.search(r'control_code:\s*([^\n]+)', response_content)
                        test_case_match = re.search(r'test_case_id:\s*([^\n]+)', response_content)
                        function_match = re.search(r'test_function_name:\s*([^\n]+)', response_content)
                        python_code_match = re.search(r'python_code:\s*\|\s*\n(.*?)(?=\n\s*\w+:|$)', response_content, re.DOTALL)
                        
                        if control_code_match and test_case_match and function_match and python_code_match:
                            result = {
                                "test_scripts": [{
                                    "control_code": control_code_match.group(1).strip(),
                                    "test_case_id": test_case_match.group(1).strip(),
                                    "test_function_name": function_match.group(1).strip(),
                                    "python_code": python_code_match.group(1).strip()
                                }]
                            }
                            logger.info("Successfully extracted test script using regex fallback")
        
        # Ensure result has test_scripts key
        if "test_scripts" not in result:
            result = {"test_scripts": []}
        
        if "test_scripts" in result:
            state["test_scripts"] = result["test_scripts"]
        
        # Log parsing step
        log_execution_step(
            state=state,
            step_name="response_parsing",
            agent_name="test_generator",
            inputs={
                "response_length": len(response_content),
                "parsing_method": "json" if "test_scripts" in result and len(result.get("test_scripts", [])) > 0 else "yaml_or_fallback"
            },
            outputs={
                "test_scripts_count": len(state.get("test_scripts", [])),
                "parsed_successfully": len(state.get("test_scripts", [])) > 0
            },
            status="completed" if len(state.get("test_scripts", [])) > 0 else "failed"
        )
        
        state["messages"].append(AIMessage(
            content=f"Generated {len(state.get('test_scripts', []))} test scripts (iteration {iteration})"
        ))
        
    except Exception as e:
        logger.error(f"Test generator failed: {e}", exc_info=True)
        state["error"] = f"Test generation failed: {str(e)}"
    
    return state


# ============================================================================
# Validation Nodes
# ============================================================================

def siem_rule_validator_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Validates generated SIEM rules for syntax, logic, performance, and completeness.
    """
    siem_rules = state.get("siem_rules", [])
    validation_results = []
    
    for rule in siem_rules:
        rule_id = rule.get("id", str(uuid.uuid4()))
        spl_code = rule.get("spl_code", "")
        
        issues = []
        
        # Syntax validation
        syntax_issues = _validate_splunk_syntax(spl_code)
        issues.extend(syntax_issues)
        
        # Logic validation
        logic_issues = _validate_siem_logic(spl_code)
        issues.extend(logic_issues)
        
        # Performance validation
        perf_issues = _validate_siem_performance(spl_code)
        issues.extend(perf_issues)
        
        # Completeness validation
        completeness_issues = _validate_siem_completeness(rule)
        issues.extend(completeness_issues)
        
        # Calculate confidence score
        error_count = sum(1 for i in issues if i["severity"] == "error")
        warning_count = sum(1 for i in issues if i["severity"] == "warning")
        
        confidence_score = max(0.0, 1.0 - (error_count * 0.3) - (warning_count * 0.1))
        
        validation_result = ValidationResult(
            artifact_type="siem_rule",
            artifact_id=rule_id,
            passed=(error_count == 0),
            confidence_score=confidence_score,
            issues=issues,
            suggestions=_generate_siem_suggestions(issues),
            validation_timestamp=datetime.utcnow()
        )
        
        validation_results.append(validation_result)
    
    if "validation_results" not in state:
        state["validation_results"] = []
    state["validation_results"].extend(validation_results)
    
    # Aggregate pass/fail
    all_passed = all(v.passed for v in validation_results)
    state["validation_passed"] = state.get("validation_passed", True) and all_passed
    
    if not all_passed:
        failed_count = sum(1 for v in validation_results if not v.passed)
        state["messages"].append(AIMessage(
            content=f"SIEM Rule Validation: {failed_count}/{len(validation_results)} rules failed validation"
        ))
    
    return state


def _validate_splunk_syntax(spl: str) -> List[Dict]:
    """Check for common Splunk SPL syntax errors."""
    issues = []
    
    if not spl:
        return [{"severity": "error", "message": "Empty SPL code", "location": "query", "suggestion": "Provide valid SPL code"}]
    
    # Missing index
    if "index=" not in spl.lower():
        issues.append({
            "severity": "warning",
            "message": "No index specified - query will be slow",
            "location": "query header",
            "suggestion": "Add 'index=<your_index>' at the start"
        })
    
    # Unclosed pipes
    pipe_count = spl.count("|")
    if pipe_count > 0:
        if spl.strip().endswith("|"):
            issues.append({
                "severity": "error",
                "message": "Query ends with pipe (|) - incomplete",
                "location": "end of query",
                "suggestion": "Complete the pipe command or remove trailing |"
            })
    
    # Unbalanced quotes
    single_quotes = spl.count("'") - spl.count("\\'")
    double_quotes = spl.count('"') - spl.count('\\"')
    
    if single_quotes % 2 != 0:
        issues.append({
            "severity": "error",
            "message": "Unbalanced single quotes",
            "location": "throughout query",
            "suggestion": "Check all quoted strings"
        })
    
    if double_quotes % 2 != 0:
        issues.append({
            "severity": "error",
            "message": "Unbalanced double quotes",
            "location": "throughout query",
            "suggestion": "Check all quoted strings"
        })
    
    # Check for eval without assignment
    if "eval " in spl.lower():
        eval_matches = re.findall(r'\|\s*eval\s+([^|]+)', spl, re.IGNORECASE)
        for eval_expr in eval_matches:
            if "=" not in eval_expr:
                issues.append({
                    "severity": "error",
                    "message": f"eval without assignment: {eval_expr.strip()}",
                    "location": "eval command",
                    "suggestion": "eval must assign to a field: eval my_field=<expression>"
                })
    
    return issues


def _validate_siem_logic(spl: str) -> List[Dict]:
    """Check for logical errors in SIEM rules."""
    issues = []
    
    # Impossible conditions (e.g., field=X AND field=Y)
    and_conditions = re.findall(r'(\w+)=(\S+)\s+AND\s+\1=(\S+)', spl, re.IGNORECASE)
    for field, val1, val2 in and_conditions:
        if val1 != val2:
            issues.append({
                "severity": "error",
                "message": f"Impossible condition: {field}={val1} AND {field}={val2}",
                "location": "filter logic",
                "suggestion": "Change to OR or remove one condition"
            })
    
    # Stats without by clause (might be intentional, but flag it)
    if "| stats " in spl.lower() and " by " not in spl.lower():
        issues.append({
            "severity": "warning",
            "message": "stats without 'by' clause - will aggregate all events into single row",
            "location": "stats command",
            "suggestion": "Add '| stats ... by <field>' if you want per-field aggregation"
        })
    
    return issues


def _validate_siem_performance(spl: str) -> List[Dict]:
    """Check for performance anti-patterns."""
    issues = []
    
    # Leading wildcards
    if re.search(r'\*\w+', spl):
        issues.append({
            "severity": "warning",
            "message": "Leading wildcard (*) detected - causes slow search",
            "location": "wildcard usage",
            "suggestion": "Avoid leading wildcards; use trailing wildcards instead"
        })
    
    # Transaction command (notoriously slow)
    if "| transaction " in spl.lower():
        issues.append({
            "severity": "warning",
            "message": "transaction command is slow - consider stats instead",
            "location": "transaction command",
            "suggestion": "Replace with 'stats list()' or 'stats values()' grouped by common field"
        })
    
    # No time window
    if "earliest=" not in spl.lower() and "latest=" not in spl.lower():
        issues.append({
            "severity": "warning",
            "message": "No time window specified - will search all time",
            "location": "query header",
            "suggestion": "Add earliest=-24h or similar to limit search scope"
        })
    
    return issues


def _validate_siem_completeness(rule: Dict) -> List[Dict]:
    """Check that rule has all required fields."""
    issues = []
    
    required_fields = ["name", "description", "severity", "spl_code"]
    for field in required_fields:
        if not rule.get(field):
            issues.append({
                "severity": "error",
                "message": f"Missing required field: {field}",
                "location": "rule metadata",
                "suggestion": f"Add {field} to rule definition"
            })
    
    # Alert configuration
    if not rule.get("alert_config"):
        issues.append({
            "severity": "warning",
            "message": "No alert configuration defined",
            "location": "rule metadata",
            "suggestion": "Add alert_config with notification channels and SLA"
        })
    
    # Compliance mapping
    if not rule.get("compliance_mappings"):
        issues.append({
            "severity": "warning",
            "message": "No compliance mappings - rule not linked to requirements",
            "location": "rule metadata",
            "suggestion": "Add compliance_mappings array with framework requirement IDs"
        })
    
    return issues


def _generate_siem_suggestions(issues: List[Dict]) -> List[str]:
    """Convert issues into actionable suggestions."""
    suggestions = []
    
    for issue in issues:
        if issue["severity"] == "error":
            suggestions.append(f"FIX: {issue['message']} → {issue['suggestion']}")
        else:
            suggestions.append(f"IMPROVE: {issue['message']} → {issue['suggestion']}")
    
    return suggestions


def playbook_validator_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Validates incident response playbooks for completeness, actionability, and traceability.
    """
    playbooks = state.get("playbooks", [])
    validation_results = []
    
    for playbook in playbooks:
        pb_id = playbook.get("id", str(uuid.uuid4()))
        markdown_content = playbook.get("markdown_content", "")
        
        issues = []
        
        # Completeness validation
        required_sections = ["DETECT", "TRIAGE", "CONTAIN", "INVESTIGATE", "REMEDIATE", "RECOVER"]
        missing_sections = [s for s in required_sections if s.upper() not in markdown_content.upper()]
        
        for section in missing_sections:
            issues.append({
                "severity": "error",
                "message": f"Missing required section: {section}",
                "location": "playbook structure",
                "suggestion": f"Add {section} section with specific steps"
            })
        
        # Actionability validation
        actionability_score = _validate_playbook_actionability(markdown_content)
        if actionability_score < 0.7:
            issues.append({
                "severity": "warning",
                "message": f"Playbook lacks specific commands (actionability score: {actionability_score:.2f})",
                "location": "throughout playbook",
                "suggestion": "Add concrete bash/SQL/API commands instead of vague instructions like 'check the logs'"
            })
        
        # Traceability validation
        if not _has_control_references(markdown_content):
            issues.append({
                "severity": "warning",
                "message": "Playbook does not reference any controls or test cases",
                "location": "playbook metadata",
                "suggestion": "Add references to controls being restored and tests to run"
            })
        
        # Timeline validation
        timeline_issues = _validate_playbook_timelines(markdown_content)
        issues.extend(timeline_issues)
        
        error_count = sum(1 for i in issues if i["severity"] == "error")
        warning_count = sum(1 for i in issues if i["severity"] == "warning")
        
        confidence_score = max(0.0, 1.0 - (error_count * 0.25) - (warning_count * 0.1))
        
        validation_result = ValidationResult(
            artifact_type="playbook",
            artifact_id=pb_id,
            passed=(error_count == 0),
            confidence_score=confidence_score,
            issues=issues,
            suggestions=[i["suggestion"] for i in issues],
            validation_timestamp=datetime.utcnow()
        )
        
        validation_results.append(validation_result)
    
    if "validation_results" not in state:
        state["validation_results"] = []
    state["validation_results"].extend(validation_results)
    
    all_passed = all(v.passed for v in validation_results)
    state["validation_passed"] = state.get("validation_passed", True) and all_passed
    
    return state


def _validate_playbook_actionability(content: str) -> float:
    """Score playbook on how actionable it is (0.0 - 1.0)."""
    # Count specific actionable elements
    bash_commands = len(re.findall(r'```bash\n(.+?)\n```', content, re.DOTALL))
    sql_queries = len(re.findall(r'```sql\n(.+?)\n```', content, re.DOTALL))
    api_calls = len(re.findall(r'curl|http|GET|POST|PUT|DELETE', content))
    specific_tools = len(re.findall(r'splunk|aws|kubectl|docker|grep|awk|sed', content, re.IGNORECASE))
    
    # Count vague instructions
    vague_phrases = len(re.findall(
        r'check the|review the|verify|ensure|make sure|consider|investigate|analyze',
        content,
        re.IGNORECASE
    ))
    
    # Score
    actionable_items = bash_commands + sql_queries + api_calls + specific_tools
    total_instructions = actionable_items + vague_phrases
    
    if total_instructions == 0:
        return 0.0
    
    return actionable_items / total_instructions


def _has_control_references(content: str) -> bool:
    """Check if playbook references controls or test cases."""
    return bool(re.search(r'Control:|TEST-|CIS|NIST|HIPAA|SOC2', content))


def _validate_playbook_timelines(content: str) -> List[Dict]:
    """Check if SLAs are realistic."""
    issues = []
    
    # Extract SLA mentions
    sla_matches = re.findall(r'SLA:\s*(\d+)\s*(min|minute|hour|hr)', content, re.IGNORECASE)
    
    for value, unit in sla_matches:
        value = int(value)
        unit_normalized = "minutes" if "min" in unit.lower() else "hours"
        
        # Unrealistic SLAs
        if unit_normalized == "minutes" and value < 5:
            issues.append({
                "severity": "warning",
                "message": f"SLA of {value} minutes may be unrealistic for this phase",
                "location": "timeline",
                "suggestion": "Consider increasing to at least 5-15 minutes for triage"
            })
    
    return issues


def test_script_validator_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Validates Python test scripts for syntax, API compatibility, and error handling.
    """
    test_scripts = state.get("test_scripts", [])
    validation_results = []
    
    for script in test_scripts:
        script_id = script.get("id", str(uuid.uuid4()))
        python_code = script.get("python_code", "")
        
        issues = []
        
        # Syntax validation
        try:
            ast.parse(python_code)
        except SyntaxError as e:
            issues.append({
                "severity": "error",
                "message": f"Python syntax error: {e.msg}",
                "location": f"line {e.lineno}",
                "suggestion": "Fix syntax error before proceeding"
            })
        
        # Check for error handling
        if "try:" not in python_code or "except" not in python_code:
            issues.append({
                "severity": "warning",
                "message": "No try/except error handling",
                "location": "function body",
                "suggestion": "Wrap API calls in try/except to handle failures gracefully"
            })
        
        # Check return type
        if not re.search(r'return\s*\([^)]+,\s*[^)]+,\s*[^)]+\)', python_code):
            issues.append({
                "severity": "error",
                "message": "Function does not return expected Tuple[bool, str, Dict]",
                "location": "return statement",
                "suggestion": "Return (passed: bool, message: str, evidence: dict)"
            })
        
        # Check for hardcoded credentials
        if re.search(r'(password|secret|key|token)\s*=\s*["\'][^"\']+["\']', python_code, re.IGNORECASE):
            issues.append({
                "severity": "error",
                "message": "Hardcoded credentials detected",
                "location": "variable assignment",
                "suggestion": "Use config dict or environment variables instead"
            })
        
        error_count = sum(1 for i in issues if i["severity"] == "error")
        warning_count = sum(1 for i in issues if i["severity"] == "warning")
        
        confidence_score = max(0.0, 1.0 - (error_count * 0.3) - (warning_count * 0.1))
        
        validation_result = ValidationResult(
            artifact_type="test_script",
            artifact_id=script_id,
            passed=(error_count == 0),
            confidence_score=confidence_score,
            issues=issues,
            suggestions=[i["suggestion"] for i in issues],
            validation_timestamp=datetime.utcnow()
        )
        
        validation_results.append(validation_result)
    
    if "validation_results" not in state:
        state["validation_results"] = []
    state["validation_results"].extend(validation_results)
    
    all_passed = all(v.passed for v in validation_results)
    state["validation_passed"] = state.get("validation_passed", True) and all_passed
    
    return state


def cross_artifact_validator_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Validates consistency across all artifact types.
    """
    siem_rules = state.get("siem_rules", [])
    playbooks = state.get("playbooks", [])
    test_scripts = state.get("test_scripts", [])
    scenarios = state.get("scenarios", [])
    controls = state.get("controls", [])
    
    issues = []
    
    # Extract scenario references from SIEM rules
    siem_scenario_refs = set()
    for rule in siem_rules:
        rule_str = json.dumps(rule)
        matches = re.findall(r'(HIPAA-SCENARIO-\d+|CIS-RISK-\d+|[A-Z]+-SCENARIO-\d+)', rule_str)
        siem_scenario_refs.update(matches)
    
    # Extract scenario references from playbooks
    playbook_scenario_refs = set()
    for pb in playbooks:
        content = pb.get("markdown_content", "")
        matches = re.findall(r'(HIPAA-SCENARIO-\d+|CIS-RISK-\d+|[A-Z]+-SCENARIO-\d+)', content)
        playbook_scenario_refs.update(matches)
    
    # Check: Every scenario should have at least one SIEM rule
    scenario_codes = {s.get("scenario_code", s.get("id", "")) for s in scenarios}
    missing_siem = scenario_codes - siem_scenario_refs
    if missing_siem:
        issues.append({
            "severity": "warning",
            "message": f"Scenarios without SIEM rules: {missing_siem}",
            "location": "cross-artifact consistency",
            "suggestion": "Generate SIEM rules for all scenarios"
        })
    
    # Check: Every scenario should have a playbook
    missing_playbooks = scenario_codes - playbook_scenario_refs
    if missing_playbooks:
        issues.append({
            "severity": "warning",
            "message": f"Scenarios without playbooks: {missing_playbooks}",
            "location": "cross-artifact consistency",
            "suggestion": "Generate playbooks for all scenarios"
        })
    
    # Check: Every control should have a test case
    control_codes = {c.get("control_code", c.get("id", "")) for c in controls}
    tested_controls = set()
    for script in test_scripts:
        func_name = script.get("test_function_name", "")
        matches = re.findall(r'test_([A-Z]+-\d+)', func_name)
        tested_controls.update(matches)
    
    untested_controls = control_codes - tested_controls
    if untested_controls:
        issues.append({
            "severity": "warning",
            "message": f"Controls without test cases: {untested_controls}",
            "location": "test coverage",
            "suggestion": "Generate test scripts for all controls"
        })
    
    # Calculate overall consistency score
    total_checks = 3
    passed_checks = total_checks - len(issues)
    confidence_score = passed_checks / total_checks if total_checks > 0 else 1.0
    
    validation_result = ValidationResult(
        artifact_type="cross_artifact",
        artifact_id="consistency_check",
        passed=(len(issues) == 0),
        confidence_score=confidence_score,
        issues=issues,
        suggestions=[i["suggestion"] for i in issues],
        validation_timestamp=datetime.utcnow()
    )
    
    if "validation_results" not in state:
        state["validation_results"] = []
    state["validation_results"].append(validation_result)
    state["validation_passed"] = state.get("validation_passed", True) and validation_result.passed
    
    return state


# ============================================================================
# Chain Validation Node
# ============================================================================

def chain_validation_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Validates the semantic chain: SIEM rule → control → risk → requirement.
    
    This node ensures traceability from detection signals back to the original
    framework requirements, validating that:
    1. SIEM rules detect signals relevant to the controls
    2. Controls address the identified risks
    3. Risks map to framework requirements
    4. Dashboard metrics measure control effectiveness
    """
    siem_rules = state.get("siem_rules", [])
    controls = state.get("controls", [])
    risks = state.get("risks", [])
    requirements = state.get("requirements", [])
    dashboards = state.get("dashboards", [])
    scenarios = state.get("scenarios", [])
    
    issues = []
    
    # Extract control codes/IDs from state
    control_codes = set()
    control_ids = set()
    for ctrl in controls:
        if isinstance(ctrl, dict):
            if ctrl.get("code"):
                control_codes.add(ctrl["code"])
            if ctrl.get("id"):
                control_ids.add(ctrl["id"])
        elif hasattr(ctrl, "code"):
            control_codes.add(ctrl.code)
        elif hasattr(ctrl, "id"):
            control_ids.add(ctrl.id)
    
    # Extract risk codes/IDs
    risk_codes = set()
    risk_ids = set()
    for risk in risks:
        if isinstance(risk, dict):
            if risk.get("code"):
                risk_codes.add(risk["code"])
            if risk.get("id"):
                risk_ids.add(risk["id"])
        elif hasattr(risk, "code"):
            risk_codes.add(risk.code)
        elif hasattr(risk, "id"):
            risk_ids.add(risk.id)
    
    # Extract requirement codes/IDs
    req_codes = set()
    req_ids = set()
    for req in requirements:
        if isinstance(req, dict):
            if req.get("code"):
                req_codes.add(req["code"])
            if req.get("id"):
                req_ids.add(req["id"])
        elif hasattr(req, "code"):
            req_codes.add(req.code)
        elif hasattr(req, "id"):
            req_ids.add(req.id)
    
    # Validation 1: SIEM rules should reference controls
    siem_control_refs = set()
    for rule in siem_rules:
        rule_str = json.dumps(rule)
        # Look for control references in rule content
        for code in control_codes:
            if code in rule_str:
                siem_control_refs.add(code)
        # Also check for control IDs
        for ctrl_id in control_ids:
            if str(ctrl_id) in rule_str:
                siem_control_refs.add(str(ctrl_id))
    
    if control_codes and not siem_control_refs:
        issues.append({
            "severity": "warning",
            "message": "SIEM rules do not reference the controls they are meant to support",
            "location": "chain_traceability",
            "suggestion": "Ensure SIEM rules explicitly reference control codes/IDs in their descriptions or metadata"
        })
    elif control_codes and len(siem_control_refs) < len(control_codes) * 0.5:
        issues.append({
            "severity": "warning",
            "message": f"Only {len(siem_control_refs)}/{len(control_codes)} controls are referenced in SIEM rules",
            "location": "chain_traceability",
            "suggestion": "Ensure all controls have corresponding SIEM detection rules"
        })
    
    # Validation 2: Controls should address risks
    # Check if controls reference risks or if risks reference controls
    control_risk_refs = set()
    for ctrl in controls:
        ctrl_str = json.dumps(ctrl) if isinstance(ctrl, dict) else str(ctrl)
        for risk_code in risk_codes:
            if risk_code in ctrl_str:
                control_risk_refs.add(risk_code)
    
    if risk_codes and not control_risk_refs:
        issues.append({
            "severity": "warning",
            "message": "Controls do not explicitly reference the risks they mitigate",
            "location": "chain_traceability",
            "suggestion": "Ensure controls are linked to their mitigating risks in the knowledge base"
        })
    
    # Validation 3: Risks should map to requirements
    risk_req_refs = set()
    for risk in risks:
        risk_str = json.dumps(risk) if isinstance(risk, dict) else str(risk)
        for req_code in req_codes:
            if req_code in risk_str:
                risk_req_refs.add(req_code)
    
    if req_codes and not risk_req_refs:
        issues.append({
            "severity": "warning",
            "message": "Risks do not explicitly reference the requirements they relate to",
            "location": "chain_traceability",
            "suggestion": "Ensure risks are linked to their source requirements in the knowledge base"
        })
    
    # Validation 4: Scenarios should drive SIEM rules
    scenario_codes = set()
    for scenario in scenarios:
        if isinstance(scenario, dict):
            code = scenario.get("scenario_code") or scenario.get("code") or scenario.get("id", "")
            if code:
                scenario_codes.add(str(code))
        elif hasattr(scenario, "code"):
            scenario_codes.add(scenario.code)
        elif hasattr(scenario, "id"):
            scenario_codes.add(str(scenario.id))
    
    siem_scenario_refs = set()
    for rule in siem_rules:
        rule_str = json.dumps(rule)
        for scenario_code in scenario_codes:
            if scenario_code in rule_str:
                siem_scenario_refs.add(scenario_code)
    
    if scenario_codes and not siem_scenario_refs:
        issues.append({
            "severity": "warning",
            "message": "SIEM rules do not reference the attack scenarios they are meant to detect",
            "location": "chain_traceability",
            "suggestion": "Ensure SIEM rules explicitly reference scenario codes to show they detect the attack patterns"
        })
    
    # Validation 5: Dashboard metrics should measure control effectiveness
    if dashboards and controls:
        dashboard_str = json.dumps(dashboards)
        dashboard_control_refs = set()
        for code in control_codes:
            if code in dashboard_str:
                dashboard_control_refs.add(code)
        
        if not dashboard_control_refs:
            issues.append({
                "severity": "warning",
                "message": "Dashboard does not reference the controls it is meant to measure",
                "location": "chain_traceability",
                "suggestion": "Ensure dashboard metrics explicitly reference control codes/IDs to show they measure control effectiveness"
            })
        elif len(dashboard_control_refs) < len(control_codes) * 0.5:
            issues.append({
                "severity": "warning",
                "message": f"Dashboard only references {len(dashboard_control_refs)}/{len(control_codes)} controls",
                "location": "chain_traceability",
                "suggestion": "Ensure dashboard metrics cover all validated controls"
            })
    
    # Calculate overall chain validation score
    total_checks = 5
    passed_checks = total_checks - len(issues)
    confidence_score = passed_checks / total_checks if total_checks > 0 else 1.0
    
    validation_result = ValidationResult(
        artifact_type="chain_validation",
        artifact_id="semantic_chain",
        passed=(len(issues) == 0),
        confidence_score=confidence_score,
        issues=issues,
        suggestions=[i["suggestion"] for i in issues],
        validation_timestamp=datetime.utcnow()
    )
    
    if "validation_results" not in state:
        state["validation_results"] = []
    state["validation_results"].append(validation_result)
    state["validation_passed"] = state.get("validation_passed", True) and validation_result.passed
    
    logger.info(f"Chain validation: {len(issues)} issues found, confidence: {confidence_score:.2f}")
    
    return state


# ============================================================================
# Feedback Analyzer Node
# ============================================================================

def feedback_analyzer_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Analyzes validation results and determines what needs to be regenerated.
    """
    validation_results = state.get("validation_results", [])
    
    # Group failures by artifact type
    failed_by_type = {}
    for result in validation_results:
        if not result.passed:
            artifact_type = result.artifact_type
            if artifact_type not in failed_by_type:
                failed_by_type[artifact_type] = []
            failed_by_type[artifact_type].append(result)
    
    # Prepare refinement instructions
    refinement_plan = []
    
    for artifact_type, failures in failed_by_type.items():
        # Aggregate all issues for this artifact type
        all_issues = []
        for failure in failures:
            all_issues.extend(failure.issues)
        
        # Group by severity
        errors = [i for i in all_issues if i["severity"] == "error"]
        warnings = [i for i in all_issues if i["severity"] == "warning"]
        
        refinement_instruction = {
            "artifact_type": artifact_type,
            "failed_count": len(failures),
            "error_count": len(errors),
            "warning_count": len(warnings),
            "specific_fixes": [i["suggestion"] for i in errors],  # Prioritize errors
            "improvements": [i["suggestion"] for i in warnings],
            "failed_artifact_ids": [f.artifact_id for f in failures]
        }
        
        refinement_plan.append(refinement_instruction)
    
    # Store refinement plan
    if "refinement_history" not in state:
        state["refinement_history"] = []
    
    state["refinement_history"].append({
        "iteration": state.get("iteration_count", 0),
        "timestamp": datetime.utcnow().isoformat(),
        "refinement_plan": refinement_plan
    })
    
    # Increment iteration counter
    state["iteration_count"] = state.get("iteration_count", 0) + 1
    
    # Check max iterations
    max_iterations = state.get("max_iterations", 3)
    if state["iteration_count"] >= max_iterations:
        state["messages"].append(AIMessage(
            content=f"Max iterations ({max_iterations}) reached. Some artifacts still have issues."
        ))
        state["next_agent"] = "artifact_assembler"
        return state
    
    # Route to first failed artifact generator
    if failed_by_type:
        # Priority order: SIEM rules > Playbooks > Tests > Pipelines
        priority = ["siem_rule", "playbook", "test_script", "data_pipeline"]
        for artifact_type in priority:
            if artifact_type in failed_by_type:
                agent_map = {
                    "siem_rule": "detection_engineer",
                    "playbook": "playbook_writer",
                    "test_script": "test_generator",
                    "data_pipeline": "pipeline_builder"
                }
                state["next_agent"] = agent_map.get(artifact_type, "artifact_assembler")
                state["messages"].append(AIMessage(
                    content=f"Regenerating {artifact_type} artifacts (iteration {state['iteration_count']})"
                ))
                return state
    
    # All validations passed
    state["next_agent"] = "artifact_assembler"
    return state


# ============================================================================
# Artifact Assembler Node
# ============================================================================

def artifact_assembler_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Packages all generated artifacts into a comprehensive deliverable.
    Can use web search for best practices and deployment guidance.
    """
    try:
        prompt_text = load_prompt("08_artifact_assembler")
        
        # Get tools conditionally
        tools = get_tools_for_agent("artifact_assembler", state=state, conditional=True)
        use_tool_calling = should_use_tool_calling_agent("artifact_assembler", state=state)
        
        llm = get_llm(temperature=0)
        
        siem_rules_str = json.dumps(state.get("siem_rules", []), indent=2)
        playbooks_str = json.dumps(state.get("playbooks", []), indent=2)
        test_scripts_str = json.dumps(state.get("test_scripts", []), indent=2)
        dashboards_str = json.dumps(state.get("dashboards", []), indent=2)
        vulnerability_mappings_str = json.dumps(state.get("vulnerability_mappings", []), indent=2)
        gap_analysis_str = json.dumps(state.get("gap_analysis_results", []), indent=2)
        cross_framework_str = json.dumps(state.get("cross_framework_mappings", []), indent=2)
        validation_results_str = json.dumps([
            {
                "artifact_type": v.artifact_type,
                "artifact_id": v.artifact_id,
                "passed": v.passed,
                "confidence_score": v.confidence_score
            }
            for v in state.get("validation_results", [])
        ], indent=2)
        
        # Format the human message with all variables first
        formatted_human_message = f"""
SIEM Rules: {siem_rules_str}
Playbooks: {playbooks_str}
Test Scripts: {test_scripts_str}
Dashboards: {dashboards_str}
Vulnerability Mappings: {vulnerability_mappings_str}
Gap Analysis Results: {gap_analysis_str}
Cross-Framework Mappings: {cross_framework_str}
Validation Results: {validation_results_str}

Assemble the final artifact package. Use available tools to look up best practices and deployment guidance if needed.
"""
        
        # Use tool-calling agent if tools are available
        if use_tool_calling and tools:
            try:
                system_prompt = prompt_text
                system_prompt += f"\n\nYou have access to {len(tools)} tools. Use them to look up best practices and deployment guidance for SIEM rules, playbooks, and test scripts."
                
                # Escape curly braces in system prompt to prevent LangChain from parsing JSON examples as template variables
                system_prompt = system_prompt.replace("{", "{{").replace("}", "}}")
                
                # Use a prompt template with agent_scratchpad for tool-calling agent
                prompt = ChatPromptTemplate.from_messages([
                    ("system", system_prompt),
                    ("human", "{input}"),  # Single variable for the formatted input
                    MessagesPlaceholder(variable_name="agent_scratchpad")  # Required for tool-calling agent
                ])
                
                agent_executor = create_tool_calling_agent(
                    llm=llm,
                    tools=tools,
                    prompt=prompt,
                    use_react_agent=False,  # Use direct tool-calling agent to avoid stop sequence issues
                    executor_kwargs={"max_iterations": 5, "verbose": False}
                )
                
                if agent_executor:
                    response = agent_executor.invoke({
                        "input": formatted_human_message
                    })
                    response_content = response.get("output", str(response)) if isinstance(response, dict) else str(response)
                    
                    # Store the raw LLM response for review
                    state["llm_response"] = response_content
                    state["llm_prompt"] = {
                        "system_prompt": system_prompt,
                        "human_message": formatted_human_message
                    }
                    
                    # Log tool-calling agent invocation step
                    log_execution_step(
                        state=state,
                        step_name="llm_invocation_with_tools",
                        agent_name="artifact_assembler",
                        inputs={
                            "system_prompt_length": len(system_prompt),
                            "human_message_length": len(formatted_human_message),
                            "tools_available": len(tools),
                            "tool_names": [getattr(t, 'name', str(t)) for t in tools] if tools else [],
                            "artifacts_count": {
                                "siem_rules": len(state.get("siem_rules", [])),
                                "playbooks": len(state.get("playbooks", [])),
                                "test_scripts": len(state.get("test_scripts", [])),
                                "dashboards": len(state.get("dashboards", [])),
                                "vulnerability_mappings": len(state.get("vulnerability_mappings", []))
                            }
                        },
                        outputs={
                            "response_length": len(response_content),
                            "response_preview": response_content[:500] if len(response_content) > 500 else response_content
                        },
                        status="completed"
                    )
                else:
                    raise ValueError("Agent executor creation failed")
            except Exception as e:
                logger.warning(f"Tool-calling agent failed for artifact_assembler, falling back to simple chain: {e}")
                use_tool_calling = False
        
        # Fallback to simple LLM chain
        if not use_tool_calling:
            # Escape curly braces in system prompt to prevent LangChain from parsing JSON examples as template variables
            system_prompt = prompt_text.replace("{", "{{").replace("}", "}}")
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "{input}")  # Single variable for the formatted input
            ])
            chain = prompt | llm
            response = chain.invoke({
                "input": formatted_human_message
            })
            response_content = response.content if hasattr(response, 'content') else str(response)
            
            # Store the raw LLM response for review
            state["llm_response"] = response_content
            state["llm_prompt"] = {
                "system_prompt": system_prompt,
                "human_message": formatted_human_message
            }
            
            # Log LLM invocation step
            log_execution_step(
                state=state,
                step_name="llm_invocation",
                agent_name="artifact_assembler",
                inputs={
                    "system_prompt_length": len(system_prompt),
                    "human_message_length": len(formatted_human_message),
                    "artifacts_count": {
                        "siem_rules": len(state.get("siem_rules", [])),
                        "playbooks": len(state.get("playbooks", [])),
                        "test_scripts": len(state.get("test_scripts", [])),
                        "dashboards": len(state.get("dashboards", [])),
                        "vulnerability_mappings": len(state.get("vulnerability_mappings", []))
                    }
                },
                outputs={
                    "response_length": len(response_content),
                    "response_preview": response_content[:500] if len(response_content) > 500 else response_content
                },
                status="completed"
            )
        
        # Parse JSON response
        try:
            result = json.loads(response_content)
        except json.JSONDecodeError:
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                result = {"package": {"summary": response_content}}
        
        # Calculate quality score
        quality_score = _calculate_quality_score(state)
        state["quality_score"] = quality_score
        
        # Log artifact assembly step
        log_execution_step(
            state=state,
            step_name="artifact_assembly",
            agent_name="artifact_assembler",
            inputs={
                "artifacts_count": {
                    "siem_rules": len(state.get("siem_rules", [])),
                    "playbooks": len(state.get("playbooks", [])),
                    "test_scripts": len(state.get("test_scripts", [])),
                    "dashboards": len(state.get("dashboards", [])),
                    "vulnerability_mappings": len(state.get("vulnerability_mappings", []))
                }
            },
            outputs={
                "quality_score": quality_score,
                "result_keys": list(result.keys()) if isinstance(result, dict) else []
            },
            status="completed"
        )
        
        state["messages"].append(AIMessage(
            content=f"Artifact assembly complete. Quality score: {quality_score:.1f}/100"
        ))
        
    except Exception as e:
        logger.error(f"Artifact assembler failed: {e}", exc_info=True)
        state["error"] = f"Artifact assembly failed: {str(e)}"
    
    return state


def _calculate_quality_score(state: EnhancedCompliancePipelineState) -> float:
    """
    Calculate overall quality score (0-100) for generated artifacts.
    """
    validation_results = state.get("validation_results", [])
    if not validation_results:
        return 0.0
    
    # Pass rate (40% weight)
    passed_count = sum(1 for v in validation_results if v.passed)
    pass_rate = passed_count / len(validation_results) if validation_results else 0.0
    pass_score = pass_rate * 40
    
    # Average confidence (30% weight)
    avg_confidence = sum(v.confidence_score for v in validation_results) / len(validation_results) if validation_results else 0.0
    confidence_score = avg_confidence * 30
    
    # Completeness (20% weight)
    expected_artifacts = {
        "siem_rule": len(state.get("scenarios", [])),  # 1 rule per scenario
        "playbook": len(state.get("scenarios", [])),   # 1 playbook per scenario
        "test_script": len(state.get("controls", [])), # 1 test per control
        "data_pipeline": 1  # 1 monitoring pipeline
    }
    
    actual_artifacts = {
        "siem_rule": len(state.get("siem_rules", [])),
        "playbook": len(state.get("playbooks", [])),
        "test_script": len(state.get("test_scripts", [])),
        "data_pipeline": len(state.get("data_pipelines", []))
    }
    
    completeness_rates = [
        min(actual_artifacts[k] / expected_artifacts[k], 1.0) if expected_artifacts[k] > 0 else 1.0
        for k in expected_artifacts
    ]
    completeness_score = (sum(completeness_rates) / len(completeness_rates)) * 20 if completeness_rates else 0.0
    
    # Iteration efficiency (10% weight)
    iteration_count = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 3)
    efficiency = max(0, 1 - (iteration_count / max_iterations)) if max_iterations > 0 else 1.0
    efficiency_score = efficiency * 10
    
    # Total
    total_score = pass_score + confidence_score + completeness_score + efficiency_score
    
    return total_score


# ============================================================================
# Dashboard Generator Node
# ============================================================================

def dashboard_generator_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Generates compliance dashboards with KPIs, metrics, and visualizations.
    Uses MDL schemas and XSOAR dashboard examples for reference.
    """
    try:
        prompt_text = load_prompt("13_dashboard_agent")
        
        # Get tools conditionally
        tools = get_tools_for_agent("dashboard_generator", state=state, conditional=True)
        use_tool_calling = should_use_tool_calling_agent("dashboard_generator", state=state)
        
        llm = get_llm(temperature=0)
        
        # Retrieve MDL and XSOAR context for dashboard generation
        retrieval_service = RetrievalService()
        query = state.get("user_query", "")
        framework_id = state.get("framework_id")
        
        # Retrieve framework context if not already present
        if not state.get("controls") and framework_id:
            try:
                # Search for controls related to the query
                controls_context = retrieval_service.search_controls(
                    query=query or "compliance controls",
                    limit=10,
                    framework_filter=[framework_id] if framework_id else None
                )
                if controls_context and hasattr(controls_context, 'controls'):
                    state["controls"] = [c.__dict__ for c in controls_context.controls]
            except Exception as e:
                logger.warning(f"Failed to retrieve controls for dashboard: {e}")
        
        if not state.get("requirements") and framework_id:
            try:
                # Search for requirements related to the query
                requirements_context = retrieval_service.search_requirements(
                    query=query or "compliance requirements",
                    limit=10,
                    framework_filter=[framework_id] if framework_id else None
                )
                if requirements_context and hasattr(requirements_context, 'requirements'):
                    state["requirements"] = [r.__dict__ for r in requirements_context.requirements]
            except Exception as e:
                logger.warning(f"Failed to retrieve requirements for dashboard: {e}")
        
        # Get framework context
        controls_str = json.dumps(state.get("controls", []), indent=2)
        requirements_str = json.dumps(state.get("requirements", []), indent=2)
        
        # Retrieve MDL schemas and XSOAR dashboards
        # CRITICAL: Use control IDs as retrieval anchors for metrics
        mdl_context = {}
        xsoar_context = {}
        
        try:
            import asyncio
            from app.retrieval.mdl_service import MDLRetrievalService
            from app.retrieval.xsoar_service import XSOARRetrievalService
            
            mdl_service = MDLRetrievalService()
            xsoar_service = XSOARRetrievalService()
            
            # Run async retrieval
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop = asyncio.new_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
            
            # Build control-scoped query for metrics
            # If controls are in state, use their codes/names to scope metrics retrieval
            controls = state.get("controls", [])
            control_scoped_query = query
            if controls:
                # Extract control codes/names to anchor metrics search
                control_codes = []
                control_names = []
                for ctrl in controls:
                    if isinstance(ctrl, dict):
                        if ctrl.get("code"):
                            control_codes.append(ctrl["code"])
                        if ctrl.get("name"):
                            control_names.append(ctrl["name"])
                    elif hasattr(ctrl, "code"):
                        control_codes.append(ctrl.code)
                    elif hasattr(ctrl, "name"):
                        control_names.append(ctrl.name)
                
                # Enhance query with control context
                if control_codes or control_names:
                    control_context = " ".join(control_codes[:5] + control_names[:5])  # Limit to avoid query bloat
                    control_scoped_query = f"{query} {control_context} metrics KPIs compliance"
            
            # Generate MDL query focused on specific entity types that exist in the database
            # CRITICAL: Only search for entities that exist: assets/hosts/devices, networks, vulnerabilities/issues, applications/projects/users
            mdl_entity_keywords = []
            # Check for asset/host/device related
            if any("asset" in cn or "host" in cn or "device" in cn or "endpoint" in cn for cn in control_names):
                mdl_entity_keywords.extend(["assets", "hosts", "devices"])
            # Check for network related
            if any("network" in cn for cn in control_names):
                mdl_entity_keywords.append("networks")
            # Check for vulnerability/issue related
            if any("vulnerability" in cn or "issue" in cn for cn in control_names):
                mdl_entity_keywords.extend(["vulnerabilities", "issues"])
            # Check for application/project/user related
            if any("application" in cn or "app" in cn or "project" in cn or "user" in cn or "access" in cn for cn in control_names):
                mdl_entity_keywords.extend(["applications", "projects", "users"])
            
            # Default to core entity types if no specific focus
            if not mdl_entity_keywords:
                mdl_entity_keywords = ["assets", "hosts", "devices", "vulnerabilities", "issues", "applications", "projects", "users"]
            
            # Combine with control-scoped query
            focused_mdl_query = f"{control_scoped_query} {' '.join(set(mdl_entity_keywords))}"
            
            # Use resolved_metrics from state if available (from metrics_recommender_node)
            # Otherwise, search MDL for metrics
            resolved_metrics = state.get("resolved_metrics", [])
            calculation_plan = state.get("calculation_plan", {})
            
            if resolved_metrics:
                # Use resolved metrics from state (already filtered and scored)
                logger.info(f"Dashboard generator: Using {len(resolved_metrics)} resolved metrics from state")
                # Convert resolved_metrics to dict format for prompt
                metrics_for_context = []
                for m in resolved_metrics:
                    metrics_for_context.append({
                        "metric_id": m.get("metric_id", ""),
                        "name": m.get("name", ""),
                        "description": m.get("description", ""),
                        "kpis": m.get("kpis", []),
                        "trends": m.get("trends", []),
                        "natural_language_question": m.get("natural_language_question", ""),
                        "source_schemas": m.get("source_schemas", []),
                        "category": m.get("category", "")
                    })
                
                # Get MDL schemas using source_schemas from resolved metrics
                source_schema_names = []
                for m in resolved_metrics:
                    schemas = m.get("source_schemas", [])
                    if isinstance(schemas, list):
                        source_schema_names.extend(schemas)
                
                # Search for schemas by name if we have source_schemas
                if source_schema_names:
                    # Try to get schemas from schema_resolution in context_cache
                    schema_resolution = state.get("context_cache", {}).get("schema_resolution", {})
                    if schema_resolution and isinstance(schema_resolution, dict):
                        schemas_list = schema_resolution.get("schemas", [])
                        table_descs_list = schema_resolution.get("table_descriptions", [])
                        mdl_context = {
                            "db_schemas": schemas_list,
                            "table_descriptions": table_descs_list,
                            "project_meta": [],
                            "metrics": metrics_for_context,  # Use resolved metrics
                        }
                    else:
                        # Fallback: search MDL with source_schemas as query
                        schema_query = " ".join(set(source_schema_names[:5]))
                        mdl_result = loop.run_until_complete(
                            mdl_service.search_all_mdl(
                                query=schema_query,
                                limit_per_collection=5
                            )
                        )
                        mdl_context = {
                            "db_schemas": [s.__dict__ for s in mdl_result.db_schemas],
                            "table_descriptions": [t.__dict__ for t in mdl_result.table_descriptions],
                            "project_meta": [p.__dict__ for p in mdl_result.project_meta],
                            "metrics": metrics_for_context,  # Use resolved metrics instead of search results
                        }
                else:
                    # No source_schemas, do regular search but use resolved metrics
                    mdl_result = loop.run_until_complete(
                        mdl_service.search_all_mdl(
                            query=focused_mdl_query,
                            limit_per_collection=5
                        )
                    )
                    mdl_context = {
                        "db_schemas": [s.__dict__ for s in mdl_result.db_schemas],
                        "table_descriptions": [t.__dict__ for t in mdl_result.table_descriptions],
                        "project_meta": [p.__dict__ for p in mdl_result.project_meta],
                        "metrics": metrics_for_context,  # Use resolved metrics
                    }
            else:
                # No resolved metrics, do regular MDL search
                mdl_result = loop.run_until_complete(
                    mdl_service.search_all_mdl(
                        query=focused_mdl_query,
                        limit_per_collection=5
                    )
                )
                mdl_context = {
                    "db_schemas": [s.__dict__ for s in mdl_result.db_schemas],
                    "table_descriptions": [t.__dict__ for t in mdl_result.table_descriptions],
                    "project_meta": [p.__dict__ for p in mdl_result.project_meta],
                    "metrics": [m.__dict__ for m in mdl_result.metrics],
                }
            
            # Log which controls are being used for dashboard generation
            if controls:
                logger.info(f"Dashboard generator: Generating dashboard for {len(controls)} controls")
                if control_codes:
                    logger.info(f"Dashboard generator: Control codes: {control_codes[:10]}")
            
            # Search for XSOAR dashboard examples
            # Use natural_language_question from resolved metrics if available (more precise anchor)
            xsoar_query = f"{query} compliance monitoring dashboard"
            if resolved_metrics:
                # Use natural_language_question from top metrics as search anchor
                natural_questions = [m.get("natural_language_question", "") for m in resolved_metrics[:3] if m.get("natural_language_question")]
                if natural_questions:
                    # Combine user query with metric questions for precise search
                    xsoar_query = f"{' '.join(natural_questions[:2])} {query}"
                    logger.info(f"Dashboard generator: Using metric natural_language_question for XSOAR search: {xsoar_query[:100]}")
            
            xsoar_result = loop.run_until_complete(
                xsoar_service.search_dashboards(
                    query=xsoar_query,
                    limit=5
                )
            )
            xsoar_context = {
                "dashboards": [d.__dict__ for d in xsoar_result],
            }
        except Exception as e:
            logger.warning(f"MDL/XSOAR retrieval failed for dashboard generator: {e}")
        
        # Format context for prompt
        mdl_str = format_retrieved_context_for_prompt(
            {"mdl": mdl_context},
            include_mdl=True,
            include_xsoar=False
        ) if mdl_context else ""
        
        xsoar_str = format_retrieved_context_for_prompt(
            {"xsoar": xsoar_context},
            include_mdl=False,
            include_xsoar=True
        ) if xsoar_context else ""
        
        # Build control-scoped context message
        control_context_msg = ""
        if controls:
            control_codes = []
            for ctrl in controls[:10]:  # Limit to top 10
                if isinstance(ctrl, dict):
                    code = ctrl.get("code", "")
                    name = ctrl.get("name", "")
                    if code:
                        control_codes.append(f"{code} ({name})" if name else code)
                elif hasattr(ctrl, "code"):
                    control_codes.append(ctrl.code)
            
            if control_codes:
                control_context_msg = f"""
CONTROL-SCOPED METRICS:
The dashboard metrics MUST be scoped to these specific controls that were validated:
{', '.join(control_codes)}

Metrics should measure the effectiveness, implementation status, and test results for these controls.
"""
        
        # Include resolved metrics and calculation plan if available
        resolved_metrics = state.get("resolved_metrics", [])
        calculation_plan = state.get("calculation_plan", {})
        
        resolved_metrics_section = ""
        if resolved_metrics:
            # Format resolved metrics for prompt
            metrics_summary = []
            for m in resolved_metrics[:10]:  # Top 10 for prompt size
                metrics_summary.append({
                    "metric_id": m.get("metric_id", ""),
                    "name": m.get("name", ""),
                    "kpis": m.get("kpis", []),
                    "trends": m.get("trends", []),
                    "natural_language_question": m.get("natural_language_question", "")
                })
            resolved_metrics_section = f"""
Resolved Metrics/KPIs (from metrics recommender - USE THESE AS PRIMARY SOURCE):
{json.dumps(metrics_summary, indent=2)}

CRITICAL: Use these resolved metrics to define dashboard widgets. Each metric has:
- KPIs: Use for gauge/count widgets
- Trends: Use for time-series widgets  
- natural_language_question: Use as widget title/description
"""
        
        calculation_plan_section = ""
        if calculation_plan:
            field_instructions = calculation_plan.get("field_instructions", [])
            metric_instructions = calculation_plan.get("metric_instructions", [])
            if field_instructions or metric_instructions:
                calc_summary = {
                    "field_instructions_count": len(field_instructions),
                    "metric_instructions_count": len(metric_instructions),
                    "sample_instructions": {
                        "fields": field_instructions[:2] if field_instructions else [],
                        "metrics": metric_instructions[:2] if metric_instructions else []
                    }
                }
                calculation_plan_section = f"""
Calculation Plan (field and metric instructions for accurate queries):
{json.dumps(calc_summary, indent=2)}

Use these instructions to write accurate SQL/queries for dashboard widgets.
"""
        
        # Format the human message with all variables first (already formatted since it's an f-string)
        formatted_human_message = f"""
User Query: {query}
Framework: {framework_id or "N/A"}
Controls: {controls_str}
Requirements: {requirements_str}
{control_context_msg}{resolved_metrics_section}{calculation_plan_section}
MDL Context (Database Schemas & Metrics):
{mdl_str}

XSOAR Dashboard Examples:
{xsoar_str}

Generate a compliance dashboard specification with KPIs, metrics, and visualizations.
CRITICAL: 
- If resolved metrics are available, use them as the PRIMARY source for dashboard widgets
- Use calculation_plan instructions to write accurate queries
- The dashboard metrics MUST be scoped to the specific controls listed above
- Use the MDL schemas to understand available data sources and the XSOAR examples as reference for layout/styling
"""
        
        # Use tool-calling agent if tools are available
        if use_tool_calling and tools:
            try:
                system_prompt = prompt_text
                system_prompt += f"\n\nYou have access to {len(tools)} tools. Use them to enrich dashboard specifications."
                
                # Escape curly braces in system prompt to prevent LangChain from parsing JSON examples as template variables
                system_prompt = system_prompt.replace("{", "{{").replace("}", "}}")
                
                # Use a prompt template with agent_scratchpad for tool-calling agent
                prompt = ChatPromptTemplate.from_messages([
                    ("system", system_prompt),
                    ("human", "{input}"),  # Single variable for the formatted input
                    MessagesPlaceholder(variable_name="agent_scratchpad")  # Required for tool-calling agent
                ])
                
                agent_executor = create_tool_calling_agent(
                    llm=llm,
                    tools=tools,
                    prompt=prompt,
                    use_react_agent=False,  # Use direct tool-calling agent to avoid stop sequence issues
                    executor_kwargs={"max_iterations": 8, "verbose": False}
                )
                
                if agent_executor:
                    response = agent_executor.invoke({
                        "input": formatted_human_message
                    })
                    response_content = response.get("output", str(response)) if isinstance(response, dict) else str(response)
                    
                    # Store the raw LLM response for review
                    state["llm_response"] = response_content
                    state["llm_prompt"] = {
                        "system_prompt": system_prompt,
                        "human_message": formatted_human_message
                    }
                    
                    # Log tool-calling agent invocation step
                    log_execution_step(
                        state=state,
                        step_name="llm_invocation_with_tools",
                        agent_name="dashboard_generator",
                        inputs={
                            "system_prompt_length": len(system_prompt),
                            "human_message_length": len(formatted_human_message),
                            "tools_available": len(tools),
                            "tool_names": [getattr(t, 'name', str(t)) for t in tools] if tools else []
                        },
                        outputs={
                            "response_length": len(response_content),
                            "response_preview": response_content[:500] if len(response_content) > 500 else response_content
                        },
                        status="completed"
                    )
                else:
                    raise ValueError("Agent executor creation failed")
            except Exception as e:
                logger.warning(f"Tool-calling agent failed for dashboard_generator, falling back to simple chain: {e}")
                use_tool_calling = False
        
        # Fallback to simple LLM chain
        if not use_tool_calling:
            # Escape curly braces in system prompt to prevent LangChain from parsing JSON examples as template variables
            system_prompt = prompt_text.replace("{", "{{").replace("}", "}}")
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "{input}")  # Single variable for the formatted input
            ])
            chain = prompt | llm
            response = chain.invoke({
                "input": formatted_human_message
            })
            response_content = response.content if hasattr(response, 'content') else str(response)
            
            # Store the raw LLM response for review
            state["llm_response"] = response_content
            state["llm_prompt"] = {
                "system_prompt": system_prompt,
                "human_message": formatted_human_message
            }
            
            # Log LLM invocation step
            log_execution_step(
                state=state,
                step_name="llm_invocation",
                agent_name="dashboard_generator",
                inputs={
                    "system_prompt_length": len(system_prompt),
                    "human_message_length": len(formatted_human_message),
                    "framework_id": framework_id,
                    "controls_count": len(state.get("controls", []))
                },
                outputs={
                    "response_length": len(response_content),
                    "response_preview": response_content[:500] if len(response_content) > 500 else response_content
                },
                status="completed"
            )
        
        # Parse response - dashboard specs should be JSON
        # Use robust JSON extraction with multiple fallback strategies
        result = None
        json_parse_error = None
        
        # Strategy 1: Try direct JSON parse
        try:
            result = json.loads(response_content)
            logger.debug("Successfully parsed JSON directly")
        except json.JSONDecodeError as e:
            json_parse_error = e
            logger.debug(f"Direct JSON parse failed: {e}")
        
        # Strategy 2: Extract from markdown code blocks (multiple formats)
        if result is None:
            json_patterns = [
                r'```json\s*(\{.*?\})\s*```',  # ```json {...} ```
                r'```\s*(\{.*?\})\s*```',       # ``` {...} ```
                r'`(\{.*?\})`',                 # `{...}`
            ]
            for pattern in json_patterns:
                try:
                    json_match = re.search(pattern, response_content, re.DOTALL)
                    if json_match:
                        result = json.loads(json_match.group(1))
                        logger.debug(f"Successfully extracted JSON from markdown pattern: {pattern[:20]}")
                        break
                except (json.JSONDecodeError, AttributeError) as e:
                    continue
        
        # Strategy 3: Find JSON object boundaries by counting braces
        if result is None:
            try:
                start_idx = response_content.find('{')
                if start_idx >= 0:
                    # Find matching closing brace by counting
                    brace_count = 0
                    end_idx = start_idx
                    for i in range(start_idx, len(response_content)):
                        if response_content[i] == '{':
                            brace_count += 1
                        elif response_content[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_idx = i + 1
                                break
                    
                    if end_idx > start_idx:
                        json_str = response_content[start_idx:end_idx]
                        # Try to clean up common issues
                        json_str = re.sub(r',\s*}', '}', json_str)  # Remove trailing commas before }
                        json_str = re.sub(r',\s*]', ']', json_str)  # Remove trailing commas before ]
                        result = json.loads(json_str)
                        logger.debug("Successfully extracted JSON by brace matching")
            except (json.JSONDecodeError, ValueError) as e:
                logger.debug(f"Brace matching extraction failed: {e}")
        
        # Strategy 4: Try to find and parse just the dashboard_specification key
        if result is None:
            try:
                # Look for "dashboard_specification": {...} pattern
                spec_match = re.search(r'"dashboard_specification"\s*:\s*(\{.*?\})', response_content, re.DOTALL)
                if spec_match:
                    spec_json = spec_match.group(1)
                    # Find matching closing brace
                    brace_count = 0
                    end_pos = 0
                    for i, char in enumerate(spec_json):
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_pos = i + 1
                                break
                    if end_pos > 0:
                        spec_json = spec_json[:end_pos]
                        spec_json = re.sub(r',\s*}', '}', spec_json)
                        spec_json = re.sub(r',\s*]', ']', spec_json)
                        result = {"dashboard_specification": json.loads(spec_json)}
                        logger.debug("Successfully extracted dashboard_specification object")
            except (json.JSONDecodeError, ValueError, AttributeError) as e:
                logger.debug(f"dashboard_specification extraction failed: {e}")
        
        # Strategy 5: Last resort - create error result
        if result is None:
            logger.warning(f"Could not parse dashboard JSON. Error: {json_parse_error}")
            logger.warning(f"Response preview (first 1000 chars): {response_content[:1000]}")
            result = {
                "dashboard_specification": {
                    "error": "Could not parse dashboard specification from LLM response",
                    "parse_error": str(json_parse_error) if json_parse_error else "Unknown error",
                    "response_length": len(response_content)
                }
            }
        
        if "dashboard_specification" in result:
            state["dashboards"] = [result["dashboard_specification"]]
        
        # Log dashboard generation step
        log_execution_step(
            state=state,
            step_name="dashboard_generation",
            agent_name="dashboard_generator",
            inputs={
                "framework_id": framework_id,
                "controls_count": len(state.get("controls", [])),
                "requirements_count": len(state.get("requirements", []))
            },
            outputs={
                "dashboards_generated": len(state.get("dashboards", [])),
                "dashboards": state.get("dashboards", [])
            },
            status="completed"
        )
        
        state["messages"].append(AIMessage(
            content=f"Generated dashboard specification for {framework_id or 'compliance'} framework"
        ))
        
    except Exception as e:
        logger.error(f"Dashboard generator failed: {e}", exc_info=True)
        state["error"] = f"Dashboard generation failed: {str(e)}"
    
    return state


# ============================================================================
# Calculation Planner Node
# ============================================================================

# ============================================================================
# Risk Control Mapper Node
# ============================================================================

def risk_control_mapper_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Maps vulnerabilities/CVEs to controls, risks, and detection signals.
    Uses ATT&CK techniques as the bridge between vulnerabilities and controls.
    """
    try:
        prompt_text = load_prompt("14_risk_control_map")
        
        # Get tools conditionally - this agent needs CVE, ATT&CK, and threat intelligence tools
        tools = get_tools_for_agent("detection_engineer", state=state, conditional=True)  # Use detection_engineer tools (CVE, ATT&CK, etc.)
        use_tool_calling = should_use_tool_calling_agent("detection_engineer", state=state)
        
        llm = get_llm(temperature=0)
        
        # Extract CVE or attack technique from query
        query = state.get("user_query", "")
        framework_id = state.get("framework_id")
        
        # Retrieve framework context if not already present
        retrieval_service = RetrievalService()
        
        if not state.get("controls") and framework_id:
            try:
                # Search for controls that might address vulnerabilities
                controls_context = retrieval_service.search_controls(
                    query=f"{query} vulnerability detection prevention",
                    limit=10,
                    framework_filter=[framework_id] if framework_id else None
                )
                if controls_context and hasattr(controls_context, 'controls'):
                    state["controls"] = [c.__dict__ for c in controls_context.controls]
            except Exception as e:
                logger.warning(f"Failed to retrieve controls for risk mapping: {e}")
        
        if not state.get("risks") and framework_id:
            try:
                # Search for risks related to vulnerabilities
                risks_context = retrieval_service.search_risks(
                    query=f"{query} vulnerability exploitation attack",
                    limit=10,
                    framework_filter=[framework_id] if framework_id else None
                )
                if risks_context and hasattr(risks_context, 'risks'):
                    state["risks"] = [r.__dict__ for r in risks_context.risks]
            except Exception as e:
                logger.warning(f"Failed to retrieve risks for risk mapping: {e}")
        
        if not state.get("scenarios") and framework_id:
            try:
                # Search for attack scenarios
                scenarios_context = retrieval_service.search_scenarios(
                    query=f"{query} attack scenario exploitation",
                    limit=10,
                    framework_filter=[framework_id] if framework_id else None
                )
                if scenarios_context and hasattr(scenarios_context, 'scenarios'):
                    state["scenarios"] = [s.__dict__ for s in scenarios_context.scenarios]
            except Exception as e:
                logger.warning(f"Failed to retrieve scenarios for risk mapping: {e}")
        
        # Get framework context
        controls_str = json.dumps(state.get("controls", []), indent=2)
        risks_str = json.dumps(state.get("risks", []), indent=2)
        scenarios_str = json.dumps(state.get("scenarios", []), indent=2)
        
        # Retrieve XSOAR playbooks and scripts for detection patterns
        xsoar_context = {}
        
        try:
            import asyncio
            from app.retrieval.xsoar_service import XSOARRetrievalService
            
            xsoar_service = XSOARRetrievalService()
            
            # Run async retrieval
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop = asyncio.new_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
            
            # Search for relevant XSOAR playbooks and scripts
            xsoar_playbooks = loop.run_until_complete(
                xsoar_service.search_playbooks(
                    query=f"{query} CVE vulnerability detection response",
                    limit=5
                )
            )
            xsoar_scripts = loop.run_until_complete(
                xsoar_service.search_scripts(
                    query=f"{query} CVE enrichment detection",
                    limit=5
                )
            )
            
            xsoar_context = {
                "playbooks": [p.__dict__ for p in xsoar_playbooks],
                "scripts": [s.__dict__ for s in xsoar_scripts],
            }
        except Exception as e:
            logger.warning(f"XSOAR retrieval failed for risk_control_mapper: {e}")
        
        # Format context for prompt
        xsoar_str = format_retrieved_context_for_prompt(
            {"xsoar": xsoar_context},
            include_mdl=False,
            include_xsoar=True
        ) if xsoar_context else ""
        
        human_message = f"""
User Query: {query}
Framework: {state.get('framework_id', 'N/A')}
Controls: {controls_str}
Risks: {risks_str}
Scenarios: {scenarios_str}

XSOAR Detection Patterns & Playbooks:
{xsoar_str}

Map the vulnerability/CVE to controls, risks, and detection signals.
Use ATT&CK techniques as the bridge. Use available tools to enrich CVE data and ATT&CK mappings.
"""
        
        # Use tool-calling agent if tools are available (CVE, ATT&CK, threat intel)
        if use_tool_calling and tools:
            try:
                system_prompt = prompt_text
                system_prompt += f"\n\nYou have access to {len(tools)} security intelligence tools (CVE, ATT&CK, EPSS, etc.). Use them to enrich vulnerability mappings."
                
                # Escape curly braces in system prompt to prevent LangChain from parsing JSON examples as template variables
                system_prompt = system_prompt.replace("{", "{{").replace("}", "}}")
                
                prompt = ChatPromptTemplate.from_messages([
                    ("system", "{system_prompt}"),
                    ("human", human_message)
                ])
                
                agent_executor = create_tool_calling_agent(
                    llm=llm,
                    tools=tools,
                    prompt=prompt,
                    use_react_agent=True,
                    executor_kwargs={"max_iterations": 10, "verbose": False}
                )
                
                if agent_executor:
                    response = agent_executor.invoke({
                        "query": query,
                        "framework_id": state.get('framework_id', 'N/A'),
                        "controls": controls_str,
                        "risks": risks_str,
                        "scenarios": scenarios_str
                    })
                    response_content = response.get("output", str(response)) if isinstance(response, dict) else str(response)
                    
                    # Store the raw LLM response for review
                    state["llm_response"] = response_content
                    state["llm_prompt"] = {
                        "system_prompt": system_prompt,
                        "human_message": human_message
                    }
                    
                    # Log tool-calling agent invocation step
                    log_execution_step(
                        state=state,
                        step_name="llm_invocation_with_tools",
                        agent_name="risk_control_mapper",
                        inputs={
                            "system_prompt_length": len(system_prompt),
                            "human_message_length": len(human_message),
                            "tools_available": len(tools),
                            "tool_names": [getattr(t, 'name', str(t)) for t in tools] if tools else [],
                            "query": query
                        },
                        outputs={
                            "response_length": len(response_content),
                            "response_preview": response_content[:500] if len(response_content) > 500 else response_content
                        },
                        status="completed"
                    )
                else:
                    raise ValueError("Agent executor creation failed")
            except Exception as e:
                logger.warning(f"Tool-calling agent failed for risk_control_mapper, falling back to simple chain: {e}")
                use_tool_calling = False
        
        # Fallback to simple LLM chain
        if not use_tool_calling:
            # Escape curly braces in system prompt to prevent LangChain from parsing JSON examples as template variables
            system_prompt = prompt_text.replace("{", "{{").replace("}", "}}")
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", human_message)
            ])
            chain = prompt | llm
            response = chain.invoke({
                "query": query,
                "framework_id": state.get('framework_id', 'N/A'),
                "controls": controls_str,
                "risks": risks_str,
                "scenarios": scenarios_str
            })
            response_content = response.content if hasattr(response, 'content') else str(response)
            
            # Store the raw LLM response for review
            state["llm_response"] = response_content
            state["llm_prompt"] = {
                "system_prompt": system_prompt,
                "human_message": human_message
            }
            
            # Log LLM invocation step
            log_execution_step(
                state=state,
                step_name="llm_invocation",
                agent_name="risk_control_mapper",
                inputs={
                    "system_prompt_length": len(system_prompt),
                    "human_message_length": len(human_message),
                    "query": query,
                    "framework_id": state.get('framework_id'),
                    "controls_count": len(state.get("controls", [])),
                    "risks_count": len(state.get("risks", [])),
                    "scenarios_count": len(state.get("scenarios", []))
                },
                outputs={
                    "response_length": len(response_content),
                    "response_preview": response_content[:500] if len(response_content) > 500 else response_content
                },
                status="completed"
            )
        
        # Parse response - vulnerability mappings should be JSON
        try:
            result = json.loads(response_content)
        except json.JSONDecodeError:
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                # Try to extract JSON from response
                start_idx = response_content.find('{')
                end_idx = response_content.rfind('}') + 1
                if start_idx >= 0 and end_idx > start_idx:
                    result = json.loads(response_content[start_idx:end_idx])
                else:
                    result = {"vulnerability_to_control_mapping": {"error": "Could not parse mapping"}}
        
        if "vulnerability_to_control_mapping" in result:
            state["vulnerability_mappings"] = [result["vulnerability_to_control_mapping"]]
        
        # Log risk control mapping step
        log_execution_step(
            state=state,
            step_name="risk_control_mapping",
            agent_name="risk_control_mapper",
            inputs={
                "query": query,
                "framework_id": state.get('framework_id'),
                "controls_count": len(state.get("controls", [])),
                "risks_count": len(state.get("risks", [])),
                "scenarios_count": len(state.get("scenarios", []))
            },
            outputs={
                "mappings_generated": len(state.get("vulnerability_mappings", [])),
                "vulnerability_mappings": state.get("vulnerability_mappings", [])
            },
            status="completed"
        )
        
        state["messages"].append(AIMessage(
            content=f"Generated vulnerability-to-control mapping for {query[:50]}..."
        ))
        
    except Exception as e:
        logger.error(f"Risk control mapper failed: {e}", exc_info=True)
        state["error"] = f"Risk control mapping failed: {str(e)}"
    
    return state


# ============================================================================
# Gap Analysis Node
# ============================================================================

def gap_analysis_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Performs comprehensive gap analysis between current state and target framework requirements.
    
    Identifies missing controls, categorizes gaps by severity, prioritizes remediation,
    and provides actionable remediation roadmaps with effort/cost estimates.
    """
    try:
        prompt_text = load_prompt("10_gap_analysis")
        
        # Get tools conditionally - gap analysis needs compliance and ATT&CK tools
        tools = get_tools_for_agent("gap_analysis", state=state, conditional=True)
        use_tool_calling = should_use_tool_calling_agent("gap_analysis", state=state)
        
        llm = get_llm(temperature=0)
        
        framework_id = state.get("framework_id")
        requirement_id = state.get("requirement_id")
        requirement_code = state.get("requirement_code")
        
        # Retrieve framework context
        retrieval_service = RetrievalService()
        
        # Get all required controls for the framework/requirement
        if not state.get("controls") and framework_id:
            try:
                if requirement_id:
                    # Get controls for specific requirement
                    req_context = retrieval_service.get_requirement_context(requirement_id)
                    if req_context and hasattr(req_context, 'requirements') and req_context.requirements:
                        req = req_context.requirements[0]
                        if hasattr(req, 'satisfying_controls'):
                            state["controls"] = [
                                {
                                    "id": c.id,
                                    "control_code": getattr(c, 'control_code', c.id),
                                    "name": c.name,
                                    "description": c.description,
                                    "control_type": getattr(c, 'control_type', None),
                                }
                                for c in req.satisfying_controls
                            ]
                else:
                    # Search for controls in the framework
                    controls_context = retrieval_service.search_controls(
                        query=f"{state.get('user_query', '')} compliance controls",
                        limit=100,
                        framework_filter=[framework_id] if framework_id else None
                    )
                    if controls_context and hasattr(controls_context, 'controls'):
                        state["controls"] = [
                            {
                                "id": c.id,
                                "control_code": getattr(c, 'control_code', c.id),
                                "name": c.name,
                                "description": c.description,
                                "control_type": getattr(c, 'control_type', None),
                            }
                            for c in controls_context.controls
                        ]
            except Exception as e:
                logger.warning(f"Failed to retrieve controls for gap analysis: {e}")
        
        # Get risks and test cases for context
        if not state.get("risks") and framework_id:
            try:
                risks_context = retrieval_service.search_risks(
                    query=f"{state.get('user_query', '')} security risks",
                    limit=50,
                    framework_filter=[framework_id] if framework_id else None
                )
                if risks_context and hasattr(risks_context, 'risks'):
                    state["risks"] = [r.__dict__ for r in risks_context.risks]
            except Exception as e:
                logger.warning(f"Failed to retrieve risks for gap analysis: {e}")
        
        if not state.get("test_cases") and framework_id:
            try:
                test_cases_context = retrieval_service.search_test_cases(
                    query=f"{state.get('user_query', '')} test validation",
                    limit=50,
                    framework_filter=[framework_id] if framework_id else None
                )
                if test_cases_context and hasattr(test_cases_context, 'test_cases'):
                    state["test_cases"] = [tc.__dict__ for tc in test_cases_context.test_cases]
            except Exception as e:
                logger.warning(f"Failed to retrieve test cases for gap analysis: {e}")
        
        # Format context for prompt
        controls_str = json.dumps(state.get("controls", []), indent=2)
        risks_str = json.dumps(state.get("risks", []), indent=2)
        test_cases_str = json.dumps(state.get("test_cases", []), indent=2)
        user_query = state.get("user_query", "")
        
        human_message = f"""
Framework: {framework_id or 'Not specified'}
Requirement: {requirement_code or requirement_id or 'Full framework assessment'}

Current Controls (claimed/implemented): {len(state.get('controls', []))}
Risks Identified: {len(state.get('risks', []))}
Test Cases Available: {len(state.get('test_cases', []))}

Controls Data:
{controls_str}

Risks Data:
{risks_str}

Test Cases Data:
{test_cases_str}

User Query: {user_query}

Perform comprehensive gap analysis. Identify ALL gaps, categorize by severity,
prioritize by risk-effort matrix, and provide actionable remediation roadmaps.
"""
        
        # Use tool-calling agent if tools are available
        if use_tool_calling and tools:
            try:
                system_prompt = prompt_text
                system_prompt += f"\n\nYou have access to {len(tools)} compliance tools. Use them to look up control details, CIS benchmarks, and ATT&CK mappings."
                
                prompt = ChatPromptTemplate.from_messages([
                    ("system", system_prompt),
                    ("human", human_message)
                ])
                
                agent_executor = create_tool_calling_agent(
                    llm=llm,
                    tools=tools,
                    prompt=prompt,
                    use_react_agent=True,
                    executor_kwargs={"max_iterations": 10, "verbose": False}
                )
                
                if agent_executor:
                    response = agent_executor.invoke({
                        "system_prompt": system_prompt,
                        "framework_id": framework_id or "N/A",
                        "requirement_code": requirement_code or "N/A",
                        "controls": controls_str,
                        "risks": risks_str,
                        "test_cases": test_cases_str,
                        "user_query": user_query
                    })
                    response_content = response.get("output", str(response)) if isinstance(response, dict) else str(response)
                else:
                    raise ValueError("Agent executor creation failed")
            except Exception as e:
                logger.warning(f"Tool-calling agent failed for gap_analysis, falling back to standard LLM: {e}")
                use_tool_calling = False
        
        if not use_tool_calling:
            # Standard LLM call
            system_prompt = prompt_text
            if tools:
                system_prompt += f"\n\nNote: {len(tools)} compliance tools are available but tool-calling is disabled. Consider mentioning relevant control details and framework information in your analysis."
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", "{system_prompt}"),
                ("human", human_message)
            ])
            
            chain = prompt | llm
            response = chain.invoke({
                "system_prompt": system_prompt,
                "framework_id": framework_id or "N/A",
                "requirement_code": requirement_code or "N/A",
                "controls": controls_str,
                "risks": risks_str,
                "test_cases": test_cases_str,
                "user_query": user_query
            })
            response_content = response.content
        
        # Parse JSON response
        try:
            # Extract JSON from markdown code blocks if present
            if "```json" in response_content:
                json_start = response_content.find("```json") + 7
                json_end = response_content.find("```", json_start)
                response_content = response_content[json_start:json_end].strip()
            elif "```" in response_content:
                json_start = response_content.find("```") + 3
                json_end = response_content.find("```", json_start)
                response_content = response_content[json_start:json_end].strip()
            
            gap_analysis_data = json.loads(response_content)
            
            # Extract gap_analysis object if nested
            if "gap_analysis" in gap_analysis_data:
                gap_analysis_data = gap_analysis_data["gap_analysis"]
            
            # Store results in state
            if isinstance(gap_analysis_data, dict):
                state["gap_analysis_results"] = [gap_analysis_data]
            elif isinstance(gap_analysis_data, list):
                state["gap_analysis_results"] = gap_analysis_data
            else:
                state["gap_analysis_results"] = [{"raw_content": gap_analysis_data}]
            
            # Extract summary for message
            summary = gap_analysis_data.get("summary", {})
            total_gaps = summary.get("gaps_identified", 0)
            critical_gaps = summary.get("gaps_by_severity", {}).get("critical", 0)
            
            state["messages"].append(AIMessage(
                content=f"Gap analysis complete. Identified {total_gaps} gaps ({critical_gaps} critical). "
                       f"See gap_analysis_results for detailed remediation roadmap."
            ))
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse gap analysis JSON: {e}")
            # Store raw content as fallback
            state["gap_analysis_results"] = [{"raw_content": response_content}]
            state["messages"].append(AIMessage(
                content=f"Gap analysis completed but response format needs review. Raw content stored in gap_analysis_results."
            ))
        
    except Exception as e:
        logger.error(f"Gap analysis node failed: {e}", exc_info=True)
        state["error"] = f"Gap analysis failed: {str(e)}"
    
    return state


# ============================================================================
# Cross Framework Mapper Node
# ============================================================================

def cross_framework_mapper_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Maps controls and requirements across different compliance frameworks.
    
    Identifies equivalent, related, and partial mappings between frameworks,
    calculates coverage percentages, and highlights consolidation opportunities.
    """
    try:
        prompt_text = load_prompt("11_cross_framework_mapper")
        
        # Get tools conditionally - cross-framework mapping needs compliance tools
        tools = get_tools_for_agent("cross_framework_mapper", state=state, conditional=True)
        use_tool_calling = should_use_tool_calling_agent("cross_framework_mapper", state=state)
        
        llm = get_llm(temperature=0)
        
        framework_id = state.get("framework_id")
        controls = state.get("controls", [])
        
        # Retrieve framework context and existing cross-framework mappings
        retrieval_service = RetrievalService()
        
        # Get existing cross-framework mappings from database if controls are available
        existing_mappings = []
        if controls:
            try:
                # Get mappings for the first control (or iterate through all)
                for control in controls[:5]:  # Limit to first 5 to avoid too many queries
                    control_id = control.get("id")
                    if control_id:
                        try:
                            cross_fw_context = retrieval_service.get_cross_framework_equivalents(
                                control_id=control_id,
                                target_frameworks=None  # Get all frameworks
                            )
                            if cross_fw_context and hasattr(cross_fw_context, 'cross_framework_mappings'):
                                for mapping in cross_fw_context.cross_framework_mappings:
                                    existing_mappings.append({
                                        "source_control_id": control_id,
                                        "target_framework_id": getattr(mapping, 'target_framework_id', None),
                                        "target_control_id": getattr(mapping, 'target_control_id', None),
                                        "target_control_code": getattr(mapping, 'target_control_code', None),
                                        "mapping_type": getattr(mapping, 'mapping_type', 'equivalent'),
                                        "confidence_score": getattr(mapping, 'confidence_score', 0.8),
                                    })
                        except Exception as e:
                            logger.debug(f"Could not get cross-framework mappings for control {control_id}: {e}")
            except Exception as e:
                logger.warning(f"Failed to retrieve existing cross-framework mappings: {e}")
        
        # Format context for prompt
        controls_str = json.dumps(controls, indent=2)
        existing_mappings_str = json.dumps(existing_mappings, indent=2) if existing_mappings else "[]"
        
        # Extract target frameworks from user query if mentioned
        user_query = state.get("user_query", "")
        target_frameworks = []
        framework_keywords = {
            "hipaa": "hipaa",
            "soc2": "soc2",
            "soc 2": "soc2",
            "nist": "nist_csf_2_0",
            "nist csf": "nist_csf_2_0",
            "cis": "cis_v8_1",
            "iso 27001": "iso27001_2022",
            "iso27001": "iso27001_2022",
        }
        for keyword, fw_id in framework_keywords.items():
            if keyword.lower() in user_query.lower():
                target_frameworks.append(fw_id)
        
        human_message = f"""
Source Framework: {framework_id or 'Not specified'}
Target Frameworks: {', '.join(target_frameworks) if target_frameworks else 'All frameworks (identify from query)'}

Source Controls:
{controls_str}

Existing Mappings (from database):
{existing_mappings_str}

User Query: {user_query}

Perform cross-framework mapping analysis. Identify equivalent, related, and partial mappings.
Calculate coverage percentages and highlight consolidation opportunities.
"""
        
        # Use tool-calling agent if tools are available
        if use_tool_calling and tools:
            try:
                system_prompt = prompt_text
                system_prompt += f"\n\nYou have access to {len(tools)} compliance tools. Use them to look up control details and framework information."
                
                prompt = ChatPromptTemplate.from_messages([
                    ("system", system_prompt),
                    ("human", human_message)
                ])
                
                agent_executor = create_tool_calling_agent(
                    llm=llm,
                    tools=tools,
                    prompt=prompt,
                    use_react_agent=True,
                    executor_kwargs={"max_iterations": 10, "verbose": False}
                )
                
                if agent_executor:
                    response = agent_executor.invoke({
                        "source_framework": framework_id or "N/A",
                        "target_frameworks": ", ".join(target_frameworks) if target_frameworks else "All frameworks",
                        "controls": controls_str,
                        "existing_mappings": existing_mappings_str,
                        "user_query": user_query
                    })
                    response_content = response.get("output", str(response)) if isinstance(response, dict) else str(response)
                else:
                    raise ValueError("Agent executor creation failed")
            except Exception as e:
                logger.warning(f"Tool-calling agent failed for cross_framework_mapper, falling back to standard LLM: {e}")
                use_tool_calling = False
        
        if not use_tool_calling:
            # Standard LLM call
            system_prompt = prompt_text
            if tools:
                system_prompt += f"\n\nNote: {len(tools)} compliance tools are available but tool-calling is disabled. Consider mentioning relevant framework mappings and control details in your analysis."
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", human_message)
            ])
            
            chain = prompt | llm
            response = chain.invoke({
                "source_framework": framework_id or "N/A",
                "target_frameworks": ", ".join(target_frameworks) if target_frameworks else "All frameworks",
                "controls": controls_str,
                "existing_mappings": existing_mappings_str,
                "user_query": user_query
            })
            response_content = response.content
        
        # Parse JSON response
        try:
            # Extract JSON from markdown code blocks if present
            if "```json" in response_content:
                json_start = response_content.find("```json") + 7
                json_end = response_content.find("```", json_start)
                response_content = response_content[json_start:json_end].strip()
            elif "```" in response_content:
                json_start = response_content.find("```") + 3
                json_end = response_content.find("```", json_start)
                response_content = response_content[json_start:json_end].strip()
            
            mapping_data = json.loads(response_content)
            
            # Extract cross_framework_mapping object if nested
            if "cross_framework_mapping" in mapping_data:
                mapping_data = mapping_data["cross_framework_mapping"]
            
            # Extract mappings list
            mappings_list = []
            if isinstance(mapping_data, dict):
                # If it's a single mapping object with mappings array
                if "mappings" in mapping_data:
                    mappings_list = mapping_data["mappings"]
                else:
                    # Store the whole object
                    mappings_list = [mapping_data]
            elif isinstance(mapping_data, list):
                mappings_list = mapping_data
            
            # Store results in state
            state["cross_framework_mappings"] = mappings_list
            
            # Extract summary for message
            coverage_info = mapping_data.get("target_framework_coverage", {}) if isinstance(mapping_data, dict) else {}
            coverage_pct = coverage_info.get("coverage_percentage", 0)
            total_mapped = coverage_info.get("controls_mapped", len(mappings_list))
            
            state["messages"].append(AIMessage(
                content=f"Cross-framework mapping complete. Found {len(mappings_list)} mappings. "
                       f"Coverage: {coverage_pct:.1f}% ({total_mapped} controls mapped). "
                       f"See cross_framework_mappings for detailed analysis."
            ))
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse cross-framework mapping JSON: {e}")
            # Store raw content as fallback
            state["cross_framework_mappings"] = [{"raw_content": response_content}]
            state["messages"].append(AIMessage(
                content=f"Cross-framework mapping completed but response format needs review. Raw content stored in cross_framework_mappings."
            ))
        
    except Exception as e:
        logger.error(f"Cross framework mapper node failed: {e}", exc_info=True)
        state["error"] = f"Cross framework mapping failed: {str(e)}"
    
    return state

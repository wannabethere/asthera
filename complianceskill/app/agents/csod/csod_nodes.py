"""
CSOD Workflow Nodes

All LangGraph node functions for the CSOD Metrics, Tables, and KPIs Recommender workflow.

Node execution order (varies by intent):
  csod_intent_classifier_node
    → csod_planner_node
      → csod_mdl_schema_retrieval_node
        → csod_metrics_retrieval_node
          → csod_scoring_validator_node
            → [Intent-specific routing]
              → csod_metrics_recommender_node (for metrics_dashboard_plan, metrics_recommender_with_gold_plan)
              → csod_dashboard_generator_node (for dashboard_generation_for_persona)
              → csod_compliance_test_generator_node (for compliance_test_generator)
            → csod_scheduler_node (optional, for scheduling/adhoc planning)
              → csod_output_assembler_node
                → END
"""
import json
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.agents.state import EnhancedCompliancePipelineState
from app.agents.prompt_loader import load_prompt, PROMPTS_CSOD
from app.agents.shared.tool_integration import (
    intelligent_retrieval,
    format_retrieved_context_for_prompt,
    create_tool_calling_agent,
)
from app.core.dependencies import get_llm
from app.retrieval.service import RetrievalService
from app.retrieval.mdl_service import build_schema_ddl

from .csod_tool_integration import (
    run_async,
    csod_get_tools_for_agent,
    csod_retrieve_mdl_schemas,
    csod_retrieve_gold_standard_tables,
    csod_format_scored_context_for_prompt,
)
from .csod_mdl_utils import prune_columns_from_schemas
from .csod_state import CSODWorkflowState
from app.agents.mdlworkflows.contextual_data_retrieval_agent import ContextualDataRetrievalAgent

logger = logging.getLogger(__name__)

# Alias for readability
CSOD_State = CSODWorkflowState


# ============================================================================
# Shared helpers
# ============================================================================

def _csod_log_step(
    state: CSOD_State,
    step_name: str,
    agent_name: str,
    inputs: Dict[str, Any],
    outputs: Dict[str, Any],
    status: str = "completed",
    error: Optional[str] = None,
) -> None:
    """Append a step record to state["execution_steps"]."""
    if "execution_steps" not in state:
        state["execution_steps"] = []
    state["execution_steps"].append({
        "step_name": step_name,
        "agent_name": agent_name,
        "timestamp": datetime.utcnow().isoformat(),
        "status": status,
        "inputs": inputs,
        "outputs": outputs,
        "error": error,
    })


def _parse_json_response(response_content: str, fallback: Any) -> Any:
    """Parse JSON from LLM response with ```json fence fallback."""
    try:
        return json.loads(response_content)
    except json.JSONDecodeError:
        match = re.search(r'```json\s*(\{.*?\})\s*```', response_content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        # Try array form
        match = re.search(r'```json\s*(\[.*?\])\s*```', response_content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return fallback


def _llm_invoke(
    state: CSOD_State,
    agent_name: str,
    prompt_text: str,
    human_message: str,
    tools: List[Any],
    use_tool_calling: bool,
    max_tool_iterations: int = 8,
) -> str:
    """
    Unified LLM invocation helper. Tries tool-calling agent first; falls back
    to simple chain.
    """
    llm = get_llm(temperature=0)

    if use_tool_calling and tools:
        try:
            system_prompt = prompt_text.replace("{", "{{").replace("}", "}}")
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ])
            executor = create_tool_calling_agent(
                llm=llm,
                tools=tools,
                prompt=prompt,
                use_react_agent=False,
                executor_kwargs={"max_iterations": max_tool_iterations, "verbose": False},
            )
            if executor:
                response = executor.invoke({"input": human_message})
                return response.get("output", str(response)) if isinstance(response, dict) else str(response)
        except Exception as e:
            logger.warning(f"{agent_name}: tool-calling agent failed, falling back to simple chain: {e}")

    # Simple chain fallback
    system_prompt = prompt_text.replace("{", "{{").replace("}", "}}")
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
    ])
    chain = prompt | llm
    response = chain.invoke({"input": human_message})
    return response.content if hasattr(response, "content") else str(response)


# ============================================================================
# 1. Intent Classifier Node
# ============================================================================

def csod_intent_classifier_node(state: CSOD_State) -> CSOD_State:
    """
    Classifies the user query into one of 4 CSOD intents:
    1. metrics_dashboard_plan - Plan for a metrics dashboard
    2. metrics_recommender_with_gold_plan - Metrics recommender with gold plan
    3. dashboard_generation_for_persona - Dashboard generation for a persona
    4. compliance_test_generator - Compliance test generator that runs alerts (SQL operations)
    
    Output fields populated:
        csod_intent, csod_persona (if applicable), data_enrichment
        (needs_mdl, needs_metrics, suggested_focus_areas, metrics_intent)
    """
    try:
        try:
            prompt_text = load_prompt("01_intent_classifier", prompts_dir=str(PROMPTS_CSOD))
        except FileNotFoundError:
            # Fallback prompt
            prompt_text = """You are an intent classifier for CSOD (Cornerstone OnDemand) workflow.
Classify the user query into one of these intents:
1. metrics_dashboard_plan - User wants to plan/create a metrics dashboard
2. metrics_recommender_with_gold_plan - User wants metrics recommendations with a gold plan
3. dashboard_generation_for_persona - User wants to generate a dashboard for a specific persona
4. compliance_test_generator - User wants to generate compliance tests/alerts (SQL operations)

Return JSON:
{
    "intent": "one of the 4 intents above",
    "persona": "persona name if intent is dashboard_generation_for_persona, else null",
    "confidence_score": 0.0-1.0,
    "data_enrichment": {
        "needs_mdl": true/false,
        "needs_metrics": true/false,
        "suggested_focus_areas": ["list", "of", "areas"],
        "metrics_intent": "current_state" | "trend" | "forecast"
    }
}"""

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


# ============================================================================
# 2. Planner Node
# ============================================================================

def csod_planner_node(state: CSOD_State) -> CSOD_State:
    """
    Produces the CSOD execution plan based on the classified intent.
    
    Output fields populated:
        csod_plan_summary, csod_estimated_complexity, csod_execution_plan,
        csod_data_sources_in_scope, csod_gap_notes
    """
    try:
        try:
            prompt_text = load_prompt("02_csod_planner", prompts_dir=str(PROMPTS_CSOD))
        except FileNotFoundError:
            prompt_text = """You are a planner for CSOD workflow.
Create an execution plan based on the intent and user query.
Return JSON with plan_summary, estimated_complexity, execution_plan, data_sources_in_scope, gap_notes."""

        tools = csod_get_tools_for_agent("csod_planner", state=state, conditional=True)
        use_tool_calling = bool(tools)

        intent = state.get("csod_intent", "")
        user_query = state.get("user_query", "")
        data_enrichment = state.get("data_enrichment", {})
        focus_areas = data_enrichment.get("suggested_focus_areas", [])
        selected_data_sources = state.get("selected_data_sources", [])

        human_message = f"""User Query: {user_query}
Intent: {intent}
Focus Areas: {json.dumps(focus_areas)}
Selected Data Sources: {json.dumps(selected_data_sources)}
Metrics Intent: {data_enrichment.get('metrics_intent', 'current_state')}
Needs MDL: {data_enrichment.get('needs_mdl', False)}
Needs Metrics: {data_enrichment.get('needs_metrics', False)}

Produce the execution plan JSON as specified in your instructions."""

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

        state["messages"].append(AIMessage(
            content=(
                f"CSOD Plan: {state['csod_plan_summary'][:100]} | "
                f"sources={state['csod_data_sources_in_scope']}"
            )
        ))

    except Exception as e:
        logger.error(f"csod_planner_node failed: {e}", exc_info=True)
        state["error"] = f"CSOD planner failed: {str(e)}"
        state.setdefault("csod_plan_summary", "")
        state.setdefault("csod_estimated_complexity", "moderate")
        state.setdefault("csod_execution_plan", [])
        state.setdefault("csod_data_sources_in_scope", state.get("selected_data_sources", []))

    return state


# ============================================================================
# 3. MDL Schema Retrieval Node
# ============================================================================

def csod_mdl_schema_retrieval_node(state: CSOD_State) -> CSOD_State:
    """
    Retrieves MDL schemas for CSOD workflow.
    Reuses DT pattern but can be customized for CSOD-specific needs.
    """
    try:
        resolved_metrics = state.get("resolved_metrics", [])
        user_query = state.get("user_query", "")
        focus_area_categories = state.get("focus_area_categories", [])
        project_id = (
            state.get("active_project_id")
            or (state.get("compliance_profile") or {}).get("project_id", "")
            or ""
        )
        silver_gold_tables_only = state.get("silver_gold_tables_only", False)

        # Collect schema names from resolved metrics
        schema_names: List[str] = []
        for metric in resolved_metrics:
            for sn in metric.get("source_schemas", []):
                if sn and sn not in schema_names:
                    schema_names.append(sn)

        fallback_query = " ".join(focus_area_categories + [user_query]).strip()
        selected_data_sources = state.get("csod_data_sources_in_scope", []) or state.get("selected_data_sources", [])

        # Retrieve schemas using CSOD helper
        schema_data = csod_retrieve_mdl_schemas(
            schema_names=schema_names,
            fallback_query=fallback_query or user_query,
            limit=10,
            selected_data_sources=selected_data_sources,
            silver_gold_tables_only=silver_gold_tables_only,
            planner_output=state.get("calculation_plan"),
            original_query=user_query,
        )

        state["csod_resolved_schemas"] = schema_data.get("schemas", [])

        # Apply column pruning if needed
        if state["csod_resolved_schemas"] and any(s.get("column_metadata") for s in state["csod_resolved_schemas"]):
            reasoning = state.get("csod_planner_reasoning") or state.get("reasoning")
            state["csod_resolved_schemas"] = prune_columns_from_schemas(
                schemas=state["csod_resolved_schemas"],
                user_query=user_query,
                reasoning=reasoning
            )

        # Gold standard tables lookup
        gold_tables: List[Dict[str, Any]] = []
        if project_id:
            gold_tables = csod_retrieve_gold_standard_tables(
                project_id=project_id,
                categories=focus_area_categories or None,
            )
        state["csod_gold_standard_tables"] = gold_tables

        # Store in context_cache
        state["context_cache"] = state.get("context_cache", {})
        state["context_cache"]["schema_resolution"] = {
            "schemas": state["csod_resolved_schemas"],
            "table_descriptions": schema_data.get("table_descriptions", []),
            "query": fallback_query,
            "data_sources": selected_data_sources,
            "focus_areas": focus_area_categories,
        }

        _csod_log_step(
            state, "csod_mdl_schema_retrieval", "csod_mdl_schema_retrieval",
            inputs={
                "schema_names_requested": schema_names,
                "project_id": project_id,
            },
            outputs={
                "schemas_found": len(state["csod_resolved_schemas"]),
                "gold_tables_found": len(gold_tables),
            },
        )

        state["messages"].append(AIMessage(
            content=(
                f"CSOD MDL schema retrieval: {len(state['csod_resolved_schemas'])} schemas, "
                f"{len(gold_tables)} gold tables"
            )
        ))

    except Exception as e:
        logger.error(f"csod_mdl_schema_retrieval_node failed: {e}", exc_info=True)
        state["error"] = f"CSOD MDL schema retrieval failed: {str(e)}"
        state.setdefault("csod_resolved_schemas", [])
        state.setdefault("csod_gold_standard_tables", [])

    return state


# ============================================================================
# 4. Metrics Retrieval Node
# ============================================================================

def csod_metrics_retrieval_node(state: CSOD_State) -> CSOD_State:
    """
    Retrieves metrics from leen_metrics_registry for CSOD workflow.
    Similar to DT metrics retrieval but focused on CSOD use cases.
    """
    try:
        from app.retrieval.mdl_service import MDLRetrievalService

        data_enrichment = state.get("data_enrichment", {})
        metrics_intent = data_enrichment.get("metrics_intent", "current_state")
        focus_areas = data_enrichment.get("suggested_focus_areas", [])
        data_sources_in_scope = state.get("csod_data_sources_in_scope", []) or state.get("selected_data_sources", [])

        # Map focus areas to metric categories (CSOD-specific)
        FOCUS_AREA_CATEGORY_MAP: Dict[str, List[str]] = {
            "learning_management": ["learning", "training", "courses"],
            "talent_management": ["talent", "performance", "succession"],
            "recruitment": ["recruitment", "hiring", "applicants"],
            "onboarding": ["onboarding", "orientation", "new_hire"],
            "compliance_training": ["compliance", "training", "certifications"],
            "skill_development": ["skills", "competencies", "development"],
        }

        focus_area_categories: List[str] = []
        for fa in focus_areas:
            for cat in FOCUS_AREA_CATEGORY_MAP.get(fa, [fa]):
                if cat not in focus_area_categories:
                    focus_area_categories.append(cat)

        state["focus_area_categories"] = focus_area_categories

        search_query = " ".join(focus_area_categories) if focus_area_categories else "csod metrics learning talent"

        mdl_service = MDLRetrievalService(workflow_type="csod")
        metrics_results = run_async(mdl_service.search_metrics_registry(query=search_query, limit=50))

        resolved_metrics: List[Dict[str, Any]] = []
        for metric_result in metrics_results:
            metadata = metric_result.metadata if hasattr(metric_result, "metadata") and metric_result.metadata else {}

            source_capabilities = metadata.get("source_capabilities", [])
            if not isinstance(source_capabilities, list):
                source_capabilities = []

            # Source match score
            source_match = 0.0
            if data_sources_in_scope and source_capabilities:
                source_patterns = [p.replace(".*", "") for p in [f"{ds.split('.')[0].lower()}.*" for ds in data_sources_in_scope]]
                for pat_prefix in source_patterns:
                    if any(isinstance(c, str) and c.startswith(pat_prefix) for c in source_capabilities):
                        source_match = 1.0
                        break
            elif not data_sources_in_scope:
                source_match = 0.5

            # Category match score
            metric_category = metadata.get("category", "")
            cat_match = 0.0
            if not focus_area_categories:
                cat_match = 0.5
            elif not metric_category:
                cat_match = 0.3
            elif metric_category in focus_area_categories:
                cat_match = 1.0
            else:
                for cat in focus_area_categories:
                    if cat in metric_category or metric_category in cat:
                        cat_match = 0.8
                        break
                if cat_match == 0.0:
                    cat_match = 0.2

            def _get_field(key: str, default: Any = None) -> Any:
                if key in metadata:
                    return metadata[key]
                if hasattr(metric_result, "content") and isinstance(metric_result.content, dict):
                    if key in metric_result.content:
                        return metric_result.content[key]
                if hasattr(metric_result, key):
                    return getattr(metric_result, key)
                return default

            base_score = metric_result.score if hasattr(metric_result, "score") else 0.0
            combined_score = base_score + (source_match * 0.1) + (cat_match * 0.1)

            resolved_metrics.append({
                "metric_id": _get_field("metric_id") or _get_field("id", "") or getattr(metric_result, "id", ""),
                "name": _get_field("name") or getattr(metric_result, "metric_name", ""),
                "description": _get_field("description") or getattr(metric_result, "metric_definition", ""),
                "category": metric_category,
                "source_capabilities": source_capabilities,
                "source_schemas": _get_field("source_schemas", []),
                "kpis": _get_field("kpis", []),
                "trends": _get_field("trends", []),
                "natural_language_question": _get_field("natural_language_question", ""),
                "data_filters": _get_field("data_filters", []),
                "data_groups": _get_field("data_groups", []),
                "score": combined_score,
            })

        resolved_metrics.sort(key=lambda m: m.get("score", 0.0), reverse=True)
        resolved_metrics = resolved_metrics[:20]

        state["resolved_metrics"] = resolved_metrics
        state["csod_retrieved_metrics"] = resolved_metrics

        # ── Enrich metrics with decision tree logic ────────────────────
        # This enriches metrics with decision tree scoring and grouping
        # Can be disabled by setting csod_use_decision_tree=False in state
        use_decision_tree = state.get("csod_use_decision_tree", True)
        if use_decision_tree and resolved_metrics:
            try:
                from app.agents.decision_trees.dt_metric_decision_nodes import enrich_metrics_with_decision_tree
                state = enrich_metrics_with_decision_tree(state)
                logger.info(
                    f"csod_metrics_retrieval: Enriched {len(resolved_metrics)} metrics with decision tree. "
                    f"Groups: {len(state.get('dt_metric_groups', []))}, "
                    f"Scored: {len(state.get('dt_scored_metrics', []))}"
                )
            except Exception as e:
                logger.warning(f"csod_metrics_retrieval: Decision tree enrichment failed: {e}", exc_info=True)
                # Continue without enrichment - don't fail the node

        _csod_log_step(
            state, "csod_metrics_retrieval", "csod_metrics_retrieval",
            inputs={
                "focus_areas": focus_areas,
                "focus_area_categories": focus_area_categories,
                "data_sources_in_scope": data_sources_in_scope,
                "decision_tree_enabled": use_decision_tree,
            },
            outputs={
                "resolved_metrics_count": len(resolved_metrics),
                "decision_tree_groups": len(state.get("dt_metric_groups", [])),
                "decision_tree_scored": len(state.get("dt_scored_metrics", [])),
            },
        )

        decision_tree_info = ""
        if use_decision_tree and state.get("dt_metric_groups"):
            groups = state.get("dt_metric_groups", [])
            group_summary = ", ".join(
                f"{g.get('group_name', 'unknown')}({g.get('total_assigned', 0)})"
                for g in groups[:3] if g.get("total_assigned", 0) > 0
            )
            decision_tree_info = f" | Decision tree: {len(groups)} groups ({group_summary})"

        state["messages"].append(AIMessage(
            content=f"CSOD Metrics retrieval: {len(resolved_metrics)} metrics resolved{decision_tree_info}"
        ))

    except Exception as e:
        logger.error(f"csod_metrics_retrieval_node failed: {e}", exc_info=True)
        state["error"] = f"CSOD metrics retrieval failed: {str(e)}"
        state.setdefault("resolved_metrics", [])
        state.setdefault("csod_retrieved_metrics", [])

    return state


# ============================================================================
# 5. Scoring Validator Node
# ============================================================================

def csod_scoring_validator_node(state: CSOD_State) -> CSOD_State:
    """
    Cross-scores all retrieved items (metrics, KPIs, schemas) against
    focus areas and intent.
    
    Similar to DT scoring validator but focused on CSOD metrics/KPIs.
    """
    try:
        data_enrichment = state.get("data_enrichment", {})
        intent = state.get("csod_intent", "")
        focus_areas = data_enrichment.get("suggested_focus_areas", [])
        focus_cats = state.get("focus_area_categories", [])
        user_query = state.get("user_query", "").lower()

        THRESHOLD = 0.50
        WARN_THRESHOLD = 0.65

        def _score_item(item: Dict, item_type: str) -> Dict:
            """Score an item based on intent and focus areas."""
            item_str = json.dumps(item).lower()
            intent_keywords = intent.replace("_", " ").split()
            query_words = [w for w in user_query.split() if len(w) > 3]
            combined = intent_keywords + query_words
            
            # Intent alignment
            matches = sum(1 for kw in combined if kw in item_str)
            intent_score = min(1.0, matches / max(len(combined), 1) * 2)
            
            # Focus area match
            focus_score = 0.5
            if focus_cats:
                for cat in focus_cats:
                    if cat.replace("_", " ") in item_str:
                        focus_score = 1.0
                        break
            
            composite = (intent_score * 0.5) + (focus_score * 0.5)
            return {
                **item,
                "composite_score": round(composite, 3),
                "low_confidence": composite < WARN_THRESHOLD,
            }

        # Score metrics
        metrics = state.get("resolved_metrics", [])
        scored_metrics = [_score_item(m, "metric") for m in metrics]
        scored_metrics = [m for m in scored_metrics if m["composite_score"] >= THRESHOLD]
        scored_metrics.sort(key=lambda m: m.get("composite_score", 0.0), reverse=True)

        # Score schemas
        schemas = state.get("csod_resolved_schemas", [])
        scored_schemas = [_score_item(s, "schema") for s in schemas]
        scored_schemas = [s for s in scored_schemas if s["composite_score"] >= THRESHOLD]

        # Build scored_context
        scored_context = {
            "scored_metrics": scored_metrics,
            "resolved_schemas": scored_schemas,
            "gold_standard_tables": state.get("csod_gold_standard_tables", []),
        }

        state["csod_scored_context"] = scored_context
        state["resolved_metrics"] = scored_metrics
        state["csod_resolved_schemas"] = scored_schemas

        _csod_log_step(
            state, "csod_scoring_validation", "csod_scoring_validator",
            inputs={
                "metrics_in": len(metrics),
                "schemas_in": len(schemas),
            },
            outputs={
                "metrics_retained": len(scored_metrics),
                "schemas_retained": len(scored_schemas),
            },
        )

        state["messages"].append(AIMessage(
            content=(
                f"CSOD Scoring: retained {len(scored_metrics)} metrics, "
                f"{len(scored_schemas)} schemas"
            )
        ))

    except Exception as e:
        logger.error(f"csod_scoring_validator_node failed: {e}", exc_info=True)
        state["error"] = f"CSOD scoring validator failed: {str(e)}"
        state["csod_scored_context"] = {
            "scored_metrics": state.get("resolved_metrics", []),
            "resolved_schemas": state.get("csod_resolved_schemas", []),
            "gold_standard_tables": state.get("csod_gold_standard_tables", []),
        }

    return state


# ============================================================================
# 6. Metrics Recommender Node
# ============================================================================

def csod_metrics_recommender_node(state: CSOD_State) -> CSOD_State:
    """
    Generates metric recommendations with optional gold plan.
    
    Uses decision tree enriched metrics to guide recommendations based on:
    - use_case (e.g., lms_learning_target, soc2_audit)
    - goal (e.g., training_completion, compliance_posture)
    - focus_area (e.g., learning_management, compliance_training)
    - audience, timeframe, metric_type
    
    Used for intents: metrics_dashboard_plan, metrics_recommender_with_gold_plan
    """
    try:
        try:
            prompt_text = load_prompt("03_metrics_recommender", prompts_dir=str(PROMPTS_CSOD))
        except FileNotFoundError:
            prompt_text = """You are a metrics recommender for CSOD workflow.
Generate metric recommendations based on the scored context and decision tree insights.
Return JSON with metric_recommendations, kpi_recommendations, table_recommendations,
and optionally medallion_plan if gold plan is requested."""

        tools = csod_get_tools_for_agent("csod_metrics_recommender", state=state, conditional=True)
        use_tool_calling = bool(tools)

        scored_context = state.get("csod_scored_context", {})
        intent = state.get("csod_intent", "")
        user_query = state.get("user_query", "")

        # ── Include decision tree context if available ────────────────────
        decision_tree_context = ""
        dt_decisions = state.get("dt_metric_decisions", {})
        dt_scored_metrics = state.get("dt_scored_metrics", [])
        dt_metric_groups = state.get("dt_metric_groups", [])
        
        if dt_decisions:
            decision_tree_context = f"""
DECISION TREE CONTEXT:
- Use Case: {dt_decisions.get('use_case', 'N/A')} (confidence: {dt_decisions.get('use_case_confidence', 0):.2f})
- Goal: {dt_decisions.get('goal', 'N/A')} (confidence: {dt_decisions.get('goal_confidence', 0):.2f})
- Focus Area: {dt_decisions.get('focus_area', 'N/A')} (confidence: {dt_decisions.get('focus_area_confidence', 0):.2f})
- Audience: {dt_decisions.get('audience', 'N/A')} (confidence: {dt_decisions.get('audience_confidence', 0):.2f})
- Timeframe: {dt_decisions.get('timeframe', 'N/A')} (confidence: {dt_decisions.get('timeframe_confidence', 0):.2f})
- Metric Type: {dt_decisions.get('metric_type', 'N/A')} (confidence: {dt_decisions.get('metric_type_confidence', 0):.2f})
- Overall Confidence: {dt_decisions.get('auto_resolve_confidence', 0):.2f}
"""
        
        if dt_scored_metrics:
            # Use decision tree scored metrics instead of raw resolved_metrics
            # These are already ranked by decision tree alignment
            top_scored = sorted(dt_scored_metrics, key=lambda m: m.get("composite_score", 0), reverse=True)[:15]
            decision_tree_context += f"""
DECISION TREE SCORED METRICS (top {len(top_scored)} by composite score):
{json.dumps([{
    "metric_id": m.get("metric_id") or m.get("id", ""),
    "name": m.get("name", ""),
    "composite_score": m.get("composite_score", 0),
    "score_breakdown": m.get("score_breakdown", {}),
    "goals": m.get("goals", []),
    "use_cases": m.get("use_cases", []),
    "focus_areas": m.get("focus_areas", []),
} for m in top_scored], indent=2)}
"""
        
        if dt_metric_groups:
            decision_tree_context += f"""
DECISION TREE METRIC GROUPS ({len(dt_metric_groups)} groups):
{json.dumps([{
    "group_name": g.get("group_name", ""),
    "goal": g.get("goal", ""),
    "total_assigned": g.get("total_assigned", 0),
    "top_metrics": [m.get("metric_id") or m.get("id", "") for m in g.get("metrics", [])[:5]],
} for g in dt_metric_groups], indent=2)}
"""

        context_str = csod_format_scored_context_for_prompt(
            scored_context,
            include_schemas=True,
            include_metrics=True,
            include_kpis=True,
        )

        human_message = f"""User Query: {user_query}
Intent: {intent}
{decision_tree_context}
SCORED CONTEXT:
{context_str}

Generate metric recommendations following your instructions.
Use the decision tree context to prioritize metrics that align with the resolved use_case, goal, and focus_area.
Prioritize metrics from the decision tree scored metrics list when available.
Note: Medallion plan will be generated separately by csod_medallion_planner_node.
Note: Data science insights will be generated separately by csod_data_science_insights_enricher node.

Return JSON with metric_recommendations, kpi_recommendations, and table_recommendations only."""

        response_content = _llm_invoke(
            state, "csod_metrics_recommender", prompt_text, human_message,
            tools, use_tool_calling, max_tool_iterations=10,
        )

        result = _parse_json_response(response_content, {})

        state["csod_metric_recommendations"] = result.get("metric_recommendations", [])
        state["csod_kpi_recommendations"] = result.get("kpi_recommendations", [])
        state["csod_table_recommendations"] = result.get("table_recommendations", [])
        
        # Note: medallion_plan is now generated by a separate csod_medallion_planner_node
        # Note: data_science_insights are now generated by a separate csod_data_science_insights_enricher node
        # Do not generate them here

        _csod_log_step(
            state, "csod_metrics_recommendation", "csod_metrics_recommender",
            inputs={
                "intent": intent,
                "scored_metrics_count": len(scored_context.get("scored_metrics", [])),
                "decision_tree_enabled": bool(dt_decisions),
                "decision_tree_use_case": dt_decisions.get("use_case", ""),
                "decision_tree_goal": dt_decisions.get("goal", ""),
            },
            outputs={
                "metric_recommendations_count": len(state["csod_metric_recommendations"]),
                "kpi_recommendations_count": len(state["csod_kpi_recommendations"]),
                "table_recommendations_count": len(state["csod_table_recommendations"]),
                "decision_tree_groups_used": len(dt_metric_groups),
            },
        )

        state["messages"].append(AIMessage(
            content=(
                f"CSOD Metrics recommender: {len(state['csod_metric_recommendations'])} metrics, "
                f"{len(state['csod_kpi_recommendations'])} KPIs"
            )
        ))

    except Exception as e:
        logger.error(f"csod_metrics_recommender_node failed: {e}", exc_info=True)
        state["error"] = f"CSOD metrics recommender failed: {str(e)}"
        state.setdefault("csod_metric_recommendations", [])
        state.setdefault("csod_kpi_recommendations", [])

    return state


# ============================================================================
# 7. Medallion Planner Node
# ============================================================================

def csod_medallion_planner_node(state: CSOD_State) -> CSOD_State:
    """
    Generates medallion architecture plan (bronze → silver → gold) using GoldModelPlanGenerator.
    
    This node runs after metrics_recommender and before dashboard/compliance test generation.
    It uses the GoldModelPlanGenerator pattern to create structured gold model specifications.
    
    Used when intent is metrics_recommender_with_gold_plan or when metrics require gold models.
    """
    try:
        from app.agents.shared.gold_model_plan_generator import (
            GoldModelPlanGenerator,
            GoldModelPlanGeneratorInput,
            SilverTableInfo,
        )
        
        metric_recommendations = state.get("csod_metric_recommendations", [])
        kpi_recommendations = state.get("csod_kpi_recommendations", [])
        resolved_schemas = state.get("csod_resolved_schemas", [])
        intent = state.get("csod_intent", "")
        user_query = state.get("user_query", "")
        silver_gold_only = state.get("silver_gold_tables_only", False)
        
        # Determine if gold plan is needed
        needs_gold_plan = (
            intent == "metrics_recommender_with_gold_plan" or
            (metric_recommendations and len(metric_recommendations) > 0)
        )
        
        if not needs_gold_plan or not metric_recommendations or not resolved_schemas:
            logger.info(
                f"csod_medallion_planner: Skipping - needs_gold_plan={needs_gold_plan}, "
                f"metrics={len(metric_recommendations)}, schemas={len(resolved_schemas)}"
            )
            # Set empty plan
            state["csod_medallion_plan"] = {
                "requires_gold_model": False,
                "reasoning": "No metrics or schemas available, or gold plan not requested",
                "specifications": [],
            }
            return state
        
        # Convert resolved_schemas to SilverTableInfo format
        silver_tables_info = []
        for schema in resolved_schemas:
            if isinstance(schema, dict):
                table_name = schema.get("table_name") or schema.get("name", "")
                if not table_name:
                    continue
                
                # Extract reasoning from schema metadata
                reason_parts = []
                
                # Use schema description if available
                schema_desc = schema.get("description", "")
                if schema_desc:
                    desc_snippet = schema_desc.split('.')[0] if '.' in schema_desc else schema_desc[:100]
                    reason_parts.append(desc_snippet)
                
                # Check if it's a gold standard table
                if schema.get("is_gold_standard"):
                    category = schema.get("category", "")
                    grain = schema.get("grain", "")
                    gs_info = "Gold standard table"
                    if category:
                        gs_info += f" (category: {category})"
                    if grain:
                        gs_info += f" (grain: {grain})"
                    reason_parts.append(gs_info)
                
                # Fallback reason
                if not reason_parts:
                    reason_parts.append("From MDL schema retrieval")
                
                reason = ". ".join(reason_parts)
                
                # Extract relevant columns reasoning
                relevant_columns_reasoning = schema.get("column_reasoning") or schema.get("relevant_columns_reasoning")
                if not relevant_columns_reasoning:
                    relevant_columns_reasoning = "Columns from MDL schema"
                
                silver_tables_info.append(
                    SilverTableInfo(
                        table_name=table_name,
                        reason=reason,
                        schema_info=schema,
                        relevant_columns=[],
                        relevant_columns_reasoning=relevant_columns_reasoning,
                    )
                )
        
        if not silver_tables_info:
            logger.warning("csod_medallion_planner: No silver tables info available")
            state["csod_medallion_plan"] = {
                "requires_gold_model": False,
                "reasoning": "No silver tables available for gold model planning",
                "specifications": [],
            }
            return state
        
        # Initialize generator
        generator = GoldModelPlanGenerator(temperature=0.3)
        
        # Prepare input
        input_data = GoldModelPlanGeneratorInput(
            metrics=metric_recommendations,
            silver_tables_info=silver_tables_info,
            user_request=user_query,
            kpis=kpi_recommendations,
            medallion_context={
                "silver_tables": [t.table_name for t in silver_tables_info],
                "gold_tables": [],  # To be created
            } if silver_gold_only else None,
        )
        
        # Generate gold model plan
        gold_model_plan = run_async(generator.generate(input_data))
        
        # Store in state - ensure it's a dict, not a Pydantic model
        plan_dict = gold_model_plan.model_dump() if hasattr(gold_model_plan, 'model_dump') else dict(gold_model_plan)
        
        # Filter mapped_metrics to only include metrics that exist in csod_metric_recommendations
        # This ensures we don't reference metrics that were filtered out or don't exist
        actual_metric_ids = {m.get("id", "") for m in metric_recommendations if isinstance(m, dict) and m.get("id")}
        if actual_metric_ids:
            filtered_specs = []
            for spec in plan_dict.get("specifications", []) or []:
                if isinstance(spec, dict):
                    filtered_expected_columns = []
                    for col in spec.get("expected_columns", []) or []:
                        if isinstance(col, dict):
                            mapped_metrics = col.get("mapped_metrics", []) or []
                            # Filter to only include metrics that exist in actual recommendations
                            filtered_mapped = [
                                m for m in mapped_metrics
                                if m in actual_metric_ids
                            ]
                            col_copy = col.copy()
                            col_copy["mapped_metrics"] = filtered_mapped
                            filtered_expected_columns.append(col_copy)
                        else:
                            filtered_expected_columns.append(col)
                    spec_copy = spec.copy()
                    spec_copy["expected_columns"] = filtered_expected_columns
                    filtered_specs.append(spec_copy)
                else:
                    filtered_specs.append(spec)
            plan_dict["specifications"] = filtered_specs
            logger.info(
                f"csod_medallion_planner: Filtered mapped_metrics to only include "
                f"{len(actual_metric_ids)} actual metric recommendations"
            )
        
        state["csod_medallion_plan"] = plan_dict
        
        _csod_log_step(
            state, "csod_medallion_planning", "csod_medallion_planner",
            inputs={
                "metrics_count": len(metric_recommendations),
                "silver_tables_count": len(silver_tables_info),
                "intent": intent,
            },
            outputs={
                "requires_gold_model": plan_dict.get("requires_gold_model", False),
                "specifications_count": len(plan_dict.get("specifications", []) or []),
            },
        )
        
        # SQL generation is handled by csod_gold_model_sql_generator_node (runs after this node)
        
        state["messages"].append(AIMessage(
            content=(
                f"CSOD Medallion planner: requires_gold_model={plan_dict.get('requires_gold_model', False)}, "
                f"{len(plan_dict.get('specifications', []) or [])} specifications"
            )
        ))
        
        logger.info(
            f"csod_medallion_planner: Generated gold model plan with "
            f"{len(plan_dict.get('specifications', []) or [])} specifications"
        )
        
    except Exception as e:
        logger.error(f"csod_medallion_planner_node failed: {e}", exc_info=True)
        state["error"] = f"CSOD medallion planner failed: {str(e)}"
        state["csod_medallion_plan"] = {
            "requires_gold_model": False,
            "reasoning": f"Error generating plan: {str(e)}",
            "specifications": [],
        }
    
    return state


# ============================================================================
# 7b. Gold Model SQL Generator Node (dbt)
# ============================================================================

def csod_gold_model_sql_generator_node(state: CSOD_State) -> CSOD_State:
    """
    Generates dbt-compatible SQL for gold models from csod_medallion_plan.
    
    Uses GoldModelSQLGenerator (shared with DT workflow).
    Runs after csod_medallion_planner when csod_generate_sql=True and plan requires gold models.
    """
    try:
        plan_dict = state.get("csod_medallion_plan", {})
        requires_gold = plan_dict.get("requires_gold_model", False)
        csod_generate_sql = state.get("csod_generate_sql", False)
        
        if not csod_generate_sql or not requires_gold or not plan_dict.get("specifications"):
            logger.info(
                f"csod_gold_model_sql_generator: Skipping - generate_sql={csod_generate_sql}, "
                f"requires_gold={requires_gold}, specs={len(plan_dict.get('specifications', []) or [])}"
            )
            state["csod_generated_gold_model_sql"] = []
            state["csod_gold_model_artifact_name"] = None
            return state
        
        from app.agents.shared.gold_model_sql_generator import GoldModelSQLGenerator
        from app.agents.shared.gold_model_plan_generator import GoldModelPlan
        
        gold_model_plan = GoldModelPlan.model_validate(plan_dict)
        resolved_schemas = state.get("csod_resolved_schemas", [])
        silver_tables_info = [s for s in resolved_schemas if isinstance(s, dict)]
        
        sql_generator = GoldModelSQLGenerator(temperature=0.0, max_tokens=4096)
        sql_response = run_async(
            sql_generator.generate(
                gold_model_plan=gold_model_plan,
                silver_tables_info=silver_tables_info,
                examples=None,
            )
        )
        
        state["csod_generated_gold_model_sql"] = [
            {
                "name": model.name,
                "sql_query": model.sql_query,
                "description": model.description,
                "materialization": model.materialization,
                "expected_columns": model.expected_columns or [],
            }
            for model in sql_response.models
        ]
        state["csod_gold_model_artifact_name"] = sql_response.artifact_name
        
        _csod_log_step(
            state, "csod_gold_model_sql_generation", "csod_gold_model_sql_generator",
            inputs={"plan_specs": len(plan_dict.get("specifications", []))},
            outputs={
                "models_generated": len(sql_response.models),
                "artifact_name": sql_response.artifact_name,
            },
        )
        
        logger.info(
            f"csod_gold_model_sql_generator: Generated SQL for {len(sql_response.models)} gold models"
        )
        state["messages"].append(AIMessage(
            content=f"CSOD Gold Model SQL: Generated {len(sql_response.models)} dbt models"
        ))
        
    except Exception as e:
        logger.exception(f"csod_gold_model_sql_generator_node failed: {e}")
        state["csod_generated_gold_model_sql"] = []
        state["csod_gold_model_artifact_name"] = None
        state["error"] = f"CSOD gold model SQL generation failed: {str(e)}"
    
    return state


# ============================================================================
# 8. Dashboard Generator Node
# ============================================================================

def csod_dashboard_generator_node(state: CSOD_State) -> CSOD_State:
    """
    Generates dashboard for a specific persona.
    
    Used for intent: dashboard_generation_for_persona
    Similar to DT dashboard generation but persona-focused.
    """
    try:
        try:
            prompt_text = load_prompt("04_dashboard_generator", prompts_dir=str(PROMPTS_CSOD))
        except FileNotFoundError:
            prompt_text = """You are a dashboard generator for CSOD workflow.
Generate a dashboard specification for the specified persona.
Return JSON with dashboard structure, components, and metadata."""

        tools = csod_get_tools_for_agent("csod_dashboard_generator", state=state, conditional=True)
        use_tool_calling = bool(tools)

        persona = state.get("csod_persona", "")
        scored_context = state.get("csod_scored_context", {})
        user_query = state.get("user_query", "")

        context_str = csod_format_scored_context_for_prompt(
            scored_context,
            include_schemas=True,
            include_metrics=True,
            include_kpis=True,
        )

        human_message = f"""User Query: {user_query}
Persona: {persona}

SCORED CONTEXT:
{context_str}

Generate dashboard for persona following your instructions.
IMPORTANT:
- Source data_table_definition from resolved_schemas (include table_name, description, column_metadata, table_ddl)
- Recommend chart_type based on table structure analysis (columns, types, grain)
- Include chart_type_reasoning explaining why each chart type was recommended
- Do NOT include 'data' field in components (data will be sourced at runtime)
- metric_id is optional but recommended when metrics are available
Return JSON only."""

        response_content = _llm_invoke(
            state, "csod_dashboard_generator", prompt_text, human_message,
            tools, use_tool_calling, max_tool_iterations=10,
        )

        result = _parse_json_response(response_content, {})

        dashboard_obj = result.get("dashboard", {})
        if not dashboard_obj.get("dashboard_id"):
            dashboard_obj["dashboard_id"] = str(uuid.uuid4())
        if not dashboard_obj.get("created_at"):
            dashboard_obj["created_at"] = datetime.utcnow().isoformat()
        
        dashboard_obj["metadata"] = {
            "source_query": user_query,
            "persona": persona,
            "generated_at": datetime.utcnow().isoformat(),
            "workflow_id": state.get("session_id", ""),
        }

        state["csod_dashboard_assembled"] = dashboard_obj

        _csod_log_step(
            state, "csod_dashboard_generation", "csod_dashboard_generator",
            inputs={"persona": persona, "scored_metrics_count": len(scored_context.get("scored_metrics", []))},
            outputs={
                "dashboard_id": dashboard_obj.get("dashboard_id"),
                "component_count": dashboard_obj.get("total_components", 0),
            },
        )

        state["messages"].append(AIMessage(
            content=(
                f"CSOD Dashboard generated for persona '{persona}': "
                f"{dashboard_obj.get('total_components', 0)} components"
            )
        ))

    except Exception as e:
        logger.error(f"csod_dashboard_generator_node failed: {e}", exc_info=True)
        state["error"] = f"CSOD dashboard generator failed: {str(e)}"
        state.setdefault("csod_dashboard_assembled", None)

    return state


# ============================================================================
# 9. Compliance Test Generator Node
# ============================================================================

def csod_compliance_test_generator_node(state: CSOD_State) -> CSOD_State:
    """
    Generates compliance test cases with SQL queries for alerts.
    
    Used for intent: compliance_test_generator
    """
    try:
        try:
            prompt_text = load_prompt("05_compliance_test_generator", prompts_dir=str(PROMPTS_CSOD))
        except FileNotFoundError:
            prompt_text = """You are a compliance test generator for CSOD workflow.
Generate SQL-based test cases and alert queries.
Return JSON with test_cases (with SQL queries) and test_queries."""

        tools = csod_get_tools_for_agent("csod_compliance_test_generator", state=state, conditional=True)
        use_tool_calling = bool(tools)

        scored_context = state.get("csod_scored_context", {})
        user_query = state.get("user_query", "")
        schemas = scored_context.get("resolved_schemas", [])

        # Build schema DDL for SQL generation
        schema_ddl = build_schema_ddl(schemas) if schemas else "No schemas available."

        human_message = f"""User Query: {user_query}

AVAILABLE SCHEMAS:
{schema_ddl}

Generate compliance test cases with SQL queries following your instructions.
Return JSON only."""

        response_content = _llm_invoke(
            state, "csod_compliance_test_generator", prompt_text, human_message,
            tools, use_tool_calling, max_tool_iterations=10,
        )

        result = _parse_json_response(response_content, {})

        state["csod_test_cases"] = result.get("test_cases", [])
        state["csod_test_queries"] = result.get("test_queries", [])

        # Validate test queries (basic SQL syntax check)
        validation_failures = []
        for test_case in state["csod_test_cases"]:
            query = test_case.get("sql_query", "")
            if query and not _validate_sql_query(query):
                validation_failures.append({
                    "test_case_id": test_case.get("test_case_id", "?"),
                    "error": "Invalid SQL query syntax",
                })

        state["csod_test_validation_passed"] = len(validation_failures) == 0
        state["csod_test_validation_failures"] = validation_failures

        _csod_log_step(
            state, "csod_compliance_test_generation", "csod_compliance_test_generator",
            inputs={"schemas_count": len(schemas)},
            outputs={
                "test_cases_count": len(state["csod_test_cases"]),
                "test_queries_count": len(state["csod_test_queries"]),
                "validation_passed": state["csod_test_validation_passed"],
            },
        )

        state["messages"].append(AIMessage(
            content=(
                f"CSOD Compliance test generator: {len(state['csod_test_cases'])} test cases, "
                f"{len(state['csod_test_queries'])} queries, "
                f"validation={'PASSED' if state['csod_test_validation_passed'] else 'FAILED'}"
            )
        ))

    except Exception as e:
        logger.error(f"csod_compliance_test_generator_node failed: {e}", exc_info=True)
        state["error"] = f"CSOD compliance test generator failed: {str(e)}"
        state.setdefault("csod_test_cases", [])
        state.setdefault("csod_test_queries", [])
        state["csod_test_validation_passed"] = False

    return state


def _validate_sql_query(query: str) -> bool:
    """Basic SQL query validation (placeholder - can be enhanced)."""
    if not query or not isinstance(query, str):
        return False
    query_lower = query.lower().strip()
    # Basic checks
    if not any(keyword in query_lower for keyword in ["select", "insert", "update", "delete", "create"]):
        return False
    return True


# ============================================================================
# 9. Scheduler Node
# ============================================================================

def csod_scheduler_node(state: CSOD_State) -> CSOD_State:
    """
    Plans scheduling or adhoc execution for the generated outputs.
    
    Determines schedule_type (adhoc, scheduled, recurring) and execution frequency.
    """
    try:
        try:
            prompt_text = load_prompt("06_scheduler", prompts_dir=str(PROMPTS_CSOD))
        except FileNotFoundError:
            prompt_text = """You are a scheduler for CSOD workflow.
Determine the appropriate schedule type and configuration.
Return JSON with schedule_type, schedule_config, execution_frequency."""

        tools = csod_get_tools_for_agent("csod_scheduler", state=state, conditional=True)
        use_tool_calling = bool(tools)

        user_query = state.get("user_query", "")
        intent = state.get("csod_intent", "")

        human_message = f"""User Query: {user_query}
Intent: {intent}

Determine scheduling configuration.
Return JSON only."""

        response_content = _llm_invoke(
            state, "csod_scheduler", prompt_text, human_message,
            tools, use_tool_calling, max_tool_iterations=3,
        )

        result = _parse_json_response(response_content, {})

        state["csod_schedule_type"] = result.get("schedule_type", "adhoc")
        state["csod_schedule_config"] = result.get("schedule_config", {})
        state["csod_execution_frequency"] = result.get("execution_frequency", "on_demand")

        _csod_log_step(
            state, "csod_scheduling", "csod_scheduler",
            inputs={"intent": intent},
            outputs={
                "schedule_type": state["csod_schedule_type"],
                "execution_frequency": state["csod_execution_frequency"],
            },
        )

        state["messages"].append(AIMessage(
            content=(
                f"CSOD Scheduler: {state['csod_schedule_type']} schedule, "
                f"frequency={state['csod_execution_frequency']}"
            )
        ))

    except Exception as e:
        logger.error(f"csod_scheduler_node failed: {e}", exc_info=True)
        state["error"] = f"CSOD scheduler failed: {str(e)}"
        state.setdefault("csod_schedule_type", "adhoc")
        state.setdefault("csod_execution_frequency", "on_demand")

    return state


# ============================================================================
# 10. Output Assembler Node
# ============================================================================

def csod_output_assembler_node(state: CSOD_State) -> CSOD_State:
    """
    Assembles final output based on intent and generated artifacts.
    """
    try:
        try:
            prompt_text = load_prompt("07_output_assembler", prompts_dir=str(PROMPTS_CSOD))
        except FileNotFoundError:
            prompt_text = """You are an output assembler for CSOD workflow.
Assemble the final output structure based on intent and generated artifacts.
Return JSON with assembled_output."""

        tools = csod_get_tools_for_agent("csod_output_assembler", state=state, conditional=True)
        use_tool_calling = bool(tools)

        intent = state.get("csod_intent", "")
        user_query = state.get("user_query", "")

        # Collect all generated artifacts
        artifacts = {
            "metric_recommendations": state.get("csod_metric_recommendations", []),
            "kpi_recommendations": state.get("csod_kpi_recommendations", []),
            "table_recommendations": state.get("csod_table_recommendations", []),
            "data_science_insights": state.get("csod_data_science_insights", []),
            "medallion_plan": state.get("csod_medallion_plan", {}),
            "dashboard": state.get("csod_dashboard_assembled", {}),
            "test_cases": state.get("csod_test_cases", []),
            "test_queries": state.get("csod_test_queries", []),
            "schedule_config": state.get("csod_schedule_config", {}),
            "gold_model_sql": state.get("csod_generated_gold_model_sql", []),
            "cubejs_schema_files": state.get("cubejs_schema_files", []),
        }

        human_message = f"""User Query: {user_query}
Intent: {intent}

GENERATED ARTIFACTS:
{json.dumps(artifacts, indent=2)}

Assemble the final output structure following your instructions.
Return JSON only."""

        response_content = _llm_invoke(
            state, "csod_output_assembler", prompt_text, human_message,
            tools, use_tool_calling, max_tool_iterations=5,
        )

        result = _parse_json_response(response_content, {})

        state["csod_assembled_output"] = result.get("assembled_output", artifacts)

        _csod_log_step(
            state, "csod_output_assembly", "csod_output_assembler",
            inputs={"intent": intent},
            outputs={
                "output_keys": list(state["csod_assembled_output"].keys()) if isinstance(state["csod_assembled_output"], dict) else [],
            },
        )

        state["messages"].append(AIMessage(
            content=f"CSOD Output assembled for intent: {intent}"
        ))

    except Exception as e:
        logger.error(f"csod_output_assembler_node failed: {e}", exc_info=True)
        state["error"] = f"CSOD output assembler failed: {str(e)}"
        # Fallback: assemble basic structure
        state["csod_assembled_output"] = {
            "intent": state.get("csod_intent", ""),
            "metric_recommendations": state.get("csod_metric_recommendations", []),
            "kpi_recommendations": state.get("csod_kpi_recommendations", []),
            "data_science_insights": state.get("csod_data_science_insights", []),
            "dashboard": state.get("csod_dashboard_assembled", {}),
            "test_cases": state.get("csod_test_cases", []),
        }

    return state

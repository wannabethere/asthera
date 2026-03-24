"""Dashboard generator."""
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

def csod_dashboard_generator_node(state: CSOD_State) -> CSOD_State:
    """
    Generates dashboard for a specific persona.
    
    Used for intent: dashboard_generation_for_persona
    Similar to DT dashboard generation but persona-focused.
    """
    try:
        try:
            prompt_text = load_prompt("04_dashboard_generator", prompts_dir=str(PROMPTS_CSOD))
        except FileNotFoundError as e:
            logger.error(f"CSOD dashboard generator prompt file not found: {e}")
            raise FileNotFoundError(
                f"CSOD dashboard generator prompt file not found. "
                f"Expected file: {PROMPTS_CSOD / '04_dashboard_generator.md'}. "
                f"Please ensure the prompt file exists."
            )

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

        layout = state.get("csod_dt_layout") or {}
        layout_block = (
            f"\nDASHBOARD_LAYOUT_FROM_RESOLVER (use these sections/widgets when non-empty):\n{json.dumps(layout, indent=2)[:8000]}\n"
            if layout
            else ""
        )

        human_message = f"""User Query: {user_query}
Persona: {persona}

SCORED CONTEXT:
{context_str}
{layout_block}
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

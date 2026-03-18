"""Scheduler + SQL validation helper."""
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
        except FileNotFoundError as e:
            logger.error(f"CSOD scheduler prompt file not found: {e}")
            raise FileNotFoundError(
                f"CSOD scheduler prompt file not found. "
                f"Expected file: {PROMPTS_CSOD / '06_scheduler.md'}. "
                f"Please ensure the prompt file exists."
            )

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

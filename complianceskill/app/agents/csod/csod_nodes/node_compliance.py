"""Compliance test generator."""
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

def csod_compliance_test_generator_node(state: CSOD_State) -> CSOD_State:
    """
    Generates compliance test cases with SQL queries for alerts.
    
    Used for intent: compliance_test_generator
    """
    try:
        try:
            prompt_text = load_prompt("05_compliance_test_generator", prompts_dir=str(PROMPTS_CSOD))
        except FileNotFoundError as e:
            logger.error(f"CSOD compliance test generator prompt file not found: {e}")
            raise FileNotFoundError(
                f"CSOD compliance test generator prompt file not found. "
                f"Expected file: {PROMPTS_CSOD / '05_compliance_test_generator.md'}. "
                f"Please ensure the prompt file exists."
            )

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

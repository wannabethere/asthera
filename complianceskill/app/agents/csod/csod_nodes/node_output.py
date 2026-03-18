"""Final output assembler."""
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

def csod_output_assembler_node(state: CSOD_State) -> CSOD_State:
    """
    Assembles final output based on intent and generated artifacts.
    """
    try:
        try:
            prompt_text = load_prompt("07_output_assembler", prompts_dir=str(PROMPTS_CSOD))
        except FileNotFoundError as e:
            logger.error(f"CSOD output assembler prompt file not found: {e}")
            raise FileNotFoundError(
                f"CSOD output assembler prompt file not found. "
                f"Expected file: {PROMPTS_CSOD / '07_output_assembler.md'}. "
                f"Please ensure the prompt file exists."
            )

        tools = csod_get_tools_for_agent("csod_output_assembler", state=state, conditional=True)
        use_tool_calling = bool(tools)

        intent = state.get("csod_intent", "")
        user_query = state.get("user_query", "")

        # Collect all generated artifacts (including data intelligence per prompts_data_intelligence_design)
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
            "schema_catalog": state.get("csod_schema_catalog", []),
            "available_metrics_list": state.get("csod_available_metrics_list", []),
            "data_capability_assessment": state.get("csod_data_capability_assessment"),
            "coverage_gaps": state.get("csod_coverage_gaps", []),
            "lineage_graph": state.get("csod_lineage_graph"),
            "column_level_lineage": state.get("csod_column_level_lineage"),
            "transformation_steps": state.get("csod_transformation_steps", []),
            "impact_analysis": state.get("csod_impact_analysis", []),
            "quality_scorecard": state.get("csod_quality_scorecard"),
            "issue_list": state.get("csod_issue_list", []),
            "freshness_report": state.get("csod_freshness_report"),
            "ingestion_schedule": state.get("csod_ingestion_schedule", []),
            "dbt_model_specs": state.get("csod_dbt_model_specs", []),
            "dependency_dag": state.get("csod_dependency_dag", []),
            "build_complexity": state.get("csod_build_complexity"),
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

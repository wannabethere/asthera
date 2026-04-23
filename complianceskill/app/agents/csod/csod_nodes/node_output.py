"""Final output assembler."""
import json

from langchain_core.messages import AIMessage

from app.agents.prompt_loader import load_prompt, PROMPTS_CSOD
from app.agents.csod.csod_tool_integration import csod_get_tools_for_agent
from app.agents.shared.unified_output_pre_assembly import (
    apply_unified_output_pre_assembly,
)
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
        apply_unified_output_pre_assembly(state, "csod")

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
        cp = state.get("compliance_profile") if isinstance(state.get("compliance_profile"), dict) else {}
        artifacts = {
            "goal_intent": state.get("goal_intent"),
            "goal_output_intents": state.get("goal_output_intents") or [],
            "goal_pipeline_flags": cp.get("goal_pipeline_flags"),
            "goal_deliverables": cp.get("goal_deliverables"),
            "assembler_goal_actions": state.get("csod_assembler_goal_actions") or [],
            "calculation_plan": state.get("calculation_plan"),
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
            "demo_sql_agent_context": state.get("csod_demo_sql_agent_context"),
            "demo_sql_result_sets": state.get("csod_demo_sql_result_sets") or [],
            "demo_sql_insights_synthetic": state.get("csod_demo_sql_insights_synthetic"),
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
            "augmented_metrics": state.get("csod_augmented_metrics") or [],
            "is_augment_response": bool(state.get("csod_augmented_metrics")),
            "followup_analysis": state.get("csod_followup_analysis_result"),
            "narrative_stream": state.get("csod_narrative_stream", []),
            "dt_layout": state.get("csod_dt_layout"),
            "metrics_layout": state.get("csod_metrics_layout"),
            "unified_pre_assembly_actions": state.get("unified_pre_assembly_actions") or [],
            "shared_per_metric_demo_artifacts": state.get("shared_per_metric_demo_artifacts")
            or [],
            "shared_per_metric_artifact_stubs": state.get("shared_per_metric_artifact_stubs")
            or [],
            "dt_generated_gold_model_sql": state.get("dt_generated_gold_model_sql") or [],
            "dt_data_science_insights": state.get("dt_data_science_insights") or [],
            "selected_layout": state.get("csod_selected_layout"),
            "question_rephraser": state.get("csod_question_rephraser_output"),
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

        assembled = result.get("assembled_output", artifacts)
        if not isinstance(assembled, dict):
            assembled = {"assembled_payload": assembled}
        for _gk in (
            "goal_intent",
            "goal_output_intents",
            "goal_pipeline_flags",
            "goal_deliverables",
            "assembler_goal_actions",
            "calculation_plan",
        ):
            if _gk in artifacts:
                assembled.setdefault(_gk, artifacts[_gk])
        state["csod_assembled_output"] = assembled

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
        _cp = state.get("compliance_profile") if isinstance(state.get("compliance_profile"), dict) else {}
        state["csod_assembled_output"] = {
            "intent": state.get("csod_intent", ""),
            "goal_intent": state.get("goal_intent"),
            "goal_pipeline_flags": _cp.get("goal_pipeline_flags"),
            "assembler_goal_actions": state.get("csod_assembler_goal_actions") or [],
            "calculation_plan": state.get("calculation_plan"),
            "metric_recommendations": state.get("csod_metric_recommendations", []),
            "kpi_recommendations": state.get("csod_kpi_recommendations", []),
            "data_science_insights": state.get("csod_data_science_insights", []),
            "dashboard": state.get("csod_dashboard_assembled", {}),
            "test_cases": state.get("csod_test_cases", []),
            "gold_model_sql": state.get("csod_generated_gold_model_sql", []),
            "demo_sql_agent_context": state.get("csod_demo_sql_agent_context"),
            "demo_sql_result_sets": state.get("csod_demo_sql_result_sets") or [],
            "demo_sql_insights_synthetic": state.get("csod_demo_sql_insights_synthetic"),
            "unified_pre_assembly_actions": state.get("unified_pre_assembly_actions") or [],
            "shared_per_metric_demo_artifacts": state.get("shared_per_metric_demo_artifacts")
            or [],
            "shared_per_metric_artifact_stubs": state.get("shared_per_metric_artifact_stubs")
            or [],
            "dt_generated_gold_model_sql": state.get("dt_generated_gold_model_sql") or [],
            "dt_data_science_insights": state.get("dt_data_science_insights") or [],
            "cubejs_schema_files": state.get("cubejs_schema_files", []),
        }

    return state

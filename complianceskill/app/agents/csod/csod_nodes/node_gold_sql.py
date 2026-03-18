"""Gold model SQL generation."""
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

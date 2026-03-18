"""Medallion / gold model planning."""
import json
from typing import Any, Dict, List

from langchain_core.messages import AIMessage

from app.agents.csod.csod_nodes._helpers import CSOD_State, _csod_log_step, logger
from app.agents.csod.csod_tool_integration import run_async

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

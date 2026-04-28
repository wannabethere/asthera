"""
Analysis planner node — produces schema-grounded, step-by-step analysis plans.

Replaces csod_planner in Phase 1 by running AFTER MDL schema retrieval so that
every plan step references real tables and columns from resolved_schemas.

Inlines the same pre/post steps as the original planner:
  1. _ensure_concept_context — backfills MDL anchors (safety net)
  2. _run_spine_precheck — DT axis seeds + capability resolution
"""
import json
import copy
from typing import Any, Dict, List, Optional

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


# ── Re-use inlined pre/post steps from the original planner ─────────────────

def _ensure_concept_context(state: CSOD_State) -> None:
    """Backfill MDL anchors from L1 concepts when planner chain skipped resolution."""
    from app.agents.csod.csod_nodes.node_concept_context import (
        _has_mdl_anchors,
        csod_concept_context_node,
    )
    if not _has_mdl_anchors(state):
        csod_concept_context_node(state)


def _run_spine_precheck(state: CSOD_State) -> None:
    """DT axis seeds + capability resolution before metrics retrieval."""
    try:
        from app.agents.capabilities.capability_spine import precheck_csod_dt_and_capabilities
        precheck_csod_dt_and_capabilities(state)
        cap = state.get("capability_resolution") or {}
        logger.info(
            "Spine precheck: use_case=%s, coverage=%.2f",
            cap.get("use_case", ""),
            cap.get("capability_coverage_ratio", 0),
        )
    except Exception as e:
        logger.warning("Spine precheck failed (non-fatal): %s", e, exc_info=True)
        state.setdefault("capability_resolution", {})
        state.setdefault("capability_retrieval_hints", "")


# ── Schema formatting for prompt injection ───────────────────────────────────

def _format_schemas_for_prompt(schemas: List[Dict], max_chars: int = 12000) -> str:
    """Format resolved schemas into a compact representation for the LLM prompt."""
    if not schemas:
        return "No schemas available."

    parts = []
    total = 0
    for schema in schemas:
        table_name = schema.get("table_name") or schema.get("name", "unknown")
        description = schema.get("description", "")
        columns = schema.get("column_metadata") or schema.get("columns", [])

        col_lines = []
        for col in columns:
            col_name = col.get("column_name") or col.get("name", "")
            col_type = col.get("data_type") or col.get("type", "")
            col_desc = col.get("description", "")
            col_lines.append(f"    - {col_name} ({col_type}): {col_desc[:80]}")

        block = f"TABLE: {table_name}\n  Description: {description[:150]}\n  Columns:\n" + "\n".join(col_lines)
        if total + len(block) > max_chars:
            parts.append(f"... ({len(schemas) - len(parts)} more tables truncated)")
            break
        parts.append(block)
        total += len(block)

    return "\n\n".join(parts)


# ── Column pruning based on plan ─────────────────────────────────────────────

def _prune_schemas_to_plan(
    resolved_schemas: List[Dict],
    plan: Dict[str, Any],
) -> List[Dict]:
    """Prune resolved_schemas to only tables and columns referenced by the plan steps."""
    # Collect all referenced tables and columns from plan steps
    referenced: Dict[str, set] = {}
    for step in plan.get("steps", []):
        for table in step.get("required_tables", []):
            referenced.setdefault(table, set())
        for table, cols in (step.get("required_columns") or {}).items():
            referenced.setdefault(table, set()).update(cols)

    # Also include join_map tables
    for join in plan.get("join_map", []):
        for key in ("left_table", "right_table"):
            t = join.get(key)
            if t:
                referenced.setdefault(t, set())
                jk = join.get("join_key")
                if jk:
                    referenced[t].add(jk)

    # Also include dimension_columns and time_column — keep them in all tables that have them
    extra_cols = set(plan.get("dimension_columns", []))
    tc = plan.get("time_column")
    if tc:
        extra_cols.add(tc)

    pruned = []
    for schema in resolved_schemas:
        table_name = schema.get("table_name") or schema.get("name", "")
        if table_name not in referenced:
            continue

        schema_copy = copy.deepcopy(schema)
        keep_cols = referenced[table_name] | extra_cols
        columns = schema_copy.get("column_metadata") or schema_copy.get("columns", [])

        if keep_cols:
            # Keep columns that are referenced, plus any that match dimension/time cols
            filtered = [
                c for c in columns
                if (c.get("column_name") or c.get("name", "")) in keep_cols
            ]
            # If no columns matched (LLM may have used slightly different names), keep all
            if filtered:
                if "column_metadata" in schema_copy:
                    schema_copy["column_metadata"] = filtered
                elif "columns" in schema_copy:
                    schema_copy["columns"] = filtered

        pruned.append(schema_copy)

    return pruned


# ── Backward-compatible execution_plan generation ────────────────────────────

def _plan_to_execution_plan(plan: Dict[str, Any]) -> List[Dict]:
    """Convert analysis plan steps to backward-compatible csod_execution_plan format."""
    execution_steps = []
    for step in plan.get("steps", []):
        execution_steps.append({
            "step_id": step.get("step_id", ""),
            "phase": "analysis",
            "agent": "analysis_planner",
            "description": step.get("description", ""),
            "semantic_question": step.get("output_description", ""),
            "reasoning": f"Step type: {step.get('step_type', '')}",
            "dependencies": step.get("dependencies", []),
            "required_tables": step.get("required_tables", []),
        })
    return execution_steps


# ══════════════════════════════════════════════════════════════════════════════
# MAIN NODE
# ══════════════════════════════════════════════════════════════════════════════

def csod_analysis_planner_node(state: CSOD_State) -> CSOD_State:
    """
    Schema-grounded analysis planner — runs AFTER MDL schema retrieval.

    Produces step-by-step analysis plans where every table and column reference
    is grounded in actual resolved schemas. Works for all analysis types
    (funnel, cohort, gap, coverage, RCA, metric recommendations, adhoc, etc.).

    Output fields populated:
        csod_analysis_plan          — step-by-step plan grounded in schemas
        csod_resolved_schemas_pruned — schemas pruned to plan-referenced columns
        csod_execution_plan         — backward-compat ordered steps
        csod_plan_summary, csod_estimated_complexity,
        csod_data_sources_in_scope, csod_gap_notes
        capability_resolution, csod_dt_seed_decisions (from spine precheck)
    """
    try:
        # Pre-step: ensure concept context is populated
        _ensure_concept_context(state)

        # Direct mode short-circuit — concept context is enough for CCE + question_rephraser.
        # Skip the heavy LLM analysis plan generation, schema pruning, and spine precheck.
        if state.get("csod_planner_only"):
            logger.info("[csod_analysis_planner] planner_only mode — skipping heavy LLM plan generation")
            return state

        prompt_text = load_prompt("30_analysis_planner", prompts_dir=str(PROMPTS_CSOD))

        tools = csod_get_tools_for_agent("csod_planner", state=state, conditional=True)
        use_tool_calling = bool(tools)

        intent = state.get("csod_intent", "")
        user_query = state.get("user_query", "")
        data_enrichment = state.get("data_enrichment", {})
        focus_areas = data_enrichment.get("suggested_focus_areas", [])
        selected_data_sources = state.get("selected_data_sources", [])
        resolved_schemas = state.get("csod_resolved_schemas", [])

        # Skill context (from skill pipeline phases 1 & 2)
        skill_context = state.get("skill_context") or {}
        skill_data_plan = state.get("skill_data_plan") or {}

        # Compliance profile filters
        compliance_profile = state.get("compliance_profile", {})
        filter_parts = []
        for key in ("time_window", "org_unit", "persona", "training_type", "cost_focus", "skills_domain"):
            val = compliance_profile.get(key)
            if val:
                label = key.replace("_", " ").title()
                if key == "org_unit":
                    ou_val = compliance_profile.get("org_unit_value")
                    if ou_val:
                        val = f"{val} ({ou_val})"
                filter_parts.append(f"{label}: {val}")
        filter_context = "\n".join(filter_parts) if filter_parts else "None specified"

        # Format resolved schemas for the prompt
        schema_context = _format_schemas_for_prompt(resolved_schemas)

        # Build the human message
        human_message = f"""User Query: {user_query}
Intent: {intent}
Focus Areas: {json.dumps(focus_areas)}
Selected Data Sources: {json.dumps(selected_data_sources)}

Filter Context (from conversational scoping):
{filter_context}
"""

        # Inject skill context if available
        if skill_context.get("skill_id"):
            human_message += f"""
Skill Context:
- Skill: {skill_context.get('skill_id', '')}
- Analysis Requirements: {json.dumps(skill_context.get('analysis_requirements', {}), indent=2)}
"""
        if skill_data_plan.get("skill_id"):
            human_message += f"""
Skill Data Plan:
- Required Metrics: {json.dumps(skill_data_plan.get('required_metrics', {}), indent=2)}
- Transformations: {json.dumps(skill_data_plan.get('transformations', []))}
- MDL Scope: {json.dumps(skill_data_plan.get('mdl_scope', {}), indent=2)}
"""

        # Inject causal paths and concept context
        causal_paths = compliance_profile.get("causal_paths", [])
        selected_concepts = compliance_profile.get("selected_concepts", [])
        selected_area_ids = compliance_profile.get("selected_area_ids", [])
        if causal_paths:
            human_message += f"\nKnown causal paths:\n{json.dumps(causal_paths, indent=2)}"
        if selected_concepts:
            human_message += f"\nUser-selected concept domains: {', '.join(selected_concepts)}"
        if selected_area_ids:
            human_message += f"\nFocus recommendation areas: {', '.join(selected_area_ids)}"

        # CRITICAL: Inject the actual resolved schemas
        human_message += f"""

RESOLVED MDL SCHEMAS (use ONLY these tables and columns in your plan):
{schema_context}

Produce the analysis plan JSON as specified in your instructions. Every table and column you reference MUST appear in the schemas above."""

        # Inject executor registry for backward compat
        try:
            from app.agents.csod.executor_registry import registry_summary_for_planner
            registry_summary = registry_summary_for_planner()
            human_message += f"\n\nAVAILABLE EXECUTORS:\n{json.dumps(registry_summary, indent=2)}"
        except Exception:
            pass

        logger.info(
            "[CSOD pipeline] csod_analysis_planner: generating schema-grounded plan "
            "(intent=%s, schemas=%d)",
            intent, len(resolved_schemas),
        )

        response_content = _llm_invoke(
            state, "csod_analysis_planner", prompt_text, human_message,
            tools, use_tool_calling, max_tool_iterations=5,
        )

        plan_result = _parse_json_response(response_content, {})

        # ── Log the generated plan ───────────────────────────────────────
        steps = plan_result.get("steps", [])
        logger.info("=" * 80)
        logger.info("[CSOD pipeline] ANALYSIS PLAN GENERATED")
        logger.info("=" * 80)
        logger.info("  Analysis Type: %s", plan_result.get("analysis_type", "N/A"))
        logger.info("  Summary: %s", plan_result.get("summary", "")[:200])
        logger.info("  Complexity: %s", plan_result.get("estimated_complexity", "N/A"))
        logger.info("  Steps: %d", len(steps))
        for step in steps:
            tables = step.get("required_tables", [])
            cols = step.get("required_columns", {})
            new_metrics = step.get("new_metrics", [])
            logger.info(
                "    [%s] %s (type=%s, tables=%s, cols=%d, new_metrics=%d, deps=%s)",
                step.get("step_id", "?"),
                step.get("description", "")[:100],
                step.get("step_type", "?"),
                tables,
                sum(len(v) for v in cols.values()) if isinstance(cols, dict) else 0,
                len(new_metrics),
                step.get("dependencies", []),
            )
        join_map = plan_result.get("join_map", [])
        if join_map:
            logger.info("  Join Map: %d joins", len(join_map))
            for j in join_map:
                logger.info(
                    "    %s -[%s]-> %s ON %s",
                    j.get("left_table", "?"),
                    j.get("join_type", "?"),
                    j.get("right_table", "?"),
                    j.get("join_key", "?"),
                )
        dims = plan_result.get("dimension_columns", [])
        if dims:
            logger.info("  Dimension Columns: %s", dims)
        tc = plan_result.get("time_column")
        if tc:
            logger.info("  Time Column: %s", tc)
        gaps = plan_result.get("gap_notes", [])
        if gaps:
            logger.info("  Gap Notes: %s", gaps)
        logger.info("=" * 80)

        # ── Persist analysis plan ────────────────────────────────────────
        state["csod_analysis_plan"] = plan_result

        # ── Prune schemas to plan references ─────────────────────────────
        if plan_result.get("steps"):
            state["csod_resolved_schemas_pruned"] = _prune_schemas_to_plan(
                resolved_schemas, plan_result,
            )
            logger.info(
                "[CSOD pipeline] csod_analysis_planner: pruned schemas %d → %d tables",
                len(resolved_schemas),
                len(state["csod_resolved_schemas_pruned"]),
            )
        else:
            state["csod_resolved_schemas_pruned"] = resolved_schemas

        # ── Backward-compat fields ───────────────────────────────────────
        state["csod_plan_summary"] = plan_result.get("summary", "")
        state["csod_estimated_complexity"] = plan_result.get(
            "estimated_complexity", "moderate"
        )
        state["csod_execution_plan"] = _plan_to_execution_plan(plan_result)
        state["csod_gap_notes"] = plan_result.get("gap_notes", [])
        state["csod_data_sources_in_scope"] = (
            plan_result.get("data_sources_in_scope") or selected_data_sources
        )

        # Narrative preview
        narrative = plan_result.get("summary", "")
        state["csod_narrative_preview"] = narrative
        state["csod_follow_up_eligible"] = True
        if narrative:
            try:
                from app.agents.csod.csod_nodes.narrative import append_csod_narrative
                append_csod_narrative(state, "planner", "Analysis Planner", narrative)
            except Exception:
                pass

        _csod_log_step(
            state, "csod_analysis_planning", "csod_analysis_planner",
            inputs={
                "user_query": user_query,
                "intent": intent,
                "focus_areas": focus_areas,
                "schema_count": len(resolved_schemas),
            },
            outputs={
                "plan_summary": state["csod_plan_summary"],
                "complexity": state["csod_estimated_complexity"],
                "step_count": len(plan_result.get("steps", [])),
                "pruned_schema_count": len(state.get("csod_resolved_schemas_pruned", [])),
            },
        )

        try:
            from app.agents.csod.reasoning_trace import refresh_reasoning_trace_after_planner
            refresh_reasoning_trace_after_planner(state)
        except Exception:
            pass

        state["messages"].append(AIMessage(
            content=(
                f"Analysis Plan: {state['csod_plan_summary'][:100]} | "
                f"steps={len(plan_result.get('steps', []))} | "
                f"schemas_pruned={len(state.get('csod_resolved_schemas_pruned', []))}"
            )
        ))

        # Post-step: spine precheck
        _run_spine_precheck(state)

    except Exception as e:
        logger.error("csod_analysis_planner_node failed: %s", e, exc_info=True)
        state["error"] = f"CSOD analysis planner failed: {str(e)}"
        state.setdefault("csod_analysis_plan", None)
        state.setdefault("csod_resolved_schemas_pruned", None)
        state.setdefault("csod_plan_summary", "")
        state.setdefault("csod_estimated_complexity", "moderate")
        state.setdefault("csod_execution_plan", [])
        state.setdefault("csod_data_sources_in_scope", state.get("selected_data_sources", []))

    return state

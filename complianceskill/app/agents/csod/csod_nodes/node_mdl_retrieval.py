"""MDL schema + gold standard retrieval."""
from typing import Any, Dict, List

from langchain_core.messages import AIMessage

from app.agents.csod.csod_tool_integration import (
    csod_retrieve_mdl_schemas,
    csod_retrieve_gold_standard_tables,
)
from app.agents.csod.csod_mdl_utils import prune_columns_from_schemas
from app.agents.csod.mdl_capability_layer import enrich_csod_mdl_after_retrieval
from app.agents.csod.csod_nodes._helpers import CSOD_State, _csod_log_step, logger
from app.agents.shared.mdl_recommender_schema_scope import build_area_scoped_mdl_fallback_query

def csod_mdl_schema_retrieval_node(state: CSOD_State) -> CSOD_State:
    """
    Retrieves MDL schemas for CSOD workflow.
    Reuses DT pattern but can be customized for CSOD-specific needs.
    
    NEW: If Lexy planner resolved MDL tables from registry, use as retrieval pre-filter.
    """
    try:
        _resolved_pids_preview = state.get("csod_resolved_project_ids") or []
        logger.info(
            "[CSOD pipeline] csod_mdl_schema_retrieval: running MDL schema "
            "+ gold-standard retrieval (active_project_id=%s, resolved_project_ids=%s, data_sources=%s)",
            state.get("active_project_id") or state.get("csod_primary_project_id") or "none",
            _resolved_pids_preview[:4],
            state.get("selected_data_sources") or [],
        )
        resolved_metrics = state.get("resolved_metrics", [])
        user_query = state.get("user_query", "")
        focus_area_categories = state.get("focus_area_categories", [])

        # ── Project ID resolution: prefer planner-resolved IDs ────────────────
        # The intent planner (csod_intent_confirm) writes csod_resolved_project_ids
        # and csod_primary_project_id. These are the most specific source of truth.
        resolved_project_ids: List[str] = state.get("csod_resolved_project_ids") or []
        project_id = (
            state.get("active_project_id")
            or state.get("csod_primary_project_id")
            or (resolved_project_ids[0] if resolved_project_ids else "")
            or (state.get("compliance_profile") or {}).get("project_id", "")
            or next(iter((state.get("compliance_profile") or {}).get("selected_project_ids") or []), "")
            or ""
        )
        if project_id:
            logger.info(
                "csod_mdl_schema_retrieval: using project_id='%s' (resolved_project_ids=%s)",
                project_id, resolved_project_ids,
            )

        silver_gold_tables_only = state.get("silver_gold_tables_only", False)
        # Direct analysis mode skips bronze/raw tables — only gold/silver
        if state.get("csod_direct_analysis_mode") == "direct":
            silver_gold_tables_only = True
            logger.info("csod_mdl_schema_retrieval: direct mode — restricting to silver/gold tables only")

        # NEW: If Lexy resolved MDL tables from registry, use as retrieval pre-filter
        compliance_profile = state.get("compliance_profile", {})
        active_mdl_tables = compliance_profile.get("active_mdl_tables", [])
        data_requirements = compliance_profile.get("data_requirements", [])
        
        # Combine: data_requirements are the minimal required set; active_mdl_tables is the full set
        priority_tables = list(set(data_requirements + active_mdl_tables[:20]))  # cap at 20
        
        if priority_tables:
            logger.info(f"MDL schema retrieval: using registry-resolved table filter ({len(priority_tables)} tables)")
            # Pass priority_tables as retrieval filter hint
            state["csod_mdl_table_filter"] = priority_tables

        # Collect schema names from resolved metrics
        schema_names: List[str] = []
        for metric in resolved_metrics:
            for sn in metric.get("source_schemas", []):
                if sn and sn not in schema_names:
                    schema_names.append(sn)

        # ── Seed schema_names from planner-resolved project tables ───────────
        # csod_resolved_project_tables is set by csod_intent_confirm._apply_selections
        # and contains {project_id: {primary_tables: [{name, key_columns, ...}], ...}}.
        # Use it directly (avoids a second JSON load) then fall back to metadata file.
        resolved_project_tables: dict = state.get("csod_resolved_project_tables") or {}
        if not schema_names and resolved_project_tables:
            for pid in resolved_project_ids:
                proj_data = resolved_project_tables.get(pid, {})
                for tinfo in proj_data.get("primary_tables", []):
                    tname = tinfo.get("name", "")
                    if tname and tname not in schema_names:
                        schema_names.append(tname)
            if schema_names:
                logger.info(
                    "csod_mdl_schema_retrieval: seeded %d schema name(s) from "
                    "csod_resolved_project_tables for project(s) %s",
                    len(schema_names), resolved_project_ids,
                )

        # Fallback: load from metadata file if still empty
        if not schema_names and resolved_project_ids:
            try:
                from app.ingestion.mdl_intent_resolver import _load_project_metadata
                meta = _load_project_metadata()
                project_index = {p["project_id"]: p for p in meta.get("projects", [])}
                for pid in resolved_project_ids:
                    proj = project_index.get(pid, {})
                    for tname in proj.get("mdl_tables", {}).get("primary", []):
                        if tname and tname not in schema_names:
                            schema_names.append(tname)
                if schema_names:
                    logger.info(
                        "csod_mdl_schema_retrieval: seeded %d schema name(s) from "
                        "metadata file for project(s) %s",
                        len(schema_names), resolved_project_ids,
                    )
            except Exception as _exc:
                logger.warning("csod_mdl_schema_retrieval: project metadata seed failed: %s", _exc)

        fallback_query = build_area_scoped_mdl_fallback_query(state)
        if not fallback_query.strip():
            fallback_query = " ".join(focus_area_categories + [user_query]).strip()
        cap_hints = (state.get("capability_retrieval_hints") or "").strip()
        if cap_hints:
            fallback_query = f"{fallback_query} {cap_hints}".strip()
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
        state["csod_mdl_retrieved_table_descriptions"] = schema_data.get("table_descriptions") or []

        # Apply column pruning if needed
        if state["csod_resolved_schemas"] and any(s.get("column_metadata") for s in state["csod_resolved_schemas"]):
            reasoning = state.get("csod_planner_reasoning") or state.get("reasoning")
            state["csod_resolved_schemas"] = prune_columns_from_schemas(
                schemas=state["csod_resolved_schemas"],
                user_query=user_query,
                reasoning=reasoning
            )

        try:
            enrich_csod_mdl_after_retrieval(state)
        except Exception as e:
            logger.warning("csod_mdl_schema_retrieval: capability layer enrichment skipped: %s", e)

        # Gold standard tables lookup with metadata-based category recommendation
        gold_tables: List[Dict[str, Any]] = []
        # Get data_enrichment outside the if block to ensure it's always defined
        data_enrichment = state.get("data_enrichment", {})
        
        if project_id or focus_area_categories:
            intent = state.get("csod_intent", "")
            selected_data_sources = state.get("csod_data_sources_in_scope", []) or state.get("selected_data_sources", [])
            user_query = state.get("user_query", "")
            focus_areas = data_enrichment.get("suggested_focus_areas", [])
            
            gold_tables = csod_retrieve_gold_standard_tables(
                project_id=project_id or "",
                categories=focus_area_categories or None,
                intent=intent,
                data_sources=selected_data_sources,
                user_query=user_query,
                focus_areas=focus_areas,
                use_semantic_search=False,  # Can be enabled via config if vector store is set up
            )
        state["csod_gold_standard_tables"] = gold_tables

        # Store in context_cache (include L2/L3/relation enrichment from enrich_csod_mdl_after_retrieval)
        state["context_cache"] = state.get("context_cache", {})
        state["context_cache"]["schema_resolution"] = {
            "schemas": state["csod_resolved_schemas"],
            "table_descriptions": schema_data.get("table_descriptions", []),
            "query": fallback_query,
            "data_sources": selected_data_sources,
            "focus_areas": focus_area_categories,
            "mdl_l1_focus_scope": state.get("csod_mdl_l1_focus_scope") or {},
            "mdl_l2_capability_tables": state.get("csod_mdl_l2_capability_tables") or {},
            "mdl_l3_retrieval_queries": state.get("csod_mdl_l3_retrieval_queries") or {},
            "mdl_relation_edges": state.get("csod_mdl_relation_edges") or [],
            "mdl_needs_focus_clarification": bool(state.get("csod_mdl_needs_focus_clarification")),
            "mdl_focus_clarification_message": state.get("csod_mdl_focus_clarification_message") or "",
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
                "l2_tables": len((state.get("csod_mdl_l2_capability_tables") or {})),
                "l3_queries": len((state.get("csod_mdl_l3_retrieval_queries") or {})),
                "relation_edges": len(state.get("csod_mdl_relation_edges") or []),
            },
        )
        try:
            from app.agents.csod.reasoning_trace import refresh_reasoning_trace_after_mdl

            refresh_reasoning_trace_after_mdl(state)
        except Exception:
            pass

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
        state.setdefault("csod_mdl_l2_capability_tables", {})
        state.setdefault("csod_mdl_l3_retrieval_queries", {})
        state.setdefault("csod_mdl_relation_edges", [])
        state.setdefault("csod_mdl_l1_focus_scope", {})
        state.setdefault("csod_mdl_needs_focus_clarification", False)
        state.setdefault("csod_mdl_focus_clarification_message", "")
        state.setdefault("csod_mdl_retrieved_table_descriptions", [])

    return state

"""Metrics registry retrieval."""
from typing import Any, Dict, List

from langchain_core.messages import AIMessage

from app.retrieval.mdl_service import MDLRetrievalService
from app.agents.csod.csod_tool_integration import run_async
from app.agents.csod.csod_nodes._helpers import CSOD_State, _csod_log_step, logger

def csod_metrics_retrieval_node(state: CSOD_State) -> CSOD_State:
    """
    Retrieves metrics from leen_metrics_registry for CSOD workflow.
    Similar to DT metrics retrieval but focused on CSOD use cases.
    
    NEW: Pre-seed priority metrics from registry if available.
    """
    try:
        logger.info(
            "[CSOD pipeline] csod_metrics_retrieval: retrieving metrics from "
            "registry for recommendations (intent=%s)",
            state.get("csod_intent", ""),
        )
        from app.retrieval.mdl_service import MDLRetrievalService

        data_enrichment = state.get("data_enrichment", {})
        metrics_intent = data_enrichment.get("metrics_intent", "current_state")
        focus_areas = data_enrichment.get("suggested_focus_areas", [])
        data_sources_in_scope = state.get("csod_data_sources_in_scope", []) or state.get("selected_data_sources", [])
        
        # Extract compliance_profile fields for filter context (from Lexy conversational layer)
        compliance_profile = state.get("compliance_profile", {})
        time_window = compliance_profile.get("time_window")
        org_unit = compliance_profile.get("org_unit")
        training_type = compliance_profile.get("training_type")
        skills_domain = compliance_profile.get("skills_domain")
        cost_focus = compliance_profile.get("cost_focus")
        
        # NEW: Pre-seed priority metrics from registry
        priority_metrics = compliance_profile.get("priority_metrics", [])
        priority_kpis = compliance_profile.get("priority_kpis", [])
        
        if priority_metrics:
            # Pre-seed the retrieval target list so the metrics retriever
            # searches for these by name first before doing semantic expansion
            state["csod_priority_metric_names"] = priority_metrics
            state["csod_priority_kpi_names"] = priority_kpis
            logger.info(f"Metrics retrieval: registry seeded {len(priority_metrics)} priority metrics")

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
        
        # Enhance search query with compliance_profile context
        query_parts = focus_area_categories.copy() if focus_area_categories else []
        
        # Add training_type to query if specified
        if training_type and training_type != "all":
            if training_type == "mandatory":
                query_parts.append("mandatory compliance")
            elif training_type == "certification":
                query_parts.append("certification")
        
        # Add skills_domain to query if specified
        if skills_domain and skills_domain != "all":
            query_parts.append(skills_domain)
        
        # Add cost_focus to query if specified (for ROI flow)
        if cost_focus:
            if cost_focus in ("waste", "no_shows"):
                query_parts.extend(["no-shows", "cancellations", "attendance"])
            elif cost_focus == "vendor_efficiency":
                query_parts.extend(["vendor", "cost", "efficiency"])
            elif cost_focus == "full_roi":
                query_parts.extend(["roi", "cost", "budget"])

        state["focus_area_categories"] = focus_area_categories

        search_query = " ".join(query_parts) if query_parts else "csod metrics learning talent"

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

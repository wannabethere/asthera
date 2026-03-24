"""Causal graph (CCE) enrichment — topology + attribution placeholder layer (cce_attribution)."""
from typing import Any, Dict, List

from langchain_core.messages import AIMessage

from app.agents.csod.csod_nodes._helpers import CSOD_State, _csod_log_step, logger


def _compute_causal_centrality(
    edges: List[Dict[str, Any]], nodes: List[Dict[str, Any]]
) -> Dict[str, Dict[str, int]]:
    """In/out degree per metric id from directed edges (topology — not Shapley)."""
    out_deg: Dict[str, int] = {}
    in_deg: Dict[str, int] = {}

    def _edge_endpoints(e: Dict[str, Any]) -> tuple:
        src = (
            e.get("source_node")
            or e.get("source_metric_id")
            or e.get("from_metric_id")
            or ""
        )
        tgt = (
            e.get("target_node")
            or e.get("target_metric_id")
            or e.get("to_metric_id")
            or ""
        )
        return (str(src).strip(), str(tgt).strip())

    for e in edges or []:
        src, tgt = _edge_endpoints(e)
        if not src or not tgt:
            continue
        out_deg[src] = out_deg.get(src, 0) + 1
        in_deg[tgt] = in_deg.get(tgt, 0) + 1

    ids = set(out_deg) | set(in_deg)
    for n in nodes or []:
        mid = str(
            n.get("metric_id") or n.get("id") or n.get("node_id") or ""
        ).strip()
        if mid:
            ids.add(mid)

    return {
        mid: {"out_degree": out_deg.get(mid, 0), "in_degree": in_deg.get(mid, 0)}
        for mid in ids
    }


def csod_causal_graph_node(state: CSOD_State) -> CSOD_State:
    """
    Builds causal graph using the causal graph creator module.

    Uses hybrid retrieval (ChromaDB + Postgres) + LLM assembly to build
    a typed causal graph that enhances metric recommendations.

    Controlled via feature flag: csod_causal_graph_enabled

    This node now uses the full causal_graph_creator_node from the causalgraph module,
    which provides:
    - Vector retrieval of nodes and edges
    - LLM assembly for graph construction
    - Causal context extraction for downstream enrichment
    """
    # Fast-path: cross-concept resume — CCE already ran, results are in state
    if state.get("csod_cross_concept_confirmed") and state.get("csod_causal_nodes") is not None:
        logger.info("[csod_causal_graph] CCE already ran (cross-concept resume) — skipping re-run")
        return state

    try:
        # Check feature flag
        causal_enabled = state.get("csod_causal_graph_enabled", False)
        if not causal_enabled:
            logger.info(
                "[CSOD pipeline] csod_causal_graph: skipped "
                "(csod_causal_graph_enabled=False)"
            )
            state.setdefault("csod_causal_nodes", [])
            state.setdefault("csod_causal_edges", [])
            state.setdefault("csod_causal_graph_metadata", {})
            state.setdefault("csod_causal_retrieval_stats", {})
            state.setdefault("csod_causal_centrality", {})
            state.setdefault("csod_causal_graph_result", {})
            try:
                from app.agents.csod.intent_config import get_cce_mode_for_intent

                state["csod_causal_mode"] = get_cce_mode_for_intent(
                    state.get("csod_intent")
                )
            except Exception:
                state.setdefault("csod_causal_mode", "disabled")
            return state

        from app.agents.causalgraph.lexy_domain_context import apply_domain_classification_to_state

        apply_domain_classification_to_state(state)

        vertical = state.get("causal_vertical", state.get("vertical", "lms"))
        logger.info(
            "[CSOD pipeline] csod_causal_graph: running causal enrichment "
            "(vertical=%s, active_domains=%s)",
            vertical,
            state.get("active_domains"),
        )
        
        user_query = state.get("user_query", "")
        
        if not user_query:
            logger.warning("No user query available for causal graph")
            state.setdefault("csod_causal_nodes", [])
            state.setdefault("csod_causal_edges", [])
            state.setdefault("csod_causal_centrality", {})
            state.setdefault("csod_causal_graph_result", {})
            return state
        
        # Prefer DT-qualified metrics when present (CCE operates on same set as execution spine)
        dt_scored = state.get("dt_scored_metrics", [])
        metric_recommendations = state.get("csod_metric_recommendations", [])
        retrieved_metrics = state.get("csod_retrieved_metrics", [])
        source_metrics = dt_scored if dt_scored else (metric_recommendations + retrieved_metrics)
        
        # Merge and deduplicate
        all_metrics = []
        seen_ids = set()
        for m in source_metrics:
            mid = m.get("metric_id") or m.get("id", "")
            if mid and mid not in seen_ids:
                seen_ids.add(mid)
                all_metrics.append(m)
        
        # Build causal graph state for the creator
        from app.agents.causalgraph import causal_graph_creator_node
        
        causal_state = {
            "user_query": user_query,
            "causal_vertical": vertical,
            "vertical": state.get("vertical", vertical),
            "active_domains": state.get("active_domains", [vertical]),
            "primary_domain": state.get("primary_domain", vertical),
            "metric_registry": all_metrics,
            "causal_metric_registry": all_metrics,
            "schema_definitions": {},  # Can bootstrap from csod_resolved_schemas if needed
            "corpus": [],  # Can load from config
            "available_data_sources": state.get("csod_data_sources_in_scope", []),
            "cce_db_url": state.get("cce_db_url"),
            "causal_proposed_nodes": [],
            "causal_proposed_edges": [],
            "causal_graph_metadata": {},
            "causal_signals": {},
            "causal_graph_panel_data": None,
            "causal_node_index": {},
            "messages": state.get("messages", []),
        }
        
        # Call causal graph creator
        causal_state = causal_graph_creator_node(causal_state)

        if causal_state.get("lexy_stage_2_concept_mapping"):
            state["lexy_stage_2_concept_mapping"] = causal_state["lexy_stage_2_concept_mapping"]
        
        # Map outputs back to CSOD state
        proposed_nodes = causal_state.get("causal_proposed_nodes", [])
        proposed_edges = causal_state.get("causal_proposed_edges", [])
        graph_metadata = causal_state.get("causal_graph_metadata", {})
        retrieval_stats = causal_state.get("causal_retrieval_stats", {})
        
        state["csod_causal_nodes"] = proposed_nodes
        state["csod_causal_edges"] = proposed_edges
        state["csod_causal_graph_metadata"] = graph_metadata
        state["csod_causal_retrieval_stats"] = retrieval_stats

        centrality = _compute_causal_centrality(proposed_edges, proposed_nodes)
        state["csod_causal_centrality"] = centrality
        state["csod_causal_graph_result"] = {
            **(graph_metadata if isinstance(graph_metadata, dict) else {}),
            "node_count": len(proposed_nodes),
            "edge_count": len(proposed_edges),
            "centrality_metric_count": len(centrality),
        }

        try:
            from app.agents.causalgraph.cce_attribution import (
                merge_attribution_into_causal_graph_result,
                prepare_cce_attribution_context,
                run_attribution,
            )

            prepare_cce_attribution_context(
                state,
                proposed_nodes=proposed_nodes,
                proposed_edges=proposed_edges,
                graph_metadata=graph_metadata if isinstance(graph_metadata, dict) else {},
                spine_metrics=all_metrics,
            )
            run_attribution(state)
            merge_attribution_into_causal_graph_result(state)
        except Exception as _cce_attr_err:
            logger.warning(
                "CCE attribution layer skipped: %s",
                _cce_attr_err,
                exc_info=True,
            )
        try:
            from app.agents.csod.intent_config import get_cce_mode_for_intent

            state["csod_causal_mode"] = get_cce_mode_for_intent(
                state.get("csod_intent")
            )
        except Exception:
            state["csod_causal_mode"] = "varies"

        # Store causal context for metrics recommender enrichment
        state["causal_signals"] = causal_state.get("causal_signals", {})
        state["causal_graph_boost_focus_areas"] = causal_state.get("causal_graph_boost_focus_areas", [])
        state["causal_graph_panel_data"] = causal_state.get("causal_graph_panel_data")
        state["causal_node_index"] = causal_state.get("causal_node_index", {})
        
        # Update messages
        if "messages" in causal_state:
            new_messages = [
                msg for msg in causal_state["messages"]
                if msg not in state.get("messages", [])
            ]
            state["messages"].extend(new_messages)
        
        _csod_log_step(
            state, "csod_causal_graph", "csod_causal_graph",
            inputs={
                "user_query": user_query,
                "vertical": vertical,
                "metric_count": len(all_metrics),
            },
            outputs={
                "nodes_assembled": len(proposed_nodes),
                "edges_assembled": len(proposed_edges),
                "retrieval_stats": retrieval_stats,
                "focus_area": causal_state.get("causal_signals", {}).get("derived_focus_area"),
                "centrality_keys": len(centrality),
                "attribution_method": state.get("attribution_method_used"),
                "attribution_placeholder": (state.get("attribution_result") or {}).get(
                    "is_placeholder"
                ),
            },
        )
        
        state["messages"].append(AIMessage(
            content=(
                f"[CausalGraph] Assembled {len(proposed_nodes)} nodes, {len(proposed_edges)} edges | "
                f"Focus: {causal_state.get('causal_signals', {}).get('derived_focus_area', 'N/A')} | "
                f"vertical={vertical}"
            )
        ))
        try:
            from app.agents.csod.csod_nodes.narrative import append_csod_narrative

            append_csod_narrative(
                state,
                "cce",
                "Causal graph",
                f"Mapped {len(proposed_nodes)} metrics and {len(proposed_edges)} relationships "
                f"(topology for downstream executors).",
            )
        except Exception:
            pass
        
    except Exception as e:
        logger.error(f"csod_causal_graph_node failed: {e}", exc_info=True)
        state["error"] = f"CausalGraph failed: {str(e)}"
        state.setdefault("csod_causal_nodes", [])
        state.setdefault("csod_causal_edges", [])
        state.setdefault("csod_causal_graph_metadata", {})
        state.setdefault("csod_causal_retrieval_stats", {})
        state.setdefault("csod_causal_centrality", {})
        state.setdefault("csod_causal_graph_result", {})

    return state


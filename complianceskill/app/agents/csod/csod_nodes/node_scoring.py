"""Scoring / composite validation."""
import json
from typing import Dict

from langchain_core.messages import AIMessage

from app.agents.csod.csod_nodes._helpers import CSOD_State, _csod_log_step, logger

def csod_scoring_validator_node(state: CSOD_State) -> CSOD_State:
    """
    Cross-scores all retrieved items (metrics, KPIs, schemas) against
    focus areas and intent.
    
    Similar to DT scoring validator but focused on CSOD metrics/KPIs.
    """
    try:
        logger.info(
            "[CSOD pipeline] csod_scoring_validator: scoring retrieved metrics/KPIs "
            "(intent=%s)",
            state.get("csod_intent", ""),
        )
        data_enrichment = state.get("data_enrichment", {})
        intent = state.get("csod_intent", "")
        focus_areas = data_enrichment.get("suggested_focus_areas", [])
        focus_cats = state.get("focus_area_categories", [])
        user_query = state.get("user_query", "").lower()

        THRESHOLD = 0.50
        WARN_THRESHOLD = 0.65

        def _score_item(item: Dict, item_type: str) -> Dict:
            """Score an item based on intent and focus areas."""
            item_str = json.dumps(item).lower()
            intent_keywords = intent.replace("_", " ").split()
            query_words = [w for w in user_query.split() if len(w) > 3]
            combined = intent_keywords + query_words
            
            # Intent alignment
            matches = sum(1 for kw in combined if kw in item_str)
            intent_score = min(1.0, matches / max(len(combined), 1) * 2)
            
            # Focus area match
            focus_score = 0.5
            if focus_cats:
                for cat in focus_cats:
                    if cat.replace("_", " ") in item_str:
                        focus_score = 1.0
                        break
            
            composite = (intent_score * 0.5) + (focus_score * 0.5)
            return {
                **item,
                "composite_score": round(composite, 3),
                "low_confidence": composite < WARN_THRESHOLD,
            }

        # Score metrics
        metrics = state.get("resolved_metrics", [])
        scored_metrics = [_score_item(m, "metric") for m in metrics]
        scored_metrics = [m for m in scored_metrics if m["composite_score"] >= THRESHOLD]
        scored_metrics.sort(key=lambda m: m.get("composite_score", 0.0), reverse=True)

        # Score schemas
        schemas = state.get("csod_resolved_schemas", [])
        scored_schemas = [_score_item(s, "schema") for s in schemas]
        scored_schemas = [s for s in scored_schemas if s["composite_score"] >= THRESHOLD]

        # Build scored_context
        scored_context = {
            "scored_metrics": scored_metrics,
            "resolved_schemas": scored_schemas,
            "gold_standard_tables": state.get("csod_gold_standard_tables", []),
        }

        state["csod_scored_context"] = scored_context
        state["resolved_metrics"] = scored_metrics
        state["csod_resolved_schemas"] = scored_schemas

        _csod_log_step(
            state, "csod_scoring_validation", "csod_scoring_validator",
            inputs={
                "metrics_in": len(metrics),
                "schemas_in": len(schemas),
            },
            outputs={
                "metrics_retained": len(scored_metrics),
                "schemas_retained": len(scored_schemas),
            },
        )

        state["messages"].append(AIMessage(
            content=(
                f"CSOD Scoring: retained {len(scored_metrics)} metrics, "
                f"{len(scored_schemas)} schemas"
            )
        ))

    except Exception as e:
        logger.error(f"csod_scoring_validator_node failed: {e}", exc_info=True)
        state["error"] = f"CSOD scoring validator failed: {str(e)}"
        state["csod_scored_context"] = {
            "scored_metrics": state.get("resolved_metrics", []),
            "resolved_schemas": state.get("csod_resolved_schemas", []),
            "gold_standard_tables": state.get("csod_gold_standard_tables", []),
        }

    return state

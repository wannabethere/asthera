"""Follow-up router: skip spine when turn>1 and question maps to a direct executor."""
import json
from typing import Dict, List, Optional

from langchain_core.messages import AIMessage

from app.agents.prompt_loader import load_prompt, PROMPTS_CSOD
from app.agents.csod.csod_nodes._helpers import (
    CSOD_State,
    _csod_log_step,
    _llm_invoke,
    _parse_json_response,
    logger,
)
from app.agents.csod.csod_nodes.narrative import append_csod_narrative
from app.agents.csod.executor_registry import EXECUTOR_REGISTRY, get_executor

# Graph node names (LangGraph) for implemented direct paths only
_FOLLOWUP_TO_GRAPH_NODE: Dict[str, str] = {
    "metric_augmenter": "csod_metrics_retrieval",
    "metrics_recommender": "csod_metrics_recommender",
    "dashboard_generator": "csod_dashboard_generator",
    "compliance_test_generator": "csod_compliance_test_generator",
    "data_discovery_agent": "data_discovery_agent",
    "data_quality_inspector": "data_quality_inspector",
    "data_lineage_tracer": "data_lineage_tracer",
}

_AUGMENT_STARTERS = (
    "add ", "include ", "append ", "also add ", "also show ",
    "want to add ", "can you add ", "i want to add ", "i'd like to add ",
    "add a ", "add the ", "add an ",
)
_FULL_ANALYSIS_SIGNALS = (
    "analyze", "over the last", "for my organization", "show me a dashboard",
    "how does", "what is the", "track my", "give me a report",
)


def _is_metric_augmentation_request(query: str) -> bool:
    """True when the user wants to append a specific metric to an existing analysis."""
    q = query.lower().strip()
    has_trigger = any(q.startswith(t) or f" {t}" in q for t in _AUGMENT_STARTERS)
    if not has_trigger:
        return False
    # Exclude phrasing that looks like a brand-new full analysis
    if any(sig in q for sig in _FULL_ANALYSIS_SIGNALS):
        return False
    return True


def _eligible_direct_executor_ids() -> List[str]:
    return sorted(
        eid
        for eid, e in EXECUTOR_REGISTRY.items()
        if e.get("can_be_direct") and e.get("implemented") is True
    )


def _heuristic_executor_id(query: str) -> Optional[str]:
    """Map follow-up wording to an implemented direct executor (analytical → metrics_recommender)."""
    q = query.lower()
    if any(
        w in q
        for w in (
            "lineage",
            "where does",
            "upstream",
            "downstream",
            "sourced from",
            "trace the metric",
        )
    ):
        return "data_lineage_tracer"
    if any(
        w in q
        for w in (
            "quality",
            "freshness",
            "complete",
            "trust the data",
            "nulls",
            "stale",
        )
    ):
        return "data_quality_inspector"
    if any(
        w in q
        for w in (
            "what tables",
            "what data",
            "inventory",
            "available schemas",
            "what can i analyze",
        )
    ):
        return "data_discovery_agent"
    if any(
        w in q
        for w in (
            "dashboard layout",
            "dashboard for",
            "persona view",
            "executive view",
            "show me a dashboard",
        )
    ):
        return "dashboard_generator"
    if any(
        w in q
        for w in (
            "sql test",
            "compliance test",
            "audit check",
            "control test",
        )
    ):
        return "compliance_test_generator"
    if any(
        w in q
        for w in (
            "department",
            "cohort",
            "segment",
            "break down",
            "breakdown",
            "by team",
            "by org",
            "by division",
            "anomaly",
            "spike",
            "gap",
            "deadline",
            "at risk",
            "roi",
            "funnel",
            "benchmark",
            "skill gap",
            "engagement",
            "crown jewel",
            "which metric",
            "other metrics",
            "recommend metrics",
            "metric recommendation",
        )
    ):
        return "metrics_recommender"
    return None


def _resolve_followup_route(executor_id: str) -> str:
    return _FOLLOWUP_TO_GRAPH_NODE.get(executor_id, "full_spine")


def csod_followup_router_node(state: CSOD_State) -> CSOD_State:
    """
    First node in graph. If csod_session_turn > 1 and spine context exists,
    may route directly to an executor; else sets route to full spine.
    """
    state.setdefault("csod_narrative_stream", [])
    state["csod_followup_graph_route"] = "csod_intent_classifier"
    state["csod_followup_short_circuit"] = False
    turn = int(state.get("csod_session_turn") or 1)
    user_query = (state.get("user_query") or "").strip()

    if turn <= 1:
        _csod_log_step(
            state,
            "followup_router",
            "csod_followup_router",
            {"turn": turn},
            {"route": "full_spine", "reason": "first_turn"},
        )
        return state

    dt = state.get("dt_scored_metrics") or []
    schemas = state.get("csod_resolved_schemas") or []
    if not dt or not schemas:
        append_csod_narrative(
            state,
            "followup",
            "Follow-up router",
            "Prior qualified metrics or schemas not in state — running full pipeline.",
        )
        _csod_log_step(
            state,
            "followup_router",
            "csod_followup_router",
            {"turn": turn},
            {"route": "full_spine", "reason": "missing_dt_or_schemas"},
        )
        return state

    # ── Metric augmentation fast-path (turn > 1, prior state required) ──────
    if _is_metric_augmentation_request(user_query):
        state["csod_augment_mode"] = True
        state["csod_metric_augmentation_request"] = user_query
        state["csod_followup_executor_id"] = "metric_augmenter"
        state["csod_followup_graph_route"] = "csod_metrics_retrieval"
        state["csod_followup_short_circuit"] = True
        append_csod_narrative(
            state,
            "followup",
            "Metric augmentation detected",
            f"Adding to your existing analysis — running targeted metric lookup for: {user_query[:120]}",
        )
        _csod_log_step(
            state,
            "followup_router",
            "csod_followup_router",
            {"turn": turn, "query": user_query[:200]},
            {"executor_id": "metric_augmenter", "graph_route": "csod_metrics_retrieval", "augment_mode": True},
        )
        state["messages"].append(AIMessage(content="[Follow-up] → metric_augmenter (csod_metrics_retrieval)"))
        return state

    eligible = _eligible_direct_executor_ids()
    chosen: Optional[str] = None
    rationale = ""

    try:
        prompt_text = load_prompt("28_followup_router", prompts_dir=str(PROMPTS_CSOD))
        human = f"""user_query: {user_query}
prior_intent: {state.get("csod_intent", "")}
eligible_executor_ids: {json.dumps(eligible)}
Return JSON only."""
        raw = _llm_invoke(state, "csod_followup_router", prompt_text, human, [], False)
        parsed = _parse_json_response(raw, {})
        if parsed.get("direct") and parsed.get("executor_id"):
            eid = str(parsed["executor_id"]).strip().lower().replace(" ", "_").replace("-", "_")
            ex = get_executor(eid)
            if ex and ex.get("can_be_direct") and ex.get("implemented") is True:
                chosen = eid
                rationale = str(parsed.get("rationale", ""))
    except FileNotFoundError:
        logger.debug("28_followup_router prompt missing, using heuristics")
    except Exception as e:
        logger.warning("followup router LLM failed: %s", e)

    if not chosen:
        chosen = _heuristic_executor_id(user_query)
        if chosen:
            ex = get_executor(chosen)
            if not ex or not ex.get("can_be_direct") or ex.get("implemented") is not True:
                chosen = None
            else:
                rationale = "heuristic_keyword_match"

    if not chosen:
        append_csod_narrative(
            state,
            "followup",
            "Follow-up router",
            "Running full analysis pipeline for this question.",
        )
        return state

    route = _resolve_followup_route(chosen)
    if route == "full_spine":
        return state

    state["csod_followup_executor_id"] = chosen
    state["csod_followup_graph_route"] = route
    state["csod_followup_short_circuit"] = True
    disp = get_executor(chosen) or {}
    dname = disp.get("display_name", chosen)
    append_csod_narrative(
        state,
        "followup",
        "Follow-up detected",
        f"I still have your qualified metrics from the previous step. "
        f"Routing directly to {dname} — skipping re-retrieval. {rationale[:120]}",
    )
    _csod_log_step(
        state,
        "followup_router",
        "csod_followup_router",
        {"turn": turn, "query": user_query[:200]},
        {"executor_id": chosen, "graph_route": route},
    )
    state["messages"].append(
        AIMessage(content=f"[Follow-up] → {chosen} ({route})")
    )
    return state

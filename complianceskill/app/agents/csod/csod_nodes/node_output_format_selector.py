"""Post-metrics layout refinement: select the best dashboard template for the results."""
import json
import pathlib

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

_LAYOUTS_PATH = pathlib.Path(__file__).resolve().parents[4] / "config" / "dashboardLayouts.json"

# ── Output format categories ──
# goal_intent values map to presentation formats (how the user SEES the output).
# These are distinct from csod_intent (what ANALYSIS to perform).
_GOAL_INTENT_TO_LAYOUT = {
    # Visualization / presentation formats
    "dashboard": "executive-overview",
    "adhoc_analysis": "analytics-grid",
    "metrics_recommendations": "analytics-grid",
    "report": "minimal-analytics",
    "alert_generation": "compliance-command",
    "workflow_automation": "operations-monitoring",
    # alert_rca is dual-purpose: both an analysis type AND a visualization format
    "alert_rca": "compliance-command",
}

# Secondary fallback: csod_intent → layout (only for output-facing intents)
_OUTPUT_INTENT_FALLBACK = {
    "dashboard_generation_for_persona": "executive-overview",
    "metrics_dashboard_plan": "analytics-grid",
    "metrics_recommender_with_gold_plan": "analytics-grid",
}
_DEFAULT_TEMPLATE = "minimal-analytics"


def _load_layout_templates() -> dict:
    """Load layout templates from config/dashboardLayouts.json."""
    try:
        with open(_LAYOUTS_PATH, "r") as f:
            data = json.load(f)
        return data.get("layout_templates", {})
    except Exception as e:
        logger.warning("Could not load dashboardLayouts.json: %s", e)
        return {}


def _template_summaries(templates: dict) -> list:
    """Extract lightweight summaries for the LLM prompt (no chart schemas)."""
    summaries = []
    for tid, tmpl in templates.items():
        summaries.append({
            "id": tid,
            "name": tmpl.get("name", tid),
            "description": tmpl.get("description", ""),
            "bestFor": tmpl.get("bestFor", []),
            "domain": tmpl.get("domain", ""),
        })
    return summaries


def csod_output_format_selector_node(state: CSOD_State) -> CSOD_State:
    """Select the best layout template given goal, intent, and actual metrics found."""
    templates = _load_layout_templates()
    if not templates:
        state["csod_selected_layout"] = None
        return state

    # Gather context
    cp = state.get("compliance_profile") if isinstance(state.get("compliance_profile"), dict) else {}
    intent = state.get("csod_intent", "")
    user_query = state.get("user_query", "")
    goal_intent = state.get("goal_intent")
    goal_deliverables = cp.get("goal_deliverables")
    goal_flags = cp.get("goal_pipeline_flags")
    metrics = state.get("csod_metric_recommendations", [])
    kpis = state.get("csod_kpi_recommendations", [])

    # Build metric/KPI summaries for the prompt
    metric_names = [m.get("metric_name") or m.get("metric_id", "") for m in metrics[:15]]
    kpi_names = [k.get("kpi_name") or k.get("kpi_id", "") for k in kpis[:10]]

    selected_id = None
    reasoning = ""

    # Try LLM-based selection
    try:
        prompt_text = load_prompt("29_output_format_selector", prompts_dir=str(PROMPTS_CSOD))
        summaries = _template_summaries(templates)
        human = f"""user_query: {user_query}
goal_intent: {goal_intent}
goal_deliverables: {json.dumps(goal_deliverables)[:2000] if goal_deliverables else 'None'}
csod_intent: {intent}
metric_recommendations: {json.dumps(metric_names)}
kpi_recommendations: {json.dumps(kpi_names)}
layout_templates:
{json.dumps(summaries, indent=2)}
"""
        raw = _llm_invoke(state, "csod_output_format_selector", prompt_text, human, [], False)
        result = _parse_json_response(raw, {})
        selected_id = result.get("template_id")
        reasoning = result.get("reasoning", "")

        # Validate the LLM picked a real template
        if selected_id not in templates:
            logger.warning("LLM selected unknown template '%s', falling back", selected_id)
            selected_id = None
    except Exception as e:
        logger.warning("Output format selector LLM failed: %s, using fallback", e)

    # Deterministic fallback: prefer goal_intent (output format), then csod_intent
    if not selected_id:
        if goal_intent and goal_intent in _GOAL_INTENT_TO_LAYOUT:
            selected_id = _GOAL_INTENT_TO_LAYOUT[goal_intent]
            reasoning = f"Fallback: goal_intent '{goal_intent}' mapped to '{selected_id}'"
        elif intent in _OUTPUT_INTENT_FALLBACK:
            selected_id = _OUTPUT_INTENT_FALLBACK[intent]
            reasoning = f"Fallback: output intent '{intent}' mapped to '{selected_id}'"
        else:
            selected_id = _DEFAULT_TEMPLATE
            reasoning = f"Default layout: no specific output format matched"

    template = templates.get(selected_id, {})
    state["csod_selected_layout"] = {
        "template_id": selected_id,
        "template_name": template.get("name", selected_id),
        "layout_structure": template.get("data", {}),
        "reasoning": reasoning,
    }

    append_csod_narrative(
        state,
        "layout",
        "Output Format Selector",
        f"Selected '{template.get('name', selected_id)}' layout for presenting results. {reasoning}",
        {"template_id": selected_id},
    )
    _csod_log_step(
        state,
        "output_format_selection",
        "csod_output_format_selector",
        {"intent": intent, "goal_intent": goal_intent, "metrics_count": len(metrics)},
        {"template_id": selected_id, "reasoning": reasoning},
    )
    state["messages"].append(AIMessage(
        content=f"[Layout] Selected output format: {template.get('name', selected_id)}"
    ))

    return state

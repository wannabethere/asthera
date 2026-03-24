"""Post-assembly narration: ChatGPT/Claude-style conversational summary."""
import json

from langchain_core.messages import AIMessage

from app.agents.prompt_loader import load_prompt, PROMPTS_CSOD
from app.agents.csod.csod_nodes._helpers import (
    CSOD_State,
    _csod_log_step,
    _llm_invoke,
    logger,
)
from app.agents.csod.csod_nodes.narrative import append_csod_narrative


def csod_completion_narration_node(state: CSOD_State) -> CSOD_State:
    """Generate a conversational summary of the completed analysis."""
    try:
        prompt_text = load_prompt("30_completion_narration", prompts_dir=str(PROMPTS_CSOD))
    except FileNotFoundError as e:
        logger.error("Completion narration prompt not found: %s", e)
        state["csod_completion_narration"] = None
        return state

    # Collect context for the narration
    user_query = state.get("user_query", "")
    intent = state.get("csod_intent", "")

    # Narrative stream: compact summary
    narrative_stream = state.get("csod_narrative_stream", [])
    stream_summary = [
        {"title": entry.get("title", ""), "message": entry.get("message", "")}
        for entry in narrative_stream[-15:]  # last 15 entries max
    ]

    # Assembled output: extract key info (avoid sending full payload)
    assembled = state.get("csod_assembled_output") or {}
    assembled_summary = {}
    if isinstance(assembled, dict):
        assembled_summary = {
            k: (len(v) if isinstance(v, list) else ("present" if v else "empty"))
            for k, v in assembled.items()
            if k not in ("goal_pipeline_flags",)
        }

    # Selected layout
    selected_layout = state.get("csod_selected_layout") or {}
    layout_name = selected_layout.get("template_name", "none")

    # Metric/KPI highlights
    metrics = state.get("csod_metric_recommendations", [])
    kpis = state.get("csod_kpi_recommendations", [])
    metric_highlights = [m.get("metric_name") or m.get("metric_id", "") for m in metrics[:10]]
    kpi_highlights = [k.get("kpi_name") or k.get("kpi_id", "") for k in kpis[:10]]

    human = f"""user_query: {user_query}
intent: {intent}
narrative_stream:
{json.dumps(stream_summary, indent=2)[:6000]}
assembled_output_summary:
{json.dumps(assembled_summary, indent=2)[:4000]}
selected_layout: {layout_name}
metric_highlights: {json.dumps(metric_highlights)}
kpi_highlights: {json.dumps(kpi_highlights)}
"""

    try:
        # Get raw text response — NOT JSON
        narration = _llm_invoke(
            state, "csod_completion_narration", prompt_text, human, [], False
        )
        # Clean up any accidental JSON fences
        if narration and narration.strip().startswith("```"):
            lines = narration.strip().split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            narration = "\n".join(lines)

        state["csod_completion_narration"] = narration.strip() if narration else None
    except Exception as e:
        logger.error("Completion narration failed: %s", e, exc_info=True)
        state["csod_completion_narration"] = None

    append_csod_narrative(
        state,
        "completion",
        "Completion Summary",
        (state.get("csod_completion_narration") or "")[:200],
    )
    _csod_log_step(
        state,
        "completion_narration",
        "csod_completion_narration",
        {"intent": intent},
        {"narration_length": len(state.get("csod_completion_narration") or "")},
    )
    if state.get("csod_completion_narration"):
        state["messages"].append(AIMessage(content=state["csod_completion_narration"]))

    return state
